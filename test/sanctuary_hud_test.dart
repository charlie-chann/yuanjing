import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:yuanjing/features/sanctuary/sanctuary_hud.dart';

void main() {
  Widget host(Widget child) => MaterialApp(home: Scaffold(backgroundColor: Colors.black, body: Center(child: child)));

  testWidgets('靠近互动列表：有几件事就列几条，点哪条做哪件', (tester) async {
    final done = <String>[];
    await tester.pumpWidget(host(PromptList(prompts: [
      HudPrompt('抚摸橘子', 'paw', () => done.add('pet')),
      HudPrompt('喂食橘子', 'food', () => done.add('feed')),
      HudPrompt('钓鱼', 'fish', () => done.add('fish')),
    ])));
    await tester.pumpAndSettle();
    expect(find.text('抚摸橘子'), findsOneWidget);
    expect(find.text('钓鱼'), findsOneWidget);
    await tester.tap(find.text('喂食橘子'));
    await tester.tap(find.text('钓鱼'));
    expect(done, ['feed', 'fish']);
  });

  testWidgets('走开了列表清空', (tester) async {
    await tester.pumpWidget(host(PromptList(prompts: [HudPrompt('敲钟', 'bell', () {})])));
    await tester.pumpAndSettle();
    await tester.pumpWidget(host(const PromptList(prompts: [])));
    await tester.pumpAndSettle();
    expect(find.text('敲钟'), findsNothing);
  });

  testWidgets('提竿键：按下那一刻就算（不等松手）', (tester) async {
    var n = 0;
    await tester.pumpWidget(host(ReelButton(biting: true, window: const Duration(milliseconds: 1800), onTap: () => n++)));
    await tester.pump(const Duration(milliseconds: 100));
    final g = await tester.startGesture(tester.getCenter(find.text('提竿')));
    expect(n, 1);
    await g.up();
    await tester.pump(const Duration(seconds: 2));
  });

  testWidgets('每个小图都画得出来', (tester) async {
    const glyphs = ['paw', 'food', 'bird', 'bell', 'fish', 'sit', 'kneel', 'incense', 'ribbon', 'plaque', 'wish', 'stand', 'calm', 'bag'];
    await tester.pumpWidget(host(Wrap(children: [for (final g in glyphs) GlyphButton(g, label: g)])));
    expect(tester.takeException(), isNull);
  });
}
