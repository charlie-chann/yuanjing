"""内容把关：广场上只放正向的内容。

现在是关键词，命中就不让公开发（仍可设为仅自己可见）。上线前要换成内容安全服务
（各云厂商都有文本审核接口），关键词留作兜底。
"""
import re

NEGATIVE = ("去死", "垃圾", "废物", "恶心", "讨厌你", "滚", "诅咒", "报复", "活该", "傻逼", "贱", "脑残", "弱智")
# 联系方式和导流：没有私信，也不让在公开内容里留
CONTACT = re.compile(r"(微信|vx|v信|加我|qq|QQ|电话|手机号|\d{7,})")
CRISIS = ("不想活", "想死", "自杀", "轻生", "结束生命", "活不下去", "伤害自己", "自残", "了结")


def check_public(text: str) -> str | None:
    """能公开发就返回 None，否则返回给用户看的原因。"""
    if any(w in text for w in NEGATIVE):
        return "广场上只放正向的话，改一改再发，或者设为仅自己可见"
    if CONTACT.search(text):
        return "广场上不能留联系方式"
    return None


def needs_support(text: str) -> bool:
    return any(w in text for w in CRISIS)
