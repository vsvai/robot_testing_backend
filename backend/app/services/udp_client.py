import socket
import threading
from datetime import datetime

from config import ROBOT_UDP_PORT
from app.services.robot_state import robot_registry


def get_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def norm_mac(s: str) -> str:
    return s.replace(":", "").lower()


udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_sock.bind(("0.0.0.0", ROBOT_UDP_PORT))


def listen_udp():
    print(f"[{get_time()}] Robot UDP listener active on port {ROBOT_UDP_PORT}")
    while True:
        try:
            data, addr = udp_sock.recvfrom(1024)
            msg = data.decode("utf-8").strip()
            if msg.startswith("PING:"):
                mac = norm_mac(msg.split(":")[1])
                robot_registry.update_udp_addr(mac, addr)
                print(f"[{get_time()}] [UDP] Hole punch mapped {mac} at {addr[0]}:{addr[1]}")
        except Exception:
            pass


def send_udp_command(mac: str, command: str) -> bool:
    dev = robot_registry.get(mac)
    addr = dev.udp_addr
    if not addr:
        print(f"[{get_time()}] [UDP] No tunnel for {mac}")
        return False
    try:
        udp_sock.sendto(command.encode("utf-8"), addr)
        print(f"[{get_time()}] [UDP] Sent '{command}' to {addr[0]}:{addr[1]}")
        return True
    except Exception as e:
        print(f"[{get_time()}] [UDP] Send error: {e}")
        return False


def start_udp_listener():
    thread = threading.Thread(target=listen_udp, daemon=True)
    thread.start()
