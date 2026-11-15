using System.Collections.Generic;
using UnityEngine;

namespace Yuanjing
{
    /// 殿里的声音：背景音乐、白天或夜晚的环境声、天气的声音（雨、暴雨、雪、风），还有雷、钟、脚步这些一次性的声音。
    /// 素材在 Resources/Audio（由 tools/audio/generate_audio.py 合成），各条轨道按天色天气慢慢交叉过渡。
    public class WorldAudio : MonoBehaviour
    {
        public static WorldAudio Instance { get; private set; }

        public string musicName = "amb_music_temple";
        /// 场景里某个位置上一直响着的声音（许愿池的水声）：走近了响，走远了轻
        public string placedLoop;
        public Vector3 placedAt;
        public float placedVolume = 0.7f, placedRange = 20f;
        /// 按谁离那个位置的远近来算音量。不填就按镜头（俯视镜头离人很远，要填成人）
        public Transform placedListener;
        [Range(0, 1)] public float master = 1f;
        public float musicVolume = 0.42f;

        readonly Dictionary<string, AudioSource> loops = new Dictionary<string, AudioSource>();
        readonly Dictionary<string, AudioClip> clips = new Dictionary<string, AudioClip>();
        AudioSource oneShot;
        int foot;
        bool muted;

        void Awake()
        {
            Instance = this;
            oneShot = gameObject.AddComponent<AudioSource>();
            oneShot.spatialBlend = 0;
            foreach (string n in new[] { musicName, "amb_sanc_day", "amb_sanc_night", "amb_w_rain", "amb_w_storm", "amb_w_snow", "amb_w_wind" }) Loop(n);
            if (!string.IsNullOrEmpty(placedLoop)) Loop(placedLoop);
        }

        void OnEnable()
        {
            if (TimeWeather.Instance != null) TimeWeather.Instance.Thunder += OnThunder;
        }

        void Start()
        {
            // Awake 的先后顺序不固定，这里再订阅一次（先退订，避免重复）
            if (TimeWeather.Instance != null) { TimeWeather.Instance.Thunder -= OnThunder; TimeWeather.Instance.Thunder += OnThunder; }
        }

        AudioClip Clip(string name)
        {
            if (!clips.TryGetValue(name, out var c))
            {
                c = Resources.Load<AudioClip>("Audio/" + name);
                clips[name] = c;
                if (c == null) Debug.LogWarning("[yuanjing] 声音素材没找到：" + name);
            }
            return c;
        }

        void Loop(string name)
        {
            var clip = Clip(name);
            if (clip == null) return;
            var s = gameObject.AddComponent<AudioSource>();
            s.clip = clip;
            s.loop = true;
            s.volume = 0;
            s.spatialBlend = 0;
            s.playOnAwake = false;
            loops[name] = s;
        }

        public void SetMuted(bool m) => muted = m;

        public void Play(string name, float volume = 1f)
        {
            var c = Clip(name);
            if (c != null && !muted) oneShot.PlayOneShot(c, volume * master);
        }

        void OnThunder()
        {
            // 光先到，声音晚一两秒
            Invoke(nameof(ThunderSound), Random.Range(0.5f, 1.8f));
        }

        void ThunderSound() => Play(Random.value < 0.6f ? "sfx_thunder_1" : "sfx_thunder_2", 0.9f);

        /// 自己的脚步声（由 GameDirector 在小人迈步时调用）
        public void Step() => Play(foot++ % 2 == 0 ? "sfx_foot_1" : "sfx_foot_2", 0.4f);

        void Update()
        {
            var tw = TimeWeather.Instance;
            if (tw == null) return;
            float night = tw.time == DayTime.Night ? 1f : tw.time == DayTime.Dusk ? 0.55f : tw.time == DayTime.Dawn ? 0.25f : 0f;
            bool rain = tw.weather == Weather.Rain, storm = tw.weather == Weather.Storm, snow = tw.weather == Weather.Snow;
            // 下雨下雪时鸟和虫都安静下来
            float calm = rain || storm ? 0.25f : snow ? 0.15f : 1f;
            Fade(musicName, musicVolume, 0.5f);
            if (!string.IsNullOrEmpty(placedLoop) && Camera.main != null)
            {
                Vector3 ear = placedListener != null ? placedListener.position : Camera.main.transform.position;
                float near = Mathf.Clamp01(1f - Vector3.Distance(ear, placedAt) / placedRange);
                Fade(placedLoop, placedVolume * (0.12f + 0.88f * near * near), 0.6f);
            }
            Fade("amb_sanc_day", (1f - night) * 0.75f * calm, 0.35f);
            Fade("amb_sanc_night", night * 0.75f * calm, 0.35f);
            Fade("amb_w_rain", rain ? 0.85f : 0f, 0.25f);
            Fade("amb_w_storm", storm ? 0.95f : 0f, 0.25f);
            Fade("amb_w_snow", snow ? 0.8f : 0f, 0.25f);
            Fade("amb_w_wind", storm ? 0.55f : snow ? 0.3f : tw.weather == Weather.Clear ? 0.12f : 0.2f, 0.25f);
        }

        void Fade(string name, float target, float speed)
        {
            if (!loops.TryGetValue(name, out var s)) return;
            target = muted ? 0 : target * master;
            s.volume = Mathf.MoveTowards(s.volume, target, speed * Time.deltaTime);
            if (s.volume > 0.001f && !s.isPlaying) s.Play();
            else if (s.volume <= 0.001f && s.isPlaying && target <= 0) s.Pause();
        }
    }
}
