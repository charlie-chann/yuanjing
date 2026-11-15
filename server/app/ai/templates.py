"""不接大模型时的 AI 内容：本地规则和模板。和应用里 lib/app/muse.dart 是同一套，接口不通时应用自己也能用。"""
import random
import re
from collections import Counter

SCENE_NAMES = {"wealth": "财富", "career": "事业", "looks": "外貌", "health": "健康", "mood": "情绪", "life": "生活", "pet": "宠物"}

NEEDS = {
    "wealth": ("安全感和选择的自由", "你要的不只是数字，是不必为钱委屈自己的底气。先把「我值得」放在「我需要」前面。"),
    "career": ("被看见和自我实现", "你想确认自己的努力有分量。不妨把大目标拆成这周就能迈出的一步。"),
    "looks": ("自我接纳和被喜欢", "你想更喜欢镜子里的自己。好看从放松开始，对自己说话时先温柔一点。"),
    "health": ("安稳和对身体的掌控", "你想和身体重新站在一起。它一直在努力保护你，给它一点休息。"),
    "mood": ("平静和情绪的出口", "你想要心里安静下来。情绪不是要解决的问题，是可以经过的天气。"),
    "life": ("归属感和生活的质感", "你想把日子过成喜欢的样子。先在今天安排一件小小的、只为自己的事。"),
    "pet": ("陪伴和无条件的爱", "你很会爱。你给毛孩子的那份耐心，也值得分一点给自己。"),
}

TITLES = {
    "wealth": ("从容的丰盛者", "钱为我工作，我为热爱生活。"),
    "career": ("走在自己节奏里的人", "我被看见，也被需要。"),
    "looks": ("由内而外发光的人", "我喜欢镜子里的自己。"),
    "health": ("被身体好好爱着的人", "我睡得安稳，醒来有力。"),
    "mood": ("心里有一片静湖的人", "风来了，我也在。"),
    "life": ("把日子过成喜欢样子的人", "我过着自己选择的生活。"),
    "pet": ("被毛孩子选中的人", "我们陪着彼此，慢慢变好。"),
}

AFFIRM = {
    "wealth": ["我值得拥有丰盛。", "金钱以轻松的方式流向我。", "我的价值，一直在增长。"],
    "career": ["我清楚自己要去哪里。", "我的努力，正在被看见。", "机会喜欢准备好的我。"],
    "looks": ["我喜欢镜子里的自己。", "我由内而外地发着光。", "我本来的样子，就很美。"],
    "health": ["我的身体知道如何修复自己。", "每一次呼吸，都在给我力量。", "我温柔地照顾自己。"],
    "mood": ["我允许情绪来，也允许它走。", "我的心，越来越安定。", "今天，我选择平静。"],
    "life": ["我正在过自己选择的生活。", "美好的事，正在向我走来。", "我值得被生活温柔对待。"],
    "pet": ["我的毛孩子健康、快乐、被爱着。", "我们陪着彼此，一天比一天好。"],
}

_STOP = {"希望", "可以", "能够", "一个", "自己", "今天", "每天", "我想", "想要", "我要", "越来", "来越", "顺利", "一切"}


def analyze(wishes: list[tuple[str, str]]) -> dict | None:
    """wishes: [(scene, text)]，新的在前。"""
    if not wishes:
        return None
    counts = Counter(s for s, _ in wishes).most_common()
    top = counts[0][0]
    words: Counter[str] = Counter()
    for _, t in wishes:
        t = re.sub(r"[^一-鿿]", "", t)
        words.update({t[i : i + 2] for i in range(len(t) - 1)} - _STOP)
    repeats = [w for w, n in words.most_common(5) if n >= 2]
    share = counts[0][1] / len(wishes)
    if len(counts) == 1 or share >= 0.6:
        trend = f"你最近的心思很集中，几乎都放在「{SCENE_NAMES[top]}」上。聚焦是显化的开始。"
    else:
        trend = f"你的心愿分布在「{'、'.join(SCENE_NAMES[s] for s, _ in counts[:3])}」几个方面，生活的各个面都在被你照顾。"
    need, advice = NEEDS[top]
    return {"total": len(wishes), "counts": [[s, n] for s, n in counts], "need": need, "advice": advice, "repeats": repeats, "trend": trend}


def identity(top_scene: str | None) -> tuple[str, str]:
    return TITLES.get(top_scene or "life", TITLES["life"])


def moment(recent_scene: str | None) -> str:
    pool = [
        "今天的我，比昨天更相信自己一点点。",
        "慢慢来，比较快。把今天过好，就是在靠近想要的生活。",
        "抬头看了会儿天，觉得一切都来得及。",
        "给自己的小小记录：今天也有好好吃饭、好好呼吸、好好喜欢自己。",
    ]
    if recent_scene in SCENE_NAMES:
        name = SCENE_NAMES[recent_scene]
        pool += [f"今天给「{name}」许了一个愿。写下来的那一刻，心里就亮了一点。", f"把想要的说出口，是我今天做得最勇敢的事。关于{name}，我已经在路上了。"]
    return random.choice(pool)


def diary() -> str:
    a = ["早上醒来时照进来的光", "一杯刚好的热水", "路上遇到的一只小猫", "朋友发来的一句「在吗」", "按时吃上的一顿饭", "自己没有放弃的那一下"]
    b = ["身体一直在好好工作", "有一个可以安心待着的地方", "今天有人对我笑了", "把一件拖了很久的事做完了", "还有想要去的地方", "我愿意对自己温柔"]
    c = ["谢谢今天的自己。", "这些小事，就是生活在爱我。", "我拥有的，比我以为的多。", "明天也请多多关照。"]
    x, y = random.sample(a, 2)
    return f"今天想谢谢三件事：\n一，{x}。\n二，{y}。\n三，{random.choice(b)}。\n{random.choice(c)}"


def praise(text: str) -> str:
    if "谢" in text or "感恩" in text:
        return random.choice(["会感恩的人，日子会越过越亮。", "能看见这些小事，你的心真的很软。", "读完觉得被你的温柔照到了。"])
    if "愿" in text or "想" in text:
        return random.choice(["敢把想要的说出来，已经很了不起。", "这个愿望听起来就会实现。", "宇宙收到了，我也替你开心。"])
    return random.choice(["你认真生活的样子，真的在发光。", "今天的你，值得一朵小红花。", "看到你这样，我也想对自己好一点。", "你比自己以为的更好。", "这份心情很珍贵，谢谢你分享。"])


def affirmations(scenes: list[str], destiny: dict[str, str], single: bool) -> list[str]:
    use = [s for s in SCENE_NAMES if s in scenes] or ["mood", "life"]
    out: list[str] = []
    for s in use:
        pool = AFFIRM[s][:]
        random.shuffle(pool)
        out += pool[: 3 if single else 2]
        d = (destiny.get(s) or "").strip()
        if d:
            out.append(f"我正在成为这样的人：{re.split(r'[。\n]', d)[0]}。")
    out.append("我已经走在路上了。")
    return out


def destiny_draft(wishes: list[str], keys: list[str]) -> str | None:
    if not wishes and not keys:
        return None
    parts = []
    if keys:
        parts.append(f"我的生活里有{'、'.join(keys[:4])}")
    for w in wishes[:3]:
        w = re.sub(r"^(我)?(希望|想要|想|要|愿)", "", w.strip())
        parts.append(re.sub(r"[。！!]$", "", w))
    return "；".join(p for p in parts if p) + "。"
