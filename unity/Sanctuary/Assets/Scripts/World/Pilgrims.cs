using System.Collections.Generic;
using UnityEngine;

namespace Yuanjing
{
    /// 殿里的其他人。真人和内置香客长得一样（同一批 Q 版小人），由 Flutter 告诉这里谁坐在哪、在做什么。
    /// 新来的人从山门走进来，找到自己的位置坐下；走的人起身往山门走，出了门再消失。
    /// 另外院子里有几位在散步的，走到树下、香炉前停下来拜一拜，只在本机，不同步。
    /// 隔一阵有一位香客进大殿跪拜、静坐，再出来（只在本机，见 PilgrimsHall.cs）。
    public partial class Pilgrims : MonoBehaviour
    {
        public static Pilgrims Instance { get; private set; }

        public GameObject[] looks;          // 小人的几套样子（第 0 套留给自己）
        public Transform seatsRoot;
        public bool benchSeats;
        /// 人从哪里进来、从哪里离开
        public Vector3 entrance, entranceInside;
        /// 散步的人会去的地方：位置和看向哪里
        public Vector3[] strollPoints = new Vector3[0];
        /// 站着做事时不站进去的几块（水平 x、z）：殿前台阶下中间那一条、台阶本身——你点「进殿」走的就是那里
        public Rect[] keepClear = new Rect[0];
        public Vector3[] strollLooks = new Vector3[0];
        public int strollers = 4;
        /// 过道：进出座位区要先走到过道上（同 GameDirector 的设置）
        public Vector3 aislePoint, aisleDir = Vector3.right;
        public Vector3[] seatExitNeg = new Vector3[0], seatExitPos = new Vector3[0];
        public Vector3 seatLook;
        public float seatStraight;

        static readonly string[] NpcNames =
        {
            "晚风", "栀子", "阿宁", "小满", "云起", "知南", "听雨", "青禾", "一苇", "星野", "念安", "见山",
            "松月", "阿梨", "初七", "向晚", "木木", "简兮", "半夏", "南乔", "清欢", "予安", "微澜", "山岚",
        };

        class Person
        {
            public string id;
            public int seat = -1;
            public Folk folk;
            public bool npc, leaving, seated, stroller;
            public float next, bowT = -1;
            public int strollAt = -1;
            // 内置香客的行程（服务器给的）：要做的事、什么时候来的（本机时间）、待多久、正在做第几件
            public string plan = "";
            public float arrive, stay;
            public int step = -1;
            public bool atSpot;
            public float lookNext;
            /// 要去（或已经站在）的那个点：别人挑站的地方时会避开
            public Vector3 target = new Vector3(9999, 0, 9999);
            /// 正走去坐的那个座位（-1 是没在去坐的路上）：坐下、改道、离开时清掉
            public int toSeat = -1;
            /// 每次给他一条新路线就加一：旧路线走到头时的回调认出自己过时了，不再执行（不然会坐到旧座位上去）
            public int gen;
        }

        // 每件事去哪儿（strollPoints 的序号，见 BuildIslet.ConfigureCrowd）：
        //   0 许愿树 1、2 香炉两侧 3 池塘 4、5 大殿前 6 钟亭 7 石碑 8 栈桥
        static int[] SpotsFor(char c) => c switch
        {
            'i' => new[] { 1, 2 }, 'h' => new[] { 4, 5 }, 't' => new[] { 0 }, 'p' => new[] { 3 },
            'v' => new[] { 6 }, 'e' => new[] { 7 }, 'l' => new[] { 8 }, _ => new int[0],
        };

        /// 行程里每件事占多少时间：静坐占大头
        static float Weight(char c) => c == 's' ? 4f : 1f;

        int StepAt(Person p, float elapsed)
        {
            float total = 0;
            foreach (char c in p.plan) total += Weight(c);
            float usable = Mathf.Max(30f, p.stay - 45f), acc = 0;
            for (int i = 0; i < p.plan.Length; i++)
            {
                acc += Weight(p.plan[i]) / total * usable;
                if (elapsed < acc) return i;
            }
            return p.plan.Length - 1;
        }

        readonly List<(string id, int seat, bool npc, string name, string plan, float since, float stay)> waiting = new List<(string, int, bool, string, string, float, float)>();
        float gateFree;

        readonly Dictionary<string, Person> people = new Dictionary<string, Person>();
        readonly List<Transform> seats = new List<Transform>();

        void Awake()
        {
            Instance = this;
            Init();
        }

        public void Init()
        {
            if (seats.Count > 0 || seatsRoot == null) return;
            foreach (Transform t in seatsRoot) seats.Add(t);
        }

        public int SeatCount => seats.Count;
        public Transform Seat(int i) => seats[Mathf.Clamp(i, 0, seats.Count - 1)];

        /// 这个座位有没有人：坐着的、行程里要回来坐的（这会儿在树下、香炉前）、还在栈桥口排队等着进来的，都算占着
        public bool Occupied(int seat)
        {
            if (seat < 0) return false;
            foreach (var p in people.Values) if (p.seat == seat && !p.leaving) return true;
            foreach (var w in waiting) if (w.seat == seat) return true;
            return false;
        }

        /// 自己（玩家）坐着的、或者正走过去要坐的座位
        static int PlayerSeat => GameDirector.Instance != null ? GameDirector.Instance.MySeat : -1;

        /// 这个座位此刻真的有人：坐在上面的，或者内置香客正走过去坐、已经走到跟前（3 米以内）的；
        /// 真人（别的玩家）只要服务器说他坐这里就算，不管他还在路上多远、还在栈桥口排队——他不会让座（Release 只管内置香客）。
        /// 只是被内置香客记着「等会儿回来坐」的（他在树下、香炉前、还在路上远处、在栈桥口排队）不算——看上去是空的蒲团，
        /// 玩家可以坐（坐了以后用 Release 让那人换一个）
        public bool Taken(int seat)
        {
            if (seat < 0 || seat >= seats.Count) return false;
            Vector3 at = seats[seat].position;
            foreach (var p in people.Values)
            {
                if (p.leaving || p.seat != seat || p.stroller) continue;
                if (p.seated || !p.npc) return true;
                if (p.folk != null && p.toSeat == seat && Flat(p.folk.transform.position, at) < 3f) return true;
            }
            foreach (var w in waiting) if (!w.npc && w.seat == seat) return true;
            return false;
        }

        static float Flat(Vector3 a, Vector3 b) => new Vector2(a.x - b.x, a.z - b.z).magnitude;

        /// 一个空座位（没人坐、没人记着、不是玩家的），随便挑；没有是 -1
        int FreeSeat()
        {
            for (int g = 0; g < 60; g++)
            {
                int s = Random.Range(0, seats.Count);
                if (!Occupied(s) && s != PlayerSeat) return s;
            }
            for (int s = 0; s < seats.Count; s++) if (!Occupied(s) && s != PlayerSeat) return s;
            return -1;
        }

        /// 玩家要坐这个座位：记着它、还没坐上的内置香客换一个（正在路上的改道；没有空的就不坐了，去别处站站）。
        /// 联网时服务器下一拍也会给他重新安排，PlaceVisitor 照新的来
        public void Release(int seat)
        {
            if (seat < 0 || seat >= seats.Count) return;
            foreach (var p in new List<Person>(people.Values))
            {
                if (p.leaving || p.seated || p.stroller || !p.npc || p.seat != seat) continue;
                bool visitor = !string.IsNullOrEmpty(p.plan);
                int to = FreeSeat();
                if (to < 0 && !visitor) continue;
                p.seat = to;
                if (p.toSeat >= 0)
                {
                    p.toSeat = -1;
                    if (visitor && p.step >= 0) GoStep(p, p.step);
                    else GoSit(p, false);
                }
            }
            for (int i = 0; i < waiting.Count; i++)
                if (waiting[i].seat == seat)
                {
                    var w = waiting[i];
                    w.seat = FreeSeat();
                    waiting[i] = w;
                }
        }

        /// 座位前面那条走道（沿着一排蒲团前面的草垫走）：座位点加上它
        public Vector3 laneOffset = Vector3.zero;
        Vector3 AisleNode(Vector3 p) => aislePoint + aisleDir * Vector3.Dot(p + laneOffset - aislePoint, aisleDir);
        bool Positive(Vector3 p) => Vector3.Dot(p - aislePoint, Vector3.Cross(Vector3.up, aisleDir)) >= 0;

        Folk Spawn(string id, Vector3 at, float yaw)
        {
            int h = Mathf.Abs(id.GetHashCode());
            var prefab = looks[1 + h % (looks.Length - 1)];
            var go = Instantiate(prefab, at, Quaternion.Euler(0, yaw, 0), transform);
            go.name = "Pilgrim_" + id;
            AnimeVariant.Apply(go, h / 13);
            // 高矮略有不同
            go.transform.localScale *= 0.95f + (h % 11) * 0.01f;
            var folk = go.GetComponent<Folk>();
            folk.walkSpeed *= 0.85f + (h % 7) * 0.04f;
            folk.FaceYaw(yaw);
            return folk;
        }

        Vector3 SeatLook(Vector3 seat) => new Vector3(Mathf.Lerp(seatLook.x, seat.x, seatStraight), seatLook.y, seatLook.z);

        /// 让一个人去某个座位。已经在殿里的直接换过去；新来的从山门走进来。instant：一进场就已经坐着的
        public void Place(string id, int seat, bool npc, string name, bool instant = false) => Place(id, seat, npc, name, instant, "", 0, 0);

        public void Place(string id, int seat, bool npc, string name, bool instant, string plan, float since, float stay)
        {
            if (seats.Count == 0) return;
            if (npc && !string.IsNullOrEmpty(plan))
            {
                PlaceVisitor(id, seat, name, instant, plan, since, stay);
                return;
            }
            seat = Mathf.Clamp(seat, 0, seats.Count - 1);
            if (people.TryGetValue(id, out var p))
            {
                p.leaving = false;
                if (p.seat == seat) return;
                p.seat = seat;
                GoSit(p, false);
                return;
            }
            p = new Person { id = id, seat = seat, npc = npc, next = Random.Range(8f, 40f) };
            if (instant)
            {
                Vector3 s = seats[seat].position;
                Vector3 d = SeatLook(s) - s;
                p.folk = Spawn(id, s, Quaternion.LookRotation(new Vector3(d.x, 0, d.z)).eulerAngles.y);
                p.folk.SetPose(benchSeats ? Folk.Pose.Bench : Folk.Pose.CrossLegged, true);
                p.folk.SeatedAt(seats[seat].position, StandPoint(seats[seat].position, p.folk));
                p.seated = true;
            }
            else
            {
                p.folk = Spawn(id, entrance, Quaternion.LookRotation(entranceInside - entrance).eulerAngles.y);
                GoSit(p, true);
            }
            p.folk.SetName(NameFor(id, name), NameColor);
            people[id] = p;
        }

        string NameFor(string id, string name) => string.IsNullOrEmpty(name) ? NpcNames[Mathf.Abs(id.GetHashCode()) % NpcNames.Length] : name;
        static readonly Color NameColor = new Color(1f, 0.965f, 0.89f);

        /// 内置香客：照行程演。一进殿就在的人直接出现在他此刻该在的地方；新来的从栈桥走进来
        void PlaceVisitor(string id, int seat, string name, bool instant, string plan, float since, float stay)
        {
            if (instant) instantPlacedAt = Time.time;
            if (people.TryGetValue(id, out var p))
            {
                if (p.leaving) return;
                // 服务器的时间为准：本机慢慢校过去，不突变
                float arrive = Time.time - since;
                p.arrive = Mathf.Lerp(p.arrive, arrive, 0.2f);
                // 服务器给他换了座位（比如原来那个被你坐了）：还没坐下的照新的去，正走在去旧座位路上的当场改道；已经坐着的不挪
                if (!p.seated && seat != p.seat && seat < seats.Count)
                {
                    p.seat = seat;
                    if (p.toSeat >= 0 && p.toSeat != seat && p.step >= 0)
                    {
                        p.toSeat = -1;
                        GoStep(p, p.step);
                    }
                }
                return;
            }
            // 还在栈桥口排队的：座位也照服务器的新安排
            int wi = waiting.FindIndex(w => w.id == id);
            if (wi >= 0 && waiting[wi].seat != seat)
            {
                var w = waiting[wi];
                w.seat = seat;
                waiting[wi] = w;
            }
            // 进殿时就在的人（instant）一律直接出现在他此刻该在的地方，不排在栈桥口跟在你身后；之后新来的才从栈桥走进来
            if (!instant)
            {
                // 栈桥口有人（包括自己）就等一会儿再进来，不会两个人叠在一起
                if (!waiting.Exists(w => w.id == id)) waiting.Add((id, seat, true, name, plan, since, stay));
                return;
            }
            p = new Person { id = id, npc = true, plan = plan, stay = stay, arrive = Time.time - since, seat = seat };
            p.step = StepAt(p, Mathf.Max(since, 1f));
            char c = plan[p.step];
            Vector3 at;
            float yaw;
            if (c == 's' && seat >= 0 && seat < seats.Count)
            {
                at = seats[seat].position;
                Vector3 d = SeatLook(at) - at;
                yaw = Quaternion.LookRotation(new Vector3(d.x, 0, d.z)).eulerAngles.y;
                p.folk = Spawn(id, at, yaw);
                p.folk.SetPose(benchSeats ? Folk.Pose.Bench : Folk.Pose.CrossLegged, true);
                p.folk.SeatedAt(seats[seat].position, StandPoint(seats[seat].position, p.folk));
                p.seated = true;
            }
            else
            {
                var (pos, look) = SpotPos(p, c);
                Vector3 d = look - pos;
                yaw = Quaternion.LookRotation(new Vector3(d.x, 0, d.z).sqrMagnitude > 0.01f ? new Vector3(d.x, 0, d.z) : Vector3.forward).eulerAngles.y;
                p.folk = Spawn(id, pos, yaw);
                p.atSpot = true;
                people[id] = p;       // 先登记，后面的人挑位置时才会避开他
            }
            p.next = Random.Range(4f, 30f);
            p.lookNext = Random.Range(6f, 20f);
            p.folk.SetName(NameFor(id, name), NameColor);
            people[id] = p;
        }

        (Vector3 pos, Vector3 look) SpotPos(Person p, char c)
        {
            var idx = SpotsFor(c);
            if (idx.Length == 0 || strollPoints.Length == 0) return (entranceInside, entranceInside + Vector3.forward);
            int h = Mathf.Abs((p.id + c).GetHashCode());
            int k = idx[h % idx.Length] % strollPoints.Length;
            // 每人站的位置错开一点：围成一圈，不挤在同一个点上
            float ang = (h % 360) * Mathf.Deg2Rad, r = 0.5f + (h / 360 % 10) * 0.12f;
            Vector3 pos = strollPoints[k] + new Vector3(Mathf.Cos(ang) * r, 0, Mathf.Sin(ang) * r);
            // 不站在走道上（keepClear：大殿台阶前的那一条、台阶本身）：往两边挪出去。
            // 挪到边上还可能贴着台阶两边的垂带（StepCheek，x 2.35–2.75）：FreeSpot 只要离隔断（垂带、栏杆、门柱……）有一个人身子宽的点，
            // 不行就往外一圈圈找（以前挪到 x ±2.85 就站下了，人一半在垂带里，一站五十多秒）
            foreach (var kc in keepClear)
                if (kc.Contains(new Vector2(pos.x, pos.z)))
                {
                    // 往这一处（strollPoints）所在的那一边挪；它正在中线上就按自己站的那一边
                    float side = Mathf.Abs(strollPoints[k].x - kc.center.x) > 0.01f ? strollPoints[k].x - kc.center.x : pos.x - kc.center.x;
                    pos.x = side >= 0f ? kc.xMax + 0.05f : kc.xMin - 0.05f;
                }
            Vector3 look = k < strollLooks.Length ? strollLooks[k] : pos + Vector3.forward;
            return (FreeSpot(pos, p), look);
        }

        /// 站人的地方碰不碰得到隔断（栏杆、垂带、门柱、石碑……，Folk.Barriers；人按半径 0.3 米算，再留几厘米），在不在要让出来的那几块里
        bool SpotBlocked(Vector3 c)
        {
            foreach (var kc in keepClear) if (kc.Contains(new Vector2(c.x, c.z))) return true;
            return Folk.BarrierNear(c, 0.34f);
        }

        /// 去做行程里的下一件事
        void GoStep(Person p, int step)
        {
            p.step = step;
            p.atSpot = false;
            char c = p.plan[step];
            var path = new List<Vector3>();
            Vector3 from = p.folk.transform.position;
            if (p.seated)
            {
                path.Add(from + laneOffset);
                path.Add(AisleNode(from));
                path.AddRange(Positive(from) ? seatExitPos : seatExitNeg);
                from = path[path.Count - 1];
            }
            p.seated = false;
            p.folk.SetPose(Folk.Pose.None);
            p.toSeat = -1;
            if (c == 's' && p.seat >= 0 && p.seat < seats.Count && !OccupiedByOther(p.seat, p.id))
            {
                int index = p.seat;
                Vector3 target = seats[index].position;
                if (InSeatBlock(from))
                {
                    // 已经在石台上（刚才去坐的蒲团被人坐了、改道）：沿走道、过道过去，不出石台（总控的路线认得走道和过道）
                    path.AddRange(Plan(from, target + laneOffset));
                }
                else
                {
                    var back = new List<Vector3>(Positive(target) ? seatExitPos : seatExitNeg);
                    back.Reverse();
                    path.AddRange(Plan(from, back[0]));
                    path.AddRange(back.GetRange(1, back.Count - 1));
                    path.Add(AisleNode(target));
                    path.Add(target + laneOffset);
                }
                path.Add(StandPoint(target, p.folk));
                p.toSeat = index;
                Go(p, path, () =>
                {
                    StartCoroutine(SitWhenFacing(p, index));
                    p.next = Random.Range(20f, 70f);
                });
                return;
            }
            var (pos, look) = SpotPos(p, c == 's' ? "itplve"[Mathf.Abs(p.id.GetHashCode()) % 6] : c);
            path.AddRange(Plan(from, pos));
            Go(p, path, () =>
            {
                p.folk.FaceTowards(look);
                p.atSpot = true;
                p.lookNext = Random.Range(5f, 14f);
                // 到了先站一下，再拜（不是一到就拜）
                if (c == 'i' || c == 'h' || c == 't') p.next = Random.Range(1.2f, 3.5f);
                else p.next = Random.Range(10f, 30f);
            });
        }

        /// 从 want 开始往外一圈圈找，找一个离别人（站着的、正要去的、自己）都有 0.65 米以上的点
        Vector3 FreeSpot(Vector3 want, Person me)
        {
            bool Free(Vector3 c)
            {
                if (SpotBlocked(c)) return false;
                foreach (var q in people.Values)
                {
                    if (q == me || q.folk == null || q.leaving) continue;
                    Vector3 a = q.folk.transform.position - c, b = q.target - c;
                    a.y = b.y = 0;
                    if (a.magnitude < 0.65f || b.magnitude < 0.65f) return false;
                }
                var gd = GameDirector.Instance;
                if (gd != null && gd.player != null)
                {
                    Vector3 a = gd.player.transform.position - c;
                    a.y = 0;
                    if (a.magnitude < 0.8f) return false;
                    // 玩家「去大殿」「去香炉」「去许愿树」站的那一点、玩家正走去的那一点：留出来，不站在上面
                    if (gd.KeepClear(c)) return false;
                }
                return true;
            }
            for (int ring = 0; ring < 6; ring++)
            {
                int n = ring == 0 ? 1 : 6 * ring;
                float off = Mathf.Abs(me.id.GetHashCode()) % 100 / 100f;
                for (int i = 0; i < n; i++)
                {
                    float a = (i + off) / n * Mathf.PI * 2f;
                    Vector3 c = want + new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a)) * (ring * 0.6f);
                    if (Free(c)) { me.target = c; return c; }
                }
            }
            // 挤得一个空的点都没有：至少不站进隔断里（离别人近一点就近一点）
            for (int ring = 0; ring < 8; ring++)
            {
                int n = ring == 0 ? 1 : 6 * ring;
                for (int i = 0; i < n; i++)
                {
                    float a = (float)i / n * Mathf.PI * 2f;
                    Vector3 c = want + new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a)) * (ring * 0.3f);
                    if (!SpotBlocked(c)) { me.target = c; return c; }
                }
            }
            me.target = want;
            return want;
        }

        /// c 附近 r 米内有没有人（站着的、走着的、正要去那里站的；要走的不算）：玩家找站的地方时避开
        public bool Crowded(Vector3 c, float r)
        {
            foreach (var q in people.Values)
            {
                if (q.folk == null || q.leaving) continue;
                if (Flat(q.folk.transform.position, c) < r) return true;
                // 正走去某处站着的（不是去坐的）：他要去的那一点也算
                if (!q.seated && q.toSeat < 0 && Flat(q.target, c) < r) return true;
            }
            return false;
        }

        /// 蒲团前面、草垫上站的地方
        Vector3 StandPoint(Vector3 seat, Folk f)
        {
            if (benchSeats) return seat;
            Vector3 fwd = SeatLook(seat) - seat; fwd.y = 0; fwd.Normalize();
            return seat + fwd * Folk.SeatStep * f.transform.lossyScale.y / 0.806f;
        }

        /// 到了蒲团前：先转身朝着大殿，再坐下去。坐之前再看一眼：座位还是不是自己的（路上服务器给换了）、
        /// 有没有别人（玩家、别的香客）先坐上了——不对就改道，不会坐到别人身上，也不会人坐在 A、记的却是 B
        System.Collections.IEnumerator SitWhenFacing(Person p, int index)
        {
            int g = p.gen;
            Vector3 seat = seats[index].position;
            Vector3 d = SeatLook(seat) - seat; d.y = 0;
            float yaw = Quaternion.LookRotation(d).eulerAngles.y;
            p.folk.FaceYaw(yaw);
            // 转到差 3 度以内再坐（不然坐下那一帧一下拧过去几十度）
            for (float t = 0; t < 2.5f && Mathf.Abs(Mathf.DeltaAngle(p.folk.transform.eulerAngles.y, yaw)) > 3f; t += Time.deltaTime) yield return null;
            if (p.leaving || p.folk == null || p.gen != g) yield break;
            p.toSeat = -1;
            if (p.seat != index || OccupiedByOther(index, p.id))
            {
                if (!string.IsNullOrEmpty(p.plan) && p.step >= 0) GoStep(p, p.step);
                else if (p.seat >= 0 && p.seat != index && !OccupiedByOther(p.seat, p.id)) GoSit(p, false);
                // 自己的座位被人（玩家）先坐了：换一个空的；没有空的就退到走道上、站到过道边——绝不站在别人的垫子上
                else Reseat(p, index);
                yield break;
            }
            if (benchSeats) p.folk.SetPose(Folk.Pose.Bench);
            else p.folk.SitOn(seat, yaw);
            p.seated = true;
        }

        /// 玩家坐了（或正走去坐）这个座位，名单上却说某人也坐这里（服务器还没收到玩家坐下、两个人同时挑了同一个）：
        /// 他还在路上就换一个空的（本机安排，服务器下一拍会给准的），没有空的就站到走道上。还没来的人不用管（总控先不摆他）
        public void Yield(string id, int seat)
        {
            if (!people.TryGetValue(id, out var p) || p.leaving || p.stroller || p.folk == null || p.seat != seat) return;
            Reseat(p, seat);
        }

        /// 不坐 avoid 这个座位了：挑一个空的走过去；没有空的就从这个座位退到它前面的走道上，再走到中间过道边站着
        void Reseat(Person p, int avoid)
        {
            int to = FreeSeat();
            if (to >= 0 && to != avoid)
            {
                p.seat = to;
                GoSit(p, false);
                return;
            }
            p.seat = -1;
            p.toSeat = -1;
            p.seated = false;
            p.folk.SetPose(Folk.Pose.None);
            Vector3 s = seats[Mathf.Clamp(avoid, 0, seats.Count - 1)].position;
            Vector3 aisle = AisleNode(s) + (Positive(s) ? 1f : -1f) * Vector3.Cross(Vector3.up, aisleDir) * 0.45f;
            Go(p, new List<Vector3> { s + laneOffset, aisle }, () => p.folk.FaceTowards(SeatLook(aisle)));
        }

        /// 在不在石台的座位区里（GameDirector 的 seatBlock）
        bool InSeatBlock(Vector3 p)
        {
            var gd = GameDirector.Instance;
            return gd != null && laneOffset != Vector3.zero && gd.seatBlock.Contains(new Vector2(p.x, p.z));
        }

        /// 别人已经坐在这个座位上了（包括自己——玩家坐着的那个）
        bool OccupiedByOther(int seat, string id)
        {
            if (seat == PlayerSeat) return true;
            foreach (var q in people.Values) if (q.id != id && q.seat == seat && q.seated && !q.leaving) return true;
            return false;
        }

        List<Vector3> Plan(Vector3 a, Vector3 b) => GameDirector.Instance != null ? GameDirector.Instance.PlanPath(a, b) : new List<Vector3> { b };

        /// 沿路线走，走到了做 done。中途又给了新路线的话，这条的 done 就作废
        void Go(Person p, List<Vector3> path, System.Action done)
        {
            int g = ++p.gen;
            p.folk.Walk(path);
            System.Action arrived = null;
            arrived = () =>
            {
                p.folk.Arrived -= arrived;
                if (p.leaving || p.gen != g) return;
                done();
            };
            p.folk.Arrived += arrived;
        }

        /// 在栈桥口等着的人：口上没人了才进来，一次一个，前后隔一两秒
        void AdmitWaiting()
        {
            if (waiting.Count == 0 || Time.time < gateFree) return;
            foreach (var f in Folk.All)
                if (f != null && Vector3.Distance(f.transform.position, entrance) < 1.6f) { gateFree = Time.time + 1.5f; return; }
            // 自己刚进来、还在栈桥上：别让人紧跟在身后走（离栈桥口 4 米以外才放人进来）
            var gd = GameDirector.Instance;
            if (gd != null && gd.player != null && Vector3.Distance(gd.player.transform.position, entrance) < 4f) { gateFree = Time.time + 1f; return; }
            var w = waiting[0];
            waiting.RemoveAt(0);
            if (people.ContainsKey(w.id)) return;
            var p = new Person { id = w.id, npc = true, plan = w.plan, stay = w.stay, arrive = Time.time - Mathf.Min(w.since, 20f), seat = w.seat, step = -1 };
            p.folk = Spawn(w.id, entrance, Quaternion.LookRotation(entranceInside - entrance).eulerAngles.y);
            p.folk.SetName(NameFor(w.id, w.name), NameColor);
            people[w.id] = p;
            p.folk.Walk(new List<Vector3> { entranceInside });
            Go(p, new List<Vector3> { entranceInside }, () => GoStep(p, 0));
            gateFree = Time.time + Random.Range(3f, 7f);
        }

        void GoSit(Person p, bool fromGate)
        {
            Vector3 target = seats[p.seat].position;
            var path = new List<Vector3>();
            if (fromGate)
            {
                path.Add(entranceInside);
                var back = new List<Vector3>(Positive(target) ? seatExitPos : seatExitNeg);
                back.Reverse();
                path.AddRange(back);
            }
            else if (p.seated)
            {
                path.Add(p.folk.transform.position + laneOffset);
                path.Add(AisleNode(p.folk.transform.position));
                if (Positive(p.folk.transform.position) != Positive(target))
                {
                    path.AddRange(Positive(p.folk.transform.position) ? seatExitPos : seatExitNeg);
                    var back = new List<Vector3>(Positive(target) ? seatExitPos : seatExitNeg);
                    back.Reverse();
                    path.AddRange(back);
                }
            }
            else
            {
                // 站着、在路上（换了座位、让座）：按总控的路线走到那一排的走道上（认得走道、过道，不踩别的蒲团），再到蒲团前
                path.AddRange(Plan(p.folk.transform.position, target + laneOffset));
                path.Add(StandPoint(target, p.folk));
                p.folk.SetPose(Folk.Pose.None);
                int idx = p.seat;
                p.toSeat = idx;
                Go(p, path, () => StartCoroutine(SitWhenFacing(p, idx)));
                return;
            }
            path.Add(AisleNode(target));
            path.Add(target + laneOffset);
            path.Add(StandPoint(target, p.folk));
            p.seated = false;
            p.folk.SetPose(Folk.Pose.None);
            int index = p.seat;
            p.toSeat = index;
            Go(p, path, () => StartCoroutine(SitWhenFacing(p, index)));
        }

        /// 起身离开：走出山门再消失
        void Leave(Person p)
        {
            if (p.leaving) return;
            p.leaving = true;
            p.toSeat = -1;
            p.gen++;
            var path = new List<Vector3>();
            // 在殿里的：放掉拜垫、蒲团，坐着的先退到蒲团前的走道上（PilgrimsHall.cs）
            bool fromHall = HallQuit(p, path);
            if (p.seated)
            {
                path.Add(p.folk.transform.position + laneOffset);
                path.Add(AisleNode(p.folk.transform.position));
                path.AddRange(Positive(p.folk.transform.position) ? seatExitPos : seatExitNeg);
            }
            Vector3 from = path.Count > 0 ? path[path.Count - 1] : p.folk.transform.position;
            path.AddRange(Plan(from, entranceInside));
            path.Add(entrance);
            if (fromHall) HallLogRoute(p, path);
            p.seated = false;
            p.folk.SetPose(Folk.Pose.None);
            p.folk.Walk(path);
            var person = p;
            p.folk.Arrived += () =>
            {
                if (!person.leaving) return;
                people.Remove(person.id);
                Destroy(person.folk.gameObject);
            };
        }

        public void Remove(string id)
        {
            if (people.TryGetValue(id, out var p)) Leave(p);
        }

        /// 让某个人拜一拜（服务器转来的别人的动作）
        public void Act(string id, string action)
        {
            if (!people.TryGetValue(id, out var p) || p.leaving || !p.seated) return;
            if (p.bowT < 0) p.bowT = 0;
        }

        /// 服务器给的名单：不在名单里的人离开（散步的人不受影响）
        public void Sync(HashSet<string> present)
        {
            var gone = new List<Person>();
            waiting.RemoveAll(w => !present.Contains(w.id));
            foreach (var p in people.Values) if (!p.stroller && !present.Contains(p.id)) gone.Add(p);
            foreach (var p in gone) Leave(p);
        }

        /// 没有服务器名单时，自己安排几位，一进来就已经坐着
        public void SeedLocal(int count, int avoidSeat)
        {
            var rng = new Rng(System.DateTime.Now.DayOfYear * 31 + System.DateTime.Now.Hour);
            int placed = 0, guard = 0;
            while (placed < count && guard++ < 200)
            {
                int s = rng.Int(seats.Count);
                if (s == avoidSeat || Occupied(s)) continue;
                Place("npc" + s, s, true, "", true);
                placed++;
            }
        }

        /// 没联网时：本机自己安排人来人往。人数按当地时间（同服务器的曲线），每隔一阵有人来、有人走
        bool localCrowd;
        float localNext;
        int localSerial;
        static readonly int[] CrowdByHour = { 11, 10, 10, 10, 11, 14, 22, 36, 44, 40, 32, 28, 27, 29, 30, 32, 36, 44, 48, 46, 38, 30, 22, 15 };
        const string Acts = "sihtpvel";

        /// 本机安排人来人往（没联网）。同一个场景重新进场（页面关了又开、Flutter 没等到 entered 又发了一遍 enter）时场景不重新加载、人还在：
        /// 以前每次都再加满一岛人（27 → 54 → 108），现在只补到该有的人数
        public void StartLocalCrowd()
        {
            localCrowd = true;
            int target = LocalTarget(), have = LocalCount();
            for (int i = have; i < target; i++) LocalVisitor(true);
            localNext = Random.Range(8f, 20f);
        }

        /// 岛上此刻的内置香客（不算正在走的）加上排着队要来的
        int LocalCount()
        {
            int count = 0;
            foreach (var p in people.Values) if (!p.leaving && p.npc) count++;
            return count + waiting.Count;
        }

        /// 测试用：本机的人数不按钟点（夜里只有十位、白天三十位，测试不能跟着钟点变）；0 是照钟点
        public static int CrowdOverride;

        int LocalTarget()
        {
            if (CrowdOverride > 0) return CrowdOverride;
            var now = System.DateTime.Now;
            float h = now.Hour + now.Minute / 60f;
            float a = CrowdByHour[now.Hour], b = CrowdByHour[(now.Hour + 1) % 24];
            return Mathf.Clamp(Mathf.RoundToInt(Mathf.Lerp(a, b, h - now.Hour)), 10, 50);
        }

        void LocalVisitor(bool already)
        {
            string id = "local" + (localSerial++);
            string plan = "";
            int n = Random.Range(1, 4);
            for (int k = 0; k < n; k++) { char c = Acts[Random.Range(1, Acts.Length)]; if (plan.IndexOf(c) < 0) plan += c; }
            if (Random.value < 0.72f) plan = "s" + plan;
            int seat = -1;
            if (plan.Contains("s"))
                for (int g = 0; g < 40; g++) { int s = Random.Range(0, seats.Count); if (!Occupied(s) && s != PlayerSeat) { seat = s; break; } }
            float stay = Random.Range(360f, 2400f);
            float since = already ? Random.Range(30f, stay - 60f) : 0;
            PlaceVisitor(id, seat, "", already, plan, since, stay);
        }

        void LocalCrowdTick(float dt)
        {
            if (!localCrowd || (localNext -= dt) > 0) return;
            localNext = Random.Range(10f, 35f);
            if (LocalCount() < LocalTarget() + Random.Range(-2, 3)) LocalVisitor(false);
        }

        /// 院子里散步的人
        public void StartWanderers()
        {
            if (strollPoints.Length == 0) return;
            for (int i = 0; i < strollers; i++)
            {
                string id = "walk" + i;
                if (people.ContainsKey(id)) continue;
                int at = (i * 3) % strollPoints.Length;
                var folk = Spawn(id, strollPoints[at] + new Vector3(Random.Range(-0.6f, 0.6f), 0, Random.Range(-0.6f, 0.6f)), Random.Range(0, 360f));
                folk.SetName(NpcNames[(i * 7 + 5) % NpcNames.Length], new Color(1f, 1f, 1f, 0.92f));
                people[id] = new Person { id = id, folk = folk, npc = true, stroller = true, strollAt = at, next = Random.Range(2f, 12f) };
            }
        }

        void Stroll(Person p)
        {
            int to;
            do to = Random.Range(0, strollPoints.Length); while (to == p.strollAt && strollPoints.Length > 1);
            p.strollAt = to;
            Vector3 target = strollPoints[to] + new Vector3(Random.Range(-0.5f, 0.5f), 0, Random.Range(-0.5f, 0.5f));
            var path = GameDirector.Instance != null ? GameDirector.Instance.PlanPath(p.folk.transform.position, target) : new List<Vector3> { target };
            p.folk.SetPose(Folk.Pose.None);
            p.folk.Walk(path);
            var person = p;
            System.Action arrived = null;
            arrived = () =>
            {
                person.folk.Arrived -= arrived;
                if (to < strollLooks.Length) person.folk.FaceTowards(strollLooks[to]);
                // 到了停一会儿，多半会合掌拜一拜
                person.next = Random.Range(6f, 16f);
                if (Random.value < 0.7f)
                {
                    person.folk.SetPose(Random.value < 0.6f ? Folk.Pose.Bow : Folk.Pose.Gassho);
                    person.bowT = 0;
                }
            };
            p.folk.Arrived += arrived;
        }

        void VisitorTick(Person p, float dt)
        {
            float elapsed = Time.time - p.arrive;
            if (elapsed >= p.stay - 40f && !p.folk.Moving && p.bowT < 0) { Leave(p); return; }
            if (p.step < 0 || p.folk.Moving) return;
            int want = StepAt(p, elapsed);
            if (want != p.step && p.bowT < 0) { GoStep(p, want); return; }
            p.next -= dt;
            if (p.atSpot)
            {
                char c = p.plan[p.step];
                if (p.next <= 0 && p.bowT < 0)
                {
                    // 在香炉、大殿、树前：合掌或鞠躬拜一拜；别处偶尔换个站的地方（像人在闲逛）
                    if (c == 'i' || c == 'h' || c == 't' || Random.value < 0.15f)
                    {
                        p.folk.SetPose(Random.value < 0.55f ? Folk.Pose.Bow : Folk.Pose.Gassho);
                        p.bowT = 0;
                        p.next = Random.Range(15f, 45f);
                    }
                    else
                    {
                        var (pos, look) = SpotPos(p, c);
                        Vector3 j = FreeSpot(pos + new Vector3(Random.Range(-1.2f, 1.2f), 0, Random.Range(-1.2f, 1.2f)), p);
                        p.atSpot = false;
                        Go(p, Plan(p.folk.transform.position, j), () => { p.folk.FaceTowards(look); p.atSpot = true; });
                        p.next = Random.Range(12f, 35f);
                    }
                }
                // 站着的时候时不时转头看看别处，再转回来
                if ((p.lookNext -= dt) <= 0 && p.bowT < 0)
                {
                    var (_, look) = SpotPos(p, c);
                    Vector3 d = look - p.folk.transform.position;
                    float baseYaw = Quaternion.LookRotation(new Vector3(d.x, 0, d.z).sqrMagnitude > 0.01f ? new Vector3(d.x, 0, d.z) : Vector3.forward).eulerAngles.y;
                    p.folk.FaceYaw(baseYaw + (Random.value < 0.5f ? 0 : Random.Range(-70f, 70f)));
                    p.lookNext = Random.Range(5f, 16f);
                }
            }
            else if (p.seated && p.next <= 0 && p.bowT < 0)
            {
                // 坐着：隔很久才拜一下，每人节奏不同
                p.next = Random.Range(30f, 110f);
                p.bowT = 0;
            }
        }

        void Update()
        {
            AdmitWaiting();
            LocalCrowdTick(Time.deltaTime);
            float dt = Time.deltaTime;
            // 殿里的香客：请人进殿、看着进了殿的人（PilgrimsHall.cs）
            HallUpdate(dt);
            foreach (var p in people.Values)
            {
                if (p.leaving) continue;
                // 进了殿的人归殿里那一段管（走、拜、坐、出殿），这里不再安排
                if (InHallVisit(p)) continue;
                // 鞠躬的节奏：1.2 秒俯下，停 0.8 秒，1.2 秒起来
                if (p.bowT >= 0)
                {
                    p.bowT += dt;
                    float t = p.bowT;
                    p.folk.SetBow(t < 1.2f ? t / 1.2f : t < 2f ? 1f : 1f - (t - 2f) / 1.2f);
                    if (t > 3.2f)
                    {
                        p.bowT = -1;
                        p.folk.SetBow(0);
                        if (p.stroller || (p.atSpot && !p.seated)) p.folk.SetPose(Folk.Pose.None);
                    }
                }
                if (!string.IsNullOrEmpty(p.plan))
                {
                    VisitorTick(p, dt);
                    continue;
                }
                p.next -= dt;
                if (p.next > 0) continue;
                if (p.stroller)
                {
                    if (!p.folk.Moving) Stroll(p);
                    p.next = 999f;
                }
                else if (p.seated && p.npc)
                {
                    // 坐着的内置香客：隔一阵拜一拜
                    p.next = Random.Range(25f, 80f);
                    p.bowT = 0;
                }
                else p.next = 5f;
            }
        }

#if UNITY_EDITOR
        /// 预览图用：直接摆好几位坐着的
        public void PreviewFill(int count) { }
#endif
    }
}
