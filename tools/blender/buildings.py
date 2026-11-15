"""建筑：大殿、牌坊、钟亭、码头、小船。每个模型的原点在它自己的地面中心，-y 是正面（朝南，朝着镜头）。"""
import math

from kit import Asset
from palette import C, tint, mix, vary


def _lattice(a, cx, y, z0, w, h, nx=3, nz=5, depth=0.05):
    """一扇格子窗：后面一块会亮的窗纸，前面是木格"""
    a.box((w, 0.03, h), (cx, y + 0.02, z0), color=C('paper'), bevel=0, mat='glow', glow=1.0)
    bar = C('lattice')
    for i in range(nx + 1):
        x = cx - w / 2 + w * i / nx
        a.box((0.035, depth, h), (x, y, z0), color=bar, bevel=0)
    for j in range(nz + 1):
        z = z0 + h * j / nz
        a.box((w, depth, 0.035), (cx, y, z - 0.017), color=bar, bevel=0)


def _hang_lantern(a, x, y, z, s=1.0):
    """挂着的红灯笼，z 是挂点"""
    a.cyl(0.012 * s, 0.22 * s, (x, y, z - 0.22 * s), C('rope_dark'), segs=5)
    r = C('cloth_red')
    a.lathe([(0.07, 0.0, C('gold_dark')), (0.1, 0.03, r), (0.2, 0.14, r), (0.23, 0.26, tint(r, 0.06)), (0.2, 0.38, r), (0.1, 0.49, C('gold_dark')), (0.07, 0.52)],
            (x, y, z - 0.74 * s), segs=12, scale=s, mat='glow', glow=1.0, color=r)
    a.cyl(0.02 * s, 0.2 * s, (x, y, z - 0.94 * s), C('gold'), r2=0.035 * s, segs=6)


def _rail(a, p0, p1, z, post_every=1.5):
    """一段石栏杆：望柱、上下横杆、中间栏板"""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    n = max(1, int(round(L / post_every)))
    ang = math.atan2(dy, dx)
    st, sl = C('stone'), C('stone_lit')
    for i in range(n + 1):
        k = i / n
        x, y = p0[0] + dx * k, p0[1] + dy * k
        a.box((0.17, 0.17, 0.78), (x, y, z), color=st, bevel=0.025, top=sl)
        a.lathe([(0.06, 0), (0.1, 0.03), (0.105, 0.09), (0.05, 0.15), (0.0, 0.17)], (x, y, z + 0.78), segs=8, color=sl)
    cx, cy = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    a.box((L, 0.1, 0.09), (cx, cy, z + 0.56), rot=(0, 0, ang), color=sl, bevel=0.02)
    a.box((L, 0.06, 0.34), (cx, cy, z + 0.14), rot=(0, 0, ang), color=st, bevel=0.015)
    a.box((L, 0.12, 0.1), (cx, cy, z), rot=(0, 0, ang), color=C('stone_dark'), bevel=0.02)


def hall(name):
    a = Asset(name)
    st, sl, sd = C('stone'), C('stone_lit'), C('stone_dark')
    red, redd, redl = C('red'), C('red_dark'), C('red_lit')
    PW, PD, PH = 17.2, 9.8, 0.7
    # 台基：下面一圈略宽的须弥座，上面铺砖
    a.box((PW + 0.3, PD + 0.3, 0.16), color=sd, bevel=0.04, mat='stone')
    # 这一层的顶要比上面那层石板低：两个面叠在同一高度会抢着显示，一直闪
    a.box((PW, PD, PH - 0.16), (0, 0, 0.1), color=st, bevel=0.05, segs=2, grad=(tint(st, -0.06), st), mat='brick')
    a.box((PW + 0.16, PD + 0.16, 0.12), (0, 0, PH - 0.12), color=sl, bevel=0.035, segs=2, top=C('slab_c'), mat='stone')
    # 台面铺方砖（每块略有深浅）
    rng = a.rng
    nx_, ny_ = 14, 8
    slw, sld = (PW - 0.5) / nx_, (PD - 0.5) / ny_
    for i in range(nx_):
        for j in range(ny_):
            # 屋里看不见的那几块不做
            cx, cy = -PW / 2 + 0.25 + slw * (i + 0.5), -PD / 2 + 0.25 + sld * (j + 0.5)
            if abs(cx) < 6.2 and -1.2 < cy < 3.0:
                continue
            c = vary(rng.choice([C('slab'), C('slab_b'), C('slab_c')]), rng, 0.03, 0.02)
            a.prism([(-slw / 2 + 0.02, -sld / 2 + 0.02), (slw / 2 - 0.02, -sld / 2 + 0.02), (slw / 2 - 0.02, sld / 2 - 0.02), (-slw / 2 + 0.02, sld / 2 - 0.02)],
                    PH - 0.02, PH + 0.035 + rng.uniform(-0.004, 0.004), tint(c, -0.1), bevel=0.018, top=c, loc=(cx, cy, 0), mat='slab')
    # 台基侧面：砌石的缝（两层错缝）
    seam = tint(sd, -0.06)
    for (x0, y0, x1, y1) in ((-PW / 2, -PD / 2, PW / 2, -PD / 2), (-PW / 2, -PD / 2, -PW / 2, PD / 2), (PW / 2, -PD / 2, PW / 2, PD / 2)):
        L = math.hypot(x1 - x0, y1 - y0)
        ang = math.atan2(y1 - y0, x1 - x0)
        nx, ny = (0, -1) if abs(y1 - y0) < 1e-6 else ((-1, 0) if x0 < 0 else (1, 0))
        a.box((L, 0.016, 0.02), ((x0 + x1) / 2 + nx * 0.004, (y0 + y1) / 2 + ny * 0.004, 0.36), rot=(0, 0, ang), color=seam, bevel=0)
        n = int(L / 1.15)
        for row, (z0, zh) in enumerate(((0.17, 0.19), (0.38, 0.2))):
            for i in range(n):
                k = (i + (0.5 if row else 0.0)) / n
                if abs(y1 - y0) < 1e-6 and abs(x0 + (x1 - x0) * k) < 2.5:
                    continue
                a.box((0.02, 0.016, zh), (x0 + (x1 - x0) * k + nx * 0.004, y0 + (y1 - y0) * k + ny * 0.004, z0), rot=(0, 0, ang), color=seam, bevel=0)
    # 台阶
    for k in range(4):
        d = 0.36 * (4 - k)
        a.box((4.7, d, 0.175), (0, -PD / 2 - d / 2 + 0.02, k * 0.175), color=tint(st, 0.02 * k), bevel=0.025, top=sl, mat='stone')
    for sx in (-1, 1):
        a.box((0.36, 1.62, 0.2), (sx * 2.55, -PD / 2 - 0.7, 0.24), rot=(math.atan2(0.7, 1.44), 0, 0), color=sl, bevel=0.04, base=False)
        a.box((0.4, 0.4, 0.5), (sx * 2.55, -PD / 2 - 1.5, 0), color=st, bevel=0.05, top=sl)
    # 栏杆
    hx, hy = PW / 2 - 0.12, PD / 2 - 0.12
    _rail(a, (-hx, -hy), (-2.9, -hy), PH)
    _rail(a, (2.9, -hy), (hx, -hy), PH)
    _rail(a, (-hx, -hy), (-hx, hy), PH)
    _rail(a, (hx, -hy), (hx, hy), PH)
    _rail(a, (-hx, hy), (hx, hy), PH)

    xs = [-6.6, -3.96, -1.32, 1.32, 3.96, 6.6]
    FY, WY, BY = -3.3, -1.5, 3.3
    CH = 3.5
    top = PH + CH
    # 柱子：前廊一排，墙身四角和中间
    cols = [(x, FY) for x in xs] + [(x, WY) for x in xs] + [(x, BY) for x in xs] + [(-6.6, 0.9), (6.6, 0.9)]
    from props_hd import petal_ring
    for (x, y) in cols:
        # 柱础：方形石墩上一个覆盆（覆莲瓣），再一道圆台
        a.box((0.62, 0.62, 0.058), (x, y, PH + 0.002), color=sd, bevel=0.015, top=st, mat='stone')
        a.lathe([(0.3, PH + 0.06), (0.31, PH + 0.08), (0.28, PH + 0.13), (0.23, PH + 0.16)], (x, y, 0), segs=40, color=sl, mat='stone')
        t = new_petals = None
        sub = Asset(name + '_pb')
        petal_ring(sub, 16, 0.24, PH + 0.1, 0.065, 0.05, 0.02, 25, sl, 'stone', up=False, rng=rng)
        a.place(sub, (x, y, 0))
        # 柱身：微微收分（上细下粗），朱漆
        a.lathe([(0.205, PH + 0.155), (0.203, PH + 1.2), (0.198, PH + 2.4), (0.19, top - 0.01)], (x, y, 0), segs=36, color=red, mat='lacquer')
        # 下面一道、上面一道金箍；上面那道之上一圈缠枝花纹带（金线、花朵凸起）
        for zz in (PH + 0.34, top - 0.62):
            a.lathe([(0.2, 0), (0.212, 0.008, C('gold_dark')), (0.216, 0.016, C('gold')), (0.212, 0.026, C('gold_dark')), (0.2, 0.03),
                     (0.2, 0.05, C('gold_dark')), (0.212, 0.054, C('gold_dark')), (0.216, 0.062, C('gold')), (0.212, 0.072, C('gold_dark')), (0.2, 0.08)],
                    (x, y, zz), segs=36, color=C('gold'), mat='toon')
        zb = top - 0.5
        a.lathe([(0.193, 0), (0.197, 0.004), (0.197, 0.3), (0.193, 0.304)], (x, y, zb), segs=36, color=C('navy'), mat='toon')
        for k in range(14):
            ang = 2 * math.pi * k / 14
            cx, cy = x + 0.2 * math.cos(ang), y + 0.2 * math.sin(ang)
            a.blob(0.024, (cx, cy, zb + 0.15), (0.45, 1, 1), C('gold'), top=C('gold_lit') if 'gold_lit' in __import__('palette').P else C('gold'), subdiv=2, bump=0.1)
            for sg in (-1, 1):
                a2 = ang + sg * 0.11
                a.tube([(x + 0.199 * math.cos(ang), y + 0.199 * math.sin(ang), zb + 0.15 + sg * 0.02),
                        (x + 0.199 * math.cos(a2), y + 0.199 * math.sin(a2), zb + 0.15 + sg * 0.09),
                        (x + 0.199 * math.cos(a2 + sg * 0.12), y + 0.199 * math.sin(a2 + sg * 0.12), zb + 0.15 + sg * 0.06)], 0.005, C('gold'), segs=4)
    # 墙：两山和后墙是粉墙，下面一截石裙
    def wall(x0, y0, x1, y1):
        L = math.hypot(x1 - x0, y1 - y0)
        ang = math.atan2(y1 - y0, x1 - x0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        a.box((L, 0.26, 0.95), (cx, cy, PH), rot=(0, 0, ang), color=C('wall_dark'), bevel=0.02, top=sl, mat='brick')
        a.box((L, 0.2, CH - 0.95), (cx, cy, PH + 0.95), rot=(0, 0, ang), color=C('wall'), bevel=0.0, grad=(C('wall_dark'), C('wall')), mat='plaster')
    wall(-6.6, WY, -6.6, BY)
    wall(6.6, WY, 6.6, BY)
    wall(-6.6, BY, 6.6, BY)
    # 正面：中间三间是格扇门，两边两间是槛窗
    for i in range(5):
        x0, x1 = xs[i] + 0.22, xs[i + 1] - 0.22
        w = x1 - x0
        if 1 <= i <= 3:
            n = 4
            lw = w / n
            for k in range(n):
                cx = x0 + lw * (k + 0.5)
                a.box((lw - 0.03, 0.09, 3.0), (cx, WY, PH + 0.02), color=redd, bevel=0.012, mat='lacquer')
                a.box((lw - 0.14, 0.11, 0.78), (cx, WY - 0.01, PH + 0.14), color=red, bevel=0.015, mat='lacquer')
                a.box((lw - 0.26, 0.13, 0.5), (cx, WY - 0.02, PH + 0.28), color=redl, bevel=0.02, mat='lacquer')
                _lattice(a, cx, WY - 0.03, PH + 1.08, lw - 0.14, 1.8, 2, 5)
        else:
            a.box((w, 0.3, 1.0), ((x0 + x1) / 2, WY, PH), color=C('wall_dark'), bevel=0.02, top=sl, mat='brick')
            a.box((w, 0.12, 2.02), ((x0 + x1) / 2, WY, PH + 1.0), color=redd, bevel=0.012, mat='lacquer')
            _lattice(a, (x0 + x1) / 2, WY - 0.04, PH + 1.12, w - 0.2, 1.76, 5, 5)
        # 门窗上面的横披
        a.box((w, 0.14, 0.42), ((x0 + x1) / 2, WY, PH + 3.04), color=red, bevel=0.012)
        _lattice(a, (x0 + x1) / 2, WY - 0.05, PH + 3.1, w - 0.2, 0.3, 6, 1)
    # 额枋：前后左右一圈，蓝底金线
    def beam(x0, y0, x1, y1, z, h=0.36, t=0.24):
        L = math.hypot(x1 - x0, y1 - y0) + 0.5
        ang = math.atan2(y1 - y0, x1 - x0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        a.box((L, t, h), (cx, cy, z), rot=(0, 0, ang), color=C('navy'), bevel=0.02)
        a.box((L + 0.02, t + 0.03, 0.05), (cx, cy, z + 0.03), rot=(0, 0, ang), color=C('gold'), bevel=0.0)
        a.box((L + 0.02, t + 0.03, 0.05), (cx, cy, z + h - 0.08), rot=(0, 0, ang), color=C('gold'), bevel=0.0)
        n = int(L / 1.32)
        for i in range(n):
            k = (i + 0.5) / n - 0.5
            a.box((0.5, t + 0.04, 0.16), (cx + math.cos(ang) * L * k, cy + math.sin(ang) * L * k, z + 0.1), rot=(0, 0, ang),
                  color=C('tile_lit') if i % 2 == 0 else C('red_lit'), bevel=0.015)
    beam(-6.6, FY, 6.6, FY, top - 0.4)
    beam(-6.6, BY, 6.6, BY, top - 0.4)
    beam(-6.6, FY, -6.6, BY, top - 0.4)
    beam(6.6, FY, 6.6, BY, top - 0.4)
    # 斗拱：檐下一排小木块，两层往外挑
    def brackets(x0, y0, x1, y1, ox, oy):
        L = math.hypot(x1 - x0, y1 - y0)
        n = int(L / 0.66)
        ang = math.atan2(y1 - y0, x1 - x0)
        for i in range(n + 1):
            k = i / n
            x, y = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
            c = C('navy') if i % 2 == 0 else C('tile_lit')
            a.box((0.3, 0.3, 0.16), (x, y, top), rot=(0, 0, ang), color=c, bevel=0.02)
            a.box((0.22, 0.5, 0.14), (x + ox * 0.14, y + oy * 0.14, top + 0.16), rot=(0, 0, ang), color=C('gold_dark'), bevel=0.02)
            a.box((0.34, 0.26, 0.14), (x + ox * 0.34, y + oy * 0.34, top + 0.3), rot=(0, 0, ang), color=c, bevel=0.02)
    brackets(-6.6, FY, 6.6, FY, 0, -1)
    brackets(-6.6, BY, 6.6, BY, 0, 1)
    brackets(-6.6, FY, -6.6, BY, -1, 0)
    brackets(6.6, FY, 6.6, BY, 1, 0)
    a.box((13.6, 7.0, 0.14), (0, 0, top + 0.42), color=redd, bevel=0.0)
    # 下层檐
    ez = top + 0.52
    a.roof(8.5, 5.25, 3.5, z=ez, lift=0.7, inner=2.3, rows=6, ridge_r=0.12, caps=C('gold'))
    # 上层：一圈矮墙，开小窗
    uz0, uz1 = ez + 0.75, ez + 2.05
    a.box((12.3, 5.9, uz1 - uz0 - 0.06), (0, 0, uz0), color=red, bevel=0.03, grad=(redd, red), mat='lacquer')
    for i in range(5):
        cx = (xs[i] + xs[i + 1]) / 2 * 0.9
        _lattice(a, cx, -2.98, uz0 + 0.5, 1.5, 0.55, 5, 2)
    a.box((12.5, 6.1, 0.2), (0, 0, uz1 - 0.2), color=C('navy'), bevel=0.02)
    a.box((12.54, 6.14, 0.05), (0, 0, uz1 - 0.12), color=C('gold'), bevel=0)
    brackets(-6.1, -2.95, 6.1, -2.95, 0, -1)
    # 上层檐
    for (x0, y0, x1, y1, ox, oy) in ((-6.1, -2.95, 6.1, -2.95, 0, -1),):
        pass
    a.roof(7.7, 4.45, 2.75, z=uz1 + 0.16, lift=0.8, rows=8, ridge_r=0.15, tip=0.6, caps=C('gold'), bells=True)
    rz = uz1 + 0.16 + 2.75
    a.lathe([(0.0, 0), (0.2, 0.03), (0.24, 0.16), (0.12, 0.26), (0.2, 0.44), (0.15, 0.6), (0.05, 0.72), (0.0, 0.9)], (0, 0, rz + 0.12), segs=12, color=C('gold'))
    # 匾
    a.box((2.1, 0.12, 0.82), (0, -3.12, uz0 + 0.3), rot=(math.radians(-12), 0, 0), color=C('gold'), bevel=0.03)
    a.box((1.86, 0.14, 0.6), (0, -3.15, uz0 + 0.41), rot=(math.radians(-12), 0, 0), color=C('navy'), bevel=0.015)
    for i in range(3):
        a.box((0.3, 0.16, 0.3), (-0.5 + i * 0.5, -3.19, uz0 + 0.56), rot=(math.radians(-12), 0, 0), color=C('gold'), bevel=0.03)
    # 檐下的红灯笼
    for x in (-5.28, -2.64, 2.64, 5.28):
        _hang_lantern(a, x, FY - 0.85, top + 0.3, 1.25)
    return a.finish(view=(18, 40, 0.92), dist=1.4)


def gate(name):
    """牌坊：两根红柱、两道横枋、一个小瓦顶"""
    a = Asset(name)
    st, sl = C('stone'), C('stone_lit')
    for sx in (-1, 1):
        x = sx * 2.15
        a.box((0.72, 0.9, 0.3), (x, 0, 0), color=st, bevel=0.05, segs=2, top=sl)
        for sy in (-1, 1):
            a.cyl(0.3, 0.2, (x, sy * 0.52, 0.56), sl, segs=16, rot=(0, math.pi / 2, 0), bevel=0.03)
        a.box((0.5, 0.56, 0.32), (x, 0, 0.3), color=sl, bevel=0.05)
        a.cyl(0.21, 3.75, (x, 0, 0.6), C('red'), segs=12, grad=(C('red_dark'), C('red_lit')))
    a.box((5.3, 0.3, 0.36), (0, 0, 3.0), color=C('red'), bevel=0.03)
    a.box((5.34, 0.34, 0.06), (0, 0, 3.05), color=C('gold'), bevel=0)
    a.box((5.9, 0.34, 0.4), (0, 0, 4.0), color=C('navy'), bevel=0.03)
    a.box((5.94, 0.38, 0.06), (0, 0, 4.06), color=C('gold'), bevel=0)
    a.box((5.94, 0.38, 0.06), (0, 0, 4.28), color=C('gold'), bevel=0)
    # 匾
    a.box((2.3, 0.14, 0.66), (0, 0, 3.35), color=C('gold'), bevel=0.03)
    a.box((2.06, 0.18, 0.46), (0, 0, 3.45), color=C('navy'), bevel=0.015)
    for sy in (-1, 1):
        for i in range(3):
            a.box((0.26, 0.04, 0.26), (-0.55 + i * 0.55, sy * 0.1, 3.55), color=C('gold'), bevel=0.02)
    for sx in (-1, 1):
        a.box((0.5, 0.2, 0.5), (sx * 1.55, 0, 3.4), color=C('red_dark'), bevel=0.02)
    # 小斗拱和瓦顶
    for i in range(9):
        x = -2.6 + i * 0.65
        a.box((0.26, 0.5, 0.14), (x, 0, 4.4), color=C('navy') if i % 2 == 0 else C('tile_lit'), bevel=0.02)
        a.box((0.2, 0.8, 0.12), (x, 0, 4.54), color=C('gold_dark'), bevel=0.02)
    a.roof(3.6, 0.85, 0.7, z=4.68, lift=0.34, rows=4, ridge_r=0.09, tip=0.3, thick=0.09, course=0.3, caps=C('gold'))
    for sx in (-1, 1):
        _hang_lantern(a, sx * 1.2, 0, 3.0, 1.0)
    return a.finish(view=(20, 30, 1.0))


def pavilion(name):
    """钟亭：四柱、攒尖顶、里面挂一口铜钟"""
    a = Asset(name)
    a.box((3.9, 3.9, 0.12), color=C('stone_dark'), bevel=0.03)
    a.box((3.6, 3.6, 0.3), color=C('stone'), top=C('slab'), bevel=0.05, segs=2)
    a.box((1.3, 0.5, 0.15), (0, -1.98, 0), color=C('stone'), top=C('slab'), bevel=0.03)
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * 1.35, sy * 1.35
            a.lathe([(0.24, 0), (0.25, 0.05), (0.2, 0.12), (0.17, 0.14)], (x, y, 0.3), segs=10, color=C('stone_lit'))
            a.cyl(0.14, 2.3, (x, y, 0.42), C('red'), segs=12, grad=(C('red_dark'), C('red_lit')))
    for i in range(4):
        ang = i * math.pi / 2
        px, py = 1.35 * math.sin(ang), -1.35 * math.cos(ang)
        a.box((2.95, 0.16, 0.24), (px, py, 2.44), rot=(0, 0, ang), color=C('navy'), bevel=0.02)
        a.box((2.97, 0.19, 0.05), (px, py, 2.5), rot=(0, 0, ang), color=C('gold'), bevel=0)
        # 坐凳栏杆（正面留空）
        if i != 0:
            a.box((2.5, 0.3, 0.08), (px, py, 0.72), rot=(0, 0, ang), color=C('wood'), bevel=0.02)
            for k in range(5):
                q = -1.0 + k * 0.5
                a.box((0.07, 0.07, 0.42), (px + math.cos(ang) * q, py + math.sin(ang) * q, 0.3), color=C('red_dark'), bevel=0.01)
        for k in range(5):
            q = -1.3 + k * 0.65
            a.box((0.22, 0.34, 0.12), (px + math.cos(ang) * q, py + math.sin(ang) * q, 2.68), rot=(0, 0, ang),
                  color=C('navy') if k % 2 == 0 else C('tile_lit'), bevel=0.02)
    a.box((3.0, 3.0, 0.1), (0, 0, 2.78), color=C('red_dark'), bevel=0.02)
    a.roof(2.4, 2.4, 1.5, z=2.86, lift=0.5, ridge_r=0.09, tip=0.45, rows=6, caps=C('gold'), bells=True)
    # 钟
    a.box((0.14, 2.8, 0.14), (0, 0, 2.5), color=C('wood_dark'), bevel=0.02)
    a.cyl(0.025, 0.32, (0, 0, 2.2), C('rope_dark'), segs=6)
    bz = C('bronze')
    a.lathe([(0.0, 0.0), (0.34, 0.0, C('bronze_dark')), (0.37, 0.04, bz), (0.335, 0.16, bz), (0.315, 0.4, C('bronze_lit')), (0.3, 0.58, bz),
             (0.27, 0.74, bz), (0.19, 0.85, C('bronze_lit')), (0.08, 0.9, bz), (0.05, 0.96), (0.0, 0.98)], (0, 0, 1.24), segs=16, color=bz)
    a.lathe([(0.325, 0.0), (0.335, 0.03), (0.325, 0.06)], (0, 0, 1.56), segs=16, color=C('gold_dark'))
    # 撞钟的木槌
    a.cyl(0.07, 1.1, (0.95, 0, 1.62), C('wood'), segs=10, rot=(0, math.pi / 2, 0))
    for sy in (-1, 1):
        a.cyl(0.012, 0.86, (0.6, sy * 0.3, 1.66), C('rope'), segs=5)
    return a.finish(view=(25, 38, 1.0))


def dock(name):
    """栈桥：从岸边伸到水里，尽头一个小平台。原点在岸边这头的中点，往 -y 伸出去"""
    a = Asset(name)
    rng = a.rng
    Lm, Lp = 6.2, 3.0          # 桥身长、平台长
    top = 0.06
    y = 0.0
    while y > -Lm:
        d = rng.uniform(0.25, 0.32)
        w = 2.4 + rng.uniform(-0.06, 0.1)
        c = vary(rng.choice([C('plank'), C('plank_b'), C('plank_c')]), rng, 0.04, 0.03)
        a.box((w, d - 0.025, 0.07), (rng.uniform(-0.04, 0.04), y - d / 2, top - 0.07 + rng.uniform(-0.006, 0.006)), rot=(0, 0, rng.uniform(-0.012, 0.012)),
              color=tint(c, -0.1), bevel=0.012, top=c)
        for sx in (-0.85, 0.85):
            a.cyl(0.016, 0.012, (sx + rng.uniform(-0.02, 0.02), y - d / 2, top + 0.002), C('bronze_dark'), segs=6, top=C('bronze'))
        y -= d
    while y > -(Lm + Lp):
        d = rng.uniform(0.25, 0.32)
        w = 5.0 + rng.uniform(-0.06, 0.1)
        c = vary(rng.choice([C('plank'), C('plank_b'), C('plank_c')]), rng, 0.04, 0.03)
        a.box((w, d - 0.025, 0.07), (rng.uniform(-0.04, 0.04), y - d / 2, top - 0.07 + rng.uniform(-0.006, 0.006)), rot=(0, 0, rng.uniform(-0.012, 0.012)),
              color=tint(c, -0.1), bevel=0.012, top=c)
        for sx in (-2.2, -0.85, 0.85, 2.2):
            a.cyl(0.016, 0.012, (sx + rng.uniform(-0.02, 0.02), y - d / 2, top + 0.002), C('bronze_dark'), segs=6, top=C('bronze'))
        y -= d
    # 底下的纵梁
    for x in (-0.85, 0.85):
        a.box((0.16, Lm + Lp, 0.18), (x, -(Lm + Lp) / 2, top - 0.25), color=C('wood_dark'), bevel=0.02)
    for x in (-2.2, 2.2):
        a.box((0.16, Lp, 0.18), (x, -Lm - Lp / 2, top - 0.25), color=C('wood_dark'), bevel=0.02)
    # 木桩
    posts = [(sx * 1.28, -yy, 0.5 if i % 2 == 0 else 0.16) for i, yy in enumerate((0.4, 2.3, 4.2)) for sx in (-1, 1)]
    posts += [(sx * 2.58, -Lm - 0.1, 0.55) for sx in (-1, 1)] + [(sx * 2.58, -Lm - Lp + 0.1, 0.55) for sx in (-1, 1)] + [(0.0, -Lm - Lp + 0.02, 0.16)]
    for (x, yy, h) in posts:
        a.cyl(0.115, 2.9 + h, (x, yy, -2.9), C('wood_dark'), r2=0.1, segs=10, grad=(C('wood_deep'), C('wood')))
        a.cyl(0.125, 0.05, (x, yy, h - 0.03), C('wood_lit'), segs=10, bevel=0.015)
        if h > 0.3:
            a.lathe([(0.118, 0), (0.135, 0.02), (0.135, 0.07), (0.118, 0.09)], (x, yy, h - 0.2), segs=10, color=C('rope'))
    # 平台两侧的绳栏
    def rope(p0, p1, sag=0.16):
        pts = []
        for i in range(9):
            k = i / 8
            pts.append((p0[0] + (p1[0] - p0[0]) * k, p0[1] + (p1[1] - p0[1]) * k, p0[2] + (p1[2] - p0[2]) * k - sag * 4 * k * (1 - k)))
        a.tube(pts, 0.022, C('rope'), segs=5)
    for sx in (-1, 1):
        rope((sx * 2.58, -Lm - 0.1, 0.4), (sx * 2.58, -Lm - Lp + 0.1, 0.4))
    rope((-1.28, -0.4, 0.36), (-1.28, -4.2, 0.36), 0.3)
    # 平台角上的灯杆
    px, py = -2.58, -Lm - Lp + 0.1
    a.cyl(0.05, 2.3, (px, py, 0.5), C('wood_dark'), segs=8)
    a.box((0.9, 0.06, 0.06), (px + 0.35, py, 2.7), color=C('wood_dark'), bevel=0.01)
    a.cyl(0.01, 0.2, (px + 0.72, py, 2.5), C('rope_dark'), segs=5)
    a.box((0.26, 0.26, 0.34), (px + 0.72, py, 2.16), color=C('paper'), bevel=0.02, mat='glow', glow=1.0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            a.box((0.035, 0.035, 0.38), (px + 0.72 + sx * 0.13, py + sy * 0.13, 2.14), color=C('wood_dark'), bevel=0)
    a.roof(0.24, 0.24, 0.14, z=2.5, loc=(px + 0.72, py), lift=0.04, pitch=0.3, amp=0, rows=2, thick=0.03, ca=C('wood_dark'), cb=C('wood_dark'),
           eave=C('wood_dark'), under=C('wood_deep'), ridge=C('wood_dark'), ridge_r=0.015, tip=0.0, hips=False)
    # 一只木桶、一盘绳
    bx, by = 1.9, -Lm - 0.7
    a.lathe([(0.0, 0.0), (0.17, 0.0, C('wood')), (0.2, 0.3, C('wood_lit')), (0.2, 0.32, C('wood_dark')), (0.17, 0.32), (0.16, 0.06), (0.0, 0.06)], (bx, by, top), segs=12, color=C('wood'))
    a.lathe([(0.195, 0), (0.21, 0.01), (0.21, 0.04), (0.195, 0.05)], (bx, by, top + 0.08), segs=12, color=C('bronze_dark'))
    a.lathe([(0.2, 0), (0.215, 0.01), (0.215, 0.04), (0.2, 0.05)], (bx, by, top + 0.22), segs=12, color=C('bronze_dark'))
    for k in range(3):
        r = 0.26 - k * 0.06
        pts = [(1.2 + r * math.cos(t * 0.7), -Lm - Lp + 0.75 + r * math.sin(t * 0.7), top + 0.03 + k * 0.04) for t in range(10)]
        a.tube(pts, 0.03, C('rope') if k % 2 == 0 else C('rope_dark'), segs=5)
    return a.finish(view=(30, 40, 0.9), ground_z=-3.0)


def boat(name):
    """小木船（带篷）。原点在水线、船中间，船头朝 +y"""
    a = Asset(name)
    import bmesh
    from kit import new_bm, paint
    Lb, B = 4.0, 0.62
    n = 14
    prof = [(1.0, 1.0), (0.93, 0.45), (0.72, 0.08), (0.36, 0.0), (0.0, -0.02)]   # (宽的比例, 高的比例)，从船舷到船底

    def station(s, inset=0.0, lift=0.0):
        w = B * (max(0.0, math.sin(math.pi * (0.06 + 0.88 * s))) ** 0.6) - inset
        w = max(0.03, w)
        sheer = 0.34 + 0.34 * (2 * s - 1) ** 2 + (0.1 if s > 0.5 else 0.0) * (2 * s - 1) ** 2
        keel = -0.2 + 0.22 * (2 * s - 1) ** 4 + lift
        pts = []
        for (kw, kh) in prof:
            pts.append((-w * kw, keel + (sheer - keel) * kh))
        for (kw, kh) in reversed(prof[:-1]):
            pts.append((w * kw, keel + (sheer - keel) * kh))
        return pts

    def loft(inset, lift, flip, c0, c1):
        t = new_bm()
        rows = []
        for i in range(n + 1):
            s = i / n
            y = -Lb / 2 + Lb * s
            rows.append([t.verts.new((x, y, z)) for (x, z) in station(s, inset, lift)])
        m = len(rows[0])
        for i in range(n):
            for k in range(m - 1):
                vs = (rows[i][k], rows[i + 1][k], rows[i + 1][k + 1], rows[i][k + 1])
                t.faces.new(tuple(reversed(vs)) if flip else vs)
        for r_, rev in ((rows[0], False), (rows[-1], True)):
            vs = list(reversed(r_)) if rev else r_
            t.faces.new(tuple(reversed(vs)) if flip else vs)
        paint(t, None, c0)
        from kit import paint_grad
        paint_grad(t, c0, c1, -0.2, 0.5)
        out = [[v.co.copy() for v in r_] for r_ in rows]
        a.merge(t)
        return out
    outer = loft(0.0, 0.0, False, C('boat_dark'), C('boat'))
    inner = loft(0.05, 0.045, True, C('boat'), C('boat_lit'))
    # 船舷的压条
    for side in (0, -1):
        a.tube([tuple(outer[i][side] + (inner[i][side] - outer[i][side]) * 0.5) for i in range(n + 1)], 0.04, C('boat_lit'), segs=6)
    # 舱板和横档
    for i in range(3, 12):
        s = i / n
        y = -Lb / 2 + Lb * s
        w = B * (math.sin(math.pi * (0.06 + 0.88 * s)) ** 0.6) * 0.72
        a.box((2 * w, Lb / n - 0.02, 0.03), (0, y, -0.08 + 0.22 * (2 * s - 1) ** 4), color=vary(C('plank'), a.rng, 0.04), bevel=0.008)
    for s in (0.2, 0.8):
        y = -Lb / 2 + Lb * s
        w = B * (math.sin(math.pi * (0.06 + 0.88 * s)) ** 0.6) * 0.95
        a.box((2 * w, 0.2, 0.045), (0, y, 0.3), color=C('wood_lit'), bevel=0.012)
    # 竹篾船篷：半圆的拱
    arc = []
    for k in range(9):
        ang = math.pi * k / 8
        arc.append((0.56 * math.cos(ang), 0.24 + 0.52 * math.sin(ang)))
    t = new_bm()
    ys = [-0.75 + 1.5 * i / 6 for i in range(7)]
    grid = [[t.verts.new((x, y, z)) for (x, z) in arc] for y in ys]
    for i in range(6):
        for k in range(8):
            f = t.faces.new((grid[i][k], grid[i][k + 1], grid[i + 1][k + 1], grid[i + 1][k]))
            c = C('straw') if (i + k) % 2 == 0 else C('straw_dark')
            paint(t, [f], c)
    a.merge(t, 'leaf')
    for y in (-0.75, 0.0, 0.75):
        a.tube([(x, y, z) for (x, z) in arc], 0.028, C('wood_dark'), segs=5)
    for k in (2, 6):
        a.tube([(arc[k][0], -0.78, arc[k][1] + 0.02), (arc[k][0], 0.78, arc[k][1] + 0.02)], 0.022, C('wood_dark'), segs=5)
    # 一支橹，斜搭在船尾
    a.tube([(0.25, -2.4, 0.1), (0.3, -1.4, 0.62), (0.34, -0.9, 0.86)], 0.03, C('wood_lit'), segs=6)
    a.box((0.16, 0.62, 0.03), (0.235, -2.62, -0.02), rot=(math.radians(27), 0, 0.04), color=C('wood'), bevel=0.01, base=False)
    a.opts['leaf'] = {'normal_up': 0.3}
    return a.finish(view=(35, 35, 1.0), ground=False)


ASSETS = {'hall': hall, 'gate': gate, 'pavilion': pavilion, 'dock': dock, 'boat': boat}
