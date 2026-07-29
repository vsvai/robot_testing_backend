from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import json

DEVICE_FILE = "device.txt"

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed  = urlparse(self.path)
        qs      = parse_qs(parsed.query)

        if parsed.path != "/register":
            self.send_response(404)
            self.end_headers()
            return

        mac     = qs.get("mac", ["unknown"])[0]
        ip      = self.client_address[0]
        ts      = datetime.now().isoformat()

        found = False
        new_lines = []

        try:
            with open(DEVICE_FILE, "r") as f:
                for line in f:
                    t,m,old_ip = line.strip().split(",")

                    print(m)
                    print(mac)
                    if m == mac:
                        new_lines.append(f"{ts},{mac},{ip}\n")
                        found = True
                    else:
                        new_lines.append(line)
        except FileNotFoundError:
            pass

        if not found:
            new_lines.append(f"{ts},{mac},{ip}\n")
        else:
            print("mac address already exists.")

        with open(DEVICE_FILE, "w") as f:
            f.writelines(new_lines)

        resp = {
                "ack"   : True,
                "mac"   : mac,
                "ip"    : ip
                }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode())


print("IP server running on port 8080")
HTTPServer(("0.0.0.0",8080), Handler).serve_forever()
