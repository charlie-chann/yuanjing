import io

from PIL import Image


def test_login_is_stable_per_device(client):
    a = client.post("/auth/device", json={"device_id": "device-aaaa-1"}).json()
    b = client.post("/auth/device", json={"device_id": "device-aaaa-1"}).json()
    assert a["user"]["id"] == b["user"]["id"] and a["new"] and not b["new"]
    assert client.get("/me/state").status_code == 401
    assert client.get("/me/state", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_wish_coins_once_per_day(client, login):
    h = login()
    start = client.get("/me/state", headers=h).json()["user"]["coins"]
    r1 = client.post("/wishes", json={"scene": "wealth", "text": "财富自由"}, headers=h).json()
    r2 = client.post("/wishes", json={"scene": "career", "text": "升职"}, headers=h).json()
    assert r1["got"] == 5 and r2["got"] == 0 and r2["coins"] == start + 5
    st = client.get("/me/state", headers=h).json()
    assert [w["text"] for w in st["wishes"]] == ["升职", "财富自由"]
    assert st["daily"]["wish"] == 1
    assert client.post("/wishes", json={"scene": "nope", "text": "x"}, headers=h).status_code == 400


def test_checkin_once(client, login):
    h = login()
    a = client.post("/checkin", headers=h).json()
    b = client.post("/checkin", headers=h).json()
    assert a["got"] == 10 and a["streak"] == 1 and b["got"] == 0
    assert client.get("/me/state", headers=h).json()["user"]["checked_in"]


def test_shop_prices_and_member_items(client, login):
    h = login()
    r = client.post("/shop/buy", json={"item_id": "moon_lamp"}, headers=h).json()
    assert r["coins"] == 268 - 120 and "moon_lamp" in r["equipped"]
    assert client.post("/shop/buy", json={"item_id": "moon_lamp"}, headers=h).status_code == 409
    assert client.post("/shop/buy", json={"item_id": "pet_bed"}, headers=h).status_code == 403
    client.post("/shop/buy", json={"item_id": "frame_gold"}, headers=h)
    r = client.post("/shop/buy", json={"item_id": "frame_star"}, headers=h).json()
    assert "frame_star" in r["equipped"] and "frame_gold" not in r["equipped"]  # 头像框只能戴一个
    assert client.post("/shop/buy", json={"item_id": "balloons"}, headers=h).status_code == 402  # 钱不够了
    r = client.post("/shop/equip", json={"item_id": "moon_lamp", "on": False}, headers=h).json()
    assert "moon_lamp" not in r["equipped"]


def test_member_skin_and_demo_toggle(client, login):
    h = login()
    assert client.patch("/me", json={"skin": "witch"}, headers=h).status_code == 403
    assert client.post("/membership/demo", json={"on": True}, headers=h).json()["member"]
    assert client.patch("/me", json={"skin": "witch"}, headers=h).json()["skin"] == "witch"
    assert client.post("/shop/buy", json={"item_id": "pet_bed"}, headers=h).status_code == 200
    me = client.post("/membership/demo", json={"on": False}, headers=h).json()
    assert not me["member"] and me["skin"] == "gold"  # 退订后会员皮肤换回免费的


def test_plaza_feed_has_seed_and_my_post(client, login):
    h = login()
    feed = client.get("/plaza", headers=h).json()
    assert len(feed["items"]) >= 10 and feed["items"][0]["ts"] >= feed["items"][-1]["ts"]
    r = client.post("/posts", json={"type": "moment", "text": "今天的晚霞很好看"}, headers=h).json()
    assert r["got"] == 5 + 2  # 发布 + 被 AI 夸
    assert r["post"]["praises"][0]["ai"]
    assert client.get("/plaza", headers=h).json()["items"][0]["id"] == r["post"]["id"]
    # 负面内容不能公开发，但可以私密存
    assert client.post("/posts", json={"type": "moment", "text": "真是垃圾"}, headers=h).status_code == 400
    assert client.post("/posts", json={"type": "diary", "text": "真是垃圾的一天", "public": False}, headers=h).status_code == 200
    assert client.post("/posts", json={"type": "moment", "text": "加我微信 12345678"}, headers=h).status_code == 400


def test_like_praise_coins_both_sides(client, login):
    a, b = login(), login()
    post = client.post("/posts", json={"type": "moment", "text": "第一次在广场发东西"}, headers=a).json()["post"]
    before = client.get("/me/state", headers=a).json()["user"]["coins"]
    r = client.post(f"/posts/{post['id']}/like", headers=b).json()
    assert r["liked"] and r["likes"] == 1 and r["got"] == 1
    r = client.post(f"/posts/{post['id']}/like", headers=b).json()
    assert not r["liked"] and r["likes"] == 0
    assert client.post(f"/posts/{post['id']}/praise", json={"text": "随便写的"}, headers=b).status_code == 400
    r = client.post(f"/posts/{post['id']}/praise", json={"text": "替你开心"}, headers=b).json()
    assert r["got"] == 2 and any(p["mine"] for p in r["post"]["praises"])
    assert client.post(f"/posts/{post['id']}/praise", json={"text": "替你开心"}, headers=b).status_code == 409
    after = client.get("/me/state", headers=a).json()["user"]["coins"]
    assert after == before + 2 + 2  # 被赞 + 被夸


def test_friends_request_and_bot_auto_accept(client, login):
    a, b = login(), login()
    aid = client.get("/me/state", headers=a).json()["user"]["id"]
    bid = client.get("/me/state", headers=b).json()["user"]["id"]
    assert client.post(f"/friends/{bid}", headers=a).json()["status"] == "requested"
    reqs = client.get("/me/state", headers=b).json()["requests"]
    assert reqs[0]["user"]["id"] == aid
    assert client.post(f"/friends/requests/{reqs[0]['id']}/accept", headers=b).json()["got"] == 2
    assert [f["id"] for f in client.get("/me/state", headers=a).json()["friends"]] == [bid]
    # 示例用户直接通过
    bot = client.get("/plaza", headers=a).json()["items"][-1]["user"]["id"]
    assert client.post(f"/friends/{bot}", headers=a).json()["status"] == "friends"
    # 好友筛选只看到自己和好友的
    feed = client.get("/plaza?filter=friends", headers=a).json()["items"]
    assert {i["user"]["id"] for i in feed} <= {aid, bid, bot}


def test_block_hides_posts_and_report_hides_after_three(client, login):
    a, b = login(), login()
    post = client.post("/posts", json={"type": "moment", "text": "一条普通的动态"}, headers=a).json()["post"]
    aid = post["user"]["id"]
    client.post(f"/blocks/{aid}", headers=b)
    assert all(i["user"]["id"] != aid for i in client.get("/plaza?limit=50", headers=b).json()["items"])
    assert client.get(f"/users/{aid}", headers=b).status_code == 404
    for _ in range(3):
        assert client.post(f"/posts/{post['id']}/report", json={"reason": "测试"}, headers=login()).status_code == 200
    assert all(i["id"] != post["id"] for i in client.get("/plaza?limit=50", headers=login()).json()["items"])


def test_vision_destiny_affirmations_pets(client, login):
    h = login()
    v = client.post("/vision", json={"text": "跑车", "scene": "life"}, headers=h).json()
    assert client.post("/vision", json={"text": " ", "scene": "life"}, headers=h).status_code == 400
    client.put("/destiny/wealth", json={"text": "我从容地过着丰盛的生活"}, headers=h)
    client.post("/affirmations", json={"text": "我值得"}, headers=h)
    p = client.post("/pets", json={"name": "团子", "kind": "狗狗"}, headers=h).json()
    st = client.get("/me/state", headers=h).json()
    assert st["vision"][0]["id"] == v["id"] and st["destiny"]["wealth"] and st["affirmations"][0]["text"] == "我值得"
    assert st["pets"][0]["name"] == "团子"
    client.put("/destiny/wealth", json={"text": ""}, headers=h)
    client.delete(f"/vision/{v['id']}", headers=h)
    client.delete(f"/pets/{p['id']}", headers=h)
    st = client.get("/me/state", headers=h).json()
    assert not st["destiny"] and not st["vision"] and not st["pets"]


def test_import_only_into_empty_account(client, login):
    h = login()
    body = {
        "wishes": [{"scene": "mood", "text": "心里安静", "ts": 1_700_000_000_000}],
        "destiny": {"life": "我过着自己选择的生活"},
        "posts": [{"type": "diary", "text": "谢谢今天", "public": False}],
        "profile": {"name": "小鹿", "skin": "witch"},
    }
    st = client.post("/me/import", json=body, headers=h).json()
    assert st["wishes"][0]["text"] == "心里安静" and st["user"]["name"] == "小鹿"
    assert st["user"]["skin"] == "gold"  # 会员皮肤不随导入带过来
    assert client.post("/me/import", json=body, headers=h).status_code == 409


def test_ai_templates(client, login):
    h = login()
    assert client.get("/ai/analysis", headers=h).json()["report"] is None
    client.post("/wishes", json={"scene": "wealth", "text": "存款翻倍"}, headers=h)
    client.post("/wishes", json={"scene": "wealth", "text": "存款再多一点"}, headers=h)
    rep = client.get("/ai/analysis", headers=h).json()
    assert rep["report"]["need"] and rep["report"]["advice"] is None  # 非会员看不到细的
    assert client.post("/ai/moment", headers=h).json()["text"]
    assert "三件事" in client.post("/ai/diary", headers=h).json()["text"]
    assert client.post("/ai/affirmations", json={}, headers=h).status_code == 403
    client.post("/membership/demo", json={"on": True}, headers=h)
    lines = client.post("/ai/affirmations", json={"scenes": ["wealth"]}, headers=h).json()["lines"]
    assert lines[-1] == "我已经走在路上了。"
    assert "存款" in client.get("/ai/destiny/wealth", headers=h).json()["text"]
    assert client.post("/ai/reading", json={"text": "我不想活了"}, headers=h).json()["support"]
    assert client.post("/ai/reading", json={"text": "被骂了"}, headers=h).json()["source"] == "none"


def test_upload_strips_and_resizes(client, login):
    h = login()
    buf = io.BytesIO()
    Image.new("RGB", (3000, 2000), (200, 120, 80)).save(buf, "PNG")
    r = client.post("/files", files={"file": ("a.png", buf.getvalue(), "image/png")}, headers=h).json()
    img = Image.open(io.BytesIO(client.get(r["url"]).content))
    assert img.format == "JPEG" and max(img.size) == 1400
    assert client.post("/files", files={"file": ("a.txt", b"hello", "text/plain")}, headers=h).status_code == 400


def test_wish_answer_api(client, login):
    h = login()
    r = client.post("/wish/answer", json={"text": "希望妈妈手术顺利", "scene": "health", "hour": 22}, headers=h).json()
    assert r["intent"] == "health.surgery" and r["mood"] == "anxious" and r["tod"] == "night"
    assert len(r["lines"]) == 4 and len(r["audio"]) == 4
    r2 = client.post("/wish/answer", json={"text": "希望妈妈手术顺利", "scene": "health", "hour": 22}, headers=h).json()
    assert r2["segments"][1] != r["segments"][1]  # 第二次换一句核心回应
    assert client.post("/wish/answer", json={"text": "不想活了", "scene": "mood"}, headers=h).json()["support"]


def test_islet_presence_and_offerings(client, login):
    """湖心小寺：在场名单、天气、心意（红布条、木牌、香）"""
    a, b = login(), login()
    assert client.post("/sanctuary/temple/beat", json={}, headers=a).status_code == 404
    s = client.post("/sanctuary/islet/beat", json={"seat": -1, "seats": 20}, headers=a).json()
    assert s["weather"] in ("clear", "rain", "storm", "snow") and s["count"] >= 1
    # 坐着的人座位不重复、在范围内；不坐的人（在岛上走动的香客）座位是 -1
    seats = [p["seat"] for p in s["people"] if p["seat"] >= 0]
    assert len(seats) == len(set(seats)) and all(0 <= x < 20 for x in seats)
    free = next(i for i in range(20) if i not in seats)
    client.post("/sanctuary/islet/beat", json={"seat": free, "seats": 20, "action": "bow"}, headers=b)
    s = client.post("/sanctuary/islet/beat", json={"seat": -1, "seats": 20}, headers=a).json()
    real = [p for p in s["people"] if not p["npc"]]
    assert len(real) == 1 and real[0]["seat"] == free and real[0]["action"] == "bow"
    assert client.post("/sanctuary/islet/beat", json={"action": "dance"}, headers=a).status_code == 400
    r1 = client.post("/sanctuary/islet/offer", json={"kind": "ribbon", "slot": 4, "text": "家人平安"}, headers=a).json()
    r2 = client.post("/sanctuary/islet/offer", json={"kind": "incense"}, headers=a).json()
    assert r1["got"] == 3 and r2["got"] == 0
    assert client.post("/sanctuary/islet/offer", json={"kind": "coin"}, headers=a).status_code == 400
    mine = client.post("/sanctuary/islet/beat", json={}, headers=a).json()
    assert {"slot": 4, "kind": "ribbon", "text": "家人平安"} in mine["mine"]
    other = client.post("/sanctuary/islet/beat", json={}, headers=b).json()
    assert {"slot": 4, "kind": "ribbon"} in other["offerings"] and not other["mine"]
    client.post("/sanctuary/islet/leave", headers=b)
    s = client.post("/sanctuary/islet/beat", json={}, headers=a).json()
    assert not [p for p in s["people"] if not p["npc"]]


def test_pets_bond_greet_and_gift(client, login):
    """小动物：摸和喂涨交情（每天各算 3 次）、喂要花金币、熟了会迎接和送礼物"""
    a = login()
    s = client.get("/pets", headers=a).json()
    assert len(s["pets"]) == 10 and all(p["level"] == 0 and not p["greet"] and p["gift"] is None for p in s["pets"])
    coins = s["coins"]
    assert client.post("/pets/dragon/pet", headers=a).status_code == 404
    # 摸 4 次：只有前 3 次算
    rs = [client.post("/pets/teddy/pet", headers=a).json() for _ in range(4)]
    assert [r["counted"] for r in rs] == [True, True, True, False] and rs[-1]["affinity"] == 3
    assert rs[2]["level_up"] and rs[2]["level"] == 1 and rs[-1]["pets_left"] == 0
    # 喂 3 次：每次花 2 金币、涨 2
    for i in range(3):
        r = client.post("/pets/teddy/feed", headers=a).json()
        assert r["counted"] and r["coins"] == coins - 2 * (i + 1)
    assert r["affinity"] == 9 and r["level"] == 1 and r["feeds_left"] == 0
    r = client.post("/pets/teddy/feed", headers=a).json()
    assert not r["counted"] and r["affinity"] == 9
    # 别的动物、别的人互不影响
    assert client.get("/pets", headers=login()).json()["pets"][0]["affinity"] == 0
    assert [p["affinity"] for p in client.get("/pets", headers=a).json()["pets"]] == [9] + [0] * 9


def test_pets_best_friend_gift(client, login, db_session=None):
    """交情到「最好的朋友」：当天第一次上岛来迎接、必有礼物，礼物一天只能收一次"""
    from app.db import SessionLocal
    from app.models import PetBond, User
    a = login()
    client.post("/pets/shiba/pet", headers=a)
    with SessionLocal() as db:
        b = db.query(PetBond).order_by(PetBond.id.desc()).first()
        b.affinity = 30
        db.commit()
    s = {p["id"]: p for p in client.get("/pets", headers=a).json()["pets"]}
    assert s["shiba"]["level"] == 3 and s["shiba"]["greet"] and s["shiba"]["gift"] == "一根捡来的树枝"
    # 再取一次：今天已经迎接过了，礼物还在（还没收）
    s = {p["id"]: p for p in client.get("/pets", headers=a).json()["pets"]}
    assert not s["shiba"]["greet"] and s["shiba"]["gift"]
    before = client.get("/pets", headers=a).json()["coins"]
    g = client.post("/pets/shiba/gift", headers=a).json()
    assert 4 <= g["got"] <= 9 and g["coins"] == before + g["got"] and g["name"] == "年糕"
    assert client.post("/pets/shiba/gift", headers=a).json()["got"] == 0
    assert {p["id"]: p for p in client.get("/pets", headers=a).json()["pets"]}["shiba"]["gift"] is None


def test_crowd_follows_time():
    """内置香客：任何时刻 10 到 50 人；同一时刻算两次一样；随时有人来有人走；早晚比凌晨多"""
    from datetime import datetime, timedelta
    from app.config import settings
    from app.routers.sanctuary import npcs_at
    t0 = datetime(2026, 11, 15, 0, 0, tzinfo=settings.tz)
    counts, churn, prev = [], 0, None
    for k in range(24 * 6):
        t = t0 + timedelta(minutes=10 * k)
        ps = npcs_at("islet", t, 216, set())
        assert 10 <= len(ps) <= 50
        assert ps == npcs_at("islet", t, 216, set())
        ids = {p["id"] for p in ps}
        assert len({p["seat"] for p in ps if p["seat"] >= 0}) == sum(p["seat"] >= 0 for p in ps)
        if prev is not None:
            churn += len(ids ^ prev)
        prev = ids
        counts.append(len(ps))
    assert churn > 24 * 6
    night = sum(counts[2 * 6:5 * 6]) / 18
    evening = sum(counts[18 * 6:20 * 6]) / 12
    assert evening > night * 2
    p = npcs_at("islet", t0 + timedelta(hours=18), 216, set())[0]
    assert p["plan"] and p["stay"] > 0 and 0 <= p["since"] < p["stay"]

