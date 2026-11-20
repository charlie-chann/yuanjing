"""湖心小寺的钓鱼和背包。

规则（都在这个文件开头，好改；鱼本身的名字、稀有度、卖价、长度在 app/islet.py）：
- 两种水域：sea（岛四周的湖，码头和岸边）、pond（小池塘）。咬钩和提竿的时机由客户端演，
  提竿成功才调 POST /fishing/catch，服务器按水域、天色、天气的权重摇一条，放进背包。
- 每天最多钓 DAILY_CATCH 次（钓到水草也算一次）。提竿失败不调接口、不占次数。
- 第一次钓到一种鱼有一笔金币（按稀有度）。每种鱼记个人最大纪录。
- 背包里的东西能卖掉换金币（POST /bag/sell）。
"""
import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_user
from ..coins import today
from ..db import get_db
from ..islet import FISH, WEED, bag_view, give, have, item_info, kind_of, take
from ..models import CoinEntry, FishDex, FishingDay, User

router = APIRouter()

SPOTS = ("sea", "pond")
TIMES = ("dawn", "day", "dusk", "night")
WEATHERS = ("clear", "rain", "storm", "snow")
DAILY_CATCH = 30                           # 每天最多钓几次

# 基础权重：水域 → {鱼: 权重}。权重是相对的，不用凑成 100
BASE_WEIGHTS: dict[str, dict[str, float]] = {
    "pond": {"crucian": 34, "loach": 30, "goldfish": 12, "shrimp": 12, WEED: 12},
    "sea": {"whitebait": 40, "silver": 12, "bass": 14, "mandarin": 5, "crab": 4, WEED: 14},
}
# 天色让某些鱼多起来：(鱼, 天色) → 权重乘几
TIME_BOOST: dict[tuple[str, str], float] = {
    ("silver", "dawn"): 3,                 # 银鱼清晨多
    ("crab", "dusk"): 3,                   # 大闸蟹黄昏和夜里多
    ("crab", "night"): 3,
    ("loach", "night"): 1.5,
    ("bass", "dusk"): 1.5,
}
# 只在特定时候才有的鱼：鱼 → (水域, 哪些天色, 哪些天气, 权重)。None 表示不限
ONLY_WHEN: dict[str, tuple[str, tuple[str, ...] | None, tuple[str, ...] | None, float]] = {
    "carp_gold": ("sea", None, ("rain", "storm"), 3),      # 金鳞鲤：雨天才有
    "moon": ("sea", ("night",), ("clear",), 3),            # 月光鱼：晴朗的夜里才有
}
# 第一次钓到一种鱼奖励多少金币（按稀有度）
FIRST_COINS = {"common": 5, "uncommon": 10, "rare": 20, "legend": 50}

# 摇鱼用的随机数。测试里可以换成固定种子的
rng = random.Random()


def fish_weights(spot: str, time: str, weather: str) -> dict[str, float]:
    """这片水、这个天色、这种天气下，每种鱼的权重"""
    w = dict(BASE_WEIGHTS[spot])
    for fish in w:
        w[fish] *= TIME_BOOST.get((fish, time), 1)
    for fish, (where, times, weathers, weight) in ONLY_WHEN.items():
        if where == spot and (times is None or time in times) and (weathers is None or weather in weathers):
            w[fish] = weight
    return w


def _day(db: Session, me: User) -> FishingDay:
    d = db.get(FishingDay, me.id)
    if d is None:
        d = FishingDay(user_id=me.id, day=today(), count=0)
        db.add(d)
    if d.day != today():
        d.day = today()
        d.count = 0
    return d


class CatchIn(BaseModel):
    spot: str
    time: str = Field(default="day", max_length=12)
    weather: str = Field(default="clear", max_length=12)


@router.post("/fishing/catch")
def catch(body: CatchIn, me: User = Depends(current_user), db: Session = Depends(get_db)):
    """提竿成功：摇一条鱼放进背包"""
    if body.spot not in SPOTS:
        raise HTTPException(400, "这里钓不了鱼")
    d = _day(db, me)
    if d.count >= DAILY_CATCH:
        raise HTTPException(409, "今天的鱼都被你钓得差不多了，明天再来")
    d.count += 1
    w = fish_weights(body.spot, body.time, body.weather)
    fish = rng.choices(list(w), weights=list(w.values()))[0]
    info = item_info(fish)
    out = {"id": fish, "name": info["name"], "rarity": info["rarity"], "about": info["about"], "size_cm": 0, "record": False, "first": False}
    got = 0
    if fish != WEED:
        lo, hi = FISH[fish][4:6]
        # 两个随机数取平均：中等个头的多，特别大特别小的少
        mm = round((lo + (hi - lo) * (rng.random() + rng.random()) / 2) * 10)
        dex = db.get(FishDex, (me.id, fish))
        if dex is None:
            dex = FishDex(user_id=me.id, fish_id=fish, count=0, best_mm=mm)
            db.add(dex)
            out["first"] = True
            got = FIRST_COINS[info["rarity"]]
            me.coins += got
            db.add(CoinEntry(user_id=me.id, amount=got, kind="fish_first", what=f"第一次钓到{info['name']}", day=today()))
        elif mm > dex.best_mm:
            dex.best_mm = mm
            out["record"] = True
        dex.count += 1
        out["size_cm"] = mm / 10
    count = give(db, me, fish)
    db.commit()
    return {"fish": out, "count": count, "left": DAILY_CATCH - d.count, "got": got, "coins": me.coins, "items": bag_view(db, me)}


@router.get("/fishing")
def fishing(me: User = Depends(current_user), db: Session = Depends(get_db)):
    """钓鱼图鉴：每种鱼钓到过没有、一共几条、最大纪录；今天还能钓几次"""
    dex = {r.fish_id: r for r in db.scalars(select(FishDex).where(FishDex.user_id == me.id))}
    d = db.get(FishingDay, me.id)
    used = d.count if d is not None and d.day == today() else 0
    out = []
    for fish, (name, rarity, about, sell, lo, hi) in FISH.items():
        r = dex.get(fish)
        only = ONLY_WHEN.get(fish)
        out.append({
            "id": fish, "name": name, "rarity": rarity, "about": about, "sell": sell, "min_cm": lo, "max_cm": hi,
            "spots": [s for s in SPOTS if fish in BASE_WEIGHTS[s] or (only is not None and only[0] == s)],
            "caught": r is not None, "count": r.count if r else 0, "best_cm": r.best_mm / 10 if r else None,
        })
    return {"fish": out, "left": DAILY_CATCH - used, "daily": DAILY_CATCH, "kinds": len(dex), "total": len(FISH)}


# ───────── 背包 ─────────
@router.get("/bag")
def bag(me: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"items": bag_view(db, me), "coins": me.coins}


class SellIn(BaseModel):
    item_id: str
    count: int = Field(default=1, ge=1, le=999)


@router.post("/bag/sell")
def sell(body: SellIn, me: User = Depends(current_user), db: Session = Depends(get_db)):
    """卖掉换金币。水草卖不出钱，等于扔掉"""
    if kind_of(body.item_id) is None:
        raise HTTPException(404, "没有这样东西")
    if have(db, me, body.item_id) < body.count:
        raise HTTPException(400, "背包里没有这么多")
    info = item_info(body.item_id)
    take(db, me, body.item_id, body.count)
    got = info["sell"] * body.count
    if got > 0:
        me.coins += got
        db.add(CoinEntry(user_id=me.id, amount=got, kind="sell", what=f"卖掉{info['name']} ×{body.count}", day=today()))
    db.commit()
    return {"got": got, "coins": me.coins, "item_id": body.item_id, "count": have(db, me, body.item_id), "items": bag_view(db, me)}
