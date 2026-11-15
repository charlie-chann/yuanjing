from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .catalog import COIN_RULES, STREAK_CAP, STREAK_STEP
from .config import settings
from .models import CoinEntry, User


def today() -> date:
    return datetime.now(settings.tz).date()


def count_today(db: Session, user: User, kind: str) -> int:
    return db.scalar(select(func.count()).select_from(CoinEntry).where(CoinEntry.user_id == user.id, CoinEntry.kind == kind, CoinEntry.day == today())) or 0


def earn(db: Session, user: User, kind: str) -> int:
    """按规则发金币，返回实际发了多少（今天到上限了返回 0）。不提交事务，由调用方提交。"""
    amount, cap, what = COIN_RULES[kind]
    if user.is_bot or count_today(db, user, kind) >= cap:
        return 0
    if kind == "checkin":
        d = today()
        user.streak = user.streak + 1 if user.last_checkin is not None and (d - user.last_checkin).days == 1 else 1
        user.last_checkin = d
        amount += min((user.streak - 1) * STREAK_STEP, STREAK_CAP)
    user.coins += amount
    db.add(CoinEntry(user_id=user.id, amount=amount, kind=kind, what=what, day=today()))
    return amount


def spend(db: Session, user: User, amount: int, what: str) -> bool:
    if amount <= 0:
        return True
    if user.coins < amount:
        return False
    user.coins -= amount
    db.add(CoinEntry(user_id=user.id, amount=-amount, kind="spend", what=what, day=today()))
    return True


def daily_counts(db: Session, user: User) -> dict[str, int]:
    rows = db.execute(
        select(CoinEntry.kind, func.count()).where(CoinEntry.user_id == user.id, CoinEntry.day == today()).group_by(CoinEntry.kind)
    ).all()
    return {k: n for k, n in rows}
