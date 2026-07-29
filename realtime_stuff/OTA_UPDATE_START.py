import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# Configuration
HTTP_PORT = 8008
UDP_PORT = 4211
fleet_registry = {} # Stores MAC -> (IP, Port)

# --- UDP Listener Thread ---
def udp_heartbeat_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', UDP_PORT))
    print(f"UDP Listener active on port {UDP_PORT}")
    
    while True:
        data, addr = sock.recvfrom(1024)
        mac = data.decode().strip().lower()
        fleet_registry[mac] = addr # Save IP and Port for this robot
        print(f"Robot {mac} checked in from {addr}")

threading.Thread(target=udp_heartbeat_listener, daemon=True).start()

# --- HTTP Handler ---
class RobotAPI(BaseHTTPRequestHandler):
    def do_GET(self):
        # Route: /move/<mac>/<cmd>
        parts = [p for p in self.path.split("/") if p]
        if len(parts) >= 3 and parts[0] == "move":
            mac = parts[1].lower()
            cmd = parts[2].upper()
            
            if mac in fleet_registry:
                target_addr = fleet_registry[mac]
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(cmd.encode(), target_addr)
                self.send_response(200); self.end_headers()
                self.wfile.write(f"UDP Sent: {cmd} to {mac}".encode())
            else:
                self.send_response(404); self.end_headers()
                self.wfile.write(b"Robot offline")
            return

HTTPServer(('', HTTP_PORT), RobotAPI).serve_forever()
