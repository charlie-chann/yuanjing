// 卡通画风（湖心小寺）几遍绘制共用的部分：材质参数、随风摆动、视线镂空。
// 颜色来自顶点色（模型在 Blender 里上的色），第四个数是摆动幅度；uv.x 是每一团的相位，uv.y 是自发光。
// 画颜色、算阴影、算深度这几遍必须用同一个摆动公式，不然叶子和影子对不上。
#ifndef YJ_TOON_COMMON_INCLUDED
#define YJ_TOON_COMMON_INCLUDED

// 叶子、草这些有自己一套材质参数的着色器先定义 YJ_OWN_MATERIAL，这里就只给视线镂空
#ifndef YJ_OWN_MATERIAL
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
half _Detail;
half _DetailScale;
float4 _BaseMap_ST;
half4 _TexMean;
half _TexTile;
half _TexFine;
half _TexFineAmount;
half _TexNormal;
half _TexSpec;
half _Paint;
half _PaintGlow;
half _Gilt;
half4 _GiltDir;
half4 _GiltColor;
half _GiltEnv;
half4 _GiltDoor;
half _GiltFloor;
half _GiltDoorK;
half _GiltCeil;
half _GiltSpec;
half _GiltLamp;
half _GiltLeafAmt;
half _GiltLeafTilt;
half _GiltLeafScale;
half _GiltMask;
half _GlowTint;
half _Floor;
float4 _FloorRect;
float4 _FloorBoxMin;
float4 _FloorBoxMax;
float4 _FloorProbe;
half _FloorRefl;
half _FloorRough;
half _FloorNight;
half _FloorTile;
half _TexHash;
half _TexContrast;
CBUFFER_END

#ifndef YJ_WEATHER_INCLUDED
float _YJWind;
#endif

// 普通模型（小人、布条、香这些不是 Blender 脚本做的）：颜色不在顶点色里，摆动幅度在红色通道
float3 YJToonSway(float3 positionOS, half4 color, half phase)
{
    half a = lerp(color.a, color.r, _Legacy) * _Sway;
    // 手绘贴图的部件（_Paint）uv 是贴图坐标，不是每一团的相位：整块一起摆（幡）
    phase *= 1.0 - saturate(_Legacy + _Paint);
    float3 w = TransformObjectToWorld(positionOS);
    float t = _Time.y;
    float p = phase * 6.2831;
    // 一阵一阵的风：整片一起缓缓起伏，每一团再有自己的小晃动
    float gust = 0.55 + 0.45 * sin(t * 0.6 + w.x * 0.13 + w.z * 0.09);
    float3 off = float3(sin(t * 1.5 + p + w.x * 0.7) + 0.5, 0.3 * sin(t * 2.2 + p * 1.7 + w.z), cos(t * 1.2 + p * 0.6 + w.z * 0.8));
    w += off * ((0.03 + 0.11 * _YJWind) * gust * a);
    return TransformWorldToObject(w);
}

#endif // YJ_OWN_MATERIAL

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

// 平视时挡在镜头和自己之间的叶子（镜头退到树冠里、灌木后面）用网点淡掉，只留三成：
// _YJFocus 是自己那一团（xyz 中心，w 半径；0 是不管，ViewSwitcher 每帧给，同 YJAnime 的 YJOccluderFade）。
// 从镜头看过去罩住自己的那个圆锥里、又比自己近的才淡；圆锥外 0.2 米慢慢恢复
float4 _YJFocus;

void YJFocusFade(float3 positionWS, float4 positionCS)
{
    if (_YJFocus.w <= 0.0) return;
    float3 toP = _YJFocus.xyz - _WorldSpaceCameraPos;
    float dp = length(toP);
    float3 dir = toP / max(dp, 1e-3);
    float3 toX = positionWS - _WorldSpaceCameraPos;
    float along = dot(toX, dir);
    if (along > dp - _YJFocus.w - 0.15 || along <= 0.0) return;
    float perp = length(toX - dir * along);
    float k = saturate((perp - _YJFocus.w * along / dp) / 0.2);
    if (k >= 1.0) return;
    // 交错梯度噪声的网点（比 4×4 方格细），留四成
    float ign = frac(52.9829189 * frac(dot(floor(positionCS.xy), float2(0.06711056, 0.00583715))));
    clip(0.4 + 0.6 * k - ign);
}

#endif
