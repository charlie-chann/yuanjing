using UnityEngine;
using UnityEngine.Rendering;

namespace Yuanjing
{
    /// 带毛的小动物：毛是把身体的网格一层层往外复制出来的「壳」（近处 28 层、远处 6 层、投影子的 1 层）。
    /// 以前这三份网格在编辑器里算好存进包里：十只动物约 205 MB，而每一层的数据都和身体那份一模一样，只多一个「第几层」。
    /// 现在包里只存身体那一份，这三份在这里现算（同一个函数，算出来的顶点和以前存的逐个相同），画出来没有差别。
    /// 算完交给显卡以后不留内存里那份。编辑器里出图（不跑游戏）也要有毛，所以 ExecuteAlways。
    [ExecuteAlways, DefaultExecutionOrder(-200)]
    public class FurShells : MonoBehaviour
    {
        /// 身体的网格（FBX 里那份，要能读顶点）
        public Mesh source;
        public SkinnedMeshRenderer near, far, shadow;
        public int nearShells = 28, farShells = 6, shadowShells = 1;

        Mesh[] built;

        void OnEnable()
        {
            if (built != null || source == null) return;
            built = new[] { Give(near, nearShells, "_fur"), Give(far, farShells, "_fur_far"), Give(shadow, shadowShells, "_fur_shadow") };
        }

        Mesh Give(SkinnedMeshRenderer r, int shells, string suffix)
        {
            if (r == null) return null;
            var m = Build(source, shells);
            m.name = source.name + suffix;
            m.hideFlags = HideFlags.DontSave;
            // 渲染器自己的包围盒不用管：换网格时引擎会按新网格重算，和以前在编辑器里直接挂带毛网格时算出来的一样
            r.sharedMesh = m;
            if (Application.isPlaying) m.UploadMeshData(true);
            return m;
        }

        void OnDestroy()
        {
            if (built == null) return;
            foreach (var m in built)
            {
                if (m == null) continue;
                if (Application.isPlaying) Destroy(m); else DestroyImmediate(m);
            }
            built = null;
        }

        /// 给蒙皮网格套上 shells 层壳。壳和身体共用骨骼权重；uv1.x 记第几层，uv2 记没动时的位置
        public static Mesh Build(Mesh src, int shells)
        {
            var pos = src.vertices; var nrm = src.normals; var col = src.colors32; var bw = src.boneWeights;
            int n = pos.Length, layers = shells + 1;
            var tris = src.triangles;
            bool hasCol = col.Length == n;
            var grey = new Color32(200, 200, 200, 128);
            var P = new Vector3[n * layers]; var N = new Vector3[n * layers]; var C = new Color32[n * layers];
            var W = new BoneWeight[n * layers]; var S = new Vector2[n * layers]; var T = new int[tris.Length * layers];
            for (int s = 0; s < layers; s++)
            {
                float h = s / (float)shells;
                int o = s * n;
                for (int i = 0; i < n; i++)
                {
                    P[o + i] = pos[i]; N[o + i] = nrm[i]; C[o + i] = hasCol ? col[i] : grey; W[o + i] = bw[i];
                    S[o + i] = new Vector2(h, 0);
                }
                // 从里往外排：先画里层，外层靠深度挡在前面
                int to = s * tris.Length;
                for (int k = 0; k < tris.Length; k++) T[to + k] = tris[k] + o;
            }
            var m = new Mesh { name = src.name + "_fur", indexFormat = IndexFormat.UInt32 };
            m.SetVertices(P); m.SetNormals(N); m.SetColors(C); m.SetUVs(1, S); m.SetUVs(2, P);
            m.boneWeights = W;
            m.bindposes = src.bindposes;
            m.SetTriangles(T, 0);
            var b = src.bounds; b.Expand(b.size.magnitude * 0.15f); m.bounds = b;
            return m;
        }
    }
}
