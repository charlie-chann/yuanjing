using System.Collections;
using UnityEngine;

namespace Yuanjing
{
    /// 钟亭里的钟：撞木横吊着，拉回去、撞上去，钟晃一晃，余音慢慢散。
    public class BellRing : MonoBehaviour
    {
        /// 撞木（原点在悬挂点，吊绳挂着像钟摆一样荡）、钟（原点在悬挂点）。没有就只响不动
        public Transform striker, bell;
        /// 撞木绕哪根轴荡（自己的坐标）：正的角度是撞向钟。bell_striker 模型撞木顺着 x、钟在 -x 那边：绕 z 轴，取 (0,0,-1)
        public Vector3 swingAxis = Vector3.right;
        /// 往后拉多少度、撞到钟上是多少度（静止时撞头离钟还有一拳，荡过去这么多正好碰上）
        public float pullBack = 24f, strike = 9f;
        /// 人站在哪撞（世界坐标）、面朝哪
        public Vector3 stand, face;
        public string sound = "sfx_bell_temple";
        public bool Ringing { get; private set; }
        float bellSwing, bellT;
        Quaternion strikerRest, bellRest;
        bool got;

        void Rest()
        {
            if (got) return;
            got = true;
            if (striker != null) strikerRest = striker.localRotation;
            if (bell != null) bellRest = bell.localRotation;
        }

        /// 撞一下。hit：撞上的那一刻
        public IEnumerator Ring(System.Action hit = null)
        {
            Rest();
            Ringing = true;
            // 往后拉 0.7 秒，撞过去 0.28 秒，弹回来慢慢停
            float t = 0;
            while (t < 0.7f)
            {
                t += Time.deltaTime;
                Swing(Mathf.SmoothStep(0, -pullBack, t / 0.7f));
                yield return null;
            }
            t = 0;
            while (t < 0.28f)
            {
                t += Time.deltaTime;
                float k = t / 0.28f;
                Swing(Mathf.Lerp(-pullBack, strike, k * k));
                yield return null;
            }
            hit?.Invoke();
            var gd = GameDirector.Instance;
            if (gd != null && gd.sound != null) gd.sound.Play(sound, 1f);
            bellSwing = 1f;
            bellT = 0;
            t = 0;
            while (t < 2.4f)
            {
                t += Time.deltaTime;
                Swing(strike * Mathf.Exp(-t * 2.2f) * Mathf.Cos(t * 5.5f));
                yield return null;
            }
            Swing(0);
            Ringing = false;
        }

        void Swing(float deg)
        {
            if (striker != null) striker.localRotation = strikerRest * Quaternion.AngleAxis(deg, swingAxis);
        }

        void Update()
        {
            if (bell == null || bellSwing <= 0.001f) return;
            bellT += Time.deltaTime;
            bellSwing = Mathf.Exp(-bellT * 0.9f);
            bell.localRotation = bellRest * Quaternion.AngleAxis(Mathf.Sin(bellT * 6.2f) * 2.2f * bellSwing, swingAxis);
            if (bellSwing <= 0.02f) { bellSwing = 0; bell.localRotation = bellRest; }
        }
    }
}
