"""愿望广场：动态、点赞、夸夸、举报、主页、好友、拉黑。没有私信，也没有自由评论。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from .. import coins as coinlib
from ..ai import llm, templates
from ..auth import current_user
from ..catalog import POST_TYPES, PRAISE_PRESETS, REPORT_HIDE_AT
from ..db import get_db
from ..models import Block, FriendRequest, Friendship, Like, Post, Praise, Report, User
from ..moderation import check_public
from ..views import brief, ms

router = APIRouter()


def _blocked_ids(db: Session, me: User) -> set[int]:
    """我拉黑的和拉黑我的，彼此看不见"""
    a = db.scalars(select(Block.blocked_id).where(Block.user_id == me.id)).all()
    b = db.scalars(select(Block.user_id).where(Block.blocked_id == me.id)).all()
    return set(a) | set(b)


def post_view(db: Session, p: Post, me: User) -> dict:
    praises = db.scalars(select(Praise).where(Praise.post_id == p.id).order_by(Praise.id)).all()
    return {
        "id": p.id,
        "type": p.type,
        "text": p.text,
        "public": p.public,
        "ts": ms(p.created_at),
        "mine": p.user_id == me.id,
        "user": brief(db, p.user, me),
        "likes": db.scalar(select(func.count()).select_from(Like).where(Like.post_id == p.id)) or 0,
        "liked": db.get(Like, (me.id, p.id)) is not None,
        "praises": [{"text": x.text, "ai": x.from_user_id is None, "mine": x.from_user_id == me.id} for x in praises],
    }


@router.get("/plaza")
def feed(
    filter: str = "all",
    before: int | None = Query(default=None, description="上一页最后一条的 id"),
    limit: int = Query(default=20, le=50),
    me: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = select(Post).where(Post.public.is_(True), Post.hidden.is_(False))
    blocked = _blocked_ids(db, me)
    if blocked:
        q = q.where(Post.user_id.not_in(blocked))
    if filter in POST_TYPES:
        q = q.where(Post.type == filter)
    elif filter == "friends":
        friends = select(Friendship.friend_id).where(Friendship.user_id == me.id)
        q = q.where(or_(Post.user_id == me.id, Post.user_id.in_(friends)))
    if before is not None:
        q = q.where(Post.id < before)
    posts = db.scalars(q.order_by(Post.id.desc()).limit(limit)).all()
    return {"items": [post_view(db, p, me) for p in posts], "next": posts[-1].id if len(posts) == limit else None}


@router.get("/me/posts")
def my_posts(me: User = Depends(current_user), db: Session = Depends(get_db)):
    posts = db.scalars(select(Post).where(Post.user_id == me.id).order_by(Post.id.desc())).all()
    return {"items": [post_view(db, p, me) for p in posts]}


class PostIn(BaseModel):
    type: str
    text: str = Field(min_length=1, max_length=2000)
    public: bool = True


@router.post("/posts")
def publish(body: PostIn, me: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.type not in POST_TYPES:
        raise HTTPException(400, "没有这种动态")
    text = body.text.strip()
    if body.public:
        problem = check_public(text)
        if problem:
            raise HTTPException(400, problem)
    p = Post(user_id=me.id, type=body.type, text=text, public=body.public)
    db.add(p)
    db.flush()
    got = coinlib.earn(db, me, "diary" if body.type == "diary" else "post")
    # 公开的内容马上收到一句 AI 夸夸，被夸的人也得金币
    if body.public:
        line = llm.complete("给用户刚发的一条正向动态写一句真诚的夸夸，20 个字以内，不要引号。", text, max_tokens=60)
        db.add(Praise(post_id=p.id, from_user_id=None, text=(line if isinstance(line, str) else templates.praise(text))[:60]))
        got += coinlib.earn(db, me, "praised")
    db.commit()
    return {"post": post_view(db, p, me), "got": got, "coins": me.coins}


@router.delete("/posts/{post_id}")
def delete_post(post_id: int, me: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(Post).where(Post.id == post_id, Post.user_id == me.id))
    db.commit()
    return {"ok": True}


def _visible_post(db: Session, post_id: int, me: User) -> Post:
    p = db.get(Post, post_id)
    if p is None or (p.user_id != me.id and (not p.public or p.hidden or p.user_id in _blocked_ids(db, me))):
        raise HTTPException(404, "这条动态不见了")
    return p


@router.post("/posts/{post_id}/like")
def toggle_like(post_id: int, me: User = Depends(current_user), db: Session = Depends(get_db)):
    """点一下赞，再点一下取消。取消再点不会重复发金币（每日上限按发放次数算）。"""
    p = _visible_post(db, post_id, me)
    row = db.get(Like, (me.id, post_id))
    got = 0
    if row is not None:
        db.delete(row)
    else:
        db.add(Like(user_id=me.id, post_id=post_id))
        if p.user_id != me.id:
            got = coinlib.earn(db, me, "like")
            coinlib.earn(db, p.user, "liked")
    db.commit()
    return {"liked": row is None, "likes": db.scalar(select(func.count()).select_from(Like).where(Like.post_id == post_id)), "got": got, "coins": me.coins}


class PraiseIn(BaseModel):
    text: str


@router.post("/posts/{post_id}/praise")
def praise(post_id: int, body: PraiseIn, me: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _visible_post(db, post_id, me)
    if body.text not in PRAISE_PRESETS:
        raise HTTPException(400, "只能选列出来的夸夸")
    if p.user_id == me.id:
        raise HTTPException(400, "不能夸自己的")
    exists = db.scalar(select(Praise.id).where(Praise.post_id == post_id, Praise.from_user_id == me.id, Praise.text == body.text))
    if exists:
        raise HTTPException(409, "这句已经夸过了")
    db.add(Praise(post_id=post_id, from_user_id=me.id, text=body.text))
    got = coinlib.earn(db, me, "praise")
    coinlib.earn(db, p.user, "praised")
    db.commit()
    return {"post": post_view(db, p, me), "got": got, "coins": me.coins}


class ReportIn(BaseModel):
    reason: str = Field(default="内容不友好", max_length=60)


@router.post("/posts/{post_id}/report")
def report(post_id: int, body: ReportIn, me: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _visible_post(db, post_id, me)
    if p.user_id == me.id:
        raise HTTPException(400, "不能举报自己的")
    if db.scalar(select(Report.id).where(Report.user_id == me.id, Report.post_id == post_id)) is None:
        db.add(Report(user_id=me.id, post_id=post_id, reason=body.reason))
        db.flush()
        if (db.scalar(select(func.count()).select_from(Report).where(Report.post_id == post_id)) or 0) >= REPORT_HIDE_AT:
            p.hidden = True
    db.commit()
    return {"ok": True}


@router.get("/users/{user_id}")
def profile(user_id: int, me: User = Depends(current_user), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None or u.banned or user_id in _blocked_ids(db, me):
        raise HTTPException(404, "找不到这个人")
    posts = db.scalars(
        select(Post).where(Post.user_id == user_id, Post.public.is_(True), Post.hidden.is_(False)).order_by(Post.id.desc()).limit(30)
    ).all()
    return {"user": brief(db, u, me), "posts": [post_view(db, p, me) for p in posts]}


# ───────── 好友 ─────────
def _befriend(db: Session, a: User, b: User) -> None:
    for x, y in ((a, b), (b, a)):
        if db.get(Friendship, (x.id, y.id)) is None:
            db.add(Friendship(user_id=x.id, friend_id=y.id))
    db.execute(delete(FriendRequest).where(or_((FriendRequest.from_id == a.id) & (FriendRequest.to_id == b.id), (FriendRequest.from_id == b.id) & (FriendRequest.to_id == a.id))))


@router.post("/friends/{user_id}")
def add_friend(user_id: int, me: User = Depends(current_user), db: Session = Depends(get_db)):
    """发好友申请。对方也申请过我、或对方是示例用户时，直接成为好友。"""
    other = db.get(User, user_id)
    if other is None or other.id == me.id or user_id in _blocked_ids(db, me):
        raise HTTPException(404, "找不到这个人")
    if db.get(Friendship, (me.id, other.id)) is not None:
        return {"status": "friends", "got": 0, "coins": me.coins}
    mutual = db.scalar(select(FriendRequest.id).where(FriendRequest.from_id == other.id, FriendRequest.to_id == me.id))
    if other.is_bot or mutual:
        _befriend(db, me, other)
        got = coinlib.earn(db, me, "friend")
        coinlib.earn(db, other, "friend")
        db.commit()
        return {"status": "friends", "got": got, "coins": me.coins}
    if db.scalar(select(FriendRequest.id).where(FriendRequest.from_id == me.id, FriendRequest.to_id == other.id)) is None:
        db.add(FriendRequest(from_id=me.id, to_id=other.id))
        db.commit()
    return {"status": "requested", "got": 0, "coins": me.coins}


@router.post("/friends/requests/{request_id}/{action}")
def answer_request(request_id: int, action: str, me: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(FriendRequest, request_id)
    if r is None or r.to_id != me.id:
        raise HTTPException(404, "申请不见了")
    got = 0
    if action == "accept":
        other = db.get(User, r.from_id)
        _befriend(db, me, other)
        got = coinlib.earn(db, me, "friend")
        coinlib.earn(db, other, "friend")
    elif action == "decline":
        db.delete(r)
    else:
        raise HTTPException(400, "只能同意或忽略")
    db.commit()
    return {"ok": True, "got": got, "coins": me.coins}


@router.delete("/friends/{user_id}")
def remove_friend(user_id: int, me: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(Friendship).where(or_((Friendship.user_id == me.id) & (Friendship.friend_id == user_id), (Friendship.user_id == user_id) & (Friendship.friend_id == me.id))))
    db.commit()
    return {"ok": True}


@router.post("/blocks/{user_id}")
def block(user_id: int, me: User = Depends(current_user), db: Session = Depends(get_db)):
    if user_id == me.id or db.get(User, user_id) is None:
        raise HTTPException(404, "找不到这个人")
    if db.get(Block, (me.id, user_id)) is None:
        db.add(Block(user_id=me.id, blocked_id=user_id))
    remove_friend(user_id, me, db)
    db.execute(delete(FriendRequest).where(or_((FriendRequest.from_id == me.id) & (FriendRequest.to_id == user_id), (FriendRequest.from_id == user_id) & (FriendRequest.to_id == me.id))))
    db.commit()
    return {"ok": True}


@router.delete("/blocks/{user_id}")
def unblock(user_id: int, me: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(Block).where(Block.user_id == me.id, Block.blocked_id == user_id))
    db.commit()
    return {"ok": True}
