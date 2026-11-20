"""钓鱼的用具和钓上来的东西（2026-11-19）。

用具：fishing_rod 竹竿、fishing_bobber 红白浮漂、fish_basket 竹编鱼篓、fishing_stool 小马扎。
鱼获（每种一个模型，按真实大小）：鲫鱼、泥鳅、小金鱼、青虾、白条、银鱼、鲈鱼、鳜鱼、大闸蟹、金鳞鲤、月光鱼、一团水草。

鱼的做法同 critters_hd.py 的锦鲤，再细一档：身体是一圈圈截面（背、腹、宽各一条曲线），颜色按位置画——背深腹白、鳞片一排排错开
（每片下缘亮、上缘暗）、鳃盖的弧线、嘴缝、各种鱼自己的花斑；鳍是一条条鳍条撑开的薄膜（鲈、鳜的背鳍前半是一根根硬棘，鳍缘是锯齿）。

约定（所有鱼获都一样，程序挂到线上时统一转一下就行）：**原点在嘴（挂钩的地方），头朝 +y，身子往 -y 拖，背朝 +z**。
水草的原点是钩住的那一头。部件：toon（身体）、leaf（鳍、叶片，双面）、glow（月光鱼身上的光点）。
"""
import math

import numpy as np
from mathutils import Vector, noise

from kit import Asset
from palette import C, hexc, mix, tint, vary
import craft
from craft import grid, fan, smooth, bump, interp, clamp


# ====================================================================== 鱼
def _curve(pts, n=240, blur=7):
    """几个控制点 (u, 值) → 一条抹顺了的曲线（按 u 查）"""
    xs = np.linspace(0, 1, n)
    ys = np.interp(xs, [p[0] for p in pts], [p[1] for p in pts])
    if blur > 1:
        k = np.hanning(blur * 2 + 1)
        k /= k.sum()
        ys = np.convolve(np.pad(ys, blur, mode='edge'), k, mode='valid')
    return lambda u: float(np.interp(u, xs, ys))


def _fin(a, roots, tips, c0, c1, ray=2, sub=2, edge=None, mat='leaf'):
    """鳍：沿根一排点、沿外缘一排点，之间是一条条鳍条撑开的膜。每隔 ray 条是一根深色的鳍条；sub：根到缘之间分几段（颜色从 c0 过渡到 c1，缘上再压一道 edge）"""
    n = len(roots)
    edge = edge or c1
    for i in range(n - 1):
        dark = ray and i % ray == 0
        for s in range(sub):
            t0, t1 = s / sub, (s + 1) / sub
            p = [Vector(roots[i]).lerp(Vector(tips[i]), t0), Vector(roots[i + 1]).lerp(Vector(tips[i + 1]), t0),
                 Vector(roots[i + 1]).lerp(Vector(tips[i + 1]), t1), Vector(roots[i]).lerp(Vector(tips[i]), t1)]
            ca, cb = mix(c0, c1, t0), mix(c0, c1, t1)
            if s == sub - 1:
                cb = mix(cb, edge, 0.6)
            cl = [tint(ca, -0.07) if dark else ca, ca, cb, tint(cb, -0.06) if dark else cb]
            a.quad(p, mat=mat, colors=cl)


def _fish(name, sp, view=(74, 12, 1.0)):
    """一条鱼。sp 里：L 全长；body 身体（嘴到尾柄）占全长多少；dorsal/ventral/width 三条曲线（占全长的比例）；
    colour(u, th, side, top) 底色和花斑；scales (沿身几排, 一圈几片, 深浅)；eye (u, 高, 半径)；鳍的参数见下面各种鱼"""
    a = Asset(name)
    rng = a.rng
    L = sp['L']
    Lb = L * sp.get('body', 0.8)
    fd, fv, fw = _curve(sp['dorsal']), _curve(sp['ventral']), _curve(sp['width'])
    zmid = _curve(sp.get('mid', [(0, 0), (1, 0)]))
    R, S = sp.get('rings', 72), sp.get('segs', 32)
    rows, around, depth = sp.get('scales', (40, 26, 0.06))
    head_u = sp.get('head', 0.22)
    belly = sp.get('belly', hexc('#f4efe4'))
    mouth_z = sp.get('mouth_z', 0.0)

    def pos(u, th):
        cs, sn = math.cos(th), math.sin(th)
        w = fw(u) * L
        h = (fd(u) if sn >= 0 else fv(u)) * L
        e = sp.get('box', 1.0)
        x = w * math.copysign(abs(cs) ** e, cs)
        z = zmid(u) * L + h * math.copysign(abs(sn) ** e, sn)
        return Vector((x, -u * Lb, z))

    def colour(u, th):
        sn = math.sin(th)
        c = sp['colour'](u, th, math.cos(th), sn)
        # 肚子发白
        c = mix(c, belly, sp.get('belly_k', 0.9) * smooth(-0.25, -0.8, sn))
        # 鳞片
        if rows and u > head_u:
            sv = (u - head_u) / (1 - head_u) * rows
            su = th / (2 * math.pi) * around + (0.5 if int(sv) % 2 else 0.0)
            fu, fv_ = su - math.floor(su) - 0.5, sv - math.floor(sv)
            e = fv_ + 0.6 * fu * fu
            sh = depth * (e - 0.5)
            if 0.9 < e < 1.06:
                sh -= depth * 1.1
            c = tint(c, sh * (0.5 + 0.5 * smooth(-0.9, -0.2, sn)))
        # 鳃盖：一道弧线，后面一圈浅的
        gu = head_u - 0.045 * (1 - sn * sn) + 0.01
        if u < head_u + 0.03:
            c = tint(c, -0.1 * bump(u, gu, 0.008) + 0.035 * bump(u, gu - 0.02, 0.012))
        # 嘴缝
        if u < 0.07 and abs(sn - mouth_z - 0.9 * u) < 0.16 and abs(math.cos(th)) > 0.2:
            c = tint(c, -0.2 * smooth(0.075, 0.03, u))
        return c
    grid(a, 'toon', S, R, lambda uu, vv: (pos(0.012 + 0.988 * vv, 2 * math.pi * uu), colour(0.012 + 0.988 * vv, 2 * math.pi * uu)),
         cap0=((0, 0.004 * L, zmid(0) * L + mouth_z * 0.01 * L), sp['colour'](0, 0, 1, 0)), cap1=((0, -Lb - 0.004 * L, zmid(1) * L), colour(1, 0)))

    def top(u):
        return zmid(u) * L + fd(u) * L

    def bot(u):
        return zmid(u) * L - fv(u) * L
    fc0, fc1 = sp['fin'], sp.get('fin_tip', mix(sp['fin'], (1, 1, 1), 0.4))
    fe = sp.get('fin_edge')
    # ── 尾鳍 ──
    tl = sp['tail']
    yt = -Lb
    hp = max(fd(1), fv(1)) * L
    Lt = L - Lb
    n = tl.get('n', 15)
    roots, tips = [], []
    for k in range(n):
        s = k / (n - 1) * 2 - 1
        roots.append((0, yt + 0.012 * L, zmid(1) * L + s * hp * 0.95))
        fork = tl.get('fork', 0.35)
        ln = Lt * (1 - fork * math.cos(s * math.pi / 2) ** tl.get('p', 1.6)) if fork >= 0 else Lt * (1 + fork * (1 - math.cos(s * math.pi / 2) ** 0.8))
        zt = zmid(1) * L + s * tl.get('spread', 0.11) * L * (abs(s) ** tl.get('round', 0.0) if tl.get('round') else 1)
        tips.append((tl.get('wave', 0.0) * L * math.sin(k * 1.3), yt - ln, zt))
    for sgn in ((-1, 1) if tl.get('double') else (0,)):          # 金鱼是左右两片的双尾
        rr = [(sgn * 0.004 * L, p[1], p[2]) for p in roots]
        tt = [(sgn * tl.get('double', 0) * L * (0.4 + 0.6 * abs(k / (n - 1) * 2 - 1)) + p[0], p[1], p[2]) for k, p in enumerate(tips)]
        _fin(a, rr, tt, tl.get('c0', fc0), tl.get('c1', fc1), ray=2, sub=tl.get('sub', 3), edge=fe)
    # ── 背鳍（可以有两段：前一段硬棘、后一段软条） ──
    for d in sp.get('dorsals', []):
        n = d.get('n', 13)
        roots, tips = [], []
        for k in range(n):
            t = k / (n - 1)
            u = d['u0'] + (d['u1'] - d['u0']) * t
            hh = d['h'] * L * (math.sin(math.pi * (d.get('a0', 0.12) + (d.get('a1', 0.95) - d.get('a0', 0.12)) * t)) ** d.get('p', 0.8))
            if d.get('spine') and k % 2 == 1:
                hh *= 0.72          # 硬棘之间的膜凹下去：鳍缘成锯齿
            roots.append((0, -u * Lb, top(u) - 0.004 * L))
            tips.append((0, -u * Lb - d.get('lean', 0.6) * hh, top(u) + hh))
        _fin(a, roots, tips, d.get('c0', fc0), d.get('c1', fc1), ray=2, sub=2, edge=d.get('edge', fe))
        if d.get('spine'):          # 硬棘：一根根尖刺
            for k in range(0, n, 2):
                a.tube([roots[k], tips[k]], [0.0028 * L, 0.0008 * L], tint(d.get('c0', fc0), -0.12), segs=4)
    # ── 臀鳍 ──
    for d in sp.get('anals', []):
        n = d.get('n', 8)
        roots, tips = [], []
        for k in range(n):
            t = k / (n - 1)
            u = d['u0'] + (d['u1'] - d['u0']) * t
            hh = d['h'] * L * math.sin(math.pi * (0.25 + 0.7 * t)) ** 0.8
            roots.append((0, -u * Lb, bot(u) + 0.004 * L))
            tips.append((0, -u * Lb - d.get('lean', 0.7) * hh, bot(u) - hh))
        _fin(a, roots, tips, d.get('c0', fc0), d.get('c1', fc1), ray=2, sub=2, edge=fe)
    # ── 胸鳍、腹鳍（左右各一） ──
    for sx in (-1, 1):
        for d in sp.get('paired', []):
            u = d['u']
            n = d.get('n', 8)
            base = Vector((sx * fw(u) * L * d.get('out', 0.9), -u * Lb, zmid(u) * L - fv(u) * L * d.get('low', 0.5)))
            ln = d['len'] * L
            roots, tips = [], []
            for k in range(n):
                t = k / (n - 1)
                roots.append(base + Vector((0, -0.012 * L * t * d.get('root', 1.0), -0.01 * L * t)))
                ang = d.get('a0', 0.25) + d.get('fan', 0.9) * t
                dv = Vector((sx * math.sin(d.get('splay', 0.6)) * math.cos(ang), -math.cos(ang) * math.cos(d.get('splay', 0.6)) - 0.1, -math.sin(ang)))
                tips.append(base + dv.normalized() * ln * (0.75 + 0.25 * math.sin(math.pi * t)))
            _fin(a, roots, tips, d.get('c0', fc0), d.get('c1', fc1), ray=2, sub=2, edge=fe)
    # ── 眼睛：一圈眼圈、黑眼珠、高光；鼻孔 ──
    eu, ez, er = sp['eye']
    for sx in (-1, 1):
        ec = Vector((sx * fw(eu) * L * sp.get('eye_out', 0.86), -eu * Lb, zmid(eu) * L + ez * L))
        a.blob(er * L * 1.28, ec, (0.45, 1, 1), sp.get('iris', hexc('#e9d9a0')), subdiv=2, bump=0)
        a.blob(er * L * 0.82, ec + Vector((sx * er * L * 0.3, 0, 0)), (0.5, 1, 1), hexc('#141214'), subdiv=2, bump=0)
        a.blob(er * L * 0.26, ec + Vector((sx * er * L * 0.62, er * L * 0.3, er * L * 0.34)), (0.6, 1, 1), (1, 1, 1), subdiv=1, bump=0)
        a.blob(0.004 * L, Vector((sx * fw(eu * 0.5) * L * 0.8, -eu * 0.5 * Lb, zmid(eu * 0.5) * L + fd(eu * 0.5) * L * 0.55)), (1, 1, 1), tint(sp['colour'](0.05, 1.2, 0.3, 0.9), -0.2),
               subdiv=1, bump=0)
    # ── 须（鲤、泥鳅） ──
    for (bu, bz, ln, dx) in sp.get('barbels', []):
        for sx in (-1, 1):
            p0 = Vector((sx * fw(bu) * L * 0.8, -bu * Lb, zmid(bu) * L - fv(bu) * L * bz))
            a.tube([p0, p0 + Vector((sx * dx * ln * L, 0.3 * ln * L, -0.5 * ln * L)), p0 + Vector((sx * dx * ln * L * 1.5, -0.1 * ln * L, -ln * L))],
                   [0.004 * L, 0.003 * L, 0.0012 * L], tint(sp['colour'](0.05, -0.5, 0.8, -0.5), -0.05), segs=4)
    for extra in sp.get('extras', []):
        extra(a, L, Lb, fd, fv, fw, zmid)
    a.opts['leaf'] = {'plain_normals': True}
    return craft.finish(a, view, floor=False, extra=sp.get('shots', {'q': (128, 24, 1.0)}))


def _n3(u, th, f=(5, 1.4, 1.4), seed=0.0):
    return noise.noise(Vector((u * f[0] + seed, math.cos(th) * f[1], math.sin(th) * f[2])))


def crucian(name):
    """鲫鱼：18 厘米。身子高而侧扁，背青灰带橄榄绿，体侧银白泛一点黄，鳞大而清楚；背鳍长，尾叉浅"""
    back, side = hexc('#5b6652'), hexc('#c9c7ae')

    def col(u, th, cs, sn):
        c = mix(side, back, smooth(0.15, 0.85, sn))
        c = mix(c, hexc('#d9c88a'), 0.25 * smooth(0.2, -0.5, sn) * (0.5 + 0.5 * _n3(u, th)))
        return c
    fin = hexc('#7c8068')
    return _fish(name, dict(
        L=0.18, body=0.8, head=0.24, scales=(16, 14, 0.13), colour=col, fin=fin, fin_tip=hexc('#a7a88f'),
        dorsal=[(0, 0.012), (0.08, 0.075), (0.2, 0.135), (0.4, 0.185), (0.55, 0.17), (0.8, 0.085), (0.93, 0.048), (1, 0.046)],
        ventral=[(0, 0.012), (0.08, 0.055), (0.2, 0.115), (0.42, 0.155), (0.6, 0.14), (0.82, 0.07), (0.93, 0.046), (1, 0.044)],
        width=[(0, 0.008), (0.08, 0.04), (0.22, 0.062), (0.42, 0.066), (0.7, 0.04), (0.92, 0.014), (1, 0.011)],
        eye=(0.1, 0.03, 0.023), tail=dict(fork=0.3, spread=0.15, sub=3),
        dorsals=[dict(u0=0.4, u1=0.86, h=0.1, n=17, lean=0.55, a0=0.3, a1=0.9, p=0.6)],
        anals=[dict(u0=0.72, u1=0.86, h=0.07)],
        paired=[dict(u=0.27, len=0.11, low=0.45), dict(u=0.47, len=0.09, low=0.95, splay=0.25, out=0.3)]))


def loach(name):
    """泥鳅：14 厘米。圆滚滚一条，黄褐色的身子上满是深色小斑点，嘴边五对短须，尾圆"""
    base, spot = hexc('#a98a4e'), hexc('#4c3a22')

    def col(u, th, cs, sn):
        c = mix(base, hexc('#6b5632'), smooth(0.0, 0.9, sn))
        n = _n3(u, th, (46, 5, 5), 2.0) + 0.5 * _n3(u, th, (90, 9, 9), 7.0)
        c = mix(c, spot, 0.8 * smooth(0.22, 0.36, n) * smooth(-0.5, -0.3, sn))
        return c
    fin = hexc('#b39a66')
    return _fish(name, dict(
        L=0.14, body=0.87, head=0.15, scales=(0, 0, 0), colour=col, fin=fin, fin_tip=hexc('#d2bf90'), belly=hexc('#e9dcb4'), belly_k=0.8, rings=60, segs=20,
        dorsal=[(0, 0.012), (0.05, 0.036), (0.14, 0.05), (0.5, 0.053), (0.85, 0.042), (1, 0.034)],
        ventral=[(0, 0.012), (0.05, 0.03), (0.14, 0.046), (0.5, 0.05), (0.85, 0.04), (1, 0.034)],
        width=[(0, 0.01), (0.05, 0.03), (0.14, 0.042), (0.5, 0.044), (0.85, 0.028), (1, 0.014)],
        mid=[(0, 0.0), (0.3, 0.004), (0.6, -0.006), (1, 0.004)],
        eye=(0.06, 0.02, 0.0125), tail=dict(fork=-0.25, spread=0.062, sub=2, n=11),
        dorsals=[dict(u0=0.52, u1=0.66, h=0.05, n=7)], anals=[dict(u0=0.76, u1=0.86, h=0.035, n=5)],
        paired=[dict(u=0.17, len=0.06, low=0.6), dict(u=0.55, len=0.045, low=0.95, splay=0.3, out=0.4)],
        barbels=[(0.012, 0.3, 0.045, 0.6), (0.02, 0.6, 0.05, 0.9), (0.03, 0.9, 0.04, 0.7)]))


def goldfish(name):
    """小金鱼：9 厘米。圆鼓鼓的身子，橘红带白肚，眼睛大，背鳍高，尾是分成左右两片的大纱尾"""
    red, white = hexc('#f0642a'), hexc('#fbf2e2')

    def col(u, th, cs, sn):
        n = _n3(u, th, (4, 1.2, 1.2), 3.0)
        c = red if (sn > -0.35 + 0.5 * n) else white
        if u < 0.2:
            c = mix(c, hexc('#f58a3a'), 0.4)
        return mix(c, hexc('#ffb347'), 0.3 * smooth(0.0, 0.9, sn) * (0.5 + 0.5 * n))
    fin = hexc('#f47a3a')
    return _fish(name, dict(
        L=0.09, body=0.58, head=0.3, scales=(10, 12, 0.07), colour=col, fin=fin, fin_tip=hexc('#fde3c4'), fin_edge=hexc('#fff6ea'), belly_k=0.5,
        dorsal=[(0, 0.02), (0.1, 0.12), (0.3, 0.2), (0.55, 0.2), (0.85, 0.09), (1, 0.06)],
        ventral=[(0, 0.02), (0.1, 0.1), (0.3, 0.19), (0.55, 0.2), (0.85, 0.085), (1, 0.055)],
        width=[(0, 0.015), (0.1, 0.085), (0.3, 0.135), (0.55, 0.135), (0.85, 0.045), (1, 0.022)],
        eye=(0.14, 0.035, 0.045), eye_out=0.95, rings=48, segs=28,
        tail=dict(fork=0.28, spread=0.34, sub=4, n=17, double=0.2, wave=0.02, p=1.2),
        dorsals=[dict(u0=0.36, u1=0.82, h=0.2, n=13, lean=0.75, a0=0.3, p=0.6)], anals=[dict(u0=0.8, u1=0.93, h=0.13, n=6)],
        paired=[dict(u=0.34, len=0.17, low=0.55), dict(u=0.62, len=0.18, low=0.95, splay=0.35, out=0.4)]))


def whitebait(name):
    """白条（䱗）：14 厘米。细长侧扁，背是青灰，体侧一片银白发亮，鳞细，尾叉深"""
    back, side = hexc('#7d8f8a'), hexc('#e6ebe8')

    def col(u, th, cs, sn):
        c = mix(side, back, smooth(0.35, 0.9, sn))
        return mix(c, hexc('#fbfdfd'), 0.5 * bump(sn, 0.1, 0.25))          # 体侧一道亮带
    fin = hexc('#b9c2bd')
    return _fish(name, dict(
        L=0.14, body=0.8, head=0.2, scales=(26, 16, 0.07), colour=col, fin=fin, fin_tip=hexc('#e2e8e4'), belly=hexc('#fbfbf6'),
        dorsal=[(0, 0.01), (0.08, 0.04), (0.2, 0.062), (0.45, 0.075), (0.8, 0.045), (0.94, 0.028), (1, 0.027)],
        ventral=[(0, 0.01), (0.08, 0.04), (0.2, 0.07), (0.45, 0.085), (0.8, 0.045), (0.94, 0.027), (1, 0.026)],
        width=[(0, 0.007), (0.08, 0.024), (0.22, 0.034), (0.45, 0.035), (0.8, 0.02), (1, 0.007)],
        eye=(0.085, 0.012, 0.02), mouth_z=0.25, tail=dict(fork=0.55, spread=0.14, sub=3),
        dorsals=[dict(u0=0.5, u1=0.63, h=0.075, n=8)], anals=[dict(u0=0.68, u1=0.86, h=0.05, n=10)],
        paired=[dict(u=0.22, len=0.11, low=0.6), dict(u=0.45, len=0.07, low=0.97, splay=0.25, out=0.3)]))


def silverfish(name):
    """银鱼：12 厘米。细得像一根玉簪，通体半透明的乳白，头尖而扁，两只黑眼睛，脊背一线淡淡的灰，肚里一点点粉"""
    body = hexc('#f1f0e8')

    def col(u, th, cs, sn):
        c = mix(body, hexc('#cfd3cb'), 0.7 * bump(sn, 1.0, 0.25))
        c = mix(c, hexc('#f2cfc4'), 0.5 * bump(u, 0.3, 0.1) * smooth(0.3, -0.4, sn))
        if abs(sn - 0.05) < 0.08 and 0.2 < u < 0.95 and int(u * 60) % 2 == 0:
            c = tint(c, -0.1)          # 体侧一排小黑点
        return c
    fin = hexc('#e8e8e0')
    return _fish(name, dict(
        L=0.12, body=0.86, head=0.16, scales=(0, 0, 0), colour=col, fin=fin, fin_tip=hexc('#f8f8f4'), belly=hexc('#fbfaf4'), belly_k=0.4, rings=44, segs=16,
        dorsal=[(0, 0.004), (0.06, 0.014), (0.16, 0.026), (0.5, 0.032), (0.85, 0.022), (1, 0.014)],
        ventral=[(0, 0.004), (0.06, 0.014), (0.16, 0.028), (0.5, 0.036), (0.85, 0.022), (1, 0.014)],
        width=[(0, 0.006), (0.06, 0.022), (0.16, 0.026), (0.5, 0.025), (0.85, 0.014), (1, 0.005)],
        eye=(0.075, 0.006, 0.014), eye_out=0.95, iris=hexc('#dfe3e2'), tail=dict(fork=0.5, spread=0.075, sub=2, n=11),
        dorsals=[dict(u0=0.62, u1=0.74, h=0.045, n=7)], anals=[dict(u0=0.72, u1=0.88, h=0.035, n=8)],
        paired=[dict(u=0.18, len=0.06, low=0.5), dict(u=0.45, len=0.04, low=0.95, splay=0.25, out=0.3)]))


def bass(name):
    """鲈鱼：32 厘米。身子长而结实，嘴大、下颌突出，背青灰、体侧银白，背上和背鳍上散着黑斑点；前一个背鳍是硬棘"""
    back, side = hexc('#5f6f70'), hexc('#d5dad3')

    def col(u, th, cs, sn):
        c = mix(side, back, smooth(0.05, 0.85, sn))
        n = _n3(u, th, (17, 3.2, 3.2), 4.0)
        if sn > 0.1 and u > 0.2:
            c = mix(c, hexc('#22282a'), 0.85 * smooth(0.28, 0.42, n) * smooth(0.1, 0.25, sn))
        return c
    fin = hexc('#7f8a86')
    return _fish(name, dict(
        L=0.32, body=0.82, head=0.27, scales=(26, 18, 0.08), colour=col, fin=fin, fin_tip=hexc('#b3bbb5'), mouth_z=-0.15,
        dorsal=[(0, 0.01), (0.06, 0.05), (0.2, 0.1), (0.38, 0.122), (0.6, 0.105), (0.82, 0.055), (0.94, 0.04), (1, 0.04)],
        ventral=[(0, 0.022), (0.06, 0.06), (0.2, 0.1), (0.4, 0.115), (0.6, 0.095), (0.82, 0.05), (0.94, 0.038), (1, 0.038)],
        width=[(0, 0.014), (0.06, 0.045), (0.2, 0.066), (0.4, 0.07), (0.7, 0.042), (0.93, 0.016), (1, 0.012)],
        eye=(0.09, 0.03, 0.017), tail=dict(fork=0.22, spread=0.135, sub=3),
        dorsals=[dict(u0=0.34, u1=0.55, h=0.1, n=13, spine=True, lean=0.5, a0=0.2, a1=0.9, c0=hexc('#6d7876')),
                 dict(u0=0.58, u1=0.82, h=0.085, n=11, lean=0.6, a0=0.35, a1=0.92)],
        anals=[dict(u0=0.68, u1=0.82, h=0.07)],
        paired=[dict(u=0.3, len=0.1, low=0.5), dict(u=0.36, len=0.09, low=0.95, splay=0.25, out=0.35)]))


def mandarin(name):
    """鳜鱼（桂花鱼）：30 厘米。身子高、头尖嘴大，黄绿色的底上一块块不规则的黑褐斑，一条黑带从吻端穿过眼睛斜到背上；
    背鳍前半是一排高高的硬棘，后半和尾鳍都是圆的，鳍上有成排的黑点"""
    base, dark = hexc('#b9a552'), hexc('#3a3021')

    def col(u, th, cs, sn):
        c = mix(hexc('#d2c487'), mix(base, hexc('#7d7a3c'), 0.5), smooth(-0.3, 0.8, sn))
        n = 1.25 * _n3(u, th, (6.5, 1.6, 1.6), 6.0) + 0.25 * _n3(u, th, (11, 2.6, 2.6), 1.0)
        if u > 0.24:
            c = mix(c, hexc('#e4d79a'), 0.5 * smooth(-0.3, -0.5, n) * smooth(-0.3, -0.1, sn))
            c = mix(c, dark, 0.88 * smooth(0.12, 0.26, n) * smooth(-0.55, -0.35, sn))
        # 过眼的斜带：从嘴尖到背鳍前
        if u < 0.36 and abs(sn - (0.1 + 2.3 * u)) < 0.2 and abs(cs) > 0.15:
            c = mix(c, dark, 0.85)
        return c
    fin = hexc('#b3a060')

    def fin_spots(a, L, Lb, fd, fv, fw, zmid):
        rng = a.rng
        for i in range(26):          # 尾鳍和后背鳍上的黑点：一排排小圆片（贴在鳍面两边）
            if i < 16:
                r, k = 0.4 + 0.42 * (i // 4) / 3, (i % 4 - 1.5) / 1.5
                p = Vector((0, -Lb - (L - Lb) * r, k * 0.085 * L * (0.5 + r)))
            else:
                t = (i - 16) / 9
                u = 0.62 + 0.2 * t
                p = Vector((0, -u * Lb - 0.03 * L, zmid(u) * L + fd(u) * L + 0.035 * L))
            for sx in (-1, 1):
                a.disc(0.006 * L, (sx * 0.0012 * L, p.y, p.z), dark, segs=6, mat='leaf', tilt=(0, math.pi / 2))
    return _fish(name, dict(
        L=0.3, body=0.8, head=0.3, scales=(30, 20, 0.04), colour=col, fin=fin, fin_tip=hexc('#d9cc8e'), belly=hexc('#efe8cf'), belly_k=0.75, mouth_z=-0.2,
        dorsal=[(0, 0.008), (0.06, 0.05), (0.2, 0.125), (0.36, 0.175), (0.55, 0.165), (0.8, 0.08), (0.93, 0.05), (1, 0.05)],
        ventral=[(0, 0.024), (0.06, 0.062), (0.2, 0.11), (0.4, 0.135), (0.6, 0.12), (0.82, 0.062), (0.93, 0.046), (1, 0.046)],
        width=[(0, 0.014), (0.06, 0.046), (0.2, 0.068), (0.4, 0.07), (0.7, 0.042), (0.93, 0.017), (1, 0.013)],
        eye=(0.1, 0.045, 0.018), tail=dict(fork=-0.22, spread=0.155, sub=3, n=17),
        dorsals=[dict(u0=0.3, u1=0.6, h=0.115, n=23, spine=True, lean=0.35, a0=0.25, a1=0.85, p=0.5, c0=hexc('#8a7c42')),
                 dict(u0=0.61, u1=0.86, h=0.12, n=11, lean=0.55, a0=0.4, a1=0.9, p=0.55)],
        anals=[dict(u0=0.68, u1=0.85, h=0.095)],
        paired=[dict(u=0.31, len=0.11, low=0.45, fan=1.2), dict(u=0.36, len=0.1, low=0.95, splay=0.25, out=0.35)],
        extras=[fin_spots]))


def carp_gold(name):
    """金鳞鲤：35 厘米，稀有。通体金色：背是赤金、体侧一片片大鳞亮得发白，鳍是透亮的橘金，嘴边两对须"""
    g0, g1, g2 = hexc('#e09a12'), hexc('#fbc92e'), hexc('#fff3b0')

    def col(u, th, cs, sn):
        c = mix(g1, g0, smooth(0.2, 0.95, sn))
        # 每片鳞中间一点最亮的反光（和下面画鳞的排法一致）
        if u > 0.23:
            sv = (u - 0.23) / 0.77 * 15
            su = th / (2 * math.pi) * 13 + (0.5 if int(sv) % 2 else 0.0)
            fu, fv_ = su - math.floor(su) - 0.5, sv - math.floor(sv)
            c = mix(c, g2, 0.75 * bump(fu, 0.0, 0.22) * bump(fv_, 0.45, 0.22) * smooth(-0.7, 0.0, sn))
        return c
    fin = hexc('#f2a23a')
    return _fish(name, dict(
        L=0.35, body=0.8, head=0.23, scales=(15, 13, 0.1), colour=col, fin=fin, fin_tip=hexc('#ffe08a'), fin_edge=hexc('#fff3c2'), belly=hexc('#ffeaa0'), belly_k=0.6,
        iris=hexc('#ffe9a0'), rings=84, segs=40,
        dorsal=[(0, 0.012), (0.07, 0.07), (0.2, 0.125), (0.38, 0.15), (0.6, 0.125), (0.82, 0.06), (0.94, 0.044), (1, 0.043)],
        ventral=[(0, 0.014), (0.07, 0.06), (0.2, 0.11), (0.4, 0.135), (0.6, 0.115), (0.82, 0.058), (0.94, 0.042), (1, 0.041)],
        width=[(0, 0.012), (0.07, 0.05), (0.2, 0.074), (0.4, 0.08), (0.7, 0.048), (0.93, 0.018), (1, 0.013)],
        eye=(0.1, 0.03, 0.017), mouth_z=-0.3, tail=dict(fork=0.42, spread=0.18, sub=4, n=17),
        dorsals=[dict(u0=0.36, u1=0.82, h=0.1, n=21, lean=0.6, a0=0.35, a1=0.9, p=0.5)], anals=[dict(u0=0.72, u1=0.85, h=0.08)],
        paired=[dict(u=0.26, len=0.13, low=0.5, fan=1.1), dict(u=0.46, len=0.1, low=0.95, splay=0.25, out=0.3)],
        barbels=[(0.02, 0.7, 0.03, 0.7), (0.035, 0.9, 0.042, 0.9)]))


def moonfish(name):
    """月光鱼：22 厘米（连飘尾），想象出来的稀有鱼。身子是半透明的银蓝，背上一弯月牙形的亮斑，体侧一排夜里会亮的小光点（部件 glow）；
    背鳍、臀鳍、尾鳍都是长长的纱，尾巴拖得比身子还长，鳍梢淡成月白"""
    b0, b1, b2 = hexc('#6f8fc9'), hexc('#b9cdea'), hexc('#eef4ff')

    def col(u, th, cs, sn):
        c = mix(b1, b0, smooth(0.0, 0.95, sn))
        c = mix(c, b2, 0.6 * bump(sn, 0.05, 0.3))
        # 背上的月牙
        d = math.hypot((u - 0.36) * 3.2, cs * 1.0)
        if sn > 0.3:
            c = mix(c, hexc('#fffbe0'), 0.9 * bump(d, 0.42, 0.09) * smooth(0.3, 0.38, u))
        return c
    fin = hexc('#9db6e6')

    def lights(a, L, Lb, fd, fv, fw, zmid):
        # 体侧一排光点（小而扁的珠子，略浮出鱼身），额上一颗大的
        for sx in (-1, 1):
            for k in range(9):
                u = 0.26 + 0.07 * k
                r = (0.0085 - 0.0005 * k) * L
                p = Vector((sx * (fw(u) * L + r * 0.2), -u * Lb, zmid(u) * L + 0.012 * L * math.sin(k * 0.8)))
                a.blob(r, p, (0.45, 1, 1), hexc('#f4f8ff'), subdiv=2, bump=0, mat='glow')
        a.blob(0.012 * L, (0, -0.1 * Lb, zmid(0.1) * L + fd(0.1) * L * 0.96), (1, 1.2, 0.45), hexc('#fffbe6'), subdiv=2, bump=0, mat='glow')
    t = _fish(name, dict(
        L=0.22, body=0.5, head=0.26, scales=(14, 14, 0.05), colour=col, fin=fin, fin_tip=hexc('#e9f0ff'), fin_edge=hexc('#ffffff'), belly=hexc('#f3f6ff'), belly_k=0.7,
        iris=hexc('#dfe8ff'),
        dorsal=[(0, 0.01), (0.1, 0.06), (0.3, 0.1), (0.5, 0.105), (0.8, 0.055), (1, 0.03)],
        ventral=[(0, 0.01), (0.1, 0.055), (0.3, 0.09), (0.5, 0.095), (0.8, 0.05), (1, 0.028)],
        width=[(0, 0.008), (0.1, 0.04), (0.3, 0.055), (0.5, 0.054), (0.8, 0.026), (1, 0.01)],
        eye=(0.16, 0.022, 0.024), rings=52, segs=28,
        tail=dict(fork=0.5, spread=0.26, sub=6, n=21, wave=0.03, p=0.9),
        dorsals=[dict(u0=0.34, u1=0.9, h=0.2, n=17, lean=1.5, a0=0.2, a1=0.75, p=0.7)], anals=[dict(u0=0.62, u1=0.92, h=0.16, n=10, lean=1.6)],
        paired=[dict(u=0.3, len=0.2, low=0.5, fan=0.7), dict(u=0.5, len=0.24, low=0.95, splay=0.3, out=0.4, fan=0.5)],
        extras=[lights]))
    return t


# ====================================================================== 青虾
def shrimp(name):
    """青虾（河虾）：身长 9 厘米。半透明的青灰色，头胸甲一整块、前面一根带锯齿的额剑，腹部六节一节压一节往下弯，尾扇五片；
    两根长须、四根短须、一对比身子还长的细螯（青虾的第二对步足）、四对细步足、腹下五对游泳足。原点在嘴（额剑根下面），身子往 -y"""
    a = Asset(name)
    rng = a.rng
    L = 0.09
    c0, c1, cd = hexc('#93a89a'), hexc('#c7d3c4'), hexc('#4f6457')
    # 身体的中线：头胸甲是直的，腹部往下弯
    N = 80
    sp, tg = [], []
    p = Vector((0, 0, 0.004))
    for i in range(N + 1):
        u = i / N
        ang = -1.15 * smooth(0.4, 1.0, u) ** 1.2
        d = Vector((0, -math.cos(ang), math.sin(ang)))
        sp.append(p.copy())
        tg.append(d)
        p = p + d * (L / N)

    def rad(u):
        r = interp(u, [0, 0.05, 0.2, 0.42, 0.7, 0.9, 1.0], [0.004, 0.0095, 0.0118, 0.0112, 0.0085, 0.0055, 0.0035])
        if u > 0.42:
            s = (u - 0.42) / 0.58 * 6
            r *= 1 + 0.07 * math.sin(math.pi * (s - math.floor(s))) ** 0.6
        return r

    def fn(uu, vv):
        i = min(N, int(vv * N))
        u = vv
        c, d = sp[i], tg[i]
        nrm = Vector((0, d.z, -d.y))          # 截面里的「上」
        nrm = Vector((0, -d.z, d.y)) if nrm.z < 0 else nrm
        th = 2 * math.pi * uu
        r = rad(u)
        q = c + Vector((1, 0, 0)) * (r * 0.78 * math.cos(th)) + nrm * (r * (1.05 if math.sin(th) > 0 else 0.9) * math.sin(th))
        sn = math.sin(th)
        col = mix(c1, c0, smooth(-0.6, 0.6, sn))
        if u > 0.42:
            s = (u - 0.42) / 0.58 * 6
            f = s - math.floor(s)
            col = mix(col, cd, 0.55 * bump(f, 0.0, 0.07) + 0.55 * bump(f, 1.0, 0.07))          # 每节后缘一道深边
            col = tint(col, 0.05 * bump(f, 0.5, 0.25))
        else:
            col = mix(col, cd, 0.35 * bump(u, 0.41, 0.012))
            col = mix(col, hexc('#6f8a7c'), 0.4 * smooth(0.3, 0.9, sn) * (0.5 + 0.5 * noise.noise(Vector((u * 60, th * 3, 0)))))
        if noise.noise(Vector((u * 130, th * 9, 3.0))) > 0.42:
            col = tint(col, -0.1)
        return q, col
    grid(a, 'toon', 16, N, fn, cap0=(sp[0] + Vector((0, 0.003, 0)), c0), cap1=(sp[-1] + tg[-1] * 0.002, c0))
    # 额剑：往前伸的一根扁刺，上缘一排小锯齿
    rs = [Vector((0, -0.004, 0.012)), Vector((0, 0.008, 0.0145)), Vector((0, 0.02, 0.0155)), Vector((0, 0.03, 0.018))]
    a.tube(rs, [0.0022, 0.0017, 0.0012, 0.0004], cd, segs=5, flat=0.5)
    for k in range(7):
        t = k / 7
        q = rs[0].lerp(rs[-1], 0.1 + 0.8 * t) + Vector((0, 0, 0.0012))
        a.quad([q + Vector((0, -0.0014, 0)), q + Vector((0, 0.0016, 0)), q + Vector((0, 0.0012, 0.0022))], color=cd, mat='leaf')
    # 眼：两根短柄上各一颗黑珠
    for sx in (-1, 1):
        a.tube([(sx * 0.004, -0.003, 0.009), (sx * 0.0085, 0.001, 0.0115)], [0.0013, 0.0015], c0, segs=5)
        a.blob(0.0027, (sx * 0.0095, 0.002, 0.012), (1, 1, 1), hexc('#141414'), subdiv=2, bump=0)
        a.blob(0.0008, (sx * 0.0108, 0.0035, 0.0132), (1, 1, 1), (1, 1, 1), subdiv=1, bump=0)
        # 长须：往前、往外甩出去再弯回来，比身子还长
        pts = [Vector((sx * 0.004, 0.001, 0.007))]
        for k in range(1, 15):
            t = k / 14
            pts.append(Vector((sx * (0.004 + 0.05 * t + 0.02 * math.sin(math.pi * t)), 0.001 + 0.06 * math.sin(math.pi * 0.62 * t) - 0.09 * t * t, 0.007 + 0.03 * math.sin(math.pi * t) - 0.015 * t)))
        a.tube(pts, [0.0011 - 0.0009 * k / 14 for k in range(15)], hexc('#b66f4e'), segs=4)
        # 短须：两根，分叉
        for (dx, dz) in ((0.4, 0.5), (0.9, 0.15)):
            a.tube([(sx * 0.0025, 0.002, 0.008), (sx * (0.0025 + 0.008 * dx), 0.014, 0.008 + 0.008 * dz), (sx * (0.0025 + 0.02 * dx), 0.026, 0.008 + 0.014 * dz)],
                   [0.0008, 0.0006, 0.0002], hexc('#b98a6a'), segs=4)
        # 触角鳞片：眼睛外侧一片薄片
        a.quad([(sx * 0.005, 0.0, 0.006), (sx * 0.011, 0.004, 0.006), (sx * 0.0095, 0.016, 0.007), (sx * 0.005, 0.012, 0.0065)], color=c1, mat='leaf')
        # 大螯（第二步足）：三节细长的臂，头上一把小钳
        j = [Vector((sx * 0.006, -0.012, -0.004)), Vector((sx * 0.02, -0.004, -0.012)), Vector((sx * 0.03, 0.022, -0.008)), Vector((sx * 0.027, 0.055, -0.002)),
             Vector((sx * 0.024, 0.075, 0.001))]
        a.tube(j, [0.0016, 0.0017, 0.0019, 0.0022, 0.0017], hexc('#5f7f86'), segs=6, color2=hexc('#3f6470'))
        for dz in (-0.0014, 0.0014):
            a.tube([j[-1], j[-1] + Vector((-sx * 0.001, 0.008, dz * 1.6)), j[-1] + Vector((-sx * 0.0015, 0.015, dz * 0.4))], [0.0013, 0.001, 0.0003], hexc('#3f6470'), segs=4)
        # 步足：四对细腿，折两折
        for k in range(4):
            y0 = -0.008 - 0.0065 * k
            a.tube([(sx * 0.005, y0, -0.004), (sx * (0.012 + 0.002 * k), y0 + 0.004 - 0.003 * k, -0.013), (sx * (0.017 + 0.002 * k), y0 + 0.012 - 0.006 * k, -0.007),
                    (sx * (0.02 + 0.002 * k), y0 + 0.02 - 0.009 * k, -0.017)], [0.001, 0.0009, 0.0008, 0.0003], hexc('#9fb3a6'), segs=4)
        # 游泳足：腹下五对小薄片
        for k in range(5):
            i = int(N * (0.46 + 0.085 * k))
            c, d = sp[i], tg[i]
            dn = Vector((0, d.z, -d.y))
            dn = -dn if dn.z > 0 else dn
            b0 = c + dn * rad(i / N) * 0.8 + Vector((sx * 0.003, 0, 0))
            a.quad([b0, b0 + d * 0.004, b0 + dn * 0.009 + d * 0.006 + Vector((sx * 0.002, 0, 0)), b0 + dn * 0.008 - d * 0.001 + Vector((sx * 0.002, 0, 0))],
                   color=c1, mat='leaf', colors=[c0, c0, c1, c1])
    # 尾扇：中间一根尖的尾节，两边各两片
    e, d = sp[-1], tg[-1]
    up = Vector((0, -d.z, d.y))
    up = -up if up.z < 0 else up
    a.tube([e - d * 0.004, e + d * 0.012], [0.0028, 0.0005], cd, segs=5, flat=0.5)
    for sx in (-1, 1):
        for k, (spl, ln) in enumerate(((0.35, 0.016), (0.85, 0.0145))):
            dv = (d * math.cos(spl) + Vector((sx, 0, 0)) * math.sin(spl)).normalized()
            sd = Vector((sx, 0, 0)).cross(up) * 0 + (dv.cross(up)).normalized()
            pts = [e + dv * ln * t + sd * (0.0045 * math.sin(math.pi * min(1.0, t * 1.05)) * s_) + up * (0.0008 * k) for (t, s_) in
                   ((0.15, 1), (0.5, 1), (0.85, 0.9), (1.0, 0.0), (0.85, -0.9), (0.5, -1), (0.15, -1))]
            fan(a, 'leaf', e - d * 0.002, pts, [mix(c1, hexc('#7fa0a8'), 0.5 if 0 < i < 6 else 0.2) for i in range(7)], root_color=c0)
    a.opts['leaf'] = {'plain_normals': True}
    return craft.finish(a, (72, 16, 1.0), floor=False, extra={'q': (125, 30, 1.0)})


# ====================================================================== 大闸蟹
def crab(name):
    """大闸蟹：壳宽 8 厘米。青灰带橄榄绿的背壳（前缘四个额齿、两侧各四个尖齿、壳面一个 H 形的沟），白肚，金黄的爪尖，
    两只大螯上一团深褐色的绒毛，八条腿各三节、带尖爪。原点在嘴（两眼之间的前缘），身子往 -y，背朝 +z"""
    a = Asset(name)
    rng = a.rng
    shell, shell_d, bellyc = hexc('#5b6a4a'), hexc('#3c4a36'), hexc('#efe8d2')
    leg, legd, tipc = hexc('#6e7a52'), hexc('#4a5438'), hexc('#d9a441')
    fur = hexc('#3b2a20')
    W, D, Hh = 0.04, 0.035, 0.014          # 半宽、半深、半高
    cy = -D

    def fn(uu, vv):
        th = 2 * math.pi * uu          # 绕一圈：0 = +x（右），pi/2 = +y（前）
        ph = math.pi * (vv - 0.5)      # -pi/2 肚底 … +pi/2 背顶
        cs, sn = math.cos(th), math.sin(th)
        # 背壳的轮廓：前缘平、前侧缘带齿、后面收窄
        out = 1.0
        front = max(0.0, sn)
        out *= 1 - 0.18 * front ** 3                                  # 前缘压平
        out *= 1 - 0.2 * max(0.0, -sn) ** 2 * (1 - abs(cs)) - 0.06 * max(0.0, -sn)      # 后面收
        a_side = abs(cs)
        if sn > -0.1:
            if a_side > 0.45:        # 侧齿：四个往前外的尖
                t = (math.atan2(sn, a_side)) / 1.1
                out += 0.075 * (abs(math.sin(t * math.pi * 4.2)) ** 3) * smooth(-0.1, 0.1, sn) * math.cos(ph) ** 2
            elif sn > 0.8:           # 额齿：四个小圆齿
                out += 0.03 * abs(math.sin(cs / 0.45 * math.pi * 2)) ** 1.5 * math.cos(ph) ** 2
        k = math.cos(ph)
        up = math.sin(ph)
        zz = Hh * (up if up > 0 else up * 0.75)
        e = k ** 0.7
        p = Vector((W * out * cs * e, cy + D * out * sn * e, zz + (0.003 * (1 - (cs * cs)) if up > 0.3 else 0)))
        # 颜色
        if up < -0.15:
            c = mix(bellyc, hexc('#d9cfb0'), 0.5 * noise.noise(p * 90) + 0.3)
        else:
            c = mix(shell, shell_d, 0.5 + 0.5 * noise.noise(p * 60))
            c = mix(c, hexc('#7d8a5c'), 0.35 * smooth(0.25, 0.0, up))          # 壳缘浅一点
            # H 形的沟、两边的鼓包
            x, y = p.x / W, (p.y - cy) / D
            hgr = bump(abs(x), 0.22, 0.05) * smooth(0.45, 0.25, abs(y)) + bump(y, -0.02, 0.05) * smooth(0.26, 0.18, abs(x))
            c = mix(c, hexc('#28331f'), 0.7 * min(1.0, hgr) * smooth(0.3, 0.6, up))
            p.z -= 0.0012 * min(1.0, hgr) * smooth(0.3, 0.6, up)
            p.z += 0.0015 * bump(abs(x), 0.5, 0.2) * bump(y, 0.1, 0.4) * smooth(0.3, 0.7, up)
        return p, c
    grid(a, 'toon', 72, 20, fn, cap0=((0, cy, -Hh * 0.75), bellyc), cap1=((0, cy, Hh + 0.003), shell))
    # 肚脐（腹甲）：肚底一块尖的盖（公蟹的尖脐）
    fan(a, 'toon', (0, cy - 0.022, -Hh * 0.76), [(0.012 * math.sin(t), cy - 0.022 + 0.03 * (1 - abs(t) / 1.6) * (1 if abs(t) < 1.5 else 0) + 0.0, -Hh * 0.77)
                                                 for t in (1.6, 0.9, 0.3, 0.0, -0.3, -0.9, -1.6)], [tint(bellyc, -0.08)] * 7, root_color=tint(bellyc, -0.12))
    # 眼：前缘两个短柄
    for sx in (-1, 1):
        a.tube([(sx * 0.011, -0.004, 0.004), (sx * 0.0125, 0.002, 0.0075)], [0.0018, 0.0016], shell_d, segs=6)
        a.blob(0.0026, (sx * 0.0128, 0.003, 0.0085), (1, 1, 1), hexc('#151515'), subdiv=2, bump=0)
        # 口器：两片小颚
        a.blob(1.0, (sx * 0.004, -0.002, -0.004), (0.004, 0.003, 0.0045), tint(bellyc, -0.06), subdiv=1, bump=0)
    # 八条腿：每边四条，三节（长节、腕前节、指节），指节是尖的、金黄色
    for sx in (-1, 1):
        for k in range(4):
            ang = math.radians(8 - 30 * k)          # 第一条朝前外，最后一条朝后
            root = Vector((sx * W * 0.82 * math.cos(math.radians(-10 - 22 * k)), cy + D * 0.75 * math.sin(math.radians(-10 - 22 * k)) + 0.006, -0.002))
            dv = Vector((sx * math.cos(ang), math.sin(ang), 0))
            ln = (0.026, 0.03, 0.029, 0.023)[k]
            j1 = root + dv * ln + Vector((0, 0, 0.012))
            j2 = j1 + (dv * 0.8 + Vector((0, -0.25, 0))).normalized() * ln * 0.9 + Vector((0, 0, -0.012))
            j3 = j2 + (dv * 0.5 + Vector((0, -0.5, 0))).normalized() * ln * 0.55 + Vector((0, 0, -0.014))
            a.tube([root, (root + j1) / 2 + Vector((0, 0, 0.003)), j1], [0.005, 0.0058, 0.0044], leg, segs=7, color2=legd, flat=0.55)
            a.tube([j1, (j1 + j2) / 2, j2], [0.0042, 0.0044, 0.003], legd, segs=7, color2=leg, flat=0.55)
            a.tube([j2, (j2 + j3) / 2, j3], [0.0028, 0.002, 0.0003], mix(leg, tipc, 0.4), segs=6, color2=tipc)
            a.blob(0.0052, j1, (1, 1, 0.7), leg, subdiv=1, bump=0)
            # 腿上的细毛：前两节后缘一排短毛
            for i in range(6):
                q = j1.lerp(j2, 0.1 + 0.15 * i)
                a.quad([q, q + Vector((0, -0.003, -0.0015)), q + (j2 - j1).normalized() * 0.0016], color=fur, mat='leaf')
        # 大螯：臂、腕、掌（一团绒毛）、两个指
        sh = Vector((sx * W * 0.62, cy + D * 0.86, -0.003))
        el = sh + Vector((sx * 0.02, 0.018, 0.004))
        wr = el + Vector((-sx * 0.008, 0.02, 0.0))
        a.tube([sh, (sh + el) / 2 + Vector((0, 0, 0.003)), el], [0.005, 0.0062, 0.0052], leg, segs=8, color2=legd, flat=0.7)
        a.tube([el, wr], [0.0054, 0.006], legd, segs=8, flat=0.75)
        pc = wr + Vector((-sx * 0.006, 0.01, 0.0))
        a.blob(1.0, pc, (0.0105, 0.014, 0.0088), mix(leg, hexc('#8a8f63'), 0.4), subdiv=3, bump=0.03)
        for i in range(22):          # 绒毛：掌上一团深褐色的小毛簇
            th = rng.uniform(0, 6.28)
            ph = rng.uniform(-0.5, 1.2)
            d = Vector((math.cos(th) * math.cos(ph) * 0.0098, math.sin(th) * math.cos(ph) * 0.012 - 0.003, math.sin(ph) * 0.008))
            a.blob(rng.uniform(0.0022, 0.0036), pc + d, (1, 1, 1), vary(fur, rng, 0.04, 0.03), subdiv=1, bump=0.5)
        for (dz, ln2, curve) in ((0.0052, 0.024, -0.0035), (-0.0048, 0.021, 0.004)):
            f0 = pc + Vector((-sx * 0.002, 0.009, dz))
            a.tube([f0, f0 + Vector((-sx * 0.004, ln2 * 0.55, curve * 0.3)), f0 + Vector((-sx * 0.007, ln2, curve))], [0.0048, 0.0036, 0.0008], hexc('#e8dfc4'), segs=7,
                   color2=hexc('#fbf7ea'))
    a.opts['leaf'] = {'plain_normals': True}
    return craft.finish(a, (22, 40, 1.0), floor=False, extra={'under': (22, -40, 1.0)})


# ====================================================================== 水草
def weed(name):
    """一团水草（钓空了）：钩上缠着的几根带状的水草叶、两根细茎，叶上趴着一只小螺蛳。原点是钩住的那一头，往 -y 拖 20 厘米"""
    a = Asset(name)
    rng = a.rng
    g0, g1, g2 = hexc('#3f6b3a'), hexc('#6c9a48'), hexc('#a9b85a')
    for i in range(11):
        ln = rng.uniform(0.11, 0.21)
        w = rng.uniform(0.006, 0.011)
        dx, dz = rng.uniform(-0.035, 0.035), rng.uniform(-0.02, 0.02)
        ph, fr = rng.uniform(0, 6.28), rng.uniform(1.2, 2.6)
        tw0 = rng.uniform(0, 3.14)
        n = 12
        c = vary(rng.choice((g0, g1, g1)), rng, 0.05, 0.05)
        P, S_ = [], []
        for k in range(n + 1):
            t = k / n
            P.append(Vector((dx * t + 0.012 * math.sin(ph + fr * 3 * t) * t, -ln * t, dz * t + 0.012 * math.cos(ph * 1.3 + fr * 2 * t) * t)))
            tw = tw0 + 2.2 * t
            S_.append(Vector((math.cos(tw), 0, math.sin(tw))) * (w * (0.5 + 0.5 * math.sin(math.pi * min(1.0, 0.15 + 0.9 * t)) ** 0.6) * (1 if k < n else 0.15)))
        for k in range(n):
            t0, t1 = k / n, (k + 1) / n
            ca, cb = mix(c, g2, 0.5 * t0 * t0), mix(c, g2, 0.5 * t1 * t1)
            # 每片叶中间一道叶脉（颜色在中线断开）
            a.quad([P[k] - S_[k], P[k], P[k + 1], P[k + 1] - S_[k + 1]], mat='leaf', colors=[tint(ca, -0.05), tint(ca, 0.06), tint(cb, 0.06), tint(cb, -0.05)])
            a.quad([P[k], P[k] + S_[k], P[k + 1] + S_[k + 1], P[k + 1]], mat='leaf', colors=[tint(ca, 0.06), tint(ca, -0.03), tint(cb, -0.03), tint(cb, 0.06)])
    # 细茎（轮叶黑藻那种）：一根茎上一轮轮的小叶
    for sx in (-1, 1):
        pts = [Vector((sx * 0.008 * k / 9 + 0.006 * math.sin(k * 0.9 + sx), -0.019 * k, -0.004 * k / 9 + 0.005 * math.cos(k * 0.7))) for k in range(10)]
        a.tube(pts, [0.0016 - 0.0009 * k / 9 for k in range(10)], g0, segs=5)
        for k in range(1, 10):
            for j in range(5):
                ang = 2 * math.pi * j / 5 + k * 0.6
                d = Vector((math.cos(ang), -0.5, math.sin(ang))).normalized()
                sd = d.cross(Vector((0, 1, 0))).normalized()
                q = pts[k]
                a.quad([q, q + d * 0.006 + sd * 0.0016, q + d * 0.013, q + d * 0.006 - sd * 0.0016], color=vary(g1, rng, 0.05, 0.04), mat='leaf')
    # 缠在钩上的那一小团、一只小螺蛳
    for i in range(6):
        a.blob(rng.uniform(0.004, 0.007), (rng.uniform(-0.006, 0.006), rng.uniform(-0.012, 0.002), rng.uniform(-0.005, 0.005)), (1, 1.3, 1), vary(g0, rng, 0.04, 0.04), subdiv=1, bump=0.3)
    sc = hexc('#6b5a3c')
    a.lathe([(0.0, -0.009), (0.0045, -0.007, tint(sc, -0.08)), (0.0062, -0.002, sc), (0.0048, 0.003, tint(sc, 0.06)), (0.0052, 0.005, sc), (0.0032, 0.009, tint(sc, 0.08)),
             (0.0035, 0.0105, sc), (0.0014, 0.014), (0.0, 0.0155)], (0.012, -0.085, 0.004), segs=10, color=sc, rot=(1.2, 0.4, 0.3))
    a.opts['leaf'] = {'plain_normals': True}
    return craft.finish(a, (25, 35, 1.0), floor=False)


# ====================================================================== 钓竿、浮漂、鱼篓、马扎
ROD_LEN = 2.6            # 握把（原点）到竿梢
ROD_BUTT = 0.2           # 握把后面还有多长
ROD_SAG = 0.075          # 竿梢比握把低多少（竹竿自己的一点弯）


def rod_point(t):
    """竿的中线：t = 0 握把、1 竿梢。竿朝 +y，梢微微往下弯"""
    return Vector((0, ROD_LEN * t, -ROD_SAG * max(0.0, t) ** 2.4))


def fishing_rod(name):
    """竹钓竿：全长 2.8 米。原点在握把正中，竿朝 +y（Unity 里是 +z）、微微往下弯，竿梢在 (0, 2.6, -0.075)（Blender 坐标）。
    一节节的竹子：节上鼓一圈、一道深色的环，节间的颜色各不相同，越往梢越细；握把缠着深色的线，竿尾一个木堵头，竿梢一个系线的小铜环"""
    a = Asset(name)
    rng = a.rng
    cb = [hexc('#c9a657'), hexc('#bf9a4a'), hexc('#d4b56a'), hexc('#b9a05a')]
    # 竹节的位置：靠把的节间短，中间长，梢上又短
    nodes, y = [], -ROD_BUTT + 0.05
    while y < ROD_LEN - 0.03:
        nodes.append(y)
        t = clamp(y / ROD_LEN)
        y += 0.1 + 0.16 * math.sin(math.pi * (0.15 + 0.75 * t)) + rng.uniform(-0.012, 0.012)
    tones = [vary(rng.choice(cb), rng, 0.04, 0.04) for _ in range(len(nodes) + 1)]

    def fn(uu, vv):
        yv = -ROD_BUTT + (ROD_LEN + ROD_BUTT) * vv
        t = yv / ROD_LEN
        r = 0.0125 - 0.0096 * clamp((yv + ROD_BUTT) / (ROD_LEN + ROD_BUTT)) ** 0.85
        seg = sum(1 for n in nodes if n < yv)
        c = tones[seg]
        # 节：鼓一圈，节上一道深环，环下一圈白霜
        dn = min(abs(yv - n) for n in nodes)
        k = bump(dn, 0.0, 0.006)
        r *= 1 + 0.16 * k
        c = mix(c, hexc('#6f5226'), 0.8 * bump(dn, 0.0, 0.0028))
        below = min((yv - n for n in nodes if n <= yv), default=1.0)
        c = mix(c, hexc('#e9dfb8'), 0.35 * smooth(0.02, 0.004, below) * smooth(0.0, 0.004, below))
        th = 2 * math.pi * uu
        # 顺着竹丝的细纹、几处褐斑
        c = tint(c, 0.03 * math.sin(uu * 2 * math.pi * 5 + seg))
        if noise.noise(Vector((yv * 9, math.cos(th) * 2.5, math.sin(th) * 2.5 + seg))) > 0.5:
            c = mix(c, hexc('#8a6a35'), 0.5)
        p = rod_point(t) + Vector((r * math.cos(th), 0, r * math.sin(th)))
        return p, c
    grid(a, 'toon', 10, 300, fn, flip=True, cap0=(rod_point(-ROD_BUTT / ROD_LEN) + Vector((0, -0.001, 0)), tones[0]), cap1=(rod_point(1.0) + Vector((0, 0.002, 0)), tones[-1]))
    # 握把：缠线（一圈圈的线，两头各一道红线扎口）
    wrap, red = hexc('#2f3540'), C('cloth_red')
    prof = []
    n = 46
    for k in range(n + 1):
        yy = -0.125 + 0.25 * k / n
        col = red if (k < 3 or k > n - 3) else (wrap if k % 2 else tint(wrap, 0.07))
        rr = 0.0125 - 0.0096 * clamp((yy + ROD_BUTT) / (ROD_LEN + ROD_BUTT)) ** 0.85
        prof.append((rr + 0.0012 + (0.0009 if k % 2 else 0.0), yy, col))
    a.lathe(prof, segs=14, color=wrap, rot=(-math.pi / 2, 0, 0), outward=True)
    # 竿尾的木堵头
    a.lathe([(0.0, -0.022), (0.009, -0.02, C('wood_dark')), (0.0145, -0.012, C('wood')), (0.0152, -0.004, C('wood_lit')), (0.0135, 0.004, C('wood')), (0.0125, 0.008)],
            (0, -ROD_BUTT, 0), segs=14, color=C('wood'), rot=(-math.pi / 2, 0, 0))
    # 竿梢：红线扎一段，头上一个小铜环（系鱼线）
    tip = rod_point(1.0)
    for k in range(6):
        p = rod_point(1.0 - 0.006 * (k + 1))
        a.lathe([(0.0036, -0.0022), (0.0041, 0.0, red), (0.0036, 0.0022)], p, segs=8, color=red, rot=(-math.pi / 2, 0, 0), outward=True)
    ring = [tip + Vector((0, 0.006 + 0.005 * math.cos(t), 0.005 * math.sin(t))) for t in [2 * math.pi * k / 12 for k in range(13)]]
    a.tube(ring, 0.0011, hexc('#d6b25a'), segs=5, cap=False)
    return craft.finish(a, (62, 18, 1.0), floor=False, extra={'grip': (35, 20, 0.2)})


def fishing_bobber(name):
    """浮漂：全长 19 厘米。原点在漂身正中（吃水线），竖着（+z 朝上）。纺锤形的漂身下白上红、中间一道金线，
    上面一根细长的漂尾（红黄黑相间的目数、顶上一颗红珠），下面一截漂脚、一个系线的小铜环（线系在 (0, 0, -0.078)）"""
    a = Asset(name)
    red, white, gold, black, yel = hexc('#e23b2c'), hexc('#fbf8ee'), hexc('#d9b24a'), hexc('#1f1d1d'), hexc('#f6d443')
    prof = []
    n = 26
    for k in range(n + 1):
        t = k / n
        z = -0.045 + 0.09 * t
        r = 0.0118 * math.sin(math.pi * (0.06 + 0.9 * t)) ** 0.8 * (1.12 - 0.3 * t) + 0.0012
        c = white if t < 0.47 else gold if t < 0.52 else red
        if 0.47 <= t < 0.52:
            r += 0.0004
        prof.append((r, z, c))
    prof = [(0.0, -0.0455, white)] + prof + [(0.0, 0.0455)]
    a.lathe(prof, segs=20, color=red)
    # 漂尾：细杆上一段段的颜色
    z = 0.044
    bands = [(red, 0.012), (yel, 0.008), (red, 0.012), (black, 0.003), (yel, 0.008), (red, 0.012), (black, 0.003), (yel, 0.008), (red, 0.01)]
    pr = []
    for c, ln in bands:
        pr.append((0.0013, z, c))
        z += ln
    pr.append((0.0013, z, red))
    a.lathe(pr, segs=8, color=red, outward=True)
    a.blob(0.003, (0, 0, z + 0.0015), (1, 1, 1.1), red, subdiv=2, bump=0)
    # 漂脚和铜环
    a.lathe([(0.0015, -0.07, black), (0.0015, -0.044)], segs=8, color=black, outward=True)
    ring = [Vector((0.0035 * math.cos(t), 0, -0.0745 + 0.0035 * math.sin(t))) for t in [2 * math.pi * k / 12 for k in range(13)]]
    a.tube(ring, 0.0009, gold, segs=5, cap=False)
    return craft.finish(a, (25, 12, 1.0), floor=False)


def fish_basket(name):
    """竹编鱼篓：高 30 厘米，腹径 30。原点在地面中心。大肚、收颈、撇口；篓身是一根根竖的篾骨和一圈圈横的篾条一上一下编的
    （每一格都是真的凹凸），口沿一圈粗的缠边，肩上两个耳、一根提绳，里面是空的"""
    a = Asset(name)
    rng = a.rng
    S = 'straw'
    st, sl, sd = C('straw'), C('straw_lit'), C('straw_dark')
    H = 0.3
    NS, NR = 40, 34          # 竖的篾骨、横的篾条
    row_c = [vary(rng.choice((st, sl, mix(st, sl, 0.5))), rng, 0.04, 0.04) for _ in range(NR + 1)]

    def prof(v):
        return interp(v, [0, 0.06, 0.25, 0.45, 0.65, 0.82, 0.9, 1.0], [0.1, 0.118, 0.142, 0.15, 0.135, 0.1, 0.093, 0.104])

    def fn(uu, vv):
        th = 2 * math.pi * uu
        r = prof(vv)
        aS = uu * NS
        b = vv * NR
        row = int(math.floor(b))
        fb = b - row
        over = math.cos(math.pi * aS) * (1 if row % 2 == 0 else -1)          # 这一格横篾在上（正）还是在下（负）
        hw = 0.0036 * over * math.sin(math.pi * fb) ** 0.5
        groove = -0.0022 * bump(fb, 0.0, 0.1) - 0.0022 * bump(fb, 1.0, 0.1)
        c = row_c[row]
        if over < -0.25:          # 横篾钻到下面去的地方露出竖的篾骨
            c = mix(sd, tint(sd, 0.06), 0.5 + 0.5 * math.sin(aS * math.pi * 2))
            hw = 0.0022 * (-over) * 0.6
        c = tint(c, 0.05 * over)
        c = mix(c, tint(sd, -0.08), 0.6 * (bump(fb, 0.0, 0.08) + bump(fb, 1.0, 0.08)))
        rr = r + hw + groove
        return Vector((rr * math.cos(th), rr * math.sin(th), 0.008 + (H - 0.008) * vv)), c
    grid(a, S, NS * 3, NR * 2, fn, cap0=((0, 0, 0.004), sd))
    # 里面（暗），口沿一圈缠边（斜着一道道缠的篾）
    grid(a, S, 40, 8, lambda uu, vv: (Vector(((prof(vv) - 0.007) * math.cos(2 * math.pi * uu), (prof(vv) - 0.007) * math.sin(2 * math.pi * uu), 0.014 + (H - 0.014) * vv)),
                                     tint(sd, -0.12 - 0.12 * (1 - vv))), flip=True, cap0=((0, 0, 0.014), tint(sd, -0.3)))

    def rim(uu, vv):
        th = 2 * math.pi * uu
        ph = 2 * math.pi * vv
        R0, r0 = prof(1.0) - 0.002, 0.0085
        tw = math.sin(uu * 2 * math.pi * 40 + ph * 1.0)
        rr = r0 * (1 + 0.1 * tw)
        return Vector(((R0 + rr * math.cos(ph)) * math.cos(th), (R0 + rr * math.cos(ph)) * math.sin(th), H + rr * math.sin(ph))), mix(sl, sd, 0.5 - 0.5 * tw)
    grid(a, S, 120, 6, rim)
    # 底：一圈圈盘出来的
    a.lathe([(0.0, 0.0, sd), (0.03, 0.0, st), (0.06, 0.0, sd), (0.085, 0.0, st), (0.103, 0.003, sd), (0.104, 0.01)], segs=40, color=sd, mat=S)
    # 两个耳和提绳
    rope, rope_d = C('rope'), C('rope_dark')
    for sx in (-1, 1):
        ear = [Vector((sx * (prof(0.86) + 0.004 + 0.012 * math.sin(t)), 0, H * 0.86 + 0.014 * math.cos(t))) for t in [math.pi * k / 8 for k in range(9)]]
        a.tube(ear, 0.004, sd, segs=6, mat=S)
    pts = []
    for k in range(25):
        t = k / 24
        ang = math.pi * t
        pts.append(Vector((-(prof(0.86) + 0.016) * math.cos(ang), 0.05 * math.sin(ang) * math.sin(ang * 2), H * 0.86 + 0.16 * math.sin(ang) ** 0.8)))
    for s_ in range(2):
        a.tube([p + Vector((0.003 * math.cos(i * 1.6 + s_ * math.pi), 0.003 * math.sin(i * 1.6 + s_ * math.pi), 0)) for i, p in enumerate(pts)], 0.0038,
               rope if s_ == 0 else rope_d, segs=5)
    return craft.finish(a, (25, 28, 1.0), ao=True, dist=0.2, extra={'top': (10, 62, 1.0)})


def fishing_stool(name):
    """小马扎：高 28 厘米，坐面 34 × 28。原点在地面中心。两副木框交叉成 X（中间一根销子），上面两根横档之间绷着几道宽布带（坐面微微下兜）"""
    a = Asset(name)
    rng = a.rng
    W = 'wood'
    wd, wl, wk = C('wood'), C('wood_lit'), C('wood_dark')
    Ht, Dy = 0.28, 0.14
    ln = math.hypot(2 * Dy, Ht)
    ang = math.atan2(2 * Dy, Ht)
    for (xo, sg) in ((0.17, 1), (0.147, -1)):          # 外框、内框
        for sx in (-1, 1):
            # 腿：从一边的地面斜到另一边的坐面
            a.box((0.022, 0.03, ln - 0.022), (sx * xo, 0, Ht / 2 + 0.002), rot=(sg * ang, 0, 0), color=vary(wd, rng, 0.03, 0.02), bevel=0.005, mat=W, base=False)
        # 上横档（圆的，布带绕在上面）、下横档
        a.cyl(0.013, 2 * xo + 0.03, (-xo - 0.015, sg * Dy, Ht), wl, segs=12, rot=(0, math.pi / 2, 0), mat=W)
        a.cyl(0.01, 2 * xo, (-xo, -sg * Dy * 0.86, Ht * 0.07), wd, segs=10, rot=(0, math.pi / 2, 0), mat=W)
    # 交叉处的销子
    for sx in (-1, 1):
        a.cyl(0.006, 0.05, (sx * 0.1585 - 0.025, 0, Ht / 2), hexc('#3b3a3c'), segs=8, rot=(0, math.pi / 2, 0))
        a.blob(0.008, (sx * 0.186, 0, Ht / 2), (0.5, 1, 1), hexc('#55545a'), subdiv=1, bump=0)
    # 坐面：五道布带（蓝白相间），两头绕过横档，中间微微下兜
    navy, cream = C('navy'), hexc('#efe6cf')
    for i in range(5):
        x0 = -0.135 + 0.0675 * i
        c = navy if i % 2 == 0 else cream

        def fn(uu, vv, x0=x0, c=c):
            y = -Dy + 2 * Dy * vv
            z = Ht + 0.0145 - 0.022 * math.sin(math.pi * vv) - 0.004 * math.sin(math.pi * uu)
            col = tint(c, 0.04 * math.sin(vv * 90) - 0.05 * bump(uu, 0.0, 0.08) - 0.05 * bump(uu, 1.0, 0.08))
            return Vector((x0 - 0.029 + 0.058 * uu, y, z)), col
        grid(a, 'cloth', 4, 14, fn, wrap=False)
        grid(a, 'cloth', 4, 14, lambda uu, vv, f=fn: (f(uu, vv)[0] - Vector((0, 0, 0.003)), tint(f(uu, vv)[1], -0.12)), wrap=False, flip=True)
        for sg in (-1, 1):          # 绕过横档的那一截
            a.lathe([(0.0148, -0.029, c), (0.0148, 0.029)], (x0, sg * Dy, Ht), segs=12, color=c, rot=(0, math.pi / 2, 0), mat='cloth', outward=True)
    return craft.finish(a, (30, 26, 1.0), ao=True, dist=0.25)


ASSETS = {
    'fishing_rod': fishing_rod, 'fishing_bobber': fishing_bobber, 'fish_basket': fish_basket, 'fishing_stool': fishing_stool,
    'fish_crucian': crucian, 'fish_loach': loach, 'fish_goldfish': goldfish, 'fish_shrimp': shrimp, 'fish_whitebait': whitebait,
    'fish_silver': silverfish, 'fish_bass': bass, 'fish_mandarin': mandarin, 'fish_crab': crab, 'fish_carp_gold': carp_gold,
    'fish_moon': moonfish, 'fish_weed': weed,
}
