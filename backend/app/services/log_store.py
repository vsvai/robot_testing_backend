import os
import re
from datetime import datetime
from pathlib import Path

from config import LOG_DIR


MAC_FILE_PATTERN = re.compile(r"^[0-9A-F]{12}\.log$", re.IGNORECASE)


def _ensure_log_dir():
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _mac_filename(mac: str) -> Path:
    return LOG_DIR / f"{mac.replace(':', '').upper()}.log"


def append_log(mac: str, message: str):
    _ensure_log_dir()
    logfile = _mac_filename(mac)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(logfile, "a") as f:
        f.write(f"[{timestamp}] {message}\n")


def list_macs() -> list[str]:
    _ensure_log_dir()
    files = [f.replace(".log", "") for f in os.listdir(LOG_DIR) if MAC_FILE_PATTERN.match(f)]
    return sorted(files)


def log_path(mac: str) -> Path:
    return _mac_filename(mac)


def read_log(mac: str, limit: int = 50) -> list[str]:
    logfile = _mac_filename(mac)
    if not logfile.exists():
        return [f"Error: Log file for {mac} not found.\n"]
    try:
        with open(logfile, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        if not lines:
            return ["Log file is empty.\n"]
        return [line for line in reversed(lines[-limit:])]
    except Exception as e:
        return [f"Server Error: {e}\n"]
