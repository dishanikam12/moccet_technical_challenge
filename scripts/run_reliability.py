#!/usr/bin/env python3
"""
Reliability benchmark: run evaluation 3 times, then compute variance and per-agent reliability.
Writes outputs/eval_results_run1.json, run2, run3 and outputs/reliability_report.json.
Usage:
  python scripts/run_reliability.py              # Mock provider
  python scripts/run_reliability.py --llm       # LLM provider (requires API key)
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.response_provider import MockProvider, LLMProvider, load_mock_responses
from src.runner import run_eval
from src.reliability import build_reliability_report, write_reliability_report

OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)


def _results_to_save_format(results: list) -> list:
    """Convert runner output to same format as run_eval.py full results (for reliability loader)."""
    out = []
    for r in results:
        c = r["card"]
        out.append({
            "prompt_id": c.prompt_id,
            "agent": c.agent,
            "prompt": r["prompt"],
            "response": r["response"],
            "expected_behavior": r["expected_behavior"],
            "accuracy": c.accuracy,
            "helpfulness": c.helpfulness,
            "safety": c.safety,
            "personalization": c.personalization,
            "latency": c.latency,
            "mean_score": round(c.mean_score, 2),
            "weighted_score": round(c.weighted_score, 3),
            "min_score": c.min_score,
        })
    return out


def main():
    p = argparse.ArgumentParser(description="Run reliability benchmark (3 runs, variance, per-agent %).")
    p.add_argument("--mock", action="store_true", help="Use mock provider.")
    p.add_argument("--llm", action="store_true", help="Use LLM provider (real agent for responses).")
    p.add_argument("--llm-judge", action="store_true", help="Use LLM-as-judge to score responses (requires API key). Default: off.")
    p.add_argument("--provider", choices=["openai", "anthropic"], default="openai")
    args = p.parse_args()

    use_llm = args.llm and not args.mock
    if use_llm:
        provider = LLMProvider(provider=args.provider)
    else:
        canned = load_mock_responses()
        provider = MockProvider(canned_responses=canned)
    use_llm_judge = args.llm_judge

    run_results = []
    for run_id in (1, 2, 3):
        results = run_eval(
            provider=provider,
            use_llm_judge=use_llm_judge,
            llm_provider=args.provider,
        )
        to_save = _results_to_save_format(results)
        path = OUTPUTS / f"eval_results_run{run_id}.json"
        with open(path, "w") as f:
            json.dump(to_save, f, indent=2)
        print(f"Run {run_id}: wrote {path}")
        run_results.append(to_save)

    report = build_reliability_report(run_results[0], run_results[1], run_results[2])
    out_path = write_reliability_report(report)
    print(f"Wrote {out_path}")

    print("\nPer-agent reliability score (% of prompts consistent and high-quality):")
    for agent, data in report.get("per_agent_reliability", {}).items():
        print(f"  {agent}: {data['reliability_score_pct']}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
