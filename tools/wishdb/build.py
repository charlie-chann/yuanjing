"""把 data/ 里写好的愿望意图和回应句，组合成完整的回应库（SQLite），给后端用。

一条完整回应 = 开场（按分类和情绪） + 核心句（按愿望意图） + 行动句（按分类） + 收尾（按时段）。
每个意图、每种情绪、每个时段各取 ANSWERS_PER_BUCKET 条不重复的组合，写进 answers 表。
每一句都单独存一行（segments 表），以后逐句录音，回应播放时按四段依次放。

用法：python3 build.py [输出路径]   默认输出 server/data/wish_answers.db
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
DEFAULT_OUT = HERE.parents[1] / "server" / "data" / "wish_answers.db"
SCENES = ("wealth", "career", "looks", "health", "mood", "life", "pet")
MOODS = ("calm", "eager", "anxious", "heavy")
TODS = ("morning", "day", "evening", "night")
ANSWERS_PER_BUCKET = 500


def parse_intents():
    intents = []
    for scene in SCENES:
        cur = None
        for raw in (DATA / f"{scene}.txt").read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("@"):
                head, _, keys = line[1:].partition("|")
                iid, name = head.split(None, 1)
                assert iid.startswith(scene + "."), iid
                cur = {"id": iid, "scene": scene, "name": name.strip(), "keys": keys.split(), "cores": [], "examples": []}
                intents.append(cur)
            elif line.startswith("- "):
                cur["cores"].append(line[2:].strip())
            elif line.startswith("? "):
                cur["examples"].append(line[2:].strip())
            else:
                raise ValueError(f"{scene}.txt 看不懂这一行：{raw}")
    ids = [i["id"] for i in intents]
    assert len(ids) == len(set(ids)), "意图编号重复"
    for i in intents:
        assert len(i["cores"]) >= 5, f"{i['id']} 核心句不到 5 条"
        assert i["keys"], f"{i['id']} 没有关键词"
    for s in SCENES:
        assert f"{s}.general" in ids, f"缺少 {s}.general 兜底意图"
    return intents


def parse_segments():
    out = {"opener": {}, "bridge": {}, "closer": {}}
    key = None
    for raw in (DATA / "segments.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.fullmatch(r"\[(opener|bridge|closer)\s+([a-z ]+)\]", line)
        if m:
            kind, rest = m.group(1), tuple(m.group(2).split())
            key = (kind, rest)
            out[kind].setdefault(rest, [])
            continue
        out[key[0]][key[1]].append(line)
    for s in SCENES:
        for mo in MOODS:
            assert len(out["opener"].get((s, mo), [])) >= 4, f"开场 {s} {mo} 不够"
        assert len(out["bridge"].get((s,), [])) >= 8, f"行动句 {s} 不够"
    for t in TODS:
        assert len(out["closer"].get((t,), [])) >= 8, f"收尾 {t} 不够"
    return out


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    intents = parse_intents()
    segs = parse_segments()
    tmp = out_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(
        """
        PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
        CREATE TABLE intents (id TEXT PRIMARY KEY, scene TEXT, name TEXT, keys TEXT, examples TEXT);
        CREATE TABLE segments (id INTEGER PRIMARY KEY, kind TEXT, scene TEXT, mood TEXT, tod TEXT, intent_id TEXT, text TEXT);
        CREATE TABLE answers (id INTEGER PRIMARY KEY, intent_id TEXT, mood TEXT, tod TEXT,
                              opener INTEGER, core INTEGER, bridge INTEGER, closer INTEGER, text TEXT);
        CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
        """
    )

    def seg(kind, text, scene=None, mood=None, tod=None, intent=None) -> int:
        cur = db.execute("INSERT INTO segments (kind, scene, mood, tod, intent_id, text) VALUES (?,?,?,?,?,?)", (kind, scene, mood, tod, intent, text))
        return cur.lastrowid

    opener_ids = {(s, mo): [seg("opener", t, s, mo) for t in segs["opener"][(s, mo)]] for s in SCENES for mo in MOODS}
    bridge_ids = {s: [seg("bridge", t, s) for t in segs["bridge"][(s,)]] for s in SCENES}
    closer_ids = {t: [seg("closer", x, tod=t) for x in segs["closer"][(t,)]] for t in TODS}
    text_of = dict(db.execute("SELECT id, text FROM segments"))

    total = 0
    for it in intents:
        db.execute("INSERT INTO intents VALUES (?,?,?,?,?)", (it["id"], it["scene"], it["name"], json.dumps(it["keys"], ensure_ascii=False), json.dumps(it["examples"], ensure_ascii=False)))
        core_ids = [seg("core", t, it["scene"], intent=it["id"]) for t in it["cores"]]
        text_of.update({i: t for i, t in zip(core_ids, it["cores"])})
        rng = random.Random(it["id"])
        rows = []
        for mo, tod in product(MOODS, TODS):
            combos = list(product(opener_ids[(it["scene"], mo)], core_ids, bridge_ids[it["scene"]], closer_ids[tod]))
            rng.shuffle(combos)
            # 先保证每条核心句都用到，再随机补满
            picked, seen_core = [], set()
            for c in combos:
                if c[1] not in seen_core:
                    picked.append(c)
                    seen_core.add(c[1])
            rest = [c for c in combos if c not in set(picked)]
            picked += rest[: ANSWERS_PER_BUCKET - len(picked)]
            for o, c, b, cl in picked:
                rows.append((it["id"], mo, tod, o, c, b, cl, "".join(text_of[x] for x in (o, c, b, cl))))
        db.executemany("INSERT INTO answers (intent_id, mood, tod, opener, core, bridge, closer, text) VALUES (?,?,?,?,?,?,?,?)", rows)
        total += len(rows)

    db.execute("CREATE INDEX ix_answers_bucket ON answers (intent_id, mood, tod)")
    n_seg = db.execute("SELECT count(*) FROM segments").fetchone()[0]
    distinct = db.execute("SELECT count(DISTINCT text) FROM answers").fetchone()[0]
    db.executemany("INSERT INTO meta VALUES (?,?)", [("intents", str(len(intents))), ("answers", str(total)), ("segments", str(n_seg))])
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out_path)
    print(f"意图 {len(intents)} 个，句子 {n_seg} 句，完整回应 {total:,} 条（不重复 {distinct:,} 条）")
    print(f"写入 {out_path}（{out_path.stat().st_size // 1048576} MB）")


if __name__ == "__main__":
    main()
