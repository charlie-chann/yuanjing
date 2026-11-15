using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using Yuanjing;

/// 山间小教堂。布局和山寺对应（单位米，+z 是往里走的方向）：
///   z < -14      院门外
///   z -14 .. -10 进门两侧的拱廊：坐的地方，有顶，长椅面朝庭院和教堂
///   z -10 .. 8   庭院：草地、石径、中间的许愿池（喷泉）、四棵柏树、教堂门边的烛台
///   z 8.6 ..     教堂的正立面：尖拱门、玫瑰花窗、两扇长窗，右边是钟楼
/// 只有建筑和氛围，没有十字架和圣像。
public static partial class SanctuaryBuild
{
    [MenuItem("Yuanjing/4 生成教堂")]
    public static void BuildChapel()
    {
        mats.Clear();
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        ConfigureRendering();

        var wallStone = Mat("ch_wall", "stone_wall", 2.6f, new Color(0.86f, 0.83f, 0.78f), rough: 1.05f);
        var trimStone = Mat("ch_trim", "sandstone", 2.2f, new Color(0.84f, 0.80f, 0.72f), rough: 1.0f);
        var floorStone = Mat("ch_floor", "paving_large", 2.2f, new Color(0.80f, 0.77f, 0.72f), puddle: 0.5f);
        var cobble = Mat("ch_cobble", "cobble", 2.4f, new Color(0.80f, 0.78f, 0.74f), puddle: 0.8f);
        var lawn = Mat("ch_lawn", "grass", 2.6f, new Color(0.72f, 0.82f, 0.60f), rough: 1.1f);
        var outside = Mat("ch_outside", "forest_floor", 3.0f, new Color(0.62f, 0.70f, 0.48f));
        var plasterOld = Mat("ch_plaster", "plaster_old", 3.0f, new Color(0.92f, 0.89f, 0.82f));
        var slate = Mat("ch_slate", "roof_slate", 1.8f, new Color(0.62f, 0.64f, 0.70f), rough: 0.85f);
        var clay = Mat("ch_clay", "roof_clay", 1.6f, new Color(0.86f, 0.74f, 0.66f), rough: 0.95f);
        var oak = Mat("ch_oak", "wood_old", 1.4f, new Color(0.62f, 0.50f, 0.40f), rough: 0.85f, wet: 0.5f);
        var doorWood = Mat("ch_door", "wood_dark", 1.3f, new Color(0.42f, 0.30f, 0.22f), rough: 0.7f, wet: 0.4f);
        var iron = Mat("ch_iron", "metal_rust", 0.8f, new Color(0.16f, 0.15f, 0.15f), rough: 0.8f, metallic: 1f);
        var bronze = Mat("bronze", "bronze", 0.9f, new Color(0.62f, 0.55f, 0.40f), rough: 0.7f, metallic: 1f);
        var water = Mat("ch_water", null, 1f, new Color(0.05f, 0.09f, 0.10f), rough: 0.04f, wet: 0f, snow: 0f, puddle: 1f);
        var wax = Mat("ch_wax", null, 1f, new Color(0.93f, 0.89f, 0.78f), rough: 0.5f, wet: 0f, snow: 0f);
        var flame = Emissive("ch_flame", new Color(1f, 0.72f, 0.3f));
        flame.SetColor("_EmissionColor", new Color(7f, 3.4f, 0.9f));
        var paperGlow = Emissive("ch_lamp_glow", new Color(0.92f, 0.82f, 0.62f));
        var mountain = Mat("mountain", "moss_rock", 22f, new Color(0.36f, 0.46f, 0.36f), rough: 1.2f, wet: 0.3f);
        var bark = Mat("bark_pine", "bark_pine", 1.2f, new Color(0.70f, 0.64f, 0.58f));
        var leafTex = LeafAtlas(new Color(0.085f, 0.16f, 0.06f), new Color(0.17f, 0.25f, 0.085f));
        var leavesMat = Mat("leaves_cypress", null, 1f, new Color(0.62f, 0.80f, 0.66f), rough: 0.75f, wet: 0.15f, snow: 0.6f);
        leavesMat.SetTexture("_BaseMap", leafTex);
        leavesMat.SetTextureScale("_BaseMap", Vector2.one);
        leavesMat.SetFloat("_AlphaClip", 1f);
        leavesMat.SetFloat("_Cutoff", 0.45f);
        leavesMat.SetFloat("_Cull", 0f);
        leavesMat.SetFloat("_Sway", 0.6f);
        leavesMat.EnableKeyword("_ALPHATEST_ON");
        leavesMat.renderQueue = (int)RenderQueue.AlphaTest;
        var roseGlass = GlassMaterial("ch_rose", RoseTexture());
        var lancetGlass = GlassMaterial("ch_lancet", LancetTexture());

        var world = Group("World");
        var structure = Group("Structure", world);
        var lampRenderers = new List<Renderer>();
        var lampLights = new List<Light>();
        var glass = new List<Renderer>();
        var leafUV = new[] { new Rect(0, 0, 0.5f, 0.5f), new Rect(0.5f, 0, 0.5f, 0.5f), new Rect(0, 0.5f, 0.5f, 0.5f), new Rect(0.5f, 0.5f, 0.5f, 0.5f) };

        // ── 地面：草地，十字石径，许愿池周围一圈 ──
        Vector3 pool = new Vector3(0, 0, -1f);
        var g = new MeshBuilder();
        g.Quad(new Vector3(-13, 0, -10), new Vector3(13, 0, -10), new Vector3(13, 0, 8.6f), new Vector3(-13, 0, 8.6f), Vector3.up);
        Add("Lawn", g, lawn, structure, false);
        g = new MeshBuilder();
        g.Box(new Vector3(0, 0.02f, -0.7f), new Vector3(2.8f, 0.04f, 18.6f));
        g.Box(new Vector3(0, 0.018f, pool.z), new Vector3(26f, 0.036f, 2.2f));
        g.Lathe(pool + Vector3.up * 0.026f, new[] { new Vector2(4.1f, 0f), new Vector2(2.0f, 0f) }, 32);
        Add("Paths", g, cobble, structure, false);
        g = new MeshBuilder();
        g.Quad(new Vector3(-140, -0.05f, -140), new Vector3(140, -0.05f, -140), new Vector3(140, -0.05f, 140), new Vector3(-140, -0.05f, 140), Vector3.up);
        Add("Outside", g, outside, structure, false);

        BuildCloister(structure, floorStone, wallStone, trimStone, plasterOld, clay, oak, iron, paperGlow, lampRenderers, lampLights);
        BuildChapelFront(structure, wallStone, trimStone, slate, oak, doorWood, iron, bronze, roseGlass, lancetGlass, paperGlow, glass, lampRenderers, lampLights);

        // ── 院墙 ──
        var walls = new MeshBuilder();
        var caps = new MeshBuilder();
        foreach (float sx in new[] { -1f, 1f })
        {
            walls.Box(new Vector3(sx * 13.25f, 1.6f, -2.6f), new Vector3(0.5f, 3.2f, 23.4f));
            caps.Box(new Vector3(sx * 13.25f, 3.28f, -2.6f), new Vector3(0.72f, 0.16f, 23.5f));
        }
        Add("Walls", walls, wallStone, structure);
        Add("WallCaps", caps, trimStone, structure);

        // ── 许愿池：八角的石池，中间一根石柱托着上面的小水盘，水从盘沿落下来 ──
        var basin = new MeshBuilder();
        basin.Lathe(pool, new[]
        {
            new Vector2(2.10f, 0f), new Vector2(2.10f, 0.10f), new Vector2(2.00f, 0.14f), new Vector2(2.00f, 0.50f), new Vector2(2.08f, 0.54f),
            new Vector2(2.08f, 0.62f), new Vector2(1.78f, 0.62f), new Vector2(1.76f, 0.30f),
        }, 8);
        basin.Lathe(pool, new[]
        {
            new Vector2(0.46f, 0.30f), new Vector2(0.46f, 0.56f), new Vector2(0.34f, 0.64f), new Vector2(0.22f, 0.80f), new Vector2(0.19f, 1.26f),
            new Vector2(0.28f, 1.38f), new Vector2(0.80f, 1.50f), new Vector2(0.84f, 1.56f), new Vector2(0.78f, 1.57f), new Vector2(0.30f, 1.47f),
            new Vector2(0.13f, 1.47f), new Vector2(0.10f, 1.84f), new Vector2(0.17f, 1.92f), new Vector2(0.10f, 2.02f), new Vector2(0.001f, 2.10f),
        }, 24);
        Add("Fountain", basin, trimStone, structure);
        var surface = new MeshBuilder();
        surface.Disc(pool + Vector3.up * 0.47f, 1.78f, 8, Vector3.up);
        surface.Disc(pool + Vector3.up * 1.545f, 0.77f, 24, Vector3.up);
        Add("Water", surface, water, structure, false);

        // ── 柏树 ──
        var barkMesh = new MeshBuilder();
        var leafMesh = new MeshBuilder();
        var cypress = new[] { new Vector3(-7.2f, 0, -6.4f), new Vector3(7.2f, 0, -6.4f), new Vector3(-7.6f, 0, 4.4f), new Vector3(7.6f, 0, 4.2f), new Vector3(-11f, 0, -5.2f) };
        for (int i = 0; i < cypress.Length; i++) Cypress(barkMesh, leafMesh, cypress[i], 6.6f + (i * 37 % 5) * 0.35f, 0.95f, 31 + i, leafUV);
        Add("CypressBark", barkMesh, bark, structure);
        Add("CypressLeaves", leafMesh, leavesMat, structure);

        // ── 烛台：教堂门两边各一座。石台上三层铁架，一排排蜡烛，有些已经点着 ──
        var stand = new MeshBuilder();
        var plinth = new MeshBuilder();
        var waxMesh = new MeshBuilder();
        var flameMesh = new MeshBuilder();
        var candleSlots = Group("CandleSlots", structure);
        var rngC = new Rng(5);
        int slotN = 0;
        foreach (float sx in new[] { -1f, 1f })
        {
            Vector3 at = new Vector3(sx * 4.3f, 0, 7.55f);
            plinth.Box(at + new Vector3(0, 0.36f, 0.1f), new Vector3(2.0f, 0.72f, 0.9f));
            plinth.Box(at + new Vector3(0, 0.75f, 0.1f), new Vector3(2.14f, 0.07f, 1.0f));
            for (int tier = 0; tier < 3; tier++)
            {
                float y = 0.80f + tier * 0.15f, z = at.z - 0.22f + tier * 0.22f;
                stand.Box(new Vector3(at.x, y, z), new Vector3(1.84f, 0.025f, 0.16f));
                foreach (float ex in new[] { -0.9f, 0.9f }) stand.Box(new Vector3(at.x + ex, (y + 0.79f) * 0.5f, z), new Vector3(0.03f, y - 0.79f + 0.02f, 0.03f));
                for (int i = 0; i < 11; i++)
                {
                    Vector3 p = new Vector3(at.x - 0.80f + i * 0.16f, y + 0.012f, z);
                    // 左边那座留一半空位给人点；右边那座基本点满
                    if (rngC.Next() < (sx < 0 ? 0.42f : 0.8f))
                    {
                        float h = rngC.Range(0.07f, 0.17f);
                        waxMesh.Cylinder(p, 0.013f, h, 8, true);
                        flameMesh.Lathe(p + Vector3.up * (h + 0.006f), new[] { new Vector2(0.001f, 0f), new Vector2(0.010f, 0.008f), new Vector2(0.014f, 0.022f), new Vector2(0.008f, 0.045f), new Vector2(0.001f, 0.066f) }, 6);
                    }
                    else if (sx < 0)
                    {
                        var slot = new GameObject($"Slot{slotN++}");
                        slot.transform.SetParent(candleSlots, false);
                        slot.transform.position = p;
                    }
                }
            }
            var lg = new GameObject("CandleLight");
            lg.transform.SetParent(structure, false);
            lg.transform.position = at + new Vector3(0, 1.45f, -0.35f);
            var l = lg.AddComponent<Light>();
            l.type = LightType.Point;
            l.color = new Color(1f, 0.62f, 0.28f);
            l.range = 5.5f;
            l.intensity = 5f;
            l.shadows = LightShadows.None;
            lg.AddComponent<Flicker>();
        }
        Add("CandlePlinth", plinth, trimStone, structure);
        Add("CandleStand", stand, iron, structure);
        Add("Candles", waxMesh, wax, structure, false);
        Add("Flames", flameMesh, flame, structure, false);

        BuildMountains(world, mountain, 5.3f);

        // ── 花草：柏树脚下、院墙根、草坪上点缀野花、山门外 ──
        plantKinds.Clear();
        var grass = Plant("grass_medium_02", new Color(0.80f, 0.86f, 0.70f));
        var shrub = Plant("shrub_03", new Color(0.82f, 0.88f, 0.78f));
        var fern = Plant("fern_02", new Color(0.86f, 0.92f, 0.82f));
        var flower = Plant("celandine_01", Color.white);
        var patches = new List<PlantPatch>();
        foreach (var c in cypress)
        {
            patches.Add(new PlantPatch { kind = fern, center = c, size = new Vector2(1.1f, 0), ring = 0.3f, count = 4, scale = new Vector2(0.7f, 1.0f) });
            patches.Add(new PlantPatch { kind = grass, center = c, size = new Vector2(1.2f, 0), ring = 0.25f, count = 14, scale = new Vector2(1.3f, 1.9f) });
        }
        foreach (float sx in new[] { -1f, 1f })
        {
            patches.Add(new PlantPatch { kind = shrub, center = new Vector3(sx * 12.5f, 0, -1f), size = new Vector2(0.9f, 17f), count = 60, scale = new Vector2(2.2f, 3.2f) });
            patches.Add(new PlantPatch { kind = grass, center = new Vector3(sx * 12.1f, 0, -1f), size = new Vector2(1.4f, 17f), count = 140, scale = new Vector2(1.5f, 2.4f) });
            // 草坪上的小野花和草丛（避开石径）
            patches.Add(new PlantPatch { kind = flower, center = new Vector3(sx * 7.5f, 0, -1.2f), size = new Vector2(8f, 15f), count = 110, scale = new Vector2(1.0f, 1.4f) });
            patches.Add(new PlantPatch { kind = grass, center = new Vector3(sx * 7.5f, 0, -1.2f), size = new Vector2(8f, 15f), count = 260, scale = new Vector2(1.2f, 2.0f) });
            patches.Add(new PlantPatch { kind = grass, center = new Vector3(sx * 8f, -0.05f, -19.5f), size = new Vector2(12f, 7f), count = 600, scale = new Vector2(1.6f, 2.6f) });
            patches.Add(new PlantPatch { kind = shrub, center = new Vector3(sx * 8f, -0.05f, -22.6f), size = new Vector2(12f, 1.4f), count = 70, scale = new Vector2(2.4f, 3.6f) });
        }
        BuildPlantPatches(structure, patches, 91);

        var tw = BuildEnvironment(world, structure, "Chapel", lampRenderers, lampLights, new Vector3(0, 1.6f, -19f), new Vector3(0, 4.5f, 9f));
        tw.glassRenderers = glass.ToArray();
        tw.ApplyImmediate(DayTime.Day, Weather.Clear);

        // ── 运行时 ──
        var seatsRoot = structure.Find("Cloister/Seats");
        var game = BuildRuntime("amb_music_chapel", "sfx_bell_church", seatsRoot, null, null, null, pool + Vector3.up * 0.47f, 1.5f);
        var off = game.GetComponent<Offerings>();
        off.candleSlots = candleSlots;
        off.waxMaterial = wax;
        off.flameMaterial = flame;
        var sound = game.GetComponent<WorldAudio>();
        sound.placedLoop = "amb_fountain";
        sound.placedAt = pool + Vector3.up;
        sound.placedVolume = 0.7f;
        BuildFountainWater(game.transform, pool);

        Vector3 front = new Vector3(0, 6.4f, 8.6f);
        game.spots = new[]
        {
            new Spot { name = "gate", floor = new Vector3(0, 0, -18.5f), look = new Vector3(0, 5.2f, 9f), pick = 0 },
            new Spot { name = "court", floor = new Vector3(0, 0.03f, -8.6f), look = front, pick = 0.01f },
            new Spot { name = "pool", floor = new Vector3(0, 0.03f, -4.5f), look = pool + Vector3.up * 1.15f, pick = 1.9f },
            new Spot { name = "candles", floor = new Vector3(-4.3f, 0.03f, 5.5f), look = new Vector3(-4.3f, 1.05f, 7.6f), pick = 1.2f },
            new Spot { name = "nave", floor = new Vector3(0, 0.03f, 3.3f), look = new Vector3(0, 7.5f, 8.6f), pick = 4.5f },
        };
        var obs = new List<Obstacle> { new Obstacle { center = pool, radius = 2.6f } };
        foreach (var c in cypress) obs.Add(new Obstacle { center = c, radius = 1.1f });
        game.obstacles = obs.ToArray();
        game.hub = new Vector3(0, 0.03f, -9.2f);
        game.aislePoint = new Vector3(0, 0.20f, -12.0f);
        game.aisleDir = Vector3.right;
        game.seatExitNeg = new[] { new Vector3(-2.05f, 0.20f, -12.0f), new Vector3(0, 0.06f, -12.0f) };
        game.seatExitPos = new[] { new Vector3(2.05f, 0.20f, -12.0f), new Vector3(0, 0.06f, -12.0f) };
        game.seatLook = front;
        game.seatStraight = 0.72f;
        game.seatDrop = 0.30f;
        ConfigureCrowd(game, new Vector3(0, 0, -20f), new Vector3(0, 0.03f, -12.4f),
            new[] { new Vector3(0, 0.03f, -4.2f), new Vector3(2.6f, 0.03f, -1.2f), new Vector3(-4.3f, 0.03f, 5.6f), new Vector3(2.4f, 0.03f, 3.6f), new Vector3(-2.8f, 0.03f, -6.8f), new Vector3(4.3f, 0.03f, 5.6f) },
            new[] { pool + Vector3.up, pool + Vector3.up, new Vector3(-4.3f, 1f, 7.6f), front, front, new Vector3(4.3f, 1f, 7.6f) },
            true);

        EditorSceneManager.SaveScene(scene, "Assets/Scenes/Chapel.unity");
        AssetDatabase.SaveAssets();
        Debug.Log("[yuanjing] 教堂已生成");
    }

    /// 进门两侧的拱廊：石地台、一排圆拱、矮墙、两坡瓦顶。长椅摆在这里，面朝庭院。
    static void BuildCloister(Transform parent, Material floor, Material wallStone, Material trim, Material plaster, Material tile, Material wood, Material iron, Material glow,
        List<Renderer> lampRenderers, List<Light> lampLights)
    {
        var root = Group("Cloister", parent);
        const float y0 = 0.20f, top = 3.5f, zFront = -10.3f, zBack = -13.9f;
        float[] xs = { 1.8f, 4.5f, 7.2f, 9.9f, 12.6f };

        var fl = new MeshBuilder();
        foreach (float sx in new[] { -1f, 1f })
        {
            fl.Box(new Vector3(sx * 7.35f, y0 * 0.5f, -12.1f), new Vector3(11.1f, y0, 4.2f));
            fl.Box(new Vector3(sx * 7.35f, y0 * 0.25f, -9.84f), new Vector3(10.6f, y0 * 0.5f, 0.4f));
        }
        fl.Box(new Vector3(0, 0.03f, -12.1f), new Vector3(3.6f, 0.06f, 4.6f));
        Add("Floor", fl, floor, root);

        // 朝庭院的一排拱：两边各四间，中间一间大的是过道
        var arches = new MeshBuilder();
        var lamps = new MeshBuilder();
        var chains = new MeshBuilder();
        var spots = new List<Vector3>();
        foreach (float sx in new[] { -1f, 1f })
            for (int i = 0; i < xs.Length - 1; i++)
            {
                float a = sx * xs[i], b = sx * xs[i + 1], cx = (a + b) * 0.5f;
                ArchWall(arches, Mathf.Min(a, b), Mathf.Max(a, b), y0, top, cx, 1.0f, y0 + 1.95f, false, zFront, 0.46f);
                // 拱洞里的矮墙
                arches.Box(new Vector3(cx, y0 + 0.26f, zFront), new Vector3(2.0f, 0.52f, 0.30f));
                // 每隔一间挂一盏铁灯
                if (i % 2 == 0)
                {
                    Vector3 c = new Vector3(cx, y0 + 2.42f, zFront);
                    chains.Box(c + Vector3.up * 0.33f, new Vector3(0.012f, 0.42f, 0.012f));
                    chains.Box(c + Vector3.up * 0.135f, new Vector3(0.20f, 0.02f, 0.20f));
                    chains.Box(c - Vector3.up * 0.135f, new Vector3(0.18f, 0.02f, 0.18f));
                    foreach (float ex in new[] { -1f, 1f })
                        foreach (float ez in new[] { -1f, 1f })
                            chains.Box(c + new Vector3(ex * 0.08f, 0, ez * 0.08f), new Vector3(0.014f, 0.26f, 0.014f));
                    lamps.Box(c, new Vector3(0.145f, 0.24f, 0.145f));
                    spots.Add(c);
                }
            }
        ArchWall(arches, -xs[0], xs[0], 0.06f, top, 0, 1.38f, y0 + 1.86f, false, zFront, 0.46f);
        Add("Arches", arches, wallStone, root);
        var cornice = new MeshBuilder();
        cornice.Box(new Vector3(0, top + 0.06f, zFront), new Vector3(25.8f, 0.14f, 0.62f));
        Add("Cornice", cornice, trim, root);
        Add("LampIron", chains, iron, root, false);
        lampRenderers.Add(Add("LampGlow", lamps, glow, root, false).GetComponent<Renderer>());
        foreach (var p in spots)
        {
            var lg = new GameObject("CloisterLight");
            lg.transform.SetParent(root, false);
            lg.transform.position = p + Vector3.back * 0.1f;
            var l = lg.AddComponent<Light>();
            l.type = LightType.Point;
            l.color = new Color(1f, 0.68f, 0.36f);
            l.range = 7f;
            l.intensity = 8f;
            l.shadows = LightShadows.None;
            lampLights.Add(l);
        }

        // 后墙：粉墙，中间是院门
        var back = new MeshBuilder();
        foreach (float sx in new[] { -1f, 1f }) back.Box(new Vector3(sx * 7.3f, y0 + (top - y0) * 0.5f, zBack - 0.05f), new Vector3(11.0f, top - y0, 0.3f));
        Add("BackWall", back, plaster, root);
        var gate = new MeshBuilder();
        ArchWall(gate, -1.82f, 1.82f, 0.06f, top + 0.5f, 0, 1.3f, 2.25f, false, zBack - 0.05f, 0.5f);
        gate.Box(new Vector3(0, 0.10f, zBack - 0.05f), new Vector3(2.6f, 0.08f, 0.5f));
        Add("Gate", gate, wallStone, root);

        // 屋顶：两坡的陶瓦，屋脊沿着拱廊走
        var roof = new MeshBuilder();
        var under = new MeshBuilder();
        roof.m = under.m = Matrix4x4.TRS(new Vector3(0, top + 0.12f, -12.1f), Quaternion.Euler(0, 90, 0), Vector3.one);
        GableRoof(roof, under, Vector3.zero, 4.4f, 27.4f, 1.45f, 0.5f);
        Add("Roof", roof, tile, root);
        Add("RoofUnder", under, wood, root);
        var beams = new MeshBuilder();
        foreach (float sx in new[] { -1f, 1f })
            foreach (float x in xs)
                beams.Box(new Vector3(sx * x, top - 0.02f, -12.1f), new Vector3(0.16f, 0.2f, 3.5f));
        Add("Beams", beams, wood, root);

        var drip = new GameObject("DripLine");
        drip.transform.SetParent(root, false);
        drip.transform.position = new Vector3(0, top - 0.05f, -12.1f + 2.2f + 0.5f);
        drip.transform.localScale = new Vector3(27f, 1, 1);

        // 长椅：没有靠背的木凳，一张坐两个人。两排，每边四张。
        var bench = new MeshBuilder();
        var seats = Group("Seats", root);
        int n = 0;
        float[] benchX = { 3.15f, 5.85f, 8.55f, 11.25f };
        foreach (float z in new[] { -11.2f, -12.8f })
            foreach (float sx in new[] { -1f, 1f })
                foreach (float bx in benchX)
                {
                    Vector3 c = new Vector3(sx * bx, y0, z);
                    bench.Box(c + new Vector3(0, 0.30f, 0), new Vector3(2.1f, 0.06f, 0.40f));
                    foreach (float ex in new[] { -0.82f, 0.82f })
                    {
                        bench.Box(c + new Vector3(ex, 0.135f, 0), new Vector3(0.07f, 0.27f, 0.34f));
                        bench.Box(c + new Vector3(ex, 0.03f, 0), new Vector3(0.10f, 0.06f, 0.40f));
                    }
                    bench.Box(c + new Vector3(0, 0.15f, 0), new Vector3(1.6f, 0.06f, 0.05f));
                    foreach (float ox in new[] { -0.6f, 0.6f })
                    {
                        var seat = new GameObject($"Seat{n++}");
                        seat.transform.SetParent(seats, false);
                        seat.transform.position = c + new Vector3(ox, 0.33f, 0);
                    }
                }
        Add("Benches", bench, wood, root);
    }

    /// 教堂的正立面：山墙、尖拱门、玫瑰花窗、两扇长窗、扶壁，右边一座钟楼
    static void BuildChapelFront(Transform parent, Material wallStone, Material trim, Material slate, Material wood, Material doorWood, Material iron, Material bronze,
        Material roseGlass, Material lancetGlass, Material glow, List<Renderer> glass, List<Renderer> lampRenderers, List<Light> lampLights)
    {
        var root = Group("Chapel", parent);
        const float zF = 8.6f, halfW = 7f, eave = 8.2f, rise = 5.2f, depth = 16f;

        var body = new MeshBuilder();
        body.Box(new Vector3(0, eave * 0.5f, zF + depth * 0.5f), new Vector3(halfW * 2f, eave, depth));
        // 山墙的三角
        body.Quad(new Vector3(-halfW, eave, zF), new Vector3(halfW, eave, zF), new Vector3(0, eave + rise, zF), new Vector3(0, eave + rise, zF), Vector3.back);
        body.Quad(new Vector3(-halfW, eave, zF + depth), new Vector3(halfW, eave, zF + depth), new Vector3(0, eave + rise, zF + depth), new Vector3(0, eave + rise, zF + depth), Vector3.forward);
        // 两翼的矮墙，把庭院围起来
        foreach (float sx in new[] { -1f, 1f }) body.Box(new Vector3(sx * 10.2f, 1.6f, zF + 0.3f), new Vector3(6.4f, 3.2f, 0.5f));
        // 扶壁：下大上小两段
        foreach (float sx in new[] { -1f, 1f })
        {
            body.Box(new Vector3(sx * (halfW - 0.1f), 2.6f, zF - 0.45f), new Vector3(1.1f, 5.2f, 1.1f));
            body.Box(new Vector3(sx * (halfW - 0.1f), 6.3f, zF - 0.25f), new Vector3(0.9f, 2.4f, 0.7f));
        }
        Add("Body", body, wallStone, root);

        var roof = new MeshBuilder();
        var under = new MeshBuilder();
        GableRoof(roof, under, new Vector3(0, eave, zF + depth * 0.5f - 0.2f), halfW * 2f, depth + 0.9f, rise, 0.55f);
        Add("Roof", roof, slate, root);
        Add("RoofUnder", under, wood, root);

        var tr = new MeshBuilder();
        // 腰线和檐口线
        tr.Box(new Vector3(0, 6.55f, zF - 0.06f), new Vector3(halfW * 2f - 1.6f, 0.2f, 0.22f));
        tr.Box(new Vector3(0, 0.25f, zF - 0.08f), new Vector3(halfW * 2f + 0.3f, 0.5f, 0.3f));
        foreach (float sx in new[] { -1f, 1f })
        {
            tr.Box(new Vector3(sx * (halfW - 0.1f), 5.28f, zF - 0.45f), new Vector3(1.24f, 0.16f, 1.24f));
            tr.Box(new Vector3(sx * (halfW - 0.1f), 7.56f, zF - 0.25f), new Vector3(1.0f, 0.14f, 0.8f));
            tr.Box(new Vector3(sx * 10.2f, 3.26f, zF + 0.3f), new Vector3(6.5f, 0.14f, 0.7f));
        }
        // 台阶
        for (int i = 0; i < 3; i++)
        {
            float frontZ = zF - 1.5f + i * 0.4f;
            tr.Box(new Vector3(0, 0.075f + i * 0.15f, (frontZ + zF) * 0.5f), new Vector3(4.8f - i * 0.3f, 0.15f, zF - frontZ));
        }
        // 门：三层往里收的尖拱线脚
        const float doorY = 0.45f, doorA = 1.25f, doorSpring = 2.75f;
        tr.Tube(ArchPath(0, doorY, doorA + 0.52f, doorSpring, true, zF - 0.10f), t => 0.17f, 8, true);
        tr.Tube(ArchPath(0, doorY, doorA + 0.26f, doorSpring, true, zF - 0.02f), t => 0.13f, 8, true);
        tr.Tube(ArchPath(0, doorY, doorA + 0.06f, doorSpring, true, zF + 0.04f), t => 0.09f, 8, true);
        // 玫瑰花窗的石圈
        const float roseY = 9.3f, roseR = 1.85f;
        tr.m = Matrix4x4.TRS(new Vector3(0, roseY, zF + 0.02f), Quaternion.Euler(-90, 0, 0), Vector3.one);
        tr.Lathe(Vector3.zero, new[] { new Vector2(roseR - 0.04f, 0f), new Vector2(roseR + 0.02f, 0.16f), new Vector2(roseR + 0.2f, 0.22f), new Vector2(roseR + 0.36f, 0.14f), new Vector2(roseR + 0.40f, 0f) }, 40);
        tr.m = Matrix4x4.identity;
        // 两扇长窗的石框
        const float lanW = 1.3f, lanH = 3.9f, lanY = 2.3f;
        foreach (float sx in new[] { -1f, 1f })
            tr.Tube(ArchPath(sx * 4.1f, lanY, lanW * 0.5f + 0.05f, lanY + lanH - lanW * 0.5f * 1.732f, true, zF - 0.02f), t => 0.085f, 8, true);
        foreach (float sx in new[] { -1f, 1f }) tr.Box(new Vector3(sx * 4.1f, lanY - 0.07f, zF - 0.06f), new Vector3(lanW + 0.4f, 0.14f, 0.26f));
        Add("Trim", tr, trim, root);

        // 门扇：两扇厚木门，中间一道缝，铁门环
        var door = new MeshBuilder();
        ArchPanel(door, 0, doorY, doorA, doorSpring, true, zF - 0.01f, Vector3.back);
        Add("Door", door, doorWood, root, false);
        var fit = new MeshBuilder();
        fit.Box(new Vector3(0, doorY + (doorSpring + doorA * 1.73f - doorY) * 0.5f, zF - 0.02f), new Vector3(0.03f, doorSpring + doorA * 1.73f - doorY, 0.02f));
        foreach (float sx in new[] { -1f, 1f })
        {
            fit.Box(new Vector3(sx * 0.62f, 1.25f, zF - 0.03f), new Vector3(1.1f, 0.07f, 0.02f));
            fit.Box(new Vector3(sx * 0.62f, 2.65f, zF - 0.03f), new Vector3(1.1f, 0.07f, 0.02f));
            fit.m = Matrix4x4.TRS(new Vector3(sx * 0.22f, 1.72f, zF - 0.05f), Quaternion.Euler(-90, 0, 0), Vector3.one);
            fit.Lathe(Vector3.zero, new[] { new Vector2(0.075f, 0f), new Vector2(0.09f, 0.012f), new Vector2(0.075f, 0.024f), new Vector2(0.06f, 0.012f), new Vector2(0.075f, 0f) }, 14);
            fit.m = Matrix4x4.identity;
        }
        Add("DoorIron", fit, iron, root, false);

        // 彩色玻璃
        var rose = new MeshBuilder();
        rose.QuadUV(new Vector3(-roseR, roseY - roseR, zF - 0.03f), new Vector3(roseR, roseY - roseR, zF - 0.03f), new Vector3(roseR, roseY + roseR, zF - 0.03f), new Vector3(-roseR, roseY + roseR, zF - 0.03f),
            Vector3.back, new Rect(0, 0, 1, 1));
        glass.Add(Add("Rose", rose, roseGlass, root, false).GetComponent<Renderer>());
        var lan = new MeshBuilder();
        foreach (float sx in new[] { -1f, 1f })
            lan.QuadUV(new Vector3(sx * 4.1f - lanW * 0.5f, lanY, zF - 0.03f), new Vector3(sx * 4.1f + lanW * 0.5f, lanY, zF - 0.03f),
                new Vector3(sx * 4.1f + lanW * 0.5f, lanY + lanH, zF - 0.03f), new Vector3(sx * 4.1f - lanW * 0.5f, lanY + lanH, zF - 0.03f), Vector3.back, new Rect(0, 0, 1, 1));
        glass.Add(Add("Lancets", lan, lancetGlass, root, false).GetComponent<Renderer>());

        // 门两边的壁灯
        var lampIron = new MeshBuilder();
        var lampGlow = new MeshBuilder();
        foreach (float sx in new[] { -1f, 1f })
        {
            Vector3 c = new Vector3(sx * 2.25f, 3.1f, zF - 0.42f);
            lampIron.Box(c + new Vector3(0, 0.2f, 0.2f), new Vector3(0.03f, 0.03f, 0.42f));
            lampIron.Box(c + Vector3.up * 0.16f, new Vector3(0.24f, 0.025f, 0.24f));
            lampIron.Box(c - Vector3.up * 0.16f, new Vector3(0.20f, 0.025f, 0.20f));
            foreach (float ex in new[] { -1f, 1f })
                foreach (float ez in new[] { -1f, 1f })
                    lampIron.Box(c + new Vector3(ex * 0.09f, 0, ez * 0.09f), new Vector3(0.016f, 0.32f, 0.016f));
            lampGlow.Box(c, new Vector3(0.165f, 0.29f, 0.165f));
            var lg = new GameObject("DoorLight");
            lg.transform.SetParent(root, false);
            lg.transform.position = c + Vector3.back * 0.2f;
            var l = lg.AddComponent<Light>();
            l.type = LightType.Point;
            l.color = new Color(1f, 0.68f, 0.36f);
            l.range = 8f;
            l.intensity = 10f;
            l.shadows = LightShadows.None;
            lampLights.Add(l);
        }
        Add("DoorLampIron", lampIron, iron, root, false);
        lampRenderers.Add(Add("DoorLampGlow", lampGlow, glow, root, false).GetComponent<Renderer>());

        // ── 钟楼：方塔，顶上四面开拱的钟室，尖顶 ──
        Vector3 tower = new Vector3(9.6f, 0, zF + 2.6f);
        const float tw = 4.2f, shaft = 12.6f, belfry = 3.6f;
        var tb = new MeshBuilder();
        tb.Box(tower + Vector3.up * shaft * 0.5f, new Vector3(tw, shaft, tw));
        for (int side = 0; side < 4; side++)
        {
            tb.m = Matrix4x4.TRS(tower + Vector3.up * shaft, Quaternion.Euler(0, side * 90, 0), Vector3.one);
            ArchWall(tb, -tw * 0.5f, tw * 0.5f, 0, belfry, 0, 0.95f, 1.35f, false, -tw * 0.5f + 0.25f, 0.5f);
        }
        tb.m = Matrix4x4.identity;
        Add("Tower", tb, wallStone, root);
        var tt = new MeshBuilder();
        tt.Box(tower + Vector3.up * (shaft + 0.02f), new Vector3(tw + 0.3f, 0.22f, tw + 0.3f));
        tt.Box(tower + Vector3.up * (shaft + belfry + 0.08f), new Vector3(tw + 0.4f, 0.24f, tw + 0.4f));
        tt.Box(tower + Vector3.up * 6.4f, new Vector3(tw + 0.16f, 0.18f, tw + 0.16f));
        Add("TowerTrim", tt, trim, root);
        var spire = new MeshBuilder();
        spire.m = Matrix4x4.TRS(tower + Vector3.up * (shaft + belfry + 0.2f), Quaternion.Euler(0, 45, 0), Vector3.one);
        spire.Lathe(Vector3.zero, new[] { new Vector2(tw * 0.5f * 1.414f + 0.3f, 0f), new Vector2(tw * 0.5f * 1.414f * 0.55f, 2.4f), new Vector2(0.02f, 6.2f) }, 4);
        Add("Spire", spire, slate, root);
        var bell = new MeshBuilder();
        Vector3 bellAt = tower + Vector3.up * (shaft + 1.25f);
        bell.Lathe(bellAt, new[]
        {
            new Vector2(0.62f, 0f), new Vector2(0.58f, 0.06f), new Vector2(0.44f, 0.30f), new Vector2(0.36f, 0.62f), new Vector2(0.33f, 0.86f), new Vector2(0.22f, 1.0f), new Vector2(0.06f, 1.05f),
        }, 24);
        bell.Box(bellAt + Vector3.up * 1.3f, new Vector3(tw - 0.6f, 0.16f, 0.16f));
        bell.Box(bellAt + Vector3.up * 1.14f, new Vector3(0.08f, 0.24f, 0.08f));
        Add("Bell", bell, bronze, root);
    }

    /// 许愿池的水：从上面的水盘沿一圈落下来，落进池里溅起一圈细小的水花
    static void BuildFountainWater(Transform parent, Vector3 pool)
    {
        var streamMat = ParticleMaterial("fountain_stream", DotTexture(), new Color(0.92f, 0.96f, 1f, 0.5f), false, true);
        var fall = Particles("FountainFall", parent, streamMat);
        fall.transform.position = pool + Vector3.up * 1.55f;
        fall.transform.rotation = Quaternion.Euler(90, 0, 0);
        var m = fall.main;
        m.startLifetime = 0.46f;
        m.startSpeed = new ParticleSystem.MinMaxCurve(0.28f, 0.42f);
        m.startSize = new ParticleSystem.MinMaxCurve(0.016f, 0.03f);
        m.gravityModifier = 1f;
        m.maxParticles = 400;
        m.simulationSpace = ParticleSystemSimulationSpace.World;
        var e = fall.emission;
        e.rateOverTime = 300f;
        var sh = fall.shape;
        sh.shapeType = ParticleSystemShapeType.Circle;
        sh.radius = 0.82f;
        sh.radiusThickness = 0f;
        var r = fall.GetComponent<ParticleSystemRenderer>();
        r.renderMode = ParticleSystemRenderMode.Stretch;
        r.velocityScale = 0.05f;
        r.lengthScale = 1.4f;

        var ringMat = ParticleMaterial("fountain_ring", DotTexture(), new Color(0.9f, 0.95f, 1f, 0.3f), false, true);
        var ring = Particles("FountainRing", parent, ringMat);
        ring.transform.position = pool + Vector3.up * 0.49f;
        ring.transform.rotation = Quaternion.Euler(90, 0, 0);
        var rm = ring.main;
        rm.startLifetime = 0.55f;
        rm.startSpeed = 0f;
        rm.startSize = new ParticleSystem.MinMaxCurve(0.05f, 0.11f);
        rm.maxParticles = 120;
        rm.simulationSpace = ParticleSystemSimulationSpace.World;
        var re = ring.emission;
        re.rateOverTime = 70f;
        var rs = ring.shape;
        rs.shapeType = ParticleSystemShapeType.Circle;
        rs.radius = 0.99f;
        rs.radiusThickness = 0.08f;
        var size = ring.sizeOverLifetime;
        size.enabled = true;
        size.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0, 0.4f, 1, 1.8f));
        var col = ring.colorOverLifetime;
        col.enabled = true;
        col.color = FadeInOut(0.1f);
        ring.GetComponent<ParticleSystemRenderer>().renderMode = ParticleSystemRenderMode.HorizontalBillboard;
    }
}
