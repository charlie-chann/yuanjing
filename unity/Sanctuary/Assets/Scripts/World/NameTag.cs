using UnityEngine;

namespace Yuanjing
{
    /// 头顶的名字：一圈深墨色的描边（八个方向各一份，压在下面），浅色的字在亮的石板、暗的湖面上都看得清。
    [RequireComponent(typeof(TextMesh))]
    public class NameTag : MonoBehaviour
    {
        public static readonly Color Ink = new Color(0.17f, 0.14f, 0.125f, 0.92f);
        TextMesh main;
        TextMesh[] rim;

        void Ensure()
        {
            if (rim != null) return;
            main = GetComponent<TextMesh>();
            main.fontStyle = FontStyle.Bold;
            rim = new TextMesh[8];
            var mr = GetComponent<MeshRenderer>();
            mr.sortingOrder = 2;
            for (int i = 0; i < 8; i++)
            {
                var go = new GameObject("rim");
                go.transform.SetParent(transform, false);
                float a = i * Mathf.PI / 4;
                // 描边的粗细按字的大小：约字高的 6%
                float w = main.characterSize * main.fontSize * 0.006f;
                go.transform.localPosition = new Vector3(Mathf.Cos(a) * w, Mathf.Sin(a) * w, 0.0005f);
                var t = go.AddComponent<TextMesh>();
                t.font = main.font;
                t.fontSize = main.fontSize;
                t.characterSize = main.characterSize;
                t.anchor = main.anchor;
                t.alignment = main.alignment;
                t.fontStyle = FontStyle.Bold;
                t.color = Ink;
                var r = go.GetComponent<MeshRenderer>();
                r.sharedMaterial = mr.sharedMaterial;
                r.sortingOrder = 1;
                rim[i] = t;
            }
        }

        public void Set(string text, Color color)
        {
            Ensure();
            main.text = text;
            main.color = color;
            foreach (var t in rim) t.text = text;
        }
    }
}
