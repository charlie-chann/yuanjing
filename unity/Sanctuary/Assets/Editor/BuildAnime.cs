using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Animations;
using UnityEngine.Playables;
using UnityEngine.Rendering;
using Yuanjing;

/// 动漫人物：VRM 模型先用 tools/blender/vrm_import.py 转成 FBX、贴图和一份说明（材质参数、会摆动的骨骼），
/// 这里按说明建材质、拼成和 Q 版小人一样用法的预制体（Folk_anime_名字），动作、姿势、名字牌都沿用。
public static partial class SanctuaryBuild
{
    const string AnimeDir = "Assets/Characters/Anime";

    [Serializable] class AnimeMatInfo { public string name, tex, shadeTex; public float[] color, shade, outlineColor; public float outline, cutoff; public int blend, cull, queue; }
    [Serializable] class AnimeMeshInfo { public string name; public string[] materials; }
    [Serializable] class AnimeSpringInfo { public float stiff, gravity, drag, radius; public string[] roots; }
    [Serializable] class AnimeInfo { public string name; public AnimeMatInfo[] materials; public AnimeMeshInfo[] meshes; public AnimeSpringInfo[] springs; }

    static Color C4(float[] a, Color fallback) => a != null && a.Length >= 3 ? new Color(a[0], a[1], a[2], a.Length > 3 ? a[3] : 1f) : fallback;

    static Material AnimeMat(string who, AnimeMatInfo info, int order)
    {
        string dir = $"{AnimeDir}/{who}";
        Directory.CreateDirectory($"{dir}/Materials");
        string path = $"{dir}/Materials/{info.name}.mat";
        var sh = Shader.Find("Yuanjing/Anime");
        var m = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (m == null) { m = new Material(sh); AssetDatabase.CreateAsset(m, path); }
        m.shader = sh;
        Texture2D T(string f) => string.IsNullOrEmpty(f) ? null : AssetDatabase.LoadAssetAtPath<Texture2D>($"{dir}/Textures/{f}");
        var main = T(info.tex);
        m.SetTexture("_MainTex", main);
        m.SetTexture("_ShadeTex", T(info.shadeTex) ?? main);
        m.SetColor("_Color", C4(info.color, Color.white));
        m.SetColor("_ShadeColor", C4(info.shade, new Color(0.8f, 0.76f, 0.86f)));
        bool skin = info.name.EndsWith("_SKIN") || info.name.EndsWith("_FACE") || info.name.EndsWith("_EYE");
        // 脸和皮肤：过渡柔、亮面多（鼻子旁边不切硬影子）；衣服头发：两段分明
        m.SetFloat("_ShadeShift", skin ? -0.4f : -0.12f);
        m.SetFloat("_Toony", skin ? 0.2f : 0.78f);
        m.SetFloat("_Cutoff", info.cutoff);
        m.SetFloat("_Cull", info.cull);
        m.SetFloat("_Ambient", 0.5f);
        m.SetFloat("_SunScale", 0.2f);
        bool transparent = info.blend >= 2, cutout = info.blend == 1;
        m.SetFloat("_AlphaClip", cutout ? 1f : 0f);
        m.SetFloat("_SrcBlend", (float)(transparent ? BlendMode.SrcAlpha : BlendMode.One));
        m.SetFloat("_DstBlend", (float)(transparent ? BlendMode.OneMinusSrcAlpha : BlendMode.Zero));
        m.SetFloat("_ZWrite", transparent ? 0f : 1f);
        m.renderQueue = transparent ? 3000 + order : cutout ? 2450 : 2000;
        m.SetOverrideTag("RenderType", transparent ? "Transparent" : cutout ? "TransparentCutout" : "Opaque");
        // 描边：半透明的（睫毛、眉毛、眼睛高光）和眼睛、嘴里面不描
        bool outline = !transparent && info.outline > 0.001f && !info.name.EndsWith("_EYE") && !info.name.Contains("Mouth");
        m.SetFloat("_OutlineWidth", outline ? info.outline * 1.2f : 0f);
        var oc = C4(info.outlineColor, Color.black);
        m.SetColor("_OutlineColor", new Color(Mathf.Max(oc.r, 0.34f), Mathf.Max(oc.g, 0.24f), Mathf.Max(oc.b, 0.3f)));
        m.SetShaderPassEnabled("SRPDefaultUnlit", outline);
        foreach (string pass in new[] { "ShadowCaster", "DepthOnly", "DepthNormals" }) m.SetShaderPassEnabled(pass, !transparent);
        EditorUtility.SetDirty(m);
        return m;
    }

    /// 裙子防穿帮的材质设置（YJAnime.shader 的 SkirtFix 那一遍）。role：0 不画这一遍；1 皮肤，在模板里标出看得见的腿和臀部；
    /// 2 裙子，在标出的地方再画一遍、深度往镜头挪 5 厘米（被腿顶穿的地方还是裙子在外面）。裙子排在皮肤后面一格画（同一个网格里先画皮肤、标好模板）
    static void SkirtFixMat(Material m, int role)
    {
        m.SetFloat("_SkirtFix", role);
        m.SetFloat("_SkirtPush", 0.05f);
        m.SetFloat("_SkirtComp", (float)(role == 2 ? CompareFunction.Equal : CompareFunction.Always));
        m.SetFloat("_SkirtOp", (float)(role == 1 ? StencilOp.Replace : StencilOp.Keep));
        m.SetFloat("_SkirtColorMask", role == 2 ? 15f : 0f);
        m.SetShaderPassEnabled("UniversalForwardOnly", role > 0);
        if (role == 2) m.renderQueue += 1;
        EditorUtility.SetDirty(m);
    }

    /// 裙子防穿帮：把人身上的网格复制一份，第四套 UV（TEXCOORD3）的 x 标出主要跟着髋、大腿走的点（腿和臀部是 1；手、胳膊、上身是 0），
    /// 存在人物文件夹里（{名字}_{网格}_legs.asset；重建时写进同一个文件，预制体的引用不变）
    static void MarkLegs(string who, SkinnedMeshRenderer r, Animator anim)
    {
        var src = r.sharedMesh;
        if (src == null) return;
        var legs = new[] { HumanBodyBones.Hips, HumanBodyBones.LeftUpperLeg, HumanBodyBones.RightUpperLeg }.Select(anim.GetBoneTransform).Where(t => t != null).ToArray();
        var isLeg = r.bones.Select(b => b != null && legs.Contains(b)).ToArray();
        var weights = src.boneWeights;
        if (weights.Length != src.vertexCount || isLeg.Length == 0) return;
        float W(int bone, float w) => bone >= 0 && bone < isLeg.Length && isLeg[bone] ? w : 0f;
        var marks = new System.Collections.Generic.List<Vector2>(src.vertexCount);
        int marked = 0;
        foreach (var w in weights)
        {
            float s = W(w.boneIndex0, w.weight0) + W(w.boneIndex1, w.weight1) + W(w.boneIndex2, w.weight2) + W(w.boneIndex3, w.weight3);
            marks.Add(new Vector2(s >= 0.5f ? 1f : 0f, 0f));
            if (s >= 0.5f) marked++;
        }
        var mesh = UnityEngine.Object.Instantiate(src);
        mesh.name = src.name + "_legs";
        mesh.SetUVs(3, marks);
        string path = $"{AnimeDir}/{who}/{who}_{r.name}_legs.asset";
        var old = AssetDatabase.LoadAssetAtPath<Mesh>(path);
        if (old != null)
        {
            EditorUtility.CopySerialized(mesh, old);
            old.name = mesh.name;
            UnityEngine.Object.DestroyImmediate(mesh);
            mesh = old;
            EditorUtility.SetDirty(mesh);
        }
        else AssetDatabase.CreateAsset(mesh, path);
        r.sharedMesh = mesh;
        Debug.Log($"[yuanjing] 裙子防穿帮 {who}/{r.name}：{src.vertexCount} 个点里 {marked} 个算腿和臀部");
    }

    static AnimationClip MotionClip(string name) =>
        AssetDatabase.LoadAllAssetsAtPath($"Assets/Motion/{name}.fbx").OfType<AnimationClip>().FirstOrDefault(c => !c.name.StartsWith("__preview") && !c.name.EndsWith("_Mirror"));

    /// 同一个 FBX 里导入时镜像出来的那份（CharacterImport：停步、转身起步）
    static AnimationClip MirrorClip(string name) =>
        AssetDatabase.LoadAllAssetsAtPath($"Assets/Motion/{name}.fbx").OfType<AnimationClip>().FirstOrDefault(c => c.name == name + "_Mirror");

    // tools/mocap/locomotion.py 写的 Assets/Motion/Locomotion.json：停步从哪进、多久站稳、走多远，转身起步转多少度
    [Serializable] class LocoClipInfo { public string name, kind; public float length, entryEnd, still, angle, exitPhase; public bool left; public float[] dist, steps; }
    [Serializable] class LocoInfo { public LocoClipInfo[] clips; }

    static LocoClipInfo LocoMeta(string name)
    {
        const string path = "Assets/Motion/Locomotion.json";
        if (!File.Exists(path)) return null;
        var info = JsonUtility.FromJson<LocoInfo>(File.ReadAllText(path));
        return info?.clips?.FirstOrDefault(c => c.name == name);
    }

    /// 一段走路片段在这个人物上：着地脚相对人往后退的速度 ÷ 根运动的速度（只算一只脚明显踩着、另一只抬着的帧）
    static float FootScale(Animator anim, AnimationClip clip)
    {
        var bz = AnimationUtility.GetEditorCurve(clip, EditorCurveBinding.FloatCurve("", typeof(Animator), "RootT.z"));
        var bx = AnimationUtility.GetEditorCurve(clip, EditorCurveBinding.FloatCurve("", typeof(Animator), "RootT.x"));
        if (bz == null || bx == null) return 1f;
        var t = anim.transform;
        var lf = anim.GetBoneTransform(HumanBodyBones.LeftFoot);
        var rf = anim.GetBoneTransform(HumanBodyBones.RightFoot);
        var graph = PlayableGraph.Create("footscale");
        var output = AnimationPlayableOutput.Create(graph, "a", anim);
        var cp = AnimationClipPlayable.Create(graph, clip);
        cp.SetApplyFootIK(true);
        output.SetSourcePlayable(cp);
        const int N = 160;
        var L = new Vector3[N + 1];
        var R = new Vector3[N + 1];
        float minL = 9, minR = 9;
        for (int f = 0; f <= N; f++)
        {
            cp.SetTime(clip.length * f / N);
            graph.Evaluate(0);
            L[f] = t.InverseTransformPoint(lf.position);
            R[f] = t.InverseTransformPoint(rf.position);
            minL = Mathf.Min(minL, L[f].y);
            minR = Mathf.Min(minR, R[f].y);
        }
        graph.Destroy();
        float k = anim.humanScale * t.lossyScale.y;
        var pairs = new System.Collections.Generic.List<Vector2>();
        for (int f = 1; f <= N; f++)
        {
            float dt = clip.length / N, t0 = clip.length * (f - 1) / N, t1 = clip.length * f / N;
            bool l = L[f].y < minL + 0.01f && L[f].y < R[f].y - 0.015f, r = R[f].y < minR + 0.01f && R[f].y < L[f].y - 0.015f;
            if (!l && !r) continue;
            Vector3 a = l ? L[f - 1] : R[f - 1], b = l ? L[f] : R[f];
            float rv = new Vector2(bx.Evaluate(t1) - bx.Evaluate(t0), bz.Evaluate(t1) - bz.Evaluate(t0)).magnitude * k;
            if (rv < 0.2f * dt) continue;
            pairs.Add(new Vector2(new Vector2(a.x - b.x, a.z - b.z).magnitude, rv));
        }
        if (pairs.Count == 0) return 1f;
        // 根运动曲线偶尔有一帧冲出去的尖（压缩、接缝）：比中位数大很多的那几帧不算
        var rs = pairs.Select(v => v.y).OrderBy(v => v).ToArray();
        float med = rs[rs.Length / 2];
        double foot = 0, root = 0;
        foreach (var v in pairs)
            if (v.y < med * 1.6f) { foot += v.x; root += v.y; }
        return root > 1e-4 ? Mathf.Clamp((float)(foot / root), 0.7f, 1.5f) : 1f;
    }

    /// 停步从哪一刻接进来：每段步态在相位 0、0.05 … 0.5（左脚着地后的半步）时，停步片段里哪一刻的姿势最像（踩着的左脚、迈着的右脚、髋，相对根）。
    /// 快走的步子大，同一相位上身子已经越过支撑脚更多；按时间比例对应（t = 相位/0.5 × entry）的话两边差 13–23 厘米，
    /// 淡进停步那 0.18 秒里支撑脚被往前拽、迈着的脚被往后拽（一顿）
    static float[] StopMap(Animator anim, AnimationClip[] gaits, AnimationClip stop, float entry)
    {
        if (stop == null || gaits == null || gaits.Length == 0) return null;
        var t = anim.transform;
        var bones = new[] { HumanBodyBones.LeftFoot, HumanBodyBones.LeftToes, HumanBodyBones.RightFoot, HumanBodyBones.RightToes, HumanBodyBones.Hips };
        float[] wts = { 2f, 1f, 1f, 1f, 1f };
        var graph = PlayableGraph.Create("stopmap");
        var output = AnimationPlayableOutput.Create(graph, "a", anim);
        Vector3[] Pose(AnimationClip c, float time)
        {
            var cp = AnimationClipPlayable.Create(graph, c);
            cp.SetApplyFootIK(true);
            output.SetSourcePlayable(cp);
            cp.SetTime(time);
            graph.Evaluate(0);
            var r = bones.Select(b => t.InverseTransformPoint(anim.GetBoneTransform(b).position)).ToArray();
            cp.Destroy();
            return r;
        }
        const int K = 11, M = 64;
        float tMax = Mathf.Min(stop.length, entry + 0.25f);
        var cand = Enumerable.Range(0, M + 1).Select(j => tMax * j / M).ToArray();
        var stopPoses = cand.Select(x => Pose(stop, x)).ToArray();
        var map = new float[gaits.Length * K];
        for (int i = 0; i < gaits.Length; i++)
        {
            float prev = 0;
            for (int k = 0; k < K; k++)
            {
                float ph = 0.5f * k / (K - 1);
                var g = Pose(gaits[i], ph * gaits[i].length);
                float best = 1e9f, bt = prev;
                for (int j = 0; j <= M; j++)
                {
                    if (cand[j] < prev - 1e-4f) continue;      // 不往回（单调）
                    float c = 0;
                    for (int b = 0; b < bones.Length; b++) c += wts[b] * (stopPoses[j][b] - g[b]).magnitude;
                    if (c < best) { best = c; bt = cand[j]; }
                }
                map[i * K + k] = prev = bt;
            }
        }
        graph.Destroy();
        return map;
    }

    /// 走路：男女各一套步态循环（慢、中、较快、快）、停步、转身起步（tools/mocap/locomotion.py 加工，见 Folk 的说明）
    static void SetGait(Folk folk, bool male)
    {
        string g = male ? "M" : "F", sfx = male ? "" : "_F";
        folk.gaitClips = new[] { $"Walk_{g}_Slow", $"Walk_{g}", $"Walk_{g}_Fast", $"Walk_{g}_Brisk" }.Select(MotionClip).Where(c => c != null).ToArray();
        folk.stopClip = MotionClip("Walk_Stop" + sfx);
        folk.stopMirrorClip = MirrorClip("Walk_Stop" + sfx);
        folk.turnClip = MotionClip("Walk_TurnStart" + sfx);
        folk.turnMirrorClip = MirrorClip("Walk_TurnStart" + sfx);
        var st = LocoMeta("Walk_Stop" + sfx);
        if (st != null)
        {
            folk.stopEntry = st.entryEnd;
            folk.stopStill = st.still;
            folk.stopDist = st.dist;
            folk.stopSteps = st.steps;
        }
        var tu = LocoMeta("Walk_TurnStart" + sfx);
        if (tu != null)
        {
            folk.turnAngle = tu.angle;
            folk.turnLeft = tu.left;
            folk.turnExitPhase = tu.exitPhase;
            // 转身时先挪的那一小步（片段里脚抬得低，自动找不出来）
            folk.turnSteps = new[] { 0.42f }.Concat(tu.steps ?? new float[0]).ToArray();
        }
        // 量一下：在这个人身上，踩在地上的那只脚往后退得比动画的根运动快多少（人形重定向后步子和根运动对不上，约 1.1–1.2 倍）。
        // 游戏里按这个倍数放大根运动，脚就不滑
        var anim = folk.animator;
        folk.gaitFootScale = folk.gaitClips.Select(c => FootScale(anim, c)).ToArray();
        folk.stopFootScale = folk.stopClip != null ? FootScale(anim, folk.stopClip) : 1f;
        folk.turnFootScale = folk.turnClip != null ? FootScale(anim, folk.turnClip) : 1f;
        Debug.Log($"[yuanjing] 步子/根运动：步态 {string.Join("、", folk.gaitFootScale.Select(x => x.ToString("F3")))}，停步 {folk.stopFootScale:F3}，转身 {folk.turnFootScale:F3}");
        folk.stopMap = StopMap(anim, folk.gaitClips, folk.stopClip, folk.stopEntry);
        if (folk.stopMap != null)
            Debug.Log($"[yuanjing] 停步接入时刻（各段步态，相位 0..0.5）：" + string.Join(" | ", Enumerable.Range(0, folk.gaitClips.Length).Select(i => folk.gaitClips[i].name + " " + string.Join(",", Enumerable.Range(0, 11).Select(k => folk.stopMap[i * 11 + k].ToString("F2"))))));
        if (folk.gaitClips.Length > 0)
        {
            folk.walkClip = folk.gaitClips[0];
            folk.walkFastClip = folk.gaitClips[folk.gaitClips.Length - 1];
        }
        Debug.Log($"[yuanjing] 走路：{string.Join("、", folk.gaitClips.Select(c => $"{c.name} {c.averageSpeed.magnitude:F2}/{c.length:F2}s"))}；停步 {folk.stopClip?.name}/{folk.stopMirrorClip?.name}；转身 {folk.turnClip?.name}/{folk.turnMirrorClip?.name}");
    }

    /// 把 Assets/Characters/Anime 下每个转好的人物拼成预制体。返回做了几个
    static int AnimeFolkPrefabs()
    {
        if (!Directory.Exists(AnimeDir)) return 0;
        int done = 0;
        foreach (string dir in Directory.GetDirectories(AnimeDir))
        {
            string who = Path.GetFileName(dir);
            string fbx = $"{AnimeDir}/{who}/{who}.fbx", json = $"{AnimeDir}/{who}/{who}.json";
            if (!File.Exists(fbx) || !File.Exists(json)) continue;
            var info = JsonUtility.FromJson<AnimeInfo>(File.ReadAllText(json));
            var avatar = AssetDatabase.LoadAllAssetsAtPath(fbx).OfType<Avatar>().FirstOrDefault();
            if (avatar == null || !avatar.isValid || !avatar.isHuman)
            {
                Debug.LogWarning($"[yuanjing] 动漫人物 {who}：人形骨骼没认出来（avatar={(avatar == null ? "无" : $"valid={avatar.isValid} human={avatar.isHuman}")}），跳过");
                continue;
            }
            var root = new GameObject($"Folk_anime_{who}");
            var modelGo = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(fbx));
            PrefabUtility.UnpackPrefabInstance(modelGo, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            modelGo.name = "Model";
            modelGo.transform.SetParent(root.transform, false);
            var anim = modelGo.GetComponent<Animator>() ?? modelGo.AddComponent<Animator>();
            anim.avatar = avatar;
            anim.runtimeAnimatorController = null;
            anim.applyRootMotion = false;
            anim.cullingMode = AnimatorCullingMode.AlwaysAnimate;

            var mats = info.materials.Select((mi, i) => (mi.name, mat: AnimeMat(who, mi, i))).ToDictionary(x => x.name, x => x.mat);
            // 裙子防穿帮（YJAnime 的 SkirtFix 那一遍）：穿裙子的人（有裙摆骨头），身上的皮肤标出腿和臀部，裙子在标出的地方补画一遍
            bool hasSkirt = info.springs != null && info.springs.Any(sp => sp.roots != null && sp.roots.Any(n => n.Contains("Skirt")));
            foreach (var kv in mats)
                SkirtFixMat(kv.Value, !hasSkirt ? 0 : kv.Key.Contains("Body") && kv.Key.EndsWith("_SKIN") ? 1 : kv.Key.Contains("Bottoms") ? 2 : 0);
            foreach (var r in modelGo.GetComponentsInChildren<SkinnedMeshRenderer>())
            {
                var mesh = info.meshes.FirstOrDefault(x => x.name == r.name);
                if (mesh == null) { Debug.LogWarning($"[yuanjing] 动漫人物 {who}：说明里没有网格 {r.name}"); continue; }
                if (mesh.materials.Length != r.sharedMaterials.Length)
                    Debug.LogWarning($"[yuanjing] 动漫人物 {who}：{r.name} 的材质数对不上（说明 {mesh.materials.Length}，模型 {r.sharedMaterials.Length}）");
                r.sharedMaterials = Enumerable.Range(0, r.sharedMaterials.Length).Select(i => mats[mesh.materials[Mathf.Min(i, mesh.materials.Length - 1)]]).ToArray();
                r.updateWhenOffscreen = false;
                // 包围盒照模型里存的（站着的那一份）：坐下、跪下时 Folk 自己换成装得下低姿势的那一份（见 Folk.UpdateBounds）
                r.shadowCastingMode = ShadowCastingMode.On;
                r.quality = SkinQuality.Bone4;
                // 眨眼
                for (int i = 0; i < r.sharedMesh.blendShapeCount; i++)
                {
                    string bn = r.sharedMesh.GetBlendShapeName(i);
                    if (bn == "Blink" || bn.EndsWith(".Blink"))
                    {
                        var blink = modelGo.AddComponent<Blink>();
                        blink.face = r;
                        blink.shape = i;
                        break;
                    }
                }
            }

            // 裙子防穿帮：带皮肤材质的网格换成标好腿和臀部的那一份
            if (hasSkirt)
                foreach (var r in modelGo.GetComponentsInChildren<SkinnedMeshRenderer>())
                    if (r.sharedMaterials.Any(m => m != null && m.GetFloat("_SkirtFix") > 0.5f && m.GetFloat("_SkirtFix") < 1.5f)) MarkLegs(who, r, anim);

            // 头发、裙摆的摆动
            var all = modelGo.GetComponentsInChildren<Transform>().GroupBy(t => t.name).ToDictionary(g => g.Key, g => g.First());
            var sb = modelGo.AddComponent<SpringBones>();
            foreach (var s in info.springs)
            {
                var roots = s.roots.Where(all.ContainsKey).Select(n => all[n]).ToArray();
                if (roots.Length == 0) continue;
                bool skirt = roots[0].name.Contains("Skirt");
                // 裙子加一点重力：腿抬起来、分开坐的时候裙摆往下垂，搭在腿上
                sb.groups.Add(new SpringBones.Group { roots = roots, stiffness = skirt ? Mathf.Min(s.stiff, 0.35f) : s.stiff, gravity = skirt ? Mathf.Max(s.gravity, 0.6f) : s.gravity, drag = Mathf.Clamp01(s.drag) });
            }
            // 大腿上各三个碰撞球、臀部一个：裙子被推到腿的外面，不穿过去
            foreach (var (up, low) in new[] { (HumanBodyBones.LeftUpperLeg, HumanBodyBones.LeftLowerLeg), (HumanBodyBones.RightUpperLeg, HumanBodyBones.RightLowerLeg) })
            {
                var a = anim.GetBoneTransform(up); var b = anim.GetBoneTransform(low);
                float thick = Vector3.Distance(a.position, b.position) * 0.2f / Mathf.Max(0.01f, a.lossyScale.y);
                foreach (float t in new[] { 0.15f, 0.5f, 0.85f })
                    sb.colliders.Add(new SpringBones.Sphere { from = a, to = b, t = t, radius = thick * (1.1f - 0.3f * t) });
            }


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
            // 动作：动捕的站立、走路（男女分开），自己做的合掌、鞠躬、跪拜、盘坐（Assets/Motion/）
            bool male = who == "fumiriya" || who == "hs_male";
            folk.idleClips = (male ? new[] { "Idle_Neutral", "Idle_Side", "Idle_Behind", "Idle_Folded", "Idle_LookUp", "Idle_Monk" }
                                   : new[] { "Idle_Neutral", "Idle_Side", "Idle_Behind", "Idle_LookUp" })
                .Select(MotionClip).Where(c => c != null).ToArray();
            folk.idleClip = folk.idleClips.Length > 0 ? folk.idleClips[0] : Clip("Idle_Loop");
            // 走路：男女各一套同步的步态（女生是改得更轻巧的那套），加停步、转身起步
            folk.walkClip = MotionClip("Walk_M") ?? Clip("Walk_Formal_Loop");
            folk.walkFastClip = MotionClip("Walk_M") ?? Clip("Walk_Loop");
            SetGait(folk, male);
            folk.sitClip = Clip("Sitting_Idle_Loop");
            folk.actionClips = new[] { "Gassho_In", "Gassho_Loop", "Gassho_Out", "Gassho_Scrub", "Bow_Scrub", "Kneel_Down", "Kneel_Loop",
                "Kowtow_Scrub", "Kneel_Up", "Sit_Down", "Sit_Loop", "SitBow_Scrub", "Sit_Up",
                "Hang_In", "Hang_Loop", "Hang_Out", "Incense_In", "Incense_Scrub", "Incense_Plant", "Incense_Out" }.Select(MotionClip).Where(c => c != null).ToArray();
            folk.model = modelGo.transform;
            folk.nameTag = tag;
            // 动漫人物是正常的头身比，不做 Q 版的大头
            folk.headScale = folk.neckScale = folk.legScale = folk.armScale = 1f;
            // 个头和 Q 版小人差不多（约 1.25 米），岛上的门、蒲团、栏杆都是按这个个头做的
            float height = anim.GetBoneTransform(HumanBodyBones.Head).position.y + 0.13f;
            // 统一按同一个比例缩（1.55 米的人缩成 1.25 米），高的男生还是比女生高
            root.transform.localScale = Vector3.one * (1.25f / 1.55f);
            PrefabUtility.SaveAsPrefabAsset(root, $"{FolkDir}/{root.name}.prefab");
            UnityEngine.Object.DestroyImmediate(root);
            Debug.Log($"[yuanjing] 动漫人物 {who}：身高 {height:F2} 米，摆动骨骼 {sb.groups.Count} 组，材质 {mats.Count} 个");
            done++;
        }
        AssetDatabase.SaveAssets();
        return done;
    }
}
