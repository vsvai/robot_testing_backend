import os
import time

from fastapi import APIRouter
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse

from config import IMAGE_FILENAME

router = APIRouter(tags=["camera"])


@router.get("/camera/latest")
def camera_latest():
    if not os.path.exists(IMAGE_FILENAME):
        return PlainTextResponse("No image captured yet.", status_code=404)
    return FileResponse(
        IMAGE_FILENAME,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/camera/stream")
def camera_stream():
    if not os.path.exists(IMAGE_FILENAME):
        return PlainTextResponse("No image captured yet.", status_code=404)

    def generate():
        while True:
            if os.path.exists(IMAGE_FILENAME):
                try:
                    with open(IMAGE_FILENAME, "rb") as f:
                        img = f.read()
                    header = f"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: {len(img)}\r\n\r\n"
                    yield header.encode() + img + b"\r\n"
                except Exception:
                    pass
            time.sleep(0.05)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache",
            "Access-Control-Allow-Origin": "*",
        },
    )
