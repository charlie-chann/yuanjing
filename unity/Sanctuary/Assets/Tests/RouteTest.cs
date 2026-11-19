using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 自动走路的路线（GameDirector.Road）：从岛上各处去大殿、殿里、香炉、许愿树、码头，走的是不是铺好的路。
/// 要求：不从山门两边的草地上绕（一定从两根门柱中间过）、不踩蒲团；从码头进殿：码头 → 山门 → 主路 → 香炉外绕半圈 → 中间过道 → 台阶 → 殿门。
/// 再真走一趟（码头上点「进殿」），记下人走过的每一点；香客（本机的人来人往）走一分钟，看他们的路线过不过山门、贴不贴着香炉。
/// 画一张俯视的路线图：unity/shots/route/map.png（灰的是要绕开的东西，黄的是铺好的路，红的是不穿过的线，蓝的是规划的路线，
/// 青的是真走的那一趟，紫的是香客走的）。跑：unity/playtest.sh RouteTest
public class RouteTest
{
    GameObject bridge, player;
    object gd;
    Type gdType;
    readonly List<string> fails = new List<string>();
    readonly List<string> sent = new List<string>();

    const BindingFlags All = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance;
    static void Log(string s) => Debug.Log("[yuanjing] 路线 " + s);
    static string F(Vector3 v) => $"({v.x:F1}, {v.z:F1})";
    static float Flat(Vector3 a, Vector3 b) => Vector2.Distance(new Vector2(a.x, a.z), new Vector2(b.x, b.z));

    object Get(string name)
    {
        var f = gdType.GetField(name, All);
        return f != null ? f.GetValue(gd) : gdType.GetProperty(name, All).GetValue(gd);
    }
    T Call<T>(string name, params object[] args) => (T)gdType.GetMethods(All).First(m => m.Name == name && m.GetParameters().Length == args.Length).Invoke(gd, args);

    void OnLog(string c, string st, LogType t)
    {
        if (c.StartsWith("SendToFlutter - ")) sent.Add(c.Substring(16));
    }

    Vector3 SpotFloor(string name)
    {
        foreach (var s in (Array)Get("spots"))
            if ((string)s.GetType().GetField("name").GetValue(s) == name) return (Vector3)s.GetType().GetField("floor").GetValue(s);
        throw new Exception("没有地点 " + name);
    }

    // ── 画图 ──
    const int W = 640, H = 1000;
    const float X0 = -16f, Z0 = -25f, PPM = 20f;
    Texture2D map;
    Vector2Int Px(Vector3 p) => new Vector2Int(Mathf.RoundToInt((p.x - X0) * PPM), Mathf.RoundToInt((p.z - Z0) * PPM));

    void Dot(Vector2Int c, int r, Color col)
    {
        for (int y = -r; y <= r; y++)
            for (int x = -r; x <= r; x++)
                if (x * x + y * y <= r * r && c.x + x >= 0 && c.x + x < W && c.y + y >= 0 && c.y + y < H) map.SetPixel(c.x + x, c.y + y, col);
    }

    void Line(Vector3 a, Vector3 b, Color col, int r = 1)
    {
        Vector2Int pa = Px(a), pb = Px(b);
        int n = Mathf.Max(1, Mathf.CeilToInt(Vector2.Distance(pa, pb)));
        for (int i = 0; i <= n; i++) Dot(Vector2Int.RoundToInt(Vector2.Lerp(pa, pb, i / (float)n)), r, col);
    }

    void Circle(Vector3 c, float rad, Color col)
    {
        int n = Mathf.Max(12, Mathf.CeilToInt(rad * PPM * 6));
        for (int i = 0; i < n; i++) Dot(Px(c + new Vector3(Mathf.Cos(i * 2 * Mathf.PI / n), 0, Mathf.Sin(i * 2 * Mathf.PI / n)) * rad), 0, col);
    }

    void Poly(Vector3 from, List<Vector3> path, Color col, int r = 1)
    {
        Vector3 prev = from;
        foreach (var p in path) { Line(prev, p, col, r); prev = p; }
    }

    /// 这条路线有没有穿过「不穿过的线」（山门两边、台基边、殿墙）、踩没踩蒲团（seatsToo：起点终点都不在座位区里才查）。
    /// 穿没穿线按整条路线算（拐点正好落在线上、前后两段各「碰一下」也算穿过去了）
    string Check(Vector3 from, List<Vector3> path, bool seatsToo)
    {
        if (Call<bool>("PathCrossesWalls", from, path)) return $"穿过了不该穿的线（山门旁边、台基边、殿墙）：{F(from)} {string.Join(" ", path.Select(F))}";
        Vector3 prev = from;
        foreach (var p in path)
        {
            if (seatsToo && Call<bool>("CrossesSeats", prev, p)) return $"踩了蒲团 {F(prev)}→{F(p)}";
            prev = p;
        }
        return null;
    }

    static float Length(Vector3 from, List<Vector3> path)
    {
        float l = 0;
        foreach (var p in path) { l += Flat(from, p); from = p; }
        return l;
    }

    /// 台阶两边垂带旁边（垂带和台基之间那个角、垂带端头前后）站着的人往殿前、往院子里、往殿里走：路线不从垂带上穿过去（先绕出垂带的南头）
    [UnityTest, Timeout(300000)]
    public IEnumerator CheekRoutes()
    {
        fails.Clear();
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        gdType = Type.GetType("Yuanjing.GameDirector, Assembly-CSharp");
        gd = gdType.GetProperty("Instance").GetValue(null);
        yield return new WaitForSeconds(1f);
        float ty = SpotFloor("hall").y;
        var targets = new[] { SpotFloor("hall"), SpotFloor("burner"), new Vector3(0, 0.72f, 17f), new Vector3(10.5f, ty, 8.8f), new Vector3(-10.5f, ty, 8.8f) };
        foreach (float sx in new[] { -1f, 1f })
            foreach (var (x, z) in new[] { (3.1f, 9.4f), (3.26f, 10.14f), (3.0f, 10.6f), (2.0f, 9.3f), (2.9f, 9.0f) })
                foreach (var b in targets)
                {
                    var a = new Vector3(sx * x, ty, z);
                    var path = Call<List<Vector3>>("PlanPath", a, b);
                    bool bad = Call<bool>("PathCrossesWalls", a, path);
                    if (bad) fails.Add($"{F(a)}→{F(b)}：{string.Join(" ", path.Select(F))}");
                    Log($"垂带旁 {F(a)}→{F(b)}{(bad ? " 穿过了垂带" : "")}：{string.Join(" ", path.Select(F))}");
                }
        Log($"垂带旁的路线：{fails.Count} 条穿过垂带");
        Assert.IsEmpty(fails, string.Join("；", fails));
    }

    [UnityTest, Timeout(600000)]
    public IEnumerator Routes()
    {
        fails.Clear();
        Application.logMessageReceived += OnLog;
        try
        {
            SceneManager.LoadScene("Islet");
            for (int i = 0; i < 10; i++) yield return null;
            bridge = GameObject.Find("Bridge");
            gdType = Type.GetType("Yuanjing.GameDirector, Assembly-CSharp");
            gd = gdType.GetProperty("Instance").GetValue(null);
            bridge.SendMessage("OnMessage", "{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"测试\"}");
            yield return new WaitForSeconds(2f);
            player = GameObject.Find("Player");

            map = new Texture2D(W, H, TextureFormat.RGB24, false);
            var bg = new Color(0.16f, 0.2f, 0.16f);
            var px = Enumerable.Repeat(bg, W * H).ToArray();
            map.SetPixels(px);
            // 座位区、殿
            var sb = (Rect)Get("seatBlock");
            var hr = (Rect)Get("hallRect");
            foreach (var (r, col) in new[] { (sb, new Color(0.35f, 0.3f, 0.2f)), (hr, new Color(0.35f, 0.15f, 0.12f)) })
                for (float x = r.xMin; x <= r.xMax; x += 0.05f)
                    for (float z = r.yMin; z <= r.yMax; z += 0.05f)
                    {
                        var c = Px(new Vector3(x, 0, z));
                        if (c.x >= 0 && c.x < W && c.y >= 0 && c.y < H) map.SetPixel(c.x, c.y, col);
                    }
            // 中间过道
            foreach (var z in new[] { sb.yMin, sb.yMax }) Line(new Vector3(-0.85f, 0, z), new Vector3(0.85f, 0, z), new Color(0.6f, 0.55f, 0.4f));
            foreach (var o in (Array)Get("obstacles"))
            {
                var c = (Vector3)o.GetType().GetField("center").GetValue(o);
                float rad = (float)o.GetType().GetField("radius").GetValue(o);
                var half = (Vector2)o.GetType().GetField("half").GetValue(o);
                Circle(c, rad + half.magnitude, new Color(0.6f, 0.6f, 0.6f));
            }
            foreach (Vector4 w in (Vector4[])Get("planWalls")) Line(new Vector3(w.x, 0, w.y), new Vector3(w.z, 0, w.w), Color.red, 1);
            var nodes = (Vector3[])Get("roadNodes");
            var links = (int[])Get("roadLinks");
            Assert.Greater(nodes.Length, 10, "没有铺好的路（BuildIslet 里 game.roadNodes）");
            for (int k = 0; k + 1 < links.Length; k += 2) Line(nodes[links[k]], nodes[links[k + 1]], new Color(0.95f, 0.8f, 0.3f), 2);

            // ── 规划的路线 ──
            var starts = new (string name, Vector3 p)[]
            {
                ("码头头上", SpotFloor("gate")), ("码头边上", new Vector3(-1.0f, 0.07f, -19.5f)), ("山门外西边草地", new Vector3(-4.5f, 0, -14.2f)),
                ("院子", SpotFloor("court")), ("树下", SpotFloor("tree")), ("树北边", new Vector3(-8.6f, 0, 1.0f)), ("香炉前", SpotFloor("burner")),
                ("池塘边", new Vector3(5.6f, 0, -1.6f)), ("西边草地", new Vector3(-10f, 0, -8f)), ("东边草地", new Vector3(8.5f, 0, -10.5f)),
                ("石台东头", new Vector3(10.6f, 0.07f, 5.0f)), ("殿前", SpotFloor("hall")), ("殿里", SpotFloor("inhall")), ("钟亭前", new Vector3(11.8f, 0, 2.6f)),
                ("西廊下", new Vector3(-2.6f, 0.735f, 11.8f)), ("殿东侧台基上", new Vector3(7.7f, 0.72f, 17f)), ("殿东北角外", new Vector3(10.2f, 0.61f, 19.5f)),
            };
            var targets = new (string name, Vector3 p)[]
            {
                ("进殿", SpotFloor("inhall")), ("去大殿", SpotFloor("hall")), ("去香炉", SpotFloor("burner")), ("去许愿树", SpotFloor("tree")), ("回码头", SpotFloor("gate")),
            };
            var burner = new Vector3(0, 0, -2f);
            var routeCol = new Color(0.35f, 0.65f, 1f);
            int checkedN = 0;
            foreach (var (sn, a) in starts)
                foreach (var (tn, b) in targets)
                {
                    if (Flat(a, b) < 1f) continue;
                    var path = Call<List<Vector3>>("PlanPath", a, b);
                    string bad = Check(a, path, true);
                    float len = Length(a, path), straight = Flat(a, b);
                    // 离香炉最近多远（不该穿过香炉）
                    float nearBurner = float.MaxValue;
                    Vector3 prev = a;
                    foreach (var p in path)
                    {
                        for (int i = 0; i <= 20; i++) nearBurner = Mathf.Min(nearBurner, Flat(Vector3.Lerp(prev, p, i / 20f), burner));
                        prev = p;
                    }
                    if (bad != null) fails.Add($"{sn}→{tn}：{bad}");
                    if (nearBurner < 1.5f) fails.Add($"{sn}→{tn}：离香炉只有 {nearBurner:F2} 米");
                    // 一头在大殿台基上、一头在台基下：照理就得绕到前面走台阶，按「走到台阶下再上去」的直线算
                    bool OnPodium(Vector3 v) => Mathf.Abs(v.x) < 8.8f && v.z > 10.9f && v.z < 23.85f;
                    if (OnPodium(a) != OnPodium(b))
                    {
                        var foot = new Vector3(0, 0, 9.3f);
                        straight = Flat(a, foot) + Flat(foot, b);
                    }
                    if (len > straight * 1.6f + 4f) fails.Add($"{sn}→{tn}：绕得太远 {len:F1} 米（直线 {straight:F1}）");
                    Log($"{sn}→{tn}：{len:F1} 米（直线 {straight:F1}）{(bad ?? "")} {string.Join(" ", path.Select(F))}");
                    Poly(a, path, routeCol);
                    checkedN++;
                }
            // 码头进殿：从两根门柱中间过、走主路、绕香炉、走中间过道
            {
                var a = SpotFloor("gate");
                var path = Call<List<Vector3>>("PlanPath", a, SpotFloor("inhall"));
                var pts = new List<Vector3> { a };
                pts.AddRange(path);
                bool gate = false, aisle = false, ring = false, offPath = false;
                for (int i = 1; i < pts.Count; i++)
                    for (int k = 0; k <= 40; k++)
                    {
                        var p = Vector3.Lerp(pts[i - 1], pts[i], k / 40f);
                        if (Mathf.Abs(p.z - (-12.5f)) < 0.05f && Mathf.Abs(p.x) < 1.4f) gate = true;
                        if (p.z > 2.2f && p.z < 7.8f && Mathf.Abs(p.x) < 0.3f) aisle = true;
                        float rb = Flat(p, burner);
                        if (p.z > -5.5f && p.z < 1.5f && rb > 2.0f && rb < 3.7f) ring = true;
                        // 主路（码头根到圆形铺地）上不离开铺的石板（半宽 1.35）
                        if (p.z > -15.2f && p.z < -5.8f && Mathf.Abs(p.x) > 1.35f) offPath = true;
                    }
                Log($"码头进殿：过山门 {gate}，绕香炉 {ring}，中间过道 {aisle}，离开主路 {offPath}");
                if (!gate || !aisle || !ring || offPath) fails.Add($"码头进殿没顺着路走：过山门 {gate}，绕香炉 {ring}，中间过道 {aisle}，离开主路 {offPath}");
                Poly(a, path, new Color(0.2f, 0.4f, 1f), 2);
            }

            // ── 真走一趟：站在码头上点「进殿」 ──
            var cc = player.GetComponent<CharacterController>();
            cc.enabled = false;
            player.transform.position = new Vector3(-0.6f, 0.07f, -21.0f);
            cc.enabled = true;
            Physics.SyncTransforms();
            yield return new WaitForSeconds(0.5f);
            sent.Clear();
            bridge.SendMessage("OnMessage", "{\"cmd\":\"goto\",\"spot\":\"inhall\"}");
            var walked = new List<Vector3>();
            bool arrived = false, gateOk = false, offGrass = false;
            Vector3 last = player.transform.position;
            float t0 = Time.time;
            while (Time.time - t0 < 90f)
            {
                yield return null;
                var p = player.transform.position;
                if (walked.Count == 0 || Flat(walked[walked.Count - 1], p) > 0.15f) walked.Add(p);
                if ((last.z - (-12.5f)) * (p.z - (-12.5f)) <= 0 && Mathf.Abs(p.x) < 1.5f) gateOk = true;
                if (p.z > -15.0f && p.z < -5.9f && Mathf.Abs(p.x) > 1.45f) offGrass = true;
                last = p;
                if (sent.Any(s => s.Contains("\"arrived\"") && s.Contains("inhall"))) { arrived = true; break; }
            }
            var end = player.transform.position;
            Log($"真走：{(arrived ? "到了" : "没到")} 用 {Time.time - t0:F1} 秒，停在 {F(end)}，过山门 {gateOk}，踩到主路外的草地 {offGrass}");
            if (!arrived) fails.Add($"码头进殿没走到（停在 {F(end)}）");
            if (!gateOk) fails.Add("码头进殿没从山门中间过");
            if (offGrass) fails.Add("码头进殿走到主路外的草地上了");
            for (int i = 1; i < walked.Count; i++) Line(walked[i - 1], walked[i], Color.cyan, 1);

            // ── 香客：本机的人来人往，快放一分多钟，看他们的路线 ──
            var folkType = Type.GetType("Yuanjing.Folk, Assembly-CSharp");
            var allFolk = (IList)folkType.GetField("All", BindingFlags.Public | BindingFlags.Static).GetValue(null);
            var pathField = folkType.GetField("path", All);
            var seen = new Dictionary<object, string>();
            var me = Get("player");
            int npcPaths = 0, npcWall = 0, npcBurner = 0;
            var npcNotes = new List<string>();
            Time.timeScale = 4f;
            for (float t = 0; t < 70f; t += Time.unscaledDeltaTime)
            {
                yield return null;
                foreach (var f in allFolk)
                {
                    var c = (Component)f;
                    if (c == null || ReferenceEquals(f, me)) continue;
                    var path = (List<Vector3>)pathField.GetValue(f);
                    if (path == null || path.Count == 0) continue;
                    string key = string.Join("|", path.Select(F));
                    if (seen.TryGetValue(f, out var k) && k == key) continue;
                    // 只记新开始的一条（路线的点被走过就会从头上去掉：只看比上一条多出来的）
                    if (seen.TryGetValue(f, out var k2) && k2.EndsWith(key)) { seen[f] = key; continue; }
                    seen[f] = key;
                    npcPaths++;
                    Vector3 from = c.transform.position;
                    string bad = Check(from, path, false);
                    // 离香炉最近多远（终点本来就站在香炉前的不算：只看半路上）
                    float nb = float.MaxValue;
                    Vector3 prev = from;
                    foreach (var p in path)
                    {
                        for (int i = 0; i <= 20; i++)
                        {
                            var q = Vector3.Lerp(prev, p, i / 20f);
                            // 起点、终点本来就在香炉跟前（站着上香、拜）的那一截不算
                            if (Flat(q, path[path.Count - 1]) < 0.8f || Flat(q, from) < 0.8f) continue;
                            nb = Mathf.Min(nb, Flat(q, burner));
                        }
                        prev = p;
                    }
                    if (bad != null) { npcWall++; npcNotes.Add($"{c.name} {bad}"); }
                    if (nb < 1.5f) { npcBurner++; npcNotes.Add($"{c.name} 离香炉 {nb:F2} 米：{F(from)} {string.Join(" ", path.Select(F))}"); }
                    Poly(from, path, new Color(0.85f, 0.4f, 0.9f));
                }
            }
            Time.timeScale = 1f;
            Log($"香客：{npcPaths} 条路线，穿过山门旁边 {npcWall} 条，贴着香炉（1.5 米内）{npcBurner} 条");
            foreach (var n in npcNotes.Take(12)) Log("香客 " + n);

            map.Apply();
            // 图的上面是北（大殿），下面是码头（贴图的第 0 行在图的最下面）
            Directory.CreateDirectory("../shots/route");
            File.WriteAllBytes("../shots/route/map.png", map.EncodeToPNG());
            Log($"查了 {checkedN} 条，{fails.Count} 处不对 {string.Join("；", fails)}");
            Assert.IsEmpty(fails, string.Join("；", fails));
        }
        finally
        {
            Time.timeScale = 1f;
            Application.logMessageReceived -= OnLog;
        }
    }
}
