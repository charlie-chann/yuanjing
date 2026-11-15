"""把数据库里的东西变成接口返回的样子。时间一律是毫秒时间戳。"""
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ai import templates
from .coins import daily_counts, today
from .models import Affirmation, CoinEntry, Destiny, FriendRequest, Friendship, Owned, Pet, User, VisionItem, Wish


def ms(dt) -> int:
    return int(dt.timestamp() * 1000)


def title_of(db: Session, user: User) -> tuple[str, str]:
    if user.title:
        return user.title, ""
    scenes = db.scalars(select(Wish.scene).where(Wish.user_id == user.id)).all()
    top = Counter(scenes).most_common(1)[0][0] if scenes else None
    if top is None:
        top = db.scalar(select(Destiny.scene).where(Destiny.user_id == user.id))
    return templates.identity(top)


def brief(db: Session, u: User, me: User | None = None) -> dict:
    d = {"id": u.id, "name": u.name, "sign": u.sign, "avatar": u.avatar_url, "title": title_of(db, u)[0], "member": u.member}
    if me is not None and me.id != u.id:
        d["friend"] = db.get(Friendship, (me.id, u.id)) is not None
        d["requested"] = db.scalar(select(FriendRequest.id).where(FriendRequest.from_id == me.id, FriendRequest.to_id == u.id)) is not None
    return d


def me_view(db: Session, u: User) -> dict:
    t = title_of(db, u)
    return {
        "id": u.id,
        "name": u.name,
        "sign": u.sign,
        "avatar": u.avatar_url,
        "coins": u.coins,
        "member": u.member,
        "member_until": ms(u.member_until) if u.member_until else None,
        "skin": u.skin_id,
        "look_mode": u.look_mode,
        "look_dynamic": u.look_dynamic,
        "streak": u.streak,
        "checked_in": u.last_checkin == today(),
        "title": t[0],
        "title_line": t[1],
    }


def state(db: Session, u: User) -> dict:
    """应用启动时拉的全部数据"""
    owned = db.scalars(select(Owned).where(Owned.user_id == u.id)).all()
    friend_ids = db.scalars(select(Friendship.friend_id).where(Friendship.user_id == u.id)).all()
    requests = db.scalars(select(FriendRequest).where(FriendRequest.to_id == u.id).order_by(FriendRequest.id.desc())).all()
    dest = db.scalars(select(Destiny).where(Destiny.user_id == u.id)).all()
    return {
        "user": me_view(db, u),
        "wishes": [{"id": w.id, "scene": w.scene, "text": w.text, "ts": ms(w.created_at)} for w in db.scalars(select(Wish).where(Wish.user_id == u.id).order_by(Wish.id.desc()))],
        "vision": [{"id": v.id, "text": v.text, "scene": v.scene, "photo": v.photo_url} for v in db.scalars(select(VisionItem).where(VisionItem.user_id == u.id).order_by(VisionItem.id.desc()))],
        "destiny": {d.scene: d.text for d in dest},
        "destiny_ts": max((ms(d.updated_at) for d in dest), default=0),
        "affirmations": [{"id": a.id, "text": a.text} for a in db.scalars(select(Affirmation).where(Affirmation.user_id == u.id).order_by(Affirmation.id.desc()))],
        "pets": [{"id": p.id, "name": p.name, "kind": p.kind, "photo": p.photo_url} for p in db.scalars(select(Pet).where(Pet.user_id == u.id).order_by(Pet.id))],
        "owned": [o.item_id for o in owned],
        "equipped": [o.item_id for o in owned if o.equipped],
        "friends": [brief(db, f, u) for f in (db.get(User, i) for i in friend_ids) if f is not None],
        "requests": [{"id": r.id, "user": brief(db, db.get(User, r.from_id), u), "ts": ms(r.created_at)} for r in requests],
        "daily": daily_counts(db, u),
        "coin_log": [
            {"amount": c.amount, "what": c.what, "ts": ms(c.created_at)}
            for c in db.scalars(select(CoinEntry).where(CoinEntry.user_id == u.id).order_by(CoinEntry.id.desc()).limit(60))
        ],
    }
