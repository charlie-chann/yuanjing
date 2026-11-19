using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 交互，三段：
///   SitStandTapAndHang：走到蒲团附近才有「坐下」、坐最近的那个、起身只退到走道上、点地面走过去一定回 arrived；
///     亲手挂红布条和木牌（走到绳外、拿在手上、系上、正面朝外、带写的字），三十二格的特写镜头都不埋在东西里、不被挡；别人挂的带字、不重复。
///   SeatRacesAndCrowd：转身坐下那一下起身、香客走到一半换座位、被香客记着但人不在的蒲团、按着摇杆做动作不滑、
///     站在挂的点上推一下摇杆再挂、蒲团之间的点出座位区不踩蒲团。
///   HallInterior：真的大殿（BuildHall 的殿、陈设和碰撞）：殿里的路线不碰东西、去两边蒲团从金柱中间走，进殿锁平视、俯视点不了、
///     镜头收近不穿天花板和墙，每块拜垫上跪拜叩首、供桌前上香（香插进香炉的灰里），殿里的蒲团坐下起身，
///     从殿里走出去、走进来都经过中间那扇门，出殿换回原来的视角。
/// 截图在 unity/shots/interact/<段>/。写了字的灰度图优先用 Flutter 测试写好的那几张（unity/shots/wish/*.png，
/// test/sanctuary_wish_mask_test.dart 生成），没有就画一张替代的。
public class InteractionTest
{
    StringBuilder report = new StringBuilder();
    readonly List<string> sent = new List<string>();
    GameObject bridge, player;
    Camera cam;
    RenderTexture rt;
    Texture2D tex;
    int shot;
    string dir;
    object gd, off, pil, folk, vs;

    [Serializable]
    class Reply
    {
        public string type, spot, kind, reason, pet, mode, action, nohang, to;
        public int seat = -999, slot = -999, mat = -999;
        public bool altar, locked, hall;
    }

    void OnLog(string c, string st, LogType t)
    {
        if (c.StartsWith("SendToFlutter - ")) sent.Add(c.Substring(16));
    }

    void Cmd(string json) => bridge.SendMessage("OnMessage", json);

    void Log(string s)
    {
        report.AppendLine(s);
        Debug.Log("[yuanjing] 交互 " + s);
    }

    void Shot(string name, int w = 0, int h = 0)
    {
        var target = rt;
        Texture2D t2 = tex;
        if (w > 0)
        {
            target = new RenderTexture(w, h, 24) { antiAliasing = 2 };
            t2 = new Texture2D(w, h, TextureFormat.RGB24, false);
        }
        cam.targetTexture = target; cam.Render(); cam.targetTexture = null;
        RenderTexture.active = target; t2.ReadPixels(new Rect(0, 0, target.width, target.height), 0, 0); t2.Apply(); RenderTexture.active = null;
        File.WriteAllBytes($"{dir}/{shot++:00}_{name}.png", t2.EncodeToPNG());
        if (w > 0) { UnityEngine.Object.Destroy(target); UnityEngine.Object.Destroy(t2); }
    }

    /// 用主镜头从指定的位置拍一张（拍完这一帧镜头脚本会自己摆回去）
    IEnumerator ShotFrom(string name, Vector3 eye, Vector3 focus, float fov = 46f, int w = 0, int h = 0)
    {
        yield return null;
        var p = cam.transform.position; var r = cam.transform.rotation; float f = cam.fieldOfView, n = cam.nearClipPlane;
        cam.transform.SetPositionAndRotation(eye, Quaternion.LookRotation(focus - eye));
        cam.fieldOfView = fov;
        cam.nearClipPlane = 0.05f;
        Shot(name, w, h);
        cam.transform.SetPositionAndRotation(p, r);
        cam.fieldOfView = f;
        cam.nearClipPlane = n;
    }

    static MethodInfo M(object o, string name, int args = -1)
    {
        foreach (var m in o.GetType().GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
            if (m.Name == name && (args < 0 || m.GetParameters().Length == args)) return m;
        return null;
    }
    static T Call<T>(object o, string name, params object[] a) => (T)M(o, name, a.Length).Invoke(o, a);
    static void Run(object o, string name, params object[] a) => M(o, name, a.Length).Invoke(o, a);
    static T Get<T>(object o, string name)
    {
        var f = o.GetType().GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
        if (f != null) return (T)f.GetValue(o);
        return (T)o.GetType().GetProperty(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance).GetValue(o);
    }
    static void Set(object o, string name, object v) => o.GetType().GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance).SetValue(o, v);

    Reply got;

    /// 等 Unity 发某种消息（从第 since 条往后找），最多 secs 秒；找到的放在 got 里
    IEnumerator Wait(string type, float secs, int since, Func<Reply, bool> ok = null)
    {
        got = null;
        for (float t = 0; t < secs; t += Time.deltaTime)
        {
            for (int i = since; i < sent.Count; i++)
            {
                var r = JsonUtility.FromJson<Reply>(sent[i]);
                if (r.type == type && (ok == null || ok(r))) { got = r; yield break; }
            }
            yield return null;
        }
    }

    int Count(string type, int since)
    {
        int n = 0;
        for (int i = since; i < sent.Count; i++) if (JsonUtility.FromJson<Reply>(sent[i]).type == type) n++;
        return n;
    }

    string Types(int since)
    {
        var sb = new StringBuilder();
        for (int i = since; i < sent.Count; i++) sb.Append(JsonUtility.FromJson<Reply>(sent[i]).type).Append(' ');
        return sb.ToString();
    }

    /// 最近一条 near 消息
    Reply LastNear()
    {
        for (int i = sent.Count - 1; i >= 0; i--)
        {
            var r = JsonUtility.FromJson<Reply>(sent[i]);
            if (r.type == "near") return r;
        }
        return new Reply { seat = -1, mat = -1 };
    }

    int LastNearSeat() => LastNear().seat;

    void Teleport(Vector3 p, Vector3 face)
    {
        var cc = player.GetComponent<CharacterController>();
        cc.enabled = false;
        player.transform.position = p;
        cc.enabled = true;
        M(folk, "FaceTowards").Invoke(folk, new object[] { face });
        ((Component)folk).transform.rotation = Quaternion.LookRotation(new Vector3(face.x - p.x, 0, face.z - p.z));
    }

    Vector3 Me => ((Component)folk).transform.position;

    static float Flat(Vector3 a, Vector3 b) => Vector2.Distance(new Vector2(a.x, a.z), new Vector2(b.x, b.z));
    static string F(Vector3 v) => v.ToString("F2");
    static string Inv(float f) => f.ToString(System.Globalization.CultureInfo.InvariantCulture);

    /// 摇杆：按世界里的方向推（换算成按镜头朝向的摇杆值）
    void Stick(Vector3 world)
    {
        if (world.sqrMagnitude < 1e-4f) { Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":0}"); return; }
        float yaw = Get<float>(Get<object>(gd, "cam"), "Yaw") * Mathf.Deg2Rad;
        world.y = 0; world.Normalize();
        // Euler(0,yaw,0) * (x,0,y) = world
        float x = world.x * Mathf.Cos(yaw) - world.z * Mathf.Sin(yaw), y = world.x * Mathf.Sin(yaw) + world.z * Mathf.Cos(yaw);
        Cmd($"{{\"cmd\":\"move\",\"x\":{Inv(x)},\"y\":{Inv(y)}}}");
    }

    /// 写了字的灰度图：Flutter 写好的那张，没有就画一张（一格格的方块当字）
    static string Mask(string file, int w, int h)
    {
        string path = $"../shots/wish/{file}.png";
        if (File.Exists(path)) return Convert.ToBase64String(File.ReadAllBytes(path));
        var t = new Texture2D(w, h, TextureFormat.RGBA32, false);
        var px = new Color32[w * h];
        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
            {
                float u = x / (float)w, v = 1f - y / (float)h;
                int cx = (int)((u - 0.2f) / 0.2f);
                bool ink = u > 0.2f && u < 0.8f && v > 0.1f && v < 0.8f && cx % 2 == 0 && ((x + y) % 7 < 4);
                px[y * w + x] = ink ? new Color32(0, 0, 0, 255) : new Color32(255, 255, 255, 255);
            }
        t.SetPixels32(px);
        t.Apply();
        return Convert.ToBase64String(t.EncodeToPNG());
    }

    IEnumerator Begin(string part)
    {
        report = new StringBuilder();
        sent.Clear();
        shot = 0;
        dir = $"../shots/interact/{part}";
        Directory.CreateDirectory(dir);
        foreach (var f in Directory.GetFiles(dir, "*.png")) File.Delete(f);
        Application.logMessageReceived -= OnLog;
        Application.logMessageReceived += OnLog;
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        bridge = GameObject.Find("Bridge");
        Cmd("{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":0,\"name\":\"测试\"}");
        yield return new WaitForSeconds(2f);
        player = GameObject.Find("Player");
        cam = Camera.main;
        rt = new RenderTexture(540, 960, 24) { antiAliasing = 4 };
        tex = new Texture2D(540, 960, TextureFormat.RGB24, false);
        gd = Type.GetType("Yuanjing.GameDirector, Assembly-CSharp").GetProperty("Instance").GetValue(null);
        off = Get<object>(gd, "offerings");
        pil = Get<object>(gd, "pilgrims");
        folk = Get<object>(gd, "player");
        vs = cam.GetComponent(Type.GetType("Yuanjing.ViewSwitcher, Assembly-CSharp"));
    }

    void End(string part)
    {
        File.WriteAllText($"{dir}/report.txt", report.ToString());
        Application.logMessageReceived -= OnLog;
    }

    // ═══════════════ 1 坐下、起身、点地面、挂布条木牌 ═══════════════

    [UnityTest, Timeout(600000)]
    public IEnumerator SitStandTapAndHang()
    {
        yield return Begin("hang");
        try
        {
            int seats = Get<int>(gd, "SeatTotal");
            int cushions = 0;
            foreach (var t in UnityEngine.Object.FindObjectsByType<Transform>(FindObjectsSortMode.None))
                if (System.Text.RegularExpressions.Regex.IsMatch(t.name, @"^Seat\d+$")) cushions++;
            Log($"进殿：座位 {seats} 个（院子里的蒲团 {cushions} 个，殿里的 {seats - cushions} 个）");
            Assert.AreEqual(60, cushions, "院子里应该是 60 个蒲团");
            Assert.AreEqual(76, seats, "殿里应该有 16 个静坐的蒲团");

            // ── 坐下按钮：只在离蒲团前面那一点 1.2 米以内才报，坐最近的那个 ──
            const int S = 14;   // 第 2 排、西边第 2 个
            Vector3 stand = Call<Vector3>(gd, "SeatStand", S), lane = Call<Vector3>(gd, "SeatLane", S);
            Cmd("{\"cmd\":\"view\",\"kind\":\"level\"}");
            Teleport(new Vector3(-4.5f, 0.06f, -1f), new Vector3(0, 0, 10));
            yield return new WaitForSeconds(0.4f);
            int farSeat = LastNearSeat();
            Teleport(new Vector3(0, 0.07f, stand.z), new Vector3(0, 0, 20));
            yield return new WaitForSeconds(0.4f);
            int aisleSeat = LastNearSeat();
            Teleport(lane, new Vector3(lane.x, 0, 20));
            yield return new WaitForSeconds(0.4f);
            int laneSeat = LastNearSeat();
            Log($"坐下按钮：远处 {farSeat}，过道里（离最近的蒲团 {Flat(new Vector3(0, 0, stand.z), Call<Vector3>(gd, "SeatStand", 12)):F2} 米）{aisleSeat}，第 {S} 号前面的走道上 {laneSeat}");
            Assert.AreEqual(-1, farSeat, "远处不该有坐下");
            Assert.AreEqual(-1, aisleSeat, "过道中间离蒲团 1.3 米，不该有坐下");
            Assert.AreEqual(S, laneSeat, "走道上应该报正对着的那个蒲团");
            Shot("near_seat_lane");

            // 坐下：seat 给 -1 也坐最近的
            int n0 = sent.Count;
            Cmd("{\"cmd\":\"sit\",\"seat\":-1}");
            yield return Wait("seated", 15f, n0);
            Assert.IsNotNull(got, "没坐下");
            Assert.AreEqual(S, got.seat);
            yield return new WaitForSeconds(3f);
            Vector3 ground = Call<Vector3>(gd, "SeatGround", S);
            Log($"坐下：{got.seat} 号，原点离蒲团 {Flat(Me, ground):F2} 米，消息 {Types(n0)}");
            Shot("seated");

            // 起身：只退到这一排前面的走道上
            n0 = sent.Count;
            Cmd("{\"cmd\":\"stand\"}");
            yield return Wait("arrived", 12f, n0);
            Assert.IsNotNull(got, "起身以后没有 arrived");
            yield return new WaitForSeconds(0.5f);
            float off1 = Flat(Me, lane);
            Log($"起身：停在离走道那一点 {off1:F2} 米（spot={got.spot}）");
            Assert.Less(off1, 0.3f, "起身应该退到这一排的走道上");
            Shot("stood_lane");

            // 给一个远处的座位：不去那么远，坐身边最近的
            n0 = sent.Count;
            Cmd("{\"cmd\":\"sit\",\"seat\":59}");
            yield return Wait("seated", 15f, n0);
            Assert.IsNotNull(got);
            Log($"给了 59 号（远处）：实际坐 {got.seat} 号");
            Assert.AreEqual(S, got.seat);
            yield return new WaitForSeconds(2.5f);
            // 推摇杆：起身退到走道上，然后自己走
            n0 = sent.Count;
            Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":1}");
            yield return new WaitForSeconds(0.1f);
            Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":0}");
            yield return Wait("arrived", 12f, n0);
            Assert.IsNotNull(got, "推摇杆起身以后没有 arrived");
            Log($"推摇杆起身：停在离走道 {Flat(Me, lane):F2} 米");

            // 身边没有空蒲团：sitFailed（reason none）
            Teleport(new Vector3(-4.5f, 0.06f, -1f), new Vector3(0, 0, 10));
            yield return new WaitForSeconds(0.3f);
            n0 = sent.Count;
            Cmd("{\"cmd\":\"sit\",\"seat\":-1}");
            yield return Wait("sitFailed", 2f, n0);
            Assert.IsNotNull(got, "远处坐下应该回 sitFailed");
            Assert.AreEqual("none", got.reason);
            Log($"远处坐下：sitFailed {got.reason}");

            // ── 点地面：走过去，一定回 arrived（以前在同一处走动时界面会一直等着） ──
            for (int k = 0; k < 2; k++)
            {
                Vector3 start = new Vector3(-3.5f, 0.06f, -8.5f);
                Teleport(start, start + (k == 0 ? new Vector3(1, 0, 1) : new Vector3(-1, 0, 1)) * 5f);
                yield return new WaitForSeconds(1.2f);
                Vector3 cf = cam.transform.forward; cf.y = 0; cf.Normalize();
                Vector3 p = Me + cf * 2.4f + Vector3.Cross(Vector3.up, cf) * (k == 0 ? 0.5f : -0.5f);
                Vector3 vp = cam.WorldToViewportPoint(p);
                n0 = sent.Count;
                Cmd($"{{\"cmd\":\"tap\",\"x\":{Inv(vp.x)},\"y\":{Inv(1 - vp.y)}}}");
                yield return Wait("moving", 2f, n0);
                bool moved = got != null;
                yield return Wait("arrived", 12f, n0);
                Log($"点地面第 {k + 1} 次：moving={moved}，arrived={(got != null ? got.spot : "没有")}");
                Assert.IsTrue(moved && got != null, "点地面走过去以后要回 arrived");
            }

            // ── 三十二格的特写镜头：不埋在东西里、看得见布条（不被木桩、树、架子、自己的身子挡住） ──
            yield return CloseUpsAllSlots();

            // ── 亲手挂红布条（平视）、木牌（俯视） ──
            yield return Hang("ribbon", "level", new Vector3(-5.2f, 0, -5.6f), Mask("mask_ribbon", 128, 512), "愿家人平安喜乐");
            yield return Hang("plaque", "top", new Vector3(-8.6f, 0, 1.4f), Mask("mask_plaque", 256, 320), "愿外婆身体健康");
            // 绘马架旁边那几格（以前特写镜头埋进架子里）
            yield return Hang("ribbon", "level", new Vector3(-11.6f, 0, -5.6f), Mask("mask_ribbon_short", 128, 512), "平安");

            // ── 别人挂的：带字、按编号不重复；字一帧合成一件，不卡 ──
            var freeSlots = new List<int>();
            for (int i = 0; i < Get<int>(off, "SlotCount"); i++) if (!Call<bool>(off, "SlotUsed", i)) freeSlots.Add(i);
            int before = CountWishes();
            string[] masks = { "mask_ribbon_long", "mask_ribbon_short", "mask_ribbon", "mask_plaque" };
            float t0 = Time.realtimeSinceStartup;
            for (int i = 0; i < 6; i++)
            {
                string kind = i == 3 ? "plaque" : "ribbon";
                string m = Mask(kind == "plaque" ? "mask_plaque" : masks[i % 3], kind == "plaque" ? 256 : 128, kind == "plaque" ? 320 : 512);
                Cmd($"{{\"cmd\":\"offerings\",\"kind\":\"{kind}\",\"list\":\"{freeSlots[i]}\",\"id\":\"t{i}\",\"tex\":\"{m}\"}}");
            }
            float ms = (Time.realtimeSinceStartup - t0) * 1000f;
            int queued = Get<int>(off, "PendingFaces");
            yield return null;
            int mid = CountWishes();
            Cmd($"{{\"cmd\":\"offerings\",\"kind\":\"ribbon\",\"list\":\"{freeSlots[0]}\",\"id\":\"t0\",\"tex\":\"{Mask("mask_ribbon_long", 128, 512)}\"}}");
            // 同一格又来一件别人的：挪到旁边的空格
            Cmd($"{{\"cmd\":\"offerings\",\"kind\":\"ribbon\",\"list\":\"{freeSlots[1]}\",\"id\":\"t9\"}}");
            yield return null;
            int after = CountWishes();
            for (int i = 0; i < 20 && Get<int>(off, "PendingFaces") > 0; i++) yield return null;
            // 一帧合成一件要多久
            t0 = Time.realtimeSinceStartup;
            Cmd($"{{\"cmd\":\"offerings\",\"kind\":\"ribbon\",\"list\":\"12\",\"id\":\"tt\",\"tex\":\"{Mask("mask_ribbon_long", 128, 512)}\"}}");
            Run(off, "Update");
            float one = (Time.realtimeSinceStartup - t0) * 1000f;
            Log($"别人挂的：放了 6 件 {before}→{mid}（收消息那一帧 {ms:F0} 毫秒，排队合成字 {queued} 件；合成一件 {one:F1} 毫秒），同一编号再发一次、同一格另一件 → {after}");
            Assert.AreEqual(before + 6, mid);
            Assert.AreEqual(mid + 1, after);
            for (int i = 0; i < 6; i++) Assert.IsNotNull(Call<Texture>(off, "FaceAt", freeSlots[i]), $"第 {freeSlots[i]} 格没有带字的贴图");

            // 远远平视看一圈：字朝外，绳结套在绳子上
            Vector3 c0 = Call<Vector3>(off, "SlotPoint", freeSlots[2]), o0 = Call<Vector3>(off, "Outward", freeSlots[2]);
            yield return ShotFrom("tree_others_close", c0 + o0 * 1.2f + Vector3.up * 0.05f, c0 + Vector3.down * 0.28f, 50f);
            yield return ShotFrom("tree_others_level", c0 + o0 * 3.2f + Vector3.up * 0.55f + Vector3.Cross(Vector3.up, o0) * 0.8f, c0 + Vector3.down * 0.3f, 52f);
            yield return ShotFrom("knot_close", c0 + o0 * 0.32f + Vector3.up * 0.1f + Vector3.Cross(Vector3.up, o0) * 0.12f, c0 + Vector3.up * 0.02f, 40f);
            yield return ShotFrom("knot_side", c0 + Vector3.Cross(Vector3.up, o0) * 0.35f + o0 * 0.05f + Vector3.up * 0.04f, c0 + Vector3.up * 0.0f, 40f);
            Vector3 c1 = Call<Vector3>(off, "SlotPoint", freeSlots[3]), o1 = Call<Vector3>(off, "Outward", freeSlots[3]);
            yield return ShotFrom("plaque_knot_close", c1 + o1 * 0.4f + Vector3.up * 0.05f + Vector3.Cross(Vector3.up, o1) * 0.15f, c1 + Vector3.down * 0.05f, 40f);
            // 从背后（树那一侧）看：不该看到反过来的字
            yield return ShotFrom("tree_back_side", c0 - o0 * 0.9f + Vector3.up * 0.05f, c0 + Vector3.down * 0.28f, 50f);
            Cmd("{\"cmd\":\"view\",\"kind\":\"top\"}");
            yield return new WaitForSeconds(1.5f);
            Shot("tree_top_view");
        }
        finally { End("hang"); }
    }

    int CountWishes()
    {
        int n = 0;
        foreach (var t in UnityEngine.Object.FindObjectsByType<MeshRenderer>(FindObjectsSortMode.None))
            if ((t.name == "Ribbon" || t.name == "Plaque") && t.transform.parent != null && t.transform.parent.name == "Game") n++;
        return n;
    }

    /// 每一格：人站在挂的那一点，特写镜头放哪（同 HangSequence），镜头不埋在碰撞体里、看布条中间的视线没被挡（人自己的身子也算）；
    /// 每格拍一张小图（slots/）
    IEnumerator CloseUpsAllSlots()
    {
        int n = Get<int>(off, "SlotCount");
        int inside = 0, blocked = 0;
        float minClear = 99;
        var sb = new StringBuilder();
        Directory.CreateDirectory($"{dir}/slots");
        foreach (var f in Directory.GetFiles($"{dir}/slots", "*.png")) File.Delete(f);
        string saveDir = dir;
        var skipped = new List<int>();
        for (int s = 0; s < n; s++)
        {
            if (!Call<bool>(gd, "HangSpotFree", s)) { skipped.Add(s); continue; }
            Vector3 sp = Call<Vector3>(off, "SlotPoint", s), o = Call<Vector3>(off, "Outward", s);
            Vector3 st = sp + o * Get<float>(gd, "hangStand");
            if (Physics.Raycast(st + Vector3.up * 2, Vector3.down, out var hit, 4f, ~(1 << 2), QueryTriggerInteraction.Ignore)) st.y = hit.point.y;
            Teleport(st, sp);
            yield return null;
            Vector3 focus = Call<Vector3>(gd, "HangFocus", s, "ribbon");
            Vector3 eye = Call<Vector3>(gd, "HangEye", s, "ribbon", Me);
            bool inS = Physics.CheckSphere(eye, 0.1f, ~(1 << 2), QueryTriggerInteraction.Ignore);
            bool lc = Physics.Linecast(eye, focus, out var lh, ~(1 << 2), QueryTriggerInteraction.Ignore);
            // 人的身子：一根竖着的胶囊（脚下 0.35..1.2 米，粗 0.2）
            float body = SegDist(eye, focus, Me + Vector3.up * 0.35f, Me + Vector3.up * 1.2f);
            bool byBody = body < 0.2f;
            if (inS) inside++;
            if (lc || byBody) blocked++;
            minClear = Mathf.Min(minClear, Vector3.Distance(eye, focus));
            sb.Append($"{s}:{Vector3.Distance(eye, focus):F1}{(inS ? "埋" : "")}{(lc ? "挡(" + lh.collider.name + ")" : "")}{(byBody ? "身" : "")} ");
            yield return null;
            dir = $"{saveDir}/slots";
            int keep = shot; shot = s;
            yield return ShotFrom($"slot", eye, focus, 46f, 180, 320);
            shot = keep; dir = saveDir;
        }
        Log($"32 格的特写：前面站不了人（自己挂时不挑）的 {string.Join(",", skipped)}；其余镜头埋在碰撞体里 {inside} 格，看布条被挡 {blocked} 格，镜头离布条最近 {minClear:F2} 米；{sb}");
        Assert.LessOrEqual(skipped.Count, 3, "站不了人的格子太多");
        Assert.AreEqual(0, inside, "特写镜头埋在东西里");
        Assert.AreEqual(0, blocked, "特写镜头看布条被挡住");
        Assert.Greater(minClear, 0.9f, "特写镜头离布条太近");
    }

    static float SegDist(Vector3 p1, Vector3 q1, Vector3 p2, Vector3 q2)
    {
        float best = float.MaxValue;
        for (int i = 0; i <= 60; i++)
        {
            Vector3 a = Vector3.Lerp(p1, q1, i / 60f);
            for (int j = 0; j <= 20; j++) best = Mathf.Min(best, Vector3.Distance(a, Vector3.Lerp(p2, q2, j / 20f)));
        }
        return best;
    }

    /// 手心：手腕和中指根之间偏指根的一点（同 HandHold.Palm）
    Vector3 Palm(bool right)
    {
        var an = Get<Animator>(folk, "animator");
        var h = an.GetBoneTransform(right ? HumanBodyBones.RightHand : HumanBodyBones.LeftHand);
        var f = an.GetBoneTransform(right ? HumanBodyBones.RightMiddleProximal : HumanBodyBones.LeftMiddleProximal);
        return f != null ? Vector3.Lerp(h.position, f.position, 0.6f) : h.position;
    }

    static readonly HumanBodyBones[] HandBones =
    {
        HumanBodyBones.LeftHand, HumanBodyBones.LeftIndexProximal, HumanBodyBones.LeftIndexIntermediate, HumanBodyBones.LeftIndexDistal,
        HumanBodyBones.LeftMiddleProximal, HumanBodyBones.LeftMiddleIntermediate, HumanBodyBones.LeftMiddleDistal,
        HumanBodyBones.LeftThumbProximal, HumanBodyBones.LeftThumbIntermediate, HumanBodyBones.LeftThumbDistal,
        HumanBodyBones.RightHand, HumanBodyBones.RightIndexProximal, HumanBodyBones.RightIndexIntermediate, HumanBodyBones.RightIndexDistal,
        HumanBodyBones.RightMiddleProximal, HumanBodyBones.RightMiddleIntermediate, HumanBodyBones.RightMiddleDistal,
        HumanBodyBones.RightThumbProximal, HumanBodyBones.RightThumbIntermediate, HumanBodyBones.RightThumbDistal,
    };

    /// 系的时候（Hang_Loop、布条还在手里）逐帧量：两手手心相对那一格（往外/往上/顺着绳子），手骨离绳子中心线最近多少、有没有伸到绳子里面那一侧
    class HangMeasure
    {
        public int slot = -1;
        public Vector3 lastHeld;
        public float shownLow = -9;
        public int n;
        public Vector3 sumR, sumL;
        public float palmGap = 0, palmFar = 0, ropeMin = 9, inside = -9, heldFar = 0;
        public string ropeBone = "";

        public void Sample(InteractionTest t, Vector3 sp, Vector3 o)
        {
            Vector3 side = Vector3.Cross(Vector3.up, o);
            Vector3 pr = t.Palm(true), pl = t.Palm(false);
            Vector3 Rel(Vector3 p) { Vector3 d = p - sp; return new Vector3(Vector3.Dot(d, o), d.y, Vector3.Dot(d, side)); }
            sumR += Rel(pr);
            sumL += Rel(pl);
            n++;
            palmGap = Mathf.Max(palmGap, Vector3.Distance(pr, pl));
            palmFar = Mathf.Max(palmFar, Mathf.Max(Vector3.Distance(pr, sp), Vector3.Distance(pl, sp)));
            heldFar = Mathf.Max(heldFar, Vector3.Distance(lastHeld, sp));
            // 绳子中心在格子上方 RopeAbove（3 厘米），粗 2.4 厘米；格子附近当它是直的
            Vector3 c = sp + Vector3.up * 0.03f;
            var an = Get<Animator>(t.folk, "animator");
            var pts = new List<(Vector3 p, string name)>();
            foreach (var b in HandBones)
            {
                var bt = an.GetBoneTransform(b);
                if (bt == null) continue;
                pts.Add((bt.position, b.ToString()));
                // 指尖：末节关节再顺着末节往外延 0.8 节
                if (b.ToString().EndsWith("Distal"))
                {
                    var mid = an.GetBoneTransform(b - 1);
                    if (mid != null) pts.Add((bt.position + (bt.position - mid.position) * 0.8f, b.ToString().Replace("Distal", "Tip")));
                }
            }
            foreach (var (p, name) in pts)
            {
                Vector3 d = p - c;
                d -= side * Vector3.Dot(d, side);
                if (d.magnitude < ropeMin) { ropeMin = d.magnitude; ropeBone = name; }
                // 往树那一侧伸过绳子多少（负的是没过）
                inside = Mathf.Max(inside, -Vector3.Dot(p - c, o) - 0.024f);
                // 人站得再往外 shift 米时（整个人平移），这一点离绳子中心多远
                for (int i = 0; i < Shifts.Length; i++) shiftMin[i] = Mathf.Min(shiftMin[i], (d + o * Shifts[i]).magnitude);
            }
        }

        public static readonly float[] Shifts = { -0.02f, 0f, 0.02f, 0.03f, 0.04f, 0.05f, 0.06f };
        public float[] shiftMin = { 9, 9, 9, 9, 9, 9, 9 };

        public string Report()
        {
            if (n == 0) return "系的时候没量到";
            Vector3 r = sumR / n, l = sumL / n;
            return $"系的时候（{n} 帧）右手心相对格子 往外 {r.x:F3} 往上 {r.y:F3} 顺绳 {r.z:F3}，左手心 往外 {l.x:F3} 往上 {l.y:F3} 顺绳 {l.z:F3}；" +
                $"两手心最远相距 {palmGap:F3}，手心离格子最远 {palmFar:F3}，布条挂点离格子最远 {heldFar:F3}；手骨离绳子中心最近 {ropeMin:F3}（{ropeBone}，绳子半径 0.024），伸过绳子到树那一侧最多 {inside:F3} 米；" +
                $"人再往外站 {string.Join(" ", System.Linq.Enumerable.Select(System.Linq.Enumerable.Range(0, Shifts.Length), i => $"{Shifts[i]:+0.00;-0.00}→{shiftMin[i]:F3}"))}（手骨、指尖离绳子中心最近）";
        }
    }

    /// 走到树下，发 offer，一路截图，等 offered；检查挂在那一格上、正面朝外、带字
    IEnumerator Hang(string kind, string view, Vector3 from, string mask, string text)
    {
        Cmd($"{{\"cmd\":\"view\",\"kind\":\"{view}\"}}");
        Teleport(from, new Vector3(-8.6f, 0, -3f));
        yield return new WaitForSeconds(1.2f);
        int n0 = sent.Count;
        Cmd($"{{\"cmd\":\"offer\",\"kind\":\"{kind}\",\"text\":\"{text}\",\"tex\":\"{mask}\"}}");
        // 挂的过程中推摇杆、点画面都不该打断
        Cmd("{\"cmd\":\"move\",\"x\":1,\"y\":0}");
        Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":0}");
        float t0 = Time.time, nextShot = 0;
        int k = 0;
        bool sawCloseUp = false;
        got = null;
        // 手和绳子：拿出来、伸手、系（Hang_Loop）、松手各拍一张近景；系的时候量两手手心离那一格多远、手骨离绳子多近
        var hm = new HangMeasure();
        float heldAt = -1, shownAt = -1, inAt = -1, loopAt = -1, goneAt = -1;
        bool shotHold = false, shotReach = false, shotTie = false, shotOut = false, shotCarry = false;
        Vector3 walkFrom = Me;
        while (Time.time - t0 < 45f)
        {
            for (int i = n0; i < sent.Count; i++)
            {
                var r = JsonUtility.FromJson<Reply>(sent[i]);
                if (r.type == "offered" || r.type == "offerFailed") { got = r; break; }
            }
            if (got != null) break;
            bool cu = Get<bool>(vs, "InCloseUp");
            sawCloseUp |= cu;
            var heldGo = Get<GameObject>(gd, "held");
            string act = Get<string>(folk, "actNow");
            // 走过去的路上：手里捏着布条卷 / 拎着木牌（从右边、稍后一点拍手和腿）
            var carryGo = Get<GameObject>(gd, "carry");
            if (!shotCarry && carryGo != null && Get<bool>(folk, "Moving") && Flat(Me, walkFrom) > 0.4f)
            {
                shotCarry = true;
                var tr = ((Component)folk).transform;
                yield return ShotFrom($"{kind}_carry_walk", Me + tr.right * 1.1f - tr.forward * 0.35f + Vector3.up * 0.75f, Me + Vector3.up * 0.5f, 44f);
                // 最低点按网格的顶点算（渲染器的包围盒为了随风摆放大过）
                float low = float.MaxValue;
                foreach (var mf in carryGo.GetComponentsInChildren<MeshFilter>())
                    foreach (var v in mf.sharedMesh.vertices) low = Mathf.Min(low, mf.transform.TransformPoint(v).y);
                Log($"挂{kind}：走过去时手里拿着 {carryGo.name}，最低点离地 {low - Me.y:F3} 米");
            }
            if (heldGo != null)
            {
                if (heldAt < 0) heldAt = Time.time;
                hm.slot = Get<int>(gd, "heldSlot");
                hm.lastHeld = heldGo.transform.position;
                var rends = heldGo.GetComponentsInChildren<Renderer>();
                if (shownAt < 0 && rends.Length > 0 && rends[0].enabled)
                {
                    shownAt = Time.time;
                    var b = rends[0].bounds;
                    foreach (var r in rends) b.Encapsulate(r.bounds);
                    hm.shownLow = b.min.y - Me.y;
                }
            }
            else if (heldAt >= 0 && goneAt < 0) goneAt = Time.time;
            if (act == "Hang_In" && inAt < 0) inAt = Time.time;
            if (act == "Hang_Loop" && loopAt < 0) loopAt = Time.time;
            if (hm.slot >= 0)
            {
                Vector3 hsp = Call<Vector3>(off, "SlotPoint", hm.slot), ho = Call<Vector3>(off, "Outward", hm.slot);
                // 人面朝那一格（背对外面）：近景的「前、右」按那一格算
                Vector3 pf = -ho, pr = Vector3.Cross(Vector3.up, pf);
                if (shownAt >= 0 && !shotHold && Time.time - shownAt > 0.05f)
                {
                    shotHold = true;
                    yield return ShotFrom($"{kind}_hand_hold", Me + pr * 1.3f + pf * 0.6f + Vector3.up * 1.0f, Me + pf * 0.2f + Vector3.up * 0.75f, 44f);
                }
                if (inAt >= 0 && !shotReach && Time.time - inAt > 0.9f)
                {
                    shotReach = true;
                    yield return ShotFrom($"{kind}_hand_reach", Me + pr * 1.3f + pf * 0.6f + Vector3.up * 1.0f, Me + pf * 0.3f + Vector3.up * 0.85f, 44f);
                }
                if (act == "Hang_Loop" && heldGo != null) hm.Sample(this, hsp, ho);
                if (loopAt >= 0 && !shotTie && Time.time - loopAt > 0.5f)
                {
                    shotTie = true;
                    Vector3 rs = Vector3.Cross(Vector3.up, ho);
                    yield return ShotFrom($"{kind}_hand_tie_side", hsp + rs * 1.2f + ho * 0.35f + Vector3.up * 0.2f, hsp + ho * 0.2f, 40f);
                    yield return ShotFrom($"{kind}_hand_tie_top", hsp + ho * 0.45f + Vector3.up * 1.1f + rs * 0.12f, hsp + ho * 0.12f, 40f);
                    yield return ShotFrom($"{kind}_hand_tie_front", hsp - ho * 1.3f + Vector3.up * 0.35f + rs * 0.3f, hsp + ho * 0.25f + Vector3.up * 0.05f, 44f);
                }
                if (goneAt >= 0 && !shotOut && Time.time - goneAt > 0.6f)
                {
                    shotOut = true;
                    Vector3 rs = Vector3.Cross(Vector3.up, ho);
                    yield return ShotFrom($"{kind}_hand_out_side", hsp + rs * 1.4f + ho * 0.5f + Vector3.up * 0.15f, hsp + ho * 0.25f + Vector3.down * 0.2f, 44f);
                }
            }
            if (Time.time - t0 > nextShot)
            {
                Shot($"{kind}_{view}_{k++}{(cu ? "_close" : "")}");
                nextShot += cu ? 1.0f : 2.5f;
            }
            yield return null;
        }
        if (hm.slot >= 0)
        {
            Vector3 hsp = Call<Vector3>(off, "SlotPoint", hm.slot);
            Log($"挂{kind}的手：拿出来→露出来 {(shownAt - heldAt):F2} 秒（那时下摆离地 {hm.shownLow:F3} 米），→Hang_In {(inAt - heldAt):F2} 秒，→Hang_Loop {(loopAt - heldAt):F2} 秒，→松手 {(goneAt - heldAt):F2} 秒；{hm.Report()}；" +
                $"松手前最后一帧布条挂点离格子 {Vector3.Distance(hm.lastHeld, hsp):F3} 米（松手时跳过去的距离）");
        }
        Assert.IsNotNull(got, $"挂{kind}没有回 offered");
        Assert.AreEqual("offered", got.type, $"挂{kind}失败：{got.reason}");
        int slot = got.slot;
        // 系上那一刻先发 hung（Flutter 这时就记到服务器），合完掌再发 offered
        int hungAt = -1, offeredAt = -1;
        for (int i = n0; i < sent.Count; i++)
        {
            var r = JsonUtility.FromJson<Reply>(sent[i]);
            if (r.type == "hung" && hungAt < 0) { hungAt = i; Assert.AreEqual(slot, r.slot, "hung 和 offered 的格子不一样"); }
            if (r.type == "offered" && offeredAt < 0) offeredAt = i;
        }
        Assert.IsTrue(hungAt >= 0 && hungAt < offeredAt, "系上时没有先发 hung");
        Assert.IsFalse(Call<bool>(gd, "CanHang", slot) == false, "挂到了自己挂不了的格子");
        Vector3 sp = Call<Vector3>(off, "SlotPoint", slot), o = Call<Vector3>(off, "Outward", slot);
        var item = Call<GameObject>(off, "ItemAt", slot);
        Assert.IsNotNull(item, "那一格上没有东西");
        var face = Call<Texture>(off, "FaceAt", slot);
        float facing = Vector3.Angle(item.transform.forward, o);
        Log($"挂{kind}（{view}）：{Time.time - t0:F1} 秒，第 {slot} 格，离格子 {Vector3.Distance(item.transform.position, sp):F3} 米，正面和朝外差 {facing:F0} 度，" +
            $"贴图 {(face != null ? face.width + "×" + face.height : "没有")}，有没有特写 {sawCloseUp}，人离那一格（水平）{Flat(Me, sp):F2} 米");
        Assert.Less(Vector3.Distance(item.transform.position, sp), 0.03f);
        Assert.Less(facing, 3f);
        Assert.IsNotNull(face, "没有写字的贴图");
        Assert.IsTrue(sawCloseUp, "系的时候镜头没有凑近");
        yield return new WaitForSeconds(1.2f);
        Shot($"{kind}_{view}_done");
        // 正面近看：从人旁边一点看（人站在它正前方，镜头太近时人会淡出成网点）
        Vector3 side = Vector3.Cross(Vector3.up, o);
        yield return ShotFrom($"{kind}_text_close", sp + o * (kind == "plaque" ? 0.75f : 1.0f) + side * 0.5f + Vector3.up * 0.02f, sp + Vector3.down * (kind == "plaque" ? 0.24f : 0.3f), 46f);
        yield return ShotFrom($"{kind}_text_level", sp + o * 2.6f + Vector3.up * 0.45f + Vector3.Cross(Vector3.up, o) * 0.6f, sp + Vector3.down * 0.3f, 52f);
        // 合掌那一下：Flutter 那边会接着发 pray，这里补上
        Cmd("{\"cmd\":\"act\",\"action\":\"pray\"}");
        yield return new WaitForSeconds(7.5f);
    }

    // ═══════════════ 1b 绳子挡人、树挂满了、谁的布条 ═══════════════

    int lastSlot;
    string lastOverlap;

    /// 挂一件，等 offered（或 offerFailed）；系的时候（特写、东西在手上）记下人和哪些碰撞体重叠，拍一张特写
    IEnumerator HangOnce(string kind, string mask, string tag)
    {
        int n0 = sent.Count;
        Cmd($"{{\"cmd\":\"offer\",\"kind\":\"{kind}\",\"text\":\"{tag}\",\"tex\":\"{mask}\"}}");
        float t0 = Time.time;
        lastOverlap = null;
        lastSlot = -1;
        got = null;
        while (Time.time - t0 < 40f)
        {
            for (int i = n0; i < sent.Count && got == null; i++)
            {
                var r = JsonUtility.FromJson<Reply>(sent[i]);
                if (r.type == "offered" || r.type == "offerFailed") got = r;
            }
            if (got != null) break;
            if (lastOverlap == null && Get<GameObject>(gd, "held") != null && Get<bool>(vs, "InCloseUp"))
            {
                yield return new WaitForSeconds(1.0f);
                var sb = new StringBuilder();
                foreach (var c in Physics.OverlapCapsule(Me + Vector3.up * 0.3f, Me + Vector3.up * 1.4f, 0.2f, ~(1 << 2), QueryTriggerInteraction.Ignore)) sb.Append(c.name).Append(' ');
                lastOverlap = sb.ToString();
                Shot($"{tag}_tying");
            }
            yield return null;
        }
        if (got != null && got.type == "offered") lastSlot = got.slot;
    }

    [UnityTest, Timeout(600000)]
    public IEnumerator TreeFullAndOwnership()
    {
        yield return Begin("tree");
        try
        {
            // ── 进场时报自己挂不了的格子（绘马架前） ──
            Reply entered = null;
            foreach (var j in sent) { var r = JsonUtility.FromJson<Reply>(j); if (r.type == "entered") entered = r; }
            int n = Get<int>(off, "SlotCount");
            var noHang = new List<int>();
            for (int i = 0; i < n; i++) if (!Call<bool>(gd, "CanHang", i)) noHang.Add(i);
            Log($"entered nohang=\"{entered?.nohang}\"，自己挂不了的 {string.Join(",", noHang)}");
            Assert.IsNotNull(entered);
            Assert.AreEqual(string.Join(",", noHang), entered.nohang);
            Assert.That(noHang.Count, Is.InRange(1, 4));

            // ── 绳子挡人：摇杆往树推，走不进绳圈；点了绳圈里面的地，走到绳外就停 ──
            Cmd("{\"cmd\":\"view\",\"kind\":\"top\"}");
            Vector3 tree = new Vector3(-8.6f, 0, -3f);
            float ropeR = Get<float>(gd, "ropeRadius");
            Assert.Greater(ropeR, 2f);
            float minD = 99;
            foreach (var start in new[] { new Vector3(-5.0f, 0, -4.6f), new Vector3(-8.0f, 0, 0.9f), new Vector3(-12.4f, 0, -1.6f) })
            {
                Teleport(start, tree);
                yield return new WaitForSeconds(0.6f);
                float t0 = Time.time;
                while (Time.time - t0 < 3.5f) { Stick(tree - Me); minD = Mathf.Min(minD, Flat(Me, tree)); yield return null; }
                Stick(Vector3.zero);
                yield return new WaitForSeconds(0.3f);
            }
            Log($"摇杆往树推 3 个方向：离树最近 {minD:F2} 米（绳子半径 {ropeR:F2}，两根桩中间绳子离树 {ropeR * Mathf.Cos(Mathf.PI / 8):F2}）");
            Assert.Greater(minD, ropeR * Mathf.Cos(Mathf.PI / 8) + 0.1f, "人走进绳圈里了");
            Shot("rope_blocks");
            {
                Teleport(new Vector3(-5.2f, 0, -5.6f), tree);
                yield return new WaitForSeconds(1.2f);
                Vector3 inside = tree + new Vector3(1.5f, 0, -0.9f);
                Vector3 vp = cam.WorldToViewportPoint(inside);
                int n0 = sent.Count;
                Cmd($"{{\"cmd\":\"tap\",\"x\":{Inv(vp.x)},\"y\":{Inv(1f - vp.y)}}}");
                yield return Wait("arrived", 15f, n0);
                Log($"点绳圈里面的地 {F(inside)}：{Types(n0)}，停在 {F(Me)}，离树 {Flat(Me, tree):F2} 米");
                Assert.IsNotNull(got, "点了地没有回 arrived");
                Assert.Greater(Flat(Me, tree), ropeR, "点绳圈里面，人走进去了");
            }

            // ── 树上挂满别人的，只剩自己挂不了的几格空着：自己挂的取下最近的一件别人的，不挂到绘马架前 ──
            string shortMask = Mask("mask_ribbon_short", 128, 512);
            for (int i = 0; i < n; i++)
                if (!noHang.Contains(i) && !Call<bool>(off, "SlotUsed", i))
                    Cmd($"{{\"cmd\":\"offerings\",\"kind\":\"{(i % 3 == 0 ? "plaque" : "ribbon")}\",\"list\":\"{i}\",\"id\":\"o{i}\",\"tex\":\"{shortMask}\"}}");
            for (int i = 0; i < 80 && Get<int>(off, "PendingFaces") > 0; i++) yield return null;
            int before = CountWishes();
            var byId = Get<IDictionary>(off, "byId");
            Cmd("{\"cmd\":\"view\",\"kind\":\"level\"}");
            Teleport(new Vector3(-11.6f, 0, -5.6f), tree);
            yield return new WaitForSeconds(1.2f);
            yield return HangOnce("ribbon", Mask("mask_ribbon", 128, 512), "busy1");
            int s1 = lastSlot;
            Log($"挂满别人的（{before} 件，空着 {string.Join(",", noHang)}）从绘马架旁边挂：挂在第 {s1} 格，系的时候人和这些重叠 [{lastOverlap}]，" +
                $"原来那件 o{s1} 还在吗 {byId.Contains("o" + s1)}，件数 {before}→{CountWishes()}");
            Assert.GreaterOrEqual(s1, 0, "挂满别人的时候没挂上：" + (got != null ? got.reason : "没回"));
            Assert.IsFalse(noHang.Contains(s1), "挂到绘马架前去了");
            Assert.IsTrue(string.IsNullOrEmpty(lastOverlap?.Trim()), "系的时候人站在东西里：" + lastOverlap);
            Assert.IsFalse(byId.Contains("o" + s1), "别人的那件没取下来");
            Assert.IsFalse(Call<bool>(off, "OthersAt", s1));
            Assert.IsNotNull(Call<Texture>(off, "FaceAt", s1));
            Assert.AreEqual(before, CountWishes());
            yield return new WaitForSeconds(1f);
            Shot("busy1_done");
            Cmd("{\"cmd\":\"act\",\"action\":\"pray\"}");
            yield return new WaitForSeconds(7.5f);

            // ── 自己刚挂的那件还没编号：别人的心意（mine 没带）发到同一格不会被它认领、吞掉；自己的（mine）才认领 ──
            var mine1 = Call<GameObject>(off, "ItemAt", s1);
            Cmd($"{{\"cmd\":\"offerings\",\"kind\":\"ribbon\",\"list\":\"{s1}\",\"id\":\"888\",\"tex\":\"{shortMask}\"}}");
            yield return null;
            int afterOther = CountWishes();
            bool otherShown = byId.Contains("888");
            Cmd($"{{\"cmd\":\"offerings\",\"kind\":\"ribbon\",\"list\":\"{s1}\",\"id\":\"777\",\"mine\":true}}");
            yield return null;
            Log($"自己刚挂的第 {s1} 格：别人的 888 发到这格 → 件数 {afterOther}，888 挂出来了 {otherShown}，这格还是自己那件 {Call<GameObject>(off, "ItemAt", s1) == mine1}；" +
                $"自己的 777（mine）→ 件数 {CountWishes()}，认领了 {byId.Contains("777") && Call<GameObject>(off, "ItemAt", s1) == mine1}");
            Assert.AreEqual(before + 1, afterOther, "别人的心意被自己刚挂的那件吞掉了");
            Assert.IsTrue(otherShown);
            Assert.AreEqual(mine1, Call<GameObject>(off, "ItemAt", s1));
            Assert.AreEqual(before + 1, CountWishes(), "自己的那件又挂了一件");
            Assert.IsTrue(byId.Contains("777"), "自己的编号没认领");

            // ── 再挂一件（另一边）：又取下一件别人的 ──
            Teleport(new Vector3(-5.6f, 0, -0.6f), tree);
            yield return new WaitForSeconds(1.2f);
            yield return HangOnce("plaque", Mask("mask_plaque", 256, 320), "busy2");
            int s2 = lastSlot;
            Log($"再挂一件木牌：第 {s2} 格，系的时候人和这些重叠 [{lastOverlap}]");
            Assert.GreaterOrEqual(s2, 0);
            Assert.IsFalse(noHang.Contains(s2));
            Assert.IsTrue(string.IsNullOrEmpty(lastOverlap?.Trim()), "系的时候人站在东西里：" + lastOverlap);
            yield return new WaitForSeconds(1f);

            // ── 重新进殿（联网）：服务器没认的（没编号的第二件）收掉，认了的（777）留着 ──
            Cmd("{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":0,\"name\":\"测试\"}");
            yield return new WaitForSeconds(1.5f);
            Log($"重新进殿：没认的第 {s2} 格还挂着 {Call<GameObject>(off, "ItemAt", s2) != null}（占着 {Call<bool>(off, "SlotUsed", s2)}），认了的第 {s1} 格还挂着 {Call<GameObject>(off, "ItemAt", s1) != null}");
            Assert.IsNull(Call<GameObject>(off, "ItemAt", s2));
            Assert.IsFalse(Call<bool>(off, "SlotUsed", s2));
            Assert.IsNotNull(Call<GameObject>(off, "ItemAt", s1));

            // ── 挂得了的格子全是自己的：才算挂满（offerFailed full），也不挂到绘马架前 ──
            var place5 = M(off, "Place", 5);
            for (int i = 0; i < n; i++)
            {
                if (!Call<bool>(gd, "CanHang", i)) continue;
                Run(off, "Evict", i);
                if (Call<GameObject>(off, "ItemAt", i) == null) place5.Invoke(off, new object[] { "plaque", i, "m" + i, null, true });
            }
            // 取下来的那些（Destroy）要过一两帧才真没了，再数
            yield return new WaitForSeconds(0.3f);
            int full = CountWishes();
            Teleport(new Vector3(-11.6f, 0, -5.6f), tree);
            yield return new WaitForSeconds(1.0f);
            yield return HangOnce("ribbon", shortMask, "full");
            Log($"挂得了的全是自己的（{full} 件）：{(got != null ? got.type + " " + got.reason : "没回")}，件数 {CountWishes()}，acting={Get<bool>(gd, "acting")}");
            Assert.IsNotNull(got);
            Assert.AreEqual("offerFailed", got.type);
            Assert.AreEqual("full", got.reason);
            Assert.AreEqual(full, CountWishes());
            Assert.IsFalse(Get<bool>(gd, "acting"));
            yield return ShotFrom("tree_full", tree + new Vector3(4.2f, 2.4f, -3.4f), tree + Vector3.up * 0.9f, 55f);
        }
        finally { End("tree"); }
    }

    // ═══════════════ 2 抢座位、香客改道、摇杆残留的速度 ═══════════════

    [UnityTest, Timeout(600000)]
    public IEnumerator SeatRacesAndCrowd()
    {
        yield return Begin("races");
        try
        {
            Cmd("{\"cmd\":\"view\",\"kind\":\"level\"}");
            yield return new WaitForSeconds(0.5f);

            // ── C：走到蒲团前、转身要坐的那一下起身：不该坐下去，MySeat 也不该乱 ──
            {
                int S = 40;
                Vector3 ground = Call<Vector3>(gd, "SeatGround", S);
                Vector3 side = ground + new Vector3(0.9f, 0, 0.3f);
                Teleport(side, side + Vector3.back * 3);
                yield return new WaitForSeconds(0.6f);
                int n0 = sent.Count;
                Cmd($"{{\"cmd\":\"sit\",\"seat\":{S}}}");
                float t0 = Time.time;
                // 等走到跟前开始转身（sitting 有值）
                while (Get<Coroutine>(gd, "sitting") == null && Time.time - t0 < 10f) yield return null;
                bool turning = Get<Coroutine>(gd, "sitting") != null;
                int pendingThen = Get<int>(gd, "MySeat");
                Cmd("{\"cmd\":\"stand\"}");
                yield return new WaitForSeconds(4f);
                string pose = Get<object>(folk, "pose").ToString();
                int my = Get<int>(gd, "MySeat");
                Log($"C 转身坐下那一下（{turning}，那时 MySeat={pendingThen}）发 stand：4 秒后 MySeat={my}，姿势 {pose}，消息 {Types(n0)}");
                Assert.IsTrue(turning, "没等到转身那一下");
                Assert.AreEqual(S, pendingThen, "走过去的路上座位应该算自己的（pendingSeat）");
                Assert.AreEqual(-1, my);
                Assert.AreEqual("None", pose, "不该坐下去");
                Assert.AreEqual(0, Count("seated", n0), "不该发 seated");
                Assert.Greater(Count("arrived", n0), 0, "要回 arrived，界面别等");
                // 转身时推摇杆：一样不坐
                n0 = sent.Count;
                Teleport(side, side + Vector3.back * 3);
                yield return new WaitForSeconds(0.4f);
                Cmd($"{{\"cmd\":\"sit\",\"seat\":{S}}}");
                t0 = Time.time;
                while (Get<Coroutine>(gd, "sitting") == null && Time.time - t0 < 10f) yield return null;
                Stick(Vector3.right);
                yield return new WaitForSeconds(0.3f);
                Stick(Vector3.zero);
                yield return new WaitForSeconds(3f);
                Log($"C 转身时推摇杆：MySeat={Get<int>(gd, "MySeat")}，姿势 {Get<object>(folk, "pose")}，消息 {Types(n0)}");
                Assert.AreEqual(-1, Get<int>(gd, "MySeat"));
                Assert.AreEqual(0, Count("seated", n0));
            }

            // ── D：香客正走去 50 号的路上，服务器把他改到 51 号：坐到 51，50 号空着、没人坐在上面 ──
            {
                var place8 = M(pil, "Place", 8);
                place8.Invoke(pil, new object[] { "nX", 50, true, "测试香客", true, "ts", 1f, 900f });
                yield return new WaitForSeconds(0.5f);
                var people = Get<IDictionary>(pil, "people");
                object p = people["nX"];
                // 行程里该去静坐了（来了 200 秒）：自己从树下走去 50 号
                Set(p, "arrive", Time.time - 200f);
                yield return new WaitForSeconds(2.5f);
                Log($"D 走去 50 号的路上：toSeat={Get<int>(p, "toSeat")}，在 {F(((Component)Get<object>(p, "folk")).transform.position)}");
                Assert.AreEqual(50, Get<int>(p, "toSeat"), "香客没在去 50 号的路上");
                place8.Invoke(pil, new object[] { "nX", 51, true, "测试香客", false, "ts", 200f, 900f });
                float t0 = Time.time;
                while (!Get<bool>(p, "seated") && Time.time - t0 < 60f) yield return null;
                var pf = (Component)Get<object>(p, "folk");
                Vector3 s50 = Call<Transform>(pil, "Seat", 50).position, s51 = Call<Transform>(pil, "Seat", 51).position;
                bool t50 = Call<bool>(pil, "Taken", 50), t51 = Call<bool>(pil, "Taken", 51);
                Log($"D 走到一半改座位：坐下了={Get<bool>(p, "seated")}，p.seat={Get<int>(p, "seat")}，人离 50 号 {Flat(pf.transform.position, s50):F2} 米、离 51 号 {Flat(pf.transform.position, s51):F2} 米；Taken(50)={t50} Taken(51)={t51}，用了 {Time.time - t0:F0} 秒");
                Assert.IsTrue(Get<bool>(p, "seated"));
                Assert.AreEqual(51, Get<int>(p, "seat"));
                Assert.Less(Flat(pf.transform.position, s51), 0.1f, "应该坐在 51 号上");
                Assert.IsFalse(t50);
                Assert.IsTrue(t51);
                Vector3 lane = Call<Vector3>(gd, "SeatLane", 51);
                Teleport(lane, lane + Vector3.forward * 3);
                yield return new WaitForSeconds(0.4f);
                int nearest = Call<int>(gd, "NearestSeat", Me, 1.2f);
                Log($"D   玩家站在 51 号前：NearestSeat = {nearest}");
                Assert.AreNotEqual(51, nearest, "有人坐着的蒲团不该给玩家坐");
                M(pil, "Sync", 1).Invoke(pil, new object[] { new HashSet<string>() });
                yield return new WaitForSeconds(1f);
            }

            // ── H：被香客记着、但他这会儿在树下的蒲团：看着是空的，走过去有「坐下」，坐了以后他换一个 ──
            {
                var place8 = M(pil, "Place", 8);
                place8.Invoke(pil, new object[] { "nR", 26, true, "记座的", true, "ts", 1f, 900f });
                yield return new WaitForSeconds(0.3f);
                var people = Get<IDictionary>(pil, "people");
                object p = people["nR"];
                bool occ = Call<bool>(pil, "Occupied", 26), taken = Call<bool>(pil, "Taken", 26);
                Vector3 lane = Call<Vector3>(gd, "SeatLane", 26);
                Teleport(lane, lane + Vector3.forward * 3);
                yield return new WaitForSeconds(0.4f);
                int near = LastNearSeat();
                int n0 = sent.Count;
                Cmd($"{{\"cmd\":\"sit\",\"seat\":{near}}}");
                yield return Wait("seated", 12f, n0);
                int sat = got != null ? got.seat : -1;
                int theirs = Get<int>(p, "seat");
                Log($"H 26 号被树下的香客记着（Occupied={occ}，Taken={taken}）：站在它前面 near={near}，坐下 {sat}，那位香客改记 {theirs}");
                Assert.IsTrue(occ);
                Assert.IsFalse(taken);
                Assert.AreEqual(26, near);
                Assert.AreEqual(26, sat);
                Assert.AreNotEqual(26, theirs);
                yield return new WaitForSeconds(2.5f);
                n0 = sent.Count;
                Cmd("{\"cmd\":\"stand\"}");
                yield return Wait("arrived", 10f, n0);
                M(pil, "Sync", 1).Invoke(pil, new object[] { new HashSet<string>() });
            }

            // ── R：别的玩家（真人）正从栈桥走去 26 号：26 号算有人，「坐下」给的是别的（以前玩家能先坐上，他走到了就站在玩家的垫子上）；
            //    万一路上的真人还是记着玩家坐的那个（两边同时挑了同一个），他走到跟前也不站在玩家的垫子上，换一个空的 ──
            {
                yield return new WaitForSeconds(0.5f);
                // 先来一份空名单：之后新来的人从栈桥走进来（第一份名单上的人一进场就已经坐着）
                Cmd("{\"cmd\":\"pilgrims\",\"list\":\"\"}");
                Cmd("{\"cmd\":\"pilgrims\",\"list\":\"u99:26:0:路人\"}");
                yield return new WaitForSeconds(1.5f);
                var people = Get<IDictionary>(pil, "people");
                bool walking = people.Contains("u99") && !Get<bool>(people["u99"], "seated");
                bool taken = Call<bool>(pil, "Taken", 26);
                Vector3 lane = Call<Vector3>(gd, "SeatLane", 26);
                Teleport(lane, lane + Vector3.forward * 3);
                yield return new WaitForSeconds(0.5f);
                int near = LastNearSeat();
                int n0 = sent.Count;
                Cmd("{\"cmd\":\"sit\",\"seat\":26}");
                yield return Wait("seated", 12f, n0);
                int sat = got != null ? got.seat : -1;
                Log($"R 真人在路上去 26 号（还在走={walking}）：Taken(26)={taken}，站在 26 号前 near={near}，「坐下 26」坐到了 {sat}");
                Assert.IsTrue(walking && taken, "真人在路上，26 号应该算有人");
                Assert.AreNotEqual(26, near);
                Assert.AreNotEqual(26, sat);
                Assert.GreaterOrEqual(sat, 0);
                // 另一位真人：已经在岛上，却记着玩家坐的这个座位，走过来
                Cmd("{\"cmd\":\"pilgrims\",\"list\":\"u99:26:0:路人|u98:55:0:路人二\"}");
                yield return new WaitForSeconds(1.0f);
                object u98 = people.Contains("u98") ? people["u98"] : null;
                Assert.IsNotNull(u98);
                var uf = ((Component)Get<object>(u98, "folk")).transform;
                uf.position = new Vector3(0, 0.07f, 1.0f);
                Set(u98, "seat", sat);
                Run(pil, "GoSit", u98, false);
                Vector3 stand = Call<Vector3>(gd, "SeatStand", sat);
                float dwell = 0, t0 = Time.time;
                while (Time.time - t0 < 30f)
                {
                    // 名单每 6 秒来一次（服务器上他还排在这个座位）
                    if ((int)((Time.time - t0) / 6f) != (int)((Time.time - t0 - Time.deltaTime) / 6f))
                        Cmd($"{{\"cmd\":\"pilgrims\",\"list\":\"u99:26:0:路人|u98:{sat}:0:路人二\"}}");
                    if (Flat(uf.position, stand) < 0.5f) dwell += Time.deltaTime;
                    yield return null;
                }
                int theirs = Get<int>(u98, "seat");
                bool seatedThere = Get<bool>(u98, "seated");
                float endD = Flat(uf.position, stand);
                Log($"R 玩家坐在 {sat}，路上的真人记着同一个：他改去 {theirs}（坐下了 {seatedThere}），在玩家站点 0.5 米内待了 {dwell:F1} 秒，最后离它 {endD:F2} 米，玩家 MySeat={Get<int>(gd, "MySeat")}");
                Assert.AreNotEqual(sat, theirs, "路上的真人还记着玩家的座位");
                Assert.Less(dwell, 3f, "真人在玩家的垫子上站着不走");
                Assert.Greater(endD, 0.6f, "真人站在玩家的垫子上");
                Assert.AreEqual(sat, Get<int>(gd, "MySeat"));
                Vector3 me = Me;
                yield return ShotFrom("real_visitor", me + new Vector3(2.2f, 1.6f, 2.2f), me + Vector3.up * 0.5f, 50f);
                n0 = sent.Count;
                Cmd("{\"cmd\":\"stand\"}");
                yield return Wait("arrived", 10f, n0);
                M(pil, "Sync", 1).Invoke(pil, new object[] { new HashSet<string>() });
                yield return new WaitForSeconds(0.5f);
            }

            // ── G：按着摇杆走、点鞠躬、马上松手：鞠躬那几秒里人不该挪 ──
            {
                Vector3 start = new Vector3(5.0f, 0.06f, -8.0f);
                Teleport(start, start + Vector3.left * 3);
                yield return new WaitForSeconds(0.6f);
                float t0 = Time.time;
                while (Time.time - t0 < 0.6f) { Stick(Vector3.left); yield return null; }
                int n0 = sent.Count;
                Cmd("{\"cmd\":\"act\",\"action\":\"bow\"}");
                Stick(Vector3.zero);
                // 松手后人先把停步那两步走完（真的迈步、脚踩稳，Folk 这时把鞠躬压在第一帧、权重 0），停稳了才弯腰：
                // 停步走了多远单独记；从停稳（或者鞠躬已经看得出来）起，人一点都不该再挪
                Vector3 at = Me;
                Vector3? settled = null;
                float stopDist = 0, most = 0, bowWhileMoving = 0;
                t0 = Time.time;
                got = null;
                while (got == null && Time.time - t0 < 10f)
                {
                    string lc = Get<object>(folk, "loco").ToString();
                    float aw = Get<float>(folk, "actW");
                    stopDist = Mathf.Max(stopDist, Flat(Me, at));
                    if (settled == null && (lc == "Idle" || aw > 0.05f)) settled = Me;
                    if (settled != null) most = Mathf.Max(most, Flat(Me, settled.Value));
                    if (lc != "Idle") bowWhileMoving = Mathf.Max(bowWhileMoving, aw);
                    yield return Wait("actionDone", 0.02f, n0);
                }
                Log($"G 按着摇杆点鞠躬：松手后停步走了 {stopDist:F3} 米（自然停步），停稳后鞠躬时人挪了 {most:F3} 米，还在走/停时鞠躬权重最多 {bowWhileMoving:F2}");
                Assert.Less(stopDist, 0.6f, "松手后停得太远");
                Assert.Less(most, 0.05f, "做动作时人在滑");
                Assert.Less(bowWhileMoving, 0.1f, "还没停稳就弯腰了");
            }

            // ── E3：人正好站在挂的那一点上，推一下摇杆马上松开再挂：不该滑走 ──
            {
                int s = Call<int>(gd, "HangSlot", new Vector3(-6.0f, 0, -6.0f));
                Vector3 sp = Call<Vector3>(off, "SlotPoint", s), o = Call<Vector3>(off, "Outward", s);
                Vector3 st = sp + o * Get<float>(gd, "hangStand");
                if (Physics.Raycast(st + Vector3.up * 2, Vector3.down, out var hit, 4f, ~(1 << 2), QueryTriggerInteraction.Ignore)) st.y = hit.point.y;
                Teleport(st, sp);
                yield return new WaitForSeconds(0.8f);
                int n0 = sent.Count;
                Stick(o);
                yield return null;
                Cmd($"{{\"cmd\":\"offer\",\"kind\":\"ribbon\",\"text\":\"z\",\"tex\":\"{Mask("mask_ribbon_short", 128, 512)}\"}}");
                Stick(Vector3.zero);
                float t0 = Time.time, most = 0;
                got = null;
                while (Time.time - t0 < 20f && got == null)
                {
                    most = Mathf.Max(most, Flat(Me, st));
                    yield return Wait("offered", 0.02f, n0);
                }
                Log($"E3 站在挂的点上推一下摇杆再挂：{(got != null ? "offered 第 " + got.slot + " 格" : "没回")}，过程中离挂的点最远 {most:F2} 米");
                Assert.IsNotNull(got);
                Assert.Less(most, 0.6f, "挂布条时人滑走了");
                Cmd("{\"cmd\":\"act\",\"action\":\"pray\"}");
                yield return Wait("actionDone", 12f, n0);
            }

            // ── 蒲团之间（第 2 排两个圆蒲团中间）往外走：先顺着南北走到走道上，不沿着那一排穿过别的蒲团 ──
            {
                Vector3 between = new Vector3(-3.18f, 0.07f, 4.8f);
                var path = Call<List<Vector3>>(gd, "PlanPath", between, new Vector3(0, 0.06f, -4f));
                var sb = new StringBuilder();
                foreach (var q in path) sb.Append(F(q)).Append(' ');
                Log($"蒲团之间出座位区的路线：{sb}");
                Assert.Less(Mathf.Abs(path[0].x - between.x), 0.01f, "第一段应该顺着南北走到走道上");
                // 每一段都不穿过圆蒲团（半径 0.2，人再宽 0.15）
                Vector3 prev = between;
                foreach (var q in path)
                {
                    for (int i = 0; i < 60; i++)
                    {
                        Vector3 x = Vector3.Lerp(prev, q, (i + 0.5f) / 60f);
                        for (int k = 0; k < 60; k++)
                            Assert.Greater(Flat(x, Call<Vector3>(gd, "SeatGround", k)), 0.3f, $"路线踩到第 {k} 号圆蒲团（{F(x)}）");
                    }
                    prev = q;
                }
            }
        }
        finally { End("races"); }
    }

    // ═══════════════ 3 大殿里面 ═══════════════

    /// 真大殿里挡人的东西（BuildHall 的碰撞：墙、门边、门扇、金柱、佛坛、供桌、磬、木鱼、功德箱、经案）。地面、台阶、廊下、天花板不算
    static readonly string[] HallFloors = { "Platform", "Floor", "Porch", "SideWalkW", "SideWalkE", "BackWalk", "Threshold", "Ceiling", "PorchCeiling" };
    static bool HallSolid(Collider c, Transform colliders) =>
        c.transform.IsChildOf(colliders) && !c.name.StartsWith("Step") && Array.IndexOf(HallFloors, c.name) < 0;

    /// 跪拜那几秒里拍：侧后方看人和拜垫、佛像（两边的拜垫从外侧拍，里侧有金柱挡着）
    IEnumerator ShotKneel(string name, Vector3 mat)
    {
        float dx = Mathf.Abs(mat.x) > 2f ? Mathf.Sign(mat.x) * 1.3f : mat.x < -0.5f ? 1.5f : -1.5f;
        yield return ShotFrom(name, mat + new Vector3(dx, 1.25f, Mathf.Abs(mat.x) > 2f ? -1.4f : -1.7f), mat + new Vector3(0, 0.55f, 0.6f), 48f);
    }

    [UnityTest, Timeout(900000)]
    public IEnumerator HallInterior()
    {
        yield return Begin("hall");
        try
        {
            // 真的大殿（BuildIslet.HallOpen 为 true、BuildHall 摆好了殿、殿里的东西和碰撞）：不再搭临时的替身
            Assert.IsTrue(Get<bool>(gd, "hallOpen"), "BuildIslet.HallOpen 是 false：大殿进不去");
            var hallColliders = GameObject.Find("World/Structure/hall/Colliders");
            Assert.IsNotNull(hallColliders, "场景里没有新大殿的碰撞（BuildHall）");
            Assert.IsNull(GameObject.Find("World/Structure/hall/Colliders/DoorShut"), "殿门口还拦着隔板");
            var hc = hallColliders.transform;
            Cmd("{\"cmd\":\"view\",\"kind\":\"top\"}");
            yield return new WaitForSeconds(0.8f);

            // ── 路线：从院子去殿里的蒲团，经过门外、门里那两点；殿里那一段不撞柱子、门扇、陈设 ──
            {
                Vector3 hallLane = Call<Vector3>(gd, "SeatLane", 60 + 6);
                var path = Call<List<Vector3>>(gd, "PlanPath", new Vector3(-3f, 0.07f, 0f), hallLane);
                var sb = new StringBuilder();
                foreach (var q in path) sb.Append(F(q)).Append(' ');
                Log($"院子 → 殿里 66 号蒲团前：{sb}");
                bool door0 = path.Exists(q => Flat(q, new Vector3(0, 0, 14.0f)) < 0.01f), door1 = path.Exists(q => Flat(q, new Vector3(0, 0, 15.0f)) < 0.01f);
                Assert.IsTrue(door0 && door1, "要经过殿门");
                // 殿里的路：从门里、从中间拜垫后面、从西边拜垫旁，走到每块拜垫、供桌前、每个蒲团前的走道：
                // 人（粗 0.2 米的胶囊）一路不碰真大殿的柱子、门扇、磬、木鱼、功德箱、经案、供桌、墙
                var targets = new List<(string, Vector3)>();
                var hm = Get<Transform>(gd, "hallMats");
                for (int i = 0; i < hm.childCount; i++) targets.Add(($"拜垫{i}", hm.GetChild(i).position));
                targets.Add(("供桌前", Get<Vector3>(gd, "altarStand")));
                for (int i = 60; i < Get<int>(gd, "SeatTotal"); i++) targets.Add(($"蒲团{i}", Call<Vector3>(gd, "SeatLane", i)));
                int bad = 0;
                var hits = new StringBuilder();
                float longest = 0;
                string longestLeg = "";
                foreach (var from in new[] { new Vector3(0, 0.72f, 15.0f), new Vector3(0, 0.72f, 17.1f), new Vector3(-4.0f, 0.72f, 18.6f) })
                    foreach (var (name, to) in targets)
                    {
                        var pp = Call<List<Vector3>>(gd, "PlanPath", from, to);
                        Vector3 prev = from;
                        float len = 0;
                        foreach (var q in pp) { len += Flat(prev, q); prev = q; }
                        // 绕远了多少：路线长度比直线长出的比例（以前经案挡着金柱之间，去西边的蒲团要绕到北边去，长出 4 米）
                        float extra = len - Flat(from, to);
                        if (extra > longest) { longest = extra; longestLeg = $"{F(from)}→{name}"; }
                        prev = from;
                        foreach (var q in pp)
                        {
                            for (float d = 0; d <= Flat(prev, q); d += 0.05f)
                            {
                                Vector3 x = Vector3.MoveTowards(new Vector3(prev.x, 0.72f, prev.z), new Vector3(q.x, 0.72f, q.z), d);
                                foreach (var c in Physics.OverlapCapsule(x + Vector3.up * 0.3f, x + Vector3.up * 1.4f, 0.2f, ~0, QueryTriggerInteraction.Ignore))
                                    if (HallSolid(c, hc))
                                    {
                                        bad++;
                                        if (hits.Length < 400) hits.Append($"{F(from)}→{name} 在 {F(x)} 碰到 {c.name}；");
                                        goto nextLeg;
                                    }
                            }
                            prev = q;
                        }
                        nextLeg:;
                    }
                // 去西边、东边蒲团：两根金柱之间空出来了，直接从中间穿过去（不再绕到北边）
                foreach (int s in new[] { 60 + 1, 60 + 5, 60 + 9, 60 + 13 })
                {
                    var pw = Call<List<Vector3>>(gd, "PlanPath", new Vector3(0, 0.72f, 15.0f), Call<Vector3>(gd, "SeatLane", s));
                    float maxZ = 0;
                    var wsb = new StringBuilder();
                    foreach (var q in pw) { maxZ = Mathf.Max(maxZ, q.z); wsb.Append(F(q)).Append(' '); }
                    Log($"门里 → 蒲团{s} 前：{wsb}（最北 z {maxZ:F2}）");
                    Assert.Less(maxZ, 17.8f, $"去蒲团{s} 绕到金柱北边去了");
                }
                // 两边拜垫的走法：从过道边 (±1.6, 18.6) 到拜垫（props.md §5 的通道）
                var side = Call<List<Vector3>>(gd, "PlanPath", new Vector3(1.6f, 0.72f, 18.6f), hm.GetChild(4).position);
                var ssb = new StringBuilder();
                foreach (var q in side) ssb.Append(F(q)).Append(' ');
                Log($"殿里的路：{targets.Count} 个去处 × 3 个起点，人碰到东西 {bad} 段 {hits}；绕得最远的一段多走 {longest:F2} 米（{longestLeg}）；过道边 → 东边拜垫：{ssb}");
                Assert.AreEqual(0, bad, "殿里的路线碰到东西");
            }
            // ── 走进殿：用摇杆从廊下往北推（俯视进去），一进门就换成平视、锁住 ──
            Teleport(new Vector3(0, 0.74f, 12.8f), new Vector3(0, 0.74f, 20f));
            yield return new WaitForSeconds(1.0f);
            Shot("porch_top");
            int n0 = sent.Count;
            float t0 = Time.time;
            while (Me.z < 15.6f && Time.time - t0 < 8f) { Stick(Vector3.forward); yield return null; }
            Stick(Vector3.zero);
            yield return Wait("view", 1f, n0, r => r.locked);
            Assert.IsNotNull(got, "进殿没有发 view locked");
            Assert.AreEqual("level", got.mode);
            Log($"摇杆走进殿：到了 {F(Me)}，view {got.mode} locked={got.locked}，Interior={Get<bool>(vs, "Interior")}，消息 {Types(n0)}");
            yield return Wait("arrived", 1f, n0, r => r.spot == "inhall");
            Assert.IsNotNull(got, "进殿以后 arrived 应该是 inhall");
            yield return new WaitForSeconds(1.5f);
            Shot("in_level");
            // 俯视、仰视点不了；第一人称可以
            n0 = sent.Count;
            Cmd("{\"cmd\":\"view\",\"kind\":\"top\"}");
            yield return Wait("view", 1f, n0);
            Assert.AreEqual("level", got.mode, "殿里不该换成俯视");
            Assert.IsTrue(got.locked);
            Cmd("{\"cmd\":\"view\",\"kind\":\"first\"}");
            yield return new WaitForSeconds(1.0f);
            Assert.AreEqual("first", Get<string>(vs, "Mode"));
            Shot("in_first");
            Cmd("{\"cmd\":\"view\",\"kind\":\"level\"}");
            yield return new WaitForSeconds(1.2f);
            // 镜头：离人 2.6 米上下（ViewSwitcher.interiorDistance：人整个、佛像整尊放得进界面中间那一截）、不高过梁底
            var follow = Get<object>(vs, "follow");
            float dist = Get<float>(follow, "CurrentDistance");
            Log($"殿里平视：镜头离人 {dist:F2} 米，镜头高 {cam.transform.position.y:F2}，被挡 {Get<string>(follow, "LastHit")}");
            Assert.LessOrEqual(dist, 2.65f);
            // 往上看到头：不穿天花板
            for (int i = 0; i < 10; i++) { Cmd("{\"cmd\":\"look\",\"dx\":0,\"dy\":-0.2}"); yield return null; }
            yield return new WaitForSeconds(1.0f);
            float camY = cam.transform.position.y;
            Shot("in_look_down");
            for (int i = 0; i < 10; i++) { Cmd("{\"cmd\":\"look\",\"dx\":0,\"dy\":0.2}"); yield return null; }
            yield return new WaitForSeconds(1.0f);
            Log($"殿里镜头：压低看 {camY:F2} 米高，抬到最高 {cam.transform.position.y:F2} 米高（梁底 5.35）");
            Assert.Less(Mathf.Max(camY, cam.transform.position.y), 5.1f, "镜头穿到天花板上面去了");
            // 放回平常的俯角（16 度上下）
            Cmd("{\"cmd\":\"look\",\"dx\":0,\"dy\":-0.23}");
            yield return new WaitForSeconds(0.6f);
            // 镜头躲墙：贴着西墙站、背对墙（西边外侧两排蒲团之间，墙里 0.27 米）
            Teleport(new Vector3(-6.2f, 0.76f, 16.4f), new Vector3(0, 0.76f, 16.4f));
            yield return new WaitForSeconds(1.5f);
            Vector3 cp = cam.transform.position;
            Log($"贴着西墙：镜头在 {F(cp)}，离人 {Get<float>(follow, "CurrentDistance"):F2} 米");
            Assert.Greater(cp.x, -6.47f, "镜头钻到墙外面去了");
            Shot("in_wall");

            // ── 拜垫：0.9 米以内才报，在那块拜垫上跪拜（站上去、面朝佛像、跪下叩首三次）。中间三块在 z 17.8，两边两块在 z 18.5 ──
            Vector3 mat1 = new Vector3(0, 0.72f, 17.8f);
            Teleport(new Vector3(0.3f, 0.74f, 16.8f), new Vector3(0, 0.74f, 21f));
            yield return new WaitForSeconds(0.6f);
            var nr = LastNear();
            Log($"离中间拜垫 {Flat(Me, mat1):F2} 米：near mat={nr.mat} altar={nr.altar}");
            Assert.AreEqual(-1, nr.mat, "1 米外不该报拜垫");
            Teleport(new Vector3(0.3f, 0.74f, 17.15f), new Vector3(0, 0.74f, 21f));
            yield return new WaitForSeconds(0.6f);
            nr = LastNear();
            Log($"离中间拜垫 {Flat(Me, mat1):F2} 米：near mat={nr.mat} altar={nr.altar}");
            Assert.AreEqual(1, nr.mat);
            Assert.IsTrue(nr.altar, "离供桌前那一点 1.3 米，应该能上香");
            Shot("near_mat");
            // 每一块拜垫都跪一次：从垫子跟前（0.7 米）点「跪拜」，走上去、转向佛像、跪下、叩首三次、起来
            var mats = Get<Transform>(gd, "hallMats");
            for (int i = 0; i < mats.childCount; i++)
            {
                Vector3 mp = mats.GetChild(i).position;
                Vector3 start = i < 3 ? mp + new Vector3(0.3f, 0.02f, -0.65f) : mp + new Vector3(mp.x < 0 ? 0.7f : -0.7f, 0.02f, 0.15f);
                Teleport(start, new Vector3(mp.x, 0.74f, 21f));
                yield return new WaitForSeconds(0.6f);
                nr = LastNear();
                Assert.AreEqual(i, nr.mat, $"站在拜垫{i} 跟前 {Flat(Me, mp):F2} 米，near 报的是 {nr.mat}");
                n0 = sent.Count;
                Cmd($"{{\"cmd\":\"act\",\"action\":\"kneel\",\"mat\":{i}}}");
                t0 = Time.time;
                got = null;
                Vector3 onMat = Vector3.zero;
                float yaw = 0, deepestBow = 0;
                bool kneelShot = false, kowtowShot = false;
                while (Time.time - t0 < 30f)
                {
                    yield return Wait("actionDone", 0.02f, n0);
                    if (got != null) break;
                    string act = Get<string>(folk, "actNow");
                    if (act == "Kowtow_Scrub")
                    {
                        float b = Get<float>(folk, "bowPhase");
                        if (b > deepestBow) { deepestBow = b; onMat = Me; yaw = ((Component)folk).transform.eulerAngles.y; }
                        if (!kowtowShot && b > 0.85f)
                        {
                            kowtowShot = true;
                            yield return ShotKneel($"kowtow_mat{i}", mp);
                        }
                    }
                    else if (!kneelShot && act != null && act.StartsWith("Kneel") && Time.time - t0 > 3.5f)
                    {
                        kneelShot = true;
                        yield return ShotKneel($"kneel_mat{i}", mp);
                    }
                }
                Assert.IsNotNull(got, $"拜垫{i} 跪拜没做完");
                Log($"拜垫{i} 跪拜：{Time.time - t0:F1} 秒，叩首最深 {deepestBow:F2} 时人在 {F(onMat)}（拜垫 {F(mp)}，垫面 {mp.y + 0.124f:F3}），朝向 {yaw:F0} 度");
                Assert.Greater(deepestBow, 0.85f, $"拜垫{i} 没有叩首");
                Assert.Less(Flat(onMat, mp), 0.12f, $"拜垫{i} 没走到拜垫上");
                Assert.AreEqual(mp.y + 0.124f, onMat.y, 0.04f, $"拜垫{i} 没跪在垫子面上");
                Assert.Less(Mathf.Abs(Mathf.DeltaAngle(yaw, 0)), 10f, $"拜垫{i} 没面朝佛像");
            }
            // 鞠躬、合掌也在拜垫上：从西边拜垫旁边的通道上点「鞠躬」
            Teleport(new Vector3(-2.9f, 0.74f, 18.65f), new Vector3(0, 0.74f, 21f));
            yield return new WaitForSeconds(0.5f);
            nr = LastNear();
            n0 = sent.Count;
            Cmd($"{{\"cmd\":\"act\",\"action\":\"bow\",\"mat\":{nr.mat}}}");
            yield return Wait("actionDone", 12f, n0);
            Log($"西边拜垫 near mat={nr.mat}，鞠躬后人在 {F(Me)}");
            Assert.AreEqual(3, nr.mat);
            Assert.Less(Flat(Me, new Vector3(-3.6f, 0, 18.5f)), 0.12f);
            yield return ShotFrom("west_mat", Me + new Vector3(1.6f, 1.3f, -1.6f), Me + Vector3.up * 0.6f, 50f);
            // ── 上香：走到中间供桌前（z 18.52）、举香拜三拜、站着不动俯身插进香炉、合掌 ──
            Teleport(new Vector3(0.6f, 0.74f, 17.4f), new Vector3(0, 0.74f, 21f));
            yield return new WaitForSeconds(0.5f);
            n0 = sent.Count;
            Cmd("{\"cmd\":\"offer\",\"kind\":\"incense\"}");
            t0 = Time.time;
            float nextShot = 0;
            int k = 0;
            bool sawCloseUp = false, held = false;
            got = null;
            // 手和香：举到脸前、拜到最低、插进灰里那一刻各从侧面拍一张近景；量两手和那把香、插的那一刻手离灰面多远
            Vector3 ashAt = Get<Vector3>(gd, "hallIncense");
            float plantAt = -1, deepest = 0, stickGap = 0;
            bool shotHold = false, shotBow = false, shotPlant = false, shotAfter = false;
            string plantLog = "";
            while (Time.time - t0 < 40f)
            {
                yield return Wait("offered", 0.02f, n0);
                if (got != null) break;
                bool cu = Get<bool>(vs, "InCloseUp");
                sawCloseUp |= cu;
                var sticksGo = Get<GameObject>(gd, "held");
                held |= sticksGo != null;
                string act = Get<string>(folk, "actNow");
                Vector3 sideEye = Me + new Vector3(1.45f, 1.0f, 0.35f), sideAt = Me + new Vector3(0, 0.85f, 0.3f);
                if (sticksGo != null && act == "Incense_Scrub")
                {
                    // 左手离香（右手心捏着香脚）多远：两只手一起拿着
                    stickGap = Mathf.Max(stickGap, Vector3.Distance(Palm(false), Palm(true)));
                    if (!shotHold && Get<bool>(folk, "ActionReady"))
                    {
                        shotHold = true;
                        yield return ShotFrom("incense_hand_hold", sideEye, sideAt + Vector3.up * 0.15f, 40f);
                    }
                    float b = Get<float>(folk, "bowPhase");
                    deepest = Mathf.Max(deepest, b);
                    if (!shotBow && b > 0.79f)
                    {
                        shotBow = true;
                        yield return ShotFrom("incense_hand_bow", sideEye, sideAt, 40f);
                    }
                }
                if (act == "Incense_Plant" && plantAt < 0) plantAt = Time.time;
                if (plantAt >= 0 && !shotPlant && Time.time - plantAt > 1.42f)
                {
                    shotPlant = true;
                    Vector3 mid = (Palm(true) + Palm(false)) * 0.5f;
                    Vector3 d = mid - ashAt;
                    plantLog = $"插香那一刻（{Time.time - plantAt:F2} 秒）两手心中点离灰面中心 水平 {new Vector2(d.x, d.z).magnitude:F3}（前后 {d.z:F3}），高出灰面 {d.y:F3}；" +
                        $"香脚（那把香的原点）离灰面 {(sticksGo != null ? (sticksGo.transform.position.y - ashAt.y).ToString("F3") : "已经松手")}，人在 {F(Me)}";
                    yield return ShotFrom("incense_hand_plant", sideEye, sideAt, 40f);
                    yield return ShotFrom("incense_hand_plant_front", ashAt + new Vector3(0.55f, 0.75f, 0.75f), ashAt + new Vector3(0, 0.05f, -0.2f), 44f);
                }
                if (plantAt >= 0 && !shotAfter && Time.time - plantAt > 3.3f)
                {
                    shotAfter = true;
                    yield return ShotFrom("incense_hand_after", sideEye, sideAt, 40f);
                }
                if (Time.time - t0 > nextShot) { Shot($"incense_{k++}{(cu ? "_close" : "")}"); nextShot += 1.4f; }
            }
            Log($"殿里上香的手：举香时两手心最远相距 {stickGap:F3} 米，拜到最深 {deepest:F2}；{plantLog}");
            Assert.IsNotNull(got, "上香没有回 offered");
            Assert.AreEqual("incense", got.kind);
            int sticks = Get<int>(off, "HallSticks");
            var planted = Get<List<GameObject>>(off, "hallSticks");
            Vector3 sp = planted.Count > 0 ? planted[planted.Count - 1].transform.position : Vector3.zero;
            Vector3 ash = Get<Vector3>(gd, "hallIncense");
            // 点着的：三支香头上都有火头（Ember）
            int embers = 0;
            if (planted.Count > 0) foreach (Transform st in planted[planted.Count - 1].transform) if (st.Find("Ember") != null) embers++;
            Log($"殿里上香：{Time.time - t0:F1} 秒，拿在手里={held}，特写={sawCloseUp}，香炉里 {sticks} 把（这一把 {embers} 支点着的），离灰面中心 {Vector3.Distance(sp, ash):F3} 米（高出灰面 {sp.y - ash.y:F3}），人回到 {F(Me)}");
            Assert.IsTrue(held && sawCloseUp);
            Assert.AreEqual(1, sticks);
            Assert.AreEqual(3, embers, "香没点着");
            Assert.Less(Vector3.Distance(sp, ash), 0.06f);
            Assert.Less(Flat(Me, Get<Vector3>(gd, "altarStand")), 0.15f);
            yield return new WaitForSeconds(1.0f);
            // 再上两次：一把把绕着灰面中心排开，不插进同一个地方
            for (int again = 0; again < 2; again++)
            {
                n0 = sent.Count;
                Cmd("{\"cmd\":\"offer\",\"kind\":\"incense\"}");
                yield return Wait("offered", 30f, n0);
                Assert.IsNotNull(got, "再上香没有回 offered");
                yield return new WaitForSeconds(0.5f);
            }
            planted = Get<List<GameObject>>(off, "hallSticks");
            float closest = 99;
            for (int i = 0; i < planted.Count; i++)
                for (int j = i + 1; j < planted.Count; j++) closest = Mathf.Min(closest, Flat(planted[i].transform.position, planted[j].transform.position));
            float farthest = 0;
            foreach (var g in planted) farthest = Mathf.Max(farthest, Flat(g.transform.position, ash));
            Log($"上了三炷香：{planted.Count} 把，两把之间最近 {closest:F3} 米，离灰面中心最远 {farthest:F3} 米");
            Assert.AreEqual(3, planted.Count);
            Assert.Greater(closest, 0.025f, "两把香插在一起了");
            Assert.Less(farthest, 0.05f);
            yield return ShotFrom("incense_planted", ash + new Vector3(0.5f, 0.35f, -0.7f), ash + Vector3.up * 0.1f, 40f);
            yield return ShotFrom("incense_planted_top", ash + new Vector3(0.05f, 0.45f, -0.25f), ash, 40f);
            // 插香那一下重新进场：香不会悬在半空（还算拿在手里，由 DropHeld 收掉）
            n0 = sent.Count;
            Cmd("{\"cmd\":\"offer\",\"kind\":\"incense\"}");
            t0 = Time.time;
            while (Time.time - t0 < 20f && !(Get<GameObject>(gd, "held") != null && Get<GameObject>(gd, "held").GetComponent(Type.GetType("Yuanjing.HandHold, Assembly-CSharp")) == null)) yield return null;
            var flying = Get<GameObject>(gd, "held");
            Assert.IsNotNull(flying, "没等到插香那一下");
            // 香从手里插进灰里只用 0.25 秒（手已经伸到灰面上方了）：在这一下当中重新进场
            yield return new WaitForSeconds(0.08f);
            Cmd("{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":0,\"name\":\"测试\"}");
            yield return null;
            yield return null;
            yield return Wait("view", 1f, n0, r => !r.locked);
            Log($"插香时重新进场：手里那把还在吗 {(flying != null)}，香炉里 {Get<int>(off, "HallSticks")} 把；视角放开了 {(got != null ? got.mode : "没有")}，现在 {Get<string>(vs, "Mode")}");
            Assert.IsTrue(flying == null, "插到一半的香留在半空了");
            Assert.AreEqual(3, Get<int>(off, "HallSticks"));
            // 在殿里重新进场：放开平视，换回进殿前的俯视（以前停在平视）
            Assert.IsNotNull(got, "在殿里重新进场没有放开视角");
            Assert.AreEqual("top", got.mode);
            Assert.AreEqual("top", Get<string>(vs, "Mode"));
            yield return new WaitForSeconds(2.5f);

            // ── 殿里的蒲团：走近才报，坐下、起身退到它前面的走道上 ──
            int H = 60 + 2;     // 西边里面那一列第 3 排（-4.55, 16.85），面朝东
            Vector3 hl = Call<Vector3>(gd, "SeatLane", H);
            Teleport(hl + new Vector3(0.5f, 0, 0.3f), hl + Vector3.left);
            yield return new WaitForSeconds(0.5f);
            int hn = LastNearSeat();
            n0 = sent.Count;
            Cmd($"{{\"cmd\":\"sit\",\"seat\":{hn}}}");
            yield return Wait("seated", 12f, n0);
            Log($"殿里的蒲团：near 报 {hn}，坐下 {(got != null ? got.seat : -1)}，原点离蒲团 {Flat(Me, Call<Vector3>(gd, "SeatGround", H)):F2} 米");
            Assert.AreEqual(H, hn);
            Assert.IsNotNull(got);
            yield return new WaitForSeconds(3f);
            Shot("hall_seated");
            yield return ShotFrom("hall_seated_side", Me + new Vector3(1.8f, 1.2f, -1.2f), Me + Vector3.up * 0.5f, 50f);
            n0 = sent.Count;
            Cmd("{\"cmd\":\"stand\"}");
            yield return Wait("arrived", 12f, n0);
            Assert.IsNotNull(got);
            Log($"殿里的蒲团起身：离它前面的走道 {Flat(Me, hl):F2} 米，arrived {got.spot}");
            Assert.Less(Flat(Me, hl), 0.3f);
            Assert.AreEqual("inhall", got.spot);
            // 站在殿中间的过道上（离蒲团都远）：「坐下」给远处的蒲团不坐，回 sitFailed
            Teleport(new Vector3(0, 0.74f, 16.5f), new Vector3(0, 0.74f, 21f));
            yield return new WaitForSeconds(0.4f);
            n0 = sent.Count;
            Cmd($"{{\"cmd\":\"sit\",\"seat\":{60 + 12}}}");
            yield return Wait("sitFailed", 1f, n0);
            Assert.IsNotNull(got, "远处的蒲团用「坐下」不该坐");

            // ── 走出殿（去大殿前）：经过门，出门就放开、换回进殿前的俯视 ──
            n0 = sent.Count;
            Cmd("{\"cmd\":\"goto\",\"spot\":\"hall\"}");
            float minAbsX = 99;
            t0 = Time.time;
            got = null;
            Vector3 last = Me;
            while (Time.time - t0 < 30f)
            {
                yield return Wait("arrived", 0.02f, n0, r => r.spot == "hall");
                if (got != null) break;
                // 穿过门那条线（z 14.3）时离中线多远
                if ((last.z - 14.3f) * (Me.z - 14.3f) <= 0) minAbsX = Mathf.Min(minAbsX, Mathf.Abs(Me.x));
                last = Me;
            }
            Assert.IsNotNull(got, "出殿没走到大殿前");
            yield return Wait("view", 0.1f, n0, r => !r.locked);
            Log($"走出殿：过门时离中线 {minAbsX:F2} 米，view {(got != null ? got.mode + " locked=" + got.locked : "没有")}，现在 {Get<string>(vs, "Mode")}");
            Assert.Less(minAbsX, 0.7f, "要从中间那扇门出去");
            Assert.IsNotNull(got);
            Assert.AreEqual("top", Get<string>(vs, "Mode"), "出殿换回进殿前的视角");
            yield return new WaitForSeconds(1f);
            Shot("out_top");

            // ── 走进殿（「进殿」按钮）：经过门，到中间拜垫后面 ──
            n0 = sent.Count;
            Cmd("{\"cmd\":\"goto\",\"spot\":\"inhall\"}");
            yield return Wait("arrived", 30f, n0, r => r.spot == "inhall");
            Assert.IsNotNull(got, "「进殿」没走进去");
            yield return Wait("view", 0.1f, n0, r => r.locked);
            Assert.IsNotNull(got);
            yield return new WaitForSeconds(1.2f);
            nr = LastNear();
            Log($"「进殿」：到了 {F(Me)}，锁平视；near mat={nr.mat} altar={nr.altar}");
            Shot("goto_inhall");
            Cmd("{\"cmd\":\"view\",\"kind\":\"first\"}");
            yield return new WaitForSeconds(1.2f);
            Shot("goto_inhall_first");

            // ── 殿里点画面：点地面、点供桌、点蒲团，人都留在殿里（以前「大殿」那一点看的是殿中间，殿里一点就被领出殿、走到台阶下面） ──
            System.Func<Vector3, bool> inHall = p => (bool)M(gd, "InHall", 1).Invoke(gd, new object[] { p });
            IEnumerator TapAt(string what, Vector3 world, string expectType)
            {
                Vector3 vp = cam.WorldToViewportPoint(world);
                Assert.IsTrue(vp.z > 0 && vp.x > 0.02f && vp.x < 0.98f && vp.y > 0.02f && vp.y < 0.98f, $"{what} 不在画面里（{vp}）");
                int m0 = sent.Count;
                Vector3 from = Me;
                Cmd($"{{\"cmd\":\"tap\",\"x\":{Inv(vp.x)},\"y\":{Inv(1 - vp.y)}}}");
                yield return Wait(expectType, 25f, m0);
                var reply = got;
                yield return new WaitForSeconds(0.6f);
                Log($"殿里点{what} {F(world)}（画面 {vp.x:F2},{vp.y:F2}）：从 {F(from)} 到 {F(Me)}；消息 {Types(m0)}");
                Assert.IsNotNull(reply, $"点{what} 没有回 {expectType}");
                for (int i = m0; i < sent.Count; i++)
                {
                    var r = JsonUtility.FromJson<Reply>(sent[i]);
                    Assert.IsFalse(r.type == "moving" && r.to == "hall", $"点{what} 被领出殿去了");
                    Assert.IsFalse(r.type == "view" && !r.locked, $"点{what} 放开了平视（出殿了）");
                }
                Assert.IsTrue(inHall(Me), $"点{what} 以后人不在殿里：{F(Me)}");
            }
            Cmd("{\"cmd\":\"view\",\"kind\":\"level\"}");
            Teleport(new Vector3(0.3f, 0.74f, 15.9f), new Vector3(0.3f, 0.74f, 21f));
            Run(Get<object>(gd, "cam"), "Snap", 0f);
            yield return new WaitForSeconds(1.5f);
            Vector3 floorTap = new Vector3(-0.9f, 0.72f, 16.9f);
            yield return TapAt("地面（西边拜垫南边）", floorTap, "arrived");
            Assert.AreEqual("inhall", got.spot);
            Assert.Less(Flat(Me, floorTap), 0.35f, "点的地面没走到");
            // 点供桌桌面：走到桌前站得下人的地方（不钻进桌子）
            Teleport(new Vector3(0.3f, 0.74f, 16.6f), new Vector3(0.3f, 0.74f, 21f));
            Run(Get<object>(gd, "cam"), "Snap", 0f);
            yield return new WaitForSeconds(1.5f);
            Vector3 tableTap = new Vector3(0.6f, 1.504f, 19.3f);
            yield return TapAt("供桌桌面", tableTap, "arrived");
            Assert.Less(Me.z, 18.8f, "走进供桌里去了");
            Assert.Less(Flat(Me, tableTap), 1.0f, "点供桌没走到桌前");
            // 第一人称点地面
            Teleport(new Vector3(0, 0.73f, 15.2f), new Vector3(0, 0.73f, 21f));
            Cmd("{\"cmd\":\"view\",\"kind\":\"first\"}");
            yield return new WaitForSeconds(0.3f);
            // 低头看地（第一人称进殿时是抬头看佛像的）
            Set(Get<object>(vs, "first"), "pitchTarget", 25f);
            yield return new WaitForSeconds(1.5f);
            yield return TapAt("地面（第一人称）", new Vector3(0.8f, 0.72f, 17.0f), "arrived");
            Cmd("{\"cmd\":\"view\",\"kind\":\"level\"}");
            yield return new WaitForSeconds(1.0f);
            // 点西边的空蒲团：走过去坐下（以前点偏一点点就被「大殿」那一点抢走）
            int tapSeat = 60 + 2;     // 西边里面那一列第 3 排（-4.55, 16.85）
            Vector3 zafu = Call<Vector3>(gd, "SeatGround", tapSeat);
            Teleport(new Vector3(-1.2f, 0.74f, 16.4f), new Vector3(-5f, 0.74f, 16.4f));
            Run(Get<object>(gd, "cam"), "Snap", 270f);
            yield return new WaitForSeconds(1.5f);
            // 点在蒲团偏 0.25 米的地方（不正好点中）
            yield return TapAt($"蒲团{tapSeat} 旁边", zafu + new Vector3(0.15f, 0.1f, 0.2f), "seated");
            Assert.AreEqual(tapSeat, got.seat, "坐到别的蒲团上了");
            Shot("tap_seated");
            n0 = sent.Count;
            Cmd("{\"cmd\":\"stand\"}");
            yield return Wait("arrived", 12f, n0);

            // ── 殿里规划路线要多久（以前每次 70–230 毫秒，主线程上卡一下） ──
            var pairs = new (Vector3, Vector3)[]
            {
                (new Vector3(0, 0.72f, 15.0f), new Vector3(-5.1f, 0.72f, 16.85f)),
                (new Vector3(0, 0.72f, 15.0f), new Vector3(5.1f, 0.72f, 17.75f)),
                (new Vector3(-5.1f, 0.72f, 15.05f), new Vector3(5.1f, 0.72f, 17.75f)),
                (new Vector3(0, 0.72f, 15.0f), new Vector3(0, 0.72f, 18.52f)),
                (new Vector3(-5.35f, 0.72f, 18.42f), new Vector3(5.8f, 0.72f, 18.45f)),
            };
            var times = new StringBuilder();
            double worst = 0;
            foreach (var (a, b) in pairs)
            {
                var sw = System.Diagnostics.Stopwatch.StartNew();
                var pp = Call<List<Vector3>>(gd, "HallPlan", a, b);
                sw.Stop();
                worst = Math.Max(worst, sw.Elapsed.TotalMilliseconds);
                times.Append($"{F(a)}→{F(b)} {sw.Elapsed.TotalMilliseconds:F2} 毫秒 {pp.Count} 段；");
            }
            Log($"殿里规划路线：{times}最慢 {worst:F2} 毫秒");
            Assert.Less(worst, 15.0, "殿里规划路线太慢（主线程上会卡）");
        }
        finally { End("hall"); }
    }
}
