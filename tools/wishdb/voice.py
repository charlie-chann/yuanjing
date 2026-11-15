"""给回应库里的每一句录女声（本机 Qwen3-TTS，和应用里其他引导语同一个声音），存到 server/data/wish_voice/<句子编号>.m4a。

先录开场、行动句、收尾（所有意图共用，录完就覆盖所有回应的四分之三），再按意图录核心句。
已经录好的跳过，可以随时中断再接着跑。录完一句就能用：后端看文件在不在决定给不给语音地址。
用法：../tts/.venv/bin/python voice.py [--limit N] [--redo 编号,编号 | @bad_voice.txt] [--take 第几版]
"""
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import mlx.core as mx
import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tts"))
import generate_guides as g  # noqa: E402  模型、音色、语气、去静音都和引导语一致

DB = HERE.parents[1] / "server" / "data" / "wish_answers.db"
OUT = HERE.parents[1] / "server" / "data" / "wish_voice"


def main() -> None:
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    OUT.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB)
    order = "CASE kind WHEN 'opener' THEN 0 WHEN 'closer' THEN 1 WHEN 'bridge' THEN 2 ELSE 3 END, id"
    # --redo 编号,编号（或 --redo @bad_voice.txt）：这些句子换一版重录；--take 决定换第几版
    redo, take = None, 0
    if "--redo" in sys.argv:
        arg = sys.argv[sys.argv.index("--redo") + 1]
        if arg.startswith("@"):
            arg = (HERE / arg[1:]).read_text().strip()
        redo = {int(x) for x in arg.split(",") if x}
        take = int(sys.argv[sys.argv.index("--take") + 1]) if "--take" in sys.argv else 1
    rows = [(i, t) for i, t in db.execute(f"SELECT id, text FROM segments ORDER BY {order}") if (i in redo if redo is not None else not (OUT / f"{i}.m4a").exists())]
    if limit:
        rows = rows[:limit]
    print(f"要录 {len(rows)} 句", flush=True)
    model = g.load_model(g.MODEL)
    t0 = time.time()
    for n, (sid, text) in enumerate(rows, 1):
        mx.random.seed(5000 + sid + take * 100000)
        chunks = [np.array(r.audio) for r in model.generate_custom_voice(text=text, speaker=g.SPEAKER, language="Chinese", instruct=g.STYLE)]
        audio = g.trim(np.concatenate(chunks).astype(np.float32), model.sample_rate)
        wav = OUT / f"{sid}.wav"
        sf.write(wav, audio, model.sample_rate)
        subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "48000", str(wav), str(OUT / f"{sid}.m4a")], check=True)
        wav.unlink()
        if n % 10 == 0 or n == len(rows):
            per = (time.time() - t0) / n
            print(f"{n}/{len(rows)}  每句 {per:.1f} 秒，还要约 {per * (len(rows) - n) / 60:.0f} 分钟", flush=True)


if __name__ == "__main__":
    main()
