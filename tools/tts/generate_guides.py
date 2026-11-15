"""用开源的 Qwen3-TTS 在本机离线生成仪式引导语，输出到 assets/voice/。

    cd tools/tts && .venv/bin/python generate_guides.py            # 生成全部
    .venv/bin/python generate_guides.py --only wealth_1 --take 2   # 某一句不满意，换一版重生成

第一次运行会从 Hugging Face 下载模型（约 2 到 3 GB）。
引导语的文字要和 lib/features/wish/wish_category.dart 里的保持一致。
"""
import argparse
import subprocess
import sys
from pathlib import Path

import mlx.core as mx
import numpy as np
import soundfile as sf
from mlx_audio.tts.utils import load_model

MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit"
SPEAKER = "Serena"
# 这段话决定了语气。想要更慢、更轻、更像耳语，改这里。
STYLE = "用非常温柔、舒缓、放松的语气，语速缓慢，声音轻柔温暖，带一点气声，像在耳边轻声引导冥想，每一句之间自然停顿。"

LINES = {
    "wealth": ["把心愿交给这枚金币。", "听，它们一枚一枚落下来了。", "丰盛正在流向你。"],
    "career": ["一点光，从山脚出发。", "它到顶了。", "天亮了，这是你的早晨。"],
    "looks": ["光从你身上滑过。", "你本来就在发光。", "被看见，也被自己喜欢。"],
    "health": ["跟着它，慢慢吸气。", "再慢慢呼出去。", "身体听见了，它在变好。"],
    "mood": ["让这一滴落下去。", "云在散开。", "湖面静了，你也是。"],
    "life": ["点亮属于你的那一盏。", "它升起来了，还有很多盏陪着它。", "你想要的生活，正在路上。"],
    "pet": ["有一串小脚印，朝你走来。", "它在天上也留了一个爪印。", "被你爱着，它什么都不怕。"],
}

# 卡点释放：五种释放方式各四句引导语，文字要和 lib/features/release/release_data.dart 一致
RELEASE = {
    "release_pool": ["把烦恼放进这只纸船。", "让这些不属于你的沉重，随着水流慢慢离开。", "你不需要抓住它们，只需要允许它们流过。", "水面亮起来了，它已经走远。"],
    "release_balloon": ["把压力装进热气球的篮子里。", "把压力交给天空，把沉重交给风。", "你不需要一直背着它们，允许自己轻一点。", "它越飞越高，已经看不见了。"],
    "release_arrow": ["那些束缚你的，此刻显出了形状。", "不属于你的束缚，在此刻被温柔切断。", "你从旧的限制中解脱。", "回到安全、完整、平静的自己。"],
    "release_potion": ["把执念交给魔药，把情绪交给转化。", "黑色的泡泡沉进去，颜色开始变了。", "那些困住你的旧故事，正在被温柔溶解。", "它们蒸发了，只剩下光。"],
    "release_deep": ["把烦恼折进这只小纸船。", "像海水容纳所有情绪一样，允许自己经历它们。", "也允许它们离开。", "你不需要一直停留在难过里。"],
    # 释放前的呼吸引导，五种方式共用
    "release_breath": ["先跟着我，慢慢吸一口气。", "再缓缓地呼出去。"],
    # 深度释放开头的身体放松，五种方式共用
    "release_scan": ["现在，把注意力带到额头和眉心，让它慢慢松开。", "肩膀往下沉，离耳朵远一点。", "感受胸口。那里的紧，随着呼气一点点散开。", "肚子变软，手心也松开。", "整个身体，被稳稳地托住。"],
    # 画面中间的留白提示
    "release_hold": ["不用着急，就这样看着。", "每呼出一口气，就再松开一点。", "你做得很好。"],
    # 放完之后安住的两句，和请用户跟念肯定语的一句
    "release_settle": ["感受一下，身体里多出来的那一点空间。", "让这份轻松，在这里多留一会儿。"],
    "release_repeat": ["跟着我，在心里再念一遍。"],
}
# 八种卡点各自的肯定语，释放完成时念。文件名是 affirm_<卡点>_1
AFFIRM = {
    "affirm_wronged": ["我稳稳地守住自己的边界，我值得被尊重，我不再被他人的行为定义。"],
    "affirm_anger": ["我可以平静地表达界限。我的力量不需要靠怒火来证明。"],
    "affirm_anxiety": ["此刻我是安全的。我一步一步来，事情会在该清楚的时候清楚。"],
    "affirm_inferior": ["我本来的样子就值得被爱。我允许自己被看见。"],
    "affirm_failure": ["我允许自己尝试，也允许自己慢慢来。每一步都在把我带向要去的地方。"],
    "affirm_judged": ["我由我自己定义。我可以自在地做自己，不需要所有人点头。"],
    "affirm_relation": ["我值得被温柔对待。我向健康、安稳的关系敞开。"],
    "affirm_overload": ["我可以休息。我做得已经足够，我允许自己被支持。"],
}

# 八种卡点各自的释放引导，进画面之前念。文字要和 lib/features/release/release_data.dart 里的 guide 一致
GUIDE = {
    "guide_wronged": ["允许这份委屈流过你，不必抓住它。别人的态度只是他们的投影，不是你的真相。"],
    "guide_anger": ["让这团热从胸口慢慢散开。你不需要压住它，也不需要被它带着走。"],
    "guide_anxiety": ["把注意力放回这一口呼吸。还没发生的事，先让它待在明天。"],
    "guide_inferior": ["把那把一直量自己的尺子放下来。你不需要先达标，才被允许存在。"],
    "guide_failure": ["把结果先交出去。你只需要迈出眼前这一步，剩下的路会自己显出来。"],
    "guide_judged": ["那些目光和声音，让它们从你身边经过。它们是别人的，不必住进你心里。"],
    "guide_relation": ["把那份等不到回应的期待，轻轻松开。它不是你的错，也不该由你一个人扛。"],
    "guide_overload": ["把肩上的东西一件一件放下来。此刻什么都不用做，世界不会因此停转。"],
}

# 冥想引导。前三段是音频冥想（免费），后两段配原生画面（会员）。文字要和 lib/features/heal/heal_data.dart 一致
MEDITATE = {
    "med_vision": ["找一个舒服的姿势，轻轻闭上眼睛。", "吸气，让空气一直沉到小腹。呼气，把今天的忙碌放下来。", "现在，想象一年以后的某个早晨。你醒来的地方，是你喜欢的样子。", "看看四周。光是从哪里照进来的？空气里有什么味道？", "那时候的你，正准备去做一件让你期待的事。", "感受一下那份踏实。它不在远处，它已经在你心里了。", "把这个画面，轻轻收进胸口。", "慢慢地，把注意力带回这里。带着它，回到今天。"],
    "med_calm": ["先什么都不用做。就这样待一会儿。", "吸气，数到四。呼气，数到六。", "留意一下，身体哪里最紧。把呼吸送到那里去。", "每呼出一口气，那里就松开一点。", "那些还没做完的事，先放在门外。它们会等你。", "此刻，你只需要呼吸。", "你已经做得够多了。", "再深深地吸一口气，然后慢慢睁开眼睛。"],
    "med_clear": ["闭上眼睛，想象一束柔和的光，落在头顶。", "它慢慢往下流，经过额头，经过肩膀，经过胸口。", "光经过的地方，旧的担心被轻轻带走。", "那些别人说过的话，那些你对自己的苛责，都不必再留着。", "它们顺着光，从脚底流出去，回到大地。", "现在，你的心里空出了一块干净的地方。", "在那里放下一句话：我值得一切美好。", "带着这份干净，慢慢回来。"],
    "med_looks": ["想象你站在一面柔光的镜子前。", "镜子里的你，眼睛很亮，神情很松。", "皮肤透着健康的光，像清晨的珍珠。", "你看着自己，嘴角轻轻扬起来。", "这份好看，不是变成别人，是你本来的样子在发光。", "记住这个画面。每一天，你都在靠近它。"],
    "med_future": ["想象很多盏灯，从你脚下缓缓升起。", "每一盏，都是你许过的一个心愿。", "它们越升越高，照亮了你要去的地方。", "在那里，你过着自己选择的生活，从容，丰盛，被爱着。", "那个你，回过头来，对现在的你微笑。", "告诉自己：我正在路上。"],
}
# 成品肯定语音频库。文字要和 lib/features/shop/shop_data.dart 一致
LIBRARY = {
    "lib_wealth": ["我值得拥有丰盛。", "金钱以轻松的方式流向我。", "我善用每一份收入，也安心地享受它。", "我的价值，一直在增长。"],
    "lib_career": ["我清楚自己要去哪里。", "我的努力，正在被看见。", "机会喜欢准备好的我。", "我从容地走在自己的节奏里。"],
    "lib_looks": ["我喜欢镜子里的自己。", "我的身体，每天都在变得更好。", "我由内而外地发着光。", "我本来的样子，就很美。"],
    "lib_health": ["我的身体知道如何修复自己。", "每一次呼吸，都在给我力量。", "我睡得安稳，醒来有精神。", "我温柔地照顾自己。"],
    "lib_mood": ["我允许情绪来，也允许它走。", "我的心，越来越安定。", "我对自己很温柔。", "今天，我选择平静。"],
    "lib_all": ["我值得一切美好。", "我想要的，正在向我走来。", "我相信自己，也相信时间。", "我已经走在路上了。"],
}
ALL = {**LINES, **RELEASE, **AFFIRM, **GUIDE, **MEDITATE, **LIBRARY}

OUT = Path(__file__).resolve().parents[2] / "assets" / "voice"


def trim(audio: np.ndarray, sr: int) -> np.ndarray:
    """去掉首尾的静音，各留一小段，再做淡入淡出。"""
    level = np.abs(audio)
    loud = np.where(level > 0.012)[0]
    if len(loud) == 0:
        return audio
    a, b = max(loud[0] - int(0.08 * sr), 0), min(loud[-1] + int(0.35 * sr), len(audio))
    audio = audio[a:b].copy()
    n = int(0.03 * sr)
    audio[:n] *= np.linspace(0, 1, n)
    audio[-n * 4:] *= np.linspace(1, 0, n * 4)
    peak = np.abs(audio).max()
    return audio * (0.82 / peak) if peak > 0 else audio


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只生成这一句，例如 wealth_1")
    ap.add_argument("--take", type=int, default=0, help="换一个随机种子重生成")
    ap.add_argument("--force", action="store_true", help="已有的文件也重新生成")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    model = load_model(MODEL)
    for scene, lines in ALL.items():
        for i, text in enumerate(lines, 1):
            key = f"{scene}_{i}"
            if args.only and args.only != key:
                continue
            if not args.only and not args.force and (OUT / f"{key}.m4a").exists():
                continue  # 已经有的不重做，加 --force 才全部重生成
            mx.random.seed(1000 + sum(map(ord, key)) + args.take * 97)
            chunks = [np.array(r.audio) for r in model.generate_custom_voice(text=text, speaker=SPEAKER, language="Chinese", instruct=STYLE)]
            audio = trim(np.concatenate(chunks).astype(np.float32), model.sample_rate)
            wav = OUT / f"{key}.wav"
            sf.write(wav, audio, model.sample_rate)
            # 压成 AAC，安装包里只放 m4a
            subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "64000", str(wav), str(OUT / f"{key}.m4a")], check=True)
            wav.unlink()
            print(f"{key}  {len(audio) / model.sample_rate:.1f}s  {text}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
