"""图片上传：缩到长边 1400，重新压成 JPEG（顺带去掉照片里的定位等隐私信息）。"""
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from PIL import Image, ImageOps

from ..auth import current_user
from ..config import settings
from ..models import User

router = APIRouter()
MAX_BYTES = 15 * 1024 * 1024


@router.post("/files")
async def upload(file: UploadFile, me: User = Depends(current_user)):
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "图片太大了")
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception:
        raise HTTPException(400, "这不是一张能打开的图片")
    img.thumbnail((1400, 1400))
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    name = f"{me.id}-{uuid.uuid4().hex}.jpg"
    img.save(settings.upload_dir / name, "JPEG", quality=86)
    return {"url": f"/files/{name}"}
