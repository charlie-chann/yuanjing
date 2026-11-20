"""湖心小寺里能拿在手上的东西：鱼、口粮、小动物叼来的收藏品，以及背包的增减。

三类东西都放在同一张 inventory 表里，按编号区分：
- 鱼（kind=fish）：钓上来的。能喂小动物，也能卖。水草也算在这里，但喂不了、卖不出钱。
- 口粮（kind=food）：商城「小寺」分组里用金币买的，编号都以 food_ 开头。
- 收藏品（kind=gift）：小动物每天叼来的、里程碑送的。不能喂，能卖，也能在商城换成头像框。

规则数字都在这个文件开头，好改。钓鱼的权重在 routers/fishing.py，最爱和里程碑在 routers/pets.py。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Inventory, User

RARITIES = ("common", "uncommon", "rare", "legend")
RARITY_NAMES = {"junk": "杂物", "common": "常见", "uncommon": "少见", "rare": "稀有", "legend": "传说"}

# 喂一条鱼涨多少亲密度（按稀有度）
FEED_BY_RARITY = {"common": 2, "uncommon": 3, "rare": 5, "legend": 8}

# 鱼：编号 → (名字, 稀有度, 一句描述, 卖多少金币, 最短厘米, 最长厘米)。编号是固定的，三维模型按它做
FISH: dict[str, tuple[str, str, str, int, float, float]] = {
    # 池塘
    "crucian": ("鲫鱼", "common", "池塘里最常见的，银灰的背，贪嘴。", 1, 8, 22),
    "loach": ("泥鳅", "common", "滑溜溜的，一不留神就从手里钻走。", 1, 6, 15),
    "goldfish": ("小金鱼", "uncommon", "不知道是谁放生的，红得像一小团火。", 3, 4, 10),
    "shrimp": ("青虾", "uncommon", "透明的身子，两根长须，倒着游。", 3, 3, 8),
    # 湖
    "whitebait": ("白条", "common", "湖面上一闪一闪的就是它，成群结队。", 1, 8, 18),
    "silver": ("银鱼", "uncommon", "细细的，近乎透明，清晨贴着水面游。", 3, 5, 12),
    "bass": ("鲈鱼", "uncommon", "大嘴，背上一排硬刺，劲儿不小。", 4, 20, 55),
    "mandarin": ("鳜鱼", "rare", "一身褐色的花斑。桃花流水鳜鱼肥。", 8, 22, 50),
    "crab": ("大闸蟹", "rare", "青背白肚，金爪黄毛，天黑了才爬出来。", 10, 6, 11),
    "carp_gold": ("金鳞鲤", "legend", "下雨时才浮上来，鳞片像一枚枚小金币。", 30, 40, 90),
    "moon": ("月光鱼", "legend", "只在晴朗的夜里出现，身上带着淡淡的光。", 30, 15, 35),
}
# 钓空了：一团水草。进背包，但不进图鉴、不能喂
WEED = "weed"
WEED_INFO = ("一团水草", "junk", "钩子挂上来的，湿漉漉一团。小动物不吃这个。", 0)

# 口粮：编号 → (名字, 一句描述, 买一个多少金币, 喂一次涨多少亲密度)
FOODS: dict[str, tuple[str, str, int, int]] = {
    "food_kibble": ("小饼干", "烤得脆脆的，谁都不挑。", 2, 2),
    "food_dried_fish": ("小鱼干", "晒得干干的，猫闻到就走不动。", 5, 3),
    "food_bone": ("肉骨头", "还带着一点肉，狗能啃一下午。", 5, 3),
    "food_cream": ("猫条", "挤出来一点点舔着吃，最金贵的零嘴。", 8, 4),
}
FOOD_SELL_RATE = 0.5       # 口粮卖回去只值买价的一半（向下取整）
STACK_MAX = 999            # 一样东西最多攒多少个

# 收藏品：编号 → (名字, 稀有度, 一句描述, 卖多少金币, 「一枚贝壳」这样的说法)。编号固定，三维模型按它做
KEEPS: dict[str, tuple[str, str, str, int, str]] = {
    "shell": ("贝壳", "common", "湖滩上捡的，里面一层淡淡的珠光。", 2, "一枚贝壳"),
    "shell_conch": ("海螺", "uncommon", "贴在耳边，能听见很远的水声。", 5, "一只海螺"),
    "pebble": ("彩色鹅卵石", "common", "被水磨得圆圆的，带一圈一圈的花纹。", 2, "一颗彩色的鹅卵石"),
    "clover": ("四叶草", "uncommon", "它在草地里找了很久才找到的。", 5, "一片四叶草"),
    "pinecone": ("松果", "common", "松树下滚来的，鳞片张得开开的。", 2, "一颗松果"),
    "ginkgo": ("银杏叶", "common", "小扇子一样，金黄金黄。", 2, "一片银杏叶"),
    "maple": ("枫叶", "common", "红透了的一片，叶柄上还有牙印。", 2, "一片枫叶"),
    "flower": ("小野花", "common", "连着一小截茎，是它小心叼来的。", 2, "一朵小野花"),
    "feather": ("羽毛", "common", "不知道是哪只小鸟落下的。", 2, "一根羽毛"),
    "bell": ("小铃铛", "uncommon", "摇一摇还响。也许是谁的项圈上掉的。", 5, "一只小铃铛"),
    "yarn": ("毛线球", "uncommon", "被玩得毛毛的，线头拖得老长。", 5, "一团毛线球"),
    "bone": ("骨头", "common", "它藏了很久的宝贝，现在归你了。", 2, "一根骨头"),
    "stick": ("树枝", "common", "一根很直、很好的树枝。", 2, "一根树枝"),
    "dried_fish": ("小鱼干", "common", "它自己舍不得吃，留给你的。", 2, "一条小鱼干"),
    "pearl": ("珍珠", "rare", "圆润的一粒，在暗处也发亮。", 15, "一粒珍珠"),
    "knot": ("平安结", "rare", "红绳编的，不知道它从哪儿找来的。愿你平安。", 15, "一枚平安结"),
}


def kind_of(item_id: str) -> str | None:
    if item_id in FISH or item_id == WEED:
        return "fish"
    if item_id in FOODS:
        return "food"
    if item_id in KEEPS:
        return "gift"
    return None


def name_of(item_id: str) -> str:
    return item_info(item_id)["name"]


def feed_gain(item_id: str) -> int:
    """喂这样东西基础涨多少亲密度；0 表示不能喂"""
    if item_id in FISH:
        return FEED_BY_RARITY[FISH[item_id][1]]
    if item_id in FOODS:
        return FOODS[item_id][3]
    return 0


def item_info(item_id: str) -> dict:
    """一样东西给界面看的样子（不含数量）。feed 是喂它基础涨多少亲密度，0 表示不能喂"""
    if item_id in FISH:
        name, rarity, about, sell = FISH[item_id][:4]
    elif item_id == WEED:
        name, rarity, about, sell = WEED_INFO
    elif item_id in FOODS:
        name, about, price, _ = FOODS[item_id]
        rarity, sell = "common", int(price * FOOD_SELL_RATE)
    elif item_id in KEEPS:
        name, rarity, about, sell = KEEPS[item_id][:4]
    else:
        raise KeyError(item_id)
    return {"id": item_id, "kind": kind_of(item_id), "name": name, "about": about, "rarity": rarity, "sell": sell, "feed": feed_gain(item_id)}


# ───────── 背包 ─────────
def have(db: Session, user: User, item_id: str) -> int:
    row = db.get(Inventory, (user.id, item_id))
    return row.count if row else 0


def give(db: Session, user: User, item_id: str, count: int = 1) -> int:
    """放进背包，返回现在有几个。不提交事务，由调用方提交"""
    row = db.get(Inventory, (user.id, item_id))
    if row is None:
        row = Inventory(user_id=user.id, item_id=item_id, count=0)
        db.add(row)
        db.flush()  # 会话不自动 flush：不先写进去，同一个请求里再放一次会查不到这一行
    row.count = min(row.count + count, STACK_MAX)
    return row.count


def take(db: Session, user: User, item_id: str, count: int = 1) -> bool:
    """从背包里拿走，不够返回 False（什么都不动）。不提交事务"""
    row = db.get(Inventory, (user.id, item_id))
    if row is None or row.count < count:
        return False
    row.count -= count
    if row.count == 0:
        db.delete(row)
        db.flush()
    return True


_ORDER = {k: i for i, k in enumerate([*FISH, WEED, *FOODS, *KEEPS])}


def bag_view(db: Session, user: User) -> list[dict]:
    db.flush()
    rows = db.scalars(select(Inventory).where(Inventory.user_id == user.id, Inventory.count > 0)).all()
    rows = [r for r in rows if r.item_id in _ORDER]
    rows.sort(key=lambda r: _ORDER[r.item_id])
    return [{**item_info(r.item_id), "count": r.count} for r in rows]
