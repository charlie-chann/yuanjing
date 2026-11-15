import 'package:flutter_test/flutter_test.dart';
import 'package:yuanjing/features/release/release_data.dart';

void main() {
  test('什么都没填时不给解读', () {
    expect(readSticking('  ', {}), isNull);
  });

  test('按文字里的关键词认出卡点', () {
    final r = readSticking('今天被上司骂了，同事针对我，我觉得自己总是被欺负。', {})!;
    expect(r.sticking.key, 'wronged');
    expect(r.emotions, contains('委屈'));
    expect(r.emotions.length, lessThanOrEqualTo(3));
  });

  test('选中的标签比关键词更有分量', () {
    final r = readSticking('最近加班好累', {'anxiety'})!;
    expect(r.sticking.key, 'anxiety');
    // 第二接近的卡点（压力过载）补一个情绪进来
    expect(r.emotions, contains('疲惫'));
  });

  test('只写了字又对不上任何词，用压力过载接住', () {
    expect(readSticking('唉', {})!.sticking.key, 'overload');
  });

  test('情绪重的时候推荐深度释放', () {
    expect(readSticking('有点担心明天的面试', {})!.deep, isFalse);
    expect(readSticking('我总是这样，每次都搞砸，真的很崩溃', {'failure'})!.deep, isTrue);
  });

  test('出现危险说法时先给求助信息', () {
    expect(needsSupport('我不想活了'), isTrue);
    expect(needsSupport('今天好累'), isFalse);
  });

  test('两档的总时长落在需求的范围里：轻量 1 到 2 分钟，深度 3 到 5 分钟', () {
    for (final s in releaseStyles) {
      expect(totalLength(s, lightRelease).inSeconds, inInclusiveRange(60, 120), reason: s.name);
      expect(totalLength(s, deepRelease).inSeconds, inInclusiveRange(180, 300), reason: s.name);
    }
  });

  test('留白提示夹在引导语的空档里，不和引导语撞在一起', () {
    for (final s in releaseStyles) {
      for (final d in [lightRelease, deepRelease]) {
        final ms = ritualLength(s, d).inMilliseconds;
        final holds = holdTimes(s, d);
        expect(holds, isNotEmpty);
        for (final (at, line) in holds) {
          expect(line, lessThan(holdLines.length));
          for (final other in s.at) {
            // 每句话四五秒，两句之间至少隔六秒
            expect(((at - other) * ms).abs(), greaterThanOrEqualTo(6000), reason: '${s.name} ${d.name}');
          }
        }
      }
    }
  });

  test('卡点和释放方式的数据完整、名字不重复', () {
    expect(stickings.map((s) => s.key).toSet().length, 8);
    expect(releaseStyles.map((s) => s.scene).toSet().length, 5);
    for (final s in releaseStyles) {
      expect(s.lines.length, 4);
      expect(s.at.length, 3);
    }
  });
}
