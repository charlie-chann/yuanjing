using System.Collections.Generic;
using UnityEngine;

namespace Yuanjing
{
    /// 留在殿里的心意：许愿树上的红布条和木牌、香炉里的香、许愿池里的硬币。
    /// 挂的位置是生成场景时在低处枝条上预留的（slots 下的一个个点）。
    /// 自己放的那一件会从眼前飘过去；别人放的直接出现。
    public class Offerings : MonoBehaviour
    {
        public static Offerings Instance { get; private set; }

        public Transform slots;
        /// 俯视的场景里镜头远，按实际大小做的布条、香根本看不见，放大一些
        public Vector3 ribbonScale = Vector3.one, plaqueScale = Vector3.one, incenseScale = Vector3.one;
        /// 烛台上还空着的位置（教堂）
        public Transform candleSlots;
        public Material ribbonMaterial, plaqueMaterial, stickMaterial, emberMaterial, coinMaterial, waxMaterial, flameMaterial;
        public ParticleSystem sparkle, smoke, splash;
        /// 香插在哪（香炉里灰面的中心）和能插的半径
        public Transform incenseAnchor;
        public float incenseRadius = 0.42f;
        /// 许愿池的水面中心和半径
        public Transform pool;
        public float poolRadius = 1.5f;

        readonly HashSet<int> used = new HashSet<int>();

        class Flight
        {
            public Transform t;
            public Vector3 from, to;
            public float k, lift, seconds, spin;
            public string kind;
            public int slot;
        }
        readonly List<Flight> flights = new List<Flight>();
        float smokeBoost;

        void Awake() => Instance = this;

        /// 能放东西的位置：寺庙是树上的枝条，教堂是烛台上的空位
        Transform Slots => slots != null ? slots : candleSlots;
        public int SlotCount => Slots == null ? 0 : Slots.childCount;

        /// 别人留下的，直接出现在那里
        public void Place(string kind, int slot)
        {
            if (kind == "candle") Candle(slot, false);
            else if (kind == "ribbon" || kind == "plaque") Hang(kind, slot, false);
        }

        /// 自己挂的要不要挑离自己最近的空位（俯视的场景里用：挂在树的另一侧就看不见了）
        public bool nearestSlot;

        public int FreeSlot()
        {
            int n = SlotCount;
            if (n == 0) return -1;
            if (nearestSlot && GameDirector.Instance != null)
            {
                Vector3 me = GameDirector.Instance.HandPoint();
                int best = -1;
                float bd = float.MaxValue;
                for (int i = 0; i < n; i++)
                {
                    if (used.Contains(i)) continue;
                    float d = (Slots.GetChild(i).position - me).sqrMagnitude;
                    if (d < bd) { bd = d; best = i; }
                }
                if (best >= 0) return best;
            }
            int start = Random.Range(0, n);
            for (int i = 0; i < n; i++)
            {
                int s = (start + i) % n;
                if (!used.Contains(s)) return s;
            }
            return start;
        }

        static Mesh ribbonMesh, plaqueMesh, stickMesh, emberMesh, coinMesh, candleMesh, flameMesh;

        static Mesh CandleMesh()
        {
            if (candleMesh != null) return candleMesh;
            var mb = new MeshBuilder();
            mb.Cylinder(Vector3.zero, 0.013f, 0.16f, 8, true);
            return candleMesh = mb.Build("Candle");
        }

        static Mesh FlameMesh()
        {
            if (flameMesh != null) return flameMesh;
            var mb = new MeshBuilder();
            mb.Lathe(Vector3.zero, new[] { new Vector2(0.001f, 0f), new Vector2(0.010f, 0.008f), new Vector2(0.014f, 0.022f), new Vector2(0.008f, 0.045f), new Vector2(0.001f, 0.066f) }, 6);
            return flameMesh = mb.Build("CandleFlame");
        }

        /// 一条布条：上端系着不动，越往下摆得越厉害
        static Mesh RibbonMesh()
        {
            if (ribbonMesh != null) return ribbonMesh;
            var mb = new MeshBuilder();
            const int seg = 8;
            const float w = 0.034f, len = 0.82f;
            for (int i = 0; i < seg; i++)
            {
                float t0 = i / (float)seg, t1 = (i + 1) / (float)seg;
                mb.Card(new Vector3(0, -len * (t0 + t1) * 0.5f, 0), Vector3.right * w, Vector3.up * len * 0.5f / seg, new Rect(0, t0 * 2f, 0.2f, 2f / seg), t1 * t1, t0 * t0);
            }
            return ribbonMesh = mb.Build("Ribbon");
        }

        /// 一块木牌：细绳吊着一块小木板，整块跟着风轻轻晃
        static Mesh PlaqueMesh()
        {
            if (plaqueMesh != null) return plaqueMesh;
            var mb = new MeshBuilder();
            mb.color = new Color(0.1f, 0, 0, 1);
            mb.Box(new Vector3(0, -0.09f, 0), new Vector3(0.004f, 0.18f, 0.004f));
            mb.color = new Color(0.45f, 0, 0, 1);
            mb.Box(new Vector3(0, -0.245f, 0), new Vector3(0.085f, 0.13f, 0.009f));
            // 上沿削成屋顶的形状
            mb.Box(new Vector3(0, -0.172f, 0), new Vector3(0.05f, 0.02f, 0.009f));
            return plaqueMesh = mb.Build("Plaque");
        }

        static Mesh StickMesh()
        {
            if (stickMesh != null) return stickMesh;
            var mb = new MeshBuilder();
            mb.Cylinder(Vector3.zero, 0.0028f, 0.27f, 6, false);
            return stickMesh = mb.Build("IncenseStick");
        }

        static Mesh EmberMesh()
        {
            if (emberMesh != null) return emberMesh;
            var mb = new MeshBuilder();
            mb.Cylinder(Vector3.zero, 0.0036f, 0.012f, 6, true);
            return emberMesh = mb.Build("IncenseEmber");
        }

        static Mesh CoinMesh()
        {
            if (coinMesh != null) return coinMesh;
            var mb = new MeshBuilder();
            mb.Cylinder(new Vector3(0, -0.0012f, 0), 0.013f, 0.0024f, 18, true);
            return coinMesh = mb.Build("Coin");
        }

        GameObject Make(string name, Mesh mesh, Material mat, Transform parent = null)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent != null ? parent : transform, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var r = go.AddComponent<MeshRenderer>();
            r.sharedMaterial = mat;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            return go;
        }

        /// 自己放的东西从人胸前出手（第三人称，看得到自己）
        Vector3 InFront(float forward, float up) =>
            GameDirector.Instance != null ? GameDirector.Instance.HandPoint() + Vector3.up * (up + 0.2f) * 0.3f : Camera.main.transform.position + Camera.main.transform.forward * forward;

        /// 挂一件到树上。kind：ribbon 红布条，plaque 木牌
        public void Hang(string kind, int slot, bool mine)
        {
            if (slots == null || slots.childCount == 0) return;
            slot = Mathf.Clamp(slot, 0, slots.childCount - 1);
            used.Add(slot);
            bool plaque = kind == "plaque";
            var go = Make(plaque ? "Plaque" : "Ribbon", plaque ? PlaqueMesh() : RibbonMesh(), plaque ? plaqueMaterial : ribbonMaterial);
            Vector3 to = slots.GetChild(slot).position;
            go.transform.rotation = Quaternion.Euler(0, Random.Range(0f, 180f), 0);
            go.transform.localScale = plaque ? plaqueScale : ribbonScale;
            if (mine && Camera.main != null)
            {
                Vector3 from = InFront(0.7f, 0.16f);
                go.transform.position = from;
                flights.Add(new Flight { t = go.transform, from = from, to = to, lift = 0.9f, seconds = 3.2f, kind = kind, slot = slot });
            }
            else go.transform.position = to;
        }

        /// 上一炷香：三支，插进香炉的灰里
        public void Incense(bool mine)
        {
            if (incenseAnchor == null) return;
            Vector2 r = Random.insideUnitCircle * incenseRadius;
            var root = new GameObject("Incense").transform;
            root.SetParent(transform, false);
            root.localScale = incenseScale;
            Vector3 to = incenseAnchor.position + new Vector3(r.x, 0, r.y);
            for (int i = -1; i <= 1; i++)
            {
                var stick = Make("Stick", StickMesh(), stickMaterial, root);
                stick.transform.localPosition = new Vector3(i * 0.014f, -0.04f, 0);
                stick.transform.localRotation = Quaternion.Euler(Random.Range(-4f, 4f), 0, i * -5f + Random.Range(-2f, 2f));
                var ember = Make("Ember", EmberMesh(), emberMaterial, stick.transform);
                ember.transform.localPosition = new Vector3(0, 0.27f, 0);
            }
            if (mine && Camera.main != null)
            {
                Vector3 from = InFront(0.55f, -0.22f);
                root.position = from;
                flights.Add(new Flight { t = root, from = from, to = to, lift = 0.25f, seconds = 2.6f, kind = "incense", slot = -1 });
            }
            else root.position = to;
        }

        /// 点一支蜡烛，放到烛台的空位上。自己点的那支：先拿在眼前，放上去以后才亮。
        public void Candle(int slot, bool mine)
        {
            if (candleSlots == null || candleSlots.childCount == 0) return;
            slot = Mathf.Clamp(slot, 0, candleSlots.childCount - 1);
            used.Add(slot);
            Vector3 to = candleSlots.GetChild(slot).position;
            var go = Make("Candle", CandleMesh(), waxMaterial);
            var fire = Make("Flame", FlameMesh(), flameMaterial, go.transform);
            fire.transform.localPosition = new Vector3(0, 0.166f, 0);
            if (mine && Camera.main != null)
            {
                Vector3 from = InFront(0.5f, -0.2f);
                go.transform.position = from;
                fire.SetActive(false);
                flights.Add(new Flight { t = go.transform, from = from, to = to, lift = 0.12f, seconds = 2.6f, kind = "candle", slot = slot });
            }
            else go.transform.position = to;
        }

        /// 往许愿池里抛一枚硬币
        public void Coin(bool mine)
        {
            if (pool == null) return;
            Vector2 r = Random.insideUnitCircle * poolRadius * 0.8f;
            Vector3 to = pool.position + new Vector3(r.x, 0, r.y);
            var go = Make("Coin", CoinMesh(), coinMaterial);
            if (mine && Camera.main != null)
            {
                Vector3 from = InFront(0.5f, -0.25f);
                go.transform.position = from;
                flights.Add(new Flight { t = go.transform, from = from, to = to, lift = 1.5f, seconds = 1.5f, kind = "coin", slot = -1, spin = 1300f });
                WorldAudio.Instance?.Play("sfx_coin_1", 0.7f);
            }
            else
            {
                go.transform.position = to + Vector3.down * 0.3f;
            }
        }

        void Update()
        {
            if (smoke != null)
            {
                smokeBoost = Mathf.MoveTowards(smokeBoost, 0, Time.deltaTime / 40f);
                var e = smoke.emission;
                e.rateOverTime = 5f + 9f * smokeBoost;
            }
            for (int i = flights.Count - 1; i >= 0; i--)
            {
                var f = flights[i];
                // 先在眼前停一拍，再飘过去
                f.k += Time.deltaTime / f.seconds;
                float k = f.kind == "coin" ? Mathf.Clamp01(f.k) : Mathf.SmoothStep(0, 1, Mathf.Clamp01((f.k - 0.18f) / 0.82f));
                f.t.position = Vector3.Lerp(f.from, f.to, k) + Vector3.up * Mathf.Sin(k * Mathf.PI) * f.lift;
                if (f.spin > 0) f.t.Rotate(f.spin * Time.deltaTime, 0, f.spin * 0.21f * Time.deltaTime);
                if (f.k < 1) continue;
                flights.RemoveAt(i);
                Land(f);
            }
        }

        void Land(Flight f)
        {
            var audio = WorldAudio.Instance;
            if (f.kind == "coin")
            {
                // 入水：溅一下水花，硬币沉到池底
                f.t.position = f.to + Vector3.down * 0.3f;
                f.t.rotation = Quaternion.Euler(Random.Range(-8f, 8f), Random.Range(0f, 360f), Random.Range(-8f, 8f));
                if (splash != null)
                {
                    splash.transform.position = f.to + Vector3.up * 0.02f;
                    splash.Emit(26);
                }
                audio?.Play("sfx_splash", 0.9f);
            }
            else if (f.kind == "candle")
            {
                f.t.position = f.to;
                f.t.GetChild(0).gameObject.SetActive(true);
                if (sparkle != null)
                {
                    sparkle.transform.position = f.to + Vector3.up * 0.2f;
                    sparkle.Emit(14);
                }
                audio?.Play("sfx_light", 0.8f);
            }
            else if (f.kind == "incense")
            {
                f.t.position = f.to;
                smokeBoost = 1;
                audio?.Play("sfx_light", 0.7f);
            }
            else
            {
                f.t.position = f.to;
                if (sparkle != null)
                {
                    sparkle.transform.position = f.to + Vector3.down * 0.3f;
                    sparkle.Emit(28);
                }
                audio?.Play(f.kind == "plaque" ? "sfx_wood" : "sfx_cloth", 0.9f);
                audio?.Play("sfx_sparkle", 0.5f);
            }
            GameDirector.Send($"{{\"type\":\"offered\",\"kind\":\"{f.kind}\",\"slot\":{f.slot}}}");
        }
    }
}
