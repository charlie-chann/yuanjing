"""湖心小寺的统一配色。所有模型只从这里取色，保证画面是一套颜色。
颜色按屏幕上看到的样子写（sRGB），存进顶点色，着色器里再换算。"""
import colorsys
import random


def hexc(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


P = {k: hexc(v) for k, v in {
    # 地面
    'grass': '#93c356', 'grass_lit': '#b1d667', 'grass_dark': '#74ab4a', 'grass_deep': '#5c9648',
    'sand': '#f0deaa', 'sand_wet': '#dcc68c', 'sand_deep': '#b9b184', 'dirt': '#cdaa78', 'dirt_dark': '#b08e62',
    'lakebed': '#8fb5a0', 'lakebed_deep': '#4f8f96',
    # 石头
    'stone': '#bdb8ab', 'stone_lit': '#d9d4c6', 'stone_dark': '#96928a', 'stone_deep': '#7a7773',
    'slab': '#cfc8b6', 'slab_b': '#c2baa6', 'slab_c': '#d8d2c2', 'moss': '#86a659',
    # 木头
    'wood': '#b07a45', 'wood_lit': '#cf9b62', 'wood_dark': '#825634', 'wood_deep': '#63402a',
    'plank': '#c08a55', 'plank_b': '#b47d4a', 'plank_c': '#cb9865',
    'red': '#cf4a33', 'red_lit': '#e2644a', 'red_dark': '#a23726', 'red_deep': '#7f2a20',
    # 屋顶和墙
    'tile': '#41656f', 'tile_lit': '#5b8891', 'tile_dark': '#30505a', 'ridge': '#2a424b', 'ridge_lit': '#3b5d67',
    'wall': '#f3e8cf', 'wall_dark': '#e2d4b2', 'gold': '#e8bb4d', 'gold_dark': '#c39535', 'navy': '#2c4a6b',
    'lattice': '#8c3a2a', 'paper': '#f7efd9',
    # 树和草
    'leaf': '#62a655', 'leaf_lit': '#8fca62', 'leaf_dark': '#44864c', 'leaf_deep': '#35703f',
    'pine': '#3f8162', 'pine_lit': '#5aa377', 'pine_dark': '#2d6650',
    'maple': '#e4633b', 'maple_lit': '#f59542', 'maple_dark': '#bf432f',
    'ginkgo': '#f4ca45', 'ginkgo_lit': '#fbe07a', 'blossom': '#f6adc0', 'blossom_lit': '#fbd3dc', 'blossom_dark': '#e78aa5',
    'trunk': '#80603f', 'trunk_lit': '#9c7850', 'trunk_dark': '#5f4430',
    'bamboo': '#8dbb55', 'bamboo_dark': '#6f9f48', 'bamboo_leaf': '#79b457',
    'reed': '#b9c36a', 'flower_w': '#fbf6ea', 'flower_y': '#f8d45c', 'flower_p': '#f29ab6', 'flower_v': '#b59be6',
    # 水里的
    'pad': '#63ad6c', 'pad_lit': '#86c97c', 'pad_dark': '#4a9460', 'lotus': '#f5a5ba', 'lotus_lit': '#fcd6df',
    'koi': '#f2802f', 'koi_w': '#fbf3e6', 'koi_r': '#e2472f',
    # 器物
    'bronze': '#6f7257', 'bronze_lit': '#93936b', 'bronze_dark': '#515543', 'ash': '#ddd6c6',
    'straw': '#d2aa60', 'straw_lit': '#e6c682', 'straw_dark': '#b08843',
    'cloth_red': '#d6402f', 'rope': '#dcc790', 'rope_dark': '#b9a26c', 'glow': '#ffdf9a', 'white': '#fbf7ee',
    'boat': '#a9683c', 'boat_dark': '#7c4a2c', 'boat_lit': '#c98a55',
}.items()}


def C(name):
    return P[name]


def tint(c, dv=0.0, ds=0.0, dh=0.0):
    """微调一个颜色：亮度、鲜艳度、色相"""
    h, s, v = colorsys.rgb_to_hsv(*c[:3])
    return colorsys.hsv_to_rgb((h + dh) % 1.0, min(1, max(0, s + ds)), min(1, max(0, v + dv)))


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def vary(c, rng: random.Random, v=0.04, s=0.03, h=0.01):
    return tint(c, rng.uniform(-v, v), rng.uniform(-s, s), rng.uniform(-h, h))
