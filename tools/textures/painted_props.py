"""大殿陈设用的手绘贴图：桌围的刺绣、拜垫和坐垫的织锦、幡、经书、佛坛上枋的彩画、宫灯的灯片。

全是用代码「画」出来的（PIL + numpy，不用照片素材）：
  - 刺绣：一块块色面里有细密的平行针脚（明暗相间的细线），颜色分三四档「退晕」（由浅到深一档一档），外面盘一圈金线；
  - 织锦：底色上织着同色暗纹，再织彩色的团花；
  - 字：思源宋体粗体，金线描边。
每张图都先按 2 倍大小画，再缩小（边缘不起锯齿）。

用法：python3 tools/textures/painted_props.py [输出目录] [名字 ...]
  不给输出目录就写到 unity/Sanctuary/Assets/Toon/Textures；名字是 frontal brocade banner sutra dais lantern enamel，不给就全画。
输出 paint_<名字>.png；另外拼一张 _paint_sheet.png 给人看（同一个目录）。
游戏里：模型上叫 paint_<名字> 的部件用这张图（材质 toon_paint_<名字>，贴图坐标是模型里的 uv）。
paint_lantern 也进 Unity（宫灯的灯片），它的材质夜里要发光（见 hall_props 的交接说明）。
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
OUT_DEFAULT = os.path.join(ROOT, 'unity', 'Sanctuary', 'Assets', 'Toon', 'Textures')
FONT = os.path.join(ROOT, 'assets', 'fonts', 'SourceHanSerifCN-Bold.otf')
SS = 2


def hexc(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


# 配色：明黄、朱红、石青、石绿、金
K = {k: hexc(v) for k, v in {
    'yellow': '#e8b83a', 'yellow_lt': '#f6d873', 'yellow_dk': '#c08a22', 'yellow_deep': '#9a6a1a',
    'red': '#b5281f', 'red_lt': '#d6493a', 'red_dk': '#861a17', 'red_deep': '#5e1210',
    'gold': '#e9c15a', 'gold_lt': '#fae7a0', 'gold_dk': '#a87a26', 'ink': '#2a1a14',
    'blue': '#2a4f86', 'blue_lt': '#5b86bf', 'blue_pale': '#a9c6e6', 'blue_dk': '#173361', 'blue_deep': '#0f2246',
    'green': '#2f7d63', 'green_lt': '#64ad86', 'green_pale': '#a9d7b5', 'green_dk': '#1d5644',
    'pink': '#e88aa0', 'pink_lt': '#f8c9d3', 'pink_pale': '#fde9ee', 'pink_dk': '#c4536f',
    'white': '#fbf5e6', 'paper': '#efe3c4', 'paper_dk': '#d9c79d', 'black': '#1d1a19',
    'purple': '#6d4a8e', 'purple_lt': '#a685c4', 'orange': '#e07a2e',
}.items()}


def mixc(a, b, t):
    return a + (b - a) * t


class Pad:
    """一张画布。坐标都按最终像素写，里面按 SS 倍画"""

    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.W, self.H = w * SS, h * SS
        self.a = np.empty((self.H, self.W, 3), np.float32)
        self.a[:] = bg
        self.clip = None        # (x0, y0, x1, y1)：只画在这个框里（一张图上拼几块时，别画出界）

    # ---- 形状 → 局部遮罩 ----
    def _local(self, box, draw_fn):
        x0, y0, x1, y1 = box
        X0, Y0 = max(0, int(math.floor(x0 * SS)) - 2), max(0, int(math.floor(y0 * SS)) - 2)
        X1, Y1 = min(self.W, int(math.ceil(x1 * SS)) + 2), min(self.H, int(math.ceil(y1 * SS)) + 2)
        if X1 <= X0 or Y1 <= Y0:
            return None
        im = Image.new('L', (X1 - X0, Y1 - Y0), 0)
        d = ImageDraw.Draw(im)

        def T(p):
            return (p[0] * SS - X0, p[1] * SS - Y0)
        draw_fn(d, T)
        return (X0, Y0, np.asarray(im, np.float32) / 255.0)

    def poly_mask(self, pts):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return self._local((min(xs), min(ys), max(xs), max(ys)), lambda d, T: d.polygon([T(p) for p in pts], fill=255))

    def ellipse_mask(self, cx, cy, rx, ry):
        return self._local((cx - rx, cy - ry, cx + rx, cy + ry),
                           lambda d, T: d.ellipse([T((cx - rx, cy - ry)), T((cx + rx, cy + ry))], fill=255))

    def line_mask(self, pts, w):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        r = w / 2 + 1

        def fn(d, T):
            d.line([T(p) for p in pts], fill=255, width=max(1, int(round(w * SS))), joint='curve')
            for p in (pts[0], pts[-1]):
                q = T(p)
                d.ellipse([q[0] - w * SS / 2, q[1] - w * SS / 2, q[0] + w * SS / 2, q[1] + w * SS / 2], fill=255)
        return self._local((min(xs) - r, min(ys) - r, max(xs) + r, max(ys) + r), fn)

    def taper_mask(self, pts, w0, w1):
        """一笔由粗到细（云纹的卷、叶脉）"""
        n = len(pts)
        left, right = [], []
        for i in range(n):
            p = pts[i]
            q0, q1 = pts[max(0, i - 1)], pts[min(n - 1, i + 1)]
            dx, dy = q1[0] - q0[0], q1[1] - q0[1]
            L = math.hypot(dx, dy) or 1
            nx, ny = -dy / L, dx / L
            w = (w0 + (w1 - w0) * i / max(1, n - 1)) / 2
            left.append((p[0] + nx * w, p[1] + ny * w))
            right.append((p[0] - nx * w, p[1] - ny * w))
        return self.poly_mask(left + right[::-1])

    def text_mask(self, s, cx, cy, size, font=FONT, stroke=0):
        f = ImageFont.truetype(font, int(size * SS))
        bb = f.getbbox(s, stroke_width=int(stroke * SS))
        tw, th = (bb[2] - bb[0]) / SS, (bb[3] - bb[1]) / SS
        x0, y0 = cx - tw / 2, cy - th / 2

        def fn(d, T):
            q = T((x0, y0))
            d.text((q[0] - bb[0], q[1] - bb[1]), s, font=f, fill=255, stroke_width=int(stroke * SS), stroke_fill=255)
        return self._local((x0 - 2, y0 - 2, x0 + tw + 2, y0 + th + 2), fn)

    # ---- 遮罩运算 ----
    @staticmethod
    def grow(m, px):
        """遮罩往外扩 px 个像素（描边用）"""
        if m is None:
            return None
        X0, Y0, a = m
        k = int(round(px * SS))
        if k <= 0:
            return m
        pad = k + 1
        im = Image.fromarray((a * 255).astype(np.uint8))
        big = Image.new('L', (im.width + 2 * pad, im.height + 2 * pad), 0)
        big.paste(im, (pad, pad))
        size = 2 * k + 1
        # MaxFilter 大核很慢：分几次小核
        while size > 1:
            s = min(size, 9)
            if s % 2 == 0:
                s -= 1
            big = big.filter(ImageFilter.MaxFilter(s))
            size -= (s - 1)
        return (X0 - pad, Y0 - pad, np.asarray(big, np.float32) / 255.0)

    @staticmethod
    def union(*ms):
        ms = [m for m in ms if m is not None]
        X0 = min(m[0] for m in ms)
        Y0 = min(m[1] for m in ms)
        X1 = max(m[0] + m[2].shape[1] for m in ms)
        Y1 = max(m[1] + m[2].shape[0] for m in ms)
        out = np.zeros((Y1 - Y0, X1 - X0), np.float32)
        for (x, y, a) in ms:
            sub = out[y - Y0:y - Y0 + a.shape[0], x - X0:x - X0 + a.shape[1]]
            np.maximum(sub, a, out=sub)
        return (X0, Y0, out)

    # ---- 上色 ----
    def put(self, m, color, alpha=1.0, mod=None):
        """把遮罩里涂上颜色。color：一个颜色，或 fn(x, y) → (h, w, 3)（x, y 是最终像素坐标的网格）。
        mod：fn(x, y) → (h, w)，乘在颜色上（针脚、织纹的明暗）"""
        if m is None:
            return
        X0, Y0, a = m
        # 裁到画布里（再裁到 clip 框里）
        cx0, cy0, cx1, cy1 = (0, 0, self.W, self.H) if self.clip is None else [int(round(v * SS)) for v in self.clip]
        x0, y0 = max(cx0, X0), max(cy0, Y0)
        x1, y1 = min(cx1, X0 + a.shape[1]), min(cy1, Y0 + a.shape[0])
        if x1 <= x0 or y1 <= y0:
            return
        a = a[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0] * alpha
        if a.max() <= 0:
            return
        need = callable(color) or mod is not None
        if need:
            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            xx = (xx + 0.5) / SS
            yy = (yy + 0.5) / SS
        c = color(xx, yy) if callable(color) else np.broadcast_to(np.asarray(color, np.float32), a.shape + (3,))
        if mod is not None:
            c = c * mod(xx, yy)[..., None]
        sub = self.a[y0:y1, x0:x1]
        sub += (c - sub) * a[..., None]

    def save(self, path):
        im = Image.fromarray((np.clip(self.a, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGB')
        im = im.resize((self.w, self.h), Image.LANCZOS)
        im.save(path, optimize=True)
        return im


# ── 针脚、织纹 ──

def stitch_lines(angle, period=1.6, depth=0.16):
    """平针：一个方向上细密的平行线（亮暗相间）"""
    ca, sa = math.cos(angle), math.sin(angle)

    def f(x, y):
        u = (x * ca + y * sa) / period
        return 1.0 + depth * (np.abs((u % 1.0) - 0.5) * 2 - 0.5) * 2 * 0.5
    return f


def stitch_radial(cx, cy, period=1.5, depth=0.16):
    """针脚绕着一个点一圈一圈（花瓣：针脚横着走、从瓣根往瓣尖排）"""
    def f(x, y):
        r = np.hypot(x - cx, y - cy) / period
        return 1.0 + depth * (np.abs((r % 1.0) - 0.5) * 2 - 0.5)
    return f


def stitch_fan(cx, cy, n=180, depth=0.16):
    """针脚从一个点放射出去（叶子、金线盘绕的「打籽」底）"""
    def f(x, y):
        a = np.arctan2(y - cy, x - cx) / (2 * math.pi) * n
        return 1.0 + depth * (np.abs((a % 1.0) - 0.5) * 2 - 0.5)
    return f


def weave(period=2.0, depth=0.06, seed=0):
    """绸缎的织纹：经纬线的细格子 + 一点不匀"""
    rng = np.random.default_rng(seed)
    ph = rng.uniform(0, 6.28, 4)

    def f(x, y):
        g = np.sin(x * (2 * math.pi / period)) * np.sin(y * (2 * math.pi / period) + ph[0])
        slub = np.sin(y * 0.37 + ph[1] + np.sin(x * 0.011 + ph[2]) * 3) * 0.5 + np.sin(y * 1.31 + ph[3]) * 0.5
        return 1.0 + depth * (0.6 * g + 0.4 * slub)
    return f


def gold_mod(seed=0, period=1.4):
    """盘金：金线一根根平行盘过去，亮暗交替，带一点闪"""
    s = stitch_lines(0.7 + seed, period, 0.32)

    def f(x, y):
        return s(x, y) * (1.0 + 0.08 * np.sin(x * 0.21 + y * 0.17 + seed))
    return f


def banded(c_lo, c_hi, axis_fn, steps=4):
    """退晕：颜色从 c_lo 到 c_hi 分几档（像彩画、刺绣里一档一档的晕色）"""
    def f(x, y):
        t = np.clip(axis_fn(x, y), 0, 1)
        q = np.floor(t * steps) / max(1, steps - 1)
        q = np.clip(q, 0, 1)[..., None]
        return c_lo + (c_hi - c_lo) * q
    return f


def smooth_grad(c_lo, c_hi, axis_fn):
    def f(x, y):
        t = np.clip(axis_fn(x, y), 0, 1)[..., None]
        return c_lo + (c_hi - c_lo) * t
    return f


# ── 纹样 ──

def petal_pts(base, ang, L, W, n=32, tip=0.0, base_w=0.32):
    """一片莲瓣（正视）：瓣根在 base，朝 ang 方向（0 = 朝上，顺时针为正），长 L、最宽 W。
    瓣根收窄、中段饱满、瓣尖收成一个短尖；tip 让瓣尖往一边勾"""
    dx, dy = math.sin(ang), -math.cos(ang)
    px, py = math.cos(ang), math.sin(ang)
    left, right = [], []
    for i in range(n + 1):
        t = i / n
        body = math.sin(math.pi * min(1.0, t * 0.9 + 0.1)) ** 0.5
        w = W / 2 * (base_w + (1 - base_w) * body) * (1 - 0.12 * t)
        if t > 0.74:
            w *= ((1 - t) / 0.26) ** 0.7
        c = t * L
        bend = tip * L * t ** 3
        cxp, cyp = base[0] + dx * c + px * bend, base[1] + dy * c + py * bend
        left.append((cxp - px * w, cyp - py * w))
        right.append((cxp + px * w, cyp + py * w))
    return left + right[::-1]


def draw_petal(pad, base, ang, L, W, c_base, c_tip, outline=None, ow=1.2, steps=5, tip=0.0, vein=None):
    """画一片绣出来的花瓣：瓣根一种颜色、瓣尖一种颜色，中间一档一档晕开（中线那边浅、两边深），针脚横着走，外盘金线"""
    pts = petal_pts(base, ang, L, W, tip=tip)
    m = pad.poly_mask(pts)
    if outline is not None:
        pad.put(Pad.grow(m, ow), outline, mod=gold_mod(ang))
    dx, dy = math.sin(ang), -math.cos(ang)
    px, py = math.cos(ang), math.sin(ang)

    def axis(x, y):
        along = ((x - base[0]) * dx + (y - base[1]) * dy) / L
        lat = np.abs((x - base[0]) * px + (y - base[1]) * py) / (W / 2)
        return 0.72 * along + 0.38 * lat * lat
    pad.put(m, banded(c_base, c_tip, axis, steps), mod=stitch_radial(base[0], base[1], 1.3, 0.18))
    if vein is not None:
        # 瓣中一道筋，两边各一道细筋
        pts2 = [(base[0] + dx * L * t, base[1] + dy * L * t) for t in (0.08, 0.45, 0.82)]
        pad.put(pad.taper_mask(pts2, max(0.8, W * 0.05), 0.3), vein, alpha=0.55)
        for sg in (-1, 1):
            pts3 = [(base[0] + dx * L * t + px * sg * W * 0.22 * math.sin(math.pi * t * 0.9), base[1] + dy * L * t + py * sg * W * 0.22 * math.sin(math.pi * t * 0.9))
                    for t in (0.15, 0.4, 0.65)]
            pad.put(pad.taper_mask(pts3, max(0.6, W * 0.03), 0.2), vein, alpha=0.35)
    return m


def lotus_front(pad, cx, cy, s, pal=None, outline=None, leaves=True, stem=True):
    """正面看的一朵莲花（刺绣、彩画里最常见的那种）：后排五瓣朝上外翻，中间露一点莲蓬，前排三瓣宽而饱满；
    下面两片侧着的荷叶（叶缘起伏、叶脉放射）。(cx, cy) 是花托，s 是花高"""
    pal = pal or (K['white'], K['pink_dk'], K['pink_pale'], K['pink'])
    gold = K['gold'] if outline is None else outline
    if stem:
        pad.put(pad.taper_mask([(cx, cy), (cx + s * 0.04, cy + s * 0.5), (cx - s * 0.02, cy + s * 0.95)], s * 0.06, s * 0.045), K['green_dk'])
    if leaves:
        for sg in (-1, 1):
            # 荷叶：一片侧着看的大圆叶（扁椭圆），叶缘起伏，叶心在靠茎的一边
            lx, ly = cx + sg * s * 0.55, cy + s * 0.36
            rx, ry = s * 0.5, s * 0.15
            tilt = -sg * 0.18
            pts = []
            for i in range(73):
                t = 2 * math.pi * i / 72
                wob = 1 + 0.045 * math.sin(t * 9 + sg)
                ex, ey = math.cos(t) * rx * wob, math.sin(t) * ry * wob
                pts.append((lx + ex * math.cos(tilt) - ey * math.sin(tilt), ly + ex * math.sin(tilt) + ey * math.cos(tilt)))
            m = pad.poly_mask(pts)
            pad.put(Pad.grow(m, 1.1), gold, mod=gold_mod(sg))
            hub = (lx - sg * rx * 0.15, ly + ry * 0.1)
            pad.put(m, banded(K['green_pale'], K['green_dk'], lambda x, y, hub=hub: np.hypot((x - hub[0]) / rx, (y - hub[1]) / ry) * 0.9, 5),
                    mod=stitch_fan(hub[0], hub[1], 160, 0.16))
            for k in range(11):
                t = 2 * math.pi * k / 11 + 0.3
                ex, ey = math.cos(t) * rx * 0.92, math.sin(t) * ry * 0.92
                q = (lx + ex * math.cos(tilt) - ey * math.sin(tilt), ly + ex * math.sin(tilt) + ey * math.cos(tilt))
                pad.put(pad.taper_mask([hub, ((hub[0] + q[0]) / 2, (hub[1] + q[1]) / 2), q], max(0.9, s * 0.012), 0.3), K['green_dk'], alpha=0.55)
            # 叶缘翻过来的一道浅边
            pad.put(pad.taper_mask(pts[40:66], max(0.8, s * 0.016), max(0.8, s * 0.016)), K['green_pale'], alpha=0.8)
    # 后排：五瓣（最外两瓣半掩、往外翻）
    for a, L, W in ((-66, 0.6, 0.34), (66, 0.6, 0.34), (-34, 0.8, 0.4), (34, 0.8, 0.4), (0, 0.9, 0.42)):
        draw_petal(pad, (cx, cy - s * 0.04), math.radians(a), s * L, s * W, pal[0], pal[1], gold, 1.0, 5, tip=0.06 * (1 if a > 0 else -1 if a < 0 else 0), vein=pal[1])
    # 莲蓬（中间露出一点）
    pad.put(Pad.grow(pad.ellipse_mask(cx, cy - s * 0.44, s * 0.16, s * 0.06), 1.0), gold)
    pad.put(pad.ellipse_mask(cx, cy - s * 0.44, s * 0.16, s * 0.06), K['yellow_lt'])
    for k in range(5):
        pad.put(pad.ellipse_mask(cx + (k - 2) * s * 0.055, cy - s * 0.445, s * 0.016, s * 0.011), K['yellow_dk'])
    # 前排：三瓣，宽、饱满，盖住后排的下半
    for a, L, W in ((-46, 0.6, 0.44), (46, 0.6, 0.44), (0, 0.56, 0.5)):
        draw_petal(pad, (cx, cy + s * 0.05), math.radians(a), s * L, s * W, pal[2], pal[3], gold, 1.0, 5, vein=pal[3])


def lotus_top(pad, cx, cy, r, rings=3, n=8, pal=None, outline=None, seed=0):
    """俯视的莲花（团花）：一圈圈花瓣，中间莲蓬"""
    pal = pal or [(K['pink_dk'], K['pink_pale']), (K['pink'], K['white']), (K['red_lt'], K['pink_lt'])]
    gold = K['gold'] if outline is None else outline
    for k in range(rings):
        rr = r * (1.0 - 0.27 * k)
        lo, hi = pal[k % len(pal)]
        for i in range(n):
            a = 2 * math.pi * (i + 0.5 * (k % 2)) / n
            ang = a  # 朝外
            base = (cx, cy)
            draw_petal(pad, base, ang, rr, rr * 2.2 * math.sin(math.pi / n) * 1.25, hi, lo, gold, 1.0, 5, vein=lo)
    pad.put(pad.ellipse_mask(cx, cy, r * 0.26, r * 0.26), K['yellow'])
    for i in range(7):
        a = 2 * math.pi * i / 7
        rr = r * 0.13 if i else 0
        pad.put(pad.ellipse_mask(cx + math.cos(a) * rr, cy + math.sin(a) * rr, r * 0.04, r * 0.04), K['yellow_deep'])
    ring = Pad.grow(pad.ellipse_mask(cx, cy, r * 0.26, r * 0.26), 1.2)
    inner = pad.ellipse_mask(cx, cy, r * 0.26, r * 0.26)
    # 莲蓬外一圈金线（整朵花在画布外时没有遮罩）
    if ring is None or inner is None:
        return
    X0, Y0, a = ring
    X1, Y1, b = inner
    a2 = a.copy()
    a2[Y1 - Y0:Y1 - Y0 + b.shape[0], X1 - X0:X1 - X0 + b.shape[1]] -= b
    pad.put((X0, Y0, np.clip(a2, 0, 1)), gold)


def spiral_pts(cx, cy, r0, turns=1.3, a0=0.0, sgn=1, n=40, shrink=0.88):
    pts = []
    for i in range(n + 1):
        t = i / n
        a = a0 + sgn * t * turns * 2 * math.pi
        r = r0 * (1 - shrink * t)
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def cloud(pad, cx, cy, s, fill, edge, line, flip=1, tail=True):
    """祥云：几团圆鼓鼓的云头，每团里一道卷，后面拖一条云尾"""
    blobs = [(0, 0, 0.5), (flip * 0.62, 0.12, 0.36), (-flip * 0.55, 0.16, 0.32), (flip * 0.18, -0.38, 0.3)]
    ms = [pad.ellipse_mask(cx + bx * s, cy + by * s, br * s, br * s) for bx, by, br in blobs]
    if tail:
        pts = []
        for i in range(21):
            t = i / 20
            pts.append((cx - flip * (0.4 + 1.2 * t) * s, cy + (0.25 + 0.18 * math.sin(t * 3.0)) * s))
        ms.append(pad.taper_mask(pts, 0.42 * s, 0.04 * s))
    if all(m is None for m in ms):
        return                      # 整朵云在画布外面
    body = Pad.union(*ms)
    pad.put(Pad.grow(body, max(1.0, s * 0.05)), edge)
    pad.put(body, fill, mod=stitch_lines(0.5, 1.4, 0.14))
    for (bx, by, br) in blobs:
        pts = spiral_pts(cx + bx * s, cy + by * s, br * s * 0.75, 1.1, math.pi * (0.2 if flip > 0 else 0.8), flip)
        pad.put(pad.taper_mask(pts, max(0.9, s * 0.08), max(0.5, s * 0.02)), line)


def meander(pad, x0, y0, x1, h, color, w=None):
    """回纹带：一个个方形的回旋，下面一条底线连起来"""
    w = w or max(1.0, h * 0.13)
    u = h * 0.86
    n = max(1, int((x1 - x0) / u))
    u = (x1 - x0) / n
    m = []
    for i in range(n):
        ox = x0 + i * u
        pts = [(0.0, 1.0), (0.0, 0.0), (0.9, 0.0), (0.9, 0.72), (0.25, 0.72), (0.25, 0.28), (0.65, 0.28), (0.65, 0.5), (0.45, 0.5)]
        q = [(ox + p[0] * u + w / 2, y0 + p[1] * (h - w) + w / 2) for p in pts]
        m.append(pad.line_mask(q, w))
    m.append(pad.line_mask([(x0, y0 + h - w / 2), (x1, y0 + h - w / 2)], w))
    pad.put(Pad.union(*m), color)


def beads(pad, x0, x1, y, r, color, gap=1.6):
    n = int((x1 - x0) / (r * 2 * gap))
    for i in range(n):
        x = x0 + (i + 0.5) * (x1 - x0) / n
        pad.put(pad.ellipse_mask(x, y, r, r), color, mod=lambda xx, yy, x=x: 1.0 + 0.3 * np.clip((x - xx - (yy - y)) / r, -1, 1))


def sea_cliff(pad, x0, y0, x1, y1, seed=0):
    """海水江崖：底下一排斜着的「立水」彩条，上面卷起的浪花，中间和两头立着山石"""
    rng = random.Random(seed)
    W, H = x1 - x0, y1 - y0
    cols = [K['blue_deep'], K['blue'], K['blue_lt'], K['blue_pale'], K['white'], K['green_pale'], K['green_lt'], K['green'], K['purple_lt'], K['pink_lt']]
    ly0 = y0 + H * 0.45
    mid = (x0 + x1) / 2

    def stripes(x, y):
        # 从中间往两边斜下去，一条条波浪形的彩条
        u = np.abs(x - mid) * 0.75 + (y - ly0) * 1.0 + np.sin((y - ly0) * 0.35 + np.abs(x - mid) * 0.05) * 2.0
        k = np.floor(u / (H * 0.045)).astype(int) % len(cols)
        out = np.empty(x.shape + (3,), np.float32)
        for i, c in enumerate(cols):
            out[k == i] = c
        return out
    m = pad.poly_mask([(x0, ly0), (x1, ly0), (x1, y1), (x0, y1)])
    pad.put(m, stripes)
    # 彩条之间的细白线
    def lines(x, y):
        u = np.abs(x - mid) * 0.75 + (y - ly0) + np.sin((y - ly0) * 0.35 + np.abs(x - mid) * 0.05) * 2.0
        f = (u / (H * 0.045)) % 1.0
        return 1.0 - 0.35 * (f < 0.12)
    pad.put(m, lambda x, y: pad_sample(pad, x, y), mod=lines)
    # 平水：一排卷浪
    wy = ly0
    n = int(W / (H * 0.42))
    for i in range(n + 1):
        cx = x0 + (i + 0.5) * W / n
        r = H * 0.2
        body = pad.ellipse_mask(cx, wy, r * 1.2, r * 0.9)
        pad.put(Pad.grow(body, 1.0), K['blue_dk'])
        pad.put(body, banded(K['blue'], K['white'], lambda x, y, cy=wy, r=r: (cy + r * 0.9 - y) / (r * 1.8), 4), mod=stitch_radial(cx, wy + r, 1.3, 0.15))
        pts = spiral_pts(cx + r * 0.2, wy - r * 0.05, r * 0.7, 1.2, math.pi * 0.9, 1 if i % 2 else -1)
        pad.put(pad.taper_mask(pts, max(1.0, r * 0.16), 0.6), K['blue_dk'])
        # 浪尖上的浪花点
        for k in range(3):
            pad.put(pad.ellipse_mask(cx - r * 0.6 + k * r * 0.5, wy - r * 0.95, r * 0.1, r * 0.1), K['white'])
    # 江崖：两头各一组山石（中间留给莲花的茎）：一高两低三座尖峰，青绿退晕、白粉勾边
    for side in (0, 1):
        for (fx, hh, ww) in ((0.1, 0.92, 0.045), (0.065, 0.62, 0.032), (0.14, 0.58, 0.03)):
            cx = x0 + W * fx if side == 0 else x1 - W * fx
            top = y1 - H * hh
            bw = W * ww
            pts = [(cx - bw, wy + H * 0.15), (cx - bw * 0.7, top + H * 0.3), (cx - bw * 0.35, top + H * 0.1), (cx - bw * 0.1, top),
                   (cx + bw * 0.2, top + H * 0.06), (cx + bw * 0.55, top + H * 0.22), (cx + bw * 0.8, top + H * 0.36), (cx + bw, wy + H * 0.15)]
            m = pad.poly_mask(pts)
            pad.put(Pad.grow(m, 1.4), K['white'])
            pad.put(m, banded(K['green_dk'], K['green_pale'], lambda x, y, top=top: 1 - (y - top) / (wy + H * 0.15 - top), 5),
                    mod=stitch_lines(1.0, 1.4, 0.16))
            for k in range(3):
                yy = top + (wy - top) * (0.25 + 0.22 * k)
                pad.put(pad.line_mask([(cx - bw * 0.35, yy + H * 0.03), (cx, yy), (cx + bw * 0.4, yy + H * 0.04)], max(0.8, H * 0.012)), K['white'], alpha=0.8)


def pad_sample(pad, x, y):
    """读画布当前的颜色（给 mod 叠在已有的颜色上用）"""
    xi = np.clip((x * SS).astype(int), 0, pad.W - 1)
    yi = np.clip((y * SS).astype(int), 0, pad.H - 1)
    return pad.a[yi, xi]


def char_medallion(pad, ch, cx, cy, r, field, ring, text):
    """一个圆的字牌：外一圈金、里面底色、正中一个金字（字外描深色边）"""
    pad.put(pad.ellipse_mask(cx, cy, r + 2.2, r + 2.2), K['gold_dk'])
    pad.put(pad.ellipse_mask(cx, cy, r, r), ring, mod=gold_mod(0.3))
    pad.put(pad.ellipse_mask(cx, cy, r * 0.86, r * 0.86), K['gold_dk'])
    pad.put(pad.ellipse_mask(cx, cy, r * 0.83, r * 0.83), field, mod=stitch_radial(cx, cy, 1.4, 0.08))
    for i in range(16):
        a = 2 * math.pi * i / 16
        pad.put(pad.ellipse_mask(cx + math.cos(a) * r * 0.93, cy + math.sin(a) * r * 0.93, r * 0.035, r * 0.035), K['gold_lt'])
    t = pad.text_mask(ch, cx, cy, r * 1.05, stroke=r * 0.05)
    pad.put(Pad.grow(t, max(1.0, r * 0.04)), K['ink'])
    pad.put(t, text, mod=stitch_lines(0.8, 1.2, 0.1))


def scroll_vine(pad, x0, y0, x1, y1, period, color, leaf, flower=None, seed=0, w=None, lotus=False):
    """缠枝（卷草）：一条波浪形的主藤；每个波峰、波谷顺着藤的走向分出一支卷须，越卷越细、卷成一个圈，
    分叉处长两片卷叶；卷心里开一朵小花（lotus=True 时是一朵正面的莲花）"""
    rng = random.Random(seed)
    H = y1 - y0
    cy = (y0 + y1) / 2
    w = w or max(1.0, H * 0.055)
    amp = H * 0.2
    pts = []
    n = int((x1 - x0) / 2) + 2
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        pts.append((x, cy + math.sin((x - x0) / period * 2 * math.pi) * amp))
    pad.put(pad.line_mask(pts, w), color)
    k = 0
    x = x0 + period * 0.25
    while x < x1 + period:
        sg = 1 if k % 2 == 0 else -1          # 1：波峰（往上卷），-1：波谷（往下卷）
        px, py = x + period * 0.08, cy - sg * amp * 0.95
        # 卷须：从藤上分出，往前上方伸，再卷回来成一个圈
        R = H * 0.2
        ccx, ccy = px + period * 0.16, py - sg * R * 0.95
        a0 = math.atan2(py - ccy, px - ccx)
        sp = spiral_pts(ccx, ccy, math.hypot(px - ccx, py - ccy), 1.05, a0, -sg if sg > 0 else 1, 36, 0.72)
        pad.put(pad.taper_mask(sp, w * 1.05, w * 0.35), color)
        # 卷叶：分叉处两片（叶尖往回勾）
        for (lx, ly, la, ll) in ((px - period * 0.03, py, -0.6, 0.32), (px + period * 0.05, py + sg * H * 0.04, 2.2, 0.24)):
            ang = la if sg > 0 else math.pi - la
            pts2 = petal_pts((lx, ly), ang, H * ll, H * 0.13, n=16, tip=0.35 * sg, base_w=0.15)
            mm = pad.poly_mask(pts2)
            pad.put(Pad.grow(mm, 0.8), color)
            pad.put(mm, banded(leaf, tint_arr(leaf, 0.35), lambda xx, yy, lx=lx, ly=ly: np.hypot(xx - lx, yy - ly) / (H * ll), 3))
        fx, fy = ccx, ccy
        if lotus:
            lotus_front(pad, fx, fy + H * 0.12, H * 0.34, leaves=False, stem=False)
        elif flower is not None:
            for i in range(5):
                a = 2 * math.pi * i / 5
                pad.put(pad.ellipse_mask(fx + math.cos(a) * H * 0.06, fy + math.sin(a) * H * 0.06, H * 0.055, H * 0.055), flower)
            pad.put(pad.ellipse_mask(fx, fy, H * 0.035, H * 0.035), K['gold_lt'])
        x += period / 2
        k += 1


def frame(pad, x0, y0, x1, y1, w, color, mod=None):
    pad.put(pad.poly_mask([(x0, y0), (x1, y0), (x1, y0 + w), (x0, y0 + w)]), color, mod=mod)
    pad.put(pad.poly_mask([(x0, y1 - w), (x1, y1 - w), (x1, y1), (x0, y1)]), color, mod=mod)
    pad.put(pad.poly_mask([(x0, y0), (x0 + w, y0), (x0 + w, y1), (x0, y1)]), color, mod=mod)
    pad.put(pad.poly_mask([(x1 - w, y0), (x1, y0), (x1, y1), (x1 - w, y1)]), color, mod=mod)


def rect(pad, x0, y0, x1, y1, color, mod=None, alpha=1.0):
    pad.put(pad.poly_mask([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]), color, mod=mod, alpha=alpha)


def ruyi_lappets(pad, x0, x1, y, h, n, fill, edge, inner):
    """如意云头的垂角：一排倒挂的三瓣云头（左右两瓣圆、下面一瓣、最下一个小尖），挂在横带下面，瓣里各一道卷"""
    u = (x1 - x0) / n
    for i in range(n):
        cx = x0 + (i + 0.5) * u
        s = u * 0.36
        lobes = [(cx - 0.52 * s, y + 0.34 * h, 0.5 * s), (cx + 0.52 * s, y + 0.34 * h, 0.5 * s), (cx, y + 0.62 * h, 0.44 * s)]
        ms = [pad.ellipse_mask(lx, ly, lr, min(lr, h * 0.32)) for lx, ly, lr in lobes]
        ms.append(pad.poly_mask([(cx - 0.32 * s, y + 0.7 * h), (cx + 0.32 * s, y + 0.7 * h), (cx, y + h)]))
        ms.append(pad.poly_mask([(cx - 0.5 * s, y), (cx + 0.5 * s, y), (cx + 0.3 * s, y + 0.3 * h), (cx - 0.3 * s, y + 0.3 * h)]))
        m = Pad.union(*ms)
        pad.put(Pad.grow(m, 1.6), edge, mod=gold_mod(i))
        pad.put(m, banded(fill, tint_arr(fill, 0.18), lambda xx, yy: 1 - (yy - y) / h, 3), mod=stitch_lines(1.2, 1.4, 0.12))
        for (lx, ly, lr), sg in zip(lobes, (1, -1, 1)):
            r0 = min(lr, h * 0.32) * 0.72
            pts = spiral_pts(lx, ly, r0, 1.05, math.pi * (0.5 if sg > 0 else 0.5), sg, 24, 0.8)
            pad.put(pad.taper_mask(pts, max(1, s * 0.08), 0.6), inner)


# ════════════════════ 各张贴图 ════════════════════

def frontal_panel(pad, X0, Y0, W, H, chars, seed=0):
    """一幅桌围：上面一道黄底回纹的横带挂一排如意云头，大红缎地上暗织云纹，
    正中一朵大莲花（盘金），两边金字团牌，下面海水江崖。最外一圈金边"""
    rng = random.Random(seed)
    pad.clip = (X0, Y0, X0 + W, Y0 + H)
    # 大红缎地 + 暗纹（同色深一点的小云）
    rect(pad, X0, Y0, X0 + W, Y0 + H, K['red'], mod=weave(2.0, 0.07, seed))
    for i in range(int(W / 70) + 1):
        for j in range(int(H / 70) + 1):
            x = X0 + i * 70 + (35 if j % 2 else 0)
            y = Y0 + j * 70 + 20
            for (dx, dy, r) in ((0, 0, 9), (10, 3, 6.5), (-9, 4, 6)):
                pad.put(pad.ellipse_mask(x + dx, y + dy, r, r), K['red_dk'], alpha=0.35)
    band = H * 0.15
    # 顶上横带
    rect(pad, X0, Y0, X0 + W, Y0 + band, K['yellow'], mod=weave(2.0, 0.06, seed + 1))
    meander(pad, X0 + 6, Y0 + band * 0.22, X0 + W - 6, band * 0.5, K['red_dk'])
    beads(pad, X0 + 4, X0 + W - 4, Y0 + band * 0.12, band * 0.045, K['gold_lt'])
    rect(pad, X0, Y0 + band * 0.86, X0 + W, Y0 + band, K['gold'], mod=gold_mod(2))
    # 横带下挂如意云头
    n = max(5, int(W / (H * 0.36)))
    ruyi_lappets(pad, X0, X0 + W, Y0 + band * 0.92, H * 0.16, n, K['yellow'], K['gold'], K['red_dk'])
    # 下面海水江崖
    sea_h = H * 0.27
    sea_cliff(pad, X0, Y0 + H - sea_h, X0 + W, Y0 + H - H * 0.03, seed)
    rect(pad, X0, Y0 + H - H * 0.03, X0 + W, Y0 + H, K['gold'], mod=gold_mod(3))
    # 中间的祥云
    cy = Y0 + band + (H - band - sea_h) * 0.52
    for (fx, fy, s, fl) in ((0.16, 0.08, 0.06, 1), (0.84, 0.08, 0.06, -1), (0.33, -0.12, 0.045, -1), (0.67, -0.12, 0.045, 1),
                            (0.08, -0.15, 0.04, 1), (0.92, -0.15, 0.04, -1)):
        cloud(pad, X0 + W * fx, cy + H * fy, H * s, K['blue_lt'], K['gold'], K['blue_dk'], fl)
    # 正中大莲花
    s = H * 0.42
    # 莲花后的火焰光
    hx, hy, hr = X0 + W / 2, cy - s * 0.04, s * 0.56
    halo = Pad.union(pad.ellipse_mask(hx, hy, hr, hr * 0.92), pad.poly_mask([(hx - hr * 0.55, hy - hr * 0.6), (hx + hr * 0.55, hy - hr * 0.6), (hx, hy - hr * 1.22)]))
    pad.put(Pad.grow(halo, 2.0), K['gold'], mod=gold_mod(0.2))
    pad.put(halo, banded(K['red_dk'], K['orange'], lambda x, y: 1 - np.hypot((x - hx) / hr, (y - hy) / (hr * 1.1)), 4),
            mod=stitch_radial(hx, hy, 1.4, 0.14))
    # 光圈上一圈火焰纹的小尖
    for i in range(15):
        ang = math.pi * (-0.95 + 0.9 * i / 14) - math.pi / 2 + math.pi / 2
        a_ = math.pi + math.pi * i / 14
        bx, by = hx + math.cos(a_) * hr * 0.9, hy + math.sin(a_) * hr * 0.82
        pad.put(pad.poly_mask(petal_pts((bx, by), a_ + math.pi / 2 - 0.25, hr * 0.27, hr * 0.13, 12, tip=0.4, base_w=0.7)), K['gold'], mod=gold_mod(i))
    lotus_front(pad, X0 + W / 2, cy + s * 0.36, s * 0.92)
    # 两边金字团牌
    nch = len(chars)
    if nch:
        half = nch // 2
        r = H * 0.14
        xs = []
        for i in range(half):
            xs.append(X0 + W * (0.5 - 0.17 - i * 0.13) if nch > 2 else X0 + W * 0.22)
        xs = sorted(xs) + sorted([X0 + W - (x - X0) for x in xs])
        for ch, x in zip(chars, xs):
            char_medallion(pad, ch, x, cy, r, K['red_dk'], K['gold'], K['gold_lt'])
    # 最外一圈金边、里面一道细黑线
    frame(pad, X0, Y0, X0 + W, Y0 + H, 3.0, K['gold'], gold_mod(4))
    frame(pad, X0 + 3, Y0 + 3, X0 + W - 3, Y0 + H - 3, 1.0, K['red_deep'])
    pad.clip = None


KNEEL_TOP = (44, 0, 468, 512)      # 拜垫顶面在 paint_brocade 里的那一块（像素，左上角原点）；hall_props.kneel_mat 按它算 uv


def rr_path(x0, y0, x1, y1, r, n_side=40, n_corner=10):
    """圆角矩形的边界（顺时针，图片坐标），返回 [(x, y, 切线角)]"""
    out = []
    segs = [((x0 + r, y0), (x1 - r, y0)), ((x1, y0 + r), (x1, y1 - r)), ((x1 - r, y1), (x0 + r, y1)), ((x0, y1 - r), (x0, y0 + r))]
    cs = [(x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)]
    for k in range(4):
        (ax, ay), (bx, by) = segs[k]
        for i in range(n_side):
            t = i / n_side
            out.append((ax + (bx - ax) * t, ay + (by - ay) * t, math.atan2(by - ay, bx - ax)))
        cx, cy, a0 = cs[k]
        for i in range(n_corner):
            a = math.radians(a0 + 90 * i / n_corner)
            out.append((cx + math.cos(a) * r, cy + math.sin(a) * r, a + math.pi / 2))
    return out


def rr_mask(pad, x0, y0, x1, y1, r):
    return pad.poly_mask([(p[0], p[1]) for p in rr_path(x0, y0, x1, y1, r, 8, 12)])


def kneel_top(pad, yellow_ground):
    """拜垫顶面（圆角矩形）：红锦外圈里一圈金回纹（一个个回纹顺着边转过去）、金联珠，里面黄锦地、四角如意云、
    中间一圈八个卷草托着一朵俯视的莲花"""
    x0, y0, x1, y1 = KNEEL_TOP
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rect(pad, 0, 0, 512, 512, K['red'], mod=weave(1.8, 0.07, 3))
    # 外圈：红锦上一圈回纹（单元沿边排，跟着边转）
    path = rr_path(x0 + 17, y0 + 17, x1 - 17, y1 - 17, 52, 1, 1)
    per = []
    L = 0.0
    dense = rr_path(x0 + 17, y0 + 17, x1 - 17, y1 - 17, 52, 60, 24)
    acc = [0.0]
    for i in range(1, len(dense) + 1):
        a_, b_ = dense[i - 1], dense[i % len(dense)]
        acc.append(acc[-1] + math.hypot(b_[0] - a_[0], b_[1] - a_[1]))
    n = int(acc[-1] / 26)
    for i in range(n):
        target = (i + 0.5) * acc[-1] / n
        k = max(j for j in range(len(dense)) if acc[j] <= target)
        x, y, a = dense[k]
        pts = [(-1, 1), (-1, -1), (1, -1), (1, 0.5), (-0.4, 0.5), (-0.4, -0.4), (0.5, -0.4)]
        ca, sa = math.cos(a), math.sin(a)
        q = [(x + (p[0] * ca - p[1] * sa) * 10.5, y + (p[0] * sa + p[1] * ca) * 10.5) for p in pts]
        pad.put(pad.line_mask(q, 2.8), K['gold'], mod=gold_mod(i))
    # 两道金线夹住回纹带
    for (ins, w) in ((2, 3.5), (33, 3.0)):
        mo = rr_mask(pad, x0 + ins, y0 + ins, x1 - ins, y1 - ins, 66 - ins)
        mi = rr_mask(pad, x0 + ins + w, y0 + ins + w, x1 - ins - w, y1 - ins - w, 66 - ins - w)
        X0, Y0, A = mo
        X1, Y1, B = mi
        A = A.copy()
        A[Y1 - Y0:Y1 - Y0 + B.shape[0], X1 - X0:X1 - X0 + B.shape[1]] -= B
        pad.put((X0, Y0, np.clip(A, 0, 1)), K['gold'], mod=gold_mod(ins))
    # 联珠：金线里侧一圈小珠
    for (x, y, a) in rr_path(x0 + 42, y0 + 42, x1 - 42, y1 - 42, 30, 14, 4):
        pad.put(pad.ellipse_mask(x, y, 2.6, 2.6), K['gold_lt'])
    # 里面：黄锦
    inner = rr_mask(pad, x0 + 47, y0 + 47, x1 - 47, y1 - 47, 26)
    pad.put(inner, K['yellow'], mod=weave(1.8, 0.07, 5))
    pad.clip = (x0 + 50, y0 + 50, x1 - 50, y1 - 50)
    yellow_ground(x0 + 50, y0 + 50, x1 - 50, y1 - 50, 6)
    pad.clip = None
    # 四角如意云
    for (sx, sy) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        px_, py_ = cx + sx * (cx - x0 - 86), cy + sy * (cy - y0 - 88)
        cloud(pad, px_, py_, 20, K['red_lt'], K['gold'], K['red_dk'], -sx, tail=False)
    # 八个卷草（椭圆一圈，绿叶金线卷须）
    for i in range(8):
        a = 2 * math.pi * i / 8 + math.pi / 8
        px_, py_ = cx + math.cos(a) * 118, cy + math.sin(a) * 150
        sp = spiral_pts(px_, py_, 22, 1.0, a + math.pi, 1, 26, 0.8)
        pad.put(pad.taper_mask(sp, 4.5, 1.4), K['green'])
        pts = petal_pts((px_, py_), a + math.pi * 0.5, 30, 15, 14, tip=0.3)
        m = pad.poly_mask(pts)
        pad.put(Pad.grow(m, 1.0), K['gold'])
        pad.put(m, K['green_lt'])
    # 正中莲花，外面一圈金线团
    ring = Pad.grow(pad.ellipse_mask(cx, cy, 104, 104), 2.5)
    pad.put(ring, K['gold'], mod=gold_mod(11))
    pad.put(pad.ellipse_mask(cx, cy, 104, 104), K['red'], mod=weave(1.8, 0.07, 12))
    lotus_top(pad, cx, cy, 96, rings=3, n=8)


CANDLE = (0, 1416, 480, 2040)      # 红蜡烛的龙纹（paint_frontal 里没用的一块）：横着正好绕蜡烛一圈（左右接得上），竖着是蜡烛侧面从下到上


def candle_band(pad):
    """龙凤烛上的描金盘龙：红蜡地，一条金龙从下往上盘一圈（身上鳞片、背鳍、三只爪），龙头在上、张口对着一颗火珠，四周金云；
    上下两道金箍。横向首尾相接（绕在圆柱上没有接缝）"""
    X0, Y0, X1, Y1 = CANDLE
    W = X1 - X0
    gold, gdk, glt = K['gold'], K['gold_dk'], K['gold_lt']
    red = hexc('#c3261d')
    rng = random.Random(41)
    pad.clip = CANDLE
    rect(pad, X0, Y0, X1, Y1, red, mod=lambda x, y: 1.0 + 0.04 * np.sin(y * 0.08 + np.sin(x * 0.05) * 2) + 0.02 * np.sin(x * 0.9 + y * 0.3))
    # 上下金箍（各一道联珠）
    for (ya, yb) in ((Y0, Y0 + 26), (Y1 - 26, Y1)):
        rect(pad, X0, ya, X1, yb, gold, mod=gold_mod(ya))
        rect(pad, X0, ya + 3, X1, ya + 5, gdk)
        rect(pad, X0, yb - 5, X1, yb - 3, gdk)
        beads(pad, X0, X1, (ya + yb) / 2, 4.2, glt, 1.5)

    def wrapput(fn):
        for dx in (-W, 0, W):
            fn(dx)
    # 云：金线勾边的小朵云（先画，龙压在上面）
    for (u, v, s_) in ((0.12, 0.13, 22), (0.62, 0.08, 18), (0.84, 0.36, 20), (0.3, 0.55, 18), (0.05, 0.8, 20), (0.55, 0.9, 22), (0.92, 0.68, 16)):
        wrapput(lambda dx, u=u, v=v, s_=s_: cloud(pad, X0 + u * W + dx, Y0 + 40 + v * (Y1 - Y0 - 80), s_, tint_arr(red, 0.12), gold, gdk,
                                                   1 if u < 0.5 else -1, tail=True))
    # 龙身：一条从左下往右上的 S 形，正好绕一圈（右端接回左端那一截在下一圈之外，用 dx 复制补上）
    def body_pt(t):
        x = X0 + W * (0.02 + 1.0 * t)
        y = Y1 - 70 - (Y1 - Y0 - 250) * t + 58 * math.sin(2 * math.pi * t * 1.5 + 0.4)
        return (x, y)
    N = 90
    pts = [body_pt(i / N) for i in range(N + 1)]

    def width(t):
        return 12 + 44 * math.sin(math.pi * min(1.0, 0.15 + t * 0.95)) ** 0.7 if t < 0.97 else 30
    left, right = [], []
    for i in range(N + 1):
        t = i / N
        p = pts[i]
        q0, q1 = pts[max(0, i - 1)], pts[min(N, i + 1)]
        dx_, dy_ = q1[0] - q0[0], q1[1] - q0[1]
        L = math.hypot(dx_, dy_) or 1
        nx, ny = -dy_ / L, dx_ / L
        w = width(t) / 2
        left.append((p[0] + nx * w, p[1] + ny * w))
        right.append((p[0] - nx * w, p[1] - ny * w))
    poly = left + right[::-1]
    # 腿（先画在身子下面）：三只，每只三爪
    for t in (0.22, 0.5, 0.78):
        i = int(t * N)
        p = pts[i]
        dx_, dy_ = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        L = math.hypot(dx_, dy_)
        nx, ny = -dy_ / L, dx_ / L                    # 指向身子「左」边（图上偏下）
        sg = 1 if (int(t * 10) % 2 == 0) else -1
        knee = (p[0] + nx * sg * 46 + dx_ / L * 12, p[1] + ny * sg * 46 + dy_ / L * 12)
        foot = (knee[0] + dx_ / L * 28 + nx * sg * 8, knee[1] + dy_ / L * 28 + ny * sg * 8)

        def leg(dx, p=p, knee=knee, foot=foot, dxl=dx_ / L, dyl=dy_ / L):
            pp = [(p[0] + dx, p[1]), (knee[0] + dx, knee[1]), (foot[0] + dx, foot[1])]
            m = pad.taper_mask(pp, 17, 10)
            pad.put(Pad.grow(m, 1.8), gdk)
            pad.put(m, gold, mod=gold_mod(1))
            # 肘后一撮毛
            pad.put(pad.taper_mask([(knee[0] + dx, knee[1]), (knee[0] + dx - dxl * 16 - 4, knee[1] - dyl * 16 + 6)], 7, 1), gdk)
            for k in (-1, 0, 1):
                a = math.atan2(dyl, dxl) + k * 0.65
                c = [(foot[0] + dx, foot[1]), (foot[0] + dx + math.cos(a) * 15, foot[1] + math.sin(a) * 15),
                     (foot[0] + dx + math.cos(a + 0.9) * 21, foot[1] + math.sin(a + 0.9) * 21)]
                pad.put(Pad.grow(pad.taper_mask(c, 6.5, 1.5), 1.0), gdk)
                pad.put(pad.taper_mask(c, 6.5, 1.5), glt)
        wrapput(leg)

    def draw_body(dx):
        pp = [(x + dx, y) for (x, y) in poly]
        m = pad.poly_mask(pp)
        pad.put(Pad.grow(m, 2.0), gdk)
        pad.put(m, gold, mod=gold_mod(3))
        # 背鳍：身子上沿一排小三角
        for i in range(4, N - 6, 3):
            t = i / N
            a, b = left[i], left[i + 2]
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            nx, ny = mx - pts[i + 1][0], my - pts[i + 1][1]
            L = math.hypot(nx, ny) or 1
            tip = (mx + nx / L * 10 - (b[0] - a[0]) * 0.4 + dx, my + ny / L * 10 - (b[1] - a[1]) * 0.4)
            pad.put(pad.poly_mask([(a[0] + dx, a[1]), (b[0] + dx, b[1]), tip]), gdk)
        # 鳞：一排排小弧（深金），腹下一道浅色腹甲
        for i in range(2, N - 4):
            t = i / N
            w = width(t) / 2
            p = pts[i]
            q0, q1 = pts[i - 1], pts[i + 1]
            dx_, dy_ = q1[0] - q0[0], q1[1] - q0[1]
            L = math.hypot(dx_, dy_)
            ux, uy = dx_ / L, dy_ / L
            nx, ny = -uy, ux
            for row in (-0.45, 0.0, 0.45):
                if (i + (1 if row == 0 else 0)) % 2:
                    continue
                c = (p[0] + nx * w * row + dx, p[1] + ny * w * row)
                r = w * 0.32
                arc = [(c[0] + (ux * math.cos(th) + nx * math.sin(th)) * r, c[1] + (uy * math.cos(th) + ny * math.sin(th)) * r)
                       for th in [math.pi * (0.5 + k / 8) for k in range(9)]]
                pad.put(pad.line_mask(arc, 1.5), gdk)
            if i % 2 == 0:
                c = (p[0] - nx * w * 0.78 + dx, p[1] - ny * w * 0.78)
                pad.put(pad.line_mask([(c[0] - ux * 3, c[1] - uy * 3), (c[0] + ux * 3, c[1] + uy * 3)], 2.2), glt)
    wrapput(draw_body)
    # 龙头（身子上端）：额头、长吻、张开的下颌、眼、两只鹿角、鬃毛、两根长须
    hx, hy = pts[-1]
    ang = math.atan2(pts[-1][1] - pts[-4][1], pts[-1][0] - pts[-4][0])
    ca, sa = math.cos(ang), math.sin(ang)

    def H(u, v):
        u, v = u * 1.55, v * 1.55
        return (hx + u * ca - v * sa, hy + u * sa + v * ca)

    def head(dx):
        def D(pts_):
            return [(x + dx, y) for (x, y) in pts_]
        # 鬃毛：脑后几道火焰形
        for k in range(5):
            b0 = H(-8, -12 + k * 6)
            pp = D([b0, H(-26 - k * 3, -20 + k * 9), H(-40 - k * 2, -26 + k * 12)])
            pad.put(pad.taper_mask(pp, 11, 1.5), gdk)
        upper = D([H(-12, -16), H(6, -20), H(26, -16), H(42, -10), H(48, -3), H(36, -2), H(18, -4), H(-6, 2)])
        lower = D([H(-6, 4), H(14, 4), H(34, 6), H(40, 12), H(26, 14), H(4, 13), H(-10, 10)])
        for poly_ in (upper, lower):
            m = pad.poly_mask(poly_)
            pad.put(Pad.grow(m, 1.8), gdk)
            pad.put(m, gold, mod=gold_mod(7))
        # 鼻头、眼、眉
        nz = H(44, -7)
        pad.put(pad.ellipse_mask(nz[0] + dx, nz[1], 6.5, 6.5), glt)
        e = H(10, -11)
        pad.put(pad.ellipse_mask(e[0] + dx, e[1], 7.5, 7.5), K['white'])
        pad.put(pad.ellipse_mask(e[0] + dx, e[1], 4.0, 4.0), K['ink'])
        pad.put(pad.taper_mask(D([H(0, -18), H(12, -21), H(22, -17)]), 3.5, 1.0), gdk)
        # 牙
        for u in (20, 30):
            pad.put(pad.poly_mask(D([H(u, -3), H(u + 4, -3), H(u + 2, 3)])), K['white'])
        # 角：两只往后上分叉
        for (v0, s_) in ((-18, 1), (-14, 0.8)):
            b = H(0, v0)
            tip = H(-30 * s_, v0 - 26 * s_)
            pad.put(pad.taper_mask(D([b, H(-14 * s_, v0 - 12 * s_), tip]), 5, 1.5), glt)
            br = H(-16 * s_, v0 - 14 * s_)
            pad.put(pad.taper_mask(D([br, H(-12 * s_, v0 - 26 * s_)]), 3, 1.0), glt)
        # 长须：从嘴角飘出去
        for (v0, ph) in ((-2, 0.0), (8, 1.4)):
            pp = [H(36 + 30 * t, v0 + 16 * math.sin(t * 4 + ph) * t) for t in [k / 10 for k in range(11)]]
            pad.put(pad.taper_mask(D(pp), 3.6, 0.8), glt)
    wrapput(head)
    # 火珠：龙口前一颗，周围一圈火焰
    fx, fy = H(70, -4)
    for dx in (-W, 0, W):
        for k in range(9):
            a = 2 * math.pi * k / 9
            pp = [(fx + dx + math.cos(a) * 14, fy + math.sin(a) * 14), (fx + dx + math.cos(a + 0.35) * 28, fy + math.sin(a + 0.35) * 28 - 6)]
            pad.put(pad.taper_mask(pp, 8, 1.2), K['orange'])
        pad.put(pad.ellipse_mask(fx + dx, fy, 15, 15), glt)
        pad.put(pad.ellipse_mask(fx + dx - 4, fy - 4, 5, 5), K['white'])
    pad.clip = None



def paint_frontal(out):
    """桌围（2048×2048）：
    上面 2048×600 是中间大供桌的（2.4 米宽 × 0.7 米高，字「佛光普照」）；
    中间 1312×600（左对齐，y 640..1240）是两边小供桌的（1.5 米宽，正中一朵莲花，两侧「吉祥」）；
    下面 y 1280..1408 是桌面上铺的黄缎桌布边（横着可以接着铺）；
    左下 CANDLE（x 0..480、y 1416..2040）是烛台上红蜡烛的描金盘龙（横着绕蜡烛一圈、首尾相接）。"""
    pad = Pad(2048, 2048, K['red_deep'])
    frontal_panel(pad, 0, 0, 2048, 600, '佛光普照', 1)
    frontal_panel(pad, 0, 640, 1312, 600, '吉祥', 2)
    # 桌布的垂边：黄缎、回纹、一排小莲瓣
    rect(pad, 0, 1280, 2048, 1408, K['yellow'], mod=weave(2, 0.06, 5))
    meander(pad, 4, 1296, 2044, 52, K['red_dk'])
    for i in range(48):
        x = (i + 0.5) * 2048 / 48
        draw_petal(pad, (x, 1404), 0, 46, 34, K['red'], K['pink_lt'], K['gold'], 1.0, 3)
    rect(pad, 0, 1280, 2048, 1286, K['gold'], mod=gold_mod(5))
    # 蜡烛上的描金盘龙（hall_props.candlestick 的蜡烛身子贴这一块）
    candle_band(pad)
    # 供桌、经案台面铺的黄缎：暗花（黄地黄花）一块 512×512，可以平铺
    damask_tile(pad, *DAMASK[:2], DAMASK[2] - DAMASK[0])
    return pad.save(os.path.join(out, 'paint_frontal.png'))


DAMASK = (512, 1456, 1024, 1968)   # paint_frontal 里暗花缎那一块（像素 x0, y0, x1, y1）；hall_props 按它算台面的 uv
DAMASK_PLAIN = (640, 1516)         # 这一块里只有素地（没有花）的一个点：台面翻过去的圆边这种窄条贴这一点


def damask_tile(pad, X0, Y0, T):
    """暗花缎（可平铺）：黄地，正中一朵团莲、四角各四分之一朵（拼起来是交错的团花），团花之间四朵小如意云，再撒小四瓣花；
    花纹只比地子深一档 / 浅一档（暗花：远看是素黄缎，近看才看出花）"""
    rect(pad, X0, Y0, X0 + T, Y0 + T, K['yellow'], mod=weave(1.8, 0.06, 50))
    old = pad.clip
    pad.clip = (X0, Y0, X0 + T, Y0 + T)
    dk = mixc(K['yellow'], K['yellow_dk'], 0.5)
    dk2 = mixc(K['yellow'], K['yellow_dk'], 0.3)
    lt = mixc(K['yellow'], K['yellow_lt'], 0.55)
    pal = [(dk, mixc(K['yellow'], K['yellow_lt'], 0.25)), (dk2, lt), (dk, lt)]
    line = mixc(K['yellow'], K['yellow_dk'], 0.65)
    for (cx, cy) in ((T / 2, T / 2), (0, 0), (T, 0), (0, T), (T, T)):
        lotus_top(pad, X0 + cx, Y0 + cy, 100, rings=3, n=8, pal=pal, outline=line)
    for (cx, cy, fl) in ((T / 2, 0, 1), (T / 2, T, 1), (0, T / 2, -1), (T, T / 2, -1)):
        cloud(pad, X0 + cx, Y0 + cy, 40, lt, dk, dk, fl, tail=False)
    for (cx, cy) in ((T / 4, T / 4), (3 * T / 4, T / 4), (T / 4, 3 * T / 4), (3 * T / 4, 3 * T / 4)):
        for k in range(4):
            ang = k * math.pi / 2 + math.pi / 4
            draw_petal(pad, (X0 + cx, Y0 + cy), ang, 20, 13, dk2, lt, None, 0.8, 3)
        pad.put(pad.ellipse_mask(X0 + cx, Y0 + cy, 3.5, 3.5), dk)
    pad.clip = old


def paint_brocade(out):
    """织锦（1024×1024）四格：
    左上 512×512：拜垫顶面（圆角矩形，用 x 44..468 那 424×512：外圈红锦金回纹、金联珠，里面黄锦、四角如意云、八个卷草，正中一朵俯视的莲花）；
    右上 512×512：禅修垫的方垫面（黄锦地、暗织小团花，四边红底金线的包边，四角如意）；
    左下 512×512：圆蒲团顶面（黄锦、正中莲花团、外一圈红边）；
    右下：四条横带，每条 512×128，侧面用（横向可以分段贴）：
        y 512..640 拜垫侧面（红锦、金色卷草）；640..768 蒲团侧面（黄锦褶子）；768..896 方垫侧边（红边金线）；896..1024 包边滚条（金黄绳纹）"""
    pad = Pad(1024, 1024, K['yellow'])

    # 黄锦地：小的四瓣花暗纹 + 卍字格
    def yellow_ground(x0, y0, x1, y1, seed):
        rect(pad, x0, y0, x1, y1, K['yellow'], mod=weave(1.8, 0.07, seed))
        step = 32
        for i in range(int((x1 - x0) / step) + 1):
            for j in range(int((y1 - y0) / step) + 1):
                x = x0 + i * step + (step / 2 if j % 2 else 0)
                y = y0 + j * step + step / 2
                if x > x1 - 4 or y > y1 - 4:
                    continue
                for a in range(4):
                    ang = a * math.pi / 2 + math.pi / 4
                    pad.put(pad.ellipse_mask(x + math.cos(ang) * 4.5, y + math.sin(ang) * 4.5, 3.6, 3.6), K['yellow_dk'], alpha=0.55)
                pad.put(pad.ellipse_mask(x, y, 2.2, 2.2), K['yellow_lt'], alpha=0.8)

    # 左上：拜垫顶（长圆角矩形的拜垫 0.62 × 0.75 米：贴图里横 424 像素（x 44..468）、竖 512 像素，比例和实物一样，圆不会被拉扁）
    kneel_top(pad, yellow_ground)

    # 右上：方垫面
    x0, y0 = 512, 0
    rect(pad, x0, y0, x0 + 512, y0 + 512, K['red'], mod=weave(1.8, 0.07, 7))
    yellow_ground(x0 + 40, y0 + 40, x0 + 472, y0 + 472, 8)
    frame(pad, x0 + 36, y0 + 36, x0 + 476, y0 + 476, 4, K['gold'], gold_mod(1))
    meander(pad, x0 + 8, y0 + 8, x0 + 504, 22, K['gold'], 2.6)
    meander(pad, x0 + 8, y0 + 482, x0 + 504, 22, K['gold'], 2.6)
    # 四角如意
    for (sx, sy) in ((0, 0), (1, 0), (0, 1), (1, 1)):
        cxp, cyp = x0 + 40 + sx * 432, y0 + 40 + sy * 432
        a = math.atan2(256 - (cyp - y0), 256 - (cxp - x0))
        cloud(pad, cxp + math.cos(a) * 30, cyp + math.sin(a) * 30, 18, K['red_lt'], K['gold'], K['red_dk'], 1 if sx else -1, tail=False)
    # 正中不画莲花（圆蒲团压在那儿，蒲团又往后挪了 0.12，画了会从蒲团前面露出一角粉边，像块污渍）；露出来的是四周，四周撒几朵小团花
    for (dx, dy) in ((-140, -140), (140, -140), (-140, 140), (140, 140)):
        lotus_top(pad, x0 + 256 + dx, y0 + 256 + dy, 34, rings=2, n=6, pal=[(K['red'], K['pink_lt']), (K['pink'], K['white'])])
    for (dx, dy) in ((0, -150), (0, 150), (-150, 0), (150, 0)):
        cloud(pad, x0 + 256 + dx, y0 + 256 + dy, 16, K['blue_lt'], K['gold'], K['blue_dk'], 1 if dx >= 0 else -1, tail=False)

    # 左下：圆蒲团顶面
    cx, cy = 256, 768
    rect(pad, 0, 512, 512, 1024, K['red'], mod=weave(1.8, 0.07, 9))
    pad.put(pad.ellipse_mask(cx, cy, 236, 236), K['yellow'], mod=weave(1.8, 0.07, 10))
    for i in range(32):
        a = 2 * math.pi * i / 32
        draw_petal(pad, (cx + math.cos(a) * 168, cy + math.sin(a) * 168), a + math.pi / 2, 50, 30, K['yellow_dk'], K['yellow_lt'], K['gold_dk'], 0.8, 3)
    lotus_top(pad, cx, cy, 120, rings=3, n=8)
    m1 = pad.ellipse_mask(cx, cy, 240, 240)
    m0 = pad.ellipse_mask(cx, cy, 232, 232)
    X0, Y0, a1 = m1
    X1, Y1, a0 = m0
    a1 = a1.copy()
    a1[Y1 - Y0:Y1 - Y0 + a0.shape[0], X1 - X0:X1 - X0 + a0.shape[1]] -= a0
    pad.put((X0, Y0, np.clip(a1, 0, 1)), K['gold'], mod=gold_mod(9))

    # 右下四条侧带
    x0 = 512
    # 拜垫侧面：红锦卷草
    rect(pad, x0, 512, 1024, 640, K['red'], mod=weave(1.8, 0.07, 11))
    pad.clip = (x0, 512, 1024, 640)            # 卷草别画出界（左边是蒲团顶面那一格）
    scroll_vine(pad, x0 - 128, 524, 1024 + 128, 628, 128, K['gold'], K['gold_dk'], K['pink_lt'], 1, 5)
    pad.clip = None
    rect(pad, x0, 512, 1024, 518, K['gold'], mod=gold_mod(6))
    rect(pad, x0, 634, 1024, 640, K['gold'], mod=gold_mod(7))
    # 蒲团侧面：黄锦、竖着的褶子（明暗）
    rect(pad, x0, 640, 1024, 768, K['yellow'], mod=lambda x, y: (1.0 + 0.16 * np.sin((x - 512) / 512 * 2 * math.pi * 12)) * weave(1.8, 0.05, 12)(x, y))
    beads(pad, x0, 1024, 650, 3.2, K['gold_lt'], 1.4)
    beads(pad, x0, 1024, 758, 3.2, K['gold_lt'], 1.4)
    # 方垫侧边：红缎、一道金线回纹
    rect(pad, x0, 768, 1024, 896, K['red'], mod=weave(1.8, 0.07, 13))
    meander(pad, x0, 800, 1024, 60, K['gold'], 5)
    # 滚条：金黄绳纹
    def rope(x, y):
        u = ((x - 512) + (y - 896) * 1.0) / 18.0
        return 1.0 + 0.32 * (np.abs((u % 1.0) - 0.5) * 2 - 0.5)
    rect(pad, x0, 896, 1024, 1024, K['gold'], mod=rope)
    return pad.save(os.path.join(out, 'paint_brocade.png'))


def banner_column(pad, X0, W, chars, field, field_lt, border, seed, ink=None):
    """一面幡（宽 W，高 2048）：
    y 0..360 幡头（三角形，莲花上托一个「佛」字）；360..1800 幡身（外锦边、里面四个字各一格，字间莲花）；
    1800..2048 幡尾（一道横带、垂角）"""
    H0, H1, H2 = 360, 1800, 2048
    # 幡头：三角形底子、外圈锦边
    rect(pad, X0, 0, X0 + W, H0, border, mod=weave(2, 0.07, seed))
    cx = X0 + W / 2
    tri = pad.poly_mask([(cx, 18), (X0 + W - 14, H0 - 12), (X0 + 14, H0 - 12)])
    pad.put(Pad.grow(tri, 3), K['gold'], mod=gold_mod(seed))
    pad.put(tri, field, mod=weave(2, 0.07, seed + 1))
    lotus_front(pad, cx, H0 - 40, W * 0.3, leaves=False, stem=False)
    char_medallion(pad, '佛', cx, H0 * 0.5 - 22, W * 0.13, K['red_dk'], K['gold'], K['gold_lt'])
    rect(pad, X0, H0 - 10, X0 + W, H0, K['gold'], mod=gold_mod(2))
    # 幡身：锦边
    rect(pad, X0, H0, X0 + W, H1, border, mod=weave(2, 0.07, seed + 2))
    bw = W * 0.12
    for y in range(H0 + 20, H1 - 10, 46):
        cloud(pad, X0 + bw / 2, y, bw * 0.26, K['blue_lt'], K['gold'], K['blue_dk'], 1, tail=False)
        cloud(pad, X0 + W - bw / 2, y + 23, bw * 0.26, K['blue_lt'], K['gold'], K['blue_dk'], -1, tail=False)
    rect(pad, X0 + bw, H0, X0 + W - bw, H1, field, mod=weave(2, 0.07, seed + 3))
    frame(pad, X0 + bw - 4, H0, X0 + W - bw + 4, H1, 4, K['gold'], gold_mod(3))
    # 四格字
    n = len(chars)
    cell = (H1 - H0 - 40) / n
    for i, ch in enumerate(chars):
        y = H0 + 20 + cell * (i + 0.5)
        # 格子：上下各一道回纹、两侧细金线
        ww = W - 2 * bw - 24
        rect(pad, X0 + bw + 12, y - cell / 2 + 10, X0 + W - bw - 12, y + cell / 2 - 10, field_lt, mod=weave(2, 0.06, seed + 4 + i))
        frame(pad, X0 + bw + 12, y - cell / 2 + 10, X0 + W - bw - 12, y + cell / 2 - 10, 2.2, K['gold'], gold_mod(i))
        t = pad.text_mask(ch, X0 + W / 2, y - cell * 0.04, ww * 0.78, stroke=2)
        if ink is None:
            pad.put(Pad.grow(t, 2.6), K['ink'])
            pad.put(t, K['gold_lt'], mod=stitch_lines(0.7, 1.3, 0.1))
        else:
            pad.put(Pad.grow(t, 2.6), K['gold'], mod=gold_mod(i))
            pad.put(t, ink, mod=stitch_lines(0.7, 1.3, 0.1))
        # 字下一朵小莲花
        if i < n - 1:
            ly = y + cell / 2
            for k in range(5):
                a = math.radians(-60 + 30 * k)
                draw_petal(pad, (X0 + W / 2, ly + 6), a, 22, 13, K['pink_dk'], K['pink_pale'], K['gold'], 0.8, 3)
    # 幡尾：横带 + 三个垂角
    rect(pad, X0, H1, X0 + W, H2, border, mod=weave(2, 0.07, seed + 9))
    meander(pad, X0 + 6, H1 + 10, X0 + W - 6, 40, K['gold'], 4)
    ruyi_lappets(pad, X0 + 8, X0 + W - 8, H1 + 64, 150, 3, field, K['gold'], K['gold_lt'])
    beads(pad, X0 + 8, X0 + W - 8, H2 - 16, 5, K['gold_lt'], 1.5)


def paint_banner(out):
    """幡（2048×2048）：四面幡各 440 宽（左起）：x 0..440 红底「佛日增辉」、440..880 红底「法轮常转」、
    880..1320 黄底「风调雨顺」、1320..1760 黄底「国泰民安」（两两成对：红的一对在中尊两旁、黄的一对在侧佛外边）；
    x 1760..1904 是两条幡带（各 72 宽，红、黄，从上到下一节一节的花纹），幡脚的飘带用；1904..2048 空着。"""
    pad = Pad(2048, 2048, K['red'])
    # 和匾一样用繁体
    banner_column(pad, 0, 440, '佛日增輝', K['red'], K['red_lt'], K['yellow'], 1)
    banner_column(pad, 440, 440, '法輪常轉', K['red'], K['red_lt'], K['yellow'], 5)
    banner_column(pad, 880, 440, '風調雨順', K['yellow'], K['yellow_lt'], K['red'], 2, ink=K['red_dk'])
    banner_column(pad, 1320, 440, '國泰民安', K['yellow'], K['yellow_lt'], K['red'], 6, ink=K['red_dk'])
    for k, (base, lt, dk) in enumerate(((K['red'], K['red_lt'], K['red_dk']), (K['yellow'], K['yellow_lt'], K['yellow_dk']))):
        x0 = 1760 + 72 * k
        rect(pad, x0, 0, x0 + 72, 2048, base, mod=weave(2, 0.07, 20 + k))
        frame(pad, x0, -10, x0 + 72, 2058, 3, K['gold'], gold_mod(k))
        for y in range(40, 2048, 160):
            for i in range(5):
                a = math.radians(-60 + 30 * i)
                draw_petal(pad, (x0 + 36, y + 30), a, 26, 15, dk, lt, K['gold'], 0.8, 3)
            pad.put(pad.ellipse_mask(x0 + 36, y + 90, 10, 10), K['gold'], mod=gold_mod(y))
            rect(pad, x0 + 4, y + 120, x0 + 68, y + 124, K['gold'], mod=gold_mod(y + 1))
    return pad.save(os.path.join(out, 'paint_banner.png'))


HEART = ('观自在菩萨行深般若波罗蜜多时照见五蕴皆空度一切苦厄舍利子色不异空空不异色色即是空空即是色受想行识亦复如是'
         '舍利子是诸法空相不生不灭不垢不净不增不减是故空中无色无受想行识无眼耳鼻舌身意无色声香味触法无眼界乃至无意识界'
         '无无明亦无无明尽乃至无老死亦无老死尽无苦集灭道无智亦无得以无所得故菩提萨埵依般若波罗蜜多故心无挂碍无挂碍故无有恐怖')


def paint_sutra(out):
    """经书（1024×1024）：
    上半 y 0..512：四本经折装的封面（每本 256×512：蓝、赭、青、黄绫，左上贴一张题签：金刚经、法华经、心经、药师经）；
    左下 512×512：摊开的经页（两页，竖排《心经》，每页 8 行 × 16 字，朱丝栏）；
    右下 512×256（y 512..768）：书口（一层层纸的侧边）；右下 y 776..1012：经案前后垂下来的黄绫（红边、石青回纹边、缠枝莲，横着接）。"""
    pad = Pad(1024, 1024, K['paper'])
    covers = [('金刚经', K['blue_dk'], K['blue']), ('法华经', hexc('#7a3b22'), hexc('#9b5232')), ('心　经', K['green_dk'], K['green']),
              ('药师经', K['yellow_dk'], K['yellow'])]
    for i, (title, dk, lt) in enumerate(covers):
        x0 = i * 256
        rect(pad, x0, 0, x0 + 256, 512, dk, mod=weave(1.6, 0.08, 30 + i))
        # 绫子上的暗花：小团花
        for gx in range(5):
            for gy in range(10):
                x = x0 + 28 + gx * 50 + (25 if gy % 2 else 0)
                y = 26 + gy * 50
                if x > x0 + 240:
                    continue
                for a in range(6):
                    ang = a * math.pi / 3
                    pad.put(pad.ellipse_mask(x + math.cos(ang) * 6, y + math.sin(ang) * 6, 4, 4), lt, alpha=0.45)
        # 题签
        rect(pad, x0 + 150, 34, x0 + 214, 330, K['paper'], mod=weave(1.5, 0.05, i))
        frame(pad, x0 + 154, 38, x0 + 210, 326, 2, K['red_dk'])
        for k, ch in enumerate(title):
            if ch == '　':
                continue
            t = pad.text_mask(ch, x0 + 182, 82 + k * 84, 50)
            pad.put(t, K['black'])
        # 包边
        frame(pad, x0, 0, x0 + 256, 512, 5, tint_arr(dk, -0.25))
    # 经页
    rect(pad, 0, 512, 512, 1024, K['paper'], mod=weave(1.2, 0.04, 40))
    for page in range(2):
        px0 = (1 - page) * 256          # 竖排从右往左读：第一页在右边
        frame(pad, px0 + 14, 530, px0 + 242, 1006, 2.2, K['red_dk'])
        rows, cols = 16, 8
        cw = (242 - 14) / cols
        for c in range(cols):
            x = px0 + 242 - cw * (c + 0.5)
            if c:
                pad.put(pad.line_mask([(x + cw / 2, 532), (x + cw / 2, 1004)], 1.0), K['red_dk'], alpha=0.7)
            for r in range(rows):
                idx = (page * cols + c) * rows + r
                if idx >= len(HEART):
                    break
                t = pad.text_mask(HEART[idx], x, 548 + r * 28.5, 22)
                pad.put(t, K['black'], alpha=0.92)
    pad.put(pad.line_mask([(256, 512), (256, 1024)], 3), K['paper_dk'])
    # 书口：一层层纸
    rect(pad, 512, 512, 1024, 768, K['paper'])
    for y in range(512, 768, 3):
        rect(pad, 512, y, 1024, y + 1, K['paper_dk'], alpha=0.6)
    # 经案前后垂下来的黄绫（512×236，一块 0.235 × 0.12 米，横着接 4 遍）：上沿一道红锦边、下沿一道石青边，各压一道金线；
    # 中间黄地上一条缠枝莲（粉莲、绿叶、金藤），下沿一排金穗头
    X0, Y0, X1, Y1 = 512, 776, 1024, 1012
    rect(pad, X0, 768, X1, 1024, K['yellow'], mod=weave(1.8, 0.07, 41))
    pad.clip = (X0, 768, X1, 1024)          # 卷草别画出界（左边是经页）；左右 128 的周期正好接得上
    scroll_vine(pad, X0 - 256, Y0 + 30, X1 + 256, Y1 - 36, 128, K['gold_dk'], K['green'], None, 3, 2.6, lotus=True)
    pad.clip = None
    rect(pad, X0, Y0, X1, Y0 + 24, K['red'], mod=weave(1.8, 0.07, 42))
    for x in range(X0, X1, 32):
        cloud(pad, x + 16, Y0 + 12, 7.5, K['red_lt'], K['gold'], K['red_dk'], 1, tail=False)
    rect(pad, X0, Y0 + 24, X1, Y0 + 28, K['gold'], mod=gold_mod(44))
    rect(pad, X0, Y1 - 34, X1, Y1 - 30, K['gold'], mod=gold_mod(45))
    rect(pad, X0, Y1 - 30, X1, Y1, K['blue'], mod=weave(1.8, 0.07, 43))
    meander(pad, X0, Y1 - 27, X1, 22, K['gold'], 2.4)
    rect(pad, X0, Y0 - 8, X1, Y0, K['gold'], mod=gold_mod(46))
    rect(pad, X0, Y1, X1, Y1 + 12, K['gold'], mod=gold_mod(47))
    return pad.save(os.path.join(out, 'paint_sutra.png'))


def tint_arr(c, dv):
    return np.clip(c * (1 + dv), 0, 1)


def paint_dais(out):
    """佛坛（须弥座）上的彩画（1024×512，横向首尾相接，可以一直铺）：
    上半 y 0..256：上枋——青地上金色缠枝莲（红、白莲花），上下各一道金线、一道白粉线；
    下半 y 256..512：束腰的地子——深绿地上金色卷草，配一排小金点（壸门之间的间柱也用这一条）。"""
    pad = Pad(1024, 512, K['blue_dk'])
    rect(pad, 0, 0, 1024, 256, K['blue'], mod=weave(2.2, 0.05, 50))
    # 缠枝莲：主藤是一条首尾相接的波浪（周期 256，正好 4 个），花在波谷波峰里
    scroll_vine(pad, -64, 30, 1088, 226, 256, K['gold'], K['green'], None, 7, 7, lotus=True)
    for (y, h, c) in ((0, 7, K['gold']), (7, 4, K['white']), (245, 4, K['white']), (249, 7, K['gold'])):
        rect(pad, 0, y, 1024, y + h, c, mod=gold_mod(y) if c is K['gold'] else None)
    # 下半：束腰
    rect(pad, 0, 256, 1024, 512, K['green_dk'], mod=weave(2.2, 0.05, 51))
    scroll_vine(pad, -64, 296, 1088, 476, 256, K['gold'], K['gold_dk'], K['gold_lt'], 9, 6)
    for (y, h, c) in ((256, 6, K['gold']), (262, 3, K['red']), (503, 3, K['red']), (506, 6, K['gold'])):
        rect(pad, 0, y, 1024, y + h, c, mod=gold_mod(y) if c is K['gold'] else None)
    beads(pad, 0, 1024, 283, 4, K['gold_lt'], 2.0)
    beads(pad, 0, 1024, 486, 4, K['gold_lt'], 2.0)
    return pad.save(os.path.join(out, 'paint_dais.png'))


def paint_lantern(out):
    """宫灯的灯片（6 张，每张 256×576，排成 1536×576；灯片实物 0.212 × 0.48 米，比例一样）：绢上画的莲花、梅枝小鸟、红团「福」字，
    四周一圈细边。hall_props.palace_lantern 的灯片（部件 paint_lantern）按这个贴；Unity 里材质 toon_paint_lantern，夜里要发光（见交接说明）"""
    H = 576
    pad = Pad(1536, H, K['white'])
    for i in range(6):
        x0 = i * 256
        pad.clip = (x0, 0, x0 + 256, H)                 # 每张灯片只画在自己那一格里
        rect(pad, x0, 0, x0 + 256, H, hexc('#fbefd2'), mod=weave(1.5, 0.03, 60 + i))
        cx = x0 + 128
        if i % 3 == 0:
            lotus_front(pad, cx, 380, 112)
            for k in range(3):
                cloud(pad, x0 + 52 + k * 76, 92 + (k % 2) * 34, 14, K['blue_pale'], K['blue_lt'], K['blue'], 1 if k % 2 else -1, tail=False)
            # 水波：几道淡蓝的弧
            for k in range(3):
                pts = [(x0 + 24 + t * 208, 520 + k * 14 + 5 * math.sin(t * 9 + k)) for t in [q / 30 for q in range(31)]]
                pad.put(pad.line_mask(pts, 2.2), K['blue_lt'], alpha=0.7)
        elif i % 3 == 1:
            # 梅枝 + 小鸟
            pts = [(x0 + 30, 500), (x0 + 90, 400), (x0 + 120, 300), (x0 + 190, 210), (x0 + 230, 180)]
            pad.put(pad.taper_mask(pts, 11, 3), hexc('#5b3a28'))
            pad.put(pad.taper_mask([(x0 + 110, 322), (x0 + 80, 225), (x0 + 66, 150)], 6.5, 2), hexc('#5b3a28'))
            pad.put(pad.taper_mask([(x0 + 150, 262), (x0 + 205, 300), (x0 + 228, 340)], 5.5, 2), hexc('#5b3a28'))
            rng = random.Random(i)
            for k in range(18):
                t = rng.random()
                p = pts[min(4, int(t * 4))]
                fx, fy = p[0] + rng.uniform(-24, 24), p[1] + rng.uniform(-26, 22)
                for a in range(5):
                    ang = 2 * math.pi * a / 5 + t
                    pad.put(pad.ellipse_mask(fx + math.cos(ang) * 6.5, fy + math.sin(ang) * 6.5, 6, 6), K['pink'])
                pad.put(pad.ellipse_mask(fx, fy, 3.2, 3.2), K['yellow'])
            # 小鸟：身子、头、喙、翅、尾
            bx, by = x0 + 168, 228
            pad.put(pad.ellipse_mask(bx, by, 22, 14), K['blue_lt'])
            pad.put(pad.ellipse_mask(bx + 4, by + 5, 15, 8), K['white'])
            pad.put(pad.ellipse_mask(bx + 18, by - 10, 11, 11), K['blue'])
            pad.put(pad.ellipse_mask(bx + 21, by - 12, 2.5, 2.5), K['ink'])
            pad.put(pad.poly_mask([(bx + 28, by - 11), (bx + 39, by - 8), (bx + 28, by - 6)]), K['orange'])
            pad.put(pad.poly_mask([(bx - 4, by - 6), (bx - 26, by + 2), (bx - 6, by + 4)]), K['blue_dk'])
            pad.put(pad.poly_mask([(bx - 18, by + 2), (bx - 46, by + 16), (bx - 40, by + 22), (bx - 14, by + 8)]), K['blue_dk'])
        else:
            t = pad.text_mask('福', cx, 262, 158, stroke=2)
            pad.put(pad.ellipse_mask(cx, 262, 104, 116), K['red_lt'], alpha=0.85)
            ring_o = pad.ellipse_mask(cx, 262, 110, 122)
            pad.put(ring_o, K['gold'], alpha=0.0)
            pad.put(Pad.grow(t, 2), K['gold_dk'])
            pad.put(t, K['gold_lt'])
            for k in range(4):
                a = math.pi / 4 + k * math.pi / 2
                cloud(pad, cx + math.cos(a) * 112, 262 + math.sin(a) * 168, 13, K['red_lt'], K['gold'], K['red_dk'], 1 if k % 2 else -1, tail=False)
            # 上下两道回纹
            meander(pad, x0 + 22, 30, x0 + 234, 20, K['red_dk'], 2.4)
            meander(pad, x0 + 22, 524, x0 + 234, 20, K['red_dk'], 2.4)
        frame(pad, x0, 0, x0 + 256, H, 7, K['red_dk'])
        frame(pad, x0 + 11, 11, x0 + 245, H - 11, 2, K['gold_dk'])
    pad.clip = None
    return pad.save(os.path.join(out, 'paint_lantern.png'))


def paint_enamel(out):
    """景泰蓝（掐丝珐琅，512×512，上下左右都能接着铺）：松石蓝的釉地（有细小的砂眼、深浅不匀），金丝勾的缠枝莲——
    两行波浪形的主藤（上下两行错开半个波），波峰波谷开一朵俯视的莲花（红、粉、黄、白几种釉色），藤上分出卷须和金边的绿叶。
    花觚这些铜胎珐琅的器物用（hall_props.py 里按圆柱展开贴）。"""
    pad = Pad(512, 512, hexc('#2c8aa8'))
    rng = np.random.default_rng(70)
    pits = rng.random((64, 64)).astype(np.float32)

    def ground(x, y):
        i = (np.floor(y / 2) % 64).astype(int)
        j = (np.floor(x / 2) % 64).astype(int)
        return (1.0 + 0.05 * np.sin(x * 2 * math.pi / 128 + np.sin(y * 2 * math.pi / 256) * 2) * np.sin(y * 2 * math.pi / 128)
                + 0.035 * (pits[i, j] - 0.5))
    rect(pad, 0, 0, 512, 512, hexc('#2c8aa8'), mod=ground)
    pals = [[(K['red'], K['pink_lt']), (K['red_lt'], K['white'])], [(K['yellow_dk'], K['yellow_lt']), (K['orange'], K['white'])],
            [(K['pink_dk'], K['pink_pale']), (K['white'], K['white'])], [(K['purple'], K['purple_lt']), (K['pink'], K['white'])]]
    gold = K['gold']
    wire = 3.2
    for row in range(2):
        cy = 128 + row * 256
        ph = row * math.pi

        def wy(x, cy=cy, ph=ph):
            return cy + 62 * math.sin(2 * math.pi * x / 256 + ph)
        for dy in (-512, 0, 512):
            pts = [(x, wy(x) + dy) for x in range(-140, 660, 3)]
            pad.put(pad.line_mask(pts, wire), gold)
        for k in range(-1, 6):
            x = 64 + k * 128
            sg = 1 if (k + row) % 2 == 0 else -1
            y = wy(x)
            for dy in (-512, 0, 512):
                for dx in (0,):
                    fx, fy = x + dx, y + dy
                    if fy < -110 or fy > 622 or fx < -110 or fx > 622:
                        continue
                    # 卷须：从藤上往外卷
                    sp = spiral_pts(fx + 34, fy + sg * 40, 26, 1.1, math.pi * (1.3 if sg > 0 else 0.7), sg, 30, 0.75)
                    pad.put(pad.taper_mask([(fx + 10, fy + sg * 6)] + sp, wire * 1.1, wire * 0.5), gold)
                    # 两片叶（金边绿釉）
                    for (la, ll) in ((math.pi * (0.25 if sg > 0 else 0.75), 40), (math.pi * (1.75 if sg > 0 else 1.25), 34)):
                        pts2 = petal_pts((fx - 22, fy), la, ll, 18, n=16, tip=0.3 * sg, base_w=0.15)
                        mm = pad.poly_mask(pts2)
                        pad.put(Pad.grow(mm, 1.4), gold)
                        pad.put(mm, banded(K['green_dk'], K['green_lt'], lambda xx, yy, lx=fx - 22, ly=fy: np.hypot(xx - lx, yy - ly) / 40, 3))
                    # 花：在波峰波谷外侧
                    pal = pals[(k + 2 * row) % len(pals)]
                    lotus_top(pad, fx + 2, fy - sg * 54, 36, rings=3, n=7, pal=pal, outline=gold)
                    # 空当里几个小金丝卷、白釉小点
                    for (ox, oy, rr) in ((64, -58, 13), (-50, 70, 11), (60, 64, 9)):
                        sp2 = spiral_pts(fx + ox, fy - sg * oy, rr, 1.2, 0.0, 1, 20, 0.6)
                        pad.put(pad.taper_mask(sp2, wire * 0.9, wire * 0.5), gold)
                    for (ox, oy) in ((-40, -40), (30, 92), (92, 20)):
                        m_ = pad.ellipse_mask(fx + ox, fy - sg * oy, 4.5, 4.5)
                        pad.put(Pad.grow(m_, 1.2), gold)
                        pad.put(m_, K['white'])
    return pad.save(os.path.join(out, 'paint_enamel.png'))


ALL = {'frontal': paint_frontal, 'brocade': paint_brocade, 'banner': paint_banner, 'sutra': paint_sutra, 'dais': paint_dais,
       'lantern': paint_lantern, 'enamel': paint_enamel}


def main():
    args = sys.argv[1:]
    out = OUT_DEFAULT
    if args and (os.sep in args[0] or args[0].startswith('.')):
        out = args.pop(0)
    os.makedirs(out, exist_ok=True)
    names = args or list(ALL)
    ims = []
    for n in names:
        im = ALL[n](out)
        print(f'[paint] paint_{n}.png {im.size[0]}×{im.size[1]}')
        ims.append(im)
    # 给人看的拼图
    th = 640
    row = [im.resize((max(1, int(im.width * th / im.height)), th)) for im in ims]
    sheet = Image.new('RGB', (sum(r.width for r in row) + 8 * len(row), th), (40, 40, 40))
    x = 0
    for r in row:
        sheet.paste(r, (x, 0))
        x += r.width + 8
    sheet.save(os.path.join(out, '_paint_sheet.png'))


if __name__ == '__main__':
    main()
