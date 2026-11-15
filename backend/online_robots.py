#!/usr/bin/env python3
"""List robots that were online in the last N minutes, with their voltages.

Run on the backend server from the `backend/` directory:

    venv/bin/python online_robots.py
    venv/bin/python online_robots.py --minutes 10
    venv/bin/python online_robots.py --hours 24
    venv/bin/python online_robots.py --watch --interval 30

"Online" means telemetry was pushed or a log line was received within the
window. Voltage comes from the telemetry store when available, otherwise the
latest `battery:` / `ADS value:` line in the robot log is used.
"""

import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from config import LOG_DIR, TELEMETRY_STORE_FILE

BATTERY_PATTERN = re.compile(
    r"\bbattery(?:_v)?\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE
)
BATTERY_FIELD_PATTERN = re.compile(r"\bB\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)")
ADS_PATTERN = re.compile(r"\bADS value\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
VOLTAGE_PATTERN = re.compile(r"\bvoltage\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
STATE_PATTERN = re.compile(r"\bstate\s*[:=]\s*([A-Za-z_]+)", re.IGNORECASE)
MAC_FILE_PATTERN = re.compile(r"^([0-9A-F]{12})\.log$", re.IGNORECASE)


def norm_mac(mac: str) -> str:
    return mac.replace(":", "").replace("-", "").strip().upper()


def load_store() -> dict[str, dict]:
    path = Path(TELEMETRY_STORE_FILE)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
    except Exception:
        return {}
    return raw.get("robots", {}) or {}


def tail_text(path: Path, max_bytes: int = 65536) -> str:
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - max_bytes))
            return f.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _positive(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if number > 0 else None


def parse_from_log(path: Path) -> tuple[float | None, str | None]:
    lines = tail_text(path).splitlines()
    battery = voltage = state = None
    latest_ads = None
    for raw in reversed(lines):
        line = raw.strip()
        if not line:
            continue
        if battery is None:
            m = BATTERY_PATTERN.search(line) or BATTERY_FIELD_PATTERN.search(line)
            if m:
                battery = _positive(m.group(1))
        if voltage is None:
            m = VOLTAGE_PATTERN.search(line)
            if m:
                voltage = _positive(m.group(1))
        if latest_ads is None:
            m = ADS_PATTERN.search(line)
            if m:
                latest_ads = _positive(m.group(1))
        if state is None:
            m = STATE_PATTERN.search(line)
            if m:
                state = m.group(1).lower()
        if battery is not None and voltage is not None and latest_ads is not None and state is not None:
            break

    return battery or voltage or latest_ads, state


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def collect(minutes: float) -> list[dict]:
    now = datetime.now()
    cutoff = now.timestamp() - minutes * 60
    records: dict[str, dict] = {}

    for mac, rec in load_store().items():
        updated = _parse_iso(rec.get("updated_at"))
        if updated is None or updated.timestamp() < cutoff:
            continue
        records[norm_mac(mac)] = {
            "mac": norm_mac(mac),
            "last_seen": updated,
            "battery": rec.get("battery_v"),
            "state": rec.get("state"),
            "source": "telemetry",
        }

    if not LOG_DIR.exists():
        return sorted(records.values(), key=lambda r: r["last_seen"], reverse=True)

    for entry in LOG_DIR.iterdir():
        match = MAC_FILE_PATTERN.match(entry.name)
        if not match:
            continue
        try:
            mtime = entry.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            continue

        mac = norm_mac(match.group(1))
        seen = datetime.fromtimestamp(mtime)
        battery, state = parse_from_log(entry)
        existing = records.get(mac)
        if existing is not None:
            existing["last_seen"] = max(existing["last_seen"], seen)
            if existing.get("battery") is None and battery is not None:
                existing["battery"] = battery
            if not existing.get("state") and state:
                existing["state"] = state
        else:
            records[mac] = {
                "mac": mac,
                "last_seen": seen,
                "battery": battery,
                "state": state,
                "source": "log",
            }

    return sorted(records.values(), key=lambda r: r["last_seen"], reverse=True)


def format_age(seen: datetime) -> str:
    seconds = max(0, int((datetime.now() - seen).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def format_window(minutes: float) -> str:
    if minutes >= 1440 and minutes % 1440 == 0:
        days = minutes / 1440
        return f"{days:g} day" + ("" if days == 1 else "s")
    if minutes >= 60 and minutes % 60 == 0:
        return f"{minutes / 60:g} h"
    return f"{minutes:g} min"


def render(rows: list[dict], minutes: float) -> str:
    out = [
        f"Online robots in last {format_window(minutes)} "
        f"(server time {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
        "",
    ]
    if not rows:
        out.append("No robots seen in this window.")
        return "\n".join(out)

    out.append(f"{'MAC':<14} {'LAST SEEN':<20} {'AGE':<9} {'BATTERY':<10} {'STATE':<10} SOURCE")
    out.append("-" * 78)
    for row in rows:
        battery = f"{row['battery']:.2f} V" if row.get("battery") is not None else "N/A"
        state = row.get("state") or "-"
        out.append(
            f"{row['mac']:<14} "
            f"{row['last_seen'].strftime('%Y-%m-%d %H:%M:%S'):<20} "
            f"{format_age(row['last_seen']):<9} "
            f"{battery:<10} "
            f"{state[:10]:<10} "
            f"{row.get('source', '-')}"
        )
    out.append("")
    out.append(f"Total: {len(rows)} robot(s)")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="List recently online robots")
    parser.add_argument("--minutes", type=float, default=None, help="time window in minutes (default 10)")
    parser.add_argument("--hours", type=float, default=None, help="time window in hours, e.g. 24 for 1 day")
    parser.add_argument("--watch", action="store_true", help="refresh continuously")
    parser.add_argument("--interval", type=float, default=30, help="refresh seconds (default 30)")
    parser.add_argument("--log-file", help="also append each snapshot to this file")
    args = parser.parse_args()

    if args.hours is not None:
        window = args.hours * 60
    elif args.minutes is not None:
        window = args.minutes
    else:
        window = 10

    try:
        while True:
            text = render(collect(window), window)
            if args.watch:
                print("\033[2J\033[H", end="")
            print(text, flush=True)
            if args.log_file:
                try:
                    with open(args.log_file, "a") as f:
                        f.write(text + "\n\n")
                except Exception as e:
                    print(f"[online_robots] log write failed: {e}")
            if not args.watch:
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
