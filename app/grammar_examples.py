import re
from .grammar_theory import build_guide
from .segment import segment


ANCHORS = {
    "是字句": ("是",), "有字句": ("有",), "吗问句": ("吗",),
    "不和没": ("不", "没"), "的字短语": ("的",), "在和位置": ("在",),
    "想和要": ("想", "要"), "基本方位词": ("上", "下", "里", "外", "前", "后"),
    "会和能": ("会", "能"), "疑问代词": ("谁", "什么", "哪", "怎么", "多少"),
    "人称代词": ("我", "你", "他", "她", "我们", "他们"),
    "指示代词": ("这", "那"), "基本数字": ("一", "两", "三", "十", "百"),
    "基本量词": ("个", "本", "杯", "张"), "数量短语": ("个", "本", "杯", "张"),
    "程度副词": ("很", "非常", "太", "真", "最"), "都和一起": ("都", "一起"),
    "时间副词": ("马上", "先", "有时"), "常常和再": ("常常", "再"),
    "还和也": ("还", "也"), "别的命令": ("别",), "从到结构": ("从", "到"),
    "跟和作介词": ("跟", "和"), "和跟还是作连词": ("和", "跟", "还是"),
    "地字结构": ("地",), "动词后的了": ("了",), "句末语气词": ("吧", "吗", "呢"),
    "主语": ("我", "他", "她", "我们"), "谓语": ("是", "有", "在"),
    "宾语": ("喜欢", "学习", "买", "吃"), "定语": ("的",), "状语": ("在", "很", "常常"),
    "补语入门": ("完", "懂", "到", "得"), "主谓短语": ("很", "是", "有"),
    "动宾短语": ("看书", "吃饭", "学习", "工作"), "偏正短语": ("的", "很"),
    "联合短语": ("和", "跟"), "介词短语": ("在", "从", "跟"),
    "陈述句": ("是", "有", "在"), "祈使句": ("请", "别"), "感叹句": ("真", "太"),
    "特指问句": ("谁", "什么", "哪", "怎么"), "选择问句": ("还是",),
    "正反问句": ("不",), "状态变化了": ("了",), "进行体": ("正在", "在", "呢"),
    "钱数表达": ("块", "元", "钱"), "日期和时间": ("年", "月", "号", "点"),
    "了表示完成": ("了",), "正在进行": ("正在", "在", "呢"), "比字句": ("比",),
    "因为所以": ("因为", "所以"), "先再然后": ("先", "再", "然后"),
    "过的经验": ("过",), "方向后缀面边": ("面", "边"), "动词重叠": ("看看", "想想", "说说"),
    "形容词重叠": ("的",), "可能": ("可能",), "离合词": ("见面", "睡觉", "洗澡"),
    "自己": ("自己",), "这么那么": ("这么", "那么", "这样", "那样"),
    "万和概数": ("万", "多"), "扩展量词": ("条", "位", "间", "次"),
    "已经": ("已经",), "着表示持续": ("着",), "就": ("就",),
    "多问程度": ("多大", "多高", "多远", "多久"), "一点儿和有点儿": ("一点", "有点"),
    "是的强调句": ("是", "的"), "从和离": ("从", "离"), "但和但是": ("但", "但是"),
    "转折复句": ("虽然", "但是"), "让字兼语句": ("让",), "连动句": ("去", "来"),
    "的字短语作名词": ("的",), "什么的": ("什么的",), "即将发生": ("快要", "就要", "要"),
    "都已经了": ("都", "了"), "还是吧": ("还是", "吧"), "结果补语": ("完", "懂", "到", "见"),
    "趋向补语": ("进来", "出去", "回来", "上去", "下来"), "程度补语": ("得",),
    "时量补语": ("小时", "分钟", "年", "月"), "一样和没有": ("一样", "没有"),
    "把字句": ("把",), "被字句": ("被",), "虽然但是": ("虽然", "但是"),
    "越来越": ("越来越",), "一边一边": ("一边",), "除了以外": ("除了", "以外"),
}

REQUIRE_ALL = {"因为所以", "从到结构", "转折复句", "虽然但是", "一边一边", "除了以外"}

CURATED_EXAMPLE_SETS = {
    "的字短语": {
        "theory": [
            ("这是我的书。", "This is my book."),
            ("她是我妈妈。", "She is my mother."),
            ("那是老师的杯子。", "That is the teacher's cup."),
            ("这是红色的杯子。", "This is a red cup."),
            ("这是我朋友的猫。", "This is my friend's cat."),
        ],
        "practice": [
            ("这是你的书。", "This is your book."),
            ("那是他的手机。", "That is his phone."),
            ("她是我的姐姐。", "She is my older sister."),
            ("这是妈妈的茶。", "This is Mom's tea."),
            ("老师的杯子在桌上。", "The teacher's cup is on the table."),
            ("我的学校很大。", "My school is large."),
            ("她喜欢红色的衣服。", "She likes red clothes."),
            ("他是我哥哥的朋友。", "He is my older brother's friend."),
            ("这是中国的茶。", "This is Chinese tea."),
            ("那是妹妹的书包。", "That is my younger sister's schoolbag."),
            ("我们的老师很好。", "Our teacher is very nice."),
            ("这是一个很好的朋友。", "This is a very good friend."),
        ],
    },
    "不和没": {
        "theory": [
            ("我不喝咖啡。", "I do not drink coffee."),
            ("他昨天没来。", "He did not come yesterday."),
            ("她不喜欢茶。", "She does not like tea."),
            ("我没有妹妹。", "I do not have a younger sister."),
            ("我今天没吃饭。", "I did not eat today."),
        ],
        "practice": [
            ("我不喝茶。", "I do not drink tea."),
            ("他不吃米饭。", "He does not eat rice."),
            ("她今天不忙。", "She is not busy today."),
            ("我明天不去学校。", "I am not going to school tomorrow."),
            ("我们不看电视。", "We do not watch television."),
            ("他昨天没来。", "He did not come yesterday."),
            ("我没吃早饭。", "I did not eat breakfast."),
            ("她没有哥哥。", "She does not have an older brother."),
            ("我没有钱。", "I do not have money."),
            ("你昨天没上课。", "You did not attend class yesterday."),
            ("妈妈今天没上班。", "Mom did not work today."),
            ("他没喝咖啡。", "He did not drink coffee."),
        ],
    },
    "吗问句": {
        "theory": [
            ("你是老师吗？", "Are you a teacher?"),
            ("她今天来吗？", "Is she coming today?"),
            ("你好吗？", "Are you well?"),
            ("他是学生吗？", "Is he a student?"),
            ("你喝茶吗？", "Do you drink tea?"),
        ],
        "practice": [
            ("你是学生吗？", "Are you a student?"),
            ("他是医生吗？", "Is he a doctor?"),
            ("她是中国人吗？", "Is she Chinese?"),
            ("你吃米饭吗？", "Do you eat rice?"),
            ("你喜欢咖啡吗？", "Do you like coffee?"),
            ("她有妹妹吗？", "Does she have a younger sister?"),
            ("今天很冷吗？", "Is it cold today?"),
            ("这是你的书吗？", "Is this your book?"),
            ("明天有课吗？", "Is there class tomorrow?"),
            ("你们现在忙吗？", "Are you busy now?"),
            ("你的妈妈好吗？", "Is your mother well?"),
            ("你们国家的人吃米饭吗？", "Do people in your country eat rice?"),
        ],
    },
    "有字句": {
        "theory": [
            ("我有一个哥哥。", "I have an older brother."),
            ("桌上有一本书。", "There is a book on the table."),
            ("我家有三个人。", "There are three people in my family."),
            ("学校前面有一家商店。", "There is a shop in front of the school."),
            ("杯子里有水。", "There is water in the cup."),
        ],
        "practice": [
            ("我有两本书。", "I have two books."),
            ("她有一个妹妹。", "She has a younger sister."),
            ("你有时间吗？", "Do you have time?"),
            ("他没有钱。", "He does not have money."),
            ("我们家有一只猫。", "Our family has a cat."),
            ("桌子上有一杯茶。", "There is a cup of tea on the table."),
            ("教室里有很多学生。", "There are many students in the classroom."),
            ("公园里有很多树。", "There are many trees in the park."),
            ("书包里没有手机。", "There is no phone in the schoolbag."),
            ("今天有中文课。", "There is Chinese class today."),
            ("医院旁边有一个饭店。", "There is a restaurant beside the hospital."),
            ("这儿有地铁站吗？", "Is there a metro station here?"),
        ],
    },
}


def _clean_corpus(conn) -> list[dict]:
    bands = {}
    for item in conn.execute("SELECT headword,hsk_bands FROM item WHERE kind='word'"):
        levels = [int(value) for value in item["hsk_bands"].split(",") if value.isdigit()]
        if levels:
            bands[item["headword"]] = min(levels)
    lexicon = set(bands)
    seen = set()
    rows = []
    for row in conn.execute(
        "SELECT zh,en,source FROM sentence WHERE validated=1 AND TRIM(en)<>'' "
        "AND LENGTH(zh) BETWEEN 4 AND 28 "
        "AND source<>'generated practice carrier' ORDER BY id"
    ):
        zh = row["zh"].strip()
        if zh in seen:
            continue
        seen.add(zh)
        tokens = segment(zh, lexicon) if lexicon else []
        token_levels = [bands[token] for token in tokens if token in bands]
        unknown = sum(
            1 for token in tokens
            if re.search(r"[\u3400-\u9fff]", token) and token not in bands
        )
        rows.append({
            "zh": zh, "en": row["en"].strip(), "source": row["source"],
            "_vocab_level": max(token_levels, default=1), "_unknown": unknown,
        })
    return rows


def _matches(title: str, zh: str) -> bool:
    anchors = ANCHORS.get(title, ())
    if not anchors:
        return True
    if title in REQUIRE_ALL:
        return all(anchor in zh for anchor in anchors[:2])
    return any(anchor in zh for anchor in anchors)


def build_example_sets(conn, point: dict, base_examples: list[dict],
                       corpus: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
    """Create separate, deterministic theory and practice pools from bundled content."""
    curated = CURATED_EXAMPLE_SETS.get(point["title_zh"])
    if curated:
        return tuple(
            [
                {"zh": zh, "en": en, "source": "authored and reviewed"}
                for zh, en in curated[name]
            ]
            for name in ("theory", "practice")
        )
    corpus = corpus if corpus is not None else _clean_corpus(conn)
    guide = build_guide(point)
    theory = [{"zh": row["zh"], "en": row["en"], "source": "authored"}
              for row in base_examples]
    for zh, en in guide["extra_examples"]:
        if not any(row["zh"] == zh for row in theory):
            theory.append({"zh": zh, "en": en, "source": "authored"})

    def candidate_key(row):
        return (
            max(0, row.get("_vocab_level", 1) - point["level"]),
            row.get("_unknown", 0),
            abs(len(row["zh"]) - 11),
            len(row["zh"]),
            row["zh"],
        )

    matching = [row for row in corpus if _matches(point["title_zh"], row["zh"])]
    matching.sort(key=candidate_key)
    fallback = sorted((row for row in corpus if row not in matching), key=candidate_key)
    theory_candidates = matching + [
        row for row in fallback
    ]
    for row in theory_candidates:
        if len(theory) >= 5:
            break
        if not any(item["zh"] == row["zh"] for item in theory):
            theory.append({key: row[key] for key in ("zh", "en", "source")})

    theory_zh = {row["zh"] for row in theory}
    practice = [
        {key: row[key] for key in ("zh", "en", "source")}
        for row in matching if row["zh"] not in theory_zh
    ]
    if len(practice) < 10:
        practice_zh = {row["zh"] for row in practice}
        practice.extend(
            {key: row[key] for key in ("zh", "en", "source")} for row in fallback
            if row["zh"] not in theory_zh and row["zh"] not in practice_zh
        )
    practice = practice[:20]

    # Tiny test databases may not include the bundled sentence corpus. Keep the
    # application usable there while the real bootstrap always produces 10+.
    if not practice:
        practice = [{"zh": row["zh"], "en": row["en"], "source": "authored"}
                    for row in base_examples]
    return theory, practice


def corpus_for_seed(conn) -> list[dict]:
    return _clean_corpus(conn)
