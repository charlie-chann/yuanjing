"""小物件（钟、石凳、钓具、鱼、礼物）共用的几样手艺（2026-11-19）。

- grid：一张按参数算出来的曲面（鱼身、钟身、鱼篓、海螺……）：每个点的位置和颜色各由一个函数给，
  浮雕、鳞片、编织纹都是「位置往外挪一点 + 颜色跟着变」画出来的。
- fan：一片从叶柄散开的薄片（银杏叶、枫叶、鱼鳍、贝壳），双面叶片材质。
- finish：同 Asset.finish，但预览图按物件自己的大小取景（kit 的预览最小按 0.3 米取景，十厘米的小东西只有指甲盖大，看不清）。
"""
import math
import os

import bmesh
import bpy
from mathutils import Vector

import kit
from kit import new_bm


def grid(a, mat, nu, nv, fn, wrap=True, flip=False, cap0=None, cap1=None, sway=0.0, glow=0.0, smooth=True, M=None):
    """参数曲面：fn(u, v) → (位置, 颜色)，u、v 都是 0..1。u 方向 nu 格（wrap=True 时首尾相接，绕一圈），v 方向 nv 格。
    u 逆时针绕 z、v 往上的时候面朝外；反了就 flip。cap0 / cap1：v=0 / v=1 那一圈用一个点封口，给 (位置, 颜色)"""
    t = new_bm()
    col = t.loops.layers.float_color['col']
    uvl = t.loops.layers.uv['uv']
    cu = nu if wrap else nu + 1
    vs, cs = [], {}
    for j in range(nv + 1):
        row = []
        for i in range(cu):
            p, c = fn(i / nu, j / nv)
            v = t.verts.new(p)
            cs[v] = c
            row.append(v)
        vs.append(row)
    ph = a.rng.random()

    def face(q):
        if len(set(q)) < 3:
            return
        try:
            f = t.faces.new(q if not flip else list(reversed(q)))
        except ValueError:
            return
        f.smooth = smooth
        for l in f.loops:
            c = cs[l.vert]
            l[col] = (c[0], c[1], c[2], sway)
            l[uvl].uv = (ph, glow)
    for j in range(nv):
        for i in range(nu):
            i2 = (i + 1) % cu if wrap else i + 1
            face([vs[j][i], vs[j][i2], vs[j + 1][i2], vs[j + 1][i]])
    for cap, row, rev in ((cap0, vs[0], True), (cap1, vs[-1], False)):
        if cap is None:
            continue
        c0 = t.verts.new(cap[0])
        cs[c0] = cap[1]
        for i in range(nu):
            i2 = (i + 1) % cu if wrap else i + 1
            face([c0, row[i2], row[i]] if rev else [c0, row[i], row[i2]])
    a.merge(t, mat, M)


def fan(a, mat, root, pts, colors, root_color=None, sway=0.0, M=None, rings=None, shade=None):
    """一片薄片：从 root 一点散到外沿一串点 pts（依次相邻）。colors 每个外沿点一个颜色。
    rings：在 root 和外沿之间再插几圈（0..1 的比例列表），每圈的颜色 = 外沿色和根色按比例混，叶片可以带弧度：
    传 (比例, 抬高) 的列表时这一圈整体沿 z 抬高那么多。shade(比例, 第几个外沿点, 颜色) → 颜色：再按位置改一道（叶脉、花斑）"""
    t = new_bm()
    col = t.loops.layers.float_color['col']
    uvl = t.loops.layers.uv['uv']
    root = Vector(root)
    rc = root_color or colors[0]
    rows = [(0.0, 0.0)] + [(r, 0.0) if isinstance(r, (int, float)) else r for r in (rings or [])] + [(1.0, 0.0)]
    cs = {}
    vr = t.verts.new(root)
    cs[vr] = rc
    layers = []
    for (k, lift) in rows[1:]:
        row = []
        for p, c in zip(pts, colors):
            v = t.verts.new(root + (Vector(p) - root) * k + Vector((0, 0, lift)))
            cc = tuple(rc[i] + (c[i] - rc[i]) * k for i in range(3))
            cs[v] = shade(k, len(row), cc) if shade else cc
            row.append(v)
        layers.append(row)
    ph = a.rng.random()

    def face(q):
        try:
            f = t.faces.new(q)
        except ValueError:
            return
        for l in f.loops:
            c = cs[l.vert]
            l[col] = (c[0], c[1], c[2], sway)
            l[uvl].uv = (ph, 0)
    n = len(pts)
    for i in range(n - 1):
        face([vr, layers[0][i], layers[0][i + 1]])
        for r in range(len(layers) - 1):
            face([layers[r][i], layers[r + 1][i], layers[r + 1][i + 1], layers[r][i + 1]])
    a.merge(t, mat, M)


def shot(name, objs, view=None, floor=True, pad=1.0):
    """预览图：按物件自己的包围球取景"""
    sc = bpy.context.scene
    if sc.camera is None or sc.camera.name != 'cam':
        kit.setup_scene()
    mat = kit.preview_material()
    if 'ground' in bpy.data.objects:
        bpy.data.objects['ground'].hide_render = not floor
    lo, hi = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    for ob in objs:
        if not ob.data.materials:
            m = ob.get('mat', '')
            mb = m.split(':')[0]
            ob.data.materials.append(kit.leaf_preview_material(m) if m.startswith('leaf_') else
                                     kit.paint_preview_material(mb) if mb.startswith('paint_') else mat)
        for v in ob.data.vertices:
            for i in range(3):
                lo[i] = min(lo[i], v.co[i])
                hi[i] = max(hi[i], v.co[i])
    ctr = (lo + hi) / 2
    rad = max(0.02, (hi - lo).length / 2) * pad
    yaw, pitch, k = view or (20, 35, 1.0)
    yaw, pitch = math.radians(yaw), math.radians(pitch)
    cam = sc.camera
    dist = rad / math.tan(cam.data.angle / 2) * 1.12 * k
    dirv = Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
    cam.location = ctr + dirv * dist
    cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.clip_start = max(0.005, dist * 0.05)
    cam.data.clip_end = dist * 4 + 100
    os.makedirs(kit.PREVIEW, exist_ok=True)
    sc.render.filepath = os.path.join(kit.PREVIEW, name + '.png')
    bpy.ops.render.render(write_still=True)
    cam.data.clip_start = 0.1


def finish(a, view=None, ao=False, floor=True, extra=None, **ao_args):
    """算暗部（可选）、导出、出预览图（按物件大小取景）。extra：{后缀: 视角} 再多拍几张。返回三角形数"""
    a.check_coplanar()
    if ao:
        a.ao(**ao_args)
    objs = a.to_objects()
    tris = a.export(objs)
    if os.environ.get('YJ_PREVIEW', '1') != '0':
        shot(a.name, objs, view, floor)
        for tag, v in (extra or {}).items():
            shot(f'{a.name}_{tag}', objs, v, floor)
    for ob in objs:
        me = ob.data
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
    for b in a.parts.values():
        b.free()
    a.parts = {}
    print(f'[yjm] {a.name}: {tris} tris')
    return tris


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def smooth(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def bump(x, c, w):
    """以 c 为中心、宽 w 的一个圆包（高斯）"""
    return math.exp(-((x - c) / w) ** 2)


def interp(x, xs, ys):
    """分段线性插值"""
    if x <= xs[0]:
        return ys[0]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + (ys[i] - ys[i - 1]) * t
    return ys[-1]
