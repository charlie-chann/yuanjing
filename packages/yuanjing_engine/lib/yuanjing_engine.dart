/// 愿境原生引擎的 Dart 一侧。
///
/// 重动画都在原生层渲染（iOS：Metal / RealityKit），Flutter 只负责把它摆进界面、告诉它演哪一场。
library;

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

/// 仪式舞台的遥控器。一个控制器对应一块 [WishStage]。
class WishStageController {
  MethodChannel? _channel;
  String _scene;

  WishStageController({String scene = 'wealth'}) : _scene = scene; // ignore: prefer_initializing_formals

  /// 仪式进行中为 true。
  final ValueNotifier<bool> playing = ValueNotifier(false);

  /// 仪式播完时触发。
  VoidCallback? onDone;

  /// 解压小游戏的状态，原生层每秒发十几次：这一轮的进度、手速攒出来的能量（都是 0 到 1）、
  /// 奖励动画的进度（没到是 -1）、已经攒满过几轮。
  final ValueNotifier<StageGame> game = ValueNotifier(const StageGame());

  /// 小游戏攒满了，奖励动画开始。
  ValueChanged<int>? onGameWin;

  /// 奖励动画放完了，画面停在最后的样子。
  ValueChanged<int>? onGameDone;

  String get scene => _scene;

  void _attach(int viewId) {
    _channel = MethodChannel('yuanjing/stage_$viewId')
      ..setMethodCallHandler((call) async {
        if (call.method == 'done') {
          playing.value = false;
          onDone?.call();
        } else if (call.method == 'game') {
          final m = (call.arguments as Map).cast<String, Object?>();
          game.value = StageGame(
            progress: (m['g'] as num).toDouble(),
            energy: (m['e'] as num).toDouble(),
            reward: (m['r'] as num).toDouble(),
            round: (m['round'] as num).toInt(),
          );
        } else if (call.method == 'gameWin') {
          onGameWin?.call(((call.arguments as Map)['round'] as num).toInt());
        } else if (call.method == 'gameDone') {
          onGameDone?.call(((call.arguments as Map)['round'] as num).toInt());
        }
      });
  }

  /// 换一场戏（财富 wealth、事业 career、外貌 looks、健康 health、情绪 mood、生活 life、宠物 pet，
  /// 以及卡点释放的 release_pool、release_balloon、release_arrow、release_potion、release_deep）。
  Future<void> setScene(String scene) async {
    _scene = scene;
    await _channel?.invokeMethod('setScene', {'scene': scene});
  }

  /// 开始仪式，返回这场仪式的时长。原生层没就绪时返回 null。
  ///
  /// 卡点释放的五场（release_pool、release_balloon、release_arrow、release_potion、release_deep）
  /// 可以用 [duration] 指定时长，画面和音效按比例拉伸；许愿的七场时长固定，传了也不生效。
  Future<Duration?> play({Duration? duration}) async {
    final seconds = await _channel?.invokeMethod<double>('play', {
      if (duration != null) 'duration': duration.inMilliseconds / 1000,
    });
    if (seconds == null) return null;
    playing.value = true;
    return Duration(milliseconds: (seconds * 1000).round());
  }

  /// 中途结束仪式：不触发 [onDone]，画面回到开始前的样子。
  Future<void> stop() async {
    playing.value = false;
    await _channel?.invokeMethod('stop');
  }

  /// 清掉放完之后的余韵，回到开始前的样子（释放仪式再来一次时用）。
  Future<void> reset() async => _channel?.invokeMethod('reset');

  /// 页面不可见时暂停渲染，省电。
  Future<void> setPaused(bool paused) async => _channel?.invokeMethod('setPaused', {'paused': paused});

  /// 手指或陀螺仪带来的轻微视差，x、y 取 -1..1。
  Future<void> setTouch(double x, double y) async => _channel?.invokeMethod('setTouch', {'x': x, 'y': y});

  /// 进入解压小游戏（只有释放的五场有）。画面暗一下再亮起来就是游戏的开头。仪式进行中会被拒绝，返回 false。
  Future<bool> gameStart() async {
    game.value = const StageGame();
    return await _channel?.invokeMethod<bool>('gameStart') ?? false;
  }

  /// 退出小游戏，回到仪式开始前的样子。
  Future<void> gameStop() async => _channel?.invokeMethod('gameStop');

  /// 奖励动画放完以后再来一轮。
  Future<void> gameAgain() async => _channel?.invokeMethod('gameAgain');

  /// 点了一下。x、y 是画面坐标：y 从下到上 -1..1，x 按同样的比例（竖屏时大约 -0.46..0.46）。
  /// [strength] 1 是一次完整的点击；拖着搅动时每挪一小段发一个零点几。
  Future<void> gameTap(double x, double y, {double strength = 1}) async =>
      _channel?.invokeMethod('gameTap', {'x': x, 'y': y, 'k': strength});

  void dispose() {
    playing.dispose();
    game.dispose();
  }
}

/// 解压小游戏此刻的状态。
class StageGame {
  /// 这一轮攒了多少，0 到 1
  final double progress;

  /// 手速攒出来的能量，0 到 1；不点了会慢慢落回去
  final double energy;

  /// 奖励动画的进度；还没攒满是 -1，放完停在 1
  final double reward;

  /// 已经攒满过几轮
  final int round;

  const StageGame({this.progress = 0, this.energy = 0, this.reward = -1, this.round = 0});
}

/// 全屏仪式舞台。目前只有 iOS 实现，其他平台显示黑底。
class WishStage extends StatelessWidget {
  final WishStageController controller;

  const WishStage({super.key, required this.controller});

  @override
  Widget build(BuildContext context) {
    if (defaultTargetPlatform != TargetPlatform.iOS) return const ColoredBox(color: Color(0xFF000000));
    return UiKitView(
      viewType: 'yuanjing/stage',
      creationParams: {'scene': controller.scene},
      creationParamsCodec: const StandardMessageCodec(),
      onPlatformViewCreated: controller._attach,
    );
  }
}

/// 界面上的触感（按钮、选中）。仪式里的触感由原生层按画面节点自己打。
class YuanjingHaptics {
  static const _channel = MethodChannel('yuanjing/engine');

  static Future<void> play(String name) async {
    try {
      await _channel.invokeMethod('haptic', {'name': name});
    } on MissingPluginException {
      // 非 iOS 平台没有实现
    }
  }
}

/// 引导语音：播放预先生成好的音频（Flutter 资源路径，如 `assets/voice/wealth_1.m4a`）。
class YuanjingVoice {
  static const _channel = MethodChannel('yuanjing/engine');

  /// 文件不存在时静默返回 false。
  static Future<bool> play(String asset, {double volume = 1}) async {
    try {
      return await _channel.invokeMethod<bool>('voice', {'asset': asset, 'volume': volume}) ?? false;
    } on MissingPluginException {
      return false;
    }
  }

  static Future<void> stop() async {
    try {
      await _channel.invokeMethod('voiceStop');
    } on MissingPluginException {
      // 非 iOS 平台没有实现
    }
  }

  /// 播放本机文件里的一句（绝对路径），返回它有多长；文件不存在返回 null。
  static Future<Duration?> playFile(String path, {double volume = 1}) async {
    try {
      final seconds = await _channel.invokeMethod<double>('voiceFile', {'path': path, 'volume': volume});
      return seconds == null ? null : Duration(milliseconds: (seconds * 1000).round());
    } on MissingPluginException {
      return null;
    }
  }

  /// 播一句并返回它有多长。冥想那种一句接一句的用它排时间；文件不存在返回 null。
  static Future<Duration?> playTimed(String asset, {double volume = 1}) async {
    try {
      final seconds = await _channel.invokeMethod<double>('voiceTimed', {'asset': asset, 'volume': volume});
      return seconds == null ? null : Duration(milliseconds: (seconds * 1000).round());
    } on MissingPluginException {
      return null;
    }
  }
}

/// 朗读任意文字（系统自带的中文语音）。只给用户自己写的肯定语用，预先生成的引导语走 [YuanjingVoice]。
class YuanjingSpeak {
  static const _channel = MethodChannel('yuanjing/engine');

  /// 念完返回 true，被打断返回 false。
  static Future<bool> speak(String text) async {
    try {
      return await _channel.invokeMethod<bool>('speak', {'text': text}) ?? false;
    } on MissingPluginException {
      return false;
    }
  }

  static Future<void> stop() async {
    try {
      await _channel.invokeMethod('speakStop');
    } on MissingPluginException {
      // 非 iOS 平台没有实现
    }
  }

  /// 存成音频文件并弹出系统分享面板。
  static Future<bool> export(String text) async {
    try {
      return await _channel.invokeMethod<bool>('speakExport', {'text': text}) ?? false;
    } on MissingPluginException {
      return false;
    }
  }
}

/// 语音输入：边说边出字。
class YuanjingSpeech {
  static const _channel = MethodChannel('yuanjing/engine');
  static const _events = EventChannel('yuanjing/speech');

  /// 识别结果：文字是「到目前为止说的整段话」，ended 为 true 表示这一次听写结束了。
  static Stream<({String text, bool ended})> get results => _events.receiveBroadcastStream().map((e) {
        final m = e as Map;
        return (text: m['text'] as String? ?? '', ended: m['ended'] == true);
      });

  /// 开始听。成功返回 null，失败返回一句给用户看的原因。
  static Future<String?> start() async {
    try {
      return await _channel.invokeMethod<String>('listenStart');
    } on MissingPluginException {
      return '这个平台还不支持语音输入';
    }
  }

  static Future<void> stop() async {
    try {
      await _channel.invokeMethod('listenStop');
    } on MissingPluginException {
      // 非 iOS 平台没有实现
    }
  }
}

/// 文件相关的系统能力。
class YuanjingFiles {
  static const _channel = MethodChannel('yuanjing/engine');

  /// 应用自己的文件夹，存档和选来的图都放这里。
  static Future<String?> docsDir() async {
    try {
      return await _channel.invokeMethod<String>('docsDir');
    } on MissingPluginException {
      return null;
    }
  }

  /// 从相册选一张图。返回相对 [docsDir] 的路径，取消返回 null。
  static Future<String?> pickPhoto() async {
    try {
      return await _channel.invokeMethod<String>('pickPhoto');
    } on MissingPluginException {
      return null;
    }
  }
}

/// 房间的遥控器：让形象做动作。
class RoomController {
  MethodChannel? _channel;

  /// 动作：wave 挥手、smile 微笑、spin 转一圈、pet 逗小狗。
  Future<void> perform(String action) async => _channel?.invokeMethod('action', {'name': action});

  /// 换装扮：只显示这几件（balloons、wall_stars、moon_lamp、pet_bed、pet_bowl、pet_ball）。
  Future<void> setDecor(List<String> names) async => _channel?.invokeMethod('decor', {'names': names});
}

/// 我的房间：原生 RealityKit 场景。需要 iOS 18；[model] 是形象的 Flutter 资源路径（.vrm）。
class RoomStage extends StatelessWidget {
  final RoomController controller;
  final String model;

  /// 带动画的宠物（.glb），最多两只
  final List<String> pets;

  /// 放在床上的静态玩偶（.glb）
  final String? plush;

  /// 一开始就显示的装扮
  final List<String> decor;

  const RoomStage({super.key, required this.controller, required this.model, this.pets = const [], this.plush, this.decor = const []});

  @override
  Widget build(BuildContext context) {
    if (defaultTargetPlatform != TargetPlatform.iOS) return const ColoredBox(color: Color(0xFFEDE1D6));
    return UiKitView(
      viewType: 'yuanjing/room',
      creationParams: {'model': model, 'pets': pets, 'plush': plush, 'decor': decor},
      creationParamsCodec: const StandardMessageCodec(),
      onPlatformViewCreated: (id) => controller._channel = MethodChannel('yuanjing/room_$id'),
    );
  }
}

/// 环境音和音效。素材在 `assets/audio/`，见 tools/audio/generate_audio.py。
class YuanjingAudio {
  static const _channel = MethodChannel('yuanjing/engine');

  /// 换环境音：wealth、career、looks、health、mood、life、pet、room；传 null 淡出到无声。
  static Future<void> bed(String? name) => _call('bed', {'name': name});

  /// 播一个音效，例如 tap、pick、chime、sparkle。
  static Future<void> sfx(String name, {double volume = 1}) => _call('sfx', {'name': name, 'volume': volume});

  static Future<void> _call(String method, Map<String, Object?> args) async {
    try {
      await _channel.invokeMethod(method, args);
    } on MissingPluginException {
      // 非 iOS 平台没有实现
    }
  }
}
