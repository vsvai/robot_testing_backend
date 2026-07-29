import io
import os
import socket
import struct
import threading
import time
from datetime import datetime

from PIL import Image

from config import CAMERA_UDP_PORT, IMAGE_FILENAME, CAMERA_RECV_BUFFER


def get_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


cam_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
cam_sock.bind(("0.0.0.0", CAMERA_UDP_PORT))


def listen_camera():
    print(f"[{get_time()}] Camera UDP listener active on port {CAMERA_UDP_PORT}")
    current_image_id = -1
    image_buffer: dict[int, bytes] = {}
    start_time = 0.0

    while True:
        try:
            data, addr = cam_sock.recvfrom(CAMERA_RECV_BUFFER)
            if len(data) < 6:
                continue

            img_id, total_chunks, chunk_idx = struct.unpack(">HHH", data[:6])
            payload = data[6:]

            if img_id != current_image_id:
                if current_image_id != -1:
                    received = sum(1 for k in image_buffer if len(image_buffer[k]) > 0)
                    print(f"[{get_time()}] [CAM] Frame {current_image_id} incomplete, dropped {total_chunks - received} packets")
                current_image_id = img_id
                image_buffer = {idx: b"" for idx in range(total_chunks)}
                start_time = time.time()
                print(f"[{get_time()}] [CAM] Frame {img_id}: expecting {total_chunks} chunks")

            image_buffer[chunk_idx] = payload

            if all(len(image_buffer[idx]) > 0 for idx in range(total_chunks)):
                full = b"".join(image_buffer[idx] for idx in range(total_chunks))
                size_kb = len(full) / 1024
                print(f"[{get_time()}] [CAM] Frame complete ({size_kb:.1f} KB)")

                try:
                    stream = io.BytesIO(full)
                    img = Image.open(stream)
                    img.verify()
                    stream.seek(0)
                    img = Image.open(stream)
                    tmp = f"{IMAGE_FILENAME}.tmp"
                    img.save(tmp, "JPEG")
                    os.replace(tmp, IMAGE_FILENAME)
                    elapsed = time.time() - start_time
                    print(f"[{get_time()}] [CAM] Saved {IMAGE_FILENAME} in {elapsed:.2f}s")
                except Exception as e:
                    print(f"[{get_time()}] [CAM] Corrupted frame: {e}")

                current_image_id = -1
        except Exception:
            pass


def start_camera_listener():
    thread = threading.Thread(target=listen_camera, daemon=True)
    thread.start()
