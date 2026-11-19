using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using Yuanjing;

/// 第三座殿「湖心小寺」：俯视的卡通画风。模型是 tools/blender 里的脚本做的（Assets/Toon/Models/*.yjm），
/// 颜色在顶点色里；这里负责摆放、水面、花草，以及和另外两座殿共用的运行时（走动、座位、心意、天气）。
/// 平面布局的数字和 tools/blender/layout.py 是同一份，改一边要同时改另一边。
public static partial class SanctuaryBuild
{
    const string ToonModels = "Assets/Toon/Models";
    static readonly Dictionary<string, Material> toonMats = new Dictionary<string, Material>();

    // ── 布局（同 layout.py）──
    const float WaterY = -0.42f;
    static readonly Vector2 IsleC = new Vector2(0f, 4.5f);
    const float PathW = 1.35f, GateZ = -12.5f, PlazaR = 3.7f, TreeBed = 2.3f, PondR = 3.1f, TerraceH = 0.07f;
    static readonly Vector3 BurnerAt = new Vector3(0, 0, -2f), TreeAt = new Vector3(-8.6f, 0, -3f), PondAt = new Vector3(8.8f, 0, -4.2f);
    // 大殿模型的原点（2026-11-17 加深以后从 15.8 挪到 17.3；台基前沿还在 z 10.9，后沿 23.7）
    static readonly Vector3 HallAt = new Vector3(0, 0, 17.3f), PavilionAt = new Vector3(14.4f, 0, 6.6f), DockAt = new Vector3(0, 0, -15.4f);
    static readonly Rect Terrace = Rect.MinMaxRect(-11.3f, 1.8f, 11.3f, 9.2f);
    const float DockLen = 6.2f, DockPlat = 3.0f;
    // 石台上的蒲团：5 排 × 每边 6 个 = 60 个，z = 2.5 + 排×1.15，|x| = 1.3 + 列×1.25；走道在蒲团前 0.70 米（草垫前沿和下一排之间）
    const int SeatRows = 5, SeatCols = 6;
    const float SeatZ0 = 2.5f, SeatDZ = 1.15f, SeatX0 = 1.3f, SeatDX = 1.25f, SeatLane = 0.70f;
    // 许愿树的绳圈（同 plants.py 的 tree_wish）
    // 新做法（一根根的真草、按花瓣建模的花）铺的范围：整座岛（2026-11-15 样板角验收后铺开）
    static readonly Rect SampleCorner = Rect.MinMaxRect(-20f, -16f, 20f, 28f);
    const int RopePosts = 8;
    // 绳子降到 1.2 米：1.25 米高的人站在绳外，抬手在胸口、肩膀的高度就能系（同 trees.py 的 tree_wish：H = 1.2）
    const float RopeR = 2.95f, RopeH = 1.2f;
    // 新大殿（spec A）：殿里地面高 0.72。HallOpen：大殿能不能走进去（新大殿模型、殿里的东西、墙和天花板的碰撞都在了，开着）。
    // 改成 false：三个门洞拦一道只挡人的隔板（BuildHall），「进殿」不显示，院子里的路线也不进殿
    const float HallFloor = 0.72f;
    const bool HallOpen = true;

    /// 卡通材质。名字就是模型部件的名字（toon、leaf、glow），另外可以自己起名字做变体
    static Material ToonMat(string name, Action<Material> set = null, string shader = "Yuanjing/Toon")
    {
        if (toonMats.TryGetValue(name, out var cached) && cached != null) return cached;
        Directory.CreateDirectory(YjmImporter.MatDir);
        string path = $"{YjmImporter.MatDir}/toon_{name}.mat";
        var m = AssetDatabase.LoadAssetAtPath<Material>(path);
        var sh = Shader.Find(shader);
        if (sh == null) throw new Exception($"找不到着色器 {shader}");
        if (m == null)
        {
            m = new Material(sh);
            AssetDatabase.CreateAsset(m, path);
        }
        m.shader = sh;
        m.enableInstancing = true;
        if (shader == "Yuanjing/Toon")
        {
            // 光照的配比：亮面大约是模型上的颜色本身，暗面是它的六成多、偏蓝紫
            m.SetFloat("_Ambient", 0.5f);
            m.SetFloat("_SunScale", 0.2f);
            m.SetColor("_ShadeColor", new Color(1.02f, 1.0f, 1.14f));
            m.SetFloat("_Legacy", 0f);
            m.SetFloat("_ShadeSoft", 0.14f);
            m.SetTexture("_DetailMap", AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Toon/Textures/toon_grain.png"));
            m.SetFloat("_Detail", 0.13f);
            m.SetFloat("_DetailScale", 0.7f);
        }
        set?.Invoke(m);
        EditorUtility.SetDirty(m);
        toonMats[name] = m;
        return m;
    }

    static void ToonMaterials()
    {
        ToonMat("toon", m => { m.SetFloat("_Cull", 2f); m.SetFloat("_Sway", 1f); });
        ToonMat("leaf", m => { m.SetFloat("_Cull", 0f); m.SetFloat("_Sway", 1f); m.SetFloat("_SnowAmount", 0.5f); m.SetColor("_RimColor", new Color(1, 1, 1, 0.04f)); m.SetFloat("_Detail", 0f); });
        // 地面：颜色来自画好的那张大贴图（tools/blender/ground_tex.py）
        ToonMat("ground", m =>
        {
            m.SetFloat("_Legacy", 1f);
            m.SetFloat("_Sway", 0f);
            m.SetFloat("_Cull", 2f);
            m.SetFloat("_Detail", 0f);
            m.SetTexture("_BaseMap", AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Toon/Textures/islet_ground.png"));
            m.SetColor("_RimColor", new Color(1, 1, 1, 0f));
        });
        // 带真实贴图的表面：树皮、石头、木头……每套贴图的平均色和铺多大在 tex_meta.json 里（tools/textures/prep.py 写的）
        string meta = File.ReadAllText("Assets/Toon/Textures/tex_meta.json");
        foreach (System.Text.RegularExpressions.Match mt in System.Text.RegularExpressions.Regex.Matches(meta,
                     "\"(\\w+)\":\\s*\\{\\s*\"mean\":\\s*\\[\\s*([\\d.]+),\\s*([\\d.]+),\\s*([\\d.]+)\\s*\\],\\s*\"tile\":\\s*([\\d.]+)"))
        {
            string tn = mt.Groups[1].Value;
            float F(int i) => float.Parse(mt.Groups[i].Value, System.Globalization.CultureInfo.InvariantCulture);
            var mean = new Color(F(2), F(3), F(4)).linear;
            float tile = F(5);
            ToonMat(tn, m =>
            {
                m.SetFloat("_Cull", 2f);
                m.SetFloat("_Sway", 0f);
                m.SetFloat("_Detail", 0f);
                m.EnableKeyword("_YJ_TEX");
                m.SetTexture("_TexMap", AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Toon/Textures/m_{tn}_c.png"));
                m.SetTexture("_TexNormalMap", AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Toon/Textures/m_{tn}_n.png"));
                m.SetColor("_TexMean", mean);
                m.SetFloat("_TexTile", tile);
                m.SetFloat("_TexFine", 5f);
                m.SetFloat("_TexFineAmount", 0.55f);
                m.SetFloat("_TexNormal", tn.StartsWith("bark") ? 1.5f : 1.0f);
                m.SetFloat("_TexSpec", tn == "lacquer" ? 0.5f : tn == "slab" || tn == "stone" ? 0.18f : 0.08f);
            });
        }
        // 院子的铺地（islet_paving）：石头的贴图，每块石板错开、翻转（评审：同一块斜的褐色水渍在一百来块石板上一块块重复），水渍淡一半
        ToonMat("paving", m =>
        {
            m.CopyPropertiesFromMaterial(ToonMat("stone"));
            m.EnableKeyword("_YJ_TEX");
            m.SetFloat("_TexHash", 1f);
            m.SetFloat("_TexContrast", 0.5f);
        });
        // 殿里的红柱：朱红漆（地仗上的油饰），不要木纹、节疤；只留很细的断纹和一层顺着柱子的光
        ToonMat("lacquer_col", m =>
        {
            m.CopyPropertiesFromMaterial(ToonMat("lacquer"));
            m.EnableKeyword("_YJ_TEX");
            m.SetFloat("_TexContrast", 0.22f);
            m.SetFloat("_TexNormal", 0.25f);
            m.SetFloat("_TexFineAmount", 0.15f);
            m.SetColor("_BaseColor", new Color(0.86f, 0.8f, 0.8f));
        });
        // 树叶：每个树种一张小枝贴图（tools/textures/leaves.py）
        foreach (string f in Directory.GetFiles("Assets/Toon/Textures", "leaf_*.png"))
        {
            string ln = Path.GetFileNameWithoutExtension(f);
            ToonMat(ln, m =>
            {
                m.SetTexture("_LeafMap", AssetDatabase.LoadAssetAtPath<Texture2D>(f.Replace('\\', '/')));
                m.SetFloat("_Ambient", 0.5f);
                m.SetFloat("_SunScale", 0.2f);
                if (ln == "leaf_blossom")
                {
                    // 花：描边和叶脉用花自己的深色，不发绿；迎光、透光都偏白
                    m.SetColor("_InkColor", new Color(0.72f, 0.5f, 0.6f));
                    m.SetColor("_LitColor", new Color(1.1f, 1.06f, 1.02f));
                    m.SetColor("_TransColor", new Color(1f, 0.86f, 0.9f));
                    m.SetColor("_ShadeColor", new Color(0.86f, 0.8f, 0.96f));
                    m.SetFloat("_LeafVary", 0.2f);
                }
            }, "Yuanjing/Leaf");
        }
        // 灯（窗纸、灯笼、石灯笼的灯室）：透出来的光带上灯罩的颜色（红灯笼透红光，评审：以前夜里是一块奶白的圆片）
        ToonMat("glow", m => { m.SetFloat("_Cull", 2f); m.SetFloat("_WetAmount", 0f); m.SetFloat("_SnowAmount", 0f); m.SetColor("_EmissionColor", Color.black); m.SetFloat("_GlowTint", 1f); });
        // 殿里的烛火、油灯、香头：白天也点着（不跟着天色开关），用自己的材质（模型里部件名还是 glow，摆放时换上这个、改名 flame）
        ToonMat("flame", m =>
        {
            m.SetFloat("_Cull", 2f); m.SetFloat("_Sway", 0f); m.SetFloat("_Detail", 0f);
            m.SetFloat("_WetAmount", 0f); m.SetFloat("_SnowAmount", 0f);
            m.SetColor("_EmissionColor", new Color(1f, 0.62f, 0.26f) * 1.3f);
        });
        // 鎏金（佛像、背光、供桌、宫灯、幡头……，handoff/statues.md §4）：明暗、旧色都烘在顶点色里（殿里照不到太阳，不然只剩一块平的颜料）。
        // 不用 _YJ_TEX：铜的贴图是锈斑，鎏金上会花。_Gilt 是固定方向的假高光和边缘亮光（不受影子影响），金面会随镜头闪一点
        ToonMat("gold", m =>
        {
            m.SetFloat("_Cull", 2f); m.SetFloat("_Sway", 0f); m.SetFloat("_Detail", 0.04f);
            m.SetColor("_ShadeColor", new Color(1.0f, 0.93f, 0.85f));      // 暗面偏暖，不偏蓝紫
            m.SetColor("_RimColor", new Color(1.0f, 0.85f, 0.5f, 0.35f));
            m.SetFloat("_WetAmount", 0f); m.SetFloat("_SnowAmount", 0f);
            // 顶点色的金偏柠檬黄（加上整个画面的饱和度）：染深、偏红一点（绿、蓝压下去），假高光加重，明暗更像金属
            // （第二轮又压了一点：凑近看脸和胸口还是一片平的柠檬黄，见 handoff/p2_fix2.md）
            m.SetColor("_BaseColor", new Color(0.92f, 0.76f, 0.55f));
            m.SetFloat("_Gilt", 0.7f);
        });
        // 佛像、莲座、背光撑子的鎏金（BuildHall 把三尊佛、两块背光上的 gold 部件换成这个）：金面照见「殿」的明暗（_GiltEnv，见 YJToon.shader）——
        // 迎着人、凸起的面亮，侧过去、朝下的深褐金，衣褶一道道分得清；每盏灯照出小亮点，镜头一走跟着滑；金箔一片片略有深浅、略斜（gilt_grain.png）。
        // 颜色不再往橙里压（以前 _BaseColor 压掉绿、蓝，金就成了一片橙色的塑料）：金的颜色、明暗、旧色都在顶点色里（tools/blender/statues.py）
        ToonMat("gilt", m =>
        {
            m.SetFloat("_Cull", 2f); m.SetFloat("_Sway", 0f); m.SetFloat("_Detail", 0f);
            m.SetColor("_ShadeColor", new Color(1.0f, 0.93f, 0.85f));
            m.SetColor("_RimColor", new Color(1.0f, 0.85f, 0.5f, 0.35f));
            m.SetFloat("_WetAmount", 0f); m.SetFloat("_SnowAmount", 0f);
            m.SetColor("_BaseColor", Color.white);
            m.SetFloat("_Gilt", 0.7f);
            m.SetVector("_GiltDir", new Vector4(0.3f, 0.75f, -0.6f, 0f));
            m.SetColor("_GiltColor", new Color(1.0f, 0.88f, 0.6f));
            m.SetFloat("_GiltEnv", 0.85f);
            m.SetVector("_GiltDoor", new Vector4(0f, 0.12f, -1f, 0f));
            m.SetFloat("_GiltFloor", 0.24f);
            m.SetFloat("_GiltDoorK", 1.55f);
            m.SetFloat("_GiltCeil", 0.35f);
            m.SetFloat("_GiltSpec", 1.0f);
            m.SetFloat("_GiltLamp", 0.8f);
            m.SetTexture("_GiltLeaf", AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Toon/Textures/gilt_grain.png"));
            m.SetFloat("_GiltLeafAmt", 0.35f);
            m.SetFloat("_GiltLeafTilt", 0.07f);
            m.SetFloat("_GiltLeafScale", 2f);
        });
        // 供桌上擦得发亮的黄铜（烛台、油灯、功德箱的包角、经案的铜件）：顶点色本来就是亮的铜黄，不用铜的贴图（那是锈斑，凑近看一块一块的），带一点假高光
        ToonMat("brass", m =>
        {
            m.SetFloat("_Cull", 2f); m.SetFloat("_Sway", 0f); m.SetFloat("_Detail", 0.04f);
            m.SetColor("_ShadeColor", new Color(1.0f, 0.93f, 0.85f));
            m.SetColor("_RimColor", new Color(1.0f, 0.88f, 0.6f, 0.3f));
            m.SetFloat("_WetAmount", 0f); m.SetFloat("_SnowAmount", 0f);
            m.SetFloat("_Gilt", 0.45f);
        });
        // 殿里的金砖地（hall.yjm 的 in_floor，BuildHall 换上）：不用石板的贴图（看着像水泥板），每块砖的颜色在顶点色里（buildings.py 的 _JINZHUAN，块块略有不同）。
        // 染深、偏暖，带一层随镜头变的光泽（同鎏金那一项，强度小）：金砖是磨过、泼过油的，斜着看有一层亮
        // 第四轮（评审：一片平的哑光灰褐、夜里几乎全黑）：颜色按世界坐标取一整张画好的地（tools/textures/painted.py 的 floor：
        // 每块砖的深浅、石面的斑、细裂、磨亮的走道、拜垫前踩出来的一片、墙根积的灰），再加一层磨亮的反光（殿里烘的环境图，BuildHall.BakeHallReflection）
        ToonMat("jinzhuan", m =>
        {
            m.SetFloat("_Cull", 2f); m.SetFloat("_Sway", 0f); m.SetFloat("_Detail", 0f);
            m.SetColor("_BaseColor", Color.white);
            m.SetColor("_ShadeColor", new Color(1.0f, 0.95f, 0.9f));
            m.SetColor("_RimColor", new Color(1f, 1f, 1f, 0.0f));
            m.SetFloat("_WetAmount", 0f); m.SetFloat("_SnowAmount", 0f);
            m.SetFloat("_Gilt", 0f);
            m.SetFloat("_Floor", 1f);
            m.SetTexture("_FloorMap", AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Toon/Textures/floor_jinzhuan.png"));
            m.SetTexture("_FloorDetail", AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Toon/Textures/floor_grain.png"));
            m.SetFloat("_FloorTile", 1.7f);
            m.SetVector("_FloorRect", new Vector4(-6.47f, 14.42f, 1f / 12.94f, 1f / 7.56f));
            m.SetFloat("_FloorRefl", 0.55f);
            m.SetFloat("_FloorRough", 0.32f);
            m.SetFloat("_FloorNight", 0.45f);
        });
        // 手绘图案的表面（tools/textures/painted*.py 画的 paint_*.png）：顶点色是白色乘烘好的明暗（AO），乘上贴图。
        // 每张贴图一个材质 toon_paint_<名字>；新加一张贴图、重新生成场景就有它的材质
        foreach (string f in Directory.GetFiles("Assets/Toon/Textures", "paint_*.png"))
        {
            string pn = Path.GetFileNameWithoutExtension(f);
            ToonMat(pn, m =>
            {
                m.SetFloat("_Legacy", 0f);
                m.SetFloat("_Paint", 1f);
                m.SetFloat("_Cull", 2f);
                m.SetTexture("_BaseMap", AssetDatabase.LoadAssetAtPath<Texture2D>(f.Replace('\\', '/')));
                // 幡：顶点色的 a 是摆动幅度（下摆 0.15）；宫灯的绢面夜里跟着灯一起亮（摆放时加进 lampRenderers）
                m.SetFloat("_Sway", pn == "paint_banner" ? 1f : 0f);
                m.SetFloat("_PaintGlow", pn == "paint_lantern" ? 1f : 0f);
                // 殿里的东西不淋雨、不积雪
                m.SetFloat("_WetAmount", 0f); m.SetFloat("_SnowAmount", 0f);
                // 佛像、大殿的彩画不加颗粒（图案本身够细）；供桌桌围、拜垫这些布面加一点
                bool fine = pn == "paint_buddha_face" || pn == "paint_robe_band" || pn == "paint_mandorla" || pn == "paint_beam" || pn == "paint_ceiling" || pn == "paint_wall";
                m.SetFloat("_Detail", fine ? 0f : 0.05f);
                // 佛像开脸是泥金：比袍子淡一点、亮一点的金，也带一点假高光
                // （开脸连着胸口、手：佛像露出来的皮肤都是这一张。也染深一点、假高光加重，脸颊、眉弓、胸口才有起伏，不是一块平的柠檬黄）
                if (pn == "paint_buddha_face")
                {
                    // 泥金的脸、手、胸口：同佛身的鎏金一样照见殿里的明暗（_GiltEnv），但更淡、更亮、更光滑（抛光的脸）：暗处托得高、金箔几乎看不出
                    m.SetFloat("_Gilt", 0.7f);
                    m.SetColor("_BaseColor", new Color(1.0f, 0.97f, 0.88f));       // 夜里（灯下、白平衡偏冷）不发灰：略暖一点
                    m.SetColor("_ShadeColor", new Color(1.0f, 0.95f, 0.88f));
                    m.SetVector("_GiltDir", new Vector4(0.3f, 0.75f, -0.6f, 0f));
                    m.SetColor("_GiltColor", new Color(1.0f, 0.9f, 0.66f));
                    m.SetFloat("_GiltEnv", 0.7f);
                    m.SetVector("_GiltDoor", new Vector4(0f, 0.12f, -1f, 0f));
                    m.SetFloat("_GiltFloor", 0.32f);
                    m.SetFloat("_GiltDoorK", 1.25f);
                    m.SetFloat("_GiltCeil", 0.3f);
                    m.SetFloat("_GiltSpec", 0.8f);
                    m.SetFloat("_GiltLamp", 0.7f);
                    m.SetTexture("_GiltLeaf", AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Toon/Textures/gilt_grain.png"));
                    m.SetFloat("_GiltLeafAmt", 0.12f);
                    m.SetFloat("_GiltLeafTilt", 0.06f);
                    m.SetFloat("_GiltLeafScale", 2f);
                }
                else if (pn == "paint_mandorla")
                {
                    // 背光：火焰、光圈的台阶边、连珠、卷草、宝珠是贴金的（贴图 a 标出来），照佛像的鎏金（toon_gilt）一样照见殿里的明暗；
                    // 石青、石绿的底子是颜料。评审：以前整块是哑光的橙色，和前面金属一样的佛像不是一回事
                    m.SetColor("_BaseColor", Color.white);
                    m.SetFloat("_GiltMask", 1f);
                    m.SetFloat("_Gilt", 0.7f);
                    m.SetColor("_ShadeColor", new Color(1.0f, 0.93f, 0.85f));
                    m.SetVector("_GiltDir", new Vector4(0.3f, 0.75f, -0.6f, 0f));
                    m.SetColor("_GiltColor", new Color(1.0f, 0.88f, 0.6f));
                    m.SetFloat("_GiltEnv", 0.85f);
                    m.SetVector("_GiltDoor", new Vector4(0f, 0.12f, -1f, 0f));
                    m.SetFloat("_GiltFloor", 0.26f);
                    m.SetFloat("_GiltDoorK", 1.5f);
                    m.SetFloat("_GiltCeil", 0.35f);
                    m.SetFloat("_GiltSpec", 1.0f);
                    m.SetFloat("_GiltLamp", 0.8f);
                    m.SetTexture("_GiltLeaf", AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Toon/Textures/gilt_grain.png"));
                    m.SetFloat("_GiltLeafAmt", 0.3f);
                    m.SetFloat("_GiltLeafTilt", 0.07f);
                    m.SetFloat("_GiltLeafScale", 2f);
                }
                else
                {
                    m.SetFloat("_Gilt", 0f);
                    m.SetColor("_BaseColor", Color.white);
                }
            });
        }
        ToonMat("water", m =>
        {
            m.SetColor("_Shallow", new Color(0.42f, 0.92f, 0.84f, 0.50f));
            m.SetColor("_Deep", new Color(0.10f, 0.60f, 0.74f, 0.92f));
            m.SetFloat("_DepthRange", 2.4f);
            m.SetFloat("_FoamWidth", 0.07f);
            m.SetFloat("_Caustic", 0.34f);
            m.SetFloat("_Glint", 0.4f);
        }, "Yuanjing/ToonWater");
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
        // 材质刚建出来时，之前导入的模型上还是空的，重新导入一遍接上
        foreach (string f in Directory.GetFiles(ToonModels, "*.yjm"))
        {
            var go = AssetDatabase.LoadAssetAtPath<GameObject>(f.Replace('\\', '/'));
            if (go == null || go.GetComponentsInChildren<MeshRenderer>().Any(r => r.sharedMaterial == null))
                AssetDatabase.ImportAsset(f.Replace('\\', '/'), ImportAssetOptions.ForceUpdate);
        }
    }

    /// 殿外不动的东西交给大殿的 InteriorCull（outside）：镜头在殿里时只画从殿门看得出去的（看不到的投影子的只投影子）。
    /// 石台、院子里的建筑、树、石头、灯笼、蒲团（Structure 下不动的）和所有花草（Greens），大殿自己和殿里的除外
    static void HallOutsideCull(Transform world)
    {
        var cull = world.GetComponentInChildren<InteriorCull>();
        if (cull == null) return;
        var list = new List<Renderer>();
        foreach (Transform group in world)
        {
            if (group.name != "Structure" && group.name != "Greens") continue;
            foreach (var r in group.GetComponentsInChildren<MeshRenderer>(true))
            {
                if (r.transform.IsChildOf(cull.transform)) continue;
                if (group.name == "Structure" && !r.gameObject.isStatic && r.GetComponentInParent<LODGroup>() == null) continue;
                list.Add(r);
            }
        }
        cull.outside = list.ToArray();
        Debug.Log($"[yuanjing] 殿外按门洞挑的东西：{list.Count} 个渲染器");
    }

    /// 摆一个模型。yaw 是绕竖轴转的角度，scale 是整体缩放
    static GameObject Put(string model, Transform parent, Vector3 at, float yaw = 0, float scale = 1f, string name = null, bool isStatic = true)
    {
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"{ToonModels}/{model}.yjm");
        if (prefab == null) { Debug.LogWarning($"[yuanjing] 没有模型 {model}"); return null; }
        var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab, parent);
        go.name = name ?? model;
        go.transform.SetPositionAndRotation(at, Quaternion.Euler(0, yaw, 0));
        go.transform.localScale = Vector3.one * scale;
        foreach (var t in go.GetComponentsInChildren<Transform>())
        {
            t.gameObject.isStatic = isStatic;
            // 叶片不算遮雨的屋檐（BakeHeightMap 按名字跳过）
            if (t.name == "leaf") t.name = "Leaves";
        }
        return go;
    }

    // ── 地形数据（Blender 导出的 islet_map.bytes）──
    class IsletMap
    {
        public int nx, ny;
        public float x0, z0, step;
        public float[] h, shore, pond;

        public static IsletMap Load()
        {
            using var r = new BinaryReader(File.OpenRead("Assets/Toon/islet_map.bytes"));
            var m = new IsletMap { nx = r.ReadInt32(), ny = r.ReadInt32(), x0 = r.ReadSingle(), z0 = r.ReadSingle(), step = r.ReadSingle() };
            float[] Read() { var a = new float[m.nx * m.ny]; for (int i = 0; i < a.Length; i++) a[i] = r.ReadSingle(); return a; }
            m.h = Read();
            m.shore = Read();
            m.pond = Read();
            return m;
        }

        float Sample(float[] a, float x, float z)
        {
            float fx = Mathf.Clamp((x - x0) / step, 0, nx - 1.001f), fz = Mathf.Clamp((z - z0) / step, 0, ny - 1.001f);
            int ix = (int)fx, iz = (int)fz;
            float tx = fx - ix, tz = fz - iz;
            return Mathf.Lerp(Mathf.Lerp(a[iz * nx + ix], a[iz * nx + ix + 1], tx), Mathf.Lerp(a[(iz + 1) * nx + ix], a[(iz + 1) * nx + ix + 1], tx), tz);
        }

        public float H(float x, float z) => Sample(h, x, z);
        /// 离岸多远：正数在岛上
        public float Shore(float x, float z) => Sample(shore, x, z);
        /// 离池塘边多远：正数在池塘里
        public float Pond(float x, float z) => Sample(pond, x, z);
    }

    static List<Obstacle> isletObs;

    /// 给摆好的东西加一个圆柱形的碰撞，并登记成自动走路时要绕开的
    static GameObject Solid(GameObject go, float radius, float height = 2.4f, float avoid = -1f)
    {
        if (go == null) return null;
        var c = go.AddComponent<CapsuleCollider>();
        float s = go.transform.localScale.x;
        c.radius = radius / s;
        c.height = Mathf.Max(height, radius * 2f) / s;
        c.center = new Vector3(0, c.height * 0.5f, 0);
        if (avoid > 0) isletObs.Add(new Obstacle { center = go.transform.position, radius = avoid });
        return go;
    }

    static void Wall(Transform parent, Vector3 a, Vector3 b, float height = 2f)
    {
        Vector3 d = b - a;
        d.y = 0;
        if (d.sqrMagnitude < 1e-4f) return;
        var go = new GameObject("Bound");
        go.transform.SetParent(parent, false);
        go.transform.SetPositionAndRotation((a + b) * 0.5f + Vector3.up * (height * 0.5f - 0.6f), Quaternion.LookRotation(d));
        var box = go.AddComponent<BoxCollider>();
        box.size = new Vector3(0.3f, height, d.magnitude + 0.3f);
        // 这一层不挡「往地上打的射线」和点画面，只挡人
        go.layer = 2;
    }

    static float Hash(int i, int k) => Mathf.Abs(Mathf.Sin(i * 127.1f + k * 311.7f) * 43758.5453f) % 1f;

    public static void BuildIslet()
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        ConfigureRendering();
        ToonMaterials();
        var map = IsletMap.Load();
        isletObs = new List<Obstacle>();
        var rng = new System.Random(20261115);
        float R(float a, float b) => a + (b - a) * (float)rng.NextDouble();

        var world = Group("World");
        var structure = Group("Structure", world);
        var greens = Group("Greens", world);
        var lampRenderers = new List<Renderer>();
        var lampLights = new List<Light>();

        // ── 地面和铺地 ──
        var ground = Put("islet_ground", structure, Vector3.zero);
        var paving = Put("islet_paving", structure, Vector3.zero);
        foreach (var root in new[] { ground, paving })
            foreach (var mf in root.GetComponentsInChildren<MeshFilter>())
                mf.gameObject.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh;

        // ── 建筑（大殿在下面摆完殿里的拜垫、蒲团以后再摆：BuildHall）──
        var gate = Put("gate", structure, new Vector3(0, 0, GateZ));
        foreach (float sx in new[] { -1f, 1f })
        {
            var post = new GameObject("GatePost");
            post.transform.SetParent(gate.transform, false);
            post.transform.localPosition = new Vector3(sx * 2.15f, 0, 0);
            Solid(post, 0.42f, 3f);
            isletObs.Add(new Obstacle { center = post.transform.position, radius = 0.75f });
        }
        Solid(Put("pavilion", structure, PavilionAt, -90), 2.3f, 3f, 3.0f);
        var dock = Put("dock", structure, DockAt);
        foreach (var mf in dock.GetComponentsInChildren<MeshFilter>())
            // 桥面、桩子都要能踩（部件名是材质名：换了贴图材质以后不叫 toon 了，按「不是叶子、不是发光」来判断）
            if (!mf.name.StartsWith("leaf") && mf.name != "glow") mf.gameObject.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh;
        Put("boat", structure, new Vector3(3.5f, WaterY + 0.02f, DockAt.z - DockLen - 1.4f), 172, 1f, "Boat", false).AddComponent<Bob>();

        // ── 香炉、许愿树、蒲团、石灯笼 ──
        var burner = Put("burner", structure, BurnerAt + Vector3.up * 0.0f);
        // 远了换简化档（BuildHall.MeshLodGroup）：院子正中的香炉花纹在顶点色里，换得很晚（俯视、从殿里看出去都还是原样，再远才换）
        MeshLodGroup(burner, 0.05f, 0.025f);
        Solid(burner, 0.95f, 1.6f, 1.55f);
        Solid(Put("tree_wish", structure, TreeAt, 40), 0.7f, 4f, RopeR + 0.55f);
        var slots = Group("Slots", structure);
        for (int i = 0; i < RopePosts; i++)
        {
            float a0 = Mathf.PI * 2f * (i + 0.5f) / RopePosts + 40f * Mathf.Deg2Rad * -1f;
            float a1 = Mathf.PI * 2f * (i + 1.5f) / RopePosts + 40f * Mathf.Deg2Rad * -1f;
            // 模型绕竖轴转了 40 度：Unity 里顺时针为正，所以角度要减
            Vector3 p0 = TreeAt + new Vector3(Mathf.Cos(a0), 0, Mathf.Sin(a0)) * RopeR;
            Vector3 p1 = TreeAt + new Vector3(Mathf.Cos(a1), 0, Mathf.Sin(a1)) * RopeR;
            var post = new GameObject("RopePost");
            post.transform.SetParent(structure, false);
            post.transform.position = p0;
            // 木桩 1.32 米高、顶上一个红帽（顶 1.44）
            Solid(post, 0.16f, 1.45f);
            // 这一段绳子朝外的方向（垂直于绳子、背对树）：布条木牌的正面朝它，绳结正好套在绳上
            Vector3 chord = p1 - p0;
            chord.y = 0;
            Vector3 outN = Vector3.Cross(Vector3.up, chord).normalized;
            if (Vector3.Dot(outN, (p0 + p1) * 0.5f - TreeAt) < 0) outN = -outN;
            for (int k = 1; k <= 4; k++)
            {
                float t = k / 5f;
                var s = new GameObject($"Slot{slots.childCount}");
                s.transform.SetParent(slots, false);
                s.transform.SetPositionAndRotation(Vector3.Lerp(p0, p1, t) + Vector3.up * (RopeH - 0.2f * 4f * t * (1 - t) - 0.03f), Quaternion.LookRotation(outN));
            }
            // 这一段绳子挡人：胸口高的绳子，摇杆走不进绳圈里（挂布条时人从绳外走过去，不会从里面穿出来）。
            // 一块薄板，在第 2 层：只挡人的碰撞胶囊，不挡镜头、不挡点画面和往地上打的射线
            var block = new GameObject("RopeBlock");
            block.transform.SetParent(structure, false);
            block.transform.SetPositionAndRotation((p0 + p1) * 0.5f + Vector3.up * 0.5f, Quaternion.LookRotation(chord));
            var rb = block.AddComponent<BoxCollider>();
            rb.size = new Vector3(0.08f, 1.3f, chord.magnitude);
            block.layer = 2;
        }

        var seats = Group("Seats", structure);
        int seatN = 0;
        // 五排、每排左右各六个，中间留一条过道：60 个座位。排与排之间留出一条走道（草垫前面），人从走道走到自己的蒲团前
        // 序号：row*12 + col*2 + (东边 1、西边 0)
        for (int row = 0; row < SeatRows; row++)
            for (int col = 0; col < SeatCols; col++)
                foreach (float sx in new[] { -1f, 1f })
                {
                    float z = SeatZ0 + row * SeatDZ, ax = SeatX0 + col * SeatDX;
                    var p = new Vector3(sx * ax, TerraceH, z);
                    // 蒲团朝着大殿摆（方草垫在前，圆蒲团在后）；座位点是圆蒲团正下方的地面（坐的动作以这里为原点，高度是动作里做好的）
                    // 模型略转一点（±3 度）：六十个摆得一丝不差的方阵像棋盘（座位点不动）
                    var cu = Put("cushion", structure, p, (Hash(row * 12 + col * 2 + (sx > 0 ? 1 : 0), 5) - 0.5f) * 6f);
                    // 方草垫 5 厘米厚：走过去脚踩在垫子上，不陷进去（碰撞只要一块薄板）
                    var mat = cu.AddComponent<BoxCollider>();
                    mat.center = new Vector3(0, 0.025f, 0.12f);
                    mat.size = new Vector3(0.8f, 0.05f, 0.8f);
                    var seat = new GameObject($"Seat{seatN++}");
                    seat.transform.SetParent(seats, false);
                    seat.transform.position = p;
                }
        // 殿里静坐的蒲团：子物体的位置是圆蒲团下的地面（殿里地面 0.72）、朝向是坐下以后面朝的方向。
        // 和院子里的用同一套「走近才显示坐下、坐最近的」，序号接在院子的后面（60 起），不报给服务器、香客不坐。
        // 每侧两列（x ±4.55、±5.65）× 四排（z 15.05..17.75）：西边一组面朝东，东边一组面朝西。
        // 方草垫一块薄碰撞（同院子里的蒲团、cushion_hall 模型的方垫：前后 -0.28..+0.52、面高 0.05），在不挡镜头的那一层。BuildHall 把 cushion_hall 模型摆在同样的位置、同样的朝向
        var hallSeats = Group("HallSeats", structure);
        foreach (float sx in new[] { -1f, 1f })
            foreach (float hx in new[] { 4.55f, 5.65f })
                foreach (float hz in new[] { 15.05f, 15.95f, 16.85f, 17.75f })
                {
                    var hs = new GameObject($"HallSeat{hallSeats.childCount}");
                    hs.transform.SetParent(hallSeats, false);
                    hs.transform.SetPositionAndRotation(new Vector3(sx * hx, HallFloor, hz), Quaternion.Euler(0, sx < 0 ? 90f : 270f, 0));
                    var hm = hs.AddComponent<BoxCollider>();
                    hm.center = new Vector3(0, 0.025f, 0.12f);
                    hm.size = new Vector3(0.8f, 0.05f, 0.8f);
                    hs.layer = NoCameraLayer;
                }
        // 殿里的拜垫（kneel_mat，props.md §4 第二轮的摆法）：位置是拜垫中心下面的地面。圆角长方 0.62（左右）× 0.75（前后）、面高 0.124（殿里地面上 0.844）：
        // 一块薄碰撞，人走上去就站在垫子面上，跪拜时膝盖、手、脚尖都在垫子上。中间三块 z 17.8（供桌前留出上香那一条），两边两块 z 18.5。
        // BuildHall 把 kneel_mat 模型摆在同样的位置
        var hallMats = Group("HallMats", structure);
        foreach (var mp in new[] { new Vector3(-1f, HallFloor, 17.8f), new Vector3(0, HallFloor, 17.8f), new Vector3(1f, HallFloor, 17.8f), new Vector3(-3.6f, HallFloor, 18.5f), new Vector3(3.6f, HallFloor, 18.5f) })
        {
            var km = new GameObject($"KneelMat{hallMats.childCount}");
            km.transform.SetParent(hallMats, false);
            km.transform.position = mp;
            var kb = km.AddComponent<BoxCollider>();
            kb.center = new Vector3(0, 0.062f, 0);
            kb.size = new Vector3(0.62f, 0.124f, 0.75f);
            km.layer = NoCameraLayer;
        }
        // 殿里自动走路要绕开的（坐标见 handoff/hall.md §6、props.md §4/§5 最后一轮）：金柱、开着的门扇、磬、木鱼、功德箱、经案、供桌。
        // 金柱按圆（柱身 r 0.24、覆盆柱础 r 0.33，绕开 0.55：柱础加上人的半个身子 0.22，自动走过去脚不会踩进柱础）；别的按东西本身的长方（props.md §5 建议的碰撞盒，和 BuildHall 里挡人的盒子一样），再往外让 0.25（人的半个身子 0.22 加一点空）。
        // 磬、木鱼、经案挪到了静坐区北边那一条（z 18.95）以后，两根金柱之间（z 15.73..17.67）空了：去两边蒲团直接从金柱中间走，不再绕到北边。
        // 要空着的几条（props.md §5）：过道 x ±1.7、供桌前那一条 z 18.18..18.81、两边拜垫的通道、两根金柱之间、静坐区北边敲磬读经站的地方
        const float body = 0.25f;
        foreach (var (c, half, r) in new[]
        {
            (new Vector3(-2.8f, HallFloor, 15.4f), Vector2.zero, 0.55f), (new Vector3(2.8f, HallFloor, 15.4f), Vector2.zero, 0.55f),
            (new Vector3(-2.8f, HallFloor, 18.0f), Vector2.zero, 0.55f), (new Vector3(2.8f, HallFloor, 18.0f), Vector2.zero, 0.55f),
            // 开着的门扇（叠在门两边，z 14.45..14.99）
            (new Vector3(-3.576f, HallFloor, 14.72f), new Vector2(0.11f, 0.27f), body), (new Vector3(-1.705f, HallFloor, 14.72f), new Vector2(0.11f, 0.27f), body),
            (new Vector3(-0.936f, HallFloor, 14.72f), new Vector2(0.11f, 0.27f), body), (new Vector3(0.936f, HallFloor, 14.72f), new Vector2(0.11f, 0.27f), body),
            (new Vector3(1.705f, HallFloor, 14.72f), new Vector2(0.11f, 0.27f), body), (new Vector3(3.576f, HallFloor, 14.72f), new Vector2(0.11f, 0.27f), body),
            // 磬、木鱼在东边静坐区北边、东边供桌旁（面朝南，敲的人站在 z 18.45），功德箱在门里东边、贴着过道（转了 90 度：南北长）
            (new Vector3(5.0f, HallFloor, 18.95f), new Vector2(0.25f, 0.25f), body), (new Vector3(5.8f, HallFloor, 18.95f), new Vector2(0.27f, 0.25f), body),
            (new Vector3(1.45f, HallFloor, 15.5f), new Vector2(0.26f, 0.38f), body),
            // 经案在西边静坐区北边（面朝南，东西长 1.28，读经的人站在 z 18.42）
            (new Vector3(-5.35f, HallFloor, 18.95f), new Vector2(0.64f, 0.26f), body),
            // 中间供桌（桌围前沿 z 18.817）、两边的供桌
            (new Vector3(0, HallFloor, 19.2f), new Vector2(1.22f, 0.4f), body),
            (new Vector3(-3.6f, HallFloor, 19.35f), new Vector2(0.77f, 0.325f), body), (new Vector3(3.6f, HallFloor, 19.35f), new Vector2(0.77f, 0.325f), body),
        })
            isletObs.Add(new Obstacle { center = c, radius = r, half = half });
        // 石台两侧的太平缸（water_vat，BuildHall 摆模型）：缸沿直径 1.16，加石座，绕开 0.9 米。第二排走道外侧那一头正对着它，那一排不从外侧进出
        foreach (float sx in new[] { -1f, 1f })
            isletObs.Add(new Obstacle { center = new Vector3(sx * 9.2f, TerraceH, 5.5f), radius = 0.9f });

        // ── 新大殿：殿、三世佛、殿里的陈设、太平缸、墙和地面的碰撞、殿里的灯（BuildHall.cs）──
        BuildHall(structure, hallSeats, hallMats, lampRenderers);

        // 石灯笼：夜里亮，带一盏小灯（数量有限：一块地面最多同时吃 8 盏灯）
        var lanternSpots = new[]
        {
            new Vector3(-2.2f, 0, -10.2f), new Vector3(2.2f, 0, -10.2f), new Vector3(-2.3f, 0, -6.4f), new Vector3(2.3f, 0, -6.4f),
            new Vector3(-10.4f, 0, 10.0f), new Vector3(10.4f, 0, 10.0f), new Vector3(-5.6f, 0, 0.9f), new Vector3(5.6f, 0, 0.9f),
            new Vector3(-12.4f, 0, 1.0f), new Vector3(13.2f, 0, 0.6f),
        };
        for (int i = 0; i < lanternSpots.Length; i++)
        {
            var p = lanternSpots[i];
            var lantern = Put("lantern", structure, p, R(-8, 8), 1.25f);
            MeshLodGroup(lantern, 0.08f, 0.04f);
            Solid(lantern, 0.38f, 2f, 0.8f);
            if (i < 6) lampLights.Add(PointLamp(structure, p + Vector3.up * 1.9f, 7f, 6.5f));
        }
        // 殿前廊下的两盏（z 11.2）：照廊下、台阶和石台北头。范围 6 米（原来 9 米一直照进殿里，夜里殿里的大块墙面、地面
        // 一个物体吃的灯超过 8 盏的上限）
        lampLights.Add(PointLamp(structure, HallAt + new Vector3(-3.4f, 3.4f, -6.1f), 6f, 5f));
        lampLights.Add(PointLamp(structure, HallAt + new Vector3(3.4f, 3.4f, -6.1f), 6f, 5f));

        // ── 树 ──
        var fallenAt = new List<(string kind, Vector3 at)>();
        void Tree(string model, float x, float z, float scale = 1f, float trunk = 0.3f)
        {
            float y = map.H(x, z);
            Solid(Put(model, structure, new Vector3(x, y - 0.03f, z), R(0, 360), scale * R(0.94f, 1.06f)), trunk, 3f, 0.9f);
            string kind = model.Contains("maple") ? "fallen_maple" : model.Contains("ginkgo") ? "fallen_ginkgo" : model.Contains("blossom") ? "fallen_petal" : model.Contains("round") ? "fallen_green" : null;
            if (kind != null) fallenAt.Add((kind, new Vector3(x, y, z)));
        }
        // 大殿两侧的松（大殿加深以后殿后已经没有能种松的地方，见 handoff/hall.md §7：每个位置按 12 个朝向、缩放上下限都和殿不碰）
        Tree("tree_pine_b", -14.0f, 19.0f, 1.1f);
        Tree("tree_pine_b", -13.6f, 12.5f, 1.1f); Tree("tree_pine_b", 14.2f, 13.4f, 1.1f);
        // 东边这棵松往东挪了 1.2 米、小一点（原来在 (12.5, 16.9)，人走到殿东北角外面时平视镜头整个埋在松针里；新位置照样 24/24 不碰殿，离岸 2.7 米）
        Tree("tree_pine_b", 13.6f, 16.4f, 0.95f); Tree("tree_round_a", -14.6f, 16.6f, 1.2f); Tree("tree_round_a", 15.0f, 17.2f, 1.15f);
        // 西边：红枫、银杏
        Tree("tree_maple_a", -13.4f, 6.6f, 1.15f, 0.25f); Tree("tree_maple_b", -13.0f, 10.6f, 1.1f, 0.2f); Tree("tree_ginkgo", -14.4f, 1.6f, 1.05f); Tree("tree_maple_b", -13.6f, -6.4f, 1.1f, 0.2f);
        Tree("tree_round_b", -12.6f, -10.2f); Tree("tree_maple_a", -10.6f, -12.0f, 0.95f, 0.25f);
        // 东边：池塘旁的花树
        Tree("tree_blossom", 12.6f, -2.6f, 1.2f, 0.25f); Tree("tree_blossom", 10.4f, -8.2f, 1.0f, 0.25f); Tree("tree_ginkgo", 14.6f, 2.8f, 1.1f); Tree("tree_round_b", 13.6f, -9.6f);
        Tree("tree_maple_b", 7.0f, -11.8f, 1.0f, 0.2f); Tree("tree_round_a", 14.8f, 11.6f, 1.1f);
        // 竹林：大殿两边各一丛（离殿的屋檐够远，hall.md §7）
        foreach (var (x, z, m) in new[] { (-11.2f, 13.0f, "bamboo_a"), (-11.5f, 14.4f, "bamboo_a"), (-10.6f, 16.0f, "bamboo_b"), (-12.1f, 15.6f, "bamboo_b"), (11.0f, 13.6f, "bamboo_a"), (11.1f, 15.3f, "bamboo_b") })
            Solid(Put(m, structure, new Vector3(x, map.H(x, z) - 0.02f, z), R(0, 360), R(0.95f, 1.15f)), 0.5f, 3f, 1.0f);
        Solid(Put("stele", structure, new Vector3(-11.6f, 0, 3.6f), 100), 0.6f, 2f, 1.0f);

        // ── 石头：岸边一圈大大小小的，水里几块 ──
        string[] rocks = { "rock_a", "rock_b", "rock_c", "rock_d", "rock_e", "rock_moss", "rock_b", "rock_c" };
        void Rock(string model, float x, float z, float scale, bool solid = true)
        {
            float y = Mathf.Max(map.H(x, z), WaterY - 0.5f);
            var go = Put(model, structure, new Vector3(x, y - 0.05f, z), R(0, 360), scale);
            if (go == null) return;
            if (solid)
                foreach (var mf in go.GetComponentsInChildren<MeshFilter>())
                    mf.gameObject.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh;
        }
        for (int i = 0; i < 44; i++)
        {
            float ang = i / 44f * Mathf.PI * 2f + R(-0.05f, 0.05f);
            Vector2 dir = new Vector2(Mathf.Cos(ang), Mathf.Sin(ang));
            // 码头正面的沙滩留空
            if (dir.y < -0.92f) continue;
            float want = R(-1.2f, 0.9f);
            float rr = 14f;
            for (int k = 0; k < 40; k++)
            {
                Vector2 p = IsleC + dir * rr;
                if (map.Shore(p.x, p.y) < want) break;
                rr += 0.3f;
            }
            Vector2 q = IsleC + dir * rr;
            // 大殿台基（连最外一圈台座：x ±8.75、z 10.75..23.85）四周 1.2 米以内不放：殿后两个角离岸很近，石头会摆到台基、栏杆里
            if (Mathf.Abs(q.x) < 8.75f + 1.2f && q.y > 10.75f - 1.2f && q.y < 23.85f + 1.2f) continue;
            Rock(rocks[rng.Next(rocks.Length)], q.x, q.y, R(0.7f, 1.5f), want > -0.3f);
        }
        foreach (var (x, z, s, m) in new[] { (-21f, -8f, 1.6f, "rock_d"), (21.5f, 3f, 1.5f, "rock_d"), (-19.5f, 16f, 1.3f, "rock_a"), (19f, -14f, 1.2f, "rock_a"), (7f, -21f, 1.1f, "rock_moss"),
                     (-8.5f, -20.5f, 1.2f, "rock_moss"), (-11.2f, 20.2f, 1.5f, "rock_d"), (12.6f, 21.4f, 1.4f, "rock_d"), (-2.4f, 25.6f, 1.2f, "rock_a"), (3.2f, 26.2f, 1.0f, "rock_moss"),
                     (-15.2f, 8.4f, 1.0f, "rock_b"), (15.6f, 6.2f, 1.1f, "rock_b"), (-10.4f, 1.6f, 0.9f, "rock_c"), (11.2f, 1.6f, 0.9f, "rock_moss") })
            Rock(m, x, z, s, map.Shore(x, z) > 0);

        // ── 花草（不算建筑：不参与「屋檐遮雨」的计算，也不加碰撞）──
        bool Open(float x, float z, float pad)
        {
            // 这一点是不是空地：不在路、铺地、石台、建筑上
            if (map.Shore(x, z) < 3.3f || map.Pond(x, z) > -0.7f) return false;
            if (Mathf.Abs(x) < PathW + pad && z > -15.5f && z < Terrace.yMin) return false;
            if (new Vector2(x - BurnerAt.x, z - BurnerAt.z).magnitude < PlazaR + pad) return false;
            if (new Vector2(x - TreeAt.x, z - TreeAt.z).magnitude < RopeR + 0.3f + pad) return false;
            if (x > Terrace.xMin - pad && x < Terrace.xMax + pad && z > Terrace.yMin - pad && z < Terrace.yMax + 1.2f) return false;
            if (Mathf.Abs(x - HallAt.x) < 9.2f + pad && Mathf.Abs(z - HallAt.z) < 6.9f + pad) return false;
            if (new Vector2(x - PavilionAt.x, z - PavilionAt.z).magnitude < 2.9f + pad) return false;
            return true;
        }
        // 样板角（许愿树周围 16 米见方）：这里换成新做法（一根根的真草、按花瓣建模的花），旧的草丛、草尖、小花在这块地里不摆
        bool InSample(float x, float z) => SampleCorner.Contains(new Vector2(x, z));
        string[] grassKinds = { "grass_a", "grass_a", "grass_b", "grass_b", "grass_c" };
        int grassCount = 0;
        for (int i = 0; i < 12000 && grassCount < 2700; i++)
        {
            float x = R(-19f, 19f), z = R(-15f, 27f);
            if (!Open(x, z, 0.1f) || InSample(x, z)) continue;
            // 一丛一丛地长：用噪声决定哪里密
            float n = Mathf.PerlinNoise(x * 0.22f + 31f, z * 0.22f + 7f);
            if (n < 0.32f + 0.3f * (float)rng.NextDouble()) continue;
            Put(grassKinds[rng.Next(grassKinds.Length)], greens, new Vector3(x, map.H(x, z), z), R(0, 360), R(0.9f, 1.6f));
            grassCount++;
        }
        // 细碎的草尖铺满地（很省，一棵十来个三角形），大草丛之间不再是光地
        int sprouts = 0;
        for (int i = 0; i < 20000 && sprouts < 4200; i++)
        {
            float x = R(-19.5f, 19.5f), z = R(-15.5f, 27.5f);
            if (!Open(x, z, 0.04f) || InSample(x, z)) continue;
            Put(rng.Next(2) == 0 ? "sprout_a" : "sprout_b", greens, new Vector3(x, map.H(x, z), z), R(0, 360), R(0.8f, 1.5f));
            sprouts++;
        }
        // 三叶草、小雏菊：一小片一小片
        string[] coverKinds = { "clover", "clover", "daisy_w", "daisy_w", "daisy_y", "daisy_b" };
        int covers = 0;
        for (int c = 0; c < 400 && covers < 520; c++)
        {
            float cx = R(-17.5f, 17.5f), cz = R(-14.5f, 26f);
            if (!Open(cx, cz, 0.3f) || InSample(cx, cz)) continue;
            string kind = coverKinds[rng.Next(coverKinds.Length)];
            int n = rng.Next(2, 6);
            for (int k = 0; k < n; k++)
            {
                float x = cx + R(-0.7f, 0.7f), z = cz + R(-0.7f, 0.7f);
                if (!Open(x, z, 0.1f)) continue;
                Put(kind, greens, new Vector3(x, map.H(x, z), z), R(0, 360), R(0.9f, 1.4f));
                covers++;
            }
        }
        // 样板角的草和花
        int blades = GrassField(greens, map, Open, SampleCorner, 200);
        string[] newFlowers = { "fl_daisy", "fl_daisy", "fl_daisy_pink", "fl_buttercup", "fl_buttercup", "fl_violet", "fl_violet", "fl_clover", "fl_clover", "fl_cosmos", "fl_cosmos_white" };
        int flowers = 0;
        for (int c = 0; c < 2400 && flowers < 520; c++)
        {
            float cx = R(SampleCorner.xMin, SampleCorner.xMax), cz = R(SampleCorner.yMin, SampleCorner.yMax);
            if (!Open(cx, cz, 0.25f)) continue;
            string kind = newFlowers[rng.Next(newFlowers.Length)];
            bool patch = kind == "fl_clover";
            int n = patch ? rng.Next(1, 3) : rng.Next(2, 6);
            for (int k = 0; k < n; k++)
            {
                float x = cx + R(-0.5f, 0.5f), z = cz + R(-0.5f, 0.5f);
                if (!Open(x, z, 0.12f)) continue;
                Put(kind, greens, new Vector3(x, map.H(x, z), z), R(0, 360), R(0.9f, 1.3f), isStatic: false);
                flowers++;
            }
        }
        // 绳圈南边一小片花地：每种花挨着摆一丛，方便蹲下来凑近看
        foreach (var (kind, x, z) in new[] { ("fl_daisy", -9.8f, -7.3f), ("fl_buttercup", -9.2f, -7.55f), ("fl_violet", -8.6f, -7.2f), ("fl_clover", -8.0f, -7.5f),
                     ("fl_cosmos", -7.4f, -7.3f), ("fl_daisy_pink", -9.5f, -6.9f), ("fl_cosmos_white", -7.8f, -6.9f), ("fl_violet", -8.9f, -7.7f) })
        {
            Put(kind, greens, new Vector3(x, map.H(x, z), z), R(0, 360), 1.15f, isStatic: false);
            flowers++;
        }
        Debug.Log($"[yuanjing] 样板角：草 {blades} 根，花 {flowers} 丛，按实例画 {MergeFlowers(greens)} 种");
        // 蕨和带穗的长草：长在外圈、树脚、石头边
        int tall = 0;
        for (int i = 0; i < 1500 && tall < 230; i++)
        {
            float x = R(-18.5f, 18.5f), z = R(-14.5f, 27f);
            float sd0 = map.Shore(x, z);
            if (sd0 < 3.4f || sd0 > 8.5f || !Open(x, z, 0.5f)) continue;
            if (Mathf.Abs(x) < 4f && z < -9f) continue;
            Put(rng.Next(3) == 0 ? "fern" : "grass_seed", greens, new Vector3(x, map.H(x, z), z), R(0, 360), R(0.9f, 1.4f));
            tall++;
        }
        // 树下的落叶、花瓣
        foreach (var (kind, at) in fallenAt)
            for (int k = 0; k < 5; k++)
            {
                float x = at.x + R(-2.2f, 2.2f), z = at.z + R(-2.2f, 2.2f);
                if (map.Shore(x, z) < 1.2f) continue;
                Put(kind, greens, new Vector3(x, Mathf.Max(map.H(x, z), 0f) + 0.07f, z), R(0, 360), R(0.9f, 1.5f));
            }
        // 许愿树下也落着叶子；石台和路上零星几片
        for (int k = 0; k < 14; k++)
            Put("fallen_green", greens, new Vector3(TreeAt.x + R(-4.5f, 4.5f), 0.08f, TreeAt.z + R(-4.5f, 4.5f)), R(0, 360), R(1f, 1.6f));
        foreach (var (x, z, kind) in new[] { (-3.2f, 4.4f, "fallen_ginkgo"), (4.4f, 7.8f, "fallen_maple"), (-5.6f, 8.2f, "fallen_maple"), (1.2f, 3.6f, "fallen_green"), (6.2f, 4.2f, "fallen_petal"),
                     (0.6f, -9.6f, "fallen_maple"), (-0.8f, -6.2f, "fallen_petal"), (0.4f, -12.2f, "fallen_ginkgo") })
            Put(kind, greens, new Vector3(x, (z > 3f ? TerraceH : 0.06f) + 0.012f, z), R(0, 360), 1.2f);
        // 蘑菇：树脚边几簇
        foreach (var (x, z) in new[] { (-9.6f, -5.6f), (-12.8f, 7.4f), (12.2f, -3.4f), (14.0f, 3.6f), (-11.8f, -9.6f), (9.4f, 13.6f), (-9.0f, 12.6f), (13.0f, -8.8f) })
            Put("mushrooms", greens, new Vector3(x, map.H(x, z), z), R(0, 360), R(1.2f, 1.8f));
        // 漂在水面上的花瓣和落叶
        for (int i = 0, n = 0; i < 400 && n < 26; i++)
        {
            float x = R(-23f, 23f), z = R(-20f, 29f);
            float sd0 = map.Shore(x, z);
            if (sd0 < -4.5f || sd0 > -0.5f) continue;
            Put(rng.Next(2) == 0 ? "fallen_petal" : "fallen_maple", greens, new Vector3(x, WaterY + 0.004f, z), R(0, 360), R(1.0f, 1.6f));
            n++;
        }
        Debug.Log($"[yuanjing] 细节：草尖 {sprouts} 三叶草雏菊 {covers} 蕨和长草 {tall}");

        // ── 有人气的小东西 ──
        Solid(Put("basin", structure, new Vector3(4.0f, 0, -10.4f), 200), 0.6f, 1f, 0.95f);
        Solid(Put("bench", structure, new Vector3(5.6f, 0, -0.9f), 68), 0.5f, 0.6f, 0.9f);
        Solid(Put("bench", structure, new Vector3(-5.2f, 0, -8.6f), -20), 0.5f, 0.6f, 0.9f);
        Solid(Put("plaque_rack", structure, new Vector3(-12.0f, 0, -4.4f), 72), 0.9f, 1.8f, 1.3f);
        Solid(Put("signpost", structure, new Vector3(2.6f, 0, -13.9f), 20), 0.25f, 1.5f, 0.6f);
        var broom = Put("broom", structure, new Vector3(9.9f, 0.3f, 5.2f), 30);
        if (broom != null) broom.transform.rotation = Quaternion.Euler(-14, 30, 6);

        string[] flowerKinds = { "flower_w", "flower_y", "flower_p", "flower_v" };
        int flowerCount = 0;
        for (int c = 0; c < 70; c++)
        {
            float cx = R(-17f, 17f), cz = R(-14f, 25f);
            if (!Open(cx, cz, 0.6f) || InSample(cx, cz)) continue;     // 新做法的花铺到的地方，旧花不摆
            string kind = flowerKinds[rng.Next(flowerKinds.Length)];
            int n = rng.Next(4, 9);
            for (int k = 0; k < n; k++)
            {
                float x = cx + R(-0.9f, 0.9f), z = cz + R(-0.9f, 0.9f);
                if (!Open(x, z, 0.2f)) continue;
                Put(kind, greens, new Vector3(x, map.H(x, z), z), R(0, 360), R(1.1f, 1.7f));
                flowerCount++;
            }
        }
        string[] bushKinds = { "bush_a", "bush_b", "bush_c", "bush_flower_p", "bush_flower_w", "bush_a", "bush_b" };
        int bushCount = 0;
        for (int i = 0; i < 400 && bushCount < 46; i++)
        {
            float x = R(-18f, 18f), z = R(-14f, 26f);
            float sd = map.Shore(x, z);
            // 灌木长在岛的外圈，中间留给人走
            if (sd < 3.6f || sd > 7.5f || !Open(x, z, 1.0f)) continue;
            if (Mathf.Abs(x) < 4.5f && z < -9f) continue;
            Put(bushKinds[rng.Next(bushKinds.Length)], greens, new Vector3(x, map.H(x, z) - 0.02f, z), R(0, 360), R(0.9f, 1.4f));
            bushCount++;
        }
        foreach (var (x, z) in new[] { (-8.6f, 9.6f), (8.6f, 9.8f), (-9.4f, 11.0f), (9.4f, 11.2f), (-3.2f, -12.8f), (3.4f, -13.0f), (-5.0f, 0.6f), (5.2f, 2.0f) })
            Put(bushKinds[rng.Next(bushKinds.Length)], greens, new Vector3(x, map.H(x, z) - 0.02f, z), R(0, 360), R(0.9f, 1.2f));
        // 芦苇：长在岸边的浅水里
        int reedCount = 0;
        for (int i = 0; i < 600 && reedCount < 34; i++)
        {
            float x = R(-24f, 24f), z = R(-20f, 30f);
            float sd = map.Shore(x, z);
            if (sd < -0.9f || sd > 0.5f) continue;
            if (Mathf.Abs(x) < 6f && z < -12f) continue;
            Put("reeds", greens, new Vector3(x, WaterY, z), R(0, 360), R(0.9f, 1.3f));
            reedCount++;
        }
        // 荷花：池塘里几丛，湖边浅水里几丛
        string[] lotusKinds = { "lotus_a", "lotus_b", "lotus_c" };
        foreach (var (dx, dz) in new[] { (-1.1f, 0.6f), (1.2f, -0.5f), (0.2f, 1.3f), (-0.3f, -1.2f) })
            Put(lotusKinds[rng.Next(3)], greens, PondAt + new Vector3(dx, WaterY + 0.012f, dz), R(0, 360), R(0.8f, 1.0f));
        int lotusCount = 0;
        for (int i = 0; i < 500 && lotusCount < 16; i++)
        {
            float x = R(-25f, 25f), z = R(-21f, 30f);
            float sd = map.Shore(x, z);
            if (sd < -3.2f || sd > -1.0f) continue;
            if (Mathf.Abs(x) < 7f && z < -12f) continue;
            Put(lotusKinds[rng.Next(3)], greens, new Vector3(x, WaterY + 0.012f, z), R(0, 360), R(0.9f, 1.3f));
            lotusCount++;
        }
        // 沙滩和路边的小东西：卵石、贝壳
        int bits = 0;
        for (int i = 0; i < 900 && bits < 46; i++)
        {
            float x = R(-21f, 21f), z = R(-19f, 28f);
            float sd = map.Shore(x, z);
            if (sd < 0.5f || sd > 3.0f) continue;
            if (Mathf.Abs(x) < 1.8f && z < -13f) continue;
            Put(rng.Next(3) == 0 ? "shells" : "pebbles", greens, new Vector3(x, map.H(x, z) + 0.005f, z), R(0, 360), R(0.9f, 1.5f));
            bits++;
        }
        for (int i = 0; i < 26; i++)
        {
            float z = R(-11f, 2f), side = rng.Next(2) == 0 ? -1f : 1f;
            float x = side * (PathW + R(0.25f, 0.7f));
            if (new Vector2(x - BurnerAt.x, z - BurnerAt.z).magnitude < PlazaR + 0.4f) continue;
            Put("pebbles", greens, new Vector3(x, 0.005f, z), R(0, 360), R(0.7f, 1.1f));
        }
        Debug.Log($"[yuanjing] 花草：草 {grassCount} 花 {flowerCount} 灌木 {bushCount} 芦苇 {reedCount} 荷花 {lotusCount + 4}");
        // 贴在地上的小东西（落叶、花瓣、卵石、贝壳、带穗的矮草）不投太阳的影子：几百件，影子只有几厘米、又碎（样板角的花合成块的时候已经关了），
        // 太阳那一遍每层级联都要一件一件画（俯视时七八百次），贴地的接触暗影 SSAO 已经有了。蕨、芦苇、灌木、树照旧投
        int flat = 0;
        foreach (Transform t in greens)
            if (t.name.StartsWith("fallen_") || t.name == "pebbles" || t.name == "shells" || t.name == "grass_seed")
                foreach (var r in t.GetComponentsInChildren<MeshRenderer>())
                {
                    r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                    flat++;
                }
        Debug.Log($"[yuanjing] 贴地的小东西不投影子：{flat} 件");

        // ── 水面和锦鲤 ──
        BuildToonWater(world);
        var fish = Group("Koi", world);
        string[] koi = { "koi_a", "koi_b", "koi_c", "koi_d" };
        void Fish(Vector3 center, Vector2 radius, int n, float scale)
        {
            for (int i = 0; i < n; i++)
            {
                var go = Put(koi[rng.Next(koi.Length)], fish, center, 0, scale * R(0.85f, 1.2f), "Koi", false);
                if (go == null) continue;
                foreach (var mr in go.GetComponentsInChildren<MeshRenderer>()) mr.shadowCastingMode = ShadowCastingMode.Off;
                var k = go.AddComponent<Koi>();
                k.center = center + new Vector3(R(-0.3f, 0.3f), R(-0.06f, 0.04f), R(-0.3f, 0.3f));
                k.radius = radius * R(0.7f, 1f);
                k.speed = R(0.16f, 0.3f) * (rng.Next(2) == 0 ? 1 : -1);
                k.phase = R(0, 20f);
            }
        }
        Fish(PondAt + Vector3.up * (WaterY - 0.22f), new Vector2(1.9f, 1.6f), 6, 1.5f);
        Fish(new Vector3(-3.8f, WaterY - 0.3f, DockAt.z - 6.5f), new Vector2(2.4f, 3.2f), 5, 1.7f);
        Fish(new Vector3(4.6f, WaterY - 0.3f, DockAt.z - 4.5f), new Vector2(2.0f, 2.6f), 4, 1.6f);

        // 一群群小鱼：在岸边浅水里
        for (int i = 0, n = 0; i < 300 && n < 4; i++)
        {
            float x = R(-22f, 22f), z = R(-19f, 28f);
            float sd1 = map.Shore(x, z);
            if (sd1 < -3.0f || sd1 > -1.4f || (Mathf.Abs(x) < 5f && z < -12f)) continue;
            n++;
            for (int k = 0; k < 9; k++)
            {
                var go = Put("minnow", fish, new Vector3(x, WaterY - 0.2f, z), 0, R(1.3f, 1.9f), "Minnow", false);
                if (go == null) continue;
                foreach (var mr in go.GetComponentsInChildren<MeshRenderer>()) mr.shadowCastingMode = ShadowCastingMode.Off;
                var kk = go.AddComponent<Koi>();
                kk.center = new Vector3(x + R(-0.4f, 0.4f), WaterY - R(0.12f, 0.3f), z + R(-0.4f, 0.4f));
                kk.radius = new Vector2(R(0.9f, 1.5f), R(0.7f, 1.2f));
                kk.speed = R(0.45f, 0.8f) * (k % 2 == 0 ? 1 : -1);
                kk.phase = R(0, 20f);
            }
        }

        // ── 小动物：六只有名字的（会记住你），加上小鸟和白鹭 ──
        var critters = Group("Critters", world);
        var font = NameFont();
        Critter Pet(string model, string id, string name, bool cat, Vector3 home, float radius, float scale, string gift)
        {
            // 有带骨骼动作、套了毛的版本就用它（现在只有柴犬），没有就用 Blender 脚本做的分件模型
            var furPrefab = AssetDatabase.LoadAssetAtPath<GameObject>($"{CritterDir}/{id}/Pet_{id}.prefab");
            GameObject go;
            if (furPrefab != null)
            {
                go = (GameObject)PrefabUtility.InstantiatePrefab(furPrefab, critters);
                go.transform.SetPositionAndRotation(new Vector3(home.x, map.H(home.x, home.z), home.z), Quaternion.Euler(0, R(0, 360), 0));
                scale = 1f;
            }
            else go = Put(model, critters, new Vector3(home.x, map.H(home.x, home.z), home.z), R(0, 360), scale, "Pet_" + id, false);
            if (go == null) return null;
            var c = go.AddComponent<Critter>();
            c.rig = go.GetComponentInChildren<Animation>();
            c.id = id;
            c.displayName = name;
            c.cat = cat;
            c.home = go.transform.position;
            c.homeRadius = radius;
            c.speed = cat ? 0.8f : 1.05f;
            c.giftInMouth = Put(gift, go.transform, go.transform.position, 0, 1f, "Gift", false);
            c.giftInMouth.transform.localScale = Vector3.one;
            c.food = Put("food_bowl", go.transform, go.transform.position, 0, 1f, "Food", false);
            c.food.transform.localScale = Vector3.one;
            if (c.rig != null)
            {
                // 礼物叼在嘴里：挂到头的骨头上，跟着头动
                var headBone = go.GetComponentsInChildren<Transform>().FirstOrDefault(t => t.name == "Head");
                if (headBone != null)
                {
                    c.giftInMouth.transform.SetParent(headBone, true);
                    c.giftInMouth.transform.position = headBone.position + go.transform.forward * 0.16f - Vector3.up * 0.04f;
                    c.giftInMouth.transform.rotation = go.transform.rotation * Quaternion.Euler(0, 90, 0);
                }
            }
            var tagGo = new GameObject("Name");
            tagGo.transform.SetParent(go.transform, false);
            var tag = tagGo.AddComponent<TextMesh>();
            tag.font = font;
            tag.fontSize = 64;
            tag.characterSize = 0.036f / scale;
            tag.anchor = TextAnchor.LowerCenter;
            tag.alignment = TextAlignment.Center;
            tag.color = new Color(1f, 0.95f, 0.8f);
            tag.text = name;
            tagGo.GetComponent<MeshRenderer>().sharedMaterial = font.material;
            c.nameTag = tag;
            return c;
        }
        // 六只都是带骨骼动作、一身绒毛的（tools/blender/animal_import.py 从柴犬、哈士奇的骨架改出来的）
        FurPetPrefab("shiba", 0.72f, 0.035f);
        FurPetPrefab("teddy", 0.56f, 0.055f, curl: 1.6f, comb: 0.25f, density: 360f);
        FurPetPrefab("cotton", 0.78f, 0.065f, comb: 0.5f, density: 380f);
        FurPetPrefab("tangerine", 0.38f, 0.022f, comb: 0.8f, density: 560f);
        FurPetPrefab("tangyuan", 0.38f, 0.026f, comb: 0.8f, density: 560f);
        FurPetPrefab("huajuan", 0.38f, 0.022f, comb: 0.8f, density: 560f);
        FurPetPrefab("zhima", 0.7f, 0.034f);
        FurPetPrefab("tuanzi", 0.74f, 0.075f, comb: 0.45f, density: 360f);
        FurPetPrefab("momo", 0.37f, 0.02f, comb: 0.85f, density: 600f);
        FurPetPrefab("doubao", 0.38f, 0.022f, comb: 0.8f, density: 560f);
        Pet("dog_teddy", "teddy", "栗子", false, new Vector3(2.6f, 0, -8.6f), 4.5f, 1.25f, "gift_bone");
        Pet("dog_shiba", "shiba", "年糕", false, new Vector3(-6.2f, 0, -7.6f), 3.2f, 1.25f, "gift_stick");
        Pet("dog_white", "cotton", "棉花", false, new Vector3(9.6f, 0, 1.4f), 3.2f, 1.2f, "gift_flower");
        Pet("cat_orange", "tangerine", "橘子", true, new Vector3(-5.6f, 0, -0.4f), 3.2f, 1.25f, "gift_fish");
        Pet("cat_white", "tangyuan", "汤圆", true, new Vector3(9.2f, 0, 9.8f), 2.6f, 1.2f, "gift_shell");
        Pet("cat_calico", "huajuan", "花卷", true, new Vector3(-10.6f, 0, -8.0f), 3f, 1.25f, "gift_flower");
        // 后加的四只，分散在岛上别的地方（10 只固定，不来不走）
        Pet("dog_shiba", "zhima", "芝麻", false, new Vector3(6.4f, 0, -12.2f), 3.4f, 1.25f, "gift_stick");
        Pet("dog_white", "tuanzi", "团子", false, new Vector3(-13.6f, 0, 12.0f), 3.6f, 1.2f, "gift_bone");
        Pet("cat_white", "momo", "墨墨", true, new Vector3(13.4f, 0, 11.0f), 2.6f, 1.2f, "gift_fish");
        // 豆包原来的家 (-2.6, 12.2) 在大殿台基上（台基里面，一开始就埋在台基里）：挪到台基前面、台阶西边那一条空地上
        Pet("cat_orange", "doubao", "豆包", true, new Vector3(-4.6f, 0, 9.9f), 2.8f, 1.2f, "gift_shell");

        // 小鸟的落脚点：地上的（w=1）和高处的（w=0）
        var perches = new List<Vector4>();
        foreach (var (x, z) in new[] { (-2.2f, 0.4f), (2.4f, -0.2f), (0.2f, -9.2f), (-3.2f, -13.6f), (3.4f, -12.2f), (6.2f, -1.6f), (-5.6f, -6.4f), (-6.4f, 4.6f), (6.6f, 5.4f), (-2.4f, 8.6f), (2.8f, 8.4f), (-8.4f, 9.6f), (10.4f, 3.8f), (-11f, 0.6f) })
            perches.Add(new Vector4(x, map.H(x, z) + (x > Terrace.xMin && x < Terrace.xMax && z > Terrace.yMin && z < Terrace.yMax ? TerraceH : 0.02f), z, 1));
        for (int i = 0; i < 6; i++) perches.Add(new Vector4(lanternSpots[i].x, 2.52f, lanternSpots[i].z, 0));
        perches.Add(new Vector4(-1.4f, 5.62f, GateZ, 0));
        perches.Add(new Vector4(1.6f, 5.62f, GateZ, 0));
        perches.Add(new Vector4(4.0f, 0.62f, -10.4f, 0));
        perches.Add(new Vector4(-12.0f, 1.98f, -4.4f, 0));
        var birds = Group("Birds", world);
        for (int i = 0; i < 11; i++)
        {
            var p = perches[(i * 3) % 14];
            var go = Put(i % 3 == 2 ? "bird_tit" : "bird_sparrow", birds, new Vector3(p.x + R(-0.5f, 0.5f), p.y, p.z + R(-0.5f, 0.5f)), R(0, 360), R(0.75f, 0.9f), "Bird", false);
            if (go == null) continue;
            var b = go.AddComponent<Bird>();
            b.perches = perches.ToArray();
        }
        // 白鹭：站在浅水里
        for (int i = 0, n = 0; i < 600 && n < 3; i++)
        {
            float x = R(-22f, 22f), z = R(-19f, 28f);
            float sd1 = map.Shore(x, z);
            if (sd1 < -1.3f || sd1 > -0.5f || (Mathf.Abs(x) < 7f && z < -11f) || z > 12f) continue;
            Put("egret", structure, new Vector3(x, WaterY - 0.22f, z), R(0, 360), R(1.1f, 1.3f), "Egret");
            n++;
        }

        foreach (var r in structure.GetComponentsInChildren<MeshRenderer>())
            if (r.name == "glow") lampRenderers.Add(r);

        var tw = BuildEnvironment(world, structure, "Islet", lampRenderers, lampLights, new Vector3(0, 21f, -23f), new Vector3(0, 0.6f, -8f));
        IsletLighting(tw);

        // ── 运行时：能去的地点和走的路线 ──
        Vector3 incense = BurnerAt + Vector3.up * 1.36f;
        // 红布条：颜色全在贴图里（运行时每条一张：布纹 + 写的字，WishCloth.cs），正反两面是分开的两层，各画朝外的一面
        var ribbon = ToonMat("o_ribbon", m =>
        {
            m.SetFloat("_Legacy", 1f);
            m.SetFloat("_Sway", 1.6f);
            m.SetFloat("_Cull", 2f);
            m.SetFloat("_WetAmount", 0.4f);
            m.SetFloat("_SnowAmount", 0f);
            m.SetFloat("_Detail", 0f);
            m.SetColor("_BaseColor", Color.white);
            m.SetColor("_RimColor", new Color(1, 1, 1, 0.08f));
        });
        var game = BuildRuntime("amb_music_temple", "sfx_bell_temple", seats, slots, ribbon, incense, null, 0, true);
        IsletBounds(world, map);
        game.offerings.incenseRadius = 0.3f;
        game.offerings.nearestSlot = true;
        const float gy = 0.06f;
        game.spots = new[]
        {
            new Spot { name = "gate", floor = new Vector3(0, 0.07f, DockAt.z - DockLen - 0.8f), look = new Vector3(0, 1f, 0f), pick = 0 },
            new Spot { name = "court", floor = new Vector3(0, gy, -7.0f), look = new Vector3(0, 1.5f, 6f), pick = 0.01f },
            // 许愿树：绳圈外一周都算「树下」（挂布条时挑离自己最近的那一格）
            new Spot { name = "tree", floor = new Vector3(-5.2f, 0, -5.6f), look = TreeAt + Vector3.up * 1.5f, pick = 3.2f, zone = TreeAt, zoneRadius = RopeR + 1.75f },
            new Spot { name = "burner", floor = new Vector3(0, gy, -4.0f), look = BurnerAt + Vector3.up * 1.2f, pick = 1.4f },
            new Spot { name = "hall", floor = new Vector3(0, TerraceH, 9.05f), look = HallAt + Vector3.up * 3f, pick = 5f },
            // 大殿里面：中间拜垫后面、面朝释迦牟尼像（大殿能进去以后才去得了；点画面不会点中它，进殿走「进殿」按钮或者自己走进去）
            new Spot { name = "inhall", floor = new Vector3(0, HallFloor, 17.1f), look = new Vector3(0, 2.6f, 21.05f), pick = 0 },
        };
        isletObs.Add(new Obstacle { center = PondAt, radius = PondR + 0.9f });
        game.obstacles = isletObs.ToArray();
        game.hub = new Vector3(0, gy, 1.3f);
        game.courtMinZ = GateZ - 0.5f;
        // 座位区：中间一条南北向的过道（两边蒲团离中线 1.3 米），每排蒲团前面（草垫和下一排之间的空当）是横着走的小道
        game.aislePoint = new Vector3(0, TerraceH, 5f);
        game.aisleDir = Vector3.forward;
        game.laneOffset = new Vector3(0, 0, SeatLane);
        game.seatBlock = Rect.MinMaxRect(-(SeatX0 + (SeatCols - 1) * SeatDX + 0.75f), SeatZ0 - 0.5f, SeatX0 + (SeatCols - 1) * SeatDX + 0.75f, SeatZ0 + (SeatRows - 1) * SeatDZ + SeatLane + 0.15f);
        // 过道两头的进出口：南头（香炉那边）、北头（大殿台阶前）
        game.seatEntries = new[] { new Vector3(0, TerraceH, SeatZ0 - 0.9f), new Vector3(0, TerraceH, game.seatBlock.yMax + 0.35f) };
        game.seatGap = SeatDX / 2f;
        game.sitRadius = 1.2f;
        // 铺好的路（自动走路顺着走，GameDirector.Road）：码头 → 山门 → 主路 → 香炉外一圈（离香炉中心 2.9 米，在圆形铺地上，
        // 香客进出石台的那几点 seatExitNeg/Pos 也在这一圈上下）→ 石台中间过道 → 殿前 → 台阶 → 殿门外；香炉一圈往西是去许愿树的踏脚石，往东是去池塘的；
        // 石台的外圈（南沿、东西两头、北沿到殿前）：从钟亭、石台两头去大殿沿着石台边走，不从蒲团中间穿。
        // 点都避开了要绕开的东西（香炉 1.55、树和绳圈 3.5、池塘 4.0、石灯笼 0.8、太平缸 0.9、石碑 1.0）
        {
            var rn = new List<Vector3>();
            var rl = new List<int>();
            int N(float x, float y, float z) { rn.Add(new Vector3(x, y, z)); return rn.Count - 1; }
            void L(params int[] chain) { for (int i = 1; i < chain.Length; i++) { rl.Add(chain[i - 1]); rl.Add(chain[i]); } }
            int dockEnd = N(0, 0.07f, DockAt.z - DockLen - 0.8f), dockRoot = N(0, 0.07f, DockAt.z - 0.2f);
            int gateS = N(0, gy, GateZ - 0.9f), gateN = N(0, gy, GateZ + 0.9f);
            const float ringR = 2.9f;
            var ring = new int[8];
            // 从正南起逆时针：0 南、2 东、4 北、6 西
            for (int k = 0; k < 8; k++)
            {
                float a = -Mathf.PI / 2 + k * Mathf.PI / 4;
                ring[k] = N(BurnerAt.x + Mathf.Cos(a) * ringR, gy, BurnerAt.z + Mathf.Sin(a) * ringR);
            }
            int aisleS = N(0, TerraceH, SeatZ0 - 0.9f), aisleN = N(0, TerraceH, game.seatBlock.yMax + 0.35f), front = N(0, TerraceH, 9.05f), door = N(0, HallFloor, 14.0f);
            int treeA = N(-4.1f, 0, -2.4f), treeB = N(-5.0f, 0, -3.5f), pond = N(4.3f, 0, -2.5f);
            // 石台外圈：南沿在第一排蒲团前（座位区南边 z 2.0 以外），东西两头 x ±10.5（太平缸外侧、石碑里侧），北沿和殿前那一点齐
            const float rimX = 10.5f, rimS = 1.75f, rimN = 8.8f;
            int rimSE = N(rimX, TerraceH, rimS), rimNE = N(rimX, TerraceH, rimN), rimSW = N(-rimX, TerraceH, rimS), rimNW = N(-rimX, TerraceH, rimN);
            // 北沿走到殿前那一段：台阶两边的垂带（x ±2.35..2.75）往南伸到 z 9.2，北沿直着连到殿前那一点只离垂带的端头 0.2 米，
            // 人一被挤就蹭上去、顺着垂带的侧面滑进垂带和台基之间那个角里出不来。在垂带端头南边加一点，绕开它
            int cheekE = N(3.2f, TerraceH, 8.7f), cheekW = N(-3.2f, TerraceH, 8.7f);
            L(dockEnd, dockRoot, gateS, gateN, ring[0]);
            for (int k = 0; k < 8; k++) L(ring[k], ring[(k + 1) % 8]);
            L(ring[4], aisleS, aisleN, front, door);
            L(aisleS, rimSE, rimNE, cheekE, front);
            L(aisleS, rimSW, rimNW, cheekW, front);
            // 殿前廊下的两头（台基上、殿墙外）：从殿两侧的台基上回到殿门、走台阶
            int porchE = N(7.6f, HallFloor, 13.5f), porchW = N(-7.6f, HallFloor, 13.5f);
            L(porchW, door, porchE);
            L(ring[6], treeA, treeB);
            L(ring[2], pond);
            game.roadNodes = rn.ToArray();
            game.roadLinks = rl.ToArray();
            game.offRoadCost = 1.7f;
            // 自动走路不穿过的线：山门两边（门柱外侧到岸边：从码头上岛、回码头都过山门，门柱中间净宽 3.5 米，主路宽 2.7 米）；
            // 大殿台基的四边（台基高 0.7，前面只有中间的台阶 x ±2.35、两边是栏杆：上殿下殿都走台阶）；
            // 殿的两山墙、后墙和前面两边的槛窗（只有中间三间的门开着）：从殿两侧的台基上进殿先绕到廊下
            const float podX = 8.8f, podZ0 = 10.9f, podZ1 = 23.85f, stairX = 2.3f, wallX = 6.6f, wallZ0 = 14.4f, wallZ1 = 22.2f, doorX = 3.7f;
            game.planWalls = new[]
            {
                new Vector4(-16f, GateZ, -1.4f, GateZ), new Vector4(1.4f, GateZ, 16f, GateZ),
                new Vector4(-podX, podZ0, -stairX, podZ0), new Vector4(stairX, podZ0, podX, podZ0),
                new Vector4(-podX, podZ0, -podX, podZ1), new Vector4(podX, podZ0, podX, podZ1), new Vector4(-podX, podZ1, podX, podZ1),
                new Vector4(-wallX, wallZ0, -wallX, wallZ1), new Vector4(wallX, wallZ0, wallX, wallZ1), new Vector4(-wallX, wallZ1, wallX, wallZ1),
                new Vector4(-wallX, wallZ0, -doorX, wallZ0), new Vector4(doorX, wallZ0, wallX, wallZ0),
                // 台阶两边的垂带（从台基往南伸出来 1.7 米）：不从它上面、端头上斜着穿过去
                new Vector4(-2.55f, 9.05f, -2.55f, podZ0), new Vector4(2.55f, 9.05f, 2.55f, podZ0),
            };
        }
        game.hallSeats = hallSeats;
        // 许愿树的绳圈：点了绳圈里面的地，走到绳外就停（绳子挡人，走进去就出不来了）
        game.ropeCenter = TreeAt;
        game.ropeRadius = RopeR;
        // 大殿里面（spec E）：进殿锁平视、拜垫、供桌前上香、殿里的蒲团
        game.hallOpen = HallOpen;
        game.hallRect = Rect.MinMaxRect(-6.5f, 14.4f, 6.5f, 22.0f);
        game.hallFloor = HallFloor;
        game.hallDoorOut = new Vector3(0, HallFloor, 14.0f);
        game.hallDoorIn = new Vector3(0, HallFloor, 15.0f);
        game.hallMats = hallMats;
        // 殿里三只香炉上的细烟（中间那只在香灰面上方 4 厘米；两边供桌上的小香炉：模型 0.75 倍，灰面约在桌面上 0.13 米）
        game.offerings.hallSmoke = BuildHallSmoke(game.transform, game.hallIncense + Vector3.up * 0.04f, 1f, "HallSmoke");
        game.offerings.hallSideSmoke = new[] { -1f, 1f }.Select(sx => BuildHallSmoke(game.transform, new Vector3(sx * 3.6f, 1.504f + 0.14f, 19.22f), 0.55f, "HallSmokeSide")).ToArray();
        // 殿里人身下的接触影子（Folk 自己在脚下摆一块）
        game.contactShadow = ContactMat(true);
        game.matRadius = 0.9f;
        game.hallFacing = Vector3.forward;
        // 上香站的那一点：中间拜垫（到 z 18.175）和供桌桌围（z 18.817）之间那一条里。整个上香都站在这里不挪：
        // Incense_Plant 脚不动、俯身，手正好伸到灰面中心上方（人前方 0.48 米）
        game.altarStand = new Vector3(0, HallFloor, 18.52f);
        game.altarRadius = 1.6f;
        // 殿里香炉 censer_hall 放在 (0, 1.504, 19.0)，灰面中心世界 (0, 1.682, 19.0)
        game.hallIncense = new Vector3(0, 1.682f, 19.0f);
        game.hallCeiling = 5.35f;
        // 殿里平视镜头：放低（比人的腰高一点），画面往上抬着把正前方那尊佛像（肉髻顶）整个放进来（ThirdPersonCamera.FrameTilt）
        game.hallCamPitch = -2f;
        game.hallLookAts = new[] { new Vector3(0, 4.45f, 21.0f), new Vector3(-3.6f, 4.0f, 21.0f), new Vector3(3.6f, 4.0f, 21.0f) };
        game.seatExitNeg = new[] { new Vector3(-0.2f, TerraceH, 1.6f) };
        game.seatExitPos = new[] { new Vector3(0.2f, TerraceH, 1.6f) };
        game.seatLook = HallAt + Vector3.up * 3f;
        game.seatDrop = 0f;      // 座位点就是地面（蒲团下面）
        game.seatStraight = 0.85f;
        game.nearRadius = 2.2f;
        // 大殿前那两处（4、5）：站在台阶两边、离中线 1.65 米（以前在台阶正下方 ±0.45 米，你点「进殿」时从他们肩膀边上 0.45 米挤过去）
        ConfigureCrowd(game, new Vector3(0, 0.07f, DockAt.z - DockLen - DockPlat + 0.6f), new Vector3(0, gy, -13.4f),
            new[] { new Vector3(-5.0f, 0, -5.9f), new Vector3(0.7f, gy, -4.1f), new Vector3(-0.9f, gy, -4.0f), new Vector3(5.6f, 0, -2.6f), new Vector3(-1.65f, TerraceH, 8.85f),
                    new Vector3(1.65f, TerraceH, 8.85f), new Vector3(12.8f, 0, 2.6f), new Vector3(-12.6f, 0, 3.0f), new Vector3(-3.6f, 0, -14.3f) },
            new[] { TreeAt + Vector3.up, BurnerAt + Vector3.up, BurnerAt + Vector3.up, PondAt, HallAt + Vector3.up * 2f, HallAt + Vector3.up * 2f, PavilionAt + Vector3.up,
                    new Vector3(-11.6f, 1f, 3.6f), new Vector3(-3.4f, 0, -20f) },
            false);
        // 其他人进出座位区：从山门到石台，中间要绕开香炉（两边各走一侧）
        game.pilgrims.seatExitNeg = new[] { new Vector3(-0.2f, TerraceH, 1.6f), new Vector3(-2.4f, gy, 0.6f), new Vector3(-2.6f, gy, -3.6f), new Vector3(-0.8f, gy, -6.6f) };
        game.pilgrims.seatExitPos = new[] { new Vector3(0.2f, TerraceH, 1.6f), new Vector3(2.4f, gy, 0.6f), new Vector3(2.6f, gy, -3.6f), new Vector3(0.8f, gy, -6.6f) };
        game.pilgrims.keepClear = new[] { Rect.MinMaxRect(-1.2f, 7.95f, 1.2f, 9.45f), Rect.MinMaxRect(-2.8f, 9.45f, 2.8f, 11.0f) };
        game.pilgrims.aislePoint = game.aislePoint;
        game.pilgrims.aisleDir = game.aisleDir;
        game.pilgrims.laneOffset = game.laneOffset;
        game.pilgrims.strollers = 5;

        // 香烟、光点按俯视的远近放大
        if (game.offerings.smoke != null)
        {
            var sm = game.offerings.smoke.main;
            sm.startSize = new ParticleSystem.MinMaxCurve(0.5f, 0.9f);
            sm.startLifetime = new ParticleSystem.MinMaxCurve(5f, 8f);
            var se = game.offerings.smoke.emission;
            se.rateOverTime = 4f;
            var ss = game.offerings.smoke.shape;
            ss.radius = 0.28f;
        }
        if (game.offerings.sparkle != null)
        {
            var sp = game.offerings.sparkle.main;
            sp.startSize = new ParticleSystem.MinMaxCurve(0.05f, 0.14f);
            sp.startSpeed = new ParticleSystem.MinMaxCurve(0.3f, 1.4f);
        }
        // 雨雪下在人周围（俯视镜头自己离得很远）
        foreach (var f in UnityEngine.Object.FindObjectsByType<FollowCamera>(FindObjectsSortMode.None)) f.anchor = game.player.transform;
        // 湖水拍岸的声音：在码头和岸边听得清，往岛里走就淡下去。用的是专门合成的低频水声
        //（之前借用教堂喷泉的高频水声，眼前没有喷泉，听着像电流杂音）
        game.sound.placedLoop = "amb_lake";
        game.sound.placedAt = new Vector3(0, 0, DockAt.z - 2f);
        game.sound.placedVolume = 0.6f;
        game.sound.placedRange = 20f;
        game.sound.placedListener = game.player.transform;

        BuildAmbience(world, game.player.transform);
        HallOutsideCull(world);
        // 殿里金砖地的反光图（白天、夜里）：场景都摆好了再烘
        BakeHallReflection(tw);

        EditorSceneManager.SaveScene(scene, "Assets/Scenes/Islet.unity");
        AssetDatabase.SaveAssets();
        Debug.Log("[yuanjing] 湖心小寺已生成");
    }

    static Light PointLamp(Transform parent, Vector3 at, float range, float intensity)
    {
        var go = new GameObject("LampLight");
        go.transform.SetParent(parent, false);
        go.transform.position = at;
        var l = go.AddComponent<Light>();
        l.type = LightType.Point;
        l.color = new Color(1f, 0.78f, 0.50f);
        l.range = range;
        l.intensity = intensity;
        l.shadows = LightShadows.None;
        return l;
    }

    /// 这座殿自己的光照：卡通画面里太阳不能贴着地平线（俯视下整片地都会落进影子里），夜里也要看得清
    static void IsletLighting(TimeWeather tw)
    {
        foreach (var p in tw.presets)
        {
            switch (p.name)
            {
                case "dawn":
                    p.sunAzimuth = -128f; p.sunElevation = 30f; p.sunColor = new Color(1f, 0.80f, 0.62f); p.sunIntensity = 2.6f;
                    p.ambientSky = new Color(0.86f, 0.80f, 1.02f); p.ambientEquator = new Color(0.92f, 0.78f, 0.74f); p.ambientGround = new Color(0.52f, 0.44f, 0.42f);
                    p.postExposure = 0f; p.temperature = 6f; p.lamps = 0.35f; p.fogDensity = 0.004f;
                    break;
                case "day":
                    p.sunAzimuth = -142f; p.sunElevation = 54f; p.sunColor = new Color(1f, 0.97f, 0.90f); p.sunIntensity = 2.9f;
                    p.ambientSky = new Color(0.92f, 1.02f, 1.22f); p.ambientEquator = new Color(0.94f, 0.96f, 1.0f); p.ambientGround = new Color(0.62f, 0.60f, 0.52f);
                    p.postExposure = 0f; p.temperature = 0f; p.lamps = 0f; p.fogDensity = 0.002f;
                    break;
                case "dusk":
                    p.sunAzimuth = 138f; p.sunElevation = 26f; p.sunColor = new Color(1f, 0.62f, 0.36f); p.sunIntensity = 2.7f;
                    p.ambientSky = new Color(0.80f, 0.70f, 1.0f); p.ambientEquator = new Color(0.96f, 0.70f, 0.60f); p.ambientGround = new Color(0.50f, 0.38f, 0.36f);
                    p.postExposure = 0f; p.temperature = 8f; p.lamps = 0.75f; p.fogDensity = 0.004f;
                    break;
                case "night":
                    p.sunAzimuth = -140f; p.sunElevation = 52f; p.sunColor = new Color(0.62f, 0.74f, 1f); p.sunIntensity = 1.5f;
                    p.ambientSky = new Color(0.30f, 0.40f, 0.78f); p.ambientEquator = new Color(0.26f, 0.32f, 0.60f); p.ambientGround = new Color(0.14f, 0.16f, 0.30f);
                    p.postExposure = 0f; p.temperature = -4f; p.lamps = 1f; p.fogDensity = 0.004f;
                    break;
            }
        }
        // 后期：不用电影式的色调映射（它会把鲜艳的颜色压灰），辉光轻一点
        const string path = "Assets/Settings/PostToon.asset";
        var profile = AssetDatabase.LoadAssetAtPath<VolumeProfile>(path);
        if (profile == null)
        {
            profile = ScriptableObject.CreateInstance<VolumeProfile>();
            AssetDatabase.CreateAsset(profile, path);
            var bloom = profile.Add<Bloom>(true);
            bloom.threshold.value = 1.0f;
            bloom.intensity.value = 0.4f;
            bloom.scatter.value = 0.65f;
            bloom.highQualityFiltering.value = true;
            var tone = profile.Add<Tonemapping>(true);
            tone.mode.value = TonemappingMode.Neutral;
            var ca = profile.Add<ColorAdjustments>(true);
            ca.postExposure.value = 0f;
            ca.contrast.value = 6f;
            ca.saturation.value = 6f;
            var wb = profile.Add<WhiteBalance>(true);
            wb.temperature.value = 0f;
            var vig = profile.Add<Vignette>(true);
            vig.intensity.value = 0.2f;
            vig.smoothness.value = 0.5f;
            foreach (var c in profile.components) AssetDatabase.AddObjectToAsset(c, profile);
            EditorUtility.SetDirty(profile);
            AssetDatabase.SaveAssets();
        }
        tw.volume.sharedProfile = profile;
        tw.lampColor = new Color(1f, 0.66f, 0.30f);
        tw.ApplyImmediate(DayTime.Day, Weather.Clear);
        var cam = Camera.main;
        cam.fieldOfView = 36f;
        cam.nearClipPlane = 0.5f;
        cam.farClipPlane = 300f;
    }

    /// 边界：沿着岸一圈看不见的矮墙（人不会走进水里），池塘一圈，栈桥两侧
    static void IsletBounds(Transform world, IsletMap map)
    {
        var root = Group("Bounds", world);
        const int N = 180;
        Vector3 Edge(int i)
        {
            float ang = i / (float)N * Mathf.PI * 2f;
            Vector2 dir = new Vector2(Mathf.Cos(ang), Mathf.Sin(ang));
            float lo = 4f, hi = 30f;
            for (int k = 0; k < 22; k++)
            {
                float mid = (lo + hi) * 0.5f;
                Vector2 p = IsleC + dir * mid;
                if (map.Shore(p.x, p.y) > 0.9f) lo = mid; else hi = mid;
            }
            Vector2 q = IsleC + dir * lo;
            return new Vector3(q.x, 0, q.y);
        }
        const float dx = 1.2f;
        for (int i = 0; i < N; i++)
        {
            Vector3 a = Edge(i), b = Edge((i + 1) % N);
            // 栈桥接岸的地方留一个口
            if (a.z < -13f && b.z < -13f)
            {
                bool ain = Mathf.Abs(a.x) < dx, bin = Mathf.Abs(b.x) < dx;
                if (ain && bin) continue;
                if (ain != bin)
                {
                    float sx = Mathf.Sign(ain ? b.x : a.x);
                    float t = (sx * dx - a.x) / (b.x - a.x);
                    Vector3 c = Vector3.Lerp(a, b, t);
                    if (ain) a = c; else b = c;
                }
            }
            Wall(root, a, b);
        }
        // 栈桥两侧和尽头的平台
        float z0 = DockAt.z + 1.6f, z1 = DockAt.z - DockLen, z2 = z1 - DockPlat + 0.15f;
        foreach (float sx in new[] { -1f, 1f })
        {
            Wall(root, new Vector3(sx * dx, 0, z0), new Vector3(sx * dx, 0, z1));
            Wall(root, new Vector3(sx * dx, 0, z1), new Vector3(sx * 2.42f, 0, z1));
            Wall(root, new Vector3(sx * 2.42f, 0, z1), new Vector3(sx * 2.42f, 0, z2));
        }
        Wall(root, new Vector3(-2.42f, 0, z2), new Vector3(2.42f, 0, z2));
        // 池塘
        const int M = 40;
        Vector3 PondEdge(int i)
        {
            float ang = i / (float)M * Mathf.PI * 2f;
            Vector2 dir = new Vector2(Mathf.Cos(ang), Mathf.Sin(ang));
            Vector2 c = new Vector2(PondAt.x, PondAt.z);
            float lo = 0.5f, hi = 7f;
            for (int k = 0; k < 20; k++)
            {
                float mid = (lo + hi) * 0.5f;
                Vector2 p = c + dir * mid;
                if (map.Pond(p.x, p.y) > -0.45f) lo = mid; else hi = mid;
            }
            Vector2 q = c + dir * lo;
            return new Vector3(q.x, 0, q.y);
        }
        for (int i = 0; i < M; i++) Wall(root, PondEdge(i), PondEdge((i + 1) % M));
    }

    /// 卡通场景不用 AddColliders（那是按山寺、教堂的物体名字来的）：碰撞在摆东西的时候就加好了，这里只垫一块底
    static void AddToonColliders()
    {
        var ground = new GameObject("GroundCollider");
        var box = ground.AddComponent<BoxCollider>();
        box.center = new Vector3(0, -4.6f, 0);
        box.size = new Vector3(300, 1, 300);
    }

    static void BuildToonWater(Transform parent)
    {
        var go = GameObject.CreatePrimitive(PrimitiveType.Plane);
        UnityEngine.Object.DestroyImmediate(go.GetComponent<Collider>());
        go.name = "Water";
        go.transform.SetParent(parent, false);
        go.transform.position = new Vector3(0, WaterY, 0);
        go.transform.localScale = new Vector3(34, 1, 34);
        var r = go.GetComponent<MeshRenderer>();
        r.sharedMaterial = ToonMat("water");
        r.shadowCastingMode = ShadowCastingMode.Off;
    }

    /// 蝴蝶、萤火虫、落叶和花瓣
    static void BuildAmbience(Transform world, Transform player)
    {
        var root = Group("Ambience", world);
        var amb = root.gameObject.AddComponent<Ambience>();
        var dot = DotTexture();
        var leafTex = SaveTexture("gen_leafshape_color", 32, 32, (u, v) =>
        {
            // 一片小叶子：两头尖的椭圆
            float x = (u - 0.5f) * 2f, y = (v - 0.5f) * 2f;
            float w = 0.55f * Mathf.Sqrt(Mathf.Max(0, 1 - y * y));
            float a = Mathf.Clamp01((w - Mathf.Abs(x)) * 8f) * Mathf.Clamp01((1 - Mathf.Abs(y)) * 6f);
            return new Color(1, 1, 1, a);
        });

        ParticleSystem Fall(string name, Vector3 at, Vector3 size, Color a, Color b, float rate)
        {
            var mat = ParticleMaterial("toon_" + name, leafTex, Color.white, false, true);
            // 屋檐下不画：跟着人飘的那一层在殿里会从屋顶穿下来
            mat.SetFloat("_Outdoor", 1f);
            var ps = Particles(name, root, mat);
            ps.transform.position = at;
            var m = ps.main;
            m.startLifetime = new ParticleSystem.MinMaxCurve(7f, 11f);
            m.startSpeed = 0f;
            m.startSize = new ParticleSystem.MinMaxCurve(0.16f, 0.26f);
            m.startRotation3D = true;
            m.startRotationX = new ParticleSystem.MinMaxCurve(0, Mathf.PI * 2);
            m.startRotationY = new ParticleSystem.MinMaxCurve(0, Mathf.PI * 2);
            m.startRotationZ = new ParticleSystem.MinMaxCurve(0, Mathf.PI * 2);
            m.startColor = new ParticleSystem.MinMaxGradient(a, b);
            m.maxParticles = 60;
            m.simulationSpace = ParticleSystemSimulationSpace.World;
            m.gravityModifier = 0.02f;
            var e = ps.emission;
            e.rateOverTime = rate;
            var sh = ps.shape;
            sh.shapeType = ParticleSystemShapeType.Box;
            sh.scale = size;
            var v = ps.velocityOverLifetime;
            v.enabled = true;
            v.space = ParticleSystemSimulationSpace.World;
            v.x = new ParticleSystem.MinMaxCurve(0.2f, 0.7f);
            v.y = new ParticleSystem.MinMaxCurve(-0.75f, -0.45f);
            v.z = new ParticleSystem.MinMaxCurve(-0.2f, 0.3f);
            var n = ps.noise;
            n.enabled = true;
            n.strength = 0.5f;
            n.frequency = 0.35f;
            n.scrollSpeed = 0.2f;
            var rot = ps.rotationOverLifetime;
            rot.enabled = true;
            rot.separateAxes = true;
            rot.x = new ParticleSystem.MinMaxCurve(-2f, 2f);
            rot.y = new ParticleSystem.MinMaxCurve(-2f, 2f);
            rot.z = new ParticleSystem.MinMaxCurve(-1f, 1f);
            var col = ps.colorOverLifetime;
            col.enabled = true;
            col.color = FadeInOut(0.08f);
            var r = ps.GetComponent<ParticleSystemRenderer>();
            r.renderMode = ParticleSystemRenderMode.Mesh;
            r.mesh = Resources.GetBuiltinResource<Mesh>("Quad.fbx");
            r.alignment = ParticleSystemRenderSpace.World;
            return ps;
        }
        var falls = new List<ParticleSystem>
        {
            Fall("LeavesWish", TreeAt + Vector3.up * 5.5f, new Vector3(7f, 1f, 7f), new Color(0.56f, 0.80f, 0.36f), new Color(0.86f, 0.90f, 0.42f), 1.2f),
            Fall("LeavesMaple", new Vector3(-12.6f, 4.2f, 7.6f), new Vector3(5f, 1f, 5f), new Color(0.95f, 0.45f, 0.22f), new Color(0.98f, 0.66f, 0.26f), 1.0f),
            Fall("Petals", new Vector3(11.8f, 3.6f, -4.6f), new Vector3(6f, 1f, 8f), new Color(0.98f, 0.72f, 0.80f), new Color(1f, 0.90f, 0.93f), 1.4f),
            Fall("LeavesGinkgo", new Vector3(14.4f, 4.6f, 2.8f), new Vector3(4f, 1f, 4f), new Color(0.98f, 0.82f, 0.30f), new Color(1f, 0.90f, 0.5f), 0.8f),
        };
        // 跟着人走的一层：身边总有几片花瓣、叶子慢慢飘过（整座岛都有，不只在树下）
        foreach (var (name, a, b, rate) in new[] { ("DriftPetals", new Color(0.99f, 0.76f, 0.83f), new Color(1f, 0.93f, 0.95f), 2.6f), ("DriftLeaves", new Color(0.97f, 0.66f, 0.28f), new Color(0.99f, 0.85f, 0.38f), 1.6f) })
        {
            var ps = Fall(name, Vector3.zero, new Vector3(15f, 1f, 20f), a, b, rate);
            ps.transform.SetParent(player, false);
            ps.transform.localPosition = new Vector3(0, 6.5f, 3f);
            var mm = ps.main;
            mm.maxParticles = 90;
            mm.startLifetime = new ParticleSystem.MinMaxCurve(9f, 14f);
            falls.Add(ps);
        }
        amb.leaves = falls.ToArray();
        amb.leafRate = 1.5f;

        // 阳光里的浮尘：很淡的小亮点慢慢浮动
        {
            var mat = ParticleMaterial("toon_mote", dot, new Color(1.6f, 1.5f, 1.1f, 0.5f), true, false);
            // 浮尘是看远处才有的一点点亮：离镜头 4 米以内就淡掉（凑近拍布条、上香时，镜头前一粒有半个巴掌大的白斑）
            mat.SetVector("_Near", new Vector4(2.0f, 4.0f, 0f, 0f));
            var ps = Particles("Motes", root, mat);
            ps.transform.SetParent(player, false);
            ps.transform.localPosition = new Vector3(0, 1.6f, 2f);
            var m = ps.main;
            m.startLifetime = new ParticleSystem.MinMaxCurve(6f, 10f);
            m.startSpeed = new ParticleSystem.MinMaxCurve(0.02f, 0.12f);
            // 一粒 1.5–3.5 厘米（原来 3–7 厘米：特写里离镜头两三米的一粒也是一大团白斑）
            m.startSize = new ParticleSystem.MinMaxCurve(0.015f, 0.035f);
            m.maxParticles = 60;
            m.simulationSpace = ParticleSystemSimulationSpace.World;
            var e = ps.emission;
            e.rateOverTime = 6f;
            var sh = ps.shape;
            sh.shapeType = ParticleSystemShapeType.Box;
            sh.scale = new Vector3(14f, 3f, 20f);
            var n = ps.noise;
            n.enabled = true;
            n.strength = 0.25f;
            n.frequency = 0.3f;
            var col = ps.colorOverLifetime;
            col.enabled = true;
            col.color = FadeInOut(0.3f);
        }
        // 小动物高兴时头顶的爱心
        {
            var heartTex = SaveTexture("gen_heart_color", 48, 48, (u, v) =>
            {
                float x = (u - 0.5f) * 2.6f, y = (v - 0.42f) * 2.6f;
                float f = Mathf.Pow(x * x + y * y - 1f, 3f) - x * x * y * y * y;
                return new Color(1, 1, 1, Mathf.Clamp01(-f * 6f));
            });
            var mat = ParticleMaterial("toon_heart", heartTex, new Color(1f, 0.42f, 0.5f, 1f), false, false);
            var ps = Particles("Hearts", root, mat);
            var m = ps.main;
            m.startLifetime = new ParticleSystem.MinMaxCurve(1.1f, 1.7f);
            m.startSpeed = new ParticleSystem.MinMaxCurve(0.5f, 0.9f);
            m.startSize = new ParticleSystem.MinMaxCurve(0.2f, 0.32f);
            m.maxParticles = 60;
            m.simulationSpace = ParticleSystemSimulationSpace.World;
            m.gravityModifier = -0.05f;
            var sh = ps.shape;
            sh.shapeType = ParticleSystemShapeType.Cone;
            sh.angle = 28f;
            sh.radius = 0.12f;
            ps.transform.rotation = Quaternion.Euler(-90, 0, 0);
            var col = ps.colorOverLifetime;
            col.enabled = true;
            col.color = FadeInOut(0.15f);
            var sz = ps.sizeOverLifetime;
            sz.enabled = true;
            sz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0, 0.4f, 1, 1.15f));
            amb.hearts = ps;
        }
        amb.grain = Put("grain", root, Vector3.zero, 0, 1f, "Grain", false);
        if (amb.grain != null) amb.grain.SetActive(false);

        // 萤火虫：夜里在草丛上方一明一灭
        {
            var mat = ParticleMaterial("toon_firefly", dot, new Color(3.2f, 3.4f, 1.2f, 1f), true, false);
            mat.SetFloat("_Outdoor", 1f);
            var ps = Particles("Fireflies", root, mat);
            ps.transform.SetParent(player, false);
            ps.transform.localPosition = new Vector3(0, 1.2f, 2f);
            var m = ps.main;
            m.startLifetime = new ParticleSystem.MinMaxCurve(5f, 9f);
            m.startSpeed = new ParticleSystem.MinMaxCurve(0.05f, 0.25f);
            m.startSize = new ParticleSystem.MinMaxCurve(0.09f, 0.16f);
            m.maxParticles = 70;
            m.simulationSpace = ParticleSystemSimulationSpace.World;
            var sh = ps.shape;
            sh.shapeType = ParticleSystemShapeType.Box;
            sh.scale = new Vector3(16f, 1.6f, 22f);
            var n = ps.noise;
            n.enabled = true;
            n.strength = 0.5f;
            n.frequency = 0.5f;
            var col = ps.colorOverLifetime;
            col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0), new GradientColorKey(Color.white, 1) },
                new[] { new GradientAlphaKey(0, 0), new GradientAlphaKey(1, 0.15f), new GradientAlphaKey(0.15f, 0.4f), new GradientAlphaKey(1, 0.6f), new GradientAlphaKey(0.2f, 0.8f), new GradientAlphaKey(0, 1) });
            col.color = g;
            amb.fireflies = ps;
        }
        // 蝴蝶：白天在花丛上方飞，翅膀一开一合
        {
            var mat = ParticleMaterial("toon_butterfly", leafTex, Color.white, false, true);
            mat.SetFloat("_Outdoor", 1f);
            var ps = Particles("Butterflies", root, mat);
            ps.transform.SetParent(player, false);
            ps.transform.localPosition = new Vector3(0, 0.9f, 2f);
            var m = ps.main;
            m.startLifetime = new ParticleSystem.MinMaxCurve(9f, 14f);
            m.startSpeed = new ParticleSystem.MinMaxCurve(0.2f, 0.5f);
            m.startSize3D = true;
            m.startSizeX = new ParticleSystem.MinMaxCurve(0.2f, 0.28f);
            m.startSizeY = new ParticleSystem.MinMaxCurve(0.2f, 0.28f);
            m.startSizeZ = 1f;
            m.startColor = new ParticleSystem.MinMaxGradient(new Color(1f, 0.96f, 0.70f), new Color(1f, 0.80f, 0.86f));
            m.maxParticles = 10;
            m.simulationSpace = ParticleSystemSimulationSpace.World;
            var sh = ps.shape;
            sh.shapeType = ParticleSystemShapeType.Box;
            sh.scale = new Vector3(12f, 0.8f, 16f);
            var n = ps.noise;
            n.enabled = true;
            n.strength = 0.9f;
            n.frequency = 0.6f;
            n.scrollSpeed = 0.4f;
            var sz = ps.sizeOverLifetime;
            sz.enabled = true;
            sz.separateAxes = true;
            // 翅膀开合：横向的宽度快速地一大一小
            var flap = new AnimationCurve();
            for (int i = 0; i <= 80; i++) flap.AddKey(new Keyframe(i / 80f, i % 2 == 0 ? 1f : 0.25f));
            sz.x = new ParticleSystem.MinMaxCurve(1f, flap);
            sz.y = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Constant(0, 1, 1));
            sz.z = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Constant(0, 1, 1));
            var col = ps.colorOverLifetime;
            col.enabled = true;
            col.color = FadeInOut(0.06f);
            var r = ps.GetComponent<ParticleSystemRenderer>();
            r.renderMode = ParticleSystemRenderMode.HorizontalBillboard;
            amb.butterflies = ps;
        }
    }
}
