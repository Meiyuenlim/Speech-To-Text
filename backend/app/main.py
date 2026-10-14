from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings
from app.db.database import init_db


def create_app() -> FastAPI:
    settings.ensure_directories()
    init_db()
    app = FastAPI(title="Local Meeting Transcription", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    if settings.uploads_dir.exists():
        app.mount("/data", StaticFiles(directory=settings.data_dir), name="data")
    return app


app = create_app()
