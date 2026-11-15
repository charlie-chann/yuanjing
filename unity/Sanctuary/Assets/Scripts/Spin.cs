using UnityEngine;

/// 链路测试用：让物体转起来
public class Spin : MonoBehaviour
{
    public float speed = 40f;

    void Update()
    {
        transform.Rotate(0f, speed * Time.deltaTime, speed * 0.3f * Time.deltaTime);
    }
}
