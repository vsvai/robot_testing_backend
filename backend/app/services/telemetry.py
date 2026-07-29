import re
from typing import Optional

from app.models import Telemetry

VOLTAGE_PATTERN = re.compile(r"(?:bat|voltage|battery)[:\s]*([\d.]+)", re.IGNORECASE)
VERSION_PATTERN = re.compile(r"(?:ver|version|fw)[:\s]*(v?\d[\w.]*)", re.IGNORECASE)
RUN_CMD_PATTERN = re.compile(r"(?:cmd|command|run)[:\s]*(\S+)", re.IGNORECASE)
STATE_PATTERN = re.compile(r"(?:state|mode)[:\s]*(\w+)", re.IGNORECASE)


def parse_telemetry_from_log(mac: str, log_lines: list[str]) -> Telemetry:
    battery_v: Optional[float] = None
    version: Optional[str] = None
    total_runs: Optional[int] = None
    last_run_cmd: Optional[str] = None
    state = "unknown"

    for line in log_lines:
        if m := VOLTAGE_PATTERN.search(line):
            try:
                battery_v = float(m.group(1))
            except ValueError:
                pass
        if m := VERSION_PATTERN.search(line):
            version = m.group(1)
        if m := STATE_PATTERN.search(line):
            state = m.group(1).lower()
        if m := RUN_CMD_PATTERN.search(line):
            last_run_cmd = m.group(1)
            total_runs = (total_runs or 0) + 1

    return Telemetry(
        mac=mac,
        state=state,
        battery_v=battery_v,
        version=version,
        total_runs=total_runs,
        last_run_cmd=last_run_cmd,
    )
