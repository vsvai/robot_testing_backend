from typing import List

from fastapi import APIRouter, HTTPException

from app.models import LowLimitSetting, TelemetryRecord, TelemetryUpdate
from app.services.telemetry_store import compute_status_lamp, telemetry_store
from app.services.telemetry import telemetry_from_log_file

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
    legacy = telemetry_from_log_file(mac)
    return TelemetryRecord(
        mac=legacy.mac,
        state=legacy.state,
        battery_v=legacy.battery_v,
        total_runs=legacy.total_runs,
        last_run_ts=legacy.last_run_ts,
        status_lamp=compute_status_lamp(legacy.state, legacy.battery_v, telemetry_store.get_low_limit()),
    )


@router.get("")
def get_all_telemetry() -> List[TelemetryRecord]:
    return [TelemetryRecord(**r) for r in telemetry_store.all()]
