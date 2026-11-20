"""小动物送来的礼物（2026-11-19）：放在地上、叼在嘴里的小物件，5～15 厘米。

海螺、彩色鹅卵石、四叶草、松果、银杏叶、枫叶、羽毛、小铃铛、毛线球、珍珠、平安结。
（骨头、树枝、小花、小鱼、贝壳是早先在 animals.py 的 pet_items 里做的，没动。）
和那几样一样：原点在地面上、物件的正中，平放着；颜色从 palette 取，接近的自己配。
部件：toon（实体）、leaf（叶片、羽毛，双面）、brass（小铃铛的铜）、glow（珍珠，自发光 0.45）。
"""
import math

from mathutils import Matrix, Vector, noise

from kit import Asset
from palette import C, hexc, mix, tint, vary
import craft
from craft import grid, fan, smooth, bump, interp, clamp


def _euler(xaxis, zhint):
    """让局部 x 轴朝 xaxis、局部 z 轴尽量朝 zhint 的转角（给 kit 的 rot 用）"""
    x = Vector(xaxis).normalized()
    z = Vector(zhint)
    z = (z - x * z.dot(x)).normalized()
    y = z.cross(x)
    return tuple(Matrix((x, y, z)).transposed().to_euler('XYZ'))


def conch(name):
    """海螺：长 9 厘米，侧躺着（螺尖朝 -x）。四圈半螺旋，一圈比一圈大，肩上一排小疙瘩；奶白的底上绕着橘褐色的带，螺口里是粉的"""
    a = Asset(name)
    cream, band, pink = hexc('#f6ead2'), hexc('#c9793a'), hexc('#f4b8a8')
    turns = 4.6

    def geo(t):
        g = 1.72 ** (turns * (t - 1))          # 每转一圈大 1.72 倍（等比螺线）
        return 0.0185 * g, 0.0168 * g + 0.0004, -0.036 + 0.064 * g
    zoff = 0.0185 + 0.0168 + 0.0006

    def fn(uu, vv):
        t = vv
        phi = 2 * math.pi * turns * t
        th = 2 * math.pi * uu
        rho, ar, x = geo(t)
        # 肩上的疙瘩：朝外偏螺尖那一侧
        knob = max(0.0, math.sin(phi * 4.0)) ** 2 * bump(th, 2.2, 0.5) * smooth(0.45, 0.7, t)
        ar2 = ar * (1 + 0.2 * knob)
        rr = rho + ar2 * math.cos(th)
        p = Vector((x - ar2 * 1.15 * math.sin(th), rr * math.cos(phi), rr * math.sin(phi) + zoff))
        # 颜色：沿螺旋的色带（随 th 分三道）、疙瘩顶上发白、细的生长纹
        c = cream
        c = mix(c, band, 0.8 * (bump(th, 1.1, 0.28) + bump(th, 2.9, 0.22) * 0.7 + bump(th, 0.2, 0.15) * 0.5))
        c = mix(c, hexc('#fff8ea'), 0.7 * knob)
        c = tint(c, 0.035 * math.sin(phi * 26))
        return p, c
    rho, ar, x = geo(1.0)
    grid(a, 'toon', 18, 140, fn, cap0=((-0.0325, 0, zoff), cream))
    # 螺口：往里凹进去的一片粉
    phi = 2 * math.pi * turns
    cen = Vector((x, rho * math.cos(phi), rho * math.sin(phi) + zoff))
    tg = Vector((0, -math.sin(phi), math.cos(phi)))
    pts = [Vector((x - ar * 1.15 * math.sin(th), (rho + ar * math.cos(th)) * math.cos(phi), (rho + ar * math.cos(th)) * math.sin(phi) + zoff))
           for th in [2 * math.pi * k / 18 for k in range(19)]]
    fan(a, 'toon', cen - tg * ar * 0.75, pts, [mix(pink, cream, 0.5)] * 19, root_color=tint(pink, -0.12), rings=[0.55])
    return craft.finish(a, (30, 32, 1.0), extra={'b': (200, 30, 1.0)})


def _stone(a, size, loc, rot, colfn, seed, nu=28, nv=16):
    """一颗磨圆了的卵石：扁的椭球，略不规则"""
    M = Matrix.Translation(loc) @ Matrix.Rotation(rot, 4, 'Z')

    def fn(uu, vv):
        th, ph = 2 * math.pi * uu, math.pi * (vv - 0.5)
        d = Vector((math.cos(th) * math.cos(ph), math.sin(th) * math.cos(ph), math.sin(ph)))
        k = 1 + 0.07 * noise.noise(d * 1.4 + Vector((seed, 0, 0)))
        e = Vector((abs(d.x) ** 0.9 * math.copysign(1, d.x), abs(d.y) ** 0.9 * math.copysign(1, d.y), abs(d.z) ** 0.8 * math.copysign(1, d.z)))
        p = Vector((e.x * size[0] * k, e.y * size[1] * k, e.z * size[2] * k + size[2]))
        return p, colfn(d, p)
    grid(a, 'toon', nu, nv, fn, cap0=((0, 0, 0.0005), colfn(Vector((0, 0, -1)), Vector((0, 0, 0)))),
         cap1=((0, 0, size[2] * 2 * (1 + 0.07 * noise.noise(Vector((seed, 0, 1.4))))), colfn(Vector((0, 0, 1)), Vector((0, 0, size[2] * 2)))), M=M)


def pebble(name):
    """彩色鹅卵石：一大两小三颗。大的是青绿色、腰上一道白色的石英脉；一颗赭红带深纹，一颗小的米白带灰点。大的长 7 厘米"""
    a = Asset(name)
    jade, white, red, sand = hexc('#6fa58f'), hexc('#f3f1e6'), hexc('#b3563c'), hexc('#ece3cd')

    def c1(d, p):
        c = mix(jade, hexc('#4f8a78'), 0.5 + 0.5 * noise.noise(d * 2.2))
        v = d.x * 0.55 + d.y * 0.3 + d.z * 0.5 + 0.12 * noise.noise(d * 3)
        c = mix(c, white, 0.9 * bump(v, 0.08, 0.07) + 0.6 * bump(v, -0.3, 0.025))
        return tint(c, 0.05 * d.z)

    def c2(d, p):
        c = mix(red, hexc('#8c3d2c'), smooth(-0.2, 0.3, math.sin(d.x * 9 + 2.5 * noise.noise(d * 2))))
        return tint(c, 0.06 * d.z)

    def c3(d, p):
        c = sand
        if noise.noise(d * 7 + Vector((3, 0, 0))) > 0.3:
            c = mix(c, hexc('#8f8b84'), 0.7)
        return tint(c, 0.04 * d.z)
    _stone(a, (0.035, 0.025, 0.014), (-0.008, 0.004, 0), 0.4, c1, 1.0)
    _stone(a, (0.021, 0.016, 0.0095), (0.042, -0.014, 0), -0.5, c2, 4.0, 22, 12)
    _stone(a, (0.013, 0.011, 0.007), (0.027, 0.03, 0), 1.2, c3, 8.0, 18, 10)
    return craft.finish(a, (25, 38, 1.0))


def clover(name):
    """四叶草：四片心形的小叶（每片中间一道折、一个白色的人字纹），一根细柄。平放，展开约 6 厘米、连柄 10 厘米"""
    a = Asset(name)
    g0, g1, pale = hexc('#4f9a48'), hexc('#79bf5c'), hexc('#cfe6b0')
    ctr = Vector((0.0, 0.012, 0.012))
    for i in range(4):
        ang = math.pi / 4 + i * math.pi / 2 + (0.06 if i % 2 else -0.05)
        d = Vector((math.cos(ang), math.sin(ang), 0))
        sd = Vector((-math.sin(ang), math.cos(ang), 0))
        Lf = 0.03 if i != 3 else 0.027
        pts, cols = [], []
        n = 25
        for k in range(n):
            s = k / (n - 1) * 2 - 1
            a_ = s * 1.22
            r = Lf * (0.52 + 0.48 * math.cos(s * math.pi / 2) ** 0.45) * (1 - 0.3 * math.exp(-(s / 0.16) ** 2))
            fold = 0.006 * abs(s) ** 0.8 * (r / Lf)          # 两半各自往上翘一点（中间是折）
            pts.append(ctr + d * (r * math.cos(a_)) + sd * (r * math.sin(a_)) + Vector((0, 0, 0.004 + fold)))
            cols.append(mix(g0, g1, 0.4 + 0.6 * abs(s)))

        def shade(k_, i_, c, n=n):
            s = i_ / (n - 1) * 2 - 1
            mark = bump(k_, 0.5 + 0.12 * (1 - abs(s)), 0.09) * smooth(1.0, 0.6, abs(s))
            c = mix(c, pale, 0.75 * mark)
            return mix(c, hexc('#3f8a3f'), 0.5 * bump(s, 0, 0.06))          # 中脉
        fan(a, 'leaf', ctr, pts, cols, root_color=g0, rings=[(0.3, 0.001), (0.5, 0.002), (0.75, 0.002)], shade=shade)
    # 叶柄：细细一根，微弯着躺在地上
    a.tube([ctr, ctr + Vector((0.002, -0.012, -0.006)), Vector((0.006, -0.03, 0.003)), Vector((0.002, -0.055, 0.0025)), Vector((-0.006, -0.078, 0.002))],
           [0.0012, 0.0013, 0.0013, 0.0012, 0.001], hexc('#7fb35a'), segs=5, mat='toon')
    a.opts['leaf'] = {'plain_normals': True, 'normal_up': 0.5}
    return craft.finish(a, (15, 50, 1.0))


def pinecone(name):
    """松果：长 8 厘米，侧躺（尖朝 +x）。一片片木质的鳞按螺旋排开、张着，每片鳞尖上一个浅色的鳞脐；底下一小截果柄"""
    a = Asset(name)
    rng = a.rng
    br, br_d, tipc = hexc('#7b5334'), hexc('#553823'), hexc('#b98d5e')
    Lc, Rm = 0.078, 0.023
    zc = Rm + 0.008
    # 芯
    a.lathe([(0.0, 0.0), (0.008, 0.002, br_d), (0.011, Lc * 0.4, br_d), (0.007, Lc * 0.8, br_d), (0.0, Lc * 0.97)], (-Lc / 2, 0, zc), segs=10, color=br_d, rot=(0, math.pi / 2, 0))
    a.tube([(-Lc / 2 + 0.002, 0, zc), (-Lc / 2 - 0.008, 0.001, zc - 0.002), (-Lc / 2 - 0.014, 0.003, zc - 0.006)], [0.004, 0.0032, 0.0028], br_d, segs=6, color2=br)
    n = 68
    for i in range(n):
        t = (i + 0.5) / n
        ang = i * math.radians(137.5)
        x = -Lc / 2 + Lc * (0.04 + 0.9 * t)
        rc = 0.011 * math.sin(math.pi * (0.1 + 0.85 * t)) ** 0.6          # 芯在这里多粗
        open_ = math.radians(62 - 30 * t)                                # 鳞张开的角：底下张得开、尖上收拢
        radial = Vector((0, math.cos(ang), math.sin(ang)))
        d = (Vector((1, 0, 0)) * math.cos(open_) + radial * math.sin(open_)).normalized()
        ln = (Rm * math.sin(math.pi * (0.14 + 0.8 * t)) ** 0.7 - rc * 0.4) / max(0.3, math.sin(open_)) * rng.uniform(0.92, 1.05)
        wd = 0.016 * math.sin(math.pi * (0.2 + 0.7 * t)) ** 0.5
        base = Vector((x, 0, zc)) + radial * rc * 0.6
        zh = (d.cross(Vector((0, -math.sin(ang), math.cos(ang))))).normalized()
        if zh.x < 0:
            zh = -zh
        c = vary(br, rng, 0.04, 0.03)
        a.box((ln, wd * 0.82, 0.003), base + d * (ln / 2), rot=_euler(d, zh), color=tint(c, -0.1), top=c, bevel=0.0, base=False)
        # 鳞盾：鳞尖上一块菱形的厚头（比鳞片宽），中间一个深色的小鳞脐
        ct = vary(tipc, rng, 0.04, 0.03)
        a.blob(1.0, base + d * (ln - 0.0005), (0.0042, wd * 0.62, 0.0036), tint(ct, -0.06), top=ct, subdiv=1, bump=0, rot=_euler(d, zh))
        a.blob(0.0013, base + d * (ln + 0.003), (1, 1, 1), br_d, subdiv=1, bump=0)
    return craft.finish(a, (30, 28, 1.0), ao=True, dist=0.02, strength=0.5)


def ginkgo(name):
    """银杏叶：扇形的一片，宽 8 厘米，连柄 10 厘米，平放（叶尖朝 +y）。金黄色，叶根带一点绿；一条条叶脉从叶柄散到叶缘，
    叶缘是波浪形的、正中一个小缺口，叶面微微拱着"""
    a = Asset(name)
    y0, y1, grn = hexc('#f2c53c'), hexc('#fbe07a'), hexc('#b9c24e')
    root = Vector((0, -0.012, 0.003))
    n = 61
    pts, cols = [], []
    for k in range(n):
        s = k / (n - 1) * 2 - 1
        ang = math.pi / 2 - s * math.radians(66)
        r = 0.056 * (1 - 0.16 * math.exp(-(s / 0.06) ** 2) - 0.07 * abs(s) ** 3 + 0.025 * math.sin(s * 19) * (1 - abs(s) * 0.5))
        curl = 0.006 * math.sin(s * 5.0) + 0.004 * abs(s)
        pts.append(root + Vector((r * math.cos(ang), r * math.sin(ang), 0.004 + curl)))
        cols.append(mix(y0, y1, 0.5 + 0.5 * math.sin(s * 7)))

    def shade(k_, i_, c):
        c = tint(c, -0.045 if i_ % 3 == 0 else 0.012)          # 叶脉：每隔两格一条深的
        c = mix(c, grn, 0.5 * smooth(0.45, 0.0, k_))
        return mix(c, hexc('#d99a2a'), 0.35 * smooth(0.85, 1.0, k_) * (0.5 + 0.5 * math.sin(i_ * 1.7)))          # 叶缘几处焦黄
    fan(a, 'leaf', root, pts, cols, root_color=grn, rings=[(0.25, 0.003), (0.5, 0.0055), (0.75, 0.005), (0.92, 0.002)], shade=shade)
    a.tube([root + Vector((0, 0.002, 0)), root + Vector((0.002, -0.014, 0.001)), root + Vector((-0.003, -0.03, -0.0005)), root + Vector((-0.002, -0.043, -0.001))],
           [0.0011, 0.001, 0.001, 0.0014], hexc('#cdb84a'), segs=5, mat='toon')
    a.opts['leaf'] = {'plain_normals': True, 'normal_up': 0.5}
    return craft.finish(a, (10, 52, 1.0))


def maple(name):
    """枫叶：五裂的一片，宽 10 厘米，平放（中间的裂片朝 +y）。从叶心的橘黄红到叶尖的深红，五条主脉发亮，叶缘带锯齿，裂片的尖微微翘起"""
    a = Asset(name)
    c_in, c_out, vein = hexc('#f59542'), hexc('#cf3d2a'), hexc('#fbc15e')
    root = Vector((0, -0.01, 0.003))
    lobes = [(0.0, 0.062, 0.5), (0.9, 0.055, 0.48), (-0.9, 0.055, 0.48), (1.8, 0.037, 0.45), (-1.8, 0.037, 0.45)]
    n = 181
    pts, cols, axis = [], [], []
    for k in range(n):
        s = k / (n - 1) * 2 - 1
        th = s * 2.45          # 从正前（+y）往两边量的角
        r, near = 0.012, 9.0
        for (t0, L, w) in lobes:
            d = abs(th - t0)
            near = min(near, d)
            if d < w:
                r = max(r, L * (1 - d / w) ** 1.15 * (1 + 0.16 * (abs(math.sin(d / w * math.pi * 3.5)) - 0.5)) + 0.012)
        lift = 0.004 * smooth(0.03, 0.062, r) + 0.0012 * math.sin(k * 0.9)
        pts.append(root + Vector((r * math.sin(th), r * math.cos(th), 0.003 + lift)))
        cols.append(mix(c_out, hexc('#e4633b'), 0.5 * smooth(0.06, 0.02, r)))
        axis.append(near)

    def shade(k_, i_, c):
        c = mix(c_in, c, smooth(0.15, 0.85, k_)) if k_ < 1 else c
        return mix(c, vein, 0.75 * bump(axis[i_], 0.0, 0.035) * smooth(1.0, 0.75, k_))
    fan(a, 'leaf', root, pts, cols, root_color=c_in, rings=[(0.2, 0.001), (0.45, 0.003), (0.7, 0.003), (0.88, 0.0015)], shade=shade)
    a.tube([root, root + Vector((0.001, -0.014, 0.0005)), root + Vector((0.005, -0.03, 0.0)), root + Vector((0.004, -0.045, -0.001))],
           [0.001, 0.001, 0.001, 0.0015], hexc('#b5452f'), segs=5, mat='toon')
    a.opts['leaf'] = {'plain_normals': True, 'normal_up': 0.5}
    return craft.finish(a, (10, 52, 1.0))


def feather(name):
    """羽毛：长 13 厘米，平放（羽尖朝 +y）。一根微弯的羽轴，两边的羽片一丝丝斜着排（外侧窄、内侧宽），有两三处羽丝分开的小缺口；
    白色，往羽尖渐渐变成青灰，根上几缕蓬松的绒"""
    a = Asset(name)
    rng = a.rng
    white, grey, shaft = hexc('#fbfaf5'), hexc('#8fa3b5'), hexc('#e9e2cf')
    Lf = 0.13

    def axis(t):
        return Vector((0.012 * math.sin(t * 1.6) - 0.004, -Lf / 2 + Lf * t, 0.004 + 0.006 * math.sin(math.pi * t)))
    a.tube([axis(k / 16) for k in range(17)], [0.0014 - 0.001 * k / 16 for k in range(17)], shaft, segs=5, mat='toon')
    n = 44
    gaps = {(-1, 13), (1, 22), (1, 31), (-1, 35)}
    for sg, wmax in ((-1, 0.0125), (1, 0.019)):
        prev = None
        for k in range(n + 1):
            t = 0.14 + 0.86 * k / n
            p = axis(t)
            tg = (axis(min(1.0, t + 0.02)) - axis(t - 0.02)).normalized()
            sd = Vector((tg.y, -tg.x, 0)).normalized() * sg
            w = wmax * math.sin(math.pi * clamp((t - 0.12) / 0.9)) ** 0.55 * (1 - 0.35 * t)
            e = p + sd * w + tg * (w * 0.75) + Vector((0, 0, -0.0035 * (w / wmax) + 0.0015 * math.sin(k * 2.1)))
            cur = (p, e, t)
            if prev is not None and (sg, k) not in gaps:
                c0 = mix(white, grey, smooth(0.45, 1.0, prev[2]) * 0.85)
                c1 = mix(white, grey, smooth(0.45, 1.0, t) * 0.85)
                dk = -0.014 if k % 2 else 0.0
                a.quad([prev[0], prev[1], e, p], mat='leaf', colors=[tint(c0, dk), tint(c0, dk - 0.04), tint(c1, dk - 0.04), tint(c1, dk)])
            prev = cur
    # 根上的绒：几缕散开的细丝
    for i in range(12):
        t = 0.03 + 0.1 * rng.random()
        p = axis(t)
        sg = rng.choice((-1, 1))
        d = Vector((sg * rng.uniform(0.5, 1.0), rng.uniform(-0.3, 0.6), rng.uniform(0.0, 0.5))).normalized()
        ln = rng.uniform(0.008, 0.014)
        sd = d.cross(Vector((0, 0, 1))).normalized() * 0.0009
        a.quad([p - sd, p + sd, p + d * ln], color=tint(white, -0.03 * rng.random()), mat='leaf')
    a.opts['leaf'] = {'plain_normals': True, 'normal_up': 0.5}
    return craft.finish(a, (8, 55, 1.0))


def little_bell(name):
    """小铃铛：直径 4 厘米的铜铃，侧躺着。圆球形，腰上一道凸棱，底下一道十字开口（开口两头各一个小圆孔，看得见里面是暗的），
    顶上一个小环，环上系一根红绳打了个蝴蝶结"""
    a = Asset(name)
    BR = 'brass'
    g0, g1, gd = hexc('#c9982f'), hexc('#f0d070'), hexc('#7a5a20')
    R = 0.02
    tilt = Matrix.Translation((0, 0, R + 0.0015)) @ Matrix.Rotation(math.radians(-108), 4, 'X') @ Matrix.Rotation(0.6, 4, 'Z')

    def fn(uu, vv):
        th, ph = 2 * math.pi * uu, math.pi * (vv - 0.5)
        d = Vector((math.cos(th) * math.cos(ph), math.sin(th) * math.cos(ph), math.sin(ph)))
        r = R * (1 + 0.045 * bump(ph, 0.0, 0.07))          # 腰上的棱
        c = mix(g0, g1, 0.5 + 0.5 * d.z)
        c = mix(c, g1, 0.6 * bump(ph, 0.0, 0.08))
        if d.z < -0.25:          # 十字开口：两道缝，缝是凹下去的暗色
            slit = min(abs(d.x), abs(d.y)) * R
            lim = 0.0021 if d.z < -0.42 else 0.0
            if slit < lim:
                r -= 0.0022
                c = tint(gd, -0.25)
            elif slit < lim + 0.0012:
                c = g1
        for (hx, hy) in ((1, 0), (-1, 0), (0, 1), (0, -1)):          # 缝头的小圆孔
            q = (d - Vector((hx * 0.9, hy * 0.9, -0.436))).length * R
            if q < 0.0034:
                r -= 0.0022
                c = tint(gd, -0.25)
            elif q < 0.0046:
                c = g1
        # 铃身上一圈錾出来的小花纹（上半）
        if 0.25 < ph < 0.9:
            c = tint(c, -0.06 * max(0.0, math.sin(th * 8)) * bump(ph, 0.55, 0.2))
        return d * r, c
    grid(a, BR, 56, 36, fn, cap0=((0, 0, -R + 0.0022), tint(gd, -0.25)), cap1=((0, 0, R), g1), M=tilt)
    # 顶上的环（一个小座子加一个圈）
    top = tilt @ Vector((0, 0, R))
    up = (tilt.to_3x3() @ Vector((0, 0, 1))).normalized()
    side = (tilt.to_3x3() @ Vector((1, 0, 0))).normalized()
    a.blob(0.0045, top + up * 0.0005, (1, 1, 1), g0, subdiv=2, bump=0, mat=BR)
    ring = [top + up * (0.007 + 0.0052 * math.sin(t)) + side * (0.0052 * math.cos(t)) for t in [2 * math.pi * k / 16 for k in range(17)]]
    a.tube(ring, 0.0014, g1, segs=6, mat=BR, cap=False)
    # 红绳：穿过环，在地上打个蝴蝶结，两根绳头
    red, red_d = C('cloth_red'), C('red_dark')
    kc = top + up * 0.012
    kn = Vector((kc.x + 0.016, kc.y + 0.012, 0.004))
    a.tube([kc - side * 0.002, kc + up * 0.006, (kc + kn) / 2 + Vector((0, 0, 0.004)), kn], 0.0013, red, segs=5)
    a.blob(0.0032, kn, (1.2, 1, 0.8), red_d, subdiv=1, bump=0)
    for sg in (-1, 1):
        lp = [kn + Vector((sg * 0.014 * math.sin(t) * (1.0), 0.008 * math.sin(2 * t) * sg * 0.6 + 0.004 * math.sin(t), 0.0015 * math.sin(t))) for t in [math.pi * k / 10 for k in range(11)]]
        a.tube(lp, 0.0012, red, segs=5)
        a.tube([kn, kn + Vector((sg * 0.008, 0.012, -0.001)), kn + Vector((sg * 0.016, 0.026, -0.002)), kn + Vector((sg * 0.013, 0.038, -0.0025))], 0.0012, red, segs=5, color2=red_d)
    return craft.finish(a, (25, 30, 1.0), ao=True, dist=0.03, strength=0.4)


def yarn(name):
    """毛线球：直径 8 厘米。一圈圈毛线朝各个方向缠出来的（每一股都是真的线），玫红色，深浅略有不同；一根线头松出来，弯弯曲曲拖在地上"""
    a = Asset(name)
    rng = a.rng
    base, lit, dark = hexc('#e2638a'), hexc('#f29ab6'), hexc('#b9456c')
    R = 0.037
    zc = R + 0.003

    def core(uu, vv):
        th, ph = 2 * math.pi * uu, math.pi * (vv - 0.5)
        d = Vector((math.cos(th) * math.cos(ph), math.sin(th) * math.cos(ph), math.sin(ph)))
        return d * (R - 0.0016) + Vector((0, 0, zc)), tint(dark, -0.06)
    grid(a, 'toon', 20, 10, core, cap0=((0, 0, zc - R + 0.0016), dark), cap1=((0, 0, zc + R - 0.0016), dark))
    for i in range(18):
        ax = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized()
        e1 = ax.cross(Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))).normalized()
        e2 = ax.cross(e1)
        off = rng.uniform(-0.45, 0.45) * R          # 不都过球心：一组组平行的小圆
        rr = math.sqrt(max(1e-6, (R + 0.0008 * (i % 3)) ** 2 - off * off))
        c = vary(rng.choice((base, base, lit, dark)), rng, 0.04, 0.04)
        for j in range(3):          # 每一组三股并排
            o2 = off + (j - 1) * 0.0044
            r2 = math.sqrt(max(1e-6, rr * rr + off * off - o2 * o2))
            pts = [Vector((0, 0, zc)) + ax * o2 + (e1 * math.cos(t) + e2 * math.sin(t)) * r2 for t in [2 * math.pi * k / 18 for k in range(19)]]
            a.tube(pts, 0.0023, tint(c, 0.03 * (j - 1)), segs=4, cap=False)
    # 松出来的线头
    pts = [Vector((R * 0.75, -R * 0.5, 0.012))]
    for k in range(1, 14):
        t = k / 13
        pts.append(Vector((R * 0.8 + 0.075 * t + 0.01 * math.sin(t * 9), -R * 0.5 - 0.03 * t + 0.016 * math.sin(t * 6.5), 0.0024 + 0.008 * (1 - t) ** 3)))
    a.tube(pts, 0.0022, base, segs=5, color2=lit)
    return craft.finish(a, (25, 30, 1.0), ao=True, dist=0.02, strength=0.5)


def pearl(name):
    """珍珠：一片张开的扇贝壳（宽 9 厘米）里躺着一颗珍珠（直径 2.2 厘米）。贝壳外面是一道道放射的棱、奶白带粉，里面是光滑的珠母白；
    珍珠是 glow 部件（自发光 0.45），夜里微微发亮"""
    a = Asset(name)
    cream, pink, nacre = hexc('#f6e3d2'), hexc('#eeb7a8'), hexc('#fdf9f2')
    Rs = 0.046

    def shell(uu, vv, inner):
        s = uu * 2 - 1
        ang = math.pi / 2 + s * math.radians(78)
        rib = math.cos(s * math.pi * 8.5)
        r = Rs * vv * (1 - 0.1 * abs(s) ** 2.2) * (1 + 0.035 * rib * vv)
        # 浅碟：最深的地方在离壳顶四成处，往壳缘、往壳顶都翘起来
        z = 0.004 + (0.018 * ((vv - 0.4) / 0.6) ** 2 if vv > 0.4 else 0.006 * ((0.4 - vv) / 0.4) ** 2)
        z += 0.0016 * rib * vv * (0.5 if inner else 1.0) + (0.0016 if inner else 0.0)
        p = Vector((r * math.cos(ang), r * math.sin(ang) - 0.018, z))
        if inner:
            c = mix(nacre, hexc('#f3dfe6'), 0.5 * bump(vv, 0.6, 0.3) * (0.5 + 0.5 * math.sin(s * 5)))
            c = mix(c, hexc('#dff0ee'), 0.35 * bump(vv, 0.3, 0.2))
            c = tint(c, 0.025 * rib * vv)
        else:
            c = mix(cream, pink, 0.6 * bump(vv, 0.55, 0.12) + 0.5 * bump(vv, 0.85, 0.07))
            c = tint(c, 0.05 * rib)
        return p, c
    # 里面（朝上）是珠母，外面（朝下）是棱
    grid(a, 'toon', 68, 14, lambda u, v: shell(u, v, True), wrap=False)
    grid(a, 'toon', 68, 14, lambda u, v: shell(u, v, False), wrap=False, flip=True)
    # 壳顶的两个小耳
    for sg in (-1, 1):
        a.box((0.011, 0.006, 0.0025), (sg * 0.007, -0.02, 0.0092), rot=(-0.3, 0, sg * 0.25), color=tint(cream, -0.05), bevel=0.001)
    # 珍珠
    pr = 0.011
    pc = Vector((0.001, 0.0005, 0.0052 + pr))

    def pf(uu, vv):
        th, ph = 2 * math.pi * uu, math.pi * (vv - 0.5)
        d = Vector((math.cos(th) * math.cos(ph), math.sin(th) * math.cos(ph), math.sin(ph)))
        c = mix(hexc('#f7efe6'), hexc('#fffdf8'), 0.5 + 0.5 * d.z)
        c = mix(c, hexc('#f6dbe2'), 0.35 * bump(d.x + d.z * 0.4, -0.5, 0.4))
        c = mix(c, hexc('#dfeef4'), 0.3 * bump(d.y - d.z * 0.3, 0.6, 0.35))
        return pc + d * pr, c
    grid(a, 'glow', 28, 16, pf, cap0=(pc - Vector((0, 0, pr)), hexc('#f3e8dd')), cap1=(pc + Vector((0, 0, pr)), hexc('#fffdf8')), glow=0.45)
    return craft.finish(a, (20, 38, 1.0))


def knot(name):
    """平安结：红绳编的盘长结，平放，长 14 厘米（挂绳朝 +y，穗子朝 -y）。中间是一块斜着的菱形（四横四竖的绳一上一下地穿），
    菱形四边各两个小耳，上面一个挂环，下面一颗金珠、一把穗子"""
    a = Asset(name)
    rng = a.rng
    red, red_l, red_d, gold = C('cloth_red'), hexc('#ec6a55'), C('red_dark'), C('gold')
    h, rr = 0.019, 0.0026
    zc = 0.0062
    ctr = Vector((0, 0.01, 0))
    ex, ey = Vector((1, 1, 0)).normalized(), Vector((-1, 1, 0)).normalized()          # 菱形的两条边的方向
    qs = [-h * 0.75, -h * 0.25, h * 0.25, h * 0.75]

    def P(p, q, z=zc):
        return ctr + ex * p + ey * q + Vector((0, 0, z))
    for j, q in enumerate(qs):
        for (along, cross, par) in ((ex, ey, 0), (ey, ex, 1)):
            pts = []
            for k in range(25):
                p = -h + 2 * h * k / 24
                z = zc + 0.0024 * math.cos(math.pi * (p + h * 0.75) / (h * 0.5)) * (1 if (j + par) % 2 == 0 else -1)
                pts.append(ctr + along * p + cross * q + Vector((0, 0, z)))
            a.tube(pts, rr, red if (j + par) % 2 else red_l, segs=6)
    # 四边的小耳：每边把相邻两根绳头连成一个圈
    for (along, cross) in ((ex, ey), (ey, ex), (-ex, ey), (-ey, ex)):
        for (q0, q1) in ((qs[0], qs[1]), (qs[2], qs[3])):
            qm, w = (q0 + q1) / 2, (q1 - q0) / 2
            pts = [ctr + along * (h + 0.0105 * math.sin(t) * (1.0)) + cross * (qm - w * math.cos(t) * (1 + 0.5 * math.sin(t))) + Vector((0, 0, zc))
                   for t in [math.pi * k / 10 for k in range(11)]]
            a.tube(pts, rr, red, segs=6)
    # 上角的挂环（长）
    top = P(h, h)
    pts = [top + Vector((0.0085 * math.sin(2 * t) * 0.9, 0.019 * (1 - math.cos(t)), 0.001 * math.sin(t))) for t in [math.pi * k / 14 for k in range(15)]]
    a.tube([P(h * 0.75, h)] + pts + [P(h, h * 0.75)], rr * 0.9, red_l, segs=6)
    a.blob(0.004, top + Vector((0, 0.002, 0)), (1, 1, 0.8), red_d, subdiv=2, bump=0)
    # 下角：收成一股，穿一颗金珠，下面一把穗子（上头扎一圈）
    bot = P(-h, -h)
    a.tube([P(-h * 0.75, -h), bot + Vector((0, -0.004, 0)), bot + Vector((0, -0.012, 0))], rr, red, segs=6)
    a.tube([P(-h, -h * 0.75), bot + Vector((0, -0.004, 0))], rr, red, segs=6)
    bead = bot + Vector((0, -0.016, 0.0004))
    a.lathe([(0.0, -0.006), (0.0038, -0.0048, C('gold_dark')), (0.0058, -0.002, gold), (0.0062, 0.0, hexc('#f6dc8a')), (0.0058, 0.002, gold), (0.0038, 0.0048, C('gold_dark')), (0.0, 0.006)],
            bead, segs=14, color=gold, rot=(math.pi / 2, 0, 0))
    hd = bead + Vector((0, -0.0105, -0.0006))
    a.lathe([(0.0, -0.005), (0.0048, -0.004, red_d), (0.0052, 0.0, red), (0.0044, 0.004, red_d), (0.0, 0.005)], hd, segs=12, color=red, rot=(math.pi / 2, 0, 0))
    for k in range(3):
        a.lathe([(0.0054, -0.0007), (0.0058, 0.0, gold), (0.0054, 0.0007)], hd + Vector((0, 0.002 - 0.002 * k, 0)), segs=12, color=gold, rot=(math.pi / 2, 0, 0), outward=True)
    for i in range(22):
        ang = 2 * math.pi * i / 22
        sp = Vector((math.cos(ang) * 0.004, 0, 0.0028 + math.sin(ang) * 0.0024))
        ln = 0.05 * rng.uniform(0.9, 1.05)
        end = hd + Vector((sp.x * 2.6 + rng.uniform(-0.002, 0.002), -0.004 - ln, max(0.0014, sp.z * 0.7)))
        mid = hd + Vector((sp.x * 1.8, -0.004 - ln * 0.5, sp.z * 0.95))
        a.tube([hd + Vector((sp.x, -0.004, sp.z - 0.0022)), mid, end], [0.0011, 0.001, 0.0008], vary(red, rng, 0.04, 0.03), segs=4)
    return craft.finish(a, (8, 55, 1.0), ao=True, dist=0.012, strength=0.45)


ASSETS = {
    'gift_shell_conch': conch, 'gift_pebble': pebble, 'gift_clover': clover, 'gift_pinecone': pinecone, 'gift_ginkgo': ginkgo, 'gift_maple': maple,
    'gift_feather': feather, 'gift_bell': little_bell, 'gift_yarn': yarn, 'gift_pearl': pearl, 'gift_knot': knot,
}
