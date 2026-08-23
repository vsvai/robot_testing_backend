import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models import Telemetry
from app.services.log_store import log_path

LINE_PATTERN = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*(.*)$")
STATE_PATTERN = re.compile(r"\bstate\s*[:=]\s*([A-Za-z_]+)", re.IGNORECASE)
BATTERY_PATTERN = re.compile(r"\bbattery(?:_v)?\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
VERSION_PATTERN = re.compile(r"\bver(?:sion)?\s*[:=]\s*(v?[0-9][\w.]*)", re.IGNORECASE)
RUN_START_PATTERN = re.compile(r"start command received", re.IGNORECASE)
RUN_STOP_PATTERN = re.compile(
    r"timed_move stop|robotstop_triggered|stop_maxrtime|maxruntime|duration_done|running_front_stop",
    re.IGNORECASE,
)
ERROR_PATTERN = re.compile(r"low_voltage|\berror\b|\bfault\b|ota failed", re.IGNORECASE)


def _parse_ts(value: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def telemetry_from_log_file(mac: str, path: Optional[Path] = None) -> Telemetry:
    state_tag: Optional[str] = None
    battery_v: Optional[float] = None
    version: Optional[str] = None
    total_runs = 0
    last_run_ts: Optional[datetime] = None
    error_seen: Optional[bool] = None
    inferred_state: Optional[str] = None

    log_file = path if path is not None else log_path(mac)
    if not log_file.exists():
        return Telemetry(mac=mac, state="unknown")

    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for raw in reversed(lines):
        m = LINE_PATTERN.match(raw.strip())
        ts = _parse_ts(m.group(1)) if m else None
        msg = m.group(2) if m else raw.strip()
        if not msg:
            continue

        if RUN_START_PATTERN.search(msg):
            total_runs += 1
            if last_run_ts is None and ts is not None:
                last_run_ts = ts

        sm = STATE_PATTERN.search(msg)
        if sm and state_tag is None:
            state_tag = sm.group(1).lower()

        bm = BATTERY_PATTERN.search(msg)
        if bm and battery_v is None:
            try:
                battery_v = float(bm.group(1))
            except ValueError:
                pass

        vm = VERSION_PATTERN.search(msg)
        if vm and version is None:
            version = vm.group(1)

        if ERROR_PATTERN.search(msg) and error_seen is None:
            error_seen = True

        if inferred_state is None:
            if RUN_STOP_PATTERN.search(msg):
                inferred_state = "idle"
            elif RUN_START_PATTERN.search(msg):
                inferred_state = "moving"

    if state_tag is not None:
        state = state_tag
    elif error_seen:
        state = "error"
    elif inferred_state is not None:
        state = inferred_state
    else:
        state = "idle"

    return Telemetry(
        mac=mac,
        state=state,
        battery_v=battery_v,
        version=version,
        total_runs=total_runs,
        last_run_cmd=None,
        last_run_ts=last_run_ts,
    )
