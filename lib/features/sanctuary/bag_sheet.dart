import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../app/skin.dart' show displayFont;
import '../../app/store.dart';
import 'islet_art.dart';
import 'sanctuary_ui.dart';

/// 湖心小寺里和「手上的东西」有关的几个弹层：背包、钓到鱼的展示卡、钓鱼图鉴、小动物册。
/// 数据都从 [store] 拿（背包、图鉴、小动物册各有一份上次取到的），在线时打开会再取一遍新的；
/// 没网时先显示上次的，卖东西这类要改数据的会提示连不上。
/// 样子跟 sanctuary_ui.dart 一套：墨褐的底、宣纸色的字、朱漆和鎏金。

const _title = TextStyle(fontFamily: displayFont, fontSize: 22, fontWeight: FontWeight.w700, letterSpacing: 2, color: SancColors.paper);
const _hint = TextStyle(fontSize: 12.5, height: 1.45, color: Color(0xB3F3E8CF));
const _body = TextStyle(fontSize: 13.5, height: 1.5, color: SancColors.paper);

Future<T?> _sheet<T>(BuildContext context, Widget child) {
  return showModalBottomSheet<T>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    barrierColor: Colors.black54,
    builder: (context) => ConstrainedBox(
      constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * 0.78),
      child: SanctuarySheet(
        padding: EdgeInsets.fromLTRB(20, 18, 20, 14 + MediaQuery.paddingOf(context).bottom),
        child: child,
      ),
    ),
  );
}

/// 一格的底：削角的小框，边线是稀有度的颜色
ShapeDecoration _box(Color edge, {bool selected = false, double fill = 0.07}) => ShapeDecoration(
      color: selected ? const Color(0x33C8452F) : SancColors.paper.withValues(alpha: fill),
      shape: BeveledRectangleBorder(borderRadius: BorderRadius.circular(6), side: BorderSide(color: selected ? SancColors.gold : edge.withValues(alpha: 0.6), width: selected ? 1.4 : 1)),
    );

/// 稀有度的小标
class _RarityTag extends StatelessWidget {
  final String? rarity;
  const _RarityTag(this.rarity);

  @override
  Widget build(BuildContext context) {
    final c = Rarity.color(rarity);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
      decoration: ShapeDecoration(shape: BeveledRectangleBorder(borderRadius: BorderRadius.circular(3), side: BorderSide(color: c.withValues(alpha: 0.8), width: 0.8))),
      child: Text(Rarity.name(rarity), style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: c)),
    );
  }
}

/// 朱漆的小印：「爱」「新」这样一个字
class _Seal extends StatelessWidget {
  final String glyph;
  final double size;
  const _Seal(this.glyph, {this.size = 18});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: ShapeDecoration(color: SancColors.vermilion, shape: BeveledRectangleBorder(borderRadius: BorderRadius.circular(size * 0.16), side: const BorderSide(color: SancColors.goldLit, width: 0.7))),
      child: Text(glyph, style: sancLabel(size * 0.58, SancColors.goldLit, spacing: 0)),
    );
  }
}

// ───────── 背包 ─────────

/// 背包弹层。分三栏：鱼、食材、礼物。
///
/// [feedTo] 给了小动物的编号时是「挑一样喂它」：只显示能喂的，它的最爱（已经喂出来的）有「爱」字印。
/// 第一格固定是「一把普通口粮（花 [feedCost] 金币）」，点它返回空字符串 ''；点背包里的东西返回它的编号；
/// 没挑就关掉返回 null。这里不调喂食接口，由调用方调。
/// 没给 [feedTo] 时是普通背包：看描述、卖出；返回值没有意义。
Future<String?> showBagSheet(BuildContext context, {String? feedTo, String? feedToName, int feedCost = 2}) {
  return _sheet<String>(context, BagPanel(feedTo: feedTo, feedToName: feedToName, feedCost: feedCost));
}

/// 背包弹层里的内容（单拿出来是为了好测）
class BagPanel extends StatefulWidget {
  final String? feedTo;
  final String? feedToName;
  final int feedCost;
  const BagPanel({super.key, this.feedTo, this.feedToName, this.feedCost = 2});

  @override
  State<BagPanel> createState() => _BagPanelState();
}

class _BagPanelState extends State<BagPanel> {
  static const _tabs = [('fish', '鱼'), ('food', '食材'), ('gift', '礼物')];
  static const _empty = {
    'fish': '还没有鱼。走到湖边或小池塘边，会多出一块「钓鱼」的牌子。',
    'food': '还没有食材。商城的「小寺」里有小饼干、小鱼干、肉骨头、猫条。',
    'gift': '还没有收藏品。和岛上的小动物熟了以后，它们每天会叼一件来送你。',
  };
  String _tab = 'fish';
  String? _picked;
  int _n = 1;
  String? _note;
  bool _busy = false;

  bool get _feeding => widget.feedTo != null;

  @override
  void initState() {
    super.initState();
    if (store.online) {
      store.loadBag().catchError((_) {});
      if (_feeding) store.loadPetBook().then((_) {}, onError: (_) {});
    }
  }

  Future<void> _sell(Map<String, dynamic> item) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final got = await store.sellItem(item['id'] as String, _n);
      _note = got > 0 ? '卖掉了，得 $got 金币' : '扔掉了';
    } on ApiError catch (e) {
      _note = e.message;
    }
    if (!mounted) return;
    setState(() {
      _busy = false;
      _n = 1;
      if (store.bagCount(item['id'] as String) == 0) _picked = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(listenable: store, builder: (context, _) => _feeding ? _feed(context) : _bag(context));
  }

  // 「挑一样喂它」
  Widget _feed(BuildContext context) {
    final favs = store.knownFavorites(widget.feedTo!);
    final items = [for (final i in store.bag) if (((i['feed'] as num?) ?? 0) > 0) i]
      ..sort((a, b) => (favs.contains(b['id']) ? 1 : 0) - (favs.contains(a['id']) ? 1 : 0));
    final name = widget.feedToName ?? '它';
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('挑一样喂$name', style: _title),
      const SizedBox(height: 4),
      Text(items.isEmpty ? '背包里还没有能喂的。去水边钓条鱼，或者到商城的「小寺」买点口粮。' : '喂到它最爱的，亲密度涨得更多。每样东西它爱不爱，喂过才知道。', style: _hint),
      const SizedBox(height: 12),
      Flexible(
        child: GridView.count(
          shrinkWrap: true,
          crossAxisCount: 4,
          mainAxisSpacing: 8,
          crossAxisSpacing: 8,
          childAspectRatio: 0.78,
          children: [
            _PlainFeedCell(cost: widget.feedCost, onTap: () => Navigator.of(context).pop('')),
            for (final i in items)
              _Cell(
                item: i,
                favorite: favs.contains(i['id']),
                gain: (i['feed'] as num).toInt(),
                onTap: () => Navigator.of(context).pop(i['id'] as String),
              ),
          ],
        ),
      ),
    ]);
  }

  // 普通背包
  Widget _bag(BuildContext context) {
    final items = [for (final i in store.bag) if (i['kind'] == _tab) i];
    Map<String, dynamic>? picked;
    for (final i in items) {
      if (i['id'] == _picked) picked = i;
    }
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        const Text('背包', style: _title),
        const Spacer(),
        Text('金币 ${store.coins}', style: sancLabel(14, SancColors.goldLit, spacing: 1)),
      ]),
      const SizedBox(height: 8),
      Row(children: [
        for (final (k, label) in _tabs)
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: SanctuaryChip(
              '$label ${store.bag.where((i) => i['kind'] == k).fold<int>(0, (a, i) => a + (i['count'] as num).toInt())}',
              selected: _tab == k,
              onTap: () => setState(() {
                _tab = k;
                _picked = null;
                _n = 1;
                _note = null;
              }),
            ),
          ),
      ]),
      const SizedBox(height: 10),
      if (items.isEmpty)
        Padding(padding: const EdgeInsets.symmetric(vertical: 36), child: Center(child: Text(_empty[_tab]!, textAlign: TextAlign.center, style: _hint)))
      else
        Flexible(
          child: GridView.count(
            shrinkWrap: true,
            crossAxisCount: 4,
            mainAxisSpacing: 8,
            crossAxisSpacing: 8,
            childAspectRatio: 0.78,
            children: [
              for (final i in items)
                _Cell(
                  item: i,
                  selected: i['id'] == _picked,
                  onTap: () => setState(() {
                    _picked = i['id'] as String;
                    _n = 1;
                    _note = null;
                  }),
                ),
            ],
          ),
        ),
      if (picked != null) ..._detail(picked) else if (_note != null) Padding(padding: const EdgeInsets.only(top: 10), child: Text(_note!, style: _hint)),
    ]);
  }

  List<Widget> _detail(Map<String, dynamic> item) {
    final count = (item['count'] as num).toInt();
    final sell = (item['sell'] as num).toInt();
    final feed = ((item['feed'] as num?) ?? 0).toInt();
    final n = _n.clamp(1, count);
    Widget step(String glyph, VoidCallback onTap) => GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: onTap,
          child: Container(width: 38, height: 38, alignment: Alignment.center, decoration: _box(SancColors.paper), child: Text(glyph, style: sancLabel(17, SancColors.paper, spacing: 0))),
        );
    return [
      const SizedBox(height: 12),
      Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        ItemArt(item['id'] as String, size: 58),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Flexible(child: Text(item['name'] as String, style: sancLabel(17, SancColors.paper, spacing: 1))),
              const SizedBox(width: 8),
              _RarityTag(item['rarity'] as String?),
            ]),
            const SizedBox(height: 3),
            Text(item['about'] as String, style: _body),
            Text(
              [
                if (feed > 0) '喂小动物：亲密度 +$feed',
                if (item['kind'] == 'gift') '可以在商城的「小动物的礼物」里兑换头像框',
                sell > 0 ? '卖 $sell 金币一个' : '卖不出钱',
              ].join(' · '),
              style: _hint,
            ),
          ]),
        ),
      ]),
      const SizedBox(height: 10),
      Row(children: [
        step('−', () => setState(() => _n = math.max(1, n - 1))),
        SizedBox(width: 50, child: Text('$n', textAlign: TextAlign.center, style: sancLabel(17, SancColors.paper, spacing: 0))),
        step('+', () => setState(() => _n = math.min(count, n + 1))),
        const SizedBox(width: 8),
        SanctuaryChip('全部', selected: n == count && count > 1, onTap: () => setState(() => _n = count)),
        const Spacer(),
        if (_note != null) Flexible(child: Text(_note!, textAlign: TextAlign.right, style: _hint)),
      ]),
      const SizedBox(height: 10),
      Opacity(
        opacity: _busy ? 0.5 : 1,
        child: LacquerButton(sell > 0 ? '卖出 $n 个 · 得 ${sell * n} 金币' : '扔掉 $n 个', onTap: () {
          _n = n;
          _sell(item);
        }),
      ),
    ];
  }
}

/// 背包里的一格：小画、名字、数量；边线是稀有度的颜色
class _Cell extends StatelessWidget {
  final Map<String, dynamic> item;
  final bool selected;
  final bool favorite;

  /// 喂食模式下显示「+2」
  final int? gain;
  final VoidCallback onTap;
  const _Cell({required this.item, this.selected = false, this.favorite = false, this.gain, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final rarity = item['rarity'] as String?;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        decoration: _box(Rarity.color(rarity), selected: selected),
        child: Stack(children: [
          Positioned.fill(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(4, 6, 4, 4),
              child: Column(children: [
                Expanded(child: FittedBox(child: ItemArt(item['id'] as String, size: 52))),
                const SizedBox(height: 2),
                Text(item['name'] as String, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11.5, color: SancColors.paper)),
              ]),
            ),
          ),
          Positioned(right: 5, top: 3, child: Text('×${item['count']}', style: sancLabel(11.5, Rarity.color(rarity), spacing: 0))),
          if (favorite) const Positioned(left: 4, top: 4, child: _Seal('爱')),
          if (gain != null && !favorite) Positioned(left: 5, top: 3, child: Text('+$gain', style: sancLabel(11, const Color(0xB3F3E8CF), spacing: 0))),
        ]),
      ),
    );
  }
}

/// 喂食模式的第一格：一把普通口粮（花金币）
class _PlainFeedCell extends StatelessWidget {
  final int cost;
  final VoidCallback onTap;
  const _PlainFeedCell({required this.cost, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        decoration: _box(SancColors.gold, fill: 0.1),
        padding: const EdgeInsets.fromLTRB(4, 6, 4, 4),
        child: Column(children: [
          const Expanded(child: FittedBox(child: CustomPaint(size: Size.square(52), painter: _BowlPainter()))),
          const SizedBox(height: 2),
          const Text('一把普通口粮', maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 11, color: SancColors.paper)),
          Text('花 $cost 金币', maxLines: 1, style: const TextStyle(fontSize: 10.5, color: SancColors.goldLit)),
        ]),
      ),
    );
  }
}

/// 一只装着口粮的小陶盆
class _BowlPainter extends CustomPainter {
  const _BowlPainter();

  @override
  void paint(Canvas canvas, Size size) {
    canvas.translate(size.width / 2, size.height / 2);
    canvas.scale(size.width / 100);
    final rnd = math.Random(3);
    for (var i = 0; i < 14; i++) {
      final x = -22 + rnd.nextDouble() * 44;
      canvas.drawCircle(Offset(x, -4 - (1 - x.abs() / 24) * 9 + rnd.nextDouble() * 4), 4.4, Paint()..color = Color.lerp(const Color(0xFFD9A25C), const Color(0xFF9A6A34), rnd.nextDouble())!);
    }
    final bowl = Path()
      ..moveTo(-34, -2)
      ..cubicTo(-32, 22, -24, 30, -16, 31)
      ..lineTo(16, 31)
      ..cubicTo(24, 30, 32, 22, 34, -2)
      ..close();
    canvas.drawPath(bowl, Paint()..shader = const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFB9623F), Color(0xFF7A3A22)]).createShader(const Rect.fromLTRB(-34, -2, 34, 31)));
    canvas.drawLine(const Offset(-33, 4), const Offset(33, 4), Paint()
      ..color = SancColors.paper.withValues(alpha: 0.5)
      ..strokeWidth = 2);
  }

  @override
  bool shouldRepaint(_BowlPainter old) => false;
}

// ───────── 钓到鱼的展示卡 ─────────

/// 钓到鱼的展示卡：鱼的画、名字、稀有度、长度、是不是新纪录或新鱼种。
/// [fish] 是 `POST /fishing/catch` 的返回摊平成的一个 Map：`{id, name, rarity, about, size_cm, record, first, count, left, got}`
/// （直接把整个返回传进来、鱼放在 fish 这一项里也认）。点「收进鱼篓」或卡片外面关掉。
Future<void> showFishCaught(BuildContext context, Map<String, dynamic> fish) {
  final f = fish['fish'] is Map ? {...fish, ...Map<String, dynamic>.from(fish['fish'] as Map)} : fish;
  return showGeneralDialog<void>(
    context: context,
    barrierDismissible: true,
    barrierLabel: '关掉',
    barrierColor: Colors.black54,
    transitionDuration: const Duration(milliseconds: 260),
    transitionBuilder: (context, a, _, child) => FadeTransition(
      opacity: a,
      child: ScaleTransition(scale: Tween(begin: 0.92, end: 1.0).animate(CurvedAnimation(parent: a, curve: Curves.easeOutBack)), child: child),
    ),
    pageBuilder: (context, _, _) => Center(child: FishCaughtCard(f, onClose: () => Navigator.of(context).pop())),
  );
}

/// 展示卡本身：一张宣纸，鱼画在水色的圆里
class FishCaughtCard extends StatelessWidget {
  final Map<String, dynamic> fish;
  final VoidCallback onClose;
  const FishCaughtCard(this.fish, {super.key, required this.onClose});

  @override
  Widget build(BuildContext context) {
    final id = fish['id'] as String;
    final rarity = fish['rarity'] as String?;
    final weed = id == 'weed';
    final first = fish['first'] == true, record = fish['record'] == true;
    final size = (fish['size_cm'] as num?)?.toDouble() ?? 0;
    final got = (fish['got'] as num?)?.toInt() ?? 0;
    final left = (fish['left'] as num?)?.toInt();
    final count = (fish['count'] as num?)?.toInt();
    final edge = Rarity.color(rarity == 'common' ? 'junk' : rarity);
    return Material(
      color: Colors.transparent,
      child: Container(
        width: 286,
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
        decoration: ShapeDecoration(
          gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [SancColors.paper, SancColors.paperShade]),
          shape: BeveledRectangleBorder(borderRadius: BorderRadius.circular(10), side: BorderSide(color: rarity == 'legend' ? SancColors.gold : SancColors.wood, width: 1.6)),
          shadows: const [BoxShadow(color: Color(0x99000000), blurRadius: 30, offset: Offset(0, 12))],
        ),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text(weed ? '钓上来的是……' : (first ? '钓到了新的鱼' : '钓到了'), style: sancLabel(13, SancColors.wood, spacing: 4)),
          const SizedBox(height: 10),
          Stack(clipBehavior: Clip.none, alignment: Alignment.center, children: [
            Container(
              width: 168,
              height: 168,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: const RadialGradient(colors: [Color(0xFF5E8E99), SancColors.slate, SancColors.slateDeep], stops: [0, 0.7, 1]),
                border: Border.all(color: edge, width: 2.4),
              ),
              child: Center(child: ItemArt(id, size: 132)),
            ),
            if (first) const Positioned(right: -6, top: 0, child: _Seal('新', size: 34)),
            if (record) const Positioned(right: -6, top: 0, child: _Seal('冠', size: 34)),
          ]),
          const SizedBox(height: 12),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            Flexible(child: Text(fish['name'] as String, style: sancLabel(24, SancColors.ink, spacing: 3))),
            if (!weed) ...[
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                decoration: ShapeDecoration(color: SancColors.ink, shape: BeveledRectangleBorder(borderRadius: BorderRadius.circular(3))),
                child: Text(Rarity.name(rarity), style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: Rarity.color(rarity))),
              ),
            ],
          ]),
          if (!weed) ...[
            const SizedBox(height: 4),
            Text('长 ${size.toStringAsFixed(1)} 厘米${record ? ' · 个人新纪录' : ''}', style: sancLabel(14, record ? SancColors.vermilion : SancColors.wood, spacing: 1)),
          ],
          const SizedBox(height: 8),
          Text((fish['about'] as String?) ?? '', textAlign: TextAlign.center, style: const TextStyle(fontSize: 13.5, height: 1.55, color: SancColors.ink)),
          const SizedBox(height: 6),
          Text(
            [
              if (got > 0) '第一次钓到，得 $got 金币',
              if (count != null) '背包里有 $count ${weed ? '团' : '条'}',
              if (left != null) left > 0 ? '今天还能钓 $left 次' : '今天钓满了',
            ].join(' · '),
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 12, height: 1.5, color: Color(0xB32B2420)),
          ),
          const SizedBox(height: 14),
          LacquerButton(weed ? '收起来' : '收进鱼篓', onTap: onClose),
        ]),
      ),
    );
  }
}

// ───────── 钓鱼图鉴 ─────────

/// 钓鱼图鉴：每种鱼钓到过没有、钓过几条、最大纪录；没钓到的只有一个剪影和在哪儿能钓到。
Future<void> showFishBook(BuildContext context) => _sheet<void>(context, const FishBookPanel());

class FishBookPanel extends StatefulWidget {
  const FishBookPanel({super.key});

  @override
  State<FishBookPanel> createState() => _FishBookPanelState();
}

class _FishBookPanelState extends State<FishBookPanel> {
  static const _spotNames = {'sea': '湖里', 'pond': '池塘'};
  static const _when = {'silver': '清晨多', 'crab': '黄昏和夜里多', 'carp_gold': '下雨天才有', 'moon': '晴朗的夜里才有'};
  String? _error;

  @override
  void initState() {
    super.initState();
    if (store.online) {
      store.loadFishBook().then((_) {}, onError: (Object e) {
        if (mounted) setState(() => _error = '$e');
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: store,
      builder: (context, _) {
        final book = store.fishBookCache;
        if (book == null) {
          return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('钓鱼图鉴', style: _title),
            Padding(padding: const EdgeInsets.symmetric(vertical: 40), child: Center(child: Text(_error ?? (store.online ? '正在翻开图鉴……' : '连上网才能看图鉴'), style: _hint))),
          ]);
        }
        final fish = (book['fish'] as List).cast<Map>();
        return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
            const Text('钓鱼图鉴', style: _title),
            const SizedBox(width: 10),
            Padding(padding: const EdgeInsets.only(bottom: 3), child: Text('${book['kinds']} / ${book['total']}', style: sancLabel(14, SancColors.goldLit, spacing: 1))),
            const Spacer(),
            Padding(padding: const EdgeInsets.only(bottom: 3), child: Text('今天还能钓 ${book['left']} 次', style: _hint)),
          ]),
          const SizedBox(height: 12),
          Flexible(
            child: GridView.count(
              shrinkWrap: true,
              crossAxisCount: 3,
              mainAxisSpacing: 8,
              crossAxisSpacing: 8,
              childAspectRatio: 0.74,
              children: [for (final f in fish) _fishCell(f)],
            ),
          ),
        ]);
      },
    );
  }

  Widget _fishCell(Map f) {
    final caught = f['caught'] == true;
    final rarity = f['rarity'] as String?;
    final where = [for (final s in (f['spots'] as List? ?? const [])) _spotNames[s] ?? '$s'].join('、');
    final best = (f['best_cm'] as num?)?.toDouble();
    return Container(
      decoration: _box(caught ? Rarity.color(rarity) : const Color(0xFF6A5F54), fill: caught ? 0.08 : 0.03),
      padding: const EdgeInsets.fromLTRB(6, 6, 6, 6),
      child: Column(children: [
        Expanded(child: FittedBox(child: ItemArt(f['id'] as String, size: 64, shadow: !caught))),
        const SizedBox(height: 2),
        Text(caught ? f['name'] as String : '？？？', maxLines: 1, style: sancLabel(13.5, caught ? SancColors.paper : const Color(0x80F3E8CF), spacing: 1)),
        const SizedBox(height: 2),
        Text(Rarity.name(rarity), style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, color: Rarity.color(rarity).withValues(alpha: caught ? 1 : 0.6))),
        Text(
          caught ? '钓过 ${f['count']} 条${best == null ? '' : '\n最大 ${best.toStringAsFixed(1)} 厘米'}' : '$where${_when[f['id']] == null ? '' : '\n${_when[f['id']]}'}',
          maxLines: 2,
          textAlign: TextAlign.center,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontSize: 10.5, height: 1.35, color: Color(0xB3F3E8CF)),
        ),
      ]),
    );
  }
}

// ───────── 小动物册 ─────────

/// 小动物册：每只的亲密度、等级、最爱、里程碑进度和礼物。[pet] 给了编号就先展开那一只（排在最前面）。
Future<void> showPetBook(BuildContext context, {String? pet}) => _sheet<void>(context, PetBookPanel(pet: pet));

class PetBookPanel extends StatefulWidget {
  final String? pet;
  const PetBookPanel({super.key, this.pet});

  @override
  State<PetBookPanel> createState() => _PetBookPanelState();
}

class _PetBookPanelState extends State<PetBookPanel> {
  late String? _open = widget.pet;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (store.online) {
      store.loadPetBook().then((_) {}, onError: (Object e) {
        if (mounted) setState(() => _error = '$e');
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: store,
      builder: (context, _) {
        final book = store.petBookCache;
        if (book == null) {
          return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('小动物册', style: _title),
            Padding(padding: const EdgeInsets.symmetric(vertical: 40), child: Center(child: Text(_error ?? (store.online ? '正在翻开……' : '连上网才能看小动物册'), style: _hint))),
          ]);
        }
        final names = (book['names'] as Map?) ?? const {};
        final pets = (book['pets'] as List).cast<Map>().toList();
        if (widget.pet != null) {
          pets.sort((a, b) => (b['id'] == widget.pet ? 1 : 0) - (a['id'] == widget.pet ? 1 : 0));
        }
        return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('小动物册', style: _title),
          const SizedBox(height: 2),
          const Text('摸一摸、喂一喂，亲密度会涨。到了门槛，它会送你礼物。', style: _hint),
          const SizedBox(height: 10),
          Flexible(
            child: ListView.separated(
              shrinkWrap: true,
              padding: EdgeInsets.zero,
              itemCount: pets.length,
              separatorBuilder: (_, _) => const SizedBox(height: 8),
              itemBuilder: (context, i) => _petCard(pets[i], names),
            ),
          ),
        ]);
      },
    );
  }

  Widget _petCard(Map p, Map names) {
    final id = p['id'] as String;
    final open = _open == id;
    final aff = (p['affinity'] as num).toInt();
    final next = (p['next'] as num?)?.toInt();
    final milestones = (p['milestones'] as List).cast<Map>();
    final done = milestones.where((m) => m['done'] == true).length;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: () => setState(() => _open = open ? null : id),
      child: Container(
        decoration: _box(open ? SancColors.gold : SancColors.paper, fill: open ? 0.09 : 0.05),
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            CustomPaint(size: const Size.square(34), painter: _PetFacePainter(p['kind'] == 'cat', id.codeUnits.fold<int>(0, (a, b) => a + b))),
            const SizedBox(width: 10),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Text(p['name'] as String, style: sancLabel(16.5, SancColors.paper, spacing: 2)),
                  const SizedBox(width: 8),
                  Text(p['level_name'] as String, style: sancLabel(12, SancColors.goldLit, spacing: 1)),
                  const Spacer(),
                  Text(next == null ? '亲密度 $aff' : '亲密度 $aff / $next', style: _hint),
                ]),
                const SizedBox(height: 5),
                _Bar(next == null ? 1 : (aff / next).clamp(0.0, 1.0)),
              ]),
            ),
          ]),
          if (!open)
            Padding(
              padding: const EdgeInsets.only(top: 6, left: 44),
              child: Text(
                p['next_milestone'] == null ? '礼物都送过了（$done 份）' : '礼物 $done / ${milestones.length} · 下一份：亲密度到 ${p['next_milestone']}',
                style: _hint.copyWith(fontSize: 11.5),
              ),
            )
          else ..._petDetail(p, names, milestones),
        ]),
      ),
    );
  }

  List<Widget> _petDetail(Map p, Map names, List<Map> milestones) {
    final favs = (p['favorites'] as List).cast<String>();
    final known = (p['favorites_known'] as List).cast<String>();
    final daily = (p['daily'] as List).cast<Map>();
    Map? nextM;
    for (final m in milestones) {
      if (m['done'] != true) {
        nextM = m;
        break;
      }
    }
    Widget slot(String? id, String label, {String? rarity}) => SizedBox(
          width: 62,
          child: Column(children: [
            Container(
              width: 46,
              height: 46,
              alignment: Alignment.center,
              decoration: _box(id == null ? const Color(0xFF6A5F54) : Rarity.color(rarity ?? 'common')),
              child: id == null ? Text('？', style: sancLabel(20, const Color(0x80F3E8CF), spacing: 0)) : ItemArt(id, size: 38),
            ),
            const SizedBox(height: 3),
            Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11, color: Color(0xCCF3E8CF))),
          ]),
        );
    return [
      const SizedBox(height: 12),
      Text('最爱吃的', style: sancLabel(12.5, SancColors.rope, spacing: 2)),
      const SizedBox(height: 6),
      Row(children: [
        for (final f in favs) known.contains(f) ? slot(f, '${names[f] ?? f}') : slot(null, '还不知道'),
        if (known.length < favs.length) const Expanded(child: Text('喂到它爱吃的，它眼睛会亮，这里就记下来', style: _hint)),
      ]),
      const SizedBox(height: 12),
      Text('亲密度礼物', style: sancLabel(12.5, SancColors.rope, spacing: 2)),
      const SizedBox(height: 6),
      Wrap(spacing: 6, runSpacing: 6, children: [
        for (final m in milestones)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: ShapeDecoration(
              color: m['done'] == true ? SancColors.goldDeep : (identical(m, nextM) ? const Color(0x33C8452F) : Colors.transparent),
              shape: BeveledRectangleBorder(borderRadius: BorderRadius.circular(4), side: BorderSide(color: m['done'] == true || identical(m, nextM) ? SancColors.gold : const Color(0x59F3E8CF), width: 0.9)),
            ),
            child: Text('${m['at']}', style: sancLabel(12.5, m['done'] == true ? SancColors.ink : (identical(m, nextM) ? SancColors.goldLit : const Color(0x99F3E8CF)), spacing: 0.5)),
          ),
      ]),
      const SizedBox(height: 6),
      for (final m in milestones)
        if (m['done'] == true || identical(m, nextM))
          Padding(
            padding: const EdgeInsets.only(bottom: 2),
            child: Text(
              m['done'] == true ? '到 ${m['at']} 时送过：${m['what']}' : '下一份：亲密度到 ${m['at']}，送「${m['what']}」',
              style: m['done'] == true ? _hint : _body.copyWith(color: SancColors.goldLit),
            ),
          ),
      if (nextM == null) const Text('它能送的都送给你了。', style: _hint),
      const SizedBox(height: 12),
      Text('每天会叼来的', style: sancLabel(12.5, SancColors.rope, spacing: 2)),
      const SizedBox(height: 6),
      Row(children: [
        for (final d in daily) d['seen'] == true ? slot(d['id'] as String, d['name'] as String, rarity: d['rarity'] as String?) : slot(null, '没收到过'),
      ]),
      const SizedBox(height: 4),
      const Text('到「亲近」以后每天有机会叼一件来，越熟越可能是稀有的。攒够了能在商城换头像框。', style: _hint),
    ];
  }
}

/// 亲密度的进度条：一道细细的金线
class _Bar extends StatelessWidget {
  final double value;
  const _Bar(this.value);

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 4,
      decoration: BoxDecoration(color: const Color(0x33F3E8CF), borderRadius: BorderRadius.circular(2)),
      alignment: Alignment.centerLeft,
      child: FractionallySizedBox(
        widthFactor: value,
        child: Container(decoration: BoxDecoration(gradient: const LinearGradient(colors: [SancColors.goldDeep, SancColors.goldLit]), borderRadius: BorderRadius.circular(2))),
      ),
    );
  }
}

/// 一个小小的猫脸或狗脸：猫是尖耳朵加胡子，狗是垂耳朵加舌头。颜色按编号在几种毛色里取
class _PetFacePainter extends CustomPainter {
  final bool cat;
  final int seed;
  const _PetFacePainter(this.cat, this.seed);

  static const _furs = [Color(0xFFE9A862), Color(0xFFF3E8CF), Color(0xFFB98A5A), Color(0xFF8E8A86), Color(0xFFD9C3A0)];

  @override
  void paint(Canvas canvas, Size size) {
    canvas.translate(size.width / 2, size.height / 2);
    canvas.scale(size.width / 100);
    final fur = Paint()..color = _furs[seed.abs() % _furs.length];
    final ink = Paint()..color = SancColors.ink;
    if (cat) {
      for (final s in const [-1.0, 1.0]) {
        canvas.drawPath(Path()..moveTo(s * 36, -8)..lineTo(s * 34, -46)..lineTo(s * 8, -30)..close(), fur);
      }
      canvas.drawOval(const Rect.fromLTRB(-40, -34, 40, 38), fur);
      final w = Paint()
        ..color = SancColors.ink.withValues(alpha: 0.6)
        ..strokeWidth = 2;
      for (final s in const [-1.0, 1.0]) {
        canvas.drawLine(Offset(s * 14, 12), Offset(s * 44, 6), w);
        canvas.drawLine(Offset(s * 14, 16), Offset(s * 44, 20), w);
      }
    } else {
      canvas.drawOval(const Rect.fromLTRB(-36, -38, 36, 36), fur);
      final ear = Paint()..color = Color.lerp(fur.color, SancColors.wood, 0.55)!;
      for (final s in const [-1.0, 1.0]) {
        canvas.drawOval(Rect.fromCenter(center: Offset(s * 36, -8), width: 22, height: 44), ear);
      }
      canvas.drawOval(const Rect.fromLTRB(-7, 18, 7, 36), Paint()..color = const Color(0xFFE9828F));
    }
    canvas.drawCircle(const Offset(-15, -6), 5, ink);
    canvas.drawCircle(const Offset(15, -6), 5, ink);
    canvas.drawOval(const Rect.fromLTRB(-6, 6, 6, 14), ink);
  }

  @override
  bool shouldRepaint(_PetFacePainter old) => old.cat != cat || old.seed != seed;
}
