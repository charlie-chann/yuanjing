using System.Collections;
using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 新大殿的碰撞（BuildHall.cs）：用摇杆（同真人操作，走 CharacterController）从石台走上台阶、穿过廊下、从中门进殿，
/// 走遍殿里该走得到的地方（props.md §5 的几条通道、拜垫、两个金柱之间、敲磬木鱼和读经站的地方），再从西边的门出来、下台阶。
/// 每一段量：走不走得到（卡住就失败）、脚下的高度（台阶、廊下 0.735、殿里 0.72、拜垫上 0.844）。
/// 另外：还不让进殿时门口那道隔板挡不挡人；往墙、供桌上推挡不挡得住。
public class HallWalkTest
{
    GameObject bridge, player;

    void Stick(Vector2 v) => bridge.SendMessage("OnMessage", "{\"cmd\":\"move\",\"x\":" + v.x.ToString("F3", System.Globalization.CultureInfo.InvariantCulture)
                                                           + ",\"y\":" + v.y.ToString("F3", System.Globalization.CultureInfo.InvariantCulture) + "}");

    /// 世界里的方向换成摇杆值。GameDirector 按住摇杆时用按下那一刻镜头的朝向（stickYaw）算方向：殿里锁成平视以后镜头跟着人转，
    /// 按此刻的镜头算会越走越偏（真人看着画面会自己修正手指），所以按着的时候照它记下的那个朝向换算
    Vector2 ToStick(Vector3 worldDir)
    {
        float yaw = Camera.main != null ? Camera.main.transform.eulerAngles.y : 0f;
        var gdType = System.Type.GetType("Yuanjing.GameDirector, Assembly-CSharp");
        var gd = gdType?.GetProperty("Instance")?.GetValue(null);
        const System.Reflection.BindingFlags F = System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
        if (gd != null && (bool)gdType.GetField("stickHeld", F).GetValue(gd)) yaw = (float)gdType.GetField("stickYaw", F).GetValue(gd);
        Vector3 d = Quaternion.Euler(0, -yaw, 0) * worldDir;
        return new Vector2(d.x, d.z).normalized;
    }

    readonly List<string> fails = new List<string>();

    IEnumerator WalkTo(string name, float x, float z, float wantY, float tol = 0.03f)
    {
        var target = new Vector3(x, 0, z);
        float best = float.MaxValue, bestAt = Time.time, t0 = Time.time;
        while (true)
        {
            Vector3 p = player.transform.position;
            Vector3 d = target - p;
            d.y = 0;
            if (d.magnitude < 0.2f) break;
            if (d.magnitude < best - 0.05f) { best = d.magnitude; bestAt = Time.time; }
            if (Time.time - bestAt > 4f || Time.time - t0 > 25f)
            {
                fails.Add($"{name} 走不到：卡在 ({p.x:F2}, {p.y:F2}, {p.z:F2})，还差 {d.magnitude:F2} 米");
                Debug.Log($"[yuanjing] 殿里走路 {name}：卡在 ({p.x:F2}, {p.y:F2}, {p.z:F2})，还差 {d.magnitude:F2} 米");
                Stick(Vector2.zero);
                yield return new WaitForSeconds(0.6f);
                // 卡住了就直接放到目标点，后面的段照样测
                player.transform.position = new Vector3(x, wantY + 0.05f, z);
                Physics.SyncTransforms();
                yield return new WaitForSeconds(0.3f);
                yield break;
            }
            Stick(ToStick(d.normalized * Mathf.Min(1f, 0.4f + d.magnitude)));
            yield return null;
        }
        Stick(Vector2.zero);
        yield return new WaitForSeconds(0.7f);
        Vector3 q = player.transform.position;
        bool ok = Mathf.Abs(q.y - wantY) <= tol;
        if (!ok) fails.Add($"{name} 脚下高 {q.y:F3}，应该 {wantY:F3}");
        Debug.Log($"[yuanjing] 殿里走路 {name}：到 ({q.x:F2}, {q.y:F3}, {q.z:F2}) 用 {Time.time - t0:F1} 秒{(ok ? "" : $"，高度不对（应该 {wantY:F3}）")}");
    }

    IEnumerator Push(string name, Vector3 dir, float seconds, System.Func<Vector3, bool> ok, string want)
    {
        for (float t = 0; t < seconds; t += Time.deltaTime)
        {
            Stick(ToStick(dir));
            yield return null;
        }
        Stick(Vector2.zero);
        yield return new WaitForSeconds(0.6f);
        Vector3 q = player.transform.position;
        bool good = ok(q);
        if (!good) fails.Add($"{name}：停在 ({q.x:F2}, {q.y:F2}, {q.z:F2})，应该 {want}");
        if (!good)
        {
            // 排查：人的胶囊往前（推的方向）挪 0.1 米碰到哪些碰撞体
            var cc = player.GetComponent<CharacterController>();
            Vector3 c = q + cc.center + dir.normalized * 0.1f;
            float half = Mathf.Max(0f, cc.height * 0.5f - cc.radius);
            var hit = Physics.OverlapCapsule(c + Vector3.up * half, c - Vector3.up * half, cc.radius, ~0, QueryTriggerInteraction.Ignore);
            Debug.Log($"[yuanjing] 殿里走路 {name}：往前 0.1 米碰到 {string.Join("、", System.Array.ConvertAll(hit, h => h.name + "@" + h.bounds.center.ToString("F2")))}");
        }
        Debug.Log($"[yuanjing] 殿里走路 {name}：停在 ({q.x:F2}, {q.y:F3}, {q.z:F2}) {(good ? "挡住了" : "没挡住，应该 " + want)}");
    }

    [UnityTest, Timeout(900000)]
    public IEnumerator WalkThroughHall()
    {
        fails.Clear();      // 同一个测试类的几个测试共用一个实例
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        bridge = GameObject.Find("Bridge");
        bridge.SendMessage("OnMessage", "{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"测试\"}");
        yield return new WaitForSeconds(2f);
        player = GameObject.Find("Player");
        player.transform.position = new Vector3(0, 0.12f, 8.6f);
        Physics.SyncTransforms();
        yield return new WaitForSeconds(0.5f);

        yield return WalkTo("台阶上", 0, 10.75f, 0.697f, 0.04f);
        yield return WalkTo("廊下", 0, 13.6f, 0.735f);
        // 还不让进殿（HallOpen 为 false）：门口有一道只挡人的隔板
        var shut = GameObject.Find("World/Structure/hall/Colliders/DoorShut");
        if (shut != null)
        {
            yield return Push("门口的隔板", Vector3.forward, 2.5f, q => q.z < 14.0f, "z < 14.0");
            shut.SetActive(false);
            Physics.SyncTransforms();
        }
        else Debug.Log("[yuanjing] 殿里走路：没有门口的隔板（HallOpen 已经是 true）");
        yield return WalkTo("中门里", 0, 15.3f, 0.72f);
        yield return WalkTo("过道", 0, 16.9f, 0.72f);
        yield return WalkTo("东边两根金柱之间", 2.8f, 16.7f, 0.72f);
        yield return WalkTo("东边静坐区北边", 4.6f, 18.43f, 0.72f);
        yield return WalkTo("敲磬的地方", 5.0f, 18.43f, 0.72f);
        yield return WalkTo("敲木鱼的地方", 5.8f, 18.45f, 0.72f);
        yield return WalkTo("东边拜垫上", 3.6f, 18.5f, 0.844f);
        yield return WalkTo("东边拜垫前的通道", 2.4f, 18.68f, 0.72f);
        yield return WalkTo("供桌前那一条", 1.4f, 18.5f, 0.72f);
        yield return WalkTo("上香站的地方", 0, 18.52f, 0.72f);
        yield return Push("往供桌上推", Vector3.forward, 2.0f, q => q.z < 18.8f - 0.18f, "z < 18.62");
        yield return WalkTo("中间拜垫上", 0, 17.8f, 0.844f);
        yield return WalkTo("西边拜垫前的通道", -2.4f, 18.68f, 0.72f);
        yield return WalkTo("西边拜垫上", -3.6f, 18.5f, 0.844f);
        yield return WalkTo("西边两根金柱之间", -2.8f, 16.7f, 0.72f);
        yield return WalkTo("读经站的地方", -5.35f, 18.42f, 0.72f);
        // 外侧一列蒲团的方草垫到 x -5.93，离墙还有 0.5 米多：贴墙走（踩到草垫边上就高 5 厘米，也算对）
        yield return WalkTo("西边静坐区外侧", -6.2f, 16.4f, 0.745f, 0.03f);
        yield return Push("往西墙上推", Vector3.left, 2.0f, q => q.x > -6.47f + 0.18f, "x > -6.29");
        yield return WalkTo("西边两根金柱之间（往东）", -2.0f, 16.4f, 0.72f);
        // 西门正对着金柱的柱础：从柱础东边、门扇西边那条（0.6 米多宽）走
        yield return WalkTo("西边的门里", -2.1f, 14.8f, 0.72f);
        yield return WalkTo("西门外的廊下", -2.6f, 13.6f, 0.735f);
        // 廊下的柱子在 z 12.5：先往南走到柱子外面，再往中间
        yield return WalkTo("廊下柱子南边", -2.6f, 11.8f, 0.735f);
        yield return WalkTo("廊下中间", 0, 11.8f, 0.735f);
        // 东门：功德箱以前正挡在门里（离金柱的柱础只有 0.11 米），真人一直往上推摇杆就顶在箱子上进不去。
        // 箱子挪到门里偏西（x 1.19..1.71）以后，门正对着的金柱柱础东边、箱子西边都有路：一直往北推，绕过柱础进殿
        // 从固定的一点推（以前接着上一段走到的地方推，差一两寸就顶在金柱的柱础上，一会儿过一会儿不过）；各个 x 的扫一遍见 SideDoors
        player.transform.position = new Vector3(2.1f, 0.78f, 13.4f);
        Physics.SyncTransforms();
        yield return new WaitForSeconds(0.8f);
        yield return Push("从东门一直往北推", Vector3.forward, 5f, q => q.z > 15.9f, "进到殿里（z > 15.9）");
        yield return WalkTo("东边的门里", 2.1f, 14.8f, 0.72f);
        yield return WalkTo("东门外的廊下（出来）", 2.6f, 13.6f, 0.735f);
        yield return WalkTo("廊下柱子南边（东）", 2.6f, 11.8f, 0.735f);
        yield return WalkTo("廊下中间（回来）", 0, 11.8f, 0.735f);
        yield return WalkTo("下台阶", 0, 9.0f, 0.07f, 0.05f);
        Stick(Vector2.zero);
        Debug.Log($"[yuanjing] 殿里走路：{fails.Count} 处不对 {string.Join("；", fails)}");
        Assert.IsEmpty(fails, string.Join("；", fails));
    }

    /// 东、西两个侧门：从廊下不同的 x（门洞 1.95–3.15，正对着金柱的柱础那几条也在内）一直往北推摇杆 6 秒，都要进到殿里。
    /// 金柱的柱础正对着侧门：推上去人是贴着圆柱础往旁边滑过去的，不能被当成撞墙停下（Folk 的「挡住了」以前只看往前挪了多少）
    [UnityTest, Timeout(900000)]
    public IEnumerator SideDoors()
    {
        fails.Clear();
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        bridge = GameObject.Find("Bridge");
        bridge.SendMessage("OnMessage", "{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"测试\"}");
        yield return new WaitForSeconds(2f);
        player = GameObject.Find("Player");
        bridge.SendMessage("OnMessage", "{\"cmd\":\"view\",\"kind\":\"level\"}");
        int ok = 0, n = 0;
        foreach (float sx in new[] { 1f, -1f })
            foreach (float ax in new[] { 1.95f, 2.15f, 2.35f, 2.55f, 2.7f, 2.85f, 3.0f, 3.15f })
            {
                float x = sx * ax;
                player.transform.SetPositionAndRotation(new Vector3(x, 0.78f, 13.2f), Quaternion.identity);
                Physics.SyncTransforms();
                yield return new WaitForSeconds(1.0f);
                for (float t = 0; t < 6f; t += Time.deltaTime)
                {
                    Stick(ToStick(Vector3.forward));
                    yield return null;
                }
                Stick(Vector2.zero);
                yield return new WaitForSeconds(0.5f);
                Vector3 q = player.transform.position;
                n++;
                bool good = q.z > 15.9f;
                if (good) ok++;
                else fails.Add($"{(sx > 0 ? "东" : "西")}门 x {x:F2} 一直往北推：停在 ({q.x:F2}, {q.z:F2})");
                Debug.Log($"[yuanjing] 殿里走路 侧门 {(sx > 0 ? "东" : "西")}门 x {x:F2}：一直往北推 6 秒 → ({q.x:F2}, {q.z:F2}) {(good ? "进去了" : "停住了")}");
            }
        Debug.Log($"[yuanjing] 殿里走路 侧门：一直往北推进去 {ok}/{n}");
        Assert.IsEmpty(fails, string.Join("；", fails));
    }
}
