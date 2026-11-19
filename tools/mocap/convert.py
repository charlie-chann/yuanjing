"""在 Blender 里把 BVH 动捕截一段、导出成 FBX（Unity 按人形骨骼导入，再套到所有动漫人物身上）。
用法：blender -b --factory-startup --python tools/mocap/convert.py -- <清单.txt>
清单每行：片段名 BVH路径 起始秒 结束秒 （# 开头是注释）
输出：unity/Sanctuary/Assets/Motion/<片段名>.fbx
CMU 的 BVH 第 0 帧是 T 字姿势，正好当人形骨骼的基准姿势；截取的片段里不能带它。"""
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
OUT = os.path.join(ROOT, 'unity', 'Sanctuary', 'Assets', 'Motion')
os.makedirs(OUT, exist_ok=True)
lst = [a for a in sys.argv[sys.argv.index('--') + 1:] if not a.startswith('--')][0]
for line in open(lst):
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    name, path, t0, t1 = line.split()[:4]
    t0, t1 = float(t0), float(t1)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_anim.bvh(filepath=os.path.join(ROOT, path), global_scale=0.01, frame_start=0, use_fps_scale=False,
                            update_scene_fps=True, update_scene_duration=True, rotate_mode='NATIVE', axis_forward='-Z', axis_up='Y')
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    sc = bpy.context.scene
    fps = sc.render.fps / sc.render.fps_base
    act = arm.animation_data.action
    f0, f1 = int(round(t0 * fps)), int(round(t1 * fps))
    # 把片段挪到从第 1 帧开始，前面放一帧 T 字姿势（第 0 帧）给 Unity 做人形基准
    for fc in act.fcurves:
        pts = fc.keyframe_points
        vals = {int(round(p.co.x)): p.co.y for p in pts}
        rest = vals.get(0, pts[0].co.y)
        keep = [(f - f0 + 1, vals[f]) for f in range(f0, f1 + 1) if f in vals]
        while len(pts):
            pts.remove(pts[0], fast=True)
        pts.insert(0, rest)
        for f, v in keep:
            pts.insert(f, v)
        fc.update()
    act.name = name
    sc.frame_start, sc.frame_end = 1, f1 - f0 + 1
    arm.name = 'Armature'
    # --ref0（locomotion.py 用）：第 0 帧（加工过的标准 T 字）也导进动画里，而且导出时停在这一帧。
    # 只有骨架、没有蒙皮的 FBX 没有绑定姿势，Unity 拿动画的第一帧当人形基准：从第 0 帧导才是 T 字
    # （从第 1 帧导，基准就成了走路的第一帧：右脚在蹬地、脚尖朝下，套到人物上右脚就一直翘着脚尖走）。
    # 片段本身从第 1 帧起（CharacterImport 把 firstFrame 设成 1）。
    # 不加时和以前一样从第 1 帧导（clips.txt 里的待机等沿用原来的基准）
    if '--ref0' in sys.argv:
        sc.frame_start = 0
        sc.frame_set(0)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, name + '.fbx'), use_selection=True, apply_scale_options='FBX_SCALE_UNITS',
                             object_types={'ARMATURE'}, add_leaf_bones=False, bake_anim=True, bake_anim_use_all_actions=False,
                             bake_anim_use_nla_strips=False, bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0,
                             axis_forward='-Z', axis_up='Y')
    print(f'[mocap] {name}: {t1 - t0:.2f} 秒，{f1 - f0 + 1} 帧，{fps:.0f} 帧/秒')
