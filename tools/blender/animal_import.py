"""把现成的带骨骼动作的狗（Quaternius 的柴犬、哈士奇，CC0）加工成岛上的六只小动物，导出 FBX 给 Unity。

同一副骨架、同一套十二段动作，靠改网格的形状变成不同的动物（只动没摆姿势时的网格，骨头不动，动作照样能用）：
  泰迪：耳朵垂下来、嘴变短、脑袋圆一圈、尾巴缩成一团
  猫：扁脸、耳朵竖着、腿和身子细一些、尾巴拉长变细，加几根胡须
然后：焊顶点、细分一次（轮廓圆滑），颜色画进顶点色（虎斑纹、三花的斑块、白肚皮），
顶点色第四个数记「这里的毛多长」（眼睛鼻子没有毛，脸和脚短，身上正常，尾巴最长）。
毛是 Unity 那边一层层套上去的（Editor/BuildFur.cs、Shaders/YJFur.shader）。

用法：blender -b --factory-startup --python tools/blender/animal_import.py -- <文件.glb> <名字> <样子>
样子：shiba teddy cotton tabby white calico
输出：unity/Sanctuary/Assets/Critters/<名字>/<名字>.fbx
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[sys.argv.index('--') + 1:]
src, name, look = args[0], args[1], args[2]
out = os.path.join(HERE, '..', '..', 'unity', 'Sanctuary', 'Assets', 'Critters', name)
os.makedirs(out, exist_ok=True)
CAT = look in ('tabby', 'white', 'calico', 'black', 'liHua')

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
for o in list(bpy.data.objects):
    if o.type == 'EMPTY' or (o.type == 'MESH' and not o.data.materials):
        bpy.data.objects.remove(o)
for a in list(bpy.data.actions):
    if '|' in a.name:
        bpy.data.actions.remove(a)
ob = next(o for o in bpy.data.objects if o.type == 'MESH')
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
me = ob.data
groups = {g.index: g.name for g in ob.vertex_groups}
MW, MWi = ob.matrix_world.copy(), ob.matrix_world.inverted()
bone = {b.name: arm.matrix_world @ b.head_local for b in arm.data.bones}
mats = [m.name for m in me.materials]

# ── 焊顶点（原模型每个三角形各有各的顶点） ──
bpy.context.view_layer.objects.active = ob
ob.select_set(True)
size = max(ob.dimensions) / max(1e-9, max(ob.scale))
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=size * 1e-4)
bpy.ops.object.mode_set(mode='OBJECT')


def owner(v):
    best, bw = '', 0
    for g in v.groups:
        if g.weight > bw:
            best, bw = groups.get(g.group, ''), g.weight
    return best


def weight(v, prefix):
    return sum(g.weight for g in v.groups if groups.get(g.group, '').startswith(prefix))


# ── 改形状（世界坐标：头朝 -y，上是 z） ──
head = bone['Head']
ear = {s: bone[f'Ear1.{s}'] for s in 'LR'}
tail0 = bone['Tail1']
TAIL = [(arm.matrix_world @ arm.data.bones[n].head_local, arm.matrix_world @ arm.data.bones[n].tail_local) for n in ('Tail1', 'Tail2', 'Tail3')]
# 骨头的尾巴点（Blender 里的骨头很短），用下一根的起点代替
TAIL = [(TAIL[i][0], TAIL[i + 1][0] if i + 1 < len(TAIL) else TAIL[i][0] + (TAIL[i][0] - TAIL[i - 1][0])) for i in range(len(TAIL))]
tail_dir = (bone['Tail3'] - bone['Tail1']).normalized()
for v in me.vertices:
    w = MW @ v.co
    o = owner(v)
    hw = weight(v, 'Head') + weight(v, 'Ear')
    if look == 'teddy':
        if hw > 0.3:
            # 嘴变短：眼睛前面的那截往回压
            front = head.y - 0.22
            if w.y < front:
                w.y = front + (w.y - front) * 0.5
                w.z = w.z + (head.z + 0.05 - w.z) * 0.15
            # 脑袋圆一圈
            w = head + (w - head) * 1.12
        ew = weight(v, 'Ear')
        if ew > 0.35:
            s = 'L' if (w.x > 0) else 'R'
            sg = 1 if s == 'L' else -1
            p = ear[s] + Vector((0, 0, 0.02))
            # 绕前后方向转下去：耳朵垂在脑袋两边，再宽一点（按耳朵骨头的权重过渡，耳根不会撕开）
            k = min(1.0, (ew - 0.35) * 2.5)
            q = Matrix.Rotation(math.radians(135) * sg * k, 4, "Y")
            r = q @ (w - p)
            r.y *= 1 + 0.5 * k
            r.x *= 1 + 0.25 * k
            w = p + r + Vector((sg * 0.06, 0.02, -0.04)) * k
        if o.startswith('Tail'):
            w = tail0 + (w - tail0) * 0.45
    elif CAT:
        if hw > 0.3 and not o.startswith('Ear'):
            front = head.y - 0.18
            if w.y < front:
                w.y = front + (w.y - front) * 0.32       # 扁脸
            w = head + (w - head) * 1.16
        if o.startswith('Ear'):
            e = ear['L' if o.endswith('.L') else 'R']
            w = head + (e - head) * 1.16 + (w - e) * 1.3
        if o.startswith('Tail'):
            # 尾巴：找每个点在哪根尾巴骨头上
            best = None
            for bi, (h0, h1) in enumerate(TAIL):
                seg = h1 - h0
                k = max(0.0, min(1.0, (w - h0).dot(seg) / seg.length_squared))
                d = (w - (h0 + seg * k)).length
                if best is None or d < best[0]:
                    best = (d, bi, k, w - (h0 + seg * k))
            # 弯法不动（竖起来的问号尾巴），只是细一半、长三成
            _, bi, k, perp = best
            h0, h1 = TAIL[bi]
            c = tail0 + (h0 + (h1 - h0) * k - tail0) * 1.3
            w = c + perp * 0.5
        if 'Leg' in o or o.startswith(('FF', 'IK')):
            w.x *= 0.86
        if o.startswith(('Torso', 'Body', 'Back', 'Neck')):
            w.x *= 0.86
        # 腿短一截、身子放低：脚还踩在地上（腿上的点按高度压，身上的点整体往下挪，关节处按权重过渡）
        legw = min(1.0, weight(v, 'Front') + weight(v, 'Back') - weight(v, 'Back') * (1 if not any(groups.get(g.group, '').startswith('BackLeg') or groups.get(g.group, '').startswith('BackUpper') or groups.get(g.group, '').startswith('BackLower') or groups.get(g.group, '').startswith('BackShoulder') for g in v.groups) else 0) + weight(v, 'FF') + weight(v, 'IK'))
        drop = 0.62
        k = (1.75 - drop) / 1.75
        w.z = (w.z - drop) * (1 - legw) + (w.z * k) * legw
    v.co = MWi @ w


# ── 颜色和毛长 ──
def fur_len(o):
    if o.startswith('Tail'):
        return 1.6 if look in ('teddy', 'cotton') else 1.4
    if o.startswith(('Head', 'Ear')):
        return 0.9 if look == 'teddy' else 0.5
    if 'LowerLeg' in o or o.startswith(('FF', 'IK')):
        return 0.8 if look == 'teddy' else 0.35
    if 'Leg' in o:
        return 0.9 if look == 'teddy' else 0.6
    if o.startswith('Neck'):
        return 1.3
    return 1.0


ORANGE, CREAM, BLACK = (0.88, 0.58, 0.3), (0.98, 0.95, 0.88), (0.1, 0.08, 0.08)
EYE = {'Eyes_White': (0.95, 0.95, 0.95), 'Eyes_Pupil': (0.16, 0.09, 0.05), 'Eyes_Black': (0.03, 0.025, 0.025)}


def colour(mat, w, n):
    if mat in EYE:
        c = EYE[mat]
        if CAT and mat == 'Eyes_Pupil':
            c = (0.45, 0.7, 0.86) if look == 'white' else (0.86, 0.7, 0.16) if look == 'black' else (0.72, 0.6, 0.18)
        return c, 0.0
    if mat == 'Black':
        return ((0.56, 0.36, 0.36) if CAT and look != "calico" else BLACK), 0.0       # 鼻头（猫是粉的）
    light = mat == 'Main_Light'
    if look == 'shiba':
        return (CREAM if light else ORANGE), None
    if look == 'kuro':
        # 黑柴：背上黑、腿和脸颊黄褐、胸口白；眼睛上方两个黄眉点
        if light:
            return CREAM, None
        if w.z > 1.6 and abs(w.x) < 0.42:
            return (0.12, 0.1, 0.1), None
        brow = any((w - Vector((sx * 0.13, head.y - 0.12, head.z + 0.1))).length < 0.07 for sx in (-1, 1))
        return ((0.82, 0.55, 0.28) if brow or w.z < 1.25 else (0.16, 0.13, 0.12)), None
    if look == 'dango':
        # 灰白长毛犬：背上灰、肚子和脸白
        return ((0.97, 0.97, 0.96) if light else (0.58, 0.58, 0.6)), None
    if look == 'teddy':
        base = (0.66, 0.4, 0.24)
        k = noise.noise(w * 6.0) * 0.06
        return tuple(min(1, max(0, x + k)) for x in base), None
    if look == 'cotton':
        return ((0.99, 0.98, 0.96) if light else (0.96, 0.95, 0.93)), None
    # 猫：肚子、胸前、脚是白的（原模型浅色的那块），其余按花色
    if look == 'white':
        return (0.98, 0.97, 0.95), None
    if look == 'black':
        return (0.09, 0.08, 0.085), None
    if look == 'liHua':
        # 狸花：棕灰底，黑色条纹，肚子浅
        if light:
            return (0.86, 0.8, 0.7), None
        s_ = math.sin(w.y * 13 + noise.noise(w * 3) * 2.5)
        return ((0.22, 0.19, 0.16) if s_ > 0.3 else (0.55, 0.47, 0.37)), None
    if light:
        return CREAM, None
    if look == 'tabby':
        # 虎斑：沿身体一圈圈的深色条纹，背上一道深脊线，脸上额头几道
        s = math.sin(w.y * 14 + noise.noise(w * 3) * 2.2)
        c = ORANGE
        if s > 0.35:
            c = (0.66, 0.36, 0.16)
        if abs(w.x) < 0.07 and w.z > 1.75:
            c = (0.62, 0.32, 0.14)
        return c, None
    # 三花：白底上一块块橘色和黑色
    k = noise.noise(w * 1.6 + Vector((3.1, 0, 0)))
    if k > 0.18:
        return ORANGE, None
    if k < -0.22:
        return (0.14, 0.12, 0.12), None
    return CREAM, None


col = me.color_attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
for poly in me.polygons:
    mat = mats[poly.material_index]
    n = MW.to_3x3() @ poly.normal
    for li in poly.loop_indices:
        v = me.vertices[me.loops[li].vertex_index]
        w = MW @ v.co
        c, f = colour(mat, w, n)
        if f is None:
            f = fur_len(owner(v))
        col.data[li].color = (c[0], c[1], c[2], f / 2)
    poly.use_smooth = True
me.color_attributes.active_color = col
me.color_attributes.render_color_index = me.color_attributes.find('Col')
one = bpy.data.materials.new('fur')
for poly in me.polygons:
    poly.material_index = 0
me.materials.clear()
me.materials.append(one)

# ── 猫的胡须：每边四根，整根绑在头上，毛长 0（不长毛） ──
if CAT:
    bm = bmesh.new()
    bm.from_mesh(me)
    cl = bm.loops.layers.float_color['Col']
    dl = bm.verts.layers.deform.verify()
    hg = next(i for i, n in groups.items() if n == 'Head')
    nose = Vector((0, head.y - 0.3, head.z - 0.08))
    for sg in (1, -1):
        for k in range(4):
            root = nose + Vector((sg * 0.09, 0.03, -0.02 - 0.025 * k))
            d = Vector((sg * 1.0, 0.25 + 0.1 * k, 0.12 - 0.12 * k)).normalized()
            ln = 0.55 - 0.05 * k
            side = Vector((0, 0, 1)).cross(d).normalized() * 0.006
            pts = [root + d * (ln * t) + Vector((0, 0, -0.06 * t * t)) for t in (0, 0.5, 1.0)]
            vs = []
            for i, p in enumerate(pts):
                wid = 1 - 0.8 * i / 2
                for s2 in (-1, 1):
                    vv = bm.verts.new(MWi @ (p + side * s2 * wid))
                    vv[dl][hg] = 1.0
                    vs.append(vv)
            for i in range(2):
                f = bm.faces.new((vs[i * 2], vs[i * 2 + 1], vs[i * 2 + 3], vs[i * 2 + 2]))
                for l in f.loops:
                    l[cl] = (0.96, 0.95, 0.92, 0.0)
    bm.to_mesh(me)
    bm.free()

# 细分一次：排到骨骼变形前面再应用，权重和顶点色都跟着插值
sub = ob.modifiers.new('sub', 'SUBSURF')
sub.levels = 1
bpy.ops.object.modifier_move_to_index(modifier='sub', index=0)
bpy.ops.object.modifier_apply(modifier='sub')

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.fbx(filepath=os.path.join(out, name + '.fbx'), use_selection=True, apply_scale_options='FBX_SCALE_UNITS',
                         object_types={'ARMATURE', 'MESH'}, add_leaf_bones=False, mesh_smooth_type='FACE', colors_type='LINEAR',
                         bake_anim=True, bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False, bake_anim_use_all_bones=True,
                         bake_anim_simplify_factor=0.3, path_mode='STRIP', axis_forward='-Z', axis_up='Y')
print(f'[animal] {name}（{look}）：{len(me.vertices)} 个顶点，{len(arm.data.bones)} 根骨头')

# 预览：摆个侧面看形状和花色
if os.environ.get('YJ_PREVIEW', '1') != '0':
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE_NEXT'
    sc.render.resolution_x = sc.render.resolution_y = 700
    m = bpy.data.materials.new('pv')
    m.use_nodes = True
    nt = m.node_tree
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name = 'Col'
    nt.links.new(at.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
    me.materials[0] = m
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = (3.4, -4.6, 3.0)
    cam.rotation_euler = (Vector((0, -0.6, 1.6)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 3
    sun.rotation_euler = (0.7, 0.2, 0.6)
    sc.collection.objects.link(sun)
    w = bpy.data.worlds.new('w')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.7, 0.75, 0.8, 1)
    sc.world = w
    sc.render.filepath = os.path.join(HERE, 'preview', f'pet_{name}.png')
    bpy.ops.render.render(write_still=True)
