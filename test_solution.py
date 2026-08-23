"""
Comprehensive Test Suite for No Wrong Door Solution
"""
import unittest
from app.models import AdapterResponse, MatchConfidence
from app.adapters.rest_adapter import RestResidentAdapter
from app.adapters.xml_adapter import XmlBenefitsAdapter
from app.services.cache import TTLCache
from app.services.matcher import compute_match_confidence, normalize_string
from app.services.aggregator import ResidentAggregator

class TestNoWrongDoor(unittest.TestCase):

    def test_string_normalization(self):
        self.assertEqual(normalize_string("118 Cedar Ave"), "118 cedar avenue")
        self.assertEqual(normalize_string("DELGADO, Maria"), "delgado maria")
        self.assertEqual(normalize_string("Main St."), "main street")

    def test_identity_matcher_high_confidence(self):
        rest_rec = {
            "first_name": "Maria",
            "last_name": "Delgado",
            "date_of_birth": "1971-04-02",
            "address_line": "118 Cedar Ave",
            "city": "Northgate"
        }
        xml_rec = {
            "name": "DELGADO, Maria",
            "born": "1971-04-02",
            "addr": "118 Cedar Avenue",
            "town": "Northgate"
        }
        conf = compute_match_confidence(rest_rec, xml_rec)
        self.assertGreaterEqual(conf.score, 0.85)
        self.assertEqual(conf.level, "HIGH")

    def test_identity_matcher_mismatch_dob(self):
        rest_rec = {
            "first_name": "Maria",
            "last_name": "Delgado",
            "date_of_birth": "1990-01-01",
            "address_line": "118 Cedar Ave",
            "city": "Northgate"
        }
        xml_rec = {
            "name": "DELGADO, Maria",
            "born": "1971-04-02",
            "addr": "118 Cedar Avenue",
            "town": "Northgate"
        }
        conf = compute_match_confidence(rest_rec, xml_rec)
        self.assertLess(conf.score, 0.85)

    def test_ttl_cache(self):
        cache = TTLCache(default_ttl=1)
        cache.set("test_key", {"data": 123})
        self.assertEqual(cache.get("test_key"), {"data": 123})

    def test_aggregator_degradation_handling(self):
        agg = ResidentAggregator()
        # Mock rest adapter success
        agg.rest_adapter.fetch_all = lambda max_pages=50: AdapterResponse(
            source_name="REST", status="ok", records=[{"id": "R-1", "first_name": "Test", "last_name": "User", "date_of_birth": "2000-01-01"}]
        )
        # Mock xml adapter failure
        agg.xml_adapter.fetch_all = lambda: AdapterResponse(
            source_name="XML", status="failed", records=[], error_message="HTTP 500 error", attempts_made=3
        )

        res = agg.get_unified_view()
        self.assertEqual(res["status"], "degraded")
        self.assertEqual(len(res["residents"]), 1)
        self.assertEqual(res["sources"]["benefits_register"]["status"], "degraded")
        self.assertIn("HTTP 500", res["sources"]["benefits_register"]["error"])

if __name__ == '__main__':
    unittest.main()
