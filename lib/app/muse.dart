import 'dart:math';

import '../features/wish/wish_category.dart';
import 'store.dart';

/// 需求里写「AI 生成」的那些内容，现在都由这里的本地规则和模板产出：没有接大模型，不联网。
///
/// 好处是不会说错话、不花钱、离线可用；坏处是不会针对具体内容回应，换几次就会看到重复。
/// 接模型时把这个文件里的函数一个个换成请求即可，调用方不用改。函数名对应需求里的功能：
/// 愿景分析、朋友圈文案、感恩日记、AI 夸夸、肯定语、终点密码、身份卡。

final _rand = Random();
T _pick<T>(List<T> list) => list[_rand.nextInt(list.length)];

WishCategory categoryOf(String scene) => wishCategories.firstWhere((c) => c.scene == scene, orElse: () => wishCategories.first);

/// 每个分类背后常见的内在需求，和一句温和的建议
const _needs = <String, (String, String)>{
  'wealth': ('安全感和选择的自由', '你要的不只是数字，是不必为钱委屈自己的底气。先把「我值得」放在「我需要」前面。'),
  'career': ('被看见和自我实现', '你想确认自己的努力有分量。不妨把大目标拆成这周就能迈出的一步。'),
  'looks': ('自我接纳和被喜欢', '你想更喜欢镜子里的自己。好看从放松开始，对自己说话时先温柔一点。'),
  'health': ('安稳和对身体的掌控', '你想和身体重新站在一起。它一直在努力保护你，给它一点休息。'),
  'mood': ('平静和情绪的出口', '你想要心里安静下来。情绪不是要解决的问题，是可以经过的天气。'),
  'life': ('归属感和生活的质感', '你想把日子过成喜欢的样子。先在今天安排一件小小的、只为自己的事。'),
  'pet': ('陪伴和无条件的爱', '你很会爱。你给毛孩子的那份耐心，也值得分一点给自己。'),
};

/// 愿景分析的结果
class WishReport {
  final int total;

  /// 各分类的次数，从多到少
  final List<(WishCategory, int)> counts;

  /// 最常出现的分类背后的需求
  final String need;
  final String advice;

  /// 反复出现的词（执念点）
  final List<String> repeats;

  /// 目标倾向：一句话
  final String trend;

  const WishReport(this.total, this.counts, this.need, this.advice, this.repeats, this.trend);
}

const _stop = ['希望', '可以', '能够', '一个', '自己', '今天', '每天', '我想', '想要', '我要', '越来', '来越', '顺利', '一切'];

/// 愿景分析：数各分类的次数，找反复出现的词，给出内在需求的解读。心愿少于一条时返回 null。
WishReport? analyzeWishes(List<Map<String, dynamic>> wishes) {
  if (wishes.isEmpty) return null;
  final by = <String, int>{};
  for (final w in wishes) {
    by[w['scene'] as String] = (by[w['scene']] ?? 0) + 1;
  }
  final counts = [for (final e in by.entries) (categoryOf(e.key), e.value)]..sort((a, b) => b.$2.compareTo(a.$2));
  final top = counts.first.$1;
  // 两个字的词里出现两次以上的，当作反复惦记的事
  final words = <String, int>{};
  for (final w in wishes) {
    final t = (w['text'] as String).replaceAll(RegExp(r'[^一-鿿]'), '');
    final seen = <String>{};
    for (var i = 0; i + 2 <= t.length; i++) {
      final g = t.substring(i, i + 2);
      if (_stop.contains(g) || !seen.add(g)) continue;
      words[g] = (words[g] ?? 0) + 1;
    }
  }
  final repeats = (words.entries.where((e) => e.value >= 2).toList()..sort((a, b) => b.value.compareTo(a.value))).take(5).map((e) => e.key).toList();
  final share = counts.first.$2 / wishes.length;
  final trend = counts.length == 1 || share >= 0.6
      ? '你最近的心思很集中，几乎都放在「${top.name}」上。聚焦是显化的开始。'
      : '你的心愿分布在「${counts.take(3).map((c) => c.$1.name).join('、')}」几个方面，生活的各个面都在被你照顾。';
  final n = _needs[top.scene]!;
  return WishReport(wishes.length, counts, n.$1, n.$2, repeats, trend);
}

/// 朋友圈文案：从最近的心愿和分类里取材
String momentCopy() {
  final w = store.wishes.isEmpty ? null : store.wishes.first;
  final cat = w == null ? null : categoryOf(w['scene'] as String);
  return _pick([
    if (cat != null) '今天给「${cat.name}」许了一个愿。写下来的那一刻，心里就亮了一点。',
    if (cat != null) '把想要的说出口，是我今天做得最勇敢的事。关于${cat.name}，我已经在路上了。',
    '今天的我，比昨天更相信自己一点点。',
    '慢慢来，比较快。把今天过好，就是在靠近想要的生活。',
    '抬头看了会儿天，觉得一切都来得及。',
    '给自己的小小记录：今天也有好好吃饭、好好呼吸、好好喜欢自己。',
  ]);
}

/// 感恩日记：三件小事的格式
String diaryCopy() {
  final a = ['早上醒来时照进来的光', '一杯刚好的热水', '路上遇到的一只小猫', '朋友发来的一句「在吗」', '按时吃上的一顿饭', '自己没有放弃的那一下'];
  final b = ['身体一直在好好工作', '有一个可以安心待着的地方', '今天有人对我笑了', '把一件拖了很久的事做完了', '还有想要去的地方', '我愿意对自己温柔'];
  final c = ['谢谢今天的自己。', '这些小事，就是生活在爱我。', '我拥有的，比我以为的多。', '明天也请多多关照。'];
  final x = _pick(a);
  var y = _pick(a);
  while (y == x) {
    y = _pick(a);
  }
  return '今天想谢谢三件事：\n一，$x。\n二，$y。\n三，${_pick(b)}。\n${_pick(c)}';
}

/// AI 夸夸：只夸，不评价
String praiseFor(String text) {
  if (text.contains('谢') || text.contains('感恩')) return _pick(['会感恩的人，日子会越过越亮。', '能看见这些小事，你的心真的很软。', '读完觉得被你的温柔照到了。']);
  if (text.contains('愿') || text.contains('想')) return _pick(['敢把想要的说出来，已经很了不起。', '这个愿望听起来就会实现。', '宇宙收到了，我也替你开心。']);
  return _pick(['你认真生活的样子，真的在发光。', '今天的你，值得一朵小红花。', '看到你这样，我也想对自己好一点。', '你比自己以为的更好。', '这份心情很珍贵，谢谢你分享。']);
}

/// 给别人夸夸时可以直接点的几句
const praisePresets = ['你真的在发光', '替你开心', '会实现的', '你值得这一切', '抱抱，你很棒', '被你治愈了'];

/// 发到广场的内容要是正向的：出现这些词时提醒改一改
const _negative = ['去死', '垃圾', '废物', '恶心', '讨厌你', '滚', '诅咒', '报复', '活该', '傻逼', '贱'];
bool isPositive(String text) => !_negative.any(text.contains);

/// 各分类的肯定语模板
const _affirm = <String, List<String>>{
  'wealth': ['我值得拥有丰盛。', '金钱以轻松的方式流向我。', '我的价值，一直在增长。'],
  'career': ['我清楚自己要去哪里。', '我的努力，正在被看见。', '机会喜欢准备好的我。'],
  'looks': ['我喜欢镜子里的自己。', '我由内而外地发着光。', '我本来的样子，就很美。'],
  'health': ['我的身体知道如何修复自己。', '每一次呼吸，都在给我力量。', '我温柔地照顾自己。'],
  'mood': ['我允许情绪来，也允许它走。', '我的心，越来越安定。', '今天，我选择平静。'],
  'life': ['我正在过自己选择的生活。', '美好的事，正在向我走来。', '我值得被生活温柔对待。'],
  'pet': ['我的毛孩子健康、快乐、被爱着。', '我们陪着彼此，一天比一天好。'],
};

/// 会员的「AI 生成肯定语」：综合终点密码、愿景板和最近的心愿。[scenes] 为空表示综合全部。
List<String> affirmationsFor(Set<String> scenes) {
  final want = scenes.isEmpty
      ? {...store.destiny.keys, ...store.wishes.take(8).map((w) => w['scene'] as String), ...store.vision.map((v) => v['scene'] as String)}
      : scenes;
  final use = want.isEmpty ? {'mood', 'life'} : want;
  final out = <String>[];
  for (final c in wishCategories) {
    if (!use.contains(c.scene)) continue;
    final pool = [..._affirm[c.scene]!]..shuffle(_rand);
    out.addAll(pool.take(scenes.length == 1 ? 3 : 2));
    // 终点密码里写了这一类的，把它也变成一句「我已经」
    final d = store.destiny[c.scene];
    if (d != null && d.trim().isNotEmpty) out.add('我正在成为这样的人：${d.trim().split(RegExp(r'[。\n]')).first}。');
  }
  out.add('我已经走在路上了。');
  return out;
}

/// 终点密码的自动积累：把这一类的心愿和愿景板关键词合成一段话。没有素材返回 null。
String? destinyDraft(String scene) {
  final wishes = store.wishes.where((w) => w['scene'] == scene).map((w) => (w['text'] as String).trim()).where((t) => t.isNotEmpty).toList();
  final keys = store.vision.where((v) => v['scene'] == scene).map((v) => (v['text'] as String).trim()).where((t) => t.isNotEmpty).toList();
  if (wishes.isEmpty && keys.isEmpty) return null;
  final parts = <String>[];
  if (keys.isNotEmpty) parts.add('我的生活里有${keys.take(4).join('、')}');
  for (final w in wishes.take(3)) {
    parts.add(w.replaceAll(RegExp(r'^(我)?(希望|想要|想|要|愿)'), '').replaceAll(RegExp(r'[。！!]$'), ''));
  }
  return '${parts.join('；')}。';
}

/// 终点身份卡：一个称号加一句话
(String, String) identityCard() {
  final report = analyzeWishes(store.wishes);
  final scene = report?.counts.first.$1.scene ?? (store.destiny.keys.isEmpty ? 'life' : store.destiny.keys.first);
  const titles = {
    'wealth': ('从容的丰盛者', '钱为我工作，我为热爱生活。'),
    'career': ('走在自己节奏里的人', '我被看见，也被需要。'),
    'looks': ('由内而外发光的人', '我喜欢镜子里的自己。'),
    'health': ('被身体好好爱着的人', '我睡得安稳，醒来有力。'),
    'mood': ('心里有一片静湖的人', '风来了，我也在。'),
    'life': ('把日子过成喜欢样子的人', '我过着自己选择的生活。'),
    'pet': ('被毛孩子选中的人', '我们陪着彼此，慢慢变好。'),
  };
  return titles[scene]!;
}
