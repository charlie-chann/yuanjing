"""读 BVH 动捕文件、算每一帧每个关节的位置，画成火柴人逐帧图（挑片段用）。
用法：python3 bvh.py <文件.bvh> <输出.png> [起始秒 结束秒 张数]"""
import math
import re
import sys

import numpy as np


def load(path):
    txt = open(path).read()
    head, motion = txt.split('MOTION')
    joints, stack, cur = [], [], None
    tokens = re.findall(r'\{|\}|[^\s{}]+', head)
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in ('ROOT', 'JOINT'):
            cur = {'name': tokens[i + 1], 'parent': stack[-1] if stack else -1, 'chan': [], 'off': None}
            joints.append(cur)
            i += 2
            continue
        if t == 'End':
            cur = {'name': joints[stack[-1]]['name'] + '_end', 'parent': stack[-1], 'chan': [], 'off': None, 'end': True}
            joints.append(cur)
            i += 2
            continue
        if t == '{':
            stack.append(len(joints) - 1)
        elif t == '}':
            stack.pop()
        elif t == 'OFFSET':
            cur['off'] = np.array([float(x) for x in tokens[i + 1:i + 4]])
            i += 4
            continue
        elif t == 'CHANNELS':
            n = int(tokens[i + 1])
            cur['chan'] = tokens[i + 2:i + 2 + n]
            i += 2 + n
            continue
        i += 1
    lines = motion.strip().split('\n')
    nf = int(lines[0].split()[1])
    ft = float(lines[1].split()[2])
    data = np.array([[float(x) for x in l.split()] for l in lines[2:2 + nf]])
    return joints, data, ft


def rot(axis, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    if axis == 'X':
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == 'Y':
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def fk(joints, frame):
    pos, rots, k = [], [], 0
    for j in joints:
        R = np.eye(3)
        t = j['off'].copy()
        for ch in j['chan']:
            v = frame[k]
            k += 1
            if ch.endswith('position'):
                t[{'X': 0, 'Y': 1, 'Z': 2}[ch[0]]] = v
            else:
                R = R @ rot(ch[0], v)
        if j['parent'] < 0:
            pos.append(t)
            rots.append(R)
        else:
            p = j['parent']
            pos.append(pos[p] + rots[p] @ t)
            rots.append(rots[p] @ R)
    return np.array(pos)


def sheet(path, out, t0=0, t1=None, n=16):
    from PIL import Image, ImageDraw
    joints, data, ft = load(path)
    T = len(data) * ft
    t1 = T if t1 is None else min(t1, T)
    times = [t0 + (t1 - t0) * k / max(1, n - 1) for k in range(n)]
    W = 220
    img = Image.new('RGB', (W * n // 2 if n > 8 else W * n, W * (2 if n > 8 else 1) * 2), (250, 250, 248))
    d = ImageDraw.Draw(img)
    cols = n // 2 if n > 8 else n
    P = [fk(joints, data[min(len(data) - 1, int(t / ft))]) for t in times]
    allp = np.concatenate(P)
    h = allp[:, 1].max() - allp[:, 1].min()
    sc = W * 0.85 / max(h, 1e-3)
    for idx, (t, p) in enumerate(zip(times, P)):
        cx, cy = (idx % cols) * W, (idx // cols) * W * 2
        for view, oy in ((0, 0), (1, W)):     # 0 侧面（看 x 轴方向：z-y），1 正面（x-y）
            ax = 2 if view == 0 else 0
            base = p[:, 1].min()
            mid = p[0, ax]
            for j, jt in enumerate(joints):
                if jt['parent'] < 0:
                    continue
                a, b = p[jt['parent']], p[j]
                col = (200, 60, 50) if 'Left' in jt['name'] or 'LHip' in jt['name'] else (50, 90, 200) if 'Right' in jt['name'] or 'RHip' in jt['name'] else (40, 40, 40)
                d.line([(cx + W / 2 + (a[ax] - mid) * sc, cy + oy + W * 0.95 - (a[1] - base) * sc),
                        (cx + W / 2 + (b[ax] - mid) * sc, cy + oy + W * 0.95 - (b[1] - base) * sc)], fill=col, width=3)
            d.text((cx + 4, cy + oy + 4), f'{t:.1f}s {"侧" if view == 0 else "正"}'.replace('侧', 'side').replace('正', 'front'), fill=(0, 0, 0))
    img.save(out)
    print(out, f'共 {T:.1f} 秒，{len(joints)} 个关节')


if __name__ == '__main__':
    a = sys.argv
    sheet(a[1], a[2], float(a[3]) if len(a) > 3 else 0, float(a[4]) if len(a) > 4 else None, int(a[5]) if len(a) > 5 else 16)


def find_loop(path, t_from=8.0, t_to=40.0, pmin=0.9, pmax=1.5):
    """在一长段走路里找一个首尾能接上的步态循环：以髋为原点比较全身关节位置，找差别最小的 (起点, 周期)"""
    joints, data, ft = load(path)
    step = max(1, int(round(1 / 60 / ft)))
    idx = list(range(int(t_from / ft), min(len(data), int(t_to / ft)), step))
    P = {}

    def pose(i):
        if i not in P:
            p = fk(joints, data[i])
            p = p - p[0]
            # 朝向归一：按两髋连线把身体转到朝同一个方向
            l, r = [k for k, j in enumerate(joints) if j['name'] in ('LeftUpLeg', 'LHipJoint')][0], [k for k, j in enumerate(joints) if j['name'] in ('RightUpLeg', 'RHipJoint')][0]
            a = p[l] - p[r]
            ang = math.atan2(a[2], a[0])
            c, s = math.cos(-ang), math.sin(-ang)
            R = np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])
            P[i] = p @ R.T
        return P[i]
    best = None
    for i in idx[::6]:
        for per in np.arange(pmin, pmax, ft * step):
            j = i + int(round(per / ft))
            if j >= len(data):
                break
            d = np.abs(pose(i) - pose(j)).mean()
            if best is None or d < best[0]:
                best = (d, i * ft, j * ft)
    return best
