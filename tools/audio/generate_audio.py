"""合成愿境的环境音和音效，输出到 assets/audio/。全部是代码算出来的，没有用任何外部素材。

    cd tools/audio && ../tts/.venv/bin/python generate_audio.py          # 全部生成
    ../tts/.venv/bin/python generate_audio.py amb_mood sfx_coin_1        # 只生成指定的几个

环境音是 24 秒的无缝循环：所有成分的周期都整除 24 秒，噪声在频域里整形，所以首尾天然接得上。
音效自带混响尾巴。想换成录音素材，直接替换 assets/audio/ 里同名的 m4a 就行，代码不用动。
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100
T = 24.0
N = int(SR * T)
OUT = Path(__file__).resolve().parents[2] / "assets" / "audio"
rng = np.random.default_rng(7)


# ───────── 基础积木 ─────────
def tt(n):
    return np.arange(n) / SR


def snap(f):
    """把频率对齐到循环长度的整数倍，保证循环无缝。"""
    return round(f * T) / T


def band(n, lo, hi, slope=0.0, seed=0, edge=0.25):
    """带通噪声，周期等于 n。slope 是每倍频程的倾斜（负数偏暗）。"""
    r = np.random.default_rng(seed)
    f = np.fft.rfftfreq(n, 1 / SR)
    spec = r.normal(size=f.size) + 1j * r.normal(size=f.size)
    lo_e, hi_e = lo * (1 - edge), hi * (1 + edge)
    g = np.clip((f - lo_e) / max(lo - lo_e, 1e-6), 0, 1) * np.clip((hi_e - f) / max(hi_e - hi, 1e-6), 0, 1)
    g = 0.5 - 0.5 * np.cos(np.pi * g)
    g *= np.power(np.maximum(f, 20) / 1000.0, slope)
    x = np.fft.irfft(spec * g, n)
    return x / (np.max(np.abs(x)) + 1e-9)


def drift(n, fmax, seed, lo=0.0, hi=1.0):
    """缓慢起伏的随机曲线，取值 lo..hi，周期等于 n。"""
    x = band(n, 0.0001, fmax, seed=seed, edge=0.5)
    x = (x - x.min()) / (x.max() - x.min() + 1e-9)
    return lo + (hi - lo) * x


def pad(notes, n=N, seed=0, bright=0.12, trem=0.22):
    """柔和的和弦垫底：每个音左右各一个略微失谐的正弦，带缓慢的音量起伏。"""
    r = np.random.default_rng(seed)
    t = tt(n)
    out = np.zeros((n, 2))
    for i, f in enumerate(notes):
        for ch, det in ((0, 1.0018), (1, 0.9982)):
            fx = snap(f * det)
            v = np.sin(2 * np.pi * fx * t + r.uniform(0, 6.28))
            v += bright * np.sin(2 * np.pi * snap(fx * 2) * t + r.uniform(0, 6.28))
            v += bright * 0.4 * np.sin(2 * np.pi * snap(fx * 3) * t + r.uniform(0, 6.28))
            k = int(r.integers(1, 6))
            out[:, ch] += v * (1 + trem * np.sin(2 * np.pi * k * t / T + r.uniform(0, 6.28))) / (1 + 0.35 * i)
    return out / (np.max(np.abs(out)) + 1e-9)


def reverb_ir(decay=2.4, lp=5200, seed=1, length=None):
    n = int(SR * (length or decay * 1.3))
    t = tt(n)
    ir = np.stack([band(n, 120, lp, slope=-0.6, seed=seed + c) for c in (0, 1)], axis=1)
    ir *= np.exp(-t * 6.9 / decay)[:, None]
    ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))[:, None]
    return ir / np.sqrt(np.sum(ir**2, axis=0, keepdims=True))


def reverb(x, wet=0.3, decay=2.4, lp=5200, seed=1, circular=False):
    """卷积混响。circular=True 用于循环素材，尾巴会绕回开头。"""
    x = np.atleast_2d(x.T).T if x.ndim == 1 else x
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    ir = reverb_ir(decay, lp, seed)
    n = x.shape[0] if circular else x.shape[0] + ir.shape[0]
    out = np.zeros((n, 2))
    for c in (0, 1):
        y = np.fft.irfft(np.fft.rfft(x[:, c], n) * np.fft.rfft(ir[:, c], n), n)
        out[:, c] = y
    dry = np.zeros((n, 2))
    dry[: x.shape[0]] = x
    return dry * (1 - wet * 0.4) + out * wet * 0.5


def modal(f0, ratios, amps, decays, dur, attack=0.002):
    """敲击一个共振体：一组不成整数倍的分音，各自衰减。钟、碗、硬币都是这个模型。"""
    n = int(SR * dur)
    t = tt(n)
    x = np.zeros(n)
    for r_, a, d in zip(ratios, amps, decays):
        x += a * np.exp(-t / d) * np.sin(2 * np.pi * f0 * r_ * t + rng.uniform(0, 6.28))
    k = max(int(attack * SR), 1)
    x[:k] *= np.linspace(0, 1, k)
    # 结尾收干净：还没衰减完就截断会留下一声咔哒（频谱图上是一条竖线）
    m = int(n * 0.25)
    x[-m:] *= np.cos(np.linspace(0, np.pi / 2, m)) ** 2
    return x


def bell(f0, dur=3.0, bright=1.0):
    return modal(f0, [1, 2.0, 2.76, 5.4, 8.93], [1, 0.5 * bright, 0.35 * bright, 0.18 * bright, 0.07 * bright], [dur * 0.4, dur * 0.3, dur * 0.22, dur * 0.12, dur * 0.07], dur)


def musicbox(f0, dur=1.6):
    return modal(f0, [1, 4.0, 9.2], [1, 0.22, 0.05], [dur * 0.32, dur * 0.12, dur * 0.05], dur)


def pluck(f0, dur=1.2, damp=0.996):
    """拨弦（Karplus-Strong）：一小段噪声在延迟线里反复过低通。"""
    n = int(SR * dur)
    p = max(int(SR / f0), 2)
    buf = rng.uniform(-1, 1, p)
    out = np.zeros(n)
    for i in range(n):
        out[i] = buf[i % p]
        buf[i % p] = damp * 0.5 * (buf[i % p] + buf[(i + 1) % p])
    return out


def place(dst, src, at, gain=1.0, pan=0.0, wrap=False):
    """把一段声音放到 dst 的 at 秒处。pan -1 左，1 右。wrap=True 时超出的部分绕回开头。"""
    if src.ndim == 1:
        l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        src = np.stack([src * l, src * r], axis=1) * 1.414
    i = int(at * SR)
    n = dst.shape[0]
    if wrap:
        idx = (i + np.arange(src.shape[0])) % n
        np.add.at(dst, idx, src * gain)
    else:
        m = min(src.shape[0], n - i)
        if m > 0:
            dst[i : i + m] += src[:m] * gain


def bloop(f_a, f_b, dur=0.09, amp=1.0):
    """水滴入水的那一声：一个很快上滑的正弦。"""
    n = int(SR * dur)
    t = tt(n)
    f = f_a + (f_b - f_a) * (t / dur) ** 0.6
    return amp * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (dur * 0.35)) * np.minimum(t / 0.003, 1)


def fade(x, a=0.005, b=0.05):
    x = x.copy()
    ka, kb = int(a * SR), int(b * SR)
    env = np.ones(x.shape[0])
    env[:ka] = np.linspace(0, 1, ka)
    env[-kb:] = np.linspace(1, 0, kb)
    return x * (env[:, None] if x.ndim == 2 else env)


def finish(x, peak):
    return x * (peak / (np.max(np.abs(x)) + 1e-9))


# ───────── 环境音（24 秒无缝循环） ─────────
C2, D2, E2, F2, G2, A2 = 65.41, 73.42, 82.41, 87.31, 98.0, 110.0


def note(semi_from_a4):
    return 440.0 * 2 ** (semi_from_a4 / 12)


def air(seed, lo=3000, hi=9000, level=0.05, rate=0.25):
    x = np.stack([band(N, lo, hi, slope=-0.8, seed=seed + c) for c in (0, 1)], axis=1)
    return x * drift(N, rate, seed + 9, 0.3, 1.0)[:, None] * level


def amb_wealth():
    """金色大厅：温暖的低音和弦，高处有若隐若现的金属泛音。"""
    x = pad([C2, G2, C2 * 2, 164.81, 196.0, 293.66], seed=1) * 0.8
    t = tt(N)
    for i, f in enumerate([1046.5, 1318.5, 1568.0, 2349.3, 3136.0]):
        g = drift(N, 0.18, 20 + i, 0.0, 1.0) ** 3
        s = np.sin(2 * np.pi * snap(f) * t) + 0.5 * np.sin(2 * np.pi * snap(f * 1.003) * t)
        place(x, s * g * 0.035, 0, pan=(i - 2) * 0.4)
    x += air(31, level=0.03)
    return finish(reverb(x, 0.35, 3.2, circular=True), 0.30)


def wind(seed, level=1.0):
    x = np.zeros((N, 2))
    for c in (0, 1):
        body = band(N, 70, 700, slope=-1.0, seed=seed + c) * drift(N, 0.12, seed + 10 + c, 0.25, 1.0) ** 1.5
        for j, fc in enumerate([520, 860, 1350]):
            body += band(N, fc * 0.93, fc * 1.07, seed=seed + 20 + j * 2 + c, edge=0.08) * drift(N, 0.2, seed + 40 + j, 0.0, 1.0) ** 3 * 0.35
        x[:, c] = body
    return x * level


def amb_career():
    """山巅拂晓：一阵一阵的山风，底下有一条很低的长音。"""
    x = wind(50) * 0.9
    x += pad([A2 / 2, E2, A2], seed=3, bright=0.05, trem=0.3) * 0.35
    return finish(reverb(x, 0.25, 2.6, circular=True), 0.30)


def amb_looks():
    """珠光：高一点的柔和和弦，像呼吸一样起伏的空气声。"""
    x = pad([174.61, 220.0, 261.63, 329.63, 523.25], seed=5, bright=0.08) * 0.75
    t = tt(N)
    for i, f in enumerate([1396.9, 1760.0, 2093.0, 2637.0]):
        g = drift(N, 0.15, 60 + i, 0.0, 1.0) ** 2.5
        place(x, np.sin(2 * np.pi * snap(f) * t) * g * 0.03, 0, pan=(i - 1.5) * 0.5)
    x += air(71, 4000, 11000, level=0.04, rate=0.12)
    return finish(reverb(x, 0.4, 3.4, circular=True), 0.28)


def amb_health():
    """竹林与颂钵：一只钵持续地鸣，带缓慢的拍音；远处有细细的流水。"""
    t = tt(N)
    x = np.zeros((N, 2))
    for ratio, a in zip([1, 2.71, 5.15, 8.2], [1, 0.45, 0.2, 0.06]):
        f = 196.0 * ratio
        for ch, d in ((0, 0.35), (1, -0.35)):
            x[:, ch] += a * (np.sin(2 * np.pi * snap(f) * t) + 0.9 * np.sin(2 * np.pi * snap(f + d + 0.25) * t))
    x *= (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t / T))[:, None] * 0.5
    stream = np.stack([band(N, 1200, 5200, slope=-0.5, seed=80 + c) for c in (0, 1)], axis=1)
    bubble = np.stack([drift(N, 11.0, 84 + c, 0.2, 1.0) ** 2 for c in (0, 1)], axis=1)
    x += stream * bubble * drift(N, 0.1, 88, 0.6, 1.0)[:, None] * 0.10
    x += wind(90, 0.10)
    return finish(reverb(x, 0.35, 3.0, circular=True), 0.28)


def crickets(seed, carrier, period, pan, level):
    x = np.zeros((N, 2))
    chirp_n = int(period * SR)
    t = tt(chirp_n)
    env = np.zeros(chirp_n)
    for k in range(3):
        c = 0.02 + k * 0.036
        env += np.exp(-(((t - c) / 0.008) ** 2))
    one = env * (np.sin(2 * np.pi * carrier * t) + 0.5 * np.sin(2 * np.pi * carrier * 1.055 * t))
    count = int(round(T / period))
    lvl = drift(count, SR / 2 * 0.2, seed, 0.35, 1.0) if count > 8 else np.ones(count)
    for i in range(count):
        place(x, one, i * period, gain=level * float(lvl[i % len(lvl)]), pan=pan, wrap=True)
    return x


def amb_mood():
    """夜湖：水轻轻拍岸，远处有虫鸣，底下是一个很淡的小调和弦。"""
    x = np.zeros((N, 2))
    for c in (0, 1):
        x[:, c] = band(N, 90, 1100, slope=-0.9, seed=100 + c) * drift(N, 0.32, 104 + c, 0.05, 1.0) ** 2 * 0.55
    x += crickets(110, 4600, 0.75, -0.6, 0.035) + crickets(111, 5150, 0.6, 0.7, 0.025) + crickets(112, 3900, 1.0, 0.2, 0.02)
    x += pad([D2, A2, 174.61, 329.63], seed=7, bright=0.06) * 0.30
    for at, f in [(3.4, 520), (9.8, 610), (16.1, 470), (21.3, 680)]:
        place(x, bloop(f, f * 1.9, 0.08, 0.25), at, pan=rng.uniform(-0.6, 0.6), wrap=True)
    return finish(reverb(x, 0.3, 3.0, circular=True), 0.28)


def amb_life():
    """万家灯火的傍晚：温暖的大调和弦，零星的火苗噼啪，一点晚风。"""
    x = pad([G2, 146.83, 246.94, 293.66, 440.0], seed=9) * 0.8
    r = np.random.default_rng(120)
    for _ in range(90):
        n = int(SR * r.uniform(0.002, 0.012))
        click = band(max(n, 64), 1800, 9000, seed=int(r.integers(1e6)))[:n] * np.exp(-tt(n) / (n / SR * 0.35))
        place(x, click, r.uniform(0, T), gain=r.uniform(0.02, 0.12), pan=r.uniform(-0.8, 0.8), wrap=True)
    x += wind(130, 0.12)
    return finish(reverb(x, 0.3, 2.8, circular=True), 0.30)


PENTA = [523.25, 587.33, 659.25, 783.99, 880.0, 1046.5, 1174.66, 1318.5]


def lullaby(x, seq, step=1.5, gain=0.2, start=0.4):
    for i, k in enumerate(seq):
        if k is None:
            continue
        place(x, musicbox(PENTA[k]), start + i * step, gain=gain, pan=np.sin(i * 1.7) * 0.4, wrap=True)


def amb_pet():
    """小窝：暖和弦上一只八音盒慢慢地弹，像摇篮曲。"""
    x = pad([130.81, 196.0, 329.63], seed=11, bright=0.08) * 0.55
    lullaby(x, [2, 4, 5, None, 4, 2, 1, None, 0, 2, 4, None, 3, 1, 0, None])
    return finish(reverb(x, 0.4, 2.8, circular=True), 0.28)


def amb_room():
    """房间的午后：很淡的暖和弦，八音盒隔很久才响一两个音。"""
    x = pad([146.83, 220.0, 369.99, 440.0], seed=13, bright=0.06) * 0.6
    lullaby(x, [None, 4, None, None, 2, None, 3, None, None, 5, None, None, 1, None, None, None], gain=0.14)
    x += air(140, 2500, 7000, level=0.02, rate=0.1)
    return finish(reverb(x, 0.4, 3.0, circular=True), 0.24)


# ───────── 音效 ─────────
def sfx_coin(variant):
    """金币入池：一声清脆的金属响，紧跟一小声入水。"""
    f0 = [2850, 3180, 2620][variant]
    ring = modal(f0, [1, 1.47, 2.09, 2.83, 3.71], [1, 0.7, 0.5, 0.3, 0.15], [0.22, 0.16, 0.12, 0.08, 0.05], 0.7, attack=0.0005)
    x = np.zeros((int(SR * 0.9), 2))
    place(x, ring, 0, 0.8)
    place(x, bloop(420 + variant * 60, 900, 0.07, 0.6), 0.035)
    return finish(fade(reverb(x, 0.3, 1.6, lp=7000, seed=5)), 0.5)


def sfx_drop():
    """大的一滴落进水里：两声水泡加一小片水花。"""
    x = np.zeros((int(SR * 1.2), 2))
    place(x, bloop(300, 760, 0.11, 1.0), 0.0)
    place(x, bloop(520, 1250, 0.07, 0.55), 0.10, pan=0.3)
    place(x, bloop(700, 1500, 0.05, 0.3), 0.19, pan=-0.3)
    n = int(SR * 0.35)
    splash = band(n, 1800, 9000, seed=201) * np.exp(-tt(n) / 0.07)
    place(x, splash, 0.005, 0.25)
    return finish(fade(reverb(x, 0.4, 2.6, seed=6)), 0.6)


def sfx_chime(f0=880.0):
    return finish(fade(reverb(bell(f0, 2.6), 0.45, 3.0, seed=7), b=0.3), 0.5)


def sfx_bowl():
    """颂钵敲一下，余音很长，带拍音。"""
    f0 = 261.63
    x = modal(f0, [1, 1.004, 2.71, 2.716, 5.15, 8.2], [1, 0.8, 0.4, 0.3, 0.15, 0.05], [3.0, 3.0, 2.0, 2.0, 1.1, 0.6], 6.5, attack=0.004)
    return finish(fade(reverb(x, 0.35, 3.2, seed=8), b=0.6), 0.5)


def sfx_sparkle():
    """一串细碎的小铃，从低到高散开。"""
    x = np.zeros((int(SR * 1.6), 2))
    for i in range(11):
        f = PENTA[int(rng.integers(3, 8))] * (2 if i % 3 else 4)
        place(x, bell(f, 0.7, 0.6), i * 0.075 + rng.uniform(0, 0.03), gain=rng.uniform(0.3, 0.7), pan=rng.uniform(-0.9, 0.9))
    return finish(fade(reverb(x, 0.45, 2.6, seed=9), b=0.3), 0.42)


def sfx_bloom():
    """光漫上来：和弦慢慢涨起再散开，上面浮着一层亮亮的空气。"""
    n = int(SR * 4.2)
    t = tt(n)
    env = np.minimum(t / 1.7, 1) ** 2 * np.exp(-np.maximum(t - 1.7, 0) / 0.9)
    x = np.zeros((n, 2))
    for i, f in enumerate([261.63, 329.63, 392.0, 523.25, 659.25, 783.99]):
        for c, d in ((0, 1.002), (1, 0.998)):
            x[:, c] += np.sin(2 * np.pi * f * d * t + i) / (1 + i * 0.3)
    x *= env[:, None]
    x += np.stack([band(n, 3500, 11000, seed=210 + c) for c in (0, 1)], axis=1) * (env**1.5)[:, None] * 0.5
    return finish(fade(reverb(x, 0.5, 3.4, seed=10), a=0.05, b=0.5), 0.45)


def sfx_rise():
    """竖琴上行的一串音。"""
    x = np.zeros((int(SR * 1.8), 2))
    for i, f in enumerate([261.63, 329.63, 392.0, 523.25, 659.25, 783.99, 1046.5, 1318.5]):
        place(x, pluck(f, 1.1) * np.exp(-tt(int(SR * 1.1)) / 0.5), i * 0.07, gain=0.6, pan=(i - 3.5) / 5)
    return finish(fade(reverb(x, 0.4, 2.6, seed=11), b=0.3), 0.45)


def sfx_whoosh():
    """有东西轻快地划过：一阵由低到高的风。"""
    n = int(SR * 1.0)
    t = tt(n)
    env = np.sin(np.pi * np.minimum(t / 0.9, 1)) ** 2
    x = np.zeros((n, 2))
    for j, fc in enumerate([300, 600, 1200, 2400]):
        w = np.exp(-(((t - 0.18 - j * 0.16) / 0.2) ** 2))
        for c in (0, 1):
            x[:, c] += band(n, fc * 0.7, fc * 1.5, seed=220 + j * 2 + c) * w
    return finish(fade(reverb(x * env[:, None], 0.25, 1.6, seed=12)), 0.35)


def sfx_breath(inhale):
    """一口气：吸气由弱到强、音色变亮，呼气相反。"""
    n = int(SR * 2.2)
    t = tt(n)
    k = t / 2.2
    env = np.sin(np.pi * k) ** 1.4 * (0.35 + 0.65 * (k if inhale else 1 - k))
    lo = np.stack([band(n, 250, 1100, slope=-0.5, seed=230 + c) for c in (0, 1)], axis=1)
    hi = np.stack([band(n, 1500, 5200, slope=-0.7, seed=234 + c) for c in (0, 1)], axis=1)
    mix = (k if inhale else 1 - k)[:, None]
    x = (lo * (1 - 0.5 * mix) + hi * (0.25 + 0.6 * mix)) * env[:, None]
    return finish(fade(reverb(x, 0.2, 1.4, seed=13), a=0.05, b=0.2), 0.22)


def sfx_step(i):
    """小脚印：一个木琴似的音，一步比一步高。"""
    f = [523.25, 587.33, 659.25, 783.99, 880.0, 1046.5, 1174.66, 1318.5, 1568.0][i]
    x = modal(f, [1, 3.93, 9.6], [1, 0.3, 0.06], [0.22, 0.07, 0.03], 0.6, attack=0.001)
    return finish(fade(reverb(x, 0.3, 1.4, seed=14)), 0.38)


def sfx_heart():
    """两下轻轻的心跳。"""
    x = np.zeros((int(SR * 0.9), 2))
    for at, a in ((0.0, 1.0), (0.27, 0.75)):
        n = int(SR * 0.22)
        t = tt(n)
        f = 90 * np.exp(-t / 0.06) + 48
        place(x, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.07) * np.minimum(t / 0.004, 1), at, a)
    return finish(fade(reverb(x, 0.12, 0.8, lp=2000, seed=15)), 0.55)


def sfx_light():
    """点着一盏灯：噗的一声，接一个暖暖的音。"""
    n = int(SR * 0.5)
    x = np.zeros((int(SR * 1.4), 2))
    place(x, band(n, 150, 1800, slope=-0.8, seed=240) * np.exp(-tt(n) / 0.09) * np.minimum(tt(n) / 0.03, 1), 0, 0.9)
    place(x, bell(392.0, 1.2, 0.4), 0.06, 0.5)
    return finish(fade(reverb(x, 0.3, 1.8, seed=16), b=0.2), 0.4)


def sfx_star():
    """流星：一道很细的、下滑的亮音。"""
    n = int(SR * 0.9)
    t = tt(n)
    f = 3200 * np.exp(-t * 1.1) + 900
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / 0.9) ** 2
    x += 0.4 * band(n, 4000, 10000, seed=250) * np.sin(np.pi * t / 0.9) ** 3
    return finish(fade(reverb(x, 0.45, 2.4, seed=17), b=0.3), 0.26)


def sfx_done():
    """仪式完成：四个钟音依次上行，每一场都用这同一个收尾。"""
    x = np.zeros((int(SR * 3.6), 2))
    for i, f in enumerate([523.25, 659.25, 783.99, 1046.5]):
        place(x, bell(f, 2.6, 0.7), i * 0.17, gain=0.6 + 0.1 * i, pan=(i - 1.5) * 0.3)
    return finish(fade(reverb(x, 0.5, 3.4, seed=18), b=0.5), 0.5)


def sfx_tap():
    """界面上的轻点。"""
    n = int(SR * 0.09)
    t = tt(n)
    x = np.sin(2 * np.pi * 1320 * t) * np.exp(-t / 0.012) + 0.3 * np.sin(2 * np.pi * 2640 * t) * np.exp(-t / 0.006)
    return finish(fade(reverb(x, 0.12, 0.5, seed=19), a=0.001, b=0.03), 0.22)


def sfx_pick():
    """切换分类：一个柔和的拨弦。"""
    x = pluck(659.25, 0.7) * np.exp(-tt(int(SR * 0.7)) / 0.18)
    return finish(fade(reverb(x, 0.3, 1.2, seed=20)), 0.3)


# ───────── 卡点释放的环境音和音效 ─────────
def harp_notes(x, seq, step=2.0, gain=0.16, start=0.6):
    for i, f in enumerate(seq):
        if f:
            n = int(SR * 1.6)
            place(x, pluck(f, 1.6) * np.exp(-tt(n) / 0.7), start + i * step, gain=gain, pan=np.sin(i * 2.1) * 0.5, wrap=True)


def furin(f0, dur=1.6, soft=1.0):
    """日式玻璃风铃的一声：很高的基音带一点拍频，分音不成整数倍，衰减快而干净。"""
    x = modal(f0, [1, 1.0045, 2.71, 5.15, 8.4], [1, 0.7, 0.42 * soft, 0.18 * soft, 0.06 * soft],
              [dur * 0.36, dur * 0.33, dur * 0.18, dur * 0.09, dur * 0.05], dur, attack=0.0015)
    return x


def furin_bed(x, seed, pitches, gusts, gain=0.16):
    """往循环里挂风铃：每阵风来的时候铃舌碰几下，间隔不匀、一下比一下轻；两三只音高不同的铃分在左右。"""
    r = np.random.default_rng(seed)
    for at in gusts:
        f0 = pitches[int(r.integers(0, len(pitches)))]
        pan = r.uniform(-0.75, 0.75)
        hits = int(r.integers(2, 6))
        tcur = at + r.uniform(-0.3, 0.3)
        amp = r.uniform(0.7, 1.0)
        for _ in range(hits):
            place(x, furin(f0 * r.uniform(0.998, 1.002), r.uniform(1.3, 2.0)), tcur % T, gain=gain * amp, pan=pan + r.uniform(-0.08, 0.08), wrap=True)
            tcur += r.uniform(0.11, 0.55)
            amp *= r.uniform(0.5, 0.85)
        # 另一只铃远远地应一声
        if r.uniform() < 0.6:
            f1 = pitches[int(r.integers(0, len(pitches)))]
            place(x, furin(f1, 1.8), (tcur + r.uniform(0.4, 1.4)) % T, gain=gain * 0.35, pan=-pan, wrap=True)


def breeze(seed, level=0.10, lo=500, hi=5200):
    """夏天傍晚的一点风：很轻，一阵一阵。"""
    x = np.stack([band(N, lo, hi, slope=-1.0, seed=seed + c) for c in (0, 1)], axis=1)
    return x * np.stack([drift(N, 0.22, seed + 5 + c, 0.25, 1.0) ** 1.6 for c in (0, 1)], axis=1) * level


# 释放的五场：都是日式风铃，底下垫一点各自的环境（水、风、海），没有旋律
FURIN = [note(27), note(29), note(31), note(34), note(36)]   # C7 D7 E7 G7 A7 一带


def amb_rel_pool():
    """檐下的风铃，旁边细细的流水。"""
    x = breeze(300, 0.06)
    stream = np.stack([band(N, 900, 4800, slope=-0.6, seed=300 + c) for c in (0, 1)], axis=1)
    x += stream * np.stack([drift(N, 9.0, 304 + c, 0.25, 1.0) ** 2 for c in (0, 1)], axis=1) * 0.07
    x += pad([146.83, 220.0, 293.66], seed=21, bright=0.03) * 0.10
    furin_bed(x, 401, [FURIN[1], FURIN[3], FURIN[4]], [1.2, 6.8, 11.5, 16.9, 21.0])
    return finish(reverb(x, 0.30, 2.6, lp=9000, circular=True), 0.27)


def amb_rel_balloon():
    """高处的风里挂着的风铃。"""
    x = wind(310, 0.30) + breeze(312, 0.05)
    x += pad([174.61, 261.63, 349.23], seed=23, bright=0.03) * 0.10
    furin_bed(x, 402, [FURIN[2], FURIN[3], FURIN[4] * 1.122], [2.0, 7.4, 12.2, 15.6, 20.3])
    return finish(reverb(x, 0.30, 2.8, lp=9000, circular=True), 0.27)


def amb_rel_arrow():
    """空旷的殿堂里一只风铃，回声长一点。"""
    x = breeze(320, 0.035, lo=1500, hi=8000)
    x += pad([146.83, 220.0, 293.66, 440.0], seed=24, bright=0.04) * 0.14
    furin_bed(x, 403, [FURIN[0], FURIN[2], FURIN[4]], [1.5, 7.0, 12.8, 18.4], gain=0.15)
    return finish(reverb(x, 0.45, 4.2, lp=9000, circular=True), 0.27)


def amb_rel_potion():
    """夜里窗边的风铃，锅里偶尔咕嘟一下。"""
    x = breeze(330, 0.045)
    x += pad([55.0, 82.41, 110.0, 164.81], seed=25, bright=0.06, trem=0.3) * 0.16
    r = np.random.default_rng(320)
    for _ in range(18):
        f = r.uniform(180, 420)
        place(x, bloop(f, f * r.uniform(1.5, 2.2), r.uniform(0.05, 0.1), 1.0), r.uniform(0, T), gain=r.uniform(0.02, 0.05), pan=r.uniform(-0.5, 0.5), wrap=True)
    furin_bed(x, 404, [FURIN[0], FURIN[1], FURIN[3]], [3.0, 9.2, 14.0, 19.8], gain=0.15)
    return finish(reverb(x, 0.35, 3.2, lp=8000, circular=True), 0.27)


def amb_rel_deep():
    """海边的风铃：底下是闷闷的海水声和一串串气泡。"""
    x = np.zeros((N, 2))
    for c in (0, 1):
        x[:, c] = band(N, 40, 380, slope=-1.2, seed=330 + c) * drift(N, 0.15, 334 + c, 0.4, 1.0)
    x *= 0.22
    x += pad([73.42, 110.0, 146.83], seed=27, bright=0.03, trem=0.35) * 0.10
    r = np.random.default_rng(340)
    for _ in range(30):
        f = r.uniform(500, 1300)
        place(x, bloop(f, f * 1.6, r.uniform(0.03, 0.06), 1.0), r.uniform(0, T), gain=r.uniform(0.012, 0.035), pan=r.uniform(-0.8, 0.8), wrap=True)
    furin_bed(x, 405, [FURIN[1], FURIN[2], FURIN[4]], [1.8, 6.2, 11.0, 16.4, 21.4])
    return finish(reverb(x, 0.40, 3.6, lp=8000, circular=True), 0.27)


def sfx_note(i):
    """小游戏里每点一下响的一声风铃：八个音排成五声音阶，点得越快用到的音越高。"""
    f = [note(17), note(19), note(22), note(24), note(26), note(29), note(31), note(34)][i]   # D6 E6 G6 A6 B6 D7 E7 G7
    x = furin(f, 1.1, soft=0.8) * 0.8
    return finish(reverb(x, 0.22, 1.4, lp=9000), 0.5)


def sfx_snap():
    """锁链断开：一声金属脆响，碎片散开时带着一串渐弱的叮当。"""
    x = np.zeros((int(SR * 2.0), 2))
    place(x, modal(1480, [1, 1.59, 2.31, 3.37, 4.6], [1, 0.8, 0.6, 0.4, 0.25], [0.5, 0.35, 0.25, 0.15, 0.1], 1.2, attack=0.0004), 0, 0.9)
    n = int(SR * 0.06)
    place(x, band(n, 1500, 9000, seed=350) * np.exp(-tt(n) / 0.012), 0, 0.6)
    for i in range(9):
        f = rng.uniform(1900, 4200)
        place(x, modal(f, [1, 1.52, 2.4], [1, 0.5, 0.3], [0.18, 0.1, 0.06], 0.5, attack=0.0005), 0.08 + i * 0.09 + rng.uniform(0, 0.04), gain=0.4 * (1 - i / 11), pan=rng.uniform(-0.9, 0.9))
    return finish(fade(reverb(x, 0.4, 2.6, seed=21), b=0.3), 0.5)


def sfx_pour():
    """倒药水：一股细流落进液体里。"""
    n = int(SR * 2.2)
    t = tt(n)
    env = np.minimum(t / 0.25, 1) * np.minimum((2.2 - t) / 0.5, 1)
    x = np.stack([band(n, 1800, 7000, slope=-0.5, seed=360 + c) for c in (0, 1)], axis=1) * (env * drift(n, 14.0, 364, 0.4, 1.0))[:, None] * 0.25
    r = np.random.default_rng(366)
    for _ in range(42):
        f = r.uniform(350, 900)
        at = r.uniform(0.1, 1.9)
        place(x, bloop(f, f * r.uniform(1.4, 2.1), r.uniform(0.03, 0.07), 1.0), at, gain=r.uniform(0.1, 0.3), pan=r.uniform(-0.4, 0.4))
    return finish(fade(reverb(x, 0.3, 1.8, seed=22), a=0.03, b=0.2), 0.4)


def sfx_bubbles():
    """一串气泡咕嘟着升上来破掉。"""
    x = np.zeros((int(SR * 2.0), 2))
    r = np.random.default_rng(370)
    for i in range(22):
        f = 380 + i * 45 + r.uniform(-60, 60)
        place(x, bloop(f, f * 1.9, r.uniform(0.03, 0.06), 1.0), i * 0.07 + r.uniform(0, 0.04), gain=r.uniform(0.2, 0.5), pan=r.uniform(-0.6, 0.6))
    return finish(fade(reverb(x, 0.35, 2.0, seed=23), b=0.2), 0.4)



# ───────── 许愿殿：庭院的底噪、天气和钟声 ─────────
def birdsong(x, seed, count, lo=2400, hi=5200, level=0.05):
    """零星的鸟鸣：几声很短的上下滑音，散在左右。"""
    r = np.random.default_rng(seed)
    for _ in range(count):
        at = r.uniform(0, T)
        f0 = r.uniform(lo, hi)
        pan = r.uniform(-0.9, 0.9)
        for k in range(int(r.integers(2, 6))):
            dur = r.uniform(0.05, 0.12)
            n = int(SR * dur)
            t = tt(n)
            f = f0 * (1 + r.uniform(-0.18, 0.25) * t / dur + 0.04 * np.sin(2 * np.pi * r.uniform(20, 45) * t))
            chirp = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / dur) ** 2
            place(x, chirp, at + k * r.uniform(0.11, 0.2), gain=level * r.uniform(0.4, 1.0), pan=pan, wrap=True)


def amb_sanc_day():
    """白天的庭院：轻风过树，远近几声鸟叫，檐角的风铃偶尔响一下。"""
    x = wind(600, 0.30)
    leaves = np.stack([band(N, 2500, 9000, slope=-0.7, seed=604 + c) for c in (0, 1)], axis=1)
    x += leaves * np.stack([drift(N, 0.25, 608 + c, 0.0, 1.0) ** 3 for c in (0, 1)], axis=1) * 0.10
    birdsong(x, 610, 16)
    birdsong(x, 611, 7, 1500, 2600, 0.035)
    for at, f in [(5.2, 1568.0), (5.9, 1975.5), (14.7, 1760.0), (20.3, 2093.0)]:
        place(x, bell(f, 2.4, 0.5), at, gain=0.035, pan=0.55, wrap=True)
    x += pad([146.83, 220.0, 293.66], seed=31, bright=0.04) * 0.12
    return finish(reverb(x, 0.3, 2.6, circular=True), 0.26)


def amb_sanc_night():
    """夜里的庭院：虫鸣此起彼伏，很轻的风，远处一只猫头鹰。"""
    x = wind(620, 0.18)
    x += crickets(621, 4400, 0.75, -0.7, 0.04) + crickets(622, 5050, 0.6, 0.6, 0.03) + crickets(623, 3700, 1.0, 0.1, 0.022) + crickets(624, 5600, 0.5, -0.2, 0.014)
    for at in (7.0, 19.0):
        for k, d in enumerate((0.0, 0.55)):
            n = int(SR * 0.42)
            t = tt(n)
            hoot = np.sin(2 * np.pi * (392 - 18 * t / 0.42) * t) * np.sin(np.pi * t / 0.42) ** 2
            place(x, hoot, at + d, gain=0.035 * (1 if k == 0 else 0.7), pan=-0.5, wrap=True)
    x += pad([D2, A2, 174.61], seed=33, bright=0.03) * 0.14
    return finish(reverb(x, 0.4, 3.4, circular=True), 0.24)


def rain(seed, body, hiss, drips):
    """雨：一层打在瓦和地上的沙沙声，一层更细的雨丝，再加檐口零星的水滴。"""
    r = np.random.default_rng(seed)
    x = np.zeros((N, 2))
    for c in (0, 1):
        x[:, c] = band(N, 500, 5200, slope=-0.5, seed=seed + c) * drift(N, 0.35, seed + 4 + c, 0.75, 1.0) * body
        x[:, c] += band(N, 4500, 13000, slope=-0.3, seed=seed + 8 + c) * drift(N, 0.6, seed + 12 + c, 0.6, 1.0) * hiss
        x[:, c] += band(N, 90, 420, slope=-1.2, seed=seed + 16 + c) * drift(N, 0.2, seed + 20 + c, 0.4, 1.0) * body * 0.5
    for _ in range(drips):
        f = r.uniform(600, 1900)
        place(x, bloop(f, f * r.uniform(1.6, 2.4), r.uniform(0.03, 0.07), 1.0), r.uniform(0, T), gain=r.uniform(0.02, 0.07), pan=r.uniform(-1, 1), wrap=True)
    return x


def amb_w_rain():
    """细密的雨：落在瓦上、石板上，檐下滴滴答答。"""
    return finish(reverb(rain(640, 0.5, 0.28, 150), 0.18, 1.6, circular=True), 0.30)


def amb_w_storm():
    """大雨：雨声更沉更满，一阵阵的风把雨卷过来。"""
    x = rain(660, 0.8, 0.4, 90) + wind(670, 0.5)
    gust = drift(N, 0.1, 675, 0.55, 1.0)[:, None]
    return finish(reverb(x * gust, 0.2, 1.8, circular=True), 0.36)


def amb_w_snow():
    """雪天：声音都被雪吸掉了，只剩很低很软的风。"""
    x = wind(680, 0.5)
    hush = np.stack([band(N, 200, 1600, slope=-1.4, seed=684 + c) for c in (0, 1)], axis=1)
    x = x * 0.6 + hush * np.stack([drift(N, 0.15, 688 + c, 0.3, 1.0) for c in (0, 1)], axis=1) * 0.35
    return finish(reverb(x, 0.25, 2.2, lp=2600, circular=True), 0.22)


def sfx_thunder(variant):
    """雷：先是一声裂开的炸响，然后在天上滚很久。variant 1 是远雷，只有滚动。"""
    dur = 7.5
    n = int(SR * dur)
    t = tt(n)
    x = np.zeros((n, 2))
    for c in (0, 1):
        roll = band(n, 28, 180, slope=-1.0, seed=700 + variant * 10 + c)
        bumps = drift(n, 2.5, 704 + variant * 10 + c, 0.25, 1.0) ** 2
        x[:, c] = roll * bumps * np.exp(-t / (2.2 if variant == 0 else 3.0)) * np.minimum(t / (0.02 if variant == 0 else 0.5), 1)
        if variant == 0:
            crack = band(n, 300, 6000, slope=-0.8, seed=708 + c) * np.exp(-t / 0.16)
            crack += band(n, 120, 900, slope=-0.6, seed=712 + c) * np.exp(-np.abs(t - 0.28) / 0.2) * 0.6
            x[:, c] += crack * 0.55
    return finish(fade(reverb(x, 0.45, 4.5, lp=2400, seed=14), b=1.2), 0.75 if variant == 0 else 0.5)


def sfx_bell_temple():
    """寺里的大钟：很低很厚的一声，嗡嗡地响很久，带着缓慢的拍音。"""
    f0 = 92.5
    x = modal(f0, [1, 1.006, 2.0, 2.41, 2.42, 3.0, 4.1, 5.43, 6.8], [1, 0.9, 0.55, 0.5, 0.4, 0.3, 0.2, 0.12, 0.06],
              [5.5, 5.5, 4.0, 3.0, 3.0, 2.2, 1.4, 0.8, 0.4], 11.0, attack=0.006)
    n = int(SR * 0.12)
    thud = band(n, 60, 500, slope=-1.0, seed=720) * np.exp(-tt(n) / 0.03)
    x[:n] += thud * 0.5
    return finish(fade(reverb(x, 0.4, 4.2, lp=3800, seed=15), b=1.5), 0.6)


def sfx_bell_church():
    """教堂的钟：比寺钟亮，带着小三度的泛音，连敲两下。"""
    def one(f0):
        return modal(f0, [0.5, 1, 1.2, 1.5, 2.0, 2.51, 3.01, 4.17], [0.5, 1, 0.55, 0.4, 0.5, 0.25, 0.18, 0.08],
                     [5.0, 4.0, 3.0, 2.4, 2.0, 1.2, 0.9, 0.5], 7.0, attack=0.003)
    x = np.zeros((int(SR * 10.5), 2))
    place(x, one(196.0), 0.0, 1.0, -0.1)
    place(x, one(196.0), 2.6, 0.85, 0.1)
    return finish(fade(reverb(x, 0.42, 4.0, seed=16), b=1.5), 0.55)


def sfx_splash():
    """硬币落进池子：先是金属很轻的一声，然后噗通入水，水花散开。"""
    x = np.zeros((int(SR * 1.8), 2))
    place(x, modal(3200, [1, 1.52, 2.31], [1, 0.5, 0.3], [0.05, 0.035, 0.02], 0.2), 0.0, 0.25)
    place(x, bloop(240, 620, 0.13, 1.0), 0.05)
    place(x, bloop(430, 1100, 0.08, 0.6), 0.16, pan=0.35)
    place(x, bloop(620, 1500, 0.06, 0.4), 0.25, pan=-0.35)
    place(x, bloop(800, 1800, 0.05, 0.25), 0.36, pan=0.2)
    n = int(SR * 0.5)
    place(x, band(n, 1500, 9500, seed=730) * np.exp(-tt(n) / 0.09), 0.05, 0.3)
    return finish(fade(reverb(x, 0.35, 2.2, seed=17)), 0.6)


def sfx_wood():
    """木牌挂上去：木头和木头轻轻碰两下。"""
    x = np.zeros((int(SR * 1.0), 2))
    for at, f, g in [(0.0, 620, 1.0), (0.17, 780, 0.55), (0.29, 700, 0.3)]:
        place(x, modal(f, [1, 2.6, 4.9], [1, 0.4, 0.15], [0.05, 0.03, 0.015], 0.3), at, g, pan=0.1)
    return finish(fade(reverb(x, 0.2, 1.2, seed=18)), 0.5)


def sfx_cloth():
    """布条在风里抖开：两阵很软的窸窣。"""
    n = int(SR * 0.9)
    t = tt(n)
    env = np.exp(-(((t - 0.16) / 0.09) ** 2)) + 0.7 * np.exp(-(((t - 0.48) / 0.12) ** 2))
    x = np.stack([band(n, 900, 7000, slope=-0.9, seed=740 + c) * env for c in (0, 1)], axis=1)
    return finish(fade(reverb(x, 0.15, 1.0, seed=19)), 0.3)


def sfx_foot(i):
    """石板上的一步：闷闷的一声，带一点沙粒。"""
    n = int(SR * 0.22)
    t = tt(n)
    thud = np.sin(2 * np.pi * (95 - 30 * t / 0.22 + i * 8) * t) * np.exp(-t / 0.035)
    grit = band(n, 1800, 6500, slope=-0.6, seed=750 + i) * np.exp(-t / 0.03) * 0.25
    x = np.zeros((int(SR * 0.5), 2))
    place(x, thud + grit, 0.0, 1.0, pan=-0.15 if i % 2 else 0.15)
    return finish(fade(reverb(x, 0.12, 0.9, seed=20 + i)), 0.32)


# ───────── 许愿殿：背景音乐（72 秒无缝循环）和风 ─────────
MUSIC_T = 72.0


def _music_pad(notes, n, seed, level=1.0, bright=0.05):
    return pad(notes, n=n, seed=seed, bright=bright) * level


def amb_music_temple():
    """山寺的背景音乐：很低的长音垫底，一把像古琴的拨弦慢慢地弹五声音阶，偶尔一声磬。"""
    n = int(SR * MUSIC_T)
    x = _music_pad([73.42, 110.0, 146.83], n, 801, 0.55, 0.03)
    x += _music_pad([220.0, 293.66], n, 802, 0.18, 0.05) * drift(n, 0.03, 803, 0.2, 1.0)[:, None]
    r = np.random.default_rng(804)
    scale = [146.83, 174.61, 196.0, 220.0, 261.63, 293.66, 349.23, 392.0, 440.0]
    phrase = [3, None, 5, 4, None, 2, None, None, 6, 5, None, 3, None, 1, None, None, 4, None, 5, 7, None, 5, None, None, 3, 2, None, 0, None, None, 2, None, 3, None, None, None]
    step = MUSIC_T / len(phrase)
    for i, deg in enumerate(phrase):
        if deg is None:
            continue
        f = scale[deg]
        place(x, pluck(f, 4.5, 0.9975), i * step + r.uniform(0, 0.12), gain=r.uniform(0.20, 0.30), pan=r.uniform(-0.35, 0.35), wrap=True)
        if r.random() < 0.35:  # 偶尔带一个低八度的泛音
            place(x, pluck(f / 2, 5.0, 0.998), i * step + 0.03, gain=0.12, pan=r.uniform(-0.2, 0.2), wrap=True)
    for at in (17.0, 53.0):
        place(x, modal(523.25, [1, 1.003, 2.76, 5.4], [1, 0.8, 0.3, 0.1], [3.5, 3.5, 2.0, 0.9], 7.0, attack=0.004), at, gain=0.07, pan=0.3, wrap=True)
    return finish(reverb(x, 0.42, 4.2, lp=4200, seed=31, circular=True), 0.26)


def amb_music_chapel():
    """教堂的背景音乐：风琴一样的和弦慢慢换，上面浮着像人声的长音，偶尔几粒竖琴。"""
    n = int(SR * MUSIC_T)
    t = tt(n)
    x = np.zeros((n, 2))
    chords = [[146.83, 220.0, 293.66, 349.23], [116.54, 174.61, 233.08, 293.66], [174.61, 261.63, 349.23, 440.0], [130.81, 196.0, 261.63, 329.63]]
    seg = MUSIC_T / len(chords)
    for ci, chord in enumerate(chords):
        # 每个和弦一个缓慢的起落，首尾和相邻的和弦交叠
        c = ((t - ci * seg + seg * 0.25) % MUSIC_T) / (seg * 1.5)
        env = np.where(c < 1, np.sin(np.pi * np.clip(c, 0, 1)) ** 2, 0.0)
        for f in chord:
            for h, a in ((1, 1.0), (2, 0.45), (3, 0.22), (4, 0.10)):
                for ch, det in ((0, 0.9985), (1, 1.0015)):
                    x[:, ch] += a * 0.05 * env * np.sin(2 * np.pi * f * h * det * t + ci + h)
    # 人声似的一层：带共振峰的噪声，跟着和弦的根音
    for ci, chord in enumerate(chords):
        c = ((t - ci * seg + seg * 0.1) % MUSIC_T) / (seg * 1.2)
        env = np.where(c < 1, np.sin(np.pi * np.clip(c, 0, 1)) ** 2, 0.0)
        f = chord[2] * 2
        for ch in (0, 1):
            x[:, ch] += 0.035 * env * (np.sin(2 * np.pi * f * t * (1 + 0.002 * np.sin(2 * np.pi * 4.6 * t + ch))) + 0.4 * np.sin(2 * np.pi * f * 2 * t))
    r = np.random.default_rng(811)
    for at, f in [(8.0, 587.33), (9.2, 698.46), (26.5, 698.46), (27.4, 587.33), (44.0, 880.0), (45.3, 698.46), (62.0, 523.25), (63.1, 659.25)]:
        place(x, pluck(f, 3.0, 0.997), at, gain=0.12, pan=r.uniform(-0.5, 0.5), wrap=True)
    return finish(reverb(x, 0.5, 5.5, lp=3800, seed=32, circular=True), 0.26)


def amb_w_wind():
    """刮风：一阵一阵的，带着穿过屋檐和树的呼啸。"""
    x = wind(820, 1.0)
    for c in (0, 1):
        x[:, c] += band(N, 300, 1200, slope=-0.8, seed=824 + c) * drift(N, 0.08, 826 + c, 0.0, 1.0) ** 2 * 0.5
    return finish(reverb(x * drift(N, 0.06, 829, 0.35, 1.0)[:, None], 0.2, 2.0, circular=True), 0.34)

def amb_fountain():
    """许愿池：水从上面的石盘沿一圈落进池里，细密的哗哗声，偶尔几声清亮的水滴。"""
    fall = np.stack([band(N, 900, 7500, slope=-0.35, seed=900 + c) for c in (0, 1)], axis=1)
    fall *= np.stack([drift(N, 9.0, 904 + c, 0.55, 1.0) for c in (0, 1)], axis=1) * drift(N, 0.15, 908, 0.8, 1.0)[:, None]
    low = np.stack([band(N, 180, 700, slope=-0.8, seed=910 + c) for c in (0, 1)], axis=1) * 0.45
    x = fall * 0.22 + low * 0.12
    rng = np.random.default_rng(912)
    for _ in range(int(T * 2.2)):
        f = rng.uniform(900, 2600)
        place(x, bloop(f, f * rng.uniform(1.4, 2.0), rng.uniform(0.03, 0.07), rng.uniform(0.05, 0.16)), rng.uniform(0, T - 0.2), 1.0, rng.uniform(-0.8, 0.8), wrap=True)
    return finish(reverb(x, 0.22, 1.4, circular=True), 0.26)

def amb_lake():
    """湖边：水一下一下轻轻拍岸，很慢。只有低频的涌动，没有高频的沙沙声
    （喷泉那种 900 赫兹以上的细密水声，眼前没有喷泉时听着像电流杂音）。"""
    x = np.zeros((N, 2))
    for c in (0, 1):
        body = band(N, 90, 480, slope=-1.0, seed=930 + c)
        lap = band(N, 280, 1300, slope=-1.5, seed=934 + c)
        swell = drift(N, 0.3, 938 + c, 0.0, 1.0) ** 2.4
        x[:, c] = body * drift(N, 0.12, 942 + c, 0.5, 1.0) * 0.5 + lap * swell * 0.6
    r = np.random.default_rng(946)
    for _ in range(int(T * 0.35)):
        f = r.uniform(320, 760)
        place(x, bloop(f, f * r.uniform(1.25, 1.5), r.uniform(0.06, 0.11), r.uniform(0.03, 0.07)), r.uniform(0, T - 0.3), 1.0, r.uniform(-0.7, 0.7), wrap=True)
    return finish(reverb(x, 0.18, 1.6, lp=2200, circular=True), 0.22)


SOUNDS = {
    "amb_music_temple": amb_music_temple, "amb_music_chapel": amb_music_chapel, "amb_w_wind": amb_w_wind,
    "amb_sanc_day": amb_sanc_day, "amb_sanc_night": amb_sanc_night, "amb_fountain": amb_fountain, "amb_lake": amb_lake,
    "amb_w_rain": amb_w_rain, "amb_w_storm": amb_w_storm, "amb_w_snow": amb_w_snow,
    "sfx_thunder_1": lambda: sfx_thunder(0), "sfx_thunder_2": lambda: sfx_thunder(1),
    "sfx_bell_temple": sfx_bell_temple, "sfx_bell_church": sfx_bell_church,
    "sfx_splash": sfx_splash, "sfx_wood": sfx_wood, "sfx_cloth": sfx_cloth,
    "sfx_foot_1": lambda: sfx_foot(0), "sfx_foot_2": lambda: sfx_foot(1),
    "amb_rel_pool": amb_rel_pool, "amb_rel_balloon": amb_rel_balloon, "amb_rel_arrow": amb_rel_arrow,
    "amb_rel_potion": amb_rel_potion, "amb_rel_deep": amb_rel_deep,
    "sfx_snap": sfx_snap, "sfx_pour": sfx_pour, "sfx_bubbles": sfx_bubbles,
    "amb_wealth": amb_wealth, "amb_career": amb_career, "amb_looks": amb_looks, "amb_health": amb_health,
    "amb_mood": amb_mood, "amb_life": amb_life, "amb_pet": amb_pet, "amb_room": amb_room,
    "sfx_coin_1": lambda: sfx_coin(0), "sfx_coin_2": lambda: sfx_coin(1), "sfx_coin_3": lambda: sfx_coin(2),
    "sfx_drop": sfx_drop, "sfx_chime": sfx_chime, "sfx_chime_hi": lambda: sfx_chime(1318.5), "sfx_bowl": sfx_bowl,
    "sfx_sparkle": sfx_sparkle, "sfx_bloom": sfx_bloom, "sfx_rise": sfx_rise, "sfx_whoosh": sfx_whoosh,
    "sfx_breath_in": lambda: sfx_breath(True), "sfx_breath_out": lambda: sfx_breath(False),
    **{f"sfx_step_{i + 1}": (lambda i=i: sfx_step(i)) for i in range(9)},
    "sfx_heart": sfx_heart, "sfx_light": sfx_light, "sfx_star": sfx_star, "sfx_done": sfx_done,
    "sfx_tap": sfx_tap, "sfx_pick": sfx_pick,
    **{f"sfx_note_{i + 1}": (lambda i=i: sfx_note(i)) for i in range(8)},
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    names = [a for a in sys.argv[1:] if not a.startswith('--')] or list(SOUNDS)
    for name in names:
        x = SOUNDS[name]()
        if x.ndim == 1:
            x = np.stack([x, x], axis=1)
        if name.startswith("sfx_"):
            # 混响尾巴衰减到听不见之后的部分裁掉，再补一个短淡出
            loud = np.where(np.max(np.abs(x), axis=1) > 0.0015)[0]
            x = fade(x[: min(loud[-1] + int(0.1 * SR), x.shape[0])], a=0.0005, b=0.08)
        wav = OUT / f"{name}.wav"
        sf.write(wav, x.astype(np.float32), SR, subtype="PCM_16")
        subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "128000", str(wav), str(OUT / f"{name}.m4a")], check=True)
        keep = "--keep-wav" in sys.argv
        rms = 20 * np.log10(np.sqrt(np.mean(x**2)) + 1e-9)
        seam = float(np.max(np.abs(x[0] - x[-1]))) if name.startswith("amb_") else 0.0
        print(f"{name:16s} {x.shape[0] / SR:5.1f}s  峰值 {np.max(np.abs(x)):.2f}  均方根 {rms:6.1f} dB  首尾差 {seam:.3f}", flush=True)
        if not keep:
            wav.unlink()


if __name__ == "__main__":
    main()
