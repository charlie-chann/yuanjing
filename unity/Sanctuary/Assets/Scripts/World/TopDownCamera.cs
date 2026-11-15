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

        Vector3 follow, pan, panTarget, lastTarget, vel;
        /// 走路时镜头慢慢转到人走的方向（每秒最多转几度）、往前多看几米
        public float autoTurn = 15f, lookAhead = 1.4f;
        float dist, pit, focus, focusTarget, lastTouch = -100f;
        bool snapped;
        Camera cam;

        public override float Yaw => yaw;

        void Awake()
        {
            cam = GetComponent<Camera>();
            if (cam != null && GetComponent<ViewSwitcher>() == null) cam.fieldOfView = fov;
            dist = distance;
            pit = pitch;
            // 镜头离得远，名字要放大才看得清，也不能因为远就藏起来
            Folk.TagScalePerMeter = 0.17f;
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
            // 换到别的视角时（ViewSwitcher 在管），这两个值由它接着设
            if (GetComponent<ViewSwitcher>() != null) return;
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
            if (dt > 0)
            {
                Vector3 v = (target.position - lastTarget) / dt;
                v.y = 0;
                if (v.magnitude > 8f) v = Vector3.zero;          // 瞬移（进场、传送）不算
                vel = Vector3.Lerp(vel, v, 1 - Mathf.Exp(-4f * dt));
            }
            lastTarget = target.position;
            float sp = vel.magnitude;
            if (sp > 0.3f && Time.time - lastTouch > 1.5f)
            {
                // 镜头转到人走的方向：走得越快转得越快；人朝着镜头走（转身往回走）时不转，免得画面一下翻过来
                float heading = Mathf.Atan2(vel.x, vel.z) * Mathf.Rad2Deg;
                float diff = Mathf.DeltaAngle(yaw, heading);
                if (Mathf.Abs(diff) < 150f) yaw = Mathf.MoveTowardsAngle(yaw, heading, autoTurn * Mathf.Clamp01(sp / 1.2f) * dt * Mathf.Clamp01(Mathf.Abs(diff) / 20f));
            }
            Vector3 ahead = sp > 0.2f ? vel / Mathf.Max(sp, 0.01f) * (lookAhead * Mathf.Clamp01(sp / 1.2f)) : Vector3.zero;
            follow = Vector3.Lerp(follow, target.position + ahead, 1 - Mathf.Exp(-3.5f * dt));
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
