import threading
import time


class CameraFrameStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._seq = 0
        self._jpeg: bytes | None = None
        self._updated_at = 0.0

    def update(self, jpeg: bytes):
        with self._lock:
            self._jpeg = jpeg
            self._seq += 1
            self._updated_at = time.time()

    def snapshot(self) -> tuple[int, bytes | None, float]:
        with self._lock:
            return self._seq, self._jpeg, self._updated_at


camera_frames = CameraFrameStore()
