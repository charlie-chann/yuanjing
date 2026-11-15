using UnityEngine;

namespace Yuanjing
{
    /// 一条锦鲤：在一片水域里慢悠悠地绕圈游，身子左右摆。模型头朝前（+z）。
    public class Koi : MonoBehaviour
    {
        public Vector3 center;
        public Vector2 radius = new Vector2(2f, 1.5f);
        public float speed = 0.25f, phase;

        public static readonly System.Collections.Generic.List<Koi> All = new System.Collections.Generic.List<Koi>();
        Vector3 lure;
        float lureLeft, lureK;

        void OnEnable() => All.Add(this);
        void OnDisable() => All.Remove(this);

        /// 有人在水边喂鱼：游过去聚在那一小片水里，过一阵散开
        public void Lure(Vector3 at, float seconds)
        {
            lure = new Vector3(at.x, center.y, at.z);
            lureLeft = seconds;
        }

        Vector3 Point(float t)
        {
            Vector3 center = Vector3.Lerp(this.center, lure, lureK);
            Vector2 radius = this.radius * Mathf.Lerp(1f, 0.28f, lureK);
            float a = t * speed + phase;
            float r = 0.62f + 0.38f * Mathf.Sin(a * 0.37f + phase * 2.1f);
            return center + new Vector3(Mathf.Cos(a) * radius.x * r, 0.03f * Mathf.Sin(a * 1.3f), Mathf.Sin(a * 0.83f + phase) * radius.y * r);
        }

        void Update()
        {
            lureLeft -= Time.deltaTime;
            lureK = Mathf.MoveTowards(lureK, lureLeft > 0 ? 1f : 0f, Time.deltaTime * 0.5f);
            float t = Time.time * Mathf.Lerp(1f, 2.2f, lureK);
            Vector3 p = Point(t), ahead = Point(t + 0.25f);
            Vector3 d = ahead - p;
            d.y = 0;
            transform.position = p;
            if (d.sqrMagnitude > 1e-6f)
                transform.rotation = Quaternion.LookRotation(d) * Quaternion.Euler(0, Mathf.Sin(t * 5f + phase * 9f) * 10f, 0);
        }
    }
}
