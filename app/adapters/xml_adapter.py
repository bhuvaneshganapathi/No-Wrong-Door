"""
XML Benefits Register Adapter with exponential backoff retries and failure tracking
"""
import time
import random
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple
from app.config import XML_SERVICE_URL, MAX_RETRIES, RETRY_BACKOFF_FACTOR, SERVICE_TIMEOUT_SECONDS
from app.models import AdapterResponse

class XmlBenefitsAdapter:
    def __init__(self, base_url: str = XML_SERVICE_URL):
        self.base_url = base_url.rstrip('/')
        # Failure tracking counters
        self.total_calls = 0
        self.total_failures = 0
        self.retries_succeeded = 0
        self.retries_failed = 0

    def parse_xml_records(self, xml_text: str) -> List[Dict[str, Any]]:
        root = ET.fromstring(xml_text)
        records = []
        if root.tag == 'BenefitsRegister':
            for rec in root.findall('Record'):
                records.append({
                    'ref': rec.findtext('Ref', '').strip(),
                    'name': rec.findtext('Name', '').strip(),
                    'born': rec.findtext('Born', '').strip(),
                    'addr': rec.findtext('Addr', '').strip(),
                    'town': rec.findtext('Town', '').strip(),
                    'benefit_code': rec.findtext('BenefitCode', '').strip(),
                    'review_due': rec.findtext('ReviewDue', '').strip(),
                })
        elif root.tag == 'Record':
            records.append({
                'ref': root.findtext('Ref', '').strip(),
                'name': root.findtext('Name', '').strip(),
                'born': root.findtext('Born', '').strip(),
                'addr': root.findtext('Addr', '').strip(),
                'town': root.findtext('Town', '').strip(),
                'benefit_code': root.findtext('BenefitCode', '').strip(),
                'review_due': root.findtext('ReviewDue', '').strip(),
            })
        return records

    def _execute_with_retry(self, url: str) -> Tuple[bool, int, str, int, float]:
        """
        Executes HTTP GET request with exponential backoff retry.
        Returns: (success, status_code, body_text, attempt_count, total_latency_ms)
        """
        start_time = time.time()
        attempt = 0
        last_error = ""
        last_status = 500

        while attempt < MAX_RETRIES:
            attempt += 1
            self.total_calls += 1
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'NoWrongDoor/1.0'})
                with urllib.request.urlopen(req, timeout=SERVICE_TIMEOUT_SECONDS) as resp:
                    body = resp.read().decode('utf-8')
                    if resp.status == 200:
                        if attempt > 1:
                            self.retries_succeeded += 1
                        latency = (time.time() - start_time) * 1000
                        return True, 200, body, attempt, latency
                    last_status = resp.status
                    last_error = f"HTTP {resp.status}"
            except urllib.error.HTTPError as e:
                last_status = e.code
                last_error = f"HTTP {e.code}: {e.reason}"
            except Exception as e:
                last_status = 503
                last_error = str(e)

            self.total_failures += 1
            # Exponential backoff with jitter if another attempt remains
            if attempt < MAX_RETRIES:
                sleep_time = (RETRY_BACKOFF_FACTOR * (2 ** (attempt - 1))) + random.uniform(0.01, 0.1)
                time.sleep(sleep_time)

        self.retries_failed += 1
        latency = (time.time() - start_time) * 1000
        return False, last_status, last_error, attempt, latency

    def fetch_all(self) -> AdapterResponse:
        url = f"{self.base_url}/records"
        success, status_code, body, attempts, latency = self._execute_with_retry(url)

        if success:
            try:
                records = self.parse_xml_records(body)
                return AdapterResponse(
                    source_name="Benefits Register (XML)",
                    status="ok",
                    records=records,
                    total_count=len(records),
                    latency_ms=latency,
                    attempts_made=attempts
                )
            except Exception as pe:
                return AdapterResponse(
                    source_name="Benefits Register (XML)",
                    status="failed",
                    records=[],
                    error_message=f"XML Parsing Error: {str(pe)}",
                    latency_ms=latency,
                    attempts_made=attempts
                )
        else:
            return AdapterResponse(
                source_name="Benefits Register (XML)",
                status="failed",
                records=[],
                error_message=f"Benefits Register failed after {attempts} attempts ({body})",
                http_status=status_code,
                latency_ms=latency,
                attempts_made=attempts
            )

    def fetch_by_ref(self, ref: str) -> AdapterResponse:
        encoded_ref = urllib.parse.quote(ref)
        url = f"{self.base_url}/records/{encoded_ref}"
        success, status_code, body, attempts, latency = self._execute_with_retry(url)

        if success:
            try:
                records = self.parse_xml_records(body)
                return AdapterResponse(
                    source_name="Benefits Register (XML)",
                    status="ok" if records else "not_found",
                    records=records,
                    total_count=len(records),
                    latency_ms=latency,
                    attempts_made=attempts
                )
            except Exception as pe:
                return AdapterResponse(
                    source_name="Benefits Register (XML)",
                    status="failed",
                    records=[],
                    error_message=f"XML Parsing Error: {str(pe)}",
                    latency_ms=latency,
                    attempts_made=attempts
                )
        else:
            return AdapterResponse(
                source_name="Benefits Register (XML)",
                status="failed" if status_code != 404 else "not_found",
                records=[],
                error_message=f"Benefits Register failed after {attempts} attempts ({body})",
                http_status=status_code,
                latency_ms=latency,
                attempts_made=attempts
            )

    def get_stats(self) -> Dict[str, Any]:
        failure_rate = (self.total_failures / self.total_calls * 100) if self.total_calls > 0 else 0.0
        return {
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "failure_rate_percent": round(failure_rate, 2),
            "retries_succeeded": self.retries_succeeded,
            "retries_failed": self.retries_failed
        }
