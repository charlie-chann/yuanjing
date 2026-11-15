using System.Collections;
using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace Yuanjing
{
    /// 临时的排查工具：每 6 秒换一种设置，每 0.25 秒量一次屏幕中下部（地面）的亮度，写进日志。
    public class FlickerProbe : MonoBehaviour
    {
        static readonly string[] modes = { "正常", "关阴影", "单层阴影", "硬阴影", "停散步", "正常" };
        int mode = -1;
        Texture2D tex;

        IEnumerator Start()
        {
            yield return new WaitForSeconds(12f);
            var sun = GameObject.Find("Sun").GetComponent<Light>();
            var urp = (UniversalRenderPipelineAsset)UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline;
            int cascades = urp.shadowCascadeCount;
            for (int round = 0; round < 2; round++)
                for (int m = 0; m < modes.Length; m++)
                {
                    sun.shadows = m == 1 ? LightShadows.None : m == 3 ? LightShadows.Hard : LightShadows.Soft;
                    urp.shadowCascadeCount = m == 2 ? 1 : cascades;
                    foreach (var t in FindObjectsByType<Transform>(FindObjectsSortMode.None))
                        if (t.name.StartsWith("Pilgrim_walk")) t.gameObject.SetActive(m != 4);
                    mode = m;
                    float t0 = Time.time;
                    var sb = new System.Text.StringBuilder();
                    while (Time.time - t0 < 6f)
                    {
                        yield return new WaitForEndOfFrame();
                        var shot = ScreenCapture.CaptureScreenshotAsTexture();
                        int w = shot.width, h = shot.height;
                        var px = shot.GetPixels(w / 4, h / 4, w / 2, h / 6);
                        float sum = 0;
                        foreach (var c in px) sum += c.grayscale;
                        Destroy(shot);
                        sb.Append(Mathf.RoundToInt(sum / px.Length * 255)).Append(' ');
                        yield return new WaitForSeconds(0.25f);
                    }
                    Debug.Log($"[yuanjing] 探测 第{round}轮 {modes[m]}：{sb}");
                }
        }
    }
}
