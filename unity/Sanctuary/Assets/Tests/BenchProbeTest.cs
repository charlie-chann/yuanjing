using System.Collections;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 石凳：坐下、起身逐帧记下原点、身子下沉、髋的位置（排查「起身时髋一帧蹿十几厘米」），并量脚有没有插进地里。
/// 跑：unity/playtest.sh BenchProbeTest，看 grep "石凳逐帧" unity/test.log
public class BenchProbeTest
{
    [UnityTest]
    public IEnumerator SitAndStand()
    {
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        var bridge = GameObject.Find("Bridge");
        const BindingFlags BF = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;
        object Get(object o, string n) { var t = o.GetType(); var f = t.GetField(n, BF); return f != null ? f.GetValue(o) : t.GetProperty(n, BF).GetValue(o); }
        void Cmd(string json) => bridge.SendMessage("OnMessage", json);
        // seed 0：不放本机的香客，石凳都空着
        Cmd("{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":0,\"name\":\"测试\"}");
        yield return new WaitForSeconds(2f);
        var gd = Object.FindObjectsByType<MonoBehaviour>(FindObjectsSortMode.None).First(m => m.GetType().Name == "GameDirector");
        var folk = (MonoBehaviour)Get(gd, "player");
        var root = GameObject.Find("Player");
        var cc = root.GetComponent<CharacterController>();
        var anim = folk.GetComponentInChildren<Animator>();
        Transform hips = anim.GetBoneTransform(HumanBodyBones.Hips), lf = anim.GetBoneTransform(HumanBodyBones.LeftToes), rf = anim.GetBoneTransform(HumanBodyBones.RightToes);
        var model = (Transform)Get(folk, "model");
        Vector3 stand = (Vector3)gd.GetType().GetMethod("SeatStand", BF).Invoke(gd, new object[] { 4 });
        cc.enabled = false;
        root.transform.position = stand + new Vector3(0.3f, 0.02f, 0.9f);
        folk.transform.localPosition = Vector3.zero;
        cc.enabled = true;
        Physics.SyncTransforms();
        yield return new WaitForSeconds(1f);
        Time.captureFramerate = 30;
        float worst = 0, lowest = 99;
        string worstAt = "";
        Vector3 last = hips.position;
        IEnumerator Watch(string what, float seconds)
        {
            for (float t = 0; t < seconds; t += Time.deltaTime)
            {
                yield return null;   // 批处理模式下 WaitForEndOfFrame 不会回来
                Vector3 h = hips.position;
                float j = (h - last).magnitude;
                float toe = Mathf.Min(lf.position.y, rf.position.y);
                if (j > worst) { worst = j; worstAt = $"{what} {t:F2}"; }
                lowest = Mathf.Min(lowest, toe);
                Debug.Log($"[yuanjing] 石凳逐帧 {what} {t:F2}：原点 {root.transform.position.ToString("F3")} 下沉 {model.localPosition.y:F3} 髋 {h.ToString("F3")} 挪 {j:F3} 脚尖 {toe:F3} 姿势 {Get(folk, "pose")} 胶囊 {cc.enabled} 滑 {Get(folk, "BenchGliding")}");
                last = h;
            }
        }
        Cmd("{\"cmd\":\"sit\",\"seat\":4}");
        yield return Watch("坐下", 6f);
        // 坐着合掌、鞠躬：脚不能插进石台里
        float before = lowest;
        lowest = 99;
        Cmd("{\"cmd\":\"act\",\"action\":\"bow\"}");
        yield return Watch("坐着鞠躬", 7f);
        Debug.Log($"[yuanjing] 石凳逐帧 坐着鞠躬时脚尖最低 {lowest:F3}（石台面 0.07；坐着不动时 {Mathf.Min(lf.position.y, rf.position.y):F3}）");
        Assert.Greater(lowest, 0.03f, "坐着鞠躬时脚尖插进石台里 4 厘米以上");
        lowest = before;
        Cmd("{\"cmd\":\"stand\"}");
        yield return Watch("起身", 4f);
        Time.captureFramerate = 0;
        Debug.Log($"[yuanjing] 石凳逐帧 髋一帧最多挪 {worst:F3}（{worstAt}），脚尖最低 {lowest:F3}（石台面 0.07）");
        Assert.Less(worst, 0.08f, $"髋一帧里蹿了 {worst:F3} 米（{worstAt}）");
        Assert.Greater(lowest, 0.03f, "脚尖插进石台里 4 厘米以上");
    }
}
