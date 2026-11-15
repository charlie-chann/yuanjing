using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;
using Yuanjing;

/// 殿里的小人：用 Quaternius 的免费底模（CC0），套上僧袍和鞋，换发型，做成 Q 版。
/// 衣服是从身体网格「吹胀」出来的一层：沿法线往外推一点，按骨骼分区留下躯干、胳膊、腿，
/// 蒙皮权重直接沿用身体的，所以走路、坐下、跪拜时衣服跟着身体动。
public static partial class SanctuaryBuild
{
    const string FolkDir = "Assets/Characters/Built";

    public class FolkLook
    {
        public string name;
        public bool female;
        public string hair;            // Hair_Buzzed、Hair_Long……
        public Color top, pants, hairColor;
        public bool darkSkin;
        public bool hat;               // 卡通版里戴不戴斗笠
    }

    /// 几套样子：素色的僧袍、居士服。自己的那套是第一个
    public static readonly FolkLook[] FolkLooks =
    {
        new FolkLook { name = "me", female = true, hair = "Hair_Buns", top = new Color(0.93f, 0.90f, 0.82f), pants = new Color(0.62f, 0.58f, 0.52f), hairColor = new Color(0.07f, 0.05f, 0.04f) },
        new FolkLook { name = "monk_ochre", female = false, hair = "Hair_Buzzed", top = new Color(0.78f, 0.58f, 0.26f), pants = new Color(0.55f, 0.40f, 0.20f), hairColor = new Color(0.10f, 0.08f, 0.06f) },
        new FolkLook { name = "monk_grey", female = false, hair = "Hair_Buzzed", top = new Color(0.52f, 0.52f, 0.50f), pants = new Color(0.36f, 0.36f, 0.35f), hairColor = new Color(0.10f, 0.08f, 0.06f) },
        new FolkLook { name = "lay_white", female = true, hair = "Hair_Long", top = new Color(0.94f, 0.93f, 0.90f), pants = new Color(0.80f, 0.78f, 0.74f), hairColor = new Color(0.06f, 0.045f, 0.035f) },
        new FolkLook { name = "lay_brown", hat = true, female = false, hair = "Hair_SimpleParted", top = new Color(0.50f, 0.36f, 0.26f), pants = new Color(0.30f, 0.24f, 0.20f), hairColor = new Color(0.08f, 0.06f, 0.05f) },
        new FolkLook { name = "lay_navy", female = true, hair = "Hair_Buns", top = new Color(0.24f, 0.28f, 0.40f), pants = new Color(0.18f, 0.19f, 0.24f), hairColor = new Color(0.05f, 0.04f, 0.035f) },
        new FolkLook { name = "lay_sage", hat = true, female = false, hair = "Hair_SimpleParted", top = new Color(0.56f, 0.62f, 0.50f), pants = new Color(0.36f, 0.38f, 0.32f), hairColor = new Color(0.12f, 0.09f, 0.06f), darkSkin = true },
        new FolkLook { name = "lay_rose", female = true, hair = "Hair_Long", top = new Color(0.78f, 0.56f, 0.54f), pants = new Color(0.50f, 0.40f, 0.40f), hairColor = new Color(0.20f, 0.12f, 0.07f) },
    };

    [MenuItem("Yuanjing/5 生成小人")]
    public static void BuildFolk()
    {
        Directory.CreateDirectory(FolkDir);
        // 导入规则改过的话要重新导入一遍动作库才生效
        AssetDatabase.ImportAsset("Assets/Characters/UAL1_Standard.fbx", ImportAssetOptions.ForceUpdate);
        clipCache.Clear();
        var controller = FolkController();
        // 只生成湖心小寺用的卡通版（写实版是山寺、教堂用的，那两座已经不要了）：同一副骨架和动作，换成卡通材质
        ToonMaterials();
        foreach (var look in FolkLooks) FolkPrefab(look, controller, true);
        // 动漫人物（VRM 转来的）：有的话再各做一个预制体
        int anime = AnimeFolkPrefabs();
        if (anime > 0) Debug.Log($"[yuanjing] 动漫人物 {anime} 个");
        AssetDatabase.SaveAssets();
        Debug.Log("[yuanjing] 小人已生成");
    }

    /// 动作库里的一段动画，复制成独立的 .anim 文件再用。
    /// 直接引用模型文件里的子资源时，状态机存的是按序号的旧编号，打包到手机上会对错片段（人会播成别的动作）。
    static readonly Dictionary<string, AnimationClip> clipCache = new Dictionary<string, AnimationClip>();

    static AnimationClip Clip(string name)
    {
        if (clipCache.TryGetValue(name, out var cached) && cached != null) return cached;
        string path = $"{FolkDir}/{name}.anim";
        var src = AssetDatabase.LoadAllAssetsAtPath("Assets/Characters/UAL1_Standard.fbx").OfType<AnimationClip>().First(c => c.name.EndsWith("|" + name) || c.name == name);
        // 新建一个干净的片段，把曲线一条条抄过去。不能用 Instantiate：复制出来的是编辑器专用的预览片段，打包时会被丢掉
        var copy = new AnimationClip { name = name, frameRate = src.frameRate };
        foreach (var binding in AnimationUtility.GetCurveBindings(src))
            AnimationUtility.SetEditorCurve(copy, binding, AnimationUtility.GetEditorCurve(src, binding));
        // 循环、根节点的设置在这里定死：根的转向、高度、水平位置都烘进姿势里（人的移动由脚本管），高度按双脚对齐
        var st = AnimationUtility.GetAnimationClipSettings(src);
        st.loopTime = name.Contains("Loop");
        st.loopBlendOrientation = true;
        st.loopBlendPositionY = true;
        st.loopBlendPositionXZ = true;
        st.keepOriginalOrientation = false;
        st.keepOriginalPositionY = false;
        st.heightFromFeet = true;
        st.keepOriginalPositionXZ = false;
        AnimationUtility.SetAnimationClipSettings(copy, st);
        AssetDatabase.DeleteAsset(path);
        AssetDatabase.CreateAsset(copy, path);
        return clipCache[name] = AssetDatabase.LoadAssetAtPath<AnimationClip>(path);
    }

    /// 动画状态机：站着和走路按速度混合，坐椅子有坐下、坐着、起身三段
    static AnimatorController FolkController()
    {
        string path = $"{FolkDir}/Folk.controller";
        AssetDatabase.DeleteAsset(path);
        var c = AnimatorController.CreateAnimatorControllerAtPath(path);
        c.AddParameter("Speed", AnimatorControllerParameterType.Float);
        c.AddParameter("Sit", AnimatorControllerParameterType.Bool);
        var sm = c.layers[0].stateMachine;
        var move = c.CreateBlendTreeInController("Move", out var tree, 0);
        tree.blendParameter = "Speed";
        tree.useAutomaticThresholds = false;
        tree.AddChild(Clip("Idle_Loop"), 0f);
        tree.AddChild(Clip("Walk_Formal_Loop"), 0.6f);
        tree.AddChild(Clip("Walk_Loop"), 1.2f);
        var enter = sm.AddState("SitEnter");
        enter.motion = Clip("Sitting_Enter");
        var idle = sm.AddState("SitIdle");
        idle.motion = Clip("Sitting_Idle_Loop");
        var exit = sm.AddState("SitExit");
        exit.motion = Clip("Sitting_Exit");
        sm.defaultState = move;
        var t = move.AddTransition(enter);
        t.AddCondition(AnimatorConditionMode.If, 0, "Sit");
        t.hasExitTime = false;
        t.duration = 0.2f;
        t = enter.AddTransition(idle);
        t.hasExitTime = true;
        t.exitTime = 0.9f;
        t.duration = 0.15f;
        t = idle.AddTransition(exit);
        t.AddCondition(AnimatorConditionMode.IfNot, 0, "Sit");
        t.hasExitTime = false;
        t.duration = 0.15f;
        t = exit.AddTransition(move);
        t.hasExitTime = true;
        t.exitTime = 0.85f;
        t.duration = 0.2f;
        t = enter.AddTransition(exit);
        t.AddCondition(AnimatorConditionMode.IfNot, 0, "Sit");
        t.hasExitTime = false;
        t.duration = 0.2f;
        return c;
    }

    static Texture2D CharTex(string name) => AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Characters/Textures/{name}.png");

    static Material FolkMat(string name, Texture2D baseMap, Texture2D normal, Color tint, float rough, string fabric = null, float tile = 1f)
    {
        var m = Mat(name, fabric, tile, tint, rough: rough, wet: 0f, snow: 0f);
        if (baseMap != null)
        {
            m.SetTexture("_BaseMap", baseMap);
            m.SetTextureScale("_BaseMap", Vector2.one);
        }
        if (normal != null)
        {
            m.SetTexture("_BumpMap", normal);
            m.SetTextureScale("_BaseMap", Vector2.one);
            m.EnableKeyword("_NORMALMAP");
        }
        if (fabric == null) m.SetTexture("_ArmMap", null);
        return m;
    }

    static readonly string[] HeadBones = { "Head", "neck" };
    static readonly string[] HandBones = { "hand", "thumb", "index", "middle", "ring", "pinky" };
    static readonly string[] FootBones = { "foot", "ball" };
    static readonly string[] LegBones = { "thigh", "calf" };

    static int Region(string bone)
    {
        string b = bone.ToLowerInvariant();
        if (HeadBones.Any(x => b.StartsWith(x.ToLowerInvariant()))) return 0;   // 头和脖子：露在外面
        if (HandBones.Any(x => b.StartsWith(x))) return 0;                      // 手：露在外面
        if (FootBones.Any(x => b.StartsWith(x))) return 3;                      // 脚：鞋
        if (LegBones.Any(x => b.StartsWith(x))) return 2;                       // 腿：裤子
        return 1;                                                               // 躯干、胳膊：上衣
    }

    /// 宽松的长袍：在身体外面一圈一圈地包。每个高度取身体这一层的外轮廓（往各个方向最远到哪），
    /// 放宽一点，腰以下把两条腿一起包住、越往下越散开，一直到脚踝；两只袖子沿胳膊包，袖口放宽。
    /// 每个袍子顶点的骨骼权重取离它最近的身体顶点的，裙摆再掺一半骨盆的，走路时不会被两条腿扯开。
    /// 返回的网格有三块：袍子、腰带、鞋。
    static Mesh RobeMesh(SkinnedMeshRenderer body, string name)
    {
        var src = body.sharedMesh;
        // 模型文件里是 Z 朝上、Y 朝前后。先换成 Y 朝上来做，做完再换回去
        Vector3 Up(Vector3 p) => new Vector3(p.x, p.z, p.y);
        var V = src.vertices.Select(Up).ToArray();
        var W = src.boneWeights;
        int n = V.Length;
        var boneNames = body.bones.Select(b => b.name.ToLowerInvariant()).ToArray();
        Vector3 BonePos(string prefix)
        {
            int i = System.Array.FindIndex(boneNames, b => b.StartsWith(prefix));
            return i < 0 ? Vector3.zero : Up(src.bindposes[i].inverse.MultiplyPoint3x4(Vector3.zero));
        }
        int pelvisBone = System.Array.FindIndex(boneNames, b => b.StartsWith("pelvis"));
        // 0 头手 1 躯干 2 腿 3 脚 4 胳膊
        var region = new int[n];
        for (int i = 0; i < n; i++)
        {
            string b = boneNames[W[i].boneIndex0];
            region[i] = b.StartsWith("upperarm") || b.StartsWith("lowerarm") ? 4 : Region(body.bones[W[i].boneIndex0].name);
        }
        float neckY = BonePos("neck_01").y, pelvisY = BonePos("pelvis").y, ankleY = Mathf.Min(BonePos("foot_l").y, BonePos("foot_r").y);
        float shoulderX = Mathf.Abs(BonePos("upperarm_l").x), wristX = Mathf.Abs(BonePos("hand_l").x);
        float crotchY = BonePos("thigh_l").y - 0.08f;

        var verts = new List<Vector3>();
        var uvs = new List<Vector2>();
        var weights = new List<BoneWeight>();
        var robeTris = new List<int>();
        var beltTris = new List<int>();
        const int Sides = 36;

        BoneWeight Nearest(Vector3 p, System.Func<int, bool> allow)
        {
            float best = float.MaxValue;
            int bi = 0;
            for (int i = 0; i < n; i++)
            {
                if (!allow(i)) continue;
                float d = (V[i] - p).sqrMagnitude;
                if (d < best) { best = d; bi = i; }
            }
            return W[bi];
        }

        BoneWeight Blend(BoneWeight a, BoneWeight b, float k)
        {
            var d = new Dictionary<int, float>();
            void Add(int i, float w) { if (w <= 0) return; d.TryGetValue(i, out float o); d[i] = o + w; }
            Add(a.boneIndex0, a.weight0 * (1 - k)); Add(a.boneIndex1, a.weight1 * (1 - k)); Add(a.boneIndex2, a.weight2 * (1 - k)); Add(a.boneIndex3, a.weight3 * (1 - k));
            Add(b.boneIndex0, b.weight0 * k); Add(b.boneIndex1, b.weight1 * k); Add(b.boneIndex2, b.weight2 * k); Add(b.boneIndex3, b.weight3 * k);
            var top = d.OrderByDescending(e => e.Value).Take(4).ToList();
            float sum = top.Sum(e => e.Value);
            var r = new BoneWeight();
            if (top.Count > 0) { r.boneIndex0 = top[0].Key; r.weight0 = top[0].Value / sum; }
            if (top.Count > 1) { r.boneIndex1 = top[1].Key; r.weight1 = top[1].Value / sum; }
            if (top.Count > 2) { r.boneIndex2 = top[2].Key; r.weight2 = top[2].Value / sum; }
            if (top.Count > 3) { r.boneIndex3 = top[3].Key; r.weight3 = top[3].Value / sum; }
            return r;
        }

        BoneWeight Mix(BoneWeight a, int bone, float k)
        {
            var d = new Dictionary<int, float>();
            void Add(int i, float w) { if (w <= 0) return; d.TryGetValue(i, out float o); d[i] = o + w; }
            Add(a.boneIndex0, a.weight0 * (1 - k)); Add(a.boneIndex1, a.weight1 * (1 - k)); Add(a.boneIndex2, a.weight2 * (1 - k)); Add(a.boneIndex3, a.weight3 * (1 - k));
            Add(bone, k);
            var top = d.OrderByDescending(e => e.Value).Take(4).ToList();
            float sum = top.Sum(e => e.Value);
            var r = new BoneWeight();
            if (top.Count > 0) { r.boneIndex0 = top[0].Key; r.weight0 = top[0].Value / sum; }
            if (top.Count > 1) { r.boneIndex1 = top[1].Key; r.weight1 = top[1].Value / sum; }
            if (top.Count > 2) { r.boneIndex2 = top[2].Key; r.weight2 = top[2].Value / sum; }
            if (top.Count > 3) { r.boneIndex3 = top[3].Key; r.weight3 = top[3].Value / sum; }
            return r;
        }

        // 一圈一圈的外轮廓：center 是圈心，axisA/axisB 是这一圈所在平面的两个方向，pick 选出参与这一圈的身体顶点
        float[] Outline(Vector3 center, Vector3 axisA, Vector3 axisB, System.Func<int, bool> pick, float minR)
        {
            var r = new float[Sides];
            for (int k = 0; k < Sides; k++) r[k] = minR;
            for (int i = 0; i < n; i++)
            {
                if (!pick(i)) continue;
                Vector3 d = V[i] - center;
                float a = Vector3.Dot(d, axisA), b = Vector3.Dot(d, axisB);
                // 支撑函数：往每个方向最远伸到哪，这样包出来的是一个凸的外壳
                for (int k = 0; k < Sides; k++)
                {
                    float t = k * Mathf.PI * 2f / Sides;
                    float proj = a * Mathf.Cos(t) + b * Mathf.Sin(t);
                    if (proj > r[k]) r[k] = proj;
                }
            }
            // 沿着一圈抹平一下
            var sm = new float[Sides];
            for (int k = 0; k < Sides; k++) sm[k] = (r[(k + Sides - 1) % Sides] + 2 * r[k] + r[(k + 1) % Sides]) * 0.25f;
            return sm;
        }

        // ── 袍身：从脚踝到脖子 ──
        var heights = new List<float>();
        for (float y = ankleY + 0.03f; y < neckY - 0.01f; y += 0.035f) heights.Add(y);
        heights.Add(neckY - 0.005f);
        var rings = new List<(Vector3 c, float[] r)>();
        foreach (float y in heights)
        {
            const float dy = 0.03f;
            bool below = y < crotchY;
            System.Func<int, bool> pick = i => Mathf.Abs(V[i].y - y) < dy && (region[i] == 1 || region[i] == 2 || (region[i] == 4 && Mathf.Abs(V[i].x) < shoulderX * 0.95f));
            // 圈心：这一层的平均位置
            Vector3 c = Vector3.zero;
            int cnt = 0;
            for (int i = 0; i < n; i++) if (pick(i)) { c += V[i]; cnt++; }
            c = cnt > 0 ? c / cnt : new Vector3(0, y, 0);
            c.y = y;
            var r = Outline(c, Vector3.right, Vector3.forward, pick, 0.06f);
            float margin = y > pelvisY ? 0.022f : 0.03f + 0.10f * Mathf.InverseLerp(pelvisY, ankleY, y);
            // 领口收一点
            if (y > neckY - 0.06f) margin = 0.012f;
            for (int k = 0; k < Sides; k++) r[k] += margin;
            rings.Add((c, r));
        }
        // 上下相邻的圈之间再抹平，袍子才不会一棱一棱的；两条腿分开那几圈不能比上面窄
        for (int pass = 0; pass < 3; pass++)
            for (int j = 1; j < rings.Count - 1; j++)
                for (int k = 0; k < Sides; k++)
                    rings[j].r[k] = (rings[j - 1].r[k] + 2 * rings[j].r[k] + rings[j + 1].r[k]) * 0.25f;
        for (int j = rings.Count - 2; j >= 0; j--)
            if (heights[j] < pelvisY)
                for (int k = 0; k < Sides; k++) rings[j].r[k] = Mathf.Max(rings[j].r[k], rings[j + 1].r[k] * 0.995f);

        int start = verts.Count;
        for (int j = 0; j < rings.Count; j++)
        {
            float y = heights[j];
            bool skirt = y < pelvisY;
            for (int k = 0; k <= Sides; k++)
            {
                float t = k * Mathf.PI * 2f / Sides;
                float r = rings[j].r[k % Sides];
                Vector3 p = rings[j].c + new Vector3(Mathf.Cos(t), 0, Mathf.Sin(t)) * r;
                verts.Add(p);
                uvs.Add(new Vector2(t * 0.25f, y));
                BoneWeight w;
                if (skirt)
                {
                    // 裙摆：左半边跟左腿，右半边跟右腿，正中间两条腿各一半；只有靠近腰的那段带一点骨盆
                    var wl = Nearest(p, i => region[i] == 2 && V[i].x < 0);
                    var wr = Nearest(p, i => region[i] == 2 && V[i].x > 0);
                    float side = Mathf.SmoothStep(0, 1, Mathf.InverseLerp(-0.07f, 0.07f, p.x));
                    w = Blend(wl, wr, side);
                    w = Mix(w, pelvisBone, Mathf.Lerp(0.55f, 0.0f, Mathf.Pow(Mathf.InverseLerp(pelvisY, ankleY, y), 0.6f)));
                }
                else w = Nearest(p, i => region[i] == 1 || region[i] == 2 || region[i] == 4);
                weights.Add(w);
            }
        }
        for (int j = 0; j < rings.Count - 1; j++)
            for (int k = 0; k < Sides; k++)
            {
                int a = start + j * (Sides + 1) + k, b = a + 1, c = a + Sides + 1, d = c + 1;
                robeTris.AddRange(new[] { a, c, b, b, c, d });
            }

        // ── 腰带：腰上一圈窄带 ──
        {
            int waist = 0;
            float bestD = float.MaxValue;
            float waistY = pelvisY + 0.12f;
            for (int j = 0; j < heights.Count; j++) if (Mathf.Abs(heights[j] - waistY) < bestD) { bestD = Mathf.Abs(heights[j] - waistY); waist = j; }
            int bs = verts.Count;
            foreach (float off in new[] { -0.03f, 0.03f })
                for (int k = 0; k <= Sides; k++)
                {
                    float t = k * Mathf.PI * 2f / Sides;
                    Vector3 p = rings[waist].c + new Vector3(Mathf.Cos(t), 0, Mathf.Sin(t)) * (rings[waist].r[k % Sides] + 0.007f) + Vector3.up * off;
                    verts.Add(p);
                    uvs.Add(new Vector2(t * 0.25f, p.y));
                    weights.Add(weights[start + waist * (Sides + 1) + k]);
                }
            for (int k = 0; k < Sides; k++)
            {
                int a = bs + k, b = a + 1, c = a + Sides + 1, d = c + 1;
                beltTris.AddRange(new[] { a, c, b, b, c, d });
            }
        }

        // ── 两只袖子：沿胳膊（初始姿势里胳膊是水平伸开的）从肩膀包到手腕，袖口放宽 ──
        foreach (float side in new[] { -1f, 1f })
        {
            int ss = verts.Count;
            int count = 0;
            float x0 = shoulderX * 0.82f, x1 = wristX - 0.035f;
            for (float x = x0; x <= x1 + 0.0001f; x += (x1 - x0) / 14f)
            {
                float sx = x * side;
                System.Func<int, bool> pick = i => region[i] == 4 && Mathf.Abs(V[i].x - sx) < 0.03f;
                Vector3 c = Vector3.zero;
                int cnt = 0;
                for (int i = 0; i < n; i++) if (pick(i)) { c += V[i]; cnt++; }
                c = cnt > 0 ? c / cnt : new Vector3(sx, neckY - 0.1f, 0);
                c.x = sx;
                var r = Outline(c, Vector3.up, Vector3.forward, pick, 0.03f);
                float u = Mathf.InverseLerp(x0, x1, x);
                // 袖子：肩膀贴身一点，越往手腕越宽，最后是宽大的袖口
                float extra = 0.018f + 0.05f * u * u;
                for (int k = 0; k <= Sides; k++)
                {
                    float t = k * Mathf.PI * 2f / Sides;
                    float rr = r[k % Sides] + extra;
                    // 袖子往下垂一点
                    Vector3 p = c + new Vector3(0, Mathf.Cos(t) * rr - 0.025f * u, Mathf.Sin(t) * rr);
                    verts.Add(p);
                    uvs.Add(new Vector2(t * 0.15f, x));
                    weights.Add(Nearest(p, i => region[i] == 4 || (region[i] == 1 && Mathf.Abs(V[i].x) > shoulderX * 0.6f)));
                }
                count++;
            }
            for (int j = 0; j < count - 1; j++)
                for (int k = 0; k < Sides; k++)
                {
                    int a = ss + j * (Sides + 1) + k, b = a + 1, c = a + Sides + 1, d = c + 1;
                    if (side > 0) robeTris.AddRange(new[] { a, b, c, b, d, c });
                    else robeTris.AddRange(new[] { a, c, b, b, c, d });
                }
        }

        // ── 鞋：把脚吹胀一点 ──
        var shoeTris = new List<int>();
        {
            var norms = src.normals.Select(Up).ToArray();
            var map = new Dictionary<int, int>();
            var tris = src.triangles;
            for (int t = 0; t < tris.Length; t += 3)
            {
                if (region[tris[t]] != 3 || region[tris[t + 1]] != 3 || region[tris[t + 2]] != 3) continue;
                for (int q = 0; q < 3; q++)
                {
                    int vi = tris[t + q];
                    if (!map.TryGetValue(vi, out int ni))
                    {
                        ni = verts.Count;
                        map[vi] = ni;
                        verts.Add(V[vi] + norms[vi] * 0.008f);
                        uvs.Add(src.uv[vi]);
                        weights.Add(W[vi]);
                    }
                    shoeTris.Add(ni);
                }
            }
        }

        // 换回模型文件的坐标。Y、Z 对调相当于照了一次镜子，三角形的绕向也要倒过来
        verts = verts.Select(Up).ToList();
        void Flip(List<int> t) { for (int q = 0; q < t.Count; q += 3) (t[q + 1], t[q + 2]) = (t[q + 2], t[q + 1]); }
        Flip(robeTris);
        Flip(beltTris);
        Flip(shoeTris);
        var mesh = new Mesh { name = name, indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
        mesh.SetVertices(verts);
        mesh.SetUVs(0, uvs);
        mesh.boneWeights = weights.ToArray();
        mesh.bindposes = src.bindposes;
        mesh.subMeshCount = 3;
        mesh.SetTriangles(robeTris, 0);
        mesh.SetTriangles(beltTris, 1);
        mesh.SetTriangles(shoeTris, 2);
        mesh.RecalculateNormals();
        mesh.RecalculateTangents();
        mesh.RecalculateBounds();
        string path = $"{FolkDir}/{name}.asset";
        AssetDatabase.DeleteAsset(path);
        AssetDatabase.CreateAsset(mesh, path);
        return mesh;
    }

    /// 卡通版小人的材质：颜色是整块的，不用布料贴图
    static Material ToonFolkMat(string name, Texture2D baseMap, Color tint, bool twoSided = false)
    {
        return ToonMat("f_" + name, m =>
        {
            m.SetFloat("_Legacy", 1f);
            m.SetFloat("_Sway", 0f);
            m.SetFloat("_WetAmount", 0f);
            m.SetFloat("_SnowAmount", 0f);
            m.SetFloat("_Cull", twoSided ? 0f : 2f);
            m.SetTexture("_BaseMap", baseMap);
            m.SetColor("_BaseColor", tint);
            m.SetColor("_RimColor", new Color(1, 1, 1, 0.1f));
        });
    }

    /// 卡通版里衣服的颜色提亮、提鲜一点，远看才分得清人
    static Color Vivid(Color c, float sat = 1.25f, float val = 1.12f)
    {
        Color.RGBToHSV(c, out float h, out float s, out float v);
        return Color.HSVToRGB(h, Mathf.Clamp01(s * sat), Mathf.Clamp01(v * val));
    }

    static void FolkPrefab(FolkLook look, AnimatorController controller, bool toon = false)
    {
        Material M(string name, Texture2D baseMap, Texture2D normal, Color tint, float rough, string fabric = null, float tile = 1f)
            => toon ? ToonFolkMat(name, baseMap, fabric != null ? Vivid(tint) : tint, name.StartsWith("folk_top")) : FolkMat(name, baseMap, normal, tint, rough, fabric, tile);

        string bodyPath = look.female ? "Assets/Characters/Superhero_Female_FullBody.fbx" : "Assets/Characters/Superhero_Male_FullBody.fbx";
        var root = new GameObject((toon ? "Folk_toon_" : "Folk_") + look.name);
        var modelGo = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(bodyPath));
        PrefabUtility.UnpackPrefabInstance(modelGo, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
        modelGo.name = "Model";
        modelGo.transform.SetParent(root.transform, false);
        var anim = modelGo.GetComponent<Animator>() ?? modelGo.AddComponent<Animator>();
        anim.avatar = AssetDatabase.LoadAllAssetsAtPath(bodyPath).OfType<Avatar>().First();
        anim.runtimeAnimatorController = null;
        anim.applyRootMotion = false;
        anim.cullingMode = AnimatorCullingMode.AlwaysAnimate;

        var bones = modelGo.GetComponentsInChildren<Transform>().GroupBy(t => t.name).ToDictionary(g => g.Key, g => g.First());
        var renderers = modelGo.GetComponentsInChildren<SkinnedMeshRenderer>();
        var body = renderers.First(r => r.name.ToLowerInvariant().Contains("superhero"));
        string g = look.female ? "Female" : "Male";
        Texture2D skinTex = look.female ? CharTex(look.darkSkin ? "T_Superhero_Female_Dark_BaseColor" : "T_Superhero_Female_Light_BaseColor")
            : CharTex(look.darkSkin ? "T_Superhero_Male_Dark" : "T_Superhero_Male_Ligh");
        var skin = M($"folk_skin_{g}_{(look.darkSkin ? "d" : "l")}", skinTex, CharTex($"T_Superhero_{g}_Normal"), Color.white, 0.62f);
        body.sharedMaterial = skin;
        var hairMat = M($"folk_hair_{look.name}", CharTex("T_Hair_1_BaseColor"), CharTex("T_Hair_1_Normal"), look.hairColor * 3.2f, 0.55f);
        foreach (var r in renderers)
        {
            if (r == body) continue;
            if (r.name.StartsWith("Eyes")) r.sharedMaterial = M("folk_eyes", CharTex("T_Eye_Brown"), null, Color.white, 0.15f);
            else r.sharedMaterial = hairMat;
        }

        // 衣服
        var cloth = new GameObject("Cloth").AddComponent<SkinnedMeshRenderer>();
        cloth.transform.SetParent(modelGo.transform, false);
        cloth.sharedMesh = RobeMesh(body, $"robe_{g}");
        cloth.bones = body.bones;
        cloth.rootBone = body.rootBone;
        cloth.localBounds = body.localBounds;
        var robeMat = M($"folk_top_{look.name}", null, null, look.top, 1f, "linen", 0.22f);
        robeMat.SetFloat("_Cull", 0f);
        cloth.sharedMaterials = new[]
        {
            robeMat,
            M($"folk_belt_{look.name}", null, null, look.pants, 0.9f, "linen", 0.15f),
            toon ? ToonFolkMat("folk_shoes", null, new Color(0.16f, 0.13f, 0.12f)) : FolkMat("folk_shoes", null, null, new Color(0.10f, 0.09f, 0.085f), 0.8f, "linen", 0.15f),
        };

        // 发型：发型文件和身体用同一套骨骼名字，按名字接到这个人的骨骼上
        if (!string.IsNullOrEmpty(look.hair))
        {
            var hairAsset = AssetDatabase.LoadAssetAtPath<GameObject>($"Assets/Characters/Hair/{look.hair}.fbx");
            var src = hairAsset.GetComponentsInChildren<SkinnedMeshRenderer>().First();
            var hair = new GameObject("Hair").AddComponent<SkinnedMeshRenderer>();
            hair.transform.SetParent(modelGo.transform, false);
            hair.sharedMesh = src.sharedMesh;
            hair.bones = src.bones.Select(b => bones.TryGetValue(b.name, out var t) ? t : body.rootBone).ToArray();
            hair.rootBone = body.rootBone;
            hair.localBounds = body.localBounds;
            hair.sharedMaterial = hairMat;
        }

        foreach (var r in modelGo.GetComponentsInChildren<SkinnedMeshRenderer>())
        {
            r.updateWhenOffscreen = false;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
            r.quality = SkinQuality.Bone4;
        }

        // 卡通版：有几位戴斗笠（Blender 做的），挂在头的骨头上，跟着头一起放大
        if (toon && look.hat)
        {
            var head = anim.GetBoneTransform(HumanBodyBones.Head);
            var hat = Put("hat", null, head.position + Vector3.up * 0.17f, 0, 0.6f, "Hat");
            if (hat != null)
            {
                foreach (var t in hat.GetComponentsInChildren<Transform>()) t.gameObject.isStatic = false;
                PrefabUtility.UnpackPrefabInstance(hat, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
                hat.transform.SetParent(head, true);
            }
        }

        // 名字：头顶一行字
        var tagGo = new GameObject("Name");
        tagGo.transform.SetParent(root.transform, false);
        var tag = tagGo.AddComponent<TextMesh>();
        tag.font = NameFont();
        tag.fontSize = 64;
        tag.characterSize = 0.012f;
        tag.anchor = TextAnchor.LowerCenter;
        tag.alignment = TextAlignment.Center;
        tag.color = Color.white;
        tagGo.GetComponent<MeshRenderer>().sharedMaterial = tag.font.material;
        tagGo.SetActive(false);

        var folk = root.AddComponent<Folk>();
        folk.animator = anim;
        folk.idleClip = Clip("Idle_Loop");
        folk.walkClip = Clip("Walk_Formal_Loop");
        folk.walkFastClip = Clip("Walk_Loop");
        folk.sitClip = Clip("Sitting_Idle_Loop");
        folk.model = modelGo.transform;
        folk.nameTag = tag;
        // 整体缩到 Q 版的个头（约 1.2 米）
        root.transform.localScale = Vector3.one * 0.6f;
        PrefabUtility.SaveAsPrefabAsset(root, $"{FolkDir}/{root.name}.prefab");
        Object.DestroyImmediate(root);
    }

    static Font NameFont()
    {
        const string path = "Assets/Fonts/SourceHanSerifCN-Medium.otf";
        if (!File.Exists(path))
        {
            Directory.CreateDirectory("Assets/Fonts");
            File.Copy("../../assets/fonts/SourceHanSerifCN-Medium.otf", path);
            AssetDatabase.ImportAsset(path);
        }
        return AssetDatabase.LoadAssetAtPath<Font>(path);
    }

    public static void SinkDebug()
    {
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"{FolkDir}/Folk_me.prefab");
        var go = (GameObject)Object.Instantiate(prefab);
        var folk = go.GetComponent<Folk>();
        var anim = go.GetComponentInChildren<Animator>();
        Debug.Log("[yuanjing] 实例化后 模型局部高度 " + folk.model.localPosition.y + " 左脚 " + anim.GetBoneTransform(HumanBodyBones.LeftFoot).position.y);
        folk.Init();
        anim.Rebind();
        anim.Update(0f);
        Debug.Log("[yuanjing] 初始化 " + folk.DebugSink());
        for (int i = 1; i <= 60; i++)
        {
            folk.DebugFrame(1f / 60f);
            if (i % 30 == 0) Debug.Log($"[yuanjing] 按游戏顺序 第 {i} 帧 " + folk.DebugSink());
        }
        folk.EditorPose("Move", 0, 0.3f, Folk.Pose.None, 0);
        Debug.Log("[yuanjing] 站着 " + folk.DebugSink());
        folk.EditorPose("Move", 0, 0.3f, Folk.Pose.None, 0);
        Debug.Log("[yuanjing] 再一帧 " + folk.DebugSink());
        for (int i = 1; i <= 120; i++)
        {
            folk.DebugFrame(1f / 60f);
            if (i % 30 == 0) Debug.Log($"[yuanjing] 第 {i} 帧 " + folk.DebugSink());
        }
    }

    /// 出一组小人的预览图：-poses "样子|姿势|鞠躬深浅|动作|位置|朝向;..."，镜头同 Preview 的 -shots
    public static void FolkPreview()
    {
        string scene = Arg("-scene") ?? "Temple";
        UnityEditor.SceneManagement.EditorSceneManager.OpenScene($"Assets/Scenes/{scene}.unity");
        foreach (var old in Object.FindObjectsByType<Pilgrims>(FindObjectsSortMode.None)) old.enabled = false;
        foreach (string spec in (Arg("-poses") ?? "").Split(';'))
        {
            var f = spec.Split('|');
            if (f.Length < 6) continue;
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"{FolkDir}/Folk_{f[0]}.prefab");
            var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            go.transform.position = Vec(f[4]);
            go.transform.rotation = Quaternion.Euler(0, float.Parse(f[5]), 0);
            var folk = go.GetComponent<Folk>();
            var pose = (Folk.Pose)System.Enum.Parse(typeof(Folk.Pose), f[1], true);
            if (f.Length > 7)
                foreach (string kv in f[7].Split(','))
                {
                    var q = kv.Split('=');
                    if (q.Length != 2) continue;
                    if (q[0] == "pitch") folk.customPitch = float.Parse(q[1]);
                    else folk.custom[q[0]] = float.Parse(q[1]);
                }
            bool sit = pose == Folk.Pose.Bench || pose == Folk.Pose.CrossLegged;
            float speed = f[3] == "walk" ? 0.6f : 0f;
            folk.EditorPose(sit ? "SitIdle" : "Move", speed, 0.3f, pose, float.Parse(f[2]));
            if (f.Length > 6) folk.SetName(f[6], Color.white);
        }
        RenderShots();
    }
}
