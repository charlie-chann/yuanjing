"""把几张预览图拼成一张，方便一眼看完。用法：python3 sheet.py 输出名 图1 图2 ..."""
import sys
from PIL import Image
out, names = sys.argv[1], sys.argv[2:]
ims = [Image.open(f'preview/{n}.png').convert('RGB') for n in names]
cols = min(4, len(ims)); rows = (len(ims) + cols - 1) // cols
w = 1800 // cols
s = Image.new('RGB', (w * cols, w * rows), (30, 30, 30))
for i, im in enumerate(ims):
    s.paste(im.resize((w, w)), ((i % cols) * w, (i // cols) * w))
s.save(f'preview/_{out}.png'); print(s.size)
