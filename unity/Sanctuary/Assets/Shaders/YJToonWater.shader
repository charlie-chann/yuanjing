// 卡通画风的水面：按水深从浅绿过渡到深蓝，岸边和石头边一圈白浪，水底有流动的光纹，下雨时有涟漪。
// 水深是用「水面下那一点的实际位置」算的，所以需要镜头的深度图（URP 设置里已打开）。
Shader "Yuanjing/ToonWater"
{
    Properties
    {
        _Shallow("浅水的颜色", Color) = (0.36, 0.88, 0.80, 0.50)
        _Deep("深水的颜色", Color) = (0.07, 0.47, 0.62, 0.94)
        _DepthRange("多深算深水（米）", Float) = 1.7
        _Foam("浪花的颜色", Color) = (1, 1, 1, 0.95)
        _FoamWidth("岸边浪花的宽度", Float) = 0.07
        _Caustic("水底光纹的强度", Float) = 0.34
        _Glint("水面闪光的强度", Float) = 0.4
    }
    SubShader
    {
        Tags { "RenderType" = "Transparent" "RenderPipeline" = "UniversalPipeline" "Queue" = "Transparent" "IgnoreProjector" = "True" }
        Pass
        {
            Name "Water"
            Tags { "LightMode" = "UniversalForward" }
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            Cull Back
            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fog
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"
            #include "Assets/Shaders/YJWeather.hlsl"

            float _YJCloud;
            CBUFFER_START(UnityPerMaterial)
            half4 _Shallow;
            half4 _Deep;
            half4 _Foam;
            half _DepthRange;
            half _FoamWidth;
            half _Caustic;
            half _Glint;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float fog : TEXCOORD1;
            };

            Varyings vert(Attributes v)
            {
                Varyings o;
                o.positionWS = TransformObjectToWorld(v.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.fog = ComputeFogFactor(o.positionCS.z);
                return o;
            }

            float2 hash2(float2 p)
            {
                p = float2(dot(p, float2(127.1, 311.7)), dot(p, float2(269.5, 183.3)));
                return frac(sin(p) * 43758.5453);
            }

            // 蜂窝状的纹路：返回「到最近的格子边界有多远」，边界处接近 0
            float web(float2 p, float t)
            {
                float2 ip = floor(p), fp = frac(p);
                float f1 = 8.0, f2 = 8.0;
                for (int y = -1; y <= 1; y++)
                    for (int x = -1; x <= 1; x++)
                    {
                        float2 g = float2(x, y);
                        float2 o = hash2(ip + g);
                        o = 0.5 + 0.38 * sin(t + 6.2831 * o);
                        float d = length(g + o - fp);
                        if (d < f1) { f2 = f1; f1 = d; }
                        else if (d < f2) f2 = d;
                    }
                return f2 - f1;
            }

            half4 frag(Varyings i) : SV_Target
            {
                float2 uv = GetNormalizedScreenSpaceUV(i.positionCS);
                float raw = SampleSceneDepth(uv);
                float3 bed = ComputeWorldSpacePosition(uv, raw, UNITY_MATRIX_I_VP);
                float depth = max(0.0, i.positionWS.y - bed.y);
                float t = _Time.y;

                half k = saturate(depth / _DepthRange);
                half kk = 1.0 - (1.0 - k) * (1.0 - k);
                half3 col = lerp(_Shallow.rgb, _Deep.rgb, kk);
                half alpha = lerp(_Shallow.a, _Deep.a, kk);

                // 水面缓缓的明暗起伏
                float swell = yjNoise(i.positionWS.xz * 0.22 + float2(t * 0.05, t * 0.03));
                col *= 0.94 + 0.12 * swell;

                // 水底的光纹：浅处明显，往深处淡掉
                float c1 = web(bed.xz * 0.95 + float2(t * 0.05, 0.0), t * 0.55);
                float c2 = web(bed.xz * 1.55 - float2(0.0, t * 0.04), t * 0.4 + 2.0);
                half caustic = smoothstep(0.16, 0.0, c1) * 0.75 + smoothstep(0.12, 0.0, c2) * 0.4;
                caustic *= (1.0 - k) * (1.0 - k) * smoothstep(0.03, 0.25, depth) * _Caustic;

                // 岸边：一条贴岸的实边，外面再有一条一涨一落的细线
                float n = yjNoise(i.positionWS.xz * 1.6 + t * 0.12);
                float edge = depth + (n - 0.5) * 0.06;
                half foam = smoothstep(_FoamWidth, _FoamWidth * 0.55, edge);
                float ring = 0.20 + 0.07 * sin(t * 0.9 + n * 4.0);
                foam = max(foam, smoothstep(0.035, 0.012, abs(edge - ring)) * 0.75 * smoothstep(0.55, 0.3, depth));

                // 水面的闪光：一小段一小段的亮线，随波移动
                float g1 = web(i.positionWS.xz * float2(0.55, 1.5) + float2(t * 0.10, t * 0.03), t * 0.5 + 5.0);
                half glint = smoothstep(0.035, 0.0, g1) * smoothstep(0.55, 0.85, yjNoise(i.positionWS.xz * 0.35 - t * 0.05)) * _Glint * k;

                // 雨点的涟漪
                half rain = 0;
                if (_YJRain > 0.01)
                {
                    float2 rp = YJRipples(i.positionWS.xz * 0.7, t);
                    rain = saturate(length(rp) * 1.6) * _YJRain;
                }

                float4 shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                Light light = GetMainLight(shadowCoord);
                half sun = saturate(light.direction.y * 1.4) * lerp(0.55, 1.0, light.shadowAttenuation);
                sun *= 1.0 - _YJCloud * smoothstep(0.42, 0.68, yjNoise(i.positionWS.xz * 0.045 + _Time.y * float2(0.016, 0.009)));
                half3 ambient = SampleSH(half3(0, 1, 0));
                half3 lighting = ambient * 0.5 + light.color * sun * 0.2;

                half3 color = col * lighting;
                color += caustic * light.color * sun * half3(0.75, 1.0, 0.9) * 0.12;
                half white = saturate(foam + glint + rain * 0.6);
                color = lerp(color, _Foam.rgb * (ambient * 0.55 + light.color * sun * 0.2), white * _Foam.a);
                alpha = saturate(max(alpha, white * _Foam.a) + caustic * 0.25);
                color = MixFog(color, i.fog);
                return half4(color, alpha);
            }
            ENDHLSL
        }
    }
}
