using UnityEngine;

namespace Yuanjing
{
    /// 烛光：亮度轻轻地、不规则地晃
    public class Flicker : MonoBehaviour
    {
        public float amount = 0.22f, speed = 7f;
        Light lamp;
        float baseIntensity, seed;

        void Awake()
        {
            lamp = GetComponent<Light>();
            baseIntensity = lamp.intensity;
            seed = Random.value * 100f;
        }

        void Update()
        {
            float n = Mathf.PerlinNoise(seed, Time.time * speed) * 0.7f + Mathf.PerlinNoise(seed + 9f, Time.time * speed * 2.7f) * 0.3f;
            lamp.intensity = baseIntensity * (1f - amount + amount * 2f * n);
        }
    }
}
