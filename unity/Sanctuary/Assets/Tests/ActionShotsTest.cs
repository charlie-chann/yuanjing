using System.Collections;
using System.IO;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 在游戏里实际跑一遍「坐下 → 合掌 → 跪拜 → 起身」，每个阶段拍一张（平视），存到 unity/shots/act_*.png。
public class ActionShotsTest
{
    [UnityTest]
    public IEnumerator Actions()
    {
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        var bridge = GameObject.Find("Bridge");
        void Cmd(string j) => bridge.SendMessage("OnMessage", j);
        Cmd("{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"测试\"}");
        yield return new WaitForSeconds(26f);
        var cam = Camera.main;
        var rt = new RenderTexture(360, 640, 24) { antiAliasing = 4 };
        var tex = new Texture2D(360, 640, TextureFormat.RGB24, false);
        Directory.CreateDirectory("../shots");
        void Shot(string n)
        {
            cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
            RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, 360, 640), 0, 0); RenderTexture.active = null;
            File.WriteAllBytes($"../shots/act_{n}.png", tex.EncodeToPNG());
        }
        Cmd("{\"cmd\":\"view\",\"kind\":\"level\"}");
        yield return new WaitForSeconds(1f);
        Cmd("{\"cmd\":\"act\",\"action\":\"pray\"}");
        yield return new WaitForSeconds(0.5f); Shot("1_pray_in");
        yield return new WaitForSeconds(2.0f); Shot("2_pray_low");
        yield return new WaitForSeconds(6f);
        Cmd("{\"cmd\":\"act\",\"action\":\"bow\"}");
        yield return new WaitForSeconds(1.2f); Shot("3_bow");
        yield return new WaitForSeconds(4f);
        Cmd("{\"cmd\":\"act\",\"action\":\"kneel\"}");
        yield return new WaitForSeconds(1.0f); Shot("4_kneel_down");
        yield return new WaitForSeconds(2.0f); Shot("5_kowtow");
        yield return new WaitForSeconds(9f); Shot("6_after");
        Cmd("{\"cmd\":\"sit\"}");
        yield return new WaitForSeconds(14f); Shot("7_seated");
        Cmd("{\"cmd\":\"view\",\"kind\":\"top\"}");
        yield return new WaitForSeconds(1.5f); Shot("8_hall_top");
        Assert.Pass();
    }
}
