using System;
using System.Collections.Generic;
using UnityEngine;

namespace Yuanjing
{
    /// 头发、裙摆、衣带的摆动：人一动，它们慢半拍跟上、再荡回来。
    /// 做法同 VRM 的 SpringBone：每根骨头记着自己「尾巴」上一刻在哪，惯性、回弹、重力三样加起来算出这一刻在哪，
    /// 再把骨头转过去对准它。参数是从原模型里读出来的（tools/blender/vrm_import.py）。
    [DefaultExecutionOrder(200)]   // 排在动画和 Folk 摆姿势之后
    public class SpringBones : MonoBehaviour
    {
        [Serializable]
        public class Group
        {
            public Transform[] roots;
            public float stiffness = 1f, gravity = 0f, drag = 0.4f;
        }

        public List<Group> groups = new List<Group>();

        /// 碰撞球：裙子、头发会被推到球面外（裙子不会穿过大腿，坐下、跪下时搭在腿上）
        [Serializable]
        public class Sphere { public Transform from, to; public float t, radius; }
        public List<Sphere> colliders = new List<Sphere>();
        /// 只有名字里带这些字的摆动骨骼才和碰撞球碰（裙子）；头发另算
        public string collideNames = "Skirt";

        class Joint
        {
            public Transform t;
            public Vector3 axis;           // 尾巴在骨头自己坐标里的方向
            public float length;           // 骨头到尾巴的距离（局部长度，乘上缩放才是世界里的）
            public Quaternion rest;        // 静止时相对父骨头的转角
            public Vector3 tail, prev;
            public Group g;
            public bool collide;
        }

        readonly List<Joint> joints = new List<Joint>();
        Vector3 lastRoot;

        void Start()
        {
            foreach (var g in groups)
                foreach (var r in g.roots)
                    if (r != null) Add(r, g);
            lastRoot = transform.position;
        }

        void Add(Transform t, Group g)
        {
            Vector3 local = t.childCount > 0 ? t.GetChild(0).localPosition : Vector3.up * 0.05f;
            if (local.sqrMagnitude < 1e-8f) local = Vector3.up * 0.05f;
            var j = new Joint { t = t, axis = local.normalized, length = local.magnitude, rest = t.localRotation, g = g,
                                collide = !string.IsNullOrEmpty(collideNames) && t.name.Contains(collideNames) };
            j.tail = j.prev = t.TransformPoint(local);
            joints.Add(j);
            for (int i = 0; i < t.childCount; i++) Add(t.GetChild(i), g);
        }

        void LateUpdate()
        {
            float dt = Mathf.Min(Time.deltaTime, 0.05f);
            if (dt <= 0f) return;
            // 离镜头远的人，头发怎么摆都看不出来：省下这份计算（几十个人同时在场）
            var cam = Camera.main;
            if (cam != null && (cam.transform.position - transform.position).sqrMagnitude > Mathf.Pow(18f * Mathf.Max(1f, 40f / cam.fieldOfView), 2f))
            {
                lastRoot = transform.position;
                return;
            }
            // 被瞬移了（进场、传送）：别让头发甩一大圈，直接跟过去
            Vector3 jump = transform.position - lastRoot;
            bool teleported = jump.sqrMagnitude > 1.5f * 1.5f;
            lastRoot = transform.position;
            float scale = transform.lossyScale.y;
            foreach (var j in joints)
            {
                if (teleported) { j.tail += jump; j.prev += jump; }
                Quaternion parent = j.t.parent != null ? j.t.parent.rotation : Quaternion.identity;
                Quaternion restWorld = parent * j.rest;
                Vector3 pos = j.t.position;
                float len = j.length * scale;
                Vector3 next = j.tail + (j.tail - j.prev) * (1f - j.g.drag)
                               + restWorld * j.axis * (j.g.stiffness * dt * scale)
                               + Vector3.down * (j.g.gravity * dt * scale);
                next = pos + (next - pos).normalized * len;
                if (j.collide)
                    foreach (var c in colliders)
                    {
                        if (c.from == null) continue;
                        Vector3 cp = c.to != null ? Vector3.Lerp(c.from.position, c.to.position, c.t) : c.from.position;
                        float r = c.radius * scale;
                        Vector3 d = next - cp;
                        if (d.sqrMagnitude < r * r && d.sqrMagnitude > 1e-8f) next = pos + ((cp + d.normalized * r) - pos).normalized * len;
                    }
                j.prev = j.tail;
                j.tail = next;
                j.t.rotation = Quaternion.FromToRotation(restWorld * j.axis, next - pos) * restWorld;
            }
        }
    }
}
