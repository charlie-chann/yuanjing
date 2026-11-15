"""把 data/ 里写好的愿望意图和回应句，组合成完整的回应库（SQLite），给后端用。

一条完整回应 = 开场（按分类和情绪） + 核心句（按意图） + 行动句（按意图） + 收尾（按时段）。
每个意图、每种情绪、每个时段各取 ANSWERS_PER_BUCKET 条不重复的组合，写进 answers 表。
每一句都单独存一行（segments 表），逐句录音，回应播放时按四段依次放。

句子编号是稳定的：录音文件按编号命名（server/data/wish_voice/<编号>.m4a），所以编号记在
segment_ids.tsv 里，同一句话每次生成都拿到同一个编号；新句子接着往后编，已经录好的句子不用重录。

用法：
  python3 build.py [输出路径]      默认输出 server/data/wish_answers.db
  python3 build.py --check 分类     只检查某个分类的素材格式，不生成（写素材时用）
"""
import json
import random
import re
import sqlite3
import sys
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
REGISTRY = HERE / "segment_ids.tsv"
DEFAULT_OUT = HERE.parents[1] / "server" / "data" / "wish_answers.db"
SCENES = ("wealth", "career", "looks", "health", "mood", "life", "pet")
MOODS = ("calm", "eager", "anxious", "heavy")
TODS = ("morning", "day", "evening", "night")
ANSWERS_PER_BUCKET = 16
MIN_CORES, MIN_ACTIONS, MIN_EXAMPLES = 15, 6, 4
# 每个分类都要有的特殊意图：general 兜底、short 两三个字的抽象愿望、blank 没写出具体内容
SPECIAL = ("general", "short", "blank")
# 录音不念人名和「他/她」（不知道用户说的是谁）；「其他」「他人」可以
PRONOUN = re.compile(r"(?<!其)[他她](?!人)")


def key_len(k: str) -> int:
    """关键词的有效长度：一个汉字算 1，一个英文单词或数字串算 2"""
    cjk = sum(1 for ch in k if not ch.isascii())
    words = len([w for w in "".join(ch if ch.isascii() else " " for ch in k).split() if w])
    return cjk + 2 * words


def check_line(where: str, text: str, errors: list[str]) -> None:
    n = len(re.sub(r"[，。！？、；：,.!?;:\s「」“”…—]", "", text))
    if not 6 <= n <= 42:
        errors.append(f"{where} 字数 {n} 不在 6～42：{text}")
    if PRONOUN.search(text):
        errors.append(f"{where} 出现了他/她：{text}")


def parse_scene(scene: str, errors: list[str]) -> list[dict]:
    intents, cur = [], None
    for no, raw in enumerate((DATA / f"{scene}.txt").read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        where = f"{scene}.txt:{no}"
        if line.startswith("@"):
            head, _, keys = line[1:].partition("|")
            iid, name = head.split(None, 1)
            if not iid.startswith(scene + "."):
                errors.append(f"{where} 意图编号要以 {scene}. 开头：{iid}")
            cur = {"id": iid, "scene": scene, "name": name.strip(), "keys": keys.split(), "cores": [], "actions": [], "examples": [], "mood": None}
            intents.append(cur)
            for k in cur["keys"]:
                if key_len(k.lstrip("!")) < 2:
                    errors.append(f"{where} 关键词太短（至少两个字）：{k}")
            continue
        if cur is None:
            errors.append(f"{where} 在第一个 @ 之前：{raw}")
            continue
        tag, body = line[:2], line[2:].strip()
        if tag == "- ":
            check_line(where, body, errors)
            cur["cores"].append(body)
        elif tag == "> ":
            check_line(where, body, errors)
            cur["actions"].append(body)
        elif tag == "? ":
            cur["examples"].append(body)
        elif tag == "~ ":
            if body not in MOODS:
                errors.append(f"{where} 默认情绪只能是 {MOODS}：{body}")
            cur["mood"] = body
        else:
            errors.append(f"{where} 看不懂这一行：{raw}")
    ids = [i["id"] for i in intents]
    for s in SPECIAL:
        if f"{scene}.{s}" not in ids:
            errors.append(f"{scene}.txt 缺少 {scene}.{s}")
    for i in intents:
        for kind, need in (("cores", MIN_CORES), ("actions", MIN_ACTIONS), ("examples", MIN_EXAMPLES)):
            if i["id"].endswith(".blank") and kind == "examples":
                continue
            if len(i[kind]) < need:
                errors.append(f"{i['id']} 的 {kind} 只有 {len(i[kind])} 条，至少 {need}")
        for kind in ("cores", "actions"):
            if len(set(i[kind])) != len(i[kind]):
                errors.append(f"{i['id']} 的 {kind} 有重复的句子")
        if not i["keys"] and not i["id"].endswith(".blank"):
            errors.append(f"{i['id']} 没有关键词")
    return intents


def parse_intents() -> list[dict]:
    errors: list[str] = []
    intents = [i for s in SCENES for i in parse_scene(s, errors)]
    ids = [i["id"] for i in intents]
    dup = {x for x in ids if ids.count(x) > 1}
    if dup:
        errors.append(f"意图编号重复：{dup}")
    if errors:
        raise SystemExit("素材有问题：\n" + "\n".join(errors[:80]) + (f"\n……共 {len(errors)} 处" if len(errors) > 80 else ""))
    return intents


def parse_segments():
    out = {"opener": {}, "closer": {}}
    key = None
    for raw in (DATA / "segments.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.fullmatch(r"\[(opener|bridge|closer)\s+([a-z ]+)\]", line)
        if m:
            # 旧格式里按分类共用的行动句（bridge）不再使用，现在每个意图有自己的行动句
            key = (m.group(1), tuple(m.group(2).split())) if m.group(1) != "bridge" else None
            if key:
                out[key[0]].setdefault(key[1], [])
            continue
        if key:
            out[key[0]][key[1]].append(line)
    for s in SCENES:
        for mo in MOODS:
            assert len(out["opener"].get((s, mo), [])) >= 4, f"开场 {s} {mo} 不够"
    for t in TODS:
        assert len(out["closer"].get((t,), [])) >= 8, f"收尾 {t} 不够"
    return out


class Ids:
    """句子编号表：同一个位置的同一句话永远是同一个编号。

    先按（种类、归属、原文）找；找不到再按原文找一个还没被这次用到的旧编号（句子挪了位置，录音照样能用）；
    都没有就发新编号。"""

    def __init__(self, path: Path, seed_db: Path):
        self.path = path
        self.by_key: dict[tuple[str, str, str], int] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                sid, kind, owner, text = line.split("\t")
                self.by_key[(kind, owner, text)] = int(sid)
        elif seed_db.exists():
            # 第一次：从旧库里接过编号，已经录好的 955 句不用重录
            db = sqlite3.connect(seed_db)
            for sid, kind, scene, mood, tod, intent, text in db.execute("SELECT id, kind, scene, mood, tod, intent_id, text FROM segments"):
                self.by_key[(kind, owner_of(kind, scene, mood, tod, intent), text)] = sid
            db.close()
        self.by_text: dict[str, list[int]] = {}
        for (_, _, text), sid in sorted(self.by_key.items(), key=lambda x: x[1]):
            self.by_text.setdefault(text, []).append(sid)
        self.next = max(self.by_key.values(), default=0) + 1
        self.used: set[int] = set()
        self.rows: list[tuple[int, str, str, str]] = []

    def get(self, kind: str, owner: str, text: str) -> int:
        sid = self.by_key.get((kind, owner, text))
        if sid is None or sid in self.used:
            sid = next((s for s in self.by_text.get(text, []) if s not in self.used), None)
        if sid is None:
            sid, self.next = self.next, self.next + 1
        self.used.add(sid)
        self.rows.append((sid, kind, owner, text))
        return sid

    def save(self) -> None:
        # 删掉的句子也留在表里：它们的编号（和录音文件）不能被新句子占用，否则会念错
        known = {sid: key for key, sid in self.by_key.items()}
        known.update({s: (k, o, t) for s, k, o, t in self.rows})
        self.path.write_text("".join(f"{s}\t{k}\t{o}\t{t}\n" for s, (k, o, t) in sorted(known.items())), encoding="utf-8")


def owner_of(kind, scene, mood, tod, intent) -> str:
    if kind == "opener":
        return f"{scene}.{mood}"
    if kind == "closer":
        return tod
    if kind == "bridge" and not intent:
        return scene
    return intent


def main():
    if "--check" in sys.argv:
        scene = sys.argv[sys.argv.index("--check") + 1]
        errors: list[str] = []
        intents = parse_scene(scene, errors)
        print("\n".join(errors) if errors else "格式没问题")
        print(f"{scene}：意图 {len(intents)} 个，核心句 {sum(len(i['cores']) for i in intents)}，行动句 {sum(len(i['actions']) for i in intents)}，测试愿望 {sum(len(i['examples']) for i in intents)}")
        sys.exit(1 if errors else 0)

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out_path = Path(args[0]) if args else DEFAULT_OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    intents = parse_intents()
    segs = parse_segments()
    ids = Ids(REGISTRY, out_path)
    tmp = out_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(
        """
        PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
        CREATE TABLE intents (id TEXT PRIMARY KEY, scene TEXT, name TEXT, keys TEXT, examples TEXT, mood TEXT);
        CREATE TABLE segments (id INTEGER PRIMARY KEY, kind TEXT, scene TEXT, mood TEXT, tod TEXT, intent_id TEXT, text TEXT);
        CREATE TABLE answers (id INTEGER PRIMARY KEY, intent_id TEXT, mood TEXT, tod TEXT,
                              opener INTEGER, core INTEGER, bridge INTEGER, closer INTEGER, text TEXT);
        CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
        """
    )

    def seg(kind, text, scene=None, mood=None, tod=None, intent=None) -> int:
        sid = ids.get(kind, owner_of(kind, scene, mood, tod, intent), text)
        db.execute("INSERT INTO segments (id, kind, scene, mood, tod, intent_id, text) VALUES (?,?,?,?,?,?,?)", (sid, kind, scene, mood, tod, intent, text))
        return sid

    opener_ids = {(s, mo): [seg("opener", t, s, mo) for t in segs["opener"][(s, mo)]] for s in SCENES for mo in MOODS}
    closer_ids = {t: [seg("closer", x, tod=t) for x in segs["closer"][(t,)]] for t in TODS}
    text_of = dict(db.execute("SELECT id, text FROM segments"))

    total = 0
    for it in intents:
        db.execute(
            "INSERT INTO intents VALUES (?,?,?,?,?,?)",
            (it["id"], it["scene"], it["name"], json.dumps(it["keys"], ensure_ascii=False), json.dumps(it["examples"], ensure_ascii=False), it["mood"]),
        )
        core_ids = [seg("core", t, it["scene"], intent=it["id"]) for t in it["cores"]]
        action_ids = [seg("bridge", t, it["scene"], intent=it["id"]) for t in it["actions"]]
        text_of.update({i: t for i, t in zip(core_ids + action_ids, it["cores"] + it["actions"])})
        rng = random.Random(it["id"])
        rows = []
        for mo, tod in product(MOODS, TODS):
            ops, cls = opener_ids[(it["scene"], mo)], closer_ids[tod]
            # 先让每条核心句都出现一次（行动句、开场、收尾轮着配），再随机补满
            cores = core_ids[:]
            rng.shuffle(cores)
            picked = {(rng.choice(ops), c, action_ids[n % len(action_ids)], rng.choice(cls)) for n, c in enumerate(cores)}
            while len(picked) < ANSWERS_PER_BUCKET:
                picked.add((rng.choice(ops), rng.choice(core_ids), rng.choice(action_ids), rng.choice(cls)))
            for o, c, b, cl in sorted(picked):
                rows.append((it["id"], mo, tod, o, c, b, cl, "".join(text_of[x] for x in (o, c, b, cl))))
        db.executemany("INSERT INTO answers (intent_id, mood, tod, opener, core, bridge, closer, text) VALUES (?,?,?,?,?,?,?,?)", rows)
        total += len(rows)

    db.execute("CREATE INDEX ix_answers_bucket ON answers (intent_id, mood, tod)")
    n_seg = db.execute("SELECT count(*) FROM segments").fetchone()[0]
    distinct = db.execute("SELECT count(DISTINCT text) FROM answers").fetchone()[0]
    db.executemany("INSERT INTO meta VALUES (?,?)", [("intents", str(len(intents))), ("answers", str(total)), ("distinct", str(distinct)), ("segments", str(n_seg))])
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out_path)
    ids.save()
    print(f"意图 {len(intents)} 个，句子 {n_seg} 句，完整回应 {total:,} 条（不重复 {distinct:,} 条）")
    print(f"写入 {out_path}（{out_path.stat().st_size // 1048576} MB）")


if __name__ == "__main__":
    main()
