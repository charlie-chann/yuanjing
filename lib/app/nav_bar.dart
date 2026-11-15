import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'skin.dart';

/// 底栏：五个入口，每个字上面一枚一直在轻轻动的小图标。
///
/// 整条底栏共用一个循环时钟，图标用 CustomPainter 跟着时钟重画，不会让页面重建；
/// 选中的那枚是皮肤的强调色（多数是金色）、动得更明显，没选中的发白、动得轻一些。
/// 减少动态效果时停在一帧上；许愿仪式等沉浸画面里底栏收起时也停。
class NavBar extends StatefulWidget {
  final List<String> labels;
  final int index;
  final ValueChanged<int> onTap;
  final Skin skin;

  /// 底栏收起时为 true，这时停掉时钟
  final ValueNotifier<bool> hidden;
  const NavBar({super.key, required this.labels, required this.index, required this.onTap, required this.skin, required this.hidden});

  /// 底栏本身的高度（不含离屏幕底部的距离）
  static const height = 56.0;

  @override
  State<NavBar> createState() => _NavBarState();
}

class _NavBarState extends State<NavBar> with SingleTickerProviderStateMixin {
  late final _clock = AnimationController(vsync: this, duration: const Duration(seconds: 8));
  bool _still = false;

  @override
  void initState() {
    super.initState();
    widget.hidden.addListener(_sync);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _still = MediaQuery.disableAnimationsOf(context);
    _sync();
  }

  @override
  void didUpdateWidget(NavBar old) {
    super.didUpdateWidget(old);
    if (old.hidden != widget.hidden) {
      old.hidden.removeListener(_sync);
      widget.hidden.addListener(_sync);
      _sync();
    }
  }

  void _sync() {
    if (_still || widget.hidden.value) {
      _clock.stop();
      if (_still) _clock.value = 0.12;
    } else if (!_clock.isAnimating) {
      _clock.repeat();
    }
  }

  @override
  void dispose() {
    widget.hidden.removeListener(_sync);
    _clock.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.skin;
    return RepaintBoundary(
      child: Container(
        height: NavBar.height,
        padding: const EdgeInsets.all(4),
        decoration: BoxDecoration(
          color: const Color(0xD917130F),
          borderRadius: BorderRadius.circular(99),
          border: Border.all(color: Colors.white24),
          boxShadow: const [BoxShadow(color: Color(0x66000000), blurRadius: 20, offset: Offset(0, 8))],
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          for (final (i, label) in widget.labels.indexed)
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () => widget.onTap(i),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 260),
                width: 64,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(99),
                  gradient: widget.index == i
                      ? RadialGradient(center: const Alignment(0, -0.35), radius: 1.1, colors: [s.deep.withValues(alpha: 0.42), s.deep.withValues(alpha: 0.10)])
                      : null,
                  border: Border.all(color: widget.index == i ? s.light.withValues(alpha: 0.45) : Colors.transparent, width: 0.8),
                ),
                child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                  RepaintBoundary(
                    child: CustomPaint(
                      size: const Size.square(25),
                      painter: _TabIconPainter(kind: i, clock: _clock, on: widget.index == i, light: s.light, deep: s.deep),
                    ),
                  ),
                  const SizedBox(height: 1),
                  Text(label,
                      style: TextStyle(
                        fontSize: 11,
                        height: 1.2,
                        letterSpacing: 0.5,
                        fontWeight: widget.index == i ? FontWeight.w700 : FontWeight.w400,
                        color: widget.index == i ? s.light : Colors.white60,
                      )),
                ]),
              ),
            ),
        ]),
      ),
    );
  }
}

const _tau = math.pi * 2;

/// 五枚小图标，画在 24×24 的格子里：
/// 0 许愿：一枚慢慢翻转的方孔金币，角上一闪；1 广场：对话气泡，三个点轮流亮，冒出小心形；
/// 2 释放：一朵随呼吸开合的莲花，下面一圈圈水纹；3 商城：礼盒，盖子不时轻轻一跳，旁边闪一下；
/// 4 我的：一个小人，头顶的光环一明一暗地呼吸。
class _TabIconPainter extends CustomPainter {
  final int kind;
  final Animation<double> clock;
  final bool on;
  final Color light;
  final Color deep;
  _TabIconPainter({required this.kind, required this.clock, required this.on, required this.light, required this.deep}) : super(repaint: clock);

  double get t => clock.value;

  /// 时钟一个循环走 [k] 圈
  double _p(int k) => t * _tau * k;

  /// 动作幅度：选中的大一些
  double get _amp => on ? 1.0 : 0.55;
  Color get _main => on ? light : Colors.white.withValues(alpha: 0.66);
  Color get _accent => on ? deep : Colors.white.withValues(alpha: 0.38);

  /// 图标上的「镂空」处：选中时用深一档的强调色，没选中时用底栏的底色
  Color get _cut => on ? Color.lerp(deep, Colors.black, 0.35)! : const Color(0xCC17130F);

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 24);
    switch (kind) {
      case 0:
        _coin(canvas);
      case 1:
        _bubble(canvas);
      case 2:
        _lotus(canvas);
      case 3:
        _gift(canvas);
      default:
        _me(canvas);
    }
    canvas.restore();
  }

  void _coin(Canvas canvas) {
    // 选中时整圈地转，没选中时左右轻轻晃
    final turn = on ? math.cos(_p(1)) : math.cos(0.5 * math.sin(_p(1)));
    final sx = math.max(0.14, turn.abs());
    const c = Offset(12, 12.6);
    const r = 8.6;
    // 侧面的厚度
    final edgeShift = (1 - sx) * 1.4 * (turn >= 0 ? 1 : -1);
    canvas.drawOval(Rect.fromCenter(center: c.translate(edgeShift, 0), width: r * 2 * sx + 0.6, height: r * 2), Paint()..color = _accent);
    final face = Rect.fromCenter(center: c, width: r * 2 * sx, height: r * 2);
    canvas.drawOval(
        face,
        Paint()
          ..shader = LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: turn >= 0 ? [Colors.white.withValues(alpha: on ? 0.95 : 0.8), _main, _accent] : [_main, _accent, _accent],
            stops: const [0, 0.45, 1],
          ).createShader(face));
    canvas.drawOval(
        Rect.fromCenter(center: c, width: r * 1.42 * sx, height: r * 1.42),
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 0.7
          ..color = _cut.withValues(alpha: 0.6));
    canvas.drawRect(Rect.fromCenter(center: c, width: 3.6 * sx, height: 3.6), Paint()..color = _cut);
    // 角上一闪
    final g = math.pow(math.max(0.0, math.sin(_p(2) - 0.6)), 4).toDouble();
    _sparkle(canvas, const Offset(19.6, 4.4), 0.8 + 2.6 * g * _amp, Colors.white.withValues(alpha: (on ? 1.0 : 0.6) * g));
  }

  void _bubble(Canvas canvas) {
    final stroke = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.6
      ..strokeJoin = StrokeJoin.round
      ..color = _main;
    final bubble = Path()
      ..addRRect(RRect.fromRectAndRadius(const Rect.fromLTRB(2.4, 7.4, 17.6, 19), const Radius.circular(5)))
      ..moveTo(6, 19)
      ..lineTo(4.6, 22.6)
      ..lineTo(10, 19);
    canvas.drawPath(bubble, stroke);
    // 三个点轮流亮，像在打字
    for (var k = 0; k < 3; k++) {
      final v = math.max(0.0, math.sin(_p(4) - k * 0.9));
      canvas.drawCircle(Offset(6.4 + k * 3.6, 13.2 - 0.8 * v * _amp), 1.15, Paint()..color = _main.withValues(alpha: 0.4 + 0.6 * v));
    }
    // 右上方冒出小心形
    final n = on ? 2 : 1;
    for (var k = 0; k < n; k++) {
      final u = (t * 2 + k * 0.5) % 1;
      final a = math.sin(u * math.pi);
      final o = Offset(19.2 + 1.4 * math.sin(u * _tau + k * 2), 10.5 - 8.5 * u);
      canvas.drawPath(_heart(o, 1.5 + 1.3 * u), Paint()..color = (on ? light : Colors.white).withValues(alpha: (on ? 1.0 : 0.6) * a));
    }
  }

  void _lotus(Canvas canvas) {
    final b = 0.5 - 0.5 * math.cos(_p(2)); // 一吸一呼
    // 水纹
    for (var k = 0; k < 2; k++) {
      final u = (t * 2 + k * 0.5) % 1;
      final rx = 3.5 + 7.5 * u;
      canvas.drawOval(
          Rect.fromCenter(center: const Offset(12, 20.2), width: rx * 2, height: rx * 0.56),
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = 0.9
            ..color = _main.withValues(alpha: (1 - u) * (on ? 0.75 : 0.45)));
    }
    const base = Offset(12, 18.4);
    void petal(double angle, double len, double width, Color color) {
      canvas.save();
      canvas.translate(base.dx, base.dy);
      canvas.rotate(angle);
      canvas.drawPath(
          Path()
            ..moveTo(0, 0)
            ..quadraticBezierTo(width, -len * 0.55, 0, -len)
            ..quadraticBezierTo(-width, -len * 0.55, 0, 0)
            ..close(),
          Paint()..color = color);
      canvas.restore();
    }

    final open = b * _amp;
    petal(-1.2 - 0.12 * open, 6.4, 3.0, _accent);
    petal(1.2 + 0.12 * open, 6.4, 3.0, _accent);
    petal(-0.62 - 0.16 * open, 9.2, 3.6, _main.withValues(alpha: on ? 0.9 : 0.55));
    petal(0.62 + 0.16 * open, 9.2, 3.6, _main.withValues(alpha: on ? 0.9 : 0.55));
    petal(0, 11 + 1.4 * open, 3.9, _main);
    // 花心一点光
    canvas.drawCircle(base.translate(0, -1.2), 1.0 + 0.5 * b, Paint()..color = Colors.white.withValues(alpha: (on ? 0.9 : 0.4) * (0.5 + 0.5 * b)));
  }

  void _gift(Canvas canvas) {
    // 盖子隔一会儿轻轻一跳
    final hop = math.pow(math.max(0.0, math.sin(_p(2))), 8).toDouble() * 1.6 * _amp;
    final fill = Paint()..color = _main;
    final cut = Paint()..color = _cut;
    final body = RRect.fromRectAndRadius(const Rect.fromLTRB(5, 12, 19, 21), const Radius.circular(1.6));
    canvas.drawRRect(body, fill);
    canvas.drawRect(const Rect.fromLTRB(11, 12, 13, 21), cut);
    canvas.save();
    canvas.translate(0, -hop);
    canvas.rotate(0.04 * hop);
    canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTRB(3.8, 8.6, 20.2, 12), const Radius.circular(1.4)), fill);
    canvas.drawRect(const Rect.fromLTRB(11, 8.6, 13, 12), cut);
    final bow = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5
      ..color = _main;
    canvas.drawPath(
        Path()
          ..moveTo(12, 8.4)
          ..cubicTo(9.5, 4.2, 6.4, 6.4, 8.6, 8.4)
          ..moveTo(12, 8.4)
          ..cubicTo(14.5, 4.2, 17.6, 6.4, 15.4, 8.4),
        bow);
    canvas.restore();
    // 旁边的闪光，和盖子错开
    final g = math.pow(math.max(0.0, math.sin(_p(2) - 1.2)), 3).toDouble();
    _sparkle(canvas, const Offset(20.6, 4), 0.8 + 2.6 * g * _amp, Colors.white.withValues(alpha: (on ? 1.0 : 0.6) * g));
    final g2 = math.pow(math.max(0.0, math.sin(_p(2) + 1.8)), 3).toDouble();
    _sparkle(canvas, const Offset(3.2, 5.2), 0.6 + 1.6 * g2 * _amp, (on ? light : Colors.white).withValues(alpha: (on ? 0.9 : 0.45) * g2));
  }

  void _me(Canvas canvas) {
    final b = 0.5 - 0.5 * math.cos(_p(2));
    // 身后一团柔光
    canvas.drawCircle(
        const Offset(12, 13),
        9.5,
        Paint()
          ..shader = RadialGradient(colors: [_main.withValues(alpha: (on ? 0.28 : 0.12) * (0.4 + 0.6 * b)), _main.withValues(alpha: 0)])
              .createShader(Rect.fromCircle(center: const Offset(12, 13), radius: 9.5)));
    final fill = Paint()..color = _main;
    canvas.drawCircle(const Offset(12, 11.2), 3.5, fill);
    canvas.drawPath(
        Path()
          ..moveTo(5.4, 21.4)
          ..cubicTo(5.4, 15.6, 18.6, 15.6, 18.6, 21.4)
          ..close(),
        fill);
    // 头顶的光环
    final s = 1 + 0.1 * b * _amp;
    canvas.drawOval(
        Rect.fromCenter(center: Offset(12, 5.2 - 0.5 * b * _amp), width: 8.6 * s, height: 2.7 * s),
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.1
          ..color = (on ? light : Colors.white).withValues(alpha: on ? 0.55 + 0.45 * b : 0.3 + 0.3 * b));
  }

  static Path _heart(Offset c, double s) => Path()
    ..moveTo(c.dx, c.dy + s * 0.8)
    ..cubicTo(c.dx - s * 1.2, c.dy, c.dx - s * 0.8, c.dy - s * 0.9, c.dx, c.dy - s * 0.35)
    ..cubicTo(c.dx + s * 0.8, c.dy - s * 0.9, c.dx + s * 1.2, c.dy, c.dx, c.dy + s * 0.8)
    ..close();

  static void _sparkle(Canvas canvas, Offset c, double r, Color color) {
    if (color.a < 0.02) return;
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
  bool shouldRepaint(_TabIconPainter old) => old.kind != kind || old.on != on || old.light != light || old.deep != deep || old.clock != clock;
}
