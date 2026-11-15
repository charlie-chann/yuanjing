import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'package:yuanjing_engine/yuanjing_engine.dart';

import '../features/me/me_page.dart';
import '../features/plaza/plaza_page.dart';
import '../features/release/release_page.dart';
import '../features/shop/shop_page.dart';
import '../features/wish/wish_page.dart';
import 'nav_bar.dart';
import 'skin.dart';
import 'store.dart';

/// 应用外壳：底部五个入口（许愿、广场、释放、商城、我的）。
/// 许愿仪式进行时底栏收起，让画面完整；每天第一次打开弹出签到。
class Shell extends StatefulWidget {
  const Shell({super.key});

  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> with WidgetsBindingObserver {
  int _tab = 0;
  final _opened = <int>{0};
  final _immersive = ValueNotifier(false);

  static const _tabs = ['许愿', '广场', '释放', '商城', '我的'];

  @override
  void initState() {
    super.initState();
    // 等登录和拉数据结束再判断要不要弹签到（连不上服务器就不弹）
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      for (var i = 0; i < 20 && !store.online; i++) {
        await Future.delayed(const Duration(milliseconds: 300));
      }
      if (mounted && store.online && !store.checkedIn) showCheckin(context);
    });
    WidgetsBinding.instance.addObserver(this);
  }

  /// 从后台回来：重新连一次服务器，补发没网时的改动、拉别人给的赞和好友申请
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) store.connect();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _immersive.dispose();
    super.dispose();
  }

  void _go(int i) {
    if (i == _tab) return;
    YuanjingAudio.sfx('tap');
    // 许愿页、释放页回到前台时自己恢复环境音；其他几页共用一条安静的
    if (i != 0 && i != 2) YuanjingAudio.bed('room');
    setState(() {
      _tab = i;
      _opened.add(i);
    });
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: store,
      builder: (context, _) {
        final s = store.skin;
        // 许愿页是深色的原生画面，其余几页跟着皮肤走，状态栏的字色要跟着换
        final darkBars = _tab == 0 || _tab == 2 || s.dark;
        return AnnotatedRegion<SystemUiOverlayStyle>(
          value: darkBars ? SystemUiOverlayStyle.light : SystemUiOverlayStyle.dark,
          child: Scaffold(
            body: Stack(
              fit: StackFit.expand,
              children: [
                IndexedStack(
                  index: _tab,
                  children: [
                    WishPage(immersive: _immersive, active: _tab == 0),
                    // 其余几页第一次点开才创建
                    _opened.contains(1) ? const PlazaPage() : const SizedBox.shrink(),
                    _opened.contains(2) ? ReleasePage(immersive: _immersive, active: _tab == 2) : const SizedBox.shrink(),
                    _opened.contains(3) ? const ShopPage() : const SizedBox.shrink(),
                    _opened.contains(4) ? const MePage() : const SizedBox.shrink(),
                  ],
                ),
                Positioned(
                  left: 0,
                  right: 0,
                  // 底栏比原来高 6，离底边近 6，上沿位置不变，各页给底栏留的空不用改
                  bottom: MediaQuery.paddingOf(context).bottom + 4,
                  child: ValueListenableBuilder(
                    valueListenable: _immersive,
                    builder: (_, hidden, child) => IgnorePointer(
                      ignoring: hidden,
                      child: AnimatedOpacity(opacity: hidden ? 0 : 1, duration: const Duration(milliseconds: 500), child: child),
                    ),
                    child: Center(
                      child: NavBar(labels: _tabs, index: _tab, onTap: _go, skin: s, hidden: _immersive),
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

/// 每日签到：连续签到每多一天多 2 个金币，最多多 10 个。
void showCheckin(BuildContext context) {
  showSkinSheet<void>(context, (context, s) {
    final done = store.checkedIn;
    // 今天签到的话是连续第几天；七天一轮地显示。没签到时按「昨天签了就接着算」估计，以服务器返回为准
    final next = done ? store.streak : store.streak + 1;
    final today = (next - 1) % 7 + 1;
    final filled = done ? today : today - 1;
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(done ? '今天已经签到' : '今天，来领一份好运', style: s.title(24)),
      const SizedBox(height: 6),
      Text(done ? '连续签到 ${store.streak} 天。明天再来。' : '每天打开签到领金币，连续签到越久领得越多。', style: s.hint(14)),
      const SizedBox(height: 18),
      Row(children: [
        for (var d = 1; d <= 7; d++)
          Expanded(
            child: Container(
              height: 62,
              margin: EdgeInsets.only(right: d == 7 ? 0 : 6),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(14),
                gradient: d <= filled ? s.accent : null,
                color: s.card,
                border: Border.all(color: d == today && !done ? s.deep : s.line, width: d == today && !done ? 1.6 : 1),
              ),
              child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                Text('第$d天', style: TextStyle(fontSize: 10.5, color: d <= filled ? s.onAccent : s.sub)),
                const SizedBox(height: 4),
                Text('+${10 + ((d - 1) * 2).clamp(0, 10)}',
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: d <= filled ? s.onAccent : s.ink)),
              ]),
            ),
          ),
      ]),
      const SizedBox(height: 20),
      SButton(done ? '好的' : '签到',
          expand: true,
          onTap: () async {
            if (!done) {
              try {
                final got = await store.checkin();
                if (context.mounted) coinToast(context, got, '签到成功，连续 ${store.streak} 天');
              } on ApiError catch (e) {
                if (context.mounted) toast(context, e.message);
                return;
              }
            }
            if (context.mounted) Navigator.of(context).pop();
          }),
    ]);
  });
}

/// 打开一个新页面
Future<T?> push<T>(BuildContext context, Widget page) => Navigator.of(context).push<T>(MaterialPageRoute(builder: (_) => page));
