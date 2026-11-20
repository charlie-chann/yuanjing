using System.Collections.Generic;
using UnityEngine;

namespace Yuanjing
{
    /// 小鸟：在地上蹦着啄食，人一走近就扑棱棱飞到别处落下；撒了谷子会飞过来吃。
    /// 落脚点由生成场景时给（地面的、高处的都有）。两只翅膀是单独的部件，飞的时候拍、落下时收起来。
    public class Bird : MonoBehaviour
    {
        public static readonly List<Bird> All = new List<Bird>();
        /// 能落脚的地方；w 是 1 表示在地面上（会蹦、会啄），0 是高处（只站着）
        public static readonly List<Vector4> Perches = new List<Vector4>();

        public Vector4[] perches = new Vector4[0];
        Transform wingL, wingR, tail;
        Vector3 pivotL, pivotR;
        Vector3 from, to, around;
        float flyT = -1, flyDur, next, hopT, peck, feedLeft;
        bool onGround = true;

        /// 这会儿落在地上（没在飞）：人走到附近才显示「喂小鸟」
        public bool Grounded => onGround && !(flyT > -900 && flyT < flyDur && flyDur > 0);

        void OnEnable() => All.Add(this);
        void OnDisable() => All.Remove(this);

        void Awake()
        {
            foreach (Transform c in transform)
            {
                if (c.name == "wing_l") wingL = c;
                else if (c.name == "wing_r") wingR = c;
            }
            if (wingL != null) { var b = wingL.GetComponent<MeshFilter>().sharedMesh.bounds; pivotL = new Vector3(b.max.x, b.center.y, b.center.z); }
            if (wingR != null) { var b = wingR.GetComponent<MeshFilter>().sharedMesh.bounds; pivotR = new Vector3(b.min.x, b.center.y, b.center.z); }
            if (Perches.Count == 0) foreach (var p in perches) Perches.Add(p);
            next = Random.Range(4f, 20f);
            around = transform.position;
        }

        void OnDestroy()
        {
            if (All.Count == 0) Perches.Clear();
        }

        /// 有人在这附近撒了谷子：飞过去吃一阵
        public void Feed(Vector3 at)
        {
            Vector2 r = Random.insideUnitCircle * 0.9f;
            feedLeft = Random.Range(10f, 14f);
            FlyTo(at + new Vector3(r.x, 0, r.y), true, Random.Range(0f, 0.8f));
        }

        void FlyTo(Vector3 p, bool ground, float delay = 0)
        {
            from = transform.position;
            to = p;
            onGround = ground;
            flyDur = Mathf.Clamp(Vector3.Distance(from, to) / 5.5f, 0.7f, 3.2f);
            flyT = -delay;
        }

        void Pick()
        {
            if (Perches.Count == 0) return;
            for (int k = 0; k < 6; k++)
            {
                var p = Perches[Random.Range(0, Perches.Count)];
                Vector3 q = new Vector3(p.x, p.y, p.z);
                if (Vector3.Distance(q, transform.position) < 2f) continue;
                var pl = GameDirector.Instance != null && GameDirector.Instance.player != null ? GameDirector.Instance.player.transform.position : Vector3.one * 999;
                if (p.w > 0.5f && Vector3.Distance(q, pl) < 3f) continue;
                Vector2 r = Random.insideUnitCircle * (p.w > 0.5f ? 0.8f : 0.05f);
                FlyTo(q + new Vector3(r.x, 0, r.y), p.w > 0.5f);
                return;
            }
        }

        static void Wing(Transform t, Vector3 pivot, float angle, float fold)
        {
            if (t == null) return;
            var r = Quaternion.Euler(0, fold, angle);
            t.localRotation = r;
            t.localPosition = pivot - r * pivot;
        }

        void Update()
        {
            float dt = Time.deltaTime, t = Time.time;
            if (flyT > -900 && flyT < flyDur && flyDur > 0 && (flyT += dt) >= 0)
            {
                // 飞：一条拱起来的弧线，翅膀快速拍
                float k = Mathf.Clamp01(flyT / flyDur);
                float e = k * k * (3 - 2 * k);
                Vector3 p = Vector3.Lerp(from, to, e);
                p.y += Mathf.Sin(k * Mathf.PI) * Mathf.Clamp(Vector3.Distance(from, to) * 0.28f, 0.6f, 2.6f);
                Vector3 d = to - from;
                d.y = 0;
                if (d.sqrMagnitude > 0.01f) transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(d), 1 - Mathf.Exp(-10f * dt));
                transform.position = p;
                float flap = Mathf.Sin(t * 42f) * 55f;
                Wing(wingL, pivotL, -flap, 0);
                Wing(wingR, pivotR, flap, 0);
                if (k >= 1)
                {
                    flyDur = 0;
                    around = to;
                    next = Random.Range(8f, 26f);
                    hopT = Random.Range(0.3f, 1.2f);
                }
                return;
            }
            // 落着：翅膀收在身侧
            Wing(wingL, pivotL, 70f, -55f);
            Wing(wingR, pivotR, -70f, 55f);
            feedLeft -= dt;
            var gd = GameDirector.Instance;
            if (gd != null && gd.player != null && feedLeft <= 0 && onGround && Vector3.Distance(gd.player.transform.position, transform.position) < 1.9f)
            {
                Pick();
                return;
            }
            next -= dt;
            if (next <= 0 && feedLeft <= 0) { Pick(); next = Random.Range(8f, 26f); return; }
            if (!onGround) return;
            // 在地上：隔一会儿蹦一小步，不时低头啄一下
            hopT -= dt;
            if (hopT <= 0)
            {
                hopT = Random.Range(0.5f, feedLeft > 0 ? 1.0f : 2.2f);
                if (Random.value < 0.6f) peck = 0.35f;
                else
                {
                    Vector2 r = Random.insideUnitCircle.normalized * Random.Range(0.08f, 0.22f);
                    Vector3 p = transform.position + new Vector3(r.x, 0, r.y);
                    if (Vector3.Distance(p, around) < 1.3f)
                    {
                        transform.rotation = Quaternion.LookRotation(new Vector3(r.x, 0, r.y));
                        from = transform.position;
                        to = p;
                        flyDur = 0;
                        transform.position = p;
                    }
                }
            }
            peck = Mathf.Max(0, peck - dt);
            float nod = peck > 0 ? Mathf.Sin((0.35f - peck) / 0.35f * Mathf.PI) * 50f : 0;
            transform.rotation = Quaternion.Euler(nod, transform.eulerAngles.y, 0);
        }
    }
}
