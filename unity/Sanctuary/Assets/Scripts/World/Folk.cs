using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Animations;
using UnityEngine.Playables;

namespace Yuanjing
{
    /// 殿里的一个小人（自己或者别人）。动作库给走路、站着、坐椅子的动画；
    /// 动作库里没有的姿势（合掌、鞠躬、跪拜、盘坐）在动画之上直接改关节角度，平滑地混进去。
    ///
    /// 走路（2026-11-17 重做）：
    /// - 几段步态循环（慢、中、快，男女各一套，tools/mocap/locomotion.py 加工）全都从左脚着地开始、右脚着地在正中间，
    ///   按同一个相位一起播，按速度两两混合：步幅和步频都跟着速度变，混合时两只脚的位置一致，不会抵消成小碎步。
    /// - 人挪多少完全按动画自己算出来的位移（根运动），脚踩在地上就不滑。
    /// - 起步：从站姿淡进步态里右脚正在往前迈的那一刻，速度从 0 加上去（步子跟着慢慢迈开）；
    ///   要转过头去（50 度以上）就播「转身起步」（真人的转身 + 第一步，镜像得到另一边），转角按需要缩放。
    /// - 停步：随时都能停，按当前相位接进真人的停步片段（左脚着地后的半步里进停步片段，右脚的半步进它的镜像），
    ///   最后一步收脚站稳，再淡到待机。按路线走的人提前算好停步要走多远，正好停在终点。
    /// - 转弯：朝向按角速度上限平滑地转，绕着踩在地上那只脚转（脚不拧着滑），速度越快身子越往弯里倾，头先看过去。
    ///   急转时先放慢。站着转身是原地小碎步。
    /// - 合掌、鞠躬时一推摇杆：腿立刻走，手臂在上半身那一层里把合掌放下来，身子不会滑着走。
    public class Folk : MonoBehaviour
    {
        public enum Pose { None, Gassho, Bow, Kneel, KneelBow, CrossLegged, Bench, Custom, Hang, Incense }

        /// 调姿势用：Custom 姿势下直接按名字设的关节值，pitch 是整个身体往前倾的角度
        public Dictionary<string, float> custom = new Dictionary<string, float>();
        public float customPitch;

        public Animator animator;
        /// 动画：站着、慢走、快走、坐着。直接用播放图按速度混合（不经过状态机：状态机在手机版里取不到片段）
        /// walkClip、walkFastClip 只在没有 gaitClips 时用（老的 Q 版小人）
        public AnimationClip idleClip, walkClip, walkFastClip, sitClip;
        /// 合掌、鞠躬、跪拜、盘坐、挂布条、上香的动作（tools/blender/pray_motions.py 做的关键帧，Assets/Motion/）。有就用它们，没有才用老办法硬改关节
        public AnimationClip[] actionClips;
        /// 几段站立待机（动捕），每人挑一段
        public AnimationClip[] idleClips;

        /// 步态循环，从慢到快（见类说明）
        public AnimationClip[] gaitClips;
        /// 停步（左脚着地后进来）、它的镜像（右脚着地后进来）；转身起步（片段本身往 turnLeft 那边转）和它的镜像
        public AnimationClip stopClip, stopMirrorClip, turnClip, turnMirrorClip;
        /// 停步片段：开头到 stopEntry 秒之间都能进来（对应步态相位 0..0.5）；stopStill 秒以后人站稳了；
        /// stopDist：片段里走过的距离按时间均分的累计比例（0..1，33 个点）；stopSteps：着地的时刻（脚步声）
        public float stopEntry = 0.7f, stopStill = 1.6f;
        public float[] stopDist, stopSteps;
        /// 停步从哪一刻接进来（BuildAnime 按姿势配好）：每段步态 11 个数，对应左脚着地后的相位 0、0.05 … 0.5
        public float[] stopMap;
        /// 转身起步：片段转了多少度、往左还是往右、结束时接步态的相位；turnSteps：着地的时刻
        public float turnAngle = 89f, turnExitPhase = 0.5f;
        public bool turnLeft = true;
        public float[] turnSteps;
        /// 在这个人身上，脚往后退的速度是动画根运动的几倍（每段步态一个；停步、转身各一个。BuildAnime 量好存下）
        public float[] gaitFootScale;
        public float stopFootScale = 1f, turnFootScale = 1f;

        /// 装模型的子物体：坐下、跪下时整个往下沉，靠它
        public Transform model;
        public TextMesh nameTag;
        /// 名字的大小随镜头远近变：每米放大多少、最大多大、多远以外不显示。由镜头脚本按自己的远近来设
        public static float TagScalePerMeter = 0.24f, TagMaxScale = 2.4f, TagHideBeyond = 26f;
        /// 自己那一团（xyz 中心，w 半径；0 是不管）：平视时挡在镜头和自己之间的人身子用网点淡掉（YJAnime 的 YJOccluderFade），
        /// 名字也收起来（不压在自己身上）。ViewSwitcher 每帧给
        public static Vector4 OccluderFocus;

        /// 这一点是不是在「从镜头看过去罩住自己的那个圆锥里、又比自己近」（同 YJOccluderFade，淡得过一半的算）
        public static bool InFrontOfFocus(Vector3 cam, Vector3 p)
        {
            if (OccluderFocus.w <= 0f) return false;
            Vector3 c = OccluderFocus;
            Vector3 toP = c - cam;
            float dp = toP.magnitude;
            if (dp < 1e-3f) return false;
            Vector3 dir = toP / dp, toX = p - cam;
            float along = Vector3.Dot(toX, dir);
            if (along > dp - OccluderFocus.w - 0.15f || along <= 0f) return false;
            float perp = (toX - dir * along).magnitude;
            return perp - OccluderFocus.w * along / dp < 0.1f;
        }
        public float walkSpeed = 0.85f;
        /// Q 版：头放大的倍数（脖子也稍微拉长一点，免得下巴埋进胸口）
        public float headScale = 1.9f, neckScale = 1.2f;
        /// Q 版：腿短一些、胳膊略短
        public float legScale = 1f, armScale = 0.9f;

        public Pose pose { get; private set; }
        /// 场上所有人（避让、栈桥口排队用）
        public static readonly List<Folk> All = new List<Folk>();
        void OnEnable() => All.Add(this);
        void OnDisable() => All.Remove(this);
        public bool Moving => path.Count > 0;
        public event Action Arrived;
        public event Action Step;
        /// PlayOnce 放的那段（或者 ReleaseHang 之后的收手）播完了
        public bool OneShotDone { get; private set; } = true;
        public event Action OneShotFinished;

        HumanPoseHandler handler;
        HumanPose hp;
        float weight;            // 现在的姿势混进去多少（0..1）
        Pose shown;              // 正在显示（或者正在淡出）的姿势
        float bowPhase;          // 鞠躬：0 直起，1 俯到最低
        float sink, sinkVel;
        Transform head, hips, lFoot, rFoot, lKnee, rKnee, neck, lThigh, rThigh, lArm, rArm, lHand, rHand, lToe, rToe;
        float ankle;

        /// 关节的缩放：动画只管转动，不碰缩放，但姿势混合会把骨骼重设一遍，所以每帧都补一次
        void ApplyProportions()
        {
            if (neck != null) neck.localScale = Vector3.one * neckScale;
            if (head != null) head.localScale = Vector3.one * (headScale / neckScale);
            if (lThigh != null) lThigh.localScale = rThigh.localScale = Vector3.one * legScale;
            if (lArm != null) lArm.localScale = rArm.localScale = Vector3.one * armScale;
        }
        readonly List<Vector3> path = new List<Vector3>();
        Vector3 velocity;
        float faceYaw, stepDist;
        bool hasFace;
        static readonly Dictionary<string, int> muscleByName = new Dictionary<string, int>();

        void Awake() => Init();

        PlayableGraph graph;
        AnimationLayerMixerPlayable layers;
        AnimationMixerPlayable mixer, upperMixer;
        AnimationClipPlayable[] slots, upperSlots;
        float sitW;

        // 播放图里各段的位置：0 待机，gaitBase.. 步态，停步/镜像/转身/镜像（各两份），坐（老的），actBase.. 动作，最后是另外几段待机
        // 停步、转身每段挂两份：快速连点摇杆时，上一次的那份还在淡出，这次用另一份从头播（不把正在淡出的那份倒回去，身子不会一跳）
        int gaitBase = 1, gaitN, stopSlot = -1, stopMSlot = -1, turnSlot = -1, turnMSlot = -1, sitSlot, actBase;
        int stopSlot2 = -1, stopMSlot2 = -1, turnSlot2 = -1, turnMSlot2 = -1;
        readonly List<int> trSlots = new List<int>();
        float[] trW;
        AnimationClip[] gait;
        static AvatarMask upperMask;

        /// 建播放图（见上面的各段位置），外面再套一层：上半身那层（手臂）用来在走路时放下合掌
        void BuildGraph()
        {
            if (graph.IsValid() || idleClip == null) return;
            animator.runtimeAnimatorController = null;
            graph = PlayableGraph.Create("Folk_" + name);
            graph.SetTimeUpdateMode(DirectorUpdateMode.GameTime);
            var output = AnimationPlayableOutput.Create(graph, "anim", animator);
            if (idleClips != null && idleClips.Length > 0) idleClip = idleClips[Mathf.Abs(name.GetHashCode()) % idleClips.Length];
            gait = gaitClips != null && gaitClips.Length > 0 ? gaitClips : walkFastClip != null && walkFastClip != walkClip ? new[] { walkClip, walkFastClip } : new[] { walkClip };
            gaitN = gait.Length;
            var clips = new List<AnimationClip> { idleClip };
            clips.AddRange(gait);
            int Add(AnimationClip c) { if (c == null) return -1; clips.Add(c); return clips.Count - 1; }
            stopSlot = Add(stopClip); stopSlot2 = Add(stopClip);
            stopMSlot = Add(stopMirrorClip); stopMSlot2 = Add(stopMirrorClip);
            turnSlot = Add(turnClip); turnSlot2 = Add(turnClip);
            turnMSlot = Add(turnMirrorClip); turnMSlot2 = Add(turnMirrorClip);
            trSlots.Clear();
            foreach (int s in new[] { stopSlot, stopSlot2, stopMSlot, stopMSlot2, turnSlot, turnSlot2, turnMSlot, turnMSlot2 }) if (s >= 0) trSlots.Add(s);
            sitSlot = Add(sitClip != null ? sitClip : idleClip);
            actBase = clips.Count;
            actIndex.Clear();
            if (actionClips != null)
                foreach (var c in actionClips)
                    if (c != null) { actIndex[c.name] = clips.Count; clips.Add(c); }
            actWeight = new float[actionClips != null ? actIndex.Count : 0];
            // 另外几段待机挂在最后：站着时隔一阵换一段（换重心、看看四周），不总是同一段循环
            idleSlot.Clear();
            idleSlot.Add(0);
            if (idleClips != null)
                foreach (var c in idleClips)
                    if (c != null && c != idleClip) { idleSlot.Add(clips.Count); clips.Add(c); }
            idleW = new float[idleSlot.Count];
            idleW[0] = 1;
            idleNext = UnityEngine.Random.Range(12f, 35f);
            trW = new float[clips.Count];
            mixer = AnimationMixerPlayable.Create(graph, clips.Count);
            slots = new AnimationClipPlayable[clips.Count];
            for (int i = 0; i < clips.Count; i++)
            {
                slots[i] = AnimationClipPlayable.Create(graph, clips[i]);
                // 脚贴地：人形动画按原来脚的位置修正
                slots[i].SetApplyFootIK(true);
                // 待机、动作各段错开一点起点，人多的时候不会整齐划一（步态各段必须同相位，下面单独设）
                slots[i].SetTime(UnityEngine.Random.value * clips[i].length);
                graph.Connect(slots[i], 0, mixer, i);
            }
            phase = UnityEngine.Random.value;
            SyncGait(phase);
            foreach (int s in trSlots) { slots[s].SetTime(0); slots[s].SetSpeed(0); }
            // 上半身那层：动作段各一份，只给手臂
            upperMixer = AnimationMixerPlayable.Create(graph, actWeight.Length);
            upperSlots = new AnimationClipPlayable[actWeight.Length];
            for (int j = 0; j < actWeight.Length; j++)
            {
                upperSlots[j] = AnimationClipPlayable.Create(graph, actionClips[j]);
                upperSlots[j].SetSpeed(0);
                graph.Connect(upperSlots[j], 0, upperMixer, j);
            }
            layers = AnimationLayerMixerPlayable.Create(graph, 2);
            graph.Connect(mixer, 0, layers, 0);
            graph.Connect(upperMixer, 0, layers, 1);
            layers.SetInputWeight(0, 1);
            layers.SetInputWeight(1, 0);
            if (upperMask == null)
            {
                upperMask = new AvatarMask();
                for (int i = 0; i < (int)AvatarMaskBodyPart.LastBodyPart; i++) upperMask.SetHumanoidBodyPartActive((AvatarMaskBodyPart)i, false);
                foreach (var b in new[] { AvatarMaskBodyPart.LeftArm, AvatarMaskBodyPart.RightArm, AvatarMaskBodyPart.LeftFingers, AvatarMaskBodyPart.RightFingers })
                    upperMask.SetHumanoidBodyPartActive(b, true);
            }
            layers.SetLayerMaskFromAvatarMask(1, upperMask);
            output.SetSourcePlayable(layers);
            Mix(0);
            if (Application.isPlaying) graph.Play();
        }

        // ── 动作段：合掌、鞠躬、跪拜、盘坐、挂布条、上香 ──
        // 播放图里除了走路、待机那几段，还挂着每一段动作；同一时间只有一段动作在播，换段时交叉淡化 0.25 秒。
        // 动作段之上整体还有一个权重 actW：0 是走路待机，1 是动作。
        readonly Dictionary<string, int> actIndex = new Dictionary<string, int>();
        readonly List<int> idleSlot = new List<int>();
        float[] idleW;
        int idleNow;
        float idleNext;
        float[] actWeight;
        readonly Queue<string> actQueue = new Queue<string>();
        string actNow;
        float actW, actTarget;
        /// PlayOnce 正在放的那段；它播完时 OneShotDone 变成 true
        string oneShot;
        bool faceHold, holding;  // 站着的动作在等人转过来（holding：已经在等了）
        float holdT, bowShown;   // bowShown：拖着播的那段实际显示到的鞠躬深浅（限速跟着 bowPhase）
        bool UseActions => actionClips != null && actionClips.Length > 0 && Pose_Allowed(shown);
        static bool Pose_Allowed(Pose p) => p != Pose.Bench && p != Pose.Custom;

        bool Has(string n) => actIndex.ContainsKey(n);
        AnimationClip ActClip(string n) => actionClips[actIndex[n] - actBase];
        /// 站着做的动作（走路时可以只留在手臂上收掉）；跪、坐的不算
        static bool Standing(string n) => n != null && !n.StartsWith("Kneel") && !n.StartsWith("Kowtow") && !n.StartsWith("Sit");

        void QueueFor(Pose old, Pose p, bool instant)
        {
            actQueue.Clear();
            bool standUp = old == Pose.Gassho || old == Pose.Bow;
            bool kneeling = old == Pose.Kneel || old == Pose.KneelBow;
            switch (p)
            {
                case Pose.Gassho:
                    if (!standUp && !instant) actQueue.Enqueue("Gassho_In");
                    actQueue.Enqueue("Gassho_Loop");
                    break;
                case Pose.Bow:
                    if (!standUp && !instant) actQueue.Enqueue("Gassho_In");
                    actQueue.Enqueue("Bow_Scrub");
                    break;
                case Pose.Kneel:
                    if (!kneeling && !instant) actQueue.Enqueue("Kneel_Down");
                    actQueue.Enqueue("Kneel_Loop");
                    break;
                case Pose.KneelBow:
                    if (!kneeling && !instant) actQueue.Enqueue("Kneel_Down");
                    actQueue.Enqueue("Kowtow_Scrub");
                    break;
                case Pose.CrossLegged:
                    if (old != Pose.CrossLegged && !instant) actQueue.Enqueue("Sit_Down");
                    actQueue.Enqueue("Sit_Loop");
                    break;
                case Pose.Hang:
                    // 伸手到绳上 → 系（循环，直到 ReleaseHang）
                    if (!instant) actQueue.Enqueue("Hang_In");
                    actQueue.Enqueue("Hang_Loop");
                    break;
                case Pose.Incense:
                    // 举香到额前 → 拿着香（鞠躬由 SetBow 拖着 Incense_Scrub 播）
                    if (!instant) actQueue.Enqueue("Incense_In");
                    actQueue.Enqueue("Incense_Scrub");
                    break;
                case Pose.None:
                    if (instant) break;
                    if (kneeling) actQueue.Enqueue("Kneel_Up");
                    else if (old == Pose.CrossLegged) actQueue.Enqueue("Sit_Up");
                    else if (standUp) actQueue.Enqueue("Gassho_Out");
                    else if (old == Pose.Hang) actQueue.Enqueue("Hang_Out");
                    else if (old == Pose.Incense) actQueue.Enqueue("Incense_Out");
                    break;
            }
            actQueue.TrimExcess();
            // 正在播一段过渡（跪下去、坐下去、起身）还没播完：等它播完再接新的，不从半截切走
            bool midTransition = !instant && actNow != null && !actNow.EndsWith("_Loop") && !actNow.EndsWith("_Scrub")
                                 && slots[actIndex[actNow]].GetTime() < ActClip(actNow).length - 0.15f;
            if (actQueue.Count > 0 && midTransition) { actTarget = 1; return; }
            if (actQueue.Count > 0) { Next(instant); actTarget = 1; if (instant) actW = 1; }
            else { actTarget = 0; if (instant) actW = 0; }
        }

        void Next(bool instant)
        {
            if (actQueue.Count == 0) return;
            string n = actQueue.Dequeue();
            while (!Has(n) && actQueue.Count > 0) n = actQueue.Dequeue();
            if (!Has(n)) return;
            actNow = n;
            var sl = slots[actIndex[n]];
            sl.SetTime(n.EndsWith("_Loop") ? UnityEngine.Random.value * ActClip(n).length : 0);
            sl.SetSpeed(n.EndsWith("_Scrub") ? 0 : 1);
            // 拖着播的那段（鞠躬）从直起来的样子开始，跟着 bowPhase 往下（限速，不会一换过去就弯到一半）
            if (n.EndsWith("_Scrub")) bowShown = instant ? bowPhase : 0;
            if (instant) for (int i = 0; i < actWeight.Length; i++) actWeight[i] = i == actIndex[n] - actBase ? 1 : 0;
        }

        /// 每帧：推进动作段（播完的段接下一段；拖着播的段按鞠躬进度定时刻），淡化各段权重
        void UpdateActions(float dt)
        {
            if (actWeight == null) return;
            // 站着的动作要等人转过来（见 SetPose）：差 20 度以上就先停在第一帧、不混进来，原地迈小步转到差 8 度以内再开始
            if (faceHold)
            {
                holdT += dt;
                float e = hasFace ? Mathf.Abs(Mathf.DeltaAngle(transform.eulerAngles.y, faceYaw)) : 0f;
                bool wait = actNow != null && pose != Pose.None && holdT < 3f && (e > (holding ? 8f : 20f) || loco == Loco.Stop || loco == Loco.Turn);
                if (wait)
                {
                    holding = true;
                    if (!actNow.EndsWith("_Loop") && !actNow.EndsWith("_Scrub")) { var sl = slots[actIndex[actNow]]; sl.SetTime(0); sl.SetSpeed(0); }
                }
                else
                {
                    if (holding && actNow != null && !actNow.EndsWith("_Scrub")) slots[actIndex[actNow]].SetSpeed(1);
                    faceHold = holding = false;
                }
            }
            if (actNow != null)
            {
                int i = actIndex[actNow];
                var clip = ActClip(actNow);
                if (actNow.EndsWith("_Scrub"))
                {
                    bowShown = dt <= 0 ? bowPhase : Mathf.MoveTowards(bowShown, bowPhase, dt / 0.35f);
                    slots[i].SetTime(Mathf.SmoothStep(0, 1, bowShown) * clip.length * 0.999f);
                }
                else if (!holding && !actNow.EndsWith("_Loop") && slots[i].GetTime() >= clip.length - 0.12f)
                {
                    string done = actNow;
                    if (actQueue.Count > 0) Next(false);
                    else if (pose == Pose.None)
                    {
                        // 从蒲团上站起来：原点挪到人站的地方，立刻换回站姿（不淡出，淡出的那一下身子会往回飘）
                        if (actNow == "Sit_Up")
                        {
                            if (sitGlide) GlideSeat();
                            else
                            {
                                // 原点一直在蒲团下面，起身那段动作自己带着人往前站到草垫上（SeatStep）：播完把原点挪过去再换站姿。
                                // 不挪的话一换回站姿人就缩回蒲团上站着，脚踩进圆蒲团里，再从那里走开
                                var mover = controller != null ? controller.transform : transform;
                                Vector3 to = sitTo + transform.forward * SeatStep * transform.lossyScale.y / 0.806f;
                                to.y = mover.position.y;
                                // 站在草垫上（比地面高几厘米）：脚下有碰撞就站到它上面
                                if (Physics.Raycast(to + Vector3.up * 0.4f, Vector3.down, out var hit, 0.6f, ~(1 << 2), QueryTriggerInteraction.Ignore) && Mathf.Abs(hit.point.y - to.y) < 0.12f) to.y = hit.point.y;
                                mover.position = to;
                                lastPos = transform.position;
                            }
                            sitGlide = false; actW = 0; for (int j = 0; j < actWeight.Length; j++) actWeight[j] = 0;
                        }
                        actTarget = 0;
                    }
                    // 上香插完香，两手空着合掌：之后就是合掌的姿势（可以接着鞠躬、放下）
                    if (done == "Incense_Plant" && pose == Pose.Incense) { pose = shown = Pose.Gassho; actQueue.Clear(); actQueue.Enqueue("Gassho_Loop"); Next(false); }
                    if (done == oneShot) FinishOneShot();
                }
                // 合掌、盘坐时又要低头鞠躬：换成拖着播的那段，起来以后换回循环
                string scrub = pose == Pose.Gassho ? "Gassho_Scrub" : pose == Pose.CrossLegged ? "SitBow_Scrub" : null;
                string loop = pose == Pose.Gassho ? "Gassho_Loop" : pose == Pose.CrossLegged ? "Sit_Loop" : null;
                if (scrub != null && actQueue.Count == 0 && Has(scrub))
                {
                    if (bowPhase > 0.001f && actNow == loop) { actQueue.Enqueue(scrub); Next(false); }
                    else if (bowPhase <= 0.001f && bowShown <= 0.001f && actNow == scrub) { actQueue.Enqueue(loop); Next(false); }
                }
            }
            float k = dt <= 0 ? 1 : Mathf.Clamp01(dt / 0.25f);
            for (int j = 0; j < actWeight.Length; j++)
            {
                bool on = actNow != null && actIndex[actNow] - actBase == j;
                actWeight[j] = Mathf.MoveTowards(actWeight[j], on ? 1 : 0, k);
            }
            actW = Mathf.MoveTowards(actW, holding ? 0 : actTarget, dt <= 0 ? 1 : dt / (actFast ? 0.2f : 0.35f));
            if (actW <= 0.001f && actTarget == 0) { actNow = null; actFast = false; }
            float sum = 0;
            foreach (float w in actWeight) sum += w;
            for (int j = 0; j < actWeight.Length; j++)
                mixer.SetInputWeight(actBase + j, sum > 1e-4f ? actWeight[j] / sum * actW : 0);
            UpdateUpper(dt);
        }

        void FinishOneShot()
        {
            oneShot = null;
            OneShotDone = true;
            OneShotFinished?.Invoke();
        }

        // ── 上半身那层：走起来时把站着做的动作（合掌、拿香、系布条）收在手臂上，腿照常走 ──
        int upperNow = -1, upperFrom = -1;
        float upperW, upperFromW;
        bool actFast, upperIn;

        /// 要走了：正在做的站立动作从全身换到手臂那层，播它的「放下」那段；全身的动作权重很快淡掉。
        /// 手臂那层一开始就是现在这个姿势（同一段、同一刻，满权重），0.3 秒里换成「放下」那段（从松手的那一刻播起），
        /// 放下以后再淡回走路的摆臂：两层交接时手不跳，也不会举着手走一段
        void HandOffToArms()
        {
            if (actNow == null || !Standing(actNow) || upperSlots == null) return;
            string n = actNow;
            int cur = actIndex[n] - actBase;
            float tNow = (float)slots[actIndex[n]].GetTime();
            string outN = n.EndsWith("_Out") ? n : n.StartsWith("Hang") ? "Hang_Out" : n.StartsWith("Incense") ? "Incense_Out" : "Gassho_Out";
            upperFrom = -1;
            if (Has(outN))
            {
                int o = actIndex[outN] - actBase;
                upperNow = o;
                if (outN == n) upperSlots[o].SetTime(tNow);
                else
                {
                    upperFrom = cur;
                    upperFromW = 1;
                    upperSlots[cur].SetTime(tNow);
                    upperSlots[cur].SetSpeed(n.EndsWith("_Loop") ? 1 : 0);
                    // 「放下」从手已经收回来的那一刻播起（Hang_Out 0.8 秒、Incense_Out 0.45 秒），播快一点，不举着手走
                    upperSlots[o].SetTime(outN == "Hang_Out" ? 0.8f : outN == "Incense_Out" ? 0.45f : 0.15f);
                }
                upperSlots[o].SetSpeed(1.4f);
                upperW = Mathf.Clamp01(actW);
                upperIn = true;
            }
            if (oneShot != null) FinishOneShot();
            actQueue.Clear();
            actTarget = 0;
            actFast = true;
            faceHold = holding = false;
            pose = Pose.None;
        }

        void UpdateUpper(float dt)
        {
            if (upperSlots == null) return;
            if (upperNow >= 0)
            {
                var c = actionClips[upperNow];
                // 全身那层的动作还没淡完时手臂这层保持满权重（不然淡完的那一下手会跳）；「放下」快播完了再淡回走路的摆臂
                if (upperSlots[upperNow].GetTime() >= c.length - 0.3f && actW <= 0.001f) { upperIn = false; upperW = Mathf.MoveTowards(upperW, 0, dt / 0.3f); }
                else if (upperIn) upperW = Mathf.MoveTowards(upperW, 1, dt / 0.15f);
                if (upperW <= 0.001f && !upperIn) { upperSlots[upperNow].SetSpeed(0); upperNow = -1; }
            }
            if (upperFrom >= 0)
            {
                upperFromW = Mathf.MoveTowards(upperFromW, 0, dt / 0.25f);
                if (upperFromW <= 0.001f || upperNow < 0) { upperSlots[upperFrom].SetSpeed(0); upperFrom = -1; }
            }
            for (int j = 0; j < upperSlots.Length; j++)
                upperMixer.SetInputWeight(j, j == upperFrom ? upperFromW : j == upperNow ? 1 - (upperFrom >= 0 ? upperFromW : 0) : 0);
            layers.SetInputWeight(1, upperNow >= 0 ? upperW : 0);
        }

        // ── 走路（见类说明） ──
        enum Loco { Idle, Move, Stop, Turn }
        Loco loco;
        float phase;                 // 步态相位：0 左脚着地，0.5 右脚着地
        float speedCmd;              // 现在按多快走（米/秒）
        float wIdle = 1, wGait, wStop, wTurn;   // 待机、步态、停步、转身起步四块的权重（淡入淡出）
        float fadeTime = 0.25f;
        int stopNow = -1, turnNow = -1;          // 正在用的停步、转身片段在播放图里的位置（各段的权重在 trW 里，淡出完才归零）
        float turnScale = 1;
        float stopRate0 = 1, stopT0;
        float shuffle;               // 站着原地转身时小碎步的权重
        Vector3 desired;             // 想往哪走（水平速度，米/秒）
        float yawVel, lean, headLook;
        readonly float[] cw = new float[8];      // 各段步态的权重
        float gaitRate = 1, gaitT = 1;
        bool arriving;
        int planSteps;               // 快到终点：停步前还要迈几步（0 = 还没定）
        float stanceYaw;             // 这一步（从上次落脚起）已经转了多少度
        Vector3 strikePos;           // 上次落脚时人在哪
        float strikeCmd, stepK = 1;  // 从上次落脚起按速度算该走多远；真走的 / 算的（平均）
        bool strikeValid;
        const float StanceYawCap = 55f;
        /// 走路转弯时踩在地上那只脚的「拧回去」的角度（度）：身子绕这只脚转了多少，这只脚就少跟着转一半（髋关节往里、往外转吃掉另一半），
        /// 脚掌不像钉在转盘上一样跟着身子整个转。抬脚以后慢慢放掉
        float lockYawL, lockYawR;
        int pivotFoot;               // RotateAbout 这一帧绕的哪只脚：1 左、2 右、3 两脚中间、0 原点
        float planSpeed, planPh;     // 这一步按多快走；上一帧的相位（看有没有落脚）
        Vector3 pivotMove;           // 这一帧绕脚转身带出来的位移
        Vector3 correction;          // 停在终点要补的那一点（米/秒）
        int rootFrame = -10;
        bool useRoot;
        Vector3 lastPos;
        int freshRoot;

        float ScaleK => (animator != null && animator.isHuman ? animator.humanScale : 1f) * transform.lossyScale.y;
        float GaitSpeed(int i) => gait[i].averageSpeed.magnitude * ScaleK * GaitFoot(i);
        float GaitFoot(int i) => gaitFootScale != null && i < gaitFootScale.Length && gait == gaitClips ? gaitFootScale[i] : 1f;

        /// 这一帧根运动要放大多少（按各段的权重）
        float FootScaleNow()
        {
            float sum = wGait * (gaitN > 0 ? 1 : 0) + wStop + wTurn, acc = 0;
            for (int i = 0; i < gaitN && i < cw.Length; i++) acc += wGait * cw[i] * GaitFoot(i);
            acc += wStop * stopFootScale + wTurn * turnFootScale;
            return sum > 1e-3f ? acc / sum : 1f;
        }
        float MinWalk => gaitN > 0 ? GaitSpeed(0) : 0.6f;

        /// 按速度 s 走，一步（半个周期）迈多远（米）。会改 cw、gaitT、gaitRate（每帧后面会按真的速度重算）
        float StepLen(float s)
        {
            GaitWeights(Mathf.Max(s, 0.05f));
            return s * gaitT / Mathf.Max(0.05f, gaitRate) * 0.5f;
        }

        /// 一步要迈 len 米，该按多快走（在 lo..hi 里找）
        float SpeedForStep(float len, float lo, float hi)
        {
            for (int i = 0; i < 14; i++)
            {
                float mid = (lo + hi) * 0.5f;
                if (StepLen(mid) < len) lo = mid; else hi = mid;
            }
            return (lo + hi) * 0.5f;
        }

        /// 按速度 s 走到下一次落脚时停步，停步片段还要走多远（停步从哪一刻接进来和速度有关，见 stopMap）
        float StopRemainAtStrike(float s)
        {
            GaitWeights(Mathf.Max(s, 0.05f));
            StopEntry(0f, out _, out float t);
            return StopRemain(t);
        }

        /// 快到终点时（在落脚那一刻）定：还要迈几步（planSteps），按多快走（planSpeed）。
        /// 迈 k 步、每步 StepLen(s)×stepK，再加上停步片段自己走的那段，正好到终点。已经定好的步数还走得到就不改（不来回改步数）；
        /// 走不到才重选：要么按 hi 走 kf 步、剩下不到 5 厘米停步时补，要么多迈一步、每步小一点（慢一点）
        void PlanApproach(float remB, float lo, float hi, bool stepped)
        {
            if (stepped) planSteps = Mathf.Max(1, planSteps - 1);
            float G(int k, float sp) => k * StepLen(sp) * stepK + StopRemainAtStrike(sp) - remB;
            // 按定好的步数、速度走下去，停的地方差不到 6 厘米就不改（停步里补）：速度不因为一点点误差来回调
            if (stepped && planSpeed >= lo - 1e-3f && planSpeed <= hi + 1e-3f && Mathf.Abs(G(planSteps, planSpeed)) <= 0.06f) return;
            bool Solvable(int k) => k >= 1 && G(k, lo) <= 0.02f && G(k, hi) >= -0.04f;
            if (!(stepped && Solvable(planSteps)))
            {
                float uHi = remB - StopRemainAtStrike(hi), slHi = StepLen(hi) * stepK;
                int kf = Mathf.Max(0, Mathf.FloorToInt(uHi / Mathf.Max(0.05f, slHi)));
                planSteps = kf >= 1 && uHi - kf * slHi <= 0.05f ? kf : kf + 1;
                if (!Solvable(planSteps) && planSteps > 1 && Solvable(planSteps - 1)) planSteps--;
            }
            // 二分找速度：G 随速度增大（步子变大、停步接得更靠后）
            float a = lo, b = hi;
            if (G(planSteps, b) <= 0) planSpeed = b;
            else if (G(planSteps, a) >= 0) planSpeed = a;
            else
            {
                for (int i = 0; i < 14; i++) { float m = (a + b) * 0.5f; if (G(planSteps, m) < 0) a = m; else b = m; }
                planSpeed = (a + b) * 0.5f;
            }
        }

        /// 速度 s（米/秒）→ 各段步态的权重、播放快慢（1 = 原速）、混合后的周期
        void GaitWeights(float s)
        {
            Array.Clear(cw, 0, cw.Length);
            int n = Mathf.Min(gaitN, cw.Length);
            float v0 = Mathf.Max(0.05f, GaitSpeed(0)), vn = Mathf.Max(0.05f, GaitSpeed(n - 1));
            if (n == 1 || s <= v0) { cw[0] = 1; gaitRate = s / v0; gaitT = gait[0].length; return; }
            if (s >= vn) { cw[n - 1] = 1; gaitRate = s / vn; gaitT = gait[n - 1].length; return; }
            for (int i = 0; i < n - 1; i++)
            {
                float va = GaitSpeed(i), vb = GaitSpeed(i + 1);
                if (s < va || s > vb) continue;
                float la = gait[i].length, lb = gait[i + 1].length;
                // 混合后一个周期走的距离 / 周期 = s：解出权重（步幅、步频一起变，播放速度就是原速）
                float num = s * la - va * la, den = num + (vb * lb - s * lb);
                float b = den > 1e-5f ? Mathf.Clamp01(num / den) : 0;
                cw[i] = 1 - b;
                cw[i + 1] = b;
                gaitT = cw[i] * la + cw[i + 1] * lb;
                gaitRate = s / ((cw[i] * va * la + cw[i + 1] * vb * lb) / gaitT);
                return;
            }
            cw[0] = 1; gaitRate = s / v0; gaitT = gait[0].length;
        }

        /// 各段步态都跳到相位 ph（只在它们没混进去的时候调，跳的那一下不会带出位移）
        void SyncGait(float ph)
        {
            phase = Mathf.Repeat(ph, 1f);
            for (int i = 0; i < gaitN; i++) slots[gaitBase + i].SetTime(phase * gait[i].length);
        }

        /// 现在的相位（按第一段步态实际播到哪算）
        float GaitPhase() => gaitN > 0 ? Mathf.Repeat((float)slots[gaitBase].GetTime() / gait[0].length, 1f) : 0;

        /// 停步片段从 t 秒开始到站稳还要走多远（米，这个人的身材）
        float StopRemain(float t)
        {
            if (stopClip == null) return 0.3f;
            float total = stopClip.averageSpeed.magnitude * stopClip.length * ScaleK * stopFootScale;
            return total * (1 - DistFrac(t / stopClip.length));
        }

        float DistFrac(float u)
        {
            if (stopDist == null || stopDist.Length < 2) return Mathf.Clamp01(u * 1.6f);
            float x = Mathf.Clamp01(u) * (stopDist.Length - 1);
            int i = Mathf.Min((int)x, stopDist.Length - 2);
            return Mathf.Lerp(stopDist[i], stopDist[i + 1], x - i);
        }

        /// 停步片段在 t 秒时的速度（米/秒）
        float StopSpeedAt(float t)
        {
            if (stopClip == null) return 0.5f;
            float dt = 0.05f;
            return (StopRemain(t) - StopRemain(t + dt)) / dt;
        }

        /// 按现在的相位，停步该接哪一段、从第几秒接
        void StopEntry(float ph, out int slot, out float t)
        {
            bool second = ph >= 0.5f;
            slot = second ? Fresh(stopMSlot, stopMSlot2) : Fresh(stopSlot, stopSlot2);
            if (slot < 0) slot = Fresh(stopSlot, stopSlot2) >= 0 ? Fresh(stopSlot, stopSlot2) : Fresh(stopMSlot, stopMSlot2);
            float h = second ? ph - 0.5f : ph;
            t = h / 0.5f * stopEntry;
            // 按姿势配好的时刻（各段步态按现在的权重混）：快走时身子已经越过支撑脚更多，从停步片段里更靠后的一刻接
            if (stopMap != null && stopMap.Length == gaitN * 11 && gaitN > 0)
            {
                float x = Mathf.Clamp01(h / 0.5f) * 10f;
                int k = Mathf.Min((int)x, 9);
                float f = x - k, sum = 0, acc = 0;
                for (int i = 0; i < gaitN && i < cw.Length; i++)
                {
                    if (cw[i] <= 0) continue;
                    acc += cw[i] * Mathf.Lerp(stopMap[i * 11 + k], stopMap[i * 11 + k + 1], f);
                    sum += cw[i];
                }
                if (sum > 1e-3f) t = acc / sum;
            }
        }

        /// 同一段的两份里挑现在没在用（权重小）的那份
        int Fresh(int a, int b) => b < 0 ? a : a < 0 ? b : trW[a] <= trW[b] ? a : b;
        bool IsStopM(int s) => s >= 0 && (s == stopMSlot || s == stopMSlot2);
        bool IsStop(int s) => s >= 0 && (s == stopSlot || s == stopSlot2 || IsStopM(s));
        bool IsTurnMain(int s) => s >= 0 && (s == turnSlot || s == turnSlot2);

        void EnterStop()
        {
            GaitWeights(Mathf.Max(speedCmd, 0.01f));   // 各段权重按现在的速度（前面算步长时可能改过）
            float ph = GaitPhase();
            StopEntry(ph, out int s, out float t);
            if (s < 0) { loco = Loco.Idle; return; }
            stopNow = s;
            slots[s].SetTime(t);
            float v = Mathf.Max(0.05f, StopSpeedAt(t));
            stopRate0 = Mathf.Clamp(speedCmd / v, 0.85f, 1.4f);
            stopT0 = t;
            slots[s].SetSpeed(stopRate0);
            freshRoot = 2;
            loco = Loco.Stop;
            fadeTime = 0.18f;
            nextStep = NextStepAfter(stopSteps, t);
        }

        void EnterMove(float ph, float fade)
        {
            if (loco != Loco.Move) { SyncGait(ph); freshRoot = 2; }
            loco = Loco.Move;
            fadeTime = fade;
            lastPhase = planPh = phase;
            stanceYaw = 0;
            strikeValid = false;
            holdFoot = 0;
        }

        bool EnterTurn(float delta)
        {
            if (turnSlot < 0 && turnMSlot < 0) return false;
            // 片段本身往左转（turnLeft）。Unity 里往右转是角度增大
            bool wantLeft = delta < 0;
            int s = wantLeft == turnLeft ? Fresh(turnSlot, turnSlot2) : Fresh(turnMSlot, turnMSlot2);
            if (s < 0) return false;
            turnNow = s;
            // 片段里腿转了约 89 度：身子最多按原样转（再多就成了两脚踩着地原地像转盘一样转）。
            // 要转得更多（往回走）：转身起步只管前面这 100 度，剩下的在接下来的一两步里边走边转（真人掉头也是这样）
            // 转身起步最多转片段的 85%（掉头时 75%）：片段里转身那只脚是踮着脚掌转的，转得越多脚掌在地上拧得越多（按原样转 90 度要拧 85 度）。
            // 剩下的在接下来的一两步里边走边转（每步最多 55 度）
            turnScale = Mathf.Clamp(Mathf.Abs(delta) / Mathf.Max(30f, turnAngle), 0.55f, Mathf.Abs(delta) > 120f ? 0.75f : 0.85f);
            slots[s].SetTime(0);
            slots[s].SetSpeed(1.08f);
            loco = Loco.Turn;
            freshRoot = 2;
            fadeTime = 0.2f;
            nextStep = NextStepAfter(turnSteps, 0);
            return true;
        }

        int nextStep;
        float lastPhase;
        static int NextStepAfter(float[] steps, float t)
        {
            if (steps == null) return 0;
            int i = 0;
            while (i < steps.Length && steps[i] < t + 0.02f) i++;
            return i;
        }

        /// 动画算好的这一帧位移（FolkRootMotion 转过来）
        public void OnRootMotion()
        {
            if (!useRoot || animator == null) return;
            rootFrame = Time.frameCount;
            Vector3 d = animator.deltaPosition * FootScaleNow();
            d.y = 0;
            // 某段刚混进来的那一帧，Unity 会按它上次播到的地方算位移，偶尔一下跳很远：限住
            float vmax = loco == Loco.Move ? (firstStep > 0 ? speedCmd * 1.15f + 0.05f : Mathf.Max(speedCmd, 0.3f) * 1.6f) : 1.3f;
            d = Vector3.ClampMagnitude(d, vmax * Mathf.Max(Time.deltaTime, 1e-4f));
            // 刚换段的头两帧，Unity 可能按那段上次播到的地方算位移、转角（一下跳很远）：这两帧按速度估
            if (freshRoot > 0)
            {
                freshRoot--;
                float v = loco == Loco.Move ? speedCmd : loco == Loco.Stop && stopNow >= 0 ? StopSpeedAt((float)slots[stopNow].GetTime()) : loco == Loco.Turn ? 0.2f : 0;
                d = transform.forward * v * Time.deltaTime;
            }
            else if (loco == Loco.Turn && turnNow >= 0)
            {
                float dy = Mathf.DeltaAngle(0, animator.deltaRotation.eulerAngles.y) * turnScale;
                dy = Mathf.Clamp(dy, -400f * Time.deltaTime, 400f * Time.deltaTime);
                RotateAbout(dy);
                // 转身那一侧的脚（片段里踮着脚掌转的那只）在开头这一下少跟着转四成：髋往里转吃掉一部分，脚掌在地上拧得少一些
                bool pivotLeft = IsTurnMain(turnNow) ? turnLeft : !turnLeft;
                if (slots[turnNow].GetTime() < 0.8f) { if (pivotLeft) lockYawL -= dy * 0.4f; else lockYawR -= dy * 0.4f; }
            }
            // 站着（原地转身的小碎步）、坐着、做动作时不挪
            if (loco == Loco.Idle || InTransition) d = Vector3.zero;
            float dt = Time.deltaTime;
            corrDisp = correction * dt;
            ApplyMove(d + corrDisp + pivotMove);
            pivotMove = Vector3.zero;
        }

        /// 转身：绕着踩在地上的那只脚转（两只脚都在地上就绕两脚中间），这只脚就不会在地上拧着滑。
        /// 站着原地转（小碎步）绕人自己的原点转：不然转一大圈人会挪开十几厘米，站不准在蒲团、拜垫上
        void RotateAbout(float dyaw, bool aboutFoot = true)
        {
            if (Mathf.Abs(dyaw) < 1e-4f) return;
            Vector3 pos = transform.position;
            Vector3 pivot = pos;
            if (aboutFoot && lFoot != null && wGait + wStop + wTurn > 0.3f)
            {
                Vector3 l = lFoot.position, r = rFoot.position;
                float dl = l.y - pos.y, dr = r.y - pos.y;
                pivot = Mathf.Abs(dl - dr) < 0.025f ? (l + r) * 0.5f : dl < dr ? l : r;
                pivotFoot = Mathf.Abs(dl - dr) < 0.025f ? 3 : dl < dr ? 1 : 2;
                pivot.y = pos.y;
                if ((pivot - pos).sqrMagnitude > 0.36f) { pivot = pos; pivotFoot = 0; }
                // 走路转弯：踩着的脚少跟着转一半（见 lockYawL）
                if (loco == Loco.Move)
                {
                    if (pivotFoot == 1 || pivotFoot == 3) lockYawL -= dyaw * (pivotFoot == 3 ? 0.25f : 0.5f);
                    if (pivotFoot == 2 || pivotFoot == 3) lockYawR -= dyaw * (pivotFoot == 3 ? 0.25f : 0.5f);
                }
            }
            transform.rotation = Quaternion.Euler(0, transform.eulerAngles.y + dyaw, 0);
            Vector3 np = pivot + Quaternion.Euler(0, dyaw, 0) * (pos - pivot);
            pivotMove += new Vector3(np.x - pos.x, 0, np.z - pos.z);
        }

        /// 把人挪 h（水平），高度跟地面（有碰撞胶囊的用胶囊挪）
        void ApplyMove(Vector3 h)
        {
            float dt = Time.deltaTime;
            var moverT = controller != null ? controller.transform : transform;
            Vector3 before = moverT.position;
            if (controller != null && controller.enabled)
            {
                Vector3 want = new Vector3(h.x, 0, h.z);
                // 正对着圆柱子（柱础、金柱）推：胶囊顶在柱子正中，往哪边都不滑，人原地踏步。往人偏的那一边拐开 50 度，贴着柱子绕过去
                Vector3 round = AroundRound(moverT.position, want);
                h.x = round.x;
                h.z = round.z;
                h.y = -2f * dt;
                controller.Move(h);
                // 被挡住了（撞墙、撞柱子）：实际挪的比想挪的少很多。贴着圆柱子往旁边滑过去（往前的分量小、横着挪得不少）不算挡住：
                // 以前只看往前挪了多少，从侧门一直往北推、蹭着金柱的柱础绕过去时被当成撞墙，人就停下了（换个方向推才走）
                Vector3 got = moverT.position - before;
                got.y = 0;
                if (want.magnitude > 0.004f)
                {
                    // 滑着走（实际挪的方向和想走的方向差不到 80 度）按挪了多少算；卡在墙角里（几乎不挪）、被顶回来照旧算挡住。
                    // 不按速度卡门槛：一挡住腿就放慢（下面的 blockK），滑得慢了又被当成挡住，越滑越慢，最后停在柱础的斜面上
                    float k = Vector3.Dot(got, want.normalized) / want.magnitude;
                    if (got.sqrMagnitude > 1e-10f && Vector3.Dot(got.normalized, want.normalized) > 0.17f) k = Mathf.Max(k, got.magnitude / want.magnitude);
                    blockK = Mathf.Lerp(blockK, Mathf.Clamp01(k), 1 - Mathf.Exp(-8f * dt));
                }
            }
            else
            {
                // 没有碰撞胶囊（香客，或者自己在自动走路线）：水平移动，高度贴着脚下的地面、台阶、蒲团
                Vector3 pos = moverT.position + new Vector3(h.x, 0, h.z);
                if (pose == Pose.None) pos += Separation(pos);
                // 不穿墙、不穿栏杆（没有碰撞胶囊的人以前只按路线走，被别人挤一下、拐弯切一下就能从石台的栏杆、门柱里穿过去）
                if (pose == Pose.None) pos = KeepOutOfSolids(moverT.position, pos);
                // 坐着、跪着的时候不跟着地面走（坐下时原点就放在蒲团下面的地上，草垫的碰撞会把人顶高）
                var ramp = groundFollow && pose == Pose.None ? RampAt(pos) : null;
                // 台阶：贴着斜坡走（一级一级的高低由 GroundIK 让脚去踩）
                if (ramp != null) pos.y = Mathf.MoveTowards(pos.y, ramp.HeightAt(pos), 3f * dt);
                else if (groundFollow && pose == Pose.None && Physics.Raycast(pos + Vector3.up * 0.8f, Vector3.down, out var hit, 2.5f, ~(1 << 2), QueryTriggerInteraction.Ignore))
                {
                    // 拜垫、蒲团前的草垫这些（StepZones）：慢慢抬上去、慢慢落下来，脚由 GroundIK 踩到垫子面上（以前一帧蹿上去 12 厘米，先落下的那只脚插进垫子里）。
                    // 别处：上台阶一下就上去，下台阶慢一点落下
                    bool soft = InStepZone(pos);
                    pos.y = hit.point.y > pos.y ? Mathf.MoveTowards(pos.y, hit.point.y, soft ? 0.9f * dt : 6f * dt + 0.02f)
                                                : Mathf.MoveTowards(pos.y, hit.point.y, soft ? 0.9f * dt : 2.5f * dt);
                }
                moverT.position = pos;
            }
            Vector3 moved = moverT.position - before;
            moved.y = 0;
            velocity = dt > 1e-5f ? moved / dt : Vector3.zero;
            lastMove = moved;
            lastPos = transform.position;
        }

        /// 有碰撞胶囊的人（摇杆走的自己）这一步正对着一根竖着的圆柱（CapsuleCollider：殿里金柱的柱础、廊下的柱子）：
        /// 碰到的地方的法线和要走的方向差不到 25 度，就把这一步往人偏离柱子中线的那一边转 50 度（正好在中线上就往右），贴着柱子绕过去。
        /// 真人推着摇杆顶到柱子会自己偏一点；测试里、手指没偏的时候人就一直顶在柱子正中原地踏步（HallWalkTest.SideDoors 东门 x 3.0）
        static readonly RaycastHit[] roundHits = new RaycastHit[4];
        Vector3 AroundRound(Vector3 pos, Vector3 want)
        {
            float len = want.magnitude;
            if (len < 1e-5f || controller == null) return want;
            Vector3 dir = want / len;
            Vector3 c = pos + controller.center;
            float half = Mathf.Max(0f, controller.height * 0.5f - controller.radius);
            int n = Physics.CapsuleCastNonAlloc(c + Vector3.up * half, c - Vector3.up * (half - 0.25f), controller.radius * 0.95f, dir, roundHits, len + 0.06f, SolidMask, QueryTriggerInteraction.Ignore);
            for (int i = 0; i < n; i++)
            {
                var hc = roundHits[i].collider as CapsuleCollider;
                if (hc == null || hc.direction != 1 || hc.transform.IsChildOf(transform) || roundHits[i].distance <= 0f) continue;
                Vector3 nrm = roundHits[i].normal;
                nrm.y = 0;
                if (nrm.sqrMagnitude < 1e-6f || Vector3.Dot(-nrm.normalized, dir) < 0.9f) continue;
                Vector3 axis = hc.transform.TransformPoint(hc.center) - pos;
                axis.y = 0;
                float side = Vector3.Cross(dir, axis).y;      // 柱子在人前进方向的右边是正的：人往左拐
                float turn = side > 0.005f ? -50f : 50f;
                return Quaternion.Euler(0, turn, 0) * want;
            }
            return want;
        }

        Vector3 lastMove;
        float blockK = 1, blockT, blockYaw;
        bool blocked;

        /// 每帧：定走路的状态、速度、朝向，给各段动画分权重
        void Locomote(float dt)
        {
            if (gaitN == 0 || dt <= 0) return;
            if (firstStep > 0) firstStep -= dt;
            // 被外面直接挪了位置（传送、坐下）：走路状态清零
            if ((transform.position - lastPos).sqrMagnitude > 1f) ResetLoco();
            bool blocked = InTransition || (actW > 0.5f && !Standing(actNow)) || pose == Pose.CrossLegged || pose == Pose.Bench
                           || pose == Pose.Kneel || pose == Pose.KneelBow;
            // 路线：算想往哪走
            float remain = 0;
            bool lastLeg = false;
            yieldK = 1;
            if (path.Count > 0) desired = SteerPath(out remain, out lastLeg);
            Vector3 want = blocked ? Vector3.zero : desired;
            float sd = want.magnitude;
            bool go = sd > 0.12f * walkSpeed;
            // 要走了，手上还合着掌、拿着香：交给手臂那层慢慢放下，腿马上走
            if (go && actNow != null && Standing(actNow) && actW > 0.01f) HandOffToArms();
            float cur = transform.eulerAngles.y;
            // 按路线走时，朝向的「目标」跟着人走（到了以后由 FaceTowards 再定）
            if (path.Count > 0 && loco != Loco.Idle) { faceYaw = cur; hasFace = true; }
            float target = go ? Quaternion.LookRotation(want).eulerAngles.y : hasFace ? faceYaw : cur;
            float err = Mathf.DeltaAngle(cur, target);
            phase = GaitPhase();

            switch (loco)
            {
                case Loco.Idle:
                    if (path.Count > 0 && remain < 0.03f) { Arrive(); break; }
                    if (go && path.Count > 0 && remain < 0.45f)
                    {
                        // 很近（半步）：不迈正步，小碎步挪过去。在侧后方的先原地转过来再挪（不倒着、不横着蹭）；
                        // 走过头一点点（在身后 0.2 米内）就算到了
                        Vector3 to = path[path.Count - 1] - transform.position;
                        to.y = 0;
                        float m0 = to.magnitude;
                        if (m0 < 0.04f) { Arrive(); break; }
                        float off = Vector3.Angle(transform.forward, to);
                        if (off > 100f && m0 < 0.2f) { Arrive(); break; }
                        if (off > 45f) { IdleTurn(err, dt); break; }
                        shuffle = Mathf.MoveTowards(shuffle, 0.45f, dt / 0.2f);
                        float m = Mathf.Min(m0, 0.35f * dt * Mathf.Cos(off * Mathf.Deg2Rad));
                        pivotMove += to.normalized * m;
                        float rot = Mathf.Clamp(err * 3f, -90f, 90f) * dt;
                        RotateAbout(rot, false);
                        ShuffleSteps(m * 360f + Mathf.Abs(rot), dt);
                        break;
                    }
                    if (go && blocked && path.Count == 0 && Mathf.Abs(Mathf.DeltaAngle(target, blockYaw)) < 30f) go = false;
                    else blocked = false;
                    if (go)
                    {
                        speedCmd = 0;
                        if (Mathf.Abs(err) > 50f)
                        {
                            // 要转过头去：远的播转身起步，近的（转身起步那一下就过头了）先原地转过来
                            if ((path.Count == 0 || remain > 1.2f) && EnterTurn(err)) break;
                            if (path.Count > 0) { IdleTurn(err, dt); break; }
                        }
                        // 起步：从右脚往前迈的那一刻开始（或者左脚，看上次停在哪只脚）
                        EnterMove(startPhase, 0.14f);
                        holdFoot = startPhase < 0.5f ? 1 : 2;
                        firstStep = 0.6f;
                        break;
                    }
                    // 站着：慢慢转向要看的方向，转得多就迈小碎步
                    IdleTurn(err, dt);
                    break;

                case Loco.Move:
                {
                    // 这一帧有没有一只脚落地（相位走过 0 或 0.5）
                    bool strikeNow = (planPh < 0.5f && phase >= 0.5f) || (planPh > 0.75f && phase < 0.25f);
                    if (strikeNow)
                    {
                        stanceYaw = 0;
                        // 量一下真走的一步比按速度算的长多少（stepK），快到终点时按它定步数、快慢
                        Vector3 dd = transform.position - strikePos; dd.y = 0;
                        if (strikeValid && firstStep <= 0 && strikeCmd > 0.15f) stepK = Mathf.Lerp(stepK, Mathf.Clamp(dd.magnitude / strikeCmd, 0.8f, 1.2f), 0.5f);
                        strikePos = transform.position; strikeCmd = 0; strikeValid = true;
                    }
                    strikeCmd += speedCmd * dt;
                    // 急转弯先放慢
                    float slow = Mathf.Lerp(1f, 0.55f, Mathf.InverseLerp(30f, 150f, Mathf.Abs(err)));
                    // 推得很轻：按最慢那段步子走（播放速度不低于 0.92，不像慢镜头）；给别人让路时可以再慢些
                    float floor = MinWalk * (yieldK < 0.95f ? 0.7f : 0.92f);
                    float st = go ? Mathf.Max(sd, floor) * slow : 0;
                    if (!go)
                    {
                        EnterStop();
                        break;
                    }
                    // 一直被挡着走不动：停下来站着，换个方向推才再走（不在墙前原地踏步）
                    blockT = blockK < 0.35f ? blockT + dt : 0;
                    if (blockT > 0.35f) { blockYaw = target; blocked = true; blockK = 1; blockT = 0; EnterStop(); break; }
                    // 按路线走、快到终点：停步只能从某一步接进去（一步一个落点），停下来的地方是一格一格的。
                    // u：现在就停，停下来离终点还差多远（正的是没走到）。再走一步 u 就少一步长：u 不到半步时现在停最准。
                    // 离终点 3 米内：进来时定好还要迈几步（planSteps，宁可多一步、步子小一点也不赶），之后每落一次脚才重算一次这一步迈多大，
                    // 速度只在 0.8–1.05 倍 walkSpeed 之间、慢慢变（不是每帧四舍五入步数：那样步数一跳，速度就在 0.86 和 1.25 之间来回抢）。
                    // 剩下的几厘米在停步的最后一步落地前补上
                    bool planning = false;
                    if (lastLeg && path.Count > 0 && stopClip == null && remain < 0.05f) { loco = Loco.Idle; Arrive(); break; }
                    if (lastLeg && path.Count > 0 && stopClip != null)
                    {
                        StopEntry(phase, out _, out float et);
                        float u = remain - StopRemain(et);
                        float sl = StepLen(Mathf.Max(speedCmd, MinWalk));
                        if (u <= 0.5f * sl + speedCmd * dt)
                        {
                            arriving = true;
                            planSteps = 0;
                            EnterStop();
                            break;
                        }
                        if (remain < 4f && yieldK > 0.95f)
                        {
                            planning = true;
                            // 快到终点：按「再迈 k 步、然后停步」正好停在终点来定这几步的快慢（每落一次脚才重算，见 PlanApproach）。
                            // 最快只按最快那段步态的原速走：再快多出来的只是步频，步子不会更大，停的地方就调不动了（人走近目标时本来也会放慢一点）
                            float lo = Mathf.Max(floor, walkSpeed * 0.7f);
                            float hi = Mathf.Max(lo, Mathf.Min(Mathf.Max(sd, floor), Mathf.Min(walkSpeed * 1.05f, GaitSpeed(gaitN - 1))));
                            if (planSteps <= 0 || strikeNow) PlanApproach(remain, lo, hi, strikeNow && planSteps > 0);
                            st = planSpeed * slow;
                        }
                    }
                    if (!planning) planSteps = 0;
                    planPh = phase;
                    // 被挡着、贴着东西蹭过去：腿跟着放慢
                    if (blockK < 0.8f) st = Mathf.Min(st, Mathf.Max(MinWalk * 0.8f, blockK * speedCmd));
                    // 快到终点时速度变得很慢（0.5 米/秒²），只有刚起步、还远没到要的速度时照常加速
                    float acc = planning && speedCmd > 0.75f * st ? 0.5f : st > speedCmd ? 1.8f : 2.4f;
                    speedCmd = Mathf.MoveTowards(speedCmd, st, acc * dt);
                    float maxRate = Mathf.Lerp(320f, 210f, Mathf.InverseLerp(0.4f, 1.2f, speedCmd));
                    float wantRate = Mathf.Clamp(err * 5f, -maxRate, maxRate);
                    yawVel = Mathf.MoveTowards(yawVel, wantRate, 1500f * dt);
                    float d = yawVel * dt;
                    if (Mathf.Abs(d) > Mathf.Abs(err)) { d = err; yawVel = err / dt * 0.5f; }
                    // 一只脚踩在地上的这一步里最多转 55 度（绕这只脚转，脚掌在地上拧着转；再多就像单脚原地打转）。
                    // 掉头（180 度）就分两三步转过去，每一步迈出去的脚已经朝着新的方向
                    float cap = StanceYawCap;
                    if (Mathf.Abs(stanceYaw + d) > cap) { d = Mathf.Clamp(stanceYaw + d, -cap, cap) - stanceYaw; yawVel = d / dt; }
                    stanceYaw += d;
                    RotateAbout(d);
                    break;
                }

                case Loco.Stop:
                {
                    if (stopNow < 0) { loco = Loco.Idle; break; }
                    float t = (float)slots[stopNow].GetTime();
                    // 进停步时的快慢慢慢回到原速
                    slots[stopNow].SetSpeed(Mathf.Lerp(stopRate0, 1f, Mathf.InverseLerp(stopT0, stopT0 + 0.5f, t)));
                    if (go && !arriving)
                    {
                        // 停到一半又要走：还在前半步里就接回步态，否则从站姿重新起步
                        if (t < stopEntry) { float ph = t / stopEntry * 0.5f + (IsStopM(stopNow) ? 0.5f : 0); loco = Loco.Idle; EnterMove(ph, 0.2f); speedCmd = Mathf.Max(speedCmd * 0.8f, StopSpeedAt(t)); }
                        else if (t > stopStill - 0.4f) { loco = Loco.Idle; EnterMove(IsStopM(stopNow) ? StartPhaseB : StartPhaseA, 0.16f); speedCmd = 0; firstStep = 0.6f; holdFoot = IsStopM(stopNow) ? 2 : 1; }
                        break;
                    }
                    // 按路线停：终点和片段会停到的地方差一点，在最后一只脚落地之前补上（这时总有一只脚在空中，挪的是迈出去的那步）；
                    // 两只脚都踩稳以后只剩很慢的一点点（≤ 4 厘米/秒，差 2 厘米以内不管）
                    correction = Vector3.zero;
                    if (arriving && path.Count > 0)
                    {
                        Vector3 end = transform.position + transform.forward * StopRemain(t);
                        Vector3 e = path[path.Count - 1] - end;
                        e.y = 0;
                        float tPlant = stopSteps != null && stopSteps.Length > 0 ? stopSteps[stopSteps.Length - 1] : stopStill - 0.4f;
                        float left = tPlant - t;
                        if (left > 0.12f) correction = Vector3.ClampMagnitude(e / left, 0.4f);
                        else correction = e.magnitude > 0.02f ? Vector3.ClampMagnitude(e, 0.04f) : Vector3.zero;
                        // 不往后滑：往回补最多抵掉片段往前走的速度的八成
                        float vf = StopSpeedAt(t) * (float)slots[stopNow].GetSpeed();
                        float cf = Vector3.Dot(correction, transform.forward);
                        if (cf < -0.8f * vf) correction -= transform.forward * (cf + 0.8f * vf);
                    }
                    if (Mathf.Abs(err) < 30f && go && (!arriving || remain > 0.6f))
                    {
                        float d = Mathf.Clamp(err * 3f, -60f, 60f) * dt;
                        RotateAbout(d);
                    }
                    if (t >= stopStill - 0.3f) { fadeTime = 0.4f; }
                    if (t >= stopStill)
                    {
                        loco = Loco.Idle;
                        startPhase = IsStopM(stopNow) ? StartPhaseB : StartPhaseA;
                        stopNow = -1;
                        speedCmd = 0;
                        correction = Vector3.zero;
                        // 停下来离终点还差几厘米：小碎步挪过去（下面 Idle 里），差得很少就算到了
                        if (arriving)
                        {
                            arriving = false;
                            if (path.Count == 0 || remain < 0.05f) Arrive();
                        }
                    }
                    break;
                }

                case Loco.Turn:
                {
                    if (turnNow < 0) { loco = Loco.Idle; break; }
                    var c = IsTurnMain(turnNow) ? turnClip : turnMirrorClip;
                    float t = (float)slots[turnNow].GetTime();
                    if (t >= c.length - 0.15f)
                    {
                        // 转身那一步落地：接进步态
                        float ph = IsTurnMain(turnNow) ? turnExitPhase : turnExitPhase + 0.5f;
                        speedCmd = MinWalk * 0.9f;
                        // 转身最后那一步落地（片段播完前就交出去了）
                        if (turnSteps != null && nextStep < turnSteps.Length) { nextStep = turnSteps.Length; Step?.Invoke(); }
                        loco = Loco.Idle;
                        EnterMove(ph, 0.15f);
                        turnNow = -1;
                    }
                    break;
                }
            }

            // 步态：按速度分权重、定快慢，各段同相位
            GaitWeights(Mathf.Max(speedCmd, 0.01f));
            // 进停步时步态还在淡出（0.18 秒）：它接着按原来的快慢往前播，不停在那一帧（不然迈着的那只脚在半空一顿，脚一跳）
            float rate = loco == Loco.Move || (loco == Loco.Stop && wGait > 0.001f) ? gaitRate : 0;
            if (loco == Loco.Idle && shuffle > 0.001f) rate = shuffleRate;
            for (int i = 0; i < gaitN; i++) slots[gaitBase + i].SetSpeed(gait[i].length * rate / gaitT);
            // 各块的权重
            float tg = loco == Loco.Move ? 1 : loco == Loco.Idle ? shuffle : 0;
            float k = dt / Mathf.Max(0.05f, fadeTime);
            wGait = Mathf.MoveTowards(wGait, tg, k);
            wStop = wTurn = 0;
            foreach (int s in trSlots)
            {
                bool on = (loco == Loco.Stop && s == stopNow && slots[s].GetTime() < stopStill - 0.3f) || (loco == Loco.Turn && s == turnNow);
                trW[s] = Mathf.MoveTowards(trW[s], on ? 1 : 0, k);
                if (IsStop(s)) wStop += trW[s]; else wTurn += trW[s];
                if (trW[s] <= 0f && s != stopNow && s != turnNow) slots[s].SetSpeed(0);
            }
            float other = wGait + wStop + wTurn;
            if (other > 1)
            {
                wGait /= other; wStop /= other; wTurn /= other;
                foreach (int s in trSlots) trW[s] /= other;
                other = 1;
            }
            wIdle = 1 - other;

            // 脚步声：步态走过 0 和 0.5；停步、转身按片段里的着地时刻
            if (loco == Loco.Move && wGait > 0.4f)
            {
                float p0 = lastPhase, p1 = GaitPhase();
                if ((p0 > 0.8f && p1 < 0.2f) || (p0 < 0.5f && p1 >= 0.5f)) Step?.Invoke();
                lastPhase = p1;
            }
            else lastPhase = GaitPhase();
            if (loco == Loco.Stop && stopNow >= 0 && stopSteps != null && nextStep < stopSteps.Length && slots[stopNow].GetTime() >= stopSteps[nextStep]) { nextStep++; Step?.Invoke(); }
            if (loco == Loco.Turn && turnNow >= 0 && turnSteps != null && nextStep < turnSteps.Length && slots[turnNow].GetTime() >= turnSteps[nextStep]) { nextStep++; Step?.Invoke(); }

            // 往弯里倾、头先看过去
            float spd = loco == Loco.Move ? speedCmd : 0;
            lean = Mathf.Lerp(lean, Mathf.Clamp(yawVel * spd * 0.035f, -7f, 7f), 1 - Mathf.Exp(-6f * dt));
            headLook = Mathf.Lerp(headLook, Mathf.Clamp(yawVel * 0.12f, -22f, 22f), 1 - Mathf.Exp(-5f * dt));
        }

        /// 从站着起步时步态从哪个相位淡进来：右脚已经离地、正从身子底下往前送，左脚在身子底下（0.29；左脚先迈是 0.79）。
        /// 再早（0.23）右脚还在身后，淡入的 0.14 秒里那只脚会先往后、往里蹭 7 厘米再往前迈（起步时往后一踢）。
        /// 淡入只要 0.14 秒（淡得慢的话，半抬的脚贴着地面往前蹭）
        const float StartPhaseA = 0.29f, StartPhaseB = 0.79f;
        float startPhase = StartPhaseA;
        float firstStep;             // 起步的第一步还剩多久：这段时间里根运动不超过要的速度（不往前冲）
        float shuffleRate;

        /// 站着转向 err 度（带角速度上限，转得多就迈小碎步）
        void IdleTurn(float err, float dt)
        {
            if (Mathf.Abs(err) > 1.5f)
            {
                float maxR = 150f;
                float wantR = Mathf.Clamp(err * 4f, -maxR, maxR);
                yawVel = Mathf.MoveTowards(yawVel, wantR, 900f * dt);
                float dy = yawVel * dt;
                if (Mathf.Abs(dy) > Mathf.Abs(err)) { dy = err; yawVel = 0; }
                RotateAbout(dy, false);
                // 坐着、跪着、做着动作时只转身子，腿不迈步
                if ((pose == Pose.None || holding) && actW < 0.3f) ShuffleSteps(Mathf.Abs(dy), dt);
                else shuffle = Mathf.MoveTowards(shuffle, 0, dt / 0.2f);
            }
            else { yawVel = 0; shuffle = Mathf.MoveTowards(shuffle, 0, dt / 0.3f); }
        }

        /// 原地转 deg 度：腿迈小碎步（步态以小权重混进来，转 180 度走一个周期）
        void ShuffleSteps(float deg, float dt)
        {
            shuffle = Mathf.MoveTowards(shuffle, 0.4f, dt / 0.2f);
            float T = gaitN > 0 ? gait[0].length : 1f;
            shuffleRate = deg / 180f / Mathf.Max(dt, 1e-4f) * T;
            if (lastPhase < 0.5f && GaitPhase() >= 0.5f || lastPhase > 0.8f && GaitPhase() < 0.2f) Step?.Invoke();
        }

        void ResetLoco()
        {
            loco = Loco.Idle;
            speedCmd = 0;
            wGait = wStop = wTurn = shuffle = 0;
            wIdle = 1;
            stopNow = turnNow = -1;
            if (trW != null) Array.Clear(trW, 0, trW.Length);
            yawVel = lean = headLook = 0;
            correction = pivotMove = Vector3.zero;
            arriving = false;
            planSteps = 0;
            lockYawL = lockYawR = 0;
            holdFoot = 0;
            firstStep = 0;
            lastPos = transform.position;
        }

        /// 就算到了（总控用：终点被人占着、挤不过去，离终点已经很近又半天没走近一点，或者走得太久了）。
        /// 路线清掉、发 Arrived；人这一步走完自然停下（停步动作照播）
        public void ArriveNow() => Arrive();

        void Arrive()
        {
            arriving = false;
            path.Clear();
            desired = Vector3.zero;
            velocity = Vector3.zero;
            Arrived?.Invoke();
        }

        /// 按路线走：往前面一点的路线上的点（拐角处提前转，走成圆弧）走；前面有人往右让
        Vector3 SteerPath(out float remain, out bool lastLeg)
        {
            Vector3 me = transform.position;
            me.y = 0;
            // 已经走过的点去掉（离得很近，或者已经在它前面了）。「在它前面」只在人就在这一段旁边（0.5 米内）时算：
            // 人站在路线的一侧、离得远（例如站在台阶垂带和台基之间的角里，路线先往南绕出去再往东），按投影算会把前两个点都当成走过了，
            // 人直奔第三个点，一头扎进角里出不来（复核、HallCrowdTest 里都见过，三次重新找路还是同一个方向）
            while (path.Count > 1)
            {
                Vector3 a = path[0], b = path[1];
                a.y = b.y = 0;
                Vector3 seg = b - a;
                bool passed = (a - me).magnitude < 0.45f;
                if (!passed && seg.sqrMagnitude > 1e-4f && Vector3.Dot(me - a, seg) > 0)
                {
                    float t = Mathf.Clamp01(Vector3.Dot(me - a, seg) / seg.sqrMagnitude);
                    passed = (me - (a + seg * t)).magnitude < 0.5f;
                }
                if (!passed) break;
                path.RemoveAt(0);
            }
            lastLeg = path.Count == 1;
            // 剩下多远
            Vector3 p = me;
            remain = 0;
            foreach (var w in path) { Vector3 q = new Vector3(w.x, 0, w.z); remain += (q - p).magnitude; p = q; }
            // 看前面多远的点
            // 看得太远拐角就切得多（座位区的走道窄，切角会踩到蒲团）：0.4–0.65 米，拐直角时离路线最多十几厘米
            float look = Mathf.Clamp(0.35f + 0.3f * speedCmd, 0.4f, 0.65f);
            Vector3 carrot = new Vector3(path[path.Count - 1].x, 0, path[path.Count - 1].z);
            p = me;
            float acc = 0;
            foreach (var w in path)
            {
                Vector3 q = new Vector3(w.x, 0, w.z);
                float l = (q - p).magnitude;
                if (acc + l >= look) { carrot = p + (q - p) * ((look - acc) / Mathf.Max(l, 1e-4f)); break; }
                acc += l;
                p = q;
            }
            Vector3 to = carrot - me;
            float dist = to.magnitude;
            if (dist < 1e-3f) return Vector3.zero;
            Vector3 dir = to / dist;
            // 避让：按两人现在的速度预判 2.5 秒内会不会走得太近（中心距小于约 0.6 米）。
            // 会的话往离他远的那一侧绕（正对面就各自往右）；交叉时他在我右前方、正朝我走过来，我放慢让他先过（迎面两人都慢一点）。
            // 已经很近了（0.75 米内）直接往外推。快到终点时让得轻一些（不然在终点前绕圈）
            Vector3 side = Vector3.Cross(Vector3.up, dir);
            Vector3 push = Vector3.zero;
            Vector3 myV = dir * Mathf.Max(speedCmd, 0.45f);
            float yieldNow = 1f;
            foreach (var o in All)
            {
                if (o == this || o == null || !o.isActiveAndEnabled) continue;
                Vector3 d = o.transform.position - transform.position;
                d.y = 0;
                float m = d.magnitude;
                if (m > 3f || m < 1e-3f) continue;
                if (Vector3.Dot(d, dir) < -0.2f && m > 0.5f) continue;          // 身后的不管
                bool walker = o.path.Count > 0 || o.loco != Loco.Idle || o.velocity.sqrMagnitude > 0.04f;
                float R = walker ? 0.62f : 0.5f;
                Vector3 ov = o.velocity;
                ov.y = 0;
                Vector3 rel = myV - ov;                                           // 我相对他的速度
                float rv2 = rel.sqrMagnitude;
                float tca = rv2 > 1e-4f ? Mathf.Clamp(Vector3.Dot(d, rel) / rv2, 0f, 2.5f) : 0f;
                Vector3 close = d - rel * tca;                                    // 离得最近时他在我哪边
                float dmin = close.magnitude;
                if (dmin < R)
                {
                    float urg = (1f - tca / 2.5f) * (1f - dmin / R);
                    float sd = Vector3.Dot(close, side);
                    float sign = Mathf.Abs(sd) < 0.08f ? 1f : -Mathf.Sign(sd);
                    push += side * sign * urg * 1.6f;
                    bool closing = Vector3.Dot(d, rel) > 0;
                    if (closing && walker && Vector3.Dot(d, side) > -0.15f)
                        yieldNow = Mathf.Min(yieldNow, Mathf.Lerp(1f, 0.35f, Mathf.Clamp01(urg * 2.5f)));
                }
                if (m < 0.75f) push -= d / m * (0.75f - m) / 0.75f * 1.2f;
            }
            float nearEnd = Mathf.Clamp01(remain / 0.8f);
            dir = (dir + push * Mathf.Lerp(0.35f, 1f, nearEnd)).normalized;
            yieldK = Mathf.Lerp(1f, yieldNow, Mathf.Lerp(0.5f, 1f, nearEnd));
            return dir * walkSpeed * yieldK;
        }

        float yieldK = 1;

        /// 最后一道保险：按路线走的人（没有碰撞胶囊）和别人中心距不到 0.45 米，就把自己往外挪开（对方也在走就各挪一半）
        Vector3 Separation(Vector3 pos)
        {
            Vector3 push = Vector3.zero;
            if (path.Count == 0 && loco == Loco.Idle) return push;
            foreach (var o in All)
            {
                if (o == this || o == null || !o.isActiveAndEnabled) continue;
                Vector3 d = pos - o.transform.position;
                d.y = 0;
                float m = d.magnitude;
                const float min = 0.45f;
                if (m >= min) continue;
                if (m < 1e-3f) d = -transform.forward * 1e-3f;
                bool oMoving = o.controller == null && (o.path.Count > 0 || o.loco != Loco.Idle);
                push += d.normalized * (min - m) * (oMoving ? 0.5f : 1f);
            }
            return Vector3.ClampMagnitude(push, 0.05f);
        }

        // ── 混合 ──

        /// 给各段动画分权重：sit 是坐着的程度（0..1，老的坐椅子）
        void Mix(float sit)
        {
            float stand = 1 - sit;
            float rest = 1 - Mathf.Clamp01(actW);
            float loco = rest * stand;
            // 待机：几段之间慢慢换（1.5 秒淡入淡出）
            float idleTotal = loco * wIdle;
            if (idleW != null && idleW.Length > 1)
            {
                float dt = Time.deltaTime;
                if (wIdle > 0.99f && actW < 0.01f && (idleNext -= dt) <= 0)
                {
                    int n = UnityEngine.Random.Range(0, idleW.Length - 1);
                    idleNow = n >= idleNow ? n + 1 : n;
                    idleNext = UnityEngine.Random.Range(15f, 40f);
                    slots[idleSlot[idleNow]].SetTime(UnityEngine.Random.value * 2f);
                }
                float sum = 0;
                for (int k = 0; k < idleW.Length; k++) { idleW[k] = Mathf.MoveTowards(idleW[k], k == idleNow ? 1 : 0, dt / 1.5f); sum += idleW[k]; }
                for (int k = 0; k < idleW.Length; k++) mixer.SetInputWeight(idleSlot[k], idleTotal * idleW[k] / Mathf.Max(sum, 1e-4f));
            }
            else mixer.SetInputWeight(0, idleTotal);
            for (int i = 0; i < gaitN; i++) mixer.SetInputWeight(gaitBase + i, loco * wGait * cw[i]);
            // 停步、转身各段（换走以后还在淡出的也按它自己的权重）
            foreach (int s in trSlots) mixer.SetInputWeight(s, loco * trW[s]);
            mixer.SetInputWeight(sitSlot, rest * sit);
        }

        void OnDestroy()
        {
            if (graph.IsValid()) graph.Destroy();
        }

        public void Init()
        {
            if (handler != null) return;
            if (animator == null) animator = GetComponentInChildren<Animator>();
            if (model == null) model = animator.transform;
            handler = new HumanPoseHandler(animator.avatar, animator.transform);
            BuildGraph();
            head = animator.GetBoneTransform(HumanBodyBones.Head);
            hips = animator.GetBoneTransform(HumanBodyBones.Hips);
            lFoot = animator.GetBoneTransform(HumanBodyBones.LeftFoot);
            rFoot = animator.GetBoneTransform(HumanBodyBones.RightFoot);
            lKnee = animator.GetBoneTransform(HumanBodyBones.LeftLowerLeg);
            rKnee = animator.GetBoneTransform(HumanBodyBones.RightLowerLeg);
            neck = animator.GetBoneTransform(HumanBodyBones.Neck);
            lThigh = animator.GetBoneTransform(HumanBodyBones.LeftUpperLeg);
            rThigh = animator.GetBoneTransform(HumanBodyBones.RightUpperLeg);
            lArm = animator.GetBoneTransform(HumanBodyBones.LeftUpperArm);
            rArm = animator.GetBoneTransform(HumanBodyBones.RightUpperArm);
            lHand = animator.GetBoneTransform(HumanBodyBones.LeftHand);
            rHand = animator.GetBoneTransform(HumanBodyBones.RightHand);
            lToe = animator.GetBoneTransform(HumanBodyBones.LeftToes);
            rToe = animator.GetBoneTransform(HumanBodyBones.RightToes);
            // 脚踝离地多高（骨骼还在初始姿势时量）：缩腿以后靠它把脚放回地面
            ankle = (Mathf.Min(lFoot.position.y, rFoot.position.y) - model.position.y) / Mathf.Max(transform.lossyScale.y, 0.001f);
            ApplyProportions();
            if (muscleByName.Count == 0)
                for (int i = 0; i < HumanTrait.MuscleCount; i++) muscleByName[HumanTrait.MuscleName[i]] = i;
            faceYaw = transform.eulerAngles.y;
            // 走路的位移用动画自己的（步态片段里带着根运动的才行；老的 Q 版动作没有，就按速度挪）
            useRoot = graph.IsValid() && gaitN > 0 && gait[0] != null && gait[0].averageSpeed.magnitude > 0.1f;
            if (useRoot && Application.isPlaying)
            {
                animator.applyRootMotion = true;
                var rm = animator.GetComponent<FolkRootMotion>() ?? animator.gameObject.AddComponent<FolkRootMotion>();
                rm.folk = this;
            }
            lastPos = transform.position;
        }

        public void SetName(string text, Color color)
        {
            if (nameTag == null) return;
            var tag = nameTag.GetComponent<NameTag>() ?? nameTag.gameObject.AddComponent<NameTag>();
            tag.Set(text, color);
            nameTag.gameObject.SetActive(!string.IsNullOrEmpty(text));
        }

        /// 换一个姿势。椅子上坐着（Bench）用动作库的坐姿动画，其余在站姿上叠加。
        public void SetPose(Pose p) => SetPose(p, false);

        /// instant：直接到位（一进场就已经坐着的人），不播起身、坐下的过程
        public void SetPose(Pose p, bool instant)
        {
            if (p == pose) return;
            var old = pose;
            pose = p;
            if (p != Pose.None) shown = p;
            if (p != Pose.None && !instant) { desired = Vector3.zero; if (loco == Loco.Move) EnterStop(); }
            if (UseActions) QueueFor(old, p, instant);
            // 站着做的动作（合掌、鞠躬、挂布条、上香）：人还没转到要朝的方向（差 20 度以上）、或者还在停步，就先等（见 UpdateActions），
            // 不边原地打转边拜。FaceTowards 在 SetPose 之前、之后调都行（下一帧才判断）
            holding = false;
            holdT = 0;
            // 跪下也一样：先转过来再跪（不然跪着的人像转盘一样原地转）
            faceHold = !instant && UseActions && actNow != null && actW < 0.3f && (p == Pose.Gassho || p == Pose.Bow || p == Pose.Hang || p == Pose.Incense
                                                                                    || p == Pose.Kneel || p == Pose.KneelBow);
        }

        /// 站着做的动作已经到位：在保持的那段上（Gassho_Loop、Bow_Scrub、Hang_Loop、Incense_Scrub……），而且完全混进来了。
        /// 上香时等它为 true 再开始 SetBow（或者至少等 IncenseReadyTime 秒）
        public bool ActionReady => !faceHold && actNow != null && actW > 0.95f && (actNow.EndsWith("_Loop") || actNow.EndsWith("_Scrub"));

        /// 系好布条，松手：播收手那段（Hang_Out），播完 OneShotDone 变成 true，人回到站姿
        public void ReleaseHang()
        {
            if (pose != Pose.Hang) return;
            OneShotDone = false;
            oneShot = "Hang_Out";
            SetPose(Pose.None);
            // Hang_In 还没播完时松手：Hang_Out 排在它后面，等 Hang_Out 真播完才算完
            if (actNow != "Hang_Out" && !actQueue.Contains("Hang_Out")) { oneShot = null; OneShotDone = true; }
        }

        /// 现在的姿势上插播一段（比如上香时 PlayOnce("Incense_Plant")）。播完 OneShotDone 变成 true（同时发 OneShotFinished），
        /// 然后回到这个姿势的保持动作。Incense_Plant 播完人是空手合掌（pose 变成 Gassho）。
        public void PlayOnce(string clip)
        {
            if (!Has(clip)) { OneShotDone = true; OneShotFinished?.Invoke(); return; }
            OneShotDone = false;
            oneShot = clip;
            actQueue.Clear();
            actQueue.Enqueue(clip);
            string hold = pose == Pose.Incense ? "Incense_Scrub" : pose == Pose.Hang ? "Hang_Loop" : pose == Pose.Gassho ? "Gassho_Loop" : null;
            if (hold != null && clip != "Incense_Plant") actQueue.Enqueue(hold);
            Next(false);
            actTarget = 1;
        }

        /// Incense_Plant 开始后多少秒香插进香炉：1.25 秒时两手停在灰面上方（人前方 0.49 米、离地 1.05 米），到这一刻往下按到离地 1.01 米
        /// （按 1.25 米高的人；灰面离地 0.962 米时手腕在灰面上方约 5 厘米），然后松手。见 pray_motions.py 的 INCENSE_PLANT_T、PLANT_DOWN
        public const float IncensePlantTime = 1.5f;
        /// Hang_In 播完（约 1.5 秒）两手在绳前：人前方约 0.40 米、离地约 1.05 米；ReleaseHang 后 Hang_Out 约 1.4 秒
        public const float HangReachTime = 1.5f;
        /// SetPose(Incense) 以后香举到额前、可以开始拜的时刻（Incense_In 的长度；人要先转过来的话更晚，以 ActionReady 为准）
        public const float IncenseReadyTime = 1.7f;

        /// 手（人形骨骼里的手腕）：挂布条、拿香时把东西挂在这里
        public Transform Hand(bool right) => right ? rHand : lHand;

        /// 坐下前站在圆蒲团前面多远（米，按 1.25 米高的人；见 tools/blender/pray_motions.py 的 STAND_Y × 0.806）
        public const float SeatStep = 0.315f;

        /// 坐下、起身、跪下这些过渡动作正在播：这时人不挪地方（不然脚在地上滑）
        public bool InTransition => actNow != null && actW > 0.5f && (actNow.EndsWith("_Up") || actNow.EndsWith("_Down"));

        /// 坐到蒲团上：人站在蒲团前面的草垫上，面朝 yaw。坐下那段动作播的时候，人一边蹲一边往后挪到蒲团上（挪的节奏跟着动作），
        /// 起身时反过来挪回草垫上
        public void SitOn(Vector3 seatGround, float yaw)
        {
            path.Clear();
            velocity = Vector3.zero;
            desired = Vector3.zero;
            var mover = controller != null ? controller.transform : transform;
            if (controller != null) controller.enabled = false;
            sitFrom = new Vector3(mover.position.x, seatGround.y, mover.position.z);
            sitTo = seatGround;
            sitGlide = GlideMode;
            if (!GlideMode) mover.position = seatGround;
            transform.rotation = Quaternion.Euler(0, yaw, 0);
            faceYaw = yaw;
            hasFace = true;
            ResetLoco();
            SetPose(Pose.CrossLegged);
            // 原点刚挪到蒲团下：坐下那段的第一帧身子正好在前面草垫上，直接换过去不淡入（淡入的那 0.25 秒身子会先缩回蒲团上再走出来）
            if (!GlideMode && actNow != null && actIndex.TryGetValue(actNow, out int i))
            {
                actW = 1;
                for (int j = 0; j < actWeight.Length; j++) actWeight[j] = j == i - actBase ? 1 : 0;
                // 这一帧就把姿势换过去（不等下一帧），原点挪了、身子还在旧姿势的那一帧也不要有
                UpdateActions(0);
                Mix(0);
                graph.Evaluate(0);
            }
        }

        Vector3 sitFrom, sitTo;
        bool sitGlide;
        /// false：坐下时原点直接放到蒲团下（动作自己带着「先站在前面一步」的位移）；true：原点一路挪过去（动作里没有位移时用）
        public static bool GlideMode = false;

        /// 一进场就坐着的人：记下蒲团和前面站的地方，起身时挪回草垫上
        public void SeatedAt(Vector3 seatGround, Vector3 standPoint)
        {
            sitTo = seatGround;
            sitFrom = new Vector3(standPoint.x, seatGround.y, standPoint.z);
            sitGlide = true;
        }

        /// 坐下、起身时把人在草垫和蒲团之间挪过去（动作里臀往后找蒲团的那 1.5 秒）
        void GlideSeat()
        {
            if (!sitGlide || actNow == null || !actIndex.TryGetValue(actNow, out int i)) return;
            float t = (float)slots[i].GetTime();
            var mover = controller != null ? controller.transform : transform;
            if (actNow == "Sit_Down") mover.position = Vector3.Lerp(sitFrom, sitTo, Mathf.SmoothStep(0, 1, Mathf.InverseLerp(0.3f, 1.6f, t)));
            else if (actNow == "Sit_Up") mover.position = Vector3.Lerp(sitTo, sitFrom, Mathf.SmoothStep(0, 1, Mathf.InverseLerp(0.7f, 2.0f, t)));
            lastPos = transform.position;
        }

        /// 鞠躬的深浅（0 直起，1 最低），由外面按节奏推
        public void SetBow(float phase) => bowPhase = Mathf.Clamp01(phase);

        public void FaceTowards(Vector3 point)
        {
            Vector3 d = point - transform.position;
            d.y = 0;
            if (d.sqrMagnitude < 0.0001f) return;
            faceYaw = Quaternion.LookRotation(d).eulerAngles.y;
            hasFace = true;
        }

        public void FaceYaw(float yaw)
        {
            faceYaw = yaw;
            hasFace = true;
        }

        /// 沿一串点走过去
        public void Walk(IEnumerable<Vector3> points)
        {
            path.Clear();
            path.AddRange(points);
            arriving = false;
            planSteps = 0;
            SetPose(Pose.None);
        }

        public void StopWalking()
        {
            path.Clear();
            arriving = false;
            desired = Vector3.zero;
        }

        /// 直接给一个速度（摇杆用）。会被走路径打断。推得很轻时按最慢的步子走，不会原地蹭
        public void Drive(Vector3 v)
        {
            path.Clear();
            arriving = false;
            v.y = 0;
            desired = Vector3.ClampMagnitude(v, walkSpeed * 1.35f);
            if (desired.sqrMagnitude > 0.0004f)
            {
                faceYaw = Quaternion.LookRotation(desired).eulerAngles.y;
                hasFace = true;
                if (pose != Pose.None) SetPose(Pose.None);
            }
            else desired = Vector3.zero;
        }

        /// 上一帧实际挪了多少（以前给主角控制器用；现在人自己挪）
        public Vector3 Motion(float dt) => velocity * dt;

        public CharacterController controller;
        /// 不用碰撞胶囊走路时，高度跟着脚下的地面走
        public bool groundFollow = true;

        void Update()
        {
            float dt = Time.deltaTime;
            bool sitting = pose == Pose.Bench || pose == Pose.CrossLegged;
            sitW = Mathf.MoveTowards(sitW, sitting ? 1 : 0, dt / 0.6f);
            if (graph.IsValid())
            {
                UpdateActions(dt);
                GlideSeat();
                Locomote(dt);
                Mix(actionClips != null && actionClips.Length > 0 && pose == Pose.CrossLegged ? 0 : Mathf.SmoothStep(0, 1, sitW));
            }
            // 模型被藏起来（动画不跑）或者没有带位移的步态：按速度直接挪
            bool rootOk = useRoot && model.gameObject.activeInHierarchy && Time.frameCount - rootFrame < 3;
            if (!rootOk)
            {
                Vector3 v = loco == Loco.Move || loco == Loco.Stop ? transform.forward * (loco == Loco.Stop ? (stopNow >= 0 ? StopSpeedAt((float)slots[stopNow].GetTime()) : 0) : speedCmd) : Vector3.zero;
                if (InTransition) v = Vector3.zero;
                ApplyMove(v * dt + correction * dt + pivotMove);
                pivotMove = Vector3.zero;
            }
            if (!useRoot)
            {
                stepDist += velocity.magnitude * dt;
                if (stepDist > 0.42f) { stepDist = 0; Step?.Invoke(); }
            }
            weight = Mathf.MoveTowards(weight, pose == Pose.None ? 0 : 1, dt / 0.7f);
        }

        float debugT;

        Vector3 prevL, prevR, corrDisp;
        bool havePrev;
        int lockFoot;

        /// 收尾：踩在地上的脚这一帧要是还滑了一点（重定向、混合带来的几厘米），把整个人反着挪回去，脚就钉在地上。
        /// 一只脚明显低（另一只抬着）钉那只；两只都踩着（起步淡入、停步最后站稳那一下）钉两只的中点。
        /// 停在终点要补的那一点（correction）是故意挪的，不算滑
        void FootLock(float dt)
        {
            if (lFoot == null || !useRoot || !Application.isPlaying) return;
            Vector3 l = lFoot.position, r = rFoot.position;
            float moveW = wGait + wStop + wTurn;
            bool moving = moveW > 0.5f || loco == Loco.Stop || (loco == Loco.Move && firstStep > 0);
            if (havePrev && dt > 1e-4f && moving && shuffle < 0.01f && actW < 0.1f && !InTransition && model.gameObject.activeInHierarchy)
            {
                float y0 = transform.position.y, ground = ankle * transform.lossyScale.y + 0.035f;
                float hl = l.y - y0, hr = r.y - y0;
                bool lowL = hl < ground, lowR = hr < ground;
                int foot;
                // 正常走、两脚一前一后：只钉明显低的那只（双脚支撑那一下后脚在滚过脚尖，中点会动）；
                // 起步、停步时两脚并在一起都踩着：钉中点
                Vector3 apart = l - r;
                apart.y = 0;
                bool together = apart.magnitude < 0.2f * transform.lossyScale.y / 0.806f;
                if ((loco == Loco.Move && firstStep <= 0) || !together)
                    foot = lowL && hl < hr - 0.012f ? 1 : lowR && hr < hl - 0.012f ? 2 : 0;
                else
                    foot = lowL && lowR ? (hl < hr - 0.025f ? 1 : hr < hl - 0.025f ? 2 : 3) : lowL ? 1 : lowR ? 2 : 0;
                // 刚落地的那一帧不管（脚还在往前送），同一只脚连着踩第二帧起才钉住
                bool steady = foot != 0 && foot == lockFoot;
                lockFoot = foot;
                if (steady)
                {
                    Vector3 slip = foot == 1 ? l - prevL : foot == 2 ? r - prevR : ((l - prevL) + (r - prevR)) * 0.5f;
                    slip -= corrDisp;
                    slip.y = 0;
                    bool soft = firstStep > 0 || loco == Loco.Stop;
                    if (slip.magnitude < (soft ? 1.2f : 0.5f) * dt)
                    {
                        float cap = soft ? 1f : 0.3f;
                        slip = Vector3.ClampMagnitude(slip, cap * dt);
                        // 起步那一步：身子往旁边、往后挪得慢一点（≤ 0.15 米/秒），重心是慢慢移到支撑脚上的，不是一下甩过去
                        if (firstStep > 0 && loco == Loco.Move)
                        {
                            Vector3 fw = transform.forward, rt = transform.right;
                            float back = Vector3.Dot(-slip, fw), side = Vector3.Dot(-slip, rt);
                            back = Mathf.Max(back, -0.1f * dt);
                            side = Mathf.Clamp(side, -0.15f * dt, 0.15f * dt);
                            slip = -(fw * back + rt * side);
                        }
                        var moverT = controller != null ? controller.transform : transform;
                        if (controller != null && controller.enabled) controller.Move(-slip);
                        else moverT.position -= slip;
                        lastPos = transform.position;
                    }
                }
            }
            havePrev = true;
        }

        // ── 站住时脚钉在地上（两段腿的 IK）──
        // 停步最后一步落地以后、站着（待机、换待机姿势）时，两只脚就踩在落下的地方不动：停步最后的站姿和待机的站姿宽窄、前后不一样，
        // 不钉住的话淡到待机那 0.4 秒里两只脚在地上往外、往前滑几厘米。原地转身、做动作、坐下就松开（0.15 秒淡掉）；
        // 起步时迈出去的那只脚马上松开，支撑脚等它蹬离地面才松开
        float plantWL, plantWR;
        bool planted;
        Vector3 plantL, plantR, plantRoot;
        Quaternion plantLq, plantRq;
        int holdFoot;                // 起步时一直钉着的支撑脚（1 左、2 右）：迈第一步时它在地上不动，等它蹬离地面才放开

        bool WantPlant()
        {
            if (!Application.isPlaying || !useRoot || lFoot == null || lKnee == null || !model.gameObject.activeInHierarchy) return false;
            if (pose != Pose.None || actW > 0.01f || InTransition || shuffle > 0.01f || sitW > 0.01f) return false;
            if (loco == Loco.Stop && stopNow >= 0)
            {
                float tPlant = stopSteps != null && stopSteps.Length > 0 ? stopSteps[stopSteps.Length - 1] : stopStill - 0.4f;
                return slots[stopNow].GetTime() >= tPlant + 0.06f;
            }
            return loco == Loco.Idle && wGait < 0.01f && wTurn < 0.01f;
        }

        void FootPlant(float dt)
        {
            bool still = WantPlant();
            if (planted && still && ((plantL - lFoot.position).sqrMagnitude > 0.09f || (plantR - rFoot.position).sqrMagnitude > 0.09f))
            {
                // 一下挪得很远（传送）：直接在新的地方钉
                plantL = lFoot.position; plantR = rFoot.position;
                plantLq = lFoot.rotation; plantRq = rFoot.rotation;
                plantRoot = transform.position;
            }
            // 人被外面慢慢挪开了（被胶囊挤开、按路线补位置）：先松开（0.15 秒），再在新的地方重新钉
            if (planted && still && (transform.position - plantRoot).sqrMagnitude > 0.0064f) still = false;
            // 起步：支撑脚在它蹬离地面以前一直钉在站着时的地方（身子慢慢移到它上面，见 FootLock；这只脚不跟着往旁边蹭）
            bool start = planted && loco == Loco.Move && firstStep > 0 && holdFoot != 0;
            float lift = ankle * transform.lossyScale.y + 0.05f, y0 = transform.position.y;
            bool wantL = still || (start && holdFoot == 1 && lFoot.position.y - y0 < lift);
            bool wantR = still || (start && holdFoot == 2 && rFoot.position.y - y0 < lift);
            if (!wantL && !wantR && start) holdFoot = 0;
            if (still && !planted && plantWL <= 0.001f && plantWR <= 0.001f)
            {
                // 刚站住：就钉在现在的位置（和动画这一帧一样，不跳）
                planted = true;
                plantL = lFoot.position; plantR = rFoot.position;
                plantLq = lFoot.rotation; plantRq = rFoot.rotation;
                plantRoot = transform.position;
            }
            plantWL = Mathf.MoveTowards(plantWL, wantL && planted ? 1 : 0, dt / (wantL ? 0.12f : 0.15f));
            plantWR = Mathf.MoveTowards(plantWR, wantR && planted ? 1 : 0, dt / (wantR ? 0.12f : 0.15f));
            if (plantWL <= 0.001f && plantWR <= 0.001f) { planted = false; return; }
            if (plantWL > 0.001f) LegIK(lThigh, lKnee, lFoot, plantL, plantLq, Mathf.SmoothStep(0, 1, plantWL));
            if (plantWR > 0.001f) LegIK(rThigh, rKnee, rFoot, plantR, plantRq, Mathf.SmoothStep(0, 1, plantWR));
        }

        /// 踩着的脚拧回去（见 lockYawL）：整条腿绕髋→踝的连线转，踝的位置不动，膝盖跟着脚的方向。抬起来的脚 0.15 秒里放掉
        void StanceTwist(float dt)
        {
            if (lFoot == null || lThigh == null || !Application.isPlaying) return;
            bool walking = (loco == Loco.Move && wGait > 0.5f) || loco == Loco.Turn;
            float y0 = transform.position.y, ground = ankle * transform.lossyScale.y + 0.03f;
            for (int k = 0; k < 2; k++)
            {
                var thigh = k == 0 ? lThigh : rThigh;
                var foot = k == 0 ? lFoot : rFoot;
                ref float lk = ref (k == 0 ? ref lockYawL : ref lockYawR);
                bool down = walking && foot.position.y - y0 < ground;
                if (!down) lk = Mathf.MoveTowards(lk, 0, Mathf.Max(Mathf.Abs(lk), 5f) * dt / 0.15f);
                lk = Mathf.Clamp(lk, -40f, 40f);
                if (Mathf.Abs(lk) < 0.05f) continue;
                Vector3 axis = thigh.position - foot.position;
                if (axis.sqrMagnitude < 1e-6f) continue;
                thigh.rotation = Quaternion.AngleAxis(lk, axis.normalized) * thigh.rotation;
            }
        }

        // ── 台阶、拜垫：脚踩在台阶面、垫子面上 ──

        /// 场景里的台阶（StairRamp 自己登记）
        public static readonly List<StairRamp> Ramps = new List<StairRamp>();
        /// 脚下高低不平、要让脚去踩的地方（拜垫、殿里蒲团前的草垫一圈；GameDirector 登记）
        public static readonly List<Rect> StepZones = new List<Rect>();

        static StairRamp RampAt(Vector3 p)
        {
            foreach (var r in Ramps) if (r != null && r.Contains(p)) return r;
            return null;
        }

        static bool InStepZone(Vector3 p)
        {
            var q = new Vector2(p.x, p.z);
            foreach (var z in StepZones) if (z.Contains(q)) return true;
            return false;
        }

        /// 不穿墙：没有碰撞胶囊的人（香客、自动走路线的自己）这一步要是从膝盖到胸口这一截撞进了隔断（栏杆、垂带、门柱、殿墙，见 Barriers），
        /// 就只沿着它滑过去（分开试 x、z，再试往左右偏 35、70 度：圆的门柱、石碑绕得过去），都不行就不挪。
        /// 本来就在里面的（被摆进去、被人挤进去的）：只许往外走（陷进去的深度变浅），往里走、贴着里面走都不行；哪一步都不浅就自己往外退
        /// （以前「起点就在里面就随便走」：殿前站着的人被摆进台阶的垂带里，站了五十多秒，走的时候从垂带的端头上跨过去）
        static readonly Collider[] solidHits = new Collider[8];
        /// 被实的东西挡着一步也挪不动有多久了：3 秒（先让找路的那一套换条路）以后往哪边滑都行（solidLoose），8 秒还卡着就放他过去一秒
        /// （宁可蹭过去，也不能一直卡着、误了行程；以前 3 秒就放过去，复核时一位香客就这样进了山门的门柱 40 帧）
        float solidStuck, solidPass, solidLoose;
        /// 排查用：最近一次挡住的是什么
        public string LastSolid { get; private set; } = "";
        Vector3 KeepOutOfSolids(Vector3 from, Vector3 to)
        {
            float dt = Time.deltaTime;
            if ((to - from).sqrMagnitude < 1e-8f) return to;
            if (solidPass > 0f) { solidPass -= dt; return to; }
            if (solidLoose > 0f) solidLoose -= dt;
            float s = Mathf.Max(transform.lossyScale.y / 0.806f, 0.5f);
            float depth0 = SolidDepth(from, BarrierBody * s, s, out Vector3 outDir, out string what);
            if (depth0 > 0f)
            {
                LastSolid = what;
                solidStuck = 0f;
                Vector3 ax0 = new Vector3(to.x, to.y, from.z), az0 = new Vector3(from.x, to.y, to.z);
                foreach (var c in new[] { to, ax0, az0 })
                    if (SolidDepth(c, BarrierBody * s, s, out _, out _) < depth0 - 1e-4f) return c;
                // 哪一步都不往外：自己往外退（一秒半米多）
                return new Vector3(from.x, to.y, from.z) + outDir * Mathf.Min(depth0 + 0.01f, 0.6f * dt);
            }
            if (!SolidHit(to, s)) { solidStuck = 0f; return to; }
            // 贴着滑过去只往要去的那边滑（离路线上下一个点的方向 78 度以内）：被旁边的人挤着、顺着垂带的侧面往台基那边滑，
            // 一路滑进垂带和台基之间的死角里出不去（复核时一位香客就这样从台阶下面滑进了角里）。滑不动就站住，让找路的那一套换条路
            Vector3 goal = path.Count > 0 ? path[0] - from : to - from;
            goal.y = 0;
            bool Toward(Vector3 c)
            {
                Vector3 m = c - from;
                m.y = 0;
                return solidLoose > 0f || m.sqrMagnitude < 1e-10f || goal.sqrMagnitude < 1e-6f || Vector3.Dot(m.normalized, goal.normalized) > 0.2f;
            }
            Vector3 ax = new Vector3(to.x, to.y, from.z), az = new Vector3(from.x, to.y, to.z);
            if (Toward(ax) && !SolidHit(ax, s)) { solidStuck = 0f; return ax; }
            if (Toward(az) && !SolidHit(az, s)) { solidStuck = 0f; return az; }
            // 往左右偏一点绕过去（圆柱子、石碑这种：x、z 分开试常常两头都碰）
            Vector3 st = to - from;
            st.y = 0;
            foreach (float a in new[] { 35f, -35f, 70f, -70f })
            {
                Vector3 c = from + Quaternion.Euler(0, a, 0) * st * (Mathf.Abs(a) > 50f ? 0.6f : 0.85f);
                c.y = to.y;
                if (Toward(c) && !SolidHit(c, s)) { solidStuck = 0f; return c; }
            }
            solidStuck += dt;
            // 挡了 3 秒：先放开「只往要去的那边滑」，往哪边滑都行（贴着垂带、栏杆挪开，不穿进去）；挡了 8 秒还挪不动（夹在角里）才放他穿过去一秒
            if (solidStuck > 3f && solidLoose <= 0f && solidStuck < 3.5f) solidLoose = 2f;
            if (solidStuck > 8f) { solidStuck = 0f; solidPass = 1f; return to; }
            return new Vector3(from.x, to.y, from.z);
        }

        /// p 这里站人（胶囊从膝盖到胸口）会不会碰到隔断
        bool SolidHit(Vector3 p, float s)
        {
            int n = Physics.OverlapCapsuleNonAlloc(p + Vector3.up * 0.42f * s, p + Vector3.up * 1.05f * s, BarrierBody * s, solidHits, SolidMask, QueryTriggerInteraction.Ignore);
            for (int i = 0; i < n; i++)
            {
                var c = solidHits[i];
                if (c is CharacterController || c.transform.IsChildOf(transform) || !Barriers.Contains(c.name)) continue;
                LastSolid = c.name;
                return true;
            }
            return false;
        }

        /// 拦隔断时人身子按多粗算（半径，米）：比腿、身子本身（约 0.12）宽一点，人停下来时和栏杆、石碑、长凳之间留两三厘米，不是贴着
        const float BarrierBody = 0.15f;

        /// p 这里站人（半径 r）陷进隔断里多深（水平，米；不碰是 0），和往哪边出来最近
        float SolidDepth(Vector3 p, float r, float s, out Vector3 outDir, out string what)
        {
            outDir = Vector3.zero;
            what = "";
            float best = 0f;
            int n = Physics.OverlapCapsuleNonAlloc(p + Vector3.up * 0.42f * s, p + Vector3.up * 1.05f * s, r, solidHits, SolidMask, QueryTriggerInteraction.Ignore);
            for (int i = 0; i < n; i++)
            {
                var c = solidHits[i];
                if (c is CharacterController || c.transform.IsChildOf(transform) || !Barriers.Contains(c.name)) continue;
                float d = Penetration(c, p, r, out Vector3 dir);
                if (d > best) { best = d; outDir = dir; what = c.name; }
            }
            return best;
        }

        /// 竖着的人（中轴过 p，半径 r）横着陷进 c 多深、往哪边出来（只看水平：隔断都是竖着立的方块、圆柱）
        static float Penetration(Collider c, Vector3 p, float r, out Vector3 outDir)
        {
            outDir = Vector3.zero;
            var t = c.transform;
            if (c is BoxCollider b)
            {
                Vector3 lp = t.InverseTransformPoint(p) - b.center, sc = t.lossyScale, he = b.size * 0.5f;
                float dx = (Mathf.Abs(lp.x) - he.x) * Mathf.Abs(sc.x), dz = (Mathf.Abs(lp.z) - he.z) * Mathf.Abs(sc.z);
                float sx = lp.x >= 0 ? 1f : -1f, sz = lp.z >= 0 ? 1f : -1f;
                if (dx <= 0f && dz <= 0f)
                {
                    // 中轴在方块里面：从离得最近的那一面出去
                    outDir = t.rotation * (dx > dz ? new Vector3(sx, 0, 0) : new Vector3(0, 0, sz));
                    outDir.y = 0;
                    outDir.Normalize();
                    return r - Mathf.Max(dx, dz);
                }
                var v = new Vector3(dx > 0 ? sx * dx : 0, 0, dz > 0 ? sz * dz : 0);
                float d = v.magnitude;
                if (d >= r) return 0f;
                outDir = t.rotation * (v / d);
                outDir.y = 0;
                outDir.Normalize();
                return r - d;
            }
            if (c is CapsuleCollider cap && cap.direction == 1)
            {
                Vector3 axis = t.TransformPoint(cap.center), h = p - axis;
                h.y = 0;
                float R = cap.radius * Mathf.Max(Mathf.Abs(t.lossyScale.x), Mathf.Abs(t.lossyScale.z)), d = h.magnitude;
                if (d >= R + r) return 0f;
                outDir = d > 1e-4f ? h / d : Vector3.back;
                return R + r - d;
            }
            Vector3 cp = c.ClosestPoint(p), hv = p - cp;
            hv.y = 0;
            float dd = hv.magnitude;
            if (dd < 1e-4f)
            {
                hv = p - c.bounds.center;
                hv.y = 0;
                outDir = hv.sqrMagnitude > 1e-6f ? hv.normalized : Vector3.back;
                return r;
            }
            if (dd >= r) return 0f;
            outDir = hv / dd;
            return r - dd;
        }

        /// 挑站的地方用：p 这里站一个人（半径 r，膝盖到胸口）会不会碰到隔断（栏杆、垂带、门柱、殿墙、石碑、长凳……）
        public static bool BarrierNear(Vector3 p, float r)
        {
            int n = Physics.OverlapCapsuleNonAlloc(p + Vector3.up * 0.4f, p + Vector3.up * 1.2f, r, solidHits, SolidMask, QueryTriggerInteraction.Ignore);
            for (int i = 0; i < n; i++)
                if (!(solidHits[i] is CharacterController) && Barriers.Contains(solidHits[i].name)) return true;
            return false;
        }

        /// 实的东西在哪几层：除了 Ignore Raycast（2）都算（殿里的柱子、栏杆、门扇在 NoCameraLayer，也算）
        const int SolidMask = ~(1 << 2);
        /// 只拦这几样「穿过去就是穿帮」的隔断：栏杆、垂带、山门的门柱、殿的墙和门框，院子里的石碑、长凳、洗手的石盆、指路牌、挂木牌的架子。
        /// 柱子、台基、铺地的石头这些不拦（路线本来就绕着走；一拦，人群里被挤过去的人就卡在柱子边、台基脚下、池边的石头上，HallCrowdTest 里卡住了几回）
        public static readonly HashSet<string> Barriers = new HashSet<string>
        {
            "RailFront", "RailSide", "RailBack", "StepCheek", "GatePost", "SideWall", "WindowBay", "Jamb",
            "stele", "bench", "basin", "signpost", "plaque_rack",
        };

        float giW, pelvisOff, pelvisVel, visY;
        string groundDebug = "";
        /// 排查用：台阶、垫子上脚下这一帧怎么补的
        public string DebugGround => giW > 0.001f ? groundDebug : "不在台阶、垫子上";
        bool visInit;
        static readonly RaycastHit[] giHits = new RaycastHit[8];

        /// 脚下 p 那一点踩得到的面有多高（朝上的面：地、台阶顶、垫子面；台阶的立面、墙不算）；没有是负无穷
        float SurfaceAt(Vector3 p)
        {
            int n = Physics.RaycastNonAlloc(p + Vector3.up * 0.35f, Vector3.down, giHits, 0.8f, ~(1 << 2), QueryTriggerInteraction.Ignore);
            float best = float.NegativeInfinity;
            for (int i = 0; i < n; i++)
            {
                var c = giHits[i].collider;
                if (c is CharacterController || c.transform.IsChildOf(transform) || giHits[i].normal.y < 0.7f) continue;
                best = Mathf.Max(best, giHits[i].point.y);
            }
            return best;
        }

        /// 一只脚：脚底（踝往下 ankle）比它正下方的面低多少（needA，正的是插进去了）、脚尖比它下面的面低多少（needT：迈步时脚尖往下垂、
        /// 落脚时脚尖伸到下一级的立面里）、脚底在原点以上多高（h：动画里这只脚抬得多高，用来分哪只脚踩着、哪只在迈）
        bool FootNeed(Transform foot, Transform toe, float baseY, float ankleH, out float needA, out float needT, out float h)
        {
            float sole = foot.position.y - ankleH;
            h = sole - baseY;
            float surf = SurfaceAt(foot.position);
            // 脚跟（踝往后 7 厘米）：下台阶时脚掌落在台阶沿外面、脚跟还在上一级的踏面里——按高的那一面算
            Vector3 fwd = toe != null ? toe.position - foot.position : transform.forward;
            fwd.y = 0f;
            if (fwd.sqrMagnitude > 1e-6f)
                surf = Mathf.Max(surf, SurfaceAt(foot.position - fwd.normalized * 0.07f * transform.lossyScale.y / 0.806f));
            needA = float.IsNegativeInfinity(surf) ? 0f : surf - sole;
            needT = float.NegativeInfinity;
            if (toe != null)
            {
                float st = SurfaceAt(toe.position);
                if (!float.IsNegativeInfinity(st)) needT = st - (toe.position.y - 0.015f * transform.lossyScale.y / 0.806f);
            }
            return !float.IsNegativeInfinity(surf);
        }

        /// 走在台阶上、上下拜垫时（站着、走着；跪、坐、做动作时不管）：
        /// 1. 胶囊（摇杆）一级一级跳上去的那一下，画出来的身子不跟着跳：按斜坡（台阶）、按每秒 0.9 米慢慢抬（垫子）走；
        /// 2. 动画里低的那只脚是踩着的：整个身子沉下去（或抬起来一点）到它踩实在它下面那一级上；
        ///    踩着的脚跟着落到踏面上，迈着的脚只在插进台阶、脚尖碰到下一级的沿时往上抬（膝盖多弯一点）。在 FootPlant 之后、甩头发（SpringBones）之前
        void GroundIK(float dt)
        {
            if (lFoot == null || lThigh == null || lKnee == null || !Application.isPlaying || !model.gameObject.activeInHierarchy) return;
            Vector3 root = transform.position;
            bool want = pose == Pose.None && actW < 0.1f && !InTransition && sitW < 0.01f;
            var ramp = want ? RampAt(root) : null;
            bool zone = want && (ramp != null || InStepZone(root));
            float s = Mathf.Max(transform.lossyScale.y, 1e-3f);
            float off = 0f;
            if (controller != null && controller.enabled)
            {
                float wantY = ramp != null ? ramp.HeightAt(root) : root.y;
                visY = !visInit || !zone ? wantY : Mathf.MoveTowards(visY, wantY, (ramp != null ? 3f : 0.9f) * dt);
                visInit = true;
                off = Mathf.Clamp(visY - root.y, -0.25f, 0.25f);
            }
            else visInit = false;
            giW = Mathf.MoveTowards(giW, zone ? 1f : 0f, dt / 0.15f);
            if (Mathf.Abs(off) > 1e-4f) model.localPosition += Vector3.up * off / s;
            if (giW <= 0.001f)
            {
                pelvisOff = pelvisVel = 0f;
                return;
            }
            float baseY = root.y + off, ankleH = ankle * s;
            bool okL = FootNeed(lFoot, lToe, baseY, ankleH, out float aL, out float tL, out float hL);
            bool okR = FootNeed(rFoot, rToe, baseY, ankleH, out float aR, out float tR, out float hR);
            // 哪只脚踩着：动画里低的那只（两只差不到 1.5 厘米就算都踩着）
            bool stL = okL && (!okR || hL <= hR + 0.015f), stR = okR && (!okL || hR <= hL + 0.015f);
            float pt = 0f;
            int n = 0;
            if (stL) { pt += aL; n++; }
            if (stR) { pt += aR; n++; }
            pt = n > 0 ? Mathf.Clamp(pt / n, -0.12f, 0.1f) : 0f;
            pelvisOff = dt <= 0f ? pt : Mathf.SmoothDamp(pelvisOff, pt * giW, ref pelvisVel, 0.08f, Mathf.Infinity, dt);
            if (Mathf.Abs(pelvisOff) > 1e-4f) model.localPosition += Vector3.up * pelvisOff / s;
            groundDebug = $"区 {(ramp != null ? "台阶" : "垫子")} 权 {giW:F2} 偏 {off:F3} 左 {aL:F3}/{(float.IsNegativeInfinity(tL) ? 0f : tL):F3}{(stL ? "踩" : "抬")} 右 {aR:F3}/{(float.IsNegativeInfinity(tR) ? 0f : tR):F3}{(stR ? "踩" : "抬")} 髋 {pelvisOff:F3}";
            for (int k = 0; k < 2; k++)
            {
                bool ok = k == 0 ? okL : okR, st = k == 0 ? stL : stR;
                if (!ok) continue;
                float na = (k == 0 ? aL : aR) - pelvisOff, nt = (k == 0 ? tL : tR) - pelvisOff;
                float need = Mathf.Max(na, nt);
                // 踩着的：落到踏面上（往下最多 8 厘米），脚尖伸进下一级的就踩到那一级的沿上；迈着的：只往上抬（插进去了、脚尖碰着沿了）
                float dy = st ? Mathf.Clamp(need, -0.08f, 0.2f) : need > 0.003f ? Mathf.Min(need, 0.2f) : 0f;
                if (Mathf.Abs(dy) < 0.003f) continue;
                var foot = k == 0 ? lFoot : rFoot;
                LegIK(k == 0 ? lThigh : rThigh, k == 0 ? lKnee : rKnee, foot, foot.position + Vector3.up * dy, foot.rotation, giW);
            }
        }

        // ── 蒙皮网格的包围盒 ──

        /// 模型里存的包围盒是站着的那一份（按根骨骼、脚底为原点；脸只有头顶那一小块）。坐下、跪下、叩首时头低了 0.4–1 米、往前探：
        /// 镜头只框着坐着的人（头顶没留空）时，脸、眼睛那几块网格被当成在画面外裁掉，只剩头发里面的描边——一张深棕色的空脸（评审第三轮）。
        /// 做着动作（坐、跪、拜，pose 不是 None 或者动作段还没淡完）的时候，每块的包围盒再并上一个装得下低姿势的盒子；站着走着换回原来的
        /// （大盒子一直开着的话，走动的人在视锥、影子级联边上都多画，俯视院子的批次翻了一倍）
        SkinnedMeshRenderer[] smrs;
        Bounds[] smrRest;
        bool lowBounds;
        static readonly Bounds LowPose = new Bounds(new Vector3(0f, 0.55f, 0.25f), new Vector3(1.7f, 1.4f, 1.9f));

        /// 离自己（镜头跟着的那个人）ShadowFar 米以外的人不投影子：俯视、平视里那么远的人只有几十个像素高，影子看不出来，
        /// 可每个人的影子都要把全身（两三万个三角形）在三层影子图里再画一遍——人多的钟点（四五十位）光影子就是六七百个批次（PerfTest）。
        /// 自己、近处的人照常投。殿里按门洞只投影子的（InteriorCull 改成 ShadowsOnly 的）不动
        public static float ShadowFar = 22f;
        float shadowNext;
        bool farShadowOff;
        UnityEngine.Rendering.ShadowCastingMode[] smrCast;

        void UpdateFarShadow()
        {
            if (smrs == null || (shadowNext -= Time.deltaTime) > 0f) return;
            shadowNext = 0.5f + 0.1f * ((GetInstanceID() & 7) / 7f);
            if (smrCast == null || smrCast.Length != smrs.Length)
            {
                smrCast = new UnityEngine.Rendering.ShadowCastingMode[smrs.Length];
                for (int i = 0; i < smrs.Length; i++) smrCast[i] = smrs[i] != null ? smrs[i].shadowCastingMode : UnityEngine.Rendering.ShadowCastingMode.On;
            }
            var gd = GameDirector.Instance;
            var me = gd != null ? gd.player : null;
            if (me == null || me == this) return;
            Vector3 d = transform.position - me.transform.position;
            d.y = 0;
            bool far = ShadowFar > 0f && d.magnitude > (farShadowOff ? ShadowFar - 1.5f : ShadowFar);
            farShadowOff = far;
            for (int i = 0; i < smrs.Length; i++)
            {
                var r = smrs[i];
                if (r == null || r.shadowCastingMode == UnityEngine.Rendering.ShadowCastingMode.ShadowsOnly) continue;
                var want = far ? UnityEngine.Rendering.ShadowCastingMode.Off : smrCast[i];
                if (r.shadowCastingMode != want) r.shadowCastingMode = want;
            }
        }

        void UpdateBounds()
        {
            if (model == null) return;
            if (smrs == null)
            {
                smrs = model.GetComponentsInChildren<SkinnedMeshRenderer>(true);
                smrRest = new Bounds[smrs.Length];
                for (int i = 0; i < smrs.Length; i++) smrRest[i] = smrs[i].localBounds;
            }
            bool low = pose != Pose.None || actW > 0.02f || sitW > 0.01f;
            if (low == lowBounds) return;
            lowBounds = low;
            for (int i = 0; i < smrs.Length; i++)
            {
                if (smrs[i] == null) continue;
                var b = smrRest[i];
                if (low) b.Encapsulate(LowPose);
                smrs[i].localBounds = b;
            }
        }

        // ── 殿里脚下的接触影子 ──

        /// 殿里的灯不投影子：人在殿里时脚下（跪着是膝盖到脚背、坐着是整个盘腿那一片）摆一块软的暗影（YJContact，GameDirector 进场时给材质）
        public static Material ContactMaterial;
        Transform contact;
        MeshRenderer contactR;
        MaterialPropertyBlock contactMpb;
        static Mesh contactQuad;
        static readonly int StrengthId = Shader.PropertyToID("_Strength");

        void UpdateContact()
        {
            var gd = GameDirector.Instance;
            bool want = Application.isPlaying && ContactMaterial != null && gd != null && hips != null && lFoot != null && model.gameObject.activeInHierarchy && gd.InHall(transform.position);
            if (!want)
            {
                if (contactR != null && contactR.enabled) contactR.enabled = false;
                return;
            }
            if (contact == null)
            {
                if (contactQuad == null)
                {
                    contactQuad = new Mesh { name = "contact_quad" };
                    contactQuad.SetVertices(new[] { new Vector3(-0.5f, -0.5f, 0), new Vector3(0.5f, -0.5f, 0), new Vector3(-0.5f, 0.5f, 0), new Vector3(0.5f, 0.5f, 0) });
                    contactQuad.SetUVs(0, new[] { new Vector2(0, 0), new Vector2(1, 0), new Vector2(0, 1), new Vector2(1, 1) });
                    contactQuad.SetTriangles(new[] { 0, 2, 1, 2, 3, 1 }, 0);
                    contactQuad.RecalculateBounds();
                }
                var go = new GameObject("ContactShadow");
                go.transform.SetParent(transform, false);
                go.AddComponent<MeshFilter>().sharedMesh = contactQuad;
                contactR = go.AddComponent<MeshRenderer>();
                contactR.sharedMaterial = ContactMaterial;
                contactR.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                contactR.receiveShadows = false;
                contactR.lightProbeUsage = UnityEngine.Rendering.LightProbeUsage.Off;
                contactMpb = new MaterialPropertyBlock();
                contact = go.transform;
            }
            Vector3 root = transform.position, r = transform.right, f = transform.forward;
            r.y = 0; f.y = 0;
            r.Normalize(); f.Normalize();
            float floor = SurfaceAt(new Vector3(hips.position.x, root.y, hips.position.z));
            if (float.IsNegativeInfinity(floor)) floor = root.y;
            // 贴着地的那几处（脚、膝盖、髋；离地 0.4 米以内的手、头——叩首时）围出来的一块，四边各放 0.12 米
            float x0 = float.MaxValue, x1 = float.MinValue, z0 = float.MaxValue, z1 = float.MinValue;
            void Add(Transform t, float maxH)
            {
                if (t == null || t.position.y - floor > maxH) return;
                Vector3 d = t.position - root;
                float a = Vector3.Dot(d, r), b = Vector3.Dot(d, f);
                x0 = Mathf.Min(x0, a); x1 = Mathf.Max(x1, a); z0 = Mathf.Min(z0, b); z1 = Mathf.Max(z1, b);
            }
            Add(lFoot, 9f); Add(rFoot, 9f); Add(lToe, 9f); Add(rToe, 9f); Add(lKnee, 0.45f); Add(rKnee, 0.45f); Add(hips, 0.6f);
            Add(lHand, 0.4f); Add(rHand, 0.4f); Add(head, 0.5f);
            const float pad = 0.12f;
            float sx = Mathf.Clamp(x1 - x0 + 2 * pad, 0.3f, 1.4f), sz = Mathf.Clamp(z1 - z0 + 2 * pad, 0.3f, 1.6f);
            Vector3 c = root + r * ((x0 + x1) * 0.5f) + f * ((z0 + z1) * 0.5f);
            contact.SetPositionAndRotation(new Vector3(c.x, floor + 0.006f, c.z), Quaternion.LookRotation(Vector3.down, f));
            float ls = Mathf.Max(transform.lossyScale.y, 1e-3f);
            contact.localScale = new Vector3(sx, sz, 1f) / ls;
            // 脚抬得越高越淡（两只脚都离地：跳不起来，但起身、迈大步时会有一下）
            float sole = Mathf.Min(lFoot.position.y, rFoot.position.y) - ankle * ls - floor;
            float k = 1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.03f, 0.3f, sole));
            contactMpb.SetFloat(StrengthId, 0.55f * k);
            contactR.SetPropertyBlock(contactMpb);
            if (!contactR.enabled) contactR.enabled = true;
        }

        void LegIK(Transform thigh, Transform knee, Transform foot, Vector3 target, Quaternion rot, float w)
        {
            Vector3 a = thigh.position, b = knee.position, c = foot.position;
            Vector3 t = Vector3.Lerp(c, target, w);
            float la = (b - a).magnitude, lb = (c - b).magnitude;
            if (la < 1e-4f || lb < 1e-4f) return;
            float d = Mathf.Clamp((t - a).magnitude, Mathf.Abs(la - lb) + 1e-3f, (la + lb) * 0.999f);
            Vector3 n = Vector3.Cross(a - b, c - b);
            if (n.sqrMagnitude < 1e-8f) n = -transform.right;     // 腿伸直了：膝盖往前弯
            n.Normalize();
            float cur = Vector3.Angle(a - b, c - b);
            float wantAng = Mathf.Acos(Mathf.Clamp((la * la + lb * lb - d * d) / (2 * la * lb), -1f, 1f)) * Mathf.Rad2Deg;
            knee.rotation = Quaternion.AngleAxis(wantAng - cur, n) * knee.rotation;
            Vector3 c2 = foot.position;
            thigh.rotation = Quaternion.FromToRotation(c2 - a, t - a) * thigh.rotation;
            foot.rotation = Quaternion.Slerp(foot.rotation, rot, w);
        }

        void LateUpdate()
        {
            FootLock(Time.deltaTime);
            ApplyPose(Time.deltaTime);
            // FootLock 下一帧比的是动画给的脚（IK 之前），不然 IK 钉住的脚会被当成「脚滑了」去挪人
            if (lFoot != null) { prevL = lFoot.position; prevR = rFoot.position; }
            StanceTwist(Time.deltaTime);
            FootPlant(Time.deltaTime);
            GroundIK(Time.deltaTime);
            UpdateContact();
            UpdateBounds();
            UpdateFarShadow();
            if (nameTag != null && head != null && !string.IsNullOrEmpty(nameTag.text) && !float.IsNaN(head.position.y))
            {
                nameTag.transform.position = head.position + Vector3.up * 0.36f * transform.lossyScale.y;
                var cam = Camera.main;
                if (cam != null)
                {
                    float d = Vector3.Distance(cam.transform.position, nameTag.transform.position);
                    nameTag.transform.rotation = Quaternion.LookRotation(nameTag.transform.position - cam.transform.position);
                    // 远近看起来差不多大；太近（贴着镜头走过）就不显示
                    nameTag.transform.localScale = Vector3.one * Mathf.Clamp(d * TagScalePerMeter, 0.55f, TagMaxScale);
                    var r = nameTag.GetComponent<MeshRenderer>();
                    bool show = d > 1.6f && d < TagHideBeyond && !InFrontOfFocus(cam.transform.position, nameTag.transform.position);
                    // 镜头在殿里、这个人在殿外：名字不显示（字画在最上面，会透过墙浮在殿里）
                    var ic = InteriorCull.Active;
                    if (show && ic != null && ic.CameraInside && !ic.InHall(transform.position)) show = false;
                    // 描边（NameTag 的八份深色字，子物体）跟着一起收：只收白字的话，留下一团灰字（殿里常压在佛像身上）
                    if (r.enabled != show)
                        foreach (var rr in nameTag.GetComponentsInChildren<MeshRenderer>(true)) rr.enabled = show;
                }
            }
        }

        // ── 姿势 ──

        void Set(string muscle, float value, float w)
        {
            if (muscleByName.TryGetValue(muscle, out int i)) hp.muscles[i] = Mathf.Lerp(hp.muscles[i], value, w);
        }

        void Both(string part, float value, float w)
        {
            Set("Left " + part, value, w);
            Set("Right " + part, value, w);
        }

        /// 双手合十在胸前（关节值是在侧面图上一组组试出来的）
        void Gassho(float w)
        {
            Both("Arm Down-Up", -0.6f, w);
            Both("Arm Front-Back", 0.55f, w);
            Both("Arm Twist In-Out", 0f, w);
            Both("Forearm Stretch", -0.95f, w);
            Both("Forearm Twist In-Out", -1f, w);
            Both("Hand Down-Up", -0.6f, w);
            Both("Hand In-Out", 0f, w);
        }

        /// 双手放在腿上（坐着的时候）
        void HandsOnLap(float w)
        {
            Both("Arm Down-Up", -0.75f, w);
            Both("Arm Front-Back", 0.35f, w);
            Both("Forearm Stretch", -0.55f, w);
            Both("Forearm Twist In-Out", -0.4f, w);
            Both("Hand Down-Up", -0.2f, w);
        }

        /// 整个身体以髋为轴往前倾 deg 度，大腿反向补回来，脚不离地（大腿前后的范围是往前 90 度、往后 50 度，往前是负值）
        void PitchAtHips(float deg, float w, float legBase)
        {
            // 绕身体横轴转正角度是往前倾；骨盆前倾时两条腿会跟着往后甩，所以大腿要往前收同样的角度
            hp.bodyRotation = Quaternion.Slerp(hp.bodyRotation, hp.bodyRotation * Quaternion.Euler(deg, 0, 0), w);
            float leg = legBase - deg / 90f;
            Both("Upper Leg Front-Back", Mathf.Clamp(leg, -1f, 1f), w);
        }

        void Spine(float amount, float w)
        {
            Set("Spine Front-Back", 0.5f * amount, w);
            Set("Chest Front-Back", 0.4f * amount, w);
            Set("UpperChest Front-Back", 0.4f * amount, w);
        }

        float kneeExtra;

        /// 走路时往弯里倾（整个人绕脚底转一点），头先往要转去的方向看
        void ApplyLean()
        {
            if (model == null) return;
            model.localRotation = Mathf.Abs(lean) > 0.01f ? Quaternion.AngleAxis(lean, Vector3.forward) : Quaternion.identity;
            if (head != null && Mathf.Abs(headLook) > 0.05f && actW < 0.5f)
                head.rotation = Quaternion.AngleAxis(headLook, Vector3.up) * head.rotation;
        }

        void ApplyPose(float dt)
        {
            // 模型被隐藏时动画不再刷新骨骼，这时不能再去改姿势
            if (handler == null || !model.gameObject.activeInHierarchy) return;
            ApplyLean();
            if (actionClips != null && actionClips.Length > 0 && Pose_Allowed(shown))
            {
                // 姿势全由动作段给（高度也是动作里做好的），这里只补关节缩放
                ApplyProportions();
                model.localPosition = Vector3.zero;
                return;
            }
            if (weight <= 0.001f)
            {
                ApplyProportions();
                ApplySink(0, dt);
                return;
            }
            handler.GetHumanPose(ref hp);
            float w = Mathf.SmoothStep(0, 1, weight);
            float bow = Mathf.SmoothStep(0, 1, bowPhase);
            float sinkTarget = 0;
            kneeExtra = 0;
            switch (shown)
            {
                case Pose.Gassho:
                    Gassho(w);
                    Spine(0.15f + 0.5f * bow, w);
                    break;
                case Pose.Bow:
                    // 站着鞠躬：从髋部往前倾，背微微弯
                    Gassho(w);
                    PitchAtHips(38f * bow, w, 0);
                    Spine(0.35f * bow, w);
                    break;
                case Pose.Kneel:
                case Pose.KneelBow:
                {
                    // 直身跪：大腿竖直，小腿平贴在身后；拜下去时上身前倾，双手往前伏地
                    float b = shown == Pose.KneelBow ? bow : 0;
                    PitchAtHips(65f * b, w, 0);
                    Both("Lower Leg Stretch", -1f, w);
                    Both("Foot Up-Down", 0.3f, w);
                    kneeExtra = 15f;
                    if (b > 0.02f)
                    {
                        Spine(0.7f * b, w);
                        Both("Arm Down-Up", Mathf.Lerp(-0.6f, -0.1f, b), w);
                        Both("Arm Front-Back", Mathf.Lerp(0.55f, 1f, b), w);
                        Both("Forearm Stretch", Mathf.Lerp(-0.95f, 0.3f, b), w);
                        Both("Forearm Twist In-Out", Mathf.Lerp(-1f, 0f, b), w);
                        Both("Hand Down-Up", Mathf.Lerp(-0.6f, 0.4f, b), w);
                    }
                    else Gassho(w);
                    sinkTarget = 1;
                    break;
                }
                case Pose.CrossLegged:
                    // 盘坐：大腿往前、往两边打开，膝盖弯到底再多弯一截，两只脚收在身前
                    Both("Upper Leg Front-Back", -1f, w);
                    Both("Upper Leg In-Out", 0.9f, w);
                    Both("Upper Leg Twist In-Out", 0.8f, w);
                    Both("Lower Leg Stretch", -1f, w);
                    Both("Foot Up-Down", 0f, w);
                    kneeExtra = 62f;
                    if (bowPhase > 0.001f)
                    {
                        Gassho(w);
                        Spine(0.2f + 0.8f * bow, w);
                    }
                    else HandsOnLap(w);
                    sinkTarget = 2;
                    break;
                case Pose.Custom:
                    foreach (var kv in custom) if (kv.Key != "sink" && kv.Key != "knee") Set(kv.Key, kv.Value, w);
                    hp.bodyRotation = hp.bodyRotation * Quaternion.Euler(customPitch, 0, 0);
                    sinkTarget = custom.ContainsKey("sink") ? custom["sink"] : 0;
                    kneeExtra = custom.ContainsKey("knee") ? custom["knee"] : 0;
                    break;
                case Pose.Bench:
                    if (bowPhase > 0.001f)
                    {
                        Gassho(w);
                        Spine(0.2f + 0.7f * bow, w);
                    }
                    else HandsOnLap(w);
                    sinkTarget = 3;
                    break;
                default:
                    Gassho(w);
                    break;
            }
            handler.SetHumanPose(ref hp);
            BendKnees(kneeExtra * w);
            ApplyProportions();
            ApplySink(sinkTarget, dt);
        }

        /// 膝盖关节默认最多弯 80 度，盘坐、跪坐要弯得更多：在动画之后直接把小腿再往里转一截
        void BendKnees(float extra)
        {
            if (extra <= 0.01f || lKnee == null) return;
            foreach (var (knee, foot) in new[] { (lKnee, lFoot), (rKnee, rFoot) })
            {
                Transform thigh = knee.parent;
                Vector3 a = (knee.position - thigh.position).normalized, b = (foot.position - knee.position).normalized;
                Vector3 axis = Vector3.Cross(a, b);
                if (axis.sqrMagnitude < 1e-4f) axis = transform.right;
                knee.rotation = Quaternion.AngleAxis(extra, axis.normalized) * knee.rotation;
            }
        }

        /// 坐下、跪下时整个人往下沉到合适的高度：跪着让膝盖着地，坐着让臀部落在坐垫或椅面上
        void ApplySink(float mode, float dt)
        {
            // 在模型自己的坐标里量髋和膝盖有多高，再算要沉多少。
            // 不能用世界坐标减来减去：那样下沉量会依赖上一帧的下沉量，动画一旦没刷新（模型被隐藏）就越滚越大，最后变成无效数
            float target = 0;
            if (mode == 1 && lKnee != null)
                target = 0.035f - Mathf.Min(model.InverseTransformPoint(lKnee.position).y, model.InverseTransformPoint(rKnee.position).y);
            else if (mode == 2 || mode == 3)
                target = 0.07f - model.InverseTransformPoint(hips.position).y;
            target = mode == 0 ? 0 : target * weight;
            if (float.IsNaN(target) || float.IsInfinity(target)) target = 0;
            target = Mathf.Clamp(target, -1.2f, 0.4f);
            if (float.IsNaN(sink) || float.IsNaN(sinkVel))
            {
                sink = 0;
                sinkVel = 0;
            }
            sink = dt <= 1e-5f ? target : Mathf.SmoothDamp(sink, target, ref sinkVel, 0.25f, Mathf.Infinity, dt);
            if (float.IsNaN(sink)) sink = target;
            model.localPosition = new Vector3(0, sink, 0);
        }

        /// 走路状态（测试打日志用）
        public string DebugLoco() => $"{(LastSolid != "" ? $"挡过 {LastSolid} " : "")}{loco} 相位 {GaitPhase():F2} 速度 {speedCmd:F2} 实际 {velocity.magnitude:F2} 播放 {gaitRate:F2} 权重 待机{wIdle:F2}/步态{wGait:F2}/停{wStop:F2}/转{wTurn:F2} 段{string.Join(",", Array.ConvertAll(cw, x => x.ToString("F2")), 0, Mathf.Max(1, gaitN))} 倾{lean:F1} 朝向 {transform.eulerAngles.y:F0}/{faceYaw:F0} 模型 {animator.transform.eulerAngles.y:F0}";

#if UNITY_EDITOR
        /// 编辑器里模拟游戏的一帧：动画更新，再做 LateUpdate 里的事
        public void DebugFrame(float dt)
        {
            if (graph.IsValid()) graph.Evaluate(dt);
            ApplyPose(dt);
        }

        public string DebugSink()
        {
            return $"ankle={ankle:F3} sink={sink:F3} model={model.localPosition.y:F3} root={transform.position.y:F3} 左脚={lFoot.position.y:F3} 右脚={rFoot.position.y:F3} 髋={hips.position.y:F3} 腿缩放={lThigh.localScale.x:F2} 头缩放={head.localScale.x:F2}";
        }

        /// 出预览图用：不跑游戏，直接把某个动作的某一帧和姿势摆出来（state 是 Move/Walk 时 speed 是走的速度，time 是步态相位 × 周期）
        public void EditorPose(string state, float speed, float time, Pose p, float bow)
        {
            Init();
            BuildGraph();
            if (!graph.IsValid()) return;
            bool walking = speed > 0.05f;
            GaitWeights(Mathf.Max(speed, 0.01f));
            wGait = walking ? 1 : 0;
            wIdle = 1 - wGait;
            wStop = wTurn = 0;
            Array.Clear(trW, 0, trW.Length);
            Mix(state == "SitIdle" ? 1 : 0);
            for (int i = 0; i < slots.Length; i++) slots[i].SetTime(time);
            if (walking) SyncGait(time / Mathf.Max(0.01f, gait[0].length));
            graph.Evaluate(0);
            pose = Pose.None;
            bowPhase = bow;
            SetPose(p, true);
            shown = p;
            weight = p == Pose.None ? 0 : 1;
            UpdateActions(0);
            Mix(0);
            graph.Evaluate(0);
            sink = 0;
            ApplyPose(0);
            if (nameTag != null && head != null)
            {
                nameTag.transform.position = head.position + Vector3.up * 0.36f * transform.lossyScale.y;
                if (Camera.main != null) nameTag.transform.rotation = Quaternion.LookRotation(nameTag.transform.position - Camera.main.transform.position);
            }
        }
#endif
    }
}
