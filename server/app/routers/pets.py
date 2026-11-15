"""湖心小寺的小动物：摸、喂、交情、迎接、礼物。

规则（都在这个文件开头，好改）：
- 六只有名字的：三只狗三只猫。每个人和每一只各有一份交情。
- 摸一下 +1，喂一次 +2（喂要花金币）。每只每天摸、喂各只有前 3 次涨交情，多了照样能摸能喂，只是不涨。
- 交情分四档：陌生、认识、亲近、最好的朋友。到「亲近」它每天第一次见你会跑来迎接，并有机会叼一件礼物；
  「最好的朋友」每天必有礼物，而且整趟都跟着你。
- 礼物换成金币，一只一天一件。
"""
import hashlib

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_user
from ..coins import spend, today
from ..db import get_db
from ..models import CoinEntry, PetBond, User

router = APIRouter()

# 编号 → (名字, 种类, 它会叼来什么)
PETS = {
    "teddy": ("栗子", "dog", "一根骨头"),
    "shiba": ("年糕", "dog", "一根捡来的树枝"),
    "cotton": ("棉花", "dog", "一朵小花"),
    "tangerine": ("橘子", "cat", "一条小鱼"),
    "tangyuan": ("汤圆", "cat", "一枚贝壳"),
    "huajuan": ("花卷", "cat", "一朵小花"),
    "zhima": ("芝麻", "dog", "一根捡来的树枝"),
    "tuanzi": ("团子", "dog", "一根骨头"),
    "momo": ("墨墨", "cat", "一条小鱼"),
    "doubao": ("豆包", "cat", "一枚贝壳"),
}
LEVELS = (0, 3, 10, 25)                    # 交情到多少升一档
LEVEL_NAMES = ("陌生", "认识", "亲近", "最好的朋友")
DAILY = 3                                  # 每天摸、喂各算几次
PET_GAIN, FEED_GAIN = 1, 2
FEED_COST = 2                              # 喂一次花多少金币
GIFT_COINS = (4, 9)                        # 礼物值多少金币（最少、最多）


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


def _has_gift(me: User, pet: str, b: PetBond | None) -> bool:
    if b is None or b.gift_day == today():
        return False
    lv = level_of(b.affinity)
    return lv >= 3 or (lv == 2 and _roll(me.id, pet, "gift") < 0.5)


def _view(me: User, pet: str, b: PetBond | None) -> dict:
    name, kind, gift = PETS[pet]
    aff = b.affinity if b else 0
    lv = level_of(aff)
    nxt = LEVELS[lv + 1] if lv + 1 < len(LEVELS) else None
    return {
        "id": pet, "name": name, "kind": kind, "affinity": aff, "level": lv, "level_name": LEVEL_NAMES[lv], "next": nxt,
        "pets_left": DAILY - (b.pets_today if b else 0) if (b.pets_today if b else 0) < DAILY else 0,
        "feeds_left": DAILY - (b.feeds_today if b else 0) if (b.feeds_today if b else 0) < DAILY else 0,
        # 今天它要不要跑来迎接（亲近以上，一天一次）、有没有礼物
        "greet": bool(b) and lv >= 2 and b.greet_day != today(),
        "gift": gift if _has_gift(me, pet, b) else None,
    }


@router.get("/pets")
def pets(me: User = Depends(current_user), db: Session = Depends(get_db)):
    """上岛时取：每只和我有多熟、今天谁来迎接、谁有礼物。取的时候就记下「今天迎接过了」"""
    out = []
    for pet in PETS:
        b = _bond(db, me, pet)
        v = _view(me, pet, b)
        out.append(v)
        if v["greet"]:
            b.greet_day = today()
    db.commit()
    return {"pets": out, "feed_cost": FEED_COST, "coins": me.coins}


def _pet(pet: str) -> str:
    if pet not in PETS:
        raise HTTPException(404, "没有这只小动物")
    return pet


@router.post("/pets/{pet}/pet")
def stroke(pet: str, me: User = Depends(current_user), db: Session = Depends(get_db)):
    b = _bond(db, me, _pet(pet), create=True)
    before = level_of(b.affinity)
    counted = b.pets_today < DAILY
    if counted:
        b.pets_today += 1
        b.affinity += PET_GAIN
    db.commit()
    return {**_view(me, pet, b), "counted": counted, "level_up": level_of(b.affinity) > before}


@router.post("/pets/{pet}/feed")
def feed(pet: str, me: User = Depends(current_user), db: Session = Depends(get_db)):
    b = _bond(db, me, _pet(pet), create=True)
    if not spend(db, me, FEED_COST, f"喂{PETS[pet][0]}"):
        raise HTTPException(400, "金币不够了")
    before = level_of(b.affinity)
    counted = b.feeds_today < DAILY
    if counted:
        b.feeds_today += 1
        b.affinity += FEED_GAIN
    db.commit()
    return {**_view(me, pet, b), "counted": counted, "level_up": level_of(b.affinity) > before, "coins": me.coins}


@router.post("/pets/{pet}/gift")
def gift(pet: str, me: User = Depends(current_user), db: Session = Depends(get_db)):
    """收下它叼来的礼物：换成金币。一只一天一件"""
    b = _bond(db, me, _pet(pet))
    if not _has_gift(me, pet, b):
        return {"got": 0, "coins": me.coins}
    lo, hi = GIFT_COINS
    got = lo + int(_roll(me.id, pet, "coins") * (hi - lo + 1))
    b.gift_day = today()
    me.coins += got
    name, _, what = PETS[pet]
    db.add(CoinEntry(user_id=me.id, amount=got, kind="pet_gift", what=f"{name}送的{what}", day=today()))
    db.commit()
    return {"got": got, "coins": me.coins, "what": what, "name": name}
