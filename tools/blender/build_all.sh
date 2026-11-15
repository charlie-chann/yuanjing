#!/bin/sh
# 用 Blender 生成湖心小寺的模型，导出到 unity/Sanctuary/Assets/Toon/Models，预览图在 tools/blender/preview。
# 用法：tools/blender/build_all.sh [模型名 ...]    不带名字就全部重做。YJ_PREVIEW=0 不出预览图（快）。
cd "$(dirname "$0")"
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python build.py -- "$@" 2>&1 \
  | grep -E "^\[yjm\]|Error|Traceback|File \"|^\s+\^|Exception|error:" | grep -v "^Blender"
