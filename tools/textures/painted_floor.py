"""大殿里的金砖地（2026-11-18，评审第三轮：「一片平的哑光灰褐，像塑料地板」）。

一整张画好的地，按世界坐标贴（YJToon 的 _Floor：x -6.47..6.47、z 14.42..21.98，就是殿里墙内皮围的那一块），
砖和 tools/blender/buildings.py 里摆的一样（东西 20 块、南北 12 块，每块 0.647 × 0.63 米，砖缝对得上）：
  - 每块砖的深浅、冷暖略有不同；砖面里有石头的斑（浅深两层云斑）、细的石粒、零星几道发丝细的裂纹、几块油渍；
  - 砖边一圈略亮（磨圆了的棱），砖角有小磕口；砖缝是深的一道；
  - 走得多的地方磨得发亮、颜色浅一点：中间过道（殿门到供桌）、供桌前上香那一条、五块拜垫前后、三个门口、去两边静坐区的路；
  - 墙根、佛坛脚下、供桌脚下：积着一层灰（灰白、哑光）、背光那一面略暗。
  贴图的 a 是「磨得多亮」（0 哑光的灰 … 1 镜面一样亮的走道），着色器拿它定反光的强弱和清楚程度。
另外一张平铺的石面细纹（floor_grain.png，512²，灰度，能无缝平铺，一张约 0.6 米），凑近时砖面不是一片平涂。

用法：python3 tools/textures/painted_floor.py [输出目录]
  不给输出目录就写到 unity/Sanctuary/Assets/Toon/Textures（floor_jinzhuan.png、floor_grain.png）；给了输出目录另外拼一张 _floor_sheet.png 给人看。
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
OUT_DEFAULT = os.path.join(ROOT, 'unity', 'Sanctuary', 'Assets', 'Toon', 'Textures')

X0, Z0, XW, ZW = -6.47, 14.42, 12.94, 7.56
NX, NZ = 20, 12
W, H = 2048, 1024


def ss(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def periodic_noise(rng, n, lo, hi, m=None):
    """能无缝平铺的噪声（n×m）：白噪声在频域里只留 lo..hi 这一段（每张图几个周期）。均值 0、标准差 1"""
    m = m or n
    fx = np.fft.fftfreq(m) * m
    fy = np.fft.fftfreq(n) * n
    FX, FY = np.meshgrid(fx, fy)
    r = np.hypot(FX, FY * m / n)
    band = ss(lo * 0.7, lo, r) * (1 - ss(hi, hi * 1.4, r))
    z = np.real(np.fft.ifft2(np.fft.fft2(rng.normal(0, 1, (n, m))) * band))
    return (z - z.mean()) / max(z.std(), 1e-9)


def blob_field(X, Z, spots):
    """几团软的斑：spots = [(x, z, rx, rz, 强度)]"""
    out = np.zeros_like(X)
    for (cx, cz, rx, rz, k) in spots:
        out += k * np.exp(-(((X - cx) / rx) ** 2 + ((Z - cz) / rz) ** 2))
    return out


def floor(out):
    rng = np.random.default_rng(1118)
    xs = X0 + (np.arange(W) + 0.5) / W * XW
    zs = Z0 + (np.arange(H) + 0.5) / H * ZW
    X, Z = np.meshgrid(xs, zs)              # 行 0 是 z 最小（门那一边）；存图时上下翻
    tw, td = XW / NX, ZW / NZ
    bi = np.clip(np.floor((X - X0) / tw).astype(int), 0, NX - 1)
    bj = np.clip(np.floor((Z - Z0) / td).astype(int), 0, NZ - 1)
    fx = (X - X0) / tw - bi                 # 砖里的位置 0..1
    fz = (Z - Z0) / td - bj
    bid = bi * NZ + bj
    nb = NX * NZ
    # ── 每块砖：深浅、冷暖 ──
    val = rng.normal(0, 1, nb)
    warm = rng.normal(0, 1, nb)
    base = np.array([0.355, 0.345, 0.33])
    col = base[None, None, :] * (1 + 0.065 * val[bid])[..., None]
    col = col * (1 + np.stack([0.018, 0.0, -0.022]) * warm[bid][..., None])
    # ── 石面的斑：两层（大块的云斑、小一点的），每块砖错开（金砖是一块块烧出来的，斑不连着） ──
    off = rng.uniform(0, 1000, (nb, 2))
    n1 = periodic_noise(rng, H, 6, 22, W)
    n2 = periodic_noise(rng, H, 30, 90, W)
    n3 = periodic_noise(rng, H, 120, 380, W)
    # 每块砖拿噪声里不同的一片（按砖号错开取），砖与砖之间的斑不连
    sx = (np.arange(W)[None, :] + (off[bid, 0] * 7).astype(int)) % W
    sy = (np.arange(H)[:, None] + (off[bid, 1] * 5).astype(int)) % H
    m1 = n1[sy, sx]
    m2 = n2[sy, sx]
    col *= (1 + 0.05 * m1 + 0.028 * m2 + 0.018 * n3)[..., None]
    # 零星几块油渍（深、略暖）、几处泛白的「析出」
    spots = []
    for _ in range(26):
        spots.append((rng.uniform(X0, X0 + XW), rng.uniform(Z0, Z0 + ZW), rng.uniform(0.06, 0.22), rng.uniform(0.05, 0.18), -rng.uniform(0.05, 0.12)))
    for _ in range(14):
        spots.append((rng.uniform(X0, X0 + XW), rng.uniform(Z0, Z0 + ZW), rng.uniform(0.03, 0.09), rng.uniform(0.03, 0.08), rng.uniform(0.04, 0.08)))
    col *= (1 + blob_field(X, Z, spots))[..., None]
    # ── 砖边：一圈磨圆的棱（略亮），再往外是砖缝（深） ──
    ex = np.minimum(fx, 1 - fx) * tw     # 离东西两边多远（米）
    ez = np.minimum(fz, 1 - fz) * td
    e = np.minimum(ex, ez)
    bevel = (1 - ss(0.004, 0.016, e)) * ss(0.0, 0.006, e)
    col *= (1 + 0.07 * bevel)[..., None]
    grout = 1 - ss(0.003, 0.0075, e)
    col = col * (1 - grout[..., None]) + np.array([0.19, 0.18, 0.17])[None, None, :] * grout[..., None]
    # 砖角的小磕口（亮一点、毛一点）
    chip = np.zeros_like(X)
    for b in range(nb):
        if rng.random() < 0.35:
            i, j = divmod(b, NZ)
            cx = X0 + (i + rng.choice([0.0, 1.0])) * tw
            cz = Z0 + (j + rng.choice([0.0, 1.0])) * td
            chip += np.exp(-(((X - cx) ** 2 + (Z - cz) ** 2) / (rng.uniform(0.012, 0.03) ** 2))) * (bid == b)
    col *= (1 + 0.12 * np.clip(chip, 0, 1) * (1 + 0.5 * n3))[..., None]
    # ── 磨亮的走道（a 大、颜色略浅略暖）：过道、上香那一条、拜垫前后、三个门口、去两边静坐区的路 ──
    wear = np.zeros_like(X)
    wear = np.maximum(wear, ss(1.25, 0.55, np.abs(X)) * ss(14.4, 14.9, Z) * (1 - ss(18.5, 18.85, Z)))      # 中间过道
    wear = np.maximum(wear, np.exp(-((X / 1.5) ** 2 + ((Z - 18.5) / 0.32) ** 2)))                          # 供桌前上香的地方
    for (mx, mz) in ((-1.0, 17.8), (0.0, 17.8), (1.0, 17.8), (-3.6, 18.5), (3.6, 18.5)):
        wear = np.maximum(wear, 0.9 * np.exp(-(((X - mx) / 0.45) ** 2 + ((Z - mz + 0.5) / 0.38) ** 2)))   # 拜垫后面站的地方
    for dx in (-2.64, 0.0, 2.64):
        wear = np.maximum(wear, 0.85 * np.exp(-(((X - dx) / 0.7) ** 2 + ((Z - 14.6) / 0.35) ** 2)))       # 门口
    for sxn in (-1, 1):
        # 去两边静坐区：从过道穿过两根金柱之间往外
        t = np.clip((np.abs(X) - 1.0) / 3.0, 0, 1)
        wear = np.maximum(wear, 0.55 * (np.sign(X) == sxn) * np.exp(-((Z - (16.7 - 0.2 * t)) / 0.35) ** 2) * ss(1.0, 1.6, np.abs(X)) * (1 - ss(4.0, 4.6, np.abs(X))))
    wear = np.clip(wear + 0.12 * (m2 * 0.5) * wear, 0, 1)
    col *= (1 + 0.16 * wear)[..., None]
    col *= (1 + np.array([0.012, 0.004, -0.01]) * wear[..., None])
    # ── 墙根、佛坛脚下、供桌脚下：积灰（灰白、哑光）、靠里的一圈略暗 ──
    dwall = np.minimum(np.minimum(X - X0, X0 + XW - X), Z0 + ZW - Z)
    dust = (1 - ss(0.0, 0.45, dwall)) * (0.6 + 0.4 * ss(-1, 1, m1))
    # 佛坛前沿 z 19.995（|x| < 5.81）、供桌脚
    dais = (np.abs(X) < 5.81) * (1 - ss(19.62, 19.99, Z)) * ss(19.3, 19.62, Z)
    tables = np.zeros_like(X)
    for (cx, cz, hx, hz) in ((0, 19.2, 1.22, 0.4), (-3.6, 19.35, 0.77, 0.325), (3.6, 19.35, 0.77, 0.325)):
        d = np.maximum(np.abs(X - cx) - hx, np.abs(Z - cz) - hz)
        tables = np.maximum(tables, 1 - ss(0.0, 0.18, np.abs(d)))
    dust = np.clip(np.maximum(dust, 0.7 * dais + 0.5 * tables), 0, 1)
    dust_col = np.array([0.5, 0.49, 0.47])
    col = col * (1 - 0.32 * dust[..., None]) + dust_col * 0.32 * dust[..., None]
    col *= (1 - 0.12 * (1 - ss(0.0, 0.12, dwall)))[..., None]
    # ── 发丝细的裂纹（一成多的砖）──
    # 第五轮（评审：一像素宽、近乎黑的线，在游戏里远看成了一截截黑虚线，像渲染出错）：画成 3 像素宽、边上虚的一道，
    # 只比砖面暗一成八（不是黑的），远处看是砖面上一道淡淡的纹，凑近才看得出是裂纹
    mask = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(mask)
    def P(x, z):
        return ((x - X0) / XW * W, (1 - (z - Z0) / ZW) * H)
    for b in range(nb):
        if rng.random() > 0.16:
            continue
        i, j = divmod(b, NZ)
        x, z = X0 + (i + rng.uniform(0.1, 0.9)) * tw, Z0 + j * td + (0 if rng.random() < 0.5 else td)
        ang = rng.uniform(0.3, 2.8) * (1 if z == Z0 + j * td else -1)
        pts = []
        L = rng.uniform(0.12, 0.45)
        for k in range(10):
            pts.append(P(x, z))
            ang += rng.normal(0, 0.35)
            x += math.cos(ang) * L / 10
            z += math.sin(ang) * L / 10
            x = min(max(x, X0 + i * tw + 0.01), X0 + (i + 1) * tw - 0.01)
            z = min(max(z, Z0 + j * td + 0.01), Z0 + (j + 1) * td - 0.01)
        d.line(pts, fill=255, width=3, joint='curve')
    crack = np.asarray(mask.filter(ImageFilter.GaussianBlur(1.1))).astype(np.float64) / 255
    rgb = np.clip(col[::-1], 0, 1) * (1 - 0.18 * crack[..., None])
    rgb = np.round(rgb * 255) / 255
    # ── a：磨得多亮 ──
    pol = 0.34 + 0.06 * m1 + 0.6 * wear
    pol *= 1 - 0.75 * dust
    pol *= 1 - 0.85 * grout
    a = np.clip(pol, 0, 1)[::-1] * (1 - 0.3 * crack)
    img = np.dstack([rgb, a[..., None]])
    p = os.path.join(out, 'floor_jinzhuan.png')
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGBA').save(p, optimize=True)
    return p


def grain(out):
    """石面细纹（512²，能无缝平铺，灰度，0.5 是不变）：细的石粒 + 几道极淡的磨痕（顺着一个方向）"""
    rng = np.random.default_rng(7)
    N = 512
    g = 0.5 + 0.09 * periodic_noise(rng, N, 60, 200) + 0.05 * periodic_noise(rng, N, 12, 40)
    f = np.fft.fftfreq(N) * N
    FX, FY = np.meshgrid(f, f)
    u = FX * math.cos(0.4) + FY * math.sin(0.4)
    v = -FX * math.sin(0.4) + FY * math.cos(0.4)
    r = np.hypot(u * 9, v)
    band = ss(20, 30, r) * (1 - ss(150, 220, r))
    scr = np.real(np.fft.ifft2(np.fft.fft2(rng.normal(0, 1, (N, N))) * band))
    scr = (scr - scr.mean()) / scr.std()
    g += 0.035 * scr
    # 零星的小黑点（石头里的杂质）
    yy, xx = np.mgrid[0:N, 0:N]
    for _ in range(90):
        cx, cy, rr = rng.uniform(0, N), rng.uniform(0, N), rng.uniform(0.6, 1.6)
        dx = (xx - cx + N / 2) % N - N / 2
        dy = (yy - cy + N / 2) % N - N / 2
        g -= 0.18 * np.exp(-(dx * dx + dy * dy) / (rr * rr))
    p = os.path.join(out, 'floor_grain.png')
    Image.fromarray((np.clip(g, 0, 1) * 255 + 0.5).astype(np.uint8), 'L').save(p, optimize=True)
    return p


def main(argv):
    out = argv[0] if argv else OUT_DEFAULT
    os.makedirs(out, exist_ok=True)
    made = [floor(out), grain(out)]
    for p in made:
        print('[paint]', p)
    a = Image.open(made[0])
    rgb = a.convert('RGB').resize((1024, 512))
    al = a.split()[3].convert('RGB').resize((1024, 512))
    sheet = Image.new('RGB', (1024, 1024 + 256))
    sheet.paste(rgb, (0, 0))
    sheet.paste(al, (0, 512))
    sheet.paste(Image.open(made[1]).convert('RGB').resize((256, 256)), (0, 1024))
    # 拼图不放进 Unity 的贴图目录（会被当成贴图导入）
    if os.path.abspath(out) != os.path.abspath(OUT_DEFAULT):
        sheet.save(os.path.join(out, '_floor_sheet.png'))


if __name__ == '__main__':
    main(sys.argv[1:])
