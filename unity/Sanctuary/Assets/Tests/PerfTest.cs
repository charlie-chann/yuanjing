using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using Unity.Profiling;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 几个固定镜头下要画多少东西（性能优化前后对比用）：按 iPhone 竖屏 1170×2532、MSAA 4、iPhone 那一档画质的 LOD 远近（lodBias 0.7），
/// 用真的游戏镜头（平视、俯视；殿里锁住的平视），每个镜头渲染一帧，ProfilerRecorder 读引擎自己的统计：
/// 批次、SetPass、绘制次数、三角形和顶点（含太阳影子的几层）、投影子的物体。
/// 再把几类东西（殿里、殿、香客、宠物、草、树、蒲团……）轮流关掉各渲染一次，差多少就是那一类占多少（含它的影子）。
/// 另外按模型列出视野里、影子里三角形最多的几样（自己数的：Mesh LOD 按第 0 档算，LODGroup 按当时该用的那档算）。
/// 每个镜头存一张图在 unity/shots/perf/。跑：unity/playtest.sh PerfTest，看 grep "\[yuanjing\] 性能" unity/test.log
/// 殿里的香客关掉（随机进殿，数字会跳），院子里的香客、宠物照常（seed 9）。
public class PerfTest
{
    const int W = 1170, H = 2532, SW = 585, SH = 1266;
    const string Dir = "../shots/perf";
    const float PhoneLodBias = 0.7f;   // ProjectSettings/QualitySettings.asset：iPhone 默认 Medium 档

    readonly List<string> sent = new List<string>();
    GameObject bridge, player;
    Camera cam;
    object gd, folk;
    Type folkType;

    [Serializable] class Reply { public string type, spot; }

    void OnLog(string c, string st, LogType t) { if (c.StartsWith("SendToFlutter - ")) sent.Add(c.Substring(16)); }
    void Cmd(string json) => bridge.SendMessage("OnMessage", json);
    static void Log(string s) => Debug.Log("[yuanjing] 性能 " + s);
    static string F(Vector3 v) => $"({v.x:F2}, {v.y:F2}, {v.z:F2})";

    static MethodInfo M(object o, string name, int args)
    {
        foreach (var m in o.GetType().GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
            if (m.Name == name && m.GetParameters().Length == args) return m;
        return null;
    }
    static void Run(object o, string name, params object[] a) => M(o, name, a.Length).Invoke(o, a);
    static T Get<T>(object o, string name)
    {
        var f = o.GetType().GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
        if (f != null) return (T)f.GetValue(o);
        return (T)o.GetType().GetProperty(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance).GetValue(o);
    }

    IEnumerator Wait(string type, float secs, int since, Func<Reply, bool> ok = null)
    {
        for (float t = 0; t < secs; t += Time.deltaTime)
        {
            for (int i = since; i < sent.Count; i++)
            {
                var r = JsonUtility.FromJson<Reply>(sent[i]);
                if (r.type == type && (ok == null || ok(r))) yield break;
            }
            yield return null;
        }
    }

    void Teleport(Vector3 p, float yaw)
    {
        var cc = player.GetComponent<CharacterController>();
        cc.enabled = false;
        player.transform.position = p;
        cc.enabled = true;
        ((Component)folk).transform.rotation = Quaternion.Euler(0, yaw, 0);
        Run(folk, "FaceYaw", yaw);
        Physics.SyncTransforms();
        Run(Get<object>(gd, "cam"), "Snap", yaw);
    }

    // ── 分类：一个渲染器属于哪一类（关掉一类量差值） ──
    static string PathOf(Transform t)
    {
        var l = new List<string>();
        for (; t != null; t = t.parent) l.Add(t.name);
        l.Reverse();
        return string.Join("/", l);
    }

    string Category(Renderer r)
    {
        if (folkType != null && r.GetComponentInParent(folkType) != null) return "香客和自己";
        string p = PathOf(r.transform);
        if (p.Contains("/hall/Inside/")) return "殿里陈设佛像";
        if (p.Contains("/hall/building/")) return "殿";
        if (p.Contains("/Pet_")) return "宠物";
        if (p.Contains("GrassField") || p.Contains("/grass")) return "草";
        if (p.Contains("/tree_") || p.Contains("/bamboo_")) return "树竹";
        if (p.Contains("/cushion/") || p.EndsWith("/cushion")) return "院子蒲团";
        if (p.Contains("/islet_ground") || p.Contains("/islet_paving")) return "地面铺地";
        if (p.Contains("/Offerings") || p.Contains("Ribbon") || p.Contains("Plaque")) return "供物布条";
        if (p.StartsWith("World/Greens") || p.Contains("/Plants")) return "花草灌木";
        return "其他";
    }

    /// 模型名（看哪样东西最费）：殿里的按 Inside 下面那一件，其他按 World/组/ 下面那一件
    static string ModelKey(Renderer r)
    {
        var parts = PathOf(r.transform).Split('/');
        int i = Array.IndexOf(parts, "Inside");
        if (i < 0) i = Array.IndexOf(parts, "hall") >= 0 ? Array.IndexOf(parts, "hall") : 1;
        string key = parts.Length > i + 1 ? parts[i + 1] : parts[parts.Length - 1];
        string part = parts[parts.Length - 1];
        key = new string(key.TakeWhile(ch => !char.IsDigit(ch) || key.StartsWith("Grass")).ToArray()).TrimEnd('_', ' ', '(');
        return key + ":" + part;
    }

    static readonly PropertyInfo SubMeshStart = typeof(Renderer).GetProperty("subMeshStartIndex", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);

    static long Tris(Mesh m)
    {
        long t = 0;
        for (int k = 0; k < m.subMeshCount; k++) t += m.GetIndexCount(k) / 3;
        return t;
    }

    /// LODGroup 里当时该画哪一档（同引擎：包围大小 / (距离 × 2 tan(视角/2)) × lodBias 和每档的门槛比）
    static Dictionary<Renderer, bool> LodActive(Camera c)
    {
        var on = new Dictionary<Renderer, bool>();
        foreach (var lg in UnityEngine.Object.FindObjectsByType<LODGroup>(FindObjectsSortMode.None))
        {
            if (!lg.enabled || !lg.gameObject.activeInHierarchy) continue;
            var lods = lg.GetLODs();
            Vector3 wp = lg.transform.TransformPoint(lg.localReferencePoint);
            float scale = Mathf.Max(Mathf.Abs(lg.transform.lossyScale.x), Mathf.Abs(lg.transform.lossyScale.y), Mathf.Abs(lg.transform.lossyScale.z));
            float d = Vector3.Distance(c.transform.position, wp);
            float h = lg.size * scale / Mathf.Max(d * 2f * Mathf.Tan(c.fieldOfView * 0.5f * Mathf.Deg2Rad), 1e-4f) * QualitySettings.lodBias;
            int pick = lods.Length;
            for (int k = 0; k < lods.Length; k++) if (h >= lods[k].screenRelativeTransitionHeight) { pick = k; break; }
            for (int k = 0; k < lods.Length; k++)
                foreach (var r in lods[k].renderers) if (r != null) on[r] = k == pick;
        }
        return on;
    }

    readonly string[] counters = { "Batches Count", "SetPass Calls Count", "Draw Calls Count", "Triangles Count", "Vertices Count", "Shadow Casters Count" };
    Dictionary<string, ProfilerRecorder> rec;
    RenderTexture rt, srt;
    Texture2D tex;

    long[] Render()
    {
        var before = counters.Select(n => rec[n].CurrentValue).ToArray();
        cam.targetTexture = rt;
        cam.Render();
        cam.targetTexture = null;
        return counters.Select((n, i) => rec[n].CurrentValue - before[i]).ToArray();
    }

    void Picture(string name)
    {
        cam.targetTexture = srt;
        cam.Render();
        cam.targetTexture = null;
        RenderTexture.active = srt;
        tex.ReadPixels(new Rect(0, 0, SW, SH), 0, 0);
        tex.Apply();
        RenderTexture.active = null;
        File.WriteAllBytes($"{Dir}/{name}.png", tex.EncodeToPNG());
    }

    static string Fmt(long[] v) => $"批次 {v[0]}，SetPass {v[1]}，绘制 {v[2]}，三角形 {v[3] / 1000}k，顶点 {v[4] / 1000}k，投影子 {v[5]}";

    IEnumerator Stat(string name)
    {
        yield return new WaitForSeconds(1.5f);
        yield return null;
        var ic = UnityEngine.Object.FindFirstObjectByType(Type.GetType("Yuanjing.InteriorCull, Assembly-CSharp"));
        int state = ic != null ? Get<int>(ic, "State") : -1;
        string culled = ic != null && ic.GetType().GetProperty("CulledOutside") != null
            ? $"，门洞挑掉 殿里 {Get<int>(ic, "CulledInside")} 殿外 {Get<int>(ic, "CulledOutside")} 走动的 {Get<int>(ic, "CulledActors")}" : "";
        // 先空渲染一遍（第一次渲染有着色器变体编译、阴影图分配）
        cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
        var all = Render();
        Log($"{name}：镜头 {F(cam.transform.position)} 视角 {cam.fieldOfView:F0}° 殿里分档 {state}{culled}：{Fmt(all)}");
        Picture(name);

        // 每一类关掉量一遍
        var rs = UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None).Where(r => r.enabled && r.gameObject.activeInHierarchy).ToList();
        var groups = rs.GroupBy(Category).OrderBy(g => g.Key).ToList();
        var line = new List<string>();
        foreach (var g in groups)
        {
            foreach (var r in g) r.enabled = false;
            var without = Render();
            foreach (var r in g) r.enabled = true;
            line.Add($"{g.Key} 批次 {all[0] - without[0]} 三角形 {(all[3] - without[3]) / 1000}k 投影子 {all[5] - without[5]}");
        }
        Log($"{name} 分类（关掉这一类少了多少）：{string.Join("；", line)}");

        // 几遍渲染各占多少：太阳的影子（几层级联）、SSAO（要先把整个画面的深度、法线再画一遍）
        var pass = new List<string>();
        var suns = UnityEngine.Object.FindObjectsByType<Light>(FindObjectsSortMode.None).Where(l => l.isActiveAndEnabled && l.type == LightType.Directional && l.shadows != LightShadows.None).ToList();
        var was = suns.Select(l => l.shadows).ToList();
        foreach (var l in suns) l.shadows = LightShadows.None;
        var noShadow = Render();
        for (int i = 0; i < suns.Count; i++) suns[i].shadows = was[i];
        pass.Add($"太阳影子 批次 {all[0] - noShadow[0]} 三角形 {(all[3] - noShadow[3]) / 1000}k");
        var ssao = Feature("SSAO");
        if (ssao != null)
        {
            ssao.SetActive(false);
            var noAo = Render();
            ssao.SetActive(true);
            pass.Add($"SSAO（深度法线预渲染） 批次 {all[0] - noAo[0]} 三角形 {(all[3] - noAo[3]) / 1000}k");
        }
        Log($"{name} 每遍：{string.Join("；", pass)}");

        // 按模型数：视野里的三角形、要投影子（影子距离以内）的三角形
        var planes = GeometryUtility.CalculateFrustumPlanes(cam);
        var lod = LodActive(cam);
        float shadowDist = ShadowDistance();
        var vis = new Dictionary<string, long>();
        var sh = new Dictionary<string, long>();
        foreach (var r in rs)
        {
            if (r is ParticleSystemRenderer || (lod.TryGetValue(r, out bool lodOn) && !lodOn)) continue;
            Mesh mesh = r is SkinnedMeshRenderer sk ? sk.sharedMesh : r.TryGetComponent(out MeshFilter mf) ? mf.sharedMesh : null;
            if (mesh == null) continue;
            long t = Tris(mesh);
            if (r.isPartOfStaticBatch)
            {
                // 静态合批以后 sharedMesh 是合起来的大网格：只数自己那几段（子网格从 subMeshStartIndex 起，引擎内部的属性）
                t = 0;
                if (SubMeshStart?.GetValue(r) is int s0)
                    for (int j = 0; j < r.sharedMaterials.Length && s0 + j < mesh.subMeshCount; j++) t += mesh.GetSubMesh(s0 + j).indexCount / 3;
            }
            string k = ModelKey(r);
            if (GeometryUtility.TestPlanesAABB(planes, r.bounds)) vis[k] = (vis.TryGetValue(k, out long a) ? a : 0) + t;
            if (r.shadowCastingMode != ShadowCastingMode.Off && Vector3.Distance(cam.transform.position, r.bounds.ClosestPoint(cam.transform.position)) < shadowDist)
                sh[k] = (sh.TryGetValue(k, out long b) ? b : 0) + t;
        }
        Log($"{name} 视野里最多（按第 0 档）：{string.Join("，", vis.OrderByDescending(kv => kv.Value).Take(14).Select(kv => $"{kv.Key} {kv.Value / 1000}k"))}");
        Log($"{name} 影子里最多（{shadowDist:F0} 米内）：{string.Join("，", sh.OrderByDescending(kv => kv.Value).Take(14).Select(kv => $"{kv.Key} {kv.Value / 1000}k"))}");
    }

    /// 渲染器上的一个特效（ScriptableRendererFeature，按名字找；测试程序集引用不到 URP，用反射）
    static ScriptableObject FeatureObj(string name)
    {
        var p = GraphicsSettings.currentRenderPipeline;
        var f = p?.GetType().GetField("m_RendererDataList", BindingFlags.NonPublic | BindingFlags.Instance);
        if (f?.GetValue(p) is not Array list || list.Length == 0) return null;
        var data = list.GetValue(0);
        if (data?.GetType().GetProperty("rendererFeatures")?.GetValue(data) is not IEnumerable feats) return null;
        foreach (var o in feats) if (o is ScriptableObject so && so.name == name) return so;
        return null;
    }

    class FeatureSwitch
    {
        public ScriptableObject so;
        public void SetActive(bool on) => so.GetType().GetMethod("SetActive").Invoke(so, new object[] { on });
    }

    static FeatureSwitch Feature(string name) { var so = FeatureObj(name); return so != null ? new FeatureSwitch { so = so } : null; }

    static float ShadowDistance()
    {
        var p = GraphicsSettings.currentRenderPipeline;
        var prop = p?.GetType().GetProperty("shadowDistance");
        return prop != null ? (float)prop.GetValue(p) : QualitySettings.shadowDistance;
    }

    [UnityTest, Timeout(900000)]
    public IEnumerator Perf()
    {
        Directory.CreateDirectory(Dir);
        foreach (var f in Directory.GetFiles(Dir, "*.png")) File.Delete(f);
        Application.logMessageReceived += OnLog;
        float biasWas = QualitySettings.lodBias;
        // 本机的人数不跟着钟点走（夜里十位、傍晚四十几位，两次量的数对不上）：按白天高峰前后的 36 位量
        var crowd = Type.GetType("Yuanjing.Pilgrims, Assembly-CSharp").GetField("CrowdOverride");
        try
        {
            crowd.SetValue(null, 36);
            SceneManager.LoadScene("Islet");
            for (int i = 0; i < 10; i++) yield return null;
            bridge = GameObject.Find("Bridge");
            Cmd("{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"我\"}");
            yield return new WaitForSeconds(3f);
            player = GameObject.Find("Player");
            cam = Camera.main;
            gd = Type.GetType("Yuanjing.GameDirector, Assembly-CSharp").GetProperty("Instance").GetValue(null);
            folk = Get<object>(gd, "player");
            folkType = Type.GetType("Yuanjing.Folk, Assembly-CSharp");
            Run(Get<object>(gd, "pilgrims"), "HallCrowd", false);

            var p = GraphicsSettings.currentRenderPipeline;
            string Prop(string n) { var pr = p?.GetType().GetProperty(n); return pr != null ? pr.GetValue(p)?.ToString() : "?"; }
            Log($"设置：画质档 {QualitySettings.names[QualitySettings.GetQualityLevel()]}（lodBias {QualitySettings.lodBias}，meshLodThreshold {QualitySettings.meshLodThreshold}），量的时候 lodBias 用 iPhone 的 {PhoneLodBias}；" +
                $"URP：影子距离 {Prop("shadowDistance")}，级联 {Prop("shadowCascadeCount")}，影子图 {Prop("mainLightShadowmapResolution")}，MSAA {Prop("msaaSampleCount")}，渲染比例 {Prop("renderScale")}，HDR {Prop("supportsHDR")}");
            QualitySettings.lodBias = PhoneLodBias;

            rec = counters.ToDictionary(n => n, n => ProfilerRecorder.StartNew(ProfilerCategory.Render, n));
            rt = new RenderTexture(W, H, 24) { antiAliasing = 4 };
            srt = new RenderTexture(SW, SH, 24) { antiAliasing = 4 };
            tex = new Texture2D(SW, SH, TextureFormat.RGB24, false);

            // ── 院子里：俯视、平视 ──
            Cmd("{\"cmd\":\"view\",\"kind\":\"top\"}");
            Teleport(new Vector3(0, 0.08f, 0.6f), 0);
            yield return Stat("俯视院子");
            Teleport(new Vector3(0, 0.08f, 4.6f), 0);
            yield return Stat("俯视石台");
            Teleport(new Vector3(0, 1.1f, 13.0f), 0);
            yield return Stat("俯视殿前");
            Cmd("{\"cmd\":\"view\",\"kind\":\"level\"}");
            Teleport(new Vector3(0, 0.08f, 1.6f), 0);
            yield return Stat("石台南头平视大殿");
            Teleport(new Vector3(0, 1.1f, 13.4f), 0);
            yield return Stat("廊下平视进门");

            // ── 进殿（游戏自己的「进殿」：殿里的平视锁住） ──
            int n0 = sent.Count;
            Cmd("{\"cmd\":\"goto\",\"spot\":\"inhall\"}");
            yield return Wait("arrived", 45f, n0, r => r.spot == "inhall");
            yield return Stat("进殿后平视");
            Teleport(new Vector3(0, 1.09f, 22.5f), 0);
            yield return Stat("过道看佛像");
            Teleport(new Vector3(0, 1.09f, 28.2f), 180);
            yield return Stat("供桌前回头看门");
            // 对照：离自己 22 米外的人也投影子（Folk.ShadowFar 关掉，以前的做法）——看省了多少
            var far = folkType.GetField("ShadowFar");
            float farWas = (float)far.GetValue(null);
            far.SetValue(null, 0f);
            yield return new WaitForSeconds(1.2f);
            yield return Stat("供桌前回头看门（远处的人也投影子）");
            far.SetValue(null, farWas);
            yield return new WaitForSeconds(1.2f);
            Teleport(new Vector3(-6.6f, 1.09f, 25.6f), 40);
            yield return Stat("西边静坐区看佛像");
            Cmd("{\"cmd\":\"sky\",\"time\":\"night\",\"weather\":\"clear\",\"instant\":true}");
            Teleport(new Vector3(0, 1.09f, 28.2f), 180);
            yield return Stat("夜里供桌前回头看门");
            Teleport(new Vector3(0, 1.09f, 22.5f), 0);
            yield return Stat("夜里过道看佛像");
        }
        finally
        {
            crowd.SetValue(null, 0);
            QualitySettings.lodBias = biasWas;
            if (rec != null) foreach (var kv in rec) kv.Value.Dispose();
            Application.logMessageReceived -= OnLog;
        }
    }
}
