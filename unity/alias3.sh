#!/bin/sh
# 对比哪样效果导致走动闪烁：unity/alias3.sh <天色> <天气> "<要关的,逗号分隔>"
cd "$(dirname "$0")"
rm -f shots/_*.png
SHOTS=""
for i in 0 1 2 3 4 5; do
  Z=$(python3 -c "print(f'0,1.9,{-11.9+$i*0.03:.3f}')"); L=$(python3 -c "print(f'0,0.9,{-8.6+$i*0.03:.3f}')")
  SHOTS="${SHOTS}_f$i|$Z|$L|$1|$2|62;"
done
./run.sh SanctuaryBuild.Preview -scene Temple -msaa 1 -off "$3" -width 603 -height 1311 -shots "$SHOTS" > /dev/null || exit 1
python3 - "$1/$2 关:$3" <<'PY'
import sys, glob
import numpy as np
from PIL import Image
fs = sorted(glob.glob('shots/_f*.png'))
ims = [np.asarray(Image.open(f).convert('L'), dtype=np.float32) for f in fs]
d = [np.abs(a - b) for a, b in zip(ims, ims[1:])]
h = ims[0].shape[0]
print(f"{sys.argv[1]:28s} 闪烁 全图 {np.mean([x.mean() for x in d]):.2f}  地面 {np.mean([x[h//2:].mean() for x in d]):.2f}  上半 {np.mean([x[:h//2].mean() for x in d]):.2f}")
PY
