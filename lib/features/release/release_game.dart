import 'dart:async';

import 'package:flutter/material.dart';
import 'package:yuanjing_engine/yuanjing_engine.dart';

import 'release_data.dart';

const _display = 'YuanjingSerif';

/// 释放页里每一场的解压小游戏：盖在原生舞台上面的一层，只管收手指和画提示、进度。
///
/// 规则在原生层（`StageView.swift`）：每点一下攒一点能量，不点了能量慢慢落回去；能量推着进度走，
/// 所以点得越快进度走得越快，画面也越亮（火更旺、光点更多、风铃的音更高）。攒满放一段奖励动画，
/// 放完可以再来一轮。魔药那一场是画圈搅动，手指每挪一小段算零点几下。
class ReleaseGame extends StatefulWidget {
  final WishStageController stage;
  final ReleaseStyle style;
  final VoidCallback onExit;

  const ReleaseGame({super.key, required this.stage, required this.style, required this.onExit});

  @override
  State<ReleaseGame> createState() => _ReleaseGameState();
}

class _ReleaseGameState extends State<ReleaseGame> with SingleTickerProviderStateMixin {
  /// 连着点了多少下（隔得太久就重新数）
  int _combo = 0;
  DateTime _last = DateTime.fromMillisecondsSinceEpoch(0);

  /// 拖着搅的时候攒的路程（逻辑像素）
  double _dragged = 0;
  Offset? _dragFrom;

  /// 攒满了：显示那一句话；奖励动画放完：显示两个按钮
  bool _won = false;
  bool _done = false;
  int _rounds = 0;
  bool _shown = false;

  /// 连击数字每点一下弹一下
  late final AnimationController _bump = AnimationController(vsync: this, duration: const Duration(milliseconds: 260), value: 1);

  @override
  void initState() {
    super.initState();
    widget.stage.onGameWin = (round) {
      if (!mounted) return;
      setState(() {
        _won = true;
        _rounds = round;
      });
    };
    widget.stage.onGameDone = (_) {
      if (mounted) setState(() => _done = true);
    };
    // 画面先暗一下再亮起来，界面晚一点淡入
    Timer(const Duration(milliseconds: 350), () {
      if (mounted) setState(() => _shown = true);
    });
  }

  @override
  void dispose() {
    widget.stage.onGameWin = null;
    widget.stage.onGameDone = null;
    _bump.dispose();
    super.dispose();
  }

  void _hit(Offset at, Size size, double strength) {
    if (_won) return;
    // 换成着色器里的坐标：y 从下到上 -1..1，x 按同样的比例
    widget.stage.gameTap((2 * at.dx - size.width) / size.height, (size.height - 2 * at.dy) / size.height, strength: strength);
  }

  void _count() {
    final now = DateTime.now();
    setState(() => _combo = now.difference(_last).inMilliseconds < 800 ? _combo + 1 : 1);
    _last = now;
    _bump.forward(from: 0);
  }

  void _down(PointerDownEvent e, Size size) {
    _dragFrom = e.localPosition;
    if (widget.style.stir) {
      _hit(e.localPosition, size, 0.5);
    } else {
      _hit(e.localPosition, size, 1);
      if (!_won) _count();
    }
  }

  void _move(PointerMoveEvent e, Size size) {
    if (!widget.style.stir || _won) return;
    final from = _dragFrom ?? e.localPosition;
    _dragFrom = e.localPosition;
    _dragged += (e.localPosition - from).distance;
    // 每挪 26 个点算三分之一下；搅满一小圈（约 130 个点）连击加一
    while (_dragged >= 26) {
      _dragged -= 26;
      _hit(e.localPosition, size, 0.34);
      _stirred += 26;
      if (_stirred >= 130) {
        _stirred = 0;
        _count();
      }
    }
  }

  double _stirred = 0;

  void _again() {
    YuanjingHaptics.play('tick');
    YuanjingAudio.sfx('tap');
    widget.stage.gameAgain();
    setState(() {
      _won = false;
      _done = false;
      _combo = 0;
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.style;
    final pad = MediaQuery.paddingOf(context);
    return AnimatedOpacity(
      opacity: _shown ? 1 : 0,
      duration: const Duration(milliseconds: 700),
      child: LayoutBuilder(builder: (context, box) {
        final size = box.biggest;
        return ValueListenableBuilder<StageGame>(
          valueListenable: widget.stage.game,
          builder: (context, g, _) {
            final e = g.energy.clamp(0.0, 1.0);
            final p = _won ? 1.0 : g.progress.clamp(0.0, 1.0);
            final idle = DateTime.now().difference(_last).inMilliseconds > 1400;
            return Stack(fit: StackFit.expand, children: [
              // 整屏收手指
              Listener(
                behavior: HitTestBehavior.opaque,
                onPointerDown: (ev) => _down(ev, size),
                onPointerMove: (ev) => _move(ev, size),
                child: const SizedBox.expand(),
              ),
              // 上下各垫一层暗色，字在亮的画面上也看得清
              const IgnorePointer(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [Color(0x66000000), Color(0x00000000), Color(0x00000000), Color(0x80000000)],
                      stops: [0, 0.2, 0.68, 1],
                    ),
                  ),
                ),
              ),
              // 名字和第几轮
              Positioned(
                left: 24,
                top: pad.top + 14,
                child: IgnorePointer(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(s.play,
                        style: const TextStyle(
                            fontFamily: _display,
                            fontSize: 21,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 2,
                            color: Colors.white,
                            shadows: [Shadow(color: Colors.black54, blurRadius: 10)])),
                    const SizedBox(height: 4),
                    AnimatedOpacity(
                      opacity: _rounds > 0 ? 1 : 0,
                      duration: const Duration(milliseconds: 500),
                      child: Text('已经完成 $_rounds 次',
                          style: const TextStyle(fontSize: 12, letterSpacing: 1, color: Colors.white70, shadows: [Shadow(color: Colors.black54, blurRadius: 8)])),
                    ),
                  ]),
                ),
              ),
              Positioned(
                right: 14,
                top: pad.top + 6,
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: widget.onExit,
                  child: const Padding(
                    padding: EdgeInsets.all(10),
                    child: Text('结束', style: TextStyle(fontSize: 14, color: Colors.white70, shadows: [Shadow(color: Colors.black54, blurRadius: 8)])),
                  ),
                ),
              ),
              // 连击：点得越快数字越亮
              Positioned(
                left: 0,
                right: 0,
                bottom: pad.bottom + 128,
                child: IgnorePointer(
                  child: AnimatedOpacity(
                    opacity: _won || idle || _combo < 3 ? 0 : (0.45 + 0.55 * e),
                    duration: const Duration(milliseconds: 350),
                    child: AnimatedBuilder(
                      animation: _bump,
                      builder: (_, child) => Transform.scale(scale: 1 + 0.22 * (1 - Curves.easeOut.transform(_bump.value)), child: child),
                      child: Text.rich(
                        TextSpan(children: [
                          const TextSpan(text: '× ', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w400)),
                          TextSpan(text: '$_combo'),
                        ]),
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontFamily: _display,
                          fontSize: 38,
                          fontWeight: FontWeight.w700,
                          color: Color.lerp(Colors.white, s.light, 0.5),
                          shadows: [Shadow(color: s.deep.withValues(alpha: 0.9), blurRadius: 18 + 22 * e), const Shadow(color: Colors.black54, blurRadius: 6)],
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              // 怎么玩：开始点了就让开
              Positioned(
                left: 32,
                right: 32,
                bottom: pad.bottom + 118,
                child: IgnorePointer(
                  child: AnimatedOpacity(
                    opacity: !_won && g.progress < 0.05 && _combo < 3 ? 1 : 0,
                    duration: const Duration(milliseconds: 600),
                    child: Text(s.playHint,
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                            fontFamily: _display,
                            fontSize: 18,
                            height: 1.7,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 1.5,
                            color: Colors.white,
                            shadows: [Shadow(color: Colors.black87, blurRadius: 16), Shadow(color: Colors.black54, blurRadius: 4)])),
                  ),
                ),
              ),
              // 进度：一条细线，头上一粒光，能量越高光越大
              Positioned(
                left: 36,
                right: 36,
                bottom: pad.bottom + 76,
                child: IgnorePointer(
                  child: AnimatedOpacity(
                    opacity: _won ? 0 : 1,
                    duration: const Duration(milliseconds: 600),
                    child: SizedBox(
                      height: 24,
                      child: LayoutBuilder(builder: (_, bar) {
                        final w = bar.maxWidth;
                        final head = 4.0 + 5.0 * e;
                        return Stack(clipBehavior: Clip.none, alignment: Alignment.centerLeft, children: [
                          Container(height: 1.5, color: Colors.white.withValues(alpha: 0.22)),
                          AnimatedContainer(
                            duration: const Duration(milliseconds: 140),
                            height: 2.5,
                            width: w * p,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(2),
                              gradient: LinearGradient(colors: [s.deep.withValues(alpha: 0.6), s.light, Colors.white]),
                              boxShadow: [BoxShadow(color: s.light.withValues(alpha: 0.35 + 0.5 * e), blurRadius: 6 + 12 * e)],
                            ),
                          ),
                          AnimatedPositioned(
                            duration: const Duration(milliseconds: 140),
                            left: w * p - head,
                            child: Container(
                              width: head * 2,
                              height: head * 2,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: Colors.white,
                                boxShadow: [BoxShadow(color: s.light.withValues(alpha: 0.9), blurRadius: 10 + 22 * e, spreadRadius: 1 + 3 * e)],
                              ),
                            ),
                          ),
                        ]);
                      }),
                    ),
                  ),
                ),
              ),
              Positioned(
                left: 0,
                right: 0,
                bottom: pad.bottom + 52,
                child: IgnorePointer(
                  child: AnimatedOpacity(
                    opacity: _won || g.progress < 0.05 ? 0 : 0.85,
                    duration: const Duration(milliseconds: 500),
                    child: Text(
                      e > 0.8 ? '就是这样，再快一点' : (e > 0.45 ? '很好，保持这个节奏' : (e > 0.12 ? '可以再快一点' : (s.stir ? '搅一搅，它在等你' : '点一点，它在等你'))),
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 12.5, letterSpacing: 2, color: Colors.white, shadows: [Shadow(color: Colors.black54, blurRadius: 8)]),
                    ),
                  ),
                ),
              ),
              // 攒满了
              Positioned(
                left: 28,
                right: 28,
                bottom: pad.bottom + 60,
                child: IgnorePointer(
                  ignoring: !_done,
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    AnimatedOpacity(
                      opacity: _won ? 1 : 0,
                      duration: const Duration(milliseconds: 1200),
                      child: Text(s.playWin,
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                              fontFamily: _display,
                              fontSize: 23,
                              height: 1.6,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 2,
                              color: Colors.white,
                              shadows: [Shadow(color: Colors.black87, blurRadius: 18), Shadow(color: Colors.black54, blurRadius: 4)])),
                    ),
                    const SizedBox(height: 26),
                    AnimatedOpacity(
                      opacity: _done ? 1 : 0,
                      duration: const Duration(milliseconds: 700),
                      child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                        GestureDetector(
                          behavior: HitTestBehavior.opaque,
                          onTap: widget.onExit,
                          child: Container(
                            height: 46,
                            padding: const EdgeInsets.symmetric(horizontal: 26),
                            alignment: Alignment.center,
                            decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(99), color: const Color(0x33000000), border: Border.all(color: Colors.white54)),
                            child: const Text('好了', style: TextStyle(fontSize: 15, color: Colors.white)),
                          ),
                        ),
                        const SizedBox(width: 12),
                        GestureDetector(
                          behavior: HitTestBehavior.opaque,
                          onTap: _again,
                          child: Container(
                            height: 46,
                            padding: const EdgeInsets.symmetric(horizontal: 26),
                            alignment: Alignment.center,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(99),
                              gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [s.light, s.deep]),
                              border: Border.all(color: Colors.white60, width: 0.8),
                              boxShadow: [BoxShadow(color: s.deep.withValues(alpha: 0.5), blurRadius: 18, offset: const Offset(0, 7))],
                            ),
                            child: const Text('再来一次', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, letterSpacing: 1, color: Color(0xFF2A1708))),
                          ),
                        ),
                      ]),
                    ),
                  ]),
                ),
              ),
            ]);
          },
        );
      }),
    );
  }
}
