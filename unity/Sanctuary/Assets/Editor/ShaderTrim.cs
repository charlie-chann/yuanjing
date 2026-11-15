using System.Collections.Generic;
using UnityEditor.Build;
using UnityEditor.Rendering;
using UnityEngine;
using UnityEngine.Rendering;

/// 渲染管线自带的「裁掉用不到的着色器版本」被我们关了（它会把运行时真要用的版本也裁掉，画面乱跳，见 docs/08），
/// 关掉以后管线里所有着色器都会全量编译，其中几个我们根本不用的有上万个版本，打包要多等一个多小时。
/// 这里把确定用不到的整个丢掉：地形、延迟渲染、XR。
class ShaderTrim : IPreprocessShaders
{
    public int callbackOrder => 1000;

    static readonly string[] Unused = { "TerrainEngine", "Terrain/", "ClusterDeferred", "/XR/", "Deferred", "HDRDebugView", "VrsVisualization", "LensFlare", "PaniniProjection", "DepthOfField", "CameraMotionBlur" };

    static List<ShaderKeyword> dropped;

    public void OnProcessShader(Shader shader, ShaderSnippetData snippet, IList<ShaderCompilerData> data)
    {
        foreach (string u in Unused)
            if (shader.name.Contains(u))
            {
                data.Clear();
                return;
            }
        // 只在 XR 里用的那一遍
        if (snippet.passName != null && snippet.passName.Contains("XR"))
        {
            data.Clear();
            return;
        }
        // 后期合成：我们只用辉光（高质量）、ACES 色调映射、调色、暗角。带下面这些开关的版本用不到
        if (shader.name.Contains("UberPost") || shader.name.Contains("FinalPost"))
        {
            if (dropped == null)
            {
                dropped = new List<ShaderKeyword>();
                foreach (string k in new[] { "_FILM_GRAIN", "_DITHERING", "_CHROMATIC_ABERRATION", "_DISTORTION", "_TONEMAP_NEUTRAL", "_BLOOM_LQ", "_BLOOM_LQ_DIRT", "_BLOOM_HQ_DIRT", "_GAMMA_20", "SCREEN_COORD_OVERRIDE", "_ENABLE_ALPHA_OUTPUT" })
                    dropped.Add(new ShaderKeyword(k));
            }
            for (int i = data.Count - 1; i >= 0; i--)
                foreach (var k in dropped)
                    if (data[i].shaderKeywordSet.IsEnabled(k))
                    {
                        data.RemoveAt(i);
                        break;
                    }
        }
    }
}
