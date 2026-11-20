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

/// 殿里的香客（PilgrimsHall.cs）：没联网（seed 9，本机人来人往）时快进跑一阵，
///   1 你在院子里：有人进殿、跪拜、静坐、出殿，殿里一般一到三位；
///   2 你站在殿里：香客照样进出，但不去中间那块拜垫；
///   3 抢位子：香客正走去的蒲团、拜垫被你挑了——你坐上去、跪上去，他让开；香客已经坐着、跪着的——不报给你，点了也换一个空的（或原地拜）；
///   4 拍几张：殿里平视，有人跪拜叩首、有人静坐。
/// 一直量：两人贴在一起（中心距不到 0.35 米）的次数、殿里的香客身子碰到殿里的东西（柱子、门扇、供桌……）的次数、
/// 给殿里香客的每一条路线（人按 0.2 米粗的胶囊）碰到东西的段数、你在殿里时香客在中间拜垫上、香客占了你的蒲团拜垫的次数。
/// 截图和 report.txt 在 unity/shots/hallcrowd/。
public class HallCrowdTest
{
    readonly StringBuilder report = new StringBuilder();
    readonly List<string> sent = new List<string>();
    readonly List<string> fails = new List<string>();
    GameObject bridge, player;
    Camera cam;
    RenderTexture rt;
    Texture2D tex;
    int shot;
    const string Dir = "../shots/hallcrowd";
    object gd, pil, folk, vs;
    Transform hallColliders;

    [Serializable]
    class Reply
    {
        public string type, spot, kind, reason, action, mode;
        public int seat = -999, mat = -999;
        public bool altar, locked, skipped;
    }

    void OnLog(string c, string st, LogType t)
    {
        if (c.StartsWith("SendToFlutter - ")) sent.Add(c.Substring(16));
    }

    void Cmd(string json) => bridge.SendMessage("OnMessage", json);

    void Log(string s)
    {
        report.AppendLine(s);
        Debug.Log("[yuanjing] 殿里香客 " + s);
    }

    void Check(bool ok, string what)
    {
        if (ok) return;
        fails.Add(what);
        Log("！不对：" + what);
    }

    static MethodInfo M(object o, string name, int args = -1)
    {
        foreach (var m in o.GetType().GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
            if (m.Name == name && (args < 0 || m.GetParameters().Length == args)) return m;
        return null;
    }
    static T Call<T>(object o, string name, params object[] a) => (T)M(o, name, a.Length).Invoke(o, a);
    static T Get<T>(object o, string name)
    {
        var f = o.GetType().GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
        if (f != null) return (T)f.GetValue(o);
        return (T)o.GetType().GetProperty(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance).GetValue(o);
    }
    static void Set(object o, string name, object v) => o.GetType().GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance).SetValue(o, v);

    static float Flat(Vector3 a, Vector3 b) => Vector2.Distance(new Vector2(a.x, a.z), new Vector2(b.x, b.z));
    static string F(Vector3 v) => v.ToString("F2");

    Vector3 Me => ((Component)folk).transform.position;
    Rect hallRect;
    float hallFloor;
    /// 同 GameDirector.InHall（每帧要算很多次，不走反射）
    bool InHall(Vector3 p) => hallRect.Contains(new Vector2(p.x, p.z)) && p.y > hallFloor - 0.22f;
    /// 院子里石凳上的座位数（殿里蒲团的序号从它起）；殿里蒲团的个数
    const int Od = 12;
    int HallSeatN => Get<Transform>(gd, "hallSeats").childCount;
    /// 殿里的一点（x、z），高度在金砖地上一点
    Vector3 HP(float x, float z) => new Vector3(x, hallFloor + 0.02f, z);
    /// 相对某个拜垫、蒲团的一点：水平偏 dx、dz，离地 dy
    Vector3 Rel(Vector3 o, float dx, float dy, float dz) => new Vector3(o.x + dx, hallFloor + dy, o.z + dz);
    Vector3 Mat(int m) => Get<Transform>(gd, "hallMats").GetChild(m).position;
    Vector3 Cushion(int k) => Get<Transform>(gd, "hallSeats").GetChild(k).position;
    Vector3 CushionStand(int k) => Call<Vector3>(gd, "SeatStand", Od + k);
    Vector3 CushionLane(int k) => Call<Vector3>(gd, "SeatLane", Od + k);
    string Slot(string id) => Call<string>(pil, "HallSlot", id);

    Component NpcFolk(string id)
    {
        var people = Get<IDictionary>(pil, "people");
        if (id == null || !people.Contains(id)) return null;
        return (Component)Get<object>(people[id], "folk");
    }

    /// Folk.All（测试程序集看不到 Yuanjing 的类型，用反射）
    static readonly FieldInfo FolkAll = Type.GetType("Yuanjing.Folk, Assembly-CSharp").GetField("All");
    static List<Behaviour> AllFolk()
    {
        var list = new List<Behaviour>();
        foreach (var o in (IList)FolkAll.GetValue(null)) if (o is Behaviour b && b != null && b.isActiveAndEnabled) list.Add(b);
        return list;
    }
    static bool Moving(Component f) => Get<bool>(f, "Moving");

    void Teleport(Vector3 p, float yaw)
    {
        var cc = player.GetComponent<CharacterController>();
        cc.enabled = false;
        player.transform.position = p;
        cc.enabled = true;
        ((Component)folk).transform.rotation = Quaternion.Euler(0, yaw, 0);
        M(folk, "FaceYaw").Invoke(folk, new object[] { yaw });
        Physics.SyncTransforms();
        M(Get<object>(gd, "cam"), "Snap").Invoke(Get<object>(gd, "cam"), new object[] { yaw });
    }

    IEnumerator Wait(string type, float secs, int since, Func<Reply, bool> ok, Action<Reply> got)
    {
        for (float t = 0; t < secs; t += Time.deltaTime)
        {
            for (int i = since; i < sent.Count; i++)
            {
                var r = JsonUtility.FromJson<Reply>(sent[i]);
                if (r.type == type && (ok == null || ok(r))) { got(r); yield break; }
            }
            yield return null;
            Sample();
        }
        got(null);
    }

    Reply LastNear()
    {
        for (int i = sent.Count - 1; i >= 0; i--)
        {
            var r = JsonUtility.FromJson<Reply>(sent[i]);
            if (r.type == "near") return r;
        }
        return new Reply { seat = -1, mat = -1 };
    }

    void Shot(string name)
    {
        cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
        RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0); tex.Apply(); RenderTexture.active = null;
        File.WriteAllBytes($"{Dir}/{shot++:00}_{name}.png", tex.EncodeToPNG());
        Log($"拍了 {shot - 1:00}_{name}：人在 {F(Me)}，镜头 {F(cam.transform.position)}，{Call<string>(pil, "HallSummary")}");
    }

    IEnumerator ShotFrom(string name, Vector3 eye, Vector3 focus, float fov = 46f)
    {
        yield return null;
        var p = cam.transform.position; var r = cam.transform.rotation; float f = cam.fieldOfView, n = cam.nearClipPlane;
        cam.transform.SetPositionAndRotation(eye, Quaternion.LookRotation(focus - eye));
        cam.fieldOfView = fov;
        cam.nearClipPlane = 0.05f;
        Shot(name);
        cam.transform.SetPositionAndRotation(p, r);
        cam.fieldOfView = f;
        cam.nearClipPlane = n;
    }

    // ── 一直量的 ──

    static readonly string[] HallFloors = { "Platform", "Floor", "Porch", "SideWalkW", "SideWalkE", "BackWalk", "Threshold", "Ceiling", "PorchCeiling" };
    bool HallSolid(Collider c) => c.transform.IsChildOf(hallColliders) && !c.name.StartsWith("Step") && Array.IndexOf(HallFloors, c.name) < 0;

    /// 香客不能进的隔断（同 Folk.Barriers 里院子、台阶、山门那几样）；连着在里面的帧数最多几帧
    static readonly string[] Barriers = { "StepCheek", "RailFront", "RailSide", "RailBack", "GatePost", "stele", "bench", "basin", "signpost", "plaque_rack" };
    readonly Dictionary<string, int> barrierRun = new Dictionary<string, int>();
    int barrierWorst;
    string barrierWho = "";
    int overlaps, bodyHits, centreMatWhileIn, tookMine, routeBad, routeLegs;
    float closest = 99f;
    string closestWho = "", bodyHitWho = "", routeHitWho = "", overlapWho = "";
    readonly HashSet<string> touching = new HashSet<string>();
    readonly HashSet<string> bodyTouching = new HashSet<string>();
    readonly float[] insideTime = new float[6];
    float playerInSince = -1;
    int maxInside;

    /// 每帧量一次
    void Sample()
    {
        float dt = Time.deltaTime;
        var all = AllFolk();
        var pos = new Vector3[all.Count];
        var near = new bool[all.Count];
        var inH = new bool[all.Count];
        for (int i = 0; i < all.Count; i++)
        {
            Vector3 p = pos[i] = all[i].transform.position;
            inH[i] = InHall(p);
            near[i] = inH[i] || (p.z > 15.2f && p.z < 16.7f && Mathf.Abs(p.x) < 10.5f && p.y > 0.9f);
        }
        // 殿里有几位香客
        int inside = 0;
        for (int i = 0; i < all.Count; i++) if (all[i] != (Component)folk && inH[i]) inside++;
        insideTime[Mathf.Min(inside, 5)] += dt;
        maxInside = Mathf.Max(maxInside, inside);
        // 贴在一起：殿里（和殿门口）的两人中心距不到 0.35 米
        var now = new HashSet<string>();
        for (int a = 0; a < all.Count; a++)
            for (int b = a + 1; b < all.Count; b++)
            {
                if (!near[a] && !near[b]) continue;
                Vector3 pa = pos[a], pb = pos[b];
                float d = Flat(pa, pb);
                if (d < closest) { closest = d; closestWho = $"{all[a].name}/{all[b].name} 在 {F(pa)}"; }
                if (d >= 0.35f) continue;
                string key = all[a].name + "|" + all[b].name;
                now.Add(key);
                if (!touching.Contains(key)) { overlaps++; if (overlapWho.Length < 600) overlapWho += $"{key} {d:F2} 米 在 {F(pa)}（{Time.time:F0}）；"; }
            }
        touching.Clear();
        touching.UnionWith(now);
        // 殿里的香客身子碰到殿里的东西（胶囊粗 0.12：脚下 0.3 到 1.4 米高）
        var nowHit = new HashSet<string>();
        for (int i = 0; i < all.Count; i++)
        {
            var f = all[i];
            if (f == (Component)folk || !inH[i]) continue;
            Vector3 p = pos[i];
            foreach (var c in Physics.OverlapCapsule(p + Vector3.up * 0.3f, p + Vector3.up * 1.4f, 0.12f, ~0, QueryTriggerInteraction.Ignore))
                if (HallSolid(c))
                {
                    string key = f.name + "|" + c.name;
                    nowHit.Add(key);
                    if (!bodyTouching.Contains(key)) { bodyHits++; if (bodyHitWho.Length < 500) bodyHitWho += $"{f.name} 在 {F(p)} 碰到 {c.name}；"; }
                }
        }
        bodyTouching.Clear();
        bodyTouching.UnionWith(nowHit);
        // 全岛的香客：身子（膝盖到胸口）进了隔断（台阶的垂带、栏杆、山门的门柱、石碑、长凳……）连着几帧
        var nowIn = new Dictionary<string, int>();
        for (int i = 0; i < all.Count; i++)
        {
            var f = all[i];
            if (f == (Component)folk) continue;
            Vector3 p = pos[i];
            foreach (var c in Physics.OverlapCapsule(p + Vector3.up * 0.45f, p + Vector3.up * 1.15f, 0.12f, ~(1 << 2), QueryTriggerInteraction.Ignore))
            {
                if (Array.IndexOf(Barriers, c.name) < 0) continue;
                string key = f.name + "|" + c.name;
                barrierRun.TryGetValue(key, out int run);
                nowIn[key] = run + 1;
                // 排查：连着三帧在里面的，记下他这时在做什么（走路的状态、最近挡过什么、姿势）
                if (run + 1 == 3) Log($"进了隔断 {key} 在 {F(p)}：{Get<object>(f, "pose")} {Call<string>(f, "DebugLoco")}");
                if (run + 1 > barrierWorst) { barrierWorst = run + 1; barrierWho = $"{key} 在 {F(p)}"; }
            }
        }
        barrierRun.Clear();
        foreach (var kv in nowIn) barrierRun[kv.Key] = kv.Value;
        // 你在殿里（12 秒以上，给正跪着的人起身走开的工夫）时，香客在中间那块拜垫上
        bool meIn = InHall(Me);
        if (meIn && playerInSince < 0) playerInSince = Time.time;
        if (!meIn) playerInSince = -1;
        int mySeat = -2;
        for (int i = 0; i < all.Count; i++)
        {
            if (!inH[i] || !all[i].name.StartsWith("Pilgrim_")) continue;
            string id = all[i].name.Substring(8), s = Slot(id);
            if (s.Length < 3 || s[s.Length - 1] != '+') continue;
            int idx = int.Parse(s.Substring(1, s.Length - 2));
            bool onMat = s[0] != 'm';
            if (onMat && idx == 1 && meIn && Time.time - playerInSince > 12f) { centreMatWhileIn++; Log($"！你在殿里时 {id} 在中间拜垫上（{s}）"); }
            // 你的蒲团、拜垫：香客不占
            if (mySeat == -2) mySeat = Get<int>(gd, "MySeat");
            if (!onMat && mySeat == Od + idx) { tookMine++; Log($"！{id} 坐在你的蒲团 {idx} 上"); }
            if (onMat && Flat(Me, Mat(idx)) < 0.2f && Get<bool>(gd, "PlayerResting")) { tookMine++; Log($"！{id} 和你在同一块拜垫 {idx} 上"); }
        }
    }

    /// 此刻殿里的蒲团、拜垫：香客坐着（跪着）的，GameDirector 不能当空的报；周围一米没人的，要当空的报
    void CheckFree(string when)
    {
        var npcs = new List<Behaviour>();
        foreach (var f in AllFolk()) if (f != (Component)folk && InHall(f.transform.position)) npcs.Add(f);
        bool Anyone(Vector3 c, float r)
        {
            if (Flat(Me, c) < r) return true;
            foreach (var f in npcs) if (Flat(f.transform.position, c) < r) return true;
            return false;
        }
        for (int i = 0; i < HallSeatN; i++)
        {
            bool sitting = npcs.Exists(f => Flat(f.transform.position, Cushion(i)) < 0.15f && !Moving(f));
            bool free = Call<bool>(gd, "SeatFree", Od + i);
            if (sitting) Check(!free, $"{when} 蒲团{i} 上坐着香客，SeatFree 却是 true");
            else if (!Anyone(CushionStand(i), 1.0f) && !Anyone(Cushion(i), 1.0f)) Check(free, $"{when} 蒲团{i} 周围没人，SeatFree 却是 false");
        }
        for (int m = 0; m < 5; m++)
        {
            bool on = npcs.Exists(f => Flat(f.transform.position, Mat(m)) < 0.15f && !Moving(f));
            bool taken = Call<bool>(pil, "HallMatTaken", m);
            if (on) Check(taken, $"{when} 拜垫{m} 上有香客，HallMatTaken 却是 false");
            else if (!Anyone(Mat(m), 1.0f)) Check(!taken, $"{when} 拜垫{m} 周围没人，HallMatTaken 却是 true");
        }
    }

    /// c 附近、离香客 npc 最远、站得下人的一点（抢位子时你从这里点）
    Vector3 AwayFrom(Component npc, params Vector3[] options)
    {
        Vector3 best = options[0];
        float bd = -1;
        foreach (var o in options)
        {
            float d = Flat(o, npc.transform.position);
            if (d > bd) { bd = d; best = o; }
        }
        return best;
    }

    /// 给殿里香客的路线：每一段按人（0.2 米粗的胶囊）一路量，碰到殿里的东西就记一段（殿外台阶以南的不量；
    /// 起点是他此刻站的地方，起步那 0.15 米不量——人本身贴着东西站的算在「身子碰到东西」里）
    void CheckRoutes()
    {
        var routes = Get<List<List<Vector3>>>(pil, "hallRoutes");
        foreach (var r in routes)
        {
            routeLegs++;
            for (int i = 1; i < r.Count; i++)
            {
                Vector3 a = r[i - 1], b = r[i];
                bool hit = false;
                for (float d = 0; d <= Flat(a, b) && !hit; d += 0.05f)
                {
                    Vector3 x = Vector3.MoveTowards(new Vector3(a.x, 0, a.z), new Vector3(b.x, 0, b.z), d);
                    if (x.z < 11f || Flat(x, r[0]) < 0.15f) continue;
                    x.y = InHall(new Vector3(x.x, hallFloor, x.z)) ? hallFloor : 1.08f;
                    foreach (var c in Physics.OverlapCapsule(x + Vector3.up * 0.3f, x + Vector3.up * 1.4f, 0.2f, ~0, QueryTriggerInteraction.Ignore))
                        if (HallSolid(c))
                        {
                            hit = true;
                            routeBad++;
                            if (routeHitWho.Length < 600) routeHitWho += $"{F(a)}→{F(b)} 在 {F(x)} 碰到 {c.name}；";
                            break;
                        }
                }
            }
        }
        routes.Clear();
    }

    /// 快进 secs 秒（游戏里的时间），每帧量
    IEnumerator Run(float secs)
    {
        float t0 = Time.time;
        while (Time.time - t0 < secs)
        {
            yield return null;
            Sample();
        }
        CheckRoutes();
    }

    string Hist()
    {
        float total = 0;
        foreach (var t in insideTime) total += t;
        var sb = new StringBuilder();
        for (int i = 0; i < insideTime.Length; i++) sb.Append($"{i}{(i == 5 ? "+" : "")} 位 {100f * insideTime[i] / Mathf.Max(total, 1e-3f):F0}%  ");
        return sb.ToString();
    }

    int CountEvents(List<string> ev, string word)
    {
        int n = 0;
        foreach (var e in ev) if (e.Contains(" " + word + " ")) n++;
        return n;
    }

    /// 等香客 id 的状态变成 want 开头（比如 "m2+"），最多 secs 秒
    IEnumerator WaitSlot(string id, string want, float secs)
    {
        for (float t = 0; t < secs && !Slot(id).StartsWith(want); t += Time.deltaTime) { yield return null; Sample(); }
    }

    /// 只留测试叫进殿的人：不再随机请人进殿，已经在殿里的做完手上这一下就出去，等他们都出来
    IEnumerator OnlySent(float secs)
    {
        M(pil, "HallCrowd").Invoke(pil, new object[] { false });
        float t0 = Time.time;
        while (Get<int>(pil, "HallVisitors") > 0 && Time.time - t0 < secs) { yield return null; Sample(); }
        Set(pil, "hallQuiet", false);
        Set(pil, "hallWantFixed", 0);
        Log($"殿里清空：{Time.time - t0:F0} 秒，{Call<string>(pil, "HallSummary")}");
    }

    /// 同一个测试类的几个测试共用一个实例（NUnit）：每个测试开头把量的东西清零
    void ResetCounters()
    {
        fails.Clear();
        report.Clear();
        sent.Clear();
        overlaps = bodyHits = centreMatWhileIn = tookMine = routeBad = routeLegs = 0;
        closest = 99f;
        closestWho = bodyHitWho = routeHitWho = overlapWho = "";
        touching.Clear();
        bodyTouching.Clear();
        barrierRun.Clear();
        barrierWorst = 0;
        barrierWho = "";
        Array.Clear(insideTime, 0, insideTime.Length);
        playerInSince = -1;
        maxInside = 0;
        shot = 0;
    }

    /// Pilgrims.CrowdOverride（静态）：本机人数，0 是照钟点
    static void CrowdOverride(int n) => Type.GetType("Yuanjing.Pilgrims, Assembly-CSharp").GetField("CrowdOverride").SetValue(null, n);

    /// 你站在殿里门里偏东（过道和东边金柱之间，(0.9, 16.1)）、偏西、过道中间不动，请香客去对面、斜对面的拜垫：
    /// 路线要绕开你（离你 0.4 米以上），不能走到你跟前挤住、原地踏步、「走不到」（复核时见过一位挤了 27 秒，三次重新找路都是同一条穿过你的路）
    [UnityTest, Timeout(900000)]
    public IEnumerator PlayerInDoorway()
    {
        ResetCounters();
        Directory.CreateDirectory(Dir);
        Application.logMessageReceived += OnLog;
        try
        {
            CrowdOverride(27);
            SceneManager.LoadScene("Islet");
            for (int i = 0; i < 10; i++) yield return null;
            bridge = GameObject.Find("Bridge");
            Cmd("{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"测试\"}");
            yield return new WaitForSeconds(3f);
            player = GameObject.Find("Player");
            cam = Camera.main;
            gd = Type.GetType("Yuanjing.GameDirector, Assembly-CSharp").GetProperty("Instance").GetValue(null);
            pil = Get<object>(gd, "pilgrims");
            folk = Get<object>(gd, "player");
            hallColliders = GameObject.Find("World/Structure/hall/Colliders").transform;
            hallRect = Get<Rect>(gd, "hallRect");
            hallFloor = Get<float>(gd, "hallFloor");
            var events = Get<List<string>>(pil, "hallEvents");
            yield return OnlySent(60f);
            var cases = new (Vector3 me, int mat)[]
            {
                // 中门里一两米（门里那一点 z 17.34）：香客从中门进来正要经过的地方
                (HP(0.9f, 18.45f), 4), (HP(-0.9f, 18.45f), 3), (HP(0.9f, 18.45f), 0),
                (HP(0.2f, 17.95f), 4), (HP(-0.5f, 18.95f), 2),
            };
            Time.timeScale = 2f;
            foreach (var (me, mat) in cases)
            {
                Teleport(me, 0f);
                yield return new WaitForSeconds(0.5f);
                string id = Call<string>(pil, "HallSend", "k", mat, 0f);
                Assert.IsNotNull(id, "没有能请进殿的香客");
                var nf = NpcFolk(id);
                float t0 = Time.time, near = 99f;
                Vector3 nearAt = Vector3.zero;
                while (Time.time - t0 < 120f && !Slot(id).EndsWith("+") && Slot(id) != "")
                {
                    yield return null;
                    Sample();
                    if (nf == null) break;
                    float d = Flat(nf.transform.position, Me);
                    if (InHall(nf.transform.position) && d < near) { near = d; nearAt = nf.transform.position; }
                }
                int stuck = events.FindAll(e => e.Contains($"走不到 {id} ")).Count, replan = events.FindAll(e => e.Contains($"重新找路 {id} ")).Count;
                Log($"门里站人 你在 {F(me)}，请 {id} 去拜垫{mat}：{Slot(id)}，用了 {Time.time - t0:F0} 秒，离你最近 {near:F2} 米（在 {F(nearAt)}），重新找路 {replan} 次，走不到 {stuck} 次");
                Check(Slot(id) == $"k{mat}+", $"你在 {F(me)}：{id} 没跪上拜垫{mat}（{Slot(id)}）");
                Check(near >= 0.4f, $"你在 {F(me)}：{id} 从你身边 {near:F2} 米擦过去");
                Check(stuck == 0, $"你在 {F(me)}：{id} 走不到");
                foreach (var e in events) if (e.Contains($" {id} ") && (e.Contains("路线") || e.Contains("重新找路") || e.Contains("走不到"))) report.AppendLine("    " + (e.Length > 500 ? e.Substring(0, 500) + "…" : e));
                yield return OnlySent(90f);
            }
            Time.timeScale = 1f;
            Log($"门里站人：贴在一起 {overlaps} 次 {overlapWho}；身子碰到东西 {bodyHits} 次 {bodyHitWho}；对不上的 {fails.Count} 处：{string.Join("；", fails)}");
            Check(overlaps == 0, $"贴在一起 {overlaps} 次");
            File.WriteAllText($"{Dir}/report_doorway.txt", report.ToString());
            Assert.IsEmpty(fails, string.Join("；", fails));
        }
        finally
        {
            CrowdOverride(0);
            Time.timeScale = 1f;
            Application.logMessageReceived -= OnLog;
            File.WriteAllText($"{Dir}/report_doorway.txt", report.ToString());
        }
    }

    [UnityTest, Timeout(1800000)]
    public IEnumerator HallVisitors()
    {
        ResetCounters();
        Directory.CreateDirectory(Dir);
        foreach (var f in Directory.GetFiles(Dir, "*.png")) File.Delete(f);
        Application.logMessageReceived += OnLog;
        try
        {
            // 本机的人数不跟着钟点走（夜里只有十位左右，请进殿的人行程上剩的时间短，常常还没跪下就走了）：按中午的人数
            CrowdOverride(27);
            SceneManager.LoadScene("Islet");
            for (int i = 0; i < 10; i++) yield return null;
            bridge = GameObject.Find("Bridge");
            Cmd("{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"测试\"}");
            yield return new WaitForSeconds(3f);
            player = GameObject.Find("Player");
            cam = Camera.main;
            rt = new RenderTexture(540, 960, 24) { antiAliasing = 4 };
            tex = new Texture2D(540, 960, TextureFormat.RGB24, false);
            gd = Type.GetType("Yuanjing.GameDirector, Assembly-CSharp").GetProperty("Instance").GetValue(null);
            pil = Get<object>(gd, "pilgrims");
            folk = Get<object>(gd, "player");
            vs = cam.GetComponent(Type.GetType("Yuanjing.ViewSwitcher, Assembly-CSharp"));
            Assert.IsTrue(Get<bool>(gd, "hallOpen"), "大殿没开");
            hallColliders = GameObject.Find("World/Structure/hall/Colliders").transform;
            hallRect = Get<Rect>(gd, "hallRect");
            hallFloor = Get<float>(gd, "hallFloor");
            var events = Get<List<string>>(pil, "hallEvents");
            Log($"进岛：{Get<IDictionary>(pil, "people").Count} 位，{Call<string>(pil, "HallSummary")}");

            // ── 1 你在院子里（香炉南边），快进 7 分钟 ──
            Time.timeScale = 6f;
            yield return Run(420f);
            // 殿里想要几位是随机的（0–3 位，一两分钟换一次；一进场有三成的时候殿里没人静坐），7 分钟里只来了一两位的时候也有：
            // 再看 3 分钟（10 分钟里至少 3 位）
            if (CountEvents(events, "进殿") < 3)
            {
                Log($"1 头 7 分钟只有 {CountEvents(events, "进殿")} 位进殿（殿里想要的人数是随机的），再看 3 分钟");
                yield return Run(180f);
            }
            Time.timeScale = 1f;
            int in1 = CountEvents(events, "进殿"), kneel1 = CountEvents(events, "跪拜"), sit1 = CountEvents(events, "静坐"), out1 = CountEvents(events, "出殿");
            int bow1 = CountEvents(events, "鞠躬") + CountEvents(events, "合掌");
            Log($"1 你在院子里 7 分钟：进殿 {in1} 次、跪拜 {kneel1}、鞠躬合掌 {bow1}、静坐 {sit1}、出殿 {out1}；殿里人数（按时间）{Hist()}最多 {maxInside} 位");
            Check(in1 >= 3, $"7（10）分钟只有 {in1} 位进殿");
            // 殿大了：从院子走到拜垫要四五十秒（老殿十几秒），7 分钟里拜的次数少一些
            Check(kneel1 + bow1 >= 1, $"7 分钟只拜了 {kneel1 + bow1} 次");
            Check(sit1 >= 1, "7 分钟没人在殿里静坐");
            Check(out1 >= 2, $"7 分钟只有 {out1} 位出殿");
            Check(maxInside <= 6, $"殿里一下子有 {maxInside} 位");
            Shot("court_view");

            // ── 2 你站在殿里过道东边（面朝佛像），快进 6 分钟：照样有人进出，但不去中间那块拜垫 ──
            Teleport(HP(0.9f, 26.0f), 0f);
            yield return new WaitForSeconds(1f);
            Time.timeScale = 6f;
            for (int k = 0; k < 18; k++)
            {
                yield return Run(20f);
                // 每一个殿里的蒲团、拜垫：香客坐着（跪着）的，「坐下」「跪拜」都不报；没人的照常能坐
                CheckFree($"2 第 {k} 次");
            }
            Time.timeScale = 1f;
            int in2 = CountEvents(events, "进殿") - in1, kneel2 = CountEvents(events, "跪拜") - kneel1, sit2 = CountEvents(events, "静坐") - sit1;
            Log($"2 你在殿里 6 分钟：进殿 {in2} 次、跪拜 {kneel2}、静坐 {sit2}；殿里人数（按时间，两段合计，含你）{Hist()}；你在殿里时香客上中间拜垫 {centreMatWhileIn} 次");
            Check(in2 >= 2, $"你在殿里 6 分钟只有 {in2} 位进殿");
            Shot("in_hall_level");

            // ── 3 抢位子 ──
            yield return OnlySent(90f);
            // 3a 香客正走去西边内列第二个蒲团（1 号），走到离它 1–1.6 米时你在旁边点「坐下」（指定这一个）：你坐上，他让开
            {
                Teleport(HP(-0.9f, 27.8f), 270f);
                yield return new WaitForSeconds(0.5f);
                string id = Call<string>(pil, "HallSend", "m", 1, 60f);
                Assert.IsNotNull(id, "没有能请进殿的香客");
                var nf = NpcFolk(id);
                Vector3 st = CushionStand(1);
                float t0 = Time.time;
                while (Time.time - t0 < 100f && !(Slot(id) == "m1" && Flat(nf.transform.position, st) < 1.6f && Flat(nf.transform.position, st) > 1.0f)) { yield return null; Sample(); }
                Log($"3a 香客 {id} 走去蒲团1：{Slot(id)}，离站的地方 {Flat(nf.transform.position, st):F2} 米");
                Check(Slot(id) == "m1", $"3a 香客没在去蒲团1 的路上（{Slot(id)}）");
                // 离蒲团1 站的地方 0.8–1 米（站在 0.7 米以内香客就当你要坐、先让了，这里要的是两人同时去）、离香客最远的一点
                Vector3 me = AwayFrom(nf, Rel(st, 0.9f, 0.02f, 0.25f), Rel(st, -0.9f, 0.02f, 0.25f), Rel(st, 0.6f, 0.02f, 0.7f), Rel(st, -0.6f, 0.02f, 0.7f));
                Log($"3a 你从 {F(me)} 点坐下（离香客 {Flat(me, nf.transform.position):F2} 米）");
                Teleport(me, 270f);
                int n0 = sent.Count;
                Cmd("{\"cmd\":\"sit\",\"seat\":13}");
                Reply sat = null;
                yield return Wait("seated", 15f, n0, null, r => sat = r);
                yield return Run(4f);
                Log($"3a 你点坐下 13：{(sat != null ? $"坐在 {sat.seat}" : "没坐下")}，香客 {id} 现在 {Slot(id)}，在 {F(nf.transform.position)}，离蒲团1 {Flat(nf.transform.position, Cushion(1)):F2} 米");
                Check(sat != null && sat.seat == Od + 1, $"3a 你没坐上蒲团1（{sat?.seat}）");
                Check(Slot(id) != "m1" && Slot(id) != "m1+", $"3a 香客还占着蒲团1（{Slot(id)}）");
                Check(Flat(nf.transform.position, Cushion(1)) > 0.6f, "3a 香客还在蒲团1 跟前");
                Check(events.Exists(e => e.Contains($"让开蒲团 {id}")), "3a 香客没让开");
                yield return ShotFrom("race_seat", Rel(Cushion(1), 2.0f, 0.9f, -1.6f), Rel(Cushion(1), 0f, 0.1f, 0f), 50f);
                n0 = sent.Count;
                Cmd("{\"cmd\":\"stand\"}");
                yield return Wait("arrived", 12f, n0, null, r => { });
                yield return OnlySent(90f);
            }
            // 3b 香客正走去 0 号拜垫（中间西边那块），离它 1–1.8 米时你点「跪拜」（这一块）：你跪上去，他让开
            {
                Teleport(Rel(Mat(0), -0.75f, 0.02f, -0.6f), 0f);
                yield return new WaitForSeconds(0.5f);
                string id = Call<string>(pil, "HallSend", "k", 0, 0f);
                Assert.IsNotNull(id, "没有能请进殿的香客");
                var nf = NpcFolk(id);
                Vector3 mp = Mat(0);
                float t0 = Time.time;
                while (Time.time - t0 < 100f && !(Slot(id) == "k0" && Flat(nf.transform.position, mp) < 1.8f && Flat(nf.transform.position, mp) > 1.0f)) { yield return null; Sample(); }
                Log($"3b 香客 {id} 走去拜垫0：{Slot(id)}，离拜垫 {Flat(nf.transform.position, mp):F2} 米");
                Check(Slot(id) == "k0", $"3b 香客没在去拜垫0 的路上（{Slot(id)}）");
                int n0 = sent.Count;
                Cmd("{\"cmd\":\"act\",\"action\":\"kneel\",\"mat\":0}");
                Reply done = null;
                Vector3 deepest = Vector3.zero;
                float bow = 0;
                bool shot3b = false;
                for (float t = 0; t < 40f && done == null; t += Time.deltaTime)
                {
                    yield return null;
                    Sample();
                    for (int i = n0; i < sent.Count && done == null; i++) { var r = JsonUtility.FromJson<Reply>(sent[i]); if (r.type == "actionDone") done = r; }
                    if (Get<string>(folk, "actNow") == "Kowtow_Scrub" && Get<float>(folk, "bowPhase") > bow) { bow = Get<float>(folk, "bowPhase"); deepest = Me; }
                    if (!shot3b && bow > 0.85f) { shot3b = true; yield return ShotFrom("race_mat", Rel(Mat(0), -1.2f, 0.8f, -1.5f), Rel(Mat(0), 0.4f, 0f, 0.1f), 50f); }
                }
                Log($"3b 你点跪拜 0：{(done != null ? "做完了" : "没做完")}，叩首最深 {bow:F2} 时你在 {F(deepest)}（拜垫 {F(mp)}），香客 {id} 现在 {Slot(id)}，在 {F(nf.transform.position)}");
                Check(done != null && bow > 0.85f, "3b 你没跪拜完");
                Check(Flat(deepest, mp) < 0.12f, $"3b 你没跪在拜垫0 上（差 {Flat(deepest, mp):F2} 米）");
                Check(Flat(nf.transform.position, mp) > 0.6f, "3b 香客还在拜垫0 上");
                Check(events.Exists(e => e.Contains($"让开拜垫 {id}")), "3b 香客没让开");
                yield return OnlySent(90f);
            }
            // 3c 香客已经坐在西边内列第三个蒲团（2 号）上：你站到它前面的走道上，「坐下」不报它；点坐下（指定它）坐到旁边空的那个
            {
                Teleport(HP(-0.9f, 27.8f), 270f);
                string id = Call<string>(pil, "HallSend", "m", 2, 120f);
                Assert.IsNotNull(id);
                yield return WaitSlot(id, "m2+", 100f);
                yield return Run(5f);
                Log($"3c 香客 {id}：{Slot(id)}");
                Check(Slot(id) == "m2+", $"3c 香客没坐上蒲团2（{Slot(id)}）");
                Vector3 lane = CushionLane(2);
                // 蒲团左右隔 1.5 米（老殿 0.9 米）：站在它和旁边 1 号蒲团的走道之间、偏它这边一点，1.2 米以内够得着的空蒲团只有旁边那个
                Vector3 lane1 = CushionLane(1);
                Teleport(HP(Mathf.Lerp(lane.x, lane1.x, 0.42f), lane.z), 270f);
                yield return Run(0.8f);
                var nr = LastNear();
                Log($"3c 站在蒲团2 前的走道上：near.seat {nr.seat}");
                CheckFree("3c");
                Check(nr.seat != Od + 2 && nr.seat >= Od, $"3c near 报的蒲团不对（{nr.seat}）");
                int n0 = sent.Count;
                Cmd("{\"cmd\":\"sit\",\"seat\":14}");
                Reply sat = null;
                yield return Wait("seated", 15f, n0, null, r => sat = r);
                yield return Run(3f);
                Log($"3c 点坐下 14：{(sat != null ? $"坐在 {sat.seat}" : "没坐下")}，你在 {F(Me)}，香客还是 {Slot(id)}");
                Check(sat != null && sat.seat >= Od && sat.seat != Od + 2, $"3c 应该坐到旁边空的蒲团（{sat?.seat}）");
                yield return ShotFrom("occupied_seat", Rel(Cushion(2), 2.2f, 0.85f, 1.3f), Rel(Cushion(2), -0.3f, 0.05f, 0f), 50f);
                n0 = sent.Count;
                Cmd("{\"cmd\":\"stand\"}");
                yield return Wait("arrived", 12f, n0, null, r => { });
                yield return OnlySent(150f);
            }
            // 3d 香客已经跪在西边那块拜垫（3 号）上：你站在它旁边，near 不报它；点鞠躬（指定它）就原地拜，不走上去
            {
                Teleport(HP(-3.0f, 27.8f), 0f);
                string id = Call<string>(pil, "HallSend", "k", 3, 0f);
                Assert.IsNotNull(id);
                yield return WaitSlot(id, "k3+", 100f);
                Check(Slot(id) == "k3+", $"3d 香客没跪上拜垫3（{Slot(id)}）");
                Teleport(Rel(Mat(3), 0.7f, 0.02f, 0.15f), 0f);
                yield return Run(0.8f);
                var nr = LastNear();
                Log($"3d 站在拜垫3 旁边：near.mat {nr.mat}");
                CheckFree("3d");
                Check(nr.mat != 3, $"3d near 还报着香客跪着的拜垫3");
                int n0 = sent.Count;
                Cmd("{\"cmd\":\"act\",\"action\":\"bow\",\"mat\":3}");
                Reply done = null;
                float far = 99;
                for (float t = 0; t < 30f && done == null; t += Time.deltaTime)
                {
                    yield return null;
                    Sample();
                    far = Mathf.Min(far, Flat(Me, Mat(3)));
                    for (int i = n0; i < sent.Count && done == null; i++) { var r = JsonUtility.FromJson<Reply>(sent[i]); if (r.type == "actionDone") done = r; }
                }
                Log($"3d 点鞠躬 3：{(done != null ? "做完了" : "没做完")}，你离拜垫3 最近 {far:F2} 米");
                Check(done != null, "3d 鞠躬没做完");
                Check(far > 0.5f, "3d 你走到香客跪着的拜垫上去了");
                yield return OnlySent(90f);
            }

            // ── 4 拍：你站在过道里（中间拜垫后面偏西），中间两边的拜垫上各有人跪拜叩首、西边拜垫上有人跪着、两边蒲团上有人静坐 ──
            {
                Teleport(HP(-0.2f, 27.2f), 0f);
                // 一位一位请（平常进殿的人前后隔 10–28 秒，这里隔 7 秒）
                string a = Call<string>(pil, "HallSend", "k", 0, 0f);
                yield return Run(7f);
                string e = Call<string>(pil, "HallSend", "k", 2, 0f);
                yield return Run(7f);
                string b = Call<string>(pil, "HallSend", "m", 10, 150f);
                yield return Run(7f);
                string c = Call<string>(pil, "HallSend", "m", 2, 150f);
                yield return Run(7f);
                string d = Call<string>(pil, "HallSend", "k", 3, 0f);
                Log($"4 请了 {a}（拜垫0）、{e}（拜垫2）、{b}（蒲团9）、{c}（蒲团2）、{d}（拜垫3）");
                var fa = NpcFolk(a);
                var fe = NpcFolk(e);
                float t0 = Time.time;
                bool s1 = false, s2 = false, s3 = false, s4 = false, s5 = false;
                while (Time.time - t0 < 160f && !(s1 && s2 && s3 && s4 && s5))
                {
                    yield return null;
                    Sample();
                    bool kowA = fa != null && Get<string>(fa, "actNow") == "Kowtow_Scrub" && Get<float>(fa, "bowPhase") > 0.8f;
                    bool kneelE = fe != null && Slot(e) == "k2+" && Get<string>(fe, "actNow") != null && Get<string>(fe, "actNow").StartsWith("K");
                    bool sitC = Slot(c) == "m2+" && Get<string>(NpcFolk(c), "actNow") == "Sit_Loop";
                    // 镜头跟前没人走过（走进来的人从镜头前面过时整个画面被他挡住）
                    bool clear = !AllFolk().Exists(x => x != (Component)folk && Moving(x) && Flat(x.transform.position, Me) < 3f);
                    if (!s1 && kowA && kneelE && clear) { s1 = true; Shot("level_kowtow_both_sides"); }
                    if (s1 && !s5) { s5 = true; yield return ShotFrom("door_wide", new Vector3(2.6f, 3.4f, 21.6f), new Vector3(-0.7f, 1.3f, 29.2f), 58f); }
                    if (!s2 && kowA) { s2 = true; yield return ShotFrom("kowtow_side", fa.transform.position + new Vector3(-1.5f, 1.15f, -1.2f), fa.transform.position + new Vector3(0, 0.45f, 0.35f), 46f); }
                    if (!s3 && sitC) { s3 = true; yield return ShotFrom("meditate_west", Cushion(2) + new Vector3(1.7f, 1.05f, -0.9f), Cushion(2) + new Vector3(0, 0.55f, 0), 46f); }
                    if (!s4 && Slot(d) == "k3+" && Get<string>(NpcFolk(d), "actNow") == "Kneel_Loop") { s4 = true; yield return ShotFrom("kneel_west_mat", Mat(3) + new Vector3(-1.3f, 1.2f, -1.6f), Mat(3) + new Vector3(0, 0.55f, 0.4f), 46f); }
                }
                // 中间两边那两位一前一后、错开了（请到的人有的在殿前、有的在院子另一头：院子里的路绕着香炉那一圈走，
                // 远的要多走二三十秒，走到时另一位已经叩完走了）：再同时请两位，只等这一张，
                // 这回一位在叩首、另一位在殿里（刚走到、跪着、或者刚起身往外走）就拍
                if (!s1)
                {
                    Log("4 中间两边的两位没同时跪着（错开了），再请两位");
                    bool InHallNow(Component f) => f != null && hallRect.Contains(new Vector2(f.transform.position.x, f.transform.position.z));
                    bool Kow(Component f) => f != null && Get<string>(f, "actNow") == "Kowtow_Scrub" && Get<float>(f, "bowPhase") > 0.8f;
                    a = Call<string>(pil, "HallSend", "k", 0, 0f);
                    e = Call<string>(pil, "HallSend", "k", 2, 0f);
                    fa = NpcFolk(a);
                    fe = NpcFolk(e);
                    t0 = Time.time;
                    while (Time.time - t0 < 100f && !(s1 && s5))
                    {
                        yield return null;
                        Sample();
                        bool both = Kow(fa) && InHallNow(fe) || Kow(fe) && InHallNow(fa);
                        // 那两位自己走在拜垫那边（镜头前面隔着你），不算挡镜头
                        bool clear = !AllFolk().Exists(x => x != (Component)folk && x != fa && x != fe && Moving(x) && Flat(x.transform.position, Me) < 3f);
                        if (!s1 && both && clear) { s1 = true; Shot("level_kowtow_both_sides"); }
                        if (s1 && !s5) { s5 = true; yield return ShotFrom("door_wide", new Vector3(2.6f, 3.4f, 21.6f), new Vector3(-0.7f, 1.3f, 29.2f), 58f); }
                    }
                }
                Check(s1 && s2 && s3 && s4 && s5, $"4 没拍全：{s1} {s2} {s3} {s4} {s5}");
                // 你坐到西边内列第二个蒲团（1 号）上：殿里静坐时的平视，对面东边蒲团上有人静坐、供桌前有人在拜
                for (float t = 0; t < 60f && Slot(b) != "m10+"; t += Time.deltaTime) { yield return null; Sample(); }
                int n0 = sent.Count;
                Teleport(CushionLane(1) + new Vector3(0.25f, 0.02f, -0.2f), 270f);
                Cmd("{\"cmd\":\"sit\",\"seat\":13}");
                Reply sat = null;
                yield return Wait("seated", 15f, n0, null, r => sat = r);
                yield return Run(3.5f);
                Shot("seated_west_view");
                Check(sat != null && sat.seat == Od + 1, $"4 没坐上蒲团1（{sat?.seat}）");
                // 夜里
                Cmd("{\"cmd\":\"sky\",\"time\":\"night\",\"weather\":\"clear\",\"instant\":true}");
                yield return Run(2f);
                Shot("seated_west_view_night");
                Cmd("{\"cmd\":\"sky\",\"time\":\"day\",\"weather\":\"clear\",\"instant\":true}");
                n0 = sent.Count;
                Cmd("{\"cmd\":\"stand\"}");
                yield return Wait("arrived", 12f, n0, null, r => { });
                // 都出殿：拜垫、蒲团全放掉
                yield return OnlySent(200f);
                int held = 0;
                for (int i = 0; i < HallSeatN; i++) if (Call<bool>(pil, "HallSeatTaken", i)) held++;
                for (int i = 0; i < 5; i++) if (Call<bool>(pil, "HallMatTaken", i)) held++;
                Log($"4 都出殿以后：殿里那一段 {Get<int>(pil, "HallVisitors")} 位，还占着的拜垫蒲团 {held} 个");
                Check(Get<int>(pil, "HallVisitors") == 0 && held == 0, "4 出殿以后还占着东西");
            }
            CheckRoutes();

            Log($"一共：进殿 {CountEvents(events, "进殿")}、跪拜 {CountEvents(events, "跪拜")}、鞠躬 {CountEvents(events, "鞠躬")}、合掌 {CountEvents(events, "合掌")}、静坐 {CountEvents(events, "静坐")}、" +
                $"让开 {CountEvents(events, "让开蒲团") + CountEvents(events, "让开拜垫")}、出殿 {CountEvents(events, "出殿")}、被叫走 {CountEvents(events, "被叫走")}、走不到 {CountEvents(events, "走不到")}");
            Log($"贴在一起 {overlaps} 次 {overlapWho}；两人最近 {closest:F2} 米（{closestWho}）");
            Log($"殿里香客身子碰到东西 {bodyHits} 次 {bodyHitWho}");
            Log($"香客身子进了隔断（垂带、栏杆、门柱、石碑、长凳……）最长连着 {barrierWorst} 帧 {barrierWho}");
            Log($"路线 {routeLegs} 条，碰到东西 {routeBad} 段 {routeHitWho}");
            Log($"你在殿里时香客上中间拜垫 {centreMatWhileIn} 次；香客占了你的蒲团、拜垫 {tookMine} 次");
            Check(overlaps == 0, $"贴在一起 {overlaps} 次");
            Check(routeBad == 0, $"路线碰到东西 {routeBad} 段");
            Check(bodyHits == 0, $"身子碰到东西 {bodyHits} 次");
            Check(barrierWorst <= 5, $"香客身子进了隔断连着 {barrierWorst} 帧（{barrierWho}）");
            Check(centreMatWhileIn == 0, "你在殿里时香客上了中间拜垫");
            Check(tookMine == 0, "香客占了你的蒲团、拜垫");
            Check(CountEvents(events, "走不到") == 0, "有香客走不到");
            Log($"重新找路 {events.FindAll(x => x.Contains("重新找路")).Count} 次，院子里挤得走不动、不进殿了 {CountEvents(events, "不进殿了")} 次");
            var tail = new StringBuilder();
            foreach (var e in events) tail.AppendLine(e);
            File.WriteAllText($"{Dir}/events.txt", tail.ToString());
            Log($"对不上的 {fails.Count} 处：{string.Join("；", fails)}");
            File.WriteAllText($"{Dir}/report.txt", report.ToString());
            Assert.IsEmpty(fails, string.Join("；", fails));
        }
        finally
        {
            CrowdOverride(0);
            Time.timeScale = 1f;
            Application.logMessageReceived -= OnLog;
            File.WriteAllText($"{Dir}/report.txt", report.ToString());
        }
    }
}
