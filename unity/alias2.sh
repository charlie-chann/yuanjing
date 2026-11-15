#!/bin/sh
# 量「闪」：正常分辨率 和 4 倍分辨率缩回来 的差。差得越多，走动时那里越闪。
# 用法：unity/alias2.sh <名字> "<镜头位置>" "<看向>"
cd "$(dirname "$0")"
rm -f shots/_*.png
./run.sh SanctuaryBuild.Preview -scene ${SCENE:-Temple} -quality 5 -width 603 -height 1311 -shots "_n|$2|$3|day|clear|72" > /dev/null || exit 1
./run.sh SanctuaryBuild.Preview -scene ${SCENE:-Temple} -quality 5 -width 2412 -height 5244 -shots "_s|$2|$3|day|clear|72" > /dev/null || exit 1
python3 - "$1" <<'PY'
import sys
import numpy as np
from PIL import Image
n = np.asarray(Image.open('shots/_n.png').convert('L'), dtype=np.float32)
s = np.asarray(Image.open('shots/_s.png').convert('L').resize((603, 1311), Image.BOX), dtype=np.float32)
d = np.abs(n - s)
h = d.shape[0]
print(f"{sys.argv[1]}: 闪烁分 {d.mean():.2f}  上半（屋顶）{d[:h//2].mean():.2f}  下半（地面）{d[h//2:].mean():.2f}")
Image.fromarray(np.clip(d * 6, 0, 255).astype(np.uint8)).save(f'shots/{sys.argv[1]}_alias.png')
PY
