from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from typing import Optional


class MacFilterRequest(BaseModel):
    id: str


class MacListResponse(BaseModel):
    mac_ids: list[str]


class RegisterRequest(BaseModel):
    mac: str


class RegisterResponse(BaseModel):
    ack: bool
    mac: str
    ip: str


class RobotStatus(BaseModel):
    mac: str
    udp_ready: bool
    ota_pending: bool


class Telemetry(BaseModel):
    mac: str
    state: str
    battery_v: Optional[float] = None
    version: Optional[str] = None
    total_runs: Optional[int] = None
    last_run_cmd: Optional[str] = None


class LogEntry(BaseModel):
    log: str


class StatusLamp(str, Enum):
    FAULT = "FAULT"
    LOW_BATTERY = "LOW_BATTERY"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    UNKNOWN = "UNKNOWN"


class TelemetryUpdate(BaseModel):
    state: str
    battery_v: Optional[float] = None
    total_runs: int = 0
    last_run_ts: Optional[datetime] = None
    total_distance_m: Optional[float] = None


class TelemetryRecord(BaseModel):
    mac: str
    state: str
    battery_v: Optional[float] = None
    total_runs: int = 0
    last_run_ts: Optional[datetime] = None
    total_distance_m: Optional[float] = None
    status_lamp: StatusLamp = StatusLamp.UNKNOWN
    updated_at: Optional[datetime] = None


class LowLimitSetting(BaseModel):
    low_limit: float
