from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.services.robot_state import robot_registry
from app.services.udp_client import send_udp_command

router = APIRouter(tags=["ota"])


@router.get("/ota/{mac}/set")
def ota_set(mac: str):
    robot_registry.set_ota_pending(mac, True)
    send_udp_command(mac, "OTA:update")
    return PlainTextResponse("ota set + UDP sent")


@router.get("/ota/{mac}/kill")
def ota_kill(mac: str):
    robot_registry.set_ota_pending(mac, False)
    send_udp_command(mac, "OTA:kill")
    return PlainTextResponse("ota killed + UDP sent")
