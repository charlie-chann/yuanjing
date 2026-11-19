using UnityEngine;

namespace Yuanjing
{
    /// 跟着自己小人的镜头。两种：贴在身后的第三人称（山寺、教堂），高处俯视的（湖心小寺）。
    /// 总控只认这几个动作，不管是哪一种。
    public abstract class PlayerCamera : MonoBehaviour
    {
        public Transform target;

        /// 镜头水平朝向。摇杆往前推，人就朝这个方向走
        public abstract float Yaw { get; }
        /// 手指拖动：dx、dy 是移动占屏幕宽高的比例
        public abstract void Look(float dx, float dy);
        /// 直接摆好（进场时）
        public abstract void Snap(float facingYaw);
        /// 慢慢转到某个方向（走到某处以后）
        public abstract void Settle(float facingYaw, float pitchWanted = 14f);
        /// 凑近看：坐下、做动作时拉近一些。0 是平常的远近，1 是最近
        public virtual void Focus(float amount) { }
        /// 特写：镜头从 eye 看着 focus（挂布条、系结时凑到跟前看），不管现在是哪个视角；EndCloseUp 回到原来的跟法
        public virtual void CloseUp(Vector3 focus, Vector3 eye) { }
        public virtual void EndCloseUp() { }
    }
}
