using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 走路脚滑多少：直走 6 秒，记下每只脚每帧的位置；每只脚离它自己最低点 1 厘米以内的帧算「踩着地」，量这些帧里脚在世界里的水平速度
public class WalkSlideTest
{
    [UnityTest, Timeout(600000)]
    public IEnumerator Slide()
    {
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        var bridge = GameObject.Find("Bridge");
        bridge.SendMessage("OnMessage", "{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"测试\"}");
        yield return new WaitForSeconds(2f);
        var player = GameObject.Find("Player");
        var anim = player.GetComponentInChildren<Animator>();
        var folk = player.GetComponentInChildren(System.Type.GetType("Yuanjing.Folk, Assembly-CSharp"));
        var slots = (UnityEngine.Animations.AnimationClipPlayable[])folk.GetType().GetField("slots", BindingFlags.NonPublic | BindingFlags.Instance).GetValue(folk);
        bridge.SendMessage("OnMessage", "{\"cmd\":\"move\",\"x\":-1,\"y\":0}");
        yield return new WaitForSeconds(1.5f);
        var lf = anim.GetBoneTransform(HumanBodyBones.LeftFoot); var rf = anim.GetBoneTransform(HumanBodyBones.RightFoot);
        var L = new List<(Vector3 p, float t)>(); var R = new List<(Vector3 p, float t)>();
        Vector3 start = player.transform.position; float t0 = Time.time;
        // 侧面拍几张：一台跟着人平移的相机，从人的左侧看腿
        var camGo = new GameObject("SideCam");
        var cam = camGo.AddComponent<Camera>();
        cam.fieldOfView = 30;
        var rt = new RenderTexture(400, 400, 24);
        var tex = new Texture2D(400, 400, TextureFormat.RGB24, false);
        int shot = 0; float nextShot = 0;
        System.IO.Directory.CreateDirectory("../shots/slide");
        for (float t = 0; t < 4f; t += Time.deltaTime)
        {
            yield return null;
            L.Add((lf.position, Time.time)); R.Add((rf.position, Time.time));
            if (t >= nextShot && shot < 12)
            {
                nextShot += 0.1f;
                Vector3 pp = player.transform.position;
                Vector3 fwd = anim.transform.forward;
                Vector3 side = Vector3.Cross(Vector3.up, fwd);
                cam.transform.position = pp + side * -3f + Vector3.up * 0.4f;
                cam.transform.LookAt(pp + Vector3.up * 0.3f);
                cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
                RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, 400, 400), 0, 0); RenderTexture.active = null;
                System.IO.File.WriteAllBytes($"../shots/slide/s{shot++:00}.png", tex.EncodeToPNG());
            }
        }
        float speed = Vector3.Distance(player.transform.position, start) / (Time.time - t0);
        bridge.SendMessage("OnMessage", "{\"cmd\":\"move\",\"x\":0,\"y\":0}");
        string Report(List<(Vector3 p, float t)> f)
        {
            float min = float.MaxValue;
            foreach (var x in f) min = Mathf.Min(min, x.p.y);
            float sum = 0; int n = 0;
            for (int i = 1; i < f.Count; i++)
            {
                if (f[i].p.y > min + 0.01f || f[i - 1].p.y > min + 0.01f) continue;
                Vector3 d = f[i].p - f[i - 1].p; d.y = 0;
                sum += d.magnitude / (f[i].t - f[i - 1].t); n++;
            }
            return $"踩地 {n} 帧，平均滑 {(n > 0 ? sum / n : 0):F3} 米/秒";
        }
        Debug.Log($"[yuanjing] 脚滑：人走 {speed:F2} 米/秒，走路动画播放速度 {UnityEngine.Playables.PlayableExtensions.GetSpeed(slots[1]):F2}/{UnityEngine.Playables.PlayableExtensions.GetSpeed(slots[2]):F2}；左脚 {Report(L)}；右脚 {Report(R)}");
        Assert.Pass();
    }
}
