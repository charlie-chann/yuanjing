"""大雄宝殿的三世佛（2026-11-17）：中间释迦牟尼，两边药师佛、阿弥陀佛，各坐一座莲台，身后一面背光。

全部手工「雕」出来：形体用距离场（sdf.py）一块块拼——椭球、圆台、管子，平滑地并起来、挖下去；眼、眉、唇是按 (x, z) 画在脸上的
浮雕（face_maps）；衣纹、衣边是贴在形体表面上画出来的一道道棱。openvdb 抽成网格（头 2.1 毫米一格、手脚 1.6 毫米、身子 3.6 毫米），
Blender 分区减面（脸正面留得密），Cycles 烤暗部乘进顶点色。
螺发一颗颗是实打实的尖顶螺壳（四百多颗，和发际线平行一排排排上去，肉髻上一圈圈），莲瓣一片片建（瓣尖外卷、中间一道脊、瓣边一圈凸线），
须弥座的壸门、宝相花、卷草一笔笔做；衣缘、开脸（描眉点睛朱唇）、背光的纹样是手绘贴图（tools/textures/painted_statues.py）。

部件：gold（鎏金：衣服、莲座、髻珠、手里的法器）、paint_buddha_face（泥金：脸、颈、胸口、手、脚，贴开脸那张图）、
toon（石青螺发）、paint_robe_band（衣缘卷草纹带）、paint_mandorla（背光）。
坐标：原点在莲座底面中心（背光也是：背光和它的佛像放在同一点），-y 是正面（朝殿门），单位米。两尊胁侍按 0.85 倍做好了（放的时候不用再缩放）。
"""
import math

import numpy as np

import sdf
from sdf import V, euler


class Frame:
    """局部坐标系：原点 o、旋转 R（列是局部轴）、整体缩放 s。头、手都在自己的坐标里写，再摆到身上"""

    def __init__(self, o=(0, 0, 0), R=None, s=1.0):
        self.o = V(o)
        self.R = np.eye(3) if R is None else np.asarray(R, np.float64)
        self.s = float(s)

    def p(self, *a):
        q = V(*a)
        return self.o + self.R @ (q * self.s)

    def d(self, *a):
        """方向（只转不移）"""
        return self.R @ V(*a)

    def r(self, Rl=None):
        return self.R if Rl is None else self.R @ Rl

    def k(self, v):
        return np.asarray(v, np.float64) * self.s if not isinstance(v, (int, float)) else v * self.s

    def child(self, o=(0, 0, 0), R=None, s=1.0):
        return Frame(self.p(o), self.r(R), self.s * s)

    # 在这个坐标系里建形体
    def sph(self, c, r):
        return sdf.Sphere(self.p(c), self.k(r))

    def ell(self, c, r, Rl=None):
        return sdf.Ellipsoid(self.p(c), self.k(r), self.r(Rl))

    def cone(self, a, b, ra, rb=None):
        return sdf.RoundCone(self.p(a), self.p(b), self.k(ra), self.k(ra if rb is None else rb))

    def chain(self, pts, radii, k=0.0):
        if isinstance(radii, (int, float)):
            radii = [radii] * len(pts)
        return sdf.chain([self.p(q) for q in pts], [self.k(r) for r in radii], self.k(k))

    def curve(self, pts, radii, n=6, k=0.0):
        """过这些点的平滑曲线做成的管子，radii 每个控制点一个（中间线性插）"""
        P = sdf.catmull(pts, n)
        if isinstance(radii, (int, float)):
            radii = [radii] * len(pts)
        m = len(P)
        rr = np.interp(np.linspace(0, len(pts) - 1, m), np.arange(len(pts)), radii)
        return self.chain(P, list(rr), k)

    def box(self, c, half, Rl=None, rnd=0.0):
        return sdf.Box(self.p(c), self.k(half), self.r(Rl), self.k(rnd))

    def torus(self, c, R0, r, Rl=None):
        return sdf.Torus(self.p(c), self.k(R0), self.k(r), self.r(Rl))

    def plane(self, p, n):
        return sdf.Plane(self.p(p), self.R @ V(n))


def U(kids, k=0.0, F=None):
    return sdf.Union(kids, F.k(k) if F else k)


def S(a, b, k=0.0, F=None):
    return sdf.Sub(a, b, F.k(k) if F else k)


def wtube(pts, radii, n=6, k=0.0):
    """世界坐标里过这些点的平滑管子"""
    P = sdf.catmull(pts, n)
    if isinstance(radii, (int, float)):
        radii = [radii] * len(pts)
    rr = np.interp(np.linspace(0, len(pts) - 1, len(P)), np.arange(len(pts)), radii)
    return sdf.chain(P, list(rr), k)


def on_surf(node, pts, dirs, tmax=0.3):
    """把空中画的点沿 dirs 方向贴到 node 的表面上（世界坐标）"""
    P = np.asarray(pts, np.float64)
    D = np.broadcast_to(np.asarray(dirs, np.float64), P.shape)
    D = D / np.linalg.norm(D, axis=1, keepdims=True)
    return sdf.project(node, P - D * tmax * 0.5, D, tmax=tmax, n=72)


# ====================================================================== 头
# 头的局部坐标：原点在两眉之间那一高度、头颅前后的中间；-y 朝前，z 朝上。尺寸（局部单位，中尊放大 1.2 倍）：
# 发际 z≈0.085，眉 0，眼缝 -0.037，鼻底 -0.105，口 -0.1375，下巴底 -0.215；脸宽（颧）0.27；耳朵从眉到下巴以下。
# 眼、眉、唇是「浮雕」：在脸的正面按 (x, z) 画一张高低图，加在距离场上（往外为正），边要利的地方过渡只有一毫米。


def ss(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def spow(x, p):
    """非负的幂（float32 里 sin(π) 会是个很小的负数，直接开小数次方会得到 nan）"""
    return np.maximum(x, 0.0) ** p


def slit_z(t):
    """上眼睑的下沿（眼缝）：t=0 内眼角，1 外眼角。中间低（垂目）、外眼角微微上挑"""
    return -0.0395 - 0.0068 * np.sin(np.pi * t) + 0.0095 * t * t


EYE_IN, EYE_OUT = 0.025, 0.109          # 眼缝长到眉长的八成（明代造像的眼细而长）


def slit_open(t):
    """眼缝开多大（上眼睑下沿到下眼睑上沿）：垂目，只露一线（比原来再收两成多，下眼睑往上盖）"""
    return 0.0031 * spow(np.sin(np.pi * np.clip(t, 0, 1)), 0.75) * (1 - 0.2 * t) + 0.0006
USH_C, USH_R, USH_H = 0.18, 0.076, 0.09            # 肉髻圆顶的中心高、半径（头颅宽的 0.55）
JEWEL_Z, JEWEL_TILT = 0.15, 34.0       # 髻珠的高度（肉髻前面的根上）、朝上仰的角
NECK_LINES = ((-0.243, 0.0016), (-0.267, 0.0016), (-0.291, 0.0014))     # 颈上三道：(颈前的高度, 沟深)


def fbox(F, lo, hi, pad=0.0):
    """局部坐标里的一个盒子 → 世界坐标里包住它的轴对齐盒子"""
    C = np.array([F.p(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    return C.min(0) - F.k(pad), C.max(0) + F.k(pad)


def brow_z(u):
    """眉线（眉骨那道利棱）的高度：从鼻梁两侧起，高高地弯上去，到眉尾收下来。内端顺着鼻梁往下接（眉、鼻一笔下来）"""
    return np.interp(u, [0.0, 0.009, 0.014, 0.022, 0.035, 0.055, 0.075, 0.095, 0.112, 0.126, 0.14],
                     [-0.06, -0.045, -0.02, -0.004, 0.011, 0.0195, 0.0205, 0.015, 0.006, -0.004, -0.012])


def nose_side(z):
    """鼻梁两侧那道（眼窝的内边）的 |x|：上接眉头，往下越来越宽"""
    return 0.0115 + 0.006 * np.clip((-z - 0.02) / 0.07, 0, 1)


def mouth_z(u):
    return -0.1375 + 0.0042 * np.clip(u / 0.031, 0, 1.2) ** 2.2


def upper_lip_z(u):
    a = -0.1262 + 0.0014 * np.sin(np.pi * np.clip(u, 0, 0.0085) / 0.017)
    b = -0.1248 + (mouth_z(0.031) + 0.0006 + 0.1248) * np.clip((u - 0.0085) / 0.0235, 0, 1) ** 1.25
    return np.where(u < 0.0085, a, b)


def lower_lip_z(u):
    return -0.1490 + 0.0128 * np.clip(u / 0.03, 0, 1) ** 2


def face_maps(x, z):
    """脸正面的高低图和几张「画」的范围：h（米，往外为正）、eye（眼缝里）、lip（唇）、brow（画眉的地方）、liner（眼线）"""
    u = np.abs(x)
    h = np.zeros(np.broadcast_shapes(np.shape(x), np.shape(z)), np.float32)
    t = np.clip((u - EYE_IN) / (EYE_OUT - EYE_IN), -0.4, 1.4)
    tc = np.clip(t, 0, 1)
    zs = slit_z(tc)
    zb = brow_z(u)
    # ── 眼窝和上眼睑：眉棱下面一刀利利地凹进去（眼窝最深处在眉下），上眼睑是一个饱满的鼓包，一直鼓到眼缝，
    #    眼缝那里是上眼睑的下沿：一道利边，下面就是凹进去的眼珠。两头（内外眼角）眼窝更深 ──
    D = 0.0074                                   # 眼窝深（局部单位；中尊放大 1.38 倍 ≈ 1 厘米）
    span = np.maximum(zb - zs, 0.01)
    sv = (zb - z) / span                         # 0 在眉棱，1 在眼缝
    crease = ss(0.0, 0.06, sv)                   # 眉棱下面那一刀（利）
    lid = np.where(sv < 0.7, np.sin(0.5 * np.pi * np.clip(sv / 0.7, 0, 1)) ** 1.15,
                   1 - 0.42 * ((sv - 0.7) / 0.3) ** 2)
    # 横向：眼缝长度以内是完整的眼睑；两头（眼角）眼睑收掉，只剩眼窝（更深）
    lw = ss(-0.12, 0.08, t) * (1 - ss(0.92, 1.12, t))
    corner = np.exp(-((t - 0.0) / 0.1) ** 2) + 0.7 * np.exp(-((t - 1.0) / 0.1) ** 2)
    sock = -D * crease * (1 - lid * lw) + 0.0011 * lw * spow(np.sin(np.pi * np.clip(sv / 0.95, 0, 1)), 1.5) \
        - 0.0018 * corner * crease * ss(1.15, 0.6, sv)          # 上眼睑鼓出脸面一点点（饱满）
    inside_s = (sv >= 0) & (sv <= 1)
    # 眼窝的内边（鼻梁两侧）：也是一道棱；外边往太阳穴慢慢平掉
    wn = ss(0.0, 0.004, u - nose_side(z))
    wo = 1 - ss(0.112, 0.135, u)
    h += np.where(inside_s, sock * wn * wo, 0.0)
    # 眼缝下面：下眼睑从缝下沿起，往下慢慢回到脸面（不是一道棱）
    below = (z < zs) & (t > -0.15) & (t < 1.15)
    oh = slit_open(tc)
    zl = zs - oh                                  # 下眼睑的上沿
    lower = -(0.0036 + 0.0012 * corner) * ss(zl - 0.018, zl, z)
    h += np.where(below & (z < zl), lower * wn * wo, 0.0)
    # 眉棱外面（额头一侧）贴着棱有一点点鼓：棱更利
    h += 0.0009 * np.exp(-((z - zb - 0.0018) / 0.0022) ** 2) * wn * wo * ss(0.012, 0.02, u)
    # ── 眼缝：杏仁形的一道，里面是凹进去的眼珠（垂目，只露一线） ──
    tin = (t > 0) & (t < 1)
    inside = tin & (z <= zs) & (z >= zl)
    edge = ss(0.0, 0.0008, zs - z) * ss(0.0, 0.0011, z - zl)          # 下沿过渡宽一点：抽网格时不起锯齿
    zc = (zs + zl) / 2
    ball = -0.0046 + 0.0012 * (1 - ((z - zc) / np.maximum(oh / 2, 1e-4)) ** 2)          # 眼珠只凹一点（太深了抽网格时缝的下沿起锯齿）
    lidm = -D * (1 - (1 - 0.42) * 1.0)           # 上眼睑下沿的高度（眼缝上沿）
    h = np.where(inside, h * (1 - edge) + ball * edge, h)
    # 内眼角一个小窝（泪阜）、外眼角收一道
    h -= 0.0026 * np.exp(-(((u - EYE_IN + 0.001) / 0.0035) ** 2 + ((z - slit_z(0.0) + 0.002) / 0.003) ** 2))
    h -= 0.0012 * np.exp(-(((u - EYE_OUT - 0.002) / 0.004) ** 2 + ((z - slit_z(1.0) + 0.001) / 0.0025) ** 2))
    eye = inside.astype(np.float32) * edge
    liner = np.where(tin, np.exp(-((z - zs - 0.0003) / 0.0010) ** 2), 0.0) * (1 - eye)
    # 眼线在外眼角往外、往上再拖一小截（越来越细）
    tt = np.clip((u - EYE_OUT) / 0.012, 0, 1)
    tail = (u > EYE_OUT - 0.002) * np.exp(-((z - slit_z(1.0) - 0.0022 * tt - 0.0002) / (0.0010 * (1 - tt) + 0.0002)) ** 2) * (1 - tt)
    liner = np.maximum(liner, tail)
    # 画眉：棱上面一道细弯（中间粗、两头尖）
    bb = np.clip((u - 0.02) / 0.104, 0, 1)
    bw = 0.0008 + 0.0016 * spow(np.sin(np.pi * bb), 0.6)
    brow = np.exp(-((z - zb - 0.0034) / bw) ** 4) * ss(0.02, 0.03, u) * (1 - ss(0.114, 0.126, u))

    # ── 唇：上唇有唇峰，下唇更厚；唇线一道细缝，嘴角两个小窝 ──
    zm = mouth_z(u)
    zu = upper_lip_z(u)
    zw = lower_lip_z(u)
    v = (z - zm) / np.maximum(zu - zm, 1e-4)
    wu = 1 - ss(0.027, 0.034, u)
    up = 0.0036 * spow(np.sin(np.pi * np.clip(v, 0, 1)), 0.55) * (0.75 + 0.25 * (1 - v)) * wu
    up = np.where((v > 0) & (v < 1), up, 0.0)
    v2 = (zm - z) / np.maximum(zm - zw, 1e-4)
    wd = 1 - ss(0.021, 0.031, u)
    lo = 0.0052 * spow(np.sin(np.pi * np.clip(v2, 0, 1)), 0.5) * (0.8 + 0.2 * v2) * wd
    lo = np.where((v2 > 0) & (v2 < 1), lo, 0.0)
    h += up + lo
    lip = (np.clip(up / 0.0012, 0, 1) + np.clip(lo / 0.0012, 0, 1)).clip(0, 1)
    h -= 0.003 * np.exp(-((z - zm) / 0.0008) ** 2) * (1 - ss(0.03, 0.036, u))
    cz = mouth_z(0.031) + 0.0004
    h -= 0.0028 * np.exp(-(((u - 0.0335) / 0.0028) ** 2 + ((z - cz) / 0.0026) ** 2))      # 嘴角两个窝（从下往上看不成两个黑点）
    # 嘴角外面略鼓（含笑）
    h += 0.0012 * np.exp(-(((u - 0.044) / 0.008) ** 2 + ((z - cz - 0.004) / 0.01) ** 2))
    # 人中：一道沟，两边两道小棱
    pz = ss(-0.1245, -0.1215, z) * (1 - ss(-0.109, -0.106, z))
    h += pz * (-0.0021 * np.exp(-(u / 0.0034) ** 2) + 0.0011 * np.exp(-((u - 0.0062) / 0.0017) ** 2))
    # 下唇下面的那道凹（颏唇沟）
    h -= 0.0019 * np.exp(-((z + 0.1625) / 0.0065) ** 2) * (1 - ss(0.018, 0.034, u))
    return h, eye, lip, brow, liner


def to_local(F, X, Y, Z):
    """世界坐标 → 这个坐标系里的局部坐标（除以缩放）"""
    R = F.R
    dx, dy, dz = X - F.o[0], Y - F.o[1], Z - F.o[2]
    return ((R[0, 0] * dx + R[1, 0] * dy + R[2, 0] * dz) / F.s,
            (R[0, 1] * dx + R[1, 1] * dy + R[2, 1] * dz) / F.s,
            (R[0, 2] * dx + R[1, 2] * dy + R[2, 2] * dz) / F.s)


def head(F, info=None, F0=None):
    """佛头（含颈和颈下一截胸口）。info：往里记下上色要用的东西"""
    # ── 头颅、额、脸的大形：额宽、颊丰、下巴小而圆，侧面看脸是平的、鼻子挺出来 ──
    skull = F.ell((0, 0.02, 0.03), (0.136, 0.155, 0.162))
    forehead = F.ell((0, -0.038, 0.035), (0.122, 0.12, 0.085))
    face = F.ell((0, -0.03, -0.07), (0.118, 0.13, 0.15))
    cheeks = [F.ell((sx * 0.07, -0.066, -0.062), (0.058, 0.082, 0.064)) for sx in (-1, 1)]          # 颧下饱满，但不往下坠
    # 下颌：比原来收三成（低了头以后从下往上看，腮下那一团最显眼，不能是双下巴）
    jaw = [F.ell((sx * 0.05, -0.05, -0.144), (0.05, 0.07, 0.046)) for sx in (-1, 1)]
    temples = [F.ell((sx * 0.104, -0.03, 0.02), (0.045, 0.09, 0.07)) for sx in (-1, 1)]
    muzzle = F.ell((0, -0.112, -0.132), (0.047, 0.058, 0.048))                                    # 口唇那一团往前（侧面脸是直的）
    crown = F.ell((0, 0.02, 0.085), (0.138, 0.152, 0.095))              # 头顶宽一点、圆一点
    base = U([skull, crown, forehead, face] + cheeks + jaw + [muzzle] + temples, 0.036, F)
    # 下巴：单独一个圆而分明的小团（过渡小，下巴是下巴）
    chin = F.ell((0, -0.118, -0.183), (0.038, 0.04, 0.026))
    base = U([base, chin], 0.024, F)
    # 肉髻：头顶上另起一个圆顶（宽约头颅的 0.55），和头顶之间是一道看得出的台阶（过渡很小），螺发一直排上去
    ush = F.ell((0, 0.018, USH_C), (USH_R, USH_R * 1.04, USH_H))
    base = U([base, ush], 0.005, F)
    # 脸上的浮雕（眼、眉、唇）
    def relief(X, Y, Z):
        x, y, z = to_local(F, X, Y, Z)
        h = face_maps(x, z)[0]
        return -(h * ss(-0.1, -0.135, y)) * F.s
    base = sdf.Displace(base, relief, F.k(0.01), box=fbox(F, (-0.15, -0.26, -0.2), (0.15, -0.08, 0.06), 0.05))
    # 颈：圆柱，下面散开接到胸口。颈根按不低头的坐标（F0）放：头低下来，颈子是从胸口斜着伸上去的，不是整根跟着歪
    F0 = F if F0 is None else F0
    neck = U([sdf.RoundCone(F.p(0, -0.01, -0.14), F0.p(0, 0.006, -0.30), F.k(0.09), F.k(0.094)),
              sdf.RoundCone(F0.p(0, 0.006, -0.30), F0.p(0, -0.005, -0.39), F.k(0.093), F.k(0.105)),
              # 颈根往两边肩上散开（斜方肌）：颈子不是一截圆筒插在胸口上（第五轮）
              F0.ell((0, 0.035, -0.385), (0.17, 0.085, 0.045))], F.k(0.04))
    body = U([base, neck], 0.028, F)
    # 下巴底下：颐（一小团，比原来小三成，不坠），和下巴之间一道软软的浅褶（宽而浅的一道凹，没有硬棱）
    yi = [(sx * 0.05, -0.085, -0.203) for sx in (-1, 1)]
    yi_pts = [yi[0], (-0.03, -0.105, -0.2125), (0, -0.116, -0.2165), (0.03, -0.105, -0.2125), yi[1]]
    on = on_surf(body, [F.p(q) for q in yi_pts], [F.d(0, 0.5, 0.86)] * 5, tmax=F.k(0.12))
    nn = sdf.grad(body, on, 1e-3)
    # 管子的中心在表面外面 4.5 毫米、半径 6 毫米：只吃进去 1.5 毫米，平滑量大 → 一道很缓的凹
    rr = [0.002, 0.005, 0.0058, 0.005, 0.002]
    ctr = [q + n_ * F.k(r - 0.0014) for q, n_, r in zip(on, nn, rr)]
    body = sdf.Sub(body, wtube(ctr, [F.k(r) for r in rr], n=5), F.k(0.009))

    # ── 鼻：鼻梁直而长（从眉心一直下来，和眉棱连成一笔），鼻头圆而不大，两边鼻翼小 ──
    nose = U([F.cone((0, -0.151, 0.004), (0, -0.184, -0.078), 0.0078, 0.0118),
              F.ell((0, -0.185, -0.088), (0.0135, 0.0135, 0.0125)),
              F.ell((0, -0.172, -0.098), (0.017, 0.015, 0.0095))], 0.01, F)
    alae = [F.ell((sx * 0.0172, -0.168, -0.0965), (0.0094, 0.0115, 0.0088), euler(0, 0, sx * math.radians(-20))) for sx in (-1, 1)]
    body = U([body, nose], 0.012, F)
    body = U([body] + alae, 0.006, F)
    for sx in (-1, 1):
        nost = F.ell((sx * 0.0092, -0.1725, -0.1045), (0.0044, 0.0064, 0.0021), euler(math.radians(-18), 0, sx * math.radians(-25)))
        body = S(body, nost, 0.0016, F)
        crease = [(sx * 0.0155, -0.17, -0.084), (sx * 0.0272, -0.1625, -0.0905), (sx * 0.0302, -0.1585, -0.0995), (sx * 0.0242, -0.162, -0.1065)]
        body = S(body, F.curve(crease, 0.0014), 0.0028, F)

    # ── 髻珠：肉髻正前面、肉髻和头顶交界那里一颗宝珠（下面一圈托子）：位置贴到头皮上 ──
    if info is not None:
        info['scalp'] = base
        jd = F.d(0, math.cos(math.radians(JEWEL_TILT)), -math.sin(math.radians(JEWEL_TILT)))
        q, n_, ok = surf(base, [F.p(0, -0.06, JEWEL_Z) - jd * F.k(0.2)], jd, tmax=F.k(0.4))
        jc = q[0]
        info['jewel'] = (jc, F.k(0.03))
        info['jewel_local'] = V(to_local(F, *jc))
        info['jewel_frame'] = F
    # ── 白毫：两眉之间一颗小圆珠 ──
    body = U([body, F.sph((0, -0.158, 0.021), 0.0064)], 0.002, F)
    if info is not None:
        info['urna'] = F.p(0, -0.166, 0.021)
        info['face'] = F

    # ── 耳：长耳，耳垂拉得很长、中间开一道缝 ──
    for sx in (-1, 1):
        E = F.child((sx * 0.132, 0.034, -0.09), euler(math.radians(-6), 0, sx * math.radians(-20)))
        sg = sx
        plate = E.ell((sg * 0.012, 0.0, 0.035), (0.012, 0.032, 0.085))
        lobe = E.ell((sg * 0.012, 0.004, -0.088), (0.011, 0.022, 0.052))
        helix = E.curve([(sg * 0.018, -0.022, -0.02), (sg * 0.022, -0.026, 0.06), (sg * 0.024, -0.008, 0.112), (sg * 0.024, 0.02, 0.115),
                         (sg * 0.023, 0.034, 0.08), (sg * 0.02, 0.032, 0.02), (sg * 0.017, 0.026, -0.04), (sg * 0.016, 0.02, -0.1),
                         (sg * 0.015, 0.006, -0.135)], [0.006, 0.0075, 0.008, 0.008, 0.0075, 0.007, 0.0068, 0.0068, 0.008])
        ear = U([plate, lobe, helix], 0.008, F)
        # 第五轮（评审：耳朵是平平的一片）：耳轮卷得厚一点、往外翻；耳轮里面一道耳舟（沟）；耳甲挖成一个深的碗；
        # 对耳轮和上面分叉的两脚粗一点；耳甲前面一个小耳屏。耳垂厚一点、圆一点
        ear = U([ear, E.curve([(sg * 0.021, -0.02, 0.0), (sg * 0.025, -0.024, 0.06), (sg * 0.027, -0.008, 0.108), (sg * 0.027, 0.018, 0.112),
                               (sg * 0.026, 0.031, 0.08), (sg * 0.023, 0.03, 0.02), (sg * 0.02, 0.024, -0.04)],
                              [0.0045, 0.006, 0.0065, 0.0065, 0.006, 0.0055, 0.005])], 0.004, F)        # 耳轮的卷边
        ear = U([ear, E.ell((sg * 0.013, 0.006, -0.094), (0.0135, 0.021, 0.046))], 0.006, F)              # 耳垂
        ear = S(ear, E.curve([(sg * 0.03, -0.012, 0.086), (sg * 0.031, 0.004, 0.098), (sg * 0.03, 0.019, 0.086), (sg * 0.028, 0.022, 0.045),
                              (sg * 0.026, 0.017, -0.005)], 0.0042), 0.003, F)                                   # 耳舟
        ear = S(ear, E.ell((sg * 0.029, -0.003, 0.014), (0.0135, 0.0145, 0.031)), 0.004, F)               # 耳甲（深碗）
        ear = U([ear, E.curve([(sg * 0.024, -0.013, 0.074), (sg * 0.026, 0.004, 0.058), (sg * 0.025, 0.012, 0.022), (sg * 0.022, 0.008, -0.022)],
                              [0.0035, 0.0055, 0.0055, 0.004])], 0.004, F)                                     # 对耳轮
        ear = U([ear, E.curve([(sg * 0.025, 0.004, 0.058), (sg * 0.025, -0.008, 0.066), (sg * 0.023, -0.019, 0.058)], 0.0038)], 0.003, F)   # 对耳轮下脚
        ear = U([ear, E.ell((sg * 0.026, -0.021, -0.003), (0.0055, 0.0055, 0.0095))], 0.004, F)           # 耳屏
        ear = S(ear, E.curve([(sg * 0.025, 0.003, -0.066), (sg * 0.026, 0.005, -0.095), (sg * 0.025, 0.005, -0.118)], 0.005), 0.004, F)  # 耳垂的缝
        body = U([body, ear], 0.01, F)

    # ── 颈上三道：三道连续的弧形浅沟（每道一个解析的沟：深度处处一样，两头在颈侧慢慢收掉），不是一截截刻痕 ──
    def neck_lines(X, Y, Z):
        x, y, z = to_local(F, X, Y, Z)
        ph = np.arctan2(x, -(y - 0.008))
        c = np.cos(np.clip(ph, -1.6, 1.6))
        fade = 1 - ss(0.95, 1.3, np.abs(ph))
        h = np.zeros_like(x)
        for z0, dep in NECK_LINES:
            zc = z0 + 0.026 * (1 - c)              # 往两边、往后微微上弯（颈前低、颈侧高）
            h = h + dep * np.exp(-((z - zc) / 0.0032) ** 2)
        return (h * fade * F.s).astype(np.float32)
    body = sdf.Displace(body, neck_lines, F.k(0.004), box=fbox(F, (-0.13, -0.16, -0.33), (0.13, 0.06, -0.2), 0.03))
    if info is not None:
        info['neck_lines'] = NECK_LINES
    return body


# ====================================================================== 身子、袈裟
# 身子的坐标（B）：原点在莲台面的中心，-y 朝前，z 朝上。中尊：肩宽 0.96、两膝 1.6、坐高（台面到肉髻顶）2.0。
class Pose:
    """一尊佛的骨架点（身子坐标里）和手印。放在腿上的手、脚的高度要等腿的形做出来再贴上去（resolve）。

    左右：佛像面朝 -y（朝殿门），所以佛自己的右手边是 -x（观者的左边）。字典的键是 x 的正负号：
    R = -1 是佛的右手、右腿，L = +1 是左手、左腿。"""
    R, L = -1, 1

    def __init__(self, mudra):
        self.mudra = mudra
        R, L = self.R, self.L
        self.neck = V(0, 0.12, 1.18)
        self.sh = {R: V(-0.4, 0.13, 1.03), L: V(0.4, 0.13, 1.03)}
        self.hip = {R: V(-0.19, 0.17, 0.17), L: V(0.19, 0.17, 0.17)}
        self.knee = {R: V(-0.66, -0.36, 0.18), L: V(0.66, -0.36, 0.18)}
        # 结跏趺坐（吉祥坐）：右腿在上，右脚脚心朝上搁在左大腿上（观者右边）；左脚压在右腿下
        self.top = R
        self.foot = dict(d=(1, -0.42, 0.05), sole=(-0.05, -0.55, 0.84))
        self.ankle = {R: V(0.03, -0.25, 0.37), L: V(-0.22, -0.16, 0.2)}
        self.elbow = {R: V(-0.53, 0.04, 0.6), L: V(0.53, 0.04, 0.6)}
        # 每只手：wrist 腕的位置（放在腿上的只给 xy，高度贴着衣服算）；d 指尖方向；palm 手心朝向
        if mudra == 'teach':          # 中尊释迦：右手说法印（举在右胸前，观者左边），左手仰放在腿上
            self.elbow[R] = V(-0.5, -0.06, 0.6)
            self.hands = {L: dict(xy=(0.26, -0.43), lift=0.021, d=(-1, -0.1, 0.0), palm=(0, 0.05, 1), pose='RELAX'),
                          R: dict(wrist=(-0.33, -0.31, 0.86), d=(0.05, -0.16, 1), palm=(-0.5, -0.87, 0.06), pose='TEACH')}
        elif mudra == 'bowl':         # 药师：左手托药钵仰放在腿上（观者右边），右手垂在右膝前（与愿印，拈一颗诃子）
            self.elbow[R] = V(-0.56, 0.0, 0.56)
            self.hands = {L: dict(xy=(0.26, -0.43), lift=0.021, d=(-1, -0.1, 0.0), palm=(0, 0.05, 1), pose='RELAX'),
                          R: dict(wrist=(-0.6, -0.57, 0.44), d=(0.0, -0.18, -1), palm=(0.0, -1, 0.15), pose='VARADA')}
        else:                         # 阿弥陀：两手仰掌、右手叠在左手上（弥陀定印，两拇指尖相接），掌上托一朵莲花
            # 两手搁在仰起的脚心上（贴着小腹前），右手在上
            # 第五轮：两手抬高 3.5 厘米（评审：仰起的右脚脚心正压在手底下，脚趾那一排看不出来）：手和脚心之间空出一指多
            self.hands = {L: dict(wrist=(0.17, -0.31, 0.51), d=(-1, -0.22, 0.04), palm=(0, 0.04, 1), pose='DHYANA'),
                          R: dict(wrist=(-0.17, -0.34, 0.55), d=(1, -0.22, 0.04), palm=(0, 0.04, 1), pose='DHYANA_TOP')}
        self.wrist = {}
        for sx, h in self.hands.items():
            self.wrist[sx] = V(h['wrist']) if 'wrist' in h else V(h['xy'][0], h['xy'][1], 0.42)

    def cuff(self, sx):
        """袖口的中心：举起来的那只袖子滑下来一些，露出小臂"""
        el, wr = self.elbow[sx], self.wrist[sx]
        return wr + (el - wr) * (0.42 if wr[2] > 0.6 else 0.2)

    def resolve(self, B, lap):
        """把放在腿上的手、脚贴到腿上衣服的表面（lap 是腿那一团的距离场）"""
        def top(x, y):
            q, n, ok = surf(lap, [B.p(x, y, 1.2)], B.d(0, 0, -1), tmax=B.k(1.5))
            return (q[0][2] - B.o[2]) / B.s if ok[0] else 0.35
        for sx, h in self.hands.items():
            if 'xy' in h:
                d = V(h['d']) / np.linalg.norm(h['d'])
                c = V(h['xy'][0], h['xy'][1], 0) + d * 0.08
                self.wrist[sx] = V(h['xy'][0], h['xy'][1], top(c[0], c[1]) + h['lift'] * 1.18)


def body_core(B, P):
    """袈裟底下的身子：宽肩、胸膛饱满、细腰。胸口露在外面的那一小块也是它"""
    parts = [
        B.ell((0, 0.1, 0.87), (0.32, 0.19, 0.27)),                     # 胸廓
        B.ell((0, 0.05, 0.6), (0.25, 0.175, 0.21)),                    # 腹（微微鼓）
        B.ell((0, 0.1, 0.5), (0.27, 0.165, 0.19)),                     # 腰
        B.ell((0, 0.1, 0.22), (0.35, 0.21, 0.2)),                      # 胯（后面不要鼓成一个球：侧面看背是顺下来的）
    ]
    for sx in (-1, 1):
        parts.append(B.ell((sx * 0.12, -0.03, 0.92), (0.13, 0.06, 0.09)))        # 胸肌（很柔和）
        parts.append(B.sph(P.sh[sx], 0.115))
        parts.append(B.cone(P.neck + V(sx * 0.05, 0.01, -0.03), P.sh[sx] + V(0, 0, 0.02), 0.075, 0.09))
    return U(parts, 0.1, B)


def arm_core(B, P, sx):
    """胳膊：上臂、小臂（袖子里面的，用来撑袖子；露在袖口外的手腕是 hands 那边做）"""
    return U([B.cone(P.sh[sx], P.elbow[sx], 0.095, 0.08), B.cone(P.elbow[sx], P.wrist[sx], 0.075, 0.055)], 0.03, B)


def legs_core(B, P):
    parts = []
    for sx in (-1, 1):
        # 大腿：扁一点的长团（膝盖不是一个球）
        a, b = P.hip[sx], P.knee[sx] + V(sx * 0.03, -0.02, 0)
        d = (b - a) / np.linalg.norm(b - a)
        side = np.cross(V(0, 0, 1), d)
        side /= np.linalg.norm(side)
        R = np.stack([d, side, np.cross(d, side)], axis=1)
        parts.append(B.ell((a + b) / 2, (np.linalg.norm(b - a) / 2 + 0.06, 0.17, 0.13), R))
    t, b = P.top, -P.top          # 在上面的那条腿（右腿）、压在下面的（左腿）
    parts.append(B.cone(P.knee[t] + V(-0.04 * t, 0, 0.0), P.ankle[t] - (P.ankle[t] - P.knee[t]) / np.linalg.norm(P.ankle[t] - P.knee[t]) * 0.07, 0.12, 0.075))
    parts.append(B.cone(P.knee[b] + V(0.04 * t, 0, -0.02), P.ankle[b], 0.12, 0.08))
    return U(parts, 0.06, B)


def lap_volume(B, P):
    """腿上那一团衣服：两条腿裹在里面，两膝之间兜下去"""
    legs = sdf.Offset(legs_core(B, P), B.k(0.035))
    return U([legs, B.ell((0, -0.24, 0.08), (0.58, 0.34, 0.08))], 0.07, B)


def sleeve_axes(P, sx):
    """举起来那只袖子的坐标：E 肘下（袖子从这里垂）、a 顺着小臂、g 垂直于小臂往下、b 往外（离开身子）、L 长"""
    el, cuff = P.elbow[sx], P.cuff(sx)
    E = el + V(0, 0, -0.02)
    a = cuff - E
    L = float(np.linalg.norm(a))
    a = a / L
    g = V(0, 0, -1) - a * (-a[2])
    g /= np.linalg.norm(g)
    b = np.cross(a, g)
    if b[0] * sx < 0:
        b = -b
    return E, a, g, b, L


def flap_depth(t):
    """袖子垂下来的那一片，在小臂下面垂多深（t：0 肘，1 袖口）"""
    return 0.06 + 0.15 * np.clip(t, 0, 1) ** 1.25


def sleeve_flap(B, P, sx):
    """举起来那只胳膊的宽袖：从小臂底下垂下来薄薄的一片（双层布，往外微鼓），袖口那头是个斜的开口边。
    不是一大团：侧面看是一片，上面再压几道兜下来的弧形褶（folds 那边加）"""
    E, a, g, b, L = sleeve_axes(P, sx)

    def fn(X, Y, Z):
        x, y, z = to_local(B, X, Y, Z)
        rx, ry, rz = x - E[0], y - E[1], z - E[2]
        t = (rx * a[0] + ry * a[1] + rz * a[2]) / L
        q = rx * g[0] + ry * g[1] + rz * g[2]
        lat = rx * b[0] + ry * b[1] + rz * b[2]
        H = flap_depth(t)
        qn = np.clip(q / H, 0, 1)
        c = 0.016 * np.sin(np.pi * qn) + 0.01
        th = 0.011 + 0.017 * (1 - qn) ** 1.5
        d = np.abs(lat - c) - th
        d = sdf.smax(d, q - H, 0.02)
        d = np.maximum(d, -q - 0.03)              # 上面藏在袖筒里
        d = np.maximum(d, -t * L)
        d = sdf.smax(d, (t - 1.0) * L + 0.035 * qn, 0.03)       # 袖口那头的开口边（角是圆的）
        return (d * B.s).astype(np.float32)
    c0 = E + a * L * 0.5 + g * 0.1
    r = L * 0.5 + 0.3
    return sdf.Func(fn, B.p(c0 - r), B.p(c0 + r))


def forearm_r(P, sx, p):
    """手那边做的小臂（hands_of 里伸进袖口的那截圆台）在 p 处的半径"""
    wr, el = P.wrist[sx], P.elbow[sx]
    t = float(np.dot(V(p) - wr, el - wr) / np.dot(el - wr, el - wr))
    return 0.043 + (0.056 - 0.043) * float(np.clip((t - 0.06) / 0.44, 0, 1))


def cuff_axes(P, sx):
    """袖口的坐标：C 袖口中心，ax 顺着小臂往手那边，g 垂直于小臂往下，b 横"""
    el, wr = P.elbow[sx], P.wrist[sx]
    C = P.cuff(sx)
    ax = (wr - el) / np.linalg.norm(wr - el)
    g = V(0, 0, -1) - ax * (-ax[2])
    g = g / np.linalg.norm(g) if np.linalg.norm(g) > 0.15 else V(0, -1, 0)
    b = np.cross(ax, g)
    return C, ax, g, b


CUFF_PLUG = 0.07          # 袖口里挖进去多深（再往里是实的：从哪儿看都看不见袖筒里面）


def cuff_end(B, P, sx):
    """袖口那一截（一个开口）：上沿贴着小臂（布搭在胳膊上），下面垂下去 5~10 厘米成一道兜着的褶（举起的那只下面接着垂的那片），
    口沿一道软的卷边（一圈粗细不一样：底下垂的地方厚），开口略斜（下沿往回收一点）。
    返回 (袖口那一截的距离场, 口里挖掉的那一块)：口里只挖到小臂外面一厘米半、七厘米深，往下那道褶的里面只开一道窄缝（两层布）"""
    C, ax, g, b = cuff_axes(P, sx)
    rf = forearm_r(P, sx, C)
    raised = P.wrist[sx][2] > 0.6
    sag = 0.05 if raised else 0.095
    R0 = rf + 0.027

    def local(X, Y, Z):
        x, y, z = to_local(B, X, Y, Z)
        rx, ry, rz = x - C[0], y - C[1], z - C[2]
        return (rx * ax[0] + ry * ax[1] + rz * ax[2], rx * b[0] + ry * b[1] + rz * b[2], rx * g[0] + ry * g[1] + rz * g[2])

    def fn(X, Y, Z):
        a, u, v = local(X, Y, Z)
        flare = 1 + 0.32 * np.clip(-a / 0.2, 0, 1)
        dc = np.sqrt(u * u + v * v) - R0 * flare
        vl = rf + sag - 0.022
        tv = np.clip(v / vl, 0, 1)
        dd_ = np.sqrt(u * u + (v - tv * vl) ** 2) - (0.05 + (0.022 - 0.05) * tv) * flare
        d2 = sdf.smin(dc, dd_, 0.03)
        ph = np.arctan2(u, -v)                   # 0 在上面
        lip = (0.0042 + 0.0038 * (1 - np.cos(ph)) / 2 + 0.0012 * np.sin(3 * ph + 0.7)) * np.exp(-((a + 0.012) / 0.013) ** 2)
        d2 = d2 - lip
        a_end = -0.028 * np.clip(v / (rf + sag), 0, 1)
        d = sdf.smax(d2, a - a_end, 0.008)
        d = np.maximum(d, -a - 0.24)
        return (d * B.s).astype(np.float32)

    def cav(X, Y, Z):
        a, u, v = local(X, Y, Z)
        ds = np.sqrt(u * u + v * v) - (rf + 0.015)
        vl = rf + sag - 0.04
        tv = np.clip(v / vl, 0, 1)
        dsl = np.sqrt(u * u + (v - tv * vl) ** 2) - 0.0055
        dcv = sdf.smin(ds, dsl, 0.006) if not raised else ds
        dcv = np.maximum(dcv, np.maximum(-a - CUFF_PLUG, a - 0.06))
        return (dcv * B.s).astype(np.float32)
    lo, hi = B.p(C - 0.36), B.p(C + 0.36)
    return sdf.Func(fn, lo, hi), sdf.Func(cav, lo, hi)


def robe_volume(B, P, lap):
    """袈裟的大形（还没开领口、没刻衣纹）：身上贴身一层；放下的袖子从小臂往腿上垂；举起的袖子底下垂一片；腿上整个裹住。
    袖子在袖口往回 5 厘米处截住，接上 cuff_end 做的袖口那一截"""
    core = body_core(B, P)
    torso = sdf.Offset(core, B.k(0.032))
    parts = [torso, B.ell((0, 0.16, 0.6), (0.27, 0.14, 0.36)),           # 背上的衣服略松（不鼓成球）
             B.ell((0, 0.2, 1.14), (0.22, 0.13, 0.11))]                    # 后领：脖子后面的衣服立起来一点，包住颈根
    for sx in (-1, 1):
        sh, el, wr = P.sh[sx], P.elbow[sx], P.wrist[sx]
        raised = wr[2] > 0.6
        C, ax, g, b = cuff_axes(P, sx)
        rf = forearm_r(P, sx, C)
        cut_at = C - ax * 0.05
        ua = el + (sh - el) * 0.12
        arm = [sdf.Offset(arm_core(B, P, sx), B.k(0.026)),
               B.cone(sh + V(sx * 0.02, 0.0, -0.06), ua + V(sx * 0.03, 0.01, -0.05), 0.09, 0.104)]   # 上臂外面垂着的袖
        end, cav = cuff_end(B, P, sx)
        if raised:
            arm.append(B.cone(el + (wr - el) * 0.05, cut_at, 0.105, rf + 0.034))
            main = sdf.Inter(U(arm, 0.035, B), B.plane(cut_at, ax))
            flap = sdf.Inter(sleeve_flap(B, P, sx), B.plane(C, ax))
            parts.append(sdf.Sub(U([main, flap, end], 0.03, B), cav, B.k(0.006)))
        else:
            arm.append(B.cone(el + (wr - el) * 0.1, cut_at, 0.11, rf + 0.036))       # 小臂的袖，到袖口收一点
            # 袖子从小臂底下垂下来落到腿上（正面看胳膊和腿之间是一片衣服）：一整片布（排得很密的十四根，平滑地并成一片，
            # 不是四根一根根的「手指」），褶另外加
            web = []
            for t in np.linspace(0.08, 0.92, 14):
                a_ = el + (C - el) * t + V(0, 0, -0.05)
                leg = V(a_[0] * 1.0 + sx * 0.02, a_[1] - 0.02, 0.27)
                if a_[2] - leg[2] > 0.02:
                    web.append(B.cone(a_, leg, 0.048, 0.058))
            if web:
                arm.append(U(web, 0.03, B))
            main = sdf.Inter(U(arm, 0.05, B), B.plane(cut_at, ax))
            parts.append(sdf.Sub(U([main, end], 0.03, B), cav, B.k(0.006)))       # 只挖袖子自己（不挖到腿上的衣服）
    parts.append(lap)
    return U(parts, 0.06, B)


# 悬裳：袈裟的下摆从腿前沿出来，盖过莲座台沿，在仰莲正面垂下来三十厘米上下。厚重的布，绕着莲座的圆弧，
# 三个大的兜（中间那个最长、最深），每个兜里两三道套着的 U 形褶，兜和兜之间布收拢成一道竖的卷褶；下摆是跟着兜走的 U 形，
# 一道一厘米多厚的卷边，衣缘带子贴在卷边上面。身子坐标（台面中心为原点）。
DRAPE_W = 0.43           # 半宽
DRAPE_RW = 0.77          # 绕莲座的圆弧半径（前后再乘 0.92，和莲座一样扁）
DRAPE_T = 0.0065         # 布的半厚
DRAPE_RB = 0.0092        # 下摆卷边的半径
DRAPE_TOP = -0.025       # 从这里往下是直直垂下来的
DRAPE_PROF = np.array([(0.2, 0.078), (0.12, 0.066), (0.06, 0.052), (0.028, 0.036), (0.01, 0.016), (0.002, -0.004),
                       (0.0, DRAPE_TOP), (0.0, -0.5)])       # (离垂面往里多少, 高)：从腿前沿出来、翻过台沿、往下垂
# 三个兜：(左端 x, 右端 x, 左端下摆高, 右端下摆高, 兜深, 往前鼓)
DRAPE_SWAGS = ((-DRAPE_W, -0.15, -0.165, -0.2, 0.075, 0.012), (-0.15, 0.15, -0.2, -0.2, 0.105, 0.016),
               (0.15, DRAPE_W, -0.2, -0.165, 0.075, 0.012))
_HEM = {}


def drape_hem_z(x):
    """悬裳下摆的高度：三个 U 形的兜（兜和兜之间的尖角抹圆）"""
    if 'z' not in _HEM:
        xs = np.linspace(-0.6, 0.6, 1201)
        z = np.full_like(xs, -0.165)
        for x0, x1, z0, z1, dep, _ in DRAPE_SWAGS:
            t = np.clip((xs - x0) / (x1 - x0), 0, 1)
            m = (xs >= x0) & (xs <= x1)
            z = np.where(m, z0 + (z1 - z0) * t - dep * spow(np.sin(np.pi * t), 0.85), z)
        g = np.exp(-0.5 * (np.arange(-40, 41) * 0.001 / 0.011) ** 2)
        z = np.convolve(np.pad(z, 40, mode='edge'), g / g.sum(), mode='valid')
        _HEM['x'], _HEM['z'] = xs, z
    return np.interp(x, _HEM['x'], _HEM['z'])


def drape_base_y(x):
    """垂下来那一面的 y（绕着莲座的圆弧）"""
    return -np.sqrt(np.maximum(DRAPE_RW ** 2 - np.asarray(x) ** 2, 0.04)) * 0.92


def drape_disp(x, z):
    """垂下来那一面的起伏（往外为正，米）：每个兜往前鼓、兜里套着的 U 形褶、兜和兜之间一道竖的卷褶；两边往后收"""
    x = np.asarray(x)
    z = np.asarray(z)
    hang = ss(DRAPE_TOP + 0.01, DRAPE_TOP - 0.1, z)                 # 台沿上贴着，往下才鼓
    hz = drape_hem_z(x)
    sv = np.clip((DRAPE_TOP - z) / np.maximum(DRAPE_TOP - hz, 0.05), 0, 1.2)       # 0 在台沿，1 在下摆
    out = np.zeros(np.broadcast_shapes(x.shape, z.shape), np.float32)
    for x0, x1, z0, z1, dep, bel in DRAPE_SWAGS:
        t = np.clip((x - x0) / (x1 - x0), 0, 1)
        m = ((x >= x0) & (x <= x1)).astype(np.float32)
        across = spow(np.sin(np.pi * t), 0.9)
        out += m * bel * across ** 1.3 * hang
        # 兜里套着的 U 形褶：四道悬链线，两头都收到兜两头的台沿上（布挂在那两点上兜下来），越往外的一道兜得越深
        dmid = DRAPE_TOP - (0.5 * (z0 + z1) - dep)
        sag = dmid * np.maximum(spow(np.sin(np.pi * t), 0.9), 0.18)
        su = (DRAPE_TOP - z) / sag
        ends = ss(0.05, 0.2, np.minimum(t, 1 - t))
        for sk, amp in ((0.3, 0.004), (0.52, 0.0065), (0.72, 0.0085), (0.9, 0.0095)):
            q = (su - sk) / 0.09
            prof = np.where(q < 0, np.exp(-q * q), np.exp(-(q * 1.7) ** 2)) - 0.3 * np.exp(-((q - 1.25) / 0.55) ** 2)
            # 兜两头（兜尖、两边）四道褶挤成一把细梳子，抽网格后成了一截截皱巴巴的锯齿（鎏金一反光很显眼）：两头先收掉（第三轮）
            out += m * amp * prof * spow(across, 1.3) * (dep / 0.105) * (1 - ss(hz + 0.09, hz + 0.068, z)) * ends
    # 兜和兜之间：布收拢成一道竖的卷褶（一根圆的竖棱，两边各一道浅沟），到衣缘带子上面就收掉（带子底下的布是平的，什么也不顶出来）
    for xc in (-0.15, 0.15):
        r = (x - xc) / 0.017
        out += (0.011 * np.exp(-r * r) - 0.004 * np.exp(-((np.abs(r) - 1.9) / 0.7) ** 2)) * hang * (1 - ss(hz + 0.1, hz + 0.07, z))
    # 两边：布往后收（包着莲座），边是圆的
    out -= 0.022 * ss(DRAPE_W - 0.07, DRAPE_W, np.abs(x)) * hang
    return out


def drape(B):
    """悬裳（见上面的说明）。返回距离场"""
    prof = DRAPE_PROF

    def fn(X, Y, Z):
        x, y, z = to_local(B, X, Y, Z)
        x, y, z = np.broadcast_arrays(x, y, z)
        yb = drape_base_y(x)
        dsp = drape_disp(x, z)
        dl = y - yb + dsp                       # 离垂面往里（+）/往外（-）多少
        best = np.full(x.shape, 1e3, np.float32)
        for k in range(len(prof) - 1):
            a, b = prof[k], prof[k + 1]
            ab = b - a
            L2 = ab.dot(ab)
            t = np.clip(((dl - a[0]) * ab[0] + (z - a[1]) * ab[1]) / L2, 0, 1)
            dy, dz = dl - (a[0] + t * ab[0]), z - (a[1] + t * ab[1])
            best = np.minimum(best, np.sqrt(dy * dy + dz * dz))
        hz = drape_hem_z(x)
        d = best - DRAPE_T
        d = sdf.smax(d, hz + DRAPE_RB * 0.6 - z, 0.004)
        # 下摆的卷边：一根圆的，略往外
        bead = np.sqrt((dl + 0.0015) ** 2 + (z - hz - DRAPE_RB) ** 2) - DRAPE_RB
        d = np.minimum(d, bead)
        d = sdf.smax(d, np.abs(x) - DRAPE_W, 0.012)
        return (d * B.s).astype(np.float32)
    return sdf.Func(fn, B.p(-0.5, -0.8, -0.4), B.p(0.5, -0.35, 0.12))


def opening_cut(B, P, core):
    """前襟的开口（双领下垂）：领口贴着脖子两边下来，到肚子上收拢。挖掉的只是开口里那一层衣服（挖到身子表面往里一厘米），
    开口边是一道三四厘米厚的布边（领缘盖在上面），不会在胸口留下一面平墙"""
    def fn(X, Y, Z):
        x, y, z = to_local(B, X, Y, Z)
        d2 = np.abs(x) - open_w(z)
        d2 = np.maximum(d2, (OPEN_Z[-1] - z))
        return np.maximum(d2, y - 0.06) * B.s
    shell = sdf.Sub(sdf.Func(fn, B.p(-0.3, -0.5, 0.35), B.p(0.3, 0.07, 1.5)), sdf.Offset(core, B.k(-0.01)))
    return shell


# ---------------------------------------------------------------- 衣服上的边、褶
def surf(node, pts, dirs, tmax=0.5):
    """把点沿 dirs 贴到 node 表面上，返回 (贴上的点, 表面法线, 贴上了没有)"""
    P = np.asarray(pts, np.float64).reshape(-1, 3)
    D = np.broadcast_to(np.asarray(dirs, np.float64), P.shape)
    D = D / np.linalg.norm(D, axis=1, keepdims=True)
    P = np.where((sdf.ev_points(node, P) < 0)[:, None], P - D * tmax * 0.5, P)    # 起点在形体里面的，先退出来
    Q = sdf.project(node, P, D, tmax=tmax, n=120)
    ok = np.abs(sdf.ev_points(node, Q)) < 0.004
    N = sdf.grad(node, Q, 1e-3)
    return Q, N, ok


def ribbon(P, N, w, t, k=0.0, taper=None):
    """一条扁带子（绅带）：P 中线上的点，N 带子厚度的方向，w 宽，t 厚。taper：每个点一个宽度系数"""
    boxes = []
    n = len(P)
    for i in range(n - 1):
        a, b = V(P[i]), V(P[i + 1])
        d = b - a
        L = np.linalg.norm(d)
        if L < 1e-6:
            continue
        d /= L
        nn = V(N[i]) + V(N[i + 1])
        nn -= d * nn.dot(d)
        nn /= max(np.linalg.norm(nn), 1e-9)
        side = np.cross(nn, d)
        R = np.stack([d, side, nn], axis=1)
        ww = w if taper is None else w * 0.5 * (taper[i] + taper[i + 1])
        boxes.append(sdf.Box((a + b) / 2, V(L / 2 + t * 0.7, ww / 2, t / 2), R, rnd=t * 0.45))
    return sdf.Union(boxes, k)


def fold_curve(B, node, pts, dirs, n=5, min_len=0.12):
    """身子坐标里画的一道线 → 贴到表面上的一串点和法线。贴不上、离得太远的相邻点处断开（不然一道褶会从空中穿过去）；
    每段按 8 毫米重新取点、来回抹顺几遍再贴回表面（褶棱是顺的一条，不是一截截锯齿）；短于 min_len 的段不要"""
    W = np.array([B.p(q) for q in sdf.catmull([V(q) for q in pts], n * 3)])
    if isinstance(dirs, list):
        D = np.array([B.d(*dd) for dd in sdf.catmull([V(q) for q in dirs], n * 3)])
    elif callable(dirs):
        D = np.array([B.d(*dirs(V(q))) for q in sdf.catmull([V(q) for q in pts], n * 3)])
    else:
        D = np.array([B.d(*dirs)] * len(W))
    D /= np.linalg.norm(D, axis=1, keepdims=True)
    Q, N, ok = surf(node, W - D * B.k(0.35), D, tmax=B.k(0.8))
    out = []
    idx = np.nonzero(ok)[0]
    if len(idx) < 4:
        return out
    br = np.nonzero((np.diff(idx) > 1) | (np.linalg.norm(np.diff(Q[idx], axis=0), axis=1) > B.k(0.05)))[0]
    for a_, b_ in zip(np.concatenate([[0], br + 1]), np.concatenate([br + 1, [len(idx)]])):
        if b_ - a_ < 4:
            continue
        q = Q[idx[a_:b_]]
        if np.linalg.norm(np.diff(q, axis=0), axis=1).sum() < B.k(min_len):
            continue
        q = resample(q, B.k(0.008))
        for _ in range(3):
            for _ in range(6):
                q[1:-1] = (q[:-2] + 2 * q[1:-1] + q[2:]) / 4
            q = sdf.snap(node, q, iters=3)
        nn = sdf.grad(node, q, 1e-3)
        for _ in range(8):
            nn[1:-1] = (nn[:-2] + 2 * nn[1:-1] + nn[2:]) / 4
            nn /= np.linalg.norm(nn, axis=1, keepdims=True)
        out.append((q, nn))
    return out


OPEN_Z = np.array([1.45, 1.22, 1.08, 0.94, 0.8, 0.66, 0.56, 0.49, 0.44])
OPEN_W = np.array([0.17, 0.175, 0.19, 0.205, 0.195, 0.16, 0.11, 0.058, 0.0])


def open_w(z):
    return np.interp(z, OPEN_Z[::-1], OPEN_W[::-1])


def inner_top(x):
    """僧祇支（里面那件）上沿的高度：胸口一道，两边略往上"""
    return 0.79 + 0.07 * np.clip(np.abs(x) / 0.22, 0, 1.2) ** 2


def inner_garment(B, P, core):
    """胸口里面那件：贴着身子一层，上沿到胸口"""
    thick = sdf.Offset(core, B.k(0.013))

    def fn(X, Y, Z):
        x, y, z = to_local(B, X, Y, Z)
        return (z - inner_top(x)) * B.s
    return sdf.Inter(thick, sdf.Func(fn, B.p(-0.4, -0.4, 0.3), B.p(0.4, 0.5, 1.0)), B.k(0.004))


def inner_folds(B, garment):
    """僧祇支上的软褶（第三轮）：胸前那件被绅带束住，带子下面的布往下散开四道浅褶（以前是一整片光溜溜的鼓面）。
    正中间留空（绅带的两条带尾垂在那里）；靠两襟的那两道短一点（下面衣服开口收窄了）。返回给 sdf.Folds 的列表"""
    out = []
    for x0, x1, z0, z1, amp, sg in ((-0.058, -0.098, 0.737, 0.535, 0.008, -1), (0.054, 0.09, 0.737, 0.545, 0.008, 1),
                                    (-0.122, -0.15, 0.757, 0.64, 0.0065, -1), (0.118, 0.144, 0.757, 0.645, 0.0065, 1)):
        pts = [(x0 + (x1 - x0) * t, -0.3, z0 + (z1 - z0) * t) for t in np.linspace(0, 1, 6)]     # 从前面往里贴（fold_curve 只往里找 0.8）
        for Q, N in fold_curve(B, garment, pts, (0, 1, 0), n=4, min_len=0.08):
            out.append(dict(P=Q, N=N, amp=B.k(amp), w1=B.k(0.008), w2=B.k(0.02), sign=sg, taper=0.3, depth=B.k(0.03)))
    return out


def resample(Q, step, closed=False):
    """把折线按弧长重新取点（每 step 米一个）"""
    Q = np.asarray(Q, np.float64)
    if closed:
        Q = np.vstack([Q, Q[:1]])
    L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))])
    n = max(int(L[-1] / step), 2)
    s = np.linspace(0, L[-1], n + (0 if closed else 1))[: (n if closed else n + 1)]
    return np.stack([np.interp(s, L, Q[:, i]) for i in range(3)], axis=1)


def collar_path(B, robe0):
    """领缘：左襟从肚子沿开口上去、绕过脖子后面、右襟下来，一整条连续的线（贴在衣服表面上），返回身子坐标里的控制点"""
    zs = np.linspace(0.5, 1.16, 9)
    left = [(open_w(z) + 0.034, -0.6, z) for z in zs]
    arc = []
    for ph in np.linspace(0.92, -0.92, 15):          # 从左肩经脖子后面到右肩（ph 是绕颈的角，0 = 正后方），从上往下贴到肩上
        a = math.pi * ph * 0.6
        arc.append((0.2 * math.sin(a), 0.1 + 0.2 * math.cos(a), 1.7))
    right = [(-(open_w(z) + 0.034), -0.6, z) for z in zs[::-1]]
    return left, arc, right


def project_path(B, node, left, arc, right):
    """把 collar_path 的三段贴到表面上：两襟从正前方往里贴，绕颈那段从上往下贴到肩上。返回 (点, 法线)，按 5 毫米重取过"""
    Ls = []
    for seg, D0 in ((left, (0, 1, 0)), (arc, (0, 0, -1)), (right, (0, 1, 0))):
        W = np.array([B.p(q) for q in seg])
        D = np.array([B.d(*D0)] * len(W))
        Q, N, ok = surf(node, W - D * B.k(0.1), D, tmax=B.k(0.9))
        Ls.append(Q[ok])
    Q = np.vstack(Ls)
    Q = np.array(sdf.catmull(list(Q), 6))
    Q = resample(Q, B.k(0.008))
    for _ in range(3):
        Q[1:-1] = (Q[:-2] + 2 * Q[1:-1] + Q[2:]) / 4
    Q = sdf.snap(node, Q, iters=4)
    N = sdf.grad(node, Q, 1e-3)
    for _ in range(6):                 # 法线顺一顺（不要一节一节地拧）
        N[1:-1] = (N[:-2] + 2 * N[1:-1] + N[2:]) / 4
        N /= np.linalg.norm(N, axis=1, keepdims=True)
    return Q, N


def knot(B, core, info):
    """胸前的绅带结：中间一道缠着的箍，两个扁的、往下垂的带圈，两条带尾垂下来（尾巴斜着剪，中间折一下）。返回距离场的一块"""
    kq, kn, ok = surf(core, [B.p(0, -0.6, inner_top(0.0) - 0.02)], B.d(0, 1, 0), tmax=1.0)
    nn = kn[0]
    K = kq[0] + nn * B.k(0.017)
    up = B.d(0, 0, 1)
    up = up - nn * up.dot(nn)
    up /= np.linalg.norm(up)
    side = np.cross(up, nn)
    parts = [sdf.Box(K, B.k(V(0.011, 0.016, 0.009)), np.stack([side, up, nn], axis=1), B.k(0.005))]
    for sg in (-1, 1):
        # 带圈：扁带子对折成的一个往外、往下垂的叶形圈（正面看见的是带子的宽面，中间一道折痕），靠结那头收细
        e1 = side * sg * 0.84 - up * 0.54
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(nn, e1)
        Rl = np.stack([e1, e2, nn], axis=1)
        lobe = sdf.Union([sdf.Ellipsoid(K + e1 * B.k(0.036) - nn * B.k(0.003), B.k(V(0.03, 0.0145, 0.0062)), Rl),
                          sdf.Ellipsoid(K + e1 * B.k(0.012), B.k(V(0.014, 0.007, 0.0055)), Rl)], B.k(0.008))
        crease = sdf.Ellipsoid(K + e1 * B.k(0.04) + nn * B.k(0.0035), B.k(V(0.022, 0.0022, 0.003)), Rl)
        lobe = sdf.Sub(lobe, crease, B.k(0.0015))
        parts.append(lobe)
        # 带尾：贴着衣服往下垂，越往下越往外，尾巴斜剪；中间一处折一下（带子往外翻一点）
        tail, tn = [], []
        for t in np.linspace(0, 1, 12):
            p = K - up * B.k(0.012 + 0.19 * t) + side * sg * B.k(0.01 + 0.035 * t + 0.012 * math.sin(math.pi * t * 1.6)) \
                + nn * B.k(0.006 * math.sin(math.pi * min(1, t * 1.8)))
            tail.append(p)
        Q, N, ok = surf(core, [q + nn * B.k(0.2) for q in tail], -nn, tmax=B.k(0.5))
        Q = np.where(ok[:, None], Q + N * B.k(0.017), np.array(tail))
        N = np.where(ok[:, None], N, nn)
        rb = ribbon(Q, N, B.k(0.026), B.k(0.004), 0.0, list(np.linspace(0.85, 1.0, len(Q))))
        tip = Q[-1]
        cutn = -up * 0.8 + side * sg * 0.6
        rb = sdf.Sub(rb, sdf.Plane(tip - up * B.k(0.004) - cutn * B.k(0.006), -cutn))      # 尾巴斜着剪
        parts.append(rb)
    info['knot'] = K
    return sdf.Union(parts, B.k(0.002))


FOLD_K = 1.85     # 衣褶的棱高统一放大（第三轮 1.3；第四轮评审：从游戏镜头看还是光溜溜的塑料，再放大四成多，褶棱在殿里的灯下才分得出明暗）


def fold_set(B, P, robe):
    """衣褶：按布受力的方向排成一组一组连续的长褶（每道 25~100 厘米），截面是圆的棱（棱顶半径 ≥ 6 毫米、一边陡一边缓，两边各有一道浅沟）：
    两膝之间腿前兜着的三四道同心弧、上面那条小腿上顺着往脚踝去的三道斜褶、上臂从肩往肘弯里斜下去的三四道、
    放下的袖子从小臂垂到膝上的三道长弧、举起那只袖子底下垂着的三道竖褶、腰到膝盖绷着的两道、胸侧两道、背上两道。返回给 sdf.Folds 的列表"""
    out = []

    # 第五轮：褶棱收窄（陡的那一面 13 → 10 毫米、缓的那一面 34 → 28 毫米）：同样高的褶，两边的坡更陡，殿里的灯下明暗分得开
    def add(pts, dirs, amp, w1=0.010, w2=0.028, sign=1.0, taper=0.22, depth=0.06, n=5, min_len=0.12):
        for Q, N in fold_curve(B, robe, pts, dirs, n, min_len):
            out.append(dict(P=Q, N=N, amp=B.k(amp), w1=B.k(w1), w2=B.k(w2), sign=sign, taper=taper, depth=B.k(depth)))

    def to_axis(a, b):
        """往线段 ab 上贴的方向（胳膊、腿那样的圆柱面）"""
        a, b = V(a), V(b)

        def f(q):
            t = np.clip((q - a).dot(b - a) / (b - a).dot(b - a), 0, 1)
            d = a + (b - a) * t - q
            return d / max(np.linalg.norm(d), 1e-9)
        return f

    for sx in (-1, 1):
        sh, el, wr = P.sh[sx], P.elbow[sx], P.wrist[sx]
        raised = wr[2] > 0.6
        C, ax, g, b = cuff_axes(P, sx)
        # 上臂：从肩头前面往肘弯里斜着下去的四道（一道比一道低，长 30 厘米上下）
        for k in range(4):
            t0 = 0.02 + 0.17 * k
            a_ = sh + (el - sh) * t0 + V(sx * 0.07, -0.07, 0.05)
            e_ = el + (sh - el) * (0.05 + 0.04 * k) + V(-sx * 0.05, -0.1, -0.01 - 0.02 * k)
            m_ = (a_ + e_) / 2 + V(sx * 0.03, -0.05, 0.0)
            add([a_, m_, e_], to_axis(sh, el), FOLD_K * (0.012 - 0.001 * k), sign=sx, min_len=0.15)
        # 胸侧：腋下往腰收的两道
        for k, zz in enumerate((0.92, 0.78)):
            a_ = V(sx * 0.34, -0.06, zz + 0.12)
            e_ = V(sx * (0.21 + 0.04 * k), -0.22, zz - 0.26)
            add([a_, (a_ + e_) / 2 + V(sx * 0.025, -0.03, 0), e_], (0, 1, 0), FOLD_K * 0.01, sign=sx)
        if raised:
            # 举起来那只袖子底下垂的那一片：三道长长的竖褶（从小臂底下直直垂到下沿），不是一圈套一圈
            E, a_, g_, b_, L = sleeve_axes(P, sx)
            for t in (0.36, 0.6, 0.84):
                H_ = flap_depth(t)
                pts = [E + a_ * t * L + g_ * (0.03 + H_ * 0.9 * u) + b_ * 0.15 for u in np.linspace(0, 1, 6)]
                add(pts, tuple(-b_), FOLD_K * 0.011, w1=0.011, w2=0.026, sign=1.0, taper=0.2, min_len=0.06)
        else:
            # 放下的袖子：从小臂底下垂到膝上的三道长弧
            kn = P.knee[sx]
            for j, t in enumerate((0.2, 0.5, 0.8)):
                a_ = el + (C - el) * t + V(sx * 0.02, -0.02, -0.07)
                e_ = V(kn[0] * (0.78 + 0.06 * t) + sx * 0.02, kn[1] * (0.4 + 0.5 * t) + 0.02, 0.3)
                m_ = (a_ + e_) / 2 + V(sx * 0.08, -0.04, 0.0)
                add([a_, m_, e_], (-sx, 0.15, 0.05), FOLD_K * 0.012, sign=-sx, min_len=0.15)
        # 腰到膝盖：大腿上绷着的两道（从腰侧斜着拉到膝头）
        kn = P.knee[sx]
        for k in range(2):
            a_ = V(sx * (0.24 + 0.04 * k), -0.28, 0.42 - 0.04 * k)
            e_ = kn + V(-sx * 0.05, -0.08 + 0.03 * k, 0.12 - 0.02 * k)
            add([a_, (a_ + e_) / 2 + V(0, -0.04, 0.03), e_], (0, 0.3, -1), FOLD_K * 0.011, sign=-sx, min_len=0.2)
        # 膝头外侧：布从膝盖上面顺着腿的外侧垂到台面上的三道（膝盖不是一个光溜溜的球）
        for k in range(3):
            a_ = kn + V(sx * 0.05, -0.1 + 0.08 * k, 0.15)
            m_ = kn + V(sx * 0.17, -0.08 + 0.08 * k, 0.04)
            e_ = kn + V(sx * 0.2, -0.06 + 0.09 * k, -0.13)
            add([a_, m_, e_], (-sx, 0.0, -0.25), FOLD_K * 0.011, sign=sx if k % 2 else -sx, min_len=0.15)
        # 背上：从肩胛往下垂的两道
        for t in (0.1, 0.24):
            a_ = V(sx * t, 0.42, 1.02)
            e_ = V(sx * (t + 0.05), 0.4, 0.4)
            add([a_, (a_ + e_) / 2 + V(sx * 0.02, 0.02, 0), e_], (0, -1, 0), 0.01, sign=sx)
    # 两膝之间：衣服绷在两膝上、在腿前兜下来的四道同心弧（坐像腿上最典型的衣纹；越往下兜得越深，接到悬裳上）
    kl, kr = P.knee[P.L], P.knee[P.R]
    for k in range(4):
        sag = 0.05 + 0.035 * k
        a_ = V(kr[0] * (0.86 - 0.03 * k), kr[1] - 0.12, kr[2] + 0.06 - 0.01 * k)
        e_ = V(kl[0] * (0.86 - 0.03 * k), kl[1] - 0.12, kl[2] + 0.06 - 0.01 * k)
        pts = [a_ + (e_ - a_) * u + V(0, -0.1 * math.sin(math.pi * u), -sag * math.sin(math.pi * u)) for u in np.linspace(0, 1, 9)]
        add(pts, (0, 0.75, -0.65), FOLD_K * (0.012 - 0.0008 * k), sign=1.0, taper=0.15, min_len=0.3)
    # 上面那条腿（右小腿）：顺着小腿往脚踝去的三道斜褶（略绕着腿转）
    t = P.top
    kn, an = P.knee[t], P.ankle[t]
    for k, off in enumerate((-0.05, 0.0, 0.05)):
        a_ = kn + V(-t * 0.03, off - 0.09, 0.13 + 0.02 * k)
        e_ = an + V(t * 0.12, off - 0.06, 0.04 - 0.02 * k)
        m_ = (a_ + e_) / 2 + V(0, -0.035, 0.05)
        add([a_, m_, e_], (0, 0.35, -1), FOLD_K * 0.012, sign=1.0 if k % 2 else -1.0, min_len=0.25)
    return out


def robe_details(B, P, robe, core, info):
    """袈裟上的衣缘（宽边）、领口、袖口、腰带结和一道道衣褶。
    返回 (加上去的, 刻下去的, 衣褶列表)。衣缘都记在 info['strips']（贴手绘纹样的带子网格）"""
    add, cut = [], []
    strips = info.setdefault('strips', [])
    # ── 领缘：左襟—绕颈—右襟一整条，先在衣服的开口边上加一道圆的厚边（布边不是刀刃），带子贴在上面 ──
    left, arc, right = collar_path(B, robe)
    Q, N = project_path(B, robe, left, arc, right)
    if len(Q) > 10:
        # 厚边：沿领缘往里（衣服里）沉一点的一根管子，把开口的刀口边包圆
        # 第四轮：衣缘做成凸起的一道厚边（评审：衣缘只是画上去的一条红带子，从游戏镜头看肩上、胸前平平的）
        add.append(sdf.chain(list(Q[::4] - N[::4] * B.k(0.004)), B.k(0.017)))
        strips.append(dict(Q=Q + N * B.k(0.006), N=N, w=B.k(0.08), t=B.k(0.012), sink=B.k(0.014), dense=True))
        # 第五轮：衣缘外侧（离开开口、肩上那一边）贴着厚边刻一道窄沟，厚边就像压在衣服上面、底下掏空了一点（评审：衣缘没有落差），
        # 灯从上面照下来，衣缘外沿一道细细的阴影线，从游戏镜头看肩上、胸前的衣缘是一层压一层的
        T_ = np.gradient(Q, axis=0)
        T_ /= np.maximum(np.linalg.norm(T_, axis=1, keepdims=True), 1e-9)
        side = np.cross(T_, N)
        side /= np.maximum(np.linalg.norm(side, axis=1, keepdims=True), 1e-9)
        ql = np.array([to_local(B, *q) for q in Q])
        sl = np.array([to_local(B, *(q + sd * B.k(0.03))) for q, sd in zip(Q, side)])
        r0 = np.hypot(ql[:, 0], ql[:, 1] - 0.1)
        r1 = np.hypot(sl[:, 0], sl[:, 1] - 0.1)
        side = np.where((r1 > r0)[:, None], side, -side)
        for _ in range(6):
            side[1:-1] = (side[:-2] + 2 * side[1:-1] + side[2:]) / 4
        side /= np.maximum(np.linalg.norm(side, axis=1, keepdims=True), 1e-9)
        groove = Q + side * B.k(0.026) - N * B.k(0.002)
        cut.append((sdf.chain(list(groove[::4]), B.k(0.0055)), 0.002))
    # ── 僧祇支上沿的一道边、胸前的绅带结 ──
    xs = np.linspace(-0.27, 0.27, 28)
    pts = [(x, -0.6, inner_top(x) - 0.012) for x in xs]
    Q, N, ok = surf(sdf.Offset(core, B.k(0.013)), [B.p(q) for q in pts], B.d(0, 1, 0), tmax=1.0)
    Q, N = Q[ok], N[ok]
    if len(Q) > 2:
        strips.append(dict(Q=Q, N=N, w=B.k(0.034), t=B.k(0.007)))
    info['knot_node'] = knot(B, core, info)
    # ── 袖口（口里挖的那一截在 robe_volume 里只挖袖子自己） ──
    for sx in (-1, 1):
        el, wr = P.elbow[sx], P.wrist[sx]
        C, ax, g, b = cuff_axes(P, sx)
        if 0.4 < wr[2] <= 0.6:
            # 垂在膝前的那只手（与愿印）：袖口以外、手腕那边的衣服（腿上那团）切掉一小块，手腕不埋在衣服里
            cut.append(sdf.Inter(sdf.Plane(B.p(C + ax * 0.01), -B.d(*ax)), B.sph(C + ax * 0.07, 0.15)))
    # 右小腿的衣服在脚踝那里收口：一圈带子
    t = P.top
    ax = P.ankle[t] - P.knee[t]
    ax /= np.linalg.norm(ax)
    a1 = np.cross(ax, V(0, 0, 1))
    a1 /= np.linalg.norm(a1)
    a2 = np.cross(ax, a1)
    hem = P.ankle[t] - ax * 0.07
    angs = np.linspace(0, 2 * math.pi, 49)
    ring_pts = np.array([B.p(hem - ax * 0.024 + (a1 * math.cos(a) + a2 * math.sin(a)) * 0.3) for a in angs])
    ctr = np.array([B.p(hem - ax * 0.024) for a in angs])
    Q, N, ok = surf(robe, ring_pts, ctr - ring_pts, tmax=B.k(0.3))
    if ok.all():
        strips.append(dict(Q=Q, N=N, w=B.k(0.045), t=B.k(0.008), closed=True))
    # 悬裳下摆一道衣缘：贴在卷边上面，跟着三个兜走（从正面贴上去）
    xs = np.linspace(-(DRAPE_W - 0.03), DRAPE_W - 0.03, 161)
    pts = np.array([B.p(x, -1.2, drape_hem_z(x) + 2 * DRAPE_RB + 0.022) for x in xs])
    Q, N, ok = surf(robe, pts, B.d(0, 1, 0), tmax=B.k(0.8))
    if ok.mean() > 0.9:
        strips.append(dict(Q=Q[ok], N=N[ok], w=B.k(0.042), t=B.k(0.006)))
    return add, cut, fold_set(B, P, robe)


# ====================================================================== 手
# 手的局部坐标（右手）：原点在腕横纹中间，x 指向指尖，-z 是手心朝的方向（手心朝下放平），y 是拇指那边。左手照镜子（y 反过来）。
# 单位：米（中尊的大小）。手长（腕到中指尖）约 0.29，手指修长、指尖略翘，指间有一点蹼（缦网相）。
FINGERS = {   # 名字: (掌骨末端 x, 横向 y, 三节长度, 三节半径)。指尖收细到指根的七成（明代金铜像的手指修长、尖细，不是一根根香肠）
    'index': (0.142, 0.036, (0.056, 0.036, 0.028), (0.0117, 0.0103, 0.0091)),
    'middle': (0.147, 0.012, (0.061, 0.040, 0.030), (0.0119, 0.0105, 0.0093)),
    'ring': (0.143, -0.012, (0.057, 0.038, 0.028), (0.0113, 0.0099, 0.0088)),
    'little': (0.133, -0.034, (0.045, 0.029, 0.025), (0.0101, 0.0089, 0.0079)),
}
TIP = 0.7         # 指尖半径 / 指根半径


def _rot(axis, ang):
    axis = V(axis) / np.linalg.norm(axis)
    x, y, z = axis
    c, s_ = math.cos(ang), math.sin(ang)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s_, x * z * C + y * s_],
                     [y * x * C + z * s_, c + y * y * C, y * z * C - x * s_],
                     [z * x * C - y * s_, z * y * C + x * s_, c + z * z * C]])


def finger_points(base, d, n, lens, flex, spread=0.0):
    """一根手指的四个关节点：base 是指根，d 是掌的方向，n 是手背朝的方向（弯曲是往 -n 弯）。flex 三个角度（度）"""
    side = np.cross(n, d)
    d = _rot(n, math.radians(spread)) @ d
    pts = [V(base)]
    cur = V(base)
    dd = d.copy()
    for L, f in zip(lens, flex):
        dd = _rot(side, math.radians(f)) @ dd
        cur = cur + dd * L
        pts.append(cur)
    return pts


def two_link(a, target, l1, l2, pole):
    """两节的链从 a 伸到 target：返回中间那个关节（往 pole 那边拐）。够不着就伸直了指过去"""
    a, target, pole = V(a), V(target), V(pole)
    dv = target - a
    L = np.linalg.norm(dv)
    dn = dv / max(L, 1e-9)
    L = min(L, (l1 + l2) * 0.999)
    x = (l1 * l1 - l2 * l2 + L * L) / (2 * L)
    h = math.sqrt(max(l1 * l1 - x * x, 0.0))
    p = pole - dn * pole.dot(dn)
    p /= max(np.linalg.norm(p), 1e-9)
    return a + dn * x + p * h


def hand(F, pose, info=None, nails=True):
    """一只手（F 是 hand_frame 给的坐标，左右手都按右手写）。pose：每根手指的 (张开角, 三节弯曲角)，拇指另有写法"""
    parts = []
    # 掌：扁的团，掌心那面有大小鱼际两块肉
    parts.append(F.ell((0.072, 0.0, 0.0), (0.078, 0.05, 0.018)))
    parts.append(F.ell((0.118, 0.0, 0.002), (0.036, 0.056, 0.016)))
    parts.append(F.ell((0.045, 0.026, -0.008), (0.034, 0.018, 0.011)))           # 大鱼际（收三成多：不鼓成一个球）
    parts.append(F.ell((0.064, -0.03, -0.006), (0.04, 0.013, 0.009)))            # 小鱼际
    parts.append(F.ell((-0.008, 0, -0.001), (0.036, 0.04, 0.021)))               # 腕：宽是掌的八成，扁的（不是一个圆球）
    palm = U(parts, 0.016, F)
    n = V(0, 0, 1)
    tips = {}
    fing = []
    knuckles, creases = [], []
    for nm, (bx, by, lens, rads) in FINGERS.items():
        spread, flex = pose[nm]
        base = V(bx - 0.014, by, 0.002)
        pts = finger_points(base, V(1, 0, 0), n, lens, flex, spread)
        r = list(rads) + [rads[0] * TIP]
        # 末节：指肚略扁、指尖收成一个小圆头（不加大球）
        f = F.curve(pts, r, n=4, k=0.004)
        dv = (pts[3] - pts[2]) / np.linalg.norm(pts[3] - pts[2])
        side = np.cross(n, dv)
        side /= np.linalg.norm(side)
        nn = np.cross(dv, side)
        nn /= np.linalg.norm(nn)
        f = U([f, F.ell(pts[3] - dv * 0.011 - nn * r[3] * 0.25, (0.012, r[3] * 0.95, r[3] * 0.82),
                        np.stack([dv, side, nn], axis=1))], 0.003, F)          # 指肚（手心那一面）
        if nails:
            nc = pts[3] - dv * 0.0098 + nn * (r[3] * 0.93)
            Rn = np.stack([dv, side, nn], axis=1)
            nail = sdf.Ellipsoid(F.p(nc), F.k(V(0.0102, r[3] * 0.78, 0.0019)), F.r(Rn))
            f = U([f, nail], 0.0006, F)
        fing.append(f)
        tips[nm] = pts[3]
        # 指背的骨节：掌指关节（手背上一排四个小鼓包）、中节关节上一点点
        for j, (pj, rj, amt) in enumerate(((pts[0], r[0], 0.55), (pts[1], r[1], 0.45))):
            dj = (pts[j + 1] - pts[j]) / np.linalg.norm(pts[j + 1] - pts[j])
            sj = np.cross(n, dj)
            sj /= np.linalg.norm(sj)
            nj = np.cross(dj, sj)
            nj /= np.linalg.norm(nj)
            knuckles.append(F.ell(pj + nj * rj * amt + dj * 0.003, (0.0085, rj * 0.72, rj * 0.5), np.stack([dj, sj, nj], axis=1)))
        # 手心那一面每个关节一道细横纹
        for j in (1, 2):
            dj = (pts[j + 1] - pts[j - 1])
            dj /= np.linalg.norm(dj)
            sj = np.cross(n, dj)
            sj /= np.linalg.norm(sj)
            nj = np.cross(dj, sj)
            nj /= np.linalg.norm(nj)
            c = pts[j] - nj * r[j] * 1.0
            creases.append(F.cone(c - sj * r[j] * 0.8, c + sj * r[j] * 0.8, 0.0015))
    # 拇指：掌骨从掌根斜着出去，后两节按目标点伸过去（捏指的手印要碰到食指尖）
    cmc = V(0.026, 0.03, -0.01)
    td = V(pose.get('thumb_dir', (0.72, 0.55, -0.42)))
    td /= np.linalg.norm(td)
    mcp = cmc + td * pose.get('thumb_meta', 0.05)
    l1, l2 = pose.get('thumb_len', (0.041, 0.032))
    if 'thumb_at' in pose:                 # 指定的点（局部坐标）：两手拇指尖相接的定印
        tgt = V(pose['thumb_at'])
    elif 'thumb_to' in pose:
        nm, off = pose['thumb_to']
        tgt = tips[nm] + V(off)
    else:
        tgt = mcp + V(pose.get('thumb_tip', (0.06, 0.006, -0.03)))
    pole = V(pose.get('thumb_pole', (0.2, 0.9, 0.4)))
    ip = two_link(mcp, tgt, l1, l2, pole)
    tip = ip + (tgt - ip) / np.linalg.norm(tgt - ip) * l2
    pts = [cmc, mcp, ip, tip]
    th = F.curve(pts, [0.0165, 0.0138, 0.0118, 0.0094], n=4, k=0.006)
    dv = (tip - ip) / np.linalg.norm(tip - ip)
    if nails:
        nn = V(pose.get('thumb_nail', (0.0, 0.6, 0.8)))
        nn = nn - dv * nn.dot(dv)
        nn /= np.linalg.norm(nn)
        side = np.cross(nn, dv)
        Rn = np.stack([dv, side, nn], axis=1)
        th = U([th, sdf.Ellipsoid(F.p(tip - dv * 0.011 + nn * 0.0104), F.k(V(0.0112, 0.0085, 0.0022)), F.r(Rn))], 0.0006, F)
    tips['thumb'] = tip
    fing.append(th)
    # 指根之间的蹼
    webs = []
    names = ['index', 'middle', 'ring', 'little']
    for a, b in zip(names[:-1], names[1:]):
        pa = V(FINGERS[a][0] + 0.004, FINGERS[a][1], 0.0)
        pb = V(FINGERS[b][0] + 0.004, FINGERS[b][1], 0.0)
        webs.append(F.cone(pa, pb, 0.007))
    out = U([palm] + webs, 0.01, F)
    out = U([out] + fing, 0.008, F)
    out = U([out] + knuckles, 0.005, F)
    out = S(out, U(creases), 0.0015, F)
    if info is not None:
        info.update({k: F.p(v) for k, v in tips.items()})
    return out


TOES = ((0.034, 0.052, 0.0162, 0.236), (0.009, 0.043, 0.0112, 0.243), (-0.012, 0.038, 0.0104, 0.238),
        (-0.03, 0.033, 0.0097, 0.229), (-0.046, 0.027, 0.0089, 0.216))      # 五个脚趾：(横向 y, 长, 根部半径, 趾根 x)，大脚趾在 +y


def foot(F):
    """脚（脚心朝上搁在大腿上的那只）：局部 x 从脚跟到脚尖，z 是脚心朝的方向，y 往大脚趾那边。
    脚心：圆的脚跟垫、内侧略凹的足弓（足下平满，只凹一点）、一横条前掌垫；前掌和脚趾之间一道横纹；
    五个脚趾一排（大脚趾最大，往小脚趾一个比一个短、细，趾间有缝），每个趾头脚心那面一个圆的趾肚、脚背那面一片趾甲，趾尖略往上翘"""
    parts = [F.ell((0.04, 0.0, 0.0), (0.052, 0.043, 0.042)),            # 脚跟
             F.ell((0.12, 0.002, -0.01), (0.085, 0.046, 0.034)),        # 足中
             F.ell((0.115, -0.002, -0.028), (0.075, 0.038, 0.026)),     # 脚背（往 -z 鼓）
             F.ell((0.192, 0.004, -0.006), (0.046, 0.06, 0.03))]        # 前掌
    foot_ = U(parts, 0.022, F)
    # 脚心那面：脚跟垫、前掌垫、外侧一条（足下平满），内侧足弓略凹
    pads = [F.ell((0.042, 0.0, 0.026), (0.04, 0.033, 0.018)),
            F.ell((0.195, 0.008, 0.019), (0.034, 0.054, 0.013)),
            F.ell((0.12, -0.024, 0.02), (0.07, 0.018, 0.012))]
    foot_ = U([foot_] + pads, 0.012, F)
    foot_ = S(foot_, F.ell((0.115, 0.046, 0.034), (0.055, 0.026, 0.016)), 0.014, F)
    toes, nails = [], []
    for k, (yy, L, r, xx) in enumerate(TOES):
        a = V(xx - 0.012, yy, 0.002)
        d1 = V(1, -0.035 * k, 0.05)
        d1 /= np.linalg.norm(d1)
        m = a + d1 * L * 0.55
        d2 = d1 + V(0, 0, 0.16)             # 趾尖略往脚心那边弯（放松的脚趾），又略往上翘
        d2 /= np.linalg.norm(d2)
        b = m + d2 * L * 0.45
        t = U([F.cone(a, m, r, r * 0.9), F.cone(m, b, r * 0.9, r * 0.82), F.sph(b, r * 0.84)], 0.004, F)
        # 趾肚：脚心那面（+z）一个圆鼓包
        t = U([t, F.ell(b - d2 * r * 0.55 + V(0, 0, r * 0.35), (r * 0.95, r * 0.88, r * 0.7))], 0.003, F)
        toes.append(t)
        # 趾甲：脚背那面（-z）
        nails.append(F.ell(b - d2 * r * 0.45 + V(0, 0, -r * 0.78), (r * 0.72, r * 0.68, 0.0022)))
    out = U([foot_] + toes, 0.006, F)
    out = U([out] + nails, 0.0008, F)
    # 前掌和脚趾之间脚心那面一道横纹、趾间的缝（脚心那面）
    crease = F.curve([(0.219, 0.04, 0.023), (0.224, 0.015, 0.024), (0.221, -0.015, 0.023), (0.212, -0.04, 0.019)], 0.0018)
    out = S(out, crease, 0.005, F)
    return out


def hand_frame(B, wrist, d, palm, right=True, s=1.0):
    """手的坐标系：wrist 腕（身子坐标），d 指尖方向，palm 手心朝向（都是身子坐标里的方向）。左手用镜像（y 轴反向）"""
    d = V(d) / np.linalg.norm(d)
    n = -V(palm)
    n = n - d * n.dot(d)
    n /= np.linalg.norm(n)
    y = np.cross(n, d)
    if not right:
        y = -y
    R = np.stack([d, y, n], axis=1)
    return Frame(B.p(wrist), B.r(R), B.s * s)


# 手印里每根手指的姿势：(张开角, (根节, 中节, 末节弯曲))
RELAX = {'index': (3, (6, 8, -6)), 'middle': (0, (7, 9, -6)), 'ring': (-3, (9, 11, -4)), 'little': (-7, (12, 13, -2)),
         'thumb': None, 'thumb_tip': (0.058, 0.014, -0.012)}
VARADA = {'index': (2, (16, 24, 14)), 'middle': (0, (6, 8, -4)), 'ring': (-3, (8, 10, -2)), 'little': (-7, (11, 13, 0)),
          'thumb': None, 'thumb_dir': (0.65, 0.6, -0.45), 'thumb_to': ('index', (-0.006, 0.004, -0.04))}
DHYANA = {'index': (2, (8, 10, -4)), 'middle': (0, (9, 11, -4)), 'ring': (-2, (10, 12, -2)), 'little': (-5, (13, 14, 0)),
          'thumb': None, 'thumb_dir': (0.55, 0.78, -0.3), 'thumb_tip': (0.045, 0.045, -0.03), 'thumb_pole': (0.2, 0.6, -0.7)}
DHYANA_TOP = dict(DHYANA)
TEACH = {'index': (0, (20, 100, 70)), 'middle': (1, (2, 4, -8)), 'ring': (-2, (6, 8, -6)), 'little': (-7, (12, 14, -2)),
         'thumb': None, 'thumb_dir': (0.75, 0.45, -0.5), 'thumb_to': ('index', (-0.013, 0.0, -0.004)),
         'thumb_meta': 0.045, 'thumb_len': (0.038, 0.03)}      # 食指弯回来、拇指尖碰食指尖：圈在食指根和中节之间（低、小），拇指短


def hands_of(B, P, info=None):
    """两只手（含小臂伸进袖口那一截）和脚心朝上的右脚，按手印摆好。返回几块（分开抽网格，包围盒小）"""
    out = []
    frames = {sx: hand_frame(B, P.wrist[sx], h['d'], h['palm'], right=(sx == P.R), s=1.18) for sx, h in P.hands.items()}
    poses = {sx: dict(globals()[h['pose']]) for sx, h in P.hands.items()}
    if P.mudra == 'amida':
        # 弥陀定印：右手叠在左手上，两拇指尖在掌心前上方相接（围成一个椭圆）
        m = (P.wrist[P.R] + P.wrist[P.L]) / 2 + V(0, -0.088, 0.072)
        for sx, F in frames.items():
            poses[sx]['thumb_at'] = tuple(F.R.T @ (B.p(m) - F.o) / F.s + V(0.0, 0.0, 0.0))
    for sx, h in P.hands.items():
        F = frames[sx]
        if info is not None:
            info.setdefault('hand_frames', {})[sx] = F
        wr, el = P.wrist[sx], P.elbow[sx]
        arm = B.cone(wr + (el - wr) * 0.06, wr + (el - wr) * 0.5, 0.043, 0.056)
        tips = {}
        out.append(U([hand(F, poses[sx], tips), arm], B.k(0.01)))
        if info is not None:
            info.setdefault('tips', {})[sx] = tips
    # 右脚：脚心朝上，搁在左大腿上（结跏趺坐，吉祥坐）；踝往右膝那边伸进衣服
    f = P.foot
    t = P.top
    Ff = hand_frame(B, P.ankle[t], f['d'], -V(f['sole']), right=False, s=1.12)   # 局部 z = 脚心朝向，y = 大脚趾那边
    out.append(U([foot(Ff), B.cone(P.ankle[t] + V(-0.03 * t, 0, -0.01), P.ankle[t] + (P.knee[t] - P.ankle[t]) * 0.2, 0.052, 0.06)], B.k(0.01)))
    if info is not None:
        info['foot'] = Ff
    return out


HEAD_PITCH = 19.0                 # 低头的角度（度）：跪在拜垫上抬头看，要看见眼睑、眉，佛是往下看着人的（7° 时看上去在仰头）
HEAD_PIVOT = V(0, 0.006, -0.30)   # 绕颈根转（头的局部坐标）：下巴不会往胸口里缩


def head_frame(B):
    """头的坐标系：原来 7° 时头在 (0, 0.072, 1.548)；现在绕颈根多低 8°（颈根不动，头往前、往下探一点）"""
    s = 1.38
    o0 = B.p(0, 0.072, 1.548)
    piv = o0 + B.r(euler(math.radians(7), 0, 0)) @ (HEAD_PIVOT * s * B.s)
    R = B.r(euler(math.radians(HEAD_PITCH), 0, 0))
    o = piv - R @ (HEAD_PIVOT * s * B.s) + B.d(0, 0, 0.018) * B.s      # 颈子长一点点：低了头下巴不贴到领口上
    return Frame(o, R, B.s * s)


def head_frame0(B):
    """不低头时的头坐标（颈根按它放）"""
    return Frame(B.p(0, 0.072, 1.548 + 0.018), B.r(euler(math.radians(7), 0, 0)), B.s * 1.38)


CHEST_NECK_K = 0.09      # 颈根并进胸口的过渡（第四轮 0.05：颈根一圈一道硬的凹线）


def chest_relief(B):
    """胸口露出来那一块的起伏（sdf.Displace：正的往里刻、负的往外鼓，米）。按身子坐标的 (x, z) 画：
    胸大肌两块略鼓的平面，下沿往外略升、收出一道利落的边，边下面略凹；中间胸骨一道浅沟（上深下浅）；
    颈根下面颈窝一个小凹；两道锁骨从颈窝两边往肩上去（中间那一段平、往外略升）。都不深（六到八毫米）：
    鎏金像的胸口是饱满的，只要让灯光照出几个面来，不是刻一身肌肉。第一版三五毫米在殿里的鎏金反光下几乎看不出，加到六到八毫米"""
    def fn(X, Y, Z):
        x, y, z = to_local(B, X, Y, Z)
        ax = np.abs(x)
        # 胸大肌：x 0.02–0.2、z 下沿到 1.04 的一大块往外鼓 4.5 毫米；下沿 zl 往外略升（胸大肌外下角在腋前）
        zl = 0.875 + 0.04 * np.clip(ax / 0.2, 0, 1.2) ** 2
        pec = ss(0.006, 0.045, ax) * (1 - ss(0.17, 0.25, ax)) * ss(zl - 0.004, zl + 0.04, z) * (1 - ss(1.0, 1.075, z))
        h = -0.008 * pec
        # 下沿那一道：边下面一道很浅、很宽的凹（不是一道刻线），边就收得利落
        h = h + 0.0014 * np.exp(-((z - (zl - 0.008)) / 0.012) ** 2) * ss(0.02, 0.06, ax) * (1 - ss(0.15, 0.21, ax))
        # 胸骨：正中一道浅沟，上面（近颈窝）深一点
        h = h + (0.0038 + 0.0026 * ss(0.9, 1.06, z)) * np.exp(-(x / 0.015) ** 2) * ss(0.85, 0.9, z) * (1 - ss(1.07, 1.1, z))
        # 颈窝（胸骨上窝）
        h = h + 0.007 * np.exp(-((x / 0.028) ** 2 + ((z - 1.098) / 0.021) ** 2))
        # 锁骨：从颈窝两边（x 0.035）往外、略往上到肩（x 0.24），一道圆的棱，两头收掉
        zc = 1.103 + 0.05 * ss(0.04, 0.24, ax)
        cl = np.exp(-((z - zc) / 0.0085) ** 2) * ss(0.03, 0.07, ax) * (1 - ss(0.2, 0.27, ax))
        h = h - 0.0055 * cl + 0.0018 * np.exp(-((z - zc + 0.016) / 0.008) ** 2) * ss(0.03, 0.07, ax) * (1 - ss(0.2, 0.27, ax))
        return (h * B.s).astype(np.float32)
    return fn


def figure(B, P, info=None):
    """一尊佛：返回 {'head': 头颈, 'body': 身子和衣服, 'hands': 手和脚}"""
    info = {} if info is None else info
    H = head_frame(B)
    hd = head(H, info, head_frame0(B))
    core = body_core(B, P)
    # 胸口露出来的那块皮肤和脖子做成一整块（和头一起，按头的精度抽网格）：颈根自然地顺到胸口，不是两块硬插在一起
    # 盒子的上沿抬到颈子里面（以前在 1.3，颈根下面切出一道横的台子，评审：胸口像个枕头，脖子下一道硬棱）
    # 第五轮：胸口刻出胸大肌的两块平面（下沿收出一道边）、胸骨一道浅沟、颈窝、两道锁骨（评审：胸口还是一整团光溜溜的枕头）；
    # 颈根和胸口之间的过渡放宽（以前颈子像一截圆筒插在胸口上，颈根一圈像高领）
    chest = sdf.Inter(core, B.box((0, -0.12, 1.06), (0.3, 0.22, 0.38)))
    chest = sdf.Displace(chest, chest_relief(B), B.k(0.012), box=(B.p(-0.3, -0.45, 0.78), B.p(0.3, 0.12, 1.24)))
    hd = sdf.Union([hd, chest], B.k(CHEST_NECK_K))
    lap = lap_volume(B, P)
    P.resolve(B, lap)
    robe0 = sdf.Sub(robe_volume(B, P, lap), opening_cut(B, P, core), B.k(0.004))
    robe0 = sdf.Union([robe0, drape(B)], B.k(0.03))
    add, cut, folds = robe_details(B, P, robe0, core, info)
    robe = robe0
    for c in cut:
        c, kk = c if isinstance(c, tuple) else (c, 0.006)          # (形, 过渡)：衣缘外沿那道窄沟过渡小（沟要利落）
        robe = sdf.Sub(robe, c, B.k(kk))
    robe = sdf.Folds(robe, folds, near=B.k(0.03))
    ig = inner_garment(B, P, core)
    ig_folds = inner_folds(B, ig)
    ig = sdf.Folds(ig, ig_folds, near=B.k(0.02))
    info['n_folds'] = len(folds) + len(ig_folds)
    info['fold_paths'] = [f['P'] for f in folds + ig_folds]
    body = sdf.Union([robe] + add, B.k(0.004))
    body = U([body, ig], 0.0)
    return {'head': hd, 'body': body, 'hands': hands_of(B, P, info), 'knot': info['knot_node'], 'H': H, 'core': core, 'B': B}


# ====================================================================== 螺发
def hairline_z(phi):
    """发际线的高度（头的局部坐标）：phi 是绕竖轴的角，0 = 正前方。前额平、鬓角收、耳上高、脑后低"""
    a = np.abs(np.degrees(phi))
    return np.interp(a, [0, 30, 55, 80, 105, 140, 180], [0.087, 0.083, 0.068, 0.045, 0.02, -0.04, -0.075])


def curl_mesh(M=12, rings=(1.0, 0.85, 0.66, 0.45, 0.24), H=0.98, turns=1.3):
    """一颗螺发（底半径 1）：尖顶的小圆锥（肩膀饱满），一道凸起的螺旋棱从底边绕一圈半到顶尖（顶尖略偏）。顶点共用（平滑法线）。
    M 段一圈 × 5 圈 + 顶尖 = 108 个三角形；M=8、三圈的是脑后看不见的那些（40 个）。
    返回 (verts, tris, 亮度)：亮度给上色（螺旋沟里、底下暗，棱上、顶上亮）"""
    Vv, br = [], []
    for k, r in enumerate(rings):
        z0 = H * (1 - r ** 1.55) ** 0.88          # 尖顶的圆锥（肩膀略鼓）
        for j in range(M):
            ph = 2 * math.pi * j / M
            psi = (ph + 2 * math.pi * turns * (1 - r)) % (2 * math.pi) - math.pi
            g = 1 - math.exp(-(psi / 1.0) ** 2) if k > 0 else 1.0           # 0 在螺旋沟里（窄的一道），1 在棱上
            w = 0.0 if k == 0 else 1.0
            rr = r * (1 - w * 0.09 * (1 - g))
            z = z0 - w * H * 0.1 * (1 - g) * (0.4 + 0.6 * r)
            Vv.append((rr * math.cos(ph), rr * math.sin(ph), z))
            br.append((0.55 + 0.5 * (z0 / H) ** 0.8) * ((0.5 + 0.55 * g) if k > 0 else 0.72))
    top = len(Vv)
    Vv.append((0.06, 0.03, H * 1.02))                 # 螺尖略偏、略尖
    br.append(1.15)
    T = []
    for k in range(len(rings) - 1):
        for j in range(M):
            a0, a1 = k * M + j, k * M + (j + 1) % M
            b0, b1 = (k + 1) * M + j, (k + 1) * M + (j + 1) % M
            T += [(a0, a1, b1), (a0, b1, b0)]
    last = (len(rings) - 1) * M
    for j in range(M):
        T.append((last + j, last + (j + 1) % M, top))
    return np.array(Vv), np.array(T), np.array(br)


def _rows_on(node, H, c0, dirs_fn, phis, els):
    """在头皮上按「经线」取点：phis × els 的射线从外往 c0 射，贴到 node 上。返回 (点 (np, ne, 3), 贴上了没有)"""
    P = np.zeros((len(phis), len(els), 3))
    OK = np.zeros((len(phis), len(els)), bool)
    for i, ph in enumerate(phis):
        D = np.array([dirs_fn(ph, el) for el in els])
        starts = np.array([H.p(c0 + d * 0.32) for d in D])
        ends = np.array([H.p(c0) for _ in D])
        Q, N, ok = surf(node, starts, ends - starts, tmax=H.k(0.32))
        P[i], OK[i] = Q, ok
    return P, OK


def _place_along(Q, step, phase, closed):
    """沿一条折线等距取点（closed：首尾相接，个数取整让一圈正好排满）"""
    Q = np.asarray(Q)
    if closed:
        Q = np.vstack([Q, Q[:1]])
    L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))])
    if L[-1] < step * 0.6:
        return np.zeros((0, 3))
    if closed:
        n = max(int(round(L[-1] / step)), 3)
        ss_ = (np.arange(n) + phase) * L[-1] / n
    else:
        n = int((L[-1] - step * 0.5) / step) + 1
        off = (L[-1] - (n - 1) * step) / 2
        ss_ = off + np.arange(n) * step
    return np.stack([np.interp(ss_, L, Q[:, k]) for k in range(3)], axis=1)


def curls(H, head_node, info, d=0.0221, seed=3):
    """螺发一排一排地排：头颅上的每一排都和发际线平行（离发际线的弧长一样，一排挨一排、上下错开半颗），
    肉髻上是绕着肉髻顶的一圈圈（顶上一颗）。排好以后只推开挨得太近的（不打乱排）。
    每颗朝着表面法线、绕自己转一个随机角。脑后（被背光挡住、哪儿都看不见）的用省面的。
    返回 (verts, tris, 亮度, 每颗中心) —— 世界坐标"""
    rng = np.random.default_rng(seed)
    scalp = info.get('scalp', head_node)
    dd = H.k(d)
    row = 0.87 * dd                           # 排距（错开半颗的密排）
    c0 = V(0, 0.02, 0.03)
    jw, jr = info.get('jewel', (None, 0))
    USH0 = V(0, 0.018, USH_C)

    def on_ush(P, lim=1.0):
        x, y, z = to_local(H, P[..., 0], P[..., 1], P[..., 2])
        e = (x / USH_R) ** 2 + ((y - 0.018) / (USH_R * 1.04)) ** 2 + ((z - USH_C) / USH_H) ** 2
        return (e < lim) & (z > USH_C - 0.03)
    # ── 头颅：经线（每 1° 一条），从发际线往上量弧长 ──
    phis = np.linspace(-math.pi, math.pi, 360, endpoint=False)
    els = np.linspace(-0.75, 1.5, 150)
    P, OK = _rows_on(scalp, H, c0, lambda ph, el: V(math.sin(ph) * math.cos(el), -math.cos(ph) * math.cos(el), math.sin(el)), phis, els)
    lx, ly, lz = to_local(H, P[..., 0], P[..., 1], P[..., 2])
    above = lz - hairline_z(phis)[:, None]
    seg = np.linalg.norm(np.diff(P, axis=1), axis=2)
    arc = np.concatenate([np.zeros((len(phis), 1)), np.cumsum(seg, axis=1)], axis=1)
    # 每条经线上发际线那一点的弧长（插值）
    s_h = np.array([np.interp(0.0, above[i], arc[i]) for i in range(len(phis))])
    S_ = arc - s_h[:, None]
    ush = on_ush(P)
    pts = []
    for r_i in range(40):
        s_r = r_i * row + 0.5 * dd * 0.9
        ring, valid = [], []
        for i in range(len(phis)):
            if S_[i, -1] < s_r:
                ring.append(P[i, -1])
                valid.append(False)
                continue
            k = int(np.searchsorted(S_[i], s_r))
            k = min(max(k, 1), len(els) - 1)
            t = (s_r - S_[i, k - 1]) / max(S_[i, k] - S_[i, k - 1], 1e-9)
            q = P[i, k - 1] + (P[i, k] - P[i, k - 1]) * t
            ring.append(q)
            valid.append(bool(OK[i, k] and OK[i, k - 1] and not on_ush(q)))
        ring, valid = np.array(ring), np.array(valid)
        if not valid.any():
            break
        if valid.all():
            pts.append(_place_along(ring, dd, 0.5 * (r_i % 2), True))
            continue
        # 断开的几段（碰到肉髻的地方断开）：每段单独等距排
        roll = (np.nonzero(~valid)[0][0] + 1) if (~valid).any() else 0
        v2 = np.roll(valid, -roll)
        r2 = np.roll(ring, -roll, axis=0)
        runs, cur = [], []
        for q, ok in zip(r2, v2):
            if ok:
                cur.append(q)
            elif cur:
                runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
        for run in runs:
            pts.append(_place_along(np.array(run), dd, 0.0, False))
    # ── 肉髻：绕顶的一圈圈 ──
    ap = surf(scalp, [H.p(USH0 + V(0, 0, 0.3))], H.d(0, 0, -1), tmax=H.k(0.4))[0][0]
    pts.append(ap[None, :])
    a_phis = np.linspace(-math.pi, math.pi, 240, endpoint=False)
    alps = np.linspace(0.0, 2.2, 120)
    PU, OKU = _rows_on(scalp, H, USH0, lambda ph, al: V(math.sin(ph) * math.sin(al), -math.cos(ph) * math.sin(al), math.cos(al)), a_phis, alps)
    segu = np.linalg.norm(np.diff(PU, axis=1), axis=2)
    arcu = np.concatenate([np.zeros((len(a_phis), 1)), np.cumsum(segu, axis=1)], axis=1)
    for r_i in range(1, 20):
        s_r = r_i * row
        ring, valid = [], []
        for i in range(len(a_phis)):
            k = int(np.searchsorted(arcu[i], s_r))
            k = min(max(k, 1), len(alps) - 1)
            t = (s_r - arcu[i, k - 1]) / max(arcu[i, k] - arcu[i, k - 1], 1e-9)
            q = PU[i, k - 1] + (PU[i, k] - PU[i, k - 1]) * t
            ring.append(q)
            valid.append(bool(on_ush(q, 1.16)))
        ring, valid = np.array(ring), np.array(valid)
        if valid.mean() < 0.15:
            break
        cand = _place_along(ring, dd, 0.5 * (r_i % 2), True)
        pts.append(cand[on_ush(cand, 1.16)])           # 肉髻根上那一圈：只留在肉髻上的（和头颅最上一排接上）
    Pc = np.vstack([p_ for p_ in pts if len(p_)])
    # 补空：头颅最上一排和肉髻最下一圈之间（肉髻根那道台阶上）、断开的排的两头，撒点补上空着的地方
    n = 12000
    u = rng.uniform(-1, 1, n)
    th = rng.uniform(0, 2 * math.pi, n)
    dirs = np.stack([np.sqrt(1 - u * u) * np.cos(th), np.sqrt(1 - u * u) * np.sin(th), u], axis=1)
    dirs = dirs[dirs[:, 2] > -0.5]
    Q, Nq, okq = surf(scalp, np.array([H.p(c0 + q * 0.4) for q in dirs]), np.array([H.d(*(-q)) for q in dirs]), tmax=H.k(0.4))
    Q = Q[okq]
    qx, qy, qz = to_local(H, Q[:, 0], Q[:, 1], Q[:, 2])
    Q = Q[qz > hairline_z(np.arctan2(qx, -qy)) + 0.9 * d]
    for q in Q[rng.permutation(len(Q))]:
        if np.min(np.linalg.norm(Pc - q, axis=1)) > dd * 0.92:
            Pc = np.vstack([Pc, q])
    # 髻珠那里让开
    if jw is not None:
        Pc = Pc[np.linalg.norm(Pc - jw, axis=1) > jr + dd * 0.38]
    # 挨得太近的（两排交界、断开的地方）：近于 0.7 颗的去掉一颗，再轻轻推开（只推不拉，排还是排）
    keep = np.ones(len(Pc), bool)
    for i in range(len(Pc)):
        if not keep[i]:
            continue
        dist = np.linalg.norm(Pc[i + 1:] - Pc[i], axis=1)
        close = np.nonzero(dist < dd * 0.7)[0] + i + 1
        keep[close] = False
    Pc = Pc[keep]
    for it in range(6):
        diff = Pc[:, None, :] - Pc[None, :, :]
        dist = np.linalg.norm(diff, axis=2) + np.eye(len(Pc))
        push = np.clip(dd * 0.95 - dist, 0, None) / dist
        Pc = Pc + 0.3 * np.einsum('ij,ijk->ik', push, diff)
        Pc = sdf.snap(scalp, Pc, iters=3)
    N = sdf.grad(scalp, Pc, 1e-3)
    hi_m = curl_mesh()
    lo_m = curl_mesh(M=8, rings=(1.0, 0.72, 0.4))
    allv, allt, allb = [], [], []
    nv = 0
    R0 = dd * 0.56
    for p, nrm in zip(Pc, N):
        lx, ly, lz = to_local(H, *p)
        hidden = ly > 0.1 and lz < USH_C - 0.03          # 脑后：背光挡着，用省面的
        tv, tt, tb = lo_m if hidden else hi_m
        a = np.cross(nrm, V(0, 0, 1) if abs(nrm[2]) < 0.9 else V(1, 0, 0))
        a /= np.linalg.norm(a)
        b = np.cross(nrm, a)
        ang = rng.uniform(0, 2 * math.pi)
        R = np.stack([a * math.cos(ang) + b * math.sin(ang), -a * math.sin(ang) + b * math.cos(ang), nrm], axis=1)
        sc = R0 * rng.uniform(0.97, 1.04)
        allt.append(tt + nv)
        allv.append(p - nrm * sc * 0.1 + (tv * sc) @ R.T)
        allb.append(tb * rng.uniform(0.93, 1.07))
        nv += len(tv)
    return np.concatenate(allv), np.concatenate(allt), np.concatenate(allb), Pc


def lathe_mesh(profile, segs=32):
    """旋转体（numpy）：profile = [(半径, 高度), ...] 从下往上，返回 (verts, tris)"""
    Vv, Q = ring_lathe(profile, n=segs, rot=0.0)
    return Vv, quads_to_tris(Q)


def attributes(bag, P, info, s):
    """手里拿的东西（世界坐标里放好，按手的坐标）"""
    HF = info.get('hand_frames', {})
    if P.mudra == 'bowl':
        # 药师佛：左手掌心托着药钵：圆鼓鼓的钵身、口沿略往里收（敞口的钵，看得见里面）、矮圈足；
        # 钵身下半一圈低低的仰莲瓣浮雕（八瓣，瓣边一道凸线），口沿一道圆唇
        F = HF[P.L]
        base = F.p(0.085, 0.0, -0.022)
        k = s
        prof = [(0.0, 0.0), (0.036, 0.0), (0.04, 0.004), (0.036, 0.01), (0.044, 0.014), (0.066, 0.026), (0.084, 0.045), (0.094, 0.068),
                (0.095, 0.088), (0.09, 0.104), (0.082, 0.115), (0.077, 0.12), (0.078, 0.125), (0.075, 0.129), (0.069, 0.127),
                (0.072, 0.118), (0.082, 0.1), (0.084, 0.08), (0.075, 0.05), (0.05, 0.03), (0.0, 0.024)]
        Vl, Q = ring_lathe([(r * k, z * k) for r, z in prof], n=72, rot=0.0)
        Vl = Vl[:-2]                              # 不要车削自带的上下封口（钵是敞口的，底下另封）
        Q = Q[(Q < len(Vl)).all(axis=1)]
        z = Vl[:, 2] / k
        th = np.arctan2(Vl[:, 1], Vl[:, 0])
        # 仰莲瓣浮雕：外壁 z 0.016..0.07 之间，八瓣（瓣尖往上），瓣边一道凸线
        ring_i = np.repeat(np.arange(len(prof)), 72)
        outer = ring_i <= 9
        aa = ((th / (2 * math.pi) * 8) % 1.0 - 0.5) * 2
        top = 0.03 + 0.042 * spow(1 - np.abs(aa) ** 1.7, 0.6)
        inside = outer & (z > 0.016) & (z < top)
        rimline = np.exp(-((top - z) / 0.0035) ** 2) * outer * (z > 0.016)
        bump = (0.0022 * inside + 0.0018 * rimline) * k
        rr = np.hypot(Vl[:, 0], Vl[:, 1])
        Vl[:, :2] *= ((rr + bump) / np.maximum(rr, 1e-9))[:, None]
        T = quads_to_tris(Q)
        col = np.tile(GOLD, (len(Vl), 1))
        col[rimline > 0.3] = GOLD_LIT
        col[ring_i >= 14] = GOLD_DARK * 0.8                 # 钵里面：暗金
        bag.add('gold', Vl + base, T, col)
        # 右手（与愿印）拇指、食指的指肚之间拈着一颗诃子：长约 3.5 厘米、五道棱的长圆果，鎏金略带一点青
        tips = info.get('tips', {}).get(P.R)
        if tips:
            a_, b_ = tips['thumb'], tips['index']
            c = (a_ + b_) / 2
            ax = (b_ - a_) / np.linalg.norm(b_ - a_)
            gap = np.linalg.norm(b_ - a_) - (0.0094 + FINGERS['index'][3][2]) * 1.18 * s
            rad = float(np.clip(gap / 2 + 0.001 * s, 0.008 * s, 0.0115 * s))
            Vs, Ts = sphere_mesh(1.0, 15, 9)
            thf = np.arctan2(Vs[:, 1], Vs[:, 0])
            r = 1 + 0.08 * np.cos(5 * thf)
            Vs[:, 0] *= r
            Vs[:, 1] *= r
            hl = 0.0175 * s
            Vs = Vs * np.array([rad, rad, hl])
            zax = np.cross(ax, V(0, 0, 1))
            zax = zax / np.linalg.norm(zax) if np.linalg.norm(zax) > 1e-3 else V(1, 0, 0)
            Rm = np.stack([ax, np.cross(zax, ax), zax], axis=1)
            Vw = Vs @ Rm.T + c
            colf = (GOLD * 0.75 + lin((0.45, 0.6, 0.35)) * 0.25)[None, :] * (0.85 + 0.15 * r[:, None] / 1.08)
            bag.add('gold', Vw, Ts, colf)
    if P.mudra == 'amida':
        # 阿弥陀佛：两掌相叠，掌上托一朵莲花：两层各八片兜着的瓣（同莲座的瓣，不交叉），中间一个莲蓬（顶上一圈莲子）
        Fl, Fr = HF[P.L], HF[P.R]
        c = (Fl.p(0.085, 0.0, -0.022) + Fr.p(0.085, 0.0, -0.02)) / 2 + V(0, 0.012 * s, 0.026 * s)
        k = s * 1.25            # 大一点：跪垫上也看得出是一朵莲
        Vv, T = lathe_mesh([(0.0, 0.0), (0.024 * k, 0.0), (0.03 * k, 0.012 * k), (0.022 * k, 0.02 * k), (0.0, 0.022 * k)], 32)
        bag.add('gold', Vv + c, T, GOLD_DARK)
        sub = Bag()
        petal_ring(sub, 8, 0.024 * k, 0.008 * k, 0.07 * k, 0.03 * k, 0.005 * k, True, GOLD, lin((0.86, 0.45, 0.42)), tilt0=22,
                   tilt1=70, curl=28, nu=10, rim=0.25, lobe=0.0, ridge=0.18, nvi=3, tipk=0.45, cup=0.22)
        petal_ring(sub, 8, 0.018 * k, 0.016 * k, 0.058 * k, 0.025 * k, 0.0045 * k, True, GOLD, lin((0.9, 0.55, 0.5)), phase=0.5,
                   tilt0=40, tilt1=84, curl=22, nu=10, rim=0.25, lobe=0.0, ridge=0.18, nvi=3, tipk=0.4, cup=0.22)
        for mat, items in sub.parts.items():
            for Vp, Tp, Cp in items:
                bag.add('gold', Vp + c, Tp, Cp, shell=True)
        Vv, T = lathe_mesh([(0.0, 0.024 * k), (0.019 * k, 0.026 * k), (0.022 * k, 0.04 * k), (0.021 * k, 0.05 * k), (0.0, 0.052 * k)], 32)
        bag.add('gold', Vv + c, T, lin((0.78, 0.66, 0.3)))
        for i in range(7):
            a = 2 * math.pi * i / 7
            Vb, Tb = sphere_mesh(0.004 * k, 8, 5)
            bag.add('gold', Vb + c + V(0.0125 * k * math.cos(a), 0.0125 * k * math.sin(a), 0.052 * k), Tb, GOLD_DARK)
        Vb, Tb = sphere_mesh(0.004 * k, 8, 5)
        bag.add('gold', Vb + c + V(0, 0, 0.053 * k), Tb, GOLD_DARK)


def jewel(bag, H, c=None):
    """髻珠：肉髻前面正中一颗红宝石（扁圆），一圈金托子，托子上一圈小金珠。c：头皮上那一点（头的局部坐标）"""
    Rj = euler(math.radians(-JEWEL_TILT), 0, 0)
    c = V(0, -0.094, 0.149) if c is None else V(c) + Rj @ V(0, -0.004, 0)
    nrm = Rj @ V(0, -1, 0)
    Vs, Ts = sphere_mesh(1.0, 16, 10)
    gem = place(Vs * np.array([0.0175, 0.0175, 0.0215]), (0, 0, 0), Rj @ euler(math.radians(90), 0, 0))
    gem = gem + c + nrm * 0.006
    bag.add('gold', np.array([H.p(q) for q in gem]), Ts, lin((0.74, 0.12, 0.1)) * (0.85 + 0.3 * ss(0.0, 0.02, (gem - c) @ nrm))[:, None] * np.ones(3))
    ring = [c + nrm * 0.002 + (Rj @ V(math.cos(a) * 0.022, 0, math.sin(a) * 0.026)) for a in np.linspace(0, 2 * math.pi, 33)]
    Vt, Tt = tube_mesh(ring, 0.0042, segs=6, cap=False)
    bag.add('gold', np.array([H.p(q) for q in Vt]), Tt, GOLD_LIT)
    for a in np.linspace(0, 2 * math.pi, 15)[:-1]:
        Vb, Tb = sphere_mesh(0.0028, 6, 4)
        p = c + nrm * 0.004 + (Rj @ V(math.cos(a) * 0.0285, 0, math.sin(a) * 0.0325))
        bag.add('gold', np.array([H.p(q) for q in Vb + p]), Tb, GOLD_LIT)


# ====================================================================== 网格袋子：几块网格（点、三角形、每个角的颜色）按材质放在一起
class Bag:
    """V (n,3)、T (m,3)、C (m,3,3)：每个三角形三个角各自的颜色（sRGB）。最后统一烤暗部、交给 kit 导出"""

    def __init__(self):
        self.parts = {}
        self.uvs = {}
        self.shells = {}            # 材质 → 哪几块是薄壳（莲瓣）：上色时不按「凹处」压暗（瓣心是凹的，但不是缝）

    def add(self, mat, Vv, T, C, UV=None, shell=False):
        """UV：paint_ 部件的贴图坐标（每个点一个 (n,2)，或每个角一个 (m,3,2)）。shell：薄壳（莲瓣）"""
        if shell:
            self.shells.setdefault(mat, set()).add(len(self.parts.get(mat, [])))
        Vv = np.asarray(Vv, np.float64)
        T = np.asarray(T, np.int64)
        C = np.asarray(C, np.float64)
        if C.ndim == 2 and C.shape[0] == len(Vv):          # 每个点一个颜色 → 每个角
            C = C[T]
        elif C.ndim == 1:
            C = np.broadcast_to(C, (len(T), 3, 3)).copy()
        if UV is not None:
            UV = np.asarray(UV, np.float64)
            if UV.ndim == 2:
                UV = UV[T]
            self.uvs.setdefault(mat, []).append(UV)
        self.parts.setdefault(mat, []).append((Vv, T, C))

    def add_quads(self, mat, Vv, Q, C):
        Q = np.asarray(Q, np.int64)
        T = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
        if np.asarray(C).ndim == 2 and len(C) == len(Vv):
            self.add(mat, Vv, T, C)
        else:
            self.add(mat, Vv, T, C)

    def merged(self, mat):
        vs, ts, cs, off = [], [], [], 0
        for Vv, T, C in self.parts.get(mat, []):
            vs.append(Vv)
            ts.append(T + off)
            cs.append(C)
            off += len(Vv)
        return np.concatenate(vs), np.concatenate(ts), np.concatenate(cs)

    def all(self):
        vs, ts, off, spans = [], [], 0, []
        for mat in self.parts:
            Vv, T, C = self.merged(mat)
            spans.append((mat, off, len(Vv)))
            vs.append(Vv)
            ts.append(T + off)
            off += len(Vv)
        return np.concatenate(vs), np.concatenate(ts), spans

    def tris(self):
        return sum(len(T) for ps in self.parts.values() for _, T, _ in ps)

    def bake_ao(self, dist=0.25, samples=64, strength=0.75, shade=(0.62, 0.5, 0.42), skip=(), face=None, shell_k=0.5):
        """整体烤一遍环境光遮蔽，乘进颜色（暗处偏暖褐：鎏金缝里积的是旧色，不是灰）。
        face：泥金皮肤（paint_buddha_face）另算：暗部先在网格上抹开 2~3 厘米（不留一块块的污渍），强度减半，
        往暖色 (0.85, 0.66, 0.45) 里压（灰色乘到金上会发脏），下巴、嘴唇、腮帮那一片最暗不低于 0.8。
        face = dict(strength, blur（米）, floor_fn(点) → 0..1 这一片要托底的程度)。
        shell_k：薄壳（莲瓣）的压暗打几折（一片压一片，全压就成了一圈发橙的铜）"""
        Vv, T, spans = self.all()
        ao = sdf.bake_ao(Vv, T, dist=dist, samples=samples)
        warm = np.array([0.85, 0.66, 0.45])
        for mat, off, n in spans:
            if mat in skip:
                continue
            a = ao[off:off + n]
            new = []
            o = 0
            shells = self.shells.get(mat, set())
            for pi_, (Vp, Tp, Cp) in enumerate(self.parts[mat]):
                aa = a[o:o + len(Vp)]
                o += len(Vp)
                if pi_ in shells:           # 莲瓣一片压一片：压暗打折（不然整圈莲瓣比衣服暗三成、发橙）
                    aa = 1 - shell_k * (1 - aa)
                if mat == 'paint_buddha_face' and face is not None:
                    el = np.linalg.norm(Vp[Tp[:, 0]] - Vp[Tp[:, 1]], axis=1).mean()
                    it = int(min(400, (face['blur'] / max(el, 1e-4)) ** 2))
                    for _ in range(it):
                        aa = 0.5 * aa + 0.5 * sdf.neighbours_mean(Vp, Tp, aa)
                    occ = np.clip(face['strength'] * (1 - aa), 0, 1)
                    mult = 1 - occ[:, None] * (1 - warm)[None, :] / 0.55
                    fl = face['floor_fn'](Vp)
                    lum = mult @ np.array([0.3, 0.59, 0.11])
                    lo_ = 0.8 * fl + (1 - fl) * 0.0
                    k = np.where(lum < lo_, (1 - lo_) / np.maximum(1 - lum, 1e-6), 1.0)
                    mult = 1 - (1 - mult) * k[:, None]
                    new.append((Vp, Tp, Cp * mult[Tp]))
                    continue
                k = 1 - strength * (1 - aa)
                tintc = k[:, None] * np.ones(3) + (1 - k[:, None]) * np.array(shade) * 0.35
                new.append((Vp, Tp, Cp * tintc[Tp]))
            self.parts[mat] = new

    def gilt(self, s=1.0):
        """鎏金的明暗（光照在 Unity 殿里几乎都在暗面，所以明暗要「画」进顶点色）：凸起的棱、朝上的边是磨亮的浅金，
        凹进去的地方是深褐金，大面上有一点点深浅起伏。脸、手（paint_ 部件，顶点色乘贴图）只轻轻地加一点"""
        HI = lin((0.95, 0.83, 0.55))            # 磨亮的棱：淡金（第三轮略淡：金箔擦亮的地方发白一点）
        DEEP = lin((0.3, 0.19, 0.075))          # 凹处：深褐金（积了香烟的旧色）
        for mat in list(self.parts):
            if mat not in ('gold', 'paint_buddha_face'):
                continue
            new = []
            shells = self.shells.get(mat, set())
            for pi_, (Vp, Tp, Cp) in enumerate(self.parts[mat]):
                if len(Vp) < 12:
                    new.append((Vp, Tp, Cp))
                    continue
                shell = pi_ in shells
                c, N = sdf.mean_curv(Vp, Tp, smooth=8 if shell else 2)
                c = c * s
                crest = ss(5.0, 40.0, c) * (0.65 + 0.35 * np.clip(N[:, 2], 0, 1))
                recess = ss(-4.0, -30.0, c)
                big = 1 + 0.07 * gilt_noise(Vp / s, 7)
                if mat == 'gold':
                    k1, k2 = (0.35, 0.0) if shell else (0.6, 0.62)       # 莲瓣：瓣心的凹不压暗（明暗已经画在瓣上了）
                    Cv = np.zeros((len(Vp), 3))
                    Cn = np.zeros(len(Vp))
                    for j in range(3):
                        np.add.at(Cv, Tp[:, j], Cp[:, j])
                        np.add.at(Cn, Tp[:, j], 1)
                    cr, rc = crest[Tp][..., None], recess[Tp][..., None]
                    C2 = Cp * big[Tp][..., None]
                    C2 = C2 * (1 - k1 * cr) + HI * k1 * cr * (C2.mean(axis=2, keepdims=True) / 0.6).clip(0.5, 1.2)
                    C2 = C2 * (1 - k2 * rc) + DEEP * k2 * rc
                else:           # 泥金皮肤：凸处略亮，凹处往暖褐里压一点（不发灰）
                    warm = np.array([0.85, 0.66, 0.45])
                    rc = 0.3 * recess[Tp][..., None]
                    C2 = Cp * (1 + 0.08 * crest[Tp][..., None]) * (1 - rc * (1 - warm))
                new.append((Vp, Tp, np.clip(C2, 0, 1)))
            self.parts[mat] = new

    def clean(self, mat):
        """导出前的网格整理：重合的点焊成一个、去掉面积为零的三角形（车削的轴心、拼接处）和用不到的点。
        返回 (verts, tris, 每角颜色, 每角 uv 或 None)"""
        Vv, T, C = self.merged(mat)
        UV = np.concatenate(self.uvs[mat]) if mat in self.uvs else None
        key = np.round(Vv / 1e-6).astype(np.int64)
        _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
        inv = inv.reshape(-1)
        Vv = Vv[first]
        T = inv[T]
        a, b, c = Vv[T[:, 0]], Vv[T[:, 1]], Vv[T[:, 2]]
        area = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2
        ok = (T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2]) & (area > 1e-10)
        T, C = T[ok], C[ok]
        if UV is not None:
            UV = UV[ok]
        used = np.zeros(len(Vv), bool)
        used[T.ravel()] = True
        remap = -np.ones(len(Vv), np.int64)
        remap[used] = np.arange(int(used.sum()))
        n_bad = int((~ok).sum())
        if n_bad:
            print(f'[yjm] {mat}: 去掉 {n_bad} 个面积为零的三角形')
        return Vv[used], remap[T], C, UV

    def to_asset(self, a):
        """放进 kit 的 Asset（每个材质一个部件）"""
        import bpy
        import bmesh
        for mat in self.parts:
            Vv, T, C, UVc = self.clean(mat)
            me = sdf.np_mesh('_bag', Vv, [T])
            col = me.color_attributes.new('col', 'FLOAT_COLOR', 'CORNER')
            c4 = np.concatenate([C.reshape(-1, 3), np.zeros((len(T) * 3, 1))], axis=1).astype(np.float32)
            col.data.foreach_set('color', c4.ravel())
            me.color_attributes.new('nrm', 'FLOAT_COLOR', 'CORNER')
            uvl = me.uv_layers.new(name='uv')
            if UVc is not None:
                uvl.data.foreach_set('uv', UVc.reshape(-1).astype(np.float32))
            else:       # 普通部件的 uv 是（摆动相位, 发光）：都是 0（Blender 新建的 uv 层默认是每个面铺满 0..1，要清掉）
                uvl.data.foreach_set('uv', np.zeros(len(T) * 6, np.float32))
            t = bmesh.new()
            t.from_mesh(me)
            bpy.data.meshes.remove(me)
            a.merge(t, mat)


def lin(c):
    return np.asarray(c, np.float64)


# ====================================================================== 莲瓣
# ====================================================================== 莲座、须弥座
# 鎏金（sRGB）。2026-11-17 第三轮：略偏黄、蓝里留一点（以前偏橙：殿里的灯、暖色环境光再一乘，蓝通道压到零，一片橙色塑料）；
# 深浅不靠把颜色往橙里压，靠材质 toon_gilt 照见殿里的明暗（YJToon.shader 的 _GiltEnv）加上这里烤的凹处、棱
GOLD = lin((0.8, 0.597, 0.266))
GOLD_LIT = lin((0.92, 0.77, 0.45))
GOLD_DARK = lin((0.55, 0.37, 0.15))
CINNABAR = lin((0.66, 0.2, 0.13))
AZURE = lin((0.13, 0.25, 0.48))
MALACHITE = lin((0.18, 0.46, 0.38))
HAIR = lin((0.176, 0.294, 0.588))          # 石青（sRGB 45,75,150）：殿里光暗，太深了会糊成一顶黑帽子


def place(Vl, origin, R=None, scale=1.0):
    Vl = np.asarray(Vl, np.float64) * scale
    if R is not None:
        Vl = Vl @ np.asarray(R).T
    return Vl + np.asarray(origin)


def rz(a):
    c, s_ = math.cos(a), math.sin(a)
    return np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]])


def ring_lathe(profile, n=8, rot=math.pi / 8, chamfer=0.0, segs=None):
    """多边形截面的「车削」：profile = [(内切圆半径, 高度), ...] 从下往上；n 边形（n 很大就是圆）。
    chamfer：多边形的角上切掉一点（八角须弥座的角不是刀尖）。返回 (verts, quads)"""
    if segs is None:
        segs = n
    # 多边形一圈的方向（单位内切圆）：每条边两端各一个点（角上切角），法向量按边算
    pts = []
    for i in range(n):
        a0 = rot + 2 * math.pi * i / n
        a1 = rot + 2 * math.pi * (i + 1) / n
        c0 = V(math.cos(a0), math.sin(a0)) / math.cos(math.pi / n)
        c1 = V(math.cos(a1), math.sin(a1)) / math.cos(math.pi / n)
        if chamfer > 0:
            pts.append(c0 + (c1 - c0) * chamfer)
            pts.append(c1 + (c0 - c1) * chamfer)
        else:
            pts.append(c0)
    m = len(pts)
    VV = []
    for r, z in profile:
        for p in pts:
            VV.append((p[0] * r, p[1] * r, z))
    Q = []
    for k in range(len(profile) - 1):
        for i in range(m):
            a = k * m + i
            b = k * m + (i + 1) % m
            Q.append((a, b, b + m, a + m))
    # 上下封口（扇形，中心一个点）
    VV.append((0, 0, profile[0][1]))
    VV.append((0, 0, profile[-1][1]))
    cb, ct = len(VV) - 2, len(VV) - 1
    top0 = (len(profile) - 1) * m
    for i in range(m):
        Q.append((cb, cb, (i + 1) % m, i))
        Q.append((ct, ct, top0 + i, top0 + (i + 1) % m))
    return np.array(VV), np.array(Q)


def quads_to_tris(Q):
    Q = np.asarray(Q)
    T = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    return T[(T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2])]


def tube_mesh(pts, r, segs=6, cap=True):
    """沿一串点的管子（numpy 网格）"""
    pts = [V(p) for p in pts]
    n = len(pts)
    rr = r if hasattr(r, '__len__') else [r] * n
    tang = [(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]) for i in range(n)]
    tang = [t / np.linalg.norm(t) for t in tang]
    up = V(0, 0, 1) if abs(tang[0][2]) < 0.9 else V(1, 0, 0)
    nrm = up - tang[0] * up.dot(tang[0])
    nrm /= np.linalg.norm(nrm)
    VV = []
    for i in range(n):
        nrm = nrm - tang[i] * nrm.dot(tang[i])
        nrm /= np.linalg.norm(nrm)
        bi = np.cross(tang[i], nrm)
        for k in range(segs):
            a = 2 * math.pi * k / segs
            VV.append(pts[i] + (nrm * math.cos(a) + bi * math.sin(a)) * rr[i])
    Q = []
    for i in range(n - 1):
        for k in range(segs):
            a, b = i * segs + k, i * segs + (k + 1) % segs
            Q.append((a, b, b + segs, a + segs))
    T = quads_to_tris(Q)
    if cap:
        VV.append(pts[0])
        VV.append(pts[-1])
        c0, c1 = len(VV) - 2, len(VV) - 1
        last = (n - 1) * segs
        caps = [(c0, (k + 1) % segs, k) for k in range(segs)] + [(c1, last + k, last + (k + 1) % segs) for k in range(segs)]
        T = np.concatenate([T, np.array(caps)])
    return np.array(VV), T


def sphere_mesh(r, nu=8, nv=6):
    VV = [(0, 0, -r)]
    for j in range(1, nv):
        ph = -math.pi / 2 + math.pi * j / nv
        for i in range(nu):
            th = 2 * math.pi * i / nu
            VV.append((r * math.cos(ph) * math.cos(th), r * math.cos(ph) * math.sin(th), r * math.sin(ph)))
    VV.append((0, 0, r))
    T = []
    for i in range(nu):
        T.append((0, 1 + (i + 1) % nu, 1 + i))
    for j in range(nv - 2):
        for i in range(nu):
            a = 1 + j * nu + i
            b = 1 + j * nu + (i + 1) % nu
            T += [(a, b, b + nu), (a, b + nu, a + nu)]
    top = len(VV) - 1
    base = 1 + (nv - 2) * nu
    for i in range(nu):
        T.append((top, base + i, base + (i + 1) % nu))
    return np.array(VV, np.float64), np.array(T)


V_OUT = np.array([-1, -0.94, -0.86, -0.76, -0.58, -0.32, 0, 0.32, 0.58, 0.76, 0.86, 0.94, 1.0])
V_LOW = np.array([-1, -0.88, -0.7, -0.4, 0, 0.4, 0.7, 0.88, 1.0])


def petal_cols(vin, rim, lobe):
    """一排横向的取点位置（0..1 的那半边，从外往里）：瓣边厚边那一溜、内瓣的边两侧各一个点（边才利）"""
    if lobe > 0:
        a = max(vin, 0.14)
        return [1.0, 0.94, 0.86, 0.77, min(a + 0.045, 0.72), a - 0.015, 0.45 * a, 0.0]
    if rim > 0.45:                 # 小浮雕瓣：一圈厚边、一道脊就够
        return [1.0, 0.84, 0.5, 0.0]
    if rim > 0:
        return [1.0, 0.93, 0.85, 0.72, 0.45, 0.2, 0.0]
    return [1.0, 0.8, 0.45, 0.0]


def petal(L, W, T, up=True, curl=55.0, tilt0=30.0, tilt1=78.0, cup=0.08, nu=16, nvi=5, rim=0.3, lobe=0.22, ridge=0.16):
    """一片莲瓣（局部坐标：瓣根在原点，x 往外（径向），z 往上，y 横向）。
    up=True 是仰莲（瓣尖朝上再往外卷），False 是覆莲（朝下、往外翻）。外面那一层（看得见的一面）刻三样：
    瓣边一圈凸起的厚边（rim，约一厘米）、里面一片小一号的「宝装」内瓣（lobe，一块边很利的凸台：每排在内瓣的边两侧各取一个点）、
    中间一道脊（ridge）；瓣尖是个利的尖、往外卷。里面那层（看不见）点数少。rim/lobe/ridge 是相对 W 的高度。
    返回 (verts, tris, uv, 外层的点数)：uv = (沿瓣长, 横向 -1..1)"""
    us = np.linspace(0, 1, nu) ** 0.9
    ang = np.radians(tilt0 + (tilt1 - tilt0) * us - curl * ss(0.6, 1.0, us))
    ds = np.diff(us) * L
    cx = np.concatenate([[0], np.cumsum(np.cos(ang[:-1]) * ds)])
    cz = np.concatenate([[0], np.cumsum(np.sin(ang[:-1]) * ds)])
    nx, nz = -np.sin(ang), np.cos(ang)            # 法线（朝瓣的里面 = 朝上/朝里那一面）
    # 宽：根部窄、中上最宽、尖上收成一个利尖（如意头那样的弧线收尖）
    wid = W * spow(np.sin(np.pi * np.clip(us * 0.9 + 0.1, 0, 1) ** 0.78), 0.62) * spow(1 - us ** 5, 0.55) + 0.0004
    th = T * (1 - 0.6 * us)
    ul = np.clip((us - 0.1) / 0.72, 0, 1)
    vin = 0.6 * spow(np.sin(np.pi * np.clip(ul * 0.92 + 0.08, 0, 1) ** 0.8), 0.7) * spow(1 - ul ** 5, 0.5) * (ul > 0)
    VV, UV = [], []
    half = petal_cols(0.5, rim, lobe)
    nv = 2 * len(half) - 1

    def relief(i, v):
        a = abs(v)
        r = rim * np.exp(-((a - 0.86) / 0.07) ** 2) * ss(0.04, 0.16, us[i]) * (1 - ss(0.9, 0.99, us[i]))
        lb = lobe * float(a < vin[i] - 0.005) * (1 - ss(0.84, 0.9, us[i])) * ss(0.1, 0.16, us[i])
        rd = ridge * np.exp(-(v / 0.09) ** 2) * ss(0.06, 0.2, us[i]) * (1 - ss(0.94, 1.0, us[i]))
        return (r + lb + rd) * W * 0.3
    for i in range(nu):                      # 外层（看得见的那面）
        hc = petal_cols(vin[i], rim, lobe)
        cols = [-c for c in hc] + hc[::-1][1:]
        for v in cols:
            y = v * wid[i]
            c = cup * wid[i] * (1 - v * v)
            o = -(th[i] / 2) * math.sqrt(max(0.0, 1 - abs(v) ** 8)) - c - relief(i, v)
            VV.append((cx[i] + nx[i] * o, y, cz[i] + nz[i] * o))
            UV.append((us[i], v))
    vi = np.linspace(1, -1, nvi)
    for i in range(nu):                      # 里层
        for v in vi:
            y = v * wid[i]
            c = cup * wid[i] * (1 - v * v)
            o = (th[i] / 2) * math.sqrt(max(0.0, 1 - abs(v) ** 8)) - c
            VV.append((cx[i] + nx[i] * o, y, cz[i] + nz[i] * o))
            UV.append((us[i], v))
    VV = np.array(VV)
    if not up:
        VV[:, 2] *= -1
    no = nu * nv
    T_ = []
    for i in range(nu - 1):
        for j in range(nv - 1):
            a = i * nv + j
            T_ += [(a, a + 1, a + nv + 1), (a, a + nv + 1, a + nv)]
        for j in range(nvi - 1):
            a = no + i * nvi + j
            T_ += [(a, a + 1, a + nvi + 1), (a, a + nvi + 1, a + nvi)]
        o1, o2 = i * nv + nv - 1, (i + 1) * nv + nv - 1
        i1, i2 = no + i * nvi, no + (i + 1) * nvi
        T_ += [(o1, i1, i2), (o1, i2, o2)]
        o1, o2 = i * nv, (i + 1) * nv
        i1, i2 = no + i * nvi + nvi - 1, no + (i + 1) * nvi + nvi - 1
        T_ += [(o1, o2, i2), (o1, i2, i1)]
    # 根部封口（扇形连到里层）
    c0 = no + nvi // 2
    for j in range(nv - 1):
        T_.append((j + 1, j, c0))
    for j in range(nvi - 1):
        T_.append((no + j, no + j + 1, nv // 2))
    T_ = np.array(T_)
    if not up:
        T_ = T_[:, ::-1]
    return VV, T_, np.array(UV), no


def petal_ring(bag, n, r, z, L, W, T, up, color, tipc, phase=0.0, sy=1.0, tilt0=30.0, tilt1=78.0, curl=55.0, nu=16,
               jitter=0.0, rng=None, mat='gold', skip_front=0.0, rim=0.3, lobe=0.22, ridge=0.16, tipk=0.5, nvi=5, cup=0.08, skip_back=0.0):
    Vp, Tp, uv, no = petal(L, W, T, up=up, curl=curl, tilt0=tilt0, tilt1=tilt1, nu=nu, rim=rim, lobe=lobe, ridge=ridge, nvi=nvi, cup=cup)
    u = uv[:, 0]
    v = uv[:, 1]
    # 颜色：鎏金；瓣尖一抹淡彩（石绿或朱，只在最外两成）；瓣边那圈厚边、内瓣的边更亮（磨亮的金）；里层略暗；瓣根略暗。
    # 第三轮：瓣尖的彩淡一半（以前加上瓣与瓣之间的暗部，整圈莲瓣在殿里看是一圈橙褐色的铜，不像金）
    tip = ss(0.84, 1.0, u)[:, None] * tipk * 0.45
    base = color[None, :] * (1 - tip) + tipc[None, :] * tip
    edge = np.exp(-((np.abs(v) - 0.86) / 0.07) ** 2)[:, None] * (1 - ss(0.88, 0.98, u))[:, None]
    HI = lin((0.95, 0.83, 0.55))
    base = base * (1 - edge * 0.7) + HI[None, :] * edge * 0.7
    if lobe > 0:
        le = np.exp(-((np.abs(v) - 0.5 * 0.6) / 0.05) ** 2)[:, None] * ss(0.15, 0.25, u)[:, None] * (1 - ss(0.78, 0.86, u))[:, None]
        base = base * (1 - le * 0.35) + HI[None, :] * le * 0.35
    inner = (np.arange(len(Vp)) >= no)[:, None]
    base = np.where(inner, base * 0.9, base)
    base = base * (0.88 + 0.16 * ss(0.0, 0.25, u))[:, None]             # 瓣根略暗
    for i in range(n):
        a = 2 * math.pi * (i + phase) / n
        if skip_front > 0 and abs(math.atan2(math.sin(a + math.pi / 2), math.cos(a + math.pi / 2))) < skip_front:
            continue        # 正前面被悬裳盖住的几片不做
        if skip_back > 0 and abs(math.atan2(math.sin(a - math.pi / 2), math.cos(a - math.pi / 2))) < skip_back:
            continue        # 正后面（贴着后墙、背光的撑子挡着，哪儿都看不见）的几片不做
        k = 1.0 + (rng.uniform(-jitter, jitter) if rng is not None else 0.0)
        Vw = place(Vp * k, (r * math.cos(a), r * math.sin(a) * sy, z), rz(a))
        # 第三轮：以前这里又乘了一遍 color（= GOLD），莲瓣成了金色的平方——一圈发橙的铜。base 本来就是从 color 起的
        bag.add(mat, Vw, Tp, np.clip(base, 0, 1), shell=True)


def hemi_mesh(r, nu=12, nv=3):
    """半球（底面开口，朝 +z）：连珠用（后半个藏在台子里，不做）"""
    VV = []
    for j in range(nv):
        ph = math.pi / 2 * j / nv
        for i in range(nu):
            th = 2 * math.pi * i / nu
            VV.append((r * math.cos(ph) * math.cos(th), r * math.cos(ph) * math.sin(th), r * math.sin(ph)))
    VV.append((0, 0, r))
    T_ = []
    for j in range(nv - 1):
        for i in range(nu):
            a, b = j * nu + i, j * nu + (i + 1) % nu
            T_ += [(a, b, b + nu), (a, b + nu, a + nu)]
    top = len(VV) - 1
    base = (nv - 1) * nu
    for i in range(nu):
        T_.append((base + i, base + (i + 1) % nu, top))
    return np.array(VV, np.float64), np.array(T_)


def bead_ring(bag, n, R, z, r, sy, col, tilt=0.0):
    """一圈连珠：半球朝外（略朝上/下 tilt 度）"""
    Vh, Th = hemi_mesh(r, 10, 3)
    for i in range(n):
        a = 2 * math.pi * i / n
        out = V(math.cos(a), math.sin(a) * sy, 0)
        out /= np.linalg.norm(out)
        ax = out * math.cos(math.radians(tilt)) + V(0, 0, math.sin(math.radians(tilt)))
        e1 = np.cross(V(0, 0, 1), ax)
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(ax, e1)
        Rm = np.stack([e1, e2, ax], axis=1)
        c = V(R * math.cos(a), R * math.sin(a) * sy, z) - ax * r * 0.25
        bag.add('gold', Vh @ Rm.T + c, Th, col)


def throne(s=1.0, lod=0):
    """莲座：八角须弥座（圭角、下枋、覆莲枭、束腰带壸门、仰莲枭、上枋）+ 仰覆莲（覆莲两层、连珠、仰莲三层）。
    原点在底面中心，台面（坐的地方）高 0.98·s"""
    bag = Bag()
    rng = np.random.default_rng(11)
    G = 'gold'

    def prof(pr, n=8, chamfer=0.12, col=GOLD, mat=G):
        Vv, Q = ring_lathe([(r * s, z * s) for r, z in pr], n=n, chamfer=chamfer)
        bag.add(mat, Vv, quads_to_tris(Q), col)

    # ── 须弥座 ──
    prof([(0.8, 0.0), (0.8, 0.055), (0.785, 0.062), (0.775, 0.068)], col=GOLD_DARK * 1.05)          # 圭角
    prof([(0.772, 0.068), (0.772, 0.128), (0.758, 0.134)], col=GOLD)                                  # 下枋
    prof([(0.755, 0.134), (0.735, 0.15), (0.705, 0.17), (0.675, 0.186), (0.66, 0.19)], col=GOLD_DARK)  # 下枭
    prof([(0.652, 0.19), (0.652, 0.33)], col=CINNABAR * 0.95)                                        # 束腰
    prof([(0.66, 0.33), (0.675, 0.334), (0.705, 0.35), (0.735, 0.37), (0.755, 0.386)], col=GOLD_DARK)  # 上枭
    prof([(0.758, 0.386), (0.79, 0.392), (0.79, 0.452), (0.772, 0.458), (0.74, 0.462)], col=GOLD)     # 上枋
    # 下枭、上枭上的小莲瓣（覆、仰）：贴在枭面上的浮雕瓣（瓣尖利、有一圈厚边和脊），不是一颗颗流下来的胶
    petal_ring(bag, 24, 0.664 * s, 0.186 * s, 0.112 * s, 0.05 * s, 0.014 * s, False, GOLD, GOLD_LIT, tilt0=28, tilt1=34, curl=-6,
               nu=6, rim=0.55, lobe=0.0, ridge=0.35, tipk=0.25, nvi=3)
    petal_ring(bag, 24, 0.664 * s, 0.334 * s, 0.112 * s, 0.05 * s, 0.014 * s, True, GOLD, GOLD_LIT, phase=0.5, tilt0=28, tilt1=34,
               curl=-6, nu=6, rim=0.55, lobe=0.0, ridge=0.35, tipk=0.25, nvi=3)
    # 束腰：八面，每面一个壸门（凸起的金线框，里面石青/朱砂相间），角上一根束腰柱，壸门里一朵宝相花
    rin = 0.652 * s
    half = rin * math.tan(math.pi / 8)
    for i in range(8):
        a = math.pi / 8 + 2 * math.pi * i / 8 + math.pi / 8
        a = 2 * math.pi * i / 8 + math.pi / 8 * 0 + math.pi / 8 - math.pi / 8
        nrm = V(math.cos(a), math.sin(a), 0)
        tan_ = V(-math.sin(a), math.cos(a), 0)
        c = nrm * rin
        # 角柱
        corner = c + tan_ * half * 0.98
        Vb, Tb = tube_mesh([corner + V(0, 0, 0.192 * s) + nrm * 0.004 * s, corner + V(0, 0, 0.328 * s) + nrm * 0.004 * s], 0.017 * s, segs=6)
        bag.add(G, Vb, Tb, GOLD)
        # 壸门：底平，两边直，上面三瓣的弧（像个倒挂的如意）
        w = half * 0.78
        zb, zt = 0.205 * s, 0.315 * s
        pts2 = []
        for t in np.linspace(0, 1, 7):
            pts2.append((-w + 2 * w * t, zb))
        for t in np.linspace(0, 1, 4)[1:]:
            pts2.append((w, zb + (zt - zb - 0.03 * s) * t))
        arch = []
        for t in np.linspace(0, 1, 25):
            x = w - 2 * w * t
            lob = 0.012 * s * abs(math.sin(3 * math.pi * t)) ** 0.7
            arch.append((x, zt - 0.03 * s + 0.03 * s * math.sin(math.pi * t) ** 0.6 + lob))
        pts2 += arch[1:]
        for t in np.linspace(0, 1, 4)[1:-1]:
            pts2.append((-w, zt - 0.03 * s - (zt - zb - 0.03 * s) * t))
        pts2.append(pts2[0])
        P3 = [c + nrm * 0.006 * s + tan_ * x + V(0, 0, z) for x, z in pts2]
        Vt, Tt = tube_mesh(P3, 0.0065 * s, segs=4, cap=False)
        bag.add(G, Vt, Tt, GOLD_LIT)
        # 壸门里的底色（比束腰再凹一点的一块板，颜色石青、朱砂相间）
        poly = [c + nrm * 0.002 * s + tan_ * x + V(0, 0, z) for x, z in pts2[:-1]]
        ctr = c + nrm * 0.002 * s + V(0, 0, (zb + zt) / 2)
        Vf = np.array([ctr] + poly)
        Tf = np.array([(0, 1 + k, 1 + (k + 1) % len(poly)) for k in range(len(poly))])
        bag.add(G, Vf, Tf, AZURE if i % 2 == 0 else MALACHITE * 0.9)
        # 宝相花：中间一颗珠，八片小瓣
        fc = c + nrm * 0.008 * s + V(0, 0, (zb + zt) / 2 + 0.004 * s)
        Vs, Ts = sphere_mesh(0.014 * s, 6, 4)
        bag.add(G, Vs + fc, Ts, GOLD_LIT)
        for k in range(8):
            b = 2 * math.pi * k / 8
            d = tan_ * math.cos(b) + V(0, 0, 1) * math.sin(b)
            Vs, Ts = sphere_mesh(1.0, 5, 4)
            Vs = Vs * np.array([0.022, 0.011, 0.007]) * s
            R = np.stack([d, np.cross(nrm, d), nrm], axis=1)
            bag.add(G, place(Vs, fc + d * 0.03 * s, R), Ts, GOLD)
        # 两边的卷草：一根从下往上卷的细管
        for sg in (-1, 1):
            pts = []
            for t in np.linspace(0, 1, 10):
                th = 3.6 * t
                rr = 0.026 * s * (1 - 0.7 * t)
                pts.append(fc + tan_ * sg * (0.055 * s + 0.03 * s * t + rr * math.cos(th)) + V(0, 0, rr * math.sin(th) - 0.01 * s))
            Vt, Tt = tube_mesh(pts, list(np.linspace(0.005, 0.003, 10) * s), segs=4)
            bag.add(G, Vt, Tt, GOLD)

    # ── 仰覆莲 ──
    sy = 0.92
    def lathe_round(pr, col, n=64):
        Vv, Q = ring_lathe([(r * s, z * s) for r, z in pr], n=n, rot=0.0)
        Vv[:, 1] *= sy
        bag.add(G, Vv, quads_to_tris(Q), col)
    lathe_round([(0.7, 0.462), (0.7, 0.5), (0.66, 0.56), (0.6, 0.62), (0.56, 0.66)], GOLD_DARK)
    lo = 1 if lod else 0
    # 覆莲：大瓣一圈（瓣尖淡朱），后面一圈小瓣（石绿）从缝里露出来
    petal_ring(bag, 16, 0.6 * s, 0.645 * s, 0.17 * s, 0.08 * s, 0.015 * s, False, GOLD, lin((0.4, 0.55, 0.45)), phase=0.5, sy=sy,
               tilt0=6, tilt1=52, curl=-28, nu=10 - lo, rim=0.22, lobe=0.0, ridge=0.16, tipk=0.4, nvi=3, cup=0.05)
    petal_ring(bag, 20, 0.62 * s, 0.6 * s, 0.21 * s, 0.11 * s, 0.017 * s, False, GOLD, lin((0.72, 0.3, 0.24)), sy=sy, tilt0=8,
               tilt1=62, curl=-40, nu=13 - 2 * lo, rim=0.22, lobe=0.17, ridge=0.12, tipk=0.45, cup=0.05)
    # 连珠
    bead_ring(bag, 40, 0.578 * s, 0.665 * s, 0.019 * s, sy, GOLD_LIT, tilt=10)
    lathe_round([(0.545, 0.64), (0.56, 0.68), (0.62, 0.78), (0.7, 0.9), (0.76, 0.975), (0.74, 0.985), (0.0, 0.985)], GOLD)
    # 仰莲三层：瓣尖分别染朱、石绿、金
    # 仰莲三层：瓣薄、窄一点（不是一个个鼓鼓的枕头），瓣边一道利的凸边、里面一片宝装内瓣、瓣尖利而略往外翻；
    # 正前面被悬裳盖住的几片不做（悬裳垂到最下一层莲瓣的根上）
    petal_ring(bag, 16, 0.56 * s, 0.68 * s, 0.36 * s, 0.16 * s, 0.018 * s, True, GOLD, lin((0.8, 0.36, 0.3)), sy=sy, tilt0=22,
               tilt1=84, curl=48, nu=13 - 2 * lo, skip_front=0.8, rim=0.2, lobe=0.16, ridge=0.12, tipk=0.45, cup=0.05, skip_back=0.7)
    petal_ring(bag, 16, 0.6 * s, 0.76 * s, 0.29 * s, 0.14 * s, 0.017 * s, True, GOLD, lin((0.32, 0.55, 0.48)), phase=0.5, sy=sy,
               tilt0=30, tilt1=86, curl=44, nu=14 - 2 * lo, skip_front=0.8, rim=0.2, lobe=0.16, ridge=0.12, tipk=0.4, cup=0.05, skip_back=0.7)
    petal_ring(bag, 16, 0.66 * s, 0.86 * s, 0.2 * s, 0.11 * s, 0.015 * s, True, GOLD, GOLD_LIT, sy=sy, tilt0=40, tilt1=86,
               curl=40, nu=11 - lo, skip_front=0.8, rim=0.22, lobe=0.0, ridge=0.14, tipk=0.3, nvi=3, cup=0.05, skip_back=0.7)
    # 台面边上一圈连珠
    bead_ring(bag, 48, 0.722 * s, 0.988 * s, 0.016 * s, sy, GOLD_LIT, tilt=35)
    return bag


# ====================================================================== 上色
def gilt_noise(Vv, seed=0):
    """鎏金的深浅：几层低频的起伏（不是光溜溜一片）"""
    rng = np.random.default_rng(seed)
    out = np.zeros(len(Vv))
    for f, a in ((3.0, 0.5), (7.0, 0.3), (17.0, 0.2)):
        k = rng.normal(size=(3, 3))
        ph = rng.uniform(0, 6.28, 3)
        out += a * np.sin(Vv @ k[0] * f + ph[0]) * np.sin(Vv @ k[1] * f + ph[1]) * np.cos(Vv @ k[2] * f * 0.7 + ph[2])
    return out


# ====================================================================== 组装、导出
def node_box(node, pad):
    return np.asarray(node.lo) - pad, np.asarray(node.hi) + pad


def decimate_regions(Vv, fl, regions, verbose=None):
    """分区减面：regions = [(区域函数(点) → 0/1, 这一区要剩多少三角形)]。一区一区来：
    Blender 的减面按顶点组只减组里的（权重 1 的减、0 的不动），所以每次只放开一区"""
    T = sdf.triangulate(fl)
    for k, (fn, target) in enumerate(regions):
        m = fn(Vv).astype(np.float64)
        tm = m[T].mean(axis=1) > 0.5
        n_in = int(tm.sum())
        if n_in <= target:
            continue
        ratio = (len(T) - n_in + target) / len(T)
        Vv, ls, lt, lv = sdf.decimate(Vv, [T], ratio, keep=m, keep_factor=1.0)
        T = sdf.polys_to_tris(ls, lt, lv)
        if verbose:
            print(f'[yjm] {verbose} 第{k + 1}区：{n_in} → {target}（现在共 {len(T)}）')
    return Vv, T


def sdf_piece(node, h, regions, verbose=None, lo=None, hi=None):
    """距离场 → 网格 → 分区减面。regions 可以是一个数（整块减到这么多）。返回 (verts, tris)"""
    if lo is None:
        lo, hi = np.asarray(node.lo) - 4 * h, np.asarray(node.hi) + 4 * h
    fld, Vv, fl = sdf.bake(node, lo, hi, h, verbose=verbose)
    n0 = sum(len(f) * (f.shape[1] - 2) for f in fl if len(f))
    if isinstance(regions, (int, float)):
        regions = [(lambda X: np.ones(len(X)), int(regions))]
    Vv, T = decimate_regions(Vv, fl, regions, verbose)
    if verbose:
        print(f'[yjm] {verbose}: {n0} → {len(T)} 个三角形')
    return Vv, T


FACE_UV = (-0.16, -0.27, 0.32, 0.39)        # 脸的贴图：头的局部 x、z 从哪到哪（x0, z0, 宽, 高）
SKIN_UV = (0.031, 0.031)                    # 脸贴图左下角 64×64 一块纯泥金的中心：手、脚、胸口都取这一点


def face_uv(H, Vv):
    """脸的贴图坐标：头的局部坐标正面投影（每个点都夹在贴图范围里）。朝后的点（耳后、后颈）u 钉到最近的那一侧边上、v 不变：
    贴图两边那一成、底下那一溜是纯泥金，所以跨在前后之间的三角形只会取到纯色（不会把眼线、唇红拉成一道缝）"""
    x, y, z = to_local(H, Vv[:, 0], Vv[:, 1], Vv[:, 2])
    x0, z0, w, h = FACE_UV
    u = np.clip((x - x0) / w, 0.002, 0.998)
    v = np.clip((z - z0) / h, 0.002, 0.998)
    back = y > -0.02
    u = np.where(back, np.where(x < 0, 0.002, 0.998), u)
    return np.stack([u, v], axis=1)


def clean_body(Vv, T, info, B):
    """身子网格的检查：扔掉零碎的小块（< 400 个点）；手边 15 厘米以内要是有一块不到 2000 个点的金（以前袖子在手腕上留下的那种圆片），
    直接报错（不能悄悄导出去）。再查一遍细长的三角形（长宽比 > 8）有多少"""
    lab = sdf.components(len(Vv), T)
    ids, cnt = np.unique(lab, return_counts=True)
    small = set(ids[cnt < 400])
    frames = info.get('hand_frames', {})
    for i, n in zip(ids, cnt):
        if n >= 2000:
            continue
        P = Vv[lab == i]
        for sx, F in frames.items():
            if np.min(np.linalg.norm(P - F.o, axis=1)) < 0.15 * B.s and n >= 400:
                lo_, hi_ = to_local(B, *P.min(0)), to_local(B, *P.max(0))
                raise RuntimeError(f'身子网格在手（{sx}）边上有一块 {n} 个点的小金块：袖子没切干净（身子坐标 {np.round(lo_, 3)}..{np.round(hi_, 3)}）')
    keep = ~np.isin(lab, list(small))
    if small:
        print(f'[yjm] 身子：扔掉 {len(small)} 块零碎（共 {int((~keep).sum())} 个点）')
    remap = -np.ones(len(Vv), np.int64)
    remap[keep] = np.arange(int(keep.sum()))
    T2 = remap[T]
    T2 = T2[(T2 >= 0).all(axis=1)]
    Vv = Vv[keep]
    a, b, c = Vv[T2[:, 0]], Vv[T2[:, 1]], Vv[T2[:, 2]]
    e = np.stack([np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1), np.linalg.norm(a - c, axis=1)], axis=1)
    area = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2
    asp = e.max(axis=1) ** 2 / np.maximum(2 * area, 1e-12)
    print(f'[yjm] 身子：长宽比 > 8 的三角形 {int((asp > 8).sum())} / {len(T2)}')
    return Vv, T2


def voxel_keys(X, h):
    q = np.floor(np.asarray(X) / h).astype(np.int64) + 4096
    return (q[:, 0] * 8192 + q[:, 1]) * 8192 + q[:, 2]


def path_keys(paths, h):
    """一串串线上的点占到的格子（再往外扩一格）"""
    P = np.vstack(paths)
    out = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                out.append(voxel_keys(P + np.array([dx, dy, dz]) * h, h))
    return np.unique(np.concatenate(out))


def buddha_bag(mudra, s, res=1.0, verbose=True, budget=1.0):
    """一尊佛（含莲座）的全部网格，放在 Bag 里（还没烤暗部）"""
    bag = throne(s, lod=0 if budget > 0.9 else 1)
    B = Frame((0, 0, 0.98 * s), None, s)
    P = Pose(mudra)
    info = {}
    fig = figure(B, P, info)
    H = info['face']
    tag = verbose and mudra

    # ── 头：脸正面、头发底下（螺发盖住）、其余（耳、颈）分区减面 ──
    def face_region(X):
        x, y, z = to_local(H, X[:, 0], X[:, 1], X[:, 2])
        return (y < -0.085) & (z > -0.235) & (z < 0.07) & (np.abs(x) < 0.125)

    def hair_region(X):
        x, y, z = to_local(H, X[:, 0], X[:, 1], X[:, 2])
        return z > hairline_z(np.arctan2(x, -y)) + 0.008
    def neck_region(X):     # 颈前那三道：单独留够面（减面以后还是三道连续的弧）
        x, y, z = to_local(H, X[:, 0], X[:, 1], X[:, 2])
        return (y < 0.0) & (z < -0.205) & (z > -0.34) & ~face_region(X)
    hv, ht = sdf_piece(fig['head'], 0.0021 * s * res,
                       [(face_region, int(26000 * budget)), (hair_region, int(2000 * budget)), (neck_region, int(4500 * budget)),
                        (lambda X: ~face_region(X) & ~hair_region(X) & ~neck_region(X), int(12000 * budget))], tag and 'head')
    x, y, z = to_local(H, hv[:, 0], hv[:, 1], hv[:, 2])
    hair = ss(0.004, 0.007, z - hairline_z(np.arctan2(x, -y)))          # 拆开的那条线藏在最下面一排螺发底下
    tri_hair = hair[ht].mean(axis=1) > 0.5
    bag.add('paint_buddha_face', hv, ht[~tri_hair], np.ones(3), UV=face_uv(H, hv))
    bag.add('toon', hv, ht[tri_hair], HAIR * 0.45)          # 螺发底下的头皮：深（缝里是暗的）
    jewel(bag, H, info.get('jewel_local'))
    # 螺发
    cv, ct, cb, cp = curls(H, fig['head'], info, d=0.0221 if s > 0.95 else 0.0242)
    bag.add('toon', cv, ct, np.clip(HAIR[None, :] * cb[:, None], 0, 1))
    info['n_curls'] = len(cp)
    # ── 手、脚 ──
    for k, nd in enumerate(fig['hands']):
        vv, tt = sdf_piece(nd, 0.0016 * s * res, int(7600 * budget), tag and f'hand{k}')
        bag.add('paint_buddha_face', vv, tt, np.ones(3), UV=np.tile(SKIN_UV, (len(vv), 1)))
    # ── 胸前的绅带结（单独细抽：带子只有四毫米厚） ──
    kv, kt = sdf_piece(fig['knot'], 0.0013 * s * res, int(2500 * budget), tag and 'knot')
    bag.add('gold', kv, kt, GOLD)
    # ── 身子和衣服：衣纹那一圈（离表面近、曲率大的地方）、悬裳下摆单独留得密一点 ──
    def hem_region(X):      # 悬裳（和腿前那一溜）
        x, y, z = to_local(B, X[:, 0], X[:, 1], X[:, 2])
        return (y < -0.5) & (z < 0.1) & (np.abs(x) < 0.5)
    fold_keys = path_keys(info['fold_paths'], 0.02 * s)

    def fold_region(X):     # 衣褶两边各两三厘米：减面的预算往这里多给（褶棱减完还是顺的）
        return np.isin(voxel_keys(X, 0.02 * s), fold_keys) & ~hem_region(X)
    # 悬裳多给一点（11k → 15k，从其余那一区挪过来）：兜里的 U 形褶在兜尖那里挤在一起，面不够时褶棱成了一截截的锯齿，
    # 鎏金的反光（toon_gilt）把这种小折面放大得很显眼
    bv, bt = sdf_piece(fig['body'], 0.0036 * s * res,
                       [(hem_region, int(15000 * budget)), (fold_region, int(36000 * budget)),
                        (lambda X: ~hem_region(X) & ~fold_region(X), int(39000 * budget))],
                       tag and 'body', lo=B.p(-1.0, -0.95, -0.4), hi=B.p(1.0, 0.62, 1.3))
    bv, bt = clean_body(bv, bt, info, B)
    c = np.tile(GOLD, (len(bv), 1)) * (1 + 0.05 * gilt_noise(bv / s, 3))[:, None]
    bag.add('gold', bv, bt, c)
    # ── 手里拿的：药钵 / 莲花 / 诃子 ──
    attributes(bag, P, info, s)
    # ── 衣缘（贴手绘纹样的带子） ──
    for st in info['strips']:
        vv, tt, uv = strip_mesh(st['Q'], st['N'], st['w'], st['t'], st.get('closed', False), period=st['w'] * 8,
                                sub=1 if st.get('dense') else 3, sink=st.get('sink', 0.012 * s))
        bag.add('paint_robe_band', vv, tt, np.ones(3), UV=uv)
    return bag, info


def check_export(name):
    """读回导出的 .yjm：每个点的法线都要是单位长（零法线到 Unity 里归一化成 NaN，会出黑点），没有面积为零的三角形"""
    import json
    import os
    import struct
    import kit
    raw = open(os.path.join(kit.OUT, name + '.yjm'), 'rb').read()
    n = struct.unpack('<I', raw[4:8])[0]
    hd = json.loads(raw[8:8 + n])
    off = 8 + n
    for p in hd['parts']:
        nv, nt = p['verts'], p['tris']
        pos = np.frombuffer(raw, np.float32, nv * 3, off).reshape(-1, 3)
        off += nv * 12
        nrm = np.frombuffer(raw, np.float32, nv * 3, off).reshape(-1, 3)
        off += nv * 12 + nv * 4 + nv * 8
        idx = np.frombuffer(raw, np.uint32, nt * 3, off).reshape(-1, 3)
        off += nt * 12
        L = np.linalg.norm(nrm, axis=1)
        bad = int((~(L > 0.5)).sum())
        a, b, c = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
        dg = int((np.linalg.norm(np.cross(b - a, c - a), axis=1) < 2e-10).sum())
        if bad:
            raise RuntimeError(f'{name}/{p["mat"]}: {bad} 个点的法线长度不对（在 {pos[~(L > 0.5)][:4].round(3).tolist()}）')
        print(f'[yjm] {name}/{p["mat"]}: 法线全部正常，面积为零的三角形 {dg} 个')


def buddha(name, mudra, s):
    import kit
    a = kit.Asset(name)
    bag, info = buddha_bag(mudra, s, budget=1.0 if s > 0.95 else 0.66)
    H = info['face']

    def chin(X):            # 下巴、嘴唇、腮帮那一片：暗部托底（不出脏污）
        x, y, z = to_local(H, X[:, 0], X[:, 1], X[:, 2])
        return ss(-0.07, -0.1, z) * ss(-0.02, -0.06, y) * (1 - ss(-0.25, -0.29, z)) * (1 - ss(0.12, 0.15, np.abs(x)))
    bag.bake_ao(dist=0.22 * s, samples=48, face=dict(strength=0.4, blur=0.025 * s, floor_fn=chin), shell_k=0.35)
    # 第二遍只看近处（4 厘米）：衣褶的沟、袖口、指缝、衣缘底下、莲瓣根这些窄缝里积的深褐金（大的那遍抹不出这么细的线），
    # 衣纹从拜垫、过道上看是一道道分得清的。脸、手只轻轻压一点（抛光的泥金，不出脏污）；衣缘带子、螺发不压
    bag.bake_ao(dist=0.04 * s, samples=32, strength=0.55, shade=(0.55, 0.38, 0.22), skip=('toon', 'paint_robe_band'),
                face=dict(strength=0.25, blur=0.006 * s, floor_fn=chin), shell_k=0.3)
    bag.gilt(s)
    bag.to_asset(a)
    print(f'[yjm] {name}: 合计 {bag.tris()} 个三角形')
    tris = a.finish(ao=False, view=(18, 12, 0.9))
    check_export(name)
    return tris


def buddha_center(name):
    """中尊释迦牟尼：说法印（右手），结跏趺坐（吉祥坐）"""
    return buddha(name, 'teach', 1.0)


def buddha_west(name):
    """西边（-x，从殿门看是左边）阿弥陀佛：弥陀定印，掌上托莲。按 0.85 倍做好。
    横三世佛的规矩是「东方药师、西方阿弥陀」：东边（+x）是药师，西边（-x）是阿弥陀（原来的分工反了，这里改过来）"""
    return buddha(name, 'amida', 0.85)


def buddha_east(name):
    """东边（+x）药师佛：左手托药钵，右手与愿印拈诃子。按 0.85 倍做好"""
    return buddha(name, 'bowl', 0.85)


ASSETS = {
    'buddha_center': buddha_center,
    'buddha_west': buddha_west,
    'buddha_east': buddha_east,
}


def smooth_path(Q, N, it=2, closed=False):
    Q, N = np.array(Q, np.float64), np.array(N, np.float64)
    for _ in range(it):
        if closed:
            Q = (np.roll(Q, 1, 0) + 2 * Q + np.roll(Q, -1, 0)) / 4
            N = (np.roll(N, 1, 0) + 2 * N + np.roll(N, -1, 0)) / 4
        else:
            Q[1:-1] = (Q[:-2] + 2 * Q[1:-1] + Q[2:]) / 4
            N[1:-1] = (N[:-2] + 2 * N[1:-1] + N[2:]) / 4
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    return Q, N


def strip_mesh(Q, N, w, t, closed=False, period=None, sub=3, nv=9, sink=0.012):
    """贴着表面的一条衣缘（真正的网格，上面贴手绘的纹样）：截面是中间平、两边圆下去的一条，两边沉进衣服里一点。
    返回 (verts, tris, uv 每个点一个)：u 沿带子（按 period 米一遍），v 横过带子 0..1"""
    if closed and np.linalg.norm(Q[0] - Q[-1]) < 1e-6:
        Q, N = Q[:-1], N[:-1]
    Q, N = smooth_path(Q, N, 2, closed)
    # 加密：每段再分 sub 份（Catmull-Rom）
    P = np.array(sdf.catmull(list(Q) + ([Q[0]] if closed else []), sub))
    Nn = np.array(sdf.catmull(list(N) + ([N[0]] if closed else []), sub))
    Nn /= np.linalg.norm(Nn, axis=1, keepdims=True)
    if closed:
        P, Nn = P[:-1], Nn[:-1]
    n = len(P)
    tang = np.roll(P, -1, 0) - np.roll(P, 1, 0) if closed else np.gradient(P, axis=0)
    tang /= np.linalg.norm(tang, axis=1, keepdims=True)
    side = np.cross(Nn, tang)
    side /= np.linalg.norm(side, axis=1, keepdims=True)
    seg = np.linalg.norm(np.diff(np.vstack([P, P[:1]]) if closed else P, axis=0), axis=1)
    sl = np.concatenate([[0], np.cumsum(seg)])
    period = period or w * 8
    vs = np.linspace(-1, 1, nv)
    prof = t * np.sqrt(np.clip(1 - np.abs(vs) ** 6, 0, 1)) - sink * (np.abs(vs) > 0.999)
    prof = np.where(np.abs(vs) > 0.999, -sink, prof)
    VV, UVv = [], []
    rows = n + (1 if closed else 0)
    for i in range(rows):
        k = i % n
        for j, v in enumerate(vs):
            VV.append(P[k] + side[k] * (v * w / 2) + Nn[k] * prof[j])
            UVv.append((sl[i] / period, (v + 1) / 2))
    T = []
    for i in range(rows - 1):
        for j in range(nv - 1):
            a = i * nv + j
            T += [(a, a + nv, a + nv + 1), (a, a + nv + 1, a + 1)]
    T = np.array(T)
    # 朝向：第一个三角形的法线要和表面法线同向
    a, b, c = VV[T[0][0]], VV[T[0][1]], VV[T[0][2]]
    if np.dot(np.cross(np.asarray(b) - a, np.asarray(c) - a), Nn[0]) < 0:
        T = T[:, ::-1]
    return np.array(VV), T, np.array(UVv)


# ====================================================================== 背光
# 背光装在莲座上（不是贴在墙上）：一块往前倾 8° 的板，板的中面在头后面 ~0.17 米（中尊）；
# 板上的平面坐标 (x 横, w 沿板往上)，单位米（中尊的大小；两边的整体按 0.85 缩），原点 = 头光圆心。
# 头光圆心按「跪在中间拜垫上抬头看」时正好套住头来定（比头的中心高 0.28 米：板在头后面，从下往上看要往上挪）。
# 身光是个椭圆，外面一圈镂空的火焰（一条条 S 形往上卷的火舌，火舌之间是透空的），顶上一颗火焰宝珠。
HEAD_R = 0.52
BODY_C, BODY_A = (0.0, -0.84), (0.94, 0.98)
LEAN = math.radians(8.0)
PLATE_O = V(0, 0.4337, 2.8546)        # 头光圆心（莲座底面中心的坐标，-y 朝前）：头低下来以后沿板往上挪了 4.5 厘米（跪垫上看还套着头）
PLATE_T = 0.045                       # 板厚
MX0, MX1, MW0, MW1 = -1.3, 1.3, -1.78, 1.02        # 板的平面范围（也是贴图的范围）
CUT_Z = 1.07                          # 板的下沿（莲座底面以上的高度）：在最上一层莲瓣尖上面
W_TOP = 0.935                         # 板的上沿（头光圆心以上，沿板量）：圆心上挪了，上沿收回来，板顶的高度不变


def plate_axes():
    """板的三根轴（莲座坐标）：ex 横、ew 沿板往上、en 朝前（板的正面）"""
    ex = V(1, 0, 0)
    ew = V(0, -math.sin(LEAN), math.cos(LEAN))
    en = V(0, -math.cos(LEAN), -math.sin(LEAN))
    return ex, ew, en


def _seg_dist(X, W, pts, rad):
    """格点 (X, W) 到折线的距离、最近处的半径、沿线的参数 t（0..1）"""
    best = np.full(X.shape, 1e9, np.float32)
    rb = np.zeros(X.shape, np.float32)
    tb = np.zeros(X.shape, np.float32)
    n = len(pts)
    L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    for i in range(n - 1):
        a, b = pts[i], pts[i + 1]
        ab = b - a
        l2 = max(ab.dot(ab), 1e-12)
        t = np.clip(((X - a[0]) * ab[0] + (W - a[1]) * ab[1]) / l2, 0, 1)
        dx, dw = X - (a[0] + t * ab[0]), W - (a[1] + t * ab[1])
        d = np.sqrt(dx * dx + dw * dw)
        m = d < best
        best = np.where(m, d, best)
        rb = np.where(m, rad[i] + (rad[i + 1] - rad[i]) * t, rb)
        tb = np.where(m, (L[i] + t * np.sqrt(l2)) / max(L[-1], 1e-9), tb)
    return best, rb, tb


class Raster:
    """背光的平面图：d 轮廓的有符号距离（里负）、h 浮雕高（米）、zone 区域（0 火焰 1 身光 2 头光 3 宝珠）、gold 金（0..1）"""

    def __init__(self, step):
        self.step = step
        self.xs = np.arange(MX0, MX1 + step / 2, step)
        self.ws = np.arange(MW0, MW1 + step / 2, step)
        self.X, self.W = np.meshgrid(self.xs, self.ws)
        sh = self.X.shape
        self.d = np.full(sh, 1.0, np.float32)
        self.h = np.zeros(sh, np.float32)
        self.zone = np.zeros(sh, np.int8)
        self.gold = np.zeros(sh, np.float32)

    def win(self, lo, hi):
        i0 = max(int((lo[1] - MW0) / self.step), 0)
        i1 = min(int((hi[1] - MW0) / self.step) + 2, len(self.ws))
        j0 = max(int((lo[0] - MX0) / self.step), 0)
        j1 = min(int((hi[0] - MX0) / self.step) + 2, len(self.xs))
        return (slice(i0, i1), slice(j0, j1)) if i1 > i0 and j1 > j0 else None

    def stroke(self, pts, rad, height, base=0.0, shape=True, gold=1.0, groove=0.0, zmask=None):
        """一笔（管子压扁的浮雕）：pts 折线 (n,2)，rad 每点半径；height 鼓起来的高；shape=True 时也算进轮廓（镂空的火舌）"""
        pts = np.asarray(pts, np.float64)
        rad = np.asarray(rad, np.float64)
        pad = rad.max() + self.step * 2
        w = self.win(pts.min(0) - pad, pts.max(0) + pad)
        if w is None:
            return
        X, W = self.X[w], self.W[w]
        d, r, t = _seg_dist(X, W, pts, rad)
        sd = d - r
        q = np.clip(d / np.maximum(r, 1e-6), 0, 1)
        prof = np.sqrt(np.clip(1 - q * q, 0, 1)) ** 0.7
        if groove > 0:            # 火舌中间一道刻线
            prof = prof - groove * np.exp(-(q / 0.18) ** 2) * (t < 0.92)
        hh = base + height * prof
        inside = sd < 0
        if zmask is not None:
            inside &= zmask[w]
        if shape:
            self.d[w] = np.minimum(self.d[w], sd)
        self.h[w] = np.where(inside, np.maximum(self.h[w], hh), self.h[w])
        self.gold[w] = np.where(inside, np.maximum(self.gold[w], gold * ss(0.0, 0.5, prof)), self.gold[w])


def _scroll_unit(c, tang, nrm, size, flip):
    """卷草的一个单元（板上的平面坐标）：一段卷进去的螺旋卷须 + 一片尖叶。tang 沿主蔓、nrm 指向卷须那边"""
    pts_t, rad_t = [], []
    for k in range(26):
        u = k / 25
        ang = math.pi * (0.2 + 2.6 * u)
        rr = size * (0.66 - 0.56 * u)
        p = c + nrm * size * 0.55 + tang * (rr * math.cos(ang) * flip) + nrm * (rr * math.sin(ang) - size * 0.1)
        pts_t.append(p)
        rad_t.append(size * (0.13 - 0.085 * u))
    # 卷须的根接到主蔓上
    pts_t = [c - tang * size * 0.25 * flip] + pts_t
    rad_t = [size * 0.13] + rad_t
    leaf, lr = [], []
    for k in range(13):
        u = k / 12
        p = c + tang * (size * (0.15 + 0.85 * u) * flip) - nrm * (size * (0.12 + 0.42 * math.sin(math.pi * u * 0.85)))
        leaf.append(p)
        lr.append(size * (0.05 + 0.34 * math.sin(math.pi * min(u * 1.15, 1)) ** 0.8))
    return (np.array(pts_t), np.array(rad_t)), (np.array(leaf), np.array(lr))


_RASTER = {}


def _blur2(A, sig):
    """二维高斯模糊（可分离，sig 以格为单位）"""
    r = max(int(sig * 3), 1)
    g = np.exp(-0.5 * (np.arange(-r, r + 1) / sig) ** 2)
    g /= g.sum()
    A = np.pad(A, r, mode='edge')
    A = np.apply_along_axis(lambda v: np.convolve(v, g, mode='valid'), 0, A)
    A = np.apply_along_axis(lambda v: np.convolve(v, g, mode='valid'), 1, A)
    return A.astype(np.float32)


def mandorla_raster(step=0.003):
    """算一次背光的平面图（缓存）。模型和手绘贴图用同一张：纹样和浮雕一点不差"""
    if step in _RASTER:
        return _RASTER[step]
    R = Raster(step)
    X, W = R.X, R.W
    rh = np.hypot(X, W)
    th_h = np.arctan2(X, W)
    ex, ew = (X - BODY_C[0]) / BODY_A[0], (W - BODY_C[1]) / BODY_A[1]
    e = np.hypot(ex, ew)
    th_b = np.arctan2(ex, ew)
    d_head = rh - HEAD_R
    d_body = (e - 1) * min(BODY_A)
    d_halo = np.minimum(d_head, d_body)
    inh = d_head < 0
    inb = (d_body < 0) & ~inh
    R.zone = np.where(inb, 1, np.where(inh, 2, 0)).astype(np.int8)
    R.d = np.minimum(R.d, d_halo - 0.03)          # 光圈外沿再加一道 3 厘米的火焰底边（实的）

    def rim_steps(r, levels):
        """一圈台阶式的边：levels = [(r0, r1, 高), ...]（r 是相对半径），边上有一点倒角"""
        out = np.zeros_like(r)
        for r0, r1, hh in levels:
            out = np.maximum(out, hh * ss(r0, r0 + 0.011, r) * (1 - ss(r1 - 0.011, r1, r)))
        return out
    # ── 身光：放射的细线、卷草带、连珠、三级台阶的外沿 ──
    hb = 0.005 + 0.0035 * np.abs(np.cos(th_b * 40)) ** 10 * ss(0.25, 0.4, e) * (1 - ss(0.66, 0.7, e))
    hb = np.maximum(hb, rim_steps(e, [(0.905, 1.0, 0.016), (0.935, 0.985, 0.025), (0.955, 0.975, 0.031)]))
    hb = np.maximum(hb, 0.004 * ss(0.71, 0.715, e) * (1 - ss(0.85, 0.855, e)))       # 卷草带的底（略低）
    R.h = np.where(inb, hb, R.h)
    R.gold = np.where(inb, np.maximum(ss(0.0035, 0.007, hb - 0.005), ss(0.9, 0.91, e)), R.gold)
    # ── 头光：中心一朵莲（两层瓣、莲蓬）、放射线、连珠、卷草带、台阶外沿 ──
    r = rh / HEAD_R
    hh = 0.006 + 0.0035 * np.abs(np.cos(th_h * 32)) ** 10 * ss(0.34, 0.42, r) * (1 - ss(0.58, 0.62, r))
    hh = np.maximum(hh, rim_steps(r, [(0.9, 1.0, 0.018), (0.93, 0.985, 0.027), (0.955, 0.975, 0.033)]))
    hh = np.maximum(hh, 0.005 * ss(0.63, 0.635, r) * (1 - ss(0.83, 0.835, r)))
    # 中心莲花：外圈 12 瓣、里圈 8 瓣（瓣是带一圈边的凸台），中间莲蓬
    for n_, r0, r1, hgt, ph in ((12, 0.06, 0.3, 0.016, 0.0), (8, 0.04, 0.19, 0.024, 0.5)):
        a = (th_h / (2 * np.pi) * n_ + ph) % 1.0 - 0.5            # 每瓣里的横向位置 -0.5..0.5
        shape = (1 - (2 * np.abs(a)) ** 2.2) ** 0.6                # 瓣的外轮廓（尖头）
        rr = r0 + (r1 - r0) * shape
        inside_p = (r < rr) & (r > 0.02)
        edge = ss(rr - 0.012, rr - 0.04, r)                         # 瓣边一圈略高（rr 处是边）
        val = hgt * (0.75 + 0.25 * (1 - edge)) * inside_p
        hh = np.where(inside_p, np.maximum(hh, val), hh)
    hh = np.maximum(hh, 0.03 * (r < 0.065) * np.sqrt(np.clip(1 - (r / 0.065) ** 2, 0, 1)) ** 0.5)
    R.h = np.where(inh, hh, R.h)
    R.gold = np.where(inh, np.maximum(ss(0.0035, 0.007, hh - 0.006), 0.0), R.gold)
    # 连珠
    for (n_, rr, rad, z_, cx, cy, ax, ay) in ((48, 0.865 * HEAD_R, 0.011, 2, 0, 0, 1, 1), (72, 0.875, 0.012, 1, BODY_C[0], BODY_C[1], BODY_A[0], BODY_A[1])):
        for k in range(n_):
            a = 2 * math.pi * k / n_
            if z_ == 2:
                p = V(math.sin(a) * rr, math.cos(a) * rr)
            else:
                p = V(cx + math.sin(a) * rr * ax, cy + math.cos(a) * rr * ay)
            zm = (R.zone == z_)
            R.stroke([p, p + 1e-4], [rad, rad], 0.013, base=0.006, shape=False, zmask=zm)
    # 卷草带：主蔓一圈波浪 + 每个单元一个卷须、一片叶（高 2 厘米多）
    # 卷草带：主蔓一圈波浪，波峰、波谷各出一个单元（一里一外交替，卷的方向一致），每个单元一段卷须、一大一小两片带叶脉的叶子，
    # 叶子互相压着、把带子铺满（比原来密一倍）
    for z_, n_u, rad_fn in ((2, 28, lambda a: (0.73 * HEAD_R, 0.73 * HEAD_R)), (1, 52, lambda a: (0.78 * BODY_A[0], 0.78 * BODY_A[1]))):
        cx, cy = (0.0, 0.0) if z_ == 2 else BODY_C
        zm = (R.zone == z_)
        stem, srad = [], []
        size = 0.058 if z_ == 2 else 0.064
        wob_a = 0.018
        for k in range(n_u * 10 + 1):
            a = 2 * math.pi * k / (n_u * 10)
            ax, ay = rad_fn(a)
            wob = wob_a * math.sin(n_u * a / 2)
            stem.append(V(cx + math.sin(a) * (ax + wob), cy + math.cos(a) * (ay + wob)))
            srad.append(0.0055)
        R.stroke(stem, srad, 0.015, base=0.005, shape=False, zmask=zm)
        for k in range(n_u):
            a = 2 * math.pi * (k + 0.5) / n_u
            ax, ay = rad_fn(a)
            sg = 1 if k % 2 == 0 else -1
            c = V(cx + math.sin(a) * (ax + sg * wob_a), cy + math.cos(a) * (ay + sg * wob_a))
            tang = V(math.cos(a) * ax, -math.sin(a) * ay)
            tang /= np.linalg.norm(tang)
            nrm = V(math.sin(a), math.cos(a)) * sg
            (tp, tr), (lp, lrr) = _scroll_unit(c, tang, nrm, size, float(sg))
            R.stroke(lp, lrr, 0.016, base=0.005, shape=False, zmask=zm, groove=0.4)
            # 第二片小叶：压在卷须根上、朝另一边
            (_, _), (lp2, lr2) = _scroll_unit(c - tang * size * 0.35, -tang, -nrm, size * 0.62, float(-sg))
            R.stroke(lp2, lr2, 0.014, base=0.005, shape=False, zmask=zm, groove=0.4)
            R.stroke(tp, tr, 0.02, base=0.005, shape=False, zmask=zm)
    # ── 火焰：沿光圈外沿一圈连着的火焰带。每条火舌根宽（和左右两条压着、咬在一起）、梢细，S 形，边上两三个起伏（火苗的瓣），
    #    中间一道刻线；方向从最下面的往外（放射）慢慢变成往上（火往上烧），越往上越长；头光顶上让给火焰宝珠 ──
    rng = np.random.default_rng(21)
    jc = V(0, HEAD_R + 0.2)                   # 火焰宝珠的珠心
    base_pts = []
    for k in range(600):
        a = 2 * math.pi * k / 600
        p = V(math.sin(a) * HEAD_R, math.cos(a) * HEAD_R)
        if (np.hypot((p[0] - BODY_C[0]) / BODY_A[0], (p[1] - BODY_C[1]) / BODY_A[1]) > 1.0):
            base_pts.append((p, V(math.sin(a), math.cos(a))))
        p = V(BODY_C[0] + math.sin(a) * BODY_A[0], BODY_C[1] + math.cos(a) * BODY_A[1])
        if np.hypot(p[0], p[1]) > HEAD_R:
            nb = V(math.sin(a) / BODY_A[0], math.cos(a) / BODY_A[1])
            base_pts.append((p, nb / np.linalg.norm(nb)))
    base_pts.sort(key=lambda q: math.atan2(q[0][0], q[0][1] + 0.5))
    P0 = np.array([q[0] for q in base_pts])
    N0 = np.array([q[1] for q in base_pts])
    Ls = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P0, axis=0), axis=1))])
    nt = int(Ls[-1] / 0.082)
    # 火焰带的底（实的一道，3~5 厘米）
    R.d = np.minimum(R.d, d_halo - (0.035 + 0.02 * ss(-1.2, 0.5, W)))
    # 第四轮（评审：「哑光的橙色锯齿圈」）：火舌窄一些、长一些、密一些，分两层——
    #   外层大火舌（S 形，梢上卷成钩，外沿分出一小股火苗），里层小火舌插在两条大火舌的根之间、卷得更紧，
    #   每条中间都有一道刻线、一道描金的内焰线；整圈贴金（贴图的 a，着色器按鎏金画），沟里留一点朱红
    def flame(Bp, nB, hgt, side, L, wmax, turn_deg, lob_k, n_=26):
        up = V(0, 1)
        blend = 0.15 + 0.75 * hgt
        dirv = nB * (1 - blend) + up * blend
        dirv /= np.linalg.norm(dirv)
        th0 = math.atan2(dirv[1], dirv[0])
        turn = -side * math.radians(turn_deg) * (0.7 + 0.3 * hgt)
        pts, rad = [], []
        p = Bp - nB * 0.03
        for k in range(n_):
            t = k / (n_ - 1)
            pts.append(p.copy())
            lob = 1 + lob_k * math.sin(math.pi * 3.2 * t + 0.4) * (1 - t)
            rad.append(wmax * spow(math.sin(math.pi * min(1.0, 0.16 + 0.84 * t ** 0.75)), 0.8) * lob + 0.003)
            th = th0 + turn * t ** 2.0 + side * 0.32 * math.sin(math.pi * t)
            p = p + V(math.cos(th), math.sin(th)) * (L / (n_ - 1))
        return pts, rad

    big, small = [], []
    nt = int(Ls[-1] / 0.066)
    for i, sv in enumerate(np.linspace(0, Ls[-1], nt)):
        for layer, frac in ((0, 0.0), (1, 0.5)):
            s_ = min(sv + frac * Ls[-1] / nt, Ls[-1])
            j = min(np.searchsorted(Ls, s_), len(P0) - 1)
            Bp, nB = P0[j], N0[j]
            if Bp[1] < MW0 + 0.08 or (Bp[1] > HEAD_R * 0.8 and abs(Bp[0]) < 0.15):
                continue                                   # 最顶上那几条让给火焰宝珠
            hgt = ss(-1.3, 0.55, Bp[1])                     # 0 在最下面，1 在头光两肩
            side = 1.0 if Bp[0] >= 0 else -1.0
            if layer == 0:
                L = (0.19 + 0.12 * hgt) * rng.uniform(0.9, 1.1)
                pts, rad = flame(Bp, nB, hgt, side, L, 0.04 + 0.008 * hgt, 125, 0.2)
                big.append((Bp[1], pts, rad))
                # 外沿分出的一小股火苗：从大火舌的六成处往外、往上卷
                k0 = int(len(pts) * 0.55)
                q0 = np.asarray(pts[k0])
                tg = np.asarray(pts[k0 + 1]) - q0
                tg /= max(np.linalg.norm(tg), 1e-9)
                out_ = V(tg[1], -tg[0]) * side
                bp2, br2 = flame(q0, out_ * 0.6 + tg * 0.4, hgt, side, L * 0.38, 0.017, 140, 0.1, 14)
                small.append((Bp[1] + 0.001, bp2, br2))
            else:
                L = (0.1 + 0.05 * hgt) * rng.uniform(0.85, 1.1)
                pts, rad = flame(Bp, nB, hgt, side, L, 0.024, 160, 0.12, 18)
                small.append((Bp[1], pts, rad))
    # 从下往上画：上面的火舌压在下面那条的梢上（一片压一片地咬住）；小火舌压在大火舌上
    for _, pts, rad in sorted(big, key=lambda q: q[0]):
        R.stroke(pts, rad, 0.02, base=0.006, shape=True, gold=1.0, groove=0.36)
        n2 = int(len(pts) * 0.72)
        R.stroke(pts[2:n2], [r * 0.3 for r in rad[2:n2]], 0.026, base=0.006, shape=False, gold=1.0)
    for _, pts, rad in sorted(small, key=lambda q: q[0]):
        R.stroke(pts, rad, 0.024, base=0.008, shape=True, gold=1.0, groove=0.3)
        n2 = int(len(pts) * 0.7)
        R.stroke(pts[1:n2], [r * 0.32 for r in rad[1:n2]], 0.029, base=0.008, shape=False, gold=1.0)
    # ── 顶上：火焰宝珠 —— 莲托上一颗刻了棱面的宝珠，七股火焰从珠子后面往上、往两边烧，梢往里卷 ──
    RJ = 0.064
    for k in range(7):
        a_ = math.radians(-78 + 26 * k)
        L = 0.12 + 0.11 * math.cos(a_) ** 2
        d0 = V(math.sin(a_), math.cos(a_))
        side = -1.0 if a_ > 0 else 1.0
        pts, rad = [], []
        p = jc + d0 * RJ * 0.7
        th0 = math.atan2(d0[1], d0[0])
        for j in range(18):
            t = j / 17
            pts.append(p.copy())
            rad.append((0.026 + 0.008 * math.cos(a_)) * spow(math.sin(math.pi * min(1.0, 0.2 + 0.8 * t ** 0.8)), 0.8) + 0.003)
            th = th0 + side * math.radians(70) * t ** 2.2 * (0.3 + abs(math.sin(a_)))
            p = p + V(math.cos(th), math.sin(th)) * (L / 17)
        R.stroke(pts, rad, 0.022, base=0.006, shape=True, gold=1.0, groove=0.32)
        R.stroke(pts[2:12], [r * 0.3 for r in rad[2:12]], 0.027, base=0.006, shape=False, gold=1.0)
    # 莲托：珠子下面三瓣仰莲
    for k, a_ in enumerate((-55, 0, 55)):
        a_ = math.radians(a_)
        c0 = jc + V(0, -RJ * 0.95)
        tip = c0 + V(math.sin(a_), math.cos(a_)) * 0.075 + V(0, -0.012 * (k != 1))
        pts = [c0 + (tip - c0) * t for t in np.linspace(0, 1, 10)]
        R.stroke(pts, [0.03 * spow(math.sin(math.pi * min(1.0, 0.15 + 0.85 * t)), 0.6) + 0.004 for t in np.linspace(0, 1, 10)], 0.02, base=0.006, shape=True, gold=1.0, groove=0.25)
    rj = np.hypot(X - jc[0], W - jc[1])
    inj = rj < RJ
    R.zone = np.where(inj, 3, R.zone).astype(np.int8)
    # 宝珠：八个棱面（刻出来的），顶上一点、中间一圈略低
    thj = np.arctan2(X - jc[0], W - jc[1])
    facet = 0.85 + 0.15 * np.abs(np.cos(thj * 4)) ** 0.5
    R.h = np.where(inj, np.maximum(R.h, 0.016 + 0.034 * np.sqrt(np.clip(1 - (rj / RJ) ** 2, 0, 1)) * facet), R.h)
    R.d = np.minimum(R.d, rj - RJ)
    R.gold = np.where(inj, np.maximum(ss(RJ - 0.01, RJ, rj), 1.0 - ss(0.0, RJ * 0.55, rj) * 0.0), R.gold)
    # 顶上截齐：板最高到头光圆心上面 W_TOP（中尊顶在 y≈5.35，两边的顶在 4.78，碰不到天花和梁下的斗拱）
    R.d = np.maximum(R.d, W - W_TOP)
    R.h = np.where((R.zone == 0) & (R.d < 0) & (R.h == 0), 0.01, R.h)      # 火焰底边（实的那一道）
    R.gold = np.where((R.zone == 0) & (R.d < 0) & (R.gold == 0), 0.6, R.gold)
    # 高度图抹一下（约 4 毫米）：台阶边、连珠抽网格以后是真的圆，不是一圈锯齿
    R.h = _blur2(R.h, 0.0042 / step)
    _RASTER[step] = R
    return R


def mandorla_node(s, step=0.003):
    """背光板（莲座坐标里，已经倾好、放好）：距离场"""
    R = mandorla_raster(step)
    ex, ew, en = plate_axes()
    O = PLATE_O * s
    nx, nw = len(R.xs), len(R.ws)

    def samp(A, xl, wl):
        fx = np.clip((xl - MX0) / step, 0, nx - 1.001)
        fw = np.clip((wl - MW0) / step, 0, nw - 1.001)
        j0, i0 = fx.astype(np.int64), fw.astype(np.int64)
        tx, tw = (fx - j0).astype(np.float32), (fw - i0).astype(np.float32)
        a, b = A[i0, j0], A[i0, j0 + 1]
        c, d = A[i0 + 1, j0], A[i0 + 1, j0 + 1]
        return (a * (1 - tx) + b * tx) * (1 - tw) + (c * (1 - tx) + d * tx) * tw

    def fn(X, Y, Z):
        X, Y, Z = np.broadcast_arrays(X, Y, Z)
        dx, dy, dz = X - O[0], Y - O[1], Z - O[2]
        xl = (dx * ex[0] + dy * ex[1] + dz * ex[2]) / s
        wl = (dx * ew[0] + dy * ew[1] + dz * ew[2]) / s
        nl = (dx * en[0] + dy * en[1] + dz * en[2]) / s
        d2 = samp(R.d, xl, wl)
        hh = samp(R.h, xl, wl)
        ham = 0.0008 * np.sin(xl * 23.0) * np.sin(wl * 19.0)
        front = nl - (PLATE_T / 2 + hh)
        back = -nl - (PLATE_T / 2 + ham)
        d = np.maximum(d2, np.maximum(front, back))
        # 下沿：莲座底面以上 CUT_Z
        d = np.maximum(d, CUT_Z - Z / s)
        return (d * s).astype(np.float32)
    corners = [O + (ex * x + ew * w) * s for x in (MX0, MX1) for w in (MW0, MW1)]
    lo = np.min(corners, axis=0) - 0.1 * s
    hi = np.max(corners, axis=0) + 0.1 * s
    return sdf.Func(fn, lo, hi)


def mandorla_uv(Vv, s):
    """贴图坐标：板上的平面坐标 (x, w) → (0..1)"""
    ex, ew, en = plate_axes()
    D = Vv / s - PLATE_O
    xl = D @ ex
    wl = D @ ew
    return np.stack([(xl - MX0) / (MX1 - MX0), (wl - MW0) / (MW1 - MW0)], axis=1)


MANDORLA_UV = (MX0, MW0, MX1 - MX0, MW1 - MW0)   # 贴图对应的板上平面范围（x0, w0, 宽, 高），中尊的大小


def mandorla(name, s):
    """背光：一块往前倾的板（浮雕 + 镂空火焰），纹样另有一张手绘贴图（paint_mandorla）；背后两根金撑子插在须弥座上。
    原点和佛像一样在莲座底面中心（放的时候和对应的佛像放在同一点），-y 朝前。"""
    import kit
    a = kit.Asset(name)
    node = mandorla_node(s)
    ex, ew, en = plate_axes()
    vox = 0.0042 * s
    lo, hi = np.asarray(node.lo), np.asarray(node.hi)
    # 第四轮：火舌两层、更密（54000 个三角形抽下来火舌的卷都糊了）
    Vv, T = sdf_piece(node, vox, int(90000), name, lo=lo, hi=hi)
    bag = Bag()
    bag.add('paint_mandorla', Vv, T, np.ones(3), UV=mandorla_uv(Vv, s))
    # 撑子：从须弥座顶面（板后面）起，两根金柱接到板的下沿后面
    for sx in (-1, 1):
        top_ = PLATE_O * s + (ex * sx * 0.3 + ew * (MW0 + 0.15)) * s - en * PLATE_T * 0.6 * s
        bot = V(sx * 0.3 * s, top_[1] + 0.02 * s, 0.455 * s)
        Vt, Tt = tube_mesh([bot, (bot + top_) / 2, top_], 0.022 * s, segs=10)
        bag.add('gold', Vt, Tt, GOLD_DARK)
    bag.bake_ao(dist=0.08 * s, samples=32, strength=0.6)
    bag.to_asset(a)
    print(f'[yjm] {name}: {bag.tris()} 个三角形')
    tris = a.finish(ao=False, view=(0, 8, 1.0))
    check_export(name)
    return tris


def mandorla_center(name):
    return mandorla(name, 1.0)


def mandorla_side(name):
    return mandorla(name, 0.85)


ASSETS.update({'mandorla_center': mandorla_center, 'mandorla_side': mandorla_side})
