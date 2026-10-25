#!/usr/bin/env python3
"""Локальный фейковый API (для проверки кэша без обращения к настоящему FPL): python tests/serve_mock.py 8765"""
import http.server, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import fpl_tool
COUNT = {"n": 0}
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("/api/", 1)[-1]
        if path == "__count__":
            body = json.dumps(COUNT).encode(); self.send_response(200); self.end_headers(); self.wfile.write(body); return
        COUNT["n"] += 1
        fn = fpl_tool._mock_name(path)
        if not os.path.exists(fn):
            self.send_response(404); self.end_headers(); return
        body = open(fn, "rb").read()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
