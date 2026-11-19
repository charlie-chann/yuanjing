"""合掌、鞠躬、跪拜、盘坐（关键帧动作）：在 Shino 的骨架上按真人的骨骼结构摆出来，导出成人形动作，所有动漫人物共用。

为什么自己做：免登录又能商用的动捕库里没有寺庙礼拜的动作（CMU 的 Bow 是谢幕式挥手鞠躬，跪下是单膝安慰人）。

怎么做得自然：
- 腿、手臂是两段骨的 IK：给脚踝、手腕定位置，膝盖、肘按「往哪边弯」算出来，关节长度不变；脚和手掌的朝向单独给。
- 合掌时手腕的位置是「相对胸口」给的：身体前倾，手跟着胸口走，不会留在原地。
- 前臂负责翻手腕（真人就是前臂旋转），手腕只管指向。
- 脊柱分三节、脖子、头各弯一点，加起来才是总弯度；头比身体晚 0.1 秒到位，手比身体早一点（动作的先后）。
- 所有保持的姿势都叠呼吸（胸口一起一伏、肩微微动）。手指单独一层：合掌并拢伸直，平时自然微屈。
- 时间曲线用缓入缓出（smootherstep），不是匀速。

坐标：人朝 +y，右手边 +x，上 +z，地面 z=0（跪、坐的动作地面就是蒲团面）。长度单位米，按 Shino 的身材（1.55 米）。

用法：blender -b --factory-startup --python tools/blender/pray_motions.py -- [片段名 ...]
输出：unity/Sanctuary/Assets/Motion/<片段名>.fbx，片段名约定：*_Loop 循环；*_Scrub 由游戏按 0..1 的进度拖着播（鞠躬的深浅）
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
SRC = os.path.join(ROOT, 'unity', 'Sanctuary', 'Assets', 'Characters', 'Anime', 'shino', 'shino.fbx')
OUT = os.path.join(ROOT, 'unity', 'Sanctuary', 'Assets', 'Motion')
FPS = 30
PAD = 3          # 片段前后多导的帧数（见 build；CharacterImport.WalkPad）

X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


def rot(axis, deg):
    return Quaternion(Vector(axis).normalized(), math.radians(deg))


def frame_rot(d0, n0, d1, n1):
    """把 (方向 d0, 参考 n0) 转到 (方向 d1, 参考 n1) 的旋转"""
    def basis(d, n):
        d = d.normalized()
        n = (n - d * n.dot(d))
        if n.length < 1e-6:
            n = d.orthogonal()
        n.normalize()
        return Matrix((d, n, d.cross(n))).transposed()
    return (basis(d1, n1) @ basis(d0, n0).transposed()).to_quaternion()


def smoother(t):
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (t * 6 - 15) + 10)


class Rig:
    def __init__(self, arm):
        self.arm = arm
        self.bones = {b.name: b for b in arm.data.bones}
        self.head = {n: b.head_local.copy() for n, b in self.bones.items()}
        self.B = {n: b.matrix_local.to_3x3().to_quaternion() for n, b in self.bones.items()}
        self.parent = {n: (b.parent.name if b.parent else None) for n, b in self.bones.items()}
        self.order = [b.name for b in arm.data.bones]          # 父在子前
        self.children = {n: [] for n in self.bones}
        for n, p in self.parent.items():
            if p:
                self.children[p].append(n)

    def J(self, s):
        return 'J_Bip_' + s

    def length(self, a, b):
        return (self.head[self.J(b)] - self.head[self.J(a)]).length


def two_bone(H, T, L1, L2, pole):
    """两段骨 IK：根在 H、末端要到 T，中间的关节往 pole 那边弯。返回中间关节的位置"""
    v = T - H
    d = min(v.length, (L1 + L2) * 0.999)
    u = v.normalized()
    a = (L1 * L1 - L2 * L2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, L1 * L1 - a * a))
    p = pole - u * pole.dot(u)
    if p.length < 1e-6:
        p = u.orthogonal()
    p.normalize()
    return H + u * a + p * h, H + u * d


class Pose(dict):
    """一个姿势的参数（都有默认值，见 BASE）"""
    def copy(self):
        return Pose({k: (v.copy() if hasattr(v, 'copy') else v) for k, v in self.items()})


BASE = {
    'hips': Vector((0, 0.007, 0.935)), 'hips_pitch': 0.0, 'hips_roll': 0.0, 'hips_yaw': 0.0,
    'spine': 0.0, 'chest': 0.0, 'upper': 0.0, 'neck': 0.0, 'headp': 0.0, 'head_yaw': 0.0, 'head_roll': 0.0, 'side': 0.0,
    'sh_fwd': 0.0, 'sh_up': 0.0,
    # 手腕的位置：hand_space='chest' 时是相对胸口（UpperChest）静止时的坐标，'world' 时是相对地面
    'hand_space': 1.0,       # 1 胸口，0 地面（可以插值，手从体侧挪到胸前时平滑换参照）
    'wl': Vector((-0.17, 0.03, 0.88)), 'wr': Vector((0.17, 0.03, 0.88)),
    'pl': Vector((1, -0.2, 0)), 'pr': Vector((-1, -0.2, 0)),             # 手掌朝哪
    'fl': Vector((0, 0.1, -1)), 'fr': Vector((0, 0.1, -1)),               # 手指朝哪
    'el': Vector((-0.6, -1, -0.2)), 'er': Vector((0.6, -1, -0.2)),       # 肘往哪边弯
    'curl': 18.0, 'thumb': 15.0, 'spread': 4.0,
    # 脚踝：两脚分开的宽度和站着的待机（动捕）一样（游戏里约 0.15 米），从待机换到合掌、上香时脚不在地上横着滑
    'al': Vector((-0.093, -0.027, 0.105)), 'ar': Vector((0.093, -0.027, 0.105)),     # 脚踝
    'tl': Vector((0, 1, -0.55)), 'tr': Vector((0, 1, -0.55)),                         # 脚尖朝哪
    'ul': Vector((0, 0.5, 1)), 'ur': Vector((0, 0.5, 1)),                             # 脚背朝哪
    'kl': Vector((0, 1, 0)), 'kr': Vector((0, 1, 0)),                                 # 膝盖朝哪
    'breath': 1.0,
}


def P(**kw):
    p = Pose({k: (v.copy() if hasattr(v, 'copy') else v) for k, v in BASE.items()})
    for k, v in kw.items():
        p[k] = Vector(v) if isinstance(v, tuple) else v
    return p


def lerp_pose(a, b, t):
    out = Pose()
    for k in a:
        va, vb = a[k], b[k]
        if isinstance(va, Vector):
            out[k] = va.lerp(vb, t)
        else:
            out[k] = va + (vb - va) * t
    return out


# 哪些参数属于哪一组：组和组之间错开一点时间（头晚、手早），动作才有先后
GROUP = {'neck': 'head', 'headp': 'head', 'head_yaw': 'head', 'head_roll': 'head',
         'wl': 'hand', 'wr': 'hand', 'pl': 'hand', 'pr': 'hand', 'fl': 'hand', 'fr': 'hand', 'el': 'hand', 'er': 'hand',
         'curl': 'hand', 'thumb': 'hand', 'spread': 'hand', 'hand_space': 'hand'}


def sample(keys, t, lag, wrap=None):
    """keys: [(时刻, 姿势)]。按组错开时间后在相邻两个关键姿势之间缓入缓出地插值。
    wrap：循环片段的长度（错开的时间绕回来，首尾接得上）"""
    out = Pose()
    for k in keys[0][1]:
        tt = t - lag.get(GROUP.get(k, 'body'), 0.0)
        if wrap:
            tt %= wrap
        if tt <= keys[0][0]:
            out[k] = keys[0][1][k]
            continue
        if tt >= keys[-1][0]:
            out[k] = keys[-1][1][k]
            continue
        for (t0, a), (t1, b) in zip(keys, keys[1:]):
            if t0 <= tt <= t1:
                s = smoother((tt - t0) / max(1e-6, t1 - t0))
                va, vb = a[k], b[k]
                out[k] = va.lerp(vb, s) if isinstance(va, Vector) else va + (vb - va) * s
                break
    return out


def solve(rig, p, t):
    """由一组参数算出每根骨头相对静止姿势的旋转（世界方向上的增量 D），以及髋的位置"""
    J = rig.J
    D = {n: Quaternion() for n in rig.bones}
    pos = {}
    # 呼吸：4 秒一次，胸口抬一点、肩微微上提
    br = math.sin(2 * math.pi * t / 4.0) * p['breath']
    hips_pos = p['hips'] + Vector((0, 0, 0.003 * br))
    Dh = rot(Z, p['hips_yaw']) @ rot(Y, p['hips_roll']) @ rot(X, -p['hips_pitch'])
    D[J('C_Hips')] = Dh

    def fk(name, Dparent_name):
        par = rig.parent[name]
        pp = pos[par] if par in pos else rig.head[par] if par else Vector()
        pos[name] = pp + D[par] @ (rig.head[name] - rig.head[par])

    pos[J('C_Hips')] = hips_pos
    if rig.parent[J('C_Hips')]:
        pos[rig.parent[J('C_Hips')]] = rig.head[rig.parent[J('C_Hips')]]

    def chain(name, local):
        par = rig.parent[name]
        D[name] = D[par] @ local
        fk(name, par)

    chain(J('C_Spine'), rot(X, -p['spine']) @ rot(Y, p['side'] * 0.4))
    chain(J('C_Chest'), rot(X, -(p['chest'] - 0.6 * br)) @ rot(Y, p['side'] * 0.3))
    chain(J('C_UpperChest'), rot(X, -(p['upper'] - 0.5 * br)) @ rot(Y, p['side'] * 0.3))
    chain(J('C_Neck'), rot(X, -p['neck']))
    chain(J('C_Head'), rot(Z, p['head_yaw']) @ rot(Y, p['head_roll']) @ rot(X, -p['headp']))

    # 锁骨：往前收、往上提一点
    for s, sg in (('L', -1), ('R', 1)):
        chain(J(f'{s}_Shoulder'), rot(Z, sg * p['sh_fwd']) @ rot(Y, -sg * (p['sh_up'] + 0.6 * br)))

    # 手臂
    uc = J('C_UpperChest')
    for s, sg in (('L', -1), ('R', 1)):
        sh, el, wr, hd = J(f'{s}_UpperArm'), J(f'{s}_LowerArm'), J(f'{s}_Hand'), J(f'{s}_Middle1')
        fk(sh, None)
        S = pos[sh]
        w_rest = p['w' + s.lower()]
        w_chest = pos[uc] + D[uc] @ (w_rest - rig.head[uc])
        Wt = w_rest.lerp(w_chest, p['hand_space'])
        L1, L2 = rig.length(f'{s}_UpperArm', f'{s}_LowerArm'), rig.length(f'{s}_LowerArm', f'{s}_Hand')
        hs = p['hand_space']
        pole = p['e' + s.lower()].lerp(D[uc] @ p['e' + s.lower()], hs)
        E, W = two_bone(S, Wt, L1, L2, pole)
        d0 = rig.head[el] - rig.head[sh]
        d1 = E - S
        # 上臂的「前面」（肘弯向的那一侧）：静止 T 字时是 +y；摆好以后是前臂指过去的方向
        fwd = (W - E) - d1.normalized() * (W - E).dot(d1.normalized())
        if fwd.length < 1e-4:
            fwd = pole
        q_up = frame_rot(d0, Y, d1, fwd)
        D[sh] = q_up
        pos[el] = E
        # 前臂：转手腕的活在这里（真人就是前臂旋转）
        palm = p['p' + s.lower()].lerp(D[uc] @ p['p' + s.lower()], hs)
        D[el] = frame_rot(rig.head[wr] - rig.head[el], -Z, W - E, palm)
        pos[wr] = W
        fing = p['f' + s.lower()].lerp(D[uc] @ p['f' + s.lower()], hs)
        D[wr] = frame_rot(rig.head[hd] - rig.head[wr], -Z, fing, palm)
        # 手指：每节往掌心弯 curl 度（拇指另算），四指略微张开
        axis = Vector((0, sg * 1.0, 0))          # 左手 -y、右手 +y：绕它转是往掌心（-z）弯
        for fi, f in enumerate(('Index', 'Middle', 'Ring', 'Little')):
            spread = (fi - 1.2) * p['spread']
            for k in (1, 2, 3):
                n = J(f'{s}_{f}{k}')
                if n not in rig.bones:
                    continue
                c = p['curl'] * (0.8, 1.15, 0.9)[k - 1] * (1 + 0.12 * fi)
                local = rot(axis, c)
                if k == 1:
                    local = rot(Z, -sg * spread) @ local
                par = rig.parent[n]
                D[n] = D[par] @ local
                fk(n, par)
        for k in (1, 2, 3):
            n = J(f'{s}_Thumb{k}')
            if n not in rig.bones:
                continue
            local = rot(Z, -sg * p['thumb'] * 0.6) @ rot(axis, p['thumb'] * 0.5) if k == 1 else rot(axis, p['thumb'] * 0.4)
            par = rig.parent[n]
            D[n] = D[par] @ local
            fk(n, par)

    # 腿
    for s in ('L', 'R'):
        ul, ll, ft, toe = J(f'{s}_UpperLeg'), J(f'{s}_LowerLeg'), J(f'{s}_Foot'), J(f'{s}_ToeBase')
        fk(ul, None)
        H = pos[ul]
        L1, L2 = rig.length(f'{s}_UpperLeg', f'{s}_LowerLeg'), rig.length(f'{s}_LowerLeg', f'{s}_Foot')
        K, A = two_bone(H, p['a' + s.lower()], L1, L2, p['k' + s.lower()])
        knee_fwd = p['k' + s.lower()]
        D[ul] = frame_rot(rig.head[ll] - rig.head[ul], Y, K - H, knee_fwd)
        D[ll] = frame_rot(rig.head[ft] - rig.head[ll], Y, A - K, knee_fwd)
        d0 = rig.head[toe] - rig.head[ft]
        D[ft] = frame_rot(d0, Z, p['t' + s.lower()], p['u' + s.lower()])
        if toe in rig.bones:
            D[toe] = D[ft]
    return D, hips_pos


def key(rig, D, hips_pos, frame):
    pb = rig.arm.pose.bones
    for n in rig.order:
        if n not in D or rig.parent[n] is None:
            continue
        par = rig.parent[n]
        L = D[par].inverted() @ D[n]
        Bn = rig.B[n]
        q = Bn.inverted() @ L @ Bn
        b = pb[n]
        b.rotation_mode = 'QUATERNION'
        b.rotation_quaternion = q
        b.keyframe_insert('rotation_quaternion', frame=frame)
    hb = pb[rig.J('C_Hips')]
    hb.location = rig.B[rig.J('C_Hips')].inverted() @ (hips_pos - rig.head[rig.J('C_Hips')])
    hb.keyframe_insert('location', frame=frame)


def rest_key(rig, frame):
    for b in rig.arm.pose.bones:
        b.rotation_mode = 'QUATERNION'
        b.rotation_quaternion = Quaternion()
        b.location = Vector()
        b.keyframe_insert('rotation_quaternion', frame=frame)
        b.keyframe_insert('location', frame=frame)


# ───────────── 姿势 ─────────────
# 胸口（UpperChest）静止时在 (0, 0.017, 1.228)。手腕坐标都是「胸口不动时」的位置

STAND = P()
GASSHO = P(wl=(-0.014, 0.19, 1.13), wr=(0.014, 0.19, 1.13), pl=(1, 0, 0), pr=(-1, 0, 0), fl=(0, 0.32, 1), fr=(0, 0.32, 1),
           el=(-1, -0.35, -0.9), er=(1, -0.35, -0.9), curl=3.0, thumb=26.0, spread=0.0, sh_fwd=4.0, neck=3.0, headp=5.0)
GASSHO_MID = P(wl=(-0.12, 0.2, 0.98), wr=(0.12, 0.2, 0.98), pl=(1, 0.2, 0.3), pr=(-1, 0.2, 0.3), fl=(0, 0.5, 0.6), fr=(0, 0.5, 0.6),
               el=(-1, -0.4, -0.8), er=(1, -0.4, -0.8), curl=8.0, thumb=20.0, spread=1.0, sh_fwd=2.0)
GASSHO_LOW = GASSHO.copy()
GASSHO_LOW.update(neck=10.0, headp=20.0, upper=4.0, chest=3.0)


def gassho_bow(deg):
    """站着鞠躬（合掌）：主要从髋部折，背基本直，头顺着脊柱；髋往后坐一点，重心还在脚上"""
    p = GASSHO.copy()
    k = deg / 45.0
    p.update(hips_pitch=deg * 0.72, spine=deg * 0.08, chest=deg * 0.08, upper=deg * 0.06, neck=4 + deg * 0.05, headp=6 + deg * 0.1,
             hips=Vector((0, 0.007 - 0.085 * k, 0.935 - 0.012 * k)), kl=Vector((0, 1, 0)), kr=Vector((0, 1, 0)))
    return p


# 跪：膝盖在蒲团上，大腿竖直（长跪），小腿和脚背平贴在身后
KNEEL_UP = GASSHO.copy()
KNEEL_UP.update(hips=Vector((0, 0.07, 0.45)), al=Vector((-0.07, -0.33, 0.07)), ar=Vector((0.07, -0.33, 0.07)),
                tl=Vector((0, -1, -0.12)), tr=Vector((0, -1, -0.12)), ul=Vector((0, 0, -1)), ur=Vector((0, 0, -1)),
                kl=Vector((0, 1, -0.2)), kr=Vector((0, 1, -0.2)))
# 跪下的中间：右膝先着地，左脚还踩在前面
HALF_KNEEL = KNEEL_UP.copy()
HALF_KNEEL.update(hips=Vector((0, 0.0, 0.56)), hips_pitch=6.0, al=Vector((-0.08, 0.3, 0.105)), tl=Vector((0, 1, -0.55)),
                  ul=Vector((0, 0.5, 1)), kl=Vector((0, 1, 0.6)), ar=Vector((0.08, -0.36, 0.08)))
STEP_BACK = GASSHO.copy()
STEP_BACK.update(hips=Vector((0, -0.02, 0.86)), ar=Vector((0.07, -0.25, 0.165)), tr=Vector((0, 0.8, -0.75)), ur=Vector((0, 0.6, 1)),
                 hips_pitch=4.0, kl=Vector((0, 1, 0.1)))
# 坐回脚跟上
KNEEL_SIT = KNEEL_UP.copy()
KNEEL_SIT.update(hips=Vector((0, -0.24, 0.31)), hips_pitch=6.0)
# 跪下、起身的中间：后面那只脚抬起来、脚尖朝后，从身子底下收过去（不擦着地）
KNEEL_MID = KNEEL_UP.copy()
KNEEL_MID.update(hips=Vector((0, 0.03, 0.5)), al=Vector((-0.08, -0.05, 0.2)), tl=Vector((0, -1, -0.35)), ul=Vector((0, -0.3, -1)), kl=Vector((0, 1, -0.4)))
# 叩首：坐在脚跟上，身子往前伏，双手掌心向下按在膝前，额头贴地
KOWTOW = KNEEL_SIT.copy()
KOWTOW.update(hips=Vector((0, -0.2, 0.33)), hips_pitch=70.0, spine=20.0, chest=18.0, upper=12.0, neck=12.0, headp=18.0,
              hand_space=0.0, wl=Vector((-0.13, 0.4, 0.035)), wr=Vector((0.13, 0.4, 0.035)), pl=Vector((0, 0, -1)), pr=Vector((0, 0, -1)),
              fl=Vector((0.15, 1, 0)), fr=Vector((-0.15, 1, 0)), el=Vector((-1, 0, 0.4)), er=Vector((1, 0, 0.4)),
              curl=10.0, thumb=8.0, spread=5.0, sh_fwd=8.0)
KOWTOW_HANDS = KNEEL_SIT.copy()
KOWTOW_HANDS.update(hips_pitch=25.0, spine=6.0, chest=6.0, hand_space=0.0, wl=Vector((-0.13, 0.36, 0.12)), wr=Vector((0.13, 0.36, 0.12)),
                    pl=Vector((0, 0.3, -1)), pr=Vector((0, 0.3, -1)), fl=Vector((0.1, 1, -0.3)), fr=Vector((-0.1, 1, -0.3)),
                    el=Vector((-1, 0, 0)), er=Vector((1, 0, 0)), curl=12.0, thumb=10.0, spread=4.0)

# 盘坐：臀坐在蒲团上，两膝往外打开，两只脚交叠在身前；双手叠放在腹前（掌心向上，右手在上，两拇指相触）
# 坐的地方（坐、起身这几段的原点是圆蒲团正下方的地面）：
#   圆蒲团顶 ZAFU、方草垫面 MAT_TOP，都按人物身高换算过（游戏里人缩到 0.806 倍：0.176 / 0.806、0.05 / 0.806）。
#   方草垫从圆蒲团往前伸（朝大殿 +y），人坐下前先站在草垫上、圆蒲团前面 STAND_Y 处。
ZAFU, MAT_TOP, STAND_Y = 0.218, 0.062, 0.39
MAT = MAT_TOP
SIT = P(hips=Vector((0, -0.04, ZAFU + 0.1)), al=Vector((0.1, 0.37, MAT + 0.065)), ar=Vector((-0.1, 0.31, MAT + 0.075)),
        tl=Vector((0.85, 0.35, -0.1)), tr=Vector((-0.85, 0.35, -0.1)), ul=Vector((0.15, 0, 1)), ur=Vector((-0.15, 0, 1)),
        kl=Vector((-1, 0.45, -0.25)), kr=Vector((1, 0.45, -0.25)), hand_space=0.0,
        wl=Vector((-0.075, 0.1, ZAFU + 0.17)), wr=Vector((0.075, 0.11, ZAFU + 0.185)), pl=Vector((0, 0, 1)), pr=Vector((0, 0, 1)),
        fl=Vector((1, 0.25, 0)), fr=Vector((-1, 0.25, 0)), el=Vector((-1, -0.2, -0.3)), er=Vector((1, -0.2, -0.3)),
        curl=10.0, thumb=28.0, spread=1.0, neck=4.0, headp=7.0)
SIT_GASSHO = SIT.copy()
SIT_GASSHO.update(hand_space=1.0, wl=GASSHO['wl'], wr=GASSHO['wr'], pl=GASSHO['pl'], pr=GASSHO['pr'], fl=GASSHO['fl'], fr=GASSHO['fr'],
                  el=GASSHO['el'], er=GASSHO['er'], curl=3.0, thumb=26.0, spread=0.0, sh_fwd=4.0)
SIT_BOW = SIT_GASSHO.copy()
SIT_BOW.update(hips_pitch=22.0, spine=7.0, chest=7.0, upper=5.0, neck=6.0, headp=12.0, hips=Vector((0, -0.06, ZAFU + 0.1)))
# 坐下、起身的中间：蹲下去，身子前倾保持平衡，两手往前
# 站在草垫上、圆蒲团前面；蹲下去时臀往后找圆蒲团
STAND_MAT = P(hips=Vector((0, STAND_Y + 0.007, 0.935 + MAT)), al=Vector((-0.045, STAND_Y - 0.027, 0.105 + MAT)), ar=Vector((0.046, STAND_Y - 0.027, 0.105 + MAT)))
SQUAT = P(hips=Vector((0, STAND_Y - 0.2, 0.5 + MAT + 0.05)), hips_pitch=32.0, spine=8.0, chest=6.0, al=Vector((-0.09, STAND_Y + 0.02, 0.105 + MAT)),
          ar=Vector((0.09, STAND_Y + 0.02, 0.105 + MAT)),
          kl=Vector((-0.25, 1, 0.3)), kr=Vector((0.25, 1, 0.3)), hand_space=0.0, wl=Vector((-0.2, STAND_Y + 0.22, 0.55 + MAT)), wr=Vector((0.2, STAND_Y + 0.22, 0.55 + MAT)),
          pl=Vector((0.5, 0, -0.8)), pr=Vector((-0.5, 0, -0.8)), fl=Vector((0, 1, -0.5)), fr=Vector((0, 1, -0.5)),
          el=Vector((-1, -0.3, -0.5)), er=Vector((1, -0.3, -0.5)), curl=20.0)
SIT_LEGS_FWD = P(hips=Vector((0, -0.06, ZAFU + 0.1)), hips_pitch=8.0, al=Vector((-0.12, 0.55, MAT + 0.06)), ar=Vector((0.12, 0.55, MAT + 0.06)),
                 tl=Vector((0, 1, 0.1)), tr=Vector((0, 1, 0.1)), ul=Vector((0, -0.2, 1)), ur=Vector((0, -0.2, 1)),
                 kl=Vector((-0.4, 0.3, 1)), kr=Vector((0.4, 0.3, 1)), hand_space=0.0, wl=Vector((-0.24, -0.12, 0.05)), wr=Vector((0.24, -0.12, 0.05)),
                 pl=Vector((0, 0, -1)), pr=Vector((0, 0, -1)), fl=Vector((-0.3, 0.5, 0)), fr=Vector((0.3, 0.5, 0)),
                 el=Vector((-0.5, -1, 0)), er=Vector((0.5, -1, 0)), curl=15.0)
SIT_LEGS_FWD['wl'] = Vector((-0.24, -0.1, ZAFU + 0.02))
SIT_LEGS_FWD['wr'] = Vector((0.24, -0.1, ZAFU + 0.02))


# ── 挂布条（许愿树的绳子）──
# 游戏里人站在绳外 0.45 米，绳上的挂点高约 1.05 米；这里按 Shino 的身材（÷0.806）：前方 0.56、高 1.30。
# 右脚往前垫半步、身子微微前倾，两手在绳前合拢系结（系的时候两手交替绕一小圈）。布条由游戏挂在右手上，松手时挂到绳上。
ROPE_Y, ROPE_Z = 0.56, 1.30
HANG_LIFT = P(wl=(-0.08, 0.2, 1.04), wr=(0.06, 0.22, 1.08), pl=(1, 0.2, 0.3), pr=(-1, 0.2, 0.3), fl=(0.1, 1, 0.5), fr=(-0.1, 1, 0.5),
              el=(-1, -0.4, -0.8), er=(1, -0.4, -0.8), curl=32.0, thumb=22.0, spread=1.0, neck=4.0, headp=8.0)
# 两手抓着布条在绳上：掌心朝里、朝下，手指往前下方弯着捏住（不是合十那样指尖朝上）
HANG_REACH = P(hand_space=0.0, wl=(-0.04, ROPE_Y - 0.06, ROPE_Z), wr=(0.04, ROPE_Y - 0.05, ROPE_Z + 0.01),
               pl=(0.8, 0, -0.6), pr=(-0.8, 0, -0.6), fl=(0.2, 1, -0.5), fr=(-0.2, 1, -0.5), el=(-1, -0.3, -0.8), er=(1, -0.3, -0.8),
               curl=48.0, thumb=32.0, spread=1.0, sh_fwd=6.0, hips=(0, 0.09, 0.925), hips_pitch=6.0, spine=4.0, chest=4.0, upper=3.0,
               neck=7.0, headp=14.0, ar=(0.085, 0.14, 0.105))
# 迈步的中间：右脚抬起来往前送
HANG_STEP = HANG_LIFT.copy()
HANG_STEP.update(hips=Vector((0, 0.05, 0.93)), ar=Vector((0.09, 0.06, 0.165)), tr=Vector((0, 1, -0.3)), hips_pitch=3.0)
# 系结：左手捏住往下翻、右手绕过去，再换过来（手腕翻、手指一松一紧地捏）
HANG_TIE_A = HANG_REACH.copy()
HANG_TIE_A.update(wl=Vector((-0.05, ROPE_Y - 0.045, ROPE_Z + 0.03)), wr=Vector((0.015, ROPE_Y - 0.08, ROPE_Z - 0.025)),
                  pl=Vector((0.4, 0.2, -0.9)), pr=Vector((-0.95, -0.2, -0.2)), fl=Vector((0.3, 1, -0.7)), fr=Vector((-0.1, 1, -0.2)),
                  curl=58.0, thumb=38.0, headp=15.0)
HANG_TIE_B = HANG_REACH.copy()
HANG_TIE_B.update(wl=Vector((-0.015, ROPE_Y - 0.08, ROPE_Z - 0.025)), wr=Vector((0.05, ROPE_Y - 0.045, ROPE_Z + 0.03)),
                  pl=Vector((0.95, -0.2, -0.2)), pr=Vector((-0.4, 0.2, -0.9)), fl=Vector((0.1, 1, -0.2)), fr=Vector((-0.3, 1, -0.7)),
                  curl=40.0, thumb=26.0, headp=13.0)
# 松手：两手稍分开、手指张开
HANG_RELEASE = HANG_REACH.copy()
HANG_RELEASE.update(wl=Vector((-0.09, ROPE_Y - 0.12, ROPE_Z - 0.04)), wr=Vector((0.09, ROPE_Y - 0.11, ROPE_Z - 0.03)), curl=8.0, thumb=12.0, spread=6.0,
                    fl=Vector((0.2, 1, -0.2)), fr=Vector((-0.2, 1, -0.2)))
# 收回来：两手落到小腹前、掌心朝里，肘往后下方垂着贴着身子（原来手腕在腰两侧、肘往外翻，看上去像叉腰）
HANG_BACK = HANG_STEP.copy()
HANG_BACK.update(curl=18.0, thumb=15.0, wl=Vector((-0.085, 0.17, 0.95)), wr=Vector((0.085, 0.18, 0.96)),
                 pl=Vector((1, 0.1, 0.15)), pr=Vector((-1, 0.1, 0.15)), fl=Vector((0.15, 0.8, -0.6)), fr=Vector((-0.15, 0.8, -0.6)),
                 el=Vector((-0.45, -1, -0.5)), er=Vector((0.45, -1, -0.5)))

# ── 上香 ──
# 拿着三炷香：两手在胸前把香拢住（右手握，左手包在外面），香竖着；举到脸前；拜（拖着播）；俯身把香插进香炉（脚不动），直起来合掌。
# 举香：两手在脸前约 0.22 米、离地约 1.04 米（游戏里），前臂斜着往上约 45 度，肘自然垂着，香头在眉毛那么高，脸露在外面。
INC_CHEST = P(wl=(-0.022, 0.2, 1.1), wr=(0.022, 0.21, 1.11), pl=(1, 0, 0), pr=(-1, 0, 0), fl=(0, 0.35, 1), fr=(0, 0.35, 1),
              el=(-1, -0.35, -0.9), er=(1, -0.35, -0.9), curl=42.0, thumb=30.0, spread=0.0, sh_fwd=3.0, neck=4.0, headp=8.0)
INC_HOLD = INC_CHEST.copy()
INC_HOLD.update(wl=Vector((-0.022, 0.27, 1.29)), wr=Vector((0.022, 0.275, 1.30)), fl=Vector((0, 0.2, 1)), fr=Vector((0, 0.2, 1)),
                el=Vector((-0.8, -0.3, -1.1)), er=Vector((0.8, -0.3, -1.1)), neck=3.0, headp=5.0, sh_fwd=4.0)


def incense_bow(deg):
    """举着香鞠躬：和合掌鞠躬一样从髋部折，香跟着胸口走"""
    p = gassho_bow(deg)
    for k in ('wl', 'wr', 'pl', 'pr', 'fl', 'fr', 'el', 'er', 'curl', 'thumb', 'spread', 'sh_fwd'):
        p[k] = INC_HOLD[k].copy() if hasattr(INC_HOLD[k], 'copy') else INC_HOLD[k]
    return p


# 插香：脚不动（供桌就在面前，没地方再迈步），从髋部往前俯身约 24 度，两手伸到人前方约 0.48 米、离地约 1.045 米（游戏里；
# 这里 ÷0.806 = 0.60、1.30），正在香炉灰面（离地 0.962 米）上方，香的下端插进灰里。
# 按大殿的中间供桌：人的原点站在 z ≈ 18.52（香炉灰面中心 z 19.0 往回 0.48），鞋尖离桌围（z 18.817）还有十几厘米，
# 胸口在桌面（离地 0.784）以上、桌边以内，不碰桌子。
PLANT_X, PLANT_Y, PLANT_Z = 0.0, 0.60, 1.30
# 插的那一刻手腕再低 4 厘米多（游戏里离灰面约 5 厘米：香的下端已经在灰里），先在灰面上方停一下再往下按
PLANT_DOWN = 1.252
INCENSE_PLANT_T = 1.5
PLANT_PRE = INC_CHEST.copy()
PLANT_PRE.update(hand_space=0.0, wl=Vector((PLANT_X - 0.022, 0.40, 1.34)), wr=Vector((PLANT_X + 0.022, 0.405, 1.35)),
                 el=Vector((-1, -0.2, -0.7)), er=Vector((1, -0.2, -0.7)), hips=Vector((0, -0.01, 0.93)), hips_pitch=8.0, spine=2.0, chest=1.0,
                 neck=6.0, headp=12.0)
PLANT = P(hand_space=0.0, wl=(PLANT_X - 0.022, PLANT_Y, PLANT_Z), wr=(PLANT_X + 0.022, PLANT_Y + 0.005, PLANT_Z + 0.01),
          pl=(1, 0, 0), pr=(-1, 0, 0), fl=(0, 0.3, 1), fr=(0, 0.3, 1), el=(-1, -0.2, -0.6), er=(1, -0.2, -0.6),
          curl=42.0, thumb=30.0, spread=0.0, sh_fwd=14.0, hips=(0, 0.035, 0.925), hips_pitch=19.0, spine=4.0, chest=3.0, upper=2.0,
          neck=8.0, headp=16.0)
# 往下按：俯得再深一点（髋 25 度）、膝微屈，手腕落到灰面上方约 5 厘米（游戏里）
PLANT_PUSH = PLANT.copy()
PLANT_PUSH.update(wl=Vector((PLANT_X - 0.022, PLANT_Y + 0.005, PLANT_DOWN)), wr=Vector((PLANT_X + 0.022, PLANT_Y + 0.01, PLANT_DOWN + 0.01)),
                  hips=Vector((0, 0.04, 0.905)), hips_pitch=25.0, spine=5.0, chest=4.0, upper=2.0, neck=9.0, headp=18.0, sh_fwd=15.0)
PLANT_RELEASE = PLANT_PUSH.copy()
PLANT_RELEASE.update(wl=Vector((PLANT_X - 0.05, PLANT_Y - 0.04, PLANT_DOWN + 0.07)), wr=Vector((PLANT_X + 0.05, PLANT_Y - 0.035, PLANT_DOWN + 0.08)),
                     curl=8.0, thumb=12.0, spread=5.0, hips=Vector((0, 0.035, 0.915)), hips_pitch=21.0)
# 直起身：两手从香炉那边收回胸前、慢慢合拢（直接接合掌；原来先落到腰两侧、肘往外翻，像叉腰，再抬起来合掌）
PLANT_BACK = GASSHO.copy()
PLANT_BACK.update(wl=Vector((-0.045, 0.24, 1.07)), wr=Vector((0.045, 0.245, 1.075)), pl=Vector((1, 0.15, 0.2)), pr=Vector((-1, 0.15, 0.2)),
                  fl=Vector((0.05, 0.5, 0.8)), fr=Vector((-0.05, 0.5, 0.8)), el=Vector((-1, -0.4, -0.9)), er=Vector((1, -0.4, -0.9)),
                  curl=8.0, thumb=18.0, spread=1.0, sh_fwd=3.0, hips_pitch=4.0, neck=4.0, headp=7.0)


def loop_of(p, secs=8.0):
    """保持的姿势：呼吸一直在动（4 秒一次），8 秒正好两次，首尾接得上"""
    return [(0.0, p), (secs, p)], secs


CLIPS = {
    # 名字: (关键姿势列表, 时长, 组的时间差)
    'Gassho_In': ([(0.0, STAND), (0.45, GASSHO_MID), (0.95, GASSHO)], 0.95),
    'Gassho_Loop': loop_of(GASSHO),
    'Gassho_Out': ([(0.0, GASSHO), (0.45, GASSHO_MID), (1.0, STAND)], 1.0),
    # 合掌低头：0 是直立合掌，1 是低头最深（游戏按进度拖着播）
    'Gassho_Scrub': ([(0.0, GASSHO), (1.0, GASSHO_LOW)], 1.0),
    # 站着鞠躬：0 直立合掌 → 1 弯到 45 度
    'Bow_Scrub': ([(0.0, gassho_bow(0)), (0.3, gassho_bow(12)), (1.0, gassho_bow(45))], 1.0),
    # 跪下：合掌站好 → 右脚往后撤半步 → 右膝着地 → 左膝跟上 → 长跪合掌
    'Kneel_Down': ([(0.0, GASSHO), (0.6, STEP_BACK), (1.3, HALF_KNEEL), (1.7, KNEEL_MID), (2.1, KNEEL_UP), (2.5, KNEEL_UP)], 2.5),
    'Kneel_Loop': loop_of(KNEEL_UP),
    # 叩首：0 长跪合掌 → 坐回脚跟、手往下 → 双手按地 → 身子伏下、额头贴地（1）
    'Kowtow_Scrub': ([(0.0, KNEEL_UP), (0.3, KNEEL_SIT), (0.55, KOWTOW_HANDS), (1.0, KOWTOW)], 1.0),
    # 起身：长跪 → 左脚往前踩 → 站起来 → 合掌放下
    'Kneel_Up': ([(0.0, KNEEL_UP), (0.35, KNEEL_MID), (0.7, HALF_KNEEL), (1.6, STEP_BACK), (2.1, GASSHO), (2.6, STAND)], 2.6),
    # 坐下：蹲下去 → 臀落到蒲团上、腿先往前伸着 → 两腿收回盘起来 → 手放到腹前
    'Sit_Down': ([(0.0, STAND_MAT), (0.8, SQUAT), (1.5, SIT_LEGS_FWD), (2.3, SIT), (2.8, SIT)], 2.8),
    'Sit_Loop': loop_of(SIT),
    # 坐着合掌鞠躬：0 坐着合掌 → 1 坐着鞠躬
    'SitBow_Scrub': ([(0.0, SIT_GASSHO), (1.0, SIT_BOW)], 1.0),
    'Sit_Up': ([(0.0, SIT), (0.6, SIT_LEGS_FWD), (1.4, SQUAT), (2.4, STAND_MAT)], 2.4),
    # 挂布条：拿着布条抬手 → 右脚垫半步、伸手到绳上 → 系（循环，游戏松手时接 Hang_Out）→ 松手、退回、手放下
    'Hang_In': ([(0.0, STAND), (0.45, HANG_LIFT), (0.85, HANG_STEP), (1.3, HANG_REACH), (1.5, HANG_REACH)], 1.5),
    'Hang_Loop': ([(0.0, HANG_REACH), (0.4, HANG_TIE_A), (0.8, HANG_REACH), (1.2, HANG_TIE_B), (1.6, HANG_REACH)], 1.6),
    'Hang_Out': ([(0.0, HANG_REACH), (0.35, HANG_RELEASE), (0.8, HANG_BACK), (1.4, STAND)], 1.4),
    # 上香：拿香到胸前 → 举到额前；拜（0 举着香直立 → 1 举着香躬身 40 度）；插香；不插直接放下
    'Incense_In': ([(0.0, STAND), (0.6, INC_CHEST), (1.4, INC_HOLD), (1.7, INC_HOLD)], 1.7),
    'Incense_Scrub': ([(0.0, incense_bow(0)), (0.3, incense_bow(12)), (1.0, incense_bow(40))], 1.0),
    'Incense_Plant': ([(0.0, INC_HOLD), (0.45, INC_CHEST), (0.95, PLANT_PRE), (1.25, PLANT), (INCENSE_PLANT_T, PLANT_PUSH), (1.85, PLANT_RELEASE),
                       (2.4, PLANT_BACK), (2.9, GASSHO), (3.2, GASSHO)], 3.2),
    'Incense_Out': ([(0.0, INC_HOLD), (0.5, INC_CHEST), (1.2, STAND)], 1.2),
}
LAG = {'head': 0.1, 'hand': -0.05}


def check(name):
    """穿模自查：每帧量膝盖、脚踝、脚尖离它下面的面（坐的动作：圆蒲团顶 z=0 半径 0.25，往外是草垫 MAT）多高"""
    keys, secs = CLIPS[name]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=SRC)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    rig = Rig(arm)
    worst = {}
    for f in range(int(secs * FPS) + 1):
        t = f / FPS
        p = sample(keys, t, LAG)
        D, hp = solve(rig, p, t)
        # 各关节的位置：沿着骨架从髋往下推
        pos = {rig.J('C_Hips'): hp}
        for n in rig.order:
            par = rig.parent[n]
            if par is None or n in pos:
                continue
            if par in pos:
                pos[n] = pos[par] + D[par] @ (rig.head[n] - rig.head[par])
        for b, flesh in (('L_LowerLeg', 0.045), ('R_LowerLeg', 0.045), ('L_Foot', 0.035), ('R_Foot', 0.035), ('L_ToeBase', 0.015), ('R_ToeBase', 0.015),
                         ('C_Head', 0.1), ('L_Hand', 0.02), ('R_Hand', 0.02), ('C_Hips', 0.09)):
            q = pos.get(rig.J(b))
            if q is None:
                continue
            r = math.hypot(q.x, q.y)
            # 圆蒲团（半径 0.25）→ 方草垫（左右 ±0.5、前后 -0.35..0.65）→ 地面
            under = ZAFU if r < 0.25 else MAT_TOP if (abs(q.x) < 0.5 and -0.35 < q.y < 0.65) else 0.0
            if not name.startswith('Sit'):
                under = 0.0               # 跪、拜、站的动作在平地上
            gap = q.z - flesh - under
            if b not in worst or gap < worst[b][0]:
                worst[b] = (round(gap, 3), round(t, 2), round(r, 2))
    print(f'[check] {name}: ' + '  '.join(f'{b} 最低 {v[0]}（{v[1]} 秒，离中心 {v[2]}）' for b, v in worst.items()))


def measure(name, times):
    """量某几个时刻手腕、头、胸、膝、脚尖在游戏里（×0.806）的位置：前方（米）、离地（米）。上香、挂布条对着供桌、绳子摆位置用"""
    keys, secs = CLIPS[name]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=SRC)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    rig = Rig(arm)
    k = 0.806
    for t in times:
        p = sample(keys, t, LAG)
        D, hp = solve(rig, p, t)
        pos = {rig.J('C_Hips'): hp}
        for n in rig.order:
            par = rig.parent[n]
            if par is None or n in pos:
                continue
            if par in pos:
                pos[n] = pos[par] + D[par] @ (rig.head[n] - rig.head[par])
        def g(b):
            q = pos[rig.J(b)]
            return f'{b} 前 {q.y * k:+.3f} 高 {q.z * k:.3f} 横 {q.x * k:+.3f}'
        wm = (pos[rig.J('L_Hand')] + pos[rig.J('R_Hand')]) / 2
        toe = max(pos[rig.J('L_ToeBase')].y, pos[rig.J('R_ToeBase')].y)
        print(f'[measure] {name} {t:.2f}s 两手腕中点 前 {wm.y * k:.3f} 高 {wm.z * k:.3f} 相隔 {(pos[rig.J("L_Hand")] - pos[rig.J("R_Hand")]).length * k:.3f}；'
              + '；'.join(g(b) for b in ('C_Head', 'C_UpperChest', 'C_Hips', 'L_LowerLeg', 'R_LowerLeg', 'L_Foot', 'R_Foot'))
              + f'；脚趾根最前 {toe * k:+.3f}')


def build(name):
    keys, secs = CLIPS[name]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=SRC)
    for o in list(bpy.data.objects):
        if o.type != 'ARMATURE':
            bpy.data.objects.remove(o)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    arm.animation_data_create()
    act = bpy.data.actions.new(name)
    arm.animation_data.action = act
    rig = Rig(arm)
    rest_key(rig, 0)
    n = int(round(secs * FPS))
    scrub = name.endswith('_Scrub')
    loop = name.endswith('_Loop')
    # 前后各多导 PAD 帧（CharacterImport.WalkPad 一样，不算在片段里）：Unity 按逐帧采样连曲线，片段第一帧的切线是按前一帧算的，
    # 前面紧挨着第 0 帧的静止姿势（基准）的话，第一、二帧之间往那边鼓出去，循环每绕一圈手就跳一下（合掌 2.7 厘米、系布条 2.2 厘米）。
    # 循环片段前后补的是绕回来的那几帧，其余的前后停在首、末姿势
    for f in range(-PAD, n + PAD + 1):
        t = f / FPS
        tt = t % secs if loop else min(max(t, 0.0), secs)
        p = sample(keys, tt, {} if scrub else LAG, secs if loop else None)
        if scrub:
            p['breath'] = 0.0         # 拖着播的不加呼吸（呼吸由叠在下面的循环给）
        if loop and abs(secs / 4.0 - round(secs / 4.0)) > 1e-3:
            p['breath'] = 0.0         # 呼吸 4 秒一次，循环长度不是 4 的倍数（系布条 1.6 秒）就不加，不然首尾对不上
        D, hp = solve(rig, p, tt)
        key(rig, D, hp, f + 1 + PAD)
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 0, n + 2 * PAD + 1
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, name + '.fbx'), use_selection=True, apply_scale_options='FBX_SCALE_UNITS',
                             object_types={'ARMATURE'}, add_leaf_bones=False, bake_anim=True, bake_anim_use_all_actions=False,
                             bake_anim_use_nla_strips=False, bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0,
                             axis_forward='-Z', axis_up='Y')
    print(f'[pray] {name}: {secs:.2f} 秒，{n + 1} 帧')


names = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
if names and names[0] == 'check':
    for nm in names[1:]:
        check(nm)
elif names and names[0] == 'measure':
    # measure 片段名 时刻,时刻,...
    measure(names[1], [float(x) for x in names[2].split(',')])
else:
    for nm in names or list(CLIPS):
        build(nm)
