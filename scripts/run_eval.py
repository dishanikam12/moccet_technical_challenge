#!/usr/bin/env python3
"""
Single evaluation run: get responses from provider -> score -> write outputs/scores.csv.
Default: no LLM-as-judge (latency + default 3s for other dimensions). Use --llm-judge to enable.
Usage:
  python scripts/run_eval.py                    # Mock provider, no judge (no API calls)
  python scripts/run_eval.py --mock             # Same
  python scripts/run_eval.py --llm              # Real LLM provider, no judge
  python scripts/run_eval.py --mock --llm-judge # Mock provider + LLM judge (needs API key)
"""

import argparse
import json
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.response_provider import MockProvider, LLMProvider, load_mock_responses
from src.runner import run_eval

OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)


def main():
    p = argparse.ArgumentParser(description="Run evaluation suite and write scores.")
    p.add_argument("--mock", action="store_true", help="Use mock response provider (no API calls for responses).")
    p.add_argument("--llm", action="store_true", help="Use LLM API for responses (requires OPENAI or ANTHROPIC key).")
    p.add_argument("--llm-judge", action="store_true", help="Use LLM-as-judge to score responses (requires API key). Default: off.")
    p.add_argument("--provider", choices=["openai", "anthropic"], default="openai", help="LLM provider for responses and judge.")
    p.add_argument("--run", type=int, default=1, help="Run id for CSV (e.g. 1, 2, 3 for reliability).")
    p.add_argument("--limit", type=int, default=None, help="Run only the first N prompts (e.g. 10 for a quick test).")
    p.add_argument("--golden-test", action="store_true", help="Merge bad mock responses (T1,T3,T5,C1,C3) so golden_answers.md gets entries.")
    args = p.parse_args()

    use_llm_provider = args.llm and not args.mock
    if use_llm_provider:
        provider = LLMProvider(provider=args.provider)
    else:
        canned = load_mock_responses(merge_bad=args.golden_test)
        provider = MockProvider(canned_responses=canned)
    use_llm_judge = args.llm_judge

    results = run_eval(
        provider=provider,
        use_llm_judge=use_llm_judge,
        llm_provider=args.provider,
        limit=args.limit,
    )

    rows = []
    for r in results:
        c = r["card"]
        rows.append({
            "prompt_id": c.prompt_id,
            "agent": c.agent,
            "prompt": r["prompt"][:200] + "..." if len(r["prompt"]) > 200 else r["prompt"],
            "run": args.run,
            "accuracy": c.accuracy,
            "helpfulness": c.helpfulness,
            "safety": c.safety,
            "personalization": c.personalization,
            "latency": c.latency,
            "mean_score": round(c.mean_score, 2),
            "weighted_score": round(c.weighted_score, 3),
            "min_score": c.min_score,
            "notes": c.notes,
        })
    df = pd.DataFrame(rows)
    out_csv = OUTPUTS / "scores.csv"
    if args.run != 1:
        out_csv = OUTPUTS / f"scores_run{args.run}.csv"
    df.to_csv(out_csv, index=False)
    print(f"Wrote {len(rows)} rows to {out_csv}")

    # Save full results (response text, expected_behavior) for golden answers
    full = []
    for r in results:
        c = r["card"]
        full.append({
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
    full_path = OUTPUTS / "eval_results.json"
    with open(full_path, "w") as f:
        json.dump(full, f, indent=2)
    print(f"Wrote full results to {full_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
