#!/bin/sh
# 小人的预览图。用法：unity/folk.sh <拼图名> "<样子|姿势|鞠躬|动作|位置|朝向|名字;...>" "<镜头;...>" [build]
cd "$(dirname "$0")"
[ "$4" = "build" ] && { ./run.sh SanctuaryBuild.BuildFolk || exit 1; }
rm -f shots/_*.png
./run.sh SanctuaryBuild.FolkPreview -scene ${SCENE:-Temple} -pilgrims 0 -width ${W:-603} -height ${H:-1311} -poses "$2" -shots "$3" || exit 1
python3 - "$1" <<'PY'
import sys, glob
from PIL import Image
fs = sorted(glob.glob('shots/_*.png'))
ims = [Image.open(f).convert('RGB') for f in fs]
n = len(ims); w = min(450, 1800 // n); h = int(w * ims[0].size[1] / ims[0].size[0]); w = w if ims[0].size[0] < ims[0].size[1] else min(1800, 1800 // n)
s = Image.new('RGB', (w * n, h))
for i, im in enumerate(ims): s.paste(im.resize((w, h)), (i * w, 0))
s.save(f'shots/{sys.argv[1]}.png'); print(sys.argv[1], s.size)
PY
