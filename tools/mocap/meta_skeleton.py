"""看走路 FBX 导入后 Unity 用的人形基准（.meta 里 humanDescription.skeleton）是不是标准 T 字：
左右脚踝→脚趾根的俯仰要一样、膝盖不弯。基准要是走路的某一帧，套到人物上那只脚就一直翘着或扣着走。
用法：python3 tools/mocap/meta_skeleton.py unity/Sanctuary/Assets/Motion/Walk_*.fbx.meta"""
import re, sys, glob, os, numpy as np
def qmul(a, b):
    w1, x1, y1, z1 = a; w2, x2, y2, z2 = b
    return np.array([w1*w2-x1*x2-y1*y2-z1*z2, w1*x2+x1*w2+y1*z2-z1*y2, w1*y2-x1*z2+y1*w2+z1*x2, w1*z2+x1*y2-y1*x2+z1*w2])
def qrot(q, v):
    return qmul(qmul(q, np.array([0, *v])), q * np.array([1, -1, -1, -1]))[1:]
def load(path):
    s = open(path).read()
    sk = s[s.index('    skeleton:'):]
    ents = re.findall(r"- name: (.*?)\n\s+parentName: (.*?)\n\s+position: \{x: (.*?), y: (.*?), z: (.*?)\}\n\s+rotation: \{x: (.*?), y: (.*?), z: (.*?), w: (.*?)\}", sk)
    B = {}
    for e in ents:
        n, par = e[0].strip(), e[1].strip()
        p = np.array(list(map(float, e[2:5]))); r = np.array([float(e[8]), float(e[5]), float(e[6]), float(e[7])])
        if n in B: continue
        B[n] = (par, p, r)
    G = {}
    def glob_(n):
        if n in G: return G[n]
        par, p, r = B[n]
        if par == '' or par not in B:
            G[n] = (p, r)
        else:
            pp, pr = glob_(par)
            G[n] = (pp + qrot(pr, p), qmul(pr, r))
        return G[n]
    for n in B: glob_(n)
    return G
for path in sorted(sys.argv[1:]):
    G = load(path)
    out = []
    for s in ('Left', 'Right'):
        a = G[s + 'Foot'][0]; t = G[s + 'ToeBase'][0]; k = G[s + 'Leg'][0]; h = G[s + 'UpLeg'][0]
        d = t - a
        # up axis: find from hips->head
        out.append((s, d))
    up = G['Head'][0] - G['Hips'][0]; up /= np.linalg.norm(up)
    res = []
    for s in ('Left', 'Right'):
        a = G[s + 'Foot'][0]; t = G[s + 'ToeBase'][0]; k = G[s + 'Leg'][0]; h = G[s + 'UpLeg'][0]
        d = t - a
        pitch = np.degrees(np.arcsin(np.dot(d, up) / np.linalg.norm(d)))
        u = k - h; v = a - k
        knee = np.degrees(np.arccos(np.dot(u, v) / np.linalg.norm(u) / np.linalg.norm(v)))
        res.append(f'{s[0]} toe {pitch:+5.1f} knee {knee:4.1f}')
    sh = G['LeftArm'][0] - G['LeftShoulder'][0]
    print(f'{os.path.basename(path):32s} ' + '  '.join(res) + f'  head-up {np.degrees(np.arccos(np.clip(np.dot((G["Head"][0]-G["Neck"][0])/np.linalg.norm(G["Head"][0]-G["Neck"][0]), up),-1,1))):.1f}')
