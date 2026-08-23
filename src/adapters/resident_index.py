"""
Adapter for Source 1 — Resident Index (REST, paginated JSON).

This adapter owns everything specific to this source:
  - HTTP calls and status handling
  - The pagination walk (and the dedup that walk requires, because the
    upstream index is reordered mid-page by other processes and can
    hand back a record it already gave us on the previous page)
  - Translating upstream failure into the adapter's own small,
    predictable error type

Nothing outside this file knows the Resident Index is paginated, or that
its pages can overlap. That's deliberate: on day two the requirements
change, and this source's behaviour should be able to change without the
assembly layer or the other adapter caring.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional

TIMEOUT_SECONDS = 5.0


class SourceUnavailable(Exception):
    """Raised when the Resident Index could not be reached at all
    (connection refused, timeout, non-JSON body). A 404 is NOT this —
    a 404 is a valid, successful answer ("no such resident")."""


@dataclass
class ResidentIndexClient:
    base_url: str = "http://127.0.0.1:8081"

    def _get(self, path: str) -> tuple[int, dict]:
        url = f"{self.base_url}{path}"
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as resp:
                body = resp.read()
                return resp.status, json.loads(body)
        except urllib.error.HTTPError as e:
            # HTTPError still carries a body/status — the service answered,
            # it just answered with an error code. Not a SourceUnavailable.
            body = e.read()
            try:
                return e.code, json.loads(body)
            except Exception:
                return e.code, {}
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise SourceUnavailable(f"resident-index unreachable: {e}") from e
        except json.JSONDecodeError as e:
            raise SourceUnavailable(f"resident-index returned non-JSON: {e}") from e

    def health(self) -> bool:
        try:
            status, _ = self._get("/health")
            return status == 200
        except SourceUnavailable:
            return False

    def get_resident(self, resident_id: str) -> Optional[dict]:
        """Returns the record, or None if the id genuinely does not exist.
        Raises SourceUnavailable if the source could not be reached."""
        status, payload = self._get(f"/residents/{resident_id}")
        if status == 200:
            return payload
        if status == 404:
            return None
        raise SourceUnavailable(f"resident-index returned unexpected status {status}")

    def list_all_residents(self) -> list[dict]:
        """Walks every page and returns the deduplicated record set.

        The upstream index can serve the same record on two consecutive
        pages when a boundary slips backwards mid-walk. We dedup by `id`
        as we go, so the same source record is never counted, returned,
        or double-counted twice in the unified output — this is the
        "duplicate-across-pages" floor requirement.
        """
        seen: dict[str, dict] = {}
        page = 1
        while True:
            status, payload = self._get(f"/residents?page={page}&page_size=25")
            if status != 200:
                raise SourceUnavailable(f"resident-index returned unexpected status {status}")
            for record in payload.get("results", []):
                seen[record["id"]] = record  # last-write-wins; content is identical either way
            if not payload.get("has_more"):
                break
            page += 1
        return list(seen.values())
