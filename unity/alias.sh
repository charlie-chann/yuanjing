#!/bin/sh
# 量「闪」的程度：同一个镜头往前挪几厘米连拍几张，算相邻两张里细节区域的变化有多大（越小越稳）。
# 用法：unity/alias.sh <名字> <画质档> "<镜头位置>" "<看向>"
cd "$(dirname "$0")"
rm -f shots/_*.png
SHOTS=""
for i in 0 1 2 3 4 5; do
  Z=$(python3 -c "p='$3'.split(',');print(f'{p[0]},{p[1]},{float(p[2])+$i*0.035:.3f}')")
  L=$(python3 -c "p='$4'.split(',');print(f'{p[0]},{p[1]},{float(p[2])+$i*0.035:.3f}')")
  SHOTS="${SHOTS}_f$i|$Z|$L|day|clear|72;"
done
./run.sh SanctuaryBuild.Preview -scene ${SCENE:-Temple} -quality $2 -width 603 -height 1311 -shots "$SHOTS" > /dev/null || exit 1
python3 - "$1" <<'PY'
import sys, glob
import numpy as np
from PIL import Image
fs = sorted(glob.glob('shots/_f*.png'))
ims = [np.asarray(Image.open(f).convert('L'), dtype=np.float32) for f in fs]
# 整体平移一致地挪了一点，相邻帧的差主要来自「闪」：取差值最大的 2% 像素的平均作为闪烁分
d = [np.abs(a - b) for a, b in zip(ims, ims[1:])]
score = np.mean([np.mean(np.sort(x.ravel())[-int(x.size * 0.02):]) for x in d])
mean = np.mean([x.mean() for x in d])
print(f"{sys.argv[1]}: 闪烁分 {score:.1f}  平均变化 {mean:.2f}")
heat = np.max(d, axis=0)
Image.fromarray(np.clip(heat * 4, 0, 255).astype(np.uint8)).save(f'shots/{sys.argv[1]}_heat.png')
Image.open(fs[0]).save(f'shots/{sys.argv[1]}_frame.png')
PY
