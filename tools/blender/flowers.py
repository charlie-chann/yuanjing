"""花（近看也经得起的做法）：一瓣一瓣建出来，花心、花蕊、花萼、茎、叶都是真的形体，不用贴图。
花瓣和叶子是实心的面，凑多近边缘都是清楚的；颜色从瓣根到瓣尖渐变，中线一道深色（花瓣的筋、叶子的主脉）。

尺寸比真花大一倍左右（真的雏菊只有两厘米，游戏里看不见）。"""
import math

from mathutils import Quaternion, Vector

from kit import Asset, new_bm
from palette import mix, tint, vary

UP = Vector((0, 0, 1))


def _perp(d):
    r = d.cross(UP)
    if r.length < 1e-4:
        r = d.cross(Vector((1, 0, 0)))
    return r.normalized()


def blade(a, base, d, side, L, W, c0, c1, mid=None, cup=0.0, droop=0.0, shape=(0.8, 0.7, 0.0), notch=0.0, cols=2, rows=4,
          mat='leaf', sway=(0.0, 0.3), phase=0.0, twist=0.0):
    """一片花瓣或叶子。从 base 沿 d 伸出去 L 长，side 是宽的方向。
    shape=(最宽处在哪 0..1 的指数, 胖瘦的指数, 尖端留多宽)；cup：横向兜起来；droop：往下弯（负的往上翘）；
    notch：瓣尖中间凹进去多少（波斯菊、樱花的缺口）；mid：中线的颜色；sway：根和尖随风摆的幅度"""
    d, side = Vector(d).normalized(), Vector(side).normalized()
    n = side.cross(d).normalized()
    t = new_bm()
    col = t.loops.layers.float_color['col']
    uv = t.loops.layers.uv['uv']
    grid = []
    for r in range(rows + 1):
        v = r / rows
        w = W * 0.5 * max(shape[2], math.sin(math.pi * min(1.0, v ** shape[0])) ** shape[1])
        if r == 0:
            w = W * 0.5 * 0.16
        tw = Quaternion(d, twist * v)
        row = []
        for c in range(cols + 1):
            u = c / cols * 2 - 1
            ext = 1.0 - notch * (1 - abs(u)) ** 1.5 * (v ** 3)
            p = Vector(base) + d * (L * v * ext) + (tw @ side) * (w * u) + (tw @ n) * (cup * W * (u * u - 0.5) * math.sin(math.pi * min(1, v + 0.1)))
            p += UP * (-droop * L * v * v)
            row.append((t.verts.new(p), u, v))
        grid.append(row)
    for r in range(rows):
        for c in range(cols):
            q = [grid[r][c], grid[r][c + 1], grid[r + 1][c + 1], grid[r + 1][c]]
            f = t.faces.new([x[0] for x in q])
            for l, (_, u, v) in zip(f.loops, q):
                cc = mix(c0, c1, v ** 0.8)
                if mid is not None:
                    cc = mix(mid, cc, min(1.0, abs(u) * 1.6 + v * 0.5))
                l[col] = (cc[0], cc[1], cc[2], sway[0] + (sway[1] - sway[0]) * v)
                l[uv].uv = (phase, 0)
    a.merge(t, mat)


def stem(a, pts, r0, r1, c0, c1, sway1=0.3, phase=0.0, segs=6):
    """茎：细管子，越往上摆得越多"""
    n = len(pts)
    a.tube(pts, [r0 + (r1 - r0) * i / (n - 1) for i in range(n)], c0, segs=segs, color2=c1, sway=(0.0, sway1), mat='toon')
    # kit.tube 给每根管子随机相位，这里要和花头一致（不然茎和花各晃各的）
    b = a.parts['toon']
    uvl = b.loops.layers.uv['uv']
    b.faces.ensure_lookup_table()
    for f in b.faces[-(n - 1) * segs - 2:]:
        for l in f.loops:
            l[uvl].uv = (phase, 0)


def _curve(rng, h, lean=0.12):
    ang = rng.uniform(0, 6.28)
    dx, dy = math.cos(ang) * lean * h, math.sin(ang) * lean * h
    return [Vector((dx * t * t, dy * t * t, h * t)) for t in (0, 0.25, 0.5, 0.75, 1.0)]


def _head_frame(pts, tilt, rng):
    """花头的朝向：大致朝上，往茎弯的方向歪一点"""
    d = (pts[-1] - pts[-2]).normalized()
    f = (UP * (1 - tilt) + d * tilt + Vector((rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15), 0))).normalized()
    x = _perp(f)
    return f, x, f.cross(x).normalized()


def _disc(a, at, f, r, h, c0, c1, phase, sway=0.3, bumps=0, rng=None, cb=None):
    """花心：一个小鼓包，上面一圈圈小颗粒（管状花、花药）"""
    x = _perp(f)
    y = f.cross(x).normalized()
    t = new_bm()
    col = t.loops.layers.float_color['col']
    uv = t.loops.layers.uv['uv']
    rings = []
    segs = 12
    for k, (rr, hh) in enumerate(((1.0, 0.0), (0.92, 0.45), (0.62, 0.85), (0.28, 1.0))):
        rings.append([t.verts.new(Vector(at) + (x * math.cos(2 * math.pi * i / segs) + y * math.sin(2 * math.pi * i / segs)) * r * rr + f * h * hh) for i in range(segs)])
    top = t.verts.new(Vector(at) + f * h * 1.04)
    for k in range(3):
        for i in range(segs):
            j = (i + 1) % segs
            t.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
    for i in range(segs):
        t.faces.new((rings[3][i], rings[3][(i + 1) % segs], top))
    for fc in t.faces:
        for l in fc.loops:
            hgt = (l.vert.co - Vector(at)).dot(f) / max(h, 1e-5)
            cc = mix(c0, c1, min(1, hgt))
            l[col] = (cc[0], cc[1], cc[2], sway)
            l[uv].uv = (phase, 0)
    a.merge(t, 'toon')
    for i in range(bumps):
        ang = i * 2.399
        rr = r * 0.9 * math.sqrt((i + 0.5) / bumps)
        hh = h * (1 - (rr / r) ** 2 * 0.75)
        p = Vector(at) + (x * math.cos(ang) + y * math.sin(ang)) * rr + f * hh
        s = r * 0.13
        blade(a, p, f, x, s * 1.6, s * 1.5, cb or c1, tint(cb or c1, 0.08), cols=2, rows=2, shape=(1.0, 0.5, 0.5), mat='leaf', sway=(sway, sway), phase=phase)


def _leaves(a, rng, at, count, L, W, c0, c1, phase, rise=(0.25, 0.6), **kw):
    """贴着地的一圈叶子"""
    for i in range(count):
        ang = 2 * math.pi * i / count + rng.uniform(-0.4, 0.4)
        up = rng.uniform(*rise)
        d = Vector((math.cos(ang), math.sin(ang), up)).normalized()
        blade(a, at, d, _perp(d), L * rng.uniform(0.75, 1.15), W * rng.uniform(0.85, 1.15), c0, vary(c1, rng, 0.04, 0.04), mid=tint(c0, -0.05),
              cup=0.25, droop=rng.uniform(0.15, 0.45), cols=2, rows=4, sway=(0.0, 0.25), phase=phase, **kw)


G0, G1 = (0.22, 0.42, 0.18), (0.42, 0.66, 0.28)


def daisy(name, petal=(0.98, 0.98, 0.95), root=(0.96, 0.86, 0.9), n=3):
    """雏菊：两层细长的白瓣，鼓鼓的黄花心；一丛两三朵，带一个花苞"""
    a = Asset(name)
    rng = a.rng
    for k in range(n):
        ph = rng.random()
        o = Vector((rng.uniform(-0.07, 0.07), rng.uniform(-0.07, 0.07), 0)) if k else Vector((0, 0, 0))
        h = rng.uniform(0.17, 0.27)
        pts = [o + p for p in _curve(rng, h)]
        stem(a, pts, 0.0038, 0.003, G0, G1, 0.3, ph)
        f, x, y = _head_frame(pts, 0.5, rng)
        top = pts[-1]
        bud = k == n - 1 and n > 1
        cnt = 21
        for layer in (0, 1):
            for i in range(cnt if not bud else 9):
                ang = 2 * math.pi * (i + 0.5 * layer) / cnt * (1 if not bud else cnt / 9)
                rad = x * math.cos(ang) + y * math.sin(ang)
                lift = (0.12 + 0.2 * layer) if not bud else 1.6
                d = (rad + f * lift).normalized()
                L = rng.uniform(0.04, 0.047) * (0.92 if layer else 1.0) * (0.55 if bud else 1.0)
                blade(a, top + rad * 0.012 + f * (0.004 + 0.003 * layer), d, f.cross(rad), L, 0.0125, root, vary(petal, rng, 0.02, 0.01),
                      cup=0.3, droop=rng.uniform(-0.05, 0.25) if not bud else 0, shape=(0.75, 0.55, 0.3), rows=3, sway=(0.3, 0.34), phase=ph)
            if bud:
                break
        # 花萼
        for i in range(8):
            ang = 2 * math.pi * i / 8
            rad = x * math.cos(ang) + y * math.sin(ang)
            blade(a, top - f * 0.006, (rad + f * 0.5).normalized(), f.cross(rad), 0.016, 0.009, G0, G1, rows=2, shape=(0.8, 0.6, 0.2), sway=(0.3, 0.3), phase=ph)
        if not bud:
            _disc(a, top + f * 0.003, f, 0.0155, 0.011, (0.93, 0.66, 0.12), (1.0, 0.86, 0.28), ph, bumps=26, rng=rng, cb=(1.0, 0.8, 0.2))
    _leaves(a, rng, Vector((0, 0, 0.004)), 7, 0.085, 0.032, G0, G1, 0.3, shape=(1.5, 0.8, 0.0))
    a.opts['leaf'] = {'normal_up': 0.45}
    return a.finish(view=(20, 28, 1.0), floor=True, dist=0.2)


def buttercup(name):
    """毛茛：五片圆圆的亮黄花瓣兜成碗，中间一圈花蕊；茎上分杈，带花苞和裂开的叶子"""
    a = Asset(name)
    rng = a.rng
    ye, yd = (1.0, 0.86, 0.12), (0.96, 0.66, 0.08)
    for k in range(3):
        ph = rng.random()
        o = Vector((rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06), 0)) if k else Vector((0, 0, 0))
        h = rng.uniform(0.2, 0.32)
        pts = [o + p for p in _curve(rng, h, 0.2)]
        stem(a, pts, 0.0034, 0.0026, G0, G1, 0.35, ph)
        f, x, y = _head_frame(pts, 0.35, rng)
        top = pts[-1]
        for i in range(5):
            ang = 2 * math.pi * i / 5
            rad = x * math.cos(ang) + y * math.sin(ang)
            d = (rad + f * 0.55).normalized()
            blade(a, top + rad * 0.004, d, f.cross(rad), 0.036, 0.036, yd, vary(ye, rng, 0.02, 0.02), mid=mix(yd, ye, 0.5), cup=0.45, droop=-0.25,
                  shape=(0.62, 0.5, 0.45), cols=4, rows=4, sway=(0.35, 0.38), phase=ph)
            blade(a, top - f * 0.003, (rad * -0.9 + f * -0.25 + f.cross(rad) * 0.5).normalized(), rad, 0.014, 0.008, G0, G1, rows=2, sway=(0.35, 0.35), phase=ph)
        _disc(a, top + f * 0.002, f, 0.0075, 0.007, (0.55, 0.7, 0.2), (0.8, 0.85, 0.3), ph, sway=0.35)
        for i in range(16):       # 花蕊
            ang = 2 * math.pi * i / 16 + rng.uniform(-0.1, 0.1)
            rad = x * math.cos(ang) + y * math.sin(ang)
            d = (rad * 0.8 + f).normalized()
            blade(a, top + rad * 0.006 + f * 0.003, d, f.cross(rad), 0.013, 0.0035, (0.95, 0.75, 0.1), (1.0, 0.9, 0.35), rows=2, shape=(1.4, 0.4, 0.8),
                  sway=(0.35, 0.37), phase=ph)
        # 茎上一片裂成三瓣的叶
        p, d0 = pts[2], (pts[3] - pts[1]).normalized()
        s0 = _perp(d0)
        for da in (-0.7, 0.0, 0.7):
            d = (Quaternion(d0, rng.uniform(0, 6.28)) @ s0)
            d = (Quaternion(UP, da) @ d + UP * 0.25).normalized()
            blade(a, p, d, _perp(d), 0.05, 0.02, G0, G1, mid=tint(G0, -0.04), cup=0.2, droop=0.25, shape=(1.4, 0.7, 0.0), rows=3, sway=(0.15, 0.3), phase=ph)
    for i in range(5):            # 贴地的叶：每片裂成三瓣
        ang = 2 * math.pi * i / 5 + rng.uniform(-0.3, 0.3)
        for da in (-0.5, 0.0, 0.5):
            d = Vector((math.cos(ang + da), math.sin(ang + da), 0.45)).normalized()
            blade(a, (0, 0, 0.004), d, _perp(d), 0.085 * (1 if da == 0 else 0.8), 0.03, G0, vary(G1, rng, 0.04, 0.04), mid=tint(G0, -0.04), cup=0.2,
                  droop=0.4, shape=(1.5, 0.7, 0.0), sway=(0.0, 0.25), phase=0.3)
    a.opts['leaf'] = {'normal_up': 0.45}
    return a.finish(view=(20, 28, 1.0), dist=0.2)


def violet(name):
    """紫花地丁：五瓣，下面那瓣最大、喉部发白带深色的线；心形的叶子一丛"""
    a = Asset(name)
    rng = a.rng
    pu, pd, wh = (0.56, 0.36, 0.86), (0.38, 0.2, 0.66), (0.95, 0.92, 1.0)
    for k in range(4):
        ph = rng.random()
        o = Vector((rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06), 0))
        h = rng.uniform(0.09, 0.16)
        pts = [o + p for p in _curve(rng, h, 0.5)]
        stem(a, pts, 0.0026, 0.002, (0.3, 0.4, 0.2), (0.5, 0.45, 0.4), 0.3, ph, segs=5)
        ang0 = math.atan2(pts[-1].y - pts[0].y, pts[-1].x - pts[0].x)
        f = Vector((math.cos(ang0), math.sin(ang0), 0.25)).normalized()      # 花朝外开
        x = _perp(f)
        y = f.cross(x).normalized()
        if y.z < 0:
            x, y = -x, -y
        top = pts[-1]
        for ang, L, W, c in ((1.15, 0.03, 0.02, pu), (1.99, 0.03, 0.02, pu), (0.15, 0.03, 0.021, pu), (2.99, 0.03, 0.021, pu), (-1.57, 0.036, 0.027, pu)):
            rad = x * math.cos(ang) + y * math.sin(ang)
            d = (rad + f * 0.35).normalized()
            blade(a, top, d, f.cross(rad), L, W, wh if ang < 0 else pd, vary(c, rng, 0.03, 0.03), mid=pd, cup=0.25, droop=-0.12,
                  shape=(0.7, 0.55, 0.4), cols=4, rows=4, sway=(0.3, 0.33), phase=ph)
        _disc(a, top + f * 0.001, f, 0.0035, 0.004, (0.95, 0.7, 0.1), (1.0, 0.85, 0.3), ph)
    for i in range(9):            # 心形叶：两片半叶拼成
        ang = 2 * math.pi * i / 9 + rng.uniform(-0.3, 0.3)
        r0 = rng.uniform(0.0, 0.03)
        base = Vector((math.cos(ang) * r0, math.sin(ang) * r0, 0.004))
        d = Vector((math.cos(ang), math.sin(ang), rng.uniform(0.3, 0.8))).normalized()
        L = rng.uniform(0.06, 0.085)
        pts = [base, base + d * L * 0.5 + UP * 0.01, base + d * L]
        stem(a, pts, 0.002, 0.0016, G0, G1, 0.2, 0.4, segs=4)
        tipd = Vector((math.cos(ang), math.sin(ang), rng.uniform(-0.1, 0.25))).normalized()
        s = _perp(tipd)
        for sg in (-1, 1):
            dd = (tipd + s * sg * 0.32).normalized()
            blade(a, pts[-1], dd, s, 0.05, 0.034, G0, vary(G1, rng, 0.04, 0.04), mid=tint(G0, -0.03), cup=0.15, droop=0.15, shape=(0.55, 0.6, 0.0),
                  rows=4, sway=(0.2, 0.3), phase=0.4)
    a.opts['leaf'] = {'normal_up': 0.45}
    return a.finish(view=(20, 28, 1.0), dist=0.2)


def clover(name):
    """三叶草：一小片，每片叶子三瓣、中间一道浅色的弯纹；夹着几个白色的小花球，偶尔一棵四叶的"""
    a = Asset(name)
    rng = a.rng
    cg0, cg1, pale = (0.2, 0.46, 0.2), (0.36, 0.66, 0.28), (0.66, 0.84, 0.56)
    for i in range(26):
        ang = rng.uniform(0, 6.28)
        r0 = 0.16 * math.sqrt(rng.random())
        o = Vector((math.cos(ang) * r0, math.sin(ang) * r0, 0))
        h = rng.uniform(0.05, 0.11)
        ph = rng.random()
        pts = [o + p for p in _curve(rng, h, 0.3)]
        stem(a, pts, 0.0018, 0.0014, cg0, cg1, 0.3, ph, segs=4)
        top = pts[-1]
        n = 4 if i == 7 else 3
        rot = rng.uniform(0, 6.28)
        for k in range(n):
            a2 = rot + 2 * math.pi * k / n
            d = Vector((math.cos(a2), math.sin(a2), rng.uniform(0.05, 0.3))).normalized()
            s = _perp(d)
            L = rng.uniform(0.024, 0.032)
            # 一瓣小叶：心形，由左右两半拼成；中段压一道浅色
            for sg in (-1, 1):
                dd = (d + s * sg * 0.3).normalized()
                t0 = len(a.part('leaf').faces)
                blade(a, top, dd, s, L, L * 0.62, cg0, vary(cg1, rng, 0.04, 0.04), cup=0.2, droop=0.1, shape=(0.5, 0.6, 0.0), rows=4,
                      sway=(0.3, 0.34), phase=ph)
                b = a.part('leaf')
                b.faces.ensure_lookup_table()
                col = b.loops.layers.float_color['col']
                for fc in b.faces[t0:]:
                    for l in fc.loops:
                        v = (l.vert.co - top).length / L
                        if 0.38 < v < 0.66:
                            c = l[col]
                            m = mix((c[0], c[1], c[2]), pale, 0.55)
                            l[col] = (m[0], m[1], m[2], c[3])
    for i in range(4):            # 花球
        ang = rng.uniform(0, 6.28)
        r0 = rng.uniform(0.03, 0.13)
        o = Vector((math.cos(ang) * r0, math.sin(ang) * r0, 0))
        ph = rng.random()
        pts = [o + p for p in _curve(rng, rng.uniform(0.11, 0.16), 0.15)]
        stem(a, pts, 0.002, 0.0016, cg0, (0.5, 0.6, 0.35), 0.3, ph, segs=4)
        c = pts[-1] + UP * 0.008
        for k in range(46):
            z = 1 - 2 * (k + 0.5) / 46
            rr = math.sqrt(1 - z * z)
            a2 = k * 2.399
            d = Vector((rr * math.cos(a2), rr * math.sin(a2), z * 0.9 + 0.25)).normalized()
            blade(a, c + d * 0.004, d, _perp(d), 0.013, 0.0045, (0.9, 0.8, 0.82) if z < 0 else (0.96, 0.9, 0.9), (1.0, 0.99, 0.97), rows=2,
                  shape=(1.2, 0.5, 0.35), cup=0.5, sway=(0.3, 0.32), phase=ph)
    a.opts['leaf'] = {'normal_up': 0.5}
    return a.finish(view=(20, 34, 1.0), dist=0.15)


def cosmos(name, petal=(0.98, 0.62, 0.78), deep=(0.86, 0.36, 0.6)):
    """波斯菊：高高的细茎，八片瓣尖带缺口的大花瓣，羽毛一样的细叶"""
    a = Asset(name)
    rng = a.rng
    for k in range(3):
        ph = rng.random()
        o = Vector((rng.uniform(-0.08, 0.08), rng.uniform(-0.08, 0.08), 0)) if k else Vector((0, 0, 0))
        h = rng.uniform(0.38, 0.58)
        pts = [o + p for p in _curve(rng, h, 0.18)]
        stem(a, pts, 0.0042, 0.0028, G0, G1, 0.45, ph)
        f, x, y = _head_frame(pts, 0.45, rng)
        top = pts[-1]
        for i in range(8):
            ang = 2 * math.pi * i / 8 + rng.uniform(-0.05, 0.05)
            rad = x * math.cos(ang) + y * math.sin(ang)
            d = (rad + f * 0.2).normalized()
            blade(a, top + rad * 0.006, d, f.cross(rad), rng.uniform(0.05, 0.056), 0.032, deep, vary(petal, rng, 0.03, 0.03), mid=mix(deep, petal, 0.55),
                  cup=0.2, droop=rng.uniform(0.0, 0.12), shape=(0.5, 0.45, 0.62), notch=0.16, cols=4, rows=5, sway=(0.45, 0.5), phase=ph)
        for i in range(8):
            ang = 2 * math.pi * (i + 0.5) / 8
            rad = x * math.cos(ang) + y * math.sin(ang)
            blade(a, top - f * 0.004, (rad + f * 0.3).normalized(), f.cross(rad), 0.016, 0.006, G0, G1, rows=2, sway=(0.45, 0.45), phase=ph)
        _disc(a, top + f * 0.002, f, 0.0105, 0.007, (0.9, 0.6, 0.08), (1.0, 0.84, 0.25), ph, sway=0.45, bumps=18, rng=rng, cb=(0.99, 0.78, 0.18))
        # 羽状的细叶：茎上三四处，每处几根细丝
        for j in (1, 2, 3):
            p = pts[j]
            az = rng.uniform(0, 6.28)
            for sg in (0, 1):
                d0 = Vector((math.cos(az + sg * 3.14), math.sin(az + sg * 3.14), 0.5)).normalized()
                for m in range(5):
                    d = (d0 + _perp(d0) * (m - 2) * 0.32 + UP * rng.uniform(-0.1, 0.1)).normalized()
                    blade(a, p, d, _perp(d), rng.uniform(0.05, 0.08), 0.0045, G0, G1, rows=3, shape=(1.3, 0.4, 0.3), droop=0.3,
                          sway=(0.12 * j, 0.14 * j + 0.1), phase=ph)
    a.opts['leaf'] = {'normal_up': 0.45}
    return a.finish(view=(20, 22, 1.0), dist=0.25)


ASSETS = {
    'fl_daisy': daisy,
    'fl_daisy_pink': lambda n: daisy(n, (0.99, 0.8, 0.86), (0.93, 0.5, 0.66)),
    'fl_buttercup': buttercup,
    'fl_violet': violet,
    'fl_clover': clover,
    'fl_cosmos': cosmos,
    'fl_cosmos_white': lambda n: cosmos(n, (0.99, 0.97, 0.98), (0.96, 0.8, 0.88)),
}
