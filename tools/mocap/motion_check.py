"""读 MotionCheckTest 写的逐帧 CSV（unity/shots/motioncheck/*.csv），量：踩地的脚滑多快、每次着地挪了多远、步频、头晃、髋摆、手摆、
膝盖弯、跳帧、身子和走的方向差多少、脚掌踩稳时的俯仰（左右要一样、和站着时一样）、两只脚都踩着地时身子转了多少度（转盘式原地转）。
（评审的 analyze.py 改来的）
用法：python3 tools/mocap/motion_check.py unity/shots/motioncheck/p_startstop.csv [t0 t1]
      python3 tools/mocap/motion_check.py --dist a.csv b.csv [c.csv]   # 几个人之间的最近距离
      python3 tools/mocap/motion_check.py --top x.csv out.png          # 俯视脚印图"""
import csv, sys, math, os
import numpy as np
from PIL import Image, ImageDraw

BONES = ['Hips', 'Spine', 'Chest', 'Neck', 'Head', 'LeftUpperLeg', 'LeftLowerLeg', 'LeftFoot', 'LeftToes',
         'RightUpperLeg', 'RightLowerLeg', 'RightFoot', 'RightToes', 'LeftUpperArm', 'LeftLowerArm', 'LeftHand',
         'RightUpperArm', 'RightLowerArm', 'RightHand']


def load(path):
    rows = list(csv.DictReader(open(path)))
    t = np.array([float(r['t']) for r in rows])
    root = np.array([[float(r['root_x']), float(r['root_y']), float(r['root_z'])] for r in rows])
    fwd = np.array([[float(r['fwd_x']), 0, float(r['fwd_z'])] for r in rows])
    B = {b: np.array([[float(r[f'{b}_x']), float(r[f'{b}_y']), float(r[f'{b}_z'])] for r in rows]) for b in BONES}
    meta = [(r['pose'], r['act'], r['done'], r['loco']) for r in rows]
    return t, root, fwd, B, meta


def contacts(y, thr):
    on = y < thr
    spans = []
    i = 0
    while i < len(on):
        if on[i]:
            j = i
            while j + 1 < len(on) and on[j + 1]:
                j += 1
            spans.append((i, j))
            i = j + 1
        else:
            i += 1
    return spans


def hspeed(p, t):
    d = np.diff(p[:, [0, 2]], axis=0)
    dt = np.maximum(np.diff(t), 1e-4)
    return np.concatenate([[0], np.linalg.norm(d, axis=1) / dt])


def analyze(path, t0=None, t1=None, quiet=False):
    t, root, fwd, B, meta = load(path)
    sel = np.ones(len(t), bool)
    if t0 is not None:
        sel = (t >= t0) & (t <= t1)
    out = {}
    name = os.path.basename(path)[:-4]
    ry = root[:, 1]
    # 脚：踝和脚尖离地（相对根）
    res = []
    slide_events = []
    for side in ('Left', 'Right'):
        ank = B[side + 'Foot']
        toe = B[side + 'Toes']
        ha = ank[:, 1] - ry
        ht = toe[:, 1] - ry
        amin = np.percentile(ha[sel], 1)
        tmin = np.percentile(ht[sel], 1)
        va = hspeed(ank, t)
        vt = hspeed(toe, t)
        # 踩地：踝贴地（脚跟着地）或脚尖贴地
        heel = (ha < amin + 0.012)
        toed = (ht < tmin + 0.010)
        planted_v = []
        for i in np.where(sel)[0]:
            if i == 0:
                continue
            if heel[i] and heel[i - 1]:
                planted_v.append(va[i])
            elif toed[i] and toed[i - 1]:
                planted_v.append(vt[i])
        pv = np.array(planted_v) if planted_v else np.zeros(1)
        # 每次着地（脚尖或者脚跟贴地的连续段）脚在地上挪了多远：踝贴地时踝挪的 + 只有脚尖贴地时脚尖挪的
        on = (heel | toed) & sel
        spans = contacts(~on, 0.5)  # spans of off; easier: compute on-spans
        on_spans = []
        i = 0
        while i < len(on):
            if on[i]:
                j = i
                while j + 1 < len(on) and on[j + 1]:
                    j += 1
                on_spans.append((i, j))
                i = j + 1
            else:
                i += 1
        for (a, b) in on_spans:
            if b - a < 3:
                continue
            s = 0.0
            for k in range(a + 1, b + 1):
                if heel[k] and heel[k - 1]:
                    s += np.linalg.norm((ank[k] - ank[k - 1])[[0, 2]])
                elif toed[k] and toed[k - 1]:
                    s += np.linalg.norm((toe[k] - toe[k - 1])[[0, 2]])
            slide_events.append((side[0], t[a], t[b], s))
        res.append((side, float(pv.mean()), float(np.percentile(pv, 95)), float(pv.max()), len(pv)))
    out['slide'] = res
    out['contacts'] = slide_events
    # 根速度、角速度
    rs = hspeed(root, t)
    yaw = np.degrees(np.unwrap(np.arctan2(fwd[:, 0], fwd[:, 2])))
    yr = np.concatenate([[0], np.diff(yaw) / np.maximum(np.diff(t), 1e-4)])
    out['rootspeed'] = rs
    out['yawrate'] = yr
    # 身子朝向 vs 走的方向
    vel = np.vstack([[0, 0], np.diff(root[:, [0, 2]], axis=0) / np.maximum(np.diff(t), 1e-4)[:, None]])
    crab = []
    for i in np.where(sel)[0]:
        v = vel[i]
        if np.linalg.norm(v) > 0.35:
            f = fwd[i, [0, 2]]
            c = math.degrees(math.acos(np.clip(np.dot(v, f) / np.linalg.norm(v) / max(1e-6, np.linalg.norm(f)), -1, 1)))
            crab.append((c, t[i]))
    out['crab'] = max(crab) if crab else (0, 0)
    # 跳帧：骨骼相对根的位置，每帧偏离前后两帧中点多少（厘米）
    pops = []
    for b in ('Hips', 'Head', 'LeftHand', 'RightHand', 'LeftFoot', 'RightFoot', 'Chest'):
        rel = B[b] - root
        dev = np.zeros(len(t))
        dev[1:-1] = np.linalg.norm(rel[1:-1] - 0.5 * (rel[:-2] + rel[2:]), axis=1) * 100
        idx = np.where(sel)[0]
        idx = idx[(idx > 0) & (idx < len(t) - 1)]
        if len(idx):
            k = idx[np.argmax(dev[idx])]
            pops.append((b, float(dev[k]), float(t[k]), float(np.median(dev[idx]))))
    out['pops'] = pops
    # 世界里髋的速度跳变（相邻帧速度差，米/秒）
    hv = np.vstack([[0, 0, 0], np.diff(B['Hips'], axis=0) / np.maximum(np.diff(t), 1e-4)[:, None]])
    dv = np.zeros(len(t))
    dv[2:] = np.linalg.norm(hv[2:] - hv[1:-1], axis=1)
    idx = np.where(sel)[0]
    idx = idx[idx > 2]
    if len(idx):
        k = idx[np.argmax(dv[idx])]
        out['hipjerk'] = (float(dv[k]), float(t[k]), float(np.median(dv[idx])))
    # 头上下、髋上下、髋左右、手前后
    def local(p):
        d = p - root
        f = fwd / np.maximum(np.linalg.norm(fwd, axis=1, keepdims=True), 1e-6)
        r = np.stack([f[:, 2], np.zeros(len(f)), -f[:, 0]], 1)
        return np.stack([np.sum(d * r, 1), d[:, 1], np.sum(d * f, 1)], 1)
    H = local(B['Head']); P = local(B['Hips']); LH = local(B['LeftHand']); RH = local(B['RightHand'])
    s = sel
    out['bob'] = dict(head_y=float(np.ptp(H[s, 1])), hip_y=float(np.ptp(P[s, 1])), hip_x=float(np.ptp(P[s, 0])),
                      lhand_z=float(np.ptp(LH[s, 2])), rhand_z=float(np.ptp(RH[s, 2])), head_x=float(np.ptp(H[s, 0])),
                      hip_z_mean=float(P[s, 2].mean()))
    # 膝盖弯曲（度）：180 - 大腿和小腿夹角
    knees = {}
    for side in ('Left', 'Right'):
        a = B[side + 'UpperLeg']; k = B[side + 'LowerLeg']; f = B[side + 'Foot']
        u = k - a; v = f - k
        ang = np.degrees(np.arccos(np.clip(np.sum(u * v, 1) / np.linalg.norm(u, axis=1) / np.linalg.norm(v, axis=1), -1, 1)))
        knees[side] = (float(ang[s].min()), float(ang[s].max()))
    out['knee'] = knees
    # 步频：脚跟着地的时刻
    strikes = []
    for side in ('Left', 'Right'):
        ha = B[side + 'Foot'][:, 1] - ry
        amin = np.percentile(ha[sel], 1)
        heel = ha < amin + 0.012
        for i in np.where(sel)[0][1:]:
            if heel[i] and not heel[i - 1]:
                strikes.append((float(t[i]), side[0]))
    strikes.sort()
    out['strikes'] = strikes
    # 脚掌俯仰（踝→脚趾根，度，往下为负）：踝贴地、水平速度很小的帧（踩稳）取中位数
    pitch = {}
    planted = {}
    for side in ('Left', 'Right'):
        ank = B[side + 'Foot']; toe = B[side + 'Toes']
        d = toe - ank
        pt = np.degrees(np.arctan2(d[:, 1], np.linalg.norm(d[:, [0, 2]], axis=1)))
        ha = ank[:, 1] - ry; ht = toe[:, 1] - ry
        amin = np.percentile(ha[sel], 1); tmin = np.percentile(ht[sel], 1)
        va = hspeed(ank, t)
        flat = sel & (ha < amin + 0.015) & (ht < tmin + 0.015) & (va < 0.15)
        pitch[side] = float(np.median(pt[flat])) if flat.any() else float('nan')
        planted[side] = (ha < amin + 0.012) | (ht < tmin + 0.010)
    out['pitch'] = pitch
    # 两只脚都踩着地时，身子朝向转了多少度（原地像转盘一样转）
    yaw_all = np.degrees(np.unwrap(np.arctan2(fwd[:, 0], fwd[:, 2])))
    both = planted['Left'] & planted['Right']
    dy = np.abs(np.diff(yaw_all, prepend=yaw_all[0]))
    out['yaw_both'] = float(dy[sel & both].sum())
    out['yaw_total'] = float(np.abs(yaw_all[sel][-1] - yaw_all[sel][0]))
    dist = np.linalg.norm((root[s][-1] - root[s][0])[[0, 2]])
    T = t[s][-1] - t[s][0]
    out['avgspeed'] = dist / max(T, 1e-4)
    if not quiet:
        print(f'== {name} [{t[s][0]:.2f}-{t[s][-1]:.2f}s] 平均速度 {out["avgspeed"]:.2f} m/s')
        for side, m, p95, mx, n in res:
            print(f'  {side} 踩地帧滑速 均 {m:.3f} p95 {p95:.3f} 最大 {mx:.3f} m/s（{n} 帧）')
        big = [c for c in slide_events if c[3] > 0.02]
        print('  每次着地脚在地上挪了（>2cm）：', ' '.join(f'{c[0]}[{c[1]:.2f}-{c[2]:.2f}] {c[3]*100:.1f}cm' for c in big) or '无')
        print('  着地：', ' '.join(f'{x:.2f}{sd}' for x, sd in strikes))
        if len(strikes) > 2:
            iv = np.diff([x for x, _ in strikes])
            print(f'  步间隔 {np.round(iv, 2).tolist()}  → 步频 {60 / np.median(iv):.0f} 步/分')
        print(f'  头上下 {out["bob"]["head_y"]*100:.1f}cm 髋上下 {out["bob"]["hip_y"]*100:.1f}cm 髋左右 {out["bob"]["hip_x"]*100:.1f}cm 头左右 {out["bob"]["head_x"]*100:.1f}cm 左手前后 {out["bob"]["lhand_z"]*100:.1f}cm 右手前后 {out["bob"]["rhand_z"]*100:.1f}cm')
        print(f'  膝盖弯 左 {knees["Left"][0]:.0f}-{knees["Left"][1]:.0f} 右 {knees["Right"][0]:.0f}-{knees["Right"][1]:.0f} 度')
        print('  跳帧（偏离前后中点 cm，最大@时刻 / 中位）：', ' '.join(f'{b} {v:.2f}@{tt:.2f}/{md:.2f}' for b, v, tt, md in pops))
        if 'hipjerk' in out:
            print(f'  髋速度跳变 最大 {out["hipjerk"][0]:.2f} m/s @ {out["hipjerk"][1]:.2f}（中位 {out["hipjerk"][2]:.3f}）')
        print(f'  身子和走的方向最多差 {out["crab"][0]:.0f} 度 @ {out["crab"][1]:.2f}')
        print(f'  根速度 最大 {rs[s].max():.2f}；朝向角速度 最大 {np.abs(yr[s]).max():.0f} 度/秒')
        print(f'  脚掌踩稳时俯仰 左 {pitch["Left"]:.1f} 右 {pitch["Right"]:.1f} 度；两脚都踩着时转了 {out["yaw_both"]:.0f} 度（总共转 {out["yaw_total"]:.0f} 度）')
    return out, (t, root, fwd, B, meta)


def footprint(path, out_png, t0=None, t1=None, scale=110):
    t, root, fwd, B, meta = load(path)
    sel = np.ones(len(t), bool) if t0 is None else (t >= t0) & (t <= t1)
    ry = root[:, 1]
    pts = np.concatenate([root[sel], B['LeftFoot'][sel], B['RightFoot'][sel]])
    c = (pts.min(0) + pts.max(0)) / 2
    span = max(np.ptp(pts[:, 0]), np.ptp(pts[:, 2])) + 0.6
    S = int(span * scale) + 40
    S = min(max(S, 300), 900)
    scale = (S - 40) / span
    im = Image.new('RGB', (S, S), (248, 247, 242))
    d = ImageDraw.Draw(im)
    def P(p):
        return (S / 2 + (p[0] - c[0]) * scale, S / 2 - (p[2] - c[2]) * scale)
    for gx in np.arange(math.floor(c[0] - span), c[0] + span, 0.5):
        d.line([P((gx, 0, c[2] - span)), P((gx, 0, c[2] + span))], fill=(225, 225, 225))
    for gz in np.arange(math.floor(c[2] - span), c[2] + span, 0.5):
        d.line([P((c[0] - span, 0, gz)), P((c[0] + span, 0, gz))], fill=(225, 225, 225))
    for side, col, colp in (('Left', (255, 190, 190), (200, 20, 20)), ('Right', (190, 200, 255), (20, 60, 210))):
        ha = B[side + 'Foot'][:, 1] - ry
        ht = B[side + 'Toes'][:, 1] - ry
        amin = np.percentile(ha[sel], 1); tmin = np.percentile(ht[sel], 1)
        for i in np.where(sel)[0]:
            pl = ha[i] < amin + 0.012
            plt = ht[i] < tmin + 0.010
            x, y = P(B[side + 'Foot'][i])
            r = 3 if pl else 1
            d.ellipse([x - r, y - r, x + r, y + r], fill=colp if pl else col)
            x2, y2 = P(B[side + 'Toes'][i])
            if plt:
                d.rectangle([x2 - 2, y2 - 2, x2 + 2, y2 + 2], outline=colp)
    for i in np.where(sel)[0][::3]:
        x, y = P(root[i]); d.point((x, y), fill=(90, 90, 90))
        if i % 30 == 0:
            f = fwd[i]
            d.line([P(root[i]), P(root[i] + f * 0.25)], fill=(60, 160, 60), width=2)
    im.save(out_png)


def mindist(paths):
    """几个人（各自的 CSV，同一时间轴）两两之间水平最近距离"""
    R = [load(p)[1] for p in paths]
    n = min(len(r) for r in R)
    for i in range(len(R)):
        for j in range(i + 1, len(R)):
            d = np.linalg.norm((R[i][:n] - R[j][:n])[:, [0, 2]], axis=1)
            print(f'{os.path.basename(paths[i])} - {os.path.basename(paths[j])}: 最近 {d.min():.3f} 米')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == '--dist':
        mindist(a[1:])
    elif a[0] == '--top':
        footprint(a[1], a[2], *(float(x) for x in a[3:5]))
    else:
        p = a[0]
        t0 = float(a[1]) if len(a) > 2 else None
        t1 = float(a[2]) if len(a) > 2 else None
        analyze(p, t0, t1)
