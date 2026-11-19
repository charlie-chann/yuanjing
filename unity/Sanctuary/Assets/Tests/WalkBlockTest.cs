using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 「去大殿」「去香炉」「去许愿树」时站位上有人：先让三位香客站在那个地点的站位上（一位正站在站位上、两位在旁边），再点「去…」。
/// 要求：一定发 arrived（不会一直走不到、界面一直等），人停在离香客 0.45 米以外、离站位 1.2 米以内，自动走已经结束
/// （near 照常报——到了以后离蒲团一米就有「坐下」）。
/// 另外测兜底：走在路上时把一位香客挪到终点上（站位本来是空的），也要在几秒内算到了。
/// 跑：unity/playtest.sh WalkBlockTest
public class WalkBlockTest
{
    GameObject bridge, player;
    object gd, pilgrims;
    readonly List<string> sent = new List<string>();
    readonly List<string> fails = new List<string>();

    [Serializable]
    class Reply { public string type, spot; public int seat = -999; }

    void OnLog(string c, string st, LogType t)
    {
        if (c.StartsWith("SendToFlutter - ")) sent.Add(c.Substring(16));
    }

    void Cmd(string json) => bridge.SendMessage("OnMessage", json);
    static void Log(string s) => Debug.Log("[yuanjing] 挡路 " + s);

    static object Get(object o, string name)
    {
        var f = o.GetType().GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
        if (f != null) return f.GetValue(o);
        return o.GetType().GetProperty(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance).GetValue(o);
    }
    static void Set(object o, string name, object v) => o.GetType().GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance).SetValue(o, v);
    static float Flat(Vector3 a, Vector3 b) => Vector2.Distance(new Vector2(a.x, a.z), new Vector2(b.x, b.z));
    static string F(Vector3 v) => $"({v.x:F2}, {v.y:F2}, {v.z:F2})";

    Vector3 SpotFloor(string name)
    {
        foreach (var s in (Array)Get(gd, "spots"))
            if ((string)Get(s, "name") == name) return (Vector3)Get(s, "floor");
        throw new Exception("没有地点 " + name);
    }

    void Teleport(Vector3 p, float yaw)
    {
        var cc = player.GetComponent<CharacterController>();
        cc.enabled = false;
        player.transform.position = p;
        cc.enabled = true;
        var folk = Get(gd, "player");
        ((Component)folk).transform.rotation = Quaternion.Euler(0, yaw, 0);
        folk.GetType().GetMethod("FaceYaw").Invoke(folk, new object[] { yaw });
        Physics.SyncTransforms();
        var cam = Get(gd, "cam");
        cam.GetType().GetMethod("Snap").Invoke(cam, new object[] { yaw });
    }

    /// 内置香客（id）站到 at，不再走开（下一件事的计时拨到很久以后，站的那一点也记成这里）
    void Park(string id, Vector3 at, Vector3 look)
    {
        var people = (IDictionary)Get(pilgrims, "people");
        var p = people[id];
        var folk = (Component)Get(p, "folk");
        folk.transform.position = at;
        float yaw = Quaternion.LookRotation(new Vector3(look.x - at.x, 0, look.z - at.z)).eulerAngles.y;
        folk.transform.rotation = Quaternion.Euler(0, yaw, 0);
        folk.GetType().GetMethod("StopWalking").Invoke(folk, null);
        folk.GetType().GetMethod("FaceYaw").Invoke(folk, new object[] { yaw });
        Set(p, "next", 9999f);
        Set(p, "lookNext", 9999f);
        Set(p, "target", at);
        Set(p, "atSpot", true);
    }

    IEnumerator WaitArrived(string spot, int since, float secs, Action<Reply, float> got)
    {
        float t0 = Time.time;
        while (Time.time - t0 < secs)
        {
            for (int i = since; i < sent.Count; i++)
            {
                var r = JsonUtility.FromJson<Reply>(sent[i]);
                if (r.type == "arrived") { got(r, Time.time - t0); yield break; }
            }
            yield return null;
        }
        got(null, secs);
    }

    void Check(bool ok, string what)
    {
        if (ok) return;
        fails.Add(what);
        Log("！不对：" + what);
    }

    [UnityTest, Timeout(300000)]
    public IEnumerator BlockedSpots()
    {
        Application.logMessageReceived += OnLog;
        try
        {
            SceneManager.LoadScene("Islet");
            for (int i = 0; i < 10; i++) yield return null;
            bridge = GameObject.Find("Bridge");
            // seed 0：不自动安排人来人往，只有下面摆的几位
            Cmd("{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":0,\"name\":\"我\"}");
            yield return new WaitForSeconds(2f);
            player = GameObject.Find("Player");
            gd = Type.GetType("Yuanjing.GameDirector, Assembly-CSharp").GetProperty("Instance").GetValue(null);
            pilgrims = Get(gd, "pilgrims");
            // 三位内置香客（行程只有一件事：在大殿前站着），一进场就在
            Cmd("{\"cmd\":\"pilgrims\",\"list\":\"blk0:-1:1:木木:h:5:3000|blk1:-1:1:青禾:h:5:3000|blk2:-1:1:予安:h:5:3000\"}");
            yield return new WaitForSeconds(1f);
            var npcs = new[] { "blk0", "blk1", "blk2" };

            // ── 站位上有人：大殿前、香炉前、许愿树下 ──
            foreach (var (spot, start) in new[] { ("hall", new Vector3(0, 0.08f, 1.6f)), ("burner", new Vector3(0, 0.08f, -8.5f)), ("tree", new Vector3(-1.5f, 0.08f, -8.5f)) })
            {
                Vector3 s = SpotFloor(spot);
                Vector3 look = s + (s - start).normalized * 3f;
                Park("blk0", s, look);
                Park("blk1", s + new Vector3(0.5f, 0, 0.1f), look);
                Park("blk2", s + new Vector3(-0.5f, 0, 0.1f), look);
                Teleport(start, Quaternion.LookRotation(s - start).eulerAngles.y);
                yield return new WaitForSeconds(0.8f);
                int n0 = sent.Count;
                Cmd($"{{\"cmd\":\"goto\",\"spot\":\"{spot}\"}}");
                Reply got = null;
                float took = 0;
                yield return WaitArrived(spot, n0, 30f, (r, t) => { got = r; took = t; });
                yield return new WaitForSeconds(1.2f);
                Vector3 me = player.transform.position;
                float closest = float.MaxValue;
                foreach (var id in npcs) closest = Mathf.Min(closest, Flat(((Component)Get(((IDictionary)Get(pilgrims, "people"))[id], "folk")).transform.position, me));
                bool walking = (bool)Get(gd, "autoWalk");
                Log($"{spot}：站位上三个人，{(got != null ? $"{took:F1} 秒到了（arrived {got.spot}）" : "30 秒没到")}，人在 {F(me)}，离站位 {Flat(me, s):F2} 米，离最近的人 {closest:F2} 米，还在自动走 {walking}");
                Check(got != null && got.spot == spot, $"{spot}：站位上有人时没发 arrived {spot}（{got?.spot}）");
                Check(closest >= 0.45f, $"{spot}：挤到人身上了（离最近的人 {closest:F2} 米）");
                Check(Flat(me, s) <= 1.2f, $"{spot}：离站位太远（{Flat(me, s):F2} 米）");
                Check(!walking, $"{spot}：到了以后还在自动走");
            }

            // ── 兜底：站位是空的，走在路上时有人站到了终点上 ──
            {
                Vector3 s = SpotFloor("hall");
                // 香客挪开
                Park("blk0", new Vector3(-6f, 0.07f, 1.0f), s);
                Park("blk1", new Vector3(-6.8f, 0.07f, 1.0f), s);
                Park("blk2", new Vector3(-7.6f, 0.07f, 1.0f), s);
                Vector3 start = new Vector3(0, 0.08f, 1.6f);
                Teleport(start, 0);
                yield return new WaitForSeconds(0.8f);
                int n0 = sent.Count;
                Cmd("{\"cmd\":\"goto\",\"spot\":\"hall\"}");
                yield return null;
                Vector3 goal = (Vector3)Get(gd, "walkGoal");
                // 走到离终点两米时，一个人站到终点上
                float t0 = Time.time;
                while (Flat(player.transform.position, goal) > 2f && Time.time - t0 < 15f) yield return null;
                Park("blk0", goal, goal + Vector3.forward);
                Reply got = null;
                float took = 0;
                yield return WaitArrived("hall", n0, 20f, (r, t) => { got = r; took = t; });
                yield return new WaitForSeconds(1.2f);
                Vector3 me = player.transform.position;
                bool walking = (bool)Get(gd, "autoWalk");
                Log($"兜底：终点 {F(goal)} 上突然站了人，{(got != null ? $"{took:F1} 秒后到了（arrived {got.spot}）" : "20 秒没到")}，人在 {F(me)}，离终点 {Flat(me, goal):F2} 米，还在自动走 {walking}");
                Check(got != null && got.spot == "hall", $"兜底：终点被人占了没发 arrived hall（{got?.spot}）");
                Check(took < 8f, $"兜底：等了 {took:F1} 秒才算到");
                Check(Flat(me, goal) <= 1.0f && !walking, $"兜底：离终点 {Flat(me, goal):F2} 米、还在走 {walking}");

                // 到了以后 near 照常报：站到 25 号蒲团前一米，要报这个蒲团
                n0 = sent.Count;
                int seat = -1;
                for (int i = 0; i < 60 && seat < 0; i++)
                {
                    Vector3 g = (Vector3)gd.GetType().GetMethod("SeatGround", BindingFlags.NonPublic | BindingFlags.Instance).Invoke(gd, new object[] { i });
                    if (Mathf.Abs(g.x - 1.3f) < 0.05f && g.z > 3f) seat = i;
                }
                Vector3 stand = (Vector3)gd.GetType().GetMethod("SeatStand", BindingFlags.NonPublic | BindingFlags.Instance).Invoke(gd, new object[] { seat });
                Vector3 lane = (Vector3)gd.GetType().GetMethod("SeatLane", BindingFlags.NonPublic | BindingFlags.Instance).Invoke(gd, new object[] { seat });
                Vector3 p = new Vector3(stand.x - 0.8f, lane.y + 0.02f, lane.z);
                Teleport(p, 90f);
                yield return new WaitForSeconds(1.2f);
                int nearSeat = -1;
                for (int i = n0; i < sent.Count; i++)
                {
                    var r = JsonUtility.FromJson<Reply>(sent[i]);
                    if (r.type == "near") nearSeat = r.seat;
                }
                Log($"到了以后离 {seat} 号蒲团 {Flat(p, stand):F2} 米：near.seat {nearSeat}");
                Check(nearSeat == seat, $"到了以后 near 没报蒲团 {seat}（{nearSeat}）");
            }
            Log($"对不上的 {fails.Count} 处：{string.Join("；", fails)}");
            Assert.IsEmpty(fails, string.Join("；", fails));
        }
        finally
        {
            Application.logMessageReceived -= OnLog;
        }
    }
}
