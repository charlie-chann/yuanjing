import 'dart:convert';
import 'dart:io';
import 'dart:ui' show ImageByteFormat, PictureRecorder;

import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:yuanjing/app/skin.dart';
import 'package:yuanjing/features/sanctuary/wish_mask.dart';

/// 许愿布条、木牌上的字：排版（竖排、换列、字号）和写成的灰度图。
/// 写成的图存到 unity/shots/wish/（Unity 的 InteractionTest 有这几张就拿来挂，看挂在树上的效果）。
void main() {
  setUpAll(() async {
    final loader = FontLoader(displayFont)
      ..addFont(File('assets/fonts/SourceHanSerifCN-Medium.otf').readAsBytes().then(ByteData.sublistView))
      ..addFont(File('assets/fonts/SourceHanSerifCN-Bold.otf').readAsBytes().then(ByteData.sublistView));
    await loader.load();
  });

  test('竖排：换行另起一列，空格去掉，标点换成竖写的，最多 40 个字', () {
    expect(WishMask.columns('家人 平安\n万事顺意'), [
      ['家', '人', '平', '安'],
      ['万', '事', '顺', '意'],
    ]);
    expect(WishMask.columns('好，好。').first, ['好', '︐', '好', '︒']);
    expect(WishMask.columns('愿' * 60).first.length, WishMask.maxChars);
  });

  test('字数多就分几列、字小一些；都在写字的范围里', () {
    final size = WishMask.ribbonSize;
    final box = WishMask.ribbonBox;
    final few = WishMask.layout('平安', size, box);
    final many = WishMask.layout('愿' * 40, size, box);
    expect(few.cell, greaterThan(many.cell * 2));
    final xs = many.glyphs.map((g) => g.$2.dx).toSet();
    expect(xs.length, greaterThanOrEqualTo(3));
    for (final g in many.glyphs) {
      expect(g.$2.dx - many.cell / 2, greaterThanOrEqualTo(box.left * size.width - 0.5));
      expect(g.$2.dx + many.cell / 2, lessThanOrEqualTo(box.right * size.width + 0.5));
      expect(g.$2.dy + many.cell / 2, lessThanOrEqualTo(box.bottom * size.height + 0.5));
    }
    // 从右往左：第一个字在最右边一列
    expect(many.glyphs.first.$2.dx, xs.reduce((a, b) => a > b ? a : b));
  });

  test('换行太多：布条最多 3 段、木牌最多 5 段，多的并到最后一段；写的时候就限住换行', () {
    final oneEach = List.filled(40, '愿').join('\n');
    expect(WishMask.columns(oneEach, maxSegs: 3).length, 3);
    expect(WishMask.columns(oneEach, maxSegs: 5).length, 5);
    expect(WishMask.columns(oneEach, maxSegs: 3).expand((c) => c).length, 40);
    // 一行一个字写满 40 个：字还是看得清（以前是 40 列、每个字 2 个像素）
    final lay = WishMask.layout(oneEach, WishMask.ribbonSize, WishMask.ribbonBox, maxSegs: WishMask.maxSegments(plaque: false));
    expect(lay.cell, greaterThan(9));
    final f = WishMask.lineLimit(plaque: false);
    TextEditingValue v(String t) => TextEditingValue(text: t);
    expect(f.formatEditUpdate(v('a\nb'), v('a\nb\nc')).text, 'a\nb\nc');
    expect(f.formatEditUpdate(v('a\nb\nc'), v('a\nb\nc\n')).text, 'a\nb\nc');
    expect(WishMask.lineLimit(plaque: true).formatEditUpdate(v('a\nb\nc'), v('a\nb\nc\nd')).text, 'a\nb\nc\nd');
  });

  test('避头：逗号、句号这些标点不写在一列的最上面（挪到上一列末尾）', () {
    const noHead = WishMask.noHead;
    for (final (text, plaque) in [
      ('希望今年考研顺利上岸，爸妈的腰不再疼，小橘猫健健康康，也希望我能对自己温柔一点', false),
      ('愿外婆身体健康，\n我们明年春天一起去看海。', true),
      ('一二三，四五六，七八九，十一二。三四五！六七八？', false),
    ]) {
      final size = plaque ? WishMask.plaqueSize : WishMask.ribbonSize;
      final box = plaque ? WishMask.plaqueBox : WishMask.ribbonBox;
      final lay = WishMask.layout(text, size, box, maxSegs: WishMask.maxSegments(plaque: plaque));
      final top = lay.glyphs.map((g) => g.$2.dy).reduce((a, b) => a < b ? a : b);
      for (final g in lay.glyphs) {
        if ((g.$2.dy - top).abs() < 0.01) expect(noHead.contains(g.$1), isFalse, reason: '「${g.$1}」写在了一列最上面：$text');
        // 挪过去的标点也还在写字的范围里
        expect(g.$2.dy + lay.cell / 2, lessThanOrEqualTo(box.bottom * size.height + 0.5));
      }
    }
  });

  test('标点换成竖排字形：括号、引号、书名号、破折号、省略号、波浪号', () {
    expect(WishMask.columns('【好】“愿”《书》（安）——…～！？：；').first,
        ['︻', '好', '︼', '﹁', '愿', '﹂', '︽', '书', '︾', '︵', '安', '︶', '︱', '︱', '︙', '︴', '︕', '︖', '︓', '︔']);
  });

  test('避尾：开括号、开引号不写在一列的最下面（挪到下一列打头）', () {
    for (final text in ['一二三四「五六七八」九十一二三四', '一二三（四五）六七八九《十一》二三四五六七', '希望今年考研顺利上岸，「爸妈的腰不再疼」，小橘猫健健康康']) {
      for (final plaque in [false, true]) {
        final size = plaque ? WishMask.plaqueSize : WishMask.ribbonSize;
        final box = plaque ? WishMask.plaqueBox : WishMask.ribbonBox;
        final lay = WishMask.layout(text, size, box, maxSegs: WishMask.maxSegments(plaque: plaque));
        // 按列分组（同一个 x），每列最下面那个字
        final byCol = <double, List<(String, Offset)>>{};
        for (final g in lay.glyphs) {
          byCol.putIfAbsent(g.$2.dx.roundToDouble(), () => []).add(g);
        }
        final last = lay.glyphs.last;
        for (final col in byCol.values) {
          col.sort((a, b) => a.$2.dy.compareTo(b.$2.dy));
          if (identical(col.last, last)) continue;
          expect(WishMask.noTail.contains(col.last.$1), isFalse, reason: '「${col.last.$1}」写在了一列最下面：$text');
          expect(WishMask.noHead.contains(col.first.$1), isFalse, reason: '「${col.first.$1}」写在了一列最上面：$text');
        }
      }
    }
  });

  testWidgets('逗号、句号、顿号在字格的右上角；叹号、问号直立居中', (tester) async {
    await tester.runAsync(() async {
      await WishMask.prepare();
      // 字少、字大一些：一列七八个字，量得准
      const text = '康，安。乐、喜！好？';
      const size = Size(256, 1024);
      const box = Rect.fromLTRB(0.17, 0.07, 0.83, 0.88);
      final lay = WishMask.layout(text, size, box);
      final rec = PictureRecorder();
      final canvas = Canvas(rec);
      canvas.drawRect(Offset.zero & size, Paint()..color = const Color(0xFFFFFFFF));
      // 画法同 WishMask.paint（布条的写字范围），只是图大一倍
      WishMask.paintBox(canvas, size, text, box);
      final img = await rec.endRecording().toImage(size.width.toInt(), size.height.toInt());
      final px = (await img.toByteData(format: ImageByteFormat.rawRgba))!;
      // 一个字格里墨的重心（相对字格中心，以字格为 1；下为正）
      Offset centroid(Offset at) {
        final c = lay.cell;
        double sx = 0, sy = 0, n = 0;
        for (var y = (at.dy - c / 2).floor(); y < (at.dy + c / 2).ceil(); y++) {
          for (var x = (at.dx - c / 2).floor(); x < (at.dx + c / 2).ceil(); x++) {
            if (px.getUint8((y * size.width.toInt() + x) * 4) > 90) continue;
            sx += x;
            sy += y;
            n++;
          }
        }
        expect(n, greaterThan(0));
        return Offset((sx / n - at.dx) / c, (sy / n - at.dy) / c);
      }
      final han = centroid(lay.glyphs.first.$2);
      for (final (ch, at) in lay.glyphs) {
        final m = centroid(at) - Offset(0, han.dy);
        if ('︐︒︑'.contains(ch)) {
          expect(m.dx, greaterThan(0.12), reason: '「$ch」应该在字格右半边：$m');
          expect(m.dy, lessThan(-0.12), reason: '「$ch」应该在字格上半边：$m');
        }
        if ('︕︖'.contains(ch)) expect(m.dx.abs(), lessThan(0.06), reason: '「$ch」应该左右居中：$m');
      }
    });
  });

  testWidgets('写成灰度图（PNG），存一份给 Unity 的测试用', (tester) async {
    await tester.runAsync(() async {
      Directory('unity/shots/wish').createSync(recursive: true);
      for (final (name, text, plaque) in [
        // 模拟器里看到的那条：「康，」的逗号要在右上角
        ('mask_ribbon', '愿家人平安健康，万事顺遂！', false),
        ('mask_plaque', '愿外婆身体健康，\n我们明年春天一起去看海。', true),
        ('mask_ribbon_long', '希望今年考研顺利上岸，爸妈的腰不再疼，小橘猫健健康康，也希望我能对自己温柔一点', false),
        ('mask_ribbon_short', '平安', false),
        ('mask_plaque_punct', '愿《小王子》里的那朵玫瑰——\n永远被好好照顾……「好吗？」', true),
      ]) {
        final b64 = await WishMask.render(text, plaque: plaque);
        expect(b64, isNotNull);
        final bytes = base64Decode(b64!);
        // 别太大：跟着 JSON 一起发给 Unity
        expect(bytes.length, lessThan(60000));
        File('unity/shots/wish/$name.png').writeAsBytesSync(bytes);
        File('unity/shots/wish/$name.txt').writeAsStringSync(text);
      }
    });
  });

  testWidgets('写愿望时旁边的小预览', (tester) async {
    // 竖排标点先量好（应用里进殿时就量）
    await tester.runAsync(WishMask.prepare);
    final key = GlobalKey();
    await tester.pumpWidget(Directionality(
      textDirection: TextDirection.ltr,
      child: Center(
        child: RepaintBoundary(
          key: key,
          child: Container(
            color: const Color(0xFF1A1512),
            padding: const EdgeInsets.all(8),
            child: const Row(mainAxisSize: MainAxisSize.min, children: [
              WishClothPreview(text: '愿家人平安健康，万事顺遂！', plaque: false, height: 128),
              SizedBox(width: 10),
              WishClothPreview(text: '愿外婆身体健康，我们明年春天一起去看海。', plaque: true, height: 92),
              SizedBox(width: 10),
              WishClothPreview(text: '愿《小王子》里的那朵玫瑰——\n永远被好好照顾……「好吗？」', plaque: true, height: 92),
            ]),
          ),
        ),
      ),
    ));
    await tester.runAsync(() async {
      final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
      final img = await boundary.toImage(pixelRatio: 3);
      final bytes = await img.toByteData(format: ImageByteFormat.png);
      File('unity/shots/wish/preview.png').writeAsBytesSync(bytes!.buffer.asUint8List());
    });
  });
}
