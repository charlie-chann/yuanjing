"""走路动作的整套加工：从 100STYLE 的长段动捕里截出步态循环、停步、转身起步，加工成能同步混合的片段，再交给 convert.py 导出 FBX。

为什么要加工（原来直接截一段就用，走起来不自然）：
- 同步：每段步态循环都从「左脚跟着地」开始，右脚跟着地按时间拉伸对齐到正中间（相位 0.5）。
  几段不同快慢的循环按同一个相位混合时，两只脚的位置一致，不会互相抵消成小碎步。
- 直：动捕里人一边走一边慢慢转弯（Walk_Monk 一个循环偏 8.8 度），这里把朝向的漂移按时间均匀扣掉，路线拉直。
- 首尾接得上：循环末帧和首帧的差别（每个关节）按时间均匀分摊掉，循环时不跳。
- 脊柱、脖子：100STYLE 的脊柱四节、脖子两节，Unity 人形骨骼只认三节和一节，多出来的 Spine3、Neck1 的转动会被丢掉
  （肩的反向扭转、头的稳定都丢了）。这里把它们的转动并到上一节（Spine2、Neck）里，自己保持基准姿势。
- 女生：用同一个人的正常走路，改成更轻巧的样子：手臂摆幅收小、肘微弯贴身，两脚落点往中线收，骨盆左右摆动和扭转加大，
  上身挺一点，步频快一点（时间压缩 7%）。
- 快走：动捕里正常走路最快约 1.0 髋高/秒，游戏里主角要 1.3 以上。快走那段用 GracefulArms 的腿和骨盆（真人快走），
  上身换成 Neutral 同相位的上身（GracefulArms 的手一直张开着，不能用）。

用法（在仓库根目录）：
  python3 tools/mocap/locomotion.py            # 加工 + 调 Blender 导出 FBX 到 unity/Sanctuary/Assets/Motion/，写 Locomotion.json
  python3 tools/mocap/locomotion.py --sheet D  # 另外把每段画成火柴人逐帧图存到目录 D（侧面 + 脚印俯视）
  python3 tools/mocap/locomotion.py --no-fbx   # 只加工、出图，不导出
"""
import json
import math
import os
import re
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
SRC = os.path.join(ROOT, 'assets_src', 'mocap', '100style')
OUT = os.path.join(ROOT, 'unity', 'Sanctuary', 'Assets', 'Motion')
BLENDER = '/Applications/Blender.app/Contents/MacOS/Blender'
FPS = 60.0
HIP = 0.855          # 100STYLE 演员站直时髋高（米），速度都按「髋高/秒」说
FOOT_PITCH = 21.0    # 平踩在地上时踝→脚趾根往下斜的角度（度，100STYLE 走路踩稳时的中位数）

# ───────────── 四元数（w, x, y, z），全部按帧向量化 ─────────────


def qmul(a, b):
    w1, x1, y1, z1 = np.moveaxis(a, -1, 0)
    w2, x2, y2, z2 = np.moveaxis(b, -1, 0)
    return np.stack([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2], -1)


def qinv(q):
    return q * np.array([1, -1, -1, -1])


def qnorm(q):
    return q / np.linalg.norm(q, axis=-1, keepdims=True)


def qaxis(axis, rad):
    axis = np.asarray(axis, float)
    axis = axis / np.linalg.norm(axis, axis=-1, keepdims=True)
    rad = np.asarray(rad, float)
    shape = np.broadcast_shapes(axis.shape[:-1], rad.shape)
    axis = np.broadcast_to(axis, shape + (3,))
    rad = np.broadcast_to(rad, shape)[..., None]
    return np.concatenate([np.cos(rad / 2), axis * np.sin(rad / 2)], -1)


def qslerp(a, b, t):
    t = np.asarray(t, float)[..., None] if np.ndim(t) else t
    d = np.sum(a * b, -1, keepdims=True)
    b = np.where(d < 0, -b, b)
    d = np.abs(d)
    th = np.arccos(np.clip(d, -1, 1))
    s = np.sin(th)
    small = s < 1e-6
    wa = np.where(small, 1 - t, np.sin((1 - t) * th) / np.where(small, 1, s))
    wb = np.where(small, t, np.sin(t * th) / np.where(small, 1, s))
    return qnorm(wa * a + wb * b)


def qpow(q, t):
    """q 的 t 次方（绕同一根轴转 t 倍角度）"""
    q = np.where(q[..., :1] < 0, -q, q)
    w = np.clip(q[..., 0], -1, 1)
    th = np.arccos(w)
    s = np.sin(th)
    ax = q[..., 1:] / np.where(s[..., None] < 1e-8, 1, s[..., None])
    th2 = th * t
    return np.concatenate([np.cos(th2)[..., None], ax * np.sin(th2)[..., None]], -1)


def qrot(q, v):
    """用 q 转向量 v"""
    qv = np.concatenate([np.zeros(v.shape[:-1] + (1,)), v], -1)
    return qmul(qmul(q, qv), qinv(q))[..., 1:]


def q_from_zyx(deg):
    """BVH 的 Zrotation Yrotation Xrotation（R = Rz·Ry·Rx）"""
    r = np.radians(deg)
    return qmul(qmul(qaxis([0, 0, 1], r[..., 0]), qaxis([0, 1, 0], r[..., 1])), qaxis([1, 0, 0], r[..., 2]))


def q_to_mat(q):
    w, x, y, z = np.moveaxis(q, -1, 0)
    return np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], -1),
                     np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], -1),
                     np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], -1)], -2)


def zyx_from_q(q):
    R = q_to_mat(q)
    y = -np.arcsin(np.clip(R[..., 2, 0], -1, 1))
    x = np.arctan2(R[..., 2, 1], R[..., 2, 2])
    z = np.arctan2(R[..., 1, 0], R[..., 0, 0])
    return np.degrees(np.stack([z, y, x], -1))


def qmean(q):
    """一组四元数的平均（同半球后求和归一，角度不大时够用）"""
    q = np.where(np.sum(q * q[:1], -1, keepdims=True) < 0, -q, q)
    return qnorm(q.mean(0))


# ───────────── BVH ─────────────


class Bvh:
    def __init__(self, name):
        path = os.path.join(SRC, name + '.bvh')
        txt = open(path).read()
        head, motion = txt.split('MOTION')
        self.header = head
        self.names, self.parent, self.offset = [], [], []
        stack = []
        toks = re.findall(r'\{|\}|[^\s{}]+', head)
        i = 0
        while i < len(toks):
            t = toks[i]
            if t in ('ROOT', 'JOINT'):
                self.names.append(toks[i + 1])
                self.parent.append(stack[-1] if stack else -1)
                i += 2
                continue
            if t == 'End':           # End Site：没有通道，不算关节
                stack.append(None)
                i += 2
                continue
            if t == '{':
                if stack and stack[-1] is None and toks[i - 1] == 'Site':
                    pass
                else:
                    stack.append(len(self.names) - 1)
            elif t == '}':
                stack.pop()
            elif t == 'OFFSET':
                if stack and stack[-1] is not None and len(self.offset) < len(self.names):
                    self.offset.append([float(x) for x in toks[i + 1:i + 4]])
                i += 4
                continue
            i += 1
        lines = motion.strip().split('\n')
        self.ft = float(lines[1].split()[2])
        self.data = np.loadtxt(lines[2:], dtype=np.float64)
        J = len(self.names)
        assert self.data.shape[1] == J * 6, (self.data.shape, J)
        self.offset = np.array(self.offset) / 100.0
        self.J = J
        self.idx = {n: i for i, n in enumerate(self.names)}

    def frames(self):
        """全部帧的 (局部旋转 q[N,J,4], 关节位置通道 p[N,J,3] 米)"""
        d = self.data.reshape(len(self.data), self.J, 6)
        return q_from_zyx(d[..., 3:]), d[..., :3] / 100.0


def fk(bvh, q, p):
    """全局位置 [N,J,3]、全局旋转 [N,J,4]（p 是各关节的位置通道，根的是轨迹）"""
    N = len(q)
    G = np.zeros_like(q)
    X = np.zeros_like(p)
    for j, par in enumerate(bvh.parent):
        if par < 0:
            G[:, j] = q[:, j]
            X[:, j] = p[:, j]
        else:
            G[:, j] = qmul(G[:, par], q[:, j])
            X[:, j] = X[:, par] + qrot(G[:, par], p[:, j])
    return X, G


# ───────────── 步态分析 ─────────────


def smooth(x, k):
    if k <= 1:
        return x
    w = np.ones(k) / k
    pad = np.pad(x, [(k // 2, k - 1 - k // 2)] + [(0, 0)] * (x.ndim - 1), mode='edge')
    return np.apply_along_axis(lambda c: np.convolve(c, w, 'valid'), 0, pad)


def heading(bvh, X):
    """身体朝向（弧度，绕竖直轴，0 = +z）：由两髋连线转 90 度得到，按走的方向定正负"""
    I = bvh.idx
    lr = X[:, I['LeftUpLeg']] - X[:, I['RightUpLeg']]
    fwd = np.stack([-lr[:, 2], np.zeros(len(lr)), lr[:, 0]], 1)   # 左 × 上 = 前
    h = np.unwrap(np.arctan2(fwd[:, 0], fwd[:, 2]))
    return smooth(h, 9)


def left_dir(bvh, X):
    I = bvh.idx
    lr = X[:, I['LeftUpLeg']] - X[:, I['RightUpLeg']]
    lr[:, 1] = 0
    return lr / np.linalg.norm(lr, axis=1, keepdims=True)


def strikes(bvh, X, ft, side):
    """脚跟着地的帧：脚踝低、水平速度掉到 0.3 米/秒以下，而且之前 0.6 秒里摆过腿（速度超过 0.9）"""
    a = X[:, bvh.idx[side + 'Foot']]
    av = np.linalg.norm(np.gradient(a[:, [0, 2]], ft, axis=0), axis=1)
    h = a[:, 1]
    floor = np.percentile(h, 2)
    c = (av < 0.3) & (h < floor + 0.04)
    res = []
    for i in range(1, len(c)):
        if c[i] and not c[i - 1]:
            w = av[max(0, i - int(0.6 / ft)):i]
            if len(w) and w.max() > 0.9:
                res.append(i)
    return np.array(res)


def contacts(bvh, X, ft, side):
    """每帧这只脚是不是踩在地上（脚踝或脚尖低、水平速度小）"""
    a = X[:, bvh.idx[side + 'Foot']]
    t = X[:, bvh.idx[side + 'ToeBase']]
    av = np.linalg.norm(np.gradient(a[:, [0, 2]], ft, axis=0), axis=1)
    tv = np.linalg.norm(np.gradient(t[:, [0, 2]], ft, axis=0), axis=1)
    fa, ftoe = np.percentile(a[:, 1], 3), np.percentile(t[:, 1], 3)
    return ((a[:, 1] < fa + 0.03) & (av < 0.35)) | ((t[:, 1] < ftoe + 0.025) & (tv < 0.35))


class Take:
    """一个源文件：帧、全局位置、着地事件"""
    cache = {}

    def __init__(self, name):
        self.name = name
        self.b = Bvh(name)
        self.q, self.p = self.b.frames()
        self.X, self.G = fk(self.b, self.q, self.p)
        self.ft = self.b.ft
        self.h = heading(self.b, self.X)
        self.L = strikes(self.b, self.X, self.ft, 'Left')
        self.R = strikes(self.b, self.X, self.ft, 'Right')

    @classmethod
    def get(cls, name):
        if name not in cls.cache:
            print(f'[loco] 读 {name} ...', flush=True)
            cls.cache[name] = Take(name)
        return cls.cache[name]

    def strike_near(self, side, t):
        s = self.L if side == 'L' else self.R
        return s[np.argmin(np.abs(s * self.ft - t))]

    def cycle(self, t):
        """从 t 附近的左脚着地开始的一个完整步态：(左着地, 右着地, 下一个左着地) 的帧号"""
        a = self.strike_near('L', t)
        b = self.L[self.L > a + int(0.7 / self.ft)][0]
        c = self.R[(self.R > a) & (self.R < b)]
        assert len(c) >= 1, (self.name, t)
        return a, int(c[0]), int(b)


# ───────────── 加工 ─────────────


def resample(q, p, src_t):
    """按源帧号（小数）重采样：旋转球面插值，位置线性插值"""
    i0 = np.clip(np.floor(src_t).astype(int), 0, len(q) - 2)
    f = (src_t - i0)
    qa, qb = q[i0], q[i0 + 1]
    qq = qslerp(qa, qb, np.broadcast_to(f[:, None], qa.shape[:-1]))
    pp = p[i0] + (p[i0 + 1] - p[i0]) * f[:, None, None]
    return qq, pp


def warp_cycle(take, a, c, b, tscale=1.0):
    """把一个步态拉成「左着地在 0、右着地在 0.5、末帧 = 下一个左着地」，帧率 60，周期按原来的（再乘 tscale）"""
    T = (b - a) * take.ft * tscale
    n = max(8, int(round(T * FPS)))
    u = np.arange(n + 1) / n
    src = np.where(u < 0.5, a + (c - a) * (u / 0.5), c + (b - c) * ((u - 0.5) / 0.5))
    q, p = resample(take.q, take.p, src)
    return q, p, n / FPS


def segment(take, t0, t1, tscale=1.0):
    a, b = t0 / take.ft, t1 / take.ft
    T = (b - a) * take.ft * tscale
    n = max(2, int(round(T * FPS)))
    src = a + (b - a) * np.arange(n + 1) / n
    q, p = resample(take.q, take.p, src)
    return q, p, n / FPS, src


def yaw_of(q_root):
    """根旋转的朝向角（弧度）：把身体前方（局部 +z 投影）的方向"""
    f = qrot(q_root, np.array([0.0, 0.0, 1.0]))
    return np.unwrap(np.arctan2(f[..., 0], f[..., 2]))


def straighten(bvh, q, p, drift):
    """按时间均匀扣掉朝向漂移 drift（弧度，正 = 绕 +y 转），路线一起掰直"""
    n = len(q)
    u = np.linspace(0, 1, n)
    rot = qaxis([0, 1, 0], -drift * u)
    q = q.copy()
    p = p.copy()
    q[:, 0] = qmul(rot, q[:, 0])
    start = p[0, 0].copy()
    d = p[:, 0] - start
    d[:, 1] = 0
    d2 = qrot(rot, d)
    p[:, 0, 0] = start[0] + d2[:, 0]
    p[:, 0, 2] = start[2] + d2[:, 2]
    return q, p


def path_drift(bvh, q, p):
    X, G = fk(bvh, q, p)
    h = heading(bvh, X)
    return h[-1] - h[0]


def close_loop(bvh, q, p, win=0.18):
    """循环首尾对上：每个关节末帧相对首帧的差（根只管俯仰、侧倾和高度、横向）分摊掉。
    躯干、手臂按时间均匀分摊；腿（大腿到脚趾）只在首尾接缝前后 win（周期的比例）里分摊，首尾各补一半：
    接缝处（相位 0 = 左脚跟着地）右脚正在蹬地，前后两个循环蹬到的程度差十几度，要是均匀摊到整个周期，
    右脚踩稳的那半个周期也会整个被转掉十几度（脚尖翘起来，踩着脚跟走）"""
    n = len(q)
    u = np.linspace(0, 1, n)[:, None]
    x = u[:, 0]
    # 接缝前后的权重：首帧 +1/2，末帧 -1/2，离接缝 win 以外为 0（余弦过渡）
    def fall(t):
        return np.where(t < win, 0.5 * (1 + np.cos(np.pi * np.clip(t / win, 0, 1))), 0.0)
    wseam = 0.5 * fall(x) - 0.5 * fall(1 - x)
    q = q.copy()
    p = p.copy()
    leg = set(bvh.idx[s + k] for s in ('Left', 'Right') for k in ('UpLeg', 'Leg', 'Foot', 'ToeBase') if s + k in bvh.idx)
    for j in range(bvh.J):
        d = qmul(q[-1, j], qinv(q[0, j]))           # 末 = d · 首
        if d[0] < 0:
            d = -d                                  # 走近路（不绕 360 度那一圈）
        if j in leg:
            corr = qpow(d[None].repeat(n, 0), wseam)   # 首帧 d^½·首，末帧 d^-½·末 = d^½·首
        else:
            corr = qpow(qinv(d)[None].repeat(n, 0), x)
        q[:, j] = qnorm(qmul(corr, q[:, j]))
    # 根的高度、横向位置：末帧回到首帧（前进方向不管）
    X, _ = fk(bvh, q, p)
    h = heading(bvh, X)
    f = np.array([math.sin(h[0]), 0, math.cos(h[0])])
    r = np.array([math.cos(h[0]), 0, -math.sin(h[0])])
    d = p[-1, 0] - p[0, 0]
    lat = d @ r
    p[:, 0] -= u * (lat * r + np.array([0, d[1], 0]))
    return q, p


def fold_spine(bvh, q, ref):
    """Spine3 并进 Spine2、Neck1 并进 Neck：子骨骼的全局转动不变，被丢掉的那节停在基准姿势 ref"""
    I = bvh.idx
    q = q.copy()
    for par, mid in (('Spine2', 'Spine3'), ('Neck', 'Neck1')):
        a, m = I[par], I[mid]
        q[:, a] = qnorm(qmul(qmul(q[:, a], q[:, m]), qinv(ref[m])[None]))
        q[:, m] = ref[m][None]
    return q


def lowpass_quat(q, k):
    """每个关节的旋转做滑动平均（当作「不摆动」的那部分）"""
    out = np.empty_like(q)
    n = len(q)
    for i in range(n):
        a, b = max(0, i - k // 2), min(n, i + k // 2 + 1)
        out[i] = qmean(q[a:b]) if q.ndim == 2 else np.stack([qmean(q[a:b, j]) for j in range(q.shape[1])])
    return out


def trunk_pitch(bvh, X):
    """上身（髋→头）平均往前倾多少度"""
    h = heading(bvh, X)
    d = X[:, bvh.idx['Head']] - X[:, 0]
    fwd = d[:, 0] * np.sin(h) + d[:, 2] * np.cos(h)
    return float(np.degrees(np.arctan2(fwd, d[:, 1])).mean())


def set_trunk_pitch(bvh, q, p, target):
    """转 Spine（绕身体右方轴），让上身平均前倾等于 target 度"""
    X, G = fk(bvh, q, p)
    cur = trunk_pitch(bvh, X)
    h = heading(bvh, X)
    n = len(q)
    rgt = np.stack([np.cos(h), np.zeros(n), -np.sin(h)], 1)
    j = bvh.idx['Spine']
    par = bvh.parent[j]
    q = q.copy()
    q[:, j] = qnorm(qmul(qinv(G[:, par]), qmul(qaxis(rgt, np.radians(target - cur)), G[:, j])))
    print(f'[loco]   上身前倾 {cur:.1f} → {target:.1f} 度', flush=True)
    return q


def damp_arms(bvh, q, k):
    """手臂（上臂、前臂）的摆动收到 k 倍（相对整个循环的平均姿势）"""
    I = bvh.idx
    q = q.copy()
    for side in ('Left', 'Right'):
        for jn in (side + 'Arm', side + 'ForeArm'):
            j = I[jn]
            m = np.repeat(qmean(q[:, j])[None], len(q), 0)
            q[:, j] = qnorm(qmul(qpow(qmul(q[:, j], qinv(m)), k), m))
    return q


def feminize(bvh, q, p, cyclic, pelvis=True, leg_w=None):
    """改成女生轻巧的走法（见文件头）。cyclic：整段是一个循环（摆动的「平均」取整段），否则取 1.2 秒滑动平均。
    leg_w：{'Left': 每帧权重, 'Right': …}，两脚往中线收的程度（不给就是全收）"""
    I = bvh.idx
    q = q.copy()
    p = p.copy()
    n = len(q)

    def mean_of(j):
        if cyclic:
            return np.repeat(qmean(q[:, j])[None], n, 0)
        return lowpass_quat(q[:, j], int(1.2 * FPS))

    X, G = fk(bvh, q, p)
    # 1. 手臂摆幅收到 6 成、前臂到 7 成，肘再弯 12 度（前臂绕自己的弯曲轴），上臂往身体收 4 度
    for side, sg in (('Left', 1), ('Right', -1)):
        for jn, k in ((side + 'Arm', 0.6), (side + 'ForeArm', 0.7)):
            j = I[jn]
            m = mean_of(j)
            dev = qmul(q[:, j], qinv(m))
            q[:, j] = qnorm(qmul(qpow(dev, k), m))
    X, G = fk(bvh, q, p)
    for side, sg in (('Left', -1), ('Right', 1)):
        ua, fa, hd = I[side + 'Arm'], I[side + 'ForeArm'], I[side + 'Hand']
        # 肘弯曲轴（世界）：上臂 × 前臂；平均方向作参照
        u = X[:, fa] - X[:, ua]
        v = X[:, hd] - X[:, fa]
        ax = np.cross(u, v)
        bad = np.linalg.norm(ax, axis=1) < 1e-4
        # 手臂几乎伸直时用身体右方（肘往前弯）
        rgt = -left_dir(bvh, X)
        ax[bad] = rgt[bad]
        ax /= np.linalg.norm(ax, axis=1, keepdims=True)
        bend = qaxis(ax, np.radians(12.0))
        # 新的前臂全局 = bend · 旧全局 → 局部 = 父全局⁻¹ · 新全局
        newG = qmul(bend, G[:, fa])
        q[:, fa] = qnorm(qmul(qinv(G[:, ua]), newG))
        # 上臂往身体收：绕身体前方轴转
        X2, G2 = fk(bvh, q, p)
        h = heading(bvh, X2)
        fwd = np.stack([np.sin(h), np.zeros(n), np.cos(h)], 1)
        add = qaxis(fwd, np.radians(4.0) * sg)
        par = bvh.parent[ua]
        newG = qmul(add, G2[:, ua])
        q[:, ua] = qnorm(qmul(qinv(G2[:, par]), newG))
    # 2. 两脚落点往中线收：大腿绕身体前方轴往里转 2 度，脚掌的全局朝向保持（不歪）
    X, G = fk(bvh, q, p)
    h = heading(bvh, X)
    fwd = np.stack([np.sin(h), np.zeros(n), np.cos(h)], 1)
    for side, sg in (('Left', -1), ('Right', 1)):
        th, sh, ft = I[side + 'UpLeg'], I[side + 'Leg'], I[side + 'Foot']
        par = bvh.parent[th]
        w = np.ones(n) if leg_w is None else leg_w[side]
        add = qaxis(fwd, np.radians(2.2) * sg * w)
        newTh = qmul(add, G[:, th])
        q[:, th] = qnorm(qmul(qinv(G[:, par]), newTh))
        newSh = qmul(newTh, q[:, sh])
        q[:, ft] = qnorm(qmul(qinv(newSh), G[:, ft]))
    # 3. 骨盆左右摆和扭转大 1.4 倍，脊柱第一节反向补回来（上身不跟着晃）。转身的片段不做（转身时「平均」跟不上，会把转身也放大）
    hips, sp = I['Hips'], I['Spine']
    if not pelvis:
        return _upright(bvh, q, p, I, n)
    m = mean_of(hips)
    dev = qmul(q[:, hips], qinv(m))          # 世界里的偏差（含前倾的起伏）
    # 只放大偏差里绕前方轴、竖直轴的部分：把偏差变到身体朝向坐标里拆
    X, G = fk(bvh, q, p)
    h = heading(bvh, X)
    yawq = qaxis([0, 1, 0], h)
    dl = qmul(qmul(qinv(yawq), dev), yawq)  # 身体坐标：x 右、y 上、z 前
    e = zyx_from_q(dl)                       # z（前方轴=侧倾）、y（竖直=扭转）、x（俯仰）
    e2 = e.copy()
    e2[:, 0] *= 1.4
    e2[:, 1] *= 1.4
    dl2 = q_from_zyx(e2)
    dev2 = qmul(qmul(yawq, dl2), qinv(yawq))
    newHip = qnorm(qmul(dev2, m))
    extra = qmul(newHip, qinv(q[:, hips]))     # 世界里多转了多少
    q[:, hips] = newHip
    # 脊柱：Spine 的全局保持原样（上身不晃）→ 局部 = 新髋⁻¹ · 旧全局
    q[:, sp] = qnorm(qmul(qinv(newHip), G[:, sp]))
    # 腿跟着骨盆转了：大腿的全局也保持原样（脚的位置不变，只是骨盆在动）
    for side in ('Left', 'Right'):
        th = I[side + 'UpLeg']
        q[:, th] = qnorm(qmul(qinv(newHip), G[:, th]))
    return _upright(bvh, q, p, I, n)


def _upright(bvh, q, p, I, n):
    # 4. 上身挺一点、头抬一点
    X, G = fk(bvh, q, p)
    for jn, deg in (('Spine1', -2.0), ('Neck', -2.0)):
        j = I[jn]
        h = heading(bvh, X)
        rgt = np.stack([np.cos(h), np.zeros(n), -np.sin(h)], 1)
        par = bvh.parent[j]
        newG = qmul(qaxis(rgt, np.radians(deg)), G[:, j])
        q[:, j] = qnorm(qmul(qinv(G[:, par]), newG))
        X, G = fk(bvh, q, p)
    return q, p


def splice_upper(bvh, q_low, p_low, q_up):
    """下身（髋、腿）用 q_low，上身（脊柱以上、手臂）用 q_up 的局部旋转（两段同相位、同帧数）"""
    I = bvh.idx
    q = q_low.copy()
    upper = set()
    for j, n in enumerate(bvh.names):
        k = j
        while k >= 0:
            if bvh.names[k] == 'Spine':
                upper.add(j)
                break
            k = bvh.parent[k]
    for j in upper:
        q[:, j] = q_up[:, j]
    return q, p_low


def tpose_ref(bvh):
    """基准姿势（FBX 里骨骼的默认姿势，Unity 把它当成人形的 T 字姿势）：100STYLE 骨骼全零转动时腿直、脚平、脊柱头直，
    只有两臂朝上，把锁骨往外放平就是标准的 T 字。不能用动捕的某一帧当基准：那一帧头偏着、手垂着，
    Unity 会把偏着的头当成「正」，套到别的人物上头就歪了。返回 (第 0 帧的通道, 各关节局部旋转)"""
    J = bvh.J
    q = np.tile(np.array([1.0, 0, 0, 0]), (J, 1))
    for side, x in (('Left', 1.0), ('Right', -1.0)):
        j = bvh.idx[side + 'Shoulder']
        d0 = bvh.offset[bvh.idx[side + 'Arm']]
        d0 = d0 / np.linalg.norm(d0)
        d1 = np.array([x, 0.0, 0.0])
        ax = np.cross(d0, d1)
        ang = math.atan2(np.linalg.norm(ax), d0 @ d1)
        q[j] = qaxis(ax / np.linalg.norm(ax), ang)
    # 脚：骨骼全零时踝→脚趾是水平的，可真人平踩在地上时踝比脚趾根高 5 厘米，踝→脚趾往下斜约 21 度（走路踩稳时左 -20、右 -22，
    # 站着的待机片段的基准也是 -22 左右）。Unity 把基准当成「脚平踩着」，所以基准里脚也要往下斜 21 度、脚趾再抬回水平，
    # 不然走路时脚掌整个往下扣 21 度（脚跟离地）
    for side in ('Left', 'Right'):
        q[bvh.idx[side + 'Foot']] = qaxis([1.0, 0.0, 0.0], math.radians(FOOT_PITCH))
        q[bvh.idx[side + 'ToeBase']] = qaxis([1.0, 0.0, 0.0], -math.radians(FOOT_PITCH))
    row = np.zeros((J, 6))
    row[:, :3] = bvh.offset * 100.0
    row[0, :3] = [0.0, bvh.offset[0, 1] * 100.0, 0.0]
    row[:, 3:] = zyx_from_q(q)
    return row.reshape(-1), q


def to_origin(bvh, q, p):
    """整段挪到原点、转成一开始朝 +z（第 0 帧的 T 字基准就站在原点朝 +z）：
    基准和片段第一帧之间不能差出几米、转一大圈，不然 Unity 压缩根运动曲线时片段开头那一下会冲出一个尖（根运动多算 2 倍，量出来的步子/根运动就不准）"""
    X, _ = fk(bvh, q, p)
    h0 = heading(bvh, X)[0]
    rot = qaxis([0.0, 1.0, 0.0], -h0)
    q = q.copy()
    p = p.copy()
    q[:, 0] = qnorm(qmul(rot[None].repeat(len(q), 0), q[:, 0]))
    d = p[:, 0] - np.array([p[0, 0, 0], 0.0, p[0, 0, 2]])
    p[:, 0] = qrot(rot[None].repeat(len(q), 0), d)
    return q, p


# 片段前后各多导几帧（不算在片段里，CharacterImport 的 WalkPad 要和它一样）：
# Unity 导入时按逐帧采样再连成曲线，片段第一帧的切线是按它前面那一帧算的。前面紧挨着的要是第 0 帧的 T 字基准，
# 第一帧和第二帧之间的曲线就往 T 字那边鼓出去（手臂一帧跳 3–4 厘米，每次循环接缝、每次从开头进停步都会跳一下）。
# 循环片段前面补它自己末尾的几帧、后面补开头的几帧（接得上）；停步、转身按头尾两帧的速度往外延
PAD = 3


def pad_ends(q, p, cyclic, pad=PAD):
    """前后各补 pad 帧（见 PAD）。q: (n, J, 4)，p: (n, J, 3)"""
    n = len(q) - 1
    if cyclic:
        disp = p[-1, 0] - p[0, 0]
        disp[1] = 0
        qa, qb = q[n - pad:n], q[1:pad + 1]
        pa, pb = p[n - pad:n].copy(), p[1:pad + 1].copy()
        pa[:, 0] -= disp
        pb[:, 0] += disp
    else:
        k = np.arange(pad, 0, -1, dtype=float)
        da = qmul(qinv(q[1]), q[0])                    # 往前一帧 = q0 · (q1⁻¹·q0)… 按局部转动外推
        db = qmul(qinv(q[-2]), q[-1])
        qa = np.stack([qnorm(qmul(q[0], qpow(da, kk))) for kk in k])
        qb = np.stack([qnorm(qmul(q[-1], qpow(db, kk))) for kk in k[::-1]])
        pa = np.stack([p[0] + (p[0] - p[1]) * kk for kk in k])
        pb = np.stack([p[-1] + (p[-1] - p[-2]) * kk for kk in k[::-1]])
    return np.concatenate([qa, q, qb]), np.concatenate([pa, p, pb])


def write_bvh(bvh, path, q, p, ref_row):
    """写 BVH：第 0 帧是基准姿势（ref_row，原始通道），之后是加工过的帧。非根关节的位置通道固定成骨骼长度（不带位移动画）"""
    n = len(q)
    e = zyx_from_q(q)
    e = np.degrees(np.unwrap(np.radians(e), axis=0))
    rows = np.zeros((n, bvh.J, 6))
    rows[:, :, :3] = bvh.offset[None] * 100.0
    rows[:, 0, :3] = p[:, 0] * 100.0
    rows[:, :, 3:] = e
    rows = rows.reshape(n, -1)
    ref = ref_row.copy().reshape(bvh.J, 6)
    ref[1:, :3] = bvh.offset[1:] * 100.0
    allrows = np.vstack([ref.reshape(1, -1), rows])
    with open(path, 'w') as f:
        f.write(bvh.header)
        f.write(f'MOTION\nFrames: {len(allrows)}\nFrame Time: {1 / FPS:.6f}\n')
        np.savetxt(f, allrows, fmt='%.5f')
    return len(allrows)


# ───────────── 片段清单 ─────────────
# 周期：从给的时刻附近的左脚着地起，一个完整步态。tscale < 1 是加快步频
CYCLES = [
    # 名字, 下身来源(文件, 时刻), 上身来源(文件, 时刻) 或 None, 女生化, 时间缩放
    # 慢走（约 0.65 髋高/秒）：Monk 的腿和骨盆（真人慢走，步子小、步频慢），上身换 Neutral 同相位的（Monk 两手一直合在身前），
    # 手臂摆幅再收到 7 成（走得慢手摆得小）。摇杆推一点点、香客慢慢逛时用它，不再拿正常步子慢放（像慢镜头）
    ('Walk_M_Slow', ('Monk_FW', 23.38), ('Neutral_FW', 34.63), False, 1.0),
    ('Walk_F_Slow', ('Monk_FW', 23.38), ('Neutral_FW', 34.63), True, 0.93),
    ('Walk_M', ('Neutral_FW', 34.63), None, False, 1.0),
    ('Walk_M_Fast', ('Neutral_FW', 9.67), None, False, 1.0),
    ('Walk_M_Brisk', ('GracefulArms_FW', 12.25), ('Neutral_FW', 9.67), False, 1.0),
    ('Walk_F', ('Neutral_FW', 34.63), None, True, 0.93),
    ('Walk_F_Fast', ('Neutral_FW', 9.67), None, True, 0.93),
    ('Walk_F_Brisk', ('GracefulArms_FW', 12.25), ('Neutral_FW', 9.67), True, 0.93),
    ('Walk_Monk', ('Monk_FW', 23.38), None, False, 1.0),
]
# 停步：从左脚着地（这时进来对应步态相位 0）开始，右脚再迈一步，左脚收拢，站住。右脚版由 Unity 导入时镜像得到（Walk_Stop 的 _Mirror）
# 转身起步：站着 → 往左/右转约 90 度同时迈出第一步 → 右脚着地（交给步态，相位 0.5）
SEGMENTS = [
    # 名字, 文件, 起, 止（秒）, 女生化, 类型
    ('Walk_Stop', 'Neutral_FW', 96.985, 98.75, False, 'stop'),
    ('Walk_Stop_F', 'Neutral_FW', 96.985, 98.75, True, 'stop'),
    ('Walk_TurnStart', 'Neutral_FW', 98.70, 100.035, False, 'turn'),
    ('Walk_TurnStart_F', 'Neutral_FW', 98.70, 100.035, True, 'turn'),
]


def build(sheet_dir=None, fbx=True):
    neutral = Take.get('Neutral_FW')
    ref_row, ref_q = tpose_ref(neutral.b)
    tmp = tempfile.mkdtemp(prefix='yj_loco_')
    meta = {'clips': [], 'pad': PAD}
    lst = []
    for name, low, up, fem, tsc in CYCLES:
        tk = Take.get(low[0])
        a, c, b = tk.cycle(low[1])
        q, p, T = warp_cycle(tk, a, c, b, tsc)
        if up is not None:
            tu = Take.get(up[0])
            a2, c2, b2 = tu.cycle(up[1])
            n = len(q) - 1
            u = np.arange(n + 1) / n
            src = np.where(u < 0.5, a2 + (c2 - a2) * (u / 0.5), c2 + (b2 - c2) * ((u - 0.5) / 0.5))
            qu, _ = resample(tu.q, tu.p, src)
            q, p = splice_upper(tk.b, q, p, qu)
            if name.endswith('_Slow'):
                q = damp_arms(tk.b, q, 0.7)
                # Monk 的骨盆往前倾得多，接上 Neutral 的脊柱整个上身就往前趴：按 Neutral 那段上身的平均前倾扶正
                Xu, _ = fk(tu.b, *resample(tu.q, tu.p, src))
                q = set_trunk_pitch(tk.b, q, p, trunk_pitch(tu.b, Xu))
        drift = path_drift(tk.b, q, p)
        q, p = straighten(tk.b, q, p, drift)
        q, p = close_loop(tk.b, q, p)
        q = fold_spine(tk.b, q, ref_q)
        if fem:
            q, p = feminize(tk.b, q, p, True)
            q, p = close_loop(tk.b, q, p)
        X, G = fk(tk.b, q, p)
        h = heading(tk.b, X)
        dist = np.linalg.norm((X[-1, 0] - X[0, 0])[[0, 2]])
        info = dict(name=name, kind='cycle', length=T, speed=dist / T / HIP, period=T,
                    src=f'{low[0]} {a * tk.ft:.3f}-{b * tk.ft:.3f}' + (f' 上身 {up[0]}' if up else ''),
                    rStrike=0.5, drift=math.degrees(drift))
        out = os.path.join(tmp, name + '.bvh')
        q, p = to_origin(tk.b, q, p)
        nf = write_bvh(tk.b, out, *pad_ends(q, p, True), ref_row)
        lst.append((name, out, nf))
        meta['clips'].append(info)
        print(f'[loco] {name}: 周期 {T:.3f} 秒，{dist / T / HIP:.3f} 髋高/秒（{dist / T:.3f} 米/秒），原来偏 {math.degrees(drift):+.1f} 度 → 已拉直；来源 {info["src"]}', flush=True)
        if sheet_dir:
            sheet(tk.b, q, p, os.path.join(sheet_dir, name + '.png'), 10)
    for name, fn, t0, t1, fem, kind in SEGMENTS:
        tk = Take.get(fn)
        q, p, T, src = segment(tk, t0, t1)
        q = fold_spine(tk.b, q, ref_q)
        X, G = fk(tk.b, q, p)
        h = heading(tk.b, X)
        if kind == 'stop':
            # 停步走得不直的那几度扣掉
            q, p = straighten(tk.b, q, p, h[-1] - h[0])
            # 路线本身也往右弯（最后一步往右落、收脚，髋往右挪了 7 厘米）：整段按时间均匀往回转，停下来的地方落回起步的那条线上
            # （不然游戏里停步时人往旁边横着挪，像螃蟹）
            X, G = fk(tk.b, q, p)
            h0 = heading(tk.b, X)[0]
            d = X[-1, 0] - X[0, 0]
            fwd = d @ np.array([math.sin(h0), 0, math.cos(h0)])
            lat = d @ np.array([math.cos(h0), 0, -math.sin(h0)])
            q, p = straighten(tk.b, q, p, math.atan2(lat, fwd))
        if fem and kind == 'stop':
            # 停步：进来时和女生步态一样（两脚往中线收），最后站住时是正常的站姿宽度（和待机一样，不然淡到待机时两只脚往外滑 3 厘米）。
            # 每只脚只在它最后一次迈步、脚在空中时放开（踩在地上的时候改腿的角度，脚会在地上滑）；骨盆摆动不放大（站住时没有「平均」可言）
            tt = np.arange(len(q)) / FPS
            ramp = lambda a, b: 1 - np.clip((tt - a) / (b - a), 0, 1) ** 2 * (3 - 2 * np.clip((tt - a) / (b - a), 0, 1))
            q, p = feminize(tk.b, q, p, False, pelvis=False, leg_w={'Right': ramp(0.25, 0.6), 'Left': ramp(0.9, 1.15)})
        elif fem:
            q, p = feminize(tk.b, q, p, False, pelvis=kind != 'turn')
        X, G = fk(tk.b, q, p)
        h = heading(tk.b, X)
        # 事件（片段内的秒）：着地
        L = [(s - src[0]) * tk.ft for s in tk.L if src[0] - 1 <= s <= src[-1] + 2]
        R = [(s - src[0]) * tk.ft for s in tk.R if src[0] - 1 <= s <= src[-1] + 2]
        def dedupe(v):
            out = []
            for x in sorted(v):
                if -0.02 <= x <= T + 0.03 and (not out or x - out[-1] > 0.25):
                    out.append(round(min(x, T), 3))
            return out
        L, R = dedupe(L), dedupe(R)
        hip = X[:, 0]
        # 走过的距离按时间均分 32 份的累计比例（游戏里按它算停步还要走多远）
        cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(hip[:, [0, 2]], axis=0), axis=1))])
        prof = np.interp(np.linspace(0, T, 33), np.arange(len(cum)) / FPS, cum / max(cum[-1], 1e-6))
        # 着地的时刻（脚步声）：每只脚从「没踩地」变成「踩地」
        steps = []
        for side in ('Left', 'Right'):
            c = contacts(tk.b, X, 1 / FPS, side)
            c = smooth(c.astype(float), 5) > 0.5
            for i in range(1, len(c)):
                if c[i] and not c[i - 1] and i / FPS > 0.05:
                    steps.append(round(i / FPS, 3))
        steps.sort()
        sp = np.linalg.norm(np.gradient(hip[:, [0, 2]], 1 / FPS, axis=0), axis=1)
        sp = smooth(sp, 9)
        still = next((i / FPS for i in range(len(sp)) if i / FPS > 0.6 and sp[i:].max() < 0.1), T)
        info = dict(name=name, kind=kind, length=T, lStrikes=L, rStrikes=R, steps=steps, dist=[round(float(x), 4) for x in prof],
                    total=float(cum[-1]) / HIP, src=f'{fn} {t0:.3f}-{t1:.3f}')
        if kind == 'stop':
            info.update(entryEnd=R[0] if R else 0.65, still=still, speed=float(sp[:10].mean() / HIP))
        else:
            ld = left_dir(tk.b, X)
            f_end = np.array([math.sin(h[-1]), 0, math.cos(h[-1])])
            yaw = yaw_of(q[:, 0])
            turn = math.degrees(yaw[-6:].mean() - yaw[:6].mean())
            info.update(angle=abs(turn), left=bool(f_end @ ld[0] > 0), exitPhase=0.5, speed=float(sp[-10:].mean() / HIP))
        out = os.path.join(tmp, name + '.bvh')
        q, p = to_origin(tk.b, q, p)
        nf = write_bvh(tk.b, out, *pad_ends(q, p, False), ref_row)
        lst.append((name, out, nf))
        meta['clips'].append(info)
        print(f'[loco] {name}: {T:.2f} 秒；{json.dumps({k: v for k, v in info.items() if k not in ("name", "src")}, ensure_ascii=False)}', flush=True)
        if sheet_dir:
            sheet(tk.b, q, p, os.path.join(sheet_dir, name + '.png'), 12)
    if fbx:
        clip_list = os.path.join(tmp, 'clips.txt')
        with open(clip_list, 'w') as f:
            for name, path, nf in lst:
                # Blender 导入 BVH 时第 i 帧放在 Blender 的第 i+1 帧：第 0 帧（基准姿势）在 1，片段从 2 开始
                f.write(f'{name} {path} {2 / FPS:.6f} {nf / FPS:.6f}\n')
        r = subprocess.run([BLENDER, '-b', '--factory-startup', '--python', os.path.join(HERE, 'convert.py'), '--', clip_list, '--ref0'],
                           capture_output=True, text=True)
        for line in r.stdout.splitlines():
            if line.startswith('[mocap]') or 'Error' in line or 'Traceback' in line:
                print(line)
        if r.returncode != 0:
            print(r.stderr[-2000:])
            sys.exit(1)
        with open(os.path.join(OUT, 'Locomotion.json'), 'w') as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
        print('[loco] 写了', os.path.join(OUT, 'Locomotion.json'))
    return meta


def sheet(bvh, q, p, out, n):
    """火柴人逐帧图：上面侧面（按起始朝向），下面脚印俯视"""
    from PIL import Image, ImageDraw
    X, G = fk(bvh, q, p)
    h0 = heading(bvh, X)[0]
    f = np.array([math.sin(h0), 0, math.cos(h0)])
    r = np.array([math.cos(h0), 0, -math.sin(h0)])
    W, H = 170, 300
    img = Image.new('RGB', (W * n, H + 140), (250, 250, 248))
    dr = ImageDraw.Draw(img)
    org = X[0, 0].copy()
    org[1] = 0
    floor = X[:, :, 1].min()
    for k in range(n):
        i = int(round((len(q) - 1) * k / max(1, n - 1)))
        Q = X[i] - org
        fw, up = Q @ f, Q[:, 1] - floor
        cx = k * W + W / 2 - fw[0] * 160
        for j, par in enumerate(bvh.parent):
            nm = bvh.names[j]
            if par < 0 or any(s in nm for s in ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky', 'End')):
                continue
            col = (200, 60, 50) if 'Left' in nm else (50, 90, 200) if 'Right' in nm else (40, 40, 40)
            dr.line([(cx + fw[par] * 160, H - 10 - up[par] * 160), (cx + fw[j] * 160, H - 10 - up[j] * 160)], fill=col, width=2)
        dr.line([(k * W, H - 10), (k * W + W, H - 10)], fill=(160, 160, 160))
        dr.text((k * W + 3, 3), f'{i / FPS:.2f}s', fill=(0, 0, 0))
        yy = H + 70
        for s, col in (('Left', (200, 60, 50)), ('Right', (50, 90, 200))):
            a, t = Q[bvh.idx[s + 'Foot']], Q[bvh.idx[s + 'ToeBase']]
            dr.line([(k * W + W / 2 + (a @ r) * 160, yy - (a @ f - fw[0]) * 160), (k * W + W / 2 + (t @ r) * 160, yy - (t @ f - fw[0]) * 160)], fill=col, width=3)
    img.save(out)


if __name__ == '__main__':
    args = sys.argv[1:]
    sd = args[args.index('--sheet') + 1] if '--sheet' in args else None
    if sd:
        os.makedirs(sd, exist_ok=True)
    build(sd, '--no-fbx' not in args)
