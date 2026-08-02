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
from .ai_review import (
    AIReviewError,
    ai_review_configured,
    ai_review_model,
    review_grammar_attempt,
)
from .content import bootstrap_content, restore_progress, sentence_pinyin
from .dictionary import word_details
from .db import connect, init_schema
from .exercises.common import NoCarrierSentence, build_question
from .grammar_theory import build_guide
from .seed import apply_declaration
from .segment import segment
from .grammar import seed_grammar
from .grammar_curriculum import RECOMMENDED_EARLY
from .grammar_examples import ANCHORS
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
    context.update({
        "request": request,
        "topics_nav": config.TOPICS,
        "ai_configured": ai_review_configured(),
    })
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


def _set_item_needs_practice(conn, item_id: int) -> None:
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
        card = json.loads(previous["card_json"]) if previous else scheduler.new_state(now)
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


@app.post("/item/{item_id}/knowledge")
def set_item_knowledge(request: Request, item_id: int,
                       state: str = Form("needs_practice"),
                       return_to: str = Form("/vocab"), conn=Depends(get_conn)):
    if not conn.execute("SELECT 1 FROM item WHERE id=?", (item_id,)).fetchone():
        return Response("Word not found", 404)
    if state == "needs_practice":
        _set_item_needs_practice(conn, item_id)
    elif state == "auto":
        conn.execute(
            "DELETE FROM item_knowledge_override WHERE user_id=1 AND item_id=?",
            (item_id,),
        )
    else:
        return Response("Invalid knowledge state", 400)
    conn.commit()
    if request.headers.get("X-Requested-With") == "hanlu":
        return {"ok": True, "state": state}
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


def _tracked_subtokens(value: str, lexicon: set[str]) -> list[str]:
    """Split an untracked Jieba chunk into the longest tracked dictionary words."""
    result = []
    position = 0
    while position < len(value):
        matches = [
            word for word in lexicon
            if value.startswith(word, position)
        ]
        if matches:
            match = max(matches, key=len)
            result.append(match)
            position += len(match)
        else:
            position += 1
    return result


def _grammar_vocabulary(conn, zh: str,
                        excluded_headwords: set[str] | None = None) -> list[dict]:
    known = _known_headwords(conn)
    excluded_headwords = excluded_headwords or set()
    lexicon = {row["headword"] for row in conn.execute("SELECT headword FROM item")}
    vocabulary = []
    tokens = []
    for chunk in segment(zh, lexicon):
        if chunk in lexicon:
            tokens.append(chunk)
        elif re.search(r"[\u3400-\u9fff]", chunk):
            tokens.extend(_tracked_subtokens(chunk, lexicon))
    for token in tokens:
        if any(
            token == marker or (len(marker) == 1 and token.startswith(marker))
            for marker in excluded_headwords
        ):
            continue
        row = conn.execute(
            "SELECT i.id,i.headword,i.pinyin,i.gloss,i.hsk_bands,"
            "iko.status knowledge_override FROM item i LEFT JOIN "
            "item_knowledge_override iko ON iko.item_id=i.id AND iko.user_id=1 "
            "WHERE i.headword=?", (token,)
        ).fetchone()
        if row and not any(item["headword"] == token for item in vocabulary):
            item = dict(row)
            if token == "没":
                # 没 is polyphonic. In beginner negation sentences it is always
                # méi ("not; have not"), not mò ("to drown; to end").
                item["pinyin"] = "méi"
                item["gloss"] = "not; have not"
            item["known"] = token in known
            vocabulary.append(item)
    return vocabulary


ENGLISH_PLACEHOLDER_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "for", "from", "in", "is",
    "it", "of", "on", "or", "the", "to", "was", "were", "with",
}


def _gloss_words(gloss: str) -> set[str]:
    words = {
        word.lower() for word in re.findall(r"[A-Za-z]+", gloss)
        if len(word) >= 3 and word.lower() not in ENGLISH_PLACEHOLDER_STOPWORDS
    }
    return words | {word[:-1] for word in words if word.endswith("s") and len(word) > 3}


def _replace_english_placeholders(conn, response: str, expected: str
                                  ) -> tuple[str, list[dict], list[str]]:
    vocabulary = _grammar_vocabulary(conn, expected)
    matches: list[dict] = []
    unresolved: list[str] = []
    resolved = response
    english_tokens = re.findall(
        r"(?<![A-Za-z])[A-Za-z][A-Za-z'-]*(?![A-Za-z])", response
    )
    for english in dict.fromkeys(english_tokens):
        normalized = english.lower()
        normalized_singular = (
            normalized[:-1] if normalized.endswith("s") and len(normalized) > 3
            else normalized
        )
        candidates = [
            item for item in vocabulary
            if normalized in _gloss_words(item["gloss"])
            or normalized_singular in _gloss_words(item["gloss"])
        ]
        if len(candidates) == 1:
            item = candidates[0]
            resolved = re.sub(
                rf"(?<![A-Za-z]){re.escape(english)}(?![A-Za-z])",
                item["headword"], resolved,
                flags=re.IGNORECASE,
            )
            matches.append({
                "english": english, "item_id": item["id"],
                "headword": item["headword"], "pinyin": item["pinyin"],
                "gloss": item["gloss"],
            })
        else:
            unresolved.append(english)
    return resolved, matches, unresolved


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


def _sync_grammar_status_from_attempts(conn, grammar_id: int) -> str:
    """Advance untouched lesson states while preserving explicit user choices."""
    state = conn.execute(
        "SELECT status,source FROM grammar_state "
        "WHERE user_id=1 AND grammar_id=?",
        (grammar_id,),
    ).fetchone()
    if state and state["source"] == "manual" and state["status"] != "not_started":
        return state["status"]
    stats = conn.execute(
        "SELECT COUNT(*) attempts,COALESCE(SUM(correct),0) correct "
        "FROM grammar_attempt WHERE user_id=1 AND grammar_id=? "
        "AND match_kind<>'curriculum_void'",
        (grammar_id,),
    ).fetchone()
    if not stats["attempts"]:
        return state["status"] if state else "not_started"
    accuracy = stats["correct"] / stats["attempts"]
    status = (
        "learned"
        if stats["attempts"] >= 8 and accuracy >= 0.85
        else "practicing"
    )
    conn.execute(
        "INSERT INTO grammar_state(user_id,grammar_id,status,updated_ts,source) "
        "VALUES(1,?,?,?,'auto') "
        "ON CONFLICT(user_id,grammar_id) DO UPDATE SET "
        "status=excluded.status,updated_ts=excluded.updated_ts,source='auto'",
        (grammar_id, status, datetime.now(timezone.utc).isoformat()),
    )
    return status


@app.get("/grammar", response_class=HTMLResponse)
def grammar_page(request: Request, conn=Depends(get_conn)):
    points = []
    for row in conn.execute(
        "SELECT gp.*,COUNT(ga.id) attempts,COALESCE(SUM(ga.correct),0) correct,"
        "COALESCE(gs.status,'not_started') status FROM grammar_point gp "
        "LEFT JOIN grammar_attempt ga ON ga.grammar_id=gp.id AND ga.user_id=1 "
        "AND ga.match_kind<>'curriculum_void' "
        "LEFT JOIN grammar_state gs ON gs.grammar_id=gp.id AND gs.user_id=1 "
        "GROUP BY gp.id,gs.status ORDER BY gp.level,gp.id"
    ):
        points.append({**dict(row), "examples": json.loads(row["examples_json"])})
    levels = {level: [point for point in points if point["level"] == level]
              for level in (1, 2, 3)}
    for level_points in levels.values():
        for lesson_number, point in enumerate(level_points, 1):
            point["lesson_number"] = lesson_number
            point["recommended_early"] = point["title_zh"] in RECOMMENDED_EARLY
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
        "FROM grammar_attempt WHERE user_id=1 AND grammar_id=? "
        "AND match_kind<>'curriculum_void'", (grammar_id,)
    ).fetchone()
    point = dict(row)
    point["recommended_early"] = point["title_zh"] in RECOMMENDED_EARLY
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
        "INSERT INTO grammar_state(user_id,grammar_id,status,updated_ts,source) "
        "VALUES(1,?,?,?,'manual') "
        "ON CONFLICT(user_id,grammar_id) DO UPDATE SET status=excluded.status,"
        "updated_ts=excluded.updated_ts,source='manual'",
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
    previous_row = conn.execute(
        "SELECT plan_json FROM grammar_session WHERE id=1"
    ).fetchone()
    previous_plan = json.loads(previous_row["plan_json"]) if previous_row else {}
    seen_by_grammar = previous_plan.get("seen_by_grammar", {})
    previous_grammar_id = previous_plan.get("grammar_id")
    previous_zh = previous_plan.get("zh")
    if previous_grammar_id and previous_zh:
        previous_key = str(previous_grammar_id)
        previous_seen = seen_by_grammar.setdefault(previous_key, [])
        if previous_zh not in previous_seen:
            previous_seen.append(previous_zh)
    grammar_key = str(point["id"])
    seen = seen_by_grammar.get(grammar_key, [])
    available = [
        example for example in examples if example["zh"] not in set(seen)
    ]
    if not available:
        seen = []
        available = [
            example for example in examples if example["zh"] != previous_zh
        ] or examples
    example = random.choice(available)
    seen_by_grammar[grammar_key] = [*seen, example["zh"]]
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
        "choices": choices, "seen_by_grammar": seen_by_grammar,
        "tested_markers": list(ANCHORS.get(point["title_zh"], ())),
    }
    conn.execute(
        "INSERT INTO grammar_session(id,plan_json) VALUES(1,?) "
        "ON CONFLICT(id) DO UPDATE SET plan_json=excluded.plan_json",
        (json.dumps(plan, ensure_ascii=False),),
    )
    conn.commit()
    return render(request, "grammar_question.html", point=dict(point), plan=plan,
                  choices=choices,
                  vocabulary=_grammar_vocabulary(
                      conn, example["zh"], set(plan["tested_markers"])
                  ))


def _next_grammar_card_url(plan: dict) -> str:
    params = {"mode": plan.get("mode", "auto")}
    if plan.get("focus_id"):
        params["grammar_id"] = plan["focus_id"]
    elif plan.get("scope") == "active":
        params["scope"] = "active"
        if plan.get("requested_level"):
            params["level"] = plan["requested_level"]
    else:
        params["level"] = plan.get("requested_level") or plan.get("level", 1)
    return f"/grammar/practice/card?{urlencode(params)}"


@app.post("/grammar/session/skip-and-flag")
def skip_and_flag_grammar_sentence(conn=Depends(get_conn)):
    row = conn.execute(
        "SELECT plan_json FROM grammar_session WHERE id=1"
    ).fetchone()
    if not row:
        return RedirectResponse("/grammar", 303)
    plan = json.loads(row["plan_json"])
    point = conn.execute(
        "SELECT title_en FROM grammar_point WHERE id=?",
        (plan["grammar_id"],),
    ).fetchone()
    if not point:
        return RedirectResponse("/grammar", 303)
    context = (
        f"{plan['zh']} — {plan['en']} · {point['title_en']}"
    )
    note = (
        "Skipped automatically: this sentence may be too advanced or may not "
        "test the lesson's target grammar clearly."
    )
    conn.execute(
        "INSERT INTO bug_report(ref,note,context,ts) "
        "SELECT ?,?,?,? WHERE NOT EXISTS "
        "(SELECT 1 FROM bug_report WHERE ref=? AND resolved=0)",
        (
            plan["ref"][:80], note, context[:1200],
            datetime.now(timezone.utc).isoformat(), plan["ref"][:80],
        ),
    )
    conn.commit()
    return RedirectResponse(_next_grammar_card_url(plan), 303)


def _normalize_answer(value: str) -> str:
    return re.sub(r"[\s。！？!?.,，'’\"“”]", "", value).lower()


BENIGN_CHINESE_VARIANTS = (
    ("桌子", "桌"),
    ("这里", "这儿"),
    ("那里", "那儿"),
    ("哪里", "哪儿"),
    ("星期", "周"),
    ("你们国家", "你国家"),
    ("今天很冷吗", "今天冷吗"),
    ("你们现在忙吗", "你现在忙吗"),
    ("您", "你"),
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
    if {actual, target} == {"妈妈今天没上班", "妈妈今天没工作"}:
        return (
            "accepted_variant",
            "没上班 focuses on not going to or being at work, while 没工作 "
            "focuses on not working. Both are natural answers here, and both "
            "use 没 correctly for a past non-event.",
        )
    if actual.replace("她", "他").replace("它", "他") == (
        target.replace("她", "他").replace("它", "他")
    ):
        return (
            "accepted_variant",
            "Your tested grammar is correct. 他, 她, and 它 are all pronounced tā, "
            "but the written character should match he, she, or it; this prompt "
            "uses 她 for “she.”",
        )
    if _canonical_chinese(response) == _canonical_chinese(expected):
        if ("桌子" in response and "桌" in expected) or (
            "桌子" in expected and "桌" in response
        ):
            return (
                "accepted_variant",
                "桌子 and 桌 both mean “table.” Before a position word such as 上, "
                "桌子上 and 桌上 are both natural.",
            )
        if "你国家" in response and "你们国家" in expected:
            return (
                "accepted_variant",
                "Your 吗 question is correct and 你国家 is understandable in "
                "conversation. 你们国家 is the more standard written form for "
                "“your country.”",
            )
        if "今天冷吗" in response and "今天很冷吗" in expected:
            return (
                "accepted_variant",
                "今天冷吗？ and 今天很冷吗？ are both natural yes–no questions. "
                "The degree adverb 很 is optional here.",
            )
        if "你现在忙吗" in response and "你们现在忙吗" in expected:
            return (
                "accepted_variant",
                "English “you” can be singular or plural. 你现在忙吗？ is correct "
                "for one person; 你们现在忙吗？ addresses several people.",
            )
        if ("您" in response) != ("您" in expected):
            return (
                "accepted_variant",
                "Your answer uses a different level of formality: 您 is polite and "
                "你 is neutral. Both preserve the tested grammar.",
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
    resolved_response = response
    vocabulary_supplied: list[dict] = []
    unresolved_placeholders: list[str] = []
    if plan["direction"] == "production":
        resolved_response, vocabulary_supplied, unresolved_placeholders = (
            _replace_english_placeholders(conn, response, plan["expected"])
        )
    match_kind, match_feedback = _grammar_match(
        resolved_response, plan["expected"], plan["direction"]
    )
    if match_kind != "incorrect" and vocabulary_supplied:
        match_kind = "accepted_with_vocab_help"
        supplied = ", ".join(
            f"{item['headword']} ({item['pinyin']}, {item['gloss'].split(';')[0]}) "
            f"for “{item['english']}”"
            for item in vocabulary_supplied
        )
        match_feedback = (
            f"Your grammar is correct. I supplied {supplied}. "
            "That vocabulary was added to practice and is not counted as "
            "independently recalled."
        )
    for item in vocabulary_supplied:
        _set_item_needs_practice(conn, item["item_id"])
    correct = match_kind != "incorrect"
    effective_hints = hints_used + len(vocabulary_supplied)
    cursor = conn.execute(
        "INSERT INTO grammar_attempt(user_id,grammar_id,direction,prompt,response,"
        "expected,correct,hints_used,ts,overridden,match_kind) "
        "VALUES(1,?,?,?,?,?,?,?,?,?,?)",
        (plan["grammar_id"], plan["direction"], plan["prompt"], response,
         plan["expected"], int(correct), effective_hints,
         datetime.now(timezone.utc).isoformat(), 0, match_kind),
    )
    current_status = _sync_grammar_status_from_attempts(
        conn, plan["grammar_id"]
    )
    point = conn.execute(
        "SELECT * FROM grammar_point WHERE id=?", (plan["grammar_id"],)
    ).fetchone()
    stats = conn.execute(
        "SELECT COUNT(*) attempts,COALESCE(SUM(correct),0) correct "
        "FROM grammar_attempt WHERE user_id=1 AND grammar_id=? "
        "AND match_kind<>'curriculum_void'",
        (plan["grammar_id"],),
    ).fetchone()
    ready_to_learn = (
        current_status == "practicing" and stats["attempts"] >= 5
        and stats["correct"] / stats["attempts"] >= 0.8
    )
    reveal = {
        "response": response or "I don’t know",
        "correct": correct,
        "match_kind": match_kind,
        "match_feedback": match_feedback,
        "diff": _answer_diff(resolved_response, plan["expected"]),
        "vocabulary_supplied": vocabulary_supplied,
        "unresolved_placeholders": unresolved_placeholders,
        "attempt_id": cursor.lastrowid,
        "ready_to_learn": bool(ready_to_learn),
        "manual_override": False,
        "ai_review_status": "",
    }
    plan["reveal"] = reveal
    conn.execute(
        "UPDATE grammar_session SET plan_json=? WHERE id=1",
        (json.dumps(plan, ensure_ascii=False),),
    )
    conn.commit()
    return RedirectResponse("/grammar-session/current", 303)


@app.get("/grammar-session/current", response_class=HTMLResponse)
def grammar_current(request: Request, conn=Depends(get_conn)):
    row = conn.execute("SELECT plan_json FROM grammar_session WHERE id=1").fetchone()
    if not row:
        return RedirectResponse("/grammar", 303)
    plan = json.loads(row["plan_json"])
    point = conn.execute(
        "SELECT * FROM grammar_point WHERE id=?", (plan["grammar_id"],)
    ).fetchone()
    if not point:
        return RedirectResponse("/grammar", 303)
    reveal = plan.get("reveal")
    if reveal:
        reveal = _hydrate_reveal_state(conn, reveal)
        return render(
            request, "grammar_reveal.html", point=dict(point), plan=plan,
            examples=_grammar_examples(point), **reveal,
        )
    return render(
        request, "grammar_question.html", point=dict(point), plan=plan,
        choices=plan.get("choices", []),
        vocabulary=_grammar_vocabulary(
            conn, plan["zh"], set(plan.get("tested_markers", ()))
        ),
    )


def _update_current_reveal(conn, attempt_id: int, **updates) -> None:
    row = conn.execute("SELECT plan_json FROM grammar_session WHERE id=1").fetchone()
    if not row:
        return
    plan = json.loads(row["plan_json"])
    reveal = plan.get("reveal")
    if not reveal or reveal.get("attempt_id") != attempt_id:
        return
    reveal.update(updates)
    plan["reveal"] = reveal
    conn.execute(
        "UPDATE grammar_session SET plan_json=? WHERE id=1",
        (json.dumps(plan, ensure_ascii=False),),
    )


def _hydrate_reveal_state(conn, reveal: dict) -> dict:
    result = dict(reveal)
    attempt_id = result.get("attempt_id")
    if not attempt_id:
        return result
    attempt = conn.execute(
        "SELECT correct,overridden,match_kind,expected FROM grammar_attempt "
        "WHERE id=? AND user_id=1", (attempt_id,),
    ).fetchone()
    if attempt:
        result["correct"] = bool(attempt["correct"])
        result["manual_override"] = bool(attempt["overridden"])
        result["match_kind"] = attempt["match_kind"]
    review = conn.execute(
        "SELECT status,provider,model,decision,confidence,target_grammar_correct,"
        "explanation,suggested_answer,differences_json,curriculum_issue,"
        "maintenance_note FROM grammar_review_request "
        "WHERE attempt_id=? AND user_id=1", (attempt_id,),
    ).fetchone()
    result["ai_review_status"] = review["status"] if review else ""
    if review and review["status"] == "resolved":
        explanation = review["explanation"] or ""
        differences = []
        for difference in json.loads(review["differences_json"] or "[]"):
            if (
                difference
                and not _ai_text_overlaps(difference, explanation)
                and not any(
                    _ai_text_overlaps(difference, existing)
                    for existing in differences
                )
            ):
                differences.append(difference)
        review_result = {
            **dict(review),
            "target_grammar_correct": bool(review["target_grammar_correct"]),
            "curriculum_issue": bool(review["curriculum_issue"]),
            "differences": differences,
            "show_suggested_answer": bool(
                review["suggested_answer"]
                and attempt
                and _normalize_answer(review["suggested_answer"])
                != _normalize_answer(attempt["expected"])
            ),
        }
        result["ai_review"] = review_result
        result["show_match_feedback"] = bool(
            result.get("match_feedback")
            and not _ai_text_overlaps(
                result["match_feedback"], review_result["explanation"]
            )
        )
    else:
        result["ai_review"] = None
        result["show_match_feedback"] = bool(result.get("match_feedback"))
    return result


def _ai_text_key(value: str) -> str:
    return re.sub(r"[^\w\u3400-\u9fff]+", " ", str(value or "").lower()).strip()


def _ai_text_overlaps(first: str, second: str) -> bool:
    first_key = _ai_text_key(first)
    second_key = _ai_text_key(second)
    return bool(
        first_key
        and second_key
        and (
            first_key == second_key
            or first_key in second_key
            or second_key in first_key
        )
    )


@app.post("/grammar/attempt/{attempt_id}/accept")
def accept_grammar_attempt(attempt_id: int, conn=Depends(get_conn)):
    attempt = conn.execute(
        "SELECT id,correct,grammar_id FROM grammar_attempt "
        "WHERE id=? AND user_id=1",
        (attempt_id,),
    ).fetchone()
    if not attempt:
        return Response("Grammar attempt not found", 404)
    conn.execute(
        "UPDATE grammar_attempt SET correct=1,overridden=1,match_kind='manual_override' "
        "WHERE id=? AND user_id=1",
        (attempt_id,),
    )
    _sync_grammar_status_from_attempts(conn, attempt["grammar_id"])
    _update_current_reveal(
        conn, attempt_id, correct=True, manual_override=True,
        match_kind="manual_override",
        match_feedback="Marked correct by you. You can undo this decision or queue it "
                       "for an AI review.",
    )
    conn.commit()
    return {"ok": True, "correct": True, "manual_override": True}


@app.post("/grammar/attempt/{attempt_id}/undo-accept")
def undo_grammar_attempt_accept(attempt_id: int, conn=Depends(get_conn)):
    attempt = conn.execute(
        "SELECT id,overridden,grammar_id FROM grammar_attempt "
        "WHERE id=? AND user_id=1",
        (attempt_id,),
    ).fetchone()
    if not attempt:
        return Response("Grammar attempt not found", 404)
    if not attempt["overridden"]:
        return {"ok": True, "correct": False, "manual_override": False}
    conn.execute(
        "UPDATE grammar_attempt SET correct=0,overridden=0,match_kind='incorrect' "
        "WHERE id=? AND user_id=1",
        (attempt_id,),
    )
    _sync_grammar_status_from_attempts(conn, attempt["grammar_id"])
    _update_current_reveal(
        conn, attempt_id, correct=False, manual_override=False,
        match_kind="incorrect", match_feedback="",
    )
    conn.commit()
    return {"ok": True, "correct": False, "manual_override": False}


@app.post("/grammar/attempt/{attempt_id}/request-review")
def request_grammar_ai_review(attempt_id: int, conn=Depends(get_conn)):
    attempt = conn.execute(
        "SELECT * FROM grammar_attempt WHERE id=? AND user_id=1", (attempt_id,)
    ).fetchone()
    if not attempt:
        return Response("Grammar attempt not found", 404)
    point = conn.execute(
        "SELECT * FROM grammar_point WHERE id=?", (attempt["grammar_id"],)
    ).fetchone()
    now_iso = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO grammar_review_request(user_id,attempt_id,status,requested_ts) "
        "VALUES(1,?,'pending',?) ON CONFLICT(attempt_id) DO UPDATE SET "
        "status='pending',requested_ts=excluded.requested_ts,resolved_ts=NULL,"
        "decision='',explanation='',provider='',model='',confidence=0,"
        "target_grammar_correct=0,suggested_answer='',differences_json='[]',"
        "curriculum_issue=0,maintenance_note=''",
        (attempt_id, now_iso),
    )
    _update_current_reveal(conn, attempt_id, ai_review_status="pending")
    conn.commit()
    if not ai_review_configured():
        return {
            "ok": True,
            "status": "pending",
            "realtime": False,
            "message": "Saved for a later review. Add the local DeepSeek key to enable live checks.",
        }
    try:
        result = review_grammar_attempt(dict(attempt), dict(point))
    except AIReviewError as exc:
        conn.execute(
            "INSERT INTO ai_usage(user_id,attempt_id,provider,model,status,error,ts) "
            "VALUES(1,?,? ,?,'error',?,?)",
            (attempt_id, "deepseek", ai_review_model(), str(exc)[:300],
             datetime.now(timezone.utc).isoformat()),
        )
        conn.execute(
            "UPDATE grammar_review_request SET explanation=? "
            "WHERE attempt_id=? AND user_id=1",
            (str(exc), attempt_id),
        )
        _update_current_reveal(
            conn, attempt_id, ai_review_status="pending",
            ai_review_error=str(exc),
        )
        conn.commit()
        return {
            "ok": True, "status": "pending", "realtime": False,
            "message": str(exc),
        }

    conn.execute(
        "INSERT INTO ai_usage(user_id,attempt_id,provider,model,status,input_tokens,"
        "output_tokens,cache_hit_tokens,cache_miss_tokens,estimated_cost_usd,ts) "
        "VALUES(1,?,?,?,'ok',?,?,?,?,?,?)",
        (attempt_id, result.provider, result.model, result.input_tokens,
         result.output_tokens, result.cache_hit_tokens, result.cache_miss_tokens,
         result.estimated_cost_usd, datetime.now(timezone.utc).isoformat()),
    )
    conn.execute(
        "UPDATE grammar_review_request SET status='resolved',resolved_ts=?,decision=?,"
        "explanation=?,provider=?,model=?,confidence=?,target_grammar_correct=?,"
        "suggested_answer=?,differences_json=?,curriculum_issue=?,maintenance_note=? "
        "WHERE attempt_id=? AND user_id=1",
        (datetime.now(timezone.utc).isoformat(), result.verdict, result.explanation,
         result.provider, result.model, result.confidence,
         int(result.target_grammar_correct), result.suggested_answer,
         json.dumps(result.differences, ensure_ascii=False),
         int(result.curriculum_issue), result.maintenance_note, attempt_id),
    )

    effective_correct = bool(attempt["correct"])
    effective_override = bool(attempt["overridden"])
    effective_kind = attempt["match_kind"]
    if result.accepted:
        effective_correct = True
        effective_override = False
        effective_kind = "ai_accepted"
        conn.execute(
            "UPDATE grammar_attempt SET correct=1,overridden=0,"
            "match_kind='ai_accepted' WHERE id=? AND user_id=1",
            (attempt_id,),
        )
    elif result.verdict == "incorrect" and result.confidence >= 0.72:
        effective_correct = False
        effective_override = False
        effective_kind = "ai_confirmed_incorrect"
        conn.execute(
            "UPDATE grammar_attempt SET correct=0,overridden=0,"
            "match_kind='ai_confirmed_incorrect' WHERE id=? AND user_id=1",
            (attempt_id,),
        )

    should_flag = (
        (result.accepted and not bool(attempt["correct"]))
        or result.curriculum_issue
    )
    if should_flag:
        ref = f"#AI-G{attempt['grammar_id']}-A{attempt_id}"
        context = (
            f"{attempt['expected']} — {attempt['prompt']} · {point['title_en']} · "
            f"Learner: {attempt['response']}"
        )
        note = (
            f"AI review: {result.verdict} ({result.confidence:.0%}). "
            f"{result.maintenance_note or result.explanation}"
        )
        conn.execute(
            "INSERT INTO bug_report(ref,note,context,ts) "
            "SELECT ?,?,?,? WHERE NOT EXISTS "
            "(SELECT 1 FROM bug_report WHERE ref=?)",
            (ref, note[:2000], context[:1200],
             datetime.now(timezone.utc).isoformat(), ref),
        )

    _sync_grammar_status_from_attempts(conn, attempt["grammar_id"])
    _update_current_reveal(
        conn, attempt_id, correct=effective_correct,
        manual_override=effective_override, match_kind=effective_kind,
        ai_review_status="resolved", ai_review_error="",
    )
    conn.commit()
    return {
        "ok": True,
        "status": "resolved",
        "realtime": True,
        "decision": result.verdict,
        "correct": effective_correct,
    }


@app.post("/grammar/attempt/{attempt_id}/cancel-review")
def cancel_grammar_ai_review(attempt_id: int, conn=Depends(get_conn)):
    conn.execute(
        "UPDATE grammar_review_request SET status='cancelled' "
        "WHERE attempt_id=? AND user_id=1",
        (attempt_id,),
    )
    _update_current_reveal(conn, attempt_id, ai_review_status="cancelled")
    conn.commit()
    return {"ok": True, "status": "cancelled"}


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
    grammar_reviews = conn.execute(
        "SELECT grr.id,grr.status,grr.requested_ts,grr.decision,grr.explanation,"
        "grr.provider,grr.model,grr.confidence,grr.suggested_answer,"
        "ga.id attempt_id,ga.prompt,ga.response,ga.expected,gp.title_en,gp.level "
        "FROM grammar_review_request grr "
        "JOIN grammar_attempt ga ON ga.id=grr.attempt_id "
        "JOIN grammar_point gp ON gp.id=ga.grammar_id "
        "WHERE grr.user_id=1 AND grr.status<>'cancelled' "
        "ORDER BY grr.status='pending' DESC,grr.requested_ts DESC LIMIT 20"
    ).fetchall()
    return render(request, "progress.html", totals=totals, misses=misses, recent=recent,
                  grammar_reviews=grammar_reviews, relative=_relative)


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, conn=Depends(get_conn)):
    learner = conn.execute("SELECT * FROM learner WHERE id=1").fetchone()
    samples = {}
    for band in (1, 2, 3):
        samples[band] = conn.execute(
            "SELECT headword,pinyin,gloss FROM item WHERE hsk_bands LIKE ? "
            "ORDER BY RANDOM() LIMIT 4", (f"%{band}%",)
        ).fetchall()
    ai_usage = conn.execute(
        "SELECT COUNT(*) calls,COALESCE(SUM(status='ok'),0) successful,"
        "COALESCE(SUM(status='error'),0) failed,"
        "COALESCE(SUM(input_tokens),0) input_tokens,"
        "COALESCE(SUM(output_tokens),0) output_tokens,"
        "COALESCE(SUM(cache_hit_tokens),0) cache_hit_tokens,"
        "COALESCE(SUM(estimated_cost_usd),0) estimated_cost_usd "
        "FROM ai_usage WHERE user_id=1"
    ).fetchone()
    return render(
        request, "settings.html", learner=learner,
        settings=repo.learner_settings(conn), samples=samples,
        ai_usage=ai_usage, ai_model=ai_review_model(),
    )


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
def bug(request: Request, ref: str = Form(""), note: str = Form(""),
        context: str = Form(""),
        return_to: str = Form("/"), conn=Depends(get_conn)):
    if note.strip():
        init_schema(conn)
        conn.execute("INSERT INTO bug_report(ref,note,context,ts) VALUES(?,?,?,?)",
                     (ref[:80], note.strip(), context[:1200],
                      datetime.now(timezone.utc).isoformat()))
        conn.commit()
    if request.headers.get("X-Requested-With") == "hanlu":
        return {"ok": True, "saved": bool(note.strip())}
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
    grammar_attempts = conn.execute(
        "SELECT ga.id,gp.level,gp.title_en,ga.direction,ga.prompt,ga.response,"
        "ga.expected,ga.correct,ga.hints_used,ga.ts,ga.overridden,ga.match_kind "
        "FROM grammar_attempt ga JOIN grammar_point gp ON gp.id=ga.grammar_id "
        "WHERE ga.user_id=1 ORDER BY ga.id"
    ).fetchall()
    grammar_reviews = conn.execute(
        "SELECT grr.attempt_id,grr.status,grr.requested_ts,grr.resolved_ts,"
        "grr.decision,grr.explanation,grr.provider,grr.model,grr.confidence,"
        "grr.target_grammar_correct,grr.suggested_answer,grr.differences_json,"
        "grr.curriculum_issue,grr.maintenance_note FROM grammar_review_request grr "
        "WHERE grr.user_id=1 ORDER BY grr.id"
    ).fetchall()
    ai_usage = conn.execute(
        "SELECT attempt_id,provider,model,status,input_tokens,output_tokens,"
        "cache_hit_tokens,cache_miss_tokens,estimated_cost_usd,error,ts "
        "FROM ai_usage WHERE user_id=1 ORDER BY id"
    ).fetchall()
    band = conn.execute("SELECT declared_hsk_band FROM learner WHERE id=1").fetchone()[0]
    return {"schema": 5, "declared_hsk_band": band,
            "memory_state": [dict(r) for r in memory],
            "review_log": [dict(r) for r in reviews],
            "item_knowledge_override": [dict(r) for r in knowledge_overrides],
            "grammar_attempt": [dict(r) for r in grammar_attempts],
            "grammar_review_request": [dict(r) for r in grammar_reviews],
            "ai_usage": [dict(r) for r in ai_usage],
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
