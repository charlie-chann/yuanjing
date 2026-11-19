using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using Yuanjing;

/// 带骨骼动作的动物（tools/blender/animal_import.py 加工过的 FBX，放在 Assets/Critters/名字/）：
/// 导入规则，以及给它套上一层层绒毛的壳、拼成预制体。
public class CritterImport : AssetPostprocessor
{
    public override uint GetVersion() => 2;

    void OnPreprocessModel()
    {
        if (!assetPath.StartsWith("Assets/Critters/")) return;
        var imp = (ModelImporter)assetImporter;
        // 老式的动画组件：按名字直接播、能淡入淡出，小动物用它最省事
        imp.animationType = ModelImporterAnimationType.Legacy;
        imp.importAnimation = true;
        imp.materialImportMode = ModelImporterMaterialImportMode.None;
        imp.importBlendShapes = false;
        imp.isReadable = true;          // 生成带毛的网格时要读顶点
    }

    void OnPreprocessAnimation()
    {
        if (!assetPath.StartsWith("Assets/Critters/")) return;
        var imp = (ModelImporter)assetImporter;
        var clips = imp.defaultClipAnimations;
        foreach (var c in clips)
        {
            // 名字去掉骨架的前缀（AnimalArmature|Walk → Walk）
            int bar = c.name.LastIndexOf('|');
            if (bar >= 0) c.name = c.name.Substring(bar + 1);
            string n = c.name.ToLowerInvariant();
            bool loop = n.StartsWith("idle") && !n.Contains("hit") || n == "walk" || n == "gallop" || n == "eating";
            c.loopTime = loop;
            c.wrapMode = loop ? WrapMode.Loop : WrapMode.ClampForever;
        }
        imp.clipAnimations = clips;
    }
}

public static partial class SanctuaryBuild
{
    const string CritterDir = "Assets/Critters";

    /// 给蒙皮网格套上 shells 层壳：算法在 FurShells.Build（运行时现算，包里不存）。这里只在生成预制体时临时算一份，用来定大小和包围盒
    static Mesh FurMesh(Mesh src, int shells) => FurShells.Build(src, shells);

    /// 把一只带骨骼动作的动物拼成预制体（Assets/Critters/名字/Pet_名字.prefab）：套毛、挂动画。height 是站着的肩高（米）
    /// 毛的样子：curl 卷毛、comb 顺毛、density 每米多少根
    static GameObject FurPetPrefab(string who, float height, float furLength = 0.03f, int shells = 28, float curl = 0f, float comb = 0.6f, float density = 420f)
    {
        string fbx = $"{CritterDir}/{who}/{who}.fbx";
        var asset = AssetDatabase.LoadAssetAtPath<GameObject>(fbx);
        if (asset == null) return null;
        var root = new GameObject("Pet_" + who);
        var model = (GameObject)PrefabUtility.InstantiatePrefab(asset);
        PrefabUtility.UnpackPrefabInstance(model, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
        model.name = "Model";
        model.transform.SetParent(root.transform, false);
        var smr = model.GetComponentInChildren<SkinnedMeshRenderer>();
        var mat = ToonMat("fur_" + who, m =>
        {
            m.enableInstancing = false;
            m.SetFloat("_FurLength", furLength);
            m.SetFloat("_Ambient", 0.5f);
            m.SetFloat("_SunScale", 0.2f);
        }, "Yuanjing/Fur");
        // 带毛的网格不再存成资源（十只约 205 MB，每层都是身体那份的复制品）：预制体里只记身体的网格和层数，FurShells 在运行时现算
        AssetDatabase.DeleteAsset($"{CritterDir}/{who}/{who}_fur.asset");
        var src = smr.sharedMesh;
        var fur = FurMesh(src, shells);
        // 远处用的省力版：6 层（俯视的时候一只狗在屏幕上就指甲盖大，20 层看不出区别）
        const int farShells = 6;
        var furFar = FurMesh(src, farShells);
        furFar.name = src.name + "_fur_far";
        // 按模型本来的大小缩放到想要的个头（原模型的单位不一定是米）
        smr.sharedMesh = fur;
        smr.sharedMaterial = mat;
        smr.updateWhenOffscreen = true;
        smr.shadowCastingMode = ShadowCastingMode.On;
        smr.quality = SkinQuality.Bone4;
        var bounds = new Bounds(smr.bounds.center, smr.bounds.size);
        float scale = height / Mathf.Max(0.01f, bounds.max.y - root.transform.position.y);
        model.transform.localScale *= scale;
        // 毛的疏密是按模型自己的单位算的（花纹跟着没动时的顶点位置走）：模型一个单位合多少米，按个头折算
        float metersPerUnit = height / Mathf.Max(1e-5f, fur.bounds.size.y / 1.15f);
        mat.SetFloat("_FurLength", furLength);
        mat.SetFloat("_Density", density * metersPerUnit);
        mat.SetFloat("_Curl", curl);
        mat.SetFloat("_Comb", comb);
        // 远处那份：再挂一个同样的蒙皮渲染器，按屏幕上的大小切换
        var farGo = Object.Instantiate(smr.gameObject, smr.transform.parent);
        farGo.name = smr.name + "_far";
        var smrFar = farGo.GetComponent<SkinnedMeshRenderer>();
        smrFar.sharedMesh = furFar;
        smrFar.bones = smr.bones;
        smrFar.rootBone = smr.rootBone;
        // 影子：毛的每一层都投影子的话，太阳那一遍每层级联都要把二十几层壳（三十万个三角形）再画一遍，影子上却只看得出外轮廓。
        // 另挂一个只投影子的：身体一层加毛尖一层（两层，约两万个三角形），轮廓和毛的长度一样；毛本身不再投影子
        var shadowMesh = FurMesh(src, 1);
        shadowMesh.name = src.name + "_fur_shadow";
        var shadowGo = Object.Instantiate(smr.gameObject, smr.transform.parent);
        shadowGo.name = smr.name + "_shadow";
        var smrShadow = shadowGo.GetComponent<SkinnedMeshRenderer>();
        smrShadow.sharedMesh = shadowMesh;
        smrShadow.bones = smr.bones;
        smrShadow.rootBone = smr.rootBone;
        smrShadow.shadowCastingMode = ShadowCastingMode.ShadowsOnly;
        smr.shadowCastingMode = ShadowCastingMode.Off;
        smrFar.shadowCastingMode = ShadowCastingMode.Off;
        var lod = root.AddComponent<LODGroup>();
        lod.SetLODs(new[] { new LOD(0.09f, new Renderer[] { smr, smrShadow }), new LOD(0.0f, new Renderer[] { smrFar, smrShadow }) });
        lod.RecalculateBounds();
        EditorUtility.SetDirty(mat);     // 不标记的话这两个数不会存进材质文件，下次打开又是默认值
        Debug.Log($"[yuanjing] {who}：模型一个单位约 {metersPerUnit:F4} 米，网格高 {src.bounds.size.y:F2}，轴向 {src.bounds.size}");

        var anim = model.GetComponent<Animation>() ?? model.AddComponent<Animation>();
        anim.playAutomatically = false;
        anim.cullingType = AnimationCullingType.AlwaysAnimate;
        var clips = AssetDatabase.LoadAllAssetsAtPath(fbx).OfType<AnimationClip>().Where(c => !c.name.StartsWith("__preview")).ToArray();
        foreach (var c in clips) if (anim.GetClip(c.name) == null) anim.AddClip(c, c.name);
        Directory.CreateDirectory($"{CritterDir}/{who}");
        // 大小、包围盒、远近切换都按带毛的网格定好了：存预制体时换回身体的网格，毛交给 FurShells 现算
        int furTris = fur.triangles.Length / 3;
        // （刚挂上时 source 还是空的，它不会在这里现算；摆进场景、启用的时候才算）
        var shellsComp = root.AddComponent<FurShells>();
        shellsComp.source = src;
        shellsComp.near = smr; shellsComp.far = smrFar; shellsComp.shadow = smrShadow;
        shellsComp.nearShells = shells; shellsComp.farShells = farShells; shellsComp.shadowShells = 1;
        foreach (var r in new[] { smr, smrFar, smrShadow }) r.sharedMesh = src;
        var prefab = PrefabUtility.SaveAsPrefabAsset(root, $"{CritterDir}/{who}/Pet_{who}.prefab");
        Object.DestroyImmediate(root);
        Object.DestroyImmediate(fur); Object.DestroyImmediate(furFar); Object.DestroyImmediate(shadowMesh);
        Debug.Log($"[yuanjing] 带毛的动物 {who}：{furTris} 个三角形（{shells} 层毛），动作 {string.Join(" ", clips.Select(c => c.name))}，缩放 {scale:F3}");
        return prefab;
    }
}
