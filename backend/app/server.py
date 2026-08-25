from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS, CORS_METHODS, CORS_HEADERS
from app.services.udp_client import start_udp_listener
from app.services.camera_listener import start_camera_listener
from app.services.rtk_service import rtk_service
from app.routers import robot, logs, camera, ota, telemetry, rtk


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_udp_listener()
    start_camera_listener()
    rtk_service.start_udp_listener()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sudoyantra Robot API",
        version="1.3",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=CORS_METHODS,
        allow_headers=CORS_HEADERS,
    )

    app.include_router(robot.router)
    app.include_router(telemetry.router)
    app.include_router(camera.router)
    app.include_router(ota.router)
    app.include_router(logs.router)
    app.include_router(rtk.router)

    return app
