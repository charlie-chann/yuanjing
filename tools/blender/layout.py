"""湖心小寺的平面布局。这里的 (x, y) 就是 Unity 里的 (x, z)：x 向右，y 往里（北）。
Unity 那边（Editor/BuildIslet.cs）有一份同样的数字，改这里要同时改那里。"""
import math
from mathutils import noise, Vector

WATER = -0.42                 # 水面高度
ISLE_C = (0.0, 4.5)           # 小岛中心
ISLE_R = (18.5, 21.8)         # 小岛的半宽、半深

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
HALL = (0.0, 15.8)            # 大殿中心
DOCK_Y0, DOCK_Y1 = -15.4, -24.6  # 栈桥从岸边到尽头
PAVILION = (14.4, 6.6)        # 钟亭（石台加宽后往东挪了）
MOUNDS = [(-11.5, 18.5, 1.5, 4.8), (12.5, 19.5, 1.2, 4.2), (-15.0, 8.0, 0.6, 2.4), (0.0, 24.2, 1.0, 4.5)]  # 小土丘 x y 高 半径


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


def shore_dist(x, y):
    """离岸线多远：正数在岛上，负数在水里"""
    vx, vy = x - ISLE_C[0], y - ISLE_C[1]
    return isle_radius(math.atan2(vy, vx)) - math.hypot(vx, vy)


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
