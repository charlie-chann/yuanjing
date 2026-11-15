// 绒毛：在动物身体外面套十来层「壳」，每层只留下一根根毛的截面，叠起来就是立体的毛（手机上不支持几何着色器，这是通用的做法）。
// 壳是生成场景时直接做进网格里的（Editor/BuildFur.cs）：uv1.x 是第几层（0 是身体本身，1 是最外层），
// uv2 是这个点在模型没动时的位置——毛的花纹按它来算，动物怎么动，毛都长在原来的地方。
// 顶点色：rgb 是毛色，第四个数是这里的毛多长（0 没有毛：眼睛、鼻子）。
// 四遍都有 Name 和 LightMode；影子和深度只画身体那一层。
Shader "Yuanjing/Fur"
{
    Properties
    {
        _BaseColor("整体染色", Color) = (1, 1, 1, 1)
        _FurLength("毛长（米）", Float) = 0.03
        _Density("毛有多密（按模型自己的单位，每单位多少根；生成时按模型大小折算好）", Float) = 420
        _Thin("毛梢收细", Range(0, 4)) = 1.6
        _Droop("往下垂", Range(0, 1.5)) = 0.35
        _RootDark("毛根有多暗", Range(0, 1)) = 0.42
        _TipLight("毛梢提亮", Range(1, 1.6)) = 1.16
        _ShadeColor("暗面的颜色", Color) = (0.86, 0.84, 1.0, 1)
        _ShadeStep("明暗交界的位置", Range(-1, 1)) = 0.0
        _ShadeSoft("交界有多柔", Range(0.01, 1)) = 0.3
        _RimColor("逆光时毛边发亮", Color) = (1, 0.96, 0.86, 0.5)
        _Curl("卷毛：每层绕多大的圈（毛的粗细的几倍）", Range(0, 3)) = 0
        _CurlTurns("卷毛：从根到梢绕几圈", Range(0, 4)) = 1.5
        _Comb("顺毛：往后往下梳的程度", Range(0, 1.5)) = 0.6
        _StrandVary("每根毛深浅差多少", Range(0, 0.6)) = 0.28
        _Gloss("眼睛、鼻头的高光", Range(0, 2)) = 1
        _Ambient("环境光强度", Range(0, 2)) = 0.5
        _SunScale("太阳光强度", Range(0, 2)) = 0.2
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry" }

        HLSLINCLUDE
        #pragma target 3.0
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

        CBUFFER_START(UnityPerMaterial)
        half4 _BaseColor;
        half4 _ShadeColor;
        half4 _RimColor;
        float _FurLength;
        float _Density;
        half _Thin;
        half _Droop;
        half _RootDark;
        half _TipLight;
        half _ShadeStep;
        half _ShadeSoft;
        half _Ambient;
        half _SunScale;
        half _Curl;
        half _CurlTurns;
        half _Comb;
        half _StrandVary;
        half _Gloss;
        CBUFFER_END
        // 往哪个方向梳（世界坐标，小动物的脚本每帧按它朝向设：往身后、往下）
        float4 _FurComb;

        // 把一个点沿法线推到它那一层壳上（毛越往外越往下垂一点）
        float3 YJFurPosition(float3 positionOS, float3 normalOS, half shell, half furAmount)
        {
            float3 w = TransformObjectToWorld(positionOS);
            float3 n = TransformObjectToWorldNormal(normalOS);
            float len = _FurLength * furAmount * 2.0;
            w += n * (shell * len);
            w.y -= shell * shell * len * _Droop;
            // 顺毛：越往外越往身后倒（不往皮肤里倒：去掉朝着法线反方向的那部分）
            float3 comb = _FurComb.xyz;
            comb -= n * min(0.0, dot(comb, n));
            w += comb * (shell * shell * len * _Comb);
            return w;
        }
        ENDHLSL

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            Cull Back
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fog

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                half4 color : COLOR;
                float2 shell : TEXCOORD1;
                float3 rest : TEXCOORD2;
            };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                half3 normalWS : TEXCOORD1;
                half4 color : TEXCOORD2;
                float4 restShell : TEXCOORD3;
                half4 fogAndVertexLight : TEXCOORD4;
            };

            Varyings vert(Attributes v)
            {
                Varyings o = (Varyings)0;
                o.positionWS = YJFurPosition(v.positionOS.xyz, v.normalOS, v.shell.x, v.color.a);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.color = half4(SRGBToLinear(v.color.rgb) * _BaseColor.rgb, v.color.a);
                o.restShell = float4(v.rest, v.shell.x);
                o.fogAndVertexLight.x = ComputeFogFactor(o.positionCS.z);
                #ifdef _ADDITIONAL_LIGHTS_VERTEX
                o.fogAndVertexLight.yzw = VertexLighting(o.positionWS, o.normalWS);
                #endif
                return o;
            }

            half4 frag(Varyings i) : SV_Target
            {
                half shell = i.restShell.w;
                half furry = saturate(i.color.a * 6.0);
                half strandTone = 1.0;
                if (shell > 0.001)
                {
                    // 没有毛的地方（眼睛、鼻子）不画壳
                    clip(i.color.a - 0.02);
                    // 毛的截面：把空间切成小格，每格正中一根毛，高矮随机；越往外层，只剩高的那些，而且越细
                    float3 p = i.restShell.xyz * _Density;
                    // 卷毛：每一层把取样的位置绕一个小圈挪一下，一根根毛就成了螺旋（相位每根不同）
                    if (_Curl > 0.001)
                    {
                        float3 c0 = floor(p);
                        float ph = frac(sin(dot(c0, float3(12.9, 78.2, 37.7))) * 4375.85) * 6.2831;
                        float a = shell * _CurlTurns * 6.2831 + ph;
                        p += float3(cos(a), sin(a), cos(a * 0.7 + 1.3)) * (_Curl * 0.35 * shell);
                    }
                    // 毛不在格子正中、粗细各不同（不然整齐得像马赛克）；再叠一层密两倍半的细绒毛，填满毛根之间
                    float3 cell = floor(p);
                    float r = frac(sin(dot(cell, float3(127.1, 311.7, 74.7))) * 43758.5453);
                    float3 jit = frac(sin(float3(dot(cell, float3(12.9, 78.2, 45.1)), dot(cell, float3(39.3, 11.1, 83.7)), dot(cell, float3(73.1, 52.9, 19.7)))) * 4375.85) - 0.5;
                    float3 f = frac(p) - 0.5 - jit * 0.55;
                    float thick = 0.7 + 0.6 * frac(r * 31.7);
                    strandTone = 1.0 + (frac(r * 17.31) - 0.5) * 2.0 * _StrandVary;
                    r = 0.35 + 0.65 * r;
                    float d2 = dot(f, f) * 4.0 / thick;
                    float keep = r * (1.0 - _Thin * d2 * shell) - shell - d2 * 0.25;
                    float3 p2 = p * 2.5 + 17.3;
                    float3 c2 = floor(p2);
                    float r2 = frac(sin(dot(c2, float3(91.7, 23.3, 57.1))) * 4375.85);
                    float3 f2 = frac(p2) - 0.5;
                    float keep2 = (0.25 + 0.3 * r2) * (1.0 - 1.4 * dot(f2, f2) * 4.0) - shell * 1.6;
                    if (keep2 > keep) strandTone *= 0.9;
                    keep = max(keep, keep2);
                    // 离远了一根毛还不到一个像素，逐根地裁会闪：改成「矮的几层整层留着、高的几层整层不要」
                    float3 fw = fwidth(p);
                    half far = saturate((max(fw.x, max(fw.y, fw.z)) - 0.3) / 0.5);
                    keep = lerp(keep, 0.5 - shell, far);
                    clip(keep);
                }
                half3 n = normalize(i.normalWS);
                // 毛根暗、毛梢亮：层与层之间有了深浅，毛才看得出一根根
                // 毛根暗、毛梢亮，每根毛深浅各不同：一根根才分得清
                half3 albedo = i.color.rgb * lerp(1.0, lerp(1.0 - _RootDark, _TipLight, shell) * strandTone, furry);

                float4 shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                Light light = GetMainLight(shadowCoord);
                half ndl = dot(n, light.direction);
                half ramp = smoothstep(_ShadeStep - _ShadeSoft, _ShadeStep + _ShadeSoft, ndl) * light.shadowAttenuation;
                half3 ambient = SampleSH(n) * _Ambient;
                half3 color = albedo * (ambient * lerp(_ShadeColor.rgb, half3(1, 1, 1), ramp) + light.color * (ramp * _SunScale));
                #if defined(_ADDITIONAL_LIGHTS)
                uint count = GetAdditionalLightsCount();
                for (uint k = 0u; k < count; ++k)
                {
                    Light l = GetAdditionalLight(k, i.positionWS);
                    color += albedo * l.color * (l.distanceAttenuation * smoothstep(-0.2, 0.5, dot(n, l.direction)));
                }
                #endif
                #ifdef _ADDITIONAL_LIGHTS_VERTEX
                color += albedo * i.fogAndVertexLight.yzw;
                #endif
                // 轮廓上的毛被光打透，镶一圈亮边
                half3 v = GetWorldSpaceNormalizeViewDir(i.positionWS);
                half rim = pow(1.0 - saturate(dot(n, v)), 2.5) * shell * furry;
                color += albedo * _RimColor.rgb * (rim * _RimColor.a * (0.4 + ramp)) * light.color * _SunScale * 3.0;
                // 眼睛、鼻头（没有毛的地方）：湿润的高光，加一点固定的眼神光
                if (i.color.a < 0.02)
                {
                    half3 hv = normalize(light.direction + v);
                    half spec = pow(saturate(dot(n, hv)), 90.0) * 2.5 + pow(saturate(dot(n, normalize(v + half3(0.25, 0.6, 0)))), 160.0) * 1.2;
                    color += light.color * spec * _Gloss * _SunScale * 2.5 + spec * _Gloss * 0.15;
                }
                color = MixFog(color, i.fogAndVertexLight.x);
                return half4(color, 1);
            }
            ENDHLSL
        }

        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode" = "ShadowCaster" }
            ZWrite On
            ZTest LEqual
            ColorMask 0
            Cull Back
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            float3 _LightDirection;
            float3 _LightPosition;
            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float2 shell : TEXCOORD1; };
            struct Varyings { float4 positionCS : SV_POSITION; };
            Varyings vert(Attributes v)
            {
                Varyings o;
                float3 positionWS = TransformObjectToWorld(v.positionOS.xyz);
                float3 normalWS = TransformObjectToWorldNormal(v.normalOS);
                #if _CASTING_PUNCTUAL_LIGHT_SHADOW
                float3 lightDir = normalize(_LightPosition - positionWS);
                #else
                float3 lightDir = _LightDirection;
                #endif
                o.positionCS = TransformWorldToHClip(ApplyShadowBias(positionWS, normalWS, lightDir));
                #if UNITY_REVERSED_Z
                o.positionCS.z = min(o.positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #else
                o.positionCS.z = max(o.positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #endif
                // 壳不投影子：挪到屏幕外面去
                if (v.shell.x > 0.001) o.positionCS = float4(2, 2, 2, 1);
                return o;
            }
            half4 frag(Varyings i) : SV_Target { return 0; }
            ENDHLSL
        }

        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode" = "DepthOnly" }
            ZWrite On
            ColorMask R
            Cull Back
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            struct Attributes { float4 positionOS : POSITION; float2 shell : TEXCOORD1; };
            struct Varyings { float4 positionCS : SV_POSITION; };
            Varyings vert(Attributes v)
            {
                Varyings o;
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                if (v.shell.x > 0.001) o.positionCS = float4(2, 2, 2, 1);
                return o;
            }
            half4 frag(Varyings i) : SV_Target { return i.positionCS.z; }
            ENDHLSL
        }

        Pass
        {
            Name "DepthNormals"
            Tags { "LightMode" = "DepthNormals" }
            ZWrite On
            Cull Back
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float2 shell : TEXCOORD1; };
            struct Varyings { float4 positionCS : SV_POSITION; half3 normalWS : TEXCOORD0; };
            Varyings vert(Attributes v)
            {
                Varyings o;
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                if (v.shell.x > 0.001) o.positionCS = float4(2, 2, 2, 1);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                return o;
            }
            half4 frag(Varyings i) : SV_Target { return half4(normalize(i.normalWS), 0); }
            ENDHLSL
        }
    }
}
