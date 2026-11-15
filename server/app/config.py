"""配置。全部从环境变量读，server/.env 里写的会先被读进来（不覆盖已有的环境变量）。"""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def _load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()


def _flag(name: str, default: bool) -> bool:
    return os.environ.get(name, "1" if default else "0").lower() in ("1", "true", "yes", "on")


class Settings:
    # 数据库：本地默认 SQLite 文件；上线换成 postgresql+psycopg://user:pass@host/db
    database_url = os.environ.get("YJ_DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'yuanjing.db'}")
    # 登录凭证的签名密钥。上线前必须换成随机的长字符串
    secret = os.environ.get("YJ_SECRET", "dev-only-secret-change-me-before-going-online")
    token_days = int(os.environ.get("YJ_TOKEN_DAYS", "180"))
    # 用户上传的图片放在哪里
    upload_dir = Path(os.environ.get("YJ_UPLOAD_DIR", str(ROOT / "data" / "uploads")))
    # 「今天」按哪个时区算：签到、每日上限都看它
    tz = ZoneInfo(os.environ.get("YJ_TZ", "Asia/Shanghai"))
    # 没接苹果内购之前，允许应用里直接开关会员（只在开发环境打开）
    demo_membership = _flag("YJ_DEMO_MEMBERSHIP", True)
    # 大模型：OpenAI 兼容接口。三项都填了才会用，否则所有 AI 内容走本地模板
    llm_base_url = os.environ.get("YJ_LLM_BASE_URL", "")
    llm_api_key = os.environ.get("YJ_LLM_API_KEY", "")
    llm_model = os.environ.get("YJ_LLM_MODEL", "")
    llm_timeout = float(os.environ.get("YJ_LLM_TIMEOUT", "20"))
    # 许愿回应库（tools/wishdb/build.py 生成）和回应语音所在的文件夹
    wish_db = Path(os.environ.get("YJ_WISH_DB", str(ROOT / "data" / "wish_answers.db")))
    wish_voice_dir = Path(os.environ.get("YJ_WISH_VOICE", str(ROOT / "data" / "wish_voice")))
    # 启动时写入示例用户和示例动态（冷启动时广场不是空的）
    seed_demo = _flag("YJ_SEED_DEMO", True)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)


settings = Settings()


# 连的不是本地 SQLite（也就是上线了）还用着默认密钥，直接拒绝启动
if not settings.database_url.startswith("sqlite") and settings.secret.startswith("dev-only"):
    raise RuntimeError("上线前必须设置 YJ_SECRET（随机的长字符串）")
