import io
import os
import socket
import struct
import threading
import time
from datetime import datetime

from PIL import Image

from config import CAMERA_UDP_PORT, IMAGE_FILENAME, CAMERA_RECV_BUFFER
from app.services.heartbeat import touch_heartbeat
from app.services.camera_store import camera_frames


def get_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


cam_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
cam_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    cam_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
except OSError:
    pass
cam_sock.bind(("0.0.0.0", CAMERA_UDP_PORT))


def _save_latest(jpeg: bytes):
    try:
        tmp = f"{IMAGE_FILENAME}.tmp"
        with open(tmp, "wb") as f:
            f.write(jpeg)
        os.replace(tmp, IMAGE_FILENAME)
    except Exception as e:
        print(f"[{get_time()}] [CAM] Failed to save image: {e}")


def _is_newer(new_id: int, current_id: int) -> bool:
    diff = (new_id - current_id) & 0xFFFF
    return 0 < diff < 0x8000


def _valid_jpeg(data: bytes) -> bool:
    if len(data) < 4 or data[:2] != b"\xff\xd8" or data[-2:] != b"\xff\xd9":
        return False
    try:
        Image.open(io.BytesIO(data)).verify()
        return True
    except Exception:
        return False


def listen_camera():
    print(f"[{get_time()}] Camera UDP listener active on port {CAMERA_UDP_PORT}")
    current_image_id = -1
    image_buffer: dict[int, bytes] | None = None

    frames_ok = 0
    frames_dropped = 0
    last_report = time.time()
    last_frame_at = 0.0

    while True:
        try:
            data, addr = cam_sock.recvfrom(CAMERA_RECV_BUFFER)
            touch_heartbeat()
            if len(data) < 6:
                continue

            img_id, total_chunks, chunk_idx = struct.unpack(">HHH", data[:6])
            payload = data[6:]
            now = time.time()

            if img_id != current_image_id:
                idle = last_frame_at == 0.0 or (now - last_frame_at) > 5.0
                if current_image_id != -1 and not idle and not _is_newer(img_id, current_image_id):
                    continue
                if image_buffer is not None:
                    frames_dropped += 1
                current_image_id = img_id
                image_buffer = {idx: b"" for idx in range(total_chunks)}
            elif image_buffer is None:
                continue

            if chunk_idx < total_chunks:
                image_buffer[chunk_idx] = payload

            if total_chunks and all(len(image_buffer[idx]) > 0 for idx in range(total_chunks)):
                full = b"".join(image_buffer[idx] for idx in range(total_chunks))
                image_buffer = None
                if _valid_jpeg(full):
                    camera_frames.update(full)
                    _save_latest(full)
                    frames_ok += 1
                    last_frame_at = now
                else:
                    frames_dropped += 1

            if now - last_report >= 5.0:
                age = f"{now - last_frame_at:.1f}s" if last_frame_at else "never"
                print(
                    f"[{get_time()}] [CAM] {frames_ok / (now - last_report):.1f} fps, "
                    f"last frame {age} ago, dropped {frames_dropped}"
                )
                frames_ok = 0
                frames_dropped = 0
                last_report = now
        except Exception:
            pass


def start_camera_listener():
    thread = threading.Thread(target=listen_camera, daemon=True)
    thread.start()
