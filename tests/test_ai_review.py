from app.ai_review import (
    GRAMMAR_REVIEW_SYSTEM_PROMPT,
    _estimated_cost,
    _parse_result,
)


def test_parse_result_handles_fenced_json_and_string_booleans():
    parsed = _parse_result(
        """```json
        {
          "verdict": "acceptable",
          "target_grammar_correct": "false",
          "confidence": 2,
          "explanation": "",
          "suggested_answer": "妈妈今天没上班。",
          "differences": ["Natural vocabulary alternative."],
          "curriculum_issue": "true",
          "maintenance_note": "Accept 上班 here."
        }
        ```"""
    )
    assert parsed["verdict"] == "acceptable"
    assert parsed["target_grammar_correct"] is False
    assert parsed["confidence"] == 1
    assert parsed["explanation"] == "DeepSeek did not provide an explanation."
    assert parsed["curriculum_issue"] is True


def test_deepseek_flash_cost_uses_cache_and_output_rates():
    values = _estimated_cost(
        "deepseek-v4-flash",
        {
            "prompt_tokens": 600,
            "completion_tokens": 100,
            "prompt_cache_hit_tokens": 400,
            "prompt_cache_miss_tokens": 200,
        },
    )
    assert values[:4] == (600, 100, 400, 200)
    assert values[4] == (400 * 0.0028 + 200 * 0.14 + 100 * 0.28) / 1_000_000


def test_ai_prompt_respects_curriculum_order_and_target_grammar():
    assert "current tested grammar pattern is decisive" in (
        GRAMMAR_REVIEW_SYSTEM_PROMPT
    )
    assert "Never require a later or unintroduced structure" in (
        GRAMMAR_REVIEW_SYSTEM_PROMPT
    )
    assert "他/她/它 mismatch" in GRAMMAR_REVIEW_SYSTEM_PROMPT
    assert "我知道在哪里找到她 is natural without 能" in (
        GRAMMAR_REVIEW_SYSTEM_PROMPT
    )
