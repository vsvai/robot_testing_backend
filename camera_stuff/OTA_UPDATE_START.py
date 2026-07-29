from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import json

PORT = 8005

# Dictionary to store state for ANY MAC address
devices = {}

def norm_mac(s):
    return s.replace(":", "").lower()

def get_device(mac):
    mac = norm_mac(mac)
    if mac not in devices:
        devices[mac] = {
            "ota_pending": False,
            "start_pending": False,
            "start_param": None,
            "wifi_pending": False,
            "wifi_param": None
        }
    return devices[mac]

class Handler(BaseHTTPRequestHandler):
    
    # Overrides default logging to hide noisy bot scans and keep the console clean
    def log_message(self, format, *args):
        pass

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send(self, code, body="", content_type="text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self._cors_headers()
        self.end_headers()
        if isinstance(body, str):
            body = body.encode()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        client_ip = self.client_address[0]
        path = urlparse(self.path).path
        parts = [p for p in path.split("/") if p]
        
        # LOG EVERY INCOMING REQUEST
        print(f"[{client_ip}] ---> GET {path}")

        # 1. Health check: /
        if len(parts) == 0:
            print(f"[{client_ip}] <--- 200 OK (Health Check)")
            self._send(200, "ok\n")
            return

        # 2. LEGACY OTA POLL: /<mac>
        if len(parts) == 1:
            mac = norm_mac(parts[0])
            device = get_device(mac)
            if device["ota_pending"]:
                print(f"[{client_ip}] <--- 200 OK (Legacy OTA required for {mac})")
                self._send(200, "ota required\n")
            else:
                self._send(204, "")
            return

        # 3. LEGACY OTA KILL: /<mac>/kill
        if len(parts) == 2 and parts[1] == "kill" and parts[0] not in ["ota", "start", "status", "wifi"]:
            mac = norm_mac(parts[0])
            device = get_device(mac)
            device["ota_pending"] = False
            print(f"[{client_ip}] <--- 200 OK (Legacy OTA cleared for {mac})")
            self._send(200, "ota cleared\n")
            return

        # For all other routes, we expect at least /<action>/<mac>
        if len(parts) < 2:
            print(f"[{client_ip}] <--- 404 Not Found")
            self._send(404, "not found\n")
            return

        action = parts[0]
        mac = norm_mac(parts[1])
        device = get_device(mac)

        # -------------------------
        # OTA ENDPOINTS
        # -------------------------
        if action == "ota":
            if len(parts) == 3 and parts[2] == "set":
                device["ota_pending"] = True
                print(f"[OTA] Set to TRUE for {mac}")
                self._send(200, "ota set\n")
                return

            if len(parts) == 3 and parts[2] == "kill":
                device["ota_pending"] = False
                print(f"[OTA] Cleared for {mac}")
                self._send(200, "ota cleared\n")
                return

            if len(parts) == 2:
                if device["ota_pending"]:
                    print(f"[{client_ip}] <--- 200 OK (OTA required for {mac})")
                    self._send(200, "ota required\n")
                else:
                    self._send(204, "")
                return

        # -------------------------
        # START / WIFI DURATION ENDPOINTS
        # -------------------------
        if action == "wifi":
            if len(parts) >= 3 and parts[2] == "set":
                param = parts[3] if len(parts) == 4 else "none"
                device["wifi_pending"] = True
                device["wifi_param"] = param
                print(f"[WIFI] Command SET for {mac} | Param: {param}")
                self._send(200, f"wifi set ({param})\n")
                return

            if len(parts) == 3 and parts[2] == "kill":
                device["wifi_pending"] = False
                device["wifi_param"] = None
                print(f"[WIFI] Command CLEARED by {mac}")
                self._send(200, "wifi cleared\n")
                return

            if len(parts) == 2:
                if device["wifi_pending"]:
                    print(f"[{client_ip}] <--- 200 OK (WIFI required: {device['wifi_param']} for {mac})")
                    self._send(200, f"wifi required: {device['wifi_param']}\n")
                else:
                    # Don't print 204s constantly to keep the console readable, unless you want to see them
                    self._send(204, "")
                return

        # -------------------------
        # START / CAMERA DURATION ENDPOINTS
        # -------------------------
        if action == "start":
            if len(parts) >= 3 and parts[2] == "set":
                param = parts[3] if len(parts) == 4 else "none"
                device["start_pending"] = True
                device["start_param"] = param
                print(f"[CAMERA] Command SET for {mac} | Param: {param}")
                self._send(200, f"start set ({param})\n")
                return

            if len(parts) == 3 and parts[2] == "kill":
                device["start_pending"] = False
                device["start_param"] = None
                print(f"[CAMERA] Command CLEARED by {mac}")
                self._send(200, "start cleared\n")
                return

            if len(parts) == 2:
                if device["start_pending"]:
                    print(f"[{client_ip}] <--- 200 OK (START required: {device['start_param']} for {mac})")
                    self._send(200, f"start required: {device['start_param']}\n")
                else:
                    self._send(204, "")
                return

        # -------------------------
        # STATUS ENDPOINT
        # -------------------------
        if action == "status" and len(parts) == 2:
            payload = {
                "mac": mac,
                "ota_pending": device["ota_pending"],
                "start_pending": device["start_pending"],
                "start_param": device["start_param"],
                "wifi_pending": device["wifi_pending"],
                "wifi_param": device["wifi_param"]
            }
            print(f"[{client_ip}] <--- 200 OK (Status Check for {mac})")
            self._send(200, json.dumps(payload), "application/json")
            return

        self._send(404, "not found\n")

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Server running on port {PORT}, accepting ANY MAC address.")
    print("Verbose logging enabled. Waiting for requests...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer shutting down.")
        server.server_close()
