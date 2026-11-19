using System;
using System.Collections.Generic;
using UnityEngine;

namespace Yuanjing
{
    /// 头发、裙摆、衣带的摆动：人一动，它们慢半拍跟上、再荡回来。
    /// 做法同 VRM 的 SpringBone：每根骨头记着自己「尾巴」上一刻在哪，惯性、回弹、重力三样加起来算出这一刻在哪，
    /// 再把骨头转过去对准它。参数是从原模型里读出来的（tools/blender/vrm_import.py）。
    [DefaultExecutionOrder(200)]   // 排在动画和 Folk 摆姿势之后
    public class SpringBones : MonoBehaviour
    {
        [Serializable]
        public class Group
        {
            public Transform[] roots;
            public float stiffness = 1f, gravity = 0f, drag = 0.4f;
        }

        public List<Group> groups = new List<Group>();

        /// 碰撞球：裙子、头发会被推到球面外（裙子不会穿过大腿，坐下、跪下时搭在腿上）
        [Serializable]
        public class Sphere { public Transform from, to; public float t, radius; }
        public List<Sphere> colliders = new List<Sphere>();
        /// 只有名字里带这些字的摆动骨骼才和碰撞球碰（裙子）；头发另算
        public string collideNames = "Skirt";

        /// 头发（根骨名字以它开头的那几组）：头低下去的时候往下垂。原来的参数里头发没有重力、只有回到原样的弹力，
        /// 头一低（叩首时脸朝地、头顶朝前），头发就跟着头一起翘起来，从身后看是一根根竖着的刺。
        /// 现在：一根头发「原样」的方向比站直时往上翘了多少（lift），翘得越多，它要回的方向就越往正下方偏、重力越大（droop 是最多偏多少）；
        /// 再绕开脑袋（一个球，按头发根的位置估出来）、不穿到脚下的地面里
        public string hairNames = "HairJoint";
        public float droop = 1f, hairGravity = 1.2f;

        /// 人转身、走动时，头发、裙摆「跟着身子一起转、一起挪」的那一份（0 是全靠惯性：以前一转身、一起步，长头发横着、平着甩出去，
        /// 走起来一直平着往后飘，像顶着大风；1 是焊死在身上不动）。剩下的那一份照旧慢半拍跟上、荡回来，所以还是看得出在飘
        public float followTurn = 0.8f, followMove = 0.92f;
        /// 起步、停下、拐弯（身子快慢、方向一变）时往反方向甩一下的劲：起步往后荡、停下往前荡，匀速走着就慢慢垂回去
        public float moveKick = 2f;
        /// 头发回到原样的劲再乘几倍：原模型给的 0.4 太软
        public float hairStiffness = 2f;
        /// 头发记得整束的形（0..1）：每一节不光往「相对上一节」的原样回，也往「相对头」的原样回这么多。
        /// 原来的算法里每一节只管自己和上一节弯了多少，一长串连起来像根软绳子：走路时头一点一晃，整束头发就被晃得往后、往两边飘着回不来
        /// （不开摆动时走路头发离正下方平均 22 度，开了 50 多度）
        public float hairShape = 0.6f;
        /// 一根头发离它「原样」的方向（垂着的方向）最多偏多少度：再怎么甩也不会横着飞出去
        public float hairMaxAngle = 55f;
        Transform head;
        Vector3 headCenter;    // 脑袋那个球的球心（头骨自己坐标里）
        float headRadius;      // 半径（头骨自己坐标里的长度）
        /// 身子：髋（量身子挪了多少用它，不用原点：坐下、起身那一下原点挪 0.3 米、身子没动；跪下去身子往下沉、原点不动）、
        /// 胸口（量弯腰弯了多少）；头发碰的几个球（胸口、后背：甩过来的头发不穿过身子；只往水平方向推开，不把发梢往上顶）
        Transform hipsBone, chestBone;
        Vector3 chestUpLocal;
        readonly List<Sphere> hairBody = new List<Sphere>();
        Vector3 velF;          // 身子水平速度（平滑过的，τ 0.1 秒）：起步、停下、拐弯时甩一下按它的变化算（和帧率无关）

        class Joint
        {
            public Transform t;
            public Vector3 axis;           // 尾巴在骨头自己坐标里的方向
            public float length;           // 骨头到尾巴的距离（局部长度，乘上缩放才是世界里的）
            public Quaternion rest;        // 静止时相对父骨头的转角
            public Vector3 tail, prev;
            public Group g;
            public bool collide, hair;
            public float refUp;            // 站直（绑定姿势）时「原样」方向和正上方的点积
            public Vector3 headDir;        // 站直时这一节在头骨自己坐标里的方向（头发整束的「形」）
        }

        readonly List<Joint> joints = new List<Joint>();
        Vector3 lastRoot, lastJump;
        float lastYaw;
        /// 上一帧没算（离镜头太远）：再算的时候从骨头现在的样子重新起头，不接着用好几秒以前的尾巴位置
        bool paused;

        void Start()
        {
            var hairRoots = new List<Transform>();
            foreach (var g in groups)
                foreach (var r in g.roots)
                    if (r != null)
                    {
                        bool hair = !string.IsNullOrEmpty(hairNames) && r.name.StartsWith(hairNames);
                        if (hair) hairRoots.Add(r);
                        Add(r, g, hair);
                    }
            lastRoot = BodyPos;
            lastYaw = transform.eulerAngles.y;
            var animH = GetComponentInChildren<Animator>() ?? GetComponentInParent<Animator>();
            var headBone = animH != null && animH.isHuman ? animH.GetBoneTransform(HumanBodyBones.Head) : null;
            if (headBone != null)
                foreach (var j in joints)
                    if (j.hair) j.headDir = Quaternion.Inverse(headBone.rotation) * (j.t.rotation * j.axis);
            // 脑袋的球：球心在头骨上方（头发根最高那一点的六成高），半径是头发根到球心距离的中位数的四分之三
            var anim = GetComponentInChildren<Animator>() ?? GetComponentInParent<Animator>();
            head = anim != null && anim.isHuman ? anim.GetBoneTransform(HumanBodyBones.Head) : null;
            if (anim != null && anim.isHuman)
            {
                hipsBone = anim.GetBoneTransform(HumanBodyBones.Hips);
                chestBone = anim.GetBoneTransform(HumanBodyBones.UpperChest) ?? anim.GetBoneTransform(HumanBodyBones.Chest);
                var neck = anim.GetBoneTransform(HumanBodyBones.Neck);
                if (chestBone != null) chestUpLocal = Quaternion.Inverse(chestBone.rotation) * Vector3.up;
                if (hipsBone != null && neck != null && chestBone != null)
                {
                    // 半径按髋到脖子的长度（1.25 米的人约 0.42 米）定：胸口 0.3 倍、后背（脊椎）0.27 倍、上臂 0.1 倍；都是骨头自己坐标里的长度
                    float spine = Vector3.Distance(hipsBone.position, neck.position) / Mathf.Max(1e-4f, transform.lossyScale.y);
                    var spineB = anim.GetBoneTransform(HumanBodyBones.Spine);
                    hairBody.Add(new Sphere { from = chestBone, to = neck, t = 0.15f, radius = spine * 0.3f });
                    if (spineB != null) hairBody.Add(new Sphere { from = spineB, to = chestBone, t = 0.5f, radius = spine * 0.27f });
                    // 上臂不加球：走起来胳膊一摆，球从下面把发梢往上顶，头发一下翘起来（HairSwingTest 起步那一段 115 度）
                }
            }
            if (head != null && hairRoots.Count > 0)
            {
                // 这时还是绑定姿势（站直）：按世界里的上下量，再换成头骨自己坐标里的
                float top = 0;
                foreach (var r in hairRoots) top = Mathf.Max(top, Vector3.Dot(r.position - head.position, Vector3.up));
                Vector3 c = head.position + Vector3.up * top * 0.6f;
                headCenter = head.InverseTransformPoint(c);
                var d = new List<float>();
                foreach (var r in hairRoots) d.Add((r.position - c).magnitude);
                d.Sort();
                headRadius = d[d.Count / 2] * 0.75f / Mathf.Max(1e-4f, head.lossyScale.y);
            }
        }

        /// 量身子挪了多少用的那一点：髋（没有就用原点）
        Vector3 BodyPos => hipsBone != null ? hipsBone.position : transform.position;

        void Add(Transform t, Group g, bool hair)
        {
            Vector3 local = t.childCount > 0 ? t.GetChild(0).localPosition : Vector3.up * 0.05f;
            if (local.sqrMagnitude < 1e-8f) local = Vector3.up * 0.05f;
            var j = new Joint { t = t, axis = local.normalized, length = local.magnitude, rest = t.localRotation, g = g, hair = hair,
                                collide = !string.IsNullOrEmpty(collideNames) && t.name.Contains(collideNames) };
            j.tail = j.prev = t.TransformPoint(local);
            Quaternion parent = t.parent != null ? t.parent.rotation : Quaternion.identity;
            j.refUp = Vector3.Dot(parent * j.rest * j.axis, Vector3.up);
            joints.Add(j);
            for (int i = 0; i < t.childCount; i++) Add(t.GetChild(i), g, hair);
        }

        void LateUpdate()
        {
            float dt = Mathf.Min(Time.deltaTime, 0.05f);
            if (dt <= 0f) return;
            // 离镜头远的人，头发怎么摆都看不出来：省下这份计算（几十个人同时在场）
            var cam = Camera.main;
            if (cam != null && (cam.transform.position - transform.position).sqrMagnitude > Mathf.Pow(18f * Mathf.Max(1f, 40f / cam.fieldOfView), 2f))
            {
                lastRoot = BodyPos;
                lastYaw = transform.eulerAngles.y;
                lastJump = Vector3.zero;
                velF = Vector3.zero;
                paused = true;
                return;
            }
            // 俯视（镜头二十多米外）时没算：尾巴还停在好几秒以前、走过的路上。一换平视（进殿就是这样）再接着算，头发就朝那边横着飞出去。
            // 所以先按骨头现在的样子（停算时最后一帧的样子，跟着头）把尾巴摆回去，从静止起头
            if (paused)
            {
                paused = false;
                foreach (var j in joints)
                {
                    j.tail = j.prev = j.t.TransformPoint(j.axis * j.length);
                }
            }
            // 被瞬移了（进场、传送）：别让头发甩一大圈，直接跟过去。
            // 按髋量（不按原点）：坐下、起身时原点一下挪到蒲团上、挪回草垫上，身子其实没动，头发也不该被甩；跪下去身子往下沉，头发跟着沉（以前飞起来）
            Vector3 root = BodyPos;
            Vector3 jump = root - lastRoot;
            bool teleported = jump.sqrMagnitude > 1.5f * 1.5f;
            // 这一帧身子绕竖轴转了多少、挪了多少：跟着转、跟着挪的那一份直接带上尾巴（这一帧和上一帧的一起带，不改它自己荡的速度）
            float yawNow = transform.eulerAngles.y;
            Quaternion turn = Quaternion.AngleAxis(Mathf.DeltaAngle(lastYaw, yawNow) * followTurn, Vector3.up);
            Vector3 carry = jump * followMove;
            // 身子快慢、方向一变（起步、停下、拐弯）：尾巴往反方向甩一下。按平滑过的水平速度的变化（加速度 × dt²）算，
            // 掉一帧（16 → 33 毫秒）不会被当成猛一停、猛一起（以前按每帧挪了多少的差算，手机上一卡头发、裙摆就一抖）
            Vector3 v = teleported ? Vector3.zero : new Vector3(jump.x, 0f, jump.z) / dt;
            Vector3 velPrev = velF;
            velF = teleported ? Vector3.zero : Vector3.Lerp(velF, v, 1f - Mathf.Exp(-dt / 0.1f));
            Vector3 kick = teleported ? Vector3.zero : -(velF - velPrev) * dt * moveKick;
            float kmax = 0.02f * dt * 60f;
            if (kick.sqrMagnitude > kmax * kmax) kick = kick.normalized * kmax;
            lastJump = teleported ? Vector3.zero : jump;
            // 弯腰弯了多少度（胸口朝上的方向离正上方）：鞠躬、拿着香拜、插香时头发不再「记着」站直时的形（那样会平着翘在脑后），往下垂
            float pitch = chestBone != null ? Vector3.Angle(chestBone.rotation * chestUpLocal, Vector3.up) : 0f;
            float shapeK = hairShape * (1f - Mathf.Clamp01(pitch / 40f));
            float bowDroop = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(10f, 45f, pitch));
            Vector3 pivot = lastRoot;
            lastRoot = root;
            lastYaw = yawNow;
            float scale = transform.lossyScale.y;
            foreach (var j in joints)
            {
                if (teleported) { j.tail += jump; j.prev += jump; }
                else
                {
                    j.tail = pivot + turn * (j.tail - pivot) + carry;
                    j.prev = pivot + turn * (j.prev - pivot) + carry;
                }
                Quaternion parent = j.t.parent != null ? j.t.parent.rotation : Quaternion.identity;
                Quaternion restWorld = parent * j.rest;
                Vector3 pos = j.t.position;
                float len = j.length * scale;
                Vector3 want = restWorld * j.axis;
                // 头发：也往「整束跟着头」的那个方向回一些（见 hairShape）
                if (j.hair && head != null && shapeK > 0f && j.headDir != Vector3.zero) want = Vector3.Slerp(want, head.rotation * j.headDir, shapeK);
                float grav = j.g.gravity;
                if (j.hair && droop > 0f)
                {
                    // 头低下去、这根头发「原样」比站直时往上翘了：往正下方垂（翘得越多垂得越多；以前翘到 0.2 才开始垂，鞠躬时后面的长发平着翘在脑后）；
                    // 弯腰本身也让它垂（见 bowDroop）
                    float lift = Vector3.Dot(want, Vector3.up) - j.refUp;
                    float w = droop * Mathf.Max(Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.05f, 0.6f, lift)), 0.85f * bowDroop);
                    if (w > 0f)
                    {
                        want = Vector3.Slerp(want, Vector3.down, w);
                        grav += hairGravity * w;
                    }
                }
                // 惯性按每秒算（原来的算法是按每秒 60 帧定的：帧数不同、荡得不同）
                float keep = Mathf.Pow(Mathf.Clamp01(1f - j.g.drag), dt * 60f);
                Vector3 next = j.tail + (j.tail - j.prev) * keep
                               + want * (j.g.stiffness * (j.hair ? hairStiffness : 1f) * dt * scale)
                               + Vector3.down * (grav * dt * scale)
                               + kick;
                next = pos + (next - pos).normalized * len;
                if (j.hair && hairMaxAngle < 179f)
                {
                    // 离垂着的方向偏得太多（转身、起步时横着、平着甩出去）：拉回到 hairMaxAngle 以内
                    Vector3 dir = (next - pos) / Mathf.Max(len, 1e-6f);
                    float ang = Vector3.Angle(want, dir);
                    if (ang > hairMaxAngle) next = pos + Vector3.Slerp(want.normalized, dir, hairMaxAngle / ang) * len;
                }
                if (j.hair && head != null && headRadius > 0f)
                {
                    // 绕开脑袋；不钻到地面（人脚下那一层）下面去
                    Vector3 hc = head.TransformPoint(headCenter);
                    float hr = headRadius * head.lossyScale.y;
                    Vector3 d = next - hc;
                    if (d.sqrMagnitude < hr * hr && d.sqrMagnitude > 1e-8f) next = pos + ((hc + d.normalized * hr) - pos).normalized * len;
                    float floor = transform.position.y + 0.01f;
                    if (next.y < floor && pos.y > floor)
                    {
                        next.y = floor;
                        next = pos + (next - pos).normalized * len;
                    }
                    // 不穿过胸口、后背、上臂
                    foreach (var c in hairBody)
                    {
                        Vector3 cp = Vector3.Lerp(c.from.position, c.to.position, c.t);
                        float r = c.radius * scale;
                        Vector3 dd = next - cp;
                        if (dd.sqrMagnitude < r * r && dd.sqrMagnitude > 1e-8f && (pos - cp).sqrMagnitude > r * r * 0.81f)
                        {
                            // 只往水平方向推出球外（发梢顺着身子往下滑，不被顶上去）
                            Vector3 hz = new Vector3(dd.x, 0f, dd.z);
                            if (hz.sqrMagnitude < 1e-8f) continue;
                            float need = Mathf.Sqrt(Mathf.Max(0f, r * r - dd.y * dd.y));
                            Vector3 q = cp + new Vector3(0f, dd.y, 0f) + hz.normalized * need;
                            next = pos + (q - pos).normalized * len;
                        }
                    }
                }
                if (j.collide)
                    foreach (var c in colliders)
                    {
                        if (c.from == null) continue;
                        Vector3 cp = c.to != null ? Vector3.Lerp(c.from.position, c.to.position, c.t) : c.from.position;
                        float r = c.radius * scale;
                        Vector3 d = next - cp;
                        if (d.sqrMagnitude < r * r && d.sqrMagnitude > 1e-8f) next = pos + ((cp + d.normalized * r) - pos).normalized * len;
                    }
                j.prev = j.tail;
                j.tail = next;
                j.t.rotation = Quaternion.FromToRotation(restWorld * j.axis, next - pos) * restWorld;
            }
        }
    }
}
