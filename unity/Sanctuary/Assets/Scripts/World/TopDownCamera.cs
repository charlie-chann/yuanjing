using UnityEngine;

namespace Yuanjing
{
    /// 俯视镜头：在高处斜着往下看，朝向固定（屏幕上方永远是北），平滑地跟着人走。
    /// 拖动画面可以把镜头挪开一点看看四周，松手几秒后回到人身上；坐下、做动作时拉近。
    public class TopDownCamera : PlayerCamera
    {
        public float yaw = 0f, pitch = 54f, distance = 26f, fov = 36f;
        public float focusDistance = 14f, focusPitch = 46f;
        /// 镜头看的那一点最远能离开岛中心多远（免得画面里大半是水）
        public Vector2 boundsMin = new Vector2(-12f, -22f), boundsMax = new Vector2(12f, 14f);
        public float maxPan = 7f;

        Vector3 follow, pan, panTarget;
        float dist, pit, focus, focusTarget, lastTouch = -100f;
        bool snapped;
        Camera cam;

        public override float Yaw => yaw;

        void Awake()
        {
            cam = GetComponent<Camera>();
            if (cam != null) cam.fieldOfView = fov;
            dist = distance;
            pit = pitch;
            // 镜头离得远，名字要放大才看得清，也不能因为远就藏起来
            Folk.TagScalePerMeter = 0.13f;
            Folk.TagMaxScale = 5f;
            Folk.TagHideBeyond = 80f;
        }

        public override void Look(float dx, float dy)
        {
            // 手指往右拖，画面跟着往右走（镜头往左挪）
            Quaternion q = Quaternion.Euler(0, yaw, 0);
            float w = 2f * dist * Mathf.Tan(fov * 0.5f * Mathf.Deg2Rad);
            panTarget += q * new Vector3(dx * w * (cam != null ? cam.aspect : 0.46f), 0, dy * w * 1.6f);
            panTarget = Vector3.ClampMagnitude(panTarget, maxPan);
            lastTouch = Time.time;
        }

        public override void Snap(float facingYaw)
        {
            if (target == null) return;
            follow = target.position;
            pan = panTarget = Vector3.zero;
            dist = Mathf.Lerp(distance, focusDistance, focus);
            pit = Mathf.Lerp(pitch, focusPitch, focus);
            snapped = true;
            Apply();
        }

        public override void Settle(float facingYaw, float pitchWanted = 14f) { }

        public override void Focus(float amount) => focusTarget = Mathf.Clamp01(amount);

        static readonly int SeeId = Shader.PropertyToID("_YJSee");
        /// 人被屋檐、树冠挡住时，视线上镂空的半径（米）
        public float seeRadius = 1.9f;

        /// 地上的云影有多重（0 没有）
        public float cloudShadow = 0.2f;

        void OnEnable() => Shader.SetGlobalFloat("_YJCloud", cloudShadow);

        void OnDisable()
        {
            Shader.SetGlobalVector(SeeId, Vector4.zero);
            Shader.SetGlobalFloat("_YJCloud", 0f);
        }

        void LateUpdate()
        {
            if (target == null) return;
            Vector3 tp = target.position;
            Shader.SetGlobalVector(SeeId, new Vector4(tp.x, tp.y, tp.z, seeRadius));
            if (!snapped) Snap(0);
            float dt = Time.deltaTime;
            follow = Vector3.Lerp(follow, target.position, 1 - Mathf.Exp(-5f * dt));
            if (Time.time - lastTouch > 2.5f) panTarget = Vector3.Lerp(panTarget, Vector3.zero, 1 - Mathf.Exp(-2.5f * dt));
            pan = Vector3.Lerp(pan, panTarget, 1 - Mathf.Exp(-9f * dt));
            focus = Mathf.Lerp(focus, focusTarget, 1 - Mathf.Exp(-1.8f * dt));
            dist = Mathf.Lerp(distance, focusDistance, focus);
            pit = Mathf.Lerp(pitch, focusPitch, focus);
            Apply();
        }

        void Apply()
        {
            Vector3 p = follow + pan;
            p.x = Mathf.Clamp(p.x, boundsMin.x, boundsMax.x);
            p.z = Mathf.Clamp(p.z, boundsMin.y, boundsMax.y);
            Vector3 pivot = new Vector3(p.x, follow.y + 0.6f, p.z);
            Quaternion rot = Quaternion.Euler(pit, yaw, 0);
            transform.SetPositionAndRotation(pivot + rot * Vector3.back * dist, rot);
        }
    }
}
