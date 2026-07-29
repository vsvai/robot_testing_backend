from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.models import RobotStatus, Telemetry
from app.services.robot_state import robot_registry
from app.services.udp_client import send_udp_command
from app.services.log_store import read_log
from app.services.telemetry import parse_telemetry_from_log

router = APIRouter(tags=["robot"])


@router.get("/start/{mac}/set/{direction}")
def start_move(mac: str, direction: str):
    send_udp_command(mac, f"START:{direction}")
    return PlainTextResponse("start set + UDP sent")


@router.get("/stop/{mac}/set")
def stop_move(mac: str):
    send_udp_command(mac, "STOP")
    return PlainTextResponse("stop set + UDP sent")


@router.get("/telemetry/{mac}")
def get_telemetry(mac: str) -> Telemetry:
    lines = read_log(mac, limit=100)
    return parse_telemetry_from_log(mac, lines)


@router.get("/status/{mac}")
def get_status(mac: str) -> RobotStatus:
    dev = robot_registry.get(mac)
    return RobotStatus(
        mac=dev.mac,
        udp_ready=dev.udp_addr is not None,
        ota_pending=dev.ota_pending,
    )


@router.get("/register")
def register(mac: str):
    dev = robot_registry.register_ip(mac, "unknown")
    return {"ack": True, "mac": dev.mac, "ip": dev.ip}
