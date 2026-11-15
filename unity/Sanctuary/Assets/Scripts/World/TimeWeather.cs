using System;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Yuanjing
{
    public enum DayTime { Dawn, Day, Dusk, Night }
    public enum Weather { Clear, Rain, Storm, Snow }

    /// 一个时段的光照设定：用哪张实拍天空、太阳在哪、各种颜色。
    [Serializable]
    public class TimePreset
    {
        public string name;
        public Texture2D sky;

        /// 太阳（或月亮）在全景图上的位置，生成场景时从图里找出来的
        public Vector2 sunUV = new Vector2(0.5f, 0.6f);

        /// 太阳在场景里的方位角（度）：0 是正前方大殿的方向，正数往右
        public float sunAzimuth;

        /// 太阳的高度角（度）；小于 0 表示用图里测出来的
        public float sunElevation = -1;
        public float skyExposure = 1;
        public Color sunColor = Color.white;
        public float sunIntensity = 2;
        public Color ambientSky = Color.gray, ambientEquator = Color.gray, ambientGround = Color.gray;
        public Color fogColor = Color.gray;
        public float fogDensity = 0.005f;
        public float postExposure = 0;
        public float temperature = 0;

        /// 灯笼、窗格、烛火亮几成
        public float lamps;
    }

    /// 天色和天气的总控：太阳、天空、雾、环境光、后期调色、表面的湿度和积雪、雨雪粒子、闪电。
    /// 编辑器里出预览图时也用它（ApplyImmediate），所以标了 ExecuteAlways。
    [ExecuteAlways]
    public class TimeWeather : MonoBehaviour
    {
        public static TimeWeather Instance { get; private set; }

        public TimePreset[] presets = new TimePreset[4];
        public Texture2D overcastSky;
        public float overcastRotation;
        public Light sun;

        /// 从地面往上打的补光，模拟地面的反光
        public Light bounce;
        public Material skyMaterial;
        public Volume volume;
        public ParticleSystem rain, rainSplash, snow;

        /// 檐口滴下来的水帘：雨停了还会零星滴一阵
        public ParticleSystem eaveDrips;
        public ReflectionProbe probe;

        /// 灯笼等发光物体的材质和灯：亮度跟着 lamps 走
        public Renderer[] lampRenderers = new Renderer[0];
        public Light[] lampLights = new Light[0];
        public float[] lampLightIntensity = new float[0];
        public Color lampColor = new Color(1f, 0.58f, 0.24f);
        /// 彩色玻璃窗：夜里从里面透光，用偏白的光，颜色由玻璃自己的图案决定
        public Renderer[] glassRenderers = new Renderer[0];
        public Color glassColor = new Color(1f, 0.93f, 0.82f);

        /// 从正上方看下去的高度图：用来判断哪里有屋檐挡着（挡着的地方不湿、不积雪、不下雨）
        public Texture2D heightMap;
        public Vector4 heightParams;

        public DayTime time = DayTime.Day;
        public Weather weather = Weather.Clear;

        // 当前实际显示的状态（在目标之间慢慢过渡）
        float wet, snowCover, rainAmount, snowAmount, cloud, lampNow, flash;
        int skyFrom = 1, skyTo = 1;
        float skyBlend = 1;
        float nextFlash = 6;
        public event Action Thunder;

        static readonly int WetId = Shader.PropertyToID("_YJWet"), SnowId = Shader.PropertyToID("_YJSnow"), RainId = Shader.PropertyToID("_YJRain"),
            WindId = Shader.PropertyToID("_YJWind"), HeightMapId = Shader.PropertyToID("_YJHeightMap"), HeightParamsId = Shader.PropertyToID("_YJHeightParams");

        /// 遮挡高度图怎么交给着色器：0 只在开头设一次全局贴图（旧做法，手机上会丢）；1 每帧重设全局贴图；2 直接设到每个材质上
        public static int bindMode = 2;
        int boundMaterials = -1;

        void OnEnable()
        {
            Instance = this;
            if (heightMap != null)
            {
                Shader.SetGlobalTexture(HeightMapId, heightMap);
                Shader.SetGlobalVector(HeightParamsId, heightParams);
            }
            RenderSettings.skybox = skyMaterial;
        }

        /// 把高度图设到所有用到它的材质上。全局贴图在手机上不可靠：显卡有时读到别的贴图，
        /// 整个场景就在「全淋湿」和「全是干的」之间来回跳。材质自己带着的贴图不会丢。
        /// 运行中新出现的材质（走进来的人）靠材质数量变化发现，再补设一遍。
        void BindHeightMap()
        {
            if (heightMap == null) return;
            if (bindMode >= 1)
            {
                Shader.SetGlobalTexture(HeightMapId, heightMap);
                Shader.SetGlobalVector(HeightParamsId, heightParams);
            }
            if (bindMode < 2) return;
            var all = Resources.FindObjectsOfTypeAll<Material>();
            if (all.Length == boundMaterials) return;
            boundMaterials = all.Length;
            foreach (var m in all)
                if (m.shader != null && m.shader.name.StartsWith("Yuanjing/")) m.SetTexture(HeightMapId, heightMap);
        }

        float bindT = 99;

        /// 直接跳到某个天色和天气，不做过渡（进场和出预览图时用）
        public void ApplyImmediate(DayTime t, Weather w)
        {
            time = t;
            weather = w;
            skyFrom = skyTo = (int)t;
            skyBlend = 1;
            wet = w == Weather.Rain || w == Weather.Storm ? 1 : 0;
            snowCover = w == Weather.Snow ? 1 : 0;
            rainAmount = w == Weather.Rain ? 0.6f : w == Weather.Storm ? 1f : 0f;
            snowAmount = w == Weather.Snow ? 1 : 0;
            cloud = w == Weather.Clear ? 0 : 1;
            lampNow = Mathf.Max(presets[(int)t].lamps, w == Weather.Storm ? 0.8f : w == Weather.Clear ? 0 : 0.35f);
            flash = 0;
            Apply();
            UpdateEnvironment(true);
            if (probe != null && probe.isActiveAndEnabled) probe.RenderProbe();
        }

        public void Set(DayTime t, Weather w)
        {
            if (t != time)
            {
                skyFrom = skyBlend > 0.5f ? skyTo : skyFrom;
                skyTo = (int)t;
                skyBlend = 0;
            }
            time = t;
            weather = w;
        }

        void Update()
        {
            if (!Application.isPlaying) return;
            float dt = Time.deltaTime;
            bool raining = weather == Weather.Rain || weather == Weather.Storm;
            skyBlend = Mathf.MoveTowards(skyBlend, 1, dt / 6f);
            cloud = Mathf.MoveTowards(cloud, weather == Weather.Clear ? 0 : 1, dt / 8f);
            rainAmount = Mathf.MoveTowards(rainAmount, weather == Weather.Rain ? 0.6f : weather == Weather.Storm ? 1f : 0f, dt / 6f);
            snowAmount = Mathf.MoveTowards(snowAmount, weather == Weather.Snow ? 1 : 0, dt / 6f);
            // 地面湿得快干得慢；雪积得慢化得更慢
            wet = Mathf.MoveTowards(wet, raining ? 1 : 0, dt / (raining ? 14f : 50f));
            snowCover = Mathf.MoveTowards(snowCover, weather == Weather.Snow ? 1 : 0, dt / (weather == Weather.Snow ? 40f : 70f));
            float lampTarget = Mathf.Max(presets[(int)time].lamps, weather == Weather.Storm ? 0.8f : weather == Weather.Clear ? 0 : 0.35f);
            lampNow = Mathf.MoveTowards(lampNow, lampTarget, dt / 4f);

            // 闪电：先亮一下，隔一小会儿再亮一下，然后雷声
            flash = Mathf.MoveTowards(flash, 0, dt * 3.5f);
            if (weather == Weather.Storm)
            {
                nextFlash -= dt;
                if (nextFlash <= 0)
                {
                    nextFlash = UnityEngine.Random.Range(9f, 22f);
                    flash = 1;
                    Invoke(nameof(SecondFlash), 0.16f);
                    Thunder?.Invoke();
                }
            }
            Apply();
        }

        /// 排查用：灯现在的亮度、第一盏灯的状态、窗格材质上的发光颜色
        public string LampDebug()
        {
            string l = lampLights != null && lampLights.Length > 0 && lampLights[0] != null ? $"{lampLights[0].enabled}/{lampLights[0].intensity:F1}/{lampLights[0].isActiveAndEnabled}" : "无";
            string e = lampRenderers != null && lampRenderers.Length > 0 && lampRenderers[0] != null ? lampRenderers[0].sharedMaterial.GetColor(EmissionId).ToString("F2") + (lampRenderers[0].HasPropertyBlock() ? " 有属性块" : "") : "无";
            return $"灯量={lampNow:F2} 时段={time} 天气={weather} 混合={skyBlend:F2} 云={cloud:F2} 灯0={l} 发光={e}";
        }

        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");

        static void SetGlow(Renderer[] renderers, Color c)
        {
            if (renderers == null) return;
            foreach (var r in renderers)
            {
                if (r == null || r.sharedMaterial == null) continue;
                if (r.HasPropertyBlock()) r.SetPropertyBlock(null);
                if (r.sharedMaterial.GetColor(EmissionId) != c) r.sharedMaterial.SetColor(EmissionId, c);
            }
        }

        // 天空变了以后让引擎重新生成「环境反光」用的那张图（不然夜里地上反出来的还是载入时的天空）
        int envKey = -1;
        float envT = 99;

        void UpdateEnvironment(bool force)
        {
            if (!Application.isPlaying) return;
            envT += Time.unscaledDeltaTime;
            int key = skyFrom * 1000000 + skyTo * 100000 + Mathf.RoundToInt(skyBlend * 20) * 100 + Mathf.RoundToInt(cloud * 20);
            if (!force && (key == envKey || envT < 0.7f)) return;
            envKey = key;
            envT = 0;
            DynamicGI.UpdateEnvironment();
        }

        void SecondFlash() => flash = 0.7f;

        /// 太阳在场景里的方向（指向太阳）
        public Vector3 SunDirection(TimePreset p)
        {
            float lat = (1f - p.sunUV.y) * Mathf.PI;
            float elev = p.sunElevation >= 0 ? p.sunElevation * Mathf.Deg2Rad : Mathf.PI / 2 - lat;
            float az = p.sunAzimuth * Mathf.Deg2Rad;
            return new Vector3(Mathf.Sin(az) * Mathf.Cos(elev), Mathf.Sin(elev), Mathf.Cos(az) * Mathf.Cos(elev));
        }

        /// 把全景图转多少，图上的太阳才正好落在场景里想要的方位
        float SkyRotation(TimePreset p)
        {
            float lonTex = (0.5f - p.sunUV.x) * Mathf.PI * 2f;
            Vector3 d = SunDirection(p);
            return lonTex - Mathf.Atan2(d.z, d.x);
        }

        void Apply()
        {
            if (presets == null || presets.Length < 4 || presets[0] == null) return;
            // 材质清单半秒查一次就够（查一次要列出所有材质，不便宜）
            if ((bindT += Time.unscaledDeltaTime) > 0.5f || !Application.isPlaying)
            {
                bindT = 0;
                BindHeightMap();
            }
            TimePreset a = presets[skyFrom], b = presets[skyTo];
            float k = Mathf.SmoothStep(0, 1, skyBlend);
            bool storm = weather == Weather.Storm;
            bool snowing = weather == Weather.Snow || snowAmount > 0.01f;

            // 阴天的程度：把太阳压暗，天空换成阴云，颜色往灰里收
            float dark = cloud * (storm ? 0.82f : snowing ? 0.45f : 0.62f);
            Color grey = Color.Lerp(new Color(0.55f, 0.58f, 0.62f), new Color(0.80f, 0.83f, 0.88f), snowAmount);

            if (sun != null)
            {
                Vector3 dir = Vector3.Slerp(SunDirection(a), SunDirection(b), k).normalized;
                // 太阳贴着地平线时影子会拉得无限长，抬高一点
                dir = new Vector3(dir.x, Mathf.Max(dir.y, 0.10f), dir.z).normalized;
                sun.transform.rotation = Quaternion.LookRotation(-dir);
                sun.color = Color.Lerp(Color.Lerp(a.sunColor, b.sunColor, k), grey, cloud * 0.8f);
                sun.intensity = Mathf.Lerp(a.sunIntensity, b.sunIntensity, k) * (1f - dark * 0.92f) + flash * 6f;
                sun.shadowStrength = Mathf.Lerp(1f, 0.35f, cloud);
                if (bounce != null)
                {
                    // 方向：太阳光在地面上反射后的方向（往上）
                    bounce.transform.rotation = Quaternion.LookRotation(new Vector3(-dir.x, Mathf.Max(dir.y, 0.35f), -dir.z));
                    bounce.color = sun.color * new Color(0.95f, 0.88f, 0.80f);
                    bounce.intensity = sun.intensity * 0.15f + Mathf.Lerp(a.ambientGround.maxColorComponent, b.ambientGround.maxColorComponent, k) * 0.5f;
                }
            }

            float lum = Mathf.Lerp(a.skyExposure, b.skyExposure, k);
            if (skyMaterial != null)
            {
                // 晴天：A、B 是两个时段的天空；阴天：整体换成阴云那张，按时段的亮度染色
                Color ambRef = Color.Lerp(a.ambientSky, b.ambientSky, k);
                float ambLum = ambRef.maxColorComponent;
                if (cloud < 0.01f)
                {
                    skyMaterial.SetTexture("_TexA", a.sky);
                    skyMaterial.SetTexture("_TexB", b.sky);
                    skyMaterial.SetFloat("_RotA", SkyRotation(a));
                    skyMaterial.SetFloat("_RotB", SkyRotation(b));
                    skyMaterial.SetFloat("_ExpA", a.skyExposure);
                    skyMaterial.SetFloat("_ExpB", b.skyExposure);
                    skyMaterial.SetColor("_TintA", Color.white);
                    skyMaterial.SetColor("_TintB", Color.white);
                    skyMaterial.SetFloat("_Blend", k);
                }
                else
                {
                    skyMaterial.SetTexture("_TexA", b.sky);
                    skyMaterial.SetTexture("_TexB", overcastSky);
                    skyMaterial.SetFloat("_RotA", SkyRotation(b));
                    skyMaterial.SetFloat("_RotB", overcastRotation);
                    skyMaterial.SetFloat("_ExpA", b.skyExposure);
                    // 阴云那张是白天拍的：按当前时段环境光的亮度压下来，夜里的阴天才是暗的
                    float overcastExp = Mathf.Lerp(0.05f, 0.75f, Mathf.InverseLerp(0.05f, 0.6f, ambLum)) * (storm ? 0.45f : snowing ? 1.15f : 0.8f);
                    skyMaterial.SetFloat("_ExpB", overcastExp);
                    skyMaterial.SetColor("_TintA", Color.white);
                    skyMaterial.SetColor("_TintB", Color.Lerp(Color.white, ambRef / Mathf.Max(ambLum, 0.01f), 0.35f));
                    skyMaterial.SetFloat("_Blend", cloud);
                }
                skyMaterial.SetFloat("_Flash", flash * 1.6f);
            }

            float ambScale = 1f - dark * 0.55f;
            Color sky = Color.Lerp(a.ambientSky, b.ambientSky, k), eq = Color.Lerp(a.ambientEquator, b.ambientEquator, k), gr = Color.Lerp(a.ambientGround, b.ambientGround, k);
            float skyLum = sky.maxColorComponent;
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = Color.Lerp(sky, grey * skyLum * 1.1f, cloud * 0.75f) * ambScale + new Color(0.5f, 0.55f, 0.7f) * flash;
            RenderSettings.ambientEquatorColor = Color.Lerp(eq, grey * skyLum * 0.9f, cloud * 0.8f) * ambScale + new Color(0.4f, 0.45f, 0.6f) * flash;
            RenderSettings.ambientGroundColor = Color.Lerp(gr, grey * skyLum * 0.45f, cloud * 0.6f) * ambScale;
            RenderSettings.reflectionIntensity = 1f;
            UpdateEnvironment(false);

            Color fog = Color.Lerp(a.fogColor, b.fogColor, k);
            float fogLum = fog.maxColorComponent;
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.ExponentialSquared;
            RenderSettings.fogColor = Color.Lerp(fog, grey * Mathf.Lerp(fogLum, fogLum * 0.75f, storm ? 1 : 0), cloud * 0.85f) + new Color(0.3f, 0.33f, 0.4f) * flash;
            RenderSettings.fogDensity = Mathf.Lerp(a.fogDensity, b.fogDensity, k) * (1f + rainAmount * 3.2f + snowAmount * 2.0f);
            if (skyMaterial != null) skyMaterial.SetColor("_Ground", RenderSettings.fogColor);

            Shader.SetGlobalFloat(WetId, wet);
            Shader.SetGlobalFloat(SnowId, snowCover);
            Shader.SetGlobalFloat(RainId, rainAmount);
            // 雨雪本身不受光，按环境光给它一个颜色：白天发亮，夜里只是淡淡的影子
            Color precip = RenderSettings.ambientSkyColor * 1.35f + (sun != null ? sun.color * sun.intensity * 0.10f : Color.black) + lampColor * lampNow * 0.05f;
            Shader.SetGlobalColor("_YJPrecipTint", precip);
            Shader.SetGlobalFloat(WindId, storm ? 1f : rainAmount > 0.1f || snowing ? 0.45f : 0.2f);

            SetEmission(rain, rainAmount * 5200f);
            SetEmission(eaveDrips, rainAmount * 520f + wet * (1f - rainAmount) * 40f);
            SetEmission(rainSplash, rainAmount * 520f);
            SetEmission(snow, snowAmount * 900f);

            // 灯笼和窗格：亮度直接设到材质上（同一种灯共用一个材质）。
            // 不用「每个物体单独的属性块」：那样这些物体走另一条绘制路径，手机上和别的物体的参数会串
            SetGlow(lampRenderers, lampColor * (0.02f + lampNow * 1.35f));
            SetGlow(glassRenderers, glassColor * (0.04f + lampNow * 2.2f));
            if (lampLights != null)
                for (int i = 0; i < lampLights.Length; i++)
                    if (lampLights[i] != null)
                    {
                        lampLights[i].intensity = lampLightIntensity[i] * lampNow;
                        lampLights[i].enabled = lampNow > 0.02f;
                    }

            if (volume != null && volume.sharedProfile != null)
            {
                if (volume.sharedProfile.TryGet(out ColorAdjustments ca))
                {
                    ca.postExposure.value = Mathf.Lerp(a.postExposure, b.postExposure, k) + dark * 0.25f;
                    ca.saturation.value = Mathf.Lerp(6f, -22f, cloud * (snowing ? 0.7f : 1f));
                }
                if (volume.sharedProfile.TryGet(out WhiteBalance wb))
                    wb.temperature.value = Mathf.Lerp(Mathf.Lerp(a.temperature, b.temperature, k), snowing ? -14f : -8f, cloud * 0.7f);
            }
            _ = lum;
        }

        static void SetEmission(ParticleSystem ps, float rate)
        {
            if (ps == null) return;
            foreach (var p in ps.GetComponentsInChildren<ParticleSystem>())
            {
                var e = p.emission;
                e.rateOverTime = rate;
            }
        }
    }
}
