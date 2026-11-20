"""小岛的地面和铺地。这两件是整块的，位置就是世界坐标，Unity 里放在原点。"""
import math
import random

import bmesh
from mathutils import Vector, noise

import layout as L
from kit import Asset, new_bm, paint
from palette import C, tint, mix, vary


def _n(x, y, f, seed=0.0):
    return noise.noise(Vector((x * f + seed, y * f - seed * 0.7, seed * 1.3)))


def ground_color(x, y, h):
    d = L.shore_dist(x, y)
    # 草地：大块的深浅变化
    a = _n(x, y, 0.11, 3.0)
    b = _n(x, y, 0.33, 9.0)
    g = mix(C('grass'), C('grass_lit'), L.smooth(-0.1, 0.5, a + b * 0.4))
    g = mix(g, C('grass_dark'), L.smooth(0.15, 0.6, -a + b * 0.3))
    # 人常走的地方露出土色
    worn = 0.0
    if L.PATH_Y0 - 1 < y < L.PATH_Y1 + 0.5:
        worn = max(worn, 1 - L.smooth(L.PATH_W + 0.2, L.PATH_W + 1.5, abs(x)))
    worn = max(worn, 1 - L.smooth(L.PLAZA_R + 0.2, L.PLAZA_R + 1.6, math.hypot(x - L.BURNER[0], y - L.BURNER[1])))
    tx0, ty0, tx1, ty1 = L.TERRACE
    dx = max(tx0 - x, 0, x - tx1)
    dy = max(ty0 - y, 0, y - (ty1 + 2.2))
    worn = max(worn, 1 - L.smooth(0.2, 1.5, math.hypot(dx, dy)))
    worn = max(worn, 1 - L.smooth(L.TREE_BED + 0.3, L.TREE_BED + 1.4, math.hypot(x - L.TREE[0], y - L.TREE[1])))
    # 大殿台基脚下一圈：绕殿走的人踩出来的土（比路淡）
    hx0, hy0, hx1, hy1 = L.HALL_RECT
    hdx = max(hx0 - x, 0, x - hx1)
    hdy = max(hy0 - y, 0, y - hy1)
    worn = max(worn, 0.8 * (1 - L.smooth(0.3, 1.5, math.hypot(hdx, hdy))))
    worn *= L.smooth(-0.6, 0.1, _n(x, y, 0.7, 5.0) + worn * 1.2 - 0.6)
    g = mix(g, mix(C('dirt'), C('dirt_dark'), 0.5 + 0.5 * _n(x, y, 0.5, 2.0)), worn * 0.9)
    # 土丘上草更深
    if h > 0.15:
        g = mix(g, C('grass_deep'), L.smooth(0.15, 1.0, h) * 0.7)
    # 岸边是沙
    edge = d + _n(x, y, 0.45, 1.0) * 0.7
    c = mix(C('sand'), g, L.smooth(2.5, 3.5, edge))
    # 池塘边一圈泥沙
    pd = L.pond_dist(x, y)
    c = mix(c, C('sand_wet'), L.smooth(-1.0, -0.2, pd + _n(x, y, 0.9, 4.0) * 0.3))
    if pd > 0:
        c = mix(c, C('lakebed'), L.smooth(0.0, 0.8, pd))
    # 水线附近的湿沙，再往下是水底
    if h < L.WATER + 0.16:
        c = mix(c, C('sand_wet'), L.smooth(L.WATER + 0.16, L.WATER + 0.02, h))
    if h < L.WATER:
        depth = L.WATER - h
        c = mix(c, C('sand_deep'), L.smooth(0.0, 0.5, depth))
        c = mix(c, C('lakebed'), L.smooth(0.4, 1.3, depth))
        c = mix(c, C('lakebed_deep'), L.smooth(1.2, 2.8, depth))
        c = tint(c, 0.03 * _n(x, y, 1.1, 6.0))
    return c


def export_map():
    """把地形数据存一份给 Unity（撒草、围边界时要知道哪里是岸、哪里是水）。
    格式：nx ny（整数），x0 y0 step（小数），然后三张表：高度、离岸多远、离池塘边多远"""
    import os
    import struct
    from kit import OUT
    step = 0.5
    x0, y0, x1, y1 = L.EXTENT
    nx, ny = int((x1 - x0) / step) + 1, int((y1 - y0) / step) + 1
    hs, sd, pd = [], [], []
    for j in range(ny):
        for i in range(nx):
            x, y = x0 + i * step, y0 + j * step
            hs.append(L.height(x, y))
            sd.append(L.shore_dist(x, y))
            pd.append(L.pond_dist(x, y))
    # 平时放在 Assets/Toon/（模型目录的上一层）；设了 YJ_OUT（导到暂存目录）就放在那个目录里，不碰 Unity 工程
    path = os.path.join(OUT, 'islet_map.bytes') if os.environ.get('YJ_OUT') else os.path.join(OUT, '..', 'islet_map.bytes')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(struct.pack('<ii3f', nx, ny, x0, y0, step))
        for arr in (hs, sd, pd):
            f.write(struct.pack(f'<{len(arr)}f', *arr))


def ground(name):
    a = Asset(name)
    t = new_bm()
    col = t.loops.layers.float_color['col']
    step = 0.5
    x0, y0, x1, y1 = L.EXTENT
    nx, ny = int((x1 - x0) / step), int((y1 - y0) / step)
    grid = []
    colors = {}
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            x, y = x0 + i * step, y0 + j * step
            h = L.height(x, y)
            v = t.verts.new((x, y, h))
            colors[v] = ground_color(x, y, h)
            row.append(v)
        grid.append(row)
    # 大殿台基底下的地面看不见，不做（台基最下一层台座比 HALL_RECT 每边宽 0.15、往地下埋 0.9 米，这里往里收 0.6 米留搭头）
    hx0, hy0, hx1, hy1 = L.HALL_RECT
    cut = 0
    for j in range(ny):
        for i in range(nx):
            xa, ya = x0 + i * step, y0 + j * step
            if xa >= hx0 + 0.6 and xa + step <= hx1 - 0.6 and ya >= hy0 + 0.6 and ya + step <= hy1 - 0.6:
                cut += 1
                continue
            t.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    loose = [v for v in t.verts if not v.link_faces]
    for v in loose:
        colors.pop(v, None)
    bmesh.ops.delete(t, geom=loose, context='VERTS')
    print(f'[yjm] {name}: 台基底下不做的格子 {cut} 个')
    # 远处的湖底：一圈大的
    far = 170.0
    ring_in = [grid[0][i] for i in range(nx + 1)] + [grid[j][nx] for j in range(1, ny + 1)] + \
              [grid[ny][i] for i in range(nx - 1, -1, -1)] + [grid[j][0] for j in range(ny - 1, 0, -1)]
    outs = []
    for v in ring_in:
        d = Vector((v.co.x, v.co.y, 0)).normalized()
        o = t.verts.new((d.x * far, d.y * far, -3.6))
        colors[o] = C('lakebed_deep')
        outs.append(o)
    m = len(ring_in)
    for k in range(m):
        t.faces.new((ring_in[k], outs[k], outs[(k + 1) % m], ring_in[(k + 1) % m]))
    bmesh.ops.recalc_face_normals(t, faces=t.faces)
    # 朝上
    if sum(f.normal.z for f in t.faces) < 0:
        bmesh.ops.reverse_faces(t, faces=t.faces)
    # 地面用一张画好的贴图（tools/blender/ground_tex.py），贴图坐标就是它在范围里的位置
    uv = t.loops.layers.uv['uv']
    for f in t.faces:
        for l in f.loops:
            c = colors[l.vert]
            l[col] = (c[0], c[1], c[2], 0)
            l[uv].uv = (min(1.0, max(0.0, (l.vert.co.x - x0) / (x1 - x0))), min(1.0, max(0.0, (l.vert.co.y - y0) / (y1 - y0))))
    a.merge(t, 'ground')
    a.opts['ground'] = {'sharp': 180}
    export_map()
    return a.finish(ao=False, view=(0, 62, 0.5), floor=False)


def _slab(a, rng, cx, cy, w, d, z=0.0, h=0.06, rot=0.0, color=None, jitter=0.05, bevel=0.025):
    """一块石板：四个角稍微不齐"""
    hw, hd = w / 2, d / 2
    pts = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    pts = [(px + rng.uniform(-jitter, jitter), py + rng.uniform(-jitter, jitter)) for px, py in pts]
    c = color or vary(rng.choice([C('slab'), C('slab_b'), C('slab_c')]), rng, 0.03, 0.02)
    a.prism(pts, z, z + h + rng.uniform(-0.008, 0.008), tint(c, -0.08), bevel=bevel, top=c, loc=(cx, cy, 0), rot=(0, 0, rot))


def _stone(a, rng, cx, cy, r, z=0.0, h=0.07):
    """一块圆不溜的踏脚石"""
    n = rng.randint(7, 9)
    ph = rng.uniform(0, 6.28)
    pts = []
    for i in range(n):
        ang = ph + 2 * math.pi * i / n
        rr = r * rng.uniform(0.82, 1.08)
        pts.append((rr * math.cos(ang) * 1.15, rr * math.sin(ang) * 0.9))
    c = vary(rng.choice([C('slab'), C('stone'), C('slab_c')]), rng, 0.03, 0.02)
    a.prism(pts, z, z + h, tint(c, -0.08), bevel=0.03, top=c, loc=(cx, cy, 0), rot=(0, 0, rng.uniform(0, 3.14)))


def paving(name):
    a = Asset(name)
    rng = a.rng
    # 主路：一排两三块，长短不齐
    y = L.PATH_Y0
    while y < L.PATH_Y1 - 0.2:
        d = rng.uniform(0.85, 1.25)
        # 香炉周围的圆形铺地另做，这一段跳过
        if abs(y + d / 2 - L.BURNER[1]) < L.PLAZA_R + 0.2:
            y += d + 0.05
            continue
        k = rng.choice([2, 2, 3])
        ws = [rng.uniform(0.8, 1.2) for _ in range(k)]
        s = (2 * L.PATH_W - 0.05 * (k - 1)) / sum(ws)
        x = -L.PATH_W
        for w in ws:
            w *= s
            _slab(a, rng, x + w / 2, y + d / 2, w, d, rot=rng.uniform(-0.012, 0.012))
            x += w + 0.05
        y += d + 0.05
    # 香炉周围：一圈一圈的扇形石板
    radii = [1.25, 1.95, 2.8, L.PLAZA_R]
    counts = [10, 16, 22]
    for k in range(3):
        r0, r1 = radii[k] + 0.03, radii[k + 1] - 0.03
        n = counts[k]
        off = rng.uniform(0, 1)
        for i in range(n):
            a0 = 2 * math.pi * (i + off) / n + 0.012
            a1 = 2 * math.pi * (i + 1 + off) / n - 0.012
            pts = [(r0 * math.cos(a0), r0 * math.sin(a0)), (r1 * math.cos(a0), r1 * math.sin(a0)),
                   (r1 * math.cos((a0 + a1) / 2), r1 * math.sin((a0 + a1) / 2)),
                   (r1 * math.cos(a1), r1 * math.sin(a1)), (r0 * math.cos(a1), r0 * math.sin(a1)),
                   (r0 * math.cos((a0 + a1) / 2), r0 * math.sin((a0 + a1) / 2))]
            c = vary(rng.choice([C('slab'), C('slab_b'), C('slab_c')]), rng, 0.03, 0.02)
            a.prism(pts, 0, 0.06 + rng.uniform(-0.006, 0.006), tint(c, -0.08), bevel=0.02, top=c, loc=(L.BURNER[0], L.BURNER[1], 0))
    # 香炉底下一整块圆石
    a.cyl(1.22, 0.1, (L.BURNER[0], L.BURNER[1], 0), C('stone'), segs=24, bevel=0.03, top=C('stone_lit'))
    # 去许愿树、去池塘、去钟亭的踏脚石
    def stepping(p0, p1, n, r=0.36, sway=0.25):
        for i in range(n):
            k = (i + 0.5) / n
            px = p0[0] + (p1[0] - p0[0]) * k + math.sin(k * 6.0) * sway
            py = p0[1] + (p1[1] - p0[1]) * k + math.cos(k * 5.0) * sway * 0.6
            _stone(a, rng, px, py, r * rng.uniform(0.85, 1.15))
    stepping((-L.PLAZA_R - 0.3, L.BURNER[1] - 0.3), (L.TREE[0] + L.TREE_BED + 0.5, L.TREE[1] - 0.6), 4)
    stepping((L.PLAZA_R + 0.3, L.BURNER[1] - 0.4), (L.POND[0] - L.POND_R - 0.7, L.POND[1] + 0.2), 3)
    stepping((L.TERRACE[2] + 0.4, 6.2), (L.PAVILION[0] - 2.2, L.PAVILION[1]), 3, sway=0.12)
    stepping((-1.9, -9.0), (-6.0, -9.6), 5, r=0.32)
    stepping((1.9, -9.4), (6.2, -10.2), 5, r=0.32)
    # 石台：一圈条石围边，里面方砖
    x0, y0, x1, y1 = L.TERRACE
    H = L.TERRACE_H
    a.box((x1 - x0, y1 - y0, H - 0.03), ((x0 + x1) / 2, (y0 + y1) / 2, 0), color=C('stone_dark'), bevel=0.03)
    b = 0.34
    n = int((x1 - x0) / 1.5)
    for i in range(n):
        w = (x1 - x0) / n
        for yy in (y0 + b / 2, y1 - b / 2):
            _slab(a, rng, x0 + w * (i + 0.5), yy, w - 0.03, b, z=H - 0.05, h=0.07, color=vary(C('stone_lit'), rng, 0.02), jitter=0.01)
    n2 = int((y1 - y0 - 2 * b) / 1.5)
    for j in range(n2):
        d = (y1 - y0 - 2 * b) / n2
        for xx in (x0 + b / 2, x1 - b / 2):
            _slab(a, rng, xx, y0 + b + d * (j + 0.5), b, d - 0.03, z=H - 0.05, h=0.07, color=vary(C('stone_lit'), rng, 0.02), jitter=0.01)
    tw, td = x1 - x0 - 2 * b, y1 - y0 - 2 * b
    nx_, ny_ = 22, 7
    for i in range(nx_):
        for j in range(ny_):
            w, d = tw / nx_, td / ny_
            _slab(a, rng, x0 + b + w * (i + 0.5), y0 + b + d * (j + 0.5), w - 0.035, d - 0.035, z=H - 0.05, h=0.05, jitter=0.012, bevel=0.018)
    # 许愿树的树池：一圈条石，里面是土
    n = 14
    for i in range(n):
        ang = 2 * math.pi * i / n
        a.box((2 * math.pi * L.TREE_BED / n - 0.04, 0.34, 0.24), (L.TREE[0] + L.TREE_BED * math.cos(ang), L.TREE[1] + L.TREE_BED * math.sin(ang), 0),
              rot=(0, 0, ang + math.pi / 2), color=vary(C('stone'), rng, 0.03), bevel=0.04, segs=2, top=vary(C('stone_lit'), rng, 0.02))
    a.cyl(L.TREE_BED - 0.12, 0.14, (L.TREE[0], L.TREE[1], 0), C('dirt_dark'), segs=28, top=mix(C('dirt_dark'), C('moss'), 0.45))
    # 池塘边一圈小石头
    n = 26
    for i in range(n):
        ang = 2 * math.pi * i / n + rng.uniform(-0.08, 0.08)
        r = L.pond_radius(ang) + rng.uniform(-0.15, 0.3)
        if rng.random() < 0.18:
            continue
        s = rng.uniform(0.35, 0.75)
        px, py = L.POND[0] + r * math.cos(ang), L.POND[1] + r * math.sin(ang)
        a.rock((s, s * rng.uniform(0.7, 1.0), s * rng.uniform(0.45, 0.7)), loc=(px, py, L.height(px, py) - 0.02), color=vary(C('stone'), rng, 0.05),
               top=C('stone_lit') if rng.random() < 0.7 else C('moss'), n=11, rot=rng.uniform(0, 3.14))
    return a.finish(view=(0, 62, 0.6), dist=0.5, strength=0.55, samples=14)


ASSETS = {'islet_ground': ground, 'islet_paving': paving}
