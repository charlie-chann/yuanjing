"""需求里写「AI 生成」的内容。配了大模型就用大模型，没配或出错就用模板；返回里 source 说明用的是哪个。"""
import re
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai import llm, templates
from ..auth import current_user
from ..catalog import SCENES
from ..db import get_db
from ..models import Destiny, User, VisionItem, Wish
from ..moderation import needs_support

router = APIRouter(prefix="/ai")


def _wishes(db: Session, me: User, limit: int = 200) -> list[tuple[str, str]]:
    return [(w.scene, w.text) for w in db.scalars(select(Wish).where(Wish.user_id == me.id).order_by(Wish.id.desc()).limit(limit))]


@router.get("/analysis")
def analysis(me: User = Depends(current_user), db: Session = Depends(get_db)):
    wishes = _wishes(db, me)
    report = templates.analyze(wishes)
    if report is None:
        return {"report": None}
    source = "template"
    text = "\n".join(f"[{templates.SCENE_NAMES[s]}] {t}" for s, t in wishes[:40])
    data = llm.complete(
        "根据用户最近的心愿，用 JSON 返回：need（他真正想要的，10 个字以内），advice（一句温和的建议，50 字以内），"
        "trend（一句话概括目标倾向，40 字以内）。",
        text,
        as_json=True,
    )
    if isinstance(data, dict) and all(isinstance(data.get(k), str) and data[k] for k in ("need", "advice", "trend")):
        report.update({k: data[k][:80] for k in ("need", "advice", "trend")})
        source = "llm"
    # 执念点（反复提到的词）和更细的建议是会员权益
    if not me.member:
        report["advice"] = None
        report["repeats"] = []
    return {"report": report, "source": source}


@router.post("/moment")
def moment(me: User = Depends(current_user), db: Session = Depends(get_db)):
    wishes = _wishes(db, me, 5)
    line = llm.complete(
        "替用户写一条朋友圈，分享一件今天的小确幸或对心愿的感悟，40 到 80 字，第一人称，不要话题标签和表情。",
        "用户最近的心愿：" + ("；".join(t for _, t in wishes) or "（还没有）"),
        max_tokens=200,
    )
    if isinstance(line, str):
        return {"text": line, "source": "llm"}
    return {"text": templates.moment(wishes[0][0] if wishes else None), "source": "template"}


@router.post("/diary")
def diary(me: User = Depends(current_user)):
    line = llm.complete("替用户写一篇感恩日记：「今天想谢谢三件事」，三件具体的日常小事，最后一句收尾，总共 120 字以内。", "写一篇", max_tokens=300)
    if isinstance(line, str):
        return {"text": line, "source": "llm"}
    return {"text": templates.diary(), "source": "template"}


class AffirmIn(BaseModel):
    scenes: list[str] = []


@router.post("/affirmations")
def affirmations(body: AffirmIn, me: User = Depends(current_user), db: Session = Depends(get_db)):
    """会员权益：根据心愿、愿景板和终点密码写肯定语。"""
    if not me.member:
        raise HTTPException(403, "AI 生成肯定语是会员权益")
    scenes = [s for s in body.scenes if s in SCENES]
    destiny = {d.scene: d.text for d in db.scalars(select(Destiny).where(Destiny.user_id == me.id))}
    vision = db.scalars(select(VisionItem).where(VisionItem.user_id == me.id)).all()
    wishes = _wishes(db, me, 12)
    use = scenes or list({*destiny, *(s for s, _ in wishes), *(v.scene for v in vision)})
    material = "\n".join(
        [f"方面：{'、'.join(templates.SCENE_NAMES[s] for s in use if s in templates.SCENE_NAMES) or '情绪、生活'}"]
        + [f"终点密码·{templates.SCENE_NAMES[s]}：{t}" for s, t in destiny.items() if s in use]
        + [f"愿景板：{v.text}" for v in vision if v.text and v.scene in use]
        + [f"心愿：{t}" for s, t in wishes if s in use]
    )
    data = llm.complete(
        "根据材料写 5 到 7 句肯定语，用 JSON 返回 {\"lines\": [...]}。每句以「我」开头，现在时，15 字左右，具体、可信，最后一句是「我已经走在路上了。」",
        material,
        max_tokens=400,
        as_json=True,
    )
    if isinstance(data, dict) and isinstance(data.get("lines"), list) and 3 <= len(data["lines"]) <= 10:
        return {"lines": [str(x)[:40] for x in data["lines"]], "source": "llm"}
    return {"lines": templates.affirmations(use, destiny, len(scenes) == 1), "source": "template"}


@router.get("/destiny/{scene}")
def destiny_draft(scene: str, me: User = Depends(current_user), db: Session = Depends(get_db)):
    """把这一类的心愿和愿景板关键词整理成终点密码的一段话"""
    if scene not in SCENES:
        raise HTTPException(400, "没有这个分类")
    wishes = [t for s, t in _wishes(db, me, 50) if s == scene]
    keys = [v.text for v in db.scalars(select(VisionItem).where(VisionItem.user_id == me.id, VisionItem.scene == scene)) if v.text]
    if not wishes and not keys:
        return {"text": None}
    line = llm.complete(
        f"把用户在「{templates.SCENE_NAMES[scene]}」方面的心愿和愿景，整理成一段第一人称、现在时的终极理想状态描述，60 到 120 字。",
        "\n".join([*wishes[:10], *keys[:10]]),
        max_tokens=300,
    )
    if isinstance(line, str):
        return {"text": line, "source": "llm"}
    return {"text": templates.destiny_draft(wishes, keys), "source": "template"}


class ReadingIn(BaseModel):
    text: str = Field(default="", max_length=500)
    tags: list[str] = []


STICKING_KEYS = ("wronged", "anger", "anxiety", "inferior", "failure", "judged", "relation", "overload")


@router.post("/reading")
def reading(body: ReadingIn, me: User = Depends(current_user)):
    """卡点解读。只在配了大模型时有用：选出最接近的卡点，再针对用户写的话写共情和深层信念。
    释放引导和肯定语仍用应用里写好的那套（它们有预先录好的语音）。没配大模型返回 source=none，应用用本地规则。"""
    if needs_support(body.text):
        return {"support": True}
    data = llm.complete(
        "用户写下了此刻的情绪卡点。用 JSON 返回：key（从 wronged 委屈、anger 愤怒、anxiety 焦虑、inferior 自卑、failure 担心失败、"
        "judged 害怕被评价、relation 关系受伤、overload 压力过载 里选最接近的一个），emotions（2 到 3 个表层情绪词的数组），"
        "empathy（针对他写的具体事情的共情，60 字以内，不评判任何人），belief（「困住你的是这句话：……」，点出深层的限制性信念，50 字以内），"
        "deep（情绪是否强烈，布尔值）。",
        f"标签：{'、'.join(body.tags) or '无'}\n内容：{body.text or '（没写）'}",
        max_tokens=400,
        as_json=True,
    )
    if (
        isinstance(data, dict)
        and data.get("key") in STICKING_KEYS
        and isinstance(data.get("empathy"), str)
        and isinstance(data.get("belief"), str)
        and isinstance(data.get("emotions"), list)
    ):
        return {
            "key": data["key"],
            "emotions": [str(e)[:6] for e in data["emotions"][:3]],
            "empathy": data["empathy"][:120],
            "belief": data["belief"][:100],
            "deep": bool(data.get("deep")),
            "source": "llm",
        }
    return {"source": "none"}
