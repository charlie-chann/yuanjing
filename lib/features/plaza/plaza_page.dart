import 'dart:async';

import 'package:flutter/material.dart';
import 'package:yuanjing_engine/yuanjing_engine.dart';

import '../../app/muse.dart';
import '../../app/skin.dart';
import '../../app/store.dart';
import '../me/me_page.dart';
import 'plaza_data.dart';

String _ago(int ts) {
  final m = (DateTime.now().millisecondsSinceEpoch - ts) ~/ 60000;
  if (m < 1) return '刚刚';
  if (m < 60) return '$m 分钟前';
  if (m < 60 * 24) return '${m ~/ 60} 小时前';
  return '${m ~/ (60 * 24)} 天前';
}

/// 愿望广场：只有正向内容的轻社交。数据来自服务器：看大家的朋友圈、感恩日记和许愿，
/// 点赞、夸夸、加好友、举报、拉黑；没有私信，也没有自由评论。
class PlazaPage extends StatefulWidget {
  const PlazaPage({super.key});

  @override
  State<PlazaPage> createState() => _PlazaPageState();
}

class _PlazaPageState extends State<PlazaPage> {
  String _filter = 'all';
  final _items = <Map<String, dynamic>>[];
  int? _next;
  bool _loading = false;
  String? _error;
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _load();
    _scroll.addListener(() {
      if (_scroll.position.extentAfter < 600) _load(more: true);
    });
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _load({bool more = false}) async {
    if (_loading || (more && _next == null)) return;
    setState(() => _loading = true);
    try {
      final r = await store.api.get('/plaza?filter=$_filter${more ? '&before=$_next' : ''}');
      if (!mounted) return;
      setState(() {
        if (!more) _items.clear();
        _items.addAll([for (final i in r['items'] as List) Map<String, dynamic>.from(i as Map)]);
        _next = r['next'] as int?;
        _error = null;
      });
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _replace(Map<String, dynamic> post) {
    final i = _items.indexWhere((p) => p['id'] == post['id']);
    if (i >= 0) setState(() => _items[i] = post);
  }

  Future<void> _like(Map<String, dynamic> p) async {
    YuanjingHaptics.play('tick');
    try {
      final r = await store.api.post('/posts/${p['id']}/like');
      store.setCoins(r);
      setState(() {
        p['liked'] = r['liked'];
        p['likes'] = r['likes'];
      });
      if (mounted) coinToast(context, r['got'] as int, '点了个赞');
    } on ApiError catch (e) {
      if (mounted) toast(context, e.message);
    }
  }

  /// 返回 friends 或 requested；失败返回 null
  Future<String?> _addFriend(Map<String, dynamic> u) async {
    try {
      final (status, got) = await store.addFriend(u['id'] as int);
      if (!mounted) return status;
      setState(() {
        for (final p in _items) {
          if ((p['user'] as Map)['id'] == u['id']) {
            (p['user'] as Map)[status == 'friends' ? 'friend' : 'requested'] = true;
          }
        }
      });
      if (status == 'requested') {
        toast(context, '已向「${u['name']}」发出好友申请');
      } else if (got > 0) {
        coinToast(context, got, '和「${u['name']}」成为好友');
      } else {
        toast(context, '和「${u['name']}」成为好友');
      }
      return status;
    } on ApiError catch (e) {
      if (mounted) toast(context, e.message);
      return null;
    }
  }

  void _praise(Map<String, dynamic> p) {
    showSkinSheet<void>(context, (context, s) {
      return StatefulBuilder(builder: (context, setSheet) {
        final praises = (p['praises'] as List).cast<Map>();
        final mine = {for (final x in praises) if (x['mine'] == true) x['text']};
        return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('夸夸', style: s.title(22)),
          const SizedBox(height: 4),
          Text('这里只有夸，没有评论和私信。', style: s.hint(13)),
          const SizedBox(height: 12),
          Flexible(
            child: ListView(shrinkWrap: true, children: [
              for (final x in praises)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Container(margin: const EdgeInsets.only(top: 8, right: 10), width: 6, height: 6, decoration: BoxDecoration(shape: BoxShape.circle, gradient: s.accent)),
                    Expanded(child: Text(x['text'] as String, style: s.body(15))),
                    if (x['ai'] == true) Text('AI', style: s.hint(11.5)),
                  ]),
                ),
              if (praises.isEmpty) Padding(padding: const EdgeInsets.symmetric(vertical: 10), child: Text('还没有人夸，来当第一个。', style: s.hint(14))),
            ]),
          ),
          if (p['mine'] != true) ...[
            const SizedBox(height: 10),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final text in praisePresets)
                SChip(text, on: mine.contains(text), onTap: mine.contains(text)
                    ? null
                    : () async {
                        try {
                          final r = await store.api.post('/posts/${p['id']}/praise', {'text': text});
                          store.setCoins(r);
                          final post = Map<String, dynamic>.from(r['post'] as Map);
                          p['praises'] = post['praises'];
                          _replace(post);
                          setSheet(() {});
                          if (context.mounted) coinToast(context, r['got'] as int, '夸了一句');
                        } on ApiError catch (e) {
                          if (context.mounted) toast(context, e.message);
                        }
                      }),
            ]),
          ],
        ]);
      });
    });
  }

  void _more(Map<String, dynamic> p) {
    final u = p['user'] as Map<String, dynamic>;
    showSkinSheet<void>(context, (context, s) {
      Widget row(String label, VoidCallback onTap) => GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: onTap,
            child: Padding(padding: const EdgeInsets.symmetric(vertical: 14), child: Text(label, style: s.body(16))),
          );
      return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        row('举报这条动态', () async {
          Navigator.of(context).pop();
          try {
            await store.api.post('/posts/${p['id']}/report', {'reason': '内容不友好'});
            if (mounted) toast(this.context, '收到，我们会尽快看');
          } on ApiError catch (e) {
            if (mounted) toast(this.context, e.message);
          }
        }),
        row('不看「${u['name']}」的动态（拉黑）', () async {
          Navigator.of(context).pop();
          try {
            await store.block(u['id'] as int);
            setState(() => _items.removeWhere((x) => (x['user'] as Map)['id'] == u['id']));
            if (mounted) toast(this.context, '以后不会再看到 TA 的动态');
          } on ApiError catch (e) {
            if (mounted) toast(this.context, e.message);
          }
        }),
      ]);
    });
  }

  void _profile(Map<String, dynamic> u) {
    final future = store.api.get('/users/${u['id']}');
    showSkinSheet<void>(context, tall: true, (context, s) {
      return FutureBuilder(
        future: future,
        builder: (context, snap) {
          if (snap.hasError) return Padding(padding: const EdgeInsets.all(30), child: Center(child: Text('${snap.error}', style: s.hint(14))));
          if (!snap.hasData) return const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator()));
          final user = Map<String, dynamic>.from(snap.data['user'] as Map);
          final posts = snap.data['posts'] as List;
          return StatefulBuilder(builder: (context, setSheet) {
            final friend = user['friend'] == true;
            final requested = user['requested'] == true;
            return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Avatar(user['name'] as String, size: 58, photo: user['avatar'] as String?),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(user['name'] as String, style: s.title(20)),
                    Text(user['sign'] as String, style: s.hint(13)),
                  ]),
                ),
                SButton(friend ? '已是好友' : (requested ? '等对方同意' : '加好友'), small: true, ghost: friend || requested, onTap: friend || requested
                    ? null
                    : () async {
                        final status = await _addFriend(user);
                        if (status != null) setSheet(() => user[status == 'friends' ? 'friend' : 'requested'] = true);
                      }),
              ]),
              const SizedBox(height: 14),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
                decoration: BoxDecoration(borderRadius: BorderRadius.circular(16), gradient: s.accent),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('终点身份卡', style: TextStyle(fontSize: 11.5, letterSpacing: 2.5, color: s.onAccent.withValues(alpha: 0.65))),
                  const SizedBox(height: 4),
                  Text(user['title'] as String, style: TextStyle(fontFamily: displayFont, fontSize: 19, fontWeight: FontWeight.w700, color: s.onAccent)),
                ]),
              ),
              const SizedBox(height: 14),
              Text('公开的动态', style: s.hint(13)),
              const SizedBox(height: 6),
              Flexible(
                child: ListView(shrinkWrap: true, children: [
                  for (final p in posts)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 7),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('${postTypes[p['type']]} · ${_ago(p['ts'] as int)}', style: s.hint(11.5)),
                        Text(p['text'] as String, maxLines: 3, overflow: TextOverflow.ellipsis, style: s.body(14.5)),
                      ]),
                    ),
                ]),
              ),
              const SizedBox(height: 6),
              Center(child: Text('私信没有开放', style: s.hint(12))),
            ]);
          });
        },
      );
    });
  }

  void _compose() {
    showSkinSheet<void>(context, tall: true, (context, s) => _Composer(onDone: (post, got) {
          if (post['public'] == true && (_filter == 'all' || _filter == post['type'] || _filter == 'friends')) {
            setState(() => _items.insert(0, post));
          }
          coinToast(this.context, got, post['type'] == 'diary' ? '日记写好了' : '发布成功');
          if (got == 0) toast(this.context, post['public'] == true ? '发布成功' : '保存好了，只有你看得到');
        }));
  }

  @override
  Widget build(BuildContext context) {
    return SkinPage(
      title: '愿望广场',
      subtitle: '只有正向的分享。点赞、夸夸、加好友都会得金币。',
      builder: (context, s) {
        return Stack(children: [
          Column(children: [
            SizedBox(
              height: 44,
              child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.fromLTRB(22, 6, 22, 6), children: [
                for (final (k, label) in [('all', '全部'), ('moment', '朋友圈'), ('diary', '感恩日记'), ('wish', '许愿'), ('friends', '好友')])
                  Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: SChip(label, on: _filter == k, onTap: () {
                        if (_filter == k) return;
                        setState(() {
                          _filter = k;
                          _items.clear();
                          _next = null;
                        });
                        _load();
                      })),
              ]),
            ),
            Expanded(
              child: RefreshIndicator(
                onRefresh: () => _load(),
                child: _items.isEmpty
                    ? ListView(children: [
                        Padding(
                          padding: const EdgeInsets.only(top: 120),
                          child: Column(children: [
                            if (_loading)
                              const CircularProgressIndicator()
                            else ...[
                              Text(_error ?? (_filter == 'friends' ? '还没有好友的动态。点别人的头像可以加好友。' : '这里还空着，来发第一条。'), textAlign: TextAlign.center, style: s.hint(14)),
                              if (_error != null) Padding(padding: const EdgeInsets.only(top: 14), child: SButton('再试一次', small: true, ghost: true, onTap: _load)),
                            ],
                          ]),
                        ),
                      ])
                    : ListView.builder(
                        controller: _scroll,
                        padding: const EdgeInsets.fromLTRB(22, 8, 22, 170),
                        itemCount: _items.length,
                        itemBuilder: (context, n) => _card(s, _items[n]),
                      ),
              ),
            ),
          ]),
          Positioned(right: 22, bottom: 108, child: SButton('写一条', onTap: _compose)),
        ]);
      },
    );
  }

  Widget _card(Skin s, Map<String, dynamic> p) {
    final u = p['user'] as Map<String, dynamic>;
    final mine = p['mine'] == true;
    final liked = p['liked'] == true;
    final praises = p['praises'] as List;
    final praisedByMe = praises.any((x) => x['mine'] == true);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: SCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            GestureDetector(onTap: mine ? null : () => _profile(u), child: Avatar(u['name'] as String, size: 40, mine: mine, photo: u['avatar'] as String?)),
            const SizedBox(width: 10),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(u['name'] as String, style: s.body(14.5).copyWith(fontWeight: FontWeight.w700)),
                Text('${postTypes[p['type']]} · ${_ago(p['ts'] as int)}', style: s.hint(12)),
              ]),
            ),
            if (!mine && u['friend'] != true)
              SButton(u['requested'] == true ? '已申请' : '加好友', small: true, ghost: true, onTap: u['requested'] == true ? null : () => _addFriend(u)),
            if (!mine)
              GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: () => _more(p),
                child: Padding(padding: const EdgeInsets.only(left: 8, top: 6, bottom: 6), child: Icon(Icons.more_horiz_rounded, color: s.sub, size: 20)),
              ),
          ]),
          const SizedBox(height: 12),
          Text(p['text'] as String, style: p['type'] == 'wish' ? s.title(17).copyWith(height: 1.6) : s.body(15.5)),
          const SizedBox(height: 12),
          Row(children: [
            _Action(label: '${p['likes']}', icon: liked ? Icons.favorite_rounded : Icons.favorite_border_rounded, on: liked, onTap: () => _like(p)),
            const SizedBox(width: 18),
            _Action(label: '夸夸 ${praises.length}', icon: Icons.auto_awesome_outlined, on: praisedByMe, onTap: () => _praise(p)),
          ]),
        ]),
      ),
    );
  }
}

class _Action extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool on;
  final VoidCallback onTap;
  const _Action({required this.label, required this.icon, required this.on, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final s = store.skin;
    final c = on ? s.deep : s.sub;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 18, color: c),
          const SizedBox(width: 5),
          Text(label, style: TextStyle(fontSize: 13.5, fontWeight: on ? FontWeight.w700 : FontWeight.w400, color: c)),
        ]),
      ),
    );
  }
}

/// 写一条：朋友圈或感恩日记。可以让 AI 起个头，可以语音输入，写到一半会自动留着。
class _Composer extends StatefulWidget {
  final void Function(Map<String, dynamic> post, int coins) onDone;
  const _Composer({required this.onDone});

  @override
  State<_Composer> createState() => _ComposerState();
}

class _ComposerState extends State<_Composer> {
  String _type = 'moment';
  bool _public = true;
  bool _busy = false;
  late final _text = TextEditingController(text: store.drafts['post_moment'] ?? '');

  String get _draftKey => 'post_$_type';

  @override
  void initState() {
    super.initState();
    _text.addListener(() => store.saveDraft(_draftKey, _text.text));
  }

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  void _switch(String type) {
    if (type == _type) return;
    setState(() {
      _type = type;
      _public = true;
    });
    final draft = store.drafts[_draftKey] ?? '';
    _text.value = TextEditingValue(text: draft, selection: TextSelection.collapsed(offset: draft.length));
  }

  Future<void> _ai() async {
    setState(() => _busy = true);
    String t;
    try {
      t = (await store.api.post(_type == 'diary' ? '/ai/diary' : '/ai/moment'))['text'] as String;
    } on ApiError {
      t = _type == 'diary' ? diaryCopy() : momentCopy();
    }
    if (!mounted) return;
    setState(() => _busy = false);
    _text.value = TextEditingValue(text: t, selection: TextSelection.collapsed(offset: t.length));
  }

  Future<void> _publish() async {
    final text = _text.text.trim();
    if (text.isEmpty) return toast(context, '先写点什么');
    setState(() => _busy = true);
    try {
      final r = await store.api.post('/posts', {'type': _type, 'text': text, 'public': _public});
      store.setCoins(r);
      store.saveDraft(_draftKey, '');
      unawaited(store.refresh());
      if (!mounted) return;
      Navigator.of(context).pop();
      widget.onDone(Map<String, dynamic>.from(r['post'] as Map), r['got'] as int);
    } on ApiError catch (e) {
      if (mounted) {
        setState(() => _busy = false);
        toast(context, e.message);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = store.skin;
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        SChip('朋友圈', on: _type == 'moment', onTap: () => _switch('moment')),
        const SizedBox(width: 8),
        SChip('感恩日记', on: _type == 'diary', onTap: () => _switch('diary')),
        const Spacer(),
        SButton('AI 帮我写', small: true, ghost: true, onTap: _busy ? null : _ai),
      ]),
      const SizedBox(height: 12),
      SField(controller: _text, hint: _type == 'diary' ? '今天想谢谢什么？' : '分享一件今天的好事', maxLines: 7, mic: true),
      const SizedBox(height: 12),
      if (_type == 'diary')
        Row(children: [
          SChip('公开到广场', on: _public, onTap: () => setState(() => _public = true)),
          const SizedBox(width: 8),
          SChip('仅自己可见', on: !_public, onTap: () => setState(() => _public = false)),
        ])
      else
        Text('朋友圈会出现在广场上，所有人都能看到。', style: s.hint(12.5)),
      const SizedBox(height: 14),
      SButton(_type == 'diary' && !_public ? '保存' : '发布', expand: true, onTap: _busy ? null : _publish),
    ]);
  }
}
