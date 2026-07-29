from http.server import BaseHTTPRequestHandler, HTTPServer
import sys, json, time, os, re

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Regex to match paths like /2805A503DE4C/log and extract the MAC
PATH_PATTERN = re.compile(r"^/([0-9A-F]{12})/log$", re.IGNORECASE)

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Check if the path matches our expected format and extract MAC
        match = PATH_PATTERN.match(self.path)
        
        if not match:
            self.send_response(404)
            self.end_headers()
            return
            
        # 2. Grab the MAC address from the URL path and force uppercase
        mac_id = match.group(1).upper()

        # 3. Read the JSON payload
        length  = int(self.headers['Content-Length'])
        body    = self.rfile.read(length)
        
        try:
            data = json.loads(body)
            log_message = data.get("log", "")
        except json.JSONDecodeError:
            self.send_response(400) # Bad Request if JSON is malformed
            self.end_headers()
            return

        # Print to terminal for live debugging
        print(f"{time.strftime('%H:%M:%S')} [{mac_id}] {log_message}")

        # 4. Dynamically set the file path based on the incoming MAC
        logfile = os.path.join(LOG_DIR, f"{mac_id}.log")

        # 5. Write to the file with bracketed timestamps for the FastAPI viewer
        with open(logfile, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {log_message}\n")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

if __name__ == "__main__":
    print("Starting ESP log receiver on port 8007 (Accepting all MACs)...")
    HTTPServer(("0.0.0.0", 8007), Handler).serve_forever()
