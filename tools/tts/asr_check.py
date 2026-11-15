"""用本地语音识别把每句语音转回文字，和原文对一遍，找出念错、多念、漏念的。

配合 check_guides.py（按语速筛）一起用。识别模型是开源的 Whisper small（约 480 MB，第一次运行自动下载）。
同音字识别错是常事，所以只看字数差得多不多、整体像不像。用法：.venv/bin/python asr_check.py [名字前缀] [-v 全部列出]
"""
import difflib
import re
import sys
import tempfile
import subprocess

from mlx_audio.stt.utils import load_model

import generate_guides as g

model = load_model("mlx-community/whisper-small-mlx")
if getattr(model, "_processor", None) is None:
    # 这个模型仓库里没带分词文件，从官方的 openai/whisper-small 取（几兆）
    from transformers import WhisperProcessor

    model._processor = WhisperProcessor.from_pretrained("openai/whisper-small")
prefix = next((a for a in sys.argv[1:] if not a.startswith("-")), "")
strip = lambda t: re.sub(r"[^一-鿿]", "", t)
bad = total = 0
for scene, lines in g.ALL.items():
    for i, text in enumerate(lines, 1):
        key = f"{scene}_{i}"
        if not key.startswith(prefix):
            continue
        path = g.OUT / f"{key}.m4a"
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(path), tmp.name], check=True)
            heard = model.generate(tmp.name, language="zh", initial_prompt="以下是普通话的句子。").text
        a, b = strip(text), strip(heard)
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        total += 1
        flag = ""
        if len(b) > len(a) * 1.25 + 1:
            flag = "多念"
        elif len(b) < len(a) * 0.8 - 1:
            flag = "漏念"
        elif ratio < 0.6:
            flag = "对不上"
        if flag:
            bad += 1
        if flag or "-v" in sys.argv:
            print(f"{key:20s} {flag or '正常':4s} 相似 {ratio:.2f}\n    原文 {text}\n    听到 {heard.strip()}", flush=True)
print(f"共 {total} 句，可疑 {bad} 句", flush=True)
