"""登录凭证：签名的令牌，放在请求头 Authorization: Bearer <令牌> 里。"""
from datetime import timedelta

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User, now


def make_token(user_id: int) -> str:
    return jwt.encode({"sub": str(user_id), "exp": now() + timedelta(days=settings.token_days)}, settings.secret, algorithm="HS256")


def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "请先登录")
    try:
        user_id = int(jwt.decode(authorization[7:], settings.secret, algorithms=["HS256"])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "登录已过期，请重新打开应用")
    user = db.get(User, user_id)
    if user is None or user.banned:
        raise HTTPException(401, "账号不可用")
    return user
