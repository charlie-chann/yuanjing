using System.Collections;
using System.IO;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
using System.Linq;
using System.Reflection;

/// 新的操作和靠近互动走一遍，每步拍一张：自由环绕（平看、俯视、拉远）、站到猫狗跟前聚焦、喂小鸟、敲钟、钓鱼、殿里俯视。
/// 图在 unity/shots/orbit/，Unity 发给 Flutter 的消息记在 log.txt
public class OrbitPlayTest
{
    [UnityTest]
    public IEnumerator Play()
    {
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        var bridge = GameObject.Find("Bridge");
        var log = new System.Text.StringBuilder();
        // 测试的程序集引用不到游戏脚本：按名字找组件、用反射取值
        const BindingFlags BF = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;
        object Get(object o, string n) { var t = o.GetType(); var f = t.GetField(n, BF); return f != null ? f.GetValue(o) : t.GetProperty(n, BF).GetValue(o); }
        MonoBehaviour[] All(string type) => Object.FindObjectsByType<MonoBehaviour>(FindObjectsSortMode.None).Where(m => m.GetType().Name == type).ToArray();
        var bt = bridge.GetComponent("Bridge").GetType();
        bt.GetEvent("Sent").AddEventHandler(null, (System.Action<string>)(s => log.AppendLine($"{Time.time:F1} {s}")));
        void Cmd(string json) => bridge.SendMessage("OnMessage", json);
        Cmd("{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"测试\"}");
        var cam = Camera.main;
        const int W = 540, H = 1170;
        var rt = new RenderTexture(W, H, 24) { antiAliasing = 4 };
        var tex = new Texture2D(W, H, TextureFormat.RGB24, false);
        Directory.CreateDirectory("../shots/orbit");
        void Shot(string n)
        {
            cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
            RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, W, H), 0, 0); RenderTexture.active = null;
            File.WriteAllBytes($"../shots/orbit/{n}.png", tex.EncodeToPNG());
        }
        var gd = All("GameDirector")[0];
        var player = (MonoBehaviour)Get(gd, "player");
        var pcam = Get(gd, "cam");
        Vector3 bellAt = (Vector3)Get(gd, "bellAt"), pondCenter = (Vector3)Get(gd, "pondCenter"), doorIn = (Vector3)Get(gd, "hallDoorIn");
        float hallFloor = (float)Get(gd, "hallFloor");
        IEnumerator Wait(float s) { float t0 = Time.time; while (Time.time - t0 < s) yield return null; }
        void Place(Vector3 p, float yaw)
        {
            if (Physics.Raycast(p + Vector3.up * 3f, Vector3.down, out var hit, 8f, ~(1 << 2), QueryTriggerInteraction.Ignore)) p.y = hit.point.y;
            // 人（Folk）是 Player（带碰撞胶囊的那个）的子物体：要挪的是 Player，不然子物体和胶囊错开，后面坐下、自动走都按胶囊算，人就飞到别处去了
            var root = GameObject.Find("Player");
            var cc = root.GetComponent<CharacterController>();
            bool was = cc.enabled;
            cc.enabled = false;
            root.transform.position = p;
            player.transform.localPosition = Vector3.zero;
            cc.enabled = was;
            player.transform.rotation = Quaternion.Euler(0, yaw, 0);
            player.GetType().GetMethod("FaceYaw").Invoke(player, new object[] { yaw });
            Physics.SyncTransforms();
            pcam.GetType().GetMethod("Snap").Invoke(pcam, new object[] { yaw });
        }
        yield return Wait(1.5f);
        Shot("01_start");
        // 拖屏：往上抬到俯视，再拉远
        for (int i = 0; i < 20; i++) { Cmd("{\"cmd\":\"look\",\"dx\":0.02,\"dy\":-0.04}"); yield return null; }
        yield return Wait(1.2f); Shot("02_look_down");
        Cmd("{\"cmd\":\"reach\",\"x\":3.6}");
        yield return Wait(1.5f); Shot("03_far_topdown");
        Cmd("{\"cmd\":\"reach\",\"x\":1}");
        for (int i = 0; i < 20; i++) { Cmd("{\"cmd\":\"look\",\"dx\":0,\"dy\":0.03}"); yield return null; }
        // 摇杆往前走两秒
        Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":1}");
        yield return Wait(2f); Shot("04_walking");
        Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":0}");
        // 站到一只小动物跟前
        var pet = All("Critter").FirstOrDefault(c => (string)Get(c, "id") == "tangerine");
        if (pet != null)
        {
            Place(pet.transform.position + new Vector3(0.9f, 0, -1.1f), -40f);
            yield return Wait(2.2f); Shot("05_pet_focus");
            Cmd("{\"cmd\":\"petact\",\"id\":\"tangerine\",\"action\":\"pet\",\"seat\":1}");
            yield return Wait(1.6f); Shot("06_pet_stroke");
            Cmd("{\"cmd\":\"petact\",\"id\":\"tangerine\",\"action\":\"feed\",\"seat\":1,\"item\":\"crucian\"}");
            yield return Wait(2.0f); Shot("07_pet_feed");
        }
        // 小鸟
        var bird = All("Bird").FirstOrDefault(b => (bool)Get(b, "Grounded"));
        if (bird != null)
        {
            Place(bird.transform.position + new Vector3(0, 0, -3.5f), 0f);
            yield return Wait(1.0f); Shot("08_bird_near");
            Cmd("{\"cmd\":\"feed\",\"kind\":\"birds\"}");
            yield return Wait(4.5f); Shot("09_bird_feed");
        }
        // 钟亭
        Place(bellAt + new Vector3(-2.4f, 0, 0), 90f);
        yield return Wait(1.0f); Shot("10_bell_near");
        Cmd("{\"cmd\":\"ring\"}");
        yield return Wait(1.3f); Shot("11_bell_ring");
        yield return Wait(3.5f);
        // 钓鱼：池塘边
        Place(pondCenter + new Vector3(-4.3f, 0, 0.4f), 90f);
        yield return Wait(1.0f); Shot("12_pond_near");
        Cmd("{\"cmd\":\"fish\",\"action\":\"cast\"}");
        yield return Wait(0.45f); Shot("13_fish_swing");
        yield return Wait(1.6f); Shot("14_fish_wait");
        var fishing = Get(gd, "fishing"); fishing.GetType().GetField("waitRange").SetValue(fishing, new Vector2(0.5f, 0.6f));
        float t1 = Time.time;
        while (!log.ToString().Contains("\"bite\"") && Time.time - t1 < 14f) yield return null;
        yield return Wait(0.3f); Shot("15_fish_bite");
        Cmd("{\"cmd\":\"fish\",\"action\":\"reel\"}");
        yield return Wait(0.6f);
        Cmd("{\"cmd\":\"fish\",\"action\":\"show\",\"kind\":\"goldfish\"}");
        yield return Wait(2.2f); Shot("16_fish_show");
        Cmd("{\"cmd\":\"fish\",\"action\":\"stop\"}");
        yield return Wait(1.2f);
        // 码头上钓（湖）
        Place(new Vector3(0.6f, 0.07f, -22f), 90f);
        yield return Wait(1.0f);
        Cmd("{\"cmd\":\"fish\",\"action\":\"cast\"}");
        yield return Wait(2.6f); Shot("17_dock_fishing");
        Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":1}"); yield return Wait(0.3f); Cmd("{\"cmd\":\"move\",\"x\":0,\"y\":0}");
        // 殿里：平看、俯视
        Place(new Vector3(0, hallFloor, doorIn.z + 1.2f), 0f);
        yield return Wait(1.5f); Shot("18_hall_level");
        for (int i = 0; i < 24; i++) { Cmd("{\"cmd\":\"look\",\"dx\":0,\"dy\":-0.04}"); yield return null; }
        Cmd("{\"cmd\":\"reach\",\"x\":3}");
        yield return Wait(1.5f); Shot("19_hall_topdown");
        // 殿中央：平看佛像、压到俯视拉远（看得到 20 个垫子）
        Cmd("{\"cmd\":\"reach\",\"x\":1}");
        Place(new Vector3(0, hallFloor, 25.6f), 0f);
        yield return Wait(1.5f); Shot("20_hall_center");
        for (int i = 0; i < 26; i++) { Cmd("{\"cmd\":\"look\",\"dx\":0,\"dy\":-0.04}"); yield return null; }
        Cmd("{\"cmd\":\"reach\",\"x\":4.2}");
        yield return Wait(2.0f); Shot("21_hall_center_topdown");
        Assert.Less(cam.transform.position.y, 12.75f, "殿里俯视镜头穿了天花");
        Cmd("{\"cmd\":\"reach\",\"x\":1}");
        // 观音像前
        Place(new Vector3(-13.6f, hallFloor, 28.8f), 270f);
        yield return Wait(1.5f); Shot("22_guanyin");
        // 拜垫上跪拜、蒲团上坐
        Place(new Vector3(0.2f, hallFloor, 28.4f), 0f);
        yield return Wait(1.0f);
        Assert.IsTrue(log.ToString().Contains("\"mat\":1"), "站到中间拜垫跟前没有报 mat");
        Cmd("{\"cmd\":\"act\",\"action\":\"kneel\",\"mat\":1}");
        yield return Wait(7f); Shot("23_kneel");
        yield return Wait(14f);
        Place(new Vector3(2.5f, hallFloor, 27.3f), 180f);
        yield return Wait(1.0f);
        Cmd("{\"cmd\":\"sit\",\"seat\":-1}");
        yield return Wait(6f); Shot("24_hall_sit");
        Assert.Less(Vector3.Distance(player.transform.position, new Vector3(2.4f, hallFloor, 26.4f)), 0.3f, "没坐在殿里那个蒲团上");
        Cmd("{\"cmd\":\"stand\"}");
        yield return Wait(4f);
        // 院子里隔着门看殿里的大佛
        Place(new Vector3(0, 0.07f, 5.0f), 0f);
        yield return Wait(1.5f); Shot("25_court_to_door");
        // 殿前抬高镜头、拉远：屋檐镂空
        Place(new Vector3(3f, 0.07f, 8.4f), 0f);
        for (int i = 0; i < 16; i++) { Cmd("{\"cmd\":\"look\",\"dx\":0,\"dy\":-0.04}"); yield return null; }
        Cmd("{\"cmd\":\"reach\",\"x\":3.6}");
        yield return Wait(1.8f); Shot("26_court_high");
        // 前廊上（屋檐底下）抬高镜头
        Place(new Vector3(-12f, hallFloor, 13.0f), 0f);
        yield return Wait(1.8f); Shot("27_porch_high");
        Cmd("{\"cmd\":\"reach\",\"x\":1}");
        for (int i = 0; i < 16; i++) { Cmd("{\"cmd\":\"look\",\"dx\":0,\"dy\":0.04}"); yield return null; }
        // 石凳：走到跟前显示「坐下」，坐下、起身
        int nBefore = log.Length;
        File.WriteAllText("../shots/orbit/log.txt", log.ToString());
        // 挑一个没人坐的座位（内置香客也会坐石凳）
        var pil = Get(gd, "pilgrims");
        int free = -1, seatN = (int)Get(pil, "SeatCount");
        for (int i = 0; i < seatN && free < 0; i++)
            if (!(bool)pil.GetType().GetMethod("Taken").Invoke(pil, new object[] { i })) free = i;
        Assert.GreaterOrEqual(free, 0, "石凳全坐满了");
        Vector3 seatAt = ((Transform)pil.GetType().GetMethod("Seat").Invoke(pil, new object[] { free })).position;
        Place(new Vector3(seatAt.x + 0.1f, 0.07f, seatAt.z + 1.0f), 180f);
        yield return Wait(1.2f);
        File.WriteAllText("../shots/orbit/log.txt", log.ToString());
        Assert.IsTrue(log.ToString(nBefore, log.Length - nBefore).Contains($"\"seat\":{free},"), $"走到石凳跟前没有报 seat {free}");
        Shot("28_bench_near");
        Cmd("{\"cmd\":\"sit\",\"seat\":-1}");
        yield return Wait(4.5f); Shot("29_bench_sit");
        Assert.IsTrue(log.ToString().Contains("\"seated\""), "没坐上石凳");
        for (int i = 0; i < 30; i++) { Cmd("{\"cmd\":\"look\",\"dx\":0.03,\"dy\":0.01}"); yield return null; }
        yield return Wait(1.0f); Shot("30_bench_sit_front");
        Cmd("{\"cmd\":\"stand\"}");
        yield return Wait(2.5f); Shot("31_bench_stood");
        Assert.Less(player.transform.position.y, 0.2f, "起身以后人还在凳面上");
        // 北边新地块、殿后
        Place(new Vector3(-26f, 0f, 30f), 0f);
        yield return Wait(1.5f); Shot("32_west_side");
        Place(new Vector3(0f, 0f, 45.8f), 180f);
        for (int i = 0; i < 12; i++) { Cmd("{\"cmd\":\"look\",\"dx\":0,\"dy\":-0.04}"); yield return null; }
        Cmd("{\"cmd\":\"reach\",\"x\":3}");
        yield return Wait(1.8f); Shot("33_behind_hall");
        File.WriteAllText("../shots/orbit/log.txt", log.ToString());
        Assert.Pass();
    }
}
