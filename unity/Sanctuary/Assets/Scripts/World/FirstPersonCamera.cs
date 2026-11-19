using UnityEngine;

namespace Yuanjing
{
    /// 第一人称：镜头就在自己眼睛的位置，拖动画面环顾四周（上下各能看 80 度）。
    /// 低头看地面时人会跟着蹲下去。仰视那一档用的也是这台镜头：眼睛压到离地四十厘米（eyeHeight 调小），
    /// 一开始抬着头；把头放平就是蹲着平看——凑近看花、看草、看小动物用这一档再放大。
    public class FirstPersonCamera : PlayerCamera
    {
        public float eyeHeight = 1.1f, crouchHeight = 0.34f, minPitch = -80f, maxPitch = 80f;
        /// 头的骨头：坐下、跪下时眼睛跟着低下去
        public Transform head;
        /// 在屋里（大殿里）：换到第一人称时先微微抬头（佛像高，平着看只看到供桌和佛像的下半身）
        public bool interior;
        public float interiorPitch = -10f;

        float yaw, pitch, yawTarget, pitchTarget, eye;
        bool snapped;

        public override float Yaw => yaw;

        public override void Look(float dx, float dy)
        {
            yawTarget += dx * 150f;
            pitchTarget = Mathf.Clamp(pitchTarget - dy * 110f, minPitch, maxPitch);
        }

        public override void Snap(float facingYaw)
        {
            yaw = yawTarget = facingYaw;
            pitch = pitchTarget = interior && eyeHeight > 0.6f ? interiorPitch : 4f;
            eye = eyeHeight;
            snapped = true;
            Apply(0);
        }

        public override void Settle(float facingYaw, float pitchWanted = 14f) { }

        void LateUpdate()
        {
            if (target == null) return;
            if (!snapped) Snap(target.eulerAngles.y);
            Apply(Time.deltaTime);
        }

        void Apply(float dt)
        {
            float k = dt <= 0 ? 1 : 1 - Mathf.Exp(-10f * dt);
            yaw = Mathf.LerpAngle(yaw, yawTarget, k);
            pitch = Mathf.Lerp(pitch, pitchTarget, k);
            // 站着的眼睛高度：有头骨就跟着头（坐、跪会变矮），走路时头的起伏滤掉
            float stand = eyeHeight;
            if (head != null) stand = Mathf.Min(eyeHeight, head.position.y - target.position.y + 0.06f);
            float want = Mathf.Lerp(stand, Mathf.Min(stand, crouchHeight), Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(28f, 62f, pitch)));
            eye = dt <= 0 ? want : Mathf.Lerp(eye, want, 1 - Mathf.Exp(-5f * dt));
            Quaternion rot = Quaternion.Euler(pitch, yaw, 0);
            Vector3 pos = target.position + Vector3.up * eye + Quaternion.Euler(0, yaw, 0) * Vector3.forward * 0.1f;
            transform.SetPositionAndRotation(pos, rot);
        }
    }
}
