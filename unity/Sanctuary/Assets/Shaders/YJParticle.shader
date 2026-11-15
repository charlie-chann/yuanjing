// 香烟、光点、水花这类小粒子：不受光的半透明。_Lit 为 1 时按环境光着色（烟在夜里要暗下去），
// _Dst 为 1 是叠亮（光点），10 是普通半透明（烟、水花）。
Shader "Yuanjing/Particle"
{
    Properties
    {
        _MainTex("形状", 2D) = "white" {}
        [HDR] _Color("颜色", Color) = (1, 1, 1, 1)
        _Lit("跟着环境光", Float) = 0
        _Dst("混合方式", Float) = 10
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
            half4 _YJPrecipTint;
            CBUFFER_START(UnityPerMaterial)
            float4 _MainTex_ST;
            half4 _Color;
            half _Lit;
            half _Dst;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; float2 uv : TEXCOORD0; half4 color : COLOR; };
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; half4 color : COLOR; float fog : TEXCOORD1; };

            Varyings vert(Attributes v)
            {
                Varyings o;
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.uv = v.uv;
                o.color = v.color;
                o.fog = ComputeFogFactor(o.positionCS.z);
                return o;
            }

            half4 frag(Varyings i) : SV_Target
            {
                half4 c = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv) * i.color * _Color;
                c.rgb *= lerp(half3(1, 1, 1), _YJPrecipTint.rgb, _Lit);
                // 离镜头太近的淡掉
                c.a *= smoothstep(0.25, 0.9, i.positionCS.w);
                c.rgb = MixFog(c.rgb, i.fog);
                return c;
            }
            ENDHLSL
        }
    }
}
