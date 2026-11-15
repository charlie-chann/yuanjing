import os
import tempfile
import uuid

# 测试用一个临时库，不碰开发库；必须在导入 app 之前设置
_tmp = tempfile.mkdtemp(prefix="yj-test-")
os.environ["YJ_DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["YJ_UPLOAD_DIR"] = f"{_tmp}/uploads"
os.environ["YJ_LLM_API_KEY"] = ""  # 测试只走模板

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def login(client):
    """新建一个用户，返回带登录凭证的请求头"""

    def make():
        r = client.post("/auth/device", json={"device_id": uuid.uuid4().hex})
        assert r.status_code == 200 and r.json()["new"]
        return {"Authorization": f"Bearer {r.json()['token']}"}

    return make
