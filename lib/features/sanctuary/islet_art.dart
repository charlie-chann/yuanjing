import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'sanctuary_ui.dart';

/// 湖心小寺里能拿在手上的东西的小画：每种鱼、每样口粮、每件收藏品各一张，全部用代码画，没有图片素材。
/// 编号和服务器 server/app/islet.py 里的一致。头像框上的小装饰（爪印、贝壳、枫叶……）也用这里的画法。

/// 稀有度的颜色和叫法
abstract final class Rarity {
  static const colors = <String, Color>{
    'junk': Color(0xFF8A7F72),
    'common': Color(0xFFCFC3A8),
    'uncommon': Color(0xFF86C08F),
    'rare': Color(0xFF79B4DA),
    'legend': SancColors.gold,
  };
  static const names = <String, String>{'junk': '杂物', 'common': '常见', 'uncommon': '少见', 'rare': '稀有', 'legend': '传说'};

  static Color color(String? r) => colors[r] ?? colors['common']!;
  static String name(String? r) => names[r] ?? '常见';
}

/// 一样东西的小画。[shadow] 为 true 时只画一个剪影（图鉴里还没钓到的鱼）。
class ItemArt extends StatelessWidget {
  final String id;
  final double size;
  final bool shadow;
  const ItemArt(this.id, {super.key, this.size = 48, this.shadow = false});

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(child: CustomPaint(size: Size.square(size), painter: _ItemPainter(id, shadow)));
  }
}

class _ItemPainter extends CustomPainter {
  final String id;
  final bool shadow;
  const _ItemPainter(this.id, this.shadow);

  @override
  void paint(Canvas canvas, Size size) {
    final m = math.min(size.width, size.height);
    if (shadow) {
      canvas.saveLayer(Offset.zero & size, Paint()..colorFilter = const ColorFilter.mode(Color(0xFF4A4038), BlendMode.srcIn));
    }
    canvas.save();
    canvas.translate(size.width / 2, size.height / 2);
    canvas.scale(m / 100);
    paintItem(canvas, id);
    canvas.restore();
    if (shadow) canvas.restore();
  }

  @override
  bool shouldRepaint(_ItemPainter old) => old.id != id || old.shadow != shadow;
}

/// 在以原点为中心的 100×100 格子里画一样东西
void paintItem(Canvas canvas, String id) {
  switch (id) {
    // 鱼
    case 'crucian':
      _crucian(canvas);
    case 'loach':
      _loach(canvas);
    case 'goldfish':
      _goldfish(canvas);
    case 'shrimp':
      _shrimp(canvas);
    case 'whitebait':
      _whitebait(canvas);
    case 'silver':
      _silver(canvas);
    case 'bass':
      _bass(canvas);
    case 'mandarin':
      _mandarin(canvas);
    case 'crab':
      _crab(canvas);
    case 'carp_gold':
      _carpGold(canvas);
    case 'moon':
      _moonFish(canvas);
    case 'weed':
      _weed(canvas);
    // 口粮
    case 'food_kibble':
      _kibble(canvas);
    case 'food_dried_fish':
      _driedFishPair(canvas);
    case 'food_bone':
      _meatBone(canvas);
    case 'food_cream':
      _cream(canvas);
    // 收藏品
    case 'shell':
      Shapes.shell(canvas, const Offset(0, 2), 38);
    case 'shell_conch':
      Shapes.conch(canvas, Offset.zero, 40);
    case 'pebble':
      Shapes.pebble(canvas, const Offset(0, 4), 38);
    case 'clover':
      Shapes.clover(canvas, const Offset(0, -4), 36);
    case 'pinecone':
      Shapes.pinecone(canvas, Offset.zero, 40);
    case 'ginkgo':
      Shapes.ginkgo(canvas, const Offset(0, 2), 40, rot: 0.2);
    case 'maple':
      Shapes.maple(canvas, const Offset(0, -2), 40, rot: -0.15);
    case 'flower':
      _wildFlower(canvas);
    case 'feather':
      Shapes.feather(canvas, Offset.zero, 42, rot: 0.25);
    case 'bell':
      Shapes.bell(canvas, const Offset(0, 2), 38);
    case 'yarn':
      Shapes.yarn(canvas, const Offset(-3, -2), 36, const Color(0xFFE58FA6));
    case 'bone':
      Shapes.bone(canvas, Offset.zero, 40, rot: -0.5);
    case 'stick':
      Shapes.stick(canvas, Offset.zero, 42, rot: -0.35);
    case 'dried_fish':
      Shapes.driedFish(canvas, Offset.zero, 40, rot: -0.3);
    case 'pearl':
      _pearlInShell(canvas);
    case 'knot':
      Shapes.knot(canvas, const Offset(0, -4), 40);
    default:
      // 不认识的编号：一个问号牌，免得空着
      canvas.drawCircle(Offset.zero, 30, _line(const Color(0x73F3E8CF), 2));
      _text(canvas, '？', 30, const Color(0xB3F3E8CF));
  }
}

Paint _fill(Color c) => Paint()..color = c;

Paint _line(Color c, double w) => Paint()
  ..color = c
  ..style = PaintingStyle.stroke
  ..strokeWidth = w
  ..strokeCap = StrokeCap.round
  ..strokeJoin = StrokeJoin.round;

Paint _grad(Rect r, List<Color> colors, {Alignment begin = Alignment.topCenter, Alignment end = Alignment.bottomCenter}) =>
    Paint()..shader = LinearGradient(begin: begin, end: end, colors: colors).createShader(r);

void _text(Canvas canvas, String s, double size, Color color) {
  final tp = TextPainter(text: TextSpan(text: s, style: sancLabel(size, color, spacing: 0)), textDirection: TextDirection.ltr)..layout();
  tp.paint(canvas, Offset(-tp.width / 2, -tp.height / 2));
}

// ───────── 鱼 ─────────

/// 一条鱼的通用画法：头朝左。[l] 身长、[h] 身高、[tail] 尾巴张多开、[dorsal] 背鳍多高。
/// [pattern] 画在身子里面（已经按身子的轮廓裁好）。
void _fish(
  Canvas canvas, {
  required double l,
  required double h,
  required Color back,
  required Color belly,
  required Color fin,
  double tail = 16,
  double dorsal = 9,
  double eye = 3.2,
  bool spiny = false,
  void Function(Canvas canvas, Rect box)? pattern,
}) {
  final x0 = -l / 2 - 4, x1 = x0 + l * 0.8; // 身子从 x0 到 x1，后面是尾巴
  final box = Rect.fromLTRB(x0, -h / 2, x1, h / 2);
  final body = Path()
    ..moveTo(x0, 1)
    ..cubicTo(x0 + l * 0.10, -h * 0.62, x0 + l * 0.50, -h * 0.62, x1, -h * 0.09)
    ..lineTo(x1, h * 0.09)
    ..cubicTo(x0 + l * 0.50, h * 0.62, x0 + l * 0.10, h * 0.60, x0, 1)
    ..close();
  final finPaint = _fill(fin);
  // 尾巴
  final tx = x1 + l * 0.24;
  canvas.drawPath(
      Path()
        ..moveTo(x1 - 2, 0)
        ..quadraticBezierTo(x1 + l * 0.10, -tail * 0.5, tx, -tail)
        ..quadraticBezierTo(tx - l * 0.09, 0, tx, tail)
        ..quadraticBezierTo(x1 + l * 0.10, tail * 0.5, x1 - 2, 0)
        ..close(),
      finPaint);
  // 背鳍、腹鳍
  final d0 = x0 + l * 0.28, d1 = x0 + l * 0.62;
  if (spiny) {
    final p = Path()..moveTo(d0, -h * 0.40);
    for (var i = 0; i < 6; i++) {
      final x = d0 + (d1 - d0) * (i + 0.5) / 6;
      p
        ..lineTo(x - 1, -h * 0.44 - dorsal * (1 - i * 0.08))
        ..lineTo(x + 2.5, -h * 0.42);
    }
    p
      ..lineTo(d1, -h * 0.30)
      ..close();
    canvas.drawPath(p, finPaint);
  } else {
    canvas.drawPath(
        Path()
          ..moveTo(d0, -h * 0.40)
          ..quadraticBezierTo(d0 + 6, -h * 0.46 - dorsal, d1, -h * 0.30)
          ..close(),
        finPaint);
  }
  canvas.drawPath(
      Path()
        ..moveTo(x0 + l * 0.34, h * 0.42)
        ..quadraticBezierTo(x0 + l * 0.42, h * 0.48 + dorsal * 0.8, x0 + l * 0.52, h * 0.40)
        ..close(),
      finPaint);
  // 身子：上深下浅
  canvas.drawPath(body, _grad(box, [back, Color.lerp(back, belly, 0.55)!, belly]));
  if (pattern != null) {
    canvas.save();
    canvas.clipPath(body);
    pattern(canvas, box);
    canvas.restore();
  }
  // 鳃、胸鳍、眼睛
  canvas.drawArc(Rect.fromCircle(center: Offset(x0 + l * 0.13, 0), radius: h * 0.36), -1.0, 2.0, false, _line(Color.lerp(back, Colors.black, 0.25)!.withValues(alpha: 0.55), 1.3));
  canvas.drawPath(
      Path()
        ..moveTo(x0 + l * 0.26, h * 0.10)
        ..quadraticBezierTo(x0 + l * 0.38, h * 0.14, x0 + l * 0.36, h * 0.34)
        ..quadraticBezierTo(x0 + l * 0.27, h * 0.28, x0 + l * 0.26, h * 0.10)
        ..close(),
      _fill(fin.withValues(alpha: 0.85)));
  final e = Offset(x0 + l * 0.12, -h * 0.12);
  canvas.drawCircle(e, eye, _fill(const Color(0xFFFFFBF0)));
  canvas.drawCircle(e, eye * 0.55, _fill(const Color(0xFF1B1512)));
  canvas.drawCircle(e.translate(-eye * 0.2, -eye * 0.25), eye * 0.2, _fill(Colors.white));
}

/// 一排排鱼鳞（小弧线）
void _scales(Canvas canvas, Rect box, Color color, {double step = 7}) {
  final p = _line(color, 1);
  var row = 0;
  for (var y = box.top + 4; y < box.bottom; y += step * 0.8) {
    for (var x = box.left + box.width * 0.24 + (row.isEven ? 0 : step / 2); x < box.right; x += step) {
      canvas.drawArc(Rect.fromCircle(center: Offset(x, y), radius: step * 0.5), -1.2, 2.4, false, p);
    }
    row++;
  }
}

/// 鲫鱼：身子高，银灰的背
void _crucian(Canvas canvas) => _fish(canvas,
    l: 78, h: 44, back: const Color(0xFF6F7E78), belly: const Color(0xFFE9E6D6), fin: const Color(0xFF8B8F7A), tail: 17, dorsal: 9,
    pattern: (c, box) => _scales(c, box, const Color(0x55FFFFFF)));

/// 白条：细长，一身银白，背上一道青
void _whitebait(Canvas canvas) => _fish(canvas,
    l: 84, h: 22, back: const Color(0xFF86A9A6), belly: const Color(0xFFF7FAF6), fin: const Color(0xFFB6CBC6), tail: 12, dorsal: 5, eye: 3,
    pattern: (c, box) => c.drawLine(Offset(box.left + 14, 0), Offset(box.right, 0), _line(const Color(0x99FFFFFF), 2)));

/// 银鱼：更细，近乎透明，能看见一条脊骨
void _silver(Canvas canvas) {
  canvas.saveLayer(const Rect.fromLTRB(-50, -50, 50, 50), Paint()..color = const Color(0xD9FFFFFF));
  _fish(canvas,
      l: 86, h: 15, back: const Color(0xFFDDEBF0), belly: const Color(0xFFFFFFFF), fin: const Color(0xFFCFE2EA), tail: 9, dorsal: 3, eye: 3.4,
      pattern: (c, box) {
    c.drawLine(Offset(box.left + 16, -1), Offset(box.right, 0), _line(const Color(0xFF9DB9C6), 1.2));
    for (var x = box.left + 22; x < box.right - 4; x += 5) {
      c.drawLine(Offset(x, -4), Offset(x + 1.5, 3.5), _line(const Color(0x669DB9C6), 0.8));
    }
  });
  canvas.restore();
  canvas.drawPath(Shapes.sparkle(const Offset(8, -16), 5), _fill(const Color(0xCCFFFFFF)));
}

/// 鲈鱼：大嘴，背上一排硬刺，身上有黑点
void _bass(Canvas canvas) {
  _fish(canvas,
      l: 84, h: 34, back: const Color(0xFF55664A), belly: const Color(0xFFE6E7CF), fin: const Color(0xFF6E7A55), tail: 15, dorsal: 12, spiny: true,
      pattern: (c, box) {
    final rnd = math.Random(5);
    for (var i = 0; i < 16; i++) {
      c.drawCircle(Offset(box.left + 18 + rnd.nextDouble() * (box.width - 22), box.top + 4 + rnd.nextDouble() * box.height * 0.5), 1.4, _fill(const Color(0xAA20281C)));
    }
    c.drawLine(Offset(box.left + 16, 2), Offset(box.right, 0), _line(const Color(0x8820281C), 1));
  });
  // 一张大嘴
  canvas.drawPath(
      Path()
        ..moveTo(-46, 1)
        ..lineTo(-36, 6.5),
      _line(const Color(0xFF2B3324), 1.8));
}

/// 鳜鱼：身子高，一身褐色的花斑
void _mandarin(Canvas canvas) => _fish(canvas,
    l: 80, h: 42, back: const Color(0xFFA0803E), belly: const Color(0xFFEFE2B4), fin: const Color(0xFF8A6A2E), tail: 15, dorsal: 12, spiny: true,
    pattern: (c, box) {
      final rnd = math.Random(11);
      for (var i = 0; i < 13; i++) {
        final o = Offset(box.left + 16 + rnd.nextDouble() * (box.width - 18), box.top + 3 + rnd.nextDouble() * (box.height - 8));
        c.drawOval(Rect.fromCenter(center: o, width: 6 + rnd.nextDouble() * 9, height: 4 + rnd.nextDouble() * 6), _fill(const Color(0xB33E2A12)));
      }
      // 一道斜着过眼睛的黑纹
      c.drawLine(Offset(box.left + 4, -10), Offset(box.left + 22, 4), _line(const Color(0x993E2A12), 3));
    });

/// 金鳞鲤：金色的鳞，嘴边两根须
void _carpGold(Canvas canvas) {
  canvas.drawCircle(Offset.zero, 40, Paint()..shader = RadialGradient(colors: [SancColors.gold.withValues(alpha: 0.35), SancColors.gold.withValues(alpha: 0)]).createShader(Rect.fromCircle(center: Offset.zero, radius: 40)));
  _fish(canvas,
      l: 86, h: 40, back: const Color(0xFFD9962A), belly: const Color(0xFFFFF0B8), fin: const Color(0xFFE9703A), tail: 19, dorsal: 10,
      pattern: (c, box) {
    _scales(c, box, const Color(0xCCFFF6CF), step: 8);
    c.drawOval(Rect.fromCenter(center: Offset(box.center.dx - 4, box.top + 9), width: box.width * 0.6, height: 8), _fill(const Color(0x55FFFFFF)));
  });
  final whisker = _line(const Color(0xFFB36A1C), 1.3);
  canvas.drawPath(Path()..moveTo(-45, 4)..quadraticBezierTo(-48, 10, -43, 14), whisker);
  canvas.drawPath(Path()..moveTo(-42, 6)..quadraticBezierTo(-43, 13, -37, 15), whisker);
  canvas.drawPath(Shapes.sparkle(const Offset(20, -24), 6), _fill(const Color(0xFFFFF6CF)));
  canvas.drawPath(Shapes.sparkle(const Offset(-18, 26), 4), _fill(const Color(0xCCFFF6CF)));
}

/// 月光鱼：淡蓝的身子带着光，尾巴像一弯月牙
void _moonFish(Canvas canvas) {
  const glow = Color(0xFFBFE2FF);
  canvas.drawCircle(Offset.zero, 42, Paint()..shader = RadialGradient(colors: [glow.withValues(alpha: 0.45), glow.withValues(alpha: 0)]).createShader(Rect.fromCircle(center: Offset.zero, radius: 42)));
  // 月牙尾
  final tail = Path.combine(
    PathOperation.difference,
    Path()..addOval(Rect.fromCircle(center: const Offset(27, 0), radius: 19)),
    Path()..addOval(Rect.fromCircle(center: const Offset(38, 0), radius: 17)),
  );
  canvas.drawPath(tail, _fill(const Color(0xFFEAF6FF)));
  // 圆圆的身子
  const box = Rect.fromLTRB(-40, -19, 16, 19);
  final body = Path()..addOval(box);
  canvas.drawPath(body, _grad(box, const [Color(0xFF8FB9E8), Color(0xFFD8ECFF), Color(0xFFFFFFFF)]));
  canvas.save();
  canvas.clipPath(body);
  for (var i = 0; i < 3; i++) {
    canvas.drawCircle(Offset(-8.0 + i * 9, -3.0 + (i.isEven ? 0 : 7)), 2.2, _fill(const Color(0xCCFFFFFF)));
  }
  canvas.restore();
  canvas.drawPath(
      Path()
        ..moveTo(-20, -17)
        ..quadraticBezierTo(-8, -32, 6, -14)
        ..close(),
      _fill(const Color(0xCCBFE2FF)));
  canvas.drawCircle(const Offset(-28, -4), 3.4, _fill(const Color(0xFF1D2B4A)));
  canvas.drawCircle(const Offset(-29, -5), 1, _fill(Colors.white));
  canvas.drawPath(Shapes.sparkle(const Offset(-6, -30), 5), _fill(Colors.white));
  canvas.drawPath(Shapes.sparkle(const Offset(14, 28), 3.5), _fill(const Color(0xCCFFFFFF)));
}

/// 小金鱼：圆滚滚，一条飘着的大尾巴
void _goldfish(Canvas canvas) {
  const red = Color(0xFFE8552E), light = Color(0xFFFFB45C);
  // 两片纱一样的尾巴
  for (final s in const [-1.0, 1.0]) {
    canvas.drawPath(
        Path()
          ..moveTo(8, 0)
          ..cubicTo(22, s * 4, 30, s * 26, 44, s * 28)
          ..cubicTo(38, s * 16, 40, s * 6, 34, 0)
          ..close(),
        _grad(const Rect.fromLTRB(8, -28, 44, 28), [red.withValues(alpha: 0.95), light.withValues(alpha: 0.7)], begin: Alignment.centerLeft, end: Alignment.centerRight));
  }
  const box = Rect.fromLTRB(-38, -20, 14, 22);
  canvas.drawPath(
      Path()
        ..moveTo(-12, -18)
        ..quadraticBezierTo(-2, -34, 8, -12)
        ..close(),
      _fill(light));
  canvas.drawOval(box, _grad(box, const [red, Color(0xFFF58A3C), Color(0xFFFFE2B0)]));
  canvas.drawOval(const Rect.fromLTRB(-22, 0, -4, 16), _fill(const Color(0x66FFFFFF)));
  // 鼓出来的眼睛
  canvas.drawCircle(const Offset(-28, -7), 5, _fill(const Color(0xFFFFF6E6)));
  canvas.drawCircle(const Offset(-29, -7), 2.6, _fill(const Color(0xFF1B1512)));
  canvas.drawCircle(const Offset(-40, -16), 2, _line(const Color(0x99FFFFFF), 1));
  canvas.drawCircle(const Offset(-44, -25), 3, _line(const Color(0x99FFFFFF), 1));
}

/// 泥鳅：长长一条弯着，嘴边几根须
void _loach(Canvas canvas) {
  final spine = Path()
    ..moveTo(-38, 6)
    ..cubicTo(-18, -22, 0, 26, 20, 2)
    ..cubicTo(28, -8, 36, -8, 40, -2);
  canvas.drawPath(spine, _line(const Color(0xFF5E4A2C), 15));
  canvas.drawPath(spine, _line(const Color(0xFF8E7444), 11));
  // 肚子上一道浅色、背上的小黑点
  canvas.drawPath(spine.shift(const Offset(0, 3)), _line(const Color(0x66F1DFAE), 3));
  final rnd = math.Random(2);
  for (final m in spine.computeMetrics()) {
    for (var d = 10.0; d < m.length - 6; d += 7) {
      final t = m.getTangentForOffset(d)!;
      canvas.drawCircle(t.position.translate(0, -3 + rnd.nextDouble() * 2), 1.2, _fill(const Color(0xAA2E2212)));
    }
  }
  // 尾巴
  canvas.drawOval(Rect.fromCenter(center: const Offset(43, -1), width: 9, height: 14), _fill(const Color(0xFF6E5732)));
  // 头、眼睛、须
  canvas.drawCircle(const Offset(-38, 6), 8, _fill(const Color(0xFF8E7444)));
  canvas.drawCircle(const Offset(-40, 3), 1.8, _fill(const Color(0xFF14100C)));
  final w = _line(const Color(0xFF5E4A2C), 1.2);
  canvas.drawLine(const Offset(-45, 8), const Offset(-50, 5), w);
  canvas.drawLine(const Offset(-45, 9), const Offset(-51, 11), w);
  canvas.drawLine(const Offset(-43, 12), const Offset(-47, 17), w);
}

/// 青虾：弓着的透明身子，一节一节，两根长须
void _shrimp(Canvas canvas) {
  const shell = Color(0xFF8FBFA6), dark = Color(0xFF4F8870);
  // 身子：一段弧，由粗到细
  final segs = <(Offset, double)>[];
  for (var i = 0; i < 7; i++) {
    final a = -2.5 + i * 0.52;
    segs.add((Offset(4 + 22 * math.cos(a), 4 + 22 * math.sin(a)), 12.5 - i * 1.2));
  }
  for (final (o, r) in segs.reversed) {
    canvas.drawCircle(o, r, _fill(shell.withValues(alpha: 0.92)));
    canvas.drawCircle(o, r, _line(dark.withValues(alpha: 0.7), 1));
  }
  // 尾扇
  final (to, _) = segs.last;
  for (final a in const [0.5, 1.0, 1.5]) {
    canvas.drawOval(Rect.fromCenter(center: to + Offset(-8 * math.cos(a), 8 * math.sin(a)), width: 7, height: 11), _fill(dark));
  }
  // 头、眼睛、须、小脚
  final (ho, _) = segs.first;
  canvas.drawOval(Rect.fromCenter(center: ho.translate(-7, 3), width: 22, height: 17), _fill(shell));
  canvas.drawCircle(ho.translate(-14, -2), 2.2, _fill(const Color(0xFF14100C)));
  final w = _line(dark, 1.1);
  canvas.drawPath(Path()..moveTo(ho.dx - 16, ho.dy + 1)..quadraticBezierTo(-46, -34, -10, -42), w);
  canvas.drawPath(Path()..moveTo(ho.dx - 16, ho.dy + 3)..quadraticBezierTo(-52, -16, -40, -40), w);
  for (var i = 1; i < 5; i++) {
    final (o, r) = segs[i];
    canvas.drawLine(o.translate(0, r * 0.2), o.translate(-5, r + 5), w);
  }
}

/// 大闸蟹：青背，一对大钳子，八条腿
void _crab(Canvas canvas) {
  const back = Color(0xFF4F6B4A), leg = Color(0xFF7A5A2E);
  final l = _line(leg, 3.2);
  for (final s in const [-1.0, 1.0]) {
    for (var i = 0; i < 4; i++) {
      final y = -2.0 + i * 7;
      canvas.drawPath(
          Path()
            ..moveTo(s * 20, y)
            ..lineTo(s * (34 + i * 1.5), y - 6 + i * 4)
            ..lineTo(s * (42 - i * 2), y + 8 + i * 3),
          l);
    }
    // 钳子
    canvas.drawPath(Path()..moveTo(s * 16, -12)..quadraticBezierTo(s * 30, -22, s * 30, -30), _line(leg, 4.5));
    canvas.drawOval(Rect.fromCenter(center: Offset(s * 31, -35), width: 15, height: 12), _fill(const Color(0xFF5E7A52)));
    canvas.drawPath(
        Path()
          ..moveTo(s * 27, -39)
          ..lineTo(s * 30, -46)
          ..lineTo(s * 33, -39)
          ..close(),
        _fill(const Color(0xFFF1E3C4)));
    // 眼睛
    canvas.drawLine(Offset(s * 6, -14), Offset(s * 7, -20), _line(back, 1.6));
    canvas.drawCircle(Offset(s * 7, -21), 2.2, _fill(const Color(0xFF14100C)));
  }
  const box = Rect.fromLTRB(-25, -16, 25, 20);
  final shell = Path()
    ..moveTo(-25, -4)
    ..cubicTo(-22, -18, 22, -18, 25, -4)
    ..cubicTo(26, 12, 12, 20, 0, 20)
    ..cubicTo(-12, 20, -26, 12, -25, -4)
    ..close();
  canvas.drawPath(shell, _grad(box, const [Color(0xFF6B8A5E), back, Color(0xFF34492F)]));
  // 背上的纹
  final g = _line(const Color(0x66172214), 1.3);
  canvas.drawPath(Path()..moveTo(-10, -6)..quadraticBezierTo(0, 0, 10, -6), g);
  canvas.drawPath(Path()..moveTo(-8, 4)..quadraticBezierTo(0, 9, 8, 4), g);
  canvas.drawOval(const Rect.fromLTRB(-16, -12, -2, -6), _fill(const Color(0x33FFFFFF)));
}

/// 一团水草
void _weed(Canvas canvas) {
  final rnd = math.Random(4);
  for (var i = 0; i < 9; i++) {
    final a = rnd.nextDouble() * math.pi * 2;
    final p = Path()..moveTo(8 * math.cos(a), 6 + 6 * math.sin(a));
    final r = 22 + rnd.nextDouble() * 14;
    p.cubicTo(r * math.cos(a + 1.2), r * math.sin(a + 1.2) * 0.8, r * math.cos(a + 2.6), r * math.sin(a + 2.2) * 0.8 + 6, r * 0.9 * math.cos(a + 3.6), 4 + r * 0.6 * math.sin(a + 3.6));
    canvas.drawPath(p, _line(Color.lerp(const Color(0xFF3F6B3A), const Color(0xFF7FA05A), rnd.nextDouble())!, 3 + rnd.nextDouble() * 2));
  }
  // 滴下来的两滴水
  for (final o in const [Offset(-12, 34), Offset(14, 38)]) {
    canvas.drawPath(
        Path()
          ..moveTo(o.dx, o.dy - 6)
          ..quadraticBezierTo(o.dx + 4, o.dy, o.dx, o.dy + 3)
          ..quadraticBezierTo(o.dx - 4, o.dy, o.dx, o.dy - 6)
          ..close(),
        _fill(const Color(0xCC9FD3E6)));
  }
}

// ───────── 口粮 ─────────

/// 小饼干：三块小骨头形的饼干
void _kibble(Canvas canvas) {
  for (final (o, rot, c) in const [
    (Offset(-12, -14), 0.4, Color(0xFFD9A25C)),
    (Offset(14, -2), -0.5, Color(0xFFC98A45)),
    (Offset(-8, 18), -0.15, Color(0xFFE0B06C)),
  ]) {
    Shapes.bone(canvas, o, 22, rot: rot, color: c, edge: const Color(0xFF8A5A2B));
    canvas.save();
    canvas.translate(o.dx, o.dy);
    canvas.rotate(rot);
    for (final x in const [-5.0, 0.0, 5.0]) {
      canvas.drawCircle(Offset(x, 0), 0.9, _fill(const Color(0xFF8A5A2B)));
    }
    canvas.restore();
  }
}

/// 小鱼干（口粮）：一根草绳上串着两条
void _driedFishPair(Canvas canvas) {
  canvas.drawPath(Path()..moveTo(-36, -30)..quadraticBezierTo(0, -40, 36, -28), _line(SancColors.ropeShade, 2.4));
  Shapes.driedFish(canvas, const Offset(-14, 0), 30, rot: math.pi / 2 - 0.12);
  Shapes.driedFish(canvas, const Offset(15, 4), 30, rot: math.pi / 2 + 0.14);
}

/// 肉骨头：一根大骨头，中间裹着一圈肉
void _meatBone(Canvas canvas) {
  Shapes.bone(canvas, Offset.zero, 44, rot: -0.6);
  canvas.save();
  canvas.rotate(-0.6);
  const box = Rect.fromLTRB(-21, -17, 21, 17);
  final meat = RRect.fromRectAndRadius(box, const Radius.circular(15));
  canvas.drawRRect(meat, _grad(box, const [Color(0xFFD9694A), Color(0xFFA83F2A)]));
  canvas.drawRRect(meat.deflate(4), _line(const Color(0x55FFD9C2), 2));
  canvas.drawOval(const Rect.fromLTRB(-13, -12, 1, -6), _fill(const Color(0x66FFFFFF)));
  canvas.restore();
}

/// 猫条：一支撕开口的小袋子，挤出一点
void _cream(Canvas canvas) {
  canvas.save();
  canvas.rotate(0.5);
  const box = Rect.fromLTRB(-11, -30, 11, 38);
  canvas.drawRRect(RRect.fromRectAndRadius(box, const Radius.circular(4)), _grad(box, const [Color(0xFFF9D36B), Color(0xFFF2A54A)], begin: Alignment.centerLeft, end: Alignment.centerRight));
  canvas.drawRect(const Rect.fromLTRB(-11, 30, 11, 38), _fill(const Color(0xFFD9853A)));
  // 袋子上一个小猫头
  canvas.drawCircle(const Offset(0, 8), 6.5, _fill(const Color(0xFFFFF6E0)));
  canvas.drawPath(Path()..moveTo(-6, 4)..lineTo(-6, -3)..lineTo(-1, 2)..close(), _fill(const Color(0xFFFFF6E0)));
  canvas.drawPath(Path()..moveTo(6, 4)..lineTo(6, -3)..lineTo(1, 2)..close(), _fill(const Color(0xFFFFF6E0)));
  canvas.drawCircle(const Offset(-2.4, 8), 0.9, _fill(SancColors.ink));
  canvas.drawCircle(const Offset(2.4, 8), 0.9, _fill(SancColors.ink));
  // 撕开的口和挤出来的肉泥
  canvas.drawPath(
      Path()
        ..moveTo(-11, -30)
        ..lineTo(-6, -34)
        ..lineTo(-2, -29)
        ..lineTo(3, -34)
        ..lineTo(7, -29)
        ..lineTo(11, -32)
        ..lineTo(11, -26)
        ..lineTo(-11, -26)
        ..close(),
      _fill(const Color(0xFFF9D36B)));
  canvas.drawPath(
      Path()
        ..moveTo(-5, -32)
        ..cubicTo(-9, -44, 8, -40, 3, -48)
        ..cubicTo(12, -42, 8, -34, 5, -32)
        ..close(),
      _fill(const Color(0xFFE9A79A)));
  canvas.restore();
}

// ───────── 收藏品里要另外摆一下的 ─────────

/// 小野花：一朵开着的、一个花苞，连着一小截茎
void _wildFlower(Canvas canvas) {
  final stem = _line(const Color(0xFF5E9450), 2.6);
  canvas.drawPath(Path()..moveTo(0, -8)..quadraticBezierTo(6, 20, -2, 42), stem);
  canvas.drawPath(Path()..moveTo(2, 16)..quadraticBezierTo(18, 10, 22, -4), stem);
  Shapes.leaf(canvas, const Offset(-10, 26), 11, rot: -1.0, color: const Color(0xFF6FA85C));
  canvas.drawOval(Rect.fromCenter(center: const Offset(23, -9), width: 9, height: 13), _fill(const Color(0xFFF4B6C8)));
  Shapes.flower(canvas, const Offset(0, -14), 24, const Color(0xFFFFF4F0), heart: const Color(0xFFF2C14E));
}

/// 珍珠：躺在半开的贝壳里
void _pearlInShell(Canvas canvas) {
  Shapes.shell(canvas, const Offset(0, 12), 34, rot: math.pi, color: const Color(0xFFD9C3CF));
  canvas.drawCircle(const Offset(0, -4), 26, Paint()..shader = RadialGradient(colors: [Colors.white.withValues(alpha: 0.5), Colors.white.withValues(alpha: 0)]).createShader(Rect.fromCircle(center: const Offset(0, -4), radius: 26)));
  Shapes.pearl(canvas, const Offset(0, -4), 15);
  canvas.drawPath(Shapes.sparkle(const Offset(20, -24), 5), _fill(Colors.white));
}

/// 可以重复用的小图形。每个都以 [c] 为中心、大小约为 [s]（半径），[rot] 是转多少弧度。
/// 里面按 -1~1 的格子画，再整体放大，所以线宽也跟着大小走。
abstract final class Shapes {
  static void _at(Canvas canvas, Offset c, double s, double rot, void Function() draw) {
    canvas.save();
    canvas.translate(c.dx, c.dy);
    if (rot != 0) canvas.rotate(rot);
    canvas.scale(s);
    draw();
    canvas.restore();
  }

  /// 四角的小闪光
  static Path sparkle(Offset c, double r) {
    final q = r * 0.22;
    return Path()
      ..moveTo(c.dx, c.dy - r)
      ..quadraticBezierTo(c.dx + q, c.dy - q, c.dx + r, c.dy)
      ..quadraticBezierTo(c.dx + q, c.dy + q, c.dx, c.dy + r)
      ..quadraticBezierTo(c.dx - q, c.dy + q, c.dx - r, c.dy)
      ..quadraticBezierTo(c.dx - q, c.dy - q, c.dx, c.dy - r)
      ..close();
  }

  /// 爪印：一个大肉垫、四个小脚趾
  static void paw(Canvas canvas, Offset c, double s, {double rot = 0, Color color = const Color(0xFFF6E7CC)}) => _at(canvas, c, s, rot, () {
        final p = _fill(color);
        canvas.drawPath(
            Path()
              ..moveTo(0, 0.0)
              ..cubicTo(0.5, -0.05, 0.75, 0.45, 0.5, 0.75)
              ..cubicTo(0.3, 0.95, -0.3, 0.95, -0.5, 0.75)
              ..cubicTo(-0.75, 0.45, -0.5, -0.05, 0, 0.0)
              ..close(),
            p);
        for (final (x, y, r) in const [(-0.68, -0.12, 0.2), (-0.26, -0.55, 0.23), (0.26, -0.55, 0.23), (0.68, -0.12, 0.2)]) {
          canvas.drawOval(Rect.fromCenter(center: Offset(x, y), width: r * 1.7, height: r * 2.2), p);
        }
      });

  /// 骨头
  static void bone(Canvas canvas, Offset c, double s, {double rot = 0, Color color = const Color(0xFFF6EDD8), Color edge = const Color(0xFFBFAE8C)}) => _at(canvas, c, s, rot, () {
        final path = Path()..addRRect(RRect.fromRectAndRadius(const Rect.fromLTRB(-0.6, -0.15, 0.6, 0.15), const Radius.circular(0.1)));
        for (final x in const [-0.66, 0.66]) {
          for (final y in const [-0.19, 0.19]) {
            path.addOval(Rect.fromCircle(center: Offset(x, y), radius: 0.23));
          }
        }
        final whole = Path.combine(PathOperation.union, path, Path());
        canvas.drawPath(whole, _fill(color));
        canvas.drawPath(whole, _line(edge, 0.05));
      });

  /// 扇贝：一把小扇子，带一道道棱
  static void shell(Canvas canvas, Offset c, double s, {double rot = 0, Color color = const Color(0xFFF7D9C8)}) => _at(canvas, c, s, rot, () {
        final rim = Color.lerp(color, const Color(0xFF8A4A3A), 0.45)!;
        canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTRB(-0.34, 0.62, 0.34, 0.92), const Radius.circular(0.08)), _fill(Color.lerp(color, rim, 0.4)!));
        final fan = Path()
          ..moveTo(-0.2, 0.8)
          ..cubicTo(-1.2, 0.45, -1.05, -0.9, 0, -0.9)
          ..cubicTo(1.05, -0.9, 1.2, 0.45, 0.2, 0.8)
          ..close();
        canvas.drawPath(fan, _grad(const Rect.fromLTRB(-1, -0.9, 1, 0.8), [Color.lerp(color, Colors.white, 0.5)!, color, Color.lerp(color, rim, 0.3)!]));
        canvas.save();
        canvas.clipPath(fan);
        for (var i = -3; i <= 3; i++) {
          final a = -math.pi / 2 + i * 0.36;
          canvas.drawLine(const Offset(0, 0.78), Offset(1.3 * math.cos(a), 0.78 + 1.75 * math.sin(a)), _line(rim.withValues(alpha: 0.7), 0.05));
        }
        canvas.restore();
        canvas.drawPath(fan, _line(rim, 0.06));
      });

  /// 海螺：一圈一圈往尖上收
  static void conch(Canvas canvas, Offset c, double s, {double rot = 0}) => _at(canvas, c, s, rot, () {
        const base = Color(0xFFEBCFA4), dark = Color(0xFFB07C4E);
        final body = Path()
          ..moveTo(-0.3, -0.98)
          ..cubicTo(0.75, -0.6, 1.05, 0.35, 0.3, 0.85)
          ..cubicTo(-0.25, 1.1, -0.95, 0.55, -0.7, -0.1)
          ..cubicTo(-0.6, -0.4, -0.4, -0.7, -0.3, -0.98)
          ..close();
        canvas.drawPath(body, _grad(const Rect.fromLTRB(-1, -1, 1, 1), const [Color(0xFFFFF1D6), base, Color(0xFFCF9C68)], begin: Alignment.topLeft, end: Alignment.bottomRight));
        canvas.save();
        canvas.clipPath(body);
        for (var i = 0; i < 5; i++) {
          final y = -0.72 + i * 0.3;
          canvas.drawPath(Path()..moveTo(-1, y + 0.25)..quadraticBezierTo(0, y - 0.2 + i * 0.03, 1, y + 0.3), _line(dark.withValues(alpha: 0.75), 0.06));
        }
        canvas.restore();
        // 螺口
        canvas.drawOval(Rect.fromCenter(center: const Offset(0.12, 0.42), width: 0.78, height: 0.5), _fill(const Color(0xFFF7B9A8)));
        canvas.drawOval(Rect.fromCenter(center: const Offset(0.16, 0.44), width: 0.5, height: 0.28), _fill(const Color(0xFFC9786A)));
        canvas.drawPath(body, _line(dark, 0.06));
      });

  /// 彩色鹅卵石：圆圆的一颗，带几道花纹
  static void pebble(Canvas canvas, Offset c, double s, {double rot = -0.2}) => _at(canvas, c, s, rot, () {
        const box = Rect.fromLTRB(-0.95, -0.62, 0.95, 0.62);
        final stone = Path()..addOval(box);
        canvas.drawPath(stone, _grad(box, const [Color(0xFFA9C2C4), Color(0xFF7F9BA3), Color(0xFF566F7A)]));
        canvas.save();
        canvas.clipPath(stone);
        canvas.drawPath(Path()..moveTo(-1, -0.1)..quadraticBezierTo(0, -0.5, 1, 0.0), _line(const Color(0xFFF3E8CF), 0.14));
        canvas.drawPath(Path()..moveTo(-1, 0.2)..quadraticBezierTo(0, -0.15, 1, 0.3), _line(const Color(0xFFD98A62), 0.11));
        canvas.drawPath(Path()..moveTo(-1, 0.42)..quadraticBezierTo(0, 0.1, 1, 0.52), _line(const Color(0xFFE8BB4D), 0.06));
        canvas.restore();
        canvas.drawOval(const Rect.fromLTRB(-0.6, -0.5, -0.1, -0.3), _fill(const Color(0x66FFFFFF)));
      });

  static Path _heartLeaf() => Path()
    ..moveTo(0, 0)
    ..cubicTo(-0.8, -0.2, -0.62, -1.02, 0, -0.64)
    ..cubicTo(0.62, -1.02, 0.8, -0.2, 0, 0)
    ..close();

  /// 四叶草
  static void clover(Canvas canvas, Offset c, double s, {double rot = 0.3, bool stem = true}) => _at(canvas, c, s, rot, () {
        if (stem) canvas.drawPath(Path()..moveTo(0, 0)..quadraticBezierTo(0.25, 0.6, -0.05, 1.2), _line(const Color(0xFF4E8A45), 0.09));
        for (var i = 0; i < 4; i++) {
          canvas.save();
          canvas.rotate(i * math.pi / 2);
          canvas.drawPath(_heartLeaf(), _fill(i.isEven ? const Color(0xFF5FA85A) : const Color(0xFF6DB866)));
          canvas.drawLine(Offset.zero, const Offset(0, -0.55), _line(const Color(0xFFBFE3A8), 0.045));
          canvas.restore();
        }
      });

  /// 松果：一层层张开的鳞片
  static void pinecone(Canvas canvas, Offset c, double s, {double rot = 0.15}) => _at(canvas, c, s, rot, () {
        const base = Color(0xFF7A4E2B), edge = Color(0xFFC08A52);
        canvas.drawLine(const Offset(0, -0.8), const Offset(0.05, -1.0), _line(base, 0.12));
        for (var row = 5; row >= 0; row--) {
          final y = -0.62 + row * 0.26;
          final half = 0.7 * math.sin((row + 1.2) / 7.4 * math.pi);
          final n = math.max(1, (half / 0.2).round());
          for (var i = 0; i <= n; i++) {
            final x = n == 0 ? 0.0 : -half + 2 * half * i / n + (row.isOdd ? 0.0 : 0.02);
            final o = Offset(x, y);
            final scale = Path()
              ..moveTo(o.dx - 0.2, o.dy - 0.1)
              ..quadraticBezierTo(o.dx, o.dy + 0.36, o.dx + 0.2, o.dy - 0.1)
              ..close();
            canvas.drawPath(scale, _fill(Color.lerp(base, edge, (5 - row) * 0.08)!));
            canvas.drawPath(scale, _line(edge, 0.035));
          }
        }
      });

  /// 银杏叶：一把小扇子，中间一道缺口
  static void ginkgo(Canvas canvas, Offset c, double s, {double rot = 0, Color color = const Color(0xFFF2C84B)}) => _at(canvas, c, s, rot, () {
        final vein = Color.lerp(color, const Color(0xFF8A5A14), 0.45)!;
        canvas.drawLine(const Offset(0, 0.25), const Offset(0.08, 1.0), _line(vein, 0.07));
        final fan = Path()
          ..moveTo(0, 0.3)
          ..lineTo(-0.98, -0.3)
          ..cubicTo(-0.8, -0.95, -0.2, -1.0, -0.06, -0.62)
          ..lineTo(0, -0.42)
          ..lineTo(0.06, -0.62)
          ..cubicTo(0.2, -1.0, 0.8, -0.95, 0.98, -0.3)
          ..close();
        canvas.drawPath(fan, _grad(const Rect.fromLTRB(-1, -1, 1, 0.3), [Color.lerp(color, Colors.white, 0.3)!, color]));
        canvas.save();
        canvas.clipPath(fan);
        for (var i = -5; i <= 5; i++) {
          final a = -math.pi / 2 + i * 0.2;
          canvas.drawLine(const Offset(0, 0.3), Offset(1.4 * math.cos(a), 0.3 + 1.4 * math.sin(a)), _line(vein.withValues(alpha: 0.5), 0.03));
        }
        canvas.restore();
      });

  /// 枫叶：五个尖
  static void maple(Canvas canvas, Offset c, double s, {double rot = 0, Color color = const Color(0xFFD2472F)}) => _at(canvas, c, s, rot, () {
        final vein = Color.lerp(color, const Color(0xFF5A1408), 0.5)!;
        canvas.drawLine(const Offset(0, 0.2), const Offset(0.1, 1.0), _line(vein, 0.07));
        const pts = [(160.0, 0.72), (188.0, 0.36), (215.0, 0.95), (242.0, 0.4), (270.0, 1.0), (298.0, 0.4), (325.0, 0.95), (352.0, 0.36), (20.0, 0.72), (90.0, 0.3)];
        final leaf = Path();
        for (var i = 0; i < pts.length; i++) {
          final (deg, r) = pts[i];
          final a = deg * math.pi / 180;
          final p = Offset(r * math.cos(a), r * math.sin(a));
          i == 0 ? leaf.moveTo(p.dx, p.dy) : leaf.lineTo(p.dx, p.dy);
        }
        leaf.close();
        canvas.drawPath(leaf, _grad(const Rect.fromLTRB(-1, -1, 1, 0.4), [Color.lerp(color, const Color(0xFFFFB04A), 0.35)!, color]));
        for (final deg in const [160.0, 215.0, 270.0, 325.0, 20.0]) {
          final a = deg * math.pi / 180;
          canvas.drawLine(const Offset(0, 0.2), Offset(0.8 * math.cos(a), 0.8 * math.sin(a) * 0.9), _line(vein.withValues(alpha: 0.6), 0.04));
        }
      });

  /// 一片普通的叶子（尖朝上）
  static void leaf(Canvas canvas, Offset c, double s, {double rot = 0, Color color = const Color(0xFF6FA85C)}) => _at(canvas, c, s, rot, () {
        final p = Path()
          ..moveTo(0, 1)
          ..cubicTo(-0.75, 0.4, -0.55, -0.6, 0, -1)
          ..cubicTo(0.55, -0.6, 0.75, 0.4, 0, 1)
          ..close();
        canvas.drawPath(p, _fill(color));
        canvas.drawLine(const Offset(0, 0.9), const Offset(0, -0.7), _line(Color.lerp(color, Colors.white, 0.45)!, 0.08));
      });

  /// 五瓣的小花
  static void flower(Canvas canvas, Offset c, double s, Color color, {double rot = 0, Color heart = const Color(0xFFF2C14E)}) => _at(canvas, c, s, rot, () {
        final shade = Color.lerp(color, const Color(0xFFB0707A), 0.28)!;
        for (var i = 0; i < 5; i++) {
          final a = -math.pi / 2 + i * math.pi * 2 / 5;
          final o = Offset(0.52 * math.cos(a), 0.52 * math.sin(a));
          canvas.drawCircle(o, 0.4, _fill(color));
          canvas.drawCircle(o, 0.4, _line(shade.withValues(alpha: 0.6), 0.04));
        }
        canvas.drawCircle(Offset.zero, 0.26, _fill(heart));
        canvas.drawCircle(const Offset(-0.06, -0.06), 0.09, _fill(Color.lerp(heart, Colors.white, 0.6)!));
      });

  /// 羽毛
  static void feather(Canvas canvas, Offset c, double s, {double rot = 0, Color color = const Color(0xFFEFF3F5)}) => _at(canvas, c, s, rot, () {
        final tip = Color.lerp(color, const Color(0xFF6F93B0), 0.6)!;
        final vane = Path()
          ..moveTo(0, 0.55)
          ..cubicTo(-0.55, 0.2, -0.5, -0.7, 0, -1)
          ..cubicTo(0.5, -0.7, 0.55, 0.2, 0, 0.55)
          ..close();
        canvas.drawPath(vane, _grad(const Rect.fromLTRB(-0.5, -1, 0.5, 0.55), [tip, color, color]));
        canvas.save();
        canvas.clipPath(vane);
        for (var y = -0.8; y < 0.5; y += 0.17) {
          canvas.drawLine(Offset(0, y + 0.12), Offset(-0.6, y - 0.14), _line(const Color(0x669AB0C0), 0.03));
          canvas.drawLine(Offset(0, y + 0.12), Offset(0.6, y - 0.14), _line(const Color(0x669AB0C0), 0.03));
        }
        canvas.restore();
        canvas.drawLine(const Offset(0, -0.9), const Offset(0, 1), _line(const Color(0xFFB9A98A), 0.06));
      });

  /// 小铃铛：圆的，下面一道开口
  static void bell(Canvas canvas, Offset c, double s, {double rot = 0}) => _at(canvas, c, s, rot, () {
        canvas.drawCircle(const Offset(0, -0.78), 0.17, _line(SancColors.goldDeep, 0.09));
        final box = Rect.fromCircle(center: const Offset(0, 0.1), radius: 0.78);
        canvas.drawCircle(box.center, 0.78, Paint()..shader = const RadialGradient(center: Alignment(-0.4, -0.5), colors: [Color(0xFFFFF6CF), SancColors.gold, Color(0xFF9A6A14)], stops: [0, 0.5, 1]).createShader(box));
        canvas.drawLine(const Offset(-0.76, 0.05), const Offset(0.76, 0.05), _line(const Color(0xFF8A5A14), 0.06));
        canvas.drawLine(const Offset(-0.4, 0.45), const Offset(0.4, 0.45), _line(const Color(0xFF3A2606), 0.1));
        canvas.drawCircle(const Offset(0, 0.45), 0.13, _fill(const Color(0xFF3A2606)));
      });

  /// 毛线球，拖着一截线头
  static void yarn(Canvas canvas, Offset c, double s, Color color, {double rot = 0}) => _at(canvas, c, s, rot, () {
        final dark = Color.lerp(color, const Color(0xFF5A1E38), 0.4)!, light = Color.lerp(color, Colors.white, 0.45)!;
        canvas.drawPath(Path()..moveTo(0.5, 0.6)..cubicTo(0.9, 1.0, 1.2, 0.5, 1.25, 0.95), _line(color, 0.09));
        final box = Rect.fromCircle(center: Offset.zero, radius: 0.82);
        final ball = Path()..addOval(box);
        canvas.drawPath(ball, Paint()..shader = RadialGradient(center: const Alignment(-0.35, -0.4), colors: [light, color, dark]).createShader(box));
        canvas.save();
        canvas.clipPath(ball);
        for (var i = 0; i < 4; i++) {
          canvas.drawArc(Rect.fromCircle(center: Offset(-1.1 + i * 0.1, -0.9), radius: 1.0 + i * 0.3), 0, 1.7, false, _line(dark.withValues(alpha: 0.55), 0.05));
          canvas.drawArc(Rect.fromCircle(center: Offset(1.2, -0.7 + i * 0.1), radius: 0.9 + i * 0.3), 1.6, 1.7, false, _line(light.withValues(alpha: 0.6), 0.05));
        }
        canvas.restore();
      });

  /// 树枝：一根直直的好树枝，带个小杈和一片叶子
  static void stick(Canvas canvas, Offset c, double s, {double rot = 0}) => _at(canvas, c, s, rot, () {
        const bark = Color(0xFF7A5230);
        canvas.drawPath(Path()..moveTo(0.1, 0.0)..quadraticBezierTo(0.3, -0.25, 0.5, -0.38), _line(bark, 0.11));
        final main = Path()
          ..moveTo(-1, 0.12)
          ..quadraticBezierTo(0, -0.1, 1, 0.08);
        canvas.drawPath(main, _line(bark, 0.2));
        canvas.drawPath(main.shift(const Offset(0, -0.04)), _line(const Color(0xFFA9794A), 0.06));
        leaf(canvas, const Offset(0.62, -0.52), 0.2, rot: 0.9);
        canvas.drawCircle(const Offset(-1, 0.12), 0.1, _fill(const Color(0xFFD9B98A)));
      });

  /// 小鱼干：晒得扁扁的一条，眼睛是个叉
  static void driedFish(Canvas canvas, Offset c, double s, {double rot = 0}) => _at(canvas, c, s, rot, () {
        const skin = Color(0xFFD9A85C), dark = Color(0xFF8A5F26);
        final body = Path()
          ..moveTo(-1, 0)
          ..cubicTo(-0.7, -0.42, 0.1, -0.4, 0.55, -0.06)
          ..lineTo(1, -0.4)
          ..lineTo(0.86, 0)
          ..lineTo(1, 0.4)
          ..lineTo(0.55, 0.06)
          ..cubicTo(0.1, 0.4, -0.7, 0.42, -1, 0)
          ..close();
        canvas.drawPath(body, _grad(const Rect.fromLTRB(-1, -0.4, 1, 0.4), const [Color(0xFFEBC27A), skin, Color(0xFFB98440)]));
        canvas.drawPath(body, _line(dark, 0.05));
        for (var x = -0.35; x < 0.5; x += 0.2) {
          canvas.drawLine(Offset(x, -0.2), Offset(x + 0.08, 0.2), _line(dark.withValues(alpha: 0.6), 0.04));
        }
        canvas.drawLine(const Offset(-0.78, -0.12), const Offset(-0.62, 0.02), _line(dark, 0.05));
        canvas.drawLine(const Offset(-0.62, -0.12), const Offset(-0.78, 0.02), _line(dark, 0.05));
      });

  /// 珍珠
  static void pearl(Canvas canvas, Offset c, double s) {
    final box = Rect.fromCircle(center: c, radius: s);
    canvas.drawCircle(c, s, Paint()..shader = const RadialGradient(center: Alignment(-0.35, -0.4), colors: [Colors.white, Color(0xFFF3E6EC), Color(0xFFB7A6C6)], stops: [0, 0.5, 1]).createShader(box));
    canvas.drawCircle(c.translate(-s * 0.32, -s * 0.36), s * 0.2, _fill(Colors.white));
  }

  /// 平安结：红绳编的菱形结，上面一个圈，下面一束穗子
  static void knot(Canvas canvas, Offset c, double s, {double rot = 0}) => _at(canvas, c, s, rot, () {
        const red = SancColors.vermilion, dark = SancColors.vermilionDeep;
        final cord = _line(red, 0.1);
        canvas.drawOval(Rect.fromCenter(center: const Offset(0, -0.78), width: 0.3, height: 0.4), cord);
        for (final sx in const [-1.0, 1.0]) {
          canvas.drawOval(Rect.fromCenter(center: Offset(sx * 0.62, -0.1), width: 0.34, height: 0.3), cord);
        }
        canvas.save();
        canvas.translate(0, -0.1);
        canvas.rotate(math.pi / 4);
        const box = Rect.fromLTRB(-0.36, -0.36, 0.36, 0.36);
        canvas.drawRRect(RRect.fromRectAndRadius(box, const Radius.circular(0.06)), _fill(red));
        for (final t in const [-0.12, 0.12]) {
          canvas.drawLine(Offset(t, -0.36), Offset(t, 0.36), _line(dark, 0.045));
          canvas.drawLine(Offset(-0.36, t), Offset(0.36, t), _line(dark, 0.045));
        }
        canvas.drawRRect(RRect.fromRectAndRadius(box, const Radius.circular(0.06)), _line(SancColors.gold, 0.035));
        canvas.restore();
        // 穗子
        canvas.drawCircle(const Offset(0, 0.5), 0.1, _fill(SancColors.gold));
        for (var i = -2; i <= 2; i++) {
          canvas.drawLine(Offset(i * 0.03, 0.58), Offset(i * 0.085, 1.2), _line(i.isEven ? red : dark, 0.05));
        }
      });
}
