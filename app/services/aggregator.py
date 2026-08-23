"""
Aggregator service for assembling Unified Resident View with Graceful Degradation
"""
import time
from typing import Dict, Any, List, Optional
from app.adapters.rest_adapter import RestResidentAdapter
from app.adapters.xml_adapter import XmlBenefitsAdapter
from app.services.cache import global_cache
from app.services.matcher import find_matching_benefits

class ResidentAggregator:
    def __init__(self):
        self.rest_adapter = RestResidentAdapter()
        self.xml_adapter = XmlBenefitsAdapter()

    def get_unified_view(self, resident_id: Optional[str] = None, page: int = 1, page_size: int = 25) -> Dict[str, Any]:
        start_time = time.time()

        # 1. Fetch REST Data
        if resident_id:
            rest_resp = self.rest_adapter.fetch_by_id(resident_id)
        else:
            rest_resp = self.rest_adapter.fetch_all()

        # 2. Fetch XML Data with caching fallback
        xml_resp = self.xml_adapter.fetch_all()

        xml_records = []
        is_xml_degraded = False
        xml_from_cache = False
        xml_error_msg = None

        if xml_resp.status == "ok":
            xml_records = xml_resp.records
            # Cache XML records for fallback
            global_cache.set("xml_all_records", xml_records)
        else:
            # Service failed or degraded - attempt to use cache
            cached_xml = global_cache.get("xml_all_records")
            if cached_xml is not None:
                xml_records = cached_xml
                is_xml_degraded = True
                xml_from_cache = True
                xml_error_msg = f"Upstream failure ({xml_resp.error_message}). Served from cache."
            else:
                is_xml_degraded = True
                xml_error_msg = xml_resp.error_message or "Benefits Register service unavailable"

        # Determine overall payload status
        if rest_resp.status == "failed":
            overall_status = "failed"
        elif is_xml_degraded:
            overall_status = "degraded"
        else:
            overall_status = "ok"

        # 3. Assemble Unified Records with Identity Matching
        unified_residents = []
        rest_records = rest_resp.records

        # Pagination slice for REST records if returning list
        total_rest_count = len(rest_records)
        if not resident_id:
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paged_rest_records = rest_records[start_idx:end_idx]
        else:
            paged_rest_records = rest_records

        for rrec in paged_rest_records:
            matched_benefits = find_matching_benefits(rrec, xml_records) if xml_records else []
            unified_rec = {
                "id": rrec.get("id"),
                "first_name": rrec.get("first_name"),
                "last_name": rrec.get("last_name"),
                "date_of_birth": rrec.get("date_of_birth"),
                "address_line": rrec.get("address_line"),
                "city": rrec.get("city"),
                "phone": rrec.get("phone"),
                "program_status": rrec.get("program_status"),
                "last_contact": rrec.get("last_contact"),
                "matched_benefits_count": len(matched_benefits),
                "benefits": [b.to_dict() for b in matched_benefits]
            }
            unified_residents.append(unified_rec)

        total_latency = (time.time() - start_time) * 1000

        # Assembly result payload
        result = {
            "status": overall_status,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sources": {
                "resident_index": {
                    "status": rest_resp.status,
                    "record_count": len(rest_records),
                    "latency_ms": round(rest_resp.latency_ms, 2),
                    "duplicates_removed": getattr(rest_resp, 'duplicates_removed', 0),
                    "error": rest_resp.error_message
                },
                "benefits_register": {
                    "status": "degraded" if is_xml_degraded else xml_resp.status,
                    "record_count": len(xml_records),
                    "latency_ms": round(xml_resp.latency_ms, 2),
                    "attempts_made": xml_resp.attempts_made,
                    "from_cache": xml_from_cache,
                    "error": xml_error_msg
                }
            },
            "failure_rate_stats": self.xml_adapter.get_stats(),
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_residents": total_rest_count,
                "has_more": (page * page_size) < total_rest_count if not resident_id else False
            },
            "residents": unified_residents,
            "total_latency_ms": round(total_latency, 2)
        }

        return result
