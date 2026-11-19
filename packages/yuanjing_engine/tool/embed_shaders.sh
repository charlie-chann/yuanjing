#!/bin/sh
# 把 shaders/stage.metal 嵌成 Swift 字符串（运行时编译，不依赖打包方式）。改完着色器后运行一次。
set -e
cd "$(dirname "$0")/.."
# 先编译一遍查错。这台机器没装 Metal 工具链（xcodebuild -downloadComponent MetalToolchain）时跳过，
# 改用 tool/preview 渲染几帧来查：那边是运行时编译，有错会直接报出来。
if xcrun -sdk iphonesimulator metal --version >/dev/null 2>&1; then xcrun -sdk iphonesimulator metal -c shaders/stage.metal -o /dev/null; else echo "没有 Metal 工具链，跳过编译检查"; fi
OUT=ios/yuanjing_engine/Sources/yuanjing_engine/StageShaderSource.swift
{ printf '// 由 tool/embed_shaders.sh 生成，不要手改。源文件：shaders/stage.metal\nlet stageShaderSource = #"""\n'; cat shaders/stage.metal; printf '"""#\n'; } > "$OUT"
echo "embedded -> $OUT"
