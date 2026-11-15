"""数据表。改了表结构要生成迁移：.venv/bin/alembic revision --autogenerate -m "说明"。"""
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    # 先用设备号免注册登录；以后接手机号、Sign in with Apple 时往这张表加字段
    device_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(24), default="愿境旅人")
    sign: Mapped[str] = mapped_column(String(60), default="我正在路上。")
    avatar_url: Mapped[str | None] = mapped_column(String(200))
    coins: Mapped[int] = mapped_column(Integer, default=268)
    member_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    skin_id: Mapped[str] = mapped_column(String(16), default="gold")
    look_mode: Mapped[str] = mapped_column(String(10), default="anime")
    look_dynamic: Mapped[bool] = mapped_column(Boolean, default=False)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    last_checkin: Mapped[date | None] = mapped_column(Date)
    # 示例用户（冷启动用），加它为好友会自动通过
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    # 身份卡称号：示例用户写死，真实用户按心愿算
    title: Mapped[str | None] = mapped_column(String(30))
    banned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    @property
    def member(self) -> bool:
        if self.member_until is None:
            return False
        until = self.member_until if self.member_until.tzinfo else self.member_until.replace(tzinfo=timezone.utc)
        return until > now()


class CoinEntry(Base):
    """金币流水。余额存在 users.coins，这里记每一笔，每日上限也按这里数。"""

    __tablename__ = "coin_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    # 奖励规则名（checkin、wish、like……）或 spend
    kind: Mapped[str] = mapped_column(String(16))
    what: Mapped[str] = mapped_column(String(60))
    # 这一笔算在哪一天（按配置的时区）
    day: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (Index("ix_coin_user_kind_day", "user_id", "kind", "day"),)


class Wish(Base):
    __tablename__ = "wishes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scene: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Post(Base):
    """朋友圈、感恩日记、许愿动态。"""

    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    public: Mapped[bool] = mapped_column(Boolean, default=True)
    # 被举报够数或人工下架后不再出现在广场
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    user: Mapped[User] = relationship()


class Like(Base):
    __tablename__ = "likes"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Praise(Base):
    """夸夸。from_user_id 为空表示 AI 夸的。"""

    __tablename__ = "praises"
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    from_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Friendship(Base):
    """好友关系，每对存两行（双向）。"""

    __tablename__ = "friendships"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    friend_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FriendRequest(Base):
    __tablename__ = "friend_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    from_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    to_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("from_id", "to_id"),)


class Block(Base):
    """拉黑：看不到对方的动态，对方也不能加我。"""

    __tablename__ = "blocks"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    blocked_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("user_id", "post_id"),)


class VisionItem(Base):
    __tablename__ = "vision_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(60), default="")
    scene: Mapped[str] = mapped_column(String(16))
    photo_url: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Destiny(Base):
    """终点密码：一个方面一段话。"""

    __tablename__ = "destiny"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    scene: Mapped[str] = mapped_column(String(16), primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Affirmation(Base):
    __tablename__ = "affirmations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Pet(Base):
    __tablename__ = "pets"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(8))
    photo_url: Mapped[str | None] = mapped_column(String(200))


class Owned(Base):
    """买过的东西：装扮，或用金币解锁的冥想。"""

    __tablename__ = "owned"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    equipped: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WishHeard(Base):
    """听过的许愿回应：用来让同一个人不总是听到同一句"""

    __tablename__ = "wish_heard"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    answer_id: Mapped[int] = mapped_column(Integer)
    core: Mapped[int] = mapped_column(Integer)
    intent: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# 湖心小寺（俯视的三维小游戏）：谁在场、留下的心意
class SanctuaryPresence(Base):
    """湖心小寺里此刻在场的人。客户端每几秒报一次，超过半分钟没报就算离开了。"""

    __tablename__ = "sanctuary_presence"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    scene: Mapped[str] = mapped_column(String(12), index=True)
    # 坐在第几个位置；-1 是站着走动
    seat: Mapped[int] = mapped_column(Integer, default=-1)
    # 最近做的动作（鞠躬、跪拜），几秒内别人能看到
    action: Mapped[str | None] = mapped_column(String(12))
    action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class SanctuaryOffering(Base):
    """留在湖心小寺的心意：许愿树绳上的红布条和木牌、香炉里的香"""

    __tablename__ = "sanctuary_offerings"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scene: Mapped[str] = mapped_column(String(12))
    kind: Mapped[str] = mapped_column(String(12))
    # 挂在树上第几个位置；香和硬币没有位置，是 -1
    slot: Mapped[int] = mapped_column(Integer, default=-1)
    # 写在上面的愿望，只有自己看得到
    text: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    __table_args__ = (Index("ix_sanctuary_offerings_scene_id", "scene", "id"),)


class PetBond(Base):
    """湖心小寺里的小动物和一个人的交情。摸它、喂它会涨，它就记住你了：
    熟了会在你上岛时跑来迎接、跟着你走，还会叼礼物来。"""

    __tablename__ = "pet_bonds"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    pet: Mapped[str] = mapped_column(String(16))
    affinity: Mapped[int] = mapped_column(Integer, default=0)
    # 每天摸和喂各只有前几次涨交情，这里记今天已经算了几次
    day: Mapped[date | None] = mapped_column(Date)
    pets_today: Mapped[int] = mapped_column(Integer, default=0)
    feeds_today: Mapped[int] = mapped_column(Integer, default=0)
    # 哪天收过它的礼物、哪天它来迎接过（一天一次）
    gift_day: Mapped[date | None] = mapped_column(Date)
    greet_day: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (UniqueConstraint("user_id", "pet", name="uq_pet_bonds_user_pet"),)
