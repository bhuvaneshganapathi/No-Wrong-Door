"""
Configuration settings for No Wrong Door Unified API
"""
import os

REST_SERVICE_URL = os.environ.get("REST_SERVICE_URL", "http://127.0.0.1:8081")
XML_SERVICE_URL = os.environ.get("XML_SERVICE_URL", "http://127.0.0.1:8082")
SERVER_PORT = int(os.environ.get("PORT", "8000"))

# Resilience Settings
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
RETRY_BACKOFF_FACTOR = float(os.environ.get("RETRY_BACKOFF_FACTOR", "0.2"))
SERVICE_TIMEOUT_SECONDS = float(os.environ.get("SERVICE_TIMEOUT_SECONDS", "3.0"))
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "300"))  # 5 minutes cache

# Identity Matching Thresholds
MATCH_HIGH_THRESHOLD = 0.85
MATCH_MEDIUM_THRESHOLD = 0.65
