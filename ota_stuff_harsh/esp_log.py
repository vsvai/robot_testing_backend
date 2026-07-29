from http.server import BaseHTTPRequestHandler, HTTPServer
import sys, json, time, os

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

EXPECTED_MAC = sys.argv[1]

logfile = os.path.join(LOG_DIR, f"{EXPECTED_MAC}.log")

if os.path.exists(logfile):
    os.remove(logfile)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != f"/{EXPECTED_MAC}/log":
            self.send_response(404)
            self.end_headers()
            return

        length  = int(self.headers['Content-Length'])
        body    = self.rfile.read(length)
        data    = json.loads(body)

        print(time.strftime("%H:%M:%S"),data["log"])

        #logfile =os.path.join(LOG_DIR, f"{EXPECTED_MAC}.log")

        with open(logfile, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {data['log']}\n")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


HTTPServer(("0.0.0.0",8001), Handler).serve_forever()
