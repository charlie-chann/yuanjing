using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace Yuanjing
{
    /// 样板角、草地上的五百多丛花（fl_*）：同一种花只存一份网格，按实例一次画一批（GPU instancing）。
    /// 以前是每丛一个渲染器（一千多次绘制），后来按 4 米一格合成大网格——合成以后每丛的顶点都复制了一份，
    /// 一百四十多万个顶点、存成 170 MB 的资源（手机包里八十多 MB、运行时一百六十 MB 内存）。现在：
    /// - 十来种花各一份网格（带两档简化，见 BuildGrass.MergeFlowers），每丛只记一个摆放矩阵；
    /// - 每台镜头开画前（beginCameraRendering）按 4 米一格挑看得见的格子（视锥；镜头在殿里时再按门洞挑，见 InteriorCull），
    ///   按格子离镜头多远定画哪一档（屏幕上的高度比例，同 LODGroup：不到 near 换第 1 档，不到 far 换第 2 档），
    ///   每种花每一档一次 RenderMeshInstanced；
    /// - 不投影子（花只有一拃高），接影子。编辑器里出图（不跑游戏）也画。
    [ExecuteAlways]
    public class FlowerField : MonoBehaviour
    {
        /// 每一种（网格、材质）一组
        public Mesh[] meshes = new Mesh[0];
        public Material[] materials = new Material[0];
        /// 每丛每个部件一个实例：摆放矩阵、属于哪一组；按格子排好（cellStart、cellCount 指到这两个数组里）
        public Matrix4x4[] matrices = new Matrix4x4[0];
        public int[] groupOf = new int[0];
        public Bounds[] cellBounds = new Bounds[0];
        public int[] cellStart = new int[0], cellCount = new int[0];
        public float near = 0.25f, far = 0.12f;
        public int layer;

        List<Matrix4x4>[] batches;
        readonly Plane[] planes = new Plane[6];
        Bounds all;

        void OnEnable()
        {
            RenderPipelineManager.beginCameraRendering += Draw;
            all = new Bounds();
            for (int c = 0; c < cellBounds.Length; c++)
                if (c == 0) all = cellBounds[0]; else all.Encapsulate(cellBounds[c]);
        }

        void OnDisable() => RenderPipelineManager.beginCameraRendering -= Draw;

        /// 实例数（测试、量开销用）
        public int Count => matrices.Length;
        /// 上一次画了几丛（各部件分开算）
        public int LastDrawn { get; private set; }

        void Draw(ScriptableRenderContext ctx, Camera cam)
        {
            if (cam == null || meshes.Length == 0 || matrices.Length == 0) return;
            if (cam.cameraType == CameraType.Preview || cam.cameraType == CameraType.Reflection) return;
            if ((cam.cullingMask & (1 << layer)) == 0) return;
            int g = meshes.Length;
            if (batches == null || batches.Length != g * 3)
            {
                batches = new List<Matrix4x4>[g * 3];
                for (int i = 0; i < batches.Length; i++) batches[i] = new List<Matrix4x4>(256);
            }
            foreach (var b in batches) b.Clear();
            GeometryUtility.CalculateFrustumPlanes(cam, planes);
            var ic = Application.isPlaying ? InteriorCull.Active : null;
            Vector3 eye = cam.transform.position;
            float k = 1f / (2f * Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad)) * QualitySettings.lodBias;
            int drawn = 0;
            for (int c = 0; c < cellBounds.Length; c++)
            {
                var cb = cellBounds[c];
                if (!GeometryUtility.TestPlanesAABB(planes, cb)) continue;
                if (ic != null && !ic.OutsideVisible(cb)) continue;
                // 屏幕上的高度比例（同 LODGroup：包围盒最大边 / 到镜头的距离 / 视锥高）
                float d = Mathf.Max(0.01f, Vector3.Distance(eye, cb.center));
                float h = Mathf.Max(cb.size.x, Mathf.Max(cb.size.y, cb.size.z)) / d * k;
                int lod = h >= near ? 0 : h >= far ? 1 : 2;
                for (int i = cellStart[c], end = cellStart[c] + cellCount[c]; i < end; i++)
                    batches[groupOf[i] * 3 + lod].Add(matrices[i]);
                drawn += cellCount[c];
            }
            LastDrawn = drawn;
            for (int i = 0; i < batches.Length; i++)
            {
                var list = batches[i];
                if (list.Count == 0) continue;
                int gi = i / 3, lod = i % 3;
                var mesh = meshes[gi];
                var mat = materials[gi];
                if (mesh == null || mat == null) continue;
                var rp = new RenderParams(mat)
                {
                    camera = cam,
                    layer = layer,
                    shadowCastingMode = ShadowCastingMode.Off,
                    receiveShadows = true,
                    worldBounds = all,
                    lightProbeUsage = LightProbeUsage.Off,
                    reflectionProbeUsage = ReflectionProbeUsage.Off,
                    forceMeshLod = (short)Mathf.Min(lod, Mathf.Max(0, mesh.lodCount - 1)),
                };
                for (int s = 0; s < mesh.subMeshCount; s++) Graphics.RenderMeshInstanced(rp, mesh, s, list);
            }
        }
    }
}
