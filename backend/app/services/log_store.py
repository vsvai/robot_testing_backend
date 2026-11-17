import os
import re
from datetime import datetime
from pathlib import Path

from config import LOG_DIR


MAC_FILE_PATTERN = re.compile(r"^[0-9A-F]{12}\.log$", re.IGNORECASE)

TAIL_MIN_BYTES = 64 * 1024


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


def _tail_bytes(logfile: Path, max_bytes: int) -> bytes:
    with open(logfile, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        start = max(0, size - max_bytes)
        f.seek(start)
        data = f.read()

    if start > 0:
        newline = data.find(b"\n")
        if newline < 0:
            return b""
        data = data[newline + 1:]
    return data


def read_log(mac: str, limit: int = 50) -> list[str]:
    logfile = _mac_filename(mac)
    if not logfile.exists():
        return []
    try:
        max_bytes = max(TAIL_MIN_BYTES, limit * 512)
        text = _tail_bytes(logfile, max_bytes).decode("utf-8", errors="ignore")
        lines = text.splitlines()
        if not lines:
            return ["Log file is empty.\n"]
        return [line + "\n" for line in reversed(lines[-limit:])]
    except Exception as e:
        return [f"Server Error: {e}\n"]
