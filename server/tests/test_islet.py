"""钓鱼、背包、带东西喂食、里程碑礼物、每日礼物、兑换"""
import random

import pytest

from app.db import SessionLocal
from app.islet import FISH, KEEPS, give
from app.models import Inventory, Owned, PetBond, User
from app.routers import fishing, pets
from app.routers.fishing import DAILY_CATCH, fish_weights


def _me(client, h) -> int:
    return client.get("/me/state", headers=h).json()["user"]["id"]


def _put(client, h, **items):
    """直接往背包里放东西"""
    uid = _me(client, h)
    with SessionLocal() as db:
        u = db.get(User, uid)
        for k, n in items.items():
            give(db, u, k, n)
        db.commit()


def _set_affinity(client, h, pet, affinity):
    uid = _me(client, h)
    with SessionLocal() as db:
        b = db.query(PetBond).filter_by(user_id=uid, pet=pet).one()
        b.affinity = affinity
        db.commit()


def _bag(client, h) -> dict:
    return {i["id"]: i["count"] for i in client.get("/bag", headers=h).json()["items"]}


@pytest.fixture
def fixed_rng(monkeypatch):
    monkeypatch.setattr(fishing, "rng", random.Random(7))


# ───────── 钓鱼 ─────────
def test_fish_weights_by_spot_time_weather():
    pond = fish_weights("pond", "day", "clear")
    assert set(pond) == {"crucian", "loach", "goldfish", "shrimp", "weed"}
    sea = fish_weights("sea", "day", "clear")
    assert set(sea) == {"whitebait", "silver", "bass", "mandarin", "crab", "weed"}
    # 常见的比稀有的多
    assert sea["whitebait"] > sea["bass"] > sea["mandarin"]
    # 银鱼清晨多，大闸蟹黄昏和夜里多
    assert fish_weights("sea", "dawn", "clear")["silver"] > sea["silver"]
    assert fish_weights("sea", "dusk", "clear")["crab"] > sea["crab"] and fish_weights("sea", "night", "rain")["crab"] > sea["crab"]
    # 金鳞鲤雨天才有；月光鱼晴朗的夜里才有；池塘里都没有
    assert "carp_gold" in fish_weights("sea", "day", "rain") and "carp_gold" in fish_weights("sea", "night", "storm")
    assert "carp_gold" not in fish_weights("sea", "day", "snow")
    assert "moon" in fish_weights("sea", "night", "clear")
    assert "moon" not in fish_weights("sea", "night", "rain") and "moon" not in fish_weights("sea", "dusk", "clear")
    assert not {"carp_gold", "moon"} & set(fish_weights("pond", "night", "clear")) and "carp_gold" not in fish_weights("pond", "day", "rain")
    # 没见过的天色、天气不报错，只是没有任何加成
    assert fish_weights("sea", "noon", "fog") == sea


def test_fishing_catch_distribution(fixed_rng):
    """摇出来的鱼跟着权重走：池塘里只出池塘的鱼，常见的明显多于少见的"""
    w = fish_weights("pond", "day", "clear")
    got = fishing.rng.choices(list(w), weights=list(w.values()), k=4000)
    assert set(got) <= set(w)
    assert got.count("crucian") > 2 * got.count("goldfish") and got.count("loach") > 2 * got.count("shrimp")
    w = fish_weights("sea", "night", "clear")
    got = fishing.rng.choices(list(w), weights=list(w.values()), k=4000)
    assert 0 < got.count("moon") < got.count("whitebait") / 5


def test_fishing_catch_bag_dex_and_daily_cap(client, login, fixed_rng):
    h = login()
    assert client.post("/fishing/catch", json={"spot": "river"}, headers=h).status_code == 400
    book = client.get("/fishing", headers=h).json()
    assert book["left"] == DAILY_CATCH and book["total"] == len(FISH) == 11 and not any(f["caught"] for f in book["fish"])
    assert "weed" not in [f["id"] for f in book["fish"]]
    coins = client.get("/bag", headers=h).json()["coins"]
    firsts, total, best = set(), {}, {}
    for i in range(DAILY_CATCH):
        r = client.post("/fishing/catch", json={"spot": "pond", "time": "day", "weather": "clear"}, headers=h)
        assert r.status_code == 200
        r = r.json()
        f = r["fish"]
        assert f["id"] in ("crucian", "loach", "goldfish", "shrimp", "weed") and r["left"] == DAILY_CATCH - 1 - i
        total[f["id"]] = total.get(f["id"], 0) + 1
        assert r["count"] == total[f["id"]]
        if f["id"] == "weed":
            assert not f["first"] and not f["record"] and r["got"] == 0 and f["size_cm"] == 0 and f["rarity"] == "junk"
            continue
        lo, hi = FISH[f["id"]][4:6]
        assert lo <= f["size_cm"] <= hi and f["name"] == FISH[f["id"]][0]
        # 第一次钓到这种：有金币；之后只有比以前的都大才算破纪录
        assert f["first"] == (f["id"] not in firsts) and (r["got"] > 0) == f["first"]
        assert f["record"] == (not f["first"] and f["size_cm"] > best[f["id"]])
        firsts.add(f["id"])
        best[f["id"]] = max(best.get(f["id"], 0), f["size_cm"])
        coins += r["got"]
        assert r["coins"] == coins
    # 到上限了：409，背包和次数都不变
    r = client.post("/fishing/catch", json={"spot": "sea"}, headers=h)
    assert r.status_code == 409 and "明天再来" in r.json()["detail"]
    assert _bag(client, h) == total
    book = client.get("/fishing", headers=h).json()
    assert book["left"] == 0 and book["kinds"] == len(firsts)
    for f in book["fish"]:
        assert f["caught"] == (f["id"] in firsts) and f["count"] == total.get(f["id"], 0)
        assert f["best_cm"] == best.get(f["id"])
    # 别人不受影响
    assert client.get("/fishing", headers=login()).json()["left"] == DAILY_CATCH


def test_fishing_legend_only_in_its_weather(client, login, monkeypatch):
    """把权重改成「只要有传说鱼就必出」：雨天的湖里出金鳞鲤，晴天不出"""
    real = fishing.fish_weights

    def only_legend(spot, time, weather):
        w = real(spot, time, weather)
        legends = {k: v for k, v in w.items() if k in ("carp_gold", "moon")}
        return legends or {"whitebait": 1}

    monkeypatch.setattr(fishing, "fish_weights", only_legend)
    h = login()
    go = lambda **kw: client.post("/fishing/catch", json=kw, headers=h).json()
    assert go(spot="sea", time="day", weather="clear")["fish"]["id"] == "whitebait"
    r = go(spot="sea", time="day", weather="rain")
    assert r["fish"]["id"] == "carp_gold" and r["fish"]["rarity"] == "legend" and r["fish"]["first"] and r["got"] == 50
    assert go(spot="sea", time="night", weather="clear")["fish"]["id"] == "moon"
    assert go(spot="sea", time="night", weather="snow")["fish"]["id"] == "whitebait"
    assert go(spot="pond", time="night", weather="clear")["fish"]["id"] == "whitebait"  # 池塘里没有传说鱼


# ───────── 背包和卖出 ─────────
def test_bag_sell(client, login):
    h = login()
    assert client.get("/bag", headers=h).json()["items"] == []
    _put(client, h, crucian=3, mandarin=1, weed=2, shell=4)
    bag = client.get("/bag", headers=h).json()
    assert [(i["id"], i["kind"], i["count"]) for i in bag["items"]] == [("crucian", "fish", 3), ("mandarin", "fish", 1), ("weed", "fish", 2), ("shell", "gift", 4)]
    by = {i["id"]: i for i in bag["items"]}
    assert by["mandarin"]["rarity"] == "rare" and by["mandarin"]["feed"] == 5 and by["weed"]["feed"] == 0 and by["shell"]["feed"] == 0
    coins = bag["coins"]
    r = client.post("/bag/sell", json={"item_id": "crucian", "count": 2}, headers=h).json()
    assert r["got"] == 2 * by["crucian"]["sell"] and r["coins"] == coins + r["got"] and r["count"] == 1
    r = client.post("/bag/sell", json={"item_id": "mandarin"}, headers=h).json()
    assert r["got"] == 8 and r["count"] == 0 and "mandarin" not in [i["id"] for i in r["items"]]
    # 水草卖不出钱，等于扔掉
    r = client.post("/bag/sell", json={"item_id": "weed", "count": 2}, headers=h).json()
    assert r["got"] == 0 and r["coins"] == coins + 2 * by["crucian"]["sell"] + 8
    # 不够、没有这样东西、数量不对
    assert client.post("/bag/sell", json={"item_id": "crucian", "count": 5}, headers=h).status_code == 400
    assert client.post("/bag/sell", json={"item_id": "dragon"}, headers=h).status_code == 404
    assert client.post("/bag/sell", json={"item_id": "crucian", "count": 0}, headers=h).status_code == 422
    assert _bag(client, h) == {"crucian": 1, "shell": 4}
    log = client.get("/me/state", headers=h).json()["coin_log"]
    assert any("卖掉鳜鱼" in c["what"] and c["amount"] == 8 for c in log)


def test_shop_buy_stack_food(client, login):
    h = login()
    r = client.post("/shop/buy_stack", json={"item_id": "food_bone", "count": 3}, headers=h).json()
    assert r["coins"] == 268 - 15 and r["count"] == 3
    r = client.post("/shop/buy_stack", json={"item_id": "food_bone", "count": 2}, headers=h).json()
    assert r["count"] == 5 and [(i["id"], i["kind"], i["count"]) for i in r["items"]] == [("food_bone", "food", 5)]
    # 口粮不是「已拥有」的东西
    assert "food_bone" not in client.get("/me/state", headers=h).json()["owned"]
    assert client.post("/shop/buy_stack", json={"item_id": "moon_lamp", "count": 1}, headers=h).status_code == 404
    assert client.post("/shop/buy_stack", json={"item_id": "food_cream", "count": 99}, headers=h).status_code == 402
    assert client.post("/shop/buy", json={"item_id": "food_bone"}, headers=h).status_code == 404


# ───────── 带东西喂食 ─────────
def test_feed_with_item_favorite_and_errors(client, login):
    h = login()
    _put(client, h, crucian=2, mandarin=1, food_bone=2, weed=1, shell=1)
    coins = client.get("/bag", headers=h).json()["coins"]
    p = {x["id"]: x for x in client.get("/pets", headers=h).json()["pets"]}
    assert p["teddy"]["favorites"] == ["food_bone", "bass", "food_kibble"] and p["teddy"]["favorites_known"] == []
    # 不是最爱：鲫鱼（常见）+2，不花金币，扣掉一条
    r = client.post("/pets/teddy/feed", json={"item": "crucian"}, headers=h).json()
    assert r["gain"] == 2 and not r["favorite"] and r["affinity"] == 2 and r["coins"] == coins and r["favorites_known"] == []
    assert "栗子" in r["reaction"]
    # 最爱：肉骨头 3 ×1.5 向上取整 = 5，记下这样最爱
    r = client.post("/pets/teddy/feed", json={"item": "food_bone"}, headers=h).json()
    assert r["gain"] == 5 and r["favorite"] and r["affinity"] == 7 and r["favorites_known"] == ["food_bone"] and "眼睛都亮了" in r["reaction"]
    # 稀有的鳜鱼 +5；对年糕是最爱：8
    r = client.post("/pets/shiba/feed", json={"item": "mandarin"}, headers=h).json()
    assert r["gain"] == 8 and r["favorite"] and r["level"] == 1 and r["level_up"]
    assert _bag(client, h) == {"crucian": 1, "food_bone": 1, "weed": 1, "shell": 1}
    # 水草、收藏品不能喂；背包里没有的、不存在的报错；都不扣东西、不占次数
    r = client.post("/pets/teddy/feed", json={"item": "weed"}, headers=h)
    assert r.status_code == 400 and "不吃" in r.json()["detail"]
    assert client.post("/pets/teddy/feed", json={"item": "shell"}, headers=h).status_code == 400
    r = client.post("/pets/teddy/feed", json={"item": "moon"}, headers=h)
    assert r.status_code == 400 and "背包里没有" in r.json()["detail"]
    assert client.post("/pets/teddy/feed", json={"item": "dragon"}, headers=h).status_code == 404
    assert _bag(client, h) == {"crucian": 1, "food_bone": 1, "weed": 1, "shell": 1}
    p = {x["id"]: x for x in client.get("/pets", headers=h).json()["pets"]}
    assert p["teddy"]["feeds_left"] == 3 and p["teddy"]["affinity"] == 7 and p["teddy"]["favorites_known"] == ["food_bone"]
    # 不带 item、带空的 body：还是老办法
    r = client.post("/pets/teddy/feed", json={}, headers=h).json()
    # 金币：栗子和年糕各过了 5 的门槛（各送 10），这一把口粮花 2
    assert r["gain"] == 2 and r["coins"] == coins + 20 - 2 and r["item"] is None
    assert client.post("/pets/teddy/feed", headers=h).json()["gain"] == 2


def test_feed_daily_cap_still_eats(client, login):
    """每只每天喂食算 5 次，超了照样能喂（东西照扣）但不涨"""
    h = login()
    _put(client, h, whitebait=7)
    rs = [client.post("/pets/momo/feed", json={"item": "whitebait"}, headers=h).json() for _ in range(7)]
    assert [r["counted"] for r in rs] == [True] * 5 + [False] * 2 and [r["gain"] for r in rs] == [2] * 5 + [0, 0]
    assert rs[-1]["affinity"] == 10 and rs[-1]["feeds_left"] == 0 and "明天" in rs[-1]["reaction"]
    assert _bag(client, h) == {}
    # 摸还是每天 3 次，和喂食分开算
    assert client.post("/pets/momo/pet", headers=h).json()["counted"]


def test_levels_keep_first_four_and_add_more():
    assert pets.LEVELS[:4] == (0, 3, 10, 25) and pets.LEVEL_NAMES[:4] == ("陌生", "认识", "亲近", "最好的朋友")
    assert len(pets.LEVELS) == len(pets.LEVEL_NAMES) > 4
    assert [pets.level_of(a) for a in (0, 2, 3, 10, 24, 25, 59, 60, 500)] == [0, 0, 1, 2, 2, 3, 3, 4, 5]
    # 每只都有 2～3 样最爱（都是能喂的）、3～4 样会叼的收藏品、一件专属头像框
    from app.islet import feed_gain
    for pet in pets.PETS:
        assert 2 <= len(pets.FAVORITES[pet]) <= 3 and all(feed_gain(f) > 0 for f in pets.FAVORITES[pet])
        assert 3 <= len(pets.GIFTS[pet]) <= 4 and all(g in KEEPS for g in pets.GIFTS[pet])
        assert pet in pets.PET_FRAME
    assert any(m[0] == pets.KEEPSAKE_AT and m[1] == "frame" for m in pets.MILESTONES)


# ───────── 里程碑礼物 ─────────
def test_milestones_stack_and_never_repeat(client, login):
    h = login()
    r = client.post("/pets/tangerine/pet", headers=h).json()
    assert r["milestone"] is None and r["milestones"] == {"got": 0, "total": 8, "next": 5, "next_what": "一包金币（10 个）"}
    coins = r["coins"]
    # 一下子跨过 5、15、30、50 四个门槛：四份礼物一起到，一份不少
    _set_affinity(client, h, "tangerine", 49)
    r = client.post("/pets/tangerine/pet", headers=h).json()
    assert [m["at"] for m in r["milestones_new"]] == [5, 15, 30, 50] and r["milestone"]["at"] == 50
    assert [m["kind"] for m in r["milestones_new"]] == ["coins", "items", "coins", "frame"]
    assert r["coins"] == coins + 10 + 30
    # milestone 是最高的那个，coins 是这次一共送的，text 把这次送的全说了一遍
    assert r["milestone"]["coins"] == 40 and [m["coins"] for m in r["milestones_new"]] == [10, 0, 30, 0]
    assert "橘子送了你一包金币（10 个）" in r["milestone"]["text"] and "小鱼干 ×2，已经放进背包" in r["milestone"]["text"]
    assert r["milestone"]["text"].endswith("橘子送了你「橘子同款小鱼头像框」，已经放进商城的「小动物的礼物」里了")
    assert r["milestone"]["item_id"] == "frame_tangerine" and r["milestone"]["what"] == "橘子同款小鱼头像框"
    assert r["milestones_new"][1]["items"] == [{"id": "dried_fish", "name": "小鱼干", "rarity": "common", "count": 2}]
    assert _bag(client, h) == {"dried_fish": 2}
    # 专属头像框直接变成已拥有（不自动戴上），之后能戴
    st = client.get("/me/state", headers=h).json()
    assert "frame_tangerine" in st["owned"] and "frame_tangerine" not in st["equipped"]
    assert "frame_tangerine" in client.post("/shop/equip", json={"item_id": "frame_tangerine"}, headers=h).json()["equipped"]
    assert r["milestones"]["got"] == 4 and r["milestones"]["next"] == 80
    # 不重复发
    r = client.post("/pets/tangerine/pet", headers=h).json()
    assert r["milestone"] is None and r["milestones_new"] == [] and r["coins"] == coins + 40
    assert _bag(client, h) == {"dried_fish": 2}
    # 再往上：80 送两样收藏品各两件
    _set_affinity(client, h, "tangerine", 79)
    _put(client, h, crucian=1)
    r = client.post("/pets/tangerine/feed", json={"item": "crucian"}, headers=h).json()
    assert r["favorite"] and r["gain"] == 3 and r["milestone"]["at"] == 80
    assert _bag(client, h) == {"dried_fish": 2, "shell": 2, "yarn": 2}
    # 各算各的：另一只从头来
    r = client.post("/pets/momo/pet", headers=h).json()
    assert r["milestones"]["got"] == 0
    # 礼物册
    book = {p["id"]: p for p in client.get("/pets/gifts", headers=h).json()["pets"]}
    t = book["tangerine"]
    assert [m["done"] for m in t["milestones"]] == [True] * 5 + [False] * 3 and t["next_milestone"] == 120
    assert t["frame"] == "frame_tangerine" and t["favorites_known"] == ["crucian"] and t["level_name"] == "知己"
    assert book["momo"]["next_milestone"] == 5 and not any(m["done"] for m in book["momo"]["milestones"])
    assert client.get("/pets/gifts", headers=h).json()["names"]["food_bone"] == "肉骨头"


def test_milestone_frame_not_duplicated_and_last_one(client, login):
    """最后一个门槛过了以后 next 是空的；专属头像框已经有了也不会出错"""
    h = login()
    client.post("/pets/teddy/pet", headers=h)
    uid = _me(client, h)
    with SessionLocal() as db:
        db.add(Owned(user_id=uid, item_id="frame_teddy"))
        db.commit()
    _set_affinity(client, h, "teddy", 400)
    r = client.post("/pets/teddy/pet", headers=h).json()
    assert len(r["milestones_new"]) == 8 and r["milestones"] == {"got": 8, "total": 8, "next": None, "next_what": None}
    assert r["level"] == 5 and r["next"] is None
    bag = _bag(client, h)
    assert bag["pearl"] == 1 and bag["knot"] == 1 and bag["bone"] == 2
    assert client.post("/pets/teddy/pet", headers=h).json()["milestones_new"] == []


# ───────── 每日礼物 ─────────
def test_daily_gift_weights_rarer_when_closer():
    for pet in pets.PETS:
        rare = [k for k in pets.GIFTS[pet] if KEEPS[k][1] == "rare"]
        lo, hi = pets.gift_weights(pet, 2), pets.gift_weights(pet, 5)
        assert set(lo) == set(pets.GIFTS[pet])
        for k in rare:
            assert hi[k] / sum(hi.values()) > lo[k] / sum(lo.values())


def test_daily_gift_goes_to_bag_and_stacks(client, login, monkeypatch):
    from datetime import timedelta

    from app import coins as coinlib

    h = login()
    client.post("/pets/doubao/pet", headers=h)
    _set_affinity(client, h, "doubao", 26)
    real = coinlib.today()
    seen = {}
    for d in range(6):
        monkeypatch.setattr(pets, "today", lambda d=d: real + timedelta(days=d))
        p = {x["id"]: x for x in client.get("/pets", headers=h).json()["pets"]}["doubao"]
        assert p["gift_item"] in pets.GIFTS["doubao"] and p["gift"] == KEEPS[p["gift_item"]][4]
        g = client.post("/pets/doubao/gift", headers=h).json()
        assert g["got"] == 0 and g["item"]["id"] == p["gift_item"] and set(g["item"]) == {"id", "name", "about", "rarity"}
        seen[g["item"]["id"]] = seen.get(g["item"]["id"], 0) + 1
        assert g["count"] == seen[g["item"]["id"]]
        assert client.post("/pets/doubao/gift", headers=h).json()["item"] is None  # 一天一件
    assert _bag(client, h) == seen and sum(seen.values()) == 6
    book = {p["id"]: p for p in client.get("/pets/gifts", headers=h).json()["pets"]}["doubao"]
    assert {d["id"] for d in book["daily"] if d["seen"]} == set(seen)
    # 还没熟的没有礼物
    assert client.post("/pets/momo/gift", headers=h).json() == {"got": 0, "coins": client.get("/bag", headers=h).json()["coins"], "item": None}


# ───────── 兑换 ─────────
def test_redeem_keepsake(client, login):
    h = login()
    # 不卖
    r = client.post("/shop/buy", json={"item_id": "frame_shell"}, headers=h)
    assert r.status_code == 403 and "5 贝壳 + 2 海螺" in r.json()["detail"]
    r = client.post("/shop/buy", json={"item_id": "frame_teddy"}, headers=h)
    assert r.status_code == 403 and "和栗子的亲密度到 50" in r.json()["detail"]
    # 材料不够：写明还差几个，一个都不扣
    _put(client, h, shell=3, shell_conch=2)
    r = client.post("/shop/redeem", json={"item_id": "frame_shell"}, headers=h)
    assert r.status_code == 400 and r.json()["detail"] == "材料不够：贝壳还差 2 个"
    assert _bag(client, h) == {"shell": 3, "shell_conch": 2}
    # 动物的专属物品换不了；不存在的 404
    assert client.post("/shop/redeem", json={"item_id": "frame_teddy"}, headers=h).status_code == 403
    assert client.post("/shop/redeem", json={"item_id": "moon_lamp"}, headers=h).status_code == 404
    # 够了：扣料、已拥有、戴上（顶掉原来的头像框）
    client.post("/shop/buy", json={"item_id": "frame_gold"}, headers=h)
    _put(client, h, shell=4)
    coins = client.get("/bag", headers=h).json()["coins"]
    r = client.post("/shop/redeem", json={"item_id": "frame_shell"}, headers=h).json()
    assert "frame_shell" in r["owned"] and "frame_shell" in r["equipped"] and "frame_gold" not in r["equipped"]
    assert r["coins"] == coins and {i["id"]: i["count"] for i in r["items"]} == {"shell": 2}
    assert client.post("/shop/redeem", json={"item_id": "frame_shell"}, headers=h).status_code == 409
    assert _bag(client, h) == {"shell": 2}
    # 一粒珍珠 + 一枚平安结
    _put(client, h, pearl=1, knot=1)
    assert "frame_pearl" in client.post("/shop/redeem", json={"item_id": "frame_pearl"}, headers=h).json()["equipped"]
    assert _bag(client, h) == {"shell": 2}


def test_keepsake_catalog_consistent():
    from app.catalog import KEEPSAKES, SHOP_ITEMS

    for item, src in KEEPSAKES.items():
        assert item in SHOP_ITEMS and item.startswith("frame_") and SHOP_ITEMS[item][2] == "frame" and len(item) <= 24
        assert ("pet" in src) != ("cost" in src)
        if "pet" in src:
            assert src["pet"] in pets.PETS
        else:
            assert all(k in KEEPS and n > 0 for k, n in src["cost"].items())
    assert Inventory.__table__.c.item_id.type.length >= max(len(k) for k in [*FISH, *KEEPS])
