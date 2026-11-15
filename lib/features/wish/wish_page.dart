import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:yuanjing_engine/yuanjing_engine.dart';

import '../sanctuary/sanctuary_page.dart';
import '../../app/muse.dart';
import '../../app/skin.dart';
import '../../app/store.dart';
import 'wish_answer.dart';
import 'wish_category.dart';

const _display = 'YuanjingSerif';

/// 首页：每日许愿。背景是原生渲染的仪式舞台，Flutter 只画上面这层界面。
class WishPage extends StatefulWidget {
  /// 仪式进行时置为 true，外壳据此收起底栏
  final ValueNotifier<bool>? immersive;

  /// 当前是否正显示这一页；切走时暂停舞台渲染
  final bool active;

  const WishPage({super.key, this.immersive, this.active = true});

  @override
  State<WishPage> createState() => _WishPageState();
}

class _WishPageState extends State<WishPage> with SingleTickerProviderStateMixin {
  final _stage = WishStageController(scene: wishCategories.first.scene);
  final _text = TextEditingController();
  final _focus = FocusNode();
  late final AnimationController _shake = AnimationController(vsync: this, duration: const Duration(milliseconds: 420));
  final _timers = <Timer>[];

  WishCategory _cat = wishCategories.first;
  bool _ceremony = false;
  String? _line;
  String? _notice;
  String? _pending;

  /// 这一次许愿匹配到的回应；仪式结束后在卡片里展示，连不上服务器时为 null
  WishAnswer? _answer;
  bool _showAnswer = false;
  int _playing = -1;

  @override
  void initState() {
    super.initState();
    _stage.onDone = _finish;
    // 写到一半的心愿留着，下次打开还在
    _text.text = store.drafts['wish'] ?? '';
    _text.addListener(() => store.saveDraft('wish', _text.text));
  }

  @override
  void didUpdateWidget(WishPage old) {
    super.didUpdateWidget(old);
    if (old.active != widget.active) {
      _stage.setPaused(!widget.active);
      if (widget.active) YuanjingAudio.bed(_cat.scene);
    }
  }

  @override
  void dispose() {
    for (final t in _timers) {
      t.cancel();
    }
    _stage.dispose();
    _text.dispose();
    _focus.dispose();
    _shake.dispose();
    super.dispose();
  }

  void _pick(WishCategory c) {
    if (c == _cat || _ceremony) return;
    YuanjingHaptics.play('tick');
    YuanjingAudio.sfx('pick');
    setState(() => _cat = c);
    _stage.setScene(c.scene);
  }

  /// [preview] 只在调试版里用：长按按钮不写心愿直接看这一场仪式，不记心愿、不加金币。
  Future<void> _makeWish({bool preview = false}) async {
    final text = _text.text.trim();
    if (text.isEmpty && !preview) {
      _shake.forward(from: 0);
      _say('先写下一个心愿');
      return;
    }
    _focus.unfocus();
    // 按下的同时去匹配回应、下载语音，和仪式开场并行
    final answerFuture = text.isEmpty ? Future<WishAnswer?>.value(null) : WishAnswer.fetch(text, _cat.scene);
    final length = await _stage.play();
    if (length == null || !mounted) return;
    _pending = preview ? null : text;
    widget.immersive?.value = true;
    setState(() {
      _ceremony = true;
      _line = null;
      _answer = null;
      _showAnswer = false;
    });
    final ms = length.inMilliseconds;
    // 回应最多等到仪式的第一句该出来的时候；来不及就用这一类原来的三句引导语
    final answer = await answerFuture.timeout(Duration(milliseconds: (ms * 0.07).round()), onTimeout: () => null);
    if (!mounted || !_ceremony) return;
    if (answer != null && answer.isSupport) {
      // 写下的话里有危险的说法：不播回应，仪式结束后显示求助信息
      _answer = answer;
      return;
    }
    if (answer == null) {
      for (final (i, at) in [0.07, 0.38, 0.70].indexed) {
        _timers.add(Timer(Duration(milliseconds: (ms * at).round()), () {
          if (!mounted || !_ceremony) return;
          setState(() => _line = _cat.lines[i]);
          YuanjingVoice.play('assets/voice/${_cat.scene}_${i + 1}.m4a');
        }));
      }
      return;
    }
    _answer = answer;
    // 仪式里先说开场和核心两句：开场一出来就播，核心句接在开场后面，但不早于仪式的四成
    _timers.add(Timer(Duration(milliseconds: (ms * 0.07).round()), () async {
      if (!mounted || !_ceremony) return;
      setState(() => _line = answer.lines[0]);
      final d = await answer.play(0);
      final wait = Duration(milliseconds: math.max(d.inMilliseconds + 300, (ms * 0.33).round()));
      _timers.add(Timer(wait, () {
        if (!mounted || !_ceremony) return;
        setState(() => _line = answer.lines[1]);
        answer.play(1);
      }));
    }));
  }

  /// 仪式结束后：卡片里显示完整的四句，接着播行动句和收尾
  Future<void> _revealAnswer() async {
    final a = _answer;
    if (a == null || a.isSupport) return;
    setState(() {
      _showAnswer = true;
      _playing = 2;
    });
    await Future.delayed(const Duration(milliseconds: 900));
    for (final i in [2, 3]) {
      if (!mounted || !_showAnswer || _answer != a) return;
      setState(() => _playing = i);
      final d = await a.play(i);
      await Future.delayed(d + const Duration(milliseconds: 350));
    }
    if (mounted && _answer == a) setState(() => _playing = -1);
  }

  void _closeAnswer() {
    YuanjingVoice.stop();
    setState(() {
      _showAnswer = false;
      _playing = -1;
    });
  }

  void _finish() {
    if (!mounted) return;
    final text = _pending;
    widget.immersive?.value = false;
    setState(() {
      _ceremony = false;
      _line = null;
      if (text != null) _text.clear();
      _notice = text == null ? null : '心愿已收下';
    });
    _pending = null;
    if (_answer?.isSupport == true) {
      _answer = null;
      _showSupport();
    } else if (_answer != null) {
      _revealAnswer();
    }
    if (text != null) {
      final scene = _cat.scene;
      store.addWish(scene, text).then((got) {
        if (mounted && got > 0) setState(() => _notice = '今日许愿完成，金币 +$got');
      }).catchError((e) {
        if (mounted) setState(() => _notice = '$e');
      });
    }
    _timers.add(Timer(const Duration(milliseconds: 2800), () {
      if (mounted) setState(() => _notice = null);
    }));
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

  void _say(String text) {
    setState(() => _notice = text);
    _timers.add(Timer(const Duration(milliseconds: 2200), () {
      if (mounted && _notice == text) setState(() => _notice = null);
    }));
  }

  /// 今天许下的心愿，新的在前
  List<Wish> get _today => [
        for (final w in store.wishes)
          if (AppStore.day(DateTime.fromMillisecondsSinceEpoch(w['ts'] as int)) == AppStore.day())
            Wish(categoryOf(w['scene'] as String), w['text'] as String, DateTime.fromMillisecondsSinceEpoch(w['ts'] as int)),
      ];

  void _showWishes() {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      barrierColor: Colors.black54,
      builder: (_) => _WishSheet(wishes: _today),
    );
  }

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final date = '${now.month}月${now.day}日　周${'一二三四五六日'[now.weekday - 1]}';
    final idle = !_ceremony && !_showAnswer;
    return Scaffold(
      resizeToAvoidBottomInset: true,
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          WishStage(controller: _stage),
          // 底部压暗，保证文字可读；仪式时撤掉，让画面完整
          IgnorePointer(
            child: AnimatedOpacity(
              opacity: idle ? 1 : 0,
              duration: const Duration(milliseconds: 700),
              child: const DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [Color(0x73000000), Color(0x00000000), Color(0x00000000), Color(0xB3000000)],
                    stops: [0, 0.24, 0.5, 1],
                  ),
                ),
              ),
            ),
          ),
          SafeArea(
            child: IgnorePointer(
              ignoring: !idle,
              child: AnimatedOpacity(
                opacity: idle ? 1 : 0,
                duration: Duration(milliseconds: idle ? 900 : 500),
                curve: Curves.easeOut,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(22, 10, 22, 66),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(children: [
                        Text(date, style: const TextStyle(fontSize: 13, color: Colors.white70, letterSpacing: 0.8)),
                        const Spacer(),
                        _CoinPill(coins: store.coins),
                      ]),
                      const SizedBox(height: 16),
                      const Text('今天，想让\n什么发生？',
                          style: TextStyle(fontFamily: _display, fontSize: 33, height: 1.3, fontWeight: FontWeight.w700, letterSpacing: 1.2, color: Colors.white)),
                      const SizedBox(height: 14),
                      // 湖心小寺的入口：进去是可以走动的俯视三维小岛，和别人一起许愿
                      Align(
                        alignment: Alignment.centerLeft,
                        child: GestureDetector(
                          behavior: HitTestBehavior.opaque,
                          onTap: () async {
                            YuanjingAudio.sfx('tap');
                            _stage.setPaused(true);
                            YuanjingAudio.bed(null);
                            await showSanctuaryEntry(context, direct: 'islet');
                            _stage.setPaused(false);
                            YuanjingAudio.bed(_cat.scene);
                          },
                          child: Container(
                            height: 36,
                            padding: const EdgeInsets.symmetric(horizontal: 14),
                            decoration: BoxDecoration(
                              color: const Color(0x59000000),
                              borderRadius: BorderRadius.circular(99),
                              border: Border.all(color: Colors.white38),
                            ),
                            child: const Row(mainAxisSize: MainAxisSize.min, children: [
                              Text('湖心小寺', style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: Colors.white)),
                              SizedBox(width: 6),
                              Text('›', style: TextStyle(fontSize: 16, color: Colors.white70)),
                            ]),
                          ),
                        ),
                      ),
                      const Spacer(),
                      Center(
                        child: AnimatedSwitcher(
                          duration: const Duration(milliseconds: 500),
                          child: Text(_cat.ritual,
                              key: ValueKey(_cat.scene),
                              style: const TextStyle(fontFamily: _display, fontSize: 15, fontWeight: FontWeight.w500, letterSpacing: 6, color: Colors.white70)),
                        ),
                      ),
                      const SizedBox(height: 18),
                      _Composer(
                        category: _cat,
                        onPick: _pick,
                        text: _text,
                        focus: _focus,
                        shake: _shake,
                        onWish: _makeWish,
                        onPreview: kDebugMode ? () => _makeWish(preview: true) : null,
                        wishCount: _today.length,
                        onShowWishes: _showWishes,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
          // 引导语出现时在底部垫一层暗色，亮场景上也看得清
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            height: 340,
            child: IgnorePointer(
              child: AnimatedOpacity(
                opacity: _ceremony && _line != null ? 1 : 0,
                duration: const Duration(milliseconds: 900),
                child: const DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [Color(0x00000000), Color(0x8C000000), Color(0xB3000000)],
                      stops: [0, 0.55, 1],
                    ),
                  ),
                ),
              ),
            ),
          ),
          // 仪式里的引导语
          Positioned(
            left: 32,
            right: 32,
            bottom: 132,
            child: IgnorePointer(
              child: AnimatedSwitcher(
                duration: const Duration(milliseconds: 900),
                child: Text(
                  _ceremony ? (_line ?? '') : '',
                  key: ValueKey(_line),
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontFamily: _display,
                    fontSize: 22,
                    fontWeight: FontWeight.w700,
                    height: 1.6,
                    letterSpacing: 2,
                    color: Colors.white,
                    shadows: [Shadow(color: Colors.black87, blurRadius: 18), Shadow(color: Colors.black54, blurRadius: 4)],
                  ),
                ),
              ),
            ),
          ),
          // 仪式结束后的回应卡片
          Positioned(
            left: 16,
            right: 16,
            bottom: MediaQuery.paddingOf(context).bottom + 74,
            child: IgnorePointer(
              ignoring: !_showAnswer,
              child: AnimatedSlide(
                offset: _showAnswer ? Offset.zero : const Offset(0, 0.15),
                duration: const Duration(milliseconds: 600),
                curve: Curves.easeOutCubic,
                child: AnimatedOpacity(
                  opacity: _showAnswer ? 1 : 0,
                  duration: const Duration(milliseconds: 600),
                  child: _answer == null || _answer!.isSupport ? const SizedBox.shrink() : _AnswerCard(answer: _answer!, playing: _playing, category: _cat, onClose: _closeAnswer),
                ),
              ),
            ),
          ),
          // 顶部的小提示
          Positioned(
            left: 0,
            right: 0,
            top: MediaQuery.paddingOf(context).top + 54,
            child: IgnorePointer(
              child: Center(
                child: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 350),
                  transitionBuilder: (child, a) => FadeTransition(
                    opacity: a,
                    child: SlideTransition(position: Tween(begin: const Offset(0, -0.4), end: Offset.zero).animate(a), child: child),
                  ),
                  child: _notice == null
                      ? const SizedBox.shrink()
                      : Container(
                          key: ValueKey(_notice),
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
                          decoration: BoxDecoration(
                            color: const Color(0xD9141210),
                            borderRadius: BorderRadius.circular(99),
                            border: Border.all(color: Colors.white24),
                          ),
                          child: Text(_notice!, style: const TextStyle(fontSize: 13.5, color: Colors.white)),
                        ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// 宇宙的回应：四句话，正在念的那句亮起来
class _AnswerCard extends StatelessWidget {
  final WishAnswer answer;
  final int playing;
  final WishCategory category;
  final VoidCallback onClose;
  const _AnswerCard({required this.answer, required this.playing, required this.category, required this.onClose});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(22, 20, 22, 16),
      decoration: BoxDecoration(
        color: const Color(0xE6100D0A),
        borderRadius: BorderRadius.circular(26),
        border: Border.all(color: category.light.withValues(alpha: 0.45)),
        boxShadow: [BoxShadow(color: category.deep.withValues(alpha: 0.35), blurRadius: 40, offset: const Offset(0, 12))],
      ),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(width: 7, height: 7, decoration: BoxDecoration(shape: BoxShape.circle, gradient: LinearGradient(colors: [category.light, category.deep]))),
          const SizedBox(width: 8),
          Text('宇宙的回应 · ${answer.intentName}', style: TextStyle(fontSize: 12.5, letterSpacing: 1.5, color: category.light.withValues(alpha: 0.85))),
        ]),
        const SizedBox(height: 14),
        for (final (i, line) in answer.lines.indexed)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: AnimatedDefaultTextStyle(
              duration: const Duration(milliseconds: 400),
              style: TextStyle(
                fontFamily: _display,
                fontSize: i == 1 ? 18.5 : 16,
                height: 1.65,
                fontWeight: i == 1 ? FontWeight.w700 : FontWeight.w500,
                color: playing == i ? Colors.white : (i == 1 ? Colors.white.withValues(alpha: 0.92) : Colors.white70),
              ),
              child: Text(line),
            ),
          ),
        const SizedBox(height: 6),
        Align(
          alignment: Alignment.centerRight,
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: () {
              YuanjingHaptics.play('tick');
              onClose();
            },
            child: Container(
              height: 40,
              padding: const EdgeInsets.symmetric(horizontal: 22),
              alignment: Alignment.center,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(99),
                gradient: LinearGradient(colors: [category.light, category.deep]),
              ),
              child: const Text('收下了', style: TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700, color: Color(0xFF2A1708))),
            ),
          ),
        ),
      ]),
    );
  }
}

/// 金币余额：一枚方孔钱加数字
class _CoinPill extends StatelessWidget {
  final int coins;
  const _CoinPill({required this.coins});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 34,
      padding: const EdgeInsets.only(left: 8, right: 13),
      decoration: BoxDecoration(
        color: const Color(0x59000000),
        borderRadius: BorderRadius.circular(99),
        border: Border.all(color: const Color(0x66F6D58A)),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Container(
          width: 19,
          height: 19,
          alignment: Alignment.center,
          decoration: const BoxDecoration(
            shape: BoxShape.circle,
            gradient: RadialGradient(center: Alignment(-0.4, -0.5), colors: [Color(0xFFFFF4C8), Color(0xFFF0C356), Color(0xFFB07A18)], stops: [0, 0.45, 1]),
          ),
          child: Container(width: 6, height: 6, color: const Color(0xFF6B4708)),
        ),
        const SizedBox(width: 7),
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 400),
          transitionBuilder: (c, a) => ScaleTransition(scale: Tween(begin: 1.35, end: 1.0).animate(a), child: FadeTransition(opacity: a, child: c)),
          child: Text('$coins',
              key: ValueKey(coins),
              style: const TextStyle(fontFamily: 'Didot', fontSize: 19, fontWeight: FontWeight.w700, color: Color(0xFFFBE7B0), height: 1.1)),
        ),
      ]),
    );
  }
}

class _Composer extends StatelessWidget {
  final WishCategory category;
  final ValueChanged<WishCategory> onPick;
  final TextEditingController text;
  final FocusNode focus;
  final Animation<double> shake;
  final VoidCallback onWish;
  final VoidCallback? onPreview;
  final int wishCount;
  final VoidCallback onShowWishes;

  const _Composer({
    required this.category,
    required this.onPick,
    required this.text,
    required this.focus,
    required this.shake,
    required this.onWish,
    this.onPreview,
    required this.wishCount,
    required this.onShowWishes,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          height: 38,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            clipBehavior: Clip.none,
            itemCount: wishCategories.length,
            separatorBuilder: (_, _) => const SizedBox(width: 8),
            itemBuilder: (_, i) {
              final c = wishCategories[i];
              final on = c == category;
              return GestureDetector(
                onTap: () => onPick(c),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 280),
                  curve: Curves.easeOut,
                  padding: const EdgeInsets.symmetric(horizontal: 17),
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(99),
                    gradient: on ? LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [c.light, c.deep]) : null,
                    color: on ? null : const Color(0x40000000),
                    border: Border.all(color: on ? Colors.white54 : Colors.white24),
                    boxShadow: on ? [BoxShadow(color: c.deep.withValues(alpha: 0.55), blurRadius: 16, offset: const Offset(0, 5))] : null,
                  ),
                  child: Text(c.name,
                      style: TextStyle(
                        fontSize: 14.5,
                        fontWeight: on ? FontWeight.w700 : FontWeight.w400,
                        color: on ? const Color(0xFF2A1708) : Colors.white.withValues(alpha: 0.86),
                      )),
                ),
              );
            },
          ),
        ),
        const SizedBox(height: 14),
        AnimatedBuilder(
          animation: shake,
          builder: (_, child) {
            final t = shake.value;
            final dx = t == 0 ? 0.0 : 7 * (1 - t) * (t * 22 % 2 < 1 ? 1 : -1);
            return Transform.translate(offset: Offset(dx, 0), child: child);
          },
          child: Container(
            padding: const EdgeInsets.fromLTRB(18, 6, 8, 8),
            decoration: BoxDecoration(
              color: const Color(0x66080604),
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: Colors.white24),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                  child: TextField(
                    controller: text,
                    focusNode: focus,
                    minLines: 1,
                    maxLines: 3,
                    textInputAction: TextInputAction.done,
                    style: const TextStyle(fontFamily: _display, fontSize: 17, height: 1.5, fontWeight: FontWeight.w500, color: Colors.white),
                    decoration: InputDecoration(
                      border: InputBorder.none,
                      isDense: true,
                      contentPadding: const EdgeInsets.symmetric(vertical: 12),
                      hintText: category.hint,
                      hintMaxLines: 2,
                      hintStyle: const TextStyle(fontFamily: _display, fontSize: 16, height: 1.5, fontWeight: FontWeight.w500, color: Colors.white54),
                    ),
                  ),
                ),
                Padding(padding: const EdgeInsets.only(bottom: 5), child: MicButton(controller: text, color: Colors.white)),
                const SizedBox(width: 8),
                _WishButton(category: category, onTap: onWish, onLongPress: onPreview),
              ],
            ),
          ),
        ),
        const SizedBox(height: 10),
        SizedBox(
          height: 30,
          child: wishCount == 0
              ? const Center(child: Text('写下来，再轻轻按下去', style: TextStyle(fontSize: 12.5, color: Colors.white54)))
              : GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: onShowWishes,
                  child: Center(
                    child: Text('今天许下了 $wishCount 个心愿，点这里看看',
                        style: const TextStyle(fontSize: 12.5, color: Colors.white70, decoration: TextDecoration.underline, decorationColor: Colors.white38)),
                  ),
                ),
        ),
      ],
    );
  }
}

class _WishButton extends StatefulWidget {
  final WishCategory category;
  final VoidCallback onTap;
  final VoidCallback? onLongPress;
  const _WishButton({required this.category, required this.onTap, this.onLongPress});

  @override
  State<_WishButton> createState() => _WishButtonState();
}

class _WishButtonState extends State<_WishButton> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    final c = widget.category;
    return GestureDetector(
      onLongPress: widget.onLongPress == null
          ? null
          : () {
              setState(() => _down = false);
              widget.onLongPress!();
            },
      onTapDown: (_) => setState(() => _down = true),
      onTapCancel: () => setState(() => _down = false),
      onTapUp: (_) {
        setState(() => _down = false);
        YuanjingHaptics.play('tick');
        YuanjingAudio.sfx('tap');
        widget.onTap();
      },
      child: AnimatedScale(
        scale: _down ? 0.94 : 1,
        duration: const Duration(milliseconds: 120),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 350),
          height: 46,
          padding: const EdgeInsets.symmetric(horizontal: 20),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(99),
            gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [c.light, c.deep]),
            border: Border.all(color: Colors.white60, width: 0.8),
            boxShadow: [
              BoxShadow(color: c.deep.withValues(alpha: _down ? 0.25 : 0.6), blurRadius: _down ? 6 : 18, offset: Offset(0, _down ? 2 : 7)),
            ],
          ),
          child: const Text('许下心愿', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFF2A1708), letterSpacing: 1)),
        ),
      ),
    );
  }
}

class _WishSheet extends StatelessWidget {
  final List<Wish> wishes;
  const _WishSheet({required this.wishes});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.fromLTRB(10, 0, 10, 10),
      padding: const EdgeInsets.fromLTRB(22, 14, 22, 26),
      decoration: BoxDecoration(
        color: const Color(0xF2141210),
        borderRadius: BorderRadius.circular(30),
        border: Border.all(color: Colors.white24),
      ),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(child: Container(width: 38, height: 4, decoration: BoxDecoration(color: Colors.white24, borderRadius: BorderRadius.circular(2)))),
            const SizedBox(height: 18),
            const Text('今天许下的', style: TextStyle(fontFamily: _display, fontSize: 21, fontWeight: FontWeight.w700, color: Colors.white)),
            const SizedBox(height: 8),
            for (final w in wishes)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 11),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Container(
                    margin: const EdgeInsets.only(top: 3),
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 1.5),
                    decoration: BoxDecoration(borderRadius: BorderRadius.circular(99), border: Border.all(color: w.category.light.withValues(alpha: 0.7))),
                    child: Text(w.category.name, style: TextStyle(fontSize: 11.5, color: w.category.light)),
                  ),
                  const SizedBox(width: 12),
                  Expanded(child: Text(w.text, style: const TextStyle(fontFamily: _display, fontSize: 16.5, height: 1.5, color: Colors.white))),
                  const SizedBox(width: 12),
                  Text('${w.at.hour.toString().padLeft(2, '0')}:${w.at.minute.toString().padLeft(2, '0')}',
                      style: const TextStyle(fontFamily: 'Didot', fontSize: 14, color: Colors.white54)),
                ]),
              ),
          ],
        ),
      ),
    );
  }
}
