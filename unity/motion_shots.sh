#!/bin/sh
# 给一段动作出逐帧图：unity/motion_shots.sh 动作名 "0,0.5,1" [人物] [朝向]
cd "$(dirname "$0")"
rm -f shots/m_$1_*.png
./run.sh MotionPreview.Run -clip "$1" -times "$2" -who "${3:-shino}" -yaw "${4:-0}" || exit 1
python3 - "$1" <<'PY'
import sys, glob
from PIL import Image
n = sys.argv[1]
fs = sorted(glob.glob(f'shots/m_{n}_*_f.png'))
if not fs: sys.exit('没有图')
ims = [(Image.open(f), Image.open(f.replace('_f.png', '_s.png'))) for f in fs]
w, h = ims[0][0].size
k = 0.5 if len(ims) > 4 else 0.7
w2, h2 = int(w * k), int(h * k)
s = Image.new('RGB', (w2 * len(ims), h2 * 2))
for i, (a, b) in enumerate(ims):
    s.paste(a.resize((w2, h2)), (i * w2, 0)); s.paste(b.resize((w2, h2)), (i * w2, h2))
s.save(f'shots/motion_{n}.png'); print(f'shots/motion_{n}.png', s.size)
PY
