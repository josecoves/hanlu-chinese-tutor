"""Provider-neutral AI second opinions for grammar attempts."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import httpx


VERDICTS = {"correct", "acceptable", "incorrect", "uncertain"}
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_BASE_URL = "https://api.deepseek.com"
GRAMMAR_REVIEW_SYSTEM_PROMPT = """You are a careful Mandarin Chinese teacher grading one exercise.
The current tested grammar pattern is decisive. If the learner does not
demonstrate that pattern, grade the answer incorrect even when the rest is
natural. Judge earlier, already introduced grammar normally.

First check whether the model answer itself clearly demonstrates the tested
pattern. If it does not, set curriculum_issue to true. In that situation do
not penalize the learner merely for also omitting the pattern; judge whether
their Chinese is a reasonable translation and use uncertain rather than
incorrect when the broken exercise prevents a fair target-grammar judgment.

Never require a later or unintroduced structure merely because it appears in
the model answer. If the learner gives a natural simpler sentence that
demonstrates the current pattern, accept it and set curriculum_issue to true
when the model answer unnecessarily depends on later grammar.

Judge the target separately from incidental vocabulary, register, punctuation,
and equally natural wording. Accept valid regional, formal, informal,
singular/plural, and omitted-subject forms when they preserve the target.
Accept a natural near-synonym for incidental vocabulary when it preserves the
prompt's practical meaning and does not replace the grammar being tested. Give
the more precise model wording as feedback, but do not call that vocabulary
choice a grammar error. For example, a reasonable class/school or work/job
wording difference is feedback unless that distinction is the lesson target.
Treat a written 他/她/它 mismatch as useful feedback, but do not let it override
a correct target-grammar judgment. If English remains only where incidental
vocabulary is missing, judge the Chinese grammar that is present. Do not invent
extra requirements: for example, 我知道在哪里找到她 is natural without 能 or 可以.
Do not demand grammar above the stated HSK level.

Explain briefly in learner-friendly English and use Chinese examples when
helpful.

Return JSON only in exactly this shape:
{
  "verdict": "correct|acceptable|incorrect|uncertain",
  "target_grammar_correct": true,
  "confidence": 0.0,
  "explanation": "short explanation",
  "suggested_answer": "natural Chinese answer",
  "differences": ["one meaningful difference"],
  "curriculum_issue": false,
  "maintenance_note": "what the deterministic exercise or grader should change"
}"""


class AIReviewError(RuntimeError):
    """A safe, user-presentable AI review failure."""


@dataclass(frozen=True)
class AIReviewResult:
    verdict: str
    target_grammar_correct: bool
    confidence: float
    explanation: str
    suggested_answer: str
    differences: tuple[str, ...]
    curriculum_issue: bool
    maintenance_note: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_hit_tokens: int
    cache_miss_tokens: int
    estimated_cost_usd: float

    @property
    def accepted(self) -> bool:
        return (
            self.verdict in {"correct", "acceptable"}
            and self.target_grammar_correct
            and self.confidence >= 0.72
        )


def ai_review_configured() -> bool:
    return bool(os.getenv("DEEPSEEK_API_KEY", "").strip())


def ai_review_model() -> str:
    return os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _clean_text(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def _parse_result(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = content.removeprefix("```json").removeprefix("```")
        content = content.removesuffix("```").strip()
    try:
        payload = json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise AIReviewError("DeepSeek returned an unreadable review.") from exc
    if not isinstance(payload, dict):
        raise AIReviewError("DeepSeek returned an unreadable review.")
    verdict = str(payload.get("verdict", "uncertain")).lower()
    if verdict not in VERDICTS:
        verdict = "uncertain"
    try:
        confidence = float(payload.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0
    differences = payload.get("differences", [])
    if not isinstance(differences, list):
        differences = []
    return {
        "verdict": verdict,
        "target_grammar_correct": _as_bool(
            payload.get("target_grammar_correct", False)
        ),
        "confidence": min(1.0, max(0.0, confidence)),
        "explanation": (
            _clean_text(payload.get("explanation"), 2400)
            or "DeepSeek did not provide an explanation."
        ),
        "suggested_answer": _clean_text(payload.get("suggested_answer"), 400),
        "differences": tuple(
            _clean_text(item, 400) for item in differences[:5] if str(item).strip()
        ),
        "curriculum_issue": _as_bool(payload.get("curriculum_issue", False)),
        "maintenance_note": _clean_text(payload.get("maintenance_note"), 1200),
    }


def _estimated_cost(model: str, usage: dict) -> tuple[int, int, int, int, float]:
    input_tokens = int(usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or 0)
    hit_tokens = int(usage.get("prompt_cache_hit_tokens") or 0)
    miss_tokens = int(
        usage.get("prompt_cache_miss_tokens")
        if usage.get("prompt_cache_miss_tokens") is not None
        else max(0, input_tokens - hit_tokens)
    )
    rates = {
        "deepseek-v4-flash": (0.0028, 0.14, 0.28),
        "deepseek-v4-pro": (0.003625, 0.435, 0.87),
    }
    cache_rate, input_rate, output_rate = rates.get(model, (0, 0, 0))
    cost = (
        hit_tokens * cache_rate
        + miss_tokens * input_rate
        + output_tokens * output_rate
    ) / 1_000_000
    return input_tokens, output_tokens, hit_tokens, miss_tokens, cost


def review_grammar_attempt(attempt: dict, point: dict) -> AIReviewResult:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise AIReviewError("DeepSeek is not configured yet.")
    model = ai_review_model()
    base_url = (
        os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).strip()
        or DEFAULT_BASE_URL
    ).rstrip("/")
    endpoint = f"{base_url}/chat/completions"
    exercise = {
        "hsk_level": point["level"],
        "lesson": point["title_en"],
        "lesson_chinese": point["title_zh"],
        "tested_pattern": point["pattern"],
        "lesson_explanation": point["explanation"],
        "direction": attempt["direction"],
        "prompt": attempt["prompt"],
        "learner_answer": attempt["response"],
        "model_answer": attempt["expected"],
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": GRAMMAR_REVIEW_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "Grade this exercise and return the requested JSON:\n"
                + json.dumps(exercise, ensure_ascii=False),
            },
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "max_tokens": 800,
        "stream": False,
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(35.0, connect=8.0)) as client:
            response = client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            response.raise_for_status()
            api_payload = response.json()
        content = api_payload["choices"][0]["message"]["content"]
        parsed = _parse_result(content)
        token_values = _estimated_cost(model, api_payload.get("usage") or {})
    except AIReviewError:
        raise
    except httpx.TimeoutException as exc:
        raise AIReviewError(
            "DeepSeek took too long. This answer was saved for later review."
        ) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 401:
            message = "DeepSeek rejected the local API key."
        elif status == 402:
            message = "The DeepSeek account needs more API credit."
        elif status == 429:
            message = "DeepSeek is busy. This answer was saved for later review."
        else:
            message = "DeepSeek could not review this answer right now."
        raise AIReviewError(message) from exc
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AIReviewError("DeepSeek returned an unreadable review.") from exc
    return AIReviewResult(
        **parsed,
        provider="deepseek",
        model=model,
        input_tokens=token_values[0],
        output_tokens=token_values[1],
        cache_hit_tokens=token_values[2],
        cache_miss_tokens=token_values[3],
        estimated_cost_usd=token_values[4],
    )
