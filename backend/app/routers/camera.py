import asyncio
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response, StreamingResponse

from config import IMAGE_FILENAME
from app.services.camera_store import camera_frames

router = APIRouter(tags=["camera"])

NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Access-Control-Allow-Origin": "*",
}


def _read_disk_frame() -> bytes | None:
    path = Path(IMAGE_FILENAME)
    if not path.exists():
        return None
    try:
        return path.read_bytes()
    except Exception:
        return None


@router.get("/camera/latest")
def camera_latest():
    _, jpeg, _ = camera_frames.snapshot()
    if jpeg is None:
        jpeg = _read_disk_frame()
    if jpeg is None:
        return PlainTextResponse("No image captured yet.", status_code=404)
    return Response(jpeg, media_type="image/jpeg", headers=NO_CACHE_HEADERS)


@router.get("/camera/stream")
async def camera_stream():
    _, initial, _ = camera_frames.snapshot()
    if initial is None:
        initial = _read_disk_frame()
    if initial is None:
        return PlainTextResponse("No image captured yet.", status_code=404)

    async def generate():
        last_seq = -1
        last_jpeg = None
        while True:
            seq, jpeg, _ = camera_frames.snapshot()
            if jpeg is None:
                jpeg = initial
            if jpeg is not None and (seq != last_seq or last_jpeg is None):
                last_seq = seq
                last_jpeg = jpeg
                header = (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
                )
                yield header + jpeg + b"\r\n"
            await asyncio.sleep(0.01)

    headers = dict(NO_CACHE_HEADERS)
    headers["X-Accel-Buffering"] = "no"
    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers=headers,
    )
