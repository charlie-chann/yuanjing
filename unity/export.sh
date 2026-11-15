#!/bin/sh
# 把 Unity 工程导出到 Flutter 工程的 ios/unityLibrary。用法：unity/export.sh [-simulator] [要执行的方法]
# 默认执行 SanctuaryBuild.BuildAndExport（生成场景并导出）。带 -simulator 导出模拟器版，否则导出真机版。
cd "$(dirname "$0")"
U=/Applications/Unity/Hub/Editor/6000.3.28f1/Unity.app/Contents/MacOS/Unity
SIM=""; [ "$1" = "-simulator" ] && SIM="-simulator" && shift
METHOD="${1:-SanctuaryBuild.BuildAndExport}"
"$U" -batchmode -quit -projectPath "$PWD/Sanctuary" -buildTarget iOS $SIM -executeMethod "$METHOD" -exportPath "$PWD/../ios/unityLibrary" -logFile "$PWD/export.log"
CODE=$?
grep -E "error CS|\[yuanjing\]|Building project for Flutter|Aborting batchmode|Exception:" export.log | sort -u | head -30
exit $CODE
