// 香烟、光点、水花这类小粒子：不受光的半透明。_Lit 为 1 时按环境光着色（烟在夜里要暗下去），
// _Dst 为 1 是叠亮（光点），10 是普通半透明（烟、水花）。
// _Outdoor 为 1 的（飘落的花瓣树叶、萤火虫、蝴蝶）：头顶有屋檐的地方不画（同雨雪，用同一张高度图）——
// 跟着人飘的那一层在大殿里会从屋顶穿下来、落在殿里。
Shader "Yuanjing/Particle"
{
    Properties
    {
        _MainTex("形状", 2D) = "white" {}
        [HDR] _Color("颜色", Color) = (1, 1, 1, 1)
        _Lit("跟着环境光", Float) = 0
        _Dst("混合方式", Float) = 10
        _Outdoor("只在露天", Float) = 0
        _Near("离镜头多近开始淡（米）：x 以内看不见，y 以外照常", Vector) = (0.5, 1.5, 0, 0)
    }
    SubShader
    {
        Tags { "Queue" = "Transparent" "RenderType" = "Transparent" "RenderPipeline" = "UniversalPipeline" "IgnoreProjector" = "True" }
        Blend SrcAlpha [_Dst]
        ZWrite Off
        Cull Off
        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_fog
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            TEXTURE2D(_YJHeightMap); SAMPLER(sampler_YJHeightMap);
            float4 _YJHeightParams;
            half4 _YJPrecipTint;
            CBUFFER_START(UnityPerMaterial)
            float4 _MainTex_ST;
            half4 _Color;
            half _Lit;
            half _Dst;
            half _Outdoor;
            float4 _Near;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; float2 uv : TEXCOORD0; half4 color : COLOR; };
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; half4 color : COLOR; float fog : TEXCOORD1; float3 positionWS : TEXCOORD2; };

            Varyings vert(Attributes v)
            {
                Varyings o;
                o.positionWS = TransformObjectToWorld(v.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.uv = v.uv;
                o.color = v.color;
                o.fog = ComputeFogFactor(o.positionCS.z);
                return o;
            }

            half4 frag(Varyings i) : SV_Target
            {
                half4 c = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv) * i.color * _Color;
                c.rgb *= lerp(half3(1, 1, 1), _YJPrecipTint.rgb, _Lit);
                if (_Outdoor > 0.5)
                {
                    // 屋檐下（高度图里头顶的屋面比这一点高）：不画
                    float2 huv = (i.positionWS.xz - _YJHeightParams.xy) * _YJHeightParams.zw;
                    float h = SAMPLE_TEXTURE2D_LOD(_YJHeightMap, sampler_YJHeightMap, huv, 0).r;
                    c.a *= smoothstep(-0.9, -0.4, i.positionWS.y - h);
                }
                // 离镜头太近的淡掉：贴着镜头的一粒在画面上是一大团白斑（许愿树下系布条的特写，镜头离布条 1.3–1.5 米，
                // 中间飘过的光点、花瓣一粒有半个巴掌大）。默认 0.5 米以内看不见、1.5 米以外照常；阳光里的浮尘远一些（BuildIslet）
                c.a *= smoothstep(_Near.x, _Near.y, i.positionCS.w);
                c.rgb = MixFog(c.rgb, i.fog);
                return c;
            }
            ENDHLSL
        }
    }
}
