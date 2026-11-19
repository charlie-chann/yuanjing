"""用距离场（SDF）雕形体：numpy 里拼椭球、胶囊、圆台……再用 Blender 自带的 openvdb 抽成网格。佛像（statues.py）用。

做法：
- 每个形体是一个 Node，能报自己的包围盒（bounds）、能在一批点上算「到表面的有符号距离」（ev，里负外正）。
- Union / Sub / Inter 是平滑的并、减、交（k 是过渡圆角的大小，0 就是硬边）。并的时候每个子形体只在自己的包围盒里算，
  所以几百个小零件也不慢。
- evaluate() 在一块规则网格上算出整块距离场，mesh() 用 openvdb 的 volumeToMesh 抽出四边形网格，
  decimate() 交给 Blender 的减面（collapse），sample()/normals() 在距离场上取值、取法线（比网格自己算的法线顺）。
- 距离场不一定处处精确（褶皱是直接加在距离上的起伏），只要表面附近大致对、梯度不太离谱就行。
"""
import math

import numpy as np

BIG = np.float32(1e3)
_MARGIN = [0.01]          # 子形体在自己包围盒外多算的一圈（evaluate 时按体素大小设）


def smin(a, b, k):
    """平滑并（k=0 就是 min）"""
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * (k * 0.25)


def smax(a, b, k):
    if k <= 0:
        return np.maximum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.maximum(a, b) + h * h * (k * 0.25)


def V(*a):
    if len(a) == 1:
        a = a[0]
    return np.asarray(a, dtype=np.float64)


def rot(axis_x=None, axis_y=None, axis_z=None):
    """由两根给定的轴（局部 x/y/z 在世界里的方向）补出一个正交的旋转矩阵（列是局部轴）"""
    ax = [None if v is None else V(v) / np.linalg.norm(v) for v in (axis_x, axis_y, axis_z)]
    if ax[2] is not None and ax[0] is not None:
        z = ax[2]
        x = ax[0] - z * ax[0].dot(z)
        x /= np.linalg.norm(x)
        y = np.cross(z, x)
    elif ax[2] is not None and ax[1] is not None:
        z = ax[2]
        y = ax[1] - z * ax[1].dot(z)
        y /= np.linalg.norm(y)
        x = np.cross(y, z)
    elif ax[0] is not None and ax[1] is not None:
        x = ax[0]
        y = ax[1] - x * ax[1].dot(x)
        y /= np.linalg.norm(y)
        z = np.cross(x, y)
    else:
        raise ValueError('rot 至少给两根轴')
    return np.stack([x, y, z], axis=1)


def euler(rx=0.0, ry=0.0, rz=0.0):
    """XYZ 顺序的欧拉角（弧度）→ 旋转矩阵（和 Blender 的 Euler 'XYZ' 一样）"""
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def _local(X, Y, Z, c, R):
    dx, dy, dz = X - np.float32(c[0]), Y - np.float32(c[1]), Z - np.float32(c[2])
    if R is None:
        return dx, dy, dz
    R = R.astype(np.float32)
    return (R[0, 0] * dx + R[1, 0] * dy + R[2, 0] * dz,
            R[0, 1] * dx + R[1, 1] * dy + R[2, 1] * dz,
            R[0, 2] * dx + R[1, 2] * dy + R[2, 2] * dz)


def _separable(X, Y, Z):
    return X.ndim == 3 and X.shape[1] == 1 and X.shape[2] == 1 and Y.shape[0] == 1 and Y.shape[2] == 1 \
        and Z.shape[0] == 1 and Z.shape[1] == 1


def _shape(X, Y, Z):
    return np.broadcast_shapes(X.shape, Y.shape, Z.shape)


class Node:
    lo = None
    hi = None

    def bounds(self):
        return self.lo, self.hi

    def ev(self, X, Y, Z):
        raise NotImplementedError

    # 小写法：a | b 并、a - b 减、a & b 交（硬边）
    def __or__(self, o):
        return Union([self, o])

    def __sub__(self, o):
        return Sub(self, o)

    def __and__(self, o):
        return Inter(self, o)


class Sphere(Node):
    def __init__(self, c, r):
        self.c, self.r = V(c), float(r)
        self.lo, self.hi = self.c - r, self.c + r

    def ev(self, X, Y, Z):
        dx, dy, dz = _local(X, Y, Z, self.c, None)
        return np.sqrt(dx * dx + dy * dy + dz * dz) - np.float32(self.r)


class Ellipsoid(Node):
    """椭球（近似距离，表面附近准）。r = 三个半轴，R = 旋转（列是局部轴）"""

    def __init__(self, c, r, R=None):
        self.c, self.r, self.R = V(c), V(r), R
        m = float(np.max(self.r))
        if R is None:
            self.lo, self.hi = self.c - self.r, self.c + self.r
        else:
            ext = np.abs(R) @ self.r
            self.lo, self.hi = self.c - ext, self.c + ext

    def ev(self, X, Y, Z):
        x, y, z = _local(X, Y, Z, self.c, self.R)
        r = self.r.astype(np.float32)
        k0 = np.sqrt((x / r[0]) ** 2 + (y / r[1]) ** 2 + (z / r[2]) ** 2)
        k1 = np.sqrt((x / (r[0] * r[0])) ** 2 + (y / (r[1] * r[1])) ** 2 + (z / (r[2] * r[2])) ** 2)
        return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


class RoundCone(Node):
    """两头是球、中间是圆台（胶囊的一般形式）。a、b 两个端点，ra、rb 两头的半径"""

    def __init__(self, a, b, ra, rb=None):
        self.a, self.b = V(a), V(b)
        self.ra = float(ra)
        self.rb = float(ra if rb is None else rb)
        r = max(self.ra, self.rb)
        self.lo = np.minimum(self.a - self.ra, self.b - self.rb)
        self.hi = np.maximum(self.a + self.ra, self.b + self.rb)
        ba = self.b - self.a
        self.l2 = float(ba.dot(ba))
        self.degenerate = math.sqrt(self.l2) <= abs(self.ra - self.rb) + 1e-6

    def ev(self, X, Y, Z):
        a, b, r1, r2 = self.a, self.b, self.ra, self.rb
        if self.degenerate:
            c, r = (a, r1) if r1 >= r2 else (b, r2)
            dx, dy, dz = X - np.float32(c[0]), Y - np.float32(c[1]), Z - np.float32(c[2])
            return np.sqrt(dx * dx + dy * dy + dz * dz) - np.float32(r)
        ba = (b - a).astype(np.float32)
        l2 = np.float32(self.l2)
        rr = np.float32(r1 - r2)
        a2 = l2 - rr * rr
        il2 = np.float32(1.0 / self.l2)
        px, py, pz = X - np.float32(a[0]), Y - np.float32(a[1]), Z - np.float32(a[2])
        y = px * ba[0] + py * ba[1] + pz * ba[2]
        z = y - l2
        qx, qy, qz = px * l2 - ba[0] * y, py * l2 - ba[1] * y, pz * l2 - ba[2] * y
        x2 = qx * qx + qy * qy + qz * qz
        y2 = y * y * l2
        z2 = z * z * l2
        k = np.sign(rr) * rr * rr * x2
        d3 = (np.sqrt(np.maximum(x2 * a2 * il2, 0)) + y * rr) * il2 - np.float32(r1)
        d1 = np.sqrt(x2 + z2) * il2 - np.float32(r2)
        d2 = np.sqrt(x2 + y2) * il2 - np.float32(r1)
        return np.where(np.sign(z) * a2 * z2 > k, d1, np.where(np.sign(y) * a2 * y2 < k, d2, d3))


class Box(Node):
    """圆角方块。half = 半尺寸，rnd = 圆角半径"""

    def __init__(self, c, half, R=None, rnd=0.0):
        self.c, self.half, self.R, self.rnd = V(c), V(half), R, float(rnd)
        ext = self.half if R is None else np.abs(R) @ self.half
        self.lo, self.hi = self.c - ext, self.c + ext

    def ev(self, X, Y, Z):
        x, y, z = _local(X, Y, Z, self.c, self.R)
        h = self.half.astype(np.float32) - np.float32(self.rnd)
        qx, qy, qz = np.abs(x) - h[0], np.abs(y) - h[1], np.abs(z) - h[2]
        out = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2 + np.maximum(qz, 0) ** 2)
        inn = np.minimum(np.maximum(qx, np.maximum(qy, qz)), 0)
        return out + inn - np.float32(self.rnd)


class Torus(Node):
    """圆环：局部 xy 平面里，主半径 R0，管半径 r"""

    def __init__(self, c, R0, r, R=None):
        self.c, self.R0, self.r, self.R = V(c), float(R0), float(r), R
        e = R0 + r
        ext = V(e, e, r) if R is None else np.abs(R) @ V(e, e, r)
        self.lo, self.hi = self.c - ext, self.c + ext

    def ev(self, X, Y, Z):
        x, y, z = _local(X, Y, Z, self.c, self.R)
        q = np.sqrt(x * x + y * y) - np.float32(self.R0)
        return np.sqrt(q * q + z * z) - np.float32(self.r)


class Plane(Node):
    """半空间：n 指向外面（距离为正的一侧）"""

    def __init__(self, p, n):
        self.p, self.n = V(p), V(n) / np.linalg.norm(n)
        self.lo, self.hi = None, None

    def ev(self, X, Y, Z):
        n = self.n.astype(np.float32)
        return (X - np.float32(self.p[0])) * n[0] + (Y - np.float32(self.p[1])) * n[1] + (Z - np.float32(self.p[2])) * n[2]


class Func(Node):
    """自己写的距离函数 fn(X, Y, Z)，给一个包围盒（None 表示到处都要算）"""

    def __init__(self, fn, lo=None, hi=None):
        self.fn = fn
        self.lo = None if lo is None else V(lo)
        self.hi = None if hi is None else V(hi)

    def ev(self, X, Y, Z):
        return self.fn(X, Y, Z)


def _sub_block(X, Y, Z, lo, hi, pad):
    """可分离的坐标（X 是 (nx,1,1)…）里，取出包围盒 [lo-pad, hi+pad] 覆盖的那一段"""
    xs, ys, zs = X[:, 0, 0], Y[0, :, 0], Z[0, 0, :]
    sl = []
    for arr, a, b in ((xs, lo[0] - pad, hi[0] + pad), (ys, lo[1] - pad, hi[1] + pad), (zs, lo[2] - pad, hi[2] + pad)):
        i0 = int(np.searchsorted(arr, a, 'left'))
        i1 = int(np.searchsorted(arr, b, 'right'))
        if i1 <= i0:
            return None
        sl.append(slice(i0, i1))
    return tuple(sl)


class Union(Node):
    def __init__(self, kids, k=0.0):
        self.kids = [c for c in kids if c is not None]
        self.k = float(k)
        los = [c.lo for c in self.kids]
        his = [c.hi for c in self.kids]
        if not self.kids or any(l is None for l in los):
            self.lo = self.hi = None
        else:
            self.lo = np.min(los, axis=0) - self.k
            self.hi = np.max(his, axis=0) + self.k

    def add(self, c):
        self.kids.append(c)
        if c.lo is None or self.lo is None and len(self.kids) > 1:
            self.lo = self.hi = None
        elif self.lo is None:
            self.lo, self.hi = c.lo - self.k, c.hi + self.k
        else:
            self.lo = np.minimum(self.lo, c.lo - self.k)
            self.hi = np.maximum(self.hi, c.hi + self.k)
        return c

    def ev(self, X, Y, Z):
        shp = _shape(X, Y, Z)
        acc = np.full(shp, BIG, np.float32)
        sep = _separable(X, Y, Z)
        for c in self.kids:
            if sep and c.lo is not None:
                sl = _sub_block(X, Y, Z, c.lo, c.hi, self.k + _MARGIN[0])
                if sl is None:
                    continue
                v = c.ev(X[sl[0]], Y[:, sl[1]], Z[:, :, sl[2]])
                acc[sl] = smin(acc[sl], v, self.k)
            else:
                acc = smin(acc, c.ev(X, Y, Z), self.k)
        return acc


class Sub(Node):
    """a 减去 b（k 是挖出来的边上的圆角）"""

    def __init__(self, a, b, k=0.0):
        self.a, self.b, self.k = a, b, float(k)
        self.lo, self.hi = a.lo, a.hi

    def ev(self, X, Y, Z):
        acc = np.array(np.broadcast_to(self.a.ev(X, Y, Z), _shape(X, Y, Z)), np.float32)
        b = self.b
        if _separable(X, Y, Z) and b.lo is not None:
            sl = _sub_block(X, Y, Z, b.lo, b.hi, self.k + _MARGIN[0])
            if sl is None:
                return acc
            v = b.ev(X[sl[0]], Y[:, sl[1]], Z[:, :, sl[2]])
            acc[sl] = smax(acc[sl], -v, self.k)
            return acc
        return smax(acc, -b.ev(X, Y, Z), self.k)


class Inter(Node):
    def __init__(self, a, b, k=0.0):
        self.a, self.b, self.k = a, b, float(k)
        if a.lo is None:
            self.lo, self.hi = b.lo, b.hi
        elif b.lo is None:
            self.lo, self.hi = a.lo, a.hi
        else:
            self.lo, self.hi = np.maximum(a.lo, b.lo), np.minimum(a.hi, b.hi)

    def ev(self, X, Y, Z):
        shp = _shape(X, Y, Z)
        if _separable(X, Y, Z) and self.lo is not None:
            out = np.full(shp, BIG, np.float32)
            sl = _sub_block(X, Y, Z, self.lo, self.hi, self.k + _MARGIN[0])
            if sl is None:
                return out
            Xs, Ys, Zs = X[sl[0]], Y[:, sl[1]], Z[:, :, sl[2]]
            out[sl] = smax(self.a.ev(Xs, Ys, Zs), self.b.ev(Xs, Ys, Zs), self.k)
            return out
        return smax(self.a.ev(X, Y, Z), self.b.ev(X, Y, Z), self.k)


class Offset(Node):
    """整体胖一圈（r>0）或瘦一圈"""

    def __init__(self, a, r):
        self.a, self.r = a, float(r)
        self.lo = None if a.lo is None else a.lo - max(0.0, r)
        self.hi = None if a.hi is None else a.hi + max(0.0, r)

    def ev(self, X, Y, Z):
        return self.a.ev(X, Y, Z) - np.float32(self.r)


class Displace(Node):
    """表面起伏：距离加上 fn(X, Y, Z)（褶皱、纹理）。amp 是起伏的最大幅度（用来放大包围盒）。
    box=(lo, hi)：只在这块盒子里加起伏（脸上的浮雕只算脸前面那一块，省时间）"""

    def __init__(self, a, fn, amp, box=None):
        self.a, self.fn, self.amp = a, fn, float(amp)
        self.lo = None if a.lo is None else a.lo - amp
        self.hi = None if a.hi is None else a.hi + amp
        self.box = None if box is None else (V(box[0]), V(box[1]))

    def ev(self, X, Y, Z):
        d = self.a.ev(X, Y, Z)
        if self.box is None:
            return d + self.fn(X, Y, Z)
        d = np.array(np.broadcast_to(d, _shape(X, Y, Z)), np.float32)
        if _separable(X, Y, Z):
            sl = _sub_block(X, Y, Z, self.box[0], self.box[1], 0.0)
            if sl is None:
                return d
            d[sl] += self.fn(X[sl[0]], Y[:, sl[1]], Z[:, :, sl[2]])
            return d
        lo, hi = self.box
        m = (X >= lo[0]) & (X <= hi[0]) & (Y >= lo[1]) & (Y <= hi[1]) & (Z >= lo[2]) & (Z <= hi[2])
        m = np.broadcast_to(m, d.shape)
        if np.any(m):
            Xb, Yb, Zb = (np.broadcast_to(A, d.shape)[m] for A in (X, Y, Z))
            d[m] += self.fn(Xb, Yb, Zb)
        return d


class Folds(Node):
    """衣褶：在形体 a 的表面上加一道道「棱」。每道褶是贴在表面上的一串点 P (m,3) 和法线 N (m,3)，截面不对称：
    一边陡（w1，褶的背光那一面）、一边缓（w2，慢慢铺开），棱顶是圆的，两边各一道浅沟。
    amp 是棱高（米），沿褶长两头收（taper），离开表面 depth 以外不起作用。sign=-1 时陡的一边换到另一侧。
    只在每道褶自己的包围盒、且离表面不远（|d| < 3 cm）的体素上算，几十道褶也不慢。"""

    def __init__(self, a, folds, near=0.03):
        self.a = a
        self.near = float(near)
        self.items = []
        amax = 0.0
        for f in folds:
            P = np.asarray(f['P'], np.float64)
            N = np.asarray(f['N'], np.float64)
            if len(P) < 3:
                continue
            seg = np.diff(P, axis=0)
            L = np.linalg.norm(seg, axis=1)
            ok = L > 1e-6
            if not np.all(ok):
                keep = np.concatenate([[True], ok])
                P, N = P[keep], N[keep]
                seg = np.diff(P, axis=0)
                L = np.linalg.norm(seg, axis=1)
            Nm = (N[:-1] + N[1:]) / 2
            Nm /= np.maximum(np.linalg.norm(Nm, axis=1, keepdims=True), 1e-9)
            T = seg / L[:, None]
            Nm = Nm - T * np.einsum('ij,ij->i', Nm, T)[:, None]
            Nm /= np.maximum(np.linalg.norm(Nm, axis=1, keepdims=True), 1e-9)
            side = np.cross(Nm, T) * float(f.get('sign', 1.0))
            w = 2.6 * max(f.get('w1', 0.006), f.get('w2', 0.03)) + 0.01
            it = dict(A=P[:-1], seg=seg, L=L, cum=np.concatenate([[0], np.cumsum(L)])[:-1], tot=L.sum(), N=Nm, S=side,
                      amp=float(f['amp']), w1=float(f.get('w1', 0.006)), w2=float(f.get('w2', 0.03)),
                      depth=float(f.get('depth', 0.04)), taper=float(f.get('taper', 0.3)), end=float(f.get('end', 0.0)),
                      lo=P.min(0) - w, hi=P.max(0) + w)
            self.items.append(it)
            amax = max(amax, it['amp'])
        self.lo = None if a.lo is None else a.lo - amax
        self.hi = None if a.hi is None else a.hi + amax

    @staticmethod
    def height(it, Q):
        """Q (n,3) 上的棱高"""
        n = len(Q)
        best = np.full(n, 1e9, np.float32)
        bi = np.zeros(n, np.int32)
        bt = np.zeros(n, np.float32)
        for i in range(len(it['A'])):
            A, sg, L = it['A'][i], it['seg'][i], it['L'][i]
            R = Q - A.astype(np.float32)
            t = np.clip((R @ sg.astype(np.float32)) / np.float32(L * L), 0, 1)
            D = R - t[:, None] * sg.astype(np.float32)
            d2 = np.einsum('ij,ij->i', D, D)
            m = d2 < best
            best[m] = d2[m]
            bi[m] = i
            bt[m] = t[m]
        A = it['A'][bi]
        Qc = A + bt[:, None] * it['seg'][bi]
        rel = Q - Qc
        sl = np.einsum('ij,ij->i', rel, it['S'][bi])
        sn = np.einsum('ij,ij->i', rel, it['N'][bi])
        u = (it['cum'][bi] + bt * it['L'][bi]) / it['tot']
        w1, w2 = it['w1'], it['w2']
        # 截面：圆的棱顶（两边都是高斯形，棱顶处斜率为 0 → 棱顶的半径约 w²/2amp，不是刀刃），陡的一边 w1、缓的一边 w2，
        # 两边各一道浅沟（布折过去压出来的那道软凹）
        q1, q2 = sl / w1, sl / w2
        prof = np.where(sl >= 0, np.exp(-q1 * q1) - 0.22 * np.exp(-((q1 - 1.7) / 0.7) ** 2),
                        np.exp(-q2 * q2) - 0.12 * np.exp(-((q2 + 1.6) / 0.7) ** 2))
        # 两头收：taper 是两头各多长（占全长的比例）收到 end
        tp = it['taper']
        g = np.minimum(np.clip(u / max(tp, 1e-3), 0, 1), np.clip((1 - u) / max(tp, 1e-3), 0, 1))
        g = it['end'] + (1 - it['end']) * (g * g * (3 - 2 * g))
        fall = np.exp(-(sn / it['depth']) ** 2)
        return (it['amp'] * prof * g * fall).astype(np.float32)

    def ev(self, X, Y, Z):
        d = self.a.ev(X, Y, Z)
        sh = _shape(X, Y, Z)
        d = np.array(np.broadcast_to(d, sh), np.float32)
        if _separable(X, Y, Z):
            for it in self.items:
                sl = _sub_block(X, Y, Z, it['lo'], it['hi'], 0.0)
                if sl is None:
                    continue
                db = d[sl]
                m = np.abs(db) < self.near
                if not np.any(m):
                    continue
                Xb = np.broadcast_to(X[sl[0]], db.shape)[m]
                Yb = np.broadcast_to(Y[:, sl[1]], db.shape)[m]
                Zb = np.broadcast_to(Z[:, :, sl[2]], db.shape)[m]
                Q = np.stack([Xb, Yb, Zb], axis=1).astype(np.float32)
                db[m] -= self.height(it, Q)
                d[sl] = db
            return d
        flat = d.reshape(-1)
        Xf, Yf, Zf = (np.broadcast_to(A, sh).reshape(-1) for A in (X, Y, Z))
        for it in self.items:
            lo, hi = it['lo'], it['hi']
            m = (Xf >= lo[0]) & (Xf <= hi[0]) & (Yf >= lo[1]) & (Yf <= hi[1]) & (Zf >= lo[2]) & (Zf <= hi[2]) & (np.abs(flat) < self.near)
            if np.any(m):
                Q = np.stack([Xf[m], Yf[m], Zf[m]], axis=1).astype(np.float32)
                flat[m] -= self.height(it, Q)
        return flat.reshape(sh)


class Clip(Node):
    """把 a 限制在一个盒子里算（盒子外当作很远）。用在只想让某个大形体影响一小块的时候"""

    def __init__(self, a, lo, hi):
        self.a = a
        self.lo, self.hi = V(lo), V(hi)

    def ev(self, X, Y, Z):
        return self.a.ev(X, Y, Z)


def chain(pts, radii, k=0.0):
    """沿一串点的一根「管子」（每段是圆台），radii 一个数或每点一个"""
    pts = [V(p) for p in pts]
    if isinstance(radii, (int, float)):
        radii = [radii] * len(pts)
    return Union([RoundCone(pts[i], pts[i + 1], radii[i], radii[i + 1]) for i in range(len(pts) - 1)], k)


def catmull(pts, n=8, closed=False):
    """过这些点的平滑曲线（Catmull-Rom），每段 n 个点"""
    P = [V(p) for p in pts]
    if closed:
        P = [P[-1]] + P + [P[0], P[1]]
    else:
        P = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for j in range(n):
            t = j / n
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-2])
    return out


# ---------------------------------------------------------------- 网格上算距离场
class Field:
    """一整块算好的距离场：d[i, j, k] 是点 lo + h*(i, j, k) 的距离"""

    def __init__(self, d, lo, h):
        self.d, self.lo, self.h = d, V(lo), float(h)

    def sample(self, P):
        """三线性插值取值，P: (N, 3)。网格外的点当作很远（正）"""
        d, lo, h = self.d, self.lo, self.h
        q = (np.asarray(P, np.float64) - lo) / h
        n = np.array(d.shape)
        i0 = np.floor(q).astype(np.int64)
        f = (q - i0).astype(np.float32)
        out_of = np.any((i0 < 0) | (i0 >= n - 1), axis=1)
        i0 = np.clip(i0, 0, n - 2)
        x, y, z = i0[:, 0], i0[:, 1], i0[:, 2]
        fx, fy, fz = f[:, 0], f[:, 1], f[:, 2]
        c000, c100, c010, c110 = d[x, y, z], d[x + 1, y, z], d[x, y + 1, z], d[x + 1, y + 1, z]
        c001, c101, c011, c111 = d[x, y, z + 1], d[x + 1, y, z + 1], d[x, y + 1, z + 1], d[x + 1, y + 1, z + 1]
        c00 = c000 + (c100 - c000) * fx
        c10 = c010 + (c110 - c010) * fx
        c01 = c001 + (c101 - c001) * fx
        c11 = c011 + (c111 - c011) * fx
        c0 = c00 + (c10 - c00) * fy
        c1 = c01 + (c11 - c01) * fy
        v = c0 + (c1 - c0) * fz
        return np.where(out_of, np.float32(1.0), v)

    def normals(self, P, e=None):
        e = e or self.h
        P = np.asarray(P, np.float64)
        g = np.zeros_like(P)
        for i in range(3):
            o = np.zeros(3)
            o[i] = e
            g[:, i] = self.sample(P + o) - self.sample(P - o)
        ln = np.linalg.norm(g, axis=1, keepdims=True)
        return g / np.maximum(ln, 1e-12)

    def ao(self, P, N, steps=(1.5, 3, 6, 12, 24), scale=None, strength=1.0):
        """距离场的环境光遮蔽：沿法线往外走几步，离别的表面越近越暗。返回 0（全遮）~1（不遮）"""
        s = scale or self.h
        occ = np.zeros(len(P), np.float32)
        wsum = 0.0
        for i, k in enumerate(steps):
            dlt = k * s
            w = 1.0 / (1.6 ** i)
            dd = self.sample(P + N * dlt)
            occ += w * np.clip((dlt - dd) / dlt, 0, 1)
            wsum += w
        return np.clip(1.0 - strength * occ / wsum, 0, 1)


def evaluate(node, lo, hi, h, verbose=None):
    """在 [lo, hi] 这块盒子里、每隔 h 米算一次距离 → Field"""
    import time
    t = time.time()
    lo = V(lo)
    hi = V(hi)
    n = np.ceil((hi - lo) / h).astype(int) + 1
    xs = (lo[0] + h * np.arange(n[0])).astype(np.float32)
    ys = (lo[1] + h * np.arange(n[1])).astype(np.float32)
    zs = (lo[2] + h * np.arange(n[2])).astype(np.float32)
    _MARGIN[0] = 3.0 * h
    d = node.ev(xs[:, None, None], ys[None, :, None], zs[None, None, :])
    d = np.array(np.broadcast_to(d, tuple(n)), dtype=np.float32, order='C', copy=True)
    bad = ~np.isfinite(d)
    if np.any(bad):     # 算出 nan 的地方当作在外面（不然 openvdb 会在那里挖出奇怪的洞）
        print(f'[yjm] !! {verbose or "距离场"}: {int(bad.sum())} 个体素是 nan/inf')
        d[bad] = h
    # 盒子的边上一圈强制在外面，保证抽出来的网格是封闭的
    for ax in range(3):
        for i in (0, -1):
            sl = [slice(None)] * 3
            sl[ax] = i
            d[tuple(sl)] = np.maximum(d[tuple(sl)], h)
    if verbose:
        print(f'[yjm] {verbose}: 距离场 {n[0]}×{n[1]}×{n[2]} = {d.size / 1e6:.1f}M 体素，{time.time() - t:.1f}s')
    return Field(d, lo, h)


def mesh(field, adaptivity=0.0, iso=0.0):
    """距离场 → 网格（openvdb volumeToMesh）。返回 verts (N,3)、faces（三角和四边形各一个数组）"""
    import openvdb as vdb
    g = vdb.FloatGrid(float(max(field.h * 4, 0.01)))
    g.copyFromArray(field.d)
    pts, tris, quads = g.convertToPolygons(isovalue=float(iso), adaptivity=float(adaptivity))
    pts = np.asarray(pts, np.float64) * field.h + field.lo
    tris = np.asarray(tris, np.int64).reshape(-1, 3)
    quads = np.asarray(quads, np.int64).reshape(-1, 4)
    return pts, tris, quads


def orient(verts, tris, quads, field):
    """openvdb 出来的面朝向不一定朝外：抽查几个面，和距离场的梯度比一下，反了就整体翻过来"""
    fs = quads[:200, :3] if len(quads) else tris[:200]
    a, b, c = verts[fs[:, 0]], verts[fs[:, 1]], verts[fs[:, 2]]
    n = np.cross(b - a, c - a)
    g = field.normals((a + b + c) / 3)
    if np.sum(np.einsum('ij,ij->i', n, g)) < 0:
        tris = tris[:, ::-1].copy()
        quads = quads[:, ::-1].copy()
    return tris, quads


# ---------------------------------------------------------------- 交给 Blender：建网格、减面
def np_mesh(name, verts, faces_list):
    """numpy 的点和面（几组：三角形 (n,3)、四边形 (m,4)……）→ Blender 网格"""
    import bpy
    faces_list = [f for f in faces_list if len(f)]
    sizes = np.concatenate([np.full(len(f), f.shape[1], np.int32) for f in faces_list])
    loops = np.concatenate([f.ravel() for f in faces_list]).astype(np.int32)
    starts = np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int32)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set('co', np.asarray(verts, np.float32).ravel())
    me.loops.add(len(loops))
    me.loops.foreach_set('vertex_index', loops)
    me.polygons.add(len(sizes))
    me.polygons.foreach_set('loop_start', starts)
    me.update(calc_edges=True)
    return me


def mesh_arrays(me):
    """Blender 网格 → (verts, loop_start, loop_total, loop_vert)"""
    nv, np_, nl = len(me.vertices), len(me.polygons), len(me.loops)
    co = np.zeros(nv * 3, np.float32)
    me.vertices.foreach_get('co', co)
    ls = np.zeros(np_, np.int32)
    lt = np.zeros(np_, np.int32)
    lv = np.zeros(nl, np.int32)
    me.polygons.foreach_get('loop_start', ls)
    me.polygons.foreach_get('loop_total', lt)
    me.loops.foreach_get('vertex_index', lv)
    return co.reshape(-1, 3).astype(np.float64), ls, lt, lv


def decimate(verts, faces_list, ratio, sym=False, keep=None, keep_factor=1.0):
    """Blender 的 collapse 减面。keep：每个点一个 0~1 的权重，越大越不减（脸、手指）"""
    import bpy
    me = np_mesh('_dec', verts, faces_list)
    ob = bpy.data.objects.new('_dec', me)
    bpy.context.scene.collection.objects.link(ob)
    m = ob.modifiers.new('d', 'DECIMATE')
    m.decimate_type = 'COLLAPSE'
    m.ratio = float(ratio)
    m.use_symmetry = bool(sym)
    m.symmetry_axis = 'X'
    if keep is not None:
        vg = ob.vertex_groups.new(name='keep')
        q = np.clip(np.round(np.asarray(keep) * 10), 0, 10).astype(int)
        for lv in range(1, 11):
            idx = np.nonzero(q == lv)[0].tolist()
            if idx:
                vg.add(idx, lv / 10.0, 'REPLACE')
        m.vertex_group = 'keep'
        m.vertex_group_factor = float(keep_factor)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me2 = bpy.data.meshes.new_from_object(ev)
    out = mesh_arrays(me2)
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    bpy.data.meshes.remove(me2)
    return out


# ---------------------------------------------------------------- 在形体上取点、画线
def ev_points(node, P):
    """在一串点 P (N,3) 上算距离"""
    P = np.asarray(P, np.float32).reshape(-1, 3)
    d = node.ev(P[:, 0], P[:, 1], P[:, 2])
    return np.array(np.broadcast_to(d, (len(P),)), np.float32)


def grad(node, P, e=1e-3):
    """距离场的梯度（单位化），P (N,3)"""
    P = np.asarray(P, np.float64).reshape(-1, 3)
    g = np.zeros_like(P)
    for i in range(3):
        o = np.zeros(3)
        o[i] = e
        g[:, i] = ev_points(node, P + o) - ev_points(node, P - o)
    return g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-12)


def project(node, P, D, tmax=0.6, n=96):
    """从 P 沿方向 D 往前找第一次碰到表面的地方（P 要在形体外面）。找不到的返回 P 自己。
    用来把画在空中的线「贴」到形体上：衣纹、衣边、颈纹……"""
    P = np.asarray(P, np.float64).reshape(-1, 3)
    D = np.broadcast_to(np.asarray(D, np.float64), P.shape)
    D = D / np.linalg.norm(D, axis=1, keepdims=True)
    ts = np.linspace(0, tmax, n)
    prev = ev_points(node, P)
    hit = np.full(len(P), -1.0)
    for i in range(1, n):
        cur = ev_points(node, P + D * ts[i])
        new = (hit < 0) & (prev > 0) & (cur <= 0)
        hit[new] = i
        prev = cur
    out = P.copy()
    ok = hit > 0
    if np.any(ok):
        a = ts[hit[ok].astype(int) - 1]
        b = ts[hit[ok].astype(int)]
        Pk, Dk = P[ok], D[ok]
        for _ in range(12):
            m = (a + b) / 2
            dm = ev_points(node, Pk + Dk * m[:, None])
            a = np.where(dm > 0, m, a)
            b = np.where(dm > 0, b, m)
        out[ok] = Pk + Dk * ((a + b) / 2)[:, None]
    return out


def snap(node, P, iters=6, e=1e-3):
    """把点沿梯度挪到表面上（牛顿法）"""
    P = np.asarray(P, np.float64).reshape(-1, 3).copy()
    for _ in range(iters):
        d = ev_points(node, P).astype(np.float64)
        P -= grad(node, P, e) * d[:, None]
    return P


def bake(node, lo, hi, h, verbose=None):
    """距离场 → 朝外的网格。返回 (field, verts, [tris, quads])"""
    f = evaluate(node, lo, hi, h, verbose)
    v, t, q = mesh(f)
    t, q = orient(v, t, q, f)
    return f, v, [t, q]


# ---------------------------------------------------------------- 网格工具（numpy）
def triangulate(faces_list):
    """三角形和四边形 → 全是三角形 (n,3)"""
    out = []
    for f in faces_list:
        f = np.asarray(f)
        if not len(f):
            continue
        for i in range(1, f.shape[1] - 1):
            out.append(f[:, [0, i, i + 1]])
    return np.concatenate(out).astype(np.int64)


def polys_to_tris(ls, lt, lv):
    """Blender 的多边形数组（起点、个数、顶点）→ 三角形"""
    out = []
    for n in np.unique(lt):
        sel = ls[lt == n]
        idx = sel[:, None] + np.arange(n)[None, :]
        f = lv[idx]
        for i in range(1, n - 1):
            out.append(f[:, [0, i, i + 1]])
    return np.concatenate(out).astype(np.int64)


def vertex_normals(V, T):
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    n = np.zeros_like(V)
    for k in range(3):
        np.add.at(n, T[:, k], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def neighbours_mean(V, T, vals=None):
    """每个点的相邻点的平均（位置或别的值）"""
    vals = V if vals is None else vals
    acc = np.zeros_like(vals, dtype=np.float64)
    cnt = np.zeros(len(V))
    for a, b in ((0, 1), (1, 2), (2, 0), (1, 0), (2, 1), (0, 2)):
        np.add.at(acc, T[:, a], vals[T[:, b]])
        np.add.at(cnt, T[:, a], 1)
    sh = (-1,) + (1,) * (acc.ndim - 1)
    return acc / np.maximum(cnt, 1).reshape(sh)


def curvature(V, T, smooth=2):
    """凸起为正、凹下为负（拉普拉斯沿法线的分量），按边长归一"""
    N = vertex_normals(V, T)
    L = neighbours_mean(V, T) - V
    el = np.linalg.norm(V[T[:, 0]] - V[T[:, 1]], axis=1).mean()
    c = -np.einsum('ij,ij->i', L, N) / max(el, 1e-9)
    for _ in range(smooth):
        c = 0.5 * c + 0.5 * neighbours_mean(V, T, c)
    return c


def bake_ao(V, T, dist=0.3, samples=48):
    """用 Cycles 把环境光遮蔽烤到顶点上：返回每个点 0（全遮）~1（不遮）"""
    import bpy
    sc = bpy.context.scene
    me = np_mesh('_ao', V, [T])
    ob = bpy.data.objects.new('_ao', me)
    sc.collection.objects.link(ob)
    ca = me.color_attributes.new('ao', 'FLOAT_COLOR', 'POINT')
    me.color_attributes.active_color = ca
    eng = sc.render.engine
    world = sc.world
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    w = bpy.data.worlds.new('_aow')
    w.light_settings.distance = dist
    sc.world = w
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.bake(type='AO', target='VERTEX_COLORS')
    a = np.zeros(len(V) * 4, np.float32)
    ca.data.foreach_get('color', a)
    sc.render.engine = eng
    sc.world = world
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    bpy.data.worlds.remove(w)
    return a.reshape(-1, 4)[:, 0].astype(np.float64)


def components(nv, T):
    """连通的块：每个点一个编号（并查集）"""
    parent = np.arange(nv)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    E = np.unique(np.sort(np.concatenate([T[:, [0, 1]], T[:, [1, 2]]]), axis=1), axis=0)
    for a, b in E:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    return np.array([find(i) for i in range(nv)])


def mean_curv(V, T, smooth=2):
    """每个点的平均曲率（1/米，凸为正）：拉普拉斯沿法线的分量除以边长的平方"""
    N = vertex_normals(V, T)
    L = neighbours_mean(V, T) - V
    e = np.linalg.norm(V[T[:, 0]] - V[T[:, 1]], axis=1)
    el = np.zeros(len(V))
    cnt = np.zeros(len(V))
    for k in range(3):
        np.add.at(el, T[:, k], e)
        np.add.at(cnt, T[:, k], 1)
    el = el / np.maximum(cnt, 1)
    c = -2 * np.einsum('ij,ij->i', L, N) / np.maximum(el * el, 1e-12)
    for _ in range(smooth):
        c = 0.5 * c + 0.5 * neighbours_mean(V, T, c)
    return c, N
