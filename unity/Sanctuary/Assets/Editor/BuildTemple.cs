using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using Yuanjing;

/// 山寺。布局（单位米，+z 是往里走的方向）：
///   z < -14      山门外
///   z -14 .. -10 山门两侧的回廊：坐的地方，有顶，面朝庭院和大殿
///   z -10 .. 8   庭院：许愿树、石灯笼、香炉
///   z 8 .. 20    大殿，坐在石台上
/// 只有建筑和氛围，没有神像。
public static partial class SanctuaryBuild
{
    const float CourtHalfW = 13f;

    [MenuItem("Yuanjing/3 生成山寺")]
    public static void BuildTemple()
    {
        mats.Clear();
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        ConfigureRendering();

        // 材质
        var paving = Mat("paving", "paving_large", 2.4f, new Color(0.80f, 0.79f, 0.76f), puddle: 1f);
        var pathStone = Mat("path_stone", "granite", 1.6f, new Color(0.74f, 0.73f, 0.71f), rough: 1.1f, puddle: 0.6f);
        var platformStone = Mat("platform_stone", "sandstone", 2.6f, new Color(0.72f, 0.72f, 0.71f), rough: 1.05f);
        var lacquer = Mat("lacquer", "wood_cedar", 1.6f, new Color(0.58f, 0.17f, 0.12f), rough: 0.6f, wet: 0.5f);
        var beamWood = Mat("beam_wood", "wood_cedar", 1.4f, new Color(0.62f, 0.34f, 0.24f), rough: 0.85f, wet: 0.5f);
        var rafterWood = Mat("rafter_wood", "wood_cedar", 1.6f, new Color(0.56f, 0.38f, 0.28f), rough: 0.9f, wet: 0.2f, snow: 0f);
        var floorWood = Mat("floor_wood", "wood_floor", 1.8f, new Color(0.66f, 0.58f, 0.50f), rough: 0.8f, wet: 0.6f);
        var plaster = Mat("plaster", "plaster", 3.0f, new Color(0.93f, 0.91f, 0.86f));
        var roofTile = Mat("roof_tile", "roof_grey", 1.5f, new Color(0.46f, 0.49f, 0.53f), rough: 0.85f);
        var ridgeTile = Mat("ridge_tile", "roof_grey", 1.2f, new Color(0.33f, 0.36f, 0.40f), rough: 0.8f);
        var lanternStone = Mat("lantern_stone", "moss_rock", 1.2f, new Color(0.72f, 0.72f, 0.69f));
        var bronze = Mat("bronze", "bronze", 0.9f, new Color(0.62f, 0.55f, 0.40f), rough: 0.7f, metallic: 1f);
        var bark = Mat("bark", "bark", 1.4f, new Color(0.80f, 0.74f, 0.68f));
        var moss = Mat("moss", "moss_rock", 2.0f, new Color(0.62f, 0.74f, 0.50f));
        var gravel = Mat("gravel", "gravel", 2.0f, new Color(0.86f, 0.84f, 0.80f), puddle: 0.4f);
        var grass = Mat("grass", "forest_floor", 3.0f, new Color(0.62f, 0.70f, 0.48f));
        var mountain = Mat("mountain", "moss_rock", 22f, new Color(0.36f, 0.46f, 0.36f), rough: 1.2f, wet: 0.3f);
        var cushion = Mat("cushion", "linen", 0.5f, new Color(0.68f, 0.50f, 0.26f), wet: 0f, snow: 0f);
        var paperGlow = Emissive("paper_glow", new Color(0.90f, 0.80f, 0.62f));
        var lattice = Emissive("lattice", Color.white, LatticeTexture());
        lattice.SetTexture("_EmissionMap", LatticeEmission());
        var leafTex = LeafAtlas(new Color(0.085f, 0.16f, 0.06f), new Color(0.17f, 0.25f, 0.085f));
        var leavesMat = Mat("leaves", null, 1f, Color.white, rough: 0.7f, wet: 0.15f, snow: 0.6f);
        leavesMat.SetTexture("_BaseMap", leafTex);
        leavesMat.SetTextureScale("_BaseMap", Vector2.one);
        leavesMat.SetFloat("_AlphaClip", 1f);
        leavesMat.SetFloat("_Cutoff", 0.45f);
        leavesMat.SetFloat("_Cull", 0f);
        leavesMat.SetFloat("_Sway", 1f);
        leavesMat.EnableKeyword("_ALPHATEST_ON");
        leavesMat.renderQueue = (int)RenderQueue.AlphaTest;
        var ribbonMat = Mat("ribbon", "linen", 0.3f, new Color(0.78f, 0.07f, 0.05f), rough: 0.9f, wet: 0.4f, snow: 0f);
        ribbonMat.SetFloat("_Cull", 0f);
        ribbonMat.SetFloat("_Sway", 1f);

        var world = Group("World");
        var structure = Group("Structure", world);
        var lampRenderers = new List<Renderer>();
        var lampLights = new List<Light>();

        // ── 地面 ──
        var g = new MeshBuilder();
        g.Quad(new Vector3(-CourtHalfW, 0, -10), new Vector3(CourtHalfW, 0, -10), new Vector3(CourtHalfW, 0, 8), new Vector3(-CourtHalfW, 0, 8), Vector3.up);
        Add("Courtyard", g, paving, structure, false);
        g = new MeshBuilder();
        g.Box(new Vector3(0, 0.02f, -1), new Vector3(3.0f, 0.04f, 18f));
        for (float z = -9.4f; z < 7.8f; z += 1.5f) g.Box(new Vector3(0, 0.03f, z), new Vector3(3.3f, 0.06f, 0.12f));
        Add("Path", g, pathStone, structure, false);
        g = new MeshBuilder();
        g.Quad(new Vector3(-140, -0.05f, -140), new Vector3(140, -0.05f, -140), new Vector3(140, -0.05f, 140), new Vector3(-140, -0.05f, 140), Vector3.up);
        Add("Outside", g, grass, structure, false);

        BuildHall(structure, platformStone, lacquer, beamWood, rafterWood, plaster, roofTile, ridgeTile, lattice, floorWood, lampRenderers);
        BuildGallery(structure, floorWood, beamWood, beamWood, rafterWood, plaster, roofTile, ridgeTile, platformStone, cushion);
        BuildWalls(structure, plaster, roofTile, platformStone);

        // ── 石灯笼：路两边各三盏 ──
        var stone = new MeshBuilder();
        var glow = new MeshBuilder();
        var lanternSpots = new List<Vector3>();
        foreach (float z in new[] { -6.5f, -1.0f, 4.5f })
            foreach (float x in new[] { -3.3f, 3.3f })
                lanternSpots.Add(StoneLantern(stone, glow, new Vector3(x, 0, z), 1.05f));
        Add("Lanterns", stone, lanternStone, structure);
        lampRenderers.Add(Add("LanternGlow", glow, paperGlow, structure, false).GetComponent<Renderer>());
        foreach (var p in lanternSpots)
        {
            var lg = new GameObject("LanternLight");
            lg.transform.SetParent(structure, false);
            lg.transform.position = p;
            var l = lg.AddComponent<Light>();
            l.type = LightType.Point;
            l.color = new Color(1f, 0.66f, 0.34f);
            l.range = 7f;
            l.intensity = 9f;
            l.shadows = LightShadows.None;
            lampLights.Add(l);
        }

        // ── 香炉：三足铜炉，立在石座上 ──
        var bz = new MeshBuilder();
        var baseStone = new MeshBuilder();
        Vector3 burner = new Vector3(0, 0, 4.2f);
        baseStone.Lathe(burner, new[] { new Vector2(0.95f, 0f), new Vector2(0.95f, 0.14f), new Vector2(0.80f, 0.20f), new Vector2(0.80f, 0.42f), new Vector2(0.90f, 0.48f), new Vector2(0.90f, 0.56f) }, 8, false, true);
        bz.Lathe(burner + Vector3.up * 0.86f, new[]
        {
            new Vector2(0.20f, 0f), new Vector2(0.50f, 0.10f), new Vector2(0.66f, 0.32f), new Vector2(0.68f, 0.52f), new Vector2(0.60f, 0.62f),
            new Vector2(0.66f, 0.70f), new Vector2(0.72f, 0.72f), new Vector2(0.72f, 0.76f), new Vector2(0.60f, 0.76f), new Vector2(0.58f, 0.66f),
        }, 28);
        for (int i = 0; i < 3; i++)
        {
            float a = i * Mathf.PI * 2f / 3f + 0.5f;
            Vector3 foot = burner + new Vector3(Mathf.Cos(a) * 0.42f, 0.56f, Mathf.Sin(a) * 0.42f);
            bz.Lathe(foot, new[] { new Vector2(0.10f, 0f), new Vector2(0.07f, 0.12f), new Vector2(0.09f, 0.26f), new Vector2(0.13f, 0.40f) }, 10, true, false);
        }
        foreach (float sx in new[] { -1f, 1f })
        {
            var ear = new List<Vector3>();
            for (int i = 0; i <= 8; i++)
            {
                float t = i / 8f * Mathf.PI;
                ear.Add(burner + new Vector3(sx * (0.70f + 0.12f * Mathf.Sin(t)), 1.56f + 0.20f * (1f - Mathf.Cos(t)), 0));
            }
            bz.Tube(ear, t => 0.035f, 8, true);
        }
        Add("Burner", bz, bronze, structure);
        Add("BurnerBase", baseStone, platformStone, structure);
        var ash = new MeshBuilder();
        ash.Disc(burner + Vector3.up * 1.52f, 0.58f, 24, Vector3.up);
        Add("BurnerAsh", ash, gravel, structure, false);

        // ── 许愿树：庭院左侧的一棵大樟树，围着石台，低处的枝条挂红布条 ──
        Vector3 treeAt = new Vector3(-5.6f, 0, -1.2f);
        var barkMesh = new MeshBuilder();
        var leafMesh = new MeshBuilder();
        var uvs = new[] { new Rect(0, 0, 0.5f, 0.5f), new Rect(0.5f, 0, 0.5f, 0.5f), new Rect(0, 0.5f, 0.5f, 0.5f), new Rect(0.5f, 0.5f, 0.5f, 0.5f) };
        var hang = Tree(barkMesh, leafMesh, treeAt + Vector3.up * 0.35f, 9.5f, 4.6f, 7, uvs);
        Add("TreeBark", barkMesh, bark, structure);
        Add("Leaves", leafMesh, leavesMat, structure);

        // ── 红枫：庭院几个角上，叶子红橙相间 ──
        var mapleTex = LeafAtlas(new Color(0.62f, 0.10f, 0.05f), new Color(0.86f, 0.36f, 0.08f), "gen_maple_color");
        var mapleMat = Mat("maple_leaves", null, 1f, Color.white, rough: 0.7f, wet: 0.15f, snow: 0.6f);
        mapleMat.SetTexture("_BaseMap", mapleTex);
        mapleMat.SetTextureScale("_BaseMap", Vector2.one);
        mapleMat.SetFloat("_AlphaClip", 1f);
        mapleMat.SetFloat("_Cutoff", 0.45f);
        mapleMat.SetFloat("_Cull", 0f);
        mapleMat.SetFloat("_Sway", 1f);
        mapleMat.EnableKeyword("_ALPHATEST_ON");
        mapleMat.renderQueue = (int)RenderQueue.AlphaTest;
        var maples = new[] { new Vector3(10.4f, 0, -7.4f), new Vector3(-10.6f, 0, 5.6f), new Vector3(10.8f, 0, 2.2f) };
        var mapleBark = new MeshBuilder();
        var mapleLeaves = new MeshBuilder();
        for (int i = 0; i < maples.Length; i++) Tree(mapleBark, mapleLeaves, maples[i], 5.6f + i * 0.5f, 2.6f, 41 + i * 7, uvs);
        Add("MapleBark", mapleBark, bark, structure);
        Add("MapleLeaves", mapleLeaves, mapleMat, structure);
        var mapleBed = new MeshBuilder();
        foreach (var m in maples) mapleBed.Lathe(m, new[] { new Vector2(1.05f, 0f), new Vector2(1.05f, 0.22f), new Vector2(0.95f, 0.26f) }, 8, false, false);
        Add("MapleBeds", mapleBed, platformStone, structure);
        var mapleMoss = new MeshBuilder();
        foreach (var m in maples) mapleMoss.Disc(m + Vector3.up * 0.24f, 0.96f, 8, Vector3.up);
        Add("MapleMoss", mapleMoss, moss, structure, false);
        var bed = new MeshBuilder();
        bed.Lathe(treeAt, new[] { new Vector2(1.9f, 0f), new Vector2(1.9f, 0.34f), new Vector2(1.72f, 0.40f) }, 8, false, false);
        Add("TreeBed", bed, platformStone, structure);
        var bedTop = new MeshBuilder();
        bedTop.Disc(treeAt + Vector3.up * 0.38f, 1.74f, 8, Vector3.up);
        Add("TreeBedMoss", bedTop, moss, structure, false);

        // 已经挂着的红布条（示例）。真实用户挂的由 Offerings.cs 在运行时加。
        var rib = new MeshBuilder();
        var rngR = new Rng(3);
        var slots = Group("RibbonSlots", structure);
        int slotIndex = 0;
        foreach (var hp in hang)
        {
            for (int k = 0; k < 3; k++)
            {
                Vector3 top = hp + new Vector3(rngR.Range(-0.5f, 0.5f), rngR.Range(-0.25f, 0.1f), rngR.Range(-0.5f, 0.5f));
                if (rngR.Next() < 0.5f)
                {
                    float len = rngR.Range(0.55f, 0.95f);
                    float ang = rngR.Range(0, Mathf.PI);
                    Vector3 right = new Vector3(Mathf.Cos(ang), 0, Mathf.Sin(ang)) * 0.035f;
                    rib.Card(top + Vector3.down * len * 0.5f, right, Vector3.up * len * 0.5f, new Rect(0, 0, 0.2f, 2f), 1f, 0f);
                }
                else
                {
                    var slot = new GameObject($"Slot{slotIndex++}");
                    slot.transform.SetParent(slots, false);
                    slot.transform.position = top;
                }
            }
        }
        Add("Ribbons", rib, ribbonMat, structure, false);

        BuildMountains(world, mountain, 0f);

        // ── 花草：树池里、灯笼脚下、院墙根、山门外 ──
        plantKinds.Clear();
        var grassA = Plant("grass_medium_02", new Color(0.80f, 0.86f, 0.70f));
        var grassB = Plant("grass_medium_02", new Color(0.86f, 0.90f, 0.78f));
        var shrub = Plant("shrub_03", new Color(0.82f, 0.88f, 0.78f));
        var fern = Plant("fern_02", new Color(0.86f, 0.92f, 0.82f));
        var flower = Plant("celandine_01", Color.white);
        var patches = new List<PlantPatch>
        {
            new PlantPatch { kind = fern, center = treeAt + Vector3.up * 0.38f, size = new Vector2(1.6f, 0), ring = 0.6f, count = 9, scale = new Vector2(0.6f, 0.9f) },
            new PlantPatch { kind = flower, center = treeAt + Vector3.up * 0.38f, size = new Vector2(1.6f, 0), ring = 0.5f, count = 14, scale = new Vector2(0.8f, 1.1f) },
            new PlantPatch { kind = grassB, center = treeAt + Vector3.up * 0.38f, size = new Vector2(1.65f, 0), ring = 0.9f, count = 40, scale = new Vector2(1.4f, 2.0f) },
        };
        foreach (var m in maples)
        {
            patches.Add(new PlantPatch { kind = grassB, center = m + Vector3.up * 0.24f, size = new Vector2(0.9f, 0), ring = 0.3f, count = 22, scale = new Vector2(1.3f, 1.9f) });
            patches.Add(new PlantPatch { kind = flower, center = m + Vector3.up * 0.24f, size = new Vector2(0.9f, 0), ring = 0.2f, count = 5 });
        }
        // 院墙根：两侧一长条灌木和草
        foreach (float sx in new[] { -1f, 1f })
        {
            patches.Add(new PlantPatch { kind = shrub, center = new Vector3(sx * 12.5f, 0, -1f), size = new Vector2(0.9f, 17f), count = 60, scale = new Vector2(2.2f, 3.2f) });
            patches.Add(new PlantPatch { kind = grassA, center = new Vector3(sx * 12.1f, 0, -1f), size = new Vector2(1.4f, 17f), count = 160, scale = new Vector2(1.5f, 2.4f) });
            patches.Add(new PlantPatch { kind = fern, center = new Vector3(sx * 12.4f, 0, -1f), size = new Vector2(0.9f, 17f), count = 22, scale = new Vector2(0.8f, 1.2f) });
        }
        // 石灯笼脚下一小撮
        foreach (var p in lanternSpots)
            patches.Add(new PlantPatch { kind = grassB, center = new Vector3(p.x, 0, p.z), size = new Vector2(0.8f, 0), ring = 0.45f, count = 10, scale = new Vector2(1.0f, 1.5f) });
        // 山门外的草地
        foreach (float sx in new[] { -1f, 1f })
        {
            // 山门外两边的草地（中间留出石路）
            patches.Add(new PlantPatch { kind = grassA, center = new Vector3(sx * 8f, -0.05f, -19.5f), size = new Vector2(12f, 7f), count = 700, scale = new Vector2(1.6f, 2.6f) });
            patches.Add(new PlantPatch { kind = flower, center = new Vector3(sx * 8f, -0.05f, -19.5f), size = new Vector2(12f, 7f), count = 90, scale = new Vector2(1.0f, 1.4f) });
            patches.Add(new PlantPatch { kind = shrub, center = new Vector3(sx * 8f, -0.05f, -22.6f), size = new Vector2(12f, 1.4f), count = 70, scale = new Vector2(2.4f, 3.6f) });
        }
        // 大殿台基两侧
        foreach (float sx in new[] { -1f, 1f })
            patches.Add(new PlantPatch { kind = shrub, center = new Vector3(sx * 10.6f, 0, 8.6f), size = new Vector2(2.2f, 1.4f), count = 24, scale = new Vector2(2.2f, 3.2f) });
        BuildPlantPatches(structure, patches, 77);

        BuildEnvironment(world, structure, "Temple", lampRenderers, lampLights, new Vector3(0, 1.6f, -19f), new Vector3(0, 2.6f, 10f));

        // ── 运行时：能去的地点和走的路线 ──
        var seatsRoot = structure.Find("Gallery/Seats");
        var game = BuildRuntime("amb_music_temple", "sfx_bell_temple", seatsRoot, slots, ribbonMat, burner + Vector3.up * 1.53f, null, 0);
        Vector3 hallLook = new Vector3(0, 3.6f, 11f);
        game.spots = new[]
        {
            new Spot { name = "gate", floor = new Vector3(0, 0, -18.5f), look = new Vector3(0, 2.8f, 10f), pick = 0 },
            new Spot { name = "court", floor = new Vector3(0, 0.03f, -8.6f), look = hallLook, pick = 0.01f },
            new Spot { name = "tree", floor = new Vector3(-2.7f, 0, -3.7f), look = treeAt + Vector3.up * 3.4f, pick = 3.6f },
            new Spot { name = "burner", floor = new Vector3(0, 0.03f, 2.2f), look = burner + Vector3.up * 1.7f, pick = 1.3f },
            new Spot { name = "hall", floor = new Vector3(0, 0.03f, 6.3f), look = new Vector3(0, 4.3f, 10.5f), pick = 5f },
        };
        var obs = new List<Obstacle>
        {
            new Obstacle { center = burner, radius = 1.5f },
            new Obstacle { center = treeAt, radius = 2.5f },
        };
        foreach (var m in maples) obs.Add(new Obstacle { center = m, radius = 1.4f });
        foreach (var p in lanternSpots) obs.Add(new Obstacle { center = new Vector3(p.x, 0, p.z), radius = 0.75f });
        game.obstacles = obs.ToArray();
        game.hub = new Vector3(0, 0.03f, -9.2f);
        game.aislePoint = new Vector3(0, 0.28f, -12.0f);
        game.aisleDir = Vector3.right;
        game.seatExitNeg = new[] { new Vector3(-2.05f, 0.28f, -12.0f), new Vector3(0, 0.06f, -12.0f) };
        game.seatExitPos = new[] { new Vector3(2.05f, 0.28f, -12.0f), new Vector3(0, 0.06f, -12.0f) };
        game.seatLook = hallLook;
        ConfigureCrowd(game, new Vector3(0, 0, -20f), new Vector3(0, 0.03f, -12.4f),
            new[] { new Vector3(-2.9f, 0.03f, -3.6f), new Vector3(0.8f, 0.03f, 2.1f), new Vector3(-1.2f, 0.03f, 2.3f), new Vector3(1.8f, 0.03f, -6.0f), new Vector3(-1.8f, 0.03f, 6.4f), new Vector3(4.8f, 0.03f, 1.0f) },
            new[] { treeAt + Vector3.up * 3f, burner + Vector3.up, burner + Vector3.up, new Vector3(0, 3.5f, 11f), new Vector3(0, 3.5f, 11f), burner + Vector3.up },
            false);
        EditorSceneManager.SaveScene(scene, "Assets/Scenes/Temple.unity");
        AssetDatabase.SaveAssets();
        Debug.Log("[yuanjing] 山寺已生成");
    }

    /// 大殿：石台、五开间的木柱、斗拱、格扇门、四坡曲面屋顶
    static void BuildHall(Transform parent, Material stoneMat, Material lacquer, Material beam, Material rafter, Material plaster, Material tile, Material ridge, Material lattice, Material floor, List<Renderer> lamps)
    {
        var root = Group("Hall", parent);
        const float baseY = 0.9f, colH = 4.4f, frontZ = 9.0f, wallZ = 11.4f, backZ = 19.2f;
        float[] xs = { -7.5f, -4.5f, -1.5f, 1.5f, 4.5f, 7.5f };

        var st = new MeshBuilder();
        st.Box(new Vector3(0, baseY * 0.5f, 14.2f), new Vector3(20f, baseY, 12.6f));
        st.Box(new Vector3(0, baseY - 0.06f, 14.2f), new Vector3(20.4f, 0.12f, 13.0f));
        for (int i = 0; i < 5; i++) st.Box(new Vector3(0, baseY * (4 - i) / 5f + baseY / 10f - baseY / 10f + 0.09f, 7.6f - 0.34f * i + 0.34f * 2), new Vector3(5.2f, 0.18f, 0.36f));
        // 台阶两边的垂带石
        foreach (float sx in new[] { -1f, 1f }) st.Box(new Vector3(sx * 2.85f, 0.42f, 7.25f), new Vector3(0.4f, 0.84f, 1.9f));

        var wood = new MeshBuilder();
        var bases = new MeshBuilder();
        var beams = new MeshBuilder();
        foreach (float z in new[] { frontZ, wallZ })
            foreach (float x in xs)
            {
                Column(wood, bases, new Vector3(x, baseY, z), 0.27f, colH);
                Bracket(beams, new Vector3(x, baseY + colH, z), 0.42f);
            }
        foreach (float x in new[] { xs[0], xs[5] })
            foreach (float z in new[] { 14.0f, 16.6f, backZ })
            {
                Column(wood, bases, new Vector3(x, baseY, z), 0.27f, colH);
                Bracket(beams, new Vector3(x, baseY + colH, z), 0.42f);
            }
        // 额枋：柱头之间的横梁，上下两道
        foreach (float z in new[] { frontZ, wallZ, backZ })
        {
            beams.Box(new Vector3(0, baseY + colH - 0.30f, z), new Vector3(15.6f, 0.42f, 0.26f));
            beams.Box(new Vector3(0, baseY + colH - 0.82f, z), new Vector3(15.2f, 0.22f, 0.18f));
            beams.Box(new Vector3(0, baseY + colH + 0.56f, z), new Vector3(16.6f, 0.26f, 0.34f));
        }
        foreach (float x in xs) beams.Box(new Vector3(x, baseY + colH - 0.30f, (frontZ + wallZ) * 0.5f), new Vector3(0.24f, 0.38f, wallZ - frontZ));
        foreach (float x in new[] { xs[0], xs[5] }) beams.Box(new Vector3(x, baseY + colH - 0.30f, (wallZ + backZ) * 0.5f), new Vector3(0.26f, 0.42f, backZ - wallZ));

        // 格扇门窗：中间三间是落地的格扇，两边两间是槛墙上开窗
        var lat = new MeshBuilder();
        var wall = new MeshBuilder();
        for (int i = 0; i < 5; i++)
        {
            float x0 = xs[i] + 0.3f, x1 = xs[i + 1] - 0.3f;
            bool door = i >= 1 && i <= 3;
            float y0 = door ? baseY + 0.12f : baseY + 1.25f, y1 = baseY + colH - 0.98f;
            int leaves = door ? 4 : 3;
            float w = (x1 - x0) / leaves;
            for (int k = 0; k < leaves; k++)
                lat.QuadUV(new Vector3(x0 + k * w + 0.02f, y0, wallZ - 0.05f), new Vector3(x0 + (k + 1) * w - 0.02f, y0, wallZ - 0.05f),
                    new Vector3(x0 + (k + 1) * w - 0.02f, y1, wallZ - 0.05f), new Vector3(x0 + k * w + 0.02f, y1, wallZ - 0.05f), Vector3.back,
                    door ? new Rect(0, 0, 1, 1) : new Rect(0, 0.36f, 1, 0.64f));
            if (!door) wall.Box(new Vector3((x0 + x1) * 0.5f, baseY + 0.66f, wallZ), new Vector3(x1 - x0 + 0.1f, 1.2f, 0.28f));
            beams.Box(new Vector3((x0 + x1) * 0.5f, y0 - 0.05f, wallZ - 0.02f), new Vector3(x1 - x0 + 0.12f, 0.12f, 0.16f));
        }
        // 两山和后墙
        foreach (float x in new[] { xs[0], xs[5] }) wall.Box(new Vector3(x, baseY + colH * 0.5f - 0.3f, (wallZ + backZ) * 0.5f), new Vector3(0.26f, colH - 0.7f, backZ - wallZ - 0.5f));
        wall.Box(new Vector3(0, baseY + colH * 0.5f - 0.3f, backZ), new Vector3(15f, colH - 0.7f, 0.26f));

        // 匾额：门楣上方一块深色的横匾，描一圈金边
        var board = new MeshBuilder();
        board.Box(new Vector3(0, baseY + colH + 0.25f, frontZ - 0.28f), new Vector3(2.6f, 0.95f, 0.1f));
        var gold = new MeshBuilder();
        foreach (float sy in new[] { -1f, 1f }) gold.Box(new Vector3(0, baseY + colH + 0.25f + sy * 0.45f, frontZ - 0.34f), new Vector3(2.7f, 0.06f, 0.04f));
        foreach (float sx in new[] { -1f, 1f }) gold.Box(new Vector3(sx * 1.32f, baseY + colH + 0.25f, frontZ - 0.34f), new Vector3(0.06f, 0.96f, 0.04f));

        Add("Platform", st, stoneMat, root);
        Add("Columns", wood, lacquer, root);
        Add("ColumnBases", bases, stoneMat, root);
        Add("Beams", beams, beam, root);
        Add("Walls", wall, plaster, root);
        lamps.Add(Add("Lattice", lat, lattice, root, false).GetComponent<Renderer>());
        Add("Board", board, Mat("board", "wood_dark", 1.2f, new Color(0.10f, 0.07f, 0.06f), rough: 0.5f, wet: 0.2f), root);
        // 匾上的金字
        var words = new MeshBuilder();
        words.QuadUV(new Vector3(-1.12f, baseY + colH - 0.14f, frontZ - 0.335f), new Vector3(1.12f, baseY + colH - 0.14f, frontZ - 0.335f),
            new Vector3(1.12f, baseY + colH + 0.64f, frontZ - 0.335f), new Vector3(-1.12f, baseY + colH + 0.64f, frontZ - 0.335f), Vector3.back, new Rect(0, 0, 1, 1));
        var wordMat = Mat("board_words", null, 1f, new Color(0.95f, 0.74f, 0.32f), rough: 0.4f, metallic: 1f, wet: 0f, snow: 0f);
        wordMat.SetTexture("_BaseMap", Tex("gen_plaque_color"));
        wordMat.SetTextureScale("_BaseMap", Vector2.one);
        wordMat.SetFloat("_AlphaClip", 1f);
        wordMat.SetFloat("_Cutoff", 0.5f);
        wordMat.EnableKeyword("_ALPHATEST_ON");
        wordMat.renderQueue = (int)RenderQueue.AlphaTest;
        Add("BoardWords", words, wordMat, root, false);
        Add("BoardGold", gold, Mat("gold", null, 1f, new Color(0.92f, 0.70f, 0.28f), rough: 0.35f, metallic: 1f, wet: 0f, snow: 0f), root);
        var fl = new MeshBuilder();
        fl.Quad(new Vector3(-9.6f, baseY + 0.005f, frontZ - 1.2f), new Vector3(9.6f, baseY + 0.005f, frontZ - 1.2f), new Vector3(9.6f, baseY + 0.005f, wallZ), new Vector3(-9.6f, baseY + 0.005f, wallZ), Vector3.up);
        Add("Porch", fl, floor, root, false);

        Roof(root, "Roof", new RoofShape { center = new Vector3(0, baseY + colH + 0.78f, 14.2f), W = 21.4f, D = 14.4f, L = 10.5f, H = 4.6f, lift = 1.15f, curve = 1.7f }, tile, ridge, rafter, 3.4f);
    }

    /// 山门两侧的回廊：木地台、两排方柱、两坡顶。蒲团摆在这里，面朝庭院。
    static void BuildGallery(Transform parent, Material floor, Material lacquer, Material beam, Material rafter, Material plaster, Material tile, Material ridge, Material stoneMat, Material cushion)
    {
        var root = Group("Gallery", parent);
        const float y0 = 0.28f, colH = 3.0f, zFront = -10.3f, zBack = -13.9f;
        float[] xs = { -12.6f, -9.9f, -7.2f, -4.5f, -1.8f, 1.8f, 4.5f, 7.2f, 9.9f, 12.6f };

        var fl = new MeshBuilder();
        foreach (float sx in new[] { -1f, 1f })
        {
            fl.Box(new Vector3(sx * 7.35f, y0 * 0.5f, -12.1f), new Vector3(11.1f, y0, 4.2f));
            fl.Box(new Vector3(sx * 7.35f, y0 * 0.5f - 0.02f, -9.86f), new Vector3(10.6f, y0 * 0.5f, 0.36f)); // 一步台阶
        }
        Add("Floor", fl, floor, root);
        var gate = new MeshBuilder();
        gate.Box(new Vector3(0, 0.03f, -12.1f), new Vector3(3.6f, 0.06f, 4.4f));
        gate.Box(new Vector3(0, 0.10f, -13.9f), new Vector3(3.4f, 0.20f, 0.3f)); // 门槛
        Add("GateFloor", gate, stoneMat, root);

        var wood = new MeshBuilder();
        var beams = new MeshBuilder();
        foreach (float z in new[] { zFront, zBack })
            foreach (float x in xs)
            {
                wood.Box(new Vector3(x, y0 + colH * 0.5f, z), new Vector3(0.24f, colH, 0.24f));
                beams.Box(new Vector3(x, y0 + colH - 0.2f, z), new Vector3(0.6f, 0.12f, 0.34f));
            }
        foreach (float z in new[] { zFront, zBack, -12.1f })
            beams.Box(new Vector3(0, y0 + colH + (z == -12.1f ? 1.05f : 0f), z), new Vector3(26.2f, 0.26f, 0.2f));
        foreach (float x in xs)
        {
            beams.Box(new Vector3(x, y0 + colH, -12.1f), new Vector3(0.18f, 0.26f, 3.8f));
            beams.Box(new Vector3(x, y0 + colH + 0.52f, -12.1f), new Vector3(0.16f, 0.9f, 0.16f)); // 脊瓜柱
        }
        // 廊前的矮栏杆（门洞那一段不设）
        foreach (float sx in new[] { -1f, 1f })
        {
            beams.Box(new Vector3(sx * 7.2f, y0 + 0.50f, zFront), new Vector3(10.6f, 0.07f, 0.08f));
            beams.Box(new Vector3(sx * 7.2f, y0 + 0.16f, zFront), new Vector3(10.6f, 0.05f, 0.06f));
        }
        Add("Columns", wood, lacquer, root);
        Add("Beams", beams, beam, root);

        // 后墙：粉墙，中间留山门
        var wall = new MeshBuilder();
        foreach (float sx in new[] { -1f, 1f }) wall.Box(new Vector3(sx * 7.3f, y0 + colH * 0.5f, zBack - 0.05f), new Vector3(11.0f, colH, 0.22f));
        wall.Box(new Vector3(0, y0 + colH - 0.25f, zBack - 0.05f), new Vector3(3.6f, 0.5f, 0.22f));
        Add("BackWall", wall, plaster, root);

        Roof(root, "Roof", new RoofShape { center = new Vector3(0, y0 + colH + 0.16f, -12.1f), W = 27.6f, D = 6.2f, L = 27.6f, H = 1.75f, lift = 0.0f, curve = 1.35f }, tile, ridge, rafter, 3.1f);

        var drip = new GameObject("DripLine");
        drip.transform.SetParent(root, false);
        drip.transform.position = new Vector3(0, y0 + colH + 0.10f, -12.1f + 3.1f + 0.16f);
        drip.transform.localScale = new Vector3(27f, 1, 1);

        // 蒲团：两排，每边六个。Seats.cs 在运行时按名字找到它们。
        var cu = new MeshBuilder();
        var seats = Group("Seats", root);
        int n = 0;
        // 每两根柱子之间摆两个，不会有柱子正挡在眼前
        float[] seatX = { 2.55f, 3.75f, 5.25f, 6.45f, 7.95f, 9.15f, 10.65f, 11.85f };
        foreach (float z in new[] { -11.3f, -12.7f })
            foreach (float sx in new[] { -1f, 1f })
                foreach (float ax in seatX)
                {
                    Vector3 p = new Vector3(sx * ax, y0, z);
                    cu.Lathe(p, new[] { new Vector2(0.001f, 0f), new Vector2(0.34f, 0f), new Vector2(0.40f, 0.05f), new Vector2(0.40f, 0.10f), new Vector2(0.34f, 0.15f), new Vector2(0.001f, 0.16f) }, 20);
                    var seat = new GameObject($"Seat{n++}");
                    seat.transform.SetParent(seats, false);
                    seat.transform.position = p + Vector3.up * 0.16f;
                }
        Add("Cushions", cu, cushion, root);
    }

    /// 两侧的院墙：粉墙黛瓦
    static void BuildWalls(Transform parent, Material plaster, Material tile, Material stoneMat)
    {
        var root = Group("Walls", parent);
        var wall = new MeshBuilder();
        var cap = new MeshBuilder();
        var foot = new MeshBuilder();
        foreach (float sx in new[] { -1f, 1f })
        {
            float x = sx * (CourtHalfW + 0.2f);
            wall.Box(new Vector3(x, 1.5f, 3f), new Vector3(0.36f, 2.5f, 36f));
            foot.Box(new Vector3(x, 0.2f, 3f), new Vector3(0.5f, 0.4f, 36.2f));
            // 墙帽：一个小小的两坡瓦顶
            cap.Quad(new Vector3(x - 0.42f, 2.72f, -15f), new Vector3(x, 3.02f, -15f), new Vector3(x, 3.02f, 21f), new Vector3(x - 0.42f, 2.72f, 21f), new Vector3(-1, 1, 0));
            cap.Quad(new Vector3(x + 0.42f, 2.72f, -15f), new Vector3(x, 3.02f, -15f), new Vector3(x, 3.02f, 21f), new Vector3(x + 0.42f, 2.72f, 21f), new Vector3(1, 1, 0));
            cap.Tube(new[] { new Vector3(x, 3.05f, -15f), new Vector3(x, 3.05f, 21f) }, t => 0.07f, 8, true);
        }
        Add("Wall", wall, plaster, root);
        Add("WallFoot", foot, stoneMat, root);
        Add("WallCap", cap, tile, root);
    }

    /// 两座殿共用的环境：太阳、天空、后期、雨雪、镜头、总控脚本、遮挡高度图
    static TimeWeather BuildEnvironment(Transform world, Transform structure, string sceneName, List<Renderer> lampRenderers, List<Light> lampLights, Vector3 camPos, Vector3 camLook)
    {
        var sunGo = new GameObject("Sun");
        var sun = sunGo.AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.shadows = LightShadows.Soft;
        sun.shadowStrength = 1f;
        // 补光：模拟阳光照到地面再弹上来的那一层光，檐下和廊子里才不会死黑
        var bounce = new GameObject("Bounce").AddComponent<Light>();
        bounce.type = LightType.Directional;
        bounce.shadows = LightShadows.None;

        System.IO.Directory.CreateDirectory(MatDir);
        var skyMat = AssetDatabase.LoadAssetAtPath<Material>($"{MatDir}/sky.mat");
        if (skyMat == null)
        {
            skyMat = new Material(Shader.Find("Yuanjing/Sky"));
            AssetDatabase.CreateAsset(skyMat, $"{MatDir}/sky.mat");
        }
        RenderSettings.skybox = skyMat;
        RenderSettings.sun = sun;
        RenderSettings.defaultReflectionMode = DefaultReflectionMode.Skybox;

        var camGo = new GameObject("Main Camera") { tag = "MainCamera" };
        var cam = camGo.AddComponent<Camera>();
        cam.transform.position = camPos;
        cam.transform.LookAt(camLook);
        // 竖屏手机上视角要开得大一些，不然像从望远镜里看
        cam.fieldOfView = 72f;
        cam.nearClipPlane = 0.1f;
        cam.farClipPlane = 600f;
        cam.allowHDR = true;
        cam.allowMSAA = true;
        var camData = camGo.AddComponent<UniversalAdditionalCameraData>();
        camData.renderPostProcessing = true;
        camData.renderShadows = true;
        camData.antialiasing = AntialiasingMode.SubpixelMorphologicalAntiAliasing;
        camData.antialiasingQuality = AntialiasingQuality.High;
        camGo.AddComponent<AudioListener>();

        var volGo = new GameObject("Post");
        var vol = volGo.AddComponent<Volume>();
        vol.isGlobal = true;
        vol.sharedProfile = PostProfile();

        // 雨：拉长的雨丝，从镜头上方落下
        var streak = StreakTexture();
        var dot = DotTexture();
        var rainMat = PrecipMaterial("rain", streak, new Color(0.85f, 0.9f, 1f, 0.30f));
        var snowMat = PrecipMaterial("snow", dot, new Color(1f, 1f, 1f, 0.9f));
        var splashMat = PrecipMaterial("splash", dot, new Color(0.9f, 0.94f, 1f, 0.35f));
        var precip = Group("Precipitation");

        var rain = NewParticles("Rain", precip, rainMat, new Vector3(0, 13f, 0));
        var rm = rain.main;
        rm.startLifetime = 0.85f;
        rm.startSpeed = 0f;
        rm.startSize = new ParticleSystem.MinMaxCurve(0.011f, 0.020f);
        rm.maxParticles = 6000;
        rm.simulationSpace = ParticleSystemSimulationSpace.World;
        var rs = rain.shape;
        rs.shapeType = ParticleSystemShapeType.Box;
        rs.scale = new Vector3(30f, 0.5f, 30f);
        var rv = rain.velocityOverLifetime;
        rv.enabled = true;
        rv.space = ParticleSystemSimulationSpace.World;
        rv.x = new ParticleSystem.MinMaxCurve(1.6f, 2.4f);
        rv.y = new ParticleSystem.MinMaxCurve(-19f, -15f);
        rv.z = new ParticleSystem.MinMaxCurve(0.4f, 1.0f);
        var rr = rain.GetComponent<ParticleSystemRenderer>();
        rr.renderMode = ParticleSystemRenderMode.Stretch;
        rr.velocityScale = 0.034f;
        rr.lengthScale = 1f;

        var splash = NewParticles("RainSplash", precip, splashMat, new Vector3(0, 0.03f, 0));
        var sm = splash.main;
        sm.startLifetime = 0.28f;
        sm.startSpeed = 0f;
        sm.startSize = new ParticleSystem.MinMaxCurve(0.05f, 0.12f);
        sm.maxParticles = 600;
        sm.simulationSpace = ParticleSystemSimulationSpace.World;
        var ss = splash.shape;
        ss.shapeType = ParticleSystemShapeType.Box;
        ss.scale = new Vector3(22f, 0f, 22f);
        var ssz = splash.sizeOverLifetime;
        ssz.enabled = true;
        ssz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0, 0.3f, 1, 1.6f));
        var sc = splash.colorOverLifetime;
        sc.enabled = true;
        var grad = new Gradient();
        grad.SetKeys(new[] { new GradientColorKey(Color.white, 0), new GradientColorKey(Color.white, 1) }, new[] { new GradientAlphaKey(1f, 0), new GradientAlphaKey(0f, 1) });
        sc.color = grad;
        var sr = splash.GetComponent<ParticleSystemRenderer>();
        sr.renderMode = ParticleSystemRenderMode.HorizontalBillboard;

        var snow = NewParticles("Snow", precip, snowMat, new Vector3(0, 9f, 0));
        var nm = snow.main;
        nm.startLifetime = 8f;
        nm.startSpeed = 0f;
        nm.startSize = new ParticleSystem.MinMaxCurve(0.03f, 0.075f);
        nm.maxParticles = 8000;
        nm.simulationSpace = ParticleSystemSimulationSpace.World;
        var ns = snow.shape;
        ns.shapeType = ParticleSystemShapeType.Box;
        ns.scale = new Vector3(30f, 1f, 30f);
        var nv = snow.velocityOverLifetime;
        nv.enabled = true;
        nv.space = ParticleSystemSimulationSpace.World;
        nv.x = new ParticleSystem.MinMaxCurve(0.1f, 0.6f);
        nv.y = new ParticleSystem.MinMaxCurve(-1.5f, -0.9f);
        nv.z = new ParticleSystem.MinMaxCurve(-0.2f, 0.2f);
        var nn = snow.noise;
        nn.enabled = true;
        nn.strength = 0.45f;
        nn.frequency = 0.35f;
        nn.scrollSpeed = 0.2f;

        Vector4 hp;
        var height = BakeHeightMap(structure, sceneName, 40f, out hp);

        var twGo = new GameObject("TimeWeather");
        var tw = twGo.AddComponent<TimeWeather>();
        tw.presets = TimePresets();
        tw.overcastSky = Sky("overcast");
        tw.sun = sun;
        tw.bounce = bounce;
        tw.skyMaterial = skyMat;
        tw.volume = vol;
        tw.rain = rain;
        tw.rainSplash = splash;
        tw.snow = snow;
        tw.eaveDrips = BuildEaveDrips(precip, structure, rainMat);
        tw.lampRenderers = lampRenderers.ToArray();
        tw.lampLights = lampLights.ToArray();
        tw.lampLightIntensity = new float[lampLights.Count];
        for (int i = 0; i < lampLights.Count; i++) tw.lampLightIntensity[i] = lampLights[i].intensity;
        tw.heightMap = height;
        tw.heightParams = hp;
        Shader.SetGlobalTexture("_YJHeightMap", height);
        Shader.SetGlobalVector("_YJHeightParams", hp);
        tw.ApplyImmediate(DayTime.Day, Weather.Clear);

        new GameObject("Bridge").AddComponent<Bridge>();
        return tw;
    }

    /// 檐口的水帘：沿着每一段名字叫 DripLine 的线往下滴。线由各座建筑在自己的屋檐外沿放。
    static ParticleSystem BuildEaveDrips(Transform parent, Transform structure, Material mat)
    {
        ParticleSystem first = null;
        foreach (var line in structure.GetComponentsInChildren<Transform>())
        {
            if (!line.name.StartsWith("DripLine")) continue;
            var go = new GameObject("EaveDrips");
            go.transform.SetParent(parent, false);
            go.transform.SetPositionAndRotation(line.position, line.rotation);
            var ps = go.AddComponent<ParticleSystem>();
            var m = ps.main;
            m.startLifetime = 0.95f;
            m.startSpeed = 0f;
            m.startSize = new ParticleSystem.MinMaxCurve(0.016f, 0.028f);
            m.gravityModifier = 1.6f;
            m.maxParticles = 900;
            m.simulationSpace = ParticleSystemSimulationSpace.World;
            var sh = ps.shape;
            sh.shapeType = ParticleSystemShapeType.Box;
            sh.scale = new Vector3(line.localScale.x, 0.02f, 0.03f);
            var e = ps.emission;
            e.rateOverTime = 0f;
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = mat;
            r.renderMode = ParticleSystemRenderMode.Stretch;
            r.velocityScale = 0.045f;
            r.lengthScale = 1f;
            r.shadowCastingMode = ShadowCastingMode.Off;
            if (first == null) first = ps;
            else
            {
                // 其余几段挂在第一段下面，发射量跟着它一起调
                go.transform.SetParent(first.transform, true);
            }
        }
        return first;
    }

    static Material PrecipMaterial(string name, Texture2D tex, Color color)
    {
        string path = $"{MatDir}/{name}.mat";
        var m = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (m == null)
        {
            m = new Material(Shader.Find("Yuanjing/Precip"));
            AssetDatabase.CreateAsset(m, path);
        }
        m.SetTexture("_MainTex", tex);
        m.SetColor("_Color", color);
        EditorUtility.SetDirty(m);
        return m;
    }

    static ParticleSystem NewParticles(string name, Transform parent, Material mat, Vector3 offset)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        go.AddComponent<FollowCamera>().offset = offset;
        var ps = go.AddComponent<ParticleSystem>();
        var e = ps.emission;
        e.rateOverTime = 0f;
        var r = go.GetComponent<ParticleSystemRenderer>();
        r.sharedMaterial = mat;
        r.shadowCastingMode = ShadowCastingMode.Off;
        r.receiveShadows = false;
        return ps;
    }

    /// 生成湖心小寺并导出到 Flutter 工程。
    /// 山寺和教堂（写实的两座）的生成代码还在，但不再生成、不进安装包（2026-11-15 用户决定只留湖心小寺）。
    public static void BuildAndExport()
    {
        SanctuarySetup.Setup();
        BuildFolk();
        BuildIslet();
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene("Assets/Scenes/Islet.unity", true) };
        ProjectExporterBatchmode.ExportProjectIos();
    }
}
