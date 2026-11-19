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

/// 评审第三轮（p3_fix1）的几处，用真的游戏量：
/// 1. 殿里 16 个蒲团挨个坐一遍：平视镜头离人至少 1.5 米（以前靠墙那一列只剩 0.7 米，画面下面三分之一是后脑勺），各拍一张；
///    坐着时从正前方贴近拍脸（头顶在画面最上沿、不留空）：脸那一块不能是一整块深色（以前蒙皮网格的包围盒是站着的那一份，坐下以后脸被当成在画面外裁掉）。
/// 2. 坐下、起身（院子里、殿里各一次）：每帧画完以后（所有 LateUpdate 之后）量髋挪了多少、身子转了多少——一帧里蹿 8 厘米以上、转 25 度以上都算「跳」。
/// 3. 上下大殿的台阶（「进殿」自动走、「出殿」、摇杆推着走）：每帧量两只脚的脚底比台阶面低多少（插进去多深）、身子一帧里上下蹿多少。
/// 截图在 unity/shots/hallseat/，记录在 report.txt。跑：unity/playtest.sh HallSeatTest（约 5 分钟）
public class HallSeatTest
{
    string Dir = "../shots/hallseat";
    readonly StringBuilder report = new StringBuilder();
    readonly List<string> sent = new List<string>();
    readonly List<string> wrong = new List<string>();
    GameObject bridge, player;
    Camera cam;
    object gd, folk, vs;
    Animator anim;
    RenderTexture rt;
    Texture2D tex;

    [Serializable] class Reply { public string type, spot; public int seat = -999, mat = -999; }

    void OnLog(string c, string st, LogType t) { if (c.StartsWith("SendToFlutter - ")) sent.Add(c.Substring(16)); }
    void Cmd(string json) => bridge.SendMessage("OnMessage", json);
    void Log(string s) { report.AppendLine(s); Debug.Log("[yuanjing] 蒲团台阶 " + s); }
    void Expect(bool ok, string what) { if (ok) return; wrong.Add(what); Log("！不对：" + what); }

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
    static string F(Vector3 v) => $"({v.x:F2}, {v.y:F2}, {v.z:F2})";
    static float Flat(Vector3 a, Vector3 b) => Vector2.Distance(new Vector2(a.x, a.z), new Vector2(b.x, b.z));

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

    void Shot(string name, Camera c = null)
    {
        c = c ?? cam;
        c.targetTexture = rt;
        c.Render();
        c.targetTexture = null;
        RenderTexture.active = rt;
        tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
        tex.Apply();
        RenderTexture.active = null;
        File.WriteAllBytes($"{Dir}/{name}.png", tex.EncodeToPNG());
    }

    static readonly RaycastHit[] hits = new RaycastHit[8];
    /// 脚下踩得到的面（朝上的面，人的碰撞胶囊不算）
    static float Surface(Vector3 p)
    {
        int n = Physics.RaycastNonAlloc(p + Vector3.up * 0.5f, Vector3.down, hits, 1.2f, ~(1 << 2), QueryTriggerInteraction.Ignore);
        float best = float.NegativeInfinity;
        for (int i = 0; i < n; i++)
        {
            if (hits[i].collider is CharacterController || hits[i].normal.y < 0.7f) continue;
            best = Mathf.Max(best, hits[i].point.y);
        }
        return best;
    }

    float ankleH;
    Vector3 lastHips;
    float lastYaw;
    bool haveLast;
    float maxJump, maxTurn, maxDepth, maxRootStep;
    string jumpAt = "", turnAt = "", depthAt = "";
    bool measureFeet;
    float lastRootY;

    void Tick()
    {
        var hips = anim.GetBoneTransform(HumanBodyBones.Hips);
        Vector3 h = hips.position;
        float yaw = ((Component)folk).transform.eulerAngles.y;
        float rootY = player.transform.position.y;
        if (haveLast)
        {
            float j = (h - lastHips).magnitude, tr = Mathf.Abs(Mathf.DeltaAngle(lastYaw, yaw));
            if (j > maxJump) { maxJump = j; jumpAt = $"{Time.time:F2} 秒 {Get<string>(folk, "actNow") ?? "-"}"; }
            if (tr > maxTurn) { maxTurn = tr; turnAt = $"{Time.time:F2} 秒 {Get<string>(folk, "actNow") ?? "-"}"; }
            maxRootStep = Mathf.Max(maxRootStep, Mathf.Abs(rootY - lastRootY));
        }
        if (measureFeet)
        {
            foreach (var (b, toe) in new[] { (HumanBodyBones.LeftFoot, false), (HumanBodyBones.RightFoot, false), (HumanBodyBones.LeftToes, true), (HumanBodyBones.RightToes, true) })
            {
                var t = anim.GetBoneTransform(b);
                if (t == null) continue;
                Vector3 p = t.position;
                // 只量台阶那一块（|x| < 2.3，z 9.3..10.95）和拜垫附近
                bool stairs = Mathf.Abs(p.x) < 2.3f && p.z > 9.3f && p.z < 10.95f;
                if (!stairs) continue;
                float sole = toe ? p.y - 0.02f : p.y - ankleH;
                float s = Surface(new Vector3(p.x, sole, p.z));
                if (float.IsNegativeInfinity(s)) continue;
                // 脚尖正好顶在上一级的立面上（差一两毫米就算「在台阶里」、按上一级的面量出十几厘米）：往脚踝那边退 2 厘米再量一次，取低的那一面
                if (toe)
                {
                    var ank = anim.GetBoneTransform(b == HumanBodyBones.LeftToes ? HumanBodyBones.LeftFoot : HumanBodyBones.RightFoot).position;
                    Vector3 back = ank - p;
                    back.y = 0f;
                    if (back.sqrMagnitude > 1e-6f)
                    {
                        float s2 = Surface(new Vector3(p.x, sole, p.z) + back.normalized * 0.02f);
                        if (!float.IsNegativeInfinity(s2)) s = Mathf.Min(s, s2);
                    }
                }
                float d = s - sole;
                if (d > maxDepth) { maxDepth = d; depthAt = $"{b} 在 {F(p)} {Time.time:F2} 秒，原点 {F(player.transform.position)}，{Get<string>(folk, "DebugGround")}"; }
            }
        }
        lastHips = h;
        lastYaw = yaw;
        lastRootY = rootY;
        haveLast = true;
    }

    void ResetMeasure()
    {
        maxJump = maxTurn = maxDepth = maxRootStep = 0;
        jumpAt = turnAt = depthAt = "";
        haveLast = false;
    }

    IEnumerator Begin(string sub)
    {
        Dir = "../shots/hallseat/" + sub;
        Directory.CreateDirectory(Dir);
        foreach (var f in Directory.GetFiles(Dir, "*.png")) File.Delete(f);
        Application.logMessageReceived += OnLog;
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        bridge = GameObject.Find("Bridge");
        Cmd("{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"我\"}");
        yield return new WaitForSeconds(2.5f);
        player = GameObject.Find("Player");
        cam = Camera.main;
        rt = new RenderTexture(540, 1170, 24) { antiAliasing = 4 };
        tex = new Texture2D(540, 1170, TextureFormat.RGB24, false);
        gd = Type.GetType("Yuanjing.GameDirector, Assembly-CSharp").GetProperty("Instance").GetValue(null);
        folk = Get<object>(gd, "player");
        vs = cam.GetComponent(Type.GetType("Yuanjing.ViewSwitcher, Assembly-CSharp"));
        anim = ((Component)folk).GetComponentInChildren<Animator>();
        ankleH = Get<float>(folk, "ankle") * ((Component)folk).transform.lossyScale.y;
        // 殿里不要香客（随机进殿的人会占着蒲团）
        Run(Get<object>(gd, "pilgrims"), "HallCrowd", false);
        player.AddComponent<HallSeatLateProbe>().tick = Tick;
    }

    void End()
    {
        Application.logMessageReceived -= OnLog;
        File.WriteAllText($"{Dir}/report.txt", report.ToString());
    }

    /// 1. 殿里 16 个蒲团挨个坐：镜头离人多远、脸画出来没有
    [UnityTest, Timeout(1200000)]
    public IEnumerator SeatViews()
    {
        yield return Begin("views");
        try
        {
            Cmd("{\"cmd\":\"view\",\"kind\":\"level\"}");
            int n0 = sent.Count;
            Cmd("{\"cmd\":\"goto\",\"spot\":\"inhall\"}");
            yield return Wait("arrived", 50f, n0, r => r.spot == "inhall");
            int outdoor = Get<int>(gd, "OutdoorSeats");
            var hallSeats = Get<Transform>(gd, "hallSeats");
            var faceCam = new GameObject("FaceCam").AddComponent<Camera>();
            faceCam.enabled = false;
            faceCam.CopyFrom(cam);
            faceCam.fieldOfView = 34f;
            for (int k = 0; k < hallSeats.childCount; k++)
            {
                int seat = outdoor + k;
                Vector3 stand = Call<Vector3>(gd, "SeatStand", seat);
                Vector3 fwd = Call<Vector3>(gd, "SeatFwd", seat);
                Vector3 p = stand + fwd * 0.5f;
                p.y = 0.76f;
                Teleport(p, Quaternion.LookRotation(-fwd).eulerAngles.y);
                yield return new WaitForSeconds(0.6f);
                n0 = sent.Count;
                Cmd($"{{\"cmd\":\"sit\",\"seat\":{seat}}}");
                yield return Wait("seated", 15f, n0, r => r.seat == seat);
                yield return new WaitForSeconds(3.2f);
                var follow = Get<object>(vs, "follow");
                float dist = Get<float>(follow, "CurrentDistance");
                string hit = Get<string>(follow, "LastHit");
                Vector3 me = player.transform.position;
                Log($"蒲团 {seat}（{F(hallSeats.GetChild(k).position)}）：坐下了 {Get<int>(gd, "mySeat") == seat}，镜头离转轴 {dist:F2} 米{(string.IsNullOrEmpty(hit) ? "" : $"（{hit} 挡着）")}，" +
                    $"镜头朝 {cam.transform.eulerAngles.y:F0}° 俯 {cam.transform.eulerAngles.x:F0}°");
                Shot($"{k:00}_seat_{seat}");
                Expect(Get<int>(gd, "mySeat") == seat, $"蒲团 {seat} 没坐下");
                Expect(dist >= 1.5f, $"蒲团 {seat}：平视镜头离人只有 {dist:F2} 米（要 ≥ 1.5）");
                // 脸：从正前方 1.1 米、眼睛那么高贴近拍，头顶正好在画面上沿（不留空：以前这样框着，脸就被裁掉）
                if (k % 4 == 0)
                {
                    var head = anim.GetBoneTransform(HumanBodyBones.Head);
                    Vector3 f = ((Component)folk).transform.forward;
                    Vector3 eye = head.position + f * 1.1f + Vector3.down * 0.15f;
                    faceCam.transform.position = eye;
                    // 镜头往下压到头顶正好在画面最上沿（只留 3%）：仰角 = 头顶的仰角 - 半个视角 × 0.94
                    Vector3 top = head.position + Vector3.up * 0.14f;
                    Vector3 to = top - eye;
                    float elev = Mathf.Atan2(to.y, new Vector2(to.x, to.z).magnitude) * Mathf.Rad2Deg - faceCam.fieldOfView * 0.5f * 0.94f;
                    faceCam.transform.rotation = Quaternion.Euler(-elev, Quaternion.LookRotation(new Vector3(-f.x, 0, -f.z)).eulerAngles.y, 0);
                    Shot($"{k:00}_face_{seat}", faceCam);
                    // 脸那一块（头骨往前 6 厘米、往上 4 厘米投到画面上）周围 5×5 像素的平均颜色：皮肤是亮的（R 150 以上），空脸是深棕色
                    Vector3 vp = faceCam.WorldToViewportPoint(head.position + f * 0.06f + Vector3.up * 0.04f);
                    float r = 0, g = 0, b = 0; int cnt = 0;
                    for (int dy = -6; dy <= 6; dy += 3)
                        for (int dx = -6; dx <= 6; dx += 3)
                        {
                            var c = tex.GetPixel(Mathf.RoundToInt(vp.x * tex.width) + dx, Mathf.RoundToInt(vp.y * tex.height) + dy);
                            r += c.r; g += c.g; b += c.b; cnt++;
                        }
                    r /= cnt; g /= cnt; b /= cnt;
                    Log($"  蒲团 {seat} 的脸（画面 {vp.x:F2},{vp.y:F2}）平均颜色 {r * 255:F0},{g * 255:F0},{b * 255:F0}");
                    Expect(vp.y > 0.5f && vp.y < 1f, $"蒲团 {seat}：脸不在贴近拍的画面上半（{vp.y:F2}）");
                    Expect(r > 0.42f, $"蒲团 {seat}：贴近拍的脸是一块深色（R {r * 255:F0}），脸没画出来");
                }
                n0 = sent.Count;
                Cmd("{\"cmd\":\"stand\"}");
                yield return Wait("arrived", 12f, n0);
                yield return new WaitForSeconds(0.4f);
            }
            UnityEngine.Object.Destroy(faceCam.gameObject);
            Log($"对不上的 {wrong.Count} 处：{string.Join("；", wrong)}");
            Assert.IsEmpty(wrong, string.Join("；", wrong));
        }
        finally { End(); }
    }

    /// 2、3. 坐下起身跳不跳，台阶上脚插进去多深
    [UnityTest, Timeout(1200000)]
    public IEnumerator SitAndStairs()
    {
        yield return Begin("motion");
        try
        {
            Time.captureFramerate = 30;
            Cmd("{\"cmd\":\"view\",\"kind\":\"level\"}");
            // ── 坐下、起身：院子里 13 号、殿里 62 号 ──
            foreach (int seat in new[] { 13, 62 })
            {
                if (seat >= 60)
                {
                    int g0 = sent.Count;
                    Cmd("{\"cmd\":\"goto\",\"spot\":\"inhall\"}");
                    yield return Wait("arrived", 50f, g0, r => r.spot == "inhall");
                }
                Vector3 stand = Call<Vector3>(gd, "SeatStand", seat);
                Vector3 fwd = Call<Vector3>(gd, "SeatFwd", seat);
                Vector3 lane = Call<Vector3>(gd, "SeatLane", seat);
                // 从走道上背对着蒲团的方向过来（坐下前要掉头，最容易拧）
                Vector3 p = lane + Vector3.Cross(Vector3.up, fwd) * 0.9f;
                p.y = lane.y + 0.03f;
                Teleport(p, Quaternion.LookRotation(Vector3.Cross(Vector3.up, fwd)).eulerAngles.y);
                yield return new WaitForSeconds(0.8f);
                ResetMeasure();
                int n0 = sent.Count;
                Cmd($"{{\"cmd\":\"sit\",\"seat\":{seat}}}");
                yield return Wait("seated", 20f, n0, r => r.seat == seat);
                yield return new WaitForSeconds(4f);
                Log($"坐下 {seat}：髋一帧最多挪 {maxJump:F3} 米（{jumpAt}），身子一帧最多转 {maxTurn:F1} 度（{turnAt}）");
                Expect(maxJump < 0.08f, $"坐下 {seat}：髋一帧里蹿了 {maxJump:F3} 米（{jumpAt}）");
                Expect(maxTurn < 25f, $"坐下 {seat}：身子一帧里拧了 {maxTurn:F1} 度（{turnAt}）");
                ResetMeasure();
                n0 = sent.Count;
                Cmd("{\"cmd\":\"stand\"}");
                yield return Wait("arrived", 12f, n0);
                yield return new WaitForSeconds(1.5f);
                Log($"起身 {seat}：髋一帧最多挪 {maxJump:F3} 米（{jumpAt}），身子一帧最多转 {maxTurn:F1} 度（{turnAt}）");
                Expect(maxJump < 0.08f, $"起身 {seat}：髋一帧里蹿了 {maxJump:F3} 米（{jumpAt}）");
            }

            // ── 台阶：「出殿」（自动走下台阶）、从石台「进殿」（自动走上去）、摇杆推着上下 ──
            measureFeet = true;
            {
                ResetMeasure();
                int n0 = sent.Count;
                Cmd("{\"cmd\":\"goto\",\"spot\":\"hall\"}");
                yield return Wait("arrived", 40f, n0, r => r.spot == "hall");
                Log($"出殿下台阶（自动走）：脚底最深插进台阶 {maxDepth:F3} 米（{depthAt}），原点一帧最多上下 {maxRootStep:F3} 米");
                Expect(maxDepth < 0.05f, $"出殿下台阶：脚插进台阶 {maxDepth:F3} 米（{depthAt}）");
                Expect(maxRootStep < 0.06f, $"出殿下台阶：原点一帧蹿了 {maxRootStep:F3} 米");
                Teleport(new Vector3(0, 0.08f, 7.6f), 0f);
                yield return new WaitForSeconds(0.8f);
                ResetMeasure();
                n0 = sent.Count;
                Cmd("{\"cmd\":\"goto\",\"spot\":\"inhall\"}");
                // 走到台阶上一半时从侧面拍一张
                var side = new GameObject("SideCam").AddComponent<Camera>();
                side.enabled = false;
                side.CopyFrom(cam);
                side.fieldOfView = 30f;
                bool shot = false;
                for (float t = 0; t < 40f; t += Time.deltaTime)
                {
                    if (!shot && player.transform.position.z > 10.0f)
                    {
                        shot = true;
                        Vector3 me = player.transform.position;
                        side.transform.position = me + new Vector3(3.2f, 0.4f, 0f);
                        side.transform.rotation = Quaternion.LookRotation(me + Vector3.up * 0.45f - side.transform.position);
                        Shot("stairs_up_side", side);
                    }
                    if (Since("arrived", "inhall", n0)) break;
                    yield return null;
                }
                Log($"进殿上台阶（自动走）：脚底最深插进台阶 {maxDepth:F3} 米（{depthAt}），原点一帧最多上下 {maxRootStep:F3} 米");
                Expect(maxDepth < 0.05f, $"进殿上台阶：脚插进台阶 {maxDepth:F3} 米（{depthAt}）");
                Expect(maxRootStep < 0.06f, $"进殿上台阶：原点一帧蹿了 {maxRootStep:F3} 米");
                // 摇杆：台阶下往北推上去，再往南推下来（胶囊一级级跳，画出来的身子按斜坡走）
                Teleport(new Vector3(0.4f, 0.08f, 8.4f), 0f);
                yield return new WaitForSeconds(0.6f);
                ResetMeasure();
                bool shot2 = false;
                for (float t = 0; t < 4.5f; t += Time.deltaTime)
                {
                    float yaw = (Get<bool>(gd, "stickHeld") ? Get<float>(gd, "stickYaw") : Get<float>(Get<object>(gd, "cam"), "Yaw")) * Mathf.Deg2Rad;
                    Cmd($"{{\"cmd\":\"move\",\"x\":{(-Mathf.Sin(yaw)).ToString(System.Globalization.CultureInfo.InvariantCulture)},\"y\":{Mathf.Cos(yaw).ToString(System.Globalization.CultureInfo.InvariantCulture)}}}");
                    if (!shot2 && player.transform.position.z > 10.0f)
                    {
                        shot2 = true;
                        Vector3 me = player.transform.position;
                        side.transform.position = me + new Vector3(3.2f, 0.4f, 0f);
                        side.transform.rotation = Quaternion.LookRotation(me + Vector3.up * 0.45f - side.transform.position);
                        Shot("stairs_stick_side", side);
                    }
                    yield return null;
                }
                Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":0}");
                yield return new WaitForSeconds(0.6f);
                Log($"摇杆上台阶：到 {F(player.transform.position)}，脚底最深插进台阶 {maxDepth:F3} 米（{depthAt}）");
                Expect(player.transform.position.z > 11f, $"摇杆上台阶没上去：{F(player.transform.position)}");
                Expect(maxDepth < 0.05f, $"摇杆上台阶：脚插进台阶 {maxDepth:F3} 米（{depthAt}）");
                UnityEngine.Object.Destroy(side.gameObject);
            }
            measureFeet = false;
            Log($"对不上的 {wrong.Count} 处：{string.Join("；", wrong)}");
            Assert.IsEmpty(wrong, string.Join("；", wrong));
        }
        finally
        {
            Time.captureFramerate = 0;
            End();
        }
    }

    bool Since(string type, string spot, int since)
    {
        for (int i = sent.Count - 1; i >= since; i--)
        {
            var r = JsonUtility.FromJson<Reply>(sent[i]);
            if (r.type == type && r.spot == spot) return true;
        }
        return false;
    }
}

/// 每帧画完以后量（排在所有 LateUpdate 之后：镜头、Folk 摆姿势、IK、甩头发都做完了，就是这一帧画出来的样子）
[DefaultExecutionOrder(32000)]
public class HallSeatLateProbe : MonoBehaviour
{
    public Action tick;
    void LateUpdate() => tick?.Invoke();
}
