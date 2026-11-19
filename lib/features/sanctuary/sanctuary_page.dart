import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_embed_unity/flutter_embed_unity.dart';
import 'package:yuanjing_engine/yuanjing_engine.dart';

import '../../app/skin.dart';
import '../../app/store.dart';
import '../wish/wish_answer.dart';
import 'sanctuary_ui.dart';
import 'wish_mask.dart';

/// 一座殿：名字、能去的地方、能留下的心意
class SanctuaryScene {
  /// 后端用的名字
  final String id;

  /// Unity 里场景的名字
  final String unity;
  final String name;
  final String line;
  final String image;

  /// 地点 → 显示的名字
  final Map<String, String> places;

  /// 地点 → 按钮上「去哪」的说法
  final Map<String, String> goTo;

  /// 坐下的地方叫什么
  final String seatName;

  /// 每个地点能留下的心意：地点 → [(种类, 按钮上的字, 要不要写愿望)]
  final Map<String, List<(String, String, bool)>> offers;

  const SanctuaryScene({
    required this.id,
    required this.unity,
    required this.name,
    required this.line,
    required this.image,
    required this.places,
    required this.goTo,
    required this.seatName,
    required this.offers,
  });
}

const sanctuaryScenes = [
  // 俯视的卡通画风，一座湖心小岛上的小寺（山寺、教堂两座写实的已经不要了）
  SanctuaryScene(
    id: 'islet',
    unity: 'Islet',
    name: '湖心小寺',
    line: '坐船上岛，石台上有蒲团，树下挂着许愿的红布条',
    image: 'assets/sanctuary/islet.jpg',
    places: {'court': '岛上', 'tree': '许愿树下', 'burner': '香炉前', 'hall': '大殿前', 'inhall': '大殿里'},
    goTo: {'court': '起身走走', 'tree': '去许愿树', 'burner': '去香炉', 'hall': '去大殿', 'inhall': '进殿'},
    seatName: '石台',
    offers: {
      'tree': [('ribbon', '挂红布条', true), ('plaque', '挂木牌', true)],
      'burner': [('incense', '上香', false)],
    },
  ),
];

const _timeNames = {'dawn': '清晨', 'day': '白天', 'dusk': '黄昏', 'night': '夜晚'};
const _weatherNames = {'clear': '晴', 'rain': '雨', 'storm': '雷雨', 'snow': '雪'};
const _display = displayFont;
const _shadow = [Shadow(color: Color(0xB3000000), blurRadius: 10)];

/// 弹层里每一栏的小标题
const _sheetLabel = TextStyle(fontFamily: _display, fontSize: 13.5, fontWeight: FontWeight.w700, letterSpacing: 3, color: Color(0xCCDCC790));

/// 许愿殿：全屏的 Unity 场景，Flutter 只在上面叠一层界面。
/// 和 Unity 之间用 JSON 字符串通信：发给场景里名叫 Bridge 的物体，Unity 用 SendToFlutter 发回来。
/// 指令和回报的清单见 unity/Sanctuary/Assets/Scripts/World/GameDirector.cs。
class SanctuaryPage extends StatefulWidget {
  final SanctuaryScene scene;
  const SanctuaryPage({super.key, required this.scene});

  @override
  State<SanctuaryPage> createState() => _SanctuaryPageState();
}

class _SanctuaryPageState extends State<SanctuaryPage> with TickerProviderStateMixin {
  SanctuaryScene get scene => widget.scene;

  bool _ready = false;
  bool _moving = true;
  bool _busy = false;
  /// 做着事（_busy）的保险：Unity 那边万一没回 actionDone / offered（页面切走、重新进场），30 秒后不再等，摇杆和木牌回来
  Timer? _busyTimer;

  void _markBusy() {
    setState(() => _busy = true);
    _busyTimer?.cancel();
    _busyTimer = Timer(const Duration(seconds: 30), () {
      if (mounted && _busy) setState(() => _busy = false);
    });
  }
  bool _sound = true;
  bool _hint = false;
  bool _hinted = false;
  String _at = '';
  int _seat = -1;
  int _seats = 32;
  int _slots = 1;
  int _count = 0;

  /// 天色和天气：null 是跟着此刻走（天色看本机时间，天气由服务器定，所有人一样）
  String? _time;
  String? _weather;
  String _serverWeather = 'clear';

  String? _subtitle;

  /// 上面那块地名（PlaceBanner）：寺门推开时再挂一次（门关着的时候看不见）
  int _bannerReplay = 0;

  /// 摇杆正被按着（有字幕时摇杆先藏起来，免得字压在上面；手指按上去就还是出来）
  bool _stickHeld = false;
  String? _pendingWish;
  String? _pendingMask;

  /// 视角：top 俯视、level 平视、low 仰视、first 第一人称；放大倍数（双指捏合，1 到 8）
  String _view = 'top';
  /// 在大殿里：Unity 锁成平视，俯视、仰视的签子收起来（只剩平视、第一人称）
  bool _viewLocked = false;
  /// 大殿能不能走进去（Unity 进场时报的）
  bool _hallOpen = false;
  final ValueNotifier<double> _zoom = ValueNotifier(1);
  double _zoomStart = 1;

  void _setView(String mode) {
    if (mode == _view) return;
    if (_viewLocked && mode != 'level' && mode != 'first') return;
    setState(() => _view = mode);
    _send({'cmd': 'view', 'kind': mode});
  }

  void _setZoom(double z) {
    z = z.clamp(1.0, 8.0);
    if ((z - _zoom.value).abs() < 0.005) return;
    _zoom.value = z;
    _send({'cmd': 'zoom', 'x': z});
  }

  /// 岛上的小动物：编号 → 服务器给的那一份（名字、交情、等级……）
  final Map<String, Map<String, dynamic>> _pets = {};
  /// 这会儿身边是哪一只（空字符串是没有）、是不是站在水边、身边最近的空蒲团（-1 是没有：走到蒲团跟前才显示「坐下」）
  String _nearPet = '';
  bool _nearWater = false;
  int _nearSeat = -1;
  /// 殿里：身边 0.9 米内的拜垫（-1 是没有）、是不是站在中间供桌前（能上香）
  int _nearMat = -1;
  bool _nearAltar = false;
  int _feedCost = 2;
  DateTime? _meditateUntil;
  final int _meditateMinutes = 3;

  Timer? _enterTimer;
  Timer? _beatTimer;
  Timer? _tick;

  /// 树上已经挂出来的心意（服务器编号）、占了的格子；写了字的图按编号缓存（别人的字也要写成图发给 Unity）
  final _shownIds = <int>{};
  final _usedSlots = <int>{};
  final _masks = <int, String>{};
  /// 自己挂不了的格子（Unity 进场时报的 nohang：绘马架前站不了人）。别人的心意先往这几格放，「给自己留 4 格」只数挂得了的
  final _noHang = <int>{};
  /// 刚系上、已经记到服务器的那一件（Unity 的 hung）：后面的 offered 不再记一次
  (String, int)? _hung;
  late final AnimationController _breath = AnimationController(vsync: this, duration: const Duration(seconds: 10));

  @override
  void initState() {
    super.initState();
    resumeUnity();
    // 竖排标点先量好（写愿望时旁边的小预览直接用）
    WishMask.prepare();
    // Unity 第一次加载要一两秒，加载好之前发的指令会丢，所以隔一会儿发一次，直到它回了「进来了」
    _enterTimer = Timer.periodic(const Duration(milliseconds: 800), (_) => _enter());
    _enter();
  }

  @override
  void dispose() {
    _enterTimer?.cancel();
    _beatTimer?.cancel();
    _busyTimer?.cancel();
    _tick?.cancel();
    _breath.dispose();
    YuanjingVoice.stop();
    if (store.online) store.api.post('/sanctuary/${scene.id}/leave', {}).catchError((_) => <String, dynamic>{});
    _send({'cmd': 'audio', 'on': false, 'volume': 1});
    pauseUnity();
    super.dispose();
  }

  void _send(Map<String, dynamic> msg) => sendToUnity('Bridge', 'OnMessage', jsonEncode(msg));

  String get _timeNow {
    final h = DateTime.now().hour;
    if (h >= 5 && h < 8) return 'dawn';
    if (h >= 8 && h < 17) return 'day';
    if (h >= 17 && h < 19) return 'dusk';
    return 'night';
  }

  String get _timeShown => _time ?? _timeNow;
  String get _weatherShown => _weather ?? _serverWeather;

  void _enter() {
    _send({'cmd': 'enter', 'scene': scene.unity, 'time': _timeShown, 'weather': _weatherShown, 'seed': store.online ? 0 : 9, 'name': store.name});
  }

  void _sky({bool instant = false}) => _send({'cmd': 'sky', 'time': _timeShown, 'weather': _weatherShown, 'instant': instant});

  void _onUnity(String raw) {
    if (!mounted) return;
    final Map<String, dynamic> msg;
    try {
      msg = jsonDecode(raw) as Map<String, dynamic>;
    } catch (_) {
      return;
    }
    switch (msg['type']) {
      case 'ready':
        if (!_ready) _enter();
      case 'entered':
        if (msg['scene'] != scene.unity) return;
        _enterTimer?.cancel();
        _seats = (msg['seats'] as num?)?.toInt() ?? 32;
        _slots = math.max(1, (msg['slots'] as num?)?.toInt() ?? 1);
        // Unity 那边按编号认得已经挂着的，重发不会挂重
        _shownIds.clear();
        _usedSlots.clear();
        _noHang
          ..clear()
          ..addAll(((msg['nohang'] as String?) ?? '').split(',').map(int.tryParse).whereType<int>());
        setState(() {
          _ready = true;
          _moving = true;
          // 重新进场（Unity 停掉了手上的动作、不会再回 actionDone）：不再等它
          _busy = false;
          _at = '';
          _seat = -1;
          _nearSeat = -1;
          _nearMat = -1;
          _nearAltar = false;
          _viewLocked = false;
          _hallOpen = msg['hall'] == true;
        });
        _send({'cmd': 'audio', 'on': _sound, 'volume': 1});
        // 场景在后台一直留着：上次离开时的视角和放大倍数按这边记的重新对一遍
        _send({'cmd': 'view', 'kind': _view});
        _send({'cmd': 'zoom', 'x': _zoom.value});
        _beat();
        _beatTimer?.cancel();
        _beatTimer = Timer.periodic(const Duration(seconds: 6), (_) => _beat());
        _loadPets();
      case 'view':
        final m = msg['mode'] as String?;
        // 进殿时 Unity 把放大放回 1 倍（殿里平视镜头离人很近），这边的放大标签跟着回去
        final z = (msg['zoom'] as num?)?.toDouble();
        if (z != null && (z - _zoom.value).abs() > 0.01) _zoom.value = z;
        setState(() {
          if (m != null) _view = m;
          _viewLocked = msg['locked'] == true;
        });
      case 'near':
        setState(() {
          _nearPet = (msg['pet'] as String?) ?? '';
          _nearWater = msg['water'] == true;
          _nearSeat = (msg['seat'] as num?)?.toInt() ?? -1;
          _nearMat = (msg['mat'] as num?)?.toInt() ?? -1;
          _nearAltar = msg['altar'] == true;
        });
      case 'sitFailed':
        final reason = msg['reason'] as String?;
        if (reason != 'busy') setState(() => _nearSeat = -1);
        _say(
            switch (reason) {
              'busy' => '稍等一下',
              'taken' => '这个蒲团刚被人坐了',
              _ => '附近没有空着的蒲团，走到蒲团跟前再坐',
            },
            const Duration(milliseconds: 2400));
      case 'offerFailed':
        final wish = _pendingWish;
        _pendingWish = null;
        _pendingMask = null;
        setState(() => _busy = false);
        if (msg['reason'] == 'full' && wish != null) {
          // 绳上挂得了的格子全是你自己的心意了：写好的愿望不丢，替你记在心愿里
          store.addWish('life', wish).then((got) {
            if (got > 0 && mounted) coinToast(context, got, '完成今日许愿');
          });
          _say('绳上挂满了你的心意。这个愿望先替你记在心愿里了', const Duration(milliseconds: 3200));
        } else {
          _say(msg['reason'] == 'full' ? '绳上已经挂满了，过些日子再来挂吧' : '稍等一下，正忙着呢', const Duration(milliseconds: 2400));
        }
      case 'petGift':
        _petGift((msg['id'] as String?) ?? '');
      case 'moving':
        setState(() => _moving = true);
      case 'arrived':
        setState(() {
          _moving = false;
          // 空字符串：在院子里随便走，没靠近哪个地方
          _at = (msg['spot'] as String?) ?? '';
          if (_at.isEmpty) _at = 'court';
          _seat = -1;
        });
        // 第一次走进院子时提示一下怎么看、怎么走
        if (!_hinted) {
          _hinted = true;
          setState(() => _hint = true);
          Timer(const Duration(seconds: 8), () {
            if (mounted) setState(() => _hint = false);
          });
        }
        _beat();
      case 'stood':
        setState(() {
          // 在殿里的蒲团上起身：还在殿里（以前回到「岛上」，地名牌子「大殿里」又出来一次）
          _at = _seat >= _seats ? 'inhall' : 'court';
          _seat = -1;
        });
        _beat();
      case 'seated':
        setState(() {
          _moving = false;
          _at = 'seat';
          _seat = (msg['seat'] as num).toInt();
          _nearSeat = -1;
          _nearMat = -1;
          _nearAltar = false;
        });
        _beat();
      case 'actionDone':
        setState(() => _busy = false);
      case 'hung':
        // 布条、木牌刚系到绳上：马上记到服务器（后面退半步、合掌那两秒里离开也不会丢）；回应等 offered 再念
        final kind = msg['kind'] as String;
        final slot = (msg['slot'] as num?)?.toInt() ?? -1;
        _hung = (kind, slot);
        _record(kind, slot, _pendingWish, _pendingMask);
      case 'offered':
        _offered(msg['kind'] as String, (msg['slot'] as num?)?.toInt() ?? -1);
      case 'thunder':
        YuanjingHaptics.play('tick');
    }
  }

  // ── 小动物：摸、喂、交情 ──

  /// 上岛时取一次：每只和我有多熟、今天谁来迎接、谁叼了礼物，转告 Unity
  Future<void> _loadPets() async {
    if (!store.online) return;
    try {
      final r = await store.api.get('/pets');
      if (!mounted) return;
      _feedCost = (r['feed_cost'] as num?)?.toInt() ?? 2;
      final list = <String>[];
      for (final p in (r['pets'] as List).cast<Map<String, dynamic>>()) {
        _pets[p['id'] as String] = p;
        list.add('${p['id']}:${p['level']}:${p['greet'] == true ? 1 : 0}:${p['gift'] != null ? 1 : 0}');
      }
      _send({'cmd': 'pets', 'list': list.join('|')});
      setState(() {});
    } catch (_) {}
  }

  Future<void> _petAct(String id, String action) async {
    if (_busy) return;
    final name = (_pets[id]?['name'] as String?) ?? '它';
    YuanjingHaptics.play('tick');
    if (!store.online) {
      _send({'cmd': 'petact', 'id': id, 'action': action, 'seat': 0});
      return;
    }
    try {
      final r = (await store.api.post('/pets/$id/$action', {})) as Map<String, dynamic>;
      if (!mounted) return;
      _pets[id] = r;
      _send({'cmd': 'petact', 'id': id, 'action': action, 'seat': (r['level'] as num?)?.toInt() ?? 0});
      if (action == 'feed') store.refresh();
      final String line;
      if (r['level_up'] == true) {
        line = '$name和你更熟了：${r['level_name']}';
      } else if (r['counted'] != true) {
        line = action == 'feed' ? '$name吃得很香。今天的交情已经涨满了，明天再来。' : '$name很受用。今天的交情已经涨满了，明天再来。';
      } else {
        final next = r['next'];
        final left = next == null ? '' : '（${r['affinity']} / $next）';
        line = action == 'feed' ? '$name吃得很香（花了 $_feedCost 金币），交情 +2$left' : '$name蹭了蹭你的手，交情 +1$left';
      }
      _say(line, const Duration(milliseconds: 2400));
    } on ApiError catch (e) {
      if (mounted) _say(e.message, const Duration(seconds: 2));
    } catch (_) {}
  }

  /// 它把礼物放到脚边了：收下，换成金币
  Future<void> _petGift(String id) async {
    if (!store.online || id.isEmpty) return;
    try {
      final r = (await store.api.post('/pets/$id/gift', {})) as Map<String, dynamic>;
      final got = (r['got'] as num?)?.toInt() ?? 0;
      if (got <= 0 || !mounted) return;
      _pets[id]?['gift'] = null;
      store.refresh();
      YuanjingHaptics.play('tick');
      coinToast(context, got, '${r['name']}送你${r['what']}');
      _say('${r['name']}叼来${r['what']}，放在你脚边。', const Duration(seconds: 3));
    } catch (_) {}
  }

  void _feedWild(String kind) {
    YuanjingHaptics.play('tick');
    _send({'cmd': 'feed', 'kind': kind});
  }

  // ── 和服务器同步：谁在场、天气、别人留下的心意 ──

  Future<void> _beat({String? action}) async {
    if (!_ready || !store.online) return;
    try {
      final r = await store.api.post('/sanctuary/${scene.id}/beat', {'seat': _seat, 'seats': _seats, 'action': ?action});
      if (!mounted) return;
      final people = (r['people'] as List).cast<Map<String, dynamic>>();
      String clean(Object? n) => '${n ?? ''}'.replaceAll(RegExp(r'[:|]'), ' ');
      // 每人：编号:座位:是不是内置:名字:要做的事:来了几秒:待几秒（内置香客才有后三项，Unity 照着演）
      _send({
        'cmd': 'pilgrims',
        'list': people
            .map((p) => '${p['id']}:${p['seat']}:${p['npc'] == true ? 1 : 0}:${clean(p['name'])}:${p['plan'] ?? ''}:${p['since'] ?? 0}:${p['stay'] ?? 0}')
            .join('|')
      });
      for (final p in people) {
        if (p['action'] != null) _send({'cmd': 'pact', 'id': p['id'], 'action': p['action']});
      }
      await _showOfferings([...(r['mine'] as List).cast<Map<String, dynamic>>()], [...(r['offerings'] as List).cast<Map<String, dynamic>>()]);
      final w = r['weather'] as String;
      final changed = w != _serverWeather;
      setState(() {
        _count = (r['count'] as num).toInt();
        _serverWeather = w;
      });
      if (changed && _weather == null) _sky();
    } catch (_) {
      // 连不上就先不同步，殿里还是能走能坐
    }
  }

  /// 自己挂得了、还空着的格子有几个
  int get _hangableFree {
    var n = 0;
    for (var s = 0; s < _slots; s++) {
      if (!_usedSlots.contains(s) && !_noHang.contains(s)) n++;
    }
    return n;
  }

  /// 别人的心意放哪一格：想要的那格空着、又不会把「自己挂得了的空格」挤到 4 格以下，就放那里；
  /// 不然先放到自己挂不了的空格里（绘马架前那几格），再往后找挂得了的空格（还剩 4 格以上时）。都不行返回 -1（这一件先不挂出来）
  int _slotForOthers(int want) {
    bool fits(int s) => !_usedSlots.contains(s) && (_noHang.contains(s) || _hangableFree > 4);
    if (fits(want)) return want;
    for (var k = 1; k <= _slots; k++) {
      final s = (want + k) % _slots;
      if (_noHang.contains(s) && !_usedSlots.contains(s)) return s;
    }
    for (var k = 1; k <= _slots; k++) {
      final s = (want + k) % _slots;
      if (fits(s)) return s;
    }
    return -1;
  }

  /// 把树上的心意发给 Unity：自己的先挂（不会被别人的挤掉），别人的挑空格、给自己留几格；写了字的写成图一起发
  Future<void> _showOfferings(List<Map<String, dynamic>> mine, List<Map<String, dynamic>> others) async {
    for (final (list, own) in [(mine, true), (others, false)]) {
      for (final o in list) {
        final id = (o['id'] as num?)?.toInt();
        final want = (o['slot'] as num?)?.toInt() ?? -1;
        final kind = o['kind'] as String? ?? '';
        if (id == null || want < 0 || (kind != 'ribbon' && kind != 'plaque') || _shownIds.contains(id)) continue;
        // 自己的照原来那格发（mine）：刚亲手挂的那件服务器编号还没回来时，Unity 认得那一格上是自己的，不会再挂一件。
        // 别人挂的：两个人挂在了同一格（各自挑的空位撞了）就挪开；最多占到自己挂得了的空格只剩 4 格，自己来了总有地方挂
        final slot = own ? want % _slots : _slotForOthers(want % _slots);
        if (slot < 0) continue;
        _shownIds.add(id);
        _usedSlots.add(slot);
        final text = (o['text'] as String?)?.trim() ?? '';
        String? mask = _masks[id];
        if (mask == null && text.isNotEmpty) {
          try {
            mask = await WishMask.render(text, plaque: kind == 'plaque');
          } catch (_) {}
          if (mask != null) _remember(id, mask);
        }
        if (!mounted) return;
        _send({'cmd': 'offerings', 'kind': kind, 'list': '$slot', 'id': '$id', 'tex': ?mask, if (own) 'mine': true});
      }
    }
  }

  void _remember(int id, String mask) {
    _masks[id] = mask;
    // 只记最近的六十张（树上一共也就三十来格）
    while (_masks.length > 60) {
      _masks.remove(_masks.keys.first);
    }
  }

  // ── 走动和动作 ──

  void _go(String spot) {
    if (_moving || _busy) return;
    YuanjingHaptics.play('tick');
    _send({'cmd': 'goto', 'spot': spot});
  }

  /// 坐到身边那个空蒲团上（Unity 报的最近的一个）
  void _sit() {
    if (_moving || _busy) return;
    YuanjingHaptics.play('tick');
    _send({'cmd': 'sit', 'seat': _nearSeat});
  }

  /// 起身：退到这一排前面的走道上，站着
  void _stand() {
    if (_moving || _busy) return;
    YuanjingHaptics.play('tick');
    _send({'cmd': 'stand'});
  }

  /// 做一个动作。mat：殿里在那块拜垫上做（Unity 先走上拜垫、面朝佛像）
  void _act(String action, {int? mat}) {
    if (_moving || _busy) return;
    YuanjingHaptics.play('tick');
    _markBusy();
    _send({'cmd': 'act', 'action': action, 'mat': ?mat});
    _beat(action: action);
  }

  /// 写下愿望。返回 null 是取消了。cloth：写在红布条（ribbon）或木牌（plaque）上挂到树上——所有人都看得到，最多 40 个字，旁边有个小预览
  Future<String?> _askWish(String title, String hint, {String? cloth}) {
    final c = TextEditingController();
    final public = cloth != null;
    return showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      barrierColor: Colors.black38,
      builder: (context) => Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
        child: SanctuarySheet(
          padding: const EdgeInsets.fromLTRB(24, 24, 24, 18),
          child: SafeArea(
            top: false,
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: const TextStyle(fontFamily: _display, fontSize: 22, fontWeight: FontWeight.w700, letterSpacing: 2, color: SancColors.paper)),
              const SizedBox(height: 14),
              Container(
                decoration: BoxDecoration(color: const Color(0x12F3E8CF), borderRadius: BorderRadius.circular(8), border: Border.all(color: const Color(0x3DF3E8CF))),
                padding: const EdgeInsets.fromLTRB(16, 4, 6, 4),
                child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                  Expanded(
                    child: TextField(
                      controller: c,
                      autofocus: true,
                      minLines: 2,
                      maxLines: 4,
                      maxLength: public ? WishMask.maxChars : 60,
                      // 挂到树上的：一行写一列，布条最多 3 列、木牌最多 5 列（再多字就小得看不清了）
                      inputFormatters: [if (public) WishMask.lineLimit(plaque: cloth == 'plaque')],
                      style: const TextStyle(fontSize: 16.5, height: 1.6, color: Colors.white),
                      cursorColor: SancColors.gold,
                      decoration: InputDecoration(border: InputBorder.none, counterText: '', hintText: hint, hintStyle: const TextStyle(color: Colors.white38)),
                    ),
                  ),
                  MicButton(controller: c, color: Colors.white70),
                  // 挂到树上的样子：竖着写，从右往左
                  if (public)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(6, 6, 4, 6),
                      child: ValueListenableBuilder<TextEditingValue>(
                        valueListenable: c,
                        builder: (_, v, _) => WishClothPreview(text: v.text, plaque: cloth == 'plaque', height: cloth == 'plaque' ? 92 : 128),
                      ),
                    ),
                ]),
              ),
              const SizedBox(height: 8),
              Text(public ? '会写在${cloth == 'plaque' ? '木牌' : '布条'}上，由你亲手挂到树上。来岛上的人都看得到，最多 ${WishMask.maxChars} 个字。' : '写下的话只有你自己看得到。',
                  style: const TextStyle(fontSize: 12.5, height: 1.5, color: Colors.white54)),
              const SizedBox(height: 16),
              LacquerButton('写好了', onTap: () {
                final t = c.text.trim();
                if (t.isNotEmpty) Navigator.of(context).pop(t);
              }),
            ]),
          ),
        ),
      ),
    );
  }

  /// 留下一件心意（红布条、木牌、香、硬币、蜡烛）。布条、木牌：写好的字写成一张图跟着发过去，人走过去亲手系上
  Future<void> _offer(String kind, String label, bool needsWish) async {
    if (_moving || _busy) return;
    String? text;
    String? mask;
    final cloth = kind == 'ribbon' || kind == 'plaque';
    if (needsWish) {
      if (cloth) await WishMask.prepare();
      if (!mounted) return;
      text = await _askWish(label, cloth ? '把愿望写在上面，竖着写' : '把愿望写在上面', cloth: cloth ? kind : null);
      if (text == null || !mounted) return;
      if (cloth) {
        _markBusy();
        try {
          mask = await WishMask.render(text, plaque: kind == 'plaque');
        } catch (_) {
          // 写不成图也照样挂（素布条），字还是会记下来
        }
        if (!mounted) return;
      }
    }
    YuanjingHaptics.play('tick');
    _pendingWish = text;
    _pendingMask = mask;
    _markBusy();
    _send({'cmd': 'offer', 'kind': kind, 'text': ?text, 'tex': ?mask});
  }

  /// 记到服务器：这一件挂在哪一格、写了什么（布条、木牌的字大家都看得到）。拿回编号以后告诉 Unity 那一格上的是自己的这一件
  void _record(String kind, int slot, String? text, String? mask) {
    if (slot >= 0) _usedSlots.add(slot);
    if (!store.online) return;
    // 布条、木牌上的字挂在树上大家都看得到（写的时候界面上说了）：public 告诉服务器可以给别人看
    final cloth = kind == 'ribbon' || kind == 'plaque';
    store.api.post('/sanctuary/${scene.id}/offer', {'kind': kind, 'slot': slot, 'text': ?text, if (cloth && text != null) 'public': true}).then((r) {
      // 记下编号：下次心跳里「自己的」这一件已经挂着了，不再发；Unity 那边认领这一格上自己刚挂的那件（重新进殿时不会被当成没记上的收掉）
      final id = (r['id'] as num?)?.toInt();
      if (id != null) {
        _shownIds.add(id);
        if (mask != null) _remember(id, mask);
        if (cloth && slot >= 0 && mounted) _send({'cmd': 'offerings', 'kind': kind, 'list': '$slot', 'id': '$id', 'mine': true});
      }
      final got = (r['got'] as num?)?.toInt() ?? 0;
      if (got > 0 && mounted) {
        store.refresh();
        coinToast(context, got, '在许愿殿留下心意');
      }
    }).catchError((_) {});
  }

  Future<void> _offered(String kind, int slot) async {
    final text = _pendingWish;
    final mask = _pendingMask;
    _pendingWish = null;
    _pendingMask = null;
    // 系上那一刻（hung）已经记过了的不再记
    final recorded = _hung != null && _hung!.$1 == kind && _hung!.$2 == slot;
    _hung = null;
    if (!recorded) _record(kind, slot, text, mask);
    if (text != null) {
      await _answer(text);
    } else {
      // 没写愿望的（上香）：放好以后拜一拜
      _send({'cmd': 'act', 'action': 'bow'});
      _beat(action: 'bow');
    }
  }

  /// 坐着许愿：写下愿望，合掌，听回应
  Future<void> _wish() async {
    if (_moving || _busy) return;
    final text = await _askWish('许个愿', '此刻心里最想要的是什么');
    if (text == null || !mounted) return;
    await _answer(text);
  }

  /// 记下心愿，合掌，播回应（四句，带字幕）
  Future<void> _answer(String text) async {
    final fetching = WishAnswer.fetch(text, 'life');
    _markBusy();
    // 刚挂好布条、木牌：特写一直对着它，念完回应再收（没有特写时 Unity 不理）
    _send({'cmd': 'linger', 'x': 45});
    _send({'cmd': 'act', 'action': 'pray'});
    _beat(action: 'pray');
    try {
      final answer = await fetching;
      if (!mounted) return;
      if (answer != null && answer.isSupport) {
        _showSupport();
        return;
      }
      store.addWish(answer?.scene ?? 'life', text).then((got) {
        if (got > 0 && mounted) coinToast(context, got, '完成今日许愿');
      });
      if (answer == null) {
        await _say('愿望已经留在这里了。', const Duration(milliseconds: 3200));
        return;
      }
      for (var i = 0; i < answer.lines.length; i++) {
        if (!mounted) return;
        setState(() => _subtitle = answer.lines[i]);
        final d = await answer.play(i);
        await Future<void>.delayed(d + const Duration(milliseconds: 450));
      }
      if (mounted) setState(() => _subtitle = null);
    } finally {
      if (mounted) _send({'cmd': 'linger', 'x': 0});
    }
  }


  Future<void> _say(String text, Duration d) async {
    setState(() => _subtitle = text);
    await Future<void>.delayed(d);
    if (mounted && _subtitle == text) setState(() => _subtitle = null);
  }

  void _showSupport() {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: const Color(0xF20B0A0D),
      builder: (_) => const SafeArea(
        child: Padding(
          padding: EdgeInsets.fromLTRB(28, 26, 28, 20),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('先停一下', style: TextStyle(fontFamily: _display, fontSize: 26, fontWeight: FontWeight.w700, color: Colors.white)),
            SizedBox(height: 12),
            Text('你写下的话让我有些担心。请先让一个真实的人陪着你。', style: TextStyle(fontSize: 16, height: 1.7, color: Colors.white)),
            SizedBox(height: 18),
            Text('全国统一心理援助热线', style: TextStyle(fontSize: 13.5, color: Colors.white70)),
            Text('12356', style: TextStyle(fontSize: 32, fontWeight: FontWeight.w700, letterSpacing: 3, color: Colors.white)),
            SizedBox(height: 8),
            Text('如果此刻有危险，请直接拨打 120 或 110。', style: TextStyle(fontSize: 14, color: Colors.white)),
          ]),
        ),
      ),
    );
  }

  // ── 静坐 ──

  void _meditate() {
    if (_moving || _busy) return;
    _send({'cmd': 'act', 'action': 'meditate'});
    _beat(action: 'meditate');
    _breath.repeat();
    setState(() => _meditateUntil = DateTime.now().add(Duration(minutes: _meditateMinutes)));
    _tick?.cancel();
    _tick = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted || _meditateUntil == null) return;
      if (DateTime.now().isAfter(_meditateUntil!)) {
        _endMeditation(finished: true);
      } else {
        setState(() {});
      }
    });
  }

  void _endMeditation({bool finished = false}) {
    _tick?.cancel();
    _breath.stop();
    setState(() => _meditateUntil = null);
    if (finished) {
      _send({'cmd': 'bell'});
      _say('静坐了 $_meditateMinutes 分钟。慢慢睁开眼睛。', const Duration(seconds: 4));
    }
  }

  // ── 界面 ──

  /// 地名牌子按哪个地方出：坐下、起身不算换地方（殿里的蒲团还是「大殿里」，院子里的蒲团还是「岛上」），只有真走到别处才出来
  String get _bannerPlace => _at == 'seat'
      ? (_seat >= _seats ? scene.places['inhall'] ?? '' : scene.places['court'] ?? '')
      : scene.places[_at] ?? '';

  List<PlaqueAction> _actions() {
    final base = _placeActions();
    final extra = <PlaqueAction>[];
    final pet = _pets[_nearPet];
    if (pet != null) {
      final name = pet['name'] as String;
      extra.add(PlaqueAction('摸摸$name', primary: true, onTap: () => _petAct(_nearPet, 'pet')));
      extra.add(PlaqueAction('喂$name', onTap: () => _petAct(_nearPet, 'feed')));
    }
    if (_nearWater) extra.add(PlaqueAction('喂鱼', primary: extra.isEmpty && base.isEmpty, onTap: () => _feedWild('fish')));
    if (_at == 'court' && _seat < 0) extra.add(PlaqueAction('喂小鸟', onTap: () => _feedWild('birds')));
    if (extra.isEmpty) return base;
    // 小动物在身边时，摸它是第一块（朱漆的），原来的第一块退成普通的
    final lead = extra.where((a) => a.primary || pet != null && a.label.startsWith('喂') && a.label != '喂鱼' && a.label != '喂小鸟').toList();
    final tail = extra.where((a) => !lead.contains(a)).toList();
    return [
      ...lead,
      for (final a in base) lead.isEmpty ? a : PlaqueAction(a.label, onTap: a.onTap),
      ...tail,
    ];
  }

  /// 人在大殿里面（站着，或者坐在殿里的蒲团上：Unity 这时锁着平视）
  bool get _inHall => _at == 'inhall' || _viewLocked || (_at == 'seat' && _seat >= _seats);

  List<PlaqueAction> _placeActions() {
    final here = scene.offers[_at] ?? const <(String, String, bool)>[];
    final offers = [for (var i = 0; i < here.length; i++) PlaqueAction(here[i].$2, primary: i == 0, onTap: () => _offer(here[i].$1, here[i].$2, here[i].$3))];
    final inHall = _inHall;
    final others = [
      for (final spot in scene.places.keys)
        if (spot != _at && spot != 'court' && (spot != 'inhall' || (_hallOpen && !inHall)))
          // 在殿里时「去大殿」就是走出殿门、站到殿前
          PlaqueAction(inHall && spot == 'hall' ? '出殿' : scene.goTo[spot]!, onTap: () => _go(spot)),
    ];
    if (_at == 'seat') {
      return [
        PlaqueAction('许愿', primary: true, onTap: _wish),
        PlaqueAction('合掌', onTap: () => _act('pray')),
        PlaqueAction('鞠躬', onTap: () => _act('bow')),
        // 坐着不给「跪拜」：盘坐在圆蒲团上跪不下去（膝盖、小腿会插进蒲团里）；要跪拜先起身，走到拜垫或空地上
        PlaqueAction('静坐', onTap: _meditate),
        PlaqueAction('起身', onTap: _stand),
        ...others,
      ];
    }
    // 走到蒲团跟前（Unity 报了身边有空蒲团）才有「坐下」，坐的是最近的那个
    final sit = _nearSeat >= 0;
    if (_at == 'inhall') {
      // 大殿里：站在中间供桌前能上香；走到拜垫跟前，跪拜、鞠躬、合掌都在那块拜垫上做（面朝佛像）；走到静坐的蒲团跟前能坐下。
      // 站在拜垫上（中间那块离供桌也不远，上香也有）：跪拜在前、是主按钮，上香跟在后面
      final mat = _nearMat >= 0 ? _nearMat : null;
      final onMat = mat != null;
      return [
        if (onMat) PlaqueAction('跪拜', primary: true, onTap: () => _act('kneel', mat: mat)),
        if (_nearAltar) PlaqueAction('上香', primary: !onMat, onTap: () => _offer('incense', '上香', false)),
        if (sit) PlaqueAction('坐下', primary: !onMat && !_nearAltar, onTap: _sit),
        if (!onMat) PlaqueAction('跪拜', onTap: () => _act('kneel')),
        PlaqueAction('鞠躬', onTap: () => _act('bow', mat: mat)),
        PlaqueAction('合掌', primary: !onMat && !_nearAltar && !sit, onTap: () => _act('pray', mat: mat)),
        ...others,
      ];
    }
    if (_at == 'court') {
      return [
        if (sit) PlaqueAction('坐下', primary: true, onTap: _sit),
        PlaqueAction('合掌', primary: !sit, onTap: () => _act('pray')),
        PlaqueAction('鞠躬', onTap: () => _act('bow')),
        PlaqueAction('跪拜', onTap: () => _act('kneel')),
        ...others,
      ];
    }
    if (_at.isEmpty) return const [];
    return [
      ...offers,
      if (sit) PlaqueAction('坐下', primary: offers.isEmpty, onTap: _sit),
      PlaqueAction('合掌', primary: offers.isEmpty && !sit, onTap: () => _act('pray')),
      PlaqueAction('鞠躬', onTap: () => _act('bow')),
      PlaqueAction('跪拜', onTap: () => _act('kneel')),
      ...others,
    ];
  }

  void _showSky() {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      barrierColor: Colors.black26,
      builder: (context) => StatefulBuilder(
        builder: (context, setSheet) {
          Widget row(String title, Map<String, String> names, String? value, void Function(String?) pick) => Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: _sheetLabel),
                  const SizedBox(height: 7),
                  Wrap(spacing: 8, runSpacing: 4, children: [
                    SanctuaryChip('跟着此刻', selected: value == null, onTap: () => pick(null)),
                    for (final e in names.entries) SanctuaryChip(e.value, selected: value == e.key, onTap: () => pick(e.key)),
                  ]),
                ],
              );
          return SanctuarySheet(
            padding: const EdgeInsets.fromLTRB(24, 24, 24, 12),
            child: SafeArea(
              top: false,
              child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
                // 地名那块三秒就淡掉了：寺里有几个人，点开天色这里也看得到
                if (_count > 1) ...[
                  Text('此刻寺里有 $_count 个人', style: const TextStyle(fontSize: 13, letterSpacing: 1, color: Colors.white60)),
                  const SizedBox(height: 16),
                ],
                row('天色', _timeNames, _time, (v) {
                  setState(() => _time = v);
                  setSheet(() {});
                  _sky();
                }),
                const SizedBox(height: 17),
                row('天气', _weatherNames, _weather, (v) {
                  setState(() => _weather = v);
                  setSheet(() {});
                  _sky();
                }),
                const SizedBox(height: 17),
                Row(children: [
                  const Text('声音', style: _sheetLabel),
                  const Spacer(),
                  SanctuaryChip(_sound ? '开着' : '关了', selected: _sound, onTap: () {
                    setState(() => _sound = !_sound);
                    setSheet(() {});
                    _send({'cmd': 'audio', 'on': _sound, 'volume': 1});
                  }),
                ]),
                const SizedBox(height: 7),
              ]),
            ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    final meditating = _meditateUntil != null;
    final left = meditating ? _meditateUntil!.difference(DateTime.now()) : Duration.zero;
    final showActions = _ready && !_moving && !_busy && !meditating && _subtitle == null;
    // 自动走的路上（从码头进殿要走四十多秒）：木牌那里只留一块「停下」；点画面别处照样改道
    final showHalt = _ready && _moving && !_busy && !meditating && _subtitle == null && _at.isNotEmpty;
    // 摇杆：做事的时候（拜、上香、系布条、许愿，镜头常凑近成特写）收起来，那时推了也不走；
    // 有字幕时也先藏起来（字幕正好在摇杆那一带），手指按上去照样能走、摇杆也出来
    final showStick = !_busy && (_subtitle == null || _stickHeld);
    return Scaffold(
      backgroundColor: Colors.black,
      resizeToAvoidBottomInset: false,
      body: Stack(fit: StackFit.expand, children: [
        EmbedUnity(onMessageFromUnity: _onUnity),
        // 拖动环顾四周，点远处走过去。手势在 Flutter 这层接，再转给 Unity。
        GestureDetector(
          behavior: HitTestBehavior.opaque,
          // 一根手指拖：转头看；两根手指捏合：放大缩小
          onScaleStart: (_) => _zoomStart = _zoom.value,
          onScaleUpdate: (d) {
            if (d.pointerCount >= 2) {
              _setZoom(_zoomStart * d.scale);
            } else {
              _send({'cmd': 'look', 'dx': -d.focalPointDelta.dx / size.width, 'dy': d.focalPointDelta.dy / size.height});
            }
          },
          onTapUp: (d) {
            // 右边竹签那一条不算点画面（万一点击穿过来了，别让人走过去）
            final slips = d.localPosition.dx > size.width - 64 && d.localPosition.dy < MediaQuery.paddingOf(context).top + 300;
            if (_ready && !_busy && !meditating && !slips) _send({'cmd': 'tap', 'x': d.localPosition.dx / size.width, 'y': d.localPosition.dy / size.height});
          },
        ),
        // 摇杆：左下角，按住拖动走路。底下那排木牌比较高，摇杆放在它和提示那行字的上面
        if (_ready && _meditateUntil == null)
          Positioned(
            left: 22,
            bottom: MediaQuery.paddingOf(context).bottom + 6 + PlaqueBar.height + 30,
            child: IgnorePointer(
              ignoring: _busy,
              child: AnimatedOpacity(
                opacity: showStick ? 1 : 0,
                duration: Duration(milliseconds: showStick ? 250 : 450),
                child: _Joystick(
                  onChanged: (v) => _send({'cmd': 'move', 'x': v.dx, 'y': -v.dy}),
                  onHeld: (held) {
                    if (mounted && held != _stickHeld) setState(() => _stickHeld = held);
                  },
                ),
              ),
            ),
          ),
        // 上下各压一层暗角，字才看得清
        const IgnorePointer(
          child: DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0x73000000), Color(0x00000000), Color(0x00000000), Color(0x8C000000)],
                stops: [0, 0.2, 0.68, 1],
              ),
            ),
          ),
        ),
        // 静坐：画面暗下来，一圈光跟着呼吸
        IgnorePointer(
          child: AnimatedOpacity(
            opacity: meditating ? 1 : 0,
            duration: const Duration(milliseconds: 1400),
            child: ColoredBox(
              color: const Color(0x8C000000),
              child: Center(
                child: AnimatedBuilder(
                  animation: _breath,
                  builder: (context, _) {
                    final t = _breath.value;
                    final k = Curves.easeInOut.transform(t < 0.5 ? t * 2 : 2 - t * 2);
                    return Column(mainAxisSize: MainAxisSize.min, children: [
                      SizedBox(
                        width: 200,
                        height: 200,
                        child: Center(
                          child: Container(
                            width: 120 + 70 * k,
                            height: 120 + 70 * k,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              border: Border.all(color: Color.fromRGBO(243, 217, 160, 0.35 + 0.4 * k), width: 1.2),
                              boxShadow: [BoxShadow(color: Color.fromRGBO(243, 217, 160, 0.10 + 0.16 * k), blurRadius: 50, spreadRadius: 6)],
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 24),
                      Text(t < 0.5 ? '吸气' : '呼气', style: const TextStyle(fontFamily: _display, fontSize: 20, letterSpacing: 8, color: Colors.white, shadows: _shadow)),
                    ]);
                  },
                ),
              ),
            ),
          ),
        ),
        SafeArea(
          child: Column(children: [
            Stack(alignment: Alignment.topCenter, children: [
              // 现在在哪、寺里有多少人：换了地方才出来三秒；走着、做着事（特写）、静坐、有字幕时不出来
              Padding(
                padding: const EdgeInsets.only(top: 50),
                child: PlaceBanner(
                  place: _bannerPlace,
                  count: _count,
                  allowed: _ready && !_moving && !_busy && !meditating && _subtitle == null,
                  replay: _bannerReplay,
                ),
              ),
              // 左上一枚「离开」的朱印，右上一块写着天色天气的瓦牌
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 4, 14, 0),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  SealBackButton(onTap: () => Navigator.of(context).maybePop()),
                  const Spacer(),
                  if (_ready && !meditating)
                    SkyTag(label: '${_timeNames[_timeShown]} · ${_weatherNames[_weatherShown]}', time: _timeShown, weather: _weatherShown, onTap: _showSky),
                ]),
              ),
            ]),
            const Expanded(child: IgnorePointer(child: SizedBox.expand())),
            if (meditating) ...[
              Text('${left.inMinutes}:${(left.inSeconds % 60).toString().padLeft(2, '0')}',
                  style: const TextStyle(fontSize: 15, letterSpacing: 2, color: Colors.white70, fontFeatures: [FontFeature.tabularFigures()])),
              const SizedBox(height: 11),
              SanctuaryChip('结束静坐', onTap: _endMeditation),
              const SizedBox(height: 23),
            ],
            // 回应的字幕
            IgnorePointer(
              child: AnimatedSwitcher(
                duration: const Duration(milliseconds: 600),
                child: _subtitle == null
                    ? const SizedBox(height: 0, width: double.infinity)
                    : Padding(
                        key: ValueKey(_subtitle),
                        padding: const EdgeInsets.fromLTRB(34, 0, 34, 54),
                        child: Text(_subtitle!,
                            textAlign: TextAlign.center,
                            style: const TextStyle(fontFamily: _display, fontSize: 19, height: 1.7, letterSpacing: 1, color: Colors.white, shadows: _shadow)),
                      ),
              ),
            ),
            IgnorePointer(
              child: AnimatedOpacity(
                opacity: _hint && showActions ? 1 : 0,
                duration: const Duration(milliseconds: 700),
                child: const Padding(
                  padding: EdgeInsets.only(bottom: 12),
                  child: Text('左下角摇杆走动，拖动画面转视角', style: TextStyle(fontSize: 13, color: Colors.white70, shadows: _shadow)),
                ),
              ),
            ),
            // 此刻能做的事：一根麻绳上挂着的许愿木牌
            IgnorePointer(
              ignoring: !showActions,
              child: AnimatedOpacity(
                opacity: showActions ? 1 : 0,
                duration: const Duration(milliseconds: 450),
                child: PlaqueBar(
                    actions: showHalt ? [PlaqueAction('停下', primary: true, onTap: () => _send({'cmd': 'halt'}))] : _actions(),
                    active: showActions || showHalt),
              ),
            ),
            const SizedBox(height: 6),
          ]),
        ),
        // 右边一串竹签：换视角（放在最上层，别的层盖不住它）；放大以后底下多一枚写着倍数的小牌，点一下还原
        if (_ready && _meditateUntil == null)
          Positioned(
            right: 12,
            top: MediaQuery.paddingOf(context).top + 4 + SkyTag.tagHeight + 14,
            // 整串竹签连同缝隙都吞掉点击：点歪了也不会穿到下面的画面里，变成「走过去」
            child: GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () {},
              child: ValueListenableBuilder<double>(
                valueListenable: _zoom,
                builder: (_, z, _) => ViewSlips(
                    mode: _view,
                    zoom: z,
                    available: _viewLocked ? const ['level', 'first'] : ViewSlips.modes,
                    onChanged: _setView,
                    onResetZoom: () => _setZoom(1)),
              ),
            ),
          ),
        // 进殿：先是一对关着的寺门（Unity 第一次加载要一两秒），场景准备好了门往两边推开。放在最上层，门关着时盖住所有按钮
        TempleGate(
            open: _ready,
            title: scene.name,
            onOpened: () {
              _send({'cmd': 'bell'});
              // 门推开了才看得见：地名从这时起再挂三秒
              setState(() => _bannerReplay++);
            }),
      ]),
    );
  }
}

/// 摇杆：铜镜一样的罗盘底，上面一枚能拖的方孔钱。输出 -1..1（往上是负的 dy）
class _Joystick extends StatefulWidget {
  final ValueChanged<Offset> onChanged;

  /// 按下、松开
  final ValueChanged<bool> onHeld;
  const _Joystick({required this.onChanged, required this.onHeld});

  @override
  State<_Joystick> createState() => _JoystickState();
}

class _JoystickState extends State<_Joystick> {
  static const double size = 124, knob = 52;
  Offset _v = Offset.zero;
  Offset _sent = Offset.zero;
  DateTime _last = DateTime(0);

  void _update(Offset local) {
    final c = const Offset(size / 2, size / 2);
    var d = local - c;
    const r = (size - knob) / 2;
    if (d.distance > r) d = d / d.distance * r;
    setState(() => _v = d / r);
    // 最多每 40 毫秒发一次，变化太小不发
    final now = DateTime.now();
    if ((_v - _sent).distance > 0.04 && now.difference(_last).inMilliseconds > 40) {
      _sent = _v;
      _last = now;
      widget.onChanged(_v);
    }
  }

  void _end() {
    setState(() => _v = Offset.zero);
    _sent = Offset.zero;
    widget.onChanged(Offset.zero);
    widget.onHeld(false);
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onPanStart: (d) {
        widget.onHeld(true);
        _update(d.localPosition);
      },
      onPanUpdate: (d) => _update(d.localPosition),
      onPanEnd: (_) => _end(),
      onPanCancel: _end,
      child: SizedBox(
        width: size,
        height: size,
        child: Stack(children: [
          const Positioned.fill(child: JoystickBase()),
          Positioned(
            left: size / 2 - knob / 2 + _v.dx * (size - knob) / 2,
            top: size / 2 - knob / 2 + _v.dy * (size - knob) / 2,
            width: knob,
            height: knob,
            child: const JoystickCoin(),
          ),
        ]),
      ),
    );
  }
}

/// 进殿前选一座：几张大图。direct 给了场景名就不用选，直接进那一座
Future<void> showSanctuaryEntry(BuildContext context, {String? direct}) async {
  // 先拿住导航器：选完以后原来那个界面可能已经重建过了
  final nav = Navigator.of(context);
  if (direct != null) {
    final s = sanctuaryScenes.firstWhere((e) => e.id == direct, orElse: () => sanctuaryScenes.first);
    await nav.push<void>(MaterialPageRoute(builder: (_) => SanctuaryPage(scene: s)));
    return;
  }
  final scene = await showModalBottomSheet<SanctuaryScene>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    barrierColor: Colors.black54,
    builder: (context) => Container(
      decoration: const BoxDecoration(color: Color(0xFF0F0D0B), borderRadius: BorderRadius.vertical(top: Radius.circular(28))),
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 10),
      child: SafeArea(
        top: false,
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Padding(
            padding: EdgeInsets.only(left: 4),
            child: Text('许愿殿', style: TextStyle(fontFamily: _display, fontSize: 26, fontWeight: FontWeight.w700, letterSpacing: 3, color: Colors.white)),
          ),
          const SizedBox(height: 6),
          const Padding(
            padding: EdgeInsets.only(left: 4),
            child: Text('走进去，找个位置坐下。此刻也有别人在这里许愿。', style: TextStyle(fontSize: 13.5, height: 1.6, color: Colors.white60)),
          ),
          const SizedBox(height: 18),
          for (final s in sanctuaryScenes)
            Padding(
              padding: const EdgeInsets.only(bottom: 14),
              child: GestureDetector(
                onTap: () => Navigator.of(context).pop(s),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(20),
                  child: SizedBox(
                    height: 150,
                    child: Stack(fit: StackFit.expand, children: [
                      Image.asset(s.image, fit: BoxFit.cover, errorBuilder: (_, _, _) => const ColoredBox(color: Color(0xFF2A241E))),
                      const DecoratedBox(
                        decoration: BoxDecoration(
                          gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0x00000000), Color(0xB3000000)], stops: [0.35, 1]),
                        ),
                      ),
                      Positioned(
                        left: 18,
                        right: 18,
                        bottom: 14,
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(s.name, style: const TextStyle(fontFamily: _display, fontSize: 24, fontWeight: FontWeight.w700, letterSpacing: 4, color: Colors.white, shadows: _shadow)),
                          const SizedBox(height: 2),
                          Text(s.line, style: const TextStyle(fontSize: 13, color: Colors.white, shadows: _shadow)),
                        ]),
                      ),
                    ]),
                  ),
                ),
              ),
            ),
        ]),
      ),
    ),
  );
  if (scene == null) return;
  await nav.push<void>(MaterialPageRoute(builder: (_) => SanctuaryPage(scene: scene)));
}
