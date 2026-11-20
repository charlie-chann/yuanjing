using System.Collections;
using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 大殿的碰撞（BuildHall.cs，2026-11-19 扩建后的九间大殿）：用摇杆（同真人操作，走 CharacterController）从石台走上台阶、穿过前廊、从中门进殿，
/// 走遍殿里该走得到的地方（前槽、中厅、两边侧廊、拜垫、供桌前、敲磬木鱼和读经站的地方、扇面墙后面的后廊绕佛一圈），再从东、西次间的门进出、下台阶。
/// 每一段量：走不走得到（卡住就失败）、脚下的高度（台阶、台面 1.08、殿里 1.07、拜垫上 1.194）。
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
        player.transform.position = new Vector3(0, 0.12f, 8.2f);
        Physics.SyncTransforms();
        yield return new WaitForSeconds(0.5f);

        // 高度：台面 1.08、殿里金砖地 1.07、拜垫面 1.194（HALL_V2.md；2026-11-19 扩建后的九间大殿）
        const float deck = 1.08f, floor = 1.07f, mat = 1.194f;
        // 台阶中段（走到离目标 0.2 米就停：z 10.05..10.45，第四、五级，高 0.617 / 0.771）
        yield return WalkTo("台阶中段", 0, 10.25f, 0.70f, 0.17f);
        yield return WalkTo("前廊", 0, 14.5f, deck);
        // 还不让进殿（HallOpen 为 false）：门口有一道只挡人的隔板
        var shut = GameObject.Find("World/Structure/hall/Colliders/DoorShut");
        if (shut != null)
        {
            yield return Push("门口的隔板", Vector3.forward, 2.5f, q => q.z < 16.4f, "z < 16.4");
            shut.SetActive(false);
            Physics.SyncTransforms();
        }
        else Debug.Log("[yuanjing] 殿里走路：没有门口的隔板（HallOpen 已经是 true）");
        yield return WalkTo("中门里（跨过门槛）", 0, 17.8f, floor);
        yield return WalkTo("前槽", 0, 19.6f, floor);
        yield return WalkTo("前排金柱之间", 7.0f, 21.42f, floor);
        yield return WalkTo("中厅蒲团东边", 8.6f, 25.6f, floor);
        yield return WalkTo("东侧廊", 17.0f, 25.6f, floor);
        yield return WalkTo("东墙供桌前", 18.0f, 28.8f, floor);
        yield return Push("往东墙的供桌上推", Vector3.right, 2.0f, q => q.x < 18.9f - 0.18f, "x < 18.72");
        yield return WalkTo("东侧廊（回来）", 16.4f, 26.6f, floor);
        yield return WalkTo("金柱和木鱼之间", 13.25f, 27.6f, floor);
        yield return WalkTo("敲木鱼的地方", 12.5f, 29.75f, floor);
        yield return WalkTo("敲磬的地方", 11.6f, 29.75f, floor);
        yield return WalkTo("东边拜垫上", 7.0f, 29.2f, mat);
        yield return WalkTo("供桌前那一条", 2.4f, 29.95f, floor);
        yield return WalkTo("上香站的地方", 0, 29.92f, floor);
        yield return Push("往供桌上推", Vector3.forward, 2.0f, q => q.z < 30.217f - 0.18f, "z < 30.04");
        yield return WalkTo("中间拜垫上", 0, 29.2f, mat);
        yield return WalkTo("拜垫后面", -3.0f, 28.0f, floor);
        yield return WalkTo("西边拜垫上", -7.0f, 29.2f, mat);
        yield return WalkTo("读经站的地方", -12.0f, 29.75f, floor);
        yield return WalkTo("观音像的供桌前", -15.2f, 28.3f, floor);
        yield return WalkTo("西侧廊", -17.0f, 24.6f, floor);
        yield return Push("往西墙上推", Vector3.left, 3.0f, q => q.x > -20.44f + 0.18f, "x > -20.26");
        // 绕佛一圈：从西边金柱和经案之间往北，走扇面墙后面的后廊，从东边回来
        yield return WalkTo("西侧廊（回来）", -16.0f, 25.2f, floor);
        yield return WalkTo("西边金柱和经案之间", -13.2f, 27.4f, floor);
        yield return WalkTo("佛坛西头", -13.2f, 34.0f, floor);
        yield return WalkTo("后廊西头", -12.4f, 38.5f, floor);
        yield return Push("往扇面墙背面推", Vector3.back, 2.0f, q => q.z > 36.43f + 0.18f, "z > 36.61");
        yield return WalkTo("后廊正中", 0, 38.5f, floor);
        yield return WalkTo("后廊东头", 12.4f, 38.5f, floor);
        yield return WalkTo("佛坛东头", 13.2f, 34.0f, floor);
        yield return WalkTo("东边金柱和木鱼之间（回来）", 13.25f, 27.4f, floor);
        yield return WalkTo("中厅蒲团东边（回来）", 8.6f, 22.6f, floor);
        yield return WalkTo("东次间的门里", 7.0f, 18.0f, floor);
        yield return WalkTo("东次间门外的前廊", 7.0f, 15.0f, deck);
        // 前廊的柱子在 z 13.3（x ±3.5、±10.5……）：从两根柱子中间往南走到柱子外面，再往中间
        yield return WalkTo("前廊柱子南边", 7.0f, 12.0f, deck);
        yield return WalkTo("台阶顶", 0, 11.8f, deck);
        // 西次间的门：从固定的一点一直往北推摇杆，进到殿里
        player.transform.position = new Vector3(-7.0f, deck + 0.05f, 14.6f);
        Physics.SyncTransforms();
        yield return new WaitForSeconds(0.8f);
        yield return Push("从西次间的门一直往北推", Vector3.forward, 5f, q => q.z > 18.2f, "进到殿里（z > 18.2）");
        yield return WalkTo("西次间的门里", -7.0f, 18.0f, floor);
        yield return WalkTo("西次间门外的前廊", -7.0f, 15.0f, deck);
        yield return WalkTo("前廊柱子南边（西）", -7.0f, 12.0f, deck);
        yield return WalkTo("台阶顶（回来）", 0, 11.8f, deck);
        yield return WalkTo("下台阶", 0, 8.6f, 0.07f, 0.05f);
        Stick(Vector2.zero);
        Debug.Log($"[yuanjing] 殿里走路：{fails.Count} 处不对 {string.Join("；", fails)}");
        Assert.IsEmpty(fails, string.Join("；", fails));
    }

    /// 东、西两个次间的门：从前廊不同的 x（叠着的门扇之间净空 4.25–9.75）一直往北推摇杆 6 秒，都要进到殿里。
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
            foreach (float ax in new[] { 4.5f, 5.0f, 5.75f, 6.5f, 7.0f, 7.75f, 8.5f, 9.0f, 9.5f })
            {
                float x = sx * ax;
                player.transform.SetPositionAndRotation(new Vector3(x, 1.13f, 14.6f), Quaternion.identity);
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
                bool good = q.z > 18.2f;
                if (good) ok++;
                else fails.Add($"{(sx > 0 ? "东" : "西")}门 x {x:F2} 一直往北推：停在 ({q.x:F2}, {q.z:F2})");
                Debug.Log($"[yuanjing] 殿里走路 侧门 {(sx > 0 ? "东" : "西")}门 x {x:F2}：一直往北推 6 秒 → ({q.x:F2}, {q.z:F2}) {(good ? "进去了" : "停住了")}");
            }
        Debug.Log($"[yuanjing] 殿里走路 侧门：一直往北推进去 {ok}/{n}");
        Assert.IsEmpty(fails, string.Join("；", fails));
    }
}
