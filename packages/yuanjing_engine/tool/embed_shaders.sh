#!/bin/sh
# 把 shaders/stage.metal 嵌成 Swift 字符串（运行时编译，不依赖打包方式）。改完着色器后运行一次。
set -e
cd "$(dirname "$0")/.."
xcrun -sdk iphonesimulator metal -c shaders/stage.metal -o /dev/null
OUT=ios/yuanjing_engine/Sources/yuanjing_engine/StageShaderSource.swift
{ printf '// 由 tool/embed_shaders.sh 生成，不要手改。源文件：shaders/stage.metal\nlet stageShaderSource = #"""\n'; cat shaders/stage.metal; printf '"""#\n'; } > "$OUT"
echo "embedded -> $OUT"
