"""小动物：泰迪、小狗、小猫、麻雀、白鹭。头朝 +y。
身体、头、四条腿、尾巴（鸟是两只翅膀）分成各自的部件（部件名写成「toon:名字」），Unity 里的脚本让它们各自动起来。"""
import math

from kit import Asset
from palette import C, tint, mix, vary, hexc


def _eyes(a, part, y, z, dx, r=0.02, color=(0.1, 0.08, 0.07)):
    for sx in (-1, 1):
        a.blob(r, (sx * dx, y, z), (1, 0.7, 1), color, subdiv=1, bump=0, mat=part)
        a.blob(r * 0.35, (sx * dx + 0.004, y - 0.012, z + 0.007), (1, 1, 1), (1, 1, 1), subdiv=1, bump=0, mat=part)


def _dog(name, body, light, dark, curly=False, ears='flop', tail='up', s=1.0, muzzle=None):
    a = Asset(name)
    muzzle = muzzle or light
    bump = 0.22 if curly else 0.05
    B, H = 'toon:body', 'toon:head'
    # 身体：前胸略大
    a.blob(0.16 * s, (0, -0.02 * s, 0.27 * s), (0.95, 1.55, 0.95), dark, top=body, subdiv=3, bump=bump, freq=3.0, mat=B)
    a.blob(0.15 * s, (0, 0.13 * s, 0.29 * s), (1.0, 1.0, 1.0), dark, top=light, subdiv=3, bump=bump, freq=3.0, mat=B)
    if curly:
        for i in range(9):
            ang = i * 0.7
            a.blob(0.07 * s, (0.1 * s * math.cos(ang), (-0.2 + 0.045 * i) * s, (0.33 + 0.05 * math.sin(ang * 2)) * s), (1, 1, 0.9), body, top=light,
                   subdiv=1, bump=0.2, mat=B)
    # 头：大一点才可爱
    hy, hz = 0.3 * s, 0.47 * s
    a.blob(0.15 * s, (0, hy, hz), (1.0, 0.95, 0.92), body, top=light, subdiv=3, bump=bump, freq=3.0, mat=H)
    a.blob(0.075 * s, (0, hy + 0.13 * s, hz - 0.035 * s), (1.0, 1.1, 0.8), muzzle, subdiv=2, bump=0.03, mat=H)
    a.blob(0.026 * s, (0, hy + 0.2 * s, hz - 0.012 * s), (1.2, 0.8, 0.9), (0.12, 0.09, 0.08), subdiv=1, bump=0, mat=H)
    _eyes(a, H, hy + 0.115 * s, hz + 0.035 * s, 0.065 * s, 0.022 * s)
    if curly:
        a.blob(0.09 * s, (0, hy - 0.01 * s, hz + 0.12 * s), (1.1, 1.0, 0.8), body, top=light, subdiv=1, bump=0.25, mat=H)
    for sx in (-1, 1):
        if ears == 'flop':
            a.blob(0.07 * s, (sx * 0.14 * s, hy - 0.01 * s, hz + 0.0 * s), (0.5, 0.85, 1.25), dark, top=body, subdiv=1, bump=bump * 0.6, mat=H)
        else:
            a.lathe([(0.055 * s, 0.0), (0.03 * s, 0.07 * s), (0.0, 0.12 * s)], (sx * 0.085 * s, hy - 0.02 * s, hz + 0.1 * s), segs=6, color=dark, mat=H,
                    rot=(0.1, sx * 0.25, 0), squash=(1.0, 0.6))
    # 腿
    for nm, x, y in (('leg_fl', -0.085, 0.16), ('leg_fr', 0.085, 0.16), ('leg_bl', -0.09, -0.19), ('leg_br', 0.09, -0.19)):
        part = 'toon:' + nm
        a.cyl(0.045 * s, 0.2 * s, (x * s, y * s, 0.03 * s), body, r2=0.052 * s, segs=7, mat=part, grad=(light, body))
        a.blob(0.055 * s, (x * s, (y + 0.015) * s, 0.035 * s), (1.0, 1.2, 0.65), light, subdiv=1, bump=0, mat=part)
    # 尾巴
    T = 'toon:tail'
    if tail == 'pom':
        a.tube([(0, -0.27 * s, 0.33 * s), (0, -0.31 * s, 0.42 * s)], 0.022 * s, body, segs=5, mat=T)
        a.blob(0.06 * s, (0, -0.32 * s, 0.46 * s), (1, 1, 1), body, top=light, subdiv=1, bump=0.25, mat=T)
    elif tail == 'curl':
        pts = [(0, -0.26 * s, 0.33 * s), (0, -0.33 * s, 0.42 * s), (0, -0.3 * s, 0.5 * s), (0, -0.23 * s, 0.5 * s), (0, -0.22 * s, 0.44 * s)]
        a.tube(pts, [0.04 * s, 0.045 * s, 0.045 * s, 0.04 * s, 0.03 * s], body, segs=6, mat=T, color2=light)
    else:
        a.tube([(0, -0.26 * s, 0.32 * s), (0, -0.36 * s, 0.4 * s), (0, -0.4 * s, 0.5 * s)], [0.035 * s, 0.03 * s, 0.018 * s], body, segs=6, mat=T, color2=light)
    return a.finish(dist=0.3, strength=0.45, view=(35, 30, 1.0))


def dogs(name):
    t = 0
    teddy = hexc('#b9743f')
    t += _dog('dog_teddy', teddy, tint(teddy, 0.1, -0.05), tint(teddy, -0.1), curly=True, ears='flop', tail='pom', s=0.95)
    shiba = hexc('#e2a352')
    t += _dog('dog_shiba', shiba, C('white'), tint(shiba, -0.08), ears='point', tail='curl', s=1.05, muzzle=C('white'))
    white = hexc('#f6f1e7')
    t += _dog('dog_white', white, (1, 1, 1), hexc('#e3dccd'), curly=True, ears='flop', tail='pom', s=0.85)
    return t


def _cat(name, body, light, dark, s=1.0, patch=None):
    a = Asset(name)
    B, H = 'toon:body', 'toon:head'
    a.blob(0.12 * s, (0, -0.02 * s, 0.22 * s), (0.9, 1.75, 0.9), dark, top=body, subdiv=3, bump=0.04, mat=B)
    if patch is not None:
        a.blob(0.07 * s, (0.03 * s, -0.08 * s, 0.29 * s), (1.2, 1.3, 0.5), patch, subdiv=1, bump=0.1, mat=B)
        a.blob(0.05 * s, (-0.04 * s, 0.1 * s, 0.29 * s), (1.2, 1.2, 0.5), patch, subdiv=1, bump=0.1, mat=B)
    hy, hz = 0.24 * s, 0.36 * s
    a.blob(0.125 * s, (0, hy, hz), (1.05, 0.9, 0.88), body, top=light, subdiv=3, bump=0.03, mat=H)
    a.blob(0.045 * s, (0, hy + 0.1 * s, hz - 0.03 * s), (1.3, 0.8, 0.7), C('white'), subdiv=1, bump=0, mat=H)
    a.blob(0.014 * s, (0, hy + 0.135 * s, hz - 0.012 * s), (1.2, 0.8, 0.8), hexc('#e8909a'), subdiv=1, bump=0, mat=H)
    _eyes(a, H, hy + 0.095 * s, hz + 0.02 * s, 0.055 * s, 0.02 * s, color=(0.16, 0.2, 0.1))
    for sx in (-1, 1):
        a.lathe([(0.05 * s, 0.0), (0.028 * s, 0.06 * s), (0.0, 0.105 * s)], (sx * 0.075 * s, hy - 0.01 * s, hz + 0.085 * s), segs=5, color=dark if patch is None else patch,
                mat=H, rot=(0.05, sx * 0.3, 0), squash=(1.0, 0.55))
    for nm, x, y in (('leg_fl', -0.06, 0.13), ('leg_fr', 0.06, 0.13), ('leg_bl', -0.065, -0.17), ('leg_br', 0.065, -0.17)):
        part = 'toon:' + nm
        a.cyl(0.03 * s, 0.17 * s, (x * s, y * s, 0.02 * s), body, r2=0.036 * s, segs=6, mat=part, grad=(light, body))
        a.blob(0.038 * s, (x * s, (y + 0.012) * s, 0.025 * s), (1.0, 1.2, 0.6), C('white'), subdiv=1, bump=0, mat=part)
    pts = [(0, -0.22 * s, 0.24 * s), (0, -0.36 * s, 0.22 * s), (0.03 * s, -0.46 * s, 0.3 * s), (0.05 * s, -0.48 * s, 0.42 * s)]
    a.tube(pts, [0.03 * s, 0.028 * s, 0.026 * s, 0.022 * s], body, segs=6, mat='toon:tail', color2=dark if patch is None else patch)
    return a.finish(dist=0.3, strength=0.45, view=(35, 30, 1.0))


def cats(name):
    t = 0
    o = hexc('#e9933f')
    t += _cat('cat_orange', o, tint(o, 0.1, -0.1), tint(o, -0.1, 0.05))
    w = hexc('#f7f2e8')
    t += _cat('cat_white', w, (1, 1, 1), hexc('#e2dccf'), s=0.92)
    t += _cat('cat_calico', w, (1, 1, 1), hexc('#e2dccf'), s=0.98, patch=hexc('#3a3230'))
    return t


def birds(name):
    t = 0
    # 麻雀：圆滚滚的，比真的大一圈，远看才认得出
    for v, (body, cap, belly) in {'sparrow': (hexc('#a8794f'), hexc('#7a4f32'), hexc('#efe3cf')), 'tit': (hexc('#6f8fb8'), hexc('#2f3f5c'), hexc('#f5e9b8'))}.items():
        a = Asset(f'bird_{v}')
        B = 'toon:body'
        a.blob(0.07, (0, 0, 0.085), (1.0, 1.3, 1.0), belly, top=body, subdiv=3, bump=0.03, mat=B)
        a.blob(0.052, (0, 0.07, 0.15), (1, 1, 0.95), body, top=cap, subdiv=3, bump=0.02, mat=B)
        a.lathe([(0.016, 0.0), (0.0, 0.04)], (0, 0.115, 0.145), segs=5, color=hexc('#e2a23c'), rot=(-math.pi / 2, 0, 0), mat=B)
        _eyes(a, B, 0.1, 0.165, 0.032, 0.011)
        a.quad([(-0.03, -0.07, 0.1), (0.03, -0.07, 0.1), (0.035, -0.17, 0.085), (-0.035, -0.17, 0.085)], mat='leaf:tail',
               colors=[body, body, cap, cap], sway=(0, 0, 0, 0))
        for sx in (-1, 1):
            a.cyl(0.005, 0.03, (sx * 0.025, 0.01, 0.0), hexc('#c98a4a'), segs=4, mat=B)
        for nm, sx in (('wing_l', -1), ('wing_r', 1)):
            a.quad([(sx * 0.055, 0.05, 0.11), (sx * 0.055, -0.07, 0.1), (sx * 0.2, -0.09, 0.105), (sx * 0.17, 0.02, 0.112)], mat='leaf:' + nm,
                   colors=[body, cap, cap, body], sway=(0, 0, 0, 0))
        a.opts['leaf:tail'] = a.opts['leaf:wing_l'] = a.opts['leaf:wing_r'] = {'plain_normals': True, 'normal_up': 0.6}
        t += a.finish(ao=False, view=(35, 30, 1.0))
    # 白鹭：站在浅水里，细长的腿和脖子
    a = Asset('egret')
    w, wl = hexc('#f4f1ea'), (1, 1, 1)
    for sx in (-1, 1):
        a.cyl(0.012, 0.52, (sx * 0.04, 0, -0.1), hexc('#3b3a36'), segs=5)
    a.blob(0.15, (0, -0.03, 0.52), (0.8, 1.5, 0.85), hexc('#dcd7cc'), top=wl, subdiv=2, bump=0.04)
    a.quad([(-0.05, -0.2, 0.52), (0.05, -0.2, 0.52), (0.03, -0.42, 0.42), (-0.03, -0.42, 0.42)], mat='leaf', colors=[w, w, wl, wl], sway=(0, 0, 0.4, 0.4))
    a.tube([(0, 0.13, 0.58), (0, 0.2, 0.72), (0, 0.14, 0.86), (0, 0.17, 1.0), (0, 0.22, 1.06)], [0.045, 0.032, 0.028, 0.028, 0.03], w, segs=7, color2=wl, sway=(0.0, 0.25))
    a.blob(0.045, (0, 0.24, 1.07), (0.9, 1.3, 0.9), wl, subdiv=1, bump=0)
    a.lathe([(0.016, 0.0), (0.0, 0.16)], (0, 0.28, 1.065), segs=5, color=hexc('#e8b23c'), rot=(-math.pi / 2 - 0.1, 0, 0))
    _eyes(a, 'toon', 0.265, 1.085, 0.028, 0.009)
    a.opts['leaf'] = {'plain_normals': True, 'normal_up': 0.5}
    t += a.finish(ao=False, view=(35, 25, 1.0), floor=False)
    # 小鱼：一群一群的
    a = Asset('minnow')
    c = hexc('#5d7f8c')
    a.lathe([(0.0, -0.09), (0.012, -0.07, c), (0.024, -0.02, tint(c, 0.08)), (0.022, 0.04, c), (0.008, 0.09, c), (0.0, 0.1)], segs=6, color=c, rot=(-math.pi / 2, 0, 0), squash=(1.0, 0.7))
    a.quad([(0, -0.085, 0), (0.03, -0.14, 0.0), (0, -0.12, 0), (-0.03, -0.14, 0.0)], color=tint(c, 0.1), mat='toon')
    t += a.finish(ao=False, floor=False)
    return t


def pet_items(name):
    """动物叼来的礼物、喂它们的食物、撒给小鸟的谷子"""
    t = 0
    a = Asset('gift_bone')
    w = hexc('#f4ead2')
    a.tube([(-0.09, 0, 0.03), (0.09, 0, 0.03)], 0.02, w, segs=6)
    for sx in (-1, 1):
        for sy in (-1, 1):
            a.blob(0.032, (sx * 0.1, sy * 0.022, 0.03), (1, 1, 0.9), w, top=(1, 1, 1), subdiv=1, bump=0)
    t += a.finish(ao=False)
    a = Asset('gift_stick')
    a.tube([(-0.16, 0, 0.02), (-0.03, 0.01, 0.025), (0.15, -0.01, 0.02)], [0.016, 0.02, 0.014], C('trunk'), segs=6, color2=C('trunk_lit'))
    a.tube([(0.02, 0.0, 0.025), (0.07, 0.05, 0.03)], 0.009, C('trunk'), segs=4)
    a.quad([(0.07, 0.05, 0.03), (0.1, 0.085, 0.035), (0.085, 0.1, 0.03), (0.055, 0.075, 0.03)], color=C('leaf_lit'), mat='leaf')
    t += a.finish(ao=False)
    a = Asset('gift_flower')
    a.tube([(-0.12, 0, 0.012), (0.05, 0, 0.02)], 0.007, C('leaf_dark'), segs=4)
    for k in range(6):
        ang = k * 1.047
        a.disc(0.032, (0.07 + 0.03 * math.cos(ang), 0.03 * math.sin(ang), 0.03), C('blossom'), segs=6, mat='leaf', rim=C('blossom_lit'))
    a.disc(0.02, (0.07, 0, 0.036), C('ginkgo'), segs=6, mat='leaf')
    a.quad([(-0.05, 0, 0.014), (-0.02, 0.035, 0.02), (0.0, 0.0, 0.016)], color=C('leaf'), mat='leaf')
    t += a.finish(ao=False)
    a = Asset('gift_fish')
    c = hexc('#8fb3c4')
    a.lathe([(0.0, -0.1), (0.014, -0.08, c), (0.034, -0.02, tint(c, 0.1)), (0.03, 0.05, c), (0.01, 0.1, c), (0.0, 0.11)], (0, 0, 0.03), segs=7, color=c,
            rot=(-math.pi / 2, 0, math.pi / 2), squash=(1.0, 0.6))
    a.quad([(-0.09, 0, 0.03), (-0.15, 0.035, 0.03), (-0.13, 0, 0.03), (-0.15, -0.035, 0.03)], color=tint(c, 0.1), mat='leaf')
    t += a.finish(ao=False)
    a = Asset('gift_shell')
    c = hexc('#f7d9c8')
    a.lathe([(0.0, 0.04), (0.035, 0.035, c), (0.07, 0.015, tint(c, -0.06)), (0.08, 0.0)], segs=11, color=c, squash=(1.0, 0.85))
    for k in range(5):
        ang = -0.9 + k * 0.45
        a.tube([(0.0, -0.01, 0.041), (0.07 * math.sin(ang), 0.06 * math.cos(ang), 0.012)], 0.004, tint(c, -0.14), segs=4)
    t += a.finish(ao=False)
    # 食盆：一只小陶碗盛着粮
    a = Asset('food_bowl')
    b = hexc('#c9573c')
    a.lathe([(0.0, 0.0), (0.085, 0.0, tint(b, -0.1)), (0.105, 0.045, b), (0.1, 0.06, tint(b, 0.08)), (0.088, 0.058), (0.08, 0.03), (0.0, 0.03)], segs=12, color=b)
    a.lathe([(0.0, 0.05, hexc('#a8733f')), (0.084, 0.045)], segs=12, color=hexc('#a8733f'))
    for k in range(7):
        ang = k * 0.9
        a.blob(0.014, (0.045 * math.cos(ang), 0.045 * math.sin(ang), 0.056), (1, 1, 0.7), hexc('#8f5a2c'), subdiv=1, bump=0)
    t += a.finish(dist=0.2)
    # 谷子：撒在地上的一把
    a = Asset('grain')
    rng = a.rng
    for i in range(40):
        ang = rng.uniform(0, 6.28)
        d = 0.75 * math.sqrt(rng.random())
        a.blob(0.012, (d * math.cos(ang), d * math.sin(ang), 0.008), (1.3, 1, 0.6), hexc('#e9c96a'), subdiv=1, bump=0)
    t += a.finish(ao=False)
    return t


ASSETS = {'dogs': dogs, 'cats': cats, 'birds': birds, 'pet_items': pet_items}
