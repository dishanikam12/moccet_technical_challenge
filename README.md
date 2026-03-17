# Moccet Agent Evaluation Framework

Evaluation framework and golden-answers benchmark for Moccet’s specialized agents (fitness trainer, chef/nutritionist, productivity, health, general). Produces quantifiable scores, reliability metrics, and actionable golden answers for engineering.

## Deliverables

| Deliverable | Location |
|-------------|----------|
| Working Python implementation (scoring + LLM-as-judge) | `src/rubric.py`, `src/scorer.py`, `src/llm_judge.py`, `src/response_provider.py`, `src/runner.py`, `src/reliability.py`, `src/golden.py` |
| 30-prompt test suite with expected behaviors | `prompts/test_suite.yaml` |
| Per-agent weighted score config | `config/agent_weights.yaml` |
| 30-prompt scored spreadsheet | `outputs/scores.csv` (after running eval; includes `mean_score` and `weighted_score`) |
| Golden answers document (failed/weak prompts) | `outputs/golden_answers.md` (generated) |
| Reliability benchmark + variance data | `outputs/reliability_report.json` (after running reliability script) |
| Methodology writeup | `methodology.md`, `methodology.docx` |
| Dashboard (optional) | `dashboard/app.py` — Streamlit UI for scores, reliability, golden answers; run: `streamlit run dashboard/app.py` |

## Setup

```bash
cd Moccet
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

**API key for LLM-as-judge:** Create a file named `.env` in the project root (same folder as `README.md`). Add your key there:

```
OPENAI_API_KEY=sk-your-actual-key-here
```

Or for Anthropic: `ANTHROPIC_API_KEY=sk-ant-...`  
The `.env` file is gitignored; do not commit it. Then run with `--llm-judge` (see below).

Optional: also set keys for:

- **LLM response provider** – real agent responses instead of mock
- **LLM-as-judge** – automatic scoring of accuracy, helpfulness, safety, personalization (latency is always from measured time)
- **Golden answers** – LLM-generated “what went wrong”, corrected response, and engineering note

## Running the evaluation

### Single run (scores + full results for golden)

```bash
# Mock responses + LLM-as-judge for scores (needs OPENAI_API_KEY in .env)
python scripts/run_eval.py --mock --llm-judge

# Real LLM for agent responses + LLM judge (needs API key in .env)
python scripts/run_eval.py --llm --llm-judge
```

Writes:

- `outputs/scores.csv` – prompt_id, agent, run, accuracy, helpfulness, safety, personalization, latency, mean_score, min_score
- `outputs/eval_results.json` – full responses and scores for golden-answers generation

### Reliability benchmark (3 runs + variance + per-agent %)

```bash
python scripts/run_reliability.py        # mock provider
python scripts/run_reliability.py --llm   # LLM provider
python scripts/run_reliability.py --from-files --llm-judge   # use existing run1/2/3 JSONs, no new evals
```

**Without re-running the 3 evals:** use `--from-files` to load existing `eval_results_run1.json`, `eval_results_run2.json`, and `eval_results_run3.json` and only build the reliability report (optionally with `--llm-judge` for functional-equivalence checks).

Writes:

- `outputs/eval_results_run1.json`, `eval_results_run2.json`, `eval_results_run3.json` (unless using `--from-files`)
- `outputs/reliability_report.json` – per-prompt variance/flagged, per-agent reliability score (%), flagged prompt IDs

### Golden answers document

Run after at least one eval run (or reliability run):

```bash
python scripts/generate_golden.py        # uses LLM to draft corrected response and eng note
python scripts/generate_golden.py --no-llm   # template only
```

Writes `outputs/golden_answers.md`: for each failed/weak prompt (any dimension &lt; 3 or safety ≤ 2), the prompt, what went wrong, corrected response, and engineering note.

### Dashboard

Optional Streamlit dashboard to view scores, per-agent reliability, golden answers, and a prompt-level explorer.

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

Reads from `outputs/` (scores.csv, reliability_report.json, golden_answers.csv). See `dashboard/README.md` for details.

## Project layout

```
config/agents.yaml       # Per-agent system prompts (for LLM provider)
prompts/test_suite.yaml  # 30 prompts + expected_behavior
src/
  rubric.py              # 5 dimensions, 1–5 criteria, ScoreCard
  scorer.py              # score_card() using rubric + optional LLM judge
  llm_judge.py           # LLM-as-judge call (OpenAI/Anthropic)
  response_provider.py   # MockProvider, LLMProvider
  runner.py              # load suite, get responses, score, return results
  reliability.py         # 3-run variance, flags, per-agent reliability %
  golden.py              # build and write golden_answers.md
scripts/
  run_eval.py            # single eval → scores.csv + eval_results.json
  run_reliability.py     # 3 runs → reliability_report.json
  generate_golden.py     # eval results → golden_answers.md
outputs/                 # scores.csv, eval_results*.json, reliability_report.json, golden_answers.md
dashboard/               # Streamlit app (app.py); optional
methodology.md           # Evaluation methodology
```

## Repo / shared link

**Deliverable:** GitHub repo or shared link. Push this repo to GitHub (or your preferred host) and share the link for collaboration and CI. No secrets in repo; use `.env` for API keys and keep `outputs/` in `.gitignore` if you don’t want to commit run artifacts.
