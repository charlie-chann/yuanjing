using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace Yuanjing
{
    /// 殿里的香客（只在大殿开着的场景，GameDirector.hallOpen）。
    /// 院子里站着的内置香客（在殿前、香炉前、树下……行程上这一处还要待一阵的），隔一阵有一位走上台阶、从中门进殿，做一两件事：
    /// 在拜垫上跪下叩首三次、站在拜垫上对着佛像鞠躬或合掌、在殿里的蒲团上静坐一到三分钟；做完从中门出去，回到他自己的行程上。
    /// 殿里平常有一到三位，有时一个也没有（hallWant 隔一两分钟换一次）。岛上人少（不到 8 位香客）时不请人进殿。
    /// 全在本机：殿里的蒲团本来就不报给服务器（GameDirector 里殿里的蒲团），服务器的名单、座位都照旧。
    /// 让着你（玩家）：
    ///   · 你站着、跪着、坐着的，你正走过去的拜垫、蒲团（GameDirector.MySeat、PlayerGoal），香客不挑；
    ///     他正走去的那一块被你挑了，他就换一块空的，没有就出殿。他已经跪上去、坐上去的不让——那一块对你来说就是有人（见下）。
    ///   · 香客跪着、坐着、或者已经走到跟前（0.9 米）的那一块，GameDirector 不再报给你「坐下」「跪拜」（HallSeatTaken、HallMatTaken），
    ///     所以你和香客不会挑到同一块：谁先占上算谁的，你先挑（他还没到跟前）就是你的。
    ///   · 你在殿里（或正走进来）时，中间那块拜垫（供桌、上香那一条正前方，你去上香要从它上面过）留给你：香客不去；
    ///     你进殿时他正跪在上面，就拜完这一下起身走开。
    ///   · 香客不上香、不在门口和过道上停着；路上有人跪着坐着就绕开；出殿、被服务器叫走（Leave）时拜垫和蒲团都放掉。
    public partial class Pilgrims
    {
        /// 一位香客这一趟进殿要做的事
        class HallVisit
        {
            /// 要做的事，按顺序：k 跪拜叩首、b 站着鞠躬、g 合掌、m 静坐
            public string acts = "";
            public int at;
            /// 占着的拜垫、殿里的蒲团（hallSeats 的序号）；-1 是没有
            public int mat = -1, seat = -1;
            /// 已经在上面了（跪下、站在拜垫上拜、坐下、起身那几秒）：这时你挑不了它，他也不再让
            public bool on;
            /// 该出殿了（行程上该去下一处、快走了、殿里不要人了）：手上这一下做完就出去
            public bool wrap;
            /// 上一段路走到了没有（走的路上那一块被你挑了、走不到，是 false）
            public bool walked;
            /// 静坐多久（秒）
            public float sitFor;
            public float since;
            /// 测试用：指定第一件事用哪一块拜垫、哪个蒲团（-1 自己挑）
            public int force = -1;
            /// 测试指定的这一趟：到这个时刻以前不因为「行程上该去下一处了」出殿（夜里人少，请来的人行程上剩的时间短，常常还没跪下就走了）
            public float graceUntil;
            public Coroutine co;
        }

        readonly Dictionary<Person, HallVisit> hallVisits = new Dictionary<Person, HallVisit>();
        /// 刚从殿里出来的人：到这个时刻以前不再请他进去（同一个人不来回进出）
        readonly Dictionary<string, float> hallRested = new Dictionary<string, float>();
        /// 殿里此刻想有几位（0–3，隔一两分钟换一次）、下一次换的时刻、下一次请人进殿的时刻
        int hallWant;
        float hallWantUntil = -1f, hallNextIn = 5f;
        bool hallSeeded;
        /// 最近一次「一进场就在岛上」的那批人摆出来的时刻（PlaceVisitor instant）
        float instantPlacedAt = -100f;
        /// 测试用：固定殿里要几位（-1 照常随机）
        [System.NonSerialized] public int hallWantFixed = -1;
        /// 测试、排查用：殿里发生的事（进殿、跪拜、静坐、让开、出殿……）和给殿里香客的每一条路线（第一个点是起点）
        public readonly List<string> hallEvents = new List<string>();
        public readonly List<List<Vector3>> hallRoutes = new List<List<Vector3>>();

        /// 进了殿那一段的人数（正走进去、在殿里、正走出来）
        public int HallVisitors => hallVisits.Count;
        bool InHallVisit(Person p) => hallVisits.ContainsKey(p);

        static GameDirector HallGd
        {
            get
            {
                var gd = GameDirector.Instance;
                return gd != null && gd.hallOpen && gd.player != null && gd.hallMats != null && gd.hallSeats != null
                       && gd.hallMats.childCount > 0 && gd.hallSeats.childCount > 0 ? gd : null;
            }
        }

        // ── 拜垫、蒲团的位置（同 GameDirector 的算法）──

        static Vector3 MatAt(GameDirector gd, int m) => gd.hallMats.GetChild(m).position;
        static Vector3 CushionAt(GameDirector gd, int k) => gd.hallSeats.GetChild(k).position;

        static Vector3 CushionFwd(GameDirector gd, int k)
        {
            Vector3 f = gd.hallSeats.GetChild(k).forward;
            f.y = 0;
            return f.sqrMagnitude > 1e-4f ? f.normalized : Vector3.forward;
        }

        /// 坐下前站的那一点（方草垫上，同 GameDirector.SeatStand）：f 是谁（高矮不同站得远近不同）；null 按你（玩家）
        static Vector3 CushionStand(GameDirector gd, int k, Folk f) =>
            CushionAt(gd, k) + CushionFwd(gd, k) * Folk.SeatStep * (f != null ? f.transform.lossyScale.y : gd.player.transform.lossyScale.y) / 0.806f;

        /// 蒲团前的走道上正对着它的一点（同 GameDirector.SeatLane）
        static Vector3 CushionLane(GameDirector gd, int k) => CushionAt(gd, k) + CushionFwd(gd, k) * gd.hallLane;

        /// 中间那块拜垫：离上香站的那一点最近的
        static int CentreMat(GameDirector gd)
        {
            int best = 0;
            for (int m = 1; m < gd.hallMats.childCount; m++)
                if (Flat(MatAt(gd, m), gd.altarStand) < Flat(MatAt(gd, best), gd.altarStand)) best = m;
            return best;
        }

        // ── 你（玩家）要用的 ──

        /// 你在殿里、在殿门口，或者正往殿里走
        static bool PlayerInHall(GameDirector gd)
        {
            Vector3 me = gd.player.transform.position;
            if (gd.InHall(me) || Flat(me, gd.hallDoorOut) < 1.6f) return true;
            var g = gd.PlayerGoal;
            return g.HasValue && gd.InHall(g.Value);
        }

        /// 你站在 c 附近（r 米内；正推着摇杆走过去的只算一半远），或者正走去 c
        static bool PlayerAt(GameDirector gd, Vector3 c, float r)
        {
            float d = Flat(gd.player.transform.position, c);
            if (d < r * 0.5f || (d < r && gd.player.Motion(1f).sqrMagnitude < 0.09f)) return true;
            var g = gd.PlayerGoal;
            return g.HasValue && Flat(g.Value, c) < 0.6f;
        }

        /// 这块拜垫你要用（站在跟前、正走过去），或者你在殿里而它是中间那块
        static bool PlayerWantsMat(GameDirector gd, int m) => PlayerAt(gd, MatAt(gd, m), 0.8f) || (m == CentreMat(gd) && PlayerInHall(gd));

        /// 这个蒲团你坐着、正走过去要坐（MySeat），或者你就站在它前面、站在它上面
        bool PlayerWantsSeat(GameDirector gd, int k) =>
            gd.MySeat == SeatCount + k || PlayerAt(gd, CushionStand(gd, k, null), 0.7f) || Flat(gd.player.transform.position, CushionAt(gd, k)) < 0.6f;

        /// 殿里第 k 个蒲团（hallSeats 的序号）有香客：坐在上面（正坐下、正起身也算），或者已经走到跟前（0.9 米）要坐了。
        /// GameDirector.SeatFree 用：这样的不报「坐下」、点了也不坐（会换身边另一个空的）
        public bool HallSeatTaken(int k)
        {
            var gd = HallGd;
            if (gd == null || k < 0 || k >= gd.hallSeats.childCount) return false;
            foreach (var kv in hallVisits)
            {
                if (kv.Value.seat != k) continue;
                if (kv.Value.on) return true;
                var f = kv.Key.folk;
                if (f != null && Flat(f.transform.position, CushionStand(gd, k, f)) < 0.9f) return true;
            }
            return false;
        }

        /// 第 m 块拜垫有香客：跪着、站在上面拜，或者已经走到跟前（0.9 米）。GameDirector.NearestMat、Act 用
        public bool HallMatTaken(int m)
        {
            var gd = HallGd;
            if (gd == null || m < 0 || m >= gd.hallMats.childCount) return false;
            foreach (var kv in hallVisits)
            {
                if (kv.Value.mat != m) continue;
                if (kv.Value.on) return true;
                var f = kv.Key.folk;
                if (f != null && Flat(f.transform.position, MatAt(gd, m)) < 0.9f) return true;
            }
            return false;
        }

        // ── 挑拜垫、蒲团 ──

        /// c 附近 r 米内有没有别人（你、别的香客、院子里的人；不算 me）
        static bool Someone(Vector3 c, float r, Folk me)
        {
            foreach (var f in Folk.All)
                if (f != null && f != me && f.isActiveAndEnabled && Flat(f.transform.position, c) < r) return true;
            return false;
        }

        bool MatHeld(int m, Person me)
        {
            foreach (var kv in hallVisits) if (kv.Key != me && kv.Value.mat == m) return true;
            return false;
        }

        bool SeatHeld(int k, Person me)
        {
            foreach (var kv in hallVisits) if (kv.Key != me && kv.Value.seat == k) return true;
            return false;
        }

        bool MatOk(GameDirector gd, int m, Person me) => !MatHeld(m, me) && !PlayerWantsMat(gd, m) && !Someone(MatAt(gd, m), 0.7f, me.folk);

        bool SeatOk(GameDirector gd, int k, Person me) =>
            !SeatHeld(k, me) && !PlayerWantsSeat(gd, k) && !Someone(CushionStand(gd, k, me.folk), 0.6f, me.folk) && !Someone(CushionAt(gd, k), 0.5f, me.folk);

        /// 别的香客正跪在（站在）第 m 块拜垫上
        bool MatOnByOther(int m, Person me)
        {
            foreach (var kv in hallVisits) if (kv.Key != me && kv.Value.mat == m && kv.Value.on) return true;
            return false;
        }

        /// 测试指定的那一块用不用得上：你要用、有人站（跪、坐）在上面就用不上，返回为什么；用得上是 null。
        /// 别的香客只是正往那一块走（还没上去）不算：叫他换一块（BumpMat）
        string ForcedMatBlock(GameDirector gd, int m, Person me)
        {
            if (PlayerWantsMat(gd, m)) return "你要用";
            foreach (var kv in hallVisits)
                if (kv.Key != me && kv.Value.mat == m && kv.Value.on) return $"{kv.Key.id} 在上面";
            foreach (var f in Folk.All)
                if (f != null && f != me.folk && f.isActiveAndEnabled && !f.Moving && Flat(f.transform.position, MatAt(gd, m)) < 0.45f) return $"{f.name} 站在上面";
            return null;
        }

        /// 别的香客正往第 m 块走（还没上去）：叫他换一块（他走路时看见 v.mat 变了就停下、另挑）
        void BumpMat(int m, Person me)
        {
            foreach (var kv in hallVisits)
                if (kv.Key != me && kv.Value.mat == m && !kv.Value.on)
                {
                    kv.Value.mat = -1;
                    HallEvent($"让开拜垫 {kv.Key.id} 拜垫{m}（{me.id} 指定了这一块）");
                }
        }

        /// 挑一块空拜垫：别的香客没占、你不用、上面没人站着；离你远的优先，中间那块少去。
        /// 测试指定了哪一块（v.force）就用那一块：别的香客正走过去的让给他，只有你要用、有人在上面才换（记下为什么）
        int PickMat(GameDirector gd, Person me, HallVisit v)
        {
            if (v.force >= 0 && v.force < gd.hallMats.childCount)
            {
                string why = ForcedMatBlock(gd, v.force, me);
                if (why == null)
                {
                    BumpMat(v.force, me);
                    return v.force;
                }
                HallEvent($"指定的拜垫用不上 {me.id} 拜垫{v.force}：{why}，换一块");
            }
            int best = -1, centre = CentreMat(gd);
            float bestScore = float.MinValue;
            Vector3 you = gd.player.transform.position;
            for (int m = 0; m < gd.hallMats.childCount; m++)
            {
                if (!MatOk(gd, m, me)) continue;
                float score = Random.value + (Flat(MatAt(gd, m), you) > 2.2f ? 0.6f : 0f) - (m == centre ? 0.35f : 0f);
                if (score > bestScore) { bestScore = score; best = m; }
            }
            return best;
        }

        /// 挑一个空蒲团：别的香客没占、你没坐没要坐、跟前没人；离你远的优先
        int PickSeat(GameDirector gd, Person me, HallVisit v)
        {
            if (v.force >= 0 && v.force < gd.hallSeats.childCount && SeatOk(gd, v.force, me)) return v.force;
            int best = -1;
            float bestScore = float.MinValue;
            Vector3 you = gd.player.transform.position;
            for (int k = 0; k < gd.hallSeats.childCount; k++)
            {
                if (!SeatOk(gd, k, me)) continue;
                float score = Random.value + (Flat(CushionAt(gd, k), you) > 2.2f ? 0.6f : 0f);
                if (score > bestScore) { bestScore = score; best = k; }
            }
            return best;
        }

        // ── 请谁进殿 ──

        /// 行程上这一处还能待多久（秒，同 StepAt 的分法；最后一件事待到快走）
        float StepLeft(Person p)
        {
            float elapsed = Time.time - p.arrive, end = p.stay - 40f;
            if (p.step < p.plan.Length - 1)
            {
                float total = 0, acc = 0, usable = Mathf.Max(30f, p.stay - 45f);
                foreach (char c in p.plan) total += Weight(c);
                for (int i = 0; i <= p.step; i++) acc += Weight(p.plan[i]) / total * usable;
                end = Mathf.Min(end, acc);
            }
            return end - elapsed;
        }

        /// 能请进殿的：内置香客，站在行程上的某一处（不是静坐那一处，没在走、没在拜），最近没进过殿，这一处还能待一分半钟以上
        bool HallCandidate(Person p, float minLeft)
        {
            if (p.leaving || p.stroller || !p.npc || p.folk == null || string.IsNullOrEmpty(p.plan) || p.step < 0 || p.step >= p.plan.Length) return false;
            if (p.seated || p.toSeat >= 0 || p.folk.Moving || !p.atSpot || p.bowT >= 0 || p.plan[p.step] == 's' || hallVisits.ContainsKey(p)) return false;
            if (hallRested.TryGetValue(p.id, out float t) && Time.time < t) return false;
            return StepLeft(p) > minLeft;
        }

        /// 挑一位：在殿前（行程是 h）的优先，其次离殿门近的
        Person HallPickVisitor(GameDirector gd, float minLeft)
        {
            Person best = null;
            float bestScore = float.MinValue;
            foreach (var p in people.Values)
            {
                if (!HallCandidate(p, minLeft)) continue;
                float score = (p.plan[p.step] == 'h' ? 3f : 0f) - Flat(p.folk.transform.position, gd.hallDoorOut) / 12f + Random.value;
                if (score > bestScore) { bestScore = score; best = p; }
            }
            return best;
        }

        /// 岛上的内置香客有几位（人少时不请人进殿）
        int VisitorCount()
        {
            int n = 0;
            foreach (var p in people.Values) if (!p.leaving && p.npc && !string.IsNullOrEmpty(p.plan)) n++;
            return n;
        }

        /// 这一趟做什么：一两件。time：行程上这一处还能待多久（秒）；静坐一到三分钟，待不了那么久就短一点，太短就不坐
        static string HallActs(float time, out float sitFor)
        {
            sitFor = 0;
            float r = Random.value;
            char a = r < 0.38f ? 'k' : r < 0.55f ? 'b' : r < 0.65f ? 'g' : 'm';
            string acts = a.ToString();
            if (Random.value < 0.55f)
            {
                char b = a == 'm' ? (Random.value < 0.6f ? 'k' : 'b')
                       : Random.value < 0.6f ? 'm'
                       : a == 'k' ? (Random.value < 0.5f ? 'b' : 'g') : 'k';
                acts += b;
            }
            if (acts.Contains("m"))
            {
                float room = time - 55f - (acts.Length - 1) * 45f;
                sitFor = Mathf.Min(Random.Range(60f, 180f), room);
                if (sitFor < 45f)
                {
                    acts = acts.Replace("m", "");
                    if (acts.Length == 0) acts = "k";
                    sitFor = 0;
                }
            }
            return acts;
        }

        /// 每帧：隔一阵换一次殿里想有几位；人不够就从院子里请一位进来
        void HallUpdate(float dt)
        {
            var gd = HallGd;
            if (gd == null) return;
            if (!hallSeeded) HallSeed(gd);
            if (Time.time >= hallWantUntil)
            {
                float r = Random.value;
                hallWant = r < 0.12f ? 0 : r < 0.45f ? 1 : r < 0.8f ? 2 : 3;
                hallWantUntil = Time.time + Random.Range(70f, 160f);
            }
            int want = hallWantFixed >= 0 ? hallWantFixed : hallWant;
            if (hallVisits.Count >= want || Time.time < hallNextIn) return;
            hallNextIn = Time.time + 3f;
            if (VisitorCount() < 8) return;
            var p = HallPickVisitor(gd, 110f);
            if (p == null) return;
            string acts = HallActs(StepLeft(p), out float sitFor);
            HallBegin(p, new HallVisit { acts = acts, sitFor = sitFor });
            // 一位一位地来，前后隔一阵
            hallNextIn = Time.time + Random.Range(10f, 28f);
        }

        /// 进场时已经在岛上的那一批人里，有一两位本来就在殿里静坐（不然你一进殿总是空的）。只在第一次有人时做一次
        void HallSeed(GameDirector gd)
        {
            // 只在一批人刚摆出来的那一秒里做（进场、服务器名单头一次来）：以后人多起来了再做，就是把院子里站着的人当着你的面变到殿里的蒲团上
            if (Time.time - instantPlacedAt > 1f)
            {
                if (VisitorCount() > 0) hallSeeded = true;
                return;
            }
            if (VisitorCount() < 8) return;
            hallSeeded = true;
            if (hallWantFixed == 0) return;
            float r = Random.value;
            int count = r < 0.3f ? 0 : r < 0.75f ? 1 : 2;
            for (int i = 0; i < count; i++)
            {
                var p = HallPickVisitor(gd, 90f);
                if (p == null) break;
                var v = new HallVisit { acts = Random.value < 0.4f ? "mk" : "m", sitFor = Mathf.Min(Random.Range(20f, 150f), StepLeft(p) - 70f) };
                int k = PickSeat(gd, p, v);
                if (k < 0 || v.sitFor < 15f) break;
                // 直接坐在蒲团上（刚进场，这一批人本来就是这一刻摆出来的）
                Vector3 g = CushionAt(gd, k);
                float yaw = Quaternion.LookRotation(CushionFwd(gd, k)).eulerAngles.y;
                p.folk.StopWalking();
                p.folk.transform.SetPositionAndRotation(g, Quaternion.Euler(0, yaw, 0));
                p.folk.FaceYaw(yaw);
                p.folk.SetPose(Folk.Pose.CrossLegged, true);
                p.folk.SeatedAt(g, CushionStand(gd, k, p.folk));
                v.seat = k;
                v.on = true;
                HallBegin(p, v);
            }
            hallNextIn = Time.time + Random.Range(5f, 15f);
        }

        void HallBegin(Person p, HallVisit v)
        {
            v.since = Time.time;
            hallVisits[p] = v;
            p.atSpot = false;
            p.bowT = -1;
            p.folk.SetBow(0);
            // 原来行程上那条路线的「到了」作废
            p.gen++;
            HallEvent($"进殿 {p.id} {v.acts}{(v.on ? $" 本来就坐在蒲团{v.seat}" : "")}{(v.force >= 0 ? $" 指定{v.force}" : "")}");
            v.co = StartCoroutine(HallRun(p, v));
        }

        // ── 进了殿以后 ──

        /// 行程上该去下一处了、快走了（服务器的时间为准）、殿里不要人了：做完手上这一下就出殿
        void HallCheck(Person p, HallVisit v)
        {
            if (v.wrap) return;
            if (hallWantFixed == 0 && hallQuiet) v.wrap = true;
            if (!string.IsNullOrEmpty(p.plan) && Time.time >= v.graceUntil)
            {
                float elapsed = Time.time - p.arrive;
                if (elapsed >= p.stay - 40f || StepAt(p, elapsed) != p.step) v.wrap = true;
            }
            // 保险：一趟最多十分钟
            if (Time.time - v.since > 600f) v.wrap = true;
        }

        /// 手上这一下早点收：要出殿了，或者在中间那块拜垫上而你进殿了
        bool HallCut(GameDirector gd, Person p, HallVisit v)
        {
            HallCheck(p, v);
            return v.wrap || (v.mat >= 0 && v.mat == CentreMat(gd) && PlayerInHall(gd));
        }

        IEnumerator HallRun(Person p, HallVisit v)
        {
            var gd = HallGd;
            for (v.at = 0; v.at < v.acts.Length && gd != null; v.at++)
            {
                HallCheck(p, v);
                if (v.wrap) break;
                char a = v.acts[v.at];
                if (a == 'm') yield return HallMeditate(gd, p, v);
                else yield return HallWorship(gd, p, v, a);
                v.force = -1;
            }
            HallFree(v);
            // 出殿：从中门出去、沿中线走下台阶，到了台阶下再回到自己的行程上（还没走上廊下就不用）
            if (gd != null && p.folk != null && NearHall(gd, p.folk.transform.position))
            {
                List<Vector3> Out()
                {
                    var path = HallRoute(gd, p.folk.transform.position, gd.hallDoorOut, p);
                    path.Add(StepsFoot(gd));
                    return path;
                }
                // 台阶下常站着几位（行程是「殿前」的人）：走到跟前一米半、挤不过去就算到了
                yield return HallWalk(gd, p, v, Out, null, 1.5f);
            }
            HallDone(p, v);
        }

        /// 在拜垫上：k 跪下叩首三次；b 站着鞠躬一到三次；g 合掌低头
        IEnumerator HallWorship(GameDirector gd, Person p, HallVisit v, char a)
        {
            for (int tries = 0; tries < 3; tries++)
            {
                if (HallCut(gd, p, v) && v.wrap) yield break;
                if (tries == 0 && v.force >= 0 && v.force < gd.hallMats.childCount && MatOnByOther(v.force, p))
                {
                    // 测试指定的那一块上正有别的香客在拜：先占着（别人不再挑它），等他起来再走过去（一次跪拜叩首不到二十秒）
                    v.mat = v.force;
                    HallEvent($"等拜垫 {p.id} 拜垫{v.force}（有人在上面）");
                    for (float t = 0; t < 30f && MatOnByOther(v.force, p) && !v.wrap; t += Time.deltaTime)
                    {
                        HallCheck(p, v);
                        yield return null;
                    }
                    v.mat = -1;
                }
                int m = PickMat(gd, p, v);
                if (m < 0)
                {
                    HallEvent($"没有空拜垫 {p.id}");
                    yield break;
                }
                v.mat = m;
                Vector3 at = MatAt(gd, m);
                p.target = at;
                // 走的路上：你挑了这一块、该走了、或者这一块让给了测试指定它的人（v.mat 被改了）就停下
                yield return HallWalk(gd, p, v, () => HallRoute(gd, p.folk.transform.position, at, p), () => PlayerWantsMat(gd, m) || HallCut(gd, p, v) || v.mat != m);
                if (v.walked && v.mat == m)
                {
                    // 面朝佛像，转过来再拜（跪的话 Folk 自己也会先等转过来）
                    float yaw = Quaternion.LookRotation(gd.hallFacing).eulerAngles.y;
                    p.folk.FaceYaw(yaw);
                    for (float t = 0; t < 2.5f && Mathf.Abs(Mathf.DeltaAngle(p.folk.transform.eulerAngles.y, yaw)) > 6f && !PlayerWantsMat(gd, m) && v.mat == m; t += Time.deltaTime)
                        yield return null;
                }
                if (!v.walked || PlayerWantsMat(gd, m) || HallCut(gd, p, v) || v.mat != m)
                {
                    // 你挑了这一块（或者该走了、让给了别人）：换一块，没有就算了
                    if (PlayerWantsMat(gd, m)) HallEvent($"让开拜垫 {p.id} 拜垫{m}");
                    else if (!v.walked && v.mat == m) HallEvent($"没走到拜垫 {p.id} 拜垫{m}");
                    v.mat = -1;
                    continue;
                }
                v.on = true;
                HallEvent($"{(a == 'k' ? "跪拜" : a == 'b' ? "鞠躬" : "合掌")} {p.id} 拜垫{m}");
                if (a == 'k') yield return HallKneel(gd, p, v);
                else yield return HallBowStanding(gd, p, v, a);
                v.on = false;
                v.mat = -1;
                yield break;
            }
        }

        /// 跪下、叩首三次、跪直一会儿、起来（同 GameDirector.ActBody 的 kneel 节奏）
        IEnumerator HallKneel(GameDirector gd, Person p, HallVisit v)
        {
            var f = p.folk;
            f.SetPose(Folk.Pose.Kneel);
            // 跪下去那段 2.5 秒，跪稳了再拜
            yield return new WaitForSeconds(2.7f);
            f.SetPose(Folk.Pose.KneelBow);
            for (int i = 0; i < 3; i++)
            {
                if (i > 0 && HallCut(gd, p, v)) break;
                yield return NpcBow(f, 1.4f, 1.0f, 1.3f);
                yield return new WaitForSeconds(Random.Range(0.1f, 0.5f));
            }
            f.SetPose(Folk.Pose.Kneel);
            yield return new WaitForSeconds(HallCut(gd, p, v) ? 0.5f : Random.Range(0.8f, 3f));
            // 起身那段 2.6 秒，站起来了才算完
            f.SetPose(Folk.Pose.None);
            yield return new WaitForSeconds(2.7f);
        }

        /// 站在拜垫上对着佛像：鞠躬一到三次，或者合掌低头停几秒
        IEnumerator HallBowStanding(GameDirector gd, Person p, HallVisit v, char a)
        {
            var f = p.folk;
            f.SetPose(a == 'g' ? Folk.Pose.Gassho : Folk.Pose.Bow);
            for (float t = 0; t < 3f && !f.ActionReady; t += Time.deltaTime) yield return null;
            yield return new WaitForSeconds(0.4f);
            if (a == 'g') yield return NpcBow(f, 1.2f, Random.Range(2.5f, 4.5f), 1.2f);
            else
            {
                int n = Random.Range(1, 4);
                for (int i = 0; i < n; i++)
                {
                    if (i > 0 && HallCut(gd, p, v)) break;
                    yield return NpcBow(f, 1.1f, 0.7f, 1.2f);
                    yield return new WaitForSeconds(0.3f);
                }
            }
            f.SetBow(0);
            f.SetPose(Folk.Pose.None);
            // 放下手
            yield return new WaitForSeconds(1.2f);
        }

        /// 在殿里的蒲团上静坐：走到蒲团前、转身坐下、合掌一拜、静坐 sitFor 秒、再一拜、起身退到走道上
        IEnumerator HallMeditate(GameDirector gd, Person p, HallVisit v)
        {
            var f = p.folk;
            if (!(v.on && v.seat >= 0))
            {
                bool sat = false;
                for (int tries = 0; tries < 3 && !sat; tries++)
                {
                    HallCheck(p, v);
                    if (v.wrap) yield break;
                    int k = PickSeat(gd, p, v);
                    if (k < 0)
                    {
                        HallEvent($"没有空蒲团 {p.id}");
                        yield break;
                    }
                    v.seat = k;
                    Vector3 lane = CushionLane(gd, k), stand = CushionStand(gd, k, f);
                    p.target = stand;
                    List<Vector3> To()
                    {
                        var path = HallRoute(gd, f.transform.position, lane, p);
                        path.Add(stand);
                        return path;
                    }
                    yield return HallWalk(gd, p, v, To, () => PlayerWantsSeat(gd, k) || v.wrap);
                    if (v.walked)
                    {
                        // 到了草垫上：先转身（背对蒲团），转过来再坐（同 SitWhenFacing）
                        float yaw0 = Quaternion.LookRotation(CushionFwd(gd, k)).eulerAngles.y;
                        f.FaceYaw(yaw0);
                        for (float t = 0; t < 2.5f && Mathf.Abs(Mathf.DeltaAngle(f.transform.eulerAngles.y, yaw0)) > 3f && !PlayerWantsSeat(gd, k); t += Time.deltaTime)
                            yield return null;
                    }
                    if (!v.walked || PlayerWantsSeat(gd, k) || v.wrap)
                    {
                        if (PlayerWantsSeat(gd, k)) HallEvent($"让开蒲团 {p.id} 蒲团{k}");
                        v.seat = -1;
                        continue;
                    }
                    v.on = true;
                    f.SitOn(CushionAt(gd, k), Quaternion.LookRotation(CushionFwd(gd, k)).eulerAngles.y);
                    HallEvent($"静坐 {p.id} 蒲团{k} {v.sitFor:F0}秒");
                    sat = true;
                }
                if (!sat) yield break;
                // 坐下去那段，坐稳了合掌一拜
                yield return new WaitForSeconds(3.2f);
                yield return NpcBow(f, 1.4f, 1.6f, 1.4f);
            }
            else HallEvent($"静坐 {p.id} 蒲团{v.seat} {v.sitFor:F0}秒（本来就坐着）");
            float until = Time.time + v.sitFor;
            while (Time.time < until)
            {
                HallCheck(p, v);
                if (v.wrap) break;
                yield return null;
            }
            // 收坐：再一拜，起身（Sit_Up 自己带着人往前站到草垫上），退到走道上
            if (!v.wrap) yield return NpcBow(f, 1.4f, 1.2f, 1.4f);
            int seat = v.seat;
            f.SetBow(0);
            f.SetPose(Folk.Pose.None);
            yield return new WaitForSeconds(0.5f);
            for (float t = 0; t < 4f && f.InTransition; t += Time.deltaTime) yield return null;
            Vector3 back = CushionLane(gd, seat);
            yield return HallWalk(gd, p, v, () => new List<Vector3> { back }, null);
            v.on = false;
            v.seat = -1;
        }

        /// 鞠躬的节奏：俯下去、停一下、起来（同 GameDirector.BowOnce）
        static IEnumerator NpcBow(Folk f, float down, float hold, float up)
        {
            for (float t = 0; t < down; t += Time.deltaTime) { f.SetBow(t / down); yield return null; }
            f.SetBow(1);
            yield return new WaitForSeconds(hold);
            for (float t = 0; t < up; t += Time.deltaTime) { f.SetBow(1 - t / up); yield return null; }
            f.SetBow(0);
        }

        /// 沿路线走过去（同院子里的走法：Folk.Walk）。route() 给出从此刻站的地方出发的路线。走到了 v.walked 为 true；
        /// 路上 abort() 为 true（那一块被你挑了、该走了）就停下。卡住的兜底同 GameDirector：离终点不到 near 米（平常 0.6）、1.5 秒没走近就算到了；
        /// 离得还远、2.5 秒原地没挪开 0.25 米（被人挤住了、挤进窄缝里了）：从站的地方重新找路，最多三次（还在院子里的就不进殿了）；走得太久就停下（v.walked false）。
        /// （绕着柱子、经案走的那几秒离终点不一定更近，所以按挪没挪动算，不按离终点远近算）
        IEnumerator HallWalk(GameDirector gd, Person p, HallVisit v, System.Func<List<Vector3>> route, System.Func<bool> abort, float near = 0.6f)
        {
            v.walked = false;
            var f = p.folk;
            var clean = HallSmooth(gd, f.transform.position, route());
            if (clean.Count == 0)
            {
                v.walked = true;
                yield break;
            }
            HallLogRoute(p, clean);
            p.gen++;
            f.Walk(clean);
            Vector3 goal = clean[clean.Count - 1];
            float t0 = Time.time, budget = HallBudget(f, clean), best = float.MaxValue, bestT = Time.time, markT = Time.time;
            Vector3 mark = f.transform.position;
            int replans = 0;
            while (f.Moving)
            {
                if (abort != null && abort())
                {
                    f.StopWalking();
                    yield break;
                }
                float d = Flat(f.transform.position, goal);
                if (d < best - 0.03f || f.InTransition) { best = Mathf.Min(best, d); bestT = Time.time; }
                if (Flat(f.transform.position, mark) > 0.25f || f.InTransition) { mark = f.transform.position; markT = Time.time; }
                if (d >= near && Time.time - markT > 2.5f && replans < 3)
                {
                    replans++;
                    float nearest = 99f;
                    foreach (var o in Folk.All) if (o != null && o != f) nearest = Mathf.Min(nearest, Flat(o.transform.position, f.transform.position));
                    HallEvent($"重新找路 {p.id} 在 {f.transform.position.x:F2},{f.transform.position.z:F2}，离最近的人 {nearest:F2} 米，{f.pose} {f.DebugLoco()}");
                    if (replans >= 3 && !NearHall(gd, f.transform.position))
                    {
                        // 还在院子里就走不动了（人挤人）：这一趟不进殿了，回自己的行程上
                        HallEvent($"不进殿了 {p.id}");
                        v.wrap = true;
                        f.StopWalking();
                        yield break;
                    }
                    var before = clean;
                    clean = HallSmooth(gd, f.transform.position, route());
                    if (clean.Count == 0) break;
                    // 新找的路和刚才那条一样（找路的觉得走得通，人却挤在这里挪不动）：先往空的那一边横着挪半步，再接着走
                    if (SameHeading(f.transform.position, before, clean))
                    {
                        var side = Sidestep(gd, f, clean);
                        if (side.HasValue)
                        {
                            clean.Insert(0, side.Value);
                            HallEvent($"横挪一步 {p.id} 到 {side.Value.x:F2},{side.Value.z:F2}");
                        }
                    }
                    HallLogRoute(p, clean);
                    f.Walk(clean);
                    goal = clean[clean.Count - 1];
                    t0 = bestT = markT = Time.time;
                    mark = f.transform.position;
                    best = float.MaxValue;
                    budget = HallBudget(f, clean);
                }
                else if ((d < near && Time.time - bestT > 1.5f) || Time.time - t0 > budget)
                {
                    if (d < near)
                    {
                        f.ArriveNow();
                        break;
                    }
                    HallEvent($"走不到 {p.id} 还差 {d:F2} 米");
                    f.StopWalking();
                    yield break;
                }
                yield return null;
            }
            v.walked = true;
        }

        /// 路线上从 at 往前走 d 米到的那一点（old 是老路线时，从老路线上离 at 最近的那一点算起）
        static Vector3 Ahead(Vector3 at, List<Vector3> path, float d, bool fromNearest)
        {
            int start = 0;
            Vector3 a = at;
            if (fromNearest)
            {
                float bd = float.MaxValue;
                for (int i = 0; i < path.Count; i++)
                {
                    float x = Flat(path[i], at);
                    if (x < bd) { bd = x; start = i; }
                }
                a = path[start];
            }
            for (int i = start; i < path.Count; i++)
            {
                float len = Flat(a, path[i]);
                if (len >= d) return Vector3.MoveTowards(a, path[i], d);
                d -= len;
                a = path[i];
            }
            return path.Count > 0 ? path[path.Count - 1] : at;
        }

        /// 新路线起头那一米和老路线在这儿往后那一米是不是同一个方向（差不到 25 度）
        static bool SameHeading(Vector3 at, List<Vector3> old, List<Vector3> now)
        {
            if (old == null || old.Count == 0 || now.Count == 0) return false;
            Vector3 a = Ahead(at, old, 1f, true) - at, b = Ahead(at, now, 1f, false) - at;
            a.y = b.y = 0;
            if (a.sqrMagnitude < 0.01f || b.sqrMagnitude < 0.01f) return false;
            return Vector3.Angle(a, b) < 25f;
        }

        /// 卡住时横着挪开的那一点：路线方向的左右各 0.5 米，挑离别人远、不在东西那一圈里的一边；两边都不行是 null
        Vector3? Sidestep(GameDirector gd, Folk f, List<Vector3> path)
        {
            Vector3 at = f.transform.position, d = Ahead(at, path, 1f, false) - at;
            d.y = 0;
            if (d.sqrMagnitude < 0.01f) return null;
            d.Normalize();
            Vector3 left = new Vector3(-d.z, 0, d.x);
            Vector3? best = null;
            float bestRoom = 0.45f;
            foreach (float side in new[] { 1f, -1f })
            {
                Vector3 q = at + left * side * 0.5f;
                if (NearHall(gd, at) && (InPad(gd, q) || !PadClear(gd, at, q))) continue;
                float room = 99f;
                foreach (var o in Folk.All)
                    if (o != null && o != f && o.isActiveAndEnabled) room = Mathf.Min(room, Flat(o.transform.position, q));
                if (room > bestRoom) { bestRoom = room; best = q; }
            }
            return best;
        }

        static float HallBudget(Folk f, List<Vector3> path)
        {
            float len = 0;
            Vector3 a = f.transform.position;
            foreach (var q in path) { len += Flat(a, q); a = q; }
            return len / Mathf.Max(0.3f, f.walkSpeed * 0.5f) + 10f;
        }

        /// 交给 Folk 之前：去掉挨得太近的点；殿里、廊下的拐角往外挪一点；人此刻挤在圈里的，先退到最近的圈外那一点。
        /// Folk 看着前面 0.4–0.65 米的那一点走，拐弯时会往里切一二十厘米，路线本来就是贴着柱子、功德箱这些拐的（只让出人的半个身子），
        /// 一切就蹭进去了。拐角往外推出差不多切掉的那么多（推出去的地方得站得下人），人实际走的弧线就落回原来的拐角上
        List<Vector3> HallSmooth(GameDirector gd, Vector3 from, List<Vector3> path)
        {
            var clean = new List<Vector3>();
            Vector3 last = from;
            if (NearHall(gd, from) && InPad(gd, from, 0.1f))
            {
                Vector3 esc = PadEscape(gd, from);
                if (Flat(esc, from) > 0.04f)
                {
                    clean.Add(esc);
                    last = esc;
                }
            }
            foreach (var q in path)
            {
                if (Flat(q, last) < 0.08f) continue;
                clean.Add(q);
                last = q;
            }
            for (int i = 0; i + 1 < clean.Count; i++)
            {
                Vector3 prev = i == 0 ? from : clean[i - 1], v = clean[i], next = clean[i + 1];
                if (!NearHall(gd, v)) continue;
                Vector3 a = v - prev, b = next - v;
                a.y = b.y = 0;
                float la = a.magnitude, lb = b.magnitude;
                if (la < 0.05f || lb < 0.05f) continue;
                a /= la;
                b /= lb;
                float turn = Vector3.Angle(a, b);
                if (turn < 15f) continue;
                Vector3 o = a - b;
                o.y = 0;
                if (o.sqrMagnitude < 1e-6f) continue;
                o.Normalize();
                float bulge = Mathf.Min(0.22f, 0.3f * Mathf.Sin(turn * 0.5f * Mathf.Deg2Rad), 0.4f * Mathf.Min(la, lb));
                // 一头在圈里（起步、到终点那一下）的拐角不挪
                if (InPad(gd, prev) || InPad(gd, next)) continue;
                for (int k = 0; k < 2; k++, bulge *= 0.5f)
                {
                    // 挪出去的那一点、连着它的两段都得在圈外（同总控规划路线的规矩）
                    Vector3 w = v + o * bulge;
                    if (InPad(gd, w) || !PadClear(gd, prev, w) || !PadClear(gd, w, next)) continue;
                    clean[i] = w;
                    break;
                }
            }
            // 殿里、廊下每 0.2 米一个点：Folk 离下一个点 0.45 米就把它丢掉、直奔再下一个点，拐角稀的话一个直角会切进去 0.4 米多
            // （比路线让出的那一圈还多）；点密了，人就一直追着前面半米左右的那一点，拐弯只切一两寸
            var dense = new List<Vector3>();
            Vector3 at = from;
            foreach (var q in clean)
            {
                float len = Flat(at, q);
                if (len > 0.3f && NearHall(gd, at) && NearHall(gd, q))
                {
                    int n = Mathf.CeilToInt(len / 0.2f);
                    for (int k = 1; k < n; k++) dense.Add(Vector3.Lerp(at, q, k / (float)n));
                }
                dense.Add(q);
                at = q;
            }
            return dense;
        }

        // ── 殿里的路线 ──

        /// 绕行用的点（x, z）：拜垫那一排后面、两根金柱之间、供桌前那一条的两头
        static readonly Vector2[] HallVias =
        {
            new Vector2(-1.6f, 17.0f), new Vector2(1.6f, 17.0f), new Vector2(-0.55f, 16.95f), new Vector2(0.55f, 16.95f),
            new Vector2(-2.1f, 17.1f), new Vector2(2.1f, 17.1f), new Vector2(-1.6f, 18.55f), new Vector2(1.6f, 18.55f),
            new Vector2(-3.3f, 16.7f), new Vector2(3.3f, 16.7f),
        };

        /// 殿前台阶下、中线上那一点（「去大殿」站的地方）：进殿先走到这里再沿中线上台阶，出殿走到这里再回自己的行程
        static Vector3 StepsFoot(GameDirector gd)
        {
            foreach (var s in gd.spots) if (s.name == "hall") return s.floor;
            return gd.hallDoorOut + Vector3.back * 5f;
        }

        /// 在殿里，或者在殿前的廊下（台基上）
        static bool NearHall(GameDirector gd, Vector3 p) => gd.InHall(p) || (p.z > 11.2f && p.z < gd.hallRect.yMin + 0.1f && Mathf.Abs(p.x) < 8.6f && p.y > gd.hallFloor - 0.2f);

        /// 殿里的路线：总控的路线（殿里绕开柱子、经案、供桌、圆蒲团，从中门进出）。从院子里进殿的先走到殿前台阶下，沿中线上台阶、穿过廊下到中门
        /// （总控从院子直接斜着走到门口，会从台基侧面的栏杆、廊下的柱子中间穿过去，也会顺着廊下挤进侧门里面那个小角落）。
        /// 殿里那一段路上要是有人跪着、坐着、站着不动（你、别的香客），就试几个绕行的点，第一条不碰人的就用
        List<Vector3> HallRoute(GameDirector gd, Vector3 from, Vector3 to, Person me)
        {
            var lead = new List<Vector3>();
            if (!NearHall(gd, from) && NearHall(gd, to))
            {
                lead.AddRange(Plan(from, StepsFoot(gd)));
                lead.Add(gd.hallDoorOut);
                from = gd.hallDoorOut;
            }
            var path = HallRouteIn(gd, from, to, me);
            lead.AddRange(path);
            return lead;
        }

        List<Vector3> HallRouteIn(GameDirector gd, Vector3 from, Vector3 to, Person me)
        {
            var still = new List<Vector3>();
            foreach (var f in Folk.All)
            {
                if (f == null || f == me.folk || !f.isActiveAndEnabled || f.Moving) continue;
                Vector3 q = f.transform.position;
                if (gd.InHall(q) && Flat(q, to) > 0.5f && Flat(q, from) > 0.5f) still.Add(q);
            }
            // 网格上直接绕开停着的人（离每人 0.6 米）：以前只按柱子、经案找路，再拿几个绕行点去试，全碰人就照原路走——
            // 你站在门里偏东（过道和东边金柱之间）时，去东边拜垫的香客径直走到你跟前，挤着原地踏步二十多秒
            var path = still.Count > 0 ? gd.PlanPathAvoiding(from, to, still, 0.6f) : Plan(from, to);
            if (still.Count == 0 || RouteClear(from, path, still)) return path;
            // 绕行点按「经过它的直线距离」由近到远试，第一条不碰人的就用（每试一个点要规划两段，不全试）
            var vias = new List<Vector3>();
            foreach (var w2 in HallVias) vias.Add(new Vector3(w2.x, gd.hallFloor, w2.y));
            vias.Sort((x, y) => (Flat(from, x) + Flat(x, to)).CompareTo(Flat(from, y) + Flat(y, to)));
            foreach (var w in vias)
            {
                var c = new List<Vector3>(gd.PlanPathAvoiding(from, w, still, 0.6f));
                c.AddRange(gd.PlanPathAvoiding(w, to, still, 0.6f));
                if (RouteClear(from, c, still)) return c;
            }
            return path;
        }

        /// 这条路离停着的人都有 0.55 米以上吗（两头 0.4 米内不算：从人跟前起步、走到人跟前的那一下）
        static bool RouteClear(Vector3 from, List<Vector3> path, List<Vector3> still)
        {
            Vector3 prev = from, end = path.Count > 0 ? path[path.Count - 1] : from;
            foreach (var q in path)
            {
                float len = Flat(prev, q);
                for (float d = 0; d <= len; d += 0.1f)
                {
                    Vector3 x = Vector3.MoveTowards(new Vector3(prev.x, 0, prev.z), new Vector3(q.x, 0, q.z), d);
                    if (Flat(x, from) < 0.4f || Flat(x, end) < 0.4f) continue;
                    foreach (var s in still) if (Flat(x, s) < 0.55f) return false;
                }
                prev = q;
            }
            return true;
        }

        // ── 不蹭进东西里 ──
        // 殿里的路线（GameDirector.HallPlan）离柱子、门扇、功德箱、经案、供桌都让出一圈（障碍的 radius：柱子 0.55，方的 0.25），
        // 圆蒲团让出 0.36。香客没有碰撞胶囊，下面几处都按这同一圈来算：拐角往外挪、挤进圈里了推出来、卡住了先退到圈外再找路

        /// 挨得着殿里、廊下的障碍（只取一次）
        Obstacle[] hallPads;

        Obstacle[] HallPads(GameDirector gd)
        {
            if (hallPads != null) return hallPads;
            var list = new List<Obstacle>();
            Rect r = gd.hallRect;
            foreach (var o in gd.obstacles)
            {
                float ex = o.half.x + o.radius, ez = o.half.y + o.radius;
                if (o.center.x + ex < r.xMin || o.center.x - ex > r.xMax || o.center.z + ez < 11.2f || o.center.z - ez > r.yMax) continue;
                list.Add(o);
            }
            return hallPads = list.ToArray();
        }

        /// 离障碍多远（水平；圆的到中心，方的到边，在里面是 0），和往外的方向
        static float PadDist(Obstacle o, Vector3 p, out Vector3 outDir)
        {
            float rx = p.x - o.center.x, rz = p.z - o.center.z;
            float dx = Mathf.Abs(rx) - o.half.x, dz = Mathf.Abs(rz) - o.half.y;
            if (dx <= 0 && dz <= 0)
            {
                // 在方块里面（或者圆心上）：往离边最近的那一面出去
                outDir = o.half == Vector2.zero ? Vector3.back : dx > dz ? new Vector3(Mathf.Sign(rx), 0, 0) : new Vector3(0, 0, Mathf.Sign(rz));
                return 0f;
            }
            var v = new Vector3(dx > 0 ? Mathf.Sign(rx) * dx : 0, 0, dz > 0 ? Mathf.Sign(rz) * dz : 0);
            float d = v.magnitude;
            outDir = v / d;
            return d;
        }

        /// 这一点在不在哪个障碍那一圈里（往里 shrink 米以内的不算），或者踩在圆蒲团上
        bool InPad(GameDirector gd, Vector3 p, float shrink = 0f)
        {
            foreach (var o in HallPads(gd)) if (PadDist(o, p, out _) < o.radius - shrink) return true;
            return OnZafu(gd, p, 0.36f - shrink);
        }

        /// 两点之间直着走，一路都在圈外吗（每 8 厘米看一下，同 GameDirector.HallClear）
        bool PadClear(GameDirector gd, Vector3 a, Vector3 b)
        {
            int n = Mathf.Max(1, Mathf.CeilToInt(Flat(a, b) / 0.08f));
            for (int k = 1; k <= n; k++) if (InPad(gd, Vector3.Lerp(a, b, k / (float)n))) return false;
            return true;
        }

        /// 踩在殿里的圆蒲团上（离圆蒲团中心 r 米以内）
        static bool OnZafu(GameDirector gd, Vector3 at, float r)
        {
            for (int k = 0; k < gd.hallSeats.childCount; k++) if (Flat(CushionAt(gd, k), at) < r) return true;
            return false;
        }

        /// 离 p 最近的、在所有圈外的一点（一圈圈往外找，最远 0.8 米）；找不到就是 p
        Vector3 PadEscape(GameDirector gd, Vector3 p)
        {
            if (!InPad(gd, p)) return p;
            for (float r = 0.06f; r <= 0.8f; r += 0.06f)
                for (int i = 0; i < 24; i++)
                {
                    float a = i * Mathf.PI * 2f / 24f;
                    Vector3 q = p + new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a)) * r;
                    if (gd.InHall(new Vector3(q.x, gd.hallFloor, q.z)) && !InPad(gd, q)) return q;
                }
            return p;
        }

        /// 殿里、廊下走着站着的人：按路线走拐弯会往里切一点、互相让开时会被挤过去，就蹭进柱子、门扇、功德箱那一圈里。
        /// 每帧（走路的位移之后）把人从圈里推回圈边上（留 5 厘米，切一点点角不管）——圈比东西本身大出人的半个身子，推回去就碰不到。
        /// 圆蒲团不推（走去坐的人要站到蒲团跟前）。跪着、坐着、拜着的不动
        void LateUpdate()
        {
            var gd = HallGd;
            if (gd == null) return;
            foreach (var p in people.Values)
            {
                var f = p.folk;
                if (f == null || f.pose != Folk.Pose.None) continue;
                Vector3 at = f.transform.position;
                if (!NearHall(gd, at)) continue;
                Vector3 push = Vector3.zero;
                foreach (var o in HallPads(gd))
                {
                    float d = PadDist(o, at, out var dir), want = o.radius - 0.05f;
                    if (d < want) push += dir * (want - d);
                }
                if (push.sqrMagnitude > 1e-8f) f.transform.position = at + Vector3.ClampMagnitude(push, 0.1f);
            }
        }

        // ── 出殿 ──

        static void HallFree(HallVisit v)
        {
            v.mat = v.seat = -1;
            v.on = false;
        }

        /// 走到廊下了：放掉一切，回到自己的行程上（行程上该去哪就去哪；快走了就离开）
        void HallDone(Person p, HallVisit v)
        {
            HallFree(v);
            hallVisits.Remove(p);
            hallRested[p.id] = Time.time + Random.Range(240f, 600f);
            HallEvent($"出殿 {p.id}");
            if (p.leaving || p.folk == null) return;
            p.target = new Vector3(9999, 0, 9999);
            p.folk.SetBow(0);
            if (string.IsNullOrEmpty(p.plan)) return;
            float elapsed = Time.time - p.arrive;
            if (elapsed >= p.stay - 40f) Leave(p);
            else GoStep(p, StepAt(p, elapsed));
        }

        /// Leave 时人还在殿里那一段（服务器叫走了）：停掉，放掉拜垫、蒲团；坐在蒲团上的先退到蒲团前的走道上（加在 path 前头）。
        /// 返回是不是殿里那一段的人
        bool HallQuit(Person p, List<Vector3> path)
        {
            if (!hallVisits.TryGetValue(p, out var v)) return false;
            if (v.co != null) StopCoroutine(v.co);
            var gd = HallGd;
            if (gd != null && v.seat >= 0 && v.on) path.Add(CushionLane(gd, v.seat));
            HallFree(v);
            hallVisits.Remove(p);
            if (p.folk != null) p.folk.SetBow(0);
            HallEvent($"被叫走 {p.id}");
            return true;
        }

        // ── 测试、排查 ──

        bool hallQuiet;

        /// 测试用：开、关殿里的香客。关：不再请人进殿，殿里的人做完手上这一下就出来
        public void HallCrowd(bool on)
        {
            hallQuiet = !on;
            hallWantFixed = on ? -1 : 0;
            if (!on) foreach (var v in hallVisits.Values) v.wrap = true;
        }

        /// 测试用：马上请一位香客进殿做 act（k 跪拜、b 鞠躬、g 合掌：拜垫 index；m 静坐：蒲团 index；index -1 自己挑）。返回他的 id，没有能请的人是 null
        public string HallSend(string act, int index, float sitFor = 90f)
        {
            var gd = HallGd;
            if (gd == null || string.IsNullOrEmpty(act)) return null;
            // 先找行程上这一处还能待两分半钟以上的（做完这一件再走）；没有再放宽
            var p = HallPickVisitor(gd, 150f) ?? HallPickVisitor(gd, 60f);
            if (p == null)
            {
                // 一时没有合适的（都在静坐、在走、刚出殿）：放宽一点，在走着的、刚出过殿的也行（测试要的是有人来）
                float best = float.MaxValue;
                foreach (var q in people.Values)
                {
                    if (q.leaving || q.stroller || !q.npc || q.folk == null || string.IsNullOrEmpty(q.plan) || q.step < 0 || q.seated || q.toSeat >= 0 || hallVisits.ContainsKey(q)) continue;
                    float d = Flat(q.folk.transform.position, gd.hallDoorOut);
                    if (StepLeft(q) > 30f && d < best) { best = d; p = q; }
                }
                if (p == null) return null;
            }
            HallBegin(p, new HallVisit { acts = act, force = index, sitFor = act.Contains("m") ? sitFor : 0, graceUntil = Time.time + 150f + (act.Contains("m") ? sitFor : 0) });
            return p.id;
        }

        /// 测试用：某人此刻在殿里那一段的样子："k1+"（跪拜、拜垫 1、已经在上面）、"m5"（静坐、蒲团 5、还没坐下）、"k"（还没挑到）；不在殿里那一段是 ""
        public string HallSlot(string id)
        {
            if (string.IsNullOrEmpty(id) || !people.TryGetValue(id, out var p) || !hallVisits.TryGetValue(p, out var v)) return "";
            char a = v.at < v.acts.Length ? v.acts[v.at] : '-';
            int i = a == 'm' ? v.seat : v.mat;
            return $"{a}{(i >= 0 ? i.ToString() : "")}{(v.on ? "+" : "")}";
        }

        /// 排查用：殿里那一段的人和各自在做什么
        public string HallSummary()
        {
            var sb = new System.Text.StringBuilder();
            sb.Append($"殿里那一段 {hallVisits.Count} 位（想要 {(hallWantFixed >= 0 ? hallWantFixed : hallWant)}）");
            foreach (var kv in hallVisits) sb.Append($"；{kv.Key.id} {kv.Value.acts} {HallSlot(kv.Key.id)}");
            return sb.ToString();
        }

        /// 排查用的记录（测试读它）：只在编辑器、开发版里记，正式版不记（每条路线一长串字，几千条）
        [System.Diagnostics.Conditional("UNITY_EDITOR"), System.Diagnostics.Conditional("DEVELOPMENT_BUILD")]
        void HallEvent(string s)
        {
            hallEvents.Add($"{Time.time:F1} {s}");
            if (hallEvents.Count > 2000) hallEvents.RemoveRange(0, 500);
        }

        /// 记下给殿里香客的一条路线（第一个点是他此刻站的地方）；同 HallEvent，只在编辑器、开发版里记
        [System.Diagnostics.Conditional("UNITY_EDITOR"), System.Diagnostics.Conditional("DEVELOPMENT_BUILD")]
        void HallLogRoute(Person p, List<Vector3> path)
        {
            var r = new List<Vector3> { p.folk != null ? p.folk.transform.position : path[0] };
            r.AddRange(path);
            hallRoutes.Add(r);
            if (hallRoutes.Count > 2000) hallRoutes.RemoveRange(0, 500);
            var sb = new System.Text.StringBuilder($"路线 {p.id}");
            foreach (var q in r) sb.Append($" {q.x:F2},{q.z:F2}");
            HallEvent(sb.ToString());
        }
    }
}
