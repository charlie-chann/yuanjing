"""接大模型（OpenAI 兼容接口）。没配置或出错时返回 None，调用方退回模板。

所有提示词都带同一段安全约束：只写正向、温和的内容，不诊断、不评判第三方、不承诺结果、
不给医疗和投资建议。模型的输出还会再过一遍内容把关，不合格就丢掉用模板。
"""
import json
import logging

import httpx

from ..config import settings
from ..moderation import check_public, needs_support

log = logging.getLogger("yuanjing.llm")

GUARD = (
    "你是显化疗愈应用「愿境」里的写作助手。只用简体中文，语气温柔、具体、真诚，不要鸡汤腔。"
    "只写正向的内容；不做医疗或心理诊断；不评判、不指责任何第三方；不承诺一定会实现；"
    "不给投资、医疗、法律建议；不出现联系方式和网址。"
)


def complete(task: str, user: str, max_tokens: int = 400, as_json: bool = False) -> str | dict | None:
    if not settings.llm_enabled:
        return None
    body = {
        "model": settings.llm_model,
        "messages": [{"role": "system", "content": GUARD + task}, {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": 0.9,
    }
    if as_json:
        body["response_format"] = {"type": "json_object"}
    try:
        r = httpx.post(
            settings.llm_base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json=body,
            timeout=settings.llm_timeout,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:  # 网络、额度、格式问题都退回模板
        log.warning("大模型调用失败，改用模板：%s", e)
        return None
    if as_json:
        try:
            data = json.loads(text)
        except ValueError:
            return None
        flat = json.dumps(data, ensure_ascii=False)
        return None if check_public(flat) or needs_support(flat) else data
    return None if check_public(text) or needs_support(text) else text
