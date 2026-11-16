import os
import socket
import struct
import threading
import time
from datetime import datetime

from config import CAMERA_UDP_PORT, IMAGE_FILENAME, CAMERA_RECV_BUFFER
from app.services.heartbeat import touch_heartbeat
from app.services.camera_store import camera_frames


def get_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


cam_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
cam_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    cam_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
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


def listen_camera():
    print(f"[{get_time()}] Camera UDP listener active on port {CAMERA_UDP_PORT}")
    current_image_id = -1
    image_buffer: dict[int, bytes] = {}

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

            if img_id != current_image_id:
                if current_image_id != -1:
                    frames_dropped += 1
                current_image_id = img_id
                image_buffer = {idx: b"" for idx in range(total_chunks)}

            if chunk_idx < total_chunks:
                image_buffer[chunk_idx] = payload

            if total_chunks and all(len(image_buffer[idx]) > 0 for idx in range(total_chunks)):
                full = b"".join(image_buffer[idx] for idx in range(total_chunks))
                if full[:2] == b"\xff\xd8" and full[-2:] == b"\xff\xd9":
                    camera_frames.update(full)
                    _save_latest(full)
                    frames_ok += 1
                    last_frame_at = time.time()
                else:
                    frames_dropped += 1
                current_image_id = -1

            now = time.time()
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
