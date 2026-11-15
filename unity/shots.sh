#!/bin/sh
# 生成场景并出一组预览图，拼成一张。用法：unity/shots.sh <拼图名字> "<镜头;镜头;...>" [build]
cd "$(dirname "$0")"
[ "$3" = "build" ] && { ./run.sh SanctuaryBuild.Build${SCENE:-Temple} || exit 1; }
rm -f shots/_*.png
./run.sh SanctuaryBuild.Preview -scene ${SCENE:-Temple} -width 603 -height 1311 -shots "$2" ${PLAYER:+-player "$PLAYER"} ${PET:+-pet "$PET"} || exit 1
python3 - "$1" <<'PY'
import sys, glob
from PIL import Image
fs = sorted(glob.glob('shots/_*.png'))
ims = [Image.open(f).convert('RGB') for f in fs]
n = len(ims); w = min(450, 1800 // n); h = int(w * 1311 / 603)
s = Image.new('RGB', (w * n, h))
for i, im in enumerate(ims): s.paste(im.resize((w, h)), (i * w, 0))
s.save(f'shots/{sys.argv[1]}.png'); print(sys.argv[1], s.size)
PY
