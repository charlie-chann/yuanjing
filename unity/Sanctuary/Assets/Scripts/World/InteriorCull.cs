using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace Yuanjing
{
    /// 殿里的东西只在看得见的时候画：三尊像、背光、供桌上的一切、宫灯和幡加起来一百多万个三角形，
    /// 镜头在殿外的时候（俯视、在院子里）它们几乎全被屋顶和墙挡着，却照样要算一遍（还要算影子、深度）。
    /// 按镜头的位置分三档（只看位置，不看朝向；朝向不对的东西引擎自己会剔掉）：
    /// - 镜头在殿里：全画；
    /// - 镜头在殿门南边、比门洞的上沿（doorTop）低：能平着看进门洞（刚进门时平视镜头还在廊下、在廊下用第一人称往里看），全画；
    /// - 镜头在殿门南边、比门洞高：从门槛看过去镜头抬得越高，透过门洞看进去越浅（屋檐挡着）。
    ///   坡度（高 / 水平距离）小于 deepSlope：能看到供桌、佛坛，全画；小于 nearSlope：只看得到门里几米的地面，
    ///   只画 near（殿里的墙地天花、门边的蒲团、拜垫、功德箱）；再高（俯视）门洞整个被屋檐挡住，殿里的都不画；
    /// - 镜头在殿的北、东、西三面（墙外）：都不画。
    /// 殿里的灯跟着 deep 一起开关。编辑器里出图时不动（全画），出图的工具自己调 Apply。
    ///
    /// 门洞：殿只有正面中间三间开着的格扇门看得穿（两边的槛窗、门上的横披窗都糊着窗纸，墙、屋顶都是实的）。
    /// 所以镜头在殿外的时候，「全画」「只画 near」这两档里还要再挑一遍：从镜头经过门洞（门槛到门上沿、两边门框之间那一个长方形，
    /// 四边各放宽 portalPad）能看到的才画——每件东西的包围盒和「镜头 + 门洞」围成的四棱锥（门洞以里的那一截）相交才画。
    /// 反过来，镜头在殿里的时候，殿外的东西也只画从门洞看得出去的（四棱锥门洞以外的那一截）：
    /// - 不动的（院子、石台、树、草、石灯笼、院子里的蒲团……：outside，BuildIslet 收集）：看不到、本来投影子的改成只投影子
    ///   （它的影子可能落在门外看得见的那块地上），不投影子的不画；
    /// - 走动的香客（不含自己）、小动物：每帧按各自站的地方看，看不到的同样只投影子；殿里的香客照常画。
    /// 门洞的四棱锥只跟镜头的位置有关，镜头挪动超过 2 厘米才重算不动的那些。镜头正好在门槛那一条上（离门线 portalSkip 以内）四棱锥算不准，不挑。
    /// 在所有镜头脚本之后跑（镜头这一帧已经摆好了），不会晚一帧。
    [DefaultExecutionOrder(10000)]
    public class InteriorCull : MonoBehaviour
    {
        public Renderer[] near = new Renderer[0], deep = new Renderer[0];
        public Light[] lights = new Light[0];
        public Renderer[] outside = new Renderer[0];
        public Rect hall;                  // 殿里（墙的中线以内）
        public float insideTop = 7.5f;     // 比这高就不算在殿里（俯视镜头在殿的正上方）
        public float doorZ = 14.3f, sillY = 0.77f, doorTop = 3.62f;
        public float doorHalf = 3.75f;     // 三间格扇门的总宽一半（两边门框的外沿；中间两根门框也当作开着，宁可多画）
        public float portalPad = 0.12f;    // 门洞四边各放宽一点（宁可多画几件）
        public float portalSkip = 0.3f;
        public float deepSlope = 0.6f, nearSlope = 1.25f;
        /// 镜头在殿里时，殿外看不到的东西离门多近还要投影子（米）：门外看得见的那块地上的影子是近处的东西投的
        public float shadowReach = 14f;
        Vector3 doorCenter => new Vector3(0f, sillY, doorZ);
        int state = -1;
        bool portalIn, portalOut;          // 现在殿里的东西按门洞挑过；殿外的东西按门洞挑过
        Vector3 lastCam = new Vector3(1e9f, 0, 0);
        ShadowCastingMode[] outsideCast;
        byte[] outsideNow;                 // 0 照常 1 只投影子 2 不画
        readonly Plane[] planes = new Plane[5];
        readonly Dictionary<Component, (Renderer[] rs, ShadowCastingMode[] cast)> hidden = new Dictionary<Component, (Renderer[], ShadowCastingMode[])>();
        readonly List<Component> actors = new List<Component>();
        /// 看不到、又离门远（连影子也不画）的那几个
        readonly HashSet<Component> hiddenFar = new HashSet<Component>();

        /// 现在是哪一档：0 都不画，1 只画 near，2 全画
        public int State => state;

        /// 按门洞挑掉了几件：殿里的、殿外不动的、走动的（测试、量开销用）
        public int CulledInside { get; private set; }
        public int CulledOutside { get; private set; }
        public int CulledActors => hidden.Count;

        void LateUpdate()
        {
            var cam = Camera.main;
            if (cam != null) Apply(cam.transform.position);
        }

        /// 场景里那一个（FlowerField 这种自己画、不是渲染器的要问它）
        public static InteriorCull Active;
        void OnEnable() => Active = this;

        void OnDisable()
        {
            if (Active == this) Active = null;
            Set(2);
        }

        /// 殿外的一块（包围盒 b）此刻要不要画：镜头在殿外照常画；镜头在殿里时只画从门洞看得出去的
        public bool OutsideVisible(Bounds b) => !portalOut || GeometryUtility.TestPlanesAABB(planes, b);

        /// 镜头在殿里（不在门槛那一条上）：殿外的人头上的名字不显示（名字的字画在最上面、不被墙挡，
        /// 殿外的人透过墙把名字浮在殿里的墙上、佛像上，Folk 看这个收起来）
        public bool CameraInside => portalOut;
        /// 这一点在殿里（墙的中线以内）
        public bool InHall(Vector3 p) => hall.Contains(new Vector2(p.x, p.z));

        public static int StateFor(Vector3 c, Rect hall, float insideTop, float doorZ, float sillY, float doorTop, float deepSlope, float nearSlope)
        {
            if (hall.Contains(new Vector2(c.x, c.z)) && c.y < insideTop) return 2;
            if (c.z >= doorZ) return 0;
            // 比门洞上沿低：平着就看得进去（离门只有一两米、按门槛算的坡度很陡的时候也一样，例如人刚进门、平视镜头还在廊下）
            if (c.y < doorTop) return 2;
            float s = (c.y - sillY) / Mathf.Max(doorZ - c.z, 0.01f);
            return s < deepSlope ? 2 : s < nearSlope ? 1 : 0;
        }

        public void Apply(Vector3 c)
        {
            int s = StateFor(c, hall, insideTop, doorZ, sillY, doorTop, deepSlope, nearSlope);
            bool inside = hall.Contains(new Vector2(c.x, c.z)) && c.y < insideTop;
            bool atDoor = Mathf.Abs(c.z - doorZ) < portalSkip;
            bool wantIn = s >= 1 && !inside && !atDoor && c.z < doorZ;
            bool wantOut = inside && !atDoor && c.z > doorZ;
            bool moved = (c - lastCam).sqrMagnitude > 0.0004f;
            bool changed = s != state || wantIn != portalIn || wantOut != portalOut;
            if ((wantIn || wantOut) && (moved || changed)) Portal(c, wantOut);
            if (wantOut) CullActors(); else ShowActors();
            if (!changed && !(moved && (wantIn || wantOut))) return;
            lastCam = c;
            state = s;
            portalIn = wantIn;
            portalOut = wantOut;
            int culled = 0;
            foreach (var r in near) if (r != null) culled += Show(r, s >= 1, wantIn);
            foreach (var r in deep) if (r != null) culled += Show(r, s >= 2, wantIn);
            CulledInside = culled;
            foreach (var l in lights) if (l != null) l.enabled = s >= 2;
            if (wantOut) CullOutside(); else ShowAll();
        }

        /// 直接定一档（不按门洞挑，殿外的都照常画）。出图的工具、关掉这个组件时用
        public void Set(int s)
        {
            ShowAll();
            ShowActors();
            portalOut = false;
            lastCam = new Vector3(1e9f, 0, 0);
            if (s == state && !portalIn) return;
            state = s;
            portalIn = false;
            foreach (var r in near) if (r != null) r.enabled = s >= 1;
            foreach (var r in deep) if (r != null) r.enabled = s >= 2;
            foreach (var l in lights) if (l != null) l.enabled = s >= 2;
            CulledInside = 0;
        }

        /// 这一档该画的，按门洞再挑一遍；返回 1 表示被门洞挑掉了
        int Show(Renderer r, bool on, bool test)
        {
            bool vis = on && (!test || GeometryUtility.TestPlanesAABB(planes, r.bounds));
            if (r.enabled != vis) r.enabled = vis;
            return on && !vis ? 1 : 0;
        }

        /// 镜头经过门洞看出去（或看进来）的四棱锥：四个侧面各过镜头和门洞的一条边，第五个面是门洞所在的那个面（只要门洞另一边的）
        void Portal(Vector3 c, bool lookingOut)
        {
            float h = doorHalf + portalPad, y0 = sillY - portalPad, y1 = doorTop + portalPad;
            var a = new Vector3(-h, y0, doorZ);
            var b = new Vector3(h, y0, doorZ);
            var d = new Vector3(h, y1, doorZ);
            var e = new Vector3(-h, y1, doorZ);
            // 四棱锥里面的一点：从镜头穿过门洞中心再往前
            Vector3 mid = (a + d) * 0.5f, inner = c + (mid - c) * 2f;
            planes[0] = Facing(new Plane(c, a, e), inner);
            planes[1] = Facing(new Plane(c, b, d), inner);
            planes[2] = Facing(new Plane(c, a, b), inner);
            planes[3] = Facing(new Plane(c, e, d), inner);
            planes[4] = new Plane(lookingOut ? Vector3.back : Vector3.forward, mid);
        }

        static Plane Facing(Plane p, Vector3 inner) => p.GetSide(inner) ? p : p.flipped;

        void CullOutside()
        {
            if (outsideCast == null || outsideCast.Length != outside.Length)
            {
                outsideCast = new ShadowCastingMode[outside.Length];
                outsideNow = new byte[outside.Length];
                for (int i = 0; i < outside.Length; i++) if (outside[i] != null) outsideCast[i] = outside[i].shadowCastingMode;
            }
            int culled = 0;
            for (int i = 0; i < outside.Length; i++)
            {
                var r = outside[i];
                if (r == null) continue;
                // 看不到的：离殿门近的（shadowReach 以内）只投影子——它的影子可能落在门外看得见的那块地上；再远的影子落不到门洞里看得见的地方，干脆不画
                var b = r.bounds;
                bool near = (b.ClosestPoint(doorCenter) - doorCenter).sqrMagnitude < shadowReach * shadowReach;
                byte want = GeometryUtility.TestPlanesAABB(planes, b) ? (byte)0 : outsideCast[i] != ShadowCastingMode.Off && near ? (byte)1 : (byte)2;
                if (want != 0) culled++;
                if (want == outsideNow[i]) continue;
                outsideNow[i] = want;
                r.enabled = want != 2;
                r.shadowCastingMode = want == 1 ? ShadowCastingMode.ShadowsOnly : outsideCast[i];
            }
            CulledOutside = culled;
        }

        void ShowAll()
        {
            if (outsideNow == null) return;
            for (int i = 0; i < outside.Length && i < outsideNow.Length; i++)
            {
                if (outsideNow[i] == 0) continue;
                outsideNow[i] = 0;
                var r = outside[i];
                if (r == null) continue;
                r.enabled = true;
                r.shadowCastingMode = outsideCast[i];
            }
            CulledOutside = 0;
        }

        /// 走动的香客（不含自己）、小动物：在殿里的照常画，殿外的按门洞挑
        void CullActors()
        {
            actors.Clear();
            var me = GameDirector.Instance != null ? GameDirector.Instance.player : null;
            foreach (var f in Folk.All) if (f != null && f != me) actors.Add(f);
            foreach (var p in Critter.All) if (p != null) actors.Add(p);
            foreach (var a in actors)
            {
                Vector3 p = a.transform.position;
                bool inHall = hall.Contains(new Vector2(p.x, p.z));
                bool vis = inHall || GeometryUtility.TestPlanesAABB(planes, new Bounds(p + Vector3.up * 0.9f, new Vector3(1.6f, 2.2f, 1.6f)));
                // 看不到的人：离殿门近的只投影子（影子可能落在门外看得见的那块地上）；离门 shadowReach 以外的影子落不到门洞里，连影子也不画（同不动的那些）
                bool nearDoor = (p - doorCenter).sqrMagnitude < shadowReach * shadowReach;
                bool off = hidden.ContainsKey(a);
                if (off && (vis || (nearDoor && hiddenFar.Contains(a)))) Restore(a);
                else if (!vis && !off)
                {
                    var rs = a.GetComponentsInChildren<Renderer>();
                    var cast = new ShadowCastingMode[rs.Length];
                    if (!nearDoor) hiddenFar.Add(a);
                    for (int i = 0; i < rs.Length; i++)
                    {
                        cast[i] = rs[i].shadowCastingMode;
                        if (cast[i] == ShadowCastingMode.Off || !nearDoor) rs[i].forceRenderingOff = true;
                        else rs[i].shadowCastingMode = ShadowCastingMode.ShadowsOnly;
                    }
                    hidden[a] = (rs, cast);
                }
            }
            // 走掉了的（离开小岛、被删掉了）
            if (hidden.Count > actors.Count)
            {
                var gone = new List<Component>();
                foreach (var k in hidden.Keys) if (k == null || !actors.Contains(k)) gone.Add(k);
                foreach (var k in gone) Restore(k);
            }
        }

        void Restore(Component a)
        {
            if (!hidden.TryGetValue(a, out var h)) return;
            hidden.Remove(a);
            hiddenFar.Remove(a);
            for (int i = 0; i < h.rs.Length; i++)
            {
                if (h.rs[i] == null) continue;
                h.rs[i].forceRenderingOff = false;
                h.rs[i].shadowCastingMode = h.cast[i];
            }
        }

        void ShowActors()
        {
            if (hidden.Count == 0) return;
            foreach (var k in new List<Component>(hidden.Keys)) Restore(k);
        }
    }
}
