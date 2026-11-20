"""建筑：大殿、牌坊、钟亭、码头、小船。每个模型的原点在它自己的地面中心，-y 是正面（朝南，朝着镜头）。
大殿 2026-11-17 改成能走进去；2026-11-19 重做成面阔九间的重檐庑殿大殿（室内约 985 平米，hall() 前面的注释有尺寸）。"""
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


# ═══════════════════ 大殿（2026-11-19 重做：面阔九间、进深五间带前廊，重檐庑殿顶；室内 40.9 × 24.1 米 ≈ 985 平米，净高 12.5 米）═══════════════════
# 用户的要求：进大殿的面积放大十倍，要有宏伟的佛像，门口一直开着。不是把老殿整体放大：瓦、砖、格心、斗拱还是人的尺度（只是更多），
# 柱、梁、屋顶按大殿的比例加粗加高。
# Blender 本地坐标：x 向右、y 往里（北）、z 向上，原点在台基地面中心；Unity 里放在 HallAt = (0, 0, 27.1)，世界 z = 27.1 + y。
# 室内的东西（地面、护墙、壁画、梁、天花、藻井、金柱）部件名都以 in_ 开头（材质还是 toon、slab、paint_beam……），
# Unity 那边只在殿里画、换一套环境光更暗的材质。交接说明（每根柱子的位置、门洞、佛坛的位置……）：tools/blender/out_v2/HALL_V2.md
H_PW, H_PD, H_PH = 46.0, 32.4, 1.05         # 台基宽、深、高（前沿还在世界 z 10.9，后沿 43.3）
H_XS = [-20.8, -17.6, -14.4, -10.5, -3.5, 3.5, 10.5, 14.4, 17.6, 20.8]   # 面阔九间：明间、两次间各 7 米（三尊佛各对一间），梢间 3.9，尽间 3.2 × 2
H_FY, H_WY, H_BY = -13.8, -10.6, 14.0       # 前廊柱、门墙（中线）、后墙（柱中线）
H_SY = [-10.6, -5.68, -0.76, 4.16, 9.08, 14.0]   # 两山墙上的柱子：进深五间，每间 4.92
H_CH = 7.0                                  # 檐柱高（柱顶 8.05）
H_CR = 0.34                                 # 檐柱半径
H_FLOOR = 1.07                              # 室内金砖地面的顶
H_IN = (20.44, -10.46, 13.64)               # 墙体内皮（护墙面）：|x| ≤ 20.44，-10.46 ≤ y ≤ 13.64
H_STEP = 0.9                                # 室内墙面在斗拱上面往里收这么多（外面看就是上层檐的板壁）
H_LEDGE = 9.02                              # 下层墙顶（斗拱上面那一圈平板的底）
H_UX, H_UY0, H_UY1 = 19.54, -9.56, 12.74    # 上层室内墙面
H_JUN = 13.0                                # 峻脚（天花四周的斜板）从上层墙面这个高度起
H_CEIL = 13.57                              # 天花支条的底（室内净高 12.5）
H_PANEL = 13.63                             # 天花板面
H_FLAT = (18.97, -8.99, 12.17)              # 平顶天花：|x| ≤ 18.97，-8.99 ≤ y ≤ 12.17
H_BEAM0 = 12.75                             # 天花梁底（东西向的两根；南北向的六根底在 12.85）
H_BEAM_T = 0.6                              # 天花梁宽
H_ROWS = (-5.68, 9.08)                      # 东西向天花梁、前后两排金柱（世界 z 21.42、36.18）
H_JIN = ([(sx * x, y) for y in H_ROWS for x in (3.5, 10.5) for sx in (-1, 1)] +
         [(sx * 14.4, y) for y in H_SY[1:5] for sx in (-1, 1)])     # 十六根金柱：中轴线和三尊佛的正前方都没有柱子
H_JIN_R = 0.42
H_ZJ = (3.2, -1.5, 4.9)                     # 藻井方口：|x| ≤ 3.2，-1.5 ≤ y ≤ 4.9（中心 (0, 1.7)，世界 z 28.8）
H_ZJ_TOP = 16.2
H_SCREEN = (-10.5, 10.5, 9.08, 0.5)         # 扇面墙（三尊佛背后的那道墙，金柱之间）：x0、x1、中线 y、厚
H_ROOF_YC = 0.1                             # 屋顶中心（前廊柱和后檐柱的正中）
H_DOORS = (3, 4, 5)                         # 开着门的三间（H_XS 里第几间）
H_DOOR_SILL = 1.10                          # 三间门的门槛顶（比室内地面高 3 厘米，人直接走过去）
H_DOOR_TOP = 5.95                           # 门洞的高（中槛底）
H_LEAF_OPEN = 88.0                          # 门扇往里开的角度
H_EAVE_OUT = 3.2                            # 下檐出檐（从檐柱中线算）
H_UW, H_UD = 19.95, 13.05                   # 上层板壁外皮的半宽、半深（中心 y = H_ROOF_YC）
H_UP_OUT = 3.3                              # 上檐出檐
H_UP_K = 1.335                              # 上檐两山的坡比前后陡多少（推山）：正脊半长 = 23.25 - 16.35 / 1.335 = 11.0

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


def _roof_h(W, D, H, z, lift, x, y, yc=0.0, curve=2.2, k=1.0):
    """kit.roof 的屋面高度（同一个公式），用来算屋檐下面还有多少空。k 是 kit.roof 的 end_k（两山比前后陡多少）"""
    y = y - yc
    dmax = min(W, D)
    d = min((W - abs(x)) * k, D - abs(y))
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


# ── 大殿放大以后省面的几样（2026-11-19）──
def _orient(pts, want):
    """把一个面的点排成法线朝 want 的顺序"""
    p = [Vector(q) for q in pts]
    n = Vector((0, 0, 0))
    for i in range(1, len(p) - 1):
        n += (p[i] - p[0]).cross(p[i + 1] - p[0])
    return [tuple(q) for q in (p if n.dot(Vector(want)) >= 0 else reversed(p))]


def _bulk_tiles(a, x0, x1, y0, y1, nx_, ny_, z, colors, rng, mat, gap=0.012, drop=0.014, v=0.03, jit=0.0015):
    """一片方砖一次放进去：每块一个顶面、四条往砖缝里斜下去的窄边（不做侧面和底面，看不见）。
    殿里两千多块金砖、台面六百多块方砖，一块十个三角形"""
    t = new_bm()
    col = t.loops.layers.float_color['col']
    w, d = (x1 - x0) / nx_, (y1 - y0) / ny_
    b = gap * 0.8
    for i in range(nx_):
        for j in range(ny_):
            ax, ay, bx, by = x0 + w * i + gap / 2, y0 + d * j + gap / 2, x0 + w * (i + 1) - gap / 2, y0 + d * (j + 1) - gap / 2
            zz = z + (rng.uniform(-jit, jit) if jit else 0.0)
            hi = [t.verts.new(p) for p in ((ax + b, ay + b, zz), (bx - b, ay + b, zz), (bx - b, by - b, zz), (ax + b, by - b, zz))]
            lo = [t.verts.new(p) for p in ((ax, ay, z - drop), (bx, ay, z - drop), (bx, by, z - drop), (ax, by, z - drop))]
            c = vary(rng.choice(colors), rng, v, 0.015)
            ce = tint(c, -0.1)
            f = t.faces.new(hi)
            for l in f.loops:
                l[col] = (c[0], c[1], c[2], 0.0)
            for k in range(4):
                k2 = (k + 1) % 4
                f = t.faces.new((lo[k], lo[k2], hi[k2], hi[k]))
                for l in f.loops:
                    cc = c if l.vert in hi else ce
                    l[col] = (cc[0], cc[1], cc[2], 0.0)
    a.merge(t, mat)
    return nx_ * ny_


def _bulk_bars(a, bars, mat='toon'):
    """很多贴在一个面上的细木条（格心、横披的棂条）：每根只做正面和两个长侧面（背面贴着窗纸、两头插在框里，看不见）。
    bars: [(起点, 终点, 朝外的法线, 凸出多少, 宽, 颜色)]，起点终点在贴着的那个面上"""
    t = new_bm()
    col = t.loops.layers.float_color['col']
    for (p0, p1, n, dep, wid, color) in bars:
        p0, p1, n = Vector(p0), Vector(p1), Vector(n)
        d = (p1 - p0).normalized()
        s = n.cross(d) * (wid / 2)
        bq = [p0 - s, p1 - s, p1 + s, p0 + s]
        fq = [q + n * dep for q in bq]
        side_c = tint(color, -0.06)
        for (pts, want, cc) in (((fq[0], fq[1], fq[2], fq[3]), n, color), ((bq[0], bq[1], fq[1], fq[0]), -s, side_c),
                                ((bq[3], fq[3], fq[2], bq[2]), s, side_c)):
            f = t.faces.new([t.verts.new(q) for q in _orient(pts, want)])
            for l in f.loops:
                l[col] = (cc[0], cc[1], cc[2], 0.0)
    a.merge(t, mat)


def _col(a, x, y, z0, z1, r, rng, pre='', segs=24, petals=16, hoops=True, band_z=None, plinth=True):
    """大殿的朱漆柱（2026-11-19，比 _column 省面：一根一千多个三角形）：方石墩、覆盆上一圈雕出来的覆莲瓣、微收分的柱身、
    两道金箍、上面一圈青底金色缠枝（贴图带）。尺寸都跟着半径 r 走；petals=0 不要莲瓣，hoops=False 不要金箍和缠枝（嵌在墙里的柱子）"""
    st, sl, sd = C('stone'), C('stone_lit'), C('stone_dark')
    if pre:
        sl, st = mix(C('stone_lit'), hexc('#7f8f86'), 0.5), mix(C('stone'), hexc('#6f7d76'), 0.45)
    S = 'stone' if not pre else 'stone:' + pre + 'stone'
    T = 'toon' if not pre else 'toon:' + pre + 'toon'
    L = 'lacquer' if not pre else 'lacquer:' + pre + 'lacquer'
    PBm = 'paint_beam' if not pre else 'paint_beam:' + pre + 'paint_beam'
    zb = z0
    if plinth:
        a.box((r * 3.2, r * 3.2, 0.1), (x, y, z0 + 0.002), color=sd, bevel=0.02, top=st, mat=S)
        zb = z0 + 0.1
    hp = 0.2 * (r / 0.34) ** 0.5                       # 覆盆高
    r0, r1, r2 = r * 1.5, r * 1.36, r + 0.03
    a.lathe([(r0, zb), (r0 + 0.008, zb + hp * 0.2), (r1, zb + hp * 0.7), (r2, zb + hp), (r * 0.9, zb + hp)],
            (x, y, 0), segs=segs, color=sl, mat=S, outward=True)
    if petals:
        # 覆莲瓣：贴着覆盆雕出来的一圈宝装莲瓣，每瓣八个面（中间鼓起一道脊，两肩圆、瓣尖朝下朝外），瓣挨着瓣
        prof_ = [(r0, 0.0), (r0 + 0.008, 0.2), (r1, 0.7), (r2, 1.0)]

        def rho(t_):
            for (ra_, ta_), (rb_, tb_) in zip(prof_, prof_[1:]):
                if t_ <= tb_:
                    return ra_ + (rb_ - ra_) * (t_ - ta_) / (tb_ - ta_)
            return r2
        da = 2 * math.pi / petals
        tp = new_bm()
        pcol = tp.loops.layers.float_color['col']
        for i in range(petals):
            ang = da * (i + 0.5)
            c = vary(sl, rng, 0.025, 0.015)
            c_rim, c_tip = tint(c, -0.1), tint(c, -0.15)

            def P(t_, off, dang=0.0):
                rr_ = rho(t_) + off
                return (x + rr_ * math.cos(ang + dang), y + rr_ * math.sin(ang + dang), zb + hp * t_)
            vR = tp.verts.new(P(0.5, 0.06))
            rim = [tp.verts.new(q) for q in (P(0.985, 0.012), P(0.8, 0.02, -da * 0.3), P(0.45, 0.03, -da * 0.47), P(0.17, 0.032, -da * 0.3), P(0.04, 0.045),
                                              P(0.17, 0.032, da * 0.3), P(0.45, 0.03, da * 0.47), P(0.8, 0.02, da * 0.3))]
            out = Vector((math.cos(ang), math.sin(ang), 0.4))
            for q in range(8):
                tri = [vR, rim[q], rim[(q + 1) % 8]]
                if (tri[1].co - tri[0].co).cross(tri[2].co - tri[0].co).dot(out) < 0:
                    tri.reverse()
                f = tp.faces.new(tri)
                for l in f.loops:
                    # 瓣心亮、瓣边暗、瓣尖最暗；点是共用的，明暗是圆的（雕出来的莲瓣，不是一颗颗多面的石子）
                    cc = tint(c, 0.03) if l.vert is vR else (c_tip if l.vert in (rim[3], rim[4], rim[5]) else c_rim)
                    l[pcol] = (cc[0], cc[1], cc[2], 0.0)
        a.merge(tp, S)
    red = C('red')
    zs = zb + hp - 0.005
    n = max(4, int(round((z1 - zs) / 1.0)))

    def shaft_r(zz):
        t_ = max(0.0, min(1.0, (zz - zs) / (z1 - zs)))
        return r * (1.0 - 0.07 * t_ ** 1.5)
    a.lathe([(shaft_r(zs + (z1 - zs) * i / n), zs + (z1 - zs) * i / n) for i in range(n + 1)], (x, y, 0), segs=segs, color=red, mat=L, outward=True)
    if not hoops:
        return
    kh = (r / 0.2) ** 0.5
    gold, gd = C('gold'), C('gold_dark')
    zh = band_z if band_z is not None else z1 - 0.9
    for zz in (zs + 0.22 * kh, zh):
        rr = min(shaft_r(zz), shaft_r(zz + 0.07 * kh)) - 0.003
        a.lathe([(rr, 0), (rr + 0.014, 0.012 * kh, gd), (rr + 0.02, 0.035 * kh, gold), (rr + 0.014, 0.058 * kh, gd), (rr, 0.07 * kh)],
                (x, y, zz), segs=segs, color=gold, mat=T, outward=True)
    # 缠枝纹带：金箍上面一圈
    zb_ = zh + 0.09 * kh
    hb_ = 0.3 * kh
    rb = shaft_r(zb_) + 0.004
    # 贴图一段大约 2:1，绕柱子几遍（要能整除段数，每段的贴图坐标才不越界）
    nrep = min([d_ for d_ in (2, 3, 4, 6, 8) if segs % d_ == 0], key=lambda d_: abs(d_ - 2 * math.pi * rb / (hb_ * 2.0)))
    faces, lip = [], []
    for kk in range(segs):
        a0, a1 = 2 * math.pi * kk / segs, 2 * math.pi * (kk + 1) / segs
        u0, u1 = (kk * nrep / segs) % 1.0, (kk * nrep / segs) % 1.0 + nrep / segs
        p0_ = (x + rb * math.cos(a0), y + rb * math.sin(a0))
        p1_ = (x + rb * math.cos(a1), y + rb * math.sin(a1))
        faces.append(([(p0_[0], p0_[1], zb_), (p1_[0], p1_[1], zb_), (p1_[0], p1_[1], zb_ + hb_), (p0_[0], p0_[1], zb_ + hb_)],
                      [_pv('beam', 'colband', u0, 0), _pv('beam', 'colband', min(1.0, u1), 0), _pv('beam', 'colband', min(1.0, u1), 1), _pv('beam', 'colband', u0, 1)]))
        ri = rb - 0.012
        for (zz, up) in ((zb_, False), (zb_ + hb_, True)):
            q = [(x + rb * math.cos(a1), y + rb * math.sin(a1), zz), (x + rb * math.cos(a0), y + rb * math.sin(a0), zz),
                 (x + ri * math.cos(a0), y + ri * math.sin(a0), zz), (x + ri * math.cos(a1), y + ri * math.sin(a1), zz)]
            lip.append((_orient(q, (0, 0, 1 if up else -1)), gd))
    a.uvfaces(faces, PBm, weld=True)
    _bulk_polys(a, lip, T)


def _gexin2(s, x0, z0, w, h, glow=False, pitch=0.085, faces=(-1, 1), studs=(-1,)):
    """双交四椀的格心（省面的做法）：中间一层窗纸，要棂条的那几面各一层斜交的棂条（每根三个面），studs 那几面的交点上一朵小四瓣花"""
    if glow:
        s.box((w, 0.006, h), (x0 + w / 2, 0, z0), color=C('paper'), bevel=0, mat='glow', glow=1.0)
    else:
        s.box((w, 0.006, h), (x0 + w / 2, 0, z0), color=_PAPER, bevel=0, mat='toon')
    bar = 0.014
    lat = C('lattice')
    stud = tint(lat, 0.12)
    sq = math.sqrt(2)
    cs = []
    c = -h - w
    while c < w + h:
        cs.append(c)
        c += pitch * sq
    bars, pol = [], []
    for f in faces:
        for sg in (1, -1):
            # 两个方向的棂条交叉处正面在同一平面上会抢着显示：反方向那一组多凸出 1.5 毫米，看着像压在上面
            dep = 0.02 + (0.0015 if sg < 0 else 0.0)
            d = (1 / sq, sg / sq)
            for c in cs:
                seg = _seg_in_rect((c, 0.0), d, w, h)
                if seg is None or seg[1] - seg[0] < 0.02:
                    continue
                ta, tb = seg
                bars.append(((x0 + c + d[0] * ta, f * 0.003, z0 + d[1] * ta), (x0 + c + d[0] * tb, f * 0.003, z0 + d[1] * tb), (0, f, 0), dep, bar, lat))
        if f in studs:
            ys = f * (0.003 + 0.0215 + 0.003)
            for c1 in cs:          # x - z = c1
                for c2 in cs:      # x + z = c2
                    x, z = (c1 + c2) / 2, (c2 - c1) / 2
                    if 0.012 < x < w - 0.012 and 0.012 < z < h - 0.012:
                        r = 0.011
                        pts = [(x0 + x - r, ys, z0 + z), (x0 + x, ys, z0 + z - r), (x0 + x + r, ys, z0 + z), (x0 + x, ys, z0 + z + r)]
                        pol.append((_orient(pts, (0, f, 0)), stud))
    _bulk_bars(s, bars, 'toon')
    if pol:
        _bulk_polys(s, pol, 'toon')


def _leaf2(lw, lh, kind='door', glow=False, faces=(-1, 1), studs=(-1,)):
    """大殿的一扇格扇（kind='door'，五抹：绦环板、裙板、绦环板、格心、绦环板）或槛窗（'window'）。
    本地坐标：x 从门轴那边 0 到 lw，z 从 0 到 lh，厚度沿 y 居中。faces：哪几面看得见（-1 是 -y 面）——开着叠在一起的门扇，
    夹在里面的那几面不做棂条和花饰。门扇高了一倍，裙板、绦环板、棂条还是原来的大小，高出来的都是格心"""
    s = Asset('_leaf')
    red, redd, redl = C('red'), C('red_dark'), C('red_lit')
    gold, gd = C('gold'), C('gold_dark')
    T, st, rh = 0.075, 0.07, 0.06
    bv = 0.006 if kind == 'door' else 0.0      # 窗扇的横档不倒角（省面）
    for x in (st / 2, lw - st / 2):
        s.box((st, T, lh), (x, 0, 0), color=redd, bevel=0.008, mat='lacquer')
    if kind == 'door':
        z1, z2, z3 = rh + 0.26, rh + 0.26 + rh + 1.0, rh + 0.26 + rh + 1.0 + rh + 0.26
        zones = [(rh, z1, 'tao'), (z1 + rh, z2, 'qun'), (z2 + rh, z3, 'tao'), (z3 + rh, lh - 0.26 - 2 * rh, 'gexin'), (lh - 0.26 - rh, lh - rh, 'tao')]
    else:
        zones = [(rh, rh + 0.2, 'tao'), (2 * rh + 0.2, lh - 0.2 - 2 * rh, 'gexin'), (lh - 0.2 - rh, lh - rh, 'tao')]
    for z in sorted({0.0, lh - rh} | {zb for (_, zb, _) in zones[:-1]}):
        s.box((lw - 2 * st + 0.004, T * 0.92, rh), (lw / 2, 0, z), color=redd, bevel=bv, mat='lacquer')
    iw = lw - 2 * st
    for (za, zb, k) in zones:
        hh = zb - za
        if k == 'gexin':
            # 高的格心中间加一道腰串（横档），格心分成上下两截，不然五米高的一片棂条太单薄
            if hh > 2.2:
                zm = za + hh * 0.5
                s.box((iw + 0.004, T * 0.8, 0.045), (lw / 2, 0, zm - 0.0225), color=redd, bevel=0.005, mat='lacquer')
                _gexin2(s, st, za, iw, zm - 0.0225 - za, glow=glow, faces=faces, studs=studs)
                _gexin2(s, st, zm + 0.0225, iw, zb - zm - 0.0225, glow=glow, faces=faces, studs=studs)
            else:
                _gexin2(s, st, za, iw, hh, glow=glow, faces=faces, studs=studs)
            continue
        s.box((iw, 0.026, hh), (lw / 2, 0, za), color=red, bevel=0.0, mat='lacquer')
        s.box((iw - 0.07, 0.036, hh - 0.06), (lw / 2, 0, za + 0.03), color=redl, bevel=0.012 if kind == 'door' else 0.0, mat='lacquer')
        for f in faces:
            if k == 'qun':
                _ruyi(s, lw / 2, za + hh / 2, iw * 0.8, f, gold)
                # 裙板四角各一个小金卷、中间一圈金线
                for (u, v) in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                    s.blob(0.014, (lw / 2 + u * (iw / 2 - 0.07), f * 0.02, za + hh / 2 + v * (hh / 2 - 0.07)), (1, 0.4, 1), gd, subdiv=0, bump=0.0)
            else:
                s.blob(1.0, (lw / 2, f * 0.02, za + hh / 2), (iw * 0.16, 0.006, hh * 0.22), gold, subdiv=0 if kind == 'window' else 1, bump=0.0)
    # 看叶：四个角上的铜饰（L 形）
    for f in faces:
        for (u, v) in ((0, 0), (1, 0), (0, 1), (1, 1)):
            x = 0.04 if u == 0 else lw - 0.04
            z = 0.04 if v == 0 else lh - 0.04
            s.box((0.09, 0.005, 0.02), (x + (0.022 if u == 0 else -0.022), f * (T / 2 + 0.0015), z), color=gold, bevel=0.0, base=False)
            s.box((0.02, 0.005, 0.09), (x, f * (T / 2 + 0.0035), z + (0.022 if v == 0 else -0.022)), color=gold, bevel=0.0, base=False)
    return s


def _transom2(a, x0, x1, y, z0, z1, step=0.12):
    """横披窗（省面的做法）：窗纸（夜里亮，暖黄）和两面的斜方格棂条，朝外那面的交点上一朵小金花。框由调用的地方做"""
    w, h = x1 - x0, z1 - z0
    a.box((w, 0.006, h), ((x0 + x1) / 2, y, z0), color=C('paper_warm'), bevel=0, mat='glow', glow=1.0)
    lat, gold = C('lattice'), C('gold')
    bars, pol = [], []
    for f in (-1, 1):
        for sg in (-1, 1):
            dep = 0.022 + (0.0015 if sg < 0 else 0.0)
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
                if len(pts) < 2 or math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1]) < 0.02:
                    continue
                (ax, az), (bx, bz) = pts[0], pts[-1]
                bars.append(((ax, y + f * 0.003, az), (bx, y + f * 0.003, bz), (0, f, 0), dep, 0.016, lat))
        if f < 0:
            ys = y - 0.03
            for i in range(int(w / step) + 1):
                for j in range(int(h / step) + 1):
                    xx, zz = x0 + (i + 0.5) * step, z0 + (j + 0.5 * (i % 2)) * step
                    if x0 + 0.03 < xx < x1 - 0.03 and z0 + 0.03 < zz < z1 - 0.03 and (i + j) % 2 == 0:
                        r = 0.016
                        pol.append((_orient([(xx - r, ys, zz), (xx, ys, zz - r), (xx + r, ys, zz), (xx, ys, zz + r)], (0, -1, 0)), gold))
    _bulk_bars(a, bars, 'toon')
    _bulk_polys(a, pol, 'toon')


def _dougong_far(a, x, y, z, ang, s=1.0, ca=None, cb=None, mat='toon', wan=0.86):
    """离得远的一攒斗拱（上层檐下的，人最近也在十几米外）：坐斗、正心瓜栱、万栱、一根往外挑的昂、耍头，一攒一百来个三角形"""
    sub = Asset('_dgf')
    ca = ca or _BLU
    cb = cb or _GRN
    t = 0.1
    _dou(sub, 0, 0, 0, 0.10, 0.15, 0.14, cb, mat)
    _vp(sub, _gong_poly(0.62, 0.12, k=1), t, 'u', 0.0, 0.10, ca, mat)
    _vp(sub, _gong_poly(wan, 0.12, k=1), t, 'u', 0.0, 0.30, cb, mat)
    _vp(sub, _gong_poly(wan * 0.8, 0.12, k=1), t, 'u', 0.30, 0.302, ca, mat)
    _vp(sub, [(-0.1, 0.0), (0.5, 0.0), (0.74, -0.12), (0.79, -0.1), (0.62, 0.12), (-0.1, 0.16)], t, 'v', 0.0, 0.14, ca, mat)
    _vp(sub, [(-0.1, 0.0), (0.6, 0.0), (0.66, 0.05), (0.62, 0.12), (-0.1, 0.12)], t, 'v', 0.0, 0.464, cb, mat)
    a.place(sub, (x, y, z), (0, 0, ang - math.pi / 2), s)


def _dg_stations(stations, step):
    """一行斗拱的位置：每根柱头上一攒（柱头科），两柱之间按 step 均分（平身科）。返回 (位置列表, 最小的攒距)"""
    out, gap = [], 1e9
    for i in range(len(stations) - 1):
        w = stations[i + 1] - stations[i]
        n = max(1, int(round(w / step)))
        gap = min(gap, w / n)
        out += [stations[i] + w * k / n for k in range(n)]
    out.append(stations[-1])
    return out, gap


def _rafters2(a, W, D, H, z, lift, yc, d_from, step=0.297, r=0.05, thick=0.16, k=1.0):
    """檐下一根根的椽子（省面的做法：四棱的，椽头一片青、一点金）。从斗拱外头伸到檐口，贴着屋檐底"""
    col = C('red_dark')
    polys = []
    for (L, f) in ((W, lambda u, d: (u, yc - D + d)), (W, lambda u, d: (u, yc + D - d)),
                   (D, lambda u, d: (W - d, yc + u)), (D, lambda u, d: (-W + d, yc + u))):
        n = int(2 * L / step)
        for i in range(1, n):
            u = -L + 2 * L * i / n
            d0 = min(d_from, L - abs(u) - 0.15)
            if d0 < 0.5:
                continue
            p = []
            for d in (d0, 0.07):
                x, y = f(u, d)
                p.append(Vector((x, y, _roof_h(W, D, H, z, lift, x, y, yc, k=k) - thick - r - 0.008)))
            dv = (p[1] - p[0]).normalized()
            sd_ = dv.cross(Vector((0, 0, 1))).normalized() * r
            dn = Vector((0, 0, -r))
            # 椽身：底面和两个侧面（顶面贴着望板，看不见）
            for (o1, o2, want) in ((sd_ + dn, -sd_ + dn, (0, 0, -1)), (sd_ * 1.0 - dn * 0.6, sd_ + dn, sd_), (-sd_ + dn, -sd_ - dn * 0.6, -sd_)):
                polys.append((_orient([p[0] + o1, p[0] + o2, p[1] + o2, p[1] + o1], want), col))
            # 椽头：一片青、中间一点金
            e = p[1]
            polys.append((_orient([e + sd_ + dn, e - sd_ + dn, e - sd_ - dn * 0.6, e + sd_ - dn * 0.6], dv), _BLU))
            g = e + dv * 0.004 + dn * 0.2
            q = r * 0.42
            polys.append((_orient([g + sd_.normalized() * q, g + Vector((0, 0, q)), g - sd_.normalized() * q, g - Vector((0, 0, q))], dv), C('gold')))
    _bulk_polys(a, polys, 'toon')


def _beast(a, p, ang, s=1.0, col=None, mat='toon'):
    """脊上的一只小兽（走兽）：蹲着的身子、往前探的头。ang 是它朝哪边（朝檐角）"""
    col = col or C('ridge_lit')
    sub = Asset('_bst')
    sub.lathe([(0.0, 0.0), (0.11, 0.0), (0.13, 0.08), (0.085, 0.2), (0.1, 0.29), (0.07, 0.39), (0.0, 0.43)], segs=6, color=col, mat=mat, squash=(1.25, 0.8))
    sub.box((0.16, 0.09, 0.09), (0.1, 0, 0.3), color=tint(col, 0.06), bevel=0.02, mat=mat)
    a.place(sub, p, (0, 0, ang), s)


def _chiwen(a, x, y, z, sx, s=1.0, mat='toon'):
    """正吻：正脊两头张口吞脊的龙头，尾巴往上往里卷，背上一把剑把。sx 是这一头朝外的方向（+1 东、-1 西）"""
    rc, rl = C('ridge'), C('ridge_lit')
    gold = C('gold')
    # 侧面的轮廓（u 朝外、v 朝上，逆时针）：嘴咬着脊（朝里），背在外，尾巴在上面往里卷
    prof = [(-0.62, 0.0), (0.5, 0.0), (0.66, 0.45), (0.68, 1.0), (0.56, 1.5), (0.3, 1.9), (-0.05, 2.08), (-0.4, 2.02), (-0.58, 1.8),
            (-0.5, 1.58), (-0.32, 1.62), (-0.14, 1.72), (0.06, 1.6), (0.14, 1.3), (0.02, 1.08), (-0.25, 1.0), (-0.56, 1.04), (-0.74, 0.86),
            (-0.5, 0.72), (-0.3, 0.6), (-0.52, 0.46), (-0.72, 0.36)]
    sub = Asset('_cw')
    sub.prism(prof, -0.19, 0.19, rc, bevel=0.035, mat=mat, top=rl, rot=(math.pi / 2, 0, 0))
    # 两面凸起的卷纹（腮、鳞），一只金眼
    for f in (-1, 1):
        yy = f * 0.2
        for (cu, cv, rr, turns) in ((0.2, 0.55, 0.2, 1.2), (0.3, 1.25, 0.16, 1.1), (-0.2, 1.84, 0.12, 1.0)):
            pts = [(cu + rr * (1 - k / 14) * math.cos(k / 14 * turns * 2 * math.pi), yy, cv + rr * (1 - k / 14) * math.sin(k / 14 * turns * 2 * math.pi)) for k in range(12)]
            sub.tube(pts, 0.03, rl, segs=4, mat=mat)
        sub.blob(0.06, (-0.3, yy, 0.86), (1, 0.5, 1), gold, subdiv=1, bump=0.0, mat=mat)
    # 剑把
    sub.box((0.1, 0.1, 0.5), (0.42, 0, 1.6), rot=(0, math.radians(18), 0), color=rl, bevel=0.02, mat=mat)
    sub.box((0.22, 0.14, 0.08), (0.5, 0, 2.05), rot=(0, math.radians(18), 0), color=gold, bevel=0.02, mat=mat)
    a.place(sub, (x, y, z), (0, 0, 0 if sx > 0 else math.pi), s)


def _hip_ridge(a, pts, r0, r1, tip, beasts=5, bs=1.0, mat='toon'):
    """一条戗脊（角脊）：沿 pts 的一根脊，梢头往外往上翘，靠檐角那一段蹲一排小兽，最前头一个骑凤仙人（高一点）"""
    rc = C('ridge')
    pts = [Vector(p) for p in pts]
    n = len(pts)
    rad = [r0 + (r1 - r0) * i / (n - 1) for i in range(n)]
    d = (pts[-1] - pts[-2])
    d.z = 0
    d.normalize()
    e = pts[-1]
    pts2 = pts + [e + d * tip * 0.5 + Vector((0, 0, tip * 0.2)), e + d * tip * 0.9 + Vector((0, 0, tip * 0.55))]
    rad2 = rad + [r1 * 0.75, r1 * 0.4]
    a.tube(pts2, rad2, rc, segs=8, mat=mat)
    ang = math.atan2(d.y, d.x)
    for q in range(beasts):
        k = 1.0 - (q + 0.6) / (beasts + 1.5) * 0.62
        i = min(n - 2, int(k * (n - 1)))
        u = k * (n - 1) - i
        p = pts[i].lerp(pts[i + 1], u)
        rr = rad[i] + (rad[i + 1] - rad[i]) * u
        _beast(a, (p.x, p.y, p.z + rr * 0.8), ang, bs * (1.25 if q == 0 else 1.0), C('gold_dark') if q == 0 else C('ridge_lit'), mat)
    return pts2[-2]


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
    FY, WY, BY = H_FY, H_WY, H_BY
    XW = xs[-1]
    CR = H_CR
    top = PH + H_CH                         # 檐柱顶 8.05
    X, Y0, Y1 = H_IN
    yc = H_ROOF_YC
    ZS = PH + 0.03                          # 台面方砖的顶
    Z = Vector((0, 0, 1))

    def lbox(p0, p1, t, z0, h, color, mat='toon', bevel=0.0, **kw):
        """沿 p0→p1 的一根方木（中线在这条线上）"""
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        a.box((L, t, h), ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, z0), rot=(0, 0, math.atan2(p1[1] - p0[1], p1[0] - p0[0])), color=color, bevel=bevel, mat=mat, **kw)

    # ═════════ 台基：须弥座的做法（圭角、下枋、束腰、上枭、上枋），高 1.05 ═════════
    # 最下一层往地下多埋 0.9 米：殿后离湖岸近的地方地面往下斜，台座不能悬空
    a.box((PW + 0.3, PD + 0.3, 1.06), (0, 0, -0.9), color=sd, bevel=0.04, mat='stone')
    a.box((PW + 0.18, PD + 0.18, 0.18), (0, 0, 0.14), color=sl, bevel=0.03, segs=2, mat='stone')
    a.box((PW, PD, 0.62), (0, 0, 0.30), color=st, bevel=0.0, grad=(tint(st, -0.06), st), mat='brick')
    a.box((PW + 0.1, PD + 0.1, 0.08), (0, 0, 0.88), color=st, bevel=0.03, mat='stone')
    a.box((PW + 0.2, PD + 0.2, 0.11), (0, 0, 0.94), color=sl, bevel=0.035, segs=2, top=C('slab_c'), mat='stone')
    SW = 8.2                                # 台阶半宽（正对三间门：明间和左右次间）
    # 束腰上砌石的缝（两层错缝）
    seam = tint(sd, -0.06)
    seams = []
    for (x0, y0, x1, y1) in ((-PW / 2, -PD / 2, PW / 2, -PD / 2), (-PW / 2, -PD / 2, -PW / 2, PD / 2), (PW / 2, -PD / 2, PW / 2, PD / 2), (-PW / 2, PD / 2, PW / 2, PD / 2)):
        L = math.hypot(x1 - x0, y1 - y0)
        ang = math.atan2(y1 - y0, x1 - x0)
        front = abs(y1 - y0) < 1e-6 and y0 < 0
        if abs(y1 - y0) < 1e-6:
            nx, ny = (0, -1) if y0 < 0 else (0, 1)
        else:
            nx, ny = (-1, 0) if x0 < 0 else (1, 0)
        if front:
            for sx in (-1, 1):
                seams.append(((sx * (PW / 2 + SW + 0.5) / 2, y0 + ny * 0.004, 0.61), (PW / 2 - SW - 0.5, 0.016, 0.02), 0.0, 0.0, seam))
        else:
            seams.append((((x0 + x1) / 2 + nx * 0.004, (y0 + y1) / 2 + ny * 0.004, 0.61), (L, 0.016, 0.02), ang, 0.0, seam))
        n = int(L / 1.15)
        for row, (z0, zh) in enumerate(((0.32, 0.28), (0.62, 0.26))):
            for i in range(n):
                k = (i + (0.5 if row else 0.0)) / n
                if front and abs(x0 + (x1 - x0) * k) < SW + 0.55:
                    continue
                seams.append(((x0 + (x1 - x0) * k + nx * 0.004, y0 + (y1 - y0) * k + ny * 0.004, z0 + zh / 2), (0.02, 0.016, zh), ang, 0.0, seam))
    _bulk_boxes(a, seams, 'toon')
    # 台面铺方砖（屋外的四块：前廊和廊前、两侧、后面；屋里另铺金砖）
    slab_c = [C('slab'), C('slab_b'), C('slab_c')]
    ex, ey = PW / 2 - 0.3, PD / 2 - 0.3
    n_slab = _bulk_tiles(a, -ex, ex, -ey, WY - 0.27, 57, 6, ZS, slab_c, rng, 'slab', gap=0.018, drop=0.026)
    n_slab += _bulk_tiles(a, -ex, -(XW + 0.25), WY - 0.27, ey, 2, 32, ZS, slab_c, rng, 'slab', gap=0.018, drop=0.026)
    n_slab += _bulk_tiles(a, XW + 0.25, ex, WY - 0.27, ey, 2, 32, ZS, slab_c, rng, 'slab', gap=0.018, drop=0.026)
    n_slab += _bulk_tiles(a, -(XW + 0.25), XW + 0.25, BY + 0.25, ey, 50, 2, ZS, slab_c, rng, 'slab', gap=0.018, drop=0.026)
    # 台阶：七级（六个踏面，最上一步踏上台面），总高 1.08，每级高 0.154、踏面 0.27；前沿到世界 z 9.18（石台北沿 9.2）
    NSTEP, TREAD = 6, 0.27
    rise = ZS / (NSTEP + 1)
    yfr = -PD / 2 - 0.1                     # 台基上枋的正面
    for k in range(NSTEP):
        d = TREAD * (NSTEP - k)
        a.box((2 * SW, d + 0.06, rise), (0, yfr - d / 2 + 0.03, k * rise), color=tint(st, 0.012 * k), bevel=0.02, top=sl, mat='stone')
    run = TREAD * NSTEP
    for sx in (-1, 1):
        xg = sx * (SW + 0.24)
        # 垂带：两边斜着的条石，下面一块三角的象眼，脚下一个石墩
        a.prism([(yfr - run, 0.0), (yfr + 0.02, 0.0), (yfr + 0.02, ZS - 0.06)], -0.21, 0.21, st, mat='stone', loc=(xg, 0, 0), rot=(math.pi / 2, 0, math.pi / 2))
        a.box((0.48, math.hypot(run, ZS) + 0.12, 0.16), (xg, yfr - run / 2, ZS / 2 + 0.05), rot=(math.atan2(ZS, run), 0, 0), color=sl, bevel=0.035, base=False, mat='stone')
        a.box((0.5, 0.5, 0.62), (xg, yfr - run - 0.2, 0), color=st, bevel=0.05, top=sl, mat='stone')
        a.lathe([(0.12, 0), (0.2, 0.04), (0.21, 0.14), (0.1, 0.24), (0.0, 0.27)], (xg, yfr - run - 0.2, 0.62), segs=10, color=sl, mat='stone')
    # 栏杆：台基四周一圈，正面在台阶那里断开
    hx, hy = PW / 2 - 0.16, PD / 2 - 0.16
    _rail(a, (-hx, -hy), (-(SW + 0.55), -hy), PH, post_every=1.7)
    _rail(a, (SW + 0.55, -hy), (hx, -hy), PH, post_every=1.7)
    _rail(a, (-hx, -hy), (-hx, hy), PH, post_every=1.7, ends=False)
    _rail(a, (hx, -hy), (hx, hy), PH, post_every=1.7, ends=False)
    _rail(a, (-hx, hy), (hx, hy), PH, post_every=1.7)

    mark('台基')
    # ═════════ 柱子 ═════════
    # 前廊柱十根、门墙上十根（门两边的四根做足，窗间的省一点）、两山和后墙嵌在墙里的十六根（只露一小半）
    cols_out = []
    for x in xs:
        _col(a, x, FY, ZS - 0.002, top, CR, rng, band_z=6.3)
        cols_out.append((x, FY, CR, '前廊柱'))
    for i, x in enumerate(xs):
        full = 3 <= i <= 6
        _col(a, x, WY, ZS - 0.002, top, CR, rng, segs=24 if full else 16, petals=16 if full else 0, hoops=full, band_z=6.3)
        cols_out.append((x, WY, CR, '门墙柱'))
    for sx in (-1, 1):
        for y in H_SY[1:]:
            _col(a, sx * XW, y, PH, top, CR, rng, segs=16, petals=0, hoops=False)
            cols_out.append((sx * XW, y, CR, '山墙柱（嵌在墙里）'))
    for x in xs[1:-1]:
        _col(a, x, BY, PH, top, CR, rng, segs=16, petals=0, hoops=False)
        cols_out.append((x, BY, CR, '后墙柱（嵌在墙里）'))
    for (x, y) in H_JIN:
        _col(a, x, y, H_FLOOR - 0.002, H_PANEL - 0.01, H_JIN_R, rng, pre='in_', band_z=11.3)

    mark('柱子')
    # ═════════ 墙：两山和后墙，红墙、下面一截青砖的下碱；柱子露出墙面 10 厘米 ═════════
    WTOP = top - 0.72                       # 额枋底 7.33
    for (p0, p1, out) in (((-XW, WY - 0.3), (-XW, BY + 0.24), (-1, 0)), ((XW, WY - 0.3), (XW, BY + 0.24), (1, 0)), ((-XW + 0.3, BY), (XW - 0.3, BY), (0, 1))):
        o = Vector((out[0], out[1], 0))
        q0, q1 = Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0))
        lbox(q0 - o * 0.03, q1 - o * 0.03, 0.54, PH, 1.3, C('wall_dark'), 'brick', bevel=0.02, top=sl)
        lbox(q0 - o * 0.06, q1 - o * 0.06, 0.48, PH + 1.3, WTOP - PH - 1.3 + 0.02, C('wall_red'), 'plaster', grad=(tint(C('wall_red'), -0.12), C('wall_red')))

    mark('墙')
    # ═════════ 正面九间：中间三间格扇门（朝里大开、叠在门框里侧），两边各三间槛窗 ═════════
    lean = []                               # 开着的门扇叠起来占的地方：给 Unity 加碰撞
    doors_out = []
    ZT0, ZT1 = H_DOOR_TOP + 0.2, WTOP - 0.2   # 横披窗 6.15 .. 7.13
    for i in range(9):
        x0, x1 = xs[i] + CR - 0.03, xs[i + 1] - CR + 0.03     # 抱框外皮（伸进柱子 3 厘米）
        ox0, ox1 = x0 + 0.15, x1 - 0.15                       # 抱框内皮：门洞
        w, ow = x1 - x0, ox1 - ox0
        cx = (x0 + x1) / 2
        door = i in H_DOORS
        zj = ZS if door else PH + 1.37
        for xx in (x0 + 0.075, x1 - 0.075):
            a.box((0.15, 0.26, WTOP - zj), (xx, WY, zj), color=redd, bevel=0.012, mat='lacquer')
        # 中槛、横披（7 米的开间用两根间柱分成三扇）、上槛
        a.box((ow, 0.22, 0.2), (cx, WY, H_DOOR_TOP), color=redd, bevel=0.014, mat='lacquer')
        a.box((ow, 0.22, 0.2), (cx, WY, ZT1), color=redd, bevel=0.014, mat='lacquer')
        nt = 3 if ow > 5 else 1
        for k in range(nt):
            ta, tb = ox0 + ow * k / nt + (0.05 if k else 0.0), ox0 + ow * (k + 1) / nt - (0.05 if k < nt - 1 else 0.0)
            _transom2(a, ta, tb, WY, ZT0, ZT1)
            if k:
                a.box((0.1, 0.2, ZT1 - ZT0), (ox0 + ow * k / nt, WY, ZT0), color=redd, bevel=0.01, mat='lacquer')
        if door:
            # 门槛石（青石，和殿里的金砖地一样高）上面一道 3 厘米高的木门槛：人直接走过去
            a.box((ow, Y0 - 0.002 - (WY - 0.27), 0.07), (cx, (Y0 - 0.002 + WY - 0.27) / 2, H_FLOOR - 0.07), color=sd, bevel=0.0, top=st, mat='stone')
            a.box((ow, 0.2, H_DOOR_SILL - H_FLOOR), (cx, WY, H_FLOOR), color=redd, bevel=0.01, top=redl, mat='lacquer')
            # 门簪：中槛外面四颗六角的木钉，钉头一朵金花
            for u in (-0.36, -0.13, 0.13, 0.36):
                px = cx + u * ow
                a.lathe([(0.0, 0.0), (0.085, 0.0), (0.085, 0.14), (0.0, 0.14)], (px, WY - 0.11, H_DOOR_TOP + 0.1), segs=6, color=red, rot=(math.pi / 2, 0, 0), mat='lacquer')
                a.lathe([(0.0, 0.0), (0.066, 0.0, gd), (0.06, 0.014, gold), (0.024, 0.024), (0.0, 0.026)], (px, WY - 0.25, H_DOOR_TOP + 0.1), segs=12, color=gold, rot=(math.pi / 2, 0, 0))
            # 六扇格扇：左右各三扇，朝里开到 88°，像屏风一样叠在门框里侧（A 挨着门框，B 折回来，C 再折出去）
            lw = ow / 6
            z0 = H_DOOR_SILL + 0.015
            lh = H_DOOR_TOP - z0 - 0.01
            for side in (-1, 1):
                H0 = Vector((ox0 + 0.045 if side < 0 else ox1 - 0.045, WY + 0.17, 0))
                th = math.radians(H_LEAF_OPEN) if side < 0 else math.radians(180 - H_LEAF_OPEN)
                dA = Vector((math.cos(th), math.sin(th), 0))
                nA = Vector((dA.y, -dA.x, 0)) if side < 0 else Vector((-dA.y, dA.x, 0))   # 指向门洞中间
                # 本地 +y 面在世界里朝 -x：西边那一叠 A 的 +y 面朝门框（看得见），C 的 -y 面朝门洞；东边反过来
                fa, fc = ((1,), (-1,)) if side < 0 else ((-1,), (1,))
                a.place(_leaf2(lw, lh, 'door', faces=fa, studs=fa), (H0.x, H0.y, z0), (0, 0, th))
                E = H0 + dA * lw
                Eb = E + nA * 0.09
                a.place(_leaf2(lw, lh, 'door', faces=(), studs=()), (Eb.x, Eb.y, z0), (0, 0, th + math.pi))
                Cb = H0 + nA * 0.18
                a.place(_leaf2(lw, lh, 'door', faces=fc, studs=fc), (Cb.x, Cb.y, z0), (0, 0, th))
                # 合页、门轴、门枕
                for (hp_, off) in ((E, 0.045), (H0, 0.135)):
                    hj = hp_ + nA * off
                    for zz in (0.4, lh / 2, lh - 0.5):
                        a.cyl(0.014, 0.13, (hj.x, hj.y, z0 + zz), gd, segs=6, top=gold)
                a.cyl(0.03, 0.06, (H0.x, H0.y, z0 - 0.045), C('bronze_dark'), segs=8)
                a.cyl(0.06, 0.035, (H0.x, H0.y, H_DOOR_TOP - 0.04), C('bronze'), segs=10, top=C('bronze_lit'))
                a.box((0.2, 0.22, 0.045), (H0.x + (0.03 if side < 0 else -0.03), H0.y + 0.03, H_FLOOR - 0.003), color=sd, bevel=0.012, top=st, mat='stone')
                pts = [H0 - nA * 0.045, E - nA * 0.045, E + nA * 0.225, H0 + nA * 0.225]
                lean.append((i, side, [(round(p.x, 3), round(p.y, 3)) for p in pts], round(z0, 3), round(z0 + lh, 3)))
            doors_out.append((i, ox0 + 0.045 + 0.225 + 0.02, ox1 - 0.045 - 0.225 - 0.02, ox0, ox1))
        else:
            # 槛墙（青砖）、风槛、槛窗（关着，窗纸夜里亮）
            a.box((w, 0.5, 1.29), (cx, WY, PH - 0.01), color=C('wall_dark'), bevel=0.02, top=sl, mat='brick')
            a.box((w, 0.26, 0.09), (cx, WY, PH + 1.28), color=redd, bevel=0.01, mat='lacquer')
            # 槛墙外面一圈凸起的石线（海棠池的边）
            for (ua, ub, za, zb_) in ((0.2, w - 0.2, PH + 0.22, PH + 0.27), (0.2, w - 0.2, PH + 1.03, PH + 1.08), (0.2, 0.25, PH + 0.27, PH + 1.03), (w - 0.25, w - 0.2, PH + 0.27, PH + 1.03)):
                a.box((ub - ua, 0.02, zb_ - za), (x0 + (ua + ub) / 2, WY - 0.255, za), color=sl, bevel=0.0, mat='stone')
            nl = 4 if ow > 3 else 3
            lw = ow / nl
            for k in range(nl):
                a.place(_leaf2(lw, H_DOOR_TOP - (PH + 1.375) - 0.005, 'window', glow=True), (ox0 + lw * k, WY, PH + 1.375))

    mark('门窗')
    # ═════════ 檐下：额枋（彩画）、平板枋、斗拱、拱垫板、挑檐枋、前廊天花 ═════════
    LW, LD, LH, LLIFT = XW + H_EAVE_OUT, (BY - FY) / 2 + H_EAVE_OUT, 15.4, 1.3     # 下檐：半宽 24.0、半深 17.1
    RING = LW - H_UW                        # 下檐这一圈的进深 4.05（从檐口到上层板壁）
    ez = top + 0.2                          # 下檐檐口 8.25
    THK = 0.16

    def soffit(x, y):
        return _roof_h(LW, LD, LH, ez, LLIFT, x, y, yc) - THK
    bx = [v - xs[0] + 0.34 for v in xs]                       # 分间（离西头的距离）
    _xuanzi_beam(a, F, (xs[0] - 0.34, FY), (XW + 0.34, FY), WTOP, top, 0.5, bx, 'xuanzi_a', 'paint_beam')
    _xuanzi_beam(a, F, (xs[0] - 0.34, BY), (XW + 0.34, BY), WTOP, top, 0.46, bx, 'xuanzi_a', 'paint_beam', faces=(0, 1))
    _xuanzi_beam(a, F, (xs[0] + 0.21, WY - 0.02), (XW - 0.21, WY - 0.02), WTOP, top, 0.28, [v - xs[0] - 0.21 for v in xs], 'xuanzi_b', 'paint_beam', faces=(1, 0))
    ya, yb_ = FY + 0.251, BY - 0.231
    ys_all = [FY] + H_SY
    for sx in (-1, 1):
        p0, p1 = (sx * XW, ya), (sx * XW, yb_)
        brk = [y - ya for y in ys_all if ya < y < yb_]
        if sx < 0:
            p0, p1 = p1, p0
            brk = [yb_ - y for y in ys_all if ya < y < yb_]
        _xuanzi_beam(a, F, p0, p1, WTOP, top, 0.44, brk, 'xuanzi_b', 'paint_beam', faces=(1, 1))
    # 抱头梁：前廊柱和门墙柱之间一间一根（彩画）
    for x in xs[1:-1]:
        _xuanzi_beam(a, F, (x, FY + 0.251), (x, WY - 0.201), top - 0.5, top - 0.004, 0.36, [], 'xuanzi_b', 'paint_beam')
    # 平板枋：前后两道通长，两山的夹在中间
    for (p0, p1, t) in (((-XW - 0.5, FY), (XW + 0.5, FY), 0.56), ((-XW - 0.5, BY), (XW + 0.5, BY), 0.52),
                        ((-XW, FY + 0.281), (-XW, BY - 0.261), 0.5), ((XW, FY + 0.281), (XW, BY - 0.261), 0.5)):
        lbox(p0, p1, t, top, 0.12, _BLU_D, bevel=0.012, top=gd)
    zt = top + 0.12
    # 拱垫板：斗拱后面一整圈红板，从平板枋一直到屋檐底下
    lbox((-XW, FY), (XW, FY), 0.06, zt, soffit(0, FY) - 0.03 - zt, redd)
    lbox((-XW, BY), (XW, BY), 0.06, zt, soffit(0, BY) - 0.03 - zt, redd)
    for sx in (-1, 1):
        lbox((sx * XW, FY + 0.031), (sx * XW, BY - 0.031), 0.06, zt, soffit(XW, 0) - 0.03 - zt, redd)
    # 斗拱：柱头上各一攒，柱间按 0.92 米一攒排（明间、次间各八攒）。正面做足，两山和后面用省一点的
    s_dg = 1.3
    stx, gapx = _dg_stations(xs, 0.92)
    sty, gapy = _dg_stations(ys_all, 0.92)
    n_dg = 0
    for k, x in enumerate(stx[1:-1]):
        ca, cb = (_BLU, _GRN) if k % 2 == 0 else (_GRN, _BLU)
        _dougong(a, x, FY, zt, -math.pi / 2, s_dg, ca, cb, inner=0.15, wan=min(0.86, (gapx - 0.02) / s_dg))
        _dougong_far(a, x, BY, zt, math.pi / 2, s_dg, ca, cb, wan=min(0.86, (gapx - 0.02) / s_dg))      # 殿后的：省面的
        n_dg += 2
    for sx in (-1, 1):
        for k, y in enumerate(sty[1:-1]):
            ca, cb = (_BLU, _GRN) if k % 2 == 0 else (_GRN, _BLU)
            _dougong(a, sx * XW, y, zt, 0 if sx > 0 else math.pi, s_dg, ca, cb, inner=0.1, lite=True, gold=False, wan=min(0.86, (gapy - 0.02) / s_dg))
            n_dg += 1
        # 四个角：一攒斜着出的角科
        for (y, sy) in ((FY, -1), (BY, 1)):
            _dougong(a, sx * XW, y, zt, math.atan2(sy, sx), s_dg, _GRN, _BLU, inner=0.1, lite=True, wan=0.5)
            n_dg += 1
    # 挑檐枋：斗拱外头一圈连起来的木枋
    o = 0.62 * s_dg
    zf = zt + 0.42 * s_dg
    for (p0, p1) in (((-XW - o - 0.05, FY - o), (XW + o + 0.05, FY - o)), ((-XW - o - 0.05, BY + o), (XW + o + 0.05, BY + o)),
                     ((-XW - o, FY - o + 0.051), (-XW - o, BY + o - 0.051)), ((XW + o, FY - o + 0.051), (XW + o, BY + o - 0.051))):
        lbox(p0, p1, 0.1, zf, 0.15, _BLU_D, bevel=0.012, top=_GRN)
    # 前廊天花：一格格天花板（彩画），支条绿色
    pz = top + 0.5
    a.box((2 * XW, WY - FY - 0.1, 0.08), (0, (FY + WY) / 2, pz + 0.065), color=_GRN_D, bevel=0.0)
    npx, npy = 52, 4
    gx = [-XW + 2 * XW * k / npx for k in range(npx + 1)]
    gy = [FY + 0.05 + (WY - FY - 0.1) * k / npy for k in range(npy + 1)]
    for i in range(npx):
        for j in range(npy):
            _pq(F, 'ceiling', 'panel_lotus' if (i + j) % 2 == 0 else 'panel_wheel', (gx[i], gy[j], pz + 0.06), (0, 1, 0), (1, 0, 0), gy[1] - gy[0], gx[1] - gx[0], part='paint_ceiling')
    ribs = []
    for xx in gx:
        ribs.append(((xx, (FY + WY) / 2, pz + 0.03), (0.07, WY - FY - 0.1, 0.06), 0.0, 0.0, _GRN))
    for yy in gy:
        ribs.append(((0, yy, pz + 0.031), (2 * XW, 0.07, 0.06), 0.0, 0.0, _GRN))
    _bulk_boxes(a, ribs, 'toon')

    mark('檐下')
    # ═════════ 下檐屋顶（一圈 4.05 米深的瓦面）、椽子、四条角脊、围脊 ═════════
    a.roof(LW, LD, LH, z=ez, loc=(0, yc), lift=LLIFT, inner=RING, pitch=0.38, course=0.42, thick=THK, ridge_r=0.2, caps=gold,
           tile_segs=3, tile_rings=2, cap_segs=6, cap_r=0.066)
    _rafters2(a, LW, LD, LH, ez, LLIFT, yc, H_EAVE_OUT - o - 0.08, thick=THK)
    bell_pts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            pts = []
            for k in range(9):
                u = k / 8
                x_, y_ = sx * (H_UW - 0.1 + (LW - H_UW + 0.1) * u), yc + sy * (H_UD - 0.1 + (LD - H_UD + 0.1) * u)
                pts.append((x_, y_, _roof_h(LW, LD, LH, ez, LLIFT, x_, y_, yc) + 0.1))
            bell_pts.append(_hip_ridge(a, pts, 0.22, 0.16, 0.6, beasts=5, bs=0.95))
    # 围脊：下檐瓦面顶着上层板壁的地方一圈脊
    zr0 = _roof_h(LW, LD, LH, ez, LLIFT, H_UW, yc, yc)
    for (p0, p1, e) in (((-H_UW, yc - H_UD), (H_UW, yc - H_UD), 0.3), ((-H_UW, yc + H_UD), (H_UW, yc + H_UD), 0.3),
                        ((-H_UW, yc - H_UD), (-H_UW, yc + H_UD), -0.301), ((H_UW, yc - H_UD), (H_UW, yc + H_UD), -0.301)):
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        c_ = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
        a.box((L + 2 * e, 0.6, 0.5), (c_[0], c_[1], zr0 - 0.12), rot=(0, 0, ang), color=C('ridge'), bevel=0.04, top=C('ridge_lit'))
        a.box((L + 2 * e + 0.1, 0.72, 0.1), (c_[0], c_[1], zr0 + 0.36), rot=(0, 0, ang), color=C('ridge_lit'), bevel=0.03)

    mark('下檐')
    # ═════════ 上层：四面板壁、一间一扇高窗、彩画檐枋、斗拱 ═════════
    UW, UD = H_UW, H_UD
    UWr, UDr, UH, ULIFT = UW + H_UP_OUT, UD + H_UP_OUT, 9.6, 1.5
    uz0 = zr0 - 0.3                              # 板壁底（藏在下檐瓦面和围脊下面）
    uz_brk = zr0 + 2.3                           # 上层斗拱底
    UZ = uz_brk + 0.2                            # 上檐檐口

    def usoffit(x, y):
        return _roof_h(UWr, UDr, UH, UZ, ULIFT, x, y, yc, k=H_UP_K) - THK
    wtop = min(usoffit(UW, yc), usoffit(0, yc - UD)) - 0.03
    sides4 = (((-UW, yc - UD), (UW, yc - UD)), ((-UW, yc + UD), (UW, yc + UD)), ((-UW, yc - UD), (-UW, yc + UD)), ((UW, yc - UD), (UW, yc + UD)))
    for (p0, p1) in sides4:
        side = abs(p0[0] - p1[0]) < 1e-6
        L0 = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        cxw, cyw = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        nrm = Vector((math.copysign(1, cxw), 0, 0)) if side else Vector((0, math.copysign(1, cyw - yc), 0))
        # 前后两面的板壁通长，两侧的夹在中间（角上叠着的顶面、底面一样高，会闪）
        a.box((L0 if not side else L0 - 0.36, 0.18, wtop - uz0), (cxw - nrm.x * 0.09, cyw - nrm.y * 0.09, uz0), rot=(0, 0, ang), color=red, bevel=0.0, grad=(redd, red), mat='lacquer')
        # 平板枋
        a.box((L0 + 0.3 if not side else L0 - 0.3, 0.3, 0.1), (cxw, cyw, uz_brk - 0.1), rot=(0, 0, ang), color=_BLU_D, bevel=0.012, top=gd)
    # 檐枋：旋子彩画（朝外那一面）
    ubx = [v + UW for v in xs[1:-1] if abs(v) < UW]
    _xuanzi_beam(a, F, (-UW - 0.1, yc - UD), (UW + 0.1, yc - UD), uz_brk - 0.66, uz_brk - 0.1, 0.24, [b + 0.1 for b in ubx], 'xuanzi_a', 'paint_beam', faces=(1, 0))
    _xuanzi_beam(a, F, (-UW - 0.1, yc + UD), (UW + 0.1, yc + UD), uz_brk - 0.66, uz_brk - 0.1, 0.24, [b + 0.1 for b in ubx], 'xuanzi_a', 'paint_beam', faces=(0, 1))
    uy0, uy1 = yc - UD + 0.121, yc + UD - 0.121
    uby = [y - uy0 for y in H_SY[1:5]]
    _xuanzi_beam(a, F, (UW, uy0), (UW, uy1), uz_brk - 0.66, uz_brk - 0.1, 0.24, uby, 'xuanzi_b', 'paint_beam', faces=(1, 0))
    _xuanzi_beam(a, F, (-UW, uy1), (-UW, uy0), uz_brk - 0.66, uz_brk - 0.1, 0.24, [uy1 - uy0 - b for b in reversed(uby)], 'xuanzi_b', 'paint_beam', faces=(1, 0))
    # 高窗：正面八扇（正中挂匾）、后面九扇、两侧各五扇；窗下一道金线
    zw = uz0 + 0.95

    def uwin(x, y, rz, w_):
        # 一扇高窗：会亮的窗纸、木框、两根间柱、斜方格的棂条（离得远，棂条稀一点、每根三个面）
        sub = Asset('_ul')
        hh = 0.8
        sub.box((w_, 0.03, hh), (0, 0.02, 0), color=C('paper_warm'), bevel=0, mat='glow', glow=1.0)
        bar = C('lattice')
        for xx in (-w_ / 2, w_ / 2):
            sub.box((0.06, 0.06, hh + 0.06), (xx, 0, -0.03), color=bar, bevel=0)
        for zz in (-0.03, hh - 0.03):
            sub.box((w_ - 0.06, 0.06, 0.06), (0, 0, zz), color=bar, bevel=0)
        bars = []
        nmul = max(2, int(round(w_ / 0.8)))
        for q in range(1, nmul):
            bars.append(((-w_ / 2 + w_ * q / nmul, 0.005, 0.03), (-w_ / 2 + w_ * q / nmul, 0.005, hh - 0.03), (0, -1, 0), 0.03, 0.04, bar))
        sq = math.sqrt(2)
        c = -hh - w_
        while c < w_ + hh:
            for sg in (1, -1):
                seg = _seg_in_rect((c, 0.0), (1 / sq, sg / sq), w_, hh)
                if seg is not None and seg[1] - seg[0] > 0.04:
                    bars.append(((-w_ / 2 + c + seg[0] / sq, 0.005, sg * seg[0] / sq), (-w_ / 2 + c + seg[1] / sq, 0.005, sg * seg[1] / sq), (0, -1, 0),
                                 0.022 + (0.002 if sg < 0 else 0.0), 0.022, bar))
            c += 0.2
        _bulk_bars(sub, bars, 'toon')
        a.place(sub, (x, y, zw), (0, 0, rz))
    for i in range(9):
        cxl = (max(xs[i], -UW) + min(xs[i + 1], UW)) / 2
        w_ = min(2.6, (min(xs[i + 1], UW) - max(xs[i], -UW)) - 0.9)
        if i != 4:
            uwin(cxl, yc - UD - 0.03, 0.0, w_)
        uwin(cxl, yc + UD + 0.03, math.pi, w_)
    for sx in (-1, 1):
        for k in range(5):
            uwin(sx * (UW + 0.03), (H_SY[k] + H_SY[k + 1]) / 2 * 0.92 + 0.1, math.pi / 2 if sx > 0 else -math.pi / 2, 2.4)
    for (p0, p1) in sides4:
        side = abs(p0[0] - p1[0]) < 1e-6
        nrm = Vector((math.copysign(1, p0[0]), 0, 0)) if side else Vector((0, math.copysign(1, p0[1] - yc), 0))
        q0, q1 = Vector((p0[0], p0[1], 0)) + nrm * 0.012, Vector((p1[0], p1[1], 0)) + nrm * 0.012
        if side:
            q0.y += 0.02
            q1.y -= 0.02
        lbox(q0, q1, 0.03, zw - 0.2, 0.05, gold)
    # 上层斗拱：离得远，用省面的
    s_up = 1.1
    ustx, ugx = _dg_stations([-UW] + [v for v in xs if abs(v) < UW - 0.5] + [UW], 0.95)
    usty, ugy = _dg_stations([yc - UD] + [v for v in H_SY if yc - UD + 0.5 < v < yc + UD - 0.5] + [yc + UD], 0.95)
    for k, x in enumerate(ustx[1:-1]):
        ca, cb = (_BLU, _GRN) if k % 2 == 0 else (_GRN, _BLU)
        _dougong_far(a, x, yc - UD, uz_brk, -math.pi / 2, s_up, ca, cb, wan=min(0.86, (ugx - 0.02) / s_up))
        _dougong_far(a, x, yc + UD, uz_brk, math.pi / 2, s_up, ca, cb, wan=min(0.86, (ugx - 0.02) / s_up))
    for sx in (-1, 1):
        for k, y in enumerate(usty[1:-1]):
            ca, cb = (_BLU, _GRN) if k % 2 == 0 else (_GRN, _BLU)
            _dougong_far(a, sx * UW, y, uz_brk, 0 if sx > 0 else math.pi, s_up, ca, cb, wan=min(0.86, (ugy - 0.02) / s_up))
        for sy in (-1, 1):
            _dougong_far(a, sx * UW, yc + sy * UD, uz_brk, math.atan2(sy, sx), s_up, _GRN, _BLU, wan=0.5)
    ou = 0.62 * s_up
    for (p0, p1) in (((-UW - ou - 0.05, yc - UD - ou), (UW + ou + 0.05, yc - UD - ou)), ((-UW - ou - 0.05, yc + UD + ou), (UW + ou + 0.05, yc + UD + ou)),
                     ((-UW - ou, yc - UD - ou + 0.051), (-UW - ou, yc + UD + ou - 0.051)), ((UW + ou, yc - UD - ou + 0.051), (UW + ou, yc + UD + ou - 0.051))):
        lbox(p0, p1, 0.1, uz_brk + 0.42 * s_up, 0.14, _BLU_D, bevel=0.012, top=_GRN)
    # 上檐：庑殿顶，两山推山（正脊长 22 米）。瓦离得远，每块省着做
    a.roof(UWr, UDr, UH, z=UZ, loc=(0, yc), lift=ULIFT, pitch=0.38, course=0.46, thick=THK, ridge_r=0.3, tip=0.8, caps=gold, bells=False,
           tile_segs=2, tile_rings=2, tile_cap=False, cap_segs=6, cap_r=0.066, beasts=False, main_ridge=False, end_k=H_UP_K)
    _rafters2(a, UWr, UDr, UH, UZ, ULIFT, yc, H_UP_OUT - ou - 0.08, thick=THK, k=H_UP_K)
    # 四条垂脊上的走兽（九只，最前头是骑凤仙人）
    RL = UWr - UDr / H_UP_K                      # 正脊半长 11.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            n_b = 9
            for q in range(n_b):
                u = 0.97 - q * 0.036
                x_, y_ = sx * (RL + (UWr - RL) * u), yc + sy * UDr * u
                zz = _roof_h(UWr, UDr, UH, UZ, ULIFT, x_, y_, yc, k=H_UP_K) + 0.06 + 0.3 * (1.0 - 0.25 * u) * 0.8
                _beast(a, (x_, y_, zz), math.atan2(sy * UDr, sx * (UWr - RL)), 1.5 if q == 0 else 1.2, gd if q == 0 else C('ridge_lit'))
            # 檐角的风铃
            x_, y_ = sx * (UWr + 0.45), yc + sy * (UDr + 0.45)
            bell_pts.append(Vector((x_, y_, _roof_h(UWr, UDr, UH, UZ, ULIFT, sx * UWr, yc + sy * UDr, yc, k=H_UP_K) + 0.2)))
    for bp in bell_pts:
        a.cyl(0.012, 0.3, (bp.x, bp.y, bp.z - 0.42), C('rope_dark'), segs=4)
        a.lathe([(0.0, 0.0), (0.1, 0.0, gd), (0.09, 0.08, gold), (0.055, 0.17, gold), (0.0, 0.2)], (bp.x, bp.y, bp.z - 0.62), segs=8, color=gold)
    # 正脊：三层（当沟、通脊、扣脊筒瓦），脊身两面一排金色的团花；两头正吻
    rz = UZ + UH
    rc, rl = C('ridge'), C('ridge_lit')
    a.box((2 * RL + 0.6, 0.7, 0.3), (0, yc, rz - 0.16), color=rc, bevel=0.05, mat='toon')
    a.box((2 * RL + 0.2, 0.42, 0.62), (0, yc, rz + 0.12), color=rc, bevel=0.03, top=rl, mat='toon')
    a.tube([(-RL - 0.1, yc, rz + 0.78), (RL + 0.1, yc, rz + 0.78)], 0.16, rl, segs=8)
    nfl = 15
    for i in range(nfl):
        x_ = -RL + 1.4 + (2 * RL - 2.8) * i / (nfl - 1)
        for f in (-1, 1):
            a.lathe([(0.0, 0.0), (0.17, 0.0, gd), (0.15, 0.03, gold), (0.06, 0.06), (0.0, 0.065)], (x_, yc + f * 0.2, rz + 0.44), segs=8, color=gold, rot=(-f * math.pi / 2, 0, 0))
    for sx in (-1, 1):
        _chiwen(a, sx * (RL + 0.05), yc, rz - 0.1, sx, 1.25)
    # 正脊正中的宝顶
    a.lathe([(0.0, 0), (0.3, 0.04), (0.36, 0.22), (0.18, 0.38), (0.3, 0.62), (0.22, 0.86), (0.08, 1.02), (0.0, 1.28)], (0, yc, rz + 0.9), segs=16, color=gold)

    mark('上层')
    # ═════════ 匾：蓝底金字「大雄寶殿」，挂在上下两层檐之间的正中 ═════════
    _plaque(a, (0, yc - UD - 0.46, uz0 + 1.62), 2.3)
    # ═════════ 楹联：明间两根前廊柱上 ═════════
    _couplet(a, (3.5, FY - CR - 0.012, PH + 3.55), '慈雲廣被', 1.9)      # 上联在右（东）
    _couplet(a, (-3.5, FY - CR - 0.012, PH + 3.55), '慧日長明', 1.9)     # 下联在左（西）
    # 檐下的红灯笼：两边六间各一盏，挂绳一直接到檐底（中间三间不挂：不挡从院子里看佛像的视线）
    for i in (0, 1, 2, 6, 7, 8):
        xl = (xs[i] + xs[i + 1]) / 2
        yl = FY - 1.3
        zl = top + 0.1
        _hang_lantern(a, xl, yl, zl, 1.7)
        a.cyl(0.014, soffit(xl, yl) + 0.05 - zl, (xl, yl, zl), C('rope_dark'), segs=5)

    mark('匾联灯')
    # ═════════ 室内 ═════════
    info = _interior(a, F, rng)

    mark('室内')
    # 手绘贴图的面一起放进去
    for part, faces in F.items():
        a.uvfaces(faces, part, weld=True)
    mark('彩画面')
    print('[yjm] hall 三角形：' + '，'.join(f'{k} {v - p_:,}' for (k, v), p_ in zip(tri_log, [0] + [v for _, v in tri_log[:-1]])))
    print(f'[yjm] hall 台面方砖 {n_slab} 块，下檐斗拱 {n_dg} 攒')
    for e in lean:
        print('[yjm] hall 开着的门扇', e)
    for e in doors_out:
        print('[yjm] hall 门洞（第几间, 净空 x0, 净空 x1, 门框 x0, 门框 x1）', tuple(round(v, 3) if isinstance(v, float) else v for v in e))
    print('[yjm] hall 檐口：下檐', round(ez, 2), '上檐', round(UZ, 2), '正脊', round(rz + 0.94, 2), '上层板壁', round(uz0, 2), '..', round(wtop, 2))
    # 预览图：默认那张（和游戏里差不多的斜俯视）之外，再出正面、俯视、院子里、门口往里、室内仰视、柱础和门的近景
    lamps = [((0, -2, 9.5), 9000, 1.5), ((-13, 1, 8), 5000, 1.5), ((13, 1, 8), 5000, 1.5), ((0, 6, 6), 4000, 1.0)]
    shots = [
        {'name': 'front', 'pos': (0, -92, 13), 'look': (0, 0, 10.5), 'lens': 40},
        {'name': 'aerial', 'pos': (58, -70, 62), 'look': (0, -2, 6), 'lens': 40},
        {'name': 'court', 'pos': (4.0, -27.5, 1.9), 'look': (0, -6, 8.5), 'lens': 20, 'lamps': lamps},
        {'name': 'steps', 'pos': (-12, -20.5, 2.6), 'look': (-2, -11, 4.2), 'lens': 24, 'lamps': lamps},
        {'name': 'door_in', 'pos': (0, -12.6, 2.7), 'look': (0, 6, 6.0), 'lens': 18, 'lamps': lamps},
        {'name': 'in_wide', 'pos': (17.5, -8.6, 3.2), 'look': (-6, 6, 6.5), 'lens': 16, 'lamps': lamps},
        {'name': 'in_ceiling', 'pos': (0.0, -4.5, 2.7), 'look': (0, 1.2, 14), 'lens': 16, 'lamps': lamps},
        {'name': 'in_back', 'pos': (0, 4.0, 2.7), 'look': (0, -10.6, 5.0), 'lens': 16, 'lamps': lamps},
        {'name': 'in_zaojing', 'pos': (1.2, -3.2, 2.7), 'look': (0, 1.7, 15.0), 'lens': 40, 'lamps': lamps + [((0, 1.7, 12.5), 2500, 1.0)]},
        {'name': 'in_rear_aisle', 'pos': (-17, 11.4, 2.7), 'look': (6, 11.4, 4.0), 'lens': 18, 'lamps': [((0, 11.4, 6), 4000, 1.0), ((-12, 11.4, 6), 3000, 1.0)]},
        {'name': 'col_base', 'pos': (5.6, -8.2, 2.1), 'look': (3.5, -5.68, 1.45), 'lens': 35, 'lamps': lamps},
        {'name': 'door_close', 'pos': (-7.2, -14.6, 2.9), 'look': (-4.4, -10.4, 2.9), 'lens': 24, 'lamps': lamps},
        {'name': 'porch', 'pos': (-19.5, -12.4, 2.7), 'look': (6, -12.2, 5.2), 'lens': 18},
        {'name': 'eave', 'pos': (31, -27, 5.5), 'look': (20.5, -14, 10.5), 'lens': 35},
        {'name': 'roof', 'pos': (30, -36, 30), 'look': (8, 0, 17), 'lens': 50},
        {'name': 'side', 'pos': (78, 4, 16), 'look': (0, 0, 10), 'lens': 40},
        {'name': 'back', 'pos': (-40, 62, 22), 'look': (0, 6, 8), 'lens': 35},
    ]
    tris = a.finish(view=(14, 34, 0.86), dist=2.2, shots=shots)
    hall.info = dict(info, lean=lean, doors=doors_out, cols_out=cols_out, parts=getattr(a, 'part_tris', []), tris=tris, tri_log=tri_log,
                     ez=ez, UZ=UZ, ridge=rz + 0.94, n_slab=n_slab, n_dg=n_dg, stairs=(SW, NSTEP + 1, ZS, yfr - run, yfr, rise, TREAD))
    _handoff(hall.info)
    return tris


def _plaque(a, c, scale=1.0):
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
    a.place(sub, c, (math.radians(14), 0, 0), scale)


def _couplet(a, c, text, scale=1.0):
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
    a.place(sub, c, (0, 0, 0), scale)


def _handoff(info):
    """把大殿的尺寸（柱位、门洞、部件三角形数……）存一份 hall_info.json，写交接说明、Unity 那边摆东西时照着它来。
    只在导到暂存目录（设了 YJ_OUT）时写"""
    import json
    from kit import OUT
    if not os.environ.get('YJ_OUT'):
        return

    def clean(v):
        if isinstance(v, Vector):
            return [round(c, 3) for c in v]
        if isinstance(v, float):
            return round(v, 4)
        if isinstance(v, (list, tuple)):
            return [clean(c) for c in v]
        if isinstance(v, dict):
            return {str(k): clean(c) for k, c in v.items()}
        return v
    with open(os.path.join(OUT, 'hall_info.json'), 'w', encoding='utf8') as f:
        json.dump(clean(info), f, ensure_ascii=False, indent=1)


def _interior(a, F, rng):
    """大殿里面：金砖地、两层的墙（下层墙裙、壁画、额枋、斗拱；上层流云、高窗、额枋）、峻脚、井口天花、天花梁、扇面墙、藻井。
    返回给交接说明用的尺寸"""
    X, Y0, Y1 = H_IN
    UX, UY0, UY1 = H_UX, H_UY0, H_UY1
    FL = H_FLOOR
    gold, gd = C('gold'), C('gold_dark')
    T = 'toon:in_toon'
    LQ = 'lacquer:in_lacquer'
    PB, PC, PW_ = 'paint_beam:in_paint_beam', 'paint_ceiling:in_paint_ceiling', 'paint_wall:in_paint_wall'
    Z = Vector((0, 0, 1))
    t_last = [_tris(a)]
    xs = H_XS

    def mark(label):
        t = _tris(a)
        print(f'[yjm] hall 室内 {label} {t - t_last[0]:,}')
        t_last[0] = t

    def lbox(p0, p1, t, z0, h, color, mat=T, bevel=0.0, **kw):
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        a.box((L, t, h), ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, z0), rot=(0, 0, math.atan2(p1[1] - p0[1], p1[0] - p0[0])), color=color, bevel=bevel, mat=mat, **kw)

    # ── 金砖地面：64 × 38 块（二尺金砖，0.64 米见方），顶面 1.07，砖缝 8 毫米 ──
    a.box((2 * X, Y1 - Y0, 0.006), (0, (Y0 + Y1) / 2, FL - 0.02), color=_GROUT, bevel=0.0, mat='slab:in_floor')
    # 颜色比老殿收了一半：一千平米的地面，块块深浅差得多了像棋盘
    jm = tuple(sum(c[i] for c in _JINZHUAN) / len(_JINZHUAN) for i in range(3))
    n_brick = _bulk_tiles(a, -X, X, Y0, Y1, 64, 38, FL, [mix(c, jm, 0.5) for c in _JINZHUAN], rng, 'slab:in_floor', gap=0.008, drop=0.012, v=0.014, jit=0.0)

    mark('地面')
    # ── 墙面：下层（到斗拱顶上 9.02）在墙体内皮；上层往里收 0.9 米，一直到峻脚 ──
    zl = H_LEDGE
    WB = H_PH + H_CH - 0.72                  # 额枋底 7.33
    for sx in (-1, 1):
        a.box((0.02, Y1 - Y0, zl - FL), (sx * (X + 0.01), (Y0 + Y1) / 2, FL), color=_WALL_RED, bevel=0.0, mat=T)
        a.box((0.02, UY1 - UY0, H_JUN + 0.03 - zl - 0.015), (sx * (UX + 0.01), (UY0 + UY1) / 2, zl + 0.015), color=_WALL_RED, bevel=0.0, mat=T)
        # 下层墙顶到上层墙脚的那一圈平板（朝下，斗拱顶着它）
        a.box((X + 0.02 - UX - 0.01, Y1 - Y0 + 0.04, 0.03), (sx * (X + 0.02 + UX + 0.01) / 2, (Y0 + Y1) / 2, zl), color=_GRN_D, bevel=0.0, mat=T)
    a.box((2 * X + 0.04, 0.02, zl - FL), (0, Y1 + 0.01, FL), color=_WALL_RED, bevel=0.0, mat=T)
    a.box((2 * X + 0.04, 0.02, zl - WB - 0.7), (0, Y0 - 0.01, WB + 0.7), color=_WALL_RED, bevel=0.0, mat=T)      # 前墙：额枋以上（以下是门窗）
    for (yy, ya_, yb_) in ((UY1 + 0.01, UY1 + 0.01, Y1 + 0.02), (UY0 - 0.01, Y0 - 0.02, UY0 - 0.01)):
        a.box((2 * UX + 0.04, 0.02, H_JUN + 0.03 - zl - 0.015), (0, yy, zl + 0.015), color=_WALL_RED, bevel=0.0, mat=T)
        a.box((2 * UX, yb_ - ya_, 0.03), (0, (ya_ + yb_) / 2, zl + 0.001), color=_GRN_D, bevel=0.0, mat=T)

    n_mural = [0]

    def wall_bay(p0, n, s0, s1, fd=0.04):
        """一间墙：踢脚、墙裙（彩画）、木线、一幅或两幅带框的壁画。p0 是这面墙从屋里看最左边的点，n 朝屋里，s 是沿墙的距离"""
        p0, n = Vector(p0), Vector(n)
        A = Z.cross(n)
        w = s1 - s0
        base = p0 + A * s0 + n * 0.002
        ang = math.atan2(A.y, A.x)
        mid = base + A * (w / 2)
        a.box((w, 0.04, 0.16), (mid.x + n.x * 0.018, mid.y + n.y * 0.018, FL), rot=(0, 0, ang), color=_INK, bevel=0.006, mat=T)
        _band_run(F, 'wall', 'dado_a' if n_mural[0] % 2 == 0 else 'dado_b', base + Vector((0, 0, FL + 0.16)), A, Z, w, 1.1, part=PW_)
        a.box((w, 0.045, 0.07), (mid.x + n.x * 0.0205, mid.y + n.y * 0.0205, FL + 1.26), rot=(0, 0, ang), color=C('red_deep'), bevel=0.008, top=gold, mat=LQ)
        nm = 2 if w > 5.5 else 1
        mw = min(3.5, w / nm - 0.7)
        mh = min(4.2, mw / 0.8525)
        fw = 0.1
        mz0 = 4.95 - mh / 2 - fw
        mz1 = 4.95 + mh / 2 + fw
        for m in range(nm):
            u0 = w * (m + 0.5) / nm - mw / 2 - fw
            fwid = mw + 2 * fw
            for (ua, ub, za, zb) in ((0, fwid, mz0, mz0 + fw), (0, fwid, mz1 - fw, mz1), (0, fw, mz0 + fw, mz1 - fw), (fwid - fw, fwid, mz0 + fw, mz1 - fw)):
                cc = base + A * (u0 + (ua + ub) / 2) + n * (fd / 2)
                a.box((ub - ua, fd, zb - za), (cc.x, cc.y, za), rot=(0, 0, ang), color=C('red_deep'), bevel=0.006, mat=LQ)
            g0, g1 = fw - 0.036, fw - 0.018
            for (ua, ub, za, zb) in ((g0, fwid - g0, mz0 + g0, mz0 + g1), (g0, fwid - g0, mz1 - g1, mz1 - g0),
                                     (g0, g1, mz0 + g0, mz1 - g0), (fwid - g1, fwid - g0, mz0 + g0, mz1 - g0)):
                cc = base + A * (u0 + (ua + ub) / 2) + n * (fd + 0.0025)
                a.box((ub - ua, 0.004, zb - za), (cc.x, cc.y, za), rot=(0, 0, ang), color=gold, bevel=0.0, mat=T)
            _pq(F, 'wall', f'mural_{(n_mural[0] * 5 + m * 7) % 12}', base + A * (u0 + fw) + Vector((0, 0, mz0 + fw)), A, Z, mw, mh, part=PW_)
        n_mural[0] += 1

    def segs_between(posts, lo, hi, half):
        cut = sorted(posts)
        edges = [lo] + [v for p in cut for v in (p - half, p + half)] + [hi]
        return [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2) if edges[i + 1] - edges[i] > 0.4]

    # 墙里的柱子在屋里露出一小半（壁柱）：两山各四根、后墙八根
    PR = 0.3
    pil = []
    sy_in = H_SY[1:5]
    for sx in (-1, 1):
        for y in sy_in:
            _col(a, sx * (X + 0.05), y, FL - 0.002, WB + 0.02, PR, rng, pre='in_', segs=16, petals=0, hoops=False)
            pil.append((sx * (X + 0.05), y))
    for x in xs[1:-1]:
        _col(a, x, Y1 + 0.05, FL - 0.002, WB + 0.02, PR, rng, pre='in_', segs=16, petals=0, hoops=False)
        pil.append((x, Y1 + 0.05))
    hb = PR - 0.02
    # 东墙（从屋里看左边是北头）、西墙、后墙
    for (s0, s1) in segs_between([Y1 - y for y in sy_in], 0.0, Y1 - Y0, hb):
        wall_bay((X, Y1, 0), (-1, 0, 0), s0, s1)
    for (s0, s1) in segs_between([y - Y0 for y in sy_in], 0.0, Y1 - Y0, hb):
        wall_bay((-X, Y0, 0), (1, 0, 0), s0, s1)
    for (s0, s1) in segs_between([x + X for x in xs[1:-1]], 0.0, 2 * X, hb):
        wall_bay((-X, Y1, 0), (0, -1, 0), s0, s1)
    # 前墙：窗下的槛墙里面贴墙裙（槛墙厚 0.5，里皮在 Y0 + 0.11）
    for i in range(9):
        if i in H_DOORS:
            continue
        x0, x1 = xs[i] + H_CR - 0.03, xs[i + 1] - H_CR + 0.03
        yy = H_WY + 0.25
        _band_run(F, 'wall', 'dado_b', (x1, yy + 0.002, FL + 0.16), (-1, 0, 0), Z, x1 - x0, 1.0, part=PW_)
        a.box((x1 - x0, 0.04, 0.16), ((x0 + x1) / 2, yy + 0.02, FL), color=_INK, bevel=0.006, mat=T)

    mark('墙面壁画')
    # ── 下层墙顶：额枋（旋子彩画）、平板枋（连珠）一圈 ──
    zb0, zb1 = WB, WB + 0.72
    bt = 0.16
    _xuanzi_beam(a, F, (-X, Y0 + bt / 2), (X, Y0 + bt / 2), zb0, zb1, bt, [x + X for x in xs[1:-1]], 'xuanzi_a', PB, faces=(0, 1), mat=T)
    _xuanzi_beam(a, F, (X, Y1 - bt / 2), (-X, Y1 - bt / 2), zb0, zb1, bt, [X - x for x in reversed(xs[1:-1])], 'xuanzi_a', PB, faces=(0, 1), mat=T)
    ya, yb = Y0 + bt + 0.001, Y1 - bt - 0.001
    _xuanzi_beam(a, F, (X - bt / 2, ya), (X - bt / 2, yb), zb0, zb1, bt, [y - ya for y in sy_in], 'xuanzi_b', PB, faces=(0, 1), mat=T)
    _xuanzi_beam(a, F, (-X + bt / 2, yb), (-X + bt / 2, ya), zb0, zb1, bt, [yb - y for y in reversed(sy_in)], 'xuanzi_b', PB, faces=(0, 1), mat=T)
    zp0, zp1 = zb1, zb1 + 0.12
    walls4 = (((X, Y0), (0, 1, 0), 2 * X), ((-X, Y1), (0, -1, 0), 2 * X), ((X, Y1), (-1, 0, 0), Y1 - Y0), ((-X, Y0), (1, 0, 0), Y1 - Y0))
    for k, (p0, n_, L) in enumerate(walls4):
        p0, n_ = Vector(p0 + (0,)), Vector(n_)
        A = Z.cross(n_)
        e = 0.0 if k < 2 else 0.121              # 前后两道通长，两山的夹在中间
        q0, q1 = p0 + A * e + n_ * 0.06, p0 + A * (L - e) + n_ * 0.06
        lbox(q0, q1, 0.12, zp0, zp1 - zp0, _BLU_D)
        _band_run(F, 'beam', 'pearl', (q0 + n_ * 0.061 + Vector((0, 0, zp0))), A, Z, L - 2 * e, zp1 - zp0, part=PB)

    mark('额枋')
    # ── 室内斗拱：四面墙一圈（往屋里挑），柱头上各一攒、柱间按 1.45 米一攒；两攒之间一块拱眼壁（彩画）；正心枋一整行连着 ──
    zg = zp1
    s_in = 1.2
    n_dg = 0
    for k, (p0, n_, L) in enumerate(walls4):
        p0, n_ = Vector(p0 + (0,)), Vector(n_)
        A = Z.cross(n_)
        ang = math.atan2(n_.y, n_.x)
        if k == 0:
            st_ = [X - x for x in reversed(xs)]
        elif k == 1:
            st_ = [x + X for x in xs]
        elif k == 2:
            st_ = [Y1 - y for y in reversed(H_SY)]
        else:
            st_ = [y - Y0 for y in H_SY]
        st_ = [0.75] + [v for v in st_ if 1.6 < v < L - 1.6] + [L - 0.75]
        pos, gap = _dg_stations(st_, 1.45)
        pts = [p0 + A * s + n_ * 0.06 for s in pos]
        for i, p in enumerate(pts):
            ca, cb = (_BLU, _GRN) if i % 2 == 0 else (_GRN, _BLU)
            _dg_set(a, p.x, p.y, zg, ang, ca, cb, T, s_in, lite=True)
            n_dg += 1
        for i in range(len(pts) - 1):
            g = (pts[i + 1] - pts[i]).length
            if g > 1.7:
                continue
            w = g - 0.36
            m = (pts[i] + pts[i + 1]) / 2 - n_ * 0.055 - A * (w / 2)
            _pq(F, 'beam', 'gongyan_a' if i % 2 == 0 else 'gongyan_b', (m.x, m.y, zg + 0.01), A, Z, w, 0.56, part=PB)
        # 正心枋：压在正心万栱上的一道通长的枋（青地金边）
        e = 0.0 if k < 2 else 0.12
        q0, q1 = p0 + A * e + n_ * 0.06, p0 + A * (L - e) + n_ * 0.06
        c_ = (q0 + q1) / 2
        _gold_box(a, ((q1 - q0).length, 0.09 * s_in, 0.15 * s_in), (c_.x, c_.y, zg + 0.50 * s_in), math.atan2(A.y, A.x), _BLU_D, T)
    for sx in (-1, 1):
        for (yy, sy_) in ((Y0 + 0.06, 1), (Y1 - 0.06, -1)):
            _dg_corner(a, sx * (X - 0.06), yy, zg, (-sx, 0), (0, sy_), _GRN, _BLU, T, s_in)

    mark('斗拱')
    # ── 上层墙面：一道流云（彩画）、上下金线，一间一扇高窗，墙顶额枋（旋子彩画）──
    uwalls = (((UX, UY0), (0, 1, 0), 2 * UX), ((-UX, UY1), (0, -1, 0), 2 * UX), ((UX, UY1), (-1, 0, 0), UY1 - UY0), ((-UX, UY0), (1, 0, 0), UY1 - UY0))
    zc0, zc1 = zl + 0.35, zl + 1.35
    zw0, zw1 = zl + 1.85, zl + 2.95
    ze0, ze1 = H_JUN - 0.72, H_JUN - 0.12
    bars, wins = [], 0
    for k, (p0, n_, L) in enumerate(uwalls):
        p0, n_ = Vector(p0 + (0,)), Vector(n_)
        A = Z.cross(n_)
        ang = math.atan2(A.y, A.x)
        _band_run(F, 'beam', 'cloud_b', p0 + n_ * 0.003 + Vector((0, 0, zc0)), A, Z, L, zc1 - zc0, part=PB)
        e = 0.0 if k < 2 else 0.031
        for zz in (zc0 - 0.06, zc1 + 0.02):
            lbox(p0 + A * e + n_ * 0.015, p0 + A * (L - e) + n_ * 0.015, 0.03, zz, 0.04, gold)
        # 高窗：位置对着下面的开间
        if k == 0:
            st_ = [UX - x for x in reversed(xs)]
        elif k == 1:
            st_ = [x + UX for x in xs]
        elif k == 2:
            st_ = [UY1 - y for y in reversed(H_SY)]
        else:
            st_ = [y - UY0 for y in H_SY]
        st_ = [max(0.0, min(L, v)) for v in st_]
        for i in range(len(st_) - 1):
            sa, sb = st_[i], st_[i + 1]
            if sb - sa < 1.6:
                continue
            ww = min(3.2, sb - sa - 1.0)
            c0 = p0 + A * ((sa + sb) / 2 - ww / 2) + n_ * 0.004
            c1 = c0 + A * ww
            mid = (c0 + c1) / 2
            a.box((ww, 0.008, zw1 - zw0), (mid.x, mid.y, zw0), rot=(0, 0, ang), color=_PAPER, bevel=0.0, mat=T)
            # 窗框
            for (ua, ub, za, zb_) in ((-0.08, ww + 0.08, zw0 - 0.08, zw0), (-0.08, ww + 0.08, zw1, zw1 + 0.08), (-0.08, 0.0, zw0, zw1), (ww, ww + 0.08, zw0, zw1)):
                cc = c0 + A * ((ua + ub) / 2) + n_ * 0.025
                a.box((ub - ua, 0.06, zb_ - za), (cc.x, cc.y, za), rot=(0, 0, ang), color=C('red_deep'), bevel=0.01, mat=LQ)
            nmul = max(1, int(round(ww / 0.8)))
            for q in range(1, nmul):
                bars.append((c0 + A * (ww * q / nmul) + Vector((0, 0, zw0)) + n_ * 0.004, c0 + A * (ww * q / nmul) + Vector((0, 0, zw1)) + n_ * 0.004, n_, 0.03, 0.04, C('lattice')))
            stp, sq = 0.22, math.sqrt(2)
            hh = zw1 - zw0
            c = -hh - ww
            while c < ww + hh:
                for sg in (1, -1):
                    seg = _seg_in_rect((c, 0.0), (1 / sq, sg / sq), ww, hh)
                    if seg is not None and seg[1] - seg[0] > 0.04:
                        bars.append((c0 + A * (c + seg[0] / sq) + Vector((0, 0, zw0 + sg * seg[0] / sq)) + n_ * 0.004,
                                     c0 + A * (c + seg[1] / sq) + Vector((0, 0, zw0 + sg * seg[1] / sq)) + n_ * 0.004, n_, 0.018 + (0.002 if sg < 0 else 0.0), 0.022, C('lattice')))
                c += stp
            wins += 1
        # 墙顶额枋（薄的一道彩画板）和连珠
        q0, q1 = p0 + A * e + n_ * 0.04, p0 + A * (L - e) + n_ * 0.04
        _xuanzi_beam(a, F, (q1.x, q1.y), (q0.x, q0.y), ze0, ze1, 0.08, [L - 2 * e - (v - e) for v in reversed(st_[1:-1])], 'xuanzi_a' if k < 2 else 'xuanzi_b', PB, faces=(1, 0), mat=T)
        _band_run(F, 'beam', 'pearl', p0 + A * e + n_ * 0.003 + Vector((0, 0, ze1)), A, Z, L - 2 * e, 0.12, part=PB)
    _bulk_bars(a, bars, T)

    mark('上层墙面')
    # ── 峻脚：上层墙顶到平顶天花的一圈斜板（流云彩画，一段一段掉头）──
    fx, fy0, fy1 = H_FLAT
    ox, oy0, oy1 = UX + 0.02, UY0 - 0.02, UY1 + 0.02
    ix, iy0, iy1, iz = fx + 0.03, fy0 - 0.03, fy1 + 0.03, H_PANEL + 0.004
    outer = [Vector((ox, oy0, H_JUN - 0.02)), Vector((ox, oy1, H_JUN - 0.02)), Vector((-ox, oy1, H_JUN - 0.02)), Vector((-ox, oy0, H_JUN - 0.02))]
    inner = [Vector((ix, iy0, iz)), Vector((ix, iy1, iz)), Vector((-ix, iy1, iz)), Vector((-ix, iy0, iz))]
    for k in range(4):
        o0, o1 = outer[k], outer[(k + 1) % 4]
        i0, i1 = inner[k], inner[(k + 1) % 4]
        key = 'cloud' if k in (0, 2) else 'cloud_b'
        L = (o1 - o0).length
        slant = 0.86
        n = max(1, int(round(L / (_aspect('beam', key) * slant))))
        for j in range(n):
            u0, u1 = (1, 0) if (j + k) % 2 == 1 else (0, 1)
            quad = [o0.lerp(o1, j / n), o0.lerp(o1, (j + 1) / n), i0.lerp(i1, (j + 1) / n), i0.lerp(i1, j / n)]
            uv = [_pv('beam', key, u0, 0), _pv('beam', key, u1, 0), _pv('beam', key, u1, 1), _pv('beam', key, u0, 1)]
            F.setdefault(PB, []).append((list(reversed([tuple(v) for v in quad])), list(reversed(uv))))
    for (p0, p1) in (((fx, fy0), (fx, fy1)), ((-fx, fy0), (-fx, fy1)), ((-fx + 0.061, fy0), (fx - 0.061, fy0)), ((-fx + 0.061, fy1), (fx - 0.061, fy1))):
        lbox(p0, p1, 0.12, H_PANEL - 0.09, 0.085, gd, bevel=0.012, top=gold)

    mark('峻脚')
    # ── 井口天花：梁把天花分成一块块，每块里排 0.9 米见方的天花板（彩画），支条（绿），支条交叉处一颗金钉 ──
    zx, zy0, zy1 = H_ZJ
    hbm = H_BEAM_T / 2
    bxs = sorted({abs(p[0]) for p in H_JIN})                 # 南北向的梁：|x| = 3.5、10.5、14.4
    xcut = [-fx] + [-v for v in reversed(bxs)] + bxs + [fx]
    ycut = [fy0, H_ROWS[0], H_ROWS[1], fy1]
    cells = []
    for i in range(len(xcut) - 1):
        xa = xcut[i] + (hbm if i > 0 else 0.06)
        xb = xcut[i + 1] - (hbm if i < len(xcut) - 2 else 0.06)
        for j in range(3):
            ya_ = ycut[j] + (hbm if j > 0 else 0.06)
            yb_ = ycut[j + 1] - (hbm if j < 2 else 0.06)
            if abs(xa + xb) < 1e-6 and j == 1:
                # 明间正中：藻井前后各一块
                cells.append((xa, xb, ya_, zy0 - 0.3, True))
                cells.append((xa, xb, zy1 + 0.3, yb_, True))
            else:
                cells.append((xa, xb, ya_, yb_, False))
    ribs, studs, n_panel = [], [], 0
    for (xa, xb, ya_, yb_, near) in cells:
        nx_, ny_ = max(1, int(round((xb - xa) / 0.9))), max(1, int(round((yb_ - ya_) / 0.9)))
        dx, dy = (xb - xa) / nx_, (yb_ - ya_) / ny_
        for i in range(nx_):
            for j in range(ny_):
                key = 'panel_lotus_b' if near else ('panel_lotus' if (i + j) % 2 == 0 else 'panel_wheel')
                _pq(F, 'ceiling', key, (xa + dx * i, ya_ + dy * j, H_PANEL), (0, 1, 0), (1, 0, 0), dy, dx, part=PC)
                n_panel += 1
        for i in range(nx_ + 1):
            ribs.append(((xa + dx * i, (ya_ + yb_) / 2, H_CEIL + 0.03), (0.07, yb_ - ya_, 0.06), 0.0, 0.0, _GRN))
        for j in range(ny_ + 1):
            ribs.append((((xa + xb) / 2, ya_ + dy * j, H_CEIL + 0.031), (xb - xa, 0.07, 0.06), 0.0, 0.0, _GRN))
        for i in range(1, nx_):
            for j in range(1, ny_):
                px, py, r_ = xa + dx * i, ya_ + dy * j, 0.07
                tip_ = (px, py, H_CEIL - 0.03)
                cs = [(px - r_, py, H_CEIL), (px, py - r_, H_CEIL), (px + r_, py, H_CEIL), (px, py + r_, H_CEIL)]
                for q in range(4):
                    studs.append((_orient([cs[q], cs[(q + 1) % 4], tip_], (0, 0, -1)), gold if q % 2 == 0 else gd))
    _bulk_boxes(a, ribs, T)
    _bulk_polys(a, studs, T)

    mark('天花')
    # ── 天花梁：东西向两根（压在前后两排金柱上），南北向六根；井口枋；雀替 ──
    for yy in H_ROWS:
        _xuanzi_beam(a, F, (-UX - 0.01, yy), (UX + 0.01, yy), H_BEAM0, H_PANEL + 0.002, H_BEAM_T, [UX + 0.01 + v for v in xcut[1:-1]],
                     'xuanzi_a', PB, mat=T, color=_BLU_D)
    for xx in xcut[1:-1]:
        brk = [v - UY0 for v in (H_SY[1:5] if abs(abs(xx) - 14.4) < 0.01 else H_ROWS)]
        _xuanzi_beam(a, F, (xx, UY0 - 0.01), (xx, UY1 + 0.01), H_BEAM0 + 0.1, H_PANEL + 0.012, H_BEAM_T - 0.04, [v + 0.01 for v in brk], 'xuanzi_b', PB, mat=T, color=_GRN_D)
    for yy in (zy0 - 0.15, zy1 + 0.15):
        _xuanzi_beam(a, F, (-3.5 + hbm - 0.019, yy), (3.5 - hbm + 0.019, yy), H_PANEL - 0.62, H_PANEL + 0.006, 0.3, [], 'xuanzi_b', PB, mat=T, color=_GRN_D)
    n_qt = 0
    for (x, y) in H_JIN:
        if y in H_ROWS:
            for sg in (-1, 1):
                if abs(x + sg * 2) > UX:
                    continue
                _queti(a, (x + sg * H_JIN_R * 0.88, y), 1, H_BEAM0, T, rot=0.0 if sg > 0 else math.pi, scale=1.9)
                n_qt += 1
        else:
            for sg in (-1, 1):
                _queti(a, (x, y + sg * H_JIN_R * 0.88), 1, H_BEAM0 + 0.1, T, rot=sg * math.pi / 2, scale=1.9)
                n_qt += 1

    mark('天花梁雀替')
    # ── 扇面墙：三尊佛背后的一道墙（后排金柱之间，顶到天花梁）。正面（朝南）墙裙、金线框、顶上一道流云；背面三幅壁画 ──
    sx0, sx1, sy_, sth = H_SCREEN
    a.box((sx1 - sx0, sth, H_BEAM0 + 0.02 - FL + 0.012), (0, sy_, FL - 0.012), color=_WALL_RED, bevel=0.0, mat=T)
    inner_x = [x for x in sorted({p[0] for p in H_JIN if p[1] == sy_}) if sx0 < x < sx1]
    for (s0, s1) in segs_between([sx1 - x for x in inner_x], H_JIN_R - 0.03, sx1 - sx0 - H_JIN_R + 0.03, H_JIN_R - 0.03):
        wall_bay((sx1, sy_ + sth / 2, 0), (0, 1, 0), s0, s1)
    for (s0, s1) in segs_between([x - sx0 for x in inner_x], H_JIN_R - 0.03, sx1 - sx0 - H_JIN_R + 0.03, H_JIN_R - 0.03):
        p0 = Vector((sx0, sy_ - sth / 2, 0))
        A, n_ = Vector((1, 0, 0)), Vector((0, -1, 0))
        w = s1 - s0
        base = p0 + A * s0 + n_ * 0.002
        mid = base + A * (w / 2)
        a.box((w, 0.04, 0.16), (mid.x, mid.y - 0.018, FL), color=_INK, bevel=0.006, mat=T)
        _band_run(F, 'wall', 'dado_a', base + Vector((0, 0, FL + 0.16)), A, Z, w, 1.1, part=PW_)
        a.box((w, 0.045, 0.07), (mid.x, mid.y - 0.0205, FL + 1.26), color=C('red_deep'), bevel=0.008, top=gold, mat=LQ)
        # 金线框（背光后面的一大块素红墙）
        for (ua, ub, za, zb_) in ((0.3, w - 0.3, FL + 1.7, FL + 1.74), (0.3, w - 0.3, 10.36, 10.4), (0.3, 0.34, FL + 1.74, 10.36), (w - 0.34, w - 0.3, FL + 1.74, 10.36)):
            a.box((ub - ua, 0.012, zb_ - za), (base.x + (ua + ub) / 2, base.y - 0.006, za), color=gold, bevel=0.0, mat=T)
        _band_run(F, 'beam', 'cloud', base + Vector((0, 0, 10.75)), A, Z, w, 1.0, part=PB)
        _band_run(F, 'beam', 'pearl', base + Vector((0, 0, 11.85)), A, Z, w, 0.14, part=PB)

    mark('扇面墙')
    # ── 藻井 ──
    _zaojing(a, F, rng)
    mark('藻井')
    return dict(n_brick=n_brick, n_panel=n_panel, n_dg_in=n_dg, n_queti=n_qt, n_win_in=wins, pilasters=pil, pil_r=PR, cells=cells)


def _zaojing(a, F, rng):
    """藻井（明间正中、拜位的上方）：方井 → 八角井（四角是角蝉）→ 圆井 → 穹顶（宝相花），每一层上沿一圈小斗拱，正中倒垂一朵金莲、一颗宝珠。
    方口 6.4 米见方，从天花 13.63 升到 16.2"""
    T = 'toon:in_toon'
    PB, PC = 'paint_beam:in_paint_beam', 'paint_ceiling:in_paint_ceiling'
    gold, gd = C('gold'), C('gold_dark')
    zx, zy0, zy1 = H_ZJ
    cx, cy = 0.0, (zy0 + zy1) / 2
    hx, hy = zx, (zy1 - zy0) / 2
    K = hx / 1.32                            # 比老殿的藻井大多少
    z0 = H_PANEL
    z1, z2, z3 = z0 + 0.7, z0 + 1.38, z0 + 2.06
    Z = Vector((0, 0, 1))
    sides = [((cx + hx, cy - hy), (cx + hx, cy + hy)), ((cx + hx, cy + hy), (cx - hx, cy + hy)), ((cx - hx, cy + hy), (cx - hx, cy - hy)), ((cx - hx, cy - hy), (cx + hx, cy - hy))]
    for (p0, p1) in sides:
        p0v, p1v = Vector((p0[0], p0[1], z0 - 0.002)), Vector((p1[0], p1[1], z0 - 0.002))
        _xz_run(F, 'beam', 'xuanzi_b', p1v, (p0v - p1v).normalized(), Z, (p1v - p0v).length, z1 - z0 + 0.012, part=PB)
    for k, (p0, p1) in enumerate(sides):
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) + (0.16 if k % 2 == 0 else -0.161)
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        a.box((L, 0.16, 0.1), ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, z0 - 0.1), rot=(0, 0, ang), color=gold, bevel=0.025, mat=T)
    s1_, s2_, s3_ = 0.58, 0.5, 0.46
    for si, (p0, p1) in enumerate(sides):
        d = Vector((p1[0] - p0[0], p1[1] - p0[1], 0))
        nrm = Vector((-d.y, d.x, 0)).normalized()
        ang = math.atan2(nrm.y, nrm.x)
        _dg_line(a, (p0[0] + d.x * 0.07, p0[1] + d.y * 0.07), (p1[0] - d.x * 0.07, p1[1] - d.y * 0.07), z1 - 0.685 * s1_ - 0.006 + 0.004 * (si % 2), ang, 1.05, s1_, T)
    a1 = 1.06 * K
    R1 = a1 / math.cos(math.pi / 8)
    oct_ = [(cx + R1 * math.cos(math.pi / 8 + k * math.pi / 4), cy + R1 * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)]
    ledge = []
    for k in range(8):
        pa, pb = oct_[k], oct_[(k + 1) % 8]
        mid = math.pi / 8 + k * math.pi / 4 + math.pi / 8
        dirx, diry = math.cos(mid), math.sin(mid)
        if abs(dirx) > 0.99 or abs(diry) > 0.99:
            if abs(dirx) > 0.99:
                qa, qb = (cx + math.copysign(hx, dirx), pa[1]), (cx + math.copysign(hx, dirx), pb[1])
            else:
                qa, qb = (pa[0], cy + math.copysign(hy, diry)), (pb[0], cy + math.copysign(hy, diry))
            ledge.append(([qa, qb, pb, pa], gd))
        else:
            corner = (cx + math.copysign(hx, dirx), cy + math.copysign(hy, diry))
            qa = (cx + math.copysign(hx, dirx), pa[1]) if abs(pa[1] - cy) < abs(pa[0] - cx) else (pa[0], cy + math.copysign(hy, diry))
            qb = (pb[0], cy + math.copysign(hy, diry)) if abs(pb[0] - cx) < abs(pb[1] - cy) else (cx + math.copysign(hx, dirx), pb[1])
            poly = [qa, corner, qb, pb, pa]
            xs_ = [p[0] for p in poly]
            ys_ = [p[1] for p in poly]
            bx0, bx1, by0, by1 = min(xs_), max(xs_), min(ys_), max(ys_)
            uv = [_pv('ceiling', 'panel_cloud', (p[0] - bx0) / (bx1 - bx0), (p[1] - by0) / (by1 - by0)) for p in poly]
            pts3 = [(p[0], p[1], z1) for p in poly]
            F.setdefault(PC, []).append((list(reversed(pts3)), list(reversed(uv))))
    _bulk_polys(a, [(_orient([(p[0], p[1], z1) for p in poly], (0, 0, -1)), col) for (poly, col) in ledge], T)
    for k in range(8):
        pa, pb = oct_[k], oct_[(k + 1) % 8]
        p0v, p1v = Vector((pa[0], pa[1], z1 - 0.004)), Vector((pb[0], pb[1], z1 - 0.004))
        L = (p1v - p0v).length
        _pq(F, 'beam', 'scroll', p1v, (p0v - p1v).normalized(), Z, L, z2 - z1 + 0.012, 0.0, min(1.0, L / (_aspect('beam', 'scroll') * (z2 - z1))), part=PB)
        mid = math.pi / 8 + k * math.pi / 4 + math.pi / 8
        inward = mid + math.pi
        _dg_line(a, (pa[0] * 0.94 + cx * 0.06 + (pb[0] - pa[0]) * 0.14, pa[1] * 0.94 + cy * 0.06 + (pb[1] - pa[1]) * 0.14),
                 (pb[0] * 0.94 + cx * 0.06 - (pb[0] - pa[0]) * 0.14, pb[1] * 0.94 + cy * 0.06 - (pb[1] - pa[1]) * 0.14),
                 z2 - 0.685 * s2_ - 0.006 + 0.004 * (k % 2), inward, 0.8, s2_, T)
    r2 = 0.86 * K
    n = 48
    ring = []

    def octr(ang):
        m = (ang - math.pi / 8) % (math.pi / 4) - math.pi / 8
        return a1 / math.cos(m)
    for k in range(n):
        ang0, ang1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        pts = [(cx + octr(ang0) * math.cos(ang0), cy + octr(ang0) * math.sin(ang0), z2), (cx + octr(ang1) * math.cos(ang1), cy + octr(ang1) * math.sin(ang1), z2),
               (cx + r2 * math.cos(ang1), cy + r2 * math.sin(ang1), z2), (cx + r2 * math.cos(ang0), cy + r2 * math.sin(ang0), z2)]
        ring.append((_orient(pts, (0, 0, -1)), gd if k % 2 else gold))
    _bulk_polys(a, ring, T)
    for k in range(n):
        ang0, ang1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        p0v = Vector((cx + r2 * math.cos(ang0), cy + r2 * math.sin(ang0), z2 - 0.004))
        p1v = Vector((cx + r2 * math.cos(ang1), cy + r2 * math.sin(ang1), z2 - 0.004))
        s0 = (k % 16) / 16
        _pq(F, 'beam', 'pearl', p1v, (p0v - p1v).normalized(), Z, (p1v - p0v).length, z3 - z2 + 0.012, s0, s0 + 1 / 16, part=PB)
    for k in range(16):
        ang = 2 * math.pi * (k + 0.5) / 16
        _dg_set(a, cx + (r2 - 0.02) * math.cos(ang), cy + (r2 - 0.02) * math.sin(ang), z3 - 0.685 * s3_ - 0.004, ang + math.pi,
                _BLU if k % 2 else _GRN, _GRN if k % 2 else _BLU, T, s3_, fat=1.5, tail=0.05, lite=True)
    rings = 8

    def dz(r):
        return z3 + (H_ZJ_TOP - z3) * max(0.0, 1 - (r / r2) ** 2) ** 0.5
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
    from props_hd import petal_ring
    sub = Asset('_lotus')
    petal_ring(sub, 12, 0.13, 0.0, 0.16, 0.08, 0.03, 30, gold, T, up=False, rng=rng)
    petal_ring(sub, 10, 0.08, -0.05, 0.12, 0.065, 0.028, 45, C('gold_dark'), T, up=False, rng=rng, phase=0.5)
    sub.lathe([(0.0, 0.05), (0.16, 0.04, gd), (0.14, -0.02, gold), (0.06, -0.08, gold), (0.0, -0.09)], segs=24, color=gold, mat=T)
    sub.cyl(0.012, 0.16, (0, 0, -0.26), gd, segs=6, mat=T)
    sub.lathe([(0.0, 0.0), (0.05, 0.01, gd), (0.09, 0.07, C('white')), (0.1, 0.12, C('white')), (0.085, 0.17, C('white')), (0.05, 0.2, gold), (0.03, 0.22, gd), (0.0, 0.23)],
              (0, 0, -0.48), segs=20, color=C('white'), mat=T)
    a.place(sub, (cx, cy, H_ZJ_TOP - 0.2), (0, 0, 0), 2.3)


def _queti(a, p, sg, z, mat, rot=0.0, scale=1.0):
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
        sub.tube(edge, 0.006, gold, segs=3, mat=mat)
        # 金色卷草：两个卷、一道茎
        for (cx, cz, r, turns) in ((0.36, -0.1, 0.055, 1.3), (0.17, -0.19, 0.045, 1.2)):
            # 卷到 0.2 r 就停（卷到圆心，最后几段管子挤在一起，面翻过来）
            pts2 = [(sg * (cx + r * (1 - k / 16) * math.cos(-k / 16 * turns * 2 * math.pi)), yf, cz + r * (1 - k / 16) * math.sin(-k / 16 * turns * 2 * math.pi)) for k in range(0, 14, 2)]
            sub.tube(pts2, 0.0055, gold, segs=3, mat=mat)
        stem = [(sg * 0.05, yf, -0.06), (sg * 0.2, yf, -0.07), (sg * 0.36, yf, -0.045), (sg * 0.52, yf, -0.06)]
        sub.tube(stem, 0.005, gold, segs=3, mat=mat)
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
    a.place(sub, (p[0], p[1], z), (0, 0, rot), scale)


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
