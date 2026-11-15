import threading
import time
from pathlib import Path

from config import HEARTBEAT_FILE, LIVENESS_FILE

_last_write = 0.0
_MIN_INTERVAL = 1.0


def _write(path: Path):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(time.time()))
    except Exception as e:
        print(f"[heartbeat] write failed: {e}")


def touch_heartbeat(force: bool = False):
    global _last_write
    now = time.monotonic()
    if not force and now - _last_write < _MIN_INTERVAL:
        return
    _last_write = now
    _write(Path(HEARTBEAT_FILE))


def _liveness_loop(interval: float):
    while True:
        _write(Path(LIVENESS_FILE))
        time.sleep(interval)


def start_liveness_heartbeat(interval: float = 10.0):
    thread = threading.Thread(
        target=_liveness_loop, args=(interval,), name="liveness-heartbeat", daemon=True
    )
    thread.start()
