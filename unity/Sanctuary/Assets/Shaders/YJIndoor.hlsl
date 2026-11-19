// 殿里的环境光：环境光（天光）本来不管屋顶，殿里看着就像室外的背阴处——偏蓝、发灰。
// 在大殿的墙里面（一个盒子）把环境光换成同样亮度、暖一点的颜色，再按 _YJIndoorTint.a 调亮暗；
// 夜里天光暗下去以后，殿里至少还有 _YJIndoorGlow 那么亮（灯火映出来的底光）。
// 盒子由运行时的 IndoorZone 组件设置；_YJIndoorMin.w = 0 时不起作用（别的场景、别的地方都不受影响）。
#ifndef YJ_INDOOR_INCLUDED
#define YJ_INDOOR_INCLUDED

float4 _YJIndoorMin;    // xyz 盒子的一角，w 强度（0 = 没有）
float4 _YJIndoorMax;    // xyz 另一角
float4 _YJIndoorFade;   // 盒子边上过渡多宽（米）：x 门那一面（-z），y 顶上（+y），z 其他几面（墙，硬一点：墙里墙外分得清）
half4 _YJIndoorTint;    // rgb 殿里环境光的颜色（乘在原来的亮度上），a 亮度倍数
half4 _YJIndoorGlow;    // rgb 殿里的底光

half YJIndoor(float3 p)
{
    if (_YJIndoorMin.w <= 0.0) return 0.0;
    float3 a = (p - _YJIndoorMin.xyz) / float3(_YJIndoorFade.z, _YJIndoorFade.z, _YJIndoorFade.x);
    float3 b = (_YJIndoorMax.xyz - p) / float3(_YJIndoorFade.z, _YJIndoorFade.y, _YJIndoorFade.z);
    float3 k = saturate(min(a, b));
    return k.x * k.y * k.z * _YJIndoorMin.w;
}

half3 YJIndoorAmbient(half3 ambient, float3 p)
{
    half k = YJIndoor(p);
    if (k <= 0.0) return ambient;
    half lum = dot(ambient, half3(0.3, 0.59, 0.11));
    half3 inside = max(lum * _YJIndoorTint.rgb * _YJIndoorTint.a, _YJIndoorGlow.rgb);
    return lerp(ambient, inside, k);
}

#endif
