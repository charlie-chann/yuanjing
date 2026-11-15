using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 样板角的闪烁测试：人站在许愿树南边的花地前不动，四种视角（俯视、平视、仰视、第一人称）加一次放大，
/// 各连着抓 60 帧，把画面分成 8×12 格，量每一格相邻两帧差多少。
/// 风吹草动是持续的、小的变化；闪烁是某一帧突然跳一下。所以数的是「比这一格平常的变化大出很多」的次数。
/// 每种视角存一张图到 unity/shots/vf_*.png。
public class ViewFlickerTest
{
    const int W = 300, H = 652, GX = 8, GY = 12, Frames = 60;

    [UnityTest]
    public IEnumerator ViewsDoNotFlicker()
    {
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        var bridge = GameObject.Find("Bridge");
        void Cmd(string json) => bridge.SendMessage("OnMessage", json);
        string weather = System.Environment.GetEnvironmentVariable("YJ_WEATHER") ?? "clear";
        Cmd("{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"" + weather + "\",\"seed\":9,\"name\":\"测试\"}");
        yield return new WaitForSeconds(26f);       // 等进场那段自动走路走完

        // 会动的东西先停掉（人、猫狗、鸟、鱼、飘的叶子）：它们经过时画面本来就该变，要量的是「没东西动的地方自己在跳」
        foreach (var t in Object.FindObjectsByType<Transform>(FindObjectsSortMode.None))
            if (t.name.StartsWith("Pilgrim_")) t.gameObject.SetActive(false);
        foreach (var mb in Object.FindObjectsByType<MonoBehaviour>(FindObjectsSortMode.None))
        {
            string tn = mb.GetType().Name;
            if (tn == "Critter" || tn == "Bird" || tn == "Koi" || tn == "Bob" || tn == "Ambience" || tn == "Pilgrims") mb.enabled = false;
        }
        foreach (var ps in Object.FindObjectsByType<ParticleSystem>(FindObjectsSortMode.None))
        {
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            ps.gameObject.SetActive(false);
        }

        var player = GameObject.Find("Player");
        var cc = player.GetComponent<CharacterController>();
        // YJ_HIDE_PLAYER=1：不画自己。人物会眨眼、头发会摆，这些是正常的动；隐藏以后还跳的才是环境在闪
        if (System.Environment.GetEnvironmentVariable("YJ_HIDE_PLAYER") == "1")
            foreach (var r in player.GetComponentsInChildren<Renderer>()) r.forceRenderingOff = true;
        void Stand(float x, float z, float yaw)
        {
            cc.enabled = false;
            player.transform.position = new Vector3(x, 0.08f, z);
            player.transform.GetChild(0).localRotation = Quaternion.Euler(0, yaw, 0);
            cc.enabled = true;
        }

        Time.captureFramerate = 30;
        var cam = Camera.main;
        var rt = new RenderTexture(W, H, 24) { antiAliasing = 1 };
        var tex = new Texture2D(W, H, TextureFormat.RGB24, false);
        Directory.CreateDirectory("../shots");
        var report = new StringBuilder();
        int worst = 0;

        // 两个站位：草地上朝着许愿树（看树、看草）；绳圈南边朝着那一小片花（低头凑近看花）
        var cases = new (string name, string view, float zoom, float lookDy, float x, float z, float yaw)[]
        {
            ("top", "top", 1f, 0f, -6.4f, -7.0f, -50f),
            ("top_zoom", "top", 5f, 0f, -6.4f, -7.0f, -50f),
            ("level", "level", 1f, 0f, -6.4f, -7.0f, -50f),
            ("low", "low", 1f, 0f, -6.4f, -7.0f, -50f),
            ("first", "first", 1f, 0f, -6.4f, -7.0f, -50f),
            ("crouch_flowers", "low", 3f, -0.43f, -8.6f, -6.4f, 180f),     // 蹲着（仰视那一档）把头放平、放大三倍：凑近看花
        };
        foreach (var c in cases)
        {
            Cmd("{\"cmd\":\"view\",\"kind\":\"top\"}");
            Stand(c.x, c.z, c.yaw);
            for (int i = 0; i < 20; i++) yield return null;
            Cmd("{\"cmd\":\"view\",\"kind\":\"" + c.view + "\"}");
            Cmd("{\"cmd\":\"zoom\",\"x\":" + c.zoom.ToString(System.Globalization.CultureInfo.InvariantCulture) + "}");
            if (c.lookDy != 0) Cmd("{\"cmd\":\"look\",\"dx\":0,\"dy\":" + c.lookDy.ToString(System.Globalization.CultureInfo.InvariantCulture) + "}");
            for (int i = 0; i < 90; i++) yield return null;      // 等镜头过渡完、草和毛稳定下来
            // YJ_FREEZE=1：把时间停住（风、摆动、云影全停），这时画面还在跳的才是真的闪
            bool freeze = System.Environment.GetEnvironmentVariable("YJ_FREEZE") == "1";
            if (freeze) Time.timeScale = 0f;

            var prev = new float[GX * GY];
            var diffs = new List<float>[GX * GY];
            for (int k = 0; k < diffs.Length; k++) diffs[k] = new List<float>();
            for (int f = 0; f < Frames; f++)
            {
                yield return null;
                cam.targetTexture = rt;
                cam.Render();
                cam.targetTexture = null;
                RenderTexture.active = rt;
                tex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
                RenderTexture.active = null;
                var px = tex.GetPixels32();
                var cur = new float[GX * GY];
                int cw = W / GX, ch = H / GY;
                for (int gy = 0; gy < GY; gy++)
                    for (int gx = 0; gx < GX; gx++)
                    {
                        long sum = 0;
                        for (int y = gy * ch; y < (gy + 1) * ch; y++)
                            for (int x = gx * cw; x < (gx + 1) * cw; x++)
                            {
                                var p = px[y * W + x];
                                sum += p.r * 2 + p.g * 5 + p.b;
                            }
                        cur[gy * GX + gx] = sum / (8f * cw * ch);
                    }
                if (f > 0)
                    for (int k = 0; k < cur.Length; k++) diffs[k].Add(Mathf.Abs(cur[k] - prev[k]));
                prev = cur;
                if (f == Frames / 2)
                {
                    tex.Apply();
                    File.WriteAllBytes($"../shots/vf_{c.name}.png", tex.EncodeToPNG());
                }
            }
            Time.timeScale = 1f;
            // 每一格：相邻帧的变化，取中位数当「平常」，比它的 3 倍加 1.2 个亮度级还大的算一次「变化大」。
            // 其中前后两帧都平静、只有这一帧跳的才是闪烁（spikes）；风一阵阵吹过来时变化是连着好几帧的，不算
            int jumps = 0, spikes = 0;
            float maxDiff = 0, medAll = 0;
            foreach (var d in diffs)
            {
                var s = new List<float>(d);
                s.Sort();
                float med = s[s.Count / 2];
                medAll += med;
                for (int t = 0; t < d.Count; t++)
                {
                    float v = d[t];
                    maxDiff = Mathf.Max(maxDiff, v);
                    if (v <= med * 3f + 1.2f) continue;
                    jumps++;
                    float before = t > 0 ? d[t - 1] : 0, after = t + 1 < d.Count ? d[t + 1] : 0;
                    // 一次闪烁是「跳过去、下一帧跳回来」，占相邻的两个差值；所以看的是隔一帧的两边
                    float before2 = t > 1 ? d[t - 2] : 0, after2 = t + 2 < d.Count ? d[t + 2] : 0;
                    if (v > 2.5f * Mathf.Max(Mathf.Min(before, after), 0.4f) && v > 2.5f * Mathf.Max(before2, after2, 0.4f)) spikes++;
                }
            }
            medAll /= diffs.Length;
            worst = Mathf.Max(worst, spikes);
            report.Append($"{c.name}: 闪 {spikes} 次，变化大 {jumps} 次（{GX * GY} 格 × {Frames - 1} 帧），平常每帧变化 {medAll:F2}，最大 {maxDiff:F2}；");
        }
        Time.captureFramerate = 0;
        Debug.Log($"[yuanjing] 视角闪烁测试（{weather}）{report}");
        Assert.LessOrEqual(worst, 3, report.ToString());
    }
}
