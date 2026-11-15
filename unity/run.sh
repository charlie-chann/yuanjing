#!/bin/sh
# 命令行调用 Unity 执行一个方法，只打印关键的日志。用法：unity/run.sh <方法> [其他参数...]
cd "$(dirname "$0")"
U=/Applications/Unity/Hub/Editor/6000.3.28f1/Unity.app/Contents/MacOS/Unity
METHOD="$1"; shift
"$U" -batchmode -quit -projectPath "$PWD/Sanctuary" -buildTarget iOS -executeMethod "$METHOD" -logFile "$PWD/run.log" "$@"
CODE=$?
grep -E "error CS|Shader error|\[yuanjing\]|Aborting batchmode|Exception:|NullReference" run.log | sort -u | head -40
exit $CODE
