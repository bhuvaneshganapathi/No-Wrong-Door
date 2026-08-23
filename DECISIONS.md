# DECISIONS.md — Architecture & Design Rationale

## 1. Stack Choice & Standard Library Strategy

**Selected Stack**: Pure Python 3 Standard Library (`http.server`, `urllib.request`, `xml.etree.ElementTree`, `json`, `threading`).

### Why this stack?
- **Zero-Dependency Guarantee**: The handbook states: *"We will clone your repository into a clean environment and follow your README, and nothing else. If it does not start, it does not reach the judging panel..."* By avoiding external dependencies (Flask, FastAPI, Requests, pydantic), there is zero risk of broken `pip` installs or missing environment setup.
- **Portability & Speed**: Native execution on any Python 3.9+ runtime across Linux, macOS, and Windows.

---

## 2. Architectural Design & Adapter Isolation

The system separates concerns into distinct layers:

```
[ HTTP Clients / CLI ]
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                       app/server.py                         │
│                    (Unified HTTP API)                       │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    app/services/aggregator.py               │
│                  (Unified View Assembly)                    │
├──────────────────────────────┬──────────────────────────────┤
│    app/services/matcher.py   │    app/services/cache.py     │
│   (Identity Matcher Engine)  │   (Thread-Safe TTL Cache)    │
└──────────────┬──────────────┴──────────────┬────────────────┘
               │                             │
               ▼                             ▼
┌──────────────────────────────┐ ┌───────────────────────────┐
│ app/adapters/rest_adapter.py │ │app/adapters/xml_adapter.py│
│ (Page-Slip Deduplication)    │ │(Retry Engine & Failure)   │
└──────────────┬───────────────┘ └─────────────┬─────────────┘
               │                               │
               ▼                               ▼
    [ REST Service :8081 ]           [ XML Service :8082 ]
```

Each source adapter operates independently and conforms to a standard contract returning `AdapterResponse`. Upstream failures or format changes in one service do not impact the adapter or logic of another.

---

## 3. Features Kept vs. Features Cut

### Features Kept
1. **Graceful Degradation Metadata**: Every API response includes a `sources` block explicitly detailing status (`ok`, `degraded`, `failed`), latency, error messages, and retry attempts for each backend.
2. **Page-Slip Deduplication Engine**: The REST index sorts by `last_contact`, which slips during pagination. The `RestResidentAdapter` tracks unique record `id`s across page requests, dropping duplicates before payload assembly.
3. **Exponential Backoff & Jitter Retry Engine**: Automatic retries for transient 500 errors from the XML Benefits Register.
4. **In-Memory TTL Caching**: Caches XML responses for 5 minutes. If the XML service fails after max retries, the aggregator seamlessly falls back to cached data with explicit `from_cache: true` and warning metadata.
5. **Identity Resolution & Match Confidence (Stretch Goal)**: Normalizes names (`Maria Delgado` vs `DELGADO, Maria`), DOBs, and street addresses (`118 Cedar Ave` vs `118 Cedar Avenue`), outputting a match score and confidence level (`HIGH`, `MEDIUM`, `UNMATCHED`).
6. **Failure Rate & Resilience Monitoring**: Live metrics tracking total calls, failure counts, failure rate percentage (%), retries succeeded, and retries failed.

### Features Cut (and Why)
- **Persistent SQL Database (PostgreSQL / SQLite)**: Cut because data is read-only synthetic records. Adding a DB adds setup friction without benefiting the floor requirements.
- **Web Frontend**: Cut per Handbook guideline (*"Only Problem 4 scores the quality of the interface. Do not spend day two on a front end nobody is scoring."*).
- **Authentication / Authorization**: Cut as explicitly noted as "Not required" in problem specification.

---

## 4. Degradation Policy & Failure Matrix

| Failure Mode | Upstream Symptom | Solution Behavior & Payload Received | How Caller Knows |
| :--- | :--- | :--- | :--- |
| **REST Service Down** | HTTP 500 / Refused | Overall status: `failed`. Returns HTTP 500 with error details. | `status: "failed"`, REST source error populated. |
| **XML Service Transient 500** | Returns `SRV-500` (40% rate) | Retries up to 3 times with exponential backoff (0.2s, 0.4s, 0.8s). If retry succeeds, returns full data. | `sources.benefits_register.attempts_made > 1`. |
| **XML Service Persistent 500 (No Cache)** | Returns `SRV-500` after 3 retries | Payload status: `degraded`. Returns REST data intact. Benefits list is empty. | `status: "degraded"`, `sources.benefits_register.status: "degraded"`, explicit error message. |
| **XML Service Persistent 500 (With Cache)** | Returns `SRV-500` after 3 retries | Payload status: `degraded`. Returns REST data + cached XML benefits data. | `sources.benefits_register.from_cache: true`, warning message. |
| **REST Page Slipping** | Duplicate records on page boundary | Adapter filters duplicates via ID tracking `seen_ids`. | `sources.resident_index.duplicates_removed` counter incremented. |

---

## 5. Day 2 Surprise Challenge Log

### The Change
The Benefits Register (`xml_service.py`) failure rate was permanently increased to **40%** (`--failure-rate 0.40`).

### What We Changed
1. **Exponential Backoff Retry Strategy**:
   - Math: With a single call failing 40% ($p=0.40$), executing 3 retries reduces unhandled failure rate to $0.4^3 = 0.064$ (**6.4%**).
2. **TTL Cache Fallback**:
   - In-memory cache stores successful Benefits Register queries. When 3 retries fail, fresh cached data is served with `from_cache: true` and `staleness_warning`.
3. **Failure Rate Telemetry**:
   - Added real-time tracking of failure rates, retries succeeded, and retries failed, visible via `/api/v1/stats` and `cli.py --simulate 20`.

### What We Chose NOT to Change
- **Core API Payload Structure**: Callers continue to receive standard `status: "ok"` or `"degraded"` JSON schemas without breaking changes.
- **Identity Matching Engine**: Remained unchanged as it operates cleanly over whatever data the adapters retrieve.

### What We Would Do Differently in Production
- Implement a distributed circuit breaker (e.g. Netflix Hystrix pattern) that trips to `OPEN` state after 5 consecutive failures, avoiding wasting socket timeouts on a persistently failing service.

---

## 6. Testing Summary & Errors Faced

### Tests Executed
1. **`test_string_normalization`**: Verified address abbreviation expansion (`Ave` -> `avenue`, `St.` -> `street`).
2. **`test_identity_matcher_high_confidence`**: Verified `Maria Delgado` matched with `DELGADO, Maria` at score >= 0.85 (`HIGH`).
3. **`test_identity_matcher_mismatch_dob`**: Verified DOB mismatch drops confidence score below threshold.
4. **`test_ttl_cache`**: Verified in-memory key-value expiry.
5. **`test_aggregator_degradation_handling`**: Verified mock 500 failure produces `degraded` status with REST data intact.
6. **Live Simulation Test (`cli.py --simulate 20`)**: Verified system resilience under 20 consecutive requests against `xml_service.py --failure-rate 0.40`.

### Errors Faced & Resolved
- **Expat Parser Missing**: Encountered Unicode/Python environment encoding quirks; resolved by using standard library `xml.etree.ElementTree` with explicit UTF-8 string decoding.
- **REST Page-Boundary Slipping**: Solved duplicate records appearing when paging by maintaining `seen_ids` in `RestResidentAdapter`.
- **40% XML 500 Spikes**: Mitigated latency spikes and failures using backoff retries + fallback caching.
