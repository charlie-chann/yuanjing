using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 走路、动作的逐帧记录（评审的测试改来的）：每一段把骨骼位置逐帧写成 CSV（tools/mocap/motion_check.py 读它量脚滑、脚掌俯仰、
/// 两脚都踩着时转了多少、两人最近距离……），再拍大一点的逐帧图。
/// 输出目录 unity/shots/motioncheck（YJ_MC_OUT 可改）；YJ_MC_ONLY="feet,start" 只跑几段；YJ_MC_FPS=30 按 30 帧跑
public class MotionCheckTest
{
    static readonly string OUT = Environment.GetEnvironmentVariable("YJ_MC_OUT") ?? Path.GetFullPath(Path.Combine(Application.dataPath, "../../shots/motioncheck"));
    GameObject bridge, playerRoot;
    Component folk;
    Animator anim;
    Camera cam;
    RenderTexture rt;
    Texture2D frame;
    const int W = 300, H = 400, COLS = 6;
    static readonly CultureInfo IC = CultureInfo.InvariantCulture;
    static string F(float v) => v.ToString("F3", IC);
    static string V(Vector3 v) => $"{F(v.x)},{F(v.y)},{F(v.z)}";
    readonly StringBuilder log = new StringBuilder();
    void Log(string s) { log.AppendLine(s); Debug.Log("[yuanjing] 逐帧 " + s); }

    void Cmd(string json) => bridge.SendMessage("OnMessage", json);
    void Stick(Vector3 world)
    {
        if (world.sqrMagnitude < 1e-6f) { Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":0}"); return; }
        float yaw = Camera.main != null ? Camera.main.transform.eulerAngles.y : 0;
        Vector3 s = Quaternion.Euler(0, -yaw, 0) * world;
        Cmd($"{{\"cmd\":\"move\",\"x\":{s.x.ToString(IC)},\"y\":{s.z.ToString(IC)}}}");
    }
    object PoseE(string n) => Enum.Parse(Type.GetType("Yuanjing.Folk+Pose, Assembly-CSharp"), n);
    static void Call(Component f, string m, params object[] a)
    {
        foreach (var mi in f.GetType().GetMethods())
            if (mi.Name == m && mi.GetParameters().Length == a.Length) { mi.Invoke(f, a); return; }
        throw new Exception("没有方法 " + m);
    }
    static bool Done(Component f) => (bool)f.GetType().GetProperty("OneShotDone").GetValue(f);
    static string ActNow(Component f) => f.GetType().GetField("actNow", BindingFlags.NonPublic | BindingFlags.Instance).GetValue(f) as string;
    static string PoseOf(Component f) => f.GetType().GetProperty("pose").GetValue(f).ToString();
    static string Loco(Component f) => f.GetType().GetMethod("DebugLoco")?.Invoke(f, null) as string;

    static readonly HumanBodyBones[] Bones = {
        HumanBodyBones.Hips, HumanBodyBones.Spine, HumanBodyBones.Chest, HumanBodyBones.Neck, HumanBodyBones.Head,
        HumanBodyBones.LeftUpperLeg, HumanBodyBones.LeftLowerLeg, HumanBodyBones.LeftFoot, HumanBodyBones.LeftToes,
        HumanBodyBones.RightUpperLeg, HumanBodyBones.RightLowerLeg, HumanBodyBones.RightFoot, HumanBodyBones.RightToes,
        HumanBodyBones.LeftUpperArm, HumanBodyBones.LeftLowerArm, HumanBodyBones.LeftHand,
        HumanBodyBones.RightUpperArm, HumanBodyBones.RightLowerArm, HumanBodyBones.RightHand };

    class Rec
    {
        public StringBuilder csv = new StringBuilder();
        public Texture2D strip; public int shots, n;
        // 判定用：每帧的时刻、根、两脚踝和脚趾、朝向（度）
        public readonly List<float> t = new List<float>(), yaw = new List<float>();
        public readonly List<Vector3> root = new List<Vector3>(), la = new List<Vector3>(), lt = new List<Vector3>(), ra = new List<Vector3>(), rt = new List<Vector3>();
        public readonly List<Vector3> lh = new List<Vector3>(), rh = new List<Vector3>();
        public readonly List<string> loco = new List<string>();
        public Vector3 target; public bool hasTarget; public float walkSpeed = 1f;
    }

    static readonly System.Text.RegularExpressions.Regex LocoRx = new System.Text.RegularExpressions.Regex(@"^(\w+) 相位 ([\d.]+) 速度 ([\d.]+) 实际 ([\d.]+) 播放 ([\d.]+)");
    /// DebugLoco 里的状态、速度、播放快慢
    static bool ParseLoco(string s, out string state, out float speed, out float rate)
    {
        state = ""; speed = rate = 0;
        var m = LocoRx.Match(s ?? "");
        if (!m.Success) return false;
        state = m.Groups[1].Value;
        speed = float.Parse(m.Groups[3].Value, IC);
        rate = float.Parse(m.Groups[5].Value, IC);
        return true;
    }

    /// 快到终点（最后 3 米、还在迈步时）：速度最大、播放最快、速度忽快忽慢来回了几次（0.02 米/秒以内的不算）
    static void ArriveStats(Rec r, out float maxV, out float maxRate, out int rev, out string trace)
    {
        maxV = 0; maxRate = 0; rev = 0;
        float ext = float.NaN; int dir = 0;
        var sb = new StringBuilder();
        float nextT = 0;
        for (int i = 0; i < r.t.Count; i++)
        {
            if (!ParseLoco(r.loco[i], out var st, out var v, out var rate) || st != "Move") continue;
            Vector3 d = r.target - r.root[i]; d.y = 0;
            if (d.magnitude > 3f) continue;
            if (r.t[i] >= nextT) { nextT = r.t[i] + 0.2f; sb.Append($" {F(d.magnitude)}:{v:F2}/{rate:F2}"); }
            maxV = Mathf.Max(maxV, v); maxRate = Mathf.Max(maxRate, rate);
            if (float.IsNaN(ext)) { ext = v; continue; }
            if (dir >= 0 && v < ext - 0.02f) { if (dir > 0) rev++; dir = -1; ext = v; }
            else if (dir <= 0 && v > ext + 0.02f) { if (dir < 0) rev++; dir = 1; ext = v; }
            else if ((dir > 0 && v > ext) || (dir < 0 && v < ext)) ext = v;
        }
        trace = sb.ToString();
    }

    /// 一帧里的「跳」：相对根的位置和前后两帧平均的差（米），取 [t0, t1] 里最大的
    static float Spike(Rec r, List<Vector3> P, float t0, float t1, out float at)
    {
        float m = 0; at = -1;
        for (int i = 1; i + 1 < r.t.Count; i++)
        {
            if (r.t[i] < t0 || r.t[i] > t1) continue;
            Vector3 a = P[i - 1] - r.root[i - 1], b = P[i] - r.root[i], c = P[i + 1] - r.root[i + 1];
            float d = (b - 0.5f * (a + c)).magnitude;
            if (d > m) { m = d; at = r.t[i]; }
        }
        return m;
    }

    /// 某状态下两脚（踝、脚趾）最低的高度（相对根）
    static void LowFeet(Rec r, string state, float t0, float t1, out float ankle, out float toe)
    {
        ankle = toe = 9;
        for (int i = 0; i < r.t.Count; i++)
        {
            if (r.t[i] < t0 || r.t[i] > t1) continue;
            if (!ParseLoco(r.loco[i], out var st, out _, out _) || st != state) continue;
            ankle = Mathf.Min(ankle, Mathf.Min(r.la[i].y, r.ra[i].y) - r.root[i].y);
            toe = Mathf.Min(toe, Mathf.Min(r.lt[i].y, r.rt[i].y) - r.root[i].y);
        }
    }

    /// 踩在地上的一只脚，一次着地里脚掌（踝→脚趾）水平方向转了多少度，取最大
    static float PlantedYaw(Rec r, float t0, float t1)
    {
        float worst = 0;
        foreach (bool left in new[] { true, false })
        {
            var A = left ? r.la : r.ra; var T = left ? r.lt : r.rt;
            float amin = 9;
            for (int i = 0; i < r.t.Count; i++) if (r.t[i] >= t0 && r.t[i] <= t1) amin = Mathf.Min(amin, A[i].y - r.root[i].y);
            bool on = false; float y0 = 0, lo = 0, hi = 0;
            for (int i = 1; i < r.t.Count; i++)
            {
                if (r.t[i] < t0 || r.t[i] > t1) continue;
                Vector3 d = A[i] - A[i - 1]; d.y = 0;
                float sp = d.magnitude / Mathf.Max(1e-4f, r.t[i] - r.t[i - 1]);
                bool down = A[i].y - r.root[i].y < amin + 0.02f && sp < 0.3f;
                Vector3 f = T[i] - A[i];
                float yaw = Mathf.Atan2(f.x, f.z) * Mathf.Rad2Deg;
                if (down && !on) { on = true; y0 = yaw; lo = hi = 0; }
                else if (down)
                {
                    float rel = Mathf.DeltaAngle(y0, yaw);
                    lo = Mathf.Min(lo, rel); hi = Mathf.Max(hi, rel);
                    worst = Mathf.Max(worst, hi - lo);
                }
                else on = false;
            }
        }
        return worst;
    }

    /// 起步那一下（从 t0 起 0.35 秒）：支撑脚（一直贴地的那只）在地上挪了多远、根往旁边挪得最快多快、迈出去的脚往后退了多少
    static void StartStats(Rec r, float t0, out float stanceSlide, out float latV, out float swingBack)
    {
        stanceSlide = 9; latV = 0; swingBack = 0;
        int i0 = r.t.FindIndex(x => x >= t0);
        if (i0 < 1) return;
        Vector3 f = new Vector3(Mathf.Sin(r.yaw[i0] * Mathf.Deg2Rad), 0, Mathf.Cos(r.yaw[i0] * Mathf.Deg2Rad)), rt = new Vector3(f.z, 0, -f.x);
        foreach (bool left in new[] { true, false })
        {
            var A = left ? r.la : r.ra;
            float m = 0, back = 0; bool low = true;
            for (int i = i0; i < r.t.Count && r.t[i] <= t0 + 0.35f; i++)
            {
                if (A[i].y - r.root[i].y > A[i0].y - r.root[i0].y + 0.015f) low = false;
                Vector3 d = A[i] - A[i0]; d.y = 0;
                m = Mathf.Max(m, d.magnitude);
                back = Mathf.Max(back, -Vector3.Dot(d, f));
            }
            if (low) stanceSlide = Mathf.Min(stanceSlide, m); else swingBack = Mathf.Max(swingBack, back);
        }
        for (int i = i0 + 1; i < r.t.Count && r.t[i] <= t0 + 0.35f; i++)
            latV = Mathf.Max(latV, Mathf.Abs(Vector3.Dot(r.root[i] - r.root[i - 1], rt)) / Mathf.Max(1e-4f, r.t[i] - r.t[i - 1]));
    }

    /// 停步站稳前后，两只脚在地上挪了多远（米）：从 Stop→Idle 前 0.25 秒到之后 0.6 秒
    static float StopSettleDrift(Rec r, out float at)
    {
        at = -1;
        for (int i = 1; i < r.t.Count; i++)
        {
            ParseLoco(r.loco[i - 1], out var s0, out _, out _);
            ParseLoco(r.loco[i], out var s1, out _, out _);
            if (s0 == "Stop" && s1 == "Idle") { at = r.t[i]; break; }
        }
        if (at < 0) return -1;
        float w0 = at - 0.25f;
        int i0 = r.t.FindIndex(x => x >= w0);
        float m = 0;
        for (int i = i0; i < r.t.Count && r.t[i] <= at + 0.6f; i++)
        {
            Vector3 a = r.la[i] - r.la[i0], b = r.ra[i] - r.ra[i0]; a.y = b.y = 0;
            m = Mathf.Max(m, Mathf.Max(a.magnitude, b.magnitude));
        }
        return m;
    }

    /// 脚掌踩稳时（踝贴地、几乎不动）踝→脚趾的俯仰（度，往下为负），取中位数
    static float FootPitch(Rec r, bool left, float t0, float t1)
    {
        var A = left ? r.la : r.ra; var T = left ? r.lt : r.rt;
        float amin = 9;
        for (int i = 0; i < r.t.Count; i++) if (r.t[i] >= t0 && r.t[i] <= t1) amin = Mathf.Min(amin, A[i].y - r.root[i].y);
        var v = new List<float>();
        for (int i = 1; i < r.t.Count; i++)
        {
            if (r.t[i] < t0 || r.t[i] > t1) continue;
            Vector3 d = A[i] - A[i - 1]; d.y = 0;
            float sp = d.magnitude / Mathf.Max(1e-4f, r.t[i] - r.t[i - 1]);
            if (A[i].y - r.root[i].y < amin + 0.015f && sp < 0.15f)
            {
                Vector3 f = T[i] - A[i];
                v.Add(Mathf.Atan2(f.y, new Vector2(f.x, f.z).magnitude) * Mathf.Rad2Deg);
            }
        }
        if (v.Count == 0) return float.NaN;
        v.Sort();
        return v[v.Count / 2];
    }

    /// 朝向转得最快的那一下（度/秒）
    static float MaxYawRate(Rec r, float t0, float t1)
    {
        float m = 0;
        for (int i = 1; i < r.t.Count; i++)
            if (r.t[i] >= t0 && r.t[i] <= t1) m = Mathf.Max(m, Mathf.Abs(Mathf.DeltaAngle(r.yaw[i - 1], r.yaw[i])) / Mathf.Max(1e-4f, r.t[i] - r.t[i - 1]));
        return m;
    }

    readonly Dictionary<string, Rec> recs = new Dictionary<string, Rec>();
    float minCross = -1;
    readonly List<string> fails = new List<string>();
    void Check(bool ok, string what) { Log((ok ? "通过 " : "没过 ") + what); if (!ok) fails.Add(what); }

    Rec NewRec(int n)
    {
        var r = new Rec { n = n };
        var hdr = new StringBuilder("t,root_x,root_y,root_z,fwd_x,fwd_z");
        foreach (var b in Bones) hdr.Append($",{b}_x,{b}_y,{b}_z");
        hdr.Append(",pose,act,done,loco");
        r.csv.AppendLine(hdr.ToString());
        if (n > 0) r.strip = new Texture2D(W * Mathf.Min(n, COLS), H * ((n + COLS - 1) / COLS), TextureFormat.RGB24, false);
        return r;
    }

    void Sample(Rec r, float t, Transform root, Animator a, Component f)
    {
        var sb = new StringBuilder();
        Vector3 fw = a.transform.forward;
        sb.Append($"{F(t)},{V(root.position)},{F(fw.x)},{F(fw.z)}");
        foreach (var b in Bones) { var tr = a.GetBoneTransform(b); sb.Append("," + (tr != null ? V(tr.position) : "nan,nan,nan")); }
        sb.Append($",{PoseOf(f)},{ActNow(f) ?? "-"},{Done(f)},\"{Loco(f)}\"");
        r.csv.AppendLine(sb.ToString());
        r.t.Add(t); r.root.Add(root.position); r.yaw.Add(a.transform.eulerAngles.y);
        r.la.Add(a.GetBoneTransform(HumanBodyBones.LeftFoot).position); r.lt.Add(a.GetBoneTransform(HumanBodyBones.LeftToes).position);
        r.ra.Add(a.GetBoneTransform(HumanBodyBones.RightFoot).position); r.rt.Add(a.GetBoneTransform(HumanBodyBones.RightToes).position);
        r.lh.Add(a.GetBoneTransform(HumanBodyBones.LeftHand).position); r.rh.Add(a.GetBoneTransform(HumanBodyBones.RightHand).position);
        r.loco.Add(Loco(f));
    }

    void Shoot(Rec r, Vector3 at, Vector3 dir, float dist, float camH, float lookH, string label)
    {
        if (r.strip == null || r.shots >= r.n) return;
        cam.transform.position = at + dir.normalized * dist + Vector3.up * camH;
        cam.transform.LookAt(at + Vector3.up * lookH);
        cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
        RenderTexture.active = rt; frame.ReadPixels(new Rect(0, 0, W, H), 0, 0); frame.Apply(); RenderTexture.active = null;
        int col = r.shots % COLS, row = r.shots / COLS;
        int rows = (r.n + COLS - 1) / COLS;
        r.strip.SetPixels(col * W, (rows - 1 - row) * H, W, H, frame.GetPixels());
        r.shots++;
    }

    void Save(Rec r, string name)
    {
        recs[name] = r;
        File.WriteAllText($"{OUT}/{name}.csv", r.csv.ToString());
        if (r.strip != null) { r.strip.Apply(); File.WriteAllBytes($"{OUT}/{name}.png", r.strip.EncodeToPNG()); }
    }

    void Place(Vector3 p, float yaw)
    {
        var cc = playerRoot.GetComponent<CharacterController>();
        cc.enabled = false;
        playerRoot.transform.position = p;
        folk.transform.rotation = Quaternion.Euler(0, yaw, 0);
        Call(folk, "FaceYaw", yaw);
        cc.enabled = true;
    }

    /// 摇杆驱动的一段：ctl(t) 返回世界方向（乘了大小）；shotAt：拍照时刻；dir/dist/h：相机方位
    IEnumerator Player(string name, Vector3 start, float yaw, float secs, Func<float, Vector3> ctl, float shot0, float shotDt, int n,
        Vector3 dir, float dist = 3.3f, float camH = 0.75f, float lookH = 0.6f, Action<float> extra = null)
    {
        Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":0}");
        yield return new WaitForSeconds(0.3f);
        Place(start, yaw);
        yield return new WaitForSeconds(1.5f);
        var r = NewRec(n);
        float t = 0, next = shot0;
        var steps = new List<float>();
        var ev = folk.GetType().GetEvent("Step");
        Action on = () => steps.Add(t);
        ev.AddEventHandler(folk, on);
        while (t < secs)
        {
            Stick(ctl(t));
            extra?.Invoke(t);
            yield return null;
            t += Time.deltaTime;
            Sample(r, t, playerRoot.transform, anim, folk);
            if (t >= next && r.shots < n) { next += shotDt; Shoot(r, playerRoot.transform.position, dir, dist, camH, lookH, F(t)); }
        }
        ev.RemoveEventHandler(folk, on);
        Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":0}");
        var sb = new StringBuilder();
        foreach (var s in steps) sb.Append(F(s) + " ");
        Log($"{name} 脚步声 {sb}");
        Save(r, name);
    }

    IEnumerator Npc(string name, GameObject look, Vector3 p0, float yaw0, List<Vector3> path, float secs, float shot0, float shotDt, int n, Vector3 dir,
        Action<Component, float, bool> onTick = null, float dist = 3.3f, float camH = 0.75f)
    {
        var npc = UnityEngine.Object.Instantiate(look, p0, Quaternion.Euler(0, yaw0, 0));
        npc.name = "CheckWalker_" + name;
        var nf = npc.GetComponent(Type.GetType("Yuanjing.Folk, Assembly-CSharp"));
        nf.GetType().GetField("walkSpeed").SetValue(nf, 0.85f);
        var na = npc.GetComponentInChildren<Animator>();
        yield return new WaitForSeconds(1f);
        bool arrived = false; float arrT = -1;
        var ev = nf.GetType().GetEvent("Arrived");
        float t = 0;
        Action onArr = () => { if (!arrived) { arrived = true; arrT = t; } };
        ev.AddEventHandler(nf, onArr);
        Call(nf, "Walk", path);
        var r = NewRec(n);
        r.target = path[path.Count - 1]; r.hasTarget = true; r.walkSpeed = 0.85f;
        float next = shot0;
        while (t < secs)
        {
            onTick?.Invoke(nf, t, arrived);
            yield return null;
            t += Time.deltaTime;
            Sample(r, t, npc.transform, na, nf);
            if (t >= next && r.shots < n) { next += shotDt; Shoot(r, npc.transform.position, dir, dist, camH, 0.6f, F(t)); }
        }
        Vector3 err = npc.transform.position - path[path.Count - 1]; err.y = 0;
        Log($"{name}: 到达 {(arrived ? F(arrT) : "没到")} 秒，终点差 {F(err.magnitude)} 米");
        Save(r, name);
        UnityEngine.Object.Destroy(npc);
        yield return null;
    }

    [UnityTest, Timeout(1200000)]
    public IEnumerator Record()
    {
        int fps = int.TryParse(Environment.GetEnvironmentVariable("YJ_MC_FPS"), out var ff) ? ff : 60;
        string only = Environment.GetEnvironmentVariable("YJ_MC_ONLY") ?? "";
        bool Want(string k) => only == "" || only.Contains(k);
        Directory.CreateDirectory(OUT);
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        bridge = GameObject.Find("Bridge");
        Cmd("{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"测试\"}");
        yield return new WaitForSeconds(2f);
        Time.captureFramerate = fps;
        playerRoot = GameObject.Find("Player");
        anim = playerRoot.GetComponentInChildren<Animator>();
        folk = playerRoot.GetComponentInChildren(Type.GetType("Yuanjing.Folk, Assembly-CSharp"));
        foreach (var tr in UnityEngine.Object.FindObjectsByType<Transform>(FindObjectsSortMode.None))
            if (tr.name.StartsWith("Pilgrim_")) tr.gameObject.SetActive(false);
        cam = new GameObject("MotionCheckCam").AddComponent<Camera>();
        cam.fieldOfView = 30;
        cam.nearClipPlane = 0.05f;
        rt = new RenderTexture(W, H, 24) { antiAliasing = 4 };
        frame = new Texture2D(W, H, TextureFormat.RGB24, false);
        var pad = GameObject.CreatePrimitive(PrimitiveType.Plane);
        pad.name = "ground";
        pad.transform.position = new Vector3(70f, 0.3f, 0f);
        pad.transform.localScale = new Vector3(4f, 1f, 4f);
        var checker = new Texture2D(2, 2) { filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Repeat };
        checker.SetPixels(new[] { new Color(0.82f, 0.8f, 0.74f), new Color(0.55f, 0.53f, 0.5f), new Color(0.55f, 0.53f, 0.5f), new Color(0.82f, 0.8f, 0.74f) });
        checker.Apply();
        var sh = Shader.Find("Universal Render Pipeline/Unlit") ?? Shader.Find("Unlit/Texture");
        var mat = new Material(sh) { mainTexture = checker };
        if (mat.HasProperty("_BaseMap")) { mat.SetTexture("_BaseMap", checker); mat.SetTextureScale("_BaseMap", new Vector2(80, 80)); }
        mat.mainTextureScale = new Vector2(80, 80);
        pad.GetComponent<Renderer>().sharedMaterial = mat;
        Vector3 S = new Vector3(70f, 0.32f, 0f);
        Vector3 west = Vector3.left, east = Vector3.right, north = Vector3.forward, south = Vector3.back;
        string sfx = fps == 60 ? "" : "_" + fps;

        if (Want("feet"))
        {
            // 脚的特写：往西走，相机在人右边（北）和左边（南），低机位
            yield return Player("feet_right" + sfx, S, 270, 3.6f, t => west, 2.2f, 0.1f, 12, north, 1.5f, 0.22f, 0.15f);
            yield return Player("feet_left" + sfx, S, 270, 3.6f, t => west, 2.2f, 0.1f, 12, south, 1.5f, 0.22f, 0.15f);
            yield return Player("feet_idle" + sfx, S, 270, 1.0f, t => Vector3.zero, 0.5f, 0.2f, 2, north, 1.5f, 0.22f, 0.15f);
        }
        if (Want("start"))
            yield return Player("p_startstop" + sfx, S, 270, 6.2f, t => t < 0.8f ? Vector3.zero : t < 3.8f ? west : Vector3.zero, 0.8f, 0.1f, 18, south,
                extra: null);
        if (Want("stopz"))
            yield return Player("p_stop" + sfx, S, 270, 6.2f, t => t < 0.8f ? Vector3.zero : t < 3.8f ? west : Vector3.zero, 3.7f, 0.12f, 18, south);
        if (Want("front"))
            yield return Player("p_walkfront" + sfx, S, 270, 3.6f, t => west, 2.0f, 0.1f, 12, (west + south * 0.35f), 3.6f, 0.9f, 0.6f);
        if (Want("back"))
            yield return Player("p_walkback" + sfx, S, 270, 3.6f, t => west, 2.0f, 0.1f, 6, (east + south * 0.2f), 3.6f, 1.2f, 0.6f);
        if (Want("turn90"))
            yield return Player("p_turn90" + sfx, S, 270, 4.6f, t => t < 2.5f ? west : north, 2.3f, 0.1f, 18, (south + east * 0.5f), 3.6f, 1.6f, 0.5f);
        if (Want("turn180"))
            yield return Player("p_turn180" + sfx, S, 270, 5.0f, t => t < 2.5f ? west : east, 2.3f, 0.1f, 18, (south + east * 0.3f), 3.6f, 1.6f, 0.5f);
        if (Want("pivot90"))
            yield return Player("p_pivot90" + sfx, S, 270, 3.4f, t => t < 0.6f ? Vector3.zero : north, 0.6f, 0.1f, 18, (south + west), 3.4f, 1.4f, 0.5f);
        if (Want("pivot180"))
            yield return Player("p_pivot180" + sfx, S, 270, 3.6f, t => t < 0.6f ? Vector3.zero : east, 0.6f, 0.1f, 18, (south + west * 0.3f), 3.4f, 1.4f, 0.5f);
        if (Want("speeds"))
            yield return Player("p_speeds" + sfx, S, 270, 13f, t => west * (t < 3 ? 0.3f : t < 6 ? 0.55f : t < 9 ? 0.8f : t < 12 ? 1f : 0f), 1.5f, 3f, 4, south);
        if (Want("zigzag"))
            yield return Player("p_zigzag" + sfx, S, 270, 5f, t => { int k = (int)(t / 0.6f) % 4; return k == 0 ? west : k == 1 ? (west + north).normalized : k == 2 ? west : (west + south).normalized; }, 1.5f, 0.1f, 18, (south + east * 0.3f), 3.8f, 1.8f, 0.5f);
        if (Want("tap"))
            yield return Player("p_tap" + sfx, S, 270, 5f, t => (t % 0.85f) < 0.35f && t < 3.4f ? west : Vector3.zero, 0.0f, 0.15f, 18, south);

        // ── 主角按路线自动走（GameDirector.Walk：去蒲团、拜垫、香炉、许愿树都是这样走）：快到终点时速度、步频稳不稳 ──
        if (Want("arrive"))
        {
            var gd = UnityEngine.Object.FindFirstObjectByType(Type.GetType("Yuanjing.GameDirector, Assembly-CSharp"));
            var walkM = gd.GetType().GetMethod("Walk", BindingFlags.NonPublic | BindingFlags.Instance, null, new[] { typeof(List<Vector3>), typeof(Vector3), typeof(string), typeof(Action) }, null);
            float ws = (float)folk.GetType().GetField("walkSpeed").GetValue(folk);
            foreach (float dist in new[] { 2.6f, 4.3f, 6.1f })
            {
                Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":0}");
                yield return new WaitForSeconds(0.3f);
                Place(S, 270);
                yield return new WaitForSeconds(1.2f);
                Vector3 start = playerRoot.transform.position, goal = start + west * dist;
                var r = NewRec(dist > 6f ? 18 : 0);
                r.target = goal; r.hasTarget = true; r.walkSpeed = ws;
                bool arrived = false; float arrT = -1, t = 0;
                var ev = folk.GetType().GetEvent("Arrived");
                Action on = () => { if (!arrived) { arrived = true; arrT = t; } };
                ev.AddEventHandler(folk, on);
                walkM.Invoke(gd, new object[] { new List<Vector3> { goal }, goal + west, "", null });
                float next = dist / 1.0f - 2.2f;
                while (t < dist / 0.6f + 2.5f)
                {
                    yield return null; t += Time.deltaTime;
                    Sample(r, t, playerRoot.transform, anim, folk);
                    if (t >= next && r.shots < r.n) { next += 0.15f; Shoot(r, playerRoot.transform.position, south, 3.3f, 0.75f, 0.6f, ""); }
                }
                ev.RemoveEventHandler(folk, on);
                Vector3 e = playerRoot.transform.position - goal; e.y = 0;
                ArriveStats(r, out float mv, out float mr, out int rev, out string tr);
                Log($"arrive_{dist:F1}: 到达 {(arrived ? F(arrT) : "没到")} 终点差 {F(e.magnitude)}；最后 3 米 速度最大 {F(mv)}（walkSpeed {F(ws)}）播放最快 {F(mr)} 快慢来回 {rev} 次；剩余:速度/播放{tr}");
                Check(arrived && e.magnitude < 0.06f, $"arrive_{dist:F1} 到了、离终点不到 6 厘米：{F(e.magnitude)}");
                Check(mv <= ws * 1.05f + 0.011f && mr <= 1.2f && rev <= 1, $"arrive_{dist:F1} 最后 3 米速度不超过 1.05 倍、播放不超过 1.2 倍、快慢最多变一次向：{F(mv)} {F(mr)} {rev}");
                Save(r, $"arrive_{dist:F1}" + sfx);
                yield return new WaitForSeconds(0.5f);
            }
        }

        // ── 挂布条：SetPose(Hang) → 3.5 秒 ReleaseHang ──
        if (Want("hang"))
        {
            Place(S, 0); yield return new WaitForSeconds(1.5f);
            var r = NewRec(24);
            float t = 0, next = 0; bool released = false; int shot = 0;
            Call(folk, "SetPose", PoseE("Hang"));
            string tl = "";
            string lastAct = "";
            while (t < 6.5f)
            {
                if (!released && t >= 3.5f) { released = true; Call(folk, "ReleaseHang"); tl += $" [{F(t)} ReleaseHang done={Done(folk)} act={ActNow(folk)}]"; }
                yield return null; t += Time.deltaTime;
                Sample(r, t, playerRoot.transform, anim, folk);
                string a = ActNow(folk) ?? "-";
                if (a != lastAct) { tl += $" [{F(t)} act={a} pose={PoseOf(folk)} done={Done(folk)}]"; lastAct = a; }
                if (t >= next && shot < 24) { next += 0.27f; Shoot(r, playerRoot.transform.position, shot % 2 == 0 ? east : (north + east * 0.6f), 3.0f, 0.8f, 0.65f, ""); shot++; }
            }
            Log("hang 时间线" + tl);
            Save(r, "hang" + sfx);
        }
        // ── 上香：和 GameDirector.HallIncense 一样的节奏 ──
        if (Want("incense"))
        {
            Place(S, 0); yield return new WaitForSeconds(1.5f);
            var r = NewRec(24);
            float t = 0, next = 0; int shot = 0;
            string tl = ""; string lastAct = "";
            Call(folk, "SetPose", PoseE("Incense"));
            float phaseT = 0;
            // 0.8 秒后拜三下（0.9 下 + 0.45 停 + 0.9 起 + 0.25）×3 = 7.5 秒，然后 PlayOnce
            bool played = false; float playT = -1; bool none = false; float doneT = -1;
            while (t < 16f)
            {
                float u = t - 0.8f;
                if (u >= 0 && u < 7.5f)
                {
                    float c = u % 2.5f;
                    float b = c < 0.9f ? c / 0.9f * 0.8f : c < 1.35f ? 0.8f : c < 2.25f ? 0.8f * (1 - (c - 1.35f) / 0.9f) : 0f;
                    Call(folk, "SetBow", b);
                }
                else if (u >= 7.5f && !played) { Call(folk, "SetBow", 0f); played = true; playT = t; Call(folk, "PlayOnce", "Incense_Plant"); tl += $" [{F(t)} PlayOnce done={Done(folk)}]"; }
                if (played && doneT < 0 && Done(folk)) { doneT = t; tl += $" [{F(t)} OneShotDone pose={PoseOf(folk)} act={ActNow(folk)}]"; }
                if (doneT > 0 && !none && t > doneT + 0.8f) { none = true; Call(folk, "SetPose", PoseE("None")); tl += $" [{F(t)} SetPose(None)]"; }
                yield return null; t += Time.deltaTime;
                Sample(r, t, playerRoot.transform, anim, folk);
                string a = ActNow(folk) ?? "-";
                if (a != lastAct) { tl += $" [{F(t)} act={a} pose={PoseOf(folk)} done={Done(folk)}]"; lastAct = a; }
                if (played && Mathf.Abs(t - playT - 1.5f) < 0.5f * Time.deltaTime + 1e-4f) tl += $" [plant@{F(t)}]";
                // 拍：0..2.4 举香；拜到底一张；PlayOnce 之后每 0.3 秒
                bool want = (t < 2.6f && t >= next) || (played && t >= next);
                if (!played && t > 2.6f && next < 30f) next = 1e9f;
                if (played && next > 1e8f) next = t;
                if (want && shot < 24) { next = t + (played ? 0.3f : 0.4f); Shoot(r, playerRoot.transform.position, shot % 2 == 0 ? east : (north + east * 0.6f), 3.0f, 0.8f, 0.65f, ""); shot++; }
            }
            Log("incense 时间线" + tl + $" playT={F(playT)}");
            Save(r, "incense" + sfx);
        }
        // ── 系布条时推摇杆走开（HandOffToArms）──
        if (Want("hangwalk"))
            yield return Player("hang_walkaway" + sfx, S, 0, 5f, t => t < 2.6f ? Vector3.zero : west, 1.8f, 0.15f, 18, south,
                extra: t => { if (t < 0.02f) Call(folk, "SetPose", PoseE("Hang")); });
        // ── 边界：Hang_In 还没播完就 ReleaseHang ──
        if (Want("edge"))
        {
            Place(S, 0); yield return new WaitForSeconds(1.5f);
            Call(folk, "SetPose", PoseE("Hang"));
            float t = 0; string tl = ""; string lastAct = ""; bool rel = false; bool lastDone = Done(folk);
            while (t < 5f)
            {
                if (!rel && t > 0.6f) { rel = true; Call(folk, "ReleaseHang"); tl += $" [{F(t)} ReleaseHang done={Done(folk)} act={ActNow(folk)} pose={PoseOf(folk)}]"; }
                yield return null; t += Time.deltaTime;
                string a = ActNow(folk) ?? "-";
                if (a != lastAct || Done(folk) != lastDone) { tl += $" [{F(t)} act={a} pose={PoseOf(folk)} done={Done(folk)}]"; lastAct = a; lastDone = Done(folk); }
            }
            Log("边界 早松手" + tl);
            // PlayOnce 在普通站姿下
            yield return new WaitForSeconds(1f);
            t = 0; tl = ""; lastAct = "";
            Call(folk, "PlayOnce", "Incense_Plant");
            tl += $" [0 PlayOnce(Incense_Plant) pose=None done={Done(folk)} act={ActNow(folk)}]";
            while (t < 5f) { yield return null; t += Time.deltaTime; string a = ActNow(folk) ?? "-"; if (a != lastAct || Done(folk) != lastDone) { tl += $" [{F(t)} act={a} pose={PoseOf(folk)} done={Done(folk)}]"; lastAct = a; lastDone = Done(folk); } }
            Log("边界 站姿 PlayOnce" + tl);
            // Incense → 立刻 PlayOnce（Incense_In 还没播完）
            yield return new WaitForSeconds(1f);
            Call(folk, "SetPose", PoseE("Incense"));
            yield return new WaitForSeconds(0.4f);
            t = 0; tl = ""; lastAct = "";
            Call(folk, "PlayOnce", "Incense_Plant");
            tl += $" [0 PlayOnce during Incense_In done={Done(folk)} act={ActNow(folk)}]";
            while (t < 5f) { yield return null; t += Time.deltaTime; string a = ActNow(folk) ?? "-"; if (a != lastAct || Done(folk) != lastDone) { tl += $" [{F(t)} act={a} pose={PoseOf(folk)} done={Done(folk)}]"; lastAct = a; lastDone = Done(folk); } }
            Log("边界 举香中 PlayOnce" + tl);
            Call(folk, "SetPose", PoseE("None"));
            yield return new WaitForSeconds(2f);
            // Incense → None（没插香）
            Call(folk, "SetPose", PoseE("Incense"));
            yield return new WaitForSeconds(2.2f);
            t = 0; tl = ""; lastAct = "";
            Call(folk, "SetPose", PoseE("None"));
            while (t < 2.5f) { yield return null; t += Time.deltaTime; string a = ActNow(folk) ?? "-"; if (a != lastAct) { tl += $" [{F(t)} act={a} pose={PoseOf(folk)}]"; lastAct = a; } }
            Log("边界 举香后放下" + tl);
            // PlayOnce 不存在的名字
            Call(folk, "PlayOnce", "NoSuchClip");
            Log($"边界 PlayOnce(NoSuchClip) done={Done(folk)}");
            yield return new WaitForSeconds(1f);
        }
        // ── 香客 ──
        if (Want("npc"))
        {
            var pil = UnityEngine.Object.FindFirstObjectByType(Type.GetType("Yuanjing.Pilgrims, Assembly-CSharp")) as Behaviour;
            var looks = (GameObject[])pil.GetType().GetField("looks").GetValue(pil);
            pil.enabled = false;
            GameObject male = null, female = null;
            for (int i = 1; i < looks.Length; i++)
            {
                var fc = looks[i].GetComponent(Type.GetType("Yuanjing.Folk, Assembly-CSharp"));
                var g = (AnimationClip[])fc.GetType().GetField("gaitClips").GetValue(fc);
                if (g == null || g.Length == 0) continue;
                if (male == null && g[0].name.StartsWith("Walk_M")) male = looks[i];
                if (female == null && g[0].name.StartsWith("Walk_F")) female = looks[i];
            }
            Log($"香客样子 男 {male?.name} 女 {female?.name}");
            // 到了以后转 135 度、马上鞠躬（Pilgrims 的做法）
            Vector3 p0 = S + new Vector3(3f, 0, -4f);
            float ta = -1;
            yield return Npc("npc_arrive_bow", female, p0, 270, new List<Vector3> { p0 + new Vector3(-3f, 0, 0) }, 9f, 3.4f, 0.25f, 18, south,
                (f, t, arr) =>
                {
                    if (arr && ta < 0) { ta = t; Call(f, "FaceTowards", f.transform.position + new Vector3(1, 0, 1)); Call(f, "SetPose", PoseE("Bow")); Log($"npc_arrive_bow 到达并鞠躬 {F(t)}"); }
                    if (ta >= 0)
                    {
                        float u = t - ta;
                        Call(f, "SetBow", u < 1.2f ? u / 1.2f : u < 2f ? 1f : Mathf.Max(0, 1f - (u - 2f) / 1.2f));
                    }
                });
            // 走 2.5 米停下、站着（停步时脚的高度、站住以后脚滑不滑）
            Vector3 p1 = S + new Vector3(2f, 0, -2f);
            yield return Npc("npc_stop_f", female, p1, 270, new List<Vector3> { p1 + new Vector3(-2.5f, 0, 0) }, 6.5f, 2.6f, 0.2f, 18, south);
            yield return Npc("npc_stop_m", male, p1, 270, new List<Vector3> { p1 + new Vector3(-2.5f, 0, 0) }, 6.5f, 2.6f, 0.2f, 18, south);
            // 身后 0.9 米的点（近的、要掉头）
            yield return Npc("npc_behind", male, p0, 270, new List<Vector3> { p0 + new Vector3(0.9f, 0, 0) }, 4f, 0.0f, 0.2f, 18, south);
            // 两人迎面：同时开始，用两台相同 Run 不行，单独写
            {
                var a = UnityEngine.Object.Instantiate(female, S + new Vector3(-4f, 0, 4f), Quaternion.Euler(0, 90, 0));
                var b = UnityEngine.Object.Instantiate(male, S + new Vector3(4f, 0, 4.1f), Quaternion.Euler(0, 270, 0));
                var c = UnityEngine.Object.Instantiate(female, S + new Vector3(0.2f, 0, 0.2f), Quaternion.Euler(0, 0, 0));
                var T = Type.GetType("Yuanjing.Folk, Assembly-CSharp");
                var fa = a.GetComponent(T); var fb = b.GetComponent(T); var fcx = c.GetComponent(T);
                foreach (var ff2 in new[] { fa, fb, fcx }) ff2.GetType().GetField("walkSpeed").SetValue(ff2, 0.85f);
                yield return new WaitForSeconds(1f);
                Call(fa, "Walk", new List<Vector3> { S + new Vector3(4.5f, 0, 4f) });
                Call(fb, "Walk", new List<Vector3> { S + new Vector3(-4.5f, 0, 4.1f) });
                Call(fcx, "Walk", new List<Vector3> { S + new Vector3(0.2f, 0, 8f) });
                var r = NewRec(18);
                var rb = NewRec(0); var rc = NewRec(0);
                float t = 0, next = 0.5f, minAB = 99, minAC = 99, minBC = 99;
                var aa = a.GetComponentInChildren<Animator>(); var ab = b.GetComponentInChildren<Animator>(); var ac = c.GetComponentInChildren<Animator>();
                while (t < 13f)
                {
                    yield return null; t += Time.deltaTime;
                    Sample(r, t, a.transform, aa, fa); Sample(rb, t, b.transform, ab, fb); Sample(rc, t, c.transform, ac, fcx);
                    Vector3 pa = a.transform.position, pb = b.transform.position, pc = c.transform.position; pa.y = pb.y = pc.y = 0;
                    minAB = Mathf.Min(minAB, (pa - pb).magnitude); minAC = Mathf.Min(minAC, (pa - pc).magnitude); minBC = Mathf.Min(minBC, (pb - pc).magnitude);
                    if (t >= next && r.shots < 18)
                    {
                        next += 0.45f;
                        Vector3 mid = S + new Vector3(0, 0, 4f);
                        Shoot(r, mid, south + Vector3.up * 0.9f, 7.5f, 1.0f, 0.3f, "");
                    }
                }
                minCross = Mathf.Min(minAB, Mathf.Min(minAC, minBC));
                Log($"迎面避让：最近距离 A-B {F(minAB)} A-C {F(minAC)} B-C {F(minBC)}；A 终点差 {F((a.transform.position - (S + new Vector3(4.5f, 0, 4f))).magnitude)} B {F((b.transform.position - (S + new Vector3(-4.5f, 0, 4.1f))).magnitude)} C {F((c.transform.position - (S + new Vector3(0.2f, 0, 8f))).magnitude)}");
                Save(r, "npc_cross_a"); Save(rb, "npc_cross_b"); Save(rc, "npc_cross_c");
                UnityEngine.Object.Destroy(a); UnityEngine.Object.Destroy(b); UnityEngine.Object.Destroy(c);
            }
        }
        // ── 判定 ──
        if (recs.TryGetValue("feet_right" + sfx, out var fr) && recs.TryGetValue("feet_idle" + sfx, out var fi))
        {
            float pl = FootPitch(fr, true, 1.2f, 3.6f), pr = FootPitch(fr, false, 1.2f, 3.6f), pi = FootPitch(fi, true, 0f, 1f);
            Check(Mathf.Abs(pl - pr) < 5f, $"走路时左右脚掌踩稳的俯仰差不到 5 度：左 {F(pl)} 右 {F(pr)}");
            Check(Mathf.Abs(pl - pi) < 5f && Mathf.Abs(pr - pi) < 5f, $"走路时脚掌和站着时差不到 5 度：站着 {F(pi)}");
        }
        if (recs.TryGetValue("p_pivot180" + sfx, out var pv))
            Check(MaxYawRate(pv, 0.6f, 3.6f) < 360f, $"站着往回转（180 度）身子最快不到 360 度/秒（不像转盘）：{F(MaxYawRate(pv, 0.6f, 3.6f))}");
        if (minCross > 0) Check(minCross >= 0.4f, $"两人交叉、迎面时中心距不小于 0.4 米：{F(minCross)}");
        // 香客按路线走到终点：最后 3 米也不赶（walkSpeed 0.85）
        foreach (var nm in new[] { "npc_arrive_bow", "npc_stop_f", "npc_stop_m" })
            if (recs.TryGetValue(nm + sfx, out var nr) || recs.TryGetValue(nm, out nr))
            {
                ArriveStats(nr, out float mv, out float mr, out int rev, out string tr);
                Log($"{nm} 最后 3 米 速度最大 {F(mv)} 播放最快 {F(mr)} 快慢来回 {rev} 次；{tr}");
                Check(mv <= nr.walkSpeed * 1.05f + 0.011f && mr <= 1.2f && rev <= 1, $"{nm} 最后 3 米速度不超过 1.05 倍 walkSpeed、播放不超过 1.2、快慢最多变一次向：{F(mv)} {F(mr)} {rev}");
            }
        // 停步时脚的高度和站着时一样（不陷进地里）
        foreach (var (nm, t0, t1) in new[] { ("p_stop", 0f, 99f), ("npc_stop_f", 0f, 99f), ("npc_stop_m", 0f, 99f) })
            if (recs.TryGetValue(nm + sfx, out var sr) || recs.TryGetValue(nm, out sr))
            {
                // 停步里还在迈的那一两步：脚不比走路、站着时低（再低就是陷进地里）；最后站住的 0.3 秒：和站着时差不到 0.8 厘米
                int si = sr.loco.FindIndex(x => x.StartsWith("Stop")), se = sr.loco.FindLastIndex(x => x.StartsWith("Stop"));
                LowFeet(sr, "Stop", 0f, t1, out float sa, out float st);
                LowFeet(sr, "Move", 0f, t1, out float ma, out float mt);
                LowFeet(sr, "Idle", t0, t1, out float ia, out float it);
                LowFeet(sr, "Stop", se >= 0 ? sr.t[se] - 0.3f : 0f, t1, out float fa, out float ft);
                Check(sa < 8 && ia < 8 && sa >= Mathf.Min(ia, ma) - 0.004f && st >= Mathf.Min(it, mt) - 0.004f,
                    $"{nm} 停步里脚踝、脚趾最低处不比走路、站着时低（差 0.4 厘米以内）：停 {F(sa)}/{F(st)} 走 {F(ma)}/{F(mt)} 站 {F(ia)}/{F(it)}");
                Check(fa < 8 && Mathf.Abs(fa - ia) < 0.008f && Mathf.Abs(ft - it) < 0.008f, $"{nm} 停步最后站住时脚踝、脚趾和站着时差不到 0.8 厘米：{F(fa)}/{F(ft)} 站 {F(ia)}/{F(it)}");
                float drift = StopSettleDrift(sr, out float at);
                Check(drift >= 0 && drift < 0.015f, $"{nm} 停步站稳、淡到待机前后（{F(at)} 秒）两只脚在地上挪了不到 1.5 厘米：{F(drift)}");
            }
        // 稳步走时手不跳（循环接缝处以前手会一帧跳 3 厘米）；进停步那一帧脚不跳
        if (fps == 60 && recs.TryGetValue("p_speeds", out var ps))
        {
            float hl = Spike(ps, ps.lh, 1.5f, 12f, out float hlt), hr = Spike(ps, ps.rh, 1.5f, 12f, out float hrt);
            Check(Mathf.Max(hl, hr) < 0.008f, $"p_speeds 摇杆 0.3/0.55/0.8/1.0 稳步走，手一帧的跳动不到 0.8 厘米：左 {F(hl)}（{F(hlt)} 秒）右 {F(hr)}（{F(hrt)} 秒）");
        }
        foreach (var nm in new[] { "p_speeds", "p_startstop", "p_stop" })
            if (fps == 60 && recs.TryGetValue(nm, out var rr))
            {
                float worst = 0, wt = -1;
                for (int i = 1; i < rr.t.Count; i++)
                {
                    ParseLoco(rr.loco[i - 1], out var s0, out _, out _); ParseLoco(rr.loco[i], out var s1, out _, out _);
                    if (s0 != "Move" || s1 != "Stop") continue;
                    foreach (var P in new[] { rr.la, rr.ra, rr.lt, rr.rt })
                    {
                        float v = Spike(rr, P, rr.t[i] - 0.05f, rr.t[i] + 0.05f, out float vt);
                        if (v > worst) { worst = v; wt = vt; }
                    }
                }
                Check(worst < 0.01f, $"{nm} 进停步时脚（踝、脚趾）一帧的跳动不到 1 厘米：{F(worst)}（{F(wt)} 秒）");
            }
        // 起步：支撑脚不滑、身子不往旁边甩、迈出去的脚不往后踢
        if (recs.TryGetValue("p_startstop" + sfx, out var pst))
        {
            StartStats(pst, 0.8f, out float ss, out float lv, out float sb);
            Check(ss < 0.03f && lv < 0.4f && sb < 0.03f, $"p_startstop 起步 0.35 秒里支撑脚滑不到 3 厘米、根往旁边不超过 0.4 米/秒、迈的脚往后不到 3 厘米：{F(ss)} {F(lv)} {F(sb)}");
        }
        // 转身时踩在地上的脚一次着地里最多拧 70 度（不像单脚原地打转）
        foreach (var nm in new[] { "p_turn90", "p_turn180", "p_pivot90", "p_pivot180", "p_zigzag" })
            if (recs.TryGetValue(nm + sfx, out var tr2))
            {
                float y = PlantedYaw(tr2, 0.3f, 99f);
                Check(y <= 70f, $"{nm} 踩在地上的脚一次着地转了不到 70 度：{F(y)}");
            }
        File.WriteAllText($"{OUT}/log{sfx}.txt", log.ToString());
        Time.captureFramerate = 0;
        Assert.IsEmpty(fails, string.Join("；", fails));
    }
}
