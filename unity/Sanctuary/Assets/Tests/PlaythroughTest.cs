using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 自己把湖心小寺玩一遍：进殿、走动、去各处、所有动作、挂心意、摸喂小动物、换视角、换天气。
/// 每一步截图（unity/shots/play/），并逐帧量：
///   身子朝向和走的方向差几度（螃蟹走）、脚着地时滑多少、
///   脚 / 膝 / 臀有没有低于脚下的面（地面、蒲团）、手有没有钻进身体、人和人有没有叠在一起。
/// 报告写在 unity/shots/play/report.txt，最差的帧在报告里点名。
public class PlaythroughTest
{
    readonly StringBuilder report = new StringBuilder();
    Camera cam;
    RenderTexture rt;
    Texture2D tex;
    GameObject bridge, player;
    Animator anim;
    int shot;

    void Cmd(string json) => bridge.SendMessage("OnMessage", json);

    void Shot(string name)
    {
        cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
        RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0); tex.Apply(); RenderTexture.active = null;
        File.WriteAllBytes($"../shots/play/{shot++:00}_{name}.png", tex.EncodeToPNG());
    }

    void Log(string s)
    {
        report.AppendLine(s);
        Debug.Log("[yuanjing] 试玩 " + s);
    }

    Transform B(HumanBodyBones b) => anim.GetBoneTransform(b);

    // ── 穿模：脚下的面有多高（地面、蒲团） ──
    static float SurfaceAt(Vector3 p)
    {
        float y = -10f;
        // 从关节上方 0.3 米往下找（太高会打到大殿、台阶外面那些看不见的碰撞盒）
        if (Physics.Raycast(new Vector3(p.x, p.y + 0.3f, p.z), Vector3.down, out var hit, 3f, ~(1 << 2), QueryTriggerInteraction.Ignore) && !hit.collider.isTrigger && hit.collider is not BoxCollider) y = hit.point.y;
        // 蒲团没有碰撞体：按它的形状算（props.cushion：方草垫 0.8×0.8 厚 0.05、往大殿方向偏 0.12；圆蒲团半径 0.2、顶高 0.176）
        foreach (var c in Cushions)
        {
            float dx = p.x - c.x, dz = p.z - c.z;
            if (Mathf.Abs(dx) < 0.4f && dz > -0.28f && dz < 0.52f) y = Mathf.Max(y, c.y + 0.05f);
            float r = new Vector2(dx, dz).magnitude;
            if (r < 0.2f) y = Mathf.Max(y, c.y + (r < 0.17f ? 0.176f : Mathf.Lerp(0.15f, 0.07f, (r - 0.17f) / 0.03f)));
        }
        return y;
    }

    static readonly List<Vector3> Cushions = new List<Vector3>();

    struct Worst { public float v; public string where; }
    readonly Dictionary<string, Worst> worst = new Dictionary<string, Worst>();

    void Note(string key, float v, string where)
    {
        if (!worst.TryGetValue(key, out var w) || v > w.v) worst[key] = new Worst { v = v, where = where };
    }

    /// 量一帧：骨头低于脚下的面多少（减去肉的厚度）、手进没进身体
    void Measure(string phase)
    {
        if (anim == null) return;
        foreach (var (b, flesh) in new[] { (HumanBodyBones.LeftFoot, 0.035f), (HumanBodyBones.RightFoot, 0.035f), (HumanBodyBones.LeftLowerLeg, 0.045f),
                     (HumanBodyBones.RightLowerLeg, 0.045f), (HumanBodyBones.Hips, 0.09f), (HumanBodyBones.LeftToes, 0.015f), (HumanBodyBones.RightToes, 0.015f) })
        {
            var t = B(b);
            if (t == null) continue;
            float s = player.transform.lossyScale.y * anim.transform.lossyScale.y;
            float pen = SurfaceAt(t.position) - (t.position.y - flesh * s);
            if (pen > 0.03f && !worst.ContainsKey("_shot_" + phase)) { worst["_shot_" + phase] = new Worst(); Shot("clip_" + phase.Replace(" ", "_")); }
            var folk = player.GetComponentInChildren(System.Type.GetType("Yuanjing.Folk, Assembly-CSharp"));
            var actNow = folk.GetType().GetField("actNow", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance).GetValue(folk);
            Note($"穿进地面/蒲团（{b}）", pen, $"{phase}，在 {t.position.ToString("F2")}，脚下的面 {SurfaceAt(t.position):F2}，动作段 {actNow}");
        }
        // 手进身体：手腕在胸腔前后范围内，离脊柱中线的水平距离小于胸宽的一半
        var chest = B(HumanBodyBones.UpperChest) ?? B(HumanBodyBones.Chest);
        var ls = B(HumanBodyBones.LeftUpperArm); var rs = B(HumanBodyBones.RightUpperArm);
        var hips = B(HumanBodyBones.Hips);
        if (chest != null && ls != null && rs != null && hips != null)
        {
            float half = Vector3.Distance(ls.position, rs.position) * 0.32f;
            Vector3 fwd = anim.transform.forward;
            foreach (var hb in new[] { HumanBodyBones.LeftHand, HumanBodyBones.RightHand })
            {
                var h = B(hb).position;
                if (h.y < hips.position.y - 0.02f || h.y > ls.position.y) continue;
                Vector3 axis = Vector3.Lerp(hips.position, chest.position, Mathf.InverseLerp(hips.position.y, chest.position.y, h.y));
                Vector3 d = h - axis; d.y = 0;
                float front = Vector3.Dot(d, fwd), side = Vector3.Dot(d, anim.transform.right);
                // 椭圆：前后 0.6 倍、左右 1 倍胸宽
                float inside = 1f - Mathf.Sqrt(Mathf.Pow(side / half, 2) + Mathf.Pow(front / (half * 0.6f), 2));
                Note("手钻进身体", inside * half, phase);
            }
        }
    }

    // ── 走路：身子朝向和走的方向差几度、脚着地时滑多少 ──
    IEnumerator WalkFor(string name, float x, float y, float secs)
    {
        Cmd($"{{\"cmd\":\"move\",\"x\":{x.ToString(System.Globalization.CultureInfo.InvariantCulture)},\"y\":{y.ToString(System.Globalization.CultureInfo.InvariantCulture)}}}");
        Vector3 last = player.transform.position;
        var lf = B(HumanBodyBones.LeftFoot); var rf = B(HumanBodyBones.RightFoot);
        Vector3 lastL = lf.position, lastR = rf.position;
        float maxYaw = 0, slide = 0; int slideN = 0;
        float camYaw0 = cam.transform.eulerAngles.y;
        for (float t = 0; t < secs; t += Time.deltaTime)
        {
            yield return null;
            Vector3 p = player.transform.position;
            Vector3 v = (p - last) / Mathf.Max(Time.deltaTime, 1e-4f); v.y = 0;
            last = p;
            if (t > 0.6f && v.magnitude > 0.3f)
            {
                float yaw = Vector3.Angle(new Vector3(anim.transform.forward.x, 0, anim.transform.forward.z), v);
                maxYaw = Mathf.Max(maxYaw, yaw);
                // 着地的脚（两脚里低的那只、离地很近）在世界里应该不动
                foreach (var (f, lp) in new[] { (lf, lastL), (rf, lastR) })
                {
                    float ground = SurfaceAt(f.position);
                    bool low = f.position.y < Mathf.Min(lf.position.y, rf.position.y) + 0.01f && f.position.y - ground < 0.13f;
                    if (low)
                    {
                        Vector3 m = f.position - lp; m.y = 0;
                        slide += m.magnitude / Mathf.Max(Time.deltaTime, 1e-4f);
                        slideN++;
                    }
                }
            }
            lastL = lf.position; lastR = rf.position;
            Measure("走路 " + name);
        }
        Shot("walk_" + name);
        Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":0}");
        float camTurn = Mathf.Abs(Mathf.DeltaAngle(camYaw0, cam.transform.eulerAngles.y));
        Log($"走路 {name}：身子和走的方向最多差 {maxYaw:F0} 度，着地的脚平均滑 {(slideN > 0 ? slide / slideN : 0):F2} 米/秒，镜头转了 {camTurn:F0} 度");
        Note("走路身子偏离方向（度）", maxYaw, name);
        yield return new WaitForSeconds(0.8f);
    }

    /// 等人停下来（自动走路走完）：位置 1 秒内几乎不动，最多等 maxSecs 秒
    IEnumerator Settle(string phase, float maxSecs = 25f)
    {
        float still = 0;
        Vector3 last = player.transform.position;
        for (float t = 0; t < maxSecs && still < 1f; t += Time.deltaTime)
        {
            yield return null;
            Measure(phase);
            float d = (player.transform.position - last).magnitude;
            last = player.transform.position;
            still = d < 0.002f ? still + Time.deltaTime : 0;
        }
    }

    IEnumerator Hold(string phase, float secs, string shotName = null)
    {
        for (float t = 0; t < secs; t += Time.deltaTime) { yield return null; Measure(phase); }
        if (shotName != null) Shot(shotName);
    }

    [UnityTest, Timeout(1200000)]
    public IEnumerator PlayEverything()
    {
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        Directory.CreateDirectory("../shots/play");
        foreach (var f in Directory.GetFiles("../shots/play", "*.png")) File.Delete(f);
        bridge = GameObject.Find("Bridge");
        Cmd("{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"测试\"}");
        yield return new WaitForSeconds(2f);
        player = GameObject.Find("Player");
        anim = player.GetComponentInChildren<Animator>();
        cam = Camera.main;
        rt = new RenderTexture(540, 960, 24) { antiAliasing = 4 };
        tex = new Texture2D(540, 960, TextureFormat.RGB24, false);
        Cushions.Clear();
        foreach (var t in Object.FindObjectsByType<Transform>(FindObjectsSortMode.None))
            if (t.name.StartsWith("Seat")) Cushions.Add(t.position);
        Log($"进殿：玩家在 {player.transform.position.ToString("F2")}，蒲团 {Cushions.Count} 个");

        // 1 进来站着
        Cmd("{\"cmd\":\"view\",\"kind\":\"level\"}");
        yield return Hold("进殿站着", 4f, "stand_level");
        var lh = B(HumanBodyBones.LeftHand).position; var rh = B(HumanBodyBones.RightHand).position; var hp = B(HumanBodyBones.Hips).position;
        Log($"站着：两手离髋的高度 {(hp.y - lh.y):F2}/{(hp.y - rh.y):F2} 米（负的就是手抬着），两手相距 {Vector3.Distance(lh, rh):F2} 米");
        Cmd("{\"cmd\":\"view\",\"kind\":\"top\"}");
        yield return Hold("进殿站着", 1.5f, "stand_top");

        // 2 走动（俯视、平视各走一圈）
        yield return WalkFor("俯视往前", 0, 1, 3);
        yield return WalkFor("俯视往右", 1, 0, 3);
        yield return WalkFor("俯视往左", -1, 0, 3);
        yield return WalkFor("俯视往后", 0, -1, 2.5f);
        Cmd("{\"cmd\":\"view\",\"kind\":\"level\"}");
        yield return new WaitForSeconds(1f);
        yield return WalkFor("平视往前", 0, 1, 3);
        yield return WalkFor("平视往右", 1, 0, 3);

        // 3 去各处
        foreach (var spot in new[] { "tree", "burner", "hall" })
        {
            Cmd($"{{\"cmd\":\"goto\",\"spot\":\"{spot}\"}}");
            yield return Settle("走去 " + spot);
            Shot("goto_" + spot);
        }

        // 4 站着做动作
        foreach (var (act, secs) in new[] { ("pray", 7f), ("bow", 4f), ("kneel", 13f) })
        {
            Cmd($"{{\"cmd\":\"act\",\"action\":\"{act}\"}}");
            yield return Hold("动作 " + act, secs * 0.4f, "act_" + act + "_a");
            yield return Hold("动作 " + act, secs * 0.6f, "act_" + act + "_b");
            yield return Settle("动作结束 " + act, 6f);
        }

        // 5 心意
        Cmd("{\"cmd\":\"goto\",\"spot\":\"tree\"}");
        yield return Settle("走去 tree");
        foreach (var k in new[] { "ribbon", "plaque" })
        {
            Cmd($"{{\"cmd\":\"offer\",\"kind\":\"{k}\"}}");
            yield return Hold("挂" + k, 4f, "offer_" + k);
        }
        Cmd("{\"cmd\":\"goto\",\"spot\":\"burner\"}");
        yield return Settle("走去 burner");
        Cmd("{\"cmd\":\"offer\",\"kind\":\"incense\"}");
        yield return Hold("上香", 5f, "offer_incense");

        // 6 坐下、坐着拜、静坐、起身
        Cmd("{\"cmd\":\"sit\"}");
        // 坐下那几秒：每 0.25 秒记髋和两脚相对蒲团中心的位置（看「先站在草垫上再坐下」对不对）
        {
            var folkC = player.GetComponentInChildren(System.Type.GetType("Yuanjing.Folk, Assembly-CSharp"));
            var fAct = folkC.GetType().GetField("actNow", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            for (float w = 0; w < 30 && (string)fAct.GetValue(folkC) != "Sit_Down"; w += Time.deltaTime) { yield return null; Measure("走去坐下"); }
            Vector3 seatC = Vector3.zero; float bestD = 99;
            foreach (var c in Cushions) { float d = Vector3.Distance(c, player.transform.position); if (d < bestD) { bestD = d; seatC = c; } }
            for (int k = 0; k < 12; k++)
            {
                var h = B(HumanBodyBones.Hips).position - seatC; var lfp = B(HumanBodyBones.LeftFoot).position - seatC; var rfp = B(HumanBodyBones.RightFoot).position - seatC;
                Log($"坐下 {k * 0.25f:F2} 秒（{fAct.GetValue(folkC)}）：原点 {(player.transform.position - seatC).ToString("F2")} 髋 {h.ToString("F2")} 左脚 {lfp.ToString("F2")} 右脚 {rfp.ToString("F2")}");
                for (float w = 0; w < 0.25f; w += Time.deltaTime) { yield return null; Measure("坐下"); }
            }
        }
        yield return Settle("走去坐下");
        yield return Hold("坐着", 3f, "sit");
        Cmd("{\"cmd\":\"view\",\"kind\":\"low\"}");
        yield return Hold("坐着", 2f, "sit_low");
        Cmd("{\"cmd\":\"view\",\"kind\":\"level\"}");
        Cmd("{\"cmd\":\"act\",\"action\":\"pray\"}");
        yield return Hold("坐着合掌", 3f, "sit_pray");
        yield return new WaitForSeconds(5f);
        Cmd("{\"cmd\":\"act\",\"action\":\"bow\"}");
        yield return Hold("坐着鞠躬", 3f, "sit_bow");
        Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":1}");
        yield return Hold("起身", 3f, "standup");
        Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":0}");

        // 7 小动物：走到最近的一只跟前，摸、喂
        Transform pet = null; float best = 999;
        foreach (var t in Object.FindObjectsByType<Transform>(FindObjectsSortMode.None))
            if (t.name.StartsWith("Pet_") && t.parent != null && t.parent.name != t.name)
            {
                float d = Vector3.Distance(t.position, player.transform.position);
                if (d < best) { best = d; pet = t; }
            }
        if (pet != null)
        {
            string id = pet.name.Substring(4);
            var cc = player.GetComponent<CharacterController>();
            cc.enabled = false;
            player.transform.position = pet.position + pet.forward * 1.1f;
            cc.enabled = true;
            yield return new WaitForSeconds(0.5f);
            Cmd($"{{\"cmd\":\"petact\",\"id\":\"{id}\",\"action\":\"pet\",\"seat\":1}}");
            yield return Hold("摸" + id, 2.5f, "pet_" + id);
            Cmd($"{{\"cmd\":\"petact\",\"id\":\"{id}\",\"action\":\"feed\",\"seat\":1}}");
            yield return Hold("喂" + id, 3f, "feed_" + id);
            // 小动物的脚：贴地吗
            var petAnim = pet.GetComponentInChildren<Animation>();
            float lowest = 99;
            foreach (var t in pet.GetComponentsInChildren<Transform>())
                if (t.name.Contains("Foot") || t.name.StartsWith("FF") || t.name.Contains("LowerLeg")) lowest = Mathf.Min(lowest, t.position.y - SurfaceAt(t.position));
            Log($"小动物 {id}：最低的脚离地 {lowest:F3} 米（负的是陷进地里）");
        }
        Cmd("{\"cmd\":\"feed\",\"kind\":\"birds\"}");
        yield return Hold("喂鸟", 4f, "feed_birds");

        // 8 视角、放大、天气
        foreach (var v in new[] { "top", "level", "low", "first" })
        {
            Cmd($"{{\"cmd\":\"view\",\"kind\":\"{v}\"}}");
            yield return Hold("视角 " + v, 1.5f, "view_" + v);
        }
        Cmd("{\"cmd\":\"view\",\"kind\":\"level\"}");
        Cmd("{\"cmd\":\"zoom\",\"x\":3}");
        yield return Hold("放大", 1.5f, "zoom3");
        Cmd("{\"cmd\":\"zoom\",\"x\":1}");
        foreach (var (time, weather) in new[] { ("dusk", "clear"), ("night", "clear"), ("day", "rain"), ("day", "snow") })
        {
            Cmd($"{{\"cmd\":\"sky\",\"time\":\"{time}\",\"weather\":\"{weather}\",\"instant\":true}}");
            yield return Hold("天气 " + time + weather, 1.5f, "sky_" + time + "_" + weather);
        }

        // 人和人叠在一起
        var people = new List<Transform>();
        foreach (var t in Object.FindObjectsByType<Transform>(FindObjectsSortMode.None)) if (t.name.StartsWith("Pilgrim_")) people.Add(t);
        int overlap = 0;
        for (int a = 0; a < people.Count; a++)
            for (int b = a + 1; b < people.Count; b++)
            {
                Vector3 d = people[a].position - people[b].position; d.y = 0;
                if (d.magnitude < 0.3f) overlap++;
            }
        Log($"最后：场上 {people.Count} 人，叠在一起的 {overlap} 对");

        Log("── 各项最差 ──");
        foreach (var kv in worst) if (!kv.Key.StartsWith("_")) Log($"{kv.Key}：{kv.Value.v:F3}（{kv.Value.where}）");
        File.WriteAllText("../shots/play/report.txt", report.ToString());
        Assert.Pass();
    }
}
