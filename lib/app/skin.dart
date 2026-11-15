import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:yuanjing_engine/yuanjing_engine.dart';

import 'store.dart';

const displayFont = 'YuanjingSerif';

/// 一套皮肤：全应用的底色、文字色、强调色和背景里飘的东西都跟着它换。
///
/// 两套免费（金币许愿、梦幻渐变），三套会员（魔法巫女、天使祝福、美人鱼海洋）。
/// 许愿页和释放仪式的背景是原生渲染的场景，不受皮肤底色影响，但按钮和强调色跟皮肤走；
/// 卡点释放默认用这套皮肤对应的释放方式（[release]）。
class Skin {
  final String id;
  final String name;
  final String mood;
  final bool member;

  /// 对应的释放仪式场景
  final String release;

  /// 背景从上到下的三段颜色
  final List<Color> bg;
  final Color ink;
  final Color sub;
  final Color card;
  final Color line;
  final Color light;
  final Color deep;

  /// 强调色按钮上的字
  final Color onAccent;
  final bool dark;

  /// 背景里飘的东西：coins、clouds、stars、feathers、bubbles
  final String motif;

  const Skin({
    required this.id,
    required this.name,
    required this.mood,
    required this.member,
    required this.release,
    required this.bg,
    required this.ink,
    required this.sub,
    required this.card,
    required this.line,
    required this.light,
    required this.deep,
    required this.onAccent,
    required this.dark,
    required this.motif,
  });

  TextStyle title(double size) =>
      TextStyle(fontFamily: displayFont, fontSize: size, height: 1.35, fontWeight: FontWeight.w700, letterSpacing: 1, color: ink);
  TextStyle body([double size = 15]) => TextStyle(fontSize: size, height: 1.6, color: ink);
  TextStyle hint([double size = 13]) => TextStyle(fontSize: size, height: 1.5, color: sub);
  LinearGradient get accent => LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [light, deep]);
}

const skins = [
  Skin(
    id: 'gold',
    name: '金币许愿',
    mood: '明亮、招财、日常百搭',
    member: false,
    release: 'release_pool',
    bg: [Color(0xFFFFFDF8), Color(0xFFFFF5DF), Color(0xFFF8E2AE)],
    ink: Color(0xFF3A2A12),
    sub: Color(0xFF8C7654),
    card: Color(0xE6FFFFFF),
    line: Color(0x38B8892B),
    light: Color(0xFFFFE7A8),
    deep: Color(0xFFE2A93A),
    onAccent: Color(0xFF2A1708),
    dark: false,
    motif: 'coins',
  ),
  Skin(
    id: 'dream',
    name: '梦幻渐变',
    mood: '温柔、治愈、安抚情绪',
    member: false,
    release: 'release_balloon',
    bg: [Color(0xFFFFE4EE), Color(0xFFE8E5FF), Color(0xFFD6EEFF)],
    ink: Color(0xFF3B3558),
    sub: Color(0xFF7D789B),
    card: Color(0xD1FFFFFF),
    line: Color(0x38A08BE0),
    light: Color(0xFFFFD9E6),
    deep: Color(0xFFB8A2F2),
    onAccent: Color(0xFF2B2350),
    dark: false,
    motif: 'clouds',
  ),
  Skin(
    id: 'witch',
    name: '魔法巫女',
    mood: '神秘、沉静、深度清理',
    member: true,
    release: 'release_potion',
    bg: [Color(0xFF0B0A0D), Color(0xFF17130F), Color(0xFF2B2117)],
    ink: Color(0xFFF1E3C4),
    sub: Color(0xFFA9987B),
    card: Color(0xCC1D1813),
    line: Color(0x47C9A45A),
    light: Color(0xFFE9CF8F),
    deep: Color(0xFFA9812F),
    onAccent: Color(0xFF1B1408),
    dark: true,
    motif: 'stars',
  ),
  Skin(
    id: 'angel',
    name: '天使祝福',
    mood: '高贵、纯净、高频能量',
    member: true,
    release: 'release_arrow',
    bg: [Color(0xFFFFFFFF), Color(0xFFF2F3F8), Color(0xFFF7EACB)],
    ink: Color(0xFF3A3D4A),
    sub: Color(0xFF8B8F9D),
    card: Color(0xE6FFFFFF),
    line: Color(0x38B4B6C6),
    light: Color(0xFFFFF6DC),
    deep: Color(0xFFD9B45A),
    onAccent: Color(0xFF3A2E12),
    dark: false,
    motif: 'feathers',
  ),
  Skin(
    id: 'mermaid',
    name: '美人鱼海洋',
    mood: '空灵、松弛、许愿蓄能',
    member: true,
    release: 'release_deep',
    bg: [Color(0xFF071A3A), Color(0xFF0C2F5C), Color(0xFF1A5A88)],
    ink: Color(0xFFEAF6FF),
    sub: Color(0xFF9CC3DD),
    card: Color(0xCC0B2447),
    line: Color(0x4789C9F0),
    light: Color(0xFFCFF3FF),
    deep: Color(0xFF4FB4DA),
    onAccent: Color(0xFF062238),
    dark: true,
    motif: 'bubbles',
  ),
];

/// 皮肤背景：渐变底色上缓缓飘着这套皮肤的元素（金币光斑、云、星、羽毛、气泡）。
class SkinBackdrop extends StatefulWidget {
  final Skin skin;
  const SkinBackdrop({super.key, required this.skin});

  @override
  State<SkinBackdrop> createState() => _SkinBackdropState();
}

class _SkinBackdropState extends State<SkinBackdrop> with SingleTickerProviderStateMixin {
  late final Ticker _ticker = createTicker((d) => _time.value = d.inMicroseconds / 1e6)..start();
  final _time = ValueNotifier(0.0);

  @override
  void dispose() {
    _ticker.dispose();
    _time.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(child: CustomPaint(painter: _BackdropPainter(widget.skin, _time), size: Size.infinite));
  }
}

class _BackdropPainter extends CustomPainter {
  final Skin skin;
  final ValueNotifier<double> time;
  _BackdropPainter(this.skin, this.time) : super(repaint: time);

  static double _h(int i, int k) {
    final x = math.sin(i * 127.1 + k * 311.7) * 43758.5453;
    return x - x.floorToDouble();
  }

  @override
  void paint(Canvas canvas, Size size) {
    final t = time.value;
    final rect = Offset.zero & size;
    canvas.drawRect(rect, Paint()..shader = LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: skin.bg).createShader(rect));
    final w = size.width, h = size.height;
    switch (skin.motif) {
      case 'coins':
        // 暖金色的光斑缓缓上升，几枚带方孔的钱影
        for (var i = 0; i < 14; i++) {
          final r = 18 + 46 * _h(i, 1);
          final y = h - ((t * (6 + 10 * _h(i, 2)) + h * 1.3 * _h(i, 3)) % (h + 2 * r)) + r;
          final x = w * _h(i, 4) + 14 * math.sin(t * 0.3 + i);
          final c = Offset(x, y);
          canvas.drawCircle(
              c,
              r,
              Paint()
                ..shader = RadialGradient(colors: [const Color(0xFFFFD98A).withValues(alpha: 0.30), const Color(0xFFFFD98A).withValues(alpha: 0)])
                    .createShader(Rect.fromCircle(center: c, radius: r)));
          if (i % 4 == 0) {
            final ring = Paint()
              ..style = PaintingStyle.stroke
              ..strokeWidth = 1.2
              ..color = const Color(0xFFD9A441).withValues(alpha: 0.22);
            canvas.drawCircle(c, r * 0.42, ring);
            canvas.drawRect(Rect.fromCenter(center: c, width: r * 0.24, height: r * 0.24), ring);
          }
        }
      case 'clouds':
        // 大团的柔云横着漂，底下一道淡淡的彩虹
        final bow = Rect.fromCircle(center: Offset(w * 0.5, h * 1.02), radius: w * 0.95);
        for (var i = 0; i < 5; i++) {
          canvas.drawArc(
              bow.deflate(i * 7.0),
              math.pi,
              math.pi,
              false,
              Paint()
                ..style = PaintingStyle.stroke
                ..strokeWidth = 7
                ..color = [const Color(0xFFFF9EC0), const Color(0xFFFFD49E), const Color(0xFFFFF3A8), const Color(0xFFA8E6C8), const Color(0xFFA9C6FF)][i]
                    .withValues(alpha: 0.16));
        }
        final blur = Paint()..maskFilter = const MaskFilter.blur(BlurStyle.normal, 26);
        for (var i = 0; i < 9; i++) {
          final cw = 120 + 150 * _h(i, 1);
          final x = ((t * (4 + 7 * _h(i, 2)) + (w + 2 * cw) * _h(i, 3)) % (w + 2 * cw)) - cw;
          final y = h * (0.06 + 0.9 * _h(i, 4));
          blur.color = Colors.white.withValues(alpha: 0.30 + 0.25 * _h(i, 5));
          canvas.drawOval(Rect.fromCenter(center: Offset(x, y), width: cw, height: cw * 0.42), blur);
          canvas.drawOval(Rect.fromCenter(center: Offset(x + cw * 0.22, y - cw * 0.12), width: cw * 0.6, height: cw * 0.34), blur);
        }
      case 'stars':
        // 暗金色的星一明一灭，底下一圈星盘的细线
        final disc = Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 0.8
          ..color = const Color(0xFFC9A45A).withValues(alpha: 0.13);
        final c0 = Offset(w * 0.5, h * 0.36);
        for (final r in [w * 0.34, w * 0.50, w * 0.52]) {
          canvas.drawCircle(c0, r, disc);
        }
        for (var i = 0; i < 12; i++) {
          final a = i * math.pi / 6 + t * 0.02;
          canvas.drawLine(c0 + Offset(math.cos(a), math.sin(a)) * w * 0.50, c0 + Offset(math.cos(a), math.sin(a)) * w * 0.52, disc..strokeWidth = 1.4);
        }
        final star = Paint();
        for (var i = 0; i < 46; i++) {
          final p = Offset(w * _h(i, 1), h * _h(i, 2));
          final tw = 0.5 + 0.5 * math.sin(t * (0.6 + 1.6 * _h(i, 3)) + i);
          final r = 0.8 + 2.2 * _h(i, 4) * _h(i, 4);
          star.color = const Color(0xFFE9CF8F).withValues(alpha: 0.15 + 0.55 * tw * _h(i, 5));
          canvas.drawCircle(p, r, star);
          if (i % 7 == 0) {
            final len = 7 + 9 * tw;
            star.strokeWidth = 0.9;
            canvas.drawLine(p - Offset(len, 0), p + Offset(len, 0), star);
            canvas.drawLine(p - Offset(0, len), p + Offset(0, len), star);
          }
        }
      case 'feathers':
        // 从上方斜下来的几道柔光，羽毛缓缓落下
        final ray = Paint()..maskFilter = const MaskFilter.blur(BlurStyle.normal, 30);
        for (var i = 0; i < 4; i++) {
          final x = w * (0.1 + 0.27 * i) + 20 * math.sin(t * 0.1 + i);
          ray.color = const Color(0xFFFFE9B0).withValues(alpha: 0.16 + 0.05 * math.sin(t * 0.3 + i * 2));
          canvas.drawPath(
              Path()
                ..moveTo(x, -40)
                ..lineTo(x + 70, -40)
                ..lineTo(x + 70 - w * 0.25, h * 0.9)
                ..lineTo(x - 60 - w * 0.25, h * 0.9)
                ..close(),
              ray);
        }
        final quill = Paint()..color = Colors.white.withValues(alpha: 0.9);
        final shade = Paint()
          ..color = const Color(0xFFB9BCCB).withValues(alpha: 0.45)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 0.8;
        for (var i = 0; i < 9; i++) {
          final len = 22 + 20 * _h(i, 1);
          final y = ((t * (9 + 9 * _h(i, 2)) + (h + 80) * _h(i, 3)) % (h + 80)) - 40;
          final x = w * _h(i, 4) + 24 * math.sin(t * 0.5 + i * 1.7);
          canvas.save();
          canvas.translate(x, y);
          canvas.rotate(0.6 * math.sin(t * 0.6 + i) + i.toDouble());
          final r = Rect.fromCenter(center: Offset.zero, width: len * 0.3, height: len);
          canvas.drawOval(r, quill);
          canvas.drawOval(r, shade);
          canvas.drawLine(Offset(0, -len * 0.5), Offset(0, len * 0.62), shade);
          canvas.restore();
        }
      case 'bubbles':
        // 海面透下来的光，气泡往上升
        final ray = Paint()..maskFilter = const MaskFilter.blur(BlurStyle.normal, 34);
        for (var i = 0; i < 4; i++) {
          final x = w * (0.05 + 0.3 * i) + 26 * math.sin(t * 0.12 + i);
          ray.color = const Color(0xFF7FD4F5).withValues(alpha: 0.10 + 0.04 * math.sin(t * 0.25 + i * 2));
          canvas.drawPath(
              Path()
                ..moveTo(x, -40)
                ..lineTo(x + 60, -40)
                ..lineTo(x + 190, h * 0.85)
                ..lineTo(x + 20, h * 0.85)
                ..close(),
              ray);
        }
        final rim = Paint()..style = PaintingStyle.stroke;
        final spot = Paint();
        for (var i = 0; i < 20; i++) {
          final r = 3 + 12 * _h(i, 1) * _h(i, 1);
          final y = h - ((t * (14 + 22 * _h(i, 2)) + (h + 60) * _h(i, 3)) % (h + 60)) + 30;
          final x = w * _h(i, 4) + 8 * math.sin(t * 1.4 + i);
          rim
            ..strokeWidth = 1
            ..color = const Color(0xFFCFF3FF).withValues(alpha: 0.42);
          canvas.drawCircle(Offset(x, y), r, rim);
          spot.color = Colors.white.withValues(alpha: 0.55);
          canvas.drawCircle(Offset(x - r * 0.35, y - r * 0.35), r * 0.16, spot);
        }
    }
  }

  @override
  bool shouldRepaint(_BackdropPainter old) => old.skin != skin;
}

/// 一个普通页面的骨架：皮肤背景、标题、内容。跟着数据变化自动刷新。
class SkinPage extends StatelessWidget {
  final String? title;
  final String? subtitle;

  /// 标题右边的东西
  final Widget? trailing;

  /// 是不是从别的页面点进来的（带返回）
  final bool pushed;

  /// 底部给底栏留的空
  final double bottom;
  final Widget Function(BuildContext context, Skin skin) builder;

  const SkinPage({super.key, this.title, this.subtitle, this.trailing, this.pushed = false, this.bottom = 0, required this.builder});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: store,
      builder: (context, _) {
        final s = store.skin;
        return Scaffold(
          backgroundColor: s.bg.first,
          resizeToAvoidBottomInset: true,
          body: Stack(fit: StackFit.expand, children: [
            SkinBackdrop(skin: s),
            SafeArea(
              bottom: false,
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                if (pushed)
                  GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTap: () => Navigator.of(context).maybePop(),
                    child: Padding(padding: const EdgeInsets.fromLTRB(22, 8, 22, 4), child: Text('‹ 返回', style: s.hint(14))),
                  ),
                if (title != null)
                  Padding(
                    padding: EdgeInsets.fromLTRB(22, pushed ? 4 : 12, 22, 6),
                    child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(title!, style: s.title(29)),
                          if (subtitle != null) Padding(padding: const EdgeInsets.only(top: 4), child: Text(subtitle!, style: s.hint(13.5))),
                        ]),
                      ),
                      ?trailing,
                    ]),
                  ),
                Expanded(child: Padding(padding: EdgeInsets.only(bottom: bottom), child: builder(context, s))),
              ]),
            ),
          ]),
        );
      },
    );
  }
}

/// 卡片
class SCard extends StatelessWidget {
  final Widget child;
  final EdgeInsets padding;
  final VoidCallback? onTap;
  const SCard({super.key, required this.child, this.padding = const EdgeInsets.all(16), this.onTap});

  @override
  Widget build(BuildContext context) {
    final s = store.skin;
    final card = Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: s.card,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: s.line),
        boxShadow: [BoxShadow(color: (s.dark ? Colors.black : s.deep).withValues(alpha: s.dark ? 0.35 : 0.12), blurRadius: 22, offset: const Offset(0, 9))],
      ),
      child: child,
    );
    if (onTap == null) return card;
    return GestureDetector(behavior: HitTestBehavior.opaque, onTap: onTap, child: card);
  }
}

/// 按钮。[ghost] 是只有描边的次要按钮。
class SButton extends StatelessWidget {
  final String label;
  final VoidCallback? onTap;
  final bool ghost;
  final bool small;
  final bool expand;
  const SButton(this.label, {super.key, this.onTap, this.ghost = false, this.small = false, this.expand = false});

  @override
  Widget build(BuildContext context) {
    final s = store.skin;
    final off = onTap == null;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: off
          ? null
          : () {
              YuanjingHaptics.play('tick');
              YuanjingAudio.sfx('tap');
              onTap!();
            },
      child: Opacity(
        opacity: off ? 0.45 : 1,
        child: Container(
          height: small ? 34 : 46,
          width: expand ? double.infinity : null,
          padding: EdgeInsets.symmetric(horizontal: small ? 14 : 22),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(99),
            gradient: ghost ? null : s.accent,
            border: Border.all(color: ghost ? s.line.withValues(alpha: 0.9) : Colors.white.withValues(alpha: 0.6), width: 0.8),
            boxShadow: ghost ? null : [BoxShadow(color: s.deep.withValues(alpha: 0.38), blurRadius: small ? 10 : 16, offset: Offset(0, small ? 4 : 7))],
          ),
          child: Center(
            widthFactor: expand ? null : 1,
            child: Text(label,
                style: TextStyle(
                    fontSize: small ? 13 : 15, fontWeight: FontWeight.w700, letterSpacing: 0.6, color: ghost ? s.ink : s.onAccent)),
          ),
        ),
      ),
    );
  }
}

/// 可选中的小标签
class SChip extends StatelessWidget {
  final String label;
  final bool on;
  final VoidCallback? onTap;
  const SChip(this.label, {super.key, this.on = false, this.onTap});

  @override
  Widget build(BuildContext context) {
    final s = store.skin;
    return GestureDetector(
      onTap: onTap == null
          ? null
          : () {
              YuanjingHaptics.play('tick');
              onTap!();
            },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        height: 32,
        padding: const EdgeInsets.symmetric(horizontal: 13),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(99),
          gradient: on ? s.accent : null,
          color: on ? null : s.card.withValues(alpha: 0.5),
          border: Border.all(color: on ? Colors.white.withValues(alpha: 0.6) : s.line),
        ),
        child: Center(
          widthFactor: 1,
          child: Text(label, style: TextStyle(fontSize: 13.5, fontWeight: on ? FontWeight.w700 : FontWeight.w400, color: on ? s.onAccent : s.ink)),
        ),
      ),
    );
  }
}

/// 「会员」小标。
///
/// 这个和 [CoinBadge] 都是不带参数的小组件，到处以 const 的形式出现；const 组件在父级刷新时不会重建，
/// 所以它们自己监听数据变化，换皮肤、金币变了才跟得上。
class MemberTag extends StatelessWidget {
  const MemberTag({super.key});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: store,
      builder: (context, _) {
        final s = store.skin;
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(6), gradient: s.accent),
          child: Text('会员', style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, color: s.onAccent)),
        );
      },
    );
  }
}

/// 金币数
class CoinBadge extends StatelessWidget {
  const CoinBadge({super.key});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: store,
      builder: (context, _) {
        final s = store.skin;
        return Container(
          height: 34,
          padding: const EdgeInsets.only(left: 8, right: 13),
          decoration: BoxDecoration(color: s.card, borderRadius: BorderRadius.circular(99), border: Border.all(color: s.line)),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            const CoinIcon(size: 19),
            const SizedBox(width: 7),
            Text('${store.coins}', style: TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700, color: s.ink)),
          ]),
        );
      },
    );
  }
}

/// 一枚方孔钱
class CoinIcon extends StatelessWidget {
  final double size;
  const CoinIcon({super.key, this.size = 16});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: const BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(center: Alignment(-0.4, -0.5), colors: [Color(0xFFFFF4C8), Color(0xFFF0C356), Color(0xFFB07A18)], stops: [0, 0.45, 1]),
      ),
      child: Container(width: size * 0.3, height: size * 0.3, color: const Color(0xFF6B4708)),
    );
  }
}

/// 底部弹出的面板
Future<T?> showSkinSheet<T>(BuildContext context, Widget Function(BuildContext context, Skin skin) builder, {bool tall = false}) {
  return showModalBottomSheet<T>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    barrierColor: Colors.black54,
    builder: (context) => ListenableBuilder(
      listenable: store,
      builder: (context, _) {
        final s = store.skin;
        return Padding(
          padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
          child: Container(
            constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * (tall ? 0.88 : 0.74)),
            decoration: BoxDecoration(
              gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [s.bg[0], s.bg[1]]),
              borderRadius: const BorderRadius.vertical(top: Radius.circular(26)),
              border: Border(top: BorderSide(color: s.line)),
            ),
            child: SafeArea(
              top: false,
              child: Padding(padding: const EdgeInsets.fromLTRB(22, 18, 22, 14), child: builder(context, s)),
            ),
          ),
        );
      },
    ),
  );
}

/// 屏幕上方的一句话提示
void toast(BuildContext context, String text) {
  final overlay = Overlay.of(context, rootOverlay: true);
  late OverlayEntry entry;
  entry = OverlayEntry(
    builder: (context) => Positioned(
      left: 0,
      right: 0,
      top: MediaQuery.paddingOf(context).top + 10,
      child: IgnorePointer(
        child: Center(
          child: TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: 1),
            duration: const Duration(milliseconds: 260),
            builder: (_, v, child) => Opacity(opacity: v, child: Transform.translate(offset: Offset(0, -10 * (1 - v)), child: child)),
            child: Material(
              color: Colors.transparent,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
                decoration: BoxDecoration(color: const Color(0xE6141210), borderRadius: BorderRadius.circular(99), border: Border.all(color: Colors.white24)),
                child: Text(text, style: const TextStyle(fontSize: 13.5, color: Colors.white)),
              ),
            ),
          ),
        ),
      ),
    ),
  );
  overlay.insert(entry);
  Future.delayed(const Duration(milliseconds: 2200), entry.remove);
}

/// 发了金币时的提示
void coinToast(BuildContext context, int amount, String what) {
  if (amount > 0) {
    YuanjingAudio.sfx('coin_1', volume: 0.6);
    toast(context, '$what，金币 +$amount');
  }
}

/// 输入框旁边的话筒：按一下开始说，再按一下停。识别出来的字接在输入框原有内容后面。
class MicButton extends StatefulWidget {
  final TextEditingController controller;
  final Color? color;
  const MicButton({super.key, required this.controller, this.color});

  @override
  State<MicButton> createState() => _MicButtonState();
}

class _MicButtonState extends State<MicButton> {
  bool _on = false;
  String _base = '';
  dynamic _sub;

  Future<void> _toggle() async {
    if (_on) {
      YuanjingSpeech.stop();
      return;
    }
    _base = widget.controller.text;
    _sub ??= YuanjingSpeech.results.listen((r) {
      if (!mounted) return;
      if (r.text.isNotEmpty) {
        final text = _base + r.text;
        widget.controller.value = TextEditingValue(text: text, selection: TextSelection.collapsed(offset: text.length));
      }
      if (r.ended) setState(() => _on = false);
    });
    final problem = await YuanjingSpeech.start();
    if (!mounted) return;
    if (problem != null) {
      toast(context, problem);
      return;
    }
    YuanjingHaptics.play('tick');
    setState(() => _on = true);
  }

  @override
  void dispose() {
    if (_on) YuanjingSpeech.stop();
    _sub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.color ?? store.skin.ink;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: _toggle,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        width: 36,
        height: 36,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: _on ? const Color(0xFFE5484D) : c.withValues(alpha: 0.10),
          border: Border.all(color: _on ? Colors.white70 : c.withValues(alpha: 0.25)),
        ),
        child: Icon(_on ? Icons.stop_rounded : Icons.mic_none_rounded, size: 19, color: _on ? Colors.white : c),
      ),
    );
  }
}
