import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../app/skin.dart' show displayFont;

/// 许愿殿里压在三维画面上的控件。
/// 颜色都从场景里取：朱漆柱子、鎏金、宣纸墙、黛瓦、木头、麻绳，
/// 这样界面像是从同一个世界里裁出来的。
abstract final class SancColors {
  /// 朱漆
  static const vermilion = Color(0xFFC8452F);
  static const vermilionDeep = Color(0xFF9B3324);

  /// 鎏金
  static const gold = Color(0xFFE8BB4D);
  static const goldDeep = Color(0xFFC39535);

  /// 朱漆上的小字用亮一点的金，不然对比不够
  static const goldLit = Color(0xFFF0C95F);

  /// 宣纸
  static const paper = Color(0xFFF3E8CF);
  static const paperShade = Color(0xFFE2D4B2);

  /// 墨
  static const ink = Color(0xFF2B2420);

  /// 黛瓦
  static const slate = Color(0xFF41656F);
  static const slateDeep = Color(0xFF2F505A);

  /// 木
  static const wood = Color(0xFF8A5A34);

  /// 麻绳
  static const rope = Color(0xFFDCC790);
  static const ropeShade = Color(0xFFB9A26C);

  /// 底部弹层的底色：暖的墨褐
  static const sheet = Color(0xFF1E1814);
}

/// 控件上的字：一律用宋体，粗，字距拉开
TextStyle sancLabel(double size, Color color, {double spacing = 2, List<Shadow>? shadows}) => TextStyle(
      fontFamily: displayFont,
      fontSize: size,
      height: 1.2,
      leadingDistribution: TextLeadingDistribution.even,
      fontWeight: FontWeight.w700,
      letterSpacing: spacing,
      color: color,
      shadows: shadows,
    );

/// 按下去缩一点，松手弹回。印章、瓦牌、弹层里的小牌子共用。
class _Press extends StatefulWidget {
  final VoidCallback? onTap;
  final Widget child;
  const _Press({required this.onTap, required this.child});

  @override
  State<_Press> createState() => _PressState();
}

class _PressState extends State<_Press> {
  bool _down = false;

  void _set(bool v) {
    if (_down != v) setState(() => _down = v);
  }

  @override
  Widget build(BuildContext context) {
    final still = MediaQuery.disableAnimationsOf(context);
    return Semantics(
      button: true,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: widget.onTap,
        onTapDown: (_) => _set(true),
        onTapUp: (_) => _set(false),
        onTapCancel: () => _set(false),
        child: AnimatedScale(
          scale: _down ? 0.94 : 1,
          duration: still ? Duration.zero : const Duration(milliseconds: 120),
          curve: Curves.easeOut,
          child: widget.child,
        ),
      ),
    );
  }
}

// ── 底部：一根麻绳，上面挂着许愿木牌 ──

/// 一块木牌上的事
class PlaqueAction {
  final String label;
  final bool primary;
  final VoidCallback onTap;
  const PlaqueAction(this.label, {this.primary = false, required this.onTap});
}

/// 此刻能做的事：横着一根麻绳，每件事是挂在绳上的一块许愿木牌，可以左右拖。
/// 第一块是朱漆金字，其余是宣纸色墨字。
class PlaqueBar extends StatefulWidget {
  /// 整条的高度（绳子 + 红绳 + 木牌 + 影子），整条都能点
  static const double height = 88;

  /// 绳子在两块牌子之间的高度；挂牌子的地方往下坠一点
  static const double ropeY = 7;
  static const double sag = 3;

  /// 木牌顶边、木牌的高度、最窄的宽度
  static const double plaqueTop = 20;
  static const double plaqueHeight = 60;
  static const double plaqueMinWidth = 64;

  /// 两块牌子之间的空隙、第一块离屏幕边的距离
  static const double gap = 10;
  static const double lead = 18;

  final List<PlaqueAction> actions;

  /// 看得见的时候才轻轻晃，藏起来就停
  final bool active;

  const PlaqueBar({super.key, required this.actions, this.active = true});

  @override
  State<PlaqueBar> createState() => _PlaqueBarState();
}

class _PlaqueBarState extends State<PlaqueBar> with SingleTickerProviderStateMixin {
  late final AnimationController _sway = AnimationController(vsync: this, duration: const Duration(seconds: 7));
  bool _still = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _still = MediaQuery.disableAnimationsOf(context);
    _sync();
  }

  @override
  void didUpdateWidget(PlaqueBar old) {
    super.didUpdateWidget(old);
    if (old.active != widget.active) _sync();
  }

  void _sync() {
    final run = widget.active && !_still;
    if (run && !_sway.isAnimating) _sway.repeat();
    if (!run && _sway.isAnimating) _sway.stop();
  }

  @override
  void dispose() {
    _sway.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(
      child: ClipRect(
        child: SizedBox(
          height: PlaqueBar.height,
          width: double.infinity,
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            clipBehavior: Clip.none,
            child: Row(children: [
              // 绳子两头画出屏幕外，拖到头回弹的时候也不会断
              const _RopeEnd(toLeft: true),
              for (var i = 0; i < widget.actions.length; i++) _Plaque(action: widget.actions[i], index: i, sway: _still ? null : _sway),
              const _RopeEnd(toLeft: false),
            ]),
          ),
        ),
      ),
    );
  }
}

/// 画一段麻绳：底下一道影子，深色的边，浅色的芯，再加一排斜纹
void _paintRope(Canvas canvas, Path path) {
  canvas.drawPath(
    path.shift(const Offset(0, 1.8)),
    Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.4
      ..color = const Color(0x4D000000)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 1.5),
  );
  canvas.drawPath(
    path,
    Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.8
      ..color = SancColors.ropeShade,
  );
  canvas.drawPath(
    path,
    Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.4
      ..color = SancColors.rope,
  );
  final twist = Paint()
    ..strokeWidth = 0.9
    ..strokeCap = StrokeCap.round
    ..color = const Color(0xCC9C8656);
  for (final m in path.computeMetrics()) {
    for (var d = 2.0; d < m.length; d += 4.4) {
      final t = m.getTangentForOffset(d);
      if (t == null) continue;
      final dir = t.vector;
      final n = Offset(-dir.dy, dir.dx);
      canvas.drawLine(t.position + n - dir * 0.9, t.position - n + dir * 0.9, twist);
    }
  }
}

/// 绳子的两头：平着伸到屏幕外面去
class _RopeEnd extends StatelessWidget {
  final bool toLeft;
  const _RopeEnd({required this.toLeft});

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(
      child: CustomPaint(
        size: const Size(PlaqueBar.lead - PlaqueBar.gap / 2, PlaqueBar.height),
        painter: _RopeEndPainter(toLeft),
      ),
    );
  }
}

class _RopeEndPainter extends CustomPainter {
  final bool toLeft;
  const _RopeEndPainter(this.toLeft);

  @override
  void paint(Canvas canvas, Size size) {
    const far = 600.0;
    final path = Path()
      ..moveTo(toLeft ? -far : 0, PlaqueBar.ropeY)
      ..lineTo(toLeft ? size.width : size.width + far, PlaqueBar.ropeY);
    _paintRope(canvas, path);
  }

  @override
  bool shouldRepaint(_RopeEndPainter old) => old.toLeft != toLeft;
}

/// 一块木牌头顶上的那段绳子：两边平，中间被牌子坠下去一点。
/// 每块牌子各画各的一段，两端高度和方向都一样，拖动的时候接得上。
class _RopeSegmentPainter extends CustomPainter {
  const _RopeSegmentPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    const y0 = PlaqueBar.ropeY, y1 = PlaqueBar.ropeY + PlaqueBar.sag;
    final path = Path()
      ..moveTo(0, y0)
      ..cubicTo(w * 0.22, y0, w * 0.30, y1, w * 0.5, y1)
      ..cubicTo(w * 0.70, y1, w * 0.78, y0, w, y0);
    _paintRope(canvas, path);
  }

  @override
  bool shouldRepaint(_RopeSegmentPainter old) => false;
}

class _Plaque extends StatefulWidget {
  final PlaqueAction action;
  final int index;

  /// 共用的一个慢慢走的钟，每块牌子按自己的相位晃；null 就不晃
  final Animation<double>? sway;
  const _Plaque({required this.action, required this.index, required this.sway});

  @override
  State<_Plaque> createState() => _PlaqueState();
}

class _PlaqueState extends State<_Plaque> with SingleTickerProviderStateMixin {
  /// 闲着的时候最多晃 1.2 度；按下去荡 4.5 度
  static const _maxSway = 1.2 * math.pi / 180;
  static const _swing = 4.5 * math.pi / 180;

  late final AnimationController _press = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 140),
    reverseDuration: const Duration(milliseconds: 180),
  )..addStatusListener(_onStatus);
  bool _held = false;

  // 点得很快的时候也要让牌子荡完一下再回来
  void _onStatus(AnimationStatus s) {
    if (s == AnimationStatus.completed && !_held) _press.reverse();
  }

  void _down() {
    _held = true;
    _press.forward();
  }

  void _up() {
    _held = false;
    if (_press.isCompleted) _press.reverse();
  }

  @override
  void dispose() {
    _press.dispose();
    super.dispose();
  }

  double _angle(bool still) {
    var a = 0.0;
    final sway = widget.sway;
    if (sway != null) {
      // 相位按黄金角错开，相邻的牌子不会一起晃
      final ph = widget.index * 2.399;
      final t = sway.value * 2 * math.pi;
      a += _maxSway * (0.7 * math.sin(t + ph) + 0.3 * math.sin(2 * t + ph * 1.7));
    }
    if (!still) a += (widget.index.isEven ? 1 : -1) * _swing * Curves.easeOut.transform(_press.value);
    return a;
  }

  @override
  Widget build(BuildContext context) {
    final a = widget.action;
    final still = MediaQuery.disableAnimationsOf(context);
    return Semantics(
      button: true,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: a.onTap,
        onTapDown: (_) => _down(),
        onTapUp: (_) => _up(),
        onTapCancel: _up,
        child: Stack(children: [
          const Positioned.fill(child: RepaintBoundary(child: CustomPaint(painter: _RopeSegmentPainter()))),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: PlaqueBar.gap / 2),
            child: AnimatedBuilder(
              animation: Listenable.merge([widget.sway, _press]),
              // 绕着红绳系在麻绳上的那一点转
              builder: (context, child) => Transform(
                alignment: Alignment.topCenter,
                origin: const Offset(0, PlaqueBar.ropeY + PlaqueBar.sag),
                transform: Matrix4.rotationZ(_angle(still)),
                child: child,
              ),
              // 牌子自己一层：晃的时候只动这一层的位置，不重画
              child: RepaintBoundary(
                child: CustomPaint(
                  painter: _PlaquePainter(primary: a.primary, seed: a.label.hashCode ^ widget.index, press: _press),
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(minWidth: PlaqueBar.plaqueMinWidth, minHeight: PlaqueBar.height, maxHeight: PlaqueBar.height),
                    child: Padding(
                      // 字放在孔下面那一块的正中；左边多 2 是把最后一个字后面的字距补回来
                      padding: const EdgeInsets.fromLTRB(15, PlaqueBar.plaqueTop + 6, 13, PlaqueBar.height - PlaqueBar.plaqueTop - PlaqueBar.plaqueHeight),
                      child: Center(
                        widthFactor: 1,
                        child: Text(
                          a.label,
                          maxLines: 1,
                          softWrap: false,
                          textScaler: MediaQuery.textScalerOf(context).clamp(maxScaleFactor: 1.3),
                          style: a.primary
                              ? sancLabel(16, SancColors.goldLit, shadows: const [Shadow(color: Color(0xB36E2014), offset: Offset(0, 1), blurRadius: 0.5)])
                              : sancLabel(16, SancColors.ink),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ]),
      ),
    );
  }
}

/// 木牌的轮廓：上面两个角削掉（像屋顶），下面两个角略圆
Path _plaquePath(Rect r, double cut, double rad) => Path()
  ..moveTo(r.left + cut, r.top)
  ..lineTo(r.right - cut, r.top)
  ..lineTo(r.right, r.top + cut)
  ..lineTo(r.right, r.bottom - rad)
  ..arcToPoint(Offset(r.right - rad, r.bottom), radius: Radius.circular(rad))
  ..lineTo(r.left + rad, r.bottom)
  ..arcToPoint(Offset(r.left, r.bottom - rad), radius: Radius.circular(rad))
  ..lineTo(r.left, r.top + cut)
  ..close();

class _PlaquePainter extends CustomPainter {
  final bool primary;
  final int seed;
  final Animation<double> press;
  _PlaquePainter({required this.primary, required this.seed, required this.press}) : super(repaint: press);

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, cx = w / 2;
    const top = PlaqueBar.plaqueTop, h = PlaqueBar.plaqueHeight;
    final pivot = Offset(cx, PlaqueBar.ropeY + PlaqueBar.sag);
    final hole = Offset(cx, top + 9.5);
    final rect = Rect.fromLTWH(0.75, top, w - 1.5, h);
    final body = _plaquePath(rect, 11, 4);

    final cordEdge = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = 2.8
      ..color = const Color(0xFF8E2B1E);
    final cord = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = 1.5
      ..color = SancColors.vermilion;

    // 绕到牌子背后的那股红绳
    final back = Offset(cx + 1.6, top + 3);
    canvas.drawLine(pivot, back, cordEdge);
    canvas.drawLine(pivot, back, cord);

    // 影子、厚度、牌面
    canvas.drawPath(
      body.shift(const Offset(0, 3.5)),
      Paint()
        ..color = const Color(0x57000000)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4),
    );
    canvas.drawPath(body.shift(const Offset(0, 2.5)), Paint()..color = primary ? const Color(0xFF7E2619) : const Color(0xFF6E4526));
    canvas.drawPath(body, Paint()..color = primary ? SancColors.vermilion : SancColors.paper);

    // 很淡的几道木纹，每块牌子不一样，但每次画出来都一样
    canvas.save();
    canvas.clipPath(body);
    final rnd = math.Random(seed);
    final grain = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.8
      ..color = primary ? const Color(0x389B3324) : const Color(0x1C8A5A34);
    for (var i = 0; i < 6; i++) {
      final y = top + h * (0.10 + 0.16 * i) + rnd.nextDouble() * 4 - 2;
      final x0 = rnd.nextDouble() * w * 0.3 - 4, x1 = w + 4 - rnd.nextDouble() * w * 0.3;
      canvas.drawPath(
        Path()
          ..moveTo(x0, y)
          ..quadraticBezierTo((x0 + x1) / 2, y + rnd.nextDouble() * 5 - 2.5, x1, y + rnd.nextDouble() * 2 - 1),
        grain,
      );
    }
    canvas.restore();

    // 木色（朱漆的是深红）的细边，里面再套一圈细线
    canvas.drawPath(
      body,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeJoin = StrokeJoin.round
        ..strokeWidth = 1.2
        ..color = primary ? SancColors.vermilionDeep : SancColors.wood,
    );
    canvas.drawPath(
      _plaquePath(rect.deflate(4), 8.7, 2),
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeJoin = StrokeJoin.round
        ..strokeWidth = 0.8
        ..color = primary ? const Color(0xD9E8BB4D) : const Color(0x808A5A34),
    );

    // 按下去暗一点
    if (press.value > 0) canvas.drawPath(body, Paint()..color = Color.fromRGBO(0, 0, 0, 0.14 * press.value));

    // 孔，前面那股红绳穿进去，绳上打个结
    canvas.drawCircle(hole, 2.7, Paint()..color = primary ? const Color(0xFF5E1B11) : const Color(0xFF4A3220));
    final front = pivot.translate(-1.2, 0);
    canvas.drawLine(front, hole, cordEdge);
    canvas.drawLine(front, hole, cord);
    final knot = RRect.fromRectAndRadius(Rect.fromCenter(center: pivot, width: 6.4, height: 6.8), const Radius.circular(2));
    canvas.drawRRect(knot, Paint()..color = SancColors.vermilion);
    canvas.drawRRect(
      knot,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 0.9
        ..color = const Color(0xFF8E2B1E),
    );
  }

  @override
  bool shouldRepaint(_PlaquePainter old) => old.primary != primary || old.seed != seed || old.press != press;
}

// ── 左上角：离开，一枚竖着的朱印 ──

class SealBackButton extends StatelessWidget {
  /// 印面的大小；外面再留一圈好点
  static const Size stamp = Size(38, 56);
  static const EdgeInsets hit = EdgeInsets.fromLTRB(8, 4, 8, 4);

  final VoidCallback onTap;
  const SealBackButton({super.key, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final style = sancLabel(18, SancColors.paper, spacing: 0);
    return _Press(
      onTap: onTap,
      child: Padding(
        padding: hit,
        child: CustomPaint(
          painter: const _SealPainter(),
          child: SizedBox.fromSize(
            size: stamp,
            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              Text('离', textScaler: TextScaler.noScaling, style: style),
              Text('开', textScaler: TextScaler.noScaling, style: style),
            ]),
          ),
        ),
      ),
    );
  }
}

class _SealPainter extends CustomPainter {
  const _SealPainter();

  /// 印边上磕掉的几个小口：位置（按宽高的比例）和大小是写死的，不是每帧随机
  static const _nicks = [
    (0.0, 0.26, 1.5),
    (1.0, 0.67, 1.7),
    (0.30, 1.0, 1.3),
    (0.72, 0.0, 1.2),
    (1.0, 0.15, 1.0),
    (0.0, 0.80, 1.1),
    (0.86, 1.0, 0.9),
  ];

  @override
  void paint(Canvas canvas, Size size) {
    final r = Offset.zero & size;
    final block = Path()..addRRect(RRect.fromRectAndRadius(r, const Radius.circular(5)));
    final nicks = Path();
    for (final (x, y, d) in _nicks) {
      nicks.addOval(Rect.fromCircle(center: Offset(x * size.width, y * size.height), radius: d));
    }
    final body = Path.combine(PathOperation.difference, block, nicks);
    canvas.drawPath(
      body.shift(const Offset(0, 2)),
      Paint()
        ..color = const Color(0x52000000)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3),
    );
    canvas.drawPath(body, Paint()..color = SancColors.vermilion);
    // 里面一圈米色的细框，有两处印得浅（盖掉一小截）
    final frame = r.deflate(3.5);
    canvas.drawRRect(
      RRect.fromRectAndRadius(frame, const Radius.circular(2.5)),
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.1
        ..color = const Color(0xE6F3E8CF),
    );
    final worn = Paint()..color = SancColors.vermilion;
    canvas.drawCircle(Offset(frame.left, frame.top + frame.height * 0.58), 1.6, worn);
    canvas.drawCircle(Offset(frame.left + frame.width * 0.66, frame.bottom), 1.4, worn);
  }

  @override
  bool shouldRepaint(_SealPainter old) => false;
}

// ── 右边：换视角的一串竹签 ──

/// 四枚竹签用一根麻绳串着挂在瓦牌下面：俯（俯视）、平（平视）、仰（仰视）、眼（第一人称）。
/// 正在用的那一枚是朱漆金字，其余是素竹墨字。放大以后底下多挂一枚小牌写倍数，点它还原。
class ViewSlips extends StatelessWidget {
  static const modes = ['top', 'level', 'low', 'first'];
  static const _glyph = {'top': '俯', 'level': '平', 'low': '仰', 'first': '眼'};
  static const _name = {'top': '俯视', 'level': '平视', 'low': '仰视', 'first': '第一人称'};
  static const double slipW = 34, slipH = 36, gap = 7;

  final String mode;
  final double zoom;
  final ValueChanged<String> onChanged;
  final VoidCallback onResetZoom;
  const ViewSlips({super.key, required this.mode, required this.zoom, required this.onChanged, required this.onResetZoom});

  @override
  Widget build(BuildContext context) {
    final zoomed = zoom > 1.05;
    final count = modes.length + (zoomed ? 1 : 0);
    return CustomPaint(
      painter: _SlipRopePainter(count),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        const SizedBox(height: gap),
        for (final m in modes) ...[
          Semantics(
            button: true,
            selected: m == mode,
            label: _name[m],
            excludeSemantics: true,
            child: _Press(
              onTap: () => onChanged(m),
              child: CustomPaint(
                painter: _SlipPainter(active: m == mode),
                child: SizedBox(
                  width: slipW,
                  height: slipH,
                  child: Center(
                    child: Text(_glyph[m]!,
                        textScaler: TextScaler.noScaling,
                        style: sancLabel(16, m == mode ? SancColors.goldLit : SancColors.ink, spacing: 0)),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: gap),
        ],
        if (zoomed)
          Semantics(
            button: true,
            label: '放大 ${zoom.toStringAsFixed(1)} 倍，点一下还原',
            excludeSemantics: true,
            child: _Press(
              onTap: onResetZoom,
              child: CustomPaint(
                painter: const _SlipPainter(active: false, paper: true),
                child: SizedBox(
                  width: slipW,
                  height: 26,
                  child: Center(
                    child: Text('×${zoom.toStringAsFixed(zoom >= 10 ? 0 : 1)}',
                        textScaler: TextScaler.noScaling, style: sancLabel(11, SancColors.vermilionDeep, spacing: 0)),
                  ),
                ),
              ),
            ),
          ),
      ]),
    );
  }
}

/// 一枚竹签：上下各一道竹节，左边一线高光
class _SlipPainter extends CustomPainter {
  final bool active, paper;
  const _SlipPainter({required this.active, this.paper = false});

  @override
  void paint(Canvas canvas, Size size) {
    final r = RRect.fromRectAndRadius(Offset.zero & size, const Radius.circular(5));
    canvas.drawRRect(r.shift(const Offset(0, 2)), Paint()..color = const Color(0x59000000));
    final fill = active ? SancColors.vermilion : paper ? SancColors.paper : const Color(0xFFE6D6A4);
    final edge = active ? SancColors.vermilionDeep : paper ? SancColors.paperShade : const Color(0xFFB79B5E);
    canvas.drawRRect(r, Paint()..color = fill);
    canvas.save();
    canvas.clipRRect(r);
    // 竹节
    final node = Paint()
      ..color = edge.withValues(alpha: 0.85)
      ..strokeWidth = 1.2;
    if (!paper) {
      canvas.drawLine(Offset(0, 5), Offset(size.width, 5), node);
      canvas.drawLine(Offset(0, size.height - 5), Offset(size.width, size.height - 5), node);
    }
    canvas.drawRect(Rect.fromLTWH(0, 0, 3, size.height), Paint()..color = Colors.white.withValues(alpha: active ? 0.16 : 0.34));
    canvas.drawRect(Rect.fromLTWH(size.width - 3, 0, 3, size.height), Paint()..color = Colors.black.withValues(alpha: 0.1));
    canvas.restore();
    canvas.drawRRect(
        r.deflate(0.6),
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.2
          ..color = active ? SancColors.gold : edge);
  }

  @override
  bool shouldRepaint(_SlipPainter old) => old.active != active || old.paper != paper;
}

/// 把竹签串起来的那根麻绳：从最上面一直垂到最后一枚后面
class _SlipRopePainter extends CustomPainter {
  final int count;
  const _SlipRopePainter(this.count);

  @override
  void paint(Canvas canvas, Size size) {
    final x = size.width / 2;
    final p = Paint()
      ..strokeCap = StrokeCap.round
      ..strokeWidth = 3
      ..color = SancColors.ropeShade;
    canvas.drawLine(Offset(x, 0), Offset(x, size.height - 8), p);
    canvas.drawLine(
        Offset(x - 0.6, 0),
        Offset(x - 0.6, size.height - 8),
        Paint()
          ..strokeCap = StrokeCap.round
          ..strokeWidth = 1.2
          ..color = SancColors.rope);
  }

  @override
  bool shouldRepaint(_SlipRopePainter old) => old.count != count;
}

// ── 右上角：天色和天气，一块黛瓦色的滴水瓦牌 ──

class SkyTag extends StatelessWidget {
  /// 瓦牌的高度（平的那一块 32，中间往下垂 8，再加 2 的厚度）
  static const double bodyHeight = 32;
  static const double tagHeight = 42;
  static const EdgeInsets hit = EdgeInsets.fromLTRB(10, 4, 0, 2);

  final String label;

  /// dawn / day / dusk / night
  final String time;

  /// clear / rain / storm / snow
  final String weather;
  final VoidCallback onTap;
  const SkyTag({super.key, required this.label, required this.time, required this.weather, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final glyph = switch (weather) {
      'rain' => _Sky.rain,
      'storm' => _Sky.storm,
      'snow' => _Sky.snow,
      _ => time == 'night' ? _Sky.moon : _Sky.sun,
    };
    return _Press(
      onTap: onTap,
      child: Padding(
        padding: hit,
        child: CustomPaint(
          painter: const _TilePainter(),
          child: SizedBox(
            height: tagHeight,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 11, tagHeight - bodyHeight),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                CustomPaint(size: const Size(16, 16), painter: _SkyGlyphPainter(glyph)),
                const SizedBox(width: 7),
                Text(
                  label,
                  maxLines: 1,
                  textScaler: MediaQuery.textScalerOf(context).clamp(maxScaleFactor: 1.2),
                  style: sancLabel(13.5, SancColors.paper, spacing: 1.5),
                ),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}

/// 滴水瓦的轮廓：上面平，下边正中垂下一个尖
Path _tilePath(Rect r, double rad, double tabHalf, double drop) {
  final cx = r.center.dx, b = r.bottom - drop;
  final c = Radius.circular(rad);
  return Path()
    ..moveTo(r.left + rad, r.top)
    ..lineTo(r.right - rad, r.top)
    ..arcToPoint(Offset(r.right, r.top + rad), radius: c)
    ..lineTo(r.right, b - rad)
    ..arcToPoint(Offset(r.right - rad, b), radius: c)
    ..lineTo(cx + tabHalf, b)
    ..quadraticBezierTo(cx + tabHalf * 0.3, b + drop * 0.08, cx, r.bottom)
    ..quadraticBezierTo(cx - tabHalf * 0.3, b + drop * 0.08, cx - tabHalf, b)
    ..lineTo(r.left + rad, b)
    ..arcToPoint(Offset(r.left, b - rad), radius: c)
    ..lineTo(r.left, r.top + rad)
    ..arcToPoint(Offset(r.left + rad, r.top), radius: c)
    ..close();
}

class _TilePainter extends CustomPainter {
  const _TilePainter();

  @override
  void paint(Canvas canvas, Size size) {
    final r = Rect.fromLTWH(0, 0, size.width, size.height - 2);
    final body = _tilePath(r, 5, 20, 8);
    canvas.drawPath(
      body.shift(const Offset(0, 3)),
      Paint()
        ..color = const Color(0x52000000)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3.5),
    );
    canvas.drawPath(body.shift(const Offset(0, 2)), Paint()..color = SancColors.slateDeep);
    canvas.drawPath(body, Paint()..color = SancColors.slate);
    // 一圈金色的细线
    canvas.drawPath(
      _tilePath(r.deflate(3), 3, 16.5, 6.2),
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeJoin = StrokeJoin.round
        ..strokeWidth = 0.8
        ..color = const Color(0xD9E8BB4D),
    );
  }

  @override
  bool shouldRepaint(_TilePainter old) => false;
}

enum _Sky { sun, moon, rain, storm, snow }

/// 天气的小图形，按 16×16 画，自己缩放
class _SkyGlyphPainter extends CustomPainter {
  final _Sky kind;
  const _SkyGlyphPainter(this.kind);

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 16);
    final fill = Paint()..color = SancColors.gold;
    final line = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = 1.3
      ..color = SancColors.gold;
    const c = Offset(8, 8);

    void cloud() {
      canvas.drawCircle(const Offset(5.3, 7.3), 2.9, fill);
      canvas.drawCircle(const Offset(9.0, 5.7), 3.7, fill);
      canvas.drawCircle(const Offset(12.1, 7.9), 2.5, fill);
      canvas.drawRRect(RRect.fromLTRBR(2.6, 7.2, 14.4, 10.3, const Radius.circular(1.5)), fill);
    }

    switch (kind) {
      case _Sky.sun:
        canvas.drawCircle(c, 3.3, fill);
        for (var i = 0; i < 8; i++) {
          final d = Offset(math.cos(i * math.pi / 4), math.sin(i * math.pi / 4));
          canvas.drawLine(c + d * 5.3, c + d * 7.1, line);
        }
      case _Sky.moon:
        canvas.drawPath(
          Path.combine(
            PathOperation.difference,
            Path()..addOval(Rect.fromCircle(center: c, radius: 6.3)),
            Path()..addOval(Rect.fromCircle(center: const Offset(11.0, 5.8), radius: 5.4)),
          ),
          fill,
        );
      case _Sky.rain:
        canvas.translate(0, -1);
        cloud();
        for (final x in const [5.2, 8.6, 12.0]) {
          canvas.drawLine(Offset(x, 12.6), Offset(x - 0.9, 15.2), line);
        }
      case _Sky.storm:
        canvas.translate(0, -1.6);
        cloud();
        canvas.drawPath(
          Path()
            ..moveTo(9.4, 11.2)
            ..lineTo(6.6, 14.3)
            ..lineTo(8.5, 14.3)
            ..lineTo(7.4, 17.2)
            ..lineTo(10.9, 13.2)
            ..lineTo(9.0, 13.2)
            ..lineTo(10.3, 11.2)
            ..close(),
          fill,
        );
      case _Sky.snow:
        line.strokeWidth = 1.1;
        for (var i = 0; i < 6; i++) {
          final a = i * math.pi / 3 + math.pi / 6;
          final d = Offset(math.cos(a), math.sin(a));
          canvas.drawLine(c, c + d * 6.6, line);
          // 每一枝靠外的地方分两个小叉
          final k = c + d * 4.2;
          for (final s in const [-1, 1]) {
            final b = a + s * math.pi / 4;
            canvas.drawLine(k, k + Offset(math.cos(b), math.sin(b)) * 2.0, line);
          }
        }
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(_SkyGlyphPainter old) => old.kind != kind;
}

// ── 地名下面：一道金色细线，正中一粒小菱形 ──

class TitleOrnament extends StatelessWidget {
  const TitleOrnament({super.key});

  @override
  Widget build(BuildContext context) => const CustomPaint(size: Size(64, 9), painter: _OrnamentPainter());
}

class _OrnamentPainter extends CustomPainter {
  const _OrnamentPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final cy = size.height / 2 - 0.5, cx = size.width / 2;
    void draw(Offset o, Color color) {
      final p = Paint()
        ..color = color
        ..strokeWidth = 1;
      canvas.drawLine(Offset(0, cy) + o, Offset(cx - 7, cy) + o, p);
      canvas.drawLine(Offset(cx + 7, cy) + o, Offset(size.width, cy) + o, p);
      canvas.drawPath(
        Path()
          ..moveTo(cx + o.dx, cy - 3.2 + o.dy)
          ..lineTo(cx + 3.2 + o.dx, cy + o.dy)
          ..lineTo(cx + o.dx, cy + 3.2 + o.dy)
          ..lineTo(cx - 3.2 + o.dx, cy + o.dy)
          ..close(),
        p,
      );
    }

    // 先垫一道暗的，亮的天底下也看得见
    draw(const Offset(0, 1), const Color(0x66000000));
    draw(Offset.zero, SancColors.gold);
  }

  @override
  bool shouldRepaint(_OrnamentPainter old) => false;
}

// ── 摇杆：铜镜一样的罗盘底，上面一枚方孔钱 ──

class JoystickBase extends StatelessWidget {
  const JoystickBase({super.key});

  @override
  Widget build(BuildContext context) => const RepaintBoundary(child: CustomPaint(painter: _CompassPainter(), child: SizedBox.expand()));
}

class _CompassPainter extends CustomPainter {
  const _CompassPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero), r = size.shortestSide / 2;
    canvas.drawCircle(c, r - 1, Paint()..color = const Color(0x5C1C1410));
    canvas.drawCircle(
      c,
      r - 1,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.4
        ..color = const Color(0xE6E8BB4D),
    );
    // 里面一圈很淡的环
    canvas.drawCircle(
      c,
      r * 0.52,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 0.8
        ..color = const Color(0x4DE8BB4D),
    );
    // 东南西北四个小刻度
    final tick = Paint()
      ..strokeCap = StrokeCap.round
      ..strokeWidth = 1.6
      ..color = const Color(0xE6E8BB4D);
    for (var i = 0; i < 4; i++) {
      final d = Offset(math.cos(i * math.pi / 2), math.sin(i * math.pi / 2));
      canvas.drawLine(c + d * (r - 12), c + d * (r - 6.5), tick);
    }
  }

  @override
  bool shouldRepaint(_CompassPainter old) => false;
}

class JoystickCoin extends StatelessWidget {
  const JoystickCoin({super.key});

  @override
  Widget build(BuildContext context) => const RepaintBoundary(child: CustomPaint(painter: _CoinPainter(), child: SizedBox.expand()));
}

class _CoinPainter extends CustomPainter {
  const _CoinPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero), r = size.shortestSide / 2 - 1;
    final hole = Rect.fromCenter(center: c, width: r * 0.52, height: r * 0.52);
    // 圆钱挖掉中间的方孔，孔里透得出底下的画面
    final coin = Path()
      ..fillType = PathFillType.evenOdd
      ..addOval(Rect.fromCircle(center: c, radius: r))
      ..addRect(hole);
    canvas.drawPath(
      coin.shift(const Offset(0, 3)),
      Paint()
        ..color = const Color(0x73000000)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 5),
    );
    canvas.drawPath(
      coin,
      Paint()
        ..shader = const RadialGradient(
          center: Alignment(-0.3, -0.4),
          radius: 0.95,
          colors: [Color(0xFFF2CC6A), SancColors.gold, SancColors.goldDeep],
          stops: [0, 0.55, 1],
        ).createShader(Rect.fromCircle(center: c, radius: r)),
    );
    final rim = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2
      ..color = const Color(0xFFA47A27);
    // 外缘、内圈、方孔的边
    canvas.drawCircle(c, r - 0.6, rim);
    canvas.drawCircle(c, r - 4.6, rim..strokeWidth = 0.8);
    canvas.drawRect(hole.inflate(2.6), rim);
    canvas.drawRect(hole, rim..strokeWidth = 1.1);
  }

  @override
  bool shouldRepaint(_CoinPainter old) => false;
}

// ── 底部弹层和里面的按钮 ──

/// 弹层的底：暖的墨褐色，顶边一道金线
class SanctuarySheet extends StatelessWidget {
  static const double radius = 20;

  final EdgeInsetsGeometry padding;
  final Widget child;
  const SanctuarySheet({super.key, required this.padding, required this.child});

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      foregroundPainter: const _SheetEdgePainter(),
      child: Container(
        decoration: const BoxDecoration(color: Color(0xF71E1814), borderRadius: BorderRadius.vertical(top: Radius.circular(radius))),
        padding: padding,
        child: child,
      ),
    );
  }
}

class _SheetEdgePainter extends CustomPainter {
  const _SheetEdgePainter();

  @override
  void paint(Canvas canvas, Size size) {
    const r = SanctuarySheet.radius;
    canvas.drawPath(
      Path()
        ..moveTo(0.5, r)
        ..arcToPoint(const Offset(r, 0.5), radius: const Radius.circular(r - 0.5))
        ..lineTo(size.width - r, 0.5)
        ..arcToPoint(Offset(size.width - 0.5, r), radius: const Radius.circular(r - 0.5)),
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1
        ..color = const Color(0xCCE8BB4D),
    );
  }

  @override
  bool shouldRepaint(_SheetEdgePainter old) => false;
}

/// 弹层里的小牌子：选中的是朱漆金字，没选中的是一圈宣纸色的线、米色的字
class SanctuaryChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback? onTap;
  const SanctuaryChip(this.label, {super.key, this.selected = false, this.onTap});

  @override
  Widget build(BuildContext context) {
    return _Press(
      onTap: onTap,
      // 看上去 38 高，上下各留 3，点得到的有 44
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Container(
          height: 38,
          // 边线自己还占 1，所以这里左右只留 11.5 和 10；402 宽的屏上「跟着此刻」加四个两字的刚好排一行
          padding: const EdgeInsets.fromLTRB(11.5, 0, 10, 0),
          decoration: ShapeDecoration(
            color: selected ? SancColors.vermilion : const Color(0x00000000),
            shape: BeveledRectangleBorder(
              borderRadius: BorderRadius.circular(5),
              side: BorderSide(color: selected ? const Color(0xCCE8BB4D) : const Color(0x73F3E8CF), width: 1),
            ),
          ),
          child: Center(
            widthFactor: 1,
            child: Text(label, maxLines: 1, style: sancLabel(14, selected ? SancColors.goldLit : SancColors.paper, spacing: 1.5)),
          ),
        ),
      ),
    );
  }
}

/// 弹层里最要紧的那个按钮：一整条朱漆，金字，里面套一圈金线
class LacquerButton extends StatelessWidget {
  final String label;
  final VoidCallback? onTap;
  const LacquerButton(this.label, {super.key, this.onTap});

  @override
  Widget build(BuildContext context) {
    return _Press(
      onTap: onTap,
      child: Container(
        height: 52,
        width: double.infinity,
        padding: const EdgeInsets.all(4),
        decoration: ShapeDecoration(
          color: SancColors.vermilion,
          shape: BeveledRectangleBorder(borderRadius: BorderRadius.circular(9), side: const BorderSide(color: SancColors.vermilionDeep, width: 1)),
        ),
        child: DecoratedBox(
          decoration: ShapeDecoration(
            shape: BeveledRectangleBorder(borderRadius: BorderRadius.circular(6.5), side: const BorderSide(color: Color(0xD9E8BB4D), width: 0.8)),
          ),
          child: Center(
            child: Padding(
              padding: const EdgeInsets.only(left: 4),
              child: Text(label, maxLines: 1, style: sancLabel(17, SancColors.goldLit, spacing: 4)),
            ),
          ),
        ),
      ),
    );
  }
}

// ── 进殿：一对朱漆寺门，场景准备好以后往两边推开 ──

/// 加载时整屏是两扇关着的寺门：朱漆门板、五排铜门钉、一对铺首衔环，门缝里透一线暖光，随着等待一明一暗。
/// [open] 变成 true 时门往两边推开（带一点透视，像真的门往里转），门缝的光涌出来铺满一屏，再淡去，露出后面的岛。
/// 系统开了「减少动态效果」时不推门，直接淡出。
class TempleGate extends StatefulWidget {
  final bool open;
  final String title;
  final VoidCallback? onOpened;
  const TempleGate({super.key, required this.open, required this.title, this.onOpened});

  @override
  State<TempleGate> createState() => _TempleGateState();
}

class _TempleGateState extends State<TempleGate> with TickerProviderStateMixin {
  late final AnimationController _glow = AnimationController(vsync: this, duration: const Duration(milliseconds: 2400))..repeat(reverse: true);
  late final AnimationController _swing = AnimationController(vsync: this, duration: const Duration(milliseconds: 1900));
  bool _gone = false;
  final DateTime _shown = DateTime.now();

  @override
  void initState() {
    super.initState();
    _swing.addStatusListener((s) {
      if (s == AnimationStatus.completed) {
        setState(() => _gone = true);
        widget.onOpened?.call();
      }
    });
    // 第二次进殿时场景早就在了，可能还没画出门就已经「准备好」：一样先关着门站一下，再推开
    if (widget.open) WidgetsBinding.instance.addPostFrameCallback((_) => _openDoors());
  }

  /// 门至少关着 0.8 秒（看清是一对门、门上写着殿名），再推开
  void _openDoors() {
    if (!mounted || _swing.isAnimating || _gone) return;
    final wait = const Duration(milliseconds: 800) - DateTime.now().difference(_shown);
    if (wait > Duration.zero) {
      Future.delayed(wait, _openDoors);
      return;
    }
    _swing.duration = MediaQuery.disableAnimationsOf(context) ? const Duration(milliseconds: 500) : const Duration(milliseconds: 1900);
    _swing.forward(from: 0);
  }

  @override
  void didUpdateWidget(TempleGate old) {
    super.didUpdateWidget(old);
    if (widget.open && !old.open) _openDoors();
    if (!widget.open && old.open) {
      _swing.value = 0;
      setState(() => _gone = false);
    }
  }

  @override
  void dispose() {
    _glow.dispose();
    _swing.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_gone) return const SizedBox.shrink();
    final still = MediaQuery.disableAnimationsOf(context);
    return IgnorePointer(
      child: AnimatedBuilder(
        animation: Listenable.merge([_glow, _swing]),
        builder: (context, _) {
          final t = _swing.value;
          // 0–0.6 推门（先慢、中间快、最后慢），0.35–0.75 门缝的光铺满，0.7–1 整体淡去
          final swing = still ? 0.0 : Curves.easeInOutCubic.transform((t / 0.6).clamp(0.0, 1.0));
          final flood = Curves.easeOut.transform(((t - 0.3) / 0.45).clamp(0.0, 1.0));
          final fade = still ? 1 - t : 1 - Curves.easeIn.transform(((t - 0.7) / 0.3).clamp(0.0, 1.0));
          final seam = 0.35 + 0.35 * Curves.easeInOut.transform(_glow.value);
          return Opacity(
            opacity: fade.clamp(0.0, 1.0),
            child: LayoutBuilder(builder: (context, c) {
              final w = c.maxWidth / 2;
              Widget leaf(bool left) {
                // 门往里转：绕外侧的边转 0 → 80 度，同时往外滑出一点
                final m = Matrix4.identity()
                  ..setEntry(3, 2, 0.0012)
                  ..rotateY((left ? 1 : -1) * swing * 1.4);
                return Positioned(
                  left: left ? -swing * w * 0.15 : null,
                  right: left ? null : -swing * w * 0.15,
                  top: 0,
                  bottom: 0,
                  width: w,
                  child: Transform(
                    alignment: left ? Alignment.centerLeft : Alignment.centerRight,
                    transform: m,
                    child: CustomPaint(painter: _GateLeafPainter(left: left, shade: swing)),
                  ),
                );
              }

              return Stack(fit: StackFit.expand, children: [
                // 门后的光：门开了才看得到
                DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: RadialGradient(
                      colors: [const Color(0xFFFFF4D6), Color.lerp(const Color(0xFFF3D9A0), const Color(0xFFFFF4D6), flood)!, const Color(0xFF2B2420)],
                      stops: [0, 0.35 + 0.5 * flood, 1],
                      radius: 0.7 + 1.2 * flood,
                    ),
                  ),
                ),
                leaf(true),
                leaf(false),
                // 门缝里那一线光
                if (swing < 0.05)
                  Center(
                    child: Container(
                      width: 3,
                      decoration: BoxDecoration(
                        color: Color.lerp(const Color(0x00FFE7B0), const Color(0xFFFFE7B0), seam),
                        boxShadow: [BoxShadow(color: const Color(0xFFFFD98A).withValues(alpha: seam * 0.8), blurRadius: 18, spreadRadius: 2)],
                      ),
                    ),
                  ),
                // 门楣上的匾：竖着写殿名
                Opacity(
                  opacity: (1 - swing * 3).clamp(0.0, 1.0),
                  child: Align(
                    alignment: const Alignment(0, -0.42),
                    child: CustomPaint(
                      painter: const _PlaquePlatePainter(),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 18),
                        child: Column(mainAxisSize: MainAxisSize.min, children: [
                          for (final ch in widget.title.characters)
                            Text(ch, textScaler: TextScaler.noScaling, style: sancLabel(26, SancColors.goldLit, spacing: 0)),
                        ]),
                      ),
                    ),
                  ),
                ),
                // 匾上空加一圈底光，提示在等
                if (flood > 0.01) Opacity(opacity: flood * 0.9, child: const ColoredBox(color: Color(0xFFFFF6E0))),
              ]);
            }),
          );
        },
      ),
    );
  }
}

/// 一扇门：朱漆门板，四周一圈深色门框，五排门钉，靠中缝那边一个铺首衔环
class _GateLeafPainter extends CustomPainter {
  final bool left;
  final double shade;
  const _GateLeafPainter({required this.left, required this.shade});

  @override
  void paint(Canvas canvas, Size size) {
    final r = Offset.zero & size;
    // 门板：竖向的木纹深浅，加推开时变暗（转过去背光）
    canvas.drawRect(
      r,
      Paint()
        ..shader = LinearGradient(
          begin: left ? Alignment.centerLeft : Alignment.centerRight,
          end: left ? Alignment.centerRight : Alignment.centerLeft,
          colors: [Color.lerp(SancColors.vermilionDeep, Colors.black, 0.25 + shade * 0.3)!, Color.lerp(SancColors.vermilion, Colors.black, shade * 0.35)!],
        ).createShader(r),
    );
    final grain = Paint()..color = Colors.black.withValues(alpha: 0.05);
    for (double x = 6; x < size.width; x += 11) {
      canvas.drawRect(Rect.fromLTWH(x, 0, 1.2 + (x * 7 % 3), size.height), grain);
    }
    // 门框
    final frame = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 10
      ..color = Color.lerp(SancColors.vermilionDeep, Colors.black, 0.35)!;
    canvas.drawRect(r.deflate(5), frame);
    // 中腰一道铜带
    final bandY = size.height * 0.62;
    canvas.drawRect(Rect.fromLTWH(0, bandY - 5, size.width, 10), Paint()..color = SancColors.goldDeep);
    canvas.drawRect(Rect.fromLTWH(0, bandY - 5, size.width, 2.5), Paint()..color = SancColors.goldLit.withValues(alpha: 0.7));
    // 门钉：五排，每排五颗，铜钉有高光
    const rows = 5, cols = 5;
    final top = size.height * 0.16, bottom = size.height * 0.88;
    for (int i = 0; i < rows; i++) {
      for (int j = 0; j < cols; j++) {
        final x = size.width * (0.16 + 0.68 * j / (cols - 1));
        final y = top + (bottom - top) * i / (rows - 1);
        final c = Offset(x, y);
        canvas.drawCircle(c.translate(1.5, 2.5), 8.5, Paint()..color = Colors.black.withValues(alpha: 0.35));
        canvas.drawCircle(
          c,
          8,
          Paint()
            ..shader = RadialGradient(center: const Alignment(-0.4, -0.5), colors: const [Color(0xFFFFE9A8), SancColors.gold, Color(0xFF8C6420)], stops: const [0, 0.45, 1])
                .createShader(Rect.fromCircle(center: c, radius: 8)),
        );
      }
    }
    // 铺首衔环：靠中缝，一块圆形铜底、一只圆环垂下来
    final cx = left ? size.width - 46.0 : 46.0;
    final cy = size.height * 0.5;
    final plate = Offset(cx, cy);
    canvas.drawCircle(plate.translate(2, 3), 23, Paint()..color = Colors.black.withValues(alpha: 0.35));
    canvas.drawCircle(
      plate,
      22,
      Paint()..shader = RadialGradient(center: const Alignment(-0.3, -0.4), colors: const [Color(0xFFF6D98A), SancColors.goldDeep, Color(0xFF6E4E1A)]).createShader(Rect.fromCircle(center: plate, radius: 22)),
    );
    // 兽面：两只眼、一道眉
    final ink = Paint()..color = const Color(0xFF5A3F14);
    canvas.drawCircle(plate.translate(-7, -5), 2.6, ink);
    canvas.drawCircle(plate.translate(7, -5), 2.6, ink);
    canvas.drawArc(Rect.fromCircle(center: plate.translate(0, -4), radius: 13), 3.6, 2.2, false, ink..style = PaintingStyle.stroke..strokeWidth = 2);
    // 环
    canvas.drawCircle(
      plate.translate(0, 20),
      15,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 4.5
        ..color = SancColors.gold,
    );
    canvas.drawArc(Rect.fromCircle(center: plate.translate(0, 20), radius: 15), 3.4, 1.4, false, Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.6
      ..color = const Color(0xFFFFF0C0));
    // 两扇门合缝处的一条深线
    final seamX = left ? size.width - 1 : 1.0;
    canvas.drawLine(Offset(seamX, 0), Offset(seamX, size.height), Paint()
      ..strokeWidth = 2
      ..color = Colors.black.withValues(alpha: 0.5));
  }

  @override
  bool shouldRepaint(_GateLeafPainter old) => old.left != left || old.shade != shade;
}

/// 门楣上那块竖匾：墨底、金边
class _PlaquePlatePainter extends CustomPainter {
  const _PlaquePlatePainter();

  @override
  void paint(Canvas canvas, Size size) {
    final r = RRect.fromRectAndRadius(Offset.zero & size, const Radius.circular(4));
    canvas.drawRRect(r.shift(const Offset(0, 4)), Paint()..color = Colors.black.withValues(alpha: 0.45));
    canvas.drawRRect(r, Paint()..color = SancColors.ink);
    canvas.drawRRect(
        r.deflate(3),
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2
          ..color = SancColors.goldDeep);
    canvas.drawRRect(
        r.deflate(6.5),
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 0.8
          ..color = SancColors.gold.withValues(alpha: 0.6));
  }

  @override
  bool shouldRepaint(_PlaquePlatePainter old) => false;
}
