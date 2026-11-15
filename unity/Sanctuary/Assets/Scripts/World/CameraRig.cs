using System;
using System.Collections.Generic;
using UnityEngine;

namespace Yuanjing
{
    /// 第一人称的镜头：沿着一串路点走过去（带脚步的起伏），可以拖动环顾四周，坐下、鞠躬、跪拜时带着视角一起动。
    /// 不做自由行走：点哪里就平稳地走到哪里，画面始终是构图过的。
    public class CameraRig : MonoBehaviour
    {
        public static CameraRig Instance { get; private set; }

        public float walkSpeed = 2.1f;
        public event Action Arrived;
        public event Action Step;

        readonly Queue<Vector3> path = new Queue<Vector3>();
        Vector3 pos, vel, lookAt, lookNow;
        float eye = 1.62f, eyeNow = 1.62f, eyeVel;
        float yaw, pitch, yawTarget, pitchTarget;
        float walked, bob;
        bool moving;

        // 鞠躬、跪拜：0 直立，1 俯到最低
        float bow, bowTarget, bowDepth = 0.5f;
        float bowHold, bowHoldFor = -1;
        int bowsLeft;
        Action bowDone;

        public bool Moving => moving;
        public bool Bowing => bowTarget > 0.5f || bow > 0;
        public float Eye => eye;

        /// 只改眼睛的高度（原地跪下、站起）
        public void SetEye(float eyeHeight) => eye = eyeHeight;
        public Vector3 Position => pos;

        void Awake()
        {
            Instance = this;
            pos = transform.position;
            pos.y = 0;
            lookAt = lookNow = transform.position + transform.forward * 20f;
        }

        /// 直接放到某处（进场时用）。floor 是脚下的地面高度。
        public void Teleport(Vector3 floor, Vector3 look, float eyeHeight)
        {
            path.Clear();
            pos = floor;
            lookAt = lookNow = look;
            eye = eyeNow = eyeHeight;
            yaw = pitch = yawTarget = pitchTarget = 0;
            moving = false;
            Apply(0);
        }

        /// 走到某处。via 是途中要经过的点；到了以后眼睛的高度变成 eyeHeight（坐下就是矮下去）。
        public void GoTo(Vector3 floor, Vector3 look, float eyeHeight, params Vector3[] via)
        {
            path.Clear();
            foreach (var p in via) path.Enqueue(p);
            path.Enqueue(floor);
            arriveLook = look;
            arriveEye = eyeHeight;
            // 走的时候站起来，看着前进的方向
            eye = 1.62f;
            moving = true;
            yawTarget = pitchTarget = 0;
        }

        Vector3 arriveLook;
        float arriveEye;

        /// 拖动环顾。dx、dy 是手指移动占屏幕宽高的比例。
        public void Look(float dx, float dy)
        {
            yawTarget = Mathf.Clamp(yawTarget + dx * 110f, -75f, 75f);
            pitchTarget = Mathf.Clamp(pitchTarget + dy * 70f, -28f, 38f);
        }

        /// 鞠躬（depth 0.5 左右）或跪拜（depth 1，连着几次）
        public void Bow(float depth, int times, Action done, float hold = -1)
        {
            bowHoldFor = hold;
            bowDepth = depth;
            bowsLeft = times;
            bowTarget = 1;
            bowHold = 0;
            bowDone = done;
        }

        void Update()
        {
            float dt = Time.deltaTime;
            if (moving)
            {
                Vector3 target = path.Peek();
                Vector3 to = target - pos;
                float dist = to.magnitude;
                // 快到终点时慢下来
                float speed = walkSpeed * Mathf.Clamp(dist * 1.2f + 0.25f, 0.3f, 1f);
                float step = speed * dt;
                if (dist <= step)
                {
                    pos = target;
                    path.Dequeue();
                    if (path.Count == 0)
                    {
                        moving = false;
                        lookAt = arriveLook;
                        eye = arriveEye;
                        Arrived?.Invoke();
                    }
                }
                else
                {
                    pos += to / dist * step;
                    // 走路时看向前方稍远处
                    Vector3 ahead = pos + to / dist * 8f;
                    lookAt = new Vector3(ahead.x, pos.y + 1.7f, ahead.z);
                    walked += step;
                    if (walked > 0.72f)
                    {
                        walked = 0;
                        Step?.Invoke();
                    }
                    bob += step;
                }
            }
            // 鞠躬的节奏：俯下去，停一下，起来
            if (bowTarget > 0.5f)
            {
                bow = Mathf.MoveTowards(bow, 1, dt / (bowDepth > 0.8f ? 1.5f : 1.1f));
                if (bow >= 1)
                {
                    bowHold += dt;
                    if (bowHold > (bowHoldFor > 0 ? bowHoldFor : bowDepth > 0.8f ? 1.2f : 0.7f)) bowTarget = 0;
                }
            }
            else if (bow > 0)
            {
                bow = Mathf.MoveTowards(bow, 0, dt / 1.3f);
                if (bow <= 0)
                {
                    bowsLeft--;
                    if (bowsLeft > 0)
                    {
                        bowTarget = 1;
                        bowHold = 0;
                    }
                    else
                    {
                        var cb = bowDone;
                        bowDone = null;
                        cb?.Invoke();
                    }
                }
            }
            Apply(dt);
        }

        void Apply(float dt)
        {
            float k = dt <= 0 ? 1 : 1 - Mathf.Exp(-3.2f * dt);
            lookNow = Vector3.Lerp(lookNow, lookAt, k);
            yaw = Mathf.Lerp(yaw, yawTarget, dt <= 0 ? 1 : 1 - Mathf.Exp(-9f * dt));
            pitch = Mathf.Lerp(pitch, pitchTarget, dt <= 0 ? 1 : 1 - Mathf.Exp(-9f * dt));
            eyeNow = dt <= 0 ? eye : Mathf.SmoothDamp(eyeNow, eye, ref eyeVel, 0.55f);

            float b = Mathf.SmoothStep(0, 1, bow);
            float bobY = moving ? Mathf.Sin(bob * Mathf.PI * 2f / 1.44f) * 0.028f : 0;
            float breath = Mathf.Sin(Time.time * 0.95f) * 0.006f;
            Vector3 eyePos = pos + Vector3.up * (eyeNow + bobY + breath);
            Vector3 dir = lookNow - eyePos;
            if (dir.sqrMagnitude < 0.01f) dir = Vector3.forward;
            Quaternion rot = Quaternion.LookRotation(dir.normalized) * Quaternion.Euler(-pitch, yaw, 0);
            // 俯身：头往前往下探，视线跟着低下去
            Vector3 fwd = rot * Vector3.forward;
            fwd.y = 0;
            fwd.Normalize();
            eyePos += fwd * (0.32f * b * bowDepth) + Vector3.down * (eyeNow * 0.62f * b * bowDepth);
            rot = rot * Quaternion.Euler(62f * b * bowDepth, 0, 0);
            transform.SetPositionAndRotation(eyePos, rot);
        }
    }
}
