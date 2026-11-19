// 愿境仪式舞台：七个心愿分类各一场全屏着色器场景。
// 这份文件是唯一的着色器源码；tool/embed_shaders.sh 把它嵌进 Swift 字符串，运行时编译。
#include <metal_stdlib>
using namespace metal;

struct Uniforms {
  float2 res;    // 像素
  float time;    // 秒
  float prog;    // -1 待机；0..1 仪式进度
  float scene;   // 0 财富 1 事业 2 外貌 3 健康 4 情绪 5 生活 6 宠物；7 起是卡点释放：池、热气球、箭、魔药、深海
  float fade;    // 切场景时的整体亮度
  float dur;     // 当前仪式时长（秒）
  float glow;    // 许过愿之后的余韵 0..1
  float2 touch;
  float2 tap;    // 小游戏：最近一次点在哪（和 uv 同一套坐标）
  float4 game;   // 小游戏：x 开着没有（0/1） y 这一轮的进度 0..1 z 手速攒出来的能量 0..1 w 离上一次点过了几秒
  float4 game2;  // x 奖励动画的进度（-1 表示还没到） y 第几轮 z、w 备用
};

struct VOut { float4 pos [[position]]; };

vertex VOut stage_vertex(uint vid [[vertex_id]]) {
  float2 p = float2(float((vid << 1) & 2), float(vid & 2));
  VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}

// ───────── 通用 ─────────
static float sstep(float a, float b, float x) { return smoothstep(a, b, x); }
static float hash11(float p) { p = fract(p * 0.1031); p *= p + 33.33; p *= p + p; return fract(p); }
static float hash21(float2 p) { float3 p3 = fract(float3(p.x, p.y, p.x) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
static float2 hash22(float2 p) { float3 p3 = fract(float3(p.x, p.y, p.x) * float3(0.1031, 0.1030, 0.0973)); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.xx + p3.yz) * p3.zy); }
static float noise(float2 p) {
  float2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash21(i), hash21(i + float2(1, 0)), f.x), mix(hash21(i + float2(0, 1)), hash21(i + float2(1, 1)), f.x), f.y);
}
static float fbm(float2 p) { float a = 0.5, s = 0.0; for (int i = 0; i < 5; i++) { s += a * noise(p); p = p * 2.03 + float2(17.1, 9.2); a *= 0.5; } return s; }
static float2 rot2(float2 p, float a) { float c = cos(a), s = sin(a); return float2(c * p.x - s * p.y, s * p.x + c * p.y); }
static float3 aces(float3 x) { return saturate((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14)); }
static float3 pal(float t) { return 0.5 + 0.5 * cos(6.2832 * (t + float3(0.0, 0.33, 0.67))); }

// 四芒星闪光
static float star(float2 p, float s) {
  float d = length(p);
  float core = exp(-d * d / (s * s));
  float cr = exp(-abs(p.x) / (s * 0.14)) * exp(-abs(p.y) / (s * 2.6)) + exp(-abs(p.y) / (s * 0.14)) * exp(-abs(p.x) / (s * 2.6));
  return core + cr * 0.55;
}

// 失焦光斑：三层视差，带亮边
static float3 bokeh(float2 uv, float time, float density, float3 tint, float seed) {
  float3 acc = float3(0.0);
  for (int l = 0; l < 3; l++) {
    float fl = float(l); float sc = 2.6 + fl * 2.2;
    float2 p = uv * sc + float2(seed * 7.0 + fl * 13.0, -time * (0.035 + 0.02 * fl) + fl * 5.0);
    float2 id = floor(p), f = fract(p) - 0.5;
    for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
      float2 o = float2(float(i), float(j)); float2 cid = id + o; float2 h = hash22(cid + fl * 31.7);
      if (h.x > density) continue;
      float2 c = o + (h - 0.5) * 0.8; float r = 0.10 + 0.20 * hash21(cid + 3.3); float d = length(f - c);
      float disc = sstep(r, r * 0.86, d); float rim = sstep(r * 0.72, r * 0.95, d) * disc;
      float tw = 0.5 + 0.5 * sin(time * (0.5 + h.y * 1.6) + h.x * 40.0);
      acc += tint * (disc * 0.22 + rim * 0.3) * tw * (0.3 + 0.7 * h.y) / (1.0 + fl * 0.7);
    }
  }
  return acc;
}

// ═════════ 0 财富：金币落进金池（光线步进） ═════════
struct Coins { float3 pos[9]; float2 rx[9]; float2 ry[9]; float sc[9]; int n; };
struct Act { float3 pos[3]; float2 rx[3]; float2 ry[3]; float sc[3]; int n; };

static float3 toLocal(float3 p, float2 rx, float2 ry) {
  float x = ry.x * p.x - ry.y * p.z, z = ry.y * p.x + ry.x * p.z; p.x = x; p.z = z;
  float y = rx.x * p.y + rx.y * p.z; z = -rx.y * p.y + rx.x * p.z; p.y = y; p.z = z; return p;
}
static float3 toWorld(float3 p, float2 rx, float2 ry) {
  float y = rx.x * p.y - rx.y * p.z, z = rx.y * p.y + rx.x * p.z; p.y = y; p.z = z;
  float x = ry.x * p.x + ry.y * p.z; z = -ry.y * p.x + ry.x * p.z; p.x = x; p.z = z; return p;
}
// 方孔钱：半径 1，带圆角边
static float sdCoin(float3 p) {
  float r = length(p.xy);
  float2 q = float2(r - 1.0, abs(p.z) - 0.075) + 0.035;
  float d = min(max(q.x, q.y), 0.0) + length(max(q, float2(0.0))) - 0.035;
  float2 a = abs(p.xy) - 0.2;
  float hole = min(max(a.x, a.y), 0.0) + length(max(a, float2(0.0))) - 0.015;
  return max(d, -hole);
}
static float2 mapA(float3 p, Act a) {
  float2 r = float2(1e5, -1.0);
  for (int i = 0; i < a.n; i++) {
    float3 l = toLocal(p - a.pos[i], a.rx[i], a.ry[i]) / a.sc[i];
    float d = sdCoin(l) * a.sc[i];
    if (d < r.x) r = float2(d, float(i));
  }
  return r;
}
static float3 nrmA(float3 p, Act a) {
  float2 e = float2(0.0025, 0.0);
  return normalize(float3(mapA(p + e.xyy, a).x - mapA(p - e.xyy, a).x, mapA(p + e.yxy, a).x - mapA(p - e.yxy, a).x, mapA(p + e.yyx, a).x - mapA(p - e.yyx, a).x));
}
static Act gather(float3 ro, float3 rd, Coins cs) {
  Act a; a.n = 0;
  for (int i = 0; i < cs.n; i++) {
    float3 oc = ro - cs.pos[i]; float b = dot(oc, rd); float r = cs.sc[i] * 1.03; float c = dot(oc, oc) - r * r;
    if (b * b - c < 0.0 || (b > 0.0 && c > 0.0)) continue;
    if (a.n < 3) { a.pos[a.n] = cs.pos[i]; a.rx[a.n] = cs.rx[i]; a.ry[a.n] = cs.ry[i]; a.sc[a.n] = cs.sc[i]; a.n++; }
  }
  return a;
}
static float marchA(float3 ro, float3 rd, Act a, float tmax, int steps) {
  float t = 0.0;
  for (int i = 0; i < steps; i++) {
    float d = mapA(ro + rd * t, a).x;
    if (d < 0.0015) return t;
    t += d * 0.9;
    if (t > tmax) break;
  }
  return -1.0;
}
// 暗调摄影棚环境：几块柔光箱，金属就靠反射它们立起来
static float3 envGold(float3 d, float rough) {
  float3 c = mix(float3(0.012, 0.007, 0.003), float3(0.10, 0.058, 0.02), sstep(-0.2, 0.9, d.y));
  c += float3(1.6, 0.85, 0.25) * exp(-abs(d.y) * 7.0) * 0.5;
  float e = 0.025 + rough * 0.35;
  c += float3(4.6, 3.9, 2.8) * sstep(0.90 - e, 0.90 + e, dot(d, normalize(float3(0.45, 0.75, 0.5))));
  c += float3(3.2, 2.6, 2.0) * sstep(0.935 - e, 0.935 + e, dot(d, normalize(float3(-0.85, 0.25, 0.45))));
  // 背后贴着地平线的一条暖光带：金池远处的那道亮线、金币侧面的轮廓光都来自它
  c += float3(3.4, 1.8, 0.55) * sstep(0.05 - e * 0.3, 0.10, d.y) * sstep(0.30 + e * 0.5, 0.20, d.y) * sstep(0.2, -0.5, d.z) * exp(-d.x * d.x * 2.2);
  c += float3(1.1, 0.62, 0.2) * sstep(0.6, 0.98, dot(d, normalize(float3(0.0, -0.55, 0.83)))) * 0.6;
  return c;
}
static float3 shadeCoin(float3 p, float3 rd, Act a, texture2d<float> tex, sampler smp) {
  float2 m = mapA(p, a); int i = int(max(m.y, 0.0) + 0.5);
  float3 n = nrmA(p, a);
  float3 l = toLocal(p - a.pos[i], a.rx[i], a.ry[i]) / a.sc[i];
  float3 ln = toLocal(n, a.rx[i], a.ry[i]);
  float shade = 1.0;
  if (abs(ln.z) > 0.7) {
    float sg = ln.z > 0.0 ? 1.0 : -1.0;
    float2 tuv = float2(l.x * sg, l.y) * 0.5 + 0.5; tuv.y = 1.0 - tuv.y;
    float e = 1.5 / 512.0;
    float h = tex.sample(smp, tuv, level(0.0)).r;
    float hx = tex.sample(smp, tuv + float2(e, 0.0), level(0.0)).r - tex.sample(smp, tuv - float2(e, 0.0), level(0.0)).r;
    float hy = tex.sample(smp, tuv + float2(0.0, e), level(0.0)).r - tex.sample(smp, tuv - float2(0.0, e), level(0.0)).r;
    ln = normalize(float3(-hx * sg * 2.4, hy * 2.4, sg));
    n = toWorld(ln, a.rx[i], a.ry[i]);
    shade = 0.62 + 0.38 * h;
  }
  float3 R = reflect(rd, n); float ndv = max(dot(-rd, n), 0.0);
  float3 F0 = float3(1.0, 0.74, 0.30);
  float3 F = F0 + (float3(1.0) - F0) * pow(1.0 - ndv, 5.0);
  return envGold(R, 0.10) * F * shade;
}
static float ring(float2 q, float2 c, float age, float amp) {
  if (age <= 0.0 || age > 6.0) return 0.0;
  float d = length(q - c); float w = d - age * 1.9;
  return amp * sin(w * 7.0) * exp(-w * w * 1.3) * exp(-age * 0.55) / (1.0 + d * 0.25);
}
static float2 rainXZ(int i) { float2 h = hash22(float2(float(i) * 7.31, 2.7)); return float2((h.x - 0.5) * 2.6, -2.8 + h.y * 4.0); }
static float rainStart(int i) { return 2.4 + 0.52 * float(i) + 0.25 * hash11(float(i) * 3.7); }
static float heightA(float2 q, float t, float ts) {
  float h = 0.012 * sin(q.x * 1.3 + t * 0.6) + 0.010 * sin(q.y * 1.7 - t * 0.5 + q.x * 0.7) + 0.004 * sin((q.x + q.y) * 5.0 + t * 1.3);
  if (ts < 0.0) { h += ring(q, float2(0.0, 0.4), fmod(t, 6.5), 0.014); return h; }
  h += ring(q, float2(0.0), ts - 1.848, 0.10);
  h += ring(q, float2(0.0), ts - 7.62, 0.05);
  for (int i = 0; i < 8; i++) h += ring(q, rainXZ(i), ts - (rainStart(i) + 1.123), 0.05);
  return h;
}
static float3 sceneWealth(float2 uv, Uniforms u, texture2d<float> tex, sampler smp) {
  float t = u.time; float ts = u.prog < 0.0 ? -1.0 : u.prog * u.dur; bool run = ts >= 0.0;
  float surge = run ? sstep(3.0, 6.2, ts) * (1.0 - 0.45 * sstep(7.6, u.dur, ts)) : 0.55 * u.glow;
  float3 ro = float3(0.0, 1.0, 7.2);
  float3 fw = normalize(float3(0.0, 1.75, 0.0) - ro); float3 rt = normalize(cross(fw, float3(0.0, 1.0, 0.0))); float3 up = cross(rt, fw); float fl = 0.43;
  float3 rd = normalize(fw + uv.x * fl * rt + uv.y * fl * up);

  Coins cs; cs.n = 0;
  float hy = 2.45 + 0.07 * sin(t * 1.1), hspin = t * 0.6, hflip = 0.16 + 0.05 * sin(t * 0.7); bool hvis = true;
  if (run) {
    float w = sstep(0.0, 1.3, ts); hspin += 9.0 * w * w; hy += 0.25 * w;
    if (ts > 1.3 && ts < 2.2) { float q = ts - 1.3; hy = 2.85 - 9.5 * q * q; hflip += 9.0 * q; }
    else if (ts >= 2.2 && ts < 7.5) hvis = false;
    else if (ts >= 7.5) { float r = sstep(7.5, 8.7, ts); hy = mix(-1.3, 2.45, r) + 0.25 * sin(r * 3.14159); hspin += 6.0 * (1.0 - r) * (1.0 - r); }
  }
  float3 hpos = float3(0.0, hy, 0.0);
  if (hvis) { cs.pos[0] = hpos; cs.rx[0] = float2(cos(hflip), sin(hflip)); cs.ry[0] = float2(cos(hspin), sin(hspin)); cs.sc[0] = 0.86; cs.n = 1; }
  if (run) for (int i = 0; i < 8; i++) {
    float s = rainStart(i); float q = ts - s; if (q < 0.0 || q > 1.5) continue;
    float2 xz = rainXZ(i); float h1 = hash11(float(i) * 5.1 + 1.0), h2 = hash11(float(i) * 9.3 + 2.0);
    float ax = h1 * 6.0 + q * (4.0 + 3.0 * h2), ay = h2 * 6.0 + q * 3.0;
    int k = cs.n; cs.pos[k] = float3(xz.x, 5.8 - 4.6 * q * q, xz.y); cs.rx[k] = float2(cos(ax), sin(ax)); cs.ry[k] = float2(cos(ay), sin(ay)); cs.sc[k] = 0.42; cs.n = k + 1;
  }

  float tPlane = rd.y < 0.0 ? -ro.y / rd.y : 1e5;
  Act a = gather(ro, rd, cs);
  float tc = a.n > 0 ? marchA(ro, rd, a, min(tPlane, 30.0), 72) : -1.0;
  float3 col;
  if (tc > 0.0) {
    col = shadeCoin(ro + rd * tc, rd, a, tex, smp);
  } else if (tPlane < 1e4) {
    float3 p = ro + rd * tPlane; float2 q = p.xz; float e = 0.02 + tPlane * 0.004;
    float h0 = heightA(q, t, ts), hx = heightA(q + float2(e, 0.0), t, ts), hz = heightA(q + float2(0.0, e), t, ts);
    float3 n = normalize(float3(-(hx - h0) / e, 1.0, -(hz - h0) / e));
    float3 R = reflect(rd, n); R.y = abs(R.y);
    float3 rc = envGold(R, 0.05);
    float3 po = p + n * 0.01;
    Act b = gather(po, R, cs);
    if (b.n > 0) { float tr = marchA(po, R, b, 20.0, 40); if (tr > 0.0) rc = shadeCoin(po + R * tr, R, b, tex, smp); }
    float ndv = max(dot(-rd, n), 0.0); float3 F0 = float3(1.0, 0.66, 0.22);
    col = rc * (F0 + (float3(1.0) - F0) * pow(1.0 - ndv, 5.0)) * 0.55;
    col += float3(1.0, 0.5, 0.1) * surge * 0.22 * exp(-tPlane * 0.05);
    float fog = 1.0 - exp(-tPlane * 0.035);
    col = mix(col, float3(1.0, 0.5, 0.14) * (0.16 + 0.50 * surge), fog * fog);
  } else {
    col = mix(float3(0.055, 0.026, 0.007), float3(0.008, 0.005, 0.003), sstep(0.0, 0.5, rd.y));
    col += float3(1.0, 0.5, 0.14) * exp(-rd.y * 9.0) * (0.20 + 0.40 * surge) * exp(-rd.x * rd.x * 3.0);
  }
  // 屏幕空间的东西：金尘光斑、落水溅起的星芒、金币的光晕
  float hzn = -fw.y / (fl * up.y);
  col += bokeh(uv, t, 0.22 + 0.4 * surge, float3(1.0, 0.62, 0.2), 1.0) * (0.22 + 0.7 * surge) * sstep(hzn - 0.25, hzn + 0.3, uv.y + 0.2 * surge);
  col += float3(1.6, 0.85, 0.25) * surge * 0.16 * exp(-abs(uv.y - hzn) * 4.0);
  if (hvis) { float3 v = hpos - ro; float2 s = float2(dot(v, rt), dot(v, up)) / (dot(v, fw) * fl); float2 dd = uv - s; col += float3(1.0, 0.6, 0.2) * 0.10 * exp(-dot(dd, dd) * 5.0); }
  if (run) for (int i = 0; i < 9; i++) {
    float age = i == 0 ? ts - 1.848 : ts - (rainStart(i - 1) + 1.123);
    if (age <= 0.0 || age > 1.1) continue;
    float2 xz = i == 0 ? float2(0.0) : rainXZ(i - 1);
    float3 v = float3(xz.x, 0.0, xz.y) - ro; float zz = dot(v, fw); float2 s = float2(dot(v, rt), dot(v, up)) / (zz * fl);
    float sc = (i == 0 ? 2.4 : 1.3) / zz; float k = 1.0 - age / 1.1;
    for (int j = 0; j < 7; j++) {
      float2 h = hash22(float2(float(i) * 3.1, float(j) * 7.7));
      float ang = mix(0.45, 2.69, h.x); float spd = 0.6 + 1.2 * h.y;
      float2 pp = s + float2(cos(ang), sin(ang)) * spd * age * sc - float2(0.0, 1.6 * age * age * sc);
      col += float3(1.0, 0.78, 0.4) * star(uv - pp, 0.011 + 0.006 * h.y) * k * k * 1.6;
    }
  }
  return col;
}

// ═════════ 4 情绪：月下静湖 ═════════
static float3 skyMood(float3 rd, float clear, float t, float2 shoot) {
  float y = max(rd.y, 0.0);
  float3 c = mix(float3(0.035, 0.075, 0.15), float3(0.006, 0.010, 0.035), sstep(0.0, 0.55, y));
  c += float3(0.05, 0.12, 0.17) * exp(-y * 9.0) * (0.5 + 0.5 * clear);
  float2 q = rd.xy / max(-rd.z, 0.05);
  float2 mp = float2(0.0, 0.20); float d = length(q - mp);
  float moon = sstep(0.074, 0.070, d);
  float3 mcol = float3(1.0, 0.96, 0.86) * mix(0.50, 1.0, sstep(0.36, 0.62, fbm((q - mp) * 16.0 + 3.0))) * (0.92 + 0.08 * fbm((q - mp) * 60.0)) * (1.0 - 0.3 * pow(d / 0.074, 3.0));
  float2 cell = floor(q * 46.0); float2 hs = hash22(cell);
  float st = step(0.955, hs.x) * sstep(0.12, 0.0, length(fract(q * 46.0) - 0.5 - (hs - 0.5) * 0.5));
  c += float3(0.8, 0.9, 1.0) * st * (0.4 + 0.6 * sin(t * (1.0 + hs.y * 3.0) + hs.x * 60.0)) * (0.25 + 0.9 * clear) * sstep(0.1, 0.3, d);
  c += float3(0.5, 0.66, 0.95) * (exp(-d * 11.0) * 0.40 + exp(-d * 3.6) * 0.07) * (0.55 + 0.6 * clear);
  c = mix(c, mcol * (0.95 + 0.4 * clear), moon);
  // 流星
  if (shoot.x > 0.0 && shoot.x < 1.0) {
    float2 a = float2(-0.38, 0.92), b = float2(0.30, 0.62); float2 hd = mix(a, b, shoot.x); float2 dir = normalize(b - a);
    float2 r = q - hd; float al = dot(r, dir), pe = length(r - dir * al);
    c += float3(0.9, 0.95, 1.0) * exp(-pe * 220.0) * sstep(-0.22, 0.0, al) * step(al, 0.0) * sin(shoot.x * 3.14159) * 2.2;
  }
  // 薄云（心事）：许愿后散开
  float cl = sstep(0.42, 0.78, fbm(q * float2(1.6, 3.2) + float2(t * 0.012, 0.0))) * (1.0 - clear) * sstep(0.0, 0.12, y);
  float3 ccol = mix(float3(0.02, 0.03, 0.06), float3(0.17, 0.22, 0.32), exp(-d * 3.0));
  return mix(c, ccol, cl * 0.82);
}
static float3 sceneMood(float2 uv, Uniforms u) {
  float t = u.time; float ts = u.prog < 0.0 ? -1.0 : u.prog * u.dur; bool run = ts >= 0.0;
  float clear = run ? sstep(2.3, 6.0, ts) : u.glow;
  float fl = 0.5; float3 ro = float3(0.0, 1.3, 0.0);
  float3 rd = normalize(float3(uv.x * fl, uv.y * fl + 0.10, -1.0));
  float2 shoot = float2(run ? (ts - 6.6) / 0.8 : (fmod(t, 23.0) - 20.0) / 0.9 * u.glow, 0.0);
  float2 hitc = float2(0.0, -9.0);
  float3 col;
  if (rd.y > 0.0) {
    col = skyMood(rd, clear, t, shoot);
  } else {
    float tp = -ro.y / rd.y; float3 p = ro + rd * tp; float2 q = p.xz;
    float att = 1.0 / (1.0 + tp * 0.015);
    float2 g = float2(noise(q * 1.5 + float2(t * 0.20, t * 0.13)) - 0.5, noise(q * 1.5 + float2(9.1 - t * 0.16, 4.3 + t * 0.18)) - 0.5) * 0.10 * att;
    g += float2(noise(q * float2(5.0, 2.2) + t * 0.3) - 0.5, noise(q * float2(5.0, 2.2) + 7.7 - t * 0.25) - 0.5) * float2(0.03, 0.10) * att;
    // 涟漪：对高度场做差分
    float e = 0.03 + tp * 0.004; float h0 = 0.0, hx = 0.0, hz = 0.0;
    if (run) { float age = ts - 2.2; h0 = ring(q, hitc, age, 0.16); hx = ring(q + float2(e, 0.0), hitc, age, 0.16); hz = ring(q + float2(0.0, e), hitc, age, 0.16); }
    for (int i = 0; i < 3; i++) {   // 待机时偶尔落下的细雨点
      float fi = float(i); float cyc = 4.3 + fi * 1.7; float k = floor((t + fi * 2.1) / cyc); float age = (t + fi * 2.1) - k * cyc;
      float2 c = float2((hash11(k * 3.1 + fi) - 0.5) * 5.0, -3.5 - hash11(k * 7.7 + fi * 2.0) * 8.0);
      h0 += ring(q, c, age, 0.022); hx += ring(q + float2(e, 0.0), c, age, 0.022); hz += ring(q + float2(0.0, e), c, age, 0.022);
    }
    float3 n = normalize(float3(g.x - (hx - h0) / e, 1.0, g.y - (hz - h0) / e));
    float3 R = reflect(rd, n); R.y = abs(R.y) + 0.002; R = normalize(R);
    float F = 0.03 + 0.97 * pow(1.0 - max(dot(-rd, n), 0.0), 5.0);
    col = mix(float3(0.004, 0.014, 0.026), skyMood(R, clear, t, shoot), saturate(F * 0.92 + 0.1));
    col = mix(col, float3(0.035, 0.075, 0.15), 1.0 - exp(-tp * 0.012));
  }
  float hzn = -0.10 / fl;
  // 地平线上的薄雾
  col += float3(0.07, 0.13, 0.20) * exp(-abs(uv.y - hzn) * 18.0) * (0.3 + 0.3 * clear);
  if (run) {
    // 一滴光落下
    float2 land = float2(0.0, (-1.3 / 9.0 - 0.10) / fl);
    float q = saturate((ts - 0.9) / 1.3); float2 dp = float2(0.0, mix(1.15, land.y, q * q));
    if (ts > 0.9 && ts < 2.2) {
      float2 r = uv - dp; float tail = exp(-abs(r.x) * 90.0) * sstep(0.0, 0.35 * q, r.y) * sstep(0.45 * q, 0.0, r.y);
      col += float3(0.75, 0.9, 1.0) * (exp(-dot(r, r) * 900.0) * 3.0 + exp(-dot(r, r) * 60.0) * 0.5 + tail * 0.8);
    }
    float fa = ts - 2.2; if (fa > 0.0 && fa < 1.2) { float2 r = (uv - land) * float2(1.0, 3.0); col += float3(0.7, 0.88, 1.0) * exp(-dot(r, r) * 14.0) * exp(-fa * 4.0) * 1.8; }
  }
  // 萤火
  float ff = run ? sstep(3.0, 5.5, ts) : u.glow;
  if (ff > 0.01) for (int i = 0; i < 16; i++) {
    float fi = float(i); float2 h = hash22(float2(fi * 3.7, 11.0));
    float life = fract(t * (0.035 + 0.03 * h.y) + h.x);
    float2 p = float2((h.x - 0.5) * 1.1 + 0.06 * sin(t * 0.7 + fi), mix(hzn - 0.05, hzn + 0.75, life) + 0.03 * sin(t * 1.1 + fi * 2.0));
    float2 r = uv - p; float b = 0.5 + 0.5 * sin(t * (1.5 + h.y * 2.0) + fi);
    col += float3(0.75, 1.0, 0.75) * (exp(-dot(r, r) * 5000.0) * 1.6 + exp(-dot(r, r) * 300.0) * 0.12) * b * ff * sin(life * 3.14159);
  }
  return col;
}

// ═════════ 5 生活：孔明灯 ═════════
static float4 lantern(float2 q, float lit, float seed, float t) {
  // q：灯身占 -0.5..0.5 高。返回预乘颜色和不透明度
  float w = mix(0.27, 0.40, sstep(-0.5, 0.25, q.y)) * (1.0 - 0.25 * sstep(0.25, 0.5, q.y));
  float2 b = float2(abs(q.x) - w, abs(q.y) - 0.5) + 0.07;
  float sd = min(max(b.x, b.y), 0.0) + length(max(b, float2(0.0))) - 0.07;
  float m = sstep(0.02, -0.02, sd);
  float fl = 0.85 + 0.15 * sin(t * 9.0 + seed * 40.0) * sin(t * 5.3 + seed * 17.0);
  float2 fq = (q - float2(0.0, -0.40)) * float2(1.7, 1.0);
  float I = exp(-length(fq) * 2.3) * lit * fl;
  float3 c = mix(float3(0.50, 0.10, 0.03), float3(1.0, 0.52, 0.14), saturate(I * 1.5)) * (0.25 + 0.75 * lit);
  c += float3(1.0, 0.88, 0.55) * I * I * 2.4;
  c *= 1.0 - 0.22 * sstep(0.03, 0.0, abs(abs(q.x) - w * 0.45)) * sstep(0.5, 0.2, abs(q.y));   // 竹骨
  c *= 1.0 - 0.5 * sstep(-0.42, -0.5, q.y);                                               // 底口
  c *= 0.75 + 0.25 * sstep(-w, w * 0.4, q.x);                                              // 侧面受光
  return float4(c * m, m);
}
static float3 sceneLife(float2 uv, Uniforms u) {
  float t = u.time; float ts = u.prog < 0.0 ? -1.0 : u.prog * u.dur; bool run = ts >= 0.0;
  float g = run ? sstep(2.2, 7.5, ts) : u.glow;
  float y = uv.y;
  float3 col = mix(float3(0.95, 0.42, 0.16), float3(0.42, 0.12, 0.26), sstep(-0.66, 0.05, y));
  col = mix(col, float3(0.035, 0.03, 0.12), sstep(0.0, 0.9, y));
  col *= 0.62 + 0.25 * g;
  col += float3(1.0, 0.5, 0.18) * exp(-abs(y + 0.68) * 5.0) * (0.25 + 0.2 * g);
  float2 sc = floor(uv * 60.0); float2 sh = hash22(sc);
  col += float3(1.0, 0.95, 0.9) * step(0.97, sh.x) * sstep(0.14, 0.0, length(fract(uv * 60.0) - 0.5 - (sh - 0.5) * 0.5)) * sstep(0.1, 0.7, y) * (0.5 + 0.5 * sin(t * (1.0 + sh.y * 3.0) + sh.x * 50.0));

  // 灯：四层，由远到近
  for (int l = 0; l < 4; l++) {
    float fl = float(l); float s = 9.0 - fl * 2.2; float v = 0.018 + fl * 0.016;
    float dens = mix(0.10 - fl * 0.02, 0.62 - fl * 0.1, g);
    float2 p = float2(uv.x * s + 0.25 * sin(t * 0.2 + fl * 2.0), (uv.y + t * v) * s) + fl * 17.3;
    float2 id = floor(p), f = fract(p) - 0.5;
    for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
      float2 o = float2(float(i), float(j)); float2 cid = id + o; float2 h = hash22(cid + fl * 5.3);
      if (h.x > dens) continue;
      float size = 0.34 + 0.2 * h.y;
      float2 c = o + (hash22(cid + 9.1) - 0.5) * 0.5;
      // 新放的灯：一道点灯的波从地面扫上天，扫到哪盏哪盏亮
      float lit = 1.0;
      if (run && h.x > 0.10 - fl * 0.02) { float cy = (id.y + 0.5 + c.y - fl * 17.3) / s - t * v; float front = mix(-1.3, 1.6, sstep(2.2, 7.4, ts)); lit = sstep(0.0, 0.3, front - cy - h.y * 0.25); if (lit <= 0.0) continue; }
      float2 q = rot2(f - c, 0.08 * sin(t * 0.6 + h.x * 30.0)) / size;
      float depth = 0.35 + 0.65 * (fl / 3.0);
      float2 hq = (f - c) / size; col += float3(1.0, 0.5, 0.15) * exp(-dot(hq, hq) * 1.3) * 0.16 * depth * lit;
      float4 L = lantern(q, lit, h.x, t);
      col = mix(col, mix(float3(0.75, 0.3, 0.3), L.rgb / max(L.a, 0.001), depth) * (0.55 + 0.6 * depth), L.a * sstep(0.0, 0.35, lit));
    }
  }
  // 远山和人家
  float ridge = -0.76 + 0.10 * fbm(float2(uv.x * 2.4 + 3.0, 1.0)) + 0.03 * noise(float2(uv.x * 14.0, 2.0));
  float land = sstep(ridge + 0.004, ridge - 0.004, y);
  float3 lc = float3(0.035, 0.018, 0.045);
  float2 wc = floor(float2(uv.x * 34.0, y * 34.0)); float2 wh = hash22(wc);
  lc += float3(1.0, 0.62, 0.22) * step(0.86, wh.x) * sstep(0.22, 0.05, length(fract(float2(uv.x * 34.0, y * 34.0)) - 0.5)) * (0.5 + 0.5 * sin(t * (0.5 + wh.y) + wh.x * 30.0)) * sstep(ridge - 0.02, ridge - 0.12, y) * 0.9;
  col = mix(col, lc, land);
  // 自己的那一盏
  if (run) {
    float lit = sstep(0.5, 1.9, ts); float r = sstep(1.9, 8.0, ts);
    float2 hp = float2(0.04 * sin(ts * 0.8), mix(-0.46, 0.62, r * r * (3.0 - 2.0 * r)));
    float size = mix(0.44, 0.15, r); float al = 1.0 - sstep(u.dur - 1.6, u.dur - 0.2, ts);
    float2 hq = (uv - hp) / size; col += float3(1.0, 0.55, 0.18) * exp(-dot(hq, hq) * 1.7) * 0.34 * lit * al;
    float4 L = lantern(rot2(uv - hp, 0.05 * sin(ts * 1.3)) / size, lit, 0.37, t);
    col = mix(col, L.rgb / max(L.a, 0.001), L.a * al);
  }
  return col;
}

// ═════════ 1 事业：登顶日出 ═════════
static float ridgeLine(float x, float fi) {
  float n = fbm(float2(x * (1.1 + fi * 0.55) + fi * 11.3, fi * 3.7));
  float r = 1.0 - abs(2.0 * fbm(float2(x * (2.0 + fi * 0.8) + fi * 5.1, 7.0 + fi)) - 1.0);
  return n * 0.6 + r * r * 0.4;
}
static float3 sceneCareer(float2 uv, Uniforms u) {
  float t = u.time; float ts = u.prog < 0.0 ? -1.0 : u.prog * u.dur; bool run = ts >= 0.0;
  float g = run ? sstep(3.0, 7.2, ts) : u.glow;
  float y = uv.y + 0.05 * g;
  float2 sun = float2(0.10, mix(-0.62, 0.26, g));
  float d = length(float2(uv.x - sun.x, y - sun.y));
  float3 night = mix(float3(0.10, 0.09, 0.20), float3(0.010, 0.016, 0.06), sstep(-0.3, 0.8, y)) + float3(0.30, 0.13, 0.12) * exp(-(y + 0.25) * 4.0) * 0.45;
  float3 day = mix(float3(1.05, 0.50, 0.16), float3(0.62, 0.28, 0.34), sstep(-0.32, 0.18, y)); day = mix(day, float3(0.05, 0.11, 0.32), sstep(0.10, 0.95, y));
  float3 col = mix(night, day, g);
  float2 sc = floor(uv * 64.0); float2 sh = hash22(sc);
  col += float3(0.9, 0.95, 1.0) * step(0.965, sh.x) * sstep(0.14, 0.0, length(fract(uv * 64.0) - 0.5 - (sh - 0.5) * 0.5)) * (0.5 + 0.5 * sin(t * (1.0 + 3.0 * sh.y) + sh.x * 50.0)) * (1.0 - g) * sstep(-0.1, 0.5, y) * 1.6;
  // 高空的卷云，被朝阳染色
  float ci = fbm(float2(uv.x * 1.6 + t * 0.006, y * 5.0 + 3.0));
  float cir = sstep(0.50, 0.78, ci) * sstep(0.12, 0.5, y) * 0.6;
  col = mix(col, mix(float3(0.09, 0.09, 0.19), float3(1.0, 0.52, 0.32), g), cir * (0.35 + 0.65 * g));
  float ang = atan2(y - sun.y, uv.x - sun.x);
  float raysv = pow(saturate(noise(float2(ang * 7.0, t * 0.05)) * 0.7 + noise(float2(ang * 19.0 + 4.0, t * 0.08)) * 0.5), 2.0);
  col += float3(1.0, 0.62, 0.26) * (exp(-d * 4.0) * 0.32 + raysv * exp(-d * 2.4) * 0.20) * g;
  col += float3(1.0, 0.92, 0.75) * sstep(0.058, 0.050, d) * 7.0 * g;        // 日面给足亮度，光晕交给辉光
  float3 fogc = mix(float3(0.10, 0.11, 0.24), float3(0.78, 0.42, 0.28), g);
  float2 peak = float2(0.10, 0.0);
  for (int i = 0; i < 6; i++) {
    float fi = float(i); float dep = fi / 5.0;
    float yy = y + 0.07 * g * dep;
    float base = mix(-0.02, -0.60, dep); float amp = mix(0.14, 0.30, dep);
    float x = uv.x + 0.02 * fi; float e = 0.02;
    float h = base + amp * ridgeLine(x, fi), h2 = base + amp * ridgeLine(x + e, fi);
    if (i == 3) {   // 主峰
      float ax = abs(uv.x - 0.10), ax2 = abs(uv.x + e - 0.10);
      float pk = 0.065 - pow(ax, 0.78) * 0.92 + 0.030 * noise(float2(uv.x * 24.0, 3.0)) * sstep(0.0, 0.08, ax) + 0.012 * noise(float2(uv.x * 70.0, 9.0));
      float pk2 = 0.065 - pow(ax2, 0.78) * 0.92 + 0.030 * noise(float2((uv.x + e) * 24.0, 3.0)) * sstep(0.0, 0.08, ax2) + 0.012 * noise(float2((uv.x + e) * 70.0, 9.0));
      h = max(h, pk); h2 = max(h2, pk2);
      peak.y = 0.065 - 0.07 * g * dep - 0.05 * g;
    }
    float slope = (h2 - h) / e;
    float m = sstep(h + 0.003, h - 0.003, yy);
    float below = h - yy;
    // 朝太阳的坡面受光；只在靠近山脊的地方明显，往下渐渐收掉，不然会拉出竖条
    float lit = mix(0.5, saturate(0.5 - slope * (sun.x > uv.x ? 1.0 : -1.0) * 0.6), exp(-max(below, 0.0) * 20.0));
    float3 rock = mix(float3(0.014, 0.018, 0.045), float3(0.11, 0.045, 0.06), g);
    float3 mc = mix(fogc * (0.5 + 0.2 * g), rock, dep * 0.8 + 0.2);
    mc *= 0.7 + 0.75 * lit * g + 0.25 * lit * (1.0 - g);
    // 山体上的岩纹
    mc *= 0.85 + 0.3 * fbm(float2(x * 9.0 + fi * 4.0, yy * 26.0));
    // 雪线：只有高处有，朝阳时染成金粉色
    float snow = sstep(base + amp * 0.50, base + amp * 0.72, h - below * 2.2 + 0.04 * (noise(float2(x * 26.0, yy * 26.0 + fi)) - 0.5)) * sstep(0.10, 0.0, below) * step(1.5, fi) * step(fi, 3.5);
    mc = mix(mc, mix(float3(0.34, 0.38, 0.55), float3(1.0, 0.72, 0.56), g) * (0.55 + 0.6 * lit), snow * 0.85);
    // 山脚浸在雾里
    mc = mix(mc, fogc * (0.75 + 0.2 * g), sstep(0.0, 0.26, base + amp * 0.62 - yy) * (0.6 - 0.2 * g) * (1.0 - dep * 0.55));
    float rim = exp(-max(below, 0.0) * mix(70.0, 140.0, dep)) * g;
    mc += float3(1.0, 0.60, 0.28) * rim * exp(-abs(uv.x - sun.x) * 2.2) * 0.7;
    col = mix(col, mc, m);
    if (i < 5) {
      float cy = base - 0.075; float cl = fbm(float2(uv.x * 2.2 + t * (0.012 + 0.006 * fi) + fi * 9.0, yy * 7.0 + fi * 3.0));
      float cm = sstep(0.42, 0.70, cl) * exp(-pow((yy - cy) * 8.0, 2.0)) * 0.85;
      col = mix(col, mix(float3(0.15, 0.16, 0.30), float3(1.0, 0.66, 0.46), g), cm);
    }
  }
  // 前景两层松林：每棵树是三层叠起来的三角
  for (int k = 0; k < 2; k++) {
    float fk = float(k); float yy = y + 0.10 * g * (1.0 + fk * 0.4);
    float gy = -0.80 - fk * 0.12 + 0.05 * noise(float2(uv.x * 3.0 + fk * 5.0, 1.0));
    float cover = 0.0;
    for (int o = 0; o < 2; o++) {
      float tx = uv.x * (11.0 - fk * 4.0) + fk * 3.3 + float(o) * 0.47; float tid = floor(tx), tf = fract(tx) - 0.5;
      float hh = hash11(tid + fk * 17.0 + float(o) * 31.0);
      float th = (0.07 + 0.09 * hh) * (1.0 + fk * 0.55); float tw = 0.30 + 0.12 * hh;
      float v = (yy - gy) / th;                                   // 0 在树根，1 在树尖
      float tier = fract(v * 3.0);                                // 三层枝叶
      float w = tw * (1.0 - v) * (0.55 + 0.45 * (1.0 - tier));
      cover = max(cover, sstep(w + 0.02, w - 0.02, abs(tf)) * step(0.0, v) * step(v, 1.0));
    }
    float m = max(cover, sstep(gy + 0.004, gy - 0.004, yy));
    float3 tc = mix(float3(0.007, 0.009, 0.024), float3(0.06, 0.022, 0.03), g) * (1.0 - fk * 0.45);
    tc = mix(tc, fogc * 0.45, sstep(0.10, -0.05, yy - gy) * 0.3 * (1.0 - fk));
    col = mix(col, tc, m);
  }
  // 登顶的那点光：从山脚沿山脊爬到峰顶
  if (run && ts < 3.6) {
    float k = sstep(0.4, 3.2, ts); float2 a = float2(-0.36, -0.52);
    float2 cp = mix(a, peak, k) + float2(0.035 * sin(k * 12.0) * (1.0 - k), 0.0);
    float2 r = uv - cp; col += float3(1.0, 0.85, 0.55) * (exp(-dot(r, r) * 2600.0) * 6.0 + exp(-dot(r, r) * 90.0) * 0.25) * sstep(0.3, 0.6, ts);
    for (int j = 1; j < 9; j++) { float kk = max(k - float(j) * 0.022, 0.0); float2 tp = mix(a, peak, kk) + float2(0.035 * sin(kk * 12.0) * (1.0 - kk), 0.0); float2 rr = uv - tp; col += float3(1.0, 0.75, 0.4) * exp(-dot(rr, rr) * 5000.0) * (1.0 - float(j) / 9.0) * 1.2; }
  }
  float beacon = run ? sstep(3.1, 3.5, ts) : u.glow;
  float2 pr = uv - peak; col += float3(1.0, 0.9, 0.7) * star(pr, 0.02 + 0.006 * sin(t * 2.0)) * beacon * (run ? 1.0 + 4.0 * exp(-max(ts - 3.3, 0.0) * 2.0) : 1.0) * 1.2;
  return col;
}

// ═════════ 球体公用：正交投影下的球面法线 ═════════
static float3 sphN(float2 p, float2 c, float r) { float2 q = (p - c) / r; float z2 = 1.0 - dot(q, q); return float3(q.x, q.y, sqrt(max(z2, 0.0))); }
static float softbox(float3 R, float3 dir, float size, float soft) { return sstep(size - soft, size + soft, dot(R, normalize(dir))); }
static float windowBox(float3 R) {
  float3 Lw = normalize(float3(-0.5, 0.66, 0.56));
  float sp = softbox(R, float3(-0.5, 0.66, 0.56), 0.945, 0.02);
  float2 wq = float2(dot(R, normalize(cross(Lw, float3(0.0, 1.0, 0.0)))), dot(R, float3(0.0, 1.0, 0.0)) - Lw.y);
  return sp * (1.0 - 0.8 * sstep(0.022, 0.0, abs(wq.x)) - 0.8 * sstep(0.022, 0.0, abs(wq.y)));
}
static float3 orbEnv(float3 R, float3 sky, float3 ground, float3 key) {
  float3 c = mix(ground, sky, sstep(-0.10, 0.08, R.y));
  c += sky * 1.6 * exp(-abs(R.y + 0.02) * 9.0);
  c += key * (max(windowBox(R), 0.0) * 3.2 + softbox(R, float3(0.78, 0.2, 0.6), 0.972, 0.012) * 1.1 + softbox(R, float3(0.1, -0.75, 0.6), 0.90, 0.06) * 0.25);
  return c;
}

// ═════════ 2 外貌：缎面上的珍珠 ═════════
static float petal(float2 q) { q.x = abs(q.x); float d = length(float2(q.x * 1.9, q.y)) - 0.5 + 0.35 * q.y; return d; }
static float3 sceneLooks(float2 uv, Uniforms u) {
  float t = u.time; float ts = u.prog < 0.0 ? -1.0 : u.prog * u.dur; bool run = ts >= 0.0;
  float g = run ? sstep(1.4, 5.0, ts) : u.glow;
  float3 col = mix(float3(0.17, 0.05, 0.095), float3(0.03, 0.008, 0.024), sstep(-0.2, 0.95, uv.y + uv.x * 0.25));
  col += float3(0.5, 0.2, 0.26) * exp(-length(uv - float2(-0.35, 0.75)) * 2.4) * 0.3;
  col += bokeh(uv, t, 0.2 + 0.3 * g, float3(1.0, 0.66, 0.7), 3.0) * (0.16 + 0.34 * g) * sstep(-0.1, 0.3, uv.y);
  // 镜面台：下半屏是一块深色的亮面，映着珍珠
  float2 c0 = float2(0.0, 0.32); float R0 = 0.265;
  float fy = -0.06;
  if (uv.y < fy) {
    float dpt = fy - uv.y;
    float3 fc = mix(float3(0.10, 0.028, 0.055), float3(0.016, 0.004, 0.012), sstep(0.0, 0.8, dpt));
    float wob = (noise(float2(uv.x * 7.0, dpt * 34.0 - t * 0.25)) - 0.5) * 0.035 * (0.3 + dpt * 2.0);
    float2 m = float2(uv.x + wob, 2.0 * fy - uv.y);
    float rr = length((m - c0) * float2(1.0, 0.82));
    float refl = sstep(R0 + 0.02, R0 - 0.06, rr);
    float3 rn = sphN(m, c0, R0 * 1.02);
    float3 rc = mix(float3(0.42, 0.24, 0.28), float3(0.95, 0.86, 0.85), saturate(rn.y * 0.5 + 0.55)) * (0.55 + 0.25 * g);
    fc = mix(fc, rc, refl * exp(-dpt * 2.2) * 0.55);
    fc += float3(1.0, 0.66, 0.70) * exp(-max(rr - R0, 0.0) * 9.0) * (0.05 + 0.10 * g) * exp(-dpt * 2.0);
    fc += float3(0.9, 0.5, 0.58) * exp(-dpt * 30.0) * 0.10;
    col = mix(col, fc, sstep(fy, fy - 0.008, uv.y));
  }
  // 光环
  if (run) for (int i = 0; i < 3; i++) { float a = ts - 1.6 - float(i) * 1.0; if (a > 0.0 && a < 2.4) { float rr = R0 + a * 0.32; float d = abs(length(uv - c0) - rr); col += float3(1.0, 0.8, 0.78) * exp(-d * 55.0) * (1.0 - a / 2.4) * 0.6; } }
  // 珍珠
  float dc = length(uv - c0);
  col += float3(1.0, 0.66, 0.70) * exp(-max(dc - R0, 0.0) * 11.0) * (0.07 + 0.17 * g);
  if (dc < R0) {
    float3 n = sphN(uv, c0, R0); float3 Rf = reflect(float3(0.0, 0.0, -1.0), n);
    float ndv = n.z; float fr = pow(1.0 - ndv, 4.0);
    float3 L = normalize(float3(-0.5, 0.65, 0.58));
    float dif = saturate(dot(n, L)); float wrap = saturate(dot(n, L) * 0.6 + 0.4);
    float3 body = float3(0.95, 0.88, 0.86) * (0.10 + 0.90 * wrap * wrap);                   // 明暗交界压深，才有体积
    body += float3(0.75, 0.30, 0.38) * saturate(0.1 - n.y * 0.8) * 0.24 * (1.0 - dif);      // 台面映上来的粉
    body += float3(0.26, 0.12, 0.15) * (1.0 - wrap) * 0.4;                                  // 珠层里透出来的一点暖
    float3 irid = pal(ndv * 1.2 + n.x * 0.3 + n.y * 0.2 + 0.04 * sin(t * 0.3));
    body = mix(body, body * (0.55 + 0.9 * irid), 0.2 + 0.4 * fr);                           // 虹彩
    float3 env = orbEnv(Rf, float3(0.30, 0.12, 0.18), float3(0.05, 0.012, 0.03), float3(1.0, 0.95, 0.93));
    float F = 0.07 + 0.93 * fr;
    float sweep = run ? exp(-pow((n.x * 0.8 + n.y * 0.6) - mix(-1.6, 1.6, sstep(0.2, 1.5, ts)), 2.0) * 7.0) * 2.4 : 0.0;
    float3 pc = body * (1.0 - 0.6 * F) + env * (0.16 + 0.84 * F) + float3(1.0, 0.97, 0.95) * (max(windowBox(Rf), 0.0) * 1.1 + sweep);
    pc *= 1.0 + 0.2 * g;
    col = mix(col, pc, sstep(R0, R0 - 0.004, dc));
  }
  // 花瓣
  for (int i = 0; i < 16; i++) {
    float fi = float(i); float2 h = hash22(float2(fi * 4.1, 2.3)); float h3 = hash11(fi * 9.7);
    if (h3 > 0.4 + 0.6 * g && !run) continue;
    float life = fract(t * (0.03 + 0.03 * h.y) + h.x);
    float2 p = float2((h.x - 0.5) * 1.15 + 0.10 * sin(t * 0.5 + fi * 1.7), mix(1.15, -1.1, life));
    if (run) { float k = sstep(1.5, 4.5, ts) * (1.0 - sstep(5.5, u.dur, ts)); float an = fi * 0.9 + ts * (1.1 + 0.4 * h.y); float rr = R0 + 0.10 + 0.22 * h.y + 0.05 * sin(ts + fi); float2 sp2 = c0 + float2(cos(an) * rr, sin(an) * rr * 0.55 + 0.25 * sin(ts * 0.6 + fi)); p = mix(p, sp2, k); }
    float size = 0.045 + 0.05 * h.y; float2 q = rot2(uv - p, t * (0.4 + h.x) + fi) / size;
    float d = petal(q); float m = sstep(0.06, -0.06, d);
    float3 pcw = mix(float3(0.95, 0.42, 0.55), float3(1.0, 0.82, 0.86), sstep(-0.5, 0.4, q.y)) * (0.62 + 0.2 * sin(fi)) * (0.8 + 0.2 * sstep(0.3, 0.0, abs(q.x)));
    col = mix(col, pcw, m * (0.55 + 0.4 * h3));
  }
  if (run) for (int i = 0; i < 6; i++) { float fi = float(i); float2 h = hash22(float2(fi, 8.0)); float a = fract(ts * 0.5 + h.x); float2 p = c0 + (h - 0.5) * R0 * 1.5; col += float3(1.0, 0.95, 0.95) * star(uv - p, 0.014) * sin(a * 3.14159) * sstep(1.0, 2.0, ts) * (1.0 - sstep(6.0, 7.5, ts)) * 0.9; }
  return col;
}

// ═════════ 3 健康：会呼吸的翡翠 ═════════
static float leaf(float2 q) { q.x = abs(q.x); return length(float2(q.x * 2.4, q.y)) - 0.5 + 0.25 * abs(q.y); }
static float3 sceneHealth(float2 uv, Uniforms u) {
  float t = u.time; float ts = u.prog < 0.0 ? -1.0 : u.prog * u.dur; bool run = ts >= 0.0;
  float g = run ? sstep(1.0, 6.5, ts) : u.glow;
  // 呼吸：待机时慢，仪式里三次深呼吸
  float br = run ? pow(0.5 - 0.5 * cos(saturate((ts - 0.6) / 6.6) * 6.2832 * 3.0), 1.3) * (1.0 - sstep(7.2, 7.6, ts)) : 0.5 + 0.5 * sin(t * 0.9);
  float3 col = mix(float3(0.02, 0.10, 0.085), float3(0.005, 0.03, 0.035), sstep(-0.3, 1.0, uv.y));
  col += float3(0.25, 0.5, 0.25) * exp(-length(uv - float2(0.25, 0.95)) * 2.2) * 0.2;
  col += bokeh(uv, t, 0.3 + 0.25 * g, float3(0.55, 1.0, 0.55), 5.0) * (0.14 + 0.26 * g) * sstep(-0.15, 0.4, uv.y);
  float2 c0 = float2(0.0, 0.30); float R0 = 0.24 * (1.0 + 0.07 * br);
  float wl = -0.16;
  // 水面：倒影和呼出去的光环
  if (uv.y < wl) {
    float dpt = (wl - uv.y); float2 m = float2(uv.x, wl + dpt) + float2(noise(float2(uv.x * 9.0, dpt * 30.0 - t * 0.6)) - 0.5, 0.0) * 0.03 * (0.3 + dpt * 3.0);
    float3 wc = float3(0.004, 0.035, 0.035) + float3(0.02, 0.09, 0.07) * exp(-dpt * 3.0);
    float rd0 = length((m - c0) * float2(1.0, 0.75));
    wc += float3(0.2, 0.9, 0.5) * exp(-max(rd0 - R0, 0.0) * 13.0) * (0.10 + 0.22 * br + 0.10 * g) * exp(-dpt * 1.5);
    float2 fc = float2(c0.x, wl - 0.20); float2 e = (uv - fc) * float2(1.0, 3.4);
    if (run) for (int i = 0; i < 3; i++) { float a = ts - 0.6 - (float(i) + 0.55) * 2.2; if (a > 0.0 && a < 2.6) { float d = abs(length(e) - a * 0.42); wc += float3(0.5, 1.0, 0.7) * exp(-d * 34.0) * (1.0 - a / 2.6) * 0.9; } }
    else { float a = fmod(t * 0.9 / 6.2832 * 2.0 + 0.5, 2.0); float d = abs(length(e) - a * 0.4); wc += float3(0.4, 0.9, 0.6) * exp(-d * 34.0) * (1.0 - a / 2.0) * 0.25; }
    col = mix(col, wc, sstep(wl, wl - 0.012, uv.y));
  }
  col += float3(0.5, 0.9, 0.6) * exp(-abs(uv.y - wl) * 26.0) * 0.12;
  // 翡翠
  float dc = length(uv - c0);
  col += float3(0.25, 1.0, 0.5) * exp(-max(dc - R0, 0.0) * (15.0 - 5.0 * br)) * (0.06 + 0.2 * br + 0.07 * g);
  if (dc < R0) {
    float3 n = sphN(uv, c0, R0); float3 Rf = reflect(float3(0.0, 0.0, -1.0), n); float ndv = n.z; float fr = pow(1.0 - ndv, 4.0);
    // 石头内部的絮：沿视线往里取几层噪声
    float veins = 0.0; for (int i = 0; i < 4; i++) { float k = float(i) * 0.22; float2 q = n.xy * (1.0 - k * 0.35) + float2(k * 1.7, k * 0.9 + t * 0.01); veins += fbm(q * (2.6 + k * 2.0) + 3.0) / 4.0; }
    float3 deep = float3(0.003, 0.085, 0.045), mid = float3(0.025, 0.36, 0.18), light = float3(0.46, 0.84, 0.60);
    float3 jade = mix(deep, mid, sstep(0.3, 0.62, veins)); jade = mix(jade, light, sstep(0.58, 0.82, veins) * 0.7);
    float3 L = normalize(float3(-0.45, 0.7, 0.55));
    float wrap = saturate(dot(n, L) * 0.6 + 0.4);
    float3 pc = jade * (0.16 + 1.0 * wrap * wrap);
    // 背光一侧反而亮：光穿过石头从暗面透出来
    pc += float3(0.20, 0.95, 0.48) * pow(saturate(dot(n, normalize(float3(0.5, -0.55, 0.5)))), 2.0) * (0.20 + 0.30 * br);
    pc += float3(0.4, 1.0, 0.6) * exp(-dot(n.xy, n.xy) * 2.6) * (0.03 + 0.30 * br) * (0.6 + 0.4 * g);
    float3 env = orbEnv(Rf, float3(0.10, 0.30, 0.20), float3(0.004, 0.03, 0.03), float3(1.0, 1.0, 0.96));
    float F = 0.05 + 0.95 * fr;
    pc = pc * (1.0 - 0.5 * F) + env * (0.12 + 0.88 * F) + float3(1.0, 1.0, 0.97) * max(windowBox(Rf), 0.0) * 1.2;
    col = mix(col, pc, sstep(R0, R0 - 0.004, dc));
  }
  // 叶子和光点
  for (int i = 0; i < 14; i++) {
    float fi = float(i); float2 h = hash22(float2(fi * 5.3, 6.1));
    float vis = run ? sstep(1.2, 3.0, ts) : u.glow * step(h.x, 0.6); if (vis < 0.01) continue;
    float an = fi * 0.45 + t * (0.25 + 0.2 * h.y); float life = fract(t * (0.04 + 0.03 * h.y) + h.x);
    float rr = R0 + 0.07 + 0.24 * h.x; float2 p = c0 + float2(cos(an) * rr, mix(-0.5, 0.75, life));
    float size = 0.035 + 0.035 * h.y; float2 q = rot2(uv - p, an * 1.3 + fi) / size; float d = leaf(q);
    float m = sstep(0.06, -0.04, d) * vis * sin(life * 3.14159);
    float3 lc = mix(float3(0.10, 0.5, 0.22), float3(0.65, 0.95, 0.5), sstep(-0.5, 0.5, q.y)) * (1.0 - 0.3 * sstep(0.04, 0.0, abs(q.x)));
    col = mix(col, lc, m * 0.9);
    float2 r = uv - (p + float2(0.05, 0.03)); col += float3(0.7, 1.0, 0.7) * exp(-dot(r, r) * 6000.0) * vis * 0.9 * sin(life * 3.14159);
  }
  return col;
}

// ═════════ 6 宠物：爪印星光 ═════════
static float pawSD(float2 q) {
  float2 m = q - float2(0.0, -0.18); float d = length(m * float2(1.0, 1.15)) - 0.30;
  d = min(d, length(m - float2(-0.17, 0.10)) - 0.17); d = min(d, length(m - float2(0.17, 0.10)) - 0.17);
  d = min(d, length((q - float2(-0.36, 0.14)) * float2(1.15, 1.0)) - 0.13); d = min(d, length((q - float2(0.36, 0.14)) * float2(1.15, 1.0)) - 0.13);
  d = min(d, length((q - float2(-0.14, 0.40)) * float2(1.15, 1.0)) - 0.14); d = min(d, length((q - float2(0.14, 0.40)) * float2(1.15, 1.0)) - 0.14);
  return d;
}
static float heartSD(float2 p) { p.x = abs(p.x); p.y = -p.y + 0.25; float a = atan2(p.x, p.y) / 3.14159; float r = length(p); float hh = abs(a); float d = (13.0 * hh - 22.0 * hh * hh + 10.0 * hh * hh * hh) / (6.0 - 5.0 * hh); return r - d * 0.55; }
static float3 scenePet(float2 uv, Uniforms u) {
  float t = u.time; float ts = u.prog < 0.0 ? -1.0 : u.prog * u.dur; bool run = ts >= 0.0;
  float g = run ? sstep(4.4, 6.5, ts) : u.glow;
  float3 col = mix(float3(0.17, 0.07, 0.06), float3(0.07, 0.03, 0.075), sstep(-1.0, 0.1, uv.y));
  col = mix(col, float3(0.018, 0.012, 0.045), sstep(0.0, 1.0, uv.y));
  col += float3(1.0, 0.5, 0.22) * exp(-length(uv - float2(0.0, -1.15)) * 2.0) * 0.26;
  float2 sc = floor(uv * 52.0); float2 sh = hash22(sc);
  col += float3(1.0, 0.92, 0.85) * step(0.96, sh.x) * sstep(0.15, 0.0, length(fract(uv * 52.0) - 0.5 - (sh - 0.5) * 0.5)) * (0.4 + 0.6 * sin(t * (1.0 + 3.0 * sh.y) + sh.x * 50.0)) * sstep(-0.5, 0.4, uv.y);
  col += bokeh(uv, t, 0.2 + 0.25 * g, float3(1.0, 0.66, 0.42), 9.0) * (0.14 + 0.24 * g);
  // 天上的爪印星座
  float2 c0 = float2(0.0, 0.34); float cs = 0.30 * (1.0 + 0.04 * sin(t * 1.2));
  float2 q = (uv - c0) / cs; float pd = pawSD(q);
  float base = 0.25 + 0.75 * g; float pop = run ? exp(-pow((ts - 4.9) * 2.4, 2.0)) : 0.0;
  col += float3(1.0, 0.74, 0.5) * exp(-max(pd, 0.0) * 9.0) * (0.10 + 0.35 * g + 0.6 * pop);
  float edge = exp(-abs(pd) * 60.0);
  col += float3(1.0, 0.88, 0.7) * edge * (0.35 * base + 0.8 * pop);
  float fill = sstep(0.01, -0.02, pd);
  col += float3(1.0, 0.68, 0.45) * fill * (0.05 + 0.32 * g + 0.5 * pop) * (0.8 + 0.2 * noise(q * 9.0 + t * 0.2));
  // 肉垫上的星：五颗
  float2 pts[5] = { float2(0.0, -0.16), float2(-0.36, 0.14), float2(0.36, 0.14), float2(-0.14, 0.40), float2(0.14, 0.40) };
  for (int i = 0; i < 5; i++) { float2 r = uv - (c0 + pts[i] * cs); col += float3(1.0, 0.95, 0.85) * star(r, 0.016) * (0.35 + 0.65 * g + 0.3 * sin(t * 2.0 + float(i) * 1.3)) * (0.5 + 0.5 * base); }
  // 一串小脚印从下面走上来
  if (run) for (int i = 0; i < 9; i++) {
    float fi = float(i); float a = ts - 0.5 - fi * 0.42; if (a <= 0.0 || a > 3.6) continue;
    float k = fi / 8.0; float2 p = float2((fmod(fi, 2.0) < 0.5 ? -0.085 : 0.085) + 0.12 * sin(k * 3.2), mix(-0.86, 0.02, k));
    float2 fq = rot2(uv - p, -0.25 * cos(k * 3.2) + (fmod(fi, 2.0) < 0.5 ? 0.18 : -0.18)) / (0.085 * (1.0 + 0.5 * exp(-a * 9.0)));
    float d = pawSD(fq); float al = sstep(0.0, 0.12, a) * (1.0 - sstep(1.6, 3.6, a));
    col += float3(1.0, 0.72, 0.42) * (sstep(0.02, -0.03, d) * 0.85 + exp(-max(d, 0.0) * 9.0) * 0.35) * al;
  }
  // 最后开出一颗心
  float hb = run ? sstep(5.0, 5.8, ts) * (1.0 - sstep(u.dur - 1.0, u.dur, ts) * (1.0 - 0.0)) : 0.0;
  if (run && hb > 0.0) {
    float hsz = 0.11 * (0.6 + 0.4 * hb) * (1.0 + 0.08 * sin(ts * 7.0) * exp(-(ts - 5.8) * 1.2));
    float2 hp = c0 + float2(0.0, -0.045) * cs / 0.30; float hd = heartSD((uv - hp) / hsz);
    float fadeOut = 1.0 - sstep(u.dur - 1.2, u.dur - 0.1, ts);
    col += float3(1.0, 0.45, 0.5) * (sstep(0.03, -0.03, hd) * 0.9 + exp(-max(hd, 0.0) * 6.0) * 0.5) * hb * fadeOut;
    for (int i = 0; i < 10; i++) { float fi = float(i); float2 h = hash22(float2(fi, 21.0)); float a = (ts - 5.2) * (0.5 + 0.5 * h.y); if (a < 0.0 || a > 1.6) continue; float an = fi * 0.628 + h.x; float2 p = hp + float2(cos(an), sin(an)) * a * 0.28; col += float3(1.0, 0.8, 0.7) * star(uv - p, 0.012) * (1.0 - a / 1.6) * 1.2; }
  }
  return col;
}

// ═════════ 卡点释放：五种释放方式 ═════════
// 这五场只看进度 P（0 = 还没开始，1 = 已经释放完），时长由外面定，轻量和深度两档共用同一套画面。
static float relP(Uniforms u) { return u.prog < 0.0 ? (u.glow > 0.5 ? 1.0 : 0.0) : u.prog; }
// 小游戏：进度 G 走仪式时间轴的 p0..p1，攒满以后的奖励动画走 p1..p2
static bool gameOn(Uniforms u) { return u.game.x > 0.5; }
static float gameP(Uniforms u, float p0, float p1, float p2) { return u.game2.x >= 0.0 ? mix(p1, p2, u.game2.x) : mix(p0, p1, u.game.y); }
// 点一下的那一圈光：在 uv 平面上从点的位置散开
static float tapRing(float2 uv, Uniforms u) {
  if (u.game.x < 0.5) return 0.0;
  float a = u.game.w; float r = length(uv - u.tap);
  return exp(-abs(r - a * 0.9) * 38.0) * exp(-a * 3.2) + exp(-r * 16.0) * exp(-a * 9.0) * 0.8;
}
static float caustic(float2 p, float t) {
  p = p - 6.2832 * floor(p / 6.2832) - 250.0; t += 23.0;
  float2 i = p; float c = 1.0; float inten = 0.005;
  for (int n = 0; n < 4; n++) {
    float tt = t * (1.0 - 3.5 / float(n + 1));
    i = p + float2(cos(tt - i.x) + sin(tt + i.y), sin(tt - i.y) + cos(tt + i.x));
    c += 1.0 / length(float2(p.x / (sin(i.x + tt) / inten), p.y / (cos(i.y + tt) / inten)));
  }
  c /= 4.0; c = 1.17 - pow(c, 1.4);
  return saturate(pow(abs(c), 8.0));
}
static float wingShape(float2 p, float spread) {
  float r = length(p); float th = atan2(p.y, p.x);
  float u = (1.0 * spread - th) / (2.3 * spread);
  if (u < 0.0 || u > 1.0 || r < 0.001) return 0.0;
  float L = (0.50 * pow(1.0 - u, 1.3) + 0.13) * sstep(0.0, 0.10, u);
  float f = fract(u * 12.0);
  L *= 0.86 + 0.14 * sqrt(max(1.0 - (2.0 * f - 1.0) * (2.0 * f - 1.0), 0.0));
  float body = sstep(L, L * 0.62, r) * sstep(0.0, 0.07, r);
  return body * (0.5 + 0.5 * pow(sin(f * 3.14159), 0.6)) * (0.6 + 0.4 * sstep(1.0, 0.2, u));
}

// 一片升起的光点：在 c 附近生成，向上飘，带闪烁
static float3 motes(float2 uv, float2 c, float spread, float t, float amount, float3 tint, float seed) {
  float3 acc = float3(0.0);
  if (amount < 0.01) return acc;
  for (int i = 0; i < 18; i++) {
    float fi = float(i); float2 h = hash22(float2(fi * 3.7 + seed, seed * 1.3 + 5.0));
    float life = fract(t * (0.10 + 0.12 * h.y) + h.x);
    float2 p = c + float2((h.x - 0.5) * spread * (0.4 + life), -0.05 + life * (0.5 + 0.5 * h.y)) + float2(0.03 * sin(t * 1.3 + fi), 0.0);
    acc += tint * star(uv - p, 0.009 + 0.008 * h.y) * sin(life * 3.14159) * (0.5 + 0.5 * sin(t * 5.0 + fi * 2.0)) * amount;
  }
  return acc;
}

// 小游戏攒满时的奖励：从 c 炸开一圈光和一把星星，慢慢落下去
static float3 rewardBurst(float2 uv, float2 c, Uniforms u, float3 tint, float seed) {
  float R = u.game2.x; if (u.game.x < 0.5 || R < 0.0) return float3(0.0);
  float3 acc = float3(0.0); float k = 1.0 - pow(1.0 - saturate(R * 1.5), 3.0); float live = 1.0 - sstep(0.45, 0.95, R);
  for (int i = 0; i < 34; i++) { float fi = float(i); float2 h = hash22(float2(fi * 1.7 + seed, 3.3)); float an = fi * 2.399;
    float2 p = c + float2(cos(an), sin(an) * 0.9 + 0.15) * k * (0.22 + 0.78 * h.x) * 0.85 - float2(0.0, 0.30 * R * R);
    acc += mix(tint, float3(1.0), 0.3 + 0.4 * h.y) * star(uv - p, 0.009 + 0.010 * h.y) * live * (0.6 + 0.4 * sin(u.time * 7.0 + fi * 2.0)) * 1.5; }
  acc += mix(tint, float3(1.0), 0.4) * exp(-abs(length(uv - c) - k * 0.85) * 20.0) * (1.0 - saturate(R * 2.4)) * 0.9;
  acc += tint * exp(-length(uv - c) * 5.0) * exp(-R * 9.0) * 1.2;
  return acc;
}

// ───────── 纸船（光线步进） ─────────
struct BoatT { float3 pos; float yaw; float roll; float pitch; float sc; };
static float sdBoat(float3 p) {
  float ax = abs(p.x) / 0.5;
  float taper = max(1.0 - pow(ax, 1.7), 0.0);
  float top = 0.19 + 0.11 * ax * ax;                       // 船舷两头上翘
  float w = 0.20 * taper;
  float side = abs(p.z) - (w * pow(saturate(p.y / top), 0.65) + 0.006);
  float d = max(side * 0.75, max(-p.y, p.y - top));
  d = max(d, abs(p.x) - 0.5);
  float cav = max(abs(p.z) - max(w - 0.022, 0.0) * pow(saturate((p.y - 0.025) / top), 0.65), 0.03 - p.y);
  cav = max(cav, abs(p.x) - 0.47);
  d = max(d, -cav * 0.75);                                  // 掏空船舱
  float sy = (p.y - 0.03) / 0.36;
  float sail = max(abs(p.z) - 0.012, max(abs(p.x) - 0.17 * (1.0 - sy), 0.03 - p.y));
  return min(d, max(sail, p.y - 0.39));                     // 中间立着的三角
}
static float3 boatLocal(float3 p, BoatT b) {
  float3 q = (p - b.pos) / b.sc;
  float2 xz = rot2(float2(q.x, q.z), b.yaw); q.x = xz.x; q.z = xz.y;
  float2 yz = rot2(float2(q.y, q.z), b.roll); q.y = yz.x; q.z = yz.y;
  float2 xy = rot2(float2(q.x, q.y), b.pitch); q.x = xy.x; q.y = xy.y;
  return q;
}
static float mapBoat(float3 p, BoatT b) { return sdBoat(boatLocal(p, b)) * b.sc; }
static float marchBoat(float3 ro, float3 rd, BoatT b) {
  float3 c = b.pos + float3(0.0, 0.2, 0.0) * b.sc; float r = 0.62 * b.sc;
  float3 oc = ro - c; float bb = dot(oc, rd); float cc = dot(oc, oc) - r * r; float disc = bb * bb - cc;
  if (disc < 0.0) return -1.0;
  float t = max(-bb - sqrt(disc), 0.0), tEnd = -bb + sqrt(disc);
  for (int i = 0; i < 70; i++) {
    float d = mapBoat(ro + rd * t, b);
    if (d < 0.0012 * b.sc + t * 0.0004) return t;
    t += d * 0.7;
    if (t > tEnd) break;
  }
  return -1.0;
}
static float3 shadeBoat(float3 p, float3 rd, BoatT b, float3 L, float3 lightCol, float3 amb, float3 glowCol) {
  float2 e = float2(0.002 * b.sc, 0.0);
  float3 n = normalize(float3(mapBoat(p + e.xyy, b) - mapBoat(p - e.xyy, b), mapBoat(p + e.yxy, b) - mapBoat(p - e.yxy, b), mapBoat(p + e.yyx, b) - mapBoat(p - e.yyx, b)));
  if (dot(n, rd) > 0.0) n = -n;
  float dif = saturate(dot(n, L));
  float3 c = float3(0.97, 0.95, 0.91) * (amb + lightCol * (0.15 + 0.85 * dif));
  c += lightCol * 0.22 * saturate(-dot(n, L));                                          // 纸是透光的
  float3 q = boatLocal(p, b);
  c *= 0.86 + 0.14 * sstep(0.0, 0.05, abs(q.y - 0.105));                                // 一道折痕
  c += glowCol * exp(-length(q - float3(0.0, 0.08, 0.0)) * 5.5);                        // 船舱里那张纸条的光
  return c;
}

// ───────── 7 许愿池流水 ─────────
static float3 skyPool(float3 rd, float P, float t) {
  float y = max(rd.y, 0.0);
  float3 c = mix(float3(1.0, 0.60, 0.30), float3(0.26, 0.38, 0.66), sstep(0.0, 0.5, y)); c = mix(c, float3(0.95, 0.52, 0.46), 0.35 * sstep(0.04, 0.2, y) * sstep(0.5, 0.2, y)); c *= 0.36 + 0.22 * P;
  float2 q = rd.xy / max(-rd.z, 0.05); float2 sp = float2(0.0, 0.05 + 0.10 * P); float d = length(q - sp);
  c += float3(1.0, 0.62, 0.28) * (exp(-d * 7.0) * 0.45 + exp(-d * 1.8) * 0.14) * (0.5 + 0.4 * P);
  c += float3(1.0, 0.9, 0.7) * sstep(0.030, 0.025, d) * 2.4;
  float cl = sstep(0.5, 0.8, fbm(q * float2(1.5, 4.5) + float2(t * 0.01, 0.0))) * sstep(0.06, 0.3, q.y) * 0.4;
  c = mix(c, float3(1.0, 0.82, 0.70) * (0.5 + 0.5 * P), cl);
  float hill = 0.035 + 0.05 * fbm(float2(q.x * 2.6 + 4.0, 3.0));
  c = mix(c, mix(float3(0.20, 0.19, 0.28), float3(0.46, 0.38, 0.40), P) * 0.55, sstep(hill + 0.004, hill - 0.004, q.y) * 0.8);
  return c;
}
static float3 sceneRelPool(float2 uv, Uniforms u) {
  float t = u.time; bool game = gameOn(u); float P = game ? gameP(u, 0.04, 0.66, 1.0) : relP(u); bool run = u.prog >= 0.0 || game;
  float E = game ? u.game.z : 0.0; float kick = game ? exp(-u.game.w * 5.0) : 0.0;
  float fl = 0.5; float3 ro = float3(0.0, 0.8, 0.0);
  float3 rd = normalize(float3(uv.x * fl, uv.y * fl - 0.14, -1.0));
  float e = pow(sstep(0.04, 0.86, P), 1.25);
  BoatT b; b.sc = 1.0;
  b.pos = float3(-0.9 * e + 0.25 * sin(e * 4.2) * e, 0.012 * sin(t * 1.5), mix(-3.0, -15.0, e));
  b.yaw = 1.12 + 0.25 * cos(e * 4.2) * e + 0.05 * sin(t * 0.5); b.roll = 0.05 * sin(t * 1.2); b.pitch = 0.03 * sin(t * 1.6 + 1.0);
  float gone = sstep(0.74, 0.90, P);
  float3 L = normalize(float3(0.15, 0.35, -0.9)); float3 lc = float3(1.0, 0.78, 0.5) * (0.7 + 0.5 * P), amb = float3(0.30, 0.36, 0.48) * (0.5 + 0.4 * P);
  float3 glowc = float3(1.0, 0.72, 0.3) * (0.5 + 0.5 * sin(t * 2.0) * 0.2) * (run || P > 0.5 ? 0.9 : 0.0) * (1.0 + 1.6 * E);
  float tb = gone < 1.0 ? marchBoat(ro, rd, b) : -1.0;
  float3 col;
  if (rd.y >= 0.0) {
    col = skyPool(rd, P, t);
  } else {
    float tp = -ro.y / rd.y; float3 p = ro + rd * tp; float2 q = p.xz;
    float att = 1.0 / (1.0 + tp * 0.06);
    float2 fq = q * 1.4 + float2(0.0, t * 0.45);                     // 水往远处流
    float2 g = float2(noise(fq) - 0.5, noise(fq + float2(7.3, 2.1)) - 0.5) * 0.10 * att;
    g += float2(noise(fq * float2(4.5, 2.0)) - 0.5, noise(fq * float2(4.5, 2.0) + 5.0) - 0.5) * float2(0.03, 0.09) * att;
    float2 bd = q - b.pos.xz; float bl = length(bd);
    g += normalize(bd + 1e-4) * sin(bl * 16.0 - t * (5.0 + 6.0 * E)) * exp(-bl * (2.2 - 1.0 * E)) * (0.07 + 0.10 * E + 0.08 * kick) * (1.0 - gone);   // 船边的水纹
    if (game) {   // 手指点在水面上荡开的一圈
      float3 rt = normalize(float3(u.tap.x * fl, min(u.tap.y, 0.2) * fl - 0.14, -1.0));
      if (rt.y < -0.01) { float2 tq = (ro + rt * (-ro.y / rt.y)).xz; float2 td = q - tq; float tl = length(td); float age = u.game.w;
        g += normalize(td + 1e-4) * sin(tl * 9.0 - age * 11.0) * exp(-abs(tl - age * 1.3) * 2.2) * exp(-age * 1.6) * 0.16 * att; }
    }
    float3 n = normalize(float3(g.x, 1.0, g.y));
    float3 R = reflect(rd, n); R.y = abs(R.y) + 0.09; R = normalize(R);
    float3 rc = skyPool(R, P, t);
    float tr = gone < 1.0 ? marchBoat(p + n * 0.01, R, b) : -1.0;
    if (tr > 0.0) rc = mix(shadeBoat(p + n * 0.01 + R * tr, R, b, L, lc, amb, glowc), rc, gone);
    float F = 0.04 + 0.96 * pow(1.0 - max(dot(-rd, n), 0.0), 5.0);
    col = mix(mix(float3(0.02, 0.09, 0.10), float3(0.05, 0.20, 0.19), P), rc, saturate(F * 0.92 + 0.12));
    col = mix(col, skyPool(normalize(float3(rd.x, 0.02, rd.z)), P, t), 1.0 - exp(-tp * 0.02));
  }
  if (tb > 0.0 && (rd.y >= 0.0 || tb < -ro.y / rd.y)) {
    float3 bc = shadeBoat(ro + rd * tb, rd, b, L, lc, amb, glowc);
    bc = mix(bc, skyPool(normalize(float3(rd.x, 0.02, rd.z)), P, t), 1.0 - exp(-tb * 0.02));
    float nd = noise(boatLocal(ro + rd * tb, b).xy * 15.0 + 2.0); float keep = sstep(gone * 1.3 - 0.3, gone * 1.3 - 0.12, nd); col = mix(col, bc, keep) + float3(1.0, 0.72, 0.28) * 2.5 * keep * (1.0 - keep) * 4.0;
  }
  // 船化成的金色光点，和越来越亮的水面
  float3 v = b.pos - ro; float2 bs = float2(v.x / -v.z, v.y / -v.z + 0.14) / fl;
  col += motes(uv, bs + float2(0.0, 0.02), 0.5, t, sstep(0.70, 0.84, P) * (1.0 - sstep(0.93, 1.0, P)) * 1.6, float3(1.0, 0.78, 0.35), 3.0);
  col += motes(uv, float2(0.0, 0.1), 1.4, t * 0.6, sstep(0.86, 1.0, P) * 0.7, float3(1.0, 0.85, 0.5), 9.0);
  if (game) {   // 划得越快，船身后的金光越多，水天越亮
    col += motes(uv, bs + float2(0.0, -0.02), 0.35 + 0.3 * E, t * 1.4, E * 1.6 * (1.0 - gone), float3(1.0, 0.80, 0.40), 51.0);
    col += float3(1.0, 0.75, 0.35) * exp(-length((uv - bs) * float2(1.0, 2.2)) * 7.0) * (0.35 * E + 0.25 * kick) * (1.0 - gone);
    col *= 1.0 + 0.22 * E;
    col += rewardBurst(uv, bs + float2(0.0, 0.05), u, float3(1.0, 0.78, 0.35), 2.0);
  }
  return col;
}

// ───────── 11 人鱼珍珠：贝壳里的珍珠交给美人鱼，她带着它游上去，浮出海面看见月亮 ─────────
static float fishShape(float2 q) {   // q：鱼身长约 1，头朝 +x
  float body = length(q * float2(1.0, 2.6)) - 0.42;
  float2 tq = q - float2(-0.52, 0.0); float tail = max(abs(tq.y) - (0.22 - tq.x * 0.9) * 0.5, abs(tq.x) - 0.16);
  return min(body, tail);
}
static float sdSeg(float2 p, float2 a, float2 b) { float2 pa = p - a, ba = b - a; return length(pa - ba * saturate(dot(pa, ba) / dot(ba, ba))); }
// 扇贝的一片壳：铰合处在原点，扇面朝上。ys 压扁（平放的那一片）。返回 (明暗, 珠光, 0, 遮罩)
static float4 shellFan(float2 q, float ys) {
  q.y /= ys; float r = length(q); float th = atan2(q.x, q.y);
  float edge = 1.0 + 0.05 * cos(th * 13.0);
  float m = sstep(edge, edge - 0.04, r) * sstep(1.22, 1.12, abs(th)) * step(0.0, r);
  float rib = 0.5 + 0.5 * cos(th * 13.0);
  float shade = (0.28 + 0.72 * rib * rib) * (0.84 + 0.16 * sin(r * 34.0)) * (0.50 + 0.50 * r);
  return float4(shade, 0.5 + 0.5 * sin(th * 3.0 + r * 5.0), 0.0, m);
}
// 美人鱼的剪影。p：身体自己的坐标，头朝 +y，全身长约 2.4。wave 摆尾的相位，amp 摆幅。
// 返回 (离轮廓的距离, 沿身体的位置 0 头 1 尾尖, 是不是尾鳍, 是不是头发)
static float4 mermaidSD(float2 p, float wave, float amp) {
  float d = 1e3; float sBest = 0.0;
  float2 prev = float2(0.0, 0.55); float2 last = prev, last2 = prev;
  for (int i = 0; i <= 22; i++) {
    float s = float(i) / 22.0;
    float x = (0.015 + 0.20 * s * s) * amp * sin(5.2 * s - wave);
    float2 c = float2(x, 0.55 - s * 1.72);
    float r = mix(0.048, 0.100, sstep(0.0, 0.09, s));                 // 脖子到肩
    r = mix(r, 0.066, sstep(0.10, 0.24, s));                          // 腰
    r = mix(r, 0.098, sstep(0.24, 0.36, s));                          // 胯
    r = mix(r, 0.016, pow(sstep(0.36, 1.0, s), 0.8));                // 尾巴越来越细
    float dd = sdSeg(p, prev, c) - r;
    if (dd < d) { d = dd; sBest = s; }
    last2 = prev; prev = c; last = c;
  }
  float hd = length(p - float2(0.0, 0.70)) - 0.100;                    // 头
  if (hd < d) { d = hd; sBest = 0.0; }
  // 两条手臂往前伸，捧着珍珠
  float ad = min(sdSeg(p, float2(-0.075, 0.50), float2(-0.035, 0.90)), sdSeg(p, float2(0.075, 0.50), float2(0.035, 0.90))) - 0.022;
  if (ad < d) { d = ad; sBest = 0.05; }
  // 尾鳍：两片叶子，跟着尾尖的方向
  float2 dir = normalize(last - last2); float2 nrm = float2(-dir.y, dir.x);
  float fin = 1e3;
  for (int k = 0; k < 2; k++) {
    float sg = k == 0 ? -1.0 : 1.0; float2 fd = normalize(dir + nrm * sg * (0.75 + 0.15 * sin(wave * 1.0 + sg)));
    float2 q = p - last; float al = dot(q, fd); float pe = dot(q, float2(-fd.y, fd.x));
    float w = 0.085 * sin(saturate(al / 0.34) * 3.14159) * (0.6 + 0.4 * saturate(al / 0.34));
    fin = min(fin, max(abs(pe) - w, max(-al, al - 0.34)));
  }
  float isFin = 0.0; if (fin < d) { d = fin; sBest = 1.0; isFin = 1.0; }
  // 头发：从头顶往后飘的一缕，比身体摆得晚半拍
  float hair = 1e3; float2 hp = float2(0.0, 0.72);
  for (int i = 1; i <= 9; i++) {
    float s = float(i) / 9.0;
    float2 c = float2(-0.05 * s + (0.03 + 0.10 * s) * amp * sin(3.6 * s - wave + 0.9) - 0.03, 0.72 - s * 0.62);
    hair = min(hair, sdSeg(p, hp, c) - mix(0.085, 0.022, s)); hp = c;
  }
  float isHair = 0.0; if (hair < d) { d = hair; isHair = 1.0; sBest = 0.0; }
  return float4(d, sBest, isFin, isHair);
}
// 把美人鱼画到 col 上。pos 身体中心，ang 朝向（0 朝上），sc 大小；light 她周围的光色
static float3 drawMermaid(float3 col, float2 uv, float2 pos, float ang, float sc, float wave, float amp, float3 light, float t) {
  float2 p = rot2(uv - pos, -ang) / sc;
  if (abs(p.x) > 0.75 || p.y > 1.05 || p.y < -1.75) return col;
  float4 m = mermaidSD(p, wave, amp);
  float a = sstep(0.012, -0.012, m.x);
  if (a <= 0.0) return col;
  float3 body = float3(0.004, 0.022, 0.040) + light * 0.05;
  // 尾巴上的鳞：一层若隐若现的珠光
  float tail = sstep(0.34, 0.46, m.y) * (1.0 - m.w);
  float2 sq = float2(p.x * 46.0, p.y * 30.0 + 0.5 * floor(p.x * 46.0));
  float scale = sstep(0.25, 0.0, abs(fract(sq.y) - 0.5)) * 0.5 + 0.5;
  float3 irid = mix(float3(0.05, 0.55, 0.60), float3(0.45, 0.32, 0.85), 0.5 + 0.5 * sin(m.y * 9.0 + p.x * 6.0 + t * 0.6));
  body = mix(body, irid * (0.10 + 0.28 * scale) * (0.6 + 1.2 * light.g), tail);
  // 尾鳍是半透明的薄膜，带几道鳍条
  float3 fin = mix(col, float3(0.20, 0.70, 0.80) * (0.5 + light.g), 0.45) * (0.75 + 0.25 * sin(p.x * 120.0 + p.y * 40.0));
  body = mix(body, fin, m.z);
  body = mix(body, float3(0.010, 0.016, 0.040) + light * 0.03, m.w);
  // 逆光的一圈亮边
  body += light * sstep(-0.028, 0.0, m.x) * (0.35 + 0.65 * sstep(-0.2, 0.6, p.x)) * 0.6;
  return mix(col, body, a);
}
static float3 moonSky(float2 uv, float t, float bright) {
  float2 m0 = float2(0.0, 0.50); float d = length(uv - m0);
  float3 c = mix(float3(0.060, 0.095, 0.220), float3(0.010, 0.020, 0.070), sstep(-0.2, 1.0, uv.y));
  // 星星
  for (int l = 0; l < 2; l++) { float sc = 14.0 + float(l) * 11.0; float2 g = uv * sc; float2 id = floor(g), f = fract(g) - 0.5; float2 h = hash22(id + float(l) * 31.0);
    if (h.x < 0.22) c += float3(0.8, 0.88, 1.0) * exp(-dot(f - (h - 0.5) * 0.7, f - (h - 0.5) * 0.7) * 900.0) * (0.35 + 0.65 * sin(t * (1.0 + 2.0 * h.y) + h.x * 40.0)) * sstep(0.26, 0.5, d) * 0.9; }
  // 薄云被月光照亮
  float cl = sstep(0.45, 0.85, fbm(float2(uv.x * 1.6 + t * 0.012, uv.y * 5.0 + 3.0)));
  c += float3(0.30, 0.36, 0.52) * cl * exp(-d * 1.6) * 0.5;
  // 月亮和月晕
  float disc = sstep(0.202, 0.196, d);
  float maria = sstep(0.30, 0.72, fbm((uv - m0) * 4.2 + 2.0));
  c = mix(c, float3(1.0, 0.965, 0.86) * (0.52 + 0.28 * bright) * (0.62 + 0.42 * maria) * (0.74 + 0.26 * sstep(0.2, 0.02, d)), disc);
  c += float3(0.55, 0.68, 1.0) * (exp(-d * 3.0) * 0.16 + exp(-max(d - 0.2, 0.0) * 16.0) * 0.22) * (0.7 + 0.5 * bright);
  return c;
}
static float3 sceneRelDeepAbove(float2 uv, Uniforms u, float a) {
  float t = u.time; float hy = -0.20; float2 m0 = float2(0.0, 0.50);
  float give = sstep(0.34, 0.66, a);                                   // 珍珠升上去，融进月亮
  float3 col;
  if (uv.y > hy) {
    col = moonSky(uv, t, give);
    col += float3(0.22, 0.32, 0.60) * exp(-(uv.y - hy) * 9.0) * 0.12;  // 海平线上的一层雾光
  } else {
    float dpt = hy - uv.y; float z = 1.0 / (dpt + 0.035);
    float2 wq = float2(uv.x * z * 0.9, z * 0.55);
    float wav = noise(wq * float2(1.4, 3.0) + float2(t * 0.25, t * 0.5)) + 0.5 * noise(wq * float2(4.0, 9.0) - float2(0.0, t * 0.9));
    col = mix(float3(0.008, 0.022, 0.060), float3(0.030, 0.070, 0.150), sstep(0.5, 0.0, dpt)) * (0.75 + 0.35 * wav);
    // 月光在水面铺出来的一条路：碎成一片片跳动的亮斑
    float px = uv.x / (0.045 + dpt * 0.30); float path = exp(-px * px);
    float gl = pow(saturate(noise(float2(uv.x * 34.0 + sin(z * 3.0 + t) * 1.2, z * 11.0 + t * 1.4)) * 0.75 + noise(float2(uv.x * 80.0, z * 27.0 - t * 2.2)) * 0.6 - 0.50), 2.6) * 3.0 * (0.35 + 0.65 * exp(-dpt * 2.2));
    col += float3(1.0, 0.95, 0.82) * gl * path * (1.1 + 0.7 * give) * sstep(0.0, 0.03, dpt);
    col += float3(0.45, 0.60, 0.90) * path * 0.10 * exp(-dpt * 2.0);
  }
  // 她浮出来，把珍珠举向月亮；然后一个转身潜回去，尾鳍在水面上翻一下
  float up = sstep(0.0, 0.26, a) * (1.0 - sstep(0.62, 0.84, a));
  float2 base = float2(0.0, hy - 0.36 + 0.34 * up);
  float2 pearl = mix(base + float2(0.0, 0.405), m0, give * give);
  if (up > 0.0) {
    float2 p = (uv - base) / 0.36;
    float d = length(p - float2(0.0, 0.70)) - 0.085;
    d = min(d, sdSeg(p, float2(0.0, 0.62), float2(0.0, 0.54)) - 0.032);
    d = min(d, sdSeg(p, float2(-0.080, 0.50), float2(0.080, 0.50)) - 0.042);
    d = min(d, sdSeg(p, float2(0.0, 0.48), float2(0.0, 0.18)) - mix(0.058, 0.086, saturate((p.y - 0.18) / 0.30)));
    d = min(d, sdSeg(p, float2(0.0, 0.18), float2(0.0, -0.45)) - mix(0.100, 0.058, saturate((p.y + 0.45) / 0.63)));
    for (int k = 0; k < 2; k++) { float sg = k == 0 ? -1.0 : 1.0;
      d = min(d, sdSeg(p, float2(sg * 0.115, 0.50), float2(sg * 0.150, 0.80)) - 0.026);
      d = min(d, sdSeg(p, float2(sg * 0.150, 0.80), float2(sg * 0.030, 1.08)) - 0.021); }
    float hair = 1e3; float2 hp = float2(-0.02, 0.74);
    for (int i = 1; i <= 7; i++) { float s = float(i) / 7.0; float2 c = float2(-0.03 - 0.07 * s + 0.035 * sin(s * 5.0 + t * 0.9) * s, 0.74 - s * 0.66); hair = min(hair, sdSeg(p, hp, c) - mix(0.088, 0.030, s)); hp = c; }
    d = min(d, hair);
    float m = sstep(0.010, -0.010, d) * step(hy, uv.y);
    float3 sil = float3(0.006, 0.012, 0.035) + float3(1.0, 0.95, 0.85) * sstep(-0.022, 0.0, d) * 0.42;
    col = mix(col, sil, m);
  }
  float flip = sstep(0.74, 0.86, a) * (1.0 - sstep(0.90, 1.0, a));
  if (flip > 0.0) {
    float k = sstep(0.74, 1.0, a); float2 fc = float2(0.05, hy + 0.13 * sin(k * 3.14159) - 0.03);
    float2 p = rot2(uv - fc, 0.35 - k * 0.8) / 0.15; float fin = 1e3;
    for (int s2 = 0; s2 < 2; s2++) { float sg = s2 == 0 ? -1.0 : 1.0; float2 q2 = p - float2(0.0, 0.05); q2.y += 0.55 * q2.x * q2.x; float2 fd = normalize(float2(sg * 0.96, 0.28)); float al = dot(q2, fd), pe = dot(q2, float2(-fd.y, fd.x));
      fin = min(fin, max(abs(pe) - 0.20 * pow(sin(saturate(al / 1.15) * 3.14159), 0.7) * (1.0 - 0.45 * saturate(al / 1.15)), max(-al, al - 1.15))); }
    fin = min(fin, sdSeg(p, float2(0.0, 0.08), float2(0.0, -0.9)) - mix(0.09, 0.16, saturate(-p.y / 0.9)));
    float3 sil = float3(0.006, 0.014, 0.040) + float3(1.0, 0.95, 0.85) * sstep(-0.03, 0.0, fin) * 0.3;
    col = mix(col, sil, sstep(0.02, -0.02, fin) * step(hy, uv.y) * flip);
  }
  // 出水、入水的水圈和溅起来的水珠
  for (int i = 0; i < 2; i++) {
    float st = i == 0 ? 0.02 : 0.78; float age = (a - st) * 9.0;
    if (age > 0.0 && age < 3.5) { float2 q = (uv - float2(0.0, hy - 0.035)) * float2(1.0, 5.5);
      col += float3(0.85, 0.92, 1.0) * exp(-abs(length(q) - age * 0.16) * 42.0) * exp(-age * 0.9) * 0.9 * step(uv.y, hy);
      for (int k = 0; k < 10; k++) { float fk = float(k); float2 h = hash22(float2(fk * 3.1 + float(i) * 9.0, 5.0)); float tt2 = age * 0.42;
        float2 sp = float2((h.x - 0.5) * 0.5 * tt2 * 2.0, hy + (0.9 + 0.8 * h.y) * tt2 - 1.9 * tt2 * tt2);
        col += float3(0.9, 0.95, 1.0) * star(uv - sp, 0.007 + 0.004 * h.y) * step(hy, sp.y) * exp(-age * 0.8) * 1.4; } }
  }
  // 珍珠：举过头顶，升起来，融进月亮
  float pa = sstep(0.04, 0.2, a) * (1.0 - sstep(0.60, 0.70, a));
  col += float3(0.85, 0.96, 1.0) * (sstep(0.022, 0.016, length(uv - pearl)) * 2.6 + exp(-length(uv - pearl) * 22.0) * 0.9) * pa;
  col += float3(1.0, 0.97, 0.88) * exp(-length(uv - m0) * 4.0) * 0.30 * give * (1.0 - 0.6 * sstep(0.8, 1.0, a));
  // 月亮旁边多了一颗星，是那粒珍珠
  col += float3(0.85, 0.95, 1.0) * star(uv - float2(0.28, 0.70), 0.016) * sstep(0.62, 0.8, a) * (1.3 + 0.5 * sin(t * 2.2));
  col += motes(uv, float2(0.0, -0.1), 1.5, t * 0.5, sstep(0.5, 1.0, a) * 0.6, float3(0.8, 0.9, 1.0), 41.0);
  col *= 1.0 - 0.30 * sstep(0.5, 1.3, length(uv * float2(1.5, 1.0)));
  return col;
}
static float3 sceneRelDeep(float2 uv, Uniforms u) {
  float t = u.time; bool game = gameOn(u);
  float P = game ? gameP(u, 0.30, 0.86, 1.0) : relP(u); bool run = u.prog >= 0.0 || game;
  float E = game ? u.game.z : 0.0; float kick = game ? exp(-u.game.w * 5.0) : 0.0;
  float cut = 0.86;
  float flash = P < cut ? exp(-(cut - P) * 70.0) : exp(-(P - cut) * 120.0);
  if (P >= cut) return sceneRelDeepAbove(uv, u, (P - cut) / (1.0 - cut)) + float3(0.75, 0.9, 1.0) * flash * 1.6;
  float fl = 0.55;
  float asc = sstep(0.30, 0.84, P);                       // 往上游了多少
  float near = sstep(0.55, 1.0, asc);                     // 快到海面了
  float2 ub = uv + float2(0.0, asc * 2.7);                // 贴着海底的那套坐标：海底往下退
  float lift = 0.85 + 0.75 * asc + 0.25 * E;
  float3 top = mix(float3(0.02, 0.20, 0.38), float3(0.10, 0.36, 0.56), near), mid = mix(float3(0.010, 0.085, 0.20), float3(0.02, 0.15, 0.30), asc), bot = float3(0.003, 0.025, 0.075);
  float3 water = (uv.y > 0.0 ? mix(mid, top, sstep(0.0, 1.1, uv.y)) : mix(mid, bot, sstep(0.0, -1.0, uv.y))) * lift;
  float3 col = water;
  // 海面透下来的光：顶上一团柔光，加几道光柱；越往上越亮
  float2 src = float2(0.10, 1.7 - 0.55 * near); float2 dv = uv - src; float a = atan2(dv.x, -dv.y);
  float sh = noise(float2(a * 11.0 + t * 0.05, 1.0)) * 0.6 + noise(float2(a * 27.0 - t * 0.07, 4.0)) * 0.4;
  sh = sstep(0.42, 0.85, sh);
  float fall = exp(-length(dv) * 0.95) * 3.2;
  col += float3(0.30, 0.75, 0.90) * sh * fall * (0.11 + 0.10 * asc) * lift;
  col += float3(0.20, 0.60, 0.80) * exp(-length(dv * float2(0.6, 1.0)) * 1.6) * (0.4 + 0.4 * near);
  // 从水下看海面：一层晃动的亮纹，中间是月亮化开的一团光
  if (near > 0.0) {
    float cy = mix(1.9, 0.62, near); float dy = uv.y - cy;
    if (dy > -0.25) {
      float k = sstep(-0.25, 0.05, dy);
      float rip = noise(float2(uv.x * 5.0 + t * 0.3, dy * 16.0 - t * 0.6)) * 0.6 + noise(float2(uv.x * 13.0 - t * 0.4, dy * 30.0 + t)) * 0.4;
      float2 md = float2(uv.x - 0.02 + 0.03 * sin(t * 1.3 + dy * 20.0), (dy - 0.14) * 1.5);
      col = mix(col, float3(0.10, 0.30, 0.46) * (0.6 + 0.9 * rip), k * 0.8);
      col += float3(0.95, 0.98, 0.90) * exp(-dot(md, md) * 30.0) * (1.2 + 0.8 * rip) * k;
      col += float3(0.6, 0.85, 1.0) * sstep(0.62, 0.9, rip) * k * 0.35;
    }
  }
  // 远处的礁石剪影
  float reef = 0.0 + 0.16 * fbm(float2(ub.x * 2.4 + 7.0, 2.0)) + 0.03 * noise(float2(ub.x * 15.0, 5.0)) - 0.05;
  col = mix(col, water * 0.62, sstep(reef + 0.03, reef - 0.03, ub.y) * 0.6);
  // 海底：起伏的沙地，上面有焦散
  float3 rdb = normalize(float3(ub.x * fl, ub.y * fl, -1.0));
  if (rdb.y < -0.01) {
    float tp = -1.1 / rdb.y; float3 p = rdb * tp; float2 q = p.xz;
    float dune = fbm(q * 0.7 + 3.0); float rip = sin((q.y + dune * 2.0) * 9.0 + fbm(q * 2.0) * 4.0);
    float ca = caustic(q * 1.7 + float2(0.0, t * 0.05), t * 0.5);
    float3 sand = float3(0.05, 0.16, 0.22) * (0.55 + 0.5 * dune + 0.08 * rip) + float3(0.35, 0.8, 0.85) * ca * 0.22;
    col = mix(sand * lift, col, 1.0 - exp(-tp * 0.16));
  }
  // 远处游过的一群鱼
  for (int i = 0; i < 12; i++) {
    float fi = float(i); float2 h = hash22(float2(fi * 2.3, 9.0));
    float cx = fract(t * 0.022 + 0.25) * 2.0 - 1.0 + (h.x - 0.5) * 0.42;
    float2 p = float2(cx + 0.02 * sin(t + fi), 0.42 + (h.y - 0.5) * 0.22 + 0.02 * sin(t * 0.7 + fi * 1.3) - asc * 1.6);
    float sz = 0.028 + 0.014 * h.x;
    float2 q = (uv - p) / sz; q.y += 0.08 * sin(q.x * 4.0 - t * 8.0 + fi);
    col = mix(col, water * 0.35, sstep(0.08, -0.06, fishShape(q)) * 0.6);
  }
  // 沙地上张开的扇贝，里面一粒发光的珍珠
  float2 s0 = float2(0.03, -0.50); float SR = 0.17;
  float take = sstep(0.22, 0.30, P);                       // 珍珠被捧走
  float pg = (run ? 1.0 : 0.55) * (0.85 + 0.15 * sin(t * 1.7));
  float2 sq = (ub - s0) / SR;
  if (abs(sq.x) < 1.3 && sq.y > -0.75 && sq.y < 1.25) {
    float2 pl = float2(0.0, 0.16); float pd = length(sq - pl);
    float3 nacre = float3(0.75, 0.95, 1.0) * exp(-pd * 2.6) * 0.62 * pg * (1.0 - take);
    float4 f1 = shellFan(sq, 1.0);                          // 立着的那片：朝着我们的是珠光的内面
    float3 c1 = mix(float3(0.62, 0.34, 0.46), float3(1.0, 0.86, 0.84), f1.x) * (float3(0.30, 0.46, 0.56) * lift + nacre);
    c1 += (pal(f1.y * 0.35 + 0.55) * 0.5 + 0.5) * 0.10 * f1.x * (lift + nacre.g);
    col = mix(col, c1, f1.w);
    float4 f2 = shellFan(float2(sq.x, -sq.y + 0.02), 0.42); // 平放的那片
    float3 c2 = mix(float3(0.52, 0.28, 0.40), float3(0.98, 0.80, 0.80), f2.x) * (float3(0.24, 0.38, 0.48) * lift + nacre * 1.3);
    col = mix(col, c2, f2.w);
    col = mix(col, float3(0.9, 0.7, 0.7) * (0.25 * lift + nacre), sstep(0.11, 0.07, length(sq * float2(1.0, 2.4))));   // 铰合处
  }
  // 美人鱼：从右下游过来，捧起珍珠，往上游
  float come = sstep(0.08, 0.26, P);
  float sway = 0.03 * sin(t * 0.45);
  float2 mp = mix(float2(1.05, -1.05), float2(0.10, -0.52), come * come * (3.0 - 2.0 * come));
  mp = mix(mp, float2(sway, -0.10 + 0.05 * E + 0.03 * kick), sstep(0.26, 0.44, P));
  mp.y -= 0.10 * near;
  float ang = mix(0.95, 0.10 * sin(t * 0.5), sstep(0.20, 0.36, P));
  float msc = 0.37;
  float wave = t * (2.6 + 1.4 * asc) + (game ? u.game.y * 46.0 : 0.0); float amp = 0.75 + 0.35 * asc + 0.6 * E + 0.3 * kick;
  float2 fwd = float2(-sin(ang), cos(ang));
  float2 hand = mp + fwd * 0.90 * msc;
  float2 pearl = mix(s0 + float2(0.0, 0.16 * SR) - float2(0.0, asc * 2.7), hand, take);
  float3 mlight = float3(0.30, 0.75, 0.90) * (0.35 + 0.6 * asc + 0.5 * E) + float3(0.75, 0.95, 1.0) * take * 0.25;
  if (P > 0.06) {
    // 她身后拖着的一道光和一串气泡：游得越快越亮
    float tr = (0.15 + 0.85 * asc) * (game ? 0.35 + 1.4 * E : 0.7);
    float2 tq = uv - (mp - fwd * 0.55); float along = -dot(tq, fwd), side = dot(tq, float2(fwd.y, -fwd.x));
    col += float3(0.35, 0.85, 1.0) * exp(-side * side * (90.0 + 60.0 * along)) * exp(-max(along, 0.0) * 1.6) * sstep(-0.05, 0.30, along) * 0.22 * tr;
    for (int i = 0; i < 14; i++) {
      float fi = float(i); float2 h = hash22(float2(fi * 3.9, 57.0)); float life = fract(t * (0.35 + 0.3 * h.y) + h.x + P * 9.0);
      float2 bp = mp - fwd * (0.45 + life * (0.6 + 0.5 * h.y)) + float2(-fwd.y, fwd.x) * (h.x - 0.5) * (0.10 + 0.25 * life);
      col += float3(0.7, 0.95, 1.0) * star(uv - bp, 0.006 + 0.006 * h.y) * sin(life * 3.14159) * tr * 1.2;
    }
    col = drawMermaid(col, uv, mp, ang, msc, wave, amp, mlight, t);
  }
  // 珍珠
  { float pd = length(uv - pearl); float pr = 0.021;
    float3 n = sphN(uv, pearl, pr);
    float3 pc = float3(0.82, 0.94, 1.0) * (0.9 + 1.5 * pow(n.z, 2.0)) + (pal(n.x * 0.4 + n.y * 0.3 + 0.6) * 0.5 + 0.5) * 0.35;
    col = mix(col, pc * (0.8 + 1.4 * pg), sstep(pr, pr - 0.004, pd));
    col += float3(0.70, 0.93, 1.0) * (exp(-pd * 13.0) * 0.55 + exp(-pd * 4.0) * 0.12) * pg * (1.0 + 1.2 * E);
    col += float3(0.8, 0.95, 1.0) * star(uv - pearl, 0.020) * pg * (0.5 + 0.5 * sin(t * 2.3)) * 0.8; }
  // 水里的悬浮物，被光柱照到的更亮；往上游的时候它们往下掠过去
  for (int l = 0; l < 3; l++) {
    float fl2 = float(l); float sc = 7.0 + fl2 * 6.0;
    float2 p = float2(uv.x * sc + fl2 * 3.0 + t * 0.03 * (1.0 + fl2), (uv.y - t * 0.012 * (1.0 + fl2) + asc * (2.0 + fl2)) * sc);
    float2 id = floor(p), f = fract(p) - 0.5; float2 h = hash22(id + fl2 * 13.0);
    float d = length(f - (h - 0.5) * 0.7);
    col += float3(0.55, 0.85, 0.95) * exp(-d * d * (500.0 - fl2 * 120.0)) * (0.10 + 0.5 * sh * fall * 0.3 + 0.25 * E) * step(h.x, 0.6) * (0.5 + 0.5 * sin(t * 1.5 + h.y * 30.0));
  }
  // 海草：前景的暗影，随水摆动
  for (int l = 0; l < 2; l++) {
    float fl2 = float(l); float sc = 8.0 - fl2 * 3.5;
    float cell = floor(ub.x * sc + fl2 * 0.5); float2 h = hash22(float2(cell, fl2 * 7.0 + 1.0));
    if (abs(cell + 0.5 - fl2 * 0.5) < 1.2 - fl2 * 0.4) continue;                   // 中间留给贝壳
    float baseY = -1.02; float hgt = (0.16 + 0.34 * h.x) * (1.0 + fl2 * 0.7);
    float v = (ub.y - baseY) / hgt;
    float cxp = (cell + 0.5 - fl2 * 0.5 + (h.y - 0.5) * 0.6) / sc + 0.05 * sin(t * 0.7 + cell * 1.7 + v * 2.5) * v * v;
    float wdt = (0.010 + 0.008 * h.y) * (1.0 + fl2 * 1.2) * (1.0 - v * 0.85);
    float soft = 0.004 + 0.006 * fl2;
    float m = sstep(wdt + soft, wdt - soft, abs(ub.x - cxp)) * step(0.0, v) * sstep(1.0, 0.9, v);
    col = mix(col, mix(float3(0.006, 0.05, 0.07), float3(0.003, 0.025, 0.04), fl2) * (0.6 + 0.8 * v), m * (0.8 + 0.15 * fl2));
  }
  // 几串气泡
  for (int l = 0; l < 2; l++) {
    float fl2 = float(l); float sc = 9.0 + fl2 * 7.0;
    float2 p = float2(uv.x * sc + fl2 * 3.0, (uv.y - t * (0.07 + 0.05 * fl2) + asc * 2.4) * sc);
    float2 id = floor(p), f = fract(p) - 0.5; float2 h = hash22(id + fl2 * 13.0);
    if (h.x < 0.05 + 0.05 * E) { float r = 0.10 + 0.16 * h.y; float2 c = (h - 0.5) * 0.4 + float2(0.08 * sin(t * 2.0 + h.x * 30.0), 0.0); float d = length(f - c); float2 hl = f - c + float2(r * 0.4, -r * 0.4);
      col += float3(0.6, 0.9, 1.0) * (sstep(0.035, 0.0, abs(d - r)) * (0.18 + 0.25 * saturate((f.y - c.y) / r)) + exp(-dot(hl, hl) * 700.0) * 0.6) / (1.0 + fl2 * 0.5); }
  }
  col += float3(0.6, 0.92, 1.0) * tapRing(uv, u) * 0.9;
  col += motes(uv, float2(0.0, -0.3), 1.6, t * 0.5, 0.05 + 0.5 * E, float3(0.6, 0.9, 1.0), 17.0);
  col *= 1.0 - 0.35 * sstep(0.35, 1.2, length(uv * float2(1.6, 1.0)));
  return col + float3(0.75, 0.9, 1.0) * flash * 1.6;
}

// ───────── 8 热气球 ─────────
static float4 cloudLayer(float2 uv, float sc, float scroll, float t, float seed, float cover) {
  float2 q = float2(uv.x * sc + seed + t * 0.008 * sc, (uv.y + scroll) * sc * 1.7);
  float d = fbm(q) + 0.12 * fbm(q * 3.1 + 5.0) - 0.06, d2 = fbm(q + float2(0.03, 0.12));
  float m = sstep(cover, cover + 0.07, d);
  float lit = saturate((d - d2) * 6.0 + 0.55);
  float3 c = mix(float3(0.62, 0.52, 0.80), float3(1.0, 0.96, 0.94), lit);
  c = mix(c, float3(1.0, 0.80, 0.78), 0.25 * (1.0 - lit));
  return float4(c, m);
}
static float3 sceneRelBalloon(float2 uv, Uniforms u) {
  float t = u.time; bool game = gameOn(u);
  // 小游戏：前四分之一把球囊吹鼓，然后升空
  float P = game ? (u.game2.x >= 0.0 ? mix(0.60, 1.0, u.game2.x) : mix(0.13, 0.60, sstep(0.25, 1.0, u.game.y))) : relP(u);
  float E = game ? u.game.z : 0.0; float kick = game ? exp(-u.game.w * 6.0) : 0.0;
  float infl = game && u.game2.x < 0.0 ? sstep(0.0, 0.25, u.game.y) : 1.0;
  float rise = sstep(0.14, 0.92, P), far = sstep(0.55, 0.96, P);
  float3 col = mix(float3(1.0, 0.62, 0.66), float3(0.30, 0.48, 0.92), sstep(-0.9, 0.8, uv.y));
  col = mix(col, float3(0.70, 0.56, 0.95), 0.30 * sstep(-0.3, 0.3, uv.y) * (1.0 - sstep(0.3, 1.0, uv.y))); col = mix(col, float3(0.30, 0.48, 0.92), 0.25 * rise);
  col *= 0.60;
  float2 sp = float2(0.30, 0.78); col += float3(1.0, 0.85, 0.7) * exp(-length(uv - sp) * 2.2) * 0.35;
  // 彩虹：上升时从上方落到身后
  float2 rc = float2(0.2, 0.9 - rise * 2.3); float rr = length(uv - rc);
  float bandv = (rr - 0.62) / 0.11;
  if (bandv > 0.0 && bandv < 1.0) col = mix(col, (pal(0.02 + bandv * 0.75) * 0.5 + 0.5) * 0.85, sin(bandv * 3.14159) * 0.55 * sstep(-0.1, 0.25, uv.y - rc.y));
  // 远处两层云
  for (int l = 0; l < 2; l++) { float4 c = cloudLayer(uv, 1.5 + float(l) * 0.6, rise * (0.9 + float(l) * 0.7), t, float(l) * 9.0, 0.60 - float(l) * 0.03); col = mix(col, c.rgb * (0.70 + 0.10 * float(l)), c.a * (0.6 + 0.25 * float(l))); }
  // 热气球
  float2 c0 = float2(0.03 * sin(t * 0.5), -0.20 + 0.45 * sstep(0.10, 0.6, P) + 0.42 * far);
  float size = 0.30 * (1.0 - 0.74 * far) * (0.62 + 0.38 * infl) * (1.0 + 0.045 * kick); float alpha = 1.0 - sstep(0.88, 0.98, P);
  c0.y -= 0.16 * (1.0 - infl);
  float2 q = (uv - c0) / size; q = rot2(q, 0.04 * sin(t * 0.6));
  float basketY = -1.78; float2 bq = q - float2(0.0, basketY);
  if (alpha > 0.0) {
    // 绳子和吊篮
    for (int k = 0; k < 2; k++) { float sx = k == 0 ? -1.0 : 1.0; float ly = saturate((q.y + 1.66) / 0.22); float lx = sx * mix(0.13, 0.15, ly);
      col = mix(col, float3(0.35, 0.25, 0.18), sstep(0.012, 0.004, abs(q.x - lx)) * step(-1.66, q.y) * step(q.y, -1.44) * alpha); }
    float bsd = max(abs(bq.x) - 0.15 + 0.03 * (-bq.y), abs(bq.y) - 0.11);
    float3 bk = float3(0.52, 0.36, 0.22) * (0.75 + 0.25 * sin(bq.x * 90.0) * sin(bq.y * 90.0)) * (0.7 + 0.5 * (bq.x + 0.15) * 2.0);
    col = mix(col, bk, sstep(0.01, -0.01, bsd) * alpha);
    // 火焰
    float flame = game ? (0.35 + 1.5 * E + 0.9 * kick) * (1.0 - far) : 0.5 + 0.5 * rise * (1.0 - far);
    float2 fq = q - float2(0.0, -1.52); float fs = 1.0 / (0.8 + 0.5 * min(flame, 2.0)); col += float3(1.0, 0.62, 0.2) * exp(-dot(fq * float2(3.0, 1.6 * fs), fq * float2(3.0, 1.6 * fs)) * 22.0) * (0.8 + 0.3 * sin(t * 13.0)) * flame * 1.6 * alpha;
    // 球囊
    float w = q.y >= 0.0 ? sqrt(max(1.0 - q.y * q.y, 0.0)) : pow(max(1.0 - pow(-q.y / 1.45, 1.8), 0.0), 0.7);
    w = max(w, q.y > -1.45 ? 0.15 : 0.0);
    w *= mix(0.62, 1.0, infl) * (1.0 + 0.03 * kick);
    if (q.y < 1.0 && q.y > -1.45 && abs(q.x) < w + 0.03) {
      float nx = clamp(q.x / w, -1.0, 1.0); float nz = sqrt(1.0 - nx * nx); float ny = q.y >= 0.0 ? q.y : -0.4 - 0.2 * (-q.y / 1.45);
      float3 n = normalize(float3(nx * sqrt(max(1.0 - ny * ny * (q.y >= 0.0 ? 1.0 : 0.0), 0.05)), ny, nz * sqrt(max(1.0 - ny * ny * (q.y >= 0.0 ? 1.0 : 0.0), 0.05))));
      float phi = asin(nx) / 3.14159 * 8.0 + t * 0.12; float gi = floor(phi); float gf = fract(phi);
      int ci = int(gi - 4.0 * floor(gi / 4.0));
      float3 gc = ci == 0 ? float3(1.0, 0.50, 0.62) : (ci == 1 ? float3(1.0, 0.93, 0.82) : (ci == 2 ? float3(0.62, 0.50, 1.0) : float3(0.45, 0.74, 1.0)));
      gc = mix(gc, float3(1.0, 0.86, 0.5), sstep(0.06, 0.03, abs(q.y - 0.02)) * 0.8);                  // 腰上的一圈金边
      gc *= 1.0 - 0.22 * pow(abs(gf - 0.5) * 2.0, 5.0);                                                 // 每一瓣之间的缝
      float3 L = normalize(float3(0.45, 0.6, 0.62));
      float dif = saturate(dot(n, L) * 0.6 + 0.4);
      float3 bc = gc * (0.22 + 0.66 * dif * dif) + float3(1.0, 0.7, 0.4) * 0.35 * flame * sstep(-0.3, -1.45, q.y) * (1.0 - far);
      bc += float3(1.0, 0.98, 0.95) * pow(saturate(dot(reflect(float3(0.0, 0.0, -1.0), n), L)), 14.0) * 0.5;
      bc += float3(0.7, 0.8, 1.0) * pow(1.0 - nz, 3.0) * 0.25;
      bc = mix(bc, col, far * 0.35);                                                                   // 远了就融进空气里
      col = mix(col, bc, sstep(0.02, -0.02, abs(q.x) - w) * alpha);
    }
  }
  // 烦恼：几朵小乌云，被吸进吊篮
  for (int i = 0; i < 4; i++) {
    float fi = float(i); float k = sstep(0.02 + fi * 0.03, 0.13 + fi * 0.03, P);
    if (k >= 1.0) continue;
    float2 home = float2(fi < 2.0 ? -0.26 : 0.27, 0.42 - fmod(fi, 2.0) * 0.26 + (fi < 2.0 ? 0.0 : -0.1)) + float2(0.015 * sin(t * 0.9 + fi * 2.0), 0.015 * sin(t * 1.1 + fi));
    float2 p = mix(home, c0 + float2(0.0, basketY * size), k * k); float r = mix(0.075, 0.012, k);
    float dd = min(length(uv - p) - r, min(length(uv - p - float2(r * 0.9, -r * 0.2)) - r * 0.75, length(uv - p + float2(r * 0.9, r * 0.15)) - r * 0.7));
    float3 wc = mix(float3(0.26, 0.22, 0.36), float3(0.45, 0.40, 0.58), sstep(-r, r, uv.y - p.y));
    col = mix(col, wc, sstep(0.012, -0.012, dd) * (1.0 - k * 0.7));
  }
  // 近处一层云，气球会从它后面穿过
  float4 nc = cloudLayer(uv, 1.1, rise * 2.6, t, 21.0, 0.63); col = mix(col, nc.rgb * 0.86, nc.a * 0.9 * sstep(0.0, 0.12, rise) * (1.0 - sstep(0.88, 1.0, rise)));
  col += motes(uv, c0 + float2(0.0, -0.5 * size), 0.3, t, rise * (1.0 - far) * 0.6, float3(1.0, 0.9, 0.95), 5.0);
  col += motes(uv, float2(0.0, 0.2), 1.3, t * 0.6, sstep(0.9, 1.0, P) * 0.6, float3(1.0, 0.92, 0.96), 12.0);
  if (game) {
    // 打得越快：风从身边掠过的细线、吊篮下撒出来的光
    for (int i = 0; i < 14; i++) { float fi = float(i); float2 h = hash22(float2(fi * 5.1, 77.0));
      float y = 1.3 - fract(h.y + t * (0.5 + 1.2 * E) * (0.6 + 0.6 * h.x)) * 2.6; float dx = uv.x - (h.x - 0.5) * 1.1; float dy = uv.y - y;
      col += float3(1.0, 0.95, 1.0) * exp(-dx * dx * 22000.0) * exp(-dy * dy * 55.0) * E * E * 0.30 * sstep(0.3, 0.5, u.game.y + step(0.0, u.game2.x)); }
    col += motes(uv, c0 + float2(0.0, -0.55 * size), 0.35, t * 1.5, E * 1.5 * alpha, float3(1.0, 0.85, 0.6), 63.0);
    col *= 1.0 + 0.15 * E;
    col += float3(1.0, 0.9, 0.8) * tapRing(uv, u) * 0.6;
    col += rewardBurst(uv, c0, u, float3(1.0, 0.72, 0.85), 4.0);
    col += rewardBurst(uv, c0 + float2(0.18, 0.12), u, float3(0.70, 0.75, 1.0), 9.0) * 0.7;
  }
  return col;
}

// ───────── 9 天使之箭 ─────────
static float sdLink(float3 p) {   // 一节链环，外接球半径约 1
  float3 q = float3(max(abs(p.x) - 0.29, 0.0), p.y, p.z);
  return length(float2(length(q.xy) - 0.52, q.z)) - 0.15;
}
static float2 mapL(float3 p, Act a) {
  float2 r = float2(1e5, -1.0);
  for (int i = 0; i < a.n; i++) { float d = sdLink(toLocal(p - a.pos[i], a.rx[i], a.ry[i]) / a.sc[i]) * a.sc[i]; if (d < r.x) r = float2(d, float(i)); }
  return r;
}
static float featherShape(float2 q) { q.x = abs(q.x); return length(float2(q.x * 3.6, q.y)) - 0.5 + 0.18 * abs(q.y); }
static float3 heaven(float3 d, float k) {   // 链环映出来的环境：上亮下暗，带一块暖光
  float3 c = mix(float3(0.10, 0.10, 0.13), float3(0.95, 0.90, 0.82), sstep(-0.3, 0.8, d.y));
  c += float3(3.0, 2.6, 2.0) * sstep(0.88, 0.96, dot(d, normalize(float3(-0.3, 0.8, 0.5))));
  return c * (0.7 + 0.5 * k);
}
static float3 sceneRelArrow(float2 uv, Uniforms u) {
  float t = u.time; bool game = gameOn(u);
  float P = game ? (u.game2.x >= 0.0 ? mix(0.115, 0.80, u.game2.x) : mix(0.03, 0.11, u.game.y)) : relP(u);
  float E = game ? u.game.z : 0.0; float kick = game ? exp(-u.game.w * 5.0) : 0.0;
  float hitP = 0.20; float tau = max(P - hitP, 0.0) * u.dur * 0.55; bool hit = P >= hitP;
  float calm = sstep(0.3, 1.0, P);
  float3 col = mix(float3(1.0, 0.74, 0.46), float3(0.42, 0.56, 0.92), sstep(-0.8, 0.95, uv.y));
  col = mix(col, float3(1.0, 0.86, 0.70), 0.35 * sstep(0.5, 0.0, abs(uv.y - 0.1)));
  col *= 0.40 + 0.10 * calm;
  // 天光
  float2 src = float2(0.0, 1.5); float2 dv = uv - src; float a = atan2(dv.x, -dv.y);
  float rays = sstep(0.35, 0.9, noise(float2(a * 9.0 + t * 0.03, 2.0)) * 0.65 + noise(float2(a * 23.0 - t * 0.05, 7.0)) * 0.35);
  col += float3(1.0, 0.90, 0.68) * rays * exp(-length(dv) * 0.8) * (0.30 + 0.30 * calm);
  // 远处一层云
  float4 c0 = cloudLayer(uv + float2(0.3, 0.0), 1.0, 0.0, t * 0.6, 51.0, 0.58);
  col = mix(col, mix(c0.rgb, float3(1.0, 0.94, 0.86), 0.6) * (0.80 + 0.10 * calm), c0.a * 0.28 * sstep(0.2, -0.3, uv.y));
  // 光做的一对翅膀、光环和中间一团柔光
  float2 wc = float2(0.0, 0.42);
  float flap = 0.86 + 0.05 * sin(t * 0.7) + 0.10 * E + 0.07 * kick + 0.12 * sstep(0.0, hitP, P) + (hit ? 0.16 * exp(-tau * 0.9) * cos(tau * 4.0) : 0.0);
  float wl = wingShape(float2(-(uv.x - wc.x) - 0.035, uv.y - wc.y), flap), wr = wingShape(float2((uv.x - wc.x) - 0.035, uv.y - wc.y), flap);
  float wI = 0.30 + 0.18 * calm + 0.55 * E + 0.25 * kick + (hit ? 0.4 * exp(-tau * 1.2) : 0.0);
  col += float3(1.0, 0.95, 0.86) * (wl + wr) * wI;
  float2 bd = (uv - wc - float2(0.0, -0.07)) * float2(9.0, 3.2);
  col += float3(1.0, 0.93, 0.78) * exp(-dot(bd, bd)) * 0.35;
  float hr = abs(length((uv - wc - float2(0.0, 0.17)) * float2(1.0, 3.2)) - 0.075);
  col += float3(1.0, 0.82, 0.42) * exp(-hr * 110.0) * (0.9 + 0.5 * calm);
  col += float3(1.0, 0.94, 0.8) * exp(-length(uv - wc) * 4.0) * (0.10 + 0.14 * sstep(0.0, hitP, P));
  // 锁链（光线步进），断开后每一节各自飞散、化成光
  float3 ro = float3(0.0, 0.0, 5.0); float fl = 0.43; float3 rd = normalize(float3(uv.x * fl, uv.y * fl, -1.0));
  Coins cs; cs.n = 0;
  for (int i = 0; i < 9; i++) {
    float fi = float(i) - 4.0; float3 h = float3(hash11(fi * 3.1 + 20.0), hash11(fi * 5.7 + 3.0), hash11(fi * 9.2 + 7.0));
    float lt = max(tau - abs(fi) * 0.07, 0.0); float k = sstep(0.9, 3.2, lt);
    if (k >= 1.0) continue;
    float3 base = float3(fi * 0.268, -0.25 - 0.10 * (1.0 - fi * fi / 16.0) + 0.008 * sin(t * 1.3 + fi * 0.8), 0.0);
    float3 vel = float3((fi == 0.0 ? (h.x - 0.5) : sign(fi)) * (0.20 + 0.28 * h.x), 0.30 + 0.45 * h.y, (h.z - 0.5) * 0.9);
    float3 pos = base + vel * lt + float3(0.0, -0.20 * lt * lt, 0.0);
    float ax = (fmod(float(i), 2.0) < 0.5 ? 0.0 : 1.5708) + lt * (1.2 + 2.0 * h.y) + 0.04 * sin(t + fi), ay = lt * (1.0 + 2.0 * h.z) * (h.x > 0.5 ? 1.0 : -1.0);
    int n = cs.n; cs.pos[n] = pos; cs.rx[n] = float2(cos(ax), sin(ax)); cs.ry[n] = float2(cos(ay), sin(ay)); cs.sc[n] = 0.205 * (1.0 - k * k); cs.n = n + 1;
  }
  Act act = gather(ro, rd, cs);
  if (act.n > 0) {
    float tt = 0.0; bool found = false;
    for (int i = 0; i < 64; i++) { float d = mapL(ro + rd * tt, act).x; if (d < 0.0015) { found = true; break; } tt += d * 0.9; if (tt > 12.0) break; }
    if (found) {
      float3 p = ro + rd * tt; float2 e = float2(0.002, 0.0);
      float3 n = normalize(float3(mapL(p + e.xyy, act).x - mapL(p - e.xyy, act).x, mapL(p + e.yxy, act).x - mapL(p - e.yxy, act).x, mapL(p + e.yyx, act).x - mapL(p - e.yyx, act).x));
      float ndv = max(dot(-rd, n), 0.0); float3 F0 = float3(0.30, 0.31, 0.36);
      float3 iron = heaven(reflect(rd, n), calm) * (F0 + (float3(1.0) - F0) * pow(1.0 - ndv, 5.0)) * 0.5;
      float glowk = hit ? sstep(0.0, 1.5, tau - abs(p.x) * 0.26) : 0.0;
      if (game && !hit) { float idx = (p.x / 0.268 + 4.5) / 9.0; glowk = sstep(idx - 0.02, idx + 0.10, u.game.y * 1.12) * (0.55 + 0.25 * E + 0.2 * sin(t * 3.0 + p.x * 9.0)); }   // 一节一节被光烧红
      col = mix(iron, float3(1.7, 0.95, 0.20) * (0.5 + 0.5 * ndv) + float3(0.9, 0.8, 0.6) * pow(1.0 - ndv, 3.0), glowk);
    }
  }
  // 箭：在光里凝成，落下来穿过锁链正中
  float2 A = wc + float2(0.0, -0.05), B = float2(0.0, -0.35 / (5.0 * fl));
  col += float3(1.0, 0.88, 0.5) * star(uv - A, 0.03) * sstep(0.03, 0.11, P) * (1.0 - sstep(0.11, 0.15, P)) * 2.2;
  float ap = (P - 0.11) / (hitP - 0.11);
  if (ap > 0.0 && ap < 1.6) {
    float k = ap * ap; float2 dir = normalize(B - A); float2 head = A + (B - A) * k;
    float2 r = uv - head; float al = dot(r, dir), pe = length(r - dir * al);
    float fadeA = ap < 1.0 ? 1.0 : 1.0 - sstep(1.0, 1.6, ap);
    float shaft = exp(-pe * 220.0) * sstep(-0.16, -0.12, al) * step(al, 0.0) * 2.4;
    float trail = exp(-pe * 60.0) * exp(al * 5.0) * step(al, 0.0) * 0.8;
    float tip = sstep(0.014, 0.0, pe - (0.012 - al) * 0.5) * step(-0.024, al) * step(al, 0.012) * 3.0;
    col += float3(1.0, 0.84, 0.42) * (shaft + trail + tip + star(r, 0.014) * 1.6) * fadeA;
  }
  if (hit) {
    float fl2 = exp(-tau * 2.4); float r = length(uv - B);
    col += float3(1.0, 0.90, 0.62) * (exp(-r * 4.0) * 1.3 + exp(-abs(r - tau * 0.55) * 26.0) * 0.7) * fl2;
    for (int i = 0; i < 26; i++) {
      float fi = float(i); float2 h = hash22(float2(fi * 2.1, 44.0)); float an = fi * 0.61; float life = saturate(tau / (1.6 + 2.2 * h.y));
      float2 p = B + float2((h.x - 0.5) * 0.9, 0.0) + float2(cos(an), sin(an) * 0.6 + 0.35) * life * (0.25 + 0.45 * h.x);
      col += float3(1.0, 0.82, 0.42) * star(uv - p, 0.010 + 0.006 * h.y) * sin(life * 3.14159) * 1.3 * step(life, 0.999);
    }
  }
  // 脚下的云海和缓缓落下的羽毛
  float4 c1 = cloudLayer(uv, 1.3, 0.0, t, 33.0, 0.46);
  col = mix(col, mix(c1.rgb, float3(1.0, 0.94, 0.84), 0.6) * (0.90 + 0.10 * calm), c1.a * sstep(-0.30, -0.85, uv.y) * 0.95);
  for (int i = 0; i < 9; i++) {
    float fi = float(i); float2 h = hash22(float2(fi * 4.4, 61.0));
    if (h.x > 0.35 + 0.65 * max(calm, E)) continue;
    float life = fract(t * (0.035 + 0.03 * h.y) + h.x * 7.0);
    float2 p = float2((h.y - 0.5) * 0.95 + 0.07 * sin(t * 0.8 + fi * 2.0), mix(1.1, -1.1, life));
    float2 q = rot2(uv - p, 0.6 * sin(t * 0.7 + fi) + fi) / (0.07 + 0.04 * h.x);
    float d = featherShape(q);
    col = mix(col, float3(1.0, 0.98, 0.95) * (0.92 - 0.22 * sstep(0.03, 0.0, abs(q.x))), sstep(0.05, -0.05, d) * 0.9);
  }
  col += motes(uv, float2(0.0, -0.5), 1.5, t * 0.6, calm * 0.7, float3(1.0, 0.82, 0.42), 23.0);
  if (game) {
    col += float3(1.0, 0.86, 0.5) * (tapRing(uv, u) + star(uv - u.tap, 0.02) * exp(-u.game.w * 6.0) * 1.5);
    col += motes(uv, wc + float2(0.0, -0.2), 0.9, t * 1.3, E * 1.4, float3(1.0, 0.88, 0.55), 71.0);
    col *= 1.0 + 0.18 * E;
    col += rewardBurst(uv, B, u, float3(1.0, 0.84, 0.45), 6.0) * sstep(0.12, 0.16, u.game2.x);
  }
  return col;
}

// ───────── 10 魔药蒸发 ─────────
static float3 potionColor(float P) {
  float3 a = float3(0.30, 0.07, 0.55), b = float3(0.05, 0.62, 0.58), m = float3(0.40, 0.80, 0.26), c = float3(1.0, 0.62, 0.14);
  return mix(mix(mix(a, b, sstep(0.24, 0.56, P)), m, sstep(0.58, 0.72, P)), c, sstep(0.72, 0.90, P));
}
static float3 sceneRelPotion(float2 uv, Uniforms u) {
  float t = u.time; bool game = gameOn(u); float P = game ? gameP(u, 0.30, 0.90, 1.0) : relP(u);
  float E = game ? u.game.z : 0.0; float kick = game ? exp(-u.game.w * 4.0) : 0.0;
  float3 liq = potionColor(P); float glowv = 0.50 + 0.30 * sstep(0.1, 0.9, P) + 0.40 * E;
  float3 col = mix(float3(0.030, 0.018, 0.042), float3(0.005, 0.003, 0.009), sstep(-0.6, 0.9, uv.y));
  float2 c0 = float2(0.0, -0.18); float R = 0.31;
  col += float3(0.20, 0.10, 0.32) * exp(-length(uv - c0 - float2(0.0, 0.25)) * 2.4) * 0.10;
  col += bokeh(uv, t, 0.22, float3(1.0, 0.72, 0.35), 4.0) * 0.045;
  float rimY = c0.y + 0.50 * R; float rimW = 0.866 * R;
  float LY = c0.y + (0.10 + 0.14 * sstep(0.04, 0.20, P)) * R; float lw = sqrt(max(R * R - (LY - c0.y) * (LY - c0.y), 0.0)) * 0.97;
  // 一张圆桌：桌面映着药的光
  float2 tc = float2(0.0, c0.y - R * 0.98 - 0.05); float te = length((uv - tc) / float2(0.44, 0.085));
  if (te < 1.0) {
    float2 tq = float2(uv.x, (uv.y - (c0.y - R * 0.98)) * 3.2);
    float3 tab = float3(0.030, 0.020, 0.036) * (0.7 + 0.6 * fbm(float2(uv.x * 30.0, uv.y * 4.0)));
    tab += liq * exp(-dot(tq, tq) * 9.0) * 0.55 * glowv + liq * exp(-dot(tq, tq) * 2.5) * 0.10 * glowv;
    ;
    col = mix(col, tab, sstep(1.0, 0.5, te));
  } else if (uv.y < tc.y && abs(uv.x) < 0.44) {
    ;
  }
  // 蒸汽：从锅口往上散
  float steam = sstep(0.42, 0.62, P) * (1.0 - 0.6 * sstep(0.9, 1.0, P)) + 0.10 + 0.7 * E;
  { float dy = uv.y - rimY; if (dy > 0.0) { float widen = 0.5 + dy * 1.6; float sx = uv.x / (rimW * widen);
      float dens = fbm(float2(sx * 2.2 + 0.4 * sin(dy * 3.0 + t * 0.3), dy * 3.4 - t * 0.33)) * exp(-sx * sx * 1.8) * exp(-dy * 1.6);
      col += mix(liq, float3(1.0), 0.25) * sstep(0.28, 0.80, dens * 1.9) * steam * 0.42; } }
  // 黑泡泡（烦恼）：一个个落进药里
  float ripple = sstep(0.05, 0.09, P) * (1.0 - sstep(0.20, 0.26, P)) * 0.6 + kick * 0.5;
  for (int i = 0; i < 5; i++) {
    float fi = float(i); float2 h = hash22(float2(fi * 3.3, 71.0));
    float st = 0.22 + fi * 0.07; float k = sstep(st, st + 0.07, P), sink = sstep(st + 0.07, st + 0.11, P);
    ripple += (P > st + 0.07 ? exp(-(P - st - 0.07) * u.dur * 0.5) : 0.0);
    if (sink >= 1.0) continue;
    float2 home = float2(-0.26 + fi * 0.13, 0.36 + 0.10 * sin(fi * 2.4) + 0.012 * sin(t * 1.1 + fi * 1.7));
    float2 p = mix(home, float2(home.x * 0.35, LY + 0.01), k * k) - float2(0.0, sink * 0.03);
    float r = (0.042 + 0.014 * h.x) * (1.0 - sink);
    float d = length(uv - p);
    if (d < r) { float3 n = sphN(uv, p, r); float fr = pow(1.0 - n.z, 2.5);
      float3 bc = float3(0.012, 0.008, 0.02) + float3(0.30, 0.16, 0.50) * fr * 0.6 + liq * saturate(-n.y) * 0.30 * glowv;
      bc += float3(1.0) * pow(saturate(dot(reflect(float3(0.0, 0.0, -1.0), n), normalize(float3(-0.5, 0.66, 0.56)))), 50.0) * 1.1;
      col = mix(col, bc, sstep(r, r - 0.004, d)); }
  }
  // 玻璃坩埚
  float dc = length(uv - c0);
  float rimEl = sqrt(max(1.0 - pow((uv.x - c0.x) / rimW, 2.0), 0.0)) * 0.028;
  if (dc < R && uv.y < rimY + rimEl) {
    float3 n = sphN(uv, c0, R); float3 Rf = reflect(float3(0.0, 0.0, -1.0), n); float fr = pow(1.0 - n.z, 3.0);
    float dx = (uv.x - c0.x) / lw; float el = sqrt(max(1.0 - dx * dx, 0.0)) * 0.030;
    float3 inside = col * 0.85 + float3(0.012, 0.008, 0.018);
    if (abs(dx) < 1.0 && uv.y < LY + el) {
      float2 lp = uv - c0;
      float swirl = fbm(rot2(lp, t * 0.15 + (game ? u.game.y * 16.0 : 0.0) + length(lp) * (3.0 + 5.0 * E)) * 7.0 + float2(0.0, t * 0.05));
      if (uv.y > LY - el) {
        float2 sq = float2(dx, (uv.y - LY) / 0.030);
        float rip = sin(length(sq) * 9.0 - t * 4.0) * saturate(ripple) * 0.22;
        inside = liq * glowv * (0.80 + rip + 0.40 * swirl);
        inside += float3(1.0) * sstep(0.10, 0.0, abs(length(sq) - 0.93)) * 0.08;
      } else {
        float depth = saturate((LY - uv.y) / (R * 1.1));
        float thick = pow(n.z, 1.3);
        inside = liq * glowv * mix(0.20, 1.0, thick) * (1.0 - 0.45 * depth) * (0.60 + 0.5 * swirl);
        inside += liq * 0.35 * glowv * exp(-length(lp - float2(0.0, -0.06)) * 7.0);
        float act2 = max(0.25 + 0.75 * sstep(0.2, 0.7, P), E * 1.3);
        float2 bp = float2(uv.x * 30.0, (uv.y - t * 0.10 * act2) * 30.0); float2 bid = floor(bp), bf = fract(bp) - 0.5; float2 bh = hash22(bid + 3.0);
        if (bh.x < 0.22 * act2) { float br2 = 0.10 + 0.18 * bh.y; float bdd = length(bf - (bh - 0.5) * 0.4); inside += mix(float3(1.0), liq, 0.4) * (sstep(0.05, 0.0, abs(bdd - br2)) * 0.45 + sstep(br2, 0.0, bdd) * 0.06) * glowv; }
      }
      inside = mix(inside, float3(0.02, 0.01, 0.04), saturate(ripple) * 0.6 * sstep(0.38, 0.72, swirl));
    }
    float F = 0.03 + 0.97 * fr;
    float3 env = float3(0.10, 0.07, 0.14) * (0.4 + 0.6 * saturate(Rf.y * 0.5 + 0.5));
    float ang = atan2(n.y, n.x); float rr = dc / R;
    float front = sstep(rimY - rimEl + 0.004, rimY - rimEl - 0.004, uv.y);
    float streak = sstep(0.74, 0.80, rr) * sstep(0.90, 0.85, rr) * sstep(0.38, 0.0, abs(ang - 2.75));
    float streak2 = sstep(0.82, 0.86, rr) * sstep(0.94, 0.90, rr) * sstep(0.30, 0.0, abs(ang + 0.75)) * 0.30;
    float spec = pow(saturate(dot(Rf, normalize(float3(-0.45, 0.6, 0.66)))), 220.0) * 1.4;
    float3 gc = inside * (1.0 - 0.6 * F) + env * F * 1.2 + float3(0.85, 0.82, 1.0) * F * 0.22 + liq * fr * 0.30 * glowv;
    gc += float3(1.0, 0.97, 0.92) * (streak * 0.55 + streak2 + spec) * front;
    col = mix(col, gc, sstep(R, R - 0.005, dc));
  }
  // 锅口的玻璃边，和底下的玻璃座
  { float2 rq = float2((uv.x - c0.x) / rimW, (uv.y - rimY) / 0.028); float rd2 = abs(length(rq) - 1.0);
    col += float3(0.9, 0.86, 1.0) * exp(-rd2 * 30.0) * (0.30 + 0.25 * sstep(0.3, -0.6, rq.y)) + liq * exp(-rd2 * 8.0) * 0.08 * glowv;
    float2 fq = float2(uv.x / 0.105, (uv.y - (c0.y - R * 0.975)) / 0.020); float fd = abs(length(fq) - 1.0);
    col += float3(0.8, 0.78, 1.0) * exp(-fd * 16.0) * 0.16 + liq * exp(-dot(fq, fq) * 1.2) * 0.25 * glowv; }
  // 药瓶：倾斜，一道细流倒进锅里；倒完就隐去
  float flaskA = 1.0 - sstep(0.27, 0.34, P);
  float tilt = sstep(0.03, 0.09, P) * (1.0 - sstep(0.20, 0.27, P));
  float2 bc0 = float2(0.26, 0.40 + 0.012 * sin(t * 1.2)); float ang = 2.0 * tilt;
  float2 bq = rot2(uv - bc0, -ang);
  float fill = 1.0 - sstep(0.06, 0.22, P);
  if (flaskA > 0.0) { float body = length(bq - float2(0.0, -0.03)) - 0.062; float neck = max(abs(bq.x) - 0.020, abs(bq.y - 0.06) - 0.045); float lip = max(abs(bq.x) - 0.028, abs(bq.y - 0.105) - 0.008);
    float sd = min(body, min(neck, lip));
    if (sd < 0.01) { float3 n = sphN(bq, float2(0.0, -0.03), 0.062); float fr = pow(1.0 - n.z, 2.5);
      float lvl = -0.092 + 0.10 * fill; float3 pcol = float3(0.16, 0.85, 0.66);
      float3 inside = body < 0.0 && (uv.y - bc0.y) < lvl ? pcol * (0.5 + 0.6 * n.z) : col;
      float3 gcol = inside * 0.9 + float3(0.6, 0.65, 0.9) * fr * 0.45 * step(body, 0.0) + float3(1.0) * pow(saturate(dot(reflect(float3(0.0, 0.0, -1.0), n), normalize(float3(-0.5, 0.66, 0.56)))), 40.0) * 0.9 * step(body, 0.0);
      gcol += float3(0.7, 0.75, 1.0) * exp(-abs(sd) * 300.0) * 0.35;
      col = mix(col, gcol, sstep(0.004, -0.002, sd) * flaskA); } }
  float pourK = sstep(0.7, 1.0, tilt) * step(0.02, fill);
  if (pourK > 0.0) {
    float2 M = bc0 + rot2(float2(0.0, 0.115), ang); float2 Sx = float2(0.05, LY);
    float best = 1e3; float bs = 0.0; float2 prev = M;
    for (int k = 1; k <= 12; k++) { float s = float(k) / 12.0; float2 pp = float2(mix(M.x, Sx.x, 1.0 - (1.0 - s) * (1.0 - s)), mix(M.y, Sx.y, s * s));
      float2 pa = uv - prev, ba = pp - prev; float hh = saturate(dot(pa, ba) / dot(ba, ba)); float d = length(pa - ba * hh);
      if (d < best) { best = d; bs = (float(k) - 1.0 + hh) / 12.0; } prev = pp; }
    float wdt = 0.0055 + 0.002 * sin(bs * 30.0 - t * 18.0);
    col += float3(0.22, 0.95, 0.75) * (sstep(wdt, wdt * 0.3, best) * 1.1 + exp(-best * 70.0) * 0.22) * pourK;
  }
  // 蒸发：亮亮的小泡从药面升起，过了锅口就散掉
  float ev = max(sstep(0.45, 0.62, P) * (1.0 - 0.75 * sstep(0.92, 1.0, P)), E);
  if (ev > 0.01) for (int i = 0; i < 16; i++) {
    float fi = float(i); float2 h = hash22(float2(fi * 2.7, 83.0)); float life = fract(t * (0.14 + 0.12 * h.y) + h.x);
    float2 p = float2((h.x - 0.5) * lw * 1.5 * (1.0 + life * 0.6) + 0.02 * sin(t * 2.0 + fi), LY + life * (0.55 + 0.3 * h.y));
    float r = 0.010 + 0.012 * h.y; float d = length(uv - p); float al = sin(life * 3.14159) * ev; float2 hl = uv - p + float2(r * 0.4, -r * 0.4);
    col += mix(liq, float3(1.0), 0.5) * (sstep(0.004, 0.0, abs(d - r)) * 0.8 + exp(-dot(hl, hl) * 30000.0) * 1.1) * al;
    col += float3(1.0, 0.9, 0.7) * star(uv - p - float2(0.0, 0.02), 0.008) * al * sstep(0.8, 1.0, life) * 2.0;
  }
  col += motes(uv, float2(0.0, 0.0), 1.2, t * 0.5, sstep(0.85, 1.0, P) * 0.6, float3(1.0, 0.80, 0.42), 29.0);
  if (game) {
    col += mix(liq, float3(1.0), 0.4) * tapRing(uv, u) * 0.8;
    col += liq * exp(-length(uv - float2(0.0, rimY + 0.1)) * 3.0) * 0.30 * E;
    col += rewardBurst(uv, float2(0.0, rimY + 0.05), u, float3(1.0, 0.72, 0.30), 8.0);
    col += rewardBurst(uv, float2(0.0, rimY + 0.25), u, mix(liq, float3(1.0), 0.3), 13.0) * 0.8;
  }
  return col;
}

fragment float4 stage_fragment(VOut in [[stage_in]], constant Uniforms &u [[buffer(0)]], texture2d<float> coinTex [[texture(0)]], sampler smp [[sampler(0)]]) {
  float2 frag = in.pos.xy;
  float2 uv = (float2(frag.x, u.res.y - frag.y) * 2.0 - u.res) / u.res.y;
  uv += u.touch * float2(0.012, 0.008);
  if (u.prog >= 0.0 && u.scene < 6.5) { float push = sstep(0.0, 0.55, u.prog) * (1.0 - sstep(0.86, 1.0, u.prog)); float2 c = float2(0.0, 0.22); uv = (uv - c) * (1.0 - 0.07 * push) + c; }
  int s = int(u.scene + 0.5);
  float3 col;
  if (s == 0) col = sceneWealth(uv, u, coinTex, smp);
  else if (s == 1) col = sceneCareer(uv, u);
  else if (s == 2) col = sceneLooks(uv, u);
  else if (s == 3) col = sceneHealth(uv, u);
  else if (s == 4) col = sceneMood(uv, u);
  else if (s == 5) col = sceneLife(uv, u);
  else if (s == 6) col = scenePet(uv, u);
  else if (s == 7) col = sceneRelPool(uv, u);
  else if (s == 8) col = sceneRelBalloon(uv, u);
  else if (s == 9) col = sceneRelArrow(uv, u);
  else if (s == 10) col = sceneRelPotion(uv, u);
  else col = sceneRelDeep(uv, u);
  // 输出线性的高动态范围颜色，色调映射放在合成那一步
  return float4(max(col * u.fade, float3(0.0)), 1.0);
}

// ═════════ 后期：辉光和合成 ═════════
struct Post {
  float2 texel;     // 源贴图一个像素的大小
  float threshold;  // 辉光阈值
  float intensity;  // 辉光强度
  float time;
  float first;      // 1 表示第一级缩小，要先取亮部
  float2 pad;
};
struct PV { float4 pos [[position]]; float2 uv; };

vertex PV post_vertex(uint vid [[vertex_id]]) {
  float2 p = float2(float((vid << 1) & 2), float(vid & 2));
  PV o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); o.uv = float2(p.x, 1.0 - p.y); return o;
}

// 缩小一半：中心加四个斜向采样。第一级只留下亮过阈值的部分，带一段柔和过渡
fragment float4 bloom_down(PV in [[stage_in]], constant Post &u [[buffer(0)]], texture2d<float> src [[texture(0)]], sampler smp [[sampler(0)]]) {
  float2 t = u.texel;
  float3 c = src.sample(smp, in.uv).rgb * 4.0;
  c += src.sample(smp, in.uv + float2(-t.x, -t.y)).rgb + src.sample(smp, in.uv + float2(t.x, -t.y)).rgb;
  c += src.sample(smp, in.uv + float2(-t.x, t.y)).rgb + src.sample(smp, in.uv + float2(t.x, t.y)).rgb;
  c /= 8.0;
  if (u.first > 0.5) {
    float br = max(c.r, max(c.g, c.b));
    float knee = u.threshold * 0.6;
    float soft = clamp(br - u.threshold + knee, 0.0, 2.0 * knee);
    soft = soft * soft / (4.0 * knee + 1e-4);
    c *= max(soft, br - u.threshold) / max(br, 1e-4);
    c = min(c, float3(8.0));
  }
  return float4(c, 1.0);
}

// 放大一倍叠回上一级：八点帐篷滤波
fragment float4 bloom_up(PV in [[stage_in]], constant Post &u [[buffer(0)]], texture2d<float> src [[texture(0)]], sampler smp [[sampler(0)]]) {
  float2 t = u.texel;
  float3 c = src.sample(smp, in.uv + float2(-2.0 * t.x, 0.0)).rgb + src.sample(smp, in.uv + float2(2.0 * t.x, 0.0)).rgb;
  c += src.sample(smp, in.uv + float2(0.0, -2.0 * t.y)).rgb + src.sample(smp, in.uv + float2(0.0, 2.0 * t.y)).rgb;
  c += 2.0 * (src.sample(smp, in.uv + float2(-t.x, -t.y)).rgb + src.sample(smp, in.uv + float2(t.x, -t.y)).rgb);
  c += 2.0 * (src.sample(smp, in.uv + float2(-t.x, t.y)).rgb + src.sample(smp, in.uv + float2(t.x, t.y)).rgb);
  return float4(c / 12.0, 1.0);
}

// 合成：场景加辉光，边缘一点色散，再过暗角、色调映射和颗粒
fragment float4 stage_composite(PV in [[stage_in]], constant Post &u [[buffer(0)]], texture2d<float> scene [[texture(0)]], texture2d<float> bloom [[texture(1)]], sampler smp [[sampler(0)]]) {
  float2 d = in.uv - 0.5;
  float2 ca = d * dot(d, d) * 0.004;
  float3 col = float3(scene.sample(smp, in.uv + ca).r, scene.sample(smp, in.uv).g, scene.sample(smp, in.uv - ca).b);
  float3 bl = bloom.sample(smp, in.uv).rgb / float(5);
  col += bl * u.intensity * 5.0;
  float2 v = d * float2(1.05, 1.45);
  col *= 1.0 - 0.36 * dot(v, v);
  col = aces(col);
  col = pow(col, float3(1.0 / 2.2));
  col += (hash21(in.pos.xy + fract(u.time) * 61.0) - 0.5) * 0.02;
  return float4(col, 1.0);
}
