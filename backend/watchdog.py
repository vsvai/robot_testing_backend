#!/usr/bin/env python3
"""Supervise the Sudoyantra backend and restart it when it dies or goes silent.

Run this instead of `python main.py`:

    python watchdog.py

Restart triggers:
  * the server process exits (crash / exception), or
  * the liveness heartbeat stops (process alive but event loop hung), or
  * no inbound robot update has been received for WATCHDOG_ACTIVITY_TIMEOUT
    seconds once at least one update has arrived.

Environment overrides:
  WATCHDOG_ACTIVITY_TIMEOUT   seconds without updates before restart (default 120)
  WATCHDOG_LIVENESS_TIMEOUT   seconds without liveness heartbeat (default 60)
  WATCHDOG_CHECK_INTERVAL     seconds between checks (default 5)
  WATCHDOG_KILL_GRACE         seconds to wait after SIGTERM (default 10)
  WATCHDOG_RESTART_DELAY      initial restart delay (default 2)
  WATCHDOG_MAX_RESTART_DELAY  max backoff delay (default 60)
  WATCHDOG_REQUIRE_ACTIVITY   set to 0 to ignore the no-update rule (default 1)
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from config import HEARTBEAT_FILE, LIVENESS_FILE

BASE_DIR = Path(__file__).resolve().parent
MAIN = BASE_DIR / "main.py"

ACTIVITY_TIMEOUT = float(os.environ.get("WATCHDOG_ACTIVITY_TIMEOUT", "120"))
LIVENESS_TIMEOUT = float(os.environ.get("WATCHDOG_LIVENESS_TIMEOUT", "60"))
CHECK_INTERVAL = float(os.environ.get("WATCHDOG_CHECK_INTERVAL", "5"))
KILL_GRACE = float(os.environ.get("WATCHDOG_KILL_GRACE", "10"))
RESTART_DELAY = float(os.environ.get("WATCHDOG_RESTART_DELAY", "2"))
MAX_RESTART_DELAY = float(os.environ.get("WATCHDOG_MAX_RESTART_DELAY", "60"))
REQUIRE_ACTIVITY = os.environ.get("WATCHDOG_REQUIRE_ACTIVITY", "1").lower() not in (
    "0",
    "false",
    "no",
    "off",
)

_stop = False
_current_proc = None


def log(msg: str):
    print(f"[watchdog {time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def _handle_signal(signum, frame):
    global _stop
    _stop = True
    log(f"received signal {signum}, shutting down")
    if _current_proc is not None and _current_proc.poll() is None:
        _signal_process(_current_proc, signal.SIGTERM)


def _signal_process(proc: subprocess.Popen, sig: int):
    try:
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(proc.pid), sig)
        elif sig == signal.SIGTERM:
            proc.terminate()
        else:
            proc.kill()
    except (ProcessLookupError, PermissionError):
        pass


def _remove(path: Path):
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except Exception as e:
        log(f"could not remove {path}: {e}")


def _age(path: Path):
    try:
        return time.time() - path.stat().st_mtime
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _sleep(seconds: float):
    end = time.time() + seconds
    while not _stop and time.time() < end:
        time.sleep(min(0.5, max(0.0, end - time.time())))


def spawn() -> subprocess.Popen:
    _remove(HEARTBEAT_FILE)
    _remove(LIVENESS_FILE)
    log(f"starting server: {sys.executable} {MAIN}")
    return subprocess.Popen(
        [sys.executable, str(MAIN)],
        cwd=str(BASE_DIR),
        start_new_session=True,
    )


def stop_process(proc: subprocess.Popen, reason: str):
    if proc.poll() is not None:
        return
    log(f"stopping server ({reason})")
    _signal_process(proc, signal.SIGTERM)
    try:
        proc.wait(timeout=KILL_GRACE)
        return
    except subprocess.TimeoutExpired:
        log("server ignored SIGTERM, force killing")
    _signal_process(proc, signal.SIGKILL)
    try:
        proc.wait(timeout=KILL_GRACE)
    except subprocess.TimeoutExpired:
        log("server still alive after SIGKILL")


def main() -> int:
    global _current_proc

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if not MAIN.exists():
        log(f"cannot find {MAIN}")
        return 1

    log(
        "watchdog started "
        f"(activity_timeout={ACTIVITY_TIMEOUT:.0f}s, "
        f"liveness_timeout={LIVENESS_TIMEOUT:.0f}s, "
        f"require_activity={REQUIRE_ACTIVITY})"
    )

    restart_delay = RESTART_DELAY
    while not _stop:
        proc = spawn()
        _current_proc = proc
        started = time.time()

        while not _stop:
            code = proc.poll()
            if code is not None:
                log(f"server exited with code {code}")
                break

            liveness = _age(LIVENESS_FILE)
            if time.time() - started > LIVENESS_TIMEOUT and (
                liveness is None or liveness > LIVENESS_TIMEOUT
            ):
                log(
                    "liveness heartbeat missing for "
                    f"{(liveness or 0):.0f}s (limit {LIVENESS_TIMEOUT:.0f}s), restarting"
                )
                stop_process(proc, "liveness heartbeat lost")
                break

            if REQUIRE_ACTIVITY:
                activity = _age(HEARTBEAT_FILE)
                if activity is not None and activity > ACTIVITY_TIMEOUT:
                    log(
                        f"no robot updates for {activity:.0f}s "
                        f"(limit {ACTIVITY_TIMEOUT:.0f}s), restarting"
                    )
                    stop_process(proc, "no robot updates")
                    break

            _sleep(CHECK_INTERVAL)

        if _stop:
            stop_process(proc, "watchdog shutdown")
            break

        _current_proc = None
        uptime = time.time() - started
        if uptime > 60:
            restart_delay = RESTART_DELAY
        else:
            restart_delay = min(MAX_RESTART_DELAY, restart_delay * 2)

        log(f"restarting server in {restart_delay:.0f}s")
        _sleep(restart_delay)

    if _current_proc is not None:
        stop_process(_current_proc, "watchdog shutdown")
        _current_proc = None
    log("watchdog stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
