"""给 Unity 工程准备材质贴图：每种材质三张 2K 图（颜色、法线、遮蔽粗糙金属合一），放到 unity/Sanctuary/Assets/Textures/。
来源 Poly Haven（CC0）。素材库 asset_library/ 里已经有的直接拷，没有的现下。用法：python3 tools/unity/prep_textures.py"""
import json
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "asset_library" / "polyhaven" / "textures"
OUT = ROOT / "unity" / "Sanctuary" / "Assets" / "Textures"
UA = {"User-Agent": "asset-fetch/1.0"}

# 工程里的名字 → Poly Haven 上的名字
TEXTURES = {
    "roof_grey": "grey_roof_tiles_02", "roof_slate": "roof_slates_02", "roof_clay": "clay_roof_tiles_02",
    "wood_dark": "dark_wooden_planks", "wood_floor": "hinoki_planks", "wood_old": "weathered_brown_planks", "wood_cedar": "japanese_cedar_planks",
    "paving": "stone_tiles_02", "paving_large": "large_floor_tiles_02", "cobble": "mossy_cobblestone",
    "plaster": "plastered_wall_04", "plaster_old": "worn_mossy_plasterwall", "stone_block": "medieval_blocks_02", "sandstone": "large_sandstone_blocks",
    "stone_wall": "japanese_stone_wall", "bark": "japanese_camphor_bark", "bark_pine": "pine_bark",
    "grass": "leafy_grass", "gravel": "gravel_floor_02", "moss_rock": "mossy_rock", "snow": "snow_02", "forest_floor": "forest_leaves_03",
    "linen": "rough_linen", "fabric": "fabric_pattern_07", "bronze": "green_metal_rust", "metal_rust": "rusty_metal_04", "granite": "granite_tile", "concrete": "concrete_floor_worn_001",
}
MAPS = {"color": "Diffuse", "normal": "nor_gl", "arm": "arm"}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180).read()


OUT.mkdir(parents=True, exist_ok=True)
for name, asset in TEXTURES.items():
    if all(any(OUT.glob(f"{name}_{k}.*")) for k in MAPS):
        continue
    files = None
    for kind, key in MAPS.items():
        if any(OUT.glob(f"{name}_{kind}.*")):
            continue
        have = list((LIB / asset).glob(f"{asset}_{kind}_2k.*"))
        if have:
            shutil.copy(have[0], OUT / f"{name}_{kind}{have[0].suffix}")
            continue
        files = files or json.loads(get(f"https://api.polyhaven.com/files/{asset}"))
        e = files.get(key, {}).get("2k", {})
        e = e.get("jpg") or e.get("png")
        if not e:
            print("没有", name, kind)
            continue
        (OUT / f"{name}_{kind}.{e['url'].rsplit('.', 1)[1]}").write_bytes(get(e["url"]))
    print("贴图", name, flush=True)
print("完成", sum(p.stat().st_size for p in OUT.glob("*")) // 1048576, "MB")
