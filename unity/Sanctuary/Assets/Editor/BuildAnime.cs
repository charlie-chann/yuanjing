using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
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

    static AnimationClip MotionClip(string name) =>
        AssetDatabase.LoadAllAssetsAtPath($"Assets/Motion/{name}.fbx").OfType<AnimationClip>().FirstOrDefault(c => !c.name.StartsWith("__preview"));

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
            foreach (var r in modelGo.GetComponentsInChildren<SkinnedMeshRenderer>())
            {
                var mesh = info.meshes.FirstOrDefault(x => x.name == r.name);
                if (mesh == null) { Debug.LogWarning($"[yuanjing] 动漫人物 {who}：说明里没有网格 {r.name}"); continue; }
                if (mesh.materials.Length != r.sharedMaterials.Length)
                    Debug.LogWarning($"[yuanjing] 动漫人物 {who}：{r.name} 的材质数对不上（说明 {mesh.materials.Length}，模型 {r.sharedMaterials.Length}）");
                r.sharedMaterials = Enumerable.Range(0, r.sharedMaterials.Length).Select(i => mats[mesh.materials[Mathf.Min(i, mesh.materials.Length - 1)]]).ToArray();
                r.updateWhenOffscreen = false;
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
            // 女生原来用的 CMU 走路（Walk_F）身子是横着的、手抬着，像螃蟹走；都改用 100STYLE 的正常走路
            folk.walkClip = MotionClip(male ? "Walk_Monk" : "Walk_M") ?? Clip("Walk_Formal_Loop");
            folk.walkFastClip = MotionClip("Walk_M") ?? Clip("Walk_Loop");
            folk.sitClip = Clip("Sitting_Idle_Loop");
            folk.actionClips = new[] { "Gassho_In", "Gassho_Loop", "Gassho_Out", "Gassho_Scrub", "Bow_Scrub", "Kneel_Down", "Kneel_Loop",
                "Kowtow_Scrub", "Kneel_Up", "Sit_Down", "Sit_Loop", "SitBow_Scrub", "Sit_Up" }.Select(MotionClip).Where(c => c != null).ToArray();
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
