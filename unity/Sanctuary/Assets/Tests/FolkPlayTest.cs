using System.Collections;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 运行模式下进山寺，跑几秒，打出自己小人的骨骼位置（查人陷进地里的问题用）。
/// 测试程序集看不到游戏脚本，所以按物体名字找。
public class FolkPlayTest
{
    [UnityTest]
    public IEnumerator PlayerStandsOnGround()
    {
        SceneManager.LoadScene("Temple");
        for (int i = 0; i < 120; i++) yield return null;
        var player = GameObject.Find("Player");
        Assert.IsNotNull(player);
        var a = player.GetComponentInChildren<Animator>();
        string P(HumanBodyBones b) => a.GetBoneTransform(b).position.y.ToString("F3");
        Debug.Log($"[yuanjing] 运行模式 进场前 root={player.transform.position.y:F3} 髋={P(HumanBodyBones.Hips)} 左脚={P(HumanBodyBones.LeftFoot)}");
        // 和真机一样：Flutter 发进场指令，小人自己走进庭院
        GameObject.Find("Bridge").SendMessage("OnMessage", "{\"cmd\":\"enter\",\"scene\":\"Temple\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":6,\"name\":\"测试\"}");
        yield return new WaitForSeconds(3f);
        Debug.Log($"[yuanjing] 运行模式 走路中 root={player.transform.position.y:F3} 髋={P(HumanBodyBones.Hips)} 左脚={P(HumanBodyBones.LeftFoot)} 速度={a.GetFloat("Speed")}");
        yield return new WaitForSeconds(12f);
        Debug.Log($"[yuanjing] 运行模式 root={player.transform.position.y:F3} 髋={P(HumanBodyBones.Hips)} 左膝={P(HumanBodyBones.LeftLowerLeg)} 左脚={P(HumanBodyBones.LeftFoot)} 头={P(HumanBodyBones.Head)} 模型={a.transform.localPosition.y:F3} 速度={a.GetFloat("Speed")}");
        foreach (var smr in player.GetComponentsInChildren<SkinnedMeshRenderer>())
            Debug.Log($"[yuanjing] 运行模式 {smr.name} 包围盒 {smr.bounds.min.y:F3}..{smr.bounds.max.y:F3}");
    }
}
