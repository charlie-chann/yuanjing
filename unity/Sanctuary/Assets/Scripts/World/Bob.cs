using UnityEngine;

namespace Yuanjing
{
    /// 浮在水上的东西（小船）：轻轻地上下起伏、左右晃
    public class Bob : MonoBehaviour
    {
        public float height = 0.025f, roll = 2.2f, speed = 0.9f;
        Vector3 basePos;
        Quaternion baseRot;

        void Start()
        {
            basePos = transform.position;
            baseRot = transform.rotation;
        }

        void Update()
        {
            float t = Time.time * speed;
            transform.position = basePos + Vector3.up * (Mathf.Sin(t) * height);
            transform.rotation = baseRot * Quaternion.Euler(Mathf.Sin(t * 0.8f + 1f) * roll * 0.5f, 0, Mathf.Sin(t * 1.1f) * roll);
        }
    }
}
