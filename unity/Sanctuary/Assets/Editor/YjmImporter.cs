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
[ScriptedImporter(3, "yjm")]
public class YjmImporter : ScriptedImporter
{
    [System.Serializable]
    class Part { public string name; public string mat; public int verts; public int tris; }
    [System.Serializable]
    class Header { public string name; public List<Part> parts; }

    public const string MatDir = "Assets/Toon/Materials";

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
            // 会摆动的东西，包围盒放大一圈，免得摆出去的部分被当成看不见而不画
            if (p.mat == "leaf") { var b = mesh.bounds; b.Expand(0.5f); mesh.bounds = b; }
            ctx.AddObjectToAsset(mesh.name, mesh);
            var go = new GameObject(p.name);
            go.transform.SetParent(root.transform, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>();
            string matPath = $"{MatDir}/toon_{p.mat}.mat";
            ctx.DependsOnArtifact(matPath);
            mr.sharedMaterial = AssetDatabase.LoadAssetAtPath<Material>(matPath);
            // 贴地的小东西（草、花）不投影子：影子又碎又费
            if (p.mat == "leaf" && header.name.StartsWith("grass")) mr.shadowCastingMode = ShadowCastingMode.Off;
        }
        ctx.AddObjectToAsset("root", root);
        ctx.SetMainObject(root);
    }
}
