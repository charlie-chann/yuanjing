"""许愿回应：把用户写的愿望匹配到最合适的意图，再从回应库里挑一条最近没听过的。

回应库是 tools/wishdb/build.py 生成的 SQLite（约 400 个意图、10 万多条完整回应），不接大模型。
一条回应 = 开场（分类 × 情绪）+ 核心句（意图）+ 行动句（意图）+ 收尾（时段）。

匹配的原则是「宁可说得泛，也不能说错」。按顺序判断：
1. 提到轻生、自伤：不播回应，显示心理援助热线。
2. 希望别人倒霉、消失、遭报应：不顺着说，用 mood.letgo_hurt 接住背后的委屈。
3. 没写出具体内容（「你」「啊啊」「123」）：用所选分类的 xx.blank。
4. 关键词打分：命中一个加「字数的 1.5 次方」，越长越具体分越高；被更长的已命中关键词包含的短词不重复计分；
   命中排除词（!开头）的意图跳过。所选分类里的意图 ×2，兜底意图打折，让具体意图优先。
5. 跨分类要有把握：最高分的意图不在所选分类时，只有分数够高、而且明显高过本分类最好的意图才用它。
6. 关键词一个都没对上：只在所选分类里比字面相似度，门槛高，还要命中至少一个少见的片段；
   不够就用所选分类的 xx.short（两三个字的抽象愿望）或 xx.general。
7. 情绪：从用词判断平常、迫切、担心、沉重四种，选对应语气的开场句；手术、哀悼这类意图自带默认情绪。
8. 时段：按手机本地时间选收尾句。
9. 去重：同一个人最近听过的核心句尽量不再出现。
10. 开场句跟着用户所选的分类走：许愿页每个分类有自己的意象（金池、山顶、孔明灯……），跨分类时不出戏。
"""
import json
import math
import random
import re
import sqlite3
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .moderation import needs_support

SCENES = ("wealth", "career", "looks", "health", "mood", "life", "pet")

# 情绪用词。只收两个字以上、不容易误判的说法（「怕」「哭」「走了」「结果」「不要」单独出现时太常见）
HEAVY = ("难过", "痛苦", "崩溃", "绝望", "撑不住", "熬不下去", "去世", "离世", "过世", "病危", "重症", "抢救", "icu", "心碎", "好难", "太难了", "心疼", "想哭", "大哭", "哭了", "失去了", "离开我", "癌症", "肿瘤", "化疗")
ANXIOUS = ("担心", "害怕", "好怕", "很怕", "焦虑", "紧张", "万一", "千万", "睡不着", "心慌", "慌了", "忐忑", "不安", "等结果", "出结果", "等通知", "等消息", "别出事", "提心吊胆")
EAGER = ("一定要", "必须", "马上", "立刻", "尽快", "赶紧", "求求", "拜托", "早日", "快点", "务必", "冲鸭", "冲冲冲", "!!")
# 旧库没有 intents.mood 这一列时用
LEGACY_MOOD = {"health.surgery": "anxious", "health.checkup": "anxious", "mood.grief": "heavy", "pet.rainbow": "heavy", "pet.lost": "anxious", "pet.sick": "anxious", "health.mental": "heavy"}

ELDERS = ("爸妈", "父母", "爸爸", "妈妈", "奶奶", "爷爷", "外公", "外婆", "姥姥", "姥爷", "老人", "老爸", "老妈")
PET_WORDS = ("猫", "狗", "毛孩子", "宠物", "喵", "汪", "主子", "兔子", "仓鼠", "鹦鹉", "柯基", "泰迪", "金毛", "布偶", "橘猫", "狗狗", "猫咪", "小猫", "小狗", "柴犬", "哈士奇", "比熊", "博美", "英短", "美短", "狸花", "豚鼠", "龙猫", "乌龟", "金鱼", "小鱼", "鱼缸", "守宫", "蜥蜴", "爬宠", "刺猬", "小鸟", "鸟儿", "玄凤", "牡丹鹦鹉")
# 愿望里提到谁：宠物的愿望不该被人的健康类抢走，提到孩子的偏向孩子健康
SUBJECTS = ((PET_WORDS, "pet.", 2.0), (("儿子", "女儿", "宝宝", "孩子", "小孩"), "health.child", 1.3))

# 希望别人不好的愿望：强说法单独出现就算；弱说法要同时提到别人，而且前面没有「不、别、没」
# 「死掉」「恨死」不放这里：「绿植别死掉」「恨死自己了」不是在咒别人
HOSTILE_STRONG = ("报应", "不得好死", "下地狱", "去死", "诅咒", "报复", "活该", "天打雷劈", "断子绝孙", "被车撞", "出车祸", "遭天谴", "尝尝滋味", "尝尝这种滋味", "一辈子单身", "孤独终老", "不得安宁")
# 「分手」「离婚」「后悔」不算：「希望他和小三分手」「他后悔了回来找我」是想复合
HOSTILE_WEAK = ("消失", "倒霉", "倒大霉", "过得不好", "过得很惨", "过得惨", "不幸福", "滚出", "滚蛋", "被开除", "被炒", "破产", "生病", "出事", "吃亏", "被骂", "挂科", "失业", "死掉", "恨死", "变丑", "胖成猪", "被甩", "找不到男朋友", "找不到女朋友", "找不到对象", "嫁不出去", "娶不到", "毕不了业", "早点分", "快点分", "后悔死", "不得好", "长痘", "满脸痘", "遭罪", "受罪", "坐牢", "被抓")
BENIGN = ("病", "痛", "疼", "痘", "斑", "疤", "烦恼", "焦虑", "压力", "失眠", "困难", "霉运", "坏运气", "噩梦", "伤心", "难过", "不开心", "坏情绪")
RECOVER = ("快点好", "快好", "好起来", "康复", "痊愈", "过去", "结束")
OTHERS = ("讨厌的", "对我不好", "欺负我", "伤害我", "背叛我", "骗我", "渣男", "渣女", "前任", "前男友", "前女友", "小三", "他", "她", "那个人", "那些人", "坏人", "仇人", "敌人", "老板", "领导", "上司", "同事", "室友", "婆婆", "后妈", "情敌", "绿茶", "的人", "那个", "那些", "这个人", "抢我", "偷我", "害我", "说我", "骂我", "老赖", "骗子", "小偷")
NEGATORS = ("不", "别", "没", "免", "勿")
SELF = ("我", "自己")

# 没有实际内容的字：去掉它们之后不到两个字，就当没写出具体内容
FILLER = set("啊阿哦噢喔嗯恩呀哈嘿呜唔吧呢吗嘛啦了的地得你我他她它这那个一好")
# 试用时常写的无意义内容
BLANK_WORDS = {"test", "测试", "测试一下", "试试", "试一下", "试一试", "abc", "asd", "qwe", "hello", "hi"}
# 一个字也是完整愿望的：瘦、富、帅……（跨分类也照样配过去）
SINGLE = {"瘦": "looks.slim", "美": "looks.short", "帅": "looks.handsome", "白": "looks.white", "高": "looks.height", "富": "wealth.short", "钱": "wealth.short", "财": "wealth.short", "爱": "mood.lovable", "甜": "life.love", "安": "life.peaceful"}
# 说的是家里人：没提宠物时，不往宠物的意图配
HUMANS = ELDERS + ("老公", "老婆", "爱人", "儿子", "女儿", "孩子", "小孩", "哥哥", "姐姐", "弟弟", "妹妹", "男朋友", "女朋友", "对象", "自己", "本人")

# 容易被子串误命中的说法，匹配前先换掉
MASKS = (("走了好运", "好运"), ("走好运", "好运"), ("走运", "好运"), ("走大运", "好运"))

PUNCT = set("，。！？、；：,.!?;:\"'“”‘’（）()【】[]《》<>~～…—-_ \t\n·@#$%^&*+=|/\\")

KEYWORD_MIN = 2.0  # 至少命中一个两字关键词（2 ** 1.5 ≈ 2.83）
CROSS_MIN, CROSS_RATIO = 4.0, 1.5  # 跨分类：分数至少 4，而且是本分类最好意图的 1.5 倍
SIMILAR_MIN = 6.0  # 字面相似度兜底的门槛


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).lower()
    return "".join(ch for ch in t if ch not in PUNCT)


def weight(key: str) -> float:
    """关键词的分量：字数的 1.5 次方；一个英文单词按两个字算（offer 不该比「央企」重）"""
    cjk = sum(1 for ch in key if not ch.isascii())
    ascii_words = len([w for w in "".join(ch if ch.isascii() else " " for ch in key).split() if w])
    return (cjk + 2 * ascii_words) ** 1.5


def meaningful(text: str) -> str:
    return "".join(ch for ch in normalize(text) if not ch.isdigit() and ch not in FILLER)


def is_blank(text: str) -> bool:
    """调用前已经确认没对上任何关键词，所以短的纯字母（asdfgh、ok）也算没写内容"""
    t, m = normalize(text), meaningful(text)
    return t in BLANK_WORDS or (t.isascii() and t.isalpha() and len(t) <= 8) or (len(set(m)) < 2 and m not in SINGLE)


def is_hostile(text: str) -> bool:
    t = normalize(text).replace("报复性", "")
    if any(w in t for w in HOSTILE_STRONG):
        return True
    for w in HOSTILE_WEAK:
        for m in re.finditer(re.escape(w), t):
            before = t[max(0, m.start() - 3) : m.start()]
            if any(n in before for n in NEGATORS):
                continue
            head, tail = t[: m.start()], t[m.end() : m.end() + 4]
            # 「他的病快点消失」「他生病快点好起来」「霉运消失」是好愿望
            if any(b in head[-4:] for b in BENIGN) or any(r in tail for r in RECOVER):
                continue
            # 说的是别人，不是自己（「我不想失业」不算）
            if any(o in head for o in OTHERS) and not head.endswith(SELF):
                return True
    return False


def mood_of(text: str, intent_id: str, default: str | None = None) -> str:
    raw = unicodedata.normalize("NFKC", text).lower()
    default = default if default is not None else LEGACY_MOOD.get(intent_id)
    if any(w in raw for w in HEAVY):
        return "heavy"
    if any(w in raw for w in ANXIOUS):
        return "anxious" if default != "heavy" else "heavy"
    # 手术、哀悼这类意图，用户写得再急，也用它们自己的语气
    if default in ("heavy", "anxious"):
        return default
    if any(w in raw for w in EAGER) or raw.count("!") >= 2:
        return "eager"
    return default or "calm"


def tod_of(hour: int) -> str:
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 17:
        return "day"
    if 17 <= hour < 21:
        return "evening"
    return "night"


@dataclass
class Intent:
    id: str
    scene: str
    name: str
    keys: list[str]
    excludes: list[str]
    mood: str | None = None

    @property
    def generic(self) -> bool:
        return self.id.endswith((".general", ".short", ".blank"))


class WishMatcher:
    def __init__(self, path: Path):
        self.path = path
        self.ok = path.exists()
        self.intents: list[Intent] = []
        self.by_id: dict[str, Intent] = {}
        self.texts: dict[int, str] = {}
        self.openers: dict[tuple[str, str], list[int]] = {}
        self.buckets: dict[tuple[str, str, str], list[tuple[int, int]]] = {}
        self._lock = threading.Lock()
        if self.ok:
            self._load()

    def _db(self):
        return sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, check_same_thread=False)

    def _load(self) -> None:
        db = self._db()
        cols = {r[1] for r in db.execute("PRAGMA table_info(intents)")}
        mood_col = "mood" if "mood" in cols else "NULL"
        prof_text: dict[str, list[str]] = {}
        for iid, scene, name, keys, examples, mood in db.execute(f"SELECT id, scene, name, keys, examples, {mood_col} FROM intents"):
            raw = json.loads(keys)
            # 排除词的「!」要在规范化之前拿掉：规范化会把它当标点删掉
            plus = [normalize(k) for k in raw if not k.startswith("!")]
            minus = [normalize(k[1:]) for k in raw if k.startswith("!")]
            it = Intent(iid, scene, name, [k for k in plus if k], [k for k in minus if k], mood or LEGACY_MOOD.get(iid))
            self.intents.append(it)
            self.by_id[iid] = it
            # 不放例句：例句里有宠物和家人的名字（豆豆、团子），会被当成「少见的片段」误配
            prof_text[iid] = [k.lstrip("!") for k in raw if not k.startswith("!")]
        self.texts = dict(db.execute("SELECT id, text FROM segments"))
        for sid, scene, mood in db.execute("SELECT id, scene, mood FROM segments WHERE kind='opener'"):
            self.openers.setdefault((scene, mood), []).append(sid)
        for iid, t in db.execute("SELECT intent_id, text FROM segments WHERE kind='core'"):
            prof_text[iid].append(t)
        # 每个意图的「字词画像」：关键词和核心句里所有相邻两个字的片段，罕见的片段分量大
        self.profile = {iid: {g for p in parts for n in [normalize(p)] for g in (n[i : i + 2] for i in range(len(n) - 1))} for iid, parts in prof_text.items()}
        df: dict[str, int] = {}
        for gs in self.profile.values():
            for g in gs:
                df[g] = df.get(g, 0) + 1
        n = len(self.profile)
        self.idf = {g: math.log(n / c) for g, c in df.items()}
        self.rare_idf = math.log(n / 3)  # 最多出现在三个意图里的片段算「少见」
        self.stats = dict(db.execute("SELECT k, v FROM meta"))
        db.close()

    def special(self, scene: str | None, kind: str) -> Intent:
        s = scene if scene in SCENES else "mood"
        return self.by_id.get(f"{s}.{kind}") or self.by_id[f"{s}.general"]

    def score(self, text: str, scene: str | None) -> list[tuple[float, Intent]]:
        t = normalize(text)
        for a, b in MASKS:
            t = t.replace(a, b)
        has_pet = any(w in t for w in PET_WORDS)
        # 「爸爸的病快点好」「妈妈心脏手术」：说的是人，不是宠物
        no_pet = not has_pet and (scene != "pet" or any(w in t for w in HUMANS))
        scored = []
        for it in self.intents:
            if any(e in t for e in it.excludes):
                continue
            hits = sorted({k for k in it.keys if k in t}, key=len, reverse=True)
            kept: list[str] = []
            for k in hits:
                if not any(k in longer for longer in kept):
                    kept.append(k)
            s = sum(weight(k) for k in kept)
            # 提到长辈、又在说身体：偏向「父母健康」，而不是泛泛的身体健康
            if it.id == "health.parents" and any(w in t for w in ELDERS) and any(w in t for w in ("健康", "身体", "硬朗", "平安", "长寿")):
                s += 6
            if s < KEYWORD_MIN:
                continue
            if it.scene == scene:
                s *= 2.0
            # 宠物类的意图，愿望里没提到宠物、又没选宠物分类时，大幅降权
            if it.scene == "pet" and no_pet:
                continue
            for words, prefix, boost in SUBJECTS:
                if it.id.startswith(prefix) and any(w in t for w in words) and not (prefix != "pet." and "毛孩子" in t):
                    s *= boost
            if it.id.endswith(".general"):
                s *= 0.6
            elif it.id.endswith(".short"):
                s *= 0.8
            scored.append((s, it))
        scored.sort(key=lambda x: -x[0])
        return scored

    def similar(self, text: str, scene: str | None) -> tuple[Intent | None, float]:
        """关键词一个都没对上时的兜底：只在所选分类里，把愿望拆成相邻两个字的片段，和每个意图的关键词、
        核心句比，罕见的片段分量大（像「极光」），常见的分量小（像「希望」）。至少要命中一个少见的片段。"""
        t = normalize(text)
        grams = {t[i : i + 2] for i in range(len(t) - 1)}
        best, best_s = None, 0.0
        for it in self.intents:
            if scene in SCENES and it.scene != scene:
                continue
            if it.generic:
                continue
            common = grams & self.profile.get(it.id, set())
            if not any(self.idf.get(g, 0.0) >= self.rare_idf for g in common):
                continue
            s = sum(self.idf.get(g, 0.0) for g in common)
            if s > best_s:
                best, best_s = it, s
        return (best, best_s) if best_s >= SIMILAR_MIN else (None, 0.0)

    def match(self, text: str, scene: str | None) -> tuple[Intent, float]:
        if is_hostile(text) and "mood.letgo_hurt" in self.by_id:
            return self.by_id["mood.letgo_hurt"], 1.0
        single = self.by_id.get(SINGLE.get(meaningful(text), ""))
        if single:
            return single, 0.5
        scored = self.score(text, scene)
        # 没写出具体内容：一个关键词也没对上，才算（「想他」「有钱」虽短，也是愿望）
        if is_blank(text) and not scored:
            return self.special(scene, "blank"), 0.0
        if scored and scene in SCENES and scored[0][1].scene != scene:
            # 跨分类要有把握：分数够高，而且明显高过本分类最好的意图，才跳过去；
            # 或者本分类什么都没对上，而愿望几乎就是那个说法本身（在事业里写「2027暴富」，在宠物里写「脱单」）。
            # 「爷爷在那边好好的」里的「好好的」只是一小部分，不能把它带去生活的通用回应
            t = normalize(text)
            core = meaningful(text)

            def covers(it: Intent) -> bool:
                # 数字不算（「2027」不能把「2027暴富」带去新年）
                longest = max((sum(not ch.isdigit() for ch in k) for k in it.keys if k in t), default=0)
                return longest >= 0.5 * max(1, len(core))

            # 本分类只对上了通用意图（「早日」碰到 career.short）时，不挡跨分类的具体意图
            in_s = next((s for s, it in scored if it.scene == scene and not it.generic), 0.0)
            ok = lambda s, it: it.scene == scene or (
                (not it.generic and s >= CROSS_MIN and s >= CROSS_RATIO * in_s)
                # 别的分类的 general 是「心想事成」这类万能话，不如用本分类自己的；short 带着分类的意思（暴富、变美）
                or (in_s == 0 and covers(it) and not it.id.endswith(".general"))
            )
            # 没把握的跨分类候选都拿掉：退回本分类最好的意图；本分类一个都没对上，就交给下面的兜底。
            # 本分类的通用意图排在有把握的跨分类意图后面（在情绪里写「健康平安」，给健康的回应）
            first = next((i for i, (s, it) in enumerate(scored) if ok(s, it) and not (it.scene == scene and it.generic)), None)
            if first is None:
                first = next((i for i, (s, it) in enumerate(scored) if ok(s, it)), None)
            scored = [] if first is None else [scored[first]] + [x for x in scored[first + 1 :] if x[1].scene == scene]
        if scored:
            top, best = scored[0]
            second = scored[1][0] if len(scored) > 1 else 0.0
            confidence = min(1.0, top / 8) * (0.5 + 0.5 * (top - second) / top)
            return best, round(confidence, 2)
        near, s = self.similar(text, scene)
        if near is not None:
            return near, round(min(0.5, s / 30), 2)
        return self.special(scene, "short" if len(meaningful(text)) <= 4 else "general"), 0.0

    def _bucket(self, intent_id: str, mood: str, tod: str) -> list[tuple[int, int]]:
        key = (intent_id, mood, tod)
        with self._lock:
            if key not in self.buckets:
                db = self._db()
                self.buckets[key] = list(db.execute("SELECT id, core FROM answers WHERE intent_id=? AND mood=? AND tod=?", key))
                db.close()
                if len(self.buckets) > 3000:
                    self.buckets.pop(next(iter(self.buckets)))
            return self.buckets[key]

    def answer(self, text: str, scene: str | None, hour: int, recent_cores: list[int]) -> dict:
        if needs_support(text):
            return {"support": True}
        intent, confidence = self.match(text, scene)
        mood = mood_of(text, intent.id, intent.mood)
        tod = tod_of(hour)
        rows = self._bucket(intent.id, mood, tod)
        recent = set(recent_cores)
        fresh = [r for r in rows if r[1] not in recent] or rows
        answer_id, _ = random.choice(fresh)
        db = self._db()
        row = list(db.execute("SELECT opener, core, bridge, closer FROM answers WHERE id=?", (answer_id,)).fetchone())
        db.close()
        # 开场句带着分类的意象，跟用户所选的分类走
        if scene in SCENES and scene != intent.scene and self.openers.get((scene, mood)):
            row[0] = random.choice(self.openers[(scene, mood)])
        return {
            "answer_id": answer_id,
            "intent": intent.id,
            "intent_name": intent.name,
            "scene": intent.scene,
            "mood": mood,
            "tod": tod,
            "confidence": confidence,
            "segments": row,
            "lines": [self.texts[s] for s in row],
        }
