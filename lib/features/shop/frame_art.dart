import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../sanctuary/islet_art.dart';
import '../sanctuary/sanctuary_ui.dart';

/// 「小动物的礼物」那一组头像框：每只动物一件专属的，另有几件用收藏品换的。全部用代码画，没有图片素材。
/// 编号和服务器 server/app/catalog.py 的 KEEPSAKES 一致。
///
/// 画在以原点为中心的 100×100 格子里：头像占中间半径 [keepsakeHole] 的圆，框压在它外面一圈，
/// 小装饰（爪印、小鱼、铃铛……）可以探出去一点，也可以压住头像的边。
const keepsakeFrameIds = {
  'frame_teddy', 'frame_shiba', 'frame_cotton', 'frame_tangerine', 'frame_tangyuan', 'frame_huajuan', 'frame_zhima',
  'frame_tuanzi', 'frame_momo', 'frame_doubao', 'frame_shell', 'frame_autumn', 'frame_meadow', 'frame_pearl', //
};

/// 头像在 100 的格子里占多大的半径
const double keepsakeHole = 37;
const double _r = 41; // 框的中线
const _tau = math.pi * 2;

/// 套在头像外面的框。[size] 是整个头像（连框）的边长。
class KeepsakeFrame extends StatelessWidget {
  final String id;
  final double size;
  const KeepsakeFrame(this.id, {super.key, required this.size});

  @override
  Widget build(BuildContext context) => IgnorePointer(child: CustomPaint(size: Size.square(size), painter: _FramePainter(id)));
}

class _FramePainter extends CustomPainter {
  final String id;
  const _FramePainter(this.id);

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.translate(size.width / 2, size.height / 2);
    canvas.scale(math.min(size.width, size.height) / 100);
    paintKeepsakeFrame(canvas, id);
    canvas.restore();
  }

  @override
  bool shouldRepaint(_FramePainter old) => old.id != id;
}

Paint _fill(Color c) => Paint()..color = c;

Paint _line(Color c, double w) => Paint()
  ..color = c
  ..style = PaintingStyle.stroke
  ..strokeWidth = w
  ..strokeCap = StrokeCap.round;

/// 一圈色带
void _band(Canvas canvas, List<Color> colors, {double width = 7, double r = _r, double turn = 0}) {
  canvas.drawCircle(
      Offset.zero,
      r,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = width
        ..shader = SweepGradient(colors: [...colors, colors.first], transform: GradientRotation(turn)).createShader(Rect.fromCircle(center: Offset.zero, radius: r)));
}

/// 色带里外各描一道细线，让框有个边
void _rims(Canvas canvas, Color color, {double width = 7, double r = _r}) {
  canvas.drawCircle(Offset.zero, r - width / 2, _line(color, 0.8));
  canvas.drawCircle(Offset.zero, r + width / 2, _line(color, 0.8));
}

Offset _on(double angle, [double r = _r]) => Offset(r * math.cos(angle), r * math.sin(angle));

/// 一对猫耳朵，长在框的顶上
void _ears(Canvas canvas, Color left, Color right, Color inner) {
  for (final (s, c) in [(-1.0, left), (1.0, right)]) {
    final base = _on(-math.pi / 2 + s * 0.62, _r + 1);
    final ear = Path()
      ..moveTo(base.dx - s * 9, base.dy + 4)
      ..lineTo(base.dx + s * 4, base.dy - 15)
      ..lineTo(base.dx + s * 10, base.dy + 6)
      ..close();
    canvas.drawPath(ear, _fill(c));
    canvas.drawPath(
        Path()
          ..moveTo(base.dx - s * 4, base.dy + 3)
          ..lineTo(base.dx + s * 3.4, base.dy - 8)
          ..lineTo(base.dx + s * 7, base.dy + 4)
          ..close(),
        _fill(inner));
  }
}

/// 一条顺着框游的小鱼（头朝 [angle] 增大的方向）
void _swimmer(Canvas canvas, double angle, Color body, Color belly) {
  final o = _on(angle);
  canvas.save();
  canvas.translate(o.dx, o.dy);
  canvas.rotate(angle + math.pi / 2);
  canvas.drawPath(
      Path()
        ..moveTo(-5, 0)
        ..lineTo(-11, -4.5)
        ..lineTo(-9.5, 0)
        ..lineTo(-11, 4.5)
        ..close(),
      _fill(body));
  canvas.drawOval(const Rect.fromLTRB(-7, -4, 8, 4), _fill(body));
  canvas.drawOval(const Rect.fromLTRB(-4, 0, 6, 3.6), _fill(belly));
  canvas.drawCircle(const Offset(5, -1), 0.9, _fill(const Color(0xFF1B1512)));
  canvas.restore();
}

/// 在 100×100 的格子里画一件头像框。[t] 是 0~1 的循环时钟（商城卡片上会动一点；头像上是静止的）。
void paintKeepsakeFrame(Canvas canvas, String id, {double t = 0}) {
  final wave = math.sin(t * _tau);
  switch (id) {
    case 'frame_teddy':
      // 栗子的爪印：栗色的皮圈，一圈小爪印一左一右地踩过去，右下角一个大的
      _band(canvas, const [Color(0xFFC08A55), Color(0xFF8A5A34), Color(0xFFA9703F), Color(0xFF6E4424)], width: 9);
      _rims(canvas, const Color(0xFF5A3518), width: 9);
      for (var i = 0; i < 7; i++) {
        final a = -math.pi / 2 + (i + 0.3) * _tau / 8.2;
        Shapes.paw(canvas, _on(a, _r + (i.isEven ? 1.2 : -1.2)), 4.6, rot: a + math.pi / 2 + (i.isEven ? 0.35 : -0.35));
      }
      final big = _on(math.pi * 0.27, _r + 1);
      canvas.drawCircle(big, 13, _fill(const Color(0xFF6E4424)));
      canvas.drawCircle(big, 13, _line(const Color(0xFFE9CF9F), 1.2));
      Shapes.paw(canvas, big.translate(0, -1.5), 9, rot: -0.3 + 0.06 * wave);

    case 'frame_shiba':
      // 年糕的树枝：两根捡来的树枝弯成一圈，底下交叉，一路长着小叶子
      const bark = Color(0xFF7A5230);
      final ring = Rect.fromCircle(center: Offset.zero, radius: _r);
      canvas.drawArc(ring, math.pi / 2 - 0.25, math.pi + 0.5, false, _line(bark, 4));
      canvas.drawArc(ring, -math.pi / 2 - 0.25, math.pi + 0.5, false, _line(const Color(0xFF8E633A), 3.4));
      canvas.drawArc(Rect.fromCircle(center: Offset.zero, radius: _r - 0.8), 0, _tau, false, _line(const Color(0x55D9B98A), 0.8));
      for (var i = 0; i < 12; i++) {
        final a = -math.pi / 2 + (i + 0.5) * _tau / 12;
        if ((a - math.pi / 2).abs() < 0.35) continue;
        final out = i.isEven;
        Shapes.leaf(canvas, _on(a, _r + (out ? 5 : -4)), 5.4,
            rot: a + (out ? 0.5 : math.pi - 0.5) + math.pi / 2, color: i % 3 == 0 ? const Color(0xFF8DB45A) : const Color(0xFF5F9450));
      }
      // 底下交叉的两个枝头、三颗红果子
      canvas.drawLine(_on(math.pi / 2 - 0.2), _on(math.pi / 2 + 0.12, _r + 9), _line(bark, 3.4));
      canvas.drawLine(_on(math.pi / 2 + 0.2), _on(math.pi / 2 - 0.12, _r + 9), _line(const Color(0xFF8E633A), 3));
      for (final (dx, dy) in const [(-4.0, -1.0), (0.0, -4.0), (4.0, -1.0)]) {
        canvas.drawCircle(_on(math.pi / 2).translate(dx, dy), 2.3, _fill(SancColors.vermilion));
        canvas.drawCircle(_on(math.pi / 2).translate(dx - 0.7, dy - 0.7), 0.6, _fill(const Color(0xCCFFFFFF)));
      }

    case 'frame_cotton':
      // 棉花的云朵：天蓝的一圈，外面裹着一团团白云，云里藏着两朵小粉花
      for (var i = 0; i < 16; i++) {
        final a = i * _tau / 16;
        canvas.drawCircle(_on(a, _r + 1.5 + (i.isEven ? 1.6 : 0)), i.isEven ? 8.2 : 6.6, _fill(const Color(0xFFDDE9F2)));
      }
      for (var i = 0; i < 16; i++) {
        final a = i * _tau / 16 + 0.05;
        canvas.drawCircle(_on(a, _r + 0.5 + (i.isEven ? 1.6 : 0)), i.isEven ? 7.2 : 5.6, _fill(Colors.white));
      }
      canvas.drawCircle(Offset.zero, keepsakeHole + 0.6, _line(const Color(0xFF9CC7E8), 2.2));
      Shapes.flower(canvas, _on(-0.5, _r + 2), 4.2, const Color(0xFFFFC4D6), rot: t * _tau);
      Shapes.flower(canvas, _on(math.pi - 0.9, _r + 2), 3.4, const Color(0xFFFFC4D6));
      canvas.drawPath(Shapes.sparkle(_on(-2.2, _r + 3), 3), _fill(const Color(0xFFBFE2FF)));

    case 'frame_tangerine':
      // 橘子同款小鱼：橘色的一圈水波，四条小鱼追着尾巴游
      _band(canvas, const [Color(0xFFFFC56B), Color(0xFFF08A2E), Color(0xFFFFB04A), Color(0xFFE5702A)]);
      _rims(canvas, const Color(0xFFB85A14));
      for (var i = 0; i < 16; i++) {
        final a = i * _tau / 16;
        canvas.drawArc(Rect.fromCircle(center: _on(a), radius: 3), a + math.pi * 0.9, 1.6, false, _line(const Color(0x88FFF1D0), 0.9));
      }
      for (var i = 0; i < 4; i++) {
        final a = i * _tau / 4 + 0.5 + t * _tau;
        _swimmer(canvas, a, i.isEven ? const Color(0xFFFFF6E6) : const Color(0xFFD9562A), i.isEven ? const Color(0xFFFFD9A8) : const Color(0xFFFFB98A));
        canvas.drawCircle(_on(a + 0.34, _r + 5), 1.2, _line(const Color(0xCCFFFFFF), 0.7));
      }

    case 'frame_tangyuan':
      // 汤圆的蓝眼睛：雪白的一圈，顶上一对白耳朵，两边各嵌一颗蓝宝石一样的眼睛，底下一个粉鼻头
      _ears(canvas, Colors.white, Colors.white, const Color(0xFFFFC9D6));
      _band(canvas, const [Colors.white, Color(0xFFE6EDF2), Colors.white, Color(0xFFD9E3EA)]);
      _rims(canvas, const Color(0xFFB7C6D2));
      for (final s in const [-1.0, 1.0]) {
        final o = _on(math.pi / 2 - s * 1.05, _r);
        final eye = Rect.fromCenter(center: o, width: 13, height: 11);
        canvas.drawOval(eye.inflate(1.4), _fill(Colors.white));
        canvas.drawOval(eye, Paint()..shader = const RadialGradient(colors: [Color(0xFFBFEAFF), Color(0xFF3FA2E8), Color(0xFF1C5FA8)], stops: [0, 0.6, 1]).createShader(eye));
        canvas.drawOval(Rect.fromCenter(center: o, width: 3 + 1.2 * wave.abs(), height: 9), _fill(const Color(0xFF0E1E36)));
        canvas.drawCircle(o.translate(-2.6, -2.4), 1.5, _fill(Colors.white));
        // 胡子
        for (final d in const [-0.14, 0.0, 0.14]) {
          canvas.drawLine(_on(math.pi / 2 - s * (0.42 + d * 0.3), _r + 2), _on(math.pi / 2 - s * (0.62 + d), _r + 9), _line(const Color(0xFFB7C6D2), 0.8));
        }
      }
      final nose = _on(math.pi / 2);
      canvas.drawPath(
          Path()
            ..moveTo(nose.dx - 3.2, nose.dy - 2)
            ..lineTo(nose.dx + 3.2, nose.dy - 2)
            ..lineTo(nose.dx, nose.dy + 2.4)
            ..close(),
          _fill(const Color(0xFFF79AB0)));

    case 'frame_huajuan':
      // 花卷的三花：白底上一块橘、一块黑的毛色，一只橘耳朵一只黑耳朵，别着三朵小花
      const orange = Color(0xFFE9963F), black = Color(0xFF3A302A);
      _ears(canvas, orange, black, const Color(0xFFFFD2C4));
      canvas.drawCircle(Offset.zero, _r, _line(const Color(0xFFFFFAF0), 7.5));
      final ring = Rect.fromCircle(center: Offset.zero, radius: _r);
      for (final (start, sweep, c) in const [
        (-2.5, 0.75, orange), (-1.35, 0.5, black), (-0.55, 0.9, orange), (0.75, 0.55, black), (1.6, 0.7, orange), (2.6, 0.6, black), //
      ]) {
        canvas.drawArc(ring, start, sweep, false, _line(c, 7.5)..strokeCap = StrokeCap.butt);
        canvas.drawCircle(_on(start), 3.75, _fill(c));
        canvas.drawCircle(_on(start + sweep), 3.75, _fill(c));
      }
      _rims(canvas, const Color(0x66705A40), width: 7.5);
      Shapes.flower(canvas, _on(0.45, _r + 3), 4.4, const Color(0xFFFFF4F0), rot: t * _tau);
      Shapes.flower(canvas, _on(2.35, _r + 3), 3.8, const Color(0xFFFFC4D6));
      Shapes.flower(canvas, _on(math.pi / 2, _r + 2), 3.4, const Color(0xFFFFE9A8), heart: const Color(0xFFE9703A));

    case 'frame_zhima':
      // 芝麻的骨头：黑芝麻色的一圈，撒着白芝麻，四个角各一根小骨头
      _band(canvas, const [Color(0xFF4A413A), Color(0xFF2B2420), Color(0xFF3E3630), Color(0xFF241E1A)]);
      _rims(canvas, const Color(0xFF8A7B66));
      final rnd = math.Random(8);
      for (var i = 0; i < 26; i++) {
        final a = rnd.nextDouble() * _tau;
        final o = _on(a, _r - 2.4 + rnd.nextDouble() * 4.8);
        canvas.save();
        canvas.translate(o.dx, o.dy);
        canvas.rotate(rnd.nextDouble() * 3);
        canvas.drawOval(const Rect.fromLTRB(-1.1, -0.6, 1.1, 0.6), _fill(const Color(0xFFF1E3C4)));
        canvas.restore();
      }
      for (var i = 0; i < 4; i++) {
        final a = math.pi / 4 + i * math.pi / 2;
        Shapes.bone(canvas, _on(a, _r + 2), 12, rot: a + math.pi / 2 + 0.08 * wave);
      }

    case 'frame_tuanzi':
      // 团子的铃铛：一条红项圈，金线缝边，底下挂着一只小金铃
      _band(canvas, const [SancColors.vermilion, Color(0xFFE06A4A), SancColors.vermilion, SancColors.vermilionDeep]);
      _rims(canvas, SancColors.vermilionDeep);
      for (var i = 0; i < 40; i++) {
        final a = i * _tau / 40;
        canvas.drawLine(_on(a, _r + 2.2), _on(a + 0.07, _r + 2.2), _line(SancColors.goldLit, 0.9));
        canvas.drawLine(_on(a, _r - 2.2), _on(a + 0.07, _r - 2.2), _line(SancColors.goldLit, 0.9));
      }
      // 项圈扣
      final buckle = _on(-math.pi / 2 + 0.75);
      canvas.save();
      canvas.translate(buckle.dx, buckle.dy);
      canvas.rotate(0.75);
      canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTRB(-4.5, -5.5, 4.5, 5.5), const Radius.circular(1.5)), _line(SancColors.gold, 1.8));
      canvas.drawLine(const Offset(-4, 0), const Offset(4, 0), _line(SancColors.goldDeep, 1.2));
      canvas.restore();
      // 铃铛轻轻摆
      final hang = _on(math.pi / 2, _r + 2);
      canvas.save();
      canvas.translate(hang.dx, hang.dy);
      canvas.rotate(0.22 * wave);
      Shapes.bell(canvas, const Offset(0, 6), 10.5);
      canvas.restore();

    case 'frame_momo':
      // 墨墨的月夜：墨色的夜空，一弯月亮、几颗星，左下角蹲着一只小黑猫的影子
      _band(canvas, const [Color(0xFF1B2440), Color(0xFF0E1220), Color(0xFF26315A), Color(0xFF0B0E18)], width: 8);
      _rims(canvas, const Color(0xFF55618F), width: 8);
      final rnd = math.Random(21);
      for (var i = 0; i < 14; i++) {
        final a = rnd.nextDouble() * _tau;
        final tw = 0.5 + 0.5 * math.sin(t * _tau * 2 + i * 1.3);
        canvas.drawPath(Shapes.sparkle(_on(a, _r - 2.5 + rnd.nextDouble() * 5), 0.9 + rnd.nextDouble() * 1.4), _fill(SancColors.goldLit.withValues(alpha: 0.55 + 0.45 * tw)));
      }
      final mo = _on(-math.pi / 4, _r + 1);
      canvas.drawCircle(mo, 11, _fill(const Color(0x33FFE7A0)));
      canvas.drawPath(
          Path.combine(PathOperation.difference, Path()..addOval(Rect.fromCircle(center: mo, radius: 8)), Path()..addOval(Rect.fromCircle(center: mo.translate(4, -3), radius: 7))),
          _fill(const Color(0xFFFFE7A0)));
      // 小黑猫：蹲着，尾巴绕到身前，一双金眼睛
      final co = _on(math.pi * 0.72, _r + 1);
      const ink = Color(0xFF0B0E18);
      canvas.drawOval(Rect.fromCenter(center: co.translate(0, 3), width: 12, height: 13), _fill(ink));
      canvas.drawCircle(co.translate(0, -6), 5, _fill(ink));
      canvas.drawPath(Path()..moveTo(co.dx - 5, co.dy - 7)..lineTo(co.dx - 4, co.dy - 13.5)..lineTo(co.dx - 0.5, co.dy - 9.5)..close(), _fill(ink));
      canvas.drawPath(Path()..moveTo(co.dx + 5, co.dy - 7)..lineTo(co.dx + 4, co.dy - 13.5)..lineTo(co.dx + 0.5, co.dy - 9.5)..close(), _fill(ink));
      canvas.drawPath(Path()..moveTo(co.dx + 5, co.dy + 7)..quadraticBezierTo(co.dx + 13, co.dy + 6, co.dx + 10, co.dy - 2), _line(ink, 2.4));
      canvas.drawCircle(co.translate(-2, -6.4), 1, _fill(SancColors.goldLit));
      canvas.drawCircle(co.translate(2, -6.4), 1, _fill(SancColors.goldLit));

    case 'frame_doubao':
      // 豆包的毛线球：两股豆沙色的毛线绕成一圈，右下角滚着一团毛线球
      const a1 = Color(0xFFB8708A), a2 = Color(0xFFE9B9C6);
      for (final (phase, color, w) in const [(0.0, a1, 3.4), (math.pi, a2, 2.6)]) {
        final p = Path();
        for (var i = 0; i <= 180; i++) {
          final a = i * _tau / 180;
          final o = _on(a, _r + 2.6 * math.sin(a * 14 + phase));
          i == 0 ? p.moveTo(o.dx, o.dy) : p.lineTo(o.dx, o.dy);
        }
        canvas.drawPath(p, _line(color, w));
      }
      canvas.drawCircle(Offset.zero, keepsakeHole + 0.4, _line(const Color(0x998A4A62), 0.8));
      final ball = _on(math.pi * 0.25, _r + 1);
      Shapes.yarn(canvas, ball, 12, a1, rot: 0.25 * wave);
      Shapes.yarn(canvas, _on(math.pi * 0.86, _r + 2), 5, const Color(0xFF9CC7E8), rot: 2);

    case 'frame_shell':
      // 贝壳风铃：浅水色的一圈，顶上三枚贝壳，底下垂着三串小贝壳、小海螺，风一吹轻轻晃
      _band(canvas, const [Color(0xFFBFE6E8), Color(0xFF7FC2CC), Color(0xFFDDF3F0), Color(0xFF6BAEBE)], width: 6);
      _rims(canvas, const Color(0xFF4F8E9E), width: 6);
      for (var i = 0; i < 10; i++) {
        canvas.drawCircle(_on(i * _tau / 10 + 0.3), 1.1, _fill(const Color(0xCCFFFFFF)));
      }
      for (final (d, s) in const [(-0.5, 8.0), (0.0, 10.5), (0.5, 8.0)]) {
        final a = -math.pi / 2 + d;
        Shapes.shell(canvas, _on(a, _r + 2), s, rot: d, color: d == 0 ? const Color(0xFFFFD9C8) : const Color(0xFFFFF1E0));
      }
      for (final (d, len, k) in const [(-0.42, 10.0, 0), (0.0, 15.0, 1), (0.42, 10.0, 2)]) {
        final top = _on(math.pi / 2 + d, _r + 2);
        canvas.save();
        canvas.translate(top.dx, top.dy);
        canvas.rotate(0.14 * math.sin(t * _tau + k * 1.4));
        canvas.drawLine(Offset.zero, Offset(0, len - 4), _line(SancColors.rope, 0.8));
        if (k == 1) {
          Shapes.conch(canvas, Offset(0, len - 1), 6.5);
        } else {
          Shapes.shell(canvas, Offset(0, len), 6, rot: math.pi, color: const Color(0xFFFFE6D6));
        }
        canvas.restore();
      }

    case 'frame_autumn':
      // 秋叶标本：一圈细细的木框，枫叶和银杏叶一红一黄地压在上面
      _band(canvas, const [Color(0xFFA9794A), Color(0xFF7A5230), Color(0xFF9A6A3E), Color(0xFF6A4526)], width: 5);
      _rims(canvas, const Color(0xFF4A2E16), width: 5);
      for (var i = 0; i < 10; i++) {
        final a = -math.pi / 2 + i * _tau / 10;
        final o = _on(a, _r + 1.5);
        final rot = a + math.pi / 2 + (i.isEven ? 0.35 : -0.3) + 0.05 * wave;
        if (i.isEven) {
          Shapes.maple(canvas, o, i % 4 == 0 ? 10.5 : 8.6, rot: rot, color: i % 4 == 0 ? const Color(0xFFD2472F) : const Color(0xFFE9703A));
        } else {
          Shapes.ginkgo(canvas, o, 8.8, rot: rot);
        }
      }

    case 'frame_meadow':
      // 野花草环：一圈青藤，开着白的、粉的、黄的小野花，夹着四叶草和一根羽毛
      canvas.drawCircle(Offset.zero, _r, _line(const Color(0xFF4E8A45), 3));
      canvas.drawCircle(Offset.zero, _r + 1.6, _line(const Color(0xFF7FB06A), 1.2));
      for (var i = 0; i < 18; i++) {
        final a = i * _tau / 18 + 0.1;
        Shapes.leaf(canvas, _on(a, _r + (i.isEven ? 3.6 : -3)), 3.6, rot: a + (i.isEven ? 0.7 : 2.4), color: i % 3 == 0 ? const Color(0xFF8DB45A) : const Color(0xFF5F9450));
      }
      Shapes.feather(canvas, _on(math.pi * 0.8, _r + 3), 9, rot: -0.9 + 0.05 * wave);
      Shapes.clover(canvas, _on(-0.25, _r + 1), 5.6, stem: false);
      Shapes.clover(canvas, _on(math.pi + 0.5, _r + 1), 4.6, stem: false);
      const colors = [Color(0xFFFFF4F0), Color(0xFFFFC4D6), Color(0xFFFFE08A), Color(0xFFCFE0FF)];
      for (var i = 0; i < 6; i++) {
        final a = -math.pi / 2 + i * _tau / 6 + (i.isEven ? 0.0 : 0.12);
        Shapes.flower(canvas, _on(a, _r + 1), i.isEven ? 7 : 5.4, colors[i % 4], rot: i * 0.7 + t * _tau, heart: i % 4 == 2 ? const Color(0xFFE9703A) : const Color(0xFFF2C14E));
      }

    case 'frame_pearl':
      // 珍珠平安扣：两道细金线，中间串着一整圈珍珠，底下系一枚平安结
      canvas.drawCircle(Offset.zero, _r - 3.4, _line(SancColors.gold, 1.2));
      canvas.drawCircle(Offset.zero, _r + 3.4, _line(SancColors.goldDeep, 1.2));
      const n = 26;
      for (var i = 0; i < n; i++) {
        final a = -math.pi / 2 + (i + 0.5) * _tau / n;
        if ((a - math.pi / 2).abs() < 0.2) continue;
        Shapes.pearl(canvas, _on(a), i % 5 == 0 ? 4.2 : 3.4);
      }
      final shine = (t * n).floor() % n;
      canvas.drawPath(Shapes.sparkle(_on(-math.pi / 2 + (shine + 0.5) * _tau / n, _r - 1), 3.2), _fill(Colors.white));
      canvas.drawCircle(_on(math.pi / 2, _r - 1), 5.2, _line(const Color(0xFFBFE3C8), 2.6));
      Shapes.knot(canvas, _on(math.pi / 2, _r + 6), 10.5, rot: 0.06 * wave);
  }
}
