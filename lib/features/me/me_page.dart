import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:yuanjing_engine/yuanjing_engine.dart';

import '../../app/shell.dart';
import '../../app/skin.dart';
import '../../app/store.dart';
import '../plaza/plaza_data.dart';
import '../room/room_page.dart';
import 'vision_pages.dart';

/// 头像：名字的第一个字，底色由名字决定。商城里买的头像框戴上后会显示在外圈。
class Avatar extends StatelessWidget {
  final String name;
  final double size;

  /// 是不是我自己的头像（要不要画头像框）
  final bool mine;
  final String? photo;
  const Avatar(this.name, {super.key, this.size = 44, this.mine = false, this.photo});

  @override
  Widget build(BuildContext context) {
    final hue = (name.codeUnits.fold<int>(0, (a, b) => a + b) * 47) % 360;
    final a = HSLColor.fromAHSL(1, hue.toDouble(), 0.55, 0.78).toColor();
    final b = HSLColor.fromAHSL(1, (hue + 40) % 360, 0.55, 0.62).toColor();
    final gold = mine && store.equipped.contains('frame_gold');
    final star = mine && store.equipped.contains('frame_star');
    final image = store.photo(mine ? (photo ?? store.avatar) : photo);
    return SizedBox(
      width: size,
      height: size,
      child: Stack(alignment: Alignment.center, children: [
        if (gold || star)
          Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: SweepGradient(
                  colors: gold
                      ? const [Color(0xFFFFF1B8), Color(0xFFD9A441), Color(0xFFFFF1B8), Color(0xFFB07A18), Color(0xFFFFF1B8)]
                      : const [Color(0xFFFFD9E6), Color(0xFFB8A2F2), Color(0xFFCFF3FF), Color(0xFFFFE7A8), Color(0xFFFFD9E6)]),
            ),
          ),
        Container(
          width: size - (gold || star ? 6 : 0),
          height: size - (gold || star ? 6 : 0),
          clipBehavior: Clip.antiAlias,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [a, b]),
            border: Border.all(color: Colors.white.withValues(alpha: 0.8), width: 1.2),
          ),
          alignment: Alignment.center,
          child: image != null
              ? Image(image: image, width: size, height: size, fit: BoxFit.cover, errorBuilder: (_, _, _) => const SizedBox.shrink())
              : Text(name.isEmpty ? '愿' : name.characters.first,
                  style: TextStyle(fontFamily: displayFont, fontSize: size * 0.42, fontWeight: FontWeight.w700, color: Colors.white)),
        ),
      ]),
    );
  }
}

/// 我的：主页、终点身份卡、签到和金币，以及房间、愿景板、终点密码、皮肤、会员这些入口。
class MePage extends StatelessWidget {
  const MePage({super.key});

  @override
  Widget build(BuildContext context) {
    return SkinPage(
      title: '我的',
      trailing: GestureDetector(onTap: () => showCoins(context), child: const CoinBadge()),
      builder: (context, s) {
        final card = (store.title, store.titleLine);
        final entries = <(String, String, VoidCallback)>[
          ('我的房间', '她和毛孩子住在这里', () => push(context, const RoomPage())),
          ('愿景板', store.vision.isEmpty ? '把想要的生活贴上去' : '已经贴了 ${store.vision.length} 张', () => push(context, const VisionPage())),
          ('终点密码', store.destiny.isEmpty ? '写下终极的理想状态' : '写了 ${store.destiny.length} 个方面', () => push(context, const DestinyPage())),
          ('愿望汇总', '共许下 ${store.wishes.length} 个心愿', () => push(context, const WishSummaryPage())),
          ('皮肤', '正在用「${s.name}」', () => showSkins(context)),
          ('会员', store.member ? '已开通' : '解锁全部皮肤和 AI 音频', () => showMember(context)),
          ('我的宠物', store.pets.map((p) => p['name']).join('、'), () => showPets(context)),
          ('我的形象', lookModes[store.lookMode]!.$1, () => showLooks(context)),
          ('我的动态', '朋友圈和感恩日记，含仅自己可见的', () => showMyPosts(context)),
          ('好友', store.requests.isNotEmpty ? '${store.requests.length} 个新的好友申请' : (store.friends.isEmpty ? '去广场认识些同路人' : '${store.friends.length} 位'), () => showFriends(context)),
        ];
        return ListView(padding: const EdgeInsets.fromLTRB(22, 8, 22, 96), children: [
          GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: () => _editProfile(context),
            child: Row(children: [
              Avatar(store.name, size: 62, mine: true),
              const SizedBox(width: 14),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    Flexible(child: Text(store.name, maxLines: 1, overflow: TextOverflow.ellipsis, style: s.title(21))),
                    if (store.member) const Padding(padding: EdgeInsets.only(left: 8), child: MemberTag()),
                  ]),
                  const SizedBox(height: 3),
                  Text(store.sign, maxLines: 1, overflow: TextOverflow.ellipsis, style: s.hint(13.5)),
                ]),
              ),
              Text('编辑', style: s.hint(13)),
            ]),
          ),
          const SizedBox(height: 18),
          // 终点身份卡
          Container(
            padding: const EdgeInsets.fromLTRB(20, 18, 20, 18),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(24),
              gradient: s.accent,
              border: Border.all(color: Colors.white.withValues(alpha: 0.7)),
              boxShadow: [BoxShadow(color: s.deep.withValues(alpha: 0.42), blurRadius: 30, offset: const Offset(0, 14))],
            ),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('终点身份卡', style: TextStyle(fontSize: 12.5, letterSpacing: 3, color: s.onAccent.withValues(alpha: 0.65))),
              const SizedBox(height: 10),
              Text(card.$1, style: TextStyle(fontFamily: displayFont, fontSize: 25, height: 1.3, fontWeight: FontWeight.w700, color: s.onAccent)),
              const SizedBox(height: 6),
              Text(card.$2, style: TextStyle(fontSize: 14.5, height: 1.5, color: s.onAccent.withValues(alpha: 0.82))),
              const SizedBox(height: 16),
              Row(children: [
                for (final (n, label) in [(store.wishes.length, '个心愿'), (store.streak, '天连续签到'), (store.friends.length, '位好友')])
                  Padding(
                    padding: const EdgeInsets.only(right: 20),
                    child: Text.rich(TextSpan(children: [
                      TextSpan(text: '$n', style: TextStyle(fontFamily: 'Didot', fontSize: 22, fontWeight: FontWeight.w700, color: s.onAccent)),
                      TextSpan(text: ' $label', style: TextStyle(fontSize: 12, color: s.onAccent.withValues(alpha: 0.7))),
                    ])),
                  ),
              ]),
            ]),
          ),
          const SizedBox(height: 14),
          SCard(
            padding: const EdgeInsets.fromLTRB(16, 12, 12, 12),
            child: Row(children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(store.checkedIn ? '今天已签到' : '今天还没签到', style: s.body(15).copyWith(fontWeight: FontWeight.w700)),
                  Text('连续 ${store.streak} 天 · 做正向的事都会得金币', style: s.hint(12.5)),
                ]),
              ),
              SButton(store.checkedIn ? '金币明细' : '去签到', small: true, ghost: store.checkedIn, onTap: () => store.checkedIn ? showCoins(context) : showCheckin(context)),
            ]),
          ),
          const SizedBox(height: 14),
          for (var i = 0; i < entries.length; i += 2)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: IntrinsicHeight(
                child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  for (var k = i; k < i + 2; k++) ...[
                    if (k > i) const SizedBox(width: 10),
                    Expanded(
                      child: k >= entries.length
                          ? const SizedBox.shrink()
                          : SCard(
                              padding: const EdgeInsets.fromLTRB(16, 14, 14, 14),
                              onTap: () {
                                YuanjingAudio.sfx('tap');
                                entries[k].$3();
                              },
                              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Text(entries[k].$1, style: s.title(17)),
                                const SizedBox(height: 4),
                                Text(entries[k].$2, maxLines: 2, overflow: TextOverflow.ellipsis, style: s.hint(12.5)),
                              ]),
                            ),
                    ),
                  ],
                ]),
              ),
            ),
          const SizedBox(height: 6),
          Center(child: Text('私信功能没有开放，这里只有正向的互动。', style: s.hint(12))),
        ]);
      },
    );
  }
}

/// 一个带标题的输入框，面板里用
class SField extends StatelessWidget {
  final TextEditingController controller;
  final String hint;
  final int maxLines;
  final bool mic;
  const SField({super.key, required this.controller, required this.hint, this.maxLines = 1, this.mic = false});

  @override
  Widget build(BuildContext context) {
    final s = store.skin;
    return Container(
      padding: EdgeInsets.fromLTRB(14, maxLines > 1 ? 10 : 2, mic ? 6 : 14, maxLines > 1 ? 8 : 2),
      decoration: BoxDecoration(color: s.card, borderRadius: BorderRadius.circular(16), border: Border.all(color: s.line)),
      child: Row(crossAxisAlignment: maxLines > 1 ? CrossAxisAlignment.end : CrossAxisAlignment.center, children: [
        Expanded(
          child: TextField(
            controller: controller,
            minLines: maxLines > 1 ? 2 : 1,
            maxLines: maxLines,
            cursorColor: s.deep,
            style: s.body(15.5),
            decoration: InputDecoration(border: InputBorder.none, isDense: true, hintText: hint, hintStyle: s.hint(15), contentPadding: const EdgeInsets.symmetric(vertical: 10)),
          ),
        ),
        if (mic) MicButton(controller: controller),
      ]),
    );
  }
}

void _editProfile(BuildContext context) {
  final name = TextEditingController(text: store.name);
  final sign = TextEditingController(text: store.sign);
  showSkinSheet<void>(context, (context, s) {
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('我的名片', style: s.title(22)),
      const SizedBox(height: 14),
      Row(children: [
        Avatar(store.name, size: 54, mine: true),
        const SizedBox(width: 12),
        SButton('换头像', small: true, ghost: true, onTap: () async {
          try {
            final url = await store.pickAndUpload();
            if (url != null) await store.updateProfile(avatar: url);
          } on ApiError catch (e) {
            if (context.mounted) toast(context, e.message);
          }
        }),
      ]),
      const SizedBox(height: 12),
      SField(controller: name, hint: '名字'),
      const SizedBox(height: 10),
      SField(controller: sign, hint: '一句话签名'),
      const SizedBox(height: 16),
      SButton('保存', expand: true, onTap: () async {
        try {
          await store.updateProfile(name: name.text.trim().isEmpty ? null : name.text.trim(), sign: sign.text.trim());
          if (context.mounted) Navigator.of(context).pop();
        } on ApiError catch (e) {
          // 名字签名不合适会被服务器拒绝，拉一遍改回去
          await store.refresh();
          if (context.mounted) toast(context, e.message);
        }
      }),
    ]);
  });
}

/// 金币：规则和最近的流水
void showCoins(BuildContext context) {
  showSkinSheet<void>(context, tall: true, (context, s) {
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(child: Text('金币', style: s.title(22))),
        const CoinIcon(size: 22),
        const SizedBox(width: 8),
        Text('${store.coins}', style: TextStyle(fontFamily: 'Didot', fontSize: 26, fontWeight: FontWeight.w700, color: s.ink)),
      ]),
      const SizedBox(height: 4),
      Text('做正向的事会得金币，可以在商城换装扮。', style: s.hint(13)),
      const SizedBox(height: 14),
      Flexible(
        child: ListView(shrinkWrap: true, children: [
          for (final e in coinRules.entries)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Row(children: [
                Expanded(child: Text(e.value.$3, style: s.body(14.5))),
                Text('今天 ${store.count(e.key)}/${e.value.$2}', style: s.hint(12.5)),
                const SizedBox(width: 12),
                SizedBox(width: 34, child: Text('+${e.value.$1}', textAlign: TextAlign.right, style: s.body(14.5).copyWith(fontWeight: FontWeight.w700))),
              ]),
            ),
          if (store.coinLog.isNotEmpty) ...[
            Padding(padding: const EdgeInsets.only(top: 14, bottom: 6), child: Text('最近的流水', style: s.hint(13))),
            for (final e in store.coinLog.take(20))
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 5),
                child: Row(children: [
                  Expanded(child: Text(e.what, style: s.body(14))),
                  Text('${e.amount > 0 ? '+' : ''}${e.amount}',
                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: e.amount > 0 ? s.deep : s.sub)),
                ]),
              ),
          ],
        ]),
      ),
    ]);
  });
}

/// 换皮肤：两套免费，三套会员
void showSkins(BuildContext context) {
  showSkinSheet<void>(context, tall: true, (context, s) {
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('皮肤', style: s.title(22)),
      const SizedBox(height: 4),
      Text('换一套，整个应用的颜色和氛围都跟着换。', style: s.hint(13)),
      const SizedBox(height: 14),
      Flexible(
        child: ListView(shrinkWrap: true, children: [
          for (final k in skins)
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () {
                if (k.member && !store.member) {
                  toast(context, '「${k.name}」是会员皮肤');
                  showMember(context);
                  return;
                }
                YuanjingAudio.sfx('pick');
                store.setSkin(k.id).catchError((e) {
                  if (context.mounted) toast(context, '$e');
                });
              },
              child: Container(
                margin: const EdgeInsets.only(bottom: 10),
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: s.card,
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: k.id == store.skinId ? s.deep : s.line, width: k.id == store.skinId ? 1.6 : 1),
                ),
                child: Row(children: [
                  // 这套皮肤的小样：底色加一颗强调色
                  Container(
                    width: 74,
                    height: 54,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(12),
                      gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: k.bg),
                      border: Border.all(color: k.line),
                    ),
                    child: Container(
                      width: 34,
                      height: 16,
                      decoration: BoxDecoration(borderRadius: BorderRadius.circular(99), gradient: k.accent, border: Border.all(color: Colors.white70, width: 0.6)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(children: [
                        Text(k.name, style: s.title(16.5)),
                        const SizedBox(width: 8),
                        if (k.member) const MemberTag() else Text('免费', style: s.hint(11.5)),
                      ]),
                      const SizedBox(height: 2),
                      Text(k.mood, style: s.hint(12.5)),
                    ]),
                  ),
                  if (k.id == store.skinId) Text('使用中', style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: s.deep)),
                ]),
              ),
            ),
        ]),
      ),
    ]);
  });
}

/// 会员：权益说明和开通。支付还没接，这里的开通只是切换本机的会员状态，方便看会员功能。
void showMember(BuildContext context) {
  const perks = [
    ('全部皮肤', '魔法巫女、天使祝福、美人鱼海洋三套限定皮肤，以及对应的释放仪式'),
    ('AI 肯定语音频', '根据许愿、愿景板和终点密码自动生成，可以导出保存'),
    ('成品音频库', '财富、事业、外貌、健康、情绪和综合六组，无限使用'),
    ('画面冥想', '外貌可视化、终极愿景两场带画面的冥想，潜意识清理免金币'),
    ('更细的分析和装扮', '愿景分析看到执念点和建议，限定的宠物装扮免费领'),
  ];
  showSkinSheet<void>(context, tall: true, (context, s) {
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [Text('会员', style: s.title(22)), const SizedBox(width: 10), if (store.member) const MemberTag()]),
      const SizedBox(height: 12),
      Flexible(
        child: ListView(shrinkWrap: true, children: [
          for (final (name, about) in perks)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Container(margin: const EdgeInsets.only(top: 7, right: 10), width: 7, height: 7, decoration: BoxDecoration(shape: BoxShape.circle, gradient: s.accent)),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(name, style: s.body(15.5).copyWith(fontWeight: FontWeight.w700)),
                    Text(about, style: s.hint(13)),
                  ]),
                ),
              ]),
            ),
        ]),
      ),
      const SizedBox(height: 4),
      Text('支付还没有接入。现在点开通不会扣费，只是打开会员功能方便体验。', style: s.hint(12)),
      const SizedBox(height: 12),
      SButton(store.member ? '关闭会员（演示）' : '开通会员（演示，不扣费）', expand: true, ghost: store.member, onTap: () async {
        try {
          await store.setMember(!store.member);
          if (!context.mounted) return;
          toast(context, store.member ? '会员功能已打开' : '已关闭会员');
          Navigator.of(context).pop();
        } on ApiError catch (e) {
          if (context.mounted) toast(context, e.message);
        }
      }),
    ]);
  });
}

/// 形象模式。现在只有动漫形象有素材，其余三种选了也先显示动漫形象。
const lookModes = <String, (String, String)>{
  'q': ('Q 版形象', '二三头身，圆圆的'),
  'anime': ('动漫形象', '现在房间里的就是她'),
  'real': ('AI 真人写实', '写实的三维形象'),
  'self': ('贴合本人', '保留你自己的五官、比例和肤质'),
};

void showLooks(BuildContext context) {
  showSkinSheet<void>(context, tall: true, (context, s) {
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('我的形象', style: s.title(22)),
      const SizedBox(height: 4),
      Text('目前只有动漫形象有模型，其余三种的素材还在准备，选了也先显示动漫形象。', style: s.hint(13)),
      const SizedBox(height: 14),
      for (final e in lookModes.entries)
        GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: () {
            store.updateProfile(lookMode: e.key);
          },
          child: Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.fromLTRB(14, 11, 14, 11),
            decoration: BoxDecoration(
              color: s.card,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: e.key == store.lookMode ? s.deep : s.line, width: e.key == store.lookMode ? 1.6 : 1),
            ),
            child: Row(children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(e.value.$1, style: s.body(15.5).copyWith(fontWeight: FontWeight.w700)),
                  Text(e.value.$2, style: s.hint(12.5)),
                ]),
              ),
              if (e.key != 'anime') Text('素材待补', style: s.hint(11.5)),
            ]),
          ),
        ),
      const SizedBox(height: 6),
      Text('相貌状态', style: s.hint(13)),
      const SizedBox(height: 8),
      Row(children: [
        SChip('固定原生相貌', on: !store.lookDynamic, onTap: () {
          store.updateProfile(lookDynamic: false);
        }),
        const SizedBox(width: 8),
        SChip('动态显化相貌', on: store.lookDynamic, onTap: () {
          store.updateProfile(lookDynamic: true);
        }),
      ]),
      const SizedBox(height: 8),
      Text(store.lookDynamic ? '跟着外貌肯定语一点点往更好的状态微调。' : '完全保留本来的五官、比例和肤质，不做修改。', style: s.hint(12.5)),
    ]);
  });
}

void showPets(BuildContext context) {
  final name = TextEditingController();
  var kind = '狗狗';
  showSkinSheet<void>(context, tall: true, (context, s) {
    return StatefulBuilder(builder: (context, setState) {
      return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('我的宠物', style: s.title(22)),
        const SizedBox(height: 4),
        Text('它们会出现在你的主页和房间里。可以给它们许愿，也可以在商城给它们买装扮。', style: s.hint(13)),
        const SizedBox(height: 14),
        Flexible(
          child: ListView(shrinkWrap: true, children: [
            for (final p in store.pets)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Row(children: [
                  Avatar(p['name'] as String, size: 46, photo: p['photo'] as String?),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(p['name'] as String, style: s.body(15.5).copyWith(fontWeight: FontWeight.w700)),
                      Text(p['kind'] as String, style: s.hint(12.5)),
                    ]),
                  ),
                  SButton(p['photo'] == null ? '传照片' : '换照片', small: true, ghost: true, onTap: p['id'] == null
                      ? null
                      : () async {
                          try {
                            final url = await store.pickAndUpload();
                            if (url != null) await store.setPetPhoto(p, url);
                          } on ApiError catch (e) {
                            if (context.mounted) toast(context, e.message);
                          }
                        }),
                  const SizedBox(width: 6),
                  GestureDetector(
                    onTap: () => store.removePet(p).catchError((e) {
                      if (context.mounted) toast(context, '$e');
                    }),
                    child: Padding(padding: const EdgeInsets.all(6), child: Text('移除', style: s.hint(12.5))),
                  ),
                ]),
              ),
          ]),
        ),
        Text('用照片生成它的专属三维形象还没接入，现在照片只当头像用；房间里显示的是示例小狗。', style: s.hint(12)),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(child: SField(controller: name, hint: '新成员的名字')),
          const SizedBox(width: 8),
          for (final k in ['狗狗', '猫咪'])
            Padding(padding: const EdgeInsets.only(right: 6), child: SChip(k, on: kind == k, onTap: () => setState(() => kind = k))),
        ]),
        const SizedBox(height: 12),
        SButton('添加', expand: true, onTap: () {
          if (name.text.trim().isEmpty) return toast(context, '先给它起个名字');
          store.addPet(name.text.trim(), kind);
          name.clear();
        }),
      ]);
    });
  });
}

void showFriends(BuildContext context) {
  showSkinSheet<void>(context, tall: true, (context, s) {
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('好友', style: s.title(22)),
      const SizedBox(height: 4),
      Text('好友之间可以互相点赞、夸夸。私信没有开放。', style: s.hint(13)),
      const SizedBox(height: 14),
      Flexible(
        child: ListView(shrinkWrap: true, children: [
          if (store.requests.isNotEmpty) ...[
            Text('新的好友申请', style: s.hint(13)),
            const SizedBox(height: 8),
            for (final r in store.requests)
              _personRow(s, r['user'] as Map, [
                SButton('同意', small: true, onTap: () async {
                  try {
                    final got = await store.answerRequest(r['id'] as int, true);
                    if (context.mounted) coinToast(context, got, '成为好友');
                  } on ApiError catch (e) {
                    if (context.mounted) toast(context, e.message);
                  }
                }),
                const SizedBox(width: 6),
                SButton('忽略', small: true, ghost: true, onTap: () => store.answerRequest(r['id'] as int, false).catchError((e) => 0)),
              ]),
            const SizedBox(height: 10),
          ],
          if (store.friends.isEmpty) Padding(padding: const EdgeInsets.symmetric(vertical: 20), child: Center(child: Text('还没有好友。去广场点「加好友」。', style: s.hint(14)))),
          for (final u in store.friends)
            _personRow(s, u, [
              SButton('移除', small: true, ghost: true, onTap: () => store.removeFriend(u['id'] as int).catchError((e) {
                    if (context.mounted) toast(context, '$e');
                  })),
            ]),
        ]),
      ),
    ]);
  });
}

Widget _personRow(Skin s, Map u, List<Widget> actions) => Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(children: [
        Avatar(u['name'] as String, size: 44, photo: u['avatar'] as String?),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(u['name'] as String, style: s.body(15.5).copyWith(fontWeight: FontWeight.w700)),
            Text(u['title'] as String? ?? '', style: s.hint(12.5)),
          ]),
        ),
        ...actions,
      ]),
    );

/// 我发过的朋友圈和感恩日记，包括仅自己可见的
void showMyPosts(BuildContext context) {
  final load = ValueNotifier<Future<dynamic>>(store.api.get('/me/posts'));
  showSkinSheet<void>(context, tall: true, (context, s) {
    return ValueListenableBuilder(
      valueListenable: load,
      builder: (context, future, _) => FutureBuilder(
        future: future,
        builder: (context, snap) {
          if (snap.hasError) return Padding(padding: const EdgeInsets.all(30), child: Center(child: Text('${snap.error}', style: s.hint(14))));
          if (!snap.hasData) return const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator()));
          final posts = snap.data['items'] as List;
          return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('我的动态', style: s.title(22)),
            const SizedBox(height: 12),
            if (posts.isEmpty) Padding(padding: const EdgeInsets.symmetric(vertical: 20), child: Center(child: Text('还没有写过。去广场点「写一条」。', style: s.hint(14)))),
            Flexible(
              child: ListView(shrinkWrap: true, children: [
                for (final p in posts)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 14),
                    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text('${postTypes[p['type']]} · ${p['public'] == true ? '公开 · ${p['likes']} 个赞' : '仅自己可见'}', style: s.hint(12)),
                          const SizedBox(height: 2),
                          Text(p['text'] as String, style: s.body(15)),
                          for (final x in p['praises'] as List)
                            Padding(padding: const EdgeInsets.only(top: 4), child: Text('${x['ai'] == true ? 'AI 夸夸' : '夸夸'}：${x['text']}', style: s.hint(13))),
                        ]),
                      ),
                      GestureDetector(
                        onTap: () async {
                          try {
                            await store.api.delete('/posts/${p['id']}');
                            load.value = store.api.get('/me/posts');
                          } on ApiError catch (e) {
                            if (context.mounted) toast(context, e.message);
                          }
                        },
                        child: Padding(padding: const EdgeInsets.all(6), child: Text('删除', style: s.hint(12.5))),
                      ),
                    ]),
                  ),
              ]),
            ),
          ]);
        },
      ),
    );
  });
}

/// 圆环形的小进度，汇总页用
class Ring extends StatelessWidget {
  final double value;
  final Color color;
  final Color track;
  final double size;
  const Ring({super.key, required this.value, required this.color, required this.track, this.size = 40});

  @override
  Widget build(BuildContext context) => CustomPaint(size: Size.square(size), painter: _RingPainter(value, color, track));
}

class _RingPainter extends CustomPainter {
  final double value;
  final Color color;
  final Color track;
  _RingPainter(this.value, this.color, this.track);

  @override
  void paint(Canvas canvas, Size size) {
    final r = Offset.zero & size;
    final p = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = size.width * 0.12
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(r.deflate(p.strokeWidth / 2), 0, math.pi * 2, false, p..color = track);
    canvas.drawArc(r.deflate(p.strokeWidth / 2), -math.pi / 2, math.pi * 2 * value.clamp(0, 1), false, p..color = color);
  }

  @override
  bool shouldRepaint(_RingPainter old) => old.value != value || old.color != color;
}
