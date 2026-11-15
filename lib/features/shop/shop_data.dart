/// 成品肯定语音频。语音是预先生成的：`assets/voice/<id>_<1..4>.m4a`，文字要和 tools/tts/generate_guides.py 里的 LIBRARY 一致。
class Track {
  final String id;
  final String name;
  final List<String> lines;
  const Track(this.id, this.name, this.lines);
}

const tracks = [
  Track('lib_all', '综合', ['我值得一切美好。', '我想要的，正在向我走来。', '我相信自己，也相信时间。', '我已经走在路上了。']),
  Track('lib_wealth', '财富', ['我值得拥有丰盛。', '金钱以轻松的方式流向我。', '我善用每一份收入，也安心地享受它。', '我的价值，一直在增长。']),
  Track('lib_career', '事业', ['我清楚自己要去哪里。', '我的努力，正在被看见。', '机会喜欢准备好的我。', '我从容地走在自己的节奏里。']),
  Track('lib_looks', '外貌', ['我喜欢镜子里的自己。', '我的身体，每天都在变得更好。', '我由内而外地发着光。', '我本来的样子，就很美。']),
  Track('lib_health', '健康', ['我的身体知道如何修复自己。', '每一次呼吸，都在给我力量。', '我睡得安稳，醒来有精神。', '我温柔地照顾自己。']),
  Track('lib_mood', '情绪', ['我允许情绪来，也允许它走。', '我的心，越来越安定。', '我对自己很温柔。', '今天，我选择平静。']),
];

/// 愿望商店里的一件装扮。[id] 同时是房间里那件装扮的名字（见 RoomView.swift 的 buildDecor）或头像框的名字。
class ShopItem {
  final String id;
  final String name;
  final String about;
  final int price;

  /// room 房间装饰、frame 头像框（同时只能戴一个）、pet 宠物装扮
  final String group;

  /// 会员限定：会员免费领，非会员买不了
  final bool member;
  const ShopItem(this.id, this.name, this.about, this.price, this.group, {this.member = false});
}

const shopItems = [
  ShopItem('wall_stars', '墙上的星星', '后墙上一小片金色的星', 60, 'room'),
  ShopItem('balloons', '一束气球', '窗边飘着三只气球', 80, 'room'),
  ShopItem('moon_lamp', '月亮灯', '窗台上一盏会发光的月亮', 120, 'room'),
  ShopItem('frame_gold', '鎏金头像框', '头像外面一圈流动的金', 50, 'frame'),
  ShopItem('frame_star', '星彩头像框', '头像外面一圈柔和的彩', 50, 'frame'),
  ShopItem('pet_bowl', '小食盆', '地毯边上放一只蓝色的食盆', 30, 'pet'),
  ShopItem('pet_ball', '小皮球', '一只红色的小球，等它来叼', 30, 'pet'),
  ShopItem('pet_bed', '云朵软垫窝', '粉色的圆窝，会员限定', 0, 'pet', member: true),
];
