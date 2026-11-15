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

        public override float Yaw => yaw;

        void Awake()
        {
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
        }

        /// 直接摆到人背后（进场时）
        public override void Snap(float facingYaw)
        {
            yaw = yawTarget = facingYaw;
            pitch = pitchTarget = 16f;
            dist = distance;
            snapped = true;
            Apply(0);
        }

        /// 慢慢转到某个方向（坐下、走到某处以后，让画面朝向要看的东西）
        public override void Settle(float facingYaw, float pitchWanted = 14f)
        {
            if (Time.time - lastTouch < 3f) return;
            yawTarget = yaw + Mathf.DeltaAngle(yaw, facingYaw);
            pitchTarget = pitchWanted;
        }

        void LateUpdate()
        {
            if (target == null) return;
            if (!snapped) Snap(target.eulerAngles.y);
            Apply(Time.deltaTime);
        }

        void Apply(float dt)
        {
            float k = dt <= 0 ? 1 : 1 - Mathf.Exp(-7f * dt);
            yaw = Mathf.LerpAngle(yaw, yawTarget, k);
            pitch = Mathf.Lerp(pitch, pitchTarget, k);
            Vector3 pivot = target.position + Vector3.up * height;
            Quaternion rot = Quaternion.Euler(pitch, yaw, 0);
            Vector3 back = rot * Vector3.back;
            float want = distance;
            // 被挡住就收近
            LastHit = "";
            if (Physics.SphereCast(pivot, 0.18f, back, out var hit, distance, blockers, QueryTriggerInteraction.Ignore))
            {
                want = Mathf.Max(1.0f, hit.distance - 0.05f);
                LastHit = hit.collider.name;
            }
            // 收近要快，放远要慢，免得一跳一跳
            dist = dt <= 0 ? want : want < dist ? Mathf.Lerp(dist, want, 1 - Mathf.Exp(-10f * dt)) : Mathf.Lerp(dist, want, 1 - Mathf.Exp(-2.5f * dt));
            Vector3 pos = pivot + back * dist;
            // 不钻到地下
            pos.y = Mathf.Max(pos.y, target.position.y + 0.25f);
            transform.SetPositionAndRotation(pos, Quaternion.LookRotation(pivot + Vector3.up * 0.1f - pos));
        }
    }
}
