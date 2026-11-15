using System;
using System.Collections.Generic;
using UnityEngine;
using Yuanjing;

/// 石头建筑的构件：圆拱和尖拱、两坡屋顶、柏树、彩色玻璃的图案。教堂用，远山两座殿共用。
public static partial class SanctuaryBuild
{
    /// 四周的远山。seed 不同，山的轮廓就不同。
    static void BuildMountains(Transform world, Material mountain, float seed)
    {
        var hills = new MeshBuilder();
        hills.Surface((u, v) =>
        {
            float x = Mathf.Lerp(-190f, 190f, u), z = Mathf.Lerp(34f, 150f, v);
            float ridge = Mathf.Sin(v * Mathf.PI);
            float n = Mathf.PerlinNoise(u * 3.1f + 3f + seed, v * 2.2f) * 0.6f + Mathf.PerlinNoise(u * 9f, v * 7f + 2f) * 0.25f + Mathf.PerlinNoise(u * 23f, v * 19f) * 0.08f;
            return new Vector3(x, -2f + ridge * (14f + 52f * n) * Mathf.Lerp(0.45f, 1.25f, v), z);
        }, 80, 30, new Vector2(380, 120), Vector3.up);
        hills.Surface((u, v) =>
        {
            float x = Mathf.Lerp(-150f, -26f, u), z = Mathf.Lerp(-60f, 90f, v);
            float n = Mathf.PerlinNoise(u * 4f + 9f + seed, v * 5f) * 0.7f + Mathf.PerlinNoise(u * 13f, v * 11f) * 0.2f;
            return new Vector3(x, -2f + Mathf.Sin(u * Mathf.PI) * (8f + 34f * n), z);
        }, 30, 40, new Vector2(120, 150), Vector3.up);
        hills.Surface((u, v) =>
        {
            float x = Mathf.Lerp(26f, 150f, u), z = Mathf.Lerp(-60f, 90f, v);
            float n = Mathf.PerlinNoise(u * 4f + 4f + seed, v * 5f + 6f) * 0.7f + Mathf.PerlinNoise(u * 13f + 3f, v * 11f) * 0.2f;
            return new Vector3(x, -2f + Mathf.Sin(u * Mathf.PI) * (8f + 30f * n), z);
        }, 30, 40, new Vector2(120, 150), Vector3.up);
        Add("Mountains", hills, mountain, world, false);

    }

    /// 拱的轮廓上的一点。t 从 0（左拱脚）到 1（右拱脚），a 是半宽；返回相对起拱线中点的位置。
    /// pointed：尖拱（左右各一段圆弧，圆心在对面的拱脚），否则是半圆拱。
    public static Vector2 ArchPoint(float t, float a, bool pointed)
    {
        if (!pointed)
        {
            float th = Mathf.PI * (1f - t);
            return new Vector2(a * Mathf.Cos(th), a * Mathf.Sin(th));
        }
        if (t <= 0.5f)
        {
            float th = Mathf.Lerp(Mathf.PI, Mathf.PI * 2f / 3f, t * 2f);
            return new Vector2(a + 2f * a * Mathf.Cos(th), 2f * a * Mathf.Sin(th));
        }
        else
        {
            float th = Mathf.Lerp(Mathf.PI / 3f, 0f, (t - 0.5f) * 2f);
            return new Vector2(-a + 2f * a * Mathf.Cos(th), 2f * a * Mathf.Sin(th));
        }
    }

    /// 一段开着拱洞的墙。墙面朝前后（z 方向），从 x0 到 x1、y0 到 y1；拱洞中心在 cx，半宽 a，spring 是起拱线的高度。
    /// 要朝别的方向，先设 mb.m。
    public static void ArchWall(MeshBuilder mb, float x0, float x1, float y0, float y1, float cx, float a, float spring, bool pointed, float z, float thick)
    {
        float zf = z - thick * 0.5f, zb = z + thick * 0.5f;
        if (cx - a > x0 + 0.001f) mb.Box(new Vector3((x0 + cx - a) * 0.5f, (y0 + y1) * 0.5f, z), new Vector3(cx - a - x0, y1 - y0, thick));
        if (x1 > cx + a + 0.001f) mb.Box(new Vector3((cx + a + x1) * 0.5f, (y0 + y1) * 0.5f, z), new Vector3(x1 - cx - a, y1 - y0, thick));
        const int seg = 20;
        for (int i = 0; i < seg; i++)
        {
            Vector2 p = ArchPoint(i / (float)seg, a, pointed), q = ArchPoint((i + 1) / (float)seg, a, pointed);
            Vector3 pf = new Vector3(cx + p.x, spring + p.y, zf), qf = new Vector3(cx + q.x, spring + q.y, zf);
            Vector3 pb = new Vector3(pf.x, pf.y, zb), qb = new Vector3(qf.x, qf.y, zb);
            // 拱上方的墙面，前后两面
            mb.Quad(pf, qf, new Vector3(qf.x, y1, zf), new Vector3(pf.x, y1, zf), Vector3.back);
            mb.Quad(pb, qb, new Vector3(qb.x, y1, zb), new Vector3(pb.x, y1, zb), Vector3.forward);
            // 拱的底面，朝着拱心
            Vector2 mid = (p + q) * 0.5f;
            mb.Quad(pf, qf, qb, pb, new Vector3(-mid.x, -mid.y - 0.02f, 0));
        }
        mb.Quad(new Vector3(cx - a, y1, zf), new Vector3(cx + a, y1, zf), new Vector3(cx + a, y1, zb), new Vector3(cx - a, y1, zb), Vector3.up);
    }

    /// 一块拱形的板（门扇）：从 y0 往上到拱顶，一条一条竖着拼起来
    public static void ArchPanel(MeshBuilder mb, float cx, float y0, float a, float spring, bool pointed, float z, Vector3 facing)
    {
        const int seg = 20;
        for (int i = 0; i < seg; i++)
        {
            Vector2 p = ArchPoint(i / (float)seg, a, pointed), q = ArchPoint((i + 1) / (float)seg, a, pointed);
            mb.Quad(new Vector3(cx + p.x, y0, z), new Vector3(cx + q.x, y0, z), new Vector3(cx + q.x, spring + q.y, z), new Vector3(cx + p.x, spring + p.y, z), facing);
        }
    }

    /// 沿着拱洞边缘走一圈的线（左边立柱、拱、右边立柱），给拱边的石线脚用
    public static List<Vector3> ArchPath(float cx, float y0, float a, float spring, bool pointed, float z, int seg = 24)
    {
        var path = new List<Vector3> { new Vector3(cx - a, y0, z) };
        for (int i = 0; i <= seg; i++)
        {
            Vector2 p = ArchPoint(i / (float)seg, a, pointed);
            path.Add(new Vector3(cx + p.x, spring + p.y, z));
        }
        path.Add(new Vector3(cx + a, y0, z));
        return path;
    }

    /// 两坡屋顶。屋脊沿 z 方向；eave 是檐口那一圈的中心，span 是跨度（x），length 是屋脊长，rise 是檐口到屋脊的高。
    /// 屋脊要沿别的方向，先设 mb.m。
    public static void GableRoof(MeshBuilder mb, MeshBuilder trim, Vector3 eave, float span, float length, float rise, float overhang)
    {
        float half = span * 0.5f, drop = overhang * rise / half, z0 = eave.z - length * 0.5f, z1 = eave.z + length * 0.5f;
        const float thick = 0.16f;
        foreach (float sx in new[] { -1f, 1f })
        {
            Vector3 e0 = eave + new Vector3(sx * (half + overhang), -drop, z0 - eave.z), e1 = eave + new Vector3(sx * (half + overhang), -drop, z1 - eave.z);
            Vector3 r0 = eave + new Vector3(0, rise, z0 - eave.z), r1 = eave + new Vector3(0, rise, z1 - eave.z);
            Vector3 outward = new Vector3(sx * rise, half, 0).normalized;
            mb.Quad(e0, e1, r1, r0, outward);
            Vector3 d = Vector3.down * thick;
            trim.Quad(e0 + d, e1 + d, r1 + d, r0 + d, -outward);
            trim.Quad(e0, e1, e1 + d, e0 + d, new Vector3(sx, 0, 0));
            // 两头的封檐板
            trim.Quad(e0, r0, r0 + d, e0 + d, Vector3.back);
            trim.Quad(e1, r1, r1 + d, e1 + d, Vector3.forward);
        }
        trim.Box(eave + new Vector3(0, rise + 0.02f, 0), new Vector3(0.34f, 0.14f, length + 0.1f));
    }

    /// 一棵柏树：细高的纺锤形，叶片一簇簇朝上
    public static void Cypress(MeshBuilder bark, MeshBuilder leaves, Vector3 at, float height, float radius, int seed, Rect[] leafUV)
    {
        var rng = new Rng(seed);
        bark.Tube(new[] { at, at + Vector3.up * height * 0.45f, at + Vector3.up * height * 0.9f }, t => Mathf.Lerp(0.14f, 0.03f, t), 8, true);
        int cards = (int)(height * 85);
        for (int i = 0; i < cards; i++)
        {
            float t = Mathf.Pow(rng.Next(), 0.85f);
            float h = Mathf.Lerp(0.45f, height, t);
            float r = radius * Mathf.Pow(Mathf.Sin(Mathf.PI * Mathf.Pow(Mathf.Clamp01(t * 0.97f + 0.02f), 0.5f)), 0.8f);
            float ang = rng.Range(0, Mathf.PI * 2f);
            Vector3 dir = new Vector3(Mathf.Cos(ang), 0, Mathf.Sin(ang));
            Vector3 c = at + Vector3.up * h + dir * r * rng.Range(0.45f, 1f);
            Vector3 up = (Vector3.up + dir * 0.35f + rng.InSphere() * 0.25f).normalized;
            Vector3 right = Vector3.Cross(up, dir + rng.InSphere() * 0.5f).normalized;
            float size = rng.Range(0.26f, 0.42f) * Mathf.Lerp(1f, 0.6f, t);
            leaves.Card(c, right * size, up * size * 1.25f, leafUV[rng.Int(leafUV.Length)], 0.25f, 0.6f, (dir + Vector3.up * 0.5f).normalized);
        }
    }

    // ───────── 彩色玻璃 ─────────

    static readonly Color Ruby = new Color(0.78f, 0.07f, 0.10f), Sapphire = new Color(0.08f, 0.20f, 0.72f), Amber = new Color(0.96f, 0.68f, 0.16f),
        Emerald = new Color(0.10f, 0.50f, 0.26f), Violet = new Color(0.42f, 0.14f, 0.58f), Lead = new Color(0.035f, 0.035f, 0.04f);

    static float Hash(float x, float y) => Mathf.Repeat(Mathf.Sin(x * 127.1f + y * 311.7f) * 43758.5453f, 1f);

    /// 一小块玻璃自己的深浅：每块略有不同，中间比边上亮
    static Color Pane(Color c, float cellX, float cellY) => c * (0.72f + 0.5f * Hash(cellX, cellY));

    /// 玫瑰花窗：中心一个圆，十二片花瓣，外圈十二个小圆窗。圆外透明。
    public static Texture2D RoseTexture() => SaveTexture("gen_rose_color", 1024, 1024, (u, v) =>
    {
        float x = (u - 0.5f) * 2f, y = (v - 0.5f) * 2f;
        float r = Mathf.Sqrt(x * x + y * y);
        if (r > 1f) return new Color(0, 0, 0, 0);
        float ang = Mathf.Atan2(y, x) + Mathf.PI;
        const int n = 12;
        float sector = ang / (Mathf.PI * 2f) * n;
        int k = Mathf.Min((int)sector, n - 1);
        float f = sector - k;
        Color c;
        if (r > 0.94f || (r > 0.615f && r < 0.655f) || (r > 0.165f && r < 0.195f)) c = Lead;
        else if (r <= 0.165f)
        {
            // 中心：金色的小花
            float petal = Mathf.Abs(Mathf.Sin(ang * 3f));
            c = r < 0.06f ? Pane(Ruby, 1, 1) : r < 0.07f ? Lead : Pane(petal > 0.5f ? Amber : Sapphire, Mathf.Floor(ang * 6f / Mathf.PI), 2);
        }
        else if (r < 0.615f)
        {
            // 花瓣：每个扇区里一片水滴形
            if (Mathf.Abs(f - 0.5f) > 0.455f) c = Lead;
            else
            {
                float t = (r - 0.195f) / 0.42f;
                float half = 0.40f * Mathf.Pow(Mathf.Sin(Mathf.PI * Mathf.Pow(t, 0.7f)), 0.8f);
                float d = Mathf.Abs(f - 0.5f);
                if (Mathf.Abs(d - half) < 0.03f) c = Lead;
                else if (Mathf.Abs(t * 7f - Mathf.Round(t * 7f)) < 0.045f) c = Lead;
                else if (d < half) c = Pane(k % 2 == 0 ? Ruby : Sapphire, k, Mathf.Floor(t * 7f + 0.5f)) * (d < half * 0.35f ? 1.25f : 1f);
                else c = Pane(k % 2 == 0 ? Sapphire : Violet, k + 20 + (f < 0.5f ? 0 : 50), Mathf.Floor(t * 7f + 0.5f)) * 0.8f;
            }
        }
        else
        {
            // 外圈：每个扇区一个小圆窗
            float ca = (k + 0.5f) / n * Mathf.PI * 2f - Mathf.PI;
            float dx = x - Mathf.Cos(ca) * 0.795f, dy = y - Mathf.Sin(ca) * 0.795f;
            float d = Mathf.Sqrt(dx * dx + dy * dy);
            if (d < 0.105f) c = d < 0.04f ? Pane(Ruby, k, 9) : d < 0.05f ? Lead : Pane(k % 2 == 0 ? Amber : Emerald, k, 7);
            else if (d < 0.125f || Mathf.Abs(f - 0.5f) > 0.47f) c = Lead;
            else c = Pane(Sapphire, k, 5 + Mathf.Floor(f * 2f));
        }
        c.a = 1;
        return c;
    });

    /// 尖拱长窗：菱形的小块玻璃，一圈红边。图是 1:3 的，拱外透明。
    public static Texture2D LancetTexture() => SaveTexture("gen_lancet_color", 512, 1536, (u, v) =>
    {
        // 换成米：宽 1，高 3，拱脚在 y = 3 - 0.866
        float x = u - 0.5f, y = v * 3f;
        const float a = 0.5f, spring = 3f - 0.866f;
        float edge;
        if (y < spring) edge = a - Mathf.Abs(x);
        else
        {
            float cx = x < 0 ? a : -a;
            edge = 2f * a - Mathf.Sqrt((x - cx) * (x - cx) + (y - spring) * (y - spring));
        }
        if (edge < 0 || y < 0.01f) return new Color(0, 0, 0, 0);
        Color c;
        if (edge < 0.03f) c = Lead;
        else if (edge < 0.10f) c = Pane(Ruby, Mathf.Floor(y * 5f), x < 0 ? 0 : 1);
        else if (edge < 0.12f) c = Lead;
        else
        {
            // 斜着的菱形格
            float p = (x + y) * 11f, q = (y - x) * 11f;
            float fp = p - Mathf.Floor(p), fq = q - Mathf.Floor(q);
            if (fp < 0.09f || fq < 0.09f) c = Lead;
            else
            {
                float pick = Hash(Mathf.Floor(p), Mathf.Floor(q));
                // 中间一竖列用金色的，像一条光带
                Color baseC = Mathf.Abs(x) < 0.07f ? (pick < 0.7f ? Amber : Ruby) : pick < 0.68f ? Sapphire : pick < 0.80f ? Violet : pick < 0.92f ? Emerald : Ruby;
                c = Pane(baseC, Mathf.Floor(p), Mathf.Floor(q));
            }
        }
        c.a = 1;
        return c;
    });

    /// 彩色玻璃的材质：白天从外面看是暗的，夜里从里面透出光（亮度由 TimeWeather 调）
    static Material GlassMaterial(string name, Texture2D map)
    {
        var m = Emissive(name, new Color(0.11f, 0.11f, 0.12f), map);
        m.SetFloat("_Roughness", 0.25f);
        m.SetFloat("_AlphaClip", 1f);
        m.SetFloat("_Cutoff", 0.5f);
        m.EnableKeyword("_ALPHATEST_ON");
        m.renderQueue = (int)UnityEngine.Rendering.RenderQueue.AlphaTest;
        return m;
    }
}
