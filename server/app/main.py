"""愿境后端入口。本地启动：.venv/bin/uvicorn app.main:app --port 8787（见 server/README.md）"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import Base, SessionLocal, engine
from .routers import ai, files, me, plaza, sanctuary, wish
from .seed import seed

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 本地开发直接按模型建表；正式环境用 alembic upgrade head 管理表结构
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(engine)
    if settings.seed_demo:
        with SessionLocal() as db:
            seed(db)
    yield


app = FastAPI(title="愿境", lifespan=lifespan)
app.include_router(me.router)
app.include_router(plaza.router)
app.include_router(sanctuary.router)
app.include_router(ai.router)
app.include_router(files.router)
app.include_router(wish.router)
settings.upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=settings.upload_dir), name="files")
settings.wish_voice_dir.mkdir(parents=True, exist_ok=True)
app.mount("/voice/wish", StaticFiles(directory=settings.wish_voice_dir), name="wish_voice")


@app.get("/health")
def health():
    return {"ok": True, "llm": settings.llm_enabled, "demo_membership": settings.demo_membership}


@app.exception_handler(ValueError)
async def value_error(_: Request, exc: ValueError):
    return JSONResponse({"detail": str(exc)}, status_code=400)
