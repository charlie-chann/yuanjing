import 'package:flutter/painting.dart';

/// 一个心愿分类，和它专属的那场仪式。
class WishCategory {
  /// 原生舞台里的场景名
  final String scene;
  final String name;

  /// 仪式的名字，显示在舞台下方
  final String ritual;
  final String hint;

  /// 仪式进行时依次出现的三句引导语
  final List<String> lines;
  final Color light;
  final Color deep;

  const WishCategory(this.scene, this.name, this.ritual, this.hint, this.lines, this.light, this.deep);
}

const wishCategories = <WishCategory>[
  WishCategory('wealth', '财富', '金币落入金池', '比如：愿这个月的收入，比我预想的更宽裕。',
      ['把心愿交给这枚金币。', '听，它们一枚一枚落下来了。', '丰盛正在流向你。'], Color(0xFFFBDD8F), Color(0xFFC08A2A)),
  WishCategory('career', '事业', '登顶日出', '比如：愿这周的提案一次通过。',
      ['一点光，从山脚出发。', '它到顶了。', '天亮了，这是你的早晨。'], Color(0xFFFFD2A6), Color(0xFFD9713F)),
  WishCategory('looks', '外貌', '缎面上的珍珠', '比如：愿我气色通透，眼里有光。',
      ['光从你身上滑过。', '你本来就在发光。', '被看见，也被自己喜欢。'], Color(0xFFFFD9DF), Color(0xFFCF6F88)),
  WishCategory('health', '健康', '会呼吸的翡翠', '比如：愿我睡得沉，醒得轻。',
      ['跟着它，慢慢吸气。', '再慢慢呼出去。', '身体听见了，它在变好。'], Color(0xFFBDF2CF), Color(0xFF2E9C68)),
  WishCategory('mood', '情绪', '月下静湖', '比如：愿我今晚心里安静下来。',
      ['让这一滴落下去。', '云在散开。', '湖面静了，你也是。'], Color(0xFFCFE6FF), Color(0xFF4C7FC0)),
  WishCategory('life', '生活', '万盏孔明灯', '比如：愿我有一个带院子的家。',
      ['点亮属于你的那一盏。', '它升起来了，还有很多盏陪着它。', '你想要的生活，正在路上。'], Color(0xFFFFD0A0), Color(0xFFE0752C)),
  WishCategory('pet', '宠物', '爪印星光', '比如：愿它健健康康，陪我很久。',
      ['有一串小脚印，朝你走来。', '它在天上也留了一个爪印。', '被你爱着，它什么都不怕。'], Color(0xFFFFD8B8), Color(0xFFD98A5A)),
];

class Wish {
  final WishCategory category;
  final String text;
  final DateTime at;
  const Wish(this.category, this.text, this.at);
}
