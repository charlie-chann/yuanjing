"""建筑：大殿、牌坊、钟亭、码头、小船。每个模型的原点在它自己的地面中心，-y 是正面（朝南，朝着镜头）。
大殿 2026-11-17 改成能走进去：加深到 12.8 米，里面有金砖地、壁画、旋子彩画的梁枋、井口天花和藻井（hall() 前面的注释有尺寸）。"""
import math
import os
import sys

import bmesh
from mathutils import Vector, Matrix

from kit import Asset, new_bm, paint, xform
from palette import C, tint, mix, vary, hexc


def _diag_bars(boxes, x0, x1, z0, z1, yb, step, color, t=0.014, d=0.02):
    """±45 度的斜方格棂条（菱花），截在 [x0, x1] × [z0, z1] 里：往 boxes 里加（_bulk_boxes 的格式）"""
    w, h = x1 - x0, z1 - z0
    for sg in (-1, 1):
        for k in range(int(math.floor(-h / step)) - 1, int(math.ceil(w / step)) + 2):
            pts = []
            for zz in (z0, z1):
                xx = x0 + k * step + sg * (zz - z0)
                if x0 - 1e-6 <= xx <= x1 + 1e-6:
                    pts.append((xx, zz))
            for xx in (x0, x1):
                zz = z0 + (xx - (x0 + k * step)) * sg
                if z0 - 1e-6 <= zz <= z1 + 1e-6:
                    pts.append((xx, zz))
            pts = sorted(set((round(px, 5), round(pz, 5)) for (px, pz) in pts))
            if len(pts) < 2:
                continue
            (ax, az), (bx, bz) = pts[0], pts[-1]
            L = math.hypot(bx - ax, bz - az)
            if L < 0.02:
                continue
            boxes.append((((ax + bx) / 2, yb, (az + bz) / 2), (L, d, t), 0.0, -math.atan2(bz - az, bx - ax), color))


def _lattice(a, cx, y, z0, w, h, nx=3, nz=5, depth=0.05):
    """一扇格子窗：后面一块会亮的窗纸（暖黄），前面是木框和斜方格的菱花棂条（评审：以前是白纸上的方格，像日式的障子）"""
    a.box((w, 0.03, h), (cx, y + 0.02, z0), color=C('paper_warm'), bevel=0, mat='glow', glow=1.0)
    bar = C('lattice')
    for x in (cx - w / 2, cx + w / 2):
        a.box((0.04, depth, h), (x, y, z0), color=bar, bevel=0)
    for z in (z0, z0 + h):
        a.box((w, depth, 0.04), (cx, y, z - 0.02), color=bar, bevel=0)
    # 中间几根竖的分格（nx 格），格里斜方格
    for i in range(1, nx):
        a.box((0.03, depth, h), (cx - w / 2 + w * i / nx, y, z0), color=bar, bevel=0)
    boxes = []
    _diag_bars(boxes, cx - w / 2, cx + w / 2, z0, z0 + h, y, min(0.1, h / 3.2), bar, t=0.016, d=depth * 0.8)
    _bulk_boxes(a, boxes, 'toon')


def _hang_lantern(a, x, y, z, s=1.0):
    """挂着的红灯笼，z 是挂点。评审第三轮：夜里是一块奶白的十二边形——现在 24 段圆、十道竖的骨（深红、不发光）、
    上下金箍、底下金穗；灯罩发光带上红色（YJToon 的 _GlowTint），亮度压到七成（夜里不被色调映射冲成白的）"""
    a.cyl(0.012 * s, 0.22 * s, (x, y, z - 0.22 * s), C('rope_dark'), segs=5)
    r = C('cloth_red')
    prof = [(0.0, 0.0), (0.07, 0.0), (0.1, 0.03), (0.2, 0.14), (0.23, 0.26), (0.2, 0.38), (0.1, 0.49), (0.07, 0.52), (0.0, 0.52)]
    cols = [C('gold_dark'), C('gold_dark'), r, r, tint(r, 0.06), r, C('gold_dark'), C('gold_dark'), C('gold_dark')]
    # 两头封口（以前上下各一个圆口，从口里能看见灯笼里面的背面）
    a.lathe([(px, pz, cc) for (px, pz), cc in zip(prof, cols)], (x, y, z - 0.74 * s), segs=24, scale=s, mat='glow', glow=0.7, color=r)
    # 竖骨：沿着灯笼的轮廓贴一圈细竹骨（深红），夜里亮的绢面被它们分成一瓣一瓣
    rib = tint(r, -0.35)
    for k in range(10):
        ang = 2 * math.pi * (k + 0.5) / 10
        pts = []
        for (px, pz) in prof[2:7]:
            rr = (px + 0.006) * s
            pts.append((x + math.cos(ang) * rr, y + math.sin(ang) * rr, z - 0.74 * s + pz * s))
        a.tube(pts, 0.006 * s, rib, segs=4)
    # 上下的金箍
    for zz, rr in ((0.035, 0.105), (0.485, 0.105)):
        a.cyl(rr * s, 0.022 * s, (x, y, z - 0.74 * s + zz * s - 0.011 * s), C('gold'), segs=24)
    a.cyl(0.02 * s, 0.2 * s, (x, y, z - 0.94 * s), C('gold'), r2=0.035 * s, segs=6)
    # 金穗：底下一束（几根细线往下垂、略散开）
    for k in range(8):
        ang = 2 * math.pi * k / 8
        a.tube([(x, y, z - 0.94 * s), (x + math.cos(ang) * 0.03 * s, y + math.sin(ang) * 0.03 * s, z - 1.12 * s)], 0.0045 * s, C('gold_dark'), segs=3)


def _rail(a, p0, p1, z, post_every=1.5, ends=True):
    """一段石栏杆：望柱、上下横杆、中间栏板。ends=False：两头的望柱不放（转角上别的那段已经放了，两根叠在一起会闪）"""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    n = max(1, int(round(L / post_every)))
    ang = math.atan2(dy, dx)
    st, sl = C('stone'), C('stone_lit')
    for i in range(n + 1):
        if not ends and i in (0, n):
            continue
        k = i / n
        x, y = p0[0] + dx * k, p0[1] + dy * k
        a.box((0.17, 0.17, 0.78), (x, y, z), color=st, bevel=0.025, top=sl)
        a.lathe([(0.06, 0), (0.1, 0.03), (0.105, 0.09), (0.05, 0.15), (0.0, 0.17)], (x, y, z + 0.78), segs=8, color=sl)
    cx, cy = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    # 横杆、栏板两头只伸进望柱一半（以前伸到柱中心，转角上两段在柱子里交叉叠着）
    Lr = L - 0.1
    a.box((Lr, 0.1, 0.09), (cx, cy, z + 0.56), rot=(0, 0, ang), color=sl, bevel=0.02)
    a.box((Lr, 0.06, 0.34), (cx, cy, z + 0.14), rot=(0, 0, ang), color=st, bevel=0.015)
    a.box((Lr, 0.12, 0.1), (cx, cy, z), rot=(0, 0, ang), color=C('stone_dark'), bevel=0.02)


# ═══════════════════ 大殿（2026-11-17：加深、能走进去，里面有金砖地、壁画、彩画梁枋、天花和藻井）═══════════════════
# Blender 本地坐标：x 向右、y 往里（北）、z 向上，原点在台基地面中心；Unity 里放在 HallAt = (0, 0, 17.3)，世界 z = 17.3 + y。
# 室内的东西（地面、护墙、壁画、梁、天花、藻井、金柱）部件名都以 in_ 开头（材质还是 toon、slab、paint_beam……），
# Unity 那边可以只给室内换一套环境光更暗的材质。
H_PW, H_PD, H_PH = 17.2, 12.8, 0.7          # 台基宽、深、高（前沿还在世界 z 10.9，后沿 23.7）
H_XS = [-6.6, -3.96, -1.32, 1.32, 3.96, 6.6]  # 面阔五间
H_FY, H_WY, H_BY = -4.8, -3.0, 4.8          # 前廊柱、门墙（中线）、后墙（中线）
H_BC = 4.92                                 # 后檐柱（嵌在后墙里，室内看不见）
H_SY = [-3.0, -0.36, 2.28, H_BC]            # 两山墙上的柱子
H_CH = 3.8                                  # 檐柱高（柱顶 4.5）
H_FLOOR = 0.72                              # 室内金砖地面的顶
H_IN = (6.47, -2.88, 4.68)                  # 墙体内皮：|x| ≤ 6.47，-2.88 ≤ y ≤ 4.68
H_LX, H_LY0, H_LY1 = 6.45, -2.86, 4.66      # 室内护墙面（墙上看到的那一层）
H_CEIL = 5.9                                # 天花支条的底（室内净高 5.18）
H_PANEL = 5.96                              # 天花板面
H_JUN = 5.47                                # 峻脚（四周的斜板）从墙上这个高度起
H_JUN_B = 5.80                              # 后墙上的峻脚从这里起（背光顶到 5.67，后墙这一边抬高）
H_JUN_RAMP = 0.7                            # 两山的峻脚外沿在靠后墙这么长里升到 H_JUN_B
H_FLAT = (5.94, -2.55, 3.95)                # 平顶天花：|x| ≤ 5.94，-2.55 ≤ y ≤ 3.95
H_ZJ = (1.32, -1.9, 0.7)                    # 藻井方口：|x| ≤ 1.32，-1.9 ≤ y ≤ 0.7（中心 (0, -0.6)，世界 z 16.7）
H_ZJ_TOP = 7.0
H_JIN = [(-2.8, -1.9), (2.8, -1.9), (-2.8, 0.7), (2.8, 0.7)]   # 四根金柱（世界 z 15.4、18.0）
H_JIN_R = 0.22
H_BEAM0 = 5.35                              # 天花梁底
H_ROOF_YC = 0.06                            # 屋顶中心（前廊柱和后檐柱的正中）
H_DOOR_SILL = 0.77                          # 三间门的门槛顶（比室内地面高 5 厘米）
H_LEAF_OPEN = 84.0                          # 门扇往里开的角度

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'textures'))
import painted as _painted  # noqa: E402  （只用它的贴图分块表 RECTS）

# 彩画、木作用到的几种颜色（顶点色）
_GRN, _GRN_L, _GRN_D = hexc('#2f8269'), hexc('#5fae8d'), hexc('#1d5a48')
_BLU, _BLU_L, _BLU_D = hexc('#2b5d92'), hexc('#5d8cc0'), hexc('#1b3e69')
_INK = hexc('#2a2326')
_WALL_RED = hexc('#9c3d2c')
_JINZHUAN = [hexc('#5f5d58'), hexc('#67645e'), hexc('#58595a'), hexc('#625f5a')]
_GROUT = hexc('#3e3b38')
_PAPER = hexc('#efe6cf')


def _pv(atlas, key, s, t):
    """手绘贴图里某一块上的点 (s, t)（0..1，t 朝上）→ 整张图的贴图坐标。四边各留 2.5 像素，免得缩小时串色"""
    W, H = _painted.SIZES[atlas]
    x0, y0, x1, y1 = _painted.RECTS[atlas][key]
    x0, x1, y0, y1 = x0 + 2.5, x1 - 2.5, y0 + 2.5, y1 - 2.5
    return ((x0 + (x1 - x0) * s) / W, 1.0 - (y1 - (y1 - y0) * t) / H)


def _aspect(atlas, key):
    x0, y0, x1, y1 = _painted.RECTS[atlas][key]
    return (x1 - x0) / (y1 - y0)


def _pq(F, atlas, key, p, A, U, L, h, s0=0.0, s1=1.0, t0=0.0, t1=1.0, part=None):
    """一块手绘贴图的长方形：从 p 起沿 A 长 L、沿 U 高 h。A×U 是它朝外的方向"""
    p, A, U = Vector(p), Vector(A), Vector(U)
    q = [p, p + A * L, p + A * L + U * h, p + U * h]
    uv = [_pv(atlas, key, s0, t0), _pv(atlas, key, s1, t0), _pv(atlas, key, s1, t1), _pv(atlas, key, s0, t1)]
    F.setdefault(part or atlas, []).append((q, uv))


def _xz_run(F, atlas, key, p, A, U, L, h, part=None):
    """旋子彩画一段（一间）：两头的箍头、找头按原比例，中间的方心拉长缩短都行"""
    e = min(0.25 * _aspect(atlas, key) * h, 0.3 * L)
    A = Vector(A)
    _pq(F, atlas, key, p, A, U, e, h, 0.0, 0.25, part=part)
    _pq(F, atlas, key, Vector(p) + A * e, A, U, L - 2 * e, h, 0.25, 0.75, part=part)
    _pq(F, atlas, key, Vector(p) + A * (L - e), A, U, e, h, 0.75, 1.0, part=part)


def _band_run(F, atlas, key, p, A, U, L, h, part=None):
    """一条连续的花边（连珠、卷草、流云）：按原比例一段段接下去"""
    n = max(1, int(round(L / (_aspect(atlas, key) * h))))
    A = Vector(A)
    for i in range(n):
        _pq(F, atlas, key, Vector(p) + A * (L * i / n), A, U, L / n, h, 0.0, 1.0, part=part)


def _bulk_boxes(a, boxes, mat='toon'):
    """很多不倒角的小方块一次放进去（格子窗的棂条、天花的支条）。boxes: [(中心, (长, 宽, 高), 绕 z 角, 绕 y 角, 颜色)]"""
    t = new_bm()
    col = t.loops.layers.float_color['col']
    FACES = ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))
    for (c, (sx, sy, sz), rz, ry, color) in boxes:
        R = (Matrix.Rotation(rz, 3, 'Z') @ Matrix.Rotation(ry, 3, 'Y'))
        cv = Vector(c)
        vs = [t.verts.new(cv + R @ Vector((i * sx / 2, j * sy / 2, k * sz / 2))) for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)]
        for fi in FACES:
            f = t.faces.new([vs[q] for q in fi])
            for l in f.loops:
                l[col] = (color[0], color[1], color[2], 0.0)
    bmesh.ops.recalc_face_normals(t, faces=t.faces)
    a.merge(t, mat)


def _bulk_polys(a, polys, mat='toon'):
    """很多小平面（一个面一个颜色）一次放进去"""
    t = new_bm()
    col = t.loops.layers.float_color['col']
    for (pts, color) in polys:
        f = t.faces.new([t.verts.new(p) for p in pts])
        for l in f.loops:
            l[col] = (color[0], color[1], color[2], 0.0)
    a.merge(t, mat)


def _roof_h(W, D, H, z, lift, x, y, yc=0.0, curve=2.2):
    """kit.roof 的屋面高度（同一个公式），用来算屋檐下面还有多少空"""
    y = y - yc
    dmax = min(W, D)
    d = min(W - abs(x), D - abs(y))
    t = max(0.0, d) / dmax
    c = (abs(x) / W * abs(y) / D) ** 3
    return z + H * (0.45 * t + 0.55 * t ** curve) + lift * c * (1 - t) ** 2


# ── 斗拱 ──
def _dou(s, cx, cy, z, hb, ht, h, col, mat='toon'):
    """斗、升：方的，上半截直、下半截往下收（斗欹）。hb、ht 是底和顶的半边长"""
    k = math.sqrt(2)
    s.lathe([(0, 0), (hb * k, 0), (ht * k, h * 0.5), (ht * k, h), (0, h)], (cx, cy, z), segs=4, color=col, rot=(0, 0, math.pi / 4), mat=mat)


def _gong_poly(L, h, cut=None, k=3):
    """栱的侧面：上边平，两头下角卷杀（一段圆弧，k 折）"""
    half = L / 2
    cut = cut if cut is not None else min(0.1, L * 0.17)
    pts = [(-half + cut, 0.0), (half - cut, 0.0)]
    for i in range(1, k + 1):
        a_ = -math.pi / 2 + math.pi / 2 * i / k
        pts.append((half - cut + cut * math.cos(a_), 0.45 * h + 0.45 * h * math.sin(a_)))
    pts += [(half, h), (-half, h)]
    for i in range(0, k):
        a_ = math.pi + math.pi / 2 * i / k
        pts.append((-half + cut + cut * math.cos(a_), 0.45 * h + 0.45 * h * math.sin(a_)))
    return pts


def _vp(s, poly, t, axis, off, z, color, mat='toon', along=0.0):
    """竖着的一块板（栱、昂）：poly 是 (沿长, 高) 的侧面形，t 是厚。axis='u' 顺着墙，'v' 往外挑"""
    poly = [(p[0] + along, p[1] + z) for p in poly]
    if axis == 'u':
        s.prism(poly, -t / 2, t / 2, color, bevel=0.0, mat=mat, loc=(0, off, 0), rot=(math.pi / 2, 0, 0))
    else:
        s.prism(poly, -t / 2, t / 2, color, bevel=0.0, mat=mat, loc=(off, 0, 0), rot=(math.pi / 2, 0, math.pi / 2))


def _dougong(a, x, y, z, ang, s=1.0, ca=None, cb=None, mat='toon', inner=0.3, gold=True, lite=False, wan=0.86):
    """一攒斗拱（清式单翘单昂，简化）。(x, y, z) 是坐斗底面中心，ang 是往外挑的方向（弧度，0 = +x）。
    s=1 时约 0.58 米高、往外挑 0.78 米；inner 是往里挑多长（室内那半截）。
    wan 是万栱的长（本地尺寸）：一行里相邻两攒的万栱不能叠在一起（叠着的两个面一青一绿，镜头一动就闪），_dougong_row 按间距算"""
    sub = Asset('_dg')
    ca = ca or _BLU
    cb = cb or _GRN
    t = 0.09
    _dou(sub, 0, 0, 0, 0.10, 0.15, 0.14, cb, mat)
    _vp(sub, _gong_poly(0.62, 0.12), t, 'u', 0.0, 0.10, ca, mat)                              # 正心瓜栱
    _vp(sub, _gong_poly(0.36 + inner, 0.125), t, 'v', 0.0, 0.10, ca, mat, along=(0.36 - inner) / 2)  # 翘（比瓜栱高半厘米：交叉处顶面不重叠）
    for u in (-0.26, 0.26):
        _dou(sub, u, 0, 0.22, 0.05, 0.065, 0.08, cb, mat)
    for v in ((0.30,) if lite else (0.30, -inner + 0.06)):
        _dou(sub, 0, v, 0.22, 0.05, 0.065, 0.08, cb, mat)
    for v in ((0.30,) if lite else (0.30, 0.0)):
        _vp(sub, _gong_poly(wan, 0.12, k=2 if lite else 3), t, 'u', v, 0.30, ca if v else cb, mat)                # 万栱
        if not lite:
            for u in (-(wan / 2 - 0.05), wan / 2 - 0.05):
                _dou(sub, u, v, 0.42, 0.045, 0.06, 0.07, cb, mat)
    # 昂：往外挑出、头往下斜成尖嘴
    _vp(sub, [(-inner, 0.0), (0.5, 0.0), (0.74, -0.12), (0.79, -0.1), (0.62, 0.12), (-inner, 0.16)], t, 'v', 0.0, 0.302, ca, mat)
    # 耍头
    _vp(sub, [(-inner, 0.0), (0.6, 0.0), (0.66, 0.05), (0.62, 0.12), (-inner, 0.12)], t, 'v', 0.0, 0.464, cb, mat)   # 昂尾顶在 0.462
    if gold:
        # 昂嘴上一点金、坐斗正面一道金边
        sub.box((0.05, 0.03, 0.04), (0, 0.77, 0.18), color=C('gold'), bevel=0.008, mat=mat, base=False)
    a.place(sub, (x, y, z), (0, 0, ang - math.pi / 2), s)


def _dougong_row(a, p0, p1, z, ang, step, s, mat='toon', inner=0.3, skip=(), ends=True, lite=False):
    """沿一条线排一行斗拱（青绿相间），返回放了的位置"""
    L = (Vector(p1) - Vector(p0)).length
    n = max(1, int(round(L / step)))
    wan = min(0.86, (L / n - 0.02) / s)      # 相邻两攒的万栱之间至少空 2 厘米
    out = []
    for i in range(0 if ends else 1, n + 1 if ends else n):
        k = i / n
        x, y = p0[0] + (p1[0] - p0[0]) * k, p0[1] + (p1[1] - p0[1]) * k
        if any(abs(x - sx) < sr and abs(y - sy) < sr for (sx, sy, sr) in skip):
            continue
        ca, cb = (_BLU, _GRN) if i % 2 == 0 else (_GRN, _BLU)
        _dougong(a, x, y, z, ang, s, ca, cb, mat, inner, lite=lite, wan=wan)
        out.append((x, y))
    return out


def _gold_vp(s, poly, t, axis, off, z, color, mat='toon', along=0.0, bev=0.007, edge=None):
    """竖着的一块板（栱、昂、耍头），两面的边沿倒一道角、倒角涂金（清式「金线」斗拱的金边）。参数同 _vp"""
    poly = [(p[0] + along, p[1] + z) for p in poly]
    t_ = new_bm()
    lo = [t_.verts.new((p[0], p[1], -t / 2)) for p in poly]
    hi = [t_.verts.new((p[0], p[1], t / 2)) for p in poly]
    n = len(poly)
    t_.faces.new(hi)
    t_.faces.new(list(reversed(lo)))
    for i in range(n):
        j = (i + 1) % n
        t_.faces.new((lo[i], lo[j], hi[j], hi[i]))
    bmesh.ops.recalc_face_normals(t_, faces=t_.faces)
    eds = [e for e in t_.edges if (e.verts[0].co.z > 0) == (e.verts[1].co.z > 0)]
    bev_f = bmesh.ops.bevel(t_, geom=eds, offset=bev, offset_type='OFFSET', segments=1, profile=0.5, affect='EDGES', clamp_overlap=True)['faces']
    paint(t_, None, color)
    paint(t_, [f for f in bev_f if f.is_valid], edge or C('gold'))
    if axis == 'u':
        s.merge(t_, mat, xform((0, off, 0), (math.pi / 2, 0, 0)))
    else:
        s.merge(t_, mat, xform((off, 0, 0), (math.pi / 2, 0, math.pi / 2)))


def _gold_box(a, size, loc, rz, color, mat='toon', bev=0.008):
    """长方木（枋），四条长棱倒角涂金。loc 是底面中心"""
    t_ = new_bm()
    bmesh.ops.create_cube(t_, size=1.0)
    for v in t_.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2] + size[2] / 2))
    eds = [e for e in t_.edges if abs(e.verts[0].co.x - e.verts[1].co.x) > 1e-6]
    bev_f = bmesh.ops.bevel(t_, geom=eds, offset=bev, offset_type='OFFSET', segments=1, profile=0.5, affect='EDGES', clamp_overlap=True)['faces']
    paint(t_, None, color)
    paint(t_, [f for f in bev_f if f.is_valid], C('gold'))
    a.merge(t_, mat, xform(loc, (0, 0, rz)))


def _dou_g(s, cx, cy, z, hb, ht, h, col, mat='toon'):
    """斗、升，斗口一圈金边"""
    k = math.sqrt(2)
    s.lathe([(0, 0), (hb * k, 0), (ht * k, h * 0.5), (ht * k, h * 0.8, C('gold')), (ht * k, h), (0, h)], (cx, cy, z), segs=4, color=col,
            rot=(0, 0, math.pi / 4), mat=mat)


def _dg_set(a, x, y, z, ang, ca, cb, mat='toon', s=1.0, fat=1.0, tail=0.12, lite=False):
    """室内一攒斗拱（单翘单昂、金线）：坐斗 → 正心瓜栱 + 翘 → 正心万栱、外拽瓜栱 + 昂 → 耍头，栱的两头都有升。
    正心枋、拽枋是一整行连着的（_interior 里放），这里不放。s=1 时高 0.68、往屋里挑 0.75；fat 把构件加厚（藻井里的小斗拱用）；
    lite 省掉外拽瓜栱和万栱上的升（藻井里的，离得远、数量多）"""
    sub = Asset('_dgi')
    t = 0.09 * fat
    _dou_g(sub, 0, 0, 0, 0.11, 0.16, 0.15, cb, mat)
    kk = 2 if lite else 3
    _gold_vp(sub, _gong_poly(0.62, 0.12, k=kk), t, 'u', 0.0, 0.11, ca, mat)                                   # 正心瓜栱
    _gold_vp(sub, _gong_poly(0.36 + tail, 0.125, k=kk), t, 'v', 0.0, 0.113, ca, mat, along=(0.36 - tail) / 2)   # 翘（底比瓜栱高 3 毫米）
    for u in (-0.26, 0.26):
        _dou_g(sub, u, 0, 0.23, 0.05, 0.066, 0.08, cb, mat)
    _dou_g(sub, 0, 0.30, 0.235, 0.05, 0.066, 0.08, cb, mat)
    _gold_vp(sub, _gong_poly(0.92, 0.12, k=kk), t, 'u', 0.0, 0.31, cb, mat)                                    # 正心万栱
    if not lite:
        _gold_vp(sub, _gong_poly(0.62, 0.12), t, 'u', 0.30, 0.315, cb, mat)                                  # 外拽瓜栱
        for u in (-0.41, 0.41):
            _dou_g(sub, u, 0, 0.43, 0.045, 0.06, 0.07, ca, mat)
        for u in (-0.26, 0.26):
            _dou_g(sub, u, 0.30, 0.435, 0.045, 0.06, 0.07, ca, mat)
    # 昂：往屋里挑出、头往下斜成尖嘴；耍头：昂上面一层，头上一个蚂蚱头
    _gold_vp(sub, [(-tail, 0.0), (0.5, 0.0), (0.72, -0.12), (0.77, -0.1), (0.62, 0.11), (-tail, 0.15)], t, 'v', 0.0, 0.312, ca, mat)
    _gold_vp(sub, [(-tail, 0.0), (0.6, 0.0), (0.68, 0.05), (0.63, 0.12), (-tail, 0.12)], t, 'v', 0.0, 0.565, cb, mat)
    if not lite:
        sub.box((0.05, 0.03, 0.04), (0, 0.755, 0.2), color=C('gold'), bevel=0.008, mat=mat, base=False)
    a.place(sub, (x, y, z), (0, 0, ang - math.pi / 2), s)


def _dg_line(a, p0, p1, z, ang, step, s, mat='toon', fat=1.5):
    """藻井里一行小斗拱（金线、构件加厚，从下面五六米外看还认得出是斗拱，不是一堆十字棍）"""
    L = (Vector(p1) - Vector(p0)).length
    n = max(1, int(round(L / step)))
    for i in range(n + 1):
        k = i / n
        ca, cb = (_BLU, _GRN) if i % 2 == 0 else (_GRN, _BLU)
        _dg_set(a, p0[0] + (p1[0] - p0[0]) * k, p0[1] + (p1[1] - p0[1]) * k, z, ang, ca, cb, mat, s, fat=fat, tail=0.05, lite=True)


def _dg_corner(a, x, y, z, d1, d2, ca, cb, mat='toon', s=1.0):
    """墙角上的一攒（角科，简化）：坐斗、沿两面墙各一道正心瓜栱、斜着挑出去的角昂和耍头。d1、d2 是两面墙往屋里的方向"""
    sub = Asset('_dgc')
    t = 0.09
    _dou_g(sub, 0, 0, 0, 0.12, 0.17, 0.15, cb, mat)
    a1, a2 = math.atan2(d1[1], d1[0]), math.atan2(d2[1], d2[0])
    for (aa, col, zz) in ((a1, ca, 0.11), (a2, cb, 0.115)):
        g = Asset('_dgc_g')
        _gold_vp(g, _gong_poly(0.62, 0.12), t, 'v', 0.0, zz, col, mat, along=0.0)
        _dou_g(g, 0, 0.26, zz + 0.12, 0.05, 0.066, 0.08, cb, mat)
        sub.place(g, (0, 0, 0), (0, 0, aa - math.pi / 2))
    diag = math.atan2(d1[1] + d2[1], d1[0] + d2[0])
    g = Asset('_dgc_d')
    _gold_vp(g, [(-0.1, 0.0), (0.72, 0.0), (0.98, -0.13), (1.03, -0.1), (0.84, 0.13), (-0.1, 0.17)], t * 1.1, 'v', 0.0, 0.24, ca, mat)
    _gold_vp(g, [(-0.1, 0.0), (0.8, 0.0), (0.9, 0.06), (0.84, 0.13), (-0.1, 0.13)], t * 1.1, 'v', 0.0, 0.43, cb, mat)
    _dou_g(g, 0, 0.62, 0.41, 0.05, 0.07, 0.07, cb, mat)
    g.box((0.05, 0.03, 0.04), (0, 1.0, 0.13), color=C('gold'), bevel=0.008, mat=mat, base=False)
    sub.place(g, (0, 0, 0), (0, 0, diag - math.pi / 2))
    a.place(sub, (x, y, z), (0, 0, 0), s)


def _tuomu(a, F, x, y, z, sx, mat, PB):
    """天花梁头下面的托木：侧面是一朵卷云的轮廓（上沿平、梢头卷一个云头，下沿两道弧收回墙里），
    两侧贴彩画（绿地金卷草），梢头一块青地旋花。x 是墙面，sx 是往屋里的方向（+1/-1），z 是梁底"""
    L, H, T = 0.62, 0.5, 0.3
    prof = [(0.0, 0.0), (L - 0.06, 0.0)]
    # 云头：梢头一个大卷（往下卷）、下面一个小卷
    for i in range(1, 9):
        a_ = math.pi / 2 - math.pi * 1.1 * i / 8
        prof.append((L - 0.06 + 0.08 * math.cos(a_), -0.08 + 0.08 * math.sin(a_)))
    prof += [(L - 0.12, -0.2), (L - 0.06, -0.24)]
    for i in range(1, 7):
        a_ = math.pi / 2 - math.pi * 1.2 * i / 6
        prof.append((L - 0.11 + 0.055 * math.cos(a_), -0.29 + 0.055 * math.sin(a_)))
    # 下沿：一道往里凹的弧回到墙上
    for i in range(1, 9):
        u = i / 8
        prof.append(((L - 0.17) * (1 - u), -0.33 - (H - 0.33) * u ** 1.6 + 0.04 * math.sin(math.pi * u)))
    prof.append((0.0, -H))
    # prism 要逆时针：现在是顺时针（上沿往梢头、再往下、再回来）
    prof = list(reversed(prof))
    sub = Asset('_tm')
    us = [p[0] for p in prof]
    vs = [p[1] for p in prof]
    u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
    # 木头：轮廓拉厚 T，两面的边倒一道金边；两个大侧面换成彩画面（同一圈点，不留缝）
    t_ = new_bm()
    lo = [t_.verts.new((p[0], -T / 2, p[1])) for p in prof]
    hi = [t_.verts.new((p[0], T / 2, p[1])) for p in prof]
    n = len(prof)
    t_.faces.new(list(reversed(hi)))
    t_.faces.new(lo)
    for i in range(n):
        j = (i + 1) % n
        t_.faces.new((lo[i], hi[i], hi[j], lo[j]))
    bmesh.ops.recalc_face_normals(t_, faces=t_.faces)
    eds = [e for e in t_.edges if (e.verts[0].co.y > 0) == (e.verts[1].co.y > 0)]
    bev_f = bmesh.ops.bevel(t_, geom=eds, offset=0.008, offset_type='OFFSET', segments=1, profile=0.5, affect='EDGES', clamp_overlap=True)['faces']
    paint(t_, None, _GRN_D)
    paint(t_, [f for f in bev_f if f.is_valid], C('gold'))
    caps = [f for f in t_.faces if abs(f.normal.y) > 0.99 and len(f.verts) > 4]
    for f in caps:
        loop = [v.co.copy() for v in f.verts]
        uv = [_pv('beam', 'tuomu_side', (v.x - u0) / (u1 - u0), (v.z - v0) / (v1 - v0)) for v in loop]
        sub.uvfaces([([tuple(v) for v in loop], uv)], PB)
    bmesh.ops.delete(t_, geom=caps, context='FACES_ONLY')
    sub.merge(t_, mat)
    # 梢头：一块旋花小板
    sub.box((0.012, 0.2, 0.16), (L + 0.025, 0, -0.16), color=_BLU_D, bevel=0.003, mat=mat, base=False)
    M = xform((x, y, z), (0, 0, 0 if sx > 0 else math.pi))
    for part, b in list(sub.parts.items()):
        a.merge(b, part, M)
    sub.parts = {}
    pe = Vector((L + 0.0315, 0, -0.16))
    q = [pe + Vector((0, -0.09, -0.07)), pe + Vector((0, 0.09, -0.07)), pe + Vector((0, 0.09, 0.07)), pe + Vector((0, -0.09, 0.07))]
    uv = [_pv('beam', 'tuomu', 0, 0), _pv('beam', 'tuomu', 1, 0), _pv('beam', 'tuomu', 1, 1), _pv('beam', 'tuomu', 0, 1)]
    q = [M @ v for v in q]
    F.setdefault(PB, []).append(([tuple(v) for v in q], uv))


# ── 柱子 ──
def _petals(a, n, r, z, length, width, thick, tilt, color, mat, rng):
    """一圈覆莲瓣（柱础上的，比 props_hd.petal_ring 省面：每瓣一个压扁的团、一道脊）"""
    for i in range(n):
        ang = 2 * math.pi * i / n
        c = vary(color, rng, 0.03, 0.02)
        pitch = -math.radians(90 - tilt)
        a.blob(1.0, (r * math.cos(ang), r * math.sin(ang), z), (width, length, thick), c, subdiv=1, bump=0.0, mat=mat, rot=(pitch, 0, ang - math.pi / 2))
        a.blob(1.0, ((r + length * 0.2) * math.cos(ang), (r + length * 0.2) * math.sin(ang), z - 0.2 * length * math.cos(pitch)),
               (width * 0.18, length * 0.75, thick * 1.25), tint(c, 0.04), subdiv=0, bump=0.0, mat=mat, rot=(pitch, 0, ang - math.pi / 2))


def _column(a, x, y, z0, z1, r, rng, mat_pre='', base_half=0.31, band_z=None, petals=True):
    """一根朱漆柱：方石墩、覆盆（一圈覆莲瓣）、微收分的柱身、两道金箍、柱头下一圈青底金色缠枝"""
    st, sl, sd = C('stone'), C('stone_lit'), C('stone_dark')
    if mat_pre:
        # 殿里的柱础：青灰带一点绿的石头（评审：以前是雪白的一块，镜头边上露出一角像一片碎瓷）
        sl, st = mix(C('stone_lit'), hexc('#7f8f86'), 0.5), mix(C('stone'), hexc('#6f7d76'), 0.45)
    k = base_half / 0.31
    S = (mat_pre + 'stone') if not mat_pre else 'stone:' + mat_pre + 'stone'
    T = 'toon' if not mat_pre else 'toon:' + mat_pre + 'toon'
    L = 'lacquer' if not mat_pre else 'lacquer:' + mat_pre + 'lacquer'
    a.box((0.62 * k, 0.62 * k, 0.058), (x, y, z0 + 0.002), color=sd, bevel=0.015, top=st, mat=S)
    # 覆盆：剖面一路往里收（墙里的柱子柱础小，r + 0.025 会比上一圈还大，整圈就翻成朝里了），顶上收进柱身里封口
    a.lathe([(0.3 * k, z0 + 0.06), (0.31 * k, z0 + 0.08), (0.28 * k, z0 + 0.13), (min(r + 0.025, 0.28 * k - 0.01), z0 + 0.16), (r * 0.9, z0 + 0.16)],
            (x, y, 0), segs=32, color=sl, mat=S, outward=True)
    if petals:
        sub = Asset('_pb')
        # 覆莲瓣：殿里的十六瓣、厚一点（雕出来的宝装莲瓣，从镜头那么远也看得出一瓣一瓣）
        _petals(sub, 16 if mat_pre else 12, 0.24 * k, z0 + 0.1, 0.075 * k, (0.075 if mat_pre else 0.06) * k, 0.03 if mat_pre else 0.022, 25, sl, S, rng)
        a.place(sub, (x, y, 0))
    red = C('red')
    # 柱身：微收分；每 0.4 米一圈（面小一些，烘的暗部才连续，不会一截亮一截暗）
    n = max(4, int(round((z1 - z0 - 0.155) / 0.4)))
    prof = []
    for i in range(n + 1):
        t = i / n
        prof.append((r * (1.0 - 0.07 * t ** 1.5), z0 + 0.155 + (z1 - z0 - 0.155) * t))
    a.lathe(prof, (x, y, 0), segs=32, color=red, mat=L, outward=True)
    def shaft_r(zz):
        t_ = max(0.0, min(1.0, (zz - z0 - 0.155) / (z1 - z0 - 0.155)))
        return r * (1.0 - 0.07 * t_ ** 1.5)
    for zz in (z0 + 0.34, (band_z or z1 - 0.62)):
        rr = min(shaft_r(zz), shaft_r(zz + 0.08)) - 0.003       # 金箍的里圈要在柱身里面（柱子往上收，不然下沿有一道缝）
        a.lathe([(rr, 0), (rr + 0.012, 0.008, C('gold_dark')), (rr + 0.016, 0.016, C('gold')), (rr + 0.012, 0.026, C('gold_dark')), (rr, 0.03),
                 (rr, 0.05, C('gold_dark')), (rr + 0.012, 0.054, C('gold_dark')), (rr + 0.016, 0.062, C('gold')), (rr + 0.012, 0.072, C('gold_dark')), (rr, 0.08)],
                (x, y, zz), segs=24, color=C('gold'), mat=T, outward=True)
    # 柱头下一圈青底金色缠枝：一条贴图带（以前是 12 朵金团 + 24 根卷须的模型，一根柱子一千多个三角形）
    zb = (band_z or z1 - 0.62) + 0.12
    rb = shaft_r(zb) + 0.003
    nseg, hb_ = 32, 0.3
    faces = []
    for kk in range(nseg):
        a0, a1 = 2 * math.pi * kk / nseg, 2 * math.pi * (kk + 1) / nseg
        u0, u1 = (kk % 16) / 16, (kk % 16 + 1) / 16            # 一圈两遍
        p0_ = (x + rb * math.cos(a0), y + rb * math.sin(a0))
        p1_ = (x + rb * math.cos(a1), y + rb * math.sin(a1))
        faces.append(([(p0_[0], p0_[1], zb), (p1_[0], p1_[1], zb), (p1_[0], p1_[1], zb + hb_), (p0_[0], p0_[1], zb + hb_)],
                      [_pv('beam', 'colband', u0, 0), _pv('beam', 'colband', u1, 0), _pv('beam', 'colband', u1, 1), _pv('beam', 'colband', u0, 1)]))
    a.uvfaces(faces, 'paint_beam' if not mat_pre else 'paint_beam:' + mat_pre + 'paint_beam', weld=True)
    # 带子下沿一圈窄边（朝下）把带子和柱身之间 3 毫米的缝封上
    ri = shaft_r(zb) - 0.004
    lip = []
    for kk in range(nseg):
        a0, a1 = 2 * math.pi * kk / nseg, 2 * math.pi * (kk + 1) / nseg
        lip.append(([(x + rb * math.cos(a1), y + rb * math.sin(a1), zb), (x + rb * math.cos(a0), y + rb * math.sin(a0), zb),
                     (x + ri * math.cos(a0), y + ri * math.sin(a0), zb), (x + ri * math.cos(a1), y + ri * math.sin(a1), zb)], C('gold_dark')))
    _bulk_polys(a, lip, T)


# ── 格扇、槛窗 ──
def _seg_in_rect(p, d, w, h):
    """过 p、方向 d 的直线在 [0,w]×[0,h] 里的那一段（参数 t0..t1），没有就返回 None"""
    t0, t1 = -1e9, 1e9
    for (pc, dc, lo, hi) in ((p[0], d[0], 0.0, w), (p[1], d[1], 0.0, h)):
        if abs(dc) < 1e-9:
            if pc < lo or pc > hi:
                return None
            continue
        a_, b_ = (lo - pc) / dc, (hi - pc) / dc
        t0, t1 = max(t0, min(a_, b_)), min(t1, max(a_, b_))
    return (t0, t1) if t1 > t0 + 1e-4 else None


def _gexin(s, x0, z0, w, h, glow=False, pitch=0.085, both=True):
    """双交四椀的格心：中间一层窗纸，两面各一层斜交的棂条，交点上一朵小四瓣花"""
    if glow:
        s.box((w, 0.006, h), (x0 + w / 2, 0, z0), color=C('paper'), bevel=0, mat='glow', glow=1.0)
    else:
        s.box((w, 0.006, h), (x0 + w / 2, 0, z0), color=_PAPER, bevel=0, mat='toon')
    bar, dep = 0.014, 0.02
    boxes, studs = [], []
    lat = C('lattice')
    stud = tint(lat, 0.12)
    sq = math.sqrt(2)
    faces = (-1, 1) if both else (-1,)
    for f in faces:
        for sg in (1, -1):
            # 两个方向的棂条交叉处正面在同一平面上会抢着显示：反方向那一组往外挪 1.5 毫米，看着像压在上面
            yb = f * (0.003 + dep / 2 + (0.0015 if sg < 0 else 0.0))
            d = (1 / sq, sg / sq)
            # 直线 x - sg*z = c（沿 d），c 按 pitch*√2 排开
            cs = []
            c = -h - w
            while c < w + h:
                cs.append(c)
                c += pitch * sq
            for c in cs:
                p = (c, 0.0) if sg > 0 else (c, 0.0)
                seg = _seg_in_rect((c, 0.0), d, w, h)
                if seg is None:
                    continue
                ta, tb = seg
                pa = (c + d[0] * ta, d[1] * ta)
                pb = (c + d[0] * tb, d[1] * tb)
                L = tb - ta
                if L < 0.02:
                    continue
                mx, mz = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
                boxes.append(((x0 + mx, yb, z0 + mz), (L, dep, bar), 0.0, -math.atan2(d[1], d[0]), lat))
        # 交点上的小花（菱形小片）
        ys = f * (0.003 + dep + 0.0045)
        ci = -h - w
        cs = []
        while ci < w + h:
            cs.append(ci)
            ci += pitch * sq
        for c1 in cs:          # x - z = c1
            for c2 in cs:      # x + z = c2
                x, z = (c1 + c2) / 2, (c2 - c1) / 2
                if 0.012 < x < w - 0.012 and 0.012 < z < h - 0.012:
                    r = 0.011
                    pts = [(x0 + x - r, ys, z0 + z), (x0 + x, ys, z0 + z - r), (x0 + x + r, ys, z0 + z), (x0 + x, ys, z0 + z + r)]
                    if f > 0:
                        pts = list(reversed(pts))
                    studs.append((pts, stud))
    _bulk_boxes(s, boxes, 'toon')
    _bulk_polys(s, studs, 'toon')


def _ruyi(s, cx, z, w, f, col):
    """裙板上的金色如意头：一团压扁的金、两边各一个卷"""
    y = f * 0.026
    s.blob(1.0, (cx, y, z), (w * 0.14, 0.006, w * 0.1), col, subdiv=1, bump=0.0)
    for sg in (-1, 1):
        pts = [(cx + sg * (w * 0.1 + w * 0.08 * math.cos(t_)), y, z - 0.01 + w * 0.08 * math.sin(t_) * 0.8) for t_ in [math.pi * (0.3 + 1.4 * i / 8) * (1 if sg > 0 else -1) + (0 if sg > 0 else math.pi) for i in range(9)]]
        s.tube(pts, 0.004, col, segs=4)


def _leaf(lw, lh, kind='door', glow=False, rng=None):
    """一扇格扇（kind='door'）或槛窗（'window'）。本地坐标：x 从门轴那边 0 到 lw，z 从 0 到 lh，厚度沿 y 居中。两面一样"""
    s = Asset('_leaf')
    red, redd, redl = C('red'), C('red_dark'), C('red_lit')
    gold, gd = C('gold'), C('gold_dark')
    T, st, rh = 0.075, 0.055, 0.05
    for x in (st / 2, lw - st / 2):
        s.box((st, T, lh), (x, 0, 0), color=redd, bevel=0.008, mat='lacquer')
    if kind == 'door':
        zones = [(rh, 0.2, 'tao'), (0.2 + rh, 0.86, 'qun'), (0.86 + rh, 1.04, 'tao'), (1.04 + rh, lh - 0.2 - rh, 'gexin'), (lh - 0.2, lh - rh, 'tao')]
    else:
        zones = [(rh, 0.17, 'tao'), (0.17 + rh, lh - 0.17 - rh, 'gexin'), (lh - 0.17, lh - rh, 'tao')]
    # 抹头（横档）：每一格之间一道
    edges = sorted({0.0, lh - rh} | {z1 for (_, z1, _) in zones[:-1]})
    for z in edges:
        s.box((lw - 2 * st + 0.004, T * 0.92, rh), (lw / 2, 0, z), color=redd, bevel=0.006, mat='lacquer')
    iw = lw - 2 * st
    for (z0, z1, k) in zones:
        hh = z1 - z0
        if k == 'gexin':
            _gexin(s, st, z0, iw, hh, glow=glow)
            continue
        s.box((iw, 0.026, hh), (lw / 2, 0, z0), color=red, bevel=0.004, mat='lacquer')
        s.box((iw - 0.06, 0.036, hh - 0.05), (lw / 2, 0, z0 + 0.025), color=redl, bevel=0.012, mat='lacquer')
        for f in (-1, 1):
            if k == 'qun':
                _ruyi(s, lw / 2, z0 + hh / 2, iw, f, gold)
                # 裙板四角各一个小金卷
                for (u, v) in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                    s.blob(0.012, (lw / 2 + u * (iw / 2 - 0.05), f * 0.02, z0 + hh / 2 + v * (hh / 2 - 0.05)), (1, 0.4, 1), gd, subdiv=0, bump=0.0)
            else:
                s.blob(1.0, (lw / 2, f * 0.02, z0 + hh / 2), (iw * 0.16, 0.006, hh * 0.22), gold, subdiv=1, bump=0.0)
    # 看叶：四个角上的铜饰（L 形）
    for f in (-1, 1):
        for (u, v) in ((0, 0), (1, 0), (0, 1), (1, 1)):
            x = 0.035 if u == 0 else lw - 0.035
            z = 0.035 if v == 0 else lh - 0.035
            s.box((0.07, 0.005, 0.016), (x + (0.017 if u == 0 else -0.017), f * (T / 2 + 0.0015), z), color=gold, bevel=0.0, base=False)
            s.box((0.016, 0.005, 0.07), (x, f * (T / 2 + 0.0035), z + (0.017 if v == 0 else -0.017)), color=gold, bevel=0.0, base=False)
    return s


def _transom(a, x0, x1, y, z0, z1):
    """横披窗：一道木框，里面窗纸（夜里亮，暖黄）和两面的斜方格（菱花）棂条，交点上一朵小金花。
    评审：以前是白纸上的方格，像日式的障子"""
    w, h = x1 - x0, z1 - z0
    a.box((w, 0.006, h), ((x0 + x1) / 2, y, z0), color=C('paper_warm'), bevel=0, mat='glow', glow=1.0)
    lat = C('lattice')
    gold = C('gold')
    boxes = []
    step = 0.12                    # 斜格的间距（沿水平量）
    for f in (-1, 1):
        yb = y + f * 0.013
        for sg in (-1, 1):
            # 一条条 ±45 度的棂条：在横披里截出来（每条从框的一边到另一边）
            k0 = int(math.floor((-h) / step)) - 1
            for k in range(k0, int(math.ceil(w / step)) + 2):
                # 直线 x = x0 + k*step + sg*(z - z0)，截在 [x0, x1] × [z0, z1] 里
                pts = []
                for zz in (z0, z1):
                    xx = x0 + k * step + sg * (zz - z0)
                    if x0 - 1e-6 <= xx <= x1 + 1e-6:
                        pts.append((xx, zz))
                for xx in (x0, x1):
                    zz = z0 + (xx - (x0 + k * step)) * sg
                    if z0 - 1e-6 <= zz <= z1 + 1e-6:
                        pts.append((xx, zz))
                pts = sorted(set((round(px, 5), round(pz, 5)) for (px, pz) in pts))
                if len(pts) < 2:
                    continue
                (ax, az), (bx, bz) = pts[0], pts[-1]
                L = math.hypot(bx - ax, bz - az)
                if L < 0.02:
                    continue
                boxes.append((((ax + bx) / 2, yb, (az + bz) / 2), (L, 0.02, 0.014), 0.0, -math.atan2(bz - az, bx - ax), lat))
        # 交点上的小金花（只在朝外那一面）
        if f < 0:
            for i in range(int(w / step) + 1):
                for j in range(int(h / step) + 1):
                    xx, zz = x0 + (i + 0.5) * step, z0 + (j + 0.5 * (i % 2)) * step
                    if x0 + 0.03 < xx < x1 - 0.03 and z0 + 0.03 < zz < z1 - 0.03 and (i + j) % 2 == 0:
                        boxes.append(((xx, yb - 0.012, zz), (0.022, 0.006, 0.022), 0.0, math.pi / 4, gold))
    _bulk_boxes(a, boxes, 'toon')
    for z in (z0, z1):
        a.box((w, 0.09, 0.04), ((x0 + x1) / 2, y, z), color=C('red_dark'), bevel=0.008, mat='lacquer', base=False)


def _xuanzi_beam(a, F, p0, p1, z0, z1, t, breaks, key, part, faces=(1, 1), color=None, mat='toon', bottom=None):
    """一根画了旋子彩画的梁枋：方木（toon）两侧是彩画，breaks 是分间的位置（离 p0 的距离），每间画一套。
    画了彩画的那一面没有木头的面，彩画面本身就是梁的侧面（和顶面、底面、端面共用棱上的点）：
    以前彩画面离木头几毫米，梁底两边各一条缝，从下面斜着看能看见彩画面的背面"""
    p0, p1 = Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0))
    D = (p1 - p0)
    L = D.length
    D.normalize()
    color = color or _BLU_D
    Z = Vector((0, 0, 1))
    bs = sorted(set([0.0, L] + [b for b in breaks if 0.05 < b < L - 0.05]))
    # 每一间里彩画还要分成三段（箍头、方心、箍头），这些分点都要在顶面、底面的棱上（不然棱上有 T 形接缝，会漏一个亮点）
    cuts = set()
    for i in range(len(bs) - 1):
        d0, d1 = bs[i], bs[i + 1]
        e = min(0.25 * _aspect('beam', key) * (z1 - z0), 0.3 * (d1 - d0))
        cuts |= {d0, d0 + e, d1 - e, d1}
    cuts = sorted(cuts)
    nR = Vector((D.y, -D.x, 0))                     # side = +1 那一面（D 的右手边）
    painted = {1: bool(faces[0]), -1: bool(faces[1])}
    polys = []
    for (zz, up) in ((z1, True), (z0, False)):
        right = [p0 + D * d + nR * (t / 2) + Z * zz for d in cuts]
        left = [p0 + D * d - nR * (t / 2) + Z * zz for d in reversed(cuts)]
        ring = right + left                         # 从上往下看是逆时针（右边往前、左边往回）：顶面就这样，底面倒过来
        ring = ring if up else list(reversed(ring))
        polys.append(([tuple(v) for v in ring], bottom if (up and bottom is not None) else color))
    for (pa, sg) in ((p0, -1), (p1, 1)):            # 两个端面
        q = [pa + nR * (t / 2) + Z * z0, pa - nR * (t / 2) + Z * z0, pa - nR * (t / 2) + Z * z1, pa + nR * (t / 2) + Z * z1]
        if sg < 0:
            q = list(reversed(q))
        polys.append(([tuple(v) for v in q], color))
    for side in (1, -1):
        if painted[side]:
            continue
        n = nR * side
        q = [p0 + n * (t / 2) + Z * z0, p1 + n * (t / 2) + Z * z0, p1 + n * (t / 2) + Z * z1, p0 + n * (t / 2) + Z * z1]
        if (q[1] - q[0]).cross(q[3] - q[0]).dot(n) < 0:
            q = list(reversed(q))
        polys.append(([tuple(v) for v in q], color))
    t_ = new_bm()
    col = t_.loops.layers.float_color['col']
    for (pts, c) in polys:
        f = t_.faces.new([t_.verts.new(p) for p in pts])
        for l in f.loops:
            l[col] = (c[0], c[1], c[2], 0.0)
    a.merge(t_, mat)
    for side in (1, -1):
        if not painted[side]:
            continue
        n = nR * side
        A = Z.cross(n)
        for i in range(len(bs) - 1):
            d0, d1 = bs[i], bs[i + 1]
            start = p0 + D * (d0 if A.dot(D) > 0 else d1)
            start = start + n * (t / 2) + Vector((0, 0, z0))
            _xz_run(F, 'beam', key, start, A, Z, d1 - d0, z1 - z0, part=part)


def _tris(a):
    return sum(v[1] for v in a.stats().values())


def hall(name):
    a = Asset(name)
    tri_log = []
    def mark(label):
        tri_log.append((label, _tris(a)))
    rng = a.rng
    F = {}                                  # 手绘贴图的面：{部件名: [(点, uv)]}
    st, sl, sd = C('stone'), C('stone_lit'), C('stone_dark')
    red, redd, redl = C('red'), C('red_dark'), C('red_lit')
    gold, gd = C('gold'), C('gold_dark')
    PW, PD, PH = H_PW, H_PD, H_PH
    xs = H_XS
    FY, WY, BY, BC = H_FY, H_WY, H_BY, H_BC
    top = PH + H_CH
    X, Y0, Y1 = H_IN
    LX, LY0, LY1 = H_LX, H_LY0, H_LY1

    # ═════════ 台基 ═════════
    # 最下一层台座往地下多埋 0.9 米：殿后两角离湖岸近，那里的地面往下斜（东北角约 -0.36），台座不能悬空
    a.box((PW + 0.3, PD + 0.3, 1.06), (0, 0, -0.9), color=sd, bevel=0.04, mat='stone')
    # 这一层的顶要比上面那层石板低：两个面叠在同一高度会抢着显示，一直闪
    a.box((PW, PD, PH - 0.16), (0, 0, 0.1), color=st, bevel=0.05, segs=2, grad=(tint(st, -0.06), st), mat='brick')
    a.box((PW + 0.16, PD + 0.16, 0.12), (0, 0, PH - 0.12), color=sl, bevel=0.035, segs=2, top=C('slab_c'), mat='stone')

    # 台面铺方砖：屋外的三块（前廊和前面、两侧、后面），屋里另铺金砖
    def slabs(x0, x1, y0, y1, nx_, ny_):
        slw, sld = (x1 - x0) / nx_, (y1 - y0) / ny_
        for i in range(nx_):
            for j in range(ny_):
                cx, cy = x0 + slw * (i + 0.5), y0 + sld * (j + 0.5)
                c = vary(rng.choice([C('slab'), C('slab_b'), C('slab_c')]), rng, 0.03, 0.02)
                a.prism([(-slw / 2 + 0.02, -sld / 2 + 0.02), (slw / 2 - 0.02, -sld / 2 + 0.02), (slw / 2 - 0.02, sld / 2 - 0.02), (-slw / 2 + 0.02, sld / 2 - 0.02)],
                        PH - 0.02, PH + 0.035 + rng.uniform(-0.004, 0.004), tint(c, -0.1), bevel=0.018, top=c, loc=(cx, cy, 0), mat='slab')
    ex0 = PW / 2 - 0.25
    slabs(-ex0, ex0, -PD / 2 + 0.25, WY - 0.12, 14, 3)                 # 前廊和廊前
    slabs(-ex0, -X - 0.26, WY - 0.12, PD / 2 - 0.25, 2, 8)             # 西侧
    slabs(X + 0.26, ex0, WY - 0.12, PD / 2 - 0.25, 2, 8)               # 东侧
    slabs(-X - 0.26, X + 0.26, BY + 0.13, PD / 2 - 0.25, 12, 1)        # 后面
    # 台基侧面：砌石的缝（两层错缝）
    seam = tint(sd, -0.06)
    for (x0, y0, x1, y1) in ((-PW / 2, -PD / 2, PW / 2, -PD / 2), (-PW / 2, -PD / 2, -PW / 2, PD / 2), (PW / 2, -PD / 2, PW / 2, PD / 2), (-PW / 2, PD / 2, PW / 2, PD / 2)):
        L = math.hypot(x1 - x0, y1 - y0)
        ang = math.atan2(y1 - y0, x1 - x0)
        if abs(y1 - y0) < 1e-6:
            nx, ny = (0, -1) if y0 < 0 else (0, 1)
        else:
            nx, ny = (-1, 0) if x0 < 0 else (1, 0)
        a.box((L, 0.016, 0.02), ((x0 + x1) / 2 + nx * 0.004, (y0 + y1) / 2 + ny * 0.004, 0.36), rot=(0, 0, ang), color=seam, bevel=0)
        n = int(L / 1.15)
        for row, (z0, zh) in enumerate(((0.17, 0.19), (0.38, 0.2))):
            for i in range(n):
                k = (i + (0.5 if row else 0.0)) / n
                if y0 < 0 and abs(y1 - y0) < 1e-6 and abs(x0 + (x1 - x0) * k) < 2.5:
                    continue
                a.box((0.02, 0.016, zh), (x0 + (x1 - x0) * k + nx * 0.004, y0 + (y1 - y0) * k + ny * 0.004, z0), rot=(0, 0, ang), color=seam, bevel=0)
    # 台阶（前沿不变：世界 z 9.48..10.9）
    for k in range(4):
        d = 0.36 * (4 - k)
        # 最上一级矮 3 毫米：它和台帮压面石有 10 厘米叠在一起，顶面一样高会闪
        a.box((4.7, d, 0.175 if k < 3 else 0.172), (0, -PD / 2 - d / 2 + 0.02, k * 0.175), color=tint(st, 0.02 * k), bevel=0.025, top=sl, mat='stone')
    for sx in (-1, 1):
        a.box((0.36, 1.62, 0.2), (sx * 2.55, -PD / 2 - 0.7, 0.24), rot=(math.atan2(0.7, 1.44), 0, 0), color=sl, bevel=0.04, base=False)
        a.box((0.4, 0.4, 0.5), (sx * 2.55, -PD / 2 - 1.5, 0), color=st, bevel=0.05, top=sl)
    # 栏杆
    hx, hy = PW / 2 - 0.12, PD / 2 - 0.12
    _rail(a, (-hx, -hy), (-2.9, -hy), PH)
    _rail(a, (2.9, -hy), (hx, -hy), PH)
    _rail(a, (-hx, -hy), (-hx, hy), PH, ends=False)
    _rail(a, (hx, -hy), (hx, hy), PH, ends=False)
    _rail(a, (-hx, hy), (hx, hy), PH)

    mark('台基')
    # ═════════ 柱子 ═════════
    cols = [(x, FY) for x in xs] + [(x, WY) for x in xs] + [(x, BC) for x in xs] + [(sx * 6.6, y) for sx in (-1, 1) for y in H_SY[1:3]]
    for (x, y) in cols:
        inwall = (y == BC) or (abs(x) > 6.5 and y > WY)
        _column(a, x, y, PH, top, 0.205, rng, base_half=0.24 if inwall else 0.31, petals=not inwall)
    for (x, y) in H_JIN:
        _column(a, x, y, H_FLOOR, H_BEAM0, H_JIN_R, rng, mat_pre='in_', base_half=0.33, band_z=4.55)

    mark('柱子')
    # ═════════ 墙：两山和后墙，外面粉墙、下面一截石裙 ═════════
    def wall(x0, y0, x1, y1, t=0.26):
        L = math.hypot(x1 - x0, y1 - y0)
        ang = math.atan2(y1 - y0, x1 - x0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        a.box((L, t, 0.95), (cx, cy, PH), rot=(0, 0, ang), color=C('wall_dark'), bevel=0.02, top=sl, mat='brick')
        # 两山、后墙：红墙（评审：官式的红柱大殿配白粉墙、黄水渍，不像）；下面一截还是青灰的石裙
        a.box((L, t - 0.06, H_CH - 0.99), (cx, cy, PH + 0.95), rot=(0, 0, ang), color=C('wall_red'), bevel=0.0, grad=(tint(C('wall_red'), -0.12), C('wall_red')), mat='plaster')
    wall(-6.6, WY, -6.6, BY + 0.13)
    wall(6.6, WY, 6.6, BY + 0.13)
    wall(-6.47, BY, 6.47, BY)

    mark('墙')
    # ═════════ 正面：中间三间格扇门（开着，折在门框里侧），两边两间槛窗 ═════════
    lean = []                       # 开着的门扇：(门轴点, 扇叠起来的外框四角) 给 Unity 加碰撞
    for i in range(5):
        x0, x1 = xs[i] + 0.2, xs[i + 1] - 0.2
        ox0, ox1 = x0 + 0.08, x1 - 0.08
        w = x1 - x0
        cx = (x0 + x1) / 2
        door = 1 <= i <= 3
        # 抱框
        for xx in (x0 + 0.04, x1 - 0.04):
            a.box((0.08, 0.24, 4.26 - PH), (xx, WY, PH), color=redd, bevel=0.01, mat='lacquer')
        # 中槛、上槛、横披
        a.box((w, 0.2, 0.12), (cx, WY, 3.62), color=redd, bevel=0.012, mat='lacquer')
        _transom(a, ox0, ox1, WY, 3.74, 4.14)
        a.box((w, 0.2, 0.12), (cx, WY, 4.14), color=redd, bevel=0.012, mat='lacquer')
        if door:
            # 门槛（矮，人能直接走过去）：夹在两边抱框中间（以前通长，两头和抱框的正面叠着）
            a.box((w - 0.16, 0.24, H_DOOR_SILL - PH), (cx, WY, PH), color=redd, bevel=0.012, top=redl, mat='lacquer')
            # 门簪：中槛外面两颗六角的木钉，钉头一朵金花
            for sg in (-1, 1):
                px = cx + sg * w * 0.25
                a.lathe([(0.0, 0.0), (0.07, 0.0), (0.07, 0.12), (0.0, 0.12)], (px, WY - 0.1, 3.68), segs=6, color=red, rot=(math.pi / 2, 0, 0), mat='lacquer')
                a.lathe([(0.0, 0.0), (0.055, 0.0, gd), (0.05, 0.012, gold), (0.02, 0.02), (0.0, 0.022)], (px, WY - 0.22, 3.68), segs=12, color=gold, rot=(math.pi / 2, 0, 0))
            # 连楹（室内一侧，门扇上面的门轴插在它的圆孔里）和地上的门枕
            a.box((w - 0.16, 0.09, 0.1), (cx, WY + 0.165, 3.52), color=redd, bevel=0.012, mat='lacquer')
            lw = (ox1 - ox0) / 4
            lh = 3.61 - (H_DOOR_SILL + 0.02)
            for side in (-1, 1):
                hx_ = ox0 + 0.035 if side < 0 else ox1 - 0.035
                hy_ = Y0 + 0.045
                th = math.radians(H_LEAF_OPEN) if side < 0 else math.radians(180 - H_LEAF_OPEN)
                dA = Vector((math.cos(th), math.sin(th), 0))
                nA = Vector((dA.y, -dA.x, 0)) if side < 0 else Vector((-dA.y, dA.x, 0))   # 指向门洞中间
                H0 = Vector((hx_, hy_, 0))
                z0 = H_DOOR_SILL + 0.02
                # 门扇 A（挨着门框）
                la = _leaf(lw, lh, 'door', rng=rng)
                a.place(la, (H0.x, H0.y, z0), (0, 0, th))
                # 门扇 B：折回来贴在 A 的门洞一侧
                E = H0 + dA * lw
                Eb = E + nA * 0.085
                thb = th + math.pi + (math.radians(3) if side < 0 else -math.radians(3))
                lb = _leaf(lw, lh, 'door', rng=rng)
                a.place(lb, (Eb.x, Eb.y, z0), (0, 0, thb))
                # 两扇之间的合页（三个）、门轴上下的轴头、门枕
                hj = E + nA * 0.042
                for zz in (0.3, lh / 2, lh - 0.4):
                    a.cyl(0.013, 0.11, (hj.x, hj.y, z0 + zz), gd, segs=8, top=gold)
                    a.box((0.06, 0.004, 0.08), (hj.x - nA.x * 0.0, hj.y, z0 + zz + 0.015), rot=(0, 0, th), color=gold, bevel=0.0)
                a.cyl(0.022, 0.08, (H0.x, H0.y, z0 + lh - 0.01), C('bronze_dark'), segs=8)
                a.cyl(0.05, 0.03, (H0.x, H0.y, 3.49), C('bronze'), segs=10, top=C('bronze_lit'))
                a.cyl(0.022, 0.05, (H0.x, H0.y, z0 - 0.04), C('bronze_dark'), segs=8)
                a.box((0.16, 0.18, 0.05), (H0.x + (0.03 if side < 0 else -0.03), H0.y + 0.04, H_FLOOR - 0.005), color=sd, bevel=0.012, top=st, mat='stone')
                # 叠起来的两扇占的地方（给碰撞）
                Ab = Eb + Vector((math.cos(thb), math.sin(thb), 0)) * lw
                pts = [H0 - nA * 0.04, E - nA * 0.04, Eb + nA * 0.04, Ab + nA * 0.04]
                lean.append((i, side, [(round(p.x, 3), round(p.y, 3)) for p in pts], round(z0, 3), round(z0 + lh, 3)))
        else:
            # 槛墙、风槛、四扇槛窗（关着，窗纸夜里亮）
            a.box((w - 0.03, 0.26, 0.95), (cx, WY, PH), color=C('wall_dark'), bevel=0.02, top=sl, mat='brick')
            a.box((w - 0.01, 0.2, 0.085), (cx, WY, 1.65), color=redd, bevel=0.01, mat='lacquer')
            lw = (ox1 - ox0) / 4
            for k in range(4):
                lf = _leaf(lw, 3.62 - 1.73, 'window', glow=True, rng=rng)
                a.place(lf, (ox0 + lw * k, WY, 1.73))
    # 走马板：横披上面到天花（外面在前廊天花以上看不见，里面是墙）
    a.box((13.2, 0.2, H_JUN + 0.03 - 4.26), (0, WY, 4.26), color=redd, bevel=0.0, mat='lacquer')

    mark('门窗')
    # ═════════ 檐下：额枋（彩画）、斗拱、拱垫板、前廊天花 ═════════
    LW, LD, LH = 8.5, 6.81, 5.0                 # 下檐：半宽、半深、高
    ez = top + 0.52
    def soffit(x, y):
        return _roof_h(LW, LD, LH, ez, 0.7, x, y, H_ROOF_YC) - 0.12
    bays_x = [xx + 6.6 for xx in xs]           # 前后的分间（离西头的距离）
    _xuanzi_beam(a, F, (-6.85, FY), (6.85, FY), top - 0.42, top, 0.3, [b + 0.25 for b in bays_x], 'xuanzi_a', 'paint_beam')
    _xuanzi_beam(a, F, (-6.85, BC + 0.06), (6.85, BC + 0.06), top - 0.42, top, 0.28, [b + 0.25 for b in bays_x], 'xuanzi_a', 'paint_beam', faces=(0, 1))
    # 两山的额枋顶在前后额枋的里侧（以前从柱中到柱中，角上和前后的额枋叠着，底面、顶面一样高）
    ya, yb_ = FY + 0.15 + 0.001, BC + 0.06 - 0.14 - 0.001
    for sx in (-1, 1):
        yb = [y - ya for y in H_SY if ya < y < yb_]
        p0, p1 = (sx * 6.66, ya), (sx * 6.66, yb_)
        if sx < 0:
            p0, p1 = p1, p0
            yb = [yb_ - y for y in H_SY if ya < y < yb_]
        _xuanzi_beam(a, F, p0, p1, top - 0.42, top, 0.26, yb, 'xuanzi_b', 'paint_beam', faces=(1, 0))
    # 平板枋：额枋上面一道薄的（连珠）
    # 前后两道通长，两山的夹在中间（角上不叠：叠着的底面从下面看得见，一直闪）
    for (p0, p1, t) in (((-7.0, FY), (7.0, FY), 0.34), ((-7.0, BC + 0.06), (7.0, BC + 0.06), 0.3),
                        ((-6.7, FY + 0.171), (-6.7, BC + 0.06 - 0.151), 0.3), ((6.7, FY + 0.171), (6.7, BC + 0.06 - 0.151), 0.3)):
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        a.box((L, t, 0.08), ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, top), rot=(0, 0, ang), color=_BLU_D, bevel=0.01, top=gd)
    # 拱垫板：斗拱后面一整圈红板，从柱顶一直到屋檐底下（不然从檐下往上看能看到屋里的夹层）
    zt = top + 0.08
    def board(x0, y0, x1, y1, zmax):
        L = math.hypot(x1 - x0, y1 - y0)
        ang = math.atan2(y1 - y0, x1 - x0)
        a.box((L, 0.05, zmax - zt), ((x0 + x1) / 2, (y0 + y1) / 2, zt), rot=(0, 0, ang), color=redd, bevel=0.0)
    board(-6.75, FY, 6.75, FY, soffit(0, FY) - 0.04)
    board(-6.75, BC + 0.06, 6.75, BC + 0.06, soffit(0, BC) - 0.04)
    for sx in (-1, 1):
        board(sx * 6.66, FY, sx * 6.66, BC + 0.06, soffit(6.66, 0) - 0.04)
    # 斗拱：前后两山各一行，往外挑
    s_dg = 0.9
    _dougong_row(a, (-6.6, FY), (6.6, FY), zt, -math.pi / 2, 0.66, s_dg, inner=0.15)
    _dougong_row(a, (-6.6, BC + 0.06), (6.6, BC + 0.06), zt, math.pi / 2, 0.66, s_dg, inner=0.15)
    for sx in (-1, 1):
        _dougong_row(a, (sx * 6.66, FY), (sx * 6.66, BC + 0.06), zt, 0 if sx > 0 else math.pi, 0.66, s_dg, ends=False, inner=0.15)
    # 挑檐枋：斗拱外头一圈连起来的木枋
    o = 0.62 * s_dg
    zf = zt + 0.42 * s_dg
    for (p0, p1) in (((-6.6 - o, FY - o), (6.6 + o, FY - o)), ((-6.6 - o, BC + 0.06 + o), (6.6 + o, BC + 0.06 + o)),
                     ((-6.66 - o, FY - o), (-6.66 - o, BC + 0.06 + o)), ((6.66 + o, FY - o), (6.66 + o, BC + 0.06 + o))):
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        a.box((L, 0.08, 0.12), ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, zf), rot=(0, 0, ang), color=_BLU_D, bevel=0.01, top=_GRN)
    # 前廊天花：一格格天花板（彩画），支条绿色
    pz = 4.92
    a.box((13.3, 1.86, 0.08), (0, (FY + WY) / 2, pz + 0.065), color=_GRN_D, bevel=0.0)
    gx = [-6.6 + 0.66 * k for k in range(21)]
    gy = [FY + 0.6 * k for k in range(4)]
    for i in range(20):
        for j in range(3):
            _pq(F, 'ceiling', 'panel_lotus' if (i + j) % 2 == 0 else 'panel_wheel', (gx[i], gy[j], pz + 0.06), (0, 1, 0), (1, 0, 0), 0.6, 0.66, part='paint_ceiling')
    ribs = []
    for xx in gx:
        ribs.append(((xx, (FY + WY) / 2, pz + 0.03), (0.07, 1.86, 0.06), 0.0, 0.0, _GRN))
    for yy in gy:
        ribs.append(((0, yy, pz + 0.03), (13.3, 0.07, 0.06), 0.0, 0.0, _GRN))
    _bulk_boxes(a, ribs, 'toon')

    mark('檐下')
    # ═════════ 下檐屋顶 ═════════
    a.roof(LW, LD, LH, z=ez, loc=(0, H_ROOF_YC), lift=0.7, inner=2.3, rows=6, ridge_r=0.12, caps=gold)
    _rafters(a, LW, LD, LH, ez, 0.7, H_ROOF_YC, LW - 6.6 - o - 0.02)

    mark('下檐')
    # ═════════ 上层：四面板壁、小窗、青底金线的檐枋、斗拱 ═════════
    UW, UD = LW - 2.3, LD - 2.3                 # 上层板壁外皮：|x| ≤ 6.2，|y - 0.06| ≤ 4.51
    UH, UZ = 3.4, None
    uz0 = 5.95                                  # 板壁底（藏在下檐瓦面下面、又在室内峻脚上面）
    uz_brk = 6.95                               # 上层斗拱底
    ur = _roof_h(LW, LD, LH, ez, 0.7, UW, 0, H_ROOF_YC)
    uz1 = uz_brk + 0.2
    UZ = uz_brk + 0.6 * 0.8 - 0.05 + 0.13       # 上檐檐口
    def usoffit(x, y):
        return _roof_h(7.7, UD + 1.5, UH, UZ, 0.8, x, y, H_ROOF_YC) - 0.12
    wtop = min(usoffit(UW, 0), usoffit(0, H_ROOF_YC - UD)) - 0.03
    yc = H_ROOF_YC
    for (p0, p1) in (((-UW, yc - UD), (UW, yc - UD)), ((-UW, yc + UD), (UW, yc + UD)), ((-UW, yc - UD), (-UW, yc + UD)), ((UW, yc - UD), (UW, yc + UD))):
        side = abs(p0[0] - p1[0]) < 1e-6
        L0 = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        cxw, cyw = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        nrm = Vector((cxw, cyw - yc, 0))
        nrm = Vector((math.copysign(1, nrm.x), 0, 0)) if side else Vector((0, math.copysign(1, nrm.y), 0))
        # 前后两面的板壁、檐枋、金线通长，两侧的夹在中间（角上叠着的顶面、底面一样高，会闪）
        a.box((L0 + 0.12 if not side else L0 - 0.24, 0.12, wtop - uz0), (cxw - nrm.x * 0.06, cyw - nrm.y * 0.06, uz0), rot=(0, 0, ang), color=red, bevel=0.0, grad=(redd, red), mat='lacquer')
        # 檐枋：青底，上下金线
        a.box((L0 + 0.2 if not side else L0 - 0.16, 0.16, 0.22), (cxw + nrm.x * 0.0, cyw + nrm.y * 0.0, uz_brk - 0.24), rot=(0, 0, ang), color=C('navy'), bevel=0.015)
        for zz in (uz_brk - 0.21, uz_brk - 0.06):
            a.box((L0 + 0.22 if not side else L0 - 0.18, 0.18, 0.03), (cxw, cyw, zz), rot=(0, 0, ang), color=gold, bevel=0.0)
    # 小窗：正面四个（正中挂匾）、后面五个、两侧各三个
    def uwin(x, y, rz):
        sub = Asset('_ul')
        _lattice(sub, 0, 0, 0, 1.5, 0.48, 5, 2)
        a.place(sub, (x, y, uz0 + 0.17), (0, 0, rz))
    for i in range(5):
        cxl = (xs[i] + xs[i + 1]) / 2 * 0.9
        if i != 2:
            uwin(cxl, yc - UD - 0.03, 0.0)
        uwin(cxl, yc + UD + 0.03, math.pi)
    for sx in (-1, 1):
        for k in range(3):
            uwin(sx * (UW + 0.03), yc - UD + (k + 0.5) * 2 * UD / 3, math.pi / 2 if sx > 0 else -math.pi / 2)
    plaque_skip = [(0.0, yc - UD, 1.5)]
    s_up = 0.8
    _dougong_row(a, (-UW, yc - UD), (UW, yc - UD), uz_brk, -math.pi / 2, 0.78, s_up, skip=plaque_skip, inner=0.1, lite=True)
    _dougong_row(a, (-UW, yc + UD), (UW, yc + UD), uz_brk, math.pi / 2, 0.78, s_up, inner=0.1, lite=True)
    for sx in (-1, 1):
        _dougong_row(a, (sx * UW, yc - UD), (sx * UW, yc + UD), uz_brk, 0 if sx > 0 else math.pi, 0.78, s_up, ends=False, inner=0.1, lite=True)
    # 上层檐
    a.roof(7.7, UD + 1.5, UH, z=UZ, loc=(0, yc), lift=0.8, rows=8, ridge_r=0.15, tip=0.6, caps=gold, bells=True)
    _rafters(a, 7.7, UD + 1.5, UH, UZ, 0.8, yc, 1.5 - 0.42)
    rz = UZ + UH
    a.lathe([(0.0, 0), (0.2, 0.03), (0.24, 0.16), (0.12, 0.26), (0.2, 0.44), (0.15, 0.6), (0.05, 0.72), (0.0, 0.9)], (0, 0, rz + 0.12), segs=16, color=gold)

    mark('上层')
    # ═════════ 匾：蓝底金字「大雄宝殿」，金边，红色的云纹框 ═════════
    _plaque(a, (0, yc - UD - 0.17, 6.9))
    # ═════════ 楹联：中间两根前廊柱上 ═════════
    # 和匾一样用繁体（评审：匾是「寶」、联是简体，一座殿里两种字）
    _couplet(a, (1.32, FY - 0.235, top - 2.15), '慈雲廣被')      # 上联在右（东）
    _couplet(a, (-1.32, FY - 0.235, top - 2.15), '慧日長明')     # 下联在左（西）

    # 檐下的红灯笼（挂绳一直接到檐底）
    for x in (-5.28, -2.64, 2.64, 5.28):
        yl = FY - 0.85
        zl = top + 0.3
        _hang_lantern(a, x, yl, zl, 1.25)
        a.cyl(0.012, soffit(x, yl) + 0.05 - zl, (x, yl, zl), C('rope_dark'), segs=5)

    mark('匾联灯')
    # ═════════ 室内 ═════════
    _interior(a, F, rng)

    mark('室内')
    # 手绘贴图的面一起放进去
    for part, faces in F.items():
        a.uvfaces(faces, part, weld=True)
    mark('彩画面')
    prev = 0
    print('[yjm] hall 三角形：' + '，'.join(f'{k} {v - p_:,}' for (k, v), p_ in zip(tri_log, [0] + [v for _, v in tri_log[:-1]])))
    for e in lean:
        print('[yjm] hall 开着的门扇', e)
    return a.finish(view=(18, 40, 0.92), dist=1.4)


def _plaque(a, c):
    """匾：外圈金边、红底云纹框、里圈金边、蓝底，上面立体的金字。c 是匾心（世界里在门的正上方，往前倾 12°）"""
    sub = Asset('_plaque')
    gold, gd = C('gold'), C('gold_dark')
    W, H = 2.76, 1.06
    sub.box((W, 0.1, H), (0, 0.05, 0), color=gd, bevel=0.035, segs=2, base=False)
    sub.box((W - 0.12, 0.12, H - 0.12), (0, 0.035, 0), color=C('red'), bevel=0.012, base=False)
    sub.box((2.2, 0.14, 0.62), (0, 0.02, 0), color=gold, bevel=0.025, segs=2, base=False)
    sub.box((2.08, 0.16, 0.5), (0, 0.005, 0), color=_BLU_D, bevel=0.01, base=False)
    # 红框上的金色云纹：一朵朵卷云
    fy = -0.025
    spots = [(-1.18, 0.0), (1.18, 0.0)] + [(-0.95 + 0.38 * k, 0.4) for k in range(6)] + [(-0.95 + 0.38 * k, -0.4) for k in range(6)]
    for (x, z) in spots:
        sub.blob(1.0, (x, fy, z), (0.045, 0.012, 0.03), gold, subdiv=2, bump=0.0)
        for sg in (-1, 1):
            pts = [(x + sg * (0.04 + 0.035 * math.cos(t_)), fy - 0.004, z + 0.035 * math.sin(t_)) for t_ in
                   [(math.pi * (1.2 - 1.6 * i / 10) if sg > 0 else math.pi * (-0.2 + 1.6 * i / 10)) for i in range(11)]]
            sub.tube(pts, 0.008, gold, segs=5)
    # 字：传统横匾从右往左读（最右是「大」），从右往左写就用繁体「寶」（简体「宝」配右起的匾不对）
    sub.text('殿寶雄大', (0, -0.074, 0.0), size=0.43, depth=0.04, bevel=0.007, color=gold, gap=1.08, back=False)
    # 顶上一颗火焰宝珠
    sub.blob(0.06, (0, 0.02, H / 2 + 0.07), (1, 0.6, 1.2), gold, subdiv=2, bump=0.0)
    for sg in (-1, 1):
        sub.tube([(sg * 0.04, 0.02, H / 2), (sg * 0.12, 0.02, H / 2 + 0.06), (sg * 0.08, 0.02, H / 2 + 0.16), (sg * 0.02, 0.02, H / 2 + 0.2)], [0.02, 0.018, 0.012, 0.005], gold, segs=6)
    a.place(sub, c, (math.radians(14), 0, 0))


def _couplet(a, c, text):
    """一条楹联：黑漆板、金边、立体金字，竖排，挂在柱子正面"""
    sub = Asset('_lian')
    gold = C('gold')
    W, H = 0.42, 1.62
    sub.box((W, 0.05, H), (0, 0.025, 0), color=_INK, bevel=0.015, segs=2, base=False)
    for (dx, dz, sx_, sz_) in ((0, H / 2 - 0.035, W - 0.06, 0.012), (0, -H / 2 + 0.035, W - 0.06, 0.012), (W / 2 - 0.035, 0, 0.012, H - 0.06), (-W / 2 + 0.035, 0, 0.012, H - 0.06)):
        sub.box((sx_, 0.006, sz_), (dx, -0.001, dz), color=gold, bevel=0.0, base=False)
    sub.text(text, (0, 0.0, -0.02), size=0.28, depth=0.025, bevel=0.005, color=gold, vertical=True, gap=1.27, back=False)
    # 上下两头的金色如意云头
    for sg in (-1, 1):
        sub.blob(1.0, (0, 0.02, sg * (H / 2 + 0.02)), (0.16, 0.03, 0.05), gold, subdiv=2, bump=0.0)
    a.place(sub, c)


def _interior(a, F, rng):
    """大殿里面：金砖地、护墙（墙裙彩画、壁画）、额枋彩画、斗拱、峻脚、井口天花、藻井"""
    X, Y0, Y1 = H_IN
    LX, LY0, LY1 = H_LX, H_LY0, H_LY1
    gold, gd = C('gold'), C('gold_dark')
    T = 'toon:in_toon'
    LQ = 'lacquer:in_lacquer'
    PB, PC, PW_ = 'paint_beam:in_paint_beam', 'paint_ceiling:in_paint_ceiling', 'paint_wall:in_paint_wall'
    Z = Vector((0, 0, 1))
    t_last = [_tris(a)]

    def mark(label):
        t = _tris(a)
        print(f'[yjm] hall 室内 {label} {t - t_last[0]:,}')
        t_last[0] = t

    # ── 金砖地面：顶面正好 0.72，砖缝深 1.4 厘米 ──
    a.box((2 * X, Y1 - Y0, 0.006), (0, (Y0 + Y1) / 2, 0.70), color=_GROUT, bevel=0.0, mat='slab:in_floor')
    nx_, ny_ = 20, 12
    tw, td = 2 * X / nx_, (Y1 - Y0) / ny_
    for i in range(nx_):
        for j in range(ny_):
            cx, cy = -X + tw * (i + 0.5), Y0 + td * (j + 0.5)
            c = vary(rng.choice(_JINZHUAN), rng, 0.025, 0.015)
            g = 0.006
            a.prism([(-tw / 2 + g, -td / 2 + g), (tw / 2 - g, -td / 2 + g), (tw / 2 - g, td / 2 - g), (-tw / 2 + g, td / 2 - g)],
                    0.69, H_FLOOR, tint(c, -0.08), bevel=0.004, top=c, loc=(cx, cy, 0), mat='slab:in_floor')

    mark('地面')
    # ── 护墙：三面墙内皮一层（暗红），上面贴墙裙、壁画、框 ──
    # 后墙前面是三尊佛的背光（板子在世界 z 21.875..21.93，中尊顶到 y 5.67）：后墙上的东西凸出护墙面都不超过 2.5 厘米，
    # 后墙顶上的峻脚从 5.78 起（两山和前面还是 5.45，靠后墙那 0.7 米斜着升上去）
    zt = H_JUN + 0.03
    zt_b = H_JUN_B + 0.03
    a.box((0.015, LY1 - LY0, zt - H_FLOOR), (LX + 0.0075, (LY0 + LY1) / 2, H_FLOOR), color=_WALL_RED, bevel=0.0, mat=T)
    a.box((0.015, LY1 - LY0, zt - H_FLOOR), (-LX - 0.0075, (LY0 + LY1) / 2, H_FLOOR), color=_WALL_RED, bevel=0.0, mat=T)
    for sx in (-1, 1):
        # 靠后墙那一段护墙接高到 5.81（峻脚在那里升高了）
        a.box((0.015, H_JUN_RAMP + 0.05, zt_b - zt), (sx * (LX + 0.0075), LY1 - (H_JUN_RAMP + 0.05) / 2, zt), color=_WALL_RED, bevel=0.0, mat=T)
    a.box((2 * LX + 0.03, 0.015, zt_b - H_FLOOR), (0, LY1 + 0.0075, H_FLOOR), color=_WALL_RED, bevel=0.0, mat=T)
    a.box((2 * LX + 0.03, 0.015, zt - 4.26), (0, LY0 - 0.0075, 4.26), color=_WALL_RED, bevel=0.0, mat=T)

    def wall_bays(p0, n, A, segs, mural0, fd=0.034):
        """一面墙上一间间的墙裙和壁画。p0：这面墙内皮上 s=0 的点，n：朝屋里，A：沿墙方向，segs：[(s0, s1)]。fd 是框凸出多少"""
        p0, n, A = Vector(p0), Vector(n), Vector(A)
        k_ = fd / 0.034
        for k, (s0, s1) in enumerate(segs):
            w = s1 - s0
            base = p0 + A * s0 + n * 0.002
            ang = math.atan2(A.y, A.x)
            # 踢脚、墙裙（彩画）、墙裙上沿的木线
            a.box((w, 0.03 * k_, 0.12), tuple(base + A * (w / 2) + n * (0.015 * k_ - 0.002))[:2] + (H_FLOOR,), rot=(0, 0, ang), color=_INK, bevel=0.006, mat=T)
            _pq(F, 'wall', 'dado_a' if k % 2 == 0 else 'dado_b', base + Vector((0, 0, 0.84)), A, Z, w, 0.88, part=PW_)
            a.box((w, 0.035 * k_, 0.06), tuple(base + A * (w / 2) + n * (0.0175 * k_ - 0.002))[:2] + (1.72,), rot=(0, 0, ang), color=C('red_deep'), bevel=0.008, top=gold, mat=LQ)
            # 壁画：外框（深红漆、里面一道金线），画心
            mz0, mz1 = 1.84, 4.14
            fw = 0.09
            for (u0, u1, z0, z1) in ((0, w, mz0, mz0 + fw), (0, w, mz1 - fw, mz1), (0, fw, mz0 + fw, mz1 - fw), (w - fw, w, mz0 + fw, mz1 - fw)):
                cc = base + A * ((u0 + u1) / 2) + n * (fd / 2)
                a.box((u1 - u0, fd, z1 - z0), (cc.x, cc.y, z0), rot=(0, 0, ang), color=C('red_deep'), bevel=0.006, mat=LQ)
            # 框面上靠里的一圈细金线
            g0, g1 = fw - 0.032, fw - 0.018
            for (u0, u1, z0, z1) in ((g0, w - g0, mz0 + g0, mz0 + g1), (g0, w - g0, mz1 - g1, mz1 - g0),
                                     (g0, g1, mz0 + g0, mz1 - g0), (w - g1, w - g0, mz0 + g0, mz1 - g0)):
                cc = base + A * ((u0 + u1) / 2) + n * (fd + 0.0025)
                a.box((u1 - u0, 0.004, z1 - z0), (cc.x, cc.y, z0), rot=(0, 0, ang), color=gold, bevel=0.0, mat=T)
            # 每一间一幅（东墙 0–2、西墙 3–5、后墙 6–10），不重复
            _pq(F, 'wall', f'mural_{(mural0 + k) % 12}', base + A * fw + Vector((0, 0, mz0 + fw)), A, Z, w - 2 * fw, mz1 - mz0 - 2 * fw, part=PW_)

    def segs_between(posts, lo, hi, half):
        cut = sorted(posts)
        edges = [lo] + [v for p in cut for v in (p - half, p + half)] + [hi]
        return [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2) if edges[i + 1] - edges[i] > 0.4]

    # 东墙：从前往后（朝屋里是 -x）；西墙：从后往前（朝屋里是 +x）
    sy = [H_SY[1], H_SY[2]]
    east = segs_between(sy, LY0, LY1, 0.17)
    wall_bays((LX, LY1, 0), (-1, 0, 0), (0, -1, 0), [(LY1 - s1, LY1 - s0) for (s0, s1) in reversed(east)], 0)
    wall_bays((-LX, LY0, 0), (1, 0, 0), (0, 1, 0), [(s0 - LY0, s1 - LY0) for (s0, s1) in east], 3)
    # 后墙：从东往西（朝屋里是 -y），柱子藏在墙里，柱位上贴一条红漆的「柱」；都是薄的（背光贴着后墙）
    back = segs_between([1.32, -1.32, 3.96, -3.96], -LX, LX, 0.18)
    wall_bays((-LX, LY1, 0), (0, -1, 0), (1, 0, 0), [(s0 + LX, s1 + LX) for (s0, s1) in back], 6, fd=0.018)
    for xx in (-3.96, -1.32, 1.32, 3.96):
        a.box((0.36, 0.022, 4.3 - H_FLOOR), (xx, LY1 - 0.0095, H_FLOOR), color=C('red'), bevel=0.006, mat=LQ)
        a.box((0.37, 0.028, 0.12), (xx, LY1 - 0.0115, H_FLOOR), color=_INK, bevel=0.006, mat=T)
    # 前墙两边窗下的槛墙里面：墙裙
    for i in (0, 4):
        x0, x1 = H_XS[i] + 0.2, H_XS[i + 1] - 0.2
        _pq(F, 'wall', 'dado_b', (x1, Y0 + 0.012, 0.84), (-1, 0, 0), Z, x1 - x0, 0.78, part=PW_)
        a.box((x1 - x0, 0.03, 0.12), ((x0 + x1) / 2, Y0 + 0.025, H_FLOOR), color=_INK, bevel=0.006, mat=T)

    mark('护墙壁画')
    # ── 额枋（旋子彩画）、平板枋（连珠）：四面墙顶一圈 ──
    zb0, zb1 = 4.30, 4.72
    bt = 0.16
    # 前面通长；两山顶在前面那道的里侧、后面顶到后墙；后墙这道只是 2 厘米的薄板（背光贴着后墙，见上）
    _xuanzi_beam(a, F, (LX + 0.01, LY1 - 0.01), (-LX - 0.01, LY1 - 0.01), zb0, zb1, 0.02,
                  [LX - xx for xx in (3.96, 1.32, -1.32, -3.96)], 'xuanzi_a', PB, faces=(0, 1), mat=T)
    _xuanzi_beam(a, F, (-LX - 0.01, LY0 + bt / 2), (LX + 0.01, LY0 + bt / 2), zb0, zb1, bt,
                  [xx + LX for xx in (-3.96, -1.32, 1.32, 3.96)], 'xuanzi_a', PB, faces=(0, 1), mat=T)
    yb0, yb1 = LY0 + bt + 0.001, LY1 - 0.021
    _xuanzi_beam(a, F, (LX - bt / 2, yb0), (LX - bt / 2, yb1), zb0, zb1, bt,
                  [y - yb0 for y in sy], 'xuanzi_b', PB, faces=(0, 1), mat=T)
    _xuanzi_beam(a, F, (-LX + bt / 2, yb1), (-LX + bt / 2, yb0), zb0, zb1, bt,
                  [yb1 - y for y in reversed(sy)], 'xuanzi_b', PB, faces=(0, 1), mat=T)
    # 平板枋：比额枋凸出少一点，正面画连珠。前面一道通长，两山夹在中间，后墙的是薄板
    zp0, zp1 = zb1, zb1 + 0.12
    for (c0, c1, d_, n_) in (((-LX, LY0 + 0.05), (LX, LY0 + 0.05), 0.1, (0, 1, 0)),
                             ((-LX, LY1 - 0.01), (LX, LY1 - 0.01), 0.02, (0, -1, 0)),
                             ((LX - 0.05, LY0 + 0.101), (LX - 0.05, LY1 - 0.021), 0.1, (-1, 0, 0)),
                             ((-LX + 0.05, LY0 + 0.101), (-LX + 0.05, LY1 - 0.021), 0.1, (1, 0, 0))):
        c0, c1, n_ = Vector(c0 + (0,)), Vector(c1 + (0,)), Vector(n_)
        L = (c1 - c0).length
        cc = (c0 + c1) / 2
        a.box((L, d_, zp1 - zp0), (cc.x, cc.y, zp0), rot=(0, 0, math.atan2(c1.y - c0.y, c1.x - c0.x)), color=_BLU_D, bevel=0.0, mat=T)
        A = Z.cross(n_)
        st_ = cc + n_ * (d_ / 2 + 0.001) - A * (L / 2)
        _band_run(F, 'beam', 'pearl', (st_.x, st_.y, zp0), A, Z, L, zp1 - zp0, part=PB)

    mark('额枋')
    # ── 室内斗拱：前墙、两山一行（往屋里挑），每攒中间隔一块拱眼壁（彩画）；正心枋、拽枋一整行连着 ──
    # 后墙上不挑斗拱（三尊佛的背光贴着后墙），只画一条流云、一条连珠
    zg = zp1
    s_in = 0.9               # 前面那行的耍头不能顶到天花梁（梁在 y -1.9，梁底 5.35）
    rows = []
    fx_ = [-5.28, -3.96, -2.64, -1.32, 0.0, 1.32, 2.64, 3.96, 5.28]
    rows.append(([(x_, LY0 + 0.05) for x_ in fx_], math.pi / 2))
    side_y = [-0.6, 1.62, 2.62, 3.62]
    rows.append(([(LX - 0.05, y_) for y_ in side_y], math.pi))
    rows.append(([(-LX + 0.05, y_) for y_ in side_y], 0.0))
    k_ = 0
    for (pts, ang) in rows:
        for (x_, y_) in pts:
            ca, cb = (_BLU, _GRN) if k_ % 2 == 0 else (_GRN, _BLU)
            _dg_set(a, x_, y_, zg, ang, ca, cb, T, s_in)
            k_ += 1
        # 拱眼壁：两攒之间贴一块（框是上窄下宽的梯形，跟着栱的空当）
        d = Vector((math.cos(ang), math.sin(ang), 0))
        A = Z.cross(d)           # 从屋里看是从左往右
        for i in range(len(pts) - 1):
            p0v, p1v = Vector(pts[i] + (0,)), Vector(pts[i + 1] + (0,))
            gap = (p1v - p0v).length
            if gap > 1.4:
                continue
            mid = (p0v + p1v) / 2 - d * 0.047
            w = gap - 0.3
            st_ = mid - A * (w / 2)
            _pq(F, 'beam', 'gongyan_a' if i % 2 == 0 else 'gongyan_b', (st_.x, st_.y, zg + 0.01), A, Z, w, 0.46, part=PB)
    # 正心枋（贴墙）、拽枋（栱头上）：一整行连着，青地金边
    def fang(c0, c1, z0, h, t):
        c0, c1 = Vector(c0 + (0,)), Vector(c1 + (0,))
        L = (c1 - c0).length
        cc = (c0 + c1) / 2
        _gold_box(a, (L, t, h), (cc.x, cc.y, z0), math.atan2(c1.y - c0.y, c1.x - c0.x), _BLU_D, T)
    S_ = s_in
    v1 = 0.05 + 0.30 * S_                     # 拽枋离护墙面
    tf = 0.09 * S_
    z_zx, h_zx = zg + 0.50 * S_, 0.15 * S_     # 正心枋：压在正心万栱的升上
    z_zy, h_zy = zg + 0.505 * S_, 0.11 * S_    # 拽枋：压在外拽瓜栱的升上
    fang((-LX + 0.005, LY0 + 0.05), (LX - 0.005, LY0 + 0.05), z_zx, h_zx, tf)
    fang((-LX + v1 + tf / 2 + 0.001, LY0 + v1), (LX - v1 - tf / 2 - 0.001, LY0 + v1), z_zy, h_zy, tf)
    # 两山的：在托木（天花梁头）那里断开
    cuts = [(-1.9 - 0.16, -1.9 + 0.16), (0.7 - 0.16, 0.7 + 0.16)]
    def runs(y0, y1):
        out, cur = [], y0
        for (c0, c1) in cuts:
            if c0 > cur and c1 < y1:
                out.append((cur, c0))
                cur = c1
        out.append((cur, y1))
        return out
    for sx in (-1, 1):
        for (r0, r1) in runs(LY0 + 0.05 + tf / 2 + 0.001, LY1 - 0.001):
            fang((sx * (LX - 0.05), r0), (sx * (LX - 0.05), r1), z_zx, h_zx, tf)
        for (r0, r1) in runs(LY0 + v1 - tf / 2, side_y[-1] + 0.45):
            fang((sx * (LX - v1), r0), (sx * (LX - v1), r1), z_zy, h_zy, tf)
    # 四个墙角：一攒角科
    for sx in (-1, 1):
        for (yy, sy_) in ((LY0 + 0.05, 1), (LY1 - 0.05, -1)):
            _dg_corner(a, sx * (LX - 0.05), yy, zg, (-sx, 0), (0, sy_), _GRN, _BLU, T, s_in)
    # 后墙：斗拱那一截画一条流云、上面一条连珠，再往上是护墙（红）到峻脚
    _band_run(F, 'beam', 'cloud_b', (-LX + 0.5, LY1 - 0.003, zg + 0.02), (1, 0, 0), Z, 2 * LX - 1.0, 0.54, part=PB)
    _band_run(F, 'beam', 'pearl', (-LX + 0.5, LY1 - 0.003, zg + 0.6), (1, 0, 0), Z, 2 * LX - 1.0, 0.12, part=PB)

    mark('斗拱')
    # ── 峻脚：墙顶到平顶天花的一圈斜板（流云彩画，两种流云、一段一段掉头）──
    fx, fy0, fy1 = H_FLAT
    ox, oy0, oy1 = LX + 0.02, LY0 - 0.02, LY1 + 0.02
    ix, iy0, iy1, iz = fx + 0.03, fy0 - 0.03, fy1 + 0.03, H_PANEL + 0.004

    def oz(p):
        """峻脚外沿（贴墙那一边）的高：后墙 5.78，两山靠后墙的 0.7 米从 5.45 斜着升上去，别处 5.45"""
        if abs(p.y - oy1) < 1e-6:
            return H_JUN_B - 0.02
        t_ = max(0.0, (p.y - (oy1 - H_JUN_RAMP)) / H_JUN_RAMP)
        return H_JUN - 0.02 + (H_JUN_B - H_JUN) * t_
    outer = [Vector((ox, oy0, 0)), Vector((ox, oy1, 0)), Vector((-ox, oy1, 0)), Vector((-ox, oy0, 0))]
    inner = [Vector((ix, iy0, iz)), Vector((ix, iy1, iz)), Vector((-ix, iy1, iz)), Vector((-ix, iy0, iz))]
    for k in range(4):
        o0, o1 = outer[k], outer[(k + 1) % 4]
        i0, i1 = inner[k], inner[(k + 1) % 4]
        key = 'cloud' if k in (0, 2) else 'cloud_b'
        L = (o1 - o0).length
        slant = 0.7
        n = max(1, int(round(L / (_aspect('beam', key) * slant))))
        m = max(1, int(math.ceil(L / n / 0.3)))           # 每一段再切细，外沿的高才能跟着变
        for j in range(n):
            flip = (j + k) % 2 == 1
            for q in range(m):
                t0, t1 = (j + q / m) / n, (j + (q + 1) / m) / n
                u0, u1 = q / m, (q + 1) / m
                if flip:
                    u0, u1 = 1 - u0, 1 - u1
                pa, pb = o0.lerp(o1, t0), o0.lerp(o1, t1)
                pa.z, pb.z = oz(pa), oz(pb)
                quad = [pa, pb, i0.lerp(i1, t1), i0.lerp(i1, t0)]
                uv = [_pv('beam', key, u0, 0), _pv('beam', key, u1, 0), _pv('beam', key, u1, 1), _pv('beam', key, u0, 1)]
                # 朝下、朝屋里：从屋里看是逆时针
                F.setdefault(PB, []).append((list(reversed([tuple(v) for v in quad])), list(reversed(uv))))
    # 峻脚和平顶交界的一道金色贴梁
    for (p0, p1) in (((fx, fy0), (fx, fy1)), ((-fx, fy0), (-fx, fy1)), ((-fx, fy0), (fx, fy0)), ((-fx, fy1), (fx, fy1))):
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) + 0.1
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        a.box((L, 0.1, 0.07), ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, H_PANEL - 0.07), rot=(0, 0, ang), color=gd, bevel=0.012, top=gold, mat=T)

    mark('峻脚')
    # ── 井口天花：支条（绿）、天花板（彩画）、支条交叉处的金色轱辘 ──
    zx, zy0, zy1 = H_ZJ
    gx = [round(0.66 * k, 4) for k in range(-9, 10)]
    gy = [round(fy0 + 0.65 * k, 4) for k in range(11)]
    ribs = []

    def rib_x(xx, y0, y1):
        if y1 - y0 > 0.05:
            ribs.append(((xx, (y0 + y1) / 2, H_CEIL + 0.03), (0.07, y1 - y0, 0.06), 0.0, 0.0, _GRN))

    def rib_y(yy, x0, x1):
        if x1 - x0 > 0.05:
            ribs.append((((x0 + x1) / 2, yy, H_CEIL + 0.03), (x1 - x0, 0.07, 0.06), 0.0, 0.0, _GRN))
    for xx in gx:
        if abs(abs(xx) - fx) < 1e-3:
            continue
        if abs(xx) < zx + 1e-3:
            # 穿过藻井口的：断开（梁上那几段也不用）
            rib_x(xx, fy0, zy0 - 0.17)
            rib_x(xx, zy1 + 0.17, fy1)
        else:
            rib_x(xx, fy0, zy0 - 0.17)
            rib_x(xx, zy0 + 0.17, zy1 - 0.17)
            rib_x(xx, zy1 + 0.17, fy1)
    for yy in gy:
        if abs(yy - fy0) < 1e-3 or abs(yy - fy1) < 1e-3 or abs(yy - zy0) < 1e-3 or abs(yy - zy1) < 1e-3:
            continue
        if zy0 < yy < zy1:
            rib_y(yy, -fx, -zx - 0.1)
            rib_y(yy, zx + 0.1, fx)
        else:
            rib_y(yy, -fx, fx)
    _bulk_boxes(a, ribs, T)
    for i in range(len(gx) - 1):
        for j in range(len(gy) - 1):
            x0, x1, y0, y1 = gx[i], gx[i + 1], gy[j], gy[j + 1]
            if x0 >= -zx - 1e-3 and x1 <= zx + 1e-3 and y0 >= zy0 - 1e-3 and y1 <= zy1 + 1e-3:
                continue        # 藻井的口
            near = (x0 >= -zx - 0.67 and x1 <= zx + 0.67 and y0 >= zy0 - 0.66 and y1 <= zy1 + 0.66)
            key = 'panel_lotus_b' if near else ('panel_lotus' if (i + j) % 2 == 0 else 'panel_wheel')
            _pq(F, 'ceiling', key, (x0, y0, H_PANEL), (0, 1, 0), (1, 0, 0), y1 - y0, x1 - x0, part=PC)
    for xx in gx[1:-1]:
        for yy in gy[1:-1]:
            if -zx - 1e-3 < xx < zx + 1e-3 and zy0 - 1e-3 < yy < zy1 + 1e-3:
                continue
            if abs(yy - zy0) < 1e-3 or abs(yy - zy1) < 1e-3:
                continue
            a.lathe([(0.0, 0.0), (0.05, 0.0, gd), (0.055, 0.008, gold), (0.035, 0.014, gold), (0.0, 0.016)], (xx, yy, H_CEIL - 0.016), segs=10, color=gold, mat=T)

    mark('天花')
    # ── 天花梁（两根，东西向，压在金柱上）、井口枋（藻井东西两边）、雀替 ──
    for yy in (zy0, zy1):
        _xuanzi_beam(a, F, (-LX, yy), (LX, yy), H_BEAM0, H_PANEL + 0.002, 0.34,
                     [LX + v for v in (-2.8, -zx, zx, 2.8)], 'xuanzi_a' if yy == zy0 else 'xuanzi_b', PB, mat=T, color=_BLU_D)
        # 梁头落在墙上：下面一块云头托木
        for sx in (-1, 1):
            _tuomu(a, F, sx * LX, yy, H_BEAM0, -sx, T, PB)
    for sx in (-1, 1):
        _xuanzi_beam(a, F, (sx * zx, zy0 + 0.17), (sx * zx, zy1 - 0.17), H_PANEL - 0.3, H_PANEL + 0.002, 0.2, [], 'xuanzi_b', PB, mat=T, color=_GRN_D)
    for (x, y) in H_JIN:
        for sg in (-1, 1):
            _queti(a, (x + sg * H_JIN_R * 0.9, y), sg, H_BEAM0, T)

    mark('天花梁雀替')
    # ── 藻井 ──
    _zaojing(a, F, rng)
    mark('藻井')


def _queti(a, p, sg, z, mat):
    """雀替：金柱和梁相交处，沿梁伸出去的一块托木。下沿是一道带卷头的曲线；两面是绿地、金边、
    金色卷草和一片青色的叶，底子朱红。sg 是往哪边伸（+x 或 -x）"""
    L, H, t = 0.7, 0.34, 0.11
    prof = [(0.0, 0.0), (L, 0.0), (L, -0.045)]
    # 下沿：从梢头往柱子，先一个小卷（翘头），再一道向下鼓的弧
    for i in range(1, 15):
        u = i / 14
        x = L * (1 - u)
        y = -0.045 - (H - 0.045) * (u ** 1.6) - 0.035 * math.sin(u * math.pi * 2.0) * (1 - u) ** 0.5
        prof.append((x, y))
    prof.append((0.0, -H))
    def flip(pts):
        return [(-x, y) for (x, y) in reversed(pts)] if sg < 0 else pts
    sub = Asset('_qt')
    sub.prism(flip(prof), -t / 2, t / 2, C('red'), bevel=0.006, mat=mat, rot=(math.pi / 2, 0, 0))
    # 两面各一块凸起的绿地（雀替轮廓往里缩一圈）
    cxp, cyp = 0.26, -0.11
    inner = [(cxp + (x - cxp) * 0.74, cyp + (y - cyp) * 0.7) for (x, y) in prof]
    sub.prism(flip(inner), -t / 2 - 0.008, t / 2 + 0.008, _GRN, bevel=0.004, mat=mat, rot=(math.pi / 2, 0, 0))
    gold = C('gold')
    for f in (-1, 1):
        yf = f * (t / 2 + 0.011)
        # 金边：沿着下沿
        edge = [(sg * x, yf, y + 0.012) for (x, y) in prof[3:-1]]
        sub.tube(edge, 0.006, gold, segs=4, mat=mat)
        # 金色卷草：两个卷、一道茎
        for (cx, cz, r, turns) in ((0.36, -0.1, 0.055, 1.3), (0.17, -0.19, 0.045, 1.2)):
            # 卷到 0.2 r 就停（卷到圆心，最后几段管子挤在一起，面翻过来）
            pts2 = [(sg * (cx + r * (1 - k / 16) * math.cos(-k / 16 * turns * 2 * math.pi)), yf, cz + r * (1 - k / 16) * math.sin(-k / 16 * turns * 2 * math.pi)) for k in range(14)]
            sub.tube(pts2, 0.0055, gold, segs=4, mat=mat)
        stem = [(sg * 0.05, yf, -0.06), (sg * 0.2, yf, -0.07), (sg * 0.36, yf, -0.045), (sg * 0.52, yf, -0.06)]
        sub.tube(stem, 0.005, gold, segs=4, mat=mat)
        # 一片青叶：薄薄的一片（以前是压扁的球，边上的面法线乱）
        leaf = []
        for i in range(12):
            th = 2 * math.pi * i / 12
            u_, w_ = 0.05 * math.cos(th), 0.022 * math.sin(th) * (1 - 0.35 * math.cos(th))
            ca_, sa_ = math.cos(-0.5 * sg), math.sin(-0.5 * sg)
            leaf.append((sg * 0.5 + u_ * ca_ - w_ * sa_, yf - f * 0.0015, -0.1 + u_ * sa_ + w_ * ca_))   # 离绿地 1.5 毫米
        if f > 0:          # 在 xz 面里逆时针 = 朝 -y；+y 那面倒过来
            leaf = list(reversed(leaf))
        _bulk_polys(sub, [(leaf, _BLU_L)], mat)
    a.place(sub, (p[0], p[1], z))


def _rafters(a, W, D, H, z, lift, yc, d_from, step=0.25, r=0.042, thick=0.12):
    """檐下一根根的圆椽：从斗拱外头一直伸到檐口，贴着屋檐底；椽头一圈青、一点金"""
    col = C('red_dark')
    for (L, f) in ((W, lambda u, d: (u, yc - D + d)), (W, lambda u, d: (u, yc + D - d)),
                   (D, lambda u, d: (W - d, yc + u)), (D, lambda u, d: (-W + d, yc + u))):
        n = int(2 * L / step)
        for i in range(1, n):
            u = -L + 2 * L * i / n
            d0 = min(d_from, L - abs(u) - 0.12)
            if d0 < 0.35:
                continue
            pts = []
            for d in (d0, d0 * 0.5, 0.06):
                x, y = f(u, d)
                pts.append((x, y, _roof_h(W, D, H, z, lift, x, y, yc) - thick - r - 0.006))
            a.tube(pts, r, col, segs=5, cap=False)
            # 椽头
            x, y, zz = pts[-1]
            x2, y2, zz2 = pts[-2]
            dv = Vector((x - x2, y - y2, zz - zz2)).normalized()
            q = Vector((0, 0, 1)).rotation_difference(dv).to_euler()
            a.cyl(r * 1.03, 0.012, (x, y, zz), _BLU, segs=8, rot=tuple(q), top=_BLU_L)
            e = Vector((x, y, zz)) + dv * 0.012
            a.cyl(r * 0.38, 0.004, tuple(e), C('gold'), segs=6, rot=tuple(q))


def _zaojing(a, F, rng):
    """藻井：方井 → 八角井（四角是角蝉）→ 圆井 → 穹顶（宝相花），每一层上沿一圈小斗拱，正中倒垂一朵金莲、一颗宝珠"""
    T = 'toon:in_toon'
    PB, PC = 'paint_beam:in_paint_beam', 'paint_ceiling:in_paint_ceiling'
    gold, gd = C('gold'), C('gold_dark')
    zx, zy0, zy1 = H_ZJ
    cx, cy = 0.0, (zy0 + zy1) / 2
    hx, hy = zx, (zy1 - zy0) / 2
    z0, z1, z2, z3 = H_PANEL, 6.24, 6.52, 6.80
    Z = Vector((0, 0, 1))
    # 方井四壁（朝里）
    sides = [((cx + hx, cy - hy), (cx + hx, cy + hy)), ((cx + hx, cy + hy), (cx - hx, cy + hy)), ((cx - hx, cy + hy), (cx - hx, cy - hy)), ((cx - hx, cy - hy), (cx + hx, cy - hy))]
    for (p0, p1) in sides:
        p0v, p1v = Vector((p0[0], p0[1], z0 - 0.002)), Vector((p1[0], p1[1], z0 - 0.002))
        # 从里面看：沿 p1→p0 走、往上（朝向井心）
        _pq(F, 'beam', 'xuanzi_b', p1v, (p0v - p1v).normalized(), Z, (p1v - p0v).length, z1 - z0 + 0.012, part=PB)
    # 方口一圈金边
    for (p0, p1) in sides:
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) + 0.12
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        a.box((L, 0.08, 0.06), ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, z0 - 0.06), rot=(0, 0, ang), color=gold, bevel=0.015, mat=T)
    # 方井上沿的小斗拱（朝井心挑）
    for si, (p0, p1) in enumerate(sides):
        d = Vector((p1[0] - p0[0], p1[1] - p0[1], 0))
        nrm = Vector((-d.y, d.x, 0)).normalized()      # 朝里
        ang = math.atan2(nrm.y, nrm.x)
        _dg_line(a, (p0[0] + d.x * 0.06, p0[1] + d.y * 0.06), (p1[0] - d.x * 0.06, p1[1] - d.y * 0.06), z1 - 0.685 * 0.3 - 0.006 + 0.003 * (si % 2), ang, 0.44, 0.3, T)   # 相邻两面差 3 毫米：角上两攒的耍头交叉，底面不在一个平面
    # 八角井：边心距 a1；从方井上沿到八角的那一圈平面（朝下），四角是角蝉（彩画云纹）
    a1 = 1.06
    R1 = a1 / math.cos(math.pi / 8)
    oct_ = [(cx + R1 * math.cos(math.pi / 8 + k * math.pi / 4), cy + R1 * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)]
    ledge = []
    for k in range(8):
        pa, pb = oct_[k], oct_[(k + 1) % 8]
        mid = math.pi / 8 + k * math.pi / 4 + math.pi / 8     # 这条边中点的方向
        dirx, diry = math.cos(mid), math.sin(mid)
        if abs(dirx) > 0.99 or abs(diry) > 0.99:
            # 正边：投到方井边上
            if abs(dirx) > 0.99:
                qa, qb = (cx + math.copysign(hx, dirx), pa[1]), (cx + math.copysign(hx, dirx), pb[1])
            else:
                qa, qb = (pa[0], cy + math.copysign(hy, diry)), (pb[0], cy + math.copysign(hy, diry))
            poly = [qa, qb, pb, pa]
            ledge.append((poly, gd))
        else:
            # 斜边：和方井的角围成角蝉（五边形）
            corner = (cx + math.copysign(hx, dirx), cy + math.copysign(hy, diry))
            qa = (cx + math.copysign(hx, dirx), pa[1]) if abs(pa[1] - cy) < abs(pa[0] - cx) else (pa[0], cy + math.copysign(hy, diry))
            qb = (pb[0], cy + math.copysign(hy, diry)) if abs(pb[0] - cx) < abs(pb[1] - cy) else (cx + math.copysign(hx, dirx), pb[1])
            poly = [qa, corner, qb, pb, pa]
            xs_ = [p[0] for p in poly]
            ys_ = [p[1] for p in poly]
            bx0, bx1, by0, by1 = min(xs_), max(xs_), min(ys_), max(ys_)
            uv = [_pv('ceiling', 'panel_cloud', (p[0] - bx0) / (bx1 - bx0), (p[1] - by0) / (by1 - by0)) for p in poly]
            pts3 = [(p[0], p[1], z1) for p in poly]
            # 朝下：从下面看是逆时针（这几个点在上面看是逆时针，所以倒过来）
            F.setdefault(PC, []).append((list(reversed(pts3)), list(reversed(uv))))
    polys = []
    for (poly, col) in ledge:
        pts3 = [(p[0], p[1], z1) for p in poly]
        polys.append((list(reversed(pts3)), col))
    _bulk_polys(a, polys, T)
    # 八角井八面墙（朝里，连珠带）
    for k in range(8):
        pa, pb = oct_[k], oct_[(k + 1) % 8]
        p0v, p1v = Vector((pa[0], pa[1], z1 - 0.004)), Vector((pb[0], pb[1], z1 - 0.004))
        L = (p1v - p0v).length
        _pq(F, 'beam', 'scroll', p1v, (p0v - p1v).normalized(), Z, L, z2 - z1 + 0.012, 0.0, L / (_aspect('beam', 'scroll') * (z2 - z1)), part=PB)
        mid = math.pi / 8 + k * math.pi / 4 + math.pi / 8
        inward = mid + math.pi
        _dg_line(a, (pa[0] * 0.92 + cx * 0.08 + (pb[0] - pa[0]) * 0.12, pa[1] * 0.92 + cy * 0.08 + (pb[1] - pa[1]) * 0.12),
                 (pb[0] * 0.92 + cx * 0.08 - (pb[0] - pa[0]) * 0.12, pb[1] * 0.92 + cy * 0.08 - (pb[1] - pa[1]) * 0.12),
                 z2 - 0.685 * 0.26 - 0.006 + 0.003 * (k % 2), inward, 0.6, 0.26, T)
    # 八角到圆的那一圈（朝下，金）
    r2 = 0.86
    n = 32
    ring = []
    for k in range(n):
        ang0, ang1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        def octr(ang):
            # 八角形在这个方向上离中心多远
            m = (ang - math.pi / 8) % (math.pi / 4) - math.pi / 8
            return a1 / math.cos(m)
        pts = [(cx + octr(ang0) * math.cos(ang0), cy + octr(ang0) * math.sin(ang0), z2), (cx + octr(ang1) * math.cos(ang1), cy + octr(ang1) * math.sin(ang1), z2),
               (cx + r2 * math.cos(ang1), cy + r2 * math.sin(ang1), z2), (cx + r2 * math.cos(ang0), cy + r2 * math.sin(ang0), z2)]
        ring.append((list(reversed(pts)), gd if k % 2 else gold))
    _bulk_polys(a, ring, T)
    # 圆井壁（朝里，连珠）
    for k in range(n):
        ang0, ang1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        p0v = Vector((cx + r2 * math.cos(ang0), cy + r2 * math.sin(ang0), z2 - 0.004))
        p1v = Vector((cx + r2 * math.cos(ang1), cy + r2 * math.sin(ang1), z2 - 0.004))
        L = (p1v - p0v).length
        s0 = (k % 16) / 16          # 一圈两遍连珠，每段都在这一块贴图里（不越界）
        _pq(F, 'beam', 'pearl', p1v, (p0v - p1v).normalized(), Z, L, z3 - z2 + 0.012, s0, s0 + 1 / 16, part=PB)
    for k in range(16):
        ang = 2 * math.pi * (k + 0.5) / 16
        _dg_set(a, cx + (r2 - 0.01) * math.cos(ang), cy + (r2 - 0.01) * math.sin(ang), z3 - 0.685 * 0.24 - 0.003, ang + math.pi,
                _BLU if k % 2 else _GRN, _GRN if k % 2 else _BLU, T, 0.24, fat=1.5, tail=0.05, lite=True)
    # 穹顶：圆井顶到正中最高 7.0，画着宝相花（按俯视投影取贴图）
    rings = 7
    dome = []
    def dz(r):
        return z3 + (H_ZJ_TOP - z3) * (1 - (r / r2) ** 2) ** 0.5
    for i in range(rings):
        ra, rb = r2 * (1 - i / rings), r2 * (1 - (i + 1) / rings)
        for k in range(n):
            ang0, ang1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
            P = [(ra, ang0), (ra, ang1), (rb, ang1), (rb, ang0)]
            pts = [(cx + r * math.cos(t_), cy + r * math.sin(t_), dz(r)) for (r, t_) in P]
            uv = [_pv('ceiling', 'zaojing', 0.5 + 0.49 * r / r2 * math.cos(t_), 0.5 + 0.49 * r / r2 * math.sin(t_)) for (r, t_) in P]
            if rb < 1e-6:
                pts, uv = pts[:3], uv[:3]
            F.setdefault(PC, []).append((list(reversed(pts)), list(reversed(uv))))
    # 正中倒垂的金莲和宝珠
    from props_hd import petal_ring
    sub = Asset('_lotus')
    petal_ring(sub, 12, 0.13, 0.0, 0.16, 0.08, 0.03, 30, gold, T, up=False, rng=rng)
    petal_ring(sub, 10, 0.08, -0.05, 0.12, 0.065, 0.028, 45, C('gold_dark'), T, up=False, rng=rng, phase=0.5)
    sub.lathe([(0.0, 0.05), (0.16, 0.04, gd), (0.14, -0.02, gold), (0.06, -0.08, gold), (0.0, -0.09)], segs=24, color=gold, mat=T)
    a.place(sub, (cx, cy, H_ZJ_TOP - 0.08))
    a.cyl(0.012, 0.16, (cx, cy, H_ZJ_TOP - 0.34), gd, segs=6, mat=T)
    a.lathe([(0.0, 0.0), (0.05, 0.01, gd), (0.09, 0.07, C('white')), (0.1, 0.12, C('white')), (0.085, 0.17, C('white')), (0.05, 0.2, gold), (0.03, 0.22, gd), (0.0, 0.23)],
            (cx, cy, H_ZJ_TOP - 0.56), segs=20, color=C('white'), mat=T)


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
