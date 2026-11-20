using System.Linq;
using UnityEngine;

namespace Yuanjing
{
    /// 视角切换：一台镜头上挂着三种跟法（俯视、身后跟随、第一人称），只开其中一种，换的时候平滑过渡。
    /// 四个视角：top 俯视；level 平视（跟在身后，和人一样高）；low 仰视（蹲在地上抬头看树、看屋檐，不画自己）；first 第一人称。
    /// 另外管放大：双指捏合把视角收窄（最多 8 倍），拖动的灵敏度跟着降，放大以后也好对准。
    [DefaultExecutionOrder(100)]   // 排在三种跟法之后：它们先摆好镜头，这里再做过渡和放大
    public class ViewSwitcher : PlayerCamera
    {
        public TopDownCamera top;
        public ThirdPersonCamera follow;
        public FirstPersonCamera first;
        public string mode = "level";
        public float topFov = 36f, followFov = 52f, firstFov = 62f, maxZoom = 8f;
        /// 殿里平视的视角放宽一点：竖屏上下还要让出两截给界面，人整个、佛像整尊才放得进中间那一截
        public float interiorFov = 58f;

        PlayerCamera active;
        Camera cam;
        float zoom = 1f, zoomTarget = 1f, baseFov, blend = 1f;
        Vector3 fromPos;
        Quaternion fromRot;
        float fromFov;
        Renderer[] body;
        Transform[] bones;
        Folk me;
        bool bodyHidden;

        static readonly int SeeId = Shader.PropertyToID("_YJSee");
        static readonly int FocusId = Shader.PropertyToID("_YJFocus");

        // 特写（挂布条时凑到跟前）：w 从 0 慢慢到 1，镜头从平常的位置滑过去；结束时再滑回来
        Vector3 cuFocus, cuEye, cuLow, cuHigh;
        float cuW, cuTarget, cuFov;
        bool cuFramed;
        public float closeUpFov = 46f;
        /// 特写时画面上下被界面挡着的那两截（同 ThirdPersonCamera.uiTop、uiBottom；特写时地名、摇杆都收起来了，上面只剩状态栏和两块小牌子）
        public float closeUpTop = 0.09f, closeUpBottom = 0.20f;
        public bool InCloseUp => cuW > 0.001f;

        public override float Yaw => active != null ? active.Yaw : 0f;
        public string Mode => mode;
        public float Zoom => zoom;

        void Awake()
        {
            cam = GetComponent<Camera>();
            if (top == null) top = GetComponent<TopDownCamera>();
            if (follow == null) follow = GetComponent<ThirdPersonCamera>();
            if (first == null) first = GetComponent<FirstPersonCamera>();
        }

        void Start()
        {
            foreach (PlayerCamera c in new PlayerCamera[] { top, follow, first }) c.target = target;
            var folk = target != null ? target.GetComponentInParent<Folk>() ?? target.GetComponentInChildren<Folk>() : null;
            if (folk != null)
            {
                if (folk.animator != null) first.head = folk.animator.GetBoneTransform(HumanBodyBones.Head);
                body = folk.model.GetComponentsInChildren<Renderer>();
                me = folk;
                if (folk.animator != null)
                    bones = new[] { HumanBodyBones.Head, HumanBodyBones.Hips, HumanBodyBones.LeftHand, HumanBodyBones.RightHand, HumanBodyBones.LeftFoot, HumanBodyBones.RightFoot }
                        .Select(folk.animator.GetBoneTransform).Where(t => t != null).ToArray();
            }
            baseFov = topFov;
            Use(mode, false);
        }

        public void SetMode(string m)
        {
            if (m != "top" && m != "level" && m != "low" && m != "first") return;
            if (m == mode && active != null) return;
            Use(m, true);
        }

        public void SetZoom(float z) => zoomTarget = Mathf.Clamp(z, 1f, maxZoom);

        // ── 自由环绕（现在唯一的操作方式）：左手摇杆走路，拖屏绕着人转、上下看（能一直压到俯视），捏合拉远拉近 ──
        /// 捏合：镜头离人的远近是平常的几倍（minReach 到 maxReach；殿里天花板低，最远收到 interiorMaxReach）
        public float minReach = 0.45f, maxReach = 4.2f, interiorMaxReach = 4.2f;
        float reach = 1f;
        public float Reach => reach;
        public void SetReach(float r)
        {
            reach = Mathf.Clamp(r, minReach, follow != null && follow.interior ? interiorMaxReach : maxReach);
            if (follow != null) follow.zoomScale = reach;
        }
        /// 抬高到多少度以上，挡在镜头和人之间的屋檐、树冠开始镂空（到 seeFull 度完全镂空）
        public float seeFrom = 24f, seeFull = 42f;
        public float ZoomTarget => zoomTarget;

        void Use(string m, bool smooth)
        {
            if (smooth)
            {
                fromPos = transform.position;
                fromRot = transform.rotation;
                fromFov = cam.fieldOfView;
                blend = 0f;
            }
            mode = m;
            // 仰视用的也是第一人称那台：眼睛压到离地四十厘米、抬头往上看。
            // （不能用「跟在身后、镜头压低」来做：那样镜头正对着人物的裙底）
            PlayerCamera next = m == "top" ? top : m == "first" || m == "low" ? (PlayerCamera)first : follow;
            float facing = target != null ? target.eulerAngles.y : 0f;
            // 从俯视换下来：朝人面对的方向看；平视、仰视、第一人称之间互换：朝向不变
            float yawNow = active != null && active != top ? active.Yaw : facing;
            top.enabled = next == top;
            follow.enabled = next == follow;
            first.enabled = next == first;
            active = next;
            if (next == follow)
            {
                // 自由环绕：能仰一点看屋檐，能一直压到快垂直的俯视
                follow.free = true;
                follow.minPitch = -18f;
                follow.maxPitch = 82f;
                follow.zoomScale = reach;
                follow.distance = follow.interior ? (wide ? interiorWideDistance : interiorDistance) : seated ? seatedDistance : 3.0f;
                follow.height = 0.95f;
                follow.Snap(yawNow);
                // 外面：比 Snap 的 16 度放平一些；殿里：Snap 已经按屋里的高低摆好
                if (!follow.interior) follow.Pitch(18f);
            }
            else if (next == first)
            {
                first.eyeHeight = m == "low" ? 0.42f : 1.1f;
                first.Snap(yawNow);
                if (m == "low") first.Look(0, 0.3f);          // 抬头三十多度
            }
            else next.Snap(yawNow);
            bool far = next == top;
            Folk.TagScalePerMeter = far ? 0.17f : 0.26f;
            Folk.TagMaxScale = far ? 5f : 2.4f;
            Folk.TagHideBeyond = far ? 80f : 26f;
            HideBody(next == first);
            if (me != null && me.nameTag != null && next != first) me.nameTag.gameObject.SetActive(!string.IsNullOrEmpty(me.nameTag.text));
        }

        /// 第一人称不画自己的身体（只留影子），不然镜头在脑袋里面
        void HideBody(bool hide)
        {
            if (body == null || hide == bodyHidden) return;
            bodyHidden = hide;
            // 自己头顶的名字也收起来（第一人称、仰视时它就飘在眼前）
            if (me != null && me.nameTag != null) me.nameTag.gameObject.SetActive(!hide && !string.IsNullOrEmpty(me.nameTag.text));
            foreach (var r in body)
                if (r != null) r.shadowCastingMode = hide ? UnityEngine.Rendering.ShadowCastingMode.ShadowsOnly : UnityEngine.Rendering.ShadowCastingMode.On;
        }

        public override void Look(float dx, float dy)
        {
            if (active != null) active.Look(dx / zoom, dy / zoom);
        }

        public override void Snap(float facingYaw)
        {
            if (active != null) active.Snap(facingYaw);
            blend = 1f;
        }

        public override void Settle(float facingYaw, float pitchWanted = 14f)
        {
            if (active != null && mode != "low") active.Settle(facingYaw, pitchWanted);
        }

        public override void Focus(float amount)
        {
            if (top != null) top.Focus(amount);
        }

        /// 聚焦到身边的小动物、谷子上（自由环绕时才有）
        public void Subject(Transform t, Vector3 point, float amount, float dist = 2.1f, float toward = 0.6f, float pitch = 20f)
        {
            if (follow != null) follow.Subject(t, point, amount, dist, toward, pitch);
        }

        public override void CloseUp(Vector3 focus, Vector3 eye)
        {
            cuFocus = focus;
            cuEye = eye;
            cuFramed = false;
            cuFov = closeUpFov;
            cuTarget = 1f;
        }

        /// 特写，上下按界面摆：镜头水平朝着 focus；low、high（人的脚、头顶、举着的香、布条的上沿……）都落在上下两截界面中间露出来的那一截里，
        /// 两头留的空一样多（放不下先保住 high）。fov 是这个特写的视角（0 用 closeUpFov）
        public void CloseUp(Vector3 focus, Vector3 eye, Vector3 low, Vector3 high, float fov = 0f)
        {
            CloseUp(focus, eye);
            cuLow = low;
            cuHigh = high;
            cuFramed = true;
            cuFov = fov > 0f ? fov : closeUpFov;
        }

        /// 特写镜头的朝向
        Quaternion CloseUpRotation()
        {
            Vector3 d = cuFocus - cuEye;
            if (!cuFramed || new Vector2(d.x, d.z).sqrMagnitude < 1e-4f) return Quaternion.LookRotation(d);
            float yaw = Mathf.Atan2(d.x, d.z) * Mathf.Rad2Deg;
            float mid = 0.5f * (ThirdPersonCamera.Elevation(cuEye, cuLow) - ThirdPersonCamera.LineAngle(1f - closeUpBottom, cuFov)
                              + ThirdPersonCamera.Elevation(cuEye, cuHigh) - ThirdPersonCamera.LineAngle(closeUpTop, cuFov));
            float c = ThirdPersonCamera.FrameCenter(cuEye, cuLow, cuHigh, cuFov, closeUpTop, 1f - closeUpBottom, mid);
            return Quaternion.Euler(-c, yaw, 0f);
        }

        public override void EndCloseUp() => cuTarget = 0f;

        /// 在屋里的时候平视镜头离人多远（2.6 米：人从脚到头、佛像到头顶才都放得进木牌和地名中间那一截；墙近就收近）；
        /// 在拜垫上跪拜时退远一点（wide），跪着、叩首的人和上面整尊佛像才放得进一个竖屏画面
        public float interiorDistance = 2.6f, interiorWideDistance = 3.0f;
        bool wide;
        /// 坐在院子里的蒲团上：平视镜头收近一点、抬高一点（GameDirector 给俯角），从后面一排坐着的人头顶上越过去看自己
        public float seatedDistance = 2.6f;
        bool seated;

        /// 坐下（院子里的蒲团）、起身：GameDirector 每帧告诉一声
        public void Seated(bool on)
        {
            if (on == seated) return;
            seated = on;
            if (follow != null && active == follow && !follow.interior) follow.distance = on ? seatedDistance : 3.0f;
        }

        /// 殿里跪拜时把平视镜头退远（true），做完收回来（false）
        public void Wide(bool on)
        {
            wide = on;
            if (follow != null && active == follow && follow.interior) follow.distance = on ? interiorWideDistance : interiorDistance;
        }
        public bool Interior => follow != null && follow.interior;

        /// 进屋（大殿里）、出屋：平视的镜头收近到 2.2 米、放低到和人头差不多高、不高过天花板、躲墙，
        /// 画面往上抬着把佛像放进来（lookAts：三尊佛像的头顶）；出来恢复 3 米
        public void SetInterior(bool inside, float ceiling, Vector3[] lookAts = null, Bounds[] keepOut = null)
        {
            if (follow == null) return;
            follow.interior = inside;
            follow.ceiling = ceiling;
            if (lookAts != null) follow.lookAts = lookAts;
            if (keepOut != null) follow.keepOut = keepOut;
            if (first != null) first.interior = inside;
            if (!inside) wide = false;
            SetReach(reach);
            if (active == follow)
            {
                follow.distance = inside ? (wide ? interiorWideDistance : interiorDistance) : seated ? seatedDistance : 3.0f;
                if (inside && !follow.free) follow.Pitch(follow.interiorPitch);
            }
        }

        void LateUpdate()
        {
            if (target == null || active == null) return;
            float dt = Time.deltaTime;
            zoom = Mathf.Lerp(zoom, zoomTarget, 1 - Mathf.Exp(-12f * dt));
            float want = active == top ? topFov : active == first ? firstFov : follow.interior ? interiorFov : followFov;
            baseFov = Mathf.Lerp(baseFov, want, 1 - Mathf.Exp(-6f * dt));
            float fov = 2f * Mathf.Atan(Mathf.Tan(baseFov * 0.5f * Mathf.Deg2Rad) / zoom) * Mathf.Rad2Deg;
            if (blend < 1f)
            {
                blend = Mathf.Min(1f, blend + dt / 0.7f);
                float k = Mathf.SmoothStep(0f, 1f, blend);
                transform.SetPositionAndRotation(Vector3.Lerp(fromPos, transform.position, k), Quaternion.Slerp(fromRot, transform.rotation, k));
                fov = Mathf.Lerp(fromFov, fov, k);
            }
            // 特写：在算好的镜头上再往特写的位置滑（0.9 秒），视角也收窄一些
            cuW = Mathf.MoveTowards(cuW, cuTarget, dt / 0.9f);
            if (cuW > 0.001f)
            {
                float k = Mathf.SmoothStep(0f, 1f, cuW);
                Quaternion look = CloseUpRotation();
                transform.SetPositionAndRotation(Vector3.Lerp(transform.position, cuEye, k), Quaternion.Slerp(transform.rotation, look, k));
                fov = Mathf.Lerp(fov, cuFov > 0f ? cuFov : closeUpFov, k);
            }
            cam.fieldOfView = fov;
            // 俯视时镜头在二十多米外，近处不用画；贴近看的时候要能凑到花跟前
            cam.nearClipPlane = cuW > 0.001f ? 0.05f : active == top ? 0.5f : active == first ? 0.04f : 0.08f;
            // 第一人称不画自己；特写时要看见自己的手，先画出来
            HideBody(active == first && cuW < 0.5f);
            // 特写（上香、系布条凑到跟前）时自己头顶的名字收起来：它就飘在手和香炉、布条旁边，挡着看。
            // 殿里也收起来：镜头只离人 2.2 米，名字正好压在佛像的脸上、头顶上
            if (me != null && me.nameTag != null)
            {
                bool tag = !bodyHidden && cuW < 0.3f && !Interior && !string.IsNullOrEmpty(me.nameTag.text);
                if (me.nameTag.gameObject.activeSelf != tag) me.nameTag.gameObject.SetActive(tag);
            }
            // 人的位置给着色器：俯视时用来把挡住人的屋檐树冠镂空（半径），其他视角只用来让脚边的草倒伏（半径 0 就是不镂空）
            Vector3 tp = target.position;
            // 自由环绕时镜头抬高了也一样：屋檐、树冠挡住人就镂空（平着看时不镂空，镜头自己会躲开挡着的东西）
            float see = active == top && blend >= 1f && cuW <= 0.001f ? top.seeRadius : 0f;
            if (active == follow && !follow.interior && cuW <= 0.001f)
                see = top.seeRadius * Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(seeFrom, seeFull, follow.PitchNow)) * Mathf.Clamp01(follow.DistanceNow / 4f);
            Shader.SetGlobalVector(SeeId, new Vector4(tp.x, tp.y, tp.z, see));
            Shader.SetGlobalFloat("_YJCloud", top.cloudShadow);
            // 平视时挡在镜头和自己之间的别人（后面一排坐着的人、从镜头前走过的香客）用网点淡掉（YJAnime.shader 的 YJOccluderFade）：
            // 告诉着色器自己那一团在哪、多大（身上几个蒙皮网格的包围盒）。俯视、第一人称、特写时不管
            // 特写（系布条、上香）时也管：站在树下、香炉边的香客挡在镜头和自己之间，也淡掉（不然整个特写只拍到别人的后背）
            Vector4 focus = Vector4.zero;
            if (((active == follow && blend >= 1f) || cuW > 0.001f) && bones != null)
            {
                // 按骨骼量（头、髋、手、脚）：蒙皮网格的包围盒是一块固定的大盒子（BuildAnime：坐下、叩首时脸不被裁掉），量不出人此刻多大
                bool any = false;
                Bounds b = default;
                foreach (var t in bones)
                {
                    if (t == null) continue;
                    if (!any) { b = new Bounds(t.position, Vector3.zero); any = true; }
                    else b.Encapsulate(t.position);
                }
                if (any)
                {
                    float s = me != null ? me.transform.lossyScale.y : 0.806f;
                    b.Expand(new Vector3(0.3f, 0.45f, 0.3f) * s);
                    focus = new Vector4(b.center.x, b.center.y, b.center.z, Mathf.Max(b.extents.y, Mathf.Max(b.extents.x, b.extents.z)) * 0.9f);
                }
            }
            Shader.SetGlobalVector(FocusId, focus);
            Folk.OccluderFocus = focus;
        }
    }
}
