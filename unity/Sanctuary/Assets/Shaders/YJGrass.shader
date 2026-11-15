// 草：一根根真的草叶（Editor/BuildGrass.cs 按 4 米一块生成）。草叶是实心的三角形，不用贴图，凑多近边缘都是清楚的。
// 颜色在顶点色里（根深梢浅），第四个数是「这个点在草叶的多高处」：0 是根、1 是梢，风和踩踏按它来弯。
// uv0：x 是这根草的排位（0..1，离远了排位靠后的先收起来，剩下的变宽补上），y 是相位；uv1：草根的位置。
// 只有一遍（画颜色）。草不投影子也不进深度预处理：几万根草再画两遍太贵，而且草贴着地，没影子看不出来。
Shader "Yuanjing/Grass"
{
    Properties
    {
        _BaseColor("整体染色", Color) = (1, 1, 1, 1)
        _ShadeColor("背阴处的颜色", Color) = (0.78, 0.92, 1.12, 1)
        _RootDark("草根有多暗", Range(0, 1)) = 0.5
        _Wind("随风弯多少", Range(0, 2)) = 1
        _Near("多远以内是全部的草（米，按视角换算）", Float) = 6
        _Far("多远以外只留五分之一", Float) = 11
        _Ambient("环境光强度", Range(0, 2)) = 0.5
        _SunScale("太阳光强度", Range(0, 2)) = 0.2
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry+10" }

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            Cull Off
            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fog
            #define YJ_OWN_MATERIAL
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            CBUFFER_START(UnityPerMaterial)
            half4 _BaseColor;
            half4 _ShadeColor;
            half _RootDark;
            half _Wind;
            half _Near;
            half _Far;
            half _Ambient;
            half _SunScale;
            CBUFFER_END

            #include "Assets/Shaders/YJWeather.hlsl"
            #include "Assets/Shaders/YJToonCommon.hlsl"
            float _YJCloud;

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                half4 color : COLOR;
                float2 uv : TEXCOORD0;
                float3 root : TEXCOORD1;
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                half4 color : TEXCOORD1;       // a：在草叶的多高处
                half4 fogAndVertexLight : TEXCOORD2;
                half3 normalWS : TEXCOORD3;
            };

            Varyings vert(Attributes v)
            {
                Varyings o = (Varyings)0;
                float3 root = TransformObjectToWorld(v.root);
                float3 w = TransformObjectToWorld(v.positionOS.xyz);
                half t = v.color.a;

                // 离远了收掉一部分、剩下的变宽。距离按视角换算：镜头拉近（放大看）时等于走近了，草要给全
                float dist = distance(root, _WorldSpaceCameraPos) / (unity_CameraProjection._m11 * 0.577);
                half far = smoothstep(_Near, _Far, dist);
                half keep = lerp(1.0, 0.2, far);
                float3 rel = w - root;
                rel.xz *= lerp(1.0, 2.3, far);
                rel.y *= lerp(1.0, 1.15, far);
                rel *= step(v.uv.x, keep);

                // 风：一阵一阵地扫过去，草梢弯得最多
                float tm = _Time.y;
                float gust = 0.5 + 0.5 * sin(tm * 0.7 + root.x * 0.21 + root.z * 0.15);
                float wave = sin(tm * 1.7 + root.x * 0.9 + root.z * 0.7 + v.uv.y * 6.2831) + 0.6 * sin(tm * 3.1 + root.x * 2.1 - root.z * 1.3);
                float bend = (0.02 + 0.10 * _YJWind) * _Wind * (0.4 + gust) * wave * t * t;
                rel.xz += float2(1.0, 0.45) * bend;

                // 人走过：脚边的草往外倒、压低（_YJSee.xyz 是人脚下的位置）
                float2 away = root.xz - _YJSee.xz;
                float d = length(away);
                half press = saturate(1.0 - d / 0.75) * saturate(1.0 - abs(root.y - _YJSee.y));
                rel.xz += away / max(d, 0.05) * (press * 0.6 * rel.y);
                rel.y *= 1.0 - press * 0.6;

                o.positionWS = root + rel;
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.color.rgb = SRGBToLinear(v.color.rgb) * _BaseColor.rgb;
                o.color.a = t;
                o.fogAndVertexLight.x = ComputeFogFactor(o.positionCS.z);
                #ifdef _ADDITIONAL_LIGHTS_VERTEX
                o.fogAndVertexLight.yzw = VertexLighting(o.positionWS, o.normalWS);
                #endif
                return o;
            }

            half4 frag(Varyings i) : SV_Target
            {
                half t = i.color.a;
                half3 albedo = i.color.rgb * lerp(1.0 - _RootDark, 1.0, smoothstep(0.0, 0.75, t));
                half3 n = normalize(i.normalWS);
                if (_YJWet + _YJSnow > 0.001)
                {
                    half open = YJOpenSky(i.positionWS, half3(0, 1, 0));
                    albedo *= lerp(1.0, 0.8, _YJWet * open);
                    // 雪：从草根往上埋，雪厚了只露草尖
                    half snow = smoothstep(t - 0.15, t + 0.1, _YJSnow * 1.2) * open;
                    albedo = lerp(albedo, half3(0.90, 0.93, 0.98), snow * 0.9);
                }
                float4 shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                Light light = GetMainLight(shadowCoord);
                half lit = light.shadowAttenuation * smoothstep(-0.1, 0.25, light.direction.y);
                lit *= 1.0 - _YJCloud * smoothstep(0.42, 0.68, yjNoise(i.positionWS.xz * 0.045 + _Time.y * float2(0.016, 0.009)));
                half3 ambient = SampleSH(half3(0, 1, 0)) * _Ambient;
                half3 color = albedo * (ambient * lerp(_ShadeColor.rgb, half3(1, 1, 1), lit) + light.color * (lit * _SunScale));
                // 逆光时草梢透亮
                half3 v = GetWorldSpaceNormalizeViewDir(i.positionWS);
                half back = saturate(dot(v, -light.direction));
                color += albedo * half3(0.9, 1.0, 0.4) * light.color * (back * back * t * lit * _SunScale * 1.2);
                #if defined(_ADDITIONAL_LIGHTS)
                uint count = GetAdditionalLightsCount();
                for (uint k = 0u; k < count; ++k)
                {
                    Light l = GetAdditionalLight(k, i.positionWS);
                    color += albedo * l.color * (l.distanceAttenuation * 0.8);
                }
                #endif
                #ifdef _ADDITIONAL_LIGHTS_VERTEX
                color += albedo * i.fogAndVertexLight.yzw;
                #endif
                color = MixFog(color, i.fogAndVertexLight.x);
                return half4(color, 1);
            }
            ENDHLSL
        }
    }
}
