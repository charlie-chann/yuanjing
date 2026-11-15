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
        public string mode = "top";
        public float topFov = 36f, followFov = 52f, firstFov = 62f, maxZoom = 8f;

        PlayerCamera active;
        Camera cam;
        float zoom = 1f, zoomTarget = 1f, baseFov, blend = 1f;
        Vector3 fromPos;
        Quaternion fromRot;
        float fromFov;
        Renderer[] body;
        Folk me;
        bool bodyHidden;

        static readonly int SeeId = Shader.PropertyToID("_YJSee");

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
                // 平视：和人差不多高，能往上抬一点、往下压很多；要抬头看高处用仰视或第一人称
                follow.minPitch = -12f;
                follow.maxPitch = 75f;
                follow.distance = 3.0f;
                follow.height = 0.95f;
                follow.Snap(yawNow);
                follow.Look(0, 0.08f);
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

        void LateUpdate()
        {
            if (target == null || active == null) return;
            float dt = Time.deltaTime;
            zoom = Mathf.Lerp(zoom, zoomTarget, 1 - Mathf.Exp(-12f * dt));
            float want = active == top ? topFov : active == first ? firstFov : followFov;
            baseFov = Mathf.Lerp(baseFov, want, 1 - Mathf.Exp(-6f * dt));
            float fov = 2f * Mathf.Atan(Mathf.Tan(baseFov * 0.5f * Mathf.Deg2Rad) / zoom) * Mathf.Rad2Deg;
            if (blend < 1f)
            {
                blend = Mathf.Min(1f, blend + dt / 0.7f);
                float k = Mathf.SmoothStep(0f, 1f, blend);
                transform.SetPositionAndRotation(Vector3.Lerp(fromPos, transform.position, k), Quaternion.Slerp(fromRot, transform.rotation, k));
                fov = Mathf.Lerp(fromFov, fov, k);
            }
            cam.fieldOfView = fov;
            // 俯视时镜头在二十多米外，近处不用画；贴近看的时候要能凑到花跟前
            cam.nearClipPlane = active == top ? 0.5f : active == first ? 0.04f : 0.08f;
            // 人的位置给着色器：俯视时用来把挡住人的屋檐树冠镂空（半径），其他视角只用来让脚边的草倒伏（半径 0 就是不镂空）
            Vector3 tp = target.position;
            Shader.SetGlobalVector(SeeId, new Vector4(tp.x, tp.y, tp.z, active == top && blend >= 1f ? top.seeRadius : 0f));
            Shader.SetGlobalFloat("_YJCloud", top.cloudShadow);
        }
    }
}
