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

/// 走路自查（游戏里真实的条件：摇杆指令经过 Bridge、镜头会跟着转）：起步、匀速走、停步、走着转 90 / 180 度、站着转身起步 90 / 180 度。
/// 每一段：
///   - 侧面逐帧图（镜头只平移不转，看腿、手、身子），存 unity/shots/loco/<段名>.png
///   - 俯视脚印图（红左脚、蓝右脚，踩着地的点画大；灰线是人走的路线），存 unity/shots/loco/<段名>_top.png
///   - 数：踩地的脚滑多快（平均 / 最大）、身子和走的方向最多差几度、停下用了多久走了多远、转过去用了多久
/// 报告 unity/shots/loco/report.txt
public class LocomotionTest
{
    GameObject bridge, playerRoot;
    Transform body;
    Animator anim;
    Component folk;
    readonly StringBuilder report = new StringBuilder();
    Camera cam;
    RenderTexture rt;
    Texture2D frame;
    const int W = 240, H = 330;
    static string F(float v) => v.ToString("F2", CultureInfo.InvariantCulture);

    void Cmd(string json) => bridge.SendMessage("OnMessage", json);

    /// 按世界里的方向推摇杆（换算成镜头坐标里的摇杆）
    void Stick(Vector3 world)
    {
        float yaw = Camera.main != null ? Camera.main.transform.eulerAngles.y : 0;
        Vector3 s = Quaternion.Euler(0, -yaw, 0) * world;
        Cmd($"{{\"cmd\":\"move\",\"x\":{s.x.ToString(CultureInfo.InvariantCulture)},\"y\":{s.z.ToString(CultureInfo.InvariantCulture)}}}");
    }

    string Loco() => folk.GetType().GetMethod("DebugLoco")?.Invoke(folk, null) as string;

    void Log(string s)
    {
        report.AppendLine(s);
        Debug.Log("[yuanjing] 走路自查 " + s);
    }

    struct Sample { public float t; public Vector3 root, l, r, fwd; public bool rec; public string st; }

    /// 一段：steps 是 (秒, 世界方向)；从 recFrom 秒起录 recSecs 秒、拍 n 张；side：镜头在人的哪一边（世界方向）
    IEnumerator Run(string name, Vector3 start, float yaw0, (float secs, Vector3 dir)[] steps, float recFrom, float recSecs, int n, Vector3 side, float eventAt = -1,
        Action<float> tick = null, Transform who = null, Animator whoAnim = null, Component whoFolk = null)
    {
        var anim = whoAnim ?? this.anim;
        var root = who ?? playerRoot.transform;
        var fk = whoFolk ?? folk;
        string Loco() => fk.GetType().GetMethod("DebugLoco")?.Invoke(fk, null) as string;
        if (who == null)
        {
            // 放回起点、站好
            Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":0}");
            yield return new WaitForSeconds(0.3f);
            var cc = playerRoot.GetComponent<CharacterController>();
            cc.enabled = false;
            playerRoot.transform.position = start;
            body.rotation = Quaternion.Euler(0, yaw0, 0);
            folk.GetType().GetMethod("FaceYaw").Invoke(folk, new object[] { yaw0 });
            cc.enabled = true;
            yield return new WaitForSeconds(1.2f);
        }
        var lf = anim.GetBoneTransform(HumanBodyBones.LeftFoot);
        var rf = anim.GetBoneTransform(HumanBodyBones.RightFoot);
        var samples = new List<Sample>();
        // 脚步声：录的这段里响了几下、隔多久
        var stepTimes = new List<float>();
        float clock = 0;
        var stepEv = fk.GetType().GetEvent("Step");
        Action onStep = () => stepTimes.Add(clock);
        stepEv.AddEventHandler(fk, onStep);
        var strip = new Texture2D(W * n, H, TextureFormat.RGB24, false);
        int shot = 0;
        float total = 0;
        foreach (var s in steps) total += s.secs;
        float t = 0, nextShot = recFrom;
        int si = 0;
        float stepEnd = steps[0].secs;
        string states = "";
        while (t < total)
        {
            while (si < steps.Length - 1 && t >= stepEnd) { si++; stepEnd += steps[si].secs; }
            if (tick != null) tick(t);
            else if (steps[si].dir.sqrMagnitude > 0) Stick(steps[si].dir); else Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":0}");
            yield return null;
            t += Time.deltaTime;
            clock = t;
            bool rec = t >= recFrom && t <= recFrom + recSecs;
            samples.Add(new Sample { t = t, root = root.position, l = lf.position, r = rf.position, fwd = anim.transform.forward, rec = rec, st = rec ? Loco() : null });
            if (rec && shot < n && t >= nextShot)
            {
                nextShot += recSecs / n;
                Vector3 p = root.position;
                cam.transform.position = p + side * 3.4f + Vector3.up * 0.72f;
                cam.transform.LookAt(p + Vector3.up * 0.58f);
                cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
                RenderTexture.active = rt; frame.ReadPixels(new Rect(0, 0, W, H), 0, 0); frame.Apply(); RenderTexture.active = null;
                strip.SetPixels(shot * W, 0, W, H, frame.GetPixels());
                shot++;
                if (shot % 2 == 1) states += $" [{F(t)}s {Loco()}]";
            }
        }
        stepEv.RemoveEventHandler(fk, onStep);
        if (who == null) Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":0}");
        strip.Apply();
        File.WriteAllBytes($"../shots/loco/{name}.png", strip.EncodeToPNG());
        // ── 数 ──
        float minL = float.MaxValue, minR = float.MaxValue;
        foreach (var s in samples) if (s.rec) { minL = Mathf.Min(minL, s.l.y - s.root.y); minR = Mathf.Min(minR, s.r.y - s.root.y); }
        float slide = 0, slideMax = 0; int slideN = 0, bigs = 0, landing = 0;
        string big = "";
        float crab = 0;
        string crabAt = "";
        for (int i = 1; i < samples.Count; i++)
        {
            var a = samples[i - 1]; var b = samples[i];
            if (!b.rec) continue;
            float dt = Mathf.Max(1e-4f, b.t - a.t);
            foreach (var (pa, pb, mn, other) in new[] { (a.l, b.l, minL, b.r), (a.r, b.r, minR, b.l) })
            {
                bool planted = pb.y - b.root.y < mn + 0.01f && pb.y <= other.y + 0.005f;
                if (!planted) continue;
                Vector3 m = pb - pa; m.y = 0;
                float v = m.magnitude / dt;
                // 超过 1 米/秒的是正在落地的那只脚（还在往前摆），不算「踩着滑」，单独数
                if (v > 1f) { landing++; continue; }
                slide += v; slideN++;
                if (v > 0.3f && bigs < 4) { bigs++; big += $" [{F(b.t)}s 滑 {F(v)} 根挪 {F((b.root - a.root).magnitude / dt)} {a.st} → {b.st}]"; }
                slideMax = Mathf.Max(slideMax, v);
            }
            Vector3 vel = (b.root - a.root) / dt; vel.y = 0;
            if (vel.magnitude > 0.35f)
            {
                float cr = Vector3.Angle(new Vector3(b.fwd.x, 0, b.fwd.z), vel);
                if (cr > crab) { crab = cr; crabAt = $"{F(b.t)}s 速度 {F(vel.magnitude)} {b.st}"; }
            }
        }
        string extra = "";
        if (eventAt >= 0)
        {
            // 事件（松手 / 转向）以后：多久停住、走了多远；多久转到新方向 10 度以内
            Vector3 at = Vector3.zero; bool got = false; float stopT = -1, turnT = -1;
            Vector3 dirAfter = Vector3.zero;
            float acc = 0;
            foreach (var s in steps) { if (acc >= eventAt - 1e-3f) { dirAfter = s.dir; break; } acc += s.secs; }
            for (int i = 1; i < samples.Count; i++)
            {
                var b = samples[i];
                if (b.t < eventAt) continue;
                if (!got) { at = b.root; got = true; }
                float v = (b.root - samples[i - 1].root).magnitude / Mathf.Max(1e-4f, b.t - samples[i - 1].t);
                if (stopT < 0 && dirAfter == Vector3.zero && v < 0.02f) { stopT = b.t - eventAt; extra += $"松手后 {F(stopT)} 秒停住、又走了 {F(Vector3.Distance(at, b.root))} 米；"; }
                if (turnT < 0 && dirAfter != Vector3.zero && Vector3.Angle(new Vector3(b.fwd.x, 0, b.fwd.z), dirAfter) < 10f) { turnT = b.t - eventAt; extra += $"转向后 {F(turnT)} 秒转到 10 度以内；"; }
            }
        }
        if (big != "") Log($"{name} 滑得多的帧：{big}");
        string steps2 = "";
        foreach (var st in stepTimes) if (st >= recFrom && st <= recFrom + recSecs) steps2 += F(st) + " ";
        Log($"{name} 脚步声：{steps2}；最偏的一帧 {crabAt}");
        Log($"{name}：踩地的脚平均滑 {F(slideN > 0 ? slide / slideN : 0)} 米/秒（最大 {F(slideMax)}，{slideN} 帧；另有 {landing} 帧是脚在落地），身子和走的方向最多差 {crab:F0} 度；{extra}状态{states}");
        // 俯视脚印
        var top = new Texture2D(360, 360, TextureFormat.RGB24, false);
        var px = new Color[360 * 360];
        for (int i = 0; i < px.Length; i++) px[i] = new Color(0.97f, 0.97f, 0.95f);
        Vector3 c = Vector3.zero; int cn = 0;
        foreach (var s in samples) if (s.rec) { c += s.root; cn++; }
        c /= Mathf.Max(1, cn);
        void Dot(Vector3 p, Color col, int rad)
        {
            int x = Mathf.RoundToInt(180 + (p.x - c.x) * 90), y = Mathf.RoundToInt(180 + (p.z - c.z) * 90);
            for (int dx = -rad; dx <= rad; dx++) for (int dy = -rad; dy <= rad; dy++)
                if (x + dx >= 0 && x + dx < 360 && y + dy >= 0 && y + dy < 360 && dx * dx + dy * dy <= rad * rad) px[(y + dy) * 360 + x + dx] = col;
        }
        for (int gx = 0; gx < 360; gx += 90) for (int gy = 0; gy < 360; gy++) { px[gy * 360 + gx] = new Color(0.85f, 0.85f, 0.85f); px[gx * 360 + gy] = new Color(0.85f, 0.85f, 0.85f); }
        foreach (var s in samples)
        {
            if (!s.rec) continue;
            Dot(s.root, new Color(0.55f, 0.55f, 0.55f), 0);
            bool pl = s.l.y - s.root.y < minL + 0.01f, pr = s.r.y - s.root.y < minR + 0.01f;
            Dot(s.l, pl ? new Color(0.8f, 0.1f, 0.1f) : new Color(1f, 0.75f, 0.75f), pl ? 3 : 1);
            Dot(s.r, pr ? new Color(0.1f, 0.25f, 0.85f) : new Color(0.75f, 0.8f, 1f), pr ? 3 : 1);
        }
        top.SetPixels(px);
        top.Apply();
        File.WriteAllBytes($"../shots/loco/{name}_top.png", top.EncodeToPNG());
    }

    /// 找一块空地：从起点往西 4 米、往南北各 3 米、往东 3 米的方块里，每隔 0.6 米都是平地（地形或铺地石，高差 15 厘米内）、
    /// 半径 0.45 米内没有东西（灯笼、栏杆、树）。离 near 最近的
    static Vector3 OpenGround(Vector3 near)
    {
        int mask = ~(1 << 2);
        bool Free(Vector3 q, float y0)
        {
            if (!Physics.Raycast(new Vector3(q.x, y0 + 2.5f, q.z), Vector3.down, out var h, 5f, mask, QueryTriggerInteraction.Ignore)) return false;
            if (!(h.collider.name == "ground" || h.collider.name == "stone") || Mathf.Abs(h.point.y - y0) > 0.15f) return false;
            foreach (var c in Physics.OverlapCapsule(h.point + Vector3.up * 0.25f, h.point + Vector3.up * 1.6f, 0.45f, mask, QueryTriggerInteraction.Ignore))
                if (c.bounds.size.x < 15f && c.bounds.size.z < 15f) return false;
            return true;
        }
        Vector3 best = near; float bestD = float.MaxValue;
        for (float x = -14; x <= 14; x += 1f)
            for (float z = -18; z <= 22; z += 1f)
            {
                if (!Physics.Raycast(new Vector3(x, near.y + 2.5f, z), Vector3.down, out var hit, 5f, mask, QueryTriggerInteraction.Ignore)) continue;
                Vector3 p = hit.point;
                float d = (p - near).sqrMagnitude;
                if (d >= bestD) continue;
                bool ok = true;
                for (float dx = -4.2f; dx <= 3.01f && ok; dx += 0.6f)
                    for (float dz = -3f; dz <= 3.01f && ok; dz += 0.6f)
                        ok = Free(p + new Vector3(dx, 0, dz), p.y);
                if (ok) { bestD = d; best = p + Vector3.up * 0.05f; }
            }
        Debug.Log($"[yuanjing] 走路自查 找空地：选 {best}");
        return best;
    }

    [UnityTest, Timeout(900000)]
    public IEnumerator Locomotion()
    {
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        bridge = GameObject.Find("Bridge");
        Cmd("{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"测试\"}");
        yield return new WaitForSeconds(2f);
        playerRoot = GameObject.Find("Player");
        anim = playerRoot.GetComponentInChildren<Animator>();
        folk = playerRoot.GetComponentInChildren(Type.GetType("Yuanjing.Folk, Assembly-CSharp"));
        body = folk.transform;
        // 别人不进画面：香客都藏起来
        foreach (var t in UnityEngine.Object.FindObjectsByType<Transform>(FindObjectsSortMode.None))
            if (t.name.StartsWith("Pilgrim_")) t.gameObject.SetActive(false);
        Directory.CreateDirectory("../shots/loco");
        var camGo = new GameObject("LocoCam");
        cam = camGo.AddComponent<Camera>();
        cam.fieldOfView = 30;
        cam.nearClipPlane = 0.1f;
        rt = new RenderTexture(W, H, 24) { antiAliasing = 4 };
        frame = new Texture2D(W, H, TextureFormat.RGB24, false);
        // 试走的场地：岛外湖面上放一块 40×40 米的平地，铺半米一格的棋盘格（看脚滑不滑一目了然），不会撞到灯笼、栏杆
        var pad = GameObject.CreatePrimitive(PrimitiveType.Plane);
        pad.name = "ground";
        pad.transform.position = new Vector3(70f, 0.3f, 0f);
        pad.transform.localScale = new Vector3(4f, 1f, 4f);
        var checker = new Texture2D(2, 2) { filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Repeat };
        checker.SetPixels(new[] { new Color(0.82f, 0.8f, 0.74f), new Color(0.62f, 0.6f, 0.55f), new Color(0.62f, 0.6f, 0.55f), new Color(0.82f, 0.8f, 0.74f) });
        checker.Apply();
        var sh = Shader.Find("Universal Render Pipeline/Unlit") ?? Shader.Find("Unlit/Texture");
        var mat = new Material(sh);
        mat.mainTexture = checker;
        if (mat.HasProperty("_BaseMap")) mat.SetTexture("_BaseMap", checker);
        mat.mainTextureScale = new Vector2(40, 40);
        if (mat.HasProperty("_BaseMap")) mat.SetTextureScale("_BaseMap", new Vector2(40, 40));
        pad.GetComponent<Renderer>().sharedMaterial = mat;
        Vector3 start = new Vector3(70f, 0.32f, 0f);
        Log($"起点 {start}，{Loco()}");
        Vector3 west = Vector3.left, east = Vector3.right, north = Vector3.forward, south = Vector3.back;
        // 往西走：镜头在南边（看人的左侧）
        yield return Run("start", start, 270, new[] { (0.4f, Vector3.zero), (2.0f, west) }, 0.3f, 1.4f, 10, south);
        yield return Run("walk", start, 270, new[] { (3.2f, west) }, 2.0f, 1.2f, 10, south);
        yield return Run("stop", start, 270, new[] { (2.6f, west), (2.2f, Vector3.zero) }, 2.2f, 2.0f, 12, south, 2.6f);
        yield return Run("turn90", start, 270, new[] { (2.4f, west), (2.2f, north) }, 2.2f, 1.6f, 10, south, 2.4f);
        yield return Run("turn180", start, 270, new[] { (2.4f, west), (2.6f, east) }, 2.2f, 2.0f, 12, south, 2.4f);
        yield return Run("pivot90", start, 270, new[] { (0.4f, Vector3.zero), (2.4f, north) }, 0.3f, 1.8f, 12, west, 0.4f);
        yield return Run("pivot180", start, 270, new[] { (0.4f, Vector3.zero), (2.6f, east) }, 0.3f, 1.9f, 12, south, 0.4f);
        yield return Run("slow", start, 270, new[] { (3.0f, west * 0.45f) }, 1.6f, 1.3f, 10, south);
        // 合掌着一推摇杆就走：手在上半身那层慢慢放下，腿马上走（身子不滑着走）
        Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":0}");
        var poseType = Type.GetType("Yuanjing.Folk+Pose, Assembly-CSharp");
        var setPose = folk.GetType().GetMethod("SetPose", new[] { poseType });
        yield return Run("gassho_walk", start, 270, new[] { (2.0f, Vector3.zero), (2.2f, west) }, 1.6f, 2.2f, 12, south, 2.0f,
            t => { if (t < 0.05f) setPose.Invoke(folk, new[] { Enum.Parse(poseType, "Gassho") }); if (t >= 2.0f) Stick(west); });
        // 香客（不用碰撞胶囊，按路线走）：一男一女，走一条带直角拐弯的路线，看拐弯、到终点停步、停的准不准
        var pil = UnityEngine.Object.FindFirstObjectByType(Type.GetType("Yuanjing.Pilgrims, Assembly-CSharp")) as Behaviour;
        var looks = (GameObject[])pil.GetType().GetField("looks").GetValue(pil);
        pil.enabled = false;
        foreach (bool male in new[] { true, false })
        {
            GameObject look = null;
            for (int i = 1; i < looks.Length && look == null; i++)
            {
                var fc = looks[i].GetComponent(Type.GetType("Yuanjing.Folk, Assembly-CSharp"));
                var g = (AnimationClip[])fc.GetType().GetField("gaitClips").GetValue(fc);
                if (g != null && g.Length > 0 && g[0].name.StartsWith(male ? "Walk_M" : "Walk_F")) look = looks[i];
            }
            if (look == null) continue;
            Vector3 p0 = start + new Vector3(4f, 0, -5f);
            var npc = UnityEngine.Object.Instantiate(look, p0, Quaternion.Euler(0, 270, 0));
            npc.name = "TestWalker";
            npc.transform.localScale *= 1.0f;
            var nf = npc.GetComponent(Type.GetType("Yuanjing.Folk, Assembly-CSharp"));
            nf.GetType().GetField("walkSpeed").SetValue(nf, 0.85f);
            var na = npc.GetComponentInChildren<Animator>();
            yield return new WaitForSeconds(1f);
            var path = new List<Vector3> { p0 + new Vector3(-3.5f, 0, 0), p0 + new Vector3(-3.5f, 0, 3.5f), p0 + new Vector3(-1.5f, 0, 4.5f) };
            bool arrived = false; float arrivedAt = -1;
            var ev = nf.GetType().GetEvent("Arrived");
            Action onArr = () => { arrived = true; };
            ev.AddEventHandler(nf, onArr);
            float t0 = Time.time;
            nf.GetType().GetMethod("Walk").Invoke(nf, new object[] { path });
            yield return Run(male ? "npc_male" : "npc_female", p0, 270, new[] { (15f, Vector3.zero) }, 0.2f, 14.5f, 24, south, -1,
                t => { if (arrived && arrivedAt < 0) arrivedAt = t; }, npc.transform, na, nf);
            Vector3 err = npc.transform.position - path[path.Count - 1]; err.y = 0;
            Log($"{(male ? "男" : "女")}香客按路线走：{(arrived ? $"{F(arrivedAt)} 秒到" : "没到")}，停的位置差 {F(err.magnitude)} 米（路线 {F(3.5f + 3.5f + 2.2f)} 米）");
            UnityEngine.Object.Destroy(npc);
            yield return null;
        }
        File.WriteAllText("../shots/loco/report.txt", report.ToString());
        Assert.Pass();
    }
}
