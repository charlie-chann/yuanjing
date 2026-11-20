using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using Yuanjing;

/// 贴图导入规则：法线图、合一图、天空各有各的设置。放进对应文件夹就自动生效。
public class TextureRules : AssetPostprocessor
{
    // 改了规则就加一，所有贴图会重新导入（2026-11-17 加 paint_* 那一条时没有加：那些贴图是新放进来的，第一次导入就按新规则）
    public override uint GetVersion() => 4;

    void OnPreprocessTexture()
    {
        var imp = (TextureImporter)assetImporter;
        string name = Path.GetFileNameWithoutExtension(assetPath);
        // 人物和花草：三线性过滤（远近档位平滑过渡，走动时不会一条条地跳），带透明的保住远处的覆盖面积（不会越远越稀、一闪一闪）
        if (assetPath.StartsWith("Assets/Plants/") || assetPath.StartsWith("Assets/Characters/"))
        {
            imp.mipmapEnabled = true;
            imp.filterMode = FilterMode.Trilinear;
            imp.anisoLevel = 4;
            if (assetPath.EndsWith("_color.png"))
            {
                imp.alphaIsTransparency = true;
                imp.mipMapsPreserveCoverage = true;
                imp.alphaTestReferenceValue = 0.45f;
            }
            return;
        }
        // 湖心小寺的贴图：地面那张很大、要清楚（各向异性开高，斜着看不糊）；颗粒图是平铺的灰度图
        if (assetPath.StartsWith("Assets/Toon/Textures/") && name.StartsWith("m_"))
        {
            // 表面细节贴图（tools/textures/prep.py）：按世界坐标平铺，凑近看要清楚；_n 是法线
            bool normal = name.EndsWith("_n");
            imp.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
            imp.sRGBTexture = !normal;
            imp.maxTextureSize = 2048;
            imp.mipmapEnabled = true;
            imp.filterMode = FilterMode.Trilinear;
            imp.anisoLevel = 8;
            imp.wrapMode = TextureWrapMode.Repeat;
            var t = imp.GetPlatformTextureSettings("iPhone");
            t.overridden = true;
            t.maxTextureSize = 2048;
            t.format = normal ? TextureImporterFormat.ASTC_5x5 : TextureImporterFormat.ASTC_6x6;
            imp.SetPlatformTextureSettings(t);
            return;
        }
        if (assetPath.StartsWith("Assets/Toon/Textures/") && name.StartsWith("leaf_"))
        {
            // 叶子的距离场贴图（tools/textures/leaves.py）：存的是数不是颜色；远处缩小后保住覆盖面积，树冠不会越远越稀
            imp.sRGBTexture = false;
            imp.alphaSource = TextureImporterAlphaSource.FromInput;
            imp.alphaIsTransparency = false;
            imp.maxTextureSize = 1024;
            imp.mipmapEnabled = true;
            imp.mipMapsPreserveCoverage = true;
            imp.alphaTestReferenceValue = 0.5f;
            imp.filterMode = FilterMode.Trilinear;
            imp.anisoLevel = 8;
            imp.wrapMode = TextureWrapMode.Clamp;
            var t = imp.GetPlatformTextureSettings("iPhone");
            t.overridden = true;
            t.maxTextureSize = 1024;
            t.format = TextureImporterFormat.ASTC_4x4;
            imp.SetPlatformTextureSettings(t);
            return;
        }
        if (assetPath.StartsWith("Assets/Toon/Textures/") && name.StartsWith("paint_"))
        {
            // 手绘图案（tools/textures/painted*.py：大殿彩画、佛像开脸、桌围、幡……）：按模型的 uv 贴，凑近看要清楚。
            // 图集里每一块往里缩了 2.5 像素：手机上用 ASTC 4×4（块最小、最清楚），相邻两块的颜色不串；保持原来的尺寸，不缩成 2 的幂。
            // 大殿三张、佛脸、背光的 uv 都在 0..1 里，边上不能绕到对边去；桌围、幡、须弥座、垂带这些有平铺（uv 超出 1）
            imp.textureType = TextureImporterType.Default;
            imp.sRGBTexture = true;
            imp.npotScale = TextureImporterNPOTScale.None;
            // 壁画的图集 2048×4096（十二幅、每间一幅不重复）：长边要 4096
            int max = name == "paint_wall" ? 4096 : 2048;
            imp.maxTextureSize = max;
            imp.mipmapEnabled = true;
            imp.filterMode = FilterMode.Trilinear;
            imp.anisoLevel = 8;
            bool clamp = name == "paint_beam" || name == "paint_ceiling" || name == "paint_wall" || name == "paint_buddha_face" || name == "paint_mandorla";
            imp.wrapMode = clamp ? TextureWrapMode.Clamp : TextureWrapMode.Repeat;
            var tp = imp.GetPlatformTextureSettings("iPhone");
            tp.overridden = true;
            tp.maxTextureSize = max;
            tp.format = TextureImporterFormat.ASTC_4x4;
            tp.compressionQuality = (int)TextureCompressionQuality.Best;
            imp.SetPlatformTextureSettings(tp);
            return;
        }
        if (assetPath.StartsWith("Assets/Toon/Textures/"))
        {
            bool grain = name.Contains("grain");
            // 湖心小寺的地面（2026-11-19 岛扩大以后是 8192 × 8192，一个像素约 1 厘米）：保持 8192，用 ASTC 8×8（包里约 22 MB）。
            // 照别的贴图那样限到 4096、ASTC 5×5 是 14 MB，但一个像素 2 厘米，比扩建前（1.4 厘米）还糊；8192 用 5×5 要 57 MB，用不起
            if (name == "islet_ground")
            {
                imp.maxTextureSize = 8192;
                imp.mipmapEnabled = true;
                imp.filterMode = FilterMode.Trilinear;
                imp.anisoLevel = 8;
                imp.wrapMode = TextureWrapMode.Clamp;
                imp.sRGBTexture = true;
                var gios = imp.GetPlatformTextureSettings("iPhone");
                gios.overridden = true;
                gios.maxTextureSize = 8192;
                gios.format = TextureImporterFormat.ASTC_8x8;
                imp.SetPlatformTextureSettings(gios);
                return;
            }
            imp.maxTextureSize = 4096;
            imp.mipmapEnabled = true;
            imp.filterMode = FilterMode.Trilinear;
            imp.anisoLevel = 8;
            imp.wrapMode = grain ? TextureWrapMode.Repeat : TextureWrapMode.Clamp;
            imp.sRGBTexture = !grain;
            var tios = imp.GetPlatformTextureSettings("iPhone");
            tios.overridden = true;
            tios.maxTextureSize = 4096;
            tios.format = grain ? TextureImporterFormat.ASTC_6x6 : TextureImporterFormat.ASTC_5x5;
            imp.SetPlatformTextureSettings(tios);
            return;
        }
        if (assetPath.StartsWith("Assets/Textures/"))
        {
            imp.maxTextureSize = 2048;
            imp.mipmapEnabled = true;
            // 三线性：远近两档之间平滑混合。原来的双线性在档位交界处是硬切，人一走动交界线就跟着滑，看着像贴图在变
            imp.filterMode = FilterMode.Trilinear;
            imp.anisoLevel = 8;
            if (name.StartsWith("gen_leaves") || name.StartsWith("gen_maple"))
            {
                imp.mipMapsPreserveCoverage = true;
                imp.alphaTestReferenceValue = 0.45f;
            }
            imp.wrapMode = TextureWrapMode.Repeat;
            if (name.EndsWith("_normal")) imp.textureType = TextureImporterType.NormalMap;
            else if (name.EndsWith("_arm") || name.EndsWith("_mask")) imp.sRGBTexture = false;
            if (name.StartsWith("gen_") && name.EndsWith("_color")) imp.alphaIsTransparency = true;
            var ios = imp.GetPlatformTextureSettings("iPhone");
            ios.overridden = true;
            ios.maxTextureSize = 2048;
            ios.format = name.EndsWith("_normal") ? TextureImporterFormat.ASTC_5x5 : TextureImporterFormat.ASTC_6x6;
            imp.SetPlatformTextureSettings(ios);
        }
        else if (assetPath.StartsWith("Assets/Sky/"))
        {
            imp.maxTextureSize = 4096;
            imp.mipmapEnabled = false;
            imp.wrapModeU = TextureWrapMode.Repeat;
            imp.wrapModeV = TextureWrapMode.Clamp;
            imp.filterMode = FilterMode.Bilinear;
            var ios = imp.GetPlatformTextureSettings("iPhone");
            ios.overridden = true;
            ios.maxTextureSize = 4096;
            ios.format = TextureImporterFormat.ASTC_HDR_6x6;
            imp.SetPlatformTextureSettings(ios);
        }
    }
}

/// 生成场景用到的公共部分：材质、渲染设置、后期、摆放物体的小工具。
public static partial class SanctuaryBuild
{
    public const string MatDir = "Assets/Materials";
    static readonly Dictionary<string, Material> mats = new Dictionary<string, Material>();

    public static Texture2D Tex(string name)
    {
        foreach (string ext in new[] { ".jpg", ".png" })
        {
            var t = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Textures/{name}{ext}");
            if (t != null) return t;
        }
        return null;
    }

    /// 一种材质。tex 是贴图的名字（Assets/Textures 里的前缀），metersPerTile 是贴图铺一遍有几米。
    public static Material Mat(string name, string tex, float metersPerTile, Color? tint = null, float rough = 1f, float metallic = 0f,
        float wet = 1f, float snow = 1f, float puddle = 0f, float normal = 1f)
    {
        if (mats.TryGetValue(name, out var cached) && cached != null) return cached;
        Directory.CreateDirectory(MatDir);
        string path = $"{MatDir}/{name}.mat";
        var m = AssetDatabase.LoadAssetAtPath<Material>(path);
        var shader = Shader.Find("Yuanjing/Surface");
        if (shader == null) throw new Exception("找不到着色器 Yuanjing/Surface，先跑 tools/unity/gen_shader.py");
        if (m == null)
        {
            m = new Material(shader);
            AssetDatabase.CreateAsset(m, path);
        }
        m.shader = shader;
        var c = tex == null ? null : Tex(tex + "_color");
        if (tex != null && c == null) Debug.LogWarning($"[yuanjing] 材质 {name} 的贴图 {tex} 还没准备好");
        m.SetTexture("_BaseMap", c);
        m.SetTextureScale("_BaseMap", Vector2.one / metersPerTile);
        m.SetColor("_BaseColor", tint ?? Color.white);
        var n = tex == null ? null : Tex(tex + "_normal");
        m.SetTexture("_BumpMap", n);
        m.SetFloat("_BumpScale", normal);
        if (n != null) m.EnableKeyword("_NORMALMAP"); else m.DisableKeyword("_NORMALMAP");
        m.SetTexture("_ArmMap", tex == null ? null : Tex(tex + "_arm"));
        m.SetFloat("_Roughness", rough);
        m.SetFloat("_Metallic", metallic);
        m.SetFloat("_OcclusionStrength", 1f);
        m.SetFloat("_WetAmount", wet);
        m.SetFloat("_SnowAmount", snow);
        m.SetFloat("_Puddle", puddle);
        m.enableInstancing = true;
        EditorUtility.SetDirty(m);
        mats[name] = m;
        return m;
    }

    /// 会发光的材质（灯笼纸、窗格）：亮度由 TimeWeather 按天色调
    public static Material Emissive(string name, Color baseColor, Texture2D map = null)
    {
        var m = Mat(name, null, 1f, baseColor, rough: 0.9f, wet: 0f, snow: 0f);
        m.SetTexture("_BaseMap", map);
        m.SetTextureScale("_BaseMap", Vector2.one);
        m.SetTexture("_EmissionMap", map);
        m.SetColor("_EmissionColor", Color.black);
        m.EnableKeyword("_EMISSION");
        m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
        return m;
    }

    public static GameObject Add(string name, MeshBuilder mb, Material mat, Transform parent, bool shadows = true)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        go.AddComponent<MeshFilter>().sharedMesh = mb.Build(name);
        var r = go.AddComponent<MeshRenderer>();
        r.sharedMaterial = mat;
        r.shadowCastingMode = shadows ? ShadowCastingMode.On : ShadowCastingMode.Off;
        go.isStatic = true;
        return go;
    }

    public static Transform Group(string name, Transform parent = null)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        return go.transform;
    }

    // ───────── 渲染设置 ─────────

    static void SetProp(SerializedObject so, string name, Action<SerializedProperty> set)
    {
        var p = so.FindProperty(name);
        if (p == null) { Debug.LogWarning($"[yuanjing] 渲染设置里没有 {name} 这一项"); return; }
        set(p);
    }

    /// 画质相关的设置：阴影、抗锯齿、高动态范围、环境光遮蔽
    public static void ConfigureRendering()
    {
        var urp = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>("Assets/Settings/URP.asset");
        var so = new SerializedObject(urp);
        SetProp(so, "m_MainLightShadowmapResolution", p => p.intValue = 4096);
        SetProp(so, "m_ShadowDistance", p => p.floatValue = 48f);
        SetProp(so, "m_ShadowCascadeCount", p => p.intValue = 3);
        SetProp(so, "m_SoftShadowsSupported", p => p.boolValue = true);
        SetProp(so, "m_SoftShadowQuality", p => p.intValue = 2);
        SetProp(so, "m_SupportsHDR", p => p.boolValue = true);
        // 多重采样在 iOS 模拟器上和后期一起用会报错，改用镜头上的后期抗锯齿（见 BuildEnvironment）
        // 真机 4 倍多重采样；模拟器不支持和后期一起用，关掉。镜头上另有 SMAA。
        // 不要用时间抗锯齿：它每帧抖动取样，模拟器上静止画面都会一直闪
        bool sim = Array.IndexOf(Environment.GetCommandLineArgs(), "-simulator") >= 0;
        SetProp(so, "m_MSAA", p => p.intValue = sim ? 1 : 4);
        SetProp(so, "m_AdditionalLightsRenderingMode", p => p.intValue = 1);
        SetProp(so, "m_AdditionalLightsPerObjectLimit", p => p.intValue = 8);
        SetProp(so, "m_AdditionalLightShadowsSupported", p => p.boolValue = false);
        // 场景里没有反射探针：混合和盒投影必须关。开着的话着色器会去读第二个探针的贴图和范围，
        // 那是没人设置过的值，手机上读到什么算什么，整个场景的反光就在几种样子之间来回跳
        SetProp(so, "m_ReflectionProbeBlending", p => p.boolValue = false);
        SetProp(so, "m_ReflectionProbeBoxProjection", p => p.boolValue = false);
        SetProp(so, "m_ColorGradingMode", p => p.intValue = 1);
        SetProp(so, "m_RequireDepthTexture", p => p.boolValue = true);
        so.ApplyModifiedPropertiesWithoutUndo();
        urp.shadowDepthBias = 0.6f;
        urp.shadowNormalBias = 0.5f;
        EditorUtility.SetDirty(urp);

        // 环境光遮蔽：让屋檐下、柱脚、缝隙里自然地暗下去。这个功能的类不公开，用名字找。
        var data = AssetDatabase.LoadAssetAtPath<UniversalRendererData>("Assets/Settings/Renderer.asset");
        // 渲染路径：普通 Forward（0）
        var dso = new SerializedObject(data);
        SetProp(dso, "m_RenderingMode", p => p.intValue = 0);
        dso.ApplyModifiedPropertiesWithoutUndo();
        EditorUtility.SetDirty(data);
        var ssaoType = typeof(UniversalRendererData).Assembly.GetType("UnityEngine.Rendering.Universal.ScreenSpaceAmbientOcclusion");
        if (ssaoType != null)
        {
            var feature = data.rendererFeatures.Find(f => f != null && f.GetType() == ssaoType);
            if (feature == null)
            {
                feature = (ScriptableRendererFeature)ScriptableObject.CreateInstance(ssaoType);
                feature.name = "SSAO";
                AssetDatabase.AddObjectToAsset(feature, data);
                data.rendererFeatures.Add(feature);
            }
            var fso = new SerializedObject(feature);
            SetProp(fso, "m_Settings.Intensity", p => p.floatValue = 1.0f);
            SetProp(fso, "m_Settings.Radius", p => p.floatValue = 0.55f);
            SetProp(fso, "m_Settings.Falloff", p => p.floatValue = 60f);
            SetProp(fso, "m_Settings.DirectLightingStrength", p => p.floatValue = 0.3f);
            // 半分辨率算（手机屏幕原尺寸 1170×2532 下和全分辨率比，平均每像素差不到 1/255，脚下、垫子边的接触暗影一样；这一遍的像素只剩四分之一）
            SetProp(fso, "m_Settings.Downsample", p => p.boolValue = true);
            // 噪声用固定图案（1）。默认的蓝噪声（0）每帧换一张，暗角里会一直有细碎的闪
            SetProp(fso, "m_Settings.AOMethod", p => p.intValue = 1);
            fso.ApplyModifiedPropertiesWithoutUndo();
            typeof(ScriptableRendererData).GetMethod("ValidateRendererFeatures", BindingFlags.Instance | BindingFlags.NonPublic)?.Invoke(data, null);
            EditorUtility.SetDirty(data);
        }
        AssetDatabase.SaveAssets();
    }

    /// 后期：辉光、电影式的色调映射、调色、暗角
    public static VolumeProfile PostProfile()
    {
        const string path = "Assets/Settings/Post.asset";
        var profile = AssetDatabase.LoadAssetAtPath<VolumeProfile>(path);
        if (profile != null) return profile;
        profile = ScriptableObject.CreateInstance<VolumeProfile>();
        AssetDatabase.CreateAsset(profile, path);
        var bloom = profile.Add<Bloom>(true);
        bloom.threshold.value = 1.05f;
        bloom.intensity.value = 0.55f;
        bloom.scatter.value = 0.72f;
        bloom.highQualityFiltering.value = true;
        var tone = profile.Add<Tonemapping>(true);
        tone.mode.value = TonemappingMode.ACES;
        var ca = profile.Add<ColorAdjustments>(true);
        ca.postExposure.value = 0f;
        ca.contrast.value = 5f;
        ca.saturation.value = 6f;
        var wb = profile.Add<WhiteBalance>(true);
        wb.temperature.value = 0f;
        var vig = profile.Add<Vignette>(true);
        vig.intensity.value = 0.26f;
        vig.smoothness.value = 0.5f;
        foreach (var c in profile.components) AssetDatabase.AddObjectToAsset(c, profile);
        EditorUtility.SetDirty(profile);
        AssetDatabase.SaveAssets();
        return profile;
    }

    // ───────── 天空 ─────────

    /// 在全景天空图上找太阳（最亮的那一块），返回它的贴图坐标
    public static Vector2 FindSun(Texture2D tex) => FindSun(tex, out _);

    /// mean：上半个天空的平均亮度（去掉太阳附近特别亮的部分），用来把不同来源的天空图校到同一个曝光
    public static Vector2 FindSun(Texture2D tex, out float mean)
    {
        const int W = 512, H = 256;
        var rt = RenderTexture.GetTemporary(W, H, 0, RenderTextureFormat.ARGBFloat, RenderTextureReadWrite.Linear);
        Graphics.Blit(tex, rt);
        var prev = RenderTexture.active;
        RenderTexture.active = rt;
        var read = new Texture2D(W, H, TextureFormat.RGBAFloat, false, true);
        read.ReadPixels(new Rect(0, 0, W, H), 0, 0);
        read.Apply();
        RenderTexture.active = prev;
        RenderTexture.ReleaseTemporary(rt);
        var px = read.GetPixels();
        float best = -1;
        int bx = W / 2, by = H * 3 / 4;
        for (int y = H / 2 + 4; y < H; y++)
            for (int x = 0; x < W; x++)
            {
                // 取周围一小块的和，避开云的亮边
                float s = 0;
                for (int dy = -1; dy <= 1; dy++)
                    for (int dx = -1; dx <= 1; dx++)
                    {
                        var c = px[Mathf.Clamp(y + dy, 0, H - 1) * W + (x + dx + W) % W];
                        s += c.r + c.g + c.b;
                    }
                if (s > best) { best = s; bx = x; by = y; }
            }
        double sum = 0;
        int count = 0;
        for (int y = H / 2 + 8; y < H; y++)
            for (int x = 0; x < W; x++)
            {
                var c = px[y * W + x];
                float l = 0.2126f * c.r + 0.7152f * c.g + 0.0722f * c.b;
                sum += Mathf.Min(l, 4f);
                count++;
            }
        mean = (float)(sum / count);
        UnityEngine.Object.DestroyImmediate(read);
        return new Vector2((bx + 0.5f) / W, (by + 0.5f) / H);
    }

    static Texture2D Sky(string name) => AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Sky/sky_{name}.hdr");

    /// 四个时段的光照设定。颜色和强度是对着预览图一点点调出来的。
    public static TimePreset[] TimePresets()
    {
        TimePreset P(string name, string sky, float az, float elev, float skyExp, Color sunCol, float sunInt, Color aSky, Color aEq, Color aGr, Color fog, float fogD, float postExp, float temp, float lamps)
        {
            var tex = Sky(sky);
            float mean = 1f;
            var uv = tex != null ? FindSun(tex, out mean) : new Vector2(0.5f, 0.6f);
            // skyExp 在这里的意思是「希望天空平均有多亮」，除以图本身的平均亮度得到曝光倍数
            Debug.Log($"[yuanjing] 天空 {name}：平均亮度 {mean:F3}，太阳在 {uv}，曝光 ×{skyExp / Mathf.Max(mean, 0.0001f):F2}");
            skyExp /= Mathf.Max(mean, 0.0001f);
            return new TimePreset
            {
                name = name, sky = tex, sunUV = uv, sunAzimuth = az, sunElevation = elev, skyExposure = skyExp,
                sunColor = sunCol, sunIntensity = sunInt, ambientSky = aSky, ambientEquator = aEq, ambientGround = aGr, fogColor = fog, fogDensity = fogD,
                postExposure = postExp, temperature = temp, lamps = lamps,
            };
        }
        return new[]
        {
            P("dawn", "dawn", -15f, -1f, 0.42f, new Color(1f, 0.66f, 0.42f), 2.6f, new Color(0.62f, 0.62f, 0.86f), new Color(0.78f, 0.60f, 0.52f), new Color(0.36f, 0.30f, 0.28f), new Color(0.86f, 0.62f, 0.50f), 0.010f, 0f, 8f, 0.45f),
            P("day", "day", -148f, 52f, 1.5f, new Color(1f, 0.96f, 0.90f), 3.0f, new Color(0.85f, 1.00f, 1.30f), new Color(0.90f, 0.92f, 0.95f), new Color(0.55f, 0.50f, 0.44f), new Color(0.72f, 0.81f, 0.92f), 0.0055f, 0.25f, 0f, 0f),
            P("dusk", "dusk", 13f, -1f, 0.42f, new Color(1f, 0.52f, 0.26f), 2.6f, new Color(0.56f, 0.52f, 0.80f), new Color(0.84f, 0.56f, 0.46f), new Color(0.34f, 0.26f, 0.24f), new Color(0.90f, 0.56f, 0.40f), 0.009f, 0f, 10f, 0.7f),
            P("night", "night", -38f, 48f, 0.045f, new Color(0.56f, 0.66f, 1f), 0.5f, new Color(0.07f, 0.095f, 0.19f), new Color(0.055f, 0.07f, 0.12f), new Color(0.03f, 0.035f, 0.05f), new Color(0.03f, 0.045f, 0.09f), 0.011f, 0.4f, -6f, 1f),
        };
    }

    // ───────── 屋檐遮挡的高度图 ─────────

    /// 从正上方往下打一遍射线，记下每个位置最高的遮挡有多高。着色器和雨雪用它判断「这里头顶有没有屋檐」。
    public static Texture2D BakeHeightMap(Transform root, string sceneName, float halfSize, out Vector4 parameters)
    {
        const int N = 512;
        var added = new List<MeshCollider>();
        foreach (var mf in root.GetComponentsInChildren<MeshFilter>())
        {
            if (mf.GetComponent<Collider>() != null || mf.sharedMesh == null) continue;
            // 树叶、布条这些会漏雨的不算遮挡
            if (mf.gameObject.name.StartsWith("Leaves") || mf.gameObject.name.StartsWith("Ribbon")) continue;
            var c = mf.gameObject.AddComponent<MeshCollider>();
            c.sharedMesh = mf.sharedMesh;
            added.Add(c);
        }
        Physics.SyncTransforms();
        var tex = new Texture2D(N, N, TextureFormat.RHalf, false, true) { wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear, name = sceneName + "_height" };
        var px = new Color[N * N];
        for (int y = 0; y < N; y++)
            for (int x = 0; x < N; x++)
            {
                var p = new Vector3(-halfSize + (x + 0.5f) / N * halfSize * 2f, 200f, -halfSize + (y + 0.5f) / N * halfSize * 2f);
                px[y * N + x] = new Color(Physics.Raycast(p, Vector3.down, out var hit, 400f) ? hit.point.y : -50f, 0, 0, 1);
            }
        tex.SetPixels(px);
        tex.Apply(false, false);
        foreach (var c in added) UnityEngine.Object.DestroyImmediate(c);
        string path = $"Assets/Settings/{sceneName}_height.asset";
        AssetDatabase.DeleteAsset(path);
        AssetDatabase.CreateAsset(tex, path);
        parameters = new Vector4(-halfSize, -halfSize, 1f / (halfSize * 2f), 1f / (halfSize * 2f));
        return tex;
    }

    // ───────── 预览图 ─────────

    /// 不开模拟器、直接让编辑器渲染几张图出来看效果。命令行：
    ///   -executeMethod SanctuaryBuild.Preview -scene Temple -shots "名字|相机位置|看向哪里|时段|天气|视角;..."
    /// 位置写成 x,y,z；时段 dawn day dusk night；天气 clear rain storm snow。图存在 unity/shots/。
    public static void Preview()
    {
        // -quality：按哪一档画质出图（手机默认用的那档要单独看）
        if (Arg("-quality") != null) QualitySettings.SetQualityLevel(int.Parse(Arg("-quality")), true);
        string scene = Arg("-scene") ?? "Temple";
        EditorSceneManager.OpenScene($"Assets/Scenes/{scene}.unity");
        RenderShots();
    }

    /// 按 -shots 在当前打开的场景里出图。-off 可以临时关掉几样效果做对比：ssao shadows bloom normal smaa；-msaa 1 模拟模拟器
    public static void RenderShots()
    {
        string off = Arg("-off") ?? "";
        var urp = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>("Assets/Settings/URP.asset");
        var rdata = AssetDatabase.LoadAssetAtPath<UniversalRendererData>("Assets/Settings/Renderer.asset");
        int msaaWas = urp.msaaSampleCount;
        var ssao = rdata.rendererFeatures.Find(f => f != null && f.name == "SSAO");
        bool ssaoWas = ssao != null && ssao.isActive;
        Bloom bloom = null;
        PostProfile().TryGet(out bloom);
        bool bloomWas = bloom != null && bloom.active;
        var bumps = new List<(Material, float)>();
        try
        {
            if (Arg("-msaa") != null) urp.msaaSampleCount = int.Parse(Arg("-msaa"));
            if (off.Contains("ssao") && ssao != null) ssao.SetActive(false);
            if (off.Contains("bloom") && bloom != null) bloom.active = false;
            if (off.Contains("normal"))
                foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None))
                    foreach (var m in r.sharedMaterials)
                        if (m != null && m.HasProperty("_BumpScale") && !bumps.Exists(b => b.Item1 == m)) { bumps.Add((m, m.GetFloat("_BumpScale"))); m.SetFloat("_BumpScale", 0); }
            if (off.Contains("smaa")) Camera.main.GetComponent<UniversalAdditionalCameraData>().antialiasing = AntialiasingMode.None;
            RenderShotsInner(off.Contains("shadows"));
        }
        finally
        {
            urp.msaaSampleCount = msaaWas;
            if (ssao != null) ssao.SetActive(ssaoWas);
            if (bloom != null) bloom.active = bloomWas;
            foreach (var (m, v) in bumps) m.SetFloat("_BumpScale", v);
        }
    }

    static void RenderShotsInner(bool noShadows)
    {
        var tw = UnityEngine.Object.FindFirstObjectByType<TimeWeather>();
        var cam = Camera.main;
        Directory.CreateDirectory("../shots");
        int w = int.Parse(Arg("-width") ?? "804"), h = int.Parse(Arg("-height") ?? "1748");
        // 预览时摆上几位香客（运行时才会出现的人，这里手动摆）
        // 带骨骼动作的小动物：出图时摆成待机动作里的一帧（不跑游戏的话它们是僵直的）
        foreach (var cr in UnityEngine.Object.FindObjectsByType<Yuanjing.Critter>(FindObjectsSortMode.None))
        {
            if (cr.rig == null) continue;
            // 名字牌、食盆、礼物平时是运行时才收起来的，出图时先藏好
            if (cr.nameTag != null) cr.nameTag.gameObject.SetActive(false);
            if (cr.food != null) cr.food.SetActive(false);
            if (cr.giftInMouth != null) cr.giftInMouth.SetActive(false);
            var idle = cr.rig.GetClip("Idle");
            if (idle != null) idle.SampleAnimation(cr.rig.gameObject, 0.6f);
            // -pet "编号,x,y,z,朝向[,动作,时刻]|编号,..."：把几只摆到指定位置
            foreach (string one in (Arg("-pet") ?? "").Split('|'))
            {
                if (one.Length == 0) continue;
                var pp0 = one.Split(',');
                if (cr.id != pp0[0]) continue;
                var pp = System.Linq.Enumerable.ToArray(System.Linq.Enumerable.Skip(pp0, 1));
                cr.transform.SetPositionAndRotation(new Vector3(float.Parse(pp[0]), float.Parse(pp[1]), float.Parse(pp[2])), Quaternion.Euler(0, pp.Length > 3 ? float.Parse(pp[3]) : 0, 0));
                if (pp.Length > 4 && cr.rig.GetClip(pp[4]) != null) cr.rig.GetClip(pp[4]).SampleAnimation(cr.rig.gameObject, pp.Length > 5 ? float.Parse(pp[5]) : 0.3f);
            }
        }
        // -player "x,y,z,朝向,姿势"：把自己摆到这里出图（不写就留在原地）。姿势：None Gassho Bow Kneel CrossLegged……
        if (Arg("-player") != null)
        {
            var pf = Arg("-player").Split(',');
            var playerGo = GameObject.Find("Player");
            var folk = playerGo != null ? playerGo.GetComponentInChildren<Yuanjing.Folk>() : null;
            if (folk != null)
            {
                playerGo.transform.position = new Vector3(float.Parse(pf[0]), float.Parse(pf[1]), float.Parse(pf[2]));
                folk.transform.localRotation = Quaternion.Euler(0, pf.Length > 3 ? float.Parse(pf[3]) : 0, 0);
                var pose = pf.Length > 4 ? (Yuanjing.Folk.Pose)Enum.Parse(typeof(Yuanjing.Folk.Pose), pf[4], true) : Yuanjing.Folk.Pose.None;
                folk.EditorPose("Move", 0, 0.3f, pose, 0);
            }
        }
        // -near 0.05：近裁剪面（默认是俯视用的 0.5，凑近拍殿里的供桌、佛脸时会切掉近处的东西）
        if (Arg("-near") != null) cam.nearClipPlane = float.Parse(Arg("-near"));
        // -matset "toon_gold:_Gilt=0,toon_paint_buddha_face:_Gilt=0"：出图时临时改几个材质参数做对比，出完改回去。
        // 颜色写成 r/g/b（如 toon_gold:_BaseColor=1/0.9/0.74）
        var matWas = new List<(Material, string, float)>();
        var colWas = new List<(Material, string, Color)>();
        foreach (string one in (Arg("-matset") ?? "").Split(','))
        {
            var kv = one.Split(':', '=');
            if (kv.Length < 3) continue;
            var m = AssetDatabase.LoadAssetAtPath<Material>($"{YjmImporter.MatDir}/{kv[0]}.mat");
            if (m == null || !m.HasProperty(kv[1])) { Debug.LogWarning($"[yuanjing] 没有材质参数 {one}"); continue; }
            if (kv[2].Contains("/"))
            {
                var c = kv[2].Split('/');
                colWas.Add((m, kv[1], m.GetColor(kv[1])));
                m.SetColor(kv[1], new Color(float.Parse(c[0]), float.Parse(c[1]), float.Parse(c[2]), c.Length > 3 ? float.Parse(c[3]) : 1f));
                continue;
            }
            matWas.Add((m, kv[1], m.GetFloat(kv[1])));
            m.SetFloat(kv[1], float.Parse(kv[2]));
        }
        try { RenderShotList(tw, cam, w, h, noShadows); }
        finally
        {
            foreach (var (m, k, v) in matWas) m.SetFloat(k, v);
            foreach (var (m, k, v) in colWas) m.SetColor(k, v);
        }
    }

    static void RenderShotList(TimeWeather tw, Camera cam, int w, int h, bool noShadows)
    {
        foreach (string shot in (Arg("-shots") ?? "").Split(';'))
        {
            var f = shot.Split('|');
            if (f.Length < 5) continue;
            cam.transform.position = Vec(f[1]);
            cam.transform.LookAt(Vec(f[2]));
            cam.fieldOfView = f.Length > 5 ? float.Parse(f[5]) : 60f;
            var time = (DayTime)Enum.Parse(typeof(DayTime), f[3], true);
            var weather = (Weather)Enum.Parse(typeof(Weather), f[4], true);
            tw.ApplyImmediate(time, weather);
            if (noShadows) tw.sun.shadows = LightShadows.None;
            // -cull 1：按镜头位置把殿里的东西开关一下（同运行时的 InteriorCull），看分档会不会被看出来
            foreach (var ic in UnityEngine.Object.FindObjectsByType<Yuanjing.InteriorCull>(FindObjectsSortMode.None))
                if (Arg("-cull") != null) ic.Apply(cam.transform.position); else ic.Set(2);
            foreach (var ps in UnityEngine.Object.FindObjectsByType<ParticleSystem>(FindObjectsSortMode.None))
            {
                var follow = ps.GetComponentInParent<FollowCamera>();
                if (follow != null) follow.Snap(cam.transform);
                ps.Simulate(6f, true, true);
            }
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
            cam.targetTexture = rt;
            cam.Render();
            cam.Render(); // 第二遍：等阴影、遮蔽这些跨帧的效果稳定
            RenderTexture.active = rt;
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            tex.Apply();
            File.WriteAllBytes($"../shots/{f[0]}.png", tex.EncodeToPNG());
            cam.targetTexture = null;
            RenderTexture.active = null;
            UnityEngine.Object.DestroyImmediate(rt);
            UnityEngine.Object.DestroyImmediate(tex);
            Debug.Log($"[yuanjing] 预览图 {f[0]} {tw.LampDebug()}");
        }
    }

    public static string Arg(string name)
    {
        var args = Environment.GetCommandLineArgs();
        int i = Array.IndexOf(args, name);
        return i >= 0 && i + 1 < args.Length ? args[i + 1] : null;
    }

    static Vector3 Vec(string s)
    {
        var p = s.Split(',');
        return new Vector3(float.Parse(p[0]), float.Parse(p[1]), float.Parse(p[2]));
    }
}
