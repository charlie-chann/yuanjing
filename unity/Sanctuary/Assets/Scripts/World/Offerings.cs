using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace Yuanjing
{
    /// 留在殿里的心意：许愿树上的红布条和木牌、香炉里的香、许愿池里的硬币。
    /// 挂的位置是生成场景时在绳圈上预留的（slots 下的一个个点）。
    /// 布条、木牌上写着愿望：字是 Flutter 用应用里的字体写好送来的灰度图，这里合成到布纹、木纹上（WishCloth），每件一张贴图。
    /// 自己挂的那件由总控（GameDirector.HangSequence）走过去亲手系上；别人挂的直接出现在绳上。
    public class Offerings : MonoBehaviour
    {
        public static Offerings Instance { get; private set; }

        public Transform slots;
        /// 布条、木牌、香的缩放。布条木牌现在按真实大小做（WishCloth），这里一般是 1
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
        /// 布条、木牌挂好以后随风摆的幅度（拿在手里时小一些）
        public float hangSway = 1f, heldSway = 0.35f;

        /// 有人占着（已经挂了、或者自己正要去挂）的格子
        readonly HashSet<int> used = new HashSet<int>();

        /// 绳上挂着的一件：哪一格、谁的（服务器编号；自己刚挂的还没有编号）、正面那张贴图
        class Item
        {
            public GameObject go;
            public string id = "", kind;
            public int slot;
            public bool mine;
            public Texture2D face;
        }
        readonly Dictionary<int, Item> atSlot = new Dictionary<int, Item>();
        readonly Dictionary<string, Item> byId = new Dictionary<string, Item>();
        readonly Dictionary<GameObject, Texture2D> faces = new Dictionary<GameObject, Texture2D>();

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
        /// 殿里的香炉：中间那只、两边供桌上那两只上面的细烟（淡淡地一直冒；有人上香时中间那只浓一阵，40 秒慢慢淡回去）
        public ParticleSystem hallSmoke;
        public ParticleSystem[] hallSideSmoke = new ParticleSystem[0];
        float hallBoost;

        void Awake() => Instance = this;

        /// 能放东西的位置：寺庙是树上的枝条，教堂是烛台上的空位
        Transform Slots => slots != null ? slots : candleSlots;
        public int SlotCount => Slots == null ? 0 : Slots.childCount;

        /// 已经挂在树上的，直接出现在那里。id 是服务器的编号（同一件不重复挂），tex 是写了字的灰度图（PNG 的 base64，可以没有）。
        /// mine：是自己以前挂的（服务器「mine」那一份）。只有自己的才会认领那一格上自己刚挂、还没编号的那件；别人的撞了格就往后挪
        public void Place(string kind, int slot, string id = null, string tex = null, bool mine = false)
        {
            if (kind == "candle") { Candle(slot, false); return; }
            if (kind != "ribbon" && kind != "plaque") return;
            if (slots == null || slots.childCount == 0) return;
            id ??= "";
            if (id != "" && byId.TryGetValue(id, out var have))
            {
                // 已经挂着了；之前没有字、这回带了字，就把字补上
                if (have.face == null && !string.IsNullOrEmpty(tex)) QueueFace(have, tex);
                return;
            }
            slot = Mathf.Clamp(slot, 0, slots.childCount - 1);
            if (atSlot.TryGetValue(slot, out var there))
            {
                if (mine && there.id == "" && there.mine && there.kind == kind && id != "")
                {
                    // 自己刚挂的那件：服务器回了编号，认下来，不再挂一件
                    there.id = id;
                    byId[id] = there;
                    if (there.face == null && !string.IsNullOrEmpty(tex)) QueueFace(there, tex);
                    return;
                }
                // 两个人挑了同一格：往后找一格空的（Flutter 那边已经错开过，这里只是保险）
                slot = NextFree(slot);
                if (slot < 0) return;
            }
            else if (used.Contains(slot))
            {
                // 这一格自己正要去挂
                slot = NextFree(slot);
                if (slot < 0) return;
            }
            // 先挂一件素的，字（解图、合成贴图）排队一帧做一件：一进殿 Flutter 一口气发来二三十件，不会卡一下
            var go = MakeWish(kind, null);
            var it = Fix(go, kind, slot, mine, id, false);
            if (!string.IsNullOrEmpty(tex)) QueueFace(it, tex);
        }

        /// 这一格上挂着的是别人的（自己挂得了的格子都满了时，取下最近的一件别人的，挂自己的）
        public bool OthersAt(int slot) => atSlot.TryGetValue(slot, out var it) && !it.mine;

        /// 取下这一格上别人挂的那件（连同它的贴图），空出这一格。自己的不取
        public bool Evict(int slot)
        {
            if (!atSlot.TryGetValue(slot, out var it) || it.mine) return false;
            Remove(it);
            return true;
        }

        /// 自己挂了、服务器却一直没认（没回编号：/offer 没发出去、或者系好那一下就离开了）的那几件：重新进殿时收掉，
        /// 以服务器为准（发出去了的，进殿后「mine」那一份会把它按原来的格子挂回来）
        public int DropUnacknowledged()
        {
            int n = 0;
            foreach (var it in new List<Item>(atSlot.Values))
                if (it.mine && it.id == "") { Remove(it); n++; }
            return n;
        }

        void Remove(Item it)
        {
            atSlot.Remove(it.slot);
            if (it.id != "" && byId.TryGetValue(it.id, out var same) && same == it) byId.Remove(it.id);
            used.Remove(it.slot);
            if (it.go != null)
            {
                faces.Remove(it.go);
                Destroy(it.go);
            }
            if (it.face != null) Destroy(it.face);
            it.face = null;
        }

        /// 等着合成贴图的（别人的心意）：一帧做一件
        readonly Queue<(Item it, string tex)> faceQueue = new Queue<(Item, string)>();
        public int PendingFaces => faceQueue.Count;

        void QueueFace(Item it, string tex) => faceQueue.Enqueue((it, tex));

        /// 兼容旧的调用：挂一件没写字的
        public void Hang(string kind, int slot, bool mine) => Place(kind, slot);

        int NextFree(int from)
        {
            int n = SlotCount;
            for (int i = 1; i < n; i++)
            {
                int s = (from + i) % n;
                if (!used.Contains(s)) return s;
            }
            return -1;
        }

        /// 自己挂的要不要挑离自己最近的空位（俯视的场景里用：挂在树的另一侧就看不见了）
        public bool nearestSlot;

        public int FreeSlot()
        {
            int n = SlotCount;
            if (n == 0) return -1;
            if (nearestSlot && GameDirector.Instance != null)
            {
                int best = NearestFreeSlot(GameDirector.Instance.HandPoint());
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

        /// 离这一点（按水平距离）最近的空格；都满了是 -1。ok：另外再挑一挑（自己挂时，前面站不了人的格子不要）
        public int NearestFreeSlot(Vector3 p, System.Func<int, bool> ok = null)
        {
            int best = -1;
            float bd = float.MaxValue;
            for (int i = 0; i < SlotCount; i++)
            {
                if (used.Contains(i) || (ok != null && !ok(i))) continue;
                Vector3 d = Slots.GetChild(i).position - p;
                d.y = 0;
                if (d.sqrMagnitude < bd) { bd = d.sqrMagnitude; best = i; }
            }
            return best;
        }

        /// 先占住一格（自己正走过去挂的时候，别人的不会挂到这里）
        public bool Reserve(int slot)
        {
            if (slot < 0 || slot >= SlotCount || used.Contains(slot)) return false;
            used.Add(slot);
            return true;
        }

        /// 不挂了：把占着的那格放回去（已经挂上东西的不放）
        public void Unreserve(int slot)
        {
            if (!atSlot.ContainsKey(slot)) used.Remove(slot);
        }

        public bool SlotUsed(int slot) => used.Contains(slot);

        /// 绳上这一格的位置（在绳子下面 3 厘米）
        public Vector3 SlotPoint(int slot) => Slots.GetChild(Mathf.Clamp(slot, 0, SlotCount - 1)).position;

        Vector3 center;
        bool centerKnown;

        /// 这一格往外（背对树干、朝着走道）的水平方向：挂上去的布条正面朝这边。
        /// 生成场景时每一格朝向已经摆成「垂直于这一段绳子、朝外」（绳结正好套在绳上）；老场景没摆的，按离绳圈中心的方向算
        public Vector3 Outward(int slot)
        {
            var st = Slots.GetChild(Mathf.Clamp(slot, 0, SlotCount - 1));
            if (st.localRotation != Quaternion.identity)
            {
                Vector3 f = st.forward;
                f.y = 0;
                if (f.sqrMagnitude > 0.25f) return f.normalized;
            }
            if (!centerKnown && SlotCount > 0)
            {
                center = Vector3.zero;
                for (int i = 0; i < SlotCount; i++) center += Slots.GetChild(i).position;
                center /= SlotCount;
                centerKnown = true;
            }
            Vector3 d = SlotPoint(slot) - center;
            d.y = 0;
            return d.sqrMagnitude > 1e-4f ? d.normalized : Vector3.forward;
        }

        /// 某一格上挂着的东西有没有写字的贴图（测试、调试用）
        public Texture FaceAt(int slot) => atSlot.TryGetValue(slot, out var it) && it.face != null ? it.face : null;
        public GameObject ItemAt(int slot) => atSlot.TryGetValue(slot, out var it) ? it.go : null;

        // ── 布条、木牌：做出来、拿在手里、系到绳上 ──

        static MaterialPropertyBlock block;

        /// 每件自己的正面贴图、共用的背面贴图、随风摆多少：用 MaterialPropertyBlock 按子网格分别给，材质大家共用
        void Paint(GameObject go, string kind, Texture2D face, float sway)
        {
            var r = go.GetComponent<MeshRenderer>();
            if (r == null) return;
            block ??= new MaterialPropertyBlock();
            block.Clear();
            block.SetTexture("_BaseMap", face != null ? face : WishCloth.Face(kind, null));
            block.SetFloat("_Sway", sway);
            r.SetPropertyBlock(block, 0);
            block.Clear();
            block.SetTexture("_BaseMap", WishCloth.Back(kind));
            block.SetFloat("_Sway", sway);
            r.SetPropertyBlock(block, 1);
        }

        void SetFace(Item it, string tex)
        {
            if (it.go == null || it.face != null) return;
            var mask = WishCloth.DecodeMask(tex);
            if (mask == null) return;
            it.face = WishCloth.Face(it.kind, mask);
            Destroy(mask);
            faces[it.go] = it.face;
            Paint(it.go, it.kind, it.face, hangSway);
        }

        /// 做一件（还没挂上）：mask 是写了字的灰度图，没有就是素的
        GameObject MakeWish(string kind, Texture2D mask)
        {
            bool plaque = kind == "plaque";
            var mat = plaque ? plaqueMaterial : ribbonMaterial;
            var go = Make(plaque ? "Plaque" : "Ribbon", plaque ? WishCloth.PlaqueMesh() : WishCloth.RibbonMesh(), mat);
            go.GetComponent<MeshRenderer>().sharedMaterials = new[] { mat, mat };
            go.transform.localScale = plaque ? plaqueScale : ribbonScale;
            Texture2D face = mask != null ? WishCloth.Face(kind, mask) : null;
            if (face != null) faces[go] = face;
            Paint(go, kind, face, hangSway);
            return go;
        }

        /// 自己要挂的那一件：做出来，拿在手里（hand 是手腕骨，finger 是中指根），正面朝 outward
        public GameObject MakeHeld(string kind, string tex, Transform hand, Transform finger, Vector3 outward)
        {
            var mask = WishCloth.DecodeMask(tex);
            var go = MakeWish(kind, mask);
            if (mask != null) Destroy(mask);
            faces.TryGetValue(go, out var face);
            Paint(go, kind, face, heldSway);
            var hold = go.AddComponent<HandHold>();
            hold.bone = hand;
            hold.finger = finger;
            hold.worldRotation = Quaternion.LookRotation(outward);
            // 拿着绳结那一头：东西的原点（绳上那一点）在手心下面一点
            hold.offset = Vector3.down * 0.035f;
            go.transform.position = hold.Palm + hold.offset;
            go.transform.rotation = hold.worldRotation;
            return go;
        }

        /// 走去绳子那里的路上捏在右手里的样子：布条卷成一小卷（整条六十多厘米，手垂在身侧会拖到地上），卷轴顺着走路的方向；
        /// 木牌就是那块木牌（拎着绳结），板面顺着走路的方向（薄的那一边朝着腿，不蹭腿）。朝向跟着人（body）水平转
        public GameObject MakeCarry(string kind, string tex, Transform hand, Transform finger, Transform body)
        {
            GameObject go;
            if (kind == "plaque") go = MakeHeld(kind, tex, hand, finger, body.forward);
            else
            {
                go = Make("RibbonRoll", WishCloth.RollMesh(), ribbonMaterial);
                go.GetComponent<MeshRenderer>().sharedMaterials = new[] { ribbonMaterial, ribbonMaterial };
                go.transform.localScale = ribbonScale;
                Paint(go, "ribbon", null, 0f);
                var h = go.AddComponent<HandHold>();
                h.bone = hand;
                h.finger = finger;
                h.offset = Vector3.zero;
                // 握在手心里：卷轴顺着指根那一条线，卷从手心往掌心那面鼓出来，半弯的手指搭在卷上
                var anim = hand != null ? hand.GetComponentInParent<Animator>() : null;
                if (anim != null && anim.isHuman)
                {
                    h.index = anim.GetBoneTransform(HumanBodyBones.RightIndexProximal);
                    h.little = anim.GetBoneTransform(HumanBodyBones.RightLittleProximal);
                    h.grip = h.index != null && h.little != null;
                }
            }
            var hold = go.GetComponent<HandHold>();
            hold.yawFrom = body;
            hold.yawOffset = kind == "plaque" ? 90f : 0f;
            go.transform.position = hold.Palm + hold.offset;
            go.transform.rotation = hold.Wanted;
            return go;
        }

        /// 抬手要系了：手里拎着的木牌转过来正面朝外（outward），和要挂上去的那一件一样（转好了再换成它，看不出换过）
        public void TurnCarry(GameObject go, Vector3 outward, float seconds)
        {
            var hold = go != null ? go.GetComponent<HandHold>() : null;
            if (hold == null) return;
            hold.yawFrom = null;
            hold.worldRotation = Quaternion.LookRotation(outward);
            hold.turnTime = seconds;
        }

        /// 布条从卷里放开：挂点（上端）在手里不动，下面一截截垂下来（seconds 秒垂到整条）
        public IEnumerator Unfurl(GameObject go, float seconds)
        {
            if (go == null) yield break;
            Vector3 full = go.transform.localScale;
            for (float t = 0; t < seconds && go != null; t += Time.deltaTime)
            {
                float k = 1f - (1f - t / seconds) * (1f - t / seconds);
                go.transform.localScale = new Vector3(full.x, full.y * Mathf.Lerp(0.12f, 1f, k), full.z);
                yield return null;
            }
            if (go != null) go.transform.localScale = full;
        }

        /// 系结（两手在绳上打结的那一圈里）：从手里挪到绳上那一格（约 0.3 秒挪到，两手就在那儿），再绕着绳子来回拧几下，越来越轻
        public IEnumerator Tie(GameObject go, int slot, float seconds)
        {
            var hold = go.GetComponent<HandHold>();
            if (hold != null) Destroy(hold);
            Vector3 to = SlotPoint(slot);
            Quaternion r1 = Quaternion.LookRotation(Outward(slot));
            WorldAudio.Instance?.Play("sfx_cloth", 0.6f);
            for (float t = 0; t < seconds; t += Time.deltaTime)
            {
                float k = t / seconds;
                float a = Mathf.Sin(k * Mathf.PI * 5f) * 14f * (1f - k);
                go.transform.SetPositionAndRotation(Vector3.Lerp(go.transform.position, to, 1f - Mathf.Exp(-Time.deltaTime * 10f)), r1 * Quaternion.Euler(a, a * 0.3f, 0));
                yield return null;
            }
            go.transform.SetPositionAndRotation(to, r1);
        }

        /// 挂好：放到这一格上，正面朝外。mine：是自己的（不会被取下）；fresh：自己刚亲手系好的，端正、闪一下、出声
        Item Fix(GameObject go, string kind, int slot, bool mine, string id, bool fresh)
        {
            var hold = go.GetComponent<HandHold>();
            if (hold != null) Destroy(hold);
            go.transform.SetParent(transform, true);
            Vector3 to = SlotPoint(slot), outward = Outward(slot);
            // 以前挂的略微歪一点（风吹的、系的松紧不一样），刚系好的端正
            float tilt = fresh ? 0f : Random.Range(-9f, 9f);
            go.transform.SetPositionAndRotation(to, Quaternion.LookRotation(outward) * Quaternion.Euler(0, tilt, 0));
            used.Add(slot);
            faces.TryGetValue(go, out var face);
            var it = new Item { go = go, id = id ?? "", kind = kind, slot = slot, mine = mine, face = face };
            atSlot[slot] = it;
            if (it.id != "") byId[it.id] = it;
            Paint(go, kind, face, hangSway);
            if (!fresh) return it;
            if (sparkle != null)
            {
                sparkle.transform.position = to + Vector3.down * 0.25f;
                sparkle.Emit(28);
            }
            var audio = WorldAudio.Instance;
            audio?.Play(kind == "plaque" ? "sfx_wood" : "sfx_cloth", 0.9f);
            audio?.Play("sfx_sparkle", 0.5f);
            return it;
        }

        /// 自己亲手挂好的那一件（mine 为 true：刚系好的）
        public void Fix(GameObject go, string kind, int slot, bool mine) => Fix(go, kind, slot, mine, "", mine);

        /// 拿在手里还没挂上就不挂了（重新进殿时）
        public void Discard(GameObject go)
        {
            if (go == null) return;
            if (faces.TryGetValue(go, out var f)) { faces.Remove(go); if (f != null) Destroy(f); }
            Destroy(go);
        }

        static Mesh stickMesh, emberMesh, coinMesh, candleMesh, flameMesh;

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
            // 香头的火：粗一点、长一点（评审：离香炉 2.6 米看不出点着了）
            mb.Cylinder(Vector3.zero, 0.0045f, 0.016f, 6, true);
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

        /// 殿里上香用的香比院子里的（俯视时放大了）小：按真的大小略放大一点，平视近看
        public float hallIncenseScale = 1.25f;

        /// 三支点着的香，做出来
        Transform MakeSticks(float scale)
        {
            var root = new GameObject("Incense").transform;
            root.SetParent(transform, false);
            root.localScale = Vector3.one * scale;
            for (int i = -1; i <= 1; i++)
            {
                var stick = Make("Stick", StickMesh(), stickMaterial, root);
                stick.transform.localPosition = new Vector3(i * 0.012f, -0.04f, 0);
                stick.transform.localRotation = Quaternion.Euler(Random.Range(-3f, 3f), 0, i * -4f + Random.Range(-1.5f, 1.5f));
                var ember = Make("Ember", EmberMesh(), emberMaterial, stick.transform);
                ember.transform.localPosition = new Vector3(0, 0.27f, 0);
            }
            return root;
        }

        /// 殿里上香：三支点着的香拿在右手里（hand 手腕骨、finger 中指根），香头朝上
        public GameObject MakeIncenseHeld(Transform hand, Transform finger)
        {
            var root = MakeSticks(hallIncenseScale);
            var hold = root.gameObject.AddComponent<HandHold>();
            hold.bone = hand;
            hold.finger = finger;
            hold.worldRotation = Quaternion.identity;
            // 捏着香脚往上一点
            hold.offset = Vector3.down * 0.02f * hallIncenseScale;
            root.position = hold.Palm + hold.offset;
            return root.gameObject;
        }

        /// 殿里插好的香（最多留几把，旧的收掉）
        readonly List<GameObject> hallSticks = new List<GameObject>();
        /// 插了第几把：一把把绕着灰面中心排成一圈（半径 3 厘米、每把隔 60 度），三支顺着半径排开，不会插进同一个地方、互相穿过去
        int planted;

        /// 把手里的香插到殿里香炉的灰里（ash 是灰面中心）：从手里送过去、立直，香脚没进灰里
        public IEnumerator PlantIncense(GameObject go, Vector3 ash, float seconds)
        {
            if (go == null) yield break;
            var hold = go.GetComponent<HandHold>();
            if (hold != null) Destroy(hold);
            float a = (planted++ % 6) * 60f * Mathf.Deg2Rad + Random.Range(-0.08f, 0.08f);
            Vector3 radial = new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a));
            Vector3 from = go.transform.position, to = ash + radial * 0.03f + Vector3.down * 0.012f;
            // 三支顺着这一把所在的半径排开（里面那支离中心 1.5 厘米、外面那支 4.5 厘米），各自略往外斜（1、2.5、4 度）：
            // 六把绕一圈，香脚、香头都不会和别的几把碰在一起（并排横着摆的话，相邻两把挨着的那两支会斜着交叉）
            Quaternion r0 = go.transform.rotation, r1 = Quaternion.LookRotation(Vector3.Cross(radial, Vector3.up));
            var sticks = new List<(Transform t, Quaternion from, Quaternion to)>();
            for (int i = 0; i < go.transform.childCount; i++)
            {
                var st = go.transform.GetChild(i);
                float lean = 2.5f + Mathf.Sign(st.localPosition.x) * (Mathf.Abs(st.localPosition.x) > 1e-4f ? 1.5f : 0f);
                sticks.Add((st, st.localRotation, Quaternion.Euler(Random.Range(-1f, 1f), 0, -lean)));
            }
            for (float t = 0; t < seconds; t += Time.deltaTime)
            {
                float k = Mathf.SmoothStep(0, 1, t / seconds);
                go.transform.SetPositionAndRotation(Vector3.Lerp(from, to, k) + Vector3.up * Mathf.Sin(k * Mathf.PI) * 0.05f, Quaternion.Slerp(r0, r1, k));
                foreach (var s in sticks) s.t.localRotation = Quaternion.Slerp(s.from, s.to, k);
                yield return null;
            }
            go.transform.SetPositionAndRotation(to, r1);
            foreach (var s in sticks) s.t.localRotation = s.to;
            hallSticks.Add(go);
            hallBoost = 1f;
            while (hallSticks.Count > 6)
            {
                if (hallSticks[0] != null) Destroy(hallSticks[0]);
                hallSticks.RemoveAt(0);
            }
            if (sparkle != null)
            {
                sparkle.transform.position = to + Vector3.up * 0.25f;
                sparkle.Emit(10);
            }
        }

        /// 殿里香炉里插着的香（测试用）
        public int HallSticks => hallSticks.Count;

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
            // 别人的心意：写了字的贴图一帧合成一件
            if (faceQueue.Count > 0)
            {
                var (it, tex) = faceQueue.Dequeue();
                SetFace(it, tex);
            }
            if (smoke != null)
            {
                smokeBoost = Mathf.MoveTowards(smokeBoost, 0, Time.deltaTime / 40f);
                var e = smoke.emission;
                e.rateOverTime = 5f + 9f * smokeBoost;
            }
            if (hallSmoke != null)
            {
                hallBoost = Mathf.MoveTowards(hallBoost, 0, Time.deltaTime / 40f);
                var e = hallSmoke.emission;
                e.rateOverTime = 2.2f + 2f * Mathf.Min(hallSticks.Count, 3) + 6f * hallBoost;
                // 刚上过香（40 秒里）烟浓一些
                var hm = hallSmoke.main;
                hm.startColor = new Color(1f, 1f, 1f, 0.75f + 0.25f * hallBoost);
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
            GameDirector.Send($"{{\"type\":\"offered\",\"kind\":\"{f.kind}\",\"slot\":{f.slot}}}");
        }
    }
}
