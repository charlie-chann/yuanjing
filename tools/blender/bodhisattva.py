"""观音菩萨立像（2026-11-19）：立在仰覆莲台上，高髻宝冠、冠中化佛，右手举在胸前拈杨柳枝，左手仰掌托净瓶，
披云肩、系长裙和腰裙，天衣（飘带）在腿前兜两道弧、从两肘垂到莲台，胸前项圈和长璎珞。身后另有一面舟形背光（mandorla_guanyin）。

工艺和三世佛（statues.py）完全一样：形体是距离场（sdf.py）拼的，头、手、脚直接用 statues.py 里佛的头、手、脚（按菩萨的比例缩小），
openvdb 抽成网格、Blender 分区减面、Cycles 烤暗部乘进顶点色。宝冠是一圈解析写出来的薄壳（冠叶的轮廓、连珠、云纹都是高低图），
冠正中的化佛（小坐佛）是几个小椭球并出来的；璎珞是贴在身上的一串串珠子（真的小球）。

部件（和三世佛相同，Unity 里不用加材质）：gold（鎏金：衣裙、天衣、宝冠、璎珞、净瓶、杨柳、莲台）、
paint_buddha_face（泥金：脸、颈、胸口、小臂、手、脚，贴开脸那张图）、toon（石青的头发）、paint_robe_band（云肩、抹胸的衣缘纹带）。
坐标：原点在莲台底面中心，-y 是正面，单位米。像高（莲台底到髻顶）约 2.78 米，莲台面高 TOP·s。
"""
import math
import os

import numpy as np

import sdf
from sdf import V, euler
import statues as st
from statues import (Frame, U, S, ss, spow, surf, to_local, Bag, GOLD, GOLD_LIT, GOLD_DARK, CINNABAR, AZURE, MALACHITE, HAIR, lin,
                     tube_mesh, sphere_mesh, lathe_mesh, ring_lathe, quads_to_tris, petal_ring, bead_ring, sdf_piece, gilt_noise)

HS = 0.8             # 头的比例（佛头的局部单位 → 身子坐标）
HAND_S = 0.7         # 手
FOOT_S = 0.86        # 脚
KL = 0.5             # 莲台：三世佛莲座上半截缩到这么大
TOP = 0.1 + 0.523 * KL   # 莲台面的高度（0.3615）
R_, L_ = -1, 1       # 菩萨自己的右手边是 -x（观者的左边）

# 骨架点（身子坐标：原点在莲台面中心，-y 朝前，z 朝上；脚底 z=0，髻顶约 2.36）
NECK = V(0, 0.03, 1.665)
SH = {R_: V(-0.192, 0.03, 1.6), L_: V(0.192, 0.03, 1.6)}
ELB = {R_: V(-0.262, 0.06, 1.265), L_: V(0.258, 0.065, 1.245)}
WR = {R_: V(-0.225, -0.19, 1.4), L_: V(0.17, -0.2, 1.17)}
HIP = {R_: V(-0.085, 0.03, 1.0), L_: V(0.085, 0.03, 1.0)}
KNEE = {R_: V(-0.09, 0.0, 0.55), L_: V(0.1, -0.045, 0.56)}        # 左膝微微往前（重心在右腿，站得松）
ANK = {R_: V(-0.085, 0.03, 0.08), L_: V(0.108, 0.0, 0.08)}
# 手：右手举在胸前拈杨柳枝（说法印的手势，拇指、食指相捻），左手仰掌托净瓶
HANDS = {R_: dict(d=(0.1, -0.22, 1), palm=(0.4, -0.9, 0.05), pose='TEACH'),
         L_: dict(d=(-0.42, -1, 0.04), palm=(0, 0.05, 1), pose='RELAX')}


def head_frames(B, pitch=11.0):
    """头的坐标系（低头 pitch 度，绕颈根转）和不低头时的坐标（颈根按它放）"""
    o0 = B.p(0, 0.035, 1.915)
    R0 = B.r(euler(math.radians(4), 0, 0))
    piv = o0 + R0 @ (st.HEAD_PIVOT * HS * B.s)
    R = B.r(euler(math.radians(pitch), 0, 0))
    o = piv - R @ (st.HEAD_PIVOT * HS * B.s)
    return Frame(o, R, B.s * HS), Frame(o0, R0, B.s * HS)


def torso(B):
    """衣服底下的身子：肩比佛窄、腰细、胯略宽"""
    parts = [B.ell((0, 0.03, 1.46), (0.168, 0.118, 0.17)),        # 胸廓
             B.ell((0, 0.015, 1.27), (0.132, 0.105, 0.15)),       # 腰腹
             B.ell((-0.006, 0.03, 1.08), (0.178, 0.132, 0.15))]   # 胯
    for sx in (-1, 1):
        parts.append(B.ell((sx * 0.07, -0.062, 1.49), (0.075, 0.03, 0.06)))          # 胸口只微微鼓一点
        parts.append(B.sph(SH[sx], 0.06))
        parts.append(B.cone(NECK + V(sx * 0.04, 0.01, -0.02), SH[sx] + V(0, 0, 0.008), 0.048, 0.052))
    return U(parts, 0.07, B)


def _loc(B, X, Y, Z):
    """身子坐标（B 不带旋转）里的局部坐标：保持 (n,1,1)、(1,m,1)、(1,1,p) 的形状不摊开，按方位角算的东西只用算一层"""
    return (X - np.float32(B.o[0])) / np.float32(B.s), (Y - np.float32(B.o[1])) / np.float32(B.s), (Z - np.float32(B.o[2])) / np.float32(B.s)


# ====================================================================== 头：发、高髻
def hair_relief(H):
    """发际以上：头发比头皮厚出一层（发际是一道小台阶），一绺绺往上梳到髻里；髻上的发丝斜着盘上去"""
    def fn(X, Y, Z):
        x, y, z = to_local(H, X, Y, Z)
        phi = np.arctan2(x, -(y - 0.02))
        m = ss(0.0, 0.006, z - st.hairline_z(np.arctan2(x, -y)))
        bun = ss(0.2, 0.235, z)
        g = np.sin(phi * 40 + 2.5 * np.sin(z * 38)) * (1 - bun) + np.sin(phi * 13 + z * 120) * bun
        return (-(0.0055 * m + 0.0017 * m * g) * H.s).astype(np.float32)
    return fn


def head_node(B, core, info):
    H, H0 = head_frames(B)
    hd = st.head(H, info, H0)
    # 高髻：头顶束起来的一个高发髻，上面再盘一个小髻；髻根一道束发的箍
    bun = U([H.ell((0, 0.03, 0.29), (0.062, 0.068, 0.092)), H.ell((0, 0.034, 0.385), (0.046, 0.05, 0.045))], 0.022, H)
    hd = U([hd, bun], 0.014, H)
    hd = sdf.Displace(hd, hair_relief(H), H.k(0.01), box=st.fbox(H, (-0.17, -0.19, -0.1), (0.17, 0.2, 0.45), 0.02))
    # 胸口露出来的那一块和颈做成一整块（同三世佛）
    chest = sdf.Inter(core, B.box((0, -0.08, 1.53), (0.16, 0.13, 0.17)))
    hd = sdf.Union([hd, chest], B.k(0.05))
    info['H'] = H
    return hd, H


# ====================================================================== 衣裙
def skirt_base(B):
    """长裙的大形：两条腿各一个上窄下宽的筒，裙摆往外撒开；左膝微微顶出来"""
    parts = [B.cone((-0.05, 0.03, 1.25), (-0.1, 0.03, 0.0), 0.098, 0.175),
             B.cone((0.05, 0.03, 1.25), (0.112, 0.015, 0.0), 0.098, 0.175),
             B.ell((-0.006, 0.035, 1.06), (0.19, 0.142, 0.2))]
    for sx in (-1, 1):
        parts.append(sdf.Offset(sdf.chain([B.p(HIP[sx]), B.p(KNEE[sx]), B.p(ANK[sx])], [B.k(0.1), B.k(0.076), B.k(0.064)]), B.k(0.028)))
    return U(parts, 0.085, B)


def flutes(B):
    """裙摆的竖褶：越往下越深，两侧和背后密、正面中间浅（那里是兜着的 U 形褶）"""
    def fn(X, Y, Z):
        x, y, z = _loc(B, X, Y, Z)
        phi = np.arctan2(x, -(y - 0.02))
        low = 1 - ss(0.12, 0.8, z)
        side = 0.42 + 0.58 * ss(0.25, 0.85, np.abs(np.sin(phi * 0.5)) * 1.3)
        g = np.sin(phi * 11 + 0.9 * np.sin(phi * 3 + 0.7))
        g = np.sign(g) * np.abs(g) ** 0.7
        return ((-(0.019 * B.s) * side * g) * low).astype(np.float32)
    return fn


def zfunc(B, zf, above=True):
    """一个按方位角起伏的水平切面：above=True 留下 z > zf(phi) 的部分"""
    def fn(X, Y, Z):
        x, y, z = _loc(B, X, Y, Z)
        phi = np.arctan2(x, -(y - 0.02))
        d = (zf(phi) - z) if above else (z - zf(phi))
        return (d * np.float32(B.s)).astype(np.float32)
    return sdf.Func(fn)


def wrap_path(B, node, ctrl, lift=0.0, n=6, axis_y=0.03, dz=0.0):
    """身子坐标里画的一道线 → 贴到 node 表面上（朝身子的中轴贴过去），返回 (点, 法线)。贴不上的点留在原处"""
    Q = np.array([B.p(q) for q in sdf.catmull([V(q) for q in ctrl], n)])
    ax = np.array([B.p(0, axis_y, 0)] * len(Q))
    ax[:, 2] = Q[:, 2] + dz * B.s
    D = ax - Q
    D /= np.maximum(np.linalg.norm(D, axis=1, keepdims=True), 1e-9)
    P, N, ok = surf(node, Q - D * B.k(0.25), D, tmax=B.k(0.9))
    P = np.where(ok[:, None], P + N * B.k(lift), Q)
    N = np.where(ok[:, None], N, -D)
    for _ in range(3):
        P[1:-1] = (P[:-2] + 2 * P[1:-1] + P[2:]) / 4
        N[1:-1] = (N[:-2] + 2 * N[1:-1] + N[2:]) / 4
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    return P, N


def drape_path(B, node, ctrl, center, lift, zmax, n=6):
    """搭在肩上、胸前的一条（垂发、冠缯）：身子坐标里画的线朝 center 那一点贴到 node 表面上（高过 zmax 的点悬空不贴）"""
    Q = np.array([B.p(q) for q in sdf.catmull([V(q) for q in ctrl], n)])
    c = B.p(center)
    D = c[None, :] - Q
    dist = np.linalg.norm(D, axis=1, keepdims=True)
    D = D / np.maximum(dist, 1e-9)
    st0 = c[None, :] - D * B.k(0.75)
    P, N, ok = surf(node, st0, D, tmax=B.k(0.75))
    ok &= Q[:, 2] < B.p(0, 0, zmax)[2]
    out = np.where(ok[:, None], P + N * B.k(lift), Q)
    Nn = np.where(ok[:, None], N, -D)
    for _ in range(3):
        out[1:-1] = (out[:-2] + 2 * out[1:-1] + out[2:]) / 4
        Nn[1:-1] = (Nn[:-2] + 2 * Nn[1:-1] + Nn[2:]) / 4
    Nn /= np.linalg.norm(Nn, axis=1, keepdims=True)
    return out, Nn


def free_ribbon(B, ctrl, twist, n=6):
    """悬空垂着的一段飘带：ctrl 是身子坐标里的点，twist 是每个控制点上带面法线绕竖轴转的角（度，0 = 朝正前 -y）"""
    Q = np.array([B.p(q) for q in sdf.catmull([V(q) for q in ctrl], n)])
    tw = np.interp(np.linspace(0, len(ctrl) - 1, len(Q)), np.arange(len(ctrl)), twist)
    N = np.array([B.d(math.sin(math.radians(a)), -math.cos(math.radians(a)), 0.0) for a in tw])
    return Q, N


def garments(B, core, info):
    """衣裙、云肩、天衣：一整块鎏金。返回距离场，顺手记下衣缘纹带、璎珞要贴的面"""
    k = B.k
    # ── 抹胸（僧祇支）：从左肩斜到右腋下的一道，上沿斜 ──
    wrap = sdf.Inter(sdf.Offset(core, k(0.009)), sdf.Plane(B.p(0, 0, 1.47), B.d(-0.2, 0.0, 1)))
    wrap = sdf.Inter(wrap, sdf.Plane(B.p(0, 0, 1.1), B.d(0, 0, -1)))
    # ── 云肩：盖住两肩、上臂和后背，前面敞开，下沿是一圈如意云头的弧 ──
    cc = [B.ell((0, 0.055, 1.49), (0.17, 0.1, 0.19))]
    for sx in (-1, 1):
        cc += [B.sph(SH[sx], 0.064), B.cone(SH[sx], ELB[sx], 0.058, 0.052),
               B.cone(NECK + V(sx * 0.04, 0.012, -0.02), SH[sx] + V(0, 0, 0.008), 0.05, 0.055)]
    cape = sdf.Offset(U(cc, 0.05, B), k(0.014))
    # 云肩的褶：每条上臂三道从肩头前面斜着绕到肘后的长褶，背上两道
    cf = []
    for sx in (-1, 1):
        sh, el = SH[sx], ELB[sx]

        def to_arm(q, sh=sh, el=el):
            t = np.clip((q - sh).dot(el - sh) / (el - sh).dot(el - sh), 0, 1)
            d = sh + (el - sh) * t - q
            return d / max(np.linalg.norm(d), 1e-9)
        for j in range(3):
            pts = []
            for t in (0.0, 0.5, 1.0):
                tt = 0.08 + 0.2 * j + (0.62 - 0.1 * j) * t
                ang = 0.15 + 1.25 * t
                pts.append(sh + (el - sh) * tt + (V(0, -1, 0) * math.cos(ang) + V(sx, 0, 0) * math.sin(ang)) * 0.16)
            for Q, N in st.fold_curve(B, cape, pts, to_arm, 5, 0.08):
                cf.append(dict(P=Q, N=N, amp=k(0.007), w1=k(0.007), w2=k(0.022), sign=float(sx), taper=0.25, depth=k(0.04)))
        for Q, N in st.fold_curve(B, cape, [(sx * 0.06, 0.4, 1.62), (sx * 0.085, 0.4, 1.48), (sx * 0.12, 0.4, 1.33)], (0, -1, 0), 5, 0.08):
            cf.append(dict(P=Q, N=N, amp=k(0.006), w1=k(0.007), w2=k(0.022), sign=float(sx), taper=0.25, depth=k(0.04)))
    cape = sdf.Folds(cape, cf, near=k(0.025))
    info['cape_folds'] = [f['P'] for f in cf]
    cape = sdf.Sub(cape, B.ell((0, -0.17, 1.53), (0.088, 0.17, 0.27)), k(0.008))          # 前面的敞口
    cape = sdf.Sub(cape, B.cone((0, 0.035, 1.6), (0, 0.035, 1.8), 0.084, 0.084), k(0.008))  # 领口
    cape = sdf.Inter(cape, zfunc(B, lambda p: 1.3 - 0.026 * (0.5 + 0.5 * np.cos(p * 8.0))))
    info['cape'] = cape
    info['wrap'] = wrap
    # ── 长裙 ──
    sk0 = skirt_base(B)
    sk = sdf.Displace(sk0, flutes(B), k(0.02), box=(B.p(-0.6, -0.5, -0.05), B.p(0.6, 0.5, 0.95)))
    folds = []

    def add(node, pts, dirs, amp, w1=0.008, w2=0.026, sign=1.0, taper=0.25, min_len=0.1):
        for Q, N in st.fold_curve(B, node, pts, dirs, 5, min_len):
            folds.append(dict(P=Q, N=N, amp=k(amp), w1=k(w1), w2=k(w2), sign=sign, taper=taper, depth=k(0.05)))
    # 两腿之间兜着的一道道 U 形褶（从胯到小腿，一道比一道宽、垂得深）
    for i in range(7):
        z0 = 0.86 - 0.115 * i
        w = 0.07 + 0.011 * i
        sag = 0.085 + 0.014 * i
        pts = [(-w, -0.4, z0 + 0.03), (-w * 0.6, -0.4, z0 - sag * 0.7), (0.004, -0.4, z0 - sag), (w * 0.6, -0.4, z0 - sag * 0.7), (w, -0.4, z0 + 0.03)]
        add(sk0, pts, (0, 1, 0), 0.0105 - 0.0005 * i, sign=-1.0)
    # 两腿外侧顺着腿垂下来的长褶，左膝顶出来的地方往膝后斜的两道
    for sx in (-1, 1):
        for j, (x0, x1) in enumerate(((0.145, 0.2), (0.185, 0.245))):
            add(sk0, [(sx * x0, -0.4, 0.95), (sx * (x0 + x1) / 2, -0.4, 0.5), (sx * x1, -0.4, 0.1)], (-sx * 0.55, 1, 0), 0.009, sign=sx)
    for j in range(2):
        add(sk0, [(0.06, -0.4, 0.62 - 0.1 * j), (0.14, -0.4, 0.56 - 0.1 * j), (0.21, -0.4, 0.6 - 0.12 * j)], (-0.3, 1, 0), 0.007, sign=-1.0)
    # 背后几道直褶
    for x0 in (-0.13, -0.045, 0.05, 0.135):
        add(sk0, [(x0, 0.5, 0.95), (x0 * 1.15, 0.5, 0.5), (x0 * 1.35, 0.5, 0.1)], (0, -1, 0), 0.008, sign=1.0 if x0 > 0 else -1.0)
    sk = sdf.Folds(sk, folds, near=k(0.03))
    info['fold_paths'] = [f['P'] for f in folds]
    # 裙摆：下沿一圈起伏，正面掀起一点露出两只脚
    sk = sdf.Inter(sk, zfunc(B, lambda p: 0.022 + 0.01 * np.sin(p * 11 + 0.9 * np.sin(p * 3 + 0.7))))
    sk = sdf.Sub(sk, B.ell((0.01, -0.27, -0.01), (0.22, 0.16, 0.085)), k(0.02))
    sk = sdf.Inter(sk, sdf.Plane(B.p(0, 0, 1.23), B.d(0, 0, 1)))
    # ── 腰裙：长裙外面再围的一条短裙，下沿在大腿中间，是一排尖角（一片片叠着的褶） ──
    def over_hem(p):
        t = (p * 9 / (2 * np.pi)) % 1.0
        return 0.845 + 0.05 * np.abs(t - 0.5) * 2 - 0.035 * np.cos(p)
    over = sdf.Inter(sdf.Offset(sk0, k(0.013)), zfunc(B, over_hem))
    over = sdf.Inter(over, sdf.Plane(B.p(0, 0, 1.235), B.d(0, 0, 1)))
    # ── 腰带：一道宽带，上下各一道棱 ──
    belt = sdf.Inter(sdf.Offset(sk0, k(0.021)), B.box((0, 0, 1.205), (0.5, 0.5, 0.027), None, 0.008))
    belt = U([belt, sdf.Inter(sdf.Offset(sk0, k(0.026)), B.box((0, 0, 1.228), (0.5, 0.5, 0.006), None, 0.003)),
              sdf.Inter(sdf.Offset(sk0, k(0.026)), B.box((0, 0, 1.182), (0.5, 0.5, 0.006), None, 0.003))], 0.002, B)
    lower = sdf.Union([sk, over, belt], k(0.003))
    info['lower'] = lower
    # ── 腰带正中的结：一个花结，两个环，两条长带垂到膝上 ──
    q, n_, ok = surf(lower, [B.p(0, -0.5, 1.2)], B.d(0, 1, 0), tmax=k(0.8))
    kc = q[0] + B.d(0, -1, 0) * k(0.012)
    kc_l = V(to_local(B, *kc))
    knot = [B.ell(kc_l, (0.024, 0.017, 0.021))]
    for sx in (-1, 1):
        # 花结的两个环：贴着腰带（先在身前画好，再贴到腰上）
        loop = [(sx * 0.008, -0.5, kc_l[2]), (sx * 0.036, -0.5, kc_l[2] + 0.024), (sx * 0.064, -0.5, kc_l[2] + 0.008),
                (sx * 0.044, -0.5, kc_l[2] - 0.02), (sx * 0.01, -0.5, kc_l[2] - 0.004)]
        P, N = wrap_path(B, lower, loop, lift=0.007, n=6)
        knot.append(sdf.chain(list(P), B.k(0.0095), B.k(0.002)))
        P, N = wrap_path(B, lower, [kc_l + V(sx * 0.012, -0.2, -0.02), V(sx * 0.03, -0.5, 1.05), V(sx * 0.045, -0.5, 0.88),
                                    V(sx * 0.04, -0.5, 0.74), V(sx * 0.065, -0.5, 0.6 + 0.04 * sx)], lift=0.004)
        knot.append(st.ribbon(P, N, k(0.036), k(0.011), taper=list(np.linspace(0.75, 1.25, len(P)))))
    knot = sdf.Union(knot, k(0.004))
    # ── 天衣：腿前两道兜着的弧（一高一低），两肘各垂一条到莲台 ──
    scarf = []
    for (zs, zm, lft) in ((1.13, 0.8, 0.004), (1.1, 0.5, 0.004)):
        ctrl = [(-0.3, 0.07, zs + 0.06), (-0.3, -0.02, zs - 0.06), (-0.22, -0.4, (zs + zm) / 2 - 0.02), (-0.09, -0.5, zm + 0.03), (0.01, -0.5, zm),
                (0.11, -0.5, zm + 0.035), (0.23, -0.4, (zs + zm) / 2), (0.3, -0.02, zs - 0.06), (0.3, 0.07, zs + 0.06)]
        P, N = wrap_path(B, lower, ctrl, lift=lft, n=8)
        scarf.append(st.ribbon(P, N, k(0.056), k(0.012)))
        info.setdefault('scarf_paths', []).append(P)
    ends = {
        R_: ([(-0.29, 0.065, 1.33), (-0.33, 0.07, 1.14), (-0.3, 0.05, 0.9), (-0.345, 0.02, 0.66), (-0.31, -0.01, 0.42), (-0.365, -0.035, 0.22),
              (-0.35, -0.06, 0.085)], [-80, -72, -42, -78, -40, -75, -50]),
        L_: ([(0.288, 0.07, 1.32), (0.322, 0.075, 1.12), (0.296, 0.055, 0.88), (0.34, 0.03, 0.64), (0.305, 0.0, 0.41), (0.36, -0.03, 0.21),
              (0.345, -0.055, 0.085)], [80, 72, 44, 76, 40, 72, 48]),
    }
    for sx, (ctrl, tw) in ends.items():
        P, N = free_ribbon(B, ctrl, tw, n=7)
        m = len(P)
        tp = np.interp(np.linspace(0, 1, m), [0, 0.15, 0.8, 0.93, 1.0], [0.8, 1.0, 1.1, 0.9, 0.35])
        scarf.append(st.ribbon(P, N, k(0.066), k(0.013), taper=list(tp)))
    scarf = sdf.Union(scarf, k(0.004))
    body = sdf.Union([wrap, cape, lower, knot, scarf], k(0.004))
    return body


# ====================================================================== 手、脚
def limbs(B, info):
    """两只手（连小臂、肘）和两只脚（连脚踝）：几块分开抽网格"""
    out = []
    frames = {}
    for sx, h in HANDS.items():
        F = st.hand_frame(B, WR[sx], h['d'], h['palm'], right=(sx == R_), s=HAND_S)
        frames[sx] = F
        wr, el, sh = WR[sx], ELB[sx], SH[sx]
        arm = U([B.cone(wr + (el - wr) * 0.07, el, 0.026, 0.044), B.cone(el, el + (sh - el) * 0.3, 0.045, 0.05)], 0.02, B)
        tips = {}
        out.append(U([st.hand(F, dict(getattr(st, h['pose'])), tips), arm], B.k(0.012)))
        info.setdefault('tips', {})[sx] = tips
    info['hand_frames'] = frames
    feet = []
    for sx in (-1, 1):
        heel = V(ANK[sx][0], -0.035 if sx < 0 else -0.06, 0.0465 * FOOT_S)
        F = st.hand_frame(B, heel, (sx * 0.2, -1, 0), (0, 0, 1), right=(sx == L_), s=FOOT_S)
        feet.append(U([st.foot(F), B.cone(heel + V(0, 0.01, 0.03), heel + V(0, 0.03, 0.2), 0.04, 0.05)], B.k(0.012)))
    return out, feet


# ====================================================================== 宝冠
CR_A, CR_B, CR_Y, CR_FL = 0.15, 0.169, 0.02, 0.3          # 冠圈：椭圆的两个半轴、中心的 y、往上撒开的斜率（头的局部单位）
CR_T = 0.0075                                             # 冠壳的厚


def crown_top(phi):
    """冠叶的上沿（头的局部 z）：正面一片高的桃形大叶，两侧各两片小叶，后面是一圈矮箍"""
    a = np.abs(phi)
    def leaf(c, w, h, p=0.62):
        return h * spow(np.cos(np.clip((a - c) / w, -1, 1) * np.pi / 2), p)
    return 0.118 + np.maximum(leaf(0.0, 0.5, 0.215), np.maximum(leaf(0.98, 0.34, 0.125), leaf(1.72, 0.3, 0.08)))


def crown_bot(phi):
    return np.maximum(st.hairline_z(phi) - 0.02, 0.028)


def crown_pt(phi, z, out=0.0):
    """冠外面上的一点（头的局部坐标）"""
    fl = 1 + CR_FL * (z - 0.06)
    return V((CR_A * fl + CR_T + out) * math.sin(phi), CR_Y - (CR_B * fl + CR_T + out) * math.cos(phi), z)


def crown_node(H):
    """宝冠：一圈薄壳（解析的），外面刻冠叶的厚边、底箍的两道弦纹和连珠、叶面上的云纹和嵌宝石的座；正面大叶中间一个龛，龛里坐着化佛"""
    def fn(X, Y, Z):
        x, y, z = to_local(H, X, Y, Z)
        x, y, z = np.broadcast_arrays(x, y, z)
        yc = y - CR_Y
        phi = np.arctan2(x, -yc)
        fl = 1 + CR_FL * (z - 0.06)
        rho = np.sqrt((x / (CR_A * fl)) ** 2 + (yc / (CR_B * fl)) ** 2)
        ds = (rho - 1) * (CR_A + CR_B) * 0.5 * fl
        top, bot = crown_top(phi), crown_bot(phi)
        e = top - z
        Rm = (CR_A + CR_B) * 0.5
        # 浮雕（往外为正）
        h = 0.0042 * np.exp(-((e - 0.007) / 0.0045) ** 2)                                  # 冠叶的厚边
        band = z - bot
        h = h + 0.003 * (np.exp(-((band - 0.004) / 0.003) ** 2) + np.exp(-((band - 0.03) / 0.003) ** 2))   # 底箍上下两道弦纹
        u = phi * Rm / 0.0125
        bead = np.clip(1 - ((u - np.round(u)) * 0.0125) ** 2 / 0.0048 ** 2 - (band - 0.017) ** 2 / 0.0048 ** 2, 0, 1)
        h = h + 0.0045 * np.sqrt(bead)                                                     # 连珠
        field = ss(0.036, 0.042, band) * ss(0.012, 0.018, e)
        # 叶面上的光芒纹：每片冠叶从自己正中（龛、宝石）往外放射的一道道细棱
        ap = np.abs(phi)
        cz = np.where(ap < 0.62, 0.2, np.where(ap < 1.38, 0.185, 0.15))
        cp = np.where(ap < 0.62, 0.0, np.where(ap < 1.38, 0.98, 1.72)) * np.sign(phi)
        rays = np.sin(np.arctan2(z - cz, (phi - cp) * Rm) * 12)
        h = h + 0.0021 * field * ss(-0.1, 0.7, rays)
        # 正面大叶上的龛：一个尖拱形的凹龛，龛边一道凸线
        nz, nx = z - 0.2, phi * Rm
        arch = np.sqrt((nx / 0.047) ** 2 + (np.maximum(nz, 0) / 0.085) ** 2 + (np.minimum(nz, 0) / 0.062) ** 2)
        h = h * ss(0.92, 1.05, arch) + 0.004 * np.exp(-((arch - 1.0) / 0.07) ** 2) - 0.0018 * (1 - ss(0.8, 0.95, arch))
        # 嵌宝石的座：两侧小叶正中、底箍正面两边各一个
        for pc, zc in ((0.98, 0.185), (-0.98, 0.185), (1.72, 0.15), (-1.72, 0.15)):
            q = np.sqrt(((phi - pc) * Rm) ** 2 + (z - zc) ** 2)
            h = h + 0.004 * np.exp(-((q - 0.017) / 0.004) ** 2) * 1.0
        d = np.maximum(np.maximum(ds - CR_T - h, -ds - 0.0005), np.maximum(-e, bot - z))
        return (d * H.s).astype(np.float32)
    lo, hi = st.fbox(H, (-0.24, -0.25, 0.0), (0.24, 0.24, 0.36), 0.01)
    shell = sdf.Func(fn, lo, hi)
    # 化佛：结跏趺坐的小佛（阿弥陀），身后一圈头光、身下一座小莲台
    c = crown_pt(0.0, 0.196, 0.0005)
    F = H.child(c, None, 1.0)
    fo = [F.sph((0, -0.008, 0.036), 0.0125), F.sph((0, -0.007, 0.05), 0.006),
          F.ell((0, -0.006, 0.01), (0.0175, 0.0115, 0.02)),
          F.ell((0, -0.011, -0.014), (0.03, 0.0145, 0.0095)),
          F.ell((0, -0.017, -0.008), (0.011, 0.006, 0.005)),
          F.ell((0, -0.008, -0.03), (0.034, 0.015, 0.008)),
          F.ell((0, -0.008, -0.042), (0.027, 0.013, 0.007))]
    for sx in (-1, 1):
        fo.append(F.cone((sx * 0.016, -0.007, 0.02), (sx * 0.02, -0.012, -0.003), 0.006, 0.0055))
        fo.append(F.cone((sx * 0.02, -0.012, -0.003), (sx * 0.006, -0.018, -0.008), 0.005, 0.0045))
    fo = U(fo, 0.003, F)
    halo = U([F.torus((0, 0.002, 0.036), 0.023, 0.0028, euler(math.pi / 2, 0, 0)),
              F.torus((0, 0.003, 0.0), 0.034, 0.0026, euler(math.pi / 2, 0, 0))], 0.001, F)
    return sdf.Union([shell, fo, halo], H.k(0.002))


# ====================================================================== 小网格：带子、珠串
def band_mesh(P, N, w, t, taper=None):
    """一条有厚度的扁带子（真的网格，不走距离场）：截面是个扁六边形。P 中线，N 带面的法线，w 宽（可以每点一个），t 厚"""
    P, N = np.asarray(P, np.float64), np.asarray(N, np.float64)
    n = len(P)
    tang = np.gradient(P, axis=0)
    tang /= np.linalg.norm(tang, axis=1, keepdims=True)
    N = N - tang * np.einsum('ij,ij->i', N, tang)[:, None]
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    side = np.cross(N, tang)
    ww = np.full(n, w) if taper is None else w * np.asarray(taper)
    prof = [(-0.5, 0.0), (-0.3, 0.5), (0.3, 0.5), (0.5, 0.0), (0.3, -0.5), (-0.3, -0.5)]
    VV = []
    for i in range(n):
        for a, b in prof:
            VV.append(P[i] + side[i] * a * ww[i] + N[i] * b * t)
    T = []
    for i in range(n - 1):
        for j in range(6):
            a, b = i * 6 + j, i * 6 + (j + 1) % 6
            T += [(a, b, b + 6), (a, b + 6, a + 6)]
    VV.append(P[0])
    VV.append(P[-1])
    c0, c1 = len(VV) - 2, len(VV) - 1
    last = (n - 1) * 6
    T += [(c0, (j + 1) % 6, j) for j in range(6)] + [(c1, last + j, last + (j + 1) % 6) for j in range(6)]
    VV, T = np.array(VV), np.array(T)
    # 朝向：第一圈的 (0,1) 边和带子的前进方向定出来的法线要朝外
    a, b, c = VV[T[0][0]], VV[T[0][1]], VV[T[0][2]]
    ctr = P[0] + tang[0] * 1e-4
    if np.dot(np.cross(b - a, c - a), (a + b + c) / 3 - (P[0] + P[1]) / 2) < 0:
        T = T[:, ::-1]
    return VV, T


def resample(Q, step):
    return st.resample(Q, step)


def bead_string(bag, P, N, r, step, s, big_every=6, lift=0.6, col=GOLD_LIT):
    """沿一道线排一串珠子（半埋在表面上）：每隔几颗一颗大的彩珠（红、绿相间）"""
    Q = resample(P, step)
    idx = np.argmin(np.linalg.norm(Q[:, None, :] - np.asarray(P)[None, :, :], axis=2), axis=1)
    Vs, Ts = sphere_mesh(1.0, 6, 4)
    for i, q in enumerate(Q):
        big = big_every and i % big_every == big_every // 2
        rr = r * (1.45 if big else 1.0)
        c = (CINNABAR * 1.1 if (i // big_every) % 2 == 0 else MALACHITE * 1.15) if big else col
        bag.add('gold', Vs * rr + q + N[idx[i]] * rr * lift, Ts, c)


# ====================================================================== 莲台
def lotus_stand(s):
    """立像的莲台：圆的两层台座，上面一圈覆莲、一道连珠、三层仰莲（同三世佛莲座的上半截，缩小成立像用的）。台面高 TOP·s"""
    bag = Bag()
    G = 'gold'
    k = KL * s

    def zz(z):
        return (0.1 + (z - 0.462) * KL) * s

    def lathe_round(pr, col, n=64):
        Vv, Q = ring_lathe(pr, n=n, rot=0.0)
        bag.add(G, Vv, quads_to_tris(Q), col)
    # 台座：下面一层大、上面一层小，中间收一道腰，腰上一圈连珠
    q = KL / 0.56 * s
    lathe_round([(0.5 * q, 0.0), (0.5 * q, 0.03 * s), (0.488 * q, 0.04 * s), (0.47 * q, 0.045 * s)], GOLD_DARK * 1.05)
    lathe_round([(0.465 * q, 0.045 * s), (0.44 * q, 0.055 * s), (0.43 * q, 0.068 * s), (0.445 * q, 0.08 * s), (0.45 * q, 0.1 * s), (0.4 * q, 0.104 * s)], GOLD)
    bead_ring(bag, 44, 0.432 * q, 0.066 * s, 0.0105 * s, 1.0, GOLD_LIT, tilt=0)
    lathe_round([(0.7 * k, zz(0.462)), (0.7 * k, zz(0.5)), (0.66 * k, zz(0.56)), (0.6 * k, zz(0.62)), (0.56 * k, zz(0.66))], GOLD_DARK)
    petal_ring(bag, 16, 0.6 * k, zz(0.645), 0.17 * k, 0.08 * k, 0.015 * k, False, GOLD, lin((0.4, 0.55, 0.45)), phase=0.5,
               tilt0=6, tilt1=52, curl=-28, nu=7, rim=0.22, lobe=0.0, ridge=0.16, tipk=0.4, nvi=3, cup=0.05)
    petal_ring(bag, 20, 0.62 * k, zz(0.6), 0.21 * k, 0.11 * k, 0.017 * k, False, GOLD, lin((0.72, 0.3, 0.24)), tilt0=8,
               tilt1=62, curl=-40, nu=9, rim=0.22, lobe=0.17, ridge=0.12, tipk=0.45, cup=0.05)
    bead_ring(bag, 40, 0.578 * k, zz(0.665), 0.019 * k, 1.0, GOLD_LIT, tilt=10)
    lathe_round([(0.545 * k, zz(0.64)), (0.56 * k, zz(0.68)), (0.62 * k, zz(0.78)), (0.7 * k, zz(0.9)), (0.76 * k, zz(0.975)),
                 (0.74 * k, zz(0.985)), (0.0, zz(0.985))], GOLD)
    petal_ring(bag, 16, 0.56 * k, zz(0.68), 0.36 * k, 0.16 * k, 0.018 * k, True, GOLD, lin((0.8, 0.36, 0.3)), tilt0=22,
               tilt1=84, curl=48, nu=9, rim=0.2, lobe=0.16, ridge=0.12, tipk=0.45, cup=0.05)
    petal_ring(bag, 16, 0.6 * k, zz(0.76), 0.29 * k, 0.14 * k, 0.017 * k, True, GOLD, lin((0.32, 0.55, 0.48)), phase=0.5,
               tilt0=30, tilt1=86, curl=44, nu=9, rim=0.2, lobe=0.16, ridge=0.12, tipk=0.4, cup=0.05)
    petal_ring(bag, 16, 0.66 * k, zz(0.86), 0.2 * k, 0.11 * k, 0.015 * k, True, GOLD, GOLD_LIT, tilt0=40, tilt1=86,
               curl=40, nu=8, rim=0.22, lobe=0.0, ridge=0.14, tipk=0.3, nvi=3, cup=0.05)
    bead_ring(bag, 48, 0.722 * k, zz(0.988), 0.016 * k, 1.0, GOLD_LIT, tilt=35)
    return bag


# ====================================================================== 饰物：璎珞、臂钏、净瓶、杨柳、垂发、冠缯
def ornaments(bag, B, info, allnode, s):
    k = B.k
    H = info['H']
    # ── 项圈：胸口一道月牙形的宽圈（带子），下沿一排小珠，正中一个如意云头的坠子嵌一颗红宝石，底下三颗垂珠 ──
    ctrl = [(-0.098, -0.3, 1.635), (-0.088, -0.3, 1.58), (-0.05, -0.3, 1.535), (0.0, -0.3, 1.52), (0.05, -0.3, 1.535), (0.088, -0.3, 1.58), (0.098, -0.3, 1.635)]
    P, N = wrap_path(B, allnode, ctrl, lift=0.003, n=8, axis_y=0.06)
    side = np.cross(N, np.gradient(P, axis=0))
    side /= np.linalg.norm(side, axis=1, keepdims=True)
    side *= np.sign(side[:, 2:3] + 1e-9) * -1          # 朝下
    Vb, Tb = band_mesh(P, N, k(0.024), k(0.007))
    bag.add('gold', Vb, Tb, GOLD_LIT * 0.97)
    bead_string(bag, P + side * k(0.015), N, k(0.0058), k(0.0125), s, big_every=0)
    bead_string(bag, P - side * k(0.0135), N, k(0.0038), k(0.0085), s, big_every=0)
    m = len(P) // 2
    pc, pn = P[m] + side[m] * k(0.034), N[m]
    Vs, Ts = sphere_mesh(1.0, 14, 9)
    ex = np.cross(pn, side[m])
    Rm = np.stack([ex, side[m], pn], axis=1)
    for (ox, oy, rx, ry, rz_, col) in ((0, 0, 0.026, 0.021, 0.008, GOLD), (0, 0, 0.012, 0.012, 0.012, CINNABAR * 1.15), (-0.021, -0.008, 0.012, 0.011, 0.008, GOLD_LIT),
                                       (0.021, -0.008, 0.012, 0.011, 0.008, GOLD_LIT), (0, 0.03, 0.007, 0.009, 0.007, MALACHITE * 1.15),
                                       (-0.016, 0.024, 0.0055, 0.007, 0.0055, GOLD_LIT), (0.016, 0.024, 0.0055, 0.007, 0.0055, GOLD_LIT)):
        bag.add('gold', (Vs * np.array([rx, ry, rz_]) * B.s) @ Rm.T + pc + (ex * ox + side[m] * oy) * B.s + pn * k(0.009), Ts, col)
    # ── 长璎珞：从项圈两边垂下来，在腰带上面的一朵宝相花上会合，再分两股垂到膝上、往两边绕到腿后 ──
    med = None
    for sx in (-1, 1):
        ctrl = [(sx * 0.082, -0.4, 1.575), (sx * 0.095, -0.4, 1.45), (sx * 0.07, -0.4, 1.34), (sx * 0.028, -0.4, 1.28), (0.0, -0.4, 1.266)]
        P2, N2 = wrap_path(B, allnode, ctrl, lift=0.004, n=8, axis_y=0.06)
        bead_string(bag, P2, N2, k(0.0066), k(0.0152), s, big_every=7)
        med = (P2[-1], N2[-1])
        ctrl = [(sx * 0.012, -0.5, 1.235), (sx * 0.05, -0.5, 1.02), (sx * 0.1, -0.5, 0.8), (sx * 0.16, -0.45, 0.67), (sx * 0.23, -0.3, 0.63), (sx * 0.28, -0.12, 0.64)]
        P3, N3 = wrap_path(B, info['lower'], ctrl, lift=0.004, n=9)
        bead_string(bag, P3, N3, k(0.0066), k(0.0152), s, big_every=7)
        # 每股半路上一颗垂下来的坠子
        j = int(len(P3) * 0.42)
        for dz, rr, col in ((-0.022, 0.011, MALACHITE * 1.15), (-0.045, 0.0075, GOLD_LIT), (-0.062, 0.0055, GOLD_LIT)):
            bag.add('gold', Vs * k(rr) * np.array([1, 1, 1.25]) + P3[j] + N3[j] * k(0.008) + B.d(0, 0, 1) * k(dz), Ts, col)
    mc, mn = med
    mc = mc + B.d(0, 0, 1) * k(-0.004)
    ex = np.cross(mn, V(0, 0, 1))
    ex /= np.linalg.norm(ex)
    ez = np.cross(ex, mn)
    Rm = np.stack([ex, ez, mn], axis=1)
    bag.add('gold', (Vs * np.array([0.03, 0.03, 0.009]) * B.s) @ Rm.T + mc + mn * k(0.008), Ts, GOLD)
    bag.add('gold', (Vs * np.array([0.0135, 0.0135, 0.012]) * B.s) @ Rm.T + mc + mn * k(0.014), Ts, CINNABAR * 1.15)
    for i in range(8):
        a = 2 * math.pi * i / 8
        d = ex * math.cos(a) + ez * math.sin(a)
        Rp = np.stack([d, np.cross(mn, d), mn], axis=1)
        bag.add('gold', (Vs * np.array([0.012, 0.0085, 0.006]) * B.s) @ Rp.T + mc + d * k(0.024) + mn * k(0.011), Ts, GOLD_LIT)
    # ── 臂钏、手镯：小臂靠肘和手腕上各一道金圈，圈上一排小珠，正面一颗宝石 ──
    for sx in (-1, 1):
        wr, el = WR[sx], ELB[sx]
        ax = (el - wr) / np.linalg.norm(el - wr)
        e1 = np.cross(ax, V(0, 0, 1))
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(ax, e1)
        for t, rad, gem in ((0.17, 0.0325, MALACHITE * 1.15),):
            c = wr + (el - wr) * t
            for off, tr in ((-0.008, 0.0042), (0.008, 0.0042), (0.0, 0.0058)):
                ring = [B.p(c + ax * off + (e1 * math.cos(a) + e2 * math.sin(a)) * (rad + (0.002 if off == 0 else 0))) for a in np.linspace(0, 2 * math.pi, 29)]
                Vt, Tt = tube_mesh(ring, k(tr), segs=6, cap=False)
                bag.add('gold', Vt, Tt, GOLD_LIT if off else GOLD)
            g = c + V(0, -1, 0.2) / np.linalg.norm(V(0, -1, 0.2)) * (rad + 0.004)
            g = c + (g - c) - ax * np.dot(g - c, ax)
            bag.add('gold', Vs * k(0.0105) + B.p(g), Ts, gem)
    # ── 净瓶：托在左掌心。小圈足、圆鼓的瓶腹、细长的颈、颈上一道凸箍、撇口，口上一个带尖钮的盖 ──
    HF = info['hand_frames']
    F = HF[L_]
    base = F.p(0.092, 0.0, -0.024)
    ks = 1.0 * s
    prof = [(0.0, 0.0), (0.03, 0.0), (0.033, 0.004), (0.03, 0.012), (0.027, 0.02), (0.036, 0.03), (0.052, 0.05), (0.06, 0.075), (0.06, 0.095),
            (0.053, 0.118), (0.038, 0.14), (0.024, 0.156), (0.0175, 0.172), (0.0155, 0.2), (0.015, 0.225), (0.0195, 0.229), (0.021, 0.234),
            (0.0195, 0.239), (0.015, 0.243), (0.0145, 0.262), (0.0165, 0.276), (0.0235, 0.288), (0.0255, 0.292), (0.0235, 0.296), (0.015, 0.298),
            (0.011, 0.304), (0.0125, 0.312), (0.0095, 0.322), (0.004, 0.336), (0.0, 0.342)]
    Vl, Tl = lathe_mesh([(r * ks, z * ks) for r, z in prof], 40)
    z = Vl[:, 2] / ks
    th = np.arctan2(Vl[:, 1], Vl[:, 0])
    col = np.tile(GOLD, (len(Vl), 1))
    # 瓶腹上一圈仰莲瓣的浮雕、肩上一道弦纹
    aa = ((th / (2 * math.pi) * 10) % 1.0 - 0.5) * 2
    topz = 0.045 + 0.05 * spow(1 - np.abs(aa) ** 1.7, 0.6)
    inside = (z > 0.03) & (z < topz) & (z < 0.1)
    rim = np.exp(-((topz - z) / 0.004) ** 2) * (z > 0.03) * (z < 0.105)
    rr = np.hypot(Vl[:, 0], Vl[:, 1])
    Vl[:, :2] *= ((rr + (0.002 * inside + 0.0018 * rim) * ks) / np.maximum(rr, 1e-9))[:, None]
    col[rim > 0.3] = GOLD_LIT
    col[(np.abs(z - 0.234) < 0.006) | (np.abs(z - 0.292) < 0.005)] = GOLD_LIT
    bag.add('gold', Vl + base, Tl, col)
    info['vase_top'] = base + V(0, 0, 0.342 * ks)
    # ── 杨柳枝：右手拇指、食指之间拈着，枝梢往外上方挑出去再垂下来，两排细长的柳叶 ──
    tips = info['tips'][R_]
    c = (tips['thumb'] + tips['index']) / 2
    ctrl = [c + V(0.012, 0.012, -0.085) * s, c + V(0.004, 0.004, -0.03) * s, c, c + V(-0.02, -0.012, 0.09) * s, c + V(-0.07, -0.03, 0.2) * s,
            c + V(-0.15, -0.045, 0.275) * s, c + V(-0.24, -0.05, 0.285) * s, c + V(-0.31, -0.05, 0.235) * s, c + V(-0.35, -0.045, 0.15) * s]
    Pw = np.array(sdf.catmull(ctrl, 7))
    Vt, Tt = tube_mesh(Pw, list(np.linspace(0.0052, 0.0016, len(Pw)) * s), segs=6)
    bag.add('gold', Vt, Tt, GOLD_DARK * 1.1)
    tang = np.gradient(Pw, axis=0)
    tang /= np.linalg.norm(tang, axis=1, keepdims=True)
    rng = np.random.default_rng(5)
    for i in range(16, len(Pw) - 1, 3):
        for sg in (-1, 1):
            if (i // 3 + (sg > 0)) % 2 == 0 and i < len(Pw) - 8:
                continue
            sd = np.cross(tang[i], V(0, -1, 0.15))
            sd /= np.linalg.norm(sd)
            d0 = tang[i] * 0.55 + sd * sg * 0.6 + V(0, 0, -0.55) + V(0, -0.12, 0) * rng.uniform(0.3, 1.3)
            d0 /= np.linalg.norm(d0)
            Lf = (0.07 + 0.022 * rng.random()) * s * (0.7 + 0.3 * min(1.0, (len(Pw) - i) / 12))
            m_ = 9
            ts = np.linspace(0, 1, m_)
            droop = V(0, 0, -1)
            Pl = np.array([Pw[i] + d0 * Lf * t + droop * Lf * 0.28 * t * t for t in ts])
            nl = np.cross(d0, np.cross(V(0, -1, 0), d0))
            nl /= np.linalg.norm(nl)
            wl = np.sin(np.pi * np.clip(ts * 0.92 + 0.06, 0, 1)) ** 0.8
            Vf, Tf = band_mesh(Pl, np.tile(nl, (m_, 1)), 0.0125 * s, 0.0026 * s, taper=wl + 0.03)
            cf = np.tile(GOLD * 0.72 + MALACHITE * 0.3, (len(Vf), 1))
            cf[1::6] = GOLD * 0.85 + MALACHITE * 0.2
            cf[2::6] = GOLD * 0.85 + MALACHITE * 0.2
            bag.add('gold', Vf, Tf, cf)
    # ── 垂发：几绺头发从耳后垂到肩上，贴着云肩往外散开 ──
    for sx in (-1, 1):
        for j, (xo, yo, ln) in enumerate(((0.0, 0.0, 1.0), (-0.03, 0.04, 0.8), (0.03, -0.035, 0.72))):
            ctrl = [(sx * 0.1, 0.115 + yo * 0.3, 1.84), (sx * 0.108, 0.12 + yo * 0.4, 1.77), (sx * (0.135 + xo * 0.3), 0.11 + yo, 1.74),
                    (sx * (0.19 + xo), 0.06 + yo, 1.76), (sx * (0.2 + 0.08 * ln + xo), 0.0 + yo, 1.76),
                    (sx * (0.2 + 0.13 * ln + xo), -0.05 + yo, 1.72)]
            Q, Nn = drape_path(B, allnode, ctrl, (0, 0.03, 1.5), 0.006, 1.8)
            rr = np.interp(np.linspace(0, 1, len(Q)), [0, 0.3, 0.85, 1.0], [0.011, 0.0105, 0.0075, 0.003]) * s * (1.0 if j == 0 else 0.8)
            Vt, Tt = tube_mesh(Q, list(rr), segs=7)
            sh = 0.72 + 0.2 * np.sin(np.arange(len(Vt)) % 7 * 2 * math.pi / 7 * 2)
            bag.add('toon', Vt, Tt, np.clip(HAIR[None, :] * sh[:, None], 0, 1))
    # ── 冠缯：宝冠两侧垂下来的两条带子，从耳后落到肩后、顺着背垂下去，带梢是个尖 ──
    for sx in (-1, 1):
        p0 = H.p(crown_pt(sx * 1.95, 0.07, 0.0))
        ctrl = [to_local(B, *p0), (sx * 0.118, 0.1, 1.87), (sx * 0.128, 0.115, 1.8), (sx * 0.15, 0.2, 1.73), (sx * 0.165, 0.3, 1.62),
                (sx * 0.15, 0.3, 1.52), (sx * 0.17, 0.3, 1.43)]
        Q, Nn = drape_path(B, allnode, ctrl, (0, 0.03, 1.5), 0.004, 1.78)
        tp = np.interp(np.linspace(0, 1, len(Q)), [0, 0.2, 0.8, 1.0], [0.6, 1.0, 1.2, 0.12])
        Vt, Tt = band_mesh(Q, Nn, k(0.022), k(0.005), taper=tp)
        bag.add('gold', Vt, Tt, GOLD * 1.05)
    # ── 髻根束发的金箍 ──
    ring = [H.p(0.0575 * math.cos(t), 0.03 + 0.062 * math.sin(t), 0.232) for t in np.linspace(0, 2 * math.pi, 33)]
    Vt, Tt = tube_mesh(ring, H.k(0.0085), segs=8, cap=False)
    bag.add('gold', Vt, Tt, GOLD_LIT)
    # ── 宝冠上嵌的宝石、冠顶的火焰珠 ──
    for pc, zc, col in ((0.98, 0.185, CINNABAR * 1.15), (-0.98, 0.185, CINNABAR * 1.15), (1.72, 0.15, MALACHITE * 1.15), (-1.72, 0.15, MALACHITE * 1.15)):
        bag.add('gold', np.array([H.p(q) for q in Vs * np.array([0.012, 0.012, 0.014]) + crown_pt(pc, zc, 0.002)]), Ts, col)
    tp_ = crown_pt(0.0, 0.118 + 0.215, -CR_T * 0.5)
    bag.add('gold', np.array([H.p(q) for q in Vs * np.array([0.011, 0.011, 0.015]) + tp_ + V(0, 0, 0.006)]), Ts, GOLD_LIT)


def edge_strips(bag, B, info, s):
    """云肩前襟两道、抹胸上沿一道衣缘纹带（贴 paint_robe_band）"""
    k = B.k
    cape, wrap = info['cape'], info['wrap']
    strips = []
    allnode = info['allnode']
    xs = np.linspace(0.02, 0.26, 49)
    for sx in (-1, 1):
        edge = []
        for z in np.linspace(1.335, 1.63, 20):
            Q = np.array([B.p(sx * x, -0.45, z) for x in xs])
            Pc, Nc, okc = surf(cape, Q, B.d(0, 1, 0), tmax=k(0.8))
            Pa, Na, oka = surf(allnode, Q, B.d(0, 1, 0), tmax=k(0.8))
            front = okc & (np.abs(Pc[:, 1] - Pa[:, 1]) < k(0.003))
            if front.any():
                edge.append((sx * (xs[np.argmax(front)] + 0.02), -0.45, z))
        if len(edge) > 6:
            P, N, ok = surf(cape, np.array([B.p(q) for q in edge]), B.d(0, 1, 0), tmax=k(0.8))
            if ok.sum() > 6:
                strips.append((P[ok], N[ok], 0.026))
    xs = np.linspace(-0.17, 0.15, 26)
    Q = np.array([B.p(x, -0.4, 1.47 + 0.2 * x - 0.018) for x in xs])
    P, N, ok = surf(wrap, Q, B.d(0, 1, 0), tmax=k(0.7))
    # 被云肩盖住的两头不要
    ok &= sdf.ev_points(cape, P) > k(0.004)
    if ok.sum() > 6:
        strips.append((P[ok], N[ok], 0.026))
    for P, N, w in strips:
        vv, tt, uv = st.strip_mesh(P, N, k(w), k(0.0045), False, period=k(w) * 8, sub=3, sink=k(0.008))
        bag.add('paint_robe_band', vv, tt, np.ones(3), UV=uv)


# ====================================================================== 组装
def guanyin_bag(s=1.0, res=1.0, budget=1.0, verbose=True):
    bag = lotus_stand(s)
    print(f'[yjm] guanyin 莲台 {bag.tris()} 个三角形')
    B = Frame((0, 0, TOP * s), None, s)
    info = {}
    core = torso(B)
    hd, H = head_node(B, core, info)
    tag = verbose and 'guanyin'

    # ── 头：脸正面、头发、颈胸分区减面 ──
    def face_region(X):
        x, y, z = to_local(H, X[:, 0], X[:, 1], X[:, 2])
        return (y < -0.085) & (z > -0.235) & (z < 0.07) & (np.abs(x) < 0.125)

    def hair_region(X):
        x, y, z = to_local(H, X[:, 0], X[:, 1], X[:, 2])
        return z > st.hairline_z(np.arctan2(x, -y)) + 0.008
    lo, hi = st.fbox(H, (-0.27, -0.27, -0.72), (0.27, 0.27, 0.46), 0.0)

    def band_region(X):     # 鬓角到脑后的发际线两边留密一点：头发和皮肤是按三角形分的两种材质，面大了分界线是锯齿
        x, y, z = to_local(H, X[:, 0], X[:, 1], X[:, 2])
        phi = np.arctan2(x, -y)
        return (np.abs(z - st.hairline_z(phi)) < 0.012) & (np.abs(phi) > 0.9) & ~face_region(X)
    hv, ht = sdf_piece(hd, 0.0019 * s * res, [(face_region, int(22000 * budget)), (band_region, int(4200 * budget)),
                                             (lambda X: hair_region(X) & ~band_region(X), int(6500 * budget)),
                                             (lambda X: ~face_region(X) & ~hair_region(X) & ~band_region(X), int(8300 * budget))],
                       tag and 'head', lo=lo, hi=hi)
    x, y, z = to_local(H, hv[:, 0], hv[:, 1], hv[:, 2])
    phi = np.arctan2(x, -(y - 0.02))
    hair = ss(0.003, 0.006, z - st.hairline_z(np.arctan2(x, -y)))
    tri_hair = hair[ht].mean(axis=1) > 0.5
    bag.add('paint_buddha_face', hv, ht[~tri_hair], np.ones(3), UV=st.face_uv(H, hv))
    # 头发：石青，发丝的棱亮一点、沟里深（同一道正弦，和浮雕对得上）
    bun = ss(0.2, 0.235, z)
    g = np.sin(phi * 40 + 2.5 * np.sin(z * 38)) * (1 - bun) + np.sin(phi * 13 + z * 120) * bun
    hc = HAIR[None, :] * (0.74 + 0.2 * g)[:, None]
    bag.add('toon', hv, ht[tri_hair], np.clip(hc, 0, 1))
    # ── 宝冠 ──
    cn = crown_node(H)
    cv, ct = sdf_piece(cn, 0.0013 * s * res, int(18000 * budget), tag and 'crown', lo=np.asarray(cn.lo) - 0.004 * s, hi=np.asarray(cn.hi) + 0.004 * s)
    bag.add('gold', cv, ct, np.tile(GOLD, (len(cv), 1)) * (1 + 0.04 * gilt_noise(cv / s, 5))[:, None])
    # ── 手、脚 ──
    hands, feet = limbs(B, info)
    for i, nd in enumerate(hands):
        vv, tt = sdf_piece(nd, 0.0014 * s * res, int(6500 * budget), tag and f'hand{i}')
        bag.add('paint_buddha_face', vv, tt, np.ones(3), UV=np.tile(st.SKIN_UV, (len(vv), 1)))
    for i, nd in enumerate(feet):
        vv, tt = sdf_piece(nd, 0.0018 * s * res, int(2800 * budget), tag and f'foot{i}')
        bag.add('paint_buddha_face', vv, tt, np.ones(3), UV=np.tile(st.SKIN_UV, (len(vv), 1)))
    # ── 衣裙 ──
    body = garments(B, core, info)
    fold_keys = st.path_keys(info['fold_paths'] + info['scarf_paths'] + info['cape_folds'], 0.02 * s)

    def fold_region(X):
        return np.isin(st.voxel_keys(X, 0.02 * s), fold_keys)

    def upper_region(X):
        return (X[:, 2] > (TOP + 1.1) * s) & ~fold_region(X)
    bv, bt = sdf_piece(body, 0.0032 * s * res, [(fold_region, int(30000 * budget)), (upper_region, int(19000 * budget)),
                                               (lambda X: ~fold_region(X) & ~upper_region(X), int(24500 * budget))],
                       tag and 'body', lo=B.p(-0.56, -0.42, -0.01), hi=B.p(0.56, 0.36, 1.76))
    lab = sdf.components(len(bv), bt)
    ids, cnt = np.unique(lab, return_counts=True)
    if len(ids) > 1:
        print(f'[yjm] guanyin 身子：{len(ids)} 块（最大 {cnt.max()} 个点），零碎 {int((cnt < 300).sum())} 块扔掉')
        keep = np.isin(lab, ids[cnt >= 300])
        remap = -np.ones(len(bv), np.int64)
        remap[keep] = np.arange(int(keep.sum()))
        bt = remap[bt]
        bt = bt[(bt >= 0).all(axis=1)]
        bv = bv[keep]
    bag.add('gold', bv, bt, np.tile(GOLD, (len(bv), 1)) * (1 + 0.05 * gilt_noise(bv / s, 3))[:, None])
    # ── 饰物、衣缘 ──
    allnode = sdf.Union([body, hd], 0.0)
    info['allnode'] = allnode
    n0 = bag.tris()
    ornaments(bag, B, info, allnode, s)
    print(f'[yjm] guanyin 饰物 {bag.tris() - n0} 个三角形')
    edge_strips(bag, B, info, s)
    info['B'] = B
    return bag, info


def _shot(name, objs, ctr, rad, view, floor=True):
    """多拍一张：对着 ctr、照 rad 这么大的一块（整体那张是 kit.render_preview 拍的）"""
    import bpy
    import kit
    from mathutils import Vector
    sc = bpy.context.scene
    yaw, pitch, kk = view
    yaw, pitch = math.radians(yaw), math.radians(pitch)
    cam = sc.camera
    ctr = Vector(ctr)
    dist = rad / math.tan(cam.data.angle / 2) * 1.12 * kk
    dirv = Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
    cam.location = ctr + dirv * dist
    cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.clip_start = max(0.01, dist * 0.05)
    cam.data.clip_end = dist * 4 + 100
    if 'ground' in bpy.data.objects:
        bpy.data.objects['ground'].hide_render = not floor
    sc.render.filepath = os.path.join(kit.PREVIEW, name + '.png')
    bpy.ops.render.render(write_still=True)
    cam.data.clip_start = 0.1


def finish_shots(a, view, shots):
    """同 Asset.finish（不再烤暗部），另外按 shots = {后缀: (中心, 半径, 视角)} 多拍几张近景"""
    import bpy
    import kit
    a.check_coplanar()
    objs = a.to_objects()
    tris = a.export(objs)
    if os.environ.get('YJ_PREVIEW', '1') != '0':
        kit.render_preview(a.name, objs, view, True)
        for tag, (ctr, rad, v) in shots.items():
            _shot(f'{a.name}_{tag}', objs, ctr, rad, v)
    for ob in objs:
        me = ob.data
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
    for b in a.parts.values():
        b.free()
    a.parts = {}
    print(f'[yjm] {a.name}: {tris} tris')
    return tris


def guanyin(name, s=1.0):
    import kit
    a = kit.Asset(name)
    res = float(os.environ.get('YJ_RES', '1'))
    bag, info = guanyin_bag(s, res=res, budget=1.0 if res <= 1.01 else 0.6)
    H = info['H']

    def chin(X):
        x, y, z = to_local(H, X[:, 0], X[:, 1], X[:, 2])
        return ss(-0.07, -0.1, z) * ss(-0.02, -0.06, y) * (1 - ss(-0.25, -0.29, z)) * (1 - ss(0.12, 0.15, np.abs(x)))
    bag.bake_ao(dist=0.2 * s, samples=48, face=dict(strength=0.4, blur=0.02 * s, floor_fn=chin), shell_k=0.35)
    bag.bake_ao(dist=0.035 * s, samples=32, strength=0.55, shade=(0.55, 0.38, 0.22), skip=('toon', 'paint_robe_band'),
                face=dict(strength=0.25, blur=0.005 * s, floor_fn=chin), shell_k=0.3)
    bag.gilt(s)
    bag.to_asset(a)
    print(f'[yjm] {name}: 合计 {bag.tris()} 个三角形')
    hc = H.p(0, -0.02, 0.06)
    shots = {'face': (hc, 0.26 * s, (8, 2, 1.0)), 'side': ((0, 0, 1.45 * s), 1.5 * s, (88, 6, 1.0)),
             'bust': ((0, 0, (TOP + 1.45) * s), 0.55 * s, (-14, 4, 1.0)), 'back': ((0, 0, 1.45 * s), 1.5 * s, (180, 8, 1.0)),
             'low': ((0, 0, (TOP + 0.55) * s), 0.72 * s, (14, 10, 1.0)), 'face_l': (hc, 0.2 * s, (-38, -6, 1.0)),
             'hand_r': (info['B'].p(WR[R_] + V(0, 0, 0.08)), 0.17 * s, (-25, 5, 1.0)), 'hand_l': (info['B'].p(WR[L_] + V(0, -0.06, 0.1)), 0.24 * s, (30, 18, 1.0)),
             'feet': ((0, -0.1 * s, (TOP + 0.08) * s), 0.3 * s, (10, 22, 1.0))}
    tris = finish_shots(a, (10, 8, 0.95), shots)
    st.check_export(name)
    return tris


# ====================================================================== 背光
MG_X, MG_W0, MG_W1 = 0.78, 0.3, 3.16      # 背光的平面范围：x ±MG_X，w（= 离莲台底面的高度）MG_W0..MG_W1（s=1 时的米）
MG_Y, MG_T = 0.285, 0.03                  # 板的中面在像后面多远（y）、板厚
MG_HEAD = (0.0, TOP + 1.96)               # 头光圆心
MG_HR = 0.335                             # 头光半径
MG_BODY = (0.0, TOP + 0.95, 0.47, 0.965)  # 身光：椭圆的中心 w、两个半轴


class Plan:
    """背光的平面图（同 statues.Raster，范围是这里自己的）：d 轮廓的有符号距离（里负）、h 浮雕高、ground 底子的颜色号"""

    def __init__(self, step):
        self.step = step
        self.xs = np.arange(-MG_X, MG_X + step / 2, step)
        self.ws = np.arange(MG_W0, MG_W1 + step / 2, step)
        self.X, self.W = np.meshgrid(self.xs, self.ws)
        self.d = np.full(self.X.shape, 1.0, np.float32)
        self.h = np.zeros(self.X.shape, np.float32)
        self.zone = np.zeros(self.X.shape, np.int8)

    def win(self, lo, hi):
        i0 = max(int((lo[1] - MG_W0) / self.step), 0)
        i1 = min(int((hi[1] - MG_W0) / self.step) + 2, len(self.ws))
        j0 = max(int((lo[0] + MG_X) / self.step), 0)
        j1 = min(int((hi[0] + MG_X) / self.step) + 2, len(self.xs))
        return (slice(i0, i1), slice(j0, j1)) if i1 > i0 and j1 > j0 else None

    def stroke(self, pts, rad, height, base=0.0, shape=True, groove=0.0):
        """一笔（压扁的管子）：火舌。shape=True 时也算进轮廓（火舌之间是透空的）"""
        pts = np.asarray(pts, np.float64)
        rad = np.asarray(rad, np.float64)
        pad = rad.max() + self.step * 2
        w = self.win(pts.min(0) - pad, pts.max(0) + pad)
        if w is None:
            return
        d, r, t = st._seg_dist(self.X[w], self.W[w], pts, rad)
        sd = d - r
        q = np.clip(d / np.maximum(r, 1e-6), 0, 1)
        prof = np.sqrt(np.clip(1 - q * q, 0, 1)) ** 0.7
        if groove > 0:
            prof = prof - groove * np.exp(-(q / 0.18) ** 2) * (t < 0.9)
        hh = base + height * prof
        if shape:
            self.d[w] = np.minimum(self.d[w], sd)
        self.h[w] = np.where(sd < 0, np.maximum(self.h[w], hh), self.h[w])


_PLAN = {}


def mandorla_plan(step=0.003):
    """观音背光的平面图：舟形——身后一个长椭圆的身光，头后一轮圆的头光，外面一圈一条条往上卷的火舌，顶上一股高的火焰。
    头光：外沿两道弦纹夹一圈连珠，里面一圈缠枝（波浪形的蔓加小叶），再里面一圈莲瓣，中心放射的光线。
    身光：沿边两道弦纹夹连珠，一圈缠枝，里面是从头光往下散开的细光线"""
    if step in _PLAN:
        return _PLAN[step]
    R = Plan(step)
    X, W = R.X, R.W
    hx, hw = MG_HEAD
    bx, bw, ba, bb = MG_BODY
    rh = np.hypot(X - hx, W - hw)
    th = np.arctan2(X - hx, W - hw)
    d_head = rh - MG_HR
    q = np.sqrt((X / ba) ** 2 + ((W - bw) / bb) ** 2)
    # 椭圆的距离：隐函数除以梯度的长（近似，离边几厘米以内够准）
    gl = np.sqrt((X / ba ** 2) ** 2 + ((W - bw) / bb ** 2) ** 2) / np.maximum(q, 1e-6)
    d_body = (q - 1) / np.maximum(gl, 1e-6)
    d_in = np.minimum(d_head, d_body)
    R.d = d_in.astype(np.float32)
    inside = d_in < 0
    h = np.where(inside, 0.004, 0.0)
    zone = np.zeros(X.shape, np.int8)
    g = lambda x, c, w_: np.exp(-((x - c) / w_) ** 2)
    # ── 身光 ──（头光盖住的地方让给头光）
    body_only = inside & (d_head > 0.0)
    e = -d_body
    hb = 0.009 * g(e, 0.012, 0.006) + 0.008 * g(e, 0.058, 0.005) + 0.008 * g(e, 0.16, 0.005)
    # 连珠：沿椭圆的周长排（用角度近似弧长）
    ang_b = np.arctan2(X / ba, (W - bw) / bb)
    arc = ang_b * (ba + bb) / 2
    u = arc / 0.026
    bead = np.clip(1 - (((u - np.round(u)) * 0.026) ** 2 + (e - 0.035) ** 2) / 0.0105 ** 2, 0, 1)
    hb = hb + 0.012 * np.sqrt(bead)
    # 缠枝：一道波浪形的主蔓，蔓的每个弯里一片小叶
    vv = e - 0.108
    wave = 0.026 * np.sin(arc / 0.052)
    hb = hb + 0.009 * g(vv, wave, 0.0065)
    leaf = np.clip(1 - ((vv + 0.9 * wave) / 0.02) ** 2 - (np.sin(arc / 0.052) ** 2 < 0.45) * 2.0, 0, 1)
    hb = hb + 0.008 * np.sqrt(leaf)
    band_b = (e > 0.064) & (e < 0.154)
    # 里面：从头光往下散开的细光线
    ray = np.clip(np.sin(th * 46), 0, 1) ** 2
    hb = hb + 0.0035 * ray * ss(0.17, 0.2, e)
    h = np.where(body_only, 0.004 + hb, h)
    zone = np.where(body_only & band_b, 1, zone)
    zone = np.where(body_only & (e >= 0.165), 3, zone)
    # ── 头光 ──
    head = d_head < 0
    e = -d_head
    hh = 0.01 * g(e, 0.012, 0.006) + 0.009 * g(e, 0.056, 0.005) + 0.009 * g(e, 0.135, 0.005)
    u = th * (MG_HR - 0.034) / 0.026
    bead = np.clip(1 - (((u - np.round(u)) * 0.026) ** 2 + (e - 0.034) ** 2) / 0.0105 ** 2, 0, 1)
    hh = hh + 0.012 * np.sqrt(bead)
    vv = e - 0.096
    wave = 0.022 * np.sin(th * 14)
    hh = hh + 0.009 * g(vv, wave, 0.006)
    leaf = np.clip(1 - ((vv + 0.9 * wave) / 0.018) ** 2 - (np.sin(th * 14) ** 2 < 0.45) * 2.0, 0, 1)
    hh = hh + 0.008 * np.sqrt(leaf)
    band_h = (e > 0.062) & (e < 0.13)
    # 莲瓣一圈：十六瓣，瓣尖朝外，每瓣中间一道脊
    rr = MG_HR - e
    a16 = ((th / (2 * np.pi) * 16) % 1.0 - 0.5) * 2
    tipr = 0.105 + 0.085 * spow(1 - np.abs(a16) ** 1.8, 0.55)
    pet = (rr < tipr) & (rr > 0.07)
    hh = hh + np.where(pet, 0.007 + 0.006 * (1 - np.abs(a16)) + 0.004 * g(a16, 0.0, 0.08), 0.0) + 0.006 * g(rr, tipr, 0.005) * (rr > 0.07)
    hh = hh + 0.004 * np.clip(np.sin(th * 30), 0, 1) ** 2 * (rr < 0.07)
    h = np.where(head, 0.007 + hh, h)
    zone = np.where(head & band_h, 2, zone)
    zone = np.where(head & pet, 4, zone)
    zone = np.where(head & (rr < MG_HR - 0.142) & ~pet, 5, zone)
    R.h = h.astype(np.float32)
    R.zone = zone
    # ── 火焰：沿着外沿一条条 S 形往上卷的火舌（越往上越长），火舌之间透空 ──
    cw = (bw + hw) / 2
    edge = []
    for a_ in np.linspace(-2.92, 2.92, 800):
        dv = V(math.sin(a_), math.cos(a_))
        lo_, hi_ = 0.0, 2.2
        for _ in range(26):
            m = (lo_ + hi_) / 2
            px, pw = dv[0] * m, cw + dv[1] * m
            qq = math.sqrt((px / ba) ** 2 + ((pw - bw) / bb) ** 2)
            ins = (qq < 1) or (math.hypot(px - hx, pw - hw) < MG_HR)
            lo_, hi_ = (m, hi_) if ins else (lo_, m)
        edge.append((dv[0] * lo_, cw + dv[1] * lo_))
    edge = np.array(edge)
    seg = np.linalg.norm(np.diff(edge, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    tot = cum[-1]
    n_t = int(tot / 0.062)
    for i in range(n_t + 1):
        sl = tot * i / n_t
        j = int(np.clip(np.searchsorted(cum, sl), 1, len(edge) - 2))
        p = V(edge[j])
        tg = V(edge[j + 1]) - V(edge[j - 1])
        tg /= np.linalg.norm(tg)
        nrm = V(tg[1], -tg[0])
        if nrm.dot(p - V(0, cw)) < 0:
            nrm = -nrm
        hf = float(np.clip((p[1] - (TOP + 0.2)) / (hw + MG_HR - TOP - 0.2), 0, 1))
        if p[1] < TOP + 0.3:
            continue
        big = (i % 2 == 0)
        L = (0.1 + 0.15 * hf ** 1.2) * (1.0 if big else 0.62)
        sd_ = 1.0 if p[0] >= 0 else -1.0
        d0 = nrm * (0.75 - 0.35 * hf) + V(0, 1) * (0.55 + 0.5 * hf)
        d0 /= np.linalg.norm(d0)
        th0 = math.atan2(d0[1], d0[0])
        pts, rad = [], []
        c = p - nrm * 0.03
        for kk in range(16):
            t = kk / 15
            pts.append(c.copy())
            rad.append((0.03 if big else 0.021) * spow(math.sin(math.pi * min(1.0, 0.22 + 0.78 * t ** 0.85)), 0.8) + 0.0035)
            tw = th0 + sd_ * (math.radians(38) * math.sin(math.pi * t) * (1 - hf * 0.5) - math.radians(55) * t ** 2.4)
            c = c + V(math.cos(tw), math.sin(tw)) * (L / 15)
        R.stroke(pts, rad, 0.016, base=0.006, shape=True, groove=0.3)
    # 顶上正中一股高的火焰，两边各一股矮一点的
    top = V(hx, hw + MG_HR - 0.03)
    for ox, L, r0, lean in ((0.0, 0.5, 0.075, 0.0), (-0.085, 0.3, 0.05, 0.5), (0.085, 0.3, 0.05, -0.5)):
        pts, rad = [], []
        c = top + V(ox, -0.01 * abs(ox) / 0.085)
        for kk in range(20):
            t = kk / 19
            pts.append(c.copy())
            rad.append(r0 * spow(math.sin(math.pi * min(1.0, 0.3 + 0.7 * t ** 0.8)), 0.9) + 0.004)
            a_ = math.pi / 2 + lean * (1 - t) * 0.6 + (0.3 * math.sin(2.2 * math.pi * t) * (1 if ox >= 0 else -1) if ox == 0 else 0.25 * math.sin(math.pi * t) * (-lean))
            c = c + V(math.cos(a_), math.sin(a_)) * (L / 19)
        R.stroke(pts, rad, 0.02, base=0.008, shape=True, groove=0.3)
    R.h = st._blur2(R.h, 0.0038 / step)
    _PLAN[step] = R
    return R


def mandorla_guanyin(name, s=1.0):
    """观音身后的背光：一块竖着的舟形板，立在莲台面上（像的身后），浮雕和透空的火焰都是真的形体，全部鎏金（部件 gold）。
    原点和观音一样在莲台底面中心（和观音放在同一点），-y 朝前"""
    import kit
    a = kit.Asset(name)
    step = 0.003
    R = mandorla_plan(step)
    nx, nw = len(R.xs), len(R.ws)

    def samp(A, xl, wl):
        fx = np.clip((xl + MG_X) / step, 0, nx - 1.001)
        fw = np.clip((wl - MG_W0) / step, 0, nw - 1.001)
        j0, i0 = fx.astype(np.int64), fw.astype(np.int64)
        tx, tw = (fx - j0).astype(np.float32), (fw - i0).astype(np.float32)
        return (A[i0, j0] * (1 - tx) + A[i0, j0 + 1] * tx) * (1 - tw) + (A[i0 + 1, j0] * (1 - tx) + A[i0 + 1, j0 + 1] * tx) * tw

    def fn(X, Y, Z):
        X, Y, Z = np.broadcast_arrays(X, Y, Z)
        xl, wl, nl = X / s, Z / s, (MG_Y * s - Y) / s
        d2 = samp(R.d, xl, wl)
        hh = samp(R.h, xl, wl)
        d = np.maximum(d2, np.maximum(nl - (MG_T / 2 + hh), -nl - MG_T / 2))
        d = np.maximum(d, (TOP + 0.004) - wl)
        return (d * s).astype(np.float32)
    lo = V(-MG_X, MG_Y - 0.06, MG_W0) * s
    hi = V(MG_X, MG_Y + 0.04, MG_W1) * s
    node = sdf.Func(fn, lo, hi)
    Vv, T = sdf_piece(node, 0.004 * s, int(34000), name, lo=lo, hi=hi)
    # 颜色：鎏金；缠枝带、莲瓣之间的底子染一点石青、石绿、朱（只在低处，凸起的纹样还是金）
    xl, wl = Vv[:, 0] / s, Vv[:, 2] / s
    zn = np.round(samp(R.zone.astype(np.float32), xl, wl)).astype(int)
    hh = samp(R.h, xl, wl)
    front = Vv[:, 1] < (MG_Y - MG_T / 2 - 0.001) * s
    col = np.tile(GOLD, (len(Vv), 1)) * (1 + 0.05 * gilt_noise(Vv / s, 9))[:, None]
    for z_, c_, lim in ((1, MALACHITE * 0.75 + GOLD_DARK * 0.25, 0.0085), (2, AZURE * 0.8 + GOLD_DARK * 0.2, 0.0115),
                        (3, GOLD_DARK * 0.9, 0.0052), (5, CINNABAR * 0.75 + GOLD_DARK * 0.25, 0.0085)):
        m = front & (zn == z_) & (hh < lim)
        col[m] = c_
    col[~front] = GOLD_DARK
    bag = Bag()
    bag.add('gold', Vv, T, col)
    # 背后两根撑子：从板背面斜着落到莲台面的后沿
    for sx in (-1, 1):
        top_ = V(sx * 0.14, MG_Y + MG_T / 2, TOP + 0.62) * s
        bot = V(sx * 0.1, 0.345, TOP - 0.004) * s
        Vt, Tt = tube_mesh([bot, (bot + top_) / 2 + V(0, 0.012 * s, 0), top_], 0.013 * s, segs=8)
        bag.add('gold', Vt, Tt, GOLD_DARK)
    bag.bake_ao(dist=0.06 * s, samples=32, strength=0.6)
    bag.gilt(s)
    bag.to_asset(a)
    print(f'[yjm] {name}: {bag.tris()} 个三角形')
    tris = finish_shots(a, (0, 6, 1.0), {'top': ((0, MG_Y * s, (TOP + 2.0) * s), 0.62 * s, (12, 4, 1.0))})
    st.check_export(name)
    return tris


ASSETS = {'guanyin': guanyin, 'mandorla_guanyin': mandorla_guanyin}
