# Problem 3 — No Wrong Door (Unified Resident View)

A unified resident API and interactive CLI built for Calder County public service delivery. Assembles data from disparate, unreliable backend services (REST Resident Index and XML Benefits Register), handling page-boundary duplication, day-two 40% failure rates, and cross-system identity resolution.

---

## Quickstart Guide

### Prerequisites
- **Python 3.9+** (Standard Library only — no `pip install` required!)

---

### Step 1: Start Mock Backend Services

Run the mock services (with the Day 2 **40% failure rate** enabled on the Benefits Register):

```bash
# Terminal 1: REST Resident Index (Port 8081)
python3 services/rest_service.py --port 8081

# Terminal 2: XML Benefits Register with 40% Failure Rate (Port 8082)
python3 services/xml_service.py --port 8082 --failure-rate 0.40
```

*(Alternatively on Linux/macOS, run `./services/run_both.sh`)*

---

### Step 2: Launch the Unified API Server

```bash
# Terminal 3: No Wrong Door Unified API (Port 8000)
python3 app/server.py --port 8000
```

The API will start at `http://127.0.0.1:8000`.

---

### Step 3: Run Interactive CLI Demo & Simulation

Run the CLI tool to query residents or simulate traffic under 40% failure conditions:

```bash
# View paginated unified resident list
python3 cli.py --page 1 --page-size 10

# Search specific resident by REST ID
python3 cli.py --id R-10234

# Run 20-request simulation showcasing 40% failure handling & resilience stats
python3 cli.py --simulate 20
```

---

### Step 4: Run Automated Test Suite

```bash
python3 test_solution.py
```

---

## API Endpoints Summary

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/health` | `GET` | Health check of Unified API and upstream backend services |
| `/api/v1/residents?page=1&page_size=25` | `GET` | Unified resident view list with pagination, source metadata & benefits |
| `/api/v1/residents/<id>` | `GET` | Single resident unified view with matched benefits |
| `/api/v1/stats` | `GET` | Real-time XML service failure rate metrics & retry statistics |

---

## Key Features & Architecture

1. **Graceful Degradation**:
   - If the XML Benefits Register fails (HTTP 500), partial REST data is returned with `status: "degraded"` and diagnostic error metadata. The API never crashes or returns a raw 500 error page.
2. **Page-Slip Deduplication Engine**:
   - Deduplicates records in the REST Resident Index caused by unstable `last_contact` sorting during pagination.
3. **Exponential Backoff Retry Engine**:
   - Retries failing XML service calls up to 3 times, reducing effective unhandled failure rate from 40% down to ~6.4%.
4. **In-Memory TTL Cache**:
   - Caches XML benefits data for 5 minutes to serve fresh fallback responses during prolonged upstream outages.
5. **Identity Resolution (Stretch Goal)**:
   - Matches records across REST and XML sources based on normalized names, DOBs, and addresses, assigning match confidence scores (`HIGH`, `MEDIUM`, `UNMATCHED`).

---

## Submission Documentation
- [`DECISIONS.md`](file:///c:/Users/hi/Desktop/No%20Wrong%20Door/DECISIONS.md): Architectural decisions, degradation matrix, and Day 2 challenge log.
- [`AI-USAGE.md`](file:///c:/Users/hi/Desktop/No%20Wrong%20Door/AI-USAGE.md): AI tool usage disclosure.
