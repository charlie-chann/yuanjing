"""把免费的实拍贴图（asset_library 里的 Poly Haven、ambientCG，CC0）处理成手绘感，给湖心小寺的表面着色器用。

每套输出到 unity/Sanctuary/Assets/Toon/Textures/：
  m_<名字>_c.png   颜色：用 Kuwahara 滤镜抹成一笔一笔的色块（细碎的噪点没了，边界还在），
                   再按高度图把凹下去的地方压暗、最深的缝描成墨线（树皮的裂、石缝、木纹的沟），漫画里就是这么画的
  m_<名字>_n.png   法线：原样（凹凸的细节靠它，凑近看木纹、石头的麻点都在）
  tex_meta.json    每套颜色的平均值、铺一遍几米。着色器用「贴图 ÷ 平均值」当明暗纹理乘到模型自己的颜色上，
                   这样全岛还是一套配色，贴图只负责细节

用法：tools/textures/.venv/bin/python tools/textures/prep.py [名字 ...]
"""
import glob
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import uniform_filter

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, '..', '..', 'asset_library')
OUT = os.path.join(HERE, '..', '..', 'unity', 'Sanctuary', 'Assets', 'Toon', 'Textures')

# 名字 → (素材库里的目录, 笔触大小, 一遍铺几米, 说明, 凹处压多暗 0..1)
SETS = {
    'bark': ('polyhaven/textures/japanese_camphor_bark', 4, 2.0, '樟树皮：许愿树', 0.8),
    'bark_dark': ('polyhaven/textures/sakura_bark', 4, 1.6, '樱树皮：花树、枫', 0.75),
    'stone': ('ambientcg/Rock030', 4, 1.3, '青石：石灯笼、石栏、台基', 0.55),
    'slab': ('polyhaven/textures/granite_tile', 5, 1.6, '石板：铺地', 0.6),
    'wood': ('polyhaven/textures/hinoki_planks', 4, 1.2, '原木：木桩、长凳、码头', 0.5),
    'wood_dark': ('polyhaven/textures/weathered_planks', 4, 1.4, '旧木：深色木件', 0.6),
    'lacquer': ('polyhaven/textures/lacquered_cherry_wood', 3, 1.0, '漆木：柱子、门窗', 0.25),
    'soil': ('ambientcg/Ground037', 4, 1.5, '土和草根：地面的细纹', 0.45),
    'straw': ('ambientcg/Wicker003', 3, 0.35, '草编：蒲团、绳', 0.7),
    'cloth': ('ambientcg/Fabric030', 2, 0.25, '布：布条、衣服', 0.35),
    'tile': ('ambientcg/Clay002', 3, 0.6, '陶瓦：瓦面、筒瓦、屋脊（瓦的形状是模型做的，贴图只给陶土的颗粒和釉面的斑驳）', 0.45),
    'brick': ('polyhaven/textures/red_brick', 4, 1.4, '砖：台基、墙裙（砖缝描线）', 0.85),
    'plaster': ('polyhaven/textures/white_plaster_rough_01', 4, 1.6, '粉墙：墙身', 0.5),
    'bronze': ('ambientcg/Metal025', 3, 0.5, '老铜：香炉、铜钟（凹处铜绿由模型的顶点色给）', 0.7),
}


def find(d, *keys):
    for k in keys:
        f = glob.glob(os.path.join(LIB, d, k))
        if f:
            return f[0]
    return None


def kuwahara(img, r):
    """经典 Kuwahara：每个点看左上、右上、左下、右下四个小窗口，取最「平」的那个窗口的平均色。
    结果是一块块平涂的颜色，边界保留。边缘按平铺处理（贴图是无缝的，处理完还得无缝）"""
    lum = img.mean(axis=2)
    size = 2 * r + 1                      # 先算以每个点为中心的窗口，再挪半个窗口变成四个角上的窗口
    m = uniform_filter(lum, size=r + 1, mode='wrap')
    m2 = uniform_filter(lum * lum, size=r + 1, mode='wrap')
    var = m2 - m * m
    mean = np.stack([uniform_filter(img[..., c], size=r + 1, mode='wrap') for c in range(3)], axis=2)
    h = (r + 1) // 2
    best_var, out = None, None
    for dy in (-h, h):
        for dx in (-h, h):
            v = np.roll(var, (dy, dx), axis=(0, 1))
            c = np.roll(mean, (dy, dx), axis=(0, 1))
            if best_var is None:
                best_var, out = v, c
            else:
                pick = v < best_var
                best_var = np.where(pick, v, best_var)
                out = np.where(pick[..., None], c, out)
    _ = size
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    meta_path = os.path.join(OUT, 'tex_meta.json')
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    names = sys.argv[1:] or list(SETS)
    for name in names:
        d, r, tile, what, cav = SETS[name]
        c = find(d, '*_color_2k.jpg', '*_diff_2k.jpg', '*_Color.jpg')
        n = find(d, '*_normal_2k.jpg', '*_nor_gl_2k.jpg', '*_NormalGL.jpg')
        if not c or not n:
            print('缺文件', name, d)
            continue
        img = np.asarray(Image.open(c).convert('RGB'), dtype=np.float32) / 255
        # 两遍：先小笔触再大笔触，色块更干净
        k = kuwahara(kuwahara(img, max(2, r - 1)), r)
        # 留三成原图的细节：纯色块凑近看太「塑料」，带一点原本的纤维和麻点才耐看
        k = k * 0.7 + img * 0.3
        # 凹处压暗、最深的缝描线：高度图拉到 0..1（去掉两头 2% 的极端值），再乘上遮蔽图
        hf = find(d, '*_height_2k.jpg', '*_disp_2k.jpg', '*_Displacement.jpg')
        af = find(d, '*_ao_2k.jpg', '*_AmbientOcclusion.jpg')
        if hf:
            h = np.asarray(Image.open(hf).convert('L').resize(img.shape[1::-1]), dtype=np.float32) / 255
            lo, hi = np.percentile(h, 2), np.percentile(h, 98)
            h = np.clip((h - lo) / max(1e-4, hi - lo), 0, 1)
            shade = 1 - cav * 0.55 * (1 - h) ** 1.5                      # 越凹越暗
            line = np.clip((0.22 - h) / 0.1, 0, 1) * cav                 # 最深的两成：墨线
            shade *= 1 - 0.6 * line
            shade *= 1 + cav * 0.22 * np.clip((h - 0.7) / 0.3, 0, 1)     # 凸起的棱提亮一点
            k = k * shade[..., None]
        if af:
            ao = np.asarray(Image.open(af).convert('L').resize(img.shape[1::-1]), dtype=np.float32) / 255
            k = k * (1 - cav * 0.5 * (1 - ao))[..., None]
        mean = k.reshape(-1, 3).mean(axis=0)
        Image.fromarray((np.clip(k, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, f'm_{name}_c.png'))
        Image.open(n).convert('RGB').save(os.path.join(OUT, f'm_{name}_n.png'))
        meta[name] = {'mean': [round(float(x), 4) for x in mean], 'tile': tile, 'from': d, 'what': what}
        print(f'{name:10s} {what}  平均色 {np.round(mean, 3)}', flush=True)
    json.dump(meta, open(meta_path, 'w'), ensure_ascii=False, indent=1)


main()
