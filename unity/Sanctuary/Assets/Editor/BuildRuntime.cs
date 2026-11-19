using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using Yuanjing;

/// 两座殿共用的运行时部分：镜头、总控、香客、心意、声音。场景各自再填地点和路线。
public static partial class SanctuaryBuild
{
    static Material ParticleMaterial(string name, Texture2D tex, Color color, bool additive, bool lit)
    {
        string path = $"{MatDir}/{name}.mat";
        var m = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (m == null)
        {
            m = new Material(Shader.Find("Yuanjing/Particle"));
            AssetDatabase.CreateAsset(m, path);
        }
        m.shader = Shader.Find("Yuanjing/Particle");
        m.SetTexture("_MainTex", tex);
        m.SetColor("_Color", color);
        m.SetFloat("_Lit", lit ? 1f : 0f);
        m.SetFloat("_Dst", additive ? (float)BlendMode.One : (float)BlendMode.OneMinusSrcAlpha);
        // 离镜头 0.5 米以内看不见、1.5 米以外照常（个别的另设）
        m.SetVector("_Near", new Vector4(0.5f, 1.5f, 0f, 0f));
        EditorUtility.SetDirty(m);
        return m;
    }

    static ParticleSystem Particles(string name, Transform parent, Material mat)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        var ps = go.AddComponent<ParticleSystem>();
        var e = ps.emission;
        e.rateOverTime = 0f;
        var sh = ps.shape;
        sh.enabled = true;
        var r = go.GetComponent<ParticleSystemRenderer>();
        r.sharedMaterial = mat;
        r.shadowCastingMode = ShadowCastingMode.Off;
        r.receiveShadows = false;
        return ps;
    }

    static Gradient FadeInOut(float peakAt = 0.15f)
    {
        var g = new Gradient();
        g.SetKeys(new[] { new GradientColorKey(Color.white, 0), new GradientColorKey(Color.white, 1) },
            new[] { new GradientAlphaKey(0f, 0), new GradientAlphaKey(1f, peakAt), new GradientAlphaKey(0f, 1) });
        return g;
    }

    /// 声音的导入设置：长的循环压缩着放在内存里（省内存），短的音效解开放（响应快）
    static void ConfigureAudio()
    {
        foreach (string file in Directory.GetFiles("Assets/Resources/Audio", "*.wav"))
        {
            var imp = (AudioImporter)AssetImporter.GetAtPath(file.Replace('\\', '/'));
            if (imp == null) continue;
            bool loop = Path.GetFileName(file).StartsWith("amb_");
            var s = imp.defaultSampleSettings;
            var load = loop ? AudioClipLoadType.CompressedInMemory : AudioClipLoadType.DecompressOnLoad;
            if (s.loadType == load && s.compressionFormat == AudioCompressionFormat.Vorbis && Mathf.Approximately(s.quality, 0.7f)) continue;
            s.loadType = load;
            s.compressionFormat = AudioCompressionFormat.Vorbis;
            s.quality = 0.7f;
            imp.defaultSampleSettings = s;
            imp.SaveAndReimport();
        }
    }

    /// 香炉上的烟：一直淡淡地冒，有人上香时浓一阵
    static ParticleSystem BuildSmoke(Transform parent, Vector3 at)
    {
        var mat = ParticleMaterial("smoke", DotTexture(), new Color(0.82f, 0.84f, 0.88f, 0.085f), false, true);
        var ps = Particles("IncenseSmoke", parent, mat);
        ps.transform.position = at;
        ps.transform.rotation = Quaternion.Euler(-90, 0, 0);
        var m = ps.main;
        m.startLifetime = new ParticleSystem.MinMaxCurve(5f, 8f);
        m.startSpeed = new ParticleSystem.MinMaxCurve(0.22f, 0.4f);
        m.startSize = new ParticleSystem.MinMaxCurve(0.22f, 0.4f);
        m.startRotation = new ParticleSystem.MinMaxCurve(0, Mathf.PI * 2);
        m.maxParticles = 160;
        m.simulationSpace = ParticleSystemSimulationSpace.World;
        var e = ps.emission;
        e.rateOverTime = 5f;
        var sh = ps.shape;
        sh.shapeType = ParticleSystemShapeType.Cone;
        sh.angle = 5f;
        sh.radius = 0.32f;
        var sz = ps.sizeOverLifetime;
        sz.enabled = true;
        sz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0, 0.5f, 1, 3.6f));
        var col = ps.colorOverLifetime;
        col.enabled = true;
        col.color = FadeInOut(0.2f);
        var n = ps.noise;
        n.enabled = true;
        n.strength = 0.22f;
        n.frequency = 0.3f;
        n.scrollSpeed = 0.12f;
        var v = ps.velocityOverLifetime;
        v.enabled = true;
        v.space = ParticleSystemSimulationSpace.World;
        v.x = new ParticleSystem.MinMaxCurve(0.05f, 0.18f);
        v.y = new ParticleSystem.MinMaxCurve(0f, 0f);
        v.z = new ParticleSystem.MinMaxCurve(-0.03f, 0.06f);
        return ps;
    }

    /// 殿里香炉上的细烟（评审：殿里的香炉一点烟都没有，上香的特写死气沉沉）：几缕细细的、慢慢往上打着卷的烟，很淡、略带一点灯的暖色。
    /// k 是浓淡（中间那只 1，两边小香炉 0.55）
    static ParticleSystem BuildHallSmoke(Transform parent, Vector3 at, float k, string name)
    {
        // 第五轮（评审：殿里的烟有了，可是几乎看不见，0.13 太淡）：香头那一截浓一点（0.3），往上越飘越淡（colorOverLifetime）；
        // 上香以后 40 秒再浓一些（Offerings 按 hallBoost 调 startColor 的不透明度）
        var mat = ParticleMaterial("smoke_hall", DotTexture(), new Color(0.9f, 0.86f, 0.8f, 0.3f), false, true);
        var ps = Particles(name, parent, mat);
        ps.transform.position = at;
        ps.transform.rotation = Quaternion.Euler(-90, 0, 0);
        var m = ps.main;
        m.startLifetime = new ParticleSystem.MinMaxCurve(5.5f, 8.5f);
        m.startSpeed = new ParticleSystem.MinMaxCurve(0.12f, 0.2f);
        m.startSize = new ParticleSystem.MinMaxCurve(0.05f * k + 0.03f, 0.1f * k + 0.04f);
        m.startRotation = new ParticleSystem.MinMaxCurve(0, Mathf.PI * 2);
        m.maxParticles = 120;
        m.simulationSpace = ParticleSystemSimulationSpace.World;
        var e = ps.emission;
        e.rateOverTime = 2.2f * k + 0.8f;
        var sh = ps.shape;
        sh.shapeType = ParticleSystemShapeType.Cone;
        sh.angle = 2f;
        sh.radius = 0.035f * k + 0.01f;
        var sz = ps.sizeOverLifetime;
        sz.enabled = true;
        sz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0, 0.6f, 1, 4.2f));
        var col = ps.colorOverLifetime;
        col.enabled = true;
        // 一冒出来就浓（香头上那一截看得见），往上散开、变淡
        var g = new Gradient();
        g.SetKeys(new[] { new GradientColorKey(Color.white, 0), new GradientColorKey(Color.white, 1) },
            new[] { new GradientAlphaKey(0f, 0), new GradientAlphaKey(1f, 0.05f), new GradientAlphaKey(0.55f, 0.3f), new GradientAlphaKey(0.2f, 0.65f), new GradientAlphaKey(0f, 1) });
        col.color = g;
        // 两边供桌上的小香炉淡一点（同一个材质）
        m.startColor = new Color(1f, 1f, 1f, k >= 1f ? 0.75f : 0.6f);
        // 打卷：噪声频率高一点、强度小，烟一缕缕地扭着往上，不是一团
        var n = ps.noise;
        n.enabled = true;
        n.strength = 0.1f;
        n.frequency = 0.9f;
        n.scrollSpeed = 0.25f;
        n.octaveCount = 2;
        var v = ps.velocityOverLifetime;
        v.enabled = true;
        v.space = ParticleSystemSimulationSpace.World;
        v.x = new ParticleSystem.MinMaxCurve(-0.015f, 0.025f);
        v.y = new ParticleSystem.MinMaxCurve(0.02f, 0.06f);
        v.z = new ParticleSystem.MinMaxCurve(-0.02f, 0.01f);
        return ps;
    }

    /// 系上布条时散开的一小团金色光点
    static ParticleSystem BuildSparkle(Transform parent)
    {
        // 原来亮到 2.6、一粒到 4 厘米：系布条的特写里镜头离布条只有 1.3–1.5 米，光点亮过泛光的门槛（1.0），一粒泛成一团团白色的大圆斑。
        // 现在不过门槛、小一些（金色的细点，不泛光）；往镜头飘过来的淡掉（离镜头 1 米以内看不见，1.6 米以外照常——特写镜头离那一格 1.35–1.5 米）
        var mat = ParticleMaterial("sparkle", DotTexture(), new Color(1.0f, 0.78f, 0.38f, 1f), true, false);
        mat.SetVector("_Near", new Vector4(1.0f, 1.6f, 0f, 0f));
        var ps = Particles("Sparkle", parent, mat);
        var m = ps.main;
        m.startLifetime = new ParticleSystem.MinMaxCurve(1.2f, 2.4f);
        m.startSpeed = new ParticleSystem.MinMaxCurve(0.12f, 0.5f);
        m.startSize = new ParticleSystem.MinMaxCurve(0.008f, 0.022f);
        m.gravityModifier = -0.03f;
        m.maxParticles = 120;
        m.simulationSpace = ParticleSystemSimulationSpace.World;
        var sh = ps.shape;
        sh.shapeType = ParticleSystemShapeType.Sphere;
        sh.radius = 0.2f;
        var col = ps.colorOverLifetime;
        col.enabled = true;
        col.color = FadeInOut(0.1f);
        var n = ps.noise;
        n.enabled = true;
        n.strength = 0.15f;
        n.frequency = 0.8f;
        return ps;
    }

    /// 硬币入水溅起的水花
    static ParticleSystem BuildSplash(Transform parent)
    {
        var mat = ParticleMaterial("coin_splash", DotTexture(), new Color(0.92f, 0.96f, 1f, 0.55f), false, true);
        var ps = Particles("CoinSplash", parent, mat);
        ps.transform.rotation = Quaternion.Euler(-90, 0, 0);
        var m = ps.main;
        m.startLifetime = new ParticleSystem.MinMaxCurve(0.45f, 0.8f);
        m.startSpeed = new ParticleSystem.MinMaxCurve(1.2f, 2.6f);
        m.startSize = new ParticleSystem.MinMaxCurve(0.012f, 0.035f);
        m.gravityModifier = 1f;
        m.maxParticles = 120;
        m.simulationSpace = ParticleSystemSimulationSpace.World;
        var sh = ps.shape;
        sh.shapeType = ParticleSystemShapeType.Cone;
        sh.angle = 26f;
        sh.radius = 0.03f;
        var col = ps.colorOverLifetime;
        col.enabled = true;
        col.color = FadeInOut(0.05f);
        return ps;
    }

    /// 其他人的路线：从哪里进出、散步去哪些地方；座位区的过道和总控用同一套
    static void ConfigureCrowd(GameDirector game, Vector3 entrance, Vector3 inside, Vector3[] strolls, Vector3[] strollLooks, bool bench)
    {
        var p = game.pilgrims;
        p.entrance = entrance;
        p.entranceInside = inside;
        p.strollPoints = strolls;
        p.strollLooks = strollLooks;
        p.benchSeats = bench;
        p.aislePoint = game.aislePoint;
        p.aisleDir = game.aisleDir;
        p.seatExitNeg = game.seatExitNeg;
        p.seatExitPos = game.seatExitPos;
        p.seatLook = game.seatLook;
        p.seatStraight = game.seatStraight;
        game.benchSeats = bench;
    }

    /// 会挡镜头的：墙、屋顶、台基这类大块的
    static readonly string[] CameraBlockers = { "Walls", "Wall", "WallCap", "WallCaps", "WallFoot", "BackWall", "Body", "Gate", "Tower", "TowerTrim", "Spire",
        "Roof", "Tiles", "TileRibs", "Ridge", "Eaves", "Platform", "Floor", "GateFloor", "Porch", "Arches", "Cornice", "Trim", "Door" };
    public const int NoCameraLayer = 9;

    /// 给建筑加上碰撞（人走路、镜头躲墙用）。树叶、布条、发光的窗格、水面这些不加
    static void AddColliders()
    {
        var skip = new[] { "Leaves", "Ribbons", "Lattice", "LanternGlow", "Water", "Flames", "Candles", "Rose", "Lancets", "Mountains", "Outside", "Paths", "Path", "BoardWords", "BoardGold", "Board", "LampGlow", "DoorLampGlow", "CypressLeaves", "BurnerAsh", "TreeBedMoss", "RoofUnder", "LampIron", "DoorLampIron", "DoorIron" };
        foreach (var mf in Object.FindObjectsByType<MeshFilter>(FindObjectsSortMode.None))
        {
            if (skip.Contains(mf.name) || mf.GetComponent<Collider>() != null) continue;
            if (mf.GetComponentInParent<Folk>() != null) continue;
            if (mf.transform.parent != null && mf.transform.root.name == "Plants") continue;
            if (mf.name.Contains("Maple") && mf.name.Contains("Leaves")) continue;
            var mc = mf.gameObject.AddComponent<MeshCollider>();
            mc.sharedMesh = mf.sharedMesh;
            // 细东西（柱子、灯笼、树干、香炉、长椅……）人会撞上，但镜头直接穿过去，不为它们收近：
            // 不然人一走，镜头扫过柱子就一下凑近一下拉远，整个画面忽大忽小
            if (!CameraBlockers.Contains(mf.name)) mf.gameObject.layer = NoCameraLayer;
        }
        // 外面的草地和远处用一大块平板接住，不至于掉下去
        var ground = new GameObject("GroundCollider");
        var box = ground.AddComponent<BoxCollider>();
        box.center = new Vector3(0, -0.55f, 0);
        box.size = new Vector3(200, 1, 200);
        // 院子外面不让走太远：山门外留一段，其余三面靠院墙
        foreach (var (c, size) in new[] { (new Vector3(0, 2, -24f), new Vector3(40, 4, 1)), (new Vector3(-14.5f, 2, -19f), new Vector3(1, 4, 12)), (new Vector3(14.5f, 2, -19f), new Vector3(1, 4, 12)) })
        {
            var wall = new GameObject("BoundCollider");
            var b = wall.AddComponent<BoxCollider>();
            b.center = c;
            b.size = size;
        }
    }

    /// 把运行时的东西都建好、互相接上，返回总控（地点和路线由各个场景自己填）。
    /// seats：蒲团或长椅上的座位点；slots：树上能挂东西的点；incenseAt：香插在哪；poolAt：许愿池水面中心。
    static GameDirector BuildRuntime(string music, string bell, Transform seats, Transform slots, Material ribbon, Vector3? incenseAt, Vector3? poolAt, float poolRadius, bool topDown = false)
    {
        ConfigureAudio();
        var camGo = Camera.main.gameObject;
        PlayerCamera follow;
        if (topDown)
        {
            // 湖心小寺：三种跟法都挂上，由 ViewSwitcher 切换（默认俯视）
            camGo.AddComponent<TopDownCamera>();
            var tpc = camGo.AddComponent<ThirdPersonCamera>();
            tpc.blockers = ~((1 << 2) | (1 << NoCameraLayer));
            tpc.enabled = false;
            camGo.AddComponent<FirstPersonCamera>().enabled = false;
            follow = camGo.AddComponent<ViewSwitcher>();
        }
        else follow = camGo.AddComponent<ThirdPersonCamera>();
        string style = topDown ? "toon_" : "";

        var game = new GameObject("Game");
        var sound = game.AddComponent<WorldAudio>();
        sound.musicName = music;

        // 自己：外面一层带碰撞的胶囊（不缩放），里面是 Q 版小人
        var looks = FolkLooks.Select(l => AssetDatabase.LoadAssetAtPath<GameObject>($"{FolkDir}/Folk_{style}{l.name}.prefab")).ToArray();
        // 湖心小寺：自己和别人都用动漫人物（Assets/Characters/Anime 下转好的那些，见 BuildAnime.cs）。
        // 第 0 个是自己（shino），其余的给别的用户和香客，按人挑一张脸，再换发色衣服色（AnimeVariant）
        if (topDown)
        {
            var anime = new System.Collections.Generic.List<GameObject>();
            var me0 = AssetDatabase.LoadAssetAtPath<GameObject>($"{FolkDir}/Folk_anime_shino.prefab");
            foreach (string f in System.IO.Directory.GetFiles(FolkDir, "Folk_anime_*.prefab"))
            {
                var g = AssetDatabase.LoadAssetAtPath<GameObject>(f.Replace('\\', '/'));
                if (g != null && g != me0) anime.Add(g);
            }
            if (me0 != null && anime.Count > 0)
            {
                anime.Sort((x, y) => string.CompareOrdinal(x.name, y.name));
                anime.Insert(0, me0);
                looks = anime.ToArray();
            }
        }
        var playerRoot = new GameObject("Player");
        var cc = playerRoot.AddComponent<CharacterController>();
        cc.radius = 0.22f;
        cc.height = 1.15f;
        cc.center = new Vector3(0, 0.6f, 0);
        cc.stepOffset = 0.3f;
        cc.slopeLimit = 50f;
        cc.skinWidth = 0.03f;
        var me = (GameObject)PrefabUtility.InstantiatePrefab(looks[0]);
        me.transform.SetParent(playerRoot.transform, false);
        var player = me.GetComponent<Folk>();
        player.controller = cc;
        player.walkSpeed = 1.0f;
        follow.target = me.transform;
        // 镜头只被建筑挡，不被人挡
        if (follow is ThirdPersonCamera tp) tp.blockers = ~((1 << 2) | (1 << NoCameraLayer));
        playerRoot.layer = 2;

        var pilgrims = game.AddComponent<Pilgrims>();
        pilgrims.seatsRoot = seats;
        pilgrims.looks = looks;

        if (topDown) AddToonColliders(); else AddColliders();

        var off = game.AddComponent<Offerings>();
        off.slots = slots;
        off.ribbonMaterial = ribbon;
        if (topDown)
        {
            // 卡通版的供品：整块的颜色，按普通模型的方式上色（摆动幅度在红色通道）
            Material Flat(string name, Color c, float sway, Color? glow = null) => ToonMat(name, m =>
            {
                m.SetFloat("_Legacy", 1f);
                m.SetFloat("_Sway", sway);
                m.SetFloat("_Cull", 0f);
                m.SetFloat("_WetAmount", 0f);
                m.SetFloat("_SnowAmount", 0f);
                m.SetColor("_BaseColor", c);
                m.SetColor("_EmissionColor", glow ?? Color.black);
            });
            // 木牌：颜色在贴图里（木纹 + 写的字，运行时每块一张），正反面分开、各画朝外的一面
            off.plaqueMaterial = ToonMat("o_plaque", m =>
            {
                m.SetFloat("_Legacy", 1f);
                m.SetFloat("_Sway", 1f);
                m.SetFloat("_Cull", 2f);
                m.SetFloat("_WetAmount", 0.5f);
                m.SetFloat("_SnowAmount", 0f);
                m.SetFloat("_Detail", 0f);
                m.SetColor("_BaseColor", Color.white);
                m.SetColor("_EmissionColor", Color.black);
                m.SetColor("_RimColor", new Color(1, 1, 1, 0.08f));
            });
            off.stickMaterial = Flat("o_stick", new Color(0.62f, 0.20f, 0.14f), 0f);
            // 香头的火：深一点的橙红打底、橙色发光（评审：以前 (4, 1.2, 0.3) 加上浅橙的底色，泛光里成了一点白，像一截白灰）
            off.emberMaterial = Flat("o_ember", new Color(0.55f, 0.13f, 0.035f), 0f, new Color(3.0f, 0.95f, 0.22f));
            off.coinMaterial = Flat("o_coin", new Color(0.95f, 0.78f, 0.36f), 0f);
            // 布条、木牌按真实大小做（布条 0.14 × 0.62 米、木牌 0.20 × 0.26 米），不再放大
            off.ribbonScale = Vector3.one;
            off.plaqueScale = Vector3.one;
            off.incenseScale = new Vector3(4.5f, 2.2f, 4.5f);
        }
        else
        {
            var plaque = Mat("plaque", "wood_cedar", 0.5f, new Color(0.95f, 0.80f, 0.60f), rough: 0.8f, wet: 0.3f, snow: 0f);
            plaque.SetFloat("_Sway", 1f);
            off.plaqueMaterial = plaque;
            off.stickMaterial = Mat("incense_stick", null, 1f, new Color(0.42f, 0.16f, 0.10f), rough: 0.9f, wet: 0f, snow: 0f);
            var ember = Emissive("ember", new Color(0.9f, 0.3f, 0.1f));
            ember.SetColor("_EmissionColor", new Color(5f, 1.3f, 0.3f));
            off.emberMaterial = ember;
            off.coinMaterial = Mat("coin", null, 1f, new Color(0.95f, 0.78f, 0.36f), rough: 0.3f, metallic: 1f, wet: 0f, snow: 0f);
        }
        off.sparkle = BuildSparkle(game.transform);
        if (incenseAt.HasValue)
        {
            var anchor = new GameObject("IncenseAnchor").transform;
            anchor.SetParent(game.transform, false);
            anchor.position = incenseAt.Value;
            off.incenseAnchor = anchor;
            off.smoke = BuildSmoke(game.transform, incenseAt.Value + Vector3.up * 0.05f);
        }
        if (poolAt.HasValue)
        {
            var pool = new GameObject("PoolAnchor").transform;
            pool.SetParent(game.transform, false);
            pool.position = poolAt.Value;
            off.pool = pool;
            off.poolRadius = poolRadius;
            off.splash = BuildSplash(game.transform);
        }

        var dir = game.AddComponent<GameDirector>();
        dir.player = player;
        dir.cam = follow;
        dir.pilgrims = pilgrims;
        dir.offerings = off;
        dir.sound = sound;
        dir.bell = bell;
        return dir;
    }
}
