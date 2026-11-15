import 'dart:math' as math;

import 'package:flutter/material.dart';

/// 商城卡片上的「商品图」：没有图片素材，全部用代码画。
///
/// 每件商品一块深色的底、一团自己颜色的光，上面画着这件东西本身；[clock] 是商城页共用的一个 0~1 循环时钟，
/// 画面跟着它缓缓地动（漂浮、闪光、转动），不会触发整页重建。减少动态效果时商城页把时钟停在一个固定值上。
class ShopArt extends StatelessWidget {
  final String id;
  final Animation<double> clock;
  final double radius;
  const ShopArt(this.id, {super.key, required this.clock, this.radius = 18});

  @override
  Widget build(BuildContext context) {
    final look = _looks[id] ?? _looks['wall_stars']!;
    return RepaintBoundary(
      child: ClipRRect(
        borderRadius: BorderRadius.circular(radius),
        child: DecoratedBox(
          decoration: BoxDecoration(gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: look.bg)),
          child: CustomPaint(painter: _ArtPainter(id, look.glow, clock), child: const SizedBox.expand()),
        ),
      ),
    );
  }
}

/// 每件商品的底色（上、下）和光的颜色
class _Look {
  final List<Color> bg;
  final Color glow;
  const _Look(this.bg, this.glow);
}

const _looks = <String, _Look>{
  'wall_stars': _Look([Color(0xFF221D4A), Color(0xFF0B0A1C)], Color(0xFFFFD976)),
  'balloons': _Look([Color(0xFF3E1A3C), Color(0xFF150A18)], Color(0xFFFF9EC4)),
  'moon_lamp': _Look([Color(0xFF15264A), Color(0xFF080C18)], Color(0xFFFFE7A0)),
  'frame_gold': _Look([Color(0xFF3D2C12), Color(0xFF120C06)], Color(0xFFF0C356)),
  'frame_star': _Look([Color(0xFF2C2148), Color(0xFF0D0A18)], Color(0xFFC9B6FF)),
  'pet_bowl': _Look([Color(0xFF103346), Color(0xFF061218)], Color(0xFF7FD3FF)),
  'pet_ball': _Look([Color(0xFF3F1616), Color(0xFF140707)], Color(0xFFFF8A72)),
  'pet_bed': _Look([Color(0xFF402238), Color(0xFF140A12)], Color(0xFFFFB3D1)),
  'voice_affirm': _Look([Color(0xFF2E2318), Color(0xFF0B0A0D)], Color(0xFFE9CF8F)),
  'voice_library': _Look([Color(0xFF221D36), Color(0xFF0A0910)], Color(0xFFB8A2F2)),
};

const _tau = math.pi * 2;

// 金色：亮、中、暗
const _g1 = Color(0xFFFFF6CF);
const _g2 = Color(0xFFF0C356);
const _g3 = Color(0xFFA8731A);

class _ArtPainter extends CustomPainter {
  final String id;
  final Color glow;
  final Animation<double> clock;
  _ArtPainter(this.id, this.glow, this.clock) : super(repaint: clock);

  /// 一圈的角度：时钟一个循环走 [k] 圈（k 取整数，循环接得上）
  double _p(int k) => clock.value * _tau * k;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    final c = Offset(w / 2, h * 0.47);
    final m = math.min(w, h);

    // 一团会慢慢呼吸的光
    final breath = 0.5 + 0.5 * math.sin(_p(2));
    canvas.drawCircle(
        c,
        m * (0.52 + 0.04 * breath),
        Paint()
          ..shader = RadialGradient(colors: [glow.withValues(alpha: 0.42 + 0.12 * breath), glow.withValues(alpha: 0)])
              .createShader(Rect.fromCircle(center: c, radius: m * 0.56)));

    // 背景里一闪一闪的小星
    final rnd = math.Random(id.length * 7919 + id.codeUnitAt(0) * 31 + id.codeUnitAt(id.length - 1));
    for (var i = 0; i < 9; i++) {
      final pos = Offset(rnd.nextDouble() * w, rnd.nextDouble() * h * 0.9);
      final phase = rnd.nextDouble() * _tau;
      final r = 1.2 + rnd.nextDouble() * 2.2;
      final v = math.pow(math.max(0.0, math.sin(_p(3) + phase)), 2).toDouble();
      if (v < 0.02) continue;
      _sparkle(canvas, pos, r * (0.6 + 0.6 * v), Colors.white.withValues(alpha: 0.75 * v));
    }

    // 地上的影子，跟着物件的起伏变大变小
    final bob = math.sin(_p(2));
    canvas.drawOval(
        Rect.fromCenter(center: Offset(c.dx, c.dy + m * 0.40), width: m * (0.50 - 0.04 * bob), height: m * 0.07),
        Paint()
          ..color = Colors.black.withValues(alpha: 0.35)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4));

    // 物件本身画在 100×100 的格子里，中心是原点，上下漂浮
    canvas.save();
    canvas.translate(c.dx, c.dy - m * 0.025 * bob);
    canvas.scale(m / 100);
    switch (id) {
      case 'wall_stars':
        _stars(canvas);
      case 'balloons':
        _balloons(canvas);
      case 'moon_lamp':
        _moon(canvas);
      case 'frame_gold':
        _frame(canvas, const [_g1, _g2, _g3, _g2, Color(0xFFFFE9A8), _g3, _g1], false);
      case 'frame_star':
        _frame(canvas, const [Color(0xFFFFB3D1), Color(0xFFC9B6FF), Color(0xFFA8E6FF), Color(0xFFFFE7A8), Color(0xFFFFB3D1)], true);
      case 'pet_bowl':
        _bowl(canvas);
      case 'pet_ball':
        _ball(canvas);
      case 'pet_bed':
        _bed(canvas);
      case 'voice_affirm':
        _affirm(canvas);
      case 'voice_library':
        _vinyl(canvas);
    }
    canvas.restore();

    // 一道斜着扫过去的光，每个循环扫两次，扫完停一会
    final u = (clock.value * 2) % 1;
    if (u < 0.35) {
      final x = -0.5 * w + (u / 0.35) * 2 * w;
      final band = Rect.fromLTWH(x - w * 0.25, 0, w * 0.5, h);
      // 以 (x, h/2) 为中心往右斜一点
      canvas.save();
      canvas.translate(x, h / 2);
      canvas.skew(-0.35, 0);
      canvas.translate(-x, -h / 2);
      canvas.drawRect(
          band,
          Paint()
            ..blendMode = BlendMode.plus
            ..shader = LinearGradient(colors: [
              Colors.white.withValues(alpha: 0),
              Colors.white.withValues(alpha: 0.13),
              Colors.white.withValues(alpha: 0),
            ]).createShader(band));
      canvas.restore();
    }
  }

  // ───────── 各件商品 ─────────

  void _stars(Canvas canvas) {
    const list = [
      (Offset(0, -2), 24.0, 0.0),
      (Offset(-27, -22), 10.0, 1.3),
      (Offset(25, -27), 12.0, 2.6),
      (Offset(-24, 21), 8.0, 3.9),
      (Offset(27, 17), 9.0, 5.0),
      (Offset(3, -36), 5.0, 0.7),
    ];
    for (final (o, r, ph) in list) {
      final pulse = 1 + 0.10 * math.sin(_p(3) + ph);
      final rr = r * pulse;
      final path = _star(o, rr, rot: -math.pi / 2 + 0.08 * math.sin(_p(1) + ph));
      canvas.drawPath(
          path,
          Paint()
            ..color = _g2.withValues(alpha: 0.6)
            ..maskFilter = MaskFilter.blur(BlurStyle.normal, rr * 0.35));
      canvas.drawPath(path, Paint()..shader = _goldShader(Rect.fromCircle(center: o, radius: rr)));
    }
  }

  void _balloons(Canvas canvas) {
    const items = [
      (Offset(1, -24), Color(0xFFF3C45A), 0.0),
      (Offset(-21, -10), Color(0xFFFF8FB1), 2.1),
      (Offset(20, -13), Color(0xFFB9A2F2), 4.2),
    ];
    const tie = Offset(0, 40);
    for (final (o, col, ph) in items) {
      // 绕着绳子的结点轻轻摆
      final a = 0.07 * math.sin(_p(2) + ph);
      canvas.save();
      canvas.translate(tie.dx, tie.dy);
      canvas.rotate(a);
      canvas.translate(-tie.dx, -tie.dy);
      final knot = Offset(o.dx, o.dy + 17);
      canvas.drawPath(
          Path()
            ..moveTo(knot.dx, knot.dy + 2)
            ..quadraticBezierTo((knot.dx + tie.dx) / 2 + 6, (knot.dy + tie.dy) / 2, tie.dx, tie.dy),
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = 1
            ..color = Colors.white.withValues(alpha: 0.55));
      final body = Rect.fromCenter(center: o, width: 27, height: 33);
      canvas.drawOval(
          body,
          Paint()
            ..shader = RadialGradient(
                    center: const Alignment(-0.4, -0.5),
                    colors: [Color.lerp(col, Colors.white, 0.55)!, col, Color.lerp(col, Colors.black, 0.45)!],
                    stops: const [0, 0.5, 1])
                .createShader(body));
      canvas.drawPath(
          Path()
            ..moveTo(knot.dx, knot.dy - 1)
            ..lineTo(knot.dx - 2.6, knot.dy + 2.5)
            ..lineTo(knot.dx + 2.6, knot.dy + 2.5)
            ..close(),
          Paint()..color = Color.lerp(col, Colors.black, 0.3)!);
      canvas.drawOval(Rect.fromCenter(center: o.translate(-5.5, -7), width: 5, height: 9), Paint()..color = Colors.white.withValues(alpha: 0.5));
      canvas.restore();
    }
  }

  void _moon(Canvas canvas) {
    final glowV = 0.5 + 0.5 * math.sin(_p(2));
    canvas.drawCircle(
        const Offset(0, -8),
        30 + 4 * glowV,
        Paint()
          ..color = const Color(0xFFFFE7A0).withValues(alpha: 0.30 + 0.2 * glowV)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 14));
    // 底座和支架
    canvas.drawRect(const Rect.fromLTWH(-1.6, 12, 3.2, 20), Paint()..color = _g3);
    final base = RRect.fromRectAndRadius(const Rect.fromLTRB(-18, 30, 18, 39), const Radius.circular(4));
    canvas.drawRRect(base, Paint()..shader = const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [_g2, _g3]).createShader(base.outerRect));
    // 月牙
    final moon = Path.combine(
      PathOperation.difference,
      Path()..addOval(Rect.fromCircle(center: const Offset(0, -8), radius: 24)),
      Path()..addOval(Rect.fromCircle(center: const Offset(11, -15), radius: 20)),
    );
    canvas.drawPath(
        moon,
        Paint()
          ..shader = const RadialGradient(center: Alignment(-0.5, 0.2), colors: [Color(0xFFFFFBE6), Color(0xFFF7DA82), Color(0xFFC8962A)], stops: [0, 0.55, 1])
              .createShader(Rect.fromCircle(center: const Offset(0, -8), radius: 24)));
    _sparkle(canvas, const Offset(20, -30), 3 + 2.5 * math.pow(math.max(0.0, math.sin(_p(2))), 3), Colors.white.withValues(alpha: 0.9));
    _sparkle(canvas, const Offset(24, 4), 2 + 1.5 * math.pow(math.max(0.0, math.sin(_p(2) + 2.4)), 3), _g1.withValues(alpha: 0.8));
  }

  void _frame(Canvas canvas, List<Color> colors, bool stars) {
    const r = 31.0;
    final rect = Rect.fromCircle(center: Offset.zero, radius: r);
    // 里面一个淡淡的人像
    final ghost = Paint()..color = Colors.white.withValues(alpha: 0.16);
    canvas.drawCircle(const Offset(0, -7), 9, ghost);
    canvas.save();
    canvas.clipPath(Path()..addOval(Rect.fromCircle(center: Offset.zero, radius: r - 3)));
    canvas.drawOval(Rect.fromCenter(center: const Offset(0, 20), width: 40, height: 30), ghost);
    canvas.restore();
    // 一圈流动的颜色：渐变跟着时钟转
    canvas.drawCircle(
        Offset.zero,
        r + 5,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 6
          ..color = colors[1].withValues(alpha: 0.35)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6));
    canvas.drawCircle(
        Offset.zero,
        r,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 9
          ..shader = SweepGradient(colors: colors, transform: GradientRotation(_p(1))).createShader(rect));
    canvas.drawCircle(
        Offset.zero,
        r - 6,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1
          ..color = colors[0].withValues(alpha: 0.55));
    if (stars) {
      for (var i = 0; i < 6; i++) {
        final a = i * _tau / 6 - _p(1) * 0.5;
        final v = 0.5 + 0.5 * math.sin(_p(3) + i * 1.7);
        _sparkle(canvas, Offset(math.cos(a), math.sin(a)) * (r + 10), 2.5 + 2.5 * v, colors[i % (colors.length - 1)].withValues(alpha: 0.5 + 0.5 * v));
      }
    } else {
      // 上下左右四颗小宝石
      for (var i = 0; i < 4; i++) {
        final a = i * _tau / 4 - math.pi / 2;
        final o = Offset(math.cos(a), math.sin(a)) * r;
        final gem = Path()
          ..moveTo(o.dx, o.dy - 4.5)
          ..lineTo(o.dx + 3.5, o.dy)
          ..lineTo(o.dx, o.dy + 4.5)
          ..lineTo(o.dx - 3.5, o.dy)
          ..close();
        canvas.drawPath(gem, Paint()..color = i == 0 ? const Color(0xFFE8475A) : const Color(0xFFFFFBEA));
      }
      final v = math.pow(math.max(0.0, math.sin(_p(2) + 1)), 4).toDouble();
      _sparkle(canvas, const Offset(-22, -24), 2 + 4 * v, Colors.white.withValues(alpha: v));
    }
  }

  void _bowl(Canvas canvas) {
    final body = Path()
      ..moveTo(-33, 2)
      ..cubicTo(-31, 22, -24, 30, -18, 31)
      ..lineTo(18, 31)
      ..cubicTo(24, 30, 31, 22, 33, 2)
      ..close();
    const rect = Rect.fromLTRB(-33, -8, 33, 31);
    canvas.drawPath(body, Paint()..shader = const LinearGradient(colors: [Color(0xFF2B7FD1), Color(0xFF8AD6FF), Color(0xFF1A4F8F)], stops: [0, 0.35, 1]).createShader(rect));
    // 碗口、粮
    canvas.drawOval(Rect.fromCenter(center: const Offset(0, 2), width: 66, height: 18), Paint()..color = const Color(0xFF9FE0FF));
    canvas.drawOval(Rect.fromCenter(center: const Offset(0, 2.5), width: 57, height: 13), Paint()..color = const Color(0xFF123A5C));
    final rnd = math.Random(3);
    for (var i = 0; i < 16; i++) {
      final x = -22 + rnd.nextDouble() * 44;
      final y = -1 - (1 - (x.abs() / 24)) * 6 + rnd.nextDouble() * 4;
      canvas.drawCircle(Offset(x, y), 3.2, Paint()..color = Color.lerp(const Color(0xFFC98A4B), const Color(0xFF8A5528), rnd.nextDouble())!);
    }
    // 碗身上一颗心，一下一下地亮
    final v = 0.6 + 0.4 * math.sin(_p(2));
    canvas.drawPath(_heart(const Offset(0, 17), 6), Paint()..color = Colors.white.withValues(alpha: 0.55 + 0.35 * v));
    // 碗上飘起两缕香气（小心形）
    for (var k = 0; k < 2; k++) {
      final u = (clock.value * 2 + k * 0.5) % 1;
      final a = math.sin(u * math.pi);
      canvas.drawPath(_heart(Offset(-10 + k * 18 + 4 * math.sin(u * _tau), -10 - 26 * u), 3 + 2 * u), Paint()..color = const Color(0xFFFFB3D1).withValues(alpha: 0.8 * a));
    }
  }

  void _ball(Canvas canvas) {
    // 小球一下一下地弹，落地时稍稍压扁
    final u = (clock.value * 3) % 1;
    final hop = math.sin(u * math.pi);
    final squash = u < 0.08 || u > 0.92 ? 0.92 : 1.0;
    const r = 27.0;
    final cy = 4 - 12 * hop;
    canvas.save();
    canvas.translate(0, cy + r);
    canvas.scale(1 / squash, squash);
    canvas.translate(0, -r);
    final rect = Rect.fromCircle(center: Offset.zero, radius: r);
    canvas.drawCircle(
        Offset.zero,
        r,
        Paint()
          ..shader = const RadialGradient(center: Alignment(-0.4, -0.45), colors: [Color(0xFFFF9C8F), Color(0xFFE53935), Color(0xFF7E1616)], stops: [0, 0.5, 1])
              .createShader(rect));
    // 白色的弧线跟着滚
    canvas.save();
    canvas.clipPath(Path()..addOval(rect));
    canvas.rotate(_p(1));
    canvas.drawCircle(
        const Offset(-34, 30),
        48,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 7
          ..color = Colors.white.withValues(alpha: 0.9));
    canvas.restore();
    canvas.drawOval(Rect.fromCenter(center: const Offset(-10, -12), width: 12, height: 7), Paint()..color = Colors.white.withValues(alpha: 0.45));
    canvas.restore();
  }

  void _bed(Canvas canvas) {
    const rect = Rect.fromLTRB(-40, -16, 40, 32);
    final paint = Paint()..shader = const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFFFDCEA), Color(0xFFF59BC0), Color(0xFFB85985)]).createShader(rect);
    final cloud = Path()
      ..addOval(Rect.fromCircle(center: const Offset(-24, 10), radius: 14))
      ..addOval(Rect.fromCircle(center: const Offset(0, 2), radius: 18))
      ..addOval(Rect.fromCircle(center: const Offset(24, 10), radius: 14))
      ..addOval(Rect.fromCircle(center: const Offset(-12, 16), radius: 14))
      ..addOval(Rect.fromCircle(center: const Offset(12, 16), radius: 14))
      ..addRRect(RRect.fromRectAndRadius(const Rect.fromLTRB(-34, 10, 34, 30), const Radius.circular(10)));
    canvas.drawPath(cloud, paint);
    // 中间的软垫
    canvas.drawOval(Rect.fromCenter(center: const Offset(0, 12), width: 50, height: 17), Paint()..color = const Color(0xFFC96A95));
    canvas.drawOval(Rect.fromCenter(center: const Offset(0, 11), width: 46, height: 14), Paint()..color = const Color(0xFFFFE6F0));
    // 冒出来的「z」一样的小星，慢慢往上飘
    for (var k = 0; k < 3; k++) {
      final u = (clock.value * 2 + k / 3) % 1;
      final a = math.sin(u * math.pi);
      _sparkle(canvas, Offset(14 + 8 * u + 3 * math.sin(u * _tau + k), -12 - 30 * u), 2 + 3 * u, Colors.white.withValues(alpha: 0.85 * a));
    }
  }

  void _affirm(Canvas canvas) {
    // 一圈声波，跟着时钟起伏
    const n = 28;
    for (var i = 0; i < n; i++) {
      final a = i * _tau / n;
      final v = 0.5 + 0.5 * math.sin(_p(4) + i * 0.9) * math.cos(_p(1) + i * 0.35);
      final r0 = 22.0, len = 4 + 12 * v;
      final dir = Offset(math.cos(a), math.sin(a));
      canvas.drawLine(
          dir * r0,
          dir * (r0 + len),
          Paint()
            ..strokeWidth = 2.6
            ..strokeCap = StrokeCap.round
            ..color = Color.lerp(_g3, _g1, v)!.withValues(alpha: 0.65 + 0.35 * v));
    }
    final beat = 1 + 0.07 * math.pow(math.max(0.0, math.sin(_p(4))), 6);
    final heart = _heart(const Offset(0, 1), 15 * beat);
    canvas.drawPath(
        heart,
        Paint()
          ..color = _g2.withValues(alpha: 0.6)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6));
    canvas.drawPath(heart, Paint()..shader = _goldShader(Rect.fromCircle(center: Offset.zero, radius: 15)));
  }

  void _vinyl(Canvas canvas) {
    const r = 33.0;
    final rect = Rect.fromCircle(center: Offset.zero, radius: r);
    canvas.drawCircle(Offset.zero, r, Paint()..color = const Color(0xFF141218));
    final groove = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.7
      ..color = Colors.white.withValues(alpha: 0.08);
    for (var g = 14.0; g < r - 1; g += 2.4) {
      canvas.drawCircle(Offset.zero, g, groove);
    }
    // 唱片上的反光跟着转
    canvas.drawCircle(
        Offset.zero,
        r,
        Paint()
          ..shader = SweepGradient(
            colors: [
              Colors.white.withValues(alpha: 0),
              Colors.white.withValues(alpha: 0.22),
              Colors.white.withValues(alpha: 0),
              Colors.white.withValues(alpha: 0),
              Colors.white.withValues(alpha: 0.16),
              Colors.white.withValues(alpha: 0),
            ],
            stops: const [0, 0.1, 0.22, 0.5, 0.6, 0.72],
            transform: GradientRotation(_p(2)),
          ).createShader(rect));
    canvas.drawCircle(Offset.zero, 12, Paint()..shader = _goldShader(Rect.fromCircle(center: Offset.zero, radius: 12)));
    canvas.save();
    canvas.rotate(_p(2));
    canvas.drawCircle(const Offset(0, -7.5), 1.6, Paint()..color = const Color(0xFF6B4708));
    canvas.restore();
    canvas.drawCircle(Offset.zero, 2.2, Paint()..color = const Color(0xFF141218));
    // 右上角一个跳动的音符
    final v = math.sin(_p(2));
    canvas.save();
    canvas.translate(30, -30 - 3 * v);
    canvas.rotate(0.12 * v);
    final note = Paint()..shader = _goldShader(const Rect.fromLTRB(-8, -16, 8, 8));
    canvas.drawOval(Rect.fromCenter(center: const Offset(-3, 4), width: 9, height: 7), note);
    canvas.drawRect(const Rect.fromLTRB(0.5, -15, 2.6, 4), note);
    canvas.drawPath(
        Path()
          ..moveTo(2.6, -15)
          ..quadraticBezierTo(10, -11, 8, -4)
          ..quadraticBezierTo(8, -9, 2.6, -10)
          ..close(),
        note);
    canvas.restore();
  }

  // ───────── 小工具 ─────────

  static Shader _goldShader(Rect r) =>
      const RadialGradient(center: Alignment(-0.35, -0.45), colors: [_g1, _g2, _g3], stops: [0, 0.5, 1]).createShader(r);

  static Path _star(Offset c, double r, {double rot = -math.pi / 2}) {
    final path = Path();
    for (var i = 0; i < 10; i++) {
      final rr = i.isEven ? r : r * 0.45;
      final a = rot + i * math.pi / 5;
      final p = c + Offset(math.cos(a), math.sin(a)) * rr;
      i == 0 ? path.moveTo(p.dx, p.dy) : path.lineTo(p.dx, p.dy);
    }
    return path..close();
  }

  static Path _heart(Offset c, double s) => Path()
    ..moveTo(c.dx, c.dy + s * 0.8)
    ..cubicTo(c.dx - s * 1.2, c.dy, c.dx - s * 0.8, c.dy - s * 0.9, c.dx, c.dy - s * 0.35)
    ..cubicTo(c.dx + s * 0.8, c.dy - s * 0.9, c.dx + s * 1.2, c.dy, c.dx, c.dy + s * 0.8)
    ..close();

  /// 四角的小闪光
  static void _sparkle(Canvas canvas, Offset c, double r, Color color) {
    final q = r * 0.22;
    canvas.drawPath(
        Path()
          ..moveTo(c.dx, c.dy - r)
          ..quadraticBezierTo(c.dx + q, c.dy - q, c.dx + r, c.dy)
          ..quadraticBezierTo(c.dx + q, c.dy + q, c.dx, c.dy + r)
          ..quadraticBezierTo(c.dx - q, c.dy + q, c.dx - r, c.dy)
          ..quadraticBezierTo(c.dx - q, c.dy - q, c.dx, c.dy - r)
          ..close(),
        Paint()..color = color);
  }

  @override
  bool shouldRepaint(_ArtPainter old) => old.id != id || old.glow != glow || old.clock != clock;
}
