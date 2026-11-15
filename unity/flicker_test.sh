#!/bin/sh
# 用法：YJ_OFF=walkers unity/flicker_test.sh
cd "$(dirname "$0")"
U=/Applications/Unity/Hub/Editor/6000.3.28f1/Unity.app/Contents/MacOS/Unity
"$U" -batchmode -projectPath "$PWD/Sanctuary" -buildTarget iOS -runTests -testPlatform PlayMode -testFilter FlickerTest -testResults "$PWD/test.xml" -logFile "$PWD/test.log" >/dev/null 2>&1
grep "地面亮度\|error CS" test.log | head -3
