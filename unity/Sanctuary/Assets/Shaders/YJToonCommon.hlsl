// 卡通画风（湖心小寺）几遍绘制共用的部分：材质参数、随风摆动、视线镂空。
// 颜色来自顶点色（模型在 Blender 里上的色），第四个数是摆动幅度；uv.x 是每一团的相位，uv.y 是自发光。
// 画颜色、算阴影、算深度这几遍必须用同一个摆动公式，不然叶子和影子对不上。
#ifndef YJ_TOON_COMMON_INCLUDED
#define YJ_TOON_COMMON_INCLUDED

CBUFFER_START(UnityPerMaterial)
half4 _BaseColor;
half4 _ShadeColor;
half4 _EmissionColor;
half4 _RimColor;
half _ShadeStep;
half _ShadeSoft;
half _Sway;
half _WetAmount;
half _SnowAmount;
half _Ambient;
half _SunScale;
half _Cull;
half _Legacy;
float4 _BaseMap_ST;
CBUFFER_END

#ifndef YJ_WEATHER_INCLUDED
float _YJWind;
#endif

// 普通模型（小人、布条、香这些不是 Blender 脚本做的）：颜色不在顶点色里，摆动幅度在红色通道
float3 YJToonSway(float3 positionOS, half4 color, half phase)
{
    half a = lerp(color.a, color.r, _Legacy) * _Sway;
    phase *= 1.0 - _Legacy;
    float3 w = TransformObjectToWorld(positionOS);
    float t = _Time.y;
    float p = phase * 6.2831;
    // 一阵一阵的风：整片一起缓缓起伏，每一团再有自己的小晃动
    float gust = 0.55 + 0.45 * sin(t * 0.6 + w.x * 0.13 + w.z * 0.09);
    float3 off = float3(sin(t * 1.5 + p + w.x * 0.7) + 0.5, 0.3 * sin(t * 2.2 + p * 1.7 + w.z), cos(t * 1.2 + p * 0.6 + w.z * 0.8));
    w += off * ((0.03 + 0.11 * _YJWind) * gust * a);
    return TransformWorldToObject(w);
}

// 俯视镜头下，人走到屋檐、树冠后面会被挡住：把「镜头到人」这条视线附近、比人头还高的东西用网点镂空。
// _YJSee：xyz 是人脚下的位置，w 是镂空的半径（米）；0 表示不镂空（第三人称的两座殿不用）
float4 _YJSee;

void YJSeeThrough(float3 positionWS, float4 positionCS)
{
    if (_YJSee.w <= 0.0) return;
    float3 a = _WorldSpaceCameraPos;
    float3 b = _YJSee.xyz + float3(0, 0.7, 0);
    float3 ab = b - a;
    float t = saturate(dot(positionWS - a, ab) / dot(ab, ab));
    float dist = length(positionWS - (a + ab * t));
    float cut = (1.0 - smoothstep(_YJSee.w * 0.55, _YJSee.w, dist)) * smoothstep(1.45, 1.95, positionWS.y - _YJSee.y) * step(t, 0.985);
    if (cut <= 0.0) return;
    // 4×4 的固定网点：镜头不动时图案不变，不会闪
    static const float bayer[16] = { 0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0 };
    uint2 px = uint2(positionCS.xy) & 3u;
    float thr = (bayer[px.x + px.y * 4u] + 0.5) / 16.0;
    clip(1.0 - cut * 0.94 - thr);
}

#endif
