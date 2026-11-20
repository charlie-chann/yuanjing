import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:yuanjing/app/store.dart';
import 'package:yuanjing/features/sanctuary/bag_sheet.dart';
import 'package:yuanjing/features/sanctuary/islet_art.dart';
import 'package:yuanjing/features/shop/frame_art.dart';

/// 背包弹层、钓到鱼的展示卡、图鉴、小动物册。数据直接塞进 store（没连服务器：store.online 是 false，弹层不会去取）
void main() {
  Map<String, dynamic> item(String id, String kind, String name, int count, {String rarity = 'common', int sell = 1, int feed = 0}) =>
      {'id': id, 'kind': kind, 'name': name, 'about': '$name的描述', 'rarity': rarity, 'count': count, 'sell': sell, 'feed': feed};

  setUp(() {
    store.online = false;
    store.coins = 100;
    store.bag
      ..clear()
      ..addAll([
        item('crucian', 'fish', '鲫鱼', 3, feed: 2),
        item('mandarin', 'fish', '鳜鱼', 1, rarity: 'rare', sell: 8, feed: 5),
        item('weed', 'fish', '一团水草', 2, rarity: 'junk', sell: 0),
        item('food_bone', 'food', '肉骨头', 4, sell: 2, feed: 3),
        item('shell', 'gift', '贝壳', 5, sell: 2),
        item('pearl', 'gift', '珍珠', 1, rarity: 'rare', sell: 15),
      ]);
    store.petBookCache = {
      'names': {'food_bone': '肉骨头', 'bass': '鲈鱼', 'food_kibble': '小饼干'},
      'pets': [
        {
          'id': 'teddy', 'name': '栗子', 'kind': 'dog', 'affinity': 32, 'level': 3, 'level_name': '最好的朋友', 'next': 60,
          'favorites': ['food_bone', 'bass', 'food_kibble'], 'favorites_known': ['food_bone'], 'frame': 'frame_teddy', 'next_milestone': 50,
          'milestones': [
            {'at': 5, 'kind': 'coins', 'what': '一包金币（10 个）', 'done': true},
            {'at': 15, 'kind': 'items', 'what': '骨头 ×2', 'done': true},
            {'at': 30, 'kind': 'coins', 'what': '一包金币（30 个）', 'done': true},
            {'at': 50, 'kind': 'frame', 'what': '栗子的爪印头像框', 'done': false},
            {'at': 80, 'kind': 'items', 'what': '树枝 ×2、松果 ×2', 'done': false},
          ],
          'daily': [
            {'id': 'bone', 'name': '骨头', 'rarity': 'common', 'seen': true},
            {'id': 'knot', 'name': '平安结', 'rarity': 'rare', 'seen': false},
          ],
        },
        {
          'id': 'momo', 'name': '墨墨', 'kind': 'cat', 'affinity': 0, 'level': 0, 'level_name': '陌生', 'next': 3,
          'favorites': ['moon', 'loach', 'food_dried_fish'], 'favorites_known': <String>[], 'frame': 'frame_momo', 'next_milestone': 5,
          'milestones': [
            {'at': 5, 'kind': 'coins', 'what': '一包金币（10 个）', 'done': false},
          ],
          'daily': [
            {'id': 'pearl', 'name': '珍珠', 'rarity': 'rare', 'seen': false},
          ],
        },
      ],
    };
    store.fishBookCache = {
      'left': 27, 'daily': 30, 'kinds': 1, 'total': 2,
      'fish': [
        {'id': 'crucian', 'name': '鲫鱼', 'rarity': 'common', 'spots': ['pond'], 'caught': true, 'count': 3, 'best_cm': 18.4},
        {'id': 'moon', 'name': '月光鱼', 'rarity': 'legend', 'spots': ['sea'], 'caught': false, 'count': 0, 'best_cm': null},
      ],
    };
  });

  /// 一个手机大小的屏，上面一个按钮：点了就打开弹层，把返回值记到 [result] 里
  Object? result = 'unset';
  Future<void> open(WidgetTester tester, Future<Object?> Function(BuildContext) show) async {
    tester.view.physicalSize = const Size(402, 874);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    result = 'unset';
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: Builder(builder: (context) => Center(child: TextButton(onPressed: () async => result = await show(context), child: const Text('打开'))))),
    ));
    await tester.tap(find.text('打开'));
    await tester.pumpAndSettle();
  }

  testWidgets('挑一样喂它：只有能喂的，最爱有印；点东西返回编号，点普通口粮返回空字符串，关掉返回 null', (tester) async {
    Future<Object?> show(BuildContext c) => showBagSheet(c, feedTo: 'teddy', feedToName: '栗子', feedCost: 2);
    await open(tester, show);
    expect(find.text('挑一样喂栗子'), findsOneWidget);
    expect(find.text('一把普通口粮'), findsOneWidget);
    expect(find.text('花 2 金币'), findsOneWidget);
    // 水草和收藏品不能喂，不出现
    expect(find.text('鲫鱼'), findsOneWidget);
    expect(find.text('鳜鱼'), findsOneWidget);
    expect(find.text('一团水草'), findsNothing);
    expect(find.text('贝壳'), findsNothing);
    // 已经喂出来的最爱（肉骨头）有「爱」字印，而且排在别的前面；别的显示涨多少
    expect(find.text('爱'), findsOneWidget);
    expect(tester.getTopLeft(find.text('肉骨头')).dx, lessThan(tester.getTopLeft(find.text('鲫鱼')).dx));
    expect(find.text('+5'), findsOneWidget);
    await tester.tap(find.text('肉骨头'));
    await tester.pumpAndSettle();
    expect(result, 'food_bone');

    await open(tester, show);
    await tester.tap(find.text('一把普通口粮'));
    await tester.pumpAndSettle();
    expect(result, '');

    await open(tester, show);
    await tester.tapAt(const Offset(200, 40)); // 点弹层外面
    await tester.pumpAndSettle();
    expect(result, isNull);
  });

  testWidgets('普通背包：三栏各放各的，点一格看描述和卖价，能调数量', (tester) async {
    await open(tester, (c) => showBagSheet(c));
    expect(find.text('背包'), findsOneWidget);
    expect(find.text('金币 100'), findsOneWidget);
    // 栏目上写着各有几个
    expect(find.text('鱼 6'), findsOneWidget);
    expect(find.text('食材 4'), findsOneWidget);
    expect(find.text('礼物 6'), findsOneWidget);
    expect(find.text('一团水草'), findsOneWidget);
    expect(find.text('贝壳'), findsNothing);
    expect(find.byType(ItemArt), findsNWidgets(3));

    await tester.tap(find.text('鳜鱼'));
    await tester.pumpAndSettle();
    expect(find.text('鳜鱼的描述'), findsOneWidget);
    expect(find.text('稀有'), findsOneWidget);
    expect(find.textContaining('亲密度 +5'), findsOneWidget);
    expect(find.text('卖出 1 个 · 得 8 金币'), findsOneWidget);

    await tester.tap(find.text('鲫鱼'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('+'));
    await tester.pumpAndSettle();
    expect(find.text('卖出 2 个 · 得 2 金币'), findsOneWidget);
    await tester.tap(find.text('全部'));
    await tester.pumpAndSettle();
    expect(find.text('卖出 3 个 · 得 3 金币'), findsOneWidget);
    // 水草卖不出钱，只能扔
    await tester.tap(find.text('一团水草'));
    await tester.pumpAndSettle();
    expect(find.text('扔掉 1 个'), findsOneWidget);

    await tester.tap(find.text('礼物 6'));
    await tester.pumpAndSettle();
    expect(find.text('贝壳'), findsOneWidget);
    expect(find.text('珍珠'), findsOneWidget);
    expect(find.text('鲫鱼'), findsNothing);
    await tester.tap(find.text('珍珠'));
    await tester.pumpAndSettle();
    expect(find.textContaining('兑换头像框'), findsOneWidget);
  });

  testWidgets('背包空的那一栏有一句话告诉你去哪儿弄', (tester) async {
    store.bag.clear();
    await open(tester, (c) => showBagSheet(c));
    expect(find.textContaining('钓鱼'), findsOneWidget);
    await tester.tapAt(const Offset(200, 40));
    await tester.pumpAndSettle();
    await open(tester, (c) => showBagSheet(c, feedTo: 'momo', feedToName: '墨墨'));
    expect(find.text('一把普通口粮'), findsOneWidget);
    expect(find.textContaining('还没有能喂的'), findsOneWidget);
  });

  testWidgets('钓到鱼的展示卡：名字、稀有度、长度、新鱼种、奖励；点按钮关掉', (tester) async {
    await open(tester, (c) => showFishCaught(c, {
          'id': 'carp_gold', 'name': '金鳞鲤', 'rarity': 'legend', 'about': '下雨时才浮上来。', 'size_cm': 66.4, 'record': false, 'first': true,
          'count': 1, 'left': 12, 'got': 50, //
        }));
    expect(find.text('钓到了新的鱼'), findsOneWidget);
    expect(find.text('金鳞鲤'), findsOneWidget);
    expect(find.text('传说'), findsOneWidget);
    expect(find.text('长 66.4 厘米'), findsOneWidget);
    expect(find.text('新'), findsOneWidget);
    expect(find.textContaining('第一次钓到，得 50 金币'), findsOneWidget);
    expect(find.textContaining('今天还能钓 12 次'), findsOneWidget);
    await tester.tap(find.text('收进鱼篓'));
    await tester.pumpAndSettle();
    expect(find.text('金鳞鲤'), findsNothing);

    // 破纪录；整个接口返回直接传进来（鱼在 fish 里）也认
    await open(tester, (c) => showFishCaught(c, {
          'fish': {'id': 'crucian', 'name': '鲫鱼', 'rarity': 'common', 'about': '贪嘴。', 'size_cm': 21.0, 'record': true, 'first': false},
          'count': 4, 'left': 0, 'got': 0, //
        }));
    expect(find.text('长 21.0 厘米 · 个人新纪录'), findsOneWidget);
    expect(find.text('冠'), findsOneWidget);
    expect(find.textContaining('今天钓满了'), findsOneWidget);
    await tester.tap(find.text('收进鱼篓'));
    await tester.pumpAndSettle();

    // 水草：没有长度和稀有度
    await open(tester, (c) => showFishCaught(c, {'id': 'weed', 'name': '一团水草', 'rarity': 'junk', 'about': '湿漉漉一团。', 'size_cm': 0, 'record': false, 'first': false, 'count': 2, 'left': 5, 'got': 0}));
    expect(find.textContaining('厘米'), findsNothing);
    expect(find.text('收起来'), findsOneWidget);
  });

  testWidgets('钓鱼图鉴：钓到的有名字和纪录，没钓到的是问号和在哪儿能钓', (tester) async {
    await open(tester, showFishBook);
    expect(find.text('钓鱼图鉴'), findsOneWidget);
    expect(find.text('1 / 2'), findsOneWidget);
    expect(find.text('今天还能钓 27 次'), findsOneWidget);
    expect(find.text('鲫鱼'), findsOneWidget);
    expect(find.textContaining('最大 18.4 厘米'), findsOneWidget);
    expect(find.text('月光鱼'), findsNothing);
    expect(find.text('？？？'), findsOneWidget);
    expect(find.textContaining('晴朗的夜里才有'), findsOneWidget);
  });

  testWidgets('小动物册：指定的那只展开，最爱没喂出来的是问号，写着下一份礼物', (tester) async {
    await open(tester, (c) => showPetBook(c, pet: 'teddy'));
    expect(find.text('栗子'), findsOneWidget);
    expect(find.text('最好的朋友'), findsOneWidget);
    expect(find.text('亲密度 32 / 60'), findsOneWidget);
    expect(find.text('肉骨头'), findsOneWidget);
    expect(find.text('还不知道'), findsNWidgets(2));
    expect(find.text('下一份：亲密度到 50，送「栗子的爪印头像框」'), findsOneWidget);
    expect(find.text('到 15 时送过：骨头 ×2'), findsOneWidget);
    expect(find.text('骨头'), findsOneWidget);
    expect(find.text('没收到过'), findsOneWidget);
    // 另一只收着，点开
    expect(find.textContaining('礼物 0 / 1 · 下一份：亲密度到 5'), findsOneWidget);
    await tester.tap(find.text('墨墨'));
    await tester.pumpAndSettle();
    expect(find.text('还不知道'), findsNWidgets(3));
  });

  testWidgets('每样东西、每件头像框都画得出来（不报错）', (tester) async {
    const ids = [
      'crucian', 'loach', 'goldfish', 'shrimp', 'whitebait', 'silver', 'bass', 'mandarin', 'crab', 'carp_gold', 'moon', 'weed',
      'food_kibble', 'food_dried_fish', 'food_bone', 'food_cream',
      'shell', 'shell_conch', 'pebble', 'clover', 'pinecone', 'ginkgo', 'maple', 'flower', 'feather', 'bell', 'yarn', 'bone', 'stick', 'dried_fish', 'pearl', 'knot',
    ];
    await tester.pumpWidget(MaterialApp(
      home: SingleChildScrollView(
        child: Wrap(children: [
          for (final id in ids) ItemArt(id, size: 40),
          const ItemArt('moon', size: 40, shadow: true),
          for (final id in keepsakeFrameIds) KeepsakeFrame(id, size: 60),
        ]),
      ),
    ));
    expect(tester.takeException(), isNull);
    expect(keepsakeFrameIds.length, 14);
  });
}
