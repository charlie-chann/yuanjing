import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_embed_unity/flutter_embed_unity.dart';
import 'package:yuanjing_engine/yuanjing_engine.dart';

import '../../app/skin.dart';
import '../../app/store.dart';
import '../wish/wish_answer.dart';

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
    places: {'court': '岛上', 'tree': '许愿树下', 'burner': '香炉前', 'hall': '大殿前'},
    goTo: {'court': '起身走走', 'tree': '去许愿树', 'burner': '去香炉', 'hall': '去大殿'},
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
  String? _pendingWish;
  DateTime? _meditateUntil;
  final int _meditateMinutes = 3;

  Timer? _enterTimer;
  Timer? _beatTimer;
  Timer? _tick;
  final _shown = <String>{};
  late final AnimationController _breath = AnimationController(vsync: this, duration: const Duration(seconds: 10));

  @override
  void initState() {
    super.initState();
    resumeUnity();
    // Unity 第一次加载要一两秒，加载好之前发的指令会丢，所以隔一会儿发一次，直到它回了「进来了」
    _enterTimer = Timer.periodic(const Duration(milliseconds: 800), (_) => _enter());
    _enter();
  }

  @override
  void dispose() {
    _enterTimer?.cancel();
    _beatTimer?.cancel();
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
        _shown.clear();
        setState(() {
          _ready = true;
          _moving = true;
          _at = '';
          _seat = -1;
        });
        _send({'cmd': 'audio', 'on': _sound, 'volume': 1});
        _beat();
        _beatTimer?.cancel();
        _beatTimer = Timer.periodic(const Duration(seconds: 6), (_) => _beat());
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
          _seat = -1;
          _at = 'court';
        });
        _beat();
      case 'seated':
        setState(() {
          _moving = false;
          _at = 'seat';
          _seat = (msg['seat'] as num).toInt();
        });
        _beat();
      case 'actionDone':
        setState(() => _busy = false);
      case 'offered':
        _offered(msg['kind'] as String, (msg['slot'] as num?)?.toInt() ?? -1);
      case 'thunder':
        YuanjingHaptics.play('tick');
    }
  }

  // ── 和服务器同步：谁在场、天气、别人留下的心意 ──

  Future<void> _beat({String? action}) async {
    if (!_ready || !store.online) return;
    try {
      final r = await store.api.post('/sanctuary/${scene.id}/beat', {'seat': _seat, 'seats': _seats, 'action': ?action});
      if (!mounted) return;
      final people = (r['people'] as List).cast<Map<String, dynamic>>();
      String clean(Object? n) => '${n ?? ''}'.replaceAll(RegExp(r'[:|]'), ' ');
      _send({'cmd': 'pilgrims', 'list': people.map((p) => '${p['id']}:${p['seat']}:${p['npc'] == true ? 1 : 0}:${clean(p['name'])}').join('|')});
      for (final p in people) {
        if (p['action'] != null) _send({'cmd': 'pact', 'id': p['id'], 'action': p['action']});
      }
      for (final o in [...(r['offerings'] as List), ...(r['mine'] as List)].cast<Map<String, dynamic>>()) {
        final slot = (o['slot'] as num).toInt();
        if (slot < 0 || !_shown.add('$slot')) continue;
        _send({'cmd': 'offerings', 'kind': o['kind'], 'list': '${slot % _slots}'});
      }
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

  // ── 走动和动作 ──

  void _go(String spot) {
    if (_moving || _busy) return;
    YuanjingHaptics.play('tick');
    _send({'cmd': 'goto', 'spot': spot});
  }

  void _sit() {
    if (_moving || _busy) return;
    YuanjingHaptics.play('tick');
    _send({'cmd': 'sit'});
  }

  void _act(String action) {
    if (_moving || _busy) return;
    YuanjingHaptics.play('tick');
    setState(() => _busy = true);
    _send({'cmd': 'act', 'action': action});
    _beat(action: action);
  }

  /// 写下愿望。返回 null 是取消了。
  Future<String?> _askWish(String title, String hint) {
    final c = TextEditingController();
    return showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      barrierColor: Colors.black38,
      builder: (context) => Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
        child: Container(
          decoration: const BoxDecoration(color: Color(0xF2141210), borderRadius: BorderRadius.vertical(top: Radius.circular(26))),
          padding: const EdgeInsets.fromLTRB(24, 22, 24, 18),
          child: SafeArea(
            top: false,
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: const TextStyle(fontFamily: _display, fontSize: 22, fontWeight: FontWeight.w700, letterSpacing: 1.5, color: Colors.white)),
              const SizedBox(height: 14),
              Container(
                decoration: BoxDecoration(color: const Color(0x14FFFFFF), borderRadius: BorderRadius.circular(16), border: Border.all(color: const Color(0x29FFFFFF))),
                padding: const EdgeInsets.fromLTRB(16, 4, 6, 4),
                child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                  Expanded(
                    child: TextField(
                      controller: c,
                      autofocus: true,
                      minLines: 2,
                      maxLines: 4,
                      maxLength: 60,
                      style: const TextStyle(fontSize: 16.5, height: 1.6, color: Colors.white),
                      cursorColor: const Color(0xFFF3D9A0),
                      decoration: InputDecoration(border: InputBorder.none, counterText: '', hintText: hint, hintStyle: const TextStyle(color: Colors.white38)),
                    ),
                  ),
                  MicButton(controller: c, color: Colors.white70),
                ]),
              ),
              const SizedBox(height: 8),
              const Text('写下的话只有你自己看得到。', style: TextStyle(fontSize: 12.5, color: Colors.white54)),
              const SizedBox(height: 14),
              _Pill('写好了', primary: true, expand: true, onTap: () {
                final t = c.text.trim();
                if (t.isNotEmpty) Navigator.of(context).pop(t);
              }),
            ]),
          ),
        ),
      ),
    );
  }

  /// 留下一件心意（红布条、木牌、香、硬币、蜡烛）
  Future<void> _offer(String kind, String label, bool needsWish) async {
    if (_moving || _busy) return;
    String? text;
    if (needsWish) {
      text = await _askWish(label, '把愿望写在上面');
      if (text == null || !mounted) return;
    }
    YuanjingHaptics.play('tick');
    _pendingWish = text;
    setState(() => _busy = true);
    _send({'cmd': 'offer', 'kind': kind});
  }

  Future<void> _offered(String kind, int slot) async {
    final text = _pendingWish;
    _pendingWish = null;
    if (slot >= 0) _shown.add('$slot');
    if (store.online) {
      store.api.post('/sanctuary/${scene.id}/offer', {'kind': kind, 'slot': slot, 'text': ?text}).then((r) {
        final got = (r['got'] as num?)?.toInt() ?? 0;
        if (got > 0 && mounted) {
          store.refresh();
          coinToast(context, got, '在许愿殿留下心意');
        }
      }).catchError((_) {});
    }
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
    setState(() => _busy = true);
    _send({'cmd': 'act', 'action': 'pray'});
    _beat(action: 'pray');
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

  String get _placeName => _at == 'seat' ? scene.seatName : scene.places[_at] ?? '';

  List<Widget> _actions() {
    final here = scene.offers[_at] ?? const <(String, String, bool)>[];
    final offers = [for (var i = 0; i < here.length; i++) _Pill(here[i].$2, primary: i == 0, onTap: () => _offer(here[i].$1, here[i].$2, here[i].$3))];
    final others = [
      for (final spot in scene.places.keys)
        if (spot != _at && spot != 'court') _Pill(scene.goTo[spot]!, onTap: () => _go(spot)),
    ];
    if (_at == 'seat') {
      return [
        _Pill('许愿', primary: true, onTap: _wish),
        _Pill('合掌', onTap: () => _act('pray')),
        _Pill('鞠躬', onTap: () => _act('bow')),
        _Pill('跪拜', onTap: () => _act('kneel')),
        _Pill('静坐', onTap: _meditate),
        _Pill(scene.goTo['court']!, onTap: () => _go('court')),
        ...others,
      ];
    }
    if (_at == 'court') {
      return [
        _Pill('找位置坐下', primary: true, onTap: _sit),
        _Pill('合掌', onTap: () => _act('pray')),
        _Pill('鞠躬', onTap: () => _act('bow')),
        _Pill('跪拜', onTap: () => _act('kneel')),
        ...others,
      ];
    }
    if (_at.isEmpty) return const [];
    return [
      ...offers,
      _Pill('合掌', primary: offers.isEmpty, onTap: () => _act('pray')),
      _Pill('鞠躬', onTap: () => _act('bow')),
      _Pill('跪拜', onTap: () => _act('kneel')),
      _Pill('去坐下', onTap: _sit),
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
                  Text(title, style: const TextStyle(fontSize: 13, color: Colors.white60, letterSpacing: 1)),
                  const SizedBox(height: 10),
                  Wrap(spacing: 8, runSpacing: 8, children: [
                    _Pill('跟着此刻', small: true, primary: value == null, onTap: () => pick(null)),
                    for (final e in names.entries) _Pill(e.value, small: true, primary: value == e.key, onTap: () => pick(e.key)),
                  ]),
                ],
              );
          return Container(
            decoration: const BoxDecoration(color: Color(0xF2141210), borderRadius: BorderRadius.vertical(top: Radius.circular(26))),
            padding: const EdgeInsets.fromLTRB(24, 22, 24, 12),
            child: SafeArea(
              top: false,
              child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
                row('天色', _timeNames, _time, (v) {
                  setState(() => _time = v);
                  setSheet(() {});
                  _sky();
                }),
                const SizedBox(height: 20),
                row('天气', _weatherNames, _weather, (v) {
                  setState(() => _weather = v);
                  setSheet(() {});
                  _sky();
                }),
                const SizedBox(height: 20),
                Row(children: [
                  const Text('声音', style: TextStyle(fontSize: 13, color: Colors.white60, letterSpacing: 1)),
                  const Spacer(),
                  _Pill(_sound ? '开着' : '关了', small: true, primary: _sound, onTap: () {
                    setState(() => _sound = !_sound);
                    setSheet(() {});
                    _send({'cmd': 'audio', 'on': _sound, 'volume': 1});
                  }),
                ]),
                const SizedBox(height: 10),
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
    return Scaffold(
      backgroundColor: Colors.black,
      resizeToAvoidBottomInset: false,
      body: Stack(fit: StackFit.expand, children: [
        EmbedUnity(onMessageFromUnity: _onUnity),
        // 拖动环顾四周，点远处走过去。手势在 Flutter 这层接，再转给 Unity。
        GestureDetector(
          behavior: HitTestBehavior.opaque,
          onPanUpdate: (d) => _send({'cmd': 'look', 'dx': -d.delta.dx / size.width, 'dy': d.delta.dy / size.height}),
          onTapUp: (d) {
            if (_ready && !_moving && !_busy && !meditating) _send({'cmd': 'tap', 'x': d.localPosition.dx / size.width, 'y': d.localPosition.dy / size.height});
          },
        ),
        // 摇杆：左下角，按住拖动走路
        if (_ready && _meditateUntil == null)
          Positioned(
            left: 22,
            bottom: MediaQuery.paddingOf(context).bottom + 84,
            child: _Joystick(onChanged: (v) => _send({'cmd': 'move', 'x': v.dx, 'y': -v.dy})),
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
        // Unity 第一次加载要一两秒，先盖一层黑
        IgnorePointer(
          child: AnimatedOpacity(
            opacity: _ready ? 0 : 1,
            duration: const Duration(milliseconds: 1200),
            child: ColoredBox(
              color: Colors.black,
              child: Center(
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  Text(scene.name, style: const TextStyle(fontFamily: _display, fontSize: 30, fontWeight: FontWeight.w700, letterSpacing: 10, color: Colors.white)),
                  const SizedBox(height: 12),
                  const Text('正在进殿…', style: TextStyle(color: Colors.white54, fontSize: 14, letterSpacing: 3)),
                ]),
              ),
            ),
          ),
        ),
        SafeArea(
          child: Column(children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 4, 14, 0),
              child: Row(children: [
                GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () => Navigator.of(context).maybePop(),
                  child: const Padding(
                    padding: EdgeInsets.fromLTRB(14, 10, 14, 10),
                    child: Text('‹ 离开', style: TextStyle(fontSize: 15, color: Colors.white, shadows: _shadow)),
                  ),
                ),
                const Spacer(),
                if (_ready && !meditating) _Pill('${_timeNames[_timeShown]} · ${_weatherNames[_weatherShown]}', small: true, onTap: _showSky),
              ]),
            ),
            // 现在在哪、殿里有多少人
            IgnorePointer(
              child: AnimatedOpacity(
                opacity: _ready && !_moving && !meditating && _placeName.isNotEmpty ? 1 : 0,
                duration: const Duration(milliseconds: 700),
                child: Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Column(children: [
                    Text(_placeName, style: const TextStyle(fontFamily: _display, fontSize: 22, fontWeight: FontWeight.w700, letterSpacing: 6, color: Colors.white, shadows: _shadow)),
                    if (_count > 1) ...[
                      const SizedBox(height: 4),
                      Text('此刻殿里有 $_count 个人', style: const TextStyle(fontSize: 12.5, letterSpacing: 1, color: Colors.white70, shadows: _shadow)),
                    ],
                  ]),
                ),
              ),
            ),
            const Expanded(child: IgnorePointer(child: SizedBox.expand())),
            if (meditating) ...[
              Text('${left.inMinutes}:${(left.inSeconds % 60).toString().padLeft(2, '0')}',
                  style: const TextStyle(fontSize: 15, letterSpacing: 2, color: Colors.white70, fontFeatures: [FontFeature.tabularFigures()])),
              const SizedBox(height: 14),
              _Pill('结束静坐', small: true, onTap: _endMeditation),
              const SizedBox(height: 26),
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
            // 此刻能做的事
            IgnorePointer(
              ignoring: !showActions,
              child: AnimatedOpacity(
                opacity: showActions ? 1 : 0,
                duration: const Duration(milliseconds: 450),
                child: SizedBox(
                  height: 48,
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: 18),
                    children: [
                      for (final w in _actions()) Padding(padding: const EdgeInsets.only(right: 9), child: Center(child: w)),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 14),
          ]),
        ),
      ]),
    );
  }
}

/// 摇杆：半透明的圆底，中间一个能拖的圆钮。输出 -1..1（往上是负的 dy）
class _Joystick extends StatefulWidget {
  final ValueChanged<Offset> onChanged;
  const _Joystick({required this.onChanged});

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
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onPanStart: (d) => _update(d.localPosition),
      onPanUpdate: (d) => _update(d.localPosition),
      onPanEnd: (_) => _end(),
      onPanCancel: _end,
      child: SizedBox(
        width: size,
        height: size,
        child: Stack(children: [
          Container(
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: const Color(0x3312100E),
              border: Border.all(color: const Color(0x55FFFFFF), width: 1),
            ),
          ),
          Positioned(
            left: size / 2 - knob / 2 + _v.dx * (size - knob) / 2,
            top: size / 2 - knob / 2 + _v.dy * (size - knob) / 2,
            child: Container(
              width: knob,
              height: knob,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: const Color(0xCCF0D49A),
                boxShadow: const [BoxShadow(color: Color(0x66000000), blurRadius: 10)],
              ),
            ),
          ),
        ]),
      ),
    );
  }
}

/// 压在三维画面上的按钮：深色半透明底，细白边。主要的那个用暖金色。
/// （Unity 画面是原生视图，Flutter 的毛玻璃对它不起作用，所以用半透明底。）
class _Pill extends StatelessWidget {
  final String label;
  final VoidCallback? onTap;
  final bool primary;
  final bool small;
  final bool expand;
  const _Pill(this.label, {this.onTap, this.primary = false, this.small = false, this.expand = false});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        height: small ? 36 : 46,
        width: expand ? double.infinity : null,
        alignment: expand ? Alignment.center : null,
        padding: EdgeInsets.symmetric(horizontal: small ? 14 : 20),
        decoration: BoxDecoration(
          color: primary ? const Color(0xF2F0D49A) : const Color(0x8C12100E),
          borderRadius: BorderRadius.circular(99),
          border: Border.all(color: primary ? const Color(0x00000000) : const Color(0x47FFFFFF), width: 0.8),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Text(label,
              style: TextStyle(
                fontSize: small ? 13.5 : 15.5,
                fontWeight: FontWeight.w600,
                letterSpacing: 0.5,
                color: primary ? const Color(0xFF2A1A08) : Colors.white,
              )),
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
