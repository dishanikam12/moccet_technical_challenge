"""
Scorer: given prompt, response, expected_behavior, and latency, produce a structured ScoreCard.
Supports LLM-as-judge (default when API key available) or human-only (latency only; other dims optional).
"""

from typing import Any, Dict, List, Optional

from .rubric import (
    ScoreCard,
    latency_seconds_to_score,
)
from . import llm_judge as judge_module


def score_card(
    prompt_id: str,
    agent: str,
    prompt: str,
    response: str,
    expected_behavior: List[str],
    latency_seconds: float,
    use_llm_judge: bool = True,
    llm_provider: str = "openai",
) -> ScoreCard:
    """
    Produce a ScoreCard for one (prompt, response) pair.
    - latency_seconds is always used to set the latency dimension objectively.
    - If use_llm_judge is True and API key is available, accuracy/helpfulness/safety/personalization
      come from the LLM judge; otherwise they default to 3 (neutral) and notes suggest human review.
    """
    latency_score = latency_seconds_to_score(latency_seconds)
    notes = ""

    if use_llm_judge:
        try:
            result = judge_module.score_with_llm(
                prompt=prompt,
                response=response,
                expected_behavior=expected_behavior,
                prompt_id=prompt_id,
                agent=agent,
                latency_seconds=latency_seconds,
                provider=llm_provider,
            )
            scores = result["scores"]
            notes = result.get("notes", "")
            return ScoreCard(
                prompt_id=prompt_id,
                agent=agent,
                accuracy=scores["accuracy"],
                helpfulness=scores["helpfulness"],
                safety=scores["safety"],
                personalization=scores["personalization"],
                latency=scores["latency"],
                notes=notes,
            )
        except Exception as e:
            notes = f"LLM judge failed: {e}; using latency-only scores."
            use_llm_judge = False

    if not use_llm_judge:
        return ScoreCard(
            prompt_id=prompt_id,
            agent=agent,
            accuracy=3,
            helpfulness=3,
            safety=3,
            personalization=3,
            latency=latency_score,
            notes=notes or "Human review recommended; LLM judge not used.",
        )
    # unreachable
    return ScoreCard(
        prompt_id=prompt_id,
        agent=agent,
        accuracy=3,
        helpfulness=3,
        safety=3,
        personalization=3,
        latency=latency_score,
        notes=notes,
    )
