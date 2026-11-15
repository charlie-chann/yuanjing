"""许愿回应：用户写下愿望 → 匹配到意图 → 从 104.8 万条回应里挑一条最近没听过的，返回文字和每句的语音地址。"""
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_user
from ..config import settings
from ..db import get_db
from ..models import User, WishHeard
from ..wishmatch import WishMatcher

router = APIRouter()


@lru_cache
def matcher() -> WishMatcher:
    return WishMatcher(settings.wish_db)


class WishAnswerIn(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    scene: str | None = None
    hour: int = Field(default=12, ge=0, le=23)
    # 在哪里许的愿。许愿殿里不说许愿页那些场景里才有的东西（金池、孔明灯……）


# 许愿页各个场景专有的意象：在别处听到会出戏


def voice_url(segment_id: int) -> str | None:
    f = settings.wish_voice_dir / f"{segment_id}.m4a"
    return f"/voice/wish/{segment_id}.m4a" if f.exists() else None


@router.post("/wish/answer")
def wish_answer(body: WishAnswerIn, me: User = Depends(current_user), db: Session = Depends(get_db)):
    m = matcher()
    if not m.ok:
        raise HTTPException(503, "回应库还没生成")
    recent = db.scalars(select(WishHeard.core).where(WishHeard.user_id == me.id).order_by(WishHeard.id.desc()).limit(60)).all()
    r = m.answer(body.text, body.scene, body.hour, list(recent))
    if r.get("support"):
        return r
    db.add(WishHeard(user_id=me.id, answer_id=r["answer_id"], core=r["segments"][1], intent=r["intent"]))
    db.commit()
    r["audio"] = [voice_url(s) for s in r["segments"]]
    return r


@router.get("/wish/stats")
def wish_stats():
    m = matcher()
    return {"ok": m.ok, **getattr(m, "stats", {}), "voiced": len(list(settings.wish_voice_dir.glob("*.m4a"))) if settings.wish_voice_dir.exists() else 0}
