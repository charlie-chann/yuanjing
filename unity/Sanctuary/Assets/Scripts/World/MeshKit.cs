using System;
using System.Collections.Generic;
using UnityEngine;

namespace Yuanjing
{
    /// 用代码拼网格的工具。贴图坐标一律以「米」为单位（材质上再设每米重复几次），
    /// 这样不同大小的构件贴同一种材质时，纹理的疏密是一致的。
    public class MeshBuilder
    {
        public readonly List<Vector3> verts = new List<Vector3>();
        public readonly List<Vector3> norms = new List<Vector3>();
        public readonly List<Vector2> uvs = new List<Vector2>();
        public readonly List<Color> cols = new List<Color>();
        public readonly List<int> tris = new List<int>();

        /// 之后加进来的几何体都先乘这个矩阵
        public Matrix4x4 m = Matrix4x4.identity;

        /// 顶点色：红色通道给着色器当「随风摆动的幅度」用
        public Color color = Color.black;

        public int Count => verts.Count;

        int V(Vector3 worldP, Vector3 worldN, Vector2 uv)
        {
            verts.Add(worldP);
            norms.Add(worldN);
            uvs.Add(uv);
            cols.Add(color);
            return verts.Count - 1;
        }

        Vector3 P(Vector3 p) => m.MultiplyPoint3x4(p);
        Vector3 N(Vector3 n) => m.MultiplyVector(n).normalized;

        /// 按面的朝向选两个轴当贴图坐标（盒式映射），相邻构件的纹理能接上
        public static Vector2 BoxUV(Vector3 p, Vector3 n)
        {
            float ax = Mathf.Abs(n.x), ay = Mathf.Abs(n.y), az = Mathf.Abs(n.z);
            if (ay >= ax && ay >= az) return new Vector2(p.x, p.z);
            if (ax >= az) return new Vector2(p.z, p.y);
            return new Vector2(p.x, p.y);
        }

        /// 一个四边形，四个点按顺序绕一圈；facing 是它该朝的方向（用来决定正反面）
        public void Quad(Vector3 a, Vector3 b, Vector3 c, Vector3 d, Vector3 facing)
        {
            a = P(a); b = P(b); c = P(c); d = P(d);
            Vector3 n = Vector3.Cross(b - a, d - a).normalized;
            Vector3 f = m.MultiplyVector(facing);
            if (Vector3.Dot(n, f) < 0)
            {
                (b, d) = (d, b);
                n = -n;
            }
            int i = V(a, n, BoxUV(a, n));
            V(b, n, BoxUV(b, n));
            V(c, n, BoxUV(c, n));
            V(d, n, BoxUV(d, n));
            tris.Add(i); tris.Add(i + 1); tris.Add(i + 2);
            tris.Add(i); tris.Add(i + 2); tris.Add(i + 3);
        }

        /// 带自定义贴图坐标的四边形（做牌匾、窗格这类贴一整张图的面）
        public void QuadUV(Vector3 a, Vector3 b, Vector3 c, Vector3 d, Vector3 facing, Rect uv)
        {
            Vector3 pa = P(a), pb = P(b), pc = P(c), pd = P(d);
            Vector3 n = Vector3.Cross(pb - pa, pd - pa).normalized;
            Vector2 ua = new Vector2(uv.xMin, uv.yMin), ub = new Vector2(uv.xMax, uv.yMin), uc = new Vector2(uv.xMax, uv.yMax), ud = new Vector2(uv.xMin, uv.yMax);
            if (Vector3.Dot(n, m.MultiplyVector(facing)) < 0)
            {
                (pb, pd) = (pd, pb);
                (ub, ud) = (ud, ub);
                n = -n;
            }
            int i = V(pa, n, ua);
            V(pb, n, ub);
            V(pc, n, uc);
            V(pd, n, ud);
            tris.Add(i); tris.Add(i + 1); tris.Add(i + 2);
            tris.Add(i); tris.Add(i + 2); tris.Add(i + 3);
        }

        /// 长方体。center 是中心，size 是长宽高。skip：不要的面（0 +x 1 -x 2 +y 3 -y 4 +z 5 -z）
        public void Box(Vector3 center, Vector3 size, int skipMask = 0)
        {
            Vector3 h = size * 0.5f;
            Vector3 c = center;
            if ((skipMask & 1) == 0) Quad(c + new Vector3(h.x, -h.y, -h.z), c + new Vector3(h.x, h.y, -h.z), c + new Vector3(h.x, h.y, h.z), c + new Vector3(h.x, -h.y, h.z), Vector3.right);
            if ((skipMask & 2) == 0) Quad(c + new Vector3(-h.x, -h.y, -h.z), c + new Vector3(-h.x, h.y, -h.z), c + new Vector3(-h.x, h.y, h.z), c + new Vector3(-h.x, -h.y, h.z), Vector3.left);
            if ((skipMask & 4) == 0) Quad(c + new Vector3(-h.x, h.y, -h.z), c + new Vector3(h.x, h.y, -h.z), c + new Vector3(h.x, h.y, h.z), c + new Vector3(-h.x, h.y, h.z), Vector3.up);
            if ((skipMask & 8) == 0) Quad(c + new Vector3(-h.x, -h.y, -h.z), c + new Vector3(h.x, -h.y, -h.z), c + new Vector3(h.x, -h.y, h.z), c + new Vector3(-h.x, -h.y, h.z), Vector3.down);
            if ((skipMask & 16) == 0) Quad(c + new Vector3(-h.x, -h.y, h.z), c + new Vector3(h.x, -h.y, h.z), c + new Vector3(h.x, h.y, h.z), c + new Vector3(-h.x, h.y, h.z), Vector3.forward);
            if ((skipMask & 32) == 0) Quad(c + new Vector3(-h.x, -h.y, -h.z), c + new Vector3(h.x, -h.y, -h.z), c + new Vector3(h.x, h.y, -h.z), c + new Vector3(-h.x, h.y, -h.z), Vector3.back);
        }

        /// 旋转体：profile 是一串（半径, 高度），从下往上；绕 y 轴转一圈。做柱子、柱础、灯笼、香炉、蒲团、钟。
        public void Lathe(Vector3 origin, IList<Vector2> profile, int sides = 24, bool capBottom = false, bool capTop = false)
        {
            int rings = profile.Count;
            float[] arc = new float[rings];
            float maxR = 0;
            for (int i = 0; i < rings; i++)
            {
                if (i > 0) arc[i] = arc[i - 1] + Vector2.Distance(profile[i], profile[i - 1]);
                maxR = Mathf.Max(maxR, profile[i].x);
            }
            int start = verts.Count;
            for (int i = 0; i < rings; i++)
            {
                // 轮廓的切线 → 法线
                Vector2 t = (profile[Mathf.Min(i + 1, rings - 1)] - profile[Mathf.Max(i - 1, 0)]).normalized;
                Vector2 n2 = new Vector2(t.y, -t.x);
                for (int s = 0; s <= sides; s++)
                {
                    float a = s / (float)sides * Mathf.PI * 2f;
                    Vector3 dir = new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a));
                    Vector3 p = origin + dir * profile[i].x + Vector3.up * profile[i].y;
                    Vector3 n = (dir * n2.x + Vector3.up * n2.y).normalized;
                    V(P(p), N(n), new Vector2(s / (float)sides * Mathf.PI * 2f * maxR, arc[i]));
                }
            }
            int w = sides + 1;
            for (int i = 0; i < rings - 1; i++)
                for (int s = 0; s < sides; s++)
                {
                    int a0 = start + i * w + s, a1 = a0 + 1, b0 = a0 + w, b1 = b0 + 1;
                    tris.Add(a0); tris.Add(b0); tris.Add(a1);
                    tris.Add(a1); tris.Add(b0); tris.Add(b1);
                }
            if (capBottom) Disc(origin + Vector3.up * profile[0].y, profile[0].x, sides, Vector3.down);
            if (capTop) Disc(origin + Vector3.up * profile[rings - 1].y, profile[rings - 1].x, sides, Vector3.up);
        }

        public void Cylinder(Vector3 baseCenter, float radius, float height, int sides = 20, bool caps = true, float topRadius = -1)
        {
            if (topRadius < 0) topRadius = radius;
            Lathe(baseCenter, new[] { new Vector2(radius, 0), new Vector2(topRadius, height) }, sides, caps, caps);
        }

        public void Disc(Vector3 center, float radius, int sides, Vector3 facing)
        {
            Vector3 n = N(facing);
            int c = V(P(center), n, BoxUV(P(center), n));
            for (int s = 0; s <= sides; s++)
            {
                float a = s / (float)sides * Mathf.PI * 2f;
                Vector3 p = P(center + new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a)) * radius);
                V(p, n, BoxUV(p, n));
            }
            bool up = Vector3.Dot(facing, Vector3.up) > 0;
            for (int s = 0; s < sides; s++)
            {
                tris.Add(c);
                if (up) { tris.Add(c + 2 + s); tris.Add(c + 1 + s); }
                else { tris.Add(c + 1 + s); tris.Add(c + 2 + s); }
            }
        }

        /// 沿一串点走的圆管，半径可以逐点不同。做树枝、屋脊、绳子。
        public void Tube(IList<Vector3> path, Func<float, float> radiusAt, int sides = 8, bool capEnd = true)
        {
            int n = path.Count;
            if (n < 2) return;
            int start = verts.Count;
            Vector3 prevSide = Vector3.zero;
            float len = 0;
            float maxR = 0;
            for (int i = 0; i < n; i++) maxR = Mathf.Max(maxR, radiusAt(i / (float)(n - 1)));
            for (int i = 0; i < n; i++)
            {
                Vector3 t = (path[Mathf.Min(i + 1, n - 1)] - path[Mathf.Max(i - 1, 0)]).normalized;
                Vector3 side = i == 0 ? Vector3.Cross(t, Mathf.Abs(t.y) > 0.9f ? Vector3.right : Vector3.up).normalized : (prevSide - t * Vector3.Dot(prevSide, t)).normalized;
                prevSide = side;
                Vector3 up = Vector3.Cross(t, side);
                if (i > 0) len += Vector3.Distance(path[i], path[i - 1]);
                float r = radiusAt(i / (float)(n - 1));
                for (int s = 0; s <= sides; s++)
                {
                    float a = s / (float)sides * Mathf.PI * 2f;
                    Vector3 d = side * Mathf.Cos(a) + up * Mathf.Sin(a);
                    V(P(path[i] + d * r), N(d), new Vector2(s / (float)sides * Mathf.PI * 2f * maxR, len));
                }
            }
            int w = sides + 1;
            for (int i = 0; i < n - 1; i++)
                for (int s = 0; s < sides; s++)
                {
                    int a0 = start + i * w + s, a1 = a0 + 1, b0 = a0 + w, b1 = b0 + 1;
                    tris.Add(a0); tris.Add(a1); tris.Add(b0);
                    tris.Add(a1); tris.Add(b1); tris.Add(b0);
                }
            if (capEnd)
            {
                int c = V(P(path[n - 1]), N((path[n - 1] - path[n - 2]).normalized), Vector2.zero);
                int ring = start + (n - 1) * w;
                for (int s = 0; s < sides; s++) { tris.Add(c); tris.Add(ring + s + 1); tris.Add(ring + s); }
            }
        }

        /// 参数曲面：f(u,v) 给出位置，u、v 都在 0..1。uvMeters 是这块曲面两个方向大约有多少米（决定贴图疏密）。
        /// facing 是曲面大致朝哪边，用来定正反面。
        public void Surface(Func<float, float, Vector3> f, int nu, int nv, Vector2 uvMeters, Vector3 facing, bool doubleSided = false)
        {
            int start = verts.Count;
            const float e = 0.002f;
            for (int j = 0; j <= nv; j++)
                for (int i = 0; i <= nu; i++)
                {
                    float u = i / (float)nu, v = j / (float)nv;
                    Vector3 p = P(f(u, v));
                    Vector3 du = P(f(Mathf.Min(u + e, 1), v)) - P(f(Mathf.Max(u - e, 0), v));
                    Vector3 dv = P(f(u, Mathf.Min(v + e, 1))) - P(f(u, Mathf.Max(v - e, 0)));
                    Vector3 n = Vector3.Cross(du, dv).normalized;
                    if (Vector3.Dot(n, m.MultiplyVector(facing)) < 0) n = -n;
                    V(p, n, new Vector2(u * uvMeters.x, v * uvMeters.y));
                }
            // 用中间那个点的法线判断三角形该怎么绕
            int w = nu + 1;
            Vector3 p00 = verts[start], p10 = verts[start + 1], p01 = verts[start + w];
            bool flip = Vector3.Dot(Vector3.Cross(p10 - p00, p01 - p00), norms[start]) < 0;
            for (int j = 0; j < nv; j++)
                for (int i = 0; i < nu; i++)
                {
                    int a = start + j * w + i, b = a + 1, c = a + w, d = c + 1;
                    if (flip) { tris.Add(a); tris.Add(c); tris.Add(b); tris.Add(b); tris.Add(c); tris.Add(d); }
                    else { tris.Add(a); tris.Add(b); tris.Add(c); tris.Add(b); tris.Add(d); tris.Add(c); }
                }
            if (doubleSided)
            {
                int count = verts.Count - start;
                int tStart = tris.Count - nu * nv * 6;
                for (int k = 0; k < count; k++) V(verts[start + k], -norms[start + k], uvs[start + k]);
                for (int k = 0; k < nu * nv * 6; k += 3)
                {
                    tris.Add(tris[tStart + k] + count);
                    tris.Add(tris[tStart + k + 2] + count);
                    tris.Add(tris[tStart + k + 1] + count);
                }
            }
        }

        /// 一张两面都看得见的卡片（树叶、布条）。sway0、sway1 是下边和上边随风摆动的幅度。
        public void Card(Vector3 center, Vector3 right, Vector3 up, Rect uv, float swayBottom, float swayTop, Vector3? normal = null)
        {
            Color keep = color;
            Vector3 a = P(center - right - up), b = P(center + right - up), c = P(center + right + up), d = P(center - right + up);
            Vector3 n = normal.HasValue ? N(normal.Value) : Vector3.Cross(b - a, d - a).normalized;
            int i = verts.Count;
            color = new Color(swayBottom, 0, 0, 1);
            V(a, n, new Vector2(uv.xMin, uv.yMin));
            V(b, n, new Vector2(uv.xMax, uv.yMin));
            color = new Color(swayTop, 0, 0, 1);
            V(c, n, new Vector2(uv.xMax, uv.yMax));
            V(d, n, new Vector2(uv.xMin, uv.yMax));
            tris.Add(i); tris.Add(i + 1); tris.Add(i + 2);
            tris.Add(i); tris.Add(i + 2); tris.Add(i + 3);
            color = keep;
        }

        public Mesh Build(string name)
        {
            var mesh = new Mesh { name = name };
            if (verts.Count > 65000) mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
            mesh.SetVertices(verts);
            mesh.SetNormals(norms);
            mesh.SetUVs(0, uvs);
            mesh.SetColors(cols);
            mesh.SetTriangles(tris, 0);
            mesh.RecalculateTangents();
            mesh.RecalculateBounds();
            return mesh;
        }
    }

    /// 可重复的随机数：同一个种子每次生成的场景一模一样
    public class Rng
    {
        uint s;
        public Rng(int seed) { s = (uint)seed * 747796405u + 2891336453u; }
        public float Next()
        {
            s ^= s << 13; s ^= s >> 17; s ^= s << 5;
            return (s & 0xFFFFFF) / (float)0x1000000;
        }
        public float Range(float a, float b) => a + (b - a) * Next();
        public int Int(int n) => Mathf.Min((int)(Next() * n), n - 1);
        public Vector3 InSphere()
        {
            for (int i = 0; i < 20; i++)
            {
                var v = new Vector3(Range(-1, 1), Range(-1, 1), Range(-1, 1));
                if (v.sqrMagnitude <= 1) return v;
            }
            return Vector3.zero;
        }
    }
}
