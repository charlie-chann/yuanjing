"""树木花草。原点都在根部的地面上。树冠、叶片会随风摆动（顶点色第四个数）。"""
import math

from mathutils import Vector

import layout as L
from kit import Asset
from palette import C, tint, mix, vary


def _leaves(a, c, r, n, colors, size=0.34, sway=1.0, squash=1.0):
    """在一团树冠表面插上一片片小叶子，轮廓才不是光溜溜的球"""
    rng = a.rng
    for _ in range(n):
        d = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1) * 0.9 + 0.25)).normalized()
        p = Vector(c) + Vector((d.x * r, d.y * r, d.z * r * squash)) * rng.uniform(0.9, 1.04)
        # 叶片：一个菱形，沿着球面朝外斜着长
        side = d.cross(Vector((0, 0, 1)))
        side = side.normalized() if side.length > 1e-3 else Vector((1, 0, 0))
        tang = side.cross(d).normalized()          # 沿球面往下的方向
        upv = (d * 0.45 + tang * 0.75 + side * rng.uniform(-0.45, 0.45)).normalized()
        s = size * rng.uniform(0.75, 1.25)
        w = side * s * 0.36
        col = rng.choice(colors)
        tip = tint(col, 0.05)
        hi = 0.5 + 0.5 * d.z
        col = mix(tint(col, -0.07), col, hi)
        a.quad([p - upv * s * 0.25, p + w + upv * s * 0.3, p + upv * s, p - w + upv * s * 0.3], mat='leaf',
               colors=[tint(col, -0.06), col, tint(col, 0.06), col], sway=(sway * 0.7, sway, sway * 1.2, sway))


def _canopy(a, c, r, base, top, leaf_colors, leaves=36, sway=0.8, squash=1.0, bump=0.12, subdiv=3, leaf_size=0.4):
    a.blob(r, c, (1, 1, squash), base, top=top, subdiv=subdiv, bump=bump, freq=1.0, sway=sway * 0.45)
    if leaves:
        _leaves(a, c, r, int(leaves * 3.4 * max(0.6, r / 1.4)), leaf_colors, leaf_size * 0.85, sway, squash)


def _trunk(a, pts, radii, segs=10, c0=None, c1=None):
    a.tube(pts, radii, c0 or C('trunk_dark'), segs=segs, color2=c1 or C('trunk_lit'))


def tree_wish(name):
    """许愿树：老树，粗干、盘根，一大蓬树冠；四周一圈木桩拉着绳子，布条和木牌就挂在绳上。
    绳圈的尺寸 Unity 那边要用（BuildIslet.cs 的 RopeRing）"""
    a = Asset(name)
    rng = a.rng
    _trunk(a, [(0, 0, -0.1), (0.05, 0, 1.0), (-0.12, 0.08, 2.2), (0.05, 0.0, 3.4), (0.0, 0.0, 4.4)], [0.78, 0.6, 0.5, 0.44, 0.36], segs=12)
    for i in range(7):
        ang = 2 * math.pi * i / 7 + rng.uniform(-0.2, 0.2)
        c, s = math.cos(ang), math.sin(ang)
        k = rng.uniform(1.25, 1.75)
        _trunk(a, [(0.25 * c, 0.25 * s, 0.75), (0.75 * c, 0.75 * s, 0.22), (k * c, k * s, 0.02), ((k + 0.35) * c, (k + 0.35) * s, -0.12)],
               [0.24, 0.17, 0.1, 0.05], segs=7, c0=C('trunk_dark'), c1=C('trunk'))
    # 大枝
    ends = []
    for i in range(7):
        ang = 2 * math.pi * i / 7 + 0.3 + rng.uniform(-0.15, 0.15)
        c, s = math.cos(ang), math.sin(ang)
        rr, zz = rng.uniform(2.0, 2.7), rng.uniform(5.6, 6.5)
        _trunk(a, [(0.1 * c, 0.1 * s, 3.4 + 0.1 * i), (0.9 * c, 0.9 * s, 4.3 + 0.1 * i), (rr * 0.75 * c, rr * 0.75 * s, zz - 0.5), (rr * c, rr * s, zz)],
               [0.3, 0.22, 0.14, 0.07], segs=7)
        ends.append((rr * c, rr * s, zz))
    g, gl, gd = C('leaf'), C('leaf_lit'), C('leaf_dark')
    lc = [g, gl, gl, tint(gl, 0.04, 0.0, -0.02)]
    _canopy(a, (0, 0, 7.5), 2.6, gd, gl, lc, leaves=70, squash=0.8)
    for (x, y, z) in ends:
        _canopy(a, (x * 1.05, y * 1.05, z + 0.5), rng.uniform(1.5, 1.9), gd, g if rng.random() < 0.5 else gl, lc, leaves=40, squash=0.78)
    for i in range(4):
        ang = 2 * math.pi * i / 4 + 0.8
        _canopy(a, (1.4 * math.cos(ang), 1.4 * math.sin(ang), 8.6), 1.45, g, tint(gl, 0.05), lc, leaves=30, squash=0.75)
    # 树上原本就系着的一些红布条
    red = C('cloth_red')
    for i in range(16):
        ang = rng.uniform(0, 6.28)
        rr = rng.uniform(1.6, 3.4)
        x, y, z = rr * math.cos(ang), rr * math.sin(ang), rng.uniform(4.9, 5.5)
        ln = rng.uniform(0.7, 1.2)
        w = 0.07
        d = Vector((math.cos(ang + 1.3), math.sin(ang + 1.3), 0)) * w
        p = Vector((x, y, z))
        col = vary(red, rng, 0.05, 0.03)
        a.quad([p - d, p + d, p + d + Vector((0, 0, -ln)), p - d + Vector((0, 0, -ln))], mat='leaf', colors=[col, col, tint(col, -0.06), tint(col, -0.06)],
               sway=(0.2, 0.2, 2.0, 2.0))
    # 绳圈：八根木桩，绳子略微下垂
    N, R, H = 8, 2.95, 1.55
    for i in range(N):
        ang = 2 * math.pi * (i + 0.5) / N
        x, y = R * math.cos(ang), R * math.sin(ang)
        a.cyl(0.075, H + 0.12, (x, y, 0), C('wood'), r2=0.065, segs=8, grad=(C('wood_dark'), C('wood_lit')))
        a.lathe([(0.0, 0), (0.09, 0.01), (0.1, 0.06), (0.06, 0.1), (0.0, 0.12)], (x, y, H + 0.1), segs=8, color=C('red'))
        ang2 = 2 * math.pi * (i + 1.5) / N
        x2, y2 = R * math.cos(ang2), R * math.sin(ang2)
        pts = []
        for k in range(9):
            t = k / 8
            pts.append((x + (x2 - x) * t, y + (y2 - y) * t, H - 0.2 * 4 * t * (1 - t)))
        a.tube(pts, 0.022, C('rope'), segs=5)
    a.opts['leaf'] = {'normal_up': 0.55}
    return a.finish(view=(15, 42, 0.9), dist=1.8)


def _pine(name, seed_h=5.6, lean=0.5):
    """松：斜斜的红褐色树干，枝头托着一片片扁平的「云片」"""
    a = Asset(name)
    rng = a.rng
    h = seed_h
    pts = [(0, 0, -0.1), (lean * 0.2, 0, h * 0.3), (lean * 0.6, 0.1, h * 0.6), (lean * 0.8, 0.0, h * 0.84), (lean * 0.9, 0, h)]
    _trunk(a, pts, [0.3, 0.24, 0.18, 0.12, 0.07], segs=9, c0=C('trunk_dark'), c1=mix(C('trunk'), C('red_dark'), 0.3))
    pd, p, pl = C('pine_dark'), C('pine'), C('pine_lit')

    def pad(x, y, z, r):
        a.blob(r, (x, y, z), (1.0, 1.0, 0.3), pd, top=pl if rng.random() < 0.65 else p, subdiv=3, bump=0.16, freq=1.5, sway=0.3, flat=-0.3)
        a.blob(r * 0.55, (x + rng.uniform(-0.2, 0.2) * r, y + rng.uniform(-0.2, 0.2) * r, z + r * 0.2), (1.0, 1.0, 0.34), p, top=tint(pl, 0.04), subdiv=2, bump=0.14, sway=0.3)
        for q in range(int(16 * r)):
            a2 = rng.uniform(0, 6.28)
            rr = r * rng.uniform(0.8, 1.06)
            pp = Vector((x + rr * math.cos(a2), y + rr * math.sin(a2), z + 0.02))
            dz = Vector((math.cos(a2), math.sin(a2), 0.3)).normalized()
            sd = Vector((-math.sin(a2), math.cos(a2), 0)) * 0.12
            c = rng.choice([p, pl, pl])
            a.quad([pp - sd, pp + sd, pp + dz * 0.4], mat='leaf', colors=[tint(c, -0.05), tint(c, -0.05), tint(c, 0.06)], sway=(0.3, 0.3, 0.8))
    levels = 4
    for i in range(levels):
        k = i / (levels - 1)
        z = h * (0.5 + 0.42 * k)
        cx = lean * (0.45 + 0.4 * k)
        n = 2 if i < levels - 1 else 0
        for j in range(n):
            ang = math.pi * j + 1.3 * i + rng.uniform(-0.4, 0.4)
            reach = (1.0 - k * 0.45) * rng.uniform(1.5, 2.1)
            x, y = cx + reach * math.cos(ang), reach * math.sin(ang)
            _trunk(a, [(cx, 0, z - 0.35), ((cx + x) / 2, y / 2, z - 0.05), (x, y, z - 0.06)], [0.1, 0.07, 0.04], segs=6,
                   c0=C('trunk_dark'), c1=mix(C('trunk'), C('red_dark'), 0.3))
            pad(x, y, z, (1.15 - 0.4 * k) * rng.uniform(0.9, 1.1))
    pad(lean * 0.9, 0, h + 0.05, 1.1)
    a.opts['leaf'] = {'normal_up': 0.6}
    return a.finish(view=(20, 40, 0.95), dist=1.4)


def pines(name):
    return _pine('tree_pine_a', 5.8, 0.6) + _pine('tree_pine_b', 4.4, -0.9) + _pine('tree_pine_c', 7.0, 0.2)


def _broadleaf(name, h, r, base, top, lc, n_blobs=5, stems=1, leaves=34, trunk_r=0.2, leaf_size=0.3, spread=1.0):
    a = Asset(name)
    rng = a.rng
    tops = []
    for sidx in range(stems):
        ang = 2 * math.pi * sidx / max(1, stems) + rng.uniform(0, 1)
        ox, oy = (0.0, 0.0) if stems == 1 else (0.14 * math.cos(ang), 0.14 * math.sin(ang))
        ex, ey = (rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2)) if stems == 1 else (0.9 * spread * math.cos(ang), 0.9 * spread * math.sin(ang))
        hh = h * rng.uniform(0.62, 0.72)
        _trunk(a, [(ox, oy, -0.1), (ox + ex * 0.25, oy + ey * 0.25, hh * 0.45), (ox + ex * 0.7, oy + ey * 0.7, hh * 0.8), (ox + ex, oy + ey, hh)],
               [trunk_r, trunk_r * 0.8, trunk_r * 0.55, trunk_r * 0.35], segs=8)
        tops.append((ox + ex, oy + ey, hh))
    for (x, y, z) in tops:
        _canopy(a, (x, y, z + r * 0.45), r * (1.0 if stems == 1 else 0.72), base, top, lc, leaves=leaves, squash=0.82, leaf_size=leaf_size)
    for i in range(n_blobs):
        ang = 2 * math.pi * i / n_blobs + rng.uniform(-0.3, 0.3)
        rr = r * rng.uniform(0.55, 0.8) * spread
        x, y, z = rr * math.cos(ang), rr * math.sin(ang), h * rng.uniform(0.6, 0.82)
        _trunk(a, [(tops[i % len(tops)][0] * 0.5, tops[i % len(tops)][1] * 0.5, z - r * 0.5), (x * 0.8, y * 0.8, z - 0.1)], [trunk_r * 0.4, trunk_r * 0.2], segs=6)
        _canopy(a, (x, y, z), r * rng.uniform(0.5, 0.68), base, top if rng.random() < 0.6 else mix(base, top, 0.5), lc, leaves=int(leaves * 0.6), squash=0.8,
                leaf_size=leaf_size)
    a.opts['leaf'] = {'normal_up': 0.55}
    return a.finish(view=(20, 42, 0.95), dist=1.4)


def maples(name):
    m, ml, md = C('maple'), C('maple_lit'), C('maple_dark')
    lc = [m, ml, ml, tint(ml, 0.04)]
    t = _broadleaf('tree_maple_a', 4.6, 1.75, md, ml, lc, n_blobs=5, stems=3, trunk_r=0.13, leaf_size=0.3, spread=1.1)
    t += _broadleaf('tree_maple_b', 3.5, 1.35, md, m, lc, n_blobs=4, stems=2, trunk_r=0.1, leaf_size=0.28)
    # 银杏：金黄的
    gk, gkl = C('ginkgo'), C('ginkgo_lit')
    t += _broadleaf('tree_ginkgo', 5.6, 1.7, tint(gk, -0.12, 0.05), gkl, [gk, gkl, gkl], n_blobs=5, stems=1, trunk_r=0.2, leaf_size=0.3)
    return t


def rounds(name):
    g, gl, gd = C('leaf'), C('leaf_lit'), C('leaf_dark')
    lc = [g, gl, gl]
    t = _broadleaf('tree_round_a', 4.8, 1.9, gd, gl, lc, n_blobs=5, trunk_r=0.2)
    t += _broadleaf('tree_round_b', 3.6, 1.45, C('leaf_deep'), g, [g, gl, gd], n_blobs=4, trunk_r=0.15)
    b, bl, bd = C('blossom'), C('blossom_lit'), C('blossom_dark')
    t += _broadleaf('tree_blossom', 3.8, 1.5, bd, bl, [b, bl, bl, C('white')], n_blobs=5, stems=2, trunk_r=0.12, leaf_size=0.26, spread=1.1)
    return t


def bamboo(name):
    total = 0
    for v, (count, spread) in {'a': (9, 0.75), 'b': (5, 0.5)}.items():
        a = Asset(f'bamboo_{v}')
        rng = a.rng
        bm, bd, bl = C('bamboo'), C('bamboo_dark'), C('bamboo_leaf')
        for i in range(count):
            ang = rng.uniform(0, 6.28)
            rr = spread * math.sqrt(rng.random())
            x, y = rr * math.cos(ang), rr * math.sin(ang)
            h = rng.uniform(3.6, 5.8)
            lx, ly = rng.uniform(-0.5, 0.5) + x * 0.5, rng.uniform(-0.5, 0.5) + y * 0.5
            r = rng.uniform(0.045, 0.065)
            n = 9
            pts, rad, sw = [], [], []
            for k in range(n + 1):
                t = k / n
                pts.append((x + lx * t * t, y + ly * t * t, h * t))
                rad.append(r * (1 - 0.6 * t))
            a.tube(pts, rad, bd, segs=6, color2=bm, sway=(0.0, 1.3), mat='leaf')
            # 竹节
            for k in range(1, n):
                t = k / n
                px, py, pz = pts[k]
                a.cyl(rad[k] * 1.25, 0.03, (px, py, pz), tint(bd, -0.06), segs=6)
            # 竹叶：上半截一簇一簇
            for k in range(4, n + 1):
                t = k / n
                px, py, pz = pts[k]
                for q in range(5):
                    a2 = rng.uniform(0, 6.28)
                    ln = rng.uniform(0.45, 0.75)
                    dv = Vector((math.cos(a2), math.sin(a2), rng.uniform(-0.35, 0.15))).normalized()
                    sd = Vector((-math.sin(a2), math.cos(a2), 0)) * 0.06
                    p0 = Vector((px, py, pz)) + dv * 0.1
                    c = vary(rng.choice([bl, bl, C('leaf_lit'), bm]), rng, 0.04)
                    s0 = 0.5 + 1.2 * t
                    a.quad([p0, p0 + dv * ln * 0.45 + sd, p0 + dv * ln, p0 + dv * ln * 0.45 - sd], mat='leaf',
                           colors=[tint(c, -0.06), c, tint(c, 0.06), c], sway=(s0, s0 + 0.5, s0 + 1.0, s0 + 0.5))
        a.opts['leaf'] = {'normal_up': 0.6, 'plain_normals': True}
        total += a.finish(view=(20, 40, 0.95), ao=False)
    return total


def bushes(name):
    total = 0
    g, gl, gd = C('leaf'), C('leaf_lit'), C('leaf_dark')
    specs = {'a': (3, 0.55, None), 'b': (4, 0.7, None), 'c': (2, 0.42, None), 'flower_p': (3, 0.5, C('flower_p')), 'flower_w': (3, 0.5, C('flower_w'))}
    for v, (n, r, fl) in specs.items():
        a = Asset(f'bush_{v}')
        rng = a.rng
        for i in range(n):
            ang = 2 * math.pi * i / n + rng.uniform(-0.4, 0.4)
            d = r * (0.0 if i == 0 else rng.uniform(0.6, 0.9))
            x, y = d * math.cos(ang), d * math.sin(ang)
            rr = r * rng.uniform(0.75, 1.0)
            a.blob(rr, (x, y, rr * 0.55), (1.0, 1.0, 0.72), gd, top=gl if rng.random() < 0.6 else g, subdiv=2, bump=0.16, sway=0.3, flat=-0.5)
            _leaves(a, (x, y, rr * 0.55), rr, 16, [g, gl, gl], 0.2, 0.7, 0.72)
            if fl is not None:
                for q in range(10):
                    dv = Vector((rng.gauss(0, 1), rng.gauss(0, 1), abs(rng.gauss(0, 1)) + 0.3)).normalized()
                    p = Vector((x, y, rr * 0.55)) + Vector((dv.x * rr, dv.y * rr, dv.z * rr * 0.72)) * 1.02
                    a.blob(0.065, tuple(p), (1, 1, 0.7), fl, top=tint(fl, 0.06), subdiv=1, bump=0.0, sway=0.6)
        a.opts['leaf'] = {'normal_up': 0.6}
        total += a.finish(view=(20, 45, 1.0), dist=0.6)
    return total


def _blade(a, base, ang, h, w, lean, c0, c1, sway=1.0, segs=2):
    """一片草叶：从根到尖两三节，越往上越弯"""
    dx, dy = math.cos(ang), math.sin(ang)
    sx, sy = -dy * w / 2, dx * w / 2
    prev = None
    for k in range(segs + 1):
        t = k / segs
        cx = base[0] + dx * lean * t * t
        cy = base[1] + dy * lean * t * t
        cz = base[2] + h * t
        ww = (1 - t * 0.85)
        row = (Vector((cx - sx * ww, cy - sy * ww, cz)), Vector((cx + sx * ww, cy + sy * ww, cz)), mix(c0, c1, t), sway * t * t)
        if prev is not None:
            a.quad([prev[0], prev[1], row[1], row[0]], mat='leaf', colors=[prev[2], prev[2], row[2], row[2]], sway=(prev[3], prev[3], row[3], row[3]),
                   phase=a.rng.random())
        prev = row


def grass(name):
    total = 0
    gd, g, gl = C('grass_dark'), C('grass'), C('grass_lit')
    for v, (n, h, w) in {'a': (9, 0.34, 0.075), 'b': (7, 0.24, 0.07), 'c': (12, 0.46, 0.08)}.items():
        a = Asset(f'grass_{v}')
        rng = a.rng
        for i in range(n):
            ang = rng.uniform(0, 6.28)
            d = rng.uniform(0, 0.12)
            _blade(a, (d * math.cos(ang), d * math.sin(ang), -0.02), ang, h * rng.uniform(0.6, 1.1), w * rng.uniform(0.8, 1.2), rng.uniform(0.08, 0.22),
                   mix(gd, g, rng.random() * 0.5), mix(g, gl, 0.4 + rng.random() * 0.6), 1.2)
        a.opts['leaf'] = {'normal_up': 0.9, 'plain_normals': True}
        total += a.finish(view=(20, 40, 1.0), ao=False)
    # 花：几根茎顶着小花
    for v, col in {'w': C('flower_w'), 'y': C('flower_y'), 'p': C('flower_p'), 'v': C('flower_v')}.items():
        a = Asset(f'flower_{v}')
        rng = a.rng
        for i in range(5):
            ang = rng.uniform(0, 6.28)
            d = rng.uniform(0.02, 0.16)
            x, y = d * math.cos(ang), d * math.sin(ang)
            h = rng.uniform(0.2, 0.36)
            _blade(a, (x, y, -0.02), ang, h, 0.03, 0.05, gd, g, 1.0, 1)
            tx, ty = x + math.cos(ang) * 0.05, y + math.sin(ang) * 0.05
            a.disc(0.075 * rng.uniform(0.85, 1.2), (tx, ty, h), tint(col, -0.04), segs=6, mat='leaf', rim=tint(col, 0.05), cup=0.025, rot=rng.uniform(0, 3),
                   tilt=(rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3)), sway=1.0)
            a.blob(0.022, (tx, ty, h + 0.012), (1, 1, 0.6), C('flower_y') if v != 'y' else C('maple_lit'), subdiv=1, bump=0, sway=1.0, mat='leaf')
        for i in range(4):
            ang = rng.uniform(0, 6.28)
            _blade(a, (0, 0, -0.02), ang, rng.uniform(0.12, 0.2), 0.06, 0.1, gd, gl, 1.0)
        a.opts['leaf'] = {'normal_up': 0.9, 'plain_normals': True}
        total += a.finish(view=(20, 40, 1.0), ao=False)
    return total


def ground_cover(name):
    """贴地的细碎植物：三叶草、小雏菊、蕨、带穗的长草、路边的小草尖。数量很多，所以每个都很省"""
    total = 0
    gd, g, gl = C('grass_dark'), C('grass'), C('grass_lit')
    # 三叶草：一小片，每棵三片圆叶
    a = Asset('clover')
    rng = a.rng
    for i in range(11):
        ang = rng.uniform(0, 6.28)
        d = 0.3 * math.sqrt(rng.random())
        x, y = d * math.cos(ang), d * math.sin(ang)
        z = rng.uniform(0.03, 0.07)
        c = vary(rng.choice([C('leaf'), C('leaf_lit'), g]), rng, 0.04)
        r0 = rng.uniform(0, 2)
        for q in range(3):
            a2 = r0 + q * 2.094
            a.disc(0.028, (x + 0.026 * math.cos(a2), y + 0.026 * math.sin(a2), z), c, segs=6, mat='leaf', rim=tint(c, 0.07), sway=0.5)
    for i in range(2):
        ang = rng.uniform(0, 6.28)
        a.blob(0.022, (0.15 * math.cos(ang), 0.15 * math.sin(ang), 0.1), (1, 1, 0.9), C('white'), top=C('blossom_lit'), subdiv=1, bump=0.1, sway=0.8, mat='leaf')
    a.opts['leaf'] = {'normal_up': 0.95, 'plain_normals': True}
    total += a.finish(ao=False)
    # 小雏菊：一片细碎的小白花
    for v, col in {'w': C('flower_w'), 'y': C('flower_y'), 'b': C('flower_v')}.items():
        a = Asset(f'daisy_{v}')
        rng = a.rng
        for i in range(9):
            ang = rng.uniform(0, 6.28)
            d = 0.28 * math.sqrt(rng.random())
            x, y = d * math.cos(ang), d * math.sin(ang)
            h = rng.uniform(0.08, 0.17)
            _blade(a, (x, y, -0.01), ang, h, 0.014, 0.02, gd, g, 0.9, 1)
            a.disc(0.03, (x, y, h), col, segs=7, mat='leaf', rim=tint(col, 0.05), cup=0.008, rot=rng.uniform(0, 3), sway=0.9)
            a.disc(0.011, (x, y, h + 0.006), C('ginkgo') if v != 'y' else C('maple'), segs=5, mat='leaf', sway=0.9)
        for i in range(5):
            _blade(a, (rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2), -0.01), rng.uniform(0, 6.28), rng.uniform(0.06, 0.11), 0.03, 0.05, gd, gl, 0.9, 1)
        a.opts['leaf'] = {'normal_up': 0.95, 'plain_normals': True}
        total += a.finish(ao=False)
    # 蕨
    a = Asset('fern')
    rng = a.rng
    for i in range(7):
        ang = 2 * math.pi * i / 7 + rng.uniform(-0.2, 0.2)
        dx, dy = math.cos(ang), math.sin(ang)
        ln = rng.uniform(0.34, 0.5)
        c = vary(rng.choice([C('leaf'), C('leaf_dark'), C('pine_lit')]), rng, 0.04)
        n = 7
        for k in range(n):
            t0, t1 = k / n, (k + 1) / n
            w0, w1 = 0.09 * (1 - t0) + 0.01, 0.09 * (1 - t1) + 0.01
            z0, z1 = 0.02 + 0.26 * math.sin(t0 * 2.2), 0.02 + 0.26 * math.sin(t1 * 2.2)
            p0 = Vector((dx * ln * t0, dy * ln * t0, z0))
            p1 = Vector((dx * ln * t1, dy * ln * t1, z1))
            sd = Vector((-dy, dx, 0))
            # 羽状的小叶：一节一节，中间留缝
            a.quad([p0 - sd * w0, p0 + sd * w0, p1 * 0.97 + p0 * 0.03 + sd * w1 * 0.6, p1 * 0.97 + p0 * 0.03 - sd * w1 * 0.6], mat='leaf',
                   colors=[tint(c, -0.05), tint(c, -0.05), tint(c, 0.07), tint(c, 0.07)], sway=(t0, t0, t1, t1), phase=i * 0.13)
    a.opts['leaf'] = {'normal_up': 0.85, 'plain_normals': True}
    total += a.finish(ao=False)
    # 带穗的长草
    a = Asset('grass_seed')
    rng = a.rng
    for i in range(10):
        ang = rng.uniform(0, 6.28)
        d = rng.uniform(0, 0.1)
        h = rng.uniform(0.4, 0.7)
        lean = rng.uniform(0.1, 0.3)
        _blade(a, (d * math.cos(ang), d * math.sin(ang), -0.02), ang, h, 0.05, lean, mix(gd, g, 0.4), C('reed'), 1.3, 3)
        if i % 2 == 0:
            tx, ty = d * math.cos(ang) + math.cos(ang) * lean, d * math.sin(ang) + math.sin(ang) * lean
            a.blob(0.028, (tx, ty, h + 0.03), (0.7, 0.7, 2.2), C('straw'), top=C('straw_lit'), subdiv=1, bump=0.1, sway=1.3, mat='leaf')
    a.opts['leaf'] = {'normal_up': 0.9, 'plain_normals': True}
    total += a.finish(ao=False)
    # 很小的草尖：铺得满地都是，填在大草丛之间
    for v, n in {'a': 5, 'b': 7}.items():
        a = Asset(f'sprout_{v}')
        rng = a.rng
        for i in range(n):
            ang = rng.uniform(0, 6.28)
            d = rng.uniform(0, 0.09)
            _blade(a, (d * math.cos(ang), d * math.sin(ang), -0.01), ang, rng.uniform(0.08, 0.16), 0.035, rng.uniform(0.03, 0.09),
                   mix(gd, g, rng.random()), mix(g, gl, 0.5 + rng.random() * 0.5), 1.0, 1)
        a.opts['leaf'] = {'normal_up': 0.95, 'plain_normals': True}
        total += a.finish(ao=False)
    return total


def water_plants(name):
    """芦苇和荷花。原点在水面上"""
    total = 0
    a = Asset('reeds')
    rng = a.rng
    rd, rl = tint(C('reed'), -0.1), C('reed')
    for i in range(14):
        ang = rng.uniform(0, 6.28)
        d = rng.uniform(0, 0.4)
        x, y = d * math.cos(ang), d * math.sin(ang)
        h = rng.uniform(0.9, 1.6)
        _blade(a, (x, y, -0.5), ang, h + 0.5, 0.07, rng.uniform(0.15, 0.45), mix(C('grass_dark'), rd, 0.5), rl, 1.3, 3)
        if rng.random() < 0.4:
            a.cyl(0.012, h + 0.75, (x, y, -0.5), rd, segs=5, mat='leaf')
            a.lathe([(0.0, 0), (0.035, 0.02), (0.04, 0.2), (0.0, 0.24)], (x, y, h + 0.2), segs=6, color=C('trunk'), mat='leaf')
    a.opts['leaf'] = {'normal_up': 0.85, 'plain_normals': True}
    total += a.finish(view=(20, 35, 1.0), ao=False, ground=False)

    pad, padl, padd = C('pad'), C('pad_lit'), C('pad_dark')
    for v, (n, flowers) in {'a': (6, 2), 'b': (4, 1), 'c': (3, 0)}.items():
        a = Asset(f'lotus_{v}')
        rng = a.rng
        for i in range(n):
            ang = rng.uniform(0, 6.28)
            d = rng.uniform(0.2, 1.1) * (0.4 + 0.25 * i)
            x, y = d * math.cos(ang), d * math.sin(ang)
            r = rng.uniform(0.3, 0.55)
            # 贴水的荷叶每片高度错开几毫米：两片叠在同一高度会抢着显示
            lift = 0.012 + 0.006 * i if rng.random() < 0.7 else rng.uniform(0.15, 0.3)
            if lift > 0.1:
                a.cyl(0.015, lift + 0.4, (x, y, -0.4), padd, segs=5, mat='leaf')
            a.disc(r, (x, y, lift), padd if rng.random() < 0.3 else pad, segs=14, mat='leaf', rim=padl, notch=0.5 if lift < 0.1 else 0.0, rot=rng.uniform(0, 6.28),
                   tilt=(rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25)) if lift > 0.1 else (0, 0), cup=0.0 if lift < 0.1 else 0.07, sway=0.0 if lift < 0.1 else 0.6)
        for i in range(flowers):
            ang = rng.uniform(0, 6.28)
            d = rng.uniform(0.3, 0.8)
            x, y = d * math.cos(ang), d * math.sin(ang)
            h = rng.uniform(0.3, 0.45)
            a.cyl(0.014, h + 0.4, (x, y, -0.4), padd, segs=5, mat='leaf')
            lo, lol = C('lotus'), C('lotus_lit')
            for ring, (cnt, rr, up, ln) in enumerate(((8, 0.05, 0.35, 0.2), (6, 0.03, 0.9, 0.17))):
                for k in range(cnt):
                    a2 = 2 * math.pi * k / cnt + ring * 0.4
                    dv = Vector((math.cos(a2), math.sin(a2), up)).normalized()
                    sd = Vector((-math.sin(a2), math.cos(a2), 0)) * 0.055
                    p0 = Vector((x + rr * math.cos(a2), y + rr * math.sin(a2), h))
                    a.quad([p0, p0 + dv * ln * 0.55 + sd, p0 + dv * ln, p0 + dv * ln * 0.55 - sd], mat='leaf', colors=[lol, lo, tint(lo, -0.05, 0.08), lo],
                           sway=(0.5, 0.6, 0.7, 0.6))
            a.cyl(0.035, 0.04, (x, y, h), C('flower_y'), segs=8, mat='leaf')
        a.opts['leaf'] = {'normal_up': 0.85, 'plain_normals': True}
        total += a.finish(view=(20, 45, 1.0), ao=False, ground=False)
    return total


ASSETS = {'tree_wish': tree_wish, 'pines': pines, 'maples': maples, 'rounds': rounds, 'bamboo': bamboo, 'bushes': bushes, 'grass': grass,
          'water_plants': water_plants, 'ground_cover': ground_cover}
