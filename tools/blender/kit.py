"""Blender 里用代码建模的公共函数。

约定：
- 坐标：X 向右，Y 向里（进深），Z 向上，单位米。导出时换成 Unity 的 (x, z, y)，三角形反向。
- 颜色写在面的顶点色里（sRGB），第四个数是「随风摆动的幅度」（0 = 不动）。
- uv.x 是每一块的随机相位（让每团叶子摆得不一样），uv.y 是自发光强度（0 或 1）。
- 一个模型分成几个部件（part），按材质名分：toon 普通、leaf 双面的叶片、glow 夜里会亮的。
"""
import bpy
import bmesh
import json
import math
import os
import random
import struct
import zlib
from mathutils import Vector, Matrix, Euler, noise
from mathutils.bvhtree import BVHTree

from palette import C, tint, mix, vary

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', '..', 'unity', 'Sanctuary', 'Assets', 'Toon', 'Models')
PREVIEW = os.path.join(HERE, 'preview')


def stable_seed(s):
    return zlib.crc32(s.encode('utf8'))


def new_bm():
    b = bmesh.new()
    b.loops.layers.float_color.new('col')
    b.loops.layers.uv.new('uv')
    return b


def paint(b, faces=None, color=(1, 1, 1), sway=0.0, phase=0.0, glow=0.0):
    col = b.loops.layers.float_color['col']
    uv = b.loops.layers.uv['uv']
    for f in (faces if faces is not None else b.faces):
        for l in f.loops:
            l[col] = (color[0], color[1], color[2], sway)
            l[uv].uv = (phase, glow)


def paint_grad(b, c0, c1, z0, z1, faces=None, axis=2, power=1.0):
    """按高度从 c0 过渡到 c1（保留摆动值）"""
    col = b.loops.layers.float_color['col']
    for f in (faces if faces is not None else b.faces):
        for l in f.loops:
            t = (l.vert.co[axis] - z0) / max(1e-6, z1 - z0)
            t = min(1, max(0, t)) ** power
            c = mix(c0, c1, t)
            l[col] = (c[0], c[1], c[2], l[col][3])


def sway_grad(b, z0, z1, amount, faces=None, power=1.0):
    col = b.loops.layers.float_color['col']
    for f in (faces if faces is not None else b.faces):
        for l in f.loops:
            t = (l.vert.co.z - z0) / max(1e-6, z1 - z0)
            t = min(1, max(0, t)) ** power
            c = l[col]
            l[col] = (c[0], c[1], c[2], amount * t)


def xform(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    if isinstance(scale, (int, float)):
        scale = (scale, scale, scale)
    S = Matrix.Diagonal((scale[0], scale[1], scale[2], 1))
    return Matrix.Translation(loc) @ Euler(rot, 'XYZ').to_matrix().to_4x4() @ S


class Asset:
    def __init__(self, name):
        self.name = name
        self.parts = {}
        self.rng = random.Random(stable_seed(name))
        self.opts = {}          # 部件的导出选项：{'leaf': {'normal_up': 0.7}}

    # ---------- 基础 ----------
    def part(self, mat):
        if mat not in self.parts:
            self.parts[mat] = new_bm()
        return self.parts[mat]

    def merge(self, t, mat='toon', M=None):
        if M is not None:
            bmesh.ops.transform(t, matrix=M, verts=t.verts)
            if M.determinant() < 0:
                bmesh.ops.reverse_faces(t, faces=t.faces)
        me = bpy.data.meshes.new('_t')
        t.to_mesh(me)
        t.free()
        self.part(mat).from_mesh(me)
        bpy.data.meshes.remove(me)

    def place(self, other, loc=(0, 0, 0), rot=(0, 0, 0), scale=1):
        """把另一个模型整个摆进来（用完对方就空了）"""
        M = xform(loc, rot, scale)
        for mat, b in list(other.parts.items()):
            self.merge(b, mat, M)
        other.parts = {}
        for k, v in other.opts.items():
            self.opts.setdefault(k, v)

    # ---------- 形体 ----------
    def box(self, size, loc=(0, 0, 0), rot=(0, 0, 0), color=(1, 1, 1), bevel=0.02, segs=1, mat='toon',
            top=None, grad=None, sway=0.0, glow=0.0, base=True):
        """方块。base=True 时 loc 是底面中心，否则是体心。top：顶面换个颜色。grad：(下色, 上色)"""
        t = new_bm()
        bmesh.ops.create_cube(t, size=1.0)
        for v in t.verts:
            v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2] + (size[2] / 2 if base else 0)))
        if bevel > 0:
            bmesh.ops.bevel(t, geom=t.edges[:], offset=min(bevel, min(size) * 0.45), offset_type='OFFSET',
                            segments=segs, profile=0.5, affect='EDGES', clamp_overlap=True)
        paint(t, None, color, sway, self.rng.random(), glow)
        if grad:
            z0 = 0 if base else -size[2] / 2
            paint_grad(t, grad[0], grad[1], z0, z0 + size[2])
        if top is not None:
            paint(t, [f for f in t.faces if f.normal.z > 0.9], top, sway, 0, glow)
        self.merge(t, mat, xform(loc, rot))

    def cyl(self, r, h, loc=(0, 0, 0), color=(1, 1, 1), r2=None, segs=14, bevel=0.0, rot=(0, 0, 0), mat='toon',
            top=None, grad=None, glow=0.0):
        """圆柱或圆台，底面在 loc"""
        t = new_bm()
        bmesh.ops.create_cone(t, cap_ends=True, cap_tris=False, segments=segs, radius1=r,
                              radius2=r if r2 is None else r2, depth=h)
        bmesh.ops.translate(t, verts=t.verts, vec=(0, 0, h / 2))
        if bevel > 0:
            edges = [e for e in t.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-5]
            bmesh.ops.bevel(t, geom=edges, offset=bevel, offset_type='OFFSET', segments=1, profile=0.5,
                            affect='EDGES', clamp_overlap=True)
        paint(t, None, color, 0, 0, glow)
        if grad:
            paint_grad(t, grad[0], grad[1], 0, h)
        if top is not None:
            paint(t, [f for f in t.faces if f.normal.z > 0.9], top, 0, 0, glow)
        self.merge(t, mat, xform(loc, rot))

    def lathe(self, profile, loc=(0, 0, 0), segs=16, color=(1, 1, 1), rot=(0, 0, 0), scale=1, mat='toon', glow=0.0,
              squash=None):
        """旋转体。profile: [(半径, 高度) 或 (半径, 高度, 颜色)]，从下往上。颜色管它到下一圈之间那一段"""
        t = new_bm()
        rings = []
        for p in profile:
            r, z = p[0], p[1]
            if r < 1e-5:
                rings.append([t.verts.new((0, 0, z))])
            else:
                rings.append([t.verts.new((r * math.cos(2 * math.pi * i / segs), r * math.sin(2 * math.pi * i / segs), z))
                              for i in range(segs)])
        for k in range(len(rings) - 1):
            a, b = rings[k], rings[k + 1]
            c = profile[k][2] if len(profile[k]) > 2 else color
            fs = []
            for i in range(segs):
                j = (i + 1) % segs
                if len(a) == 1 and len(b) == 1:
                    continue
                if len(a) == 1:
                    fs.append(t.faces.new((a[0], b[j], b[i])))
                elif len(b) == 1:
                    fs.append(t.faces.new((a[i], a[j], b[0])))
                else:
                    fs.append(t.faces.new((a[i], a[j], b[j], b[i])))
            paint(t, fs, c, 0, 0, glow)
        if squash:
            for v in t.verts:
                v.co.x *= squash[0]
                v.co.y *= squash[1]
        bmesh.ops.recalc_face_normals(t, faces=t.faces)
        self.merge(t, mat, xform(loc, rot, scale))

    def blob(self, r, loc=(0, 0, 0), scale=(1, 1, 1), color=(1, 1, 1), top=None, subdiv=2, bump=0.16, freq=1.3,
             mat='toon', sway=0.0, rot=(0, 0, 0), flat=None, power=1.0):
        """一团：树冠、灌木。top：顶上的颜色（从下到上过渡）。flat：把低于这个高度（相对半径）的压平"""
        t = new_bm()
        bmesh.ops.create_icosphere(t, subdivisions=subdiv, radius=1.0)
        off = Vector((self.rng.uniform(-50, 50), self.rng.uniform(-50, 50), self.rng.uniform(-50, 50)))
        for v in t.verts:
            n = noise.noise(v.co * freq + off)
            v.co = v.co * (1 + bump * n * 2)
            if flat is not None and v.co.z < flat:
                v.co.z = flat + (v.co.z - flat) * 0.15
        ph = self.rng.random()
        paint(t, None, color, sway, ph)
        if top is not None:
            paint_grad(t, color, top, -0.6, 1.0, power=power)
        self.merge(t, mat, xform(loc, rot, (scale[0] * r, scale[1] * r, scale[2] * r)))

    def rock(self, size, loc=(0, 0, 0), color=None, top=None, n=26, bevel=0.05, rot=0.0, sink=0.15, mat='toon'):
        """石头：随机点的凸包再倒角。size=(宽, 深, 高)"""
        color = color or C('stone')
        t = new_bm()
        rng = self.rng
        for _ in range(n):
            d = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized()
            k = rng.uniform(0.75, 1.0)
            t.verts.new((d.x * size[0] / 2 * k, d.y * size[1] / 2 * k, abs(d.z) * size[2] * k - size[2] * sink))
        res = bmesh.ops.convex_hull(t, input=t.verts)
        junk = list({g for g in res.get('geom_interior', []) + res.get('geom_unused', []) if isinstance(g, bmesh.types.BMVert)})
        if junk:
            bmesh.ops.delete(t, geom=junk, context='VERTS')
        bmesh.ops.dissolve_limit(t, angle_limit=math.radians(7), verts=t.verts, edges=t.edges)
        if bevel > 0:
            bmesh.ops.bevel(t, geom=t.edges[:], offset=bevel * min(size), offset_type='OFFSET', segments=2,
                            profile=0.6, affect='EDGES', clamp_overlap=True)
        bmesh.ops.recalc_face_normals(t, faces=t.faces)
        paint(t, None, color)
        paint_grad(t, tint(color, -0.10, 0.02), tint(color, 0.05), 0, size[2] * 0.8)
        if top is not None:
            col = t.loops.layers.float_color['col']
            for f in t.faces:
                if f.normal.z > 0.75:
                    for l in f.loops:
                        l[col] = (top[0], top[1], top[2], 0)
        self.merge(t, mat, xform(loc, (0, 0, rot)))

    def tube(self, pts, radii, color=(1, 1, 1), segs=8, mat='toon', cap=True, color2=None, sway=None, flat=1.0):
        """沿一串点的管子（树干、枝、绳、屋脊）。radii 可以是一个数或一串数。flat：把截面压扁的比例（竖直方向）"""
        pts = [Vector(p) for p in pts]
        n = len(pts)
        if isinstance(radii, (int, float)):
            radii = [radii] * n
        t = new_bm()
        col = t.loops.layers.float_color['col']
        tang = [(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(n)]
        up = Vector((0, 0, 1)) if abs(tang[0].z) < 0.9 else Vector((1, 0, 0))
        nrm = (up - tang[0] * up.dot(tang[0])).normalized()
        rings = []
        for i in range(n):
            if i > 0:
                nrm = (nrm - tang[i] * nrm.dot(tang[i]))
                nrm = nrm.normalized() if nrm.length > 1e-6 else up
            bi = tang[i].cross(nrm).normalized()
            ring = []
            for k in range(segs):
                a = 2 * math.pi * k / segs
                ring.append(t.verts.new(pts[i] + (nrm * math.cos(a) * flat + bi * math.sin(a)) * radii[i]))
            rings.append(ring)
        for i in range(n - 1):
            for k in range(segs):
                j = (k + 1) % segs
                t.faces.new((rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]))
        if cap:
            t.faces.new(rings[0])
            t.faces.new(list(reversed(rings[-1])))
        bmesh.ops.recalc_face_normals(t, faces=t.faces)
        ph = self.rng.random()
        for f in t.faces:
            for l in f.loops:
                # 找这个点属于第几圈
                c = color
                l[col] = (c[0], c[1], c[2], 0)
                l[t.loops.layers.uv['uv']].uv = (ph, 0)
        if color2 is not None or sway is not None:
            idx = {}
            for i, ring in enumerate(rings):
                for v in ring:
                    idx[v] = i / max(1, n - 1)
            for f in t.faces:
                for l in f.loops:
                    u = idx[l.vert]
                    c = mix(color, color2, u) if color2 is not None else color
                    s = (sway[0] + (sway[1] - sway[0]) * u) if sway is not None else 0
                    l[col] = (c[0], c[1], c[2], s)
        self.merge(t, mat)

    def prism(self, poly, z0, z1, color=(1, 1, 1), bevel=0.0, mat='toon', top=None, segs=1, loc=(0, 0, 0), rot=(0, 0, 0)):
        """任意多边形拉成的柱体（石板、平台）。poly: [(x, y)] 逆时针"""
        t = new_bm()
        lo = [t.verts.new((p[0], p[1], z0)) for p in poly]
        hi = [t.verts.new((p[0], p[1], z1)) for p in poly]
        n = len(poly)
        t.faces.new(hi)
        t.faces.new(list(reversed(lo)))
        for i in range(n):
            j = (i + 1) % n
            t.faces.new((lo[i], lo[j], hi[j], hi[i]))
        bmesh.ops.recalc_face_normals(t, faces=t.faces)
        if bevel > 0:
            edges = [e for e in t.edges if e.verts[0].co.z > z1 - 1e-5 and e.verts[1].co.z > z1 - 1e-5]
            bmesh.ops.bevel(t, geom=edges, offset=bevel, offset_type='OFFSET', segments=segs, profile=0.5,
                            affect='EDGES', clamp_overlap=True)
        paint(t, None, color)
        if top is not None:
            paint(t, [f for f in t.faces if f.normal.z > 0.9], top)
        self.merge(t, mat, xform(loc, rot))

    def quad(self, pts, color=(1, 1, 1), mat='leaf', sway=(0, 0, 0, 0), colors=None, phase=None):
        """一片四边形或三角形（草叶、竹叶、布条）。sway 给每个角一个摆动值"""
        t = new_bm()
        vs = [t.verts.new(p) for p in pts]
        f = t.faces.new(vs)
        col = t.loops.layers.float_color['col']
        uv = t.loops.layers.uv['uv']
        ph = self.rng.random() if phase is None else phase
        for i, l in enumerate(f.loops):
            c = colors[i] if colors else color
            l[col] = (c[0], c[1], c[2], sway[i] if i < len(sway) else 0)
            l[uv].uv = (ph, 0)
        self.merge(t, mat)

    def disc(self, r, loc=(0, 0, 0), color=(1, 1, 1), segs=16, mat='toon', rim=None, notch=0.0, rot=0.0, tilt=(0, 0),
             cup=0.0, sway=0.0):
        """一片圆片（荷叶、花瓣盘）。notch：缺口占的角度；cup：边缘翘起的高度；rim：边缘的颜色"""
        t = new_bm()
        c0 = t.verts.new((0, 0, 0))
        span = 2 * math.pi - notch
        vs = [t.verts.new((r * math.cos(notch / 2 + span * i / segs), r * math.sin(notch / 2 + span * i / segs), cup))
              for i in range(segs + 1)]
        col = t.loops.layers.float_color['col']
        uv = t.loops.layers.uv['uv']
        ph = self.rng.random()
        for i in range(segs):
            f = t.faces.new((c0, vs[i], vs[i + 1]))
            for l in f.loops:
                c = color if (l.vert is c0 or rim is None) else rim
                l[col] = (c[0], c[1], c[2], sway if l.vert is not c0 else 0)
                l[uv].uv = (ph, 0)
        if notch <= 0:
            bmesh.ops.remove_doubles(t, verts=t.verts, dist=1e-5)
        self.merge(t, mat, xform(loc, (tilt[0], tilt[1], rot)))

    # ---------- 屋顶 ----------
    def roof(self, W, D, H, z=0.0, loc=(0, 0), lift=0.5, curve=2.2, pitch=0.36, amp=0.035, inner=None, rows=8,
             thick=0.12, ca=None, cb=None, eave=None, under=None, ridge=None, ridge_r=0.13, hips=True, mat='toon',
             tip=0.45, finial=True):
        """中式屋顶（四面坡，檐角上翘，瓦垄起伏）。W、D 是檐口的半宽半深，H 是檐口到屋脊的高。
        inner：只留离檐口这么近的一圈（重檐的下层）。"""
        ca = ca or C('tile')
        cb = cb or C('tile_lit')
        eave = eave or C('ridge')
        under = under or C('red_dark')
        ridge = ridge or C('ridge')
        dmax = min(W, D)
        dlim = dmax if inner is None else min(inner, dmax)

        def height(x, y):
            d = min(W - abs(x), D - abs(y))
            t = max(0.0, d) / dmax
            c = (abs(x) / W * abs(y) / D) ** 3
            return z + H * (0.45 * t + 0.55 * t ** curve) + lift * c * (1 - t) ** 2

        def clip(poly, a, b, c):
            # 留下 a*u + b*d <= c 的部分
            out = []
            for i in range(len(poly)):
                p, q = poly[i], poly[(i + 1) % len(poly)]
                fp, fq = a * p[0] + b * p[1] - c, a * q[0] + b * q[1] - c
                if fp <= 1e-9:
                    out.append(p)
                if (fp < -1e-9 and fq > 1e-9) or (fp > 1e-9 and fq < -1e-9):
                    k = fp / (fp - fq)
                    out.append((p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k))
            return out

        def surface(t, corr, step, drop, flip):
            col = t.loops.layers.float_color['col']
            cache = {}

            def vert(x, y, zz, key):
                if key not in cache:
                    cache[key] = t.verts.new((x, y, zz))
                return cache[key]
            # (沿檐方向的半长, 另一个方向的半长, 把 (u, d) 变成 (x, y) 的函数)
            sides = [
                (W, D, lambda u, d: (u, -(D - d))), (W, D, lambda u, d: (-u, D - d)),
                (D, W, lambda u, d: (W - d, u)), (D, W, lambda u, d: (-(W - d), -u)),
            ]
            ds = [dlim * i / rows for i in range(rows + 1)]
            for si, (L, _, f) in enumerate(sides):
                nu = max(2, int(round(2 * L / step)))
                us = [-L + 2 * L * i / nu for i in range(nu + 1)]
                for i in range(nu):
                    for j in range(rows):
                        poly = [(us[i], ds[j]), (us[i + 1], ds[j]), (us[i + 1], ds[j + 1]), (us[i], ds[j + 1])]
                        poly = clip(poly, 1, 1, L)      # u <= L - d
                        poly = clip(poly, -1, 1, L)     # -u <= L - d
                        if len(poly) < 3:
                            continue
                        vs = []
                        for (u, d) in poly:
                            x, y = f(u, d)
                            ridge_v = (int(round((u + L) / step)) % 2 == 0)
                            zz = height(x, y) - drop + (amp if (corr and ridge_v) else 0)
                            vs.append((vert(x, y, zz, (round(x, 4), round(y, 4), si if corr else 0)), ridge_v, d))
                        # 去掉重复的点
                        uniq = []
                        for v in vs:
                            if not uniq or uniq[-1][0] is not v[0]:
                                uniq.append(v)
                        if len(uniq) > 1 and uniq[0][0] is uniq[-1][0]:
                            uniq.pop()
                        if len(uniq) < 3:
                            continue
                        try:
                            face = t.faces.new([v[0] for v in (reversed(uniq) if flip else uniq)])
                        except ValueError:
                            continue
                        row_c = mix(ca, cb, 0.5 + 0.5 * math.sin(j * 1.7 + si))
                        look = {v[0]: v for v in uniq}
                        for l in face.loops:
                            _, rv, d = look[l.vert]
                            if corr:
                                c = mix(tint(row_c, -0.07), tint(row_c, 0.06), 1.0 if rv else 0.0)
                                c = mix(tint(c, -0.05), c, min(1.0, d / max(0.01, dlim) * 3))
                            else:
                                c = under
                            l[col] = (c[0], c[1], c[2], 0)

        t = new_bm()
        surface(t, True, pitch / 2, 0.0, False)
        self.merge(t, mat, xform((loc[0], loc[1], 0)))
        # 底面（檐下能看到的那一面），粗一些就够
        t = new_bm()
        surface(t, False, max(W, D) / 4, thick, True)
        self.merge(t, mat, xform((loc[0], loc[1], 0)))
        # 檐口的封边：沿四条檐一圈厚边
        n = 24
        for (ax, sx, sy) in ((0, 1, -1), (0, 1, 1), (1, 1, 1), (1, -1, 1)):
            pts = []
            for i in range(n + 1):
                u = -1 + 2 * i / n
                x, y = ((u * W, sy * D) if ax == 0 else (sx * W, u * D))
                pts.append((x + loc[0], y + loc[1], height(x, y) - thick * 0.45))
            self.tube(pts, thick * 0.62, eave, segs=6, mat=mat)
        if inner is not None:
            return
        # 屋脊
        if W - D > 0.05:
            L = W - D
            pts = [(-L - tip * 0.9, 0, z + H + 0.42), (-L - tip * 0.5, 0, z + H + 0.2), (-L, 0, z + H + 0.08),
                   (0, 0, z + H + 0.05), (L, 0, z + H + 0.08), (L + tip * 0.5, 0, z + H + 0.2), (L + tip * 0.9, 0, z + H + 0.42)]
            self.tube([(p[0] + loc[0], p[1] + loc[1], p[2]) for p in pts],
                      [ridge_r * 0.55, ridge_r * 0.9, ridge_r * 1.15, ridge_r * 1.15, ridge_r * 1.15, ridge_r * 0.9, ridge_r * 0.55],
                      ridge, segs=8, mat=mat, color2=None)
        elif abs(W - D) <= 0.05 and finial:
            # 攒尖顶：顶上一个宝顶
            self.lathe([(0, 0), (ridge_r * 1.6, 0.02), (ridge_r * 1.7, 0.12), (ridge_r * 0.9, 0.2), (ridge_r * 1.5, 0.36),
                        (ridge_r * 1.3, 0.5), (ridge_r * 0.5, 0.62), (0, 0.8)], (loc[0], loc[1], z + H - 0.05), segs=12,
                       color=C('gold'), mat=mat)
        if hips:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    pts, rad = [], []
                    m = 10
                    x0, y0 = sx * max(0.0, W - D), sy * max(0.0, D - W)
                    for i in range(m + 1):
                        k = i / m
                        x, y = x0 + (sx * W - x0) * k, y0 + (sy * D - y0) * k
                        pts.append((x + loc[0], y + loc[1], height(x, y) + 0.06))
                        rad.append(ridge_r * (1.0 - 0.25 * k))
                    # 檐角再往外翘一点
                    ex, ey, ez = pts[-1]
                    dx, dy = sx / math.sqrt(2), sy / math.sqrt(2)
                    pts.append((ex + dx * tip * 0.5, ey + dy * tip * 0.5, ez + tip * 0.22))
                    rad.append(ridge_r * 0.6)
                    pts.append((ex + dx * tip * 0.85, ey + dy * tip * 0.85, ez + tip * 0.6))
                    rad.append(ridge_r * 0.32)
                    self.tube(pts, rad, ridge, segs=8, mat=mat)

    # ---------- 收尾 ----------
    def ao(self, samples=20, dist=1.6, strength=0.6, ground=True, shade=(0.52, 0.5, 0.72), ground_z=0.0, skip=('leaf',)):
        """把「缝里、墙脚更暗」算出来乘进顶点色。shade 是暗处偏的颜色（偏蓝紫，画面更通透）"""
        verts, tris = [], []
        for mat, b in self.parts.items():
            base = len(verts)
            b.verts.ensure_lookup_table()
            verts += [v.co.copy() for v in b.verts]
            for f in b.faces:
                vs = [v.index + base for v in f.verts]
                for i in range(1, len(vs) - 1):
                    tris.append((vs[0], vs[i], vs[i + 1]))
        if ground:
            base = len(verts)
            g = 200.0
            verts += [Vector((-g, -g, ground_z)), Vector((g, -g, ground_z)), Vector((g, g, ground_z)), Vector((-g, g, ground_z))]
            tris += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
        if not tris:
            return
        tree = BVHTree.FromPolygons(verts, tris, all_triangles=True)
        rng = random.Random(7)
        dirs = []
        for i in range(samples):
            # 半球上按余弦分布取方向
            u, v = (i + rng.random()) / samples, rng.random()
            r, a = math.sqrt(u), 2 * math.pi * v
            dirs.append(Vector((r * math.cos(a), r * math.sin(a), math.sqrt(max(0.0, 1 - u)))))
        zaxis = Vector((0, 0, 1))
        for mat, b in self.parts.items():
            if mat in skip:
                continue
            col = b.loops.layers.float_color['col']
            cache = {}
            for f in b.faces:
                fn = f.normal
                fc = f.calc_center_median()
                for l in f.loops:
                    n = (fn * 0.65 + l.vert.normal * 0.35).normalized()
                    # 取样点往面的中间挪一些：大面的角上被旁边的小东西挡住时，不至于把整个大面都拖暗
                    to_c = fc - l.vert.co
                    shift = min(0.25, 1.0 / max(1e-6, to_c.length))
                    big = to_c.length > 0.6
                    key = (l.vert.index, round(n.x, 1), round(n.y, 1), round(n.z, 1), f.index if big else -1)
                    a = cache.get(key)
                    if a is None:
                        rot = zaxis.rotation_difference(n).to_matrix()
                        o = l.vert.co + to_c * shift + n * 0.03
                        occ = 0.0
                        for d in dirs:
                            hit = tree.ray_cast(o, rot @ d, dist)
                            if hit[0] is not None:
                                occ += 1.0 - (hit[3] / dist) * 0.7
                        a = 1.0 - strength * occ / samples
                        cache[key] = a
                    c = l[col]
                    k = [a + (1 - a) * shade[i] * 0.55 for i in range(3)]
                    l[col] = (c[0] * k[0], c[1] * k[1], c[2] * k[2], c[3])

    def check_coplanar(self, min_area=0.03):
        """找「两个面叠在同一个平面上」的地方：这种地方渲染时两个面抢着显示，镜头稍微一动就闪。
        只查朝向相同、面积不太小的面；用平面内的包围盒粗查，报出来的要人看一眼。"""
        groups = {}
        for mat, b in self.parts.items():
            for f in b.faces:
                if f.calc_area() < min_area:
                    continue
                n = f.normal
                d = n.dot(f.verts[0].co)
                key = (round(n.x, 2), round(n.y, 2), round(n.z, 2), round(d, 3))
                # 平面内的两个方向
                u = n.cross(Vector((0, 0, 1)))
                u = u.normalized() if u.length > 1e-3 else Vector((1, 0, 0))
                v = n.cross(u)
                us = [u.dot(x.co) for x in f.verts]
                vs = [v.dot(x.co) for x in f.verts]
                groups.setdefault(key, []).append((min(us), max(us), min(vs), max(vs), f.calc_center_median(), {x.index for x in f.verts}, mat))
        hits = []
        for key, fs in groups.items():
            if len(fs) < 2 or len(fs) > 400:
                continue
            for i in range(len(fs)):
                a = fs[i]
                for j in range(i + 1, len(fs)):
                    c = fs[j]
                    ou = min(a[1], c[1]) - max(a[0], c[0]) - 0.01
                    ov = min(a[3], c[3]) - max(a[2], c[2]) - 0.01
                    # 同一个部件里共用顶点的是挨着的两个面，不是叠着
                    if a[6] == c[6] and a[5] & c[5]:
                        continue
                    if ou > 0 and ov > 0 and ou * ov > min_area:
                        hits.append((ou * ov, key, tuple(round(x, 2) for x in a[4]), tuple(round(x, 2) for x in c[4])))
        hits.sort(reverse=True)
        for area, key, p, q in hits[:6]:
            print(f'[yjm] !! {self.name} 有两个面叠在一起：朝向 {key[:3]} 高度 {key[3]}，重叠约 {area:.2f} 平米，在 {p} 和 {q}')
        return len(hits)

    def stats(self):
        return {m: (len(b.verts), sum(len(f.verts) - 2 for f in b.faces)) for m, b in self.parts.items()}

    def to_objects(self, sharp=50.0):
        """变成 Blender 物体（用来算法线和出预览图）"""
        objs = []
        for mat, b in self.parts.items():
            if len(b.faces) == 0:
                continue
            opt = self.opts.get(mat, {})
            ang = math.radians(opt.get('sharp', sharp))
            for f in b.faces:
                f.smooth = True
            for e in b.edges:
                e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0) > ang)
            me = bpy.data.meshes.new(f'{self.name}_{mat}')
            b.to_mesh(me)
            ob = bpy.data.objects.new(f'{self.name}_{mat}', me)
            bpy.context.scene.collection.objects.link(ob)
            if not opt.get('plain_normals'):
                m = ob.modifiers.new('wn', 'WEIGHTED_NORMAL')
                m.keep_sharp = True
                m.weight = 60
            ob['mat'] = mat
            objs.append(ob)
        return objs

    def export(self, objs, out_dir=None):
        out_dir = out_dir or OUT
        os.makedirs(out_dir, exist_ok=True)
        dg = bpy.context.evaluated_depsgraph_get()
        header = {'name': self.name, 'parts': []}
        blobs = []
        total = 0
        for ob in objs:
            mat = ob['mat']
            opt = self.opts.get(mat, {})
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            me.calc_loop_triangles()
            col = me.color_attributes['col'].data
            uv = me.uv_layers['uv'].data
            cn = me.corner_normals
            up = opt.get('normal_up', 0.0)
            index, pos, nrm, cols, uvs, idx = {}, [], [], [], [], []
            for tri in me.loop_triangles:
                ids = []
                for li in tri.loops:
                    v = me.loops[li].vertex_index
                    n = Vector(cn[li].vector)
                    if up > 0:
                        n = (n * (1 - up) + Vector((0, 0, up))).normalized()
                    c = col[li].color
                    u = uv[li].uv
                    key = (v, round(n.x, 3), round(n.y, 3), round(n.z, 3), round(c[0], 3), round(c[1], 3), round(c[2], 3),
                           round(c[3], 3), round(u[0], 3), round(u[1], 3))
                    k = index.get(key)
                    if k is None:
                        k = len(index)
                        index[key] = k
                        p = me.vertices[v].co
                        pos += [p.x, p.z, p.y]
                        nrm += [n.x, n.z, n.y]
                        cols += [max(0, min(255, int(round(c[i] * 255)))) for i in range(4)]
                        uvs += [u[0], u[1]]
                    ids.append(k)
                idx += [ids[0], ids[2], ids[1]]
            ev.to_mesh_clear()
            nv, nt = len(index), len(idx) // 3
            total += nt
            header['parts'].append({'name': mat, 'mat': mat, 'verts': nv, 'tris': nt})
            blobs.append(struct.pack(f'<{nv * 3}f', *pos) + struct.pack(f'<{nv * 3}f', *nrm) + bytes(cols)
                         + struct.pack(f'<{nv * 2}f', *uvs) + struct.pack(f'<{nt * 3}I', *idx))
        hj = json.dumps(header).encode('utf8')
        with open(os.path.join(out_dir, self.name + '.yjm'), 'wb') as f:
            f.write(b'YJM1' + struct.pack('<I', len(hj)) + hj + b''.join(blobs))
        return total

    def finish(self, ao=True, preview=True, view=None, floor=True, **ao_args):
        """算暗部、导出、出预览图。返回三角形数"""
        self.check_coplanar()
        if ao:
            self.ao(**ao_args)
        objs = self.to_objects()
        tris = self.export(objs)
        if preview and os.environ.get('YJ_PREVIEW', '1') != '0':
            render_preview(self.name, objs, view, floor)
        for ob in objs:
            me = ob.data
            bpy.data.objects.remove(ob)
            bpy.data.meshes.remove(me)
        for b in self.parts.values():
            b.free()
        self.parts = {}
        print(f'[yjm] {self.name}: {tris} tris')
        return tris


# ---------- 预览图 ----------
_mat = None


def preview_material():
    global _mat
    if _mat is None:
        m = bpy.data.materials.new('yj_preview')
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        bsdf = nt.nodes.new('ShaderNodeBsdfDiffuse')
        attr = nt.nodes.new('ShaderNodeAttribute')
        attr.attribute_name = 'col'
        gam = nt.nodes.new('ShaderNodeGamma')
        gam.inputs[1].default_value = 2.2
        nt.links.new(attr.outputs['Color'], gam.inputs[0])
        nt.links.new(gam.outputs[0], bsdf.inputs['Color'])
        nt.links.new(bsdf.outputs[0], out.inputs['Surface'])
        m.use_backface_culling = False
        _mat = m
    return _mat


def setup_scene():
    sc = bpy.context.scene
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    sc.render.engine = 'BLENDER_EEVEE_NEXT'
    sc.render.resolution_x, sc.render.resolution_y = 900, 900
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'Standard'
    sc.eevee.taa_render_samples = 16
    try:
        sc.eevee.use_gtao = True
        sc.eevee.use_shadows = True
    except Exception:
        pass
    w = bpy.data.worlds.new('w')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.62, 0.74, 0.86, 1)
    w.node_tree.nodes['Background'].inputs[1].default_value = 0.55
    sc.world = w
    sun = bpy.data.lights.new('sun', 'SUN')
    sun.energy = 2.4
    sun.color = (1.0, 0.95, 0.86)
    sun.angle = math.radians(3)
    so = bpy.data.objects.new('sun', sun)
    so.rotation_euler = (math.radians(48), 0, math.radians(-38))
    sc.collection.objects.link(so)
    cam = bpy.data.cameras.new('cam')
    cam.lens = 85
    co = bpy.data.objects.new('cam', cam)
    sc.collection.objects.link(co)
    sc.camera = co
    # 地面
    gm = bpy.data.meshes.new('ground')
    gb = bmesh.new()
    bmesh.ops.create_grid(gb, x_segments=1, y_segments=1, size=400)
    gb.to_mesh(gm)
    gb.free()
    go = bpy.data.objects.new('ground', gm)
    gmat = bpy.data.materials.new('ground')
    gmat.use_nodes = True
    gmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.42, 0.55, 0.30, 1)
    gmat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 1
    gm.materials.append(gmat)
    go.location.z = -0.002
    sc.collection.objects.link(go)
    return co


def render_preview(name, objs, view=None, floor=True):
    """view: (水平角度, 俯角, 距离倍数)。默认和游戏里差不多的俯视角"""
    sc = bpy.context.scene
    if sc.camera is None or sc.camera.name != 'cam':
        setup_scene()
    mat = preview_material()
    if 'ground' in bpy.data.objects:
        bpy.data.objects['ground'].hide_render = not floor
    lo, hi = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    for ob in objs:
        if not ob.data.materials:
            ob.data.materials.append(mat)
        for v in ob.data.vertices:
            for i in range(3):
                lo[i] = min(lo[i], v.co[i])
                hi[i] = max(hi[i], v.co[i])
    ctr = (lo + hi) / 2
    rad = max(0.3, (hi - lo).length / 2)
    yaw, pitch, k = view or (0, 48, 1.0)
    yaw, pitch = math.radians(yaw), math.radians(pitch)
    cam = sc.camera
    dist = rad / math.tan(cam.data.angle / 2) * 1.12 * k
    dirv = Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
    cam.location = ctr + dirv * dist
    cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.clip_end = dist * 4 + 100
    os.makedirs(PREVIEW, exist_ok=True)
    sc.render.filepath = os.path.join(PREVIEW, name + '.png')
    bpy.ops.render.render(write_still=True)
