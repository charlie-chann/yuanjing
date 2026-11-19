"""器物和小摆设：石头、石灯笼、香炉、蒲团、码头、小船、牌坊、石板路……"""
import math

from kit import Asset
from palette import C, tint, mix, vary


def rocks(name):
    """一组石头：大中小各几块，场景里挑着摆"""
    total = 0
    sizes = {'a': (1.5, 1.2, 0.95), 'b': (1.0, 0.85, 0.6), 'c': (0.62, 0.55, 0.38), 'd': (2.3, 1.7, 1.5), 'e': (0.36, 0.3, 0.2)}
    for k, s in sizes.items():
        a = Asset(f'rock_{k}')
        a.rock(s, color=vary(C('stone'), a.rng), top=C('stone_lit'), n=30 if k in 'ad' else 22)
        if k in 'ad':
            a.rock((s[0] * 0.5, s[1] * 0.5, s[2] * 0.45), loc=(s[0] * 0.42, -s[1] * 0.3, 0), color=C('stone_dark'), top=C('stone'), n=18)
            a.rock((s[0] * 0.3, s[1] * 0.32, s[2] * 0.25), loc=(-s[0] * 0.45, -s[1] * 0.34, 0), color=C('stone'), top=C('stone_lit'), n=16)
        total += a.finish()
    # 长了青苔的
    a = Asset('rock_moss')
    a.rock((1.3, 1.1, 0.8), color=C('stone_dark'), top=C('moss'), n=28)
    a.rock((0.6, 0.5, 0.4), loc=(0.62, 0.3, 0), color=C('stone'), top=C('moss'), n=18)
    total += a.finish()
    return total


def lantern(name):
    """石灯笼：夜里灯室会亮"""
    a = Asset(name)
    st, sl, sd = C('stone'), C('stone_lit'), C('stone_dark')
    a.prism(_ngon(6, 0.36), 0, 0.12, sd, bevel=0.03, top=st)
    a.prism(_ngon(6, 0.27), 0.12, 0.22, st, bevel=0.03, top=sl)
    a.lathe([(0.12, 0.22), (0.105, 0.5), (0.10, 0.8), (0.13, 0.95), (0.21, 1.02)], segs=10, color=st)
    a.prism(_ngon(6, 0.31), 1.02, 1.1, st, bevel=0.025, top=sl)
    a.box((0.3, 0.3, 0.3), (0, 0, 1.1), color=C('glow'), bevel=0.0, mat='glow', glow=1.0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            a.box((0.075, 0.075, 0.32), (sx * 0.15, sy * 0.15, 1.1), color=st, bevel=0.012)
    for i in range(4):
        ang = i * math.pi / 2
        a.box((0.34, 0.04, 0.05), (0.165 * math.sin(ang), -0.165 * math.cos(ang), 1.1), rot=(0, 0, ang), color=st, bevel=0.01)
        a.box((0.34, 0.04, 0.05), (0.165 * math.sin(ang), -0.165 * math.cos(ang), 1.37), rot=(0, 0, ang), color=st, bevel=0.01)
    a.roof(0.29, 0.29, 0.22, z=1.42, lift=0.07, pitch=0.4, amp=0.0, rows=4, thick=0.06, ca=sd, cb=st, eave=sd, under=sd,
           ridge=sd, ridge_r=0.03, tip=0.12, finial=False)
    a.lathe([(0.0, 0), (0.07, 0.02), (0.085, 0.09), (0.04, 0.15), (0.0, 0.22)], (0, 0, 1.66), segs=8, color=sl)
    return a.finish()


def _ngon(n, r, rot=0.0, sx=1.0, sy=1.0):
    return [(r * sx * math.cos(rot + 2 * math.pi * i / n), r * sy * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)]


def burner(name):
    """香炉：石座上一只三足铜鼎，炉口一层香灰（香就插在这里，高度 Unity 那边要用）"""
    a = Asset(name)
    st, sl = C('stone'), C('stone_lit')
    a.prism(_ngon(8, 1.0, math.pi / 8), 0.1, 0.3, C('stone_dark'), bevel=0.05, top=st, segs=2)
    a.prism(_ngon(8, 0.8, math.pi / 8), 0.3, 0.46, st, bevel=0.05, top=sl, segs=2)
    bz, bl, bd = C('bronze'), C('bronze_lit'), C('bronze_dark')
    for i in range(3):
        ang = 2 * math.pi * i / 3 + math.pi / 2
        x, y = 0.4 * math.cos(ang), 0.4 * math.sin(ang)
        a.tube([(x * 1.25, y * 1.25, 0.46), (x * 1.2, y * 1.2, 0.62), (x, y, 0.82)], [0.1, 0.085, 0.12], bd, segs=8, color2=bz)
    a.lathe([(0.0, 0.74), (0.3, 0.74, bd), (0.52, 0.86, bz), (0.62, 1.05, bl), (0.6, 1.2, bz), (0.5, 1.3, bd), (0.52, 1.34, C('gold_dark')),
             (0.6, 1.38, bz), (0.6, 1.43, bz), (0.52, 1.43, bd), (0.5, 1.36)], segs=20, color=bz)
    # 香灰：只一层（叠两层在同一高度会闪）
    a.lathe([(0.0, 1.36, C('ash')), (0.505, 1.36)], segs=20, color=C('ash'))
    # 腰上一圈乳钉
    for i in range(12):
        ang = 2 * math.pi * i / 12
        a.blob(0.045, (0.615 * math.cos(ang), 0.615 * math.sin(ang), 1.08), (1, 1, 1), C('gold_dark'), subdiv=1, bump=0)
    # 两只耳
    for sx in (-1, 1):
        pts = [(sx * 0.56, 0, 1.4), (sx * 0.66, 0, 1.52), (sx * 0.68, 0, 1.68), (sx * 0.6, 0, 1.76), (sx * 0.52, 0, 1.68), (sx * 0.52, 0, 1.44)]
        a.tube(pts, 0.04, bz, segs=6)
    return a.finish(dist=0.8)


def cushion(name):
    """蒲团：下面一张方的草编坐垫（膝盖和脚放在上面），上面靠后一个圆的蒲团（臀坐在上面）。
    尺寸 Unity 那边要用（BuildIslet.cs 的座位、Tests/PlaythroughTest.cs 的穿模检查）：
    方垫 0.8×0.8、厚 0.05，中心在原点往 +y（朝大殿）0.12；圆蒲团半径 0.2、顶面高 0.18，中心在原点。"""
    a = Asset(name)
    # 蒲草的本色：比别处的稻草黄淡一些、灰一些（评审：六十个金黄的蒲团排成方阵，俯视像棋盘）
    s1, s2, s3 = tint(C('straw'), -0.04, -0.2), tint(C('straw_lit'), -0.03, -0.2), tint(C('straw_dark'), -0.04, -0.16)
    # 方垫：四边包一圈深色的布边，中间草编
    a.box((0.8, 0.8, 0.05), (0, 0.12, 0), color=s1, bevel=0.012, top=s2, segs=2)
    for (w, d, x, y) in ((0.8, 0.05, 0, 0.12 - 0.375), (0.8, 0.05, 0, 0.12 + 0.375), (0.05, 0.7, -0.375, 0.12), (0.05, 0.7, 0.375, 0.12)):
        a.box((w, d, 0.053), (x, y, 0), color=s3, bevel=0.01)
    # 圆蒲团：一圈一圈的草编，顶上被坐得微微凹下去
    prof = [(0.0, 0.05), (0.17, 0.05, s3), (0.2, 0.07, s1), (0.205, 0.11, s3), (0.195, 0.15, s2), (0.17, 0.172, s1), (0.12, 0.18, s2),
            (0.07, 0.176, s1), (0.0, 0.172)]
    a.lathe(prof, segs=28, color=s1)
    return a.finish(dist=0.4)


def koi(name):
    """锦鲤：头朝 +y。原点在身体中间"""
    total = 0
    for v, (body, patch) in {'a': (C('koi'), C('koi_w')), 'b': (C('koi_w'), C('koi_r')), 'c': (C('gold'), C('koi')), 'd': (C('koi_r'), C('koi_w'))}.items():
        a = Asset(f'koi_{v}')
        rng = a.rng
        prof = []
        n = 9
        for i in range(n + 1):
            t = i / n
            r = 0.085 * (math.sin(math.pi * (0.08 + 0.86 * t)) ** 0.8) * (1.25 - 0.5 * t)
            prof.append((max(0.004, r), -0.3 + 0.6 * (1 - t), patch if rng.random() < 0.38 else body))
        prof = list(reversed(prof))
        a.lathe([(0.0, prof[0][1] - 0.01)] + prof + [(0.0, prof[-1][1] + 0.02)], segs=8, color=body, rot=(-math.pi / 2, 0, 0), squash=(1.0, 0.7))
        tail = tint(body, 0.06)
        a.quad([(0, -0.28, 0), (0.1, -0.46, 0.0), (0, -0.4, 0), (-0.1, -0.46, 0.0)], color=tail, mat='toon')
        for sx in (-1, 1):
            a.quad([(sx * 0.06, 0.1, -0.01), (sx * 0.17, 0.02, -0.02), (sx * 0.07, 0.02, -0.01)], color=tail, mat='toon')
        a.quad([(0, 0.08, 0.055), (0.012, -0.08, 0.09), (0, -0.14, 0.05), (-0.012, -0.08, 0.09)], color=patch, mat='toon')
        total += a.finish(ao=False, view=(20, 60, 1.0), floor=False)
    return total


def fence(name):
    """矮竹篱：一段 2 米，沿 x 方向"""
    a = Asset(name)
    rng = a.rng
    bm, bd = C('bamboo'), C('bamboo_dark')
    for i in range(9):
        x = -1.0 + i * 0.25
        h = 0.5 + rng.uniform(-0.04, 0.05)
        a.cyl(0.028, h, (x, 0, 0), mix(bd, C('straw'), 0.5), segs=6, top=C('straw_lit'))
    for z in (0.16, 0.38):
        a.tube([(-1.06, 0.035, z), (1.06, 0.035, z)], 0.024, mix(bm, C('straw'), 0.55), segs=6)
    for i in (0, 4, 8):
        x = -1.0 + i * 0.25
        for z in (0.16, 0.38):
            a.lathe([(0.04, 0), (0.05, 0.015), (0.04, 0.03)], (x, 0.015, z - 0.015), segs=6, color=C('rope_dark'))
    return a.finish(dist=0.5)


def stele(name):
    """石碑：龟趺座上一块碑"""
    a = Asset(name)
    st, sl, sd = C('stone'), C('stone_lit'), C('stone_dark')
    a.box((1.2, 0.8, 0.22), color=sd, bevel=0.05, segs=2, top=st)
    a.box((0.9, 0.5, 0.16), (0, 0, 0.22), color=st, bevel=0.04, top=sl)
    a.box((0.7, 0.2, 1.5), (0, 0, 0.38), color=st, bevel=0.03, grad=(sd, sl))
    a.box((0.56, 0.22, 1.1), (0, 0, 0.5), color=tint(sd, -0.03), bevel=0.01)
    a.cyl(0.36, 0.24, (0, 0.12, 1.86), sl, segs=14, rot=(math.pi / 2, 0, 0), bevel=0.03)
    for i in range(5):
        a.box((0.34, 0.24, 0.035), (0, 0, 0.66 + i * 0.18), color=sl, bevel=0.0)
    return a.finish()


def hat(name):
    """斗笠：原点在头顶接触的地方"""
    a = Asset(name)
    s1, s2, s3 = C('straw'), C('straw_lit'), C('straw_dark')
    a.lathe([(0.0, 0.2, s2), (0.07, 0.17, s1), (0.15, 0.12, s2), (0.23, 0.07, s1), (0.31, 0.02, s2), (0.37, -0.02, s3), (0.375, -0.035, s3), (0.3, 0.0, s3),
             (0.1, 0.1, s3), (0.0, 0.14)], segs=16, color=s1)
    return a.finish(ao=False)


def beach_bits(name):
    """沙滩上的小东西：一小堆卵石、贝壳、海星"""
    total = 0
    a = Asset('pebbles')
    rng = a.rng
    for i in range(7):
        ang = rng.uniform(0, 6.28)
        d = rng.uniform(0, 0.45)
        s = rng.uniform(0.08, 0.2)
        a.rock((s, s * rng.uniform(0.7, 1.0), s * 0.55), loc=(d * math.cos(ang), d * math.sin(ang), -0.01), color=vary(rng.choice([C('stone'), C('stone_lit'), C('slab_b'), C('stone_dark')]), rng, 0.05),
               n=12, bevel=0.12, rot=rng.uniform(0, 3.14))
    total += a.finish(dist=0.3)
    a = Asset('shells')
    rng = a.rng
    for i in range(3):
        ang = rng.uniform(0, 6.28)
        d = rng.uniform(0.05, 0.4)
        x, y = d * math.cos(ang), d * math.sin(ang)
        c = rng.choice([C('white'), C('blossom_lit'), C('flower_y')])
        # 扇贝：半个扁圆锥
        a.lathe([(0.0, 0.035), (0.05, 0.03, c), (0.09, 0.012, tint(c, -0.05)), (0.1, 0.0)], (x, y, 0.0), segs=9, color=c, rot=(0, 0, rng.uniform(0, 6.28)), squash=(1.0, 0.8))
    # 海星
    c = C('maple_lit')
    pts = []
    for k in range(10):
        ang = 2 * math.pi * k / 10
        r = 0.12 if k % 2 == 0 else 0.045
        pts.append((r * math.cos(ang), r * math.sin(ang)))
    a.prism(pts, 0.0, 0.03, tint(c, -0.08), bevel=0.012, top=c, loc=(0.3, -0.25, 0))
    total += a.finish(dist=0.3)
    return total


def details(name):
    """让院子有人气的小东西：洗手的石钵、长凳、扫帚、木牌架、指路牌、落叶、蘑菇"""
    total = 0
    st, sl, sd = C('stone'), C('stone_lit'), C('stone_dark')
    # 石钵：一块凿空的石头盛着水，竹筒往里滴水，上面搁一把竹勺
    a = Asset('basin')
    a.rock((1.1, 0.95, 0.62), color=sd, top=st, n=30, bevel=0.05, sink=0.05)
    a.lathe([(0.0, 0.5, C('lakebed')), (0.3, 0.5, sl), (0.36, 0.56, sl), (0.4, 0.58, st), (0.42, 0.54)], segs=14, color=sl)
    a.lathe([(0.0, 0.535, mix(C('lakebed'), C('white'), 0.35)), (0.3, 0.535)], segs=14, color=C('lakebed'))
    bm, bd = C('bamboo'), C('bamboo_dark')
    a.cyl(0.035, 0.95, (-0.55, 0.1, 0), bd, segs=7, grad=(bd, bm))
    a.tube([(-0.55, 0.1, 0.86), (-0.3, 0.06, 0.8), (-0.12, 0.03, 0.74)], 0.028, bm, segs=7)
    for z in (0.3, 0.6):
        a.cyl(0.04, 0.02, (-0.55, 0.1, z), tint(bd, -0.06), segs=7)
    a.tube([(0.5, -0.2, 0.6), (0.1, -0.02, 0.62)], 0.012, C('straw'), segs=5)
    a.lathe([(0.0, 0.0), (0.05, 0.0, C('straw_dark')), (0.055, 0.06, C('straw')), (0.045, 0.06), (0.04, 0.012), (0.0, 0.012)], (0.06, 0.0, 0.59), segs=8, color=C('straw'))
    for i in range(5):
        ang = i * 1.3
        a.rock((0.22, 0.18, 0.12), loc=(0.62 * math.cos(ang), 0.56 * math.sin(ang), 0), color=vary(st, a.rng, 0.05), top=C('moss') if i % 2 else sl, n=14)
    total += a.finish(dist=0.6)
    # 长凳
    a = Asset('bench')
    w, wl, wd = C('wood'), C('wood_lit'), C('wood_dark')
    for i, y in enumerate((-0.13, 0.0, 0.13)):
        a.box((1.5, 0.115, 0.045), (0, y, 0.4), color=vary(w, a.rng, 0.04), bevel=0.012, top=vary(wl, a.rng, 0.03))
    for sx in (-0.6, 0.6):
        a.box((0.07, 0.36, 0.4), (sx, 0, 0), color=wd, bevel=0.012)
        a.box((0.09, 0.42, 0.05), (sx, 0, 0), color=wd, bevel=0.012)
    a.box((1.2, 0.05, 0.06), (0, 0, 0.16), color=wd, bevel=0.01)
    total += a.finish(dist=0.5)
    # 扫帚：靠在什么东西上的，这里先斜着立
    a = Asset('broom')
    a.tube([(0, 0, 0.32), (0.05, 0.0, 1.5)], 0.016, C('bamboo_dark'), segs=6, color2=C('straw'))
    for i in range(14):
        ang = a.rng.uniform(0, 6.28)
        r = a.rng.uniform(0.02, 0.16)
        a.tube([(0, 0, 0.36), (r * math.cos(ang) * 0.5, r * math.sin(ang) * 0.5, 0.2), (r * math.cos(ang), r * math.sin(ang), 0.0)], 0.009,
               vary(C('straw_dark'), a.rng, 0.05), segs=4)
    a.lathe([(0.03, 0), (0.04, 0.01), (0.04, 0.05), (0.03, 0.06)], (0, 0, 0.33), segs=6, color=C('rope_dark'))
    total += a.finish(ao=False)
    # 木牌架：两根柱子三道横杆，挂满写了愿望的小木牌
    a = Asset('plaque_rack')
    for sx in (-1.0, 1.0):
        a.box((0.1, 0.1, 1.75), (sx, 0, 0), color=wd, bevel=0.015, grad=(C('wood_deep'), w))
        a.box((0.2, 0.2, 0.08), (sx, 0, 0), color=sd, bevel=0.02, top=st)
    a.roof(1.25, 0.24, 0.16, z=1.78, lift=0.05, pitch=0.3, amp=0.012, rows=2, thick=0.04, ridge_r=0.03, tip=0.1, course=0.12)
    for row, z in enumerate((1.55, 1.12, 0.7)):
        a.box((2.0, 0.05, 0.045), (0, 0, z), color=w, bevel=0.01)
        n = 9
        for i in range(n):
            x = -0.85 + 1.7 * i / (n - 1) + a.rng.uniform(-0.03, 0.03)
            if a.rng.random() < 0.15:
                continue
            c = vary(a.rng.choice([C('plank_c'), C('wood_lit'), C('paper')]), a.rng, 0.04)
            tilt = a.rng.uniform(-0.12, 0.12)
            for side in (-1, 1):
                p0 = (x, side * 0.035, z - 0.02)
                a.quad([(x - 0.07, side * 0.035, z - 0.3), (x + 0.07, side * 0.035, z - 0.3), (x + 0.07 + tilt * 0.02, side * 0.035, z - 0.1),
                        (x, side * 0.035, z - 0.05), (x - 0.07 + tilt * 0.02, side * 0.035, z - 0.1)], mat='leaf',
                       colors=[tint(c, -0.06)] * 2 + [c, tint(c, 0.04), c], sway=(0.5, 0.5, 0.15, 0.0, 0.15))
            a.cyl(0.006, 0.07, (x, 0, z - 0.06), C('cloth_red'), segs=4)
    a.opts['leaf'] = {'normal_up': 0.3, 'plain_normals': True}
    total += a.finish(dist=0.6, view=(20, 30, 1.0))
    # 指路牌
    a = Asset('signpost')
    a.box((0.09, 0.09, 1.5), color=wd, bevel=0.015, grad=(C('wood_deep'), w))
    a.rock((0.4, 0.36, 0.2), color=st, top=C('moss'), n=14)
    for z, ang, c in ((1.2, 0.25, C('plank_c')), (0.95, -2.7, C('plank'))):
        a.prism([(-0.36, -0.07), (0.28, -0.07), (0.4, 0.0), (0.28, 0.07), (-0.36, 0.07)], -0.018, 0.018, tint(c, -0.1), top=c, bevel=0.008,
                loc=(0.0, -0.065, z), rot=(math.pi / 2, 0, ang))
    total += a.finish(dist=0.5)
    # 落叶：贴在地上的一小片
    for v, cols in {'green': [C('leaf'), C('leaf_lit'), C('ginkgo')], 'maple': [C('maple'), C('maple_lit'), C('maple_dark')],
                    'ginkgo': [C('ginkgo'), C('ginkgo_lit'), C('maple_lit')], 'petal': [C('blossom'), C('blossom_lit'), C('white')]}.items():
        a = Asset(f'fallen_{v}')
        rng = a.rng
        for i in range(16):
            ang = rng.uniform(0, 6.28)
            d = 1.1 * math.sqrt(rng.random())
            x, y = d * math.cos(ang), d * math.sin(ang)
            r = rng.uniform(0, 6.28)
            s = rng.uniform(0.05, 0.09) if v != 'petal' else rng.uniform(0.03, 0.05)
            c = vary(rng.choice(cols), rng, 0.05)
            dx, dy = math.cos(r) * s, math.sin(r) * s
            px, py = -dy * 0.55, dx * 0.55
            z = 0.012 + 0.002 * i
            a.quad([(x - dx, y - dy, z), (x + px, y + py, z + 0.004), (x + dx, y + dy, z), (x - px, y - py, z + 0.004)], mat='leaf',
                   colors=[tint(c, -0.06), c, tint(c, 0.06), c], sway=(0, 0, 0, 0))
        a.opts['leaf'] = {'normal_up': 1.0, 'plain_normals': True}
        total += a.finish(ao=False)
    # 蘑菇
    a = Asset('mushrooms')
    for i, (x, y, s, c) in enumerate(((0, 0, 1.0, C('cloth_red')), (0.12, 0.06, 0.7, C('cloth_red')), (-0.1, 0.09, 0.55, C('maple_lit')), (0.03, -0.12, 0.45, C('paper')))):
        a.cyl(0.018 * s, 0.09 * s, (x, y, 0), C('paper'), r2=0.014 * s, segs=6)
        a.lathe([(0.0, 0.085 * s), (0.065 * s, 0.085 * s, tint(c, -0.1)), (0.07 * s, 0.1 * s, c), (0.045 * s, 0.135 * s, tint(c, 0.06)), (0.0, 0.15 * s)], (x, y, 0), segs=9, color=c)
        if i < 2:
            for q in range(4):
                ang = q * 1.7 + i
                a.blob(0.009 * s, (x + 0.04 * s * math.cos(ang), y + 0.04 * s * math.sin(ang), 0.128 * s), (1, 1, 0.5), C('white'), subdiv=1, bump=0)
    total += a.finish(dist=0.2)
    return total


ASSETS = {'rocks': rocks, 'lantern': lantern, 'burner': burner, 'cushion': cushion, 'koi': koi, 'fence': fence, 'stele': stele, 'hat': hat, 'beach_bits': beach_bits, 'details': details}
