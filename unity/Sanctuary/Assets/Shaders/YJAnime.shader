// 动漫人物（VRM 转来的，见 tools/blender/vrm_import.py）：颜色来自贴图，明暗分两段（脸上柔一点），外面一圈描边。
// 参数照着原模型 MToon 材质里的来：暗面颜色、描边粗细、镂空还是半透明。
// 五遍，每一遍都有 Name 和 LightMode（少写会闪，见 docs/08）；描边那一遍用 SRPDefaultUnlit。
Shader "Yuanjing/Anime"
{
    Properties
    {
        _MainTex("贴图", 2D) = "white" {}
        _ShadeTex("暗面的贴图（没有就用上面那张）", 2D) = "white" {}
        _Color("染色", Color) = (1, 1, 1, 1)
        _ShadeColor("暗面的颜色", Color) = (0.8, 0.76, 0.86, 1)
        _ShadeShift("明暗交界的位置（越小亮面越多）", Range(-1, 1)) = -0.2
        _Toony("交界有多硬", Range(0, 1)) = 0.6
        _OutlineWidth("描边粗细（厘米）", Range(0, 1)) = 0.1
        _OutlineColor("描边颜色", Color) = (0.3, 0.2, 0.25, 1)
        _RimColor("边缘光", Color) = (1, 1, 1, 0.12)
        _Cutoff("镂空的门槛", Range(0, 1)) = 0.5
        _AlphaClip("按透明度镂空", Float) = 0
        _Ambient("环境光强度", Range(0, 2)) = 0.5
        _SunScale("太阳光强度", Range(0, 2)) = 0.2
        [Enum(UnityEngine.Rendering.CullMode)] _Cull("剔除", Float) = 2
        [Enum(UnityEngine.Rendering.BlendMode)] _SrcBlend("混合：源", Float) = 1
        [Enum(UnityEngine.Rendering.BlendMode)] _DstBlend("混合：底", Float) = 0
        _ZWrite("写深度", Float) = 1
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry" }

        HLSLINCLUDE
        #pragma target 3.0
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

        CBUFFER_START(UnityPerMaterial)
        float4 _MainTex_ST;
        half4 _Color;
        half4 _ShadeColor;
        half4 _OutlineColor;
        half4 _RimColor;
        half _ShadeShift;
        half _Toony;
        half _OutlineWidth;
        half _Cutoff;
        half _AlphaClip;
        half _Ambient;
        half _SunScale;
        half _Cull;
        half _SrcBlend;
        half _DstBlend;
        half _ZWrite;
        CBUFFER_END

        TEXTURE2D(_MainTex);
        SAMPLER(sampler_MainTex);
        TEXTURE2D(_ShadeTex);
        SAMPLER(sampler_ShadeTex);

        // 贴着镜头的人（别人从镜头前走过、镜头被挤到人身边）用网点淡掉，不会整屏都是衣服
        void YJNearFade(float3 positionWS, float4 positionCS)
        {
            float d = distance(positionWS, _WorldSpaceCameraPos);
            if (d > 0.75) return;
            static const float bayer[16] = { 0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0 };
            uint2 px = uint2(positionCS.xy) & 3u;
            clip((d - 0.25) / 0.5 - (bayer[px.x + px.y * 4u] + 0.5) / 16.0);
        }

        half4 YJAnimeBase(float2 uv)
        {
            half4 c = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, uv) * _Color;
            if (_AlphaClip > 0.5) clip(c.a - _Cutoff);
            return c;
        }
        ENDHLSL

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            Cull [_Cull]
            Blend [_SrcBlend] [_DstBlend]
            ZWrite [_ZWrite]
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fog

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float2 uv : TEXCOORD0; };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                half3 normalWS : TEXCOORD1;
                float2 uv : TEXCOORD2;
                half4 fogAndVertexLight : TEXCOORD3;
            };

            Varyings vert(Attributes v)
            {
                Varyings o = (Varyings)0;
                o.positionWS = TransformObjectToWorld(v.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.uv = TRANSFORM_TEX(v.uv, _MainTex);
                o.fogAndVertexLight.x = ComputeFogFactor(o.positionCS.z);
                #ifdef _ADDITIONAL_LIGHTS_VERTEX
                o.fogAndVertexLight.yzw = VertexLighting(o.positionWS, o.normalWS);
                #endif
                return o;
            }

            half4 frag(Varyings i, FRONT_FACE_TYPE facing : FRONT_FACE_SEMANTIC) : SV_Target
            {
                YJNearFade(i.positionWS, i.positionCS);
                half4 base = YJAnimeBase(i.uv);
                half3 shadeTex = SAMPLE_TEXTURE2D(_ShadeTex, sampler_ShadeTex, i.uv).rgb * _ShadeColor.rgb;
                half3 n = normalize(i.normalWS) * IS_FRONT_VFACE(facing, 1.0, -1.0);
                float4 shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                Light light = GetMainLight(shadowCoord);
                half ndl = dot(n, light.direction);
                // 交界：从 _ShadeShift 开始变亮；_Toony 越大过渡越窄（脸上用小的，不会在鼻子旁边切出一块硬影子）
                half hi = lerp(1.0, _ShadeShift + 0.12, _Toony);
                half ramp = smoothstep(_ShadeShift, hi, ndl) * lerp(1.0, light.shadowAttenuation, 0.85);
                half3 albedo = lerp(shadeTex, base.rgb, ramp);
                half3 ambient = SampleSH(n) * _Ambient;
                half3 color = albedo * (ambient + light.color * (ramp * _SunScale));
                #if defined(_ADDITIONAL_LIGHTS)
                uint count = GetAdditionalLightsCount();
                for (uint k = 0u; k < count; ++k)
                {
                    Light l = GetAdditionalLight(k, i.positionWS);
                    color += base.rgb * l.color * (l.distanceAttenuation * smoothstep(-0.2, 0.5, dot(n, l.direction)));
                }
                #endif
                #ifdef _ADDITIONAL_LIGHTS_VERTEX
                color += base.rgb * i.fogAndVertexLight.yzw;
                #endif
                half3 v = GetWorldSpaceNormalizeViewDir(i.positionWS);
                half rim = pow(1.0 - saturate(dot(n, v)), 4.0) * ramp;
                color += rim * _RimColor.rgb * _RimColor.a * light.color * _SunScale;
                color = MixFog(color, i.fogAndVertexLight.x);
                return half4(color, base.a);
            }
            ENDHLSL
        }

        Pass
        {
            // 描边：把模型沿法线撑大一圈、只画背面，颜色是贴图乘上描边色
            Name "Outline"
            Tags { "LightMode" = "SRPDefaultUnlit" }
            Cull Front
            ZWrite On
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_fog

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float2 uv : TEXCOORD0; };
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; half fog : TEXCOORD1; float3 positionWS : TEXCOORD2; };

            Varyings vert(Attributes v)
            {
                Varyings o;
                float3 w = TransformObjectToWorld(v.positionOS.xyz);
                float3 n = TransformObjectToWorldNormal(v.normalOS);
                // 离远了线会细到看不见，按距离稍微加粗一点（不超过三倍）
                float dist = distance(w, _WorldSpaceCameraPos);
                w += n * (_OutlineWidth * 0.01 * clamp(dist * 0.35, 1.0, 3.0));
                o.positionCS = TransformWorldToHClip(w);
                o.positionWS = w;
                o.uv = TRANSFORM_TEX(v.uv, _MainTex);
                o.fog = ComputeFogFactor(o.positionCS.z);
                return o;
            }
            half4 frag(Varyings i) : SV_Target
            {
                YJNearFade(i.positionWS, i.positionCS);
                half4 base = YJAnimeBase(i.uv);
                half3 c = base.rgb * _OutlineColor.rgb * (SampleSH(half3(0, 1, 0)) * _Ambient + _MainLightColor.rgb * (_SunScale * 0.5));
                return half4(MixFog(c, i.fog), 1);
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
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            float3 _LightDirection;
            float3 _LightPosition;
            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float2 uv : TEXCOORD0; };
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; };
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
                o.uv = TRANSFORM_TEX(v.uv, _MainTex);
                return o;
            }
            half4 frag(Varyings i) : SV_Target { YJAnimeBase(i.uv); return 0; }
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
            #pragma vertex vert
            #pragma fragment frag
            struct Attributes { float4 positionOS : POSITION; float2 uv : TEXCOORD0; };
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; };
            Varyings vert(Attributes v)
            {
                Varyings o;
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.uv = TRANSFORM_TEX(v.uv, _MainTex);
                return o;
            }
            half4 frag(Varyings i) : SV_Target { YJAnimeBase(i.uv); return i.positionCS.z; }
            ENDHLSL
        }

        Pass
        {
            Name "DepthNormals"
            Tags { "LightMode" = "DepthNormals" }
            ZWrite On
            Cull [_Cull]
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float2 uv : TEXCOORD0; };
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; half3 normalWS : TEXCOORD1; };
            Varyings vert(Attributes v)
            {
                Varyings o;
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.uv = TRANSFORM_TEX(v.uv, _MainTex);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                return o;
            }
            half4 frag(Varyings i, FRONT_FACE_TYPE facing : FRONT_FACE_SEMANTIC) : SV_Target
            {
                YJAnimeBase(i.uv);
                return half4(normalize(i.normalWS) * IS_FRONT_VFACE(facing, 1.0, -1.0), 0);
            }
            ENDHLSL
        }
    }
}
