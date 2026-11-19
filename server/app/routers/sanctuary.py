"""湖心小寺（许愿页里的俯视三维小游戏）：谁在场、坐在哪、天气，以及留下的心意（红布条、木牌、香、硬币）。

客户端进殿后每隔几秒报一次自己的位置（/beat），顺便拿回全场的情况。没有长连接，够用也好部署。
真人不多的时候由内置的香客撑场面：他们什么时候来、坐哪，由时间算出来（同一时刻所有人看到的一样），不存库。
红布条、木牌上写的愿望挂在树上，所有人都看得到（产品决定：不审核）——只限写的时候界面上说明了这一点的（客户端带 public）。
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
# 自己挂在树上的最多拿回多少件（树上一共 32 格；香不算）
MINE_SHOWN = 32
# 挂在树上的心意
CLOTH = ("ribbon", "plaque")
# 挂在树上给大家看的红布条、木牌最多写多少字（客户端写成竖排的图，也是这么多）
CLOTH_TEXT_MAX = 40

NPC_NAMES = (
    "晚风", "栀子", "阿宁", "小满", "云起", "知南", "听雨", "青禾", "一苇", "星野", "念安", "见山",
    "松月", "阿梨", "初七", "向晚", "木木", "简兮", "半夏", "南乔", "清欢", "予安", "微澜", "山岚",
    "阿布", "时雨", "小鹿", "沐阳", "十里", "禾川", "朝颜", "之遥", "鹿鸣", "溪午", "明澈", "长安",
    "林间", "小舟", "叶子", "阿遥", "暮云", "清和", "怀瑾", "晴川", "白露", "知秋", "月白", "苏木",
    "阿森", "小橙", "北辰", "南风", "雨眠", "夏至", "以宁", "野菊", "江屿", "听澜", "竹西", "临溪",
    "七七", "阿柒", "一一", "糖糖", "小雅", "思远", "若水", "春和", "景明", "初晴", "归舟", "明月",
    "西窗", "晓风", "阿朵", "小柚", "海棠", "云舒", "安然", "知行", "念念", "岁岁", "朝朝", "暮暮",
    "青柠", "白茶", "麦子", "阿凉", "蒲公英", "小葵", "风铃", "砚池", "墨白", "梧桐", "芦花", "远山",
    "阿九", "十一", "小白", "阿橘", "南星", "疏影", "梅子", "清越", "望舒", "星河", "寒山", "照水",
    "可可", "豆豆", "阿禾", "阿茶", "知了", "林夕", "听风", "一诺", "长歌", "未央", "子衿", "无忧",
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


# 内置香客在岛上会做的事（客户端按代号找地方）：
#   s 去蒲团静坐  i 香炉前上香  h 大殿前拜  t 许愿树下  p 池塘边看鱼  v 钟亭  e 石碑前  l 栈桥上看湖
ACTIVITIES = "sihtpvel"
# 一天里每个小时大概有多少人（凌晨少，早上和傍晚是高峰）
CROWD_BY_HOUR = (11, 10, 10, 10, 11, 14, 22, 36, 44, 40, 32, 28, 27, 29, 30, 32, 36, 44, 48, 46, 38, 30, 22, 15)
CROWD_MIN, CROWD_MAX = 10, 50


def crowd_target(t: datetime) -> float:
    """此刻岛上大概该有多少内置香客：按小时的曲线（相邻小时之间平滑过渡），再叠一个慢慢变的起伏，每天不一样"""
    local = t.astimezone(settings.tz)
    h = local.hour + local.minute / 60
    a, b = CROWD_BY_HOUR[int(h) % 24], CROWD_BY_HOUR[(int(h) + 1) % 24]
    k = h - int(h)
    base = a + (b - a) * k
    # 半小时一档的起伏（±20%），档与档之间线性过渡
    blk = (local.hour * 60 + local.minute) / 30
    n0 = _hash("crowd", local.date(), int(blk)) % 1000 / 1000
    n1 = _hash("crowd", local.date(), int(blk) + 1) % 1000 / 1000
    wave = n0 + (n1 - n0) * (blk - int(blk))
    return max(CROWD_MIN, min(CROWD_MAX, base * (0.8 + 0.4 * wave)))


def _visit(scene: str, i: int, t: datetime, target: float):
    """第 i 位内置香客此刻在不在、来了多久、打算待多久、要做哪些事。
    每人把时间分成一段段（每段 30–60 分钟），每段里按「此刻该有多少人」的比例决定来不来；来的话在段里某个时刻来，待 6–40 分钟。"""
    ts = t.timestamp()
    period = 1800 + _hash("period", scene, i) % 1800
    # 平均每人在场的时长占比，用来把「该有多少人」换算成「每段来的概率」
    for back in (0, 1):
        block = int((ts + _hash("offset", scene, i) % period) // period) - back
        start_block = block * period - _hash("offset", scene, i) % period
        stay = 360 + _hash("stay", scene, i, block) % 2040
        arrive = start_block + _hash("arrive", scene, i, block) % max(1, period - stay)
        when = datetime.fromtimestamp(arrive, t.tzinfo)
        chance = min(1.0, crowd_target(when) / len(NPC_NAMES) * period / 1380)
        if _hash("come", scene, i, block) % 10000 / 10000 >= chance:
            continue
        if arrive <= ts < arrive + stay:
            # 要做的事：多数人以静坐为主，顺便去一两个地方；有些人只是来逛逛
            r = _hash("plan", scene, i, block)
            n = 1 + r % 3
            plan = ""
            for k in range(n):
                c = ACTIVITIES[1 + (r >> (4 + 3 * k)) % (len(ACTIVITIES) - 1)]
                if c not in plan:
                    plan += c
            if (r >> 20) % 100 < 72:
                plan = plan[:1] + "s" + plan[1:] if (r >> 24) % 2 else "s" + plan
            return int(ts - arrive), int(stay), plan
    return None


def npcs_at(scene: str, t: datetime, seats: int, taken: set[int]) -> list[dict]:
    """此刻在场的内置香客：10 到 50 人，按时间自动多少，随时有人来、有人走。
    同一时刻所有人看到的一样（全由时间算出来，不存库）。每人带着「来了多久、待多久、要做哪些事」，客户端照着演。"""
    target = crowd_target(t)
    out, used = [], set(taken)
    # 内置香客最多坐满三分之二的蒲团，真人来了总有位子
    cap = len(taken) + seats * 2 // 3
    for i, name in enumerate(NPC_NAMES):
        v = _visit(scene, i, t, target)
        if v is None:
            continue
        since, stay, plan = v
        seat = -1
        if "s" in plan and len(used) < cap:
            seat = _hash("seat", scene, i, stay) % seats
            while seat in used:
                seat = (seat + 1) % seats
            used.add(seat)
        out.append({"id": f"n{i}", "name": name, "seat": seat, "npc": True, "action": None, "plan": plan, "since": since, "stay": stay})
    # 保证在 10 到 50 之间：多了去掉来得最晚的，少了请几位「刚到」的
    out.sort(key=lambda p: -p["since"])
    if len(out) > CROWD_MAX:
        for p in out[CROWD_MAX:]:
            used.discard(p["seat"])
        out = out[:CROWD_MAX]
    i = 0
    present = {p["id"] for p in out}
    while len(out) < CROWD_MIN and i < len(NPC_NAMES):
        j = (_hash("fill", scene, t.date(), i) + i) % len(NPC_NAMES)
        i += 1
        if f"n{j}" in present:
            continue
        present.add(f"n{j}")
        block = int(t.timestamp() // 1800)
        since = _hash("fillsince", scene, j, block) % 900
        seat, plan = -1, "lp"
        if len(used) < cap:
            seat, plan = _hash("seat", scene, j, block) % seats, "s"
            while seat in used:
                seat = (seat + 1) % seats
            used.add(seat)
        out.append({"id": f"n{j}", "name": NPC_NAMES[j], "seat": seat, "npc": True, "action": None, "plan": plan, "since": since, "stay": 1800})
    return out


class BeatIn(BaseModel):
    seat: int = Field(default=-1, ge=-1, le=400)
    action: str | None = None
    # 这座殿一共有多少个座位、树上有多少个能挂的位置（由场景决定，客户端报上来）
    seats: int = Field(default=32, ge=1, le=400)


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
    # 自己的座位先占上：两个人同时挑了同一个蒲团时，各自看到的都是自己坐着、对方站着（不会两个人叠在一个蒲团上）
    for p, _ in rows:
        if p.user_id == me.id and p.seat >= 0:
            taken.add(p.seat)
    for p, name in rows:
        if p.user_id == me.id:
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
        select(SanctuaryOffering.id, SanctuaryOffering.slot, SanctuaryOffering.kind, SanctuaryOffering.text, SanctuaryOffering.public)
        .where(SanctuaryOffering.scene == scene, SanctuaryOffering.slot >= 0, SanctuaryOffering.kind.in_(CLOTH), SanctuaryOffering.user_id != me.id)
        .order_by(SanctuaryOffering.id.desc())
        .limit(SHOWN)
    ).all()
    # 自己挂在树上的（只算布条、木牌：天天上香的人，香不会把自己的布条挤出这一份）
    mine = db.execute(
        select(SanctuaryOffering.id, SanctuaryOffering.slot, SanctuaryOffering.kind, SanctuaryOffering.text)
        .where(SanctuaryOffering.scene == scene, SanctuaryOffering.slot >= 0, SanctuaryOffering.kind.in_(CLOTH), SanctuaryOffering.user_id == me.id)
        .order_by(SanctuaryOffering.id.desc())
        .limit(MINE_SHOWN)
    ).all()
    total = db.scalar(select(func.count()).select_from(SanctuaryOffering).where(SanctuaryOffering.scene == scene)) or 0
    return {
        "scene": scene,
        "weather": weather_at(scene, t),
        "count": len(people) + standing + 1,
        "people": people,
        # 别人的字：写的时候说明了「大家都看得到」的才给（老版本写的那些当时说的是只有自己看得到）
        "offerings": [{"id": i, "slot": s, "kind": k, "text": x if pub else None} for i, s, k, x, pub in offerings],
        "mine": [{"id": i, "slot": s, "kind": k, "text": x} for i, s, k, x in mine],
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
    # 写的字给不给别人看（新版本挂红布条、木牌时带 true：写的界面上说了「来岛上的人都看得到」）
    public: bool = False


@router.post("/sanctuary/{scene}/offer")
def offer(scene: str, body: OfferIn, me: User = Depends(current_user), db: Session = Depends(get_db)):
    """留下一件心意。红布条、木牌上写的话挂在树上，所有人都看得到；按产品的决定不过内容检查。每天第一次有金币。
    返回这一件的编号：客户端拿它认出下次心跳里自己刚挂的那一件，不重复挂。"""
    _scene(scene)
    if body.kind not in KINDS[scene]:
        raise HTTPException(400, "这座殿里没有这种心意")
    text = (body.text or "").strip() or None
    public = body.public and body.kind in CLOTH and text is not None
    if public and len(text) > CLOTH_TEXT_MAX:
        # 挂出来给大家看的最多 40 个字（客户端已经截过；这里兜底，多的不要）
        text = text[:CLOTH_TEXT_MAX]
    row = SanctuaryOffering(user_id=me.id, scene=scene, kind=body.kind, slot=body.slot, text=text, public=public)
    db.add(row)
    got = earn(db, me, "sanctuary")
    db.commit()
    return {"ok": True, "id": row.id, "got": got, "coins": me.coins}
