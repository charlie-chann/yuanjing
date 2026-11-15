// 树叶：树冠是成百上千张「小枝卡片」，每张贴的是一小枝画出来的叶子（tools/textures/leaves.py）。
// 贴图存的是距离场（离叶子边缘多远），所以凑得再近，叶子的轮廓、描边、叶脉都是清楚的线。
// 光照用的法线是建模时指定的「朝树冠外」（tools/blender/trees.py），整棵树明暗成团，不是一片片乱闪。
// 和 YJToon 一样，每一遍都写了 Name 和 LightMode（少写会闪，见 docs/08）。
Shader "Yuanjing/Leaf"
{
    Properties
    {
        _LeafMap("小枝贴图（距离场：R 轮廓 G 线条 B 每片深浅）", 2D) = "white" {}
        _BaseColor("整体染色", Color) = (1, 1, 1, 1)
        _ShadeColor("暗面的颜色", Color) = (0.60, 0.80, 0.92, 1)
        _LitColor("迎光最亮的那一块的颜色", Color) = (1.22, 1.16, 0.70, 1)
        _TwigColor("小枝的颜色", Color) = (0.30, 0.20, 0.13, 1)
        _InkColor("描边和叶脉：把叶子本来的颜色乘上它", Color) = (0.34, 0.46, 0.40, 1)
        _Ink("描边有多重", Range(0, 1)) = 0.85
        _InkWidth("描边有多粗", Range(0, 0.5)) = 0.14
        _Vein("叶脉有多重", Range(0, 1)) = 0.45
        _LeafVary("每片叶子深浅差多少", Range(0, 1)) = 0.34
        _Trans("背光透亮", Range(0, 3)) = 1.0
        _TransColor("透亮的颜色", Color) = (0.86, 1.0, 0.36, 1)
        _ShadeStep("明暗交界的位置", Range(-1, 1)) = 0.02
        _ShadeSoft("交界有多柔", Range(0.01, 1)) = 0.2
        _ShadowAmount("树冠自己的影子有多重", Range(0, 1)) = 0.75
        _Sway("整枝随风摆", Range(0, 2)) = 1
        _Flutter("叶片抖动", Range(0, 3)) = 1
        _WetAmount("会不会淋湿", Range(0, 1)) = 1
        _SnowAmount("会不会积雪", Range(0, 1)) = 0.6
        _Ambient("环境光强度", Range(0, 2)) = 0.5
        _SunScale("太阳光强度", Range(0, 2)) = 0.2
    }
    SubShader
    {
        Tags { "RenderType" = "TransparentCutout" "RenderPipeline" = "UniversalPipeline" "Queue" = "AlphaTest" }

        HLSLINCLUDE
        #pragma target 3.0
        #define YJ_OWN_MATERIAL
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

        CBUFFER_START(UnityPerMaterial)
        half4 _BaseColor;
        half4 _ShadeColor;
        half4 _TwigColor;
        half4 _InkColor;
        half4 _TransColor;
        half4 _LitColor;
        half _Ink;
        half _InkWidth;
        half _Vein;
        half _LeafVary;
        half _Trans;
        half _ShadeStep;
        half _ShadeSoft;
        half _ShadowAmount;
        half _Sway;
        half _Flutter;
        half _WetAmount;
        half _SnowAmount;
        half _Ambient;
        half _SunScale;
        CBUFFER_END

        TEXTURE2D(_LeafMap);
        SAMPLER(sampler_LeafMap);

        #include "Assets/Shaders/YJWeather.hlsl"
        #include "Assets/Shaders/YJToonCommon.hlsl"

        // 风：整枝缓缓地摆（幅度在顶点色第四个数里，越靠外的枝越大），叶梢再快速地抖（uv.y：0 是接在枝上的根，1 是梢）。
        // 画颜色、算影子、算深度这几遍用的是同一个函数，叶子和影子才对得上。
        float3 YJLeafSway(float3 positionOS, half branch, half tip)
        {
            float3 w = TransformObjectToWorld(positionOS);
            float t = _Time.y;
            float gust = 0.55 + 0.45 * sin(t * 0.6 + w.x * 0.13 + w.z * 0.09);
            float amp = (0.03 + 0.11 * _YJWind) * gust;
            float3 off = float3(sin(t * 1.5 + w.x * 0.7) + 0.5, 0.3 * sin(t * 2.2 + w.z), cos(t * 1.2 + w.z * 0.8));
            float f = sin(t * (4.0 + 3.0 * _YJWind) + w.x * 2.3 + w.y * 3.1 + w.z * 1.7) + 0.5 * sin(t * 9.1 + w.x * 5.0 + w.z * 4.0);
            w += off * (amp * branch * _Sway) + float3(0.3, 1.0, 0.3) * (f * amp * 0.3 * tip * _Flutter);
            return TransformWorldToObject(w);
        }

        // 按距离场裁出叶子的形状。远处贴图缩小后边缘会变虚，导入时开了「保住覆盖面积」，所以统一按 0.5 裁
        void YJLeafClip(float2 uv)
        {
            clip(SAMPLE_TEXTURE2D(_LeafMap, sampler_LeafMap, uv).a - 0.5);
        }

        // 贴到镜头跟前的叶子用网点淡掉（平视、第一人称钻进灌木、树枝里时，不会被一片大叶子糊住整个屏幕）。
        // 网点是固定的 4×4 图案，镜头不动时不变，不会闪
        void YJLeafNearFade(float3 positionWS, float4 positionCS)
        {
            float d = distance(positionWS, _WorldSpaceCameraPos);
            if (d > 0.9) return;
            static const float bayer[16] = { 0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0 };
            uint2 px = uint2(positionCS.xy) & 3u;
            float thr = (bayer[px.x + px.y * 4u] + 0.5) / 16.0;
            clip((d - 0.3) / 0.6 - thr);
        }
        ENDHLSL

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            Cull Off
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fog
            #pragma multi_compile_instancing
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
                half3 color : TEXCOORD2;
                half4 fogAndVertexLight : TEXCOORD3;
                float2 uv : TEXCOORD4;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            Varyings vert(Attributes v)
            {
                Varyings o = (Varyings)0;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_TRANSFER_INSTANCE_ID(v, o);
                o.positionWS = TransformObjectToWorld(YJLeafSway(v.positionOS.xyz, v.color.a, v.uv.y));
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.color = SRGBToLinear(v.color.rgb) * _BaseColor.rgb;
                o.uv = v.uv;
                o.fogAndVertexLight.x = ComputeFogFactor(o.positionCS.z);
                #ifdef _ADDITIONAL_LIGHTS_VERTEX
                o.fogAndVertexLight.yzw = VertexLighting(o.positionWS, o.normalWS);
                #endif
                return o;
            }

            half4 frag(Varyings i) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(i);
                half4 t = SAMPLE_TEXTURE2D(_LeafMap, sampler_LeafMap, i.uv);
                clip(t.a - 0.5);
                YJSeeThrough(i.positionWS, i.positionCS);
                YJLeafNearFade(i.positionWS, i.positionCS);

                // 一个像素跨了多少「距离」：线比一个像素还细的时候（离远了）就淡掉，不然整棵树会发黑
                half px = max(fwidth(t.r), 0.0005);
                half ink = (1.0 - smoothstep(0.5 + _InkWidth - px, 0.5 + _InkWidth + px, t.r)) * saturate(_InkWidth / px * 0.6) * _Ink;
                half pg = max(fwidth(t.g), 0.0005);
                half vein = smoothstep(0.62 - pg, 0.62 + pg, t.g) * saturate(0.3 / pg) * _Vein;

                half twig = step(t.b, 0.12);
                half leaf = saturate((t.b - 0.12) / 0.88);
                half3 albedo = i.color * lerp(1.0 - _LeafVary, 1.0 + _LeafVary * 0.55, leaf);
                albedo = lerp(albedo, _TwigColor.rgb, twig);
                albedo = lerp(albedo, albedo * _InkColor.rgb, saturate(max(ink, vein * (1.0 - twig))));

                half3 n = normalize(i.normalWS);
                half up = saturate(n.y);
                if (_YJWet + _YJSnow > 0.001)
                {
                    half open = YJOpenSky(i.positionWS, n);
                    albedo *= lerp(1.0, 0.8, _YJWet * _WetAmount * open);
                    half lie = saturate((up - 0.25) * 2.0) * open * _SnowAmount;
                    half grain = 0.6 + 0.4 * yjNoise(i.positionWS.xz * 2.3) + 0.3 * (yjNoise(i.positionWS.xz * 0.5) - 0.5);
                    half cover = _YJSnow * 1.35;
                    half snow = smoothstep(1.0 - cover, 1.0 - cover + 0.18, lie * grain) * smoothstep(0.0, 0.1, lie);
                    albedo = lerp(albedo, half3(0.90, 0.93, 0.98), snow);
                }

                float4 shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                Light light = GetMainLight(shadowCoord);
                half ndl = dot(n, light.direction);
                half ramp = smoothstep(_ShadeStep - _ShadeSoft, _ShadeStep + _ShadeSoft, ndl);
                half shadow = lerp(1.0, light.shadowAttenuation, _ShadowAmount);
                half lit = ramp * shadow;
                lit *= 1.0 - _YJCloud * smoothstep(0.42, 0.68, yjNoise(i.positionWS.xz * 0.045 + _Time.y * float2(0.016, 0.009)));

                half3 ambient = SampleSH(n) * _Ambient;
                half3 shade = ambient * lerp(_ShadeColor.rgb, half3(1, 1, 1), lit);
                // 三段：暗面偏蓝绿、中间是叶子本色、迎着光的那一块偏黄发亮（动漫里树冠的画法）
                half hot = smoothstep(0.5, 0.8, ndl) * shadow;
                albedo *= lerp(half3(1, 1, 1), _LitColor.rgb, hot);
                half3 color = albedo * (shade + light.color * (lit * _SunScale));

                // 背光透亮：逆着太阳看（比如站在树下仰头），叶子被照透，发黄绿色的光
                half3 v = GetWorldSpaceNormalizeViewDir(i.positionWS);
                half back = saturate(dot(v, -light.direction));
                half trans = back * back * back * _Trans * lerp(0.35, 1.0, light.shadowAttenuation) * (1.0 - twig);
                color += albedo * _TransColor.rgb * light.color * (trans * _SunScale * 1.6);

                #if defined(_ADDITIONAL_LIGHTS)
                uint count = GetAdditionalLightsCount();
                for (uint k = 0u; k < count; ++k)
                {
                    Light l = GetAdditionalLight(k, i.positionWS);
                    color += albedo * l.color * (l.distanceAttenuation * 0.7);
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

        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode" = "ShadowCaster" }
            ZWrite On
            ZTest LEqual
            ColorMask 0
            Cull Off
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
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
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; };

            Varyings vert(Attributes v)
            {
                Varyings o;
                UNITY_SETUP_INSTANCE_ID(v);
                float3 positionWS = TransformObjectToWorld(YJLeafSway(v.positionOS.xyz, v.color.a, v.uv.y));
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
                o.uv = v.uv;
                return o;
            }
            half4 frag(Varyings i) : SV_Target
            {
                YJLeafClip(i.uv);
                return 0;
            }
            ENDHLSL
        }

        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode" = "DepthOnly" }
            ZWrite On
            ColorMask R
            Cull Off
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing

            struct Attributes
            {
                float4 positionOS : POSITION;
                half4 color : COLOR;
                float2 uv : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };
            struct Varyings { float4 positionCS : SV_POSITION; float3 positionWS : TEXCOORD0; float2 uv : TEXCOORD1; };

            Varyings vert(Attributes v)
            {
                Varyings o;
                UNITY_SETUP_INSTANCE_ID(v);
                o.positionWS = TransformObjectToWorld(YJLeafSway(v.positionOS.xyz, v.color.a, v.uv.y));
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.uv = v.uv;
                return o;
            }
            half4 frag(Varyings i) : SV_Target
            {
                YJLeafClip(i.uv);
                YJSeeThrough(i.positionWS, i.positionCS);
                YJLeafNearFade(i.positionWS, i.positionCS);
                return i.positionCS.z;
            }
            ENDHLSL
        }

        Pass
        {
            Name "DepthNormals"
            Tags { "LightMode" = "DepthNormals" }
            ZWrite On
            Cull Off
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                half4 color : COLOR;
                float2 uv : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };
            struct Varyings { float4 positionCS : SV_POSITION; half3 normalWS : TEXCOORD0; float3 positionWS : TEXCOORD1; float2 uv : TEXCOORD2; };

            Varyings vert(Attributes v)
            {
                Varyings o;
                UNITY_SETUP_INSTANCE_ID(v);
                o.positionWS = TransformObjectToWorld(YJLeafSway(v.positionOS.xyz, v.color.a, v.uv.y));
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.uv = v.uv;
                return o;
            }
            half4 frag(Varyings i) : SV_Target
            {
                YJLeafClip(i.uv);
                YJSeeThrough(i.positionWS, i.positionCS);
                YJLeafNearFade(i.positionWS, i.positionCS);
                return half4(normalize(i.normalWS), 0);
            }
            ENDHLSL
        }
    }
}
