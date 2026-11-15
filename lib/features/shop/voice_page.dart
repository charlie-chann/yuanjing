import 'dart:async';

import 'package:flutter/material.dart';
import 'package:yuanjing_engine/yuanjing_engine.dart';

import '../../app/muse.dart';
import '../../app/skin.dart';
import '../../app/store.dart';
import '../me/me_page.dart';
import '../wish/wish_category.dart';
import 'shop_data.dart';

/// 声音类的两件「商品」：肯定语音频（自己写、AI 生成）和成品音频库。从商城的卡片点进来。
class VoicePage extends StatefulWidget {
  /// true 是成品音频库，false 是肯定语音频
  final bool library;
  const VoicePage({super.key, required this.library});

  @override
  State<VoicePage> createState() => _VoicePageState();
}

class _VoicePageState extends State<VoicePage> {
  late final _own = TextEditingController(text: store.drafts['affirm'] ?? '');

  /// 会员 AI 生成：选了哪些分类、生成出来的句子
  final _scenes = <String>{};
  List<String> _made = [];

  /// 正在念的：我写的第几条（-1 没有）、AI 生成的是否在念、音频库的哪一组和第几句
  int _speaking = -1;
  bool _madeSpeaking = false;
  String? _track;
  int _trackLine = 0;
  Timer? _trackTimer;

  @override
  void initState() {
    super.initState();
    _own.addListener(() => store.saveDraft('affirm', _own.text));
  }

  @override
  void dispose() {
    _stopAll();
    _own.dispose();
    super.dispose();
  }

  void _stopAll() {
    _trackTimer?.cancel();
    YuanjingVoice.stop();
    YuanjingSpeak.stop();
    _speaking = -1;
    _madeSpeaking = false;
    _track = null;
  }

  // ───────── 肯定语 ─────────

  void _saveOwn() {
    final text = _own.text.trim();
    if (text.isEmpty) return toast(context, '先写一句肯定语');
    store.addAffirmation(text);
    store.saveDraft('affirm', '');
    _own.clear();
    toast(context, '音频生成好了，点播放试听');
  }

  Future<void> _speakOwn(int i) async {
    final same = _speaking == i;
    setState(_stopAll);
    if (same) return;
    setState(() => _speaking = i);
    await YuanjingSpeak.speak(store.affirmations[i]['text'] as String);
    if (mounted && _speaking == i) setState(() => _speaking = -1);
  }

  Future<void> _speakMade() async {
    final was = _madeSpeaking;
    setState(_stopAll);
    if (was) return;
    setState(() => _madeSpeaking = true);
    await YuanjingSpeak.speak(_made.join('　'));
    if (mounted) setState(() => _madeSpeaking = false);
  }

  Future<void> _export(String text) async {
    if (!store.member) {
      toast(context, '导出是会员权益，免费版只能在应用里听');
      showMember(context);
      return;
    }
    toast(context, '正在生成音频文件');
    if (!await YuanjingSpeak.export(text) && mounted) toast(context, '导出没成功，再试一次');
  }

  // ───────── 音频库 ─────────

  void _playTrack(Track t) {
    if (!store.member) {
      toast(context, '成品音频库是会员权益');
      showMember(context);
      return;
    }
    final same = _track == t.id;
    setState(_stopAll);
    if (same) return;
    YuanjingAudio.bed('mood');
    setState(() => _track = t.id);
    _trackSay(t, 0);
  }

  /// 四句循环念，句子之间留三秒
  Future<void> _trackSay(Track t, int n) async {
    if (!mounted || _track != t.id) return;
    final i = n % t.lines.length;
    setState(() => _trackLine = i);
    final length = await YuanjingVoice.playTimed('assets/voice/${t.id}_${i + 1}.m4a');
    if (!mounted || _track != t.id) return;
    _trackTimer = Timer((length ?? const Duration(seconds: 4)) + const Duration(seconds: 3), () => _trackSay(t, n + 1));
  }

  @override
  Widget build(BuildContext context) {
    return SkinPage(
      title: widget.library ? '成品音频库' : '肯定语音频',
      pushed: true,
      builder: (context, s) => ListView(
        padding: EdgeInsets.fromLTRB(22, 6, 22, 24 + MediaQuery.paddingOf(context).bottom),
        children: widget.library ? _library(s) : _affirmations(s),
      ),
    );
  }

  List<Widget> _affirmations(Skin s) => [
        SCard(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('自己写一句', style: s.title(18)),
            const SizedBox(height: 4),
            Text('用「我」开头，用现在时，写你想成为的样子。免费版可以在应用里听，导出是会员权益。', style: s.hint(13)),
            const SizedBox(height: 12),
            SField(controller: _own, hint: '例如：我从容地过着自己选择的生活。', maxLines: 4, mic: true),
            const SizedBox(height: 12),
            SButton('生成音频', expand: true, onTap: _saveOwn),
          ]),
        ),
        for (final (i, a) in store.affirmations.indexed)
          Padding(
            padding: const EdgeInsets.only(top: 10),
            child: SCard(
              padding: const EdgeInsets.fromLTRB(16, 12, 10, 12),
              child: Row(children: [
                Expanded(child: Text(a['text'] as String, style: s.body(15))),
                _Round(icon: _speaking == i ? Icons.stop_rounded : Icons.play_arrow_rounded, onTap: () => _speakOwn(i)),
                _Round(icon: Icons.ios_share_rounded, ghost: true, onTap: () => _export(a['text'] as String)),
                _Round(icon: Icons.close_rounded, ghost: true, onTap: () {
                  setState(_stopAll);
                  store.removeAffirmation(a).catchError((e) {
                    if (mounted) toast(context, '$e');
                  });
                }),
              ]),
            ),
          ),
        const SizedBox(height: 16),
        SCard(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [Text('AI 帮我生成', style: s.title(18)), const SizedBox(width: 8), const MemberTag()]),
            const SizedBox(height: 4),
            Text('根据你的心愿、愿景板和终点密码来写。选一个方面是单项，多选或不选是综合。', style: s.hint(13)),
            const SizedBox(height: 12),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final c in wishCategories)
                SChip(c.name, on: _scenes.contains(c.scene), onTap: () => setState(() => _scenes.contains(c.scene) ? _scenes.remove(c.scene) : _scenes.add(c.scene))),
            ]),
            const SizedBox(height: 12),
            SButton(_made.isEmpty ? '生成' : '换一组', expand: true, onTap: () async {
              if (!store.member) {
                toast(context, 'AI 生成肯定语是会员权益');
                showMember(context);
                return;
              }
              List<String> lines;
              try {
                final r = await store.api.post('/ai/affirmations', {'scenes': _scenes.toList()});
                lines = (r['lines'] as List).cast<String>();
              } on ApiError catch (e) {
                // 没网时用本机的模板
                if (!e.offline) {
                  if (mounted) toast(context, e.message);
                  return;
                }
                lines = affirmationsFor(_scenes);
              }
              if (!mounted) return;
              setState(() {
                _stopAll();
                _made = lines;
              });
            }),
            if (_made.isNotEmpty) ...[
              const SizedBox(height: 14),
              for (final line in _made) Padding(padding: const EdgeInsets.only(bottom: 6), child: Text(line, style: s.title(16).copyWith(height: 1.6))),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(child: SButton(_madeSpeaking ? '停止' : '播放', small: true, onTap: _speakMade)),
                const SizedBox(width: 8),
                Expanded(child: SButton('存下来', small: true, ghost: true, onTap: () {
                  store.addAffirmation(_made.join(''));
                  toast(context, '存到上面的列表里了');
                })),
                const SizedBox(width: 8),
                Expanded(child: SButton('导出', small: true, ghost: true, onTap: () => _export(_made.join('　')))),
              ]),
            ],
          ]),
        ),
        const SizedBox(height: 10),
        Text('你自己写的和 AI 生成的句子，是用手机自带的中文语音念的，音色不如预先录制的自然。', style: s.hint(12)),
      ];

  List<Widget> _library(Skin s) => [
        Row(children: [Expanded(child: Text('录好的女声，四句一组循环播放。会员无限使用。', style: s.hint(13))), const MemberTag()]),
        const SizedBox(height: 12),
        for (final t in tracks)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: SCard(
              onTap: () => _playTrack(t),
              padding: const EdgeInsets.fromLTRB(16, 14, 12, 14),
              child: Row(children: [
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(t.name, style: s.title(17)),
                    const SizedBox(height: 4),
                    AnimatedSwitcher(
                      duration: const Duration(milliseconds: 500),
                      child: Text(_track == t.id ? t.lines[_trackLine] : t.lines.first,
                          key: ValueKey('${t.id}${_track == t.id ? _trackLine : -1}'),
                          style: _track == t.id ? s.body(14.5).copyWith(fontWeight: FontWeight.w700) : s.hint(13.5)),
                    ),
                  ]),
                ),
                if (!store.member)
                  Icon(Icons.lock_outline_rounded, size: 20, color: s.sub)
                else
                  _Round(icon: _track == t.id ? Icons.stop_rounded : Icons.play_arrow_rounded, onTap: () => _playTrack(t)),
              ]),
            ),
          ),
      ];
}

class _Round extends StatelessWidget {
  final IconData icon;
  final bool ghost;
  final VoidCallback onTap;
  const _Round({required this.icon, this.ghost = false, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final s = store.skin;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        width: 36,
        height: 36,
        margin: const EdgeInsets.only(left: 6),
        decoration: BoxDecoration(shape: BoxShape.circle, gradient: ghost ? null : s.accent, border: ghost ? Border.all(color: s.line) : null),
        child: Icon(icon, size: 20, color: ghost ? s.sub : s.onAccent),
      ),
    );
  }
}
