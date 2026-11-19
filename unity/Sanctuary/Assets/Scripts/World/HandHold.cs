using UnityEngine;

namespace Yuanjing
{
    /// 拿在手里的东西（要挂的布条、木牌，走过去的路上捏着的布条卷）：位置跟着手心走，朝向保持竖直（布是垂着的，不跟着手腕翻）。
    /// 排在动画、裙摆弹簧之后算（手的位置这一帧已经定了）。
    [DefaultExecutionOrder(250)]
    public class HandHold : MonoBehaviour
    {
        /// 手腕的骨头，和中指根的骨头（有的话取两者之间偏指根的一点当手心，不用管骨头的轴朝哪）
        public Transform bone, finger;
        /// 在手心的基础上再挪一点（世界坐标，米）：东西的挂点在手心下面一点
        public Vector3 offset = new Vector3(0, -0.015f, 0);
        /// 朝向：世界里的旋转（正面朝外）
        public Quaternion worldRotation = Quaternion.identity;
        /// 走路时捏着：朝向跟着这个人水平转（yawFrom 的朝向再转 yawOffset 度），不用 worldRotation
        public Transform yawFrom;
        public float yawOffset;
        /// 换朝向时用多久转过去（秒，0 是马上）：木牌抬手时从顺着走路的方向转到正面朝外
        public float turnTime;
        /// 握在手心里（布条卷）：卷轴顺着四个指根那一条线（小指根→食指根），卷的中心从手心往掌心那一面挪 gripOut 米，
        /// 走路时半弯着的手指正好搭在卷上，看着是握着的（不是贴在手背、手边上的一块）。只用骨头的位置，不管骨头的轴朝哪
        public bool grip;
        public Transform index, little;
        public bool rightHand = true;
        public float gripOut = 0.013f;

        public Vector3 Palm => bone == null ? transform.position : finger == null ? bone.position : Vector3.Lerp(bone.position, finger.position, 0.6f);

        /// 现在想要的朝向
        public Quaternion Wanted => yawFrom != null ? Quaternion.Euler(0, yawFrom.eulerAngles.y + yawOffset, 0) : worldRotation;

        void LateUpdate()
        {
            if (bone == null) return;
            if (grip && index != null && little != null && finger != null)
            {
                Vector3 axis = index.position - little.position, fingers = finger.position - bone.position;
                // 右手：手指方向 × 指根连线 = 掌心朝的方向（左手反过来）
                Vector3 palmN = Vector3.Cross(fingers, axis).normalized * (rightHand ? 1f : -1f);
                if (axis.sqrMagnitude > 1e-6f && palmN.sqrMagnitude > 0.5f)
                {
                    // 绕卷轴转到布头朝下（布头垂着）
                    transform.SetPositionAndRotation(Palm + palmN * gripOut, Quaternion.LookRotation(axis.normalized, Vector3.up));
                    return;
                }
            }
            Quaternion want = Wanted;
            Quaternion rot = turnTime > 0f ? Quaternion.Slerp(transform.rotation, want, 1f - Mathf.Exp(-Time.deltaTime * 4f / turnTime)) : want;
            transform.SetPositionAndRotation(Palm + offset, rot);
        }
    }
}
