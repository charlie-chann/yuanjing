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

/// 湖心小寺走一圈、拍下来（看画面用的巡检）：全用真的游戏——发给 GameDirector 的指令（走、坐、跪拜、上香、挂布条、换天色），
/// 真的镜头（ViewSwitcher 的俯视、平视、第一人称，拖动、捏合放大都走 look / zoom 指令；上香、系布条时是游戏自己的特写），
/// 只有「站到哪儿」用瞬移省时间。按编号拍：
///   01 俯视全岛  02 石台上平视大殿  03 殿前抬头看匾  04 夜里的殿前  05 俯视石台上的蒲团  06 离蒲团一米（near.seat）  07 坐下
///   08 点「进殿」走进去的第一眼  09 同一处换第一人称  10 进殿门（平视、锁住）  11 过道里看供桌和三尊像  12 中间拜垫上跪下（镜头在身后）  13 跪在拜垫上看释迦的脸（第一人称放大）
///   14、15 从两边拜垫看阿弥陀、药师  16、17 坐在西边、东边的蒲团上  18 从供桌前回头看门  19 过道里抬头看藻井  20 供桌近看
///   21–23 上香（举香、拜、插香）  24 叩首  25 殿里的夜  26 坐着时裙子的近景  27 叩首时裙子的近景  28 殿东北角外面（松树下）
///   30 捏着布条走过去  31 系布条的特写  32 平视看挂好的字  33 树上大家的心意
///   34 殿里有香客跪拜、静坐（过道里平视）  35（36）同一时刻从门里看进去（宽；两块拜垫一张装不下就一块一张）
/// 截图在 unity/shots/tour/NN_名字.png，联系表 unity/shots/tour/sheet.png；每张都记下人在哪、朝哪、什么视角（锁没锁）、镜头在哪、
/// near 报了什么、Flutter 这时会显示哪些按钮（照 sanctuary_page.dart 的规则算），写在 report.txt。
/// 殿里的画面不拖动镜头（看的就是游戏自己摆的样子）：要看的那尊佛像头顶得在画面里、自己头顶的名字收起来（ExpectFrame）；叩首时头发不翘。
/// 该有的按钮、视角对不上就记一笔，最后有对不上的就算失败。跑：unity/playtest.sh TourTest（约 4 分钟）
public class TourTest
{
    // iPhone 竖屏的一半（1170×2532）
    const int W = 585, H = 1266, TW = 195, TH = 422;
    const string Dir = "../shots/tour";

    readonly StringBuilder report = new StringBuilder();
    readonly List<string> sent = new List<string>();
    readonly List<string> wrong = new List<string>();
    readonly List<(int n, Color32[] px)> thumbs = new List<(int, Color32[])>();
    GameObject bridge, player;
    Camera cam;
    RenderTexture rt;
    Texture2D tex;
    object gd, folk, vs, off;
    int mySeat = -1;

    [Serializable]
    class Reply
    {
        public string type, spot, mode, pet;
        public int seat = -999, mat = -999, slot = -999;
        public bool altar, locked, water;
    }

    void OnLog(string c, string st, LogType t)
    {
        if (c.StartsWith("SendToFlutter - ")) sent.Add(c.Substring(16));
    }

    void Cmd(string json) => bridge.SendMessage("OnMessage", json);

    void Log(string s)
    {
        report.AppendLine(s);
        Debug.Log("[yuanjing] 巡览 " + s);
    }

    void Expect(bool ok, string what)
    {
        if (ok) return;
        wrong.Add(what);
        Log("！不对：" + what);
    }

    // ── 反射（测试程序集引用不到游戏的类型）──
    static MethodInfo M(object o, string name, int args)
    {
        foreach (var m in o.GetType().GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
            if (m.Name == name && m.GetParameters().Length == args) return m;
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

    static string F(Vector3 v) => $"({v.x:F2}, {v.y:F2}, {v.z:F2})";
    static string Inv(float f) => f.ToString(System.Globalization.CultureInfo.InvariantCulture);
    static float Flat(Vector3 a, Vector3 b) => Vector2.Distance(new Vector2(a.x, a.z), new Vector2(b.x, b.z));
    Vector3 Me => player.transform.position;
    float MyYaw => ((Component)folk).transform.eulerAngles.y;
    string Act => Get<string>(folk, "actNow");

    // ── 收到的消息 ──
    Reply Last(string type, int since = 0)
    {
        for (int i = sent.Count - 1; i >= since; i--)
        {
            var r = JsonUtility.FromJson<Reply>(sent[i]);
            if (r.type == type) return r;
        }
        return null;
    }

    Reply LastNear() => Last("near") ?? new Reply { seat = -1, mat = -1, pet = "" };

    /// 等某种消息，最多 secs 秒
    IEnumerator Wait(string type, float secs, int since, Func<Reply, bool> ok = null, Action<Reply> got = null)
    {
        for (float t = 0; t < secs; t += Time.deltaTime)
        {
            for (int i = since; i < sent.Count; i++)
            {
                var r = JsonUtility.FromJson<Reply>(sent[i]);
                if (r.type == type && (ok == null || ok(r))) { got?.Invoke(r); yield break; }
            }
            yield return null;
        }
    }

    /// Flutter 的 _at：arrived 报的地点（空的算 court），坐下是 seat，起身是 court
    string At()
    {
        for (int i = sent.Count - 1; i >= 0; i--)
        {
            var r = JsonUtility.FromJson<Reply>(sent[i]);
            if (r.type == "arrived") return string.IsNullOrEmpty(r.spot) ? "court" : r.spot;
            if (r.type == "seated") { mySeat = r.seat; return "seat"; }
            if (r.type == "stood") return "court";
        }
        return "";
    }

    bool Locked => Last("view")?.locked ?? false;
    string Mode => Get<string>(vs, "Mode");

    /// 这时 Flutter 会显示的按钮（照 sanctuary_page.dart 的 _placeActions：在哪个地点、near 报的坐下 / 拜垫 / 上香、锁没锁）。
    /// 殿里的主按钮前面带 *（Has 不管有没有 *）
    bool Has(string button) => Buttons().Exists(x => x.TrimStart('*') == button);
    string Primary() => Buttons().Find(x => x.StartsWith("*"))?.Substring(1) ?? "";

    List<string> Buttons()
    {
        var near = LastNear();
        string at = At();
        int seat = at == "seat" ? mySeat : -1;
        bool inHall = at == "inhall" || Locked || (at == "seat" && seat >= 60);
        var places = new[] { ("court", "起身走走"), ("tree", "去许愿树"), ("burner", "去香炉"), ("hall", "去大殿"), ("inhall", "进殿") };
        var others = new List<string>();
        foreach (var (spot, go) in places)
            if (spot != at && spot != "court" && (spot != "inhall" || !inHall)) others.Add(inHall && spot == "hall" ? "出殿" : go);
        var b = new List<string>();
        if (!string.IsNullOrEmpty(near.pet)) b.Add("摸摸");
        if (near.water) b.Add("喂鱼");
        bool sit = near.seat >= 0;
        if (at == "seat") b.AddRange(new[] { "许愿", "合掌", "鞠躬", "静坐", "起身" });
        else if (at == "inhall")
        {
            // 站在拜垫上：跪拜在前（主按钮），上香跟在后面
            bool onMat = near.mat >= 0;
            if (onMat) b.Add($"*跪拜(拜垫{near.mat})");
            if (near.altar) b.Add(onMat ? "上香" : "*上香");
            if (sit) b.Add(!onMat && !near.altar ? "*坐下" : "坐下");
            if (!onMat) b.Add("跪拜");
            b.Add("鞠躬");
            b.Add(!onMat && !near.altar && !sit ? "*合掌" : "合掌");
        }
        else if (at == "court")
        {
            if (sit) b.Add("坐下");
            b.AddRange(new[] { "合掌", "鞠躬", "跪拜", "喂小鸟" });
        }
        else if (at != "")
        {
            if (at == "tree") b.AddRange(new[] { "挂红布条", "挂木牌" });
            if (at == "burner") b.Add("上香");
            if (sit) b.Add("坐下");
            b.AddRange(new[] { "合掌", "鞠躬", "跪拜" });
        }
        b.AddRange(others);
        return b;
    }

    // ── 摆人、摆镜头 ──
    void Teleport(Vector3 p, float yaw)
    {
        var cc = player.GetComponent<CharacterController>();
        cc.enabled = false;
        player.transform.position = p;
        cc.enabled = true;
        ((Component)folk).transform.rotation = Quaternion.Euler(0, yaw, 0);
        Run(folk, "FaceYaw", yaw);
        Physics.SyncTransforms();
        // 镜头直接摆到人身后（同进场时）
        Run(Get<object>(gd, "cam"), "Snap", yaw);
    }

    static float YawTo(Vector3 from, Vector3 to) => Quaternion.LookRotation(new Vector3(to.x - from.x, 0, to.z - from.z)).eulerAngles.y;

    void View(string kind) => Cmd($"{{\"cmd\":\"view\",\"kind\":\"{kind}\"}}");
    void Zoom(float x) => Cmd($"{{\"cmd\":\"zoom\",\"x\":{Inv(x)}}}");
    /// 手指拖画面：dy 正是往上看（平视最多抬 12 度）
    void Look(float dx, float dy) => Cmd($"{{\"cmd\":\"look\",\"dx\":{Inv(dx)},\"dy\":{Inv(dy)}}}");
    void Sky(string time) => Cmd($"{{\"cmd\":\"sky\",\"time\":\"{time}\",\"weather\":\"clear\",\"instant\":true}}");

    void Stick(Vector3 world)
    {
        if (world.sqrMagnitude < 1e-4f) { Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":0}"); return; }
        // 按着摇杆时 GameDirector 用按下那一刻镜头的朝向算方向（平视的镜头会跟着人转）
        float yaw = (Get<bool>(gd, "stickHeld") ? Get<float>(gd, "stickYaw") : Get<float>(Get<object>(gd, "cam"), "Yaw")) * Mathf.Deg2Rad;
        world.y = 0;
        world.Normalize();
        float x = world.x * Mathf.Cos(yaw) - world.z * Mathf.Sin(yaw), y = world.x * Mathf.Sin(yaw) + world.z * Mathf.Cos(yaw);
        Cmd($"{{\"cmd\":\"move\",\"x\":{Inv(x)},\"y\":{Inv(y)}}}");
    }

    /// 第一人称镜头直接抬头 / 低头到某个角度（正是往下看）
    void FirstPitch(float pitch)
    {
        var first = Get<object>(vs, "first");
        Set(first, "pitchTarget", pitch);
    }

    static string Mask(string file) => File.Exists($"../shots/wish/{file}.png") ? Convert.ToBase64String(File.ReadAllBytes($"../shots/wish/{file}.png")) : "";

    // ── 拍照 ──
    void Shot(int n, string name)
    {
        cam.targetTexture = rt;
        cam.Render();
        cam.targetTexture = null;
        RenderTexture.active = rt;
        tex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
        tex.Apply();
        RenderTexture.active = null;
        File.WriteAllBytes($"{Dir}/{n:00}_{name}.png", tex.EncodeToPNG());
        var px = new Color32[TW * TH];
        for (int y = 0; y < TH; y++)
            for (int x = 0; x < TW; x++)
                px[y * TW + x] = tex.GetPixelBilinear((x + 0.5f) / TW, (y + 0.5f) / TH);
        thumbs.Add((n, px));
        var near = LastNear();
        Vector3 cp = cam.transform.position;
        var follow = Get<object>(vs, "follow");
        string hit = Get<string>(follow, "LastHit");
        var body = BodyInFrame();
        Log($"{n:00} {name}：人 {F(Me)} 朝 {MyYaw:F0}°，视角 {Mode}{(Locked ? "（锁）" : "")} 放大 {Get<float>(vs, "Zoom"):F1}，" +
            $"镜头 {F(cp)} 离人 {Vector3.Distance(cp, Me + Vector3.up * 0.95f):F2} 米 视角 {cam.fieldOfView:F0}°{(string.IsNullOrEmpty(hit) ? "" : $" 被 {hit} 挡")}，" +
            $"人在画面里 脚 {body.feet:F2} 头顶 {body.top:F2}（0 底 1 顶；木牌摇杆挡着 0.20 以下，地名牌子挡着 0.90 以上），" +
            $"near 坐下 {near.seat} 拜垫 {near.mat} 上香 {near.altar}，在 {At()}，动作 {Act ?? "-"}，按钮 [{string.Join(" ", Buttons())}]");
    }

    /// 自己在画面里多高：身上最低的那一点（脚、跪着的膝盖小腿）和最高的那一点（头顶）的画面高度（0 底 1 顶），按身上几个蒙皮网格的包围盒算
    (float feet, float top) BodyInFrame()
    {
        var anim = ((Component)folk).GetComponentInChildren<Animator>();
        var hd = anim.GetBoneTransform(HumanBodyBones.Head);
        float lo = 9, hi = -9;
        foreach (var b in new[] { HumanBodyBones.LeftToes, HumanBodyBones.RightToes, HumanBodyBones.LeftFoot, HumanBodyBones.RightFoot, HumanBodyBones.LeftLowerLeg, HumanBodyBones.RightLowerLeg, HumanBodyBones.Hips })
        {
            var t = anim.GetBoneTransform(b);
            if (t == null) continue;
            lo = Mathf.Min(lo, cam.WorldToViewportPoint(t.position + Vector3.down * 0.03f).y);
        }
        hi = cam.WorldToViewportPoint(hd.position + Vector3.up * 0.14f).y;
        return (lo, hi);
    }

    /// 人整个在界面中间露出来的那一截里（脚不被底下的木牌、摇杆挡着；头不被上面的地名、牌子挡着）
    void ExpectBody(int n, float bottom = 0.19f, float top = 0.91f)
    {
        var b = BodyInFrame();
        Expect(b.feet >= bottom, $"{n:00}：人的脚在画面 {b.feet:F2} 处，被底下的木牌、摇杆挡着（要 {bottom:F2} 以上）");
        Expect(b.top <= top, $"{n:00}：人的头顶在画面 {b.top:F2} 处，被上面的牌子挡着（要 {top:F2} 以下）");
    }

    /// 用主镜头从指定的位置拍一张（看细处：裙子有没有被腿顶穿），拍完摆回去
    void CloseShot(int n, string name, Vector3 eye, Vector3 at, float fov)
    {
        var p = cam.transform.position; var r = cam.transform.rotation; float f = cam.fieldOfView, nc = cam.nearClipPlane;
        cam.transform.SetPositionAndRotation(eye, Quaternion.LookRotation(at - eye));
        cam.fieldOfView = fov;
        cam.nearClipPlane = 0.05f;
        Shot(n, name);
        cam.transform.SetPositionAndRotation(p, r);
        cam.fieldOfView = f;
        cam.nearClipPlane = nc;
    }

    /// 镜头和自己（胸口）之间 0.5 米以内有没有别人（香客没有碰撞体，射线测不到）
    bool PeopleBetween()
    {
        Vector3 a = cam.transform.position, b = Me + Vector3.up * 0.9f;
        foreach (var an in UnityEngine.Object.FindObjectsByType<Animator>(FindObjectsSortMode.None))
        {
            if (an.transform.IsChildOf(player.transform)) continue;
            bool pilgrim = false;
            for (var tr = an.transform; tr != null && !pilgrim; tr = tr.parent) pilgrim = tr.name.StartsWith("Pilgrim_");
            if (!pilgrim) continue;
            Vector3 p = an.transform.position + Vector3.up * 0.9f, ab = b - a;
            float t = Mathf.Clamp01(Vector3.Dot(p - a, ab) / ab.sqrMagnitude);
            if (Vector3.Distance(p, a + ab * t) < 0.5f) return true;
        }
        return false;
    }

    /// 自己的髋在哪、面朝哪（水平）
    Vector3 Hips => ((Component)folk).GetComponentInChildren<Animator>().GetBoneTransform(HumanBodyBones.Hips).position;
    Vector3 Fwd { get { var f = ((Component)folk).transform.forward; f.y = 0; return f.normalized; } }

    /// 佛像的头顶在不在画面里（离上边、左右边至少留一点）：返回在画面里的高度（0 底 1 顶），不在画面里是负数
    float InFrame(Vector3 p)
    {
        // 按截图的竖画面（W×H）算左右：主镜头平时的宽高比是编辑器窗口的（横的）
        cam.aspect = (float)W / H;
        Vector3 v = cam.WorldToViewportPoint(p);
        cam.ResetAspect();
        return v.z > 0 && v.x > 0.02f && v.x < 0.98f && v.y > 0f && v.y < 0.98f ? v.y : -1f;
    }

    static readonly Vector3 HeadC = new Vector3(0, 4.45f, 21.0f), HeadW = new Vector3(-3.6f, 4.0f, 21.0f), HeadE = new Vector3(3.6f, 4.0f, 21.0f);

    /// 殿里的画面：要看的那尊佛像头顶在画面里；自己头顶的名字收起来了
    void ExpectFrame(int n, Vector3 head, string who)
    {
        float y = InFrame(head);
        var tag = Get<TextMesh>(folk, "nameTag");
        bool tagShown = tag != null && tag.gameObject.activeInHierarchy;
        Log($"{n:00} 画面：{who}头顶在画面里 {(y >= 0 ? $"高 {y:F2}" : "不在")}，镜头往上抬 {Get<float>(Get<object>(vs, "follow"), "Tilt"):F1}°，自己的名字 {(tagShown ? "显示" : "收起")}");
        Expect(y >= 0, $"{n:00}：{who}的头不在画面里");
        Expect(!tagShown, $"{n:00}：殿里自己头顶的名字没收起来");
        ExpectBody(n);
    }

    /// 头发：最高的那根头发骨头比头骨高多少（叩首时头发该往下垂，不该翘起来）
    float HairAboveHead()
    {
        var anim = ((Component)folk).GetComponentInChildren<Animator>();
        var head = anim.GetBoneTransform(HumanBodyBones.Head);
        float top = float.MinValue;
        foreach (var t in anim.GetComponentsInChildren<Transform>())
            if (t.name.StartsWith("HairJoint")) top = Mathf.Max(top, t.position.y - head.position.y);
        return top;
    }

    IEnumerator Settle(float secs)
    {
        yield return new WaitForSeconds(secs);
    }

    /// 联系表：每张缩成 195×422，六张一行，左上角写编号
    void Sheet()
    {
        const int cols = 6, gap = 4;
        int rows = (thumbs.Count + cols - 1) / cols;
        int sw = cols * TW + (cols + 1) * gap, sh = rows * TH + (rows + 1) * gap;
        var px = new Color32[sw * sh];
        for (int i = 0; i < px.Length; i++) px[i] = new Color32(24, 24, 24, 255);
        for (int k = 0; k < thumbs.Count; k++)
        {
            int ox = gap + (k % cols) * (TW + gap), oy = sh - (gap + (k / cols + 1) * (TH + gap)) + gap;
            var t = thumbs[k].px;
            for (int y = 0; y < TH; y++)
                for (int x = 0; x < TW; x++) px[(oy + y) * sw + ox + x] = t[y * TW + x];
            Number(px, sw, ox + 4, oy + TH - 4, thumbs[k].n);
        }
        var s = new Texture2D(sw, sh, TextureFormat.RGB24, false);
        s.SetPixels32(px);
        s.Apply();
        File.WriteAllBytes($"{Dir}/sheet.png", s.EncodeToPNG());
        UnityEngine.Object.Destroy(s);
    }

    // 3×5 的数字（一行三位，从上到下）
    static readonly string[] Digits = { "111101101101111", "010110010010111", "111001111100111", "111001111001111", "101101111001001", "111100111001111", "111100111101111", "111001010010010", "111101111101111", "111101111001111" };

    /// 在 (x, top) 往下写两位编号：白字黑底，每个点 4 像素
    static void Number(Color32[] px, int sw, int x, int top, int n)
    {
        const int s = 4;
        string str = n.ToString("00");
        for (int yy = -2; yy < 5 * s + 2; yy++)
            for (int xx = -2; xx < str.Length * 4 * s; xx++) px[(top - yy) * sw + x + xx] = new Color32(0, 0, 0, 255);
        for (int c = 0; c < str.Length; c++)
        {
            string d = Digits[str[c] - '0'];
            for (int r = 0; r < 5; r++)
                for (int q = 0; q < 3; q++)
                    if (d[r * 3 + q] == '1')
                        for (int a = 0; a < s; a++)
                            for (int b = 0; b < s; b++) px[(top - r * s - a) * sw + x + c * 4 * s + q * s + b] = new Color32(255, 255, 255, 255);
        }
    }

    /// Pilgrims.CrowdOverride（静态）：本机人数，0 是照钟点
    static void CrowdOverride(int n) => Type.GetType("Yuanjing.Pilgrims, Assembly-CSharp").GetField("CrowdOverride").SetValue(null, n);

    [UnityTest, Timeout(600000)]
    public IEnumerator Tour()
    {
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
            // 没联网（seed 9）：本机自己安排香客来来往往、坐蒲团
            Cmd("{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"我\"}");
            yield return new WaitForSeconds(3f);
            player = GameObject.Find("Player");
            cam = Camera.main;
            rt = new RenderTexture(W, H, 24) { antiAliasing = 4 };
            tex = new Texture2D(W, H, TextureFormat.RGB24, false);
            gd = Type.GetType("Yuanjing.GameDirector, Assembly-CSharp").GetProperty("Instance").GetValue(null);
            folk = Get<object>(gd, "player");
            off = Get<object>(gd, "offerings");
            vs = cam.GetComponent(Type.GetType("Yuanjing.ViewSwitcher, Assembly-CSharp"));
            // 殿里的香客（PilgrimsHall）关掉：巡视要站上两边的拜垫、坐殿里的蒲团，随机进殿的人会占着。殿里有香客的样子见最后的 34、35 和 HallCrowdTest
            Run(Get<object>(gd, "pilgrims"), "HallCrowd", false);
            Assert.IsTrue(Get<bool>(gd, "hallOpen"), "大殿没开（BuildIslet.HallOpen）");
            var entered = Last("entered");
            Log($"进岛：entered {(entered != null ? "收到了" : "没有")}，{sent.Count} 条消息");

            // ── 01 俯视全岛（站在院子中间，石台南边）──
            View("top");
            Teleport(new Vector3(0, 0.08f, 0.6f), 0);
            yield return Settle(2.5f);
            Shot(1, "top_island_day");

            // ── 02 石台南头，平视看大殿 ──
            View("level");
            Teleport(new Vector3(0, 0.08f, 1.6f), 0);
            yield return Settle(1.8f);
            Shot(2, "terrace_level_to_hall");

            // ── 03 走到殿前（「去大殿」），再退回石台北头抬头看匾（匾在上檐下面，台阶跟前被下檐挡着看不到）──
            int n0 = sent.Count;
            Cmd("{\"cmd\":\"goto\",\"spot\":\"hall\"}");
            yield return Wait("arrived", 20f, n0, r => r.spot == "hall");
            Expect(At() == "hall" && Has("进殿"), $"殿前应该有「进殿」：在 {At()}，按钮 {string.Join(" ", Buttons())}");
            Teleport(new Vector3(0, 0.08f, 6.6f), 0);
            Look(0, 0.25f);
            yield return Settle(1.6f);
            Shot(3, "hall_front_plaque");

            // ── 04 夜里的殿前（石台南头）──
            Sky("night");
            Teleport(new Vector3(0, 0.08f, 1.6f), 0);
            Look(0, 0.12f);
            yield return Settle(2f);
            Shot(4, "night_exterior");
            Sky("day");

            // ── 05 俯视石台上的六十个蒲团 ──
            View("top");
            Teleport(new Vector3(0, 0.08f, 4.6f), 0);
            yield return Settle(2.5f);
            Shot(5, "top_outdoor_cushions");

            // ── 06 走到一个蒲团跟前（离它坐下前站的那一点一米）：near 报这个蒲团，有「坐下」；再远就没有 ──
            View("level");
            int seat = -1;
            Vector3 stand = Vector3.zero, lane = Vector3.zero;
            // 挑中间过道东边第一列（x 1.3）、没人的那一个：从过道上走过去，旁边没有别的蒲团抢着报
            for (int i = 0; i < 60 && seat < 0; i++)
            {
                Vector3 g = Call<Vector3>(gd, "SeatGround", i);
                if (Mathf.Abs(g.x - 1.3f) > 0.05f || g.z < 3f || !Call<bool>(gd, "SeatFree", i)) continue;
                seat = i;
                stand = Call<Vector3>(gd, "SeatStand", i);
                lane = Call<Vector3>(gd, "SeatLane", i);
            }
            Assert.GreaterOrEqual(seat, 0, "石台上东边第一列没有空蒲团");
            {
                // 中间过道正中：离两边第一列蒲团（x ±1.3）都超过 1.2 米
                Vector3 far = new Vector3(0, lane.y + 0.02f, lane.z);
                Teleport(far, YawTo(far, stand));
                yield return Settle(0.8f);
                var nf = LastNear();
                Log($"离 {seat} 号蒲团 {Flat(Me, stand):F2} 米：near.seat {nf.seat}");
                Expect(nf.seat < 0 && !Has("坐下"), $"离蒲团 {Flat(Me, stand):F2} 米不该有「坐下」（near.seat {nf.seat}）");
                Vector3 p = new Vector3(stand.x - Mathf.Sqrt(Mathf.Max(0.01f, 1f - (lane.z - stand.z) * (lane.z - stand.z))), lane.y + 0.02f, lane.z);
                Teleport(p, YawTo(p, stand));
                yield return Settle(1.6f);
                var nr = LastNear();
                Log($"离 {seat} 号蒲团 {Flat(Me, stand):F2} 米：near.seat {nr.seat}");
                Shot(6, "near_outdoor_cushion");
                Expect(nr.seat == seat && Has("坐下"), $"离蒲团一米应该报它、有「坐下」：near.seat {nr.seat}（想要 {seat}）");

                // ── 07 「坐下」──
                n0 = sent.Count;
                Cmd($"{{\"cmd\":\"sit\",\"seat\":{nr.seat}}}");
                Reply sat = null;
                yield return Wait("seated", 12f, n0, null, r => sat = r);
                Expect(sat != null && sat.seat == seat, $"坐下：{(sat != null ? sat.seat.ToString() : "没坐下")}");
                yield return Settle(3f);
                Shot(7, "seated_outdoor");
                Expect(At() == "seat" && Has("起身"), $"坐着应该有「起身」：在 {At()}");
                n0 = sent.Count;
                Cmd("{\"cmd\":\"stand\"}");
                yield return Wait("arrived", 12f, n0);
                Log($"起身：退到 {F(Me)}（走道上那一点 {F(lane)}，差 {Flat(Me, lane):F2} 米）");
            }

            // ── 08 「进殿」：从石台北头点「进殿」走进去，到了以后的第一眼（镜头自己摆的，不拖）──
            Teleport(new Vector3(0, 0.08f, 8.2f), 0);
            yield return Settle(0.8f);
            n0 = sent.Count;
            Cmd("{\"cmd\":\"goto\",\"spot\":\"inhall\"}");
            Reply inh = null;
            yield return Wait("arrived", 30f, n0, r => r.spot == "inhall", r => inh = r);
            Expect(inh != null, "「进殿」没走到");
            yield return Settle(2.5f);
            Shot(8, "goto_inhall");
            ExpectFrame(8, HeadC, "释迦");
            Expect(Primary() == "跪拜(拜垫1)" && Has("上香"), $"「进殿」到了（中间拜垫后面）主按钮应该是跪拜（拜垫1）、也有上香：{string.Join(" ", Buttons())}");
            // ── 09 同一处换第一人称（不拖）：殿里第一人称一换过来就微微抬头，释迦的头也在画面里 ──
            View("first");
            yield return Settle(1.2f);
            Shot(9, "goto_inhall_first");
            ExpectFrame(9, HeadC, "释迦");
            View("level");

            // ── 10 从廊下推摇杆走进殿门：一进门换平视、锁住 ──
            Teleport(new Vector3(0, 0.76f, 12.3f), 0);
            yield return Settle(1.0f);
            n0 = sent.Count;
            bool lockedShot = false;
            float t0 = Time.time;
            while (Me.z < 16.2f && Time.time - t0 < 12f)
            {
                Stick(Vector3.forward);
                yield return null;
                if (!lockedShot && Last("view", n0) != null && Last("view", n0).locked && Me.z > 14.75f)
                {
                    lockedShot = true;
                    Shot(10, "enter_door_locked");
                    Expect(Mode == "level", $"进门应该是平视：{Mode}");
                }
            }
            Stick(Vector3.zero);
            Expect(lockedShot, "进殿没有锁平视");

            // ── 11 过道里：第三人称，看供桌和三尊像（镜头自己摆的，不拖）──
            yield return Settle(2.9f);
            Shot(11, "aisle_to_altar");
            ExpectFrame(11, HeadC, "释迦");
            Log($"站着：头发最高处比头骨高 {HairAboveHead():F3} 米");
            Expect(At() == "inhall" && Locked, $"殿里应该在 inhall、锁平视：在 {At()}，锁 {Locked}");
            // 殿里平视镜头离人 2.6 米（ViewSwitcher.interiorDistance）：比外面的 3 米近，人整个、佛像整尊才放得进界面中间那一截
            Expect(Get<float>(Get<object>(vs, "follow"), "distance") <= 2.61f, "殿里平视镜头没收近到 2.6 米");

            // ── 12、24 中间拜垫：走到跟前（0.7 米）点「跪拜」：走上拜垫、面朝释迦、跪下、叩首三次（镜头在身后）──
            Teleport(new Vector3(0.3f, 0.76f, 17.15f), 0);
            yield return Settle(1.0f);
            Expect(LastNear().mat == 1 && LastNear().altar && Primary() == "跪拜(拜垫1)" && Has("上香"),
                $"中间拜垫跟前主按钮应该是「跪拜」（拜垫 1），也有「上香」：near.mat {LastNear().mat} altar {LastNear().altar}，{string.Join(" ", Buttons())}");
            n0 = sent.Count;
            Cmd("{\"cmd\":\"act\",\"action\":\"kneel\",\"mat\":1}");
            bool s12 = false, s24 = false;
            t0 = Time.time;
            Reply done = null;
            while (done == null && Time.time - t0 < 30f)
            {
                yield return null;
                done = Last("actionDone", n0);
                string a = Act;
                // 跪稳了（Kneel_Loop）再拍
                if (!s12 && a == "Kneel_Loop" && Time.time - t0 > 1f) { s12 = true; Shot(12, "kneel_centre_mat"); ExpectFrame(12, HeadC, "释迦"); }
                if (!s24 && a == "Kowtow_Scrub" && Get<float>(folk, "bowPhase") > 0.85f)
                {
                    s24 = true;
                    Shot(24, "kowtow_centre_mat");
                    ExpectFrame(24, HeadC, "释迦");
                    // 27 叩首时从身后斜上方凑近看裙子（以前腿、臀部、背心从裙子后面顶出来）
                    Vector3 hk = Hips;
                    CloseShot(27, "kowtow_skirt_close", hk - Fwd * 1.1f + Vector3.up * 0.75f + Vector3.Cross(Vector3.up, Fwd) * 0.35f, hk, 40f);
                    float hair = HairAboveHead();
                    Log($"叩首：头发最高处比头骨高 {hair:F3} 米");
                    Expect(hair < 0.12f, $"叩首时头发翘起来了（最高处比头骨高 {hair:F2} 米）");
                }
            }
            Expect(s12 && s24 && done != null, $"中间拜垫跪拜：跪下 {s12} 叩首 {s24} 做完 {done != null}");

            // ── 13 再跪一次，第一人称、放大，跪着抬头看释迦的脸（镜头摆正朝北）──
            View("first");
            Run(Get<object>(gd, "cam"), "Snap", 0f);
            Zoom(2.4f);
            n0 = sent.Count;
            Cmd("{\"cmd\":\"act\",\"action\":\"kneel\",\"mat\":1}");
            t0 = Time.time;
            bool s13 = false;
            done = null;
            Vector3 face = new Vector3(0, 3.95f, 21.0f);
            while (done == null && Time.time - t0 < 30f)
            {
                yield return null;
                done = Last("actionDone", n0);
                // 跪稳了、还没拜下去：眼睛高度跟着头（约 1.6 米），抬头对着脸
                float since = Time.time - t0;
                if (!s13 && since > 1.8f)
                {
                    Vector3 eye = cam.transform.position;
                    FirstPitch(-Mathf.Atan2(face.y - eye.y, face.z - eye.z) * Mathf.Rad2Deg);
                }
                if (!s13 && since > 2.9f && Act == "Kneel_Loop") { s13 = true; Shot(13, "kneel_eye_buddha_face"); }
            }
            Expect(s13, "跪着看佛像那一张没拍到");
            Zoom(1f);
            View("level");
            yield return Settle(0.8f);

            // ── 14、15 两边的拜垫上：西边阿弥陀、东边药师 ──
            foreach (var (n, x, mat, name) in new[] { (14, -3.6f, 3, "west_statue_from_mat"), (15, 3.6f, 4, "east_statue_from_mat") })
            {
                Teleport(new Vector3(x, 0.87f, 18.5f), 0);
                yield return Settle(1.8f);
                Shot(n, name);
                ExpectFrame(n, x < 0 ? HeadW : HeadE, x < 0 ? "阿弥陀" : "药师");
                Expect(LastNear().mat == mat && !Has("坐下"), $"站在拜垫{mat} 上 near.mat 应该是 {mat}、不该有「坐下」：mat {LastNear().mat} seat {LastNear().seat}");
            }

            // ── 16、17 殿里的蒲团：走到跟前、「坐下」坐最近的那个，坐稳了拍，再起身 ──
            foreach (var (n, x, name) in new[] { (16, -3.55f, "seated_west_cushion"), (17, 3.55f, "seated_east_cushion") })
            {
                Teleport(new Vector3(x, 0.76f, 16.4f), x < 0 ? 270f : 90f);
                yield return Settle(1.0f);
                var nr = LastNear();
                Expect(nr.seat >= 60 && Has("坐下"), $"殿里蒲团跟前应该有「坐下」：near.seat {nr.seat}");
                n0 = sent.Count;
                Cmd($"{{\"cmd\":\"sit\",\"seat\":{nr.seat}}}");
                Reply sat = null;
                yield return Wait("seated", 12f, n0, null, r => sat = r);
                Expect(sat != null && sat.seat >= 60, $"殿里的蒲团没坐下：{(sat != null ? sat.seat.ToString() : "没有 seated")}");
                yield return Settle(3.2f);
                Shot(n, name);
                ExpectBody(n);
                // 26 坐在西边蒲团上，从身后斜上方凑近看裙子（以前大腿、臀部从裙子后面顶出来）
                if (n == 16)
                {
                    Vector3 hs = Hips;
                    CloseShot(26, "seated_skirt_close", hs - Fwd * 1.0f + Vector3.up * 0.6f, hs + Vector3.up * 0.05f, 40f);
                }
                n0 = sent.Count;
                Cmd("{\"cmd\":\"stand\"}");
                yield return Wait("arrived", 12f, n0);
                Expect(At() == "inhall", $"殿里起身以后应该还在殿里：{At()}");
            }

            // ── 18 站在供桌前，回头看殿门 ──
            Teleport(new Vector3(0, 0.76f, 18.45f), 180f);
            yield return Settle(1.8f);
            Shot(18, "back_to_door_from_altar");
            Expect(LastNear().altar, "供桌前应该能上香");

            // ── 19 过道里第一人称抬头：天花和藻井 ──
            Teleport(new Vector3(0, 0.76f, 16.2f), 0);
            View("first");
            yield return Settle(0.3f);
            FirstPitch(-72f);
            yield return Settle(1.5f);
            Shot(19, "ceiling_zaojing");

            // ── 20 供桌近看：站在中间拜垫后面，第一人称微微低头看供桌（香炉、烛台、油灯、花瓶、桌围）──
            Teleport(new Vector3(0, 0.76f, 17.05f), 0);
            yield return Settle(0.3f);
            FirstPitch(10f);
            yield return Settle(1.6f);
            Shot(20, "altar_table_close");
            Expect(LastNear().altar && Has("上香"), "供桌前 1.5 米应该有「上香」");
            View("level");

            // ── 21–23 上香：从拜垫后面点「上香」：走到供桌前、拿出三支点着的香、举香拜三拜、俯身插进香炉（游戏自己的特写镜头）──
            Teleport(new Vector3(0.5f, 0.76f, 17.1f), 0);
            yield return Settle(1.0f);
            n0 = sent.Count;
            Cmd("{\"cmd\":\"offer\",\"kind\":\"incense\"}");
            t0 = Time.time;
            bool s21 = false, s22 = false, s23 = false;
            float plantAt = -1;
            done = null;
            while (done == null && Time.time - t0 < 40f)
            {
                yield return null;
                done = Last("offered", n0);
                string a = Act;
                var held = Get<GameObject>(gd, "held");
                if (!s21 && held != null && a == "Incense_Scrub" && Get<bool>(folk, "ActionReady")) { s21 = true; Shot(21, "incense_hold"); ExpectBody(21); }
                if (!s22 && a == "Incense_Scrub" && Get<float>(folk, "bowPhase") > 0.75f) { s22 = true; Shot(22, "incense_bow"); ExpectBody(22); }
                if (a == "Incense_Plant" && plantAt < 0) plantAt = Time.time;
                if (!s23 && plantAt > 0 && Time.time - plantAt > 1.45f) { s23 = true; Shot(23, "incense_plant"); ExpectBody(23); }
            }
            Expect(s21 && s22 && s23 && done != null, $"上香：举香 {s21} 拜 {s22} 插香 {s23} 做完 {done != null}");
            Log($"上香以后香炉里 {Get<int>(off, "HallSticks")} 把，人在 {F(Me)}");

            // ── 28 殿东北角外面（以前平视镜头整个埋在松树的针叶里；松树往东挪了，挡在镜头和人之间的叶子也会淡掉）──
            Teleport(new Vector3(10.2f, 1.0f, 19.5f), 300f);
            // 出了殿视角换回进殿前的那个：这里要平视
            yield return Settle(0.4f);
            View("level");
            Teleport(new Vector3(10.2f, 1.0f, 19.5f), 300f);
            yield return Settle(2.5f);
            Shot(28, "ne_corner_out");

            // ── 25 殿里的夜（过道里看佛像）──
            Sky("night");
            View("level");
            Teleport(new Vector3(0, 0.76f, 16.2f), 0);
            yield return Settle(2.2f);
            Shot(25, "night_interior");
            ExpectFrame(25, HeadC, "释迦");
            Sky("day");

            // ── 30–33 许愿树：别人已经挂了几件（带字）；站在树下点「挂红布条」：捏着卷起来的布条走到绳前、抬手放开、系上 ──
            // 站到树下（「去许愿树」从殿里走过来要半分钟，这里直接站过去；出殿时视角换回进殿前的平视）
            Vector3 treeAt = new Vector3(-8.6f, 0, -3f);
            Vector3 from = treeAt + new Vector3(3.4f, 0, -2.6f).normalized * 4.4f;
            from.y = 0.02f;
            n0 = sent.Count;
            Teleport(from, YawTo(from, treeAt));
            yield return Wait("arrived", 3f, n0, r => r.spot == "tree");
            // 别人已经挂了的：离自己最近的五格（自己要往旁边走几步才有空格），再往后隔一格挂一件，一共十四件，有布条有木牌、都写了字
            int slots = Get<int>(off, "SlotCount");
            var order = new List<int>();
            for (int i = 0; i < slots; i++) order.Add(i);
            order.Sort((a, b) => Flat(Call<Vector3>(off, "SlotPoint", a), Me).CompareTo(Flat(Call<Vector3>(off, "SlotPoint", b), Me)));
            string[] masks = { Mask("mask_ribbon_long"), Mask("mask_plaque"), Mask("mask_ribbon_short"), Mask("mask_ribbon") };
            int placed = 0;
            for (int k = 0; k < order.Count && placed < 14; k++)
            {
                if (k >= 5 && k % 2 == 0) continue;
                bool plaque = placed % 3 == 1;
                Cmd($"{{\"cmd\":\"offerings\",\"kind\":\"{(plaque ? "plaque" : "ribbon")}\",\"list\":\"{order[k]}\",\"id\":\"tour{order[k]}\",\"tex\":\"{masks[(plaque ? 1 : placed) % masks.Length]}\"}}");
                placed++;
            }
            yield return Settle(1.0f);
            Expect(At() == "tree" && Has("挂红布条"), $"树下应该有「挂红布条」：在 {At()}");
            n0 = sent.Count;
            Cmd($"{{\"cmd\":\"offer\",\"kind\":\"ribbon\",\"text\":\"愿家人平安喜乐\",\"tex\":\"{Mask("mask_ribbon")}\"}}");
            t0 = Time.time;
            bool s30 = false, s31 = false;
            float loopAt = -1;
            done = null;
            Vector3 start = Me;
            while (done == null && Time.time - t0 < 45f)
            {
                yield return null;
                done = Last("offered", n0);
                var carry = Get<GameObject>(gd, "carry");
                if (!s30 && carry != null && Flat(Me, start) > 0.7f && Get<bool>(folk, "Moving")) { s30 = true; Shot(30, "carry_ribbon_walking"); }
                if (Act == "Hang_Loop" && loopAt < 0) loopAt = Time.time;
                if (!s31 && loopAt > 0 && Time.time - loopAt > 0.7f) { s31 = true; Shot(31, "tying_close"); ExpectBody(31); }
            }
            Expect(s30 && s31 && done != null, $"挂布条：捏着走 {s30} 系 {s31} 做完 {done != null}（走了 {Flat(Me, start):F2} 米）");
            int mine = done != null ? done.slot : -1;

            // ── 32 平视看挂好的那一条：人站在它旁边（绳外半米、偏开 0.42 米，面朝绳子），镜头在身后，捏合放大一点 ──
            if (mine >= 0)
            {
                Vector3 sp = Call<Vector3>(off, "SlotPoint", mine), o = Call<Vector3>(off, "Outward", mine);
                Vector3 side = Vector3.Cross(Vector3.up, o);
                Vector3 p = sp + o * 0.5f + side * 0.42f;
                p.y = 0.02f;
                View("level");
                Teleport(p, YawTo(p, p - o));
                Zoom(1.4f);
                yield return Settle(2.0f);
                Shot(32, "hung_ribbon_level");
                Zoom(1f);
            }

            // ── 33 树上大家的心意：退远一点平视看整棵树 ──
            {
                Vector3 p = treeAt + new Vector3(3.4f, 0, -2.6f).normalized * 6.6f;
                p.y = 0.02f;
                Teleport(p, YawTo(p, treeAt));
                Look(0, -0.05f);
                yield return Settle(2.0f);
                Shot(33, "tree_overview_others");
            }

            // ── 34、35 殿里有香客（PilgrimsHall）：打开随机进殿，再请两位到中间两边的拜垫上跪拜、一位到西边蒲团上静坐；
            //    你站在过道里（中间拜垫后面）用游戏的平视镜头看一张，再从门里往里看一张宽的。香客走进来要二三十秒 ──
            {
                var pil = Get<object>(gd, "pilgrims");
                Run(pil, "HallCrowd", true);
                n0 = sent.Count;
                Cmd("{\"cmd\":\"goto\",\"spot\":\"inhall\"}");
                yield return Wait("arrived", 40f, n0, r => r.spot == "inhall");
                Teleport(new Vector3(-0.2f, 0.74f, 15.85f), 0f);
                string kw = Call<string>(pil, "HallSend", "k", 0, 0f);
                string ke = Call<string>(pil, "HallSend", "k", 2, 0f);
                string ms = Call<string>(pil, "HallSend", "m", 2, 120f);
                string Slot(string id) => id == null ? "" : Call<string>(pil, "HallSlot", id);
                bool On(string id) => Slot(id).EndsWith("+");
                Log($"34 请了 {kw}（拜垫0）、{ke}（拜垫2）、{ms}（蒲团2）");
                var hallEvents = Get<List<string>>(pil, "hallEvents");
                // 殿里记下的、和这几位有关的事（进殿、路线、让开、走不到、出殿……）
                void DumpEvents(string why, params string[] ids)
                {
                    foreach (var e in hallEvents)
                        foreach (var id in ids)
                            if (id != null && (e.Contains(" " + id + " ") || e.EndsWith(" " + id)))
                            {
                                Log($"34 {why} {(e.Length > 400 ? e.Substring(0, 400) + "…" : e)}");
                                break;
                            }
                }
                // 两位都跪上了（或者等了 70 秒、至少一位跪上了）再拍。请的人还没跪上就出了殿（走不到、被挤得不进殿了……）：记下他的经过，再请一位到同一块
                float tw = Time.time;
                bool resentW = false, resentE = false;
                while (Time.time - tw < 90f && !(On(kw) && On(ke) && On(ms)) && !(Time.time - tw > 70f && (On(kw) || On(ke))))
                {
                    if (!resentW && kw != null && Slot(kw) == "" && Time.time - tw < 60f)
                    {
                        resentW = true;
                        DumpEvents("还没跪上就出了殿：", kw);
                        kw = Call<string>(pil, "HallSend", "k", 0, 0f) ?? kw;
                        Log($"34 再请 {kw}（拜垫0）");
                    }
                    if (!resentE && ke != null && Slot(ke) == "" && Time.time - tw < 60f)
                    {
                        resentE = true;
                        DumpEvents("还没跪上就出了殿：", ke);
                        ke = Call<string>(pil, "HallSend", "k", 2, 0f) ?? ke;
                        Log($"34 再请 {ke}（拜垫2）");
                    }
                    yield return null;
                }
                // 请的时候指定了拜垫（有人跪在上面就等他起来，别人正走过去的让给他；只有你要用、有人站在上面才换）：照他们真跪上的那几块摆人、摆镜头
                var matsT = Get<Transform>(gd, "hallMats");
                var onMats = new List<(string id, Vector3 at)>();
                foreach (var id in new[] { kw, ke })
                {
                    string sl = Slot(id);
                    if (sl.Length > 1 && sl[0] == 'k' && sl.EndsWith("+") && int.TryParse(sl.Substring(1).TrimEnd('+'), out int mi) && mi < matsT.childCount) onMats.Add((id, matsT.GetChild(mi).position));
                }
                Vector3 aim = new Vector3(-0.7f, 0.75f, 17.7f);
                if (onMats.Count > 0)
                {
                    aim = Vector3.zero;
                    foreach (var q in onMats) aim += q.at;
                    aim /= onMats.Count;
                    aim.y = 0.75f;
                }
                // 你站在那几块拜垫后面 2 米的过道上（往它们那边偏一点，但不出中门的宽：镜头在你身后 2.6 米、从中门里看进来，偏多了被门扇挡住），镜头在你身后：跪着的人在你前面两边
                Teleport(new Vector3(Mathf.Clamp(aim.x - 0.2f, -0.45f, 0.45f), 0.74f, 15.85f), 0f);
                yield return Settle(2.5f);
                // 镜头和人之间有走过的香客（网点淡掉的一个人挡满画面）：等他走过去（最多 10 秒）
                for (float tc = 0; tc < 10f && PeopleBetween(); tc += Time.deltaTime) yield return null;
                Log($"34 殿里：{Call<string>(pil, "HallSummary")}；跪上的拜垫 {onMats.Count} 块，中心 ({aim.x:F2},{aim.z:F2})");
                Shot(34, "hall_npcs_level");
                bool any = On(kw) || On(ke);
                Expect(any, $"34：请进殿的香客 90 秒还没跪上拜垫（{kw} {Slot(kw)}，{ke} {Slot(ke)}）");
                if (!any) DumpEvents("没跪上：", kw, ke);
                // 从门里往里看：站在拜垫的另一侧（拜垫在西边就从门东边看），对着它们。门里看过去竖着的画面只有二十几度宽：
                // 两块拜垫一东一西（中间两边那两块也差不多）一张装不下，就一块一张（35、36）
                Vector3 EyeFor(Vector3 at) => new Vector3(at.x <= 0f ? 1.25f : -1.25f, 2.35f, 14.9f);
                Vector3 HeadOf(string id)
                {
                    var f = id == null ? null : GameObject.Find("Pilgrim_" + id);
                    var anim = f != null ? f.GetComponentInChildren<Animator>() : null;
                    var head = anim != null ? anim.GetBoneTransform(HumanBodyBones.Head) : null;
                    return head != null ? head.position : Vector3.zero;
                }
                // 按截图的画面（竖的 W×H）算：主镜头平时的宽高比是编辑器窗口的（横的），拿它算会以为两边都还在画面里
                Vector3 Vp(Vector3 eye, Vector3 at, Vector3 p)
                {
                    var p0 = cam.transform.position; var r0 = cam.transform.rotation; float fov0 = cam.fieldOfView;
                    cam.transform.SetPositionAndRotation(eye, Quaternion.LookRotation(at - eye));
                    cam.fieldOfView = 58f;
                    cam.aspect = (float)W / H;
                    Vector3 vp = cam.WorldToViewportPoint(p);
                    cam.ResetAspect();
                    cam.transform.SetPositionAndRotation(p0, r0); cam.fieldOfView = fov0;
                    return vp;
                }
                bool Inside(Vector3 vp) => vp.z > 0 && vp.x > 0.04f && vp.x < 0.96f && vp.y > 0.04f && vp.y < 0.96f;
                var views = new List<(Vector3 eye, Vector3 at, List<string> ids)>();
                if (onMats.Count == 0) views.Add((EyeFor(aim), aim, new List<string>()));
                else
                {
                    Vector3 e0 = EyeFor(aim);
                    bool all = onMats.TrueForAll(q => Inside(Vp(e0, aim, HeadOf(q.id))));
                    if (all) views.Add((e0, aim, onMats.ConvertAll(q => q.id)));
                    else foreach (var q in onMats) views.Add((EyeFor(q.at), new Vector3(q.at.x, 0.75f, q.at.z), new List<string> { q.id }));
                }
                for (int vi = 0; vi < views.Count; vi++)
                {
                    var (eye, at, ids) = views[vi];
                    foreach (var id in ids)
                    {
                        Vector3 vp = Vp(eye, at, HeadOf(id));
                        Log($"{35 + vi} {id} 的头在画面 ({vp.x:F2},{vp.y:F2})");
                        Expect(Inside(vp), $"{35 + vi}：跪着的 {id} 不在门里那张画面里");
                    }
                    CloseShot(35 + vi, vi == 0 ? "hall_npcs_door_wide" : "hall_npcs_door_wide_b", eye, at, 58f);
                }
                Run(pil, "HallCrowd", false);
            }

            Sheet();
            Log($"拍了 {thumbs.Count} 张；对不上的 {wrong.Count} 处：{string.Join("；", wrong)}");
            File.WriteAllText($"{Dir}/report.txt", report.ToString());
            Assert.IsEmpty(wrong, string.Join("；", wrong));
        }
        finally
        {
            CrowdOverride(0);
            Application.logMessageReceived -= OnLog;
            if (report.Length > 0) File.WriteAllText($"{Dir}/report.txt", report.ToString());
        }
    }
}
