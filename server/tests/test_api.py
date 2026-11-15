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
    seats = [p["seat"] for p in s["people"]]
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
