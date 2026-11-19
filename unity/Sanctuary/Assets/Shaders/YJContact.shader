// 贴地的接触影子（殿里）：殿里的灯不投影子、SSAO 只压暗环境光，人、拜垫、蒲团、供桌腿底下一点暗都没有，看着像贴上去、浮在金砖上。
// 一块平放在地上的方片，乘到地面上（Blend DstColor Zero）：中间深、往外软软地淡掉。
// _Round 1 是椭圆（人、蒲团、柱子），0 是圆角长方（拜垫、供桌、经案）；_Soft 是边上淡掉的那一圈占半边长的几成；
// _Strength 最深处压暗多少（每个人身上用 MaterialPropertyBlock 按脚离地多高再乘一下）
Shader "Yuanjing/Contact"
{
    Properties
    {
        _Strength("深浅", Range(0, 1)) = 0.5
        _Soft("边上淡掉的一圈", Range(0.05, 1)) = 0.5
        _Round("椭圆（1）还是圆角长方（0）", Float) = 1
        _Tint("影子的颜色", Color) = (0.32, 0.24, 0.2, 1)
    }
    SubShader
    {
        Tags { "Queue" = "Transparent-90" "RenderType" = "Transparent" "RenderPipeline" = "UniversalPipeline" "IgnoreProjector" = "True" }
        Pass
        {
            Name "Contact"
            Tags { "LightMode" = "UniversalForward" }
            Blend DstColor Zero
            ZWrite Off
            ZTest LEqual
            Cull Off
            Offset -1, -1
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            CBUFFER_START(UnityPerMaterial)
            half _Strength, _Soft, _Round;
            half4 _Tint;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; float2 uv : TEXCOORD0; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; UNITY_VERTEX_INPUT_INSTANCE_ID };

            Varyings vert(Attributes v)
            {
                Varyings o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_TRANSFER_INSTANCE_ID(v, o);
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.uv = v.uv;
                return o;
            }

            half4 frag(Varyings i) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(i);
                float2 p = abs(i.uv * 2.0 - 1.0);
                // 0 在中间那一块里，1 在边上
                float inner = 1.0 - _Soft;
                float dr = length(max(p - inner, 0.0)) / max(_Soft, 1e-3);
                float de = saturate((length(p) - inner) / max(_Soft, 1e-3));
                float d = lerp(dr, de, _Round);
                half a = (1.0 - smoothstep(0.0, 1.0, d)) * _Strength;
                // 中间也带一点点从中心往外的渐变，不是一整块平的深色
                a *= lerp(1.0, 0.75, saturate(length(p)));
                return half4(lerp(half3(1, 1, 1), _Tint.rgb, a), 1);
            }
            ENDHLSL
        }
    }
}
