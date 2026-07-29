from http.server import BaseHTTPRequestHandler, HTTPServer
import json, time, os

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Split the path. Example: "/2805A503DE4C/log" becomes ['', '2805A503DE4C', 'log']
        path_parts = self.path.strip("/").split("/")
        
        # 2. Check if the URL has the correct structure (MAC / "log")
        if len(path_parts) != 2 or path_parts[1] != "log":
            self.send_response(404)
            self.end_headers()
            return

        # 3. Extract the MAC address from the URL dynamically
        mac_id = path_parts[0].upper()

        # 4. Read the incoming JSON payload from the ESP32
        length  = int(self.headers['Content-Length'])
        body    = self.rfile.read(length)
        
        try:
            data = json.loads(body)
            log_msg = data.get("log", "Empty Log")
        except json.JSONDecodeError:
            self.send_response(400) # Bad Request if JSON is malformed
            self.end_headers()
            return

        # Print to your server terminal for live monitoring
        print(f"{time.strftime('%H:%M:%S')} [{mac_id}] {log_msg}")

        # 5. Dynamically route to the correct file based on the MAC
        logfile = os.path.join(LOG_DIR, f"{mac_id}.log")

        # 6. Append to the file (Added brackets to the timestamp to match your FastAPI viewer)
        with open(logfile, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {log_msg}\n")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

if __name__ == "__main__":
    print("Log server running on port 8001. Accepting logs from all robots...")
    HTTPServer(("0.0.0.0", 8001), Handler).serve_forever()
