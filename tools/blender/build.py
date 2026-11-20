"""在 Blender 里生成全部模型。用法见 build_all.sh。
blender -b --factory-startup --python tools/blender/build.py -- [模型名 ...]
不带名字就全部生成。"""
import importlib
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import kit  # noqa: E402

# trees 排在 plants 后面：同名的树用新做法的那棵
MODULES = ['props', 'props_hd', 'plants', 'trees', 'flowers', 'buildings', 'terrain', 'animals', 'critters_hd',
           'hall_props', 'statues',  # 大殿里的陈设、佛像（2026-11-17）
           'bodhisattva', 'bell_props', 'fishing_props', 'gifts']  # 观音、石凳和钟、钓具和鱼、小动物的礼物（2026-11-19）


def main():
    names = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    kit.setup_scene()
    table = {}
    for m in MODULES:
        try:
            mod = importlib.import_module(m)
        except ModuleNotFoundError as e:
            if e.name != m:
                raise
            continue
        except Exception as e:  # 别的模块正改到一半（语法错误等）不影响生成其他模型
            print(f'[yjm] 跳过模块 {m}：{type(e).__name__}: {e}')
            continue
        table.update(getattr(mod, 'ASSETS', {}))
    todo = names or list(table)
    total = 0
    for n in todo:
        if n not in table:
            print(f'[yjm] 没有这个模型：{n}')
            continue
        t = time.time()
        a = table[n](n)
        tris = a if isinstance(a, int) else 0
        total += tris
        print(f'[yjm] {n} 用时 {time.time() - t:.1f}s')
    print(f'[yjm] 共 {len(todo)} 个，{total} 个三角形')


main()
