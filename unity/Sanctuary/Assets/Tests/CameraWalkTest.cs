using System.Collections;
using System.Text;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 推着摇杆在院子里走一圈，记录镜头离人的距离和挡住镜头的东西（查走动时画面忽远忽近）
public class CameraWalkTest
{
    [UnityTest]
    public IEnumerator CameraDistanceSteady()
    {
        SceneManager.LoadScene("Temple");
        for (int i = 0; i < 10; i++) yield return null;
        var bridge = GameObject.Find("Bridge");
        bridge.SendMessage("OnMessage", "{\"cmd\":\"enter\",\"scene\":\"Temple\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":8,\"name\":\"测试\"}");
        yield return new WaitForSeconds(8f);
        var cam = Camera.main.GetComponent("ThirdPersonCamera");
        var distProp = cam.GetType().GetProperty("CurrentDistance");
        var hitField = cam.GetType().GetField("LastHit");
        var sb = new StringBuilder();
        var hits = new System.Collections.Generic.Dictionary<string, int>();
        float lastD = -1, maxJump = 0;
        string[] moves = { "0,1", "1,0.3", "0,-1", "-1,0.2", "0,1" };
        foreach (var mv in moves)
        {
            bridge.SendMessage("OnMessage", "{\"cmd\":\"move\",\"x\":" + mv.Split(',')[0] + ",\"y\":" + mv.Split(',')[1] + "}");
            for (int f = 0; f < 120; f++)
            {
                yield return null;
                float d = (float)distProp.GetValue(cam);
                string h = (string)hitField.GetValue(cam);
                if (h != "") { hits.TryGetValue(h, out int c); hits[h] = c + 1; }
                if (lastD > 0) maxJump = Mathf.Max(maxJump, Mathf.Abs(d - lastD));
                lastD = d;
                if (f % 10 == 0) sb.Append(d.ToString("F2")).Append(' ');
            }
        }
        bridge.SendMessage("OnMessage", "{\"cmd\":\"move\",\"x\":0,\"y\":0}");
        var hs = new StringBuilder();
        foreach (var kv in hits) hs.Append(kv.Key).Append('×').Append(kv.Value).Append(' ');
        Debug.Log($"[yuanjing] 镜头距离 逐帧最大跳变 {maxJump:F2}：{sb}");
        Debug.Log($"[yuanjing] 挡住镜头的：{hs}");
    }
}
