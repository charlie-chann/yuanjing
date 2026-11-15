"""大殿匾额上的字：用应用里自带的思源宋体（开源）画成一张透明底的图，Unity 里贴在匾上当金字。
用法：python3 tools/unity/gen_plaque.py [字]
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
text = sys.argv[1] if len(sys.argv) > 1 else "愿境"
W, H = 1024, 384
img = Image.new("RGBA", (W, H), (255, 255, 255, 0))
font = ImageFont.truetype(str(ROOT / "assets/fonts/SourceHanSerifCN-Bold.otf"), 250)
d = ImageDraw.Draw(img)
gap = 110
widths = [d.textlength(c, font=font) for c in text]
x = (W - sum(widths) - gap * (len(text) - 1)) / 2
for c, w in zip(text, widths):
    box = d.textbbox((0, 0), c, font=font)
    d.text((x, (H - (box[3] - box[1])) / 2 - box[1]), c, font=font, fill=(255, 255, 255, 255))
    x += w + gap
out = ROOT / "unity/Sanctuary/Assets/Textures/gen_plaque_color.png"
img.save(out)
print(out)
