import json
import re

from fastapi import APIRouter, Query, Request
from fastapi.responses import PlainTextResponse

from app.models import MacFilterRequest, MacListResponse
from app.services.log_store import append_log, list_macs, read_log

router = APIRouter(tags=["logs"])

MAC_PATH_PATTERN = re.compile(r"^/([0-9A-F]{12})/log$", re.IGNORECASE)


@router.post("/macs")
def filter_macs(body: MacFilterRequest) -> MacListResponse:
    macs = list_macs()
    return MacListResponse(mac_ids=macs)


@router.get("/macs")
def get_macs() -> MacListResponse:
    return MacListResponse(mac_ids=list_macs())


@router.get("/view/{mac_id}")
def view_log(mac_id: str, limit: int = Query(50)):
    lines = read_log(mac_id, limit)
    return PlainTextResponse("".join(lines))


@router.api_route("/{path:path}", methods=["POST"])
async def receive_log(request: Request, path: str):
    match = MAC_PATH_PATTERN.match(f"/{path}")
    if not match:
        return PlainTextResponse("Not Found", status_code=404)
    mac_id = match.group(1).upper()
    try:
        body = await request.json()
        message = body.get("log", "")
    except Exception:
        return PlainTextResponse("Bad Request", status_code=400)
    append_log(mac_id, message)
    print(f"{mac_id} {message}")
    return PlainTextResponse("OK")
