using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.AssetImporters;
using UnityEngine;
using UnityEngine.Rendering;

/// 导入 Blender 脚本导出的模型（.yjm，格式见 tools/blender/kit.py 的 export）。
/// 一个文件是一个模型，里面按材质分成几个部件：toon 普通、leaf 双面叶片、glow 夜里会亮的。
/// 颜色在顶点色里，不用贴图。坐标在导出时已经换成 Unity 的。
[ScriptedImporter(6, "yjm")]
public class YjmImporter : ScriptedImporter
{
    [System.Serializable]
    class Part { public string name; public string mat; public int verts; public int tris; }
    [System.Serializable]
    class Header { public string name; public List<Part> parts; }

    public const string MatDir = "Assets/Toon/Materials";

    /// 哪些模型的部件存简化档（Mesh LOD），超过多少个三角形才存
    public static readonly string[] MeshLodModels =
    {
        "buddha_", "mandorla_", "altar_dais", "altar_table", "censer_hall", "palace_lantern", "muyu", "flower_vase", "donation_box",
        "sutra_desk", "fruit_plate", "qing", "candlestick", "burner", "water_vat", "lantern", "guanyin", "stone_bench", "temple_bell",
    };

    static int MeshLodMinTris(string model, string part)
    {
        if (model.StartsWith("buddha_") || model.StartsWith("mandorla_") || model == "guanyin") return 20000;
        if (model == "hall") return part.StartsWith("in_") ? int.MaxValue : 4000;
        foreach (var m in MeshLodModels) if (model.StartsWith(m)) return 2000;
        return int.MaxValue;
    }

    public override void OnImportAsset(AssetImportContext ctx)
    {
        byte[] data = File.ReadAllBytes(ctx.assetPath);
        using var r = new BinaryReader(new MemoryStream(data));
        if (Encoding.ASCII.GetString(r.ReadBytes(4)) != "YJM1") { ctx.LogImportError("不是 yjm 文件"); return; }
        int hl = r.ReadInt32();
        var header = JsonUtility.FromJson<Header>(Encoding.UTF8.GetString(r.ReadBytes(hl)));
        var root = new GameObject(header.name);
        foreach (var p in header.parts)
        {
            var pos = new Vector3[p.verts];
            var nrm = new Vector3[p.verts];
            var col = new Color32[p.verts];
            var uv = new Vector2[p.verts];
            for (int i = 0; i < p.verts; i++) pos[i] = new Vector3(r.ReadSingle(), r.ReadSingle(), r.ReadSingle());
            for (int i = 0; i < p.verts; i++) nrm[i] = new Vector3(r.ReadSingle(), r.ReadSingle(), r.ReadSingle());
            for (int i = 0; i < p.verts; i++) col[i] = new Color32(r.ReadByte(), r.ReadByte(), r.ReadByte(), r.ReadByte());
            for (int i = 0; i < p.verts; i++) uv[i] = new Vector2(r.ReadSingle(), r.ReadSingle());
            var idx = new int[p.tris * 3];
            for (int i = 0; i < idx.Length; i++) idx[i] = (int)r.ReadUInt32();
            var mesh = new Mesh { name = header.name + "_" + p.name };
            if (p.verts > 65000) mesh.indexFormat = IndexFormat.UInt32;
            mesh.vertices = pos;
            mesh.normals = nrm;
            mesh.colors32 = col;
            mesh.uv = uv;
            mesh.triangles = idx;
            mesh.RecalculateBounds();
            // 三尊佛像和背光一件就是几万到十几万个三角形，从殿门口、院子里看过去用不着那么细：
            // 在模型里多存几档简化的（Mesh LOD，每档大约减半）。引擎自己按屏幕大小挑档在这里不起作用（实测远近都是第 0 档），
            // 所以由摆模型的地方（BuildHall.MeshLodGroup）用 LODGroup 按远近切、每档的渲染器指定画第几档（forceMeshLod）。
            // 殿里、院子里几样重的陈设也一样；大殿外面那几件（屋顶瓦、斗拱梁柱、台基）只拿简化的那档投影子（BuildHall.HallShadowProxy）
            if (p.tris > MeshLodMinTris(header.name, p.name)) MeshLodUtility.GenerateMeshLods(mesh);
            // 会摆动的东西，包围盒放大一圈，免得摆出去的部分被当成看不见而不画
            if (p.mat == "leaf") { var b = mesh.bounds; b.Expand(0.5f); mesh.bounds = b; }
            ctx.AddObjectToAsset(mesh.name, mesh);
            var go = new GameObject(p.name);
            go.transform.SetParent(root.transform, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>();
            // 鱼、礼物（钓上来拎在手里、小动物叼着的）：发光的部件（月光鱼、珍珠）白天也亮（toon_shine），鳍、叶子不积雪（toon_leaf_dry）
            string matName = p.mat;
            if (header.name.StartsWith("fish_") || header.name.StartsWith("gift_"))
                matName = p.mat == "glow" ? "shine" : p.mat == "leaf" ? "leaf_dry" : p.mat;
            string matPath = $"{MatDir}/toon_{matName}.mat";
            ctx.DependsOnArtifact(matPath);
            mr.sharedMaterial = AssetDatabase.LoadAssetAtPath<Material>(matPath);
            // 贴地的小东西（草、花）不投影子：影子又碎又费
            if (p.mat == "leaf" && header.name.StartsWith("grass")) mr.shadowCastingMode = ShadowCastingMode.Off;
        }
        ctx.AddObjectToAsset("root", root);
        ctx.SetMainObject(root);
    }
}
