#ifndef YJ_WEATHER_INCLUDED
#define YJ_WEATHER_INCLUDED

// 天气对表面的影响：淋湿、积水和雨点涟漪、积雪。全局参数由 TimeWeather.cs 设置。
// 屋檐下不该湿也不该积雪：用一张从正上方看下去的高度图判断某一点头顶有没有遮挡。

TEXTURE2D(_YJHeightMap);
SAMPLER(sampler_YJHeightMap);
float4 _YJHeightParams; // xy：高度图覆盖范围的最小角（世界坐标 xz），zw：1 / 范围
float _YJWet;           // 0..1 表面有多湿
float _YJSnow;          // 0..1 积雪有多厚
float _YJRain;          // 0..1 正在下的雨有多大（决定涟漪）
float _YJWind;          // 0..1 风有多大（决定树叶和布条摆得多厉害）

float yjHash(float2 p)
{
    p = frac(p * float2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return frac(p.x * p.y);
}

float yjNoise(float2 p)
{
    float2 i = floor(p), f = frac(p);
    f = f * f * (3.0 - 2.0 * f);
    return lerp(lerp(yjHash(i), yjHash(i + float2(1, 0)), f.x), lerp(yjHash(i + float2(0, 1)), yjHash(i + float2(1, 1)), f.x), f.y);
}

float yjFbm(float2 p)
{
    return yjNoise(p) * 0.5 + yjNoise(p * 2.03 + 17.1) * 0.3 + yjNoise(p * 4.1 + 5.3) * 0.2;
}

// 这一点头顶是不是露天：1 露天，0 有遮挡
float YJOpenSky(float3 posWS, float3 nWS)
{
    float2 q = posWS.xz + nWS.xz * 0.45; // 墙面往外挪一点再查，屋檐下的墙是干的
    float2 uv = (q - _YJHeightParams.xy) * _YJHeightParams.zw;
    float h = SAMPLE_TEXTURE2D_LOD(_YJHeightMap, sampler_YJHeightMap, uv, 0).r;
    float inside = step(0.0, uv.x) * step(uv.x, 1.0) * step(0.0, uv.y) * step(uv.y, 1.0);
    return lerp(1.0, smoothstep(-0.55, -0.12, posWS.y - h), inside);
}

// 雨点落在水面上的一圈圈涟漪，返回法线在 xz 上的偏移
float2 YJRipples(float2 p, float t)
{
    float2 n = 0;
    for (int k = 0; k < 3; k++)
    {
        float2 g = p * (1.7 + 1.1 * k) + k * 17.3;
        float2 id = floor(g);
        float2 f = frac(g) - 0.5;
        float h = yjHash(id + k * 3.7);
        float tt = frac(t * (0.75 + 0.5 * h) + h * 7.0);
        float2 c = (float2(yjHash(id + 3.1), yjHash(id + 7.7)) - 0.5) * 0.55;
        float2 d = f - c;
        float r = length(d);
        float ring = r - tt * 0.42;
        float w = sin(ring * 46.0) * smoothstep(0.07, 0.0, abs(ring)) * (1.0 - tt) * (1.0 - tt);
        n += d / max(r, 1e-4) * w;
    }
    return n;
}

void YJApplyWeather(float3 posWS, float3 geomN, half wetAmount, half snowAmount, half puddleAmount, inout SurfaceData s, inout InputData d)
{
    if (_YJWet + _YJSnow < 0.001)
        return;
    geomN = normalize(geomN);
    float up = saturate(geomN.y);
    float open = YJOpenSky(posWS, geomN);

    // 淋湿：颜色变深、表面变亮；朝上的面更湿
    float wet = _YJWet * wetAmount * open * lerp(0.4, 1.0, up);
    s.albedo *= lerp(1.0, 0.56, wet * (1.0 - s.metallic));
    s.smoothness = lerp(s.smoothness, max(s.smoothness, 0.80), wet * 0.9);

    // 积水：平地上低洼的地方，雨越久水洼越大；正在下雨时有涟漪
    float flatness = smoothstep(0.93, 0.99, geomN.y);
    float puddle = smoothstep(0.64 - _YJWet * 0.22, 0.69 - _YJWet * 0.22, yjFbm(posWS.xz * 0.27)) * wet * puddleAmount * flatness;
    if (puddle > 0.001)
    {
        float2 rip = YJRipples(posWS.xz, _Time.y) * _YJRain * 0.55;
        float3 n = normalize(float3(rip.x, 1.0, rip.y));
        d.normalWS = normalize(lerp(d.normalWS, n, puddle));
        s.albedo *= lerp(1.0, 0.62, puddle);
        s.smoothness = lerp(s.smoothness, 0.97, puddle);
        s.occlusion = lerp(s.occlusion, 1.0, puddle);
    }

    // 积雪：只落在朝上、露天的面上，边缘不整齐
    float lie = saturate((up - 0.35) * 2.2) * open * snowAmount;
    float cover = _YJSnow * 1.35;
    float grain = 0.55 + 0.45 * yjNoise(posWS.xz * 3.1) + 0.35 * (yjNoise(posWS.xz * 0.45) - 0.5);
    // 竖直的面和有遮挡的地方（lie 为 0）不积雪
    float snow = smoothstep(1.0 - cover, 1.0 - cover + 0.3, lie * grain) * smoothstep(0.0, 0.10, lie);
    if (snow > 0.001)
    {
        float sparkle = yjNoise(posWS.xz * 61.0);
        s.albedo = lerp(s.albedo, half3(0.84, 0.88, 0.94) * (0.94 + 0.06 * sparkle), snow);
        s.smoothness = lerp(s.smoothness, 0.22 + 0.25 * step(0.93, sparkle), snow);
        s.metallic = lerp(s.metallic, 0.0, snow);
        s.occlusion = lerp(s.occlusion, 1.0, snow * 0.7);
        float2 bump = float2(yjNoise(posWS.xz * 5.0) - 0.5, yjNoise(posWS.xz * 5.0 + 9.0) - 0.5) * 0.35;
        d.normalWS = normalize(lerp(d.normalWS, normalize(geomN + float3(bump.x, 0.0, bump.y)), snow * 0.85));
    }
}

#endif
