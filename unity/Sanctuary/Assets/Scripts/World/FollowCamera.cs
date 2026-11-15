using UnityEngine;

namespace Yuanjing
{
    /// 雨雪的发射区域一直跟着镜头走，这样只需要在镜头周围下雨。
    public class FollowCamera : MonoBehaviour
    {
        public Vector3 offset;
        /// 不跟镜头、改跟这个东西（俯视镜头离人很远，雨雪要下在人周围）
        public Transform anchor;

        void LateUpdate()
        {
            if (anchor != null) { transform.position = new Vector3(anchor.position.x, 0, anchor.position.z) + offset; return; }
            var cam = Camera.main;
            if (cam != null) Snap(cam.transform);
        }

        public void Snap(Transform cam)
        {
            if (anchor != null) { transform.position = new Vector3(anchor.position.x, 0, anchor.position.z) + offset; return; }
            // 发射区域往镜头前方挪一些：看得见的那一边雨更密
            Vector3 f = cam.forward;
            f.y = 0;
            transform.position = new Vector3(cam.position.x, 0, cam.position.z) + f.normalized * 6f + offset;
        }
    }
}
