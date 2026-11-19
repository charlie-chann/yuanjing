"""树（近看也经得起的做法）：真的一级级分枝，树皮用实拍处理成手绘感的贴图，
树冠是几千张「小枝卡片」（每张贴一小枝画出来的叶子，见 tools/textures/leaves.py），不是一团团的球。

卡片的光照法线统一朝树冠外（一半按整棵树、一半按它所在的那一大枝），所以明暗是成团的：每一大枝上亮下暗，
凑近看每片叶子的轮廓和叶脉又是清楚的。这是动漫画风的树的通用做法。

这里的 tree_wish 顶替 plants.py 里旧的那棵（build.py 里 trees 排在 plants 后面）。绳圈的尺寸不变，
Unity 那边（BuildIslet.cs 的 RopeRing）不用改。
"""
import math

from mathutils import Quaternion, Vector

from kit import Asset, new_bm
from palette import C, mix, tint, vary

UP = Vector((0, 0, 1))
MOSS = (0.36, 0.47, 0.24)


def _perp(d):
    r = d.cross(UP)
    if r.length < 1e-4:
        r = d.cross(Vector((1, 0, 0)))
    return r.normalized()


def limb(a, rng, pts, radii, sides, c0, c1=None, mat='bark', noise=0.0, lobes=None, cap=True, moss=0.0):
    """一段枝干：沿一串点的管子。和 kit.tube 的区别：截面不是正圆（noise 让它疙疙瘩瘩的），
    lobes=(角度们, 每一圈鼓多少) 让树干根部朝着每条树根的方向鼓出去（板根）；moss：贴地的那一截长多少青苔"""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    t = new_bm()
    col = t.loops.layers.float_color['col']
    uv = t.loops.layers.uv['uv']
    tang = [(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(n)]
    ref = UP if abs(tang[0].z) < 0.9 else Vector((1, 0, 0))
    nrm = (ref - tang[0] * ref.dot(tang[0])).normalized()
    ph = [rng.uniform(0, 6.28) for _ in range(4)]
    rings = []
    for i in range(n):
        if i > 0:
            nrm = nrm - tang[i] * nrm.dot(tang[i])
            nrm = nrm.normalized() if nrm.length > 1e-6 else _perp(tang[i])
        bi = tang[i].cross(nrm).normalized()
        ring = []
        for k in range(sides):
            ang = 2 * math.pi * k / sides
            r = radii[i]
            if noise:
                r *= 1 + noise * (0.6 * math.sin(ang * 2 + ph[0] + i * 0.7) + 0.4 * math.sin(ang * 3 + ph[1] - i * 1.1)
                                  + 0.35 * math.sin(ang * 5 + ph[2] + i * 1.9))
            if lobes:
                bulge = max(math.exp(-(((ang - la + math.pi) % (2 * math.pi) - math.pi) / 0.3) ** 2) for la in lobes[0])
                r *= 1 + lobes[1][i] * bulge
            ring.append(t.verts.new(pts[i] + (nrm * math.cos(ang) + bi * math.sin(ang)) * r))
        rings.append(ring)
    where = {}
    for i, ring in enumerate(rings):
        for v in ring:
            where[v] = i / max(1, n - 1)
    for i in range(n - 1):
        for k in range(sides):
            j = (k + 1) % sides
            t.faces.new((rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]))
    if cap:
        t.faces.new(list(reversed(rings[-1])))
    for f in t.faces:
        for l in f.loops:
            c = mix(c0, c1, where[l.vert]) if c1 is not None else c0
            if moss:
                co = l.vert.co
                m = max(0.0, min(1.0, (0.62 - co.z) / 0.55)) * (0.55 + 0.45 * math.sin(co.x * 4.1 + ph[3]) * math.cos(co.y * 3.7 + ph[2]))
                c = mix(c, MOSS, max(0.0, m) * moss)
            l[col] = (c[0], c[1], c[2], 0)
            l[uv].uv = (0, 0)
    a.merge(t, mat)


class Grower:
    """一级级往外长枝。spec 里每一级一组数：
    segs 分几段、sides 截面几条边、wiggle 弯弯曲曲的程度、up 往上翘（负的是下垂）、
    kids 分几个杈、start 从枝的哪里开始分、ang 杈和枝的夹角（度）、lift 杈再往上抬多少、r 杈比枝细多少、l 杈比枝短多少"""

    def __init__(self, a, spec, leaf_mat, crown_c, colors, bark):
        self.a, self.rng, self.spec, self.leaf_mat = a, a.rng, spec, leaf_mat
        self.crown_c = Vector(crown_c)
        self.colors, self.bark = colors, bark
        self.hang = []        # 能挂布条的地方（中等粗细的枝上的点）
        self.cards = 0
        # 下面几样按树的大小定，灌木会改小
        self.cluster_level = 2          # 从第几级枝开始算「一团」
        self.size = (0.5, 0.7)          # 一张小枝卡片多大（米）
        self.every = 0.13               # 细枝上每隔多远一枝叶子
        self.hi = (3.6, 5.0)            # 多高以上的叶子偏亮：(起点, 范围)
        self.sway = (3.0, 5.5)          # 离 (0,0,起点) 越远摆得越多：(起点高度, 多远摆到最大)
        self.blossom = None             # 开花：(贴图材质, 梢上有多大比例是花, 花的颜色)
        self.bark_mat = 'bark'          # 树皮用哪套贴图
        self.roll = 1.25                # 叶片卡绕枝转多少（小了叶片都平躺着：松针一片片的「云片」）
        self.odd = (0.14, 0.03)         # 多大比例的叶子是新叶（黄绿）、多大比例是老叶（发红）

    def branch(self, p0, d0, r0, L, level, cluster=None):
        rng, s = self.rng, self.spec[level]
        last = level == len(self.spec)
        n = s['segs']
        pts, d = [Vector(p0)], Vector(d0).normalized()
        for i in range(n):
            rnd = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
            d = (d + rnd * s['wiggle'] + UP * s['up']).normalized()
            pts.append(pts[-1] + d * (L / n))
        end = s.get('taper', 0.42)
        radii = [r0 * (1 - (1 - end) * (i / n) ** 0.9) for i in range(n + 1)]
        dark, lit = self.bark
        limb(self.a, rng, pts, radii, s['sides'], mix(dark, lit, min(1, level * 0.22)), mix(dark, lit, min(1, level * 0.22 + 0.2)),
             noise=s.get('noise', 0.0), mat=self.bark_mat)

        def at(t):
            x = t * n
            i = min(n - 1, int(x))
            f = x - i
            return pts[i].lerp(pts[i + 1], f), (pts[i + 1] - pts[i]).normalized(), radii[i] + (radii[i + 1] - radii[i]) * f

        if level == self.cluster_level:
            # 这一大枝连同它上面所有的小枝算「一团」：叶子的明暗按这一团来分
            cluster = (pts[0] + (pts[-1] - pts[0]) * 0.75 + UP * 0.25, max(0.8, L * 0.8))
        if 2 <= level <= 3:
            for t in (0.35, 0.7):
                p, _, _ = at(t)
                self.hang.append(p)

        if last:
            self.sprigs(pts, at, cluster)
            return
        k = s['kids']
        az0 = rng.uniform(0, 6.28)
        for j in range(k):
            t = s['start'] + (1 - s['start']) * (j + rng.uniform(0.2, 0.8)) / k
            tip = j == k - 1
            if tip:
                t = 1.0
            p, dd, rr = at(t)
            ang = math.radians(s['ang'] * rng.uniform(0.75, 1.25)) * (0.35 if tip else 1.0)
            side = Quaternion(dd, az0 + j * 2.399 + rng.uniform(-0.4, 0.4)) @ _perp(dd)
            cd = (dd * math.cos(ang) + side * math.sin(ang) + UP * s.get('lift', 0.0)).normalized()
            cr = (rr if tip else min(rr * 0.92, r0 * s['r'] * rng.uniform(0.85, 1.12)))
            cl = L * s['l'] * rng.uniform(0.85, 1.15) * (1 - 0.2 * t)
            self.branch(p, cd, cr, cl, level + 1, cluster)
        # 靠外的细枝上也直接长几枝叶子，树冠里面不会空
        if level == len(self.spec) - 1:
            self.sprigs(pts, at, cluster, every=self.every * 2.3, start=0.45)

    def sprigs(self, pts, at, cluster, every=None, start=0.2):
        rng = self.rng
        every = every or self.every
        L = sum((pts[i + 1] - pts[i]).length for i in range(len(pts) - 1))
        cnt = max(2, int(L * (1 - start) / every))
        for i in range(cnt + 3):
            tipfan = i >= cnt             # 梢上再多出三枝，朝不同方向散开
            t = 1.0 if tipfan else start + (1 - start) * (i + rng.uniform(0, 0.6)) / cnt
            p, d, _ = at(min(1.0, t))
            sgn = 1 if i % 2 == 0 else -1
            out = _perp(d) * sgn
            if tipfan:
                out = Quaternion(d, (i - cnt) * 2.1 + rng.uniform(-0.3, 0.3)) @ _perp(d)
                axis = (d * rng.uniform(0.7, 1.1) + out * rng.uniform(0.2, 0.6) + UP * rng.uniform(-0.3, 0.1)).normalized()
            else:
                axis = (d * rng.uniform(0.3, 0.8) + out * rng.uniform(0.5, 1.0) + UP * rng.uniform(-0.45, 0.15)).normalized()
            self.card(p, axis, cluster, flower=tipfan and self.blossom is not None and rng.random() < self.blossom[1])

    def card(self, p, axis, cluster, flower=False):
        rng = self.rng
        flat = _perp(axis)
        side = Quaternion(axis, rng.uniform(-self.roll, self.roll)) @ flat      # 有平着的、有斜着的、有快竖起来的：从哪边看都不会只剩一条线
        size = rng.uniform(*self.size)
        ctr = p + axis * size * 0.5
        cc, cr = cluster
        n = ((ctr - self.crown_c).normalized() * 0.5 + (ctr - cc).normalized() * 0.5 + UP * 0.2).normalized()
        depth = min(1.0, (ctr - cc).length / cr)
        hi = max(0.0, min(1.0, (ctr.z - self.hi[0]) / self.hi[1]))
        deep, base, lit, young = self.colors
        c = mix(deep, base, depth ** 0.7)
        c = mix(c, lit, 0.4 * hi * depth)
        r = rng.random()
        if r < self.odd[0]:
            c = mix(c, young, 0.55)          # 新叶：黄绿
        elif r < self.odd[0] + self.odd[1]:
            c = mix(c, (0.78, 0.36, 0.22), 0.5)   # 老叶会红，零星几枝
        c = vary(c, rng, 0.05, 0.05, 0.012)
        sway = 0.25 + 0.6 * min(1.0, (ctr - Vector((0, 0, self.sway[0]))).length / self.sway[1])
        mat = self.leaf_mat
        if flower:
            mat, c = self.blossom[0], vary(self.blossom[2], rng, 0.04, 0.05, 0.01)
            n = (n + UP * 0.6).normalized()
        self.a.card(p, axis, side, size, size, mat, c, n, bend=rng.uniform(-0.1, 0.13), rows=2, sway=sway)
        self.cards += 1


def tree_wish(name):
    """许愿树：老樟树。粗干盘根，五六根大枝撑开一大蓬树冠；枝上系着红布条；四周一圈木桩拉着绳子。"""
    a = Asset(name)
    rng = a.rng
    # 老樟树的皮：灰褐色，比别的树深
    dark, mid, lit = (0.30, 0.23, 0.18), (0.42, 0.33, 0.26), (0.55, 0.45, 0.36)

    # 树根：七条，从树干根部爬出去钻进土里
    roots = [2 * math.pi * i / 7 + rng.uniform(-0.2, 0.2) for i in range(7)]
    for ang in roots:
        c, s = math.cos(ang), math.sin(ang)
        k = rng.uniform(1.35, 1.9)
        w = rng.uniform(-0.25, 0.25)
        limb(a, rng, [(0.3 * c, 0.3 * s, 0.7), (0.7 * c, 0.7 * s, 0.3),
                      (1.05 * c - w * s * 0.3, 1.05 * s + w * c * 0.3, 0.1), (k * c - w * s, k * s + w * c, 0.0),
                      ((k + 0.45) * c - w * s * 1.4, (k + 0.45) * s + w * c * 1.4, -0.14)],
             [0.3, 0.24, 0.17, 0.11, 0.04], 10, dark, mid, noise=0.1, moss=0.8)
    # 树干：根部朝着每条树根鼓出去，往上略收，分杈的地方又粗一点
    # 顶上收成圆头，大枝从里面长出来（不收的话分杈处是个平台）
    zs = [-0.15, 0.12, 0.4, 0.8, 1.3, 1.9, 2.5, 2.9, 3.15, 3.32, 3.4]
    rs = [0.9, 0.82, 0.7, 0.63, 0.59, 0.56, 0.56, 0.58, 0.5, 0.32, 0.1]
    lean = [(0.0, 0.0), (0.0, 0.0), (0.01, 0.0), (0.04, 0.01), (0.02, 0.05), (-0.06, 0.07), (-0.08, 0.03), (-0.05, 0.0),
            (-0.05, 0.0), (-0.05, 0.0), (-0.05, 0.0)]
    limb(a, rng, [(lean[i][0], lean[i][1], zs[i]) for i in range(len(zs))], rs, 24, dark, mid, noise=0.05,
         lobes=(roots, [0.45, 0.4, 0.3, 0.16, 0.06, 0, 0, 0, 0, 0, 0]), moss=0.7)
    # 锯掉的老枝留下的两个疤
    for ang, z in ((0.9, 1.7), (3.6, 2.2)):
        c, s = math.cos(ang), math.sin(ang)
        limb(a, rng, [(0.42 * c, 0.42 * s, z), (0.66 * c, 0.66 * s, z + 0.08), (0.74 * c, 0.74 * s, z + 0.1)], [0.17, 0.14, 0.12], 9, dark, lit, noise=0.06)

    spec = {
        1: dict(segs=11, sides=12, wiggle=0.07, up=0.065, kids=5, start=0.3, ang=52, lift=0.25, r=0.56, l=0.6, noise=0.05),
        2: dict(segs=7, sides=8, wiggle=0.1, up=0.036, kids=4, start=0.25, ang=50, lift=0.15, r=0.55, l=0.62, noise=0.04),
        3: dict(segs=5, sides=6, wiggle=0.15, up=-0.016, kids=4, start=0.2, ang=46, lift=0.0, r=0.5, l=0.62),
        4: dict(segs=3, sides=4, wiggle=0.2, up=-0.06, taper=0.35),
    }
    g = Grower(a, spec, 'leaf_camphor', (0, 0, 5.6),
               (C('leaf_deep'), C('leaf'), C('leaf_lit'), (0.72, 0.84, 0.36)), (dark, mid))
    top = Vector((-0.05, 0.0, 2.75))
    for i in range(5):
        ang = 2 * math.pi * i / 5 + 0.3 + rng.uniform(-0.2, 0.2)
        inc = math.radians(rng.uniform(40, 54))
        d = Vector((math.cos(ang) * math.sin(inc), math.sin(ang) * math.sin(inc), math.cos(inc)))
        g.branch(top + Vector((math.cos(ang) * 0.12, math.sin(ang) * 0.12, 0.05 * i)), d, rng.uniform(0.3, 0.36), rng.uniform(4.0, 4.6), 1)
    g.branch(top + Vector((0, 0, 0.1)), Vector((0.08, -0.05, 1)), 0.34, 4.0, 1)      # 中间往上的主枝
    print(f'[yjm] {name}: {g.cards} 枝叶子')

    # 枝上系着的红布条（比绳圈高，抬头才看得到）
    red = C('cloth_red')
    spots = [p for p in g.hang if 3.3 < p.z < 5.6 and 0.8 < math.hypot(p.x, p.y) < 3.9]
    rng.shuffle(spots)
    for p in spots[:22]:
        ang = rng.uniform(0, 6.28)
        ln = rng.uniform(0.6, 1.15)
        d = Vector((math.cos(ang), math.sin(ang), 0)) * 0.035
        col = vary(red, rng, 0.05, 0.03)
        for sgn, k in ((1, 1.0), (-1, 0.72)):          # 打了结垂下来的两头，一长一短
            q = p + Vector((math.cos(ang + 1.57), math.sin(ang + 1.57), 0)) * 0.03 * sgn
            a.quad([q - d, q + d, q + d + Vector((0, 0, -ln * k)), q - d + Vector((0, 0, -ln * k))], mat='leaf',
                   colors=[col, col, tint(col, -0.06), tint(col, -0.06)], sway=(0.1, 0.1, 1.8, 1.8))

    # 绳圈：八根木桩，绳子略微下垂（Unity 那边按这个挂布条和木牌：BuildIslet.cs 的 RopePosts、RopeR、RopeH 要同改）
    # 绳高 1.55 → 1.2（2026-11-17）：1.25 米高的小人系布条时手在胸口到肩的高度，不用踮脚够
    N, R, H = 8, 2.95, 1.2
    for i in range(N):
        ang = 2 * math.pi * (i + 0.5) / N
        x, y = R * math.cos(ang), R * math.sin(ang)
        a.cyl(0.075, H + 0.12, (x, y, 0), C('wood'), r2=0.065, segs=12, grad=(C('wood_dark'), C('wood_lit')), mat='wood')
        a.lathe([(0.0, 0), (0.09, 0.01), (0.1, 0.06), (0.06, 0.1), (0.0, 0.12)], (x, y, H + 0.1), segs=12, color=C('red'))
        ang2 = 2 * math.pi * (i + 1.5) / N
        x2, y2 = R * math.cos(ang2), R * math.sin(ang2)
        pts = []
        for k in range(13):
            t = k / 12
            pts.append((x + (x2 - x) * t, y + (y2 - y) * t, H - 0.2 * 4 * t * (1 - t)))
        a.tube(pts, 0.024, C('rope'), segs=8, mat='straw')
    return a.finish(view=(15, 20, 0.95), dist=1.8)


def shrub(name, stems=7, reach=0.75, flower=None, seed_tilt=(25, 62)):
    """灌木：从根上发出一把细枝，枝上密密的小叶子。flower：开花的颜色（杜鹃那样，花开在枝梢）"""
    a = Asset(name)
    rng = a.rng
    dark, lit = (0.3, 0.24, 0.18), (0.48, 0.38, 0.28)
    spec = {
        1: dict(segs=5, sides=5, wiggle=0.16, up=0.09, kids=4, start=0.3, ang=48, lift=0.2, r=0.6, l=0.55, taper=0.5),
        2: dict(segs=3, sides=4, wiggle=0.2, up=0.02, taper=0.4),
    }
    g = Grower(a, spec, 'leaf_camphor', (0, 0, reach * 0.45),
               ((0.16, 0.36, 0.2), (0.27, 0.53, 0.25), (0.48, 0.72, 0.32), (0.66, 0.82, 0.36)), (dark, lit))
    g.cluster_level, g.size, g.every = 1, (0.26, 0.38), 0.075
    g.hi, g.sway = (reach * 0.35, reach * 0.8), (0.1, reach * 1.2)
    if flower is not None:
        g.blossom = ('leaf_blossom', 0.6, flower)
    for i in range(stems):
        ang = 2 * math.pi * i / stems + rng.uniform(-0.35, 0.35)
        inc = math.radians(rng.uniform(*seed_tilt)) * (0.3 if i == 0 else 1.0)
        d = Vector((math.cos(ang) * math.sin(inc), math.sin(ang) * math.sin(inc), math.cos(inc)))
        g.branch(Vector((math.cos(ang) * 0.05, math.sin(ang) * 0.05, -0.02)), d, rng.uniform(0.02, 0.03), reach * rng.uniform(0.85, 1.2), 1)
    return a.finish(view=(20, 30, 1.0), dist=0.5)


def broadleaf(name, h, crown, trunk_r, leaf, colors, bark, bark_mat='bark_dark', stems=1, kids=4, lean=0.15, size=(0.5, 0.7),
              blossom=None, odd=(0.12, 0.0), every=0.15):
    """阔叶树（枫、银杏、樱、圆冠的杂树）：一到三根主干，往上分四级枝，枝梢挂叶片卡。
    h 树高、crown 树冠半径、colors=(深, 中, 亮, 新叶)、bark=(暗, 亮) 树皮颜色"""
    a = Asset(name)
    rng = a.rng
    dark, lit = bark
    trunk_h = h - crown * 1.25
    g = Grower(a, {
        1: dict(segs=8, sides=10, wiggle=0.08, up=0.07, kids=kids, start=0.35, ang=46, lift=0.2, r=0.58, l=0.62, noise=0.04),
        2: dict(segs=6, sides=7, wiggle=0.12, up=0.04, kids=4, start=0.25, ang=48, lift=0.12, r=0.55, l=0.62),
        3: dict(segs=4, sides=5, wiggle=0.16, up=-0.01, kids=4, start=0.2, ang=46, lift=0.0, r=0.5, l=0.62),
        4: dict(segs=3, sides=4, wiggle=0.2, up=-0.05, taper=0.35),
    }, leaf, (0, 0, trunk_h + crown * 0.6), colors, (dark, lit))
    g.bark_mat, g.size, g.odd, g.every = bark_mat, size, odd, every
    g.hi, g.sway = (trunk_h, crown * 2), (trunk_h * 0.6, crown * 1.6)
    if blossom is not None:
        g.blossom = blossom
    for si in range(stems):
        ang = 2 * math.pi * si / stems + rng.uniform(0, 1)
        o = Vector((math.cos(ang), math.sin(ang), 0)) * (0.0 if stems == 1 else trunk_r * 0.8)
        top = o + Vector((rng.uniform(-lean, lean), rng.uniform(-lean, lean), 0)) * trunk_h + Vector((0, 0, trunk_h * (1 if stems == 1 else rng.uniform(0.75, 0.95))))
        if stems > 1:
            top += Vector((math.cos(ang), math.sin(ang), 0)) * crown * 0.35
        pts = [o + (top - o) * t + Vector((0, 0, 0)) for t in (0, 0.25, 0.5, 0.75, 1.0)]
        pts[0].z = -0.12
        r0 = trunk_r * (1 if stems == 1 else 0.7)
        limb(a, rng, pts, [r0 * 1.35, r0 * 1.05, r0 * 0.95, r0 * 0.9, r0 * 0.85], 12, dark, mix(dark, lit, 0.4), noise=0.05, mat=bark_mat, moss=0.5)
        n = 4 if stems == 1 else 3
        for i in range(n):
            a2 = 2 * math.pi * i / n + ang + rng.uniform(-0.3, 0.3)
            inc = math.radians(rng.uniform(32, 52))
            d = Vector((math.cos(a2) * math.sin(inc), math.sin(a2) * math.sin(inc), math.cos(inc)))
            g.branch(top - Vector((0, 0, 0.1 * i)), d, r0 * 0.6, crown * rng.uniform(1.0, 1.2), 1)
        g.branch(top, Vector((0.05, 0.0, 1)), r0 * 0.55, crown * 0.95, 1)
    print(f'[yjm] {name}: {g.cards} 枝叶子')
    return a.finish(view=(20, 25, 0.95), dist=1.6)


def pine(name, h, lean, tiers=5):
    """松：斜着长的红褐色树干，几层平伸的枝，枝上的松针一簇簇平铺成「云片」"""
    a = Asset(name)
    rng = a.rng
    dark, lit = (0.36, 0.2, 0.15), (0.6, 0.38, 0.26)
    g = Grower(a, {
        1: dict(segs=6, sides=7, wiggle=0.1, up=-0.01, kids=4, start=0.3, ang=55, lift=0.0, r=0.55, l=0.55),
        2: dict(segs=4, sides=5, wiggle=0.14, up=0.0, kids=5, start=0.2, ang=58, lift=-0.05, r=0.5, l=0.6),
        3: dict(segs=3, sides=4, wiggle=0.16, up=0.03, taper=0.4),
    }, 'leaf_pine', (lean * 0.6, 0, h * 0.7), ((0.12, 0.3, 0.2), (0.2, 0.42, 0.26), (0.36, 0.58, 0.3), (0.46, 0.64, 0.34)), (dark, lit))
    g.bark_mat, g.cluster_level, g.size, g.roll, g.every, g.odd = 'bark_dark', 1, (0.75, 1.0), 0.5, 0.045, (0.08, 0.0)
    g.hi, g.sway = (h * 0.5, h * 0.5), (h * 0.4, h * 0.6)
    bend = rng.uniform(-0.3, 0.3)
    trunk = [Vector((lean * t * t + bend * math.sin(math.pi * t) * 0.6, bend * math.sin(math.pi * t), h * t)) for t in (0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.88, 1.0)]
    trunk[0].z = -0.12
    limb(a, rng, trunk, [0.34, 0.3, 0.27, 0.23, 0.19, 0.15, 0.11, 0.07], 12, dark, lit, noise=0.07, mat='bark_dark', moss=0.4)
    for i in range(tiers):
        k = i / (tiers - 1)
        t = 0.42 + 0.55 * k
        x = int(t * (len(trunk) - 1))
        p = trunk[min(x, len(trunk) - 2)].lerp(trunk[min(x + 1, len(trunk) - 1)], t * (len(trunk) - 1) - x)
        for j in range(2 if i < tiers - 1 else 1):
            a2 = math.pi * j + 2.2 * i + rng.uniform(-0.4, 0.4)
            d = Vector((math.cos(a2), math.sin(a2), rng.uniform(0.0, 0.15) if i < tiers - 1 else 0.8)).normalized()
            g.branch(p, d, 0.12 * (1 - 0.5 * k), h * (0.42 - 0.22 * k) * rng.uniform(0.9, 1.1), 1)
    print(f'[yjm] {name}: {g.cards} 簇松针')
    return a.finish(view=(20, 25, 0.95), dist=1.6)


def bamboo_grove(name, count, spread):
    """竹：一丛竿子，竿上一节一节，上半截每节伸出细枝挂竹叶"""
    a = Asset(name)
    rng = a.rng
    for i in range(count):
        ang = rng.uniform(0, 6.28)
        rr = spread * math.sqrt(rng.random())
        x, y = rr * math.cos(ang), rr * math.sin(ang)
        h = rng.uniform(4.2, 6.4)
        lx, ly = rng.uniform(-0.6, 0.6) + x * 0.6, rng.uniform(-0.6, 0.6) + y * 0.6
        r = rng.uniform(0.045, 0.065)
        n = 11
        pts = [(x + lx * (k / n) ** 2, y + ly * (k / n) ** 2, h * k / n) for k in range(n + 1)]
        rad = [r * (1 - 0.55 * k / n) for k in range(n + 1)]
        green, old = (0.5, 0.66, 0.3), (0.36, 0.5, 0.24)
        a.tube(pts, rad, old, segs=10, color2=green, sway=(0.0, 1.2), mat='toon')
        for k in range(1, n):                       # 竹节：鼓出一圈、颜色发白
            px, py, pz = pts[k]
            a.cyl(rad[k] * 1.18, 0.025, (px, py, pz - 0.012), (0.72, 0.76, 0.56), segs=10)
        for k in range(5, n + 1):
            px, py, pz = pts[k]
            p0 = Vector((px, py, pz))
            for q in range(2):
                a2 = rng.uniform(0, 6.28)
                d = Vector((math.cos(a2), math.sin(a2), rng.uniform(-0.25, 0.25))).normalized()
                tw = rng.uniform(0.25, 0.45)
                a.tube([p0, p0 + d * tw * 0.5 + Vector((0, 0, 0.04)), p0 + d * tw], [0.008, 0.006, 0.004], (0.42, 0.55, 0.26), segs=4,
                       sway=(0.5 + k / n, 0.8 + k / n), mat='toon')
                for c in range(3):
                    dd = (d + Vector((rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(-0.6, 0.1)))).normalized()
                    side = Quaternion(dd, rng.uniform(-1.0, 1.0)) @ _perp(dd)
                    col = vary(rng.choice([(0.4, 0.62, 0.3), (0.5, 0.7, 0.34), (0.32, 0.54, 0.28)]), rng, 0.04, 0.04)
                    n_ = (dd + Vector((0, 0, 0.5))).normalized()
                    a.card(p0 + d * tw * rng.uniform(0.4, 1.0), dd, side, 0.55, 0.55, 'leaf_bamboo', col, n_, bend=0.12, sway=0.6 + 0.8 * k / n)
    return a.finish(view=(20, 25, 0.95), dist=1.0)


ASSETS = {
    'tree_wish': tree_wish,
    # 下面这些顶替 plants.py 里同名的老树（团块做的）
    'tree_maple_a': lambda n: broadleaf(n, 4.8, 1.8, 0.16, 'leaf_maple', ((0.62, 0.12, 0.08), (0.84, 0.24, 0.12), (0.98, 0.5, 0.2), (0.96, 0.68, 0.26)),
                                        ((0.3, 0.22, 0.2), (0.48, 0.38, 0.32)), stems=3, odd=(0.18, 0.0), size=(0.45, 0.6)),
    'tree_maple_b': lambda n: broadleaf(n, 3.7, 1.4, 0.12, 'leaf_maple', ((0.7, 0.2, 0.1), (0.9, 0.36, 0.14), (0.99, 0.6, 0.24), (0.9, 0.76, 0.3)),
                                        ((0.3, 0.22, 0.2), (0.48, 0.38, 0.32)), stems=2, odd=(0.2, 0.0), size=(0.42, 0.55)),
    'tree_ginkgo': lambda n: broadleaf(n, 5.8, 1.75, 0.22, 'leaf_ginkgo', ((0.8, 0.56, 0.12), (0.95, 0.74, 0.2), (1.0, 0.88, 0.38), (0.72, 0.78, 0.3)),
                                       ((0.32, 0.26, 0.2), (0.5, 0.42, 0.34)), lean=0.08, odd=(0.1, 0.0)),
    'tree_round_a': lambda n: broadleaf(n, 5.0, 1.9, 0.22, 'leaf_camphor', (C('leaf_deep'), C('leaf'), C('leaf_lit'), (0.72, 0.84, 0.36)),
                                        ((0.3, 0.24, 0.2), (0.5, 0.42, 0.34)), bark_mat='bark', odd=(0.12, 0.03)),
    'tree_round_b': lambda n: broadleaf(n, 3.8, 1.45, 0.16, 'leaf_camphor', (C('leaf_deep'), C('leaf_dark'), C('leaf'), (0.7, 0.82, 0.36)),
                                        ((0.3, 0.24, 0.2), (0.5, 0.42, 0.34)), bark_mat='bark', odd=(0.1, 0.03)),
    'tree_blossom': lambda n: broadleaf(n, 4.0, 1.55, 0.13, 'leaf_camphor', ((0.24, 0.42, 0.22), (0.38, 0.58, 0.3), (0.55, 0.72, 0.36), (0.66, 0.8, 0.4)),
                                        ((0.28, 0.2, 0.18), (0.46, 0.34, 0.3)), stems=2, blossom=('leaf_blossom', 0.85, (0.99, 0.74, 0.84)), size=(0.42, 0.56),
                                        every=0.11),
    'tree_pine_a': lambda n: pine(n, 5.8, 0.6),
    'tree_pine_b': lambda n: pine(n, 4.6, -0.9, 4),
    'tree_pine_c': lambda n: pine(n, 7.0, 0.25, 6),
    'bamboo_a': lambda n: bamboo_grove(n, 9, 0.75),
    'bamboo_b': lambda n: bamboo_grove(n, 5, 0.5),
    # 灌木：顶替 plants.py 里一团团球的那几种（名字相同）
    'bush_a': lambda n: shrub(n, 7, 0.8),
    'bush_b': lambda n: shrub(n, 9, 1.0),
    'bush_c': lambda n: shrub(n, 6, 0.6),
    'bush_flower_p': lambda n: shrub(n, 7, 0.75, flower=(0.98, 0.56, 0.72)),
    'bush_flower_w': lambda n: shrub(n, 7, 0.75, flower=(0.99, 0.96, 0.94)),
}
