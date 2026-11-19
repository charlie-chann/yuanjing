import 'package:flutter/painting.dart';

/// 一种卡点：预设标签、识别用的关键词，和解读的四段话。
///
/// 解读现在是本地规则（按标签和关键词匹配），没有接大模型。四段的结构和需求里定的一致：
/// 共情承接、看见卡点、释放引导、肯定语收束。接上模型后只需要替换 [readSticking]。
class Sticking {
  /// 也是肯定语语音的文件名：`assets/voice/affirm_<key>_1.m4a`
  final String key;
  final String name;
  final List<String> emotions;
  final String empathy;
  final String belief;
  final String guide;

  /// 要和 tools/tts/generate_guides.py 里 AFFIRM 的文字一致，语音念的就是这一句
  final String affirm;
  final List<String> words;

  const Sticking({
    required this.key,
    required this.name,
    required this.emotions,
    required this.empathy,
    required this.belief,
    required this.guide,
    required this.affirm,
    required this.words,
  });
}

const stickings = [
  Sticking(
    key: 'wronged',
    name: '委屈',
    emotions: ['委屈', '愤怒', '无力'],
    empathy: '我听见你的委屈。被针对、被否定真的很难受，你会愤怒、会不安，这很正常。',
    belief: '此刻困住你的，不是这件事本身，而是心里那句话：我容易被伤害，我改变不了别人对我的态度。',
    guide: '允许这份委屈流过你，不必抓住它。别人的态度只是他们的投影，不是你的真相。',
    affirm: '我稳稳地守住自己的边界，我值得被尊重，我不再被他人的行为定义。',
    words: ['委屈', '欺负', '针对', '冤枉', '误会', '被骂', '骂了', '不公平', '凭什么', '受气', '冤'],
  ),
  Sticking(
    key: 'anger',
    name: '愤怒',
    emotions: ['愤怒', '憋闷', '不甘'],
    empathy: '这股火是真的。被冒犯、被越界的时候，愤怒是在替你说：这样不行。',
    belief: '困住你的是这句话：我只有发火，才会被当回事。',
    guide: '让这团热从胸口慢慢散开。你不需要压住它，也不需要被它带着走。',
    affirm: '我可以平静地表达界限。我的力量不需要靠怒火来证明。',
    words: ['生气', '愤怒', '火大', '气死', '讨厌', '恨', '烦死', '受不了', '恶心', '凭什么'],
  ),
  Sticking(
    key: 'anxiety',
    name: '焦虑',
    emotions: ['焦虑', '不安', '紧绷'],
    empathy: '脑子停不下来的感觉很累。你一直在替还没发生的事提前担心。',
    belief: '困住你的是这句话：只要我没想好所有可能，坏事就会发生。',
    guide: '把注意力放回这一口呼吸。还没发生的事，先让它待在明天。',
    affirm: '此刻我是安全的。我一步一步来，事情会在该清楚的时候清楚。',
    words: ['焦虑', '担心', '紧张', '睡不着', '失眠', '慌', '不安', '怎么办', '来不及', '害怕', '心慌'],
  ),
  Sticking(
    key: 'inferior',
    name: '自卑',
    emotions: ['自卑', '羞怯', '失落'],
    empathy: '总觉得自己不够好，是很孤单的感觉。你已经对自己严格太久了。',
    belief: '困住你的是这句话：我要先变得足够好，才配被喜欢。',
    guide: '把那把一直量自己的尺子放下来。你不需要先达标，才被允许存在。',
    affirm: '我本来的样子就值得被爱。我允许自己被看见。',
    words: ['自卑', '不够好', '不如', '比不上', '配不上', '丑', '胖', '差劲', '没用', '不配', '比别人'],
  ),
  Sticking(
    key: 'failure',
    name: '担心失败',
    emotions: ['害怕', '犹豫', '压力'],
    empathy: '越在乎，越怕搞砸。你的害怕，是因为这件事对你真的重要。',
    belief: '困住你的是这句话：一旦失败，就证明我不行。',
    guide: '把结果先交出去。你只需要迈出眼前这一步，剩下的路会自己显出来。',
    affirm: '我允许自己尝试，也允许自己慢慢来。每一步都在把我带向要去的地方。',
    words: ['失败', '搞砸', '考试', '面试', '做不到', '不行', '怕', '万一', '完蛋', '输', '落榜', '被拒'],
  ),
  Sticking(
    key: 'judged',
    name: '害怕被评价',
    emotions: ['紧张', '在意', '拘束'],
    empathy: '被人盯着看、被人议论，会让人缩起来。你只是想安全地做自己。',
    belief: '困住你的是这句话：别人怎么看我，决定了我是谁。',
    guide: '那些目光和声音，让它们从你身边经过。它们是别人的，不必住进你心里。',
    affirm: '我由我自己定义。我可以自在地做自己，不需要所有人点头。',
    words: ['评价', '看法', '眼光', '议论', '嘲笑', '笑话', '丢人', '尴尬', '别人怎么看', '说闲话', '背后说'],
  ),
  Sticking(
    key: 'relation',
    name: '关系受伤',
    emotions: ['难过', '失望', '孤单'],
    empathy: '被在乎的人伤到，是最疼的。你的难过，说明你认真付出过。',
    belief: '困住你的是这句话：我不值得被好好对待。',
    guide: '把那份等不到回应的期待，轻轻松开。它不是你的错，也不该由你一个人扛。',
    affirm: '我值得被温柔对待。我向健康、安稳的关系敞开。',
    words: ['分手', '吵架', '冷战', '背叛', '离开', '不理', '失恋', '前任', '朋友', '家人', '父母', '老公', '老婆', '男朋友', '女朋友', '孤单', '伤心', '失望'],
  ),
  Sticking(
    key: 'overload',
    name: '压力过载',
    emotions: ['疲惫', '压力', '紧绷'],
    empathy: '你已经撑了很久。累不是软弱，是身体在提醒你，该歇一会儿了。',
    belief: '困住你的是这句话：我一停下来，一切就会垮掉。',
    guide: '把肩上的东西一件一件放下来。此刻什么都不用做，世界不会因此停转。',
    affirm: '我可以休息。我做得已经足够，我允许自己被支持。',
    words: ['压力', '累', '加班', '撑不住', '崩溃', '喘不过气', '忙', '熬夜', '好多事', '做不完', '扛', '透支'],
  ),
];

/// 一次解读的结果。
class ReleaseReading {
  final Sticking sticking;

  /// 表层情绪，最多三个
  final List<String> emotions;

  /// 情绪比较重，推荐深度释放
  final bool deep;

  /// 大模型针对用户写的具体事情写的共情和深层信念；没有时用 [sticking] 里写好的
  final String? _empathy;
  final String? _belief;

  const ReleaseReading(this.sticking, this.emotions, this.deep, [this._empathy, this._belief]);

  String get empathy => _empathy ?? sticking.empathy;
  String get belief => _belief ?? sticking.belief;
}

const _intense = ['总是', '永远', '一直', '每次', '受不了', '崩溃', '撑不住', '特别', '非常', '真的很', '太', '好累', '绝望'];

/// 这些说法出现时不进入仪式，先给出求助信息。
const _crisis = ['不想活', '想死', '自杀', '轻生', '结束生命', '活不下去', '伤害自己', '自残', '了结'];

bool needsSupport(String text) => _crisis.any(text.contains);

/// 按选中的标签和文字里的关键词找出最贴近的卡点。什么都没有时返回 null。
ReleaseReading? readSticking(String text, Set<String> picked) {
  if (text.trim().isEmpty && picked.isEmpty) return null;
  final scores = <Sticking, int>{};
  for (final s in stickings) {
    var score = picked.contains(s.key) ? 3 : 0;
    for (final w in s.words) {
      if (text.contains(w)) score += 1;
    }
    scores[s] = score;
  }
  final ranked = stickings.toList()..sort((a, b) => scores[b]!.compareTo(scores[a]!));
  // 只写了字、又一个词都没对上：按「压力过载」接住，它的话最不容易说错
  final top = scores[ranked.first]! > 0 ? ranked.first : stickings.last;
  final emotions = <String>[...top.emotions];
  final second = ranked[1];
  if (second != top && scores[second]! > 0) {
    final extra = second.emotions.where((e) => !emotions.contains(e)).firstOrNull;
    if (extra != null) emotions.insert(1, extra);
  }
  final weight = _intense.where(text.contains).length + picked.length + (text.length > 60 ? 1 : 0);
  return ReleaseReading(top, emotions.take(3).toList(), weight >= 3);
}

/// 一种释放方式，对应原生舞台里的一场戏和一套皮肤。
class ReleaseStyle {
  /// 原生场景名，也是引导语语音的前缀：`assets/voice/<scene>_<1..4>.m4a`
  final String scene;

  /// 环境音名字：`assets/audio/amb_<bed>.m4a`
  final String bed;
  final String name;
  final String skin;

  /// 开始按钮上的字
  final String action;

  /// 四句引导语，要和 tools/tts/generate_guides.py 里 RELEASE 的文字一致
  final List<String> lines;

  /// 后三句各在仪式进度的哪里出现，和画面里的节点对齐
  final List<double> at;

  /// 写着烦恼的纸条要飞到画面的哪里（纸船、吊篮、锁链、坩埚、贝壳）
  final Alignment vessel;

  /// 这一场的解压小游戏：按钮上的名字、怎么玩的一句提示、攒满时的一句话。
  /// 画面和规则在原生层（`StageView.swift` 的 stepGame、着色器里各场的 game 分支）：
  /// 点得越快能量越高，能量推着进度走，攒满放一段奖励动画。
  final String play;
  final String playHint;
  final String playWin;

  /// 这个游戏是画圈搅动的（魔药），其余的是点
  final bool stir;

  /// 深度释放时画面的长度系数。天使之箭的高潮来得早，后面是留白，放短一点
  final double pace;
  final Color light;
  final Color deep;

  const ReleaseStyle({
    required this.scene,
    required this.bed,
    required this.name,
    required this.skin,
    required this.action,
    required this.lines,
    required this.at,
    required this.vessel,
    required this.play,
    required this.playHint,
    required this.playWin,
    this.stir = false,
    this.pace = 1,
    required this.light,
    required this.deep,
  });
}

const releaseStyles = [
  ReleaseStyle(
    scene: 'release_pool',
    bed: 'rel_pool',
    name: '纸船流水',
    skin: '金币许愿',
    action: '放开纸船',
    lines: ['把烦恼放进这只纸船。', '让这些不属于你的沉重，随着水流慢慢离开。', '你不需要抓住它们，只需要允许它们流过。', '水面亮起来了，它已经走远。'],
    at: [0.14, 0.45, 0.86],
    vessel: Alignment(0, 0.12),
    play: '拨水送船',
    playHint: '轻点水面，送纸船远行\n点得越快，它漂得越远',
    playWin: '它乘着金色的光，走远了',
    light: Color(0xFFFFE7A8),
    deep: Color(0xFFE2A93A),
  ),
  ReleaseStyle(
    scene: 'release_balloon',
    bed: 'rel_balloon',
    name: '热气球',
    skin: '梦幻渐变',
    action: '放飞热气球',
    lines: ['把压力装进热气球的篮子里。', '把压力交给天空，把沉重交给风。', '你不需要一直背着它们，允许自己轻一点。', '它越飞越高，已经看不见了。'],
    at: [0.16, 0.48, 0.88],
    vessel: Alignment(0, 0.72),
    play: '给气球打气',
    playHint: '轻点屏幕，为热气球打气\n点得越快，火越旺、飞得越高',
    playWin: '它飞出云层了',
    light: Color(0xFFFFD9E6),
    deep: Color(0xFFB8A2F2),
  ),
  ReleaseStyle(
    scene: 'release_arrow',
    bed: 'rel_arrow',
    name: '天使之箭',
    skin: '天使祝福',
    action: '射出天使之箭',
    lines: ['那些束缚你的，此刻显出了形状。', '不属于你的束缚，在此刻被温柔切断。', '你从旧的限制中解脱。', '回到安全、完整、平静的自己。'],
    at: [0.14, 0.45, 0.78],
    vessel: Alignment(0, 0.16),
    play: '点亮羽翼',
    playHint: '轻点屏幕，把光注进锁链\n点得越快，翅膀越亮',
    playWin: '锁链断开了',
    pace: 0.75,
    light: Color(0xFFFFF6DC),
    deep: Color(0xFFE6C36A),
  ),
  ReleaseStyle(
    scene: 'release_potion',
    bed: 'rel_potion',
    name: '魔药蒸发',
    skin: '魔法巫女',
    action: '倒入魔药',
    lines: ['把执念交给魔药，把情绪交给转化。', '黑色的泡泡沉进去，颜色开始变了。', '那些困住你的旧故事，正在被温柔溶解。', '它们蒸发了，只剩下光。'],
    at: [0.30, 0.55, 0.85],
    vessel: Alignment(0, 0.10),
    play: '搅一搅魔药',
    playHint: '在屏幕上画圈，搅动魔药\n搅得越快，颜色变得越快',
    playWin: '全都化成光了',
    stir: true,
    light: Color(0xFFE2C9FF),
    deep: Color(0xFF8E5BD6),
  ),
  ReleaseStyle(
    scene: 'release_deep',
    bed: 'rel_deep',
    name: '人鱼珍珠',
    skin: '美人鱼海洋',
    action: '交给美人鱼',
    lines: ['把烦恼交给这枚贝壳。', '像海水容纳所有情绪一样，允许自己经历它们。', '她带着它，游向有光的地方。', '月光下，它只是一粒珍珠。'],
    at: [0.14, 0.42, 0.88],
    vessel: Alignment(0.06, 0.50),
    play: '陪她游向月光',
    playHint: '轻点屏幕，陪她往上游\n点得越快，离月光越近',
    playWin: '她浮出海面，看见月亮了',
    light: Color(0xFFCFF3FF),
    deep: Color(0xFF4FB4DA),
  ),
];

/// 五种方式共用的引导语。文字要和 tools/tts/generate_guides.py 里的一致，语音念的就是这些。
/// 深度释放开头的身体放松：`assets/voice/release_scan_<1..5>.m4a`
const scanLines = [
  '现在，把注意力带到额头和眉心，让它慢慢松开。',
  '肩膀往下沉，离耳朵远一点。',
  '感受胸口。那里的紧，随着呼气一点点散开。',
  '肚子变软，手心也松开。',
  '整个身体，被稳稳地托住。',
];

/// 画面中间的留白提示：`assets/voice/release_hold_<1..3>.m4a`
const holdLines = ['不用着急，就这样看着。', '每呼出一口气，就再松开一点。', '你做得很好。'];

/// 放完之后安住的两句：`assets/voice/release_settle_<1..2>.m4a`
const settleLines = ['感受一下，身体里多出来的那一点空间。', '让这份轻松，在这里多留一会儿。'];

/// 释放的两档（界面上现在只用轻量这一档，深度的配置留着）。一场仪式分五段：呼吸、放松（只有深度有）、看见、释放、安住，最后是肯定语。
class ReleaseDepth {
  final String name;
  final String about;

  /// 跟着光圈呼吸几轮
  final int breaths;

  /// 身体放松念几句（[scanLines] 的前几句）
  final int scan;

  /// 释放画面的长度
  final Duration ritual;

  /// 画面长度是否乘上每种方式的 [ReleaseStyle.pace]
  final bool paced;

  /// 画面中间的留白提示：true 全用，false 只用最后一处
  final bool allHolds;

  /// 安住念几句（[settleLines] 的前几句）
  final int settle;

  /// 肯定语念完后再带着跟念几遍
  final int repeats;

  const ReleaseDepth({
    required this.name,
    required this.about,
    required this.breaths,
    required this.scan,
    required this.ritual,
    required this.paced,
    required this.allHolds,
    required this.settle,
    required this.repeats,
  });

  /// 仪式里顶部显示的几段
  List<String> get phases => ['呼吸', if (scan > 0) '放松', '看见', '释放', '安住'];
}

const lightRelease = ReleaseDepth(
  name: '轻量',
  about: '约 2 分钟',
  breaths: 1,
  scan: 0,
  ritual: Duration(seconds: 55),
  paced: false,
  allHolds: false,
  settle: 1,
  repeats: 1,
);
const deepRelease = ReleaseDepth(
  name: '深度',
  about: '约 4 分半',
  breaths: 3,
  scan: 5,
  ritual: Duration(seconds: 120),
  paced: true,
  allHolds: true,
  settle: 2,
  repeats: 2,
);

// 每一段留多长。语音最长的一句大约 10 秒，都留了余量。
const noteTime = Duration(seconds: 3);
const breathTime = Duration(seconds: 10);
const scanLineTime = Duration(seconds: 11);
const guideTime = Duration(seconds: 13);
const settleLineTime = Duration(seconds: 11);
const affirmTime = Duration(seconds: 12);
const repeatCueTime = Duration(seconds: 4);

/// 这一档、这种方式的释放画面放多久
Duration ritualLength(ReleaseStyle s, ReleaseDepth d) => d.paced ? d.ritual * s.pace : d.ritual;

/// 画面中间的留白提示：(进度, 第几句)。夹在四句引导语的空档里。
List<(double, int)> holdTimes(ReleaseStyle s, ReleaseDepth d) {
  final all = [
    // 第二句引导语来得晚的（魔药），开头先垫一句
    if (s.at[0] >= 0.25) s.at[0] / 2,
    (s.at[0] + s.at[1]) / 2,
    (s.at[1] + s.at[2]) / 2,
  ];
  if (!d.allHolds) return [(all.last, 1)];
  return [for (final (i, t) in all.indexed) (t, i % holdLines.length)];
}

/// 从点下开始到肯定语念完一共多久
Duration totalLength(ReleaseStyle s, ReleaseDepth d) =>
    noteTime +
    breathTime * d.breaths +
    scanLineTime * d.scan +
    guideTime +
    ritualLength(s, d) +
    settleLineTime * d.settle +
    affirmTime +
    (repeatCueTime + affirmTime) * d.repeats;
