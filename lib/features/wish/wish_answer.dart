import 'dart:async';

import 'package:yuanjing_engine/yuanjing_engine.dart';

import '../../app/store.dart';

/// 一条许愿回应：四句话（开场、核心、行动、收尾），每句可能有一段语音（已经下载到本机）。
///
/// 回应来自后端的回应库（tools/wishdb，131 种愿望、104.8 万条组合），由关键词和字词相似度匹配，
/// 不接大模型。连不上服务器时返回 null，许愿页用原来的固定引导语。
class WishAnswer {
  final String intent;
  final String intentName;

  /// 这条愿望归到哪一类（财富、事业……），记心愿时用
  final String scene;
  final List<String> lines;

  /// 每句语音在本机的路径；没有录音的那句是 null
  final List<String?> files;

  const WishAnswer(this.intent, this.intentName, this.lines, this.files, {this.scene = 'life'});

  /// 需要真人帮助的说法：不播回应，许愿页改为显示求助信息
  static const support = WishAnswer('support', '', [], []);
  bool get isSupport => intent == 'support';

  /// 请求一条回应，并把四段语音下载到本机。整体最多等 [wait]，超时返回 null。
  static Future<WishAnswer?> fetch(String text, String scene, {Duration wait = const Duration(seconds: 4)}) async {
    if (!store.online || store.dir == null) return null;
    try {
      return await _fetch(text, scene).timeout(wait);
    } catch (_) {
      return null;
    }
  }

  static Future<WishAnswer?> _fetch(String text, String scene) async {
    final r = await store.api.post('/wish/answer', {'text': text, 'scene': scene, 'hour': DateTime.now().hour});
    if (r['support'] == true) return support;
    final lines = (r['lines'] as List).cast<String>();
    final urls = (r['audio'] as List).cast<String?>();
    final segs = (r['segments'] as List).cast<int>();
    final files = await Future.wait([
      for (var i = 0; i < urls.length; i++)
        if (urls[i] == null)
          Future.value(null)
        else
          () async {
            final path = '${store.dir}/voice_cache/${segs[i]}.m4a';
            try {
              await store.api.download(urls[i]!, path);
              return path;
            } catch (_) {
              return null;
            }
          }(),
    ]);
    return WishAnswer(r['intent'] as String, r['intent_name'] as String, lines, files, scene: (r['scene'] as String?) ?? scene);
  }

  /// 播第 [i] 句，返回它有多长（没有录音时按字数估一个阅读时间）
  Future<Duration> play(int i) async {
    final f = files[i];
    final d = f == null ? null : await YuanjingVoice.playFile(f);
    return d ?? Duration(milliseconds: 1200 + lines[i].length * 220);
  }
}
