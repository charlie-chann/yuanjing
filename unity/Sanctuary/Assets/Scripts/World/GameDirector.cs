using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace Yuanjing
{
    /// 可以走过去的一个地点：站在哪、看向哪
    [Serializable]
    public class Spot
    {
        public string name;
        public Vector3 floor, look;
        public float eye = 1.62f;
        /// 点画面时，离看向的那一点多近算点中了它（米）。树冠大就给大一些。
        public float pick = 1.5f;
    }

    /// 院子里要绕开的东西（香炉、树池、石灯笼、水池），按圆算
    [Serializable]
    public class Obstacle
    {
        public Vector3 center;
        public float radius;
    }

    /// 殿里的总控：收 Flutter 发来的指令（进场、换天色天气、走动、坐下、做动作、留心意），
    /// 指挥自己的小人和第三人称镜头，再把结果告诉 Flutter。寺庙和教堂用同一份，只是地点和路线的数据不同。
    ///
    /// Flutter → 这里（JSON，cmd 字段）：
    ///   enter    {scene, time, weather, seed, name} 进场。seed 是先摆几位本地 NPC，name 是自己头顶的名字
    ///   move     {x, y}                       摇杆（-1..1，y 朝前），松手发 0,0
    ///   sky      {time, weather, instant}     换天色天气
    ///   goto     {spot}                       走到某个地点
    ///   sit      {seat}                       找位置坐下，seat 不给就挑最近的空位
    ///   act      {action}                     bow 鞠躬 / kneel 跪拜 / pray 合掌 / meditate 静坐
    ///   offer    {kind}                       ribbon 红布条 / plaque 木牌 / incense 上香 / coin 抛硬币 / candle 点蜡烛
    ///   offerings{list:"3,7,12", kind}        别人已经挂着的
    ///   pilgrims {list:"id:座位:是不是NPC:名字|..."} 现在殿里有谁
    ///   pact     {id, action}                 某个人做了动作
    ///   look     {dx, dy}                     拖动画面，镜头绕着人转
    ///   tap      {x, y}                       点了画面上某处（0..1，左上角是原点）
    ///   audio    {on, volume}                 声音开关
    ///   bell                                  敲一下钟
    /// 这里 → Flutter（type 字段）：entered moving arrived（走到或走近了某个地点，spot 为空是在院子里随便走）seated actionDone offered thunder
    public class GameDirector : MonoBehaviour
    {
        public static GameDirector Instance { get; private set; }

        public Folk player;
        public PlayerCamera cam;
        public Pilgrims pilgrims;
        public Offerings offerings;
        public WorldAudio sound;

        public Spot[] spots = new Spot[0];
        public Obstacle[] obstacles = new Obstacle[0];
        public string startSpot = "gate", firstSpot = "court";

        /// 院子里的集散点：从座位区出来先到这里
        public Vector3 hub;
        /// 座位区的过道：一条直线。从座位先横着走到过道上，再沿过道走到出口。
        public Vector3 aislePoint, aisleDir = Vector3.right;
        /// 从过道走到集散点途中要经过的点。过道两边各一条。
        public Vector3[] seatExitNeg = new Vector3[0], seatExitPos = new Vector3[0];
        public Vector3 seatLook;
        /// 坐下以后朝哪看：0 是所有座位都看向 seatLook，1 是各自朝正前方（座位前面有柱子、墙垛时用大一些，免得被挡住）
        public float seatStraight;
        public float seatDrop = 0.16f;
        /// 坐的是蒲团（盘坐）还是长椅
        public bool benchSeats;
        /// 走到离地点多近算到了
        public float nearRadius = 2.0f;
        /// 往里走过这条线就算进了院子（不填就用集散点的位置）
        public float courtMinZ = float.NaN;
        public string bell = "sfx_bell_temple";

        [Serializable]
        class Msg
        {
            public string cmd, scene, time, weather, spot, action, kind, id, list, name;
            public int seat = -1, slot = -1, seed;
            public float dx, dy, x, y, volume = 1;
            public bool instant, on = true;
        }

        // 换殿：先记下进场指令，新场景加载好以后再执行
        static string pendingEnter;
        static bool loading;

        string at = "";
        int mySeat = -1;
        bool acting, autoWalk, synced;
        Action onArrive;
        Vector2 stick;
        float nextChime = 30, nextBell = 170;

        void Awake()
        {
            Instance = this;
            Application.targetFrameRate = 60;
        }

        void OnEnable()
        {
            Bridge.Received += OnMessage;
        }

        void OnDisable()
        {
            Bridge.Received -= OnMessage;
        }

        void Start()
        {
            player.Arrived += () =>
            {
                autoWalk = false;
                FreeMove();
                var cb = onArrive;
                onArrive = null;
                cb?.Invoke();
            };
            player.Step += () => sound.Step();
            if (!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("YJ_PROBE"))) gameObject.AddComponent<RenderProbe>();
            if (TimeWeather.Instance != null) TimeWeather.Instance.Thunder += () => Send("{\"type\":\"thunder\"}");
            var s = Find(startSpot);
            if (s != null) PlaceAt(s);
            loading = false;
            if (pendingEnter != null)
            {
                string json = pendingEnter;
                pendingEnter = null;
                OnMessage(json);
            }
        }

        /// 回到用摇杆自由走的状态（坐着、跪着时不开碰撞胶囊）
        void FreeMove()
        {
            if (player.controller != null && !player.controller.enabled && mySeat < 0 && !acting && !autoWalk) player.controller.enabled = true;
        }

        /// 别的脚本要绕开院子里的东西走路时用
        public List<Vector3> PlanPath(Vector3 a, Vector3 b) => Plan(a, b);

        /// 直接把人放到某个地点，镜头摆到身后
        void PlaceAt(Spot s)
        {
            var cc = player.controller;
            if (cc != null) cc.enabled = false;
            (cc != null ? cc.transform : player.transform).position = s.floor;
            Vector3 d = s.look - s.floor;
            d.y = 0;
            float yaw = Quaternion.LookRotation(d.sqrMagnitude > 0.01f ? d : Vector3.forward).eulerAngles.y;
            player.transform.rotation = Quaternion.Euler(0, yaw, 0);
            player.FaceYaw(yaw);
            if (cc != null) cc.enabled = true;
            cam.Snap(yaw);
        }

        /// 自己放的东西（布条、香、硬币）从哪里出手：人胸前
        public Vector3 HandPoint() => player.transform.position + Vector3.up * 0.75f + player.transform.forward * 0.25f;

        public static void Send(string json) => Bridge.Send(json);

        Spot Find(string name)
        {
            foreach (var s in spots) if (s.name == name) return s;
            return null;
        }

        void OnMessage(string json)
        {
            Msg m;
            try { m = JsonUtility.FromJson<Msg>(json); }
            catch (Exception e)
            {
                Debug.LogWarning("[yuanjing] 收到的指令看不懂：" + json + " " + e.Message);
                return;
            }
            if (m == null || string.IsNullOrEmpty(m.cmd) || loading) return;
            if (m.cmd == "enter" && !string.IsNullOrEmpty(m.scene) && m.scene != SceneManager.GetActiveScene().name)
            {
                pendingEnter = json;
                loading = true;
                SceneManager.LoadScene(m.scene);
                return;
            }
            switch (m.cmd)
            {
                case "enter": Enter(m); break;
                case "sky": Sky(m, m.instant); break;
                case "goto": Go(m.spot); break;
                case "sit": Sit(m.seat); break;
                case "act": Act(m.action); break;
                case "offer": Offer(m.kind); break;
                case "offerings":
                    foreach (string part in (m.list ?? "").Split(','))
                        if (int.TryParse(part, out int slot)) offerings.Place(string.IsNullOrEmpty(m.kind) ? "ribbon" : m.kind, slot);
                    break;
                case "pilgrims": SyncPilgrims(m.list ?? ""); break;
                case "pact": pilgrims.Act(m.id, m.action); break;
                case "look": cam.Look(m.dx, m.dy); break;
                case "move": Move(m.x, m.y); break;
                case "tap": Tap(m.x, m.y); break;
                case "audio":
                    sound.SetMuted(!m.on);
                    sound.master = Mathf.Clamp01(m.volume);
                    break;
                case "bell": sound.Play(bell, 0.8f); break;
            }
        }

        static bool Parse<T>(string s, out T value) where T : struct
        {
            value = default;
            return !string.IsNullOrEmpty(s) && Enum.TryParse(s, true, out value);
        }

        void Sky(Msg m, bool instant)
        {
            var tw = TimeWeather.Instance;
            if (tw == null) return;
            var t = Parse(m.time, out DayTime pt) ? pt : tw.time;
            var w = Parse(m.weather, out Weather pw) ? pw : tw.weather;
            if (instant) tw.ApplyImmediate(t, w);
            else tw.Set(t, w);
        }

        void Enter(Msg m)
        {
            StopAllCoroutines();
            acting = false;
            autoWalk = false;
            onArrive = null;
            Sky(m, true);
            player.SetPose(Folk.Pose.None);
            player.StopWalking();
            PlaceAt(Find(startSpot));
            player.SetName(m.name ?? "", new Color(1f, 0.86f, 0.55f));
            at = startSpot;
            mySeat = -1;
            synced = false;
            if (m.seed > 0) pilgrims.SeedLocal(m.seed, -1);
            pilgrims.StartWanderers();
            Send($"{{\"type\":\"entered\",\"scene\":\"{SceneManager.GetActiveScene().name}\",\"seats\":{pilgrims.SeatCount},\"slots\":{offerings.SlotCount}}}");
            StartCoroutine(WalkIn());
        }

        IEnumerator WalkIn()
        {
            yield return new WaitForSeconds(0.6f);
            sound.Play(bell, 0.55f);
            yield return new WaitForSeconds(0.8f);
            Go(firstSpot);
        }

        /// 摇杆：按镜头的朝向换算成人走的方向。坐着、跪着时一推摇杆就起身
        void Move(float x, float y)
        {
            stick = Vector2.ClampMagnitude(new Vector2(x, y), 1f);
            if (stick.sqrMagnitude < 0.0004f) return;
            if (acting) return;
            if (mySeat >= 0)
            {
                // 坐着推摇杆：先起身走到过道上，再交给摇杆
                Vector3 seat = pilgrims.Seat(mySeat).position;
                player.SetPose(Folk.Pose.None);
                mySeat = -1;
                cam.Focus(0);
                Send("{\"type\":\"stood\"}");
                Walk(new List<Vector3> { AisleNode(seat) }, AisleNode(seat) + aisleDir, "", () => { });
                return;
            }
            if (autoWalk)
            {
                // 正在自动走：中途推摇杆，就停下改成自己走
                autoWalk = false;
                onArrive = null;
                player.StopWalking();
                FreeMove();
            }
        }

        // ── 走路 ──

        Vector3 AisleNode(Vector3 seat) => aislePoint + aisleDir * Vector3.Dot(seat - aislePoint, aisleDir);

        bool Positive(Vector3 seat) => Vector3.Dot(seat - aislePoint, aisleDir) >= 0;

        Vector3 SeatFloor(int seat) => pilgrims.Seat(seat).position + Vector3.down * seatDrop;

        /// 从一点走到另一点，碰到要绕开的东西就从它旁边绕
        List<Vector3> Plan(Vector3 a, Vector3 b, int depth = 0)
        {
            var res = new List<Vector3>();
            if (depth < 4)
            {
                Vector2 A = new Vector2(a.x, a.z), B = new Vector2(b.x, b.z), ab = B - A;
                if (ab.sqrMagnitude > 0.01f)
                    foreach (var o in obstacles)
                    {
                        Vector2 C = new Vector2(o.center.x, o.center.z);
                        float t = Vector2.Dot(C - A, ab) / ab.sqrMagnitude;
                        if (t <= 0.03f || t >= 0.97f) continue;
                        Vector2 closest = A + ab * t;
                        float d = Vector2.Distance(closest, C);
                        if (d >= o.radius) continue;
                        Vector2 dir = d > 0.02f ? (closest - C) / d : new Vector2(-ab.y, ab.x).normalized;
                        Vector2 w = C + dir * (o.radius + 0.3f);
                        var mid = new Vector3(w.x, Mathf.Lerp(a.y, b.y, t), w.y);
                        res.AddRange(Plan(a, mid, depth + 1));
                        res.AddRange(Plan(mid, b, depth + 1));
                        return res;
                    }
            }
            res.Add(b);
            return res;
        }

        void Walk(List<Vector3> path, Vector3 look, string to, Action arrived)
        {
            // 去掉挨得太近的点
            var clean = new List<Vector3>();
            Vector3 last = player.transform.position;
            foreach (var p in path)
            {
                if (Vector3.Distance(p, last) < 0.08f) continue;
                clean.Add(p);
                last = p;
            }
            if (clean.Count == 0)
            {
                arrived?.Invoke();
                return;
            }
            onArrive = () =>
            {
                player.FaceTowards(look);
                Vector3 d = look - player.transform.position;
                cam.Settle(Quaternion.LookRotation(new Vector3(d.x, 0, d.z)).eulerAngles.y);
                arrived?.Invoke();
            };
            autoWalk = true;
            // 按规划好的路线走时不用碰撞胶囊（路线已经绕开了东西；坐上长椅也不会被挡）
            if (player.controller != null) player.controller.enabled = false;
            player.Walk(clean);
            Send($"{{\"type\":\"moving\",\"to\":\"{to}\"}}");
        }

        /// 从现在坐的位置走出座位区，一直到集散点
        void LeaveSeat(List<Vector3> path)
        {
            Vector3 seat = SeatFloor(mySeat);
            path.Add(AisleNode(seat));
            path.AddRange(Positive(seat) ? seatExitPos : seatExitNeg);
            path.Add(hub);
        }

        bool Busy => acting;

        public void Go(string name)
        {
            var s = Find(name);
            if (s == null || Busy) return;
            var path = new List<Vector3>();
            Vector3 from = player.transform.position;
            if (mySeat >= 0)
            {
                LeaveSeat(path);
                from = hub;
            }
            path.AddRange(Plan(from, s.floor));
            if (mySeat >= 0) player.SetPose(Folk.Pose.None);
            mySeat = -1;
            cam.Focus(0);
            Walk(path, s.look, name, () =>
            {
                at = name;
                Send($"{{\"type\":\"arrived\",\"spot\":\"{name}\"}}");
            });
        }

        public void Sit(int seat)
        {
            if (Busy || pilgrims.SeatCount == 0) return;
            if (seat < 0 || seat >= pilgrims.SeatCount || pilgrims.Occupied(seat))
            {
                // 挑离自己最近的空位
                float best = float.MaxValue;
                seat = -1;
                for (int i = 0; i < pilgrims.SeatCount; i++)
                {
                    if (i == mySeat || pilgrims.Occupied(i)) continue;
                    float d = Vector3.Distance(pilgrims.Seat(i).position, player.transform.position);
                    if (d < best)
                    {
                        best = d;
                        seat = i;
                    }
                }
                if (seat < 0) return;
            }
            if (seat == mySeat) return;
            Vector3 target = SeatFloor(seat);
            bool pos = Positive(target);
            var path = new List<Vector3>();
            if (mySeat >= 0)
            {
                Vector3 cur = SeatFloor(mySeat);
                path.Add(AisleNode(cur));
                if (Positive(cur) != pos)
                {
                    // 换到过道另一边：先出去，再从那边进来
                    path.AddRange(Positive(cur) ? seatExitPos : seatExitNeg);
                    var back = new List<Vector3>(pos ? seatExitPos : seatExitNeg);
                    back.Reverse();
                    path.AddRange(back);
                }
            }
            else
            {
                path.AddRange(Plan(player.transform.position, hub));
                var back = new List<Vector3>(pos ? seatExitPos : seatExitNeg);
                back.Reverse();
                path.AddRange(back);
            }
            path.Add(AisleNode(target));
            path.Add(target);
            player.SetPose(Folk.Pose.None);
            mySeat = -1;
            cam.Focus(0);
            int chosen = seat;
            Vector3 look = new Vector3(Mathf.Lerp(seatLook.x, target.x, seatStraight), seatLook.y, seatLook.z);
            // 走到座位上方再坐下：最后一步落在座位点上（蒲团或长椅的面）
            path[path.Count - 1] = pilgrims.Seat(seat).position;
            Walk(path, look, "seat", () =>
            {
                mySeat = chosen;
                at = "seat";
                player.SetPose(benchSeats ? Folk.Pose.Bench : Folk.Pose.CrossLegged);
                cam.Focus(0.6f);
                sound.Play("sfx_cloth", 0.5f);
                Send($"{{\"type\":\"seated\",\"seat\":{chosen}}}");
            });
        }

        // ── 动作 ──

        void Act(string action)
        {
            if (Busy || string.IsNullOrEmpty(action))
            {
                // 这会儿做不了也回一声，免得界面一直等
                Send($"{{\"type\":\"actionDone\",\"action\":\"{action}\",\"skipped\":true}}");
                return;
            }
            StartCoroutine(DoAct(action));
        }

        /// 鞠躬的节奏：俯下去、停一下、起来
        IEnumerator BowOnce(float down, float hold, float up)
        {
            for (float t = 0; t < down; t += Time.deltaTime) { player.SetBow(t / down); yield return null; }
            player.SetBow(1);
            yield return new WaitForSeconds(hold);
            for (float t = 0; t < up; t += Time.deltaTime) { player.SetBow(1 - t / up); yield return null; }
            player.SetBow(0);
        }

        IEnumerator DoAct(string action)
        {
            acting = true;
            player.StopWalking();
            autoWalk = false;
            bool seated = mySeat >= 0;
            cam.Focus(1f);
            var before = player.pose;
            switch (action)
            {
                case "bow":
                    if (!seated) player.SetPose(Folk.Pose.Bow);
                    yield return new WaitForSeconds(0.35f);
                    yield return BowOnce(1.1f, 0.7f, 1.2f);
                    break;
                case "pray":
                    // 合掌：低头，停几秒
                    sound.Play("sfx_bowl", 0.6f);
                    if (!seated) player.SetPose(Folk.Pose.Gassho);
                    else player.SetBow(0.01f);
                    yield return new WaitForSeconds(0.6f);
                    yield return BowOnce(1.2f, 4.5f, 1.2f);
                    break;
                case "kneel":
                    // 跪下，三拜，起来
                    player.SetPose(Folk.Pose.Kneel);
                    sound.Play("sfx_cloth", 0.5f);
                    yield return new WaitForSeconds(1.2f);
                    player.SetPose(Folk.Pose.KneelBow);
                    for (int i = 0; i < 3; i++) yield return BowOnce(1.4f, 1.0f, 1.3f);
                    player.SetPose(Folk.Pose.Kneel);
                    yield return new WaitForSeconds(0.6f);
                    break;
                case "meditate":
                    // 静坐的引导和计时在 Flutter 那边，这里只敲一下磬；没坐着就原地合掌
                    sound.Play("sfx_bowl", 0.7f);
                    if (!seated) player.SetPose(Folk.Pose.Gassho);
                    break;
            }
            player.SetBow(0);
            if (action != "meditate") player.SetPose(seated ? before : Folk.Pose.None);
            if (action != "meditate") cam.Focus(seated ? 0.6f : 0f);
            acting = false;
            Send($"{{\"type\":\"actionDone\",\"action\":\"{action}\"}}");
        }

        void Offer(string kind)
        {
            if (Busy) return;
            player.StopWalking();
            cam.Focus(0.75f);
            switch (kind)
            {
                case "ribbon":
                case "plaque":
                    offerings.Hang(kind, offerings.FreeSlot(), true);
                    break;
                case "incense":
                    offerings.Incense(true);
                    break;
                case "coin":
                    offerings.Coin(true);
                    break;
                case "candle":
                    offerings.Candle(offerings.FreeSlot(), true);
                    break;
            }
        }

        void SyncPilgrims(string list)
        {
            var present = new HashSet<string>();
            foreach (string item in list.Split('|'))
            {
                var f = item.Split(':');
                if (f.Length < 2 || !int.TryParse(f[1], out int seat)) continue;
                if (seat == mySeat) continue;
                present.Add(f[0]);
                // 进殿后第一次拿到的名单：这些人本来就在，直接坐在位子上；之后新来的才从山门走进来
                pilgrims.Place(f[0], seat, f.Length > 2 && f[2] == "1", f.Length > 3 ? f[3] : "", !synced);
            }
            synced = true;
            pilgrims.Sync(present);
        }

        /// 点画面：点中某个地点（树、香炉、大殿……）就走过去，点中空蒲团就去坐
        void Tap(float x, float y)
        {
            if (Busy || Camera.main == null) return;
            Ray ray = Camera.main.ViewportPointToRay(new Vector3(x, 1f - y, 0));
            // 一个点离这条视线有多远；在镜头背后的不算
            float Miss(Vector3 p)
            {
                float along = Vector3.Dot(p - ray.origin, ray.direction);
                return along < 0.5f ? float.MaxValue : Vector3.Distance(ray.origin + ray.direction * along, p);
            }
            float best = 1f;
            string spot = null;
            int seat = -1;
            foreach (var s in spots)
            {
                if (s.name == at || s.name == startSpot || s.pick <= 0) continue;
                float score = Mathf.Min(Miss(s.look) / s.pick, Miss(s.floor) / 1.0f);
                if (score < best)
                {
                    best = score;
                    spot = s.name;
                }
            }
            for (int i = 0; i < pilgrims.SeatCount; i++)
            {
                if (i == mySeat || pilgrims.Occupied(i)) continue;
                float score = Miss(pilgrims.Seat(i).position) / 0.42f;
                if (score < best)
                {
                    best = score;
                    spot = null;
                    seat = i;
                }
            }
            if (seat >= 0) Sit(seat);
            else if (spot != null) Go(spot);
            else if (Physics.Raycast(ray, out var hit, 90f, ~(1 << 2), QueryTriggerInteraction.Ignore) && hit.normal.y > 0.7f)
            {
                // 点了地面：走过去
                if (mySeat >= 0) { player.SetPose(Folk.Pose.None); mySeat = -1; }
                cam.Focus(0);
                var path = Plan(player.transform.position, hit.point);
                Walk(path, hit.point + (hit.point - player.transform.position).normalized, "", () => { });
            }
        }

        void Update()
        {
            float dt = Time.deltaTime;
            // 摇杆：按镜头朝向走
            if (!autoWalk && !acting && mySeat < 0)
            {
                FreeMove();
                // 一推摇杆走开，镜头就回到平常的远近
                if (stick.sqrMagnitude > 0.01f) cam.Focus(0);
                Quaternion yaw = Quaternion.Euler(0, cam.Yaw, 0);
                Vector3 v = yaw * new Vector3(stick.x, 0, stick.y) * player.walkSpeed * 1.25f;
                player.Drive(v);
            }
            // 离哪个地点近，就算在哪；走开了告诉 Flutter
            if (!autoWalk && mySeat < 0)
            {
                string near = "";
                float best = nearRadius;
                foreach (var s in spots)
                {
                    if (s.name == startSpot || s.name == "court") continue;
                    float d = Vector2.Distance(new Vector2(s.floor.x, s.floor.z), new Vector2(player.transform.position.x, player.transform.position.z));
                    if (d < best) { best = d; near = s.name; }
                }
                if (near == "" && player.transform.position.z > (float.IsNaN(courtMinZ) ? hub.z - 0.5f : courtMinZ)) near = "court";
                if (near != at && at != startSpot || (at == startSpot && near != "" && near != startSpot))
                {
                    at = near;
                    Send($"{{\"type\":\"arrived\",\"spot\":\"{near}\"}}");
                }
            }
            // 偶尔的声音：檐角的风铃，远处的钟
            nextChime -= dt;
            if (nextChime <= 0)
            {
                nextChime = UnityEngine.Random.Range(35f, 80f);
                sound.Play("sfx_chime", 0.22f);
            }
            nextBell -= dt;
            if (nextBell <= 0)
            {
                nextBell = UnityEngine.Random.Range(160f, 280f);
                sound.Play(bell, 0.3f);
            }
        }
    }
}
