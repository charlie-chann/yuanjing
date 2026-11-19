"""大殿的壁画（2026-11-18，评审第三轮：「大片空的米色底、几座渐变的山、心形叶子的菩提树、叶子身子点个头的飞天——像矢量剪贴画」）。

照北京法海寺明代壁画那一路「重彩」画：暗沉的石绿、赭褐的底子上满铺祥云和山石，人物一组一组地画满画面：
  - 十八罗汉：每幅三位，坐在山石上，各拿各的法器（锡杖、钵、经卷、蒲扇、念珠、小塔），有的身边伏着虎、云里探出龙，旁边侍立小沙弥；
  - 诸天礼佛：一行四五位天人踏着祥云走向佛前，宝冠、头光、璎珞、长长的飘带，手里捧香炉、莲花、花盘、幢幡；
  - 说法图、净土莲池、飞天散花各一幅。
画法：墨线勾边（粗细有变化）、平涂再退晕、头光、宝冠、璎珞、法器上用「沥粉贴金」（一道暗金托底、一道亮金压在上面，像凸起来的金线）；
最后整幅刷一层旧色（偏暖、略暗），加淡淡的水渍、细的龟裂纹。

每面墙的每一间各一幅，不重复（东墙三间、西墙三间、后墙五间，共 11 幅，多画一幅备用）：painted.py 的 atlas('wall') 调 mural2(w, h, i)。
"""
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import painted as P
from painted import K, Canvas, bez, arc, spiral, mix, mountain, cloud_head, pine, rock, lotus_side, lotus_leaf, crane, bamboo, falling_flowers, seated_buddha, SKIN, SKIN_DK

GOLD, GOLD_LT, GOLD_DK = K['gold'], K['gold_lt'], K['gold_dk']
INK = K['ink']
BG_GREEN = (52, 74, 62)
BG_BROWN = (88, 66, 46)
BG_BLUE = (36, 58, 78)


def gold_line(c, pts, w=2.0):
    """沥粉贴金：一道暗金托底、一道亮金压在上面偏左上半个像素（看着是凸起来的金线）"""
    c.line(pts, GOLD_DK, w + 1.2)
    c.line([(x - 0.45, y - 0.45) for (x, y) in pts], GOLD, w * 0.75)
    c.line([(x - 0.7, y - 0.7) for (x, y) in pts], GOLD_LT, max(0.6, w * 0.3))


def gold_ring(c, cx, cy, r, w=2.2):
    gold_line(c, arc(cx, cy, r, 0, 2 * math.pi, 64), w)


def gold_dot(c, x, y, r):
    c.circle(x, y, r + 0.8, fill=GOLD_DK)
    c.circle(x - r * 0.15, y - r * 0.15, r, fill=GOLD)
    c.circle(x - r * 0.35, y - r * 0.35, r * 0.4, fill=GOLD_LT)


def ribbon(c, pts, width, col, edge=INK):
    """飘带：一条宽窄变化的长带（中间宽、两头尖），墨线勾边，中间一道亮线"""
    n = len(pts)
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a = pts[min(i + 1, n - 1)]
        b = pts[max(i - 1, 0)]
        tx, ty = a[0] - b[0], a[1] - b[1]
        l = math.hypot(tx, ty) or 1
        nx, ny = -ty / l, tx / l
        t = i / (n - 1)
        wv = width * (0.35 + 0.65 * math.sin(math.pi * min(1, 0.1 + t)) ** 0.7) * (1 + 0.25 * math.sin(t * 9))
        left.append((x + nx * wv / 2, y + ny * wv / 2))
        right.append((x - nx * wv / 2, y - ny * wv / 2))
    poly = left + right[::-1]
    c.poly(poly, fill=col, outline=edge, width=1.1)
    c.line(pts[2:-3], mix(col, (255, 255, 255), 0.45), max(0.8, width * 0.12))


def cloud_puff(c, x, y, s, col=(236, 232, 214), shade=(150, 170, 176), line=GOLD_DK, n=4, seed=0, gold=True):
    """祥云：几个卷头的云团（白里透青、金线勾），后面拖一条云尾"""
    rng = random.Random(seed)
    heads = [(x + (i - (n - 1) / 2) * s * 0.9 + rng.uniform(-0.15, 0.15) * s, y + rng.uniform(-0.25, 0.25) * s, s * rng.uniform(0.45, 0.62)) for i in range(n)]
    for (hx, hy, r) in heads:
        c.circle(hx, hy, r + 1.5, fill=shade)
    for (hx, hy, r) in heads:
        c.circle(hx, hy - r * 0.08, r * 0.9, fill=col)
        sp = spiral(hx, hy, r * 0.1, r * 0.72, -math.pi / 2, 1.1, 36)
        if gold:
            gold_line(c, sp, 1.2)
        else:
            c.line(sp, shade, 1.2)
    tail = bez((heads[-1][0], heads[-1][1] + s * 0.2), (heads[-1][0] + s * 1.0, heads[-1][1] + s * 0.6),
               (heads[-1][0] + s * 1.6, heads[-1][1] - s * 0.3), (heads[-1][0] + s * 2.4, heads[-1][1] + s * 0.05), 30)
    c.line(tail, shade, s * 0.22)
    c.line(tail, col, s * 0.13)


def background(c, w, h, seed, base=BG_GREEN, sky=None):
    """暗沉的底子：上浅下深的退晕，满铺淡淡的大朵云纹、零星的散花"""
    rng = random.Random(seed)
    sky = sky or mix(base, (210, 196, 160), 0.25)
    a = np.zeros((c.im.size[1], c.im.size[0], 3), np.float32)
    yy = np.linspace(0, 1, a.shape[0])[:, None]
    for k in range(3):
        a[..., k] = sky[k] * (1 - yy) + base[k] * yy
    n = np.random.default_rng(seed).normal(0, 1, (a.shape[0] // 24 + 2, a.shape[1] // 24 + 2)).astype(np.float32)
    n = np.asarray(Image.fromarray(n, mode='F').resize((a.shape[1], a.shape[0]), Image.BICUBIC))
    a *= (1 + 0.05 * n)[..., None]
    c.im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    c.d = ImageDraw.Draw(c.im)
    # 淡的大云纹（底子上的暗花）
    for _ in range(9):
        x, y, s = rng.uniform(0, w), rng.uniform(0, h * 0.75), rng.uniform(w * 0.06, w * 0.11)
        for j in range(3):
            c.line(spiral(x + j * s * 0.9, y, s * 0.1, s * 0.55, rng.uniform(0, 6), 1.2, 40), mix(base, sky, 0.6), 2.4)


def ground(c, w, h, y0, seed, col=K['green_dk'], col2=K['green']):
    """近处的地：一层层的坡（石绿、赭石），坡上小草、小花、几块石头"""
    rng = random.Random(seed)
    for k in range(3):
        yb = y0 + (h - y0) * k / 3
        pts = [(x, yb + 8 * math.sin(x * 0.02 + k + seed) + 5 * math.sin(x * 0.07 + seed)) for x in np.linspace(-10, w + 10, 60)]
        c.poly(pts + [(w + 10, h + 10), (-10, h + 10)], fill=mix(col, col2, 0.35 * k), outline=mix(col, INK, 0.4), width=1.2)
        gl = [(x, y + 3) for (x, y) in pts]
        c.line(gl, mix(col2, GOLD, 0.3), 1.0)
    for _ in range(int(w * 0.25)):
        x, y = rng.uniform(0, w), rng.uniform(y0 + 6, h - 2)
        c.line([(x, y), (x + rng.uniform(-3, 3), y - rng.uniform(4, 9))], mix(col2, K['green_lt'], 0.5), 1.0)
    for _ in range(int(w * 0.05)):
        x, y = rng.uniform(0, w), rng.uniform(y0 + 6, h - 4)
        cc = rng.choice([K['pink'], K['white'], K['yellow'], K['red_lt']])
        for j in range(5):
            a = j * 2 * math.pi / 5
            c.circle(x + math.cos(a) * 2.2, y + math.sin(a) * 2.2, 1.8, fill=cc)
        c.circle(x, y, 1.2, fill=GOLD)


def big_rock(c, x, y, s, seed, col=K['blue'], col2=K['green']):
    """太湖石一样的山石：几块叠起来，石青退晕到石绿，墨线勾、披麻皴，顶上描金"""
    rng = random.Random(seed)
    for k in range(4):
        cx, cy = x + rng.uniform(-0.5, 0.5) * s, y - rng.uniform(0.0, 0.6) * s
        r = s * rng.uniform(0.35, 0.6)
        pts = []
        for j in range(14):
            a = math.pi + j * math.pi / 13
            rr = r * rng.uniform(0.75, 1.05)
            pts.append((cx + math.cos(a) * rr * 1.25, cy + math.sin(a) * rr * 0.95))
        pts.append((cx + r * 1.2, cy + r * 0.3))
        pts.append((cx - r * 1.2, cy + r * 0.3))
        c.poly(pts, fill=mix(col, col2, k / 3), outline=INK, width=1.6)
        for j in range(5):
            px, py = cx + rng.uniform(-0.8, 0.8) * r, cy - rng.uniform(0.0, 0.7) * r
            c.line([(px, py), (px + rng.uniform(-0.2, 0.2) * r, py + rng.uniform(0.25, 0.45) * r)], mix(col, INK, 0.5), 1.2)
        gold_line(c, pts[2:9], 1.0)


def halo(c, x, y, r, fill=None):
    if fill is not None:
        c.circle(x, y, r, fill=fill)
    gold_ring(c, x, y, r, 2.4)
    gold_ring(c, x, y, r * 0.86, 1.2)
    for k in range(16):
        a = 2 * math.pi * k / 16
        gold_dot(c, x + math.cos(a) * r * 0.93, y + math.sin(a) * r * 0.93, 1.3)


def face(c, x, y, s, facing=1, kind='deva', oval=True):
    """一张 3/4 侧的脸：x, y 是脸的中心，s 是脸高；oval=False 不画脸的轮廓（罗汉：头和脸是一个大光头）"""
    sg = facing
    if oval:
        c.ellipse(x, y, s * 0.4, s * 0.5, fill=SKIN, outline=SKIN_DK, width=1.1)
    # 耳（带耳珰）
    c.ellipse(x - sg * s * 0.36, y + s * 0.02, s * 0.09, s * 0.16, fill=SKIN, outline=SKIN_DK, width=0.9)
    if kind == 'deva':
        gold_dot(c, x - sg * s * 0.37, y + s * 0.22, s * 0.05)
    # 眉、眼、鼻、嘴
    for (ex, w_) in ((0.08, 0.13), (0.26, 0.1)):
        ex_ = x + sg * s * ex
        c.line([(ex_ - w_ * s, y - s * 0.12), (ex_ + w_ * s, y - s * 0.14)], INK if kind != 'arhat' else (240, 240, 235), 1.1 if kind != 'arhat' else 1.8)
        c.line([(ex_ - w_ * s * 0.8, y - s * 0.02), (ex_ + w_ * s * 0.8, y - s * 0.03)], INK, 1.0)
    c.line([(x + sg * s * 0.2, y - s * 0.02), (x + sg * s * 0.26, y + s * 0.14), (x + sg * s * 0.18, y + s * 0.16)], SKIN_DK, 0.9)
    c.ellipse(x + sg * s * 0.16, y + s * 0.3, s * 0.07, s * 0.03, fill=K['red'])
    if kind == 'deva':
        c.circle(x + sg * s * 0.16, y - s * 0.22, s * 0.025, fill=K['red'])


def deva(c, x, y, s, seed, facing=1, robe=K['red'], robe2=K['green'], scarf=K['blue_lt'], hold='lotus'):
    """诸天（站着的天人，3/4 侧往 facing 那边走）：y 是脚下，s 是脚到冠顶的高"""
    rng = random.Random(seed)
    sg = facing

    def Q(u, v):
        return (x + sg * u * s, y - v * s)
    # 飘带：从两肩绕出来往身后、往下飘成两道 S 形
    for (k, col) in ((0, scarf), (1, mix(robe, K['pink'], 0.4))):
        p0 = Q(-0.06 + 0.12 * k, 0.74)
        pts = bez(p0, Q(-0.45 - 0.2 * k, 0.86 - 0.3 * k), Q(-0.25 - 0.3 * k, 0.25), Q(-0.7 - 0.25 * k, 0.05 + 0.2 * k), 40)
        ribbon(c, pts, s * 0.035, col)
    # 下裳：长裙到脚面，往后飘一点
    skirt = [Q(-0.1, 0.5), Q(0.1, 0.5), Q(0.16, 0.04), Q(0.06, 0.0), Q(-0.12, 0.0), Q(-0.22, 0.06)]
    c.poly(skirt, fill=robe, outline=INK, width=1.4)
    for k in range(4):
        c.line(bez(Q(-0.08 + k * 0.05, 0.48), Q(-0.08 + k * 0.05, 0.3), Q(-0.12 + k * 0.055, 0.16), Q(-0.15 + k * 0.06, 0.02), 12), mix(robe, INK, 0.45), 1.0)
    gold_line(c, [Q(-0.22, 0.06), Q(-0.12, 0.0), Q(0.06, 0.0), Q(0.16, 0.04)], 1.4)
    # 鞋尖
    c.ellipse(*Q(0.12, 0.0), s * 0.03, s * 0.012, fill=K['red_dk'], outline=INK, width=0.8)
    # 上衣、长袖（宽大的袖子垂到膝上）
    body = [Q(-0.1, 0.76), Q(0.1, 0.76), Q(0.13, 0.48), Q(-0.12, 0.48)]
    c.poly(body, fill=robe2, outline=INK, width=1.3)
    for sd in (-1, 1):
        sl = [Q(0.02 + sd * 0.1, 0.74), Q(0.06 + sd * 0.17, 0.6), Q(0.1 + sd * 0.17, 0.36), Q(0.02 + sd * 0.1, 0.33), Q(0.0 + sd * 0.07, 0.55)]
        c.poly(sl, fill=mix(robe2, robe, 0.35 if sd > 0 else 0.1), outline=INK, width=1.2)
        gold_line(c, [Q(0.1 + sd * 0.17, 0.36), Q(0.02 + sd * 0.1, 0.33)], 1.2)
    # 腰带、披巾在胸前一道弧
    c.line([Q(-0.12, 0.5), Q(0.13, 0.5)], K['red_dk'], s * 0.018)
    gold_line(c, [Q(-0.12, 0.505), Q(0.13, 0.505)], 0.9)
    c.line(bez(Q(-0.1, 0.74), Q(-0.05, 0.62), Q(0.06, 0.62), Q(0.11, 0.74), 16), scarf, s * 0.02)
    # 璎珞：胸前一串金珠，中间垂一颗宝石
    for k in range(9):
        t = k / 8
        px, py = Q(-0.08 + 0.17 * t, 0.71 - 0.06 * math.sin(math.pi * t))
        gold_dot(c, px, py, s * 0.007)
    c.circle(*Q(0.005, 0.64), s * 0.012, fill=K['green'], outline=GOLD_DK, width=1.0)
    # 手、拿着的东西（两手在胸前）
    hx, hy = Q(0.13, 0.6)
    c.ellipse(hx, hy, s * 0.025, s * 0.02, fill=SKIN, outline=SKIN_DK, width=0.9)
    c.ellipse(hx - sg * s * 0.03, hy + s * 0.012, s * 0.022, s * 0.018, fill=SKIN, outline=SKIN_DK, width=0.9)
    if hold == 'lotus':
        c.line([Q(0.14, 0.6), Q(0.18, 0.74), Q(0.2, 0.86)], K['green_dk'], 2.0)
        lotus_side(c, *Q(0.2, 0.88), s * 0.05, 0.8, stem=0)
    elif hold == 'censer':
        cx, cy = Q(0.2, 0.62)
        c.line([Q(0.14, 0.6), Q(0.2, 0.6)], GOLD_DK, 1.6)
        c.ellipse(cx, cy, s * 0.04, s * 0.02, fill=GOLD, outline=GOLD_DK, width=1.0)
        c.poly([(cx - s * 0.04, cy), (cx + s * 0.04, cy), (cx + s * 0.025, cy + s * 0.04), (cx - s * 0.025, cy + s * 0.04)], fill=GOLD, outline=GOLD_DK, width=1.0)
        for k in range(3):
            sm = bez((cx + (k - 1) * s * 0.012, cy - s * 0.01), (cx + (k - 1) * s * 0.02 - s * 0.03, cy - s * 0.1), (cx + s * 0.04, cy - s * 0.16), (cx - s * 0.01 + k * s * 0.01, cy - s * 0.25), 20)
            c.line(sm, (232, 230, 220), 1.4)
    elif hold == 'plate':
        cx, cy = Q(0.2, 0.66)
        c.ellipse(cx, cy, s * 0.07, s * 0.018, fill=GOLD, outline=GOLD_DK, width=1.0)
        for k in range(5):
            c.circle(cx + (k - 2) * s * 0.022, cy - s * 0.02 - (k % 2) * s * 0.012, s * 0.015, fill=rng.choice([K['pink'], K['red_lt'], K['yellow'], K['white']]), outline=K['pink_dk'], width=0.7)
    elif hold == 'banner':
        px0, py0 = Q(0.16, 0.0)
        px1, py1 = Q(0.2, 1.25)
        c.line([(px0, py0), (px1, py1)], K['brown_dk'], 2.2)
        gold_dot(c, px1, py1, s * 0.012)
        bw = s * 0.07
        ban = [(px1 - bw * 0.2, py1 + s * 0.03), (px1 + bw * 0.9, py1 + s * 0.03), (px1 + bw * 0.9, py1 + s * 0.42), (px1 + bw * 0.35, py1 + s * 0.48), (px1 - bw * 0.2, py1 + s * 0.42)]
        c.poly(ban, fill=mix(robe, K['yellow'], 0.3), outline=INK, width=1.0)
        for k in range(3):
            gold_line(c, [(px1 - bw * 0.2, py1 + s * (0.1 + 0.11 * k)), (px1 + bw * 0.9, py1 + s * (0.1 + 0.11 * k))], 0.9)
    elif hold == 'ruyi':
        c.line([Q(0.1, 0.56), Q(0.24, 0.8)], GOLD_DK, 2.6)
        cloud_head(c, *Q(0.25, 0.82), s * 0.03, GOLD, GOLD_DK, GOLD_LT)
    # 头：头光、高髻、宝冠、脸
    hxc, hyc = Q(0.02, 0.85)
    halo(c, hxc, hyc, s * 0.115)
    c.ellipse(hxc - sg * s * 0.015, hyc - s * 0.035, s * 0.055, s * 0.06, fill=INK)
    face(c, hxc + sg * s * 0.01, hyc + s * 0.01, s * 0.1, sg)
    # 宝冠：三片金叶、中间一颗宝石，两边垂缯带
    for k, (dx, hgt) in enumerate(((-0.04, 0.05), (0.0, 0.07), (0.04, 0.05))):
        bx, by = hxc + sg * dx * s, hyc - s * 0.05
        c.poly([(bx - s * 0.022, by), (bx + s * 0.022, by), (bx, by - hgt * s)], fill=GOLD, outline=GOLD_DK, width=1.0)
    c.circle(hxc, hyc - s * 0.08, s * 0.011, fill=K['red'], outline=GOLD_DK, width=0.8)
    for sd in (-1, 1):
        c.line(bez((hxc + sd * s * 0.05, hyc - s * 0.04), (hxc + sd * s * 0.09, hyc), (hxc + sd * s * 0.06, hyc + s * 0.06), (hxc + sd * s * 0.1, hyc + s * 0.12), 14), K['red_lt'], 1.6)


def smooth(pts, n=10, closed=True):
    """Catmull-Rom：控制点连成一条顺的曲线（闭合的轮廓、或者一笔）"""
    out = []
    m = len(pts)
    rng_ = range(m) if closed else range(m - 1)
    for i in rng_:
        p0 = pts[(i - 1) % m] if closed or i > 0 else pts[0]
        p1 = pts[i]
        p2 = pts[(i + 1) % m]
        p3 = pts[(i + 2) % m] if closed or i + 2 < m else pts[-1]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    if not closed:
        out.append(pts[-1])
    return out


def shape(c, pts, fill, outline=INK, width=1.4, n=10):
    sm = smooth(pts, n)
    c.poly(sm, fill=fill, outline=outline, width=width)
    return sm


def pine2(c, x, y, h, seed, facing=1):
    """松：一棵斜着长的老松，树皮一片片的鳞，枝头一簇簇扇形的松针（深绿托底、一根根浅绿的针）"""
    rng = random.Random(seed)
    sg = facing
    trunk = bez((x, y), (x + sg * h * 0.12, y - h * 0.3), (x - sg * h * 0.1, y - h * 0.62), (x + sg * h * 0.08, y - h * 0.95), 30)
    c.line(trunk, K['brown_dk'], h * 0.075)
    c.line(trunk, K['brown'], h * 0.05)
    for k in range(0, len(trunk) - 2, 2):
        px, py = trunk[k]
        c.ellipse(px + rng.uniform(-1, 1) * h * 0.012, py, h * 0.016, h * 0.009, outline=K['brown_dk'], width=1.0)
    for k in range(6):
        t = 0.3 + k * 0.12
        bx, by = trunk[int(t * (len(trunk) - 1))]
        sd = -1 if k % 2 else 1
        ex, ey = bx + sd * h * rng.uniform(0.22, 0.36), by - h * rng.uniform(0.0, 0.08)
        c.line([(bx, by), ((bx + ex) / 2, by - h * 0.04), (ex, ey)], K['brown_dk'], h * 0.022)
        for j in range(3):
            cx, cy = ex + rng.uniform(-0.6, 0.6) * h * 0.08, ey - rng.uniform(0.0, 0.05) * h
            r = h * rng.uniform(0.075, 0.1)
            c.ellipse(cx, cy, r * 1.1, r * 0.55, fill=K['green_deep'])
            for q in range(15):
                a = math.pi + q * math.pi / 14
                c.line([(cx, cy + r * 0.2), (cx + math.cos(a) * r * 1.05, cy + r * 0.2 + math.sin(a) * r * 0.62)], mix(K['green'], K['green_lt'], rng.random() * 0.6), 1.0)


def arhat(c, x, y, s, seed, attr='staff', robe=K['ochre'], band=K['red_dk'], facing=1):
    """罗汉：坐在山石上（一腿盘、一腿垂下来），光头、白长眉、皱纹，内衣石绿，袈裟斜披、田相格描金，手里各有法器。
    y 是石头底，s 是坐着的人高（石头底到头顶）"""
    rng = random.Random(seed)
    sg = facing

    def Q(u, v):
        return (x + sg * u * s, y - v * s)
    # 山石座：比人宽，浅一点（石青、石绿），墨线、描金
    big_rock(c, x - sg * s * 0.02, y, s * 0.36, seed, col=K['blue_lt'], col2=K['green'])
    inner = K['green_dk'] if robe != K['green'] else K['blue_dk']
    halo(c, *Q(-0.02, 0.86), s * 0.15)
    # 垂下来的那条腿（裤管、脚、草鞋）
    shape(c, [Q(0.13, 0.33), Q(0.29, 0.31), Q(0.27, 0.12), Q(0.23, 0.05), Q(0.15, 0.06), Q(0.14, 0.2)], inner)
    c.ellipse(*Q(0.2, 0.035), s * 0.065, s * 0.026, fill=SKIN, outline=SKIN_DK, width=0.9)
    c.line([Q(0.15, 0.03), Q(0.26, 0.03)], K['brown_dk'], 1.6)
    # 盘着的腿（膝盖往外，下摆铺在石头上）
    lap = shape(c, [Q(-0.34, 0.27), Q(-0.33, 0.37), Q(-0.12, 0.43), Q(0.14, 0.42), Q(0.3, 0.36), Q(0.28, 0.27), Q(0.06, 0.24), Q(-0.18, 0.23)], inner)
    for k in range(4):
        c.line(smooth([Q(-0.28 + k * 0.12, 0.27), Q(-0.24 + k * 0.12, 0.33), Q(-0.18 + k * 0.12, 0.38)], 6, False), mix(inner, INK, 0.45), 1.0)
    gold_line(c, smooth([Q(-0.34, 0.27), Q(-0.1, 0.235), Q(0.28, 0.27)], 8, False), 1.1)
    # 身子：圆的肩、略往前探
    body = [Q(-0.21, 0.42), Q(-0.24, 0.55), Q(-0.18, 0.68), Q(-0.06, 0.74), Q(0.08, 0.74), Q(0.18, 0.68), Q(0.22, 0.55), Q(0.19, 0.42)]
    shape(c, body, robe)
    # 内衣：右胸露出来一角
    shape(c, [Q(0.02, 0.73), Q(0.12, 0.72), Q(0.08, 0.58)], inner, width=1.0)
    # 袈裟：从左肩斜到右胁，田相格（金线）、金边
    kas = [Q(-0.2, 0.67), Q(-0.06, 0.745), Q(0.05, 0.73), Q(0.21, 0.5), Q(0.2, 0.42), Q(0.0, 0.42), Q(-0.22, 0.45)]
    sm = shape(c, kas, band, width=1.2)
    for k in range(1, 5):
        t = k / 5
        a_, b_ = Q(-0.2 + 0.36 * t, 0.67 - 0.25 * t), Q(-0.06 + 0.27 * t, 0.745 - 0.245 * t)
        gold_line(c, [a_, b_], 0.8)
    for k in range(1, 3):
        t = k / 3
        gold_line(c, [Q(-0.2 + 0.02 * t, 0.67 - 0.2 * t), Q(0.05 + 0.15 * t, 0.73 - 0.28 * t)], 0.8)
    gold_line(c, sm[: len(sm) // 2], 1.3)
    # 两只袖子：右手抬起拿法器，左手搭在膝上
    shape(c, [Q(0.14, 0.7), Q(0.25, 0.62), Q(0.3, 0.5), Q(0.22, 0.47), Q(0.15, 0.56)], mix(robe, INK, 0.12), width=1.2)
    shape(c, [Q(-0.17, 0.68), Q(-0.26, 0.56), Q(-0.3, 0.42), Q(-0.2, 0.4), Q(-0.16, 0.54)], mix(robe, INK, 0.12), width=1.2)
    hand_r, hand_l = Q(0.26, 0.48), Q(-0.25, 0.39)
    # 法器
    if attr == 'staff':
        c.line([Q(0.34, -0.02), Q(0.27, 1.08)], K['brown_dk'], s * 0.022)
        sx, sy = Q(0.27, 1.14)
        gold_ring(c, sx, sy, s * 0.06, 1.8)
        for k in range(4):
            gold_ring(c, sx - s * 0.05 + k * s * 0.033, sy + s * 0.05, s * 0.016, 1.0)
        hand_r = Q(0.3, 0.5)
    elif attr == 'bowl':
        bx, by = Q(0.02, 0.45)
        c.d.pieslice(((bx - s * 0.09) * P.SS, (by - s * 0.07) * P.SS, (bx + s * 0.09) * P.SS, (by + s * 0.07) * P.SS), 0, 180, fill=(40, 36, 40))
        c.ellipse(bx, by, s * 0.09, s * 0.03, fill=(28, 26, 30), outline=GOLD_DK, width=1.2)
        gold_line(c, arc(bx, by, s * 0.09, 0, math.pi, 20), 1.0)
        c.line(bez((bx, by - s * 0.02), (bx - s * 0.1, by - s * 0.2), (bx + s * 0.12, by - s * 0.3), (bx + s * 0.02, by - s * 0.48), 24), (220, 228, 224), 2.4)
        hand_r, hand_l = Q(0.1, 0.43), Q(-0.07, 0.43)
    elif attr == 'scroll':
        a_, b_ = Q(-0.06, 0.52), Q(0.24, 0.58)
        c.poly([a_, b_, (b_[0], b_[1] + s * 0.11), (a_[0], a_[1] + s * 0.11)], fill=(240, 232, 205), outline=INK, width=1.0)
        for k in range(6):
            t = (k + 0.5) / 6
            px = a_[0] + (b_[0] - a_[0]) * t
            c.line([(px, a_[1] + (b_[1] - a_[1]) * t + s * 0.02), (px, a_[1] + (b_[1] - a_[1]) * t + s * 0.09)], INK, 0.8)
        hand_r, hand_l = b_, a_
    elif attr == 'fan':
        fx_, fy_ = Q(0.32, 0.72)
        c.line([Q(0.26, 0.5), (fx_, fy_)], K['brown_dk'], 2.0)
        c.ellipse(fx_, fy_ - s * 0.06, s * 0.075, s * 0.095, fill=(206, 184, 120), outline=INK, width=1.1)
        for k in range(9):
            a = -math.pi / 2 + (k - 4) * 0.2
            c.line([(fx_, fy_), (fx_ + math.cos(a) * s * 0.075, fy_ - s * 0.06 + math.sin(a) * s * 0.095)], K['brown'], 0.8)
    elif attr == 'beads':
        bx, by = Q(0.24, 0.5)
        for k in range(16):
            a = 2 * math.pi * k / 16
            c.circle(bx + math.cos(a) * s * 0.045, by + s * 0.05 + math.sin(a) * s * 0.06, s * 0.012, fill=K['brown_dk'], outline=GOLD_DK, width=0.6)
    elif attr == 'pagoda':
        P.pagoda(c, *Q(0.27, 0.62), s * 0.28)
    elif attr == 'tiger':
        tx, ty = Q(-0.42, 0.02)
        shape(c, [(tx - s * 0.22, ty - s * 0.05), (tx - s * 0.2, ty - s * 0.15), (tx + s * 0.05, ty - s * 0.17), (tx + s * 0.16, ty - s * 0.12), (tx + s * 0.12, ty - s * 0.02), (tx - s * 0.1, ty)], (214, 140, 52), width=1.3)
        c.circle(tx + sg * s * 0.17, ty - s * 0.15, s * 0.07, fill=(214, 140, 52), outline=INK, width=1.2)
        c.ellipse(tx + sg * s * 0.19, ty - s * 0.12, s * 0.035, s * 0.025, fill=(245, 236, 220))
        for k in range(7):
            px = tx - s * 0.17 + k * s * 0.045
            c.line([(px, ty - s * 0.16), (px + s * 0.012, ty - s * 0.08)], INK, 1.6)
        c.circle(tx + sg * s * 0.19, ty - s * 0.17, s * 0.011, fill=(250, 220, 90))
        c.line(bez((tx - s * 0.2, ty - s * 0.06), (tx - s * 0.32, ty - s * 0.04), (tx - s * 0.36, ty - s * 0.14), (tx - s * 0.3, ty - s * 0.2), 12), INK, 2.0)
    elif attr == 'dragon':
        pts = bez(Q(0.05, 1.32), Q(0.5, 1.08), Q(-0.25, 0.96), Q(0.28, 0.78), 40)
        ribbon(c, pts, s * 0.07, K['blue'], edge=INK)
        for k in range(0, len(pts) - 2, 3):
            gold_dot(c, pts[k][0], pts[k][1], 1.0)
        hx, hy = pts[-1]
        c.circle(hx, hy, s * 0.04, fill=K['blue_dk'], outline=INK, width=1.2)
        c.line([(hx, hy), (hx + s * 0.08, hy - s * 0.06)], GOLD, 1.4)
        cloud_puff(c, pts[5][0], pts[5][1] + s * 0.05, s * 0.08, n=3, seed=seed)
    c.ellipse(*hand_r, s * 0.036, s * 0.029, fill=SKIN, outline=SKIN_DK, width=0.9)
    c.ellipse(*hand_l, s * 0.036, s * 0.027, fill=SKIN, outline=SKIN_DK, width=0.9)
    # 头：大光头（头顶略长）、大耳垂、白长眉垂下来、额头三道皱纹，有的留白胡子
    hx, hy = Q(-0.02, 0.85)
    c.rect(hx - s * 0.035, hy + s * 0.06, hx + s * 0.035, hy + s * 0.13, fill=SKIN)
    # 一个大光头：头顶略长、往后脑勺鼓，下巴收进来
    shape(c, [(hx - sg * s * 0.075, hy - s * 0.02), (hx - sg * s * 0.06, hy - s * 0.1), (hx + sg * s * 0.0, hy - s * 0.13), (hx + sg * s * 0.065, hy - s * 0.09),
              (hx + sg * s * 0.075, hy + s * 0.0), (hx + sg * s * 0.055, hy + s * 0.07), (hx + sg * s * 0.0, hy + s * 0.095), (hx - sg * s * 0.055, hy + s * 0.06)],
          SKIN, outline=SKIN_DK, width=1.1, n=8)
    c.ellipse(hx - sg * s * 0.075, hy + s * 0.02, s * 0.016, s * 0.034, fill=SKIN, outline=SKIN_DK, width=0.9)
    face(c, hx + sg * s * 0.012, hy + s * 0.02, s * 0.15, sg, kind='arhat', oval=False)
    for k in range(3):
        c.line(arc(hx, hy - s * 0.02 + k * s * 0.016, s * 0.045, math.pi * 1.15, math.pi * 1.85, 10), SKIN_DK, 0.8)
    if rng.random() < 0.55:
        shape(c, [(hx - s * 0.04, hy + s * 0.07), (hx + s * 0.05, hy + s * 0.07), (hx + sg * s * 0.03, hy + s * 0.17), (hx - sg * s * 0.0, hy + s * 0.15)], (236, 236, 230), outline=(170, 170, 165), width=0.8, n=6)
    for sd in (-1, 1):
        c.line(bez((hx + sd * s * 0.02, hy - s * 0.0), (hx + sd * s * 0.06, hy - s * 0.01), (hx + sd * s * 0.1, hy + s * 0.02), (hx + sd * s * 0.12, hy + s * 0.08), 10), (246, 246, 240), 2.2)


def attendant(c, x, y, s, seed, facing=1, robe=K['brown']):
    """侍立的小沙弥（捧经、合掌）"""
    sg = facing
    c.poly([(x - s * 0.13, y), (x + s * 0.12, y), (x + sg * s * 0.08, y - s * 0.7), (x - sg * s * 0.08, y - s * 0.7)], fill=robe, outline=INK, width=1.2)
    c.poly([(x - s * 0.08, y - s * 0.68), (x + s * 0.06, y - s * 0.7), (x + s * 0.1, y - s * 0.32), (x - s * 0.02, y - s * 0.28)], fill=K['red_dk'], outline=INK, width=0.9)
    c.ellipse(x + sg * s * 0.06, y - s * 0.52, s * 0.05, s * 0.035, fill=SKIN, outline=SKIN_DK, width=0.8)
    face(c, x + sg * s * 0.01, y - s * 0.8, s * 0.17, sg, kind='monk')
    c.ellipse(x, y - s * 0.86, s * 0.07, s * 0.035, fill=mix(SKIN, (90, 90, 100), 0.25))


def frame(c, w, h):
    b = w * 0.035
    c.rect(0, 0, w, b, fill=K['red_dk'])
    c.rect(0, h - b, w, h, fill=K['red_dk'])
    c.rect(0, 0, b, h, fill=K['red_dk'])
    c.rect(w - b, 0, w, h, fill=K['red_dk'])
    gold_line(c, [(b, b), (w - b, b), (w - b, h - b), (b, h - b), (b, b)], 1.8)
    c.rect(b + 4, b + 4, w - b - 4, h - b - 4, outline=INK, width=1.2)


def varnish(im, seed):
    """旧色：整幅偏暖、略暗，淡淡的水渍和细的龟裂纹，边上略深"""
    a = np.asarray(im).astype(np.float32) / 255
    h, w = a.shape[:2]
    rng = np.random.default_rng(seed)
    a *= np.array([0.95, 0.9, 0.8])[None, None, :]
    n = rng.normal(0, 1, (h // 40 + 2, w // 40 + 2)).astype(np.float32)
    n = np.asarray(Image.fromarray(n, mode='F').resize((w, h), Image.BICUBIC))
    a *= (1 + 0.05 * n)[..., None]
    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.minimum(np.minimum(xx, w - 1 - xx) / w, np.minimum(yy, h - 1 - yy) / h)
    a *= (0.88 + 0.12 * np.clip(edge / 0.12, 0, 1))[..., None]
    # 龟裂：随机的折线网，很淡
    crack = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(crack)
    r2 = random.Random(seed)
    for _ in range(int(w * h / 9000)):
        x, y = r2.uniform(0, w), r2.uniform(0, h)
        pts = [(x, y)]
        ang = r2.uniform(0, 6.28)
        for _ in range(r2.randint(3, 7)):
            ang += r2.uniform(-0.9, 0.9)
            L = r2.uniform(6, 18)
            x, y = x + math.cos(ang) * L, y + math.sin(ang) * L
            pts.append((x, y))
        d.line(pts, fill=255, width=1)
    ck = np.asarray(crack.filter(ImageFilter.GaussianBlur(0.4))).astype(np.float32) / 255
    a *= (1 - 0.18 * ck)[..., None]
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


ARHAT_SETS = [
    (('staff', K['ochre'], K['red_dk']), ('bowl', K['brown'], K['green_dk']), ('scroll', K['red'], K['gold_dk'])),
    (('tiger', K['ochre'], K['blue_dk']), ('beads', K['green'], K['red_dk']), ('fan', K['brown'], K['red'])),
    (('dragon', K['blue_lt'], K['red_dk']), ('pagoda', K['ochre'], K['green_dk']), ('staff', K['red'], K['blue_dk'])),
    (('scroll', K['green'], K['red_dk']), ('beads', K['ochre'], K['blue_dk']), ('bowl', K['red_dk'], K['gold_dk'])),
    (('fan', K['blue_lt'], K['red_dk']), ('tiger', K['brown'], K['green_dk']), ('pagoda', K['ochre'], K['red'])),
    (('dragon', K['ochre'], K['blue_dk']), ('staff', K['green'], K['red_dk']), ('scroll', K['brown'], K['gold_dk'])),
]


def mural2(w, h, i):
    """第 i 幅（0..11）"""
    seed = 101 + i * 17
    rng = random.Random(seed)
    c = Canvas(w, h)
    if i in (0, 1, 2, 4, 6, 8):
        # 罗汉三位：近处山石、松、竹，远处云山
        k = (0, 1, 2, 4, 6, 8).index(i)
        background(c, w, h, seed, base=mix(BG_GREEN, BG_BROWN, 0.3 * (k % 2)))
        mountain(c, -10, w + 10, h * 0.5, [(w * 0.2, h * 0.24, w * 0.16), (w * 0.62, h * 0.3, w * 0.18), (w * 0.92, h * 0.2, w * 0.12)], seed,
                 K['blue_lt'], K['green_lt'], mix(K['green_dk'], BG_GREEN, 0.5), line=K['blue_dk'])
        for j in range(3):
            cloud_puff(c, rng.uniform(0.05, 0.75) * w, rng.uniform(0.08, 0.36) * h, w * 0.045, n=rng.randint(3, 5), seed=seed + j)
        pine2(c, w * (0.12 if k % 2 else 0.88), h * 0.78, h * 0.66, seed + 5, facing=1 if k % 2 else -1)
        ground(c, w, h, h * 0.66, seed)
        if k % 3 == 1:
            for j, (x, hh) in enumerate(((0.06, 0.5), (0.13, 0.42))):
                bamboo(c, w * x, h * 0.8, h * hh, seed + j)
        sets = ARHAT_SETS[k]
        spots = [(0.24, 0.88, 0.36), (0.55, 0.79, 0.31), (0.8, 0.95, 0.38)]
        for j, ((attr, robe, band), (sx, sy, sz)) in enumerate(zip(sets, spots)):
            arhat(c, w * sx, h * sy, h * sz, seed + 31 * j, attr=attr, robe=robe, band=band, facing=1 if sx < 0.5 else -1)
        attendant(c, w * 0.38, h * 0.97, h * 0.2, seed + 3, facing=1)
        falling_flowers(c, w * 0.05, h * 0.05, w * 0.95, h * 0.5, 30, seed)
    elif i in (3, 5, 7):
        # 诸天礼佛：一行天人踏云走向佛前（东墙往北、西墙往北：都朝佛像那边走）
        k = (3, 5, 7).index(i)
        background(c, w, h, seed, base=mix(BG_BLUE, BG_GREEN, 0.4 * k), sky=(150, 130, 96))
        for j in range(5):
            cloud_puff(c, rng.uniform(0.0, 0.85) * w, rng.uniform(0.05, 0.3) * h, w * 0.05, n=rng.randint(3, 5), seed=seed + j)
        facing = -1 if i == 5 else 1
        holds = ['censer', 'lotus', 'plate', 'banner', 'ruyi', 'lotus']
        robes = [(K['red'], K['green']), (K['green'], K['red_dk']), (K['blue'], K['ochre']), (K['red_dk'], K['blue_lt']), (K['ochre'], K['green_dk'])]
        n = 4 + (k % 2)
        for j in range(n):
            t = (j + 0.5) / n
            xx = w * (0.12 + 0.76 * (t if facing > 0 else 1 - t))
            yy = h * (0.9 - 0.1 * ((j + k) % 2))
            cloud_puff(c, xx - w * 0.04, yy + h * 0.015, w * 0.06, n=4, seed=seed + 40 + j, col=(240, 236, 220))
            r1, r2 = robes[(j + k) % len(robes)]
            deva(c, xx, yy, h * rng.uniform(0.5, 0.56), seed + j, facing=facing, robe=r1, robe2=r2, scarf=rng.choice([K['blue_lt'], K['green_lt'], K['pink']]), hold=holds[(j + 2 * k) % len(holds)])
        falling_flowers(c, w * 0.05, h * 0.1, w * 0.95, h * 0.55, 46, seed)
    elif i in (9, 10):
        # 后墙两边的两间：诸天礼佛，两排（前排大、后排小一点，错开），最前面一位擎着宝盖；都朝中间的佛像走
        background(c, w, h, seed, base=mix(BG_BROWN, BG_GREEN, 0.5), sky=(168, 140, 98))
        for j in range(5):
            cloud_puff(c, rng.uniform(0.0, 0.85) * w, rng.uniform(0.04, 0.22) * h, w * 0.045, n=rng.randint(3, 5), seed=seed + j)
        facing = 1 if i == 9 else -1
        holds = ['banner', 'plate', 'lotus', 'censer', 'ruyi', 'plate', 'lotus']
        robes = [(K['green'], K['red']), (K['red'], K['blue_lt']), (K['ochre'], K['green_dk']), (K['blue'], K['red_dk']), (K['red_dk'], K['green'])]
        for row, (yy, sz, n) in enumerate(((0.66, 0.42, 4), (0.95, 0.52, 3))):
            for j in range(n):
                t = (j + 0.5 + 0.5 * row) / (n + 0.5)
                xx = w * (0.1 + 0.8 * (t if facing > 0 else 1 - t))
                cloud_puff(c, xx - w * 0.04, h * yy + h * 0.012, w * 0.055, n=4, seed=seed + 40 + j + 7 * row, col=(240, 236, 220))
                r1, r2 = robes[(j + 2 * row) % len(robes)]
                deva(c, xx, h * yy, h * sz * rng.uniform(0.95, 1.05), seed + j + 9 * row, facing=facing, robe=r1, robe2=r2,
                     scarf=rng.choice([K['blue_lt'], K['green_lt'], K['pink']]), hold=holds[(j + 3 * row + i) % len(holds)])
        falling_flowers(c, w * 0.05, h * 0.05, w * 0.95, h * 0.6, 50, seed)
    else:
        # 飞天散花（备用）
        background(c, w, h, seed, base=BG_GREEN, sky=(170, 150, 110))
        for j in range(6):
            cloud_puff(c, rng.uniform(0, 0.85) * w, rng.uniform(0.05, 0.85) * h, w * 0.05, n=4, seed=seed + j)
        for j, (x, y, s_, fl) in enumerate(((0.3, 0.25, 0.4, False), (0.68, 0.5, 0.42, True), (0.35, 0.75, 0.36, False))):
            P.apsara(c, w * x, h * y, w * s_, flip=fl, skirt=[K['green'], K['blue_lt'], K['red_lt']][j], ribbon=[K['red'], K['vermil'], K['blue']][j])
        falling_flowers(c, w * 0.05, h * 0.05, w * 0.95, h * 0.95, 80, seed)
    frame(c, w, h)
    return varnish(c.final(), seed)
