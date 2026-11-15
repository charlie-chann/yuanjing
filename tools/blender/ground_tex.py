"""给小岛的地面画一张细致的贴图（4096×4096，约 1.5 厘米一个像素）。
顶点色只能半米一个颜色，草地、沙滩、土路的交界是糊的；贴图里可以画出清楚的边界、一根根草叶、卵石、沙纹。
用法：python3 ground_tex.py   （先跑过 build_all.sh islet_ground，要用它导出的 islet_map.bytes）"""
import math
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from palette import P  # noqa: E402

ASSETS = os.path.join(HERE, '..', '..', 'unity', 'Sanctuary', 'Assets', 'Toon')
N = 4096
SS = 2                      # 画的时候放大一倍，最后缩回来，线条才不带锯齿
WATER = -0.42
PATH_W, PATH_Y0, PATH_Y1 = 1.35, -15.2, 1.8
BURNER, PLAZA_R = (0.0, -2.0), 3.7
TREE, TREE_BED = (-8.6, -3.0), 2.3
TERRACE = (-11.3, 1.8, 11.3, 9.2)


def col(name):
    return np.array(P[name], dtype=np.float32)


def load_map():
    d = open(os.path.join(ASSETS, 'islet_map.bytes'), 'rb').read()
    nx, ny, x0, y0, step = struct.unpack('<ii3f', d[:20])
    a = np.frombuffer(d[20:], dtype='<f4').reshape(3, ny, nx)
    return nx, ny, x0, y0, step, a


def up(a, size):
    """把半米一格的表放大到贴图大小（双三次，边界平滑）"""
    im = Image.fromarray(a.astype(np.float32), mode='F')
    return np.asarray(im.resize((size, size), Image.BICUBIC), dtype=np.float32)


def vnoise(size, cells, seed):
    """平滑的随机起伏：cells 是横向有几个起伏"""
    r = np.random.default_rng(seed)
    g = r.random((cells + 3, cells + 3)).astype(np.float32)
    im = Image.fromarray(g, mode='F').resize((size + 3 * size // cells, size + 3 * size // cells), Image.BICUBIC)
    return np.asarray(im, dtype=np.float32)[:size, :size]


def fbm(size, cells, seed, octaves=4):
    out = np.zeros((size, size), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        out += vnoise(size, cells * 2 ** o, seed + o * 17) * amp
        tot += amp
        amp *= 0.5
    return out / tot


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def grain(path, n=512):
    """一张能无缝平铺的「手绘颗粒」灰度图：卡通着色器把它按世界坐标铺在所有表面上，
    大块的纯色里就有了细微的深浅（石头的麻点、木头的纹、墙上的笔触），不再是光溜溜一片"""
    r = np.random.default_rng(5)
    f = np.fft.fftfreq(n)[:, None] ** 2 + np.fft.fftfreq(n)[None, :] ** 2
    fr = np.sqrt(f) * n
    out = np.zeros((n, n))
    for lo, hi, amp, stretch in ((2, 7, 0.9, 1.0), (8, 26, 0.7, 1.0), (30, 90, 0.5, 1.0), (10, 60, 0.6, 5.0)):
        w = r.normal(size=(n, n))
        F = np.fft.fft2(w)
        fy = np.fft.fftfreq(n)[:, None] * n
        fx = np.fft.fftfreq(n)[None, :] * n
        rr = np.sqrt((fx / stretch) ** 2 + fy ** 2) if stretch != 1.0 else fr
        band = np.exp(-((rr - (lo + hi) / 2) / ((hi - lo) / 2)) ** 2)
        x = np.real(np.fft.ifft2(F * band))
        out += amp * x / (x.std() + 1e-9)
    out = out / out.std()
    g = np.clip(0.5 + out * 0.17, 0, 1)
    Image.fromarray((g * 255).astype(np.uint8), mode='L').save(path)


def main():
    nx, ny, x0, y0, step, m = load_map()
    x1, y1 = x0 + (nx - 1) * step, y0 + (ny - 1) * step
    # 贴图的行从上到下是 y 从小到大（v=0 在南边），Unity 里 uv = ((x-x0)/W, (z-z0)/H)
    H, S, Pd = up(m[0], N), up(m[1], N), up(m[2], N)
    xs = np.linspace(x0, x1, N, dtype=np.float32)[None, :].repeat(N, 0)
    ys = np.linspace(y0, y1, N, dtype=np.float32)[:, None].repeat(N, 1)

    n_big, n_mid, n_fine, n_edge = fbm(N, 6, 1), fbm(N, 22, 2), fbm(N, 90, 3, 3), fbm(N, 40, 4, 3)

    # ── 草地：几种深浅的色块，边界清楚（不是糊成一片）
    g = n_big * 0.6 + n_mid * 0.4
    img = np.empty((N, N, 3), np.float32)
    img[:] = col('grass')
    for thr, name, soft in ((0.56, 'grass_lit', 0.012), (0.63, 'grass_lit', 0.01), (0.44, 'grass_dark', 0.012), (0.36, 'grass_deep', 0.012)):
        if name.endswith('lit'):
            k = smooth(thr - soft, thr + soft, g)
        else:
            k = 1 - smooth(thr - soft, thr + soft, g)
        k *= 0.75 if name != 'grass_deep' else 0.5
        img = img * (1 - k[..., None]) + col(name) * k[..., None]
    img *= (0.96 + 0.08 * n_fine)[..., None]
    # 土丘上草更深
    k = smooth(0.15, 1.0, H) * 0.6
    img = img * (1 - k[..., None]) + col('grass_deep') * k[..., None]

    # ── 人常走的地方露出土：边界用噪声咬出毛边
    worn = np.zeros((N, N), np.float32)
    inpath = (ys > PATH_Y0 - 1) & (ys < PATH_Y1 + 0.5)
    worn = np.maximum(worn, np.where(inpath, 1 - smooth(PATH_W + 0.15, PATH_W + 1.3, np.abs(xs)), 0))
    worn = np.maximum(worn, 1 - smooth(PLAZA_R + 0.15, PLAZA_R + 1.4, np.hypot(xs - BURNER[0], ys - BURNER[1])))
    tx0, ty0, tx1, ty1 = TERRACE
    dx = np.maximum(np.maximum(tx0 - xs, 0), xs - tx1)
    dy = np.maximum(np.maximum(ty0 - ys, 0), ys - (ty1 + 2.2))
    worn = np.maximum(worn, 1 - smooth(0.15, 1.3, np.hypot(dx, dy)))
    worn = np.maximum(worn, 1 - smooth(TREE_BED + 0.3, TREE_BED + 1.3, np.hypot(xs - TREE[0], ys - TREE[1])))
    dirt_mask = smooth(0.47, 0.53, worn + (n_edge - 0.5) * 0.55)
    dirt = col('dirt') * (0.93 + 0.14 * n_mid)[..., None]
    dirt = dirt * (1 - smooth(0.5, 0.62, n_fine)[..., None] * 0.1)
    img = img * (1 - dirt_mask[..., None]) + dirt * dirt_mask[..., None]

    # ── 沙滩：离岸近的一圈；沙和草的交界清楚、弯弯曲曲
    edge = S + (n_edge - 0.5) * 1.6 + (n_fine - 0.5) * 0.3
    sand_mask = 1 - smooth(2.85, 2.95, edge)
    sand = col('sand') * (0.95 + 0.1 * n_mid)[..., None]
    # 沙纹：顺着岸线的细波纹
    ripple = np.sin(S * 14.0 + n_mid * 9.0) * 0.5 + 0.5
    sand = sand * (1 - (smooth(0.75, 0.95, ripple) * 0.07 * smooth(2.4, 0.6, S))[..., None])
    img = img * (1 - sand_mask[..., None]) + sand * sand_mask[..., None]
    # 池塘边一圈湿泥
    pk = smooth(-0.95, -0.75, Pd + (n_edge - 0.5) * 0.5)
    img = img * (1 - pk[..., None]) + (col('sand_wet') * (0.94 + 0.12 * n_mid)[..., None]) * pk[..., None]
    # 水线：湿沙一条清楚的边，再往下是水底
    wet = smooth(WATER + 0.17, WATER + 0.13, H + (n_fine - 0.5) * 0.04)
    img = img * (1 - wet[..., None] * 0.85) + col('sand_wet') * (wet[..., None] * 0.85)
    depth = np.maximum(0, WATER - H)
    for d0, d1, name in ((0.0, 0.45, 'sand_deep'), (0.35, 1.2, 'lakebed'), (1.1, 2.7, 'lakebed_deep')):
        k = smooth(d0, d1, depth)
        img = img * (1 - k[..., None]) + col(name) * k[..., None]
    under = depth > 0.02
    img = np.where(under[..., None], img * (0.95 + 0.1 * n_mid)[..., None], img)

    grass_mask = (1 - dirt_mask) * (1 - sand_mask) * (1 - pk) * (H > WATER + 0.1)
    land_sand = sand_mask * (H > WATER + 0.1)

    # ── 细节：一笔一笔画上去（放大一倍画，再缩回来）
    base = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((N * SS, N * SS), Image.BILINEAR)
    d = ImageDraw.Draw(base, 'RGBA')
    r = np.random.default_rng(11)
    ppm = N * SS / (x1 - x0)          # 一米多少像素（横向）
    ppm_y = N * SS / (y1 - y0)

    def px(x, y):
        return (x - x0) * ppm, (y - y0) * ppm_y

    def c255(name, k=1.0, a=255):
        c = P[name]
        return (int(min(1, c[0] * k) * 255), int(min(1, c[1] * k) * 255), int(min(1, c[2] * k) * 255), a)

    def sample(mask, n, thr=0.5):
        """按遮罩撒点：返回落在遮罩里的 (x, y)"""
        out = []
        while len(out) < n:
            xx = r.uniform(x0 + 0.5, x1 - 0.5, n * 2)
            yy = r.uniform(y0 + 0.5, y1 - 0.5, n * 2)
            ix = ((xx - x0) / (x1 - x0) * (N - 1)).astype(int)
            iy = ((yy - y0) / (y1 - y0) * (N - 1)).astype(int)
            ok = mask[iy, ix] > thr
            out += list(zip(xx[ok], yy[ok]))
            if len(out) == 0 and n > 0:
                break
        return out[:n]

    # 草叶：成千上万根短短的弯线，亮的暗的都有；镜头在南边，叶尖朝北偏一点
    blades = sample(grass_mask, 190000)
    for i, (x, y) in enumerate(blades):
        cx, cy = px(x, y)
        ln = r.uniform(0.05, 0.13) * ppm
        ang = r.normal(0.0, 0.5)
        ex, ey = cx + math.sin(ang) * ln, cy + math.cos(ang) * ln
        t = r.random()
        c = c255('grass_lit', 1.04, 150) if t < 0.42 else c255('grass_deep', 0.95, 120) if t < 0.8 else c255('grass_dark', 0.9, 140)
        d.line([(cx, cy), ((cx + ex) / 2 + r.normal(0, 1.2), (cy + ey) / 2), (ex, ey)], fill=c, width=2 if t < 0.8 else 3)
    # 草丛的暗根：一小团一小团
    for (x, y) in sample(grass_mask, 14000):
        cx, cy = px(x, y)
        rr = r.uniform(0.04, 0.09) * ppm
        d.ellipse([cx - rr, cy - rr * 0.7, cx + rr, cy + rr * 0.7], fill=c255('grass_deep', 0.92, 60))
    # 草地上零星的小花点
    for name in ('flower_w', 'flower_y', 'flower_p', 'flower_v'):
        for (x, y) in sample(grass_mask, 2600):
            cx, cy = px(x, y)
            rr = r.uniform(0.012, 0.022) * ppm
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=c255(name, 1.0, 235))
    # 土路：小石子（亮面加一圈暗影）、细裂纹
    dirt_only = dirt_mask * (1 - sand_mask) * (H > WATER + 0.1)
    for (x, y) in sample(dirt_only, 9000):
        cx, cy = px(x, y)
        rr = r.uniform(0.012, 0.04) * ppm
        d.ellipse([cx - rr + 1.5, cy - rr * 0.75 - 1.5, cx + rr + 1.5, cy + rr * 0.75 - 1.5], fill=c255('dirt_dark', 0.8, 150))
        d.ellipse([cx - rr, cy - rr * 0.75, cx + rr, cy + rr * 0.75], fill=c255(r.choice(['stone_lit', 'stone', 'slab_b']), 1.0, 235))
    for (x, y) in sample(dirt_only, 2500):
        cx, cy = px(x, y)
        pts = [(cx, cy)]
        ang = r.uniform(0, 6.28)
        for k in range(4):
            ang += r.normal(0, 0.5)
            pts.append((pts[-1][0] + math.cos(ang) * 0.05 * ppm, pts[-1][1] + math.sin(ang) * 0.05 * ppm))
        d.line(pts, fill=c255('dirt_dark', 0.86, 110), width=2)
    # 土和草交界的地方长出一撮撮草尖，盖住土边
    band = (np.abs(worn + (n_edge - 0.5) * 0.55 - 0.5) < 0.05) * (1 - sand_mask)
    for (x, y) in sample(band, 16000):
        cx, cy = px(x, y)
        ln = r.uniform(0.06, 0.14) * ppm
        ang = r.normal(0.0, 0.6)
        d.line([(cx, cy), (cx + math.sin(ang) * ln, cy + math.cos(ang) * ln)],
               fill=c255(r.choice(['grass', 'grass_dark', 'grass_lit', 'grass_deep']), r.uniform(0.92, 1.05), 190), width=2)
    # 沙滩：细沙粒、小卵石、贝壳碎片
    for (x, y) in sample(land_sand, 40000):
        cx, cy = px(x, y)
        rr = r.uniform(0.006, 0.014) * ppm
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=c255('sand_wet', r.uniform(0.86, 1.02), 170) if r.random() < 0.6 else c255('white', 1.0, 150))
    for (x, y) in sample(land_sand, 3500):
        cx, cy = px(x, y)
        rr = r.uniform(0.02, 0.05) * ppm
        d.ellipse([cx - rr + 2, cy - rr * 0.7 - 2, cx + rr + 2, cy + rr * 0.7 - 2], fill=c255('sand_deep', 0.85, 130))
        d.ellipse([cx - rr, cy - rr * 0.7, cx + rr, cy + rr * 0.7], fill=c255(r.choice(['stone_lit', 'slab_c', 'stone', 'white']), 1.0, 240))
    # 沙和草交界：草尖探到沙上
    sband = (np.abs(edge - 2.9) < 0.12) * (H > WATER + 0.12)
    for (x, y) in sample(sband, 26000):
        cx, cy = px(x, y)
        ln = r.uniform(0.07, 0.16) * ppm
        ang = r.normal(0.0, 0.6)
        d.line([(cx, cy), (cx + math.sin(ang) * ln, cy + math.cos(ang) * ln)], fill=c255(r.choice(['grass', 'grass_dark', 'grass_lit']), 1.0, 220), width=3)
    # 水底：卵石和深色的水草斑
    shallow = (depth > 0.03) & (depth < 1.6)
    for (x, y) in sample(shallow.astype(np.float32), 16000):
        cx, cy = px(x, y)
        rr = r.uniform(0.03, 0.09) * ppm
        d.ellipse([cx - rr + 2, cy - rr * 0.7 - 2, cx + rr + 2, cy + rr * 0.7 - 2], fill=c255('lakebed_deep', 0.9, 110))
        d.ellipse([cx - rr, cy - rr * 0.7, cx + rr, cy + rr * 0.7], fill=c255(r.choice(['stone', 'sand_deep', 'slab_b', 'stone_dark']), 1.0, 200))
    for (x, y) in sample(shallow.astype(np.float32), 5000):
        cx, cy = px(x, y)
        for k in range(3):
            ang = r.uniform(-0.6, 0.6)
            ln = r.uniform(0.1, 0.22) * ppm
            d.line([(cx + k * 3, cy), (cx + k * 3 + math.sin(ang) * ln, cy + math.cos(ang) * ln)], fill=c255('pad_dark', 0.9, 150), width=3)

    out = base.resize((N, N), Image.LANCZOS)
    out = out.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=0))
    path = os.path.join(ASSETS, 'Textures', 'islet_ground.png')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Unity 的贴图 v=0 在图的最下面一行，而这里第 0 行是最南边（v=0），所以上下翻一下再存
    out.transpose(Image.FLIP_TOP_BOTTOM).save(path)
    grain(os.path.join(ASSETS, 'Textures', 'toon_grain.png'))
    out.resize((1024, 1024), Image.LANCZOS).save(os.path.join(HERE, 'preview', 'islet_ground_tex.png'))
    # 局部原始大小，看细节
    out.crop((1700, 900, 2500, 1500)).save(os.path.join(HERE, 'preview', 'islet_ground_crop.png'))
    print('地面贴图', out.size, path)


main()
