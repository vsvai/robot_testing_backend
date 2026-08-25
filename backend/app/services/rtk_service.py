import socket
import json
import threading
from datetime import datetime
from typing import Optional

from config import RTK_UDP_PORT, RTK_TCP_PORT, RTK_RECV_BUFFER, RTK_FIX_QUALITY
from app.models import RTKPosition


def get_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class RTKService:
    def __init__(self):
        self._udp_sock: Optional[socket.socket] = None
        self._tcp_sock: Optional[socket.socket] = None
        self._tcp_connected = False
        self._tcp_rover_ip: Optional[str] = None
        self._udp_active = False
        self._lock = threading.Lock()
        self._position: Optional[RTKPosition] = None
        self._position_count = 0
        self._udp_thread: Optional[threading.Thread] = None
        self._tcp_thread: Optional[threading.Thread] = None

    @property
    def udp_active(self) -> bool:
        return self._udp_active

    @property
    def tcp_connected(self) -> bool:
        return self._tcp_connected

    @property
    def tcp_rover_ip(self) -> Optional[str]:
        return self._tcp_rover_ip

    @property
    def position(self) -> Optional[RTKPosition]:
        with self._lock:
            return self._position

    @property
    def position_count(self) -> int:
        return self._position_count

    def _parse_position(self, data: str) -> Optional[RTKPosition]:
        try:
            msg = json.loads(data.strip())
            fix_value = msg.get("fix", 0)
            fix_quality = RTK_FIX_QUALITY.get(fix_value, f"UNKNOWN ({fix_value})")

            return RTKPosition(
                lat=msg.get("lat", 0.0),
                lon=msg.get("lon", 0.0),
                alt=msg.get("alt", 0.0),
                fix=fix_value,
                sat=msg.get("sat", 0),
                hdop=msg.get("hdop", 0.0),
                fix_quality=fix_quality,
                timestamp=datetime.now(),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"[{get_time()}] [RTK] Parse error: {e}")
            return None

    def _update_position(self, pos: RTKPosition):
        with self._lock:
            self._position = pos
            self._position_count += 1

    def _udp_listener(self):
        try:
            self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._udp_sock.bind(("0.0.0.0", RTK_UDP_PORT))
            self._udp_active = True
            print(f"[{get_time()}] [RTK] UDP listener active on port {RTK_UDP_PORT}")

            while self._udp_active:
                try:
                    data, addr = self._udp_sock.recvfrom(RTK_RECV_BUFFER)
                    msg = data.decode("utf-8").strip()
                    pos = self._parse_position(msg)
                    if pos:
                        self._update_position(pos)
                        print(f"[{get_time()}] [RTK UDP] Position from {addr[0]}: {pos.lat:.6f}, {pos.lon:.6f} ({pos.fix_quality})")
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[{get_time()}] [RTK UDP] Error: {e}")
        except Exception as e:
            print(f"[{get_time()}] [RTK UDP] Failed to start: {e}")
        finally:
            self._udp_active = False
            if self._udp_sock:
                self._udp_sock.close()

    def _tcp_receiver(self):
        try:
            while self._tcp_connected and self._tcp_sock:
                try:
                    data = self._tcp_sock.recv(RTK_RECV_BUFFER)
                    if not data:
                        print(f"[{get_time()}] [RTK TCP] Connection closed by rover")
                        break

                    msg = data.decode("utf-8").strip()
                    pos = self._parse_position(msg)
                    if pos:
                        self._update_position(pos)
                        print(f"[{get_time()}] [RTK TCP] Position: {pos.lat:.6f}, {pos.lon:.6f} ({pos.fix_quality})")
                except Exception as e:
                    print(f"[{get_time()}] [RTK TCP] Receive error: {e}")
                    break
        finally:
            self._tcp_connected = False
            if self._tcp_sock:
                self._tcp_sock.close()
                self._tcp_sock = None
            print(f"[{get_time()}] [RTK TCP] Disconnected")

    def start_udp_listener(self):
        if self._udp_thread and self._udp_thread.is_alive():
            print(f"[{get_time()}] [RTK] UDP listener already running")
            return

        self._udp_thread = threading.Thread(target=self._udp_listener, daemon=True)
        self._udp_thread.start()

    def stop_udp_listener(self):
        self._udp_active = False
        if self._udp_sock:
            self._udp_sock.close()
            self._udp_sock = None

    def connect_tcp(self, rover_ip: str) -> bool:
        if self._tcp_connected:
            print(f"[{get_time()}] [RTK TCP] Already connected to {self._tcp_rover_ip}")
            return True

        try:
            self._tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._tcp_sock.settimeout(5.0)
            self._tcp_sock.connect((rover_ip, RTK_TCP_PORT))
            self._tcp_connected = True
            self._tcp_rover_ip = rover_ip

            self._tcp_thread = threading.Thread(target=self._tcp_receiver, daemon=True)
            self._tcp_thread.start()

            print(f"[{get_time()}] [RTK TCP] Connected to {rover_ip}:{RTK_TCP_PORT}")
            return True
        except Exception as e:
            print(f"[{get_time()}] [RTK TCP] Connection failed: {e}")
            if self._tcp_sock:
                self._tcp_sock.close()
                self._tcp_sock = None
            return False

    def disconnect_tcp(self):
        if not self._tcp_connected:
            print(f"[{get_time()}] [RTK TCP] Not connected")
            return

        self._tcp_connected = False
        if self._tcp_sock:
            self._tcp_sock.close()
            self._tcp_sock = None
        print(f"[{get_time()}] [RTK TCP] Disconnected")


rtk_service = RTKService()
