"""大殿里的手绘贴图：梁枋的旋子彩画、天花板、藻井、壁画、墙裙。

全是用代码「画」的（PIL + numpy，不用照片素材）：一块块平涂的色面、白线黑线勾边、颜色由浅到深一档一档地「退晕」、
金线描轮廓。每张图先按 2 倍大小画，再缩小（边缘不起锯齿）。三张图集，每张对应一个材质：

  paint_beam.png     2048×1024  梁枋彩画：两种旋子彩画（青箍头、绿箍头）、连珠带、卷草带、流云带
  paint_ceiling.png  2048×1024  左边藻井顶上的圆（宝相花）；右边四格天花板（莲花、法轮、莲花换色、云纹）
  paint_wall.png     2048×4096  十二幅壁画（十八罗汉六幅、诸天礼佛三幅、说法图、净土莲池、飞天：painted_murals.py）；底下两种墙裙

模型里用到哪一块，按 RECTS 里的范围取贴图坐标（tools/blender/buildings.py 里的 hall() 用同一份表）。
贴图坐标 v 朝上：PNG 的最上一行是 v=1。

用法：python3 tools/textures/painted.py [输出目录] [beam ceiling wall ...]
  不给输出目录就写到 unity/Sanctuary/Assets/Toon/Textures；另外拼一张 _hall_paint_sheet.png 给人看。
游戏里：模型上叫 paint_beam 之类的部件用这张图（材质 toon_paint_beam，_BaseMap 是这张图，按模型里的 uv 取色）。
"""
import math
import os
import random
import sys

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:  # Blender 里 buildings.py 只读下面的 RECTS（贴图坐标），不画图
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
OUT_DEFAULT = os.path.join(ROOT, 'unity', 'Sanctuary', 'Assets', 'Toon', 'Textures')
SS = 2

# 每张图里各块的位置（像素，左上角为原点：x0, y0, x1, y1）。buildings.py 换算成贴图坐标
SIZES = {'beam': (2048, 1536), 'ceiling': (2048, 1024), 'wall': (2048, 4096)}
RECTS = {
    'beam': {
        'xuanzi_a': (0, 0, 2048, 256), 'xuanzi_b': (0, 256, 2048, 512),
        'pearl': (0, 512, 2048, 640), 'scroll': (0, 640, 2048, 768), 'cloud': (0, 768, 2048, 1024),
        # 2026-11-17 补：第二种流云（小朵、来回掉头）、拱眼壁两种（斗拱之间的板）、托木头上的旋花
        'cloud_b': (0, 1024, 2048, 1280),
        'gongyan_a': (0, 1280, 512, 1536), 'gongyan_b': (512, 1280, 1024, 1536),
        'tuomu': (1024, 1280, 1280, 1536), 'tuomu_side': (1280, 1280, 1792, 1536),
        'colband': (1792, 1280, 2048, 1408), 'colband_b': (1792, 1408, 2048, 1536),
    },
    'ceiling': {
        'zaojing': (0, 0, 1024, 1024),
        'panel_lotus': (1024, 0, 1536, 512), 'panel_wheel': (1536, 0, 2048, 512),
        'panel_lotus_b': (1024, 512, 1536, 1024), 'panel_cloud': (1536, 512, 2048, 1024),
    },
    # 2026-11-18：十二幅（每一间一幅、不重复；painted_murals.py），图集加高到 4096
    'wall': dict([(f'mural_{i}', (682 * (i % 3), 800 * (i // 3), 682 * (i % 3) + 682, 800 * (i // 3) + 800)) for i in range(12)] +
                 [('dado_a', (0, 3200, 1024, 3648)), ('dado_b', (1024, 3200, 2048, 3648))]),
}


def hexc(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# 配色：石青、石绿、朱、金、墨、粉（清式彩画的那一套，稍微柔和一点，和岛上的卡通配色合得来）
K = {k: hexc(v) for k, v in {
    'blue': '#2b5d92', 'blue_lt': '#5d8cc0', 'blue_pale': '#a8c6e4', 'blue_dk': '#1b3e69', 'blue_deep': '#13294a',
    'green': '#2f8269', 'green_lt': '#5fae8d', 'green_pale': '#a9d8bd', 'green_dk': '#1d5a48', 'green_deep': '#143f33',
    'red': '#c0392b', 'red_lt': '#df6a50', 'red_dk': '#8e2419', 'red_deep': '#5f1710', 'vermil': '#d2492f',
    'gold': '#e6bb4c', 'gold_lt': '#f8e08e', 'gold_dk': '#a77b26',
    'ink': '#1d1b1f', 'white': '#f6f1e3', 'pink': '#ec9cb0', 'pink_lt': '#f9d3dc', 'pink_dk': '#c95d7a',
    'ochre': '#c98b3a', 'plaster': '#e9dcbf', 'plaster_dk': '#d6c49e', 'brown': '#7a5236', 'brown_dk': '#4f3424',
    'yellow': '#f0cf5c', 'purple': '#7a5a96',
}.items()}


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


class Canvas:
    """一张画布。坐标按最终像素写，内部按 SS 倍画"""

    def __init__(self, w, h, bg=(0, 0, 0)):
        self.w, self.h = w, h
        self.im = Image.new('RGB', (w * SS, h * SS), bg)
        self.d = ImageDraw.Draw(self.im)

    def P(self, pts):
        return [(x * SS, y * SS) for (x, y) in pts]

    def poly(self, pts, fill=None, outline=None, width=1.0):
        pts = self.P(pts)
        if fill is not None:
            self.d.polygon(pts, fill=fill)
        if outline is not None and width > 0:
            self.d.line(pts + [pts[0]], fill=outline, width=max(1, int(round(width * SS))), joint='curve')

    def line(self, pts, color, width=1.0):
        self.d.line(self.P(pts), fill=color, width=max(1, int(round(width * SS))), joint='curve')
        # 线头圆一点
        r = width * SS / 2
        if r >= 1.5:
            for (x, y) in (pts[0], pts[-1]):
                self.d.ellipse((x * SS - r, y * SS - r, x * SS + r, y * SS + r), fill=color)

    def circle(self, cx, cy, r, fill=None, outline=None, width=1.0):
        box = ((cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS)
        self.d.ellipse(box, fill=fill, outline=outline, width=max(1, int(round(width * SS))) if outline else 0)

    def ellipse(self, cx, cy, rx, ry, fill=None, outline=None, width=1.0):
        box = ((cx - rx) * SS, (cy - ry) * SS, (cx + rx) * SS, (cy + ry) * SS)
        self.d.ellipse(box, fill=fill, outline=outline, width=max(1, int(round(width * SS))) if outline else 0)

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=1.0):
        self.d.rectangle((x0 * SS, y0 * SS, x1 * SS - 1, y1 * SS - 1), fill=fill, outline=outline,
                         width=max(1, int(round(width * SS))) if outline else 0)

    def paste(self, other, x, y):
        self.im.paste(other.im, (x * SS, y * SS))

    def final(self):
        return self.im.resize((self.w, self.h), Image.LANCZOS)


def bez(p0, p1, p2, p3, n=24):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def arc(cx, cy, r, a0, a1, n=32):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def spiral(cx, cy, r0, r1, a0, turns, n=60, sign=1):
    """阿基米德螺线（云头、卷草的卷）"""
    return [(cx + (r0 + (r1 - r0) * i / n) * math.cos(a0 + sign * turns * 2 * math.pi * i / n),
             cy + (r0 + (r1 - r0) * i / n) * math.sin(a0 + sign * turns * 2 * math.pi * i / n)) for i in range(n + 1)]


def grain(im, amount=6, seed=1, scale=1):
    """一点点手绘颗粒（颜料不匀）"""
    a = np.asarray(im).astype(np.float32)
    rng = np.random.default_rng(seed)
    h, w = a.shape[:2]
    n = rng.normal(0, 1, (h // 4 + 2, w // 4 + 2)).astype(np.float32)
    n = np.asarray(Image.fromarray(n, mode='F').resize((w, h), Image.BICUBIC))
    f = rng.normal(0, 1, (h, w)).astype(np.float32) * 0.5
    a = a + (n * amount + f * amount * 0.6)[..., None] * scale
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# ───────────────────────── 旋子彩画 ─────────────────────────
def whirl(c, cx, cy, R, ring_cols, eye_col, n_out=10, n_in=7, phase=0.0):
    """旋花：外圈一圈旋转的花瓣、里圈一圈、中间旋眼。ring_cols = (外圈色, 外圈浅, 里圈色, 里圈浅)"""
    oc, ol, ic, il = ring_cols
    # 外圈：整个圆先涂底，再画一瓣一瓣（每瓣是一段旋转的月牙，浅色在里、深色在外，退晕）
    c.circle(cx, cy, R, fill=K['white'])
    c.circle(cx, cy, R * 0.965, fill=oc)
    for k in range(n_out):
        a = phase + 2 * math.pi * k / n_out
        pts = []
        for i in range(13):
            t = i / 12
            r = R * (0.55 + 0.41 * t)
            pts.append((cx + r * math.cos(a + 0.5 * t), cy + r * math.sin(a + 0.5 * t)))
        a2 = a + 2 * math.pi / n_out * 0.86
        for i in range(12, -1, -1):
            t = i / 12
            r = R * (0.55 + 0.41 * t)
            pts.append((cx + r * math.cos(a2 + 0.5 * t), cy + r * math.sin(a2 + 0.5 * t)))
        c.poly(pts, fill=ol, outline=K['ink'], width=1.2)
        # 瓣里一道白线（退晕的最浅一档）
        inner = [(cx + R * (0.6 + 0.3 * t) * math.cos(a + 0.12 + 0.5 * t), cy + R * (0.6 + 0.3 * t) * math.sin(a + 0.12 + 0.5 * t)) for t in np.linspace(0, 1, 10)]
        c.line(inner, K['white'], 1.1)
    # 里圈
    c.circle(cx, cy, R * 0.57, fill=K['ink'])
    c.circle(cx, cy, R * 0.55, fill=ic)
    for k in range(n_in):
        a = -phase + 2 * math.pi * (k + 0.5) / n_in
        pts = []
        for i in range(11):
            t = i / 10
            r = R * (0.27 + 0.26 * t)
            pts.append((cx + r * math.cos(a - 0.6 * t), cy + r * math.sin(a - 0.6 * t)))
        a2 = a + 2 * math.pi / n_in * 0.8
        for i in range(10, -1, -1):
            t = i / 10
            r = R * (0.27 + 0.26 * t)
            pts.append((cx + r * math.cos(a2 - 0.6 * t), cy + r * math.sin(a2 - 0.6 * t)))
        c.poly(pts, fill=il, outline=K['ink'], width=1.0)
    # 旋眼：金边、红心、金点
    c.circle(cx, cy, R * 0.27, fill=K['gold_dk'])
    c.circle(cx, cy, R * 0.24, fill=K['gold'])
    c.circle(cx, cy, R * 0.17, fill=eye_col)
    c.circle(cx, cy, R * 0.07, fill=K['gold_lt'])


def xuanzi(w, h, variant):
    """一段梁枋的旋子彩画（一开间）：两头箍头，找头里一整二破的旋花，中间方心。
    variant 'a'：青箍头、绿找头、青方心（方心里金色流云）；'b'：绿箍头、青找头、绿方心（方心里锦纹）"""
    A, B = (K['blue'], K['green']) if variant == 'a' else (K['green'], K['blue'])
    Al, Bl = (K['blue_lt'], K['green_lt']) if variant == 'a' else (K['green_lt'], K['blue_lt'])
    Ad, Bd = (K['blue_dk'], K['green_dk']) if variant == 'a' else (K['green_dk'], K['blue_dk'])
    c = Canvas(w, h, B)
    m = h * 0.06              # 上下边的那道深色边
    # 上下两道：墨线、金线，枋子的棱
    def half(flip):
        # flip=False 画左半，True 画右半（镜像）
        X = (lambda u: w - u * w) if flip else (lambda u: u * w)
        # 箍头
        u0, u1 = 0.0, 0.055
        c.poly([(X(u0), 0), (X(u1), 0), (X(u1), h), (X(u0), h)], fill=A)
        for (uu, col, wd) in ((0.012, K['white'], 2.4), (0.04, K['ink'], 2.0), (0.047, K['gold'], 3.0), (0.055, K['ink'], 2.0)):
            c.line([(X(uu), 0), (X(uu), h)], col, wd)
        # 箍头里的退晕：一道浅色
        c.poly([(X(0.02), 0), (X(0.03), 0), (X(0.03), h), (X(0.02), h)], fill=Al)
        # 找头底色
        u2 = 0.282
        c.poly([(X(u1), 0), (X(u2), 0), (X(u2), h), (X(u1), h)], fill=B)
        # 旋花：一整二破。整的在找头中间，破的（半个）贴着上下边，靠方心那边
        R = h * 0.36
        whirl(c, X(0.135), h / 2, R, (Bd, Bl, Ad, Al), K['red'], phase=0.3 if not flip else -0.3)
        for yy in (0, h):
            whirl(c, X(0.232), yy, R * 0.92, (Ad, Al, Bd, Bl), K['red'], n_out=9, n_in=6)
        # 岔口线：找头和方心之间一道折线（白、墨、金三道）
        band = [(X(0.258), 0), (X(0.272), 0), (X(0.296), h * 0.5), (X(0.272), h), (X(0.258), h), (X(0.282), h * 0.5)]
        c.poly(band, fill=A)
        for (dx, col, wd) in ((-0.004, K['ink'], 3.0), (0.0, K['white'], 2.2), (0.018, K['gold'], 2.6), (0.022, K['ink'], 2.0)):
            pts = [(X(0.258 + dx), 0), (X(0.282 + dx), h * 0.5), (X(0.258 + dx), h)]
            c.line(pts, col, wd)
    half(False)
    half(True)
    # 方心：两头尖的长六边形（方心头是一个带内凹弧的尖角）
    def fx(u):
        return u * w
    tip, sh = 0.30, 0.335
    top, bot = h * 0.16, h * 0.84
    left = bez((fx(tip), h / 2), (fx(tip + 0.012), h * 0.32), (fx(sh - 0.012), top + 4), (fx(sh), top), 10)
    right = [(w - x, y) for (x, y) in reversed(left)]
    outline = left + right + [(w - x, h - y) for (x, y) in left[::-1]][::-1][::-1]
    # 下半边：镜像上半边
    lower_r = [(x, h - y) for (x, y) in reversed(right)]
    lower_l = [(x, h - y) for (x, y) in reversed(left)]
    shape = left + right + lower_r[::-1][::-1] + []
    shape = left + right + [(x, h - y) for (x, y) in reversed(right)] + [(x, h - y) for (x, y) in reversed(left)]
    # 方心外的找头延伸（方心头两边的三角）用找头的底色
    c.poly([(fx(0.28), 0), (fx(0.72), 0), (fx(0.72), h), (fx(0.28), h)], fill=B)
    c.poly(shape, fill=K['white'])
    inset = [(x + (6 if x < w / 2 else -6), y + (5 if y < h / 2 else -5)) for (x, y) in shape]
    c.poly(inset, fill=K['ink'])
    inset2 = [(x + (10 if x < w / 2 else -10), y + (8 if y < h / 2 else -8)) for (x, y) in shape]
    c.poly(inset2, fill=K['gold'])
    inset3 = [(x + (14 if x < w / 2 else -14), y + (11 if y < h / 2 else -11)) for (x, y) in shape]
    c.poly(inset3, fill=A)
    x0, x1 = fx(0.345), fx(0.655)
    if variant == 'a':
        # 方心：金色流云，一朵朵如意云头连成一带
        n = 5
        for k in range(n):
            cx = x0 + (x1 - x0) * (k + 0.5) / n
            cy = h / 2 + (h * 0.06 if k % 2 else -h * 0.06)
            s = h * 0.17
            cloud_head(c, cx, cy, s, K['gold'], K['gold_dk'], K['gold_lt'], flip=(k % 2 == 1))
            if k < n - 1:
                nx = x0 + (x1 - x0) * (k + 1.5) / n
                ny = h / 2 + (h * 0.06 if (k + 1) % 2 else -h * 0.06)
                c.line(bez((cx + s * 0.9, cy), (cx + s * 2.0, cy + (ny - cy) * 0.1 + h * 0.12 * (1 if k % 2 == 0 else -1)),
                           (nx - s * 2.0, ny - h * 0.12 * (1 if k % 2 == 0 else -1)), (nx - s * 0.9, ny)), K['gold'], 3.2)
    else:
        # 方心：锦纹（斜方格，格心一朵小金花）
        step = h * 0.17
        for i in range(-2, int((x1 - x0) / step) + 3):
            for j in range(-1, 6):
                cx = x0 + i * step + (step / 2 if j % 2 else 0)
                cy = h * 0.2 + j * step / 2
                if cx < x0 - 2 or cx > x1 + 2 or cy < h * 0.22 or cy > h * 0.78:
                    continue
                d = step * 0.45
                c.poly([(cx, cy - d / 2), (cx + d, cy), (cx, cy + d / 2), (cx - d, cy)], outline=Al, width=1.6)
                c.circle(cx, cy, step * 0.08, fill=K['gold'])
    # 上下边：墨线和一道细金线
    c.rect(0, 0, w, m, fill=Ad)
    c.rect(0, h - m, w, h, fill=Ad)
    c.line([(0, m), (w, m)], K['ink'], 2.0)
    c.line([(0, h - m), (w, h - m)], K['ink'], 2.0)
    c.line([(0, m * 0.45), (w, m * 0.45)], K['gold'], 2.0)
    c.line([(0, h - m * 0.45), (w, h - m * 0.45)], K['gold'], 2.0)
    return c


def cloud_head(c, cx, cy, s, fill, dark, light, flip=False):
    """如意云头：三个圆团成一朵，下面两个小卷"""
    sg = -1 if flip else 1
    blobs = [(0, -0.25, 0.55), (-0.55, 0.15, 0.42), (0.55, 0.15, 0.42), (0, 0.32, 0.36)]
    for (dx, dy, r) in blobs:
        c.circle(cx + dx * s, cy + dy * s * sg, r * s + 2, fill=dark)
    for (dx, dy, r) in blobs:
        c.circle(cx + dx * s, cy + dy * s * sg, r * s, fill=fill)
    for (dx, dy, r) in blobs[:3]:
        c.line(spiral(cx + dx * s, cy + dy * s * sg, r * s * 0.12, r * s * 0.7, -math.pi / 2 * sg, 1.0, 40, sign=sg), dark, 1.8)
    c.circle(cx, cy - 0.25 * s * sg, 0.14 * s, fill=light)


def band_pearl(w, h):
    """连珠带：青底，一串金珠，珠子之间小菱形"""
    c = Canvas(w, h, K['blue'])
    c.rect(0, 0, w, h * 0.14, fill=K['blue_dk'])
    c.rect(0, h * 0.86, w, h, fill=K['blue_dk'])
    c.line([(0, h * 0.14), (w, h * 0.14)], K['gold'], 2.0)
    c.line([(0, h * 0.86), (w, h * 0.86)], K['gold'], 2.0)
    n = int(w / (h * 0.62))
    for i in range(n):
        x = (i + 0.5) * w / n
        c.circle(x, h / 2, h * 0.25, fill=K['gold_dk'])
        c.circle(x - 1.5, h / 2 - 1.5, h * 0.22, fill=K['gold'])
        c.circle(x - h * 0.07, h / 2 - h * 0.07, h * 0.07, fill=K['gold_lt'])
        xm = x + w / n / 2
        d = h * 0.07
        c.poly([(xm, h / 2 - d), (xm + d, h / 2), (xm, h / 2 + d), (xm - d, h / 2)], fill=K['white'])
    return c


def band_scroll(w, h):
    """卷草带：朱红底，金色卷草一波一波地连下去"""
    c = Canvas(w, h, K['red'])
    c.rect(0, 0, w, h * 0.1, fill=K['red_dk'])
    c.rect(0, h * 0.9, w, h, fill=K['red_dk'])
    c.line([(0, h * 0.1), (w, h * 0.1)], K['gold'], 2.0)
    c.line([(0, h * 0.9), (w, h * 0.9)], K['gold'], 2.0)
    period = h * 1.6
    n = int(round(w / period))
    period = w / n
    pts = [(x, h / 2 + h * 0.2 * math.sin(2 * math.pi * x / period)) for x in np.linspace(0, w, n * 40 + 1)]
    c.line(pts, K['gold_dk'], 5.0)
    c.line(pts, K['gold'], 3.0)
    for i in range(n * 2):
        x = (i + 0.25) * period / 2
        up = (i % 2 == 0)
        y = h / 2 + h * 0.2 * math.sin(2 * math.pi * x / period)
        sg = -1 if up else 1
        cx, cy = x + period * 0.12, y + sg * h * 0.12
        sp = spiral(cx, cy, h * 0.03, h * 0.17, math.pi * (0.9 if up else 1.1), 1.15, 50, sign=1 if up else -1)
        c.line(sp, K['gold_dk'], 4.4)
        c.line(sp, K['gold'], 2.6)
        # 一片叶
        lx, ly = x - period * 0.08, y - sg * h * 0.1
        c.poly(bez((x, y), (lx, ly - sg * h * 0.12), (lx - period * 0.1, ly), (lx - period * 0.13, ly + sg * h * 0.06), 10) +
               bez((lx - period * 0.13, ly + sg * h * 0.06), (lx - period * 0.04, ly + sg * h * 0.1), (x - period * 0.02, y + sg * h * 0.02), (x, y), 10),
               fill=K['green_lt'], outline=K['gold_dk'], width=1.4)
    return c


def band_cloud(w, h):
    """流云带（峻脚的斜板上）：石绿底，一朵朵青白如意云，云尾拖成一条"""
    c = Canvas(w, h, K['green'])
    c.rect(0, 0, w, h * 0.07, fill=K['green_dk'])
    c.rect(0, h * 0.93, w, h, fill=K['green_dk'])
    c.line([(0, h * 0.07), (w, h * 0.07)], K['gold'], 2.4)
    c.line([(0, h * 0.93), (w, h * 0.93)], K['gold'], 2.4)
    n = 5
    for i in range(n):
        cx = (i + 0.5) * w / n
        cy = h * (0.5 + (0.06 if i % 2 else -0.06))
        s = h * 0.3
        # 云尾：一条粗的、两边勾深色，连到下一朵
        tail = bez((cx - s * 0.5, cy + s * 0.35), (cx - s * 2.0, cy + s * 1.0), (cx - w / n + s * 2.0, cy - s * 0.6), (cx - w / n + s * 0.6, cy + (h * 0.12 if i % 2 else -h * 0.12) + s * 0.1))
        c.line(tail, K['blue_dk'], 26)
        c.line(tail, K['blue_pale'], 18)
        c.line(tail, K['white'], 4)
        cloud_head(c, cx, cy, s, K['blue_pale'], K['blue_dk'], K['white'], flip=(i % 2 == 1))
        cloud_head(c, cx - s * 1.1, cy + s * 0.45, s * 0.55, K['blue_pale'], K['blue_dk'], K['white'], flip=(i % 2 == 0))
    return c


def band_cloud_b(w, h):
    """流云带第二种：深一点的石绿底，小朵的如意云一左一右地掉头，云尾短，中间点缀金色小云和散花"""
    c = Canvas(w, h, K['green_dk'])
    c.rect(0, h * 0.08, w, h * 0.92, fill=K['green'])
    c.line([(0, h * 0.08), (w, h * 0.08)], K['gold'], 2.4)
    c.line([(0, h * 0.92), (w, h * 0.92)], K['gold'], 2.4)
    c.line([(0, h * 0.13), (w, h * 0.13)], K['blue_dk'], 1.6)
    c.line([(0, h * 0.87), (w, h * 0.87)], K['blue_dk'], 1.6)
    n = 8
    rng = random.Random(5)
    for i in range(n):
        cx = (i + 0.5) * w / n
        flip = i % 2 == 1
        sg = -1 if flip else 1
        cy = h * (0.46 if flip else 0.54)
        s = h * 0.17
        # 短云尾，往回勾一个卷
        tail = bez((cx - sg * s * 0.6, cy + s * 0.3), (cx - sg * s * 1.6, cy + s * 0.9), (cx - sg * s * 2.6, cy + s * 0.1), (cx - sg * s * 2.4, cy - s * 0.5), 24)
        c.line(tail, K['blue_dk'], 16)
        c.line(tail, K['white'] if flip else K['blue_pale'], 10)
        c.line(spiral(cx - sg * s * 2.4, cy - s * 0.75, s * 0.06, s * 0.3, math.pi / 2, 1.0, 30, sign=-sg), K['blue_dk'], 3)
        cloud_head(c, cx, cy, s, K['white'] if flip else K['blue_pale'], K['blue_dk'], (255, 255, 255), flip=flip)
        cloud_head(c, cx + sg * s * 1.0, cy + s * 0.5, s * 0.5, K['blue_pale'] if flip else K['white'], K['blue_dk'], (255, 255, 255), flip=not flip)
        # 两朵之间：一朵小金云、几片散落的花瓣
        gx = cx + w / n / 2
        cloud_head(c, gx, h * 0.5, h * 0.07, K['gold'], K['gold_dk'], K['gold_lt'], flip=flip)
        for k in range(3):
            px, py = gx + rng.uniform(-w / n * 0.3, w / n * 0.3), h * rng.uniform(0.2, 0.8)
            if abs(px - gx) < h * 0.12:
                continue
            a = rng.uniform(0, math.pi)
            r = h * 0.025
            c.poly([(px + math.cos(a) * r * 2, py + math.sin(a) * r * 2), (px - math.sin(a) * r, py + math.cos(a) * r),
                    (px - math.cos(a) * r * 2, py - math.sin(a) * r * 2), (px + math.sin(a) * r, py - math.cos(a) * r)], fill=K['pink'], outline=K['pink_dk'], width=1.0)
    return c


def gongyan(w, h, kind):
    """拱眼壁（两攒斗拱之间那块板）：朱红底，金边的绿框（上窄下宽，跟着斗拱的空当），框里一朵莲（a）或火焰宝珠（b）"""
    c = Canvas(w, h, K['red_dk'])
    m = w * 0.06
    top, bot = h * 0.1, h * 0.92
    frame = [(m * 2.2, top), (w - m * 2.2, top), (w - m, bot), (m, bot)]
    c.poly(frame, fill=K['green_dk'], outline=K['gold'], width=3.0)
    inner = [(m * 3.2, top + h * 0.06), (w - m * 3.2, top + h * 0.06), (w - m * 2.0, bot - h * 0.05), (m * 2.0, bot - h * 0.05)]
    c.poly(inner, fill=K['red'], outline=K['gold_dk'], width=1.6)
    cx, cy = w / 2, h * 0.55
    if kind == 'a':
        # 莲座上一朵正面的莲花，两边卷草
        for sg in (-1, 1):
            sp = spiral(cx + sg * w * 0.24, cy + h * 0.12, h * 0.02, h * 0.12, math.pi * (0.5 + 0.5 * sg), 1.2, 40, sign=sg)
            c.line(sp, K['gold_dk'], 5)
            c.line(sp, K['gold'], 3)
            c.poly(bez((cx + sg * w * 0.06, cy + h * 0.2), (cx + sg * w * 0.16, cy + h * 0.02), (cx + sg * w * 0.3, cy - h * 0.02), (cx + sg * w * 0.34, cy + h * 0.08), 10) +
                   bez((cx + sg * w * 0.34, cy + h * 0.08), (cx + sg * w * 0.24, cy + h * 0.12), (cx + sg * w * 0.14, cy + h * 0.2), (cx + sg * w * 0.06, cy + h * 0.2), 10),
                   fill=K['green_lt'], outline=K['green_deep'], width=1.4)
        lotus_side(c, cx, cy + h * 0.06, h * 0.26, 1.0, stem=0)
        c.ellipse(cx, cy + h * 0.22, w * 0.14, h * 0.04, fill=K['gold_dk'])
    else:
        # 火焰宝珠：一颗白珠，外面一圈红焰、一圈金焰
        for (r, col, tips) in ((0.2, K['gold'], 7), (0.16, K['vermil'], 5)):
            # 上半圈一条条往上卷的火舌（尖往右偏一点），下半圈是圆的
            pts = []
            for i in range(tips):
                a0 = math.pi + math.pi * i / tips
                a1 = math.pi + math.pi * (i + 1) / tips
                am = (a0 + a1) / 2 + 0.12
                L = 1.55 + 0.35 * math.sin(math.pi * (i + 0.5) / tips)
                pts += [(cx + math.cos(a0) * h * r, cy + math.sin(a0) * h * r),
                        (cx + math.cos(am - 0.1) * h * r * (1 + (L - 1) * 0.5), cy + math.sin(am - 0.1) * h * r * (1 + (L - 1) * 0.5)),
                        (cx + math.cos(am + 0.08) * h * r * L, cy + math.sin(am + 0.08) * h * r * L)]
            pts += [(cx + math.cos(a) * h * r, cy + math.sin(a) * h * r) for a in np.linspace(0, math.pi, 12)]
            c.poly(pts, fill=col, outline=K['gold_dk'], width=1.4)
        c.circle(cx, cy, h * 0.13, fill=K['white'], outline=K['blue_dk'], width=2.0)
        c.circle(cx - h * 0.04, cy - h * 0.04, h * 0.04, fill=(255, 255, 255))
        for sg in (-1, 1):
            cloud_head(c, cx + sg * w * 0.3, cy + h * 0.2, h * 0.09, K['blue_pale'], K['blue_dk'], K['white'], flip=sg > 0)
    return c


def col_band(w, h, kind):
    """柱头下的一圈：青地，上下金边，中间金色缠枝（一个卷、一朵小花），左右接得上（绕柱子一圈接两遍）"""
    c = Canvas(w, h, K['blue_dk'] if kind == 'a' else K['green_dk'])
    c.rect(0, 0, w, h * 0.1, fill=K['gold_dk'])
    c.rect(0, h * 0.9, w, h, fill=K['gold_dk'])
    c.line([(0, h * 0.13), (w, h * 0.13)], K['gold'], 1.6)
    c.line([(0, h * 0.87), (w, h * 0.87)], K['gold'], 1.6)
    pts = [(x, h / 2 + h * 0.16 * math.sin(2 * math.pi * x / w)) for x in np.linspace(0, w, 60)]
    c.line(pts, K['gold_dk'], 5)
    c.line(pts, K['gold'], 3)
    for (x, up) in ((w * 0.25, True), (w * 0.75, False)):
        y = h / 2 + h * 0.16 * math.sin(2 * math.pi * x / w)
        sg = -1 if up else 1
        sp = spiral(x + w * 0.06, y + sg * h * 0.1, h * 0.02, h * 0.17, math.pi * (0.9 if up else 1.1), 1.1, 40, sign=1 if up else -1)
        c.line(sp, K['gold_dk'], 4.6)
        c.line(sp, K['gold'], 2.8)
        fx_, fy_ = x - w * 0.1, y - sg * h * 0.12
        for k in range(5):
            a = 2 * math.pi * k / 5
            c.circle(fx_ + math.cos(a) * h * 0.06, fy_ + math.sin(a) * h * 0.06, h * 0.05, fill=K['vermil'] if kind == 'a' else K['pink'])
        c.circle(fx_, fy_, h * 0.04, fill=K['gold'])
    return c


def tuomu_end(w, h):
    """托木（梁头下的云头木）的端头：青地金边，中间一朵小旋花"""
    c = Canvas(w, h, K['blue_dk'])
    c.rect(w * 0.06, h * 0.06, w * 0.94, h * 0.94, fill=K['blue'], outline=K['gold'], width=3)
    whirl(c, w / 2, h / 2, w * 0.34, (K['blue_dk'], K['blue_lt'], K['green_dk'], K['green_lt']), K['vermil'], n_out=8, n_in=6)
    return c


def tuomu_side(w, h):
    """托木的侧面：绿地，金边，一道卷云纹沿着下沿卷上来"""
    c = Canvas(w, h, K['green_dk'])
    c.rect(w * 0.02, h * 0.05, w * 0.98, h * 0.95, fill=K['green'], outline=K['gold'], width=3)
    pts = bez((w * 0.05, h * 0.75), (w * 0.35, h * 0.95), (w * 0.6, h * 0.35), (w * 0.85, h * 0.45), 40)
    c.line(pts, K['gold_dk'], 7)
    c.line(pts, K['gold'], 4)
    for (x, y, r, sg) in ((0.85, 0.45, 0.18, -1), (0.3, 0.65, 0.12, 1), (0.6, 0.62, 0.1, -1)):
        sp = spiral(w * x, h * y - h * r, h * 0.02, h * r, math.pi / 2, 1.2, 40, sign=sg)
        c.line(sp, K['gold_dk'], 6)
        c.line(sp, K['gold'], 3.6)
    c.poly(bez((w * 0.45, h * 0.3), (w * 0.55, h * 0.12), (w * 0.7, h * 0.1), (w * 0.75, h * 0.2), 10) +
           bez((w * 0.75, h * 0.2), (w * 0.65, h * 0.28), (w * 0.55, h * 0.32), (w * 0.45, h * 0.3), 10), fill=K['blue_lt'], outline=K['blue_dk'], width=1.4)
    return c


# ───────────────────────── 天花板、藻井 ─────────────────────────
def panel_frame(c, x0, y0, S, ground, ring, ring_lt, corner, corner_lt):
    """天花板的框：底色、四个岔角云、中间圆光（白、墨、金三道圈）"""
    c.rect(x0, y0, x0 + S, y0 + S, fill=ground)
    # 边上一圈细线（支条遮住大半）
    c.rect(x0 + S * 0.03, y0 + S * 0.03, x0 + S * 0.97, y0 + S * 0.97, outline=K['gold'], width=2.2)
    cx, cy = x0 + S / 2, y0 + S / 2
    # 岔角云：四个角各一组云头（画在角上，超出板子的部分自然被裁掉）
    for (sx, sy) in ((0, 0), (1, 0), (0, 1), (1, 1)):
        px, py = x0 + sx * S, y0 + sy * S
        dx, dy = (1 if sx == 0 else -1), (1 if sy == 0 else -1)
        c.circle(px, py, S * 0.25, fill=K['ink'])
        c.circle(px, py, S * 0.24, fill=corner)
        c.circle(px, py, S * 0.165, fill=corner_lt)
        for (u, v, r) in ((0.2, 0.06, 0.07), (0.06, 0.2, 0.07), (0.15, 0.15, 0.075)):
            cx_, cy_ = px + dx * S * u, py + dy * S * v
            c.circle(cx_, cy_, r * S + 2, fill=K['ink'])
            c.circle(cx_, cy_, r * S, fill=K['white'])
            c.line(spiral(cx_, cy_, 1, r * S * 0.75, math.atan2(-dy, -dx), 1.1, 30), corner, 1.8)
        c.line(arc(px, py, S * 0.205, 0, 2 * math.pi, 64), K['gold'], 1.6)
    R = S * 0.38
    c.circle(cx, cy, R + 3, fill=K['ink'])
    c.circle(cx, cy, R, fill=K['white'])
    c.circle(cx, cy, R * 0.95, fill=K['gold'])
    c.circle(cx, cy, R * 0.92, fill=K['ink'])
    c.circle(cx, cy, R * 0.9, fill=ring)
    c.circle(cx, cy, R * 0.76, fill=ring_lt)
    c.circle(cx, cy, R * 0.72, fill=ring)
    return cx, cy, R * 0.72


def lotus_top(c, cx, cy, R, petal=K['pink'], petal_lt=K['pink_lt'], petal_dk=K['pink_dk']):
    """俯看的一朵莲花：两层八瓣，中间莲蓬"""
    for layer, (rr, n, ph) in enumerate(((1.0, 8, 0.0), (0.68, 8, math.pi / 8))):
        for k in range(n):
            a = ph + 2 * math.pi * k / n
            L = R * rr
            Wd = L * 0.42
            ca, sa = math.cos(a), math.sin(a)
            def P(u, v):
                return (cx + ca * u - sa * v, cy + sa * u + ca * v)
            pts = bez(P(L * 0.12, 0), P(L * 0.35, Wd * 1.1), P(L * 0.9, Wd * 0.7), P(L, 0), 14) + \
                bez(P(L, 0), P(L * 0.9, -Wd * 0.7), P(L * 0.35, -Wd * 1.1), P(L * 0.12, 0), 14)
            c.poly(pts, fill=petal_dk if layer == 0 else petal, outline=K['gold_dk'], width=1.6)
            inner = bez(P(L * 0.25, 0), P(L * 0.42, Wd * 0.6), P(L * 0.8, Wd * 0.38), P(L * 0.9, 0), 10) + \
                bez(P(L * 0.9, 0), P(L * 0.8, -Wd * 0.38), P(L * 0.42, -Wd * 0.6), P(L * 0.25, 0), 10)
            c.poly(inner, fill=petal if layer == 0 else petal_lt)
            c.line([P(L * 0.3, 0), P(L * 0.82, 0)], K['white'], 1.3)
    c.circle(cx, cy, R * 0.3, fill=K['gold_dk'])
    c.circle(cx, cy, R * 0.27, fill=K['yellow'])
    for k in range(7):
        a = 2 * math.pi * k / 7
        c.circle(cx + R * 0.15 * math.cos(a), cy + R * 0.15 * math.sin(a), R * 0.04, fill=K['green_dk'])
    c.circle(cx, cy, R * 0.04, fill=K['green_dk'])


def dharma_wheel(c, cx, cy, R):
    """法轮：八根辐条，外圈带八个小尖，金色"""
    g, gd, gl = K['gold'], K['gold_dk'], K['gold_lt']
    for k in range(8):
        a = 2 * math.pi * k / 8 + math.pi / 8
        ca, sa = math.cos(a), math.sin(a)
        c.poly([(cx + ca * R * 0.98 - sa * R * 0.07, cy + sa * R * 0.98 + ca * R * 0.07), (cx + ca * R * 1.12, cy + sa * R * 1.12),
                (cx + ca * R * 0.98 + sa * R * 0.07, cy + sa * R * 0.98 - ca * R * 0.07)], fill=g, outline=gd, width=1.4)
    c.circle(cx, cy, R, fill=gd)
    c.circle(cx, cy, R * 0.94, fill=g)
    c.circle(cx, cy, R * 0.78, fill=gd)
    c.circle(cx, cy, R * 0.74, fill=K['red'])
    for k in range(8):
        a = 2 * math.pi * k / 8
        ca, sa = math.cos(a), math.sin(a)
        pts = [(cx + ca * R * 0.2 - sa * R * 0.05, cy + sa * R * 0.2 + ca * R * 0.05), (cx + ca * R * 0.45 - sa * R * 0.09, cy + sa * R * 0.45 + ca * R * 0.09),
               (cx + ca * R * 0.76, cy + sa * R * 0.76), (cx + ca * R * 0.45 + sa * R * 0.09, cy + sa * R * 0.45 - ca * R * 0.09),
               (cx + ca * R * 0.2 + sa * R * 0.05, cy + sa * R * 0.2 - ca * R * 0.05)]
        c.poly(pts, fill=g, outline=gd, width=1.4)
    c.circle(cx, cy, R * 0.26, fill=gd)
    c.circle(cx, cy, R * 0.22, fill=g)
    # 轮心的三旋（喜旋）
    for k in range(3):
        a = 2 * math.pi * k / 3
        c.line(spiral(cx, cy, R * 0.02, R * 0.18, a, 0.45, 20), K['red'], 2.2)
    c.circle(cx - R * 0.3, cy - R * 0.55, R * 0.06, fill=gl)


def ceiling_panel(c, x0, y0, S, kind):
    if kind == 'lotus':
        cx, cy, r = panel_frame(c, x0, y0, S, K['green'], K['blue'], K['blue_lt'], K['blue'], K['blue_pale'])
        lotus_top(c, cx, cy, r * 0.95)
    elif kind == 'lotus_b':
        cx, cy, r = panel_frame(c, x0, y0, S, K['blue'], K['green'], K['green_lt'], K['green'], K['green_pale'])
        lotus_top(c, cx, cy, r * 0.95, K['white'], (255, 250, 240), (230, 200, 190))
    elif kind == 'wheel':
        cx, cy, r = panel_frame(c, x0, y0, S, K['green'], K['blue'], K['blue_lt'], K['blue'], K['blue_pale'])
        dharma_wheel(c, cx, cy, r * 0.78)
    elif kind == 'cloud':
        # 藻井的角蝉、斜板用：金色云纹铺满，绿底
        c.rect(x0, y0, x0 + S, y0 + S, fill=K['green'])
        rng = random.Random(9)
        for i in range(3):
            for j in range(3):
                cloud_head(c, x0 + S * (i + 0.5) / 3 + (S / 12 if j % 2 else 0), y0 + S * (j + 0.5) / 3, S * 0.085, K['gold'], K['gold_dk'], K['gold_lt'], flip=(i + j) % 2 == 1)
        c.rect(x0 + 4, y0 + 4, x0 + S - 4, y0 + S - 4, outline=K['gold'], width=3)


def zaojing_disc(S):
    """藻井顶上的圆：深青底，外圈连珠，几圈宝相花瓣一层层往里收，中间留给立体的莲花"""
    c = Canvas(S, S, K['blue_deep'])
    cx = cy = S / 2
    R = S * 0.49
    c.circle(cx, cy, R, fill=K['gold_dk'])
    c.circle(cx, cy, R * 0.97, fill=K['blue_dk'])
    # 连珠一圈
    n = 64
    for k in range(n):
        a = 2 * math.pi * k / n
        c.circle(cx + R * 0.92 * math.cos(a), cy + R * 0.92 * math.sin(a), R * 0.03, fill=K['gold'])
    c.circle(cx, cy, R * 0.87, fill=K['gold'])
    c.circle(cx, cy, R * 0.855, fill=K['green_dk'])
    # 外层宝相花瓣（16 瓣，绿，退晕三档）
    for layer, (r0, r1, n, cols, ph) in enumerate((
            (0.5, 0.85, 16, (K['green_dk'], K['green'], K['green_lt'], K['green_pale']), 0.0),
            (0.36, 0.66, 12, (K['blue_dk'], K['blue'], K['blue_lt'], K['blue_pale']), math.pi / 12),
            (0.22, 0.46, 8, (K['red_dk'], K['red'], K['red_lt'], K['pink_lt']), 0.0))):
        for k in range(n):
            a = ph + 2 * math.pi * k / n
            ca, sa = math.cos(a), math.sin(a)
            Wd = R * r1 * math.sin(math.pi / n) * 1.25
            for step, col in enumerate(cols):
                kk = 1 - step * 0.22
                L0, L1 = R * r0, R * (r0 + (r1 - r0) * kk)
                w2 = Wd * kk

                def P(u, v):
                    return (cx + ca * u - sa * v, cy + sa * u + ca * v)
                pts = bez(P(L0, 0), P(L0, w2 * 1.1), P(L1 - (L1 - L0) * 0.25, w2 * 1.05), P(L1, 0), 14) + \
                    bez(P(L1, 0), P(L1 - (L1 - L0) * 0.25, -w2 * 1.05), P(L0, -w2 * 1.1), P(L0, 0), 14)
                c.poly(pts, fill=col, outline=K['ink'] if step == 0 else None, width=1.6)
            # 瓣尖一个小卷
            tip = (cx + ca * R * r1 * 0.93, cy + sa * R * r1 * 0.93)
            c.circle(tip[0], tip[1], R * 0.012, fill=K['gold'])
    # 中心：金色圆，立体的莲花盖在上面
    c.circle(cx, cy, R * 0.24, fill=K['gold_dk'])
    c.circle(cx, cy, R * 0.22, fill=K['gold'])
    c.circle(cx, cy, R * 0.14, fill=K['red'])
    return c


# ───────────────────────── 壁画 ─────────────────────────
def noise1(n, seed, octaves=4):
    rng = np.random.default_rng(seed)
    out = np.zeros(n)
    for o in range(octaves):
        k = 4 * 2 ** o
        pts = rng.normal(0, 1, k + 1)
        xs = np.linspace(0, k, n)
        out += np.interp(xs, np.arange(k + 1), pts) / (1.8 ** o)
    return out / np.abs(out).max()


def mountain(c, x0, x1, base, peaks, seed, top_col, mid_col, base_col, line=K['ink'], gold=True):
    """青绿山：每座峰由几块圆头的山石簇在一起（轮廓起伏、不尖），颜色从峰顶的石青过渡到山腰石绿、山脚赭石，
    轮廓一道深色边、峰顶描金，山坡上几道皴笔。peaks: [(x, 高度, 宽)]（按最终像素）"""
    rng = random.Random(seed)
    W, H = c.im.size
    xs = np.arange(W, dtype=np.float32) / SS
    ys = np.full(W, float(base), dtype=np.float32)
    bumps = []
    for (px, ph, pw) in peaks:
        bumps.append((px, ph, pw))
        for _ in range(4):
            bumps.append((px + rng.uniform(-0.75, 0.75) * pw, ph * rng.uniform(0.45, 0.85), pw * rng.uniform(0.25, 0.45)))
    for (px, ph, pw) in bumps:
        u = np.clip((xs - px) / pw, -1, 1)
        prof = np.maximum(np.cos(u * math.pi / 2), 0.0) ** 1.6
        ys = np.minimum(ys, base - ph * prof)
    ys += (noise1(W, seed, 6) * 2.5 + noise1(W, seed + 3, 3) * 4).astype(np.float32)
    ys = np.minimum(ys, base)
    ok = (xs >= x0) & (xs <= x1)
    ys[~ok] = base
    a = np.asarray(c.im).astype(np.float32).copy()
    yy = np.arange(H, dtype=np.float32)[:, None] / SS
    top = ys[None, :]
    inside = (yy >= top) & (yy <= base + 1)
    f = np.clip((yy - top) / np.maximum(base - top, 1.0), 0, 1)
    def col(v):
        return np.array(v, np.float32)
    tc, mc, bc = col(top_col), col(mid_col), col(base_col)
    k1 = np.clip((f - 0.18) / 0.25, 0, 1)[..., None]
    k2 = np.clip((f - 0.62) / 0.3, 0, 1)[..., None]
    rock = tc * (1 - k1) + mc * k1
    rock = rock * (1 - k2) + bc * k2
    # 竖向的明暗：每块山石左亮右暗（光从左上来）
    shade = 0.9 + 0.12 * np.sin(xs[None, :] * 0.09 + noise1(W, seed + 9, 3)[None, :] * 3)
    rock = rock * shade[..., None]
    # 轮廓内侧一道深边
    rim = np.clip(1 - (yy - top) / 3.0, 0, 1)[..., None]
    rock = rock * (1 - rim * 0.7) + col(line) * rim * 0.7
    m = inside[..., None]
    a = np.where(m, rock, a)
    c.im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    c.d = ImageDraw.Draw(c.im)
    pts = [(float(xs[i]), float(ys[i])) for i in range(0, W, 2) if ok[i] and ys[i] < base - 1]
    if gold and len(pts) > 2:
        c.line([(x, y + 2.5) for (x, y) in pts], K['gold'], 1.0)
    # 皴笔：沿坡往下的短线（披麻皴），颜色比山色深
    for _ in range(int((x1 - x0) * 0.6)):
        i = rng.randrange(W)
        if not ok[i] or base - ys[i] < 25:
            continue
        x, y = float(xs[i]), float(ys[i]) + rng.uniform(6, (base - ys[i]) * 0.7)
        L = rng.uniform(7, 16)
        sl = rng.uniform(-0.5, 0.5)
        c.line([(x, y), (x + sl * L, y + L)], mix(mid_col, line, 0.45), 1.0)


def cloud_band(c, x, y, s, n=3, col=K['white'], edge=K['blue_lt']):
    """一团如意云（几个云头连在一起，下面拖一条云尾）"""
    for i in range(n):
        cloud_head(c, x + i * s * 1.25, y + (s * 0.25 if i % 2 else 0), s * 0.75, col, edge, (255, 255, 255), flip=(i % 2 == 1))
    tail = bez((x + (n - 1) * s * 1.25 + s * 0.4, y + s * 0.4), (x + n * s * 1.25 + s, y + s * 0.9), (x + n * s * 1.25 + s * 2.2, y - s * 0.2), (x + n * s * 1.25 + s * 3.0, y + s * 0.2), 30)
    c.line(tail, edge, 6)
    c.line(tail, col, 3.4)


def pine(c, x, y, h, seed):
    rng = random.Random(seed)
    trunk = bez((x, y), (x - h * 0.08, y - h * 0.35), (x + h * 0.12, y - h * 0.6), (x + h * 0.02, y - h))
    c.line(trunk, K['brown_dk'], h * 0.07)
    c.line(trunk, K['brown'], h * 0.045)
    for k in range(5):
        t = 0.35 + k * 0.15
        bx, by = trunk[int(t * (len(trunk) - 1))]
        sg = -1 if k % 2 else 1
        ex, ey = bx + sg * h * rng.uniform(0.25, 0.4), by - h * rng.uniform(0.02, 0.08)
        c.line([(bx, by), ((bx + ex) / 2, by - h * 0.05), (ex, ey)], K['brown_dk'], h * 0.025)
        # 一簇松针：扁圆，深绿，里面一道浅色
        c.ellipse(ex, ey - h * 0.03, h * 0.17, h * 0.07, fill=K['green_deep'])
        c.ellipse(ex, ey - h * 0.045, h * 0.14, h * 0.045, fill=K['green_dk'])
        for j in range(7):
            a = math.pi + j * math.pi / 6
            c.line([(ex, ey - h * 0.03), (ex + math.cos(a) * h * 0.15, ey - h * 0.03 + math.sin(a) * h * 0.06)], K['green'], 1.2)
    c.ellipse(trunk[-1][0], trunk[-1][1] - h * 0.02, h * 0.2, h * 0.08, fill=K['green_deep'])
    c.ellipse(trunk[-1][0], trunk[-1][1] - h * 0.035, h * 0.16, h * 0.05, fill=K['green_dk'])


def crane(c, x, y, s, flip=False):
    sg = -1 if flip else 1
    # 翅膀
    c.poly([(x, y), (x - sg * s * 0.9, y - s * 0.7), (x - sg * s * 1.3, y - s * 0.55), (x - sg * s * 0.4, y + s * 0.1)], fill=K['white'], outline=K['ink'], width=1.2)
    c.poly([(x - sg * s * 1.0, y - s * 0.66), (x - sg * s * 1.3, y - s * 0.55), (x - sg * s * 0.95, y - s * 0.5)], fill=K['ink'])
    c.poly([(x, y), (x + sg * s * 0.3, y - s * 0.75), (x + sg * s * 0.6, y - s * 0.62), (x + sg * s * 0.2, y + s * 0.08)], fill=(240, 240, 235), outline=K['ink'], width=1.2)
    # 身子、脖子、头
    c.ellipse(x, y + s * 0.05, s * 0.32, s * 0.14, fill=K['white'], outline=K['ink'], width=1.2)
    c.line([(x + sg * s * 0.25, y), (x + sg * s * 0.6, y - s * 0.2), (x + sg * s * 0.85, y - s * 0.22)], K['ink'], s * 0.06)
    c.circle(x + sg * s * 0.88, y - s * 0.23, s * 0.06, fill=K['ink'])
    c.circle(x + sg * s * 0.88, y - s * 0.27, s * 0.03, fill=K['red'])
    c.line([(x + sg * s * 0.92, y - s * 0.22), (x + sg * s * 1.08, y - s * 0.19)], K['ochre'], 1.6)
    c.line([(x - sg * s * 0.25, y + s * 0.1), (x - sg * s * 0.7, y + s * 0.2)], K['ink'], 1.4)


def pagoda(c, x, y, h):
    """几层的塔：每层一段墙、一道檐"""
    n = 7
    for k in range(n):
        t = k / n
        w = h * (0.22 - 0.12 * t)
        yy = y - h * 0.9 * t
        hh = h * 0.9 / n
        c.rect(x - w * 0.6, yy - hh * 0.8, x + w * 0.6, yy, fill=K['plaster'], outline=K['ink'], width=1.0)
        c.rect(x - w * 0.15, yy - hh * 0.6, x + w * 0.15, yy - hh * 0.15, fill=K['ink'])
        c.poly([(x - w * 1.05, yy - hh * 0.75), (x + w * 1.05, yy - hh * 0.75), (x + w * 0.7, yy - hh * 1.0), (x - w * 0.7, yy - hh * 1.0)], fill=K['green_dk'], outline=K['ink'], width=1.0)
    c.line([(x, y - h * 0.9), (x, y - h * 1.05)], K['gold_dk'], 3)
    c.circle(x, y - h * 1.06, h * 0.025, fill=K['gold'])


def bamboo(c, x, y, h, seed, col=K['green']):
    rng = random.Random(seed)
    lean = rng.uniform(-0.08, 0.08)
    segs = 6
    for k in range(segs):
        ya, yb = y - h * k / segs, y - h * (k + 1) / segs
        xa, xb = x + lean * h * k / segs, x + lean * h * (k + 1) / segs
        c.line([(xa, ya), (xb, yb + 3)], K['green_dk'], h * 0.05)
        c.line([(xa, ya), (xb, yb + 3)], col, h * 0.032)
        c.line([(xb - h * 0.03, yb), (xb + h * 0.03, yb)], K['green_deep'], 2.2)
    for _ in range(14):
        t = rng.uniform(0.35, 1.0)
        bx, by = x + lean * h * t, y - h * t
        a = rng.uniform(-0.6, 0.6) + (math.pi if rng.random() < 0.5 else 0)
        L = h * rng.uniform(0.09, 0.15)
        ex, ey = bx + math.cos(a) * L, by + math.sin(a) * L * 0.6 + L * 0.3
        nx, ny = -(ey - by), ex - bx
        nl = math.hypot(nx, ny) or 1
        nx, ny = nx / nl * L * 0.16, ny / nl * L * 0.16
        c.poly([(bx, by), ((bx + ex) / 2 + nx, (by + ey) / 2 + ny), (ex, ey), ((bx + ex) / 2 - nx, (by + ey) / 2 - ny)], fill=K['green_dk'], outline=K['green_deep'], width=1.0)


def lotus_side(c, x, y, s, open_=1.0, stem=2.2):
    """侧看的一朵莲花：花瓣一层层，粉色退晕"""
    if stem > 0:
        c.line([(x, y + s * 0.2), (x + s * 0.05, y + s * stem)], K['green_dk'], s * 0.08)
    for (a, L, col) in ((-0.95, 0.85, K['pink_dk']), (0.95, 0.85, K['pink_dk']), (-0.5, 1.0, K['pink']), (0.5, 1.0, K['pink']), (0.0, 1.05, K['pink_lt'])):
        a2 = a * open_
        tipx, tipy = x + math.sin(a2) * s * L, y - math.cos(a2) * s * L
        nx, ny = math.cos(a2) * s * 0.3, math.sin(a2) * s * 0.3
        pts = bez((x, y + s * 0.15), (x + nx, y + ny), (tipx + nx * 0.6, tipy + ny * 0.6 + s * 0.2), (tipx, tipy), 12) + \
            bez((tipx, tipy), (tipx - nx * 0.6, tipy - ny * 0.6 + s * 0.2), (x - nx, y - ny), (x, y + s * 0.15), 12)
        c.poly(pts, fill=col, outline=K['pink_dk'], width=1.2)
        c.line([(x + (tipx - x) * 0.25, y + (tipy - y) * 0.25 + s * 0.1), (x + (tipx - x) * 0.8, y + (tipy - y) * 0.8)], K['white'], 1.0)


def lotus_leaf(c, x, y, s, tilt=0.4):
    c.ellipse(x, y, s, s * tilt, fill=K['green_dk'], outline=K['green_deep'], width=1.4)
    c.ellipse(x, y - s * tilt * 0.08, s * 0.9, s * tilt * 0.82, fill=K['green'])
    for k in range(9):
        a = 2 * math.pi * k / 9
        c.line([(x, y), (x + math.cos(a) * s * 0.85, y + math.sin(a) * s * tilt * 0.8)], K['green_lt'], 1.3)


def bodhi(c, x, y, h, seed):
    """菩提树：粗干、大树冠由一片片心形叶子叠成"""
    rng = random.Random(seed)
    left = bez((x - h * 0.13, y), (x - h * 0.05, y - h * 0.05), (x - h * 0.07, y - h * 0.3), (x - h * 0.03, y - h * 0.48), 16)
    right = bez((x + h * 0.04, y - h * 0.48), (x + h * 0.02, y - h * 0.3), (x + h * 0.05, y - h * 0.05), (x + h * 0.14, y), 16)
    c.poly(left + right, fill=K['brown'], outline=K['brown_dk'], width=1.8)
    for k in range(4):
        c.line(bez((x - h * 0.03 + k * h * 0.02, y - h * 0.02), (x - h * 0.04 + k * h * 0.02, y - h * 0.15), (x - h * 0.01 + k * h * 0.015, y - h * 0.3), (x + k * h * 0.008, y - h * 0.45), 12), K['brown_dk'], 1.2)
    for (dx, dy) in ((-0.2, -0.62), (0.22, -0.6), (0.0, -0.7)):
        c.line([(x, y - h * 0.4), (x + dx * h, y + dy * h)], K['brown_dk'], h * 0.03)
    blobs = [(0, -0.72, 0.36), (-0.25, -0.62, 0.26), (0.26, -0.62, 0.26), (-0.1, -0.88, 0.22), (0.14, -0.86, 0.22)]
    for (dx, dy, r) in blobs:
        c.ellipse(x + dx * h, y + dy * h, r * h, r * h * 0.8, fill=K['green_deep'])
    for _ in range(170):
        (dx, dy, r) = rng.choice(blobs)
        a, rr = rng.uniform(0, 2 * math.pi), r * h * math.sqrt(rng.random()) * 0.92
        lx, ly = x + dx * h + math.cos(a) * rr, y + dy * h + math.sin(a) * rr * 0.8
        s = h * 0.04
        col = rng.choice([K['green'], K['green_dk'], K['green_lt'], K['green']])
        # 心形叶，叶尖朝下
        pts = bez((lx, ly + s * 1.3), (lx - s * 1.2, ly + s * 0.2), (lx - s * 0.8, ly - s * 0.9), (lx, ly - s * 0.3), 8) + \
            bez((lx, ly - s * 0.3), (lx + s * 0.8, ly - s * 0.9), (lx + s * 1.2, ly + s * 0.2), (lx, ly + s * 1.3), 8)
        c.poly(pts, fill=col, outline=K['green_deep'], width=0.8)


def rock(c, x, y, s, seed):
    rng = random.Random(seed)
    pts = []
    for k in range(9):
        a = math.pi + k * math.pi / 8
        r = s * rng.uniform(0.7, 1.0)
        pts.append((x + math.cos(a) * r * 1.2, y + math.sin(a) * r * 0.9))
    c.poly(pts, fill=K['blue_lt'], outline=K['ink'], width=1.6)
    for k in range(3):
        c.line([(x - s * 0.5 + k * s * 0.4, y - s * 0.5), (x - s * 0.3 + k * s * 0.4, y - s * 0.05)], K['blue_dk'], 1.4)


SKIN = (243, 210, 168)
SKIN_DK = (196, 140, 96)


def seated_buddha(c, x, y, s, robe=K['red'], robe_dk=K['red_dk']):
    """菩提树下成道的佛（佛传题材）：身光、头光、莲座、结跏趺坐、禅定印。y 是莲座底，s 是从莲座到头顶的高"""
    c.ellipse(x, y - s * 0.48, s * 0.44, s * 0.5, fill=K['blue_pale'], outline=K['gold'], width=2.4)
    for k in range(24):
        a = 2 * math.pi * k / 24
        c.line([(x + math.cos(a) * s * 0.18, y - s * 0.48 + math.sin(a) * s * 0.2), (x + math.cos(a) * s * 0.42, y - s * 0.48 + math.sin(a) * s * 0.47)], K['white'], 1.2)
    c.circle(x, y - s * 0.8, s * 0.2, fill=K['green_pale'], outline=K['gold'], width=2.2)
    c.circle(x, y - s * 0.8, s * 0.155, outline=K['gold_dk'], width=1.2)
    # 莲座：两层仰莲瓣
    for row, (yy, n, w_) in enumerate(((y - s * 0.03, 9, 0.46), (y - s * 0.09, 7, 0.4))):
        for k in range(n):
            px = x - s * w_ + (k + 0.5) * 2 * s * w_ / n
            pw = s * w_ / n * 1.15
            c.poly(bez((px - pw, yy), (px - pw, yy - s * 0.07), (px - pw * 0.2, yy - s * 0.11), (px, yy - s * 0.13), 8) +
                   bez((px, yy - s * 0.13), (px + pw * 0.2, yy - s * 0.11), (px + pw, yy - s * 0.07), (px + pw, yy), 8),
                   fill=K['pink'] if row == 0 else K['pink_lt'], outline=K['pink_dk'], width=1.2)
    # 盘腿、身子、袈裟
    c.ellipse(x, y - s * 0.17, s * 0.36, s * 0.1, fill=robe, outline=robe_dk, width=1.6)
    body = [(x - s * 0.17, y - s * 0.62), (x + s * 0.17, y - s * 0.62), (x + s * 0.27, y - s * 0.22), (x - s * 0.27, y - s * 0.22)]
    c.poly(body, fill=robe, outline=robe_dk, width=1.6)
    c.poly([(x - s * 0.1, y - s * 0.62), (x + s * 0.06, y - s * 0.62), (x + s * 0.02, y - s * 0.42)], fill=K['green'])
    c.line([(x + s * 0.17, y - s * 0.62), (x - s * 0.08, y - s * 0.24)], K['gold'], 2.2)
    for k in range(3):
        c.line(bez((x - s * 0.24 + k * s * 0.06, y - s * 0.24), (x - s * 0.2 + k * s * 0.06, y - s * 0.35), (x - s * 0.19 + k * s * 0.05, y - s * 0.45), (x - s * 0.15 + k * s * 0.04, y - s * 0.55), 10), robe_dk, 1.2)
    c.ellipse(x, y - s * 0.25, s * 0.1, s * 0.04, fill=K['yellow'], outline=SKIN_DK, width=1.0)
    # 头：金色的脸、螺髻、肉髻、长耳
    c.rect(x - s * 0.035, y - s * 0.68, x + s * 0.035, y - s * 0.61, fill=K['yellow'])
    for sg in (-1, 1):
        c.ellipse(x + sg * s * 0.085, y - s * 0.77, s * 0.022, s * 0.05, fill=K['yellow'], outline=SKIN_DK, width=0.8)
    c.ellipse(x, y - s * 0.78, s * 0.08, s * 0.1, fill=K['yellow'], outline=SKIN_DK, width=1.2)
    c.ellipse(x, y - s * 0.855, s * 0.082, s * 0.05, fill=K['blue_dk'])
    c.circle(x, y - s * 0.91, s * 0.04, fill=K['blue_dk'])
    for sg in (-1, 1):
        c.line([(x + sg * s * 0.015, y - s * 0.785), (x + sg * s * 0.055, y - s * 0.78)], K['ink'], 1.2)
    c.circle(x, y - s * 0.815, s * 0.008, fill=K['white'])
    c.circle(x, y - s * 0.735, s * 0.009, fill=K['red'])


def arhat(c, x, y, s, seed, robe=K['ochre'], band=K['red_dk']):
    """罗汉：坐在山石上，光头、白长眉，赭黄袈裟搭红格，右手持禅杖。y 是石头底，s 是人的高"""
    rng = random.Random(seed)
    rock(c, x, y - s * 0.02, s * 0.3, seed)
    c.circle(x - s * 0.02, y - s * 0.86, s * 0.16, outline=K['gold'], width=2.0)
    # 禅杖：长杆、顶上一个环、几个小环
    c.line([(x + s * 0.3, y + s * 0.02), (x + s * 0.24, y - s * 1.05)], K['brown_dk'], s * 0.025)
    c.circle(x + s * 0.24, y - s * 1.12, s * 0.07, outline=K['gold_dk'], width=2.4)
    for k in range(3):
        c.circle(x + s * 0.2 + k * s * 0.04, y - s * 1.06, s * 0.02, outline=K['gold'], width=1.4)
    # 一条腿盘、一条腿垂
    c.ellipse(x - s * 0.06, y - s * 0.3, s * 0.3, s * 0.09, fill=robe, outline=K['brown_dk'], width=1.4)
    c.poly([(x + s * 0.05, y - s * 0.32), (x + s * 0.22, y - s * 0.3), (x + s * 0.2, y - s * 0.05), (x + s * 0.1, y - s * 0.05)], fill=robe, outline=K['brown_dk'], width=1.4)
    c.ellipse(x + s * 0.17, y - s * 0.03, s * 0.06, s * 0.025, fill=SKIN, outline=SKIN_DK, width=1.0)
    body = [(x - s * 0.17, y - s * 0.68), (x + s * 0.13, y - s * 0.68), (x + s * 0.2, y - s * 0.32), (x - s * 0.27, y - s * 0.32)]
    c.poly(body, fill=robe, outline=K['brown_dk'], width=1.6)
    # 袈裟上的红格（田相）
    c.poly([(x - s * 0.17, y - s * 0.68), (x - s * 0.02, y - s * 0.68), (x + s * 0.2, y - s * 0.36), (x + s * 0.06, y - s * 0.32)], fill=band, outline=K['gold_dk'], width=1.0)
    for k in range(3):
        t = (k + 1) / 4
        c.line([(x - s * 0.17 + t * s * 0.23, y - s * 0.68 + t * s * 0.36), (x - s * 0.02 + t * s * 0.22, y - s * 0.68 + t * s * 0.32)], K['gold_dk'], 1.0)
    # 手：一只抚膝，一只握杖
    c.ellipse(x + s * 0.24, y - s * 0.55, s * 0.04, s * 0.035, fill=SKIN, outline=SKIN_DK, width=1.0)
    c.ellipse(x - s * 0.12, y - s * 0.36, s * 0.05, s * 0.03, fill=SKIN, outline=SKIN_DK, width=1.0)
    # 头：光头、白长眉、大耳
    c.rect(x - s * 0.04, y - s * 0.74, x + s * 0.03, y - s * 0.67, fill=SKIN)
    c.ellipse(x - s * 0.1, y - s * 0.84, s * 0.025, s * 0.045, fill=SKIN, outline=SKIN_DK, width=0.8)
    c.ellipse(x - s * 0.02, y - s * 0.85, s * 0.09, s * 0.11, fill=SKIN, outline=SKIN_DK, width=1.2)
    for sg in (-1, 1):
        c.line(bez((x - s * 0.02 + sg * s * 0.01, y - s * 0.88), (x - s * 0.02 + sg * s * 0.05, y - s * 0.9), (x - s * 0.02 + sg * s * 0.08, y - s * 0.86), (x - s * 0.02 + sg * s * 0.11, y - s * 0.8), 10), K['white'], 2.0)
        c.line([(x - s * 0.02 + sg * s * 0.015, y - s * 0.85), (x - s * 0.02 + sg * s * 0.05, y - s * 0.85)], K['ink'], 1.2)
    c.line([(x - s * 0.04, y - s * 0.79), (x, y - s * 0.79)], K['red_dk'], 1.2)


def apsara(c, x, y, s, flip=False, skirt=K['green'], ribbon=K['red']):
    """飞天：身子横着飞，裙子往后飘，长长的飘带绕成几道弧，手里托一盘花。s 是身长"""
    sg = -1 if flip else 1

    def P(u, v):
        return (x + sg * u * s, y + v * s)
    # 飘带：从肩上绕出来，往后拖两条长弧
    for (pts, col) in (([P(0.1, -0.05), P(-0.4, -0.45), P(-0.9, 0.1), P(-1.4, -0.3)], ribbon), ([P(0.05, 0.02), P(-0.3, 0.4), P(-0.8, -0.05), P(-1.25, 0.32)], K['blue_lt'])):
        b = bez(*pts, n=36)
        c.line(b, K['ink'], s * 0.05)
        c.line(b, col, s * 0.035)
        c.line(b, K['white'], 1.0)
    # 裙：从腰往后飘成一个长尖
    sk = bez(P(-0.05, -0.04), P(-0.3, -0.12), P(-0.55, -0.05), P(-0.85, 0.02), 16) + bez(P(-0.85, 0.02), P(-0.55, 0.14), P(-0.3, 0.16), P(-0.05, 0.08), 16)
    c.poly(sk, fill=skirt, outline=K['green_deep'], width=1.4)
    for k in range(3):
        c.line(bez(P(-0.1, -0.02 + k * 0.04), P(-0.35, -0.06 + k * 0.05), P(-0.55, 0.0 + k * 0.03), P(-0.78, 0.02 + k * 0.01), 12), K['green_lt'], 1.2)
    c.ellipse(*P(-0.86, 0.03), s * 0.04, s * 0.02, fill=SKIN, outline=SKIN_DK, width=0.8)
    # 上身、手臂、托盘
    c.poly([P(-0.06, -0.06), P(0.22, -0.13), P(0.27, -0.04), P(0.0, 0.08)], fill=SKIN, outline=SKIN_DK, width=1.2)
    c.line([P(0.06, -0.04), P(0.2, -0.1)], K['gold'], 1.6)
    c.line([P(0.2, -0.1), P(0.34, -0.22), P(0.44, -0.24)], SKIN_DK, s * 0.04)
    c.line([P(0.2, -0.1), P(0.34, -0.22), P(0.44, -0.24)], SKIN, s * 0.028)
    c.ellipse(*P(0.46, -0.27), s * 0.08, s * 0.022, fill=K['gold'], outline=K['gold_dk'], width=1.0)
    for k in range(3):
        c.circle(*P(0.42 + k * 0.04, -0.31), s * 0.025, fill=K['pink'], outline=K['pink_dk'], width=0.8)
    # 头：头光、发髻
    c.circle(*P(0.3, -0.2), s * 0.11, outline=K['gold'], width=1.8)
    c.circle(*P(0.3, -0.19), s * 0.065, fill=SKIN, outline=SKIN_DK, width=1.0)
    c.circle(*P(0.33, -0.27), s * 0.04, fill=K['ink'])
    c.ellipse(*P(0.28, -0.24), s * 0.06, s * 0.03, fill=K['ink'])
    c.circle(*P(0.34, -0.17), s * 0.006, fill=K['red'])


def falling_flowers(c, x0, y0, x1, y1, n, seed):
    """散花：几十片小花瓣（飞天撒的）"""
    rng = random.Random(seed)
    for _ in range(n):
        px, py = rng.uniform(x0, x1), rng.uniform(y0, y1)
        r = rng.uniform(3, 6)
        a = rng.uniform(0, math.pi)
        col = rng.choice([K['pink'], K['pink_lt'], K['white'], K['yellow']])
        c.poly([(px + math.cos(a) * r * 1.8, py + math.sin(a) * r * 1.8), (px - math.sin(a) * r, py + math.cos(a) * r),
                (px - math.cos(a) * r * 1.8, py - math.sin(a) * r * 1.8), (px + math.sin(a) * r, py - math.cos(a) * r)], fill=col, outline=K['pink_dk'], width=0.8)


def monk_walk(c, x, y, s, seed, robe=K['ochre']):
    """朝山的小和尚（侧面，走路）：s 是身高"""
    c.poly([(x - s * 0.12, y), (x + s * 0.1, y), (x + s * 0.08, y - s * 0.7), (x - s * 0.08, y - s * 0.7)], fill=robe, outline=K['brown_dk'], width=1.2)
    c.poly([(x - s * 0.08, y - s * 0.68), (x + s * 0.06, y - s * 0.7), (x + s * 0.1, y - s * 0.35), (x - s * 0.02, y - s * 0.3)], fill=K['red_dk'])
    c.circle(x + s * 0.01, y - s * 0.8, s * 0.09, fill=SKIN, outline=SKIN_DK, width=1.0)
    c.line([(x + s * 0.12, y - s * 0.55), (x + s * 0.2, y + s * 0.02)], K['brown_dk'], 2.0)


def mural(w, h, kind, seed):
    """一幅壁画：米色的墙底，上面青绿山水的题材，外面一道赭石框"""
    c = Canvas(w, h, K['plaster'])
    rng = random.Random(seed)
    sky = K['plaster']
    if kind == 0:        # 青绿山水：远山、近山、云、松
        mountain(c, 0, w, h * 0.55, [(w * 0.3, h * 0.32, w * 0.16), (w * 0.62, h * 0.4, w * 0.14), (w * 0.9, h * 0.25, w * 0.12)], seed, K['blue_lt'], K['green_lt'], K['plaster_dk'], line=K['blue_dk'], gold=False)
        cloud_band(c, w * 0.08, h * 0.5, w * 0.06, 3)
        mountain(c, -20, w + 20, h * 0.86, [(w * 0.15, h * 0.42, w * 0.13), (w * 0.45, h * 0.28, w * 0.18), (w * 0.82, h * 0.48, w * 0.12)], seed + 1, K['blue'], K['green'], K['ochre'])
        cloud_band(c, w * 0.45, h * 0.62, w * 0.07, 2)
        pine(c, w * 0.22, h * 0.97, h * 0.42, seed)
    elif kind == 1:      # 莲池：水面、荷叶、荷花，远处淡山
        mountain(c, 0, w, h * 0.42, [(w * 0.25, h * 0.15, w * 0.15), (w * 0.7, h * 0.2, w * 0.2)], seed, K['blue_pale'], K['green_pale'], K['plaster'], line=K['blue_lt'], gold=False)
        cloud_band(c, w * 0.5, h * 0.16, w * 0.055, 3)
        c.rect(0, h * 0.42, w, h, fill=(196, 219, 214))
        for k in range(16):
            yy = h * 0.45 + k * h * 0.035
            pts = [(x, yy + 3 * math.sin(x * 0.05 + k)) for x in np.linspace(0, w, 60)]
            c.line(pts, (160, 196, 196), 1.4)
        for (x, y, s) in ((0.2, 0.62, 0.13), (0.7, 0.58, 0.11), (0.45, 0.8, 0.16), (0.88, 0.85, 0.12), (0.08, 0.9, 0.12)):
            lotus_leaf(c, w * x, h * y, w * s)
        for (x, y, s) in ((0.3, 0.5, 0.07), (0.6, 0.66, 0.08), (0.82, 0.5, 0.06), (0.15, 0.72, 0.05), (0.92, 0.7, 0.05), (0.52, 0.48, 0.045)):
            lotus_side(c, w * x, h * y, w * s)
        # 池上一身小飞天
        apsara(c, w * 0.62, h * 0.3, w * 0.28, flip=True, skirt=K['blue_lt'])
        falling_flowers(c, w * 0.3, h * 0.3, w * 0.95, h * 0.6, 22, seed)
    elif kind == 2:      # 菩提树、远山、一座小塔
        mountain(c, 0, w, h * 0.62, [(w * 0.75, h * 0.3, w * 0.18), (w * 0.95, h * 0.2, w * 0.12)], seed, K['blue_lt'], K['green_lt'], K['plaster_dk'], line=K['blue_dk'])
        pagoda(c, w * 0.78, h * 0.5, h * 0.2)
        cloud_band(c, w * 0.55, h * 0.18, w * 0.055, 3)
        c.rect(0, h * 0.8, w, h, fill=K['green_pale'])
        bodhi(c, w * 0.42, h * 0.9, h * 0.8, seed)
        # 菩提树下成道：佛结跏趺坐在树下，两边各一个合掌的比丘
        seated_buddha(c, w * 0.42, h * 0.93, h * 0.36)
        for (xx, fl) in ((0.12, False), (0.76, True)):
            monk_walk(c, w * xx, h * 0.94, h * 0.16, seed, robe=K['ochre'] if fl else K['brown'])
        for k in range(4):
            rock(c, w * (0.66 + 0.08 * k), h * (0.93 + 0.01 * (k % 2)), w * 0.035, seed + k)
        falling_flowers(c, w * 0.05, h * 0.12, w * 0.95, h * 0.55, 26, seed)
    elif kind == 3:      # 飞天散花：两身飞天在云里飞，花瓣往下落，下面青绿山、两只鹤
        mountain(c, 0, w, h * 0.72, [(w * 0.75, h * 0.42, w * 0.15), (w * 0.95, h * 0.5, w * 0.12)], seed + 3, K['blue_pale'], K['green_pale'], K['plaster'], line=K['blue_lt'], gold=False)
        mountain(c, -10, w + 10, h * 0.95, [(w * 0.18, h * 0.55, w * 0.16), (w * 0.55, h * 0.66, w * 0.14), (w * 0.88, h * 0.62, w * 0.12)], seed, K['blue'], K['green'], K['ochre'])
        c.circle(w * 0.82, h * 0.1, w * 0.06, fill=K['red_lt'])
        cloud_band(c, w * 0.02, h * 0.2, w * 0.05, 3)
        cloud_band(c, w * 0.5, h * 0.42, w * 0.05, 3)
        cloud_band(c, w * 0.1, h * 0.58, w * 0.04, 2)
        apsara(c, w * 0.62, h * 0.22, w * 0.42)
        apsara(c, w * 0.36, h * 0.44, w * 0.36, flip=True, skirt=K['blue_lt'], ribbon=K['vermil'])
        falling_flowers(c, w * 0.1, h * 0.25, w * 0.9, h * 0.7, 40, seed)
        crane(c, w * 0.22, h * 0.7, w * 0.07)
        crane(c, w * 0.7, h * 0.62, w * 0.06, flip=True)
    elif kind == 4:      # 山顶宝塔、瀑布
        mountain(c, -10, w + 10, h * 0.95, [(w * 0.5, h * 0.62, w * 0.2), (w * 0.12, h * 0.35, w * 0.12), (w * 0.9, h * 0.4, w * 0.12)], seed, K['blue'], K['green'], K['ochre'])
        pagoda(c, w * 0.5, h * 0.36, h * 0.24)
        fx_ = w * 0.4
        fall = bez((fx_, h * 0.6), (fx_ + w * 0.01, h * 0.7), (fx_ - w * 0.01, h * 0.8), (fx_, h * 0.93))
        c.line(fall, K['blue_pale'], 12)
        c.line(fall, K['white'], 6)
        for k in range(3):
            c.line([(fx_ + k * 2 - 2, h * 0.62), (fx_ + k * 2 - 2, h * 0.9)], K['blue_lt'], 0.8)
        c.ellipse(fx_, h * 0.935, w * 0.06, h * 0.012, fill=K['white'])
        cloud_band(c, w * 0.05, h * 0.18, w * 0.055, 3)
        cloud_band(c, w * 0.55, h * 0.55, w * 0.06, 3)
        # 山路上朝山的几个和尚
        path = bez((w * 0.05, h * 0.97), (w * 0.3, h * 0.9), (w * 0.2, h * 0.8), (w * 0.42, h * 0.72), 20)
        c.line(path, K['plaster_dk'], 7)
        for k, t in enumerate((0.15, 0.45, 0.75)):
            px, py = path[int(t * (len(path) - 1))]
            monk_walk(c, px, py, h * 0.07, seed + k, robe=K['ochre'] if k % 2 else K['brown'])
        crane(c, w * 0.75, h * 0.28, w * 0.06, flip=True)
    else:                # 罗汉：松下、竹边，一位罗汉坐在山石上，旁边一个小沙弥捧经
        mountain(c, 0, w, h * 0.5, [(w * 0.4, h * 0.2, w * 0.2), (w * 0.85, h * 0.3, w * 0.14)], seed, K['blue_pale'], K['green_pale'], K['plaster'], line=K['blue_lt'], gold=False)
        cloud_band(c, w * 0.1, h * 0.16, w * 0.055, 3)
        c.rect(0, h * 0.86, w, h, fill=K['green_pale'])
        for k, (x, hh) in enumerate(((0.72, 0.7), (0.8, 0.58), (0.9, 0.76))):
            bamboo(c, w * x, h * 0.92, h * hh, seed + k)
        pine(c, w * 0.2, h * 0.95, h * 0.62, seed + 9)
        arhat(c, w * 0.48, h * 0.9, h * 0.42, seed)
        monk_walk(c, w * 0.8, h * 0.95, h * 0.17, seed + 2, robe=K['brown'])
        rock(c, w * 0.12, h * 0.94, w * 0.08, seed + 5)
        for k in range(4):
            lotus_side(c, w * (0.08 + 0.06 * k), h * 0.9, w * 0.025, 0.8, stem=1.2)
    # 框：一道赭石宽边、里面一道墨线一道金线
    b = w * 0.035
    c.rect(0, 0, w, b, fill=K['red_dk'])
    c.rect(0, h - b, w, h, fill=K['red_dk'])
    c.rect(0, 0, b, h, fill=K['red_dk'])
    c.rect(w - b, 0, w, h, fill=K['red_dk'])
    c.rect(b, b, w - b, h - b, outline=K['gold'], width=2.4)
    c.rect(b + 4, b + 4, w - b - 4, h - b - 4, outline=K['ink'], width=1.2)
    return c


def dado(w, h, kind):
    """墙裙：深朱红底，金线框，中间一个如意头的长方框（框里画莲或云），上下两道卷草"""
    c = Canvas(w, h, K['red_dk'])
    c.rect(0, 0, w, h * 0.12, fill=K['red_deep'])
    c.rect(0, h * 0.9, w, h, fill=K['red_deep'])
    c.line([(0, h * 0.12), (w, h * 0.12)], K['gold'], 2.6)
    c.line([(0, h * 0.9), (w, h * 0.9)], K['gold'], 2.6)
    # 上沿一道回纹（一笔连下去的方形回旋）
    u = h * 0.022
    y0f = h * 0.06 - u * 1.5
    pts = []
    x = 0.0
    while x < w:
        for (ax, ay) in ((0, 3), (0, 0), (3, 0), (3, 2), (1, 2), (1, 1), (2, 1)):
            pass
        unit = [(0, 3), (0, 0), (3, 0), (3, 2), (1.5, 2), (1.5, 1), (2, 1)]
        seg = [(x + ax * u, y0f + ay * u) for (ax, ay) in unit]
        c.line(seg, K['gold'], 1.6)
        c.line([(x, y0f + 3 * u), (x + 4 * u, y0f + 3 * u)], K['gold'], 1.6)
        x += 4 * u
    # 中间的框：海棠形（四角内凹）
    x0, x1, y0, y1 = w * 0.08, w * 0.92, h * 0.22, h * 0.8
    r = h * 0.08
    pts = []
    for (cx, cy, a0) in ((x1, y0, math.pi / 2), (x1, y1, math.pi), (x0, y1, 1.5 * math.pi), (x0, y0, 0)):
        pts += arc(cx, cy, r, a0 + math.pi / 2, a0, 10)
    c.poly(pts, fill=K['red'], outline=K['gold'], width=3.0)
    inner = [(x + (6 if x < w / 2 else -6), y + (6 if y < h / 2 else -6)) for (x, y) in pts]
    c.poly(inner, outline=K['gold_dk'], width=1.4)
    cy = (y0 + y1) / 2
    if kind == 0:
        # 缠枝莲：一条波浪形的金藤，三朵莲花
        pts = [(x, cy + h * 0.1 * math.sin((x - x0) / (x1 - x0) * 4 * math.pi)) for x in np.linspace(x0 + r * 1.5, x1 - r * 1.5, 120)]
        c.line(pts, K['gold_dk'], 4.4)
        c.line(pts, K['gold'], 2.6)
        for k in range(3):
            x = x0 + (x1 - x0) * (k + 0.5) / 3
            lotus_side(c, x, cy + h * 0.02, h * 0.12, stem=0.9)
        for k in range(4):
            x = x0 + (x1 - x0) * (k + 1) / 4 - (x1 - x0) / 8
            y = cy + h * 0.1 * math.sin((x - x0) / (x1 - x0) * 4 * math.pi)
            sp = spiral(x, y - h * 0.07, 1, h * 0.06, 0, 1.2, 30)
            c.line(sp, K['gold'], 2.2)
    else:
        for k in range(4):
            x = x0 + (x1 - x0) * (k + 0.5) / 4
            cloud_head(c, x, cy + (h * 0.04 if k % 2 else -h * 0.04), h * 0.1, K['gold'], K['gold_dk'], K['gold_lt'], flip=k % 2 == 1)
    return c


# ───────────────────────── 拼图集 ─────────────────────────
def atlas(kind):
    W, H = SIZES[kind]
    big = Image.new('RGB', (W, H), (0, 0, 0))

    def put(c, key):
        x0, y0, x1, y1 = RECTS[kind][key]
        im = c.final() if hasattr(c, 'final') else c
        assert im.size == (x1 - x0, y1 - y0), (key, im.size)
        big.paste(im, (x0, y0))
    if kind == 'beam':
        put(xuanzi(2048, 256, 'a'), 'xuanzi_a')
        put(xuanzi(2048, 256, 'b'), 'xuanzi_b')
        put(band_pearl(2048, 128), 'pearl')
        put(band_scroll(2048, 128), 'scroll')
        put(band_cloud(2048, 256), 'cloud')
        put(band_cloud_b(2048, 256), 'cloud_b')
        put(gongyan(512, 256, 'a'), 'gongyan_a')
        put(gongyan(512, 256, 'b'), 'gongyan_b')
        put(tuomu_end(256, 256), 'tuomu')
        put(tuomu_side(512, 256), 'tuomu_side')
        put(col_band(256, 128, 'a'), 'colband')
        put(col_band(256, 128, 'b'), 'colband_b')
    elif kind == 'ceiling':
        put(zaojing_disc(1024), 'zaojing')
        for key, k in (('panel_lotus', 'lotus'), ('panel_wheel', 'wheel'), ('panel_lotus_b', 'lotus_b'), ('panel_cloud', 'cloud')):
            c = Canvas(512, 512)
            ceiling_panel(c, 0, 0, 512, k)
            put(c, key)
    elif kind == 'wall':
        import painted_murals
        for i in range(12):
            put(painted_murals.mural2(682, 800, i), f'mural_{i}')
        put(dado(1024, 448, 0), 'dado_a')
        put(dado(1024, 448, 1), 'dado_b')
    return grain(big, 4.0, seed=len(kind))


def main(argv):
    out = OUT_DEFAULT
    names = []
    for a in argv:
        if os.path.isdir(a) or '/' in a:
            out = a
        else:
            names.append(a)
    names = names or list(SIZES)
    os.makedirs(out, exist_ok=True)
    tiles = []
    for n in names:
        im = atlas(n)
        p = os.path.join(out, f'paint_{n}.png')
        im.save(p, optimize=True)
        print('手绘贴图', n, im.size, p)
        tiles.append(im)
    # 拼一张给人看
    hh = 700
    ims = [t.resize((int(t.width * hh / t.height), hh), Image.LANCZOS) for t in tiles]
    sheet = Image.new('RGB', (sum(i.width for i in ims) + 10 * (len(ims) - 1), hh), (40, 40, 40))
    x = 0
    for i in ims:
        sheet.paste(i, (x, 0))
        x += i.width + 10
    sheet.save(os.path.join(out, '_hall_paint_sheet.png'))


if __name__ == '__main__':
    main(sys.argv[1:])
