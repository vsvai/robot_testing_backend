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
