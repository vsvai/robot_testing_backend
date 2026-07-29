from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import json
import socket
import threading
import struct
import io
import os
from PIL import Image

PORT = 8100
ROBOT_UDP_PORT = 8888
CAMERA_UDP_PORT = 5005
IMAGE_FILENAME = "latest_image.jpg"

# 1. Bind UDP Socket for Robot Control
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_sock.bind(("0.0.0.0", ROBOT_UDP_PORT))

# 2. Bind UDP Socket for ESP32-CAM Chunks
cam_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
cam_sock.bind(("0.0.0.0", CAMERA_UDP_PORT))

devices = {}

def norm_mac(s):
    return s.replace(":", "").lower()

def get_device(mac):
    mac = norm_mac(mac)
    if mac not in devices:
        devices[mac] = {
            "ip": None,
            "udp_addr": None,  # Stores return path from hole punch
            "ota_pending": False, "start_pending": False, "start_dir": None,
            "move_pending": False, "move_dir": None, "move_dur": None, "stop_pending": False
        }
    return devices[mac]

# Background task to catch the ESP32 UDP Pings
def listen_udp():
    print(f"📡 Robot UDP Listener active on Port {ROBOT_UDP_PORT}")
    while True:
        try:
            data, addr = udp_sock.recvfrom(1024)
            msg = data.decode('utf-8').strip()
            
            if msg.startswith("PING:"):
                mac = norm_mac(msg.split(":")[1])
                device = get_device(mac)
                
                if device["udp_addr"] != addr:
                    device["udp_addr"] = addr
                    print(f"[UDP] 🕳️ Firewall Tunnel mapped for {mac} at {addr[0]}:{addr[1]}")
        except Exception:
            pass

# Background task to reassemble chunked images from ESP32-CAM
def listen_camera_udp():
    print(f"📷 Camera UDP Listener active on Port {CAMERA_UDP_PORT}")
    current_image_id = -1
    image_buffer = {}

    while True:
        try:
            data, addr = cam_sock.recvfrom(1030)
            if len(data) < 6:
                continue

            img_id, total_chunks, chunk_idx = struct.unpack(">HHH", data[:6])
            payload = data[6:]

            # Reset buffer if a new frame sequence begins
            if img_id != current_image_id:
                current_image_id = img_id
                image_buffer = {idx: b"" for idx in range(total_chunks)}

            # Append the incoming chunk
            image_buffer[chunk_idx] = payload

            # Verify if every single chunk for this frame has arrived
            if all(len(image_buffer[idx]) > 0 for idx in range(total_chunks)):
                full_image_data = b"".join(image_buffer[idx] for idx in range(total_chunks))
                
                try:
                    image = Image.open(io.BytesIO(full_image_data))
                    # Atomic save operation
                    tmp_filename = f"{IMAGE_FILENAME}.tmp"
                    image.save(tmp_filename, "JPEG")
                    os.replace(tmp_filename, IMAGE_FILENAME)
                except Exception:
                    # Packet drop/corruption over link safely handled without crashing
                    pass
                
                current_image_id = -1  # Reset ready for next frame
        except Exception:
            pass

# Start both background UDP listener loops
threading.Thread(target=listen_udp, daemon=True).start()
threading.Thread(target=listen_camera_udp, daemon=True).start()

# Core UDP Dispatcher (Pushes control commands to the robot endpoint)
def send_udp_command(mac, command_string):
    device = get_device(mac)
    addr = device["udp_addr"]
    
    if not addr:
        print(f"[UDP-ERROR] No tunnel mapped for {mac} yet. Wait for a ping.")
        return False
        
    try:
        udp_sock.sendto(command_string.encode('utf-8'), addr)
        print(f"[UDP-SEND] ⚡ Pushed '{command_string}' to {addr[0]}:{addr[1]}")
        return True
    except Exception as e:
        print(f"[UDP-ERROR] Failed to send: {e}")
        return False

# Unified TCP Server for cURL controls and Live Video streaming
class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass
    
    def _send(self, code, body="", content_type="text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if isinstance(body, str): body = body.encode()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        parts = [p for p in path.split("/") if p]
        
        if len(parts) == 0:
            self._send(200, "ok\n")
            return

        action = parts[0]

        # --- LIVE BROWSER LIVESTREAM ENDPOINT ---
        if action == "camera" and len(parts) > 1 and parts[1] == "stream":
            if not os.path.exists(IMAGE_FILENAME):
                self._send(404, "No image captured yet.\n")
                return
            
            # Send standard MJPEG stream headers for an endless browser visual feed
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            
            try:
                while True:
                    if os.path.exists(IMAGE_FILENAME):
                        try:
                            with open(IMAGE_FILENAME, "rb") as f:
                                img_bytes = f.read()
                            
                            self.wfile.write(b"--frame\r\n")
                            self.wfile.write(b"Content-Type: image/jpeg\r\n")
                            self.wfile.write(f"Content-Length: {len(img_bytes)}\r\n\r\n".encode())
                            self.wfile.write(img_bytes)
                            self.wfile.write(b"\r\n")
                        except Exception:
                            pass
                    threading.sleep(0.05) # ~20 FPS limit to save network cycles
            except Exception:
                # Browser closed connection cleanly
                return

        mac = norm_mac(parts[1]) if len(parts) > 1 else norm_mac(parts[0])
        device = get_device(mac)

        if action == "register":
            device["ip"] = self.client_address[0]
            print(f"[TCP] Registered IP for {mac}: {self.client_address[0]}")
            self._send(200, "registered\n")
            return

        # --- OTA COMMANDS DIRECTED VIA UDP ---
        if action == "ota" or len(parts) == 1:
            if len(parts) == 3 and parts[2] == "set":
                device["ota_pending"] = True
                send_udp_command(mac, "OTA:update")
                self._send(200, "ota set + UDP sent\n")
                return
            if len(parts) == 3 and parts[2] == "kill":
                device["ota_pending"] = False
                send_udp_command(mac, "OTA:kill")
                self._send(200, "ota cleared + UDP sent\n")
                return
            if len(parts) <= 2:
                if device["ota_pending"]: self._send(200, "ota required\n")
                else: self._send(204, "")
                return

        # --- MOTOR COMMANDS DIRECTED VIA UDP ---
        if action == "start":
            if len(parts) >= 3 and parts[2] == "set":
                direction = parts[3] if len(parts) == 4 else "none"
                send_udp_command(mac, f"START:{direction}")
                self._send(200, f"start set + UDP sent\n")
                return

        if action == "move":
            if len(parts) == 4:
                send_udp_command(mac, f"MOVE:{parts[2]}:{parts[3]}")
                self._send(200, f"move set + UDP sent\n")
                return

        if action == "stop":
            if len(parts) == 3 and parts[2] == "set":
                send_udp_command(mac, "STOP")
                self._send(200, "stop set + UDP sent\n")
                return

        if action == "status" and len(parts) == 2:
            payload = {
                "mac": mac,
                "udp_ready": bool(device["udp_addr"]),
                "ota_pending": device["ota_pending"]
            }
            self._send(200, json.dumps(payload), "application/json")
            return

        self._send(404, "not found\n")

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"🚀 Server running on TCP {PORT} | Robot UDP {ROBOT_UDP_PORT} | Camera UDP {CAMERA_UDP_PORT}")
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()
