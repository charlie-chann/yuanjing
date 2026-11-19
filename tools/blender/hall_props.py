"""大殿里的陈设（2026-11-17）：佛坛、供桌、五供、长明灯、宫灯、幡、磬、木鱼、经案、功德箱、拜垫、禅修坐垫，外加月台上的太平缸。

每个模型的原点在它自己的地面中心（宫灯、幡是挂点），-y 是正面（朝南，朝殿门）。
摆放的位置见文件末尾的 LAYOUT（Unity 世界坐标 x, y=上, z=北；yaw 按 Unity 的习惯，顺时针为正）。

带手绘贴图的部件叫 paint_<名字>（贴图是 tools/textures/painted_props.py 画的 paint_<名字>.png），
这些部件的 uv 是真的贴图坐标（不是 kit 里普通部件的「相位、发光」）；顶点色照常是白色乘上算出来的暗部（AO）、第四个数照常是摆动幅度。
Unity 那边：材质 toon_paint_<名字>.mat，贴图放在 _BaseMap（见交接说明）。
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

import kit
from kit import Asset, edge_light, new_bm, paint, xform
from palette import C, hexc, mix, tint, vary

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
FONT = os.path.join(ROOT, 'assets', 'fonts', 'SourceHanSerifCN-Bold.otf')


def tex_dir():
    """手绘贴图在哪：YJ_PAINT_DIR > YJ_OUT/textures（先导到别处的时候）> Unity 的 Textures"""
    d = os.environ.get('YJ_PAINT_DIR')
    if d:
        return d
    if os.environ.get('YJ_OUT'):
        return os.path.join(os.environ['YJ_OUT'], 'textures')
    return os.path.join(ROOT, 'unity', 'Sanctuary', 'Assets', 'Toon', 'Textures')


# 贴图尺寸（像素），算 uv 用；和 painted_props.py 里画的一致
TEX_SIZE = {'paint_enamel': (512, 512), 'paint_frontal': (2048, 2048), 'paint_brocade': (1024, 1024), 'paint_banner': (2048, 2048), 'paint_sutra': (1024, 1024),
            'paint_dais': (1024, 512), 'paint_lantern': (1536, 576)}


def px(mat, x0, y0, x1, y1, inset=1.5):
    """贴图上一块矩形（像素，图片左上角是原点）→ (u0, v0, u1, v1)，v 朝上（Unity 的习惯）。inset：往里缩几个像素，免得 mipmap 渗到旁边的图块"""
    W, H = TEX_SIZE[mat]
    return ((x0 + inset) / W, 1 - (y1 - inset) / H, (x1 - inset) / W, 1 - (y0 + inset) / H)


def in_rect(r, s, t):
    return (r[0] + (r[2] - r[0]) * s, r[1] + (r[3] - r[1]) * t)


def rep(s, sc, k, off=0.0):
    """贴图沿 s 重复 k 遍：这个角在它那个面所属的那一遍里是多少（0..1）"""
    return s * k + off - math.floor(sc * k + off)


# 常用颜色（宫殿里的：朱红、金、石青、石绿、明黄）
GOLD, GOLD_D, GOLD_L = C('gold'), C('gold_dark'), tint(C('gold'), 0.08, -0.1)
GILT = hexc('#e2b54a')            # 贴金：比 palette 的 gold 稍沉一点（室内）
GILT_D = hexc('#a77a2a')
RED, RED_D, RED_L = hexc('#b8302a'), hexc('#7e1d18'), hexc('#d24a3a')
LAQ = hexc('#8a2a1e')              # 朱漆（深）
NAVY, NAVY_L = hexc('#24466e'), hexc('#3f6b98')
GREEN, GREEN_L = hexc('#2c6e5a'), hexc('#4f9a7c')
BRASS, BRASS_L, BRASS_D = hexc('#b48a3e'), hexc('#d8b060'), hexc('#7a5a26')
WHITE = C('white')
YEL = hexc('#e8b83a')


class PAsset(Asset):
    """kit.Asset 加上：带贴图坐标的参数曲面（paint_* 部件）、三维文字。预览图里 paint_* 部件贴上贴图。"""

    def __init__(self, name):
        super().__init__(name)
        self.remap = None           # 名字以 cushion_ 开头的会被 kit 换成草编材质，这里不要

    # ---------- 参数曲面 ----------
    def surf(self, P, nu, nv, mat='toon', uv=None, color=(1, 1, 1), colf=None, sway=None, wrap=False, flip=False, weld=True,
             glow=0.0, M=None, fcol=None):
        """参数曲面：P(s, t) → 点（s、t 都在 0..1，分 nu、nv 段）。
        法线朝 dP/ds × dP/dt（旋转体：s 绕 z 逆时针、t 沿轮廓从下往上，法线就朝外）。
        uv(s, t, p, sc, tc) → 贴图坐标（每个角按这个面自己的 s 算，wrap 时 s 不会从 1 跳回 0；sc、tc 是这个面中心的参数，
        贴图要重复几遍时用 rep(s, sc, k) 算，接缝上的角才知道自己是上一遍的 1 还是下一遍的 0）。
        colf(s, t, p) → 颜色；fcol(sc, tc) → 整个面一个颜色（色带边缘干脆，不渐变）；sway(s, t, p) → 摆动幅度。
        wrap：s 首尾相接。weld：把重合的点焊上（旋转体的极点）"""
        t_ = new_bm()
        col = t_.loops.layers.float_color['col']
        uvl = t_.loops.layers.uv['uv']
        nI = nu if wrap else nu + 1
        grid = [[t_.verts.new(P(i / nu, j / nv)) for j in range(nv + 1)] for i in range(nI)]
        ph = self.rng.random()
        for i in range(nu):
            i2 = (i + 1) % nI if wrap else i + 1
            for j in range(nv):
                vs = [grid[i][j], grid[i2][j], grid[i2][j + 1], grid[i][j + 1]]
                st = [(i / nu, j / nv), ((i + 1) / nu, j / nv), ((i + 1) / nu, (j + 1) / nv), (i / nu, (j + 1) / nv)]
                if flip:
                    vs, st = vs[::-1], st[::-1]
                # 重合的角（极点）去掉，退化成三角形
                keep = []
                for k in range(4):
                    if all((vs[k].co - vs[q].co).length > 1e-7 for q in keep):
                        keep.append(k)
                if len(keep) < 3:
                    continue
                try:
                    f = t_.faces.new([vs[k] for k in keep])
                except ValueError:
                    continue
                sc, tc = (i + 0.5) / nu, (j + 0.5) / nv
                fc_ = fcol(sc, tc) if fcol else None
                for l, k in zip(f.loops, keep):
                    s, tt = st[k]
                    p = l.vert.co
                    c = fc_ if fc_ is not None else (colf(s, tt, p) if colf else color)
                    l[col] = (c[0], c[1], c[2], sway(s, tt, p) if sway else 0.0)
                    l[uvl].uv = uv(s, tt, p, sc, tc) if uv else (ph, glow)
        if weld:
            bmesh.ops.remove_doubles(t_, verts=t_.verts, dist=1e-6)
        self.merge(t_, mat, M)

    def rev(self, prof, segs, mat='toon', loc=(0, 0, 0), rot=(0, 0, 0), scale=1, rx=1.0, ry=1.0, uv=None, color=(1, 1, 1),
            colf=None, wobble=None, sway=None, glow=0.0, fcol=None):
        """旋转体（可以是椭圆的）。prof：[(r, z)]；colf(s, j, p)、uv(s, j, p) 里 j 是轮廓上第几个点（可以是小数：t*(n-1)）。
        wobble(ang, j) → 半径的倍数（褶子、瓣）。
        面朝哪边：沿轮廓走，法线在走的方向的右手边（(dz, -dr)），也就是实体要在左手边——外壁从下往上、顶面从外往里、底面从里往外。
        两头都收到轴上的（实心的）轮廓自动按 (r, z) 平面里的面积正负纠正走向；开口的（单片的盘、壳）要自己按这个规矩写"""
        if len(prof) > 2 and prof[0][0] < 1e-6 and prof[-1][0] < 1e-6:
            area = sum(prof[i][0] * prof[i + 1][1] - prof[i + 1][0] * prof[i][1] for i in range(len(prof) - 1))
            if area < 0:
                prof = prof[::-1]
                if colf is not None or uv is not None or sway is not None or fcol is not None:
                    m_ = len(prof) - 1
                    colf = (lambda f: (lambda s, j, p: f(s, m_ - j, p)))(colf) if colf else None
                    uv = (lambda f: (lambda s, j, p, sc, jc: f(s, m_ - j, p, sc, m_ - jc)))(uv) if uv else None
                    sway = (lambda f: (lambda s, j, p: f(s, m_ - j, p)))(sway) if sway else None
                    fcol = (lambda f: (lambda sc, jc: f(sc, m_ - jc)))(fcol) if fcol else None
                if wobble is not None:
                    m_ = len(prof) - 1
                    wobble = (lambda f: (lambda ang, j: f(ang, m_ - j)))(wobble)
        n = len(prof) - 1

        def P(s, t):
            j = int(round(t * n))
            r, z = prof[j][0], prof[j][1]
            a_ = 2 * math.pi * s
            k = wobble(a_, j) if wobble else 1.0
            return Vector((r * rx * k * math.cos(a_), r * ry * k * math.sin(a_), z))
        cf = (lambda s, t, p: colf(s, t * n, p)) if colf else None
        uf = (lambda s, t, p, sc, tc: uv(s, t * n, p, sc, tc * n)) if uv else None
        sf = (lambda s, t, p: sway(s, t * n, p)) if sway else None
        ff = (lambda sc, tc: fcol(sc, tc * n)) if fcol else None
        self.surf(P, segs, n, mat, uf, color, cf, sf, wrap=True, glow=glow, M=xform(loc, rot, scale), fcol=ff)

    def sheet(self, corners, nu, nv, mat, rect=None, color=(1, 1, 1), colf=None, disp=None, sway=None, M=None, back=None, back_off=0.002,
              rep_u=1):
        """一张布/板：corners = (左下, 右下, 右上, 左上)，rect 是贴图上的那一块。disp(s, t) → 沿法线的起伏。
        back：背面的颜色（给就做一个背面，稍微往后挪 2 毫米，免得叠在一起闪）。rep_u：贴图横着重复几遍（nu 要是它的倍数）"""
        p0, p1, p2, p3 = [Vector(c) for c in corners]
        nrm = (p1 - p0).cross(p3 - p0).normalized()

        def P(s, t):
            p = (p0 * (1 - s) + p1 * s) * (1 - t) + (p3 * (1 - s) + p2 * s) * t
            return p + nrm * (disp(s, t) if disp else 0.0)
        uf = (lambda s, t, p, sc, tc: in_rect(rect, rep(s, sc, rep_u) if rep_u > 1 else s, t)) if rect else None
        self.surf(P, nu, nv, mat, uf, color, colf, sway, M=M)
        if back is not None:
            def Pb(s, t):
                return P(s, t) - nrm * back_off
            self.surf(Pb, nu, nv, 'toon', None, back, None, sway, flip=True, M=M)

    # ---------- 三维文字 ----------
    def text3d(self, s, size, depth, loc=(0, 0, 0), rot=(0, 0, 0), color=GILT, mat='gold', bevel=0.0015, res=3, side=None, spacing=1.0):
        """三维的字（思源宋体粗体）：竖着写在 xz 平面上，朝 -y（正面），loc 是字的中心、字面所在的位置往外凸 depth"""
        cu = bpy.data.curves.new('yj_text', 'FONT')
        cu.body = s
        cu.font = bpy.data.fonts.load(FONT, check_existing=True)
        cu.size = size
        cu.space_character = spacing
        cu.align_x, cu.align_y = 'CENTER', 'CENTER'
        cu.extrude = depth / 2
        cu.bevel_depth = bevel
        cu.bevel_resolution = 1
        cu.resolution_u = res
        cu.fill_mode = 'BOTH'
        ob = bpy.data.objects.new('yj_text', cu)
        bpy.context.scene.collection.objects.link(ob)
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        bpy.data.objects.remove(ob)
        bpy.data.curves.remove(cu)
        t_ = new_bm()
        vs = [t_.verts.new(v.co) for v in me.vertices]
        for p in me.polygons:
            try:
                t_.faces.new([vs[i] for i in p.vertices])
            except ValueError:
                pass
        bpy.data.meshes.remove(me)
        bmesh.ops.remove_doubles(t_, verts=t_.verts, dist=1e-6)
        # 思源宋体（CFF 字形）在 Blender 里出来的字比字号小很多：按字形的实际高度放大到「字高 ≈ 0.88 × size」
        ys_ = [v.co.y for v in t_.verts]
        if ys_:
            k = size * 0.88 / max(1e-6, max(ys_) - min(ys_))
            cy_ = (max(ys_) + min(ys_)) / 2
            xs_ = [v.co.x for v in t_.verts]
            cx_ = (max(xs_) + min(xs_)) / 2
            for v in t_.verts:
                v.co.x = (v.co.x - cx_) * k
                v.co.y = (v.co.y - cy_) * k
        bmesh.ops.triangulate(t_, faces=t_.faces[:])
        bmesh.ops.dissolve_degenerate(t_, edges=t_.edges[:], dist=2e-5)
        bmesh.ops.triangulate(t_, faces=t_.faces[:])
        bmesh.ops.recalc_face_normals(t_, faces=t_.faces)
        paint(t_, None, color)
        sd = side if side is not None else tint(color, -0.18)
        cl = t_.loops.layers.float_color['col']
        for f in t_.faces:
            if abs(f.normal.z) < 0.6:        # 字的侧面（笔画的厚度）暗一点
                for l in f.loops:
                    l[cl] = (sd[0], sd[1], sd[2], 0)
        # 字在 xy 平面上、朝 +z；转成竖着朝 -y，字面中心在 loc
        R = Matrix.Rotation(math.pi / 2, 4, 'X')
        bmesh.ops.transform(t_, matrix=Matrix.Translation((0, 0, depth / 2)), verts=t_.verts)
        bmesh.ops.transform(t_, matrix=R, verts=t_.verts)
        self.merge(t_, mat, xform(loc, rot))

    # ---------- 收尾：预览图里 paint_* 部件贴上贴图（kit 自己会贴的话就用 kit 的） ----------
    def finish(self, ao=True, preview=True, view=None, floor=True, **ao_args):
        # glow 部件：uv.y 是发光量（YJToon：emission = _EmissionColor * uv.y）。kit.blob、tube 这些不给 glow 参数的会写成 0，
        # 夜里就不亮了——导出前把所有 glow 部件的 uv.y 统一成 1（uv.x 的相位不动）
        for key, b in self.parts.items():
            if key.split(':')[0] == 'glow':
                uvl = b.loops.layers.uv['uv']
                for f in b.faces:
                    for l in f.loops:
                        l[uvl].uv = (l[uvl].uv[0], 1.0)
        if hasattr(kit, 'paint_preview_material'):
            return super().finish(ao=ao, preview=preview, view=view, floor=floor, **ao_args)
        self.check_coplanar()
        if ao:
            self.ao(**ao_args)
        objs = self.to_objects()
        tris = self.export(objs)
        if preview and os.environ.get('YJ_PREVIEW', '1') != '0':
            for ob in objs:
                m = ob.get('mat', '')
                if m.startswith('paint_'):
                    ob.data.materials.append(_paint_preview(m.split(':')[0]))
                elif m == 'glow':
                    ob.data.materials.append(_glow_preview())
            kit.render_preview(self.name, objs, view, floor)
        for ob in objs:
            me = ob.data
            bpy.data.objects.remove(ob)
            bpy.data.meshes.remove(me)
        for b in self.parts.values():
            b.free()
        self.parts = {}
        print(f'[yjm] {self.name}: {tris} tris')
        return tris


_pmats = {}


def _vcol(nt):
    attr = nt.nodes.new('ShaderNodeAttribute')
    attr.attribute_name = 'col'
    gam = nt.nodes.new('ShaderNodeGamma')
    gam.inputs[1].default_value = 2.2
    nt.links.new(attr.outputs['Color'], gam.inputs[0])
    return gam


def _paint_preview(name):
    if name in _pmats:
        return _pmats[name]
    m = bpy.data.materials.new('prev_' + name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    img = nt.nodes.new('ShaderNodeTexImage')
    p = os.path.join(tex_dir(), name + '.png')
    if os.path.exists(p):
        img.image = bpy.data.images.load(p)
    uvn = nt.nodes.new('ShaderNodeUVMap')
    uvn.uv_map = 'uv'
    nt.links.new(uvn.outputs[0], img.inputs[0])
    mul = nt.nodes.new('ShaderNodeMixRGB')
    mul.blend_type = 'MULTIPLY'
    mul.inputs[0].default_value = 1.0
    nt.links.new(_vcol(nt).outputs[0], mul.inputs[1])
    nt.links.new(img.outputs['Color'], mul.inputs[2])
    b = nt.nodes.new('ShaderNodeBsdfDiffuse')
    nt.links.new(mul.outputs[0], b.inputs['Color'])
    nt.links.new(b.outputs[0], out.inputs['Surface'])
    _pmats[name] = m
    return m


def _glow_preview():
    if 'glow' in _pmats:
        return _pmats['glow']
    m = bpy.data.materials.new('prev_glow')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(_vcol(nt).outputs[0], em.inputs[0])
    em.inputs[1].default_value = 1.6
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    _pmats['glow'] = m
    return m


def smooth_prof(pts, n=4):
    """把一串 (r, z) 用 Catmull-Rom 加密成更圆顺的轮廓（经过原来的每个点）"""
    out = []
    m = len(pts)
    for i in range(m - 1):
        p0, p1, p2, p3 = pts[max(0, i - 1)], pts[i], pts[i + 1], pts[min(m - 1, i + 2)]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[q]) + (-p0[q] + p2[q]) * t + (2 * p0[q] - 5 * p1[q] + 4 * p2[q] - p3[q]) * t2
                                    + (-p0[q] + 3 * p1[q] - 3 * p2[q] + p3[q]) * t3) for q in range(2)))
    out.append(tuple(pts[-1][:2]))
    return out




def plan_square(h, p=14.0):
    """圆角方形（超椭圆）：角度 → 半径倍数"""
    def f(ang):
        c, s = abs(math.cos(ang)), abs(math.sin(ang))
        return h / (c ** p + s ** p) ** (1 / p)
    return f


BRO = 'paint_brocade'


def rope_loop(a, plan, z, r, segs, rect=None, mat=None, cy=0.0, pitch=0.06, sides=6):
    """一圈滚条（金黄绳纹，贴图 paint_brocade 右下 y 896..1024 那条）。plan(ang) → 中心线到圆心的距离（可以是椭圆、圆角方）"""
    rect = rect or px(BRO, 512, 900, 1024, 1020, inset=8)
    mat = mat or BRO

    def C2(ang):
        rr = plan(ang)
        return Vector((rr * math.cos(ang), cy + rr * math.sin(ang), z))
    # 一圈的长度
    Ltot = sum((C2(2 * math.pi * (i + 1) / 256) - C2(2 * math.pi * i / 256)).length for i in range(256))
    # 每一遍绳纹正好占整数个面（不然有的面跨在两遍的接缝上，贴图坐标跑出这一条，取到旁边图块的颜色）
    per = max(1, int(round(segs * pitch / Ltot)))
    reps = max(1, int(round(segs / per)))
    segs = reps * per
    # 弧长参数：s 均匀对应弧长（绳纹不被拉长压扁）
    acc = [0.0]
    for i in range(512):
        acc.append(acc[-1] + (C2(2 * math.pi * (i + 1) / 512) - C2(2 * math.pi * i / 512)).length)

    def ang_of(s):
        target = s * acc[-1]
        lo, hi = 0, 512
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if acc[mid] < target:
                lo = mid
            else:
                hi = mid
        f = (target - acc[lo]) / max(1e-9, acc[lo + 1] - acc[lo])
        return 2 * math.pi * (lo + f) / 512

    def P(s, t):
        ang = ang_of(s)
        c = C2(ang)
        d = (C2(ang + 1e-3) - C2(ang - 1e-3)).normalized()
        out = d.cross(Vector((0, 0, 1))).normalized()
        th = 2 * math.pi * t
        return c + out * (r * math.cos(th)) + Vector((0, 0, r * math.sin(th)))
    a.surf(P, segs, sides, mat, lambda s, t, p, sc, tc: in_rect(rect, rep(s, sc, reps), t), wrap=True)


def knot(a, p, nrm, s):
    """小盘长结：两圈细金线压在布面上，下面垂一小撮红穗"""
    side = Vector((0, 0, 1)).cross(nrm).normalized()
    up = Vector((0, 0, 1))
    for k in range(2):
        pts = []
        for q in range(17):
            th = 2 * math.pi * q / 16
            r = s * (0.55 + 0.45 * math.cos(2 * th)) * (1 - 0.35 * k)
            pts.append(p + nrm * (0.004 + 0.0014 * k) + side * (r * math.cos(th)) + up * (r * math.sin(th)))
        a.tube(pts, 0.0024, GILT, segs=4, mat='gold', cap=False)
    a.blob(0.0065, p + nrm * 0.005, (1, 1, 1), GILT, subdiv=1, bump=0, mat='gold')
    for k in range(5):
        ang = 2 * math.pi * k / 5
        d = side * (0.004 * math.cos(ang)) + nrm * (0.003 + 0.002 * math.sin(ang))
        a.tube([p + d - up * 0.004, p + d * 1.4 - up * 0.03 + nrm * 0.004], [0.0022, 0.0016], RED, segs=4)


# ════════════════════ 拜垫、禅修坐垫 ════════════════════

def kneel_mat(name):
    """拜垫：长圆角矩形的厚垫（宽 0.62、前后 0.75，高 0.12），比规格里的 0.5 深一些：磕头时手、额头在前头、脚尖在后头，都落在垫子上
    （跪拜动作 KOWTOW 手在根骨前约 0.26、脚尖在后约 0.22，按游戏里 0.806 倍算）。
    顶面织锦（外圈红锦金回纹、联珠，里面黄锦、四角如意云、八个卷草、正中一朵莲花，贴 paint_brocade 左上那块，比例和实物一样），
    侧面一圈红锦金卷草，上下两道金黄的滚条，前后左右各一个金线小结垂红穗。
    人跪在上面：顶面边上 0.12、正中略鼓到 0.124（世界 y = 0.72 + 0.124 = 0.844）。"""
    a = PAsset(name)
    RX, RY, PW = 0.31, 0.375, 4.5

    def plan(ang, k=1.0):
        c, s = abs(math.cos(ang)), abs(math.sin(ang))
        return k / ((c / RX) ** PW + (s / RY) ** PW) ** (1 / PW)
    side = [(0.94, 0.0), (0.975, 0.004), (0.993, 0.014), (1.0, 0.03), (1.006, 0.05), (1.008, 0.07), (1.004, 0.088), (0.993, 0.101)]
    top = [(0.975, 0.11), (0.95, 0.1165), (0.9, 0.1195), (0.8, 0.1215), (0.6, 0.1232), (0.35, 0.1238), (0.0, 0.124)]
    prof = [(0.0, 0.0)] + side + top
    n = len(prof) - 1
    js = len(side)
    rect_side = px(BRO, 512, 516, 1024, 636, inset=6)
    KT = (44, 0, 468, 512)                       # painted_props.KNEEL_TOP

    def P(s, t):
        j = int(round(t * n))
        ang = 2 * math.pi * s
        r = plan(ang) * prof[j][0]
        return Vector((r * math.cos(ang), r * math.sin(ang), prof[j][1]))

    def uv(s, t, p, sc, tc):
        jc = tc * n
        if jc < 1:
            return (4 / 1024, 1 - 4 / 1024)                    # 底面：红边上的一点
        if jc < js:
            tt = (p.z - 0.008) / 0.094
            return in_rect(rect_side, rep(s, sc, 10), max(0.0, min(1.0, tt)))
        x, y = p.x / RX, p.y / RY                               # 顶面：投到那块圆角矩形上（+y 是贴图的上边）
        return ((KT[0] + (x + 1) / 2 * (KT[2] - KT[0])) / 1024, 1 - (KT[1] + (1 - y) / 2 * (KT[3] - KT[1])) / 1024)
    a.surf(P, 60, n, BRO, uv, wrap=True)
    # 滚条：顶边一道、底边一道
    rope_loop(a, lambda ang: plan(ang, 0.99), 0.104, 0.0075, 80, sides=5)
    rope_loop(a, lambda ang: plan(ang, 0.982), 0.0065, 0.0065, 80, sides=5)
    # 四面各一个小结（前后左右）
    for i in range(4):
        ang = i * math.pi / 2 + math.pi / 2
        rr = plan(ang, 1.008)
        nrm = Vector((math.cos(ang), math.sin(ang), 0))
        knot(a, Vector((rr * math.cos(ang), rr * math.sin(ang), 0.062)), nrm, 0.02)
    return a.finish(dist=0.25, view=(25, 35, 0.9))


def cushion_hall(name):
    """殿里的禅修坐垫：尺寸、高度和外面的 cushion（props.py）一模一样（坐下的动作是按那个做的），只换了表面：
    方垫 0.8×0.8、厚 0.05、中心往 +y（人面朝的方向）0.12，黄锦面（暗织小团花、正中莲花、四角如意）、红锦金回纹的侧边、顶边一道金黄滚条；
    圆蒲团半径 0.2、顶高 0.18（正中 0.172），黄锦打褶的侧面、顶上一朵绣的莲花团、上下两道滚条。
    蒲团顶面（r ≤ 0.17）的轮廓就是 props.cushion 的那几个点、点和点之间是直线（和原来一样高，人坐的地方 0.176 不能高出一点）；
    侧面才加密成圆的。面数压到 3k 左右（殿里 16 个）"""
    a = PAsset(name)
    W, T, CY = 0.8, 0.05, 0.12
    h = W / 2
    sq = plan_square(h, 16.0)
    rtop = px(BRO, 512, 0, 1024, 512, inset=2)
    rside = px(BRO, 512, 772, 1024, 892, inset=6)
    # ── 方垫：圆角方的「旋转体」，侧面直上直下、顶边圆过去、顶面平（0.05） ──
    prof = [(0.0, 0.0), (0.985, 0.0), (1.0, 0.006), (1.0, 0.036), (0.993, 0.045), (0.982, 0.0492), (0.965, 0.05), (0.6, 0.05), (0.0, 0.05)]
    n = len(prof) - 1

    def P(s, t):
        j = int(round(t * n))
        ang = 2 * math.pi * s
        r = sq(ang) * prof[j][0]
        return Vector((r * math.cos(ang), CY + r * math.sin(ang), prof[j][1]))

    def uv(s, t, p, sc, tc):
        j = tc * n
        if j < 1:
            return (4 / 1024, 1 - 4 / 1024)
        if j < 5:
            # 侧面：看这个面在哪一边，沿那条边的位置当 u
            k = int(math.floor(sc * 4 + 0.5)) % 4
            along = (p.y - CY, -p.x, -(p.y - CY), p.x)[k]
            return in_rect(rside, (along + h) / W, max(0.0, min(1.0, p.z / 0.046)))
        return in_rect(rtop, (p.x + h) / W, (p.y - CY + h) / W)
    a.surf(P, 48, n, BRO, uv, wrap=True)
    # 顶边一道滚条（顶高 0.0555，和原来深色布边 0.053 差不多高）
    rope_loop(a, plan_square(h - 0.004, 16.0), 0.05, 0.0055, 52, cy=CY, sides=4)
    # 四角的小穗
    for (sx, sy) in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        d = Vector((sx, sy, 0)).normalized()
        p = Vector((sx * (h - 0.012), CY + sy * (h - 0.012), 0.03))
        a.blob(0.007, p + d * 0.006, (1, 1, 1), GILT, subdiv=1, bump=0, mat='gold')
        for k in (-1, 0, 1):
            side = Vector((-d.y, d.x, 0)) * (0.004 * k)
            a.tube([p + d * 0.01 + side, p + d * 0.016 + side * 1.5 + Vector((0, 0, -0.026))], [0.0024, 0.0016], RED, segs=4)

    # ── 圆蒲团：顶面就是 props.cushion 的点（0.17, 0.172) (0.12, 0.18) (0.07, 0.176) (0, 0.172)，侧面加密 ──
    prof = [(0.0, 0.0505), (0.17, 0.05), (0.188, 0.0565), (0.2, 0.07), (0.2045, 0.09), (0.205, 0.11), (0.2015, 0.13), (0.195, 0.15),
            (0.185, 0.1625), (0.17, 0.172), (0.12, 0.18), (0.07, 0.176), (0.0, 0.172)]
    j0, j1 = 3, 7          # (0.2, 0.07) 到 (0.195, 0.15) 是打褶的侧面
    rpl = px(BRO, 512, 644, 1024, 764, inset=6)

    def zuv(s, j, p, sc, jc):
        if jc < 1:
            return (4 / 1024, 1 - 4 / 1024)
        if j0 <= jc <= j1:
            return in_rect(rpl, rep(s, sc, 2), max(0.0, min(1.0, (p.z - 0.07) / 0.08)))
        R0 = 0.205 if jc < j0 else 0.195
        RP = 240 if jc < j0 else 236
        return ((256 + p.x / R0 * RP) / 1024, 1 - (768 - p.y / R0 * RP) / 1024)

    def pleat(ang, j):
        # 侧面的褶子：只往里收（不超出原来的外径）
        if j0 <= j <= j1:
            k = math.sin(math.pi * (j - j0) / (j1 - j0))
            return 1.0 - 0.02 * k * (0.5 + 0.5 * math.cos(20 * ang))
        return 1.0
    a.rev(prof, 40, BRO, uv=zuv, wobble=pleat)
    rope_loop(a, lambda ang: 0.1935, 0.1505, 0.0055, 36, sides=4)
    rope_loop(a, lambda ang: 0.1985, 0.0695, 0.0055, 36, sides=4)
    return a.finish(dist=0.4, view=(25, 40, 0.95))


# ════════════════════ 公共的小零件：莲瓣、圆角矩形的线脚、方截面的弯腿、卷草 ════════════════════

def petal(a, base, d, n, L, W, T, mat, c0, c1, rim=None, cup=0.22, curl=0.12, ridge=0.35, nu=6, nv=6, tipw=0.0, bulge=1.0, round_=0.0,
          bow=0.0, rim_w=0.78, local_n=False):
    """一片莲瓣：从 base 沿 d 长 L、宽 W、厚 T，n 是瓣外面（凸面）朝的方向。
    cup：瓣两边往里收（瓣是凹的）；curl：瓣尖往外翻；ridge：瓣中一道脊；rim：沥粉贴金的描边颜色（瓣的边缘一圈）。
    颜色从瓣根 c0 渐变到瓣尖 c1（退晕）"""
    d = Vector(d).normalized()
    n = Vector(n)
    n = (n - d * n.dot(d)).normalized()
    s_ = d.cross(n).normalized()
    b = Vector(base)

    def hw(t):
        t = min(1.0, t)
        sharp = 0.32 * (1 - t) ** 1.4 + 0.82 * math.sin(math.pi * t ** 0.78)
        # 圆瓣（荷花）：中段宽、到瓣尖才很快收成一个小尖
        rnd = (0.25 + 0.75 * math.sin(math.pi * 0.5 * min(1.0, t / 0.55)) ** 0.8) * (1 - max(0.0, (t - 0.72) / 0.28) ** 1.6) ** 0.55
        return W / 2 * (sharp * (1 - round_) + rnd * round_) + tipw * math.sin(math.pi * t ** 0.6)

    def mid(t, w):
        return (b + d * (L * t) + s_ * (w * hw(t)) - n * (cup * W * 0.5 * w * w * math.sin(math.pi * min(1.0, t * 0.9 + 0.1)))
                + n * (curl * L * t ** 3) - n * (bow * L * math.sin(math.pi * t)))

    def thick(t, w):
        return T / 2 * math.sqrt(max(0.0, 1 - w * w)) * math.sin(math.pi * t) ** 0.6 * bulge

    def colf(w, t):
        c = mix(c0, c1, t ** 0.8)
        if rim is not None and (abs(w) > rim_w or t > 0.93):
            return rim
        return c

    def nloc(t, w):
        # local_n：沿中面在这一点的法线加厚（瓣兜得很深时用）；默认沿 n 加厚（瓣尖卷得厉害、瓣又厚时，沿局部法线加厚会把外层折叠起来）
        if not local_n:
            return n
        e = 1e-3
        dw = mid(t, min(1.0, w + e)) - mid(t, max(-1.0, w - e))
        dt = mid(min(1.0, t + e), w) - mid(max(0.0, t - e), w)
        m = dw.cross(dt)
        if m.length < 1e-12:
            return n
        m.normalize()
        return m if m.dot(n) > 0 else -m

    def Po(s, t):
        w = s * 2 - 1
        return mid(t, w) + nloc(t, w) * (thick(t, w) + T * ridge * math.exp(-(w / 0.16) ** 2) * math.sin(math.pi * t) ** 1.5)

    def Pi(s, t):
        w = s * 2 - 1
        return mid(t, w) - nloc(t, w) * thick(t, w)
    # 外面（+n 那面）按 dP/ds × dP/dt = (d×n)×d = n 本来就朝外；里面那片要反过来
    a.surf(Po, nu, nv, mat, colf=lambda s, t, p: colf(s * 2 - 1, t), weld=False)
    a.surf(Pi, nu, nv, mat, colf=lambda s, t, p: tint(colf(s * 2 - 1, t), -0.08), weld=False, flip=True)


def bao_petal(a, base, d, n, L, W, H, mat, c_edge, c_mid, c_in, rim, ws=None, ts=None, rim_mat=None, bow=0.0, cup=0.0,
              base_w=0.7, sink=0.0015, back=None, ridge=0.35):
    """宝装莲瓣（浮雕的一片）：瓣根宽、中段最宽、瓣尖收成一个尖；瓣面鼓起、中间一道脊，瓣心一片小瓣（颜色浅一档）。
    base 瓣根中点，d 瓣尖方向，n 瓣面朝外的方向；长 L、宽 W、鼓起最高 H。
    网格是不均匀的（ws 横着从 -1 到 1、ts 竖着从 0 到 1）：贴金的描边、瓣心的小瓣都落在网格线上，每个面一个颜色（边缘干净，不渐变糊开）。
    边界一圈压在底面往下 sink（贴着器身/枭面，看不见背面）；back 给颜色的话再做一个扇形的背面（瓣根悬空、从下面看得见的时候）。
    bow：沿瓣长方向往里弯（贴着鼓腹）；cup：横着往里兜"""
    d = Vector(d).normalized()
    n = Vector(n)
    n = (n - d * n.dot(d)).normalized()
    s_ = d.cross(n).normalized()
    b = Vector(base)
    ws = ws or [-1.0, -0.86, -0.6, -0.3, 0.0, 0.3, 0.6, 0.86, 1.0]
    ts = ts or [0.0, 0.1, 0.22, 0.36, 0.5, 0.64, 0.78, 0.9, 1.0]
    nu, nv = len(ws) - 1, len(ts) - 1

    def hw(t):
        # 半宽：瓣根 base_w，t 0.4 最宽，往瓣尖收成尖（稍带一点内凹的弧，像桃尖）
        if t <= 0.4:
            f = base_w + (1 - base_w) * math.sin(math.pi / 2 * t / 0.4)
        else:
            u = (t - 0.4) / 0.6
            f = math.cos(math.pi / 2 * u ** 1.1) ** 0.9 * (1 - 0.12 * math.sin(math.pi * u) * u)
        return W / 2 * max(0.0, f)

    def inner(t):
        # 瓣心小瓣的半宽（相对 hw）：t 0.1..0.8 之间；也是一片瓣的样子——瓣根圆、t 0.38 最宽、往上收成尖（不是两头圆的一块）
        if t <= 0.1 or t >= 0.8:
            return 0.0
        u = (t - 0.1) / 0.7
        if u < 0.4:
            f = math.sin(math.pi / 2 * u / 0.4) ** 0.8
        else:
            f = math.cos(math.pi / 2 * (u - 0.4) / 0.6) ** 1.1
        return 0.42 * f

    def height(w, t):
        aw = abs(w)
        body = (1 - aw ** 2) ** 0.55 * math.sin(math.pi * min(1.0, t * 1.02)) ** 0.5
        rid = ridge * max(0.0, 1 - aw / 0.3) * math.sin(math.pi * t) ** 0.8
        # 瓣心小瓣：比外瓣面略高一点点（只够在边上留一道细细的影子，不做成一块平台）
        k = inner(t)
        lift = 0.07 * min(1.0, (k - aw) / 0.08) if (k > 0 and aw <= k + 1e-6) else 0.0
        return H * (body + rid + lift) - (sink if (aw > 0.999 or t < 1e-6 or t > 0.999) else 0.0)

    def warp(c, t):
        # 网格的列 c → 真正的横向位置 w：|c| ≤ 0.3 的几列挤到瓣心小瓣的轮廓里（随 t 变宽变窄），0.3..0.6 填中间，外面不动。
        # 这样小瓣的边正好落在网格线上，是一片瓣的形状（不是一个方块）
        k = inner(t)
        ac, sg = abs(c), (1 if c >= 0 else -1)
        if ac <= 0.3:
            return sg * ac / 0.3 * k
        if ac <= 0.6:
            return sg * (k + (ac - 0.3) / 0.3 * (0.6 - k))
        return c

    def P(si, ti):
        w, t = warp(si, ti), ti
        return (b + d * (L * t) + s_ * (w * hw(t)) + n * height(w, t) - n * (bow * L * math.sin(math.pi * t))
                - n * (cup * W * 0.5 * w * w))
    gold = rim_mat or mat
    pts = [[P(w, t) for t in ts] for w in ws]
    tb = new_bm()
    col = tb.loops.layers.float_color['col']
    uvl = tb.loops.layers.uv['uv']
    vs = [[tb.verts.new(p) for p in row] for row in pts]
    tg = new_bm()
    colg = tg.loops.layers.float_color['col']
    uvg = tg.loops.layers.uv['uv']
    vg = [[tg.verts.new(p) for p in row] for row in pts]
    ph = a.rng.random()
    for i in range(nu):
        for j in range(nv):
            wc, tc = (ws[i] + ws[i + 1]) / 2, (ts[j] + ts[j + 1]) / 2
            is_rim = rim is not None and (abs(wc) > 0.86 or tc > ts[-2] + 1e-6)
            if is_rim:
                c = rim
            elif inner(tc) > 0 and abs(wc) < 0.3:          # 小瓣两头那一行收成一个点（三角形），小瓣的根和尖都是尖的、不是平头
                c = c_in
            elif abs(wc) > 0.6:
                c = c_edge
            else:
                c = c_mid
            T_, V_, CL, UV = (tg, vg, colg, uvg) if (is_rim and rim_mat) else (tb, vs, col, uvl)
            q = [V_[i][j], V_[i + 1][j], V_[i + 1][j + 1], V_[i][j + 1]]
            keep = []
            for k_ in range(4):
                if all((q[k_].co - q[m_].co).length > 1e-7 for m_ in keep):
                    keep.append(k_)
            if len(keep) < 3:
                continue
            try:
                f = T_.faces.new([q[k_] for k_ in keep])
            except ValueError:
                continue
            for l in f.loops:
                l[CL] = (c[0], c[1], c[2], 0.0)
                l[UV].uv = (ph, 0.0)
    # 法线朝 dP/dw × dP/dt = s_ × d = -n？这里 s_ = d × n，所以 s_ × d = n：朝外，不用翻
    for T_ in (tb, tg):
        bmesh.ops.remove_doubles(T_, verts=T_.verts, dist=1e-7)
    a.merge(tb, mat)
    if len(tg.faces):
        a.merge(tg, gold)
    else:
        tg.free()
    if back is not None:
        # 背面：边界一圈 + 背后一个点，扇形
        loop = [pts[i][0] for i in range(nu + 1)] + [pts[nu][j] for j in range(1, nv + 1)] + \
               [pts[i][nv] for i in range(nu - 1, -1, -1)] + [pts[0][j] for j in range(nv - 1, 0, -1)]
        clean = []
        for p in loop:
            if not clean or (p - clean[-1]).length > 1e-7:
                clean.append(p)
        if (clean[0] - clean[-1]).length < 1e-7:
            clean.pop()
        cen = b + d * (L * 0.4) - n * (H * 0.4 + bow * L)
        tk = new_bm()
        ck = tk.loops.layers.float_color['col']
        vk = [tk.verts.new(p) for p in clean]
        vc = tk.verts.new(cen)
        for i in range(len(vk)):
            try:
                f = tk.faces.new((vc, vk[(i + 1) % len(vk)], vk[i]))
            except ValueError:
                continue
            for l in f.loops:
                l[ck] = (back[0], back[1], back[2], 0.0)
        bmesh.ops.recalc_face_normals(tk, faces=tk.faces)
        # 背面要朝 -n（recalc 按封闭性猜，开口的扇形不一定对：按和 -n 的点积再纠正一遍）
        for f in tk.faces:
            if f.normal.dot(n) > 0:
                bmesh.ops.reverse_faces(tk, faces=[f])
        a.merge(tk, mat)


def petal_row(a, p0, p1, z, nrm, L, W, T, mat, c0, c1, rim, up=True, tilt=25.0, spacing=None, double=True, **kw):
    """沿一条直线排一排莲瓣（须弥座的仰莲、覆莲）：瓣根在 z，瓣尖朝上（仰）或朝下（覆），往外 nrm 方向倾 tilt 度。
    double：两层错开（后一层露出瓣尖）"""
    p0, p1 = Vector(p0), Vector(p1)
    nrm = Vector(nrm).normalized()
    Lr = (p1 - p0).length
    spacing = spacing or W * 0.92
    k = max(1, int(round(Lr / spacing)))
    sg = 1 if up else -1
    tl = math.radians(tilt)
    dvec = Vector((0, 0, sg)) * math.cos(tl) + nrm * math.sin(tl)
    out = nrm * math.cos(tl) - Vector((0, 0, sg)) * math.sin(tl)
    for layer in ((0, 1.0, 0.0), (1, 0.82, 0.5)) if double else ((0, 1.0, 0.0),):
        li, sc, off = layer
        for i in range(k + (1 if li else 0)):
            f = (i + 0.5 - off) / k
            if f < 0.0 or f > 1.0:
                continue
            p = p0.lerp(p1, f) + Vector((0, 0, z)) - nrm * (0.012 * li) + Vector((0, 0, -sg * 0.01 * li))
            petal(a, p, dvec, out, L * sc, W, T, mat, c0 if not li else tint(c0, -0.08), c1 if not li else tint(c1, -0.06), rim, **kw)


def _rr_layout(hx, hy, rc, step, ncorner):
    """圆角矩形边界上的取样点（只记「第几条边/第几个角、走到哪」），换个偏移量再算位置时点数、顺序都不变"""
    ex, ey = hx - rc, hy - rc
    items = []
    for k in range(4):
        L = 2 * (ex if k % 2 == 0 else ey)
        m = max(1, int(round(L / step)))
        items += [('e', k, i / m) for i in range(m)]
        if rc > 1e-6:
            items += [('c', k, i / ncorner) for i in range(ncorner)]
    return items


def _rr_point(it, hx, hy, rc, off):
    """往外偏 off 以后的圆角矩形（角上的圆半径跟着变：rc + off，偏进去比 rc 还多就成了尖角，不会翻过来打结）。返回 (点, 外法线)"""
    R = max(0.0, rc + off)
    HX, HY = hx + off, hy + off
    X, Y = HX - R, HY - R
    kind, k, f = it
    if kind == 'e':
        (ax, ay), (bx, by), nn = (((-X, -HY), (X, -HY), (0, -1)), ((HX, -Y), (HX, Y), (1, 0)),
                                  ((X, HY), (-X, HY), (0, 1)), ((-HX, Y), (-HX, -Y), (-1, 0)))[k]
        return Vector((ax + (bx - ax) * f, ay + (by - ay) * f)), Vector(nn)
    cx, cy, a0 = ((X, -Y, -90), (X, Y, 0), (-X, Y, 90), (-X, -Y, 180))[k]
    ang = math.radians(a0 + 90 * f)
    nv_ = Vector((math.cos(ang), math.sin(ang)))
    return Vector((cx, cy)) + nv_ * R, nv_


def rrect_ring(hx, hy, rc, step=0.06, ncorner=4):
    """圆角矩形的边界一圈：([(点, 外法线)], 弧长表)，逆时针，从 -y 那条边的左端开始"""
    out = [_rr_point(it, hx, hy, rc, 0.0) for it in _rr_layout(hx, hy, rc, step, ncorner)]
    arc = [0.0]
    for i in range(1, len(out) + 1):
        arc.append(arc[-1] + (out[i % len(out)][0] - out[i - 1][0]).length)
    return out, arc


def rrect_sweep(a, hx, hy, rc, prof, mat='toon', color=(1, 1, 1), colf=None, uv=None, step=0.06, ncorner=4, loc=(0, 0, 0),
                cap_top=False, cap_bottom=False, cap_color=None):
    """沿圆角矩形扫一条轮廓线（台面的冰盘沿、须弥座的枋和枭）：prof = [(往外偏多少, 高度)] 从下往上。
    uv(arc, j, p, sc, jc)：arc 是这一点沿边界的弧长（米）。colf(j, p) → 颜色。
    每一圈都是一个真的圆角矩形（往里偏得比圆角半径还多就成了尖角），封顶、封底的面不会自己打结"""
    items = _rr_layout(hx, hy, rc, step, ncorner)
    _, arc = rrect_ring(hx, hy, rc, step, ncorner)
    N, n = len(items), len(prof) - 1
    o = Vector(loc)
    rows = []
    for (off, z) in prof:
        rows.append([Vector((q.x, q.y, z)) + o for (q, _n) in (_rr_point(it, hx, hy, rc, off) for it in items)])

    def P(s, t):
        return rows[int(round(t * n))][int(round(s * N)) % N]

    def ARC(s):
        return arc[int(round(s * N))]
    uf = (lambda s, t, p, sc, tc: uv(ARC(s), t * n, p, sc, tc * n)) if uv else None
    cf = (lambda s, t, p: colf(t * n, p)) if colf else None
    a.surf(P, N, n, mat, uf, color, cf, wrap=True, weld=False)
    for (flag, j, up) in ((cap_bottom, 0, False), (cap_top, n, True)):
        if not flag:
            continue
        t_ = new_bm()
        pts = []
        for p in rows[j]:
            if not pts or (p - pts[-1]).length > 1e-6:
                pts.append(p)
        if len(pts) > 2 and (pts[0] - pts[-1]).length < 1e-6:
            pts.pop()
        vs = [t_.verts.new(p) for p in pts]
        t_.faces.new(vs if up else vs[::-1])
        paint(t_, None, cap_color or color)
        a.merge(t_, mat)


def sq_path(a, pts, sizes, color, mat='toon', ch=0.25, colors=None, caps=True, ref=None, aspect=1.0):
    """方截面（四角倒圆）的一根弯料：腿、牙子、桌脚的马蹄。sizes 每个点的边长。ch：倒角占边长的比例。
    截面的方向沿路径「平行移动」（不会在拐弯处突然转 90°、把料拧坏）：第一个点按 ref（截面 x 轴大致朝哪，默认：竖直的料朝 -x、
    水平的料朝上）定好，后面每个点只把上一个点的 x 轴投到新的截面上。法线朝外（截面在 (nx, ny) 里逆时针、nx × ny = 切线）"""
    pts = [Vector(p) for p in pts]
    m = len(pts)
    if isinstance(sizes, (int, float)):
        sizes = [sizes] * m
    sec = []
    for k in range(4):
        ang = k * math.pi / 2
        for (u, v) in ((0.5, -0.5 + ch / 2), (0.5, 0.5 - ch / 2)):
            ca, sa = math.cos(ang), math.sin(ang)
            sec.append((u * ca - v * sa, u * sa + v * ca))
    tgs = [(pts[min(m - 1, i + 1)] - pts[max(0, i - 1)]).normalized() for i in range(m)]
    if ref is None:
        ref = Vector((-1, 0, 0)) if abs(tgs[0].z) > 0.7 else Vector((0, 0, 1))
    ref = Vector(ref)
    nx = ref - tgs[0] * ref.dot(tgs[0])
    if nx.length < 1e-6:
        nx = Vector((0, 1, 0)) - tgs[0] * tgs[0].y
    nx.normalize()
    frames = []
    for i in range(m):
        tg = tgs[i]
        nx = nx - tg * nx.dot(tg)
        nx.normalize()
        ny = tg.cross(nx).normalized()
        frames.append((nx.copy(), ny))

    def P(s, t):
        i = int(round(t * (m - 1)))
        q = int(round(s * 8)) % 8
        nx_, ny_ = frames[i]
        u, v = sec[q]
        return pts[i] + nx_ * (u * sizes[i]) + ny_ * (v * sizes[i] * aspect)
    cf = (lambda s, t, p: colors[int(round(t * (m - 1)))]) if colors else None
    a.surf(P, 8, m - 1, mat, None, color, cf, wrap=True, weld=False)
    if caps:
        for (i, rev_) in ((0, True), (m - 1, False)):
            t_ = new_bm()
            vs = [t_.verts.new(P(q / 8, i / (m - 1))) for q in range(8)]
            t_.faces.new(vs[::-1] if rev_ else vs)
            paint(t_, None, colors[i] if colors else color)
            a.merge(t_, mat)


def scroll2d(c, r0, turns, a0, sgn=1, n=24, shrink=0.25):
    """平面上的一个卷（卷草、云头）：从外往里旋，返回 [(x, y)]"""
    out = []
    for i in range(n + 1):
        t = i / n
        ang = a0 + sgn * 2 * math.pi * turns * t
        r = r0 * (1 - (1 - shrink) * t)
        out.append((c[0] + r * math.cos(ang), c[1] + r * math.sin(ang)))
    return out


def relief(a, pts2d, frame, r, color, mat='gold', taper=True, segs=None):
    """把平面上的一串点贴到一个面上做成凸起的线（卷草、云纹的阳线）。frame = (原点, u 方向, v 方向, 外法线)"""
    o, U_, V_, N_ = frame
    pts = [o + U_ * x + V_ * y + N_ * (r * 0.4) for (x, y) in pts2d]
    if len(pts) < 2:
        return
    radii = [r * (1.0 - 0.55 * (i / (len(pts) - 1)) if taper else 1.0) for i in range(len(pts))]
    a.tube(pts, radii, color, segs=segs or (4 if r < 0.003 else 5), mat=mat)


def cloud_scroll(a, frame, cx, cy, s, color, flip=1, mat='gold', r=None):
    """一朵如意云头的阳线（左右对称）：心形的外轮廓——下面一个尖、两边两个大卷瓣、顶上一个小圆瓣，
    两个大卷瓣里各一个往里旋的卷。大小：宽约 1.5 s、高约 1.1 s，(cx, cy) 是中心。flip 不再用（对称的，正反一样）"""
    r = r or s * 0.09
    half = [(0.0, -0.46), (-0.2, -0.36), (-0.46, -0.24), (-0.66, -0.04), (-0.72, 0.18), (-0.62, 0.36), (-0.44, 0.44), (-0.3, 0.38),
            (-0.26, 0.5), (-0.15, 0.6), (0.0, 0.63)]
    if s < 0.04:
        half = half[::2] + [half[-1]] if len(half) % 2 == 0 else half[::2]      # 很小的（宫灯上 4 厘米的）少一半点
    ring = half + [(-x, y) for (x, y) in half[::-1][1:]]
    ring = smooth_prof(ring, 2) if s >= 0.07 else ring
    relief(a, [(cx + x * s, cy + y * s) for (x, y) in ring], frame, r, color, mat, taper=False, segs=4 if s < 0.07 else 5)
    n2 = max(6, min(14, int(s * 150))) if s >= 0.07 else (6 if s >= 0.04 else 5)
    for sg in (-1, 1):
        # 卷瓣里的卷：从卷瓣和顶瓣之间的那个凹口出发，贴着外轮廓往外、往下转，再往里旋到中心
        c_ = (cx + sg * 0.42 * s, cy + 0.12 * s)
        a0 = math.pi * 0.42 if sg < 0 else math.pi * 0.58
        relief(a, scroll2d(c_, 0.21 * s, 1.0, a0, -sg, n2, shrink=0.2), frame, r * 0.85, color, mat, segs=4)
    # 顶瓣里一道小弧（像如意头上的一道凹线）
    relief(a, [(cx + x * s, cy + y * s) for (x, y) in ((-0.1, 0.36), (-0.05, 0.43), (0.0, 0.45), (0.05, 0.43), (0.1, 0.36))], frame, r * 0.7,
           color, mat, taper=False, segs=4)


def vine(a, frame, x0, x1, y, amp, period, color, r, mat='gold', leaf=True):
    """一条卷草：主藤是波浪线，每个波峰波谷长出一个卷"""
    n = max(8, int((x1 - x0) / period * 12))
    main = [(x0 + (x1 - x0) * i / n, y + amp * math.sin(2 * math.pi * ((x1 - x0) * i / n) / period)) for i in range(n + 1)]
    relief(a, main, frame, r, color, mat, taper=False)
    k = int((x1 - x0) / (period / 2))
    for i in range(k):
        xc = x0 + period / 4 + i * period / 2
        if xc > x1 - period * 0.2:
            break
        sg = 1 if i % 2 == 0 else -1
        yc = y + sg * amp
        relief(a, scroll2d((xc + period * 0.12, yc - sg * amp * 0.05), amp * 0.75, 1.0, math.pi * (0.5 if sg > 0 else 1.5), -sg,
                           max(9, min(18, int(amp * 650)))),
               frame, r * 0.9, color, mat)
        if leaf:
            relief(a, [(xc - period * 0.02, yc), (xc - period * 0.12, yc + sg * amp * 0.55), (xc - period * 0.2, yc + sg * amp * 0.65)],
                   frame, r * 0.8, color, mat)


def plate(a, poly, frame, th, color, mat='toon', bevel=0.0, back=None):
    """一块平板：poly 是板面上的轮廓 [(u, v)]（逆时针），frame = (原点, u 方向, v 方向, 外法线)；往里（-外法线）厚 th"""
    o, U_, V_, N_ = [Vector(x) for x in frame]
    t_ = new_bm()
    fr = [t_.verts.new(o + U_ * u + V_ * v) for (u, v) in poly]
    bk = [t_.verts.new(o + U_ * u + V_ * v - N_ * th) for (u, v) in poly]
    f0 = t_.faces.new(fr)
    t_.faces.new(bk[::-1])
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        t_.faces.new((fr[j], fr[i], bk[i], bk[j]))
    bmesh.ops.recalc_face_normals(t_, faces=t_.faces)
    bev = []
    if bevel > 0:
        bev = bmesh.ops.bevel(t_, geom=list(f0.edges), offset=bevel, offset_type='OFFSET', segments=1, profile=0.5, affect='EDGES',
                              clamp_overlap=True)['faces']
    paint(t_, None, color)
    if back is not None:
        paint(t_, [f for f in t_.faces if f.normal.dot(N_) < -0.5], back)
    edge_light(t_, bev)
    a.merge(t_, mat)


FRO = 'paint_frontal'


def _apron_edge(n=3):
    """牙条的下沿（壸门式）：u 0..1 → 离牙条上沿多远（米，正数往下）。两头是牙头，中间一个垂下来的小尖"""
    ctrl = [(0.0, 0.105), (0.05, 0.1), (0.09, 0.07), (0.13, 0.05), (0.42, 0.05), (0.47, 0.058), (0.5, 0.078), (0.53, 0.058),
            (0.58, 0.05), (0.87, 0.05), (0.91, 0.07), (0.95, 0.1), (1.0, 0.105)]
    return smooth_prof(ctrl, n)


def _table(a, W, D, H, frontal_rect, val_frac, seed=0):
    """供桌：束腰、冰盘沿的台面，四条马蹄腿，壸门牙条上贴金卷草；前面挂桌围（刺绣，下沿金穗），台面铺黄缎、三面垂边。
    台面（黄缎）高 H + 0.004"""
    hx, hy = W / 2, D / 2
    LQ = 'lacquer'
    lq, lq_l, lq_d = LAQ, tint(LAQ, 0.07), tint(LAQ, -0.12)
    # ── 台面：冰盘沿（上面盖着黄缎，顶面不做） ──
    prof = [(-0.05, H - 0.05), (-0.004, H - 0.05), (0.0, H - 0.046), (0.0, H - 0.032), (0.003, H - 0.024), (0.0045, H - 0.013),
            (0.003, H - 0.005), (-0.002, H - 0.0005), (-0.04, H - 0.0005)]
    rrect_sweep(a, hx, hy, 0.02, prof, LQ, colf=lambda j, p: lq_l if 3 <= j <= 6 else lq, cap_bottom=True, cap_color=lq_d, step=0.08)
    # ── 束腰：往里收，中间一道金线 ──
    wz0, wz1 = H - 0.088, H - 0.05
    rrect_sweep(a, hx - 0.028, hy - 0.028, 0.01, [(-0.01, wz0 - 0.002), (0.0, wz0), (0.0, wz1), (-0.01, wz1 + 0.002)], LQ, color=lq_d, step=0.1)
    ring, _ = rrect_ring(hx - 0.028, hy - 0.028, 0.01, 0.1, 3)
    pts = [(p.x + q.x * 0.003, p.y + q.y * 0.003, (wz0 + wz1) / 2) for (p, q) in ring]
    pts.append(pts[0])
    a.tube(pts, 0.0035, GILT, segs=5, mat='gold', cap=False)
    # ── 四条腿：方料、四角倒圆，下面马蹄足往里兜 ──
    ins, ls = 0.05, 0.078
    for sx in (-1, 1):
        for sy in (-1, 1):
            lx, ly = sx * (hx - ins), sy * (hy - ins)
            din = Vector((-sx, -sy, 0)).normalized()
            base = Vector((lx, ly, 0))
            path = [base + Vector((0, 0, wz1 - 0.005)), base + Vector((0, 0, 0.4)), base + Vector((0, 0, 0.2)),
                    base + din * 0.006 + Vector((0, 0, 0.13)), base + din * 0.02 + Vector((0, 0, 0.09)), base + din * 0.034 + Vector((0, 0, 0.065))]
            sq_path(a, path, [ls, ls * 0.95, ls * 0.88, ls * 0.95, ls * 1.05, ls * 1.0], lq, LQ,
                    colors=[lq, lq, lq, lq_d, lq_d, tint(lq_d, -0.1)])
            # 马蹄上的贴金小卷（朝外的两面各一个）
            for (nx_, ny_) in ((sx, 0), (0, sy)):
                N_ = Vector((nx_, ny_, 0))
                U_ = Vector((0, 0, 1)).cross(N_)
                o = base + N_ * (ls * 0.5 + 0.001) + Vector((0, 0, 0.07))
                relief(a, scroll2d((0.0, 0.0), 0.016, 1.1, math.pi * 0.5, 1 if (nx_ + ny_) > 0 else -1, 14), (o, U_, Vector((0, 0, 1)), N_),
                       0.0032, GILT)
    # ── 牙条：四面，壸门式下沿，贴金卷草 ──
    edge = [(u, dz * 1.25) for (u, dz) in _apron_edge()]
    th = 0.02
    for k, (L, cen, N_, U_) in enumerate((
            (W - 2 * ins - ls, Vector((0, -(hy - ins + ls / 2 - 0.004), 0)), Vector((0, -1, 0)), Vector((1, 0, 0))),
            (W - 2 * ins - ls, Vector((0, hy - ins + ls / 2 - 0.004, 0)), Vector((0, 1, 0)), Vector((-1, 0, 0))),
            (D - 2 * ins - ls, Vector((hx - ins + ls / 2 - 0.004, 0, 0)), Vector((1, 0, 0)), Vector((0, 1, 0))),
            (D - 2 * ins - ls, Vector((-(hx - ins + ls / 2 - 0.004), 0, 0)), Vector((-1, 0, 0)), Vector((0, -1, 0))))):
        V_ = Vector((0, 0, 1))
        poly = [(-L / 2 + u * L, -dz) for (u, dz) in edge]
        poly = [(L / 2 + 0.002, 0.0), (-L / 2 - 0.002, 0.0)] + [(-L / 2 - 0.002, poly[0][1])] + poly[1:-1] + [(L / 2 + 0.002, poly[-1][1])]
        # 逆时针（从外面看）：上沿从右到左，再沿下沿从左到右
        o = cen + Vector((0, 0, wz0))
        plate(a, poly, (o, U_, V_, N_), th, lq, LQ, bevel=0.003)
        if k == 0:
            continue                        # 正面挂着桌围，看不见
        fr = (o + N_ * 0.0005, U_, V_, N_)
        # 中间一朵云头，两边卷草
        cloud_scroll(a, fr, 0.0, -0.04, 0.045, GILT, r=0.0038)
        vine(a, fr, -L / 2 + 0.13, -0.08, -0.034, 0.011, 0.09, GILT, 0.0032, leaf=True)
        vine(a, fr, 0.08, L / 2 - 0.13, -0.034, 0.011, 0.09, GILT, 0.0032, leaf=True)
        for sg in (-1, 1):
            relief(a, scroll2d((sg * (L / 2 - 0.045), -0.07), 0.02, 1.1, math.pi * (0.0 if sg > 0 else 1.0), sg, 16), fr, 0.0034, GILT)
    # ── 托泥：腿下一圈落地的木框，四角下面各垫一只小龟足 ──
    tx, ty = hx - ins + ls * 0.25, hy - ins + ls * 0.25
    # 托泥：一圈方框（截面闭合：底、外立面、顶、里立面）
    rrect_sweep(a, tx, ty, 0.012, [(-0.07, 0.022), (-0.004, 0.022), (0.0, 0.026), (0.0, 0.055), (-0.004, 0.06), (-0.07, 0.06), (-0.07, 0.022)], LQ,
                colf=lambda j, p: lq_l if j == 3 else lq_d, cap_top=False, step=0.12, ncorner=3)
    for sx in (-1, 1):
        for sy in (-1, 1):
            a.lathe([(0.0, 0.0), (0.034, 0.0, lq_d), (0.04, 0.012, lq), (0.034, 0.022), (0.0, 0.022)], (sx * (tx - 0.03), sy * (ty - 0.03), 0), segs=10,
                    color=lq_d, mat=LQ)
    # 托泥上沿一道金线（看得见的三面）
    for (p0, p1) in (((-tx - 0.001, -ty + 0.02), (-tx - 0.001, ty - 0.02)), ((tx + 0.001, -ty + 0.02), (tx + 0.001, ty - 0.02)),
                     ((-tx + 0.02, ty + 0.001), (tx - 0.02, ty + 0.001))):
        a.tube([(p0[0], p0[1], 0.05), (p1[0], p1[1], 0.05)], 0.003, GILT, segs=5, mat='gold')
    # 两侧：腿和托泥之间一块镂空的「券口」牙子（卷草）
    for sx in (-1, 1):
        x = sx * (hx - ins + ls / 2 - 0.006)
        L = D - 2 * ins - ls
        N_, U_ = Vector((sx, 0, 0)), Vector((0, sx, 0))
        for (zb, flip) in ((0.06, 1),):
            poly = [(-L / 2, 0.0), (L / 2, 0.0), (L / 2, 0.075), (L / 2 - 0.03, 0.06), (L / 2 - 0.05, 0.03), (L / 2 - 0.08, 0.016),
                    (-L / 2 + 0.08, 0.016), (-L / 2 + 0.05, 0.03), (-L / 2 + 0.03, 0.06), (-L / 2, 0.075)]
            o = Vector((x, 0, zb))
            plate(a, poly, (o, U_, Vector((0, 0, 1)), N_), 0.018, lq, LQ, bevel=0.002)
            relief(a, scroll2d((-L / 2 + 0.035, 0.035), 0.016, 1.0, math.pi, -1, 14), (o + N_ * 0.0005, U_, Vector((0, 0, 1)), N_), 0.003, GILT)
            relief(a, scroll2d((L / 2 - 0.035, 0.035), 0.016, 1.0, 0.0, 1, 14), (o + N_ * 0.0005, U_, Vector((0, 0, 1)), N_), 0.003, GILT)
    # ── 桌围：前面垂下来，竖着几道柔和的褶子，下沿一排金红相间的穗子 ──
    yf = -(hy + 0.008)
    z0f, z1f = 0.03, H - 0.047                 # 桌围上沿藏在台面冰盘沿下面（不和台面的立面叠在一起）
    nf = max(6, int(W / 0.26))

    def fold(s, t):
        return -0.012 * (0.5 + 0.5 * math.cos(2 * math.pi * s * nf)) * (1 - t) ** 1.2 - 0.002
    a.sheet([(-hx, yf, z0f), (hx, yf, z0f), (hx, yf, z1f), (-hx, yf, z1f)], nf * 6, 8, FRO, frontal_rect, disp=fold, back=RED_D)
    rng = a.rng
    nstr = int(W / 0.0075)
    for i in range(nstr):
        s = (i + 0.5) / nstr
        x = -hx + W * s
        y = yf + fold(s, 0) * -1 * -1
        y = yf - fold(s, 0)
        c = GILT if (i // 3) % 2 == 0 else RED
        ln = 0.024 + rng.uniform(-0.003, 0.003)
        a.tube([(x, y, z0f + 0.004), (x + rng.uniform(-0.002, 0.002), y - 0.001, z0f - ln)], [0.0022, 0.0016], vary(c, rng, 0.04, 0.02), segs=3,
               mat='gold' if c is GILT else 'toon', cap=False)
    # ── 台面上的黄缎：暗花缎（paint_frontal 里可以平铺的那块，0.3 米一个花），四边圆圆地翻下去（翻边半径 1.4 厘米），
    # 前面和两侧再垂一截缎边（paint_frontal 底下那条：回纹、莲瓣），翻边和垂边接缝处一道金色滚边 ──
    zt = H + 0.004
    yv, xv = -(hy + 0.016), hx + 0.012
    yb = hy + 0.004
    rr_ = 0.014
    cyc, hyc = (yv + yb) / 2, (yb - yv) / 2
    tiled_sheet(a, -xv + rr_, xv - rr_, yv + rr_, yb - rr_, zt, 0.3, DAMASK_RECT, FRO, ox=-0.15, oy=cyc - 0.15)
    roll = [(-rr_ + rr_ * math.sin(th), zt - rr_ + rr_ * math.cos(th)) for th in [math.pi / 2 * (1 - i / 4) for i in range(5)]]
    rrect_sweep(a, xv, hyc, rr_, roll, FRO, uv=lambda arc, j, p, sc, jc: DAMASK_UV0, step=0.15, ncorner=3, loc=(0, cyc, 0))
    vh = 0.15
    zv = zt - rr_
    vrect = px(FRO, 0, 1280, 2048 * val_frac, 1408)
    a.sheet([(-xv, yv, zt - vh), (xv, yv, zt - vh), (xv, yv, zv), (-xv, yv, zv)], max(4, int(W / 0.1)), 2, FRO, vrect,
            back=tint(YEL, -0.35))
    srect = px(FRO, 0, 1280, 2048 * (D + 0.02) / 2.4, 1408)
    a.sheet([(xv, yv, zt - vh), (xv, hy + 0.004, zt - vh), (xv, hy + 0.004, zv), (xv, yv, zv)], 8, 2, FRO, srect, back=tint(YEL, -0.35), back_off=0.0035)
    a.sheet([(-xv, hy + 0.004, zt - vh), (-xv, yv, zt - vh), (-xv, yv, zv), (-xv, hy + 0.004, zv)], 8, 2, FRO, srect, back=tint(YEL, -0.35), back_off=0.0035)
    # 翻边和垂边的接缝：一道金色滚边（前面和两侧，拐角跟着圆角走）
    cr = []
    for k in range(4):
        ang = -math.pi / 2 + math.pi / 2 * k / 3
        cr.append((xv - rr_ + (rr_ + 0.0035) * math.cos(ang), yv + rr_ + (rr_ + 0.0035) * math.sin(ang)))
    edge_pts = [(-xv - 0.0035, yb, zv), (-xv - 0.0035, yv + rr_, zv)] + [(-p_[0], p_[1], zv) for p_ in cr[::-1]][1:-1] + \
               [(-xv + rr_, yv - 0.0035, zv), (xv - rr_, yv - 0.0035, zv)] + [(p_[0], p_[1], zv) for p_ in cr][1:-1] + \
               [(xv + 0.0035, yv + rr_, zv), (xv + 0.0035, yb, zv)]
    a.tube(edge_pts, 0.0045, GILT, segs=6, mat='gold')


DAMASK_RECT = px(FRO, 512, 1456, 1024, 1968, inset=2.5)      # 暗花缎（painted_props.DAMASK）
DAMASK_UV0 = ((640 + 0.5) / 2048, 1 - (1516 + 0.5) / 2048)   # 暗花缎里素地的一点（painted_props.DAMASK_PLAIN）


def tiled_sheet(a, x0, x1, y0, y1, z, T, rect, mat, ox=0.0, oy=0.0, color=(1, 1, 1)):
    """水平的一块（朝上），贴图 rect 按 T 米一块平铺：网格线正好落在每块贴图的边上，每个面的 uv 只落在一块里（图集里的一块也能平铺）。
    ox、oy：贴图的原点（第 0 块的左下角）在哪"""
    xs = sorted(set([x0, x1] + [ox + k * T for k in range(-40, 41) if x0 + 1e-6 < ox + k * T < x1 - 1e-6]))
    ys = sorted(set([y0, y1] + [oy + k * T for k in range(-40, 41) if y0 + 1e-6 < oy + k * T < y1 - 1e-6]))
    t_ = new_bm()
    col = t_.loops.layers.float_color['col']
    uvl = t_.loops.layers.uv['uv']
    V = [[t_.verts.new((x, y, z)) for y in ys] for x in xs]
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            xc, yc = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            tx0 = ox + math.floor((xc - ox) / T) * T
            ty0 = oy + math.floor((yc - oy) / T) * T
            f = t_.faces.new((V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]))
            for l in f.loops:
                p = l.vert.co
                l[uvl].uv = in_rect(rect, (p.x - tx0) / T, (p.y - ty0) / T)
                l[col] = (color[0], color[1], color[2], 0.0)
    a.merge(t_, mat)


def altar_table(name):
    """中间的大供桌：2.4 宽、0.75 深、0.78 高（台面黄缎 0.784）。摆在 (0, 0.72, 19.2)"""
    a = PAsset(name)
    _table(a, 2.4, 0.75, 0.78, px(FRO, 0, 0, 2048, 600), 1.0)
    return a.finish(dist=0.6, view=(28, 22, 0.85))


def altar_table_side(name):
    """两边的小供桌：1.5 宽、0.6 深、0.78 高。摆在 (±3.6, 0.72, 19.35)"""
    a = PAsset(name)
    _table(a, 1.5, 0.6, 0.78, px(FRO, 0, 640, 1312, 1240), 1.5 / 2.4, seed=1)
    return a.finish(dist=0.6, view=(28, 22, 0.85))



# ════════════════════ 五供：香炉、烛台、花觚；果盘、长明灯 ════════════════════

BZ, BZ_L, BZ_D = hexc('#5c3f2c'), hexc('#b48a52'), hexc('#2f2119')      # 宣德炉那种暗紫铜，口沿、耳上磨得发亮
ASH = hexc('#7a7570')


INCENSE = hexc('#a8352a')


def censer_hall(name, lite=False):
    """殿里供桌上的香炉（五供正中）：宣德式铜炉——鼓腹、收颈、外撇的口沿，口沿上两只朝冠耳；
    颈上一圈凸起的回纹带，肩上三组兽面（饕餮：凸眼、卷眉、翻角，中间的鼻梁兼作扉棱），腹下一圈贴着器身的覆莲瓣（鎏金描边），
    三只象鼻足（象首贴在炉底，鼻子往下外伸、末端卷成一个涡站在炉座上）。下面一个五瓣如意形的红木炉座：起线的座面、束腰、
    垂下的牙子、五只三弯腿（腿脚往外卷）。
    炉里一层香灰（灰色，残香脚边上一圈烧黑了，几截掉下来的香灰卷），插着烧剩的香脚（红竹签，圆的），正中半径 0.05 以内空着给玩家插香。
    香灰面：口沿处（r 0.125）高 0.172、正中 0.178。原点在炉座底面中心；摆在大供桌上 (0, 1.504, 19.0)，
    香灰正中的世界坐标 (0, 1.682, 19.0)（0.75 倍的侧供桌香炉：正中高 0.1335）。
    lite：两边侧供桌上那两只（0.75 倍、离人远一点）——同样的外形和高度，省掉兽面、象首的细节，残香少一些，面数大约一半"""
    a = PAsset(name)
    rng = a.rng
    SEG = 44 if lite else 64
    B = 'bronze'
    WM = 'wood_dark'
    wd, wl, wdd = hexc('#4a2a1f'), hexc('#6e4030'), hexc('#2e1912')
    # ── 炉座：五瓣如意形 ──
    def lobe(ang, j=0):
        return 1.0 + 0.075 * math.cos(5 * ang)
    top = [(0.0, 0.026), (0.86, 0.026), (0.9, 0.0275), (0.95, 0.03), (0.985, 0.0325), (1.0, 0.0345), (0.99, 0.0365), (0.95, 0.0375),
           (0.9, 0.0378), (0.0, 0.0378)]
    a.rev([(r * 0.172, z) for (r, z) in top], 40 if lite else 60, WM, colf=lambda s, j, p: wl if 4 <= j <= 6 else (wdd if j <= 1 else wd), wobble=lobe)
    # 座面边上一道描金细线
    a.tube([(0.168 * lobe(t) * math.cos(t), 0.168 * lobe(t) * math.sin(t), 0.0373) for t in [2 * math.pi * k / 60 for k in range(61)]], 0.0011,
           GILT, segs=4, mat='gold', cap=False)
    # 束腰、牙子（往外撇、下沿五个垂下来的小尖）
    a.rev([(0.0, 0.019), (0.148, 0.019), (0.146, 0.021), (0.146, 0.026), (0.0, 0.026)], 60, WM, color=wdd, wobble=lobe)
    apron = [(0.0, 0.012), (0.15, 0.012), (0.158, 0.0135), (0.163, 0.016), (0.162, 0.019), (0.0, 0.019)]
    a.rev(apron, 60, WM, colf=lambda s, j, p: wl if j == 3 else wd, wobble=lambda ang, j: lobe(ang) * (1.0 if j < 1 else 1.0))
    for i in range(5):
        ang = 2 * math.pi * i / 5
        r = 0.158 * lobe(ang)
        o = Vector((math.cos(ang), math.sin(ang), 0))
        # 三弯腿：从牙子下往外鼓、再收回来，脚往外卷一个小涡
        pts = [o * (r - 0.012) + Vector((0, 0, 0.015)), o * (r - 0.004) + Vector((0, 0, 0.011)), o * (r + 0.004) + Vector((0, 0, 0.0065)),
               o * (r + 0.003) + Vector((0, 0, 0.003)), o * (r + 0.008) + Vector((0, 0, 0.0012)), o * (r + 0.013) + Vector((0, 0, 0.0022)),
               o * (r + 0.0135) + Vector((0, 0, 0.0055)), o * (r + 0.01) + Vector((0, 0, 0.0062))]
        a.tube(pts, [0.0075, 0.007, 0.0058, 0.005, 0.0042, 0.0035, 0.0028, 0.0022], wd, segs=7, mat=WM, color2=wl)

    # ── 炉身 ──
    prof = [(0.0, 0.075), (0.06, 0.074), (0.1, 0.08), (0.13, 0.092), (0.148, 0.106), (0.155, 0.12), (0.154, 0.132), (0.15, 0.145),
            (0.143, 0.156), (0.136, 0.163), (0.132, 0.168), (0.132, 0.174), (0.138, 0.18), (0.148, 0.188), (0.155, 0.194), (0.157, 0.198),
            (0.153, 0.2015), (0.145, 0.2015), (0.135, 0.197), (0.127, 0.188), (0.125, 0.178), (0.124, 0.168)]
    R_of = prof_r(prof[2:])

    def bcol(s, j, p):
        k = noise.noise(p * 40) * 0.05
        if 13 <= j <= 17:
            return tint(BZ_L, k)                               # 口沿磨亮
        c = mix(BZ_D, BZ, min(1.0, max(0.0, (p.z - 0.075) / 0.06)))
        return tint(c, k + 0.04 * noise.noise(p * 9 + Vector((2, 7, 1))))
    a.rev(prof, SEG, B, colf=bcol)
    # 颈上一圈回纹（凸线），上下两道弦纹
    if lite:
        # 侧供桌上的：颈上只做上下两道弦纹、中间一道凸起的素带（不做回纹）
        for (zz, rr_) in ((0.1628, 0.0014), (0.168, 0.0026), (0.1732, 0.0014)):
            a.tube([((R_of(zz) + 0.0008) * math.cos(t), (R_of(zz) + 0.0008) * math.sin(t), zz) for t in [2 * math.pi * q / 44 for q in range(45)]],
                   rr_, BZ_L if rr_ < 0.002 else BZ, segs=4, mat=B, cap=False)
    else:
        meander_band(a, R_of, 0.1625, 0.1735, 30, BZ_L, B, rr=0.0013)
    # 肩上三组兽面（正面一组，另两组在两侧后方；三只足在它们中间）
    for g in range(0 if lite else 3):
        beast_mask(a, R_of, 2 * math.pi * g / 3 - math.pi / 2, 0.138, 0.07, BZ, tint(BZ_L, -0.06), B)
    # 肩、腹之间一道弦纹
    NR = 44 if lite else 72
    a.tube([((R_of(0.1225) + 0.0012) * math.cos(t), (R_of(0.1225) + 0.0012) * math.sin(t), 0.1225) for t in [2 * math.pi * q / NR for q in range(NR + 1)]],
           0.0018, BZ_L, segs=4, mat=B, cap=False)
    # 腹下一圈覆莲（宝装莲瓣）：瓣根在腹最宽处下面一点，顺着鼓腹往下贴（bow 让瓣跟着器身弯），瓣面鼓起、中间一道脊，
    # 瓣心一片小瓣（亮一档的铜），鎏金描边；相邻两瓣在瓣根处挨着，瓣尖之间露出器身
    NP = 12 if lite else 16
    for i in range(NP):
        ang = 2 * math.pi * (i + 0.5) / NP
        o = Vector((math.cos(ang), math.sin(ang), 0))
        za, zb_ = 0.122, 0.093
        pa = o * R_of(za) + Vector((0, 0, za))
        pb = o * R_of(zb_) + Vector((0, 0, zb_))
        d = (pb - pa).normalized()
        nrm = (o - d * o.dot(d)).normalized()
        L = (pb - pa).length
        bao_petal(a, pa + nrm * 0.0008, d, nrm, L, 0.078 if lite else 0.06, 0.0036 if lite else 0.004, B, tint(BZ, -0.03), tint(BZ, 0.02), tint(BZ, 0.08),
                  tint(GILT, -0.1), ts=[0.0, 0.1, 0.25, 0.42, 0.6, 0.78, 0.9, 1.0] if lite else [0.0, 0.1, 0.18, 0.28, 0.39, 0.5, 0.61, 0.71, 0.8, 0.9, 1.0],
                  bow=-0.1, cup=0.1, back=BZ_D)
    # ── 三只象鼻足：象首贴在炉底往外探出来（圆额、一对大耳朵往后张、眼、白牙），鼻子粗、往下伸到炉座面上往外卷成一个涡 ──
    TUSK = hexc('#e6dcc4')
    for i in range(3):
        ang = 2 * math.pi * i / 3 + math.pi / 2
        o = Vector((math.cos(ang), math.sin(ang), 0))
        side = Vector((-o.y, o.x, 0))
        hc = o * 0.118 + Vector((0, 0, 0.083))                  # 象首：一半埋在炉底里
        a.blob(0.021, hc, (1.0, 1.2, 1.0), BZ, subdiv=2, bump=0.0, mat=B, rot=(0, 0, ang), top=BZ_L)
        # 额头上鼓起的一块（顶光照着亮）
        a.blob(0.013, hc + o * 0.009 + Vector((0, 0, 0.009)), (1.0, 1.3, 0.8), tint(BZ, 0.05), subdiv=2, bump=0.0, mat=B, rot=(0, 0, ang),
               top=BZ_L)
        for sg in (-1, 1):
            # 耳朵：一大片往两边、往后张开的扇形（3 厘米多），边上一道亮边，耳心凹一点
            ec = hc + side * sg * 0.019 - o * 0.004 + Vector((0, 0, 0.002))
            ed = (side * sg * 0.75 - o * 0.45 + Vector((0, 0, -0.35))).normalized()
            en = (o * 0.85 + side * sg * 0.35).normalized()
            if lite:
                a.blob(0.016, ec + ed * 0.012, (0.3, 1.0, 1.15), BZ, subdiv=1, bump=0, mat=B, rot=(0, 0, ang + sg * 0.6))
            else:
                bao_petal(a, ec, ed, en, 0.034, 0.034, 0.003, B, BZ, tint(BZ, 0.04), tint(BZ, -0.08), tint(BZ_L, -0.05),
                          ws=[-1.0, -0.8, -0.35, 0.0, 0.35, 0.8, 1.0], ts=[0.0, 0.2, 0.5, 0.78, 0.92, 1.0], cup=0.25, base_w=0.55,
                          back=BZ_D, ridge=0.0)
                # 眼睛：一圈眼眶、黑眼珠
                ey = hc + o * 0.016 + side * sg * 0.0105 + Vector((0, 0, 0.006))
                a.blob(0.0034, ey, (1, 1, 1), BZ_L, subdiv=1, bump=0, mat=B)
                a.blob(0.0022, ey + o * 0.0022, (1, 1, 1), hexc('#1a120d'), subdiv=1, bump=0, mat=B)
                # 牙：白的，从嘴边往前往上翘
                tb_ = hc + o * 0.017 + side * sg * 0.0075 - Vector((0, 0, 0.008))
                a.tube([tb_, tb_ + o * 0.008 - Vector((0, 0, 0.004)), tb_ + o * 0.016 + side * sg * 0.003 + Vector((0, 0, 0.001))],
                       [0.0026, 0.0021, 0.0008], TUSK, segs=6)
        # 鼻子：从额前往外、往下，粗 → 细；到炉座面（0.0378）上从里往下、往外、再往上卷一个涡（涡的平面朝外竖着，侧面看得出卷）
        Z_ = Vector((0, 0, 1))
        cc_ = o * 0.153 + Z_ * 0.0548
        pts = [hc + o * 0.017 + Z_ * 0.002, hc + o * 0.025 - Z_ * 0.007, o * 0.144 + Z_ * 0.068, o * 0.1415 + Z_ * 0.061]
        rad = [0.0098, 0.0094, 0.0088, 0.0084]
        nq = 12 if lite else 16
        for q in range(1, nq + 1):
            f = q / nq
            th = math.pi + f * math.pi * 1.75
            R_ = 0.0118 * (1 - 0.55 * f)
            pts.append(cc_ + o * (R_ * math.cos(th)) + Z_ * (R_ * math.sin(th)))
            rad.append(0.0082 * (1 - 0.55 * f))
        a.tube(pts, rad, BZ, segs=8 if lite else 10, mat=B, color2=tint(BZ, -0.15))
        if not lite:
            # 鼻子上一节节的横纹（压下去的细线：暗色细环，几乎贴着鼻子）
            for q in range(4):
                t = 0.15 + 0.22 * q
                p = pts[1].lerp(pts[3], t)
                tg = (pts[3] - pts[1]).normalized()
                bi = tg.cross(side).normalized()
                ring = [p + (side * math.cos(th_) + bi * math.sin(th_)) * 0.0089 for th_ in [math.pi * (0.15 + 0.7 * q_ / 6) for q_ in range(7)]]
                a.tube(ring, 0.0009, BZ_D, segs=3, mat=B, cap=True)
    # ── 两只朝冠耳（口沿上竖起来、往外撇的方环耳），里外两道棱 ──
    for sx in (-1, 1):
        for (dy, rr, cc) in ((0.0, 0.0075, BZ), (0.0068, 0.0024, BZ_L), (-0.0068, 0.0024, BZ_L)):
            pts = [(sx * 0.134, dy, 0.1985), (sx * 0.14, dy, 0.215), (sx * 0.149, dy, 0.232), (sx * 0.16, dy, 0.243), (sx * 0.17, dy, 0.238),
                   (sx * 0.169, dy, 0.222), (sx * 0.162, dy, 0.207), (sx * 0.155, dy, 0.199)]
            a.tube(pts, rr, cc, segs=8 if rr > 0.005 else 4, mat=B)
    # ── 香灰：微微隆起，几处小坑 ──
    # 第五轮（评审：近看灰面还是平的一片灰）：再撒一层三五毫米的小灰疙瘩、几个小坑（香灰落下来结成的一粒粒），
    # 网格加密到 3 毫米一圈（原来 8 毫米一格，这么小的疙瘩做不出来）；疙瘩顶上颜色浅一点、坑里深一点（ash_col）
    import random as _rnd
    lr = _rnd.Random(911)
    lumps = []
    for _ in range(40 if lite else 110):
        rr_ = 0.118 * math.sqrt(lr.random())
        aa_ = lr.uniform(0, 2 * math.pi)
        rad = lr.uniform(0.0016, 0.0028)
        lumps.append((rr_ * math.cos(aa_), rr_ * math.sin(aa_), rad, lr.uniform(0.0016, 0.0032) * (-0.7 if lr.random() < 0.18 else 1.0)))

    def lump_h(x, y):
        h = 0.0
        for (lx, ly, rad, hh) in lumps:
            d2 = (x - lx) ** 2 + (y - ly) ** 2
            if d2 < 9 * rad * rad:
                h += hh * math.exp(-d2 / (rad * rad))
        return h

    def ash_z(x, y):
        r = math.hypot(x, y)
        # 评审第三轮：灰面像一块平的灰泥 —— 起伏加大一倍（一个个小灰堆、小坑）
        rim = 1 - max(0.0, (r - 0.112) / 0.013)          # 贴着炉口那一圈不起疙瘩（和炉壁接得上）
        return (0.172 + 0.006 * (1 - (r / 0.125) ** 2) + 0.0035 * noise.noise(Vector((x * 30, y * 30, 3.0)))
                + 0.0018 * noise.noise(Vector((x * 90, y * 90, 7.0))) + lump_h(x, y) * max(0.0, rim))
    stubs = []
    # 残香脚插得密一些（评审：一床烧剩的香脚，不是稀稀拉拉几根）
    NST = 16 if lite else 34
    for i in range(NST):
        for _ in range(30):
            angs = rng.uniform(0, 2 * math.pi)
            r = rng.uniform(0.056, 0.115)
            x, y = r * math.cos(angs), r * math.sin(angs)
            if all(math.hypot(x - q[0], y - q[1]) > 0.0115 for q in stubs):
                break
        stubs.append((x, y))

    def ash_col(s_, t_, p):
        c = tint(ASH, 0.05 * noise.noise(p * 60) + 0.03 * noise.noise(p * 15) - 0.03 * t_ + 22.0 * lump_h(p.x, p.y))
        for (x, y) in stubs:
            d = math.hypot(p.x - x, p.y - y)
            if d < 0.014:
                c = mix(c, hexc('#3b3631'), (1 - d / 0.014) ** 1.3 * 0.8)         # 香脚边上烧黑了（中间黑、往外淡回灰色）
        return c
    a.surf(lambda s_, t_: Vector((0.1245 * t_ * math.cos(2 * math.pi * s_), 0.1245 * t_ * math.sin(2 * math.pi * s_),
                                  ash_z(0.1245 * t_ * math.cos(2 * math.pi * s_), 0.1245 * t_ * math.sin(2 * math.pi * s_)))),
           96 if lite else 160, 26 if lite else 42, 'toon', colf=ash_col, wrap=True, flip=True)
    # 残香：红竹签的香脚，高矮不一（露出灰面 1..6 厘米）、歪 6..15 度；颜色有褪成粉红的、有暗红的；
    # 头上一截烧焦（灰黑 → 灰），比签子细一点。前三炷还在烧
    STUB_C = [hexc('#c46a5e'), hexc('#b4544a'), hexc('#a03a30'), hexc('#8a2e26'), hexc('#6e231d')]
    for i, (x, y) in enumerate(stubs):
        burning = i <= 2
        h = rng.uniform(0.13, 0.17) if burning else rng.uniform(0.01, 0.06)
        tl = math.radians(rng.uniform(2, 6) if burning else rng.uniform(6, 15))
        az = rng.uniform(0, 2 * math.pi)
        lean = Vector((math.sin(tl) * math.cos(az), math.sin(tl) * math.sin(az), math.cos(tl)))
        b0 = Vector((x, y, ash_z(x, y) - 0.012))
        top = b0 + lean * (h + 0.012)
        rr = 0.0016 if burning else rng.uniform(0.0016, 0.0021)
        sc_ = vary(INCENSE, rng, 0.04, 0.03) if burning else vary(STUB_C[rng.randrange(len(STUB_C))], rng, 0.04, 0.04)
        burnt = 0.0 if burning else rng.uniform(0.004, 0.009)
        a.tube([b0, top - lean * (0.06 if burning else burnt)], rr, sc_, segs=6, mat='toon', cap=False)
        if not burning:
            a.tube([top - lean * burnt, top - lean * (burnt * 0.4), top], [rr * 0.96, rr * 0.82, rr * 0.55], hexc('#2b2724'), segs=6, mat='toon',
                   cap=True, color2=hexc('#77716b'))
        # 香脚边上一圈烧黑的灰：直接画在香灰面的顶点色里（ash_col），不另外垫一片（垫片的边会看出来，像个小垫圈）
        if burning:
            # 还在烧的三炷：上半截是褐色的香身，香头一点红光（glow），上面顶一小截灰
            a.tube([top - lean * 0.06, top], rr * 1.35, hexc('#6b4a33'), segs=6, mat='toon', cap=True)
            a.blob(0.0024, top + lean * 0.004, (1, 1, 1.4), (1.0, 0.45, 0.15), subdiv=1, bump=0, mat='glow')
            a.tube([top + lean * 0.0062, top + lean * 0.011], [rr * 1.25, rr * 1.0], hexc('#8f8a84'), segs=6, mat='toon', cap=True)
    # 掉在灰上的几截香灰：灰色的短圆条（香烧完剩下的灰柱，粗 4..5 毫米、长 1..3 厘米），有的微微弯、有的断成两三截，
    # 平躺着、一半陷在灰里；颜色比灰面浅一点点（不是白的）
    for i in range(4 if lite else 8):
        for _ in range(30):
            angs = rng.uniform(0, 2 * math.pi)
            r = rng.uniform(0.055, 0.105)
            x, y = r * math.cos(angs), r * math.sin(angs)
            if all(math.hypot(x - q[0], y - q[1]) > 0.016 for q in stubs):
                break
        d0 = rng.uniform(0, 2 * math.pi)
        bend = rng.choice((-1, 1)) * rng.uniform(0.35, 0.9)
        Ltot = rng.uniform(0.01, 0.03)
        npc = 1 if Ltot < 0.016 else rng.choice((1, 2, 3))
        rr = rng.uniform(0.0025, 0.003)
        cc = mix(hexc('#86817b'), hexc('#9a958f'), rng.random())          # 只比灰面浅一点（灰面 #7a7570），不是白的
        seg = Ltot / npc
        pos, dd = Vector((x, y, 0)), d0
        for k in range(npc):
            pts = []
            for q in range(4):
                t = q / 3
                ang = dd + bend * t * seg / 0.03
                p_ = pos + Vector((math.cos(ang), math.sin(ang), 0)) * (seg * t)
                pts.append(Vector((p_.x, p_.y, ash_z(p_.x, p_.y) + rr * 0.35)))
            a.tube(pts, [rr * 0.8, rr, rr, rr * 0.75], vary(cc, rng, 0.03, 0.02), segs=6, mat='toon', cap=True, flat=0.8,
                   color2=tint(cc, -0.12))
            # 断口：下一截错开一点、拐一点
            last = pts[-1]
            dd = dd + bend * seg / 0.03 + rng.uniform(-0.35, 0.35)
            pos = Vector((last.x, last.y, 0)) + Vector((math.cos(dd), math.sin(dd), 0)) * rng.uniform(0.002, 0.004)
    # 铜器凹处积一点黑（纹样的根部）
    occ_tint(a, [B], BZ_D, amount=0.55, dist=0.012, samples=8 if lite else 10, power=1.2)
    return a.finish(dist=0.3, view=(20, 25, 0.9))


def censer_hall_side(name):
    """两边侧供桌上的香炉（摆 0.75 倍）：和 censer_hall 同一个样子、同样的香灰高度（0.75 倍后正中 0.1335），细节省一半面数"""
    return censer_hall(name, lite=True)


def candlestick(name):
    """烛台（一对，五供两侧）：铜（黄铜）的，喇叭形底座、竹节杆、两颗宝珠节、大承盘口沿一圈莲瓣、烛扦；
    插一支红蜡烛（身上描金盘龙：贴图 paint_frontal 左下那块，龙头、鳞、爪、火珠、祥云都画在上面），顶上烧化一个浅坑，蜡泪顺着流下来；
    烛芯上一朵火苗（glow）。原点在底面中心，总高约 0.69"""
    a = PAsset(name)
    B = 'bronze'
    br, bl, bd = BRASS, BRASS_L, BRASS_D
    prof = [(0.0, 0.0), (0.098, 0.0), (0.104, 0.006), (0.1, 0.014), (0.085, 0.02), (0.068, 0.032), (0.058, 0.05), (0.062, 0.062),
            (0.055, 0.075), (0.036, 0.09), (0.026, 0.105), (0.022, 0.13), (0.03, 0.142), (0.022, 0.154), (0.018, 0.19),
            (0.026, 0.2), (0.018, 0.21), (0.017, 0.235), (0.034, 0.25), (0.042, 0.265), (0.034, 0.28), (0.02, 0.29), (0.02, 0.305),
            (0.05, 0.315), (0.1, 0.322), (0.112, 0.33), (0.108, 0.336), (0.09, 0.332), (0.05, 0.328), (0.022, 0.33), (0.016, 0.345),
            (0.016, 0.36), (0.0, 0.36)]

    def col(s, j, p):
        k = 0.06 * noise.noise(p * 30)
        if j in (2, 7, 12, 16, 19, 24, 25):
            return tint(bl, k)
        return tint(br if j % 3 else bd, k)
    a.rev(prof, 30, B, colf=col)
    # 底座上一圈覆莲瓣、承盘口沿一圈仰莲瓣
    for i in range(12):
        ang = 2 * math.pi * (i + 0.5) / 12
        out = Vector((math.cos(ang), math.sin(ang), 0))
        petal(a, out * 0.06 + Vector((0, 0, 0.058)), out * 0.85 + Vector((0, 0, -0.5)), out + Vector((0, 0, 0.6)), 0.04, 0.034, 0.006, B,
              br, bl, rim=bl, cup=0.1, curl=0.0, ridge=0.45, nu=4, nv=4)
    for i in range(16):
        ang = 2 * math.pi * i / 16
        out = Vector((math.cos(ang), math.sin(ang), 0))
        petal(a, out * 0.1 + Vector((0, 0, 0.326)), out * 0.55 + Vector((0, 0, 0.84)), out, 0.034, 0.042, 0.005, B,
              br, bl, rim=bl, cup=0.15, curl=0.15, ridge=0.4, nu=4, nv=4)
    # 三只小如意足
    for i in range(3):
        ang = 2 * math.pi * i / 3 + math.pi / 2
        o = Vector((math.cos(ang), math.sin(ang), 0))
        a.blob(0.02, o * 0.09 + Vector((0, 0, 0.004)), (1.2, 0.8, 0.45), bd, subdiv=2, bump=0, mat=B, rot=(0, 0, ang))
    # ── 蜡烛：身子贴 paint_frontal 里画的描金盘龙（红蜡地、金龙绕一圈、上下金箍），顶上烧化的一个浅坑 ──
    red, red_d = hexc('#c3261d'), hexc('#8f1712')
    zc0, zc1, rc = 0.345, 0.6, 0.03
    crect = px(FRO, 0, 1416, 480, 2040, inset=1)
    zs1 = zc1 - 0.004

    def cP(s_, t_):
        ang = 2 * math.pi * s_
        return Vector((rc * math.cos(ang), rc * math.sin(ang), zc0 + (zs1 - zc0) * t_))
    a.surf(cP, 32, 10, FRO, lambda s_, t_, p, sc, tc: in_rect(crect, s_, t_), wrap=True)
    a.rev([(rc, zs1), (rc * 0.985, zc1 - 0.0012), (rc * 0.93, zc1), (rc * 0.8, zc1 - 0.003), (rc * 0.45, zc1 - 0.007), (0.0, zc1 - 0.008)], 32,
          'toon', colf=lambda s_, j, p: red if j < 2.5 else tint(red, -0.08))
    # 蜡泪：几道从口沿往下流
    for i in range(6):
        ang = 2 * math.pi * i / 6 + 0.4 * (i % 2)
        o = Vector((math.cos(ang), math.sin(ang), 0))
        ln = 0.02 + 0.03 * ((i * 37) % 5) / 5
        pts = [o * (rc * 0.95) + Vector((0, 0, zc1 + 0.001)), o * (rc + 0.002) + Vector((0, 0, zc1 - 0.006)),
               o * (rc + 0.0025) + Vector((0, 0, zc1 - ln * 0.6)), o * (rc + 0.002) + Vector((0, 0, zc1 - ln))]
        a.tube(pts, [0.004, 0.0042, 0.0035, 0.004], tint(red, 0.05), segs=6, mat='toon')
    # 烛芯、火苗（外焰橙、内焰黄白，挂在 glow 上）
    a.tube([(0, 0, zc1 - 0.008), (0.001, 0, zc1 + 0.012)], 0.0016, (0.12, 0.1, 0.09), segs=4)
    a.rev([(0.0, zc1 + 0.006), (0.006, zc1 + 0.012), (0.0105, zc1 + 0.024), (0.011, zc1 + 0.036), (0.008, zc1 + 0.052),
           (0.004, zc1 + 0.068), (0.0, zc1 + 0.08)], 12, 'glow', colf=lambda s, j, p: mix((1.0, 0.93, 0.62), (1.0, 0.55, 0.16), min(1.0, j / 6) ** 1.2),
          glow=1.0)
    return a.finish(dist=0.3, view=(20, 15, 0.95))


def _lotus_bloom(a, c, up, size, rng, open_=1.0):
    """一朵荷花（花觚里插的）：九片又宽又兜的花瓣（里面四片合着、外面五片张开，瓣根白、瓣尖粉，瓣上几道细筋），
    当中一个黄绿的莲蓬（顶上一圈莲子孔），莲蓬下一圈黄色的花蕊（细丝、顶上一点花药）"""
    up = Vector(up).normalized()
    side = up.cross(Vector((0.3, 1, 0)) if abs(up.y) < 0.9 else Vector((1, 0, 0))).normalized()
    fwd = up.cross(side).normalized()
    pink, pink_l, white = hexc('#ec7896'), hexc('#fbd2dc'), hexc('#fff4f0')
    for (n, L, W_, tilt, ph, c0, c1, r0, cup, curl) in ((4, 0.84, 0.56, 14 * open_ + 8, 0.0, pink_l, pink, 0.08, 0.5, -0.06),
                                                        (5, 1.0, 0.62, 44 * open_, 0.5, white, tint(pink, -0.02), 0.13, 0.42, 0.04)):
        for i in range(n):
            ang = 2 * math.pi * (i + ph) / n + rng.uniform(-0.05, 0.05)
            out = side * math.cos(ang) + fwd * math.sin(ang)
            tl = math.radians(tilt + rng.uniform(-3, 3))
            d = up * math.cos(tl) + out * math.sin(tl)
            petal(a, c + out * size * r0, d, out, size * L, size * W_, size * 0.04, 'toon:petal', c0, c1, None, cup=cup, curl=curl,
                  ridge=0.06, nu=6, nv=6, round_=0.55, bow=0.04)
    R = _rot_to(up)
    # 莲蓬：倒圆台，顶面平、边上一圈圆棱，顶上七个莲子孔（深色小凹点）
    pod = c + up * size * 0.08
    a.lathe([(0.0, 0.0), (size * 0.09, size * 0.01, hexc('#9fa84a')), (size * 0.19, size * 0.12, hexc('#c6c45e')), (size * 0.25, size * 0.2, hexc('#d8d470')),
             (size * 0.24, size * 0.225, hexc('#e3dc7c')), (size * 0.15, size * 0.232), (0.0, size * 0.234)], pod, segs=16, color=hexc('#d9d27a'), rot=R)
    for k in range(8):
        ang = 2 * math.pi * k / 7
        rr = size * 0.14 if k < 7 else 0.0
        p = pod + up * (size * 0.236) + (side * math.cos(ang) + fwd * math.sin(ang)) * rr
        a.blob(size * 0.026, p, (1, 1, 0.35), hexc('#6f6a2c'), subdiv=1, bump=0, rot=R)
    # 花蕊：一圈细丝，往外斜，顶上一点橙黄的花药
    for k in range(22):
        ang = 2 * math.pi * k / 22 + rng.uniform(-0.05, 0.05)
        o = side * math.cos(ang) + fwd * math.sin(ang)
        p0 = pod + up * size * 0.06 + o * size * 0.2
        p1 = p0 + up * size * rng.uniform(0.17, 0.22) + o * size * 0.1
        a.tube([p0, p1], [size * 0.008, size * 0.006], hexc('#f6dc72'), segs=3, cap=False)
        a.blob(size * 0.016, p1, (1, 1, 1.6), hexc('#f0a62c'), subdiv=1, bump=0, rot=R)


def _rot_to(up):
    q = Vector((0, 0, 1)).rotation_difference(Vector(up).normalized())
    return q.to_euler()


def _lotus_leaf(a, c, nrm, R, rng, curl=0.25):
    """一张荷叶：兜起来的一只浅碗（中间低、边缘翘起、一圈波浪），正中一点叶脐，叶脉从中间放射出去（颜色深一档），两面（反面浅）"""
    nrm = Vector(nrm).normalized()
    side = nrm.cross(Vector((0.2, 1, 0.1))).normalized()
    fwd = nrm.cross(side).normalized()
    g, gl, gd = hexc('#4f9a5c'), hexc('#86c272'), hexc('#2f6f45')
    ph = rng.uniform(0, 6.28)

    def P(s, t, off=0.0):
        ang = 2 * math.pi * s
        r = R * t
        z = R * (0.34 * t * t + 0.12 * t ** 4 * (0.6 + 0.4 * math.sin(3 * ang + ph))) + R * 0.05 * t ** 3 * math.sin(11 * ang + ph)
        return c + side * (r * math.cos(ang)) + fwd * (r * math.sin(ang)) + nrm * (z + off)

    def col(s, t, p):
        vein = abs(math.sin(math.pi * s * 18)) < 0.1
        if t < 0.1:
            return hexc('#c9d27a')
        return tint(g, -0.06) if vein else mix(g, gl, t ** 1.4)
    # 正反两面连成一个闭合的薄壳（u < 0.5 是正面、从叶心到叶缘；u > 0.5 是反面、从叶缘回到叶心），叶缘是同一圈点，不会从边上露出反面
    def Q(s, u):
        return P(s, 2 * u) if u <= 0.5 else P(s, 2 * (1 - u), -0.0025 * min(1.0, 2 * (1 - u) * 6))

    def qcol(s, u, p):
        return col(s, 2 * u, p) if u <= 0.5 else mix(gl, hexc('#a8d38c'), 2 * (1 - u))
    a.surf(Q, 40, 11, 'toon', colf=qcol, wrap=True, flip=True)


def flower_vase(name):
    """花觚（一对，五供最外两件）：铜胎掐丝珐琅（景泰蓝），喇叭口、鼓腹、外撇的足，腹和足上四道扉棱；
    插两朵荷花（九片宽瓣、黄莲蓬、一圈花蕊）、一个花苞、两张兜起来的荷叶，茎是圆的。原点在底面中心，瓶高 0.42，连花约 0.86"""
    a = PAsset(name)
    rng = a.rng
    B = 'bronze'
    tq, tq_d, tq_l = hexc('#2f86a6'), hexc('#1d5f7c'), hexc('#5cb0c8')
    gold, gold_d = GILT, GILT_D
    prof = [(0.0, 0.0), (0.072, 0.0), (0.075, 0.008), (0.07, 0.016), (0.06, 0.03), (0.05, 0.055), (0.044, 0.08), (0.046, 0.095),
            (0.054, 0.11), (0.062, 0.135), (0.064, 0.16), (0.06, 0.185), (0.05, 0.205), (0.04, 0.215), (0.034, 0.23),
            (0.033, 0.26), (0.038, 0.29), (0.048, 0.32), (0.062, 0.35), (0.077, 0.385), (0.087, 0.415), (0.09, 0.42), (0.086, 0.424),
            (0.08, 0.418), (0.07, 0.4), (0.0, 0.37)]
    # 珐琅的几段贴 paint_enamel（按圆柱展开：一圈 2 遍，竖着按真实长度），几道口沿、箍是鎏金的
    ENA = 'paint_enamel'
    gilt = {0, 1, 2, 7, 8, 12, 13, 20, 21, 22, 23, 24}
    n = len(prof) - 1
    tile = 0.2                                        # 一张贴图竖着对应 0.2 米

    def uv(s_, j, p, sc, jc):
        return (rep(s_, sc, 2), 0.5 + p.z / tile)
    k = 0
    while k < n:
        g = k in gilt
        k2 = k
        while k2 < n and (k2 in gilt) == g:
            k2 += 1
        seg = prof[k:k2 + 1]
        if g:
            a.rev(seg, 56, 'gold', colf=lambda s_, j, p: GILT if p.z > 0.01 else GILT_D)
        else:
            a.rev(seg, 56, ENA, uv=uv)
        k = k2
    # 口里面深一点
    # 扉棱：腹部、足部各四道，带缺口
    for i in range(4):
        ang = 2 * math.pi * i / 4 + math.pi / 4
        c_, s_ = math.cos(ang), math.sin(ang)
        for (z0, z1, r0, r1) in ((0.11, 0.2, 0.06, 0.06), (0.025, 0.085, 0.062, 0.045), (0.3, 0.38, 0.04, 0.072)):
            k = 5
            for q in range(k):
                z = z0 + (z1 - z0) * (q + 0.5) / k
                r = r0 + (r1 - r0) * (q + 0.5) / k + 0.006
                a.box((0.007, 0.022, (z1 - z0) / k * 0.82), (r * c_, r * s_, z - (z1 - z0) / k * 0.41), rot=(0, 0, ang), color=gold if q % 2 else gold_d,
                      bevel=0.002, mat='gold')
    # 荷花、花苞、荷叶、茎
    stem_c = hexc('#4c8a4a')
    top = Vector((0, 0, 0.4))
    blooms = [(Vector((0.03, -0.03, 0.69)), Vector((0.2, -0.45, 1)), 0.092, 1.0), (Vector((-0.08, 0.0, 0.6)), Vector((-0.55, -0.25, 1)), 0.08, 0.85)]
    for (c, up, sz, op) in blooms:
        a.tube([top + Vector((c.x * 0.2, c.y * 0.2, 0)), top + Vector((c.x * 0.6, c.y * 0.6, (c.z - 0.4) * 0.5)), c - Vector(up).normalized() * sz * 0.05],
               0.0048, stem_c, segs=8)
        _lotus_bloom(a, c, up, sz, rng, op)
    # 花苞
    bud = Vector((0.05, 0.04, 0.78))
    a.tube([top, top + Vector((0.02, 0.02, 0.2)), bud - Vector((0, 0, 0.01))], 0.0042, stem_c, segs=8)
    for i in range(5):
        ang = 2 * math.pi * i / 5
        out = Vector((math.cos(ang), math.sin(ang), 0))
        petal(a, bud + out * 0.004, Vector((0, 0, 1)) + out * 0.12, out, 0.075, 0.046, 0.005, 'toon:petal', hexc('#f6c3cf'), hexc('#d9587a'), None,
              cup=0.55, curl=-0.06, ridge=0.08, nu=6, nv=6, round_=0.6)
    # 荷叶
    for (c, nrm, R) in ((Vector((-0.08, -0.05, 0.5)), Vector((-0.5, -0.4, 1)), 0.075), (Vector((0.09, 0.05, 0.56)), Vector((0.5, 0.3, 1)), 0.065)):
        a.tube([top, top + (c - top) * 0.5 + Vector((0, 0, 0.03)), c - Vector(nrm).normalized() * 0.004], 0.0042, stem_c, segs=8)
        _lotus_leaf(a, c, nrm, R, rng)
    return a.finish(dist=0.35, view=(20, 12, 0.95), skip=('leaf', 'toon:petal'))


def fruit_plate(name):
    """果盘（两边供桌上，和 fruit_plate_peach 配一对）：白地青花的高足盘，堆着苹果、橘子，最上面一只苹果带叶。
    原点在底面中心，总高约 0.3"""
    a = PAsset(name)
    rng = a.rng
    z = _fruit_dish(a)

    def apple(c, r, hue):
        base = mix(hexc('#c9302c'), hexc('#e7b33c'), hue)
        a.rev(smooth_prof([(0.0, -0.9), (0.45, -0.95), (0.82, -0.72), (1.0, -0.25), (0.97, 0.3), (0.78, 0.72), (0.42, 0.9), (0.18, 0.76),
                           (0.0, 0.68)], 2), 20, 'toon', loc=c, scale=r,
              colf=lambda s_, j, p: mix(tint(base, -0.1), tint(base, 0.08), max(0.0, min(1.0, (p.z - c.z) / r * 0.6 + 0.5)))
              if not (math.sin(s_ * 50 + j) > 0.9 and j > 4) else tint(base, 0.14))
        a.tube([c + Vector((0, 0, r * 0.66)), c + Vector((0.003, 0, r * 0.9)), c + Vector((0.006, 0.002, r * 1.12))], [r * 0.06, r * 0.05, r * 0.04],
               (0.35, 0.22, 0.12), segs=5)

    def orange(c, r):
        o = hexc('#ef8a23')
        a.blob(r, c, (1, 1, 0.92), o, top=tint(o, 0.06), subdiv=2, bump=0.012, freq=26)
        a.blob(r * 0.13, c + Vector((0, 0, r * 0.9)), (1, 1, 0.4), hexc('#5d7a2f'), subdiv=1, bump=0)
    for i in range(6):
        ang = 2 * math.pi * i / 6
        c = Vector((0.085 * math.cos(ang), 0.085 * math.sin(ang), z + 0.036))
        (apple(c, 0.038, rng.uniform(0, 0.35)) if i % 2 == 0 else orange(c, 0.037))
    for i in range(3):
        ang = 2 * math.pi * i / 3 + 0.5
        c = Vector((0.04 * math.cos(ang), 0.04 * math.sin(ang), z + 0.096))
        (apple(c, 0.037, rng.uniform(0.1, 0.5)) if i % 2 == 0 else orange(c, 0.036))
    top = Vector((0, 0, z + 0.15))
    apple(top, 0.036, 0.05)
    lf = hexc('#4f8f3e')
    petal(a, top + Vector((0.006, 0.0, 0.04)), Vector((1, -0.3, 0.35)), Vector((0, 0, 1)), 0.05, 0.026, 0.002, 'toon', lf, tint(lf, 0.08), None,
          cup=0.2, curl=-0.1, ridge=0.3, nu=4, nv=4)
    return a.finish(dist=0.25, view=(20, 25, 0.9))


def oil_lamp(name):
    """长明灯：黄铜的莲花灯，圆足、细杆一颗宝珠节，杆头一朵仰莲托着油盏，盏里一根灯芯一朵小火苗（glow）。原点在底面中心，高约 0.3"""
    a = PAsset(name)
    B = 'bronze'
    br, bl, bd = BRASS, BRASS_L, BRASS_D
    prof = [(0.0, 0.0), (0.07, 0.0), (0.074, 0.006), (0.066, 0.014), (0.05, 0.022), (0.03, 0.035), (0.016, 0.05), (0.013, 0.1),
            (0.022, 0.112), (0.026, 0.12), (0.02, 0.128), (0.012, 0.135), (0.011, 0.18), (0.018, 0.19), (0.024, 0.196), (0.0, 0.198)]
    a.rev(prof, 36, B, colf=lambda s, j, p: bl if j in (2, 9, 14) else (bd if j in (5, 12) else br))
    for (n, r, z, L, tilt, ph) in ((8, 0.018, 0.192, 0.045, 52, 0.0), (8, 0.016, 0.196, 0.04, 30, 0.5)):
        for i in range(n):
            ang = 2 * math.pi * (i + ph) / n
            out = Vector((math.cos(ang), math.sin(ang), 0))
            tl = math.radians(tilt)
            petal(a, out * r + Vector((0, 0, z)), Vector((0, 0, 1)) * math.cos(tl) + out * math.sin(tl), out, L, 0.034, 0.005, B, br, bl,
                  rim=bl, cup=0.25, curl=0.12, ridge=0.4, nu=4, nv=4)
    # 油盏：一只小碗，碗里一层油（深琥珀色），灯芯、火苗
    a.rev([(0.0, 0.2), (0.02, 0.2), (0.032, 0.208), (0.04, 0.222), (0.041, 0.226), (0.037, 0.226), (0.03, 0.216), (0.0, 0.214)], 24, B,
          colf=lambda s, j, p: bl if j in (3, 4) else br)
    a.rev([(0.0355, 0.219), (0.0, 0.219)], 24, 'toon', color=hexc('#b5791f'))          # 油面（从外往里写：朝上）
    a.tube([(0, 0, 0.214), (0.001, 0, 0.232)], 0.0018, (0.15, 0.12, 0.1), segs=4)
    a.rev([(0.0, 0.228), (0.005, 0.233), (0.0085, 0.243), (0.0085, 0.252), (0.0055, 0.264), (0.0025, 0.276), (0.0, 0.284)], 10, 'glow',
          colf=lambda s, j, p: mix((1.0, 0.94, 0.66), (1.0, 0.56, 0.18), min(1.0, j / 6) ** 1.2), glow=1.0)
    return a.finish(dist=0.25, view=(20, 15, 0.95))




# ════════════════════ 佛坛（须弥座） ════════════════════

DAI = 'paint_dais'


def _kunmen(w, h, n=40):
    """壸门的轮廓（面板本地坐标：u 从 -w/2 到 w/2，v 从 0 到 h），逆时针：底边、右边、上面一串圆弧瓣、中间一个尖、左边"""
    w2 = w / 2
    h1 = h * 0.52
    pts = [(-w2, 0.0), (w2, 0.0), (w2, h1)]
    for i in range(1, n):
        x = w2 - w * i / n
        e = math.sqrt(max(0.0, 1 - (x / w2) ** 2))
        lobe = abs(math.sin(math.pi * 2.5 * (x / w2 + 1)))
        peak = max(0.0, 1 - abs(x) / (w * 0.07))
        y = h1 + (h * 0.86 - h1) * e ** 0.8 + h * 0.06 * lobe * e + h * 0.12 * peak ** 1.5
        pts.append((x, y))
    pts.append((-w2, h1))
    return pts


def altar_dais(name):
    """佛坛：清式须弥座，11.6 × 1.95，高 0.85（顶面 0.85）。从下往上：圭角（四角贴金云头）、下枋（彩画：绿地金卷草）、
    下枭（覆莲，青绿退晕描金）、皮条线、束腰（朱漆地上一排壸门：绿地卷草的门心、贴金的门框和门心里的火焰宝珠，门间一根根间柱）、
    上枭（仰莲，石青退晕描金）、上枋（彩画：青地缠枝莲）、台面（朱漆，金边）。
    原点在底面中心，正面朝 -y；摆在 (0, 0.72, 20.975)（世界 x -5.8..5.8、z 20.0..21.95，顶面世界高 1.57）。背面贴墙，背面不做雕饰"""
    a = PAsset(name)
    HX, HY = 5.8, 0.975
    LQ = 'lacquer'
    red, red_d, red_l = LAQ, tint(LAQ, -0.12), tint(LAQ, 0.08)
    upper = px(DAI, 0, 6, 1024, 250, inset=0)
    lower = px(DAI, 0, 262, 1024, 506, inset=0)
    rep_len = 0.46

    def band_uv(rect, z0, z1):
        def f(arc, j, p, sc, jc):
            return (arc / rep_len, rect[1] + (rect[3] - rect[1]) * max(0.0, min(1.0, (p.z - z0) / (z1 - z0))))
        return f
    STEP = 0.15
    # ── 圭角 ──
    rrect_sweep(a, HX, HY, 0.03, [(-0.06, 0.0), (0.0, 0.0), (0.0, 0.062), (-0.008, 0.074), (-0.04, 0.08)], LQ,
                colf=lambda j, p: red_d if j < 3 else red, step=STEP, cap_bottom=False)
    # ── 下枋：彩画 ──
    rrect_sweep(a, HX - 0.04, HY - 0.04, 0.02, [(-0.004, 0.08), (0.0, 0.084), (0.0, 0.186), (-0.004, 0.19)], DAI,
                uv=band_uv(lower, 0.084, 0.186), step=STEP)
    # ── 下枭（凹进去的一道，前面盖着覆莲） ──
    rrect_sweep(a, HX - 0.04, HY - 0.04, 0.02, [(-0.004, 0.19), (-0.03, 0.2), (-0.06, 0.25), (-0.065, 0.3)], LQ, color=red_d, step=STEP)
    # ── 皮条线、束腰（朱漆） ──
    rrect_sweep(a, HX - 0.1, HY - 0.1, 0.012, [(0.0, 0.3), (0.012, 0.302), (0.012, 0.312), (0.0, 0.314), (-0.04, 0.316), (-0.04, 0.554),
                                              (0.0, 0.556), (0.012, 0.558), (0.012, 0.568), (0.0, 0.57)], LQ,
                colf=lambda j, p: GILT if j in (1, 2, 7, 8) else red, step=STEP)
    # ── 上枭（凹，盖着仰莲） ──
    rrect_sweep(a, HX - 0.04, HY - 0.04, 0.02, [(-0.065, 0.57), (-0.06, 0.62), (-0.03, 0.67), (-0.004, 0.68)], LQ, color=red_d, step=STEP)
    # ── 上枋：彩画，上下各一道金线 ──
    rrect_sweep(a, HX - 0.04, HY - 0.04, 0.02, [(-0.004, 0.68), (0.0, 0.684), (0.0, 0.796), (-0.004, 0.8)], DAI,
                uv=band_uv(upper, 0.684, 0.796), step=STEP)
    for z in (0.686, 0.794):
        ring, _ = rrect_ring(HX - 0.04, HY - 0.04, 0.02, 0.5, 3)
        pts = [(p.x + q.x * 0.003, p.y + q.y * 0.003, z) for (p, q) in ring]
        a.tube(pts + [pts[0]], 0.004, GILT, segs=5, mat='gold', cap=False)
    # ── 台面：朱漆，冰盘沿，边上一道金线 ──
    # 台面分三圈接起来（同一套取样点，接缝上的点完全重合）：边上 6 厘米朱漆、6..17 厘米彩画带、里面一整块朱漆（不叠面）
    rrect_sweep(a, HX, HY, 0.03, [(-0.04, 0.8), (-0.004, 0.8), (0.0, 0.806), (0.002, 0.82), (0.0, 0.84), (-0.006, 0.85), (-0.03, 0.85),
                                  (-0.06, 0.85)], LQ, colf=lambda j, p: red_l if 2 <= j <= 4 else red, step=STEP)
    rrect_sweep(a, HX, HY, 0.03, [(-0.17, 0.85), (-0.17, 0.85)], LQ, step=STEP, cap_top=True, cap_color=red)
    ring, _ = rrect_ring(HX, HY, 0.03, 0.5, 3)
    pts = [(p.x + q.x * 0.0035, p.y + q.y * 0.0035, 0.82) for (p, q) in ring]
    a.tube(pts + [pts[0]], 0.0045, GILT, segs=5, mat='gold', cap=False)
    # 台面上离边 6..17 厘米一圈彩画带（和上枋同一条青地缠枝莲，平铺在台面上，外沿朝外看是正的），两边各一道描金线
    # （佛像、莲座压在中间；台面别的地方还是朱漆）
    zb_ = 0.85
    rrect_sweep(a, HX, HY, 0.03, [(-0.06, zb_), (-0.17, zb_)], DAI,
                uv=lambda arc, j, p, sc, jc: (arc / rep_len, upper[1] + (upper[3] - upper[1]) * min(1.0, max(0.0, j))), step=STEP)
    for off in (0.058, 0.172):
        ring, _ = rrect_ring(HX - off, HY - off, 0.0, 0.5, 1)
        pts = [(p.x, p.y, zb_ + 0.0004) for (p, q) in ring]
        a.tube(pts + [pts[0]], 0.0042, GILT, segs=4, mat='gold', cap=False, flat=0.45)

    # ── 仰覆莲：前面和两侧（背面贴墙不做）。宝装莲瓣：瓣面鼓起、中间一道脊、尖瓣尖，瓣心一片浅一档的小瓣，贴金描边（单独的 gold 部件）；
    # 青绿退晕：外圈深、中间浅、小瓣最浅。相邻两瓣瓣根之间留 2 毫米，瓣尖之间露出后面暗红的枭
    sides = [((-HX + 0.11, -HY), (HX - 0.11, -HY), (0, -1)), ((HX, -HY + 0.11), (HX, HY - 0.15), (1, 0)), ((-HX, HY - 0.15), (-HX, -HY + 0.11), (-1, 0))]
    for (p0, p1, nn) in sides:
        N_ = Vector((nn[0], nn[1], 0))
        P0, P1 = Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0))
        L = (P1 - P0).length
        k = max(1, int(round(L / 0.17)))
        Wp = L / k - 0.002
        for (z, sg, c0, c1) in ((0.302, -1, GREEN, GREEN_L), (0.568, 1, NAVY, NAVY_L)):
            tl = math.radians(20)
            d = Vector((0, 0, sg)) * math.cos(tl) + N_ * math.sin(tl)
            out = N_ * math.cos(tl) - Vector((0, 0, sg)) * math.sin(tl)
            for i in range(k):
                p = P0.lerp(P1, (i + 0.5) / k) - N_ * 0.098 + Vector((0, 0, z))
                bao_petal(a, p, d, out, 0.112, Wp, 0.013, 'toon', tint(c0, -0.04), mix(c0, c1, 0.5), tint(c1, 0.16), GILT, rim_mat='gold',
                          ts=[0.0, 0.1, 0.17, 0.27, 0.38, 0.5, 0.61, 0.71, 0.79, 0.88, 1.0], back=red_d if sg > 0 else None, base_w=0.62,
                          ridge=0.22)
                # （覆莲瓣尖朝下、往外翘，背面只有从底下往上看才看得见：不做背面，省面数）
    # ── 束腰上的壸门、间柱 ──
    zb, zt = 0.33, 0.54
    hh = zt - zb
    post = 0.1
    for (p0, p1, nn, npanel) in (((-HX + 0.1, -HY + 0.1), (HX - 0.1, -HY + 0.1), (0, -1), 12),
                                 ((HX - 0.1, -HY + 0.1), (HX - 0.1, HY - 0.1), (1, 0), 2),
                                 ((-HX + 0.1, HY - 0.1), (-HX + 0.1, -HY + 0.1), (-1, 0), 2)):
        P0, P1 = Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0))
        N_ = Vector((nn[0], nn[1], 0))
        U_ = (P1 - P0).normalized()
        L = (P1 - P0).length
        if nn[1] == 0:
            L -= 0.2          # 两侧：后面靠墙那头留一点
        w = (L - (npanel + 1) * post) / npanel
        face = 0.04            # 束腰面在边界往里 0.04（相对 HX-0.1）
        for i in range(npanel + 1):
            c = P0 + U_ * (post / 2 + i * (w + post)) - N_ * face
            # 两侧的那排：挨着前面的那根间柱和正面那排的最后一根是同一根，不要再做一遍（叠在一起会闪）
            corner_dup = (nn[0] > 0 and i == 0) or (nn[0] < 0 and i == npanel)
            # 间柱：朱漆，前面一道金线，上下两头小金托
            if not corner_dup:
                a.box((post * 0.62, 0.03, hh + 0.02), c + N_ * 0.012 + Vector((0, 0, zb - 0.01)), rot=(0, 0, math.atan2(U_.y, U_.x)), color=red_l,
                      bevel=0.006, mat=LQ)
                a.tube([c + N_ * 0.028 + Vector((0, 0, zb + 0.02)), c + N_ * 0.028 + Vector((0, 0, zt - 0.02))], 0.004, GILT, segs=5, mat='gold')
                for z in (zb + 0.004, zt - 0.004):
                    a.blob(0.02, c + N_ * 0.024 + Vector((0, 0, z)), (1.4, 0.7, 0.6), GILT, subdiv=2, bump=0, mat='gold',
                           rot=(0, 0, math.atan2(U_.y, U_.x)))
            if i == npanel:
                break
            cc = P0 + U_ * (post + i * (w + post) + w / 2) - N_ * face
            o = cc + N_ * 0.004 + Vector((0, 0, zb))
            outline = _kunmen(w - 0.04, hh - 0.012, 30)
            # 门心：绿地金卷草（彩画贴图），按真实尺寸铺
            t_ = new_bm()
            uvl = t_.loops.layers.uv['uv']
            col = t_.loops.layers.float_color['col']
            vs = [t_.verts.new(o + U_ * u + Vector((0, 0, v))) for (u, v) in outline]
            f = t_.faces.new(vs)
            for l in f.loops:
                q = l.vert.co - o
                u_, v_ = q.dot(U_), q.z
                l[uvl].uv = ((u_ + 7.0) / rep_len, lower[1] + (lower[3] - lower[1]) * (0.08 + 0.84 * v_ / (hh - 0.012)))
                l[col] = (1.0, 1.0, 1.0, 0.0)
            bmesh.ops.recalc_face_normals(t_, faces=t_.faces)
            if f.normal.dot(N_) < 0:
                bmesh.ops.reverse_faces(t_, faces=[f])
            a.merge(t_, DAI)
            # 贴金的门框（一道圆的阳线，沿壸门的轮廓）
            pts = [o + N_ * 0.004 + U_ * u + Vector((0, 0, v)) for (u, v) in outline]
            a.tube(pts + [pts[0]], 0.0065, GILT, segs=5, mat='gold', cap=False)
            # 门心正中：莲座上一颗火焰宝珠，两边一对卷云
            fr = (o + N_ * 0.006, U_, Vector((0, 0, 1)), N_)
            jc = o + N_ * 0.02 + Vector((0, 0, hh * 0.42))
            a.blob(0.026, jc, (1, 0.7, 1.15), GILT, subdiv=2, bump=0, mat='gold')
            for k in range(5):
                ang = math.radians(-60 + 30 * k)
                d = U_ * math.sin(ang) + Vector((0, 0, math.cos(ang)))
                a.tube([jc + d * 0.024, jc + d * 0.045 + N_ * -0.006, jc + d * 0.06 + U_ * 0.008 * math.sin(ang * 3)], [0.006, 0.004, 0.0015], GILT,
                       segs=4, mat='gold')
            for k in range(5):
                ang = math.radians(-50 + 25 * k)
                d = U_ * math.sin(ang) + Vector((0, 0, -0.3))
                petal(a, jc + Vector((0, 0, -0.02)) + U_ * (0.012 * math.sin(ang)), U_ * math.sin(ang) * 0.9 + Vector((0, 0, -0.35)), N_,
                      0.04, 0.026, 0.008, 'gold', GILT, tint(GILT, 0.08), None, cup=0.1, curl=0.1, ridge=0.4, nu=3, nv=3)
            for sg in ((-1, 1) if nn[1] != 0 else ()):          # 两侧面的门心只留宝珠（侧面看得少，省面数）
                cloud_scroll(a, fr, sg * w * 0.27, hh * 0.36, 0.06, GILT, flip=sg, r=0.0045)
    # ── 圭角：四个角上贴金的大卷云（正面和侧面各一个） ──
    for sx in (-1, 1):
        for (N_, U_, o) in ((Vector((0, -1, 0)), Vector((1, 0, 0)), Vector((sx * (HX - 0.16), -HY, 0.0))),
                            (Vector((sx, 0, 0)), Vector((0, sx, 0)), Vector((sx * HX, -HY + 0.16, 0.0)))):
            fr = (o + N_ * 0.001, U_, Vector((0, 0, 1)), N_)
            relief(a, scroll2d((0.0, 0.034), 0.024, 1.15, math.pi * 0.5, sx, 20), fr, 0.005, GILT)
            relief(a, [(-0.1 * sx, 0.012), (-0.05 * sx, 0.014), (-0.01 * sx, 0.024)], fr, 0.0045, GILT)
    # 正面圭角正中：一朵卷云
    cloud_scroll(a, (Vector((0, -HY - 0.001, 0.0)), Vector((1, 0, 0)), Vector((0, 0, 1)), Vector((0, -1, 0))), 0.0, 0.042, 0.05, GILT, r=0.005)
    return a.finish(dist=0.9, view=(20, 18, 0.55))



# ════════════════════ 宫灯、幡 ════════════════════

def palace_lantern(name):
    """宫灯：六角，紫檀色的木框、贴金的线脚；六面灯片（绢画：莲花、梅枝小鸟、红团「福」字），贴 paint_lantern（真贴图，不是顶点色）；
    顶上一圈宝盖、六只龙头挑出来各挂一小串红穗；底下（从下往上看的那一面）：六角的托盘（斜底、贴金的边线），
    一圈贴金的联珠，正中垂下一朵鎏金的倒挂莲苞（两层莲瓣包着一颗宝珠），六个角上各一个车出来的鎏金垂头（圈、颈、四瓣的莲苞、尖），
    垂头下挂红穗；正中一大串红穗。原点在顶上的挂点（吊在天花下），往下总长约 2.3。
    灯片：部件 paint_lantern，Unity 材质 toon_paint_lantern 夜里要整片发光（见交接说明）"""
    a = PAsset(name)
    WD, WDL = hexc('#4a2a1f'), hexc('#6e4030')
    WM = 'wood_dark'
    LAN = 'paint_lantern'
    R = 0.25
    zt, zb = -1.12, -1.6

    def hexp(r, k, z):
        ang = math.pi / 6 + k * math.pi / 3
        return Vector((r * math.cos(ang), r * math.sin(ang), z))
    # ── 挂钩、吊绳（两股拧在一起的红绳），中间一个金色的结 ──
    a.rev([(0.0, -0.005), (0.02, -0.008), (0.026, -0.02), (0.02, -0.03), (0.008, -0.034), (0.0, -0.034)], 12, 'gold', color=GILT)
    for k in range(2):
        pts = [Vector((0.007 * math.cos(z * 18 + k * math.pi), 0.007 * math.sin(z * 18 + k * math.pi), z)) for z in [-0.03 - 0.92 * q / 28 for q in range(29)]]
        a.tube(pts, 0.0065, RED if k else RED_D, segs=5)
    a.blob(0.03, (0, 0, -0.5), (1, 1, 1.3), GILT, subdiv=2, bump=0.05, freq=20, mat='gold')
    for sg in (-1, 1):
        a.tube([(0, 0, -0.5), (sg * 0.03, 0, -0.53), (sg * 0.04, 0, -0.6)], [0.006, 0.005, 0.003], RED, segs=5)
    # ── 宝盖：顶盘、六角的小屋顶、一圈贴金的楣子 ──
    a.rev([(0.0, -0.95), (0.05, -0.95), (0.06, -0.96), (0.055, -0.975), (0.0, -0.975)], 18, 'gold', color=GILT)
    roof = [(0.0, -1.062), (0.27, -1.062), (0.3, -1.062), (0.32, -1.055), (0.31, -1.045), (0.22, -1.02), (0.12, -0.985), (0.06, -0.975), (0.0, -0.975)]
    a.rev(roof, 6, WM, colf=lambda s_, j, p: GILT if 2.5 < j < 4.5 else WD)
    for k in range(6):
        p0, p1 = hexp(0.27, k, -1.062), hexp(0.27, k + 1, -1.062)
        mid_ = (p0 + p1) / 2
        N_ = Vector((mid_.x, mid_.y, 0)).normalized()
        U_ = (p1 - p0).normalized()
        a.box((0.27, 0.02, 0.06), mid_ + Vector((0, 0, -0.06)), rot=(0, 0, math.atan2(U_.y, U_.x)), color=WD, bevel=0.004, mat=WM)
        fr = (mid_ + N_ * 0.0105 + Vector((0, 0, -0.03)), U_, Vector((0, 0, 1)), N_)
        cloud_scroll(a, fr, 0.0, 0.0, 0.03, GILT, r=0.0028)
        for sg in (-1, 1):
            relief(a, scroll2d((sg * 0.085, 0.0), 0.014, 1.0, math.pi * (0 if sg > 0 else 1), sg, 12), fr, 0.0025, GILT)
        # 龙头挑杆：从宝盖的角上挑出去、往上翘，龙头嘴里挂一串小红穗
        c0 = hexp(0.3, k, -1.05)
        out = Vector((c0.x, c0.y, 0)).normalized()
        arm = [c0, c0 + out * 0.035 + Vector((0, 0, 0.004)), c0 + out * 0.065 + Vector((0, 0, 0.018)), c0 + out * 0.085 + Vector((0, 0, 0.036))]
        a.tube(arm, [0.017, 0.015, 0.013, 0.012], GILT, segs=8, mat='gold')
        # 龙头：额头、长吻、张开的下颌、两只眼、两只角、颈后一撮鬃
        hd = arm[-1] + out * 0.018 + Vector((0, 0, 0.008))
        ro = (0, 0, math.atan2(out.y, out.x))
        a.blob(0.021, hd, (1.25, 0.95, 0.95), GILT, subdiv=2, bump=0.0, mat='gold', rot=ro)
        a.blob(0.014, hd + out * 0.026 + Vector((0, 0, 0.002)), (1.5, 0.75, 0.62), GILT, subdiv=2, bump=0, mat='gold', rot=ro)
        a.blob(0.01, hd + out * 0.022 - Vector((0, 0, 0.014)), (1.6, 0.7, 0.45), GILT_D, subdiv=1, bump=0, mat='gold', rot=ro)
        sd0 = out.cross(Vector((0, 0, 1)))
        for sg in (-1, 1):
            a.blob(0.0055, hd + out * 0.012 + sd0 * sg * 0.014 + Vector((0, 0, 0.008)), (1, 1, 1), hexc('#2a1a12'), subdiv=1, bump=0)
        for q in range(4):
            a.tube([hd - out * (0.012 + 0.006 * q) + Vector((0, 0, 0.012)), hd - out * (0.03 + 0.008 * q) + Vector((0, 0, 0.026 - 0.004 * q))],
                   [0.004, 0.001], GILT_D, segs=3, mat='gold')
        for sg in (-1, 1):
            a.tube([hd + sd0 * sg * 0.008 + Vector((0, 0, 0.012)), hd + sd0 * sg * 0.014 - out * 0.02 + Vector((0, 0, 0.04))], [0.004, 0.0015], GILT,
                   segs=4, mat='gold')
        tp = hd + out * 0.032 - Vector((0, 0, 0.018))
        a.tube([tp, tp - Vector((0, 0, 0.06))], 0.0025, RED, segs=4)
        a.blob(0.012, tp - Vector((0, 0, 0.07)), (1, 1, 1.2), GILT, subdiv=1, bump=0, mat='gold')
        for q in range(5):
            ang = 2 * math.pi * q / 5
            d = Vector((math.cos(ang), math.sin(ang), 0)) * 0.0075
            a.tube([tp - Vector((0, 0, 0.08)) + d, tp - Vector((0, 0, 0.27)) + d * 1.8], [0.0022, 0.0016], vary(RED, a.rng, 0.04), segs=3, cap=False,
                   mat='toon', sway=(0.0, 0.2))
    # ── 灯身：六根立柱、上下两道横枋、灯片 ──
    for k in range(6):
        c = hexp(R, k, 0)
        sq_path(a, [Vector((c.x, c.y, zt + 0.02)), Vector((c.x, c.y, zb - 0.03))], 0.03, WD, WM, ref=Vector((c.x, c.y, 0)))
        for z in (zt + 0.03, zb - 0.035):
            a.blob(0.02, Vector((c.x, c.y, z)), (1, 1, 0.7), GILT, subdiv=1, bump=0, mat='gold')
        p0, p1 = hexp(R, k, 0), hexp(R, k + 1, 0)
        mid_ = (p0 + p1) / 2
        U_ = (p1 - p0).normalized()
        N_ = Vector((mid_.x, mid_.y, 0)).normalized()
        rot = (0, 0, math.atan2(U_.y, U_.x))
        for (z, h) in ((zt - 0.005, 0.03), (zb - 0.028, 0.03)):
            a.box((R - 0.02, 0.028, h), mid_ + Vector((0, 0, z)), rot=rot, color=WD, bevel=0.004, mat=WM)
            a.tube([p0 * 0.92 + N_ * 0.012 + Vector((0, 0, z + h / 2)), p1 * 0.92 + N_ * 0.012 + Vector((0, 0, z + h / 2))], 0.0035, GILT, segs=4,
                   mat='gold')
    # 灯片：每面一块（2×3 格，绢面微微往外鼓一点），贴 paint_lantern 的第 k 张（256×576，比例和灯片一样）
    for k in range(6):
        p0, p1 = hexp(R * 0.965, k, 0), hexp(R * 0.965, k + 1, 0)
        q0, q1 = p0.lerp(p1, 0.06), p0.lerp(p1, 0.94)
        N_ = Vector(((q0 + q1).x, (q0 + q1).y, 0)).normalized()
        rect = (k * 256 / 1536 + 1.5 / 1536, 1.5 / 576, (k + 1) * 256 / 1536 - 1.5 / 1536, 1 - 1.5 / 576)

        def Pp(s_, t_, q0=q0, q1=q1, N_=N_):
            return q0.lerp(q1, s_) + Vector((0, 0, zb + (zt - zb) * t_)) + N_ * (0.004 * math.sin(math.pi * s_) * math.sin(math.pi * t_))
        a.surf(Pp, 2, 3, LAN, lambda s_, t_, p, sc, tc, rect=rect: in_rect(rect, s_, t_), weld=False)
        # 灯片四周一圈细金框
        a.tube([q0 + Vector((0, 0, zb + 0.008)), q1 + Vector((0, 0, zb + 0.008)), q1 + Vector((0, 0, zt - 0.008)), q0 + Vector((0, 0, zt - 0.008)),
                q0 + Vector((0, 0, zb + 0.008))], 0.003, GILT, segs=4, mat='gold', cap=False)
    # ── 底：六角托盘（斜底）、边上一道贴金线脚 ──
    tray = [(0.0, zb - 0.078), (0.15, zb - 0.078), (0.2, zb - 0.066), (0.262, zb - 0.052), (0.288, zb - 0.044), (0.292, zb - 0.036),
            (0.286, zb - 0.03), (0.0, zb - 0.03)]
    a.rev(tray, 6, WM, colf=lambda s_, j, p: GILT if 3.5 < j < 5.5 else (WDL if j < 1.5 else WD))
    # 托盘底面一圈贴金的联珠
    for q in range(24):
        ang = 2 * math.pi * q / 24
        a.lathe([(0.0, -0.006), (0.006, -0.004), (0.0075, 0.0), (0.006, 0.004), (0.0, 0.006)], (0.165 * math.cos(ang), 0.165 * math.sin(ang), zb - 0.079),
                segs=6, color=GILT, mat='gold')
    a.tube([(0.135 * math.cos(2 * math.pi * q / 48), 0.135 * math.sin(2 * math.pi * q / 48), zb - 0.0785) for q in range(49)], 0.0035, GILT_D,
           segs=4, mat='gold', cap=False)
    # 正中倒挂的莲苞：上面一圈大瓣、下面一圈小瓣（瓣尖往里收），包着一颗宝珠
    for (n_, rr, z, L, W_, tl, ph, c0) in ((12, 0.07, zb - 0.078, 0.1, 0.06, 32, 0.0, GILT), (8, 0.045, zb - 0.13, 0.07, 0.048, 18, 0.5, tint(GILT, 0.05))):
        for i in range(n_):
            ang = 2 * math.pi * (i + ph) / n_
            o = Vector((math.cos(ang), math.sin(ang), 0))
            d = o * math.sin(math.radians(tl)) - Vector((0, 0, math.cos(math.radians(tl))))
            nrm = o - d * o.dot(d)
            petal(a, o * rr + Vector((0, 0, z)), d, nrm, L, W_, 0.008, 'gold', c0, tint(GILT, 0.1), GILT_D, cup=0.18, curl=-0.2, ridge=0.25,
                  nu=5, nv=4, round_=1.0, rim_w=0.84)
    a.rev([(0.0, zb - 0.235), (0.02, zb - 0.228), (0.03, zb - 0.21), (0.028, zb - 0.19), (0.016, zb - 0.175), (0.0, zb - 0.17)], 16, 'gold', color=GILT)
    # 六个角上的垂头（车出来的：一道圈、细颈、四瓣的莲苞、尖），垂头下挂红穗
    for k in range(6):
        c = hexp(0.27, k, zb - 0.047)                 # 顶上一点插进托盘里
        bud = [(0.0, -0.0), (0.016, -0.002), (0.018, -0.008), (0.012, -0.013), (0.008, -0.018), (0.016, -0.03), (0.02, -0.042), (0.016, -0.056),
               (0.008, -0.068), (0.0, -0.076)]
        a.rev([(r, c.z + z) for (r, z) in bud], 10, 'gold', loc=(c.x, c.y, 0), colf=lambda s_, j, p: GILT_D if j in (3, 4) else GILT,
              wobble=lambda ang, j: 1.0 - (0.18 * abs(math.sin(2 * ang)) ** 0.5 if 5 <= j <= 8 else 0.0))
        tip = c + Vector((0, 0, -0.076))
        a.tube([tip, tip - Vector((0, 0, 0.05))], 0.003, RED, segs=4)
        a.blob(0.009, tip - Vector((0, 0, 0.055)), (1, 1, 1.2), GILT, subdiv=1, bump=0, mat='gold')
        for q in range(5):
            ang = 2 * math.pi * q / 5
            d = Vector((math.cos(ang), math.sin(ang), 0)) * 0.0072
            a.tube([tip - Vector((0, 0, 0.062)) + d, tip - Vector((0, 0, 0.2)) + d * 1.6], [0.002, 0.0015], vary(RED, a.rng, 0.04), segs=3, cap=False,
                   sway=(0.0, 0.2))
    # 大穗：金色的结、一圈红丝穗
    kz = zb - 0.27
    a.blob(0.03, (0, 0, kz), (1, 1, 1.25), GILT, subdiv=2, bump=0.06, freq=24, mat='gold')
    a.tube([(0, 0, zb - 0.235), (0, 0, kz)], 0.004, RED, segs=4)
    a.rev([(0.0, kz - 0.03), (0.035, kz - 0.045), (0.04, kz - 0.07), (0.0, kz - 0.072)], 12, 'gold', color=GILT_D)
    rng = a.rng
    for q in range(24):
        ang = 2 * math.pi * q / 24
        r0 = 0.03 + 0.009 * (q % 2)
        d = Vector((math.cos(ang), math.sin(ang), 0))
        ln = 0.4 + rng.uniform(-0.03, 0.03)
        a.tube([d * r0 + Vector((0, 0, kz - 0.06)), d * (r0 + 0.012) + Vector((0, 0, kz - 0.06 - ln * 0.5)), d * (r0 + 0.02) + Vector((0, 0, kz - 0.06 - ln))],
               [0.0023, 0.002, 0.0016], vary(RED, rng, 0.05, 0.03), segs=3, cap=False, sway=(0.0, 0.25))
    return a.finish(dist=0.4, view=(20, 10, 0.8), floor=False, skip=('leaf', 'glow'))


BAN = 'paint_banner'


def _banner(name, col, border_col):
    """幡：一条从天花板垂下来的长条丝幡（宽 0.5、长 2.33），三角形的幡头、四个字的幡身、幡尾三个垂角，
    幡头两角垂下两条长飘带；正反两面都绣着（背面的字也是正的）。原点在挂点，往下总长约 2.75；下半截轻轻摆（顶点色第四个数：
    幡身 0.02 → 0.13，飘带最多 0.15——殿里是关着的，别像树叶那样晃）。
    col：paint_banner 里第几面（0 红「佛日增辉」、1 红「法轮常转」、2 黄「风调雨顺」、3 黄「国泰民安」）"""
    a = PAsset(name)
    TW, TH = 2048, 2048
    X0 = 440 * col
    W, L = 0.5, 2.33
    k = L / 2048                         # 每像素多少米（竖着）
    z_head = -0.16                       # 幡头尖
    z_hb = z_head - 360 * k              # 幡头底（幡身顶）
    z_body = z_head - 1800 * k
    z_end = z_head - 2048 * k

    def U(x):
        return (X0 + x) / TW

    def V(y):
        return 1 - y / TH

    def sway_at(z):
        # 殿里没风：只是轻轻地飘（最下面 0.13）
        return 0.02 + 0.11 * max(0.0, min(1.0, (z_head - z) / L)) ** 1.5

    def wave(x, z):
        t = max(0.0, (z_hb - z) / (L * 0.8))
        return 0.014 * math.sin(2 * math.pi * (x / W * 1.3 + t * 0.9)) * min(1.0, t * 2) + 0.01 * t * t

    def make(front=True):
        sgn = 1 if front else -1
        off = 0.0 if front else 0.002
        # 正面朝 -y。背面：贴图左右翻过来（背面看字也是正的）
        def P_body(s, t):
            x = -W / 2 + W * s
            z = z_body + (z_hb - z_body) * t
            return Vector((x, wave(x, z) + off, z))

        def uv_body(s, t, p, sc, tc):
            ss = s if front else 1 - s
            return (U(2 + 436 * ss), V(1800 - 1440 * t))
        a.surf(P_body, 6, 26, BAN, uv_body, sway=lambda s, t, p: sway_at(p.z), flip=not front, weld=False)

        def P_head(s, t):
            # 梯形 → 三角形：t=1 是幡头尖
            x = (-W / 2 - 0.004 + (W + 0.008) * s) * (1 - t)
            z = z_hb + (z_head - z_hb) * t
            return Vector((x, wave(x, z) + off, z))

        def uv_head(s, t, p, sc, tc):
            ss = s if front else 1 - s
            return (U(220 + (ss - 0.5) * 440 * (1 - t) * 0.985), V(354 - 346 * t))
        a.surf(P_head, 6, 6, BAN, uv_head, sway=lambda s, t, p: sway_at(p.z), flip=not front, weld=True)

        # 幡尾：下沿按三个如意垂角的尖剪成锯齿
        tips = [(0.0, 2000), (1 / 6, 2016), (2 / 6, 1950), (0.5, 2016), (4 / 6, 1950), (5 / 6, 2016), (1.0, 2000)]

        def edge_y(s):
            for i in range(len(tips) - 1):
                if tips[i][0] <= s <= tips[i + 1][0]:
                    f = (s - tips[i][0]) / (tips[i + 1][0] - tips[i][0])
                    return tips[i][1] + (tips[i + 1][1] - tips[i][1]) * f
            return 2000

        def P_tail(s, t):
            x = -W / 2 + W * s
            yb = edge_y(s)
            y = yb + (1800 - yb) * t
            z = z_head - y * k
            return Vector((x, wave(x, z) + off, z))

        def uv_tail(s, t, p, sc, tc):
            ss = s if front else 1 - s
            yb = edge_y(s)
            return (U(2 + 436 * ss), V(yb + (1800 - yb) * t))
        a.surf(P_tail, 12, 3, BAN, uv_tail, sway=lambda s, t, p: sway_at(p.z), flip=not front, weld=False)
    make(True)
    make(False)
    # 幡头底下一根贴金的细杆（撑着幡身），两头小宝珠
    a.tube([(-W / 2 - 0.035, 0.001, z_hb + 0.004), (W / 2 + 0.035, 0.001, z_hb + 0.004)], 0.007, GILT, segs=8, mat='gold')
    for sx in (-1, 1):
        a.blob(0.014, (sx * (W / 2 + 0.042), 0.001, z_hb + 0.004), (1, 1, 1.2), GILT, subdiv=2, bump=0, mat='gold')
    # 挂绳、挂钩
    a.rev([(0.0, -0.005), (0.018, -0.008), (0.022, -0.02), (0.016, -0.028), (0.0, -0.028)], 10, 'gold', color=GILT)
    a.tube([(0, 0.001, -0.025), (0, 0.001, z_head + 0.01)], 0.005, RED, segs=5)
    a.blob(0.012, (0, 0.001, z_head + 0.004), (1, 1, 1), GILT, subdiv=1, bump=0, mat='gold')
    # 两条飘带：从幡头两角垂下，比幡身长，下半截 S 形飘着
    sx_ = 1760 + 72 * (0 if col < 2 else 1)            # 飘带：红幡用红带、黄幡用黄带
    for sx in (-1, 1):
        x0 = sx * (W / 2 + 0.05)
        top = z_hb - 0.01
        Ls = top - (z_end - 0.3)

        def P(s, t, x0=x0, sx=sx):
            z = top - Ls * (1 - t)
            d = 1 - t
            x = x0 + sx * 0.03 * d + 0.025 * math.sin(d * 7 + sx) * d
            y = 0.02 * math.sin(d * 5 + sx * 0.7) * d
            return Vector((x - 0.035 + 0.07 * s, y, z))
        for front in (True, False):
            a.surf(lambda s, t, P=P, front=front: P(s, t) + Vector((0, 0.0 if front else 0.002, 0)), 2, 30, BAN,
                   lambda s, t, p, sc, tc, front=front: ((sx_ + 4 + 64 * (s if front else 1 - s)) / TW, V(2040 - 2030 * t)),
                   sway=lambda s, t, p: 0.03 + 0.12 * (1 - t) ** 1.3, flip=not front, weld=False)
        a.blob(0.012, (x0, 0.001, top + 0.004), (1, 1, 1), GILT, subdiv=1, bump=0, mat='gold')
    return a.finish(dist=0.4, view=(25, 5, 0.75), floor=False)


def banner(name):
    """红幡「佛日增辉」（下联：辉是平声，挂西边——面朝佛坛时的左手）"""
    return _banner(name, 0, YEL)


def banner_b(name):
    """红幡「法轮常转」（上联：转是仄声，挂东边——面朝佛坛时的右手）"""
    return _banner(name, 1, YEL)


def banner_gold(name):
    """黄幡「风调雨顺」（上联，东）"""
    return _banner(name, 2, RED)


def banner_gold_b(name):
    """黄幡「国泰民安」（下联，西）"""
    return _banner(name, 3, RED)



# ════════════════════ 磬、木鱼、经案、功德箱 ════════════════════

def _stand(a, W, D, H, top_color=None, legs=True, ins=0.035, ls=0.05):
    """小供台（放磬、木鱼）：朱漆，冰盘沿的台面、束腰、壸门牙条（贴金卷云）、四条马蹄腿、托泥。台面高 H"""
    hx, hy = W / 2, D / 2
    LQ = 'lacquer'
    lq, lq_l, lq_d = LAQ, tint(LAQ, 0.07), tint(LAQ, -0.12)
    prof = [(-0.04, H - 0.035), (-0.003, H - 0.035), (0.0, H - 0.031), (0.0, H - 0.02), (0.003, H - 0.012), (0.0, H - 0.003), (-0.004, H)]
    rrect_sweep(a, hx, hy, 0.015, prof, LQ, colf=lambda j, p: lq_l if 2 <= j <= 4 else lq, cap_bottom=True, cap_top=True,
                cap_color=top_color or lq, step=0.1)
    wz0, wz1 = H - 0.06, H - 0.035
    rrect_sweep(a, hx - 0.02, hy - 0.02, 0.008, [(-0.006, wz0 - 0.002), (0.0, wz0), (0.0, wz1), (-0.006, wz1 + 0.002)], LQ, color=lq_d, step=0.2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            lx, ly = sx * (hx - ins), sy * (hy - ins)
            din = Vector((-sx, -sy, 0)).normalized()
            base = Vector((lx, ly, 0))
            path = [base + Vector((0, 0, wz1)), base + Vector((0, 0, H * 0.5)), base + Vector((0, 0, 0.12)),
                    base + din * 0.005 + Vector((0, 0, 0.08)), base + din * 0.014 + Vector((0, 0, 0.055)), base + din * 0.022 + Vector((0, 0, 0.04))]
            sq_path(a, path, [ls, ls * 0.95, ls * 0.88, ls * 0.95, ls * 1.05, ls], lq, LQ, colors=[lq, lq, lq, lq_d, lq_d, lq_d])
    edge = [(u, dz * 0.75) for (u, dz) in _apron_edge(2)]
    for (L, cen, N_, U_) in ((W - 2 * ins - ls, Vector((0, -(hy - ins + ls / 2 - 0.003), 0)), Vector((0, -1, 0)), Vector((1, 0, 0))),
                             (W - 2 * ins - ls, Vector((0, hy - ins + ls / 2 - 0.003, 0)), Vector((0, 1, 0)), Vector((-1, 0, 0))),
                             (D - 2 * ins - ls, Vector((hx - ins + ls / 2 - 0.003, 0, 0)), Vector((1, 0, 0)), Vector((0, 1, 0))),
                             (D - 2 * ins - ls, Vector((-(hx - ins + ls / 2 - 0.003), 0, 0)), Vector((-1, 0, 0)), Vector((0, -1, 0)))):
        poly = [(-L / 2 + u * L, -dz) for (u, dz) in edge]
        poly = [(L / 2 + 0.002, 0.0), (-L / 2 - 0.002, 0.0), (-L / 2 - 0.002, poly[0][1])] + poly[1:-1] + [(L / 2 + 0.002, poly[-1][1])]
        o = cen + Vector((0, 0, wz0))
        plate(a, poly, (o, U_, Vector((0, 0, 1)), N_), 0.016, lq, LQ, bevel=0.002)
        cloud_scroll(a, (o + N_ * 0.0005, U_, Vector((0, 0, 1)), N_), 0.0, -0.03, 0.032, GILT, r=0.0032)
    tx, ty = hx - ins + ls * 0.25, hy - ins + ls * 0.25
    rrect_sweep(a, tx, ty, 0.01, [(-0.05, 0.016), (-0.003, 0.016), (0.0, 0.02), (0.0, 0.04), (-0.003, 0.044), (-0.05, 0.044), (-0.05, 0.016)], LQ,
                colf=lambda j, p: lq_l if j == 3 else lq_d, step=0.2, ncorner=3)
    for sx in (-1, 1):
        for sy in (-1, 1):
            a.lathe([(0.0, 0.0), (0.024, 0.0, lq_d), (0.028, 0.009, lq), (0.024, 0.016), (0.0, 0.016)], (sx * (tx - 0.025), sy * (ty - 0.025), 0), segs=10,
                    color=lq_d, mat=LQ)


def _ring_cushion(a, r, h, z, hole=0.0):
    """圆的织锦小垫（磬垫、木鱼垫）：侧面红锦金卷草，顶面黄锦莲花"""
    rect_side = px(BRO, 512, 516, 1024, 636, inset=6)
    prof = [(0.0, z), (r * 0.94, z), (r * 0.99, z + h * 0.12), (r * 1.01, z + h * 0.45), (r * 0.99, z + h * 0.8), (r * 0.93, z + h * 0.97),
            (r * 0.8, z + h), (r * 0.5, z + h * 1.02), (0.0, z + h * 1.03)]

    def uv(s, j, p, sc, jc):
        if jc < 1:
            return (4 / 1024, 1 - 4 / 1024)
        if jc < 5:
            return in_rect(rect_side, rep(s, sc, 3), max(0.0, min(1.0, (p.z - z) / h)))
        return ((256 + p.x / r * 236) / 1024, 1 - (768 - p.y / r * 236) / 1024)
    a.rev(prof, 48, BRO, uv=uv)
    rope_loop(a, lambda ang: r * 0.955, z + h * 0.95, 0.0055, 48)


def qing(name):
    """磬：铜磬（大钵形，口沿厚、腹上两道弦纹、一圈阴刻的经文带）坐在织锦的磬垫上，放在一张朱漆小供台上；
    台面上横放一根磬槌（木柄、红布包头）。原点在地面中心，总高约 0.76；磬口正中（敲的地方）高约 0.74"""
    a = PAsset(name)
    H = 0.5
    _stand(a, 0.48, 0.48, H)
    _ring_cushion(a, 0.17, 0.06, H, 0)
    B = 'bronze'
    z0 = H + 0.055
    prof = [(0.0, z0), (0.06, z0 + 0.002), (0.11, z0 + 0.018), (0.155, z0 + 0.05), (0.18, z0 + 0.09), (0.19, z0 + 0.13), (0.188, z0 + 0.16),
            (0.183, z0 + 0.178), (0.184, z0 + 0.186), (0.181, z0 + 0.19), (0.17, z0 + 0.19), (0.168, z0 + 0.18), (0.172, z0 + 0.15),
            (0.165, z0 + 0.1), (0.13, z0 + 0.045), (0.07, z0 + 0.024), (0.0, z0 + 0.02)]

    def col(s, j, p):
        k = 0.05 * noise.noise(p * 30)
        if j in (7, 8, 9):
            return tint(BZ_L, k)
        if 4 <= j <= 6:
            # 经文带：一格一格的小凹点（阴刻的字），暗一点
            u = s * 120
            if 0.3 < u % 1.0 < 0.75 and abs(math.sin(p.z * 260)) > 0.3 and z0 + 0.1 < p.z < z0 + 0.15:
                return tint(BZ_D, k)
        return tint(BZ if j < 11 else BZ_D, k)
    a.rev(prof, 72, B, colf=col)
    for z, r in ((z0 + 0.155, 0.19), (z0 + 0.095, 0.182)):
        a.tube([(r * math.cos(2 * math.pi * k / 64), r * math.sin(2 * math.pi * k / 64), z) for k in range(65)], 0.003, BZ_L, segs=4, mat=B, cap=False)
    # 磬槌：斜放在台面上
    p0, p1 = Vector((-0.2, -0.17, H + 0.012)), Vector((0.12, -0.2, H + 0.012))
    a.tube([p0, p1], [0.009, 0.011], C('wood_dark'), segs=8, mat='wood_dark')
    a.blob(0.026, p1 + (p1 - p0).normalized() * 0.022 + Vector((0, 0, 0.012)), (1.1, 1, 1), RED, subdiv=2, bump=0.03, freq=30)
    a.tube([p0 - (p1 - p0).normalized() * 0.004, p0 + Vector((-0.01, 0.02, -0.006))], 0.0025, RED, segs=4)
    return a.finish(dist=0.35, view=(25, 20, 0.85))


def muyu(name):
    """木鱼：大木鱼（扁圆的鱼头形，朱漆描金）。正面一道横开的鱼口（只占正面一段，两头圆收，往里凹 3 厘米，口里黑），
    上下唇各鼓起一道、描金；鱼口两头往后上方是一对刻出来的鱼眼（凹下去的杏仁形眼窝、金边、凸起的眼珠）；
    背上一排排贴金的鳞；顶上的提手是两条鳌鱼拱成一道桥，鱼头在正中相对、一起衔着一颗火焰宝珠（鱼身有鳞纹、背鳍、尾巴分叉贴在木鱼背上）。
    坐在织锦垫上、放在朱漆小供台上，台上一根木鱼槌。原点在地面中心，总高约 0.8"""
    a = PAsset(name)
    H = 0.42
    _stand(a, 0.52, 0.48, H)
    _ring_cushion(a, 0.2, 0.05, H, 0)
    z0 = H + 0.045
    RX, RY, RZ = 0.21, 0.18, 0.135
    zc = z0 + RZ * 0.8
    LQ = 'lacquer'
    LAT0, LW, DEPTH = -0.12, 0.075, 0.03            # 鱼口：中心纬度、半高（弧度）、深
    LON_HALF = math.radians(52)                      # 鱼口从正面往两边各伸多少
    EYE_LON, EYE_LAT = math.radians(66), 0.2         # 鱼眼（离正面多少度、纬度）

    def front_of(lon):
        return lon + math.pi / 2                     # 离正面（-y）多少弧度（-π..π）

    def mouth(lon, lat):
        d = abs(((front_of(lon) + math.pi) % (2 * math.pi)) - math.pi)
        gl = 1.0 if d < LON_HALF else max(0.0, 1 - ((d - LON_HALF) / math.radians(9)) ** 2)
        gz = math.exp(-((lat - LAT0) / LW) ** 6)
        return gl * gz, gl

    def eye(lon, lat):
        d = ((front_of(lon) + math.pi) % (2 * math.pi)) - math.pi
        out = 0.0
        for sg in (-1, 1):
            u = (d - sg * EYE_LON) / 0.17
            v = (lat - EYE_LAT) / 0.11
            e = u * u + v * v
            if e < 1:
                out = max(out, (1 - e) ** 0.6)
        return out

    def base_pt(lon, lat):
        x = RX * math.cos(lat) * math.cos(lon)
        y = RY * math.cos(lat) * math.sin(lon)
        z = RZ * math.sin(lat)
        if z < -RZ * 0.8:
            z = -RZ * 0.8 - (z + RZ * 0.8) * 0.12      # 底下压平
        return Vector((x, y, z))

    def P_ll(lon, lat):
        p = base_pt(lon, lat)
        n = Vector((p.x / RX ** 2, p.y / RY ** 2, p.z / RZ ** 2)).normalized()
        g, gl = mouth(lon, lat)
        lip = 0.006 * gl * (math.exp(-((lat - (LAT0 + LW * 1.25)) / 0.05) ** 2) + math.exp(-((lat - (LAT0 - LW * 1.25)) / 0.05) ** 2))
        off = -DEPTH * g + lip - 0.007 * eye(lon, lat)
        return p + n * off + Vector((0, 0, zc))
    # 纬度：鱼口那一段加密（口的上下壁要陡）
    lats = [-math.pi / 2 + math.pi * k / 26 for k in range(27)]
    lats += [LAT0 + LW * (k / 6) * 1.9 for k in range(-6, 7)]
    lats = sorted(set(round(x, 5) for x in lats))
    nl = len(lats) - 1

    def P(s, t):
        lon = 2 * math.pi * s - math.pi / 2
        return P_ll(lon, lats[int(round(t * nl))])

    def strike(lon, lat):
        # 敲的地方：额头正中偏前（木鱼槌落下的那一块），漆磨薄了、颜色发暗发褐
        d = abs(((front_of(lon) + math.pi) % (2 * math.pi)) - math.pi)
        return max(0.0, 1 - (d / 0.62) ** 2 - ((lat - 0.78) / 0.3) ** 2)

    def col(s, t, p):
        lon = 2 * math.pi * s - math.pi / 2
        lat = lats[int(round(t * nl))]
        g, gl = mouth(lon, lat)
        if g > 0.5:
            return hexc('#2a0e0a')
        if eye(lon, lat) > 0.05:
            return tint(LAQ, -0.08)
        c = mix(LAQ, tint(LAQ, 0.1), max(0.0, math.sin(lat)))
        c = tint(c, 0.05 * noise.noise(p * 25) + 0.03 * noise.noise(p * 7))
        k = strike(lon, lat)
        if k > 0:
            c = mix(c, tint(hexc('#6a2a1e'), 0.04 * noise.noise(p * 40)), min(1.0, k * 1.3) ** 1.2 * 0.3)
        return c
    a.surf(P, 56, nl, LQ, colf=col, wrap=True)
    # 上下唇：两道贴金的弧线（在鼓起的唇上）
    for dl in (LW * 1.25, -LW * 1.25):
        pts = []
        for q in range(29):
            d = (q / 28 - 0.5) * 2 * (LON_HALF + math.radians(5))
            lon = -math.pi / 2 + d
            p = P_ll(lon, LAT0 + dl)
            pts.append(p + (p - Vector((0, 0, zc))).normalized() * 0.002)
        a.tube(pts, 0.0035, GILT, segs=5, mat='gold')
    # 鱼眼：眼窝一圈金边、凸起的眼珠（金）、黑瞳
    for sg in (-1, 1):
        lon_c = -math.pi / 2 + sg * EYE_LON
        ring = []
        for q in range(25):
            t = 2 * math.pi * q / 24
            ring.append(P_ll(lon_c + 0.17 * math.cos(t), EYE_LAT + 0.11 * math.sin(t)))
        cen = P_ll(lon_c, EYE_LAT)
        nrm = (cen - Vector((0, 0, zc))).normalized()
        a.tube([p + (p - Vector((0, 0, zc))).normalized() * 0.0015 for p in ring], 0.003, GILT, segs=5, mat='gold', cap=False)
        a.blob(0.016, cen + nrm * 0.004, (1.15, 1.15, 0.9), GILT, subdiv=2, bump=0, mat='gold', rot=_rot_to(nrm))
        a.blob(0.008, cen + nrm * 0.0155, (1, 1, 0.6), hexc('#1d120d'), subdiv=1, bump=0, rot=_rot_to(nrm))
    # 鳞：浅浮雕的鱼鳞，一排排像瓦一样从上往下压着（上一排的下沿翘起来压在下一排上面，沿口下面是一道暗槽），
    # 盖满背上和两侧（脸、眼睛、额头上敲的那一块空着）；只有离头最近的那一列鳞沿口贴金
    def base_n(lon, lat):
        p = base_pt(lon, lat)
        return Vector((p.x / RX ** 2, p.y / RY ** 2, p.z / RZ ** 2)).normalized()

    def clear_of_face(lon, lat):
        d = abs(((front_of(lon) + math.pi) % (2 * math.pi)) - math.pi)
        # 鳞往前一直铺到眼睛后面、额头两边（从正面看两侧也是一片鳞）；空出来的只有：眼睛、鱼口那一圈脸，额头正中敲的那块
        lim = math.radians(82 if lat < 0.42 else (36 if lat < 0.86 else 40))
        return d - lim

    SH = 0.0032                                   # 鳞沿口翘起来多高
    us = [-1.0, -0.6, -0.2, 0.2, 0.6, 1.0]
    vs_ = [0.0, 0.35, 0.65, 0.86, 1.0]
    for row in range(9):
        lat_top = 1.3 - 0.128 * row
        dlat = 0.19
        latm = lat_top - dlat * 0.5
        rl = math.hypot(RX, RY) / math.sqrt(2) * math.cos(latm)
        dlon = 0.033 / max(0.04, rl)
        n_all = int(2 * math.pi / dlon)
        dlon = 2 * math.pi / n_all
        cand = []
        for q in range(n_all):
            lon0 = math.pi / 2 + (q + 0.5 * (row % 2)) * dlon       # 从背后（+y）开始排
            if clear_of_face(lon0, latm) > dlon * 0.45:
                cand.append(lon0)
        # 离头最近的两片（左右各一）沿口贴金
        dfront = [abs(((front_of(l_) + math.pi) % (2 * math.pi)) - math.pi) for l_ in cand]
        gilt_set = set()
        if cand:
            for sg in (-1, 1):
                side_c = [k_ for k_, l_ in enumerate(cand) if (((front_of(l_) + math.pi) % (2 * math.pi)) - math.pi) * sg > 0]
                if side_c:
                    gilt_set.add(min(side_c, key=lambda k_: dfront[k_]))
        for k_, lon0 in enumerate(cand):
            def SP(u, v, lon0=lon0):
                vend = 0.55 + 0.45 * math.sqrt(max(0.0, 1 - u * u))
                lat = lat_top - dlat * v * vend
                lon = lon0 + u * dlon * 0.56
                if v < 0.82:
                    h = math.sin(math.pi / 2 * v / 0.82) ** 0.8
                else:
                    h = max(0.0, math.cos(math.pi / 2 * min(1.0, (v - 0.82) / 0.18))) ** 0.6
                h = SH * h * (1 - abs(u) ** 4) ** 0.5
                if abs(u) > 0.999 or v < 1e-6 or v > 0.999:
                    h -= 0.0015
                return base_pt(lon, lat) + base_n(lon, lat) * h + Vector((0, 0, zc))
            tb = new_bm()
            cl = tb.loops.layers.float_color['col']
            V_ = [[tb.verts.new(SP(u, v)) for v in vs_] for u in us]
            tg = new_bm() if k_ in gilt_set else None
            for iu in range(len(us) - 1):
                for iv in range(len(vs_) - 1):
                    vc = (vs_[iv] + vs_[iv + 1]) / 2
                    gilt = tg is not None and vc > 0.86
                    T_ = tg if gilt else tb
                    if gilt:
                        q4 = [T_.verts.new(V_[x][y].co) for (x, y) in ((iu, iv), (iu + 1, iv), (iu + 1, iv + 1), (iu, iv + 1))]
                    else:
                        q4 = [V_[iu][iv], V_[iu + 1][iv], V_[iu + 1][iv + 1], V_[iu][iv + 1]]
                    f = T_.faces.new(q4)
                    c = GILT if gilt else (tint(LAQ, 0.07) if 0.65 <= vc <= 0.86 else (LAQ if vc > 0.3 else tint(LAQ, -0.06)))
                    lc = T_.loops.layers.float_color['col']
                    for l in f.loops:
                        l[lc] = (c[0], c[1], c[2], 0.0)
            # 法线：沿 u（经度增加）× 沿 v（纬度往下）——经度增加是绕 z 逆时针、纬度往下，两者叉乘朝里：翻过来
            bmesh.ops.reverse_faces(tb, faces=tb.faces[:])
            a.merge(tb, LQ)
            if tg is not None:
                bmesh.ops.reverse_faces(tg, faces=tg.faces[:])
                bmesh.ops.remove_doubles(tg, verts=tg.verts, dist=1e-7)
                a.merge(tg, 'gold')
    # 提手：两条鳌鱼拱成桥，头在正中相对，衔一颗火焰宝珠
    ztop = zc + RZ * 0.985
    for sx in (-1, 1):
        tail = Vector((sx * 0.135, 0.01, ztop - 0.025))
        pts = [tail, Vector((sx * 0.12, 0.01, ztop + 0.02)), Vector((sx * 0.095, 0.008, ztop + 0.055)), Vector((sx * 0.062, 0.005, ztop + 0.068)),
               Vector((sx * 0.038, 0.004, ztop + 0.062))]
        a.tube(pts, [0.011, 0.015, 0.018, 0.019, 0.018], LAQ, segs=10, mat=LQ, color2=tint(LAQ, 0.1))
        # 鱼头：圆额、往前的嘴（张着），两只金眼、两根须
        hd = Vector((sx * 0.032, 0.004, ztop + 0.06))
        a.blob(0.021, hd, (1.25, 0.95, 0.95), LAQ, subdiv=2, bump=0, mat=LQ)
        a.blob(0.012, hd + Vector((-sx * 0.02, 0, 0.006)), (1.2, 0.85, 0.55), tint(LAQ, 0.05), subdiv=2, bump=0, mat=LQ)
        a.blob(0.01, hd + Vector((-sx * 0.019, 0, -0.01)), (1.2, 0.8, 0.45), tint(LAQ, -0.06), subdiv=1, bump=0, mat=LQ)
        for sy in (-1, 1):
            a.blob(0.0055, hd + Vector((-sx * 0.004, sy * 0.016, 0.01)), (1, 1, 1), GILT, subdiv=1, bump=0, mat='gold')
            a.tube([hd + Vector((-sx * 0.016, sy * 0.008, 0.004)), hd + Vector((-sx * 0.006, sy * 0.03, 0.02)), hd + Vector((sx * 0.012, sy * 0.036, 0.026))],
                   [0.0022, 0.0016, 0.0008], GILT, segs=4, mat='gold')
        # 背鳍：沿着拱背一排金色的小尖
        for k in range(5):
            t = 0.15 + 0.16 * k
            i0 = min(3, int(t * 4))
            p = pts[i0].lerp(pts[i0 + 1], t * 4 - i0)
            a.tube([p + Vector((0, 0, 0.014)), p + Vector((sx * 0.008, 0, 0.03 - 0.002 * k))], [0.005, 0.001], GILT, segs=4, mat='gold')
        # 身上的鳞纹（一圈圈金线）
        for k in range(3):
            p = pts[1].lerp(pts[3], 0.2 + 0.3 * k)
            d = (pts[3] - pts[1]).normalized()
            side = d.cross(Vector((0, 1, 0))).normalized()
            ring = [p + (side * math.cos(t) + Vector((0, 1, 0)) * math.sin(t)) * 0.0175 for t in [math.pi * (-0.1 + 1.2 * q / 10) for q in range(11)]]
            a.tube(ring, 0.002, GILT, segs=4, mat='gold')
        # 尾巴：分叉的两片，贴在木鱼背上
        for sy in (-1, 1):
            d = Vector((sx * 0.8, sy * 0.55, -0.25)).normalized()
            petal(a, tail + Vector((0, 0, 0.004)), d, Vector((0, 0, 1)) - d * d.z, 0.045, 0.03, 0.006, 'gold', GILT, tint(GILT, 0.08), GILT_D,
                  cup=0.1, curl=0.15, ridge=0.4, nu=4, nv=4, round_=0.5)
    # 宝珠：两只鱼嘴中间，外面一圈火焰
    pearl = Vector((0, 0.004, ztop + 0.072))
    a.blob(0.019, pearl, (1, 1, 1), GILT, subdiv=3, bump=0, mat='gold')
    for k in range(9):
        ang = 2 * math.pi * k / 9
        d = Vector((math.cos(ang), 0, math.sin(ang)))
        a.tube([pearl + d * 0.016, pearl + d * 0.03 + Vector((0, 0, 0.012))], [0.006, 0.001], tint(GILT, 0.06), segs=4, mat='gold')
    # 木鱼槌
    p0, p1 = Vector((0.12, -0.2, H + 0.012)), Vector((-0.16, -0.17, H + 0.012))
    a.tube([p0, p1], [0.009, 0.011], C('wood_dark'), segs=8, mat='wood_dark')
    a.blob(0.03, p1 + (p1 - p0).normalized() * 0.026 + Vector((0, 0, 0.016)), (1.1, 1, 1), C('wood'), subdiv=2, bump=0, mat='wood')
    # 鳞沿口下面的暗槽：漆积在凹处更深
    occ_tint(a, [LQ], hexc('#3a0d09'), amount=0.6, dist=0.01, samples=10, power=1.1)
    return a.finish(dist=0.35, view=(20, 20, 0.85))


SUT = 'paint_sutra'


def _book(a, c, w, l, th, cover, rot=0.0, tilt=0.0):
    """一本经折装的经书：封面（绫子、题签）贴 paint_sutra 上面的四张封面之一，四周是一层层纸的书口"""
    R = Matrix.Translation(c) @ Matrix.Rotation(rot, 4, 'Z') @ Matrix.Rotation(tilt, 4, 'X')
    rc = px(SUT, 256 * cover, 0, 256 * (cover + 1), 512, inset=3)
    edge = px(SUT, 512, 520, 1024, 760, inset=4)
    hw, hl = w / 2, l / 2
    # 封面
    a.sheet([(-hw, -hl, th), (hw, -hl, th), (hw, hl, th), (-hw, hl, th)], 1, 1, SUT, rc, M=R)
    # 书口四面
    for (p0, p1, L) in (((-hw, -hl), (hw, -hl), w), ((hw, -hl), (hw, hl), l), ((hw, hl), (-hw, hl), w), ((-hw, hl), (-hw, -hl), l)):
        a.sheet([(p0[0], p0[1], 0.0), (p1[0], p1[1], 0.0), (p1[0], p1[1], th), (p0[0], p0[1], th)], 1, 1, SUT,
                (edge[0], edge[1], edge[0] + (edge[2] - edge[0]) * L / 0.3, edge[1] + (edge[3] - edge[1]) * th / 0.06), M=R)
    a.sheet([(-hw, hl, 0.0), (hw, hl, 0.0), (hw, -hl, 0.0), (-hw, -hl, 0.0)], 1, 1, 'toon', color=tint(C('paper'), -0.2), M=R)


def sutra_desk(name):
    """经案：翘头案（1.2 × 0.5，高 0.78），案面铺黄绫；上面一个斜的经架托着摊开的《心经》，旁边一摞经书（金刚经、法华经、药师经）、
    一串念珠、一只小引磬。原点在地面中心，正面朝 -y（念经的人站在 -y 那边）"""
    a = PAsset(name)
    W, D, H = 1.2, 0.5, 0.78
    hx, hy = W / 2, D / 2
    LQ = 'wood_dark'
    wd, wl, wdd = hexc('#5a3324'), hexc('#7a4a33'), hexc('#3e2219')
    # 案面：两头翘起来
    rrect_sweep(a, hx, hy, 0.01, [(-0.04, H - 0.045), (-0.003, H - 0.045), (0.0, H - 0.04), (0.0, H - 0.008), (-0.003, H)], LQ,
                colf=lambda j, p: wl if j == 3 else wd, cap_bottom=True, cap_top=True, cap_color=wd, step=0.12)
    for sx in (-1, 1):
        pts = [(sx * (hx - 0.12), H), (sx * (hx - 0.03), H), (sx * hx, H + 0.01), (sx * (hx + 0.03), H + 0.045), (sx * (hx + 0.035), H + 0.06),
               (sx * (hx - 0.005), H + 0.04), (sx * (hx - 0.05), H + 0.012), (sx * (hx - 0.12), H + 0.004)]
        poly = [(x, z) for (x, z) in pts]
        if sx < 0:
            poly = poly[::-1]
        plate(a, poly, (Vector((0, hy - 0.004, 0)), Vector((1, 0, 0)), Vector((0, 0, 1)), Vector((0, 1, 0))), D - 0.008, wd, LQ, bevel=0.003)
    # 翘头的正面、背面各贴一个金卷
    for sx in (-1, 1):
        for sy in (-1, 1):
            fr = (Vector((sx * (hx + 0.004), sy * (hy - 0.004 + 0.0006) if sy > 0 else -(hy - 0.004) - 0.0006, H + 0.026)), Vector((sx * -sy, 0, 0)),
                  Vector((0, 0, 1)), Vector((0, sy, 0)))
            relief(a, scroll2d((0.0, 0.0), 0.014, 1.1, math.pi * 0.5, -sx * sy, 12), fr, 0.0028, GILT)
    # 腿：方腿；两侧腿间一块挡板：板心深色，一圈起线的金框，正中一朵如意云头，下面一条卷草，四角各一个卷（角花）
    for sx in (-1, 1):
        for sy in (-1, 1):
            sq_path(a, [(sx * (hx - 0.1), sy * (hy - 0.05), H - 0.045), (sx * (hx - 0.1), sy * (hy - 0.05), 0.0)], 0.045, wd, LQ)
        N_ = Vector((sx, 0, 0))
        U_ = Vector((0, sx, 0))
        o = Vector((sx * (hx - 0.1), 0, 0.2))
        # 板的两头插进腿里（不和腿的内面贴在同一个平面上）
        hw_ = hy - 0.055
        plate(a, [(-hw_, 0.0), (hw_, 0.0), (hw_, 0.48), (-hw_, 0.48)], (o + N_ * 0.009, U_, Vector((0, 0, 1)), N_), 0.018, wdd, LQ, bevel=0.003)
        fr = (o + N_ * 0.0095, U_, Vector((0, 0, 1)), N_)
        # 起线的框（贴金阳线）、框里四角的角花
        ix, iz0, iz1 = hw_ - 0.028, 0.03, 0.45
        relief(a, [(-ix, iz0), (ix, iz0), (ix, iz1), (-ix, iz1), (-ix, iz0 + 0.0001)], fr, 0.0036, GILT, taper=False)
        for (cx_, cz_, a0_, sg_) in ((-ix + 0.03, 0.34, math.pi, 1), (ix - 0.03, 0.34, 0.0, -1), (-ix + 0.03, iz0 + 0.03, math.pi, -1),
                                     (ix - 0.03, iz0 + 0.03, 0.0, 1)):
            relief(a, scroll2d((cx_, cz_), 0.02, 1.1, a0_ + (math.pi * 0.5 if cz_ > 0.2 else -math.pi * 0.5) * sg_ * 0.0, sg_, 12), fr, 0.003, GILT)
        # 框里分上下两格（绦环板）：上面一条窄格里一道小卷草；下面的大格正中一朵如意云头，云头底下左右各伸出一枝卷草，
        # 往外、往上卷成一个涡，枝上各长两片叶
        relief(a, [(-ix, 0.37), (ix, 0.37)], fr, 0.003, GILT, taper=False)
        vine(a, fr, -ix + 0.035, ix - 0.035, 0.405, 0.011, 0.075, GILT, 0.0024, leaf=True)
        cloud_scroll(a, fr, 0.0, 0.215, 0.12, GILT, r=0.0048)
        for sg in (-1, 1):
            stem = [(sg * 0.01, 0.15), (sg * 0.04, 0.115), (sg * 0.085, 0.1), (sg * 0.125, 0.11), (sg * 0.145, 0.14)]
            spiral = scroll2d((sg * 0.12, 0.155), 0.028, 1.15, math.pi * (0.0 if sg > 0 else 1.0) - sg * math.pi * 0.25, sg, 14, shrink=0.2)
            relief(a, smooth_prof(stem, 3) + spiral[1:], fr, 0.0042, GILT)
            for (u0, v0, du, dv) in ((0.05, 0.11, 0.018, -0.04), (0.095, 0.1, -0.006, 0.045)):
                # 叶子：一圈杏仁形的阳线（叶根、两边鼓、叶尖）
                L_ = math.hypot(du, dv)
                nx_, ny_ = -dv / L_ * 0.011, du / L_ * 0.011
                leaf = [(u0, v0), (u0 + du * 0.45 + nx_, v0 + dv * 0.45 + ny_), (u0 + du, v0 + dv), (u0 + du * 0.45 - nx_, v0 + dv * 0.45 - ny_),
                        (u0, v0)]
                relief(a, [(sg * x, y) for (x, y) in smooth_prof(leaf, 2)], fr, 0.0028, GILT, taper=False, segs=4)
            # 底下一个小卷收尾
            relief(a, scroll2d((sg * 0.06, 0.06), 0.022, 1.0, math.pi * 0.5, -sg, 12, shrink=0.25), fr, 0.0034, GILT)
        sq_path(a, [(sx * (hx - 0.1), -(hy - 0.05), 0.04), (sx * (hx - 0.1), hy - 0.05, 0.04)], 0.035, wd, LQ, caps=False)
        sq_path(a, [(sx * (hx - 0.1), -(hy - 0.05), 0.7), (sx * (hx - 0.1), hy - 0.05, 0.7)], 0.03, wd, LQ, caps=False)
    # 前后牙条：下沿壸门式（两头牙头、正中垂一个小尖），正面贴金卷草、正中一朵云头
    La = W - 0.2 - 0.045
    edge = [(u, dz * 0.85) for (u, dz) in _apron_edge()]
    for sy in (-1, 1):
        N_ = Vector((0, sy, 0))
        U_ = Vector((-sy, 0, 0))
        poly = [(-La / 2 + u * La, -dz) for (u, dz) in edge]
        poly = [(La / 2 + 0.002, 0.0), (-La / 2 - 0.002, 0.0)] + [(-La / 2 - 0.002, poly[0][1])] + poly[1:-1] + [(La / 2 + 0.002, poly[-1][1])]
        o = Vector((0, sy * (hy - 0.05 + 0.0225 - 0.003), H - 0.045))
        plate(a, poly, (o, U_, Vector((0, 0, 1)), N_), 0.018, wd, LQ, bevel=0.003)
        # （牙条正面被垂下来的黄绫挡住，只在两头的牙头上各贴一个金卷）
        fr = (o + N_ * 0.0005, U_, Vector((0, 0, 1)), N_)
        for sg in (-1, 1):
            relief(a, scroll2d((sg * (La / 2 - 0.03), -0.06), 0.016, 1.1, math.pi * (0.0 if sg > 0 else 1.0), sg, 12), fr, 0.003, GILT)
    # 案面上的黄绫：暗花缎（和供桌一样，paint_frontal），前后各垂下一截（paint_sutra 的黄绫边：红边、缠枝莲、石青回纹，横着接 4 遍）
    zt = H + 0.002
    yrect = px(SUT, 512, 768, 1024, 1024, inset=2)
    tiled_sheet(a, -hx + 0.13, hx - 0.13, -(hy + 0.004), hy + 0.004, zt, 0.3, DAMASK_RECT, FRO, ox=-0.15, oy=-0.15)
    for sy in (-1, 1):
        y0 = sy * (hy + 0.004)
        pts = [(-hx + 0.13, y0, zt - 0.12), (hx - 0.13, y0, zt - 0.12), (hx - 0.13, y0, zt), (-hx + 0.13, y0, zt)]
        if sy > 0:
            pts = [pts[1], pts[0], pts[3], pts[2]]
        a.sheet(pts, 4, 1, SUT, yrect, back=tint(YEL, -0.3), rep_u=4)
    # 经架：斜板（前低后高）+ 托条，上面摊开的《心经》
    zb = zt + 0.002
    ang = math.radians(28)
    c = Vector((-0.05, 0.02, zb))
    Wb, Lb = 0.3, 0.26
    up = Vector((0, math.cos(ang), math.sin(ang)))
    a.box((Wb + 0.02, 0.012, 0.03), c + Vector((0, -Lb / 2 * math.cos(ang) - 0.01, 0)), color=wd, bevel=0.003, mat=LQ)
    for sx in (-1, 1):
        a.tube([c + Vector((sx * 0.12, Lb * 0.35 * math.cos(ang), 0)), c + Vector((sx * 0.12, Lb * 0.35 * math.cos(ang), Lb * math.sin(ang) * 0.85))],
               0.008, wd, segs=6, mat=LQ)
    o = c + Vector((0, -Lb / 2 * math.cos(ang), 0.012))
    corners = [o + Vector((-Wb / 2, 0, 0)), o + Vector((Wb / 2, 0, 0)), o + Vector((Wb / 2, 0, 0)) + up * Lb, o + Vector((-Wb / 2, 0, 0)) + up * Lb]
    nrm = (corners[1] - corners[0]).cross(corners[3] - corners[0]).normalized()
    t_ = [p - nrm * 0.008 for p in corners]
    # 经架的斜板：一块有厚度的板（背面也是实的）
    plate(a, [(-Wb / 2, 0.0), (Wb / 2, 0.0), (Wb / 2, Lb), (-Wb / 2, Lb)], (o - nrm * 0.008, Vector((1, 0, 0)), up, nrm), 0.012, wl, LQ, bevel=0.002)
    # 两页（中间略凹）
    prect = px(SUT, 0, 516, 512, 1020, inset=3)
    a.sheet(corners, 8, 2, SUT, prect, disp=lambda s_, t_: 0.012 * math.sin(math.pi * s_) ** 0.6 - 0.012 * math.exp(-((s_ - 0.5) / 0.05) ** 2),
            back=tint(C('paper'), -0.15))
    # 一摞经书
    for k, cv in enumerate((0, 1, 3)):
        _book(a, Vector((0.36 + 0.004 * k, 0.02 - 0.006 * k, zb + 0.032 * k)), 0.13, 0.27, 0.03, cv, rot=0.04 * (k - 1))
    # 念珠：一圈小珠子，搭在案上，一个红穗
    bead = hexc('#6a3a22')
    cc = Vector((-0.38, -0.08, zb + 0.009))
    for q in range(36):
        t = 2 * math.pi * q / 36
        p = cc + Vector((0.075 * math.cos(t) + 0.01 * math.sin(2 * t), 0.05 * math.sin(t), 0))
        a.blob(0.0085, p, (1, 1, 1), vary(bead, a.rng, 0.04), subdiv=1, bump=0, mat='wood_dark')
    a.blob(0.013, cc + Vector((0.086, -0.002, 0.004)), (1, 1, 1), GILT, subdiv=2, bump=0, mat='gold')
    for q in range(5):
        a.tube([cc + Vector((0.09, 0, 0.002)), cc + Vector((0.14 + 0.005 * q, -0.02 + 0.01 * q, -0.004))], [0.002, 0.0015], RED, segs=3)
    # 引磬：一只小铜钵装在木柄上，横放
    p0 = Vector((0.12, -0.17, zb + 0.008))
    a.tube([p0, p0 + Vector((0.16, 0.02, 0))], 0.007, wd, segs=6, mat=LQ)
    a.rev([(0.0, 0.0), (0.02, 0.002), (0.03, 0.015), (0.032, 0.03), (0.028, 0.031), (0.026, 0.018), (0.0, 0.01)], 20, 'bronze',
          loc=p0 + Vector((-0.02, 0.0, 0.024)), rot=(0, math.pi / 2, 0), colf=lambda s_, j, p: BRASS_L if j in (3, 4) else BRASS)
    return a.finish(dist=0.5, view=(20, 30, 0.85))


def donation_box(name):
    """功德箱：朱漆木箱（0.7 宽、0.45 深、0.88 高），正面一块描金框的牌子上凸起两个贴金大字「功德」，下面一朵贴金莲花；
    箱盖略出檐，盖上一道铜的投币口；四条竖边上下都包着如意形的铜饰件，前面一把铜锁，两侧铜拉环；
    两侧、背面各一块描金框的小牌子（贴金莲花、卷草、云头）；下面一个带小脚的底座。原点在地面中心"""
    a = PAsset(name)
    LQ = 'lacquer'
    W, D = 0.7, 0.45
    lq, lq_l, lq_d = LAQ, tint(LAQ, 0.07), tint(LAQ, -0.12)
    B = 'bronze'
    # 底座
    rrect_sweep(a, W / 2 + 0.02, D / 2 + 0.02, 0.01, [(-0.02, 0.025), (0.0, 0.025), (0.0, 0.07), (-0.01, 0.08), (-0.03, 0.082)], LQ,
                colf=lambda j, p: lq_d if j < 2 else lq, step=0.2, cap_top=True, cap_color=lq_d)
    for sx in (-1, 1):
        for sy in (-1, 1):
            a.lathe([(0.0, 0.0), (0.028, 0.0, lq_d), (0.032, 0.012, lq), (0.026, 0.026), (0.0, 0.026)], (sx * (W / 2 - 0.02), sy * (D / 2 - 0.02), 0),
                    segs=10, color=lq_d, mat=LQ)
    # 箱身
    z0, z1 = 0.08, 0.8
    rrect_sweep(a, W / 2, D / 2, 0.012, [(-0.02, z0), (0.0, z0 + 0.004), (0.0, z1 - 0.004), (-0.02, z1)], LQ, color=lq, step=0.2)
    # 箱盖：略出檐，冰盘沿
    rrect_sweep(a, W / 2 + 0.025, D / 2 + 0.025, 0.015, [(-0.04, z1), (-0.004, z1), (0.0, z1 + 0.006), (0.003, z1 + 0.025), (0.0, z1 + 0.04),
                                                        (-0.006, z1 + 0.046), (-0.03, z1 + 0.05)], LQ,
                colf=lambda j, p: lq_l if 2 <= j <= 4 else lq, step=0.2, cap_top=True, cap_bottom=True, cap_color=lq)
    zt = z1 + 0.05
    # 投币口：铜板、中间一道黑缝
    a.box((0.3, 0.1, 0.006), (0, 0, zt), color=BRASS, bevel=0.003, mat=B)
    a.box((0.22, 0.016, 0.002), (0, 0, zt + 0.006), color=hexc('#120a08'), bevel=0.0)
    for sx in (-1, 1):
        a.blob(0.006, (sx * 0.135, 0, zt + 0.006), (1, 1, 0.6), BRASS_L, subdiv=1, bump=0, mat=B)
    # 正面的牌子：描金的框、深红底、两个凸起的贴金大字
    fy = -D / 2
    pz0, pz1 = 0.36, 0.72
    plate(a, [(-0.27, pz0), (0.27, pz0), (0.27, pz1), (-0.27, pz1)], (Vector((0, fy - 0.006, 0)), Vector((1, 0, 0)), Vector((0, 0, 1)), Vector((0, -1, 0))),
          0.008, lq_d, LQ, bevel=0.003)
    frame_pts = [(-0.255, pz0 + 0.015), (0.255, pz0 + 0.015), (0.255, pz1 - 0.015), (-0.255, pz1 - 0.015), (-0.255, pz0 + 0.015)]
    a.tube([Vector((x, fy - 0.0075, z)) for (x, z) in frame_pts], 0.006, GILT, segs=6, mat='gold', cap=False)
    for (x, z) in frame_pts[:4]:
        a.blob(0.013, (x, fy - 0.009, z), (1, 0.5, 1), GILT, subdiv=2, bump=0, mat='gold')
    a.text3d('功德', 0.19, 0.014, loc=(0.0, fy - 0.0062, (pz0 + pz1) / 2 + 0.005), color=GILT, mat='gold', bevel=0.0018, spacing=1.05)
    # 牌子下面：一朵贴金的莲花（凸起的花瓣）、两边卷草
    fr = (Vector((0, fy - 0.001, 0)), Vector((1, 0, 0)), Vector((0, 0, 1)), Vector((0, -1, 0)))
    lc = Vector((0, fy - 0.002, 0.2))
    for k in range(7):
        ang = math.radians(-75 + 25 * k)
        d = Vector((math.sin(ang), 0, math.cos(ang)))
        petal(a, lc, d, Vector((0, -1, 0)), 0.07 if k in (2, 3, 4) else 0.055, 0.04, 0.012, 'gold', GILT, tint(GILT, 0.08), GILT_D, cup=0.0,
              curl=0.1, ridge=0.5, nu=4, nv=4, round_=1.0)
    for sg in (-1, 1):
        vine(a, (Vector((sg * 0.07, fy - 0.001, 0)), Vector((sg, 0, 0)), Vector((0, 0, 1)), Vector((0, -1, 0))), 0.0, 0.22, 0.2, 0.025, 0.11, GILT, 0.004)
    # 四角包铜（如意云头形的薄片）：前后四条竖边，每条边的上下两头、两个面上各一片
    for sx in (-1, 1):
        for sy in (-1, 1):
            for z in (z0 + 0.004, z1 - 0.004):
                sz = 1 if z > 0.4 else -1
                for (N_, U_) in ((Vector((0, sy, 0)), Vector((-sx, 0, 0))), (Vector((sx, 0, 0)), Vector((0, -sy, 0)))):
                    base = Vector((sx * W / 2, sy * D / 2, z))
                    o = base + N_ * 0.001
                    poly = [(0.0, 0.0), (0.075, 0.0), (0.07, -0.02 * sz), (0.05, -0.03 * sz), (0.035, -0.05 * sz), (0.02, -0.07 * sz), (0.0, -0.075 * sz)]
                    if sz < 0:
                        poly = poly[::-1]
                    if (U_.cross(Vector((0, 0, 1)))).dot(N_) > 0:
                        poly = [(u, v) for (u, v) in poly][::-1]
                    plate(a, poly, (o + N_ * 0.0025, U_, Vector((0, 0, 1)), N_), 0.003, BRASS, B, bevel=0.0)
                    a.blob(0.005, o + N_ * 0.004 + U_ * 0.02 + Vector((0, 0, -0.02 * sz)), (1, 1, 1), BRASS_L, subdiv=1, bump=0, mat=B)
    # 两侧、背面：各一块描金框的牌子，里面一朵贴金莲花、两边卷草、上面一朵云头（放在过道边、正面朝着过道，进门和静坐的人看到的是侧面、背面）
    for (N_, U_, c_, w_) in ((Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((W / 2, 0, 0.0)), 0.3),
                             (Vector((-1, 0, 0)), Vector((0, -1, 0)), Vector((-W / 2, 0, 0.0)), 0.3),
                             (Vector((0, 1, 0)), Vector((-1, 0, 0)), Vector((0, D / 2, 0.0)), 0.5)):
        V_ = Vector((0, 0, 1))
        pz0_, pz1_ = 0.2, 0.54
        plate(a, [(-w_ / 2, pz0_), (w_ / 2, pz0_), (w_ / 2, pz1_), (-w_ / 2, pz1_)], (c_ + N_ * 0.006, U_, V_, N_), 0.008, lq_d, LQ, bevel=0.003)
        fp = [(-w_ / 2 + 0.014, pz0_ + 0.014), (w_ / 2 - 0.014, pz0_ + 0.014), (w_ / 2 - 0.014, pz1_ - 0.014), (-w_ / 2 + 0.014, pz1_ - 0.014)]
        fpts = [c_ + N_ * 0.0075 + U_ * u + V_ * v for (u, v) in fp]
        a.tube(fpts + [fpts[0]], 0.005, GILT, segs=6, mat='gold', cap=False)
        for q in fpts:
            a.blob(0.011, q + N_ * 0.002, (1, 1, 1), GILT, subdiv=1, bump=0, mat='gold')
        lc_ = c_ + N_ * 0.0095 + V_ * 0.3
        for k in range(7):
            ang = math.radians(-75 + 25 * k)
            d = U_ * math.sin(ang) + V_ * math.cos(ang)
            petal(a, lc_, d, N_, 0.075 if k in (2, 3, 4) else 0.058, 0.042, 0.011, 'gold', GILT, tint(GILT, 0.08), GILT_D, cup=0.0,
                  curl=0.1, ridge=0.45, nu=4, nv=4, round_=1.0)
        fr = (c_ + N_ * 0.0065, U_, V_, N_)
        for sg in (-1, 1):
            relief(a, scroll2d((sg * (w_ / 2 - 0.06), 0.27), 0.03, 1.1, math.pi * (0.0 if sg > 0 else 1.0), sg, 18), fr, 0.004, GILT)
            relief(a, [(sg * 0.05, 0.255), (sg * (w_ / 2 - 0.09), 0.235), (sg * (w_ / 2 - 0.05), 0.25)], fr, 0.0035, GILT)
        cloud_scroll(a, fr, 0.0, 0.46, 0.05, GILT, r=0.004)
    # 前面的铜锁：锁鼻、一把横的老式铜锁
    lz = z1 - 0.02
    a.box((0.06, 0.006, 0.07), (0, fy - 0.003, lz - 0.06), color=BRASS, bevel=0.002, mat=B)
    a.box((0.07, 0.022, 0.03), (0, fy - 0.02, lz - 0.075), color=BRASS, bevel=0.005, mat=B)
    a.tube([(-0.025, fy - 0.02, lz - 0.045), (-0.025, fy - 0.02, lz - 0.02), (0.025, fy - 0.02, lz - 0.02), (0.025, fy - 0.02, lz - 0.045)], 0.0035,
           BRASS_L, segs=5, mat=B)
    # 两侧的铜拉环
    for sx in (-1, 1):
        c = Vector((sx * (W / 2 + 0.004), 0, 0.62))
        a.rev([(0.0, 0.0), (0.03, 0.0), (0.03, 0.004), (0.0, 0.004)], 16, B, loc=c, rot=(0, sx * math.pi / 2, 0), color=BRASS)
        pts = [c + Vector((sx * 0.012, 0.035 * math.cos(t), -0.035 * math.sin(t) - 0.0)) for t in [math.pi * q / 12 for q in range(13)]]
        a.tube(pts, 0.005, BRASS_L, segs=6, mat=B)
    return a.finish(dist=0.4, view=(25, 20, 0.85))


# ════════════════════ 太平缸（月台两侧） ════════════════════

def water_vat(name):
    """太平缸：铜缸（口径 1.16、缸身高约 0.75），缸口一道卷起来的圆唇，唇下一圈凸起的回纹带，肩上一圈乳钉（两行、上下各一道弦纹），
    腹下两道弦纹；两侧一对大铺首衔环（狮面约 0.22 宽、嘴里衔着铜环）。铜绿往凹处钻（纹样根部、唇下、铺首四周），铺首下面淌下来几道绿。
    坐在八角的石须弥座上（覆莲）；缸里一汪水（water 材质，水面 0.91），漂着三片兜起来的睡莲叶（叶脉、缺口）和一个花苞。
    原点在地面中心，总高 1.0"""
    a = PAsset(name)
    rng = a.rng
    st, sl, sd = C('stone'), C('stone_lit'), C('stone_dark')
    S = 'stone'
    from props_hd import _ngon
    a.prism(_ngon(8, 0.66, math.pi / 8), 0.0, 0.08, sd, bevel=0.025, top=st, mat=S)
    a.prism(_ngon(8, 0.6, math.pi / 8), 0.08, 0.12, st, bevel=0.015, top=sl, mat=S)
    for i in range(24):
        ang = 2 * math.pi * (i + 0.5) / 24
        out = Vector((math.cos(ang), math.sin(ang), 0))
        petal(a, out * 0.5 + Vector((0, 0, 0.2)), out * 0.55 + Vector((0, 0, -0.85)), out, 0.08, 0.14, 0.03, S, st, sl, None, cup=0.0, curl=0.2,
              ridge=0.4, nu=4, nv=4, round_=1.0)
    a.prism(_ngon(8, 0.52, math.pi / 8), 0.12, 0.2, tint(st, -0.04), bevel=0.012, mat=S)
    a.prism(_ngon(8, 0.58, math.pi / 8), 0.2, 0.25, st, bevel=0.015, top=sl, mat=S)
    B = 'bronze'
    bz, bl, bd = hexc('#4d4433'), hexc('#8a7b55'), hexc('#2c271e')
    green = hexc('#6c9686')
    z0 = 0.25
    # 缸身：外壁从下往上、圆唇（往外卷一圈）、内壁往下、缸底（往里收到轴）——两头都在轴上，自动朝外
    prof = [(0.0, z0 + 0.01), (0.3, z0 + 0.01), (0.4, z0 + 0.04), (0.47, z0 + 0.12), (0.53, z0 + 0.26), (0.55, z0 + 0.38), (0.545, z0 + 0.48),
            (0.53, z0 + 0.58), (0.52, z0 + 0.64), (0.521, z0 + 0.68), (0.535, z0 + 0.705), (0.556, z0 + 0.716), (0.574, z0 + 0.723),
            (0.582, z0 + 0.733), (0.58, z0 + 0.744), (0.568, z0 + 0.75), (0.55, z0 + 0.75), (0.53, z0 + 0.746), (0.508, z0 + 0.736),
            (0.495, z0 + 0.72), (0.488, z0 + 0.69), (0.486, z0 + 0.6), (0.47, z0 + 0.32), (0.44, z0 + 0.3), (0.0, z0 + 0.3)]
    R_of = prof_r(prof[1:])
    lion_ang = (0.0, math.pi)

    def col(s, j, p):
        k = 0.05 * noise.noise(p * 12)
        c = mix(bd, bz, min(1.0, max(0.0, (p.z - z0) / 0.3)))
        if 11 <= j <= 16:
            c = bl                                     # 唇上磨亮
        if j >= 18:
            c = tint(bd, -0.04)                        # 缸里面
        g = max(0.0, min(1.0, 0.45 + noise.noise(p * 5 + Vector((3, 1, 2))) * 0.8 - (p.z - z0) * 0.5))
        return tint(mix(c, green, g * 0.3), k)
    a.rev(prof, 80, B, colf=col)
    # 唇下一圈回纹带（z0+0.62..0.665），肩上两行乳钉（z0+0.52..0.58 之间），腹下两道弦纹
    meander_band(a, R_of, z0 + 0.618, z0 + 0.668, 36, bl, B, rr=0.0042)
    for (z, rr) in ((z0 + 0.505, 0.006), (z0 + 0.595, 0.006), (z0 + 0.17, 0.009), (z0 + 0.2, 0.006)):
        r = R_of(z) + rr * 0.5
        a.tube([(r * math.cos(2 * math.pi * k / 96), r * math.sin(2 * math.pi * k / 96), z) for k in range(97)], rr, bl, segs=5, mat=B, cap=False)
    for row, z in enumerate((z0 + 0.528, z0 + 0.568)):
        n_ = 40
        for i in range(n_):
            ang = 2 * math.pi * (i + 0.5 * row) / n_
            if any(abs(((ang - la + math.pi) % (2 * math.pi)) - math.pi) < 0.2 for la in lion_ang):
                continue                                # 铺首那里不排
            r = R_of(z)
            o = Vector((math.cos(ang), math.sin(ang), 0))
            a.lathe([(0.0, -0.004), (0.012, 0.0), (0.009, 0.008), (0.0, 0.012)], o * r + Vector((0, 0, z)), segs=6, color=bl, mat=B,
                    rot=(0, math.pi / 2, ang))
    # 铺首衔环：两侧
    for la in lion_ang:
        o = Vector((math.cos(la), math.sin(la), 0))
        zc_ = z0 + 0.43
        lion_mask(a, o * (R_of(zc_) + 0.004) + Vector((0, 0, zc_)), o, Vector((0, 0, 1)), 0.22, bz, bl, bd, B)
    # 水面（从缸壁往里写：朝上）、睡莲叶、花苞
    zw = z0 + 0.66
    a.rev([(0.4875, zw), (0.0, zw)], 48, 'water', color=(0.3, 0.5, 0.5))
    for (x, y, r, rot_) in ((0.2, 0.12, 0.13, 0.3), (-0.14, -0.22, 0.1, 2.1), (-0.25, 0.18, 0.075, 4.0)):
        def Pp(s_, t_, x=x, y=y, r=r, rot_=rot_):
            ang = rot_ + 0.32 + (2 * math.pi - 0.64) * s_
            rr = r * t_ * (1 + 0.025 * math.sin(7 * ang))
            return Vector((x + rr * math.cos(ang), y + rr * math.sin(ang), zw + 0.004 + 0.022 * r / 0.13 * t_ ** 3))

        def pc(s_, t_, p, r=r):
            vein = abs(math.sin(math.pi * s_ * 13)) < 0.12 and t_ > 0.15
            return tint(C('pad'), -0.08) if vein else mix(C('pad'), C('pad_lit'), t_ ** 2)
        a.surf(Pp, 20, 4, 'toon', colf=pc, flip=True)
        a.surf(lambda s_, t_, Pp=Pp: Pp(s_, t_) - Vector((0, 0, 0.003)), 20, 4, 'toon', color=tint(C('pad'), -0.15))
    bud = Vector((0.06, 0.25, zw))
    a.tube([bud + Vector((0, 0, -0.02)), bud + Vector((0.004, 0, 0.05))], 0.005, hexc('#4c8a4a'), segs=6)
    for i in range(5):
        ang = 2 * math.pi * i / 5
        oo = Vector((math.cos(ang), math.sin(ang), 0))
        petal(a, bud + Vector((0, 0, 0.048)) + oo * 0.003, Vector((0, 0, 1)) + oo * 0.15, oo, 0.06, 0.034, 0.004, 'toon', hexc('#f6c3cf'), hexc('#d9587a'),
              None, cup=0.55, curl=-0.06, ridge=0.08, nu=5, nv=5, round_=0.6)

    # 铜绿：往凹处钻（纹样根部、唇下、铺首四周），铺首下面淌下来几道
    def drips(p, n):
        out = 0.0
        if p.z < z0 + 0.4 and n.z < 0.5:
            ang = math.atan2(p.y, p.x)
            for la in lion_ang:
                d = abs(((ang - la + math.pi) % (2 * math.pi)) - math.pi)
                if d < 0.22:
                    streak = max(0.0, math.sin(d * 70 + la * 3)) ** 3
                    out += 0.8 * streak * max(0.0, 1 - (z0 + 0.4 - p.z) / 0.3) * (1 - d / 0.22)
        return out
    occ_tint(a, [B], green, amount=0.6, dist=0.03, samples=12, power=0.8, extra=drips)
    return a.finish(dist=0.8, view=(20, 25, 0.9))


# ════════════════════ 后来加的公共小零件（香炉、太平缸、寿桃盘用） ════════════════════

def occ_tint(a, mats, color, amount=0.6, dist=0.08, samples=12, power=1.0, extra=None):
    """按「缝里有多深」往顶点色里混一个颜色（铜绿、积灰往凹处钻）：每个点往法线那半边打几条短射线，挡住的越多混得越多。
    extra(p, n) → 额外加的量（比如铺首下面一道道往下流的铜绿）"""
    import random as _r
    from mathutils.bvhtree import BVHTree
    verts, tris = [], []
    for m, b in a.parts.items():
        base = len(verts)
        b.verts.ensure_lookup_table()
        verts += [v.co.copy() for v in b.verts]
        for f in b.faces:
            vs = [v.index + base for v in f.verts]
            for i in range(1, len(vs) - 1):
                tris.append((vs[0], vs[i], vs[i + 1]))
    tree = BVHTree.FromPolygons(verts, tris, all_triangles=True)
    rng = _r.Random(5)
    dirs = []
    for i in range(samples):
        u, v = (i + rng.random()) / samples, rng.random()
        r, ang = math.sqrt(u), 2 * math.pi * v
        dirs.append(Vector((r * math.cos(ang), r * math.sin(ang), math.sqrt(max(0.0, 1 - u)))))
    zaxis = Vector((0, 0, 1))
    for m in mats:
        b = a.parts.get(m)
        if b is None:
            continue
        col = b.loops.layers.float_color['col']
        cache = {}
        for f in b.faces:
            for l in f.loops:
                n = (f.normal * 0.5 + l.vert.normal * 0.5).normalized()
                key = (l.vert.index, round(n.x, 1), round(n.y, 1), round(n.z, 1))
                k = cache.get(key)
                if k is None:
                    R = zaxis.rotation_difference(n).to_matrix()
                    o = l.vert.co + n * 0.0015
                    hit = sum(1 for d in dirs if tree.ray_cast(o, R @ d, dist)[0] is not None)
                    k = min(1.0, (hit / samples) ** power * amount + (extra(l.vert.co, n) if extra else 0.0))
                    cache[key] = k
                c = l[col]
                mm = mix((c[0], c[1], c[2]), color, max(0.0, min(1.0, k)))
                l[col] = (mm[0], mm[1], mm[2], c[3])


def meander_band(a, r_of, z0, z1, n, color, mat, rr=0.0016, flat=1.0):
    """一圈回纹（方形回旋的凸线），贴在旋转体的一段上：r_of(z) → 这个高度上器身的半径；n 个单元"""
    h = z1 - z0
    for i in range(n):
        a0 = 2 * math.pi * i / n
        da = 2 * math.pi / n
        pts2 = [(0.0, 0.0), (0.0, 1.0), (0.86, 1.0), (0.86, 0.22), (0.24, 0.22), (0.24, 0.74), (0.62, 0.74), (0.62, 0.46), (0.44, 0.46)]
        pts = []
        for (u, v) in pts2:
            ang = a0 + da * (0.07 + u * 0.86)
            z = z0 + h * (0.1 + 0.8 * v)
            r = r_of(z) + rr * 0.55
            pts.append(Vector((r * math.cos(ang), r * math.sin(ang), z)))
        a.tube(pts, rr, color, segs=4, mat=mat, flat=flat)
    for z in (z0, z1):
        r = r_of(z) + rr * 0.5
        a.tube([(r * math.cos(2 * math.pi * k / (n * 2)), r * math.sin(2 * math.pi * k / (n * 2)), z) for k in range(n * 2 + 1)], rr * 0.9, color,
               segs=4, mat=mat, cap=False)


def prof_r(prof):
    """旋转体轮廓 → r(z)（外壁那一段：z 单调上升的部分）"""
    pts = []
    for (r, z) in prof:
        if pts and z <= pts[-1][1]:
            break
        pts.append((r, z))

    def f(z):
        if z <= pts[0][1]:
            return pts[0][0]
        for i in range(len(pts) - 1):
            if pts[i][1] <= z <= pts[i + 1][1]:
                t = (z - pts[i][1]) / max(1e-9, pts[i + 1][1] - pts[i][1])
                return pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t
        return pts[-1][0]
    return f


def beast_mask(a, R_of, ang0, zc, s, color, hi, mat):
    """器腹上的一组兽面（饕餮）：中间一道鼻梁（兼作扉棱），两只凸眼、往外卷的眉、往上翻的角、嘴角两道卷。s 是整组的宽（弧长）"""
    def on(u, dz, out=0.0):
        z = zc + dz
        R = R_of(z)
        a_ = ang0 + u / R
        return Vector(((R + out) * math.cos(a_), (R + out) * math.sin(a_), z))
    k = s / 0.09
    # 鼻梁、扉棱：中间一道竖的，分三节
    for q in range(3):
        z = -0.014 * k + q * 0.011 * k
        a.tube([on(0, z, 0.002), on(0, z + 0.009 * k, 0.0045 if q == 1 else 0.0035)], [0.0042 * k, 0.0034 * k], hi, segs=6, mat=mat)
    for sg in (-1, 1):
        # 眼：眼眶一圈、凸起的眼珠
        e = on(sg * 0.02 * k, 0.003 * k, 0.0)
        ring = [on(sg * 0.02 * k + 0.0085 * k * math.cos(t), 0.003 * k + 0.0055 * k * math.sin(t), 0.0012) for t in [2 * math.pi * q / 12 for q in range(13)]]
        a.tube(ring, 0.0014 * k, hi, segs=4, mat=mat, cap=False)
        a.blob(0.0055 * k, on(sg * 0.02 * k, 0.003 * k, 0.0022 * k), (1.2, 1.0, 0.75), hi, subdiv=1, bump=0, mat=mat,
               rot=(0, 0, math.atan2(e.y, e.x)))
        # 眉：从眉心往外，末端往下卷一圈
        pts = [on(sg * (0.006 + 0.03 * t) * k, (0.012 + 0.004 * math.sin(math.pi * t)) * k, 0.0015) for t in (0, 0.33, 0.66, 1.0)]
        for q in range(7):
            th = q / 6 * math.pi * 1.5
            pts.append(on(sg * (0.039 - 0.006 * math.sin(th)) * k, (0.006 + 0.006 * math.cos(th)) * k, 0.0015))
        a.tube(pts, [0.0019 * k] * 4 + [0.0017 * k] * 7, hi, segs=4, mat=mat)
        # 角：往上外翻
        pts = [on(sg * (0.01 + 0.022 * t) * k, (0.017 + 0.008 * t + 0.003 * math.sin(math.pi * t)) * k, 0.0012) for t in (0, 0.33, 0.66, 1.0)]
        a.tube(pts, [0.0024 * k, 0.0026 * k, 0.002 * k, 0.001 * k], hi, segs=4, mat=mat)
        # 嘴角两道卷
        pts = [on(sg * (0.004 + 0.02 * t) * k, (-0.012 - 0.004 * math.sin(math.pi * t)) * k, 0.0012) for t in (0, 0.5, 1.0)]
        for q in range(5):
            th = q / 4 * math.pi * 1.3
            pts.append(on(sg * (0.028 - 0.004 * math.sin(th)) * k, (-0.012 + 0.004 * (1 - math.cos(th))) * k, 0.0012))
        a.tube(pts, 0.0015 * k, hi, segs=4, mat=mat)


def _fruit_dish(a):
    """白地青花的高足盘（口沿、足沿一道青边，盘心外圈一圈青花莲瓣、盘壁一圈青花点），口径 0.33；返回盘心的高度"""
    wh, bl, bl2 = hexc('#f6f2e8'), hexc('#2f4f93'), hexc('#5d7fbf')
    prof = [(0.0, 0.0), (0.058, 0.0), (0.06, 0.006), (0.058, 0.012), (0.05, 0.016), (0.03, 0.03), (0.024, 0.05), (0.028, 0.062),
            (0.06, 0.074), (0.1, 0.081), (0.13, 0.088), (0.15, 0.096), (0.162, 0.104), (0.166, 0.109), (0.161, 0.112),
            (0.15, 0.106), (0.13, 0.098), (0.1, 0.092), (0.06, 0.089), (0.0, 0.088)]

    def fc(sc, jc):
        j = int(jc)
        if j in (1, 2, 12, 13):
            return bl                                     # 足沿、口沿的青边
        if j in (15, 16):
            # 盘心外圈：一瓣一瓣的青花莲瓣（瓣、空相间）
            return bl2 if (sc * 24) % 1.0 < 0.62 else wh
        if j in (9, 10):
            return bl2 if (sc * 36) % 1.0 < 0.5 else wh
        return wh
    a.rev(prof, 72, 'toon', fcol=fc)
    return 0.094


def fruit_plate_peach(name):
    """寿桃盘（两边供桌上，和 fruit_plate 配一对）：同样的青花高足盘，堆着一摞寿桃（白面蒸的桃形馒头：尖上一抹粉红、
    一侧一道浅沟，桃根两片绿叶）：底下六个、中间三个、顶上一个。原点在底面中心，总高约 0.3"""
    a = PAsset(name)
    rng = a.rng
    z = _fruit_dish(a)
    dough, blush, crease = hexc('#f7efe2'), hexc('#ef7f98'), hexc('#d9a2a2')
    lf = hexc('#4f9a4a')

    def peach(c, r, tilt, yaw):
        R_ = Matrix.Translation(c) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(tilt, 4, 'Y')
        prof = [(0.0, -0.78), (0.55, -0.8), (0.88, -0.58), (1.0, -0.15), (0.94, 0.3), (0.74, 0.66), (0.42, 0.95), (0.14, 1.16), (0.0, 1.24)]
        b = PAsset('_peach')
        b.rev(prof, 20, 'toon', scale=r,
              colf=lambda s_, j, p: mix(dough, blush, max(0.0, min(1.0, (p.z / r - 0.35) / 0.8)) ** 1.3),
              wobble=lambda ang, j: 1.0 - 0.06 * math.exp(-((ang - math.pi) / 0.18) ** 2) * (1.0 if 1 < j < 8 else 0.4))
        # 一侧的浅沟（从尖往下的一道粉线）：贴着桃身（沟底在 -x 那边，桃身那里收进去 6%）
        rz = prof_r(prof[1:])
        pts = [Vector((-(rz(zn) * 0.94 * r + 0.0006), 0, zn * r)) for zn in [-0.35 + 1.45 * q / 10 for q in range(11)]]
        b.tube(pts, r * 0.03, crease, segs=4)
        # 桃根两片叶子
        for sg in (-1, 1):
            d = Vector((0.6 * sg, 0.8, -0.25)).normalized()
            petal(b, Vector((0, r * 0.55, -r * 0.62)), d, Vector((0, 0.3, 1)), r * 0.85, r * 0.42, r * 0.04, 'toon', tint(lf, -0.08), tint(lf, 0.1), None,
                  cup=0.25, curl=-0.1, ridge=0.25, nu=4, nv=5)
        for m, bm_ in list(b.parts.items()):
            a.merge(bm_, m, R_)
        b.parts = {}
    for i in range(6):
        ang = 2 * math.pi * i / 6 + 0.3
        c = Vector((0.086 * math.cos(ang), 0.086 * math.sin(ang), z + 0.03))
        peach(c, 0.034, math.radians(18), ang + math.pi)
    for i in range(3):
        ang = 2 * math.pi * i / 3 + 0.8
        c = Vector((0.04 * math.cos(ang), 0.04 * math.sin(ang), z + 0.085))
        peach(c, 0.034, math.radians(10), ang + math.pi)
    peach(Vector((0, 0, z + 0.14)), 0.035, 0.0, 0.4)
    return a.finish(dist=0.25, view=(20, 25, 0.9))


def lion_mask(a, c, out, up, s, bz, bl, bd, mat):
    """铺首衔环：狮面（圆鼓的脸盘、一圈卷毛的鬃、两道浓眉、凸眼、宽鼻、咧开的嘴）、嘴里衔着一只大铜环。
    c 是脸中心（贴在缸壁上），out 朝外，up 朝上，s 是脸宽（米）"""
    out, up = Vector(out).normalized(), Vector(up).normalized()
    side = up.cross(out).normalized()
    k = s / 0.22

    def P(u, v, w=0.0):
        return c + side * (u * k) + up * (v * k) + out * (w * k)
    rot = (0, 0, math.atan2(out.y, out.x) - math.pi / 2)
    # 脸盘：扁的圆饼
    a.blob(0.082 * k, P(0, 0.004, 0.006), (1.0, 0.36, 0.96), bz, subdiv=3, bump=0.0, mat=mat, rot=rot, top=tint(bz, 0.04))
    # 鬃：外圈一圈往外卷的毛卷（每个卷是一小段螺旋）
    for i in range(16):
        t = 2 * math.pi * i / 16
        cu, cv = 0.094 * math.cos(t), 0.094 * math.sin(t) + 0.004
        pts = []
        for q in range(9):
            th = t + math.pi * 0.5 + q / 8 * math.pi * 1.6
            rr = 0.018 * (1 - 0.55 * q / 8)
            pts.append(P(cu + rr * math.cos(th), cv + rr * math.sin(th), 0.012 + 0.006 * (1 - q / 8)))
        a.tube(pts, [0.0075 * k * (1 - 0.45 * q / 8) for q in range(9)], bz, segs=5, mat=mat, color2=bl)
    # 眉：两道浓眉，从眉心往外上翻、末端卷
    for sg in (-1, 1):
        pts = [P(sg * (0.008 + 0.05 * t), 0.03 + 0.012 * math.sin(math.pi * t) + 0.01 * t, 0.026 + 0.004 * math.sin(math.pi * t)) for t in (0, 0.25, 0.5, 0.75, 1.0)]
        for q in range(1, 6):
            th = q / 5 * math.pi * 1.2
            pts.append(P(sg * (0.058 + 0.008 * math.sin(th)), 0.04 - 0.008 * (1 - math.cos(th)), 0.026))
        a.tube(pts, [0.0075 * k] * 5 + [0.0065 * k, 0.006 * k, 0.005 * k, 0.004 * k, 0.0035 * k], bl, segs=6, mat=mat)
        # 凸眼：眼眶、眼珠
        e = P(sg * 0.03, 0.012, 0.03)
        a.blob(0.015 * k, e, (1.15, 0.8, 0.85), bz, subdiv=2, bump=0, mat=mat, rot=rot)
        a.blob(0.0085 * k, P(sg * 0.03, 0.011, 0.04), (1, 1, 1), bl, subdiv=2, bump=0, mat=mat, rot=rot)
        # 腮上的卷毛
        pts = [P(sg * (0.045 + 0.016 * math.cos(th)), -0.03 + 0.016 * math.sin(th), 0.024) for th in [math.pi * (0.5 + 1.5 * q / 8) * sg for q in range(9)]]
        a.tube(pts, 0.0045 * k, bl, segs=5, mat=mat)
    # 鼻：宽鼻头、两个鼻孔
    a.blob(0.02 * k, P(0, -0.008, 0.036), (1.4, 0.9, 0.9), bl, subdiv=2, bump=0, mat=mat, rot=rot)
    a.tube([P(0, 0.03, 0.03), P(0, 0.01, 0.038)], [0.007 * k, 0.009 * k], bz, segs=6, mat=mat)
    for sg in (-1, 1):
        a.blob(0.0055 * k, P(sg * 0.012, -0.016, 0.044), (1, 1, 0.7), bd, subdiv=1, bump=0, mat=mat, rot=rot)
    # 嘴：咧开的上唇一道、两边嘴角卷、上面两颗獠牙
    pts = [P(0.045 * math.cos(t), -0.04 + 0.018 * math.sin(t) * 0.0 - 0.012 * math.sin(t), 0.026) for t in [math.pi * (q / 12) for q in range(13)]]
    a.tube(pts, 0.0055 * k, bl, segs=5, mat=mat)
    a.blob(0.024 * k, P(0, -0.05, 0.016), (1.6, 0.6, 0.6), bd, subdiv=2, bump=0, mat=mat, rot=rot)
    for sg in (-1, 1):
        a.tube([P(sg * 0.02, -0.042, 0.03), P(sg * 0.022, -0.058, 0.032)], [0.004 * k, 0.001 * k], hexc('#d8cfb4'), segs=4)
    # 衔环：嘴里穿一根横销，挂一只粗铜环（环上两道棱）
    pin = P(0, -0.052, 0.03)
    a.tube([P(-0.026, -0.052, 0.03), P(0.026, -0.052, 0.03)], 0.0065 * k, bd, segs=6, mat=mat)
    R_ = 0.07 * k
    # 环：一圈粗的，前后各一道细棱（往外、往里各偏 1 厘米左右）
    for (dw, rr, cc) in ((0.0, 0.0125 * k, bl), (0.0105, 0.004 * k, tint(bl, 0.08)), (-0.0105, 0.004 * k, tint(bl, 0.08))):
        ring = [pin + side * (R_ * math.sin(t)) + up * (-R_ + R_ * math.cos(t)) + out * (0.006 * k + dw * k) for t in [2 * math.pi * q / 28 for q in range(29)]]
        a.tube(ring, rr, cc, segs=8 if not dw else 4, mat=mat, cap=False)


# ════════════════════ 摆放（Unity 世界坐标） ════════════════════
# yaw 是 Unity 的：绕 y 轴、从上往下看顺时针为正。yaw=θ 时模型正面（-y）朝 (-sinθ, 0, -cosθ)，坐垫上「人面朝」的方向（+y）朝 (sinθ, 0, cosθ)。
# 殿内地面（金砖）顶面 y = 0.72；天花支条底 y = 5.9（宫灯、幡的原点是挂点，挂在支条交叉处的金轱辘下面：x = 0.66k，z = 14.75 + 0.65k）。
# 避开了大殿的四根金柱 (±2.8, 15.4)、(±2.8, 18.0)（柱半径 0.22、柱础半宽 0.33）、两道天花梁（z 15.4、18.0，梁底 y 5.35）、往里开的门扇。
# 留出来的通道（玩家自动走路时 CharacterController 是关着的，所以这里一定要空）：
#   - 中间过道 x -1.7..1.7；正中供桌前 z 18.2..18.8 一条（上香时站 z 18.4、往前一步到 z 18.6 插香）；
#   - 去两边拜垫的横道：z 18.25..18.85、x 1.6..3.3（西边对称），金柱础在 z ≤ 18.33、侧供桌桌围在 z ≥ 19.04。
# 这张表只是给 Unity 那边（BuildIslet.cs）照着摆的，Blender 里不用；hall_props 的预览脚本也按它摆。
LAYOUT = [
    # 佛坛：x -5.8..5.8、z 20.0..21.95，顶面 y 1.57
    ('altar_dais', (0.0, 0.72, 20.975), 0, 1.0),
    # 供桌：中间一张、两边各一张（台面黄缎 y 1.504）
    ('altar_table', (0.0, 0.72, 19.2), 0, 1.0),
    ('altar_table_side', (-3.6, 0.72, 19.35), 0, 1.0),
    ('altar_table_side', (3.6, 0.72, 19.35), 0, 1.0),
    # 中间供桌上的五供：香炉居中靠前（香灰正中世界 (0, 1.682, 19.0)），烛台一对、花觚一对；香炉后面两盏长明灯
    ('censer_hall', (0.0, 1.504, 19.0), 0, 1.0),
    ('candlestick', (-0.52, 1.504, 19.15), 0, 1.0),
    ('candlestick', (0.52, 1.504, 19.15), 0, 1.0),
    ('flower_vase', (-0.94, 1.504, 19.22), 0, 1.0),
    ('flower_vase', (0.94, 1.504, 19.22), 0, 1.0),
    ('oil_lamp', (-0.24, 1.504, 19.4), 0, 1.0),
    ('oil_lamp', (0.24, 1.504, 19.4), 0, 1.0),
    # 两边供桌：小一号的香炉（0.75 倍）、一对烛台（0.8 倍）、果盘（外侧苹果橘子、里侧寿桃）、一盏长明灯
    ('censer_hall_side', (-3.6, 1.504, 19.22), 0, 0.75),
    ('candlestick', (-4.15, 1.504, 19.35), 0, 0.8),
    ('candlestick', (-3.05, 1.504, 19.35), 0, 0.8),
    ('fruit_plate', (-3.88, 1.504, 19.45), 0, 1.0),
    ('fruit_plate_peach', (-3.32, 1.504, 19.45), 0, 1.0),
    ('oil_lamp', (-3.6, 1.504, 19.55), 0, 1.0),
    ('censer_hall_side', (3.6, 1.504, 19.22), 0, 0.75),
    ('candlestick', (3.05, 1.504, 19.35), 0, 0.8),
    ('candlestick', (4.15, 1.504, 19.35), 0, 0.8),
    ('fruit_plate_peach', (3.32, 1.504, 19.45), 0, 1.0),
    ('fruit_plate', (3.88, 1.504, 19.45), 0, 1.0),
    ('oil_lamp', (3.6, 1.504, 19.55), 0, 1.0),
    # 拜垫 0.62 × 0.75（顶面 y 0.844）：中间三个往后挪到 z 17.8（规格是 18.25；挪开以后供桌前空出 z 18.18..18.82 给上香），
    # 两边的到 z 18.5（规格 18.6；垫子加深了，往前会顶到侧供桌）
    ('kneel_mat', (-1.0, 0.72, 17.8), 0, 1.0),
    ('kneel_mat', (0.0, 0.72, 17.8), 0, 1.0),
    ('kneel_mat', (1.0, 0.72, 17.8), 0, 1.0),
    ('kneel_mat', (-3.6, 0.72, 18.5), 0, 1.0),
    ('kneel_mat', (3.6, 0.72, 18.5), 0, 1.0),
    # 磬、木鱼：东边侧供桌外头那一块空地（x 4.35..6.4、z 18.3..19.6：禅修坐垫北边、侧供桌和东墙之间），正面朝南；
    # 敲的人站在 z ≈ 18.45 面朝北。不挡金柱之间进出禅修区的口子，也不挡去侧拜垫的横道
    ('qing', (5.0, 0.72, 18.95), 0, 1.0),
    ('muyu', (5.8, 0.72, 18.95), 0, 1.0),
    # 功德箱：进门东边、过道旁，正面朝过道（西）；往北挪到 z 15.5，南头离折起来的门扇（x 1.6..1.82、z ≤ 14.99）13 厘米，进门就看得见整块「功德」牌
    ('donation_box', (1.45, 0.72, 15.5), 90, 1.0),   # 门里偏西（BuildHall 摆在 x 1.45）：以前在 2.1，正挡着东门
    # 经案：西边侧供桌外头那一块空地（和磬、木鱼对称），正面朝南，念经的人站在 (-5.35, 18.42) 面朝北（佛坛那边）
    ('sutra_desk', (-5.35, 0.72, 18.95), 0, 1.0),
    # 宫灯 4 盏（挂在支条交叉处 y 5.9，灯片中心 y 4.54，灯底大约 y 3.57）：前一对在藻井两旁 (±1.98, 16.7)；
    # 后一对在中间供桌和侧供桌之间的上方，往外挪到 x ±2.64（从殿门、过道看过去不再挡红幡上的字）
    ('palace_lantern', (-1.98, 5.9, 16.7), 0, 1.0),
    ('palace_lantern', (1.98, 5.9, 16.7), 0, 1.0),
    ('palace_lantern', (-2.64, 5.9, 19.3), 0, 1.0),
    ('palace_lantern', (2.64, 5.9, 19.3), 0, 1.0),
    # 幡 4 面（挂在支条交叉处，幡脚大约 y 3.11）：佛坛前，红的两面在中尊两旁、黄的两面在两尊侧佛外边。
    # 对联：上联末字仄声、挂在右边（面朝佛坛时的右手 = 东），下联末字平声、挂在左边（西）。
    # 红幡 东「法轮常转」（转，仄）/ 西「佛日增辉」（辉，平）；黄幡 东「风调雨顺」（顺，仄）/ 西「国泰民安」（安，平）
    ('banner_b', (1.98, 5.9, 19.95), 0, 1.0),
    ('banner', (-1.98, 5.9, 19.95), 0, 1.0),
    ('banner_gold', (5.28, 5.9, 19.95), 0, 1.0),
    ('banner_gold_b', (-5.28, 5.9, 19.95), 0, 1.0),
    # 月台两侧的太平缸
    ('water_vat', (-9.2, 0.07, 5.5), 0, 1.0),
    ('water_vat', (9.2, 0.07, 5.5), 0, 1.0),
] + [('cushion_hall', (sx * x, 0.72, z), 90 if sx < 0 else -90, 1.0)     # 禅修坐垫 16 个：西边一组面朝东、东边一组面朝西
     for sx in (-1, 1) for x in (4.55, 5.65) for z in (15.05, 15.95, 16.85, 17.75)]


ASSETS = {
    'kneel_mat': kneel_mat, 'cushion_hall': cushion_hall, 'altar_table': altar_table, 'altar_table_side': altar_table_side,
    'censer_hall': censer_hall, 'candlestick': candlestick, 'flower_vase': flower_vase, 'fruit_plate': fruit_plate,
    'fruit_plate_peach': fruit_plate_peach, 'oil_lamp': oil_lamp,
    'altar_dais': altar_dais, 'palace_lantern': palace_lantern, 'banner': banner, 'banner_b': banner_b, 'banner_gold': banner_gold,
    'banner_gold_b': banner_gold_b, 'censer_hall_side': censer_hall_side,
    'qing': qing, 'muyu': muyu, 'sutra_desk': sutra_desk, 'donation_box': donation_box, 'water_vat': water_vat,
}
