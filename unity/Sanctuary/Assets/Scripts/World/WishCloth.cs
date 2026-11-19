using System;
using System.Collections.Generic;
using UnityEngine;

namespace Yuanjing
{
    /// 许愿树绳上的红布条、木牌：网格和贴图（按真实大小做，不再靠放大）。
    ///
    /// 布条：宽 0.14、长约 0.62 米。上端收拢系在绳上（一个绳结加两条短尾巴），下端是一排毛边线头，两边一道金线。
    /// 木牌：0.20 × 0.26 米的五边形小木板，倒角，红绳吊着，底下一个金珠加红穗子。
    ///
    /// 每件都是两个子网格：0 是写字的正面（每件一张自己的贴图，Flutter 用应用里的字体写好字送来一张灰度图，
    /// 白是布、黑是墨，这里叠上布纹/木纹合成），1 是背面、侧边、绳结、穗子（大家共用一张贴图）。
    /// 正面背面是两层分开的面、都只画朝外那一面，所以从背后看不会看到反过来的字。
    /// 本地坐标：原点是绳上那一格（Slot）的点，+z 是正面朝外（背对树），y 朝上。
    /// 着色器是 Yuanjing/Toon 的「普通模型」用法：颜色 = 贴图 × _BaseColor，顶点色红色通道是随风摆动的幅度。
    public static class WishCloth
    {
        // ── Flutter 那边写字的图（wish_mask.dart 里是同一组数）──
        public const int RibbonW = 128, RibbonH = 512, PlaqueW = 256, PlaqueH = 320;

        public const float RibbonWidth = 0.14f, RibbonBody = 0.575f, RibbonFringe = 0.045f;
        /// 布条贴图里毛边占下面多少（v 从 0 到这里是线头）
        const float FringeV = 0.06f;
        public const float PlaqueWidth = 0.20f, PlaqueTop = -0.11f, PlaqueShoulder = -0.17f, PlaqueBottom = -0.37f, PlaqueThick = 0.012f;

        /// 绳子（trees.py 的 tree_wish：管半径 0.024）中心在 Slot 点上面 0.03 米。绳结套在绳子外面：圈的半径要大过绳子半径加管子半径
        public const float RopeAbove = 0.03f, RopeRadius = 0.024f;
        const float KnotR = 0.034f, KnotTube = 0.0075f, PlaqueKnotR = 0.033f, PlaqueKnotTube = 0.006f;

        static Mesh ribbon, plaque;
        static Texture2D ribbonBack, plaqueTrim, ribbonBlank, plaqueBlank;
        /// 没写字的布、木头的像素（算一次留着）：每件只在有墨的地方改颜色，不用每个像素重算布纹木纹
        static Color32[] ribbonBase, plaqueBase, plaqueBaseSeal;

        // ── 拼网格的小工具：两个子网格，三角形朝向按给的法线定 ──
        class Builder
        {
            public readonly List<Vector3> v = new List<Vector3>();
            public readonly List<Vector2> uv = new List<Vector2>();
            public readonly List<Color> c = new List<Color>();
            public readonly List<int>[] sub = { new List<int>(), new List<int>() };

            public int Add(Vector3 p, Vector2 t, float sway)
            {
                v.Add(p);
                uv.Add(t);
                c.Add(new Color(sway, 0, 0, 1));
                return v.Count - 1;
            }

            /// 一个三角形，朝 facing 那一面是正面
            public void Tri(int s, int a, int b, int d, Vector3 facing)
            {
                Vector3 n = Vector3.Cross(v[b] - v[a], v[d] - v[a]);
                if (Vector3.Dot(n, facing) >= 0) { sub[s].Add(a); sub[s].Add(b); sub[s].Add(d); }
                else { sub[s].Add(a); sub[s].Add(d); sub[s].Add(b); }
            }

            public void Quad(int s, int a, int b, int d, int e, Vector3 facing)
            {
                Tri(s, a, b, d, facing);
                Tri(s, a, d, e, facing);
            }

            public Mesh Build(string name)
            {
                var m = new Mesh { name = name };
                m.SetVertices(v);
                m.SetUVs(0, uv);
                m.SetColors(c);
                m.subMeshCount = 2;
                m.SetTriangles(sub[0], 0);
                m.SetTriangles(sub[1], 1);
                m.RecalculateNormals();
                m.RecalculateBounds();
                // 随风摆动会把顶点挪出去一点，包围盒放大些，免得边上被裁掉
                var b = m.bounds;
                b.Expand(0.4f);
                m.bounds = b;
                return m;
            }

            /// 一圈管子（绳结）：绕着 axis 的圆环，圆心 center，大半径 R，管半径 r
            public void Torus(int s, Vector3 center, Vector3 axis, float R, float r, int ring, int tube, Vector2 texAt, float sway)
            {
                axis.Normalize();
                Vector3 e1 = Vector3.Cross(axis, Mathf.Abs(axis.y) > 0.9f ? Vector3.right : Vector3.up).normalized, e2 = Vector3.Cross(axis, e1);
                int start = v.Count;
                for (int i = 0; i <= ring; i++)
                {
                    float a = i / (float)ring * Mathf.PI * 2f;
                    Vector3 radial = e1 * Mathf.Cos(a) + e2 * Mathf.Sin(a);
                    // 绳结不是正圆：一边鼓一点（打结的那一团）
                    float bump = 1f + 0.35f * Mathf.Max(0, Mathf.Cos(a - 0.6f)) * Mathf.Max(0, Mathf.Cos(a - 0.6f));
                    for (int j = 0; j <= tube; j++)
                    {
                        float b = j / (float)tube * Mathf.PI * 2f;
                        Vector3 p = center + radial * R + (radial * Mathf.Cos(b) + axis * Mathf.Sin(b)) * r * bump;
                        Add(p, texAt, sway);
                    }
                }
                int w = tube + 1;
                for (int i = 0; i < ring; i++)
                    for (int j = 0; j < tube; j++)
                    {
                        int a0 = start + i * w + j, a1 = a0 + 1, b0 = a0 + w, b1 = b0 + 1;
                        Vector3 mid = (v[a0] + v[b1]) * 0.5f;
                        float ang = (i + 0.5f) / ring * Mathf.PI * 2f;
                        Vector3 rc = center + (e1 * Mathf.Cos(ang) + e2 * Mathf.Sin(ang)) * R;
                        Quad(s, a0, a1, b1, b0, mid - rc);
                    }
            }

            /// 一根细管子（绳子、穗子）：从 a 到 b，半径 ra 到 rb，sides 条边
            public void Tube(int s, Vector3 a, Vector3 b, float ra, float rb, int sides, Vector2 texAt, float swayA, float swayB)
            {
                Vector3 axis = (b - a).normalized;
                Vector3 e1 = Vector3.Cross(axis, Mathf.Abs(axis.y) > 0.9f ? Vector3.right : Vector3.up).normalized, e2 = Vector3.Cross(axis, e1);
                int start = v.Count;
                for (int k = 0; k <= 1; k++)
                    for (int i = 0; i <= sides; i++)
                    {
                        float ang = i / (float)sides * Mathf.PI * 2f;
                        Vector3 rad = e1 * Mathf.Cos(ang) + e2 * Mathf.Sin(ang);
                        Add((k == 0 ? a : b) + rad * (k == 0 ? ra : rb), texAt + new Vector2(0, k * 0.02f), k == 0 ? swayA : swayB);
                    }
                int w = sides + 1;
                for (int i = 0; i < sides; i++)
                {
                    int a0 = start + i, a1 = a0 + 1, b0 = a0 + w, b1 = b0 + 1;
                    float ang = (i + 0.5f) / sides * Mathf.PI * 2f;
                    Quad(s, a0, a1, b1, b0, e1 * Mathf.Cos(ang) + e2 * Mathf.Sin(ang));
                }
            }
        }

        static float Hash(int i, int k) => Mathf.Abs(Mathf.Sin(i * 127.1f + k * 311.7f) * 43758.5453f) % 1f;

        // ── 红布条 ──

        /// 布条上一点的位置：u 横向 0..1（0 在看的人左手边，也就是本地 +x），t 竖向 0（上端）..1（下端）
        static Vector3 RibbonPoint(float u, float t, float side)
        {
            // 上端收拢在绳结里，往下慢慢展开成整幅
            float gather = Mathf.Lerp(0.5f, 1f, Mathf.SmoothStep(0f, 1f, t / 0.1f));
            float x = (0.5f - u) * RibbonWidth * gather;
            float y = -0.004f - t * RibbonBody;
            // 布不是平的：竖着有一道缓缓的起伏，横着微微往外拱，还带一点扭
            float z = 0.012f * Mathf.Sin(t * Mathf.PI * 1.25f + 0.2f) * (1f - 0.35f * t)
                    + 0.007f * (1f - Mathf.Pow(2f * u - 1f, 2f)) * Mathf.SmoothStep(0f, 1f, t / 0.15f)
                    + (u - 0.5f) * 0.018f * Mathf.Sin(t * Mathf.PI);
            return new Vector3(x, y, z + side * 0.0007f);
        }

        public static Mesh RibbonMesh()
        {
            if (ribbon != null) return ribbon;
            var bd = new Builder();
            const int NA = 4, NL = 16;
            float totalLen = RibbonBody + RibbonFringe;
            // 正面（子网格 0，写字的那张）和背面（子网格 1，素布）
            foreach (float side in new[] { 1f, -1f })
            {
                int sub = side > 0 ? 0 : 1;
                int start = bd.v.Count;
                for (int j = 0; j <= NL; j++)
                {
                    float t = j / (float)NL;
                    float sw = Mathf.Pow((0.004f + t * RibbonBody) / totalLen, 2f);
                    for (int i = 0; i <= NA; i++)
                    {
                        float u = i / (float)NA;
                        bd.Add(RibbonPoint(u, t, side), new Vector2(side > 0 ? u : 1f - u, 1f - t * (1f - FringeV)), sw);
                    }
                }
                for (int j = 0; j < NL; j++)
                    for (int i = 0; i < NA; i++)
                    {
                        int a = start + j * (NA + 1) + i;
                        bd.Quad(sub, a, a + 1, a + NA + 2, a + NA + 1, Vector3.forward * side);
                    }
                // 下端的毛边：一根根线头，长短不一、略歪
                const int K = 12;
                for (int k = 0; k < K; k++)
                {
                    float u0 = (k + 0.12f) / K, u1 = (k + 0.88f) / K, um = (u0 + u1) * 0.5f;
                    float len = RibbonFringe * (0.55f + 0.45f * Hash(k, 3));
                    float lean = (Hash(k, 7) - 0.5f) * 0.012f;
                    Vector3 p0 = RibbonPoint(u0, 1f, side), p1 = RibbonPoint(u1, 1f, side);
                    Vector3 tip = (p0 + p1) * 0.5f + new Vector3(lean, -len, 0.002f * (Hash(k, 9) - 0.5f));
                    Vector3 tipL = tip + (p0 - p1) * 0.18f, tipR = tip - (p0 - p1) * 0.18f;
                    float sw0 = Mathf.Pow((0.004f + RibbonBody) / totalLen, 2f), sw1 = Mathf.Pow((0.004f + RibbonBody + len) / totalLen, 2f);
                    float su(float uu) => side > 0 ? uu : 1f - uu;
                    int a = bd.Add(p0, new Vector2(su(u0), FringeV), sw0);
                    int b = bd.Add(p1, new Vector2(su(u1), FringeV), sw0);
                    int c = bd.Add(tipR, new Vector2(su(um + 0.01f), 0f), sw1);
                    int d = bd.Add(tipL, new Vector2(su(um - 0.01f), 0f), sw1);
                    bd.Quad(sub, a, b, c, d, Vector3.forward * side);
                }
            }
            // 绳结：绕着绳子（本地 x 方向，Slot 的朝向就是垂直于这段绳子朝外）的一圈，套在绳子外面不埋进去
            Vector2 red = new Vector2(0.5f, 0.55f);
            bd.Torus(1, new Vector3(0, RopeAbove, 0), Vector3.right, KnotR, KnotTube, 14, 6, red, 0f);
            // 打结剩下的两条短尾巴，从绳结前面往两边斜着垂下来
            foreach (float sx in new[] { -1f, 1f })
            {
                Vector3 top = new Vector3(sx * 0.008f, RopeAbove - 0.022f, KnotR + 0.004f);
                Vector3 dir = new Vector3(sx * 0.42f, -1f, 0.25f).normalized;
                Vector3 across = Vector3.Cross(dir, Vector3.forward).normalized * 0.011f;
                for (int k = 0; k < 2; k++)
                {
                    float side = k == 0 ? 1f : -1f;
                    Vector3 off = Vector3.forward * 0.0006f * side;
                    Vector3 bend = new Vector3(0, 0, 0.006f);
                    int a = bd.Add(top - across + off, red, 0f);
                    int b = bd.Add(top + across + off, red, 0f);
                    int c = bd.Add(top + dir * 0.07f + across * 0.7f + bend + off, red + new Vector2(0.02f, 0), 0.05f);
                    int d = bd.Add(top + dir * 0.07f - across * 0.7f + bend + off, red + new Vector2(0.02f, 0), 0.05f);
                    bd.Quad(1, a, b, c, d, Vector3.forward * side);
                }
            }
            return ribbon = bd.Build("WishRibbon");
        }

        static Mesh roll;

        /// 卷起来的红布条（走去绳子那里的路上捏在手里）：从下往上卷成一小卷，卷轴是本地 z（布的宽 0.14 米），
        /// 两头露着金线的布边（贴图 u 的两边），最外一层的布头压出一道台阶，再垂下来一小截带毛边的布头。全用素布那一面（子网格 1）
        public static Mesh RollMesh()
        {
            if (roll != null) return roll;
            var bd = new Builder();
            const int NT = 32, NA = 10;
            const float turns = 1.15f, r0 = 0.0165f, grow = 0.0045f, half = RibbonWidth * 0.5f;
            float R(float a) => r0 + grow * a / (Mathf.PI * 2f);
            // 布卷是软的：两头往里收一点（最外边收 18%），中间略鼓，不是一根直筒（直筒加平的两头，远看像一块红砖）
            float Taper(float u) => 1f - 0.18f * Mathf.Pow(Mathf.Abs(2f * u - 1f), 4f);
            float aEnd = turns * Mathf.PI * 2f;
            // 卷着的那一层：螺旋（转一圈多一点，最外层盖过开头那一截）。u 沿卷轴（布宽），v 沿着布长慢慢走
            int start = bd.v.Count;
            for (int j = 0; j <= NT; j++)
            {
                float a = aEnd * j / NT;
                Vector3 rad = new Vector3(Mathf.Sin(a), -Mathf.Cos(a), 0);
                for (int i = 0; i <= NA; i++)
                {
                    float u = i / (float)NA;
                    bd.Add(rad * R(a) * Taper(u) + Vector3.forward * Mathf.Lerp(-half, half, u), new Vector2(u, 0.25f + 0.4f * j / NT), 0f);
                }
            }
            for (int j = 0; j < NT; j++)
                for (int i = 0; i < NA; i++)
                {
                    int a = start + j * (NA + 1) + i;
                    float am = aEnd * (j + 0.5f) / NT;
                    bd.Quad(1, a, a + 1, a + NA + 2, a + NA + 1, new Vector3(Mathf.Sin(am), -Mathf.Cos(am), 0));
                }
            // 两头：卷的端面看得出一圈圈卷着的布——由外往里一圈金边（布边的金线）、一圈红（布面），按螺旋一层层往里，中间一个小孔
            foreach (float sz in new[] { -1f, 1f })
            {
                float tk = Taper(sz < 0 ? 0f : 1f);
                Vector2 gold = new Vector2(sz < 0 ? 0.01f : 0.99f, 0.5f), red = new Vector2(sz < 0 ? 0.12f : 0.88f, 0.5f);
                const int NS = 72;
                // 螺旋从卷芯（半径约 3 毫米）一直绕到最外层，每圈往外 grow；每一点往里画一条宽 grow 的带子，整个端面就盖满了
                float aIn = -(r0 - 0.003f) / grow * Mathf.PI * 2f;
                int prev = -1, prevIn = -1;
                for (int k = 0; k <= NS; k++)
                {
                    float a = Mathf.Lerp(aIn, aEnd, k / (float)NS);
                    float rr = R(a) * tk;
                    Vector3 dir = new Vector3(Mathf.Sin(a), -Mathf.Cos(a), 0);
                    Vector3 z = Vector3.forward * sz * half;
                    // 每一层：外沿一窄条金线、里面是红布，再往里是下一层
                    int o = bd.Add(dir * rr + z, gold, 0f);
                    int m = bd.Add(dir * (rr - grow * 0.35f * tk) + z, gold, 0f);
                    int i2 = bd.Add(dir * (rr - grow * 0.35f * tk) + z, red, 0f);
                    int c = bd.Add(dir * Mathf.Max(0f, rr - grow * tk) + z, red, 0f);
                    if (prev >= 0)
                    {
                        bd.Quad(1, prev, o, m, prev + 1, Vector3.forward * sz);
                        bd.Quad(1, prevIn, i2, c, prevIn + 1, Vector3.forward * sz);
                    }
                    prev = o;
                    prevIn = i2;
                }
            }
            // 布头：从最外层的边上顺着往下垂 4 厘米，下端是毛边（贴图里 v 0..FringeV 那一段）
            Vector3 lip = new Vector3(Mathf.Sin(aEnd), -Mathf.Cos(aEnd), 0) * R(aEnd);
            Vector3 down = new Vector3(0.25f, -1f, 0).normalized;
            // 两面各一层（布头薄，从哪边都看得到；各用各的顶点，法线不会抵消）
            foreach (float side in new[] { 1f, -1f })
            {
                int t0 = bd.v.Count;
                for (int k = 0; k <= 2; k++)
                    for (int i = 0; i <= NA; i++)
                    {
                        float u = i / (float)NA, f = k / 2f;
                        Vector3 p = lip * Taper(u) + down * (0.04f * f) + Vector3.forward * Mathf.Lerp(-half, half, u) * (1f - 0.04f * f);
                        bd.Add(p + new Vector3(0.004f * f * f + side * 0.0006f, 0, 0), new Vector2(u, Mathf.Lerp(0.25f, 0f, f)), 0f);
                    }
                for (int k = 0; k < 2; k++)
                    for (int i = 0; i < NA; i++)
                    {
                        int a = t0 + k * (NA + 1) + i;
                        bd.Quad(1, a, a + 1, a + NA + 2, a + NA + 1, Vector3.right * side);
                    }
            }
            return roll = bd.Build("WishRibbonRoll");
        }

        // ── 木牌 ──

        /// 木牌的外轮廓（看正面，逆时针）：底边两角、两肩、尖顶
        static readonly Vector2[] PlaqueOutline =
        {
            new Vector2(-PlaqueWidth / 2, PlaqueBottom), new Vector2(PlaqueWidth / 2, PlaqueBottom), new Vector2(PlaqueWidth / 2, PlaqueShoulder),
            new Vector2(0, PlaqueTop), new Vector2(-PlaqueWidth / 2, PlaqueShoulder),
        };

        static Vector2 FaceUV(Vector2 p) => new Vector2((PlaqueWidth / 2 - p.x) / PlaqueWidth, (p.y - PlaqueBottom) / (PlaqueTop - PlaqueBottom));

        /// 轮廓往里缩 d（倒角那一圈的内边）
        static Vector2[] Inset(Vector2[] o, float d)
        {
            int n = o.Length;
            var r = new Vector2[n];
            for (int i = 0; i < n; i++)
            {
                Vector2 a = o[(i + n - 1) % n], b = o[i], c = o[(i + 1) % n];
                Vector2 n1 = new Vector2(-(b - a).y, (b - a).x).normalized, n2 = new Vector2(-(c - b).y, (c - b).x).normalized;
                Vector2 bis = (n1 + n2).normalized;
                r[i] = b + bis * d / Mathf.Max(0.3f, Vector2.Dot(bis, n1));
            }
            return r;
        }

        public static Mesh PlaqueMesh()
        {
            if (plaque != null) return plaque;
            var bd = new Builder();
            const float sway = 0.55f, ch = 0.0028f;
            float hz = PlaqueThick / 2;
            var outer = PlaqueOutline;
            var inner = Inset(outer, ch);
            int n = outer.Length;
            Vector2 wood = new Vector2(0.25f, 0.5f);
            foreach (float side in new[] { 1f, -1f })
            {
                // 板面：正面写字（子网格 0）、背面素木（子网格 1，木纹那一块）
                int sub = side > 0 ? 0 : 1;
                Vector2 cen = Vector2.zero;
                foreach (var p in inner) cen += p;
                cen /= n;
                Vector2 UV(Vector2 p) => side > 0 ? FaceUV(p) : new Vector2(FaceUV(p).x * 0.49f, FaceUV(p).y);
                int ci = bd.Add(new Vector3(cen.x, cen.y, hz * side), UV(cen), sway);
                int first = bd.v.Count;
                for (int i = 0; i < n; i++) bd.Add(new Vector3(inner[i].x, inner[i].y, hz * side), UV(inner[i]), sway);
                for (int i = 0; i < n; i++) bd.Tri(sub, ci, first + i, first + (i + 1) % n, Vector3.forward * side);
                // 倒角：板面边缘到侧面斜着削一小圈
                for (int i = 0; i < n; i++)
                {
                    int j = (i + 1) % n;
                    Vector2 e = outer[j] - outer[i];
                    Vector3 nrm = (new Vector3(e.y, -e.x, 0).normalized + Vector3.forward * side).normalized;
                    int a = bd.Add(new Vector3(inner[i].x, inner[i].y, hz * side), wood, sway);
                    int b = bd.Add(new Vector3(inner[j].x, inner[j].y, hz * side), wood + new Vector2(0.02f, 0), sway);
                    int c = bd.Add(new Vector3(outer[j].x, outer[j].y, (hz - ch) * side), wood + new Vector2(0.02f, 0.03f), sway);
                    int d = bd.Add(new Vector3(outer[i].x, outer[i].y, (hz - ch) * side), wood + new Vector2(0, 0.03f), sway);
                    bd.Quad(1, a, b, c, d, nrm);
                }
            }
            // 侧面（板的厚度）
            for (int i = 0; i < n; i++)
            {
                int j = (i + 1) % n;
                Vector2 e = outer[j] - outer[i];
                Vector3 nrm = new Vector3(e.y, -e.x, 0).normalized;
                int a = bd.Add(new Vector3(outer[i].x, outer[i].y, hz - ch), wood + new Vector2(0.1f, 0), sway);
                int b = bd.Add(new Vector3(outer[j].x, outer[j].y, hz - ch), wood + new Vector2(0.1f + e.magnitude, 0), sway);
                int c = bd.Add(new Vector3(outer[j].x, outer[j].y, -hz + ch), wood + new Vector2(0.1f + e.magnitude, 0.02f), sway);
                int d = bd.Add(new Vector3(outer[i].x, outer[i].y, -hz + ch), wood + new Vector2(0.1f, 0.02f), sway);
                bd.Quad(1, a, b, c, d, nrm);
            }
            // 红绳：从尖顶下面的小孔分两股上去，在绳子上打一个结
            Vector2 red = new Vector2(0.75f, 0.75f), gold = new Vector2(0.75f, 0.25f);
            Vector3 hole = new Vector3(0, PlaqueTop - 0.022f, 0);
            // 两股红绳上到绳结的下沿（绳子下面），不穿进绳子里
            Vector3 knot = new Vector3(0, RopeAbove - PlaqueKnotR + 0.002f, 0.004f);
            foreach (float sx in new[] { -1f, 1f })
                bd.Tube(1, hole + new Vector3(sx * 0.004f, 0, sx * 0.004f), knot + new Vector3(sx * 0.005f, 0, 0), 0.0024f, 0.0024f, 5, red, sway, 0f);
            bd.Torus(1, new Vector3(0, RopeAbove, 0), Vector3.right, PlaqueKnotR, PlaqueKnotTube, 14, 5, red, 0f);
            // 穗子：底边中间一小段绳，一颗金珠，下面一把红线
            Vector3 b0 = new Vector3(0, PlaqueBottom, 0);
            bd.Tube(1, b0, b0 + Vector3.down * 0.018f, 0.002f, 0.002f, 5, red, sway, sway + 0.05f);
            Vector3 bead = b0 + Vector3.down * 0.026f;
            bd.Tube(1, bead + Vector3.up * 0.008f, bead, 0.003f, 0.0085f, 8, gold, sway + 0.05f, sway + 0.06f);
            bd.Tube(1, bead, bead + Vector3.down * 0.008f, 0.0085f, 0.003f, 8, gold, sway + 0.06f, sway + 0.07f);
            Vector3 tas = bead + Vector3.down * 0.008f;
            bd.Tube(1, tas, tas + Vector3.down * 0.012f, 0.0035f, 0.0055f, 8, red, sway + 0.07f, sway + 0.1f);
            bd.Tube(1, tas + Vector3.down * 0.012f, tas + Vector3.down * 0.07f, 0.0055f, 0.0095f, 10, red + new Vector2(0, 0.1f), sway + 0.1f, 1f);
            return plaque = bd.Build("WishPlaque");
        }

        // ── 贴图 ──

        /// Flutter 送来的灰度图（PNG 的 base64）。坏了、空的返回 null
        public static Texture2D DecodeMask(string base64)
        {
            if (string.IsNullOrEmpty(base64)) return null;
            try
            {
                byte[] bytes = Convert.FromBase64String(base64);
                var t = new Texture2D(2, 2, TextureFormat.RGBA32, false);
                if (!t.LoadImage(bytes, false) || t.width < 8 || t.height < 8)
                {
                    UnityEngine.Object.Destroy(t);
                    return null;
                }
                return t;
            }
            catch (Exception e)
            {
                Debug.LogWarning("[yuanjing] 布条上的字解不开：" + e.Message);
                return null;
            }
        }

        static Color32 C(float r, float g, float b) => new Color32((byte)(Mathf.Clamp01(r) * 255), (byte)(Mathf.Clamp01(g) * 255), (byte)(Mathf.Clamp01(b) * 255), 255);

        static float Noise(int x, int y) => Hash(x * 7 + 3, y * 13 + 1);

        /// 墨有多浓（0 没有墨，1 最黑）：灰度图白是布、黑是墨
        static float[] InkOf(Texture2D mask, int w, int h)
        {
            var ink = new float[w * h];
            if (mask == null) return ink;
            var px = mask.GetPixels32();
            bool same = mask.width == w && mask.height == h;
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                {
                    float g;
                    if (same)
                    {
                        var p = px[y * w + x];
                        g = (p.r + p.g + p.b) / 765f;
                        // 透明的地方算没有墨
                        g = Mathf.Lerp(1f, g, p.a / 255f);
                    }
                    else
                    {
                        var p = mask.GetPixelBilinear((x + 0.5f) / w, (y + 0.5f) / h);
                        g = Mathf.Lerp(1f, (p.r + p.g + p.b) / 3f, p.a);
                    }
                    ink[y * w + x] = Mathf.Clamp01(1f - g);
                }
            return ink;
        }

        static Texture2D Finish(Color32[] px, int w, int h, string name)
        {
            var t = new Texture2D(w, h, TextureFormat.RGBA32, true) { name = name, wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Trilinear, anisoLevel = 4 };
            t.SetPixels32(px);
            t.Apply(true, true);
            return t;
        }

        /// 红布：经纬的细纹、几道压出来的褶子、两边的卷边和金线，下面一截是线头
        static Color32 RibbonPixel(int x, int y, int w, int h, float ink, bool back)
        {
            float u = (x + 0.5f) / w, v = (y + 0.5f) / h;
            float r = 0.80f, g = 0.13f, b = 0.10f;
            // 织纹：经线一根根略有深浅，纬线隔一行亮一点
            float warp = (Noise(x, 0) - 0.5f) * 0.10f, weft = ((y & 1) == 0 ? 0.025f : -0.02f) + (Noise(0, y) - 0.5f) * 0.05f;
            float cross = ((x + y) & 1) == 0 ? 0.015f : -0.015f;
            // 褶子：横着几道很淡的明暗
            float crease = 0.05f * Mathf.Sin(v * 37f + Mathf.Sin(u * 5f) * 0.8f) * Mathf.Sin(v * 11f + 1.3f);
            float k = 1f + warp + weft + cross + crease;
            // 两边卷边略深
            float edge = Mathf.Min(u, 1f - u);
            if (edge < 0.03f) k *= 0.78f;
            // 上端收在结里的一截略深
            if (v > 0.965f) k *= 0.82f;
            r *= k; g *= k; b *= k;
            // 金线：两边各一道，像绣上去的一针一针
            float gu = Mathf.Abs(edge - 0.052f);
            if (gu < 0.012f && v > FringeV)
            {
                float stitch = (y / 3 % 2 == 0) ? 1f : 0.82f;
                float a = Mathf.SmoothStep(1f, 0f, gu / 0.012f);
                r = Mathf.Lerp(r, 0.96f * stitch, a);
                g = Mathf.Lerp(g, 0.76f * stitch, a);
                b = Mathf.Lerp(b, 0.34f * stitch, a);
            }
            // 线头：竖着一根根，颜色浅一点
            if (v < FringeV)
            {
                float thread = 0.85f + 0.3f * Noise(x, 7);
                r = 0.84f * thread; g = 0.18f * thread; b = 0.13f * thread;
            }
            if (!back && ink > 0.001f)
            {
                // 墨：近黑，带一点暖；墨重的地方略有光泽
                float a = Mathf.Clamp01(ink * 1.05f);
                r = Mathf.Lerp(r, 0.10f, a);
                g = Mathf.Lerp(g, 0.05f, a);
                b = Mathf.Lerp(b, 0.045f, a);
            }
            return C(r, g, b);
        }

        /// 木牌正面在五边形里面多远（负数在外面）
        static float PlaqueInside(float u, float v)
        {
            float vs = (PlaqueShoulder - PlaqueBottom) / (PlaqueTop - PlaqueBottom);
            float d = Mathf.Min(Mathf.Min(u, 1f - u), v);
            // 两条屋脊斜边
            Vector2 p = new Vector2(u * PlaqueWidth, v * (PlaqueTop - PlaqueBottom));
            Vector2 apex = new Vector2(PlaqueWidth / 2, PlaqueTop - PlaqueBottom), sl = new Vector2(0, vs * (PlaqueTop - PlaqueBottom)), sr = new Vector2(PlaqueWidth, sl.y);
            float Edge(Vector2 a, Vector2 b)
            {
                Vector2 e = (b - a).normalized;
                Vector2 nn = new Vector2(e.y, -e.x);
                return Vector2.Dot(p - a, nn);
            }
            float dl = Edge(apex, sl), dr = Edge(sr, apex);
            float roof = Mathf.Min(-dl, -dr);
            return Mathf.Min(d * PlaqueWidth, roof);
        }

        /// 木牌：竖纹的浅色木头，边上熏得深一点，一圈朱红细框，字是墨，写了字的右下……左下角钤一方小红印
        static Color32 PlaquePixel(int x, int y, int w, int h, float ink, bool hasText, bool front = true)
        {
            float u = (x + 0.5f) / w, v = (y + 0.5f) / h;
            float r = 0.87f, g = 0.71f, b = 0.49f;
            // 木纹：竖着的年轮线，随高度轻轻弯
            float ring = Mathf.Sin((u * 26f + 0.5f * Mathf.Sin(v * 4.2f + u * 2.6f) + 0.15f * Mathf.Sin(v * 17f)) * Mathf.PI * 2f);
            float k = 1f + 0.07f * ring * ring * Mathf.Sign(ring) + (Noise(x, y) - 0.5f) * 0.06f + (Noise(x / 2, 3) - 0.5f) * 0.05f;
            float inside = PlaqueInside(u, v);
            // 边缘熏深
            k *= Mathf.Lerp(0.72f, 1f, Mathf.SmoothStep(0f, 0.012f, inside));
            r *= k; g *= k * 0.98f; b *= k * 0.95f;
            // 朱红细框：离边 1.1 厘米一道
            float frame = Mathf.Abs(inside - 0.011f);
            if (front && frame < 0.0013f)
            {
                float a = Mathf.SmoothStep(1f, 0f, frame / 0.0013f) * 0.85f;
                r = Mathf.Lerp(r, 0.70f, a); g = Mathf.Lerp(g, 0.18f, a); b = Mathf.Lerp(b, 0.10f, a);
            }
            // 穿绳的小孔
            float hu = (u - 0.5f) * PlaqueWidth, hv = (v - (PlaqueTop - 0.022f - PlaqueBottom) / (PlaqueTop - PlaqueBottom)) * (PlaqueTop - PlaqueBottom);
            float hr = Mathf.Sqrt(hu * hu + hv * hv);
            if (hr < 0.0045f) { r *= 0.25f; g *= 0.2f; b *= 0.18f; }
            else if (hr < 0.006f) { r *= 0.75f; g *= 0.7f; b *= 0.65f; }
            if (ink > 0.001f)
            {
                float a = Mathf.Clamp01(ink * 1.05f);
                r = Mathf.Lerp(r, 0.09f, a); g = Mathf.Lerp(g, 0.065f, a); b = Mathf.Lerp(b, 0.05f, a);
            }
            // 小红印：左下角，方的，四边留一圈白
            if (hasText && InSeal(x, y, w, h))
            {
                float su = (u - 0.13f) / 0.085f, sv = (v - 0.065f) / 0.07f;
                bool border = su < 0.12f || su > 0.88f || sv < 0.12f || sv > 0.88f;
                bool carve = !border && (Mathf.Abs(su - 0.5f) < 0.06f || Mathf.Abs(sv - 0.5f) < 0.06f || Noise(x, y) < 0.08f);
                if (border || !carve)
                {
                    float wear = Noise(x * 3, y * 5) < 0.12f ? 0.4f : 0.9f;
                    r = Mathf.Lerp(r, 0.78f, wear); g = Mathf.Lerp(g, 0.12f, wear); b = Mathf.Lerp(b, 0.10f, wear);
                }
            }
            return C(r, g, b);
        }

        /// 没写字的布（木头）那一张的像素：第一次用到时算好留着
        static Color32[] Base(bool plaq, bool seal)
        {
            int w = plaq ? PlaqueW : RibbonW, h = plaq ? PlaqueH : RibbonH;
            ref Color32[] cache = ref (plaq ? ref (seal ? ref plaqueBaseSeal : ref plaqueBase) : ref ribbonBase);
            if (cache != null) return cache;
            var px = new Color32[w * h];
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                    px[y * w + x] = plaq ? PlaquePixel(x, y, w, h, 0f, seal) : RibbonPixel(x, y, w, h, 0f, false);
            cache = px;
            return px;
        }

        /// 木牌左下角那方小红印的范围（印盖在墨上面）
        static bool InSeal(int x, int y, int w, int h)
        {
            float u = (x + 0.5f) / w, v = (y + 0.5f) / h;
            return u > 0.13f && u < 0.215f && v > 0.065f && v < 0.135f;
        }

        /// 一件心意正面的贴图：布纹或木纹叠上写的字。mask 为空就是没写字的素布、素木（共用一张）
        public static Texture2D Face(string kind, Texture2D mask)
        {
            bool plaq = kind == "plaque";
            if (mask == null)
            {
                if (plaq && plaqueBlank != null) return plaqueBlank;
                if (!plaq && ribbonBlank != null) return ribbonBlank;
            }
            int w = plaq ? PlaqueW : RibbonW, h = plaq ? PlaqueH : RibbonH;
            var ink = InkOf(mask, w, h);
            bool hasText = false;
            foreach (float i in ink) if (i > 0.3f) { hasText = true; break; }
            // 布纹木纹是现成的，只在有墨的地方往墨色上调（墨色同 RibbonPixel、PlaquePixel 里的）
            var px = (Color32[])Base(plaq, plaq && hasText).Clone();
            Color32 inkC = plaq ? C(0.09f, 0.065f, 0.05f) : C(0.10f, 0.05f, 0.045f);
            for (int i = 0; i < px.Length; i++)
            {
                float a = ink[i];
                if (a <= 0.001f) continue;
                a = Mathf.Clamp01(a * 1.05f);
                if (plaq && hasText && InSeal(i % w, i / w, w, h)) continue;
                var c = px[i];
                px[i] = new Color32((byte)(c.r + (inkC.r - c.r) * a), (byte)(c.g + (inkC.g - c.g) * a), (byte)(c.b + (inkC.b - c.b) * a), 255);
            }
            var t = Finish(px, w, h, plaq ? "WishPlaqueFace" : "WishRibbonFace");
            if (mask == null)
            {
                if (plaq) plaqueBlank = t; else ribbonBlank = t;
            }
            return t;
        }

        /// 共用的那张：布条是素红布（背面、绳结、尾巴），木牌是一张小图集（左半木纹、右上红绳、右下金珠）
        public static Texture2D Back(string kind)
        {
            if (kind == "plaque")
            {
                if (plaqueTrim != null) return plaqueTrim;
                const int w = 128, h = 128;
                var px = new Color32[w * h];
                for (int y = 0; y < h; y++)
                    for (int x = 0; x < w; x++)
                    {
                        float u = (x + 0.5f) / w, v = (y + 0.5f) / h;
                        if (u < 0.5f) px[y * w + x] = PlaquePixel(x, y, w / 2, h, 0, false, false);
                        else if (v >= 0.5f)
                        {
                            // 红绳：一股股捻起来的斜纹
                            float k = 0.85f + 0.2f * Mathf.Sin((x + y) * 1.4f) + (Noise(x, y) - 0.5f) * 0.1f;
                            px[y * w + x] = C(0.78f * k, 0.12f * k, 0.09f * k);
                        }
                        else
                        {
                            float k = 0.85f + 0.25f * Noise(x / 2, y / 2);
                            px[y * w + x] = C(0.95f * k, 0.74f * k, 0.30f * k);
                        }
                    }
                return plaqueTrim = Finish(px, w, h, "WishPlaqueTrim");
            }
            if (ribbonBack != null) return ribbonBack;
            {
                int w = RibbonW / 2, h = RibbonH / 2;
                var px = new Color32[w * h];
                for (int y = 0; y < h; y++)
                    for (int x = 0; x < w; x++)
                        px[y * w + x] = RibbonPixel(x * 2, y * 2, RibbonW, RibbonH, 0, true);
                return ribbonBack = Finish(px, w, h, "WishRibbonBack");
            }
        }
    }
}
