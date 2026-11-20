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
        /// 「在这里」的范围：zoneRadius 大于 0 时，离 zone 这么近都算（许愿树：绳圈一周都算树下）；不填就是离 floor 不到 nearRadius
        public Vector3 zone;
        public float zoneRadius;
    }

    /// 要绕开的东西（香炉、树池、石灯笼、水池），按圆算。half 不是 0 的是长方的（殿里的供桌、经案、功德箱、磬、木鱼）：
    /// 长方（x、z 各一半的长度 half）往外再让出 radius（人的半个身子加一点空）
    [Serializable]
    public class Obstacle
    {
        public Vector3 center;
        public float radius;
        public Vector2 half;
    }

    /// 殿里的总控：收 Flutter 发来的指令（进场、换天色天气、走动、坐下、做动作、留心意），
    /// 指挥自己的小人和第三人称镜头，再把结果告诉 Flutter。寺庙和教堂用同一份，只是地点和路线的数据不同。
    ///
    /// Flutter → 这里（JSON，cmd 字段）：
    ///   enter    {scene, time, weather, seed, name} 进场。seed 是先摆几位本地 NPC，name 是自己头顶的名字
    ///   move     {x, y}                       摇杆（-1..1，y 朝前），松手发 0,0。方向按按下那一刻镜头的朝向算
    ///   sky      {time, weather, instant}     换天色天气
    ///   goto     {spot}                       走到某个地点
    ///   sit      {seat}                       坐到身边（sitRadius 以内）最近的空蒲团；seat 是 near 里报的那个，这边会再核一遍
    ///   stand                                 坐着时起身，退到这一排前面的走道上
    ///   act      {action, mat}                bow 鞠躬 / kneel 跪拜 / pray 合掌 / meditate 静坐。
    ///                                         mat：殿里拜垫的序号（near 里报的那个），给了就先走上那块拜垫、面朝佛像再做
    ///   offer    {kind, text, tex}            ribbon 红布条 / plaque 木牌 / incense 上香 / coin 抛硬币 / candle 点蜡烛。
    ///                                         布条木牌：text 是写的愿望，tex 是 Flutter 写好字的灰度图（PNG 的 base64，白是布、黑是墨）。
    ///                                         上香：在殿里就走到中间供桌前，拿三支香、举香拜三拜、插进香炉；在院子里插在香炉里
    ///   offerings{list:"3", kind, id, tex, mine} 树上已经挂着的（id 是服务器编号，同一件不重复挂；tex 同上，可以没有；
    ///                                         mine：自己以前挂的——认领那一格上自己刚挂、还没编号的那件，也不会被取下）
    ///   pilgrims {list:"id:座位:是不是NPC:名字|..."} 现在寺里有谁
    ///   pact     {id, action}                 某个人做了动作
    ///   look     {dx, dy}                     拖动画面，镜头绕着人转
    ///   view     {kind}                       top 俯视 / level 平视 / low 仰视 / first 第一人称（在殿里只能平视、第一人称）
    ///   zoom     {x}                          放大倍数（1 到 8）
    ///   tap      {x, y}                       点了画面上某处（0..1，左上角是原点）
    ///   audio    {on, volume}                 声音开关
    ///   bell                                  敲一下钟
    ///   pets / petact / feed                  小动物
    /// 这里 → Flutter（type 字段）：
    ///   entered {scene, seats, slots, hall, nohang}（hall：大殿能不能进去；nohang：自己挂不了的格子，如 "18,19,20"——
    ///           绘马架前站不了人。Flutter 摆别人的心意时先往这几格放，「给自己留几格」只数挂得了的）  moving {to}
    ///   arrived {spot}（走到或走近了某个地点；每次自动走完、被摇杆打断都会发一次。spot 是 inhall 就是在大殿里面）
    ///   seated {seat}  stood  sitFailed {reason}（none 身边没有空蒲团 / busy 正忙 / taken 走到跟前被人先坐了）  actionDone {action}
    ///   hung {kind, slot}（布条、木牌系到绳上的那一刻：Flutter 这时就记到服务器，后面退半步、合掌时离开也不会丢）
    ///   offered {kind, slot}（布条亲手系好、合完掌了，香插好了）
    ///   offerFailed {kind, reason}（full：挂得了的格子全是自己的了；busy：正忙）
    ///   near {pet, water, seat, mat, altar}（身边的小动物、水边、sitRadius 以内最近的空蒲团、殿里 0.9 米内的拜垫（没有都是 -1）、
    ///         是不是在中间供桌前能上香）
    ///   view {mode, locked}（locked：在殿里，只能平视、第一人称，Flutter 把俯视、仰视藏起来）  thunder  petGift
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
        /// 石凳（湖心小寺石台上的）：坐下前站在凳前多远。座位点在凳面上，seatDrop 是凳面高；人走到凳前、背对凳子站好再坐下（Folk.SitBench）。
        /// 0 是教堂的长椅：直接走到座位点上
        public float benchStep;
        /// 殿的另外几个门（左右次间）：门外、门里各一点，和 hallDoorOut / hallDoorIn 一样用；进出殿挑顺路的那个门
        public Vector3[] hallSideDoorsOut = new Vector3[0], hallSideDoorsIn = new Vector3[0];
        /// 走到离地点多近算到了
        public float nearRadius = 2.0f;
        /// 座位区（一排排蒲团）的范围，x 是左右、y 是南北（世界 z）；进出一律走中间的过道
        public Rect seatBlock = Rect.MinMaxRect(-11.6f, 1.7f, 11.6f, 9.4f);
        /// 过道两头的进出口（从座位区外面进来先走到这里）
        public Vector3[] seatEntries = new Vector3[0];
        /// 殿里静坐的蒲团：这个物体下面的子物体，位置是圆蒲团下的地面，朝向是坐下以后面朝的方向。
        /// 序号接在院子里的座位后面（SeatCount 起），不报给服务器、香客不坐
        public Transform hallSeats;
        /// 殿里蒲团前面那条走道离蒲团多远（院子里的用 laneOffset）
        public float hallLane = 0.55f;
        /// 蒲团之间的空当离蒲团中心多远：人在蒲团后面时从这里绕到前面
        public float seatGap = 0.62f, hallSeatGap = 0.45f;
        /// 离蒲团前面站的那一点多近，才显示「坐下」、才能坐
        public float sitRadius = 1.2f;
        /// 挂布条时站在绳子外面多远。Hang_Loop 里两手心在人前方约 0.43 米：站 0.48 米，系的时候手指正好搭在绳子上（站 0.45 米时指节陷进绳子里）
        public float hangStand = 0.48f;
        /// 许愿树的绳圈（中心、半径；0 是没有）：绳子挡人，点了绳圈里面的地只走到绳外
        public Vector3 ropeCenter;
        public float ropeRadius;

        // ── 大殿里面（第二阶段新大殿放进来以后 hallOpen 为 true；坐标见 spec：殿内地面 0.72，门在 z 14.3） ──
        /// 大殿能不能走进去
        public bool hallOpen;
        /// 殿里的范围：x 左右、y 是世界 z（南北）。站在这里面、脚下高过 hallFloor - 0.22 就算进殿了
        public Rect hallRect = Rect.MinMaxRect(-6.5f, 14.4f, 6.5f, 22.0f);
        public float hallFloor = 0.72f;
        /// 进出殿门：门外廊下一点、门里一点（中间那扇门，净宽 1.65 米）
        public Vector3 hallDoorOut = new Vector3(0, 0.72f, 14.0f), hallDoorIn = new Vector3(0, 0.72f, 15.0f);
        /// 拜垫：这个物体下面的子物体，位置是拜垫中心下面的地面。离哪块 matRadius 以内，就能在那块上拜
        public Transform hallMats;
        public float matRadius = 0.9f;
        /// 在殿里拜、上香时面朝哪（佛像在北边）
        public Vector3 hallFacing = Vector3.forward;
        /// 上香：站在中间供桌前哪一点、离它多近算「在供桌前」、香插到哪（殿里香炉灰面的中心）
        /// （上香的人一直站在这里，不再往前挪：Incense_Plant 脚不动、俯身，手正好伸到灰面中心上方，人前方 0.48 米）
        public Vector3 altarStand = new Vector3(0, 0.72f, 18.52f);
        public float altarRadius = 1.6f;
        public Vector3 hallIncense = new Vector3(0, 1.682f, 19.0f);
        /// 殿里镜头的天花板（梁底）：第三人称镜头不超过它
        public float hallCeiling = 5.35f;
        /// 殿里平视镜头的高低（俯角，度）：比外面低，比人的腰高一点；画面再往上抬着把佛像放进来（见 ThirdPersonCamera.FrameTilt）
        public float hallCamPitch = -2f;
        /// 殿里人脚下接触影子的材质（YJContact，BuildIslet 给）
        public Material contactShadow;
        /// 在拜垫上跪拜时的镜头高低（镜头也退远到 3 米，ViewSwitcher.Wide）：和跪着的人头差不多高，平着看过去，画面往上抬把佛像放进来
        public float hallKneelPitch = 0f;
        /// 三尊佛像的头顶（肉髻顶）：殿里平视时画面尽量把正前方那一尊整个放进来
        public Vector3[] hallLookAts = { new Vector3(0, 4.45f, 21.0f), new Vector3(-3.6f, 4.0f, 21.0f), new Vector3(3.6f, 4.0f, 21.0f) };
        /// 殿里镜头不钻进去的几块（三张供桌连同佛坛前那一片，到桌上香炉、烛台的顶）：在供桌前回头看殿门时，镜头抬到桌上东西的上面，不从香炉后面看人
        public Bounds[] hallCamKeepOut =
        {
            new Bounds(new Vector3(0, 1.6f, 19.45f), new Vector3(2.8f, 1.9f, 1.5f)),
            new Bounds(new Vector3(-3.6f, 1.6f, 19.55f), new Vector3(1.9f, 1.9f, 1.3f)),
            new Bounds(new Vector3(3.6f, 1.6f, 19.55f), new Vector3(1.9f, 1.9f, 1.3f)),
        };
        /// 坐在院子里的蒲团上时平视镜头的俯角（镜头也收近到 2.6 米，ViewSwitcher.Seated）
        public float seatedCamPitch = 21f;
        /// 殿里自动走路最北走到哪（再往北是供桌、佛坛）
        public float hallWalkMaxZ = 18.95f;
        /// 往里走过这条线就算进了院子（不填就用集散点的位置）
        public float courtMinZ = float.NaN;

        // ── 铺好的路 ──
        /// 院子里铺好的路（码头 → 山门 → 主路 → 香炉外一圈 → 石台中间过道 → 殿前台阶 → 殿门，加上去许愿树、池塘的踏脚石）：
        /// 路上的点（roadNodes）和连线（roadLinks，两个一组的点序号）。自动走路（去大殿、进殿、去香炉、去许愿树、坐下、点画面走过去）
        /// 顺着路走不比直着穿草地远太多就顺着路走（见 Road）。没填就照旧直着走、绕开东西
        public Vector3[] roadNodes = new Vector3[0];
        public int[] roadLinks = new int[0];
        /// 不在路上走（穿草地、从路边斜插过去）一米按几米算：越大越愿意绕到路上走
        public float offRoadCost = 1.7f;
        /// 自动走路不穿过的线（x0, z0, x1, z1，水平面上）：山门两边（门柱到岸边：从码头上岛、去码头一定从山门过）、
        /// 大殿台基的边（上下殿走台阶）、殿墙和槛窗（进出殿走中间三间的门）。只管规划路线，摇杆照样走（真挡人的是碰撞）
        public Vector4[] planWalls = new Vector4[0];
        public string bell = "sfx_bell_temple";

        // ── 靠近才能做的事：钓鱼、敲钟、喂小鸟 ──
        /// 水面高度；小池塘在哪、多大（站在它边上钓的是池塘里的鱼，别处的水边是湖）
        public float waterY = -0.42f;
        public Vector3 pondCenter = new Vector3(8.8f, 0, -4.2f);
        public float pondRadius = 4.6f;
        public Fishing fishing;
        /// 钟亭里的钟：离它 bellRadius 以内才显示「敲钟」
        public BellRing bellRing;
        public Vector3 bellAt = new Vector3(14.4f, 0, 6.6f);
        public float bellRadius = 3.0f;
        /// 离落在地上的小鸟多近才显示「喂小鸟」
        public float birdRadius = 5.5f;

        [Serializable]
        class Msg
        {
            public string cmd, scene, time, weather, spot, action, kind, id, list, name, text, tex, item;
            public int seat = -1, slot = -1, mat = -1, seed;
            public float dx, dy, x, y, volume = 1;
            public bool instant, on = true, mine;
        }

        // 换殿：先记下进场指令，新场景加载好以后再执行
        static string pendingEnter;
        static bool loading;

        string at = "";
        int mySeat = -1;
        /// 正走过去要坐的蒲团（还没坐下）：香客挑座位时也避开它；坐下那一刻才变成 mySeat
        int pendingSeat = -1;
        /// 走到蒲团前、转身坐下的那一小段（转身的 0.8 秒）。推摇杆、点别处、起身都会先停掉它
        Coroutine sitting;
        bool acting, autoWalk, synced;
        /// 人在不在殿里（在的话锁平视），进殿前是什么视角（出殿时换回去）
        bool inHall;
        string viewBeforeHall;
        Action onArrive;
        Vector2 stick, stickFrom;
        /// 摇杆按下那一刻镜头的朝向：一直按着时都按它算方向（镜头自己慢慢转，人走的路不会跟着弯成圆圈）
        float stickYaw;
        bool stickHeld;
        float nextChime = 30, nextBell = 170;
        /// 正拿在手里、还没系上的布条或木牌，和为它占着的那一格
        GameObject held;
        int heldSlot = -1;
        /// 走去绳子那里的路上捏在手里的（布条卷、拎着的木牌）：抬手要系时换成 held
        GameObject carry;

        /// 自己坐在、或者正走过去要坐的第几个座位（-1 是没有）。香客挑座位时避开它
        public int MySeat => mySeat >= 0 ? mySeat : pendingSeat;

        /// 不坐了：停掉转身坐下那一段，放掉正要去坐的蒲团
        void CancelSit()
        {
            if (sitting != null) StopCoroutine(sitting);
            sitting = null;
            pendingSeat = -1;
        }

        /// 停下脚步，连摇杆留下的速度也清掉（做动作、挂布条时不再推摇杆，速度不清的话人会一路滑出去）
        void Halt()
        {
            player.StopWalking();
            player.Drive(Vector3.zero);
        }

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
            Folk.ContactMaterial = contactShadow;
            if (!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("YJ_PROBE"))) gameObject.AddComponent<RenderProbe>();
            if (TimeWeather.Instance != null) TimeWeather.Instance.Thunder += () => Send("{\"type\":\"thunder\"}");
            var s = Find(startSpot);
            if (s != null) PlaceAt(s);
            // 殿里走路的网格先算好（第一次点「坐下」「跪拜」时不再卡一下）
            if (hallOpen) HallGrid();
            // 拜垫（12 厘米高）、殿里蒲团前的方草垫一圈：走上去、走下来时身子慢慢抬、脚踩在垫子面上（Folk.GroundIK）
            Folk.StepZones.Clear();
            if (hallMats != null)
                foreach (Transform m in hallMats) Folk.StepZones.Add(new Rect(m.position.x - 0.75f, m.position.z - 0.8f, 1.5f, 1.6f));
            if (hallSeats != null)
                foreach (Transform h in hallSeats) Folk.StepZones.Add(new Rect(h.position.x - 0.8f, h.position.z - 0.8f, 1.6f, 1.6f));
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
            // 从石凳上起身、原点还在往凳前滑：等滑完再开（Update 里接着开）
            if (player.BenchGliding) { freeMoveLater = true; return; }
            if (player.controller != null && !player.controller.enabled && mySeat < 0 && !acting && !autoWalk) player.controller.enabled = true;
        }
        bool freeMoveLater;

        /// 别的脚本要绕开院子里的东西走路时用
        public List<Vector3> PlanPath(Vector3 a, Vector3 b) => Route(a, b);

        /// 座位区（石台上一排排蒲团）：只有设了 laneOffset 的场景才有
        bool InSeats(Vector3 p) => laneOffset != Vector3.zero && seatBlock.Contains(new Vector2(p.x, p.z));

        /// 中间过道有多宽的一半（过道里没有蒲团，可以直着走）
        public float aisleHalf = 0.85f;

        /// 这段路会不会踩过蒲团（穿过座位区、又不是沿着中间过道）
        bool CrossesSeats(Vector3 a, Vector3 b)
        {
            if (laneOffset == Vector3.zero) return false;
            for (int i = 1; i < 24; i++)
            {
                Vector3 p = Vector3.Lerp(a, b, i / 24f);
                if (InSeats(p) && Mathf.Abs(p.x - aislePoint.x) > aisleHalf) return true;
            }
            return false;
        }

        /// 点在不在殿里（只看水平位置，不管高低）
        bool InHallXZ(Vector3 p) => hallOpen && hallRect.Contains(new Vector2(p.x, p.z));
        /// 人在不在殿里：在殿的范围里、脚下是殿里的地面（台基上），不是台基外面的地上
        public bool InHall(Vector3 p) => InHallXZ(p) && p.y > hallFloor - 0.22f;

        /// 规划路线：一头在殿里就从中间那扇门进出；院子里进出座位区一律走中间的过道（不从蒲团上踩过去），同一排走道上的直接横着走
        List<Vector3> Route(Vector3 a, Vector3 b)
        {
            bool ha = InHallXZ(a), hb = InHallXZ(b);
            if (ha && hb) return HallPlan(a, b);
            if (ha || hb)
            {
                // 门外廊下一点、门里一点：殿里那一段绕开柱子、经案、供桌、门扇（obstacles 里有），外面那一段照院子里的走法
                var r = new List<Vector3>();
                // 三间门都开着：挑顺路的那个（殿里那一头到门里、殿外那一头到门外的直线距离加起来最短；差不多就走中门）
                Vector3 dOut = hallDoorOut, dIn = hallDoorIn;
                Vector3 inP = ha ? a : b, outP = ha ? b : a;
                float bestD = FlatDist(inP, dIn) + FlatDist(outP, dOut) - 1.5f;
                for (int k = 0; k < hallSideDoorsOut.Length && k < hallSideDoorsIn.Length; k++)
                {
                    float d = FlatDist(inP, hallSideDoorsIn[k]) + FlatDist(outP, hallSideDoorsOut[k]);
                    if (d < bestD) { bestD = d; dOut = hallSideDoorsOut[k]; dIn = hallSideDoorsIn[k]; }
                }
                if (ha)
                {
                    r.AddRange(HallPlan(a, dIn));
                    r.Add(dOut);
                    r.AddRange(RouteOutside(dOut, b));
                }
                else
                {
                    r.AddRange(RouteOutside(a, dOut));
                    r.Add(dIn);
                    r.AddRange(HallPlan(dIn, b));
                }
                return r;
            }
            return RouteOutside(a, b);
        }

        /// 殿里走路：东西挨得近（柱子、经案、木鱼、门扇之间常常只剩二三十厘米），绕一个圆的走法会挤过去。
        /// 这里按 0.1 米一格的网格找最短路（A*，避开障碍圆和四面墙），再拉直成几段直线。
        /// 殿里的障碍、圆蒲团都不会动：哪些格子走不了只在第一次用（或进场）时算一遍（HallGrid），
        /// 以后每次只跑 A*（二叉堆）、由近往远找起点终点的格子——以前每走一次都把整张网格、全岛的障碍重算一遍，一次 70–230 毫秒，点「坐下」「跪拜」「出殿」都会卡一下
        List<Vector3> HallPlan(Vector3 a, Vector3 b)
        {
            HallGrid();
            // 拜垫不踩着走过去（上香、去别的拜垫、去蒲团都从拜垫旁边绕）：只有起点、终点所在的那一块能踩
            matAllowA = HallMatAt(a);
            matAllowB = HallMatAt(b);
            matsBlock = true;
            try
            {
                // 要绕开的人（PlanPathAvoiding）：绕不开（人把过道堵死了）就不管人再找一遍，交给走路时互相让
                var r = HallPlanGrid(a, b);
                if (r == null)
                {
                    hallAvoid.Clear();
                    r = HallPlanGrid(a, b);
                }
                return r;
            }
            finally { matsBlock = false; }
        }

        /// 殿里找路时临时绕开的人：x、z 是人站的地方，y 是绕开的半径（PlanPathAvoiding 填上，找完清掉）
        readonly List<Vector3> hallAvoid = new List<Vector3>();
        /// 正在算网格里固定的障碍（HallGrid）：这时不算要绕开的人
        bool hallGridBuilding;

        /// 同 PlanPath，只是殿里那一段离 people 里每个人至少 r 米（网格上把人周围一圈当成走不了的格子，A* 自己绕过去）。
        /// 起点、终点跟前的人不算（从人跟前起步、走到人旁边那一块拜垫）；人把路堵死了就照常找（走路时互相让开）。
        /// 殿里的香客找路用：你（玩家）站在门里、过道上时，以前路线照样从你身上穿过去，走到你跟前挤住、原地踏步二三十秒
        public List<Vector3> PlanPathAvoiding(Vector3 a, Vector3 b, IList<Vector3> people, float r)
        {
            hallAvoid.Clear();
            foreach (var q in people)
                if (FlatDist(q, a) > r + 0.1f && FlatDist(q, b) > r + 0.1f) hallAvoid.Add(new Vector3(q.x, r, q.z));
            try { return Route(a, b); }
            finally { hallAvoid.Clear(); }
        }

        /// 这一点离要绕开的人太近
        bool NearAvoided(Vector3 p)
        {
            if (hallGridBuilding) return false;
            foreach (var h in hallAvoid)
            {
                float dx = p.x - h.x, dz = p.z - h.z;
                if (dx * dx + dz * dz < h.y * h.y) return true;
            }
            return false;
        }

        /// 第 c 格此刻走不了：固定的障碍以外，不该踩的拜垫、要绕开的人
        bool CellOff(int c) => hallBlocked[c] || MatCellBlocked(c) || (hallAvoid.Count > 0 && NearAvoided(HallP(c, 0f)));

        List<Vector3> HallPlanGrid(Vector3 a, Vector3 b)
        {
            var direct = new List<Vector3> { b };
            if (HallClear(a, b)) return direct;
            float y = Mathf.Lerp(a.y, b.y, 0.5f);
            int sa = HallSnap(a), sb = HallSnap(b);
            // 绕着人找不到：返回 null，HallPlan 不管人再找一遍
            if (sa < 0 || sb < 0) return hallAvoid.Count > 0 ? null : Plan(a, b);
            if (!HallAStar(sa, sb)) return hallAvoid.Count > 0 ? null : Plan(a, b);
            var cells = new List<Vector3>();
            for (int c = sb; c != sa; c = hallFrom[c]) cells.Add(HallP(c, y));
            cells.Add(HallP(sa, y));
            cells.Reverse();
            cells.Add(b);
            // 拉直：从当前点往后看，能直着走到的最远那一点，就直接走过去
            var path = new List<Vector3>();
            Vector3 at = a;
            int idx = 0;
            while (idx < cells.Count)
            {
                int far = idx;
                for (int k = cells.Count - 1; k > idx; k--)
                    if (HallClear(at, cells[k])) { far = k; break; }
                at = cells[far];
                path.Add(at);
                idx = far + 1;
            }
            return path;
        }

        // ── 殿里走路的网格（HallPlan 用）：一格 0.1 米——经案和金柱、门扇和金柱之间这种只比人宽一点的空当也找得到 ──
        const float HallCell = 0.1f, HallWallPad = 0.25f;
        /// 走不了的格子（下标 i * hallNz + j，i 是东西、j 是南北）；null 是还没算
        bool[] hallBlocked;
        int hallNx, hallNz;
        float hallX0, hallZ0, hallZMax;
        /// 挨得着殿里那块地的障碍（院子里的树、石头、池子不用每一步都算）、殿里圆蒲团的位置
        Obstacle[] hallObs = new Obstacle[0];
        Vector3[] hallZafu = new Vector3[0];
        /// 拜垫（往外让 0.15 米）、每一格落在哪块拜垫上（-1 不在）；规划时（matsBlock）除了起点、终点那一块都走不了
        Rect[] hallMatRects = new Rect[0];
        int[] hallMatOf;
        int matAllowA = -1, matAllowB = -1;
        bool matsBlock;

        int HallMatAt(Vector3 p)
        {
            for (int k = 0; k < hallMatRects.Length; k++) if (hallMatRects[k].Contains(new Vector2(p.x, p.z))) return k;
            return -1;
        }

        bool MatCellBlocked(int c) => matsBlock && hallMatOf != null && hallMatOf[c] >= 0 && hallMatOf[c] != matAllowA && hallMatOf[c] != matAllowB;
        /// 网格是按哪一份 obstacles 算的（换了就重算）
        Obstacle[] hallGridFor;
        // A* 用的（每次清零重用，不每次新开）
        float[] hallG;
        int[] hallFrom;
        bool[] hallDone;
        readonly List<(float f, int c)> hallHeap = new List<(float, int)>();
        readonly List<(float d, int c)> hallNear = new List<(float, int)>();

        /// 算一遍殿里哪些格子走不了（障碍、蒲团都不动，只算一次）
        void HallGrid()
        {
            if (hallBlocked != null && hallGridFor == obstacles) return;
            hallGridFor = obstacles;
            hallX0 = hallRect.xMin + HallWallPad;
            hallZ0 = hallRect.yMin + 0.27f;
            hallZMax = Mathf.Min(hallRect.yMax - HallWallPad, hallWalkMaxZ);
            hallNx = Mathf.Max(1, Mathf.FloorToInt((hallRect.width - 2 * HallWallPad) / HallCell) + 1);
            hallNz = Mathf.Max(1, Mathf.FloorToInt((hallZMax - hallZ0) / HallCell) + 1);
            // 外接框（中心 ± 半边长 + 半径）碰得到殿里那块地的障碍才留下
            var near = new List<Obstacle>();
            foreach (var o in obstacles)
            {
                float ex = o.half.x + o.radius, ez = o.half.y + o.radius;
                if (o.center.x + ex < hallRect.xMin || o.center.x - ex > hallRect.xMax || o.center.z + ez < hallRect.yMin || o.center.z - ez > hallRect.yMax) continue;
                near.Add(o);
            }
            hallObs = near.ToArray();
            int nzf = hallSeats != null ? hallSeats.childCount : 0;
            hallZafu = new Vector3[nzf];
            for (int i = 0; i < nzf; i++) hallZafu[i] = hallSeats.GetChild(i).position;
            int nm = hallMats != null ? hallMats.childCount : 0;
            hallMatRects = new Rect[nm];
            for (int k = 0; k < nm; k++)
            {
                Vector3 m = hallMats.GetChild(k).position;
                // 左右多让 0.1 米（路线贴着拜垫的角拐过去时，迈出去的那只脚离身子中线一拳多，踩上拜垫的圆边）；前后不多让：中间拜垫和供桌之间那一条（上香站的地方）只有二三十厘米
                hallMatRects[k] = new Rect(m.x - 0.31f - 0.25f, m.z - 0.375f - 0.15f, 0.62f + 0.5f, 0.75f + 0.3f);
            }
            int n = hallNx * hallNz;
            hallBlocked = new bool[n];
            hallMatOf = new int[n];
            bool was = matsBlock;
            matsBlock = false;
            hallGridBuilding = true;
            for (int c = 0; c < n; c++)
            {
                hallBlocked[c] = !HallFree(HallP(c, 0f));
                hallMatOf[c] = HallMatAt(HallP(c, 0f));
            }
            hallGridBuilding = false;
            matsBlock = was;
            hallG = new float[n];
            hallFrom = new int[n];
            hallDone = new bool[n];
        }

        /// 第 c 格的中心（高低用 y）
        Vector3 HallP(int c, float y) => new Vector3(hallX0 + (c / hallNz) * HallCell, y, hallZ0 + (c % hallNz) * HallCell);

        /// 殿里这一点站得下人吗：在四面墙以内、不在障碍里、不踩圆蒲团（方草垫可以踩）
        bool HallFree(Vector3 p)
        {
            if (p.x < hallX0 - 0.01f || p.x > hallRect.xMax - HallWallPad + 0.01f || p.z > hallZMax + 0.01f || p.z < hallZ0 - 0.01f) return false;
            foreach (var o in hallObs) if (ObsDist(o, p) < o.radius) return false;
            foreach (var z in hallZafu) if (FlatDist(z, p) < 0.36f) return false;
            if (matsBlock)
            {
                int k = HallMatAt(p);
                if (k >= 0 && k != matAllowA && k != matAllowB) return false;
            }
            if (hallAvoid.Count > 0 && NearAvoided(p)) return false;
            return true;
        }

        /// 两点之间能不能直着走过去（每 8 厘米看一下）
        bool HallClear(Vector3 p, Vector3 q)
        {
            float len = FlatDist(p, q);
            int n = Mathf.Max(1, Mathf.CeilToInt(len / 0.08f));
            for (int k = 1; k < n; k++) if (!HallFreeFast(Vector3.Lerp(p, q, k / (float)n))) return false;
            return true;
        }

        /// 同 HallFree，查算好的网格（一格 0.1 米）：新大殿四十米宽，一条路要看上千个点，每个点再把几十个障碍量一遍就卡了
        bool HallFreeFast(Vector3 p)
        {
            if (hallBlocked == null || hallGridBuilding) return HallFree(p);
            if (p.x < hallX0 - 0.01f || p.x > hallRect.xMax - HallWallPad + 0.01f || p.z > hallZMax + 0.01f || p.z < hallZ0 - 0.01f) return false;
            int ci = Mathf.Clamp(Mathf.RoundToInt((p.x - hallX0) / HallCell), 0, hallNx - 1);
            int cj = Mathf.Clamp(Mathf.RoundToInt((p.z - hallZ0) / HallCell), 0, hallNz - 1);
            return !CellOff(ci * hallNz + cj);
        }

        /// 一点落到格子上：离它最近、空着、又能直着走过去的那一格（0.15 米以内的不用看能不能直着走）；没有是 -1。
        /// 由近往远一圈圈找：窗口外的格子至少离它 r 格远，窗口里找到的比这近就是最近的
        int HallSnap(Vector3 p, bool needClear = true)
        {
            int ci = Mathf.Clamp(Mathf.RoundToInt((p.x - hallX0) / HallCell), 0, hallNx - 1);
            int cj = Mathf.Clamp(Mathf.RoundToInt((p.z - hallZ0) / HallCell), 0, hallNz - 1);
            int maxR = Mathf.Max(hallNx, hallNz);
            int tested = 0;     // 上一圈已经试过的窗口半径（这一圈只试新进来的那一圈格子）
            for (int r = 3; ; r = Mathf.Min(maxR, r * 2))
            {
                hallNear.Clear();
                for (int i = Mathf.Max(0, ci - r); i <= Mathf.Min(hallNx - 1, ci + r); i++)
                    for (int j = Mathf.Max(0, cj - r); j <= Mathf.Min(hallNz - 1, cj + r); j++)
                    {
                        int c = i * hallNz + j;
                        if (CellOff(c)) continue;
                        hallNear.Add((FlatDist(HallP(c, 0f), p), c));
                    }
                hallNear.Sort((x, y2) => x.d.CompareTo(y2.d));
                float bound = r >= maxR ? float.MaxValue : r * HallCell;
                foreach (var (d, c) in hallNear)
                {
                    if (d > bound) break;
                    // 上一圈试过、没过的不再试
                    int i = c / hallNz, j = c % hallNz;
                    if (tested > 0 && Mathf.Abs(i - ci) <= tested && Mathf.Abs(j - cj) <= tested && d <= tested * HallCell) continue;
                    if (!needClear || d < 0.15f || HallClear(p, HallP(c, p.y))) return c;
                }
                if (r >= maxR) return -1;
                tested = r;
            }
        }

        /// 网格上的 A*（八个方向，斜着走不擦障碍的角）：从 sa 到 sb 找得到路吗；路记在 hallFrom 里
        bool HallAStar(int sa, int sb)
        {
            int n = hallNx * hallNz;
            Array.Fill(hallG, float.MaxValue);
            Array.Clear(hallDone, 0, n);
            hallHeap.Clear();
            int gi = sb / hallNz, gj = sb % hallNz;
            float H(int c)
            {
                float di = c / hallNz - gi, dj = c % hallNz - gj;
                return Mathf.Sqrt(di * di + dj * dj) * HallCell;
            }
            hallG[sa] = 0;
            HeapPush(H(sa), sa);
            while (hallHeap.Count > 0)
            {
                int cur = HeapPop();
                if (cur == sb) return true;
                if (hallDone[cur]) continue;
                hallDone[cur] = true;
                int ci = cur / hallNz, cj = cur % hallNz;
                for (int di = -1; di <= 1; di++)
                    for (int dj = -1; dj <= 1; dj++)
                    {
                        if (di == 0 && dj == 0) continue;
                        int ni = ci + di, nj = cj + dj;
                        if (ni < 0 || nj < 0 || ni >= hallNx || nj >= hallNz) continue;
                        int nc = ni * hallNz + nj;
                        if (hallDone[nc] || CellOff(nc)) continue;
                        // 斜着走不能擦着障碍的角切过去
                        int c1 = (ci + di) * hallNz + cj, c2 = ci * hallNz + cj + dj;
                        if (di != 0 && dj != 0 && (CellOff(c1) || CellOff(c2))) continue;
                        float ng = hallG[cur] + (di != 0 && dj != 0 ? HallCell * 1.4142f : HallCell);
                        if (ng >= hallG[nc]) continue;
                        hallG[nc] = ng;
                        hallFrom[nc] = cur;
                        HeapPush(ng + H(nc), nc);
                    }
            }
            return false;
        }

        void HeapPush(float f, int c)
        {
            hallHeap.Add((f, c));
            int i = hallHeap.Count - 1;
            while (i > 0)
            {
                int up = (i - 1) / 2;
                if (hallHeap[up].f <= f) break;
                hallHeap[i] = hallHeap[up];
                i = up;
            }
            hallHeap[i] = (f, c);
        }

        int HeapPop()
        {
            int top = hallHeap[0].c;
            var last = hallHeap[hallHeap.Count - 1];
            hallHeap.RemoveAt(hallHeap.Count - 1);
            int n = hallHeap.Count;
            if (n == 0) return top;
            int i = 0;
            while (true)
            {
                int l = 2 * i + 1;
                if (l >= n) break;
                int m = l + 1 < n && hallHeap[l + 1].f < hallHeap[l].f ? l + 1 : l;
                if (hallHeap[m].f >= last.f) break;
                hallHeap[i] = hallHeap[m];
                i = m;
            }
            hallHeap[i] = last;
            return top;
        }

        /// 殿里点到的地方站不了人（供桌、佛坛、蒲团上，墙根、佛坛后面）：换成离它最近、站得下的一点
        Vector3 HallStandable(Vector3 p)
        {
            HallGrid();
            if (HallFree(p)) return p;
            int c = HallSnap(p, false);
            if (c < 0) return p;
            Vector3 q = HallP(c, p.y);
            q.y = hallFloor;
            return q;
        }

        /// 各排圆蒲团那条线的 z（从南到北），按院子里的座位算一次
        List<float> rowZ;

        List<float> SeatRows()
        {
            if (rowZ != null) return rowZ;
            rowZ = new List<float>();
            for (int i = 0; i < OutdoorSeats; i++)
            {
                float z = pilgrims.Seat(i).position.z;
                if (!rowZ.Exists(r => Mathf.Abs(r - z) < 0.05f)) rowZ.Add(z);
            }
            rowZ.Sort();
            return rowZ;
        }

        /// 座位区里的一点挪到最近的走道上：在中间过道里的不用挪；在两个圆蒲团之间、草垫上、蒲团后面的，
        /// 顺着南北方向走到这一排前面（或后面）的走道——往离开这一排圆蒲团那条线的方向走，不会踩到圆蒲团
        Vector3 OnLane(Vector3 p)
        {
            if (Mathf.Abs(p.x - aislePoint.x) < aisleHalf) return p;
            var rows = SeatRows();
            if (rows.Count == 0) return p;
            int r = 0;
            for (int i = 1; i < rows.Count; i++) if (Mathf.Abs(rows[i] - p.z) < Mathf.Abs(rows[r] - p.z)) r = i;
            float z = p.z >= rows[r] ? rows[r] + laneOffset.z : r > 0 ? rows[r - 1] + laneOffset.z : rows[0] - 0.42f;
            if (Mathf.Abs(p.z - z) <= 0.15f) return p;
            return new Vector3(p.x, p.y, z);
        }

        bool InObstacle(Vector3 p, float pad = 0f)
        {
            foreach (var o in obstacles)
                if (ObsDist(o, p) < o.radius + pad) return true;
            return false;
        }

        static float Cross2(Vector2 a, Vector2 b) => a.x * b.y - a.y * b.x;
        static Vector2 XZ(Vector3 p) => new Vector2(p.x, p.z);

        /// 水平面上 p→q 这一段碰到 r→s 这条线（端点碰上也算）
        static bool SegTouch(Vector2 p, Vector2 q, Vector2 r, Vector2 s)
        {
            Vector2 d1 = q - p, d2 = s - r;
            float den = Cross2(d1, d2);
            if (Mathf.Abs(den) < 1e-6f) return false;
            float t = Cross2(r - p, d2) / den, u = Cross2(r - p, d1) / den;
            return t >= -1e-4f && t <= 1f + 1e-4f && u >= -1e-4f && u <= 1f + 1e-4f;
        }

        /// 一条路线（从 from 出发，一个个点连起来）有没有从「不穿过的线」（山门两边、台基边、殿墙）的一边走到另一边。
        /// 按路线上的点在线的哪一边算：起点、终点、半路的拐点正好落在线上都不算穿过（站在线上的那一点照样走得到、走得开），
        /// 可是从这一边经过线上的一点走到那一边算——不能一段一段地看（两段各自只是「碰到」线，连起来就穿过去了）
        public bool PathCrossesWalls(Vector3 from, List<Vector3> path)
        {
            if (planWalls == null || planWalls.Length == 0) return false;
            var pts = new List<Vector3>(path.Count + 1) { from };
            pts.AddRange(path);
            foreach (var w in planWalls)
            {
                Vector2 r = new Vector2(w.x, w.y), s = new Vector2(w.z, w.w);
                int Side(Vector3 p)
                {
                    float c = Cross2(s - r, XZ(p) - r);
                    return c > 1e-4f ? 1 : c < -1e-4f ? -1 : 0;
                }
                int last = Side(pts[0]), lastAt = 0;
                for (int i = 1; i < pts.Count; i++)
                {
                    int sd = Side(pts[i]);
                    if (sd == 0) continue;
                    if (last != 0 && sd != last)
                        for (int k = lastAt; k < i; k++)
                            if (SegTouch(XZ(pts[k]), XZ(pts[k + 1]), r, s)) return true;
                    last = sd;
                    lastAt = i;
                }
            }
            return false;
        }

        /// 一条路线（从 from 出发）踩不踩蒲团、穿不穿「不穿过的线」
        bool PathBlocked(Vector3 from, List<Vector3> path)
        {
            Vector3 prev = from;
            foreach (var p in path)
            {
                if (CrossesSeats(prev, p)) return true;
                prev = p;
            }
            return PathCrossesWalls(from, path);
        }

        /// 从 a 走到 b（都在座位区外）：能顺着铺好的路走就顺着走。
        /// 路上的点之间按实际长短算，不在路上的那几段（从 a 走到路上、从路上走到 b、直着走）按 offRoadCost 倍算，挑总数最小的走法（Dijkstra，二十来个点）。
        /// 踩蒲团、穿过「不穿过的线」（山门两边、台基边、殿墙）的那几段不算数。从码头去大殿：码头 → 山门 → 主路 → 香炉外绕半圈 → 中间过道 → 殿前台阶 → 殿门；
        /// 在院子里走几步、从路边走到旁边的草地上：直着走（绕到路上反而远）
        List<Vector3> Road(Vector3 a, Vector3 b)
        {
            var direct = Plan(a, b);
            int n = roadNodes != null ? roadNodes.Length : 0;
            if (n == 0 || roadLinks == null || roadLinks.Length < 2) return direct;
            float Off(Vector3 from, List<Vector3> leg) => PathBlocked(from, leg) ? float.PositiveInfinity : PathLength(from, leg) * offRoadCost;
            float best = Off(a, direct);
            var fromA = new List<Vector3>[n];
            var dist = new float[n];
            var prev = new int[n];
            var done = new bool[n];
            for (int i = 0; i < n; i++)
            {
                fromA[i] = Plan(a, roadNodes[i]);
                dist[i] = Off(a, fromA[i]);
                prev[i] = -1;
            }
            // 路上走：一个个点按「从 a 过来最近」往外推
            for (int round = 0; round < n; round++)
            {
                int u = -1;
                for (int i = 0; i < n; i++) if (!done[i] && (u < 0 || dist[i] < dist[u])) u = i;
                if (u < 0 || float.IsInfinity(dist[u])) break;
                done[u] = true;
                for (int k = 0; k + 1 < roadLinks.Length; k += 2)
                {
                    int v = roadLinks[k] == u ? roadLinks[k + 1] : roadLinks[k + 1] == u ? roadLinks[k] : -1;
                    if (v < 0 || v >= n || done[v]) continue;
                    float d = dist[u] + FlatDist(roadNodes[u], roadNodes[v]);
                    if (d < dist[v]) { dist[v] = d; prev[v] = u; }
                }
            }
            // 从路上哪一点下来走到 b
            int end = -1;
            List<Vector3> toB = null;
            for (int i = 0; i < n; i++)
            {
                if (float.IsInfinity(dist[i])) continue;
                var leg = Plan(roadNodes[i], b);
                float total = dist[i] + Off(roadNodes[i], leg);
                if (total < best - 0.01f) { best = total; end = i; toB = leg; }
            }
            if (end < 0) return direct;
            var chain = new List<int>();
            for (int i = end; i >= 0; i = prev[i]) chain.Add(i);
            chain.Reverse();
            var path = new List<Vector3>(fromA[chain[0]]);
            for (int i = 1; i < chain.Count; i++) path.Add(roadNodes[chain[i]]);
            path.AddRange(toB);
            return path;
        }

        List<Vector3> RouteOutside(Vector3 a, Vector3 b)
        {
            bool ia = InSeats(a), ib = InSeats(b);
            if (ia || ib)
            {
                // 不在走道上的点（两个蒲团之间、草垫上）先挪到走道上，再按走道、过道走
                var head = new List<Vector3>();
                Vector3 la = ia ? OnLane(a) : a, lb = ib ? OnLane(b) : b;
                if (FlatDist(la, a) > 0.05f) head.Add(la);
                var mid = RouteSeats(la, lb, ia, ib);
                head.AddRange(mid);
                if (FlatDist(lb, b) > 0.05f) head.Add(b);
                return head;
            }
            return RouteSeats(a, b, false, false);
        }

        /// 进出座位区的走法（a、b 在座位区里的话已经在走道上了）
        List<Vector3> RouteSeats(Vector3 a, Vector3 b, bool ia, bool ib)
        {
            if (!ia && !ib)
            {
                // 两头都在座位区外：能顺着铺好的路走就顺着走（Road）；路线要是斜着穿过座位区，就改走中间的过道（从一头进、另一头出）
                var direct = Road(a, b);
                if (!PathCrossesSeats(a, direct) || seatEntries.Length < 2) return direct;
                Vector3 ea = NearestEntry(a), eb = NearestEntry(b);
                var via = new List<Vector3>(Road(a, ea));
                if (eb != ea) via.Add(eb);
                via.AddRange(Road(eb, b));
                return via;
            }
            var r = new List<Vector3>();
            if (ia && ib)
            {
                // 同一排的走道上：直接横着走；不同排：到中间过道上，沿过道走到那一排
                if (Mathf.Abs(a.z - b.z) >= 0.3f)
                {
                    r.Add(new Vector3(aislePoint.x, aislePoint.y, a.z));
                    r.Add(new Vector3(aislePoint.x, aislePoint.y, b.z));
                }
                r.Add(b);
                return r;
            }
            // 一头在座位区里：从这一排走道的哪一头进出——中间过道（再从过道的南头、北头出去），或者走道外侧的那一头。挑路短、又不踩蒲团的
            Vector3 inside = ia ? a : b, outside = ia ? b : a;
            Vector3 aisle = new Vector3(aislePoint.x, aislePoint.y, inside.z);
            Vector3 entry = NearestEntry(outside);
            // 外面那一段（走到过道口）顺着铺好的路走
            var toEntry = Road(outside, entry);
            float viaAisle = PathLength(outside, toEntry) + FlatDist(entry, aisle) + FlatDist(aisle, inside);
            Vector3 sideP = new Vector3(Mathf.Sign(inside.x - aislePoint.x) * (Mathf.Max(Mathf.Abs(seatBlock.xMin), Mathf.Abs(seatBlock.xMax)) + 0.25f) + aislePoint.x, inside.y, inside.z);
            var sidePlan = Plan(outside, sideP);
            float viaSide = FlatDist(outside, sideP) + FlatDist(sideP, inside);
            // 走道外侧那一头有东西（太平缸）挡着就不走那头
            bool sideFree = !InObstacle(sideP, 0.1f) && Plan(sideP, inside).Count == 1;
            var leg = new List<Vector3>();
            if (sideFree && viaSide < viaAisle && !PathCrossesSeats(outside, sidePlan))
            {
                leg.AddRange(sidePlan);
                leg.Add(inside);
            }
            else
            {
                leg.AddRange(toEntry);
                leg.Add(aisle);
                leg.Add(inside);
            }
            if (ib) return leg;
            // 从里往外走：同一条路反过来（终点换成 b）
            leg.Reverse();
            leg.RemoveAt(0);
            leg.Add(b);
            return leg;
        }

        Vector3 NearestEntry(Vector3 p)
        {
            Vector3 best = new Vector3(aislePoint.x, aislePoint.y, seatBlock.yMin - 0.3f);
            float bd = float.MaxValue;
            foreach (var e in seatEntries)
                if (FlatDist(e, p) < bd) { bd = FlatDist(e, p); best = e; }
            return best;
        }

        bool PathCrossesSeats(Vector3 from, List<Vector3> path)
        {
            Vector3 prev = from;
            foreach (var p in path)
            {
                if (CrossesSeats(prev, p)) return true;
                prev = p;
            }
            return false;
        }

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
                case "stand": Stand(); break;
                case "act": Act(m.action, m.mat); break;
                case "offer": Offer(m); break;
                case "offerings":
                    foreach (string part in (m.list ?? "").Split(','))
                        if (int.TryParse(part, out int slot)) offerings.Place(string.IsNullOrEmpty(m.kind) ? "ribbon" : m.kind, slot, m.id, m.tex, m.mine);
                    break;
                case "pilgrims": SyncPilgrims(m.list ?? ""); break;
                case "pact": pilgrims.Act(m.id, m.action); break;
                case "look": cam.Look(m.dx, m.dy); break;
                // 换视角：kind 是 top（俯视）、level（平视）、low（仰视）、first（第一人称）；放大：x 是倍数（1 到 8）。
                // 在殿里只能平视、第一人称（俯视看到的是屋顶，仰视会穿过天花板）
                case "view":
                    if (cam is ViewSwitcher vs)
                    {
                        EndLinger();
                        if (!inHall || m.kind == "level" || m.kind == "first") vs.SetMode(m.kind);
                        SendView(vs);
                    }
                    break;
                case "zoom": if (cam is ViewSwitcher vz) vz.SetZoom(m.x); break;
                // 捏合拉远拉近：镜头离人的远近是平常的 x 倍
                case "reach": if (cam is ViewSwitcher vr) vr.SetReach(m.x); break;
                // 钓鱼：cast 抛竿 / reel 提竿 / show 把 kind 这条鱼提出水面 / stop 收竿
                case "fish": Fish(m.action, m.kind); break;
                // 敲钟（站在钟亭边才行）
                case "ring": Ring(); break;
                // 特写多留一会儿（x 秒，0 是现在就收）：挂好布条以后 Flutter 念回应的那几句字幕，镜头一直对着新挂的那一件
                case "linger":
                    if (m.x <= 0f) EndLinger();
                    else if (lingerCloseUp > 0f) lingerCloseUp = Mathf.Max(lingerCloseUp, Time.time + m.x);
                    break;
                case "move": Move(m.x, m.y); break;
                // 「停下」：自动走的路上（从码头进殿要走四十多秒）不走了，就停在这里
                case "halt": if (!acting) StopAutoWalk(); break;
                case "tap": Tap(m.x, m.y); break;
                case "audio":
                    sound.SetMuted(!m.on);
                    sound.master = Mathf.Clamp01(m.volume);
                    break;
                case "bell": sound.Play(bell, 0.8f); break;
                case "pets": BondPets(m.list ?? ""); break;
                case "petact":
                    foreach (var c in Critter.All)
                        if (c.id == m.id)
                        {
                            c.React(m.action, m.seat, m.item);
                            if (!acting && mySeat < 0 && !autoWalk) player.FaceTowards(c.transform.position);
                            sound.Play(m.action == "feed" ? "sfx_wood" : "sfx_sparkle", 0.4f);
                            // 摸它、喂它的那一阵镜头一直对着它
                            petFocus = c.transform;
                            petFocusUntil = Time.time + (m.action == "feed" ? 6.5f : 4f);
                        }
                    break;
                case "feed": Feed(m.kind); break;
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
            sitting = null;
            pendingSeat = -1;
            acting = false;
            autoWalk = false;
            onArrive = null;
            DropHeld();
            // 在殿里重新进场：放开平视，换回进殿前的视角（发给 Flutter，它接着照这个重新对一遍）
            LeaveHallView(true);
            lingerCloseUp = 0;
            if (fishing != null) fishing.Stop(false);
            cam.EndCloseUp();
            // 操作方式只有一种：摇杆走路、拖屏绕着人转（以前的俯视、仰视、第一人称几档不再用）
            if (cam is ViewSwitcher ev) { ev.SetMode("level"); ev.Subject(null, Vector3.zero, 0); }
            petFocus = null;
            birdFocusUntil = 0;
            nearBird = false;
            nearBell = false;
            stickHeld = false;
            Sky(m, true);
            // 直接站好（跪着、坐着时重新进场：不在院子里播起身那段）
            player.SetPose(Folk.Pose.None, true);
            player.SetBow(0);
            player.StopWalking();
            PlaceAt(Find(startSpot));
            // 自己的名字是金色，别人是暖白（Pilgrims.NameColor），一眼分得出
            player.SetName(m.name ?? "", new Color(0.94f, 0.79f, 0.37f));
            at = startSpot;
            mySeat = -1;
            synced = false;
            nearPet = "";
            nearWater = "";
            nextWaterScan = 0;
            nearSeat = -1;
            nearMat = -1;
            nearAltar = false;
            // 没联网（seed > 0）：本机按同样的规则自己安排人来人往；联网时人都由服务器的名单来
            if (m.seed > 0) pilgrims.StartLocalCrowd();
            // 联网时：自己挂了、服务器没认的收掉（进殿后服务器「mine」那一份会挂回来）。没联网时留着
            else offerings.DropUnacknowledged();
            var no = new List<string>();
            for (int i = 0; i < offerings.SlotCount; i++) if (!CanHang(i)) no.Add(i.ToString());
            Send($"{{\"type\":\"entered\",\"scene\":\"{SceneManager.GetActiveScene().name}\",\"seats\":{pilgrims.SeatCount},\"slots\":{offerings.SlotCount},\"hall\":{(hallOpen ? "true" : "false")},\"nohang\":\"{string.Join(",", no)}\"}}");
            StartCoroutine(WalkIn());
        }

        /// 进殿：不自动走路，直接站在院子里（香炉南边、面朝大殿），等你自己走
        IEnumerator WalkIn()
        {
            var s = Find(firstSpot);
            PlaceAt(s);
            at = firstSpot;
            yield return null;
            Send($"{{\"type\":\"arrived\",\"spot\":\"{firstSpot}\"}}");
        }

        /// 摇杆：按镜头的朝向换算成人走的方向。坐着、跪着时一推摇杆就起身。
        /// 方向按「按下那一刻」镜头的朝向算，按住不放时镜头自己转（跟到人身后）也不改，人走的是直线；
        /// 手指把方向拧过一个大角度（35 度以上）时，按此刻的镜头重新算
        void Move(float x, float y)
        {
            stick = Vector2.ClampMagnitude(new Vector2(x, y), 1f);
            if (stick.sqrMagnitude < 0.0004f)
            {
                stickHeld = false;
                return;
            }
            if (!stickHeld || Vector2.Angle(stickFrom, stick) > 35f)
            {
                stickHeld = true;
                stickYaw = cam.Yaw;
                stickFrom = stick;
            }
            // 钓着鱼推摇杆：收竿走人
            if (fishing != null && fishing.Active) fishing.Stop();
            if (acting) return;
            if (mySeat >= 0)
            {
                // 坐着推摇杆：先起身退到这一排前面的走道上，再交给摇杆
                Stand();
                return;
            }
            if (sitting != null)
            {
                // 走到蒲团前正转身要坐：不坐了，交给摇杆（告诉 Flutter 停在哪了）
                CancelSit();
                FreeMove();
                ArrivedHere();
                return;
            }
            // 正在自动走：中途推摇杆，就停下改成自己走（告诉 Flutter 停在哪了，界面不会一直等着）。正要去坐的蒲团也不坐了
            if (autoWalk) StopAutoWalk();
        }

        void StopAutoWalk()
        {
            if (!autoWalk) return;
            autoWalk = false;
            onArrive = null;
            CancelSit();
            player.StopWalking();
            FreeMove();
            ArrivedHere();
        }

        /// 起身：站起来，退到这一排蒲团前面的走道上（不再走回中间过道）
        void Stand()
        {
            if (acting) return;
            if (mySeat < 0)
            {
                // 还没坐下（正走过去、正转身）：不坐了，原地停下。其实没坐着（两边的状态没对上）：回一声，界面别等
                bool wasGoing = sitting != null || pendingSeat >= 0;
                CancelSit();
                if (wasGoing && autoWalk)
                {
                    autoWalk = false;
                    onArrive = null;
                    Halt();
                    FreeMove();
                }
                if (!autoWalk) ArrivedHere();
                return;
            }
            int s = mySeat;
            Vector3 lane = SeatLane(s);
            Halt();
            player.SetPose(Folk.Pose.None);
            mySeat = -1;
            cam.Focus(0);
            Send("{\"type\":\"stood\"}");
            Walk(new List<Vector3> { lane }, lane + SeatFwd(s), "", ArrivedHere);
        }

        /// 此刻站在哪个地点（离哪个最近；都不近、又在院子里就是 court）
        string SpotHere()
        {
            Vector3 me = player.transform.position;
            if (InHall(me)) return "inhall";
            string near = "";
            float best = 1f;
            foreach (var s in spots)
            {
                if (s.name == startSpot || s.name == "court" || s.name == "inhall") continue;
                float d = s.zoneRadius > 0
                    ? Vector2.Distance(new Vector2(s.zone.x, s.zone.z), new Vector2(me.x, me.z)) / s.zoneRadius
                    : Vector2.Distance(new Vector2(s.floor.x, s.floor.z), new Vector2(me.x, me.z)) / nearRadius;
                if (d < best) { best = d; near = s.name; }
            }
            if (near == "" && me.z > (float.IsNaN(courtMinZ) ? hub.z - 0.5f : courtMinZ)) near = "court";
            return near;
        }

        /// 自动走完（或被打断）：告诉 Flutter 现在在哪
        void ArrivedHere()
        {
            string near = SpotHere();
            if (near == "" && at == startSpot) near = startSpot;
            at = near;
            Send($"{{\"type\":\"arrived\",\"spot\":\"{near}\"}}");
        }

        // ── 走路 ──

        /// 座位前面那条走道（沿着一排蒲团前面的草垫走）：座位点加上它
        public Vector3 laneOffset = Vector3.zero;
        Vector3 AisleNode(Vector3 seat) => aislePoint + aisleDir * Vector3.Dot(seat + laneOffset - aislePoint, aisleDir);

        bool Positive(Vector3 seat) => Vector3.Dot(seat - aislePoint, Vector3.Cross(Vector3.up, aisleDir)) >= 0;

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
                        // 长方的按外接圆算（院子里没有长方的；殿里的路由 HallPlan 走，这里只是兜底）
                        float rad = o.radius + o.half.magnitude;
                        if (d >= rad) continue;
                        Vector2 dir = d > 0.02f ? (closest - C) / d : new Vector2(-ab.y, ab.x).normalized;
                        Vector2 w = C + dir * (rad + 0.3f);
                        var mid = new Vector3(w.x, Mathf.Lerp(a.y, b.y, t), w.y);
                        res.AddRange(Plan(a, mid, depth + 1));
                        res.AddRange(Plan(mid, b, depth + 1));
                        return res;
                    }
            }
            res.Add(b);
            return res;
        }

        // ── 自动走卡住了的兜底 ──
        // 终点上站着人（香客、别的玩家）时，人一直往他身上挤（互相让开的推力把人推开），永远走不到那几厘米以内，
        // Folk 就一直不发 Arrived：界面一直等着、「坐下」「跪拜」这些按钮也一直不出来。所以：
        // 离终点已经不到 0.6 米、又 1.5 秒没再走近 3 厘米，就算到了；不管在哪，走得比该走的时间长很多也停下

        /// 自动走的终点（没在自动走时不算）：香客挑站的地方时避开它
        Vector3 walkGoal;
        float walkStart, walkBudget, stallBest, stallT;

        /// 卡住的判断从头算（开始走一条新路线时）
        void ResetStall(Vector3 goal, float pathLen)
        {
            walkGoal = goal;
            walkStart = stallT = Time.time;
            stallBest = float.MaxValue;
            walkBudget = pathLen / Mathf.Max(0.3f, player.walkSpeed * 0.5f) + 8f;
        }

        /// 是不是卡住了：离终点很近却半天走不近，或者走了太久
        bool Stalled()
        {
            float d = FlatDist(player.transform.position, walkGoal);
            // 还在起身、跪起来（过渡动作播着，人不挪）：不算卡住
            if (player.InTransition) { stallT = Time.time; return false; }
            if (d < stallBest - 0.03f) { stallBest = d; stallT = Time.time; }
            return (d < 0.6f && Time.time - stallT > 1.5f) || Time.time - walkStart > walkBudget;
        }

        static float PathLength(Vector3 from, List<Vector3> path)
        {
            float len = 0;
            foreach (var p in path) { len += FlatDist(from, p); from = p; }
            return len;
        }

        /// 自动走时每帧看一眼：卡住了就当走到了（离终点还远——比如一直被挡在路上——就停在原地，告诉 Flutter 停在哪了）
        void WatchStall()
        {
            if (!autoWalk || !Stalled()) return;
            float d = FlatDist(player.transform.position, walkGoal);
            Debug.Log($"[yuanjing] 自动走卡住了：离终点 {d:F2} 米，走了 {Time.time - walkStart:F1} 秒，{(d <= 1f ? "就算到了" : "停在这里")}");
            if (d <= 1f)
            {
                // 照常「到了」：转向要看的方向、发 arrived（在 Arrived 里）
                player.ArriveNow();
                return;
            }
            autoWalk = false;
            onArrive = null;
            CancelSit();
            Halt();
            FreeMove();
            ArrivedHere();
        }

        /// 自己正走去的那一点（自动走、走去拜垫、走到供桌前上香、走去挂布条的路上）；没在走是 null。殿里的香客挑拜垫、蒲团时避开它
        public Vector3? PlayerGoal => (autoWalk || acting) && player != null && player.Moving ? walkGoal : (Vector3?)null;

        /// 「这一点别站人」：玩家点了「去大殿」「去香炉」「去许愿树」站的那几点、玩家正自动走去的终点（0.6 米内）。
        /// 香客挑站的地方时用（Pilgrims.FreeSpot）
        public bool KeepClear(Vector3 c, float r = 0.6f)
        {
            if (autoWalk && FlatDist(c, walkGoal) < r) return true;
            foreach (var s in spots)
                if (s.pick > 0.5f && s.name != "inhall" && FlatDist(c, s.floor) < r) return true;
            return false;
        }

        /// 走去某个地点时站哪：那个地点的站位上有人（香客站着、正要去那里站），就在旁边找一块空地
        /// （离谁都有 0.65 米、不在障碍里、不踩进座位区、地面和站位一样高），挑离自己近的那一块
        Vector3 FreeAround(Vector3 want)
        {
            bool Free(Vector3 c)
            {
                if (pilgrims != null && pilgrims.Crowded(c, 0.65f)) return false;
                foreach (var o in Folk.All)
                    if (o != null && o != player && o.isActiveAndEnabled && FlatDist(o.transform.position, c) < 0.65f) return false;
                return true;
            }
            if (Free(want)) return want;
            bool wantInSeats = InSeats(want);
            Vector3 me = player.transform.position, best = want;
            for (int ring = 1; ring <= 5; ring++)
            {
                float bd = float.MaxValue;
                int n = 8 * ring;
                for (int i = 0; i < n; i++)
                {
                    float a = i * Mathf.PI * 2f / n;
                    Vector3 c = want + new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a)) * (0.3f * ring);
                    if (!Free(c) || InObstacle(c, 0.3f) || (!wantInSeats && InSeats(c))) continue;
                    // 地面一样高（不站到台阶、石台边外面去）
                    if (Physics.Raycast(c + Vector3.up * 1.2f, Vector3.down, out var hit, 2.4f, ~(1 << 2), QueryTriggerInteraction.Ignore) && Mathf.Abs(hit.point.y - want.y) > 0.08f) continue;
                    float d = FlatDist(c, me);
                    if (d < bd) { bd = d; best = c; }
                }
                if (bd < float.MaxValue) return best;
            }
            return want;
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
            ResetStall(clean[clean.Count - 1], PathLength(player.transform.position, clean));
            onArrive = () =>
            {
                player.FaceTowards(look);
                Vector3 d = look - player.transform.position;
                // 殿里：镜头放低（画面自己往上抬着看佛像）
                cam.Settle(Quaternion.LookRotation(new Vector3(d.x, 0, d.z)).eulerAngles.y, InHall(player.transform.position) ? hallCamPitch : 14f);
                arrived?.Invoke();
            };
            autoWalk = true;
            EndLinger();
            // 按规划好的路线走时不用碰撞胶囊（路线已经绕开了东西；坐上长椅也不会被挡）
            if (player.controller != null) player.controller.enabled = false;
            player.Walk(clean);
            Send($"{{\"type\":\"moving\",\"to\":\"{to}\"}}");
        }

        /// 从现在坐的位置起身：先退到这一排前面的走道上（殿里的蒲团也一样），返回那一点；接下来的路由 Route 规划
        /// （走道的哪一头近、过道的南头还是北头、要不要进出殿门）
        Vector3 LeaveSeat(List<Vector3> path)
        {
            Vector3 lane = SeatLane(mySeat);
            path.Add(lane);
            return lane;
        }

        bool Busy => acting;

        /// 挂好布条以后特写还留到什么时候（0 是没有在留）
        float lingerCloseUp;

        void EndLinger()
        {
            if (lingerCloseUp <= 0) return;
            lingerCloseUp = 0;
            cam.EndCloseUp();
        }

        public void Go(string name)
        {
            var s = Find(name);
            if (s == null || Busy) return;
            if (name == "inhall" && !hallOpen)
            {
                // 大殿还进不去：回一声，界面别等
                ArrivedHere();
                return;
            }
            CancelSit();
            Halt();
            var path = new List<Vector3>();
            Vector3 from = player.transform.position;
            if (mySeat >= 0) from = LeaveSeat(path);
            // 站位上有人就站在他旁边的空地上（不往人身上挤）
            path.AddRange(Route(from, name == "inhall" ? s.floor : FreeAround(s.floor)));
            if (mySeat >= 0) player.SetPose(Folk.Pose.None);
            mySeat = -1;
            cam.Focus(0);
            Walk(path, s.look, name, () =>
            {
                at = name;
                Send($"{{\"type\":\"arrived\",\"spot\":\"{name}\"}}");
            });
        }

        // ── 座位 ──
        // 院子石台上的蒲团归 pilgrims 管（序号 0..SeatCount-1，服务器只知道这些）；
        // 殿里静坐的蒲团在 hallSeats 下，序号接在后面。两种用同一套「离得最近的空位」「走过去」「起身」。

        int OutdoorSeats => pilgrims != null ? pilgrims.SeatCount : 0;
        public int SeatTotal => OutdoorSeats + (hallSeats != null ? hallSeats.childCount : 0);
        bool HallSeat(int i) => i >= OutdoorSeats;
        Transform SeatT(int i) => HallSeat(i) ? hallSeats.GetChild(i - OutdoorSeats) : pilgrims.Seat(i);
        /// 圆蒲团正下方的地面（坐下的动作以这里为原点）
        Vector3 SeatGround(int i) => HallSeat(i) ? SeatT(i).position : SeatFloor(i);

        /// 坐下以后面朝哪（水平方向）
        Vector3 SeatFwd(int i)
        {
            if (HallSeat(i))
            {
                Vector3 f = SeatT(i).forward;
                f.y = 0;
                return f.sqrMagnitude > 1e-4f ? f.normalized : Vector3.forward;
            }
            Vector3 s = pilgrims.Seat(i).position;
            Vector3 d = new Vector3(Mathf.Lerp(seatLook.x, s.x, seatStraight), seatLook.y, seatLook.z) - s;
            d.y = 0;
            return d.sqrMagnitude > 1e-4f ? d.normalized : Vector3.forward;
        }

        /// 坐下前站的那一点：圆蒲团前面的方草垫上（长椅就是座位点本身）
        Vector3 SeatStand(int i) => benchSeats && !HallSeat(i) ? SeatGround(i) + SeatFwd(i) * benchStep : SeatGround(i) + SeatFwd(i) * Folk.SeatStep * player.transform.lossyScale.y / 0.806f;
        /// 这一排蒲团前面的走道上、正对着这个蒲团的一点（起身退到这里）；石凳就是凳前站的那一点
        Vector3 SeatLane(int i) => HallSeat(i) ? SeatGround(i) + SeatFwd(i) * hallLane : BenchSeat(i) ? SeatStand(i) : SeatGround(i) + laneOffset;
        /// 这个座位是石凳上的（坐下前站在凳前）
        bool BenchSeat(int i) => benchSeats && benchStep > 0f && !HallSeat(i);
        /// 这个蒲团能不能坐：有人坐在上面、或者有人正走过去坐而且已经到跟前了，才算有人。
        /// 只是被香客记着（他这会儿在树下、香炉前、远处路上）的不算——看着是空的就能坐，坐了以后让他换一个（Pilgrims.Release）。
        /// 殿里的蒲团：进殿的香客坐在上面、或者已经走到跟前要坐了，也不能坐（Pilgrims.HallSeatTaken；他还在路上远处的话你先坐，他让开）
        bool SeatFree(int i) => i != mySeat && (HallSeat(i) ? !pilgrims.HallSeatTaken(i - OutdoorSeats) : !pilgrims.Taken(i));

        static float FlatDist(Vector3 a, Vector3 b) => Vector2.Distance(new Vector2(a.x, a.z), new Vector2(b.x, b.z));

        /// 一点离障碍物有多远（水平）：圆的是到中心，长方的是到长方的边（在里面是 0）
        static float ObsDist(Obstacle o, Vector3 p)
        {
            float dx = Mathf.Max(Mathf.Abs(p.x - o.center.x) - o.half.x, 0f), dz = Mathf.Max(Mathf.Abs(p.z - o.center.z) - o.half.y, 0f);
            return Mathf.Sqrt(dx * dx + dz * dz);
        }

        /// 离 p 最近（按到「坐下前站的那一点」的水平距离）的空蒲团，超过 radius 的不算；没有是 -1
        public int NearestSeat(Vector3 p, float radius)
        {
            int best = -1;
            float bd = radius;
            for (int i = 0; i < SeatTotal; i++)
            {
                float d = FlatDist(SeatStand(i), p);
                if (d >= bd || !SeatFree(i)) continue;
                bd = d;
                best = i;
            }
            return best;
        }

        /// Flutter 的「坐下」：坐到身边最近的空蒲团。给的 seat 不行（被人坐了、太远）就重新挑；身边没有就回 sitFailed
        public void Sit(int seat)
        {
            if (Busy || SeatTotal == 0)
            {
                Send($"{{\"type\":\"sitFailed\",\"reason\":\"{(Busy ? "busy" : "none")}\"}}");
                return;
            }
            if (seat >= 0 && seat == mySeat) return;
            if (seat >= 0 && seat == pendingSeat && (autoWalk || sitting != null)) return;
            CancelSit();
            Vector3 me = player.transform.position;
            // 人可能还在挪：比显示按钮的范围多给半米
            bool ok = seat >= 0 && seat < SeatTotal && SeatFree(seat) && FlatDist(SeatStand(seat), me) <= sitRadius + 0.5f;
            if (!ok) seat = mySeat >= 0 ? -1 : NearestSeat(me, sitRadius);
            if (seat < 0)
            {
                Send("{\"type\":\"sitFailed\",\"reason\":\"none\"}");
                return;
            }
            SitAt(seat, mySeat < 0);
        }

        /// 走近路到一个蒲团前：在它前面就直接过去；在别的蒲团前面先到这一排的走道上；在它后面、旁边就从旁边的空当绕过来
        List<Vector3> Approach(int seat, Vector3 me)
        {
            Vector3 s = SeatGround(seat), f = SeatFwd(seat), side = Vector3.Cross(Vector3.up, f);
            if (BenchSeat(seat))
            {
                // 石凳：人在凳子后面、旁边就绕到凳前（凳子在要绕开的东西里），在凳前直接走过去
                var bp = new List<Vector3>();
                if (Vector3.Dot(me - s, f) < benchStep - 0.1f) bp.AddRange(Route(me, SeatStand(seat) + f * 0.25f));
                bp.Add(SeatStand(seat));
                return bp;
            }
            float laneD = Vector3.Dot(SeatLane(seat) - s, f);
            float gap = HallSeat(seat) ? hallSeatGap : seatGap;
            Vector3 d = me - s;
            float along = Vector3.Dot(d, f), across = Vector3.Dot(d, side);
            Vector3 At(float a, float c) => s + f * a + side * c;
            var path = new List<Vector3>();
            if (along < 0.15f)
            {
                float g = across >= 0 ? gap : -gap;
                path.Add(At(along, g));
                path.Add(At(laneD, g));
            }
            else if (Mathf.Abs(across) > 0.45f || along > laneD + 0.15f)
                path.Add(At(laneD, across));
            path.Add(SeatStand(seat));
            return path;
        }

        /// 走到某个蒲团坐下。near：就在旁边（走近路）；否则（点了远处的蒲团）按座位区的过道走过去。
        /// 走过去的路上这个蒲团就算自己的了（pendingSeat）：香客不会挑它，记着它的内置香客换一个
        void SitAt(int seat, bool near)
        {
            CancelSit();
            Halt();
            Vector3 stand = SeatStand(seat), lane = SeatLane(seat);
            var path = new List<Vector3>();
            if (mySeat >= 0 && !HallSeat(mySeat) && !HallSeat(seat) && !BenchSeat(seat))
            {
                // 换位置：先回到自己这一排的走道；不在同一排就到中间过道上，沿过道走到那一排（过道里没有蒲团）
                Vector3 cur = SeatFloor(mySeat), target = SeatFloor(seat);
                path.Add(cur + laneOffset);
                if (Mathf.Abs(cur.z - target.z) > 0.3f)
                {
                    path.Add(AisleNode(cur));
                    path.Add(AisleNode(target));
                }
                path.Add(lane);
                path.Add(stand);
            }
            else if (mySeat >= 0)
            {
                Vector3 from = LeaveSeat(path);
                path.AddRange(Route(from, lane));
                path.Add(stand);
            }
            else if (near) path.AddRange(Approach(seat, player.transform.position));
            else
            {
                path.AddRange(Route(player.transform.position, lane));
                path.Add(stand);
            }
            player.SetPose(Folk.Pose.None);
            mySeat = -1;
            pendingSeat = seat;
            if (!HallSeat(seat)) pilgrims.Release(seat);
            cam.Focus(0);
            int chosen = seat;
            Vector3 fwd = SeatFwd(seat), ground = SeatGround(seat);
            Vector3 look = HallSeat(seat) ? ground + fwd * 3f + Vector3.up : new Vector3(Mathf.Lerp(seatLook.x, ground.x, seatStraight), seatLook.y, seatLook.z);
            float yaw = Quaternion.LookRotation(fwd).eulerAngles.y;
            Walk(path, look, "seat", () => sitting = StartCoroutine(SitDown(chosen, ground, yaw)));
        }

        /// 走到了蒲团前：转身，再看一眼还空不空（路上可能有人先坐了），空着就坐下。坐下那一刻才算 mySeat
        IEnumerator SitDown(int chosen, Vector3 seatPos, float yaw)
        {
            // 先等一帧：StartCoroutine 返回、记进 sitting 以后再往下走（不然这一段一口气跑完，sitting 留着一个跑完了的）
            yield return null;
            Halt();
            player.FaceYaw(yaw);
            // 转到差 3 度以内再坐（以前只等 0.8 秒、差 6 度：掉头坐下时常常还差三四十度，坐下那一帧一下拧过去）
            for (float t = 0; t < 2.5f && Mathf.Abs(Mathf.DeltaAngle(player.transform.eulerAngles.y, yaw)) > 3f; t += Time.deltaTime) yield return null;
            sitting = null;
            pendingSeat = -1;
            if (!SeatFree(chosen))
            {
                // 被人先坐了：身边还有空的就坐那个，没有就告诉 Flutter
                int other = NearestSeat(player.transform.position, sitRadius);
                if (other >= 0)
                {
                    SitAt(other, true);
                    yield break;
                }
                Send("{\"type\":\"sitFailed\",\"reason\":\"taken\"}");
                ArrivedHere();
                yield break;
            }
            mySeat = chosen;
            at = "seat";
            if (BenchSeat(chosen)) player.SitBench(pilgrims.Seat(chosen).position, yaw);
            else if (benchSeats && !HallSeat(chosen)) player.SetPose(Folk.Pose.Bench);
            else player.SitOn(seatPos, yaw);
            cam.Focus(0.6f);
            // 殿里的蒲团：平视镜头挑一个退得开、不被金柱挡、最好看得见佛像的方向（靠墙的那几个从侧面看；哪儿都退不开就从头顶上看）
            if (HallSeat(chosen)) { var (vy, vp) = HallSeatView(chosen); cam.Settle(vy, vp); }
            // 院子里的蒲团：平视镜头抬高一点（排距只有 1.15 米，后面一排坐着的人的头本来正好挡在画面下半、盖住自己）
            else cam.Settle(yaw, seatedCamPitch);
            sound.Play("sfx_cloth", 0.5f);
            Send($"{{\"type\":\"seated\",\"seat\":{chosen}}}");
        }

        /// 坐在殿里的蒲团上，平视镜头从哪个方向看（水平朝向、高低）。
        /// 以前只从人正后方往佛像那边转 0–36 度：靠墙那一列（外侧一列、南头一对）身后就是侧墙、窗台，镜头被挡得只剩 0.7 米，
        /// 画面下面三分之一是自己后脑勺的网点。现在一圈 24 个方向都试：从转轴往后按镜头的球（半径 0.18）扫过去，
        /// 离人不到 1.6 米的不要；剩下的按「离得开多远、金柱离画面中线多远、佛像在不在画面里、是不是从人身后或侧面看」打分。
        /// 哪个方向都退不到 1.6 米（窗台前那一对），镜头抬高到 30 度，从头顶上看下来，不贴着后脑勺
        public (float yaw, float pitch) HallSeatView(int seat)
        {
            Vector3 g = SeatGround(seat), f = SeatFwd(seat);
            float yaw0 = Quaternion.LookRotation(f).eulerAngles.y;
            Vector3 pivot = g + Vector3.up * 0.95f;
            int blockers = ~((1 << 2) | (1 << 9));
            float want = cam is ViewSwitcher vsd ? vsd.interiorDistance : 2.6f;
            float best = yaw0, bestScore = float.MinValue, bestClear = 0f;
            for (int k = 0; k < 24; k++)
            {
                float y = yaw0 + 15f * k;
                Vector3 dir = Quaternion.Euler(hallCamPitch, y, 0) * Vector3.forward;
                Vector3 flat = new Vector3(dir.x, 0, dir.z).normalized;
                float d = want;
                if (Physics.SphereCast(pivot, 0.18f, -dir, out var hit, want, blockers, QueryTriggerInteraction.Ignore)) d = Mathf.Max(0.35f, hit.distance - 0.05f);
                Vector3 eye = pivot - dir * d;
                // 金柱离画面中线多远（度；超过半个画面宽就不算了）
                float clear = 12f;
                foreach (var o in obstacles)
                {
                    if (o.half != Vector2.zero || !InHallXZ(o.center)) continue;
                    Vector3 to = o.center - eye;
                    to.y = 0;
                    if (Vector3.Dot(to, flat) <= 0f) continue;
                    clear = Mathf.Min(clear, Vector3.Angle(flat, to) - Mathf.Atan2(0.3f, to.magnitude) * Mathf.Rad2Deg);
                }
                // 佛像（头顶）在画面里（水平 25 度以内）加分
                float statue = 0f;
                if (hallLookAts != null)
                    foreach (var p in hallLookAts)
                    {
                        Vector3 v = p - eye;
                        v.y = 0;
                        if (v.sqrMagnitude > 0.25f && Vector3.Angle(flat, v) < 25f) { statue = 6f; break; }
                    }
                // 从身后看最好，侧面也行，正对着脸差一点（cos：身后 +3，正面 −3）
                float facing = 3f * Vector3.Dot(flat, f);
                float score = (d < 1.6f ? -100f + d * 10f : 0f) + 4f * Mathf.Min(d, want) + Mathf.Max(clear, -10f) + statue + facing;
                if (score > bestScore) { bestScore = score; best = y; bestClear = d; }
            }
            return (best, bestClear >= 1.6f ? hallCamPitch : 30f);
        }

        // ── 动作 ──

        void Act(string action, int mat = -1)
        {
            if (Busy || string.IsNullOrEmpty(action))
            {
                // 这会儿做不了也回一声，免得界面一直等
                Send($"{{\"type\":\"actionDone\",\"action\":\"{action}\",\"skipped\":true}}");
                return;
            }
            // 正走去坐、正转身要坐：不坐了，就地做
            if (mySeat < 0) CancelSit();
            // 这块拜垫刚被进殿的香客占了（跪上去了、已经走到跟前）：换身边另一块空的，没有就原地做
            if (mat >= 0 && pilgrims != null && pilgrims.HallMatTaken(mat)) mat = NearestMat(player.transform.position);
            if (mat >= 0 && mySeat < 0 && hallMats != null && mat < hallMats.childCount && InHall(player.transform.position) && action != "meditate")
                StartCoroutine(ActOnMat(action, mat));
            else StartCoroutine(DoAct(action));
        }

        /// 离 p 最近（matRadius 以内）的拜垫；不在殿里、没有是 -1
        public int NearestMat(Vector3 p)
        {
            if (hallMats == null || !InHall(p)) return -1;
            int best = -1;
            float bd = matRadius;
            for (int i = 0; i < hallMats.childCount; i++)
            {
                // 进殿的香客跪在（站在）上面、或者已经走到跟前的拜垫不报（Pilgrims.HallMatTaken）
                if (pilgrims != null && pilgrims.HallMatTaken(i)) continue;
                float d = FlatDist(hallMats.GetChild(i).position, p);
                if (d < bd) { bd = d; best = i; }
            }
            return best;
        }

        /// 是不是站在中间供桌前（能上香）
        public bool NearAltar(Vector3 p) => InHall(p) && FlatDist(p, altarStand) <= altarRadius;

        /// 在拜垫上拜：先走上那块拜垫（垫子有一块薄碰撞，踩上去人就站在垫子面上）、面朝佛像，再做
        IEnumerator ActOnMat(string action, int mat)
        {
            acting = true;
            autoWalk = false;
            onArrive = null;
            Halt();
            EndLinger();
            cam.Focus(0.6f);
            Vector3 to = hallMats.GetChild(mat).position;
            yield return WalkScripted(Route(player.transform.position, to), 12f);
            float yaw = Quaternion.LookRotation(hallFacing).eulerAngles.y;
            player.FaceYaw(yaw);
            // 等人转过来（原地小碎步，≤150 度/秒）再跪：Folk 的跪也会先等朝向（差 8 度以内才播 Kneel_Down），这里多等一会儿，后面拜的节奏不会被吃掉
            for (float t = 0; t < 2.5f && Mathf.Abs(Mathf.DeltaAngle(player.transform.eulerAngles.y, yaw)) > 5f; t += Time.deltaTime) yield return null;
            // 镜头：转到人身后偏 10 度（从外侧往殿中间看：西边的拜垫镜头在西南，东边的在东南；中间那块在西南），
            // 退远到 3 米、和跪着的人头一样高，画面抬着把这一尊佛像整个放进来——跪着、叩首的人整个在画面下半（在木牌上面），佛像在上面
            if (cam is ViewSwitcher vs) vs.Wide(true);
            cam.Settle(yaw + (to.x <= 0.05f ? 10f : -10f), hallKneelPitch);
            yield return ActBody(action);
            if (cam is ViewSwitcher vs2) vs2.Wide(false);
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
            Halt();
            autoWalk = false;
            onArrive = null;
            // 殿里没站在拜垫上（拜垫都被人占了、站在过道上）：也先转过来面朝佛像再拜，不对着墙、对着旁边的人拜
            if (mySeat < 0 && action != "meditate" && InHall(player.transform.position))
            {
                float yaw = Quaternion.LookRotation(hallFacing).eulerAngles.y;
                player.FaceYaw(yaw);
                for (float t = 0; t < 2.5f && Mathf.Abs(Mathf.DeltaAngle(player.transform.eulerAngles.y, yaw)) > 5f; t += Time.deltaTime) yield return null;
            }
            yield return ActBody(action);
        }

        /// 动作本身（站着、坐着、在拜垫上都一样）；做完 acting 放开、发 actionDone
        IEnumerator ActBody(string action)
        {
            acting = true;
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
                case "kneel" when seated:
                    // 盘坐着跪不下去（膝盖、小腿会插进圆蒲团里）：就在蒲团上深深地拜三拜（界面上坐着时本来也不给跪拜）
                    sound.Play("sfx_cloth", 0.4f);
                    yield return new WaitForSeconds(0.3f);
                    for (int i = 0; i < 3; i++) yield return BowOnce(1.5f, 1.1f, 1.4f);
                    break;
                case "kneel":
                    // 跪下，三拜，起来
                    player.SetPose(Folk.Pose.Kneel);
                    sound.Play("sfx_cloth", 0.5f);
                    // 跪下去这段动作 2.5 秒，跪稳了再拜
                    yield return new WaitForSeconds(2.7f);
                    player.SetPose(Folk.Pose.KneelBow);
                    for (int i = 0; i < 3; i++) yield return BowOnce(1.4f, 1.0f, 1.3f);
                    player.SetPose(Folk.Pose.Kneel);
                    yield return new WaitForSeconds(0.6f);
                    // 起身：站起来那段 2.6 秒，播完再算这个动作做完
                    player.SetPose(Folk.Pose.None);
                    yield return new WaitForSeconds(2.6f);
                    break;
                case "meditate":
                    // 静坐的引导和计时在 Flutter 那边，这里只敲一下磬；没坐着就原地合掌
                    sound.Play("sfx_bowl", 0.7f);
                    if (!seated) player.SetPose(Folk.Pose.Gassho);
                    break;
            }
            player.SetBow(0);
            // 挂好布条、上好香以后的特写还没到时候（Flutter 还在念回应）：先留着，到时候（或者人走开）再收
            if (Time.time >= lingerCloseUp) EndLinger();
            if (action != "meditate") player.SetPose(seated ? before : Folk.Pose.None);
            if (action != "meditate") cam.Focus(seated ? 0.6f : 0f);
            acting = false;
            Send($"{{\"type\":\"actionDone\",\"action\":\"{action}\"}}");
        }

        void Offer(Msg m)
        {
            string kind = m.kind ?? "";
            if (Busy)
            {
                Send($"{{\"type\":\"offerFailed\",\"kind\":\"{kind}\",\"reason\":\"busy\"}}");
                return;
            }
            if (mySeat < 0) CancelSit();
            switch (kind)
            {
                case "ribbon":
                case "plaque":
                    StartCoroutine(HangSequence(kind, m.tex));
                    break;
                case "incense":
                    // 在殿里：走到中间供桌前，亲手上香；在院子里：插到香炉里
                    if (InHall(player.transform.position)) { StartCoroutine(HallIncense()); break; }
                    Halt();
                    cam.Focus(0.75f);
                    offerings.Incense(true);
                    break;
                case "coin":
                    Halt();
                    cam.Focus(0.75f);
                    offerings.Coin(true);
                    break;
                case "candle":
                    Halt();
                    cam.Focus(0.75f);
                    offerings.Candle(offerings.FreeSlot(), true);
                    break;
            }
        }

        // ── 亲手挂布条、木牌 ──

        /// 右手（手腕骨 player.Hand(true)、中指根）：布条、香都拿在右手心里
        Transform HandBone(out Transform finger)
        {
            finger = player.animator != null ? player.animator.GetBoneTransform(HumanBodyBones.RightMiddleProximal) : null;
            var hand = player.Hand(true);
            return hand != null ? hand : player.transform;
        }

        /// 抬手去系：Hang_In 右脚垫半步、两手伸到绳上（人前方约 0.40 米、离地约 1.05 米）→ Hang_Loop 系结，布条一直在右手里
        void BeginHangMotion() => player.SetPose(Folk.Pose.Hang);

        /// 系好、松手：Hang_Out（松手、右脚收回、手放下，约 1.4 秒，播完 player.OneShotDone）
        void ReleaseHangMotion() => player.ReleaseHang();

        /// 布条拿在手里还没挂上就被打断（重新进殿）：扔掉，把占着的格子放回去
        void DropHeld()
        {
            if (held != null) offerings.Discard(held);
            held = null;
            if (carry != null) offerings.Discard(carry);
            carry = null;
            if (heldSlot >= 0) offerings.Unreserve(heldSlot);
            heldSlot = -1;
        }

        /// 按路线走，不发 moving/arrived（挂布条这一整套里用；摇杆、点画面这时都不理）
        IEnumerator WalkScripted(List<Vector3> path, float timeout)
        {
            var clean = new List<Vector3>();
            Vector3 last = player.transform.position;
            foreach (var p in path)
            {
                if (Vector3.Distance(p, last) < 0.05f) continue;
                clean.Add(p);
                last = p;
            }
            if (clean.Count == 0)
            {
                Halt();
                yield break;
            }
            if (player.controller != null) player.controller.enabled = false;
            player.Walk(clean);
            // 终点上有人挡着、挤不过去：离终点很近又半天走不近就不走了（同 WatchStall）
            ResetStall(clean[clean.Count - 1], PathLength(player.transform.position, clean));
            walkBudget = Mathf.Min(walkBudget, timeout);
            for (float t = 0; t < timeout && player.Moving && !Stalled(); t += Time.deltaTime) yield return null;
            Halt();
        }

        /// 挂红布条、木牌：挑离自己最近的空格 → 从身上拿出来捏在右手里（布条卷成一卷）→ 走到绳外 hangStand 米、面朝那一格 → 镜头凑近 →
        /// 抬手伸到绳上（Hang_In，布条从卷里放开垂下来）→ 两手系结（Hang_Loop）→ 松手、收脚（Hang_Out，人不挪）→ 合掌 → 告诉 Flutter「offered」。
        /// 整个过程 acting：摇杆、点画面、别的指令都不理，不会挂到一半跑开
        IEnumerator HangSequence(string kind, string tex)
        {
            acting = true;
            autoWalk = false;
            onArrive = null;
            Halt();
            EndLinger();
            if (mySeat >= 0)
            {
                // 坐着（按理说不会：只有在树下才有这两个按钮）：先站起来
                player.SetPose(Folk.Pose.None);
                mySeat = -1;
                Send("{\"type\":\"stood\"}");
                yield return new WaitForSeconds(2.6f);
            }
            int slot = HangSlot(player.transform.position, out bool evict);
            // 挂得了的格子都满了：取下离自己最近的一件别人的，挂自己的（镜头还远，看不出来）
            if (slot >= 0 && evict) offerings.Evict(slot);
            if (slot < 0 || !offerings.Reserve(slot))
            {
                acting = false;
                Send($"{{\"type\":\"offerFailed\",\"kind\":\"{kind}\",\"reason\":\"full\"}}");
                yield break;
            }
            heldSlot = slot;
            Vector3 sp = offerings.SlotPoint(slot), outward = offerings.Outward(slot);
            Vector3 stand = HangStand(slot);
            cam.Focus(0.6f);
            // 从身上拿出来，捏在右手里走过去：布条卷成一小卷（整条垂下来会拖到地上），木牌拎着绳结、板面顺着走的方向
            var hand = HandBone(out var finger);
            carry = offerings.MakeCarry(kind, tex, hand, finger, player.transform);
            sound.Play("sfx_cloth", 0.3f);
            // 走过去：绕开树和绳圈（Plan 会从外面绕），最后一段直直走到绳子外面
            yield return WalkScripted(Route(player.transform.position, stand), 30f);
            player.FaceTowards(sp);
            float yawWant = Quaternion.LookRotation(-outward).eulerAngles.y;
            for (float t = 0; t < 0.9f && Mathf.Abs(Mathf.DeltaAngle(player.transform.eulerAngles.y, yawWant)) > 5f; t += Time.deltaTime) yield return null;
            // 镜头凑近：从人右肩后上方看着那一格（俯视、平视都一样；手机竖屏，人在下面、布条在当中）。
            // 离人一米多，人不会因为贴着镜头淡出；那边有树干、木桩、绘马架挡着就换个位置（CloseUpEye）
            Vector3 focus = HangFocus(slot, kind);
            Vector3 meNow = player.transform.position;
            Vector3 hangEye = HangEye(slot, kind, meNow);
            // 竖着：人从脚到头顶、布条整条都在木牌和上面那几块牌子中间；横着：对准布条和人之间偏布条那一点（布条在当中，人在左边一点，不出画）
            if (cam is ViewSwitcher hv)
            {
                Vector3 aim = Vector3.Lerp(focus, new Vector3(meNow.x, focus.y, meNow.z), 0.3f);
                hv.CloseUp(aim, hangEye, meNow, meNow + Vector3.up * HangBody, HangFov);
            }
            else cam.CloseUp(focus, hangEye);
            // 抬手（Hang_In）：要挂的那一件先做好、藏着，手里还是走路时捏着的那个。
            // 布条：等手抬到整条布条垂下来下摆也离开地面（Hang_In 开头一秒内），卷收掉、布条从手里放开垂下来；
            // 木牌：抬手时转过来正面朝外（0.3 秒），转好了换成要挂的那一块（一模一样，看不出换过）
            held = offerings.MakeHeld(kind, tex, hand, finger, outward);
            var shown = held.GetComponentsInChildren<Renderer>();
            foreach (var r in shown) r.enabled = false;
            BeginHangMotion();
            if (kind == "plaque") offerings.TurnCarry(carry, outward, 0.3f);
            float ground = player.transform.position.y;
            for (float t = 0; t < 1f && shown.Length > 0; t += Time.deltaTime)
            {
                yield return null;
                var b = shown[0].bounds;
                foreach (var r in shown) b.Encapsulate(r.bounds);
                if (b.min.y > ground + 0.03f && (kind != "plaque" || t > 0.4f)) break;
            }
            foreach (var r in shown) if (r != null) r.enabled = true;
            if (carry != null) offerings.Discard(carry);
            carry = null;
            if (kind != "plaque") StartCoroutine(offerings.Unfurl(held, 0.35f));
            sound.Play("sfx_cloth", 0.4f);
            // 两手伸到绳上：等 Hang_In 播完、Hang_Loop 接上（ActionReady；人还要转一点的话 Folk 先转过来，会更久），布条一直在右手里
            for (float t = 0; t < Folk.HangReachTime + 1.5f && !player.ActionReady; t += Time.deltaTime) yield return null;
            // 系一个结（Hang_Loop 一圈 1.6 秒）：布条从右手里挪到绳上那一格（绳结套上绳子），跟着两手拧几下系紧；松手时它已经在格子上，不会跳
            yield return offerings.Tie(held, slot, 1.6f);
            ReleaseHangMotion();
            offerings.Fix(held, kind, slot, true);
            held = null;
            heldSlot = -1;
            // 系上了：马上告诉 Flutter 记到服务器（后面收手、合掌这几秒里离开，也不会只挂在本机）
            Send($"{{\"type\":\"hung\",\"kind\":\"{kind}\",\"slot\":{slot}}}");
            // 松手、收脚、手放下（Hang_Out 里右脚自己收回来，人不用再往后挪），看着它合掌
            for (float t = 0; t < 2f && !player.OneShotDone; t += Time.deltaTime) yield return null;
            player.FaceTowards(sp);
            player.SetPose(Folk.Pose.Gassho);
            yield return new WaitForSeconds(1.4f);
            // 特写先留着：Flutter 接着会让人合掌、念回应（平视时镜头一回到身后，人就把布条挡住了）。
            // 合掌做完、或者人走开了、或者十几秒没动静，再退回平常的镜头
            lingerCloseUp = Time.time + 16f;
            cam.Focus(0.6f);
            acting = false;
            at = SpotHere();
            Send($"{{\"type\":\"offered\",\"kind\":\"{kind}\",\"slot\":{slot}}}");
        }

        /// 挂这一格时人站的那一点（绳外 hangStand 米、脚下的地面）
        public Vector3 HangStand(int slot)
        {
            Vector3 st = offerings.SlotPoint(slot) + offerings.Outward(slot) * hangStand;
            st.y = player.transform.position.y;
            if (Physics.Raycast(st + Vector3.up * 2f, Vector3.down, out var hit, 4f, ~(1 << 2), QueryTriggerInteraction.Ignore)) st.y = hit.point.y;
            return st;
        }

        /// 这一格自己挂得了：挂的那一点上站得了人（绘马架、石灯笼紧挨着绳子的那几格站不了），
        /// 特写镜头也找得到一个看得清布条的位置（不埋在东西里、看布条中间那条视线没被挡）。挂不了的自己挂时不挑；别人的照样挂
        public bool HangSpotFree(int slot)
        {
            Vector3 st = HangStand(slot);
            if (Physics.CheckCapsule(st + Vector3.up * 0.34f, st + Vector3.up * 1.0f, 0.2f, ~(1 << 2), QueryTriggerInteraction.Ignore)) return false;
            Vector3 focus = HangFocus(slot, "ribbon"), eye = HangEye(slot, "ribbon", st);
            Transform self = player.controller != null ? player.controller.transform : player.transform;
            return !Physics.CheckSphere(eye, 0.1f, ~(1 << 2), QueryTriggerInteraction.Ignore) && !Blocked(eye, focus, ~(1 << 2), self, st);
        }

        /// 自己挂不了的格子（HangSpotFree 不过：绘马架前那几格）。场景里的东西不动，第一次用时算一遍记下来
        bool[] noHang;

        /// 这一格自己挂得了（自己挂时只挑这些；挂不了的那几格只放别人的）
        public bool CanHang(int slot)
        {
            int n = offerings != null ? offerings.SlotCount : 0;
            if (noHang == null || noHang.Length != n)
            {
                noHang = new bool[n];
                for (int i = 0; i < n; i++) noHang[i] = !HangSpotFree(i);
            }
            return slot >= 0 && slot < n && !noHang[slot];
        }

        /// 自己挂的时候挑哪一格：离人最近、自己挂得了的空格。挂得了的都满了：挑离人最近、挂着别人的那一格（evict：先把别人的取下来）。
        /// 挂得了的格子全是自己的，才算挂满（-1）。挂不了的那几格（绘马架前，人站不进去、镜头看不清）永远不挑
        public int HangSlot(Vector3 me, out bool evict)
        {
            evict = false;
            var ok = new List<int>();
            for (int i = 0; i < offerings.SlotCount; i++) if (CanHang(i)) ok.Add(i);
            ok.Sort((x, y) => FlatDist(offerings.SlotPoint(x), me).CompareTo(FlatDist(offerings.SlotPoint(y), me)));
            foreach (int s in ok) if (!offerings.SlotUsed(s)) return s;
            foreach (int s in ok)
                if (offerings.OthersAt(s))
                {
                    evict = true;
                    return s;
                }
            return -1;
        }

        public int HangSlot(Vector3 me) => HangSlot(me, out _);

        // ── 特写镜头放哪 ──

        /// 挂布条、木牌时镜头看着哪：那一格下面一点（布条、木牌的中间）
        public Vector3 HangFocus(int slot, string kind) => offerings.SlotPoint(slot) + Vector3.down * (kind == "plaque" ? 0.22f : 0.27f);

        /// 挂布条的特写：视角、要整个放进画面的身高（脚到头顶）
        public const float HangFov = 52f, HangBody = 1.35f;

        /// 挂某一格时的特写镜头位置（人站在 me）。离布条 2 米多：人从脚到头顶、布条整条都放得进木牌和上面那几块牌子中间那一截
        /// （以前 1.5 米，竖屏里只看得到人的肩膀到膝盖，头在画面外）
        public Vector3 HangEye(int slot, string kind, Vector3 me) =>
            CloseUpEye(HangFocus(slot, kind), offerings.Outward(slot), me, kind == "plaque" ? 2.1f : 2.3f);

        /// 特写的镜头放哪：从 focus 往 back（朝外、人身后）退 dist 米，偏到人的右边、和人的胸口差不多高。
        /// 那边有东西（树干、木桩、绘马架、殿里的柱子）就收近；收得太近、或者从那里看过去被挡住（木桩、架子、自己的身子挡在布条前面），
        /// 就换另一边、抬高、拉远些，挑看得最清楚的一个
        public Vector3 CloseUpEye(Vector3 focus, Vector3 back, Vector3 me, float dist)
        {
            back.y = 0;
            back = back.sqrMagnitude > 1e-4f ? back.normalized : Vector3.back;
            Vector3 right = Vector3.Cross(Vector3.up, -back);
            const int mask = ~(1 << 2);
            Transform self = player.controller != null ? player.controller.transform : player.transform;
            GatherPeople(focus);
            float best = float.MaxValue;
            Vector3 bestEye = focus + back * dist + right * 1.3f + Vector3.up * 0.2f;
            foreach (float side in new[] { 1f, -1f })
                foreach (float lat in new[] { 1.0f, 1.3f, 1.6f })
                    foreach (float up in new[] { 0.2f, 0.4f })
                        foreach (float k in new[] { 1f, 0.85f })
                        {
                            Vector3 want = focus + back * dist * k + right * side * lat + Vector3.up * up;
                            Vector3 dir = want - focus;
                            float len = dir.magnitude;
                            dir /= len;
                            float clear = len;
                            if (Physics.SphereCast(focus, 0.12f, dir, out var hit, len, mask, QueryTriggerInteraction.Ignore) && !hit.transform.IsChildOf(self))
                                clear = Mathf.Max(0.05f, hit.distance - 0.1f);
                            Vector3 eye = focus + dir * clear;
                            if (Physics.CheckSphere(eye, 0.1f, mask, QueryTriggerInteraction.Ignore)) continue;
                            // 从这里看过去：布条（木牌）上几处、画面边上几处，有几处被挡住
                            float blocked = 0;
                            for (int i = -1; i <= 1; i++)
                                for (int j = -1; j <= 1; j++)
                                {
                                    Vector3 pt = focus + right * (i * 0.07f) + Vector3.up * (j * 0.2f + 0.05f);
                                    if (Blocked(eye, pt, mask, self, me)) blocked += 1f;
                                }
                            for (int i = -1; i <= 1; i += 2)
                                for (int j = -1; j <= 1; j += 2)
                                    if (Blocked(eye, focus + right * (i * 0.32f) + Vector3.up * (j * 0.42f), mask, self, Vector3.positiveInfinity)) blocked += 0.4f;
                            // 别的香客（没有碰撞体，射线测不到）站在镜头和布条、和自己之间：整个特写只拍到他的后背
                            if (PeopleBlock(eye, focus)) blocked += 4f;
                            if (PeopleBlock(eye, me + Vector3.up * 1.0f)) blocked += 2f;
                            if (PeopleBlock(eye, me + Vector3.up * 0.4f)) blocked += 1f;
                            float score = blocked + (clear < 1.0f ? (1.0f - clear) * 4f : 0f) + Mathf.Abs(lat - 1.3f) * 0.3f + (up - 0.2f) * 0.2f
                                        + (side < 0 ? 0.08f : 0f) + (k < 1f ? 0.12f : 0f);
                            if (score < best) { best = score; bestEye = eye; }
                        }
            return bestEye;
        }

        /// 上香的特写镜头放哪：在人的侧面（先试右手那边），离 2.5 米上下、和两手差不多高，横着看过去——
        /// 人从脚到头顶、举着的香、俯身插香的两手和香炉都在一个竖屏画面里（木牌和上面几块牌子中间那一截）。以前从身后看，长头发正好挡着手，只看得见香头从肩膀上冒出来。
        /// 斜到前面去（45–60 度）不行：中间供桌上的烛台、花瓶正好挡在镜头和手之间（它们没有碰撞，测不出来），所以只在侧面前后偏一点。
        /// 那边被挡（金柱、边上的供桌、墙）就换另一边、换角度
        public Vector3 IncenseEye(Vector3 focus, Vector3 me)
        {
            Vector3 fwd = hallFacing;
            fwd.y = 0;
            fwd = fwd.sqrMagnitude > 1e-4f ? fwd.normalized : Vector3.forward;
            const int mask = ~(1 << 2);
            Transform self = player.controller != null ? player.controller.transform : player.transform;
            GatherPeople(focus);
            float best = float.MaxValue;
            Vector3 bestEye = focus + Quaternion.Euler(0, 88f, 0) * fwd * 2.6f + Vector3.up * 0.1f;
            foreach (float side in new[] { 1f, -1f })
                foreach (float ang in new[] { 88f, 78f, 100f })
                    foreach (float dist in new[] { 2.6f, 2.3f })
                        foreach (float up in new[] { 0.1f, 0.3f })
                        {
                            Vector3 dir = Quaternion.Euler(0, side * ang, 0) * fwd;
                            Vector3 want = focus + dir * dist + Vector3.up * up;
                            Vector3 d = want - focus;
                            float len = d.magnitude;
                            d /= len;
                            if (Physics.SphereCast(focus, 0.12f, d, out var hit, len, mask, QueryTriggerInteraction.Ignore) && !hit.transform.IsChildOf(self)) continue;
                            if (Physics.CheckSphere(want, 0.15f, mask, QueryTriggerInteraction.Ignore)) continue;
                            // 从这里看过去：手和香、香炉、人的胸口，有几处被挡住
                            float blocked = 0;
                            foreach (var pt in new[] { focus, focus + Vector3.up * 0.25f, hallIncense + Vector3.up * 0.05f, me + Vector3.up * 1.1f + fwd * 0.1f })
                                if (Blocked(want, pt, mask, self, Vector3.positiveInfinity)) blocked += 1f;
                            if (PeopleBlock(want, focus)) blocked += 4f;
                            if (PeopleBlock(want, me + Vector3.up * 0.6f)) blocked += 2f;
                            float score = blocked + Mathf.Abs(ang - 88f) * 0.01f + (dist < 2.5f ? 0.15f : 0f) + (up - 0.1f) * 0.3f + (side < 0 ? 0.1f : 0f);
                            if (score < best) { best = score; bestEye = want; }
                        }
            return bestEye;
        }

        /// 特写附近（6 米内）的别人：香客、走动的人没有碰撞体，挑镜头时按一根竖着的胶囊（脚下 0.15 到 1.45 米、半径 0.3 米）算
        readonly List<Vector3> nearPeople = new List<Vector3>();
        void GatherPeople(Vector3 focus)
        {
            nearPeople.Clear();
            foreach (var f in Folk.All)
                if (f != null && f != player && FlatDist(f.transform.position, focus) < 6f) nearPeople.Add(f.transform.position);
        }

        bool PeopleBlock(Vector3 eye, Vector3 pt)
        {
            foreach (var q in nearPeople)
                if (SegDist(eye, pt, q + Vector3.up * 0.15f, q + Vector3.up * 1.45f) < 0.3f) return true;
            return false;
        }

        /// 从 eye 看 pt 有没有被挡住：碰撞体（人自己的胶囊不算），和人的身子（按一根竖着的胶囊算：脚下 0.35 到 1.2 米、粗 0.2 米）
        static bool Blocked(Vector3 eye, Vector3 pt, int mask, Transform self, Vector3 me)
        {
            if (Physics.Linecast(eye, pt, out var hit, mask, QueryTriggerInteraction.Ignore) && !hit.transform.IsChildOf(self)) return true;
            if (float.IsInfinity(me.x)) return false;
            return SegDist(eye, pt, me + Vector3.up * 0.35f, me + Vector3.up * 1.2f) < 0.2f;
        }

        /// 两条线段之间最近的距离
        static float SegDist(Vector3 p1, Vector3 q1, Vector3 p2, Vector3 q2)
        {
            Vector3 d1 = q1 - p1, d2 = q2 - p2, r = p1 - p2;
            float a = Vector3.Dot(d1, d1), e = Vector3.Dot(d2, d2), f = Vector3.Dot(d2, r);
            float sc, tc;
            float c = Vector3.Dot(d1, r), b = Vector3.Dot(d1, d2), den = a * e - b * b;
            sc = den > 1e-8f ? Mathf.Clamp01((b * f - c * e) / den) : 0f;
            tc = (b * sc + f) / e;
            if (tc < 0f) { tc = 0f; sc = Mathf.Clamp01(-c / a); }
            else if (tc > 1f) { tc = 1f; sc = Mathf.Clamp01((b - c) / a); }
            return Vector3.Distance(p1 + d1 * sc, p2 + d2 * tc);
        }

        // ── 殿里上香 ──

        /// 上香时要整个放进画面的高度：脚到举在脸前的香头
        public const float IncenseBody = 1.45f;

        /// 拿起三支香、举到脸前（Incense_In，约 1.7 秒；之后 SetBow 推 Incense_Scrub 举着香拜）
        void BeginIncenseMotion() => player.SetPose(Folk.Pose.Incense);

        /// 举着香拜一下的深浅（0 直起，1 最低）：SetBow 在 Pose.Incense 下推 Incense_Scrub
        void IncenseBow(float x) => player.SetBow(x);

        /// 俯身把香插进香炉（Incense_Plant，脚不动）：Folk.IncensePlantTime 秒时两手在灰面中心正上方约 5 厘米（按下去那一下），香从手里插进灰里；
        /// 播完人是空手合掌（pose 变成 Gassho），OneShotDone 变成 true
        IEnumerator PlantIncenseMotion(GameObject sticks, Vector3 ash)
        {
            player.PlayOnce("Incense_Plant");
            yield return new WaitForSeconds(Folk.IncensePlantTime);
            yield return offerings.PlantIncense(sticks, ash, 0.25f);
            // 插进灰里了，不再算拿在手里：后面直起身合掌那一段里重新进场，插好的这把留在香炉里（DropHeld 不会把它收掉）
            if (held == sticks) held = null;
            for (float t = 0; t < 2.5f && !player.OneShotDone; t += Time.deltaTime) yield return null;
        }

        /// 殿里上香：走到中间供桌前（面朝佛像）→ 镜头凑近 → 拿出三支点着的香 → 举香拜三拜 → 俯身插进香炉 → 合掌 → offered。
        /// 整个过程 acting：摇杆、点画面都不理
        IEnumerator HallIncense()
        {
            acting = true;
            autoWalk = false;
            onArrive = null;
            Halt();
            EndLinger();
            if (mySeat >= 0)
            {
                // 坐在殿里的蒲团上点了上香：先站起来
                player.SetPose(Folk.Pose.None);
                mySeat = -1;
                Send("{\"type\":\"stood\"}");
                yield return new WaitForSeconds(2.6f);
            }
            cam.Focus(0.6f);
            yield return WalkScripted(Route(player.transform.position, altarStand), 20f);
            float yaw = Quaternion.LookRotation(hallFacing).eulerAngles.y;
            player.FaceYaw(yaw);
            for (float t = 0; t < 0.9f && Mathf.Abs(Mathf.DeltaAngle(player.transform.eulerAngles.y, yaw)) > 5f; t += Time.deltaTime) yield return null;
            // 镜头：从人的右侧面（稍靠前）平平地看过去，两手、那把香、香炉一起在画面里（从身后看头发正好挡着手）
            Vector3 me = player.transform.position;
            Vector3 focus = Vector3.Lerp(hallIncense, me + Vector3.up * 1.0f, 0.45f);
            Vector3 incEye = IncenseEye(focus, me);
            // 竖着：人从脚到举着的香头都在木牌和上面那几块牌子中间
            if (cam is ViewSwitcher iv) iv.CloseUp(focus, incEye, me, me + Vector3.up * IncenseBody);
            else cam.CloseUp(focus, incEye);
            var hand = HandBone(out var finger);
            held = offerings.MakeIncenseHeld(hand, finger);
            sound.Play("sfx_light", 0.6f);
            yield return new WaitForSeconds(0.6f);
            BeginIncenseMotion();
            // 等香举到脸前（人要先转过来的话更久）再拜
            for (float t = 0; t < Folk.IncenseReadyTime + 1.5f && !player.ActionReady; t += Time.deltaTime) yield return null;
            // 举香拜三拜
            for (int i = 0; i < 3; i++)
            {
                for (float t = 0; t < 0.9f; t += Time.deltaTime) { IncenseBow(t / 0.9f * 0.8f); yield return null; }
                yield return new WaitForSeconds(0.45f);
                for (float t = 0; t < 0.9f; t += Time.deltaTime) { IncenseBow(0.8f * (1 - t / 0.9f)); yield return null; }
                IncenseBow(0);
                yield return new WaitForSeconds(0.25f);
            }
            // 站着不动俯身插进香炉，直起来合掌（Incense_Plant 自己收在合掌上，不用再 SetPose）。
            // 插的那一下香还算拿在手里（held）：这时重新进场（StopAllCoroutines）由 DropHeld 收掉，不会悬在半空
            yield return PlantIncenseMotion(held, hallIncense);
            held = null;
            sound.Play("sfx_light", 0.7f);
            yield return new WaitForSeconds(1.4f);
            lingerCloseUp = Time.time + 10f;
            cam.Focus(0.6f);
            acting = false;
            at = SpotHere();
            Send("{\"type\":\"offered\",\"kind\":\"incense\",\"slot\":-1}");
        }

        // ── 殿里：锁平视 ──

        /// 告诉 Flutter 现在是什么视角、锁没锁
        void SendView(ViewSwitcher vs) => Send($"{{\"type\":\"view\",\"mode\":\"{vs.Mode}\",\"locked\":false,\"inhall\":{(inHall ? "true" : "false")},\"reach\":{vs.Reach.ToString("F2", System.Globalization.CultureInfo.InvariantCulture)},\"zoom\":{vs.ZoomTarget.ToString("F2", System.Globalization.CultureInfo.InvariantCulture)}}}");

        /// 进殿：换成平视（殿里俯视看到的是屋顶）、镜头收近、不穿天花板；出殿：换回进殿前的视角
        void WatchHall()
        {
            bool now = InHall(player.transform.position);
            if (now == inHall) return;
            if (now)
            {
                inHall = true;
                if (cam is ViewSwitcher vs)
                {
                    // 殿里照样能转、能压到俯视：镜头不高过天花板，被墙和柱子挡住就收近
                    viewBeforeHall = vs.Mode;
                    vs.SetInterior(true, hallCeiling, hallLookAts, hallCamKeepOut);
                    SendView(vs);
                }
            }
            else LeaveHallView(true);
        }

        void LeaveHallView(bool restore)
        {
            if (!inHall) return;
            inHall = false;
            if (cam is ViewSwitcher vs)
            {
                vs.SetInterior(false, hallCeiling);
                if (restore && !string.IsNullOrEmpty(viewBeforeHall)) vs.SetMode(viewBeforeHall);
                SendView(vs);
            }
            viewBeforeHall = null;
        }

        /// 自己这会儿是不是坐着、跪着（小动物会跟着趴下）
        public bool PlayerResting => mySeat >= 0 || acting;

        /// 进岛时 Flutter 发来：每只小动物和你有多熟、今天要不要来迎接、有没有礼物。格式 "编号:等级:迎接:礼物|..."
        void BondPets(string list)
        {
            foreach (string item in list.Split('|'))
            {
                var f = item.Split(':');
                if (f.Length < 4 || !int.TryParse(f[1], out int level)) continue;
                // 第五段（可以没有）：今天礼物的收藏品编号（pinecone、shell_conch……），它叼的模型换成 gift_<编号>
                foreach (var c in Critter.All) if (c.id == f[0]) c.Bond(level, f[2] == "1", f[3] == "1", f.Length > 4 ? f[4] : null);
            }
        }

        /// 撒谷子喂小鸟、往水里喂鱼
        void Feed(string kind)
        {
            Vector3 at = player.transform.position + player.transform.forward * 1.4f;
            if (kind == "fish")
            {
                foreach (var k in Koi.All)
                    if (Vector3.Distance(k.center, player.transform.position) < 9f)
                    {
                        // 引到离人最近的那片水里：从鱼的地盘中心往人这边靠
                        Vector3 d = player.transform.position - k.center;
                        d.y = 0;
                        k.Lure(k.center + Vector3.ClampMagnitude(d, Mathf.Max(0.3f, d.magnitude - 1.6f)) * 0.75f, 14f);
                    }
                sound.Play("sfx_drop", 0.5f);
            }
            else if (Ambience.Instance != null)
            {
                if (Physics.Raycast(at + Vector3.up * 1.5f, Vector3.down, out var hit, 3f, ~(1 << 2), QueryTriggerInteraction.Ignore)) at.y = hit.point.y;
                Ambience.Instance.FeedBirds(at);
                sound.Play("sfx_cloth", 0.35f);
                // 小鸟飞过来吃的那一阵，镜头对着谷子那一片
                birdFocusAt = at;
                birdFocusUntil = Time.time + 13f;
            }
            cam.Focus(0.4f);
        }

        string nearPet = "", nearWater = "";
        int nearSeat = -1, nearMat = -1;
        bool nearAltar, nearBird, nearBell;
        /// 最近的那片水在哪（抛竿朝它）；下一次找水的时刻（一秒找四次就够）
        Vector3 waterPoint;
        float nextWaterScan;
        /// 镜头正对着的小动物（摸、喂的那一阵）、对着谷子的那一阵
        Transform petFocus;
        float petFocusUntil, birdFocusUntil;
        Vector3 birdFocusAt;

        /// 身边最近的水：往四周 12 个方向、1.5 和 2.6 米处往下看，脚下是水（比水面低）就算。返回 sea、pond 或空
        string ScanWater(Vector3 me)
        {
            if (me.y < waterY - 0.05f || InHall(me)) return "";
            float best = float.MaxValue;
            string kind = "";
            for (int ring = 0; ring < 2; ring++)
            {
                float r = ring == 0 ? 1.5f : 2.6f;
                for (int k = 0; k < 12; k++)
                {
                    float a = k * Mathf.PI / 6f;
                    Vector3 q = me + new Vector3(Mathf.Sin(a), 0, Mathf.Cos(a)) * r;
                    bool wet = !Physics.Raycast(new Vector3(q.x, me.y + 2.5f, q.z), Vector3.down, out var hit, 9f, ~(1 << 2), QueryTriggerInteraction.Ignore) || hit.point.y < waterY - 0.04f;
                    if (!wet) continue;
                    // 朝着人面对的方向的水优先
                    float score = r - Vector3.Dot((q - me).normalized, player.transform.forward) * 0.6f;
                    if (score < best)
                    {
                        best = score;
                        waterPoint = q;
                        kind = FlatDist(q, pondCenter) < pondRadius ? "pond" : "sea";
                    }
                }
                if (kind != "") break;
            }
            return kind;
        }

        /// 钓鱼
        void Fish(string action, string kind)
        {
            if (fishing == null) return;
            switch (action)
            {
                case "cast":
                    if (acting || autoWalk || mySeat >= 0 || sitting != null) { Send("{\"type\":\"fish\",\"state\":\"ended\"}"); return; }
                    string w = ScanWater(player.transform.position);
                    if (w == "") { Send("{\"type\":\"fish\",\"state\":\"ended\"}"); return; }
                    Halt();
                    cam.Focus(0);
                    fishing.Cast(waterPoint, w);
                    break;
                case "reel": fishing.Reel(); break;
                case "show": fishing.Show(kind ?? ""); break;
                default: fishing.Stop(); break;
            }
        }

        /// 敲钟：转过去、两手推撞木，撞上那一下钟声响起
        void Ring()
        {
            if (acting || autoWalk || mySeat >= 0 || sitting != null || (bellRing != null && bellRing.Ringing) || FlatDist(player.transform.position, bellAt) > bellRadius + 0.8f)
            {
                Send("{\"type\":\"actionDone\",\"action\":\"ring\"}");
                return;
            }
            StartCoroutine(RingBell());
        }

        static readonly Dictionary<string, float> PushPose = new Dictionary<string, float>
        {
            // 两臂往前平伸、手掌朝前（关节值在侧面图上试出来的：Arm Front-Back 负的才是往前）
            { "Left Arm Down-Up", -0.45f }, { "Right Arm Down-Up", -0.45f }, { "Left Arm Front-Back", -0.5f }, { "Right Arm Front-Back", -0.5f },
            { "Left Forearm Stretch", 0.3f }, { "Right Forearm Stretch", 0.3f },
        };

        IEnumerator RingBell()
        {
            acting = true;
            Halt();
            if (fishing != null) fishing.Stop(false);
            Vector3 face = bellRing != null && bellRing.face != Vector3.zero ? bellRing.face : bellAt;
            // 先走到撞木尾巴旁边站好（钟亭里挂了撞木的话）
            if (bellRing != null && bellRing.stand != Vector3.zero && FlatDist(player.transform.position, bellRing.stand) > 0.25f)
                yield return WalkScripted(Route(player.transform.position, bellRing.stand), 8f);
            player.FaceTowards(face);
            yield return new WaitForSeconds(0.35f);
            player.custom.Clear();
            foreach (var kv in PushPose) player.custom[kv.Key] = kv.Value;
            player.customPitch = 0;
            player.SetPose(Folk.Pose.Custom);
            if (bellRing != null)
            {
                // 往后拉的时候身子后仰一点，撞出去时往前送
                StartCoroutine(Lean(-6f, 0.7f, 10f, 0.28f));
                yield return bellRing.Ring();
            }
            else
            {
                yield return new WaitForSeconds(0.9f);
                sound.Play(bell, 1f);
                yield return new WaitForSeconds(1.6f);
            }
            player.customPitch = 0;
            player.SetPose(Folk.Pose.None);
            acting = false;
            Send("{\"type\":\"actionDone\",\"action\":\"ring\"}");
        }

        IEnumerator Lean(float back, float tBack, float fwd, float tFwd)
        {
            float t = 0;
            while (t < tBack) { t += Time.deltaTime; player.customPitch = Mathf.SmoothStep(0, back, t / tBack); yield return null; }
            t = 0;
            while (t < tFwd) { t += Time.deltaTime; player.customPitch = Mathf.Lerp(back, fwd, t / tFwd); yield return null; }
            t = 0;
            while (t < 0.8f) { t += Time.deltaTime; player.customPitch = Mathf.SmoothStep(fwd, 0, t / 0.8f); yield return null; }
        }

        /// 身边有没有小动物、是不是站在水边、有没有空蒲团、殿里有没有拜垫、是不是在供桌前
        /// （Flutter 据此显示「摸摸」「喂鱼」「坐下」「跪拜」「上香」）。变了才发
        void WatchNearby()
        {
            Vector3 me = player.transform.position;
            // 空蒲团、拜垫、供桌：站着、没在自动走、没在做动作、没在坐下时才算
            bool free = mySeat < 0 && !autoWalk && !acting && sitting == null;
            int seat = free ? NearestSeat(me, sitRadius) : -1;
            int mat = free ? NearestMat(me) : -1;
            bool altar = free && NearAltar(me);
            // 站在拜垫上（离拜垫比离旁边那个蒲团近）：只给拜，不给「坐下」（两边的拜垫离最北一排静坐的蒲团不到 1.2 米）
            if (seat >= 0 && mat >= 0 && FlatDist(hallMats.GetChild(mat).position, me) < FlatDist(SeatStand(seat), me)) seat = -1;
            bool fishingNow = fishing != null && fishing.Active;
            string pet = "";
            Critter petC = null;
            float best = 2.1f;
            if (free && !fishingNow)
                foreach (var c in Critter.All)
                {
                    float d = Vector3.Distance(c.transform.position, me);
                    if (d < best) { best = d; pet = c.id; petC = c; }
                }
            // 小鸟：有落在地上的在附近才算（太近了它会飞走，所以圈子给大一些）；撒了谷子、鸟在吃的那一阵也算
            bool bird = false;
            if (free && !fishingNow)
                foreach (var b in Bird.All)
                    if (b.Grounded && Vector3.Distance(b.transform.position, me) < birdRadius) { bird = true; break; }
            bool bellNear = free && !fishingNow && FlatDist(me, bellAt) < bellRadius && !InHall(me);
            // 水边：一秒找四次（要往四周打二十几条线）
            string water = nearWater;
            if (Time.time >= nextWaterScan)
            {
                nextWaterScan = Time.time + 0.25f;
                water = free || fishingNow ? ScanWater(me) : "";
            }
            if (pet != nearPet || water != nearWater || seat != nearSeat || mat != nearMat || altar != nearAltar || bird != nearBird || bellNear != nearBell)
            {
                nearPet = pet;
                nearWater = water;
                nearSeat = seat;
                nearMat = mat;
                nearAltar = altar;
                nearBird = bird;
                nearBell = bellNear;
                SendNear();
            }
            // 镜头聚焦：站在小动物跟前（没推摇杆）就对着它、收近；摸、喂的那一阵一直对着；撒了谷子对着谷子那一片
            if (cam is ViewSwitcher vs && !acting)
            {
                bool still = stick.sqrMagnitude < 0.01f && !autoWalk;
                if (fishingNow)
                    vs.Subject(null, fishing.Float + Vector3.up * 0.5f, still ? 1f : 0f, 3.3f, 0.3f);
                else if (petFocus != null && Time.time < petFocusUntil && Vector3.Distance(petFocus.position, me) < 4.5f)
                    vs.Subject(petFocus, Vector3.up * 0.3f, 1f, 1.9f, 1f);
                else if (petC != null && still && !fishingNow)
                    vs.Subject(petC.transform, Vector3.up * 0.3f, 1f, 2.1f, 1f);
                else if (Time.time < birdFocusUntil && still && FlatDist(birdFocusAt, me) < 5f)
                    // 小鸟在地上，旁边常有灌木草丛：从高一点的地方往下看，不让叶子挡在镜头前
                    vs.Subject(null, birdFocusAt + Vector3.up * 0.1f, 1f, 2.6f, 0.95f, 38f);
                else
                    vs.Subject(null, Vector3.zero, 0);
                if (petFocus != null && Time.time >= petFocusUntil) petFocus = null;
            }
        }

        void SendNear() => Send($"{{\"type\":\"near\",\"pet\":\"{nearPet}\",\"water\":\"{nearWater}\",\"bird\":{(nearBird ? "true" : "false")},\"bell\":{(nearBell ? "true" : "false")},\"seat\":{nearSeat},\"mat\":{nearMat},\"altar\":{(nearAltar ? "true" : "false")}}}");

        void SyncPilgrims(string list)
        {
            var present = new HashSet<string>();
            foreach (string item in list.Split('|'))
            {
                var f = item.Split(':');
                if (f.Length < 2 || !int.TryParse(f[1], out int seat)) continue;
                present.Add(f[0]);
                if (seat >= 0 && seat == MySeat)
                {
                    // 名单里有人的座位正是自己坐的（服务器还没收到自己坐下）：内置香客改去别处；
                    // 真人还没来的先不摆，已经在岛上、正走过来的让他换一个空的（不会站到自己的垫子上），都不让他离开
                    if (f.Length > 4 && f[2] == "1" && !string.IsNullOrEmpty(f[4])) seat = -1;
                    else
                    {
                        pilgrims.Yield(f[0], seat);
                        continue;
                    }
                }
                // 进殿后第一次拿到的名单：这些人本来就在，直接坐在位子上；之后新来的才从山门走进来
                // 内置香客多带三项：要做的事、来了几秒、待几秒
                string plan = f.Length > 4 ? f[4] : "";
                float since = f.Length > 5 && float.TryParse(f[5], out float sv) ? sv : 0;
                float stay = f.Length > 6 && float.TryParse(f[6], out float st) ? st : 0;
                pilgrims.Place(f[0], seat, f.Length > 2 && f[2] == "1", f.Length > 3 ? f[3] : "", !synced, plan, since, stay);
            }
            synced = true;
            pilgrims.Sync(present);
        }

        /// 点画面：点中某个地点（树、香炉、大殿……）就走过去，点中空蒲团就去坐
        void Tap(float x, float y)
        {
            if (Busy || Camera.main == null) return;
            // 正转身要坐、正走去坐：不坐了，照点的来
            if (mySeat < 0) CancelSit();
            Ray ray = Camera.main.ViewportPointToRay(new Vector3(x, 1f - y, 0));
            // 一个点离这条视线有多远；在镜头背后的不算
            float Miss(Vector3 p)
            {
                float along = Vector3.Dot(p - ray.origin, ray.direction);
                return along < 0.5f ? float.MaxValue : Vector3.Distance(ray.origin + ray.direction * along, p);
            }
            // 视线先打到的地面（或墙）有多远：比它远出半米以上的蒲团是被挡住的，不算点中
            bool hitAny = Physics.Raycast(ray, out var first, 90f, ~(1 << 2), QueryTriggerInteraction.Ignore);
            float hitDist = hitAny ? first.distance : float.MaxValue;
            // 人在殿里、或者点中的是殿里面（隔着门点殿里的地、佛像）：殿外的地点（大殿前、香炉、树……）都不算点中。
            // 「大殿」那一点看的是殿中间（离地 3 米），殿里点哪儿都离它近，以前在殿里一点地面、一点蒲团旁边，就被领出殿、走到台阶下面去了。
            // 出殿用「出殿」按钮；在殿里隔着门点院子的地，照点地面走出去
            bool hallTap = InHall(player.transform.position) || (hitAny && InHallXZ(first.point) && first.point.y < hallFloor + 4.5f);
            float best = 1f;
            string spot = null;
            int seat = -1;
            foreach (var s in spots)
            {
                if (s.name == at || s.name == startSpot || s.pick <= 0) continue;
                if (hallTap && !InHallXZ(s.floor)) continue;
                float score = Mathf.Min(Miss(s.look) / s.pick, Miss(s.floor) / 1.0f);
                if (score < best)
                {
                    best = score;
                    spot = s.name;
                }
            }
            for (int i = 0; i < SeatTotal; i++)
            {
                if (!SeatFree(i)) continue;
                if (Vector3.Dot(SeatGround(i) - ray.origin, ray.direction) > hitDist + 0.6f) continue;
                float score = Miss(SeatGround(i)) / 0.42f;
                if (score < best)
                {
                    best = score;
                    spot = null;
                    seat = i;
                }
            }
            // 点中的蒲团就在身边：走近路；远的：按过道走过去（明确点了它，就走过去坐）
            if (seat >= 0) SitAt(seat, mySeat < 0 && FlatDist(SeatStand(seat), player.transform.position) <= sitRadius + 0.3f);
            else if (spot != null) Go(spot);
            else if (Physics.Raycast(ray, out var hit, 90f, ~(1 << 2), QueryTriggerInteraction.Ignore) && hit.normal.y > 0.7f)
            {
                // 点了地面：走过去（坐着的先起身退到走道上）；走到了一定回一声 arrived，界面不会一直等
                var path = new List<Vector3>();
                Vector3 from = player.transform.position;
                Halt();
                if (mySeat >= 0)
                {
                    path.Add(SeatLane(mySeat));
                    from = SeatLane(mySeat);
                    player.SetPose(Folk.Pose.None);
                    mySeat = -1;
                    Send("{\"type\":\"stood\"}");
                }
                cam.Focus(0);
                Vector3 to = hit.point;
                // 殿里点到供桌、佛坛、蒲团上、墙根：走到它跟前站得下人的地方
                if (InHall(to)) to = HallStandable(to);
                if (ropeRadius > 0 && FlatDist(to, ropeCenter) < ropeRadius + 0.3f)
                {
                    // 点在绳圈里面：走到绳外那一点就停（绳子挡人，走进去就出不来了）
                    Vector3 d = to - ropeCenter;
                    d.y = 0;
                    if (d.sqrMagnitude < 1e-4f) d = player.transform.position - ropeCenter;
                    d.y = 0;
                    to = ropeCenter + d.normalized * (ropeRadius + 0.45f);
                    // 高低照点中的那一点（树下是平地；走的时候脚下贴着地面）
                    to.y = hit.point.y;
                }
                path.AddRange(Route(from, to));
                Walk(path, to + (to - player.transform.position).normalized, "", ArrivedHere);
            }
        }

        void Update()
        {
            float dt = Time.deltaTime;
            // 挂好布条后的特写：推摇杆走开、或者时间到了，就退回去
            if (lingerCloseUp > 0 && !acting && (Time.time > lingerCloseUp || stick.sqrMagnitude > 0.01f)) EndLinger();
            // 进出大殿：锁平视、放开
            WatchHall();
            // 坐在院子里的蒲团上：平视镜头收近一点
            if (cam is ViewSwitcher seatCam) seatCam.Seated(mySeat >= 0 && !HallSeat(mySeat));
            // 摇杆：按镜头朝向走（转身坐下那一小段不走：一推摇杆 Move 就把坐下取消了）
            // 自动走卡住了（终点上有人）：就算到了
            WatchStall();
            if (!autoWalk && !acting && mySeat < 0 && sitting == null)
            {
                FreeMove();
                // 一推摇杆走开，镜头就回到平常的远近
                if (stick.sqrMagnitude > 0.01f) cam.Focus(0);
                Quaternion yaw = Quaternion.Euler(0, stickHeld ? stickYaw : cam.Yaw, 0);
                Vector3 v = yaw * new Vector3(stick.x, 0, stick.y) * player.walkSpeed;
                player.Drive(v);
            }
            // 离哪个地点近，就算在哪；走开了告诉 Flutter（做动作、挂布条、转身坐下时不算，做完再说）
            if (!autoWalk && mySeat < 0 && !acting && sitting == null)
            {
                string near = SpotHere();
                if (near != at && at != startSpot || (at == startSpot && near != "" && near != startSpot))
                {
                    at = near;
                    Send($"{{\"type\":\"arrived\",\"spot\":\"{near}\"}}");
                }
            }
            if (freeMoveLater && !player.BenchGliding) { freeMoveLater = false; FreeMove(); }
            WatchNearby();
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
