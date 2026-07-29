
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import json
import sys

import threading

PORT = 8000
MAC = sys.argv[1]

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed  = urlparse(self.path)
        qs      = parse_qs(parsed.query)
        
        if parsed.path == "/" + MAC + "/kill":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Server shutting down\n")

            sys.exit(1)
            #threading.Thread(target=self.server.shutdown).start()

        if parsed.path != "/" + MAC:
            self.send_response(404)
            print("mac not found")
            self.end_headers()
            return

        self.send_response(200)
        self.end_headers()

        print("mac correct")



if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Server running on port {PORT}")
    server.serve_forever()
    print("serer_stopped")
