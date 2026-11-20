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

  /// room 房间装饰、frame 头像框（同时只能戴一个）、pet 宠物装扮、
  /// keepsake 小动物的礼物（都是头像框，不卖：动物送的，或用收藏品换的）
  final String group;

  /// 会员限定：会员免费领，非会员买不了
  final bool member;

  /// 小动物的礼物才有：哪只动物送的（它的名字），或者用哪些收藏品换（编号 → 几个）
  final String? petName;
  final Map<String, int> cost;
  const ShopItem(this.id, this.name, this.about, this.price, this.group, {this.member = false, this.petName, this.cost = const {}});

  /// 是不是头像框（戴在头像外面，同时只能戴一个）
  bool get isFrame => group == 'frame' || group == 'keepsake';
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

/// 湖心小寺的口粮：买的是数量，放进背包，喂岛上的小动物。价格和涨多少以服务端 server/app/islet.py 的 FOODS 为准。
class FoodItem {
  final String id;
  final String name;
  final String about;
  final int price;

  /// 喂一次涨多少亲密度（喂到它最爱的再乘 1.5）
  final int feed;
  const FoodItem(this.id, this.name, this.about, this.price, this.feed);
}

const foodItems = [
  FoodItem('food_kibble', '小饼干', '烤得脆脆的，谁都不挑', 2, 2),
  FoodItem('food_dried_fish', '小鱼干', '晒得干干的，猫闻到就走不动', 5, 3),
  FoodItem('food_bone', '肉骨头', '还带着一点肉，狗能啃一下午', 5, 3),
  FoodItem('food_cream', '猫条', '挤出来一点点舔着吃，最金贵的零嘴', 8, 4),
];

/// 小动物的专属礼物：和它的亲密度到这个数时它送给你。以服务端 server/app/catalog.py 的 KEEPSAKE_AT 为准
const keepsakeAt = 50;

/// 小动物的礼物：不卖。来路以服务端 server/app/catalog.py 的 KEEPSAKES 为准。
const keepsakes = [
  ShopItem('frame_teddy', '栗子的爪印头像框', '栗色的皮圈上，一圈小爪印踩过去', 0, 'keepsake', petName: '栗子'),
  ShopItem('frame_shiba', '年糕的树枝头像框', '它捡来的两根好树枝，弯成了一圈', 0, 'keepsake', petName: '年糕'),
  ShopItem('frame_cotton', '棉花的云朵头像框', '软软的一圈白云，藏着两朵小花', 0, 'keepsake', petName: '棉花'),
  ShopItem('frame_tangerine', '橘子同款小鱼头像框', '四条小鱼绕着你追尾巴', 0, 'keepsake', petName: '橘子'),
  ShopItem('frame_tangyuan', '汤圆的蓝眼睛头像框', '一对白耳朵，两颗蓝宝石一样的眼睛', 0, 'keepsake', petName: '汤圆'),
  ShopItem('frame_huajuan', '花卷的三花头像框', '一块橘一块黑的毛色，别着小花', 0, 'keepsake', petName: '花卷'),
  ShopItem('frame_zhima', '芝麻的骨头头像框', '黑芝麻色的一圈，四个角各一根骨头', 0, 'keepsake', petName: '芝麻'),
  ShopItem('frame_tuanzi', '团子的铃铛头像框', '红项圈，底下挂一只小金铃', 0, 'keepsake', petName: '团子'),
  ShopItem('frame_momo', '墨墨的月夜头像框', '墨色的夜空，月亮底下蹲着一只小黑猫', 0, 'keepsake', petName: '墨墨'),
  ShopItem('frame_doubao', '豆包的毛线球头像框', '两股豆沙色的毛线绕成一圈', 0, 'keepsake', petName: '豆包'),
  ShopItem('frame_shell', '贝壳风铃头像框', '顶上三枚贝壳，底下垂着一串风铃', 0, 'keepsake', cost: {'shell': 5, 'shell_conch': 2}),
  ShopItem('frame_autumn', '秋叶标本头像框', '枫叶和银杏叶一红一黄，压成一圈', 0, 'keepsake', cost: {'maple': 3, 'ginkgo': 3}),
  ShopItem('frame_meadow', '野花草环头像框', '青藤编的环，开满小野花', 0, 'keepsake', cost: {'flower': 4, 'clover': 2, 'feather': 2}),
  ShopItem('frame_pearl', '珍珠平安扣头像框', '一整圈珍珠，底下系一枚平安结', 0, 'keepsake', cost: {'pearl': 1, 'knot': 1}),
];

/// 收藏品叫什么（兑换要用的那几样），显示「5 贝壳 + 2 海螺」用
const keepNames = {
  'shell': '贝壳', 'shell_conch': '海螺', 'maple': '枫叶', 'ginkgo': '银杏叶', 'flower': '小野花', 'clover': '四叶草', 'feather': '羽毛', 'pearl': '珍珠', 'knot': '平安结', //
};

/// 一件小动物的礼物怎么得到，写成一句短话
String keepsakeSource(ShopItem item) => item.petName != null
    ? '和${item.petName}的亲密度到 $keepsakeAt'
    : '${item.cost.entries.map((e) => '${e.value} ${keepNames[e.key] ?? e.key}').join(' + ')} 兑换';
