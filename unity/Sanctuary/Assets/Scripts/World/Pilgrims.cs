using System.Collections.Generic;
using UnityEngine;

namespace Yuanjing
{
    /// 殿里的其他人。真人和内置香客长得一样（同一批 Q 版小人），由 Flutter 告诉这里谁坐在哪、在做什么。
    /// 新来的人从山门走进来，找到自己的位置坐下；走的人起身往山门走，出了门再消失。
    /// 另外院子里有几位在散步的，走到树下、香炉前停下来拜一拜，只在本机，不同步。
    public class Pilgrims : MonoBehaviour
    {
        public static Pilgrims Instance { get; private set; }

        public GameObject[] looks;          // 小人的几套样子（第 0 套留给自己）
        public Transform seatsRoot;
        public bool benchSeats;
        /// 人从哪里进来、从哪里离开
        public Vector3 entrance, entranceInside;
        /// 散步的人会去的地方：位置和看向哪里
        public Vector3[] strollPoints = new Vector3[0];
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
        }

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

        public bool Occupied(int seat)
        {
            foreach (var p in people.Values) if (p.seat == seat && !p.leaving) return true;
            return false;
        }

        Vector3 AisleNode(Vector3 p) => aislePoint + aisleDir * Vector3.Dot(p - aislePoint, aisleDir);
        bool Positive(Vector3 p) => Vector3.Dot(p - aislePoint, aisleDir) >= 0;

        Folk Spawn(string id, Vector3 at, float yaw)
        {
            int h = Mathf.Abs(id.GetHashCode());
            var prefab = looks[1 + h % (looks.Length - 1)];
            var go = Instantiate(prefab, at, Quaternion.Euler(0, yaw, 0), transform);
            go.name = "Pilgrim_" + id;
            // 高矮略有不同
            go.transform.localScale *= 0.95f + (h % 11) * 0.01f;
            var folk = go.GetComponent<Folk>();
            folk.walkSpeed *= 0.85f + (h % 7) * 0.04f;
            folk.FaceYaw(yaw);
            return folk;
        }

        Vector3 SeatLook(Vector3 seat) => new Vector3(Mathf.Lerp(seatLook.x, seat.x, seatStraight), seatLook.y, seatLook.z);

        /// 让一个人去某个座位。已经在殿里的直接换过去；新来的从山门走进来。instant：一进场就已经坐着的
        public void Place(string id, int seat, bool npc, string name, bool instant = false)
        {
            if (seats.Count == 0) return;
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
                p.folk.SetPose(benchSeats ? Folk.Pose.Bench : Folk.Pose.CrossLegged);
                p.seated = true;
            }
            else
            {
                p.folk = Spawn(id, entrance, Quaternion.LookRotation(entranceInside - entrance).eulerAngles.y);
                GoSit(p, true);
            }
            p.folk.SetName(string.IsNullOrEmpty(name) ? NpcNames[Mathf.Abs(id.GetHashCode()) % NpcNames.Length] : name, new Color(1f, 1f, 1f, 0.92f));
            people[id] = p;
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
                path.Add(AisleNode(p.folk.transform.position));
                if (Positive(p.folk.transform.position) != Positive(target))
                {
                    path.AddRange(Positive(p.folk.transform.position) ? seatExitPos : seatExitNeg);
                    var back = new List<Vector3>(Positive(target) ? seatExitPos : seatExitNeg);
                    back.Reverse();
                    path.AddRange(back);
                }
            }
            path.Add(AisleNode(target));
            path.Add(target);
            p.seated = false;
            p.folk.SetPose(Folk.Pose.None);
            p.folk.Walk(path);
            var person = p;
            System.Action arrived = null;
            arrived = () =>
            {
                person.folk.Arrived -= arrived;
                if (person.leaving) return;
                person.folk.FaceTowards(SeatLook(target));
                person.folk.SetPose(benchSeats ? Folk.Pose.Bench : Folk.Pose.CrossLegged);
                person.seated = true;
            };
            p.folk.Arrived += arrived;
        }

        /// 起身离开：走出山门再消失
        void Leave(Person p)
        {
            if (p.leaving) return;
            p.leaving = true;
            var path = new List<Vector3>();
            if (p.seated)
            {
                path.Add(AisleNode(p.folk.transform.position));
                path.AddRange(Positive(p.folk.transform.position) ? seatExitPos : seatExitNeg);
            }
            path.Add(entranceInside);
            path.Add(entrance);
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

        void Update()
        {
            float dt = Time.deltaTime;
            foreach (var p in people.Values)
            {
                if (p.leaving) continue;
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
                        if (p.stroller) p.folk.SetPose(Folk.Pose.None);
                    }
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
