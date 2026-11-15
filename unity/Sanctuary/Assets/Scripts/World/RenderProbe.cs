using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Yuanjing
{
    /// 排查「画面闪」的工具，只有带环境变量 YJ_PROBE 启动才运行（模拟器：SIMCTL_CHILD_YJ_PROBE=1 xcrun simctl launch …）。
    /// 人站着不动，逐项关掉渲染效果，每种设置下连续抓相邻两帧比差异（越小越稳），结果写进日志。
    /// 编辑器里出单张图看不出逐帧的闪，必须在真机或模拟器上这样量。
    public class RenderProbe : MonoBehaviour
    {
        static readonly string[] Modes =
        {
            "基准", "静止", "静止 无抗锯齿", "静止 无抗锯齿 关遮蔽", "静止 无抗锯齿 关遮蔽 关阴影", "静止 SMAA",
            "无抗锯齿", "SMAA", "关遮蔽", "关阴影", "关辉光", "关粒子", "关人", "SMAA 关遮蔽", "SMAA 关遮蔽 关粒子 关人",
        };

        IEnumerator Start()
        {
            yield return new WaitForSecondsRealtime(20f);
            if (System.Environment.GetEnvironmentVariable("YJ_PROBE") == "5")
            {
                yield return Lamps();
                yield break;
            }
            if (System.Environment.GetEnvironmentVariable("YJ_PROBE") == "4")
            {
                yield return Bind();
                yield break;
            }
            if (System.Environment.GetEnvironmentVariable("YJ_PROBE") == "3")
            {
                yield return Who();
                yield break;
            }
            if (System.Environment.GetEnvironmentVariable("YJ_PROBE") == "2")
            {
                yield return Slow();
                yield break;
            }
            var tw = TimeWeather.Instance;
            var cd = Camera.main.GetUniversalAdditionalCameraData();
            var aaWas = cd.antialiasing;
            Bloom bloom = null;
            if (tw.volume != null) tw.volume.sharedProfile.TryGet(out bloom);
            ScriptableRendererFeature ssao = null;
            foreach (var f in Resources.FindObjectsOfTypeAll<ScriptableRendererFeature>()) if (f.name == "SSAO") ssao = f;
            Debug.Log($"[yuanjing] 探测开始 遮蔽={(ssao != null)} 辉光={(bloom != null)} 抗锯齿={cd.antialiasing} 屏幕={Screen.width}x{Screen.height}");
            foreach (var (t, w) in new[] { (DayTime.Night, Weather.Rain), (DayTime.Day, Weather.Clear) })
            {
                tw.ApplyImmediate(t, w);
                yield return new WaitForSecondsRealtime(3f);
                foreach (string mode in Modes)
                {
                    Time.timeScale = mode.Contains("静止") ? 0 : 1;
                    cd.antialiasing = mode.Contains("无抗锯齿") ? AntialiasingMode.None : mode.Contains("SMAA") ? AntialiasingMode.SubpixelMorphologicalAntiAliasing : aaWas;
                    if (ssao != null) ssao.SetActive(!mode.Contains("关遮蔽"));
                    tw.sun.shadows = mode.Contains("关阴影") ? LightShadows.None : LightShadows.Soft;
                    if (bloom != null) bloom.active = !mode.Contains("关辉光");
                    foreach (var r in FindObjectsByType<ParticleSystemRenderer>(FindObjectsInactive.Include, FindObjectsSortMode.None)) r.enabled = !mode.Contains("关粒子");
                    foreach (var f in FindObjectsByType<Folk>(FindObjectsInactive.Include, FindObjectsSortMode.None)) f.model.gameObject.SetActive(!mode.Contains("关人"));
                    yield return new WaitForSecondsRealtime(1.2f);
                    yield return Measure($"{t}/{w} {mode}");
                }
            }
            Time.timeScale = 1;
            cd.antialiasing = aaWas;
            if (ssao != null) ssao.SetActive(true);
            tw.sun.shadows = LightShadows.Soft;
            if (bloom != null) bloom.active = true;
            Debug.Log("[yuanjing] 探测结束");
        }

        static string State()
        {
            var sun = TimeWeather.Instance.sun;
            return $"主光色={Shader.GetGlobalVector("_MainLightColor"):F2} 主光向={Shader.GetGlobalVector("_MainLightPosition"):F2} 附加灯数={Shader.GetGlobalVector("_AdditionalLightsCount").x} " +
                   $"阴影参数={Shader.GetGlobalVector("_MainLightShadowParams"):F2} 级联开={Shader.IsKeywordEnabled("_MAIN_LIGHT_SHADOWS_CASCADE")} 单层开={Shader.IsKeywordEnabled("_MAIN_LIGHT_SHADOWS")} 附加开={Shader.IsKeywordEnabled("_ADDITIONAL_LIGHTS")} " +
                   $"遮蔽开={Shader.IsKeywordEnabled("_SCREEN_SPACE_OCCLUSION")} 太阳={sun.intensity:F2}/{sun.enabled}/{sun.shadows} 太阳是场景主光={(RenderSettings.sun == sun)} 湿={Shader.GetGlobalFloat("_YJWet"):F2} 环境={RenderSettings.ambientSkyColor:F2}";
        }

        /// 查「灯光忽有忽无、窗格变色」：不改天色天气（用应用自己设的），每个阶段 60 秒，
        /// 量右侧地面的橙色程度（灯笼照没照到）和窗格的橙色程度，跳变时把灯的状态打出来
        IEnumerator Lamps()
        {
            var tw = TimeWeather.Instance;
            ScriptableRendererFeature ssao = null;
            foreach (var f in Resources.FindObjectsOfTypeAll<ScriptableRendererFeature>()) if (f.name == "SSAO") ssao = f;
            string[] phases = { "基准", "关辉光", "防无效数", "辉光限幅", "关后期", "人不显示", "基准" };
            Light bounce = tw.bounce;
            var cd = Camera.main.GetUniversalAdditionalCameraData();
            Bloom bloom = null;
            if (tw.volume != null) tw.volume.sharedProfile.TryGet(out bloom);
            float clampWas = bloom != null ? bloom.clamp.value : 0;
            foreach (string ph in phases)
            {
                GraphicsSettings.useScriptableRenderPipelineBatching = ph != "关合批";
                if (ssao != null) ssao.SetActive(ph != "关遮蔽");
                tw.sun.shadows = ph == "关阴影" ? LightShadows.None : LightShadows.Soft;
                foreach (var f in FindObjectsByType<Folk>(FindObjectsInactive.Include, FindObjectsSortMode.None)) f.model.gameObject.SetActive(ph != "人不显示");
                foreach (var r in FindObjectsByType<ParticleSystemRenderer>(FindObjectsInactive.Include, FindObjectsSortMode.None)) r.enabled = ph != "关粒子";
                if (bounce != null) bounce.enabled = ph != "关补光";
                if (bloom != null)
                {
                    bloom.active = ph != "关辉光";
                    bloom.clamp.overrideState = true;
                    bloom.clamp.value = ph == "辉光限幅" ? 2.5f : clampWas;
                }
                cd.stopNaN = ph == "防无效数";
                cd.renderPostProcessing = ph != "关后期";
                yield return new WaitForSecondsRealtime(1.5f);
                var g = new StringBuilder();
                var l = new StringBuilder();
                float lastG = -999, lastL = -999;
                int flipG = 0, flipL = 0, logged = 0;
                for (int i = 0; i < 600; i++)
                {
                    yield return new WaitForSecondsRealtime(0.08f);
                    yield return new WaitForEndOfFrame();
                    var tex = ScreenCapture.CaptureScreenshotAsTexture();
                    var px = tex.GetPixels32();
                    int W = tex.width, H = tex.height;
                    Destroy(tex);
                    // 截图的原点在左下角
                    float Orange(float x0, float x1, float y0, float y1)
                    {
                        double s2 = 0;
                        int c = 0;
                        for (int y = (int)(H * y0); y < (int)(H * y1); y += 4)
                            for (int x = (int)(W * x0); x < (int)(W * x1); x += 4)
                            {
                                var p = px[y * W + x];
                                s2 += p.r - p.b;
                                c++;
                            }
                        return (float)(s2 / c);
                    }
                    float vg = Orange(0.70f, 0.95f, 0.50f, 0.54f);
                    float vl = Orange(0.42f, 0.58f, 0.675f, 0.725f);
                    bool fg = lastG > -900 && Mathf.Abs(vg - lastG) > 6, fl = lastL > -900 && Mathf.Abs(vl - lastL) > 12;
                    if (fg) flipG++;
                    if (fl) flipL++;
                    if ((fg || fl || i == 0) && logged++ < 7)
                        Debug.Log($"[yuanjing] 灯探测 {ph} 第{i}次 地面橙 {lastG:F0}→{vg:F0} 窗格橙 {lastL:F0}→{vl:F0} 帧={Time.frameCount} 附加灯数={Shader.GetGlobalVector("_AdditionalLightsCount").x} {tw.LampDebug()}");
                    lastG = vg;
                    lastL = vl;
                    g.Append((char)('5' + Mathf.Clamp(Mathf.RoundToInt(vg / 8f), -5, 4)));
                    l.Append((char)('0' + Mathf.Clamp(Mathf.RoundToInt(vl / 12f), 0, 9)));
                }
                Debug.Log($"[yuanjing] 灯探测 {ph} 地面跳变 {flipG} 次 {g}");
                Debug.Log($"[yuanjing] 灯探测 {ph} 窗格跳变 {flipL} 次 {l}");
            }
            Debug.Log("[yuanjing] 探测结束");
        }

        /// 对照实验：遮挡高度图三种交给着色器的办法，各看 60 秒里地面整片变暗多少次（袍子隐藏着，这种情况最容易触发）
        IEnumerator Bind()
        {
            var tw = TimeWeather.Instance;
            Camera.main.GetUniversalAdditionalCameraData().antialiasing = AntialiasingMode.SubpixelMorphologicalAntiAliasing;
            tw.ApplyImmediate(DayTime.Night, Weather.Rain);
            foreach (var (label, mode, hideCloth) in new[] { ("只设一次全局（旧）", 0, true), ("每帧重设全局", 1, true), ("设到材质上", 2, true), ("只设一次全局（旧）", 0, true), ("设到材质上", 2, true), ("设到材质上 人都正常", 2, false) })
            {
                TimeWeather.bindMode = mode;
                if (mode < 2)
                    foreach (var m in Resources.FindObjectsOfTypeAll<Material>())
                        if (m.shader != null && m.shader.name.StartsWith("Yuanjing/")) m.SetTexture("_YJHeightMap", null);
                foreach (var f in FindObjectsByType<Folk>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                    foreach (var r in f.model.GetComponentsInChildren<SkinnedMeshRenderer>(true)) r.enabled = !hideCloth || r.name != "Cloth";
                yield return new WaitForSecondsRealtime(1.5f);
                var line = new StringBuilder();
                int dark = 0, flips = 0;
                float last = -1;
                for (int i = 0; i < 600; i++)
                {
                    yield return new WaitForSecondsRealtime(0.08f);
                    yield return new WaitForEndOfFrame();
                    var tex = ScreenCapture.CaptureScreenshotAsTexture();
                    var px = tex.GetPixels32();
                    int W = tex.width, H = tex.height;
                    Destroy(tex);
                    double sum = 0;
                    int c = 0;
                    for (int y = H * 12 / 100; y < H * 34 / 100; y += 6)
                        for (int x = W * 6 / 100; x < W * 32 / 100; x += 6)
                        {
                            var p = px[y * W + x];
                            sum += (p.r * 2 + p.g * 5 + p.b) >> 3;
                            c++;
                        }
                    float v = (float)(sum / c);
                    if (last >= 0 && Mathf.Abs(v - last) > 5) flips++;
                    last = v;
                    if (v < 19) dark++;
                    line.Append(v < 19 ? '#' : '.');
                }
                Debug.Log($"[yuanjing] 绑定实验 {label}：整片变暗 {dark}/600 次采样，跳变 {flips} 次 {line}");
            }
            Debug.Log("[yuanjing] 探测结束");
        }

        /// 查是谁触发了「整片忽明忽暗」：每种设置 40 秒，亮暗一切换就把渲染状态打出来
        IEnumerator Who()
        {
            var tw = TimeWeather.Instance;
            var cd = Camera.main.GetUniversalAdditionalCameraData();
            cd.antialiasing = AntialiasingMode.SubpixelMorphologicalAntiAliasing;
            tw.ApplyImmediate(DayTime.Night, Weather.Rain);
            string[] phases = { "基准", "关合批", "关附加灯", "只藏散步的", "只藏坐着的", "只藏自己", "只藏袍子", "只留袍子", "基准" };
            foreach (string ph in phases)
            {
                GraphicsSettings.useScriptableRenderPipelineBatching = ph != "关合批";
                foreach (var l in FindObjectsByType<Light>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                    if (l != tw.sun) l.gameObject.SetActive(ph != "关附加灯");
                foreach (var f in FindObjectsByType<Folk>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                {
                    bool me = f.controller != null, walker = f.name.StartsWith("Pilgrim_walk");
                    bool hide = (ph == "只藏散步的" && walker) || (ph == "只藏坐着的" && !walker && !me) || (ph == "只藏自己" && me);
                    f.model.gameObject.SetActive(!hide);
                    foreach (var r in f.model.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                        r.enabled = ph == "只藏袍子" ? r.name != "Cloth" : ph == "只留袍子" ? r.name == "Cloth" : true;
                }
                yield return new WaitForSecondsRealtime(1f);
                var line = new StringBuilder();
                float last = -1;
                int flips = 0;
                for (int i = 0; i < 400; i++)
                {
                    yield return new WaitForSecondsRealtime(0.08f);
                    yield return new WaitForEndOfFrame();
                    var tex = ScreenCapture.CaptureScreenshotAsTexture();
                    var px = tex.GetPixels32();
                    int W = tex.width, H = tex.height;
                    Destroy(tex);
                    double sum = 0;
                    int c = 0;
                    for (int y = H * 12 / 100; y < H * 34 / 100; y += 6)
                        for (int x = W * 6 / 100; x < W * 32 / 100; x += 6)
                        {
                            var p = px[y * W + x];
                            sum += (p.r * 2 + p.g * 5 + p.b) >> 3;
                            c++;
                        }
                    float v = (float)(sum / c);
                    if (last < 0) Debug.Log($"[yuanjing] 谁探测 {ph} 起始 亮度={v:F0} {State()}");
                    else if (Mathf.Abs(v - last) > 5 && flips++ < 4)
                    {
                        int vis = 0, moving = 0;
                        foreach (var f in FindObjectsByType<Folk>(FindObjectsSortMode.None))
                        {
                            if (f.Moving) moving++;
                            foreach (var r in f.GetComponentsInChildren<SkinnedMeshRenderer>()) if (r.isVisible) { vis++; break; }
                        }
                        Debug.Log($"[yuanjing] 谁探测 {ph} 第{i}次 亮度 {last:F0}→{v:F0} 看得见的人={vis} 在走的={moving} 镜头={Camera.main.transform.position:F2} {State()}");
                    }
                    last = v;
                    line.Append(v < 19 ? '#' : '.');
                }
                Debug.Log($"[yuanjing] 谁探测 {ph} 时间线 {line}");
            }
            Debug.Log("[yuanjing] 探测结束");
        }

        /// 查「整片忽明忽暗」：每种设置下 20 秒、每秒 10 次量一块没有人的地面的亮度，同时记下有几个人正在拜
        IEnumerator Slow()
        {
            var tw = TimeWeather.Instance;
            var cd = Camera.main.GetUniversalAdditionalCameraData();
            string aa = System.Environment.GetEnvironmentVariable("YJ_AA") ?? "smaa";
            cd.antialiasing = aa == "taa" ? AntialiasingMode.TemporalAntiAliasing : aa == "none" ? AntialiasingMode.None : AntialiasingMode.SubpixelMorphologicalAntiAliasing;
            ScriptableRendererFeature ssao = null;
            foreach (var f in Resources.FindObjectsOfTypeAll<ScriptableRendererFeature>()) if (f.name == "SSAO") ssao = f;
            string[] phases = { "基准", "人不投影", "人不显示", "关遮蔽", "关阴影", "基准" };
            foreach (var (t, w) in new[] { (DayTime.Night, Weather.Rain), (DayTime.Day, Weather.Rain) })
            {
                tw.ApplyImmediate(t, w);
                foreach (string ph in phases)
                {
                    foreach (var f in FindObjectsByType<Folk>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                    {
                        f.model.gameObject.SetActive(ph != "人不显示");
                        foreach (var r in f.GetComponentsInChildren<Renderer>(true))
                            if (!(r is ParticleSystemRenderer) && r.GetComponent<TextMesh>() == null)
                                r.shadowCastingMode = ph == "人不投影" ? ShadowCastingMode.Off : ShadowCastingMode.On;
                    }
                    if (ssao != null) ssao.SetActive(ph != "关遮蔽");
                    tw.sun.shadows = ph == "关阴影" ? LightShadows.None : LightShadows.Soft;
                    yield return new WaitForSecondsRealtime(1f);
                    var series = new StringBuilder();
                    var acts = new StringBuilder();
                    var refl = new StringBuilder();
                    float lo = 999, hi = 0;
                    for (int i = 0; i < 200; i++)
                    {
                        yield return new WaitForSecondsRealtime(0.08f);
                        yield return new WaitForEndOfFrame();
                        var tex = ScreenCapture.CaptureScreenshotAsTexture();
                        var px = tex.GetPixels32();
                        int W = tex.width, H = tex.height;
                        Destroy(tex);
                        double sum = 0;
                        int c = 0;
                        for (int y = H * 12 / 100; y < H * 34 / 100; y += 6)
                            for (int x = W * 6 / 100; x < W * 32 / 100; x += 6)
                            {
                                var p = px[y * W + x];
                                sum += (p.r * 2 + p.g * 5 + p.b) >> 3;
                                c++;
                            }
                        float v = (float)(sum / c);
                        lo = Mathf.Min(lo, v);
                        hi = Mathf.Max(hi, v);
                        series.Append(Mathf.RoundToInt(v)).Append(' ');
                        int bowing = 0;
                        foreach (var f in FindObjectsByType<Folk>(FindObjectsSortMode.None))
                            if (f.pose == Folk.Pose.Bow || f.pose == Folk.Pose.Gassho || f.pose == Folk.Pose.Kneel || f.pose == Folk.Pose.KneelBow) bowing++;
                        acts.Append(bowing);
                        var rt = ReflectionProbe.defaultTexture;
                        refl.Append(rt == null ? '-' : rt.width > 16 ? 'R' : 'r');
                    }
                    Debug.Log($"[yuanjing] 慢探测 {t}/{w} {aa} {ph} 亮度 {lo:F0}..{hi:F0}：{series}");
                    Debug.Log($"[yuanjing] 慢探测 {t}/{w} {aa} {ph} 在拜的人数：{acts}");
                    Debug.Log($"[yuanjing] 慢探测 {t}/{w} {aa} {ph} 反射贴图：{refl}");
                }
            }
            Debug.Log("[yuanjing] 探测结束");
        }

        /// 相邻两帧的差异（亮度 0..255）：地面、建筑、屋顶天空三块分别算；另外每 0.25 秒记一次地面亮度，看有没有整片忽明忽暗
        IEnumerator Measure(string label)
        {
            var sum = new double[3];
            var big = new double[3];
            var n = new double[3];
            byte[] prev = null;
            int w = 0, h = 0;
            const int step = 3;
            for (int i = 0; i <= 10; i++)
            {
                yield return new WaitForEndOfFrame();
                var tex = ScreenCapture.CaptureScreenshotAsTexture();
                var px = tex.GetPixels32();
                w = tex.width;
                h = tex.height;
                Destroy(tex);
                int cols = w / step, rows = h / step;
                var lum = new byte[cols * rows];
                for (int y = 0; y < rows; y++)
                    for (int x = 0; x < cols; x++)
                    {
                        var c = px[y * step * w + x * step];
                        lum[y * cols + x] = (byte)((c.r * 2 + c.g * 5 + c.b) >> 3);
                    }
                if (prev != null)
                    for (int y = 0; y < rows; y++)
                    {
                        int region = y < rows * 0.40f ? 0 : y < rows * 0.75f ? 1 : 2;
                        for (int x = 0; x < cols; x++)
                        {
                            // 画面正中是自己的小人，不算
                            if (x > cols * 0.36f && x < cols * 0.64f) continue;
                            int d = Mathf.Abs(lum[y * cols + x] - prev[y * cols + x]);
                            sum[region] += d;
                            if (d > 8) big[region]++;
                            n[region]++;
                        }
                    }
                prev = lum;
            }
            float lo = 999, hi = 0;
            for (int i = 0; i < 10; i++)
            {
                yield return new WaitForSecondsRealtime(0.25f);
                yield return new WaitForEndOfFrame();
                var tex = ScreenCapture.CaptureScreenshotAsTexture();
                var px = tex.GetPixels32();
                Destroy(tex);
                double s = 0;
                int c = 0;
                for (int y = h / 8; y < h * 3 / 8; y += 8)
                    for (int x = w / 8; x < w * 7 / 8; x += 8)
                    {
                        var p = px[y * w + x];
                        s += (p.r * 2 + p.g * 5 + p.b) >> 3;
                        c++;
                    }
                float v = (float)(s / c);
                lo = Mathf.Min(lo, v);
                hi = Mathf.Max(hi, v);
            }
            var sb = new StringBuilder();
            string[] names = { "地面", "建筑", "屋顶" };
            for (int r = 0; r < 3; r++) sb.Append($"{names[r]} {sum[r] / n[r]:F2}（明显闪 {big[r] / n[r] * 100:F1}%） ");
            Debug.Log($"[yuanjing] 探测 {label,-34} 帧间差 {sb} 地面亮度 {lo:F0}..{hi:F0}");
        }
    }
}
