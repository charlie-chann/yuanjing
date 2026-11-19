# 愿境后端

FastAPI + SQLAlchemy。本地默认用 SQLite（`data/yuanjing.db`），上线换 PostgreSQL。

## 本地跑

```bash
cd server
uv sync                # 第一次
./run.sh               # http://127.0.0.1:8787 ，接口文档在 /docs
.venv/bin/python -m pytest -q
```

应用默认连 `http://127.0.0.1:8787`（模拟器能直接连）。真机或线上：`flutter build ios --dart-define=YJ_API=https://你的域名`。

本地的 SQLite 启动时只会 `create_all`：缺的表会建，**已有的表不会加新列**。改了表结构（比如 `sanctuary_offerings.public`）以后，老的 `data/yuanjing.db` 要升一下：

```bash
.venv/bin/alembic upgrade head          # data/yuanjing.db 已经记了版本（alembic_version）
# 一个从没记过版本、由 create_all 建出来的老库：先对一下缺哪些列，再从对应的版本记起，例如
# .venv/bin/alembic stamp 5c8e3f0d2b41 && .venv/bin/alembic upgrade head
```

不升的话 `/sanctuary` 的心跳和 `/offer` 会报 `no such column`，岛上就没有别人、也记不下挂上去的心意。

## 有什么

- 登录：先用设备号免注册（`POST /auth/device`），以后接手机号或 Sign in with Apple 往 users 表加字段。
- 数据：心愿、愿景板（图片上传 `POST /files`，会缩图并去掉照片里的定位信息）、终点密码、肯定语、宠物、资料、皮肤。
- 金币：发放规则、每日上限、连续签到、商城价格、会员限定都在 `app/catalog.py`，**以服务器为准**，应用里那份只用来显示。
- 广场：动态分页、点赞、只能选预设句子的夸夸、举报（3 人举报自动下架）、拉黑、好友申请（示例用户自动通过）。没有私信和自由评论。
- 内容把关：`app/moderation.py`，关键词和联系方式过滤。**上线前要接云厂商的文本审核**，关键词留作兜底。
- AI：`app/routers/ai.py`。`.env` 里填了 `YJ_LLM_BASE_URL / YJ_LLM_API_KEY / YJ_LLM_MODEL`（任何 OpenAI 兼容接口）就用大模型，否则用 `app/ai/templates.py` 的模板；大模型的输出也会再过一遍内容把关。
- 示例用户：`app/seed.py`，8 个人 12 条动态，冷启动用。正式环境 `YJ_SEED_DEMO=0`。
- 接后端之前存在手机上的数据，第一次登录时由应用调 `POST /me/import` 搬上来（只对空账号有效，金币和买过的东西不搬）。

## 上线前必须做

1. `YJ_SECRET` 换成随机长串（连的不是 SQLite 还用默认值会拒绝启动）。
2. 换 PostgreSQL：`YJ_DATABASE_URL=postgresql+psycopg://...`，加装 `psycopg[binary]`，然后 `.venv/bin/alembic upgrade head`。改了表结构：`.venv/bin/alembic revision --autogenerate -m "说明"`。
3. `YJ_DEMO_MEMBERSHIP=0`，接苹果内购的服务端校验后由回调开通会员。
4. 接文本审核和图片审核；国内上架还需要备案、隐私政策、实名或手机号登录。
5. 图片目前存本机磁盘，多台服务器时换成对象存储。

