using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using Yuanjing;

/// 成品的花草（Poly Haven，CC0）：草丛、灌木、蕨、野花。按区域随机摆，再按种类合并成一个网格（手机上一种只画一次）。
public static partial class SanctuaryBuild
{
    class PlantKind
    {
        public string folder;
        public Mesh[] variants;
        public Material mat;
    }

    static readonly Dictionary<string, PlantKind> plantKinds = new Dictionary<string, PlantKind>();

    static PlantKind Plant(string folder, Color tint)
    {
        if (plantKinds.TryGetValue(folder, out var k) && k.mat != null) return k;
        string dir = $"Assets/Plants/{folder}";
        // 面数太多的变体不要（手机上成片摆会很重）
        var meshes = Directory.GetFiles(dir, "*.obj").OrderBy(f => f)
            .Select(f => AssetDatabase.LoadAllAssetsAtPath(f).OfType<Mesh>().FirstOrDefault()).Where(m => m != null && m.vertexCount <= 2400).ToArray();
        var tex = AssetDatabase.LoadAssetAtPath<Texture2D>($"{dir}/{folder}_color.png");
        var imp = (TextureImporter)AssetImporter.GetAtPath($"{dir}/{folder}_color.png");
        if (imp != null && (!imp.alphaIsTransparency || imp.maxTextureSize != 1024))
        {
            imp.alphaIsTransparency = true;
            imp.maxTextureSize = 1024;
            imp.mipMapsPreserveCoverage = true;
            imp.alphaTestReferenceValue = 0.45f;
            imp.SaveAndReimport();
        }
        var m = Mat($"plant_{folder}", null, 1f, tint, rough: 0.8f, wet: 0.2f, snow: 0.7f);
        m.SetTexture("_BaseMap", tex);
        m.SetTextureScale("_BaseMap", Vector2.one);
        m.SetFloat("_AlphaClip", 1f);
        m.SetFloat("_Cutoff", 0.45f);
        m.SetFloat("_Cull", 0f);
        m.SetFloat("_Sway", 0.6f);
        m.EnableKeyword("_ALPHATEST_ON");
        m.renderQueue = (int)RenderQueue.AlphaTest;
        k = new PlantKind { folder = folder, variants = meshes, mat = m };
        plantKinds[folder] = k;
        return k;
    }

    /// 一片区域里撒一种植物。area 是中心和半径（圆）或者矩形（size.y 不为 0）；count 棵；scale 大小范围
    class PlantPatch
    {
        public PlantKind kind;
        public Vector3 center;
        public Vector2 size;         // 矩形的长宽；y 为 0 时 x 是圆的半径
        public float ring;           // 圆环：只在半径 ring..x 之间摆（围着树池边）
        public int count;
        public Vector2 scale = new Vector2(0.8f, 1.2f);
    }

    static void BuildPlantPatches(Transform parent, IEnumerable<PlantPatch> patches, int seed)
    {
        var rng = new Rng(seed);
        var byKind = new Dictionary<PlantKind, List<CombineInstance>>();
        foreach (var p in patches)
        {
            if (p.kind.variants.Length == 0) continue;
            if (!byKind.TryGetValue(p.kind, out var list)) byKind[p.kind] = list = new List<CombineInstance>();
            for (int i = 0; i < p.count; i++)
            {
                Vector3 pos;
                if (p.size.y > 0) pos = p.center + new Vector3(rng.Range(-0.5f, 0.5f) * p.size.x, 0, rng.Range(-0.5f, 0.5f) * p.size.y);
                else
                {
                    float a = rng.Range(0, Mathf.PI * 2), r = Mathf.Sqrt(rng.Range(p.ring * p.ring / (p.size.x * p.size.x), 1f)) * p.size.x;
                    pos = p.center + new Vector3(Mathf.Cos(a) * r, 0, Mathf.Sin(a) * r);
                }
                var mesh = p.kind.variants[rng.Int(p.kind.variants.Length)];
                float s = rng.Range(p.scale.x, p.scale.y);
                list.Add(new CombineInstance { mesh = mesh, transform = Matrix4x4.TRS(pos, Quaternion.Euler(0, rng.Range(0, 360f), 0), Vector3.one * s) });
            }
        }
        var root = Group("Plants", parent);
        foreach (var kv in byKind)
        {
            var mesh = new Mesh { name = "plants_" + kv.Key.folder, indexFormat = IndexFormat.UInt32 };
            mesh.CombineMeshes(kv.Value.ToArray(), true, true);
            // 顶点色红通道：越高摆得越厉害（着色器按它随风摆）
            var v = mesh.vertices;
            var cols = new Color[v.Length];
            float top = mesh.bounds.max.y;
            for (int i = 0; i < v.Length; i++) cols[i] = new Color(Mathf.Clamp01(v[i].y / 0.8f) * 0.6f, 0, 0, 1);
            mesh.colors = cols;
            mesh.RecalculateBounds();
            string path = $"{MatDir}/../Plants/{mesh.name}_{parent.gameObject.scene.name}.asset";
            AssetDatabase.DeleteAsset(path);
            AssetDatabase.CreateAsset(mesh, path);
            var go = new GameObject(mesh.name);
            go.transform.SetParent(root, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var r = go.AddComponent<MeshRenderer>();
            r.sharedMaterial = kv.Key.mat;
            r.shadowCastingMode = ShadowCastingMode.Off;
            go.isStatic = true;
        }
    }
}
