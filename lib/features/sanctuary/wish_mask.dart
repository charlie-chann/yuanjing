import 'dart:convert';
import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../app/skin.dart';

/// 许愿树上的红布条、木牌上写的字：竖排、从右往左一列列写，按字数自动挑字号，用应用里的思源宋体（加粗、略带墨晕，像毛笔写的）。
///
/// 写好的字画成一张灰度图（白是布、黑是墨），PNG 转 base64 跟着 offer 指令发给 Unity，
/// Unity 把它叠到布纹、木纹上（unity/Sanctuary/Assets/Scripts/World/WishCloth.cs，图的大小两边是同一组数）。
/// 别人挂的也一样：服务器给字，这里写成图再发过去（按编号缓存）。
abstract final class WishMask {
  /// 图的大小（像素）：布条整个正面、木牌整个正面
  static const ribbonSize = Size(128, 512);
  static const plaqueSize = Size(256, 320);

  /// 写字的范围（占整张图的比例，左上角是原点）：布条避开上面系结的一截、两边金线、下面的毛边；木牌避开尖顶、朱红细框和左下角的小印
  static const ribbonBox = Rect.fromLTRB(0.17, 0.07, 0.83, 0.88);
  static const plaqueBox = Rect.fromLTRB(0.14, 0.25, 0.86, 0.80);

  /// 最多写几个字（布条 0.14 米宽，再多就看不清了）
  static const maxChars = 40;

  /// 最多分几段（一行一段，每段另起一列）：布条 3 段、木牌 5 段。再多的行并到最后一段里接着写（不然一行一个字就是几十列，字小得看不清）
  static int maxSegments({required bool plaque}) => plaque ? 5 : 3;

  /// 写的时候就限住换行：布条最多换 2 次行、木牌 4 次
  static TextInputFormatter lineLimit({required bool plaque}) {
    final most = maxSegments(plaque: plaque) - 1;
    return TextInputFormatter.withFunction((old, now) => '\n'.allMatches(now.text).length > most ? old : now);
  }

  /// 竖排时不能写在一列最上面的标点（逗号、句号、顿号、冒号、分号、叹号、问号、各种右括号、右书名号、右引号）：避头，挪到上一列的末尾
  static const noHead = {'︐', '︒', '︑', '︓', '︔', '︕', '︖', '︶', '︸', '︺', '︼', '︾', '﹀', '﹂', '﹄', '︘', '﹈'};

  /// 竖排时不能写在一列最下面的标点（各种左括号、左书名号、左引号）：避尾，挪到下一列打头
  static const noTail = {'︵', '︷', '︹', '︻', '︽', '︿', '﹁', '﹃', '︗', '﹇'};

  /// 竖排时换成竖写的标点（Unicode 的竖排字形 U+FE10–FE19、U+FE30–FE4F，思源宋体 YuanjingSerif 里全都有）。
  /// 引号按大陆竖排的习惯写成直角引号
  static const _vertical = {
    '，': '︐', ',': '︐', '﹐': '︐', '。': '︒', '．': '︒', '｡': '︒', '、': '︑', '﹑': '︑',
    '：': '︓', ':': '︓', '；': '︔', ';': '︔', '！': '︕', '!': '︕', '？': '︖', '?': '︖',
    '（': '︵', '(': '︵', '）': '︶', ')': '︶', '｛': '︷', '{': '︷', '｝': '︸', '}': '︸', '〔': '︹', '〕': '︺',
    '【': '︻', '】': '︼', '《': '︽', '》': '︾', '〈': '︿', '〉': '﹀', '〖': '︗', '〗': '︘', '［': '﹇', '[': '﹇', '］': '﹈', ']': '﹈',
    '「': '﹁', '」': '﹂', '『': '﹃', '』': '﹄', '“': '﹁', '”': '﹂', '‘': '﹃', '’': '﹄',
    '—': '︱', '―': '︱', '-': '︱', '–': '︲', '～': '︴', '~': '︴', '〜': '︴', '…': '︙', '‥': '︰',
  };

  /// 竖排标点在一个字格里摆在哪（不管字体自己把它画在字身框的哪儿）：
  /// 逗号、句号、顿号在右上角那一格（大陆竖排的规矩）；叹号、问号、冒号、分号、破折号、省略号、波浪号直立、居中。
  /// 括号、引号、书名号用字体自己的竖排字形（开的那半贴着下面的字、合的那半贴着上面的字，本来就是按竖排画的）。
  /// 为什么要量：模拟器上同一个字体、同一个竖排逗号（U+FE10）画出来在字格正中偏左，在 flutter test 里却在右上角，
  /// 所以不信字形自己的位置，量出墨在哪，再挪到该在的地方
  static const _corner = {'︐', '︒', '︑'};
  static const _centred = {'︕', '︖', '︓', '︔', '︱', '︲', '︙', '︴', '︰'};

  /// 量好的墨的范围（以字号为 1、画字时 TextPainter 那个框的中心为原点；下为正）
  static final _ink = <String, Rect>{};

  /// 一个字的字身框（汉字的墨大致占满它）在 TextPainter 框里的中心：思源宋体行高 1.0 时汉字比框的中心高约 0.09 个字号
  static Offset _emCentre = const Offset(0, -0.09);

  /// 先把竖排标点的墨量一遍（写成图之前、打开写愿望的弹层之前调一次；量过就不再量）
  static Future<void> prepare() async {
    if (_ink.isNotEmpty) return;
    final found = <String, Rect>{};
    for (final ch in ['康', ..._corner, ..._centred]) {
      final r = await _measure(ch);
      if (r != null) found[ch] = r;
    }
    final han = found.remove('康');
    if (han != null) _emCentre = Offset(0, han.center.dy);
    _ink.addAll(found);
  }

  static Future<Rect?> _measure(String ch) async {
    const fs = 96.0, n = 192;
    final rec = ui.PictureRecorder();
    final c = Canvas(rec);
    c.drawRect(const Rect.fromLTWH(0, 0, 192, 192), Paint()..color = Colors.white);
    final tp = TextPainter(
      text: TextSpan(text: ch, style: const TextStyle(fontFamily: displayFont, fontWeight: FontWeight.w700, fontSize: fs, height: 1.0, color: Colors.black)),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(c, Offset(n / 2 - tp.width / 2, n / 2 - tp.height / 2));
    final img = await rec.endRecording().toImage(n, n);
    final bytes = await img.toByteData(format: ui.ImageByteFormat.rawRgba);
    img.dispose();
    if (bytes == null) return null;
    var x0 = n, x1 = -1, y0 = n, y1 = -1;
    for (var y = 0; y < n; y++) {
      for (var x = 0; x < n; x++) {
        if (bytes.getUint8((y * n + x) * 4) >= 128) continue;
        if (x < x0) x0 = x;
        if (x > x1) x1 = x;
        if (y < y0) y0 = y;
        if (y > y1) y1 = y;
      }
    }
    if (x1 < 0) return null;
    return Rect.fromLTRB((x0 - n / 2) / fs, (y0 - n / 2) / fs, (x1 + 1 - n / 2) / fs, (y1 + 1 - n / 2) / fs);
  }

  /// 这个字（竖排标点）要挪多少（以字号为 1）：把量出来的墨挪到它在字格里该在的地方。没量过、不是要挪的标点就不挪
  static Offset shiftOf(String ch) {
    final ink = _ink[ch];
    if (ink == null) return Offset.zero;
    if (_corner.contains(ch)) {
      // 右上角：墨的中心放在字身框右上那一格的中心偏外一点（和字形本来的设计差不多）
      return _emCentre + const Offset(0.28, -0.25) - ink.center;
    }
    return _emCentre - ink.center;
  }

  /// 一段段的字：换行另起一段（一段从新的一列写起），空格去掉，最多 maxChars 个；段数超过 maxSegs 的，后面几行并到最后一段里
  static List<List<String>> columns(String text, {int maxSegs = 1 << 30}) {
    final out = <List<String>>[];
    var n = 0;
    for (final line in text.trim().split('\n')) {
      final col = out.length >= maxSegs ? out.removeLast() : <String>[];
      for (final ch in line.characters) {
        if (ch.trim().isEmpty) continue;
        if (n >= maxChars) break;
        // 省略号竖排占一格就够了
        if (ch == '…' && col.isNotEmpty && col.last == '︙') continue;
        col.add(_vertical[ch] ?? ch);
        n++;
      }
      if (col.isNotEmpty) out.add(col);
    }
    return out;
  }

  /// 一段按每列 rows 个字切成几列：一列最下面是开括号、开引号的话，它挪到下一列打头（避尾，这一列少一个字）；
  /// 切出来的一列要是以不能打头的标点开头，就把它挪到上一列末尾（避头，那一列多一个字）
  static List<List<String>> _split(List<String> seg, int rows) {
    final out = <List<String>>[];
    var i = 0;
    while (i < seg.length) {
      var n = math.min(rows, seg.length - i);
      while (n > 1 && i + n < seg.length && noTail.contains(seg[i + n - 1])) {
        n--;
      }
      var col = seg.sublist(i, i + n);
      i += n;
      while (out.isNotEmpty && col.isNotEmpty && noHead.contains(col.first)) {
        out.last.add(col.first);
        col = col.sublist(1);
      }
      if (col.isNotEmpty) out.add(col);
    }
    return out;
  }

  /// 排版：每段（一行）从上往下写，写满一列换下一列；挑能让字最大的「每列几个字」（算上避头挪过去的标点）
  static ({double cell, List<(String, Offset)> glyphs}) layout(String text, Size size, Rect box, {int maxSegs = 1 << 30}) {
    final segs = columns(text, maxSegs: maxSegs);
    final w = box.width * size.width, h = box.height * size.height;
    if (segs.isEmpty) return (cell: 0, glyphs: const []);
    final total = segs.fold<int>(0, (a, s) => a + s.length);
    var bestCell = 0.0;
    var cols = <List<String>>[];
    for (var rows = 1; rows <= total; rows++) {
      final split = [for (final s in segs) ..._split(s, rows)];
      final longest = split.fold<int>(0, (a, c) => math.max(a, c.length));
      final cell = math.min(w / split.length, h / longest);
      if (cell > bestCell + 0.01) {
        bestCell = cell;
        cols = split;
      }
    }
    // 一两个字时别大到顶满整幅
    final cell = math.min(bestCell, w * 0.92);
    final usedRows = cols.fold<int>(0, (a, c) => math.max(a, c.length));
    final left = box.left * size.width, top = box.top * size.height;
    // 整块居中；竖着偏上一点（字少时不沉在底下）
    final x0 = left + (w + cols.length * cell) / 2;
    final y0 = top + (h - usedRows * cell) * 0.32;
    final glyphs = <(String, Offset)>[];
    for (var c = 0; c < cols.length; c++) {
      for (var r = 0; r < cols[c].length; r++) {
        glyphs.add((cols[c][r], Offset(x0 - (c + 0.5) * cell, y0 + (r + 0.5) * cell)));
      }
    }
    return (cell: cell, glyphs: glyphs);
  }

  /// 把字写到画布上（size 是整张图的大小）。ink 是墨色；预览的时候也用它
  static void paint(Canvas canvas, Size size, String text, {required bool plaque, Color ink = Colors.black}) =>
      paintBox(canvas, size, text, plaque ? plaqueBox : ribbonBox, maxSegs: maxSegments(plaque: plaque), ink: ink);

  /// 在 box 这个范围里写（paint 用布条、木牌各自的范围；测试用它在大一点的图上量标点的位置）
  static void paintBox(Canvas canvas, Size size, String text, Rect box, {int maxSegs = 1 << 30, Color ink = Colors.black}) {
    final lay = layout(text, size, box, maxSegs: maxSegs);
    if (lay.glyphs.isEmpty) return;
    final fs = lay.cell * 0.9;
    final rnd = math.Random(text.hashCode);
    for (final (ch, at) in lay.glyphs) {
      // 手写的样子：每个字略歪一点、略错开一点
      final rot = (rnd.nextDouble() - 0.5) * 0.07;
      final jitter = Offset((rnd.nextDouble() - 0.5) * 0.05 * fs, (rnd.nextDouble() - 0.5) * 0.04 * fs);
      TextPainter tp(Paint p) => TextPainter(
            text: TextSpan(text: ch, style: TextStyle(fontFamily: displayFont, fontWeight: FontWeight.w700, fontSize: fs, height: 1.0, foreground: p)),
            textDirection: TextDirection.ltr,
          )..layout();
      // 先铺一层略晕开的墨，再描一圈让笔画粗一点（像毛笔），最后是实的字
      final bleed = tp(Paint()
        ..color = ink.withValues(alpha: 0.55)
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, math.max(0.6, fs * 0.03)));
      final stroke = tp(Paint()
        ..color = ink
        ..style = PaintingStyle.stroke
        ..strokeWidth = math.max(0.6, fs * 0.035)
        ..strokeJoin = StrokeJoin.round);
      final fill = tp(Paint()..color = ink);
      canvas.save();
      canvas.translate(at.dx + jitter.dx, at.dy + jitter.dy);
      canvas.rotate(rot);
      // 竖排标点：逗号句号顿号挪到右上角，叹号问号这些居中（见 shiftOf）
      final o = Offset(-fill.width / 2, -fill.height / 2) + shiftOf(ch) * fs;
      bleed.paint(canvas, o);
      stroke.paint(canvas, o);
      fill.paint(canvas, o);
      canvas.restore();
    }
  }

  /// 写成灰度图，返回 PNG 的 base64（白底黑字，大小是 ribbonSize / plaqueSize）
  static Future<String?> render(String text, {required bool plaque}) async {
    final size = plaque ? plaqueSize : ribbonSize;
    await prepare();
    final rec = ui.PictureRecorder();
    final canvas = Canvas(rec, Offset.zero & size);
    canvas.drawRect(Offset.zero & size, Paint()..color = Colors.white);
    paint(canvas, size, text, plaque: plaque);
    final img = await rec.endRecording().toImage(size.width.toInt(), size.height.toInt());
    final bytes = await img.toByteData(format: ui.ImageByteFormat.png);
    img.dispose();
    if (bytes == null) return null;
    return base64Encode(bytes.buffer.asUint8List());
  }
}

/// 写愿望时的小预览：一条红布（或一块木牌），字竖着写在上面，和挂到树上的样子一样
class WishClothPreview extends StatelessWidget {
  final String text;
  final bool plaque;
  final double height;
  const WishClothPreview({super.key, required this.text, required this.plaque, this.height = 150});

  @override
  Widget build(BuildContext context) {
    final s = plaque ? WishMask.plaqueSize : WishMask.ribbonSize;
    return SizedBox(
      height: height,
      width: height * s.width / s.height,
      child: CustomPaint(painter: _PreviewPainter(text, plaque)),
    );
  }
}

class _PreviewPainter extends CustomPainter {
  final String text;
  final bool plaque;
  _PreviewPainter(this.text, this.plaque);

  @override
  void paint(Canvas canvas, Size size) {
    final full = plaque ? WishMask.plaqueSize : WishMask.ribbonSize;
    canvas.save();
    canvas.scale(size.width / full.width, size.height / full.height);
    final r = Offset.zero & full;
    if (plaque) {
      // 木牌：五边形，尖顶，朱红细框
      final path = Path()
        ..moveTo(0, full.height)
        ..lineTo(full.width, full.height)
        ..lineTo(full.width, full.height * 0.231)
        ..lineTo(full.width / 2, 0)
        ..lineTo(0, full.height * 0.231)
        ..close();
      canvas.drawPath(path, Paint()..color = const Color(0xFFDDB57E));
      canvas.drawPath(path, Paint()
        ..color = const Color(0xFF8A5A2B)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 5);
      canvas.drawCircle(Offset(full.width / 2, full.height * 0.085), 5, Paint()..color = const Color(0xFF3A2414));
    } else {
      // 布条：红布，两边金线，下面一排线头
      canvas.drawRect(Rect.fromLTRB(0, 0, full.width, full.height * 0.95), Paint()..color = const Color(0xFFC4302A));
      final gold = Paint()
        ..color = const Color(0xFFE8C063)
        ..strokeWidth = 3;
      canvas.drawLine(Offset(full.width * 0.052, 0), Offset(full.width * 0.052, full.height * 0.94), gold);
      canvas.drawLine(Offset(full.width * 0.948, 0), Offset(full.width * 0.948, full.height * 0.94), gold);
      final thread = Paint()
        ..color = const Color(0xFFC4302A)
        ..strokeWidth = 4;
      for (var i = 0; i < 12; i++) {
        final x = (i + 0.5) / 12 * full.width;
        canvas.drawLine(Offset(x, full.height * 0.94), Offset(x + (i.isEven ? 2 : -2), full.height * (0.975 + (i % 3) * 0.008)), thread);
      }
    }
    canvas.clipRect(r);
    WishMask.paint(canvas, full, text, plaque: plaque, ink: const Color(0xFF1C0F0B));
    canvas.restore();
  }

  @override
  bool shouldRepaint(_PreviewPainter old) => old.text != text || old.plaque != plaque;
}
