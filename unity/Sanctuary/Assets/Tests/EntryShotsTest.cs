using System.Collections;
using System.IO;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 进殿那几秒：俯视拍几张，并报告玩家附近 1 米内有几个人、谁离玩家最近（查「刚进来身子叠在一起」）
public class EntryShotsTest
{
    [UnityTest]
    public IEnumerator Entry()
    {
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        var bridge = GameObject.Find("Bridge");
        bridge.SendMessage("OnMessage", "{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"测试\"}");
        var cam = Camera.main;
        var rt = new RenderTexture(360, 640, 24) { antiAliasing = 4 };
        var tex = new Texture2D(360, 640, TextureFormat.RGB24, false);
        Directory.CreateDirectory("../shots");
        var player = GameObject.Find("Player");
        float[] at = { 0.3f, 1f, 2f, 4f, 8f };
        float t0 = Time.time;
        for (int k = 0; k < at.Length; k++)
        {
            while (Time.time - t0 < at[k]) yield return null;
            cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
            RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, 360, 640), 0, 0); RenderTexture.active = null;
            File.WriteAllBytes($"../shots/entry_{k}.png", tex.EncodeToPNG());
            var pp = player.transform.position;
            string near = "";
            int n = 0;
            foreach (var f in Object.FindObjectsByType<Animator>(FindObjectsSortMode.None))
            {
                if (f.transform.IsChildOf(player.transform) || !f.isHuman) continue;
                float d = Vector3.Distance(f.transform.position, pp);
                if (d < 1f) { n++; near += $"{f.transform.parent.name}({d:F2}) "; }
            }
            var anims = player.GetComponentsInChildren<Animator>();
            int renderers = 0;
            foreach (var r in player.GetComponentsInChildren<SkinnedMeshRenderer>()) if (r.enabled) renderers++;
            Debug.Log($"[yuanjing] 进殿 {at[k]} 秒：玩家在 {pp.ToString("F2")}，动画器 {anims.Length} 个（{string.Join(",", System.Array.ConvertAll(anims, a => a.transform.parent.name + "/" + (a.avatar != null ? a.avatar.name : "无")))}），蒙皮 {renderers} 个，1 米内 {n} 人 {near}");
        }
        Assert.Pass();
    }
}
