import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

PORT = 8003
BASE_DIR = "/home/ubuntu/images"

# Dictionaries for state
ota_devices = {}
start_devices = {}
capture_pending = {} # Track if we want an image

def norm_mac(s):
    return s.replace(":", "").lower()

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body=""):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body.encode() if isinstance(body, str) else body)

    def do_POST(self):
        path = urlparse(self.path).path
        parts = [p for p in path.split("/") if p]
        mac = norm_mac(parts[1]) if len(parts) > 1 else "unknown"

        # 1. RECEIVE IMAGE: POST /upload/<mac>
        if parts[0] == "upload":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            save_path = f"{BASE_DIR}/images/{mac}"
            os.makedirs(save_path, exist_ok=True)
            filename = f"{save_path}/{int(time.time())}.jpg"
            
            with open(filename, "wb") as f:
                f.write(post_data)
            
            capture_pending[mac] = False # Auto-clear trigger
            print(f"Image saved for {mac}")
            self._send(200, "Image Received")

        # 2. RECEIVE LOGS: POST /log/<mac>
        elif parts[0] == "log":
            content_length = int(self.headers['Content-Length'])
            log_data = self.rfile.read(content_length).decode('utf-8')
            
            os.makedirs(f"{BASE_DIR}/logs", exist_ok=True)
            with open(f"{BASE_DIR}/logs/{mac}.log", "a") as f:
                f.write(f"[{time.ctime()}] {log_data}\n")
            self._send(200, "Log Saved")

    def do_GET(self):
        path = urlparse(self.path).path
        parts = [p for p in path.split("/") if p]
        if not parts: return self._send(200, "ok")
        
        mac = norm_mac(parts[1]) if len(parts) > 1 else None

        # Trigger Image Capture: /capture/<mac>/set
        if len(parts) == 3 and parts[0] == "capture" and parts[2] == "set":
            capture_pending[mac] = True
            self._send(200, f"Capture triggered for {mac}")

        # Device Polls for Image Task: /capture/<mac>
        elif len(parts) == 2 and parts[0] == "capture":
            if capture_pending.get(mac):
                self._send(200, "capture required")
            else:
                self._send(204, "")

# Ensure directories exist before starting
os.makedirs(f"{BASE_DIR}/images", exist_ok=True)
os.makedirs(f"{BASE_DIR}/logs", exist_ok=True)

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"SudoYantra Multi-Device Server running on {PORT}")
    server.serve_forever()
