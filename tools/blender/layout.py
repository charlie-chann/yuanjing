"""湖心小寺的平面布局。这里的 (x, y) 就是 Unity 里的 (x, z)：x 向右，y 往里（北）。
Unity 那边（Editor/BuildIslet.cs）有一份同样的数字，改这里要同时改那里。"""
import math
from mathutils import noise, Vector

WATER = -0.42                 # 水面高度
ISLE_C = (0.0, 4.5)           # 小岛中心
ISLE_R = (18.5, 21.8)         # 小岛（南半边，老岛）的半宽、半深
# 2026-11-19 大殿放大十倍：岛在北边长出一大块圆角的地（葫芦形），老岛南半边的岸线不变
LOBE_C = (0.0, 29.0)          # 北边那块地的中心
LOBE_R = (33.2, 24.6)         # 半宽、半深（y 4.4 .. 53.6）
LOBE_N = 5.0                  # 圆角方形的指数（越大越方）
LOBE_BLEND = 3.5              # 两块地接起来的地方抹圆多少米（葫芦的腰）

PATH_W = 1.35                 # 主路半宽
PATH_Y0, PATH_Y1 = -15.2, 1.8  # 主路从码头到石台
GATE_Y = -12.5                # 牌坊
BURNER = (0.0, -2.0)          # 香炉
PLAZA_R = 3.7                 # 香炉周围的圆形铺地
TREE = (-8.6, -3.0)           # 许愿树
TREE_BED = 2.3
POND = (8.8, -4.2)            # 小池塘
POND_R = 3.1
TERRACE = (-11.3, 1.8, 11.3, 9.2)  # 石台（蒲团，216 个座位）x0 y0 x1 y1
TERRACE_H = 0.07
HALL = (0.0, 27.1)            # 大殿模型原点（2026-11-19 面阔九间的大殿：台基 46 × 32.4，前沿还在 y 10.9）
HALL_RECT = (-23.0, 10.9, 23.0, 43.3)  # 大殿台基 x0 y0 x1 y1（不算最外一圈 0.15 米的台座）
DOCK_Y0, DOCK_Y1 = -15.4, -24.6  # 栈桥从岸边到尽头
PAVILION = (14.4, 6.6)        # 钟亭（石台加宽后往东挪了）
# 小土丘 x y 高 半径。殿两侧原来那两座压在新台基底下，挪到殿后的两个角上（离台基 3 米以上，不挡绕殿走的路）
MOUNDS = [(-26.6, 48.6, 1.3, 2.9), (26.4, 48.9, 1.1, 2.7), (-15.0, 8.0, 0.6, 2.4)]


# 地形网格、islet_map.bytes、地面贴图覆盖的范围（x0, y0, x1, y1）。老的是 (-27, -29, 27, 33)
EXTENT = (-37.0, -29.0, 37.0, 59.0)


def smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def isle_radius(theta):
    """沿某个方向，岸线离中心多远（带一点不规则）"""
    c, s = math.cos(theta), math.sin(theta)
    n = 2.6
    r = (abs(c / ISLE_R[0]) ** n + abs(s / ISLE_R[1]) ** n) ** (-1 / n)
    wob = noise.noise(Vector((c * 1.7 + 3.1, s * 1.7 - 1.3, 0.5))) * 1.6 + noise.noise(Vector((c * 4.2, s * 4.2, 7.7))) * 0.55
    return r + wob


def lobe_radius(theta):
    """北边那块地：圆角方形，岸线只带很小的起伏（殿后、殿侧的地不宽，起伏大了会咬到台基边上）"""
    c, s = math.cos(theta), math.sin(theta)
    r = (abs(c / LOBE_R[0]) ** LOBE_N + abs(s / LOBE_R[1]) ** LOBE_N) ** (-1 / LOBE_N)
    wob = noise.noise(Vector((c * 2.3 - 5.2, s * 2.3 + 2.4, 3.5))) * 0.9 + noise.noise(Vector((c * 6.1, s * 6.1, 1.7))) * 0.35
    return r + wob


def shore_dist(x, y):
    """离岸线多远：正数在岛上，负数在水里。两块地取大的那个，接缝处抹圆"""
    vx, vy = x - ISLE_C[0], y - ISLE_C[1]
    a = isle_radius(math.atan2(vy, vx)) - math.hypot(vx, vy)
    wx, wy = x - LOBE_C[0], y - LOBE_C[1]
    b = lobe_radius(math.atan2(wy, wx)) - math.hypot(wx, wy)
    # 接缝抹圆只在 y 2 以北做（到 y 5 才抹足）：老岛南半边的岸线不动。
    # （北边那块地的南沿在 y 4.4 以北，南半边岸上、岸边 a 都比 b 大，取大的就是 a）
    k = LOBE_BLEND * smooth(2.0, 5.0, y)
    if k < 1e-6:
        return max(a, b)
    h = max(0.0, k - abs(a - b)) / k
    return max(a, b) + h * h * k * 0.25


def pond_radius(theta):
    return POND_R + 0.45 * math.sin(theta * 2 + 0.7) + 0.3 * math.sin(theta * 3 + 2.1)


def pond_dist(x, y):
    """离池塘边多远：正数在池塘里"""
    vx, vy = x - POND[0], y - POND[1]
    return pond_radius(math.atan2(vy, vx)) - math.hypot(vx, vy)


def height(x, y):
    d = shore_dist(x, y)
    if d >= 2.6:
        h = 0.0
    elif d >= 0:
        h = (WATER - 0.06) * (1 - smooth(0, 2.6, d))
    else:
        h = max(-3.4, WATER - 0.06 + d * 0.36)
    if d > 3.0:
        for (mx, my, mh, mr) in MOUNDS:
            q = math.hypot(x - mx, y - my) / mr
            if q < 1:
                h += mh * (1 - q * q) ** 2
    pd = pond_dist(x, y)
    if pd > -0.9:
        h -= smooth(-0.7, 1.6, pd) * 1.75
    return h
