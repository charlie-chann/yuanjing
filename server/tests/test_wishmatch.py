"""许愿回应的匹配准确率。愿望都是手写的口语说法：
- 每个意图自带的例句（tools/wishdb/data/*.txt 里的 ? 行）
- CASES：早先另写的口语愿望
- wish_cases.tsv、wish_cases_holdout.tsv：盲写的愿望（写的人只看过意图名单），含刁钻、负面、无意义、错别字的说法
- REGRESSION：真实测出来答非所问的愿望
最要紧的指标是「答非所问」：结果既不在可接受的意图里，也不是所选分类的通用回应。
改关键词或打分规则后跑：.venv/bin/python -m pytest tests/test_wishmatch.py -q
"""
import json
import sqlite3
from pathlib import Path

import pytest

from app.config import settings
from app.wishmatch import WishMatcher, is_blank, is_hostile, mood_of, tod_of

pytestmark = pytest.mark.skipif(not settings.wish_db.exists(), reason="回应库还没生成：python3 tools/wishdb/build.py")


@pytest.fixture(scope="module")
def m():
    return WishMatcher(settings.wish_db)


CASES = [

 ('希望下个月能发年终奖，好过年', 'wealth', ['wealth.bonus']), ('房贷压力好大，希望早点还完', 'wealth', ['wealth.debt']),
 ('想有自己的一个小家，有个大阳台', 'wealth', ['wealth.house']), ('希望奶茶店生意火爆', 'wealth', ['wealth.business','wealth.restaurant']),
 ('愿我今年拿下省考', 'career', ['career.civil']), ('三月的复试一定要过啊', 'career', ['career.postgrad','career.retest']),
 ('周五终面，求顺利', 'career', ['career.interview']), ('不想再被老板骂了', 'career', ['career.colleague','career.boss','career.bully']),
 ('想做自己喜欢的工作，不想上班了', 'career', ['career.passion']), ('明天开题报告顺利', 'career', ['career.thesis']),
 ('夏天之前瘦到九十斤', 'looks', ['looks.slim']), ('额头的痘痘快消失吧', 'looks', ['looks.skin','looks.acne']),
 ('发际线不要再后移了', 'looks', ['looks.hair','looks.hairloss']), ('想练出腹肌', 'looks', ['looks.body','looks.abs']),
 ('妈妈下周做手术，一定要顺利', 'health', ['health.surgery']), ('希望我的甲状腺结节是良性的', 'health', ['health.checkup','health.nodule','health.biopsy']),
 ('今晚能睡个好觉', 'health', ['health.sleep']), ('试管这次一定要成功', 'health', ['health.pregnancy','health.ivf']),
 ('我想戒掉熬夜', 'health', ['health.sleep','health.schedule']), ('老爸血压稳定下来', 'health', ['health.chronic','health.pressure','health.parents']),
 ('不想再为小事焦虑了', 'mood', ['mood.anxiety']), ('想忘掉那个人', 'mood', ['mood.breakup']),
 ('外婆去年走了，好想她', 'mood', ['mood.grief']), ('我想变得勇敢一点', 'mood', ['mood.confidence','mood.courage']),
 ('今年能遇到正缘', 'life', ['life.single']), ('希望他能回来找我', 'life', ['life.reunite']),
 ('儿子期末考好一点', 'life', ['life.kids']), ('十月去冰岛看极光', 'life', ['life.travel','life.sky','life.abroad_trip']),
 ('抢到周杰伦演唱会的票', 'life', ['life.concert']), ('我们家早点搬进新房', 'life', ['life.home']),
 ('团子的病快点好起来', 'pet', ['pet.sick']), ('希望豆豆回家', 'pet', ['pet.lost']), ('咪咪在喵星要快乐', 'pet', ['pet.rainbow']),
 ('想养一只布偶猫', 'pet', ['pet.adopt','pet.want']), ('两只猫别再打架了', 'pet', ['pet.together']),
 ('希望这个季度业绩第一', 'career', ['career.recognition','wealth.deal','career.sales']), ('愿老板给我涨点薪水', 'wealth', ['wealth.raise']),
 ('卡里能多点余额', 'wealth', ['wealth.save','wealth.general','wealth.rent']), ('客户赶紧把钱打过来', 'wealth', ['wealth.payment']),
 ('新开的面馆客人多一点', 'wealth', ['wealth.business','wealth.restaurant']), ('今年能把车贷结清', 'wealth', ['wealth.debt']),
 ('一建考试一次过', 'career', ['career.cert']), ('笔试过了就好', 'career', ['career.interview','career.exam','career.written']),
 ('考上心仪的研究生学校', 'career', ['career.postgrad','career.retest']), ('这周的汇报别出错', 'career', ['career.speech','career.project']),
 ('想换一个不那么累的工作', 'career', ['career.switch','career.balance']), ('小红书涨到一万粉', 'wealth', ['wealth.creator']),
 ('腿再细一点', 'looks', ['looks.body','looks.slim','looks.legs']), ('不想再长白头发了', 'looks', ['looks.hair','looks.gray_hair']),
 ('鼻子上的黑头没有了', 'looks', ['looks.skin','looks.pores']), ('婚礼那天皮肤状态好', 'looks', ['looks.wedding','looks.skin']),
 ('姥姥平平安安', 'health', ['health.parents','health.longevity']), ('胃镜结果没问题', 'health', ['health.checkup']),
 ('宝宝的湿疹快好', 'health', ['health.child','health.recover','health.child_sick','health.allergy']), ('我想每天运动半小时', 'health', ['health.exercise']),
 ('不要再半夜醒来', 'health', ['health.sleep']), ('老公戒烟成功', 'health', ['health.quit']),
 ('别再因为工作失眠了', 'health', ['health.sleep']), ('膝盖别再疼了', 'health', ['health.pain']),
 ('希望自己不要那么敏感', 'mood', ['mood.strong','mood.anxiety','mood.stable','mood.calm','mood.sensitive']), ('不再想起他', 'mood', ['mood.breakup']),
 ('能心平气和地过日子', 'mood', ['mood.calm','mood.stable']), ('爷爷在那边好好的', 'mood', ['mood.grief']),
 ('想对自己温柔一点', 'mood', ['mood.selflove']), ('撑过这段最难的日子', 'mood', ['mood.hope']),
 ('明年春天把婚结了', 'life', ['life.marriage']), ('女儿顺利考上高中', 'life', ['life.kids','career.gaokao']),
 ('和室友好好相处', 'life', ['life.friend','life.home','life.roommate','life.social']), ('出国旅游签证顺利', 'life', ['life.visa','life.travel']),
 ('去成都吃火锅看熊猫', 'life', ['life.travel']), ('我们一家人身体健康开开心心', 'life', ['life.family','health.general','mood.happy','life.peaceful']),
 ('布丁的皮肤病快点好', 'pet', ['pet.weight','pet.sick','pet.skin']), ('小黑别再挑食了', 'pet', ['pet.behave','pet.picky']),
 ('橘猫长命百岁', 'pet', ['pet.long','pet.health']), ('流浪狗都有人领养', 'pet', ['pet.adopt']),
 ('这个月的工资能多发一点', 'wealth', ['wealth.raise','wealth.income']), ('早日攒够五十万', 'wealth', ['wealth.save']),
 ('理财不要再亏了', 'wealth', ['wealth.invest','wealth.spend']), ('网店销量翻倍', 'wealth', ['wealth.business','wealth.creator','wealth.ecommerce']),
 ('能还上欠朋友的钱', 'wealth', ['wealth.debt']), ('中个五百万', 'wealth', ['wealth.lottery']),
 ('想给妈妈换个大房子', 'wealth', ['wealth.family','wealth.house']), ('甲方别再改需求了', 'career', ['career.project','career.colleague']),
 ('事业单位面试第一名', 'career', ['career.civil','career.interview']), ('保住现在的工作', 'career', ['career.layoff']),
 ('科目三一把过', 'career', ['career.exam','career.driving']), ('雅思考出七分', 'career', ['career.abroad','career.language']),
 ('早点找到实习', 'career', ['career.job','career.layoff','career.internship']), ('写的书能出版', 'career', ['career.publish']),
 ('双眼皮自然一点', 'looks', ['looks.eyes','looks.face']), ('肚子上的肉没了', 'looks', ['looks.slim','looks.belly']),
 ('牙齿变整齐', 'looks', ['looks.teeth']), ('头发长得快一点', 'looks', ['looks.hair']),
 ('爸爸的心脏支架手术成功', 'health', ['health.surgery']), ('孩子退烧', 'health', ['health.child','health.recover','health.child_sick','health.allergy']),
 ('结节不要再长大', 'health', ['health.checkup','health.chronic','health.nodule']), ('坚持游泳一百天', 'health', ['health.exercise']),
 ('这次能怀上', 'health', ['health.pregnancy']), ('不再痛风', 'health', ['health.chronic','health.pain','health.gout']),
 ('不要再自我怀疑', 'mood', ['mood.confidence','mood.selflove','mood.strong']), ('从失恋里走出来', 'mood', ['mood.breakup']),
 ('别人说什么我都不在乎', 'mood', ['mood.strong']), ('每天都有好心情', 'mood', ['mood.happy','mood.short']),
 ('不再一个人吃饭', 'mood', ['mood.lonely','life.single']), ('放过自己', 'mood', ['mood.selflove','mood.forgive']),
 ('男朋友早点求婚', 'life', ['life.marriage']), ('异地快点结束', 'life', ['life.longdist']),
 ('全家人去海南过年', 'life', ['life.travel','life.family','life.sea']), ('邻居别再装修了', 'life', ['life.home','life.roommate']),
 ('孩子不再叛逆', 'life', ['life.kids']), ('跟喜欢的人有结果', 'life', ['life.crush','life.marriage','life.love']),
 ('狗狗做完手术顺利醒来', 'pet', ['pet.sick','pet.surgery']), ('猫咪别再掉毛了', 'pet', ['pet.weight','pet.health','pet.skin']),
 ('早日遇到我的小猫', 'pet', ['pet.adopt','pet.want','pet.general']), ('想再见它一面', 'pet', ['pet.rainbow','pet.reunite']),
]


def test_library_size(m):
    assert int(m.stats["answers"]) >= 100_000
    assert int(m.stats["distinct"]) == int(m.stats["answers"])  # 每一条完整回应都不重复
    assert int(m.stats["intents"]) >= 380


def test_own_examples(m):
    db = sqlite3.connect(settings.wish_db)
    ex = [(iid, scene, e) for iid, scene, exs in db.execute("select id, scene, examples from intents") for e in json.loads(exs)]
    ok = sum(m.match(e, scene)[0].id == iid for iid, scene, e in ex)
    assert ok / len(ex) >= 0.95, f"例句准确率 {ok}/{len(ex)}"


def test_spoken_wishes(m):
    wrong = [(t, want, m.match(t, s)[0].id) for t, s, want in CASES if m.match(t, s)[0].id not in want]
    assert len(wrong) <= len(CASES) * 0.05, wrong


def generic(scene: str) -> set[str]:
    return {f"{scene}.general", f"{scene}.short", f"{scene}.blank"}


def load_cases(name: str = "wish_cases.tsv") -> list[tuple[str, str, list[str]]]:
    rows = []
    for line in (Path(__file__).parent / name).read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            text, scene, want = line.split("\t")
            rows.append((text, scene, want.split(",")))
    return rows


# wish_cases.tsv：1,088 条盲写愿望，照着它补过关键词（调前：具体意图 84.0%，答非所问 9.7%）
# wish_cases_holdout.tsv：433 条，在上面调完之后另写的独立验收集（第一次跑：具体意图 89.8%，答非所问 6.0%）
@pytest.mark.parametrize("name,min_n", [("wish_cases.tsv", 900), ("wish_cases_holdout.tsv", 400)])
def test_blind_cases(m, name, min_n):
    cases = load_cases(name)
    assert len(cases) >= min_n
    res = [(t, s, want, m.match(t, s)[0].id) for t, s, want in cases]
    hit = [r for r in res if r[3] in r[2]]
    wrong = [r for r in res if r[3] not in r[2] and r[3] not in generic(r[1])]
    assert len(wrong) <= len(res) * 0.02, f"答非所问 {len(wrong)}/{len(res)}：{wrong[:40]}"
    assert len(hit) >= len(res) * 0.85, f"具体意图命中 {len(hit)}/{len(res)}"


# 真实测出来答非所问的愿望：（愿望，分类，可以接受的意图；空表示所选分类的通用回应也行）
REGRESSION = [
    ("所有对我不好的人都受到报应", "mood", ["mood.letgo_hurt"]),
    ("讨厌的人明天消失啦", "mood", ["mood.letgo_hurt"]),
    ("希望前男友过得不好", "mood", ["mood.letgo_hurt"]),
    ("让渣男倒大霉", "life", ["mood.letgo_hurt"]),
    ("希望世界和平", "life", []),
    ("希望明天不下雨", "life", []),
    ("游戏上王者", "life", []),
    ("我想去火星", "life", []),
    ("希望中国队夺冠", "life", []),
    ("希望我的绿植活下来", "life", []),
    ("想要一台新iPhone", "wealth", []),
    ("希望老板走了好运", "career", []),
    ("胸部大到C杯", "looks", []),
    ("赚钱", "wealth", ["wealth.short", "wealth.income"]),
    ("2027暴富", "career", ["wealth.short"]),
    ("健康平安", "mood", ["health.short", "health.general", "mood.general"]),
    ("工作顺顺利利", "career", ["career.general", "career.short"]),
    ("暴富", "wealth", ["wealth.short", "wealth.freedom", "wealth.lottery"]),
    ("美丽", "looks", ["looks.short", "looks.general"]),
]
FORBIDDEN = {  # 这些愿望绝对不能落到的意图
    "希望世界和平": "pet.", "希望明天不下雨": "health.", "游戏上王者": "health.", "我想去火星": "life.visa",
    "希望中国队夺冠": "wealth.", "希望我的绿植活下来": "pet.", "希望老板走了好运": "mood.grief",
}


@pytest.mark.parametrize("text,scene,want", REGRESSION)
def test_regression(m, text, scene, want):
    got = m.match(text, scene)[0].id
    if want:
        assert got in want, got
    else:
        assert got.startswith(scene + ".") or got in want, got
    bad = FORBIDDEN.get(text)
    assert not (bad and got.startswith(bad)), got


def test_hostile_and_blank():
    assert is_hostile("所有对我不好的人都受到报应") and is_hostile("讨厌的人明天消失啦") and is_hostile("希望她过得不好")
    assert not any(is_hostile(t) for t in ("希望他和小三分手", "希望他的病快点消失", "希望他不要生病", "霉运消失", "我不想失业"))
    assert all(is_blank(t) for t in ("你", "123", "啊啊啊", "好的"))
    assert not any(is_blank(t) for t in ("平安", "采访", "暴富"))


def test_fallback_to_category(m):
    assert m.match("嗯嗯", "career")[0].id == "career.blank"
    assert m.match("呜呜呜", "pet")[0].id == "pet.blank"
    assert m.match("你", "life")[0].id == "life.blank"


def test_cross_scene_opener_follows_chosen_scene(m):
    r = m.answer("希望妈妈手术顺利", "wealth", 10, [])
    assert r["intent"] == "health.surgery"
    assert r["segments"][0] in m.openers[("wealth", r["mood"])]


def test_mood_and_time():
    assert mood_of("妈妈的病一定要快点好", "health.recover") == "eager"
    assert mood_of("好担心明天的结果", "health.checkup") == "anxious"
    assert mood_of("外婆走了，好难过", "mood.grief") == "heavy"
    assert mood_of("希望顺利", "health.surgery") == "anxious"  # 手术类默认是担心
    assert mood_of("早日走出来", "mood.grief", "heavy") == "heavy"  # 哀悼类再急也用沉重的语气
    assert mood_of("希望老板走了好运", "career.general") == "calm"  # 「走了」不再算沉重
    assert mood_of("别怕，会好的", "health.general") == "calm"  # 单独的「怕」不算担心
    assert [tod_of(h) for h in (7, 13, 19, 23)] == ["morning", "day", "evening", "night"]


def test_answer_rotates_core_lines(m):
    seen = []
    for _ in range(5):
        r = m.answer("今年考研上岸", "career", 9, seen)
        assert r["intent"] == "career.postgrad" and len(r["lines"]) == 4
        seen.append(r["segments"][1])
    assert len(set(seen)) == 5  # 连着许五次，五句核心句都不一样


def test_crisis_goes_to_support(m):
    assert m.answer("我不想活了", "mood", 23, [])["support"]
