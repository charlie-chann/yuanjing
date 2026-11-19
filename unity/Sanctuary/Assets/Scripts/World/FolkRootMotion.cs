using UnityEngine;

namespace Yuanjing
{
    /// 挂在人物模型（带 Animator 的那个子物体）上：动画算出这一帧身体该挪多少（走路片段自带的位移），转交给 Folk 去挪人。
    /// 人怎么走全按动画里脚的节奏来，脚就不会在地上滑。
    public class FolkRootMotion : MonoBehaviour
    {
        public Folk folk;

        void OnAnimatorMove()
        {
            if (folk != null) folk.OnRootMotion();
        }
    }
}
