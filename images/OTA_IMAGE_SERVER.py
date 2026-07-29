from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import json
import os
import glob # Needed to search for timestamp files

PORT = 8004 # Set this to the port you are using
devices = {}

# Make sure this points to your actual base images folder
BASE_IMAGES_FOLDER = "/home/ubuntu/images/images/"

def norm_mac(s):
    return s.replace(":", "").lower()

def get_device(mac):
    mac = norm_mac(mac)
    if mac not in devices:
        devices[mac] = {"ota_pending": False, "start_pending": False, "direction": None}
    return devices[mac]

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body="", content_type="text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        if isinstance(body, str):
            body = body.encode()
        self.wfile.write(body)

    # (POST section is unchanged from before)
    def do_POST(self):
        path = urlparse(self.path).path
        parts = [p for p in path.split("/") if p]
        # --- (Existing image upload handler to folders) ---
        # I am assuming your current POST handler already does this properly
        if len(parts) == 2 and parts[0] == "upload":
            mac = norm_mac(parts[1])
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send(400, "no content\n")
                return
            post_data = self.rfile.read(content_length)
            # Code to save to folder is here in your script.
            # I will not provide that part to avoid breaking your current setup.
            self._send(200, "Image uploaded\n")
            return
        self._send(404, "not found\n")

    def do_GET(self):
        path = urlparse(self.path).path
        parts = [p for p in path.split("/") if p]

        # Keep existing logic for health check, OTA poll, and OTA kill
        if len(parts) == 0:
            self._send(200, "ok\n")
            return
        if len(parts) == 1:
            mac = norm_mac(parts[0])
            device = get_device(mac)
            if device["ota_pending"]:
                self._send(200, "ota required\n")
            else:
                self._send(204, "")
            return
        if len(parts) == 2 and parts[1] == "kill" and parts[0] not in ["ota", "start", "status", "view"]:
            mac = norm_mac(parts[0])
            device = get_device(mac)
            device["ota_pending"] = False
            self._send(200, "ota cleared\n")
            return

        if len(parts) < 2:
            self._send(404, "not found\n")
            return

        action = parts[0]
        mac = norm_mac(parts[1])
        device = get_device(mac)

        # -------------------------
        # NEW: COMPREHENSIVE VIEW SECTION
        # -------------------------
        if action == "view":
            mac_folder = os.path.join(BASE_IMAGES_FOLDER, mac)

            # 1. Gallery View: /view/<mac>
            # (Displays list of all timestamps)
            if len(parts) == 2:
                # Scan for all JPEG files
                search_path = os.path.join(mac_folder, "*.jpg")
                # Sort files to ensure timestamps appear chronologically
                files = sorted(glob.glob(search_path))

                if not files:
                    self._send(404, "No images found for this device yet\n")
                    return

                # Construct the HTML gallery page
                html_title = f"Photo Log - {mac}"
                html_body = f"<h2>Photo Log: {mac}</h2><ul>"
                
                # Internal CSS to resemble log page (monospaced)
                html_style = """
                <style>
                    body { font-family: 'Consolas', 'Monaco', 'Courier New', monospace; background-color: #f4f7f6; color: #333; padding: 20px; }
                    h2 { border-bottom: 2px solid #ccc; padding-bottom: 10px; }
                    ul { list-style-type: none; padding: 0; }
                    li { background-color: white; border: 1px solid #ddd; margin-bottom: 5px; padding: 10px; border-radius: 3px; display: flex; align-items: center;}
                    a { color: #007bff; text-decoration: none; font-weight: bold;}
                    a:hover { text-decoration: underline;}
                    .time-icon { font-size: 0.8em; margin-right: 10px;}
                </style>
                """
                
                for file_path in files:
                    # Extract timestamp (e.g., "1773602828") from "/home/.../images/mac/1773602828.jpg"
                    timestamp = os.path.splitext(os.path.basename(file_path))[0]
                    # Create link that points to the single image view endpoint
                    html_body += f"<li><span class='time-icon'>[</span><a href='/view/{mac}/{timestamp}'>{timestamp}</a><span class='time-icon'>]</span></li>"
                
                html_body += "</ul>"
                full_html = f"<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>{html_style}<title>{html_title}</title></head><body>{html_body}</body>html>"
                self._send(200, full_html, "text/html")
                return

            # 2. Single Image View: /view/<mac>/<timestamp>
            # (Displays a specific photo)
            elif len(parts) == 3:
                timestamp = parts[2]
                filename = f"{timestamp}.jpg"
                latest_file_path = os.path.join(mac_folder, filename)

                if os.path.exists(latest_file_path):
                    with open(latest_file_path, "rb") as f:
                        self.send_response(200)
                        self.send_header("Content-Type", "image/jpeg")
                        self.end_headers()
                        self.wfile.write(f.read())
                    return
                else:
                    self._send(404, "Specified image not found\n")
                    return

        # -------------------------
        # (Existing handlers for OTA, START, STATUS - Keep these)
        # -------------------------
        # I'll not repeat the full ota/start sections to keep the snippet focused
        # but they must remain in your file.
        # ...

        self._send(404, "not found\n")

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Server running on port {PORT}")
    server.serve_forever()
