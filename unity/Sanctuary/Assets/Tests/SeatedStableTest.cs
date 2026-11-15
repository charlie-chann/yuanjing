using System.Collections;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 坐着、跪着的人，位置必须一直是正常的数。
/// 出过的事故：盘坐的香客每帧算「身体下沉多少」时越算越大，位置涨到上亿亿、最后成了无效数，
/// 引擎拿这些坏掉的位置去分配灯光和阴影，整个场景的地面、建筑全都忽明忽暗地闪。
public class SeatedStableTest
{
    [UnityTest]
    public IEnumerator SeatedPeopleStayPut()
    {
        SceneManager.LoadScene(System.Environment.GetEnvironmentVariable("YJ_SCENE") ?? "Temple");
        for (int i = 0; i < 10; i++) yield return null;
        var bridge = GameObject.Find("Bridge");
        string scene = SceneManager.GetActiveScene().name;
        bridge.SendMessage("OnMessage", "{\"cmd\":\"enter\",\"scene\":\"" + scene + "\",\"time\":\"night\",\"weather\":\"clear\",\"seed\":10,\"name\":\"测试\"}");
        yield return new WaitForSeconds(6f);
        bridge.SendMessage("OnMessage", "{\"cmd\":\"sit\"}");
        yield return new WaitForSeconds(14f);
        bridge.SendMessage("OnMessage", "{\"cmd\":\"act\",\"action\":\"kneel\"}");
        float worst = 0;
        string who = "";
        int people = 0;
        for (int t = 0; t < 40; t++)
        {
            yield return new WaitForSeconds(1f);
            people = 0;
            foreach (var a in Object.FindObjectsByType<Animator>(FindObjectsSortMode.None))
            {
                people++;
                var model = a.transform;
                float y = model.localPosition.y;
                var hips = a.GetBoneTransform(HumanBodyBones.Hips).position;
                float off = Mathf.Abs(hips.y - model.parent.position.y);
                bool bad = float.IsNaN(y) || float.IsNaN(hips.y) || Mathf.Abs(y) > 1.5f || off > 2.5f;
                float m = bad ? float.MaxValue : Mathf.Max(Mathf.Abs(y), off);
                if (m > worst) { worst = m; who = $"{model.parent.name} 第{t}秒 模型偏移={y} 髋离脚下={off}"; }
            }
        }
        Debug.Log($"[yuanjing] 坐稳测试 {scene}：{people} 个人，最大偏移 {worst}（{who}）");
        Assert.Greater(people, 5);
        Assert.Less(worst, 2.5f, who);
    }
}
