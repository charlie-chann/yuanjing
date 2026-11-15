// 卡通画风的表面：颜色取自顶点色，光照分成亮面和暗面两段（交界柔和），暗面偏蓝紫。
// 接太阳的影子、环境光、灯笼的点光、雾、淋湿和积雪。每一遍都写了名字和 LightMode：
// 少写一个，URP 会把那一遍当成普通的再画一次，画面就会闪（见 docs/08 的闪烁排查）。
Shader "Yuanjing/Toon"
{
    Properties
    {
        _BaseColor("整体染色", Color) = (1, 1, 1, 1)
        _BaseMap("贴图（只有普通模型用）", 2D) = "white" {}
        _Legacy("普通模型：颜色不在顶点色里", Float) = 0
        _ShadeColor("暗面的颜色", Color) = (0.62, 0.66, 0.90, 1)
        _ShadeStep("明暗交界的位置", Range(-1, 1)) = 0.08
        _ShadeSoft("交界有多柔", Range(0.01, 1)) = 0.22
        [HDR] _EmissionColor("自发光", Color) = (0, 0, 0, 1)
        _RimColor("边缘光", Color) = (1, 1, 1, 0.18)
        _Sway("随风摆动", Range(0, 2)) = 1
        _WetAmount("会不会淋湿", Range(0, 1)) = 1
        _SnowAmount("会不会积雪", Range(0, 1)) = 1
        _Ambient("环境光强度", Range(0, 2)) = 1
        _SunScale("太阳光强度", Range(0, 2)) = 1
        [Enum(UnityEngine.Rendering.CullMode)] _Cull("剔除", Float) = 2
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry" }

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            Cull [_Cull]
            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fragment _ _SCREEN_SPACE_OCCLUSION
            #pragma multi_compile_fog
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "Assets/Shaders/YJWeather.hlsl"
            #include "Assets/Shaders/YJToonCommon.hlsl"
            TEXTURE2D(_BaseMap);
            SAMPLER(sampler_BaseMap);
            float _YJCloud;

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                half4 color : COLOR;
                float2 uv : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                half3 normalWS : TEXCOORD1;
                half4 color : TEXCOORD2;      // 已经换成线性的颜色，a 是自发光
                half4 fogAndVertexLight : TEXCOORD3;
                float2 uv : TEXCOORD4;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            Varyings vert(Attributes v)
            {
                Varyings o = (Varyings)0;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_TRANSFER_INSTANCE_ID(v, o);
                float3 pos = YJToonSway(v.positionOS.xyz, v.color, v.uv.x);
                o.positionWS = TransformObjectToWorld(pos);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.color.rgb = lerp(SRGBToLinear(v.color.rgb), half3(1, 1, 1), _Legacy) * _BaseColor.rgb;
                o.color.a = lerp(v.uv.y, 1.0, _Legacy);
                o.uv = v.uv * _BaseMap_ST.xy + _BaseMap_ST.zw;
                o.fogAndVertexLight.x = ComputeFogFactor(o.positionCS.z);
                #ifdef _ADDITIONAL_LIGHTS_VERTEX
                o.fogAndVertexLight.yzw = VertexLighting(o.positionWS, o.normalWS);
                #endif
                return o;
            }

            half4 frag(Varyings i, FRONT_FACE_TYPE facing : FRONT_FACE_SEMANTIC) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(i);
                YJSeeThrough(i.positionWS, i.positionCS);
                half3 n = normalize(i.normalWS) * IS_FRONT_VFACE(facing, 1.0, -1.0);
                half3 albedo = i.color.rgb;
                if (_Legacy > 0.5) albedo *= SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, i.uv).rgb;
                half up = saturate(n.y);

                // 天气：淋湿变深，积雪变白（屋檐下不湿不白）
                half3 emission = _EmissionColor.rgb * i.color.a;
                if (_YJWet + _YJSnow > 0.001)
                {
                    half open = YJOpenSky(i.positionWS, n);
                    half wet = _YJWet * _WetAmount * open * lerp(0.45, 1.0, up);
                    albedo *= lerp(1.0, 0.74, wet);
                    half lie = saturate((up - 0.3) * 2.0) * open * _SnowAmount;
                    half grain = 0.6 + 0.4 * yjNoise(i.positionWS.xz * 1.3) + 0.3 * (yjNoise(i.positionWS.xz * 0.3) - 0.5);
                    half cover = _YJSnow * 1.35;
                    half snow = smoothstep(1.0 - cover, 1.0 - cover + 0.18, lie * grain) * smoothstep(0.0, 0.1, lie);
                    albedo = lerp(albedo, half3(0.90, 0.93, 0.98), snow);
                }

                float4 shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                Light light = GetMainLight(shadowCoord);
                half ndl = dot(n, light.direction);
                half ramp = smoothstep(_ShadeStep - _ShadeSoft, _ShadeStep + _ShadeSoft, ndl);
                half lit = ramp * light.shadowAttenuation;
                // 云影：大块的明暗在地上慢慢飘过（只在俯视的场景里开，_YJCloud 是强度）
                lit *= 1.0 - _YJCloud * smoothstep(0.42, 0.68, yjNoise(i.positionWS.xz * 0.045 + _Time.y * float2(0.016, 0.009)));

                half ao = 1.0;
                #if defined(_SCREEN_SPACE_OCCLUSION)
                float2 suv = GetNormalizedScreenSpaceUV(i.positionCS);
                AmbientOcclusionFactor aof = GetScreenSpaceAmbientOcclusion(suv);
                ao = aof.indirectAmbientOcclusion;
                #endif

                half3 ambient = SampleSH(n) * _Ambient;
                // 暗面：只有环境光，再偏一点蓝紫；亮面：环境光加太阳
                half3 shade = ambient * lerp(_ShadeColor.rgb, half3(1, 1, 1), lit) * lerp(1.0, ao, 0.85);
                half3 color = albedo * (shade + light.color * (lit * _SunScale));

                #if defined(_ADDITIONAL_LIGHTS)
                uint count = GetAdditionalLightsCount();
                for (uint k = 0u; k < count; ++k)
                {
                    Light l = GetAdditionalLight(k, i.positionWS);
                    half d = smoothstep(-0.1, 0.5, dot(n, l.direction));
                    color += albedo * l.color * (l.distanceAttenuation * d);
                }
                #endif
                #ifdef _ADDITIONAL_LIGHTS_VERTEX
                color += albedo * i.fogAndVertexLight.yzw;
                #endif

                // 边缘光：朝上的亮面边缘微微发亮，物体的轮廓更清楚
                half3 v = GetWorldSpaceNormalizeViewDir(i.positionWS);
                half rim = pow(1.0 - saturate(dot(n, v)), 3.0) * saturate(n.y * 0.6 + 0.4) * lit;
                color += rim * _RimColor.rgb * _RimColor.a * light.color * _SunScale;

                color += emission;
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
            Cull [_Cull]
            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"
            #include "Assets/Shaders/YJToonCommon.hlsl"

            float3 _LightDirection;
            float3 _LightPosition;

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                half4 color : COLOR;
                float2 uv : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };
            struct Varyings { float4 positionCS : SV_POSITION; };

            Varyings vert(Attributes v)
            {
                Varyings o;
                UNITY_SETUP_INSTANCE_ID(v);
                float3 pos = YJToonSway(v.positionOS.xyz, v.color, v.uv.x);
                float3 positionWS = TransformObjectToWorld(pos);
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
            Cull [_Cull]
            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Assets/Shaders/YJToonCommon.hlsl"

            struct Attributes
            {
                float4 positionOS : POSITION;
                half4 color : COLOR;
                float2 uv : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };
            struct Varyings { float4 positionCS : SV_POSITION; float3 positionWS : TEXCOORD0; };

            Varyings vert(Attributes v)
            {
                Varyings o;
                UNITY_SETUP_INSTANCE_ID(v);
                o.positionWS = TransformObjectToWorld(YJToonSway(v.positionOS.xyz, v.color, v.uv.x));
                o.positionCS = TransformWorldToHClip(o.positionWS);
                return o;
            }
            half4 frag(Varyings i) : SV_Target
            {
                YJSeeThrough(i.positionWS, i.positionCS);
                return i.positionCS.z;
            }
            ENDHLSL
        }

        Pass
        {
            Name "DepthNormals"
            Tags { "LightMode" = "DepthNormals" }
            ZWrite On
            Cull [_Cull]
            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Assets/Shaders/YJToonCommon.hlsl"

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                half4 color : COLOR;
                float2 uv : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };
            struct Varyings { float4 positionCS : SV_POSITION; half3 normalWS : TEXCOORD0; float3 positionWS : TEXCOORD1; };

            Varyings vert(Attributes v)
            {
                Varyings o;
                UNITY_SETUP_INSTANCE_ID(v);
                o.positionWS = TransformObjectToWorld(YJToonSway(v.positionOS.xyz, v.color, v.uv.x));
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                return o;
            }
            half4 frag(Varyings i, FRONT_FACE_TYPE facing : FRONT_FACE_SEMANTIC) : SV_Target
            {
                YJSeeThrough(i.positionWS, i.positionCS);
                half3 n = normalize(i.normalWS) * IS_FRONT_VFACE(facing, 1.0, -1.0);
                return half4(n, 0);
            }
            ENDHLSL
        }
    }
}
