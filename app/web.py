import json
import hashlib
import random
import re
from difflib import SequenceMatcher
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode
from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from . import config, grading, repo, scheduler, session as session_builder
from .content import bootstrap_content, restore_progress, sentence_pinyin
from .dictionary import word_details
from .db import connect, init_schema
from .exercises.common import NoCarrierSentence, build_question
from .grammar_theory import build_guide
from .seed import apply_declaration
from .segment import segment
from .grammar import seed_grammar
from .tts import synthesize

templates = Jinja2Templates(directory=str(config.ROOT / "templates"))


def get_conn():
    conn = connect(config.DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.DATA_DIR.mkdir(exist_ok=True)
    config.AUDIO_DIR.mkdir(exist_ok=True)
    conn = connect(config.DB_PATH)
    init_schema(conn)
    bootstrap_content(conn)
    seed_grammar(conn)
    restore_progress(conn)
    cutoff = (datetime.now(timezone.utc) - timedelta(
        days=config.BUG_RESOLVED_RETENTION_DAYS)).isoformat()
    conn.execute(
        "DELETE FROM bug_report WHERE resolved=1 AND resolved_ts IS NOT NULL AND resolved_ts<?",
        (cutoff,),
    )
    conn.commit()
    conn.close()
    yield


app = FastAPI(title="汉路 Chinese Tutor", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(config.ROOT / "static")), name="static")


def render(request, name, **context):
    context.update({"request": request, "topics_nav": config.TOPICS})
    return templates.TemplateResponse(request, name, context)


def _relative(ts: str | None) -> str:
    if not ts:
        return "—"
    try:
        seconds = (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds()
    except ValueError:
        return "—"
    if seconds < 3600:
        return f"{max(1, int(seconds // 60))}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    return f"{int(seconds // 86400)}d ago"


def _score(card_json: str | None, settings: dict) -> int | None:
    if not card_json:
        return None
    return round(100 * scheduler.retrievability(
        json.loads(card_json), retention=float(settings["desired_retention"])
    ))


def _vocab_rows(conn, where="", params=(), limit=300, *, hsk=0,
                practice="all", sort="hsk"):
    settings = repo.learner_settings(conn)
    rows = conn.execute(
        "SELECT i.*, "
        "MAX(CASE WHEN ms.facet='listening' THEN ms.card_json END) listen_card,"
        "MAX(CASE WHEN ms.facet='reading-recognition' THEN ms.card_json END) read_card,"
        "COUNT(DISTINCT rl.id) practices, MAX(rl.ts) last_ts,"
        "MAX(iko.status) knowledge_override "
        "FROM item i LEFT JOIN memory_state ms ON ms.item_id=i.id AND ms.user_id=1 "
        "LEFT JOIN review_log rl ON rl.item_id=i.id AND rl.user_id=1 "
        "LEFT JOIN item_knowledge_override iko ON iko.item_id=i.id AND iko.user_id=1 "
        + where + " GROUP BY i.id",
        params,
    ).fetchall()
    result = []
    for row in rows:
        levels = sorted({
            int(value) for value in row["hsk_bands"].split(",") if value.isdigit()
        })
        if hsk in (1, 2, 3) and hsk not in levels:
            continue
        if practice == "unpracticed" and row["practices"]:
            continue
        if practice == "practiced" and not row["practices"]:
            continue
        result.append({
            **dict(row),
            "primary_hsk": min(levels, default=0),
            "listening_score": _score(row["listen_card"], settings),
            "reading_score": _score(row["read_card"], settings),
            "last": _relative(row["last_ts"]),
            "dictionary_url": (
                "https://www.mdbg.net/chinese/dictionary?page=worddict&wdrst=0&wdqb="
                + quote(row["headword"])
            ),
        })
    if sort == "hanzi":
        result.sort(key=lambda row: row["headword"])
    elif sort == "practiced":
        result.sort(key=lambda row: (
            -row["practices"], row["primary_hsk"],
            row["freq_rank"] or 999999, row["id"],
        ))
    elif sort == "last":
        result.sort(key=lambda row: row["last_ts"] or "", reverse=True)
    else:
        result.sort(key=lambda row: (
            row["primary_hsk"] or 99, row["freq_rank"] or 999999, row["id"],
        ))
    return result[:limit]


def _known_headwords(conn) -> set[str]:
    learner_band = conn.execute(
        "SELECT declared_hsk_band FROM learner WHERE id=1"
    ).fetchone()[0]
    latest_reviews = {}
    for row in conn.execute(
        "SELECT i.headword,rl.grade FROM review_log rl JOIN item i ON i.id=rl.item_id "
        "WHERE rl.user_id=1 ORDER BY rl.ts DESC,rl.id DESC"
    ):
        latest_reviews.setdefault(row["headword"], row["grade"])
    known = {
        headword for headword, grade in latest_reviews.items() if grade > 1
    }
    needs_practice = {
        row["headword"] for row in conn.execute(
            "SELECT i.headword FROM item_knowledge_override iko "
            "JOIN item i ON i.id=iko.item_id "
            "WHERE iko.user_id=1 AND iko.status='needs_practice'"
        )
    }
    known.difference_update(needs_practice)
    for row in conn.execute("SELECT headword,hsk_bands FROM item WHERE kind='word'"):
        levels = [int(value) for value in row["hsk_bands"].split(",") if value.isdigit()]
        if (
            row["headword"] not in latest_reviews
            and row["headword"] not in needs_practice
            and levels and min(levels) <= learner_band
        ):
            known.add(row["headword"])
    return known


def _practice_filter_url(path: str, q: str, hsk: int, practice: str) -> str:
    params = {}
    if q.strip():
        params["q"] = q.strip()
    if hsk in (1, 2, 3):
        params["hsk"] = hsk
    if practice in {"unpracticed", "practiced"}:
        params["practice"] = practice
    return path + (f"?{urlencode(params)}" if params else "")


@app.get("/", response_class=HTMLResponse)
def home(request: Request, conn=Depends(get_conn)):
    settings = repo.learner_settings(conn)
    due = repo.due_count(conn)
    new = settings["daily_new_items"]
    practiced = conn.execute("SELECT COUNT(DISTINCT item_id) FROM review_log").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM item").fetchone()[0]
    recent = conn.execute(
        "SELECT i.headword,i.pinyin,i.gloss,rl.grade FROM review_log rl "
        "JOIN item i ON i.id=rl.item_id ORDER BY rl.ts DESC LIMIT 5"
    ).fetchall()
    return render(request, "home.html", due=due, new=new, practiced=practiced,
                  total=total, recent=recent)


def _save_plan(conn, plan):
    conn.execute(
        "INSERT INTO session(id,user_id,plan_json) VALUES(1,1,?) "
        "ON CONFLICT(id) DO UPDATE SET plan_json=excluded.plan_json",
        (json.dumps(plan, ensure_ascii=False),),
    )
    conn.commit()


@app.get("/session/start")
def start_session(conn=Depends(get_conn)):
    queue = session_builder.build(conn)
    _save_plan(conn, {"queue": queue, "idx": 0, "correct": 0, "wrong": 0})
    return RedirectResponse("/session/next", 303)


@app.get("/review/start")
def start_review(conn=Depends(get_conn)):
    queue = session_builder.build(conn, reviews_only=True)
    _save_plan(conn, {"queue": queue, "idx": 0, "correct": 0, "wrong": 0})
    return RedirectResponse("/session/next", 303)


def _current_plan(conn):
    row = conn.execute("SELECT plan_json FROM session WHERE id=1").fetchone()
    return json.loads(row["plan_json"]) if row else None


def _serve(request, conn, plan):
    while plan["idx"] < len(plan["queue"]):
        item_id, facet = plan["queue"][plan["idx"]]
        try:
            question = build_question(conn, item_id, facet)
            break
        except NoCarrierSentence:
            plan["idx"] += 1
            _save_plan(conn, plan)
    else:
        return render(request, "wrap.html", plan=plan)
    is_new = conn.execute(
        "SELECT 1 FROM review_log WHERE user_id=1 AND item_id=? LIMIT 1", (item_id,)
    ).fetchone() is None
    plan["served_at"] = datetime.now(timezone.utc).isoformat()
    plan.pop("reveal", None)
    plan["question"] = asdict(question)
    _save_plan(conn, plan)
    ref = f"#{'R' if facet == 'reading-recognition' else 'L'}{item_id}-{question.sentence_id}"
    return render(request, "question.html", q=question, idx=plan["idx"], ref=ref,
                  is_new=is_new, progress=plan["idx"] + 1, total=len(plan["queue"]))


@app.get("/session/next", response_class=HTMLResponse)
def next_card(request: Request, conn=Depends(get_conn)):
    plan = _current_plan(conn)
    if not plan:
        return RedirectResponse("/", 303)
    if plan.get("reveal"):
        plan["idx"] += 1
    return _serve(request, conn, plan)


@app.post("/session/answer", response_class=HTMLResponse)
def answer(request: Request, idx: int = Form(...), response: str = Form(""),
           hints_used: int = Form(0), conn=Depends(get_conn)):
    plan = _current_plan(conn)
    if not plan:
        return RedirectResponse("/", 303)
    if plan.get("reveal") and idx == plan["idx"]:
        return render(request, "reveal.html", **plan["reveal"])
    if idx != plan["idx"]:
        if plan.get("reveal"):
            return render(request, "reveal.html", **plan["reveal"])
        return _serve(request, conn, plan)
    item_id, facet = plan["queue"][idx]
    stored_question = plan.get("question")
    if stored_question and stored_question.get("item_id") == item_id:
        from .exercises.common import Question
        q = Question(**stored_question)
    else:
        q = build_question(conn, item_id, facet)
    served = datetime.fromisoformat(plan.get("served_at", datetime.now(timezone.utc).isoformat()))
    latency = max(0, int((datetime.now(timezone.utc) - served).total_seconds() * 1000))
    correct = response == q.correct
    settings = repo.learner_settings(conn)
    rating = grading.rating_for(correct, latency, hints_used)
    previous = conn.execute(
        "SELECT * FROM memory_state WHERE user_id=1 AND item_id=? AND facet=?",
        (item_id, facet),
    ).fetchone()
    state = json.loads(previous["card_json"]) if previous else scheduler.new_state()
    new_card = scheduler.review(state, rating, retention=float(settings["desired_retention"]))
    lapses = (previous["lapses"] if previous else 0) + int(not correct)
    conn.execute(
        "INSERT INTO memory_state(user_id,item_id,facet,difficulty,stability,last_review_ts,"
        "due_ts,lapses,suspended,card_json,seeded) VALUES(1,?,?,?,?,?,?,?,?,?,0) "
        "ON CONFLICT(user_id,item_id,facet) DO UPDATE SET difficulty=excluded.difficulty,"
        "stability=excluded.stability,last_review_ts=excluded.last_review_ts,"
        "due_ts=excluded.due_ts,lapses=excluded.lapses,suspended=excluded.suspended,"
        "card_json=excluded.card_json,seeded=0",
        (item_id, facet, new_card.get("difficulty"), new_card.get("stability"),
         new_card.get("last_review"), new_card["due"], lapses,
         int(grading.is_leech(lapses)), json.dumps(new_card)),
    )
    conn.execute(
        "INSERT INTO review_log(user_id,item_id,facet,exercise_type,grade,latency_ms,"
        "hints_used,elapsed_days,ts) VALUES(1,?,?,?,?,?,?,?,?)",
        (item_id, facet, facet, rating, latency, hints_used, None,
         datetime.now(timezone.utc).isoformat()),
    )
    if correct:
        conn.execute(
            "DELETE FROM item_knowledge_override WHERE user_id=1 AND item_id=?",
            (item_id,),
        )
    if facet == "reading-recognition" and previous is None:
        sibling = scheduler.new_state(datetime.now(timezone.utc) + timedelta(days=1))
        conn.execute(
            "INSERT OR IGNORE INTO memory_state(user_id,item_id,facet,difficulty,stability,"
            "last_review_ts,due_ts,lapses,suspended,card_json,seeded) "
            "VALUES(1,?,'listening',NULL,NULL,NULL,?,0,0,?,0)",
            (item_id, sibling["due"], json.dumps(sibling)),
        )
    plan["correct" if correct else "wrong"] += 1
    blanked = q.sentence_zh.replace(q.headword, "＿＿")
    tokens = []
    for token in segment(q.sentence_zh, [q.headword]):
        row = conn.execute("SELECT pinyin,gloss FROM item WHERE headword=?", (token,)).fetchone()
        tokens.append({"word": token, "pinyin": row["pinyin"] if row else "",
                       "gloss": row["gloss"] if row else "—"})
    ref = f"#{'R' if facet == 'reading-recognition' else 'L'}{item_id}-{q.sentence_id}"
    reveal = {
        "q": asdict(q), "idx": idx, "ref": ref, "correct": correct, "response": response or "I don’t know",
        "blanked": blanked, "tokens": tokens, "progress": idx + 1, "total": len(plan["queue"]),
        "word": word_details(conn, item_id, q.sentence_id),
    }
    plan["reveal"] = reveal
    _save_plan(conn, plan)
    conn.commit()
    return render(request, "reveal.html", **reveal)


@app.get("/session/end")
def end_session(conn=Depends(get_conn)):
    conn.execute("DELETE FROM session WHERE id=1")
    conn.commit()
    return RedirectResponse("/", 303)


@app.post("/item/{item_id}/snooze")
def snooze_item(item_id: int, days: int = Form(7), conn=Depends(get_conn)):
    if not conn.execute("SELECT 1 FROM item WHERE id=?", (item_id,)).fetchone():
        return Response("Word not found", 404)
    days = 30 if days == 30 else 7
    until = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    conn.execute(
        "INSERT INTO item_preference(user_id,item_id,snoozed_until) VALUES(1,?,?) "
        "ON CONFLICT(user_id,item_id) DO UPDATE SET snoozed_until=excluded.snoozed_until",
        (item_id, until),
    )
    plan = _current_plan(conn)
    if plan and plan["idx"] < len(plan["queue"]) and plan["queue"][plan["idx"]][0] == item_id:
        plan["idx"] += 1
        plan.pop("reveal", None)
        plan.pop("question", None)
        _save_plan(conn, plan)
    conn.commit()
    return RedirectResponse("/session/next?snoozed=1", 303)


@app.post("/item/{item_id}/knowledge")
def set_item_knowledge(item_id: int, state: str = Form("needs_practice"),
                       return_to: str = Form("/vocab"), conn=Depends(get_conn)):
    if not conn.execute("SELECT 1 FROM item WHERE id=?", (item_id,)).fetchone():
        return Response("Word not found", 404)
    if state == "needs_practice":
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        conn.execute(
            "INSERT INTO item_knowledge_override(user_id,item_id,status,updated_ts) "
            "VALUES(1,?,'needs_practice',?) ON CONFLICT(user_id,item_id) DO UPDATE "
            "SET status=excluded.status,updated_ts=excluded.updated_ts",
            (item_id, now_iso),
        )
        for facet in config.FACETS:
            previous = conn.execute(
                "SELECT * FROM memory_state WHERE user_id=1 AND item_id=? AND facet=?",
                (item_id, facet),
            ).fetchone()
            card = (
                json.loads(previous["card_json"])
                if previous else scheduler.new_state(now)
            )
            card["due"] = now_iso
            conn.execute(
                "INSERT INTO memory_state(user_id,item_id,facet,difficulty,stability,"
                "last_review_ts,due_ts,lapses,suspended,card_json,seeded) "
                "VALUES(1,?,?,?,?,?,?,?,?,?,0) ON CONFLICT(user_id,item_id,facet) "
                "DO UPDATE SET due_ts=excluded.due_ts,suspended=0,"
                "card_json=excluded.card_json,seeded=0",
                (
                    item_id, facet,
                    previous["difficulty"] if previous else card.get("difficulty"),
                    previous["stability"] if previous else card.get("stability"),
                    previous["last_review_ts"] if previous else None,
                    now_iso, previous["lapses"] if previous else 0, 0,
                    json.dumps(card),
                ),
            )
    elif state == "auto":
        conn.execute(
            "DELETE FROM item_knowledge_override WHERE user_id=1 AND item_id=?",
            (item_id,),
        )
    else:
        return Response("Invalid knowledge state", 400)
    conn.commit()
    safe_return = return_to if return_to.startswith("/") and not return_to.startswith("//") else "/vocab"
    return RedirectResponse(safe_return, 303)


@app.get("/vocab", response_class=HTMLResponse)
def vocab(request: Request, q: str = "", hsk: int = 0, practice: str = "all",
          sort: str = "hsk", conn=Depends(get_conn)):
    hsk = hsk if hsk in (1, 2, 3) else 0
    practice = practice if practice in {"all", "unpracticed", "practiced"} else "all"
    sort = sort if sort in {"hsk", "hanzi", "practiced", "last"} else "hsk"
    where, params = "", ()
    if q.strip():
        where = " WHERE i.headword LIKE ? OR i.pinyin LIKE ? OR i.gloss LIKE ? "
        needle = f"%{q.strip()}%"
        params = (needle, needle, needle)
    rows = _vocab_rows(
        conn, where, params, 2000, hsk=hsk, practice=practice, sort=sort
    )
    return render(request, "vocab.html", rows=rows, q=q, hsk=hsk,
                  practice=practice, sort=sort, clear_url="/vocab",
                  practice_url=(
                      _practice_filter_url("/vocab/practice", q, hsk, practice)
                      if rows else ""
                  ),
                  practice_label="Practice this filtered set →",
                  title="Vocabulary",
                  subtitle=f"{len(rows)} matching words in your practical lexicon")


@app.get("/vocab/practice")
def vocab_practice(q: str = "", hsk: int = 0, practice: str = "all",
                   conn=Depends(get_conn)):
    hsk = hsk if hsk in (1, 2, 3) else 0
    practice = practice if practice in {"all", "unpracticed", "practiced"} else "all"
    queue = session_builder.build_filtered(
        conn, hsk=hsk, practice=practice, q=q
    )
    _save_plan(conn, {"queue": queue, "idx": 0, "correct": 0, "wrong": 0})
    return RedirectResponse("/session/next", 303)


@app.get("/topics", response_class=HTMLResponse)
def topics(request: Request, conn=Depends(get_conn)):
    known = _known_headwords(conn)
    inventory_counts = {
        int(row["level"]): row["total"]
        for row in conn.execute(
            "SELECT CAST(hsk_bands AS INTEGER) level,COUNT(*) total "
            "FROM item WHERE kind='word' AND hsk_bands IN ('1','2','3') "
            "GROUP BY hsk_bands"
        )
    }
    inventory = [
        {"level": level, "total": inventory_counts.get(level, 0)}
        for level in (1, 2, 3)
    ]
    grouped = {name: {level: {"known": 0, "total": 0} for level in (1, 2, 3)}
               for name in config.TOPICS}
    topic_words = {name: set() for name in config.TOPICS}
    for row in conn.execute(
        "SELECT it.topic,i.headword,i.hsk_bands FROM item_topic it "
        "JOIN item i ON i.id=it.item_id WHERE i.kind='word'"
    ):
        if row["topic"] not in grouped:
            continue
        topic_words[row["topic"]].add(row["headword"])
        levels = {int(value) for value in row["hsk_bands"].split(",")
                  if value.isdigit() and int(value) in (1, 2, 3)}
        for level in levels:
            grouped[row["topic"]][level]["total"] += 1
            grouped[row["topic"]][level]["known"] += int(row["headword"] in known)
    result = []
    for name in config.TOPICS:
        bands = []
        suggested_level = None
        for level in (1, 2, 3):
            band = grouped[name][level]
            band["level"] = level
            band["percent"] = (
                round(100 * band["known"] / band["total"]) if band["total"] else None
            )
            if suggested_level is None and band["total"] and band["percent"] < 100:
                suggested_level = level
            bands.append(band)
        result.append({
            "name": name,
            "total": len(topic_words[name]),
            "known": len(topic_words[name] & known),
            "bands": bands,
            "suggested_level": suggested_level,
        })
    return render(request, "topics.html", topics=result, inventory=inventory)


@app.get("/topic/{name}", response_class=HTMLResponse)
def topic(request: Request, name: str, q: str = "", hsk: int = 0,
          practice: str = "all", sort: str = "hsk", conn=Depends(get_conn)):
    if name not in config.TOPICS:
        return Response("Unknown topic", 404)
    hsk = hsk if hsk in (1, 2, 3) else 0
    practice = practice if practice in {"all", "unpracticed", "practiced"} else "all"
    sort = sort if sort in {"hsk", "hanzi", "practiced", "last"} else "hsk"
    search_where = ""
    params = [name]
    if q.strip():
        search_where = (
            " AND (i.headword LIKE ? OR i.pinyin LIKE ? OR i.gloss LIKE ?) "
        )
        needle = f"%{q.strip()}%"
        params.extend((needle, needle, needle))
    rows = _vocab_rows(
        conn,
        " JOIN item_topic it_filter ON it_filter.item_id=i.id "
        "WHERE it_filter.topic=? " + search_where,
        tuple(params), 2000, hsk=hsk, practice=practice, sort=sort,
    )
    practice_url = _practice_filter_url(
        f"/topic/{quote(name)}/practice", q, hsk, practice
    ) if rows else ""
    return render(request, "vocab.html", rows=rows, q=q, hsk=hsk,
                  practice=practice, sort=sort,
                  clear_url=f"/topic/{quote(name)}", title=name,
                  subtitle=f"{len(rows)} matching words",
                  practice_url=practice_url,
                  practice_label="Practice this filtered set →")


@app.get("/topic/{name}/practice")
def topic_practice(name: str, q: str = "", hsk: int = 0,
                   practice: str = "all", conn=Depends(get_conn)):
    if name not in config.TOPICS:
        return Response("Unknown topic", 404)
    hsk = hsk if hsk in (1, 2, 3) else 0
    practice = practice if practice in {"all", "unpracticed", "practiced"} else "all"
    queue = session_builder.build_filtered(
        conn, topic=name, hsk=hsk, practice=practice, q=q
    )
    _save_plan(conn, {"queue": queue, "idx": 0, "correct": 0, "wrong": 0})
    return RedirectResponse("/session/next", 303)


def _story_items_in_text(text: str, lexicon_rows: dict[str, dict]) -> list[dict]:
    """Prefer the longest tracked vocabulary item at each Chinese text position."""
    words = sorted(lexicon_rows, key=lambda word: (-len(word), word))
    result = []
    seen = set()
    index = 0
    while index < len(text):
        match = next((word for word in words if text.startswith(word, index)), None)
        if not match:
            index += 1
            continue
        item = lexicon_rows[match]
        if item["id"] not in seen:
            seen.add(item["id"])
            result.append(item)
        index += len(match)
    return result


@app.get("/stories", response_class=HTMLResponse)
def stories(request: Request, conn=Depends(get_conn)):
    known = _known_headwords(conn)
    declared_band = conn.execute(
        "SELECT declared_hsk_band FROM learner WHERE id=1"
    ).fetchone()[0]
    lexicon_rows = {item["headword"]: dict(item) for item in conn.execute(
        "SELECT id,headword FROM item WHERE kind='word'"
    )}
    result = []
    for row in conn.execute(
        "SELECT s.*,COALESCE(ss.status,'new') status,"
        "COALESCE(ss.current_index,0) current_index,"
        "(SELECT COUNT(*) FROM story_sentence_progress sp "
        "WHERE sp.user_id=1 AND sp.story_id=s.id) completed_sentences,"
        "(SELECT COUNT(DISTINCT swe.item_id) FROM story_word_exposure swe "
        "WHERE swe.user_id=1 AND swe.story_id=s.id AND swe.status='hard') hard_words "
        "FROM story s LEFT JOIN story_state ss ON ss.story_id=s.id AND ss.user_id=1 "
        "ORDER BY s.id"
    ):
        content = json.loads(row["sentences_json"])
        tokens = {
            item["headword"] for sentence in content
            for item in _story_items_in_text(sentence["zh"], lexicon_rows)
        }
        score = round(100 * len(tokens & known) / max(1, len(tokens)))
        result.append({**dict(row), "proficiency": score, "sentences": len(content),
                       "known_words": len(tokens & known), "total_words": len(tokens)})
    return render(request, "stories.html", stories=result, declared_band=declared_band)


@app.get("/story/{story_id}", response_class=HTMLResponse)
def story(request: Request, story_id: int, conn=Depends(get_conn)):
    row = conn.execute("SELECT * FROM story WHERE id=?", (story_id,)).fetchone()
    if not row:
        return Response("Story not found", 404)
    content = json.loads(row["sentences_json"])
    completed = {progress["sentence_index"] for progress in conn.execute(
        "SELECT sentence_index FROM story_sentence_progress "
        "WHERE user_id=1 AND story_id=?", (story_id,)
    )}
    hard_by_sentence = {}
    for exposure in conn.execute(
        "SELECT sentence_index,item_id FROM story_word_exposure "
        "WHERE user_id=1 AND story_id=? AND status='hard'", (story_id,)
    ):
        hard_by_sentence.setdefault(exposure["sentence_index"], set()).add(
            exposure["item_id"]
        )
    lexicon_rows = {item["headword"]: dict(item) for item in conn.execute(
        "SELECT id,headword,pinyin,gloss,hsk_bands FROM item WHERE kind='word'"
    )}
    for index, sentence in enumerate(content):
        words = []
        for item in _story_items_in_text(sentence["zh"], lexicon_rows):
            words.append({
                **item,
                "hard": item["id"] in hard_by_sentence.get(index, set()),
            })
        sentence["words"] = words
        sentence["completed"] = index in completed
    state = conn.execute(
        "SELECT status,current_index FROM story_state WHERE user_id=1 AND story_id=?",
        (story_id,),
    ).fetchone()
    status = state["status"] if state else "new"
    start_index = min(max(0, state["current_index"] if state else 0),
                      max(0, len(content) - 1))
    return render(request, "story.html", story=dict(row), sentences=content,
                  status=status, start_index=start_index,
                  completed_count=len(completed))


@app.post("/story/{story_id}/status")
def story_status(request: Request, story_id: int, status: str = Form(...),
                 conn=Depends(get_conn)):
    if status not in {"new", "reading", "finished"}:
        return Response("Invalid story status", 400)
    story_row = conn.execute("SELECT sentences_json FROM story WHERE id=?", (story_id,)).fetchone()
    if not story_row:
        return Response("Story not found", 404)
    current_index = (
        max(0, len(json.loads(story_row["sentences_json"])) - 1)
        if status == "finished" else 0
    )
    conn.execute(
        "INSERT INTO story_state(user_id,story_id,status,current_index,updated_ts) "
        "VALUES(1,?,?,?,?) ON CONFLICT(user_id,story_id) DO UPDATE SET "
        "status=excluded.status,current_index=CASE WHEN excluded.status='new' THEN 0 "
        "WHEN excluded.status='finished' THEN excluded.current_index "
        "ELSE story_state.current_index END,updated_ts=excluded.updated_ts",
        (story_id, status, current_index, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    if request.headers.get("x-requested-with") == "hanlu":
        return {"ok": True, "status": status}
    return RedirectResponse(f"/story/{story_id}", 303)


def _schedule_story_word(conn, item_id: int, hard: bool, now: datetime) -> None:
    previous = conn.execute(
        "SELECT * FROM memory_state WHERE user_id=1 AND item_id=? "
        "AND facet='reading-recognition'", (item_id,)
    ).fetchone()
    if previous and not hard:
        return
    settings = repo.learner_settings(conn)
    state = json.loads(previous["card_json"]) if previous else scheduler.new_state(now)
    rating = 1 if hard else 2
    updated = scheduler.review(
        state, rating, now=now, retention=float(settings["desired_retention"])
    )
    lapses = (previous["lapses"] if previous else 0) + int(hard)
    conn.execute(
        "INSERT INTO memory_state(user_id,item_id,facet,difficulty,stability,last_review_ts,"
        "due_ts,lapses,suspended,card_json,seeded) VALUES(1,?,'reading-recognition',"
        "?,?,?,?,?,?,?,0) ON CONFLICT(user_id,item_id,facet) DO UPDATE SET "
        "difficulty=excluded.difficulty,stability=excluded.stability,"
        "last_review_ts=excluded.last_review_ts,due_ts=excluded.due_ts,"
        "lapses=excluded.lapses,suspended=excluded.suspended,"
        "card_json=excluded.card_json,seeded=0",
        (
            item_id, updated.get("difficulty"), updated.get("stability"),
            updated.get("last_review"), updated["due"], lapses,
            int(grading.is_leech(lapses)), json.dumps(updated),
        ),
    )


@app.post("/story/{story_id}/sentence/{sentence_index}/complete")
def complete_story_sentence(story_id: int, sentence_index: int,
                            hard: str = Form(""), conn=Depends(get_conn)):
    row = conn.execute("SELECT sentences_json FROM story WHERE id=?", (story_id,)).fetchone()
    if not row:
        return Response("Story not found", 404)
    content = json.loads(row["sentences_json"])
    if sentence_index < 0 or sentence_index >= len(content):
        return Response("Sentence not found", 404)
    hard_ids = {
        int(value) for value in hard.split(",")
        if value.strip().isdigit()
    }
    lexicon_rows = {item["headword"]: dict(item) for item in conn.execute(
        "SELECT id,headword FROM item WHERE kind='word'"
    )}
    word_ids = [
        item["id"] for item in _story_items_in_text(
            content[sentence_index]["zh"], lexicon_rows
        )
    ]
    hard_ids &= set(word_ids)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    for item_id in word_ids:
        new_status = "hard" if item_id in hard_ids else "studied"
        existing = conn.execute(
            "SELECT status FROM story_word_exposure WHERE user_id=1 AND story_id=? "
            "AND sentence_index=? AND item_id=?",
            (story_id, sentence_index, item_id),
        ).fetchone()
        changed = not existing or existing["status"] != new_status
        conn.execute(
            "INSERT INTO story_word_exposure(user_id,story_id,sentence_index,item_id,"
            "status,updated_ts) VALUES(1,?,?,?,?,?) ON CONFLICT(user_id,story_id,"
            "sentence_index,item_id) DO UPDATE SET status=excluded.status,"
            "updated_ts=excluded.updated_ts",
            (story_id, sentence_index, item_id, new_status, now_iso),
        )
        if changed:
            grade = 1 if new_status == "hard" else 2
            conn.execute(
                "INSERT INTO review_log(user_id,item_id,facet,exercise_type,grade,"
                "latency_ms,hints_used,elapsed_days,ts) VALUES(1,?,'reading-recognition',"
                "'story-context',?,0,0,NULL,?)",
                (item_id, grade, now_iso),
            )
            _schedule_story_word(conn, item_id, new_status == "hard", now)
    conn.execute(
        "INSERT OR IGNORE INTO story_sentence_progress(user_id,story_id,sentence_index,"
        "completed_ts) VALUES(1,?,?,?)", (story_id, sentence_index, now_iso)
    )
    completed_count = conn.execute(
        "SELECT COUNT(*) FROM story_sentence_progress WHERE user_id=1 AND story_id=?",
        (story_id,),
    ).fetchone()[0]
    status = "finished" if completed_count >= len(content) else "reading"
    next_index = min(sentence_index + 1, len(content) - 1)
    conn.execute(
        "INSERT INTO story_state(user_id,story_id,status,current_index,updated_ts) "
        "VALUES(1,?,?,?,?) ON CONFLICT(user_id,story_id) DO UPDATE SET "
        "status=CASE WHEN story_state.status='finished' THEN 'finished' "
        "ELSE excluded.status END,current_index=MAX(story_state.current_index,"
        "excluded.current_index),updated_ts=excluded.updated_ts",
        (story_id, status, next_index, now_iso),
    )
    conn.commit()
    return {
        "ok": True, "status": status, "completed": completed_count,
        "total": len(content), "studied_words": len(word_ids) - len(hard_ids),
        "hard_words": len(hard_ids),
    }


def _grammar_hints(conn, zh: str) -> list[dict]:
    known = _known_headwords(conn)
    lexicon = {row["headword"] for row in conn.execute("SELECT headword FROM item")}
    hints = []
    for token in segment(zh, lexicon):
        if token in known or not re.search(r"[\u3400-\u9fff]", token):
            continue
        row = conn.execute(
            "SELECT headword,pinyin,gloss,hsk_bands FROM item WHERE headword=?", (token,)
        ).fetchone()
        if row and not any(item["headword"] == token for item in hints):
            hints.append(dict(row))
    return hints


def _grammar_examples(point, include_extra: bool = True) -> list[dict]:
    point_dict = dict(point)
    stored = point_dict.get("theory_examples_json") or "[]"
    examples = list(json.loads(stored))
    if not examples:
        examples = list(json.loads(point["examples_json"]))
    if include_extra and not json.loads(stored):
        for zh, en in build_guide(point_dict)["extra_examples"]:
            if not any(example["zh"] == zh for example in examples):
                examples.append({"zh": zh, "en": en})
    return [{**example, "pinyin": sentence_pinyin(example["zh"])}
            for example in examples]


def _grammar_navigation(conn, grammar_id: int) -> dict:
    rows = [dict(row) for row in conn.execute(
        "SELECT gp.id,gp.level,gp.title_zh,gp.title_en,"
        "COALESCE(gs.status,'not_started') status FROM grammar_point gp "
        "LEFT JOIN grammar_state gs ON gs.grammar_id=gp.id AND gs.user_id=1 "
        "ORDER BY gp.level,gp.id"
    )]
    level_numbers = {1: 0, 2: 0, 3: 0}
    for row in rows:
        level_numbers[row["level"]] += 1
        row["lesson_number"] = level_numbers[row["level"]]
    current_index = next((index for index, row in enumerate(rows)
                          if row["id"] == grammar_id), 0)

    def next_matching(status: str | None = None):
        for offset in range(1, len(rows) + 1):
            candidate = rows[(current_index + offset) % len(rows)]
            if candidate["id"] != grammar_id and (
                status is None or candidate["status"] == status
            ):
                return candidate
        return None

    return {
        "next": next_matching(),
        "not_started": next_matching("not_started"),
        "practicing": next_matching("practicing"),
        "learned": next_matching("learned"),
    }


@app.get("/grammar", response_class=HTMLResponse)
def grammar_page(request: Request, conn=Depends(get_conn)):
    points = []
    for row in conn.execute(
        "SELECT gp.*,COUNT(ga.id) attempts,COALESCE(SUM(ga.correct),0) correct,"
        "COALESCE(gs.status,'not_started') status FROM grammar_point gp "
        "LEFT JOIN grammar_attempt ga ON ga.grammar_id=gp.id AND ga.user_id=1 "
        "LEFT JOIN grammar_state gs ON gs.grammar_id=gp.id AND gs.user_id=1 "
        "GROUP BY gp.id,gs.status ORDER BY gp.level,gp.id"
    ):
        points.append({**dict(row), "examples": json.loads(row["examples_json"])})
    levels = {level: [point for point in points if point["level"] == level]
              for level in (1, 2, 3)}
    for level_points in levels.values():
        for lesson_number, point in enumerate(level_points, 1):
            point["lesson_number"] = lesson_number
    learner_band = conn.execute(
        "SELECT declared_hsk_band FROM learner WHERE id=1"
    ).fetchone()[0]
    status_counts = {"not_started": 0, "practicing": 0, "learned": 0}
    for point in points:
        status_counts[point["status"]] += 1
        point["ready_to_learn"] = (
            point["status"] == "practicing" and point["attempts"] >= 5
            and point["correct"] / point["attempts"] >= 0.8
        )
    curriculum_meta = {}
    for level, level_points in levels.items():
        level_counts = {"not_started": 0, "practicing": 0, "learned": 0}
        for point in level_points:
            level_counts[point["status"]] += 1
        curriculum_meta[level] = {
            "label": f"{len(level_points)} lessons in the curriculum"
                     + (" · WIP" if level == 3 else ""),
            "counts": level_counts,
        }
    return render(request, "grammar.html", levels=levels, learner_band=learner_band,
                  status_counts=status_counts, curriculum_meta=curriculum_meta)


@app.get("/grammar/{grammar_id}", response_class=HTMLResponse)
def grammar_detail(request: Request, grammar_id: int, conn=Depends(get_conn)):
    row = conn.execute("SELECT * FROM grammar_point WHERE id=?", (grammar_id,)).fetchone()
    if not row:
        return Response("Grammar point not found", 404)
    state = conn.execute(
        "SELECT status FROM grammar_state WHERE user_id=1 AND grammar_id=?", (grammar_id,)
    ).fetchone()
    attempts = conn.execute(
        "SELECT COUNT(*) attempts,COALESCE(SUM(correct),0) correct "
        "FROM grammar_attempt WHERE user_id=1 AND grammar_id=?", (grammar_id,)
    ).fetchone()
    point = dict(row)
    level_ids = [item["id"] for item in conn.execute(
        "SELECT id FROM grammar_point WHERE level=? ORDER BY id", (point["level"],)
    )]
    lesson_number = level_ids.index(grammar_id) + 1
    ready_to_learn = (
        (state["status"] if state else "not_started") == "practicing"
        and attempts["attempts"] >= 5
        and attempts["correct"] / attempts["attempts"] >= 0.8
    )
    return render(request, "grammar_detail.html", point=point,
                  examples=_grammar_examples(row), guide=build_guide(point),
                  status=state["status"] if state else "not_started", attempts=attempts,
                  navigation=_grammar_navigation(conn, grammar_id),
                  lesson_number=lesson_number, lesson_total=len(level_ids),
                  ready_to_learn=ready_to_learn)


@app.post("/grammar/{grammar_id}/status")
def grammar_status(request: Request, grammar_id: int, status: str = Form(...),
                   conn=Depends(get_conn)):
    if status not in {"not_started", "practicing", "learned"}:
        return Response("Invalid grammar status", 400)
    if not conn.execute("SELECT 1 FROM grammar_point WHERE id=?", (grammar_id,)).fetchone():
        return Response("Grammar point not found", 404)
    conn.execute(
        "INSERT INTO grammar_state(user_id,grammar_id,status,updated_ts) VALUES(1,?,?,?) "
        "ON CONFLICT(user_id,grammar_id) DO UPDATE SET status=excluded.status,"
        "updated_ts=excluded.updated_ts",
        (grammar_id, status, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    if request.headers.get("x-requested-with") == "hanlu":
        return {"ok": True, "status": status}
    return RedirectResponse(f"/grammar/{grammar_id}", 303)


@app.get("/grammar-audio")
def grammar_audio(text: str = ""):
    text = text.strip()
    if not text or len(text) > 240 or not re.search(r"[\u3400-\u9fff]", text):
        return Response("Invalid Chinese text", 400)
    name = synthesize(text)
    if not name:
        return Response("Audio is temporarily unavailable", 503)
    return FileResponse(config.AUDIO_DIR / name, media_type="audio/mpeg",
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.get("/grammar/practice/card", response_class=HTMLResponse)
def grammar_practice(request: Request, level: int = 0, grammar_id: int = 0,
                     mode: str = "auto", scope: str = "",
                     conn=Depends(get_conn)):
    level = min(3, max(0, level))
    if grammar_id:
        point = conn.execute(
            "SELECT * FROM grammar_point WHERE id=?", (grammar_id,)
        ).fetchone()
    elif scope == "active":
        if level:
            point = conn.execute(
                "SELECT gp.* FROM grammar_point gp JOIN grammar_state gs "
                "ON gs.grammar_id=gp.id AND gs.user_id=1 "
                "WHERE gs.status='practicing' AND gp.level=? "
                "ORDER BY RANDOM() LIMIT 1", (level,)
            ).fetchone()
        else:
            point = conn.execute(
                "SELECT gp.* FROM grammar_point gp JOIN grammar_state gs "
                "ON gs.grammar_id=gp.id AND gs.user_id=1 "
                "WHERE gs.status='practicing' ORDER BY RANDOM() LIMIT 1"
            ).fetchone()
    else:
        point = conn.execute(
            "SELECT * FROM grammar_point WHERE level=? ORDER BY RANDOM() LIMIT 1", (level,)
        ).fetchone()
    if not point:
        return render(request, "grammar_empty.html", level=level, scope=scope)
    practice_payload = point["practice_examples_json"] or "[]"
    examples = json.loads(practice_payload) or json.loads(point["examples_json"])
    example = random.choice(examples)
    declared = conn.execute(
        "SELECT declared_hsk_band FROM learner WHERE id=1"
    ).fetchone()[0]
    direction = mode
    if direction == "auto":
        direction = "production" if declared > point["level"] else "comprehension"
    if direction not in {"comprehension", "production"}:
        direction = "comprehension"
    if direction == "comprehension":
        all_examples = []
        for row in conn.execute(
            "SELECT examples_json,practice_examples_json FROM grammar_point"
        ):
            pool = json.loads(row["practice_examples_json"] or "[]")
            all_examples.extend(pool or json.loads(row["examples_json"]))
        choices = [example["en"]]
        for sample in random.sample(all_examples, min(len(all_examples), 12)):
            if sample["en"] not in choices:
                choices.append(sample["en"])
            if len(choices) == 4:
                break
        random.shuffle(choices)
        prompt, expected = example["zh"], example["en"]
    else:
        choices = []
        prompt, expected = example["en"], example["zh"]
    plan = {
        "grammar_id": point["id"], "level": point["level"], "direction": direction,
        "prompt": prompt, "expected": expected, "zh": example["zh"],
        "en": example["en"], "pinyin": sentence_pinyin(example["zh"]), "mode": mode,
        "ref": f"#G{point['id']}-{hashlib.sha1(example['zh'].encode()).hexdigest()[:6]}",
        "scope": scope, "focus_id": grammar_id, "requested_level": level,
    }
    conn.execute(
        "INSERT INTO grammar_session(id,plan_json) VALUES(1,?) "
        "ON CONFLICT(id) DO UPDATE SET plan_json=excluded.plan_json",
        (json.dumps(plan, ensure_ascii=False),),
    )
    conn.commit()
    return render(request, "grammar_question.html", point=dict(point), plan=plan,
                  choices=choices, hints=_grammar_hints(conn, example["zh"]))


def _normalize_answer(value: str) -> str:
    return re.sub(r"[\s。！？!?.,，'’\"“”]", "", value).lower()


BENIGN_CHINESE_VARIANTS = (
    ("桌子", "桌"),
    ("这里", "这儿"),
    ("那里", "那儿"),
    ("哪里", "哪儿"),
    ("星期", "周"),
)
PROTECTED_GRAMMAR_MARKERS = ("不", "没", "别", "了", "过", "着", "把", "被", "比", "吗")


def _canonical_chinese(value: str) -> str:
    value = _normalize_answer(value)
    for longer, canonical in BENIGN_CHINESE_VARIANTS:
        value = value.replace(longer, canonical)
    return value


def _grammar_match(response: str, expected: str, direction: str) -> tuple[str, str]:
    actual = _normalize_answer(response)
    target = _normalize_answer(expected)
    if actual == target:
        return "exact", ""
    if direction != "production":
        return "incorrect", ""
    if _canonical_chinese(response) == _canonical_chinese(expected):
        if ("桌子" in response and "桌" in expected) or (
            "桌子" in expected and "桌" in response
        ):
            return (
                "accepted_variant",
                "桌子 and 桌 both mean “table.” Before a position word such as 上, "
                "桌子上 and 桌上 are both natural.",
            )
        return (
            "accepted_variant",
            "Your wording uses a common equivalent form, so it has been accepted.",
        )
    markers_match = all(actual.count(marker) == target.count(marker)
                        for marker in PROTECTED_GRAMMAR_MARKERS)
    if markers_match and min(len(actual), len(target)) >= 6:
        if SequenceMatcher(None, actual, target).ratio() >= 0.96:
            return (
                "accepted_close",
                "Your answer differs only slightly and preserves the tested grammar, "
                "so it has been accepted.",
            )
    return "incorrect", ""


def _answer_diff(response: str, expected: str) -> dict:
    actual = _normalize_answer(response)
    target = _normalize_answer(expected)
    matcher = SequenceMatcher(None, actual, target)
    response_chunks, expected_chunks = [], []
    for opcode, a1, a2, b1, b2 in matcher.get_opcodes():
        if a1 != a2:
            response_chunks.append({"text": actual[a1:a2], "changed": opcode != "equal"})
        if b1 != b2:
            expected_chunks.append({"text": target[b1:b2], "changed": opcode != "equal"})
    return {"response": response_chunks, "expected": expected_chunks}


@app.post("/grammar/answer", response_class=HTMLResponse)
def grammar_answer(request: Request, response: str = Form(""),
                   hints_used: int = Form(0), conn=Depends(get_conn)):
    row = conn.execute("SELECT plan_json FROM grammar_session WHERE id=1").fetchone()
    if not row:
        return RedirectResponse("/grammar", 303)
    plan = json.loads(row["plan_json"])
    match_kind, match_feedback = _grammar_match(
        response, plan["expected"], plan["direction"]
    )
    correct = match_kind != "incorrect"
    cursor = conn.execute(
        "INSERT INTO grammar_attempt(user_id,grammar_id,direction,prompt,response,"
        "correct,hints_used,ts,overridden,match_kind) VALUES(1,?,?,?,?,?,?,?,?,?)",
        (plan["grammar_id"], plan["direction"], plan["prompt"], response, int(correct),
         hints_used, datetime.now(timezone.utc).isoformat(), 0, match_kind),
    )
    conn.commit()
    point = conn.execute(
        "SELECT * FROM grammar_point WHERE id=?", (plan["grammar_id"],)
    ).fetchone()
    stats = conn.execute(
        "SELECT COUNT(*) attempts,COALESCE(SUM(correct),0) correct "
        "FROM grammar_attempt WHERE user_id=1 AND grammar_id=?",
        (plan["grammar_id"],),
    ).fetchone()
    state = conn.execute(
        "SELECT status FROM grammar_state WHERE user_id=1 AND grammar_id=?",
        (plan["grammar_id"],),
    ).fetchone()
    ready_to_learn = (
        state and state["status"] == "practicing" and stats["attempts"] >= 5
        and stats["correct"] / stats["attempts"] >= 0.8
    )
    return render(request, "grammar_reveal.html", point=dict(point), plan=plan,
                  response=response or "I don’t know", correct=correct,
                  examples=_grammar_examples(point), match_kind=match_kind,
                  match_feedback=match_feedback,
                  diff=_answer_diff(response, plan["expected"]),
                  attempt_id=cursor.lastrowid, ready_to_learn=ready_to_learn)


@app.post("/grammar/attempt/{attempt_id}/accept")
def accept_grammar_attempt(attempt_id: int, conn=Depends(get_conn)):
    attempt = conn.execute(
        "SELECT id,correct FROM grammar_attempt WHERE id=? AND user_id=1", (attempt_id,)
    ).fetchone()
    if not attempt:
        return Response("Grammar attempt not found", 404)
    conn.execute(
        "UPDATE grammar_attempt SET correct=1,overridden=1,match_kind='manual_override' "
        "WHERE id=? AND user_id=1",
        (attempt_id,),
    )
    conn.commit()
    return {"ok": True, "correct": True}


@app.get("/progress", response_class=HTMLResponse)
def progress(request: Request, conn=Depends(get_conn)):
    totals = conn.execute(
        "SELECT SUM(grade>1) correct,SUM(grade=1) wrong,COUNT(*) total FROM review_log"
    ).fetchone()
    misses = conn.execute(
        "SELECT i.headword,i.pinyin,i.gloss,MAX(rl.ts) ts FROM review_log rl "
        "JOIN item i ON i.id=rl.item_id WHERE rl.grade=1 GROUP BY i.id "
        "ORDER BY ts DESC LIMIT 10"
    ).fetchall()
    recent = conn.execute(
        "SELECT i.headword,i.pinyin,i.gloss,rl.facet,rl.grade,rl.ts FROM review_log rl "
        "JOIN item i ON i.id=rl.item_id ORDER BY rl.ts DESC LIMIT 40"
    ).fetchall()
    return render(request, "progress.html", totals=totals, misses=misses, recent=recent,
                  relative=_relative)


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, conn=Depends(get_conn)):
    learner = conn.execute("SELECT * FROM learner WHERE id=1").fetchone()
    samples = {}
    for band in (1, 2, 3):
        samples[band] = conn.execute(
            "SELECT headword,pinyin,gloss FROM item WHERE hsk_bands LIKE ? "
            "ORDER BY RANDOM() LIMIT 4", (f"%{band}%",)
        ).fetchall()
    return render(request, "settings.html", learner=learner,
                  settings=repo.learner_settings(conn), samples=samples)


@app.post("/settings")
def save_settings(declared_hsk_band: int = Form(...), daily_new_items: int = Form(...),
                  desired_retention: float = Form(...), conn=Depends(get_conn)):
    desired_retention = min(0.99, max(0.50, desired_retention))
    daily_new_items = min(50, max(0, daily_new_items))
    apply_declaration(conn, min(7, max(0, declared_hsk_band)))
    conn.execute("UPDATE learner SET settings_json=? WHERE id=1", (
        json.dumps({"daily_new_items": daily_new_items,
                    "desired_retention": desired_retention}),))
    conn.commit()
    return RedirectResponse("/settings?saved=1", 303)


@app.post("/bug")
def bug(ref: str = Form(""), note: str = Form(""), context: str = Form(""),
        return_to: str = Form("/"), conn=Depends(get_conn)):
    if note.strip():
        init_schema(conn)
        conn.execute("INSERT INTO bug_report(ref,note,context,ts) VALUES(?,?,?,?)",
                     (ref[:80], note.strip(), context[:1200],
                      datetime.now(timezone.utc).isoformat()))
        conn.commit()
    return RedirectResponse(return_to if return_to.startswith("/") else "/", 303)


@app.get("/export")
def export_page(request: Request, conn=Depends(get_conn)):
    return render(request, "export.html")


def _progress_payload(conn):
    memory = conn.execute(
        "SELECT i.headword,ms.facet,ms.difficulty,ms.stability,ms.last_review_ts,"
        "ms.due_ts,ms.lapses,ms.suspended,ms.card_json FROM memory_state ms "
        "JOIN item i ON i.id=ms.item_id WHERE ms.user_id=1"
    ).fetchall()
    reviews = conn.execute(
        "SELECT i.headword,rl.facet,rl.exercise_type,rl.grade,rl.latency_ms,"
        "rl.hints_used,rl.elapsed_days,rl.ts FROM review_log rl "
        "JOIN item i ON i.id=rl.item_id WHERE rl.user_id=1"
    ).fetchall()
    story_states = conn.execute(
        "SELECT s.title_zh,ss.status,ss.current_index,ss.updated_ts "
        "FROM story_state ss JOIN story s ON s.id=ss.story_id WHERE ss.user_id=1"
    ).fetchall()
    story_sentences = conn.execute(
        "SELECT s.title_zh,sp.sentence_index,sp.completed_ts "
        "FROM story_sentence_progress sp JOIN story s ON s.id=sp.story_id "
        "WHERE sp.user_id=1"
    ).fetchall()
    story_words = conn.execute(
        "SELECT s.title_zh,swe.sentence_index,i.headword,swe.status,swe.updated_ts "
        "FROM story_word_exposure swe JOIN story s ON s.id=swe.story_id "
        "JOIN item i ON i.id=swe.item_id WHERE swe.user_id=1"
    ).fetchall()
    knowledge_overrides = conn.execute(
        "SELECT i.headword,iko.status,iko.updated_ts FROM item_knowledge_override iko "
        "JOIN item i ON i.id=iko.item_id WHERE iko.user_id=1"
    ).fetchall()
    band = conn.execute("SELECT declared_hsk_band FROM learner WHERE id=1").fetchone()[0]
    return {"schema": 3, "declared_hsk_band": band,
            "memory_state": [dict(r) for r in memory],
            "review_log": [dict(r) for r in reviews],
            "item_knowledge_override": [dict(r) for r in knowledge_overrides],
            "story_state": [dict(r) for r in story_states],
            "story_sentence_progress": [dict(r) for r in story_sentences],
            "story_word_exposure": [dict(r) for r in story_words]}


@app.get("/export/progress")
def export_progress(conn=Depends(get_conn)):
    data = json.dumps(_progress_payload(conn), ensure_ascii=False, indent=2)
    return Response(data, media_type="application/json", headers={
        "Content-Disposition": 'attachment; filename="progress_export.json"'})


@app.get("/export/topics")
def export_topics(conn=Depends(get_conn)):
    result = {}
    for row in conn.execute(
        "SELECT i.headword,it.topic FROM item_topic it JOIN item i ON i.id=it.item_id "
        "ORDER BY i.headword,it.topic"
    ):
        result.setdefault(row["headword"], []).append(row["topic"])
    return Response(json.dumps(result, ensure_ascii=False, indent=2),
                    media_type="application/json", headers={
                        "Content-Disposition": 'attachment; filename="topic_labels.json"'})


@app.get("/audio/{name}")
def audio(name: str):
    safe = Path(name).name
    path = config.AUDIO_DIR / safe
    return FileResponse(path, media_type="audio/mpeg") if path.exists() else Response(status_code=404)
