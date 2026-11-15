"""画叶子贴图：一张图是一小枝，上面十来片叶子（或一簇花）。树冠就是成百上千张这样的小枝卡片。

存成「距离场」：每个像素记的不是颜色，而是「离叶子边缘有多远」。着色器按这个距离来描边，
所以不管放大多少倍，叶子的边缘和叶脉都是清楚的线，不会糊成马赛克。

四个通道：
  R  离叶片轮廓的距离（0.5 是边缘，大于 0.5 在叶子里面）
  G  线条：叶脉，以及叶子叠着叶子时上面那片的边（1 是线的正中，往两边降）
  B  每片叶子的深浅（每片不一样，叶尖比叶根亮一点）；小于 0.12 的是枝条
  A  同 R（给不认距离场的地方当透明度用）

用法：tools/textures/.venv/bin/python tools/textures/leaves.py [名字 ...]
输出：unity/Sanctuary/Assets/Toon/Textures/leaf_<名字>.png，预览在 tools/blender/preview/
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', '..', 'unity', 'Sanctuary', 'Assets', 'Toon', 'Textures')
PREVIEW = os.path.join(HERE, '..', 'blender', 'preview')
BIG, N = 4096, 1024
EDGE_SPREAD = 56          # 轮廓的距离场在大图上覆盖多少像素
LINE_SPREAD = 26


def rot(p, a):
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


# ── 叶形：都画在「叶柄在原点、叶尖朝 +y、长度 1」的坐标里，返回 (轮廓点, 叶脉线段们) ──

def ovate(rng, width=0.42, tip=1.6, wavy=0.0):
    """卵形带尖的叶子（樟、樱的叶子）"""
    pts_l, pts_r = [], []
    n = 40
    bend = rng.uniform(-0.08, 0.08)
    for i in range(n + 1):
        t = i / n
        w = width * math.sin(math.pi * t ** 0.85) ** 0.9 * (1 - 0.35 * t ** tip)
        w *= 1 + wavy * math.sin(t * 38)
        cx = bend * math.sin(math.pi * t)
        pts_l.append((cx - w, t))
        pts_r.append((cx + w, t))
    outline = pts_l + pts_r[::-1]
    mid = [(bend * math.sin(math.pi * i / 20), i / 20) for i in range(21)]
    veins = [mid]
    for k in range(1, 7):
        t = 0.1 + 0.12 * k
        cx = bend * math.sin(math.pi * t)
        w = width * math.sin(math.pi * t ** 0.85) ** 0.9 * (1 - 0.35 * t ** tip)
        for sx in (-1, 1):
            veins.append([(cx, t), (cx + sx * w * 0.5, t + 0.07), (cx + sx * w * 0.88, t + 0.16)])
    return outline, veins


def maple(rng):
    """枫叶：五个尖裂片，边缘有小锯齿"""
    lobes = [(0, 1.0), (52, 0.82), (-52, 0.82), (112, 0.5), (-112, 0.5)]
    order = sorted(lobes, key=lambda x: x[0])
    outline = [(0.0, -0.02)]
    veins = []
    c = (0.0, 0.28)
    for idx, (ang, ln) in enumerate(order):
        a = math.radians(ang)
        tipp = (c[0] + math.sin(a) * ln * 0.72, c[1] + math.cos(a) * ln * 0.72)
        # 每个裂片：从上一个凹口到尖再到下一个凹口，边上带两个小齿
        a0 = math.radians(ang - 26)
        a1 = math.radians(ang + 26)
        n0 = (c[0] + math.sin(a0) * ln * 0.2, c[1] + math.cos(a0) * ln * 0.2)
        n1 = (c[0] + math.sin(a1) * ln * 0.2, c[1] + math.cos(a1) * ln * 0.2)
        for k in (0.0, 0.34, 0.5, 0.7, 0.84):
            base = (n0[0] + (tipp[0] - n0[0]) * k, n0[1] + (tipp[1] - n0[1]) * k)
            jag = 0.035 * ln if k in (0.5, 0.84) else 0.0
            outline.append((base[0] + math.sin(a0 - 0.9) * jag, base[1] + math.cos(a0 - 0.9) * jag))
        outline.append(tipp)
        for k in (0.84, 0.7, 0.5, 0.34, 0.0):
            base = (n1[0] + (tipp[0] - n1[0]) * k, n1[1] + (tipp[1] - n1[1]) * k)
            jag = 0.035 * ln if k in (0.5, 0.84) else 0.0
            outline.append((base[0] + math.sin(a1 + 0.9) * jag, base[1] + math.cos(a1 + 0.9) * jag))
        veins.append([c, ((c[0] + tipp[0]) / 2, (c[1] + tipp[1]) / 2), tipp])
        for f in (0.45, 0.7):
            b = (c[0] + (tipp[0] - c[0]) * f, c[1] + (tipp[1] - c[1]) * f)
            for sx in (-1, 1):
                veins.append([b, (b[0] + math.sin(a + sx * 0.7) * ln * 0.12, b[1] + math.cos(a + sx * 0.7) * ln * 0.12)])
    veins.append([(0, -0.02), c])
    return outline, veins


def ginkgo(rng):
    """银杏：扇形，顶上一个小缺口"""
    outline = [(0.0, 0.0), (-0.03, 0.25)]
    n = 30
    for i in range(n + 1):
        a = math.radians(-62 + 124 * i / n)
        r = 0.72 * (1 + 0.035 * math.sin(i * 2.1)) * (1 - 0.16 * math.exp(-((i - n / 2) / 1.6) ** 2))
        outline.append((math.sin(a) * r, 0.28 + math.cos(a) * r))
    outline += [(0.03, 0.25)]
    veins = [[(0, 0.0), (0, 0.28)]]
    for i in range(13):
        a = math.radians(-56 + 112 * i / 12)
        veins.append([(0, 0.28), (math.sin(a) * 0.66, 0.28 + math.cos(a) * 0.66)])
    return outline, veins


def petal(rng):
    """一朵五瓣花（樱、桃）：画成一整片，花心在 (0, 0.5)"""
    outline = []
    for i in range(5):
        a0 = math.radians(i * 72)
        for k in range(13):
            t = k / 12
            a = a0 + math.radians(-33 + 66 * t)
            r = 0.46 * math.sin(math.pi * t) ** 0.55 * (1 - 0.13 * math.exp(-((t - 0.5) / 0.09) ** 2)) + 0.06
            outline.append((math.sin(a) * r, 0.5 + math.cos(a) * r))
    veins = []
    for i in range(5):
        a = math.radians(i * 72)
        veins.append([(math.sin(a) * 0.05, 0.5 + math.cos(a) * 0.05), (math.sin(a) * 0.34, 0.5 + math.cos(a) * 0.34)])
        for d in (-0.5, 0.5):
            b = a + d
            veins.append([(math.sin(b) * 0.03, 0.5 + math.cos(b) * 0.03), (math.sin(b) * 0.12, 0.5 + math.cos(b) * 0.12)])
    return outline, veins


def needle(rng):
    """一根松针"""
    return [(-0.012, 0), (0.012, 0), (0.008, 0.9), (0.0, 1.0), (-0.008, 0.9)], []


def lance(rng):
    """细长的叶子（竹叶、草）"""
    return ovate(rng, width=0.11, tip=1.0)


# ── 小枝的排法：每种树怎么长叶子 ──
def camphor(rng):
    """樟叶：椭圆、中间最宽、叶尖拖长，叶根出三条主脉（樟树的特征）"""
    n = 40
    width = rng.uniform(0.25, 0.3)
    bend = rng.uniform(-0.1, 0.1)

    def half(t):
        return width * math.sin(math.pi * t ** 0.9) ** 0.8 * (1 - 0.5 * t ** 2.2)

    def cx(t):
        return bend * math.sin(math.pi * t)
    outline = [(cx(i / n) - half(i / n), i / n) for i in range(n + 1)] + [(cx(i / n) + half(i / n), i / n) for i in range(n, -1, -1)]
    veins = [[(cx(i / 20), i / 20) for i in range(21)]]
    for sx in (-1, 1):
        # 从叶根出来、沿着叶缘弯上去的两条
        veins.append([(cx(t) + sx * half(t) * (0.62 if t < 0.6 else 0.62 - (t - 0.6) * 0.9), t) for t in (0.06, 0.16, 0.3, 0.45, 0.6, 0.74)])
        for t in (0.5, 0.64, 0.78):
            veins.append([(cx(t), t), (cx(t) + sx * half(t) * 0.5, t + 0.06), (cx(t) + sx * half(t) * 0.86, t + 0.13)])
    return outline, veins


def sprig_alternate(rng, leaf, count=13, size=(0.27, 0.36), spread=58, twig=True, reach=0.6):
    """叶子沿着一根小枝互生，枝梢一片"""
    items = []
    x, y, a = 0.5, 0.03, rng.uniform(-0.06, 0.06)
    path = [(x, y)]
    for i in range(count):
        step = reach / count
        a += rng.uniform(-0.12, 0.12)
        x, y = x + math.sin(a) * step, y + math.cos(a) * step
        path.append((x, y))
        side = 1 if i % 2 == 0 else -1
        la = a + side * math.radians(spread + rng.uniform(-12, 12)) * (1 - 0.45 * i / count)
        items.append(((x, y), la, rng.uniform(*size) * (1 - 0.25 * i / count), leaf))
    items.append(((x, y), a + rng.uniform(-0.2, 0.2), rng.uniform(*size) * 0.9, leaf))
    return (path if twig else []), items


def sprig_cluster(rng, leaf, count=9, size=(0.3, 0.42)):
    """叶子从一个点散开（枫叶一把把的；银杏一簇）"""
    items = []
    path = [(0.5, 0.02), (0.5 + rng.uniform(-0.03, 0.03), 0.22), (0.5, 0.4)]
    for i in range(count):
        a = math.radians(-100 + 200 * (i + rng.uniform(-0.3, 0.3)) / (count - 1))
        r = rng.uniform(0.0, 0.1)
        items.append(((0.5 + math.sin(a) * r, 0.42 + math.cos(a) * r * 0.5), a * 0.75, rng.uniform(*size), leaf))
    rng.shuffle(items)
    return path, items


def sprig_blossom(rng, count=11):
    """一枝花：细枝上开着花，间着几片小叶子"""
    items = []
    x, y, a = 0.5, 0.03, rng.uniform(-0.1, 0.1)
    path = [(x, y)]
    for i in range(count):
        a += rng.uniform(-0.25, 0.25)
        x, y = x + math.sin(a) * 0.075, y + math.cos(a) * 0.075
        path.append((x, y))
        side = 1 if i % 2 == 0 else -1
        off = rng.uniform(0.05, 0.12)
        if i % 4 == 3:
            items.append(((x, y), a + side * 1.0, rng.uniform(0.16, 0.2), ovate))
        else:
            px, py = x + math.sin(a + side * 1.3) * off, y + math.cos(a + side * 1.3) * off
            s = rng.uniform(0.2, 0.26)
            # 花是整朵画的，花心在自己坐标的 (0, 0.5)，所以摆的时候往回退半个大小
            items.append(((px - math.sin(rng.uniform(0, 6.28)) * 0, py - s * 0.5), rng.uniform(-0.4, 0.4), s, petal))
    return path, items


def sprig_pine(rng, count=5):
    """松针：每个节上一把针，散成扇面"""
    items = []
    x, y, a = 0.5, 0.03, rng.uniform(-0.08, 0.08)
    path = [(x, y)]
    for i in range(count):
        a += rng.uniform(-0.15, 0.15)
        x, y = x + math.sin(a) * 0.13, y + math.cos(a) * 0.13
        path.append((x, y))
        for k in range(26):
            items.append(((x, y), a + math.radians(rng.uniform(-78, 78)), rng.uniform(0.2, 0.3), needle))
    return path, items


SPECIES = {
    # 名字: 小枝怎么排
    'camphor': lambda r: sprig_alternate(r, camphor, 9, (0.25, 0.33), 60, reach=0.7),
    'maple': lambda r: sprig_cluster(r, maple, 9),
    'ginkgo': lambda r: sprig_cluster(r, ginkgo, 8, (0.26, 0.36)),
    'blossom': lambda r: sprig_blossom(r),
    'pine': lambda r: sprig_pine(r),
    'bamboo': lambda r: sprig_alternate(r, lance, 9, (0.36, 0.5), 42),
}


def build(name):
    rng = random.Random(sum(map(ord, name)) * 7)
    path, items = SPECIES[name](rng)
    mask = Image.new('L', (BIG, BIG), 0)
    lines = Image.new('L', (BIG, BIG), 0)
    shade = np.zeros((BIG, BIG), np.float32)
    dm, dl = ImageDraw.Draw(mask), ImageDraw.Draw(lines)

    def px(p):
        return (p[0] * BIG, (1 - p[1]) * BIG)

    # 枝条：先画，叶子盖在上面
    if path:
        tw = Image.new('L', (BIG, BIG), 0)
        ImageDraw.Draw(tw).line([px(p) for p in path], fill=255, width=int(BIG * 0.012), joint='curve')
        dm.line([px(p) for p in path], fill=255, width=int(BIG * 0.012), joint='curve')
        shade = np.where(np.asarray(tw) > 0, 0.06, shade)
    for (base, ang, size, fn) in items:
        outline, veins = fn(rng)
        pts = [px((base[0] + rot((x * size, y * size), -ang)[0], base[1] + rot((x * size, y * size), -ang)[1])) for x, y in outline]
        dm.polygon(pts, fill=255)
        # 这片叶子盖住的地方，底下的线擦掉；再画它自己的边和叶脉
        dl.polygon(pts, fill=0)
        dl.line(pts + [pts[0]], fill=255, width=3)
        for v in veins:
            dl.line([px((base[0] + rot((x * size, y * size), -ang)[0], base[1] + rot((x * size, y * size), -ang)[1])) for x, y in v], fill=255, width=3)
        # 深浅：每片随机一个底色，叶根暗、叶尖亮
        one = Image.new('L', (BIG, BIG), 0)
        ImageDraw.Draw(one).polygon(pts, fill=255)
        bb = one.getbbox()
        if bb is None:
            continue
        m = np.asarray(one.crop(bb)) > 0
        ys, xs = np.mgrid[bb[1]:bb[3], bb[0]:bb[2]]
        ax = (math.sin(ang), math.cos(ang))
        along = ((xs / BIG - base[0]) * ax[0] + ((1 - ys / BIG) - base[1]) * ax[1]) / max(size, 1e-6)
        val = np.clip(rng.uniform(0.3, 0.78) + 0.2 * np.clip(along, 0, 1), 0.15, 1.0)
        region = shade[bb[1]:bb[3], bb[0]:bb[2]]
        shade[bb[1]:bb[3], bb[0]:bb[2]] = np.where(m, val, region)

    m = np.asarray(mask) > 127
    inside = distance_transform_edt(m)
    outside = distance_transform_edt(~m)
    sdf = np.clip(0.5 + (inside - outside) / (2 * EDGE_SPREAD), 0, 1)
    ld = distance_transform_edt(np.asarray(lines) < 127)
    line = np.clip(1 - ld / LINE_SPREAD, 0, 1)
    # 轮廓外面一点的深浅：往外延，缩小以后边上不会混进黑色
    from scipy.ndimage import grey_dilation
    shade_out = grey_dilation(shade, size=(41, 41))
    shade = np.where(m, shade, shade_out)

    def down(a):
        return np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((N, N), Image.LANCZOS))
    r, g, b = down(sdf), down(line), down(shade)
    os.makedirs(OUT, exist_ok=True)
    Image.merge('RGBA', [Image.fromarray(x) for x in (r, g, b, r)]).save(os.path.join(OUT, f'leaf_{name}.png'))
    # 预览：按着色器的画法大致上色，看形状对不对
    alpha = (r.astype(np.float32) / 255 > 0.5).astype(np.float32)
    green = np.array([0.36, 0.62, 0.3]) if name not in ('maple', 'ginkgo', 'blossom') else np.array([0.9, 0.42, 0.22]) if name == 'maple' else np.array([0.96, 0.8, 0.3]) if name == 'ginkgo' else np.array([0.98, 0.72, 0.8])
    bb_ = b.astype(np.float32) / 255
    colr = green[None, None, :] * (0.55 + 0.6 * bb_[..., None])
    colr = np.where((bb_ < 0.12)[..., None], np.array([0.42, 0.3, 0.2])[None, None, :], colr)
    colr *= (1 - 0.45 * (g.astype(np.float32) / 255 > 0.62))[..., None]
    edge = (np.abs(r.astype(np.float32) / 255 - 0.53) < 0.03)
    colr *= (1 - 0.5 * edge)[..., None]
    bg = np.array([0.8, 0.86, 0.9])[None, None, :]
    out = colr * alpha[..., None] + bg * (1 - alpha[..., None])
    os.makedirs(PREVIEW, exist_ok=True)
    Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(os.path.join(PREVIEW, f'leaf_{name}.png'))
    print('叶子', name, len(items), '片')


for n in (sys.argv[1:] or list(SPECIES)):
    build(n)
