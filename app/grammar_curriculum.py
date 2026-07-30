"""Curriculum-order metadata and lightweight grammar dependency detection."""

from __future__ import annotations

import re


# These lessons unlock a large share of ordinary beginner sentences. The badge
# is guidance, not a prerequisite gate and does not change the learner's status.
RECOMMENDED_EARLY = frozenset({
    "是字句",
    "有字句",
    "吗问句",
    "不和没",
    "的字短语",
    "在和位置",
    "想和要",
    "基本方位词",
    "会和能",
    "疑问代词",
    "基本量词",
    "动词后的了",
    "进行体",
    "了表示完成",
    "正在进行",
    "比字句",
    "因为所以",
    "过的经验",
    "的字短语作名词",
    "结果补语",
})


# The rules intentionally focus on structures that can materially raise the
# difficulty of a sentence. They are not intended to parse all Chinese.
DEPENDENCY_RULES = (
    ("把字句", re.compile(r"把")),
    ("被字句", re.compile(r"被")),
    ("越来越", re.compile(r"越来越")),
    ("一边一边", re.compile(r"一边[^。！？?]{0,24}一边")),
    ("除了以外", re.compile(r"除了[^。！？?]{0,24}(?:以)?外")),
    ("转折复句", re.compile(r"虽然")),
    ("进行体", re.compile(r"正在|正[^，。！？?]{1,12}呢")),
    ("比字句", re.compile(r"比")),
    ("因为所以", re.compile(r"因为|所以")),
    ("先再然后", re.compile(r"先[^。！？?]{0,24}(?:再|然后)")),
    (
        "过的经验",
        re.compile(
            r"(?:去|来|吃|喝|看|听|见|学|做|说|买|用|读|玩|坐|开|住|想)"
            r"过"
        ),
    ),
    ("可能", re.compile(r"可能")),
    ("自己", re.compile(r"自己")),
    ("这么那么", re.compile(r"这么|那么|这样|那样")),
    ("已经", re.compile(r"已经")),
    (
        "着表示持续",
        re.compile(r"(?:开|关|穿|拿|坐|站|躺|放|挂|写|看|听|等)着"),
    ),
    (
        "是的强调句",
        re.compile(
            r"是[^，。！？?]{0,18}"
            r"(?:来|去|到|做|买|找|学|认识|坐|跟|在|用|写|说|看)"
            r"[^，。！？?]{0,12}的(?:吗|呢)?[。！？?]?$"
        ),
    ),
    ("从和离", re.compile(r"(?:^|[，。！？?\s])[^，。！？?]{0,12}离[^，。！？?]")),
    ("但和但是", re.compile(r"但是|但")),
    ("让字兼语句", re.compile(r"让[^，。！？?]{1,16}(?:去|来|做|看|说|读|写|吃|喝)")),
    ("什么的", re.compile(r"什么的")),
    ("即将发生", re.compile(r"快要|就要")),
    (
        "都已经了",
        re.compile(
            r"都(?:已经|[一二两三四五六七八九十\d]+"
            r"(?:点|岁|天|年|个月|小时))[^，。！？?]{0,8}了"
        ),
    ),
    ("还是吧", re.compile(r"还是[^，。！？?]{1,16}吧")),
    (
        "补语入门",
        re.compile(
            r"(?:看|吃|听|写|做|买|找|学|说|读|喝|关|洗)"
            r"(?:完|好|懂|到|见|错)"
            r"|(?:走|跑|拿|带)(?:进|出|回|上|下)(?:来|去)"
            r"|(?:进|出|上|下)(?:来|去)"
        ),
    ),
    (
        "程度补语",
        re.compile(r"(?:说|写|做|唱|跑|走|睡|学|吃|开|画)得[^，。！？?]{1,12}"),
    ),
    (
        "时量补语",
        re.compile(
            r"(?:学|住|工作|等|睡|看|玩|走)(?:了)?"
            r"[一二两三四五六七八九十\d]+(?:个)?(?:小时|分钟|年|月|天)"
        ),
    ),
    ("一样和没有", re.compile(r"(?:跟|和)[^，。！？?]{1,12}一样")),
)

LESSON_DEPENDENCY_EXCEPTIONS = {
    # 到 is the endpoint marker being taught here, even when it follows a verb.
    "从到结构": frozenset({"补语入门"}),
}


def grammar_dependencies(zh: str) -> tuple[str, ...]:
    """Return the earliest curriculum lessons required by obvious structures."""
    return tuple(
        title for title, pattern in DEPENDENCY_RULES if pattern.search(zh)
    )


def future_dependencies(
    zh: str,
    point: dict,
    curriculum_order: dict[str, tuple[int, int]],
) -> tuple[str, ...]:
    """Return detected requirements introduced after the current lesson."""
    current = (
        int(point["level"]),
        int(point.get("lesson_number", 10_000)),
    )
    future = []
    exceptions = LESSON_DEPENDENCY_EXCEPTIONS.get(
        point["title_zh"], frozenset()
    )
    for title in grammar_dependencies(zh):
        required = curriculum_order.get(title)
        if (
            required
            and required > current
            and title != point["title_zh"]
            and title not in exceptions
        ):
            future.append(title)
    return tuple(future)
