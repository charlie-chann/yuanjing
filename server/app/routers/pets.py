"""湖心小寺的小动物：摸、喂、亲密度、迎接、礼物。

规则（都在这个文件开头，好改）：
- 十只有名字的：五只狗五只猫。每个人和每一只各有一份亲密度（老代码里叫交情，是同一个数）。
- 摸一下 +1，每天前 3 次算。
- 喂：不带东西是花 2 金币喂一把普通口粮，+2；带背包里的鱼或口粮，扣掉 1 个，按东西涨
  （鱼按稀有度 2/3/5/8，口粮按各自的数）。每只有三样最爱，喂到最爱的 ×1.5 向上取整。
  每只每天喂食前 5 次算亲密度，多了照样能喂，只是不涨。
- 亲密度分六档：陌生、认识、亲近、最好的朋友、知己、家人。前四档的门槛和含义不能动
  （Unity 里按 level ≥ 2 迎接、≥ 3 一直跟着）。
- 每日小礼物：「亲近」每天一半机会、「最好的朋友」起每天必有。给一件收藏品进背包（不再换金币），
  每只有自己会叼来的四种，越熟越可能是稀有的。一只一天一件。
- 里程碑礼物：亲密度累计到 5、15、30、50、80、120、170、230 各送一份，一只一只各算各的，永不重置。
  由低到高：一小包金币 → 几件收藏品 → 它的专属头像框（直接变成「已拥有」）→ ……
"""
import hashlib
import math

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_user
from ..catalog import KEEPSAKE_AT, KEEPSAKES, SHOP_ITEMS
from ..coins import spend, today
from ..db import get_db
from ..islet import KEEPS, bag_view, feed_gain, give, item_info, kind_of, name_of, take
from ..models import CoinEntry, Owned, PetBond, PetMemo, User

router = APIRouter()

# 编号 → (名字, 种类)
PETS = {
    "teddy": ("栗子", "dog"),
    "shiba": ("年糕", "dog"),
    "cotton": ("棉花", "dog"),
    "tangerine": ("橘子", "cat"),
    "tangyuan": ("汤圆", "cat"),
    "huajuan": ("花卷", "cat"),
    "zhima": ("芝麻", "dog"),
    "tuanzi": ("团子", "dog"),
    "momo": ("墨墨", "cat"),
    "doubao": ("豆包", "cat"),
}
# 每只的最爱（鱼或口粮的编号）：猫偏爱鱼，狗偏爱骨头和大鱼，各有不同
FAVORITES: dict[str, tuple[str, ...]] = {
    "teddy": ("food_bone", "bass", "food_kibble"),
    "shiba": ("food_bone", "mandarin", "crucian"),
    "cotton": ("food_kibble", "whitebait", "shrimp"),
    "tangerine": ("crucian", "food_dried_fish", "carp_gold"),
    "tangyuan": ("silver", "food_cream", "moon"),
    "huajuan": ("shrimp", "food_cream", "whitebait"),
    "zhima": ("food_bone", "crab", "loach"),
    "tuanzi": ("food_kibble", "bass", "food_bone"),
    "momo": ("moon", "loach", "food_dried_fish"),
    "doubao": ("crab", "food_cream", "crucian"),
}
# 每只会叼来的收藏品（按性格分）。第一样是它最常叼的，里程碑送收藏品也从这里取
GIFTS: dict[str, tuple[str, ...]] = {
    "teddy": ("bone", "stick", "pinecone", "knot"),
    "shiba": ("stick", "pinecone", "maple", "bell"),
    "cotton": ("flower", "clover", "feather", "knot"),
    "tangerine": ("dried_fish", "shell", "yarn", "pearl"),
    "tangyuan": ("shell", "shell_conch", "feather", "pearl"),
    "huajuan": ("flower", "ginkgo", "yarn", "clover"),
    "zhima": ("stick", "pebble", "bone", "ginkgo"),
    "tuanzi": ("bone", "bell", "pebble", "maple"),
    "momo": ("dried_fish", "feather", "pebble", "pearl"),
    "doubao": ("shell", "shell_conch", "yarn", "knot"),
}

LEVELS = (0, 3, 10, 25, 60, 120)           # 亲密度到多少升一档。前四个不能动
LEVEL_NAMES = ("陌生", "认识", "亲近", "最好的朋友", "知己", "家人")
PET_DAILY = 3                              # 每天摸几次算亲密度
FEED_DAILY = 5                             # 每天喂几次算亲密度
PET_GAIN, FEED_GAIN = 1, 2                 # 摸一下、喂一把普通口粮各涨多少
FEED_COST = 2                              # 喂一把普通口粮花多少金币
FAVORITE_RATE = 1.5                        # 喂到最爱的乘几（向上取整）

GIFT_LEVEL = 2                             # 到哪一档开始有每日礼物
GIFT_CHANCE = 0.5                          # 刚到那一档时每天有礼物的机会；再高一档起每天必有
# 每日礼物按稀有度的权重：等级 → (常见, 少见, 稀有)。越熟越可能给稀有的
GIFT_RARITY_WEIGHTS = {2: (60, 32, 8), 3: (50, 34, 16), 4: (40, 35, 25), 5: (30, 35, 35)}

# 里程碑：(亲密度门槛, 种类, 内容)
# - coins：一包金币，内容是几个
# - items：几件收藏品，内容是 ((它会叼的第几样 或 收藏品编号, 几个), ...)
# - frame：它的专属头像框（catalog.KEEPSAKES 里 pet 是它的那件），门槛必须等于 catalog.KEEPSAKE_AT
MILESTONES: tuple[tuple[int, str, object], ...] = (
    (5, "coins", 10),
    (15, "items", ((0, 2),)),
    (30, "coins", 30),
    (KEEPSAKE_AT, "frame", None),
    (80, "items", ((1, 2), (2, 2))),
    (120, "coins", 80),
    (170, "items", (("pearl", 1), ("knot", 1))),
    (230, "coins", 200),
)
PET_FRAME = {src["pet"]: item for item, src in KEEPSAKES.items() if "pet" in src}


def level_of(affinity: int) -> int:
    return max(i for i, need in enumerate(LEVELS) if affinity >= need)


def _roll(user_id: int, pet: str, salt: str) -> float:
    """同一个人、同一只、同一天，结果固定（刷新不会变）"""
    h = hashlib.sha256(f"{user_id}:{pet}:{today().isoformat()}:{salt}".encode()).digest()
    return int.from_bytes(h[:4], "big") / 2**32


def _bond(db: Session, me: User, pet: str, create: bool = False) -> PetBond | None:
    b = db.scalar(select(PetBond).where(PetBond.user_id == me.id, PetBond.pet == pet))
    if b is None and create:
        b = PetBond(user_id=me.id, pet=pet, affinity=0, pets_today=0, feeds_today=0)
        db.add(b)
    if b is not None and b.day != today():
        b.day = today()
        b.pets_today = 0
        b.feeds_today = 0
    return b


def _memo(db: Session, me: User, pet: str, create: bool = False) -> PetMemo | None:
    m = db.get(PetMemo, (me.id, pet))
    if m is None and create:
        m = PetMemo(user_id=me.id, pet=pet, milestones=0, favs="", gifts_seen="")
        db.add(m)
        db.flush()
    return m


def _ids(text: str | None) -> list[str]:
    return [x for x in (text or "").split(",") if x]


def _remember(text: str, item: str) -> str:
    ids = _ids(text)
    return text if item in ids else ",".join([*ids, item])


# ───────── 每日礼物 ─────────
def _has_gift(me: User, pet: str, b: PetBond | None) -> bool:
    if b is None or b.gift_day == today():
        return False
    lv = level_of(b.affinity)
    return lv > GIFT_LEVEL or (lv == GIFT_LEVEL and _roll(me.id, pet, "gift") < GIFT_CHANCE)


def gift_weights(pet: str, level: int) -> dict[str, float]:
    """这只动物在这个等级，每样收藏品被叼来的权重：先按稀有度分，同一稀有度的几样平分"""
    by = dict(zip(("common", "uncommon", "rare"), GIFT_RARITY_WEIGHTS[max(GIFT_LEVEL, min(level, max(GIFT_RARITY_WEIGHTS)))]))
    kinds = GIFTS[pet]
    return {k: by[KEEPS[k][1]] / sum(1 for x in kinds if KEEPS[x][1] == KEEPS[k][1]) for k in kinds}


def _gift_item(me: User, pet: str, b: PetBond) -> str:
    """今天它叼来的是哪一样（同一天固定）"""
    w = gift_weights(pet, level_of(b.affinity))
    at = _roll(me.id, pet, "what") * sum(w.values())
    for item, weight in w.items():
        at -= weight
        if at < 0:
            return item
    return GIFTS[pet][0]


# ───────── 里程碑 ─────────
def _milestone_view(pet: str, i: int) -> dict:
    """第 i 个里程碑送的是什么"""
    at, kind, what = MILESTONES[i]
    out = {"at": at, "kind": kind, "coins": 0, "items": [], "item_id": None}
    if kind == "coins":
        out["coins"] = what
        out["what"] = f"一包金币（{what} 个）"
    elif kind == "items":
        for ref, n in what:
            item = GIFTS[pet][ref] if isinstance(ref, int) else ref
            out["items"].append({"id": item, "name": KEEPS[item][0], "rarity": KEEPS[item][1], "count": n})
        out["what"] = "、".join(f"{x['name']} ×{x['count']}" for x in out["items"])
    else:
        out["item_id"] = PET_FRAME[pet]
        out["what"] = SHOP_ITEMS[PET_FRAME[pet]][0]
    return out


def _grant_milestones(db: Session, me: User, pet: str, b: PetBond) -> list[dict]:
    """亲密度跨过了哪些还没送过礼物的门槛，就把礼物都发了。一次可能跨好几个。不提交事务"""
    m = _memo(db, me, pet, create=True)
    name = PETS[pet][0]
    out = []
    while m.milestones < len(MILESTONES) and b.affinity >= MILESTONES[m.milestones][0]:
        g = _milestone_view(pet, m.milestones)
        if g["kind"] == "coins":
            me.coins += g["coins"]
            db.add(CoinEntry(user_id=me.id, amount=g["coins"], kind="pet_gift", what=f"{name}送的一包金币", day=today()))
        elif g["kind"] == "items":
            for x in g["items"]:
                give(db, me, x["id"], x["count"])
        elif db.get(Owned, (me.id, g["item_id"])) is None:
            # 专属头像框：直接算已拥有，不自动戴上（免得悄悄换掉正戴着的）
            db.add(Owned(user_id=me.id, item_id=g["item_id"]))
            db.flush()
        m.milestones += 1
        out.append(g)
    return out


def _milestone_text(pet: str, got: list[dict]) -> str:
    """这次跨过的里程碑，写成一句能直接给人看的话"""
    name = PETS[pet][0]
    parts = []
    for g in got:
        if g["kind"] == "coins":
            parts.append(f"{name}送了你{g['what']}")
        elif g["kind"] == "items":
            parts.append(f"{name}送了你{g['what']}，已经放进背包")
        else:
            parts.append(f"{name}送了你「{g['what']}」，已经放进商城的「小动物的礼物」里了")
    return "；".join(parts)


def _milestones_brief(pet: str, m: PetMemo | None) -> dict:
    got = m.milestones if m else 0
    nxt = _milestone_view(pet, got) if got < len(MILESTONES) else None
    return {"got": got, "total": len(MILESTONES), "next": nxt["at"] if nxt else None, "next_what": nxt["what"] if nxt else None}


# ───────── 给界面看的样子 ─────────
def _view(me: User, pet: str, b: PetBond | None, m: PetMemo | None) -> dict:
    name, kind = PETS[pet]
    aff = b.affinity if b else 0
    lv = level_of(aff)
    nxt = LEVELS[lv + 1] if lv + 1 < len(LEVELS) else None
    gift = _gift_item(me, pet, b) if _has_gift(me, pet, b) else None
    known = _ids(m.favs) if m else []
    return {
        "id": pet, "name": name, "kind": kind, "affinity": aff, "level": lv, "level_name": LEVEL_NAMES[lv], "next": nxt,
        "pets_left": max(0, PET_DAILY - (b.pets_today if b else 0)),
        "feeds_left": max(0, FEED_DAILY - (b.feeds_today if b else 0)),
        # 今天它要不要跑来迎接（亲近以上，一天一次）、有没有礼物（gift 是「一枚贝壳」这样的说法，gift_item 是收藏品编号）
        "greet": bool(b) and lv >= 2 and b.greet_day != today(),
        "gift": KEEPS[gift][4] if gift else None,
        "gift_item": gift,
        # 最爱：favorites 是全部，favorites_known 是已经喂出来的（没喂到过的界面上先显示成「？」）
        "favorites": list(FAVORITES[pet]),
        "favorites_known": [f for f in FAVORITES[pet] if f in known],
        "milestones": _milestones_brief(pet, m),
    }


@router.get("/pets")
def pets(me: User = Depends(current_user), db: Session = Depends(get_db)):
    """上岛时取：每只和我有多熟、今天谁来迎接、谁有礼物。取的时候就记下「今天迎接过了」"""
    out = []
    for pet in PETS:
        b = _bond(db, me, pet)
        v = _view(me, pet, b, _memo(db, me, pet))
        out.append(v)
        if v["greet"]:
            b.greet_day = today()
    db.commit()
    return {"pets": out, "feed_cost": FEED_COST, "coins": me.coins}


@router.get("/pets/gifts")
def gift_book(me: User = Depends(current_user), db: Session = Depends(get_db)):
    """礼物册：每只动物的里程碑礼物送到哪儿了、下一个门槛是多少、每日礼物收过哪几种"""
    out = []
    for pet in PETS:
        b = _bond(db, me, pet)
        m = _memo(db, me, pet)
        v = _view(me, pet, b, m)
        got = m.milestones if m else 0
        seen = _ids(m.gifts_seen) if m else []
        out.append({
            **{k: v[k] for k in ("id", "name", "kind", "affinity", "level", "level_name", "next", "favorites", "favorites_known")},
            "frame": PET_FRAME.get(pet),
            "milestones": [{**_milestone_view(pet, i), "done": i < got} for i in range(len(MILESTONES))],
            "next_milestone": MILESTONES[got][0] if got < len(MILESTONES) else None,
            # 每日礼物：它会叼来的几样，seen 是收到过没有
            "daily": [{"id": k, "name": KEEPS[k][0], "rarity": KEEPS[k][1], "seen": k in seen} for k in GIFTS[pet]],
        })
    db.rollback()  # _bond 可能顺手把「今天」的计数清了零，这里只是看，不写
    # names：最爱里出现的鱼和口粮叫什么，界面不用自己再存一份
    names = {f: name_of(f) for favs in FAVORITES.values() for f in favs}
    return {"pets": out, "names": names}


def _pet(pet: str) -> str:
    if pet not in PETS:
        raise HTTPException(404, "没有这只小动物")
    return pet


def _after(db: Session, me: User, pet: str, b: PetBond, before: int, counted: bool, gain: int) -> dict:
    """摸完、喂完共用的收尾：发里程碑礼物、提交、拼返回"""
    got = _grant_milestones(db, me, pet, b)
    db.commit()
    return {
        **_view(me, pet, b, _memo(db, me, pet)),
        "counted": counted, "gain": gain, "level_up": level_of(b.affinity) > before, "coins": me.coins,
        # milestone：这次跨过的里程碑，没有是 null。跨了好几个时是最高的那个，但 coins 是这次一共送的金币、
        # text 是把这次送的全说一遍的一句话；milestones_new 是这次跨过的全部，一个一个分开
        "milestone": {**got[-1], "coins": sum(g["coins"] for g in got), "text": _milestone_text(pet, got)} if got else None,
        "milestones_new": got,
        # 背包现在的样子（喂掉了东西、里程碑送了收藏品，界面直接拿这个换）
        "items": bag_view(db, me),
    }


@router.post("/pets/{pet}/pet")
def stroke(pet: str, me: User = Depends(current_user), db: Session = Depends(get_db)):
    b = _bond(db, me, _pet(pet), create=True)
    before = level_of(b.affinity)
    counted = b.pets_today < PET_DAILY
    if counted:
        b.pets_today += 1
        b.affinity += PET_GAIN
    return _after(db, me, pet, b, before, counted, PET_GAIN if counted else 0)


class FeedIn(BaseModel):
    # 背包里的鱼或口粮的编号；不带就是花金币喂一把普通口粮
    item: str | None = Field(default=None, max_length=24)


def _reaction(pet: str, favorite: bool, counted: bool) -> str:
    name, kind = PETS[pet]
    if favorite:
        return f"{name}眼睛都亮了，吃得呼噜呼噜的" if kind == "cat" else f"{name}眼睛都亮了，尾巴摇成了小风车"
    if not counted:
        return f"{name}吃得很香。今天它已经吃饱了，亲密度明天再涨"
    return f"{name}吃得很香"


@router.post("/pets/{pet}/feed")
def feed(pet: str, body: FeedIn | None = Body(default=None), me: User = Depends(current_user), db: Session = Depends(get_db)):
    b = _bond(db, me, _pet(pet), create=True)
    item = body.item if body else None
    favorite = False
    if item is None:
        if not spend(db, me, FEED_COST, f"喂{PETS[pet][0]}"):
            raise HTTPException(400, "金币不够了")
        gain = FEED_GAIN
    else:
        if kind_of(item) is None:
            raise HTTPException(404, "没有这样东西")
        gain = feed_gain(item)
        if gain <= 0:
            raise HTTPException(400, f"{PETS[pet][0]}闻了闻，不吃{name_of(item)}")
        if not take(db, me, item):
            raise HTTPException(400, f"背包里没有{name_of(item)}了")
        favorite = item in FAVORITES[pet]
        if favorite:
            gain = math.ceil(gain * FAVORITE_RATE)
            m = _memo(db, me, pet, create=True)
            m.favs = _remember(m.favs, item)
    before = level_of(b.affinity)
    counted = b.feeds_today < FEED_DAILY
    if counted:
        b.feeds_today += 1
        b.affinity += gain
    out = _after(db, me, pet, b, before, counted, gain if counted else 0)
    return {**out, "favorite": favorite, "reaction": _reaction(pet, favorite, counted), "item": item}


@router.post("/pets/{pet}/gift")
def gift(pet: str, me: User = Depends(current_user), db: Session = Depends(get_db)):
    """收下它叼来的礼物：一件收藏品，进背包。一只一天一件。got 一直是 0（老版本拿它当金币数）"""
    b = _bond(db, me, _pet(pet))
    if not _has_gift(me, pet, b):
        return {"got": 0, "coins": me.coins, "item": None}
    item = _gift_item(me, pet, b)
    b.gift_day = today()
    count = give(db, me, item)
    m = _memo(db, me, pet, create=True)
    m.gifts_seen = _remember(m.gifts_seen, item)
    db.commit()
    info = item_info(item)
    return {
        "got": 0, "coins": me.coins, "name": PETS[pet][0], "what": KEEPS[item][4], "count": count,
        "item": {k: info[k] for k in ("id", "name", "about", "rarity")},
        "items": bag_view(db, me),
    }
