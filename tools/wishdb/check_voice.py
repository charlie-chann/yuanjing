"""给回应库的录音做质检：语速（多念、漏念、卡顿）和听写比对（用本地 Whisper 把语音转回文字，和原文对一遍）。

可疑的句子编号写进 bad_voice.txt，再用 voice.py --redo 换一版重录。同音字识别错是常事，所以听写只看字数和整体像不像。
用法：../tts/.venv/bin/python check_voice.py [--no-asr] [--only 编号,编号]
"""
import difflib
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
DB = HERE.parents[1] / "server" / "data" / "wish_answers.db"
OUT = HERE.parents[1] / "server" / "data" / "wish_voice"
strip = lambda t: re.sub(r"[^一-鿿]", "", t)


def main() -> None:
    only = {int(x) for x in sys.argv[sys.argv.index("--only") + 1].split(",")} if "--only" in sys.argv else None
    rows = [(i, t) for i, t in sqlite3.connect(DB).execute("SELECT id, text FROM segments ORDER BY id") if only is None or i in only]
    stats, missing = {}, []
    for sid, text in rows:
        path = OUT / f"{sid}.m4a"
        if not path.exists():
            missing.append(sid)
            continue
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(path), tmp.name], check=True)
            audio, sr = sf.read(tmp.name)
        hop = int(0.02 * sr)
        level = np.array([np.abs(audio[k:k + hop]).max() for k in range(0, len(audio) - hop, hop)])
        voiced = level > 0.02
        gap = run = 0
        for v in voiced:
            run = 0 if v else run + 1
            gap = max(gap, run)
        stats[sid] = (len(strip(text)) / max(voiced.sum() * 0.02, 0.01), gap * 0.02, len(audio) / sr)
    mid = float(np.median([s[0] for s in stats.values()]))
    bad = {}
    for sid, (rate, gap, total) in stats.items():
        if rate < mid * 0.72:
            bad[sid] = f"念得太长（每秒 {rate:.1f} 字）"
        elif rate > mid * 1.35:
            bad[sid] = f"念得太短（每秒 {rate:.1f} 字）"
        elif gap > 1.6:
            bad[sid] = f"中间停了 {gap:.1f} 秒"
    print(f"共 {len(stats)} 句，缺 {len(missing)} 句，语速中位数每秒 {mid:.1f} 字，语速可疑 {len(bad)} 句", flush=True)

    if "--no-asr" not in sys.argv:
        from mlx_audio.stt.utils import load_model

        model = load_model("mlx-community/whisper-small-mlx")
        if getattr(model, "_processor", None) is None:
            from transformers import WhisperProcessor

            model._processor = WhisperProcessor.from_pretrained("openai/whisper-small")
        texts = dict(rows)
        for n, sid in enumerate(stats, 1):
            with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
                subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(OUT / f"{sid}.m4a"), tmp.name], check=True)
                heard = model.generate(tmp.name, language="zh", initial_prompt="以下是普通话的句子。").text
            a, b = strip(texts[sid]), strip(heard)
            ratio = difflib.SequenceMatcher(None, a, b).ratio()
            flag = "多念" if len(b) > len(a) * 1.25 + 1 else "漏念" if len(b) < len(a) * 0.8 - 1 else "对不上" if ratio < 0.6 else ""
            if flag:
                bad[sid] = bad.get(sid, "") + f" {flag}（相似 {ratio:.2f}）听到：{heard.strip()}"
            if n % 100 == 0:
                print(f"听写 {n}/{len(stats)}", flush=True)
    texts = dict(rows)
    for sid in sorted(bad):
        print(f"{sid:5d} {bad[sid].strip()}\n      原文：{texts[sid]}", flush=True)
    (HERE / "bad_voice.txt").write_text(",".join(str(i) for i in sorted(set(bad) | set(missing))))
    print(f"可疑 {len(bad)} 句，缺 {len(missing)} 句，编号写进 bad_voice.txt", flush=True)


if __name__ == "__main__":
    main()
