using System.Collections;
using System.IO;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

/// 坐下、跪下以后从正前方低处拍一张，看裙子有没有搭在腿上（unity/shots/skirt_*.png）
public class SkirtTest
{
    [UnityTest, Timeout(600000)]
    public IEnumerator Skirt()
    {
        SceneManager.LoadScene("Islet");
        for (int i = 0; i < 10; i++) yield return null;
        var bridge = GameObject.Find("Bridge");
        bridge.SendMessage("OnMessage", "{\"cmd\":\"enter\",\"scene\":\"Islet\",\"time\":\"day\",\"weather\":\"clear\",\"seed\":9,\"name\":\"测试\"}");
        yield return new WaitForSeconds(2f);
        var player = GameObject.Find("Player");
        var anim = player.GetComponentInChildren<Animator>();
        var camGo = new GameObject("FrontCam");
        var cam = camGo.AddComponent<Camera>();
        cam.fieldOfView = 28; cam.nearClipPlane = 0.05f;
        var rt = new RenderTexture(500, 500, 24) { antiAliasing = 4 };
        var tex = new Texture2D(500, 500, TextureFormat.RGB24, false);
        void Shot(string n)
        {
            var hips = anim.GetBoneTransform(HumanBodyBones.Hips).position;
            Vector3 f = anim.transform.forward; f.y = 0; f.Normalize();
            // 正前方低处、侧面、身后斜上方各一张（裙子防穿帮：前面的手、腿不能被补画的裙子盖住，后面不能露洞）
            Vector3 side = Vector3.Cross(Vector3.up, f);
            // 别人（前后排坐着的香客）先藏起来，免得挡在测试镜头前面
            var others = new System.Collections.Generic.List<Renderer>();
            foreach (var r in Object.FindObjectsByType<SkinnedMeshRenderer>(FindObjectsSortMode.None))
                if (r.enabled && !r.transform.IsChildOf(player.transform)) { r.enabled = false; others.Add(r); }
            foreach (var (tag, eye) in new[] { ("", hips + f * 1.6f + Vector3.up * 0.05f), ("_side", hips + side * 1.5f + f * 0.4f + Vector3.up * 0.3f), ("_back", hips - f * 1.4f + Vector3.up * 0.7f) })
            {
                cam.transform.position = eye;
                cam.transform.LookAt(hips + Vector3.up * 0.05f);
                cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
                RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, 500, 500), 0, 0); RenderTexture.active = null;
                File.WriteAllBytes($"../shots/skirt_{n}{tag}.png", tex.EncodeToPNG());
            }
            foreach (var r in others) r.enabled = true;
            // 裙子骨头在哪：最低的裙摆点离髋多远（看裙子是不是翻上去了）
            float lowest = 9; foreach (var t in player.GetComponentsInChildren<Transform>()) if (t.name.Contains("Skirt")) lowest = Mathf.Min(lowest, t.position.y - hips.y);
            Debug.Log($"[yuanjing] 裙子 {n}：最低的裙摆点比髋高 {lowest:F3} 米");
        }
        Shot("stand");
        // 站到石台上第一排东边那个蒲团前面的走道上，再「坐下」（坐最近的空蒲团）
        var cc = player.GetComponent<CharacterController>();
        cc.enabled = false;
        player.transform.position = new Vector3(1.3f, 0.09f, 3.25f);
        cc.enabled = true;
        yield return new WaitForSeconds(1f);
        bridge.SendMessage("OnMessage", "{\"cmd\":\"sit\"}");
        yield return new WaitForSeconds(16f);
        Shot("sit");
        bridge.SendMessage("OnMessage", "{\"cmd\":\"move\",\"x\":0,\"y\":1}");
        yield return new WaitForSeconds(0.3f);
        bridge.SendMessage("OnMessage", "{\"cmd\":\"move\",\"x\":0,\"y\":0}");
        yield return new WaitForSeconds(6f);
        bridge.SendMessage("OnMessage", "{\"cmd\":\"act\",\"action\":\"kneel\"}");
        yield return new WaitForSeconds(3.2f);
        Shot("kneel");
        // 叩首最低的那一下
        var folkType = System.Type.GetType("Yuanjing.Folk, Assembly-CSharp");
        var folk = player.GetComponentInChildren(folkType);
        var bp = folkType.GetField("bowPhase", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance);
        for (float t = 0; t < 12f && (float)bp.GetValue(folk) < 0.9f; t += Time.deltaTime) yield return null;
        Shot("kowtow");
        Assert.Pass();
    }
}
