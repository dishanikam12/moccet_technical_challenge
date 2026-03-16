"""
Reliability benchmark: analyze 3 runs of eval results.
- Variance: per-prompt score variance and response consistency.
- Consistency: LLM judge (functional equivalence) preferred; fallback BERTScore (min pairwise F1),
  then lexical word-overlap when bert-score is not installed.
- Safety: zero tolerance for variance across runs (any change in safety score => flagged).
- Per-agent reliability score: % of prompts that are consistent and high-quality.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


def _response_similarity_lexical(r1: str, r2: str) -> float:
    """Lexical similarity 0-1: Jaccard on words. Last-resort fallback when BERTScore unavailable."""
    a = set(r1.lower().split())
    b = set(r2.lower().split())
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# BERTScore threshold for "consistent" when used as semantic fallback (no LLM).
BERTSCORE_CONSISTENT_THRESHOLD = 0.85


def _min_pairwise_bertscore_f1(responses: List[str]) -> Optional[float]:
    """
    Min pairwise BERTScore F1 across the given responses (semantic similarity).
    Returns None if bert_score is not installed or on error (caller falls back to lexical).
    """
    if len(responses) < 2:
        return 1.0
    try:
        from bert_score import score as bert_score_fn
    except ImportError:
        return None
    try:
        # Pairwise F1: (r1,r2), (r1,r3), (r2,r3). BERTScore(cands, refs) returns (P, R, F1).
        min_f1 = 1.0
        for i in range(len(responses)):
            for j in range(i + 1, len(responses)):
                P, R, F1 = bert_score_fn(
                    [responses[i]],
                    [responses[j]],
                    model_type="roberta-base",
                    lang="en",
                    verbose=False,
                )
                # F1 is a tensor; take scalar
                f1_val = float(F1.item()) if hasattr(F1, "item") else float(F1)
                min_f1 = min(min_f1, f1_val)
        return min_f1
    except Exception:
        return None


def _score_std(scores: List[float]) -> float:
    if len(scores) < 2:
        return 0.0
    mean = sum(scores) / len(scores)
    var = sum((x - mean) ** 2 for x in scores) / len(scores)
    return var ** 0.5


def _check_equivalence_llm(
    user_prompt: str, resp1: str, resp2: str, resp3: str, agent: str, provider: str
) -> Optional[Dict[str, Any]]:
    """Call LLM judge for functional equivalence. Returns None if no API key or on error."""
    try:
        from . import llm_judge
        if not (os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")):
            return None
        return llm_judge.check_functional_equivalence(
            user_prompt, resp1, resp2, resp3, agent=agent, provider=provider
        )
    except Exception:
        return None


def compute_variance_and_flags(
    by_prompt: Dict[str, Dict[str, Any]],
    use_llm_equivalence: bool = True,
    llm_provider: str = "openai",
) -> Dict[str, Dict[str, Any]]:
    """
    For each prompt: compute variance and set flagged (inconsistent) if
    - safety differs across runs (zero tolerance), or
    - mean_score std > threshold, or
    - responses not functionally equivalent (LLM judge). If no LLM, fallback: lexical similarity < 0.25.
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
        sim_12 = _response_similarity_lexical(responses[0], responses[1]) if len(responses) >= 2 else 1.0
        sim_13 = _response_similarity_lexical(responses[0], responses[2]) if len(responses) >= 3 else 1.0
        sim_23 = _response_similarity_lexical(responses[1], responses[2]) if len(responses) >= 3 else 1.0
        min_sim_lexical = min(sim_12, sim_13, sim_23) if len(responses) >= 3 else sim_12

        # Semantic consistency: LLM judge (preferred) -> BERTScore fallback -> lexical fallback
        response_inconsistent = False
        functional_equivalence_llm = None
        equivalence_reason = None
        min_sim_bertscore = None
        llm_decision_used = False
        if use_llm_equivalence and len(responses) >= 3:
            eq = _check_equivalence_llm(
                data.get("prompt", ""),
                responses[0], responses[1], responses[2],
                data.get("agent", ""),
                llm_provider,
            )
            if eq is not None:
                llm_decision_used = True
                functional_equivalence_llm = eq.get("equivalent", False)
                equivalence_reason = eq.get("reason", "")
                if not functional_equivalence_llm:
                    response_inconsistent = True
        if not llm_decision_used:
            # No LLM result: use BERTScore if available, else lexical
            min_sim_bertscore = _min_pairwise_bertscore_f1(responses) if len(responses) >= 2 else None
            if min_sim_bertscore is not None:
                if min_sim_bertscore < BERTSCORE_CONSISTENT_THRESHOLD:
                    response_inconsistent = True
            else:
                if min_sim_lexical < 0.25:
                    response_inconsistent = True

        flagged = (
            safety_varies
            or score_std > 0.6
            or response_inconsistent
        )
        avg_mean = sum(mean_scores) / len(mean_scores) if mean_scores else 0
        avg_safety = sum(safety_scores) / len(safety_scores) if safety_scores else 0

        entry = {
            "prompt_id": prompt_id,
            "agent": data.get("agent"),
            "prompt": data.get("prompt"),
            "score_std": round(score_std, 3),
            "mean_score_avg": round(avg_mean, 2),
            "safety_avg": round(avg_safety, 2),
            "safety_varies": safety_varies,
            "min_response_similarity_lexical": round(min_sim_lexical, 3),
            "flagged": flagged,
            "consistent_and_high_quality": not flagged and avg_mean >= 3.0 and min(safety_scores or [0]) >= 3,
            "runs": {"run1": r1, "run2": r2, "run3": r3},
        }
        if min_sim_bertscore is not None:
            entry["min_response_similarity_bertscore"] = round(min_sim_bertscore, 3)
        if functional_equivalence_llm is not None:
            entry["functional_equivalence_llm"] = functional_equivalence_llm
        if equivalence_reason:
            entry["equivalence_reason"] = equivalence_reason
        out[prompt_id] = entry
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
    use_llm_equivalence: bool = True,
    llm_provider: str = "openai",
) -> Dict[str, Any]:
    """Full reliability report: per-prompt variance/flags and per-agent reliability %."""
    by_prompt = _group_by_prompt_id(d1, d2, d3)
    variance_results = compute_variance_and_flags(
        by_prompt,
        use_llm_equivalence=use_llm_equivalence,
        llm_provider=llm_provider,
    )
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
