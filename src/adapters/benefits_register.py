"""
Adapter for Source 2 — Benefits Register (legacy XML).

This source is *always* slow (~0.7-2.4s per call) and *sometimes* fails
outright (500) — both are documented as normal operating behaviour, not
incidents. This adapter's whole job is to absorb that and hand the
assembly layer one of exactly three outcomes:

    ("ok",          record)   -- got a real answer
    ("not_found",   None)     -- the source answered and said "no such record"
    ("unavailable", reason)   -- could not get a real answer after retrying

All calls here are GET (read-only), so retrying is safe by construction:
there is no write to double. We still cap retries and use short backoff
so a caller isn't stuck absorbing 3 x 2.4s of latency on every request.

/health is exempt from both the delay and the failure injection (per the
data pack README), so it's the one reliable signal for "is the source up
at all" as opposed to "did this one call happen to fail."
"""
from __future__ import annotations

import time
import random
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

TIMEOUT_SECONDS = 5.0
MAX_ATTEMPTS = 3
BACKOFF_BASE = 0.25  # seconds, exponential with jitter


class SourceUnavailable(Exception):
    pass


def _record_from_xml(elem: ET.Element) -> dict:
    def text(tag):
        node = elem.find(tag)
        return node.text if node is not None else None

    return {
        "ref": text("Ref"),
        "name": text("Name"),
        "born": text("Born"),
        "addr": text("Addr"),
        "town": text("Town"),
        "benefit_code": text("BenefitCode"),
        "review_due": text("ReviewDue"),
    }


@dataclass
class BenefitsRegisterClient:
    base_url: str = "http://127.0.0.1:8082"

    def _raw_get(self, path: str) -> tuple[int, bytes]:
        url = f"{self.base_url}{path}"
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise SourceUnavailable(f"benefits-register unreachable: {e}") from e

    def health(self) -> bool:
        try:
            status, _ = self._raw_get("/health")
            return status == 200
        except SourceUnavailable:
            return False

    def _get_with_retry(self, path: str) -> tuple[int, bytes]:
        last_exc: Optional[Exception] = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                status, body = self._raw_get(path)
                if status == 500:
                    # Documented, expected, transient. Retry.
                    if attempt < MAX_ATTEMPTS:
                        time.sleep(BACKOFF_BASE * (2 ** (attempt - 1)) + random.uniform(0, 0.1))
                        continue
                    return status, body  # exhausted retries; let caller classify
                return status, body  # 200 or 404 — a real answer, stop here
            except SourceUnavailable as e:
                last_exc = e
                if attempt < MAX_ATTEMPTS:
                    time.sleep(BACKOFF_BASE * (2 ** (attempt - 1)) + random.uniform(0, 0.1))
        raise last_exc or SourceUnavailable("benefits-register unreachable")

    def get_by_ref(self, ref: str) -> tuple[str, Optional[dict]]:
        """Returns (outcome, record) where outcome is one of
        'ok' | 'not_found' | 'unavailable'."""
        try:
            status, body = self._get_with_retry(f"/records/{quote(ref, safe='')}")
        except SourceUnavailable:
            return "unavailable", None

        if status == 404:
            return "not_found", None
        if status != 200:
            return "unavailable", None

        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return "unavailable", None

        rec = root.find("Record")
        if rec is None:
            return "not_found", None
        return "ok", _record_from_xml(rec)

    def list_all(self) -> tuple[str, list[dict]]:
        """Returns (outcome, records). outcome is 'ok' or 'unavailable'."""
        try:
            status, body = self._get_with_retry("/records")
        except SourceUnavailable:
            return "unavailable", []
        if status != 200:
            return "unavailable", []
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return "unavailable", []
        return "ok", [_record_from_xml(r) for r in root.findall("Record")]
