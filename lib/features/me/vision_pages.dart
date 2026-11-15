import 'package:flutter/material.dart';
import 'package:yuanjing_engine/yuanjing_engine.dart';

import '../../app/muse.dart';
import '../../app/skin.dart';
import '../../app/store.dart';
import '../wish/wish_category.dart';
import 'me_page.dart';

// ───────── 愿景板 ─────────

/// 愿景板：把想要的生活一张张贴上去。可以只写关键词，也可以配一张自己的图；排版是自动的。
class VisionPage extends StatefulWidget {
  const VisionPage({super.key});

  @override
  State<VisionPage> createState() => _VisionPageState();
}

class _VisionPageState extends State<VisionPage> with SingleTickerProviderStateMixin {
  /// 一道光慢慢扫过每一张，照片轻轻推近：让板子是活的
  late final _glow = AnimationController(vsync: this, duration: const Duration(seconds: 9))..repeat();
  int _seed = 0;

  static const _heights = [150.0, 205.0, 124.0, 178.0, 232.0];
  static const _ideas = ['跑车', '海边的房子', '环球旅行', '自由的时间', '健康的身体', '被爱着'];

  @override
  void dispose() {
    _glow.dispose();
    super.dispose();
  }

  void _add({String? text}) {
    final word = TextEditingController(text: text ?? '');
    var scene = 'life';
    String? photo;
    showSkinSheet<void>(context, tall: true, (context, s) {
      return StatefulBuilder(builder: (context, setState) {
        final image = store.photo(photo);
        return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('贴一张', style: s.title(22)),
          const SizedBox(height: 12),
          SField(controller: word, hint: '一个关键词，或一句话', mic: true),
          const SizedBox(height: 12),
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final c in wishCategories) SChip(c.name, on: scene == c.scene, onTap: () => setState(() => scene = c.scene)),
          ]),
          const SizedBox(height: 12),
          Row(children: [
            if (image != null)
              Padding(
                padding: const EdgeInsets.only(right: 12),
                child: ClipRRect(borderRadius: BorderRadius.circular(12), child: Image(image: image, width: 64, height: 64, fit: BoxFit.cover)),
              ),
            SButton(photo == null ? '配一张图' : '换一张', small: true, ghost: true, onTap: () async {
              try {
                final url = await store.pickAndUpload();
                if (url != null) setState(() => photo = url);
              } on ApiError catch (e) {
                if (context.mounted) toast(context, e.message);
              }
            }),
            const SizedBox(width: 10),
            Expanded(child: Text('不配图也可以，会用这一类的颜色做底。', style: s.hint(12.5))),
          ]),
          const SizedBox(height: 16),
          SButton('贴上去', expand: true, onTap: () async {
            if (word.text.trim().isEmpty && photo == null) return toast(context, '写个关键词，或者配一张图');
            try {
              await store.addVision(word.text.trim(), scene, photo);
              if (context.mounted) Navigator.of(context).pop();
            } on ApiError catch (e) {
              if (context.mounted) toast(context, e.message);
            }
          }),
        ]);
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    return SkinPage(
      pushed: true,
      title: '愿景板',
      subtitle: '每天看一眼想要的生活。贴上去的内容也会写进终点密码。',
      builder: (context, s) {
        final items = store.vision;
        // 两列瀑布：每张按顺序放进当前较矮的那一列
        final cols = [<Widget>[], <Widget>[]];
        final tall = [0.0, 0.0];
        for (final (i, v) in items.indexed) {
          final h = _heights[(i * 3 + _seed) % _heights.length];
          final c = tall[0] <= tall[1] ? 0 : 1;
          tall[c] += h + 10;
          cols[c].add(Padding(padding: const EdgeInsets.only(bottom: 10), child: _Tile(v, height: h, glow: _glow, index: i)));
        }
        return ListView(padding: const EdgeInsets.fromLTRB(22, 8, 22, 40), children: [
          Row(children: [
            SButton('贴一张', small: true, onTap: _add),
            const SizedBox(width: 8),
            if (items.length > 1) SButton('AI 重新排版', small: true, ghost: true, onTap: () => setState(() => _seed++)),
          ]),
          const SizedBox(height: 14),
          if (items.isEmpty) ...[
            Text('还空着。从这些开始，或者写你自己的：', style: s.hint(14)),
            const SizedBox(height: 10),
            Wrap(spacing: 8, runSpacing: 8, children: [for (final w in _ideas) SChip(w, onTap: () => _add(text: w))]),
          ] else
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(child: Column(children: cols[0])),
              const SizedBox(width: 10),
              Expanded(child: Column(children: cols[1])),
            ]),
          if (items.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8), child: Center(child: Text('长按一张可以取下来', style: s.hint(12)))),
          // 还没贴过的灵感一直留在下面，点一下就能接着贴
          if (items.isNotEmpty && _ideas.any((w) => !items.any((v) => v['text'] == w))) ...[
            const SizedBox(height: 18),
            Text('还可以贴这些：', style: s.hint(13)),
            const SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final w in _ideas)
                if (!items.any((v) => v['text'] == w)) SChip(w, onTap: () => _add(text: w)),
            ]),
          ],
        ]);
      },
    );
  }
}

class _Tile extends StatelessWidget {
  final Map<String, dynamic> v;
  final double height;
  final Animation<double> glow;
  final int index;
  const _Tile(this.v, {required this.height, required this.glow, required this.index});

  @override
  Widget build(BuildContext context) {
    final cat = categoryOf(v['scene'] as String);
    final image = store.photo(v['photo'] as String?);
    final has = image != null;
    final text = v['text'] as String;
    return GestureDetector(
      onLongPress: () {
        YuanjingHaptics.play('tick');
        store.removeVision(v).then((_) {
          if (context.mounted) toast(context, '取下来了');
        }).catchError((e) {
          if (context.mounted) toast(context, '$e');
        });
      },
      child: ClipRRect(
        borderRadius: BorderRadius.circular(18),
        child: SizedBox(
          height: height,
          width: double.infinity,
          child: AnimatedBuilder(
            animation: glow,
            builder: (context, child) {
              // 每张错开一点，光从左上扫到右下
              final t = (glow.value + index * 0.17) % 1;
              return Stack(fit: StackFit.expand, children: [
                if (has)
                  Transform.scale(scale: 1.04 + 0.05 * (0.5 - (t - 0.5).abs()) * 2, child: Image(image: image, fit: BoxFit.cover))
                else
                  DecoratedBox(decoration: BoxDecoration(gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [cat.light, cat.deep]))),
                DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment(-1.6 + 3.2 * t, -1),
                      end: Alignment(-0.6 + 3.2 * t, 1),
                      colors: [Colors.white.withValues(alpha: 0), Colors.white.withValues(alpha: has ? 0.16 : 0.34), Colors.white.withValues(alpha: 0)],
                    ),
                  ),
                ),
                child!,
              ]);
            },
            child: Stack(fit: StackFit.expand, children: [
              if (has)
                const DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0x00000000), Color(0x99000000)], stops: [0.45, 1]),
                  ),
                ),
              Padding(
                padding: const EdgeInsets.all(14),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.end, children: [
                  Text(cat.name, style: TextStyle(fontSize: 11.5, letterSpacing: 2, color: has ? Colors.white70 : const Color(0x992A1708))),
                  if (text.isNotEmpty)
                    Text(text,
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontFamily: displayFont, fontSize: 19, height: 1.35, fontWeight: FontWeight.w700, color: has ? Colors.white : const Color(0xFF2A1708))),
                ]),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}

// ───────── 终点密码 ─────────

/// 终点密码：所有终极理想的总览，一个方面一段话。会跟着心愿和愿景板一起长，AI 生成的肯定语和身份卡都从这里取材。
class DestinyPage extends StatefulWidget {
  const DestinyPage({super.key});

  @override
  State<DestinyPage> createState() => _DestinyPageState();
}

class _DestinyPageState extends State<DestinyPage> {
  late final _fields = {
    for (final c in wishCategories) c.scene: TextEditingController(text: store.destiny[c.scene] ?? store.drafts['destiny_${c.scene}'] ?? ''),
  };

  @override
  void initState() {
    super.initState();
    for (final e in _fields.entries) {
      e.value.addListener(() => _keep(e.key, e.value.text));
    }
  }

  /// 边写边存：写了什么就是什么，不用点保存（停笔一秒后发到服务器）
  void _keep(String scene, String text) => store.setDestiny(scene, text);

  /// 把这一类的心愿和愿景板关键词整理成一段，接在已有内容后面
  Future<bool> _gather(String scene) async {
    String? draft;
    try {
      draft = (await store.api.get('/ai/destiny/$scene'))['text'] as String?;
    } on ApiError {
      draft = destinyDraft(scene);
    }
    if (draft == null || !mounted) return false;
    final c = _fields[scene]!;
    if (c.text.contains(draft)) return true;
    final text = c.text.trim().isEmpty ? draft : '${c.text.trim()}\n$draft';
    c.value = TextEditingValue(text: text, selection: TextSelection.collapsed(offset: text.length));
    return true;
  }

  @override
  void dispose() {
    for (final c in _fields.values) {
      c.dispose();
    }
    store.flushDestiny();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SkinPage(
      pushed: true,
      title: '终点密码',
      subtitle: '你终极的理想状态，一个方面一段话。边写边存。',
      builder: (context, s) {
        final t = store.destinyTs == 0 ? null : DateTime.fromMillisecondsSinceEpoch(store.destinyTs);
        return ListView(padding: const EdgeInsets.fromLTRB(22, 8, 22, 40), children: [
          Row(children: [
            SButton('从心愿和愿景板整理', small: true, onTap: () async {
              var n = 0;
              for (final c in wishCategories) {
                if (await _gather(c.scene)) n++;
              }
              if (!context.mounted) return;
              toast(context, n == 0 ? '还没有可以整理的心愿或愿景' : '整理了 $n 个方面，可以接着改');
            }),
            const Spacer(),
            if (t != null) Text('更新于 ${t.month}月${t.day}日', style: s.hint(12)),
          ]),
          const SizedBox(height: 14),
          for (final c in wishCategories)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: SCard(
                padding: const EdgeInsets.fromLTRB(16, 12, 10, 8),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    Container(width: 9, height: 9, decoration: BoxDecoration(shape: BoxShape.circle, gradient: LinearGradient(colors: [c.light, c.deep]))),
                    const SizedBox(width: 8),
                    Text(c.name, style: s.title(17)),
                    const Spacer(),
                    GestureDetector(
                      onTap: () async {
                        if (!await _gather(c.scene) && context.mounted) toast(context, '「${c.name}」还没有心愿或愿景');
                      },
                      child: Padding(padding: const EdgeInsets.all(6), child: Text('整理', style: s.hint(12.5))),
                    ),
                    MicButton(controller: _fields[c.scene]!),
                  ]),
                  TextField(
                    controller: _fields[c.scene],
                    minLines: 2,
                    maxLines: 6,
                    cursorColor: s.deep,
                    style: s.body(15),
                    decoration: InputDecoration(
                        border: InputBorder.none, isDense: true, hintText: '在${c.name}上，最终的我是什么样子？', hintStyle: s.hint(14.5), contentPadding: const EdgeInsets.symmetric(vertical: 8)),
                  ),
                ]),
              ),
            ),
        ]);
      },
    );
  }
}

// ───────── 愿望汇总与分析 ─────────

/// 愿望汇总：所有许过的心愿按日、周、月归档；上面是愿景分析和内在需求的解读。
class WishSummaryPage extends StatefulWidget {
  const WishSummaryPage({super.key});

  @override
  State<WishSummaryPage> createState() => _WishSummaryPageState();
}

class _WishSummaryPageState extends State<WishSummaryPage> {
  String _by = 'day';

  /// 服务器给的分析（配了大模型时是模型写的）；拿不到就用本机统计
  WishReport? _server;

  @override
  void initState() {
    super.initState();
    store.api.get('/ai/analysis').then((r) {
      final m = r['report'];
      if (m == null || !mounted) return;
      setState(() => _server = WishReport(
            m['total'] as int,
            [for (final c in m['counts'] as List) (categoryOf(c[0] as String), c[1] as int)],
            m['need'] as String,
            m['advice'] as String? ?? '',
            (m['repeats'] as List).cast<String>(),
            m['trend'] as String,
          ));
    }).catchError((_) {});
  }

  String _group(DateTime d) {
    switch (_by) {
      case 'day':
        return '${d.month}月${d.day}日';
      case 'week':
        final monday = d.subtract(Duration(days: d.weekday - 1));
        final sunday = monday.add(const Duration(days: 6));
        return '${monday.month}月${monday.day}日 – ${sunday.month}月${sunday.day}日';
      default:
        return '${d.year}年${d.month}月';
    }
  }

  @override
  Widget build(BuildContext context) {
    return SkinPage(
      pushed: true,
      title: '愿望汇总',
      builder: (context, s) {
        final report = _server ?? analyzeWishes(store.wishes);
        final groups = <String, List<Map<String, dynamic>>>{};
        for (final w in store.wishes) {
          groups.putIfAbsent(_group(DateTime.fromMillisecondsSinceEpoch(w['ts'] as int)), () => []).add(w);
        }
        return ListView(padding: const EdgeInsets.fromLTRB(22, 8, 22, 40), children: [
          if (report == null)
            Padding(padding: const EdgeInsets.only(top: 40), child: Center(child: Text('还没有心愿。去许愿页写下第一个。', style: s.hint(14.5))))
          else ...[
            SCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('愿景分析', style: s.title(19)),
                const SizedBox(height: 4),
                Text(report.trend, style: s.body(14.5)),
                const SizedBox(height: 14),
                for (final (c, n) in report.counts.take(4))
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Row(children: [
                      SizedBox(width: 44, child: Text(c.name, style: s.body(13.5))),
                      Expanded(
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(4),
                          child: Stack(children: [
                            Container(height: 8, color: s.line),
                            FractionallySizedBox(
                              widthFactor: n / report.counts.first.$2,
                              child: Container(height: 8, decoration: BoxDecoration(gradient: LinearGradient(colors: [c.light, c.deep]))),
                            ),
                          ]),
                        ),
                      ),
                      SizedBox(width: 30, child: Text('$n', textAlign: TextAlign.right, style: s.hint(13))),
                    ]),
                  ),
                const SizedBox(height: 8),
                Text('你真正想要的', style: s.hint(12.5)),
                const SizedBox(height: 2),
                Text(report.need, style: s.title(17)),
                const SizedBox(height: 10),
                if (store.member) ...[
                  Text(report.advice, style: s.body(14.5)),
                  if (report.repeats.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Text('你反复提到的', style: s.hint(12.5)),
                    const SizedBox(height: 6),
                    Wrap(spacing: 8, runSpacing: 8, children: [for (final w in report.repeats) SChip(w)]),
                  ],
                ] else
                  GestureDetector(
                    onTap: () => showMember(context),
                    child: Row(children: [
                      const MemberTag(),
                      const SizedBox(width: 8),
                      Expanded(child: Text('会员可以看到更细的解读：给你的建议，和你反复提到的事。', style: s.hint(13))),
                    ]),
                  ),
                const SizedBox(height: 10),
                Text('这份分析按分类和用词统计；服务器配了大模型时由模型来写。', style: s.hint(11.5)),
              ]),
            ),
            const SizedBox(height: 16),
            Row(children: [
              for (final (k, label) in [('day', '按日'), ('week', '按周'), ('month', '按月')])
                Padding(padding: const EdgeInsets.only(right: 8), child: SChip(label, on: _by == k, onTap: () => setState(() => _by = k))),
              const Spacer(),
              Text('共 ${report.total} 个', style: s.hint(13)),
            ]),
            const SizedBox(height: 10),
            for (final g in groups.entries) ...[
              Padding(
                padding: const EdgeInsets.only(top: 8, bottom: 6),
                child: Row(children: [Text(g.key, style: s.title(15.5)), const SizedBox(width: 8), Text('${g.value.length} 个', style: s.hint(12.5))]),
              ),
              for (final w in g.value)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Container(
                      margin: const EdgeInsets.only(top: 3),
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 1.5),
                      decoration: BoxDecoration(borderRadius: BorderRadius.circular(99), border: Border.all(color: s.line)),
                      child: Text(categoryOf(w['scene'] as String).name, style: s.hint(11.5)),
                    ),
                    const SizedBox(width: 10),
                    Expanded(child: Text(w['text'] as String, style: s.body(15))),
                  ]),
                ),
            ],
          ],
        ]);
      },
    );
  }
}
