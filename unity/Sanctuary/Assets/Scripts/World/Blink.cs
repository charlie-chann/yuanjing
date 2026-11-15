using UnityEngine;

namespace Yuanjing
{
    /// 眨眼：隔几秒闭一下眼（用脸上「闭眼」那个表情形变），偶尔连眨两下。
    public class Blink : MonoBehaviour
    {
        public SkinnedMeshRenderer face;
        public int shape = -1;
        float next, t = -1f;
        int again;

        void Start() => next = Time.time + Random.Range(1f, 4f);

        void Update()
        {
            if (face == null || shape < 0) return;
            if (t < 0f)
            {
                if (Time.time < next) return;
                t = 0f;
            }
            t += Time.deltaTime;
            const float close = 0.06f, hold = 0.04f, open = 0.1f;
            float w = t < close ? t / close : t < close + hold ? 1f : 1f - (t - close - hold) / open;
            face.SetBlendShapeWeight(shape, Mathf.Clamp01(w) * 100f);
            if (t >= close + hold + open)
            {
                t = -1f;
                if (again == 0 && Random.value < 0.2f) { again = 1; next = Time.time + 0.12f; }
                else { again = 0; next = Time.time + Random.Range(2.2f, 6f); }
            }
        }
    }
}
