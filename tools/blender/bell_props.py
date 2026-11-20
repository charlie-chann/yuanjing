"""殿前的石凳、石鼓凳，钟亭里的铜钟和撞钟木（2026-11-19）。

石凳（stone_bench）：一条长石板搁在两个石墩上。石板的棱角磨圆了、磨得发亮，墩子四面各刻一朵如意云头，两墩之间一块牙板（下沿是壸门的弧）。
石鼓凳（stone_stool）：鼓形，上下各一圈鼓钉、一道弦纹，鼓腹四面开光（凹进去的海棠形框，框里一朵四瓣花）。
铜钟（temple_bell）：原点在悬挂点（蒲牢钮的拱顶里面），钟往下垂。蒲牢钮（双头龙的拱）、肩上一圈莲瓣、三组弦纹、四道竖棱分成四区，
  上区每区九枚钟乳，下区 ±x 两面是莲花撞座、±y 两面铸「国泰民安」「风调雨顺」，钟口是八瓣波形（荷叶口），里面是空的。
撞钟木（bell_striker）：原点在两根吊绳上端的正中（挂在梁上的那一点）。一根横吊的圆木沿 x 放，-x 那头包铜皮（撞钟的一头），
  +x 那头垂一根拉绳；绕 y 轴前后荡。

部件：stone（石）、bronze（铜钟）、wood（撞木）、brass（铜皮、铁箍上的钉）、toon（绳、铁箍）。都是 Unity 里已有的材质。
"""
import math

import bmesh
from mathutils import Vector, noise

from kit import Asset, new_bm, xform
from palette import C, mix, tint, vary, hexc
import craft
from craft import grid, smooth, bump, interp
from props_hd import VERDIGRIS


# ====================================================================== 石凳
def _worn_block(a, size, loc, mat, color, top=None, r=0.014, n=(10, 4, 3), wear=0.5, seed=0.0, moss=None):
    """一块磨圆了棱角的石头方块：棱不是整齐的倒角，是深浅不一的圆角（磨损），棱上的颜色发亮；底下可以泛一点青苔。
    loc 是底面中心"""
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    t = new_bm()
    bmesh.ops.create_cube(t, size=1.0)
    for v in t.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    for ax, (h, cnt) in enumerate(((hx, n[0]), (hy, n[1]), (hz, n[2]))):
        cuts = [-(h - r), -(h - r * 0.45), h - r * 0.45, h - r]
        cuts += [-(h - r) + 2 * (h - r) * k / cnt for k in range(1, cnt)]
        for c in cuts:
            no = Vector((0, 0, 0))
            no[ax] = 1
            co = Vector((0, 0, 0))
            co[ax] = c
            bmesh.ops.bisect_plane(t, geom=t.verts[:] + t.edges[:] + t.faces[:], plane_co=co, plane_no=no, dist=1e-6)
    col = t.loops.layers.float_color['col']
    lit = tint(color, 0.07, -0.02)
    info = {}
    for v in t.verts:
        p = v.co
        q = Vector((max(abs(p.x) - (hx - r), 0), max(abs(p.y) - (hy - r), 0), max(abs(p.z) - (hz - r), 0)))
        edge = min(1.0, q.length / r)
        if q.length > 1e-9:
            nz = noise.noise(Vector((p.x * 9 + seed, p.y * 9, p.z * 9)))
            rr = r * (1 - wear * 0.45 * max(0.0, nz + 0.25) * (1 if sum(1 for c in q if c > 1e-9) >= 2 else 0.0))
            qn = q.normalized() * rr
            v.co = Vector((math.copysign(hx - r + qn.x, p.x) if q.x > 0 else p.x,
                           math.copysign(hy - r + qn.y, p.y) if q.y > 0 else p.y,
                           math.copysign(hz - r + qn.z, p.z) if q.z > 0 else p.z))
        info[v] = edge
    for f in t.faces:
        f.smooth = True
        up = f.normal.z > 0.7
        for l in f.loops:
            p = l.vert.co
            c = top if (up and top is not None) else color
            m = noise.noise(Vector((p.x * 5 + seed, p.y * 5, p.z * 5 + 3)))
            c = tint(c, 0.035 * m, 0, 0)
            c = mix(c, lit, 0.7 * smooth(0.5, 1.0, info[l.vert]))
            if moss is not None:
                k = smooth(0.14, 0.0, p.z + hz) * max(0.0, 0.45 + noise.noise(Vector((p.x * 14, p.y * 14, seed))))
                c = mix(c, moss, min(0.75, k))
            l[col] = (c[0], c[1], c[2], 0)
    a.merge(t, mat, xform((loc[0], loc[1], loc[2] + hz)))


def _ruyi(a, c, right, up, out, size, color, mat):
    """贴在石面上的一朵如意云头：左右两个往里卷的涡、中间一个桃形的尖，底下两道往外撇的云脚。
    c 是花心，right/up/out 是石面上的横、竖和朝外的方向"""
    c, right, up, out = Vector(c), Vector(right), Vector(up), Vector(out)
    r0 = size * 0.085
    for sg in (-1, 1):
        pts = []
        for k in range(15):
            t = k / 14
            ang = math.pi * (0.55 + 2.25 * t)
            rr = size * (0.3 - 0.24 * t)
            pts.append(c + right * (sg * (size * 0.33 + rr * math.cos(ang))) + up * (size * 0.1 + rr * math.sin(ang)) + out * (r0 * 0.25))
        a.tube([c + up * (size * 0.52) + out * (r0 * 0.25)] + pts, [r0 * 0.9] + [r0 * (1.0 - 0.45 * k / 14) for k in range(15)], color, segs=5, mat=mat)
        foot = [c + right * (sg * size * 0.1) + up * (-size * 0.22) + out * (r0 * 0.25),
                c + right * (sg * size * 0.34) + up * (-size * 0.34) + out * (r0 * 0.25),
                c + right * (sg * size * 0.62) + up * (-size * 0.26) + out * (r0 * 0.25),
                c + right * (sg * size * 0.7) + up * (-size * 0.1) + out * (r0 * 0.25)]
        a.tube(foot, [r0 * 0.85, r0 * 0.8, r0 * 0.65, r0 * 0.35], color, segs=5, mat=mat)
    a.blob(size * 0.1, c + up * (size * 0.08) + out * (r0 * 0.2), (1, 1, 1), color, subdiv=2, bump=0, mat=mat)


def stone_bench(name):
    """长条石凳：长 1.5 米、宽 0.42、高 0.47。原点在地面中心，长边沿 x"""
    a = Asset(name)
    rng = a.rng
    S = 'stone'
    st, sl, sd = C('stone'), C('stone_lit'), C('stone_dark')
    moss = mix(st, C('moss'), 0.6)
    # 凳面：一整条石板，棱角磨圆、磨亮；面上两头略深（常坐的中间磨得亮）
    _worn_block(a, (1.5, 0.42, 0.11), (0, 0, 0.36), S, st, top=mix(st, sl, 0.6), r=0.02, n=(16, 5, 2), wear=0.9, seed=1.3)
    # 凳面边上几处磕掉的小缺口（深一点的小坑）
    for i in range(7):
        x = rng.uniform(-0.7, 0.7)
        sy = rng.choice((-1, 1))
        a.blob(rng.uniform(0.012, 0.022), (x, sy * 0.203, 0.36 + rng.choice((0.008, 0.1))), (1.6, 0.6, 0.7), tint(st, -0.1), subdiv=1, bump=0.25, mat=S)
    for sx in (-1, 1):
        x0 = sx * 0.5
        # 石墩：圭脚、束腰、上枋三截，上下宽、中间收
        _worn_block(a, (0.25, 0.4, 0.07), (x0, 0, 0.0), S, sd, top=st, r=0.012, n=(3, 5, 1), wear=0.8, seed=2.0 + sx, moss=moss)
        _worn_block(a, (0.18, 0.33, 0.215), (x0, 0, 0.068), S, tint(st, -0.03), r=0.012, n=(3, 5, 3), wear=0.6, seed=3.0 + sx)
        _worn_block(a, (0.24, 0.39, 0.085), (x0, 0, 0.28), S, st, top=sl, r=0.014, n=(3, 5, 1), wear=0.8, seed=4.0 + sx)
        # 束腰上下各一道线脚
        for z in (0.078, 0.272):
            a.box((0.2, 0.35, 0.014), (x0, 0, z - 0.007), color=sl, bevel=0.005, mat=S)
        # 四面的如意云头
        for (nx, ny, w) in ((0, -1, 0.27), (0, 1, 0.27), (sx, 0, 0.16)):
            out = Vector((nx, ny, 0))
            right = Vector((-ny, nx, 0)) if ny else Vector((0, 1, 0))
            cc = Vector((x0 + nx * 0.09, ny * 0.165, 0.178))
            _ruyi(a, cc, right, (0, 0, 1), out, w * 0.42, sl, S)
        # 上枋下沿一排小仰莲瓣（正面、背面、外侧面）
        for (nx, ny, cnt, half) in ((0, -1, 5, 0.085), (0, 1, 5, 0.085), (sx, 0, 7, 0.15)):
            for k in range(cnt):
                u = -half + 2 * half * k / (cnt - 1)
                px = x0 + (nx * 0.117 if nx else u)
                py = (ny * 0.192 if ny else u)
                a.blob(1.0, (px, py, 0.296), (0.019 if ny else 0.009, 0.009 if ny else 0.019, 0.016), vary(sl, rng, 0.02, 0.01), subdiv=1, bump=0, mat=S)
        # 墩脚的青苔
        for i in range(6):
            ang = rng.uniform(0, 6.28)
            a.blob(rng.uniform(0.012, 0.024), (x0 + 0.125 * math.cos(ang), 0.2 * math.sin(ang), rng.uniform(0.014, 0.035)), (1, 1, 0.5), moss, subdiv=1, bump=0.3)
    # 牙板：两墩之间、凳面底下一块竖着的薄石板，下沿是壸门的弧（两头低、中间高，中间一个尖）
    poly = [(-0.41, 0.36)]
    for k in range(25):
        t = k / 24
        x = -0.41 + 0.82 * t
        d = abs(t - 0.5) * 2
        z = 0.2 + 0.075 * (1 - d) ** 0.55 + 0.014 * math.cos(d * math.pi * 3) * (1 - d)
        poly.append((x, z))
    poly.append((0.41, 0.36))
    a.prism(poly, -0.02, 0.02, tint(st, -0.02), mat=S, rot=(math.pi / 2, 0, 0))
    # 牙板正中一朵小如意、两边卷草各一笔
    for sy in (-1, 1):
        _ruyi(a, (0, sy * 0.021, 0.322), (-sy, 0, 0), (0, 0, 1), (0, sy, 0), 0.055, sl, S)
        for sg in (-1, 1):
            pts = [Vector((sg * (0.1 + 0.25 * t), sy * 0.022, 0.335 - 0.025 * math.sin(math.pi * t) + 0.012 * math.sin(3 * math.pi * t))) for t in [k / 10 for k in range(11)]]
            a.tube(pts, [0.005 - 0.0025 * k / 10 for k in range(11)], sl, segs=5, mat=S)
    return craft.finish(a, (28, 26, 1.0), ao=True, dist=0.5, extra={'end': (80, 14, 1.0)})


# ====================================================================== 石鼓凳
def stone_stool(name):
    """石鼓凳：高 0.46、腹径 0.42。原点在地面中心"""
    a = Asset(name)
    rng = a.rng
    S = 'stone'
    st, sl, sd = C('stone'), C('stone_lit'), C('stone_dark')
    moss = mix(st, C('moss'), 0.55)
    H = 0.46

    def prof(v):
        return 0.158 + 0.052 * math.sin(math.pi * min(1.0, max(0.0, v))) ** 0.75

    def fn(u, v):
        th = 2 * math.pi * u
        z = H * v
        r = prof(v)
        h = 0.0
        c = st
        # 上下口沿各一道圆唇、里面一道弦纹
        for vc in (0.035, 0.965):
            h += 0.007 * bump(v, vc, 0.03)
        for vc in (0.185, 0.815):
            k = bump(v, vc, 0.014)
            h += 0.005 * k
            c = mix(c, sl, 0.6 * k)
        # 开光：四面各一个海棠形（四瓣）的凹框，框边一道凸线，框里一朵四瓣花
        dth = ((th + math.pi / 4) % (math.pi / 2)) - math.pi / 4
        x, y = dth * r, z - H / 2
        phi = math.atan2(y, x)
        rp = math.hypot(x / 0.092, y / 0.105)
        lob = 1.0 + 0.11 * math.cos(4 * phi)
        e = rp / lob
        if e < 1.0:
            h -= 0.011 * smooth(1.0, 0.8, e)
            c = mix(c, tint(sd, -0.03), 0.8 * smooth(1.0, 0.86, e))
            # 花：四片圆瓣加一个花心
            fr = math.hypot(x, y)
            pet = 0.03 + 0.03 * abs(math.cos(2 * phi)) ** 0.8
            if fr < pet:
                kf = smooth(pet, pet * 0.6, fr) * (0.55 + 0.45 * smooth(0.0, 0.012, fr))
                h += 0.009 * kf
                c = mix(c, sl, 0.75 * kf)
            if fr < 0.012:
                h += 0.004
        rim = bump(e, 1.03, 0.07)
        h += 0.005 * rim
        c = mix(c, sl, 0.55 * rim)
        # 石头的深浅、底下的青苔
        p = Vector((r * math.cos(th), r * math.sin(th), z))
        c = tint(c, 0.03 * noise.noise(p * 7))
        km = smooth(0.12, 0.0, z) * max(0.0, 0.4 + noise.noise(p * 16))
        c = mix(c, moss, min(0.7, km))
        return ((r + h) * math.cos(th), (r + h) * math.sin(th), z), c
    grid(a, S, 104, 38, fn, cap0=((0, 0, 0.0), sd))
    # 凳面：微微鼓起，靠边一道浅槽，中间磨得亮
    a.lathe([(0.163, H - 0.002, sl), (0.15, H + 0.006, sl), (0.128, H + 0.009, tint(st, -0.06)), (0.122, H + 0.0085, mix(st, sl, 0.7)),
             (0.06, H + 0.012, sl), (0.0, H + 0.013)], segs=64, color=sl, mat=S)
    # 鼓钉：上下各一圈
    for vc, n in ((0.105, 26), (0.895, 26)):
        r = prof(vc) + 0.004
        for i in range(n):
            th = 2 * math.pi * (i + (0.5 if vc > 0.5 else 0.0)) / n
            a.blob(0.0125, (r * math.cos(th), r * math.sin(th), H * vc), (1, 1, 1), vary(sl, rng, 0.02, 0.01), subdiv=1, bump=0, mat=S)
    return craft.finish(a, (25, 24, 1.0), ao=True, dist=0.3)


# ====================================================================== 铜钟
BELL_H = 0.9          # 钟口到钟顶
BELL_TOP = 1.02       # 钟口到悬挂点（蒲牢钮拱顶的里面）


def _bell_r(h):
    """钟身外面的半径：钟口略撇，往上慢慢收，肩是圆的、顶是平的"""
    if h <= 0.68:
        return 0.302 + 0.072 * math.exp(-h / 0.2)
    t = min(0.992, (h - 0.68) / 0.22)
    r0 = 0.302 + 0.072 * math.exp(-0.68 / 0.2)
    return r0 * max(0.0, 1 - t ** 2.7) ** (1 / 2.7) * (1 - 0.04 * t) + 0.0


def _bell_wave(th, h):
    """波形钟口：八瓣，瓣尖朝下；越往上越不起伏"""
    return 0.034 * (1 - abs(math.cos(4 * th)) ** 1.3) * max(0.0, 1 - h / 0.13) ** 1.6


def temple_bell(name):
    """铜钟：原点在悬挂点，钟口在 z = -1.02（瓣尖），钟口直径 0.75。±x 两面是撞座（撞木沿 x 撞），±y 两面是铭文"""
    a = Asset(name)
    rng = a.rng
    B = 'bronze'
    bz, bl, bd = C('bronze'), C('bronze_lit'), C('bronze_dark')
    Z0 = -BELL_TOP

    def hv(v):
        return BELL_H * (1.5 * v - 0.5 * v * v)

    def outer(u, v):
        th = 2 * math.pi * u
        h = hv(v)
        r = _bell_r(h)
        rel = 0.0
        k_lit = 0.0
        # 钟唇：口沿一道厚边
        lip = smooth(0.05, 0.02, h)
        rel += 0.009 * lip
        # 三组弦纹
        for c0 in (0.125, 0.165, 0.435, 0.475, 0.7):
            k = bump(h, c0, 0.0075)
            rel += 0.0065 * k
            k_lit = max(k_lit, k)
        # 四道竖棱（各两根），把钟身分成四区
        if 0.17 < h < 0.7:
            dth = ((th) % (math.pi / 2)) - math.pi / 4
            for off in (-0.014, 0.014):
                k = bump(dth * r, off, 0.0065)
                rel += 0.0055 * k
                k_lit = max(k_lit, k)
        # 肩上一圈覆莲瓣（十六瓣）
        if 0.71 < h < 0.875:
            t = (h - 0.71) / 0.165
            aa = ((th / (2 * math.pi) * 16) % 1.0 - 0.5) * 2
            edge = 1 - t - abs(aa) ** 1.6 * 0.95
            if edge > 0:
                k = smooth(0.0, 0.12, edge)
                rel += 0.004 * k + 0.003 * bump(edge, 0.05, 0.05) + 0.002 * bump(aa, 0, 0.1) * k
                k_lit = max(k_lit, 0.6 * bump(edge, 0.05, 0.06))
        # 下区的一圈回纹（钟唇上面那一带）
        if 0.05 < h < 0.118:
            uu = (th * r / 0.03) % 1.0
            vv_ = (h - 0.05) / 0.068
            key = (0.12 < uu < 0.88 and 0.15 < vv_ < 0.85) and not (0.3 < uu < 0.7 and 0.35 < vv_ < 0.65) and not (0.56 < uu < 0.88 and 0.35 < vv_ < 0.52)
            if key:
                rel += 0.003
                k_lit = max(k_lit, 0.6)
        r += rel
        z = Z0 + h + _bell_wave(th, h)
        p = Vector((r * math.cos(th), r * math.sin(th), z))
        c = mix(bz, bl, 0.75 * k_lit)
        c = mix(c, bl, 0.35 * lip)
        return p, c
    grid(a, B, 168, 60, outer, cap1=((0, 0, Z0 + BELL_H + 0.004), bz))

    # 里面：空的，暗；口沿一圈把里外接起来
    def inner(u, v):
        th = 2 * math.pi * u
        h = 0.82 * v
        r = _bell_r(h) - 0.03 - 0.012 * smooth(0.0, 0.1, h)
        if h > 0.6:
            r *= max(0.05, 1 - ((h - 0.6) / 0.24) ** 2.2)
        return Vector((r * math.cos(th), r * math.sin(th), Z0 + h + _bell_wave(th, h))), tint(bd, -0.06 - 0.1 * v)
    grid(a, B, 64, 10, inner, flip=True, cap1=((0, 0, Z0 + 0.8), tint(bd, -0.18)))

    def rim(u, v):
        th = 2 * math.pi * u
        r = (_bell_r(0) + 0.009) * (1 - v) + (_bell_r(0) - 0.03) * v
        return Vector((r * math.cos(th), r * math.sin(th), Z0 + _bell_wave(th, 0) - 0.004 * math.sin(math.pi * v))), mix(bl, bd, v)
    grid(a, B, 168, 2, rim, flip=True)

    def on(th, h, out=0.0):
        r = _bell_r(h) + out
        return Vector((r * math.cos(th), r * math.sin(th), Z0 + h))

    # 钟乳（枚）：上区每区三行三列
    for q in range(4):
        thc = q * math.pi / 2 + math.pi / 4 + math.pi / 4
        for row, h in enumerate((0.525, 0.585, 0.645)):
            for dth in (-0.42, 0.0, 0.42):
                th = thc + dth * (0.3 / _bell_r(h))
                a.lathe([(0.021, 0.0, bz), (0.019, 0.005, bl), (0.0135, 0.012, bl), (0.0075, 0.019, bl), (0.0, 0.0225)], on(th, h, -0.002), segs=12, color=bl,
                        rot=(0, math.pi / 2, th), mat=B)
    # 撞座：±x 两面各一朵八瓣莲（撞木撞在这里），磨得最亮
    for th in (0.0, math.pi):
        c = on(th, 0.3, -0.003)
        a.lathe([(0.092, 0.0, bz), (0.09, 0.008, bl), (0.082, 0.011, bz), (0.078, 0.007, bd), (0.05, 0.007, bl), (0.046, 0.014, bl), (0.03, 0.016, bl),
                 (0.012, 0.02, bl), (0.0, 0.021)], c, segs=40, color=bl, rot=(0, math.pi / 2, th), mat=B)
        out = Vector((math.cos(th), math.sin(th), 0))
        side = Vector((-math.sin(th), math.cos(th), 0))
        for k in range(8):
            ang = 2 * math.pi * (k + 0.5) / 8
            d = side * math.cos(ang) + Vector((0, 0, 1)) * math.sin(ang)
            a.blob(1.0, c + out * 0.009 + d * 0.064, (0.006, 0.0125, 0.019), tint(bl, 0.03), subdiv=2, bump=0, mat=B, rot=(ang - math.pi / 2, 0, th))
        for k in range(7):
            ang = 2 * math.pi * k / 7
            d = side * math.cos(ang) + Vector((0, 0, 1)) * math.sin(ang)
            a.blob(0.005, c + out * 0.018 + d * 0.019, (1, 1, 1), tint(bl, 0.06), subdiv=1, bump=0, mat=B)
    # 铭文：±y 两面，每面四个字（两列，从右往左读）
    for th, words in ((-math.pi / 2, ('国泰', '民安')), (math.pi / 2, ('风调', '雨顺'))):
        for ci, col_ in enumerate(words):
            for ri, ch in enumerate(col_):
                h = 0.375 - 0.115 * ri
                dth = (0.068 if ci == 0 else -0.068) / _bell_r(h)       # 第一列在看的人右手边
                t2 = th + dth if th < 0 else th + dth
                p = on(t2, h, -0.0015)
                a.text(ch, loc=(p.x, p.y, p.z), rot=(0, 0, t2 + math.pi / 2), size=0.098, depth=0.0075, bevel=0.0018, color=bl, mat=B, back=False)
        # 铭文外面一个长方的线框
        for dz0, dz1, sgn in ((0.19, 0.44, -1), (0.19, 0.44, 1)):
            pts = [on(th + sgn * 0.135 / _bell_r(h_), h_, 0.001) for h_ in (dz0, (dz0 + dz1) / 2, dz1)]
            a.tube(pts, 0.004, bl, segs=5, mat=B)
        for h_ in (0.19, 0.44):
            pts = [on(th + d_ / _bell_r(h_), h_, 0.001) for d_ in (-0.135, -0.07, 0.0, 0.07, 0.135)]
            a.tube(pts, 0.004, bl, segs=5, mat=B)
    # 蒲牢钮：一条拱起来的双头龙（拱在 xz 平面里），两头各一个龙头咬着钟顶；背上一排鳍，身上一圈圈鳞
    top = Z0 + BELL_H
    pts, rad = [], []
    for k in range(25):
        t = k / 24
        ang = math.pi * t
        pts.append(Vector((-0.118 * math.cos(ang), 0, top - 0.012 + (BELL_TOP - BELL_H + 0.045) * math.sin(ang) ** 0.85)))
        rad.append(0.03 + 0.008 * abs(math.cos(ang)) ** 2)
    a.tube(pts, rad, bz, segs=14, mat=B)
    for k in range(2, 23):
        p0 = pts[k]
        tg = (pts[k + 1] - pts[k - 1]).normalized()
        nrm = Vector((0, 1, 0)).cross(tg).normalized()
        if nrm.z < 0 and abs(tg.x) > 0.5:
            nrm = -nrm
        outv = (p0 - Vector((0, 0, top + 0.02))).normalized()
        # 鳞：一圈圈的环（每隔一节），背鳍：拱背上一排小三角
        if k % 2 == 0:
            ring = [p0 + (Vector((0, 1, 0)) * math.cos(b_) + outv * math.sin(b_)) * (rad[k] + 0.0015) for b_ in [2 * math.pi * j / 14 for j in range(15)]]
            a.tube(ring, 0.0038, bl, segs=4, mat=B, cap=False)
        a.lathe([(0.008, 0.0), (0.005, 0.012), (0.0, 0.024)], p0 + outv * (rad[k] - 0.002), segs=5, color=bl, mat=B,
                rot=(0, math.atan2(outv.x, outv.z), 0), squash=(1.4, 0.55))
    for sx in (-1, 1):
        hc = Vector((sx * 0.135, 0, top + 0.012))
        a.blob(1.0, hc, (0.05, 0.04, 0.036), bz, top=bl, subdiv=3, bump=0.04, mat=B)                        # 头
        a.blob(1.0, hc + Vector((sx * 0.045, 0, -0.012)), (0.036, 0.03, 0.02), bz, top=bl, subdiv=2, bump=0.03, mat=B)   # 吻
        a.blob(1.0, hc + Vector((sx * 0.07, 0, -0.004)), (0.012, 0.018, 0.01), bl, subdiv=2, bump=0, mat=B)   # 鼻
        for sy in (-1, 1):
            a.blob(0.0105, hc + Vector((sx * 0.022, sy * 0.03, 0.016)), (1, 1, 1), bl, subdiv=2, bump=0, mat=B)                # 眼
            a.blob(0.005, hc + Vector((sx * 0.027, sy * 0.037, 0.018)), (1, 1, 1), bd, subdiv=1, bump=0, mat=B)
            a.tube([hc + Vector((sx * 0.01, sy * 0.022, 0.028)), hc + Vector((-sx * 0.02, sy * 0.04, 0.055)), hc + Vector((-sx * 0.045, sy * 0.036, 0.062))],
                   [0.008, 0.0065, 0.003], bl, segs=6, mat=B)                                                 # 角
            a.tube([hc + Vector((sx * 0.06, sy * 0.022, -0.012)), hc + Vector((sx * 0.085, sy * 0.045, -0.03)), hc + Vector((sx * 0.07, sy * 0.06, -0.04))],
                   [0.004, 0.003, 0.0015], bl, segs=5, mat=B)                                                 # 须
            a.blob(1.0, hc + Vector((sx * 0.01, sy * 0.036, -0.022)), (0.03, 0.014, 0.014), bz, subdiv=2, bump=0, mat=B)       # 爪搭在钟顶上
    # 钟顶平面上一圈弦纹
    pts = [Vector((0.165 * math.cos(t), 0.165 * math.sin(t), top - 0.004 + 0.0)) for t in [2 * math.pi * k / 48 for k in range(49)]]
    a.tube(pts, 0.006, bl, segs=5, mat=B, cap=False)
    # 铜绿：凹处、朝下的地方、钟的下半泛绿（同香炉的做法）
    b = a.parts.get(B)
    col = b.loops.layers.float_color['col']
    for f in b.faces:
        for l in f.loops:
            p = l.vert.co
            hrel = (p.z - Z0) / BELL_H
            k = 0.22 * max(0.0, 1 - hrel) + max(0.0, -f.normal.z) * 0.25 + 0.42 * noise.noise(p * 7.0) + 0.2 * noise.noise(p * 23.0)
            k = max(0.0, min(0.8, k))
            cc = l[col]
            m = mix((cc[0], cc[1], cc[2]), VERDIGRIS, k * 0.5)
            l[col] = (m[0], m[1], m[2], cc[3])
    return craft.finish(a, (32, 12, 1.0), ao=True, floor=False, ground=False, dist=0.5, strength=0.5, extra={'face': (0, 8, 1.0), 'under': (35, -38, 1.0)})


# ====================================================================== 撞钟木
STRIKER_DROP = 0.9      # 悬挂点到撞木中轴
STRIKER_X0, STRIKER_X1 = -0.82, 0.72      # 撞木两头（-x 是撞钟的一头）
STRIKER_R = 0.07


def bell_striker(name):
    """撞钟木：原点在两根吊绳上端的正中。撞木沿 x，中轴在 z = -0.9；撞钟的一头（包铜皮）在 x = -0.82，另一头垂一根拉绳"""
    a = Asset(name)
    rng = a.rng
    W = 'wood'
    wd, wl, wk = C('wood'), C('wood_lit'), C('wood_dark')
    zc = -STRIKER_DROP
    L = STRIKER_X1 - STRIKER_X0

    # 木头：略有粗细，顺着木纹一道道深浅，几处节疤
    knots = [(rng.uniform(0.15, 0.85), rng.uniform(0, 6.28)) for _ in range(4)]

    def log(u, v):
        th = 2 * math.pi * u
        x = STRIKER_X0 + 0.02 + (L - 0.02) * v
        r = STRIKER_R * (1 + 0.025 * noise.noise(Vector((x * 2.2, math.cos(th), math.sin(th)))))
        g = noise.noise(Vector((x * 1.6, math.cos(th) * 9, math.sin(th) * 9)))
        c = mix(wd, wl, 0.5 + 0.5 * g)
        c = mix(c, wk, 0.55 * smooth(0.25, 0.6, noise.noise(Vector((x * 1.1 + 5, math.cos(th) * 22, math.sin(th) * 22)))))
        for kv, kth in knots:
            d = math.hypot((v - kv) * L, math.atan2(math.sin(th - kth), math.cos(th - kth)) * STRIKER_R)
            if d < 0.03:
                c = mix(wk, c, smooth(0.008, 0.03, d))
                r += 0.003 * smooth(0.03, 0.01, d)
        return Vector((x, r * math.cos(th), zc + r * math.sin(th))), c
    grid(a, W, 28, 44, log)
    # +x 那头的断面：一圈圈年轮
    a.lathe([(0.0, 0.004, wl), (0.012, 0.004, wd), (0.024, 0.0035, wl), (0.036, 0.003, wd), (0.05, 0.002, wl), (0.062, 0.0, wk), (STRIKER_R + 0.001, -0.006)],
            (STRIKER_X1 - 0.004, 0, zc), segs=28, color=wd, rot=(0, math.pi / 2, 0), mat=W)
    # -x 那头：包一截铜皮（筒），两道箍、一圈铆钉，撞钟的面微微鼓、中间撞得发亮
    BR = 'brass'
    br, brl, brd = hexc('#c9a24a'), hexc('#ecd386'), hexc('#8f6f2d')
    R1 = STRIKER_R + 0.007
    a.lathe([(0.0, -0.014, brl), (0.03, -0.012, br), (0.058, -0.006, brd), (R1 - 0.004, 0.0, br), (R1, 0.008, brl), (R1 + 0.004, 0.014, brl), (R1, 0.022, br),
             (R1, 0.16, brl), (R1 + 0.004, 0.168, brl), (R1, 0.176, brd), (R1 - 0.006, 0.19), (STRIKER_R - 0.002, 0.192)],
            (STRIKER_X0, 0, zc), segs=32, color=br, rot=(0, math.pi / 2, 0), mat=BR)
    for i in range(10):
        ang = 2 * math.pi * i / 10
        a.blob(0.0065, (STRIKER_X0 + 0.145, (R1 + 0.001) * math.cos(ang), zc + (R1 + 0.001) * math.sin(ang)), (1, 1, 1), brl, subdiv=1, bump=0, mat=BR)
    # 两道铁箍（吊绳套在箍上的环里）
    iron, iron_l = hexc('#3b3a3c'), hexc('#5d5c60')
    rope, rope_d = C('rope'), C('rope_dark')
    for xr in (-0.4, 0.4):
        a.lathe([(STRIKER_R - 0.002, -0.024, iron), (STRIKER_R + 0.006, -0.02, iron_l), (STRIKER_R + 0.006, 0.02, iron), (STRIKER_R - 0.002, 0.024)],
                (xr, 0, zc), segs=28, color=iron, rot=(0, math.pi / 2, 0), mat='toon', outward=True)
        for i in range(6):
            ang = 2 * math.pi * (i + 0.5) / 6
            a.blob(0.006, (xr, (STRIKER_R + 0.006) * math.cos(ang), zc + (STRIKER_R + 0.006) * math.sin(ang)), (1, 1, 1), brd, subdiv=1, bump=0, mat=BR)
        # 箍顶上的铁环
        ring = [Vector((xr + 0.02 * math.cos(t), 0, zc + STRIKER_R + 0.022 + 0.02 * math.sin(t))) for t in [2 * math.pi * k / 16 for k in range(17)]]
        a.tube(ring, 0.006, iron_l, segs=6, mat='toon', cap=False)
        # 吊绳：两股拧在一起，从梁上（z=0）垂到铁环，环上打个结
        z_lo = zc + STRIKER_R + 0.034
        for st_ in range(2):
            pts = []
            n = 70
            for k in range(n + 1):
                t = k / n
                ang = t * 2 * math.pi * 13 + st_ * math.pi
                pts.append(Vector((xr + 0.0062 * math.cos(ang), 0.0062 * math.sin(ang), z_lo + (0.0 - z_lo) * t)))
            a.tube(pts, 0.0072, rope if st_ == 0 else rope_d, segs=5, mat='toon')
        a.blob(0.021, (xr, 0, z_lo + 0.012), (1, 1, 1.25), rope, top=rope_d, subdiv=2, bump=0.12)
        a.blob(0.017, (xr, 0, -0.012), (1.1, 1.1, 0.9), rope_d, subdiv=2, bump=0.1)
    # 拉绳：+x 那头底下一个铁环，垂一根绳，绳头一个木把手
    xp = STRIKER_X1 - 0.1
    ring = [Vector((xp + 0.018 * math.cos(t), 0, zc - STRIKER_R - 0.016 + 0.018 * math.sin(t))) for t in [2 * math.pi * k / 14 for k in range(15)]]
    a.tube(ring, 0.005, iron_l, segs=6, mat='toon', cap=False)
    pts = [Vector((xp + 0.012 * math.sin(k * 0.55), 0.006 * math.sin(k * 0.9), zc - STRIKER_R - 0.03 - 0.05 * k)) for k in range(10)]
    a.tube(pts, 0.0075, rope, segs=6, mat='toon', color2=rope_d)
    pe = pts[-1]
    a.blob(0.016, pe + Vector((0, 0, 0.004)), (1, 1, 1.1), rope_d, subdiv=2, bump=0.1)
    a.lathe([(0.0, -0.065), (0.011, -0.062, wk), (0.016, -0.03, wd), (0.0135, 0.0, wl), (0.016, 0.03, wd), (0.011, 0.062, wk), (0.0, 0.065)],
            (pe.x, pe.y, pe.z - 0.02), segs=12, color=wd, rot=(math.pi / 2, 0, 0), mat=W)
    return craft.finish(a, (25, 12, 1.0), ao=True, floor=False, ground=False, dist=0.3, strength=0.5)


ASSETS = {'stone_bench': stone_bench, 'stone_stool': stone_stool, 'temple_bell': temple_bell, 'bell_striker': bell_striker}
