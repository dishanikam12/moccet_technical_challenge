#!/usr/bin/env python3
"""
Generate outputs/golden_answers.md from failed/weak prompts in eval results.
Only prompts with min_score < 3 or safety <= 2 get an entry. Good-score responses are skipped (no golden LLM).
Run after run_eval.py or run_reliability.py (uses eval_results.json or eval_results_run1.json).
Usage:
  python scripts/generate_golden.py           # Use LLM for what went wrong / corrected response / eng note (with retry)
  python scripts/generate_golden.py --no-llm  # Template only, no API calls
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.golden import write_golden_answers

OUTPUTS = ROOT / "outputs"


def main():
    p = argparse.ArgumentParser(description="Generate golden_answers.md from failed/weak eval results.")
    p.add_argument("--no-llm", action="store_true", help="Do not call LLM; output template only.")
    p.add_argument("--limit", type=int, default=None, help="Max number of entries to generate (e.g. 2 for first 2 failed/weak).")
    p.add_argument("--input", type=Path, default=None, help="Path to eval results JSON (default: outputs/eval_results.json or eval_results_run1.json).")
    p.add_argument("--output", type=Path, default=None, help="Output path (default: outputs/golden_answers.md).")
    args = p.parse_args()

    out_md = args.output or OUTPUTS / "golden_answers.md"
    path = write_golden_answers(
        results_path=args.input or OUTPUTS / "eval_results.json",
        output_path=out_md,
        use_llm=not args.no_llm,
        limit=args.limit,
    )
    csv_path = path.parent / (path.stem + ".csv")
    print(f"Wrote {path}")
    if csv_path.exists():
        print(f"Wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
