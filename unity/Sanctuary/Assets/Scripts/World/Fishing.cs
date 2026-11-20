using System.Collections.Generic;
using UnityEngine;

namespace Yuanjing
{
    /// 钓鱼：站在水边抛竿，等浮漂往下一沉（咬钩）就提竿。咬钩的时机在这里演；钓上来的是什么鱼由服务器定，
    /// Flutter 拿到以后再告诉这里把哪条鱼提出水面。
    ///
    /// Flutter → 这里（GameDirector 转过来）：fish {action: cast | reel | show(kind) | stop}
    /// 这里 → Flutter：fish {state}
    ///   cast    竿甩出去了，浮漂落水
    ///   bite    咬钩了（window 秒内提竿才算）
    ///   missed  没来得及提，鱼跑了（线还在水里，接着等）
    ///   early   没咬钩就提了竿，空的（收竿）
    ///   hooked  提竿提中了：Flutter 去服务器问是什么鱼，再发 show
    ///   shown   鱼提出水面、拎到眼前了（Flutter 这时出卡片）
    ///   ended   收竿了（自己走开、stop、出了岔子都会发）
    [DefaultExecutionOrder(260)]   // 排在动画、手里拿的东西之后：竿子跟着这一帧的手
    public class Fishing : MonoBehaviour
    {
        public GameDirector game;
        /// 竿、浮漂、每种鱼的模型（没有就用代码拼的简单样子顶着）。鱼的名字是 fish_编号
        public GameObject rodPrefab, bobberPrefab;
        public GameObject[] fishPrefabs = new GameObject[0];
        public Material lineMaterial;
        /// 竿梢在竿子模型里的位置（握把在原点，竿朝 +Z）
        public Vector3 rodTip = new Vector3(0, -0.075f, 2.6f);
        public float waterY = -0.42f;
        /// 咬钩前等多久（秒，最短、最长）、咬钩后多久内提竿算数
        public Vector2 waitRange = new Vector2(3.5f, 9f);
        public float biteWindow = 1.8f;

        enum State { Off, Cast, Wait, Bite, Lift, Show, Away }
        State state = State.Off;
        float t, waitFor, pitch = 40f, pitchVel;
        Vector3 waterPoint, bobFrom, bobPos, dir;
        GameObject rod, bobber, fish;
        LineRenderer line;
        Transform hand, finger;
        string spot = "sea";

        public bool Active => state != State.Off;
        public string Spot => spot;

        static void Tell(string s, string extra = "") => GameDirector.Send($"{{\"type\":\"fish\",\"state\":\"{s}\"{extra}}}");

        /// 两手在身前握着竿：右手在前、左手在后托着
        static readonly Dictionary<string, float> Hold = new Dictionary<string, float>
        {
            // 关节值在侧面图上试出来的（Arm Front-Back 负的是往前）：右手在身前胸口下面一点握着竿，左手在后面托着
            { "Right Arm Down-Up", -0.7f }, { "Right Arm Front-Back", -0.2f }, { "Right Forearm Stretch", -0.15f },
            { "Left Arm Down-Up", -0.74f }, { "Left Arm Front-Back", 0.02f }, { "Left Forearm Stretch", -0.55f },
        };

        /// 浮漂落水的那一点（镜头对着它）
        public Vector3 Float => waterPoint;

        void Make()
        {
            if (rod != null) return;
            rod = rodPrefab != null ? Instantiate(rodPrefab) : Simple(PrimitiveType.Cylinder, new Vector3(0.022f, rodTip.z * 0.5f, 0.022f), new Color(0.62f, 0.5f, 0.28f), true);
            rod.name = "FishingRod";
            bobber = bobberPrefab != null ? Instantiate(bobberPrefab) : Simple(PrimitiveType.Sphere, Vector3.one * 0.06f, new Color(0.85f, 0.16f, 0.12f), false);
            bobber.name = "Bobber";
            var lg = new GameObject("FishingLine");
            line = lg.AddComponent<LineRenderer>();
            line.positionCount = 14;
            line.widthMultiplier = 0.006f;
            line.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            line.receiveShadows = false;
            line.material = lineMaterial != null ? lineMaterial : new Material(Shader.Find("Sprites/Default"));
            line.startColor = line.endColor = new Color(0.95f, 0.95f, 0.9f, 0.85f);
            foreach (var g in new[] { rod, bobber, lg }) { g.transform.SetParent(transform, false); g.SetActive(false); }
        }

        /// 没有模型时顶着用的：一根棍（沿 +Z）、一个球
        static GameObject Simple(PrimitiveType kind, Vector3 scale, Color color, bool alongZ)
        {
            var root = new GameObject();
            var g = GameObject.CreatePrimitive(kind);
            Destroy(g.GetComponent<Collider>());
            g.transform.SetParent(root.transform, false);
            g.transform.localScale = scale;
            if (alongZ) { g.transform.localRotation = Quaternion.Euler(90, 0, 0); g.transform.localPosition = new Vector3(0, 0, scale.y); }
            var mr = g.GetComponent<MeshRenderer>();
            var sh = Shader.Find("Yuanjing/Toon");
            if (sh != null) { mr.material = new Material(sh); mr.material.color = color; if (mr.material.HasProperty("_BaseColor")) mr.material.SetColor("_BaseColor", color); }
            return root;
        }

        /// 抛竿：朝 water 那一点（岸边最近的水）
        public void Cast(Vector3 water, string where)
        {
            if (game == null || game.player == null || state == State.Cast || state == State.Lift || state == State.Show) return;
            Make();
            var p = game.player;
            spot = where;
            dir = water - p.transform.position;
            dir.y = 0;
            if (dir.sqrMagnitude < 0.01f) dir = p.transform.forward;
            dir.Normalize();
            // 浮漂落在哪：顺着这个方向往外找水够深的地方，最远 4.6 米
            waterPoint = p.transform.position + dir * 2.2f;
            for (float d = 4.6f; d >= 1.6f; d -= 0.4f)
            {
                Vector3 q = p.transform.position + dir * d;
                bool deep = !Physics.Raycast(new Vector3(q.x, waterY + 3f, q.z), Vector3.down, out var hit, 8f, ~(1 << 2), QueryTriggerInteraction.Ignore) || hit.point.y < waterY - 0.2f;
                if (deep) { waterPoint = q; break; }
            }
            waterPoint.y = waterY;
            p.FaceTowards(p.transform.position + dir);
            p.custom.Clear();
            foreach (var kv in Hold) p.custom[kv.Key] = kv.Value;
            p.customPitch = 0;
            p.SetPose(Folk.Pose.Custom);
            hand = p.Hand(true);
            finger = hand != null && hand.childCount > 0 ? hand.GetChild(0) : null;
            if (fish != null) { Destroy(fish); fish = null; }
            rod.SetActive(true);
            bobber.SetActive(false);
            line.gameObject.SetActive(false);
            state = State.Cast;
            t = 0;
            pitch = 75f;
            pitchVel = 0;
        }

        /// 提竿
        public void Reel()
        {
            if (state == State.Bite)
            {
                state = State.Lift;
                t = 0;
                if (game.sound != null) game.sound.Play("sfx_drop", 0.6f);
                Tell("hooked", $",\"spot\":\"{spot}\"");
            }
            else if (state == State.Wait || state == State.Away)
            {
                Tell("early");
                Stop(false);
            }
        }

        /// 服务器说钓到的是这个：把它提出水面，拎到眼前
        public void Show(string kind)
        {
            if (state != State.Lift && state != State.Show) return;
            GameObject prefab = null;
            foreach (var f in fishPrefabs) if (f != null && f.name == "fish_" + kind) prefab = f;
            fish = prefab != null ? Instantiate(prefab) : Simple(PrimitiveType.Sphere, new Vector3(0.07f, 0.09f, 0.22f), new Color(0.75f, 0.78f, 0.8f), false);
            fish.name = "Catch";
            fish.transform.SetParent(transform, false);
            fish.transform.position = bobPos;
            state = State.Show;
            t = 0;
        }

        /// 收竿。told：要不要告诉 Flutter（它自己叫停的也回一声，界面好收）
        public void Stop(bool tell = true)
        {
            if (state == State.Off) return;
            state = State.Off;
            if (rod != null) rod.SetActive(false);
            if (bobber != null) bobber.SetActive(false);
            if (line != null) line.gameObject.SetActive(false);
            if (fish != null) { Destroy(fish); fish = null; }
            if (game != null && game.player != null && game.player.pose == Folk.Pose.Custom) game.player.SetPose(Folk.Pose.None);
            if (game != null && game.cam != null) game.cam.EndCloseUp();
            if (tell) Tell("ended");
        }

        Vector3 Palm => hand == null ? transform.position : finger == null ? hand.position : Vector3.Lerp(hand.position, finger.position, 0.6f);

        void LateUpdate()
        {
            if (state == State.Off || game == null || game.player == null) return;
            float dt = Time.deltaTime;
            t += dt;
            // 竿子抬多高（度）：甩竿从身后甩到前面；等的时候斜斜举着；咬钩时竿梢被拽得一点一点；提竿时扬起来
            float want = 28f;
            switch (state)
            {
                case State.Cast:
                    want = t < 0.35f ? 105f : 22f;
                    if (t > 0.5f && !bobber.activeSelf)
                    {
                        bobber.SetActive(true);
                        line.gameObject.SetActive(true);
                        bobFrom = Tip();
                    }
                    if (t > 0.5f)
                    {
                        float k = Mathf.Clamp01((t - 0.5f) / 0.75f);
                        bobPos = Vector3.Lerp(bobFrom, waterPoint, k) + Vector3.up * Mathf.Sin(k * Mathf.PI) * 1.1f;
                        if (k >= 1f)
                        {
                            state = State.Wait;
                            t = 0;
                            waitFor = Random.Range(waitRange.x, waitRange.y);
                            if (game.sound != null) game.sound.Play("sfx_drop", 0.45f);
                            Tell("cast", $",\"spot\":\"{spot}\"");
                        }
                    }
                    break;
                case State.Wait:
                case State.Away:
                    bobPos = waterPoint + Vector3.up * (Mathf.Sin(Time.time * 1.7f) * 0.012f + (state == State.Away ? Mathf.Max(0, 0.06f - t * 0.2f) : 0f));
                    // 快咬钩前浮漂先轻轻点两下
                    if (state == State.Wait && waitFor - t < 1.1f) bobPos.y -= Mathf.Max(0, Mathf.Sin((waitFor - t) * 14f)) * 0.018f;
                    if (state == State.Away && t > 0.6f) { state = State.Wait; t = 0; waitFor = Random.Range(waitRange.x, waitRange.y); }
                    else if (state == State.Wait && t >= waitFor)
                    {
                        state = State.Bite;
                        t = 0;
                        if (game.sound != null) game.sound.Play("sfx_drop", 0.7f);
                        Tell("bite", $",\"window\":{biteWindow.ToString("F2", System.Globalization.CultureInfo.InvariantCulture)}");
                    }
                    break;
                case State.Bite:
                    want = 20f + Mathf.Sin(Time.time * 31f) * 3f;
                    bobPos = waterPoint + Vector3.down * (0.07f + Mathf.Sin(Time.time * 26f) * 0.02f) + dir * Mathf.Sin(Time.time * 9f) * 0.05f;
                    if (t > biteWindow)
                    {
                        state = State.Away;
                        t = 0;
                        Tell("missed");
                    }
                    break;
                case State.Lift:
                    want = 62f;
                    bobPos = Vector3.Lerp(bobPos, HoldPoint(), 1 - Mathf.Exp(-3.5f * dt));
                    // 服务器一直没回（断网）：等 6 秒就收竿
                    if (t > 6f) Stop();
                    break;
                case State.Show:
                    want = 66f;
                    bobPos = Vector3.Lerp(bobPos, HoldPoint(), 1 - Mathf.Exp(-5f * dt));
                    if (fish != null)
                    {
                        // 鱼挂在线上甩尾巴：嘴朝上，身子左右摆，慢慢转
                        fish.transform.position = bobPos;
                        fish.transform.rotation = Quaternion.Euler(-90f + Mathf.Sin(Time.time * 13f) * 9f * Mathf.Exp(-t * 0.5f), Time.time * 40f, Mathf.Sin(Time.time * 17f) * 14f * Mathf.Exp(-t * 0.5f));
                    }
                    if (t - dt < 0.7f && t >= 0.7f)
                    {
                        Vector3 me = game.player.transform.position;
                        Vector3 focus = HoldPoint() + Vector3.down * 0.12f;
                        Vector3 eye = focus - dir * 1.15f + Vector3.Cross(Vector3.up, dir) * 0.55f + Vector3.up * 0.12f;
                        game.cam.CloseUp(focus, eye);
                        Tell("shown");
                    }
                    break;
            }
            pitch = Mathf.SmoothDamp(pitch, want, ref pitchVel, state == State.Cast ? 0.12f : 0.22f);
            Quaternion rot = Quaternion.LookRotation(Quaternion.AngleAxis(-pitch, Vector3.Cross(Vector3.up, dir)) * dir, Vector3.up);
            rod.transform.SetPositionAndRotation(Palm, rot);
            if (bobber.activeSelf)
            {
                bobber.transform.position = bobPos;
                bobber.SetActive(state != State.Show || fish == null);
                Vector3 a = Tip(), b = bobPos;
                // 线：松的时候往下垂，提竿时绷直
                float sag = state == State.Lift || state == State.Show ? 0.02f : state == State.Bite ? 0.05f : Mathf.Min(0.5f, Vector3.Distance(a, b) * 0.16f);
                for (int i = 0; i < line.positionCount; i++)
                {
                    float k = i / (float)(line.positionCount - 1);
                    Vector3 p = Vector3.Lerp(a, b, k);
                    p.y -= Mathf.Sin(k * Mathf.PI) * sag;
                    p.y = Mathf.Max(p.y, Mathf.Min(a.y, b.y) - 0.02f);
                    line.SetPosition(i, p);
                }
            }
            else if (state == State.Show && fish != null)
            {
                Vector3 a = Tip(), b = bobPos;
                for (int i = 0; i < line.positionCount; i++) line.SetPosition(i, Vector3.Lerp(a, b, i / (float)(line.positionCount - 1)));
            }
        }

        Vector3 Tip() => rod.transform.TransformPoint(rodTip);

        /// 提上来的鱼拎在哪：人前面半米多、胸口高
        Vector3 HoldPoint()
        {
            var p = game.player.transform;
            return p.position + dir * 0.62f + Vector3.up * (1.02f * p.lossyScale.y / 0.806f);
        }
    }
}
