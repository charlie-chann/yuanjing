"""把 VRM 动漫人物（VRoid 导出的那种）转成 Unity 现有人物管线能用的 FBX。

VRM 其实是带扩展信息的 glb：Blender 能直接读网格、骨骼、表情形变和贴图，这里再把扩展里的
材质参数（暗面颜色、描边粗细、透明方式）、表情名字、人形骨骼对应、头发裙摆的摆动骨骼读出来，写成一份说明给 Unity。

用法：blender -b --factory-startup --python tools/blender/vrm_import.py -- <文件.vrm> <名字>
输出：unity/Sanctuary/Assets/Characters/Anime/<名字>/<名字>.fbx、Textures/*.png、<名字>.json
"""
import json
import os
import shutil
import struct
import sys
import tempfile

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
src, name = sys.argv[sys.argv.index('--') + 1:][:2]
out = os.path.join(HERE, '..', '..', 'unity', 'Sanctuary', 'Assets', 'Characters', 'Anime', name)
os.makedirs(os.path.join(out, 'Textures'), exist_ok=True)

with open(src, 'rb') as f:
    f.read(12)
    n, _ = struct.unpack('<II', f.read(8))
    gltf = json.loads(f.read(n))
vrm = gltf['extensions']['VRM']
nodes = gltf['nodes']
images = gltf.get('images', [])
textures = gltf.get('textures', [])

tmp = os.path.join(tempfile.mkdtemp(), name + '.glb')
shutil.copy(src, tmp)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=tmp)

# 多余的东西：碰撞球的示意、空物体
for o in list(bpy.data.objects):
    if o.type == 'MESH' and not o.data.materials:
        bpy.data.objects.remove(o)
    elif o.type == 'EMPTY':
        bpy.data.objects.remove(o)

# 贴图存成 PNG（名字用 glb 里图片的名字）
img_file = {}
for i, im in enumerate(images):
    nm = im.get('name') or f'image_{i}'
    b = bpy.data.images.get(nm)
    if b is None:
        continue
    path = os.path.join(out, 'Textures', nm + '.png')
    b.filepath_raw = path
    b.file_format = 'PNG'
    b.save()
    img_file[i] = nm + '.png'


def tex_file(ti):
    if ti is None or ti < 0 or ti >= len(textures):
        return None
    return img_file.get(textures[ti].get('source'))


mats = []
for m in vrm['materialProperties']:
    fp, vp, tp = m['floatProperties'], m['vectorProperties'], m['textureProperties']
    mats.append({
        'name': m['name'],
        'tex': tex_file(tp.get('_MainTex')),
        'shadeTex': tex_file(tp.get('_ShadeTexture')),
        'color': vp.get('_Color', [1, 1, 1, 1]),
        'shade': vp.get('_ShadeColor', [0.8, 0.8, 0.9, 1]),
        'outline': fp.get('_OutlineWidth', 0),
        'outlineColor': vp.get('_OutlineColor', [0, 0, 0, 1]),
        'blend': int(fp.get('_BlendMode', 0)),          # 0 不透明 1 镂空 2 半透明 3 半透明且写深度
        'cutoff': fp.get('_Cutoff', 0.5),
        'cull': int(fp.get('_CullMode', 2)),            # 0 两面都画 2 只画正面
        'queue': m.get('renderQueue', -1),
    })

# 表情：把形变的名字从 target_N 改成 VRM 里的表情名（一个表情只动一个形变的那些）
face_keys = {}
mesh_objs = {}
for o in bpy.data.objects:
    if o.type == 'MESH':
        mesh_objs[o.data.name] = o
gl_meshes = gltf['meshes']
expr = {}
for g in vrm['blendShapeMaster']['blendShapeGroups']:
    binds = g.get('binds', [])
    expr[g['name']] = [{'mesh': gl_meshes[b['mesh']]['name'], 'index': b['index'], 'weight': b['weight']} for b in binds]
for o in bpy.data.objects:
    if o.type == 'MESH' and o.data.shape_keys:
        kb = o.data.shape_keys.key_blocks
        for gname, binds in expr.items():
            if len(binds) == 1 and binds[0]['weight'] >= 99:
                k = kb.get(f"target_{binds[0]['index']}")
                if k is not None:
                    k.name = gname

# 人形骨骼对应、会摆动的骨骼（头发、裙摆、胸）
human = {b['bone']: nodes[b['node']]['name'] for b in vrm['humanoid']['humanBones']}
springs = []
for g in vrm['secondaryAnimation']['boneGroups']:
    springs.append({'stiff': g.get('stiffiness', 1.0), 'gravity': g.get('gravityPower', 0.0), 'drag': g.get('dragForce', 0.4),
                    'radius': g.get('hitRadius', 0.02), 'roots': [nodes[i]['name'] for i in g.get('bones', [])]})

meta = {k: v for k, v in vrm['meta'].items() if k != 'texture'}
# 每个网格的材质顺序（Unity 导入 FBX 后按这个顺序把材质对上）
meshes = [{'name': o.name, 'materials': [m.name for m in o.data.materials]} for o in bpy.data.objects if o.type == 'MESH']
json.dump({'name': name, 'meta': meta, 'materials': mats, 'meshes': meshes, 'human': human, 'springs': springs, 'expressions': expr},
          open(os.path.join(out, name + '.json'), 'w'), ensure_ascii=False, indent=1)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.fbx(filepath=os.path.join(out, name + '.fbx'), use_selection=True, apply_scale_options='FBX_SCALE_UNITS',
                         object_types={'ARMATURE', 'MESH'}, add_leaf_bones=False, bake_anim=False, mesh_smooth_type='FACE',
                         use_armature_deform_only=False, path_mode='STRIP', axis_forward='-Z', axis_up='Y')
tris = sum(len(o.data.loop_triangles) or sum(len(p.vertices) - 2 for p in o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')
print(f'[vrm] {name}: {tris} 三角形，{len(mats)} 个材质，{len(human)} 根人形骨骼，{len(springs)} 组摆动骨骼，授权 {meta.get("licenseName")}')
