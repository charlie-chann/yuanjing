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
        // 手绘图案（大殿彩画、佛像开脸、桌围……tools/textures/painted*.py）：顶点色（白 × 烘好的明暗）乘贴图，uv 是贴图坐标
        _Paint("手绘贴图：顶点色乘贴图", Float) = 0
        _PaintGlow("手绘贴图夜里跟着灯一起亮（宫灯的绢面）", Float) = 0
        // 鎏金：殿里照不到太阳，按一个固定方向的「假光」加一点镜面高光和边缘亮光，不乘影子
        _Gilt("鎏金假高光（不受影子影响）", Range(0, 1)) = 0
        _GiltDir("假高光的光从哪来（世界方向）", Vector) = (0.3, 0.75, -0.6, 0)
        _GiltColor("假高光的颜色", Color) = (1.0, 0.85, 0.52, 1)
        // 鎏金（佛像）：金面上照出来的是「殿」——前面（门口、供桌上的灯烛）一大片亮，头顶的天花中等，两边的墙、地面暗；
        // 再加每盏灯照出的小亮点。凸起、迎着人的面亮，侧过去、朝下的面深，衣褶一道道分得清。0 = 只用上面那一项（旧的做法）
        _GiltEnv("鎏金：照见殿里的明暗（佛像）", Range(0, 1)) = 0
        _GiltDoor("前面那片亮从哪个方向来（世界）", Vector) = (0, 0.12, -1, 0)
        _GiltFloor("照见墙、地面时有多暗", Range(0, 1)) = 0.2
        _GiltDoorK("照见前面那片亮有多亮", Range(0, 3)) = 1.2
        _GiltCeil("照见天花有多亮", Range(0, 2)) = 0.35
        _GiltSpec("高光（灯、假光）有多亮", Range(0, 3)) = 1
        _GiltLamp("灯把殿里照亮多少（算进照见的亮度）", Range(0, 2)) = 0.5
        // 金箔：一片片贴上去的金（R 深浅，GB 每片略斜一点的法线，A 擦磨的亮度），按世界坐标三向平铺
        _GiltLeaf("金箔贴图", 2D) = "gray" {}
        _GiltLeafAmt("金箔深浅有多明显", Range(0, 1)) = 0
        _GiltLeafTilt("每片金箔斜多少（反光一片片地闪）", Range(0, 1)) = 0
        _GiltLeafScale("金箔贴图每米铺几遍", Float) = 2
        // 手绘贴图的 a 是「哪里是金」（背光：火焰、凸起的纹样贴金，石青石绿的底子是颜料）：上面那组鎏金只用在 a 大的地方
        _GiltMask("鎏金只用在贴图 a 标的地方", Float) = 0
        // 灯（glow）：发光的颜色乘顶点色（红灯笼透红光、窗纸透暖白光），1 是全按顶点色
        _GlowTint("发光带上顶点色", Range(0, 1)) = 0
        // 金砖地（殿里）：颜色按世界坐标取一整张画好的地（_FloorMap：每块砖的深浅、磨亮的走道、拜垫前踩出来的一片），
        // 再加一层磨亮的反光：殿里烘好的一张环境图（_FloorCube 白天、_FloorCubeNight 夜里，盒子投影：佛像、红柱、宫灯照在地上的位置对得上）
        _Floor("金砖地", Float) = 0
        _FloorMap("地面整张图（世界 xz）", 2D) = "white" {}
        _FloorDetail("石面细纹（平铺）", 2D) = "gray" {}
        _FloorTile("石面细纹每米铺几遍", Float) = 1.6
        _FloorRect("地面图的范围（x0, z0, 1/宽, 1/深）", Vector) = (0, 0, 1, 1)
        _FloorCube("反光：白天", Cube) = "black" {}
        _FloorCubeNight("反光：夜里", Cube) = "black" {}
        _FloorBoxMin("反光盒子（殿里）最小角", Vector) = (-6.5, 0.72, 14.4, 0)
        _FloorBoxMax("反光盒子最大角", Vector) = (6.5, 5.9, 22, 0)
        _FloorProbe("烘环境图的位置", Vector) = (0, 1.2, 17.5, 0)
        _FloorRefl("反光有多强", Range(0, 1)) = 0.5
        _FloorRough("反光有多糊（0 镜面）", Range(0, 1)) = 0.35
        _FloorNight("夜里地面提亮", Range(0, 2)) = 0.4
        _DetailMap("手绘颗粒（按世界坐标平铺）", 2D) = "gray" {}
        _Detail("颗粒有多明显", Range(0, 0.5)) = 0
        _DetailScale("每米铺几遍", Float) = 0.7
        // 下面这一组是「带真实贴图」的表面用的（树皮、石头、木头……材质上打开 _YJ_TEX 才生效）
        _TexMap("细节贴图：颜色（按世界坐标三向平铺）", 2D) = "gray" {}
        [Normal] _TexNormalMap("细节贴图：法线", 2D) = "bump" {}
        _TexMean("贴图的平均色（贴图除以它，只留明暗纹理）", Color) = (0.5, 0.5, 0.5, 1)
        _TexTile("铺一遍几米", Float) = 1.2
        _TexFine("凑近时再叠一层，密多少倍", Float) = 6
        _TexFineAmount("那一层有多明显", Range(0, 1)) = 0.6
        _TexNormal("凹凸有多明显", Range(0, 2)) = 1
        _TexSpec("高光", Range(0, 1)) = 0.15
        // 一块块的石板（院子的铺地）：每块按自己的顶点色错开、翻转贴图（不然同一块水渍一块块地重复），贴图的深浅也可以减一些
        _TexHash("每块错开贴图", Float) = 0
        _TexContrast("贴图深浅有多明显", Range(0, 1)) = 1
        _ShadeColor("暗面的颜色", Color) = (0.62, 0.66, 0.90, 1)
        _ShadeStep("明暗交界的位置", Range(-1, 1)) = 0.08
        _ShadeSoft("交界有多柔", Range(0.01, 1)) = 0.14
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
            #pragma shader_feature_local_fragment _ _YJ_TEX
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "Assets/Shaders/YJWeather.hlsl"
            #include "Assets/Shaders/YJToonCommon.hlsl"
            #include "Assets/Shaders/YJIndoor.hlsl"
            TEXTURE2D(_BaseMap);
            SAMPLER(sampler_BaseMap);
            TEXTURE2D(_DetailMap);
            SAMPLER(sampler_DetailMap);
            TEXTURE2D(_TexMap);
            SAMPLER(sampler_TexMap);
            TEXTURE2D(_TexNormalMap);
            SAMPLER(sampler_TexNormalMap);
            TEXTURE2D(_GiltLeaf);
            SAMPLER(sampler_GiltLeaf);
            TEXTURE2D(_FloorMap);
            SAMPLER(sampler_FloorMap);
            TEXTURE2D(_FloorDetail);
            SAMPLER(sampler_FloorDetail);
            TEXTURECUBE(_FloorCube);
            SAMPLER(sampler_FloorCube);
            TEXTURECUBE(_FloorCubeNight);
            float _YJCloud;
            // 夜里多少（0 白天 1 夜里，TimeWeather 跟着灯一起给）
            float _YJNight;

            /// 盒子投影：从 p 沿 dir 打到殿的四面墙、地、天花上那一点，换成从烘环境图的地方看过去的方向
            float3 YJBoxProject(float3 dir, float3 p)
            {
                float3 t1 = (_FloorBoxMax.xyz - p) / dir;
                float3 t2 = (_FloorBoxMin.xyz - p) / dir;
                float3 tf = max(t1, t2);
                float t = min(min(tf.x, tf.y), tf.z);
                return p + dir * max(t, 0.0) - _FloorProbe.xyz;
            }

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
                // 手绘贴图的部件 uv.y 是贴图坐标，不能当自发光
                o.color.a = lerp(lerp(v.uv.y, 1.0, _Legacy), 0.0, _Paint);
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
                half paintA = 1.0;
                if (_Legacy > 0.5 || _Paint > 0.5)
                {
                    half4 bm = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, i.uv);
                    albedo *= bm.rgb;
                    paintA = bm.a;
                }
                // 金砖地：整张画好的地（按世界坐标）乘一层平铺的石面细纹；a 是磨得多亮（走道、拜垫前亮）
                half floorPolish = 0.0;
                if (_Floor > 0.5)
                {
                    float2 fuv = (i.positionWS.xz - _FloorRect.xy) * _FloorRect.zw;
                    half4 fl = SAMPLE_TEXTURE2D(_FloorMap, sampler_FloorMap, fuv);
                    half fd = SAMPLE_TEXTURE2D(_FloorDetail, sampler_FloorDetail, i.positionWS.xz * _FloorTile).r;
                    albedo = fl.rgb * _BaseColor.rgb * (0.88 + 0.24 * fd);
                    floorPolish = fl.a;
                }
                // 手绘颗粒：从三个方向按世界坐标铺上去，大块纯色里有细微的深浅，不是光溜溜一片
                if (_Detail > 0.001)
                {
                    half3 w = abs(n);
                    w = w * w * w * w;
                    w /= (w.x + w.y + w.z);
                    float3 q = i.positionWS * _DetailScale;
                    half g = SAMPLE_TEXTURE2D(_DetailMap, sampler_DetailMap, q.zy).r * w.x
                           + SAMPLE_TEXTURE2D(_DetailMap, sampler_DetailMap, q.xz).r * w.y
                           + SAMPLE_TEXTURE2D(_DetailMap, sampler_DetailMap, q.xy).r * w.z;
                    albedo *= 1.0 + (g - 0.5) * 2.0 * _Detail;
                }
                // 金箔（佛像的鎏金）：一片片的深浅；每片贴得略斜一点，反光的法线跟着偏一点（镜头一动金面一片片地闪，不是塑料那样一整片顺滑）
                half4 leaf = half4(0.5, 0.5, 0.5, 0.5);
                half3 nGilt = n;
                if (_GiltEnv > 0.001 && _GiltLeafAmt + _GiltLeafTilt > 0.001)
                {
                    half3 w = abs(n);
                    w = w * w * w * w;
                    w /= (w.x + w.y + w.z);
                    float3 q = i.positionWS * _GiltLeafScale;
                    half4 lx = SAMPLE_TEXTURE2D(_GiltLeaf, sampler_GiltLeaf, q.zy);
                    half4 ly = SAMPLE_TEXTURE2D(_GiltLeaf, sampler_GiltLeaf, q.xz);
                    half4 lz = SAMPLE_TEXTURE2D(_GiltLeaf, sampler_GiltLeaf, q.xy);
                    leaf = lx * w.x + ly * w.y + lz * w.z;
                    // 贴图的 g、b 是这一片往贴图 u、v 两个方向斜多少：换成世界方向（三个投影面各自的 u、v）
                    half3 tilt = half3(0, lx.b - 0.5, lx.g - 0.5) * w.x + half3(ly.g - 0.5, 0, ly.b - 0.5) * w.y + half3(lz.g - 0.5, lz.b - 0.5, 0) * w.z;
                    nGilt = normalize(n + tilt * (2.0 * _GiltLeafTilt));
                    albedo *= 1.0 + (leaf.r - 0.5) * 2.0 * _GiltLeafAmt;
                }
                half3 nGeo = n;
                half relief = 0;
                #if defined(_YJ_TEX)
                {
                    // 真实贴图：从三个方向按世界坐标铺（模型不用展贴图）。颜色只取「相对平均色的明暗」乘到本来的颜色上，
                    // 所以配色还是统一的那一套；法线贴图让表面有真实的凹凸。
                    half3 w = abs(n);
                    w = w * w * w * w * w * w;
                    w /= (w.x + w.y + w.z);
                    float3 q = i.positionWS / _TexTile;
                    // 每块石板错开：顶点色（每块略有不同）当成随机数，平移贴图、再左右上下翻一翻（法线的分量跟着翻）
                    half2 flip = half2(1, 1);
                    if (_TexHash > 0.5)
                    {
                        float hsh = frac(sin(dot(i.color.rgb, float3(127.1, 311.7, 74.7))) * 43758.5453);
                        float hsh2 = frac(hsh * 17.13 + 0.31);
                        q += float3(hsh, hsh2, frac(hsh * 7.7)) * 9.0;
                        flip = half2(hsh2 < 0.5 ? -1 : 1, frac(hsh * 3.1) < 0.5 ? -1 : 1);
                        q.xz *= flip;
                    }
                    half3 tex = SAMPLE_TEXTURE2D(_TexMap, sampler_TexMap, q.zy).rgb * w.x
                              + SAMPLE_TEXTURE2D(_TexMap, sampler_TexMap, q.xz).rgb * w.y
                              + SAMPLE_TEXTURE2D(_TexMap, sampler_TexMap, q.xy).rgb * w.z;
                    half3 tx = UnpackNormal(SAMPLE_TEXTURE2D(_TexNormalMap, sampler_TexNormalMap, q.zy));
                    half3 ty = UnpackNormal(SAMPLE_TEXTURE2D(_TexNormalMap, sampler_TexNormalMap, q.xz));
                    ty.xy *= flip;
                    half3 tz = UnpackNormal(SAMPLE_TEXTURE2D(_TexNormalMap, sampler_TexNormalMap, q.xy));
                    // 凑近时（几米以内）再叠一层密得多的：只取朝向最正的那一面，省采样
                    float dist = distance(i.positionWS, _WorldSpaceCameraPos);
                    half fine = _TexFineAmount * saturate(1.0 - dist / 5.0);
                    if (fine > 0.01)
                    {
                        float2 fq = (w.x > w.y && w.x > w.z ? q.zy : w.y > w.z ? q.xz : q.xy) * _TexFine;
                        half3 ft = SAMPLE_TEXTURE2D(_TexMap, sampler_TexMap, fq).rgb;
                        half3 fn = UnpackNormal(SAMPLE_TEXTURE2D(_TexNormalMap, sampler_TexNormalMap, fq));
                        tex *= lerp(half3(1, 1, 1), ft / max(_TexMean.rgb, 0.02), fine);
                        tx.xy += fn.xy * fine * w.x;
                        ty.xy += fn.xy * fine * w.y;
                        tz.xy += fn.xy * fine * w.z;
                    }
                    albedo *= lerp(half3(1, 1, 1), clamp(tex / max(_TexMean.rgb, 0.02), 0.16, 1.7), _TexContrast);
                    // 三个方向的法线合起来（whiteout 混合）
                    tx = half3(tx.xy * _TexNormal + n.zy, abs(tx.z) * n.x);
                    ty = half3(ty.xy * _TexNormal + n.xz, abs(ty.z) * n.y);
                    tz = half3(tz.xy * _TexNormal + n.xy, abs(tz.z) * n.z);
                    n = normalize(tx.zyx * w.x + ty.xzy * w.y + tz.xyz * w.z);
                }
                #endif
                half up = saturate(nGeo.y);

                // 天气：淋湿变深，积雪变白（屋檐下不湿不白）
                // 手绘贴图的部件按图案本身的颜色发光（宫灯绢面上画的花纹透出来），别的按 uv.y
                half3 emission = _EmissionColor.rgb * (_Paint > 0.5 ? albedo * _PaintGlow : (half3)i.color.a);
                // 灯：透出来的光带上灯罩自己的颜色（红灯笼是红的、窗纸是暖白的；按最亮的那一档归一，再开个方，不至于红得发黑）
                if (_GlowTint > 0.001)
                {
                    half3 tc = i.color.rgb / max(max(i.color.r, i.color.g), max(i.color.b, 1e-3));
                    emission *= lerp(half3(1, 1, 1), sqrt(tc), _GlowTint);
                }
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
                // 明暗的大块面按模型本来的法线分（干净的两段），凹凸的细节另外叠上去
                half ndl = dot(nGeo, light.direction);
                half ramp = smoothstep(_ShadeStep - _ShadeSoft, _ShadeStep + _ShadeSoft, ndl);
                #if defined(_YJ_TEX)
                relief = dot(n, light.direction) - ndl;
                ramp = saturate(ramp + relief * 0.9 * smoothstep(-0.35, 0.25, ndl));
                #endif
                half lit = ramp * light.shadowAttenuation;
                // 云影：大块的明暗在地上慢慢飘过（只在俯视的场景里开，_YJCloud 是强度）
                lit *= 1.0 - _YJCloud * smoothstep(0.42, 0.68, yjNoise(i.positionWS.xz * 0.045 + _Time.y * float2(0.016, 0.009)));

                half ao = 1.0;
                #if defined(_SCREEN_SPACE_OCCLUSION)
                float2 suv = GetNormalizedScreenSpaceUV(i.positionCS);
                AmbientOcclusionFactor aof = GetScreenSpaceAmbientOcclusion(suv);
                ao = aof.indirectAmbientOcclusion;
                #endif

                half3 ambient = YJIndoorAmbient(SampleSH(n) * _Ambient, i.positionWS);
                // 暗面：只有环境光，再偏一点蓝紫；亮面：环境光加太阳
                half3 shade = ambient * lerp(_ShadeColor.rgb, half3(1, 1, 1), lit) * lerp(1.0, ao, 0.85);
                half3 color = albedo * (shade + light.color * (lit * _SunScale));
                half3 v = GetWorldSpaceNormalizeViewDir(i.positionWS);
                // 鎏金（_GiltEnv）：殿里有多亮（不看朝向：环境光加上灯照亮的那一份），每盏灯在金面上照出的小亮点
                half3 room = ambient * lerp(1.0, ao, 0.85);
                half3 lampSpec = 0;

                #if defined(_ADDITIONAL_LIGHTS)
                uint count = GetAdditionalLightsCount();
                for (uint k = 0u; k < count; ++k)
                {
                    Light l = GetAdditionalLight(k, i.positionWS);
                    half d = smoothstep(-0.1, 0.5, dot(n, l.direction));
                    // 殿里的灯不投影子：屏幕空间 AO 也压一压灯照的这一份（以前只压环境光，殿里地面主要是灯照亮的，人、拜垫、桌腿底下一点不暗）
                    color += albedo * l.color * (l.distanceAttenuation * d * lerp(1.0, ao, 0.7));
                    if (_GiltEnv > 0.001)
                    {
                        room += l.color * (l.distanceAttenuation * _GiltLamp);
                        half3 hl = normalize(l.direction + v);
                        lampSpec += l.color * (l.distanceAttenuation * pow(saturate(dot(nGilt, hl)), 48.0));
                    }
                }
                #endif
                #ifdef _ADDITIONAL_LIGHTS_VERTEX
                color += albedo * i.fogAndVertexLight.yzw * lerp(1.0, ao, 0.7);
                room += i.fogAndVertexLight.yzw * _GiltLamp;
                #endif

                // 背光这种一半金一半颜料的手绘贴图：鎏金只用在贴图 a 标出来的金上
                half giltEnv = _GiltEnv * (_GiltMask > 0.5 ? paintA : 1.0);
                if (_GiltEnv > 0.001)
                {
                    // 鎏金（佛像）：金属的颜色是它照见的东西。按反射方向在一个假的「殿」里取明暗：前面（殿门、供桌上的灯烛）一大片亮，
                    // 朝上照见天花（中等），朝两边照见墙、朝下照见地面（暗）。迎着人、凸起来的面亮，侧过去、往下的面是深褐金，衣褶、莲瓣一道道分得清；
                    // 镜头一走，亮的地方跟着在金面上滑。都乘「殿里有多亮」：白天、夜里（灯烛）各按各的亮度，暗处不自己发光
                    half3 r = reflect(-v, nGilt);
                    half front = saturate(dot(r, normalize(_GiltDoor.xyz)));
                    half env = _GiltFloor + _GiltDoorK * front * front * front + _GiltCeil * smoothstep(0.1, 0.9, r.y);
                    env *= lerp(0.6, 1.0, smoothstep(-0.75, -0.1, r.y));
                    half3 metal = albedo * room * env;
                    // 高光：固定方向的假光（头顶偏前）加每盏灯的亮点；最亮处偏淡金（金箔的高光接近白），擦磨得亮的地方（leaf.a）更亮
                    half3 gh = normalize(normalize(_GiltDir.xyz) + v);
                    half nh = saturate(dot(nGilt, gh));
                    half key = pow(nh, 64.0) + 0.15 * pow(nh, 12.0);
                    half lumRoom = dot(room, half3(0.3, 0.59, 0.11));
                    half3 hi = lerp(albedo * 1.5, _GiltColor.rgb, 0.55);
                    half3 glint = hi * (key * lumRoom * 2.0 + lampSpec) * (_GiltSpec * lerp(1.0, lerp(0.55, 1.25, leaf.a), saturate(_GiltLeafAmt * 2.5)));
                    color = lerp(color, metal, giltEnv) + glint * giltEnv;
                }
                else if (_Gilt > 0.001)
                {
                    // 鎏金：金属的颜色主要是它「照出来的」东西——反射方向朝上照见灯和亮的天花，朝下照见暗的地面。
                    // 按反射方向给金面一层随镜头变化的深浅（迎着人、朝上的面亮，朝下、凹进去的深），再加一个固定方向「假光」的高光和边缘亮光。
                    // 都不乘影子（殿里太阳照不到，lit 是 0）；高光乘环境光的亮度，暗处不会自己发亮
                    half amb = saturate(dot(ambient, half3(0.3, 0.59, 0.11)) * 2.0 + 0.25);
                    half3 r = reflect(-v, n);
                    half up = saturate(r.y * 0.55 + 0.5);
                    color *= lerp(1.0, lerp(0.55, 1.35, up * up * (3.0 - 2.0 * up)), _Gilt);
                    half3 gh = normalize(normalize(_GiltDir.xyz) + v);
                    half nh = saturate(dot(n, gh));
                    half spec = pow(nh, 40.0) + pow(nh, 8.0) * 0.25;
                    half fres = pow(1.0 - saturate(dot(n, v)), 2.5) * saturate(n.y * 0.5 + 0.6);
                    // 最亮处偏淡金（金箔的高光接近白），不全是金色本身
                    half3 hi = lerp(albedo * 1.6, _GiltColor.rgb, 0.4);
                    color += hi * _Gilt * (spec * 1.6 + fres * 0.45) * amb;
                }
                if (_Floor > 0.5)
                {
                    // 磨亮的金砖：照出殿里的东西（佛像的金、红柱、宫灯），斜着看更亮（菲涅尔），磨得多的地方（走道、拜垫前）更亮更清楚。
                    // 白天、夜里各一张环境图，再乘「殿里此刻有多亮」（同鎏金：环境光加灯）
                    half3 rv = reflect(-v, nGeo);
                    float3 bp = YJBoxProject(rv, i.positionWS);
                    half rough = _FloorRough * (1.0 - 0.45 * floorPolish);
                    half3 env = lerp(SAMPLE_TEXTURECUBE_LOD(_FloorCube, sampler_FloorCube, bp, rough * 6.0).rgb,
                                     SAMPLE_TEXTURECUBE_LOD(_FloorCubeNight, sampler_FloorCube, bp, rough * 6.0).rgb, saturate(_YJNight));
                    half nv = saturate(dot(nGeo, v));
                    half fres = 0.06 + 0.94 * pow(1.0 - nv, 4.0);
                    half k = _FloorRefl * fres * lerp(0.55, 1.0, floorPolish) * lerp(1.0, ao, 0.6);
                    color = color * (1.0 - k * 0.6) + env * k;
                    // 夜里殿里只有灯：地面整片快黑了（亮度 28/255），托起来一点（不是灯照的，是「眼睛适应了」的那一份）
                    color += albedo * _FloorNight * saturate(_YJNight) * 0.12;
                }
                #if defined(_YJ_TEX)
                // 一点高光：凹凸迎着光的地方亮一下
                half3 hv = normalize(light.direction + v);
                color += light.color * (_SunScale * _TexSpec * lit * pow(saturate(dot(n, hv)), 28.0));
                #endif
                // 边缘光：朝上的亮面边缘微微发亮，物体的轮廓更清楚
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
