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
    const float PathW = 1.35f, GateZ = -12.5f, PlazaR = 3.7f, TreeBed = 2.3f, PondR = 3.1f, TerraceH = 0.14f;
    static readonly Vector3 BurnerAt = new Vector3(0, 0, -2f), TreeAt = new Vector3(-8.6f, 0, -3f), PondAt = new Vector3(8.8f, 0, -4.2f);
    static readonly Vector3 HallAt = new Vector3(0, 0, 15.8f), PavilionAt = new Vector3(11.6f, 0, 6.4f), DockAt = new Vector3(0, 0, -15.4f);
    static readonly Rect Terrace = Rect.MinMaxRect(-7.4f, 3.0f, 7.4f, 9.2f);
    const float DockLen = 6.2f, DockPlat = 3.0f;
    // 许愿树的绳圈（同 plants.py 的 tree_wish）
    const int RopePosts = 8;
    const float RopeR = 2.95f, RopeH = 1.55f;

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
        }
        set?.Invoke(m);
        EditorUtility.SetDirty(m);
        toonMats[name] = m;
        return m;
    }

    static void ToonMaterials()
    {
        ToonMat("toon", m => { m.SetFloat("_Cull", 2f); m.SetFloat("_Sway", 1f); });
        ToonMat("leaf", m => { m.SetFloat("_Cull", 0f); m.SetFloat("_Sway", 1f); m.SetFloat("_SnowAmount", 0.5f); m.SetColor("_RimColor", new Color(1, 1, 1, 0.04f)); });
        ToonMat("glow", m => { m.SetFloat("_Cull", 2f); m.SetFloat("_WetAmount", 0f); m.SetFloat("_SnowAmount", 0f); m.SetColor("_EmissionColor", Color.black); });
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

        // ── 建筑 ──
        var hall = Put("hall", structure, HallAt);
        var hallBox = hall.AddComponent<BoxCollider>();
        hallBox.center = new Vector3(0, 2f, -0.2f);
        hallBox.size = new Vector3(17.6f, 4f, 10.4f);
        var steps = new GameObject("StepsBlock");
        steps.transform.SetParent(hall.transform, false);
        var stepBox = steps.AddComponent<BoxCollider>();
        stepBox.center = new Vector3(0, 1f, -5.6f);
        stepBox.size = new Vector3(5.6f, 2f, 1.6f);

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
            if (mf.name == "toon") mf.gameObject.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh;
        Put("boat", structure, new Vector3(3.5f, WaterY + 0.02f, DockAt.z - DockLen - 1.4f), 172, 1f, "Boat", false).AddComponent<Bob>();

        // ── 香炉、许愿树、蒲团、石灯笼 ──
        Solid(Put("burner", structure, BurnerAt + Vector3.up * 0.0f), 0.95f, 1.6f, 1.55f);
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
            Solid(post, 0.16f, 1.7f);
            for (int k = 1; k <= 4; k++)
            {
                float t = k / 5f;
                var s = new GameObject($"Slot{slots.childCount}");
                s.transform.SetParent(slots, false);
                s.transform.position = Vector3.Lerp(p0, p1, t) + Vector3.up * (RopeH - 0.2f * 4f * t * (1 - t) - 0.03f);
            }
        }

        var seats = Group("Seats", structure);
        int seatN = 0;
        foreach (float z in new[] { 5.0f, 6.6f })
            foreach (float ax in new[] { 1.7f, 2.8f, 3.9f, 5.0f, 6.1f })
                foreach (float sx in new[] { -1f, 1f })
                {
                    var p = new Vector3(sx * ax, TerraceH, z);
                    Put("cushion", structure, p, R(0, 360));
                    var seat = new GameObject($"Seat{seatN++}");
                    seat.transform.SetParent(seats, false);
                    seat.transform.position = p + Vector3.up * 0.155f;
                }

        // 石灯笼：夜里亮，带一盏小灯（数量有限：一块地面最多同时吃 8 盏灯）
        var lanternSpots = new[]
        {
            new Vector3(-2.2f, 0, -10.2f), new Vector3(2.2f, 0, -10.2f), new Vector3(-2.3f, 0, -6.4f), new Vector3(2.3f, 0, -6.4f),
            new Vector3(-8.1f, 0, 2.5f), new Vector3(8.1f, 0, 2.5f), new Vector3(-4.6f, 0, 1.4f), new Vector3(4.6f, 0, 1.4f),
            new Vector3(-12.4f, 0, 1.0f), new Vector3(13.2f, 0, 0.6f),
        };
        for (int i = 0; i < lanternSpots.Length; i++)
        {
            var p = lanternSpots[i];
            Solid(Put("lantern", structure, p, R(-8, 8), 1.25f), 0.38f, 2f, 0.8f);
            if (i < 6) lampLights.Add(PointLamp(structure, p + Vector3.up * 1.9f, 7f, 6.5f));
        }
        lampLights.Add(PointLamp(structure, HallAt + new Vector3(-3.4f, 3.4f, -4.6f), 9f, 5f));
        lampLights.Add(PointLamp(structure, HallAt + new Vector3(3.4f, 3.4f, -4.6f), 9f, 5f));

        // ── 树 ──
        void Tree(string model, float x, float z, float scale = 1f, float trunk = 0.3f)
        {
            float y = map.H(x, z);
            Solid(Put(model, structure, new Vector3(x, y - 0.03f, z), R(0, 360), scale * R(0.94f, 1.06f)), trunk, 3f, 0.9f);
        }
        // 大殿后面和两侧的松
        Tree("tree_pine_c", -11.5f, 18.6f, 1.2f); Tree("tree_pine_a", 12.4f, 19.6f, 1.15f); Tree("tree_pine_a", -5.5f, 23.5f, 1.2f); Tree("tree_pine_c", 5.8f, 23.8f, 1.25f);
        Tree("tree_pine_b", -13.6f, 12.5f, 1.1f); Tree("tree_pine_b", 14.2f, 13.4f, 1.1f); Tree("tree_pine_a", 0.4f, 24.8f, 1.3f); Tree("tree_pine_c", -9.2f, 22.4f);
        Tree("tree_pine_b", 9.8f, 23.0f); Tree("tree_round_a", -14.6f, 16.6f, 1.2f); Tree("tree_round_a", 15.0f, 17.2f, 1.15f);
        // 西边：红枫、银杏
        Tree("tree_maple_a", -13.4f, 6.6f, 1.15f, 0.25f); Tree("tree_maple_b", -11.4f, 9.4f, 1.1f, 0.2f); Tree("tree_ginkgo", -14.4f, 1.6f, 1.05f); Tree("tree_maple_b", -13.6f, -6.4f, 1.1f, 0.2f);
        Tree("tree_round_b", -12.6f, -10.2f); Tree("tree_maple_a", -10.6f, -12.0f, 0.95f, 0.25f);
        // 东边：池塘旁的花树
        Tree("tree_blossom", 12.6f, -2.6f, 1.2f, 0.25f); Tree("tree_blossom", 10.4f, -8.2f, 1.0f, 0.25f); Tree("tree_ginkgo", 14.6f, 2.8f, 1.1f); Tree("tree_round_b", 13.6f, -9.6f);
        Tree("tree_maple_b", 7.0f, -11.8f, 1.0f, 0.2f); Tree("tree_round_a", 15.2f, 9.4f, 1.1f);
        // 竹林：西北角一丛
        foreach (var (x, z, m) in new[] { (-9.6f, 13.4f, "bamboo_a"), (-11.2f, 14.6f, "bamboo_a"), (-10.2f, 15.6f, "bamboo_b"), (-8.6f, 15.0f, "bamboo_b"), (10.0f, 14.4f, "bamboo_a"), (11.4f, 15.4f, "bamboo_b") })
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
            if (Mathf.Abs(x - HallAt.x) < 9.2f + pad && Mathf.Abs(z - HallAt.z) < 5.6f + pad) return false;
            if (new Vector2(x - PavilionAt.x, z - PavilionAt.z).magnitude < 2.9f + pad) return false;
            return true;
        }
        string[] grassKinds = { "grass_a", "grass_a", "grass_b", "grass_b", "grass_c" };
        int grassCount = 0;
        for (int i = 0; i < 9000 && grassCount < 2300; i++)
        {
            float x = R(-19f, 19f), z = R(-15f, 27f);
            if (!Open(x, z, 0.25f)) continue;
            // 一丛一丛地长：用噪声决定哪里密
            float n = Mathf.PerlinNoise(x * 0.22f + 31f, z * 0.22f + 7f);
            if (n < 0.32f + 0.3f * (float)rng.NextDouble()) continue;
            Put(grassKinds[rng.Next(grassKinds.Length)], greens, new Vector3(x, map.H(x, z), z), R(0, 360), R(0.9f, 1.6f));
            grassCount++;
        }
        string[] flowerKinds = { "flower_w", "flower_y", "flower_p", "flower_v" };
        int flowerCount = 0;
        for (int c = 0; c < 70; c++)
        {
            float cx = R(-17f, 17f), cz = R(-14f, 25f);
            if (!Open(cx, cz, 0.6f)) continue;
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

        foreach (var r in structure.GetComponentsInChildren<MeshRenderer>())
            if (r.name == "glow") lampRenderers.Add(r);

        var tw = BuildEnvironment(world, structure, "Islet", lampRenderers, lampLights, new Vector3(0, 21f, -23f), new Vector3(0, 0.6f, -8f));
        IsletLighting(tw);

        // ── 运行时：能去的地点和走的路线 ──
        Vector3 incense = BurnerAt + Vector3.up * 1.36f;
        var ribbon = ToonMat("o_ribbon", m =>
        {
            m.SetFloat("_Legacy", 1f);
            m.SetFloat("_Sway", 1.6f);
            m.SetFloat("_Cull", 0f);
            m.SetFloat("_WetAmount", 0f);
            m.SetFloat("_SnowAmount", 0f);
            m.SetColor("_BaseColor", new Color(0.86f, 0.22f, 0.16f));
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
            new Spot { name = "tree", floor = new Vector3(-5.2f, 0, -5.6f), look = TreeAt + Vector3.up * 1.5f, pick = 3.2f },
            new Spot { name = "burner", floor = new Vector3(0, gy, -4.0f), look = BurnerAt + Vector3.up * 1.2f, pick = 1.4f },
            new Spot { name = "hall", floor = new Vector3(0, TerraceH, 8.3f), look = HallAt + Vector3.up * 3f, pick = 5f },
        };
        isletObs.Add(new Obstacle { center = PondAt, radius = PondR + 0.9f });
        game.obstacles = isletObs.ToArray();
        game.hub = new Vector3(0, gy, 2.3f);
        game.courtMinZ = GateZ - 0.5f;
        game.aislePoint = new Vector3(0, TerraceH, 5.8f);
        game.aisleDir = Vector3.right;
        game.seatExitNeg = new[] { new Vector3(-0.7f, TerraceH, 5.8f), new Vector3(-0.5f, TerraceH, 3.5f) };
        game.seatExitPos = new[] { new Vector3(0.7f, TerraceH, 5.8f), new Vector3(0.5f, TerraceH, 3.5f) };
        game.seatLook = HallAt + Vector3.up * 3f;
        game.seatStraight = 0.85f;
        game.nearRadius = 2.2f;
        ConfigureCrowd(game, new Vector3(0, 0.07f, DockAt.z - DockLen - DockPlat + 0.6f), new Vector3(0, gy, -13.4f),
            new[] { new Vector3(-5.0f, 0, -5.9f), new Vector3(0.7f, gy, -4.1f), new Vector3(-0.9f, gy, -4.0f), new Vector3(5.6f, 0, -2.6f), new Vector3(-1.1f, TerraceH, 8.2f),
                    new Vector3(1.2f, TerraceH, 8.3f), new Vector3(10.6f, 0, 3.4f), new Vector3(-10.0f, 0, 4.2f), new Vector3(-3.4f, 0, -13.4f) },
            new[] { TreeAt + Vector3.up, BurnerAt + Vector3.up, BurnerAt + Vector3.up, PondAt, HallAt + Vector3.up * 2f, HallAt + Vector3.up * 2f, PavilionAt + Vector3.up,
                    new Vector3(-11.6f, 1f, 3.6f), new Vector3(-3.4f, 0, -20f) },
            false);
        // 其他人进出座位区：从山门到石台，中间要绕开香炉（两边各走一侧）
        game.pilgrims.seatExitNeg = new[] { new Vector3(-0.7f, TerraceH, 5.8f), new Vector3(-0.5f, TerraceH, 3.5f), new Vector3(-2.4f, gy, 0.6f), new Vector3(-2.6f, gy, -3.6f), new Vector3(-0.8f, gy, -6.6f) };
        game.pilgrims.seatExitPos = new[] { new Vector3(0.7f, TerraceH, 5.8f), new Vector3(0.5f, TerraceH, 3.5f), new Vector3(2.4f, gy, 0.6f), new Vector3(2.6f, gy, -3.6f), new Vector3(0.8f, gy, -6.6f) };
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
        amb.leaves = falls.ToArray();
        amb.leafRate = 1.1f;

        // 萤火虫：夜里在草丛上方一明一灭
        {
            var mat = ParticleMaterial("toon_firefly", dot, new Color(3.2f, 3.4f, 1.2f, 1f), true, false);
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
