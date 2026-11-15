// 天空：两张实拍的全景天空之间渐变（换天色时用），加上打雷时的闪光。
Shader "Yuanjing/Sky"
{
    Properties
    {
        [NoScaleOffset] _TexA("天空 A", 2D) = "black" {}
        [NoScaleOffset] _TexB("天空 B", 2D) = "black" {}
        _Blend("A 到 B", Range(0, 1)) = 0
        _RotA("A 的方位（弧度）", Float) = 0
        _RotB("B 的方位（弧度）", Float) = 0
        _ExpA("A 的曝光", Float) = 1
        _ExpB("B 的曝光", Float) = 1
        _TintA("A 的染色", Color) = (1, 1, 1, 1)
        _TintB("B 的染色", Color) = (1, 1, 1, 1)
        _Ground("地平线以下的颜色", Color) = (0.2, 0.22, 0.25, 1)
        _Flash("闪电", Float) = 0
        _MaxBright("亮度上限", Float) = 40
    }
    SubShader
    {
        Tags { "Queue" = "Background" "RenderType" = "Background" "PreviewType" = "Skybox" }
        Cull Off
        ZWrite Off
        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            TEXTURE2D(_TexA); SAMPLER(sampler_TexA);
            TEXTURE2D(_TexB); SAMPLER(sampler_TexB);
            float _Blend, _RotA, _RotB, _ExpA, _ExpB, _Flash, _MaxBright;
            half4 _TintA, _TintB, _Ground;

            struct Attributes { float4 positionOS : POSITION; };
            struct Varyings { float4 positionCS : SV_POSITION; float3 dir : TEXCOORD0; };

            Varyings vert(Attributes v)
            {
                Varyings o;
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.dir = v.positionOS.xyz;
                return o;
            }

            // 方向 → 全景图坐标。和 TimeWeather.cs 里从图上找太阳的换算是同一套。
            float2 LatLong(float3 d, float rot)
            {
                float lon = atan2(d.z, d.x) + rot;
                float lat = acos(clamp(d.y, -1.0, 1.0));
                return float2(0.5 - lon / TWO_PI, 1.0 - lat / PI);
            }

            half4 frag(Varyings i) : SV_Target
            {
                float3 d = normalize(i.dir);
                // 地平线以下用地平线那一圈的颜色，避免看到拍摄地的地面
                float3 ds = normalize(float3(d.x, max(d.y, 0.004), d.z));
                half3 a = SAMPLE_TEXTURE2D_LOD(_TexA, sampler_TexA, LatLong(ds, _RotA), 0).rgb * _ExpA * _TintA.rgb;
                half3 b = SAMPLE_TEXTURE2D_LOD(_TexB, sampler_TexB, LatLong(ds, _RotB), 0).rgb * _ExpB * _TintB.rgb;
                half3 c = lerp(a, b, _Blend);
                c = min(c, _MaxBright);
                c = lerp(c, _Ground.rgb, smoothstep(0.0, -0.12, d.y));
                c += _Flash * half3(0.75, 0.82, 1.0) * (0.25 + saturate(dot(c, half3(0.3, 0.5, 0.2))));
                return half4(c, 1.0);
            }
            ENDHLSL
        }
    }
}
