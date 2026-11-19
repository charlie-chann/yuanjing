"""三世佛的手绘贴图（2026-11-17）：佛脸的「开脸」（描眉、点睛、朱唇、白毫）和袈裟衣缘的卷草纹带。

佛脸：脸上是泥金（比身上的鎏金浅、细），眉毛、眼线、嘴唇是画上去的（明清金身像的做法：眉眼描黑、唇点朱）。
  画法和 tools/blender/statues.py 里雕脸用的是同一张「高低图」（face_maps）：眉棱、眼缝、唇的位置一点不差。
  模型那边按头的局部坐标正面投影取贴图坐标（statues.FACE_UV），所以这张图就是「正面看过去的脸」。
衣缘：朱红底、两边金线、中间一路金卷草，卷头上开小花（石青、石绿点花心），横着能无缝接（四个纹样一遍）。

用法：python3 tools/textures/painted_statues.py [输出目录] [face band ...]
  不给输出目录就写到 unity/Sanctuary/Assets/Toon/Textures。另外拼一张 _statue_paint_sheet.png 给人看。
游戏里：模型上叫 paint_buddha_face / paint_robe_band 的部件用这两张图（材质 toon_paint_<名字>，_BaseMap 是这张图）。
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
OUT_DEFAULT = os.path.join(ROOT, 'unity', 'Sanctuary', 'Assets', 'Toon', 'Textures')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'blender'))
import statues  # noqa: E402  （只用到它的 face_maps、FACE_UV：纯 numpy）

SS = 2


def ss(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def c255(c):
    return tuple(int(round(max(0, min(1, v)) * 255)) for v in c)


def face(out):
    """佛脸：1024×1024（2 的幂：Unity 默认导入不会再重采样），对应头的局部坐标 x∈[-0.16, 0.16]、z∈[-0.27, 0.12]（贴图上方是头顶）"""
    x0, z0, w, h = statues.FACE_UV
    W, H = 1024, 1024
    Wb, Hb = W * SS, H * SS
    xs = x0 + (np.arange(Wb) + 0.5) / Wb * w
    zs = z0 + h - (np.arange(Hb) + 0.5) / Hb * h          # 第一行是 v=1（最上面）
    X, Z = np.meshgrid(xs, zs)
    rel, eye, lip, brow, liner = statues.face_maps(X, Z)
    img = np.zeros((Hb, Wb, 3))
    # 泥金：和身上的鎏金同一个色相，亮一成多、淡一点（抛光的脸比袍子浅；不是奶油色的脸配橘色的衣服）；颧上、额上略亮（像擦过一样）。
    # 第三轮：以前 (0.84, 0.635, 0.3)，在殿里的暖光下和袍子一样是一片橙
    base = np.array([0.87, 0.70, 0.40])
    glow = 0.035 * np.exp(-(((np.abs(X) - 0.065) / 0.04) ** 2 + ((Z + 0.075) / 0.04) ** 2)) \
        + 0.025 * np.exp(-((X / 0.08) ** 2 + ((Z - 0.04) / 0.04) ** 2))
    rng = np.random.default_rng(3)
    grain = rng.normal(0, 1, (Hb // 8 + 1, Wb // 8 + 1))
    grain = np.kron(grain, np.ones((8, 8)))[:Hb, :Wb]
    # 外圈一成宽（两边、底下）是纯泥金：头后面、耳朵、脖子的点都钉在这一圈上，跨过去的三角形只取到纯色
    plain = np.maximum(ss(0.118, 0.13, np.abs(X)), ss(-0.245, -0.255, Z))
    img[:] = base[None, None, :] * (1 + (glow[..., None] + 0.008 * grain[..., None]) * (1 - plain[..., None]))
    def put(m, c):
        m = np.clip(m, 0, 1)[..., None]
        img[:] = img * (1 - m) + np.array(c)[None, None, :] * m
    # 唇：朱红，上唇略深，唇线一道更深
    zm = statues.mouth_z(np.abs(X))
    up = (Z > zm).astype(float)
    put(np.clip(lip * 1.4, 0, 1), (0.78, 0.31, 0.24))
    put(np.clip(lip * 1.4, 0, 1) * up * 0.35, (0.62, 0.2, 0.16))
    put(np.exp(-((Z - zm) / 0.0007) ** 2) * (np.abs(X) < 0.031) * 0.85, (0.4, 0.1, 0.08))
    # 眉：细长的弯，画在眉棱上面一点，青黑色；眉头细、眉中略粗、眉尾挑出去
    put(np.clip(brow * 1.3, 0, 1), (0.1, 0.12, 0.2))
    # 眼：垂目只露一线，缝里整条是青黑的眼珠（不露眼白），中间偏内一点更黑（瞳仁）；缝的上沿一道黑眼线（外眼角拖出去），
    #    下沿一道淡淡的暖褐线，画得比刻出来的缝宽一点点，盖住网格上的小锯齿
    u = np.abs(X)
    t = np.clip((u - statues.EYE_IN) / (statues.EYE_OUT - statues.EYE_IN), 0, 1)
    zs = statues.slit_z(t)
    oh = statues.slit_open(t)
    tin = (u > statues.EYE_IN - 0.001) & (u < statues.EYE_OUT + 0.001)
    slit = ss(-0.0012, 0.0002, zs + 0.0004 - Z) * ss(-0.0012, 0.0002, Z - (zs - oh - 0.0004)) * tin
    slit *= ss(-0.06, 0.04, t) * (1 - ss(0.97, 1.06, t))
    put(np.clip(slit, 0, 1), (0.09, 0.075, 0.08))
    iris = np.sqrt(((u - (statues.EYE_IN + 0.42 * (statues.EYE_OUT - statues.EYE_IN))) / 0.016) ** 2)
    put(np.clip(slit, 0, 1) * ss(1.0, 0.5, iris) * 0.8, (0.03, 0.025, 0.03))
    put(np.clip(liner * 1.15, 0, 1), (0.05, 0.045, 0.06))
    low = np.exp(-((Z - (zs - oh - 0.0005)) / 0.0006) ** 2) * ss(0.0, 0.08, t) * (1 - ss(0.92, 1.0, t)) * tin
    put(low * 0.4, (0.42, 0.26, 0.14))
    # 发际线：额头上那一道（螺发是另外的部件；这里画一道干净的石青边，发际线以上都是石青）。
    # 两边的那一成：金色一直到 z=0.06（侧面、后面贴到这一列的点都在发际线以下），再往上才是石青
    hz = statues.hairline_z(np.arcsin(np.clip(X / 0.15, -1, 1)))
    hz = hz * (1 - plain) + 0.06 * plain
    put(ss(-0.0012, 0.0006, Z - hz), (0.176 * 0.45, 0.294 * 0.45, 0.588 * 0.45))
    # 白毫：一颗白珠
    r = np.sqrt(X ** 2 + (Z - 0.021) ** 2)
    put((r < 0.0068).astype(float), (0.95, 0.92, 0.84))
    put(np.exp(-((X + 0.002) ** 2 + (Z - 0.0235) ** 2) / 0.0018 ** 2) * 0.8, (1, 1, 1))
    # 发际线：贴图最上面那一溜（头发是另外的部件，这里只是防止接缝露出金色）——保持金色即可
    # 左下角 64×64 一块纯泥金（statues.SKIN_UV 取它的中心）：手、脚、胸口用
    img[Hb - 64 * SS:, :64 * SS] = base[None, None, :]
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    p = os.path.join(out, 'paint_buddha_face.png')
    im.save(p, optimize=True)
    return p


def band(out):
    """衣缘纹带：1024×128，横着无缝接；朱底、金边、金卷草、小花"""
    W, H = 1024, 128
    Wb, Hb = W * SS, H * SS
    red = (0.7, 0.2, 0.13)
    red_dk = (0.5, 0.12, 0.08)
    gold = (0.95, 0.76, 0.33)
    gold_dk = (0.66, 0.46, 0.16)
    blue = (0.16, 0.33, 0.6)
    green = (0.2, 0.52, 0.42)
    im = Image.new('RGB', (Wb, Hb), c255(red))
    d = ImageDraw.Draw(im)
    # 两边：金边，里面一道细黑线、一道细金线
    e = int(Hb * 0.1)
    d.rectangle([0, 0, Wb, e], fill=c255(gold))
    d.rectangle([0, Hb - e, Wb, Hb], fill=c255(gold))
    d.rectangle([0, e, Wb, e + 4], fill=c255(red_dk))
    d.rectangle([0, Hb - e - 5, Wb, Hb - e], fill=c255(red_dk))
    d.rectangle([0, e + 9, Wb, e + 13], fill=c255(gold))
    d.rectangle([0, Hb - e - 14, Wb, Hb - e - 10], fill=c255(gold))
    # 卷草：主蔓是一道正弦，四个周期；每半个周期往外卷出一个卷头，卷头里一朵小花
    n = 4
    per = Wb / n
    mid = Hb / 2
    amp = Hb * 0.16
    lw = int(Hb * 0.05)

    def vine(x):
        return mid + amp * math.sin(2 * math.pi * x / per)
    pts = [(x, vine(x)) for x in np.linspace(-per, Wb + per, 600)]
    for k in range(len(pts) - 1):
        d.line([pts[k], pts[k + 1]], fill=c255(gold_dk), width=lw + 4)
    for k in range(len(pts) - 1):
        d.line([pts[k], pts[k + 1]], fill=c255(gold), width=lw)
    for i in range(-1, n + 1):
        for half in (0, 1):
            x0 = per * (i + 0.25 + 0.5 * half)
            y0 = vine(x0)
            sg = -1 if half == 0 else 1          # 波峰往下卷、波谷往上卷
            # 卷头：从主蔓伸出的一段螺旋
            cx, cy = x0 + per * 0.16, y0 + sg * Hb * 0.13
            spiral = []
            for t in np.linspace(0, 1, 60):
                ang = math.pi * (1.0 + 2.1 * t) * (-sg)
                rr = Hb * 0.13 * (1 - 0.75 * t)
                spiral.append((cx + rr * math.cos(ang) * 1.3, cy + rr * math.sin(ang)))
            spiral = [(x0, y0)] + spiral
            for k in range(len(spiral) - 1):
                d.line([spiral[k], spiral[k + 1]], fill=c255(gold_dk), width=lw + 2)
            for k in range(len(spiral) - 1):
                d.line([spiral[k], spiral[k + 1]], fill=c255(gold), width=max(2, lw - 2))
            # 叶：主蔓另一侧一片尖叶（石绿描金）
            lx, ly = x0 - per * 0.12, y0 - sg * Hb * 0.06
            leaf = []
            for t in np.linspace(0, 2 * math.pi, 30):
                leaf.append((lx + per * 0.09 * math.cos(t), ly + Hb * 0.055 * math.sin(t) * (1 + 0.6 * math.cos(t))))
            d.polygon(leaf, fill=c255(green), outline=c255(gold))
            # 小花：卷头中心六瓣
            fx, fy = cx + Hb * 0.02, cy
            for k in range(6):
                a = 2 * math.pi * k / 6
                px, py = fx + Hb * 0.045 * math.cos(a), fy + Hb * 0.045 * math.sin(a)
                d.ellipse([px - Hb * 0.032, py - Hb * 0.032, px + Hb * 0.032, py + Hb * 0.032], fill=c255(gold))
            d.ellipse([fx - Hb * 0.03, fy - Hb * 0.03, fx + Hb * 0.03, fy + Hb * 0.03], fill=c255(blue), outline=c255(gold_dk))
    im = im.resize((W, H), Image.LANCZOS)
    p = os.path.join(out, 'paint_robe_band.png')
    im.save(p, optimize=True)
    return p


def _thousand_buddhas(d, P, rings, size, gold, gold_dk, rng):
    """千佛：沿几圈椭圆一个挨一个的小坐佛（金线勾、金填身光），P(x, w) → 像素。rings = [(cx, cw, ax, aw, 间距)]"""
    for (cx, cw, ax, aw, gap) in rings:
        n = max(8, int(2 * math.pi * math.sqrt((ax * ax + aw * aw) / 2) / gap))
        for k in range(n):
            t = 2 * math.pi * (k + 0.5 * (len(rings) % 2)) / n
            x, w = cx + math.sin(t) * ax, cw + math.cos(t) * aw
            s = size * rng.uniform(0.94, 1.06)
            px, py = P(x, w)
            u = s * 787          # 米 → 像素（2048 / 2.6 米）
            # 身光（椭圆圈）、头光（圆圈）、莲座（一道弧）、身子（三角）、头（圆）
            d.ellipse([px - u * 0.36, py - u * 0.62, px + u * 0.36, py + u * 0.1], outline=gold, width=max(1, int(u * 0.05)))
            d.ellipse([px - u * 0.17, py - u * 0.78, px + u * 0.17, py - u * 0.44], outline=gold, width=max(1, int(u * 0.045)))
            d.pieslice([px - u * 0.34, py - u * 0.02, px + u * 0.34, py + u * 0.24], 180, 360, fill=gold_dk)
            d.polygon([(px - u * 0.26, py + u * 0.04), (px + u * 0.26, py + u * 0.04), (px + u * 0.11, py - u * 0.42), (px - u * 0.11, py - u * 0.42)], fill=gold)
            d.ellipse([px - u * 0.085, py - u * 0.66, px + u * 0.085, py - u * 0.48], fill=gold)


def _scroll_field(d, P, cx, cw, r0, r1, n, gold, rng, width):
    """头光里的缠枝卷草（金线）：两圈波浪主蔓，每个波上一个卷须、一片叶"""
    for ring in range(2):
        rr = r0 + (r1 - r0) * (0.3 + 0.45 * ring)
        amp = (r1 - r0) * 0.16
        pts = []
        for k in range(n * 12 + 1):
            t = 2 * math.pi * k / (n * 12)
            r = rr + amp * math.sin(n * t + ring * math.pi)
            pts.append(P(cx + math.sin(t) * r, cw + math.cos(t) * r))
        d.line(pts, fill=gold, width=width)
        for k in range(n):
            t = 2 * math.pi * (k + 0.25 + 0.5 * ring) / n
            sg = 1 if k % 2 == 0 else -1
            r = rr + amp * math.sin(n * t + ring * math.pi)
            c = (cx + math.sin(t) * r, cw + math.cos(t) * r)
            sp = []
            for j in range(22):
                u = j / 21
                ang = t + sg * (0.3 + 2.4 * u)
                rad = (r1 - r0) * (0.16 - 0.12 * u)
                sp.append(P(c[0] + math.sin(ang) * rad * 0.9 + math.sin(t) * (r1 - r0) * 0.06 * sg, c[1] + math.cos(ang) * rad + math.cos(t) * (r1 - r0) * 0.06 * sg))
            d.line(sp, fill=gold, width=max(1, width - 1))
            # 一片叶：两笔弧
            lx, lw = c[0] - math.sin(t) * (r1 - r0) * 0.08 * sg, c[1] - math.cos(t) * (r1 - r0) * 0.08 * sg
            a0 = t + math.pi / 2 * sg
            tip = (lx + math.sin(a0) * (r1 - r0) * 0.3, lw + math.cos(a0) * (r1 - r0) * 0.3)
            d.polygon([P(lx, lw), P((lx + tip[0]) / 2 + math.cos(a0) * 0.02, (lw + tip[1]) / 2 - math.sin(a0) * 0.02), P(*tip),
                       P((lx + tip[0]) / 2 - math.cos(a0) * 0.02, (lw + tip[1]) / 2 + math.sin(a0) * 0.02)], fill=gold)


def mandorla(out):
    """背光：和 statues.mandorla_raster 同一张平面图（statues.MANDORLA_UV 的范围），2048²（评审第三轮：1024 的那张里大片空的石青底）。
    火焰、光圈的台阶边、连珠、卷草、宝珠是贴金的（a = 1：着色器按鎏金画，照见殿里的明暗，和佛像一样是金属）；
    火舌之间的沟里、火焰带的底留一点朱红、橙（a 小：颜料）；身光的石青底上画满一圈圈的千佛（金线小坐佛），
    头光的石绿底上画两圈缠枝卷草；底子上再刷一层很淡的旧色（深一点、暖一点）"""
    x0, z0, w, h = statues.MANDORLA_UV
    W = 2048
    H = 2048
    R = statues.mandorla_raster(w / (W * SS))
    d, rel, zone, gold = R.d, R.h, R.zone, R.gold
    hh, ww = d.shape
    red = np.array([0.66, 0.16, 0.09])
    orange = np.array([0.88, 0.42, 0.14])
    blue = np.array([0.12, 0.25, 0.5])
    green = np.array([0.14, 0.41, 0.33])
    gcol = np.array([0.93, 0.74, 0.34])
    X, Wp = R.X, R.W
    d_halo = np.minimum(np.hypot(X, Wp) - statues.HEAD_R,
                        (np.hypot((X - statues.BODY_C[0]) / statues.BODY_A[0], (Wp - statues.BODY_C[1]) / statues.BODY_A[1]) - 1)
                        * min(statues.BODY_A))
    fz = np.clip(d_halo / 0.3, 0, 1)[..., None]
    img = red * (1 - fz) + orange * fz
    e = np.hypot((X - statues.BODY_C[0]) / statues.BODY_A[0], (Wp - statues.BODY_C[1]) / statues.BODY_A[1])
    img = np.where((zone == 1)[..., None], blue * (0.8 + 0.4 * (1 - np.clip(e, 0, 1)))[..., None], img)
    r = np.hypot(X, Wp) / statues.HEAD_R
    img = np.where((zone == 2)[..., None], green * (0.8 + 0.45 * (1 - np.clip(r, 0, 1)))[..., None], img)
    # 金：火焰里凸起来的地方（火舌的脊、内焰线、宝珠、莲托）全金，沟里按高低慢慢露出朱红；光圈里凸起来的纹样全金
    g = np.clip(gold, 0, 1)
    flame_gold = np.clip(ss(0.006, 0.016, rel) * 1.0, 0, 1)
    g = np.where(zone == 0, np.maximum(g * 0.9, flame_gold), g)
    g = np.where(zone == 3, 1.0, g)
    gg = g[..., None]
    img = img * (1 - gg) + gcol * gg * (0.86 + 0.25 * np.clip(rel / 0.03, 0, 1))[..., None]
    alpha = np.where(zone == 0, 0.2 + 0.8 * g, g)
    # 镂空的边、外轮廓一圈金线
    edge = np.exp(-((d + 0.005) / 0.004) ** 2)
    img = img * (1 - edge[..., None]) + gcol * edge[..., None]
    alpha = np.maximum(alpha, edge)
    img = np.where((d > 0.004)[..., None], gcol * 0.8, img)
    alpha = np.where(d > 0.004, 1.0, alpha)
    # 画上去的纹样（不是浮雕）：千佛、缠枝卷草，金线（a 0.85：半金半颜料）
    im = Image.fromarray((np.clip(img[::-1], 0, 1) * 255).astype(np.uint8))
    am = Image.fromarray((np.clip(alpha[::-1], 0, 1) * 255).astype(np.uint8), 'L')
    pat = Image.new('L', im.size, 0)
    dp = ImageDraw.Draw(pat)
    Wb, Hb = im.size

    def P(x, wv):
        return ((x - x0) / w * Wb, (1 - (wv - z0) / h) * Hb)
    rng = np.random.default_rng(31)
    # 身光：从里往外四圈千佛（最外一圈压着卷草带里沿）
    bc, ba = statues.BODY_C, statues.BODY_A
    _thousand_buddhas(dp, P, [(bc[0], bc[1], ba[0] * f, ba[1] * f, 0.118) for f in (0.28, 0.4, 0.52, 0.64)], 0.112, 255, 170, rng)
    # 头光：两圈缠枝卷草（放射线和中心莲花之间）
    _scroll_field(dp, P, 0.0, 0.0, statues.HEAD_R * 0.33, statues.HEAD_R * 0.6, 14, 255, rng, max(2, int(Wb / 700)))
    pat = pat.filter(ImageFilter.GaussianBlur(0.6))
    pa = np.asarray(pat).astype(np.float64) / 255
    zone_f = zone[::-1]
    pa *= ((zone_f == 1) | (zone_f == 2))
    pa *= (1 - np.clip(np.asarray(am).astype(np.float64) / 255 * 1.5, 0, 1))     # 浮雕的金上不再画
    rgb = np.asarray(im).astype(np.float64) / 255
    rgb = rgb * (1 - pa[..., None]) + gcol * 0.95 * pa[..., None]
    a_out = np.maximum(np.asarray(am).astype(np.float64) / 255, pa * 0.85)
    # 旧色：颜料的底子上很淡的一层暖褐（金上不刷），零星几处褪色
    rng2 = np.random.default_rng(5)
    stain = Image.fromarray((rng2.random((hh // 16 + 1, ww // 16 + 1)) * 255).astype(np.uint8)).resize((ww, hh), Image.BICUBIC)
    st = (np.asarray(stain).astype(np.float64) / 255 - 0.5)
    paint = 1 - a_out
    rgb = rgb * (1 - 0.1 * paint[..., None]) + np.array([0.42, 0.3, 0.16]) * 0.1 * paint[..., None]
    rgb *= (1 + 0.07 * st * paint)[..., None]
    # 颜色和 a 分开缩小（PIL 缩 RGBA 时按 a 预乘：a 为 0 的颜料底子会变成黑的）
    ci = Image.fromarray((np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    ai = Image.fromarray((np.clip(a_out, 0, 1) * 255 + 0.5).astype(np.uint8), 'L').resize((W, H), Image.LANCZOS)
    im = Image.merge('RGBA', (*ci.split(), ai))
    p = os.path.join(out, 'paint_mandorla.png')
    im.save(p, optimize=True)
    return p


def _periodic_noise(rng, n, lo, hi, aniso=None):
    """能无缝平铺的噪声（n×n）：白噪声在频域里只留 lo..hi 这一段频率（每张图几个周期）。
    aniso=(角度, 拉长倍数)：沿这个方向拉长（擦磨的一道道细纹）。返回均值 0、标准差 1"""
    f = np.fft.fftfreq(n) * n
    FX, FY = np.meshgrid(f, f)
    if aniso is not None:
        a, k = aniso
        u = FX * math.cos(a) + FY * math.sin(a)
        v = -FX * math.sin(a) + FY * math.cos(a)
        r = np.hypot(u * k, v)
    else:
        r = np.hypot(FX, FY)
    band = ss(lo * 0.7, lo, r) * (1 - ss(hi, hi * 1.4, r))
    z = np.real(np.fft.ifft2(np.fft.fft2(rng.normal(0, 1, (n, n))) * band))
    return (z - z.mean()) / max(z.std(), 1e-9)


def grain(out):
    """鎏金的金箔（512×512，能无缝平铺；材质 toon_gilt 的 _GiltLeaf，按世界坐标三向平铺，一张约半米）。存的是数不是颜色：
    R：每片金箔的深浅（0.5 是不变；片与片 ±5% 上下，接缝一道略深的线，零星几个暗点）；
    G、B：这一片往贴图 u、v 方向斜多少（0.5 是不斜）：金箔贴的时候不会完全平，镜头一动反光一片一片地闪；
    A：擦磨的亮度（一道道顺着擦的方向的细纹，每片的方向不同；暗点那里不亮）。
    一行 6 片（每片约 8 厘米，同常见的金箔大小），一行一行错开（像砌砖），边是微微弯的"""
    N = 512
    rng = np.random.default_rng(11)
    rows = 6
    cell = N / rows
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float64)
    # 片的边不是笔直的：整张图加一点能平铺的扭动
    wob = _periodic_noise(rng, N, 3, 9) * 2.2
    wob2 = _periodic_noise(rng, N, 3, 9) * 2.2
    ys = (yy + wob) % N
    row = np.floor(ys / cell).astype(int) % rows
    shift = rng.uniform(0, cell, rows)
    xs = (xx + wob2 + shift[row]) % N
    col = np.floor(xs / cell).astype(int) % rows
    leaf_id = row * rows + col
    nleaf = rows * rows
    val = rng.normal(0, 1, nleaf)
    tilt = rng.normal(0, 1, (nleaf, 2))
    shine = rng.uniform(0, 1, nleaf)
    ang = rng.integers(0, 3, nleaf)
    # 离片边多远（像素）：接缝是一道细线（后贴的那片压在前一片上，略深、略斜）
    fy = ys / cell - np.floor(ys / cell)
    fx = xs / cell - np.floor(xs / cell)
    edge = np.minimum(np.minimum(fx, 1 - fx), np.minimum(fy, 1 - fy)) * cell
    seam = np.exp(-(edge / 1.3) ** 2)
    # 片里的细皱（金箔压上去时的小折痕）：高频、很淡
    crinkle = _periodic_noise(rng, N, 40, 90)
    crx, cry = _periodic_noise(rng, N, 25, 70), _periodic_noise(rng, N, 25, 70)
    # 擦磨的细纹：三个方向各一层，每片挑一个方向
    streaks = [_periodic_noise(rng, N, 30, 120, aniso=(a, 7.0)) for a in (0.35, 1.4, 2.5)]
    st = np.choose(ang[leaf_id], streaks)
    # 零星的暗点（磨穿、落了灰的小坑）
    pits = np.zeros((N, N))
    for _ in range(140):
        cx, cy, r = rng.uniform(0, N), rng.uniform(0, N), rng.uniform(0.8, 2.2)
        dx = (xx - cx + N / 2) % N - N / 2
        dy = (yy - cy + N / 2) % N - N / 2
        pits = np.maximum(pits, np.exp(-(dx * dx + dy * dy) / (r * r)))
    R = 0.5 + 0.05 * val[leaf_id] - 0.045 * seam + 0.012 * crinkle + 0.012 * st - 0.13 * pits
    G = 0.5 + 0.17 * tilt[leaf_id, 0] + 0.05 * crx
    B = 0.5 + 0.17 * tilt[leaf_id, 1] + 0.05 * cry
    A = 0.62 + 0.22 * (shine[leaf_id] - 0.5) + 0.16 * np.clip(st, -2, 2) - 0.12 * seam - 0.5 * pits
    img = np.stack([R, G, B, A], axis=-1)
    im = Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGBA')
    p = os.path.join(out, 'gilt_grain.png')
    im.save(p, optimize=True)
    return p


def main(argv):
    out = OUT_DEFAULT
    names = []
    for a in argv:
        if os.path.sep in a or a.startswith('.'):
            out = a
        else:
            names.append(a)
    os.makedirs(out, exist_ok=True)
    todo = {'face': face, 'band': band, 'mandorla': mandorla, 'grain': grain}
    made = [todo[n](out) for n in (names or list(todo))]
    for p in made:
        print('[paint]', p)
    # 拼一张给人看
    ims = [Image.open(p) for p in made]
    Ht = sum(int(im.height * 600 / im.width) for im in ims)
    sheet = Image.new('RGB', (600, Ht), (40, 40, 40))
    y = 0
    for im in ims:
        h = int(im.height * 600 / im.width)
        sheet.paste(im.resize((600, h)), (0, y))
        y += h
    sheet.save(os.path.join(out, '_statue_paint_sheet.png'))


if __name__ == '__main__':
    main(sys.argv[1:])
