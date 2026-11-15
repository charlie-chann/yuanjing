"""许愿回应：把用户写的愿望匹配到最合适的意图，再从回应库里挑一条他最近没听过的。

回应库是 tools/wishdb/build.py 生成的 SQLite（131 个意图、955 句、104.8 万条完整回应），不接大模型。

匹配算法：
1. 规范化：全角转半角、去空格和标点、英文转小写。
2. 关键词打分：每个意图有一组关键词，命中一个加「字数的 1.5 次方」，越长越具体分越高；
   被同一意图里更长的已命中关键词包含的短词不重复计分；命中排除词（!开头）的意图直接跳过。
3. 分类加权：和用户选的分类一致的意图乘 1.3；兜底的「xx.general」意图打 6 折，优先具体意图。
4. 最高分不到门槛，就用用户所选分类的兜底意图。
5. 情绪：从用词判断平常、迫切、担心、沉重四种，选对应语气的开场句；少数意图自带默认情绪。
6. 时段：按手机本地时间分早上、白天、傍晚、夜里，选对应的收尾句。
7. 去重：同一个人最近听过的核心句尽量不再出现，同一意图会轮着换说法。
"""
import json
import random
import sqlite3
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .moderation import needs_support

SCENES = ("wealth", "career", "looks", "health", "mood", "life", "pet")

HEAVY = ("难过", "痛苦", "崩溃", "绝望", "撑不住", "去世", "离世", "走了", "癌", "病危", "重症", "抢救", "哭", "心碎", "活不下去", "失去", "离开我", "好难", "太难", "熬不下去", "心疼")
ANXIOUS = ("担心", "害怕", "焦虑", "紧张", "怕", "万一", "能不能", "千万", "不要", "别再", "睡不着", "慌", "忐忑", "不安", "结果", "等通知", "等消息")
EAGER = ("一定", "必须", "马上", "立刻", "尽快", "赶紧", "求求", "拜托", "早日", "快点", "务必", "冲", "!!", "！！")
DEFAULT_MOOD = {"health.surgery": "anxious", "health.checkup": "anxious", "mood.grief": "heavy", "pet.rainbow": "heavy", "pet.lost": "anxious", "pet.sick": "anxious", "health.mental": "heavy"}

ELDERS = ("爸妈", "父母", "爸爸", "妈妈", "奶奶", "爷爷", "外公", "外婆", "姥姥", "姥爷", "老人", "老爸", "老妈")

# 愿望里提到谁：宠物的愿望不该被人的健康类抢走，提到爸妈、孩子的要偏向对应的意图
SUBJECTS = (
    (("猫", "狗", "毛孩子", "宠物", "喵", "汪", "主子", "兔子", "仓鼠", "鹦鹉", "柯基", "泰迪", "金毛", "布偶", "橘猫"), "pet.", 2.0),

    (("儿子", "女儿", "宝宝", "孩子", "小孩"), "health.child", 1.3),
)

PUNCT = set("，。！？、；：,.!?;:\"'“”‘’（）()【】[]《》<>~～…—-_ \t\n")


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).lower()
    return "".join(ch for ch in t if ch not in PUNCT)


def weight(key: str) -> float:
    """关键词的分量：字数的 1.5 次方；一个英文单词按两个字算（offer 不该比「央企」重）"""
    cjk = sum(1 for ch in key if not ch.isascii())
    ascii_words = len([w for w in "".join(ch if ch.isascii() else " " for ch in key).split() if w])
    return (cjk + 2 * ascii_words) ** 1.5


def mood_of(text: str, intent_id: str) -> str:
    raw = unicodedata.normalize("NFKC", text)
    if any(w in raw for w in HEAVY):
        return "heavy"
    if any(w in raw for w in ANXIOUS):
        return "anxious"
    if any(w in raw for w in EAGER) or raw.count("!") >= 2:
        return "eager"
    return DEFAULT_MOOD.get(intent_id, "calm")


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


class WishMatcher:
    def __init__(self, path: Path):
        self.path = path
        self.ok = path.exists()
        self.intents: list[Intent] = []
        self.texts: dict[int, str] = {}
        self.buckets: dict[tuple[str, str, str], list[tuple[int, int]]] = {}
        self._lock = threading.Lock()
        if self.ok:
            self._load()

    def _db(self):
        return sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, check_same_thread=False)

    def _load(self) -> None:
        db = self._db()
        for iid, scene, name, keys in db.execute("SELECT id, scene, name, keys FROM intents"):
            raw = json.loads(keys)
            # 排除词的「!」要在规范化之前拿掉：规范化会把它当标点删掉
            plus = [normalize(k) for k in raw if not k.startswith("!")]
            minus = [normalize(k[1:]) for k in raw if k.startswith("!")]
            self.intents.append(Intent(iid, scene, name, plus, minus))
        self.texts = dict(db.execute("SELECT id, text FROM segments"))
        # 每个意图的「字词画像」：关键词、核心回应句、例句里所有相邻两个字的片段
        import math
        self.profile = {}
        prof_text = {}
        for iid, keys, examples in db.execute("SELECT id, keys, examples FROM intents"):
            parts = [k.lstrip("!") for k in json.loads(keys) if not k.startswith("!")] + json.loads(examples)
            prof_text[iid] = parts
        for iid, t in db.execute("SELECT intent_id, text FROM segments WHERE kind='core'"):
            prof_text[iid].append(t)
        for iid, parts in prof_text.items():
            self.profile[iid] = {g for p in parts for n in [normalize(p)] for g in (n[i : i + 2] for i in range(len(n) - 1))}
        df = {}
        for gs in self.profile.values():
            for g in gs:
                df[g] = df.get(g, 0) + 1
        n = len(self.profile)
        self.idf = {g: math.log(n / c) for g, c in df.items()}
        self.stats = dict(db.execute("SELECT k, v FROM meta"))
        db.close()

    def score(self, text: str, scene: str | None) -> list[tuple[float, Intent]]:
        t = normalize(text)
        scored = []
        for it in self.intents:
            if any(e and e in t for e in it.excludes):
                continue
            hits = sorted({k for k in it.keys if k and k in t}, key=len, reverse=True)
            kept: list[str] = []
            for k in hits:
                if not any(k in longer for longer in kept):
                    kept.append(k)
            s = sum(weight(k) for k in kept)
            # 提到长辈、又在说身体：偏向「父母健康」，而不是泛泛的身体健康
            if it.id == "health.parents" and any(w in t for w in ELDERS) and any(w in t for w in ("健康", "身体", "硬朗", "平安", "长寿")):
                s += 6
            if s <= 0:
                continue
            if it.scene == scene:
                s *= 2.0
            # 宠物类的意图，愿望里没提到宠物、又没选宠物分类时，大幅降权
            if it.scene == "pet" and scene != "pet" and not any(w in t for w in SUBJECTS[0][0]):
                s *= 0.3
            for words, prefix, boost in SUBJECTS:
                if it.id.startswith(prefix) and any(w in t for w in words) and not (prefix != "pet." and "毛孩子" in t):
                    s *= boost
            if it.id.endswith(".general"):
                s *= 0.6
            scored.append((s, it))
        scored.sort(key=lambda x: -x[0])
        return scored

    def similar(self, text: str, scene: str | None) -> tuple[Intent | None, float]:
        """关键词一个都没对上时的兜底：把愿望拆成相邻两个字的片段，和每个意图的关键词、回应句、例句比，
        罕见的片段分量大（像「极光」），常见的分量小（像「希望」）。"""
        grams = {t[i : i + 2] for t in [normalize(text)] for i in range(len(t) - 1)}
        best, best_s = None, 0.0
        for it in self.intents:
            s = sum(self.idf.get(g, 0.0) for g in grams & self.profile[it.id])
            if it.scene == scene:
                s *= 1.5
            if it.id.endswith(".general"):
                s *= 0.6
            if s > best_s:
                best, best_s = it, s
        return best, best_s

    def match(self, text: str, scene: str | None) -> tuple[Intent, float]:
        scored = self.score(text, scene)
        if not scored or scored[0][0] < 1.4:
            near, s = self.similar(text, scene)
            if near is not None and s >= 3.0:
                return near, round(min(0.5, s / 20), 2)
        if scored and scored[0][0] >= 1.4:
            best, top = scored[0][1], scored[0][0]
            second = scored[1][0] if len(scored) > 1 else 0.0
            confidence = min(1.0, top / 8) * (0.5 + 0.5 * (top - second) / top)
            return best, round(confidence, 2)
        fallback = f"{scene if scene in SCENES else 'mood'}.general"
        return next(i for i in self.intents if i.id == fallback), 0.0

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
        mood = mood_of(text, intent.id)
        tod = tod_of(hour)
        rows = self._bucket(intent.id, mood, tod)
        recent = set(recent_cores)
        fresh = [r for r in rows if r[1] not in recent] or rows
        answer_id, _ = random.choice(fresh)
        db = self._db()
        row = db.execute("SELECT opener, core, bridge, closer FROM answers WHERE id=?", (answer_id,)).fetchone()
        db.close()
        return {
            "answer_id": answer_id,
            "intent": intent.id,
            "intent_name": intent.name,
            "scene": intent.scene,
            "mood": mood,
            "tod": tod,
            "confidence": confidence,
            "segments": list(row),
            "lines": [self.texts[s] for s in row],
        }
