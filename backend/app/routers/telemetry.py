from typing import List

from fastapi import APIRouter, HTTPException

from app.models import LowLimitSetting, TelemetryRecord, TelemetryUpdate
from app.services.telemetry_store import compute_status_lamp, telemetry_store
from app.services.log_store import read_log
from app.services.telemetry import parse_telemetry_from_log

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get("/settings")
def get_settings() -> LowLimitSetting:
    return LowLimitSetting(low_limit=telemetry_store.get_low_limit())


@router.put("/settings")
def set_settings(payload: LowLimitSetting) -> LowLimitSetting:
    telemetry_store.set_low_limit(payload.low_limit)
    return payload


@router.post("/{mac}")
def push_telemetry(mac: str, payload: TelemetryUpdate) -> TelemetryRecord:
    return TelemetryRecord(**telemetry_store.update(mac, payload))


@router.get("/{mac}")
def get_robot_telemetry(mac: str) -> TelemetryRecord:
    rec = telemetry_store.get(mac)
    if rec is not None:
        return TelemetryRecord(**rec)
    legacy = parse_telemetry_from_log(mac, read_log(mac, limit=100))
    return TelemetryRecord(
        mac=legacy.mac,
        state=legacy.state,
        battery_v=legacy.battery_v,
        total_runs=legacy.total_runs or 0,
        status_lamp=compute_status_lamp(legacy.state, legacy.battery_v, telemetry_store.get_low_limit()),
    )


@router.get("")
def get_all_telemetry() -> List[TelemetryRecord]:
    return [TelemetryRecord(**r) for r in telemetry_store.all()]
