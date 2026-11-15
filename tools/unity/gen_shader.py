"""从 Unity 自带的标准着色器（URP Lit）生成我们自己的表面着色器 Yuanjing/Surface。

为什么不从头写：直接在官方源码上改，阴影、多光源、环境光遮蔽、光照贴图这些都原样保留，
而且和当前安装的渲染管线版本保证一致。只在三处动手：
  1. 输入：多了一张「遮蔽/粗糙/金属」合一的贴图和几个天气参数
  2. 前向渲染的片元：采样合一贴图，然后套上天气（YJWeather.hlsl：淋湿、积水、积雪）
  3. 去掉用不到的几遍（延迟渲染、2D、XR）
升级 Unity 或渲染管线后重新跑一遍：python3 tools/unity/gen_shader.py
"""
import glob
import re
from pathlib import Path

PROJ = Path(__file__).resolve().parents[2] / "unity" / "Sanctuary"
PKG = Path(glob.glob(str(PROJ / "Library/PackageCache/com.unity.render-pipelines.universal@*"))[0])
OUT = PROJ / "Assets" / "Shaders"


def must_replace(s, a, b, count=1):
    assert s.count(a) >= 1, f"源码里找不到：{a[:60]}"
    return s.replace(a, b) if count == 0 else s.replace(a, b, count)


def drop_pass(s, name):
    """整个删掉一遍绘制。必须从单独成行的 Pass 开始删到它配对的右花括号。
    以前是往前找最近的「Pass」四个字母，结果找到了注释里的 ShaderPassName，只删掉了名字和标签，
    留下一遍没有标签的绘制。渲染管线对没有标签的绘制照画不误，于是每个物体每帧被画两遍，画面在两种样子之间乱跳。"""
    i = s.find(f'Name "{name}"')
    if i < 0:
        return s
    starts = [m.start() for m in re.finditer(r"^[ \t]*Pass[ \t]*$", s[:i], re.M)]
    assert starts, f"找不到 {name} 这一遍的开头"
    start = starts[-1]
    depth, j = 0, s.find("{", start)
    assert j < i, f"{name} 这一遍的结构和预想的不一样"
    while True:
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return s[:start] + s[j + 1:]


# ── 输入 ──
inp = (PKG / "Shaders/LitInput.hlsl").read_text()
inp = inp.replace("UNIVERSAL_LIT_INPUT_INCLUDED", "YJ_SURFACE_INPUT_INCLUDED")
inp = must_replace(inp, "half _Surface;\n", "half _Surface;\nhalf _Roughness;\nhalf _WetAmount;\nhalf _SnowAmount;\nhalf _Puddle;\nhalf _Sway;\n")
inp = must_replace(inp, "TEXTURE2D(_ClearCoatMap);", "TEXTURE2D(_ArmMap);            SAMPLER(sampler_ArmMap);\nTEXTURE2D(_ClearCoatMap);")
(OUT / "YJInput.hlsl").write_text("// 由 tools/unity/gen_shader.py 生成，不要手改\n" + inp)

# ── 前向渲染 ──
fwd = (PKG / "Shaders/LitForwardPass.hlsl").read_text()
fwd = fwd.replace("UNIVERSAL_FORWARD_LIT_PASS_INCLUDED", "YJ_SURFACE_FORWARD_INCLUDED")
fwd = must_replace(
    fwd,
    '#include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"\n',
    '#include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"\n'
    '#include "Assets/Shaders/YJWeather.hlsl"\n'
    "#ifndef REQUIRES_WORLD_SPACE_POS_INTERPOLATOR\n#define REQUIRES_WORLD_SPACE_POS_INTERPOLATOR\n#endif\n",
)
fwd = must_replace(
    fwd,
    "    InitializeStandardLitSurfaceData(input.uv, surfaceData);\n",
    "    InitializeStandardLitSurfaceData(input.uv, surfaceData);\n"
    "    // 遮蔽(R) 粗糙(G) 金属(B) 合一的贴图\n"
    "    half3 arm = SAMPLE_TEXTURE2D(_ArmMap, sampler_ArmMap, input.uv).rgb;\n"
    "    surfaceData.occlusion = lerp(1.0, arm.r, _OcclusionStrength);\n"
    "    surfaceData.smoothness = saturate(1.0 - arm.g * _Roughness);\n"
    "    surfaceData.metallic = saturate(arm.b * _Metallic);\n",
)
fwd = must_replace(
    fwd,
    "    InitializeInputData(input, surfaceData.normalTS, inputData);\n    SETUP_DEBUG_TEXTURE_DATA",
    "    InitializeInputData(input, surfaceData.normalTS, inputData);\n"
    "    YJApplyWeather(input.positionWS, input.normalWS.xyz, _WetAmount, _SnowAmount, _Puddle, surfaceData, inputData);\n"
    "    SETUP_DEBUG_TEXTURE_DATA",
)
# 随风摆动：顶点色的红色通道是幅度（树叶、布条的自由端是 1，系着的那头是 0）
fwd = must_replace(fwd, "    float4 tangentOS    : TANGENT;\n", "    float4 tangentOS    : TANGENT;\n    half4 color         : COLOR;\n")
fwd = must_replace(
    fwd,
    "    VertexPositionInputs vertexInput = GetVertexPositionInputs(input.positionOS.xyz);\n",
    "    input.positionOS.xyz = YJSwayOS(input.positionOS.xyz, input.color.r);\n"
    "    VertexPositionInputs vertexInput = GetVertexPositionInputs(input.positionOS.xyz);\n",
)
fwd = must_replace(fwd, '#include "Assets/Shaders/YJWeather.hlsl"\n', '#include "Assets/Shaders/YJWeather.hlsl"\n#include "Assets/Shaders/YJSway.hlsl"\n')
(OUT / "YJForwardPass.hlsl").write_text("// 由 tools/unity/gen_shader.py 生成，不要手改\n" + fwd)

# ── 阴影、深度、深度法线：也要摆，和画颜色那一遍完全一致 ──
def sway_pass(src, guard, newguard, pos_field, first_use, out_name):
    t = (PKG / "Shaders" / src).read_text().replace(guard, newguard)
    t = must_replace(t, f"    float4 {pos_field}", f"    half4 color         : COLOR;\n    float4 {pos_field}")
    t = must_replace(t, first_use, f"    input.{pos_field.split()[0]}.xyz = YJSwayOS(input.{pos_field.split()[0]}.xyz, input.color.r);\n" + first_use)
    t = "#include \"Assets/Shaders/YJSway.hlsl\"\n" + t
    (OUT / out_name).write_text("// 由 tools/unity/gen_shader.py 生成，不要手改\n" + t)

sway_pass("ShadowCasterPass.hlsl", "UNIVERSAL_SHADOW_CASTER_PASS_INCLUDED", "YJ_SHADOW_CASTER_PASS_INCLUDED",
          "positionOS   : POSITION;", "    float3 positionWS = TransformObjectToWorld(input.positionOS.xyz);\n", "YJShadowCasterPass.hlsl")
sway_pass("DepthOnlyPass.hlsl", "UNIVERSAL_DEPTH_ONLY_PASS_INCLUDED", "YJ_DEPTH_ONLY_PASS_INCLUDED",
          "position     : POSITION;", "    output.positionCS = TransformObjectToHClip(input.position.xyz);\n", "YJDepthOnlyPass.hlsl")
sway_pass("LitDepthNormalsPass.hlsl", "UNIVERSAL_FORWARD_LIT_DEPTH_NORMALS_PASS_INCLUDED", "YJ_DEPTH_NORMALS_PASS_INCLUDED",
          "positionOS   : POSITION;", "    output.positionCS = TransformObjectToHClip(input.positionOS.xyz);\n", "YJDepthNormalsPass.hlsl")

# ── 着色器本体 ──
sh = (PKG / "Shaders/Lit.shader").read_text()
sh = must_replace(sh, 'Shader "Universal Render Pipeline/Lit"', 'Shader "Yuanjing/Surface"')
sh = must_replace(
    sh,
    "    Properties\n    {\n",
    "    Properties\n    {\n"
    '        [NoScaleOffset] _ArmMap("遮蔽(R) 粗糙(G) 金属(B)", 2D) = "white" {}\n'
    '        _Roughness("粗糙度倍数", Range(0.0, 2.0)) = 1.0\n'
    '        _WetAmount("会被淋湿的程度", Range(0.0, 1.0)) = 1.0\n'
    '        _SnowAmount("会积雪的程度", Range(0.0, 1.0)) = 1.0\n'
    '        _Puddle("会积水的程度", Range(0.0, 1.0)) = 0.0\n'
    '        _Sway("随风摆动", Range(0.0, 1.0)) = 0.0\n',
)
sh = sh.replace('#include "Packages/com.unity.render-pipelines.universal/Shaders/LitInput.hlsl"', '#include "Assets/Shaders/YJInput.hlsl"')
sh = must_replace(sh, '#include "Packages/com.unity.render-pipelines.universal/Shaders/LitForwardPass.hlsl"', '#include "Assets/Shaders/YJForwardPass.hlsl"')
for pkg, mine in (("ShadowCasterPass.hlsl", "YJShadowCasterPass.hlsl"), ("DepthOnlyPass.hlsl", "YJDepthOnlyPass.hlsl"), ("LitDepthNormalsPass.hlsl", "YJDepthNormalsPass.hlsl")):
    sh = must_replace(sh, f'#include "Packages/com.unity.render-pipelines.universal/Shaders/{pkg}"', f'#include "Assets/Shaders/{mine}"', 0)
for name in ("GBuffer", "Universal2D", "XRMotionVectors"):
    sh = drop_pass(sh, name)
sh = re.sub(r'\n\s*CustomEditor "[^"]+"', "", sh)
(OUT / "YJSurface.shader").write_text("// 由 tools/unity/gen_shader.py 生成，不要手改\n" + sh)
# 每一遍都必须有名字和光照模式标签：没有标签的会被渲染管线当成普通绘制多画一遍
passes = re.split(r"^[ \t]*Pass[ \t]*$", sh, flags=re.M)[1:]
for body in passes:
    assert re.search(r'Name "\w+"', body) and "LightMode" in body, "有一遍绘制缺名字或光照模式标签：" + body[:200]
print("生成", [p.name for p in OUT.glob("YJ*")], "剩下的几遍：", re.findall(r'Name "(\w+)"', sh))
