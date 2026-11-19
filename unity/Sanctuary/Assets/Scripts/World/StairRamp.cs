using UnityEngine;

namespace Yuanjing
{
    /// 台阶：走路时人的原点贴着一条斜坡上下（按路线走的直接走斜坡，摇杆推着的胶囊照旧一级一级上，画出来的身子按斜坡走），
    /// 不再一级一级地跳（以前上下大殿的台阶，整个人一帧里蹿上、掉下 17.5 厘米，脚插进台阶里 10–15 厘米）。
    /// 斜坡穿过每一级踏面的正中间，脚和踏面差的那一点（最多半级）由 Folk.GroundIK 补：踩着的脚落在踏面上，迈着的脚抬过台阶沿。
    /// area：台阶那一块（水平，x、z）；高度沿 z 从 (z0, y0) 线性到 (z1, y1)，z0 以前是 y0、z1 以后是 y1（两头和地面、台基一样高，接得上）
    public class StairRamp : MonoBehaviour
    {
        public Rect area;
        public float z0, y0, z1, y1;

        void OnEnable() { if (!Folk.Ramps.Contains(this)) Folk.Ramps.Add(this); }
        void OnDisable() => Folk.Ramps.Remove(this);

        public bool Contains(Vector3 p) => area.Contains(new Vector2(p.x, p.z));
        public float HeightAt(Vector3 p) => Mathf.Lerp(y0, y1, Mathf.InverseLerp(z0, z1, p.z));
    }
}
