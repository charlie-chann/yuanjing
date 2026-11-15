using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using Yuanjing;

/// 建筑构件：曲面屋顶、柱子、石灯笼、树。山寺和教堂共用。
public static partial class SanctuaryBuild
{
    /// 屋顶曲面上的一点。u 沿屋檐方向（0..1），s 从屋檐（0）到屋脊（1）。
    /// 屋面是凹曲线（檐口平缓、越往上越陡），四个角往上翘。
    public class RoofShape
    {
        public Vector3 center;   // 檐口平面的中心
        public float W, D;       // 檐口外沿的长（x）和进深（z）
        public float L;          // 正脊的长度；等于 W 就是两坡的悬山顶，小于 W 是四坡顶
        public float H;          // 檐口到正脊的高度
        public float lift;       // 翼角起翘的高度
        public float curve = 1.6f;

        float Y(float s, float corner) => H * Mathf.Pow(s, curve) + lift * Mathf.Pow(1f - s, 2.4f) * Mathf.Pow(corner, 3.2f);
        float HalfW(float s) => Mathf.Lerp(W * 0.5f, L * 0.5f, s);
        float HalfD(float s) => Mathf.Lerp(D * 0.5f, 0f, s);

        /// 前后两坡。side = -1 是朝 -z 的那一坡，+1 是朝 +z 的。
        public Vector3 FrontBack(float u, float s, int side)
        {
            float x = (u * 2f - 1f) * HalfW(s);
            return center + new Vector3(x, Y(s, Mathf.Abs(u * 2f - 1f)), side * HalfD(s));
        }

        /// 左右两坡（四坡顶才有）。side = -1 是朝 -x 的。
        public Vector3 LeftRight(float u, float s, int side)
        {
            float z = (u * 2f - 1f) * HalfD(s);
            return center + new Vector3(side * HalfW(s), Y(s, Mathf.Abs(u * 2f - 1f)), z);
        }

        /// 前后坡上固定 x 的一条线能往上走到多高（四坡顶靠近两端的瓦垄会先碰到斜脊）
        public float MaxS(float x)
        {
            float ax = Mathf.Abs(x);
            if (ax <= L * 0.5f || W <= L + 0.001f) return 1f;
            return Mathf.Clamp01((W * 0.5f - ax) / (W * 0.5f - L * 0.5f));
        }

        public Vector3 FrontBackAtX(float x, float s, int side)
        {
            float hw = HalfW(s);
            float u = hw < 0.001f ? 0.5f : Mathf.Clamp01((x / hw + 1f) * 0.5f);
            return FrontBack(u, s, side);
        }

        public Vector3 LeftRightAtZ(float z, float s, int side)
        {
            float hd = HalfD(s);
            float u = hd < 0.001f ? 0.5f : Mathf.Clamp01((z / hd + 1f) * 0.5f);
            return LeftRight(u, s, side);
        }

        public bool Hipped => L < W - 0.01f;
        public float SlopeLength => Mathf.Sqrt(D * D * 0.25f + H * H) * 1.08f;
    }

    /// 一整座瓦屋顶：屋面、一垄一垄的筒瓦、檐口的瓦当、屋脊、檐下的椽子和望板。
    public static void Roof(Transform parent, string name, RoofShape r, Material tile, Material ridgeMat, Material wood, float rafterDepth)
    {
        var root = Group(name, parent);
        float slope = r.SlopeLength;

        // 屋面
        var mb = new MeshBuilder();
        for (int side = -1; side <= 1; side += 2)
        {
            int sd = side;
            mb.Surface((u, s) => r.FrontBack(u, s, sd), 40, 14, new Vector2(r.W, slope), new Vector3(0, 1, sd * 0.5f));
            if (r.Hipped) mb.Surface((u, s) => r.LeftRight(u, s, sd), 24, 14, new Vector2(r.D, slope), new Vector3(sd * 0.5f, 1, 0));
        }
        Add("Tiles", mb, tile, root);

        // 筒瓦：顺着坡的一条条半圆瓦垄，檐口处收一个圆头（瓦当）
        var ribs = new MeshBuilder();
        const float gap = 0.30f, rr = 0.052f;
        for (int side = -1; side <= 1; side += 2)
        {
            for (float x = -r.W * 0.5f + gap * 0.5f; x < r.W * 0.5f; x += gap)
            {
                float smax = r.MaxS(x);
                if (smax < 0.06f) continue;
                var path = new List<Vector3>();
                int seg = Mathf.Max(3, Mathf.CeilToInt(12 * smax));
                for (int i = 0; i <= seg; i++) path.Add(r.FrontBackAtX(x, smax * i / seg, side) + Vector3.up * 0.035f);
                ribs.Tube(path, t => rr, 6, false);
                ribs.Lathe(path[0] + new Vector3(0, -0.01f, side * 0.01f), new[] { new Vector2(0.001f, -0.02f), new Vector2(rr * 1.15f, -0.02f), new Vector2(rr * 1.15f, 0.03f), new Vector2(0.001f, 0.03f) }, 8);
            }
            if (!r.Hipped) continue;
            for (float z = -r.D * 0.5f + gap * 0.5f; z < r.D * 0.5f; z += gap)
            {
                float smax = Mathf.Clamp01(1f - 2f * Mathf.Abs(z) / r.D) * 0.98f;
                if (smax < 0.06f) continue;
                var path = new List<Vector3>();
                int seg = Mathf.Max(3, Mathf.CeilToInt(12 * smax));
                for (int i = 0; i <= seg; i++) path.Add(r.LeftRightAtZ(z, smax * i / seg, side) + Vector3.up * 0.035f);
                ribs.Tube(path, t => rr, 6, false);
            }
        }
        Add("TileRibs", ribs, tile, root);

        // 屋脊：正脊两头微微上翘，四坡顶再加四条斜脊，一直走到翘起的檐角
        var ridge = new MeshBuilder();
        var main = new List<Vector3>();
        for (int i = 0; i <= 20; i++)
        {
            float t = i / 20f;
            float x = Mathf.Lerp(-r.L * 0.5f - 0.25f, r.L * 0.5f + 0.25f, t);
            float end = Mathf.Pow(Mathf.Abs(t * 2f - 1f), 6f);
            main.Add(r.center + new Vector3(x, r.H + 0.16f + end * 0.55f, 0));
        }
        ridge.Tube(main, t => 0.17f + 0.05f * Mathf.Pow(Mathf.Abs(t * 2f - 1f), 4f), 10, true);
        ridge.Box(r.center + new Vector3(0, r.H + 0.02f, 0), new Vector3(r.L + 0.3f, 0.26f, 0.30f));
        if (r.Hipped)
        {
            for (int sx = -1; sx <= 1; sx += 2)
                for (int sz = -1; sz <= 1; sz += 2)
                {
                    var hip = new List<Vector3>();
                    for (int i = 0; i <= 14; i++)
                    {
                        float s = 1f - i / 14f;
                        hip.Add(r.FrontBack(sx > 0 ? 1f : 0f, s, sz) + Vector3.up * 0.09f);
                    }
                    // 檐角再往外挑出去一点
                    Vector3 tip = hip[hip.Count - 1] + (hip[hip.Count - 1] - hip[hip.Count - 2]).normalized * 0.35f + Vector3.up * 0.14f;
                    hip.Add(tip);
                    ridge.Tube(hip, t => Mathf.Lerp(0.13f, 0.085f, t), 8, true);
                }
        }
        else
        {
            // 两坡顶：山面的封檐板
            for (int sx = -1; sx <= 1; sx += 2)
                for (int sz = -1; sz <= 1; sz += 2)
                {
                    var edge = new List<Vector3>();
                    for (int i = 0; i <= 10; i++) edge.Add(r.FrontBack(sx > 0 ? 1f : 0f, i / 10f, sz) + Vector3.up * 0.06f);
                    ridge.Tube(edge, t => 0.09f, 6, true);
                }
        }
        Add("Ridge", ridge, ridgeMat, root);

        // 檐下：望板（屋面的底面）和一根根椽子，坐在檐下抬头能看到
        var under = new MeshBuilder();
        float us = Mathf.Clamp01(rafterDepth / (r.D * 0.5f));
        for (int side = -1; side <= 1; side += 2)
        {
            int sd = side;
            under.Surface((u, s) => r.FrontBack(u, s * us, sd) + Vector3.down * 0.10f, 36, 5, new Vector2(r.W, rafterDepth), new Vector3(0, -1, 0));
            // 檐口的封板
            under.Surface((u, v) => r.FrontBack(u, 0f, sd) + Vector3.down * (0.02f + 0.16f * v), 36, 1, new Vector2(r.W, 0.18f), new Vector3(0, 0, sd));
            for (float x = -r.W * 0.5f + 0.2f; x < r.W * 0.5f; x += 0.42f)
            {
                float smax = Mathf.Min(r.MaxS(x), us);
                if (smax < 0.05f) continue;
                var path = new List<Vector3>();
                for (int i = 0; i <= 6; i++) path.Add(r.FrontBackAtX(x, smax * i / 6f, side) + Vector3.down * 0.17f);
                under.Tube(path, t => 0.055f, 6, true);
            }
            if (!r.Hipped) continue;
            float usx = Mathf.Clamp01(rafterDepth / ((r.W - r.L) * 0.5f));
            under.Surface((u, s) => r.LeftRight(u, s * usx, sd) + Vector3.down * 0.10f, 24, 5, new Vector2(r.D, rafterDepth), new Vector3(0, -1, 0));
            under.Surface((u, v) => r.LeftRight(u, 0f, sd) + Vector3.down * (0.02f + 0.16f * v), 24, 1, new Vector2(r.D, 0.18f), new Vector3(sd, 0, 0));
            for (float z = -r.D * 0.5f + 0.2f; z < r.D * 0.5f; z += 0.42f)
            {
                float smax = Mathf.Min(Mathf.Clamp01(1f - 2f * Mathf.Abs(z) / r.D) * 0.98f, usx);
                if (smax < 0.05f) continue;
                var path = new List<Vector3>();
                for (int i = 0; i <= 6; i++) path.Add(r.LeftRightAtZ(z, smax * i / 6f, side) + Vector3.down * 0.17f);
                under.Tube(path, t => 0.055f, 6, true);
            }
        }
        Add("Eaves", under, wood, root);
    }

    /// 一根圆柱加石柱础。返回柱顶的高度。
    public static void Column(MeshBuilder wood, MeshBuilder stone, Vector3 at, float radius, float height)
    {
        stone.Lathe(at, new[]
        {
            new Vector2(radius * 1.9f, 0f), new Vector2(radius * 1.9f, 0.10f), new Vector2(radius * 1.55f, 0.16f),
            new Vector2(radius * 1.65f, 0.24f), new Vector2(radius * 1.25f, 0.32f), new Vector2(radius * 1.08f, 0.34f),
        }, 20, false, true);
        // 柱子上细下粗一点点，更像真的木柱
        wood.Lathe(at + Vector3.up * 0.33f, new[] { new Vector2(radius, 0f), new Vector2(radius * 0.99f, height * 0.5f), new Vector2(radius * 0.93f, height - 0.33f) }, 20);
    }

    /// 柱头上的斗拱（简化成几层交叠的木块）
    public static void Bracket(MeshBuilder mb, Vector3 top, float size)
    {
        mb.Box(top + Vector3.up * 0.09f, new Vector3(size * 0.62f, 0.18f, size * 0.62f));
        mb.Box(top + Vector3.up * 0.26f, new Vector3(size * 1.5f, 0.15f, size * 0.36f));
        mb.Box(top + Vector3.up * 0.26f, new Vector3(size * 0.36f, 0.15f, size * 1.5f));
        mb.Box(top + Vector3.up * 0.42f, new Vector3(size * 2.1f, 0.15f, size * 0.34f));
        mb.Box(top + Vector3.up * 0.42f, new Vector3(size * 0.34f, 0.15f, size * 2.1f));
        foreach (float dx in new[] { -1f, 1f })
        {
            mb.Box(top + new Vector3(dx * size * 0.66f, 0.35f, 0), new Vector3(size * 0.3f, 0.1f, size * 0.3f));
            mb.Box(top + new Vector3(0, 0.35f, dx * size * 0.66f), new Vector3(size * 0.3f, 0.1f, size * 0.3f));
        }
    }

    /// 石灯笼。返回发光的那一格（灯室）的中心。
    public static Vector3 StoneLantern(MeshBuilder stone, MeshBuilder glow, Vector3 at, float scale = 1f)
    {
        float k = scale;
        stone.Lathe(at, new[] { new Vector2(0.34f * k, 0f), new Vector2(0.34f * k, 0.10f * k), new Vector2(0.26f * k, 0.18f * k), new Vector2(0.15f * k, 0.24f * k) }, 6, false, false);
        stone.Lathe(at + Vector3.up * 0.24f * k, new[] { new Vector2(0.11f * k, 0f), new Vector2(0.10f * k, 0.62f * k) }, 12);
        stone.Lathe(at + Vector3.up * 0.86f * k, new[] { new Vector2(0.10f * k, 0f), new Vector2(0.30f * k, 0.10f * k), new Vector2(0.30f * k, 0.16f * k) }, 6, false, true);
        // 灯室：四角四根小柱，中间是发光的纸
        Vector3 c = at + Vector3.up * 1.20f * k;
        float h = 0.36f * k, w = 0.22f * k;
        for (int sx = -1; sx <= 1; sx += 2)
            for (int sz = -1; sz <= 1; sz += 2)
                stone.Box(c + new Vector3(sx * w, 0, sz * w), new Vector3(0.05f * k, h, 0.05f * k));
        stone.Box(c + Vector3.up * (h * 0.5f - 0.015f * k), new Vector3(w * 2.2f, 0.03f * k, w * 2.2f));
        stone.Box(c + Vector3.down * (h * 0.5f - 0.015f * k), new Vector3(w * 2.2f, 0.03f * k, w * 2.2f));
        glow.Box(c, new Vector3(w * 1.82f, h * 0.9f, w * 1.82f));
        // 笠：往外挑、四角微翘的石顶，上面一颗宝珠
        stone.Lathe(at + Vector3.up * 1.38f * k, new[]
        {
            new Vector2(0.44f * k, 0.03f * k), new Vector2(0.42f * k, 0.07f * k), new Vector2(0.20f * k, 0.20f * k), new Vector2(0.08f * k, 0.26f * k), new Vector2(0.06f * k, 0.30f * k),
        }, 6, true, false);
        stone.Lathe(at + Vector3.up * 1.68f * k, new[] { new Vector2(0.001f, 0.18f * k), new Vector2(0.05f * k, 0.14f * k), new Vector2(0.085f * k, 0.07f * k), new Vector2(0.05f * k, 0f) }, 10);
        return c;
    }

    /// 一棵阔叶大树：树干和分枝用圆管，枝头是一簇簇叶片。返回低处枝条的端点（挂红布条用）。
    public static List<Vector3> Tree(MeshBuilder bark, MeshBuilder leaves, Vector3 at, float height, float spread, int seed, Rect[] leafUV)
    {
        var rng = new Rng(seed);
        var hangPoints = new List<Vector3>();
        void Branch(Vector3 from, Vector3 dir, float length, float radius, int depth)
        {
            int seg = depth == 0 ? 8 : 5;
            var path = new List<Vector3> { from };
            Vector3 p = from, d = dir.normalized;
            Vector3 bend = Vector3.Cross(d, rng.InSphere()).normalized;
            for (int i = 1; i <= seg; i++)
            {
                float t = i / (float)seg;
                // 枝条先往外长，再因为自重略微下垂；主干则略微扭一下
                d = (d + bend * 0.10f + Vector3.up * (depth == 0 ? 0.02f : 0.06f * (1f - t) - 0.05f * t)).normalized;
                p += d * length / seg;
                path.Add(p);
            }
            float r0 = radius, r1 = radius * (depth >= 3 ? 0.25f : 0.55f);
            bark.Tube(path, t => Mathf.Lerp(r0, r1, t) * (depth == 0 ? 1f + 0.5f * Mathf.Pow(1f - t, 5f) : 1f), depth == 0 ? 14 : depth == 1 ? 9 : 6, true);
            if (depth >= 2)
            {
                // 枝头的叶簇
                // 叶片要小、要密才像真的；低于人头顶的不长，免得贴到眼前露出是一张张卡片
                int cards = depth == 2 ? 26 : 58;
                for (int i = 0; i < cards; i++)
                {
                    Vector3 c = Vector3.Lerp(path[seg / 2], path[seg], rng.Next()) + rng.InSphere() * (0.55f + 0.25f * depth);
                    if (c.y < at.y + 2.75f) continue;
                    float size = rng.Range(0.21f, 0.36f);
                    Vector3 right = Vector3.Cross(rng.InSphere() + Vector3.up * 0.4f, Vector3.up + rng.InSphere() * 0.8f).normalized;
                    Vector3 up = Vector3.Cross(right, (rng.InSphere() + Vector3.forward * 0.2f).normalized).normalized;
                    Vector3 crown = at + Vector3.up * height * 0.62f;
                    leaves.Card(c, right * size, up * size, leafUV[rng.Int(leafUV.Length)], 0.5f, 1f, ((c - crown).normalized + Vector3.up * 0.6f).normalized);
                }
            }
            if (depth == 2 && p.y < at.y + height * 0.62f && p.y > at.y + 2.1f) hangPoints.Add(p);
            if (depth >= 3) return;
            int kids = depth == 0 ? 6 : depth == 1 ? 4 : 3;
            for (int i = 0; i < kids; i++)
            {
                float t = depth == 0 ? Mathf.Lerp(0.42f, 1f, (i + rng.Next() * 0.6f) / kids) : rng.Range(0.35f, 1f);
                Vector3 start = path[Mathf.Clamp(Mathf.RoundToInt(t * seg), 1, seg)];
                float ang = (i / (float)kids + rng.Range(-0.08f, 0.08f)) * Mathf.PI * 2f;
                Vector3 outward = new Vector3(Mathf.Cos(ang), 0, Mathf.Sin(ang));
                Vector3 nd = depth == 0 ? (outward * rng.Range(0.75f, 1.1f) + Vector3.up * rng.Range(0.35f, 0.8f)) : (d * 0.6f + outward * 0.7f + Vector3.up * rng.Range(-0.05f, 0.4f));
                float nl = depth == 0 ? spread * rng.Range(0.55f, 0.85f) : length * rng.Range(0.5f, 0.72f);
                Branch(start, nd, nl, Mathf.Lerp(r0, r1, t) * (depth == 0 ? 0.52f : 0.6f), depth + 1);
            }
        }
        Branch(at, Vector3.up + rng.InSphere() * 0.06f, height * 0.62f, height * 0.045f, 0);
        return hangPoints;
    }

    // ───────── 代码画的贴图 ─────────

    static Texture2D SaveTexture(string name, int w, int h, Func<float, float, Color> f)
    {
        var tex = new Texture2D(w, h, TextureFormat.RGBA32, false);
        var px = new Color[w * h];
        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
                px[y * w + x] = f((x + 0.5f) / w, (y + 0.5f) / h);
        tex.SetPixels(px);
        string path = $"Assets/Textures/{name}.png";
        Directory.CreateDirectory("Assets/Textures");
        File.WriteAllBytes(path, tex.EncodeToPNG());
        UnityEngine.Object.DestroyImmediate(tex);
        AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate);
        return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
    }

    /// 叶片图集：2×2 四格，每格一小簇叶子，背景透明
    public static Texture2D LeafAtlas(Color a, Color b, string name = "gen_leaves_color")
    {
        var rng = new Rng(11);
        const int cells = 2, perCell = 70;
        var leaves = new List<(Vector2 c, float ang, float len, float wid, Color col)>();
        for (int cy = 0; cy < cells; cy++)
            for (int cx = 0; cx < cells; cx++)
                for (int i = 0; i < perCell; i++)
                {
                    var center = new Vector2((cx + rng.Range(0.24f, 0.76f)) / cells, (cy + rng.Range(0.24f, 0.76f)) / cells);
                    var col = Color.Lerp(a, b, rng.Next());
                    col *= rng.Range(0.72f, 1.12f);
                    leaves.Add((center, rng.Range(0, Mathf.PI * 2f), rng.Range(0.030f, 0.046f), rng.Range(0.36f, 0.5f), col));
                }
        return SaveTexture(name, 1024, 1024, (u, v) =>
        {
            Color result = new Color(a.r * 0.6f, a.g * 0.6f, a.b * 0.6f, 0);
            foreach (var l in leaves)
            {
                Vector2 d = new Vector2(u, v) - l.c;
                if (Mathf.Abs(d.x) > 0.05f || Mathf.Abs(d.y) > 0.05f) continue;
                float cs = Mathf.Cos(l.ang), sn = Mathf.Sin(l.ang);
                float along = (d.x * cs + d.y * sn) / l.len, across = (-d.x * sn + d.y * cs) / (l.len * l.wid);
                if (along < -1f || along > 1f) continue;
                // 叶形：中间宽，叶尖收尖
                float t = (along + 1f) * 0.5f;
                float half = Mathf.Pow(Mathf.Sin(Mathf.PI * Mathf.Pow(t, 0.8f)), 0.9f);
                if (Mathf.Abs(across) > half) continue;
                float vein = Mathf.Exp(-across * across * 40f) * 0.10f;
                float shade = 0.82f + 0.18f * (1f - Mathf.Abs(across) / Mathf.Max(half, 0.01f));
                Color c = l.col * shade + new Color(vein * 0.5f, vein, vein * 0.3f, 0);
                c.a = 1;
                result = c;
            }
            return result;
        });
    }

    /// 木格窗：深色的木格，后面是透着暖光的纸
    public static Texture2D LatticeTexture()
    {
        return SaveTexture("gen_lattice_color", 512, 512, (u, v) =>
        {
            float gu = Mathf.Abs((u * 6f) % 1f - 0.5f), gv = Mathf.Abs((v * 8f) % 1f - 0.5f);
            bool frame = u < 0.035f || u > 0.965f || v < 0.03f || v > 0.97f;
            bool bar = gu > 0.42f || gv > 0.43f;
            // 每隔一格加一条斜向的小格，做成传统的菱花感觉
            float du = (u * 6f) % 1f, dv = (v * 8f) % 1f;
            bool diag = Mathf.Abs(du - dv) < 0.05f || Mathf.Abs(du + dv - 1f) < 0.05f;
            if (frame || bar || (diag && v > 0.36f)) return new Color(0.13f, 0.06f, 0.04f, 1);
            if (v < 0.34f) return new Color(0.20f, 0.09f, 0.06f, 1); // 下半截是实木裙板
            float paper = 0.86f + 0.10f * Mathf.PerlinNoise(u * 30f, v * 30f);
            return new Color(0.98f * paper, 0.86f * paper, 0.62f * paper, 1);
        });
    }

    /// 窗格的发光图：只有纸透光
    public static Texture2D LatticeEmission()
    {
        return SaveTexture("gen_lattice_emit", 512, 512, (u, v) =>
        {
            float gu = Mathf.Abs((u * 6f) % 1f - 0.5f), gv = Mathf.Abs((v * 8f) % 1f - 0.5f);
            bool frame = u < 0.035f || u > 0.965f || v < 0.03f || v > 0.97f;
            float du = (u * 6f) % 1f, dv = (v * 8f) % 1f;
            bool diag = Mathf.Abs(du - dv) < 0.05f || Mathf.Abs(du + dv - 1f) < 0.05f;
            if (frame || gu > 0.42f || gv > 0.43f || (diag && v > 0.36f) || v < 0.34f) return Color.black;
            float glow = 0.55f + 0.45f * Mathf.PerlinNoise(u * 3f + 5f, v * 2f);
            return new Color(glow, glow * 0.78f, glow * 0.45f, 1);
        });
    }

    public static Texture2D StreakTexture() => SaveTexture("gen_streak_mask", 16, 128, (u, v) =>
    {
        float a = Mathf.Exp(-Mathf.Pow((u - 0.5f) * 5f, 2f)) * Mathf.Pow(Mathf.Sin(v * Mathf.PI), 0.6f);
        return new Color(1, 1, 1, a);
    });

    public static Texture2D DotTexture() => SaveTexture("gen_dot_mask", 64, 64, (u, v) =>
    {
        float d = Vector2.Distance(new Vector2(u, v), new Vector2(0.5f, 0.5f)) * 2f;
        return new Color(1, 1, 1, Mathf.Clamp01(1f - d) * Mathf.Clamp01(1.6f - d * 1.6f));
    });
}
