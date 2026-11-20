"""账号、个人资料、心愿、愿景板、终点密码、肯定语、宠物、金币、商城、会员。"""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import coins as coinlib
from ..auth import current_user, make_token
from ..catalog import COIN_RULES, KEEPSAKE_AT, KEEPSAKES, LOOK_MODES, POST_TYPES, SCENES, SHOP_ITEMS, SKINS
from ..config import settings
from ..db import get_db
from ..islet import FOODS, KEEPS, STACK_MAX, bag_view, give, have, take
from ..models import Affirmation, Destiny, Owned, Pet, Post, User, VisionItem, Wish, now
from ..moderation import check_public
from ..views import me_view, ms, state

router = APIRouter()


class DeviceLogin(BaseModel):
    device_id: str = Field(min_length=8, max_length=64)


@router.post("/auth/device")
def login_device(body: DeviceLogin, db: Session = Depends(get_db)):
    """免注册登录：同一台设备永远是同一个账号。返回 new=true 表示刚建的号（应用可以把本机旧数据导进来）。"""
    user = db.scalar(select(User).where(User.device_id == body.device_id))
    new = user is None
    if new:
        user = User(device_id=body.device_id)
        db.add(user)
        db.commit()
    elif user.banned:
        raise HTTPException(403, "账号不可用")
    return {"token": make_token(user.id), "new": new, "user": me_view(db, user)}


@router.get("/me/state")
def get_state(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return state(db, user)


class ProfilePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=24)
    sign: str | None = Field(default=None, max_length=60)
    avatar: str | None = Field(default=None, max_length=200)
    skin: str | None = None
    look_mode: str | None = None
    look_dynamic: bool | None = None


@router.patch("/me")
def patch_me(body: ProfilePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.name is not None or body.sign is not None:
        problem = check_public(f"{body.name or ''} {body.sign or ''}")
        if problem:
            raise HTTPException(400, "名字和签名会公开显示，" + problem.split("，", 1)[-1])
    if body.skin is not None:
        if body.skin not in SKINS:
            raise HTTPException(400, "没有这套皮肤")
        if SKINS[body.skin] and not user.member:
            raise HTTPException(403, "这是会员皮肤")
        user.skin_id = body.skin
    if body.look_mode is not None:
        if body.look_mode not in LOOK_MODES:
            raise HTTPException(400, "没有这种形象")
        user.look_mode = body.look_mode
    for k in ("name", "sign", "look_dynamic"):
        v = getattr(body, k)
        if v is not None:
            setattr(user, k, v.strip() if isinstance(v, str) else v)
    if body.avatar is not None:
        user.avatar_url = body.avatar or None
    db.commit()
    return me_view(db, user)


# ───────── 心愿 ─────────
class WishIn(BaseModel):
    scene: str
    text: str = Field(min_length=1, max_length=200)


@router.post("/wishes")
def add_wish(body: WishIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.scene not in SCENES:
        raise HTTPException(400, "没有这个分类")
    w = Wish(user_id=user.id, scene=body.scene, text=body.text.strip())
    db.add(w)
    got = coinlib.earn(db, user, "wish")
    db.commit()
    return {"wish": {"id": w.id, "scene": w.scene, "text": w.text, "ts": ms(w.created_at)}, "got": got, "coins": user.coins}


@router.delete("/wishes/{wish_id}")
def del_wish(wish_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(Wish).where(Wish.id == wish_id, Wish.user_id == user.id))
    db.commit()
    return {"ok": True}


# ───────── 金币 ─────────
@router.post("/checkin")
def checkin(user: User = Depends(current_user), db: Session = Depends(get_db)):
    got = coinlib.earn(db, user, "checkin")
    db.commit()
    return {"got": got, "streak": user.streak, "coins": user.coins}


@router.get("/coins/rules")
def coin_rules():
    return {k: {"amount": a, "cap": c, "what": w} for k, (a, c, w) in COIN_RULES.items()}


# ───────── 商城和会员 ─────────
class ItemIn(BaseModel):
    item_id: str
    on: bool = True


@router.post("/shop/buy")
def buy(body: ItemIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = SHOP_ITEMS.get(body.item_id)
    if item is None:
        raise HTTPException(404, "没有这件商品")
    name, price, group, member_only = item
    if db.get(Owned, (user.id, body.item_id)) is not None:
        raise HTTPException(409, "已经有了")
    if body.item_id in KEEPSAKES:
        raise HTTPException(403, f"「{name}」不卖，{keepsake_source(body.item_id)}")
    if member_only:
        if not user.member:
            raise HTTPException(403, f"「{name}」是会员限定")
    elif group == "meditation" and user.member:
        pass  # 会员不用花金币
    elif not coinlib.spend(db, user, price, f"购买「{name}」" if group != "meditation" else f"解锁{name}"):
        raise HTTPException(402, f"金币不够，还差 {price - user.coins} 个")
    db.add(Owned(user_id=user.id, item_id=body.item_id))
    db.flush()
    if group in ("room", "frame", "pet"):
        _equip(db, user, body.item_id, True)
    db.commit()
    return _shop_state(db, user)


@router.post("/shop/equip")
def equip(body: ItemIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.get(Owned, (user.id, body.item_id)) is None:
        raise HTTPException(404, "还没有这件")
    _equip(db, user, body.item_id, body.on)
    db.commit()
    return _shop_state(db, user)


def keepsake_source(item_id: str) -> str:
    """一件小动物的礼物怎么得到，写成一句话"""
    src = KEEPSAKES[item_id]
    if "pet" in src:
        from .pets import PETS  # 放在这里引，免得两个路由文件互相引

        return f"和{PETS[src['pet']][0]}的亲密度到 {KEEPSAKE_AT} 时它会送给你"
    return "要用" + " + ".join(f"{n} {KEEPS[k][0]}" for k, n in src["cost"].items()) + "兑换"


class StackIn(BaseModel):
    item_id: str
    count: int = Field(default=1, ge=1, le=99)


@router.post("/shop/buy_stack")
def buy_stack(body: StackIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """买可以叠加的东西（小寺的口粮）：买的是数量，放进背包"""
    food = FOODS.get(body.item_id)
    if food is None:
        raise HTTPException(404, "没有这件商品")
    name, _, price, _ = food
    if have(db, user, body.item_id) + body.count > STACK_MAX:
        raise HTTPException(400, f"背包里的{name}放不下了")
    total = price * body.count
    if not coinlib.spend(db, user, total, f"购买{name} ×{body.count}"):
        raise HTTPException(402, f"金币不够，还差 {total - user.coins} 个")
    count = give(db, user, body.item_id, body.count)
    db.commit()
    return {"coins": user.coins, "item_id": body.item_id, "count": count, "items": bag_view(db, user)}


@router.post("/shop/redeem")
def redeem(body: ItemIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """用收藏品兑换一件小动物的礼物：扣收藏品，变成已拥有并戴上"""
    src = KEEPSAKES.get(body.item_id)
    if src is None:
        raise HTTPException(404, "没有这件东西")
    name = SHOP_ITEMS[body.item_id][0]
    if db.get(Owned, (user.id, body.item_id)) is not None:
        raise HTTPException(409, "已经有了")
    if "cost" not in src:
        raise HTTPException(403, f"「{name}」换不了，{keepsake_source(body.item_id)}")
    short = [f"{KEEPS[k][0]}还差 {n - have(db, user, k)} 个" for k, n in src["cost"].items() if have(db, user, k) < n]
    if short:
        raise HTTPException(400, "材料不够：" + "，".join(short))
    for k, n in src["cost"].items():
        take(db, user, k, n)
    db.add(Owned(user_id=user.id, item_id=body.item_id))
    db.flush()
    _equip(db, user, body.item_id, True)
    db.commit()
    return {**_shop_state(db, user), "items": bag_view(db, user)}


def _equip(db: Session, user: User, item_id: str, on: bool) -> None:
    if on and SHOP_ITEMS[item_id][2] == "frame":
        for o in db.scalars(select(Owned).where(Owned.user_id == user.id, Owned.item_id.startswith("frame_"))):
            o.equipped = False
    db.get(Owned, (user.id, item_id)).equipped = on


def _shop_state(db: Session, user: User) -> dict:
    owned = db.scalars(select(Owned).where(Owned.user_id == user.id)).all()
    return {"coins": user.coins, "owned": [o.item_id for o in owned], "equipped": [o.item_id for o in owned if o.equipped]}


class DemoMember(BaseModel):
    on: bool


@router.post("/membership/demo")
def demo_member(body: DemoMember, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """没接苹果内购前的演示开关。正式环境 YJ_DEMO_MEMBERSHIP=0 关掉，会员只能由内购回调开通。"""
    if not settings.demo_membership:
        raise HTTPException(403, "请通过应用内购买开通会员")
    user.member_until = now() + timedelta(days=30) if body.on else None
    if not body.on and SKINS.get(user.skin_id):
        user.skin_id = "gold"
    db.commit()
    return me_view(db, user)


# ───────── 愿景板 ─────────
class VisionIn(BaseModel):
    text: str = Field(default="", max_length=60)
    scene: str
    photo: str | None = Field(default=None, max_length=200)


@router.post("/vision")
def add_vision(body: VisionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.scene not in SCENES:
        raise HTTPException(400, "没有这个分类")
    if not body.text.strip() and not body.photo:
        raise HTTPException(400, "写个关键词，或者配一张图")
    v = VisionItem(user_id=user.id, text=body.text.strip(), scene=body.scene, photo_url=body.photo)
    db.add(v)
    db.commit()
    return {"id": v.id, "text": v.text, "scene": v.scene, "photo": v.photo_url}


@router.delete("/vision/{item_id}")
def del_vision(item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(VisionItem).where(VisionItem.id == item_id, VisionItem.user_id == user.id))
    db.commit()
    return {"ok": True}


# ───────── 终点密码 ─────────
class DestinyIn(BaseModel):
    text: str = Field(max_length=2000)


@router.put("/destiny/{scene}")
def put_destiny(scene: str, body: DestinyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if scene not in SCENES:
        raise HTTPException(400, "没有这个分类")
    row = db.get(Destiny, (user.id, scene))
    if not body.text.strip():
        if row is not None:
            db.delete(row)
    elif row is None:
        db.add(Destiny(user_id=user.id, scene=scene, text=body.text))
    else:
        row.text = body.text
        row.updated_at = now()
    db.commit()
    return {"ok": True}


# ───────── 肯定语 ─────────
class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)


@router.post("/affirmations")
def add_affirmation(body: TextIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = Affirmation(user_id=user.id, text=body.text.strip())
    db.add(a)
    db.commit()
    return {"id": a.id, "text": a.text}


@router.delete("/affirmations/{item_id}")
def del_affirmation(item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(Affirmation).where(Affirmation.id == item_id, Affirmation.user_id == user.id))
    db.commit()
    return {"ok": True}


# ───────── 宠物 ─────────
class PetIn(BaseModel):
    name: str = Field(min_length=1, max_length=16)
    kind: str = Field(default="狗狗", max_length=8)
    photo: str | None = Field(default=None, max_length=200)


@router.post("/pets")
def add_pet(body: PetIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = Pet(user_id=user.id, name=body.name.strip(), kind=body.kind, photo_url=body.photo)
    db.add(p)
    db.commit()
    return {"id": p.id, "name": p.name, "kind": p.kind, "photo": p.photo_url}


class PetPatch(BaseModel):
    photo: str | None = Field(default=None, max_length=200)


@router.patch("/pets/{pet_id}")
def patch_pet(pet_id: int, body: PetPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(Pet, pet_id)
    if p is None or p.user_id != user.id:
        raise HTTPException(404, "没有这只宠物")
    p.photo_url = body.photo
    db.commit()
    return {"id": p.id, "name": p.name, "kind": p.kind, "photo": p.photo_url}


@router.delete("/pets/{pet_id}")
def del_pet(pet_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(Pet).where(Pet.id == pet_id, Pet.user_id == user.id))
    db.commit()
    return {"ok": True}


# ───────── 把本机旧数据搬上来 ─────────
class ImportIn(BaseModel):
    wishes: list[dict] = []
    vision: list[dict] = []
    destiny: dict[str, str] = {}
    affirmations: list[str] = []
    pets: list[dict] = []
    posts: list[dict] = []
    profile: dict = {}


@router.post("/me/import")
def import_local(body: ImportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """只给空账号用一次：把接后端之前存在手机上的内容搬上来。金币和买过的东西不搬（本机的数不可信）。"""
    has = any(db.scalar(select(m.id).where(m.user_id == user.id).limit(1)) for m in (Wish, VisionItem, Affirmation, Post))
    if has:
        raise HTTPException(409, "这个账号已经有数据了")
    from datetime import datetime, timezone

    def when(item) -> datetime:
        ts = item.get("ts")
        return datetime.fromtimestamp(ts / 1000, timezone.utc) if isinstance(ts, (int, float)) else now()

    for w in body.wishes[:500]:
        if w.get("scene") in SCENES and str(w.get("text", "")).strip():
            db.add(Wish(user_id=user.id, scene=w["scene"], text=str(w["text"])[:200], created_at=when(w)))
    for v in body.vision[:200]:
        if v.get("scene") in SCENES:
            db.add(VisionItem(user_id=user.id, text=str(v.get("text", ""))[:60], scene=v["scene"], photo_url=v.get("photo")))
    for scene, text in body.destiny.items():
        if scene in SCENES and text.strip():
            db.add(Destiny(user_id=user.id, scene=scene, text=text[:2000]))
    for a in body.affirmations[:200]:
        if a.strip():
            db.add(Affirmation(user_id=user.id, text=a[:300]))
    if body.pets:
        db.execute(delete(Pet).where(Pet.user_id == user.id))
        for p in body.pets[:20]:
            if str(p.get("name", "")).strip():
                db.add(Pet(user_id=user.id, name=str(p["name"])[:16], kind=str(p.get("kind", "狗狗"))[:8], photo_url=p.get("photo")))
    for p in body.posts[:200]:
        if p.get("type") in POST_TYPES and str(p.get("text", "")).strip():
            text = str(p["text"])
            public = bool(p.get("public")) and check_public(text) is None
            db.add(Post(user_id=user.id, type=p["type"], text=text[:2000], public=public, created_at=when(p)))
    prof = body.profile
    if isinstance(prof.get("name"), str) and prof["name"].strip() and check_public(prof["name"]) is None:
        user.name = prof["name"].strip()[:24]
    if isinstance(prof.get("sign"), str) and check_public(prof["sign"]) is None:
        user.sign = prof["sign"][:60]
    if prof.get("look_mode") in LOOK_MODES:
        user.look_mode = prof["look_mode"]
    if prof.get("skin") in SKINS and not SKINS[prof["skin"]]:
        user.skin_id = prof["skin"]
    db.commit()
    return state(db, user)
