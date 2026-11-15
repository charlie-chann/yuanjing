"""重录过的句子：原版（wish_voice_take0/）和新版各算一次语速，留下离全体中位数更近的那一版。"""
import re, subprocess, sys, tempfile
from pathlib import Path
import numpy as np, soundfile as sf
D = Path(__file__).resolve().parents[1].parent / "server" / "data"
MID = float(sys.argv[1]) if len(sys.argv) > 1 else 3.9
import sqlite3
texts = dict(sqlite3.connect(D / "wish_answers.db").execute("SELECT id, text FROM segments"))
def rate(p, text):
    with tempfile.NamedTemporaryFile(suffix=".wav") as t:
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(p), t.name], check=True)
        a, sr = sf.read(t.name)
    hop = int(0.02 * sr)
    v = sum(np.abs(a[k:k + hop]).max() > 0.02 for k in range(0, len(a) - hop, hop)) * 0.02
    return len(re.sub(r"[^一-鿿]", "", text)) / max(v, 0.01)
kept_old = 0
for old in sorted((D / "wish_voice_take0").glob("*.m4a")):
    new = D / "wish_voice" / old.name
    sid = int(old.stem)
    ro, rn = rate(old, texts[sid]), rate(new, texts[sid])
    if abs(np.log(ro / MID)) < abs(np.log(rn / MID)):
        new.write_bytes(old.read_bytes())
        kept_old += 1
    print(f"{sid:4d} 原版 {ro:.1f} 新版 {rn:.1f} -> {'原版' if abs(np.log(ro / MID)) < abs(np.log(rn / MID)) else '新版'}")
print("留原版", kept_old)
