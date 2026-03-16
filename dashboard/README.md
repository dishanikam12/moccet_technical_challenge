# Moccet Eval Dashboard

Streamlit dashboard to visualize eval scores, reliability, and golden answers.

## Run

From the **project root** (Moccet):

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

Or from this folder:

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app reads from `../outputs/` (scores.csv, reliability_report.json, golden_answers.csv). Generate those first with the main scripts (run_eval, run_reliability, generate_golden).

## Remove

To remove the dashboard entirely, delete the `dashboard/` folder. The rest of the project does not depend on it.
