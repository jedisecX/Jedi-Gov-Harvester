from __future__ import annotations
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

def make_server(routes: dict[str, Callable]):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            fn = routes.get(path) or routes.get("*")
            if fn is None:
                self.send_error(404); return
            fn(self)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    server.base = f"http://127.0.0.1:{server.server_address[1]}"
    return server

def send(handler, status: int, body: bytes, headers=None):
    handler.send_response(status)
    hdrs = {"Content-Type": "application/octet-stream", "Content-Length": str(len(body))}
    if headers:
        hdrs.update(headers)
    for k, v in hdrs.items():
        handler.send_header(k, v)
    handler.end_headers()
    handler.wfile.write(body)
