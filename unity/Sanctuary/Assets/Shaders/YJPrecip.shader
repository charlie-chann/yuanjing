// 雨丝、雪花、水花：不受光的半透明粒子。头顶有屋檐的地方不画（和表面着色器用同一张高度图）。
Shader "Yuanjing/Precip"
{
    Properties
    {
        _MainTex("形状", 2D) = "white" {}
        [HDR] _Color("颜色", Color) = (1, 1, 1, 1)
    }
    SubShader
    {
        Tags { "Queue" = "Transparent" "RenderType" = "Transparent" "RenderPipeline" = "UniversalPipeline" "IgnoreProjector" = "True" }
        Blend SrcAlpha OneMinusSrcAlpha
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
            half4 _YJPrecipTint; // 雨雪被环境光照亮的颜色，由 TimeWeather 设
            CBUFFER_START(UnityPerMaterial)
            float4 _MainTex_ST;
            half4 _Color;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; float2 uv : TEXCOORD0; half4 color : COLOR; };
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; half4 color : COLOR; float3 positionWS : TEXCOORD1; float fog : TEXCOORD2; };

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
                float2 huv = (i.positionWS.xz - _YJHeightParams.xy) * _YJHeightParams.zw;
                float h = SAMPLE_TEXTURE2D_LOD(_YJHeightMap, sampler_YJHeightMap, huv, 0).r;
                float open = smoothstep(-0.9, -0.4, i.positionWS.y - h);
                half4 c = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv) * i.color * _Color;
                c.rgb *= _YJPrecipTint.rgb;
                c.a *= open;
                // 离镜头太近的淡掉，不然会糊在眼前
                c.a *= smoothstep(0.35, 1.2, i.positionCS.w);
                c.rgb = MixFog(c.rgb, i.fog);
                return c;
            }
            ENDHLSL
        }
    }
}
