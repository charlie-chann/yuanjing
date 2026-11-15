"""香炉、石灯笼（高细节版）：顶替 props.py 里同名的两样。

香炉：仿商周青铜鼎。石座是八角须弥座，束腰上一圈覆莲瓣；鼎身是细分很密的旋转体，
口沿下一道回纹带（一个个凸起的方形回旋纹）、腹部三组饕餮纹（凸眼、卷眉、鼻梁、角）、六道带缺口的扉棱，
三条兽足（膝上一张兽面、底下三趾爪），两只立耳，炉口香灰上插着几截残香。凹处顶点色里泛铜绿。
石灯笼：六角，基座覆莲、竿上三道竹节箍、中台仰莲加小佛龛纹、火袋两面圆月窗两面格子窗、笠的六角上翘卷草、顶上宝珠。
"""
import math

from mathutils import Vector

from kit import Asset
from palette import C, mix, tint, vary

VERDIGRIS = (0.36, 0.55, 0.47)


def _ngon(n, r, rot=0.0):
    return [(r * math.cos(rot + 2 * math.pi * i / n), r * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)]


def petal_ring(a, n, r, z, length, width, thick, tilt, color, mat, up=True, rng=None, phase=0.0):
    """一圈莲瓣：每瓣是压扁的团块，瓣尖朝外上翘（仰莲）或朝外下垂（覆莲）"""
    for i in range(n):
        ang = 2 * math.pi * (i + phase) / n
        c = vary(color, rng, 0.03, 0.02) if rng else color
        pitch = math.radians(90 - tilt) * (1 if up else -1)
        a.blob(1.0, (r * math.cos(ang), r * math.sin(ang), z), (width, length, thick), c, top=tint(c, 0.06), subdiv=2, bump=0.0, mat=mat,
               rot=(pitch, 0, ang - math.pi / 2))
        # 瓣中一道脊
        a.blob(1.0, ((r + length * 0.2) * math.cos(ang), (r + length * 0.2) * math.sin(ang), z + (0.2 if up else -0.2) * length * math.cos(pitch)),
               (width * 0.18, length * 0.75, thick * 1.25), tint(c, 0.04), subdiv=1, bump=0.0, mat=mat, rot=(pitch, 0, ang - math.pi / 2))


def burner(name):
    a = Asset(name)
    rng = a.rng
    st, sl, sd = C('stone'), C('stone_lit'), C('stone_dark')
    S = 'stone'
    # ── 须弥座：下枋、下枭（覆莲）、束腰、上枭（仰莲）、上枋 ──
    a.prism(_ngon(8, 1.02, math.pi / 8), 0.0, 0.12, sd, bevel=0.03, top=st, mat=S)
    a.prism(_ngon(8, 0.96, math.pi / 8), 0.12, 0.17, st, bevel=0.02, top=sl, mat=S)
    petal_ring(a, 24, 0.86, 0.2, 0.1, 0.07, 0.03, 35, st, S, up=False, rng=rng)
    a.prism(_ngon(8, 0.78, math.pi / 8), 0.17, 0.33, tint(st, -0.04), bevel=0.015, mat=S)
    # 束腰上每一面一块小壸门（凹进去的海棠形框）
    for i in range(8):
        ang = 2 * math.pi * (i + 0.5) / 8 + math.pi / 8 - math.pi / 8
        cx, cy = 0.79 * math.cos(ang), 0.79 * math.sin(ang)
        a.box((0.32, 0.02, 0.09), (cx, cy, 0.205), rot=(0, 0, ang + math.pi / 2), color=tint(st, -0.12), bevel=0.008, mat=S)
        a.box((0.26, 0.025, 0.06), (cx * 1.003, cy * 1.003, 0.22), rot=(0, 0, ang + math.pi / 2), color=tint(st, 0.02), bevel=0.012, mat=S)
    petal_ring(a, 24, 0.84, 0.37, 0.1, 0.07, 0.03, 35, sl, S, up=True, rng=rng, phase=0.5)
    a.prism(_ngon(8, 0.9, math.pi / 8), 0.36, 0.46, st, bevel=0.025, top=sl, mat=S)

    B = 'bronze'
    bz, bl, bd = C('bronze'), C('bronze_lit'), C('bronze_dark')
    green = mix(bd, VERDIGRIS, 0.55)
    # ── 鼎身 ──
    prof = [(0.0, 0.74, bd), (0.18, 0.742, bd), (0.34, 0.765, green), (0.46, 0.81, bd), (0.55, 0.88, bz), (0.6, 0.96, bz), (0.625, 1.05, bl),
            (0.625, 1.12, bz), (0.61, 1.18, bz), (0.585, 1.22, bd), (0.575, 1.29, bz), (0.58, 1.33, bd), (0.6, 1.36, bz), (0.625, 1.39, bl),
            (0.63, 1.42, bz), (0.615, 1.435, bd), (0.56, 1.43, bd), (0.52, 1.38, bd), (0.5, 1.36)]
    a.lathe(prof, segs=72, color=bz, mat=B)
    a.lathe([(0.0, 1.36, C('ash')), (0.505, 1.36)], segs=48, color=C('ash'), mat='toon')
    # 香灰上的小起伏和几截残香
    for i in range(14):
        ang, rr = rng.uniform(0, 6.28), 0.45 * math.sqrt(rng.random())
        a.blob(rng.uniform(0.03, 0.06), (rr * math.cos(ang), rr * math.sin(ang), 1.36), (1, 1, 0.25), tint(C('ash'), rng.uniform(-0.05, 0.03)), subdiv=1, bump=0.2)
    for i in range(9):
        ang, rr = rng.uniform(0, 6.28), 0.38 * math.sqrt(rng.random())
        h = rng.uniform(0.04, 0.16)
        a.cyl(0.006, h, (rr * math.cos(ang), rr * math.sin(ang), 1.355), (0.62, 0.22, 0.18), segs=6, top=(0.3, 0.28, 0.26))
    # 口沿下的回纹带：48 个方形回旋纹，凸起在鼎面上
    n = 48
    for i in range(n):
        ang = 2 * math.pi * (i + 0.5) / n
        c, s_ = math.cos(ang), math.sin(ang)
        tang = ang + math.pi / 2
        r0 = 0.583
        w = 2 * math.pi * r0 / n * 0.86
        z0 = 1.255
        for (dx, dz, sx, sz) in ((0, 0.024, w, 0.006), (0, -0.024, w, 0.006), (-w / 2, 0, 0.006, 0.054), (w / 2, -0.006, 0.006, 0.042),
                                 (0.002, 0.008, w * 0.62, 0.005), (-w * 0.3, 0, 0.005, 0.02), (0.004, -0.009, w * 0.36, 0.005)):
            px = r0 * c - s_ * dx
            py = r0 * s_ + c * dx
            a.box((sx, 0.012, sz), (px, py, z0 + dz - sz / 2), rot=(0, 0, tang), color=bl, bevel=0.001, mat=B)
    # 回纹带上下两道弦纹
    for z in (1.222, 1.29):
        pts = [(0.586 * math.cos(2 * math.pi * k / 64), 0.586 * math.sin(2 * math.pi * k / 64), z) for k in range(65)]
        a.tube(pts, 0.006, bl, segs=5, mat=B, cap=False)
    # 腹部：三组饕餮纹（两只足之间各一组）
    for g in range(3):
        ang0 = 2 * math.pi * g / 3 + math.pi / 2 + math.pi / 3
        fwd = Vector((math.cos(ang0), math.sin(ang0), 0))
        side = Vector((-math.sin(ang0), math.cos(ang0), 0))
        R = 0.628
        zc = 1.05

        def on(u, dz, out=0.0):
            # 鼎面上的一点：u 是沿圆周的弧长（左负右正），dz 是高度差
            a_ = ang0 + u / R
            return Vector(((R + out) * math.cos(a_), (R + out) * math.sin(a_), zc + dz))
        # 鼻梁
        a.tube([on(0, 0.08, 0.005), on(0, 0.0, 0.012), on(0, -0.08, 0.006)], [0.012, 0.016, 0.011], bl, segs=6, mat=B)
        for sg in (-1, 1):
            # 凸眼：眼眶、眼珠
            a.blob(0.028, on(sg * 0.075, 0.02, 0.002), (1.2, 0.5, 0.8), bd, subdiv=2, bump=0, mat=B)
            a.blob(0.017, on(sg * 0.075, 0.02, 0.014), (1, 0.6, 1), bl, subdiv=2, bump=0, mat=B)
            # 卷眉：从眉心往外卷的一道
            pts = [on(sg * (0.02 + 0.13 * t), 0.06 + 0.03 * math.sin(math.pi * t) - 0.05 * t * t, 0.004) for t in (0, 0.25, 0.5, 0.75, 1.0)]
            ex = pts[-1]
            for k in range(6):
                th = k / 5 * math.pi * 1.4
                pts.append(on(sg * (0.15 - 0.025 * math.sin(th)), 0.0 - 0.025 * (1 - math.cos(th)) + 0.01, 0.004))
            a.tube(pts, 0.0065, bl, segs=5, mat=B)
            # 角：向上外翻
            pts = [on(sg * (0.04 + 0.08 * t), 0.09 + 0.05 * t + 0.02 * math.sin(math.pi * t), 0.003) for t in (0, 0.33, 0.66, 1.0)]
            a.tube(pts, [0.008, 0.009, 0.007, 0.004], bl, segs=5, mat=B)
            # 嘴角两道
            pts = [on(sg * (0.02 + 0.07 * t), -0.07 - 0.02 * math.sin(math.pi * t), 0.004) for t in (0, 0.5, 1.0)]
            a.tube(pts, 0.005, bl, segs=5, mat=B)
            # 底纹：细的云雷纹，填满剩下的地方
            for row in range(3):
                for col in range(3):
                    p0 = on(sg * (0.14 + 0.035 * col), -0.08 + 0.05 * row, 0.003)
                    a.box((0.026, 0.006, 0.026), (p0.x, p0.y, p0.z - 0.013), rot=(0, 0, ang0 + math.pi / 2), color=tint(bz, -0.03), bevel=0.002, mat=B)
    # 扉棱：六道，带缺口
    for i in range(6):
        ang = 2 * math.pi * i / 6 + math.pi / 2
        c, s_ = math.cos(ang), math.sin(ang)
        for k in range(7):
            z = 0.9 + k * 0.042
            r = 0.6 + 0.02 * math.sin(math.pi * (z - 0.88) / 0.32)
            a.box((0.022, 0.05, 0.03), (r * c, r * s_, z), rot=(0, 0, ang), color=bz if k % 2 else bl, bevel=0.004, mat=B)
    # 口沿上的立耳：方环形，里外两道棱
    for sx in (-1, 1):
        for off, rr, cc in ((0.0, 0.034, bz), (0.022, 0.012, bl), (-0.022, 0.012, bl)):
            pts = [(sx * 0.53, off, 1.42), (sx * 0.56, off, 1.56), (sx * 0.6, off, 1.68), (sx * 0.62, off, 1.74), (sx * 0.58, off, 1.78),
                   (sx * 0.5, off, 1.78), (sx * 0.46, off, 1.74), (sx * 0.46, off, 1.64), (sx * 0.47, off, 1.44)]
            a.tube(pts, rr, cc, segs=10, mat=B)
    # 三条兽足
    for i in range(3):
        ang = 2 * math.pi * i / 3 + math.pi / 2
        c, s_ = math.cos(ang), math.sin(ang)
        top, knee, foot = Vector((0.4 * c, 0.4 * s_, 0.84)), Vector((0.5 * c, 0.5 * s_, 0.66)), Vector((0.53 * c, 0.53 * s_, 0.5))
        a.tube([top, (top + knee) / 2 + Vector((0, 0, 0.01)), knee, (knee + foot) / 2, foot], [0.11, 0.09, 0.075, 0.07, 0.085], bd, segs=16, color2=bz, mat=B)
        # 膝上的兽面：鼓起的额头、两只眼、鼻
        out = Vector((c, s_, 0))
        side = Vector((-s_, c, 0))
        fc = knee + out * 0.07 + Vector((0, 0, 0.06))
        a.blob(0.06, fc, (1, 0.7, 0.9), bz, top=bl, subdiv=2, bump=0.05, mat=B)
        for sg in (-1, 1):
            a.blob(0.016, fc + out * 0.04 + side * sg * 0.028 + Vector((0, 0, 0.01)), (1, 1, 1), bl, subdiv=2, bump=0, mat=B)
            a.tube([fc + out * 0.035 + side * sg * 0.01 + Vector((0, 0, 0.04)), fc + out * 0.02 + side * sg * 0.06 + Vector((0, 0, 0.07))], [0.008, 0.004], bl, segs=5, mat=B)
        a.blob(0.014, fc + out * 0.055 - Vector((0, 0, 0.015)), (1, 1.2, 0.8), bl, subdiv=2, bump=0, mat=B)
        # 爪：三趾
        for k in (-1, 0, 1):
            d = (out + side * k * 0.6).normalized()
            p0 = foot - Vector((0, 0, 0.02))
            a.tube([p0, p0 + d * 0.06 + Vector((0, 0, -0.02)), p0 + d * 0.1 + Vector((0, 0, -0.035))], [0.03, 0.024, 0.012], bd, segs=8, mat=B)
    # 铜绿：鼎身下半、凹处泛绿（直接改顶点色：越低、越朝下越绿，加点斑驳）
    b = a.parts.get(B)
    if b is not None:
        col = b.loops.layers.float_color['col']
        from mathutils import noise
        for f in b.faces:
            for l in f.loops:
                p = l.vert.co
                k = max(0.0, min(1.0, (1.0 - p.z) * 1.3)) * 0.55 + max(0.0, -f.normal.z) * 0.3
                k += 0.35 * noise.noise(p * 9.0)
                k = max(0.0, min(0.85, k))
                cc = l[col]
                m = mix((cc[0], cc[1], cc[2]), VERDIGRIS, k * 0.6)
                l[col] = (m[0], m[1], m[2], cc[3])
    return a.finish(dist=0.8, view=(20, 25, 0.9))


def lantern(name):
    """石灯笼：高约 1.9 米（Unity 里再放大 1.25 倍）。灯室（发光的方块）位置、大小不变"""
    a = Asset(name)
    rng = a.rng
    st, sl, sd = C('stone'), C('stone_lit'), C('stone_dark')
    S = 'stone'
    moss = mix(st, C('moss'), 0.55)
    # 基座：六角，两层，上面一圈覆莲
    a.prism(_ngon(6, 0.38), 0, 0.08, sd, bevel=0.02, top=st, mat=S)
    a.prism(_ngon(6, 0.33), 0.08, 0.17, st, bevel=0.02, top=sl, mat=S)
    petal_ring(a, 12, 0.24, 0.19, 0.075, 0.055, 0.025, 30, sl, S, up=False, rng=rng)
    a.lathe([(0.15, 0.17), (0.17, 0.2), (0.14, 0.24)], segs=36, color=st, mat=S)
    # 竿：圆柱，中间三道竹节箍
    a.lathe([(0.115, 0.23), (0.105, 0.42), (0.1, 0.62), (0.105, 0.82), (0.115, 0.92)], segs=36, color=st, mat=S)
    for z in (0.42, 0.57, 0.72):
        a.lathe([(0.105, z - 0.015), (0.122, z - 0.006), (0.124, z), (0.122, z + 0.006), (0.105, z + 0.015)], segs=36, color=sl, mat=S)
    # 竿下半截一片青苔
    for i in range(10):
        ang = rng.uniform(-1.0, 1.0)
        a.blob(rng.uniform(0.02, 0.035), (0.105 * math.cos(ang), 0.105 * math.sin(ang), rng.uniform(0.25, 0.45)), (0.4, 1, 1), moss, subdiv=1, bump=0.3)
    # 中台：六角，仰莲，每面一个小龛
    a.lathe([(0.12, 0.92), (0.2, 0.95), (0.22, 0.97)], segs=36, color=st, mat=S)
    petal_ring(a, 12, 0.2, 0.97, 0.07, 0.05, 0.022, 35, sl, S, up=True, rng=rng)
    a.prism(_ngon(6, 0.31), 0.98, 1.1, st, bevel=0.018, top=sl, mat=S)
    for i in range(6):
        ang = 2 * math.pi * (i + 0.5) / 6
        cx, cy = 0.27 * math.cos(ang), 0.27 * math.sin(ang)
        a.box((0.13, 0.015, 0.07), (cx, cy, 1.005), rot=(0, 0, ang + math.pi / 2), color=tint(st, -0.14), bevel=0.006, mat=S)
        a.blob(0.022, (cx * 1.03, cy * 1.03, 1.04), (1, 0.5, 1.3), sl, subdiv=2, bump=0.02, mat=S)
    # 火袋：灯室（发光）+ 四根角柱 + 两面圆月窗、两面格子窗 + 上下枋
    a.box((0.3, 0.3, 0.3), (0, 0, 1.1), color=C('glow'), bevel=0.0, mat='glow', glow=1.0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            a.box((0.06, 0.06, 0.32), (sx * 0.155, sy * 0.155, 1.1), color=st, bevel=0.01, mat=S)
    for i in range(4):
        ang = i * math.pi / 2
        n = (math.sin(ang), -math.cos(ang))
        for z in (1.1, 1.385):
            a.box((0.36, 0.045, 0.045), (0.168 * n[0], 0.168 * n[1], z), rot=(0, 0, ang), color=st, bevel=0.008, mat=S)
        if i % 2 == 0:
            # 圆月窗：一圈石框
            pts = [(0.17 * n[0] + 0.08 * math.cos(t) * math.cos(ang), 0.17 * n[1] + 0.08 * math.cos(t) * math.sin(ang), 1.25 + 0.08 * math.sin(t))
                   for t in [2 * math.pi * k / 40 for k in range(41)]]
            a.tube(pts, 0.012, sl, segs=6, mat=S, cap=False)
            # 框外四角的石板（窗是在一块石板上开的圆洞）
            for (u, v) in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                a.box((0.05, 0.02, 0.05), (0.168 * n[0] + u * 0.1 * math.cos(ang), 0.168 * n[1] + u * 0.1 * math.sin(ang), 1.25 + v * 0.1 - 0.025),
                      rot=(0, 0, ang), color=st, bevel=0.006, mat=S)
        else:
            # 格子窗
            for k in (-1, 0, 1):
                a.box((0.012, 0.02, 0.24), (0.17 * n[0] + k * 0.06 * math.cos(ang), 0.17 * n[1] + k * 0.06 * math.sin(ang), 1.13), rot=(0, 0, ang),
                      color=sl, bevel=0.003, mat=S)
            for z in (1.19, 1.25, 1.31):
                a.box((0.24, 0.02, 0.012), (0.17 * n[0], 0.17 * n[1], z), rot=(0, 0, ang), color=sl, bevel=0.003, mat=S)
    # 笠：六角攒尖，檐角上翘、尖上一个卷草
    a.roof(0.3, 0.3, 0.24, z=1.42, lift=0.08, pitch=0.42, amp=0.0, rows=5, thick=0.07, ca=sd, cb=st, eave=sd, under=sd, ridge=sd,
           ridge_r=0.032, tip=0.05, finial=False, mat=S, hips=False)
    # 四条垂脊：从顶到檐角，贴着屋面
    for sx in (-1, 1):
        for sy in (-1, 1):
            pts = [(sx * 0.3 * k, sy * 0.3 * k, 1.42 + 0.24 * (1 - k) ** 1.6 + 0.08 * k ** 3 + 0.03) for k in (0.0, 0.3, 0.6, 0.85, 1.0)]
            a.tube(pts, [0.028, 0.026, 0.024, 0.022, 0.02], st, segs=8, mat=S)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p0 = Vector((sx * 0.3, sy * 0.3, 1.53))
            d = Vector((sx, sy, 0)).normalized()
            pts = [p0 + d * (0.03 * math.cos(t)) + Vector((0, 0, 0.035 * math.sin(t) + 0.01 * t)) for t in [k / 10 * 4.5 for k in range(11)]]
            a.tube(pts, [0.016 - 0.0012 * k for k in range(11)], st, segs=6, mat=S)
    # 宝珠：请花（一圈小仰莲）+ 桃形的珠
    petal_ring(a, 8, 0.05, 1.68, 0.04, 0.03, 0.015, 40, sl, S, up=True, rng=rng)
    a.lathe([(0.0, 1.66), (0.05, 1.67), (0.07, 1.71), (0.075, 1.76), (0.06, 1.81), (0.03, 1.85), (0.008, 1.88), (0.0, 1.89)], segs=32, color=sl, mat=S)
    return a.finish(dist=0.6, view=(20, 20, 0.9))


ASSETS = {'burner': burner, 'lantern': lantern}
