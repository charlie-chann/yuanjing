using UnityEngine;

namespace Yuanjing
{
    /// 第三人称镜头：在自己的小人斜后上方跟着。拖动画面绕着人转、上下看；
    /// 镜头和人之间被墙、柱子挡住时往人身边收，不穿墙。人坐下、做动作时，镜头慢慢转到人背后。
    public class ThirdPersonCamera : PlayerCamera
    {
        public float distance = 3.3f, height = 0.95f, minPitch = -8f, maxPitch = 55f;
        public LayerMask blockers = ~0;

        float yaw, pitch = 16f, yawTarget, pitchTarget = 16f, dist;
        float lastTouch = -100f;
        bool snapped;
        Vector3 lastTarget, vel;
        /// 走路时镜头慢慢绕到人身后（每秒最多转几度）
        public float autoTurn = 40f;
        /// 在屋里（大殿里）：镜头不高过天花板（梁底下 0.3 米），被墙挡住时可以收得很近（柱子在不挡镜头的那一层，照样穿过去）
        public bool interior;
        public float ceiling = 5.35f;
        /// 屋里镜头的高低：比外面低（比人的腰高一点，稍低于转轴），从人身后平平地、略往上看过去，不是从上往下压着看
        public float interiorPitch = -2f;
        /// 屋里要尽量整个放进画面的几点（三尊佛像的头顶）：镜头水平朝向 25 度以内的那一尊，画面往上抬，
        /// 让它的头顶在 statueLine 那条线以下——人在画面下半，佛像整尊在上面，不会只拍到胸口、头被切掉（见 FrameTilt）。
        /// 手指拖过画面就不再自动抬（照手指的来），下一次走到某处、坐下、跪下（Settle）或者 Snap 再接着管
        public Vector3[] lookAts = new Vector3[0];
        /// 画面上下被界面挡着的那两截（占屏幕高的比例，Flutter 那边）：上面是状态栏、地名、「离开」和天色的牌子，下面是一排木牌和摇杆。
        /// 人要整个落在中间露出来的那一截里：脚不低于 uiBottom 那条线、头顶不高于 uiTop 那条线；
        /// 殿里正前方那尊佛像的头顶尽量不高于 statueLine（地名三秒就淡掉，佛像的头可以伸到上面那截里一点）
        public float uiTop = 0.10f, uiBottom = 0.20f, statueLine = 0.07f;
        /// 量头顶用的身高（站着的；坐着、跪着更矮，按站着的留不碍事）
        public float bodyHeight = 1.3f;
        /// 屋里镜头不往这几块里钻（供桌、佛坛前那一片：桌上有香炉、烛台，没有碰撞）：镜头落进去就抬到它上面，从高处越过桌上的东西看人
        public Bounds[] keepOut = new Bounds[0];
        public float maxTilt = 22f;
        float tilt, tiltTarget;
        bool userAim;
        Camera cam;
        /// 调试用：此刻往上抬了几度
        public float Tilt => tilt;

        public override float Yaw => yaw;

        void Awake()
        {
            // 和别的跟法挂在同一台镜头上时（ViewSwitcher），这些由它统一管
            if (GetComponent<ViewSwitcher>() != null) return;
            Folk.TagScalePerMeter = 0.24f;
            Folk.TagMaxScale = 2.4f;
            Folk.TagHideBeyond = 26f;
            Shader.SetGlobalVector("_YJSee", Vector4.zero);
            Shader.SetGlobalFloat("_YJCloud", 0f);
        }
        /// 调试用：现在镜头离人多远、是不是被挡住了
        public float CurrentDistance => dist;
        public string LastHit = "";

        /// 手指拖动：dx、dy 是移动占屏幕宽高的比例
        public override void Look(float dx, float dy)
        {
            yawTarget += dx * 220f;
            pitchTarget = Mathf.Clamp(pitchTarget - dy * 120f, minPitch, maxPitch);
            lastTouch = Time.time;
            // 手指拖过：屋里的自动抬头停在现在这样，照手指的来
            userAim = true;
            tiltTarget = tilt;
        }

        /// 直接定高低（换视角、进屋时程序自己定的，不算手指拖过）
        public void Pitch(float p)
        {
            pitchTarget = Mathf.Clamp(p, minPitch, maxPitch);
        }

        /// 直接摆到人背后（进场时）
        public override void Snap(float facingYaw)
        {
            yaw = yawTarget = facingYaw;
            pitch = pitchTarget = interior ? interiorPitch : 16f;
            dist = distance * zoomScale;
            snapped = true;
            userAim = false;
            tilt = tiltTarget = FrameTilt(Orbit(target.position + Vector3.up * height, yaw, pitch, distance));
            Apply(0);
        }

        /// 慢慢转到某个方向（坐下、走到某处以后，让画面朝向要看的东西）
        public override void Settle(float facingYaw, float pitchWanted = 14f)
        {
            if (Time.time - lastTouch < 3f) return;
            yawTarget = yaw + Mathf.DeltaAngle(yaw, facingYaw);
            pitchTarget = pitchWanted;
            userAim = false;
        }

        /// 从 pivot 往后退 d 米（水平朝向 y、高低 p）的镜头位置和朝向（不管墙）
        static (Vector3 pos, Quaternion rot) Orbit(Vector3 pivot, float y, float p, float d)
        {
            Vector3 pos = pivot + Quaternion.Euler(p, y, 0) * Vector3.back * d;
            return (pos, Quaternion.LookRotation(pivot + Vector3.up * 0.1f - pos));
        }

        /// 竖屏上从上往下 s 处（0 顶 1 底）那条线，比画面中线高几度（视角 fov）
        public static float LineAngle(float s, float fov) => Mathf.Atan((1f - 2f * s) * Mathf.Tan(fov * 0.5f * Mathf.Deg2Rad)) * Mathf.Rad2Deg;

        /// 从 eye 看 p 的仰角（度，往上为正）
        public static float Elevation(Vector3 eye, Vector3 p)
        {
            Vector3 v = p - eye;
            return Mathf.Atan2(v.y, new Vector2(v.x, v.z).magnitude) * Mathf.Rad2Deg;
        }

        /// 画面中线该朝上多少度（仰角）：low 落在 bottom 那条线以上、high 落在 top 那条线以下；两样都放得下就取 want（夹在中间），
        /// 放不下先保住 high（头、香、布条比脚要紧）
        public static float FrameCenter(Vector3 eye, Vector3 low, Vector3 high, float fov, float top, float bottom, float want)
        {
            float hi = Elevation(eye, low) - LineAngle(bottom, fov);
            float lo = Elevation(eye, high) - LineAngle(top, fov);
            if (lo > hi) return lo;
            return Mathf.Clamp(want, lo, hi);
        }

        /// 画面在「看着转轴」的基础上再往上抬几度（负的是往下压）：
        /// 人整个（脚到头顶）落在上下两截界面中间露出来的那一截里——以前殿里平视时人的脚在屏幕最下面 2%，正好压在一排木牌后面，跪拜时整个人都在木牌后面；
        /// 殿里正前方（25 度以内）有佛像的话，再把它的头顶放到 statueLine 以下：人往下、佛像往上，两头留的空一样多；两样放不下先保住人
        float FrameTilt((Vector3 pos, Quaternion rot) view)
        {
            if (cam == null) cam = GetComponent<Camera>();
            float fov = cam != null ? cam.fieldOfView : 52f;
            Vector3 fwd = view.rot * Vector3.forward;
            float center = Mathf.Asin(Mathf.Clamp(fwd.y, -1f, 1f)) * Mathf.Rad2Deg;
            Vector3 flat = new Vector3(fwd.x, 0, fwd.z);
            Vector3 feet = target.position, head = feet + Vector3.up * bodyHeight;
            float want = center;
            if (interior && lookAts != null)
            {
                float statue = float.NegativeInfinity;
                foreach (var p in lookAts)
                {
                    Vector3 v = p - view.pos;
                    Vector3 vf = new Vector3(v.x, 0, v.z);
                    if (vf.sqrMagnitude < 0.25f || Vector3.Angle(flat, vf) > 25f) continue;
                    statue = Mathf.Max(statue, Elevation(view.pos, p) - LineAngle(statueLine, fov));
                }
                // 佛像要的最低仰角和脚要的最高仰角之间取一半（两头留的空一样多）
                if (!float.IsNegativeInfinity(statue))
                    want = 0.5f * (statue + Elevation(view.pos, feet) - LineAngle(1f - uiBottom, fov));
            }
            float c = FrameCenter(view.pos, feet, head, fov, uiTop, 1f - uiBottom, want);
            return Mathf.Clamp(c - center, -maxTilt, maxTilt);
        }

        void LateUpdate()
        {
            if (target == null) return;
            if (!snapped) Snap(target.eulerAngles.y);
            float dt = Time.deltaTime;
            if (dt > 0)
            {
                Vector3 v = (target.position - lastTarget) / dt;
                v.y = 0;
                if (v.magnitude > 8f) v = Vector3.zero;
                vel = Vector3.Lerp(vel, v, 1 - Mathf.Exp(-4f * dt));
            }
            lastTarget = target.position;
            float sp = vel.magnitude;
            if (!free && sp > 0.3f && Time.time - lastTouch > 1.2f)
            {
                float heading = Mathf.Atan2(vel.x, vel.z) * Mathf.Rad2Deg;
                float diff = Mathf.DeltaAngle(yawTarget, heading);
                if (Mathf.Abs(diff) < 150f) yawTarget = Mathf.MoveTowardsAngle(yawTarget, heading, autoTurn * Mathf.Clamp01(sp / 1.0f) * dt * Mathf.Clamp01(Mathf.Abs(diff) / 15f));
            }
            Apply(dt);
        }

        /// 屋里站着不动、镜头被身后的门扇、金柱、墙挡得离人不到 clearMin 米（画面里只剩自己的背，例如站在门里偏东、身后正是叠着的门扇，0.9 米）：
        /// 往左右（15 度一档，最多 75 度）找一个退得开的方向，慢慢转过去。手指拖过 3 秒内、人在走、坐着跪着做动作时不管（殿里的蒲团有自己挑的方向）。
        /// 门槛定得低（1.1 米）：在供桌前回头看门时镜头被佛坛挡在 1.4 米上下、抬到供桌上面从人身后看过去，那是要的样子（转开了反而让花觚挡在镜头前）
        public float clearMin = 1.1f;
        /// 自由环绕（摇杆走路、拖屏转视角的那套操作）：镜头不自己往人身后转、不自己找退得开的方向，全听手指的
        public bool free;
        /// 捏合拉远拉近：实际离人多远 = distance × zoomScale
        public float zoomScale = 1f;
        /// 此刻镜头的俯角（度）、离人多远
        public float PitchNow => pitch;
        public float DistanceNow => dist;
        /// 聚焦的对象（身边的小动物、撒了谷子的地方）：转轴从人身上往它那边挪、镜头收近，人和它一起在画面里。null 是没有
        Transform subject;
        Vector3 subjectPoint;
        float subjectW, subjectTarget, subjectDist = 2.1f, subjectToward = 0.6f;
        /// 聚焦时镜头往右偏几度（竖屏左右视角只有二十几度，4 度大约是屏幕宽的六分之一）
        public float subjectShift = 4.5f;

        /// 聚焦到一个东西上（t 可以是空的，那就用 point）；amount 0 放开、1 完全聚焦；dist 是聚焦时镜头离转轴多远。
        /// 刚聚焦上的那一刻镜头转到人的斜后方（越过肩膀看它，它在画面正中，人在一边）；之后手指拖动照样能转
        public void Subject(Transform t, Vector3 point, float amount, float dist = 2.1f, float toward = 0.6f, float pitchWanted = 20f)
        {
            subjectToward = toward;
            bool fresh = amount > 0.01f && (subjectTarget <= 0.01f || t != subject || (t == null && (point - subjectPoint).sqrMagnitude > 1f));
            subject = t;
            subjectPoint = point;
            subjectTarget = Mathf.Clamp01(amount);
            subjectDist = dist;
            if (fresh && target != null && Time.time - lastTouch > 1.2f)
            {
                Vector3 to = (t != null ? t.position : point) - target.position;
                to.y = 0;
                if (to.sqrMagnitude > 0.01f)
                {
                    float heading = Mathf.Atan2(to.x, to.z) * Mathf.Rad2Deg;
                    // 镜头朝向 = 人到它的方向再偏开 25 度（越过人的肩膀看它；竖屏窄，偏多了人就出画面了）：往离现在近的那一边偏
                    float a1 = heading + 25f, a2 = heading - 25f;
                    float pick = Mathf.Abs(Mathf.DeltaAngle(yawTarget, a1)) < Mathf.Abs(Mathf.DeltaAngle(yawTarget, a2)) ? a1 : a2;
                    yawTarget = yawTarget + Mathf.DeltaAngle(yawTarget, pick);
                    pitchTarget = Mathf.Clamp(pitchWanted, minPitch, maxPitch);
                }
            }
        }
        public bool HasSubject => subjectTarget > 0.01f;
        float clearNext;
        Folk targetFolk;

        void SeekClearYaw(Vector3 pivot, float blockedAt)
        {
            if (free || !interior || blockedAt >= clearMin || Time.time < clearNext || Time.time - lastTouch < 3f || vel.magnitude > 0.15f) return;
            clearNext = Time.time + 0.6f;
            if (targetFolk == null) targetFolk = target.GetComponentInParent<Folk>();
            if (targetFolk != null && (targetFolk.pose != Folk.Pose.None || targetFolk.Moving)) return;
            float bestOff = 0f, bestD = blockedAt + 0.3f;
            foreach (float off in new[] { 15f, -15f, 30f, -30f, 45f, -45f, 60f, -60f, 75f, -75f })
            {
                Vector3 b = Quaternion.Euler(pitch, yawTarget + off, 0) * Vector3.back;
                float d = distance;
                if (Physics.SphereCast(pivot, 0.18f, b, out var h, distance, blockers, QueryTriggerInteraction.Ignore)) d = h.distance - 0.05f;
                if (d > bestD)
                {
                    bestD = d;
                    bestOff = off;
                    if (d >= clearMin + 0.3f) break;
                }
            }
            if (bestOff != 0f) yawTarget += bestOff;
        }

        /// 跟着人的高度（平滑过的）：摇杆走台阶时胶囊一级一级往上跳、踩上拜垫一下高 12 厘米，镜头不跟着一顿一顿地跳
        float followY;
        bool haveY;

        void Apply(float dt)
        {
            float k = dt <= 0 ? 1 : 1 - Mathf.Exp(-7f * dt);
            yaw = Mathf.LerpAngle(yaw, yawTarget, k);
            pitch = Mathf.Lerp(pitch, pitchTarget, k);
            float ty = target.position.y;
            followY = !haveY || dt <= 0 || Mathf.Abs(ty - followY) > 0.6f ? ty : Mathf.Lerp(followY, ty, 1 - Mathf.Exp(-9f * dt));
            haveY = true;
            Vector3 pivot = new Vector3(target.position.x, followY, target.position.z) + Vector3.up * height;
            if (interior) pivot.y = Mathf.Min(pivot.y, ceiling - 0.6f);
            // 聚焦：转轴挪到人和它中间偏它那边、镜头收近（人还在画面里，它在正中）
            subjectW = dt <= 0 ? subjectTarget : Mathf.MoveTowards(subjectW, subjectTarget, dt / 0.6f);
            float sw = Mathf.SmoothStep(0f, 1f, subjectW);
            if (sw > 0.001f)
            {
                Vector3 sp = subject != null ? subject.position + Vector3.up * subjectPoint.y : subjectPoint;
                pivot = Vector3.Lerp(pivot, Vector3.Lerp(pivot, sp, subjectToward), sw);
            }
            // 聚焦时人不能挡在镜头和它之间（它绕着人转、蹭到脚边时会这样）：镜头到它的方向和它到人的方向不到 48 度，就慢慢绕开
            if (sw > 0.5f && dt > 0 && Time.time - lastTouch > 1.2f)
            {
                Vector3 toMe = target.position - (subject != null ? subject.position : subjectPoint);
                toMe.y = 0;
                if (toMe.sqrMagnitude > 0.04f)
                {
                    // 镜头在转轴的哪个方向：朝向转 180 度
                    float camDir = yawTarget + 180f, meDir = Mathf.Atan2(toMe.x, toMe.z) * Mathf.Rad2Deg;
                    float sep = Mathf.DeltaAngle(meDir, camDir);
                    if (Mathf.Abs(sep) < 48f) yawTarget += (sep >= 0 ? 1f : -1f) * 110f * dt;
                }
            }
            Quaternion rot = Quaternion.Euler(pitch, yaw, 0);
            Vector3 back = rot * Vector3.back;
            float want = Mathf.Lerp(distance * zoomScale, Mathf.Min(distance * zoomScale, subjectDist), sw);
            // 屋里往上抬（俯视）时：离人最远只到天花板底下，不靠「把镜头按在天花板下」来凑（那样画面会歪）
            if (interior && back.y > 0.05f) want = Mathf.Min(want, Mathf.Max(0.6f, (ceiling - 0.35f - pivot.y) / back.y));
            float reach = want;
            // 被挡住就收近
            LastHit = "";
            if (Physics.SphereCast(pivot, 0.18f, back, out var hit, reach, blockers, QueryTriggerInteraction.Ignore))
            {
                // 屋里墙近：收到墙跟前为止（宁可离人近一点，也不能钻到墙外面去）
                want = Mathf.Max(interior ? 0.35f : 1.0f, hit.distance - 0.05f);
                LastHit = hit.collider.name;
            }
            if (dt > 0) SeekClearYaw(pivot, want);
            // 收近要快，放远要慢，免得一跳一跳
            dist = dt <= 0 ? want : want < dist ? Mathf.Lerp(dist, want, 1 - Mathf.Exp(-10f * dt)) : Mathf.Lerp(dist, want, 1 - Mathf.Exp(-2.5f * dt));
            Vector3 pos = pivot + back * dist;
            // 不钻到地下；屋里不顶到天花板
            pos.y = Mathf.Max(pos.y, target.position.y + 0.25f);
            if (interior)
            {
                // 落在供桌那一片上面：抬到它的顶上（离边 0.3 米以内慢慢抬，绕过去时不一跳）
                foreach (var b in keepOut)
                {
                    float inX = Mathf.Min(pos.x - b.min.x, b.max.x - pos.x), inZ = Mathf.Min(pos.z - b.min.z, b.max.z - pos.z);
                    float inside = Mathf.Min(inX, inZ);
                    if (inside <= 0f || pos.y >= b.max.y || pos.y < b.min.y) continue;
                    pos.y = Mathf.Lerp(pos.y, b.max.y, Mathf.SmoothStep(0f, 1f, inside / 0.3f));
                }
                pos.y = Mathf.Min(pos.y, ceiling - 0.3f);
            }
            Quaternion look = Quaternion.LookRotation(pivot + Vector3.up * 0.1f - pos);
            // 画面上下抬压：人整个在界面中间露出来的那一截里，屋里再把佛像整尊放进来（手指拖过就停在那里）
            // 聚焦着小动物时不管「人整个放进画面」那一套：画面正中给它
            if (!userAim) tiltTarget = sw > 0.5f ? 0f : FrameTilt((pos, look));
            tilt = dt <= 0 ? tiltTarget : Mathf.Lerp(tilt, tiltTarget, 1 - Mathf.Exp(-3f * dt));
            // 聚焦时镜头再往右偏一点：它落在画面中间偏左，右边那一列「能做的事」不压在它身上
            transform.SetPositionAndRotation(pos, look * Quaternion.Euler(-tilt, subjectShift * sw, 0));
        }
    }
}
