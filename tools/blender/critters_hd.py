"""小鸟和锦鲤（近看也经得起的版本）：顶替 animals.py 的 bird_sparrow、bird_tit 和 props.py 的 koi_a~d（名字相同）。

小鸟：身体是细分得很密的球，羽色按部位画（麻雀的栗色头顶、白脸颊上的黑斑、黑喉、背上的深色纵纹、翅上的白斑）；
翅膀和尾巴是一根根羽毛拼的，每根羽毛中间一道羽轴、边缘深浅不同。部件名还是 body、wing_l、wing_r、tail（Bird.cs 靠名字找翅膀）。
锦鲤：身体按鳞片一片片画深浅（每片鳞的下缘亮、上缘暗），红白花斑按位置画；鳍是一条条鳍条撑开的薄膜。
"""
import math

import bmesh
from mathutils import Vector, noise

from kit import Asset, new_bm, xform
from palette import hexc, mix, tint, vary


def _shape(a, mat, loc, scale, colorfn, subdiv=4, deform=None, sway=0.0):
    """一个光滑的团（细分很密），颜色按位置算：colorfn(单位球上的点) → 颜色"""
    t = new_bm()
    bmesh.ops.create_icosphere(t, subdivisions=subdiv, radius=1.0)
    col = t.loops.layers.float_color['col']
    for v in t.verts:
        if deform:
            v.co = deform(v.co.copy())
    for f in t.faces:
        f.smooth = True
        for l in f.loops:
            c = colorfn(l.vert.co.normalized())
            l[col] = (c[0], c[1], c[2], sway)
    a.merge(t, mat, xform(loc, (0, 0, 0), scale))


def _feather(a, part, base, d, side, L, W, edge, mid, shaft, tip=None):
    """一根羽毛：两半拼成，中间一道羽轴（颜色在中线断开），羽片略带弧度"""
    d, side = Vector(d).normalized(), Vector(side).normalized()
    up = side.cross(d).normalized()
    b = Vector(base)
    tip = tip or edge
    m = b + d * (L * 0.45)
    e = b + d * L
    for sg in (-1, 1):
        w1 = b + d * (L * 0.12) + side * (sg * W * 0.34)
        w2 = m + side * (sg * W * 0.5) + up * 0.0012
        w3 = b + d * (L * 0.84) + side * (sg * W * 0.4)
        pts = [b, w1, w2, m] if sg < 0 else [b, m, w2, w1]
        a.quad(pts, mat=part, colors=[shaft, mix(mid, edge, 0.3), edge, shaft] if sg < 0 else [shaft, shaft, edge, mix(mid, edge, 0.3)])
        pts = [m, w2, w3, e] if sg < 0 else [m, e, w3, w2]
        a.quad(pts, mat=part, colors=[shaft, edge, tip, tint(shaft, 0.05)] if sg < 0 else [shaft, tint(shaft, 0.05), tip, edge])


def _bird(name, look):
    a = Asset(name)
    rng = a.rng
    B = 'toon:body'
    L = look
    # 身体：圆胖、前高后低
    def body_col(p):
        x, y, z = p.x, p.y, p.z
        c = L['belly']
        back = max(0.0, min(1.0, (z + 0.15) * 2.2))
        c = mix(c, L['back'], back)
        if z > 0.1:      # 背上的纵纹
            s = noise.noise(Vector((x * 14, y * 3, z * 2)))
            if s > 0.18:
                c = mix(c, L['streak'], 0.75)
        if y > 0.55 and z < 0.2 and abs(x) < 0.5:      # 喉部
            c = mix(c, L['bib'], max(0.0, min(1.0, (y - 0.55) * 4)) * L['bib_amt'])
        return vary(c, rng, 0.015, 0.01)
    _shape(a, B, (0, 0, 0.085), (0.07, 0.092, 0.068), body_col, subdiv=4,
           deform=lambda v: Vector((v.x, v.y, v.z + 0.12 * max(0, v.y) * (v.z + 1) * 0.5)))

    # 头
    def head_col(p):
        x, y, z = p.x, p.y, p.z
        c = L['cap'] if z > 0.15 + 0.2 * y else L['cheek']
        if L.get('cheek_spot') and abs(x) > 0.55 and -0.1 < z < 0.25 and -0.3 < y < 0.3:
            c = L['cheek_spot']
        if z < -0.2 and y > 0.0:
            c = mix(c, L['bib'], L['bib_amt'])
        if L.get('collar') and z < -0.45:
            c = L['collar']
        return vary(c, rng, 0.01, 0.01)
    _shape(a, B, (0, 0.075, 0.15), (0.05, 0.05, 0.048), head_col, subdiv=4)
    # 喙：上下两片
    a.lathe([(0.013, 0.0), (0.009, 0.014), (0.0, 0.036)], (0, 0.118, 0.152), segs=10, color=L['beak'], rot=(-math.pi / 2, 0, 0), mat=B,
            squash=(1.0, 0.75))
    a.lathe([(0.01, 0.0), (0.0, 0.026)], (0, 0.118, 0.142), segs=8, color=tint(L['beak'], -0.08), rot=(-math.pi / 2 + 0.2, 0, 0), mat=B,
            squash=(1.0, 0.6))
    # 眼睛：黑眼珠、一圈细眼圈、两个高光
    for sx in (-1, 1):
        a.blob(0.0115, (sx * 0.037, 0.098, 0.162), (0.6, 1, 1), (0.04, 0.03, 0.03), subdiv=2, bump=0, mat=B)
        a.blob(0.004, (sx * 0.042, 0.104, 0.168), (0.6, 1, 1), (1, 1, 1), subdiv=1, bump=0, mat=B)
        a.blob(0.0022, (sx * 0.043, 0.098, 0.157), (0.6, 1, 1), (0.9, 0.9, 0.95), subdiv=1, bump=0, mat=B)
    # 腿和脚趾
    for sx in (-1, 1):
        x0 = sx * 0.024
        a.tube([(x0, 0.01, 0.045), (x0, 0.015, 0.02), (x0, 0.02, 0.003)], [0.0045, 0.004, 0.0035], L['leg'], segs=6, mat=B)
        for ang in (-0.5, 0.0, 0.5, math.pi):
            ln = 0.022 if ang != math.pi else 0.016
            dx, dy = math.sin(ang) * ln, math.cos(ang) * ln
            a.tube([(x0, 0.02, 0.003), (x0 + dx * 0.6, 0.02 + dy * 0.6, 0.002), (x0 + dx, 0.02 + dy, 0.0)], [0.003, 0.0026, 0.0018], L['leg'], segs=5, mat=B)
    # 翅膀：在身体两侧展开（停着时 Bird.cs 把它收起来）
    for nm, sx in (('wing_l', -1), ('wing_r', 1)):
        P = 'leaf:' + nm
        sh = Vector((sx * 0.05, 0.03, 0.115))
        # 初级飞羽：从翼尖往后散开
        for i in range(9):
            k = i / 8
            base = sh + Vector((sx * (0.075 + 0.055 * k), -0.008 - 0.016 * k, -0.002 * i))
            d = Vector((sx * (0.9 - 0.75 * k), -1.0, 0.0))
            _feather(a, P, base, d, Vector((1, sx * (0.9 - 0.75 * k), 0)), 0.115 + 0.02 * math.sin(math.pi * k), 0.03, L['flight_edge'], L['flight'], tint(L['flight'], -0.12),
                     tip=tint(L['flight'], -0.1))
        # 次级飞羽：沿着翅膀内侧
        for i in range(7):
            k = i / 6
            base = sh + Vector((sx * (0.01 + 0.07 * k), -0.005, 0.003))
            _feather(a, P, base, Vector((sx * 0.1, -1.0, 0.0)), Vector((sx, 0, 0)), 0.08, 0.03, L['flight_edge'], L['flight'], tint(L['flight'], -0.1))
        # 覆羽：两排短的，盖在飞羽根上（麻雀这里有两道白斑）
        for row, (yo, ln, c, n) in enumerate(((0.0, 0.05, L['wingbar'], 7), (0.014, 0.04, L['covert'], 8), (0.026, 0.03, L['wingbar'], 6), (0.036, 0.026, L['covert'], 6))):
            for i in range(n):
                k = i / (n - 1)
                base = sh + Vector((sx * (0.005 + (0.12 - 0.02 * row) * k + 0.006 * row), 0.006 + yo, 0.003 + 0.0025 * row))
                _feather(a, P, base, Vector((sx * 0.12, -1.0, 0.0)), Vector((sx, 0, 0)), ln, 0.034 - 0.003 * row, tint(c, 0.06), c, tint(c, -0.08))
    # 尾羽：一扇
    for i in range(10):
        k = i / 9 - 0.5
        base = Vector((k * 0.02, -0.07, 0.1))
        _feather(a, 'leaf:tail', base, Vector((k * 0.45, -1.0, -0.08)), Vector((1, 0, 0)), 0.1 - 0.02 * abs(k), 0.024, L['flight_edge'], L['tail'],
                 tint(L['tail'], -0.1))
    for p in ('leaf:tail', 'leaf:wing_l', 'leaf:wing_r'):
        a.opts[p] = {'plain_normals': True, 'normal_up': 0.6}
    import os
    return a.finish(ao=False, view=tuple(float(x) for x in os.environ.get('YJ_VIEW', '35,30,1.0').split(',')))


SPARROW = dict(belly=hexc('#ede4d4'), back=hexc('#9b6e47'), streak=hexc('#4a3424'), bib=hexc('#1e1b1a'), bib_amt=0.95, cap=hexc('#7d4a2b'),
               cheek=hexc('#f4efe6'), cheek_spot=hexc('#1f1c1b'), beak=hexc('#3a3330'), leg=hexc('#c99a72'), flight=hexc('#6a4a33'),
               flight_edge=hexc('#c49a6c'), covert=hexc('#8a5d3c'), wingbar=hexc('#f2ece0'), tail=hexc('#6b4c36'))
TIT = dict(belly=hexc('#f3d75e'), back=hexc('#6d8f74'), streak=hexc('#5b7a62'), bib=hexc('#1c1c22'), bib_amt=0.9, cap=hexc('#1c1c24'),
           cheek=hexc('#f6f4ee'), beak=hexc('#2a2a2e'), leg=hexc('#5a6878'), flight=hexc('#45607a'), flight_edge=hexc('#9cb6cc'),
           covert=hexc('#5a7c96'), wingbar=hexc('#e8eef2'), tail=hexc('#3d5468'), collar=hexc('#1c1c24'))


def _koi(name, base, patch, pattern, seed):
    """锦鲤：头朝 +y，原点在身体中间。pattern：花斑怎么分布（'kohaku' 红白、'showa' 三色、'gold' 黄金、'tancho' 丹顶）"""
    a = Asset(name)
    rng = a.rng
    t = new_bm()
    col = t.loops.layers.float_color['col']
    R, S = 44, 32         # 沿身体几圈、每圈几个点
    length = 0.62
    rings = []
    for i in range(R + 1):
        u = i / R                    # 0 是嘴，1 是尾柄
        y = length / 2 - u * length * 0.82
        r = 0.088 * (math.sin(math.pi * min(1.0, 0.06 + u * 1.02)) ** 0.75) * (1.2 - 0.55 * u) + 0.004
        ring = []
        for j in range(S):
            th = 2 * math.pi * j / S
            ring.append(t.verts.new((math.cos(th) * r * 0.82, y, math.sin(th) * r * 1.02)))
        rings.append(ring)
    tip0 = t.verts.new((0, length / 2 + 0.01, 0))

    def colour(u, th):
        x, z = math.cos(th), math.sin(th)
        top = max(0.0, z)
        q = Vector((u * 5, x * 1.4, z * 1.4 + seed))
        n = noise.noise(q) + 0.5 * noise.noise(q * 2.3)
        if pattern == 'kohaku':
            c = patch if (n > -0.05 and top > 0.05) or (u < 0.18 and top > 0.3) else base
        elif pattern == 'tancho':
            c = patch if (u - 0.1) ** 2 + (x * 0.25) ** 2 < 0.006 and top > 0.4 else base
        elif pattern == 'showa':
            c = patch if n > 0.1 and top > 0.0 else (hexc('#1d1a1a') if n < -0.32 else base)
        else:
            c = mix(base, patch, max(0.0, n))
        # 肚子发白、背上深一点
        c = mix(c, hexc('#f6f1e6'), max(0.0, -z - 0.35) * 0.9)
        c = tint(c, 0.04 * z)
        # 鳞片：一排排错开，每片下缘（靠尾）亮、上缘暗
        sv = u * 34
        su = th / (2 * math.pi) * 26 + (0.5 if int(sv) % 2 else 0.0)
        fu, fv = su - math.floor(su) - 0.5, sv - math.floor(sv)
        edge = fv + 0.6 * fu * fu
        scale_shade = 0.06 * (edge - 0.5) * (1 if u > 0.16 else 0)
        if 0.9 < edge < 1.05 and u > 0.16:
            scale_shade -= 0.06
        return tint(c, scale_shade)

    for i in range(R):
        for j in range(S):
            j2 = (j + 1) % S
            f = t.faces.new((rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]))
            f.smooth = True
            for l in f.loops:
                ii = i if l.vert in rings[i] else i + 1
                jj = rings[ii].index(l.vert)
                c = colour(ii / R, 2 * math.pi * jj / S)
                l[col] = (c[0], c[1], c[2], 0)
    for j in range(S):
        f = t.faces.new((tip0, rings[0][(j + 1) % S], rings[0][j]))
        f.smooth = True
        for l in f.loops:
            c = colour(0.0, 2 * math.pi * j / S)
            l[col] = (c[0], c[1], c[2], 0)
    end = t.verts.new((0, rings[-1][0].co.y - 0.004, 0))
    for j in range(S):
        f = t.faces.new((end, rings[-1][j], rings[-1][(j + 1) % S]))
        for l in f.loops:
            l[col] = (base[0], base[1], base[2], 0)
    yt = rings[-1][0].co.y
    a.merge(t, 'toon')

    def fin(root_pts, tip_pts, c0, c1, rays=True):
        """鳍：沿根一排点、沿外缘一排点，之间是一条条鳍条撑开的膜（鳍条颜色深一点）"""
        n = len(root_pts)
        for i in range(n - 1):
            ray = rays and i % 2 == 0
            ca, cb = (tint(c0, -0.06), tint(c1, -0.04)) if ray else (c0, c1)
            a.quad([root_pts[i], root_pts[i + 1], tip_pts[i + 1], tip_pts[i]], mat='leaf', colors=[ca, c0, c1, cb])

    fc0, fc1 = mix(base, hexc('#ffffff'), 0.35), mix(base, hexc('#ffffff'), 0.7)
    # 尾鳍：分成上下两叶，中间凹进去
    root, tipp = [], []
    for k in range(13):
        s = k / 12 * 2 - 1
        root.append(Vector((0, yt + 0.01, s * 0.02)))
        ln = 0.17 - 0.06 * math.cos(s * math.pi) * -1 - 0.05
        tipp.append(Vector((0.01 * math.sin(k), yt - ln, s * 0.13)))
    fin(root, tipp, fc0, fc1)
    # 背鳍：从背中间到靠后，长条
    root = [Vector((0, 0.08 - 0.022 * k, 0.088 - 0.004 * k)) for k in range(13)]
    tipp = [Vector((0, 0.08 - 0.022 * k - 0.03, 0.088 - 0.004 * k + 0.055 * math.sin(math.pi * (0.15 + 0.85 * k / 12)))) for k in range(13)]
    fin(root, tipp, fc0, fc1)
    # 胸鳍、腹鳍
    for sx in (-1, 1):
        for (yy, zz, ln) in ((0.13, -0.05, 0.1), (-0.05, -0.07, 0.07)):
            root = [Vector((sx * 0.05, yy - 0.01 * k, zz)) for k in range(7)]
            tipp = [Vector((sx * (0.05 + ln * math.cos(0.3 + 0.12 * k)), yy - 0.01 * k - ln * 0.6, zz - 0.02 - ln * 0.25)) for k in range(7)]
            fin(root, tipp, fc0, fc1)
        # 胡须两对、眼睛
        for (yy, zz, ln) in ((0.3, -0.01, 0.035), (0.29, 0.005, 0.02)):
            a.tube([(sx * 0.018, yy, zz), (sx * 0.03, yy + ln * 0.5, zz - 0.01), (sx * 0.035, yy + ln * 0.3, zz - 0.025)], [0.0025, 0.002, 0.0012],
                   tint(base, -0.05), segs=4)
        a.blob(0.011, (sx * 0.042, 0.255, 0.02), (0.6, 1, 1), hexc('#151314'), subdiv=2, bump=0)
        a.blob(0.0035, (sx * 0.047, 0.26, 0.026), (0.6, 1, 1), (1, 1, 1), subdiv=1, bump=0)
    a.opts['leaf'] = {'plain_normals': True}
    return a.finish(ao=False, view=(20, 60, 1.0), floor=False)


ASSETS = {
    'bird_sparrow': lambda n: _bird(n, SPARROW),
    'bird_tit': lambda n: _bird(n, TIT),
    'koi_a': lambda n: _koi(n, hexc('#f7f3ea'), hexc('#d8432a'), 'kohaku', 1.3),
    'koi_b': lambda n: _koi(n, hexc('#f7f3ea'), hexc('#d8432a'), 'tancho', 2.1),
    'koi_c': lambda n: _koi(n, hexc('#f0b232'), hexc('#ffd86a'), 'gold', 3.7),
    'koi_d': lambda n: _koi(n, hexc('#f7f3ea'), hexc('#e0602e'), 'showa', 5.2),
}
