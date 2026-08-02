import re
from .grammar_curriculum import future_dependencies, grammar_dependencies
from .grammar_theory import build_guide


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
STRICT_MATCHERS = {
    "是字句": re.compile(r"(?:^|[，。！？?])[^\uff0c。！？?]{0,10}是[^\uff0c。！？?]{1,10}"),
    "有字句": re.compile(r"(?:没有|有)(?!点|的)[^\uff0c。！？?]{0,12}"),
    "吗问句": re.compile(r"吗[？?]?$"),
    "不和没": re.compile(r"(?:^|[\s，。！？?])[^\uff0c。！？?]{0,8}(?:不|没有|没)(?:是|有|在|去|来|吃|喝|看|听|说|买|卖|学|做|喜欢|想|要|会|能|忙|冷|热|好|大|小|上课|上班)"),
    "的字短语": re.compile(r"[^\uff0c。！？?]{1,12}的(?:书|人|朋友|老师|妈妈|爸爸|哥哥|姐姐|弟弟|妹妹|杯子|手机|衣服|学校|家|茶|猫|东西)|(?:是|有)(?:我|你|他|她)(?:妈妈|爸爸|哥哥|姐姐|弟弟|妹妹)"),
    "在和位置": re.compile(r"(?:^|[，。！？?])[^\uff0c。！？?]{0,10}在(?:家|学校|公司|商店|医院|公园|教室|房间|桌|书包|饭店|地铁|北京|上海|这|那|哪)"),
    "想和要": re.compile(
        r"(?:^|[，。！？?])[^，。！？?]{0,8}(?:不想|想|要)"
        r"(?:吃|喝|去|来|回|看|买|学|说|做|睡|上课|一|两|茶|咖啡)"
    ),
    "基本方位词": re.compile(
        r"在[^\uff0c。！？?]{1,8}(?:上|下|里|外|前面|后面)"
        r"(?:有|是|，|。|！|？|$)|"
        r"[^\uff0c。！？?]{1,8}(?:上|下|里|外|前面|后面)有"
    ),
    "会和能": re.compile(r"(?:不会|会|不能|能)(?:说|写|读|开|游|做|来|去|吃|喝|看|听|学|帮|走|跑|坐|买|工作)"),
    "疑问代词": re.compile(r"谁|什么|哪(?:儿|里|个|本|位)?|怎么|多少|几(?:个|本|点|岁)?"),
    "人称代词": re.compile(r"^(?:我|你|他|她|我们|你们|他们|她们)"),
    "指示代词": re.compile(r"(?:这|那)(?:个|本|杯|张|位|只|些|里|儿|是)"),
    "基本数字": re.compile(r"[零一二两三四五六七八九十百]{1,5}(?:个|本|杯|张|岁|点|人|天|年|月|号)"),
    "基本量词": re.compile(r"(?:[一二两三四五六七八九十]|这|那)(?:个|本|杯|张)(?:人|书|水|茶|纸|照片|苹果|学生|朋友|东西)"),
    "数量短语": re.compile(r"[零一二两三四五六七八九十百]{1,4}(?:个|本|杯|张|只|件|位|条|间|次)"),
    "程度副词": re.compile(r"(?:很|非常|太|真|最)(?:好|大|小|高|矮|冷|热|忙|累|贵|便宜|漂亮|高兴|喜欢|想|快|慢|辣|好吃|有意思)"),
    "都和一起": re.compile(r"(?:我们|你们|他们|大家|[^\uff0c。！？?]{1,8}和[^\uff0c。！？?]{1,8})(?:也)?都|(?:一起)(?:吃|喝|去|来|看|学|做|走|工作|上课|玩)"),
    "时间副词": re.compile(r"(?:马上|有时|现在|今天|明天|昨天|早上|晚上)[^\uff0c。！？?]{0,8}(?:去|来|回|吃|喝|看|学|做|坐|工作|上课|睡)"),
    "常常和再": re.compile(r"常常(?:去|来|吃|喝|看|听|说|学|做|坐|开|读|工作)|再(?:去|来|吃|喝|看|听|说|学|做|读|写|试|等)"),
    "还和也": re.compile(r"(?:^|[，。！？?])[^\uff0c。！？?]{0,8}(?:也|还)(?:是|有|在|去|来|吃|喝|看|听|说|学|做|喜欢|想|要|会|能|忙|好)"),
    "别的命令": re.compile(r"(?:^|[，。！？?])别(?:说|去|来|吃|喝|看|听|忘|开|关|走|跑|等|担心|着急|生气)"),
    "跟和作介词": re.compile(r"(?:^|[，。！？?])[^\uff0c。！？?]{0,8}(?:跟|和)(?:我|你|他|她|爸爸|妈妈|老师|朋友|同学|家人)[^\uff0c。！？?]{0,8}(?:去|来|吃|喝|看|说|学|工作|住|玩|见面)"),
    "和跟还是作连词": re.compile(r"[^\uff0c。！？?]{1,8}(?:和|跟)[^\uff0c。！？?]{1,8}|[^\uff0c。！？?]{1,8}还是[^\uff0c。！？?]{1,8}[？?]"),
    "地字结构": re.compile(r"(?:慢慢|高兴|快|认真|安静|大声|小声|清楚)地(?:说|走|笑|学|看|听|读|写|回|工作)"),
    "动词后的了": re.compile(r"(?:买|吃|喝|看|听|说|学|做|去|来|写|读|开|关|见|找|给)了(?:[一二两三四五六七八九十这那]|[^\uff0c。！？?]{1,10})"),
    "句末语气词": re.compile(r"(?:吧|吗|呢)[！？。!?]?$"),
    "定语": re.compile(r"[^\uff0c。！？?]{1,12}的(?:人|书|东西|老师|朋友|衣服|学校|家|饭|菜|杯子|手机)"),
    "状语": re.compile(r"^(?:[^\uff0c。！？?]{1,8})(?:今天|明天|昨天|早上|晚上|在[^\uff0c。！？?]{1,6}|常常|慢慢地)[^\uff0c。！？?]{1,10}"),
    "补语入门": re.compile(r"(?:看|吃|听|写|做|买|找|学|说|读|喝|关|洗)(?:完|好|懂|到|见|错)|(?:走|跑|拿|带)(?:进|出|回|上|下)(?:来|去)"),
    "动宾短语": re.compile(r"(?:看书|吃饭|喝水|学习中文|学中文|做饭|做作业|买东西|听音乐|看电视|开车|上课|工作)"),
    "偏正短语": re.compile(r"(?:[^\uff0c。！？?]{1,8}的[^\uff0c。！？?]{1,8}|中文书|中国茶|认真学习|慢慢走)"),
    "联合短语": re.compile(r"[^\uff0c。！？?]{1,8}(?:和|跟)[^\uff0c。！？?]{1,8}"),
    "介词短语": re.compile(r"(?:^|[，。！？?])[^\uff0c。！？?]{0,8}(?:在|从|跟|和)(?:家|学校|公司|北京|上海|美国|中国|这|那|我|你|他|她|朋友|老师|妈妈|爸爸)"),
    "祈使句": re.compile(r"^(?:请|别|不要)(?:坐|说|看|听|读|写|吃|喝|去|来|开|关|等|走|跑|忘|担心)"),
    "感叹句": re.compile(r"(?:真|太|多么)(?:好|大|小|高|漂亮|可爱|冷|热|快|慢|贵|便宜|好吃|有意思)[^\uff01!]{0,3}[！!]"),
    "特指问句": re.compile(r"(?:谁|什么|哪(?:儿|里)?|怎么|为什么|多少|几)[^\uff1f?]{0,12}[？?]"),
    "选择问句": re.compile(r"[^\uff0c。！？?]{1,12}还是[^\uff0c。！？?]{1,12}[？?]"),
    "正反问句": re.compile(
        r"是不是|有没有|要不要|想不想|会不会|在不在|来不来|去不去|"
        r"冷不冷|贵不贵|好不好|看没看"
    ),
    "动词重叠": re.compile(r"([\u3400-\u9fff])\1|([\u3400-\u9fff]{2})\2"),
    "形容词重叠": re.compile(r"([\u3400-\u9fff])\1|([\u3400-\u9fff]{2})\2"),
    "多问程度": re.compile(r"多(?:大|高|远|久|长|冷|难)"),
    "是的强调句": re.compile(
        r"是[^，。！？?]{0,18}"
        r"(?:来|去|到|做|买|找|学|认识|坐|跟|在|用|写|说|看|给|拍|出生|进)"
        r"[^，。！？?]{0,12}的[^，。！？?]{0,4}(?:吗|呢)?[。！？?]?$"
    ),
    "状态变化了": re.compile(r"(?:冷|热|高|长高|大|小|好|多|忙|不忙|懂|会|会走路|有|有时间|到家|关门|停|暖和|生气|准备好)了[。！？!?]?$"),
    "进行体": re.compile(r"正在(?:写|吃|看|听|说|学|做|等|下|开|玩|给|上课|[^\uff0c。！？?]{0,6}上课)|正[^\uff0c。！？?]{1,8}呢|在(?:写|吃|看|听|说|学|做|等|下|开|玩|给|上课|[^\uff0c。！？?]{1,6}玩)[^\uff0c。！？?]{0,8}呢|在(?:写|吃|看|听|说|学|做)"),
    "钱数表达": re.compile(r"[零一二两三四五六七八九十百千\d]{1,8}(?:块|元|角|毛|分)(?:钱)?"),
    "日期和时间": re.compile(r"(?:[一二两三四五六七八九十零\d]{1,4}年)?[一二两三四五六七八九十\d]{1,3}月[一二两三四五六七八九十\d]{1,3}(?:号|日)|[一二两三四五六七八九十\d]{1,3}点(?:半|[一二两三四五六七八九十\d]{1,3}分?)?"),
    "了表示完成": re.compile(r"(?:买|吃|喝|看|听|说|学|做|去|来|写|读|开|关|见|找|给)了(?:[^\uff0c。！？?]{1,12})"),
    "正在进行": re.compile(r"正在(?:写|吃|喝|看|听|说|学|做|等|下|开|玩)|在(?:写|吃|喝|看|听|说|学|做|等|下|开|玩)[^\uff0c。！？?]{0,8}呢"),
    "因为所以": re.compile(r"因为|所以"),
    "比字句": re.compile(r"[^\uff0c。！？?]{1,10}比[^\uff0c。！？?]{1,10}(?:高|矮|大|小|冷|热|快|慢|贵|便宜|好|长|短|多|少|早|晚)"),
    "先再然后": re.compile(r"先[^。！？?]{1,16}(?:再|然后)[^。！？?]{1,16}"),
    "过的经验": re.compile(r"(?:去|来|吃|喝|看|听|见|学|做|说|买|用|读|玩|坐|开|住)(?:没)?过"),
    "方向后缀面边": re.compile(r"(?:上|下|里|外|前|后|左|右|对)(?:面|边)"),
    "可能": re.compile(r"可能(?:是|有|在|去|来|吃|喝|看|学|做|下雨|迟到|会|要|不|很)"),
    "离合词": re.compile(r"(?:见[^。！？?]{0,8}面|睡[^。！？?]{0,10}觉|洗[^。！？?]{0,8}澡)"),
    "自己": re.compile(r"(?:自己(?:做|去|来|吃|喝|看|学|写|买|开|照顾|相信|的)|相信自己)"),
    "这么那么": re.compile(r"(?:这么|那么|这样|那样)(?:好|大|小|高|冷|热|快|慢|说|做|学|想|的)"),
    "万和概数": re.compile(r"[一二两三四五六七八九十百\d]{1,5}(?:多)?万|[一二两三四五六七八九十百千\d]{1,5}多(?:个|人|年|天|岁|块|本|分钟|页)"),
    "扩展量词": re.compile(r"(?:[一二两三四五六七八九十]|这|那)(?:(?:条|位|间|名|包|件|辆)(?:鱼|路|裤子|中文老师|老师|医生|客人|房|学生|米|茶|事|衣服|车)|次)"),
    "已经": re.compile(r"已经(?:是|有|在|去|来|吃|喝|看|学|做|完|到|买|开|关|走|住|不|很)"),
    "着表示持续": re.compile(r"(?:开|关|穿|拿|坐|站|躺|放|挂|写|看|听|等|笑)着"),
    "就": re.compile(r"(?:就)(?:是|有|在|去|来|吃|喝|看|学|做|到|回|走|开|起|给|知道|明白|好)|(?:到|来|去|吃|看|做)[^。！？?]{0,4}就"),
    "一点儿和有点儿": re.compile(r"有点(?:儿)?(?:大|小|冷|热|贵|累|忙|慢|难|晚)|(?:大|小|冷|热|贵|便宜|快|慢|多|少|早|晚|好|难|大声|喝)一点(?:儿)?"),
    "从和离": re.compile(r"从[^\uff0c。！？?]{1,10}(?:来|去|到|走|开|回)|[^\uff0c。！？?]{1,10}离[^\uff0c。！？?]{1,10}(?:远|近|有)"),
    "但和但是": re.compile(r"(?:但是|但)[^\uff0c。！？?]{1,14}"),
    "让字兼语句": re.compile(r"让[^\uff0c。！？?]{1,8}(?:去|来|做|看|说|读|写|吃|喝|学|休息|帮)"),
    "连动句": re.compile(r"(?:去|来)(?:学校|商店|公园|饭店|北京|上海|家)?(?:买|看|吃|喝|学|做|找|见|玩)|(?:坐|开)(?:车|地铁|火车)(?:去|来)"),
    "的字短语作名词": re.compile(r"[^\uff0c。！？?]{1,16}的(?:人|书|电影|饭|衣服|东西|是|都|很|给|已经|那|这|，|。|！|？|$)"),
    "即将发生": re.compile(r"(?:快要|就要)(?:下雨|上课|下课|到|走|来|去|回|开始|结束|关门|考试|放假)"),
    "都已经了": re.compile(r"都(?:已经|[^\uff0c。！？?]{1,8})[^\uff0c。！？?]{0,8}了(?:[，。！？!?]|$)"),
    "还是吧": re.compile(r"还是[^\uff0c。！？?]{1,12}吧[。！？!?]?$"),
    "结果补语": re.compile(r"(?:看|吃|听|写|做|买|找|学|说|读|喝|关|洗)(?:完|好|懂|到|见|对|错|清楚)"),
    "趋向补语": re.compile(r"(?:(?:走|跑|拿|带|回|搬|开)[^\uff0c。！？?]{0,7}(?:进来|进去|出来|出去|回来|回去|上来|上去|下来|下去|过来|过去|起来)|(?:走|跑)(?:上|下|进|出)[^\uff0c。！？?]{0,5}(?:来|去)|(?:^|请)(?:进来|进去|出来|出去|回来|回去|上来|上去|下来|下去|过来|过去))"),
    "程度补语": re.compile(r"(?:说|写|做|唱|跑|走|睡|学|吃|开|画|游)(?:[^\uff0c。！？?]{0,6})得[^\uff0c。！？?]{1,10}"),
    "时量补语": re.compile(r"(?:学|住|工作|等|睡|看|玩|走)(?:了)?[半一二两三四五六七八九十\d]+(?:个)?(?:小时|分钟|年|月|天)"),
    "一样和没有": re.compile(r"(?:跟|和)[^\uff0c。！？?]{1,10}一样|[^\uff0c。！？?]{1,10}没有[^\uff0c。！？?]{1,10}(?:高|大|小|快|慢|好|贵|冷|热|多)"),
    "把字句": re.compile(r"把[^\uff0c。！？?]{1,10}(?:放|拿|给|打开|关上|吃完|看完|写好|写错|做好|带|送)"),
    "被字句": re.compile(r"被[^\uff0c。！？?]{1,18}"),
}

GENERAL_STRUCTURE_LESSONS = {
    "主语", "谓语", "宾语", "主谓短语", "陈述句",
}

GRAMMAR_WIKI_ADAPTED_SOURCE = (
    "Chinese Grammar Wiki (adapted; see content/ALLSET_ATTRIBUTION.md)"
)

CURATED_EXAMPLE_SETS = {
    "基本方位词": {
        "theory": [
            ("书在桌子上。", "The book is on the table."),
            ("猫在桌子下。", "The cat is under the table."),
            ("杯子在书包里。", "The cup is in the schoolbag."),
            ("学校前面有商店。", "There is a shop in front of the school."),
            ("医院后面有公园。", "There is a park behind the hospital."),
        ],
        "practice": [
            ("手机在桌子上。", "The phone is on the table."),
            ("书包在椅子下。", "The schoolbag is under the chair."),
            ("弟弟在房间里。", "My younger brother is in the room."),
            ("爸爸在公司外。", "Dad is outside the company."),
            ("车在学校前面。", "The vehicle is in front of the school."),
            ("公园在医院后面。", "The park is behind the hospital."),
            ("那本书在椅子上。", "That book is on the chair."),
            ("猫在门外。", "The cat is outside the door."),
            ("我的书在书包里。", "My book is in the schoolbag."),
            ("老师在教室里。", "The teacher is in the classroom."),
            ("妈妈在商店前面。", "Mom is in front of the shop."),
            ("我在家里。", "I am at home."),
        ],
    },
    "想和要": {
        "theory": [
            ("我想喝水。", "I would like to drink water."),
            ("她想看电视。", "She would like to watch television."),
            ("你想回家吗？", "Would you like to go home?"),
            ("我要一杯茶。", "I would like a cup of tea."),
            ("他要去学校。", "He wants to go to school."),
        ],
        "practice": [
            ("我想吃米饭。", "I would like to eat rice."),
            ("你想喝咖啡吗？", "Would you like to drink coffee?"),
            ("我们想看电视。", "We would like to watch television."),
            ("她不想去商店。", "She does not want to go to the shop."),
            ("他想买一本书。", "He would like to buy a book."),
            ("你想吃饭吗？", "Would you like to eat?"),
            ("我要一杯水。", "I would like a cup of water."),
            ("妈妈要两个苹果。", "Mom wants two apples."),
            ("你要咖啡吗？", "Would you like coffee?"),
            ("弟弟要回家。", "My younger brother wants to go home."),
            ("我们明天要上课。", "We have class tomorrow."),
            ("她要学中文。", "She wants to study Chinese."),
        ],
    },
    "在和位置": {
        "theory": [
            ("妈妈在家。", "Mom is at home."),
            ("我在学校学习。", "I study at school."),
            ("爸爸在公司工作。", "Dad works at the company."),
            ("书在桌子上。", "The book is on the table."),
            ("他们在教室里。", "They are in the classroom."),
        ],
        "practice": [
            ("我在家吃饭。", "I eat at home."),
            ("她在学校学习。", "She studies at school."),
            ("他在医院工作。", "He works at the hospital."),
            ("老师在教室里。", "The teacher is in the classroom."),
            ("我的书在桌上。", "My book is on the table."),
            ("手机在书包里。", "The phone is in the schoolbag."),
            ("我们在公园走路。", "We walk in the park."),
            ("妈妈在商店买东西。", "Mom buys things at the shop."),
            ("弟弟在房间里看书。", "My younger brother reads in his room."),
            ("他们在饭店吃饭。", "They eat at the restaurant."),
            ("我在地铁上听音乐。", "I listen to music on the metro."),
            ("猫在桌子下。", "The cat is under the table."),
        ],
    },
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
            ("他昨天没去学校。", "He did not go to school yesterday."),
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

CURATED_PRACTICE_SETS = {
    "从到结构": [
        ("我从家走到公园。", "I walk from home to the park."),
        ("她从学校回到家。", "She returns home from school."),
        ("爸爸从公司开车到机场。", "Dad drives from the company to the airport."),
        ("我们从早上八点学到十点。", "We study from eight to ten in the morning."),
        ("图书馆从星期一开到星期六。", "The library opens from Monday through Saturday."),
        ("从北京到上海要五个小时。", "It takes five hours from Beijing to Shanghai."),
        ("他从一楼走到三楼。", "He walks from the first floor to the third."),
        ("这条路从学校一直到医院。", "This road runs from the school to the hospital."),
        ("我从第一课看到第五课。", "I read from lesson one through lesson five."),
        ("火车从南站开到北站。", "The train runs from the south station to the north station."),
        ("从这儿到商店不远。", "It is not far from here to the shop."),
        ("妈妈从商店走到学校。", "Mom walks from the shop to the school."),
    ],
    "因为所以": [
        ("因为下雨，所以我没出门。", "Because it rained, I did not go out."),
        ("因为今天很冷，所以我穿了外套。", "Because it is cold today, I put on a coat."),
        ("因为他生病了，所以没有上班。", "Because he is sick, he did not go to work."),
        ("因为我喜欢中文，所以每天都学习。", "Because I like Chinese, I study every day."),
        ("因为车来了，所以我们上车吧。", "Because the vehicle has arrived, let us get on."),
        ("因为她很累，所以想早点睡觉。", "Because she is tired, she wants to sleep early."),
        ("因为明天考试，所以我要复习。", "Because the test is tomorrow, I need to review."),
        ("因为没有咖啡，所以我喝茶。", "Because there is no coffee, I am drinking tea."),
        ("因为路很远，所以我们坐地铁。", "Because the journey is far, we are taking the metro."),
        ("因为今天放假，所以学校没有人。", "Because today is a holiday, nobody is at school."),
        ("因为饭很好吃，所以大家都吃了很多。", "Because the food was delicious, everyone ate a lot."),
        ("因为他会说中文，所以我们请他帮忙。", "Because he speaks Chinese, we asked him to help."),
    ],
    "被字句": [
        ("我的自行车被弟弟骑走了。", "My bicycle was ridden away by my younger brother."),
        ("窗户被风吹开了。", "The window was blown open by the wind."),
        ("这本书被老师拿走了。", "This book was taken away by the teacher."),
        ("我的手机被朋友找到了。", "My phone was found by a friend."),
        ("晚饭被孩子们吃完了。", "Dinner was finished by the children."),
        ("门被爸爸关上了。", "The door was closed by Dad."),
        ("他的名字被写错了。", "His name was written incorrectly."),
        ("那张照片被我放在桌上了。", "That photo was put on the table by me."),
        ("小猫被雨淋湿了。", "The kitten was soaked by the rain."),
        ("我的杯子被妹妹打破了。", "My cup was broken by my younger sister."),
        ("问题被大家解决了。", "The problem was solved by everyone."),
        ("他被公司派到北京工作。", "He was sent by the company to work in Beijing."),
        ("那本书被学生拿走了。", "That book was taken away by a student."),
    ],
    "虽然但是": [
        ("虽然工作很忙，但是她每天都运动。", "Although work is busy, she exercises every day."),
        ("虽然没见过面，但是我们常常聊天。", "Although we have not met, we often chat."),
        ("虽然天气很冷，但是孩子们还在外面玩。", "Although it is cold, the children are still playing outside."),
        ("虽然这本书很长，但是我看完了。", "Although this book is long, I finished it."),
        ("虽然他年纪小，但是很会照顾人。", "Although he is young, he is good at caring for people."),
        ("虽然路很远，但是我们还是走到了终点。", "Although the journey was far, we still walked to the end."),
        ("虽然她不舒服，但是还是来上课了。", "Although she felt unwell, she still came to class."),
        ("虽然房间不大，但是非常舒服。", "Although the room is not large, it is very comfortable."),
        ("虽然我听不懂，但是我想继续听。", "Although I cannot understand, I want to keep listening."),
        ("虽然下着雨，但是比赛没有停。", "Although it was raining, the match did not stop."),
        ("虽然价格很贵，但是质量很好。", "Although the price is high, the quality is good."),
        ("虽然时间不多，但是我们做完了。", "Although there was little time, we finished."),
    ],
    "越来越": [
        ("天气越来越热了。", "The weather is getting hotter."),
        ("她的中文越来越好了。", "Her Chinese is getting better."),
        ("孩子越来越高了。", "The child is getting taller."),
        ("我越来越喜欢这个城市。", "I like this city more and more."),
        ("天黑得越来越早了。", "It is getting dark earlier and earlier."),
        ("来这里的人越来越多。", "More and more people are coming here."),
        ("这条路越来越宽了。", "This road is getting wider."),
        ("他的工作越来越忙。", "His work is getting busier."),
        ("我越来越听得懂中文了。", "I understand more and more spoken Chinese."),
        ("妹妹越来越像妈妈。", "My younger sister looks more and more like Mom."),
        ("手机变得越来越便宜了。", "Phones are becoming cheaper and cheaper."),
        ("我们越来越熟了。", "We are becoming more familiar with each other."),
    ],
    "一边一边": [
        ("我一边听音乐，一边做作业。", "I listen to music while doing homework."),
        ("她一边走路，一边打电话。", "She talks on the phone while walking."),
        ("爸爸一边喝茶，一边看新闻。", "Dad drinks tea while watching the news."),
        ("弟弟一边吃饭，一边看电视。", "My younger brother watches television while eating."),
        ("我们一边聊天，一边等车。", "We chat while waiting for the vehicle."),
        ("老师一边说，一边写。", "The teacher writes while speaking."),
        ("妈妈一边做饭，一边听广播。", "Mom listens to the radio while cooking."),
        ("他一边跑步，一边听中文。", "He listens to Chinese while running."),
        ("孩子们一边唱歌，一边跳舞。", "The children dance while singing."),
        ("我一边看地图，一边找路。", "I look for the way while reading the map."),
        ("她一边工作，一边学习。", "She studies while working."),
        ("我们一边走，一边看风景。", "We look at the scenery while walking."),
    ],
    "除了以外": [
        ("除了中文以外，我还学习英语。", "Besides Chinese, I also study English."),
        ("除了他以外，大家都来了。", "Everyone came except him."),
        ("除了星期天以外，她每天都上班。", "She works every day except Sunday."),
        ("除了茶以外，这里还有咖啡。", "Besides tea, there is also coffee here."),
        ("除了北京以外，我还去过上海。", "Besides Beijing, I have also been to Shanghai."),
        ("除了这本书以外，其他的书都很便宜。", "Except for this book, all the others are inexpensive."),
        ("除了妈妈以外，家里没有别人。", "Nobody else is home except Mom."),
        ("除了走路以外，我们也可以坐车。", "Besides walking, we can also take a vehicle."),
        ("除了水果以外，她还买了面包。", "Besides fruit, she also bought bread."),
        ("除了数学以外，他最喜欢中文。", "Besides mathematics, he likes Chinese best."),
        ("除了今天以外，这个星期都有课。", "There is class all week except today."),
        ("除了下雨的时候以外，我每天都跑步。", "I run every day except when it rains."),
        ("除了咖啡以外，他还喜欢茶。", "Besides coffee, he also likes tea."),
        ("除了她以外，我们都会说中文。", "Except for her, we can all speak Chinese."),
        ("除了周末以外，这家商店每天都开门。", "Except on weekends, this shop opens every day."),
    ],
    "动词重叠": [
        ("你看看这张照片。", "Take a look at this photo."),
        ("我想想这个问题。", "Let me think about this question."),
        ("请说说你的家人。", "Please talk a little about your family."),
        ("我们出去走走吧。", "Let us go out for a short walk."),
        ("你试试这个菜。", "Try this dish."),
        ("请等等我。", "Please wait for me for a moment."),
        ("大家休息休息吧。", "Everyone, take a short rest."),
        ("我听听这段录音。", "I will listen to this recording."),
        ("你问问老师。", "Ask the teacher and see."),
        ("我们讨论讨论这个办法。", "Let us discuss this approach a little."),
        ("我去商店看看。", "I will go have a look at the shop."),
        ("请你介绍介绍北京。", "Please tell us a little about Beijing."),
    ],
    "多问程度": [
        ("你的孩子多大？", "How old is your child?"),
        ("那座山多高？", "How tall is that mountain?"),
        ("从你家到学校有多远？", "How far is it from your home to the school?"),
        ("你学中文学了多久？", "How long have you studied Chinese?"),
        ("这个房间多大？", "How large is this room?"),
        ("这条河多长？", "How long is this river?"),
        ("今天有多冷？", "How cold is it today?"),
        ("坐地铁要多久？", "How long does the metro take?"),
        ("你哥哥多高？", "How tall is your older brother?"),
        ("从这里到机场有多远？", "How far is it from here to the airport?"),
        ("这本书有多难？", "How difficult is this book?"),
        ("你每天睡多久？", "How long do you sleep each day?"),
    ],
    "转折复句": [
        ("虽然下雨，但是我们还是出门了。", "Although it rained, we still went out."),
        ("虽然很累，但是她很开心。", "Although she was tired, she was happy."),
        ("虽然他不会做饭，但是很会做咖啡。", "Although he cannot cook, he makes coffee well."),
        ("虽然今天是周末，但是我要工作。", "Although today is the weekend, I need to work."),
        ("虽然车很慢，但是很舒服。", "Although the vehicle is slow, it is comfortable."),
        ("虽然我第一次来，但是我很喜欢这里。", "Although this is my first visit, I like it here."),
        ("虽然她没有时间，但是愿意帮助我。", "Although she has no time, she is willing to help me."),
        ("虽然中文不容易，但是很有意思。", "Although Chinese is not easy, it is interesting."),
        ("虽然已经很晚，但是商店还开着。", "Although it is late, the shop is still open."),
        ("虽然他家很远，但是他从不迟到。", "Although his home is far away, he is never late."),
        ("虽然只有一天，但是我们去了很多地方。", "Although we had only one day, we visited many places."),
        ("虽然这个办法简单，但是很有用。", "Although this method is simple, it is useful."),
        ("虽然今天很冷，但是他还是去了公园。", "Although it is cold today, he still went to the park."),
    ],
    "什么的": [
        ("我喜欢看电影、听音乐什么的。", "I like movies, music, and things like that."),
        ("书、茶什么的都可以买。", "You can buy books, tea, and things like that."),
        ("周末我会看书、做饭什么的。", "On weekends I read, cook, and do things like that."),
        ("她带了衣服、鞋子什么的。", "She brought clothes, shoes, and similar things."),
        ("我们聊工作、学习什么的。", "We talk about work, study, and so on."),
        ("桌上有杯子、盘子什么的。", "There are cups, plates, and things like that on the table."),
        ("他会说中文、英语什么的。", "He speaks Chinese, English, and so on."),
        ("旅行前要准备护照、机票什么的。", "Before traveling, prepare a passport, tickets, and so on."),
        ("我想买点水果、面包什么的。", "I want to buy some fruit, bread, and things like that."),
        ("他们常常一起吃饭、喝茶什么的。", "They often eat, drink tea, and do similar things together."),
        ("她喜欢红色、黄色什么的。", "She likes red, yellow, and colors like those."),
        ("教室里有地图、照片什么的。", "There are maps, photos, and similar things in the classroom."),
        ("我们可以喝茶、聊天什么的。", "We can drink tea, chat, and do things like that."),
    ],
    "是的强调句": [
        ("我是坐地铁来的。", "I came by metro."),
        ("她是昨天到的。", "She arrived yesterday."),
        ("这本书是老师给我的。", "The teacher gave me this book."),
        ("我们是在学校认识的。", "We met at school."),
        ("他是跟朋友一起去的。", "He went with a friend."),
        ("你是什么时候开始学中文的？", "When did you start learning Chinese?"),
        ("这张照片是谁拍的？", "Who took this photo?"),
        ("我是用手机买的票。", "I bought the ticket using my phone."),
        ("她是在北京出生的。", "She was born in Beijing."),
        ("他们是怎么找到这里的？", "How did they find this place?"),
        ("蛋糕是妈妈做的。", "Mom made the cake."),
        ("我是从南门进来的。", "I came in through the south gate."),
    ],
    "形容词重叠": [
        ("她有一双大大的眼睛。", "She has a pair of big eyes."),
        ("房间干干净净的。", "The room is nice and clean."),
        ("桌上有一本厚厚的书。", "There is a thick book on the table."),
        ("孩子的小脸红红的。", "The child's little face is rosy."),
        ("我们高高兴兴地回家了。", "We went home happily."),
        ("她有漂漂亮亮的衣服。", "She has pretty clothes."),
        ("请写几个大大的字。", "Please write several nice large characters."),
        ("公园里有绿绿的树。", "There are lush green trees in the park."),
        ("桌子干干净净的。", "The table is nice and clean."),
        ("小猫安安静静地坐在门口。", "The kitten is sitting very quietly by the door."),
        ("妹妹的手小小的。", "My younger sister's hands are tiny."),
        ("今天的天空蓝蓝的。", "Today's sky is beautifully blue."),
    ],
    "正反问句": [
        ("你去不去？", "Are you going or not?"),
        ("这个菜好不好吃？", "Does this dish taste good?"),
        ("她是不是老师？", "Is she a teacher?"),
        ("你有没有时间？", "Do you have time?"),
        ("今天冷不冷？", "Is it cold today?"),
        ("他会不会说中文？", "Can he speak Chinese?"),
        ("我们要不要坐地铁？", "Should we take the metro?"),
        ("你想不想喝茶？", "Would you like tea?"),
        ("这本书贵不贵？", "Is this book expensive?"),
        ("妈妈在不在家？", "Is Mom at home?"),
        ("你看没看这部电影？", "Did you watch this movie?"),
        ("他们来不来？", "Are they coming?"),
    ],
    "进行体": [
        ("我正在写作业。", "I am doing homework."),
        ("他们正吃饭呢。", "They are eating right now."),
        ("妹妹在看电视呢。", "My younger sister is watching television."),
        ("老师正在说话。", "The teacher is speaking."),
        ("爸爸在开车呢。", "Dad is driving."),
        ("我们正在等地铁。", "We are waiting for the metro."),
        ("妈妈正做晚饭呢。", "Mom is making dinner."),
        ("孩子们在公园玩呢。", "The children are playing in the park."),
        ("她正在给朋友打电话。", "She is calling a friend."),
        ("外面正在下雨。", "It is raining outside."),
        ("我在听中文录音呢。", "I am listening to a Chinese recording."),
        ("他们正在教室里上课。", "They are having class in the classroom."),
    ],
    "状态变化了": [
        ("天冷了。", "It has become cold."),
        ("我现在懂了。", "I understand now."),
        ("孩子长高了。", "The child has grown taller."),
        ("雨停了。", "The rain has stopped."),
        ("他不生气了。", "He is no longer angry."),
        ("我们到家了。", "We are home now."),
        ("妹妹会走路了。", "My younger sister can walk now."),
        ("商店关门了。", "The shop is closed now."),
        ("我有时间了。", "I have time now."),
        ("天气暖和了。", "The weather has become warmer."),
        ("她的中文好多了。", "Her Chinese is much better now."),
        ("大家都准备好了。", "Everyone is ready now."),
        ("他现在不忙了。", "He is no longer busy now."),
    ],
    "的字短语作名词": [
        ("红的是我的。", "The red one is mine."),
        ("我喜欢你做的饭。", "I like the food you made."),
        ("桌上的都是中文书。", "The ones on the table are all Chinese books."),
        ("穿白衣服的是我姐姐。", "The person wearing white is my older sister."),
        ("你买的很漂亮。", "The one you bought is beautiful."),
        ("我想看老师推荐的电影。", "I want to watch the movie the teacher recommended."),
        ("昨天来的那个人是医生。", "The person who came yesterday is a doctor."),
        ("大的给你，小的给我。", "The big one is for you and the small one for me."),
        ("这是妈妈送给我的。", "This is the one Mom gave me."),
        ("正在说话的是我们的老师。", "The person speaking is our teacher."),
        ("我没找到你说的那本书。", "I did not find the book you mentioned."),
        ("便宜的已经卖完了。", "The inexpensive ones have sold out."),
    ],
}


# These short reviewed banks fill gaps exposed by strict matching. They are
# intentionally simple variations of the lesson's core structure; unlike the
# general sentence corpus, every line was written for the named lesson.
CURATED_PRACTICE_SUPPLEMENTS = {
    "会和能": [
        ("她会写汉字。", "She can write Chinese characters."),
        ("弟弟会游泳。", "My younger brother can swim."),
        ("爸爸会开车。", "Dad knows how to drive."),
        ("我今天能去。", "I can go today."),
        ("你明天能来吗？", "Can you come tomorrow?"),
    ],
    "基本数字": [
        ("我家有三个人。", "There are three people in my family."),
        ("她有五本书。", "She has five books."),
        ("桌上有六个苹果。", "There are six apples on the table."),
        ("我今年二十岁。", "I am twenty years old this year."),
        ("教室里有十个学生。", "There are ten students in the classroom."),
        ("他八点上课。", "His class starts at eight."),
    ],
    "基本量词": [
        ("这个人是我老师。", "This person is my teacher."),
        ("那本书是中文书。", "That book is a Chinese book."),
        ("我要一杯茶。", "I would like a cup of tea."),
        ("桌上有一张照片。", "There is a photo on the table."),
        ("我买两本书。", "I am buying two books."),
        ("她喝三杯水。", "She drinks three cups of water."),
        ("那个学生是我朋友。", "That student is my friend."),
        ("我有四张纸。", "I have four sheets of paper."),
        ("这本书很好。", "This book is very good."),
        ("请给我两杯水。", "Please give me two cups of water."),
        ("那个人是我朋友。", "That person is my friend."),
    ],
    "数量短语": [
        ("我要两个苹果。", "I would like two apples."),
        ("她有三本书。", "She has three books."),
        ("桌上有四杯水。", "There are four cups of water on the table."),
        ("我看了五次。", "I watched it five times."),
        ("家里有两只猫。", "There are two cats at home."),
        ("她买了三件衣服。", "She bought three items of clothing."),
        ("教室里有十位老师。", "There are ten teachers in the classroom."),
        ("这里有六间房。", "There are six rooms here."),
        ("我买了两张票。", "I bought two tickets."),
        ("她喝了一杯咖啡。", "She drank a cup of coffee."),
    ],
    "常常和再": [
        ("他常常喝茶。", "He often drinks tea."),
        ("我们常常看电视。", "We often watch television."),
        ("妈妈常常做饭。", "Mom often cooks."),
        ("她常常听音乐。", "She often listens to music."),
        ("请再说一次。", "Please say it once more."),
        ("我想再看一次。", "I would like to watch it again."),
        ("你再读这本书。", "Read this book again."),
        ("我们明天再来。", "We will come again tomorrow."),
        ("爸爸常常开车去公司。", "Dad often drives to the company."),
        ("你再试一次。", "Try once more."),
        ("我们再等一下。", "Let us wait a little longer."),
        ("她常常读中文书。", "She often reads Chinese books."),
    ],
    "别的命令": [
        ("别走。", "Do not leave."), ("别跑。", "Do not run."),
        ("别开门。", "Do not open the door."),
        ("别关门。", "Do not close the door."),
        ("别吃这个。", "Do not eat this."),
        ("别喝咖啡。", "Do not drink coffee."),
        ("别看电视。", "Do not watch television."),
        ("别担心。", "Do not worry."),
        ("别生气。", "Do not be angry."),
        ("别等我。", "Do not wait for me."),
        ("别去那里。", "Do not go there."),
        ("别来太晚。", "Do not come too late."),
        ("别忘了这本书。", "Do not forget this book."),
    ],
    "跟和作介词": [
        ("我跟妈妈去商店。", "I am going to the shop with Mom."),
        ("她跟老师学中文。", "She studies Chinese with the teacher."),
        ("弟弟跟朋友玩。", "My younger brother plays with a friend."),
        ("我和爸爸看电视。", "I watch television with Dad."),
        ("他和同学吃饭。", "He eats with a classmate."),
    ],
    "地字结构": [
        ("请慢慢地走。", "Please walk slowly."),
        ("他高兴地笑了。", "He laughed happily."),
        ("她认真地学中文。", "She studies Chinese carefully."),
        ("请安静地看书。", "Please read quietly."),
        ("老师清楚地说了一次。", "The teacher said it clearly once."),
        ("他大声地读这本书。", "He reads this book aloud."),
        ("我认真地听老师说话。", "I listen carefully to the teacher."),
        ("妈妈高兴地回家。", "Mom goes home happily."),
        ("她小声地说话。", "She speaks quietly."),
        ("弟弟慢慢地读这本书。", "My younger brother reads this book slowly."),
        ("我认真地写汉字。", "I write Chinese characters carefully."),
        ("他安静地听音乐。", "He listens to music quietly."),
        ("请清楚地写你的名字。", "Please write your name clearly."),
    ],
    "动词后的了": [
        ("我喝了一杯水。", "I drank a cup of water."),
        ("她看了一本书。", "She read a book."),
        ("他写了三个字。", "He wrote three characters."),
        ("我们学了中文。", "We studied Chinese."),
        ("妈妈做了晚饭。", "Mom made dinner."),
    ],
    "祈使句": [
        ("请看这里。", "Please look here."), ("请听。", "Please listen."),
        ("请读这本书。", "Please read this book."),
        ("请写你的名字。", "Please write your name."),
        ("请等一下。", "Please wait a moment."),
        ("请喝茶。", "Please drink some tea."),
        ("别走。", "Do not leave."), ("别跑。", "Do not run."),
        ("不要开门。", "Do not open the door."),
        ("不要担心。", "Do not worry."),
    ],
    "感叹句": [
        ("这本书真好！", "This book is really good!"),
        ("这个孩子真可爱！", "This child is so cute!"),
        ("今天太冷了！", "It is so cold today!"),
        ("这杯茶太热了！", "This tea is too hot!"),
        ("她真漂亮！", "She is really beautiful!"),
        ("你真快！", "You are really fast!"),
        ("这个苹果真大！", "This apple is really big!"),
        ("这个菜太好吃了！", "This dish is so delicious!"),
        ("这间房真大！", "This room is really large!"),
        ("今天太热了！", "It is so hot today!"),
        ("这个公园真漂亮！", "This park is really beautiful!"),
        ("这本书真有意思！", "This book is really interesting!"),
        ("那个孩子真高！", "That child is really tall!"),
    ],
    "选择问句": [
        ("你喝水还是喝茶？", "Do you drink water or tea?"),
        ("他是老师还是学生？", "Is he a teacher or a student?"),
        ("你要这本还是那本？", "Do you want this book or that one?"),
        ("我们在家吃还是去饭店吃？", "Shall we eat at home or at a restaurant?"),
        ("你今天来还是明天来？", "Are you coming today or tomorrow?"),
        ("她会说中文还是英文？", "Can she speak Chinese or English?"),
        ("你看书还是看电视？", "Will you read or watch television?"),
        ("他要咖啡还是茶？", "Does he want coffee or tea?"),
        ("你在学校还是在家？", "Are you at school or at home?"),
        ("我们九点走还是十点走？", "Shall we leave at nine or ten?"),
        ("你买苹果还是买水果？", "Will you buy apples or other fruit?"),
    ],
    "钱数表达": [
        ("这杯咖啡八块钱。", "This coffee costs eight yuan."),
        ("一杯茶五元。", "A cup of tea costs five yuan."),
        ("这个苹果两块钱。", "This apple costs two yuan."),
        ("一张票十元。", "One ticket costs ten yuan."),
        ("这本书十五块钱。", "This book costs fifteen yuan."),
        ("这件衣服五十元。", "This item of clothing costs fifty yuan."),
        ("两杯水四块钱。", "Two cups of water cost four yuan."),
        ("这个菜二十元。", "This dish costs twenty yuan."),
        ("苹果三块五毛。", "The apples cost three yuan and five mao."),
        ("一本书二十五块钱。", "A book costs twenty-five yuan."),
    ],
    "日期和时间": [
        ("今天是八月二号。", "Today is August second."),
        ("明天是三月十号。", "Tomorrow is March tenth."),
        ("我们七点吃饭。", "We eat at seven."),
        ("她九点半上课。", "Her class begins at nine thirty."),
        ("我十一点睡觉。", "I sleep at eleven."),
    ],
    "正在进行": [
        ("我正在看书。", "I am reading."),
        ("她正在写字。", "She is writing."),
        ("爸爸正在开车。", "Dad is driving."),
        ("妈妈正在做饭。", "Mom is cooking."),
        ("我们正在等车。", "We are waiting for the vehicle."),
        ("他在喝茶呢。", "He is drinking tea."),
        ("妹妹在看电视呢。", "My younger sister is watching television."),
        ("老师在说话呢。", "The teacher is speaking."),
    ],
    "先再然后": [
        ("我先喝水，再吃饭。", "I drink water first, then eat."),
        ("她先看书，再睡觉。", "She reads first, then sleeps."),
        ("我们先上课，再吃饭。", "We have class first, then eat."),
        ("你先写字，再读一次。", "Write first, then read it once."),
        ("他先去商店，然后回家。", "He goes to the shop first, then returns home."),
        ("我先看电视，然后做饭。", "I watch television first, then cook."),
        ("请先坐，然后喝茶。", "Please sit first, then drink tea."),
        ("妈妈先买菜，再做饭。", "Mom buys food first, then cooks."),
        ("我先喝茶，然后看书。", "I drink tea first, then read."),
        ("她先去公司，再去商店。", "She goes to the company first, then the shop."),
        ("你先看问题，然后写答案。", "Read the question first, then write the answer."),
        ("我们先学中文，再看电影。", "We study Chinese first, then watch a movie."),
    ],
    "可能": [
        ("他可能在家。", "He may be at home."),
        ("她可能要来。", "She may be coming."),
        ("妈妈可能很忙。", "Mom may be very busy."),
        ("这可能是他的书。", "This may be his book."),
        ("我们明天可能去北京。", "We may go to Beijing tomorrow."),
        ("他可能不喝咖啡。", "He may not drink coffee."),
        ("今天可能会下雨。", "It may rain today."),
        ("她可能在学校学习。", "She may be studying at school."),
    ],
    "离合词": [
        ("我昨天见了他一面。", "I met him once yesterday."),
        ("我们见过两次面。", "We have met twice."),
        ("她跟老师见了一面。", "She met the teacher once."),
        ("他昨天睡了一觉。", "He slept for a while yesterday."),
        ("弟弟睡了半个小时觉。", "My younger brother slept for half an hour."),
        ("我今天洗了一个澡。", "I took a shower today."),
        ("她早上洗了一个澡。", "She took a shower in the morning."),
        ("他们明天见一面。", "They will meet tomorrow."),
        ("我跟朋友见了两次面。", "I met my friend twice."),
        ("弟弟下午睡了一觉。", "My younger brother took a nap in the afternoon."),
        ("我运动后洗了一个澡。", "I took a shower after exercising."),
        ("她昨天跟王老师见了一面。", "She met Teacher Wang yesterday."),
    ],
    "自己": [
        ("她自己学中文。", "She studies Chinese by herself."),
        ("弟弟自己写名字。", "My younger brother writes his name by himself."),
        ("我自己买这本书。", "I will buy this book myself."),
        ("妈妈自己开车去公司。", "Mom drives to the company by herself."),
    ],
    "万和概数": [
        ("这个城市有十万人。", "This city has one hundred thousand people."),
        ("那辆车五万块钱。", "That vehicle costs fifty thousand yuan."),
        ("这里有两万本书。", "There are twenty thousand books here."),
        ("他们学校有一万多个学生。", "Their school has more than ten thousand students."),
        ("我等了十多分钟。", "I waited for more than ten minutes."),
        ("她买了二十多本书。", "She bought more than twenty books."),
        ("他三十多岁。", "He is in his thirties."),
        ("公园里有一百多个人。", "There are more than one hundred people in the park."),
        ("这本书有三百多页。", "This book has more than three hundred pages."),
        ("公司有两千多个人。", "The company has more than two thousand people."),
        ("这套房子两百万块钱。", "This apartment costs two million yuan."),
        ("那里有三万多个人。", "There are more than thirty thousand people there."),
    ],
    "扩展量词": [
        ("她买了一条鱼。", "She bought one fish."),
        ("这是一位中文老师。", "This is a Chinese teacher."),
        ("我们要两间房。", "We need two rooms."),
        ("班里有三十名学生。", "There are thirty students in the class."),
        ("我买了两包米。", "I bought two bags of rice."),
        ("他去过北京两次。", "He has been to Beijing twice."),
        ("妈妈买了三件衣服。", "Mom bought three items of clothing."),
        ("家里有一辆车。", "There is one vehicle at home."),
        ("这里有两条路。", "There are two roads here."),
        ("他是一位医生。", "He is a doctor."),
        ("我去过那家饭店三次。", "I have been to that restaurant three times."),
    ],
    "已经": [
        ("我已经到家了。", "I have already arrived home."),
        ("她已经吃饭了。", "She has already eaten."),
        ("他们已经走了。", "They have already left."),
        ("妈妈已经买了菜。", "Mom has already bought food."),
    ],
    "着表示持续": [
        ("门开着。", "The door is open."),
        ("她穿着红衣服。", "She is wearing red clothing."),
        ("他手里拿着一本书。", "He is holding a book."),
        ("老师坐着说话。", "The teacher is speaking while seated."),
        ("我站着等车。", "I am waiting for the vehicle while standing."),
        ("桌上放着两杯水。", "Two cups of water are sitting on the table."),
        ("墙上挂着一张照片。", "A photo is hanging on the wall."),
        ("她笑着跟我说话。", "She speaks to me while smiling."),
    ],
    "一点儿和有点儿": [
        ("今天有点儿冷。", "It is a little cold today."),
        ("这个房间有点儿小。", "This room is a little small."),
        ("这本书有点儿难。", "This book is a little difficult."),
        ("我今天有点儿累。", "I am a little tired today."),
        ("这杯茶有点儿热。", "This tea is a little hot."),
        ("请慢一点儿。", "Please be a little slower."),
        ("有没有大一点儿的？", "Do you have a slightly larger one?"),
        ("这个便宜一点儿。", "This one is a little cheaper."),
        ("请早一点儿来。", "Please come a little earlier."),
        ("我想多喝一点儿水。", "I would like to drink a little more water."),
        ("今天有点儿热。", "It is a little hot today."),
        ("这件衣服有点儿贵。", "This item of clothing is a little expensive."),
        ("请大声一点儿说。", "Please speak a little louder."),
    ],
    "即将发生": [
        ("快要下雨了。", "It is about to rain."),
        ("我们快要上课了。", "Our class is about to begin."),
        ("火车快要到了。", "The train is about to arrive."),
        ("她快要回家了。", "She is about to return home."),
        ("电影就要开始了。", "The movie is about to begin."),
        ("我们就要放假了。", "Our vacation is about to begin."),
        ("商店就要关门了。", "The shop is about to close."),
        ("他们就要来了。", "They are about to arrive."),
        ("考试快要开始了。", "The test is about to begin."),
        ("我就要走了。", "I am about to leave."),
    ],
    "都已经了": [
        ("都已经十点了。", "It is already ten o'clock."),
        ("他都已经二十岁了。", "He is already twenty years old."),
        ("我们都已经吃过饭了。", "We have all already eaten."),
        ("他们都已经到家了。", "They have all already arrived home."),
        ("都下午五点了。", "It is already five in the afternoon."),
        ("孩子都十岁了。", "The child is already ten years old."),
        ("我都已经回家了。", "I have already returned home."),
        ("他都已经吃饭了。", "He has already eaten."),
        ("都已经十二月了。", "It is already December."),
        ("她都已经走了。", "She has already left."),
        ("我们都已经看完这本书了。", "We have all already finished this book."),
        ("孩子们都已经回家了。", "The children have all already gone home."),
    ],
    "还是吧": [
        ("我们还是坐地铁吧。", "We had better take the metro."),
        ("你还是喝水吧。", "You had better drink water."),
        ("今天还是在家吃吧。", "Let us eat at home today."),
        ("你还是问老师吧。", "You had better ask the teacher."),
        ("我们还是明天去吧。", "We had better go tomorrow."),
        ("他还是先休息吧。", "He had better rest first."),
        ("你还是再看一次吧。", "You had better watch it again."),
        ("我们还是回家吧。", "We had better go home."),
        ("她还是喝茶吧。", "She had better drink tea."),
        ("你还是早一点儿来吧。", "You had better come a little earlier."),
        ("天气很冷，你还是回家吧。", "It is cold, so you had better go home."),
    ],
    "趋向补语": [
        ("请走进来。", "Please walk in."),
        ("他跑出去了。", "He ran out."),
        ("请拿一本书过来。", "Please bring a book over here."),
        ("她走上去了。", "She walked up."),
        ("弟弟跑下来了。", "My younger brother ran down."),
        ("妈妈带回来了两个苹果。", "Mom brought back two apples."),
        ("他开车出去了。", "He drove the vehicle out."),
        ("请拿回去。", "Please take it back."),
        ("孩子跑进来了。", "The child ran in."),
        ("他拿出来一本书。", "He took out a book."),
        ("请带一杯水上来。", "Please bring a cup of water upstairs."),
        ("她从房间里走出来。", "She walked out of the room."),
    ],
    "时量补语": [
        ("我等了十分钟。", "I waited for ten minutes."),
        ("她睡了八个小时。", "She slept for eight hours."),
        ("他在北京住了两年。", "He lived in Beijing for two years."),
        ("我们走了三个小时。", "We walked for three hours."),
        ("妈妈工作了十年。", "Mom worked for ten years."),
        ("弟弟看了一个小时电视。", "My younger brother watched television for an hour."),
        ("我学了三年中文。", "I studied Chinese for three years."),
        ("她在公园玩了两个小时。", "She played in the park for two hours."),
        ("他等了半个小时。", "He waited for half an hour."),
        ("我们在上海住了五天。", "We stayed in Shanghai for five days."),
    ],
    "把字句": [
        ("请把书放在桌上。", "Please put the book on the table."),
        ("我把门打开了。", "I opened the door."),
        ("她把杯子给了我。", "She gave me the cup."),
        ("妈妈把饭做好了。", "Mom finished preparing the food."),
        ("他把苹果吃完了。", "He finished eating the apple."),
        ("我把这本书看完了。", "I finished reading this book."),
        ("请把窗户关上。", "Please close the window."),
        ("弟弟把名字写错了。", "My younger brother wrote the name incorrectly."),
        ("我把手机拿回来了。", "I brought the phone back."),
        ("爸爸把我送到学校。", "Dad took me to school."),
        ("我把水放在桌上。", "I put the water on the table."),
        ("她把手机给了妈妈。", "She gave the phone to Mom."),
        ("请把这个字写好。", "Please write this character carefully."),
    ],
}


def vocabulary_profile(zh: str, bands: dict[str, int]) -> tuple[int, int]:
    """Return minimum vocabulary level and unknown Hanzi count for a sentence."""
    max_word_length = max((len(word) for word in bands), default=1)
    total_unknown = 0
    sentence_level = 1
    for run in re.findall(r"[\u3400-\u9fff]+", zh):
        size = len(run)
        # Each entry is (unknown characters, maximum level, token count).
        best: list[tuple[int, int, int] | None] = [None] * (size + 1)
        best[size] = (0, 1, 0)
        for start in range(size - 1, -1, -1):
            fallback = best[start + 1]
            assert fallback is not None
            choices = [(fallback[0] + 1, fallback[1], fallback[2] + 1)]
            for end in range(start + 1, min(size, start + max_word_length) + 1):
                word = run[start:end]
                if word not in bands or best[end] is None:
                    continue
                tail = best[end]
                choices.append((tail[0], max(bands[word], tail[1]), tail[2] + 1))
            best[start] = min(choices, key=lambda item: (item[0], item[1], item[2]))
        profile = best[0]
        assert profile is not None
        total_unknown += profile[0]
        sentence_level = max(sentence_level, profile[1])
    return sentence_level, total_unknown


def _clean_corpus(conn) -> list[dict]:
    bands = {}
    for item in conn.execute("SELECT headword,hsk_bands FROM item WHERE kind='word'"):
        levels = [int(value) for value in item["hsk_bands"].split(",") if value.isdigit()]
        if levels:
            bands[item["headword"]] = min(levels)
    relaxed_vocab = len(bands) < 100
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
        vocab_level, unknown = vocabulary_profile(zh, bands)
        rows.append({
            "zh": zh, "en": row["en"].strip(), "source": row["source"],
            "_vocab_level": vocab_level, "_unknown": unknown,
            "_relaxed_vocab": relaxed_vocab,
        })
    return rows


def _matches(title: str, zh: str) -> bool:
    strict = STRICT_MATCHERS.get(title)
    if strict:
        return bool(strict.search(zh))
    anchors = ANCHORS.get(title, ())
    if not anchors:
        return True
    if title in REQUIRE_ALL:
        return all(anchor in zh for anchor in anchors[:2])
    return any(anchor in zh for anchor in anchors)


def build_example_sets(conn, point: dict, base_examples: list[dict],
                       corpus: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
    """Create separate, deterministic theory and practice pools from bundled content."""
    curriculum_order = point.get("curriculum_order", {})

    def tagged(row: dict) -> dict:
        result = {key: row[key] for key in ("zh", "en", "source")}
        result["grammar_dependencies"] = list(grammar_dependencies(row["zh"]))
        return result

    def curriculum_safe(row: dict) -> bool:
        hanzi_count = len(re.findall(r"[\u3400-\u9fff]", row["zh"]))
        length_limit = 16 if point["level"] == 1 else 22
        return (
            not future_dependencies(row["zh"], point, curriculum_order)
            and (
                row.get("_relaxed_vocab", False)
                or (
                    row.get("_vocab_level", point["level"]) <= point["level"]
                    and row.get("_unknown", 0) == 0
                )
            )
            and hanzi_count <= length_limit
        )

    curated = CURATED_EXAMPLE_SETS.get(point["title_zh"])
    if curated:
        return tuple(
            [
                tagged({
                    "zh": zh,
                    "en": en,
                    "source": GRAMMAR_WIKI_ADAPTED_SOURCE,
                })
                for zh, en in curated[name]
            ]
            for name in ("theory", "practice")
        )
    corpus = corpus if corpus is not None else _clean_corpus(conn)
    guide = build_guide(point)
    theory = [
        tagged({"zh": row["zh"], "en": row["en"], "source": "authored"})
        for row in base_examples
    ]
    for zh, en in guide["extra_examples"]:
        if not any(row["zh"] == zh for row in theory):
            candidate = {"zh": zh, "en": en, "source": "authored"}
            if curriculum_safe(candidate):
                theory.append(tagged(candidate))

    def candidate_key(row):
        return (
            max(0, row.get("_vocab_level", 1) - point["level"]),
            row.get("_unknown", 0),
            abs(len(row["zh"]) - 11),
            len(row["zh"]),
            row["zh"],
        )

    safe_corpus = [row for row in corpus if curriculum_safe(row)]
    matching = [
        row for row in safe_corpus
        if _matches(point["title_zh"], row["zh"])
    ]
    matching.sort(key=candidate_key)
    fallback = sorted(
        (row for row in safe_corpus if row not in matching),
        key=candidate_key,
    )
    reviewed_candidates = [
        {
            "zh": zh,
            "en": en,
            "source": GRAMMAR_WIKI_ADAPTED_SOURCE,
        }
        for zh, en in (
            list(CURATED_PRACTICE_SETS.get(point["title_zh"], ()))
            + list(CURATED_PRACTICE_SUPPLEMENTS.get(point["title_zh"], ()))
        )
    ]
    theory_candidates = matching + reviewed_candidates
    if point["title_zh"] in GENERAL_STRUCTURE_LESSONS:
        theory_candidates.extend(fallback)
    for row in theory_candidates:
        if len(theory) >= 5:
            break
        if not any(item["zh"] == row["zh"] for item in theory):
            theory.append(tagged(row))

    theory_zh = {row["zh"] for row in theory}
    practice = []
    practice_zh = set()
    reviewed_practice = (
        list(CURATED_PRACTICE_SETS.get(point["title_zh"], ()))
        + list(CURATED_PRACTICE_SUPPLEMENTS.get(point["title_zh"], ()))
    )
    for zh, en in reviewed_practice:
        if zh in theory_zh or zh in practice_zh:
            continue
        practice.append(tagged({
            "zh": zh,
            "en": en,
            "source": GRAMMAR_WIKI_ADAPTED_SOURCE,
        }))
        practice_zh.add(zh)
    if point["title_zh"] in CURATED_PRACTICE_SETS and len(practice) >= 10:
        return theory, practice[:20]
    for row in matching:
        if row["zh"] in theory_zh or row["zh"] in practice_zh:
            continue
        practice.append(tagged(row))
        practice_zh.add(row["zh"])
    if len(practice) < 10 and point["title_zh"] in GENERAL_STRUCTURE_LESSONS:
        practice.extend(
            tagged(row) for row in fallback
            if row["zh"] not in theory_zh and row["zh"] not in practice_zh
        )
    practice = practice[:20]

    # Tiny test databases may not include the bundled sentence corpus. Keep the
    # application usable there while the real bootstrap always produces 10+.
    if not practice:
        practice = [
            tagged({"zh": row["zh"], "en": row["en"], "source": "authored"})
            for row in base_examples
        ]
        practice_zh = {row["zh"] for row in practice}
        theory = [row for row in theory if row["zh"] not in practice_zh]
    return theory, practice


def corpus_for_seed(conn) -> list[dict]:
    return _clean_corpus(conn)
