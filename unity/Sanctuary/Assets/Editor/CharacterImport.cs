using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

/// 人物素材的导入规则：Quaternius 的角色和动作库都按标准人形骨骼导入，这样动作能套到任何一个角色上。
public class CharacterImport : AssetPostprocessor
{
    // 改了导入规则就把版本号加一，Unity 会自动重新导入
    public override uint GetVersion() => 18;

    void OnPreprocessModel()
    {
        // 动作（tools/mocap/convert.py 转的动捕、tools/blender/pray_motions.py 做的关键帧）：人形骨骼，用它自己的骨架建基准
        if (assetPath.StartsWith("Assets/Motion/"))
        {
            var mi = (ModelImporter)assetImporter;
            mi.animationType = ModelImporterAnimationType.Human;
            mi.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
            mi.importAnimation = true;
            mi.materialImportMode = ModelImporterMaterialImportMode.None;
            mi.resampleCurves = true;
            mi.animationCompression = ModelImporterAnimationCompression.Optimal;
            // 走路（tools/mocap/locomotion.py）：人形基准每次都重新认，不沿用 .meta 里存的旧基准。
            // 只有骨架的 FBX 没有绑定姿势，Unity 拿动画第一帧当基准：convert.py --ref0 让第一帧（第 0 帧）就是标准 T 字。
            // 以前第一帧是走路的一帧（右脚蹬地、脚尖朝下，头偏着），套到人物上右脚一直翘着脚尖、头歪
            if (Path.GetFileName(assetPath).StartsWith("Walk_"))
            {
                var hd = mi.humanDescription;
                hd.human = new HumanBone[0];
                hd.skeleton = new SkeletonBone[0];
                mi.humanDescription = hd;
                mi.autoGenerateAvatarMappingIfUnspecified = true;
            }
            return;
        }
        if (!assetPath.StartsWith("Assets/Characters/")) return;
        var imp = (ModelImporter)assetImporter;
        bool hair = assetPath.Contains("/Hair/");
        imp.animationType = hair ? ModelImporterAnimationType.Generic : ModelImporterAnimationType.Human;
        imp.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
        imp.importAnimation = assetPath.Contains("UAL1");
        imp.materialImportMode = ModelImporterMaterialImportMode.None;
        imp.importBlendShapes = true;
        imp.globalScale = 1f;
    }

    /// 走路片段（tools/mocap/locomotion.py）前后各多导的帧数（和那边的 PAD 一样）：片段从第 1 + WalkPad 帧起、到倒数第 WalkPad + 1 帧止。
    /// 多导的几帧让片段开头、结尾的曲线切线是对的（不然第一帧和第二帧之间往 T 字基准那边鼓，手臂每个循环跳一下）
    public const int WalkPad = 3;

    /// 各段走路片段的高度、朝向修正（人形单位，在 shino/dshibu/fumiriya 上量的：unity/run.sh MotionDiag.Level）。
    /// 高度：踩稳的那只脚踝和待机时一样高（停步片段不修正的话整个停步里脚陷进地里 2 厘米多）；
    /// 朝向：Unity 按身体朝向（髋和肩）定根的朝向，动捕里人走的方向和它差 3–4 度，走起来斜着（像螃蟹），这里转回来
    static readonly Dictionary<string, (float h, float yaw)> WalkFix = new Dictionary<string, (float, float)>
    {
        // h：Unity 的 heightOffset（人形单位，正的是往下沉，所以这里是负的）；yaw：rotationOffset（度，镜像那份取反）
        { "Walk_F_Slow", (-0.0149f, 3.18f) }, { "Walk_F", (-0.0091f, 3.17f) }, { "Walk_F_Fast", (-0.0078f, 4.40f) }, { "Walk_F_Brisk", (-0.0040f, 4.15f) },
        { "Walk_M_Slow", (-0.0133f, 3.13f) }, { "Walk_M", (-0.0097f, 2.96f) }, { "Walk_M_Fast", (-0.0093f, 3.55f) }, { "Walk_M_Brisk", (-0.0062f, 3.48f) },
        { "Walk_Stop_F", (-0.0309f, 0f) }, { "Walk_Stop", (-0.0290f, 0f) },
    };

    /// tools/mocap/locomotion.py 做的走路片段（老的 Walk_Slow 不是）
    static bool LocoClip(string f) => f.StartsWith("Walk_F") || f.StartsWith("Walk_M") || f.StartsWith("Walk_Stop") || f.StartsWith("Walk_TurnStart");

    void OnPreprocessAnimation()
    {
        if (assetPath.StartsWith("Assets/Motion/"))
        {
            var mi = (ModelImporter)assetImporter;
            var list = mi.defaultClipAnimations;
            string file = Path.GetFileNameWithoutExtension(assetPath);
            // 走路的过渡段（停步、转身起步）：不循环；转身起步的转身留作根运动（游戏按它转人），其余按身体朝向烤进姿势
            bool walkPart = file.StartsWith("Walk_Stop") || file.StartsWith("Walk_TurnStart");
            var outList = new List<ModelImporterClipAnimation>();
            foreach (var c in list)
            {
                c.name = file;
                // 第 0 帧是给人形基准用的 T 字姿势，不要；走路片段（locomotion.py）、关键帧动作（pray_motions.py）前后还各有 WalkPad 帧，只是给曲线切线用的
                bool padded = LocoClip(file) || (!file.StartsWith("Idle") && !file.StartsWith("Walk"));
                int pad = padded ? WalkPad : 0;
                if (c.firstFrame < 1 + pad) c.firstFrame = 1 + pad;
                c.lastFrame -= pad;
                if (WalkFix.TryGetValue(file, out var fix)) { c.heightOffset = fix.h; c.rotationOffset = fix.yaw; }
                bool loop = file.StartsWith("Idle") || (file.StartsWith("Walk") && !walkPart) || file.EndsWith("_Loop");
                c.loopTime = loop;
                c.loopPose = loop;                 // 首尾对齐，循环时不跳
                // 原地播：水平位移和转身交给游戏里的移动，动画只管姿势；高度按双脚对齐（脚踩在原点上）
                // 朝向一律按身体对齐：动捕里人可能是斜着、横着录的，不对齐的话走起来身子是歪的（像螃蟹走）
                c.lockRootRotation = true;
                c.keepOriginalOrientation = false;
                // 但自己做的关键帧动作（鞠躬、叩首）不能按身体朝向对齐：那样会把身子往前弯的角度一起抹掉，鞠躬变成站直
                // 关键帧做的（合掌、鞠躬、跪、坐）：位置按做的时候原样放（跪、坐时臀和膝的高度就是做好的，不能再按脚对齐）
                bool keyed = !file.StartsWith("Idle") && !file.StartsWith("Walk");
                bool low = file.StartsWith("Kneel") || file.StartsWith("Sit") || file.StartsWith("Kowtow");
                c.lockRootHeightY = true;
                c.keepOriginalPositionY = low;
                c.heightFromFeet = !low;
                c.lockRootPositionXZ = !file.StartsWith("Walk");
                c.keepOriginalPositionXZ = keyed;
                if (keyed) c.keepOriginalOrientation = false;
                if (file.StartsWith("Walk_TurnStart")) c.lockRootRotation = false;
                outList.Add(c);
                // 停步、转身起步再导一份左右镜像（另一只脚、另一个方向），名字加 _Mirror
                if (walkPart)
                    outList.Add(new ModelImporterClipAnimation
                    {
                        name = file + "_Mirror", takeName = c.takeName, firstFrame = c.firstFrame, lastFrame = c.lastFrame,
                        loopTime = c.loopTime, loopPose = c.loopPose, lockRootRotation = c.lockRootRotation, keepOriginalOrientation = c.keepOriginalOrientation,
                        lockRootHeightY = c.lockRootHeightY, keepOriginalPositionY = c.keepOriginalPositionY, heightFromFeet = c.heightFromFeet,
                        lockRootPositionXZ = c.lockRootPositionXZ, keepOriginalPositionXZ = c.keepOriginalPositionXZ, mirror = true,
                        wrapMode = c.wrapMode, cycleOffset = c.cycleOffset, heightOffset = c.heightOffset, rotationOffset = -c.rotationOffset
                    });
            }
            mi.clipAnimations = outList.ToArray();
            return;
        }
        if (!assetPath.Contains("UAL1")) return;
        var imp = (ModelImporter)assetImporter;
        var clips = imp.defaultClipAnimations;
        foreach (var c in clips)
        {
            string n = c.name.ToLowerInvariant();
            c.loopTime = n.Contains("idle") || n.Contains("walk") || n.Contains("run") || n.Contains("loop") || n.Contains("sit") || n.Contains("pray");
            c.lockRootRotation = true;
            c.lockRootHeightY = true;
            c.lockRootPositionXZ = true;
            // 按身体朝向对齐：动作库里有的动画原本是朝后的，不对齐的话人会倒着走
            c.keepOriginalOrientation = false;
            // 高度按双脚对齐：动画系统保证脚踩在角色的原点上（这套动作的根骨在髋部，按原始高度会让人陷到腰）
            c.keepOriginalPositionY = false;
            c.heightFromFeet = true;
            c.keepOriginalPositionXZ = true;
        }
        imp.clipAnimations = clips;
    }
}

public static class CharacterInfo
{
    public static void Hierarchy()
    {
        foreach (var path in new[] { "Assets/Characters/Superhero_Male_FullBody.fbx", "Assets/Characters/Hair/Hair_Buzzed.fbx" })
        {
            var go = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            void Walk(Transform t, int d) { if (d < 9) Debug.Log("[yuanjing] " + new string(' ', d * 2) + t.name + " " + t.localPosition.ToString("F3") + " " + t.localScale.ToString("F2")); foreach (Transform c in t) Walk(c, d + 1); }
            Walk(go.transform, 0);
            foreach (var smr in go.GetComponentsInChildren<SkinnedMeshRenderer>()) Debug.Log($"[yuanjing] 蒙皮 {smr.name} 根骨 {smr.rootBone?.name} 骨头 {smr.bones.Length} 顶点 {smr.sharedMesh.vertexCount} 子网格 {smr.sharedMesh.subMeshCount}");
            foreach (var mf in go.GetComponentsInChildren<MeshFilter>()) Debug.Log($"[yuanjing] 网格 {mf.name} 顶点 {mf.sharedMesh.vertexCount}");
        }
        var anim = AssetDatabase.LoadAllAssetsAtPath("Assets/Characters/Superhero_Male_FullBody.fbx").OfType<Avatar>().First();
        var hd = anim.humanDescription;
        foreach (var hb in hd.human) Debug.Log($"[yuanjing] 人形 {hb.humanName} = {hb.boneName}");
    }

    public static void PlantSizes()
    {
        foreach (var dir in System.IO.Directory.GetDirectories("Assets/Plants"))
            foreach (var f in System.IO.Directory.GetFiles(dir, "*.obj").Take(3))
            {
                var m = AssetDatabase.LoadAllAssetsAtPath(f).OfType<Mesh>().FirstOrDefault();
                Debug.Log($"[yuanjing] {f} {(m == null ? "无网格" : m.bounds.size.ToString("F2") + " 顶点 " + m.vertexCount)}");
            }
    }

    public static void ClipFlags()
    {
        foreach (var path in System.IO.Directory.GetFiles("Assets/Characters/Built", "*.anim"))
        {
            var c = AssetDatabase.LoadAssetAtPath<AnimationClip>(path);
            Debug.Log($"[yuanjing] {path} 标记={c.hideFlags} 人形={c.humanMotion} 长度={c.length}");
        }
        foreach (var c in AssetDatabase.LoadAllAssetsAtPath("Assets/Characters/UAL1_Standard.fbx").OfType<AnimationClip>().Take(3))
            Debug.Log($"[yuanjing] 原片段 {c.name} 标记={c.hideFlags}");
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Characters/Built/Folk_me.prefab");
        var so = new SerializedObject(prefab.GetComponent("Folk"));
        Debug.Log($"[yuanjing] 预制体 idleClip={so.FindProperty("idleClip").objectReferenceValue}");
    }

    public static void Muscles()
    {
        for (int i = 0; i < HumanTrait.MuscleCount; i++)
            Debug.Log($"[yuanjing] {i:00} {HumanTrait.MuscleName[i]} 默认范围 {HumanTrait.GetMuscleDefaultMin(i)}..{HumanTrait.GetMuscleDefaultMax(i)}");
    }

    public static void MeshAxes()
    {
        var go = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Characters/Superhero_Male_FullBody.fbx");
        var smr = go.GetComponentsInChildren<SkinnedMeshRenderer>().First(r => r.name.Contains("Hero"));
        var m = smr.sharedMesh;
        Debug.Log($"[yuanjing] 网格包围盒 {m.bounds.center:F3} {m.bounds.size:F3}");
        Debug.Log($"[yuanjing] 网格物体旋转 {smr.transform.localEulerAngles} 缩放 {smr.transform.localScale} 骨架旋转 {go.transform.Find("Armature").localEulerAngles} 缩放 {go.transform.Find("Armature").localScale}");
        string[] names = { "pelvis", "neck_01", "Head", "foot_l", "hand_l", "upperarm_l", "thigh_l" };
        foreach (var nm in names)
        {
            int i = System.Array.FindIndex(smr.bones, b => b.name == nm);
            Debug.Log($"[yuanjing] {nm} 在网格里 {m.bindposes[i].inverse.MultiplyPoint3x4(Vector3.zero):F3} 世界 {smr.bones[i].position:F3}");
        }
    }

    /// 打印动作库里所有动作的名字和长度
    public static void ListClips()
    {
        AssetDatabase.Refresh();
        foreach (var path in Directory.GetFiles("Assets/Characters", "*.fbx", SearchOption.AllDirectories))
        {
            var objs = AssetDatabase.LoadAllAssetsAtPath(path);
            var clips = objs.OfType<AnimationClip>().Where(c => !c.name.StartsWith("__preview")).ToList();
            var avatar = objs.OfType<Avatar>().FirstOrDefault();
            Debug.Log($"[yuanjing] {path}：人形 {(avatar != null && avatar.isHuman && avatar.isValid)}，动作 {clips.Count} 个");
            foreach (var c in clips) Debug.Log($"[yuanjing]   {c.name} {c.length:F2}s");
            var go = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            foreach (var r in go.GetComponentsInChildren<Renderer>()) Debug.Log($"[yuanjing]   网格 {r.name} 材质槽 {r.sharedMaterials.Length} 包围盒 {r.bounds.size}");
        }
    }
}
