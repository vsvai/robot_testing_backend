import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import DEFAULT_LOW_LIMIT_V, TELEMETRY_STORE_FILE
from app.models import StatusLamp, TelemetryUpdate


def norm_mac(s: str) -> str:
    return s.replace(":", "").replace("-", "").strip().lower()


def compute_status_lamp(state: str, battery_v: Optional[float], low_limit: float) -> StatusLamp:
    s = (state or "").lower()
    if s == "error":
        return StatusLamp.FAULT
    if battery_v is not None and battery_v < low_limit:
        return StatusLamp.LOW_BATTERY
    if s == "moving":
        return StatusLamp.RUNNING
    if s == "idle":
        return StatusLamp.STOPPED
    return StatusLamp.UNKNOWN


class TelemetryStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._robots: dict[str, dict] = {}
        self._low_limit: float = DEFAULT_LOW_LIMIT_V
        self._load()

    def _load(self):
        path = Path(TELEMETRY_STORE_FILE)
        try:
            if path.exists():
                raw = json.loads(path.read_text())
                self._low_limit = float(raw.get("low_limit", DEFAULT_LOW_LIMIT_V))
                self._robots = raw.get("robots", {})
        except Exception as e:
            print(f"[telemetry] store load failed: {e}")

    def _save_locked(self):
        try:
            Path(TELEMETRY_STORE_FILE).write_text(
                json.dumps({"low_limit": self._low_limit, "robots": self._robots}, indent=2)
            )
        except Exception as e:
            print(f"[telemetry] store save failed: {e}")

    @staticmethod
    def _decorate(rec: dict, low_limit: float) -> dict:
        out = dict(rec)
        out["status_lamp"] = compute_status_lamp(out.get("state", ""), out.get("battery_v"), low_limit)
        return out

    def update(self, mac: str, payload: TelemetryUpdate) -> dict:
        key = norm_mac(mac)
        now_iso = datetime.now().isoformat()
        with self._lock:
            prev = self._robots.get(key, {})
            last_run_ts = payload.last_run_ts.isoformat() if payload.last_run_ts else None
            prev_runs = prev.get("total_runs") or 0
            if last_run_ts is None and payload.total_runs > prev_runs:
                last_run_ts = now_iso
            elif last_run_ts is None:
                last_run_ts = prev.get("last_run_ts")
            rec = {
                "mac": mac,
                "state": payload.state.lower(),
                "battery_v": payload.battery_v,
                "total_runs": payload.total_runs,
                "last_run_ts": last_run_ts,
                "total_distance_m": payload.total_distance_m,
                "updated_at": now_iso,
            }
            self._robots[key] = rec
            self._save_locked()
            return self._decorate(rec, self._low_limit)

    def get(self, mac: str) -> Optional[dict]:
        key = norm_mac(mac)
        with self._lock:
            rec = self._robots.get(key)
            if rec is None:
                return None
            return self._decorate(rec, self._low_limit)

    def all(self) -> list[dict]:
        with self._lock:
            return [self._decorate(rec, self._low_limit) for rec in self._robots.values()]

    def set_low_limit(self, value: float):
        with self._lock:
            self._low_limit = value
            self._save_locked()

    def get_low_limit(self) -> float:
        with self._lock:
            return self._low_limit


telemetry_store = TelemetryStore()
