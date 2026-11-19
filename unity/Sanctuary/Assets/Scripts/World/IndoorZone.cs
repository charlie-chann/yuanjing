using UnityEngine;

namespace Yuanjing
{
    /// 殿里的环境光（着色器那边见 Shaders/YJIndoor.hlsl）：天光不管屋顶，殿里本来会像室外的背阴处一样偏蓝发灰。
    /// 在这个盒子里（世界坐标）环境光换成同样亮度的暖色；夜里天光暗下去，至少还有 glow 那么亮（灯火映出来的底光）。
    /// 盒子朝门的一面（-z）慢慢过渡（门口照进来的天光），顶上也过渡（天花板、藻井按原来的环境光，不出接缝），墙那几面是硬边。
    /// 编辑器里出图时也要生效，所以 ExecuteAlways；只在启用时设一次全局参数，不每帧算。
    [ExecuteAlways]
    public class IndoorZone : MonoBehaviour
    {
        public Vector3 min, max;
        public float doorFade = 0.8f, topFade = 0.45f, wallFade = 0.03f;
        [Range(0, 1)] public float strength = 1f;
        // tint、glow 是直接乘、直接比的数（着色器里的线性空间），不按颜色换算
        public Color tint = new Color(1f, 0.86f, 0.66f);
        public float brightness = 1f;
        public Color glow = new Color(0.20f, 0.13f, 0.07f);

        static readonly int MinId = Shader.PropertyToID("_YJIndoorMin"), MaxId = Shader.PropertyToID("_YJIndoorMax"), FadeId = Shader.PropertyToID("_YJIndoorFade"),
            TintId = Shader.PropertyToID("_YJIndoorTint"), GlowId = Shader.PropertyToID("_YJIndoorGlow");

        void OnEnable() => Apply();
        void OnValidate() => Apply();

        void OnDisable() => Shader.SetGlobalVector(MinId, Vector4.zero);

        public void Apply()
        {
            if (!isActiveAndEnabled) return;
            Shader.SetGlobalVector(MinId, new Vector4(min.x, min.y, min.z, strength));
            Shader.SetGlobalVector(MaxId, new Vector4(max.x, max.y, max.z, 0));
            Shader.SetGlobalVector(FadeId, new Vector4(Mathf.Max(doorFade, 0.01f), Mathf.Max(topFade, 0.01f), Mathf.Max(wallFade, 0.01f), 0));
            Shader.SetGlobalVector(TintId, new Vector4(tint.r, tint.g, tint.b, brightness));
            Shader.SetGlobalVector(GlowId, new Vector4(glow.r, glow.g, glow.b, 0));
        }
    }
}
