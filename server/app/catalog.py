"""规则和商品。应用里也有一份用来显示，但以这里为准：价格、上限、会员限定都在服务端校验。"""

# 正向行为的金币奖励：(每次多少, 每天最多几次, 流水里写什么)
COIN_RULES: dict[str, tuple[int, int, str]] = {
    "checkin": (10, 1, "每日签到"),
    "wish": (5, 1, "完成今日许愿"),
    "post": (5, 1, "发布朋友圈"),
    "diary": (5, 1, "写感恩日记"),
    "friend": (2, 5, "添加好友"),
    "like": (1, 10, "给别人点赞"),
    "praise": (2, 5, "给别人夸夸"),
    "liked": (2, 10, "被点赞"),
    "praised": (2, 10, "被夸夸"),
    "sanctuary": (3, 1, "在湖心小寺留下心意"),
}

# 连续签到每多一天多给几个，最多多给几个
STREAK_STEP = 2
STREAK_CAP = 10

# 商品：id → (名字, 价格, 分组, 会员限定)。分组 frame 的同时只能戴一个
SHOP_ITEMS: dict[str, tuple[str, int, str, bool]] = {
    "wall_stars": ("墙上的星星", 60, "room", False),
    "balloons": ("一束气球", 80, "room", False),
    "moon_lamp": ("月亮灯", 120, "room", False),
    "frame_gold": ("鎏金头像框", 50, "frame", False),
    "frame_star": ("星彩头像框", 50, "frame", False),
    "pet_bowl": ("小食盆", 30, "pet", False),
    "pet_ball": ("小皮球", 30, "pet", False),
    "pet_bed": ("云朵软垫窝", 0, "pet", True),
    # 用金币解锁的冥想（会员不用解锁）
    "med_clear": ("冥想「潜意识清理」", 30, "meditation", False),
    # ── 小动物的礼物：不卖。来路写在下面的 KEEPSAKES 里。都是头像框，和别的头像框一样同时只能戴一个 ──
    "frame_teddy": ("栗子的爪印头像框", 0, "frame", False),
    "frame_shiba": ("年糕的树枝头像框", 0, "frame", False),
    "frame_cotton": ("棉花的云朵头像框", 0, "frame", False),
    "frame_tangerine": ("橘子同款小鱼头像框", 0, "frame", False),
    "frame_tangyuan": ("汤圆的蓝眼睛头像框", 0, "frame", False),
    "frame_huajuan": ("花卷的三花头像框", 0, "frame", False),
    "frame_zhima": ("芝麻的骨头头像框", 0, "frame", False),
    "frame_tuanzi": ("团子的铃铛头像框", 0, "frame", False),
    "frame_momo": ("墨墨的月夜头像框", 0, "frame", False),
    "frame_doubao": ("豆包的毛线球头像框", 0, "frame", False),
    "frame_shell": ("贝壳风铃头像框", 0, "frame", False),
    "frame_autumn": ("秋叶标本头像框", 0, "frame", False),
    "frame_meadow": ("野花草环头像框", 0, "frame", False),
    "frame_pearl": ("珍珠平安扣头像框", 0, "frame", False),
}

# 小动物的礼物从哪儿来。两种：
# - {"pet": 动物编号}：这只动物的专属物品，和它的亲密度到 KEEPSAKE_AT 时它送给你（见 routers/pets.py 的里程碑）
# - {"cost": {收藏品编号: 几个}}：用收藏品在商城兑换（POST /shop/redeem）
KEEPSAKE_AT = 50
KEEPSAKES: dict[str, dict] = {
    "frame_teddy": {"pet": "teddy"},
    "frame_shiba": {"pet": "shiba"},
    "frame_cotton": {"pet": "cotton"},
    "frame_tangerine": {"pet": "tangerine"},
    "frame_tangyuan": {"pet": "tangyuan"},
    "frame_huajuan": {"pet": "huajuan"},
    "frame_zhima": {"pet": "zhima"},
    "frame_tuanzi": {"pet": "tuanzi"},
    "frame_momo": {"pet": "momo"},
    "frame_doubao": {"pet": "doubao"},
    "frame_shell": {"cost": {"shell": 5, "shell_conch": 2}},
    "frame_autumn": {"cost": {"maple": 3, "ginkgo": 3}},
    "frame_meadow": {"cost": {"flower": 4, "clover": 2, "feather": 2}},
    "frame_pearl": {"cost": {"pearl": 1, "knot": 1}},
}

SKINS = {"gold": False, "dream": False, "witch": True, "angel": True, "mermaid": True}
SCENES = ("wealth", "career", "looks", "health", "mood", "life", "pet")
POST_TYPES = ("moment", "diary", "wish")
LOOK_MODES = ("q", "anime", "real", "self")

# 夸夸只能从这些里选（没有自由评论，避免负能量）
PRAISE_PRESETS = ("你真的在发光", "替你开心", "会实现的", "你值得这一切", "抱抱，你很棒", "被你治愈了")

# 一条动态被几个人举报后自动下架，等人工复核
REPORT_HIDE_AT = 3
