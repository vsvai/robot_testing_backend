import threading
from typing import Optional


class RobotDevice:
    def __init__(self, mac: str):
        self.mac = mac
        self.ip: Optional[str] = None
        self.udp_addr: Optional[tuple[str, int]] = None
        self.ota_pending = False
        self.last_seen: Optional[str] = None


class RobotStateRegistry:
    def __init__(self):
        self._devices: dict[str, RobotDevice] = {}
        self._lock = threading.Lock()

    def _key(self, mac: str) -> str:
        return mac.replace(":", "").lower()

    def get(self, mac: str) -> RobotDevice:
        key = self._key(mac)
        with self._lock:
            if key not in self._devices:
                self._devices[key] = RobotDevice(key)
            return self._devices[key]

    def all(self) -> list[RobotDevice]:
        with self._lock:
            return list(self._devices.values())

    def register_ip(self, mac: str, ip: str) -> RobotDevice:
        dev = self.get(mac)
        with self._lock:
            dev.ip = ip
        return dev

    def update_udp_addr(self, mac: str, addr: tuple[str, int]) -> RobotDevice:
        dev = self.get(mac)
        with self._lock:
            dev.udp_addr = addr
        return dev

    def set_ota_pending(self, mac: str, pending: bool) -> RobotDevice:
        dev = self.get(mac)
        with self._lock:
            dev.ota_pending = pending
        return dev

    def filter_by_group(self, group_id: str) -> list[str]:
        return [d.mac for d in self.all()]


robot_registry = RobotStateRegistry()
