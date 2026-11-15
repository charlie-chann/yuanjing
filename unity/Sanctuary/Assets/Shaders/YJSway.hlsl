// 随风摆动：顶点色的红色通道是幅度（树叶、布条的自由端是 1，系着的那头是 0）。
// 画颜色、算阴影、算深度这几遍必须用同一个公式，不然叶子和它自己的影子对不上，影子会抖、会忽有忽无。
#ifndef YJ_SWAY_INCLUDED
#define YJ_SWAY_INCLUDED
#ifndef YJ_WEATHER_INCLUDED
float _YJWind;          // 天气那边已经声明过的话就不再声明
#endif
float3 YJSwayOS(float3 positionOS, half amount)
{
    float3 w = TransformObjectToWorld(positionOS);
    float t = _Time.y;
    float3 off = float3(sin(t * 1.9 + w.x * 1.3 + w.z * 0.7), 0.25 * sin(t * 2.7 + w.x), cos(t * 1.5 + w.z * 1.1 + w.y));
    return positionOS + TransformWorldToObjectDir(off, false) * (0.03 + 0.12 * _YJWind) * amount * _Sway;
}
#endif
