using UnityEngine;

namespace Yuanjing
{
    /// 同一个动漫人物模型出现好几次时，按人换发色和衣服的颜色，看起来是不同的人。
    /// 只是乘一个颜色（不改贴图）：浅色头发的模型变化大，黑头发的模型基本还是黑头发。
    public static class AnimeVariant
    {
        static readonly Color[] Hair =
        {
            Color.white, new Color(0.95f, 0.72f, 0.52f), new Color(0.72f, 0.5f, 0.42f), new Color(0.62f, 0.62f, 0.72f),
            new Color(1f, 0.8f, 0.88f), new Color(0.5f, 0.42f, 0.4f), new Color(0.82f, 0.9f, 1f), new Color(1f, 0.92f, 0.7f),
        };
        static readonly Color[] Cloth =
        {
            Color.white, new Color(0.78f, 0.88f, 1f), new Color(1f, 0.86f, 0.8f), new Color(0.84f, 1f, 0.86f),
            new Color(0.92f, 0.84f, 1f), new Color(1f, 0.96f, 0.82f), new Color(0.7f, 0.7f, 0.74f),
        };
        static readonly int ColorId = Shader.PropertyToID("_Color");

        /// seed 用这个人的编号算出来的数，同一个人每次进来都一样
        public static void Apply(GameObject go, int seed)
        {
            if (seed % 5 == 0) return;           // 有两成保持原样
            Color hair = Hair[seed % Hair.Length], cloth = Cloth[(seed / 7) % Cloth.Length];
            var mpb = new MaterialPropertyBlock();
            foreach (var r in go.GetComponentsInChildren<SkinnedMeshRenderer>())
            {
                var mats = r.sharedMaterials;
                for (int i = 0; i < mats.Length; i++)
                {
                    var m = mats[i];
                    if (m == null || !m.HasProperty(ColorId)) continue;
                    string n = m.name;
                    Color tint = n.Contains("_HAIR") ? hair : n.Contains("_CLOTH") ? cloth : Color.clear;
                    if (tint == Color.clear) continue;
                    r.GetPropertyBlock(mpb, i);
                    mpb.SetColor(ColorId, m.GetColor(ColorId) * tint);
                    r.SetPropertyBlock(mpb, i);
                }
            }
        }
    }
}
