"""Original, structured lesson guidance for the grammar reference pages."""

ASPECT_TITLES = {
    "动词后的了", "状态变化了", "了表示完成", "正在进行", "进行体",
    "过的经验", "着表示持续", "已经", "即将发生", "都已经了",
}
COMPLEMENT_TITLES = {"补语入门", "结果补语", "趋向补语", "程度补语", "时量补语"}
COMPARISON_TITLES = {"比字句", "一样和没有", "一点儿和有点儿", "多问程度"}
QUESTION_TITLES = {"吗问句", "疑问代词", "特指问句", "选择问句", "正反问句"}
NOUN_PHRASE_TITLES = {
    "的字短语", "定语", "偏正短语", "的字短语作名词", "基本量词",
    "数量短语", "扩展量词",
}


GUIDES = {
    "的字短语作名词": {
        "intro": (
            "Chinese puts the entire description before the noun it describes. "
            "That description can be a single word, a verb phrase, or a complete mini-clause. "
            "的 marks the end of the description so the listener can identify the head noun.",
            "If the head noun is already obvious, it can be omitted. The phrase ending in 的 then "
            "means “the one,” “the person,” or “the thing” described by the earlier phrase.",
        ),
        "structures": (
            {
                "label": "Keep the noun",
                "pattern": "phrase + 的 + noun",
                "body": "Use this when the noun is new, important, or not recoverable from context. "
                        "The phrase before 的 answers “which noun?”",
            },
            {
                "label": "Omit a known noun",
                "pattern": "phrase + 的",
                "body": "Drop the noun only after the conversation has made it clear. The same form "
                        "can refer to a person or a thing, so context supplies the missing category.",
            },
        ),
        "notes": (
            "The phrase before 的 keeps normal Chinese word order: subject, then verb, then object.",
            "This pattern does not itself show past, present, or future. Time words and context do that work.",
            "Long English relative clauses move before the noun in Chinese: “the book that I bought” becomes “I bought + 的 + book.”",
        ),
        "pitfall": "Do not place the modifying phrase after the noun as English does. Keep the complete description before 的 and the noun.",
        "extra_examples": (
            ("我昨天买的书在桌上。", "The book that I bought yesterday is on the table."),
            ("坐在门口的人是王老师。", "The person sitting by the door is Teacher Wang."),
            ("红的是我的，蓝的是她的。", "The red one is mine, and the blue one is hers."),
            ("你做的很好吃。", "What you made is delicious."),
        ),
    },
    "不和没": {
        "intro": (
            "不 and 没 both negate, but they view an event differently. 不 rejects a habit, fact, intention, or future action. "
            "没 says that an expected event did not occur or that something is not possessed.",
        ),
        "structures": (
            {"label": "Habit, fact, or choice", "pattern": "不 + verb/adjective", "body": "Use 不 for general truths, repeated behavior, and decisions about now or the future."},
            {"label": "Past non-event or possession", "pattern": "没(有) + verb/noun", "body": "Use 没 before a past event and 没有 for “do not have.” A completed-event 了 normally disappears under 没."},
        ),
        "notes": ("不 often changes to second tone before another fourth-tone syllable in speech.", "没 is not simply a past-tense word; it denies completion or occurrence."),
        "pitfall": "Avoid *没去了 for “did not go.” Say 没去 because 没 already marks the event as unrealized.",
        "extra_examples": (("我明天不去公司。", "I am not going to the office tomorrow."), ("我还没吃早饭。", "I have not eaten breakfast yet.")),
    },
    "想和要": {
        "intro": (
            "想 and 要 can both introduce a desired action, but they differ in force. 想 often sounds like a thought, wish, or tentative plan; 要 can be a firm intention, request, or need.",
        ),
        "structures": (
            {"label": "A softer intention", "pattern": "subject + 想 + verb", "body": "Use 想 when you are considering or would like to do something."},
            {"label": "A firm intention or request", "pattern": "subject + 要 + verb/noun", "body": "Use 要 for a stronger plan, a need, or an order such as requesting an item."},
        ),
        "notes": ("想 can also mean “to miss” when followed by a person.", "不要 before a verb forms a negative command; it is not the ordinary opposite of 想."),
        "pitfall": "In service situations, bare 我要 can sound direct. Adding 请, 想, or a polite context softens the request.",
        "extra_examples": (("我想周末去爬山。", "I would like to go hiking this weekend."), ("我们明天要考试。", "We have an exam tomorrow.")),
    },
    "会和能": {
        "intro": (
            "Mandarin divides English “can” into different ideas. 会 normally points to a learned skill or a likely future event, while 能 points to capacity or circumstances.",
        ),
        "structures": (
            {"label": "Learned skill", "pattern": "会 + verb", "body": "Use 会 for abilities acquired through learning or practice."},
            {"label": "Capacity or circumstances", "pattern": "能 + verb", "body": "Use 能 when health, rules, time, or another condition makes the action possible."},
        ),
        "notes": ("可以 is common when asking or granting permission.", "The right modal depends on why the action is possible, not only on the English translation."),
        "pitfall": "For permission, 能 may ask whether circumstances allow it; 可以 more directly asks whether it is permitted.",
        "extra_examples": (("她会开车。", "She knows how to drive."), ("今天太忙，我不能去。", "I am too busy to go today.")),
    },
    "是的强调句": {
        "intro": (
            "是…的 does not usually announce whether an event happened. It assumes the event is known and focuses one detail: when, where, how, why, or by whom it happened.",
        ),
        "structures": (
            {"label": "Focus a circumstance", "pattern": "subject + 是 + focused detail + verb + 的", "body": "Place the information being contrasted after 是. In positive speech, 是 is sometimes omitted."},
            {"label": "Ask for the missing detail", "pattern": "subject + 是 + question detail + verb + 的？", "body": "Replace the focused detail with 怎么, 哪儿, 什么时候, or another question phrase."},
        ),
        "notes": ("The object may appear before or after 的 depending on length and style.", "Negative 是…的 normally uses 不是 before the focused detail."),
        "pitfall": "Do not use 是…的 merely to say an action is complete. Use it when the completion is already understood and one circumstance matters.",
        "extra_examples": (("我们是在上海认识的。", "It was in Shanghai that we met."), ("这张照片是谁拍的？", "Who took this photo?")),
    },
    "比字句": {
        "intro": (
            "A 比 B compares one specific quality. The adjective follows the comparison directly; 很 is normally unnecessary because the sentence already establishes a degree contrast.",
        ),
        "structures": (
            {"label": "Basic difference", "pattern": "A + 比 + B + adjective", "body": "A has more of the stated quality than B."},
            {"label": "Measured difference", "pattern": "A + 比 + B + adjective + amount", "body": "Add a number, 一点儿, or 多了 after the adjective to show the size of the difference."},
        ),
        "notes": ("To say A is not as adjective as B, use A 没有 B + adjective.", "For equality, use A 跟 B 一样 + adjective."),
        "pitfall": "Avoid adding 很 immediately before the adjective in a basic 比 sentence.",
        "extra_examples": (("这条路比那条路短一点儿。", "This road is a little shorter than that one."), ("坐飞机比坐火车快多了。", "Flying is much faster than taking the train.")),
    },
    "过的经验": {
        "intro": (
            "Experiential 过 looks back over a period of life and confirms that an event has occurred at least once. It does not describe one specific finished event in a narrative.",
        ),
        "structures": (
            {"label": "Affirm an experience", "pattern": "subject + verb + 过 + object", "body": "Use this when whether the experience has ever happened is the main point."},
            {"label": "Deny an experience", "pattern": "subject + 没 + verb + 过 + object", "body": "Use 没 before the verb; 过 remains because it names the experiential viewpoint."},
        ),
        "notes": ("Use 了 for a particular completed event tied to a definite occasion.", "过 can combine with 次 to count how many times the experience occurred."),
        "pitfall": "A precise finished-time phrase such as 昨天 usually calls for 了, not experiential 过.",
        "extra_examples": (("我没坐过高铁。", "I have never taken high-speed rail."), ("她去过成都两次。", "She has been to Chengdu twice.")),
    },
    "着表示持续": {
        "intro": (
            "着 presents a state as continuing. Often an earlier action created the state: a door was opened and is now standing open, or a picture was hung and remains on the wall.",
        ),
        "structures": (
            {"label": "A continuing state", "pattern": "verb + 着", "body": "Use a stative action such as sitting, wearing, holding, opening, or hanging."},
            {"label": "Background manner", "pattern": "verb 1 + 着 + verb 2", "body": "The first action continues as the background while the second action occurs."},
        ),
        "notes": ("正在 highlights an action unfolding; 着 highlights the state that continues.", "Negation is usually 没(有) + verb + 着."),
        "pitfall": "Do not treat every English “-ing” form as 着. Choose 正在 for an active event in progress.",
        "extra_examples": (("她穿着一件蓝衣服。", "She is wearing blue clothing."), ("他笑着跟我说话。", "He spoke to me while smiling.")),
    },
    "结果补语": {
        "intro": (
            "A result complement is part of the verb phrase. The first verb names the action; the following element says whether the intended result—finishing, understanding, finding, seeing, or doing correctly—was reached.",
        ),
        "structures": (
            {"label": "Positive result", "pattern": "verb + result (+ 了)", "body": "The result directly follows the action with no object inserted between them."},
            {"label": "Result not reached", "pattern": "没 + verb + result", "body": "Use 没 before the whole verb-result unit to deny that the outcome occurred."},
        ),
        "notes": ("Common results include 完, 好, 到, 懂, 见, 对, and 错.", "The object follows the complete verb-result unit."),
        "pitfall": "Do not place 了 between the action and its result. Keep the combination together, such as 看完 or 听懂.",
        "extra_examples": (("我找到了那本书。", "I found that book."), ("对不起，我没听清楚。", "Sorry, I did not hear clearly.")),
    },
    "趋向补语": {
        "intro": (
            "Directional complements combine a movement with direction. 来 views the motion as approaching the speaker or chosen viewpoint; 去 views it as moving away.",
        ),
        "structures": (
            {"label": "Simple direction", "pattern": "verb + 来/去", "body": "Use the viewpoint alone when the path is already clear."},
            {"label": "Compound direction", "pattern": "verb + 上/下/进/出/回/过/起 + 来/去", "body": "Add a path element before 来 or 去 to show how the movement unfolds."},
        ),
        "notes": ("Speaker viewpoint matters more than English word choice.", "Location objects have special placement patterns; short objects often sit before 来/去."),
        "pitfall": "Choose 来 or 去 from the scene’s viewpoint, not automatically from the English verb “come” or “go.”",
        "extra_examples": (("请把书拿过来。", "Please bring the book over here."), ("孩子跑上楼去了。", "The child ran upstairs away from here.")),
    },
    "程度补语": {
        "intro": (
            "A 得 complement evaluates an action. The verb names what someone does; the phrase after 得 describes the quality, speed, frequency, or intensity of that performance.",
        ),
        "structures": (
            {"label": "Describe performance", "pattern": "subject + verb + 得 + description", "body": "The description can be an adjective or a fuller phrase."},
            {"label": "Repeat a verb with an object", "pattern": "subject + verb + object + verb + 得 + description", "body": "When the verb already has an object, repeat the verb before 得 in the clearest beginner pattern."},
        ),
        "notes": ("The negative word belongs after 得: 说得不好.", "Questions often replace the description with 怎么样."),
        "pitfall": "Keep 的, 地, and 得 separate: 得 comes after the verb to introduce its degree or manner.",
        "extra_examples": (("他写汉字写得很漂亮。", "He writes Chinese characters beautifully."), ("你今天睡得怎么样？", "How did you sleep today?")),
    },
    "时量补语": {
        "intro": (
            "A duration complement measures how long an action or state continues. Its position depends on whether the verb has an object and whether that object is a pronoun or full noun phrase.",
        ),
        "structures": (
            {"label": "No object", "pattern": "verb + duration", "body": "Place the duration directly after an intransitive verb or state."},
            {"label": "Verb with an object", "pattern": "verb + object + verb + duration", "body": "Repeating the verb is a reliable beginner pattern when the object must remain explicit."},
        ),
        "notes": ("了 after the verb can mark the completed span; sentence-final 了 can imply the state still continues.", "For a continuing state, the English translation may use “have been … for.”"),
        "pitfall": "Do not automatically place the duration before the verb as an ordinary time word.",
        "extra_examples": (("我等了半个小时。", "I waited for half an hour."), ("他学中文学了三年了。", "He has been studying Chinese for three years.")),
    },
    "一点儿和有点儿": {
        "intro": (
            "Both expressions mean “a little,” but their position reveals their job. 有点儿 introduces the speaker’s mild, often negative assessment; 一点儿 follows a quality to request or describe a small difference.",
        ),
        "structures": (
            {"label": "Mild unwanted quality", "pattern": "有点儿 + adjective", "body": "Use this when the current degree is slightly inconvenient or disappointing."},
            {"label": "A small change or comparison", "pattern": "adjective + 一点儿", "body": "Use this after an adjective when asking for a small adjustment or comparing degrees."},
        ),
        "notes": ("有一点儿 can also be a literal small amount before a noun.", "The emotional preference is a tendency, not an absolute rule."),
        "pitfall": "Word order matters: 有点儿贵 means “a bit expensive”; 便宜一点儿 means “a little cheaper.”",
        "extra_examples": (("这个房间有点儿小。", "This room is a bit small."), ("有没有大一点儿的？", "Do you have a slightly larger one?")),
    },
}


def _category_notes(title: str) -> tuple[str, ...]:
    if title in ASPECT_TITLES:
        return (
            "Chinese aspect describes how an event is viewed—completed, ongoing, experienced, or changed—rather than assigning a grammatical tense.",
            "Time words still supply when the event happens; the marker supplies the speaker’s viewpoint.",
            "Compare the positive, negative, and question forms because aspect markers often change under negation.",
        )
    if title in COMPLEMENT_TITLES:
        return (
            "Keep the verb and complement together as one predicate unit.",
            "The complement adds a result, direction, degree, or quantity; it is not a second unrelated action.",
            "Practice the negative form separately because its word order can differ from a positive completed sentence.",
        )
    if title in COMPARISON_TITLES:
        return (
            "Name the two items before stating the property or measurable difference.",
            "Chinese comparison patterns already establish degree, so an extra 很 is often unnecessary.",
            "Equality, inequality, and a measured difference use different structures even when English uses the same adjective.",
        )
    if title in QUESTION_TITLES:
        return (
            "Keep ordinary Chinese word order and change only the part that carries the question.",
            "A question word remains where its answer would appear.",
            "Do not combine two complete yes–no question patterns unless the sentence specifically requires both.",
        )
    if title in NOUN_PHRASE_TITLES:
        return (
            "Chinese modifiers normally come before the noun they describe.",
            "Measure words sit between a number or demonstrative and the noun.",
            "When context makes the head noun obvious, some 的 phrases can stand on their own.",
        )
    return (
        "Read the pattern from left to right and identify which slot changes in your own sentence.",
        "Keep time and place before the main predicate unless this lesson’s pattern explicitly places them elsewhere.",
        "Compare the statement, negative, and question forms before producing the pattern freely.",
    )


def build_guide(point: dict) -> dict:
    guide = GUIDES.get(point["title_zh"], {})
    structures = guide.get("structures") or (
        {
            "label": "Core structure",
            "pattern": point["pattern"],
            "body": "Keep these parts in this order. Replace each English label with the person, time, place, action, or description your sentence needs.",
        },
    )
    intro = guide.get("intro") or (
        point["explanation"],
        "This lesson is easiest to master by noticing its word order first, then varying one slot at a time while keeping the rest of the structure stable.",
    )
    return {
        "intro": intro,
        "structures": structures,
        "notes": guide.get("notes") or _category_notes(point["title_zh"]),
        "pitfall": guide.get("pitfall") or (
            "A word-for-word English translation can produce the wrong Chinese order. "
            "Build from the Chinese pattern, then check the meaning."
        ),
        "extra_examples": guide.get("extra_examples") or (),
    }
