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
            var clips = new[] { idleClip, walkClip, walkFastClip != null ? walkFastClip : walkClip, sitClip != null ? sitClip : idleClip };
            mixer = AnimationMixerPlayable.Create(graph, clips.Length);
            slots = new AnimationClipPlayable[clips.Length];
            for (int i = 0; i < clips.Length; i++)
            {
                slots[i] = AnimationClipPlayable.Create(graph, clips[i]);
                // 各段错开一点起点，人多的时候不会整齐划一
                slots[i].SetTime(UnityEngine.Random.value * clips[i].length);
                graph.Connect(slots[i], 0, mixer, i);
            }
            output.SetSourcePlayable(mixer);
            Mix(0, 0);
            if (Application.isPlaying) graph.Play();
        }

        /// 按速度（米/秒）和坐着的程度（0..1）给四段动画分权重
        void Mix(float speed, float sit)
        {
            float a = Mathf.InverseLerp(0.6f * walkSpeed, 1.2f * walkSpeed, speed);
            float w = Mathf.Clamp01(speed / (0.6f * walkSpeed));
            float stand = 1 - sit;
            mixer.SetInputWeight(0, stand * (1 - w));
            mixer.SetInputWeight(1, stand * w * (1 - a));
            mixer.SetInputWeight(2, stand * w * a);
            mixer.SetInputWeight(3, sit);
            // 走路动画的快慢跟着实际速度，脚不打滑
            float rate = speed > 0.05f ? Mathf.Clamp(speed / (0.8f * walkSpeed), 0.6f, 1.6f) : 1f;
            slots[1].SetSpeed(rate);
            slots[2].SetSpeed(rate);
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
            nameTag.text = text;
            nameTag.color = color;
            nameTag.gameObject.SetActive(!string.IsNullOrEmpty(text));
        }

        /// 换一个姿势。椅子上坐着（Bench）用动作库的坐姿动画，其余在站姿上叠加。
        public void SetPose(Pose p)
        {
            if (p == pose) return;
            pose = p;
            if (p != Pose.None) shown = p;

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
            faceYaw = Quaternion.LookRotation(to).eulerAngles.y;
            hasFace = true;
            return velocity * dt;
        }

        /// 这一帧的位移：有路径走路径，没有就用 Drive 给的速度。由主角控制器或香客自己调用。
        public Vector3 Motion(float dt) => path.Count > 0 ? PathStep(dt) : velocity * dt;

        public CharacterController controller;
        /// 不用碰撞胶囊走路时，高度跟着脚下的地面走
        public bool groundFollow = true;

        void Update()
        {
            float dt = Time.deltaTime;
            Vector3 move = Motion(dt);
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
                if (groundFollow && Physics.Raycast(pos + Vector3.up * 0.8f, Vector3.down, out var hit, 2.5f, ~(1 << 2), QueryTriggerInteraction.Ignore))
                    pos.y = Mathf.MoveTowards(pos.y, hit.point.y, 2.5f * dt);
                mover.position = pos;
            }
            float speed = dt > 1e-5f ? new Vector2(move.x, move.z).magnitude / dt : 0;
            if (float.IsNaN(speed) || float.IsInfinity(speed)) speed = 0;
            moveSpeed = Mathf.Lerp(moveSpeed, speed, 1 - Mathf.Exp(-10f * dt));
            bool sitting = pose == Pose.Bench || pose == Pose.CrossLegged;
            sitW = Mathf.MoveTowards(sitW, sitting ? 1 : 0, dt / 0.6f);
            if (graph.IsValid()) Mix(moveSpeed, Mathf.SmoothStep(0, 1, sitW));
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
            pose = p;
            shown = p;
            weight = p == Pose.None ? 0 : 1;
            bowPhase = bow;
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
