using System.Collections.Generic;
using UnityEngine;

namespace Yuanjing
{
    /// 岛上有名字的小动物（狗、猫）。模型的身体、头、四条腿、尾巴是分开的部件，这里让它们各自动：
    /// 走路时腿前后摆、身子一颠一颠，高兴时尾巴摇得快，趴下时腿收起来。
    /// 平时在自己的地盘里闲逛、趴着；和你熟了（好感由服务器记着）会在你上岛时跑来迎接、跟着你走，还会叼礼物来。
    public class Critter : MonoBehaviour
    {
        public static readonly List<Critter> All = new List<Critter>();

        public string id = "", displayName = "";
        public bool cat;
        public float speed = 1.0f, homeRadius = 5f;
        public Vector3 home;
        public TextMesh nameTag;
        /// 嘴里叼着的东西、放在地上的食物（生成场景时就挂好，平时藏着）
        public GameObject giftInMouth, food;
        /// 礼物的模型（gift_<编号>）、鱼的模型（fish_<编号>）：BuildIslet 把 Toon/Models 里有的都给上。
        /// 今天的礼物是哪一件（pets 指令的第五段）就叼哪一件；喂的是鱼就在嘴边放那条鱼
        public GameObject[] giftPrefabs = new GameObject[0], fishPrefabs = new GameObject[0];
        GameObject fishFood;

        static GameObject FindPrefab(GameObject[] list, string name)
        {
            if (list != null) foreach (var g in list) if (g != null && g.name == name) return g;
            return null;
        }

        /// 叼的礼物换成 gift_<id>（dried_fish 用 gift_fish）；没有这个模型、没给编号就还叼原来那件
        void SwapGift(string id)
        {
            if (string.IsNullOrEmpty(id) || giftInMouth == null) return;
            var prefab = FindPrefab(giftPrefabs, "gift_" + (id == "dried_fish" ? "fish" : id));
            if (prefab == null || giftInMouth.name == "Gift_" + id) return;
            var old = giftInMouth.transform;
            var go = Instantiate(prefab, old.parent);
            go.name = "Gift_" + id;
            go.transform.localPosition = old.localPosition;
            go.transform.localRotation = old.localRotation;
            go.transform.localScale = old.localScale;
            int k = rest.IndexOf(old);
            if (k >= 0) rest[k] = go.transform;
            Destroy(old.gameObject);
            giftInMouth = go;
        }
        /// 带骨骼动作的那种（柴犬）：有这个就播现成的动作片段，不用下面那套「部件各自转」
        public Animation rig;
        string clipNow = "";
        float moveSpeed;

        /// 和你有多熟：0 陌生 1 认识 2 亲近 3 最好的朋友
        [System.NonSerialized] public int level;

        enum State { Idle, Walk, Lie, Greet, Happy, Eat }
        State state = State.Idle;
        float stateT, wait = 2f, phase, lie, happy, eatT, followLeft, wag;
        bool follow, greetPending, hasGift, giftDropped;
        Vector3 target;
        Transform body, head, tail;
        readonly Transform[] legs = new Transform[4];
        readonly Vector3[] legPivot = new Vector3[4];
        Vector3 headPivot, tailPivot;
        float legLen = 0.2f;
        readonly List<Transform> rest = new List<Transform>();

        void OnEnable() => All.Add(this);
        void OnDisable() => All.Remove(this);

        static Vector3 Top(Transform t)
        {
            var b = t.GetComponent<MeshFilter>().sharedMesh.bounds;
            return new Vector3(b.center.x, b.max.y, b.center.z);
        }

        void Awake()
        {
            string[] names = { "leg_fl", "leg_fr", "leg_bl", "leg_br" };
            foreach (Transform c in transform)
            {
                int k = System.Array.IndexOf(names, c.name);
                if (k >= 0)
                {
                    legs[k] = c;
                    legPivot[k] = Top(c);
                    legLen = c.GetComponent<MeshFilter>().sharedMesh.bounds.size.y;
                }
                else if (c.name == "body") body = c;
                else if (c.name == "head") head = c;
                else if (c.name == "tail") tail = c;
            }
            if (head != null)
            {
                var b = head.GetComponent<MeshFilter>().sharedMesh.bounds;
                headPivot = new Vector3(b.center.x, b.min.y + b.size.y * 0.25f, b.min.z + b.size.z * 0.2f);
                if (giftInMouth != null) rest.Add(giftInMouth.transform);
            }
            if (tail != null)
            {
                var b = tail.GetComponent<MeshFilter>().sharedMesh.bounds;
                tailPivot = new Vector3(b.center.x, b.min.y + b.size.y * 0.2f, b.max.z);
            }
            if (home == Vector3.zero) home = transform.position;
            phase = Random.value * 10f;
            wait = Random.Range(1f, 6f);
            if (giftInMouth != null) giftInMouth.SetActive(false);
            if (food != null) food.SetActive(false);
            if (nameTag != null)
            {
                (nameTag.GetComponent<NameTag>() ?? nameTag.gameObject.AddComponent<NameTag>()).Set(displayName, new Color(1f, 0.85f, 0.66f));
                nameTag.gameObject.SetActive(false);
            }
        }

        /// 进岛时由 Flutter 告诉：和这只有多熟、要不要来迎接、今天有没有礼物
        public void Bond(int newLevel, bool greet, bool gift, string giftId = null)
        {
            level = newLevel;
            if (gift) SwapGift(giftId);
            greetPending = greet && level >= 2;
            hasGift = gift && level >= 2;
            giftDropped = false;
            if (giftInMouth != null) giftInMouth.SetActive(hasGift);
            follow = level >= 3;
            if (greetPending) { state = State.Greet; stateT = 0; }
        }

        /// 摸它、喂它
        public void React(string action, int newLevel, string item = null)
        {
            level = Mathf.Max(level, newLevel);
            var p = Player();
            if (p != null) Face(p.position - transform.position, 1f);
            if (action == "feed" && food != null)
            {
                Vector3 at = Ground(transform.position + transform.forward * 0.42f * transform.localScale.x);
                // 喂的是钓上来的鱼（item 是鱼的编号）：嘴边地上放那条鱼（侧躺着），不摆食盆；别的（food_*、空）照旧摆食盆
                if (fishFood != null) Destroy(fishFood);
                fishFood = null;
                var fp = FindPrefab(fishPrefabs, "fish_" + item);
                if (!string.IsNullOrEmpty(item) && fp != null)
                {
                    fishFood = Instantiate(fp);
                    fishFood.name = "FoodFish";
                    // 鱼的原点在嘴、头朝 +z、背朝 +y：侧躺（绕 z 转 90 度），身子中段摆在食盆的位置，头斜着朝向它
                    var rot = Quaternion.Euler(0, transform.eulerAngles.y + 115f, 0);
                    fishFood.transform.SetPositionAndRotation(at + rot * Vector3.back * 0.09f + Vector3.up * 0.022f, rot * Quaternion.Euler(0, 0, 90f));
                    food.SetActive(false);
                }
                else
                {
                    food.SetActive(true);
                    food.transform.SetParent(null, true);
                    food.transform.position = at;
                    food.transform.rotation = Quaternion.identity;
                }
                state = State.Eat;
                eatT = 0;
            }
            else
            {
                state = State.Happy;
                stateT = 0;
                Ambience.Hearts(transform.position + Vector3.up * 0.7f, 4);
            }
            followLeft = Mathf.Max(followLeft, 40f);
        }

        static Transform Player() => GameDirector.Instance != null && GameDirector.Instance.player != null ? GameDirector.Instance.player.transform : null;

        static Vector3 Ground(Vector3 p)
        {
            if (Physics.Raycast(p + Vector3.up * 1.2f, Vector3.down, out var hit, 3f, ~(1 << 2), QueryTriggerInteraction.Ignore)) p.y = hit.point.y;
            return p;
        }

        void Face(Vector3 dir, float k)
        {
            dir.y = 0;
            if (dir.sqrMagnitude < 1e-4f) return;
            transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(dir), k);
        }

        /// 朝目标走一步，返回还有多远
        float StepTo(Vector3 to, float v, float dt)
        {
            Vector3 d = to - transform.position;
            d.y = 0;
            float dist = d.magnitude;
            if (dist < 0.05f) return dist;
            Face(d, 1 - Mathf.Exp(-8f * dt));
            moveSpeed = v;
            Vector3 p = transform.position + d / dist * Mathf.Min(dist, v * dt);
            transform.position = Ground(p);
            phase += v * dt * (cat ? 13f : 11f);
            return dist;
        }

        bool Walkable(Vector3 p)
        {
            // 脚下得是岛上的地面（不是水底），也别走进建筑、树、香炉里
            if (!Physics.Raycast(p + Vector3.up * 1.5f, Vector3.down, out var hit, 3f, ~(1 << 2), QueryTriggerInteraction.Ignore)) return false;
            if (hit.point.y < -0.08f || hit.point.y > 0.5f || hit.normal.y < 0.8f) return false;
            var gd = GameDirector.Instance;
            if (gd != null)
                foreach (var o in gd.obstacles)
                    if (new Vector2(p.x - o.center.x, p.z - o.center.z).magnitude < o.radius + 0.3f) return false;
            return !Physics.CheckSphere(p + Vector3.up * 0.5f, 0.25f, ~(1 << 2), QueryTriggerInteraction.Ignore);
        }

        void Update()
        {
            float dt = Time.deltaTime;
            stateT += dt;
            var player = Player();
            float toPlayer = player != null ? Vector3.Distance(player.position, transform.position) : 99f;
            bool moving = false;
            float wantLie = 0, wantHappy = 0;

            switch (state)
            {
                case State.Greet:
                    // 跑过来迎接：到跟前跳两下，叼着礼物的话放在你脚边
                    if (player == null) { state = State.Idle; break; }
                    if (toPlayer > 1.25f)
                    {
                        StepTo(player.position, speed * 2.4f, dt);
                        moving = true;
                    }
                    else
                    {
                        greetPending = false;
                        state = State.Happy;
                        stateT = 0;
                        Ambience.Hearts(transform.position + Vector3.up * 0.7f, 5);
                        if (hasGift && !giftDropped) DropGift();
                        followLeft = follow ? 1e9f : 70f;
                    }
                    break;
                case State.Happy:
                    wantHappy = 1;
                    if (player != null) Face(player.position - transform.position, 1 - Mathf.Exp(-6f * dt));
                    if (stateT > 2.6f) { state = State.Idle; wait = Random.Range(1f, 3f); }
                    break;
                case State.Eat:
                    eatT += dt;
                    if (eatT > 3.2f)
                    {
                        if (food != null) food.SetActive(false);
                        if (fishFood != null) { Destroy(fishFood); fishFood = null; }
                        state = State.Happy;
                        stateT = 0;
                        Ambience.Hearts(transform.position + Vector3.up * 0.7f, 6);
                    }
                    break;
                case State.Walk:
                    moving = true;
                    if (StepTo(target, speed, dt) < 0.12f || stateT > 14f) { state = State.Idle; wait = Random.Range(2f, 7f); stateT = 0; }
                    break;
                case State.Lie:
                    wantLie = 1;
                    if (stateT > wait && !(GameDirector.Instance != null && GameDirector.Instance.PlayerResting && followLeft > 0)) { state = State.Idle; wait = Random.Range(1f, 3f); stateT = 0; }
                    break;
                default:
                    if (followLeft > 0 && player != null)
                    {
                        // 跟着你：离远了就小跑跟上；你坐下，它就在旁边趴下
                        followLeft -= dt;
                        if (toPlayer > 2.4f)
                        {
                            Vector3 side = player.right * (id.GetHashCode() % 2 == 0 ? 0.9f : -0.9f) - player.forward * 0.7f;
                            StepTo(player.position + side, speed * (toPlayer > 5f ? 2.4f : 1.5f), dt);
                            moving = true;
                        }
                        else if (GameDirector.Instance != null && GameDirector.Instance.PlayerResting && stateT > 1.5f)
                        {
                            state = State.Lie;
                            stateT = 0;
                            wait = 8f;
                        }
                    }
                    else if (stateT > wait)
                    {
                        stateT = 0;
                        if (Random.value < (cat ? 0.45f : 0.3f))
                        {
                            state = State.Lie;
                            wait = Random.Range(6f, 16f);
                        }
                        else
                        {
                            for (int k = 0; k < 8; k++)
                            {
                                Vector2 r = Random.insideUnitCircle * homeRadius;
                                Vector3 p = home + new Vector3(r.x, 0, r.y);
                                if (!Walkable(p) || Physics.Linecast(transform.position + Vector3.up * 0.3f, p + Vector3.up * 0.3f, ~(1 << 2), QueryTriggerInteraction.Ignore)) continue;
                                target = p;
                                state = State.Walk;
                                break;
                            }
                            wait = Random.Range(2f, 6f);
                        }
                    }
                    break;
            }

            lie = Mathf.MoveTowards(lie, wantLie, dt * 2.2f);
            happy = Mathf.MoveTowards(happy, wantHappy, dt * 4f);
            Pose(moving, dt);

            if (nameTag != null)
            {
                bool show = toPlayer < 4.5f;
                if (nameTag.gameObject.activeSelf != show) nameTag.gameObject.SetActive(show);
                if (show && Camera.main != null)
                {
                    nameTag.transform.position = transform.position + Vector3.up * (0.95f * transform.localScale.x - lie * 0.1f);
                    nameTag.transform.rotation = Camera.main.transform.rotation;
                    // 远近看起来差不多大（俯视时镜头在二十多米外，凑近看时只有一两米）
                    float cd = Vector3.Distance(Camera.main.transform.position, nameTag.transform.position);
                    nameTag.transform.localScale = Vector3.one * Mathf.Clamp(cd * 0.055f, 0.14f, 1.4f);
                }
            }
        }

        void DropGift()
        {
            giftDropped = true;
            if (giftInMouth != null)
            {
                giftInMouth.transform.SetParent(null, true);
                giftInMouth.transform.position = Ground(transform.position + transform.forward * 0.45f * transform.localScale.x) + Vector3.up * 0.02f;
                giftInMouth.transform.rotation = Quaternion.Euler(0, Random.Range(0, 360f), 0);
                rest.Remove(giftInMouth.transform);
            }
            GameDirector.Send($"{{\"type\":\"petGift\",\"id\":\"{id}\"}}");
        }

        static void Pivot(Transform t, Vector3 pivot, Quaternion r, Vector3 offset, float scaleY = 1f)
        {
            if (t == null) return;
            t.localRotation = r;
            t.localScale = new Vector3(1, scaleY, 1);
            Vector3 p = r * Vector3.Scale(pivot, new Vector3(1, scaleY, 1));
            t.localPosition = pivot - p + offset;
        }

        /// 带骨骼的：按状态挑一段动作，淡入淡出地换
        static readonly int CombId = Shader.PropertyToID("_FurComb");
        MaterialPropertyBlock combBlock;

        void PoseRig(bool moving)
        {
            // 毛往身后、往下梳
            if (combBlock == null) combBlock = new MaterialPropertyBlock();
            Vector3 comb = (-transform.forward * 0.8f + Vector3.down * 0.6f).normalized;
            foreach (var r in rig.GetComponentsInChildren<SkinnedMeshRenderer>())
            {
                r.GetPropertyBlock(combBlock);
                combBlock.SetVector(CombId, comb);
                r.SetPropertyBlock(combBlock);
            }
            bool fast = moving && moveSpeed > speed * 1.8f;
            string clip = state == State.Eat ? "Eating" : state == State.Lie ? "Idle_2_HeadLow" : moving ? (fast ? "Gallop" : "Walk") : happy > 0.1f ? "Idle_2" : "Idle";
            if (rig.GetClip(clip) == null) clip = "Idle";
            if (clip != clipNow)
            {
                rig.CrossFade(clip, 0.25f);
                clipNow = clip;
            }
            // 步子的快慢跟着实际走的速度，脚才不打滑
            var st = rig[clip];
            if (st != null) st.speed = moving ? Mathf.Clamp(moveSpeed / (fast ? 2.6f : 1.0f), 0.7f, 1.8f) : 1f;
            // 高兴了原地蹦两下
            rig.transform.localPosition = Vector3.up * (happy * Mathf.Abs(Mathf.Sin(Time.time * 9f)) * 0.07f);
        }

        void Pose(bool moving, float dt)
        {
            if (rig != null) { PoseRig(moving); return; }
            float t = Time.time;
            float swing = moving ? 30f : 0f;
            // 趴下：腿收短，整个身子落下去
            float fold = Mathf.Lerp(1f, 0.28f, lie);
            float drop = legLen * (1 - fold) * 0.92f;
            float bob = moving ? Mathf.Abs(Mathf.Sin(phase)) * 0.014f : 0;
            float hop = happy * Mathf.Abs(Mathf.Sin(t * 9f)) * 0.07f;
            Vector3 off = new Vector3(0, bob + hop - drop, 0);
            for (int i = 0; i < 4; i++)
            {
                float ph = phase + ((i == 0 || i == 3) ? 0 : Mathf.PI);
                Pivot(legs[i], legPivot[i], Quaternion.Euler(Mathf.Sin(ph) * swing, 0, 0), off, fold);
            }
            if (body != null) body.localPosition = off;
            // 头：平时慢慢左右看；吃东西时一下一下低头
            float eat = state == State.Eat ? 1f : 0f;
            float nod = eat * (32f + 10f * Mathf.Sin(t * 11f)) + lie * 8f;
            float look = (1 - eat) * Mathf.Sin(t * 0.7f + phase) * 14f * (moving ? 0.3f : 1f);
            Pivot(head, headPivot, Quaternion.Euler(nod, look, 0), off);
            // 尾巴：狗高兴了摇得飞快，猫慢悠悠地甩
            wag = Mathf.MoveTowards(wag, happy > 0.1f || state == State.Eat ? 1f : moving ? 0.5f : 0.25f, dt * 3f);
            float w = cat ? Mathf.Sin(t * 1.8f + phase) * 18f : Mathf.Sin(t * Mathf.Lerp(5f, 17f, wag)) * Mathf.Lerp(10f, 32f, wag);
            Pivot(tail, tailPivot, Quaternion.Euler(cat ? Mathf.Sin(t * 1.1f) * 8f : 0, w, 0), off);
            if (giftInMouth != null && giftInMouth.transform.parent == transform && head != null)
            {
                // 叼在嘴里的东西跟着头
                Vector3 mouth = headPivot + new Vector3(0, 0.02f, 0.26f);
                giftInMouth.transform.localPosition = head.localPosition + head.localRotation * mouth;
                giftInMouth.transform.localRotation = head.localRotation * Quaternion.Euler(0, 90, 0);
            }
        }
    }
}
