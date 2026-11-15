"""示例用户和示例动态：冷启动时广场不是空的。只在库里还没有示例用户时写入一次。"""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Post, Praise, User, now

USERS = [
    ("晚风里的橘子", "慢慢来，比较快。", "把日子过成喜欢样子的人"),
    ("小满", "今天也要好好吃饭。", "被身体好好爱着的人"),
    ("云朵贩卖机", "收集每一朵好看的云。", "心里有一片静湖的人"),
    ("阿宁", "我正在成为自己喜欢的大人。", "走在自己节奏里的人"),
    ("栗子和豆包", "两只猫的铲屎官。", "被毛孩子选中的人"),
    ("一颗小行星", "宇宙那么大，总有一颗星为我亮。", "由内而外发光的人"),
    ("周末看海", "存钱，看海，爱自己。", "从容的丰盛者"),
    ("麦子", "把每一天当礼物拆开。", "把日子过成喜欢样子的人"),
]

# (第几个用户, 类型, 内容, 几分钟前, 夸夸)
POSTS = [
    (0, "moment", "下班路上的晚霞是粉橘色的，站在天桥上看了五分钟。原来不赶时间的时候，城市这么好看。", 12, ["被你治愈了"]),
    (1, "diary", "今天想谢谢三件事：\n一，早上那碗热乎乎的小米粥。\n二，同事帮我带了一把伞。\n三，身体没有闹脾气，陪我把今天走完了。", 47, ["会感恩的人，日子会越过越亮。"]),
    (3, "wish", "许愿：三个月后，我能在评审会上从容地讲完自己的方案。", 65, ["会实现的", "替你开心"]),
    (2, "moment", "今天做了十分钟冥想。脑子里的弹幕慢慢少了，像湖面静下来。", 98, []),
    (4, "moment", "豆包今天学会了握手，栗子在旁边一脸不屑。被两只毛孩子包围的周末，什么都不缺。", 130, ["被你治愈了"]),
    (5, "wish", "许愿：喜欢镜子里的自己，不是变成谁，是本来的样子在发光。", 185, ["你真的在发光"]),
    (6, "diary", "发工资了，先给自己存了一笔「看海基金」。谢谢一直努力的自己，也谢谢钱愿意来找我。", 240, []),
    (7, "moment", "把拖了半个月的体检做了。结果都好。走出医院的时候阳光特别亮。", 310, ["你值得这一切"]),
    (0, "diary", "今天想谢谢：楼下开了的那棵桂花树，一封回得很认真的邮件，还有终于睡了个整觉的我。", 420, []),
    (3, "moment", "被夸「你最近状态真好」。偷偷开心了一整天。原来认真许过的愿，会从别人嘴里先听到回音。", 560, ["你真的在发光"]),
    (2, "wish", "许愿：心里常常安静，遇到风浪也稳得住。", 720, []),
    (5, "moment", "今天没化妆出门，素着脸去买了一束花。花店老板说「你笑起来很好看」。", 900, ["抱抱，你很棒"]),
]


def seed(db: Session) -> None:
    if db.scalar(select(User.id).where(User.is_bot.is_(True)).limit(1)) is not None:
        return
    users = [User(name=n, sign=s, title=t, is_bot=True, coins=0) for n, s, t in USERS]
    db.add_all(users)
    db.flush()
    t0 = now()
    # 按时间从旧到新插入，id 越大越新，广场按 id 倒序就是按时间倒序
    for ui, kind, text, ago, praises in sorted(POSTS, key=lambda p: -p[3]):
        p = Post(user_id=users[ui].id, type=kind, text=text, public=True, created_at=t0 - timedelta(minutes=ago))
        db.add(p)
        db.flush()
        for i, line in enumerate(praises):
            # 示例夸夸来自别的示例用户
            db.add(Praise(post_id=p.id, from_user_id=users[(ui + i + 1) % len(users)].id, text=line))
    db.commit()
