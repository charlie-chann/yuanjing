import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'sanctuary_ui.dart';

/// 湖心小寺的操作界面（开放世界游戏那一套）：
/// 左下摇杆走路，拖动画面转视角、捏合拉远拉近；
/// 走到能做事的东西跟前，画面右边冒出一列「可以做的事」（[PromptList]），点一下就做；
/// 右下角是随时能做的动作（合掌、鞠躬）；钓鱼时右下角换成「提竿」（[ReelButton]）。

/// 靠近才出现的一件事
class HudPrompt {
  final String label;

  /// 前面那枚小圆牌上画什么：paw 爪印、food 食盆、bird 小鸟、bell 钟、fish 鱼、sit 蒲团、kneel 跪拜、
  /// incense 香、ribbon 布条、plaque 木牌、wish 许愿、stand 起身、calm 静坐、bag 背包
  final String glyph;
  final VoidCallback onTap;
  const HudPrompt(this.label, this.glyph, this.onTap);
}

/// 画面右边的一列：此刻身边能做的事。第一条是金边的（最想让你做的那件），其余是素的。
class PromptList extends StatelessWidget {
  final List<HudPrompt> prompts;
  const PromptList({super.key, required this.prompts});

  static const double rowHeight = 46;

  @override
  Widget build(BuildContext context) {
    final still = MediaQuery.disableAnimationsOf(context);
    return AnimatedSwitcher(
      duration: still ? Duration.zero : const Duration(milliseconds: 220),
      switchInCurve: Curves.easeOutCubic,
      transitionBuilder: (child, a) => FadeTransition(
        opacity: a,
        child: SlideTransition(position: Tween(begin: const Offset(0.12, 0), end: Offset.zero).animate(a), child: child),
      ),
      layoutBuilder: (current, previous) => Stack(alignment: Alignment.centerRight, children: [...previous, ?current]),
      child: prompts.isEmpty
          ? const SizedBox(key: ValueKey('none'))
          : Column(
              key: ValueKey(prompts.map((p) => p.label).join('|')),
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                for (var i = 0; i < prompts.length; i++)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: _PromptRow(prompt: prompts[i], lead: i == 0),
                  ),
              ],
            ),
    );
  }
}

class _PromptRow extends StatefulWidget {
  final HudPrompt prompt;
  final bool lead;
  const _PromptRow({required this.prompt, required this.lead});

  @override
  State<_PromptRow> createState() => _PromptRowState();
}

class _PromptRowState extends State<_PromptRow> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    final lead = widget.lead;
    return Semantics(
      button: true,
      label: widget.prompt.label,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: widget.prompt.onTap,
        onTapDown: (_) => setState(() => _down = true),
        onTapUp: (_) => setState(() => _down = false),
        onTapCancel: () => setState(() => _down = false),
        child: AnimatedScale(
          scale: _down ? 0.95 : 1,
          duration: const Duration(milliseconds: 110),
          child: Container(
            height: PromptList.rowHeight,
            padding: const EdgeInsets.fromLTRB(5, 0, 16, 0),
            decoration: BoxDecoration(
              // 墨色的底，右边淡出去一点，像一条压在画面上的墨痕
              gradient: LinearGradient(colors: [const Color(0xE61E1814), Color(lead ? 0xD91E1814 : 0xB81E1814)]),
              borderRadius: BorderRadius.circular(PromptList.rowHeight / 2),
              border: Border.all(color: lead ? const Color(0xE6E8BB4D) : const Color(0x59F3E8CF), width: lead ? 1.3 : 1),
              boxShadow: const [BoxShadow(color: Color(0x59000000), blurRadius: 10, offset: Offset(0, 3))],
            ),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              // 小圆牌：朱漆底（第一条）或墨底，上面一个金色的小图
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: lead ? SancColors.vermilion : const Color(0xFF3A302A),
                  border: Border.all(color: lead ? const Color(0xFFF0C95F) : const Color(0x80E8BB4D), width: 1),
                ),
                child: CustomPaint(painter: HudGlyphPainter(widget.prompt.glyph, lead ? SancColors.goldLit : SancColors.gold)),
              ),
              const SizedBox(width: 10),
              Text(widget.prompt.label, maxLines: 1, style: sancLabel(15.5, lead ? SancColors.goldLit : SancColors.paper, spacing: 1.5)),
            ]),
          ),
        ),
      ),
    );
  }
}

/// 小圆牌上的图：几笔画成的，不用图片
class HudGlyphPainter extends CustomPainter {
  final String glyph;
  final Color color;
  const HudGlyphPainter(this.glyph, this.color);

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    final u = size.shortestSide / 36; // 按 36 的圆牌画，别的大小跟着缩放
    canvas.save();
    canvas.translate(c.dx, c.dy);
    canvas.scale(u);
    final fill = Paint()..color = color;
    final line = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.8
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    switch (glyph) {
      case 'paw':
        // 掌垫加四个脚趾
        canvas.drawOval(Rect.fromCenter(center: const Offset(0, 4), width: 12, height: 9.5), fill);
        for (final (dx, dy, r) in [(-7.5, -1.5, 2.6), (-2.8, -6.5, 2.9), (2.8, -6.5, 2.9), (7.5, -1.5, 2.6)]) {
          canvas.drawOval(Rect.fromCenter(center: Offset(dx, dy), width: r * 2, height: r * 2.4), fill);
        }
      case 'food':
        // 一只食盆，上面冒着一小堆
        final bowl = Path()
          ..moveTo(-10, 0)
          ..lineTo(10, 0)
          ..lineTo(7, 8)
          ..lineTo(-7, 8)
          ..close();
        canvas.drawPath(bowl, fill);
        canvas.drawArc(Rect.fromCenter(center: const Offset(0, 0), width: 14, height: 12), math.pi, math.pi, false, line);
        canvas.drawCircle(const Offset(-2, -7), 1.3, fill);
        canvas.drawCircle(const Offset(3, -8.5), 1.3, fill);
      case 'bird':
        // 圆身子、尖嘴、翘尾巴
        canvas.drawOval(Rect.fromCenter(center: const Offset(-1, 2), width: 15, height: 11), fill);
        canvas.drawCircle(const Offset(6, -4), 4.6, fill);
        canvas.drawPath(
            Path()
              ..moveTo(10, -5)
              ..lineTo(14.5, -3.5)
              ..lineTo(10, -2)
              ..close(),
            fill);
        canvas.drawPath(
            Path()
              ..moveTo(-7, 0)
              ..lineTo(-14, -5)
              ..lineTo(-9, 4)
              ..close(),
            fill);
        canvas.drawLine(const Offset(-1, 7), const Offset(-1, 11), line);
        canvas.drawLine(const Offset(3, 7), const Offset(3, 11), line);
      case 'bell':
        // 一口钟：钮、钟身、钟口的波形
        canvas.drawArc(Rect.fromCenter(center: const Offset(0, -9.5), width: 6, height: 6), math.pi, math.pi, false, line);
        final body = Path()
          ..moveTo(-6, -8)
          ..quadraticBezierTo(-8.5, 2, -10, 8)
          ..quadraticBezierTo(-5, 10.5, 0, 8.5)
          ..quadraticBezierTo(5, 10.5, 10, 8)
          ..quadraticBezierTo(8.5, 2, 6, -8)
          ..close();
        canvas.drawPath(body, fill);
      case 'fish':
        // 鱼身、尾巴、一只眼
        canvas.drawOval(Rect.fromCenter(center: const Offset(2, 0), width: 17, height: 10), fill);
        canvas.drawPath(
            Path()
              ..moveTo(-5, 0)
              ..lineTo(-12.5, -6)
              ..lineTo(-10.5, 0)
              ..lineTo(-12.5, 6)
              ..close(),
            fill);
        canvas.drawCircle(const Offset(6.5, -1.5), 1.3, Paint()..color = const Color(0xFF2B2420));
      case 'sit':
        // 一只圆蒲团（两层编的草圈）
        canvas.drawOval(Rect.fromCenter(center: const Offset(0, 2), width: 22, height: 11), fill);
        canvas.drawOval(
            Rect.fromCenter(center: const Offset(0, 0.5), width: 14, height: 6),
            Paint()
              ..color = const Color(0x8C2B2420)
              ..style = PaintingStyle.stroke
              ..strokeWidth = 1.2);
        canvas.drawArc(Rect.fromCenter(center: const Offset(0, -1), width: 22, height: 11), math.pi * 1.05, math.pi * 0.9, false, line);
      case 'kneel':
        // 跪着叩首的小人：头、弓着的背、小腿
        canvas.drawCircle(const Offset(-8, 4), 3.2, fill);
        canvas.drawPath(
            Path()
              ..moveTo(-5.5, 5)
              ..quadraticBezierTo(1, -9, 8, 2)
              ..lineTo(8, 8)
              ..lineTo(-4, 8),
            line..strokeWidth = 2.6);
      case 'incense':
        // 三支香，香头有烟
        for (final dx in [-5.0, 0.0, 5.0]) {
          canvas.drawLine(Offset(dx, 10), Offset(dx * 1.25, -3), line);
          canvas.drawCircle(Offset(dx * 1.25, -4.5), 1.5, fill);
        }
        canvas.drawPath(
            Path()
              ..moveTo(0, -7)
              ..quadraticBezierTo(4, -9.5, 1, -12.5),
            line..strokeWidth = 1.2);
      case 'ribbon':
        // 一条垂着的布条，上头一个结
        canvas.drawPath(
            Path()
              ..moveTo(-3.5, -9)
              ..lineTo(3.5, -9)
              ..lineTo(4.5, 9)
              ..lineTo(0, 5.5)
              ..lineTo(-4.5, 9)
              ..close(),
            fill);
        canvas.drawLine(const Offset(-8, -10.5), const Offset(8, -10.5), line);
      case 'plaque':
        // 五角的小木牌（绘马），上面穿着绳
        canvas.drawPath(
            Path()
              ..moveTo(0, -8)
              ..lineTo(9, -3)
              ..lineTo(9, 9)
              ..lineTo(-9, 9)
              ..lineTo(-9, -3)
              ..close(),
            fill);
        canvas.drawLine(const Offset(0, -8), const Offset(0, -12.5), line);
      case 'wish':
        // 合着的两只手
        canvas.drawPath(
            Path()
              ..moveTo(0, -11)
              ..quadraticBezierTo(-5.5, -3, -6, 9)
              ..lineTo(0, 9)
              ..close(),
            fill);
        canvas.drawPath(
            Path()
              ..moveTo(0, -11)
              ..quadraticBezierTo(5.5, -3, 6, 9)
              ..lineTo(0, 9)
              ..close(),
            fill);
        canvas.drawLine(const Offset(0, -9), const Offset(0, 9), Paint()..color = const Color(0x8C2B2420)..strokeWidth = 1.1);
      case 'stand':
        // 往上的箭头
        canvas.drawLine(const Offset(0, 9), const Offset(0, -8), line..strokeWidth = 2.4);
        canvas.drawPath(
            Path()
              ..moveTo(-6.5, -2)
              ..lineTo(0, -9)
              ..lineTo(6.5, -2),
            line);
      case 'calm':
        // 一圈圈荡开的水纹
        for (final r in [3.0, 7.0, 11.0]) {
          canvas.drawCircle(Offset.zero, r, line..strokeWidth = r < 4 ? 2.2 : 1.4);
        }
      case 'bag':
        // 束口的布囊
        canvas.drawPath(
            Path()
              ..moveTo(-5, -5)
              ..quadraticBezierTo(-12, 3, -8, 9)
              ..lineTo(8, 9)
              ..quadraticBezierTo(12, 3, 5, -5)
              ..close(),
            fill);
        canvas.drawPath(
            Path()
              ..moveTo(-6, -10)
              ..lineTo(-4, -5.5)
              ..lineTo(4, -5.5)
              ..lineTo(6, -10),
            line);
      default:
        canvas.drawCircle(Offset.zero, 4, fill);
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(HudGlyphPainter old) => old.glyph != glyph || old.color != color;
}

/// 右下角的圆键：朱漆的大键（主动作）或墨底的小键
class RoundAction extends StatefulWidget {
  final String label;
  final double size;
  final bool primary;
  final VoidCallback? onTap;
  const RoundAction(this.label, {super.key, this.size = 56, this.primary = false, this.onTap});

  @override
  State<RoundAction> createState() => _RoundActionState();
}

class _RoundActionState extends State<RoundAction> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    final p = widget.primary;
    return Semantics(
      button: true,
      label: widget.label,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: widget.onTap,
        onTapDown: (_) => setState(() => _down = true),
        onTapUp: (_) => setState(() => _down = false),
        onTapCancel: () => setState(() => _down = false),
        child: AnimatedScale(
          scale: _down ? 0.92 : 1,
          duration: const Duration(milliseconds: 110),
          child: Container(
            width: widget.size,
            height: widget.size,
            padding: const EdgeInsets.all(3.5),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: p ? SancColors.vermilion : const Color(0xD91E1814),
              border: Border.all(color: p ? SancColors.vermilionDeep : const Color(0x73F3E8CF), width: 1),
              boxShadow: const [BoxShadow(color: Color(0x66000000), blurRadius: 12, offset: Offset(0, 4))],
            ),
            child: DecoratedBox(
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(color: p ? const Color(0xD9E8BB4D) : const Color(0x40E8BB4D), width: 0.9),
              ),
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.only(left: 1.5),
                  child: Text(widget.label,
                      maxLines: 1, style: sancLabel(widget.size > 60 ? 17 : 14, p ? SancColors.goldLit : SancColors.paper, spacing: 1.5)),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// 右上角的小圆键，里面是一个小图（背包）
class GlyphButton extends StatelessWidget {
  final String glyph;
  final String label;
  final VoidCallback? onTap;
  const GlyphButton(this.glyph, {super.key, required this.label, this.onTap});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: label,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onTap,
        child: Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: const Color(0xD91E1814),
            border: Border.all(color: const Color(0x80E8BB4D), width: 1),
            boxShadow: const [BoxShadow(color: Color(0x59000000), blurRadius: 8, offset: Offset(0, 3))],
          ),
          child: CustomPaint(painter: HudGlyphPainter(glyph, SancColors.gold)),
        ),
      ),
    );
  }
}

/// 钓鱼时的大键：等的时候是素的「提竿」；咬钩的那一两秒变成朱漆的、外面一圈金线从满慢慢烧完，烧完鱼就跑了
class ReelButton extends StatefulWidget {
  /// 是不是正咬着钩
  final bool biting;

  /// 咬钩后多久内提竿算数
  final Duration window;
  final VoidCallback onTap;
  const ReelButton({super.key, required this.biting, required this.window, required this.onTap});

  @override
  State<ReelButton> createState() => _ReelButtonState();
}

class _ReelButtonState extends State<ReelButton> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: widget.window);

  @override
  void didUpdateWidget(ReelButton old) {
    super.didUpdateWidget(old);
    if (widget.biting && !old.biting) {
      _c.duration = widget.window;
      _c.forward(from: 0);
    } else if (!widget.biting && old.biting) {
      _c.stop();
    }
  }

  @override
  void initState() {
    super.initState();
    if (widget.biting) _c.forward();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final b = widget.biting;
    return Semantics(
      button: true,
      label: '提竿',
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTapDown: (_) => widget.onTap(),
        child: AnimatedBuilder(
          animation: _c,
          builder: (context, _) {
            // 咬钩时一下一下地鼓起来，催你提竿
            final pulse = b ? 1 + 0.06 * math.sin(_c.value * math.pi * 10) : 1.0;
            return Transform.scale(
              scale: pulse,
              child: SizedBox(
                width: 96,
                height: 96,
                child: CustomPaint(
                  painter: _ReelRingPainter(b ? 1 - _c.value : 0),
                  child: Center(
                    child: Container(
                      width: 78,
                      height: 78,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: b ? SancColors.vermilion : const Color(0xD91E1814),
                        border: Border.all(color: b ? const Color(0xFFF0C95F) : const Color(0x73F3E8CF), width: b ? 1.6 : 1),
                        boxShadow: [BoxShadow(color: b ? const Color(0x99C8452F) : const Color(0x66000000), blurRadius: b ? 22 : 12, offset: const Offset(0, 4))],
                      ),
                      child: Center(
                        child: Padding(
                          padding: const EdgeInsets.only(left: 3),
                          child: Text('提竿', style: sancLabel(20, b ? SancColors.goldLit : SancColors.paper, spacing: 3)),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

class _ReelRingPainter extends CustomPainter {
  /// 还剩多少（1 满，0 没有）
  final double left;
  const _ReelRingPainter(this.left);

  @override
  void paint(Canvas canvas, Size size) {
    if (left <= 0) return;
    final r = Rect.fromCircle(center: size.center(Offset.zero), radius: size.shortestSide / 2 - 3);
    canvas.drawArc(
        r,
        -math.pi / 2,
        math.pi * 2 * left,
        false,
        Paint()
          ..color = SancColors.goldLit
          ..style = PaintingStyle.stroke
          ..strokeWidth = 4
          ..strokeCap = StrokeCap.round);
  }

  @override
  bool shouldRepaint(_ReelRingPainter old) => old.left != left;
}
