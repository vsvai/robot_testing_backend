from pathlib import Path

HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8100

ROBOT_UDP_PORT = 8888
CAMERA_UDP_PORT = 5005

UDP_RECV_BUFFER = 1024
CAMERA_RECV_BUFFER = 1030

IMAGE_FILENAME = "latest_image.jpg"

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = Path("/home/ubuntu/ota_stuff/logs")
FIRMWARE_DIR = BASE_DIR / "firmware"

CORS_ORIGINS = ["*"]
CORS_METHODS = ["*"]
CORS_HEADERS = ["*"]
