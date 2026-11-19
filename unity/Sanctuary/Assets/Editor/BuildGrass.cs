using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

/// 草地：一根根真的草叶。按 4 米一块生成网格，每块两档：近处是全部的草，远处只留五分之一
/// （着色器 YJGrass 里离远了会把排位靠后的草收起来、剩下的变宽，两档切换时看不出跳变）。
public static partial class SanctuaryBuild
{
    const float GrassChunk = 4f;
    const string GrassDir = "Assets/Toon/Grass";

    /// 样板角的花（fl_*：五百多丛，每丛花茎花心、花瓣叶子两个部件）一丛一个渲染器的话，看得见那一片时光花就要画一千多次
    /// （SSAO 的深度法线那一遍再画一千多次），手机上很费。以前按格子合成大网格，每丛的顶点都复制一份，资源 170 MB（包里八十多 MB）。
    /// 现在交给 FlowerField 按实例画：同一种花（同一个网格、同一种材质）只存一份网格（另存一份带两档简化的，不留 CPU 那份），
    /// 每丛只记摆放矩阵，按 cell 米见方的格子分好（运行时按格子挑看得见的、定简化档）。
    /// 材质就用原来那份（ToonMat 都开着 GPU instancing：打包时按材质留着色器的 instancing 版本；别的渲染器照旧走 SRP Batcher）。
    /// 不投太阳的影子：花只有一拃高，影子贴在草上只有几厘米。返回有几种（网格 × 材质）
    static int MergeFlowers(Transform greens, float cell = 4f)
    {
        var inst = new List<(Mesh mesh, Material mat, Matrix4x4 m, Vector2Int cell, Bounds b)>();
        var kill = new List<GameObject>();
        int layer = 0;
        foreach (Transform t in greens)
        {
            if (!t.name.StartsWith("fl_")) continue;
            kill.Add(t.gameObject);
            foreach (var mr in t.GetComponentsInChildren<MeshRenderer>())
            {
                if (!mr.TryGetComponent(out MeshFilter mf) || mf.sharedMesh == null || mr.sharedMaterial == null) continue;
                layer = mr.gameObject.layer;
                Vector3 p = t.position;
                inst.Add((mf.sharedMesh, mr.sharedMaterial, mr.transform.localToWorldMatrix, new Vector2Int(Mathf.FloorToInt(p.x / cell), Mathf.FloorToInt(p.z / cell)), mr.bounds));
            }
        }
        string path = $"{GrassDir}/flower_chunks.asset";
        AssetDatabase.DeleteAsset(path);
        string meshPath = $"{GrassDir}/flower_meshes.asset";
        AssetDatabase.DeleteAsset(meshPath);
        if (inst.Count == 0) return 0;
        // 每种（网格、材质）一组：网格另存一份，带两档简化（每档约减半），存好以后不留 CPU 那份
        var groups = new List<(Mesh src, Material mat)>();
        var lodMesh = new Dictionary<Mesh, Mesh>();
        var instMat = new Dictionary<Material, Material>();
        Mesh first = null;
        foreach (var x in inst)
        {
            if (!groups.Contains((x.mesh, x.mat))) groups.Add((x.mesh, x.mat));
            if (!lodMesh.ContainsKey(x.mesh))
            {
                var m = UnityEngine.Object.Instantiate(x.mesh);
                m.name = x.mesh.name + "_inst";
                MeshLodUtility.GenerateMeshLods(m, 2);
                m.UploadMeshData(true);
                if (first == null) { AssetDatabase.CreateAsset(m, meshPath); first = m; }
                else AssetDatabase.AddObjectToAsset(m, meshPath);
                lodMesh[x.mesh] = m;
            }
            if (!instMat.ContainsKey(x.mat))
            {
                if (!x.mat.enableInstancing) x.mat.enableInstancing = true;
                instMat[x.mat] = x.mat;
            }
        }
        // 按格子排好
        inst.Sort((a, b) => a.cell.x != b.cell.x ? a.cell.x.CompareTo(b.cell.x) : a.cell.y.CompareTo(b.cell.y));
        var holder = new GameObject("FlowerField");
        holder.transform.SetParent(greens, false);
        var field = holder.AddComponent<Yuanjing.FlowerField>();
        field.layer = layer;
        field.meshes = groups.ConvertAll(g => lodMesh[g.src]).ToArray();
        field.materials = groups.ConvertAll(g => instMat[g.mat]).ToArray();
        field.matrices = inst.ConvertAll(x => x.m).ToArray();
        field.groupOf = inst.ConvertAll(x => groups.IndexOf((x.mesh, x.mat))).ToArray();
        var starts = new List<int>();
        var counts = new List<int>();
        var bounds = new List<Bounds>();
        for (int i = 0; i < inst.Count;)
        {
            int j = i;
            var b = inst[i].b;
            while (j < inst.Count && inst[j].cell == inst[i].cell) { b.Encapsulate(inst[j].b); j++; }
            // 会摆动的叶子、花瓣：包围盒放大一圈（同 YjmImporter），贴着屏幕边不会整格被裁掉
            b.Expand(0.4f);
            starts.Add(i);
            counts.Add(j - i);
            bounds.Add(b);
            i = j;
        }
        field.cellStart = starts.ToArray();
        field.cellCount = counts.ToArray();
        field.cellBounds = bounds.ToArray();
        foreach (var g in kill) UnityEngine.Object.DestroyImmediate(g);
        AssetDatabase.SaveAssets();
        Debug.Log($"[yuanjing] 花：{inst.Count} 个实例，{groups.Count} 种（网格 × 材质），{bounds.Count} 格");
        return groups.Count;
    }

    /// 在 area 这块地里种草。open(x, z, 留边) 说这一点是不是空地；perSqm 是每平方米几根
    static int GrassField(Transform parent, IsletMap map, Func<float, float, float, bool> open, Rect area, int perSqm = 260)
    {
        Directory.CreateDirectory(GrassDir);
        string assetPath = $"{GrassDir}/grass_chunks.asset";
        AssetDatabase.DeleteAsset(assetPath);
        var mat = ToonMat("grass_blade", m => { m.enableInstancing = false; }, "Yuanjing/Grass");
        var holder = new GameObject("GrassField");
        holder.transform.SetParent(parent, false);
        var rng = new System.Random(77123);
        float R(float a, float b) => a + (b - a) * (float)rng.NextDouble();
        Mesh first = null;
        int total = 0;

        // 草的颜色：根深梢浅，和地面那张贴图的草色接得上；零星几根发黄
        Color rootC = new Color(0.25f, 0.47f, 0.20f), tipC = new Color(0.60f, 0.80f, 0.36f), dryC = new Color(0.78f, 0.76f, 0.40f);

        for (float cz = area.yMin; cz < area.yMax; cz += GrassChunk)
            for (float cx = area.xMin; cx < area.xMax; cx += GrassChunk)
            {
                var center = new Vector3(cx + GrassChunk / 2, 0, cz + GrassChunk / 2);
                center.y = map.H(center.x, center.z);
                var pos = new List<Vector3>(); var nrm = new List<Vector3>(); var col = new List<Color32>();
                var uv0 = new List<Vector2>(); var uv1 = new List<Vector3>();
                var near = new List<int>();
                // 远处那档只留五分之一的草：它的网格只存这五分之一的顶点（以前把全部顶点又存了一遍，白占一半的体积和显存）
                var fpos = new List<Vector3>(); var fnrm = new List<Vector3>(); var fcol = new List<Color32>();
                var fuv0 = new List<Vector2>(); var fuv1 = new List<Vector3>(); var far = new List<int>();
                int n = (int)(GrassChunk * GrassChunk * perSqm);
                int side = Mathf.CeilToInt(Mathf.Sqrt(n));
                float cell = GrassChunk / side;
                for (int iz = 0; iz < side; iz++)
                    for (int ix = 0; ix < side; ix++)
                    {
                        float x = cx + (ix + R(0, 1)) * cell, z = cz + (iz + R(0, 1)) * cell;
                        if (!open(x, z, 0.02f)) continue;
                        // 一片高一片矮：大块的噪声定高矮，再叠一层小的；路边、石头边的草矮（像被踩过、修过）
                        float patch = Mathf.PerlinNoise(x * 0.35f + 11f, z * 0.35f + 3f);
                        float clump = Mathf.PerlinNoise(x * 1.9f + 5f, z * 1.9f + 17f);
                        if (clump < 0.2f && R(0, 1) < 0.6f) continue;             // 留一点稀的地方，露出土
                        float h = Mathf.Lerp(0.09f, 0.2f, patch) * R(0.7f, 1.3f);
                        if (patch > 0.62f && clump > 0.55f) h *= R(1.3f, 2.0f);     // 几丛长得高的
                        if (!open(x, z, 0.3f)) h *= 0.6f;
                        float wdt = R(0.007f, 0.012f) * Mathf.Lerp(1f, 1.5f, h / 0.4f);
                        float face = R(0, Mathf.PI * 2);
                        float leanAng = R(0, Mathf.PI * 2);
                        float lean = R(0.1f, 0.55f);
                        var sideV = new Vector3(Mathf.Cos(face), 0, Mathf.Sin(face));
                        var leanV = new Vector3(Mathf.Cos(leanAng), 0, Mathf.Sin(leanAng));
                        var rootW = new Vector3(x, map.H(x, z) - 0.01f, z);
                        var root = rootW - center;
                        float rank = R(0, 1), phase = R(0, 1);
                        Color tip = Color.Lerp(tipC, dryC, R(0, 1) < 0.07f ? R(0.4f, 0.9f) : 0f);
                        float v = R(0.88f, 1.1f);
                        tip *= v;
                        Color rt = rootC * v * Mathf.Lerp(0.9f, 1.1f, patch);
                        var normal = (Vector3.up + leanV * 0.2f).normalized;
                        int b = pos.Count;
                        for (int k = 0; k <= 3; k++)
                        {
                            float t = k / 3f;
                            var p = root + Vector3.up * (h * t) + leanV * (lean * h * t * t);
                            float hw = wdt * (1f - 0.92f * Mathf.Pow(t, 1.6f));
                            Color32 c = Color.Lerp(rt, tip, Mathf.Pow(t, 0.8f));
                            c.a = (byte)Mathf.RoundToInt(t * 255);
                            int cnt = k == 3 ? 1 : 2;
                            for (int s = 0; s < cnt; s++)
                            {
                                pos.Add(cnt == 1 ? p : p + sideV * (s == 0 ? -hw : hw));
                                nrm.Add(normal); col.Add(c); uv0.Add(new Vector2(rank, phase)); uv1.Add(root);
                            }
                        }
                        var list = new List<int> { b, b + 2, b + 1, b + 1, b + 2, b + 3, b + 2, b + 4, b + 3, b + 3, b + 4, b + 5, b + 4, b + 6, b + 5 };
                        near.AddRange(list);
                        if (rank < 0.2f)
                        {
                            int fb = fpos.Count;
                            for (int q = b; q < pos.Count; q++) { fpos.Add(pos[q]); fnrm.Add(nrm[q]); fcol.Add(col[q]); fuv0.Add(uv0[q]); fuv1.Add(uv1[q]); }
                            foreach (int q in list) far.Add(q - b + fb);
                        }
                        total++;
                    }
                if (pos.Count == 0) continue;

                // 草会被风吹、会变宽：包围盒留出余量，不然贴着屏幕边会被整块裁掉。两档用同一个包围盒（按全部的草算）
                Bounds? shared = null;
                Mesh Make(string name, List<Vector3> p, List<Vector3> nn, List<Color32> cc, List<Vector2> u0, List<Vector3> u1, List<int> tris)
                {
                    var m = new Mesh { name = name, indexFormat = p.Count > 65000 ? IndexFormat.UInt32 : IndexFormat.UInt16 };
                    m.SetVertices(p); m.SetNormals(nn); m.SetColors(cc); m.SetUVs(0, u0); m.SetUVs(1, u1);
                    m.SetTriangles(tris, 0);
                    if (shared == null) { var bb = m.bounds; bb.Expand(new Vector3(0.6f, 0.4f, 0.6f)); shared = bb; }
                    m.bounds = shared.Value;
                    if (first == null) { AssetDatabase.CreateAsset(m, assetPath); first = m; }
                    else AssetDatabase.AddObjectToAsset(m, assetPath);
                    return m;
                }
                var go = new GameObject($"Grass_{cx:0}_{cz:0}");
                go.transform.SetParent(holder.transform, false);
                go.transform.position = center;
                var lods = new List<LOD>();
                foreach (var (name, tris, until) in new[] { ("near", near, 0.3f), ("far", far, 0.0f) })
                {
                    var c = new GameObject(name);
                    c.transform.SetParent(go.transform, false);
                    c.AddComponent<MeshFilter>().sharedMesh = name == "near"
                        ? Make($"{go.name}_{name}", pos, nrm, col, uv0, uv1, tris)
                        : Make($"{go.name}_{name}", fpos, fnrm, fcol, fuv0, fuv1, tris);
                    var mr = c.AddComponent<MeshRenderer>();
                    mr.sharedMaterial = mat;
                    mr.shadowCastingMode = ShadowCastingMode.Off;
                    mr.lightProbeUsage = LightProbeUsage.Off;
                    mr.reflectionProbeUsage = ReflectionProbeUsage.Off;
                    lods.Add(new LOD(until, new Renderer[] { mr }));
                }
                var lg = go.AddComponent<LODGroup>();
                lg.SetLODs(lods.ToArray());
                lg.RecalculateBounds();
            }
        AssetDatabase.SaveAssets();
        return total;
    }
}
