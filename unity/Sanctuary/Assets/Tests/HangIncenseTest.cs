using System;
using System.Collections;
using System.Globalization;
using System.IO;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 挂布条、上香的动作和 Folk 的接口（给大殿、许愿树那边用的）：
///   SetPose(Hang) → 系（循环）→ ReleaseHang() → 等 OneShotDone；
///   SetPose(Incense) → SetBow 拜三下 → PlayOnce("Incense_Plant") → 等 OneShotDone（插完是合掌）→ SetPose(None)。
/// 每一步从侧面、正面各拍一张，拼成 unity/shots/loco/hang.png、incense.png；量手的高度、离人多远，记在日志里。
public class HangIncenseTest
{
    Component folk;
    Animator anim;
    Transform root;
    Camera cam;
    RenderTexture rt;
    Texture2D frame;
    const int W = 240, H = 330;
    static string F(float v) => v.ToString("F2", CultureInfo.InvariantCulture);

    object Pose(string n) => Enum.Parse(Type.GetType("Yuanjing.Folk+Pose, Assembly-CSharp"), n);
    void Call(string m, params object[] a)
    {
        foreach (var mi in folk.GetType().GetMethods())
            if (mi.Name == m && mi.GetParameters().Length == a.Length) { mi.Invoke(folk, a); return; }
        throw new Exception("没有方法 " + m);
    }
    bool Done => (bool)folk.GetType().GetProperty("OneShotDone").GetValue(folk);
    string ActNow => folk.GetType().GetField("actNow", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance).GetValue(folk) as string;

    void Shoot(Texture2D strip, int i, Vector3 dir)
    {
        Vector3 p = root.position;
        cam.transform.position = p + dir * 2.6f + Vector3.up * 0.85f;
        cam.transform.LookAt(p + Vector3.up * 0.7f);
        cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
        RenderTexture.active = rt; frame.ReadPixels(new Rect(0, 0, W, H), 0, 0); frame.Apply(); RenderTexture.active = null;
        strip.SetPixels(i * W, 0, W, H, frame.GetPixels());
    }

    string Hands()
    {
        var r = (Transform)folk.GetType().GetMethod("Hand").Invoke(folk, new object[] { true });
        var l = (Transform)folk.GetType().GetMethod("Hand").Invoke(folk, new object[] { false });
        Vector3 m = (r.position + l.position) * 0.5f - root.position;
        float fwd = Vector3.Dot(m, root.GetComponentInChildren<Animator>().transform.forward);
        return $"两手中点 离地 {F(m.y)} 米、在人前方 {F(fwd)} 米、两手相距 {F(Vector3.Distance(r.position, l.position))} 米（动作段 {ActNow}）";
    }

    [UnityTest, Timeout(600000)]
    public IEnumerator HangAndIncense()
    {
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        var bridge = GameObject.Find("Bridge");
        bridge.SendMessage("OnMessage", "{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"测试\"}");
        yield return new WaitForSeconds(2f);
        var player = GameObject.Find("Player");
        foreach (var t in UnityEngine.Object.FindObjectsByType<Transform>(FindObjectsSortMode.None))
            if (t.name.StartsWith("Pilgrim_")) t.gameObject.SetActive(false);
        // 湖面上一块平地，背景干净
        var pad = GameObject.CreatePrimitive(PrimitiveType.Plane);
        pad.name = "ground";
        pad.transform.position = new Vector3(70f, 0.3f, 0f);
        pad.transform.localScale = new Vector3(2f, 1f, 2f);
        var cc = player.GetComponent<CharacterController>();
        cc.enabled = false;
        player.transform.position = new Vector3(70f, 0.32f, 0f);
        cc.enabled = true;
        root = player.transform;
        anim = player.GetComponentInChildren<Animator>();
        folk = player.GetComponentInChildren(Type.GetType("Yuanjing.Folk, Assembly-CSharp"));
        folk.transform.rotation = Quaternion.identity;
        Call("FaceYaw", 0f);
        Directory.CreateDirectory("../shots/loco");
        cam = new GameObject("HangCam").AddComponent<Camera>();
        cam.fieldOfView = 34;
        rt = new RenderTexture(W, H, 24) { antiAliasing = 4 };
        frame = new Texture2D(W, H, TextureFormat.RGB24, false);
        yield return new WaitForSeconds(1f);
        Vector3 side = Vector3.right, front = Vector3.forward;

        // ── 挂布条 ──
        var hang = new Texture2D(W * 8, H, TextureFormat.RGB24, false);
        var strip2 = new Texture2D(W * 8, H, TextureFormat.RGB24, false);
        Call("SetPose", Pose("Hang"));
        float[] at = { 0.3f, 0.8f, 1.3f, 2.0f, 2.6f };
        float clock = 0; int k = 0;
        while (k < at.Length)
        {
            yield return null; clock += Time.deltaTime;
            if (clock >= at[k]) { Shoot(hang, k, side); Debug.Log($"[yuanjing] 挂布条 {F(clock)}s：{Hands()}"); k++; }
        }
        Call("ReleaseHang");
        Debug.Log($"[yuanjing] 挂布条 松手：OneShotDone={Done}");
        float t0 = clock;
        while (!Done && clock - t0 < 5f)
        {
            yield return null; clock += Time.deltaTime;
            if (k < 8 && clock - t0 >= (k - 4) * 0.45f) { Shoot(hang, k, side); k++; }
        }
        Debug.Log($"[yuanjing] 挂布条 收手用了 {F(clock - t0)} 秒，OneShotDone={Done}，姿势 {folk.GetType().GetProperty("pose").GetValue(folk)}");
        yield return new WaitForSeconds(1f);
        // 正面那一排
        Call("SetPose", Pose("Hang"));
        yield return new WaitForSeconds(2f);
        Shoot(strip2, 0, front);
        Debug.Log($"[yuanjing] 挂布条 正面：{Hands()}");
        Call("ReleaseHang");
        yield return new WaitForSeconds(2.5f);

        // ── 上香 ──
        // 大殿中间供桌、香炉的替身（hall_props 的尺寸）：人站在上香点 z 18.52 时，桌围在人前方 0.297 米（z 18.817），桌面离地 0.784，
        // 桌深 0.758；香炉中心在前方 0.48（z 19.0），炉身半径 0.155，口沿离地 0.986，灰面 0.962
        Vector3 o = root.position;
        var table = GameObject.CreatePrimitive(PrimitiveType.Cube);
        table.name = "AltarTableProxy";
        table.transform.position = o + new Vector3(0, 0.784f / 2, 0.297f + 0.758f / 2);
        table.transform.localScale = new Vector3(2.4f, 0.784f, 0.758f);
        var censer = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        censer.name = "CenserProxy";
        censer.transform.position = o + new Vector3(0, 0.784f + 0.101f, 0.48f);
        censer.transform.localScale = new Vector3(0.31f, 0.101f, 0.31f);
        foreach (var g in new[] { table, censer }) UnityEngine.Object.Destroy(g.GetComponent<Collider>());
        Bounds tb = new Bounds(table.transform.position, table.transform.localScale);
        var bones = new[] { HumanBodyBones.Head, HumanBodyBones.UpperChest, HumanBodyBones.Chest, HumanBodyBones.Hips, HumanBodyBones.LeftLowerLeg, HumanBodyBones.RightLowerLeg,
            HumanBodyBones.LeftToes, HumanBodyBones.RightToes, HumanBodyBones.LeftHand, HumanBodyBones.RightHand, HumanBodyBones.LeftLowerArm, HumanBodyBones.RightLowerArm };
        float minClear = 9; string minWho = "";
        void Clearance()
        {
            foreach (var b in bones)
            {
                var tr = anim.GetBoneTransform(b);
                if (tr == null) continue;
                // 骨头点到桌子的距离（在里面为负）；手、头这些骨头点外面还有一层肉，按 0.04 米算
                Vector3 q = tr.position, c = tb.ClosestPoint(q);
                float d = tb.Contains(q) ? -Mathf.Min(Mathf.Min(q.y - tb.min.y, tb.max.y - q.y), Mathf.Min(q.z - tb.min.z, tb.max.z - q.z)) : Vector3.Distance(q, c);
                if (d < minClear) { minClear = d; minWho = $"{b}（{F(Time.time)}）"; }
            }
        }
        var inc = new Texture2D(W * 10, H, TextureFormat.RGB24, false);
        Call("SetPose", Pose("Incense"));
        yield return new WaitForSeconds(2.0f);
        Shoot(inc, 0, side);
        Shoot(strip2, 1, front);
        Debug.Log($"[yuanjing] 上香 举香：{Hands()}");
        int s = 1;
        for (int b = 0; b < 3; b++)
        {
            for (float t = 0; t < 1.2f; t += Time.deltaTime) { Call("SetBow", t / 1.2f); yield return null; Clearance(); }
            Call("SetBow", 1f);
            if (b == 0) { Shoot(inc, s++, side); Shoot(strip2, 2, front); Debug.Log($"[yuanjing] 上香 拜到底：{Hands()}"); }
            yield return new WaitForSeconds(0.4f);
            for (float t = 0; t < 1.0f; t += Time.deltaTime) { Call("SetBow", 1 - t); yield return null; }
            Call("SetBow", 0f);
        }
        Call("PlayOnce", "Incense_Plant");
        float plantT = (float)folk.GetType().GetField("IncensePlantTime").GetValue(null);
        t0 = Time.time;
        bool planted = false;
        while (!Done && Time.time - t0 < 6f)
        {
            yield return null;
            float e = Time.time - t0;
            Clearance();
            if (!planted && e >= plantT)
            {
                planted = true; Shoot(inc, s++, side); Shoot(strip2, 3, front); Debug.Log($"[yuanjing] 上香 插香那一刻（{F(e)}s）：{Hands()}");
                var rh = (Transform)folk.GetType().GetMethod("Hand").Invoke(folk, new object[] { true });
                var lh = (Transform)folk.GetType().GetMethod("Hand").Invoke(folk, new object[] { false });
                Vector3 m = (rh.position + lh.position) * 0.5f, ash = o + new Vector3(0, 0.962f, 0.48f);
                Debug.Log($"[yuanjing] 上香 插香那一刻两手中点离香炉灰面中心：水平 {F(new Vector2(m.x - ash.x, m.z - ash.z).magnitude)} 米（前后 {F(m.z - ash.z)}），高出灰面 {F(m.y - ash.y)} 米、高出炉口 {F(m.y - (o.y + 0.986f))} 米");
            }
            else if (s < 8 && e >= (s - 1) * 0.5f) Shoot(inc, s++, side);
        }
        Debug.Log($"[yuanjing] 上香 插香播完用了 {F(Time.time - t0)} 秒，OneShotDone={Done}，姿势 {folk.GetType().GetProperty("pose").GetValue(folk)}（{ActNow}）");
        Debug.Log($"[yuanjing] 上香 拜、插香时身子离供桌（替身）最近 {F(minClear)} 米：{minWho}（骨头点，不算肉的厚度）");
        yield return new WaitForSeconds(0.8f);
        Shoot(inc, s++, side);
        Call("SetPose", Pose("None"));
        yield return new WaitForSeconds(1.6f);
        Shoot(inc, s++, side);
        Debug.Log($"[yuanjing] 上香 放下：{Hands()}");
        hang.Apply(); inc.Apply(); strip2.Apply();
        File.WriteAllBytes("../shots/loco/hang.png", hang.EncodeToPNG());
        File.WriteAllBytes("../shots/loco/incense.png", inc.EncodeToPNG());
        File.WriteAllBytes("../shots/loco/hang_incense_front.png", strip2.EncodeToPNG());
        Assert.Pass();
    }
}
