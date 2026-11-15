"""湖心小寺（许愿页里的俯视三维小游戏）：谁在场、坐在哪、天气，以及留下的心意（红布条、木牌、香、硬币）。

客户端进殿后每隔几秒报一次自己的位置（/beat），顺便拿回全场的情况。没有长连接，够用也好部署。
真人不多的时候由内置的香客撑场面：他们什么时候来、坐哪，由时间算出来（同一时刻所有人看到的一样），不存库。
"""
import hashlib
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..auth import current_user
from ..coins import earn
from ..config import settings
from ..db import get_db
from ..models import SanctuaryOffering, SanctuaryPresence, User, now

router = APIRouter()

SCENES = ("islet",)
# 每座殿能留下的心意
KINDS = {"islet": ("ribbon", "plaque", "incense")}
ACTIONS = ("bow", "kneel", "pray", "meditate")
# 多久没报就算离开（秒）
STALE = 30
# 树上最多显示多少件别人挂的
SHOWN = 40

NPC_NAMES = (
    "晚风", "栀子", "阿宁", "小满", "云起", "知南", "听雨", "青禾", "一苇", "星野", "念安", "见山",
    "松月", "阿梨", "初七", "向晚", "木木", "简兮", "半夏", "南乔", "清欢", "予安", "微澜", "山岚",
    "阿布", "时雨", "小鹿", "沐阳", "十里", "禾川", "朝颜", "之遥", "鹿鸣", "溪午", "明澈", "长安",
)


def _hash(*parts) -> int:
    return int.from_bytes(hashlib.blake2b("|".join(map(str, parts)).encode(), digest_size=6).digest(), "big")


def weather_at(scene: str, t: datetime) -> str:
    """这座殿此刻的天气：每 20 分钟定一次，所有人看到的一样。冬天才会下雪。"""
    local = t.astimezone(settings.tz)
    r = _hash("weather", scene, local.date(), (local.hour * 60 + local.minute) // 20) % 100
    if r < 56:
        return "clear"
    if r < 78:
        return "rain"
    if r < 88:
        return "storm"
    return "snow" if local.month in (11, 12, 1, 2) else "rain"


def npcs_at(scene: str, t: datetime, seats: int, taken: set[int]) -> list[dict]:
    """此刻在场的内置香客。每位各有各的作息：一段时间来、一段时间不来，来了就固定坐一个位置。"""
    local = t.astimezone(settings.tz)
    # 早晚人多，凌晨人少，但任何时候都不会冷清（三十六位里来几成）
    share = (36, 32, 30, 30, 30, 34, 40, 46, 44, 40, 38, 40, 44, 42, 40, 40, 42, 48, 54, 60, 64, 62, 52, 42)[local.hour]
    limit = max(0, min(seats - len(taken) - 2, seats * 2 // 3))
    ts = int(t.timestamp())
    out = []
    used = set(taken)
    for i, name in enumerate(NPC_NAMES):
        if len(out) >= limit:
            break
        stay = 480 + _hash("stay", scene, i) % 1200  # 一次待 8 到 28 分钟
        block = (ts + _hash("offset", scene, i) % stay) // stay
        if _hash("come", scene, i, block) % 100 >= share:
            continue
        seat = _hash("seat", scene, i, block) % seats
        while seat in used:
            seat = (seat + 1) % seats
        used.add(seat)
        out.append({"id": f"n{i}", "name": name, "seat": seat, "npc": True, "action": None})
    return out


class BeatIn(BaseModel):
    seat: int = Field(default=-1, ge=-1, le=200)
    action: str | None = None
    # 这座殿一共有多少个座位、树上有多少个能挂的位置（由场景决定，客户端报上来）
    seats: int = Field(default=32, ge=1, le=200)


def _scene(scene: str) -> str:
    if scene not in SCENES:
        raise HTTPException(404, "没有这座殿")
    return scene


def _state(db: Session, scene: str, me: User, seats: int) -> dict:
    t = now()
    rows = db.execute(
        select(SanctuaryPresence, User.name)
        .join(User, User.id == SanctuaryPresence.user_id)
        .where(SanctuaryPresence.scene == scene, SanctuaryPresence.last_seen > t - timedelta(seconds=STALE), User.banned.is_(False))
    ).all()
    people, taken, standing = [], set(), 0
    for p, name in rows:
        if p.user_id == me.id:
            if p.seat >= 0:
                taken.add(p.seat)
            continue
        if p.seat < 0 or p.seat >= seats or p.seat in taken:
            standing += 1
            continue
        taken.add(p.seat)
        at = p.action_at.replace(tzinfo=t.tzinfo) if p.action_at and p.action_at.tzinfo is None else p.action_at
        fresh = at is not None and (t - at).total_seconds() < 8
        people.append({"id": f"u{p.user_id}", "name": name, "seat": p.seat, "npc": False, "action": p.action if fresh else None})
    people += npcs_at(scene, t, seats, taken)
    offerings = db.execute(
        select(SanctuaryOffering.slot, SanctuaryOffering.kind)
        .where(SanctuaryOffering.scene == scene, SanctuaryOffering.slot >= 0, SanctuaryOffering.user_id != me.id)
        .order_by(SanctuaryOffering.id.desc())
        .limit(SHOWN)
    ).all()
    mine = db.execute(
        select(SanctuaryOffering.slot, SanctuaryOffering.kind, SanctuaryOffering.text)
        .where(SanctuaryOffering.scene == scene, SanctuaryOffering.user_id == me.id)
        .order_by(SanctuaryOffering.id.desc())
        .limit(20)
    ).all()
    total = db.scalar(select(func.count()).select_from(SanctuaryOffering).where(SanctuaryOffering.scene == scene)) or 0
    return {
        "scene": scene,
        "weather": weather_at(scene, t),
        "count": len(people) + standing + 1,
        "people": people,
        "offerings": [{"slot": s, "kind": k} for s, k in offerings],
        "mine": [{"slot": s, "kind": k, "text": x} for s, k, x in mine],
        "offered_total": total,
    }


@router.post("/sanctuary/{scene}/beat")
def beat(scene: str, body: BeatIn, me: User = Depends(current_user), db: Session = Depends(get_db)):
    """报一次自己的位置（进殿、坐下、做动作时立刻报，平时每几秒报一次），拿回全场的情况。"""
    _scene(scene)
    if body.action is not None and body.action not in ACTIONS:
        raise HTTPException(400, "没有这个动作")
    p = db.get(SanctuaryPresence, me.id)
    if p is None:
        p = SanctuaryPresence(user_id=me.id, scene=scene)
        db.add(p)
    p.scene = scene
    p.seat = body.seat
    p.last_seen = now()
    if body.action:
        p.action = body.action
        p.action_at = now()
    db.commit()
    return _state(db, scene, me, body.seats)


@router.post("/sanctuary/{scene}/leave")
def leave(scene: str, me: User = Depends(current_user), db: Session = Depends(get_db)):
    _scene(scene)
    db.execute(delete(SanctuaryPresence).where(SanctuaryPresence.user_id == me.id))
    db.commit()
    return {"ok": True}


class OfferIn(BaseModel):
    kind: str
    slot: int = Field(default=-1, ge=-1, le=500)
    text: str | None = Field(default=None, max_length=200)


@router.post("/sanctuary/{scene}/offer")
def offer(scene: str, body: OfferIn, me: User = Depends(current_user), db: Session = Depends(get_db)):
    """留下一件心意。写在上面的话只有自己看得到，所以不过内容检查。每天第一次有金币。"""
    _scene(scene)
    if body.kind not in KINDS[scene]:
        raise HTTPException(400, "这座殿里没有这种心意")
    db.add(SanctuaryOffering(user_id=me.id, scene=scene, kind=body.kind, slot=body.slot, text=(body.text or "").strip() or None))
    got = earn(db, me, "sanctuary")
    db.commit()
    return {"ok": True, "got": got, "coins": me.coins}
