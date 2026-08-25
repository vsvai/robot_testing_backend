from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.models import RTKPosition, RTKStatus
from app.services.rtk_service import rtk_service


router = APIRouter(tags=["rtk"])


class ConnectRequest(BaseModel):
    rover_ip: str


@router.get("/rtk/position")
def get_position():
    pos = rtk_service.position
    if pos is None:
        return PlainTextResponse("No position data available", status_code=404)
    return pos.model_dump()


@router.get("/rtk/status")
def get_status() -> RTKStatus:
    return RTKStatus(
        udp_active=rtk_service.udp_active,
        tcp_connected=rtk_service.tcp_connected,
        tcp_rover_ip=rtk_service.tcp_rover_ip,
        last_update=rtk_service.position.timestamp if rtk_service.position else None,
        position_count=rtk_service.position_count,
    )


@router.post("/rtk/connect")
def connect_tcp(req: ConnectRequest) -> PlainTextResponse:
    success = rtk_service.connect_tcp(req.rover_ip)
    if success:
        return PlainTextResponse(f"Connected to rover at {req.rover_ip}")
    return PlainTextResponse(f"Failed to connect to {req.rover_ip}", status_code=500)


@router.post("/rtk/disconnect")
def disconnect_tcp() -> PlainTextResponse:
    rtk_service.disconnect_tcp()
    return PlainTextResponse("Disconnected from rover")


@router.get("/rtk/network")
def get_network_info() -> dict:
    return {
        "base_ap_ssid": "X20P_RTK_BASE",
        "base_ap_password": "12345678",
        "base_ip": "192.168.4.1",
        "tcp_port": 4230,
        "udp_port": 4220,
    }
