import 'package:flutter/material.dart';
import 'package:yuanjing_engine/yuanjing_engine.dart';

import '../../app/skin.dart';
import '../../app/store.dart';
import '../me/me_page.dart';
import 'shop_art.dart';
import 'shop_data.dart';
import 'voice_page.dart';

/// 宇宙商城：像游戏里的道具店，一张会员卡加一整格商品卡（图、名字、价格），不分类。
/// 点卡片弹出购买确认；两张声音类的卡（肯定语音频、成品音频库）点进去是原来的功能页。
class ShopPage extends StatefulWidget {
  const ShopPage({super.key});

  @override
  State<ShopPage> createState() => _ShopPageState();
}

// 商品卡上的深色「宝盒」配色，所有皮肤下都一样
const _boxTop = Color(0xFF241D15);
const _boxBottom = Color(0xFF110D09);
const _gold = Color(0xFFE9CF8F);
const _goldDeep = Color(0xFFA9812F);
const _cream = Color(0xFFF1E3C4);
const _muted = Color(0xFFA9987B);

/// 格子里的一张卡：装扮商品，或者两件声音类的「商品」
class _Entry {
  final String art;
  final String name;
  final ShopItem? item;

  /// 声音类：true 成品音频库，false 肯定语音频
  final bool library;
  const _Entry(this.art, this.name, {this.item, this.library = false});
}

class _ShopPageState extends State<ShopPage> with SingleTickerProviderStateMixin {
  /// 全商城共用的一个循环时钟，所有卡片的图都跟着它动
  late final _clock = AnimationController(vsync: this, duration: const Duration(seconds: 10));
  bool _still = false;
  bool _visible = true;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // 减少动态效果时停在一帧上；切到别的底栏页时（IndexedStack 里看不见）也停
    _still = MediaQuery.disableAnimationsOf(context);
    _visible = Visibility.of(context);
    if (_still || !_visible) {
      _clock.stop();
      if (_still) _clock.value = 0.12;
    } else if (!_clock.isAnimating) {
      _clock.repeat();
    }
  }

  @override
  void dispose() {
    _clock.dispose();
    super.dispose();
  }

  static final _entries = [
    const _Entry('voice_affirm', '肯定语音频'),
    const _Entry('voice_library', '成品音频库', library: true),
    for (final i in shopItems) _Entry(i.id, i.name, item: i),
  ];

  void _open(_Entry e) {
    YuanjingHaptics.play('tick');
    YuanjingAudio.sfx('tap');
    final item = e.item;
    if (item == null) {
      Navigator.of(context).push(MaterialPageRoute(builder: (_) => VoicePage(library: e.library)));
      return;
    }
    _confirm(item);
  }

  // ───────── 购买确认 ─────────

  void _confirm(ShopItem item) {
    showSkinSheet<void>(context, (sheet, s) {
      final owned = store.owned.contains(item.id);
      final on = store.equipped.contains(item.id);
      final short = item.price - store.coins;
      return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Container(
          // 小屏手机上图缩一点，免得面板放不下
          height: (MediaQuery.sizeOf(sheet).height * 0.27).clamp(170.0, 230.0),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: _gold.withValues(alpha: 0.45)),
            boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.35), blurRadius: 24, offset: const Offset(0, 10))],
          ),
          child: ShopArt(item.id, clock: _clock, radius: 23),
        ),
        const SizedBox(height: 16),
        Row(children: [
          Flexible(child: Text(item.name, style: s.title(23))),
          if (item.member) const Padding(padding: EdgeInsets.only(left: 8), child: MemberTag()),
        ]),
        const SizedBox(height: 2),
        Text(item.about, style: s.hint(14)),
        Text(item.group == 'frame' ? '戴上后在主页和广场的头像上能看到' : '会出现在「我的 → 我的房间」里', style: s.hint(12)),
        const SizedBox(height: 14),
        Row(children: [
          if (owned)
            Text(on ? '使用中' : '已拥有', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: s.deep))
          else if (item.member)
            Text('会员免费领', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: s.deep))
          else ...[
            const CoinIcon(size: 24),
            const SizedBox(width: 8),
            Text('${item.price}', style: TextStyle(fontFamily: 'Didot', fontSize: 28, fontWeight: FontWeight.w700, color: s.ink)),
          ],
          const Spacer(),
          Text('我的金币 ${store.coins}', style: s.hint(13)),
        ]),
        if (!owned && !item.member && short > 0) Padding(padding: const EdgeInsets.only(top: 4), child: Text('还差 $short 个金币，做点正向的小事就能攒到', style: s.hint(12.5))),
        const SizedBox(height: 16),
        if (owned)
          SButton(on ? _offLabel(item) : _onLabel(item), expand: true, ghost: on, onTap: () => _wear(sheet, item, !on))
        else if (item.member && !store.member)
          SButton('开通会员领取', expand: true, onTap: () => showMember(sheet))
        else if (!item.member && short > 0)
          SButton('看看怎么赚金币', expand: true, ghost: true, onTap: () => showCoins(sheet))
        else
          SButton(item.member ? '免费领取' : '购买', expand: true, onTap: () => _buy(sheet, item)),
      ]);
    });
  }

  static String _onLabel(ShopItem item) => item.group == 'frame' ? '戴上' : '摆出来';
  static String _offLabel(ShopItem item) => item.group == 'frame' ? '取下' : '收起来';

  Future<void> _buy(BuildContext sheet, ShopItem item) async {
    try {
      await store.buy(item.id);
    } on ApiError catch (e) {
      if (sheet.mounted) toast(sheet, e.message);
      return;
    }
    YuanjingAudio.sfx('sparkle', volume: 0.7);
    YuanjingHaptics.play('tick');
    if (sheet.mounted) Navigator.of(sheet).pop();
    if (mounted) toast(context, item.group == 'frame' ? '已戴上「${item.name}」' : '「${item.name}」已经摆进房间');
  }

  /// 戴上或取下。头像框同时只能戴一个，服务器会处理
  Future<void> _wear(BuildContext sheet, ShopItem item, bool on) async {
    try {
      await store.wear(item.id, on);
    } on ApiError catch (e) {
      if (sheet.mounted) toast(sheet, e.message);
    }
  }

  // ───────── 页面 ─────────

  @override
  Widget build(BuildContext context) {
    return SkinPage(
      title: '宇宙商城',
      trailing: GestureDetector(onTap: () => showCoins(context), child: const CoinBadge()),
      builder: (context, s) {
        return CustomScrollView(slivers: [
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(22, 8, 22, 14),
            sliver: SliverToBoxAdapter(child: _MemberCard(onTap: () => showMember(context))),
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(22, 0, 22, 100),
            sliver: SliverGrid.builder(
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 2, mainAxisSpacing: 12, crossAxisSpacing: 12, childAspectRatio: 0.76),
              itemCount: _entries.length,
              itemBuilder: (context, i) => _Card(entry: _entries[i], clock: _clock, onTap: () => _open(_entries[i])),
            ),
          ),
        ]);
      },
    );
  }
}

/// 一张商品卡：上面是会动的商品图，下面是名字和价格（或者拥有状态）
class _Card extends StatelessWidget {
  final _Entry entry;
  final Animation<double> clock;
  final VoidCallback onTap;
  const _Card({required this.entry, required this.clock, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final item = entry.item;
    final owned = item != null && store.owned.contains(item.id);
    final on = item != null && store.equipped.contains(item.id);
    final member = item?.member ?? entry.library;

    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(6),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(22),
          gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [_boxTop, _boxBottom]),
          border: Border.all(color: on ? _gold : _gold.withValues(alpha: 0.28), width: on ? 1.4 : 1),
          boxShadow: [
            BoxShadow(color: Colors.black.withValues(alpha: 0.28), blurRadius: 16, offset: const Offset(0, 8)),
            if (on) BoxShadow(color: _gold.withValues(alpha: 0.25), blurRadius: 18),
          ],
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(
            child: Stack(children: [
              Positioned.fill(child: ShopArt(entry.art, clock: clock, radius: 17)),
              if (member) const Positioned(left: 8, top: 8, child: _Tag('会员', fill: true)),
              if (owned) Positioned(right: 8, top: 8, child: _Tag(on ? '使用中' : '已拥有', fill: on)),
            ]),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(6, 9, 6, 5),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(entry.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontFamily: displayFont, fontSize: 15, fontWeight: FontWeight.w700, letterSpacing: 0.5, color: _cream)),
              const SizedBox(height: 5),
              SizedBox(height: 20, child: _price(item, owned, on)),
            ]),
          ),
        ]),
      ),
    );
  }

  Widget _price(ShopItem? item, bool owned, bool on) {
    const strong = TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: _gold);
    const weak = TextStyle(fontSize: 12.5, color: _muted);
    if (item == null) {
      return Row(children: [
        const Icon(Icons.graphic_eq_rounded, size: 16, color: _gold),
        const SizedBox(width: 5),
        Text(entry.library ? '会员畅听' : '免费 · 自己写', style: entry.library ? strong : weak),
      ]);
    }
    if (owned) {
      return Row(children: [
        Icon(on ? Icons.check_circle_rounded : Icons.inventory_2_outlined, size: 15, color: on ? _gold : _muted),
        const SizedBox(width: 5),
        Text(on ? '使用中' : '已拥有 · 点开使用', style: on ? strong : weak),
      ]);
    }
    if (item.member) return const Text('会员免费领', style: strong);
    return Row(children: [
      const CoinIcon(size: 17),
      const SizedBox(width: 6),
      Text('${item.price}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: _gold, letterSpacing: 0.5)),
    ]);
  }
}

/// 商品图角上的小标
class _Tag extends StatelessWidget {
  final String text;
  final bool fill;
  const _Tag(this.text, {this.fill = false});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2.5),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(99),
        gradient: fill ? const LinearGradient(colors: [_gold, _goldDeep]) : null,
        color: fill ? null : Colors.black.withValues(alpha: 0.45),
        border: Border.all(color: fill ? Colors.white54 : _gold.withValues(alpha: 0.5), width: 0.7),
      ),
      child: Text(text, style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, color: fill ? const Color(0xFF1B1408) : _gold)),
    );
  }
}

/// 会员：一张紧凑的卡
class _MemberCard extends StatelessWidget {
  final VoidCallback onTap;
  const _MemberCard({required this.onTap});

  @override
  Widget build(BuildContext context) {
    final on = store.member;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        height: 70,
        padding: const EdgeInsets.fromLTRB(12, 0, 12, 0),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF3A2C16), Color(0xFF15100A)]),
          border: Border.all(color: _gold.withValues(alpha: 0.55)),
          boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.28), blurRadius: 16, offset: const Offset(0, 8))],
        ),
        child: Row(children: [
          Container(
            width: 44,
            height: 44,
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(center: Alignment(-0.3, -0.4), colors: [Color(0xFFFFF4C8), Color(0xFFF0C356), Color(0xFF9A6A14)]),
            ),
            child: const Icon(Icons.workspace_premium_rounded, size: 26, color: Color(0xFF4A3006)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(on ? '会员已开通' : '会员', style: const TextStyle(fontFamily: displayFont, fontSize: 16.5, fontWeight: FontWeight.w700, color: _cream)),
              const SizedBox(height: 2),
              const Text('限定皮肤 · 音频库 · 限定装扮免费领', maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 12, color: _muted)),
            ]),
          ),
          Container(
            height: 32,
            padding: const EdgeInsets.symmetric(horizontal: 14),
            alignment: Alignment.center,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(99),
              gradient: on ? null : const LinearGradient(colors: [_gold, _goldDeep]),
              border: Border.all(color: on ? _gold.withValues(alpha: 0.5) : Colors.white54, width: 0.8),
            ),
            child: Text(on ? '查看' : '开通', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: on ? _gold : const Color(0xFF1B1408))),
          ),
        ]),
      ),
    );
  }
}
