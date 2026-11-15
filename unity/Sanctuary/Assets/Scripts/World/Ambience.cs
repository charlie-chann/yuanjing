using UnityEngine;

namespace Yuanjing
{
    /// 湖心小寺里那些会动的小东西：白天的蝴蝶、夜里的萤火虫、飘落的叶子和花瓣。
    /// 多少跟着天色和天气走：下雨没有蝴蝶和萤火虫，风大的时候叶子落得多。
    public class Ambience : MonoBehaviour
    {
        public static Ambience Instance { get; private set; }
        public ParticleSystem butterflies, fireflies;
        /// 小动物高兴时头顶冒的小爱心
        public ParticleSystem hearts;
        /// 撒给小鸟的谷子、喂鱼时的水花
        public GameObject grain;

        void Awake() => Instance = this;

        public static void Hearts(Vector3 at, int count)
        {
            if (Instance == null || Instance.hearts == null) return;
            Instance.hearts.transform.position = at;
            Instance.hearts.Emit(count);
        }

        /// 在某处撒一把谷子：附近的小鸟飞过来吃
        public void FeedBirds(Vector3 at)
        {
            if (grain != null)
            {
                grain.SetActive(true);
                grain.transform.position = at + Vector3.up * 0.02f;
                CancelInvoke(nameof(HideGrain));
                Invoke(nameof(HideGrain), 16f);
            }
            foreach (var b in Bird.All) b.Feed(at);
        }

        void HideGrain()
        {
            if (grain != null) grain.SetActive(false);
        }

        public ParticleSystem[] leaves = new ParticleSystem[0];
        public float butterflyRate = 0.6f, fireflyRate = 5f, leafRate = 1.2f;

        float b, f, l = 1;

        static void Rate(ParticleSystem ps, float rate)
        {
            if (ps == null) return;
            var e = ps.emission;
            e.rateOverTime = rate;
        }

        void Update()
        {
            var tw = TimeWeather.Instance;
            if (tw == null) return;
            bool clear = tw.weather == Weather.Clear;
            bool night = tw.time == DayTime.Night, dusk = tw.time == DayTime.Dusk;
            float dt = Time.deltaTime;
            b = Mathf.MoveTowards(b, clear && !night ? 1 : 0, dt / 4f);
            f = Mathf.MoveTowards(f, clear && night ? 1 : clear && dusk ? 0.4f : 0, dt / 4f);
            l = Mathf.MoveTowards(l, tw.weather == Weather.Storm ? 3f : tw.weather == Weather.Snow ? 0.2f : 1f, dt / 4f);
            Rate(butterflies, butterflyRate * b);
            Rate(fireflies, fireflyRate * f);
            foreach (var p in leaves) Rate(p, leafRate * l);
        }
    }
}
