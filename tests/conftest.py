import sqlite3
import pytest
from fastapi.testclient import TestClient
from app.db import init_schema
from app.grammar import seed_grammar
from app.web import app, get_conn


@pytest.fixture
def db(tmp_path):
    conn = sqlite3.connect(tmp_path / "test.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    conn.execute(
        "INSERT INTO item(headword,pinyin,gloss,hsk_bands) VALUES('茶','chá','tea','1')"
    )
    item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO sentence(zh,pinyin,en,source,validated) "
        "VALUES('我喜欢喝茶。','wǒ xǐhuan hē chá。','I like drinking tea.','test',1)"
    )
    sentence_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute("INSERT INTO sentence_token VALUES(?,?,0)", (sentence_id, item_id))
    for word, gloss in [("水", "water"), ("饭", "rice"), ("书", "book")]:
        conn.execute("INSERT INTO item(headword,pinyin,gloss,hsk_bands) VALUES(?,?,?,'1')",
                     (word, word, gloss))
    corpus = [
        ("她是我的老师。", "She is my teacher."),
        ("家里有三个人。", "There are three people at home."),
        ("你今天去学校吗？", "Are you going to school today?"),
        ("我昨天没上班。", "I did not work yesterday."),
        ("这是朋友送的书。", "This is a book a friend gave me."),
        ("妹妹正在房间里看书。", "My younger sister is reading in her room."),
        ("我想周末去公园。", "I want to go to the park this weekend."),
        ("他会说中文。", "He can speak Chinese."),
        ("你为什么迟到？", "Why are you late?"),
        ("我们一起吃晚饭吧。", "Let us eat dinner together."),
        ("请再说一次。", "Please say it again."),
        ("我从公司走到车站。", "I walk from the office to the station."),
        ("今天比昨天冷。", "Today is colder than yesterday."),
        ("因为下雨，所以我坐地铁。", "Because it is raining, I am taking the metro."),
        ("我去过北京两次。", "I have been to Beijing twice."),
        ("她穿着一件红衣服。", "She is wearing red clothing."),
        ("电影已经开始了。", "The movie has already started."),
        ("我终于看完这本书了。", "I finally finished this book."),
        ("请把杯子放在桌上。", "Please put the cup on the table."),
        ("门被风吹开了。", "The door was blown open by the wind."),
        ("天气越来越热了。", "The weather is getting hotter."),
        ("我一边听音乐，一边做饭。", "I listen to music while cooking."),
        ("除了咖啡以外，我还买了茶。", "Besides coffee, I also bought tea."),
        ("她中文说得很好。", "She speaks Chinese very well."),
        ("我们在北京住了三个月。", "We lived in Beijing for three months."),
    ]
    conn.executemany(
        "INSERT INTO sentence(zh,en,source,validated) VALUES(?,?,'test corpus',1)",
        corpus,
    )
    seed_grammar(conn)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def client(db):
    def override():
        yield db
    app.dependency_overrides[get_conn] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
