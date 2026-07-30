import re
from .grammar_curriculum import future_dependencies, grammar_dependencies
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
STRICT_MATCHERS = {
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
}

CURATED_EXAMPLE_SETS = {
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
        ("妈妈从厨房走到客厅。", "Mom walks from the kitchen to the living room."),
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
    ],
    "什么的": [
        ("我喜欢看电影、听音乐什么的。", "I like movies, music, and things like that."),
        ("苹果、香蕉什么的都可以买。", "You can buy apples, bananas, and things like that."),
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
        ("他的房间整整齐齐的。", "His room is very neat."),
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
        return not future_dependencies(row["zh"], point, curriculum_order)

    curated = CURATED_EXAMPLE_SETS.get(point["title_zh"])
    if curated:
        return tuple(
            [
                tagged({
                    "zh": zh,
                    "en": en,
                    "source": "authored and reviewed",
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
    theory_candidates = matching + [
        row for row in fallback
    ]
    for row in theory_candidates:
        if len(theory) >= 5:
            break
        if not any(item["zh"] == row["zh"] for item in theory):
            theory.append(tagged(row))

    theory_zh = {row["zh"] for row in theory}
    curated_practice = CURATED_PRACTICE_SETS.get(point["title_zh"])
    if curated_practice:
        practice = [
            tagged({
                "zh": zh,
                "en": en,
                "source": "authored and reviewed",
            })
            for zh, en in curated_practice
            if zh not in theory_zh
        ]
        return theory, practice

    practice = [
        tagged(row)
        for row in matching if row["zh"] not in theory_zh
    ]
    if len(practice) < 10:
        practice_zh = {row["zh"] for row in practice}
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
    return theory, practice


def corpus_for_seed(conn) -> list[dict]:
    return _clean_corpus(conn)
