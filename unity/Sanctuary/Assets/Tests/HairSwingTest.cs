using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 头发（SpringBones）：转身、起步、走着拐弯、停下、跪拜叩首时甩得多远。
/// 量：每一根头发骨头离头顶那根竖线横着多远（按人自己的左右、前后量），每一段取最大；再从人身后拍几张连着的（unity/shots/hair/*.png）。
/// 要求：转身、拐弯时头发不横着甩出去太远（以前在殿门口一转身，长头发横着飞出去半个身子），站着、走着又不像焊死了一样不动。
/// 跑：unity/playtest.sh HairSwingTest
public class HairSwingTest
{
    GameObject bridge, player;
    Animator anim;
    Transform head;
    readonly List<Transform> hair = new List<Transform>();
    Camera shotCam;
    RenderTexture rt;
    Texture2D tex;
    readonly List<string> fails = new List<string>();
    readonly float[] lifts = new float[9], means = new float[9];
    Component springs;
    Vector3 lastHead;

    static void Log(string s) => Debug.Log("[yuanjing] 头发 " + s);
    void Cmd(string json) => bridge.SendMessage("OnMessage", json);
    void Stick(float x, float y) => Cmd("{\"cmd\":\"move\",\"x\":" + x.ToString("F2", System.Globalization.CultureInfo.InvariantCulture) + ",\"y\":" + y.ToString("F2", System.Globalization.CultureInfo.InvariantCulture) + "}");

    /// 头发最翘的那一截离正下方多少度（每一节头发骨头指向下一节的方向；长头发垂着时二三十度，横着甩出去九十度）。
    /// 只看头顶以下的（头顶上那几节本来就是横着贴着头皮的）
    float Lift() => LiftStats().worst;

    /// 头顶以下的头发：最翘的那一截、平均离正下方多少度
    (float worst, float mean) LiftStats()
    {
        float worst = 0, sum = 0;
        int n = 0;
        foreach (var t in hair)
        {
            if (t.childCount == 0 || t.position.y > head.position.y - 0.05f) continue;
            Vector3 d = t.GetChild(0).position - t.position;
            if (d.sqrMagnitude < 1e-6f) continue;
            float a = Vector3.Angle(Vector3.down, d);
            worst = Mathf.Max(worst, a);
            sum += a;
            n++;
        }
        return (worst, n > 0 ? sum / n : 0f);
    }

    /// 此刻头发离头顶那根竖线：横着最远（左右）、往后最远、离竖线最远（水平），按人现在的朝向量
    (float side, float back, float far) Spread()
    {
        Vector3 f = player.transform.GetComponentInChildren<Animator>().transform.forward;
        f.y = 0;
        f.Normalize();
        Vector3 r = Vector3.Cross(Vector3.up, f);
        Vector3 h = head.position;
        float side = 0, back = 0, far = 0;
        foreach (var t in hair)
        {
            Vector3 d = t.position - h;
            side = Mathf.Max(side, Mathf.Abs(Vector3.Dot(d, r)));
            back = Mathf.Max(back, -Vector3.Dot(d, f));
            far = Mathf.Max(far, new Vector2(d.x, d.z).magnitude);
        }
        return (side, back, far);
    }

    void Shot(string name, float yawOffset = 180f)
    {
        Vector3 f = anim.transform.forward;
        f.y = 0;
        f.Normalize();
        Vector3 at = head.position + Vector3.down * 0.35f;
        // 默认从人身后看（yawOffset 180）；90 是从右边。跪着、叩首时头低：镜头抬高一些，不埋在草里
        Vector3 dir = Quaternion.Euler(0, yawOffset, 0) * f;
        float up = head.position.y - player.transform.position.y < 0.8f ? 0.9f : 0.25f;
        shotCam.transform.position = at + dir * 2.0f + Vector3.up * up;
        shotCam.transform.LookAt(at);
        shotCam.targetTexture = rt;
        shotCam.Render();
        shotCam.targetTexture = null;
        RenderTexture.active = rt;
        tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
        tex.Apply();
        RenderTexture.active = null;
        File.WriteAllBytes($"../shots/hair/{name}.png", tex.EncodeToPNG());
    }

    /// 录一段：每帧量一次，取最大；按给的时刻拍几张
    IEnumerator Record(string name, float secs, float[] shotsAt, (float side, float back, float far)[] result, int slot, float shotYaw = 180f)
    {
        var max = (side: 0f, back: 0f, far: 0f);
        float lift = 0, meanMax = 0, nextLog = 0;
        var series = new System.Text.StringBuilder();
        int next = 0;
        for (float t = 0; t < secs; t += Time.deltaTime)
        {
            yield return null;
            var s = Spread();
            max = (Mathf.Max(max.side, s.side), Mathf.Max(max.back, s.back), Mathf.Max(max.far, s.far));
            var ls = LiftStats();
            lift = Mathf.Max(lift, ls.worst);
            meanMax = Mathf.Max(meanMax, ls.mean);
            if (t >= nextLog)
            {
                // 诊断：弹簧骨这一帧记下的身子位移、头骨这一帧的位移（毫米）
                string dbg = "";
                if (springs != null)
                {
                    var lj = springs.GetType().GetField("lastJump", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                    if (lj != null) dbg = $"[{((Vector3)lj.GetValue(springs)).magnitude * 1000:F0}/{(head.position - lastHead).magnitude * 1000:F0}]";
                }
                series.Append($"{ls.mean:F0}/{ls.worst:F0}{dbg} ");
                nextLog += 0.2f;
            }
            lastHead = head.position;
            if (shotsAt != null && next < shotsAt.Length && t >= shotsAt[next])
            {
                Shot($"{name}_{next}", shotYaw);
                next++;
            }
        }
        result[slot] = max;
        lifts[slot] = lift;
        means[slot] = meanMax;
        Log($"{name}：横着最远 {max.side:F3} 米，往后最远 {max.back:F3} 米，离头顶竖线最远 {max.far:F3} 米，最翘的一截离正下方 {lift:F0} 度，平均最多 {meanMax:F0} 度（每 0.2 秒 平均/最翘：{series}）");
    }

    [UnityTest, Timeout(600000)]
    public IEnumerator Swing()
    {
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        bridge = GameObject.Find("Bridge");
        // 不摆本机的香客（seed 0）：只看自己
        Cmd("{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":0,\"name\":\"测试\"}");
        yield return new WaitForSeconds(2f);
        player = GameObject.Find("Player");
        anim = player.GetComponentInChildren<Animator>();
        head = anim.GetBoneTransform(HumanBodyBones.Head);
        foreach (var t in anim.GetComponentsInChildren<Transform>())
            if (t.name.StartsWith("HairJoint")) hair.Add(t);
        Assert.Greater(hair.Count, 5, "没找到头发骨头");
        foreach (var b in anim.GetComponentsInChildren<Behaviour>()) if (b.GetType().Name == "SpringBones") springs = b;
        // 对照用：YJ_NOSPRING=1 时关掉头发的摆动（头发焊在头上），看走路时的姿势本身让头发偏多少
        if (!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("YJ_NOSPRING")))
            foreach (var b in anim.GetComponentsInChildren<Behaviour>())
                if (b.GetType().Name == "SpringBones") b.enabled = false;
        Directory.CreateDirectory("../shots/hair");
        foreach (var f in Directory.GetFiles("../shots/hair", "*.png")) File.Delete(f);
        var camGo = new GameObject("HairCam");
        shotCam = camGo.AddComponent<Camera>();
        shotCam.fieldOfView = 40;
        shotCam.nearClipPlane = 0.05f;
        shotCam.enabled = false;
        rt = new RenderTexture(360, 480, 24) { antiAliasing = 4 };
        tex = new Texture2D(360, 480, TextureFormat.RGB24, false);
        Cmd("{\"cmd\":\"view\",\"kind\":\"level\"}");

        // 站在院子里空地上（香炉南边），面朝北
        var cc = player.GetComponent<CharacterController>();
        cc.enabled = false;
        player.transform.position = new Vector3(0, 0.07f, -8.5f);
        cc.enabled = true;
        var folk = anim.GetComponentInParent(Type.GetType("Yuanjing.Folk, Assembly-CSharp"));
        var faceYaw = folk.GetType().GetMethod("FaceYaw");
        faceYaw.Invoke(folk, new object[] { 0f });
        yield return new WaitForSeconds(2.5f);

        var r = new (float side, float back, float far)[9];
        yield return Record("01站着", 2f, new[] { 1f }, r, 0);
        // 原地转身 180 度
        faceYaw.Invoke(folk, new object[] { 180f });
        yield return Record("02原地转身", 2.2f, new[] { 0.2f, 0.4f, 0.6f, 0.9f, 1.4f }, r, 1);
        yield return new WaitForSeconds(1.5f);
        // 往前走（镜头朝向不管：按摇杆往上推，人朝着镜头前方走）
        Stick(0, 1);
        yield return Record("03起步", 2.0f, new[] { 0.3f, 0.6f, 1.2f }, r, 2, 90f);
        // 走着往右拐（摇杆推到右边）
        Stick(1, 0);
        yield return Record("04走着拐弯", 1.6f, new[] { 0.2f, 0.4f, 0.7f, 1.1f }, r, 3);
        Stick(0, 0);
        yield return Record("05停下", 1.8f, new[] { 0.2f, 0.5f, 1.0f }, r, 4, 90f);
        yield return new WaitForSeconds(1f);
        // 原地反复左右转（转身最猛的情形）
        faceYaw.Invoke(folk, new object[] { 0f });
        yield return Record("06再转身", 1.2f, new[] { 0.25f, 0.5f }, r, 5);
        yield return new WaitForSeconds(1.5f);
        // 跪下、叩首三次、起来
        Cmd("{\"cmd\":\"act\",\"action\":\"kneel\"}");
        yield return Record("07跪拜叩首", 13f, new[] { 3.5f, 4.6f, 5.4f, 12f }, r, 6, 140f);
        yield return new WaitForSeconds(1f);
        yield return Record("08站好", 1.5f, new[] { 1f }, r, 7);
        // 俯视（镜头二十多米外，头发不算）时走一段、转个身，再换回平视（进殿时就是这样：俯视走到殿门口，一进门换平视）
        Cmd("{\"cmd\":\"view\",\"kind\":\"top\"}");
        yield return new WaitForSeconds(1.5f);
        Stick(1, 0);
        yield return new WaitForSeconds(1.5f);
        Stick(0, -1);
        yield return new WaitForSeconds(1.5f);
        Stick(0, 0);
        yield return new WaitForSeconds(0.3f);
        Cmd("{\"cmd\":\"view\",\"kind\":\"level\"}");
        yield return Record("09俯视换回平视", 1.6f, new[] { 0.05f, 0.3f, 0.7f }, r, 8);
        float frames = 0, secs = 0;
        for (int i = 0; i < 30; i++) { yield return null; frames++; secs += Time.unscaledDeltaTime; }
        Log($"编辑器里每秒 {frames / secs:F0} 帧");

        // 要求：转身、拐弯、停下时横着甩出去的不超过站着时的 2.2 倍、也不超过 0.36 米；走起来要看得出在动（往后荡的比站着时多）
        float rest = Mathf.Max(0.05f, r[0].side);
        foreach (int i in new[] { 1, 3, 4, 5, 8 })
        {
            if (r[i].side > Mathf.Max(rest * 2.2f, 0.2f) || r[i].side > 0.36f)
                fails.Add($"第 {i + 1} 段横着甩出去 {r[i].side:F2} 米（站着时 {rest:F2}）");
        }
        if (r[2].back < r[0].back + 0.01f) fails.Add($"起步时头发没往后荡（{r[2].back:F3}，站着 {r[0].back:F3}）：太硬了");
        // 最翘的一截：走着、转着不横着飞（站着时的那么多再加 30 度以内；以前起步、俯视换平视时多 44 度，平着往后飘）
        foreach (int i in new[] { 1, 2, 3, 4, 5, 8 })
            if (lifts[i] > lifts[0] + 30f) fails.Add($"第 {i + 1} 段头发翘到离正下方 {lifts[i]:F0} 度（站着时 {lifts[0]:F0}）");
        Log($"{fails.Count} 处不对 {string.Join("；", fails)}");
        UnityEngine.Object.Destroy(camGo);
        Assert.IsEmpty(fails, string.Join("；", fails));
    }
}
