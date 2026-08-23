"""
REST Resident Index Adapter with pagination deduplication
"""
import time
import json
import urllib.request
import urllib.error
from typing import Set, List, Dict, Any
from app.config import REST_SERVICE_URL, SERVICE_TIMEOUT_SECONDS
from app.models import AdapterResponse

class RestResidentAdapter:
    def __init__(self, base_url: str = REST_SERVICE_URL):
        self.base_url = base_url.rstrip('/')

    def fetch_all(self, max_pages: int = 50) -> AdapterResponse:
        start_time = time.time()
        all_records: List[Dict[str, Any]] = []
        seen_ids: Set[str] = set()
        duplicates_removed = 0
        current_page = 1
        has_more = True
        
        try:
            while has_more and current_page <= max_pages:
                url = f"{self.base_url}/residents?page={current_page}"
                req = urllib.request.Request(url, headers={'User-Agent': 'NoWrongDoor/1.0'})
                with urllib.request.urlopen(req, timeout=SERVICE_TIMEOUT_SECONDS) as resp:
                    if resp.status != 200:
                        break
                    data = json.loads(resp.read().decode('utf-8'))
                    page_results = data.get('results', [])
                    has_more = data.get('has_more', False)

                    for rec in page_results:
                        rid = rec.get('id')
                        if rid and rid in seen_ids:
                            duplicates_removed += 1
                            continue
                        if rid:
                            seen_ids.add(rid)
                        all_records.append(rec)
                
                current_page += 1

            latency = (time.time() - start_time) * 1000
            response = AdapterResponse(
                source_name="Resident Index (REST)",
                status="ok",
                records=all_records,
                total_count=len(all_records),
                latency_ms=latency,
                attempts_made=1
            )
            # Store internal duplicate metadata
            response.duplicates_removed = duplicates_removed  # type: ignore
            return response

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return AdapterResponse(
                source_name="Resident Index (REST)",
                status="failed",
                records=[],
                total_count=0,
                error_message=f"REST service error: {str(e)}",
                latency_ms=latency
            )

    def fetch_by_id(self, resident_id: str) -> AdapterResponse:
        start_time = time.time()
        url = f"{self.base_url}/residents/{urllib.parse.quote(resident_id)}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'NoWrongDoor/1.0'})
            with urllib.request.urlopen(req, timeout=SERVICE_TIMEOUT_SECONDS) as resp:
                if resp.status == 200:
                    rec = json.loads(resp.read().decode('utf-8'))
                    latency = (time.time() - start_time) * 1000
                    return AdapterResponse(
                        source_name="Resident Index (REST)",
                        status="ok",
                        records=[rec],
                        total_count=1,
                        latency_ms=latency
                    )
                else:
                    latency = (time.time() - start_time) * 1000
                    return AdapterResponse(
                        source_name="Resident Index (REST)",
                        status="failed",
                        records=[],
                        error_message=f"HTTP {resp.status}",
                        http_status=resp.status,
                        latency_ms=latency
                    )
        except urllib.error.HTTPError as e:
            latency = (time.time() - start_time) * 1000
            return AdapterResponse(
                source_name="Resident Index (REST)",
                status="failed" if e.code != 404 else "not_found",
                records=[],
                error_message=f"HTTP {e.code}: {e.reason}",
                http_status=e.code,
                latency_ms=latency
            )
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return AdapterResponse(
                source_name="Resident Index (REST)",
                status="failed",
                records=[],
                error_message=str(e),
                latency_ms=latency
            )
