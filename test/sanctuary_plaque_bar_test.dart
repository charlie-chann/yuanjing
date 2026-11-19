import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:yuanjing/features/sanctuary/sanctuary_ui.dart';

/// 底下那排木牌：绳子还在滑（甩出去、拖过头回弹）的时候点一下，只是让它停住，不算点了手指下面那块
void main() {
  final taps = <String>[];

  // 木牌闲着会一直轻轻晃（pumpAndSettle 等不到头）：关掉动画
  Widget bar() => MaterialApp(
        builder: (context, child) => MediaQuery(data: MediaQuery.of(context).copyWith(disableAnimations: true), child: child!),
        home: Scaffold(
          body: Align(
            alignment: Alignment.bottomCenter,
            child: SizedBox(
              width: 390,
              child: PlaqueBar(actions: [
                for (final l in ['跪拜', '上香', '鞠躬', '合掌', '去许愿树', '去香炉', '出殿', '喂小鸟']) PlaqueAction(l, onTap: () => taps.add(l)),
              ]),
            ),
          ),
        ),
      );

  Offset centerOf(WidgetTester tester, String label) => tester.getCenter(find.text(label));

  // iOS：拖到头会回弹（BouncingScrollPhysics），模拟器里出问题的就是这种
  testWidgets('拖过头、松手回弹的时候点一下：只停住，不按木牌', (tester) async {
    taps.clear();
    await tester.pumpWidget(bar());
    // 往左拖过头（拖到最右边还多拉出去一截），松手：从界外弹回来
    final g = await tester.startGesture(tester.getCenter(find.byType(PlaqueBar)));
    for (var i = 0; i < 20; i++) {
      await g.moveBy(const Offset(-60, 0));
      await tester.pump(const Duration(milliseconds: 16));
    }
    await g.up();
    await tester.pump(const Duration(milliseconds: 16));
    await tester.pump(const Duration(milliseconds: 16));
    final pos = tester.state<ScrollableState>(find.byType(Scrollable)).position;
    expect(pos.isScrollingNotifier.value, isTrue, reason: '应该还在回弹');
    // 这时手指落在一块牌子上
    await tester.tapAt(centerOf(tester, '出殿'));
    await tester.pump(const Duration(milliseconds: 16));
    expect(taps, isEmpty, reason: '回弹时点一下不该按下木牌');
    await tester.pumpAndSettle();
    // 停稳以后照常点
    await tester.tapAt(centerOf(tester, '出殿'));
    await tester.pumpAndSettle();
    expect(taps, ['出殿']);
  }, variant: TargetPlatformVariant.only(TargetPlatform.iOS));

  testWidgets('甩出去还在滑的时候点一下：只停住，不按木牌', (tester) async {
    taps.clear();
    await tester.pumpWidget(bar());
    await tester.fling(find.byType(PlaqueBar), const Offset(-120, 0), 900);
    await tester.pump(const Duration(milliseconds: 30));
    final pos = tester.state<ScrollableState>(find.byType(Scrollable)).position;
    expect(pos.isScrollingNotifier.value, isTrue, reason: '应该还在滑');
    await tester.tapAt(tester.getCenter(find.byType(PlaqueBar)));
    await tester.pump(const Duration(milliseconds: 16));
    expect(taps, isEmpty, reason: '滑的时候点一下不该按下木牌');
    expect(pos.isScrollingNotifier.value, isFalse, reason: '点一下应该让它停住');
    await tester.pumpAndSettle();
    // 停住以后同一个地方再点一下：照常按下
    await tester.tapAt(tester.getCenter(find.byType(PlaqueBar)));
    await tester.pumpAndSettle();
    expect(taps.length, 1);
  }, variant: TargetPlatformVariant.only(TargetPlatform.iOS));

  testWidgets('不动的时候点：照常按下', (tester) async {
    taps.clear();
    await tester.pumpWidget(bar());
    await tester.tap(find.text('上香'));
    await tester.pumpAndSettle();
    expect(taps, ['上香']);
  });
}
