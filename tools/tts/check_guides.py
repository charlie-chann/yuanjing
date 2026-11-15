"""按语速筛出可能念坏的句子：模型偶尔会多念、漏念或中间卡住，耳朵听之前先用数字过一遍。

每句算「去掉静音后每秒几个字」和「中间最长的停顿」，偏离正常范围的列出来，
再用 generate_guides.py --only <名字> --take <n> 换一版。用法：.venv/bin/python check_guides.py
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

import generate_guides as g

OUT = g.OUT
bad = 0
rows = []
for scene, lines in g.ALL.items():
    for i, text in enumerate(lines, 1):
        key = f"{scene}_{i}"
        path = OUT / f"{key}.m4a"
        if not path.exists():
            print(f"缺文件 {key}")
            bad += 1
            continue
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16", str(path), tmp.name], check=True)
            audio, sr = sf.read(tmp.name)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        hop = int(0.02 * sr)
        level = np.array([np.abs(audio[k:k + hop]).max() for k in range(0, len(audio) - hop, hop)])
        voiced = level > 0.02
        chars = len(re.sub(r"[，。、？！\s]", "", text))
        speak = voiced.sum() * 0.02
        # 中间最长的一段静音
        gap = run = 0
        for v in voiced:
            run = 0 if v else run + 1
            gap = max(gap, run)
        rate = chars / max(speak, 0.01)
        rows.append((key, chars, len(audio) / sr, speak, rate, gap * 0.02))
rates = np.array([r[4] for r in rows])
mid = float(np.median(rates))
for key, chars, total, speak, rate, gap in rows:
    flag = ""
    if rate < mid * 0.72:
        flag = "念得太长，可能多念或拖音"
    elif rate > mid * 1.35:
        flag = "念得太短，可能漏字"
    elif gap > 1.6:
        flag = "中间停顿太久"
    if flag or "-v" in sys.argv:
        print(f"{key:20s} {chars:2d} 字  全长 {total:4.1f}s  出声 {speak:4.1f}s  每秒 {rate:3.1f} 字  最长停顿 {gap:3.1f}s  {flag}")
        bad += bool(flag)
print(f"共 {len(rows)} 句，语速中位数每秒 {mid:.1f} 字，可疑 {bad} 句")
