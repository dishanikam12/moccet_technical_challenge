# Deliverables (excluding GitHub repo)

This folder contains the evaluation deliverables for the agent evaluation framework.

| File | Description |
|------|-------------|
| **rubric.py** | Rubric: 5 dimensions 1–5, ScoreCard, latency_seconds_to_score(), get_rubric_text_for_llm(), per-agent weights. `src/rubric.py`. |
| **scorer.py** | score_card(): prompt, response, expected_behavior, latency → ScoreCard. Uses rubric + optional LLM-as-judge. `src/scorer.py`. |
| **llm_judge.py** | LLM-as-judge: score_with_llm() returns 1–5 per dimension. `src/llm_judge.py`. |
| **runner.py** | run_eval(): load suite, get responses, score each via score_card(). `src/runner.py`. |
| **scores.csv** | 30-prompt scored spreadsheet: prompt_id, agent, dimensions, mean_score, weighted_score, min_score |
| **golden_answers.md** | Golden answers document (failed/weak prompts: what went wrong, corrected response, engineering note) |
| **golden_answers.csv** | Same content in CSV form |
| **reliability_report.json** | Reliability benchmark: per-prompt variance/flags, per-agent reliability %, flagged_prompt_ids |
| **test_suite.yaml** | 30-prompt test suite with expected behaviors |
| **agent_weights.yaml** | Per-agent weighted score config for weighted_score in scores.csv |
| **Methodology doc** | Added separately (e.g. methodology.md or methodology.docx) — evaluation methodology writeup. |

Note: The .py files use relative imports and are intended to be run as part of the full project from the repo root. They are included here as the Working Python implementation (scoring framework + LLM-as-judge).
