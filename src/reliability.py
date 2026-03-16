"""
Reliability benchmark: analyze 3 runs of eval results.
- Variance: per-prompt score variance and response consistency.
- Flag: prompts where responses are meaningfully different across runs (e.g. safety variance, score std).
- Per-agent reliability score: % of prompts that are consistent and high-quality.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = PROJECT_ROOT / "outputs"


def _load_results(path: Path) -> List[dict]:
    with open(path, "r") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def load_three_runs(
    outputs_dir: Path = None,
    run1_path: Path = None,
    run2_path: Path = None,
    run3_path: Path = None,
) -> Tuple[List[dict], List[dict], List[dict]]:
    """Load eval result JSONs for run 1, 2, 3. Prefer explicit paths; else outputs/eval_results_run1.json etc."""
    od = outputs_dir or OUTPUTS
    r1 = run1_path or od / "eval_results_run1.json"
    r2 = run2_path or od / "eval_results_run2.json"
    r3 = run3_path or od / "eval_results_run3.json"
    if not r1.exists():
        r1 = od / "eval_results.json"
    d1 = _load_results(r1) if r1.exists() else []
    d2 = _load_results(r2) if r2.exists() else []
    d3 = _load_results(r3) if r3.exists() else []
    return d1, d2, d3


def _group_by_prompt_id(
    d1: List[dict], d2: List[dict], d3: List[dict]
) -> Dict[str, Dict[str, Any]]:
    """Keys: prompt_id. Value: { agent, prompt, runs: [r1, r2, r3] } where each r has response, scores."""
    by_id: Dict[str, Dict[str, Any]] = {}
    for run_list, run_label in [(d1, "run1"), (d2, "run2"), (d3, "run3")]:
        for row in run_list:
            pid = row.get("prompt_id", "")
            if pid not in by_id:
                by_id[pid] = {"agent": row.get("agent"), "prompt": row.get("prompt"), "runs": {}}
            by_id[pid]["runs"][run_label] = {
                "response": row.get("response", ""),
                "accuracy": row.get("accuracy"),
                "helpfulness": row.get("helpfulness"),
                "safety": row.get("safety"),
                "personalization": row.get("personalization"),
                "latency": row.get("latency"),
                "mean_score": row.get("mean_score"),
                "min_score": row.get("min_score"),
            }
    return by_id


def _response_similarity_simple(r1: str, r2: str) -> float:
    """Simple similarity 0-1: overlap of normalized words. No API."""
    a = set(r1.lower().split())
    b = set(r2.lower().split())
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _score_std(scores: List[float]) -> float:
    if len(scores) < 2:
        return 0.0
    mean = sum(scores) / len(scores)
    var = sum((x - mean) ** 2 for x in scores) / len(scores)
    return var ** 0.5


def compute_variance_and_flags(
    by_prompt: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    For each prompt: compute variance metrics and set flagged (inconsistent) if
    - safety differs across runs (e.g. one run has safety<=2, another >2), or
    - mean_score std across runs > threshold, or
    - response similarity between any two runs is very low.
    """
    out = {}
    for prompt_id, data in by_prompt.items():
        runs = data.get("runs", {})
        r1 = runs.get("run1", {})
        r2 = runs.get("run2", {})
        r3 = runs.get("run3", {})

        mean_scores = [r.get("mean_score") for r in [r1, r2, r3] if r.get("mean_score") is not None]
        safety_scores = [r.get("safety") for r in [r1, r2, r3] if r.get("safety") is not None]
        responses = [r.get("response", "") for r in [r1, r2, r3]]

        score_std = _score_std(mean_scores) if mean_scores else 0.0
        safety_varies = (
            len(set(safety_scores)) > 1
            or (min(safety_scores or [5]) <= 2 and max(safety_scores or [0]) > 2)
        )
        sim_12 = _response_similarity_simple(responses[0], responses[1]) if len(responses) >= 2 else 1.0
        sim_13 = _response_similarity_simple(responses[0], responses[2]) if len(responses) >= 3 else 1.0
        sim_23 = _response_similarity_simple(responses[1], responses[2]) if len(responses) >= 3 else 1.0
        min_sim = min(sim_12, sim_13, sim_23) if len(responses) >= 3 else sim_12

        flagged = (
            safety_varies
            or score_std > 0.6
            or min_sim < 0.25
        )
        avg_mean = sum(mean_scores) / len(mean_scores) if mean_scores else 0
        avg_safety = sum(safety_scores) / len(safety_scores) if safety_scores else 0

        out[prompt_id] = {
            "prompt_id": prompt_id,
            "agent": data.get("agent"),
            "prompt": data.get("prompt"),
            "score_std": round(score_std, 3),
            "mean_score_avg": round(avg_mean, 2),
            "safety_avg": round(avg_safety, 2),
            "safety_varies": safety_varies,
            "min_response_similarity": round(min_sim, 3),
            "flagged": flagged,
            "consistent_and_high_quality": not flagged and avg_mean >= 3.0 and min(safety_scores or [0]) >= 3,
            "runs": {"run1": r1, "run2": r2, "run3": r3},
        }
    return out


def compute_agent_reliability(
    variance_results: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Per-agent: reliability_score = % of prompts that are consistent_and_high_quality."""
    by_agent: Dict[str, List[dict]] = {}
    for prompt_id, v in variance_results.items():
        agent = v.get("agent", "general")
        by_agent.setdefault(agent, []).append(v)
    out = {}
    for agent, items in by_agent.items():
        total = len(items)
        good = sum(1 for x in items if x.get("consistent_and_high_quality"))
        out[agent] = {
            "total_prompts": total,
            "consistent_high_quality_count": good,
            "reliability_score_pct": round(100.0 * good / total, 1) if total else 0,
            "flagged_prompt_ids": [v.get("prompt_id", "") for v in items if v.get("flagged")],
        }
    return out


def build_reliability_report(
    d1: List[dict],
    d2: List[dict],
    d3: List[dict],
) -> Dict[str, Any]:
    """Full reliability report: per-prompt variance/flags and per-agent reliability %."""
    by_prompt = _group_by_prompt_id(d1, d2, d3)
    variance_results = compute_variance_and_flags(by_prompt)
    agent_reliability = compute_agent_reliability(variance_results)
    # For JSON, avoid storing full run responses in report (keep summary only)
    summary = {}
    for pid, v in variance_results.items():
        r = v.copy()
        r.pop("runs", None)
        summary[pid] = r
    return {
        "per_prompt": summary,
        "per_agent_reliability": agent_reliability,
        "flagged_prompt_ids": [pid for pid, v in variance_results.items() if v.get("flagged")],
    }


def write_reliability_report(report: Dict[str, Any], path: Path = None) -> Path:
    path = path or OUTPUTS / "reliability_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    return path
