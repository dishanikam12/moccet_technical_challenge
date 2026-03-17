"""
Runner: load test suite, get responses from provider, score each, collect results.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .response_provider import ResponseProvider
from .rubric import ScoreCard
from .scorer import score_card

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_SUITE_PATH = PROJECT_ROOT / "prompts" / "test_suite.yaml"


def load_test_suite(path: Path = None) -> List[dict]:
    path = path or TEST_SUITE_PATH
    if not path.exists():
        return []
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    prompts = data.get("prompts") if isinstance(data, dict) else []
    return prompts or []


def run_eval(
    provider: ResponseProvider,
    test_suite_path: Path = None,
    use_llm_judge: bool = True,
    llm_provider: str = "openai",
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Load prompt suite, get response for each from provider, score with scorer.
    Returns list of dicts: card, response, prompt_id, agent, prompt, expected_behavior (for CSV and golden).
    If limit is set, only run the first limit prompts.
    """
    prompts = load_test_suite(test_suite_path)
    if limit is not None and limit > 0:
        prompts = prompts[:limit]
    results: List[Dict[str, Any]] = []
    for item in prompts:
        prompt_id = item.get("id", "")
        agent = item.get("agent", "general")
        prompt = item.get("prompt", "")
        expected = item.get("expected_behavior")
        if isinstance(expected, str):
            expected = [expected]
        expected = expected or []
        response_text, latency_seconds = provider.get_response(agent, prompt, prompt_id)
        card = score_card(
            prompt_id=prompt_id,
            agent=agent,
            prompt=prompt,
            response=response_text,
            expected_behavior=expected,
            latency_seconds=latency_seconds,
            use_llm_judge=use_llm_judge,
            llm_provider=llm_provider,
        )
        results.append({
            "card": card,
            "response": response_text,
            "prompt_id": prompt_id,
            "agent": agent,
            "prompt": prompt,
            "expected_behavior": expected,
        })
    return results
