using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Animations;
using UnityEngine.Playables;

namespace Yuanjing
{
    /// 殿里的一个小人（自己或者别人）。动作库给走路、站着、坐椅子的动画；
    /// 动作库里没有的姿势（合掌、鞠躬、跪拜、盘坐）在动画之上直接改关节角度，平滑地混进去。
    public class Folk : MonoBehaviour
    {
        public enum Pose { None, Gassho, Bow, Kneel, KneelBow, CrossLegged, Bench, Custom }

        /// 调姿势用：Custom 姿势下直接按名字设的关节值，pitch 是整个身体往前倾的角度
        public Dictionary<string, float> custom = new Dictionary<string, float>();
        public float customPitch;

        public Animator animator;
        /// 动画：站着、慢走、快走、坐着。直接用播放图按速度混合（不经过状态机：状态机在手机版里取不到片段）
        public AnimationClip idleClip, walkClip, walkFastClip, sitClip;
        /// 合掌、鞠躬、跪拜、盘坐的动作（tools/blender/pray_motions.py 做的关键帧，Assets/Motion/）。有就用它们，没有才用老办法硬改关节
        public AnimationClip[] actionClips;
        /// 几段站立待机（动捕），每人挑一段
        public AnimationClip[] idleClips;
        /// 装模型的子物体：坐下、跪下时整个往下沉，靠它
        public Transform model;
        public TextMesh nameTag;
        /// 名字的大小随镜头远近变：每米放大多少、最大多大、多远以外不显示。由镜头脚本按自己的远近来设
        public static float TagScalePerMeter = 0.24f, TagMaxScale = 2.4f, TagHideBeyond = 26f;
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

        HumanPoseHandler handler;
        HumanPose hp;
        float weight;            // 现在的姿势混进去多少（0..1）
        Pose shown;              // 正在显示（或者正在淡出）的姿势
        float bowPhase;          // 鞠躬：0 直起，1 俯到最低
        float sink, sinkVel;
        Transform head, hips, lFoot, rFoot, lKnee, rKnee, neck, lThigh, rThigh, lArm, rArm;
        float ankle;

        /// 关节的缩放：动画只管转动，不碰缩放，但姿势混合会把骨骼重设一遍，所以每帧都补一次
        void ApplyProportions()
        {
            if (neck != null) neck.localScale = Vector3.one * neckScale;
            if (head != null) head.localScale = Vector3.one * (headScale / neckScale);
            if (lThigh != null) lThigh.localScale = rThigh.localScale = Vector3.one * legScale;
            if (lArm != null) lArm.localScale = rArm.localScale = Vector3.one * armScale;
        }
        readonly Queue<Vector3> path = new Queue<Vector3>();
        Vector3 velocity;
        float faceYaw, stepDist;
        bool hasFace;
        static int[] muscleIndex;
        static readonly Dictionary<string, int> muscleByName = new Dictionary<string, int>();

        void Awake() => Init();

        PlayableGraph graph;
        AnimationMixerPlayable mixer;
        AnimationClipPlayable[] slots;
        float sitW, moveSpeed;

        /// 建播放图：四段动画接进一个混合器，权重每帧按速度和坐没坐着算
        void BuildGraph()
        {
            if (graph.IsValid() || idleClip == null) return;
            animator.runtimeAnimatorController = null;
            graph = PlayableGraph.Create("Folk_" + name);
            graph.SetTimeUpdateMode(DirectorUpdateMode.GameTime);
            var output = AnimationPlayableOutput.Create(graph, "anim", animator);
            if (idleClips != null && idleClips.Length > 0) idleClip = idleClips[Mathf.Abs(name.GetHashCode()) % idleClips.Length];
            var baseClips = new[] { idleClip, walkClip, walkFastClip != null ? walkFastClip : walkClip, sitClip != null ? sitClip : idleClip };
            var clips = new List<AnimationClip>(baseClips);
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
            mixer = AnimationMixerPlayable.Create(graph, clips.Count);
            slots = new AnimationClipPlayable[clips.Count];
            for (int i = 0; i < clips.Count; i++)
            {
                slots[i] = AnimationClipPlayable.Create(graph, clips[i]);
                // 脚贴地：人形动画按原来脚的位置修正
                slots[i].SetApplyFootIK(true);
                // 各段错开一点起点，人多的时候不会整齐划一
                slots[i].SetTime(UnityEngine.Random.value * clips[i].length);
                graph.Connect(slots[i], 0, mixer, i);
            }
            output.SetSourcePlayable(mixer);
            Mix(0, 0);
            if (Application.isPlaying) graph.Play();
        }

        // ── 动作段：合掌、鞠躬、跪拜、盘坐 ──
        // 播放图里除了走路、待机那四段，还挂着每一段动作；同一时间只有一段动作在播，换段时交叉淡化 0.25 秒。
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
        bool UseActions => actionClips != null && actionClips.Length > 0 && Pose_Allowed(shown);
        static bool Pose_Allowed(Pose p) => p != Pose.Bench && p != Pose.Custom;

        bool Has(string n) => actIndex.ContainsKey(n);

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
                case Pose.None:
                    if (instant) break;
                    if (kneeling) actQueue.Enqueue("Kneel_Up");
                    else if (old == Pose.CrossLegged) actQueue.Enqueue("Sit_Up");
                    else if (standUp) actQueue.Enqueue("Gassho_Out");
                    break;
            }
            actQueue.TrimExcess();
            // 正在播一段过渡（跪下去、坐下去、起身）还没播完：等它播完再接新的，不从半截切走
            bool midTransition = !instant && actNow != null && !actNow.EndsWith("_Loop") && !actNow.EndsWith("_Scrub")
                                 && slots[actIndex[actNow]].GetTime() < actionClips[actIndex[actNow] - 4].length - 0.15f;
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
            sl.SetTime(n.EndsWith("_Loop") ? UnityEngine.Random.value * actionClips[actIndex[n] - 4].length : 0);
            sl.SetSpeed(n.EndsWith("_Scrub") ? 0 : 1);
            if (instant) for (int i = 0; i < actWeight.Length; i++) actWeight[i] = i == actIndex[n] - 4 ? 1 : 0;
        }

        /// 每帧：推进动作段（播完的段接下一段；拖着播的段按鞠躬进度定时刻），淡化各段权重
        void UpdateActions(float dt)
        {
            if (actWeight == null) return;
            if (actNow != null)
            {
                int i = actIndex[actNow];
                var clip = actionClips[i - 4];
                if (actNow.EndsWith("_Scrub")) slots[i].SetTime(Mathf.SmoothStep(0, 1, bowPhase) * clip.length * 0.999f);
                else if (!actNow.EndsWith("_Loop") && slots[i].GetTime() >= clip.length - 0.12f)
                {
                    if (actQueue.Count > 0) Next(false);
                    else if (pose == Pose.None)
                    {
                        // 从蒲团上站起来：原点挪到人站的地方，立刻换回站姿（不淡出，淡出的那一下身子会往回飘）
                        if (actNow == "Sit_Up") { GlideSeat(); sitGlide = false; actW = 0; for (int j = 0; j < actWeight.Length; j++) actWeight[j] = 0; }
                        actTarget = 0;
                    }
                }
                // 合掌、盘坐时又要低头鞠躬：换成拖着播的那段，起来以后换回循环
                string scrub = pose == Pose.Gassho ? "Gassho_Scrub" : pose == Pose.CrossLegged ? "SitBow_Scrub" : null;
                string loop = pose == Pose.Gassho ? "Gassho_Loop" : pose == Pose.CrossLegged ? "Sit_Loop" : null;
                if (scrub != null && actQueue.Count == 0 && Has(scrub))
                {
                    if (bowPhase > 0.001f && actNow == loop) { actQueue.Enqueue(scrub); Next(false); }
                    else if (bowPhase <= 0.001f && actNow == scrub) { actQueue.Enqueue(loop); Next(false); }
                }
            }
            float k = dt <= 0 ? 1 : Mathf.Clamp01(dt / 0.25f);
            for (int j = 0; j < actWeight.Length; j++)
            {
                bool on = actNow != null && actIndex[actNow] - 4 == j;
                actWeight[j] = Mathf.MoveTowards(actWeight[j], on ? 1 : 0, k);
            }
            actW = Mathf.MoveTowards(actW, actTarget, dt <= 0 ? 1 : dt / 0.35f);
            if (actW <= 0.001f && actTarget == 0) actNow = null;
            float sum = 0;
            foreach (float w in actWeight) sum += w;
            for (int j = 0; j < actWeight.Length; j++)
                mixer.SetInputWeight(4 + j, sum > 1e-4f ? actWeight[j] / sum * actW : 0);
        }

        /// 按速度（米/秒）和坐着的程度（0..1）给四段动画分权重
        void Mix(float speed, float sit)
        {
            float a = Mathf.InverseLerp(0.6f * walkSpeed, 1.2f * walkSpeed, speed);
            float w = Mathf.Clamp01(speed / (0.6f * walkSpeed));
            float stand = 1 - sit;
            float rest = 1 - Mathf.Clamp01(actW);
            // 待机：几段之间慢慢换（1.5 秒淡入淡出）
            float idleTotal = rest * stand * (1 - w);
            if (idleW != null && idleW.Length > 1)
            {
                float dt = Time.deltaTime;
                if (w < 0.01f && actW < 0.01f && (idleNext -= dt) <= 0)
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
            mixer.SetInputWeight(1, rest * stand * w * (1 - a));
            mixer.SetInputWeight(2, rest * stand * w * a);
            mixer.SetInputWeight(3, rest * sit);
            // 走路动画的快慢：按这段动画自己一秒走多远（换算到这个人的身高）来定，脚不打滑
            for (int i = 1; i <= 2; i++)
            {
                var c = i == 1 ? walkClip : (walkFastClip != null ? walkFastClip : walkClip);
                float clipSpeed = c.averageSpeed.magnitude * (animator.isHuman ? animator.humanScale : 1f) * transform.lossyScale.y;
                float rate = speed > 0.05f ? Mathf.Clamp(speed / Mathf.Max(0.05f, clipSpeed > 0.05f ? clipSpeed : 0.8f * walkSpeed), 0.5f, 1.8f) : 1f;
                slots[i].SetSpeed(rate);
            }
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
            // 脚踝离地多高（骨骼还在初始姿势时量）：缩腿以后靠它把脚放回地面
            ankle = (Mathf.Min(lFoot.position.y, rFoot.position.y) - model.position.y) / Mathf.Max(transform.lossyScale.y, 0.001f);
            ApplyProportions();
            if (muscleByName.Count == 0)
                for (int i = 0; i < HumanTrait.MuscleCount; i++) muscleByName[HumanTrait.MuscleName[i]] = i;
            faceYaw = transform.eulerAngles.y;
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
            if (UseActions) QueueFor(old, p, instant);

        }

        /// 坐下前站在圆蒲团前面多远（米，按 1.25 米高的人；见 tools/blender/pray_motions.py 的 STAND_Y × 0.806）
        public const float SeatStep = 0.24f;

        /// 坐下、起身、跪下这些过渡动作正在播：这时人不挪地方（不然脚在地上滑）
        public bool InTransition => actNow != null && actW > 0.5f && (actNow.EndsWith("_Up") || actNow.EndsWith("_Down"));

        /// 坐到蒲团上：人站在蒲团前面的草垫上，面朝 yaw。坐下那段动作播的时候，人一边蹲一边往后挪到蒲团上（挪的节奏跟着动作），
        /// 起身时反过来挪回草垫上
        public void SitOn(Vector3 seatGround, float yaw)
        {
            path.Clear();
            velocity = Vector3.zero;
            var mover = controller != null ? controller.transform : transform;
            if (controller != null) controller.enabled = false;
            sitFrom = new Vector3(mover.position.x, seatGround.y, mover.position.z);
            sitTo = seatGround;
            sitGlide = GlideMode;
            if (!GlideMode) mover.position = seatGround;
            transform.rotation = Quaternion.Euler(0, yaw, 0);
            faceYaw = yaw;
            hasFace = true;
            SetPose(Pose.CrossLegged);
            // 原点刚挪到蒲团下：坐下那段的第一帧身子正好在前面草垫上，直接换过去不淡入（淡入的那 0.25 秒身子会先缩回蒲团上再走出来）
            if (!GlideMode && actNow != null && actIndex.TryGetValue(actNow, out int i))
            {
                actW = 1;
                for (int j = 0; j < actWeight.Length; j++) actWeight[j] = j == i - 4 ? 1 : 0;
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
        }

        /// 站起来那段动作播完时，身子在原点前面一步（草垫上）：把原点挪过去，再交给走路、待机
        void Recenter()
        {
            if (hips == null) return;
            Vector3 off = hips.position - transform.position;
            off.y = 0;
            if (off.magnitude < 0.05f || off.magnitude > 0.6f) return;
            var mover = controller != null ? controller.transform : transform;
            bool cc = controller != null && controller.enabled;
            if (cc) controller.enabled = false;
            mover.position += off;
            if (cc) controller.enabled = true;
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
            foreach (var p in points) path.Enqueue(p);
            SetPose(Pose.None);
        }

        public void StopWalking()
        {
            path.Clear();
        }

        /// 直接给一个速度（摇杆用）。会被走路径打断。
        public void Drive(Vector3 v)
        {
            path.Clear();
            velocity = Vector3.ClampMagnitude(v, walkSpeed * 1.35f);
            if (velocity.sqrMagnitude > 0.0004f)
            {
                faceYaw = Quaternion.LookRotation(velocity).eulerAngles.y;
                hasFace = true;
                if (pose != Pose.None) SetPose(Pose.None);
            }
        }

        /// 自己移动（没有 CharacterController 的香客）。返回这一帧想走的位移。
        Vector3 PathStep(float dt)
        {
            if (path.Count == 0) return Vector3.zero;
            Vector3 target = path.Peek();
            Vector3 to = target - transform.position;
            to.y = 0;
            float dist = to.magnitude;
            float speed = walkSpeed * Mathf.Clamp(dist * 1.6f + 0.35f, 0.35f, 1f);
            float step = speed * dt;
            if (dist <= Mathf.Max(step, 0.02f))
            {
                path.Dequeue();
                if (path.Count == 0)
                {
                    velocity = Vector3.zero;
                    Arrived?.Invoke();
                }
                return to;
            }
            velocity = to / dist * speed;
            // 避让：前面 0.9 米内有人，就往侧边让一点（各自往右让，不会两人原地顶牛）
            Vector3 dir = to / dist, side = Vector3.Cross(Vector3.up, dir);
            Vector3 push = Vector3.zero;
            Vector3 me = transform.position;
            foreach (var o in All)
            {
                if (o == this || o == null) continue;
                Vector3 d = o.transform.position - me;
                d.y = 0;
                float m = d.magnitude;
                if (m > 0.9f || m < 1e-3f) continue;
                float ahead = Vector3.Dot(d, dir);
                if (ahead < -0.1f) continue;
                float k = (0.9f - m) / 0.9f;
                push -= d / m * k * 0.6f;
                push += side * k * 0.5f;
            }
            if (dist > 0.3f) velocity += push * speed;
            faceYaw = Quaternion.LookRotation(to).eulerAngles.y;
            hasFace = true;
            return velocity * dt;
        }

        /// 这一帧的位移：有路径走路径，没有就用 Drive 给的速度。由主角控制器或香客自己调用。
        public Vector3 Motion(float dt) => InTransition ? Vector3.zero : path.Count > 0 ? PathStep(dt) : velocity * dt;

        public CharacterController controller;
        /// 不用碰撞胶囊走路时，高度跟着脚下的地面走
        public bool groundFollow = true;

        void Update()
        {
            float dt = Time.deltaTime;
            Vector3 move = Motion(dt);
            var moverT = controller != null ? controller.transform : transform;
            Vector3 before = moverT.position;
            if (controller != null && controller.enabled)
            {
                move.y = -2f * dt;
                controller.Move(move);
            }
            else
            {
                // 没有碰撞胶囊（香客，或者自己在自动走路线）：水平移动，高度贴着脚下的地面、台阶、蒲团
                var mover = controller != null ? controller.transform : transform;
                Vector3 pos = mover.position + new Vector3(move.x, 0, move.z);
                // 坐着、跪着的时候不跟着地面走（坐下时原点就放在蒲团下面的地上，草垫的碰撞会把人顶高）
                if (groundFollow && pose == Pose.None && Physics.Raycast(pos + Vector3.up * 0.8f, Vector3.down, out var hit, 2.5f, ~(1 << 2), QueryTriggerInteraction.Ignore))
                    pos.y = Mathf.MoveTowards(pos.y, hit.point.y, 2.5f * dt);
                mover.position = pos;
            }
            // 走路动画的快慢按「真正走了多远」算：撞到东西被挡住时脚不会在原地蹭
            Vector3 moved = moverT.position - before;
            float speed = dt > 1e-5f ? Mathf.Min(new Vector2(move.x, move.z).magnitude, new Vector2(moved.x, moved.z).magnitude) / dt : 0;
            if (float.IsNaN(speed) || float.IsInfinity(speed)) speed = 0;
            moveSpeed = Mathf.Lerp(moveSpeed, speed, 1 - Mathf.Exp(-10f * dt));
            bool sitting = pose == Pose.Bench || pose == Pose.CrossLegged;
            sitW = Mathf.MoveTowards(sitW, sitting ? 1 : 0, dt / 0.6f);
            if (graph.IsValid())
            {
                UpdateActions(dt);
                GlideSeat();
                Mix(moveSpeed, actionClips != null && actionClips.Length > 0 && pose == Pose.CrossLegged ? 0 : Mathf.SmoothStep(0, 1, sitW));
            }
            stepDist += speed * dt;
            if (stepDist > 0.42f)
            {
                stepDist = 0;
                Step?.Invoke();
            }
            if (hasFace)
                transform.rotation = Quaternion.Euler(0, Mathf.LerpAngle(transform.eulerAngles.y, faceYaw, 1f - Mathf.Exp(-9f * dt)), 0);
            weight = Mathf.MoveTowards(weight, pose == Pose.None ? 0 : 1, dt / 0.7f);
        }

        float debugT;

        void LateUpdate()
        {
            ApplyPose(Time.deltaTime);
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
                    r.enabled = d > 1.6f && d < TagHideBeyond;
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

        void ApplyPose(float dt)
        {
            // 模型被隐藏时动画不再刷新骨骼，这时不能再去改姿势
            if (handler == null || !model.gameObject.activeInHierarchy) return;
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

        /// 出预览图用：不跑游戏，直接把某个动作的某一帧和姿势摆出来
        public void EditorPose(string state, float speed, float time, Pose p, float bow)
        {
            Init();
            BuildGraph();
            if (!graph.IsValid()) return;
            Mix(speed, state == "SitIdle" ? 1 : 0);
            for (int i = 0; i < slots.Length; i++) slots[i].SetTime(time);
            graph.Evaluate(0);
            pose = Pose.None;
            bowPhase = bow;
            SetPose(p, true);
            shown = p;
            weight = p == Pose.None ? 0 : 1;
            UpdateActions(0);
            Mix(speed, 0);
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
