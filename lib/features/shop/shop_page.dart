import 'package:flutter/material.dart';
import 'package:yuanjing_engine/yuanjing_engine.dart';

import '../../app/skin.dart';
import '../../app/store.dart';
import '../me/me_page.dart';
import 'shop_art.dart';
import 'shop_data.dart';
import 'voice_page.dart';

/// 宇宙商城：像游戏里的道具店，一张会员卡加一整格商品卡（图、名字、价格）。
/// 点卡片弹出购买确认；两张声音类的卡（肯定语音频、成品音频库）点进去是原来的功能页。
/// 下面另有两组和湖心小寺连着的：「小寺」卖喂小动物的口粮（买的是数量，进背包）；
/// 「小动物的礼物」不卖，是岛上的小动物送的、或者用它们叼来的收藏品换的头像框，没得到的灰着并写明怎么得到。
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

  /// 小寺的口粮（可叠加，买的是数量）
  final FoodItem? food;

  /// 声音类：true 成品音频库，false 肯定语音频
  final bool library;
  const _Entry(this.art, this.name, {this.item, this.food, this.library = false});
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
  static final _foods = [for (final f in foodItems) _Entry(f.id, f.name, food: f)];
  static final _keepsakes = [for (final i in keepsakes) _Entry(i.id, i.name, item: i)];

  @override
  void initState() {
    super.initState();
    // 兑换要看背包里有几个收藏品：进商城时取一遍新的（没网就用上次的）
    if (store.online) store.loadBag().catchError((_) {});
  }

  void _open(_Entry e) {
    YuanjingHaptics.play('tick');
    YuanjingAudio.sfx('tap');
    final item = e.item;
    if (e.food != null) {
      _confirmFood(e.food!);
    } else if (item == null) {
      Navigator.of(context).push(MaterialPageRoute(builder: (_) => VoicePage(library: e.library)));
    } else if (item.group == 'keepsake') {
      _confirmKeepsake(item);
    } else {
      _confirm(item);
    }
  }

  // ───────── 小寺的口粮：选数量再买 ─────────

  void _confirmFood(FoodItem food) {
    var n = 1;
    showSkinSheet<void>(context, (sheet, s) {
      return StatefulBuilder(builder: (sheet, setSheet) {
        final total = food.price * n;
        final short = total - store.coins;
        Widget step(IconData icon, int d) => GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () => setSheet(() => n = (n + d).clamp(1, 99)),
              child: Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: s.line)),
                child: Icon(icon, size: 20, color: s.ink),
              ),
            );
        return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Container(
            height: (MediaQuery.sizeOf(sheet).height * 0.22).clamp(150.0, 200.0),
            decoration: BoxDecoration(borderRadius: BorderRadius.circular(24), border: Border.all(color: _gold.withValues(alpha: 0.45))),
            child: ShopArt(food.id, clock: _clock, radius: 23),
          ),
          const SizedBox(height: 16),
          Text(food.name, style: s.title(23)),
          const SizedBox(height: 2),
          Text(food.about, style: s.hint(14)),
          Text('买了放进背包。到湖心小寺走到小动物跟前喂它，亲密度 +${food.feed}；喂到它最爱的，涨得更多', style: s.hint(12)),
          const SizedBox(height: 14),
          Row(children: [
            const CoinIcon(size: 24),
            const SizedBox(width: 8),
            Text('$total', style: TextStyle(fontFamily: 'Didot', fontSize: 28, fontWeight: FontWeight.w700, color: s.ink)),
            const Spacer(),
            step(Icons.remove_rounded, -1),
            SizedBox(width: 48, child: Text('$n', textAlign: TextAlign.center, style: TextStyle(fontSize: 19, fontWeight: FontWeight.w700, color: s.ink))),
            step(Icons.add_rounded, 1),
          ]),
          const SizedBox(height: 4),
          Text(short > 0 ? '还差 $short 个金币' : '背包里有 ${store.bagCount(food.id)} 个 · 我的金币 ${store.coins}', style: s.hint(12.5)),
          const SizedBox(height: 16),
          if (short > 0)
            SButton('看看怎么赚金币', expand: true, ghost: true, onTap: () => showCoins(sheet))
          else
            SButton('买 $n 个', expand: true, onTap: () => _buyFood(sheet, food, n)),
        ]);
      });
    });
  }

  Future<void> _buyFood(BuildContext sheet, FoodItem food, int n) async {
    try {
      await store.buyStack(food.id, n);
    } on ApiError catch (e) {
      if (sheet.mounted) toast(sheet, e.message);
      return;
    }
    YuanjingAudio.sfx('sparkle', volume: 0.7);
    if (sheet.mounted) Navigator.of(sheet).pop();
    if (mounted) toast(context, '$n 个${food.name}已经放进背包');
  }

  // ───────── 小动物的礼物：不卖，写明怎么得到；收藏品够了可以兑换 ─────────

  void _confirmKeepsake(ShopItem item) {
    showSkinSheet<void>(context, (sheet, s) {
      final owned = store.owned.contains(item.id);
      final on = store.equipped.contains(item.id);
      final enough = item.cost.isNotEmpty && item.cost.entries.every((e) => store.bagCount(e.key) >= e.value);
      return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Container(
          height: (MediaQuery.sizeOf(sheet).height * 0.27).clamp(170.0, 230.0),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(24), border: Border.all(color: _gold.withValues(alpha: 0.45))),
          child: _Dim(dim: !owned, child: ShopArt(item.id, clock: _clock, radius: 23)),
        ),
        const SizedBox(height: 16),
        Text(item.name, style: s.title(23)),
        const SizedBox(height: 2),
        Text(item.about, style: s.hint(14)),
        Text('戴上后在主页和广场的头像上能看到', style: s.hint(12)),
        const SizedBox(height: 14),
        if (owned)
          Text(on ? '使用中' : '已拥有', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: s.deep))
        else if (item.petName != null) ...[
          Text('这件不卖，是${item.petName}的礼物', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: s.deep)),
          const SizedBox(height: 2),
          Text('去湖心小寺摸摸它、喂喂它。${keepsakeSource(item)}，它会亲自送给你。', style: s.hint(13)),
        ] else ...[
          Text('用小动物叼来的收藏品兑换', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: s.deep)),
          const SizedBox(height: 6),
          for (final e in item.cost.entries)
            Padding(
              padding: const EdgeInsets.only(bottom: 3),
              child: Row(children: [
                Icon(store.bagCount(e.key) >= e.value ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded, size: 16, color: store.bagCount(e.key) >= e.value ? s.deep : s.sub),
                const SizedBox(width: 6),
                Text('${keepNames[e.key] ?? e.key} × ${e.value}', style: s.body(14)),
                const Spacer(),
                Text('你有 ${store.bagCount(e.key)} / ${e.value}', style: s.hint(13)),
              ]),
            ),
          if (!enough) Text('和岛上的小动物熟了以后，它们每天会叼一件来', style: s.hint(12)),
        ],
        const SizedBox(height: 16),
        if (owned)
          SButton(on ? '取下' : '戴上', expand: true, ghost: on, onTap: () => _wear(sheet, item, !on))
        else if (item.cost.isNotEmpty)
          SButton(enough ? '兑换' : '收藏品还不够', expand: true, onTap: enough ? () => _redeem(sheet, item) : null)
        else
          SButton('知道了', expand: true, ghost: true, onTap: () => Navigator.of(sheet).pop()),
      ]);
    });
  }

  Future<void> _redeem(BuildContext sheet, ShopItem item) async {
    try {
      await store.redeem(item.id);
    } on ApiError catch (e) {
      if (sheet.mounted) toast(sheet, e.message);
      return;
    }
    YuanjingAudio.sfx('sparkle', volume: 0.7);
    YuanjingHaptics.play('tick');
    if (sheet.mounted) Navigator.of(sheet).pop();
    if (mounted) toast(context, '换到了，已戴上「${item.name}」');
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
        Text(item.isFrame ? '戴上后在主页和广场的头像上能看到' : '会出现在「我的 → 我的房间」里', style: s.hint(12)),
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

  static String _onLabel(ShopItem item) => item.isFrame ? '戴上' : '摆出来';
  static String _offLabel(ShopItem item) => item.isFrame ? '取下' : '收起来';

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
    if (mounted) toast(context, item.isFrame ? '已戴上「${item.name}」' : '「${item.name}」已经摆进房间');
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

  Widget _grid(List<_Entry> list) => SliverPadding(
        padding: const EdgeInsets.fromLTRB(22, 0, 22, 0),
        sliver: SliverGrid.builder(
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 2, mainAxisSpacing: 12, crossAxisSpacing: 12, childAspectRatio: 0.76),
          itemCount: list.length,
          itemBuilder: (context, i) => _Card(entry: list[i], clock: _clock, onTap: () => _open(list[i])),
        ),
      );

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
          _grid(_entries),
          SliverToBoxAdapter(child: _GroupTitle('小寺', '喂湖心小寺里小动物的口粮，买了放进背包', s)),
          _grid(_foods),
          SliverToBoxAdapter(child: _GroupTitle('小动物的礼物', '不卖。和岛上的小动物熟了，它们送的；或者用它们叼来的收藏品换', s)),
          _grid(_keepsakes),
          const SliverToBoxAdapter(child: SizedBox(height: 100)),
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
    // 小动物的礼物：还没得到的灰着
    final locked = item != null && item.group == 'keepsake' && !owned;
    final have = entry.food == null ? 0 : store.bagCount(entry.food!.id);

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
              Positioned.fill(child: _Dim(dim: locked, child: ShopArt(entry.art, clock: clock, radius: 17))),
              if (member) const Positioned(left: 8, top: 8, child: _Tag('会员', fill: true)),
              if (locked) const Positioned(left: 8, top: 8, child: _Tag('未得到')),
              if (have > 0) Positioned(right: 8, top: 8, child: _Tag('背包里 $have')),
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
    final food = entry.food;
    if (food != null) {
      return Row(children: [
        const CoinIcon(size: 17),
        const SizedBox(width: 6),
        Text('${food.price}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: _gold, letterSpacing: 0.5)),
        const Text(' / 个', style: weak),
        const Spacer(),
        Text('亲密度 +${food.feed}', style: weak),
      ]);
    }
    if (item != null && item.group == 'keepsake' && !owned) {
      // 怎么得到：动物送的写亲密度；收藏品换的写要什么，够了就提示可以换
      final enough = item.cost.isNotEmpty && item.cost.entries.every((e) => store.bagCount(e.key) >= e.value);
      return Row(children: [
        Icon(enough ? Icons.redeem_rounded : (item.petName != null ? Icons.pets_rounded : Icons.lock_outline_rounded), size: 14, color: enough ? _gold : _muted),
        const SizedBox(width: 4),
        Expanded(child: Text(enough ? '收藏品够了 · 点开兑换' : keepsakeSource(item), maxLines: 1, overflow: TextOverflow.ellipsis, style: enough ? strong.copyWith(fontSize: 12.5) : weak.copyWith(fontSize: 11.5))),
      ]);
    }
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

/// 分组的小标题
class _GroupTitle extends StatelessWidget {
  final String title;
  final String about;
  final Skin skin;
  const _GroupTitle(this.title, this.about, this.skin);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 26, 24, 12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: skin.title(19)),
        const SizedBox(height: 2),
        Text(about, style: skin.hint(12.5)),
      ]),
    );
  }
}

/// 还没得到的东西：图变成灰的、暗一点
class _Dim extends StatelessWidget {
  final bool dim;
  final Widget child;
  const _Dim({required this.dim, required this.child});

  @override
  Widget build(BuildContext context) {
    if (!dim) return child;
    return Opacity(
      opacity: 0.55,
      child: ColorFiltered(
        colorFilter: const ColorFilter.matrix([0.33, 0.5, 0.17, 0, 0, 0.33, 0.5, 0.17, 0, 0, 0.33, 0.5, 0.17, 0, 0, 0, 0, 0, 1, 0]),
        child: child,
      ),
    );
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
