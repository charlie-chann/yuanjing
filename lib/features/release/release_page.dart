import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:yuanjing_engine/yuanjing_engine.dart';

import '../../app/skin.dart';
import '../../app/store.dart';
import 'release_data.dart';

const _display = 'YuanjingSerif';

enum _Step { input, reading, ritual, done }

/// 卡点释放：写下卡点 → 看见它 → 一场释放仪式 → 一句肯定语收束。
///
/// 这是私密功能：写下的内容只在这一页的内存里，做完就清掉，不保存、不进广场。
/// 背景是原生渲染的释放场景，Flutter 只画上面这层界面。作为底栏「释放」页，默认用当前皮肤对应的释放方式。
class ReleasePage extends StatefulWidget {
  /// 仪式进行时置为 true，外壳据此收起底栏
  final ValueNotifier<bool>? immersive;

  /// 当前是否正显示这一页；切走时暂停舞台渲染
  final bool active;

  const ReleasePage({super.key, this.immersive, this.active = true});

  @override
  State<ReleasePage> createState() => _ReleasePageState();
}

class _ReleasePageState extends State<ReleasePage> with TickerProviderStateMixin {
  late final _stage = WishStageController(scene: _style.scene);
  final _text = TextEditingController();
  final _focus = FocusNode();
  final _picked = <String>{};
  final _timers = <Timer>[];

  /// 纸条飞进纸船（吊篮、坩埚）的那一下
  late final AnimationController _note = AnimationController(vsync: this, duration: const Duration(milliseconds: 1500));

  /// 一轮呼吸：前四成吸气，后六成呼气
  late final AnimationController _breath = AnimationController(vsync: this, duration: const Duration(seconds: 10));

  _Step _step = _Step.input;
  /// 默认用当前皮肤对应的释放方式
  ReleaseStyle _style = releaseStyles.firstWhere((s) => s.scene == store.skin.release, orElse: () => releaseStyles.first);
  ReleaseDepth _depth = lightRelease;
  ReleaseReading? _reading;
  String? _line;
  String? _notice;
  bool _support = false;
  bool _breathing = false;
  bool _noteShown = false;

  /// 正在等服务器读用户写的话
  bool _thinking = false;

  /// 仪式进行到哪一段（呼吸、放松、看见、释放、安住），空着表示还在放纸条
  String _phase = '';
  bool _quick = false;

  @override
  void initState() {
    super.initState();
    _stage.onDone = _onDone;
    _focus.addListener(() {
      if (mounted) setState(() {});
    });
  }

  @override
  void didUpdateWidget(ReleasePage old) {
    super.didUpdateWidget(old);
    if (old.active != widget.active) {
      _stage.setPaused(!widget.active);
      if (widget.active) YuanjingAudio.bed(_style.bed);
    }
  }

  @override
  void dispose() {
    _cancelTimers();
    YuanjingVoice.stop();
    _stage.dispose();
    _text.dispose();
    _focus.dispose();
    _note.dispose();
    _breath.dispose();
    super.dispose();
  }

  void _cancelTimers() {
    for (final t in _timers) {
      t.cancel();
    }
    _timers.clear();
  }

  /// 仪式里的定时步骤：页面还在、仪式没被中途结束才执行
  void _after(int ms, VoidCallback run) {
    _timers.add(Timer(Duration(milliseconds: ms), () {
      if (mounted && _step == _Step.ritual) run();
    }));
  }

  void _say(String text) {
    setState(() => _notice = text);
    _timers.add(Timer(const Duration(milliseconds: 2400), () {
      if (mounted && _notice == text) setState(() => _notice = null);
    }));
  }

  String get _noteText {
    final text = _text.text.trim();
    if (text.isNotEmpty) return text;
    return stickings.where((s) => _picked.contains(s.key)).map((s) => s.name).join('、');
  }

  void _toggle(Sticking s) {
    YuanjingHaptics.play('tick');
    YuanjingAudio.sfx('pick');
    setState(() => _picked.contains(s.key) ? _picked.remove(s.key) : _picked.add(s.key));
  }

  /// 输入完成，进入解读。[safe] 表示用户已经看过求助信息并选择继续。
  Future<void> _see({bool safe = false}) async {
    if (_thinking) return;
    final text = _text.text.trim();
    var reading = readSticking(text, _picked);
    if (reading == null) {
      _say('先选一个标签，或者写一句话');
      return;
    }
    _focus.unfocus();
    if (!safe && needsSupport(text)) {
      setState(() => _support = true);
      return;
    }
    // 写了字又连得上服务器：让服务器读一下（配了大模型时会针对写的事情回应），最多等八秒
    if (text.isNotEmpty && store.online) {
      setState(() => _thinking = true);
      try {
        final tags = [for (final k in stickings) if (_picked.contains(k.key)) k.name];
        final r = await store.api.post('/ai/reading', {'text': text, 'tags': tags}).timeout(const Duration(seconds: 8));
        if (r['support'] == true && !safe) {
          if (mounted) setState(() => _support = true);
          return;
        }
        if (r['source'] == 'llm') {
          final k = stickings.firstWhere((x) => x.key == r['key'], orElse: () => reading!.sticking);
          reading = ReleaseReading(k, (r['emotions'] as List).cast<String>(), r['deep'] == true, r['empathy'] as String, r['belief'] as String);
        }
      } catch (_) {
        // 服务器读不了就用本机规则
      } finally {
        if (mounted) setState(() => _thinking = false);
      }
      if (!mounted) return;
    }
    final result = reading!;
    setState(() {
      _support = false;
      _reading = result;
      _depth = result.deep ? deepRelease : lightRelease;
      _step = _Step.reading;
    });
  }

  /// 会员皮肤对应的三种方式，要么开了会员，要么它正好是当前皮肤的那一种
  bool _locked(ReleaseStyle s) => !store.member && s.scene != store.skin.release && skins.any((k) => k.release == s.scene && k.member);

  void _pickStyle(ReleaseStyle s) {
    if (s == _style) return;
    if (_locked(s)) {
      _say('「${s.name}」是会员皮肤的释放方式');
      return;
    }
    YuanjingHaptics.play('tick');
    YuanjingAudio.sfx('pick');
    setState(() => _style = s);
    _stage.setScene(s.scene);
  }

  /// 开始仪式。[quick] 只在调试版里用：长按按钮跳过呼吸，十几秒看完整场画面。
  void _begin({bool quick = false}) {
    _cancelTimers();
    widget.immersive?.value = true;
    _quick = quick;
    setState(() {
      _step = _Step.ritual;
      _notice = null;
      _line = _style.lines[0];
      _noteShown = true;
      _breathing = false;
      _phase = '';
    });
    _note.value = 0;
    YuanjingVoice.play('assets/voice/${_style.scene}_1.m4a');
    _after(1500, () => _note.forward());
    _after(noteTime.inMilliseconds, () {
      setState(() => _noteShown = false);
      YuanjingHaptics.play('tick');
      if (quick) {
        _play(const Duration(seconds: 14));
      } else {
        _breathe(0);
      }
    });
  }

  // 第一段：跟着光圈呼吸
  void _breathe(int round) {
    if (round >= _depth.breaths) {
      _scan(0);
      return;
    }
    setState(() {
      _phase = '呼吸';
      _breathing = true;
      _line = '慢慢吸气';
    });
    _breath.forward(from: 0);
    YuanjingAudio.sfx('breath_in');
    YuanjingHaptics.play('breath');
    if (round == 0) YuanjingVoice.play('assets/voice/release_breath_1.m4a');
    _after(4000, () {
      setState(() => _line = '缓缓呼出去');
      YuanjingAudio.sfx('breath_out');
      if (round == 0) YuanjingVoice.play('assets/voice/release_breath_2.m4a');
    });
    _after(breathTime.inMilliseconds, () => _breathe(round + 1));
  }

  // 第二段（只有深度有）：从头到脚放松一遍，光圈继续一张一合带着呼吸
  void _scan(int i) {
    if (i >= _depth.scan) {
      _seeIt();
      return;
    }
    if (i == 0) _breath.repeat();
    setState(() {
      _phase = '放松';
      _breathing = true;
      _line = scanLines[i];
    });
    YuanjingVoice.play('assets/voice/release_scan_${i + 1}.m4a');
    _after(scanLineTime.inMilliseconds, () => _scan(i + 1));
  }

  // 第三段：把解读里「怎么放下」那句话念给用户听，然后进画面
  void _seeIt() {
    final sticking = _reading?.sticking;
    if (sticking == null) {
      _play(ritualLength(_style, _depth));
      return;
    }
    if (!_breath.isAnimating) _breath.repeat();
    setState(() {
      _phase = '看见';
      _breathing = true;
      _line = sticking.guide;
    });
    YuanjingVoice.play('assets/voice/guide_${sticking.key}_1.m4a');
    _after(guideTime.inMilliseconds, () => _play(ritualLength(_style, _depth)));
  }

  // 第四段：释放画面
  Future<void> _play(Duration length) async {
    _breath.stop();
    setState(() {
      _phase = '释放';
      _breathing = false;
      _line = null;
    });
    final real = await _stage.play(duration: length);
    if (!mounted || _step != _Step.ritual) return;
    if (real == null) {
      _stopRitual();
      _say('画面还没准备好，再试一次');
      return;
    }
    final ms = real.inMilliseconds;
    for (final (i, at) in _style.at.indexed) {
      _after((ms * at).round(), () {
        setState(() => _line = _style.lines[i + 1]);
        YuanjingVoice.play('assets/voice/${_style.scene}_${i + 2}.m4a');
      });
    }
    if (_quick) return;
    // 四句引导语之间的空档里垫几句留白提示
    for (final (at, i) in holdTimes(_style, _depth)) {
      _after((ms * at).round(), () {
        setState(() => _line = holdLines[i]);
        YuanjingVoice.play('assets/voice/release_hold_${i + 1}.m4a');
      });
    }
  }

  void _onDone() {
    if (!mounted || _step != _Step.ritual) return;
    _cancelTimers();
    if (_quick) {
      _toDone();
    } else {
      _settle(0);
    }
  }

  // 第五段：画面停在放完之后的样子，安住一会儿
  void _settle(int i) {
    if (i >= _depth.settle) {
      _toDone();
      return;
    }
    setState(() {
      _phase = '安住';
      _line = settleLines[i];
    });
    YuanjingVoice.play('assets/voice/release_settle_${i + 1}.m4a');
    _after(settleLineTime.inMilliseconds, () => _settle(i + 1));
  }

  /// 收束：肯定语念一遍，再带着在心里跟念几遍
  void _toDone() {
    _cancelTimers();
    setState(() {
      _step = _Step.done;
      _line = null;
    });
    final key = _reading?.sticking.key;
    if (key == null) return;
    void later(int ms, String asset) {
      _timers.add(Timer(Duration(milliseconds: ms), () {
        if (mounted && _step == _Step.done) YuanjingVoice.play(asset);
      }));
    }

    final affirm = 'assets/voice/affirm_${key}_1.m4a';
    later(900, affirm);
    var at = 900 + affirmTime.inMilliseconds;
    for (var r = 0; r < (_quick ? 0 : _depth.repeats); r++) {
      later(at, 'assets/voice/release_repeat_1.m4a');
      later(at + repeatCueTime.inMilliseconds, affirm);
      at += repeatCueTime.inMilliseconds + affirmTime.inMilliseconds;
    }
  }

  /// 中途结束：回到解读那一步，什么都不记
  void _stopRitual() {
    _cancelTimers();
    _note.stop();
    _breath.stop();
    YuanjingVoice.stop();
    _stage.stop();
    widget.immersive?.value = false;
    setState(() {
      _step = _Step.reading;
      _line = null;
      _breathing = false;
      _noteShown = false;
    });
  }

  void _again() {
    _cancelTimers();
    YuanjingVoice.stop();
    _stage.reset();
    widget.immersive?.value = false;
    setState(() => _step = _Step.reading);
  }

  /// 做完了：写下的内容全部清掉
  void _finish() {
    _cancelTimers();
    YuanjingVoice.stop();
    _stage.reset();
    widget.immersive?.value = false;
    _text.clear();
    setState(() {
      _picked.clear();
      _reading = null;
      _step = _Step.input;
    });
  }

  @override
  Widget build(BuildContext context) {
    final quiet = _step == _Step.input || _step == _Step.reading;
    return Scaffold(
      resizeToAvoidBottomInset: true,
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          WishStage(controller: _stage),
          // 写字和读解读的时候把画面压暗，仪式开始再亮出来
          IgnorePointer(
            child: AnimatedOpacity(
              opacity: quiet ? 1 : 0,
              duration: const Duration(milliseconds: 1200),
              child: const DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [Color(0xA6000000), Color(0x73000000), Color(0xD9000000)],
                    stops: [0, 0.4, 1],
                  ),
                ),
              ),
            ),
          ),
          _Layer(show: _step == _Step.input, child: _buildInput()),
          _Layer(show: _step == _Step.reading, child: _buildReading()),
          _Layer(show: _step == _Step.ritual, child: _buildRitual()),
          _Layer(show: _step == _Step.done, child: _buildDone()),
          _Layer(show: _support, child: _buildSupport()),
          Positioned(
            left: 0,
            right: 0,
            top: MediaQuery.paddingOf(context).top + 54,
            child: IgnorePointer(
              child: Center(
                child: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 350),
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

  // ───────── 第一步：写下卡点 ─────────

  Widget _buildInput() {
    final typing = _focus.hasFocus;
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(22, 4, 22, widget.immersive == null ? 20 : 66),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (widget.immersive == null)
              GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: () => Navigator.of(context).maybePop(),
                child: const Padding(padding: EdgeInsets.only(bottom: 8), child: Text('‹ 返回', style: TextStyle(fontSize: 14, color: Colors.white70))),
              ),
            const Text('只有你看得见。不保存，也不会出现在广场。', style: TextStyle(fontSize: 13, color: Colors.white70, letterSpacing: 0.4)),
            if (!typing) ...[
              const SizedBox(height: 16),
              const Text('此刻，是什么\n压着你？',
                  style: TextStyle(fontFamily: _display, fontSize: 33, height: 1.3, fontWeight: FontWeight.w700, letterSpacing: 1.2, color: Colors.white)),
            ],
            const Spacer(),
            _Panel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Wrap(spacing: 8, runSpacing: 8, children: [
                    for (final s in stickings) _Chip(label: s.name, on: _picked.contains(s.key), style: _style, onTap: () => _toggle(s)),
                  ]),
                  const SizedBox(height: 14),
                  TextField(
                    controller: _text,
                    focusNode: _focus,
                    minLines: 2,
                    maxLines: 3,
                    maxLength: 200,
                    cursorColor: _style.light,
                    style: const TextStyle(fontSize: 15.5, height: 1.5, color: Colors.white),
                    decoration: const InputDecoration(
                      isCollapsed: true,
                      border: InputBorder.none,
                      counterText: '',
                      hintText: '发生了什么？写一句就好，只选上面的标签也可以',
                      hintStyle: TextStyle(fontSize: 15, height: 1.5, color: Colors.white38),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(children: [
                    MicButton(controller: _text, color: Colors.white),
                    const Spacer(),
                    _PillButton(label: _thinking ? '正在看…' : '看见它', style: _style, onTap: _see),
                  ]),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ───────── 第二步：解读，选释放方式 ─────────

  Widget _buildReading() {
    final r = _reading;
    if (r == null) return const SizedBox.shrink();
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(22, 4, 22, widget.immersive == null ? 20 : 66),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () => setState(() => _step = _Step.input),
              child: const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: Text('‹ 改一改', style: TextStyle(fontSize: 14, color: Colors.white70)),
              ),
            ),
            Expanded(
              child: SingleChildScrollView(
                key: ValueKey(r.sticking.key),
                padding: const EdgeInsets.only(top: 6, bottom: 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Wrap(spacing: 8, runSpacing: 8, children: [
                      for (final e in r.emotions)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
                          decoration: BoxDecoration(borderRadius: BorderRadius.circular(99), border: Border.all(color: Colors.white38)),
                          child: Text(e, style: const TextStyle(fontSize: 13, color: Colors.white)),
                        ),
                    ]),
                    const SizedBox(height: 18),
                    _Reveal(
                      delay: 200,
                      child: Text(r.empathy,
                          style: const TextStyle(fontFamily: _display, fontSize: 21, height: 1.65, fontWeight: FontWeight.w700, color: Colors.white)),
                    ),
                    const SizedBox(height: 22),
                    _Reveal(delay: 1300, child: _Block(title: '困住你的', body: r.belief)),
                    const SizedBox(height: 18),
                    _Reveal(delay: 2400, child: _Block(title: '怎么放下', body: r.sticking.guide)),
                    const SizedBox(height: 18),
                    const _Reveal(
                      delay: 3300,
                      child: Text('还有一句肯定语，释放完成时送给你。', style: TextStyle(fontSize: 13, color: Colors.white60)),
                    ),
                  ],
                ),
              ),
            ),
            _Panel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  SizedBox(
                    height: 62,
                    child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      clipBehavior: Clip.none,
                      itemCount: releaseStyles.length,
                      separatorBuilder: (_, _) => const SizedBox(width: 8),
                      itemBuilder: (_, i) {
                        final s = releaseStyles[i];
                        final on = s == _style;
                        return GestureDetector(
                          onTap: () => _pickStyle(s),
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 260),
                            width: 104,
                            padding: const EdgeInsets.symmetric(horizontal: 12),
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(16),
                              gradient: on ? LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [s.light, s.deep]) : null,
                              color: on ? null : const Color(0x40000000),
                              border: Border.all(color: on ? Colors.white60 : Colors.white24),
                            ),
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(s.name,
                                    style: TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700, color: on ? const Color(0xFF2A1708) : Colors.white)),
                                const SizedBox(height: 3),
                                Text(_locked(s) ? '${s.skin} · 会员' : s.skin,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(fontSize: 11.5, color: on ? const Color(0xB32A1708) : Colors.white54)),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(children: [
                    for (final d in [lightRelease, deepRelease]) ...[
                      Expanded(
                        child: GestureDetector(
                          onTap: () {
                            if (d == _depth) return;
                            YuanjingHaptics.play('tick');
                            setState(() => _depth = d);
                          },
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 260),
                            height: 40,
                            alignment: Alignment.center,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(99),
                              color: d == _depth ? Colors.white.withValues(alpha: 0.16) : Colors.transparent,
                              border: Border.all(color: d == _depth ? Colors.white60 : Colors.white24),
                            ),
                            child: Text.rich(
                              TextSpan(text: '${d.name}  ${d.about}', children: [
                                if ((d == deepRelease) == r.deep) TextSpan(text: '  推荐', style: TextStyle(fontSize: 11.5, color: _style.light)),
                              ]),
                              style: TextStyle(fontSize: 13, color: d == _depth ? Colors.white : Colors.white70),
                            ),
                          ),
                        ),
                      ),
                      if (d == lightRelease) const SizedBox(width: 8),
                    ],
                  ]),
                  const SizedBox(height: 12),
                  _PillButton(
                    label: _style.action,
                    style: _style,
                    expand: true,
                    onTap: _begin,
                    onLongPress: kDebugMode ? () => _begin(quick: true) : null,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ───────── 第三步：仪式 ─────────

  Widget _buildRitual() {
    final pad = MediaQuery.paddingOf(context);
    return Stack(
      fit: StackFit.expand,
      children: [
        // 引导语出现时在底部垫一层暗色，亮场景上也看得清
        Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          height: 340,
          child: IgnorePointer(
            child: AnimatedOpacity(
              opacity: _line != null ? 1 : 0,
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
        // 呼吸的光圈：吸气时张开，呼气时收回
        IgnorePointer(
          child: AnimatedOpacity(
            opacity: _breathing ? 1 : 0,
            duration: const Duration(milliseconds: 900),
            child: Align(
              alignment: const Alignment(0, -0.2),
              child: AnimatedBuilder(
                animation: _breath,
                builder: (_, _) {
                  final v = _breath.value;
                  final k = v < 0.4 ? Curves.easeInOut.transform(v / 0.4) : 1 - Curves.easeInOut.transform((v - 0.4) / 0.6);
                  return Transform.scale(
                    scale: 0.6 + 0.4 * k,
                    child: Container(
                      width: 210,
                      height: 210,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white.withValues(alpha: 0.55 + 0.35 * k), width: 1.2),
                        gradient: RadialGradient(colors: [
                          Colors.white.withValues(alpha: 0.02),
                          _style.light.withValues(alpha: 0.10 + 0.14 * k),
                        ], stops: const [0.55, 1]),
                        boxShadow: [BoxShadow(color: _style.light.withValues(alpha: 0.25 * k), blurRadius: 40, spreadRadius: 2)],
                      ),
                    ),
                  );
                },
              ),
            ),
          ),
        ),
        // 写着烦恼的纸条：停一会儿，然后飞进画面里
        IgnorePointer(
          child: AnimatedOpacity(
            opacity: _noteShown ? 1 : 0,
            duration: const Duration(milliseconds: 500),
            child: AnimatedBuilder(
              animation: _note,
              builder: (_, child) {
                final v = Curves.easeInOutCubic.transform(_note.value);
                return Align(
                  alignment: Alignment.lerp(const Alignment(0, -0.12), _style.vessel, v)!,
                  child: Opacity(
                    opacity: 1 - Curves.easeIn.transform(((_note.value - 0.7) / 0.3).clamp(0, 1)),
                    child: Transform.rotate(angle: -0.035 + 0.5 * v, child: Transform.scale(scale: 1 - 0.93 * v, child: child)),
                  ),
                );
              },
              child: Container(
                width: 236,
                constraints: const BoxConstraints(minHeight: 104),
                padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
                decoration: BoxDecoration(
                  color: const Color(0xFFFBF6EA),
                  borderRadius: BorderRadius.circular(3),
                  boxShadow: const [
                    BoxShadow(color: Color(0x73000000), blurRadius: 26, offset: Offset(0, 14)),
                    BoxShadow(color: Color(0x33000000), blurRadius: 3, offset: Offset(0, 1)),
                  ],
                ),
                // 只按内容的高度撑开，短的时候居中；不能给 Container 设 alignment，那样会撑满整屏
                child: Align(
                  heightFactor: 1,
                  child: Text(_noteText,
                      textAlign: _noteText.length <= 12 ? TextAlign.center : TextAlign.start,
                      maxLines: 5,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontFamily: _display, fontSize: 15.5, height: 1.65, fontWeight: FontWeight.w500, color: Color(0xFF3A2E22))),
                ),
              ),
            ),
          ),
        ),
        Positioned(
          left: 32,
          right: 32,
          bottom: pad.bottom + 96,
          child: IgnorePointer(
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 900),
              child: Text(
                _line ?? '',
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
        // 现在到哪一段了：长的仪式里让人心里有数
        Positioned(
          left: 0,
          right: 0,
          top: pad.top + 17,
          child: IgnorePointer(
            child: AnimatedOpacity(
              opacity: _phase.isNotEmpty && !_quick ? 1 : 0,
              duration: const Duration(milliseconds: 700),
              child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                for (final (i, name) in _depth.phases.indexed) ...[
                  if (i > 0) const SizedBox(width: 14),
                  AnimatedDefaultTextStyle(
                    duration: const Duration(milliseconds: 500),
                    style: TextStyle(
                      fontSize: 12.5,
                      letterSpacing: 1,
                      fontWeight: name == _phase ? FontWeight.w700 : FontWeight.w400,
                      color: name == _phase ? Colors.white : Colors.white38,
                      shadows: const [Shadow(color: Colors.black54, blurRadius: 8)],
                    ),
                    child: Text(name),
                  ),
                ],
              ]),
            ),
          ),
        ),
        Positioned(
          right: 14,
          top: pad.top + 6,
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: _stopRitual,
            child: const Padding(
              padding: EdgeInsets.all(10),
              child: Text('结束',
                  style: TextStyle(fontSize: 14, color: Colors.white70, shadows: [Shadow(color: Colors.black54, blurRadius: 8)])),
            ),
          ),
        ),
      ],
    );
  }

  // ───────── 第四步：肯定语收束 ─────────

  Widget _buildDone() {
    final r = _reading;
    return Stack(
      fit: StackFit.expand,
      children: [
        const IgnorePointer(
          child: DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0x00000000), Color(0x80000000), Color(0xCC000000)],
                stops: [0.25, 0.6, 1],
              ),
            ),
          ),
        ),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(30, 0, 30, 40),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                const Text('已经放下了', style: TextStyle(fontSize: 13.5, letterSpacing: 4, color: Colors.white70)),
                const SizedBox(height: 16),
                Text(
                  r?.sticking.affirm ?? '',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontFamily: _display,
                    fontSize: 23,
                    height: 1.7,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1,
                    color: Colors.white,
                    shadows: [Shadow(color: Colors.black87, blurRadius: 18)],
                  ),
                ),
                const SizedBox(height: 34),
                Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTap: _again,
                    child: Container(
                      height: 46,
                      padding: const EdgeInsets.symmetric(horizontal: 22),
                      alignment: Alignment.center,
                      decoration: BoxDecoration(borderRadius: BorderRadius.circular(99), border: Border.all(color: Colors.white54)),
                      child: const Text('再放一次', style: TextStyle(fontSize: 15, color: Colors.white)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  _PillButton(label: '完成', style: _style, onTap: _finish),
                ]),
              ],
            ),
          ),
        ),
      ],
    );
  }

  // ───────── 需要真人帮助的时候 ─────────

  Widget _buildSupport() {
    return ColoredBox(
      color: const Color(0xF20B0A0D),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 30),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('先停一下', style: TextStyle(fontFamily: _display, fontSize: 28, fontWeight: FontWeight.w700, color: Colors.white)),
              const SizedBox(height: 16),
              const Text('你写下的话让我有些担心。这不是一场小仪式能接住的重量，请先让一个真实的人陪着你。',
                  style: TextStyle(fontSize: 16, height: 1.7, color: Colors.white)),
              const SizedBox(height: 24),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: const Color(0x1FFFFFFF),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: Colors.white24),
                ),
                child: const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('全国统一心理援助热线', style: TextStyle(fontSize: 13.5, color: Colors.white70)),
                  SizedBox(height: 6),
                  Text('12356', style: TextStyle(fontSize: 34, fontWeight: FontWeight.w700, letterSpacing: 3, color: Colors.white)),
                  SizedBox(height: 10),
                  Text('如果此刻有危险，请直接拨打 120 或 110。', style: TextStyle(fontSize: 14, height: 1.6, color: Colors.white)),
                ]),
              ),
              const SizedBox(height: 28),
              _PillButton(label: '我知道了', style: _style, expand: true, onTap: () => setState(() => _support = false)),
              const SizedBox(height: 6),
              Center(
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () => _see(safe: true),
                  child: const Padding(
                    padding: EdgeInsets.all(12),
                    child: Text('我现在是安全的，继续释放', style: TextStyle(fontSize: 14, color: Colors.white60)),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 流程里的一层：不显示时淡出并且不接收点击
class _Layer extends StatelessWidget {
  final bool show;
  final Widget child;
  const _Layer({required this.show, required this.child});

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      ignoring: !show,
      child: AnimatedOpacity(
        opacity: show ? 1 : 0,
        duration: Duration(milliseconds: show ? 800 : 400),
        curve: Curves.easeOut,
        child: child,
      ),
    );
  }
}

/// 底部那块半透明的操作面板
class _Panel extends StatelessWidget {
  final Widget child;
  const _Panel({required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xCC14110F),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: Colors.white24),
        boxShadow: const [BoxShadow(color: Color(0x66000000), blurRadius: 24, offset: Offset(0, 10))],
      ),
      child: child,
    );
  }
}

class _Chip extends StatelessWidget {
  final String label;
  final bool on;
  final ReleaseStyle style;
  final VoidCallback onTap;
  const _Chip({required this.label, required this.on, required this.style, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 220),
        height: 34,
        padding: const EdgeInsets.symmetric(horizontal: 14),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(99),
          gradient: on ? LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [style.light, style.deep]) : null,
          color: on ? null : const Color(0x40000000),
          border: Border.all(color: on ? Colors.white54 : Colors.white24),
        ),
        child: Center(
          widthFactor: 1,
          child: Text(label,
              style: TextStyle(
                fontSize: 14,
                fontWeight: on ? FontWeight.w700 : FontWeight.w400,
                color: on ? const Color(0xFF2A1708) : Colors.white.withValues(alpha: 0.86),
              )),
        ),
      ),
    );
  }
}

class _Block extends StatelessWidget {
  final String title;
  final String body;
  const _Block({required this.title, required this.body});

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(title, style: const TextStyle(fontSize: 13, letterSpacing: 2, color: Colors.white60)),
      const SizedBox(height: 6),
      Text(body, style: const TextStyle(fontSize: 16, height: 1.7, color: Colors.white)),
    ]);
  }
}

/// 解读是一段一段出现的：等 [delay] 毫秒后淡入
class _Reveal extends StatefulWidget {
  final int delay;
  final Widget child;
  const _Reveal({required this.delay, required this.child});

  @override
  State<_Reveal> createState() => _RevealState();
}

class _RevealState extends State<_Reveal> {
  Timer? _timer;
  bool _shown = false;

  @override
  void initState() {
    super.initState();
    _timer = Timer(Duration(milliseconds: widget.delay), () {
      if (mounted) setState(() => _shown = true);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedOpacity(opacity: _shown ? 1 : 0, duration: const Duration(milliseconds: 900), curve: Curves.easeOut, child: widget.child);
  }
}

class _PillButton extends StatefulWidget {
  final String label;
  final ReleaseStyle style;
  final bool expand;
  final VoidCallback onTap;
  final VoidCallback? onLongPress;
  const _PillButton({required this.label, required this.style, required this.onTap, this.onLongPress, this.expand = false});

  @override
  State<_PillButton> createState() => _PillButtonState();
}

class _PillButtonState extends State<_PillButton> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    final s = widget.style;
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
        scale: _down ? 0.95 : 1,
        duration: const Duration(milliseconds: 120),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 350),
          height: 46,
          width: widget.expand ? double.infinity : null,
          padding: const EdgeInsets.symmetric(horizontal: 24),
          alignment: widget.expand ? Alignment.center : null,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(99),
            gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [s.light, s.deep]),
            border: Border.all(color: Colors.white60, width: 0.8),
            boxShadow: [
              BoxShadow(color: s.deep.withValues(alpha: _down ? 0.2 : 0.5), blurRadius: _down ? 6 : 18, offset: Offset(0, _down ? 2 : 7)),
            ],
          ),
          child: Center(
            widthFactor: widget.expand ? null : 1,
            child: Text(widget.label, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Color(0xFF2A1708), letterSpacing: 1)),
          ),
        ),
      ),
    );
  }
}
