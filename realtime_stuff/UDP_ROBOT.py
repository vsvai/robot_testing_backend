from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import json
import socket
import threading
import struct
import io
import os
import time
from datetime import datetime
from PIL import Image

# --- CONFIGURATION ---
PORT = 8100
ROBOT_UDP_PORT = 8888
CAMERA_UDP_PORT = 5005
IMAGE_FILENAME = "latest_image.jpg"

# --- SOCKET SETUP ---
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_sock.bind(("0.0.0.0", ROBOT_UDP_PORT))

cam_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
cam_sock.bind(("0.0.0.0", CAMERA_UDP_PORT))

# --- GLOBAL STATE ---
devices = {}
devices_lock = threading.Lock()

# --- HELPER FUNCTIONS ---
def get_time():
    """Helper to format timestamps consistently for logs."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def norm_mac(s):
    return s.replace(":", "").lower()

def get_device(mac):
    mac = norm_mac(mac)
    with devices_lock:
        if mac not in devices:
            devices[mac] = {
                "ip": None,
                "udp_addr": None,  # Stores return path from hole punch
                "ota_pending": False, "start_pending": False, "start_dir": None,
                "move_pending": False, "move_dir": None, "move_dur": None, "stop_pending": False
            }
        return devices[mac]

# --- BACKGROUND TASKS ---
def listen_udp():
    """Catches ESP32 UDP Pings and keeps the NAT hole open."""
    print(f"[{get_time()}] 📡 Robot UDP Listener active on Port {ROBOT_UDP_PORT}")
    while True:
        try:
            data, addr = udp_sock.recvfrom(1024)
            msg = data.decode('utf-8').strip()
            
            if msg.startswith("PING:"):
                mac = norm_mac(msg.split(":")[1])
                device = get_device(mac)
                
                if device["udp_addr"] != addr:
                    with devices_lock:
                        device["udp_addr"] = addr
                    print(f"[{get_time()}] [UDP] 🕳️ Firewall Tunnel mapped for {mac} at {addr[0]}:{addr[1]}")
        except Exception:
            pass

def listen_camera_udp():
    """Reassembles chunked images from ESP32-CAM and verifies headers."""
    print(f"[{get_time()}] 📷 Camera UDP Listener active on Port {CAMERA_UDP_PORT}")
    current_image_id = -1
    image_buffer = {}
    start_time = 0

    while True:
        try:
            data, addr = cam_sock.recvfrom(1030)
            if len(data) < 6:
                continue

            img_id, total_chunks, chunk_idx = struct.unpack(">HHH", data[:6])
            payload = data[6:]

            # Reset buffer if a new frame sequence begins
            if img_id != current_image_id:
                # If previous frame never finished, log dropped packets
                if current_image_id != -1:
                    received = sum(1 for k in image_buffer if len(image_buffer[k]) > 0)
                    print(f"[{get_time()}] [CAM-{CAMERA_UDP_PORT}] ⚠️ Frame {current_image_id} incomplete. Dropped {total_chunks - received} packets.")

                current_image_id = img_id
                image_buffer = {idx: b"" for idx in range(total_chunks)}
                start_time = time.time()
                
                print(f"[{get_time()}] [CAM-{CAMERA_UDP_PORT}] 📷 Incoming connection from {addr[0]}:{addr[1]}")
                print(f"[{get_time()}] [CAM-{CAMERA_UDP_PORT}] 📥 START_IMG_FRAME {img_id}: Expecting {total_chunks} chunks")

            # Append incoming chunk
            image_buffer[chunk_idx] = payload

            # Verify if every chunk for this frame has arrived
            if all(len(image_buffer[idx]) > 0 for idx in range(total_chunks)):
                full_image_data = b"".join(image_buffer[idx] for idx in range(total_chunks))
                file_size_kb = len(full_image_data) / 1024
                
                print(f"[{get_time()}] [CAM-{CAMERA_UDP_PORT}] 📦 Receiving chunks: [{total_chunks}/{total_chunks}] 100%")
                
                try:
                    # 1. Verify JPEG header strictly
                    image_stream = io.BytesIO(full_image_data)
                    img_verify = Image.open(image_stream)
                    img_verify.verify() 
                    print(f"[{get_time()}] [CAM-{CAMERA_UDP_PORT}] ✅ Image verified (Valid JPEG, {file_size_kb:.1f} KB)")
                    
                    # 2. Reset stream pointer and save atomically
                    image_stream.seek(0)
                    image_save = Image.open(image_stream)
                    
                    tmp_filename = f"{IMAGE_FILENAME}.tmp"
                    image_save.save(tmp_filename, "JPEG")
                    os.replace(tmp_filename, IMAGE_FILENAME)
                    
                    elapsed_time = time.time() - start_time
                    print(f"[{get_time()}] [SYS] 💾 Saved '{IMAGE_FILENAME}' in {elapsed_time:.2f}s\n")
                    
                except Exception as e:
                    print(f"[{get_time()}] [CAM-{CAMERA_UDP_PORT}] ❌ Corrupted Frame: {e}\n")
                    pass
                
                current_image_id = -1  # Reset for next frame
        except Exception:
            pass

def send_udp_command(mac, command_string):
    """Pushes control commands to the robot via UDP hole punch."""
    device = get_device(mac)
    addr = device["udp_addr"]
    
    if not addr:
        print(f"[{get_time()}] [UDP-ERROR] No tunnel mapped for {mac}. Wait for a ping.")
        return False
        
    try:
        udp_sock.sendto(command_string.encode('utf-8'), addr)
        print(f"[{get_time()}] [UDP-SEND] ⚡ Pushed '{command_string}' to {addr[0]}:{addr[1]}")
        return True
    except Exception as e:
        print(f"[{get_time()}] [UDP-ERROR] Failed to send: {e}")
        return False

# --- MULTI-THREADED TCP SERVER ---
class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass # Suppress default noisy HTTP logs
    
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
            self._send(200, "Sudoyantra OS Server Active\n")
            return

        action = parts[0]

        # --- LIVE MJPEG STREAM ---
        if action == "camera" and len(parts) > 1 and parts[1] == "stream":
            if not os.path.exists(IMAGE_FILENAME):
                self._send(404, "No image captured yet.\n")
                return
            
            print(f"[{get_time()}] [TCP] Live stream requested by {self.client_address[0]}")
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
                        except (ConnectionResetError, BrokenPipeError):
                            print(f"[{get_time()}] [TCP] Stream disconnected cleanly.")
                            return
                        except Exception:
                            pass
                    time.sleep(0.05) # ~20 FPS limit
            except Exception:
                return

        mac = norm_mac(parts[1]) if len(parts) > 1 else norm_mac(parts[0])
        device = get_device(mac)

        # --- ROUTING COMMANDS ---
        if action == "register":
            with devices_lock:
                device["ip"] = self.client_address[0]
            print(f"[{get_time()}] [TCP] Registered IP for {mac}: {self.client_address[0]}")
            self._send(200, "registered\n")
            return

        if action == "ota" or len(parts) == 1:
            if len(parts) == 3 and parts[2] == "set":
                with devices_lock:
                    device["ota_pending"] = True
                send_udp_command(mac, "OTA:update")
                self._send(200, "ota set + UDP sent\n")
                return
            if len(parts) == 3 and parts[2] == "kill":
                with devices_lock:
                    device["ota_pending"] = False
                send_udp_command(mac, "OTA:kill")
                self._send(200, "ota cleared + UDP sent\n")
                return
            if len(parts) <= 2:
                if device["ota_pending"]: self._send(200, "ota required\n")
                else: self._send(204, "")
                return

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
	# ==========================================
        # --- LATEST SINGLE IMAGE (API FOR WEBPAGE) ---
        # ==========================================
        if action == "camera" and len(parts) > 1 and parts[1] == "latest":
            if not os.path.exists(IMAGE_FILENAME):
                self._send(404, "No image captured yet.\n")
                return
            
            try:
                # Read the latest image file
                with open(IMAGE_FILENAME, "rb") as f:
                    img_bytes = f.read()
                
                # Send HTTP headers (including CORS and Cache-Busting)
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Access-Control-Allow-Origin", "*") # CORS so your webpage can fetch it
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.send_header("Content-Length", str(len(img_bytes)))
                self.end_headers()
                
                # Send the actual image bytes
                self.wfile.write(img_bytes)
            except Exception as e:
                print(f"[{get_time()}] [TCP] Error serving latest image: {e}")
                self._send(500, "Internal Server Error\n")
            return
        # ==========================================



        self._send(404, "not found\n")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # Start UDP listeners in background threads
    threading.Thread(target=listen_udp, daemon=True).start()
    threading.Thread(target=listen_camera_udp, daemon=True).start()

    # Start non-blocking HTTP server
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[{get_time()}] 🚀 Sudoyantra OS Server running on TCP {PORT} | Robot UDP {ROBOT_UDP_PORT} | Camera UDP {CAMERA_UDP_PORT}")
    try: 
        server.serve_forever()
    except KeyboardInterrupt: 
        print(f"\n[{get_time()}] Shutting down server...")
        server.server_close()


