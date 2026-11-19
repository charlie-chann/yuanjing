using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using Yuanjing;

/// 湖心小寺的新大殿（spec A–C）：殿本身、三世佛和背光、殿里的陈设、石台两边的太平缸，墙和地面的碰撞，殿里的灯。
/// 模型都是 tools/blender 里做的（buildings.py 的 hall、statues.py、hall_props.py），坐标见 handoff/hall.md、statues.md、props.md。
/// 殿里的玩法数据（拜垫、蒲团的点，自动走路要绕开的东西，能不能进殿 HallOpen）在 BuildIslet 里，这里只摆看得见的东西和挡人的墙。
public static partial class SanctuaryBuild
{
    /// 摆一个盒子碰撞（世界坐标的两个角）。layer 0 也挡镜头；NoCameraLayer 只挡人
    static BoxCollider HallBox(Transform parent, string name, Vector3 min, Vector3 max, int layer = 0)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        go.transform.position = (min + max) * 0.5f;
        go.isStatic = true;
        go.layer = layer;
        var b = go.AddComponent<BoxCollider>();
        b.size = max - min;
        return b;
    }

    /// 一根柱子的碰撞：竖着的胶囊，底在 bottom，再加一圈和覆盆一样粗的（高一米，人迈不上去）
    static void HallColumn(Transform parent, Vector3 bottom, float radius, float top, float baseRadius)
    {
        var go = new GameObject("Column");
        go.transform.SetParent(parent, false);
        go.transform.position = bottom;
        go.isStatic = true;
        go.layer = NoCameraLayer;
        var c = go.AddComponent<CapsuleCollider>();
        c.radius = radius;
        c.height = top - bottom.y;
        c.center = new Vector3(0, c.height * 0.5f, 0);
        // 柱础是圆的覆盆（下面那块方石只高 6 厘米）：按圆的挡，方石的角脚尖会踩上一点，门里那条窄道才走得过去。
        // 胶囊往地下伸（地面那一截是直的圆柱）：以前底在地面上，贴地那一截是胶囊的半球、越往下越细，人的胶囊顶上去是一个往上斜的面，
        // 当成坡往上爬、爬不上就卡住——从东侧门 x 3.0 一直往北推，每次都停在柱础西南边（HallWalkTest.SideDoors）
        var b = go.AddComponent<CapsuleCollider>();
        b.radius = baseRadius;
        b.height = 2f;
        b.center = new Vector3(0, 0f, 0);
    }

    /// 接触影子的材质：round 1 椭圆（人、圆蒲团、柱础、磬），0 圆角长方（拜垫、供桌、经案）
    static Material ContactMat(bool round) => ToonMat(round ? "contact_round" : "contact_rect", m =>
    {
        m.SetFloat("_Round", round ? 1f : 0f);
        m.SetFloat("_Soft", round ? 0.6f : 0.4f);
        m.SetFloat("_Strength", round ? 0.5f : 0.55f);
        m.SetColor("_Tint", new Color(0.32f, 0.24f, 0.2f, 1f));
        m.renderQueue = 3000 - 90;
    }, "Yuanjing/Contact");

    /// 地上放一块接触影子（殿里的灯不投影子，东西底下要有一圈暗才「落」在金砖上）：中心 at（地面高）、水平尺寸 sx × sz、绕竖轴转 yaw
    static void ContactQuad(Transform parent, string name, Vector3 at, float sx, float sz, float yaw, bool round)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        go.transform.SetPositionAndRotation(at + Vector3.up * 0.004f, Quaternion.Euler(90f, yaw, 0f));
        go.transform.localScale = new Vector3(sx, sz, 1f);
        go.AddComponent<MeshFilter>().sharedMesh = Resources.GetBuiltinResource<Mesh>("Quad.fbx");
        var r = go.AddComponent<MeshRenderer>();
        r.sharedMaterial = ContactMat(round);
        r.shadowCastingMode = ShadowCastingMode.Off;
        r.receiveShadows = false;
        r.lightProbeUsage = LightProbeUsage.Off;
        r.reflectionProbeUsage = ReflectionProbeUsage.Off;
        go.isStatic = true;
    }

    /// 殿里地上的接触影子：拜垫、蒲团的方草垫、四根金柱的柱础、供桌、佛坛前沿、功德箱、经案、磬、木鱼
    static void HallContacts(Transform inside, Transform hallSeats, Transform hallMats)
    {
        var g = Group("Contact", inside);
        float y = HallFloor;
        foreach (Transform km in hallMats) ContactQuad(g, "mat", new Vector3(km.position.x, y, km.position.z), 0.92f, 1.06f, km.eulerAngles.y, false);
        foreach (Transform hs in hallSeats)
        {
            Vector3 c = hs.position + hs.forward * 0.12f;
            ContactQuad(g, "seat", new Vector3(c.x, y, c.z), 1.04f, 1.04f, hs.eulerAngles.y, false);
            // 圆蒲团压在草垫上：再深一圈（草垫面 5 厘米高）
            ContactQuad(g, "zafu", new Vector3(hs.position.x, y + 0.05f, hs.position.z), 0.62f, 0.62f, 0f, true);
        }
        foreach (float sx in new[] { -1f, 1f })
            foreach (float z in new[] { 15.4f, 18.0f })
                ContactQuad(g, "column", new Vector3(sx * 2.8f, y, z), 1.15f, 1.15f, 0f, true);
        ContactQuad(g, "altar_table", new Vector3(0, y, 19.2f), 2.75f, 1.1f, 0f, false);
        foreach (float sx in new[] { -1f, 1f }) ContactQuad(g, "side_table", new Vector3(sx * 3.6f, y, 19.35f), 1.8f, 0.9f, 0f, false);
        ContactQuad(g, "dais", new Vector3(0, y, 20.0f), 11.95f, 0.55f, 0f, false);
        ContactQuad(g, "donation_box", new Vector3(1.45f, y, 15.5f), 0.78f, 1.02f, 0f, false);
        ContactQuad(g, "sutra_desk", new Vector3(-5.35f, y, 18.95f), 1.55f, 0.78f, 0f, false);
        ContactQuad(g, "qing", new Vector3(5.0f, y, 18.95f), 0.72f, 0.72f, 0f, true);
        ContactQuad(g, "muyu", new Vector3(5.8f, y, 18.95f), 0.72f, 0.7f, 0f, true);
    }

    // ── 金砖地的反光：在殿里烘一张环境图（白天、夜里各一张），地面的着色器按盒子投影取（YJToon 的 _Floor）──
    static readonly Vector3 FloorProbeAt = new Vector3(0f, 1.2f, 17.6f);
    static readonly Vector3 FloorBoxMin = new Vector3(-6.47f, HallFloor, 14.42f), FloorBoxMax = new Vector3(6.47f, 5.9f, 21.98f);

    /// 场景摆好以后调：在殿中间离地 1.2 米的地方朝六个方向各拍一张（不画人、不画院子里的东西），存成两张立方体贴图，给金砖地的材质
    static void BakeHallReflection(TimeWeather tw)
    {
        var mat = ToonMat("jinzhuan");
        var day = BakeCube(tw, DayTime.Day, "Assets/Toon/Textures/hall_refl_day.asset");
        var night = BakeCube(tw, DayTime.Night, "Assets/Toon/Textures/hall_refl_night.asset");
        tw.ApplyImmediate(DayTime.Day, Weather.Clear);
        mat.SetTexture("_FloorCube", day);
        mat.SetTexture("_FloorCubeNight", night);
        mat.SetVector("_FloorProbe", FloorProbeAt);
        mat.SetVector("_FloorBoxMin", FloorBoxMin);
        mat.SetVector("_FloorBoxMax", FloorBoxMax);
        EditorUtility.SetDirty(mat);
    }

    static Cubemap BakeCube(TimeWeather tw, DayTime time, string path)
    {
        tw.ApplyImmediate(time, Weather.Clear);
        foreach (var ic in UnityEngine.Object.FindObjectsByType<InteriorCull>(FindObjectsSortMode.None)) ic.Set(2);
        const int size = 128;
        var go = new GameObject("FloorProbeCam");
        var cam = go.AddComponent<Camera>();
        go.transform.position = FloorProbeAt;
        cam.nearClipPlane = 0.05f;
        cam.farClipPlane = 60f;
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = Color.black;
        // 只拍殿和殿里的东西（人、小动物在别的层也不碍事：编辑器里没有香客）
        cam.cullingMask = ~0;
        cam.enabled = false;
        var cube = new Cubemap(size, TextureFormat.RGBAHalf, true);
        // 一面一面地拍（Camera.RenderToCubemap 在 URP 里返回 true，但读回来的是一堆乱数）
        bool ok = false;
        {
            // 渲染管线不支持直接拍立方体：一面一面地拍（每面 90 度、正方形），按 Unity 立方体贴图每一面的朝向摆镜头
            cam.fieldOfView = 90f;
            cam.aspect = 1f;
            var rt = new RenderTexture(size, size, 24, RenderTextureFormat.ARGBHalf, RenderTextureReadWrite.Linear);
            var tex = new Texture2D(size, size, TextureFormat.RGBAHalf, false, true);
            var faces = new (CubemapFace f, Vector3 fwd, Vector3 up)[]
            {
                (CubemapFace.PositiveX, Vector3.right, Vector3.down), (CubemapFace.NegativeX, Vector3.left, Vector3.down),
                (CubemapFace.PositiveY, Vector3.up, Vector3.forward), (CubemapFace.NegativeY, Vector3.down, Vector3.back),
                (CubemapFace.PositiveZ, Vector3.forward, Vector3.down), (CubemapFace.NegativeZ, Vector3.back, Vector3.down),
            };
            cam.targetTexture = rt;
            foreach (var (f, fwd, up) in faces)
            {
                go.transform.rotation = Quaternion.LookRotation(fwd, -up);
                cam.Render();
                cam.Render();
                RenderTexture.active = rt;
                tex.ReadPixels(new Rect(0, 0, size, size), 0, 0);
                tex.Apply();
                // 立方体贴图每一面的像素是从上往下存的：上下翻一下
                var px = tex.GetPixels();
                var flip = new Color[px.Length];
                for (int y = 0; y < size; y++) Array.Copy(px, y * size, flip, (size - 1 - y) * size, size);
                cube.SetPixels(flip, f);
            }
            cam.targetTexture = null;
            RenderTexture.active = null;
            UnityEngine.Object.DestroyImmediate(rt);
            UnityEngine.Object.DestroyImmediate(tex);
        }
        cube.Apply(true);
        string Px(CubemapFace f) { var c = cube.GetPixel(f, size / 2, size / 2); return $"{c.r:F2},{c.g:F2},{c.b:F2}"; }
        Debug.Log($"[yuanjing] 金砖地反光图 {time}（存之前）：+z（佛像）{Px(CubemapFace.PositiveZ)} -z（门）{Px(CubemapFace.NegativeZ)} -y（地）{Px(CubemapFace.NegativeY)} +y（天花）{Px(CubemapFace.PositiveY)} +x {Px(CubemapFace.PositiveX)}");
        UnityEngine.Object.DestroyImmediate(go);
        AssetDatabase.DeleteAsset(path);
        AssetDatabase.CreateAsset(cube, path);
        Debug.Log($"[yuanjing] 金砖地反光图 {time}：{(ok ? "RenderToCubemap" : "一面一面拍")} → {path}");
        return AssetDatabase.LoadAssetAtPath<Cubemap>(path);
    }

    static void HallLight(Transform parent, string name, Vector3 at, float range, float intensity)
    {
        var l = PointLamp(parent, at, range, intensity);
        l.name = name;
        // 殿里的灯比院子里的灯笼白一点（太橙了金像会变成一片柠檬黄）
        l.color = new Color(1f, 0.87f, 0.70f);
    }

    /// 摆新大殿和殿里的一切。hallSeats、hallMats 是玩法那边的点（蒲团、拜垫的模型照着它们摆）
    static Transform BuildHall(Transform structure, Transform hallSeats, Transform hallMats, List<Renderer> lampRenderers)
    {
        var root = Group("hall", structure);
        var building = Put("hall", root, HallAt, 0, 1f, "building");

        // ── 三世佛和背光（statues.md §3）：原点都是莲座底面中心，背光和佛像放在同一点；比例 1（两边的已经按 0.85 做好）、朝南（yaw 0）。
        // 西边阿弥陀、东边药师（东方药师、西方阿弥陀，statues.md §7）
        var inside = Group("Inside", root);
        Put("buddha_center", inside, new Vector3(0, 1.57f, 21.05f));
        Put("buddha_west", inside, new Vector3(-3.6f, 1.57f, 21.05f));
        Put("buddha_east", inside, new Vector3(3.6f, 1.57f, 21.05f));
        Put("mandorla_center", inside, new Vector3(0, 1.57f, 21.05f));
        Put("mandorla_side", inside, new Vector3(-3.6f, 1.57f, 21.05f), 0, 1f, "mandorla_west");
        Put("mandorla_side", inside, new Vector3(3.6f, 1.57f, 21.05f), 0, 1f, "mandorla_east");
        // 佛像、背光的模型里存了几档简化（YjmImporter 的 Mesh LOD）：不参加静态合批（合批以后就不按远近挑了），它们各自一件，合批也省不了什么
        foreach (Transform t in inside)
            foreach (var g in t.GetComponentsInChildren<Transform>())
                GameObjectUtility.SetStaticEditorFlags(g.gameObject, GameObjectUtility.GetStaticEditorFlags(g.gameObject) & ~StaticEditorFlags.BatchingStatic);
        // 佛像、莲座、背光撑子的金换成佛像自己的鎏金（toon_gilt：照见殿里的明暗、金箔，BuildIslet.ToonMaterials）；供桌、宫灯这些还用 toon_gold
        var gilt = ToonMat("gilt");
        foreach (Transform t in inside)
            foreach (var r in t.GetComponentsInChildren<MeshRenderer>())
                if (r.name == "gold") r.sharedMaterial = gilt;

        // ── 殿里的陈设（props.md §4 的 LAYOUT，第二轮）。yaw 是 Unity 的（俯视顺时针），模型正面朝 -z
        Put("altar_dais", inside, new Vector3(0, HallFloor, 20.975f));
        Put("altar_table", inside, new Vector3(0, HallFloor, 19.2f));
        Put("censer_hall", inside, new Vector3(0, 1.504f, 19.0f));
        foreach (float sx in new[] { -1f, 1f })
        {
            Put("altar_table_side", inside, new Vector3(sx * 3.6f, HallFloor, 19.35f));
            Put("candlestick", inside, new Vector3(sx * 0.52f, 1.504f, 19.15f));
            Put("flower_vase", inside, new Vector3(sx * 0.94f, 1.504f, 19.22f));
            Put("oil_lamp", inside, new Vector3(sx * 0.24f, 1.504f, 19.4f));
            Put("censer_hall_side", inside, new Vector3(sx * 3.6f, 1.504f, 19.22f), 0, 0.75f);
            Put("candlestick", inside, new Vector3(sx * 4.15f, 1.504f, 19.35f), 0, 0.8f);
            Put("candlestick", inside, new Vector3(sx * 3.05f, 1.504f, 19.35f), 0, 0.8f);
            Put("fruit_plate", inside, new Vector3(sx * 3.88f, 1.504f, 19.45f));
            Put("fruit_plate_peach", inside, new Vector3(sx * 3.32f, 1.504f, 19.45f));
            Put("oil_lamp", inside, new Vector3(sx * 3.6f, 1.504f, 19.55f));
            // 宫灯挂在天花的肋条交叉点上（模型原点是挂点，往下垂）：前一对、后一对
            Put("palace_lantern", inside, new Vector3(sx * 1.98f, 5.9f, 16.7f));
            Put("palace_lantern", inside, new Vector3(sx * 2.64f, 5.9f, 19.3f));
        }
        // 幡：上联（仄声收尾）挂东边（面朝佛像时的右手），下联挂西边
        Put("banner_b", inside, new Vector3(1.98f, 5.9f, 19.95f));        // 法轮常转
        Put("banner", inside, new Vector3(-1.98f, 5.9f, 19.95f));         // 佛日增辉
        Put("banner_gold", inside, new Vector3(5.28f, 5.9f, 19.95f));     // 风调雨顺
        Put("banner_gold_b", inside, new Vector3(-5.28f, 5.9f, 19.95f));  // 国泰民安
        Put("qing", inside, new Vector3(5.0f, HallFloor, 18.95f));
        Put("muyu", inside, new Vector3(5.8f, HallFloor, 18.95f));
        Put("donation_box", inside, new Vector3(1.45f, HallFloor, 15.5f), 90);
        Put("sutra_desk", inside, new Vector3(-5.35f, HallFloor, 18.95f));
        // 拜垫、静坐的蒲团：照着玩法那边的点摆（同一个位置、同一个朝向），点挪了模型跟着挪
        foreach (Transform km in hallMats)
            Put("kneel_mat", inside, km.position, km.eulerAngles.y);
        foreach (Transform hs in hallSeats)
            Put("cushion_hall", inside, hs.position, hs.eulerAngles.y);
        HallContacts(inside, hallSeats, hallMats);

        // 烛火、油灯、香头白天也点着：换成自己的材质，改个名字（不进 lampRenderers，不跟着天色开关）；宫灯的绢面夜里跟着灯一起亮
        var flame = ToonMat("flame");
        var brass = ToonMat("brass");
        // 金砖地：换成金砖自己的材质（深、暖、带一层光泽；石板贴图看着像水泥）
        var jinzhuan = ToonMat("jinzhuan");
        foreach (var r in root.GetComponentsInChildren<MeshRenderer>())
            if (r.name == "in_floor") r.sharedMaterial = jinzhuan;
        // 殿里、殿外的朱漆（柱子、门窗、框）：朱红漆，不要樱桃木的木纹和节疤（评审）
        var lacquerCol = ToonMat("lacquer_col");
        foreach (var r in building.GetComponentsInChildren<MeshRenderer>())
            if (r.name == "in_lacquer" || r.name == "lacquer") r.sharedMaterial = lacquerCol;
        // 殿里的香炉也用擦亮的铜（天天有人上香、擦拭）：带锈的铜贴图在上香的特写里是一片橙色锈点，看着脏
        string[] polished = { "candlestick", "oil_lamp", "donation_box", "sutra_desk", "censer_hall", "censer_hall_side" };
        foreach (var r in inside.GetComponentsInChildren<MeshRenderer>())
        {
            // 供桌上的黄铜器、香炉是擦亮的，磬、缸这些深色的老铜还用带锈的铜
            if (r.name == "bronze" && polished.Contains(r.transform.parent.name)) r.sharedMaterial = brass;
            if (r.name == "glow")
            {
                r.sharedMaterial = flame;
                r.name = "flame";
                r.shadowCastingMode = ShadowCastingMode.Off;
            }
            else if (r.name == "paint_lantern") lampRenderers.Add(r);
        }

        // ── 石台两边的太平缸（props.md §4）
        foreach (float sx in new[] { -1f, 1f })
        {
            var vat = Put("water_vat", structure, new Vector3(sx * 9.2f, TerraceH, 5.5f));
            MeshLodGroup(vat, 0.08f, 0.04f);
            Solid(vat, 0.66f, 1.0f);
        }

        HallColliders(Group("Colliders", root));
        var lights = Group("Lights", root);
        HallLights(lights);

        // 佛像、背光、供桌、香炉、宫灯这些重的：远了换简化档（模型里存的 Mesh LOD，见 YjmImporter）。
        // 佛像、背光按 8 米多（iPhone 的画质档，殿里的视角）换一半、15 米外换四分之一：在殿里的过道、拜垫上都是原样，
        // 从石台上透过殿门看进去、从殿西边静坐区看东边那尊才换。
        // 陈设的颜色、旧色、描金都在顶点色里，简化了会糊一点：换得晚（在屏幕上只剩 6 %、3 % 高才换；一尺高的烛台九米外才换），殿里看都是原样
        foreach (Transform model in inside)
        {
            bool statue = model.name.StartsWith("buddha_") || model.name.StartsWith("mandorla_");
            MeshLodGroup(model.gameObject, statue ? 0.24f : 0.06f, statue ? 0.13f : 0.03f);
        }
        HallShadowProxy(building);

        // 殿里的东西不投太阳的影子：殿里整个在屋顶的影子里，它们的影子落不到亮处，白算（这一遍要把一百多万个三角形再画一次）。
        // 门口照进来的那一小块阳光里只有地面和门边的蒲团、功德箱，这几样照旧投影子
        string[] shadowKeep = { "cushion_hall", "kneel_mat", "donation_box" };
        var near = new List<Renderer>();
        var deep = new List<Renderer>();
        foreach (Transform model in inside)
        {
            bool nearDoor = shadowKeep.Contains(model.name);
            foreach (var r in model.GetComponentsInChildren<MeshRenderer>())
            {
                if (!nearDoor) r.shadowCastingMode = ShadowCastingMode.Off;
                (nearDoor ? near : deep).Add(r);
            }
        }
        foreach (var r in building.GetComponentsInChildren<MeshRenderer>())
            if (r.name.StartsWith("in_"))
            {
                r.shadowCastingMode = ShadowCastingMode.Off;
                near.Add(r);
            }
        // 镜头在殿外、透过门洞看不进去的时候，殿里的东西不画（InteriorCull 里有分档的说明）
        var cull = root.gameObject.AddComponent<InteriorCull>();
        cull.near = near.ToArray();
        cull.deep = deep.ToArray();
        cull.lights = lights.GetComponentsInChildren<Light>();
        cull.hall = Rect.MinMaxRect(-6.6f, 14.3f, 6.6f, 22.23f);

        // 殿里的环境光：墙里面换成暖的（门那一面慢慢过渡）
        var zone = root.gameObject.AddComponent<IndoorZone>();
        zone.min = new Vector3(-6.6f, 0.4f, 14.3f);
        zone.max = new Vector3(6.6f, 5.75f, 22.23f);
        zone.tint = new Color(1f, 0.9f, 0.76f);
        zone.Apply();
        return root;
    }

    /// 墙、地、台阶的碰撞（hall.md §6）。殿本身没有整块的碰撞盒：人从台阶走上台基、从三个门洞走进去。
    /// 墙、门上的横板、天花板在第 0 层（也挡镜头，镜头不会穿到墙外、屋顶里）；柱子、栏杆、门扇、矮的陈设在 NoCameraLayer（只挡人，镜头穿过去不会一顶一顶的）
    static void HallColliders(Transform c)
    {
        int nc = NoCameraLayer;
        // 台基：盖板顶 0.70；外面的石板高 1.5 厘米（0.735），殿里的金砖地面 0.72
        HallBox(c, "Platform", new Vector3(-8.6f, -0.9f, 10.9f), new Vector3(8.6f, 0.70f, 23.7f));
        HallBox(c, "Floor", new Vector3(-6.47f, 0.70f, 14.42f), new Vector3(6.47f, HallFloor, 21.98f));
        HallBox(c, "Porch", new Vector3(-8.35f, 0.70f, 11.15f), new Vector3(8.35f, 0.735f, 14.18f));
        HallBox(c, "SideWalkW", new Vector3(-8.35f, 0.70f, 14.18f), new Vector3(-6.73f, 0.735f, 23.45f));
        HallBox(c, "SideWalkE", new Vector3(6.73f, 0.70f, 14.18f), new Vector3(8.35f, 0.735f, 23.45f));
        HallBox(c, "BackWalk", new Vector3(-6.73f, 0.70f, 22.23f), new Vector3(6.73f, 0.735f, 23.45f));
        // 门槛那一条（门槛本身高 0.77，只有 5 厘米，不挡脚）：和廊下的石板一样高，进门不会先往下掉
        HallBox(c, "Threshold", new Vector3(-3.75f, 0.70f, 14.18f), new Vector3(3.75f, 0.735f, 14.42f));
        // 四级台阶（hall.md §4：每级 0.175 高、0.36 深，宽 4.7），两边的垂带挡住（只能走台阶上去）
        for (int k = 0; k < 4; k++)
        {
            float z0 = 10.92f - 0.36f * (4 - k), top = k == 3 ? 0.697f : 0.175f * (k + 1);
            HallBox(c, $"Step{k}", new Vector3(-2.35f, top - 0.175f, z0), new Vector3(2.35f, top, 10.92f));
        }
        // 走台阶的斜坡（StairRamp）：人的原点贴着它上下，穿过每一级踏面的正中间（第一级踏面中间 z 9.66 高 0.175 … 第四级 z 10.74 高 0.697，
        // 每 0.36 米高 0.175），两头接地面（石台 TerraceH）和台基面 0.70；一级级的高低让脚自己踩（Folk.GroundIK）
        {
            var ramp = c.gameObject.AddComponent<Yuanjing.StairRamp>();
            const float slope = 0.175f / 0.36f;
            // 区域往南多给 0.35 米：走到台阶跟前、脚尖快碰到第一级的时候，脚下的补偿已经完全起作用
            ramp.area = new Rect(-2.35f, 8.85f, 4.7f, 10.95f - 8.85f);
            ramp.y0 = TerraceH;
            ramp.z0 = 9.66f - (0.175f - TerraceH) / slope;
            ramp.y1 = 0.70f;
            ramp.z1 = 9.66f + (0.70f - 0.175f) / slope;
        }
        foreach (float sx in new[] { -1f, 1f })
            HallBox(c, "StepCheek", new Vector3(Mathf.Min(sx * 2.35f, sx * 2.75f), -0.2f, 9.2f), new Vector3(Mathf.Max(sx * 2.35f, sx * 2.75f), 1.5f, 10.92f), nc);
        // 栏杆（顶约 1.6）
        foreach (float sx in new[] { -1f, 1f })
        {
            HallBox(c, "RailFront", new Vector3(Mathf.Min(sx * 2.9f, sx * 8.48f), 0.70f, 10.935f), new Vector3(Mathf.Max(sx * 2.9f, sx * 8.48f), 1.6f, 11.105f), nc);
            HallBox(c, "RailSide", new Vector3(sx * 8.48f - 0.085f, 0.70f, 11.02f), new Vector3(sx * 8.48f + 0.085f, 1.6f, 23.58f), nc);
        }
        HallBox(c, "RailBack", new Vector3(-8.48f, 0.70f, 23.495f), new Vector3(8.48f, 1.6f, 23.665f), nc);
        // 墙：两侧、后墙（y 0.7..5.5）；前檐墙两边的槛窗、门两边的柱子和抱框、门洞上面那一条（中槛以上都是实的）
        foreach (float sx in new[] { -1f, 1f })
        {
            HallBox(c, "SideWall", new Vector3(sx * 6.6f - 0.13f, 0.70f, 14.3f), new Vector3(sx * 6.6f + 0.13f, 5.5f, 22.23f));
            HallBox(c, "WindowBay", new Vector3(Mathf.Min(sx * 3.96f, sx * 6.6f), 0.70f, 14.18f), new Vector3(Mathf.Max(sx * 3.96f, sx * 6.6f), 3.62f, 14.42f));
            foreach (float jx in new[] { 1.32f, 3.96f })
                HallBox(c, "Jamb", new Vector3(sx * jx - 0.21f, 0.70f, 14.1f), new Vector3(sx * jx + 0.21f, 3.62f, 14.5f));
            // 往里开着、两两叠在门边的门扇（z 14.45..14.99）：第 0 层，也挡镜头（hall.md §6 和墙一起；镜头不会从门扇里穿过去）
            foreach (float lx in new[] { 3.576f, 1.705f, 0.936f })
                HallBox(c, "DoorLeaves", new Vector3(sx * lx - 0.11f, 0.79f, 14.45f), new Vector3(sx * lx + 0.11f, 3.61f, 14.99f));
        }
        HallBox(c, "BackWall", new Vector3(-6.47f, 0.70f, 21.97f), new Vector3(6.47f, 5.5f, 22.23f));
        HallBox(c, "DoorBand", new Vector3(-6.6f, 3.62f, 14.18f), new Vector3(6.6f, 5.5f, 14.42f));
        // 还不让进殿的时候（BuildIslet.HallOpen 为 false），三个门洞拦一道只挡人的隔板（第 2 层：不挡镜头、不挡点画面、不挡往地上打的射线）
        if (!HallOpen)
            HallBox(c, "DoorShut", new Vector3(-3.75f, 0.70f, 14.18f), new Vector3(3.75f, 3.62f, 14.42f), 2);
        // 天花板：殿里在天花梁下面（梁底 5.35，镜头最高到 5.05）；廊下的天花底 4.90
        HallBox(c, "Ceiling", new Vector3(-6.47f, 5.30f, 14.42f), new Vector3(6.47f, 5.80f, 21.98f));
        HallBox(c, "PorchCeiling", new Vector3(-6.8f, 4.90f, 12.3f), new Vector3(6.8f, 5.40f, 14.18f));
        // 柱子：廊下一排、门那一排的两个角（墙里的已经在墙的盒子里）、殿里四根金柱
        foreach (float sx in new[] { -1f, 1f })
        {
            foreach (float x in new[] { 1.32f, 3.96f, 6.6f })
                HallColumn(c, new Vector3(sx * x, 0.735f, 12.5f), 0.22f, 4.5f, 0.31f);
            HallColumn(c, new Vector3(sx * 6.6f, 0.735f, 14.3f), 0.22f, 4.5f, 0.31f);
            foreach (float z in new[] { 15.4f, 18.0f })
                HallColumn(c, new Vector3(sx * 2.8f, HallFloor, z), 0.24f, 5.35f, 0.33f);
            // 两侧墙里的檐柱（z 16.94、19.58）：往殿里凸出 7 厘米（里面到 |x| 6.395），墙的盒子只到 6.47，贴着墙走会蹭进柱子里
            foreach (float z in new[] { 16.94f, 19.58f })
                HallColumn(c, new Vector3(sx * 6.6f, HallFloor, z), 0.21f, 4.5f, 0.25f);
        }
        // 佛坛（顶 1.57）和三尊像：只是挡镜头（人上不去佛坛）
        HallBox(c, "Dais", new Vector3(-5.81f, HallFloor, 19.995f), new Vector3(5.81f, 1.57f, 21.955f));
        HallBox(c, "BuddhaCenter", new Vector3(-0.85f, 1.57f, 20.2f), new Vector3(0.85f, 4.47f, 21.9f));
        foreach (float sx in new[] { -1f, 1f })
            HallBox(c, "BuddhaSide", new Vector3(sx * 3.6f - 0.725f, 1.57f, 20.325f), new Vector3(sx * 3.6f + 0.725f, 4.04f, 21.775f));
        // 供桌、磬、木鱼、功德箱、经案（props.md §5 的碰撞盒），矮，只挡人
        HallBox(c, "AltarTable", new Vector3(-1.22f, HallFloor, 18.8f), new Vector3(1.22f, 1.51f, 19.6f), nc);
        foreach (float sx in new[] { -1f, 1f })
            HallBox(c, "SideTable", new Vector3(sx * 3.6f - 0.77f, HallFloor, 19.025f), new Vector3(sx * 3.6f + 0.77f, 1.51f, 19.675f), nc);
        HallBox(c, "Qing", new Vector3(4.75f, HallFloor, 18.7f), new Vector3(5.25f, 1.47f, 19.2f), nc);
        HallBox(c, "Muyu", new Vector3(5.535f, HallFloor, 18.705f), new Vector3(6.065f, 1.54f, 19.195f), nc);
        HallBox(c, "DonationBox", new Vector3(1.19f, HallFloor, 15.12f), new Vector3(1.71f, 1.58f, 15.88f), nc);
        HallBox(c, "SutraDesk", new Vector3(-5.99f, HallFloor, 18.69f), new Vector3(-4.71f, 1.51f, 19.21f), nc);
    }

    /// 一件模型远了换简化档：模型里每个大部件存了几档简化的网格（Mesh LOD，YjmImporter，每档约减半），引擎自己挑档不起作用，
    /// 这里给每个这样的部件再挂两个同样的渲染器，分别只画第 1 档（约一半）、第 2 档（约四分之一），用 LODGroup 按屏幕上的大小切：
    /// 模型在屏幕上的高度比例（乘画质的 lodBias，iPhone 那一档 0.7）不到 near 换第 1 档，不到 far 换第 2 档，一直画（不剔掉）。
    /// 没存简化档的小部件（烛火、绢面、几百个三角形的）每档都用同一个。第 0 档也写明只画第 0 档（不让引擎自己挑）。
    /// 着色器没有 LOD 交叉淡化，直接换（换的地方离得远，看不出跳）。带简化档的不参加静态合批（合批以后就不能挑档了）
    static void MeshLodGroup(GameObject model, float near, float far)
    {
        var parts = new List<MeshRenderer>();
        foreach (var r in model.GetComponentsInChildren<MeshRenderer>())
            if (r.TryGetComponent(out MeshFilter mf) && mf.sharedMesh != null) parts.Add(r);
        if (!parts.Exists(r => r.GetComponent<MeshFilter>().sharedMesh.lodCount >= 3)) return;
        var levels = new[] { new List<Renderer>(), new List<Renderer>(), new List<Renderer>() };
        foreach (var r in parts)
        {
            var mesh = r.GetComponent<MeshFilter>().sharedMesh;
            if (mesh.lodCount < 3)
            {
                foreach (var l in levels) l.Add(r);
                continue;
            }
            NoStaticBatch(r.gameObject);
            r.forceMeshLod = 0;
            levels[0].Add(r);
            for (int k = 1; k <= 2; k++) levels[k].Add(LodCopy(r, mesh, $"{r.name}_lod{k}", k, r.shadowCastingMode));
        }
        var lg = model.GetComponent<LODGroup>();
        if (lg == null) lg = model.AddComponent<LODGroup>();
        lg.fadeMode = LODFadeMode.None;
        lg.SetLODs(new[] { new LOD(near, levels[0].ToArray()), new LOD(far, levels[1].ToArray()), new LOD(0.0f, levels[2].ToArray()) });
        lg.RecalculateBounds();
    }

    /// 同一个网格再挂一个渲染器（同位置、同材质），只画第 lod 档
    static MeshRenderer LodCopy(MeshRenderer r, Mesh mesh, string name, int lod, ShadowCastingMode cast)
    {
        var go = new GameObject(name);
        go.transform.SetParent(r.transform.parent, false);
        go.transform.localPosition = r.transform.localPosition;
        go.transform.localRotation = r.transform.localRotation;
        go.transform.localScale = r.transform.localScale;
        go.layer = r.gameObject.layer;
        go.AddComponent<MeshFilter>().sharedMesh = mesh;
        var c = go.AddComponent<MeshRenderer>();
        c.sharedMaterials = r.sharedMaterials;
        c.shadowCastingMode = cast;
        c.receiveShadows = r.receiveShadows;
        c.lightProbeUsage = r.lightProbeUsage;
        c.reflectionProbeUsage = r.reflectionProbeUsage;
        c.forceMeshLod = (short)lod;
        return c;
    }

    static void NoStaticBatch(GameObject g) =>
        GameObjectUtility.SetStaticEditorFlags(g, GameObjectUtility.GetStaticEditorFlags(g) & ~StaticEditorFlags.BatchingStatic);

    /// 大殿外面的大部件（屋顶的瓦、斗拱梁柱门窗、台基、栏杆）投的影子用简化的那一档（第 1 档，约一半）：另挂一个只投影子的，原来的不再投影子。
    /// 太阳的影子每层级联都要把它们画一遍（三层：三十多万个三角形画三次），影子图上一个像素就有几毫米到几厘米，简化一半看不出来。
    /// 不用更简的档：简化的面和真的面差得多了，屋顶自己身上会投出斑斑点点的假影子
    static void HallShadowProxy(GameObject building)
    {
        foreach (var r in building.GetComponentsInChildren<MeshRenderer>())
        {
            if (r.name.StartsWith("in_") || r.shadowCastingMode == ShadowCastingMode.Off || !r.TryGetComponent(out MeshFilter mf)) continue;
            var mesh = mf.sharedMesh;
            if (mesh == null || mesh.lodCount < 2) continue;
            NoStaticBatch(r.gameObject);
            r.forceMeshLod = 0;
            LodCopy(r, mesh, r.name + "_shadow", 1, ShadowCastingMode.ShadowsOnly);
            r.shadowCastingMode = ShadowCastingMode.Off;
        }
    }

    /// 殿里一直亮着的几盏灯（不跟着天色开关；殿里白天也是靠灯和门口的天光）。没有影子，所以范围都小，不往墙外漏
    static void HallLights(Transform parent)
    {
        // 正中一盏：照亮天花、藻井和殿中间
        HallLight(parent, "HallFill", new Vector3(0, 4.6f, 17.0f), 8f, 1.0f);
        // 佛前三盏：脸和鎏金从门口、过道、拜垫上都看得清
        HallLight(parent, "BuddhaLight", new Vector3(0, 3.4f, 19.6f), 4.5f, 1.2f);
        HallLight(parent, "BuddhaLightW", new Vector3(-3.6f, 3.2f, 19.6f), 4.5f, 1.0f);
        HallLight(parent, "BuddhaLightE", new Vector3(3.6f, 3.2f, 19.6f), 4.5f, 1.0f);
    }

    /// 检查：所有 .yjm 模型的每个部件都接上了材质，材质的着色器没出错（不是洋红色），手绘贴图的材质有贴图。
    /// 命令行：unity/run.sh SanctuaryBuild.CheckToonParts   有问题会抛异常（run.sh 返回非零）
    public static void CheckToonParts()
    {
        var bad = new List<string>();
        int parts = 0;
        foreach (string f in Directory.GetFiles(ToonModels, "*.yjm").OrderBy(s => s))
        {
            string path = f.Replace('\\', '/');
            var go = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if (go == null) { bad.Add($"{path} 读不出来"); continue; }
            var line = new List<string>();
            foreach (var r in go.GetComponentsInChildren<MeshRenderer>())
            {
                parts++;
                var m = r.sharedMaterial;
                string why = null;
                if (m == null) why = "没有材质";
                else if (m.shader == null || m.shader.name == "Hidden/InternalErrorShader") why = "着色器丢了（洋红）";
                else if (ShaderUtil.ShaderHasError(m.shader) || !m.shader.isSupported) why = $"着色器 {m.shader.name} 出错";
                else if (m.HasProperty("_Paint") && m.GetFloat("_Paint") > 0.5f && m.GetTexture("_BaseMap") == null) why = "手绘材质没有贴图";
                line.Add($"{r.name}→{(m != null ? m.name : "空")}{(why != null ? "（" + why + "）" : "")}");
                if (why != null) bad.Add($"{Path.GetFileNameWithoutExtension(path)}/{r.name}：{why}");
            }
            Debug.Log($"[yuanjing] 部件 {Path.GetFileNameWithoutExtension(path)}：{string.Join("，", line)}");
        }
        Debug.Log($"[yuanjing] 部件检查：{parts} 个部件，{bad.Count} 个有问题");
        if (bad.Count > 0) throw new Exception("部件材质有问题：" + string.Join("；", bad));
    }

    /// 量一量几个镜头下要画多少东西（手机是 iPhone）。命令行：
    ///   unity/run.sh SanctuaryBuild.MeasureHallCost -shots "名字|相机位置|看向|时段|天气|视角;..."
    /// 每个镜头：先按镜头位置让 InteriorCull 开关殿里的东西（同运行时），再数视野里的物体：三角形、物体数（≈不合批时的绘制次数）、
    /// 材质数（≈SetPass）、要投影子的物体和三角形（太阳的影子还要画一遍）、照到每个物体的点光源（手机上每个像素都要逐个算）。
    /// 另外渲染一帧，读编辑器自己的统计（UnityStats），两边对照
    public static void MeasureHallCost()
    {
        UnityEditor.SceneManagement.EditorSceneManager.OpenScene("Assets/Scenes/Islet.unity");
        var tw = UnityEngine.Object.FindFirstObjectByType<TimeWeather>();
        var cam = Camera.main;
        var culls = UnityEngine.Object.FindObjectsByType<InteriorCull>(FindObjectsSortMode.None);
        var rt = new RenderTexture(1170, 2532, 24, RenderTextureFormat.ARGB32) { antiAliasing = 4 };
        foreach (string mname in new[] { "buddha_center", "buddha_west", "mandorla_center", "mandorla_side" })
        {
            var go = AssetDatabase.LoadAssetAtPath<GameObject>($"{ToonModels}/{mname}.yjm");
            if (go == null) continue;
            var parts = new List<string>();
            foreach (var mf in go.GetComponentsInChildren<MeshFilter>())
            {
                var m = mf.sharedMesh;
                var lv = new List<string>();
                for (int l = 0; l < m.lodCount; l++) lv.Add($"{m.GetLod(0, l).indexCount / 3000}k");
                parts.Add($"{mf.name}[{string.Join("/", lv)}]");
            }
            Debug.Log($"[yuanjing] 开销 LOD {mname}：{string.Join("，", parts)}");
        }
        foreach (string shot in (Arg("-shots") ?? "").Split(';'))
        {
            var f = shot.Split('|');
            if (f.Length < 5) continue;
            cam.transform.position = Vec(f[1]);
            cam.transform.LookAt(Vec(f[2]));
            cam.fieldOfView = f.Length > 5 ? float.Parse(f[5]) : 60f;
            cam.nearClipPlane = cam.transform.position.y > 10f ? 0.5f : 0.08f;
            tw.ApplyImmediate((DayTime)Enum.Parse(typeof(DayTime), f[3], true), (Weather)Enum.Parse(typeof(Weather), f[4], true));
            foreach (var ic in culls) ic.Apply(cam.transform.position);
            // 手机竖屏（iPhone 的分辨率）
            cam.targetTexture = rt;
            cam.aspect = rt.width / (float)rt.height;
            var planes = GeometryUtility.CalculateFrustumPlanes(cam);
            var points = UnityEngine.Object.FindObjectsByType<Light>(FindObjectsSortMode.None).Where(l => l.isActiveAndEnabled && l.type == LightType.Point && l.intensity > 0).ToList();
            float shadowDist = QualitySettings.shadowDistance > 0 ? QualitySettings.shadowDistance : 48f;
            long tris = 0, shadowTris = 0, hallTris = 0;
            int objs = 0, casters = 0, maxLights = 0;
            double lightTris = 0;
            var mats = new HashSet<Material>();
            var visLights = new HashSet<Light>();
            foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None))
            {
                if (!r.enabled || !r.gameObject.activeInHierarchy || r is ParticleSystemRenderer) continue;
                var mf = r.GetComponent<MeshFilter>();
                Mesh mesh = r is SkinnedMeshRenderer sk ? sk.sharedMesh : mf != null ? mf.sharedMesh : null;
                if (mesh == null) continue;
                long t = 0;
                for (int k = 0; k < mesh.subMeshCount; k++) t += mesh.GetIndexCount(k) / 3;
                var b = r.bounds;
                if (r.shadowCastingMode != ShadowCastingMode.Off && Vector3.Distance(cam.transform.position, b.ClosestPoint(cam.transform.position)) < shadowDist)
                {
                    casters++;
                    shadowTris += t;
                }
                if (!GeometryUtility.TestPlanesAABB(planes, b)) continue;
                objs++;
                tris += t;
                if (culls.Length > 0 && r.transform.IsChildOf(culls[0].transform)) hallTris += t;
                foreach (var m in r.sharedMaterials) if (m != null) mats.Add(m);
                int n = 0;
                foreach (var l in points)
                    if (b.SqrDistance(l.transform.position) < l.range * l.range) { n++; visLights.Add(l); }
                n = Mathf.Min(n, 8);
                maxLights = Mathf.Max(maxLights, n);
                lightTris += (double)n * t;
            }
            cam.Render();
            cam.Render();
            cam.targetTexture = null;
            cam.ResetAspect();
            Debug.Log($"[yuanjing] 开销 {f[0]}：殿里分档 {(culls.Length > 0 ? culls[0].State : -1)}，视野里 {objs} 个物体、{tris / 1000}k 三角形（其中殿和殿里 {hallTris / 1000}k），{mats.Count} 种材质；" +
                      $"投影子 {casters} 个物体、{shadowTris / 1000}k 三角形；照到视野的点光源 {visLights.Count} 盏，一个物体最多 {maxLights} 盏，按三角形平均 {(tris > 0 ? lightTris / tris : 0):F1} 盏。" +
                      $"编辑器统计：{UnityStats.triangles / 1000}k 三角形，{UnityStats.batches} 批，SetPass {UnityStats.setPassCalls}，绘制 {UnityStats.drawCalls}，投影子 {UnityStats.shadowCasters}");
        }
        foreach (var ic in culls) ic.Set(2);
        UnityEngine.Object.DestroyImmediate(rt);
    }
}
