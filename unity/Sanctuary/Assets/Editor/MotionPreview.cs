using System.Globalization;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Animations;
using UnityEngine.Playables;

/// 检查动作用：把 Assets/Motion 里的一段动作套到一个动漫人物身上，按给的几个时刻各拍一张正面、一张侧面。
///   -executeMethod MotionPreview.Run -clip 动作名 -who shino -times 0,0.5,1 [-yaw 0]
/// 图存在 unity/shots/m_<动作>_<序号>_<f|s>.png
public static class MotionPreview
{
    public static void Run()
    {
        string clipName = SanctuaryBuild.Arg("-clip"), who = SanctuaryBuild.Arg("-who") ?? "shino";
        var times = (SanctuaryBuild.Arg("-times") ?? "0").Split(',').Select(t => float.Parse(t, CultureInfo.InvariantCulture)).ToArray();
        foreach (string f in Directory.GetFiles("Assets/Motion", "*.fbx"))
        {
            var av = AssetDatabase.LoadAllAssetsAtPath(f).OfType<Avatar>().FirstOrDefault();
            Debug.Log($"[yuanjing] 动作 {Path.GetFileNameWithoutExtension(f)}：人形={(av != null && av.isHuman)}");
        }
        string path = $"Assets/Motion/{clipName}.fbx";
        var clip = AssetDatabase.LoadAllAssetsAtPath(path).OfType<AnimationClip>().FirstOrDefault(c => !c.name.StartsWith("__preview"));
        if (clip == null) { Debug.LogError($"[yuanjing] 没有动作 {clipName}"); return; }
        Debug.Log($"[yuanjing] {clipName}：{clip.length:F2} 秒，循环 {clip.isLooping}，平均速度 {clip.averageSpeed.magnitude:F3}");

        EditorSceneManager.OpenScene("Assets/Scenes/Islet.unity");
        var player = GameObject.Find("Player");
        if (player != null) player.SetActive(false);
        foreach (var t in Object.FindObjectsByType<Transform>(FindObjectsSortMode.None))
            if (t.name.StartsWith("Pet_") || t.name.StartsWith("Pilgrim_")) t.gameObject.SetActive(false);
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"Assets/Characters/Built/Folk_anime_{who}.prefab");
        var go = (GameObject)Object.Instantiate(prefab);
        var folk = go.GetComponent<Yuanjing.Folk>();
        var anim = go.GetComponentInChildren<Animator>();
        Object.DestroyImmediate(folk);
        foreach (var sb in go.GetComponentsInChildren<Yuanjing.SpringBones>()) Object.DestroyImmediate(sb);
        // 一块空地：码头前的沙滩上，背景干净
        Vector3 at = new Vector3(0f, 0.07f, -14.6f);
        float yaw = float.Parse(SanctuaryBuild.Arg("-yaw") ?? "0", CultureInfo.InvariantCulture);
        go.transform.SetPositionAndRotation(at, Quaternion.Euler(0, yaw, 0));
        var graph = PlayableGraph.Create("preview");
        var output = AnimationPlayableOutput.Create(graph, "a", anim);
        var cp = AnimationClipPlayable.Create(graph, clip);
        cp.SetApplyFootIK(true);
        output.SetSourcePlayable(cp);
        // 批处理模式下帧数不往前走，蒙皮只算一次：让它每次渲染都重算，不然每张图都是同一个姿势
        foreach (var smr in go.GetComponentsInChildren<SkinnedMeshRenderer>()) { smr.forceMatrixRecalculationPerRender = true; smr.updateWhenOffscreen = true; }
        if (SanctuaryBuild.Arg("-stride") != null)
        {
            // 量步幅：逐帧取两只脚相对人原点的前后位置，着地那只脚往后退的速度就是这段走路「真正」的速度
            var lf = anim.GetBoneTransform(HumanBodyBones.LeftFoot); var rf = anim.GetBoneTransform(HumanBodyBones.RightFoot);
            float prevL = 0, prevR = 0, sum = 0; int n = 0;
            for (int f = 0; f <= 120; f++)
            {
                cp.SetTime(clip.length * f / 120f); graph.Evaluate(0);
                float zl = go.transform.InverseTransformPoint(lf.position).z, zr = go.transform.InverseTransformPoint(rf.position).z;
                float yl = lf.position.y, yr = rf.position.y;
                if (f > 0)
                {
                    float dt = clip.length / 120f;
                    float v = yl < yr ? (prevL - zl) / dt : (prevR - zr) / dt;
                    sum += v; n++;
                }
                prevL = zl; prevR = zr;
            }
            Debug.Log($"[yuanjing] 步幅 {clipName}：着地脚往后退平均 {sum / n:F3} 米/秒（人缩放 {go.transform.lossyScale.y:F3}，humanScale {anim.humanScale:F3}），averageSpeed×humanScale×缩放 = {clip.averageSpeed.magnitude * anim.humanScale * go.transform.lossyScale.y:F3}");
        }
        var cam = Camera.main;
        var tw = Object.FindFirstObjectByType<Yuanjing.TimeWeather>();
        if (tw != null) tw.ApplyImmediate(Yuanjing.DayTime.Day, Yuanjing.Weather.Clear);
        int w = 420, h = 560;
        var rt = new RenderTexture(w, h, 24) { antiAliasing = 4 };
        var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
        Directory.CreateDirectory("../shots");
        for (int i = 0; i < times.Length; i++)
        {
            cp.SetTime(times[i]);
            graph.Evaluate(0);
            Debug.Log($"[yuanjing] t={times[i]} 髋相对原点 {go.transform.InverseTransformPoint(anim.GetBoneTransform(HumanBodyBones.Hips).position).ToString("F3")} 左脚相对原点 {go.transform.InverseTransformPoint(anim.GetBoneTransform(HumanBodyBones.LeftFoot).position).ToString("F3")}");
            foreach (var (tag, dir) in new[] { ("f", Quaternion.Euler(0, yaw, 0) * Vector3.forward), ("s", Quaternion.Euler(0, yaw + 90, 0) * Vector3.forward) })
            {
                Vector3 look = at + Vector3.up * 0.62f;
                cam.transform.position = look + dir * 3.2f + Vector3.up * 0.15f;
                cam.transform.LookAt(look);
                cam.fieldOfView = 26f;
                cam.nearClipPlane = 0.1f;
                cam.targetTexture = rt;
                cam.Render();
                cam.Render();
                RenderTexture.active = rt;
                tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
                tex.Apply();
                File.WriteAllBytes($"../shots/m_{clipName}_{i:00}_{tag}.png", tex.EncodeToPNG());
                cam.targetTexture = null;
                RenderTexture.active = null;
            }
        }
        graph.Destroy();
    }
}
