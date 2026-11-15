using System.Collections;
using System.Text;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 站着不动 20 秒，每 0.2 秒量一次脚下地面的亮度，看会不会突然整片变暗。
/// 环境变量 YJ_OFF 可以关掉某样东西做对比：walkers（散步的人）、shadows（阴影）、ssao、pilgrims（所有人）
public class FlickerTest
{
    [UnityTest]
    public IEnumerator GroundStaysLit()
    {
        SceneManager.LoadScene("Temple");
        for (int i = 0; i < 10; i++) yield return null;
        var bridge = GameObject.Find("Bridge");
        bridge.SendMessage("OnMessage", "{\"cmd\":\"enter\",\"scene\":\"Temple\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":8,\"name\":\"测试\"}");
        yield return new WaitForSeconds(9f);
        string off = System.Environment.GetEnvironmentVariable("YJ_OFF") ?? "";
        if (off.Contains("walkers"))
            foreach (var go in Object.FindObjectsByType<Transform>(FindObjectsSortMode.None))
                if (go.name.StartsWith("Pilgrim_walk")) go.gameObject.SetActive(false);
        if (off.Contains("pilgrims"))
            foreach (var go in Object.FindObjectsByType<Transform>(FindObjectsSortMode.None))
                if (go.name.StartsWith("Pilgrim_")) go.gameObject.SetActive(false);
        if (off.Contains("shadows")) GameObject.Find("Sun").GetComponent<Light>().shadows = LightShadows.None;
        var cam = Camera.main;
        var rt = new RenderTexture(160, 348, 24);
        var tex = new Texture2D(160, 348, TextureFormat.RGB24, false);
        var sb = new StringBuilder();
        float min = 999, max = 0;
        for (int i = 0; i < 100; i++)
        {
            yield return new WaitForSeconds(0.2f);
            cam.targetTexture = rt;
            cam.Render();
            cam.targetTexture = null;
            RenderTexture.active = rt;
            tex.ReadPixels(new Rect(0, 0, 160, 348), 0, 0);
            RenderTexture.active = null;
            float sum = 0;
            int n = 0;
            for (int y = 60; y < 120; y++)
                for (int x = 40; x < 120; x++) { var c = tex.GetPixel(x, y); sum += c.grayscale; n++; }
            float v = sum / n * 255;
            min = Mathf.Min(min, v); max = Mathf.Max(max, v);
            sb.Append(Mathf.RoundToInt(v)).Append(' ');
        }
        Debug.Log($"[yuanjing] 地面亮度（关掉：{off}）最暗 {min:F0} 最亮 {max:F0}：{sb}");
    }
}
