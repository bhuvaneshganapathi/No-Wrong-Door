"""
No Wrong Door - Unified API HTTP Server (Stdlib ThreadingHTTPServer)
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import json
import urllib.parse
import urllib.request
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from app.config import SERVER_PORT, REST_SERVICE_URL, XML_SERVICE_URL
from app.services.aggregator import ResidentAggregator

aggregator = ResidentAggregator()

class UnifiedAPIHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def _send_json(self, code: int, payload: dict):
        body = json.dumps(payload, indent=2).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)

        # 1. Health Endpoint
        if u.path == '/health':
            rest_health = "unknown"
            xml_health = "unknown"
            try:
                with urllib.request.urlopen(f"{REST_SERVICE_URL}/health", timeout=1.5) as r:
                    rest_health = "ok" if r.status == 200 else f"HTTP {r.status}"
            except Exception as e:
                rest_health = f"error ({str(e)})"

            try:
                with urllib.request.urlopen(f"{XML_SERVICE_URL}/health", timeout=1.5) as r:
                    xml_health = "ok" if r.status == 200 else f"HTTP {r.status}"
            except Exception as e:
                xml_health = f"error ({str(e)})"

            return self._send_json(200, {
                "status": "ok",
                "service": "No Wrong Door Unified API",
                "upstreams": {
                    "resident_index": rest_health,
                    "benefits_register": xml_health
                }
            })

        # 2. Stats Endpoint (Failure rates & metrics)
        if u.path == '/api/v1/stats':
            stats = aggregator.xml_adapter.get_stats()
            return self._send_json(200, {
                "status": "ok",
                "xml_service_failure_stats": stats
            })

        # 3. Residents Endpoint (List & Pagination)
        if u.path == '/api/v1/residents' or u.path == '/residents':
            try:
                page = int(q.get('page', ['1'])[0])
                page_size = int(q.get('page_size', ['25'])[0])
            except ValueError:
                return self._send_json(400, {"error": "bad_request", "message": "Invalid page parameters"})

            result = aggregator.get_unified_view(page=page, page_size=page_size)
            return self._send_json(200, result)

        # 4. Single Resident Endpoint
        if u.path.startswith('/api/v1/residents/') or u.path.startswith('/residents/'):
            rid = u.path.rsplit('/', 1)[-1]
            if not rid:
                return self._send_json(400, {"error": "bad_request", "message": "Missing resident ID"})

            result = aggregator.get_unified_view(resident_id=rid)
            if result['status'] == 'failed' or not result['residents']:
                return self._send_json(404, {"error": "not_found", "message": f"Resident {rid} not found"})
            return self._send_json(200, result)

        return self._send_json(404, {"error": "not_found", "path": u.path})

    def log_message(self, fmt, *a):
        print(f"  [unified-api] {fmt % a}")

def run_server(port: int = SERVER_PORT):
    server_address = ('127.0.0.1', port)
    httpd = ThreadingHTTPServer(server_address, UnifiedAPIHandler)
    print(f"==================================================")
    print(f" No Wrong Door Unified API Server")
    print(f" Running on http://127.0.0.1:{port}")
    print(f" Endpoints:")
    print(f"   GET /health")
    print(f"   GET /api/v1/residents?page=1&page_size=25")
    print(f"   GET /api/v1/residents/<id>")
    print(f"   GET /api/v1/stats")
    print(f"==================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="No Wrong Door Unified API Server")
    parser.add_argument('--port', type=int, default=SERVER_PORT, help="Port to listen on (default 8000)")
    args = parser.parse_args()
    run_server(args.port)
