#!/bin/sh
# 在编辑器里跑运行模式测试：unity/playtest.sh <测试类名>   （YJ_SCENE=Chapel 换场景）
cd "$(dirname "$0")"
U=/Applications/Unity/Hub/Editor/6000.3.28f1/Unity.app/Contents/MacOS/Unity
rm -f test.xml
"$U" -batchmode -projectPath "$PWD/Sanctuary" -buildTarget iOS -runTests -testPlatform PlayMode -testFilter "$1" -testResults "$PWD/test.xml" -logFile "$PWD/test.log" >/dev/null 2>&1
grep "error CS" test.log | sort -u | head -5
grep "\[yuanjing\] 坐稳测试\|\[yuanjing\] 镜头距离\|\[yuanjing\] 视角闪烁\|无效数" test.log | sort -u | head -6 | cut -c1-900
python3 - <<'PY'
import re
t = open('test.xml').read() if __import__('os').path.exists('test.xml') else ''
m = re.search(r'<test-run[^>]*result="(\w+)"[^>]*total="(\d+)"[^>]*passed="(\d+)"[^>]*failed="(\d+)"', t)
print('结果：', m.groups() if m else '没有生成结果')
for msg in re.findall(r'<message><!\[CDATA\[(.*?)\]\]>', t, re.S)[:2]: print('  ', msg.strip()[:300])
PY
