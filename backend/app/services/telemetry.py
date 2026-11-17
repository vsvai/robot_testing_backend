import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models import Telemetry
from app.services.log_store import log_path

LINE_PATTERN = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*(.*)$")
STATE_PATTERN = re.compile(r"\bstate\s*[:=]\s*([A-Za-z_]+)", re.IGNORECASE)
BATTERY_PATTERN = re.compile(r"\bbattery(?:_v)?\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
BATTERY_FIELD_PATTERN = re.compile(r"\bB\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)")
VERSION_PATTERN = re.compile(r"\bver(?:sion)?\s*[:=]\s*(v?[0-9][\w.]*)", re.IGNORECASE)
RUN_START_PATTERN = re.compile(r"start command received", re.IGNORECASE)
RUN_STOP_PATTERN = re.compile(
    r"timed_move stop|robotstop_triggered|stop_maxrtime|maxruntime|duration_done|running_front_stop",
    re.IGNORECASE,
)
ERROR_PATTERN = re.compile(r"low_voltage|\berror\b|\bfault\b|ota failed", re.IGNORECASE)

READ_CHUNK = 1024 * 1024
MAX_READ_BYTES = 64 * 1024 * 1024


def _parse_ts(value: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


class _LogScanState:
    def __init__(self):
        self.lock = threading.Lock()
        self.offset = 0
        self.partial = b""
        self.total_runs = 0
        self.last_run_ts: Optional[datetime] = None
        self.state_tag: Optional[str] = None
        self.battery_v: Optional[float] = None
        self.version: Optional[str] = None
        self.error_seen = False
        self.inferred_state: Optional[str] = None

    def reset(self):
        self.offset = 0
        self.partial = b""
        self.total_runs = 0
        self.last_run_ts = None
        self.state_tag = None
        self.battery_v = None
        self.version = None
        self.error_seen = False
        self.inferred_state = None


_scan_states: dict[str, _LogScanState] = {}
_scan_states_lock = threading.Lock()


def _get_scan_state(key: str) -> _LogScanState:
    with _scan_states_lock:
        state = _scan_states.get(key)
        if state is None:
            state = _LogScanState()
            _scan_states[key] = state
        return state


def _consume_line(state: _LogScanState, raw: bytes):
    text = raw.decode("utf-8", errors="ignore").strip()
    if not text:
        return

    match = LINE_PATTERN.match(text)
    if match:
        ts_raw, msg = match.group(1), match.group(2)
    else:
        ts_raw, msg = None, text
    if not msg:
        return

    start_match = RUN_START_PATTERN.search(msg)
    if start_match:
        state.total_runs += 1
        if ts_raw:
            ts = _parse_ts(ts_raw)
            if ts is not None:
                state.last_run_ts = ts

    sm = STATE_PATTERN.search(msg)
    if sm:
        state.state_tag = sm.group(1).lower()

    bm = BATTERY_PATTERN.search(msg) or BATTERY_FIELD_PATTERN.search(msg)
    if bm:
        try:
            state.battery_v = float(bm.group(1))
        except ValueError:
            pass

    vm = VERSION_PATTERN.search(msg)
    if vm:
        state.version = vm.group(1)

    if ERROR_PATTERN.search(msg):
        state.error_seen = True

    if RUN_STOP_PATTERN.search(msg):
        state.inferred_state = "idle"
    elif start_match:
        state.inferred_state = "moving"


def _scan_new_bytes(state: _LogScanState, log_file: Path) -> bool:
    try:
        size = log_file.stat().st_size
    except OSError:
        return False

    if size < state.offset:
        state.reset()
    if size == state.offset:
        return True

    remaining = MAX_READ_BYTES
    with open(log_file, "rb") as f:
        f.seek(state.offset)
        while remaining > 0:
            chunk = f.read(min(READ_CHUNK, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            state.offset += len(chunk)
            data = state.partial + chunk
            lines = data.split(b"\n")
            state.partial = lines.pop()
            for raw in lines:
                _consume_line(state, raw)
    return True


def telemetry_from_log_file(mac: str, path: Optional[Path] = None) -> Telemetry:
    log_file = path if path is not None else log_path(mac)
    if not log_file.exists():
        return Telemetry(mac=mac, state="unknown")

    state = _get_scan_state(str(log_file.resolve()))
    with state.lock:
        _scan_new_bytes(state, log_file)

        if state.state_tag is not None:
            state_name = state.state_tag
        elif state.error_seen:
            state_name = "error"
        elif state.inferred_state is not None:
            state_name = state.inferred_state
        else:
            state_name = "idle"

        return Telemetry(
            mac=mac,
            state=state_name,
            battery_v=state.battery_v,
            version=state.version,
            total_runs=state.total_runs,
            last_run_cmd=None,
            last_run_ts=state.last_run_ts,
        )
