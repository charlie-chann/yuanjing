"""把 Poly Haven 的 glTF 植物模型转成 Unity 原生能读的 OBJ（每个变体一个文件），贴图拷到同一个目录。
glTF 是 Y 朝上、右手系；OBJ 也是，Unity 导入时会自己翻 X。
用法：python3 tools/unity/gltf_to_obj.py <模型名> [<模型名>...]
"""
import base64, json, shutil, struct, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "asset_library/polyhaven/models"
DST = ROOT / "unity/Sanctuary/Assets/Plants"
CT = {5126: ("f", 4), 5123: ("H", 2), 5125: ("I", 4), 5121: ("B", 1)}
N = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def quat_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def convert(name):
    d = SRC / name
    gltf = next(d.glob("*.gltf"))
    g = json.loads(gltf.read_text())
    buf = (d / g["buffers"][0]["uri"]).read_bytes()

    def acc(i):
        a = g["accessors"][i]
        bv = g["bufferViews"][a["bufferView"]]
        fmt, size = CT[a["componentType"]]
        n = N[a["type"]]
        off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        stride = bv.get("byteStride", size * n)
        out = np.empty((a["count"], n), dtype=np.float64)
        for k in range(a["count"]):
            out[k] = struct.unpack_from("<" + fmt * n, buf, off + k * stride)
        return out

    out = DST / name
    out.mkdir(parents=True, exist_ok=True)
    for img in g["images"]:
        src = d / img["uri"]
        if src.exists() and "diff" in src.name or "arm" in src.name:
            shutil.copy(src, out / src.name)
    files = []
    for node in g["nodes"]:
        if "mesh" not in node:
            continue
        m = g["meshes"][node["mesh"]]
        R = quat_mat(node.get("rotation", [0, 0, 0, 1]))
        S = np.array(node.get("scale", [1, 1, 1]))
        lines, base = [], 1
        for p in m["primitives"]:
            P = acc(p["attributes"]["POSITION"]) * S @ R.T
            Nn = acc(p["attributes"]["NORMAL"]) @ R.T
            UV = acc(p["attributes"]["TEXCOORD_0"])
            I = acc(p["indices"]).astype(int).ravel()
            # 每个变体放在原点上：底部中心对齐到 0
            c = np.array([(P[:, 0].min() + P[:, 0].max()) / 2, P[:, 1].min(), (P[:, 2].min() + P[:, 2].max()) / 2])
            P = P - c
            lines += [f"v {x:.5f} {y:.5f} {z:.5f}" for x, y, z in P]
            lines += [f"vn {x:.5f} {y:.5f} {z:.5f}" for x, y, z in Nn]
            lines += [f"vt {u:.5f} {1 - v:.5f}" for u, v in UV]
            for t in range(0, len(I), 3):
                a, b, cc = I[t] + base, I[t + 1] + base, I[t + 2] + base
                lines.append(f"f {a}/{a}/{a} {b}/{b}/{b} {cc}/{cc}/{cc}")
            base += len(P)
        fn = out / f"{node.get('name', name)}.obj"
        fn.write_text("\n".join(lines) + "\n")
        files.append(fn.name)
    print(name, files)


for n in sys.argv[1:]:
    convert(n)
