import 'package:flutter/material.dart';
import 'package:yuanjing_engine/yuanjing_engine.dart';

import '../../app/store.dart';

/// 我的房间：原生渲染的房间和形象，Flutter 只放标题和动作按钮。从「我的」里点进来。
/// 商城里买了并戴上的装扮（气球、星星、月亮灯、宠物的窝和玩具）会出现在房间里。
class RoomPage extends StatefulWidget {
  const RoomPage({super.key});

  @override
  State<RoomPage> createState() => _RoomPageState();
}

class _RoomPageState extends State<RoomPage> {
  final _room = RoomController();

  @override
  void initState() {
    super.initState();
    YuanjingAudio.bed('room');
    store.addListener(_syncDecor);
  }

  @override
  void dispose() {
    store.removeListener(_syncDecor);
    super.dispose();
  }

  void _syncDecor() => _room.setDecor(store.equipped.toList());

  static const _ink = Color(0xFF4A3528);
  static const _actions = [('wave', '打个招呼'), ('pet', '逗逗小狗'), ('spin', '转个圈')];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
        body: Stack(
      fit: StackFit.expand,
      children: [
        RoomStage(
          decor: store.equipped.toList(),
          controller: _room,
          model: 'assets/models/girl_a.vrm',
          pets: const ['assets/models/shiba.glb', 'assets/models/husky.glb'],
          plush: 'assets/models/poodle.glb',
        ),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(22, 6, 22, 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () => Navigator.of(context).maybePop(),
                  child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 6), child: Text('‹ 返回', style: TextStyle(fontSize: 14, color: _ink.withValues(alpha: 0.7)))),
                ),
                const Text('我的房间',
                    style: TextStyle(fontFamily: 'YuanjingSerif', fontSize: 30, fontWeight: FontWeight.w700, letterSpacing: 1.5, color: _ink)),
                const SizedBox(height: 6),
                Text('她会跟着你的心愿，一天天变成你想成为的样子。', style: TextStyle(fontSize: 13.5, color: _ink.withValues(alpha: 0.7))),
                const Spacer(),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    for (final (id, label) in _actions)
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 5),
                        child: GestureDetector(
                          onTap: () => _room.perform(id),
                          child: Container(
                            height: 42,
                            padding: const EdgeInsets.symmetric(horizontal: 16),
                            alignment: Alignment.center,
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.86),
                              borderRadius: BorderRadius.circular(99),
                              border: Border.all(color: Colors.white),
                              boxShadow: [BoxShadow(color: _ink.withValues(alpha: 0.18), blurRadius: 16, offset: const Offset(0, 6))],
                            ),
                            child: Text(label, style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w600, color: _ink)),
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 12),
                Center(child: Text('形象和家具目前是占位素材', style: TextStyle(fontSize: 12, color: _ink.withValues(alpha: 0.55)))),
              ],
            ),
          ),
        ),
      ],
    ));
  }
}
