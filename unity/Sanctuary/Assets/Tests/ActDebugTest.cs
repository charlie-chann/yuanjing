using System.Collections;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 查「站着做动作没反应」：做合掌、鞠躬时逐秒打出玩家的姿势、正在播的动作段、动作段权重、右手高度
public class ActDebugTest
{
    [UnityTest, Timeout(600000)]
    public IEnumerator Debug_()
    {
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        var bridge = GameObject.Find("Bridge");
        bridge.SendMessage("OnMessage", "{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"测试\"}");
        yield return new WaitForSeconds(2f);
        var player = GameObject.Find("Player");
        var folk = player.GetComponentInChildren(System.Type.GetType("Yuanjing.Folk, Assembly-CSharp"));
        var anim = player.GetComponentInChildren<Animator>();
        var T = folk.GetType();
        object F(string n) => T.GetField(n, BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Public)?.GetValue(folk) ?? T.GetProperty(n)?.GetValue(folk);
        var clips = (AnimationClip[])F("actionClips");
        Debug.Log($"[yuanjing] 动作段 {(clips == null ? -1 : clips.Length)} 个；walk={((AnimationClip)F("walkClip"))?.name} 平均速度 {((AnimationClip)F("walkClip"))?.averageSpeed.magnitude:F3} humanScale {anim.humanScale:F3} 缩放 {folk.transform.lossyScale.y:F3}");
        bridge.SendMessage("OnMessage", "{\"cmd\":\"goto\",\"spot\":\"hall\"}");
        for (int k = 0; k < 20; k++) { yield return new WaitForSeconds(1f); Debug.Log($"[yuanjing] 走去大殿 {k}：位置 {player.transform.position.ToString("F2")} pose={F("pose")} acting={T.Assembly.GetType("Yuanjing.GameDirector").GetField("acting", BindingFlags.NonPublic | BindingFlags.Instance).GetValue(Object.FindFirstObjectByType(T.Assembly.GetType("Yuanjing.GameDirector")))}"); }
        foreach (var act in new[] { "pray", "bow", "kneel" })
        {
            bridge.SendMessage("OnMessage", "{\"cmd\":\"act\",\"action\":\"" + act + "\"}");
            for (int k = 0; k < 6; k++)
            {
                yield return new WaitForSeconds(1f);
                Debug.Log($"[yuanjing] {act} 第{k}秒：pose={F("pose")} shown={F("shown")} actNow={F("actNow")} actW={F("actW")} 右手高 {anim.GetBoneTransform(HumanBodyBones.RightHand).position.y - player.transform.position.y:F2} 头高 {anim.GetBoneTransform(HumanBodyBones.Head).position.y - player.transform.position.y:F2}");
            }
            yield return new WaitForSeconds(6f);
        }
        Assert.Pass();
    }
}
