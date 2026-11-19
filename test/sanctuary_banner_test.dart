import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:yuanjing/features/sanctuary/sanctuary_ui.dart';

/// 上面的地名：换了地方才出来，三秒多以后淡掉；走着、做着事（特写）、有字幕时不出来
void main() {
  Widget banner(String place, {bool allowed = true, int replay = 0, int count = 11}) => MaterialApp(
        home: Scaffold(body: Center(child: PlaceBanner(place: place, count: count, allowed: allowed, replay: replay))),
      );

  double opacity(WidgetTester tester) => tester.widget<AnimatedOpacity>(find.byType(AnimatedOpacity)).opacity;

  testWidgets('换了地方出来，三秒后淡掉；同一个地方不再出来', (tester) async {
    await tester.pumpWidget(banner(''));
    expect(opacity(tester), 0);
    await tester.pumpWidget(banner('岛上'));
    await tester.pump(const Duration(milliseconds: 700));
    expect(opacity(tester), 1);
    expect(find.text('此刻寺里有 11 个人'), findsOneWidget);
    expect(find.textContaining('殿里有'), findsNothing);
    await tester.pump(const Duration(seconds: 3));
    expect(opacity(tester), 0, reason: '三秒多以后应该淡掉');
    // 同一个地方（坐下又站起来）：不再出来
    await tester.pumpWidget(banner('岛上', count: 12));
    await tester.pump(const Duration(milliseconds: 300));
    expect(opacity(tester), 0);
    // 换了地方：又出来
    await tester.pumpWidget(banner('大殿里'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(opacity(tester), 1);
    await tester.pump(const Duration(seconds: 4));
    expect(opacity(tester), 0);
  });

  testWidgets('做着事（特写、走着、字幕）不出来，做完也不再冒出来', (tester) async {
    await tester.pumpWidget(banner('许愿树下'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(opacity(tester), 1);
    // 一点「挂红布条」：开始做事，马上收起来
    await tester.pumpWidget(banner('许愿树下', allowed: false));
    await tester.pump(const Duration(milliseconds: 300));
    expect(opacity(tester), 0);
    // 一秒后做完：三秒还没到，也不再出来
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpWidget(banner('许愿树下'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(opacity(tester), 0);
    // 换地方时正忙着：等不忙了、还在三秒里就出来
    await tester.pumpWidget(banner('香炉前', allowed: false));
    await tester.pump(const Duration(milliseconds: 500));
    expect(opacity(tester), 0);
    await tester.pumpWidget(banner('香炉前'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(opacity(tester), 1);
    await tester.pump(const Duration(seconds: 4));
  });

  testWidgets('寺门推开（replay）再挂一次；一个人时不写人数', (tester) async {
    await tester.pumpWidget(banner('岛上', count: 1));
    await tester.pump(const Duration(seconds: 4));
    expect(opacity(tester), 0);
    expect(find.textContaining('个人'), findsNothing);
    await tester.pumpWidget(banner('岛上', count: 1, replay: 1));
    await tester.pump(const Duration(milliseconds: 300));
    expect(opacity(tester), 1);
    await tester.pump(const Duration(seconds: 4));
    expect(opacity(tester), 0);
  });
}
