using System.Globalization;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Animations;
using UnityEngine.Playables;

/// 走路片段的自查：每段步态在某个人物身上真正走多快（着地那只脚往后退的速度）、平均速度、根运动的曲线。
///   unity/run.sh MotionDiag.Run [-who shino]
public static class MotionDiag
{
    public static void Run()
    {
        string who = SanctuaryBuild.Arg("-who") ?? "shino";
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"Assets/Characters/Built/Folk_anime_{who}.prefab");
        var go = (GameObject)Object.Instantiate(prefab);
        var folk = go.GetComponent<Yuanjing.Folk>();
        var anim = go.GetComponentInChildren<Animator>();
        var clips = folk.gaitClips.Concat(new[] { folk.stopClip, folk.stopMirrorClip, folk.turnClip, folk.turnMirrorClip }).Where(c => c != null).ToArray();
        Object.DestroyImmediate(folk);
        foreach (var sb in go.GetComponentsInChildren<Yuanjing.SpringBones>()) Object.DestroyImmediate(sb);
        go.transform.position = Vector3.zero;
        var lf = anim.GetBoneTransform(HumanBodyBones.LeftFoot);
        var rf = anim.GetBoneTransform(HumanBodyBones.RightFoot);
        foreach (var clip in clips)
        {
            var graph = PlayableGraph.Create("diag");
            var output = AnimationPlayableOutput.Create(graph, "a", anim);
            var cp = AnimationClipPlayable.Create(graph, clip);
            cp.SetApplyFootIK(true);
            output.SetSourcePlayable(cp);
            int N = 120;
            float sum = 0; int n = 0;
            float prevL = 0, prevR = 0;
            float minL = 9, minR = 9;
            var zs = new float[N + 1];
            for (int f = 0; f <= N; f++)
            {
                cp.SetTime(clip.length * f / N);
                graph.Evaluate(0);
                minL = Mathf.Min(minL, lf.position.y); minR = Mathf.Min(minR, rf.position.y);
            }
            string contact = "";
            for (int f = 0; f <= N; f++)
            {
                cp.SetTime(clip.length * f / N);
                graph.Evaluate(0);
                float zl = go.transform.InverseTransformPoint(lf.position).z, zr = go.transform.InverseTransformPoint(rf.position).z;
                bool l = lf.position.y < minL + 0.012f, r = rf.position.y < minR + 0.012f;
                if (f % 6 == 0) contact += l && r ? "B" : l ? "L" : r ? "R" : "-";
                if (f > 0 && (l || r))
                {
                    float dt = clip.length / N;
                    float v = l && (!r || lf.position.y <= rf.position.y) ? (prevL - zl) / dt : (prevR - zr) / dt;
                    sum += v; n++;
                }
                prevL = zl; prevR = zr;
            }
            // 按相位分 10 段：着地脚往后退的速度 / 根运动的速度
            var bins = new float[10]; var cnt = new int[10]; var rbins = new float[10];
            var bz0 = AnimationUtility.GetEditorCurve(clip, EditorCurveBinding.FloatCurve("", typeof(Animator), "RootT.z"));
            var bx0 = AnimationUtility.GetEditorCurve(clip, EditorCurveBinding.FloatCurve("", typeof(Animator), "RootT.x"));
            float k = anim.humanScale * go.transform.lossyScale.y;
            for (int f = 1; f <= N; f++)
            {
                float t0 = clip.length * (f - 1) / N, t1 = clip.length * f / N, dt = t1 - t0;
                cp.SetTime(t0); graph.Evaluate(0);
                Vector3 l0 = go.transform.InverseTransformPoint(lf.position), r0 = go.transform.InverseTransformPoint(rf.position);
                cp.SetTime(t1); graph.Evaluate(0);
                Vector3 l1 = go.transform.InverseTransformPoint(lf.position), r1 = go.transform.InverseTransformPoint(rf.position);
                bool useL = l1.y < r1.y;
                float fv = useL ? (l0.z - l1.z) / dt : (r0.z - r1.z) / dt;
                float rv = bz0 == null ? 0 : new Vector2(bx0.Evaluate(t1) - bx0.Evaluate(t0), bz0.Evaluate(t1) - bz0.Evaluate(t0)).magnitude / dt * k;
                int b = Mathf.Min(9, (f - 1) * 10 / N);
                bins[b] += fv; rbins[b] += rv; cnt[b]++;
            }
            var lul = anim.GetBoneTransform(HumanBodyBones.LeftUpperLeg); var rul = anim.GetBoneTransform(HumanBodyBones.RightUpperLeg);
            string facing = "";
            foreach (float u in new[] { 0f, 0.25f, 0.5f, 0.75f, 1f })
            {
                cp.SetTime(clip.length * u); graph.Evaluate(0);
                Vector3 fw = Vector3.Cross(Vector3.up, go.transform.InverseTransformDirection(lul.position - rul.position));
                facing += $" {Mathf.Atan2(fw.x, fw.z) * Mathf.Rad2Deg:F0}";
            }
            Debug.Log($"[yuanjing] 朝向 {clip.name}（身体朝向，度，0 = 人物前方）：{facing}");
            string prof = string.Join(" ", Enumerable.Range(0, 10).Select(b => $"{bins[b] / Mathf.Max(1, cnt[b]):F2}/{rbins[b] / Mathf.Max(1, cnt[b]):F2}"));
            Debug.Log($"[yuanjing] 相位剖面 {clip.name}（脚/根）：{prof}");
            graph.Destroy();
            // 根运动曲线（人形片段里的 RootT）
            var bz = EditorCurveBinding.FloatCurve("", typeof(Animator), "RootT.z");
            var bx = EditorCurveBinding.FloatCurve("", typeof(Animator), "RootT.x");
            var cz = AnimationUtility.GetEditorCurve(clip, bz);
            var cx = AnimationUtility.GetEditorCurve(clip, bx);
            string root = cz == null ? "无 RootT" : $"RootT 起 ({cx.Evaluate(0):F3},{cz.Evaluate(0):F3}) 末 ({cx.Evaluate(clip.length):F3},{cz.Evaluate(clip.length):F3})";
            Debug.Log(string.Format(CultureInfo.InvariantCulture, "[yuanjing] 片段 {0}：{1:F3} 秒，averageSpeed {2}（{3:F3}），humanScale {4:F3} 缩放 {5:F3} → 按平均速度 {6:F3} 米/秒；着地脚往后退 {7:F3} 米/秒；{8}；着地 {9}；循环 {10}",
                clip.name, clip.length, clip.averageSpeed.ToString("F3"), clip.averageSpeed.magnitude, anim.humanScale, go.transform.lossyScale.y,
                clip.averageSpeed.magnitude * anim.humanScale * go.transform.lossyScale.y, n > 0 ? sum / n : 0, root, contact, clip.isLooping));
        }
        Object.DestroyImmediate(go);
    }
    /// 步态片段首尾接缝：片段单独在人物上播，跨过循环点逐帧看手、脚（相对根）有没有一帧跳
    ///   unity/run.sh MotionDiag.Wrap [-who shino]
    public static void Wrap()
    {
        string who = SanctuaryBuild.Arg("-who") ?? "shino";
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"Assets/Characters/Built/Folk_anime_{who}.prefab");
        var go = (GameObject)Object.Instantiate(prefab);
        var folk = go.GetComponent<Yuanjing.Folk>();
        var anim = go.GetComponentInChildren<Animator>();
        var clips = SanctuaryBuild.Arg("-act") != null ? folk.actionClips.Where(c => c != null && (c.name.EndsWith("_Loop") || c.name.EndsWith("_Scrub"))).ToArray() : folk.gaitClips.ToArray();
        Object.DestroyImmediate(folk);
        foreach (var sb in go.GetComponentsInChildren<Yuanjing.SpringBones>()) Object.DestroyImmediate(sb);
        go.transform.position = Vector3.zero;
        var lh = anim.GetBoneTransform(HumanBodyBones.LeftHand);
        var rh = anim.GetBoneTransform(HumanBodyBones.RightHand);
        var lf = anim.GetBoneTransform(HumanBodyBones.LeftFoot);
        foreach (var clip in clips)
        {
            var graph = PlayableGraph.Create("diag");
            var output = AnimationPlayableOutput.Create(graph, "a", anim);
            var cp = AnimationClipPlayable.Create(graph, clip);
            cp.SetApplyFootIK(true);
            output.SetSourcePlayable(cp);
            float L = clip.length;
            string s = "";
            foreach (float off in new[] { -3f, -2f, -1f, -0.5f, -0.1f, 0f, 0.001f, 0.1f, 0.5f, 1f, 2f, 3f })
            {
                cp.SetTime(L + off / 60f);
                graph.Evaluate(0);
                Vector3 a = go.transform.InverseTransformPoint(lh.position), b = go.transform.InverseTransformPoint(rh.position), f = go.transform.InverseTransformPoint(lf.position);
                s += $"\n   t=L{off:+0.###;-0.###;+0}f  左手 {a.x:F3},{a.y:F3},{a.z:F3}  右手 {b.x:F3},{b.y:F3},{b.z:F3}  左脚 {f.z:F3}";
            }
            // 按播放推进（不 SetTime）：从 L-5 帧起每帧 1/60 推过去
            cp.SetTime(L - 5f / 60f);
            graph.Evaluate(0);
            s += "\n   推进:";
            for (int i = 0; i < 10; i++)
            {
                graph.Evaluate(1f / 60f);
                Vector3 a = go.transform.InverseTransformPoint(lh.position);
                s += $" [{cp.GetTime():F3} {a.x:F3},{a.y:F3},{a.z:F3}]";
            }
            // 片段里手臂肌肉曲线首尾
            string mus = "";
            foreach (var bnd in AnimationUtility.GetCurveBindings(clip))
            {
                if (!bnd.propertyName.Contains("Arm") && !bnd.propertyName.Contains("Hand") && !bnd.propertyName.Contains("Shoulder")) continue;
                var c = AnimationUtility.GetEditorCurve(clip, bnd);
                float v0 = c.Evaluate(0), v1 = c.Evaluate(L), vm = c.Evaluate(1f / 60f), vn = c.Evaluate(L - 1f / 60f);
                if (Mathf.Abs(v0 - v1) > 0.01f || Mathf.Abs(vm - v0) > 0.05f) mus += $" {bnd.propertyName} {vn:F3}|{v1:F3}→{v0:F3}|{vm:F3}";
            }
            Debug.Log($"[yuanjing] 接缝 {clip.name} 长 {L:F4} 循环 {clip.isLooping} {s}\n   手臂曲线首尾不一致:{mus}");
            graph.Destroy();
        }
        Object.DestroyImmediate(go);
    }
    /// 各段走路片段在人物身上的脚有多高（和待机比），走的方向偏不偏（averageSpeed 横向分量 → 角度）
    ///   unity/run.sh MotionDiag.Level [-who shino]
    public static void Level()
    {
        foreach (string who in (SanctuaryBuild.Arg("-who") ?? "shino,dshibu,fumiriya").Split(','))
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"Assets/Characters/Built/Folk_anime_{who}.prefab");
            var go = (GameObject)Object.Instantiate(prefab);
            var folk = go.GetComponent<Yuanjing.Folk>();
            var anim = go.GetComponentInChildren<Animator>();
            var list = new System.Collections.Generic.List<(AnimationClip c, string kind)>();
            foreach (var c in folk.idleClips) list.Add((c, "idle"));
            foreach (var c in folk.gaitClips) list.Add((c, "gait"));
            foreach (var c in new[] { folk.stopClip, folk.stopMirrorClip }) if (c != null) list.Add((c, "stop"));
            foreach (var c in new[] { folk.turnClip, folk.turnMirrorClip }) if (c != null) list.Add((c, "turn"));
            Object.DestroyImmediate(folk);
            foreach (var sb in go.GetComponentsInChildren<Yuanjing.SpringBones>()) Object.DestroyImmediate(sb);
            go.transform.position = Vector3.zero;
            var lf = anim.GetBoneTransform(HumanBodyBones.LeftFoot);
            var rf = anim.GetBoneTransform(HumanBodyBones.RightFoot);
            var lt = anim.GetBoneTransform(HumanBodyBones.LeftToes);
            var rt = anim.GetBoneTransform(HumanBodyBones.RightToes);
            float k = anim.humanScale * go.transform.lossyScale.y;
            string s = $"[yuanjing] 脚高 {who}（humanScale×缩放 {k:F3}）：";
            foreach (var (clip, kind) in list)
            {
                var graph = PlayableGraph.Create("lvl");
                var output = AnimationPlayableOutput.Create(graph, "a", anim);
                var cp = AnimationClipPlayable.Create(graph, clip);
                cp.SetApplyFootIK(true);
                output.SetSourcePlayable(cp);
                int N = 80;
                var foot = new System.Collections.Generic.List<float>();
                var toe = new System.Collections.Generic.List<float>();
                for (int f = 0; f <= N; f++)
                {
                    float u = f / (float)N;
                    if (kind == "stop" && u < 0.75f) continue;     // 停步：最后站稳的那段
                    if (kind == "turn" && u > 0.12f) continue;     // 转身起步：开头站着的那段
                    cp.SetTime(clip.length * u);
                    graph.Evaluate(0);
                    foot.Add(Mathf.Min(lf.position.y, rf.position.y));
                    toe.Add(Mathf.Min(lt.position.y, rt.position.y));
                }
                foot.Sort(); toe.Sort();
                // 站姿：两脚相对根的位置（停步取最后一帧，待机取开头）
                string stance = "";
                if (kind == "stop" || kind == "idle")
                {
                    anim.applyRootMotion = false;
                    go.transform.position = Vector3.zero; go.transform.rotation = Quaternion.identity;
                    cp.SetTime(kind == "stop" ? clip.length : 0); graph.Evaluate(0);
                    Vector3 a = go.transform.InverseTransformPoint(lf.position), b = go.transform.InverseTransformPoint(rf.position);
                    Vector3 hp = go.transform.InverseTransformPoint(anim.GetBoneTransform(HumanBodyBones.Hips).position);
                    stance = $" 站姿 左脚({a.x:+0.000;-0.000},{a.z:+0.000;-0.000}) 右脚({b.x:+0.000;-0.000},{b.z:+0.000;-0.000}) 髋({hp.x:+0.000;-0.000},{hp.z:+0.000;-0.000}) 宽 {a.x - b.x:F3}";
                }
                float fq = kind == "gait" ? foot[foot.Count / 10] : foot.Average(), tq = kind == "gait" ? toe[toe.Count / 10] : toe.Average();
                var av = clip.averageSpeed;
                // 停步、转身：分几段看根运动往哪走（逐帧推进，累加 deltaPosition）
                string seg = "";
                if (kind == "stop" || kind == "turn")
                {
                    anim.applyRootMotion = true;
                    go.transform.position = Vector3.zero; go.transform.rotation = Quaternion.identity;
                    cp.SetTime(0); graph.Evaluate(0);
                    Vector3 acc = Vector3.zero; float tw = 0; float yawAcc = 0;
                    for (int f = 1; f * (1f / 60f) <= clip.length + 1e-4f; f++)
                    {
                        graph.Evaluate(1f / 60f);
                        acc += anim.deltaPosition; yawAcc += anim.deltaRotation.eulerAngles.y > 180 ? anim.deltaRotation.eulerAngles.y - 360 : anim.deltaRotation.eulerAngles.y;
                        float t = f / 60f;
                        if (t - tw >= 0.25f - 1e-4f || f * (1f / 60f) + 1f / 60f > clip.length + 1e-4f)
                        {
                            seg += $" [{tw:F2}-{t:F2} {acc.x / k:+0.000;-0.000},{acc.z / k:+0.000;-0.000} 转{yawAcc:F0}]";
                            acc = Vector3.zero; tw = t; yawAcc = 0;
                        }
                    }
                }
                s += $"\n   {clip.name,-24} {kind} 脚踝 {fq:F4} 脚趾 {tq:F4}  走向偏 {Mathf.Atan2(av.x, av.z) * Mathf.Rad2Deg:F2}° (avg {av.x:F3},{av.z:F3}){seg}{stance}";
                graph.Destroy();
            }
            Debug.Log(s);
            Object.DestroyImmediate(go);
        }
    }
    /// 转身起步片段里腿的扭转肌肉（看是不是被人形的范围卡住了）
    public static void TurnMuscles()
    {
        foreach (var path in new[] { "Assets/Motion/Walk_TurnStart_F.fbx" })
            foreach (var clip in AssetDatabase.LoadAllAssetsAtPath(path).OfType<AnimationClip>().Where(c => !c.name.StartsWith("__preview")))
            {
                string s = $"[yuanjing] 腿扭转 {clip.name}：";
                foreach (var b in AnimationUtility.GetCurveBindings(clip))
                {
                    if (!b.propertyName.Contains("Twist") && !b.propertyName.Contains("Foot")) continue;
                    if (!b.propertyName.Contains("Leg") && !b.propertyName.Contains("Foot")) continue;
                    var c = AnimationUtility.GetEditorCurve(clip, b);
                    s += $"\n   {b.propertyName,-34}";
                    for (float t = 0; t <= clip.length + 1e-3f; t += 0.1f) s += $" {c.Evaluate(t):+0.00;-0.00}";
                }
                Debug.Log(s);
            }
        for (int i = 0; i < HumanTrait.MuscleCount; i++)
            if (HumanTrait.MuscleName[i].Contains("Leg Twist") || HumanTrait.MuscleName[i].Contains("Foot Twist"))
                Debug.Log($"[yuanjing] 范围 {HumanTrait.MuscleName[i]} {HumanTrait.GetMuscleDefaultMin(i)}..{HumanTrait.GetMuscleDefaultMax(i)}");
    }
    /// 转身起步在人物身上逐帧推进（根的转动按片段的 deltaRotation 转人），看踩着的右脚在世界里转了多少
    public static void TurnFeet()
    {
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Characters/Built/Folk_anime_shino.prefab");
        var go = (GameObject)Object.Instantiate(prefab);
        var folk = go.GetComponent<Yuanjing.Folk>();
        var anim = go.GetComponentInChildren<Animator>();
        var clip = folk.turnClip;
        Object.DestroyImmediate(folk);
        foreach (var sb in go.GetComponentsInChildren<Yuanjing.SpringBones>()) Object.DestroyImmediate(sb);
        go.transform.position = Vector3.zero;
        foreach (bool ik in new[] { true, false })
        {
            var graph = PlayableGraph.Create("tf");
            var output = AnimationPlayableOutput.Create(graph, "a", anim);
            var cp = AnimationClipPlayable.Create(graph, clip);
            cp.SetApplyFootIK(ik);
            output.SetSourcePlayable(cp);
            anim.applyRootMotion = true;
            go.transform.rotation = Quaternion.identity;
            cp.SetTime(0); graph.Evaluate(0);
            string s = $"[yuanjing] 转身脚 {clip.name} footIK={ik}：";
            var rf = anim.GetBoneTransform(HumanBodyBones.RightFoot); var rt = anim.GetBoneTransform(HumanBodyBones.RightToes);
            var lf = anim.GetBoneTransform(HumanBodyBones.LeftFoot); var lt = anim.GetBoneTransform(HumanBodyBones.LeftToes);
            float yaw = 0;
            for (int f = 0; f <= 80; f++)
            {
                if (f > 0) { graph.Evaluate(1f / 60f); yaw += Mathf.DeltaAngle(0, anim.deltaRotation.eulerAngles.y); go.transform.rotation = Quaternion.Euler(0, yaw, 0); graph.Evaluate(0); }
                if (f % 6 == 0)
                {
                    Vector3 r = rt.position - rf.position, l = lt.position - lf.position;
                    s += $"\n   {f / 60f:F2} 身 {yaw:F0} 右脚 {Mathf.Atan2(r.x, r.z) * Mathf.Rad2Deg:F0} 左脚 {Mathf.Atan2(l.x, l.z) * Mathf.Rad2Deg:F0}";
                }
            }
            Debug.Log(s);
            graph.Destroy();
        }
        Object.DestroyImmediate(go);
    }
    /// 停步接进来的那一刻：步态在相位 ph 和停步片段在 t(ph) 的姿势差多少（两脚、脚趾相对根，厘米）
    public static void StopMatch()
    {
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Characters/Built/Folk_anime_shino.prefab");
        var go = (GameObject)Object.Instantiate(prefab);
        var folk = go.GetComponent<Yuanjing.Folk>();
        var anim = go.GetComponentInChildren<Animator>();
        var stop = folk.stopClip; float entry = folk.stopEntry;
        var gaits = folk.gaitClips;
        Object.DestroyImmediate(folk);
        foreach (var sb in go.GetComponentsInChildren<Yuanjing.SpringBones>()) Object.DestroyImmediate(sb);
        go.transform.position = Vector3.zero;
        var bones = new[] { HumanBodyBones.LeftFoot, HumanBodyBones.RightFoot, HumanBodyBones.LeftToes, HumanBodyBones.RightToes, HumanBodyBones.Hips };
        Vector3[] Pose(AnimationClip c, float t)
        {
            var g = PlayableGraph.Create("sm");
            var o = AnimationPlayableOutput.Create(g, "a", anim);
            var cp = AnimationClipPlayable.Create(g, c);
            cp.SetApplyFootIK(true);
            o.SetSourcePlayable(cp);
            cp.SetTime(t); g.Evaluate(0);
            var r = bones.Select(b => go.transform.InverseTransformPoint(anim.GetBoneTransform(b).position)).ToArray();
            g.Destroy();
            return r;
        }
        foreach (var gc in new[] { gaits[gaits.Length - 1], gaits[1] })
        {
            string s = $"[yuanjing] 停步接入 {gc.name} → {stop.name}（entry {entry:F2}）：";
            for (float ph = 0; ph <= 0.5f; ph += 0.05f)
            {
                var a = Pose(gc, ph * gc.length); var b = Pose(stop, ph / 0.5f * entry);
                s += $"\n   相位 {ph:F2}:";
                for (int i = 0; i < bones.Length; i++) { var d = (b[i] - a[i]) * 100; s += $" {bones[i]} ({d.x:F1},{d.y:F1},{d.z:F1})"; }
            }
            Debug.Log(s);
        }
        Object.DestroyImmediate(go);
    }
}
