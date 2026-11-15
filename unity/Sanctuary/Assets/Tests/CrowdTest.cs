using System.Collections;
using System.Collections.Generic;
using System.IO;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 没联网时的人流：快进跑一阵（时间 6 倍速），统计人数变化、进来几人、走了几人、两人最近的距离、站在哪些地方。
public class CrowdTest
{
    [UnityTest]
    public IEnumerator CrowdComesAndGoes()
    {
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        var bridge = GameObject.Find("Bridge");
        bridge.SendMessage("OnMessage", "{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"测试\"}");
        yield return new WaitForSeconds(3f);
        Time.timeScale = 6f;
        var seen = new HashSet<string>();
        var first = new HashSet<string>();
        int minCount = 999, maxCount = 0, overlaps = 0;
        float closest = 99;
        string closestWho = "";
        var cam = Camera.main;
        var rt = new RenderTexture(360, 640, 24) { antiAliasing = 4 };
        var tex = new Texture2D(360, 640, TextureFormat.RGB24, false);
        for (int k = 0; k < 60; k++)
        {
            yield return new WaitForSeconds(6f);     // 游戏里 6 秒 = 真实 1 秒；一共游戏里 6 分钟
            var now = new List<Transform>();
            foreach (var t in Object.FindObjectsByType<Transform>(FindObjectsSortMode.None))
                if (t.name.StartsWith("Pilgrim_")) now.Add(t);
            if (k == 0) foreach (var t in now) first.Add(t.name);
            foreach (var t in now) seen.Add(t.name);
            minCount = Mathf.Min(minCount, now.Count);
            maxCount = Mathf.Max(maxCount, now.Count);
            for (int a = 0; a < now.Count; a++)
                for (int b = a + 1; b < now.Count; b++)
                {
                    Vector3 d = now[a].position - now[b].position; d.y = 0;
                    if (d.magnitude < closest) { closest = d.magnitude; closestWho = $"{now[a].name}/{now[b].name} 在 {now[a].position.ToString("F1")}"; }
                    if (d.magnitude < 0.3f) overlaps++;
                }
            if (k % 20 == 19)
            {
                cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
                RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, 360, 640), 0, 0); RenderTexture.active = null;
                Directory.CreateDirectory("../shots");
                File.WriteAllBytes($"../shots/crowd_{k / 20}.png", tex.EncodeToPNG());
            }
        }
        Time.timeScale = 1f;
        int arrived = 0;
        foreach (var n in seen) if (!first.Contains(n)) arrived++;
        int stillHere = 0;
        foreach (var t in Object.FindObjectsByType<Transform>(FindObjectsSortMode.None)) if (t.name.StartsWith("Pilgrim_") && first.Contains(t.name)) stillHere++;
        Debug.Log($"[yuanjing] 人流测试：人数 {minCount}–{maxCount}，开头 {first.Count} 人，后来进来 {arrived} 人，开头那批走了 {first.Count - stillHere} 人，两人最近 {closest:F2} 米（{closestWho}），贴在一起的次数 {overlaps}");
        Assert.Greater(arrived, 0);
    }
}
