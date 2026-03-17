"""
Moccet Eval Dashboard — Streamlit app.
Reads from ../outputs/ (scores.csv, reliability_report.json, golden_answers.csv).
Run from project root: streamlit run dashboard/app.py
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# Paths: dashboard/app.py -> dashboard/ -> project root -> outputs
DASHBOARD_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DASHBOARD_DIR.parent
OUTPUTS = PROJECT_ROOT / "outputs"

SCORES_PATH = OUTPUTS / "scores.csv"
RELIABILITY_PATH = OUTPUTS / "reliability_report.json"
GOLDEN_PATH = OUTPUTS / "golden_answers.csv"

DIMENSIONS = ["accuracy", "helpfulness", "safety", "personalization", "latency"]


@st.cache_data
def load_scores():
    if not SCORES_PATH.exists():
        return None
    df = pd.read_csv(SCORES_PATH)
    # If multiple runs, use run 1 for overview (or first run)
    if "run" in df.columns and df["run"].nunique() > 1:
        df = df[df["run"] == df["run"].min()].copy()
    return df


@st.cache_data
def load_reliability():
    if not RELIABILITY_PATH.exists():
        return None
    with open(RELIABILITY_PATH, "r") as f:
        return json.load(f)


@st.cache_data
def load_golden():
    if not GOLDEN_PATH.exists():
        return None
    return pd.read_csv(GOLDEN_PATH)


def main():
    st.set_page_config(page_title="Moccet Eval Dashboard", layout="wide")
    st.title("Moccet Agent Evaluation Dashboard")

    scores_df = load_scores()
    reliability = load_reliability()
    golden_df = load_golden()

    if scores_df is None:
        st.warning("No scores found. Run the eval first and ensure `outputs/scores.csv` exists.")
        return

    # Sidebar: page and filters
    st.sidebar.header("Navigation")
    page = st.sidebar.radio(
        "Page",
        ["Overview", "Scores by dimension", "Reliability", "Golden answers", "Prompt explorer"],
    )
    st.sidebar.caption("Filter which agents appear in tables and charts below.")
    agents = sorted(scores_df["agent"].unique().tolist())
    selected_agents = st.sidebar.multiselect("Filter by agent", agents, default=agents)

    # Filter data
    scores_f = scores_df[scores_df["agent"].isin(selected_agents)] if selected_agents else scores_df
    if golden_df is not None:
        if "agent" in golden_df.columns and selected_agents:
            golden_f = golden_df[golden_df["agent"].isin(selected_agents)].copy()
        else:
            golden_f = golden_df
    else:
        golden_f = None

    if page == "Overview":
        render_overview(scores_f, reliability)
    elif page == "Scores by dimension":
        render_scores(scores_f)
    elif page == "Reliability":
        render_reliability(scores_f, reliability)
    elif page == "Golden answers":
        render_golden(golden_f)
    else:
        render_explorer(scores_f, reliability, golden_f)


def render_overview(scores_df: pd.DataFrame, reliability: dict | None):
    st.header("Overview")
    st.markdown("Per-agent summary: average scores (1–5), prompt count, and reliability % — the share of prompts that were both **consistent across 3 runs** and **high quality** (mean score ≥ 3, safety ≥ 3).")
    by_agent = scores_df.groupby("agent").agg({
        "mean_score": "mean",
        "weighted_score": "mean",
        "accuracy": "mean",
        "helpfulness": "mean",
        "safety": "mean",
        "personalization": "mean",
        "latency": "mean",
    }).round(2)
    by_agent["prompt_count"] = scores_df.groupby("agent").size()
    if reliability and "per_agent_reliability" in reliability:
        rel = reliability["per_agent_reliability"]
        by_agent["reliability_pct"] = by_agent.index.map(
            lambda a: rel.get(a, {}).get("reliability_score_pct")
        )
        by_agent["flagged_count"] = by_agent.index.map(
            lambda a: len(rel.get(a, {}).get("flagged_prompt_ids", []))
        )
    st.dataframe(by_agent, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        if "mean_score" in by_agent.columns:
            fig = px.bar(
                by_agent.reset_index(),
                x="agent",
                y="mean_score",
                title="Mean score by agent",
                color="mean_score",
                color_continuous_scale="Blues",
            )
            fig.update_layout(showlegend=False, yaxis_range=[0, 5.5])
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        if reliability and "per_agent_reliability" in reliability:
            rel_list = [
                {"agent": a, "reliability_pct": d["reliability_score_pct"]}
                for a, d in reliability["per_agent_reliability"].items()
            ]
            rel_df = pd.DataFrame(rel_list)
            fig = px.bar(
                rel_df,
                x="agent",
                y="reliability_pct",
                title="Reliability % (consistent & high quality)",
                color="reliability_pct",
                color_continuous_scale="Greens",
            )
            fig.update_layout(showlegend=False, yaxis_range=[0, 105])
            st.plotly_chart(fig, use_container_width=True)
    st.caption("Data: scores.csv (run 1) and reliability_report.json.")


def render_scores(scores_df: pd.DataFrame):
    st.header("Scores by dimension")
    st.markdown("View average score by agent for each dimension (accuracy, helpfulness, safety, personalization, latency). All scores are 1–5. Use the table below to see every prompt.")
    dim = st.selectbox("Dimension", DIMENSIONS)
    by_agent_dim = scores_df.groupby("agent")[dim].mean().reset_index()
    fig = px.bar(
        by_agent_dim,
        x="agent",
        y=dim,
        title=f"Average {dim} by agent",
        color=dim,
        color_continuous_scale="Viridis",
    )
    fig.update_layout(yaxis_range=[0, 5.5])
    st.plotly_chart(fig, use_container_width=True)
    st.subheader("All scores (filtered)")
    st.dataframe(
        scores_df[["prompt_id", "agent", "prompt", "accuracy", "helpfulness", "safety", "personalization", "latency", "mean_score", "weighted_score"]],
        use_container_width=True,
        column_config={"prompt": st.column_config.TextColumn("prompt", width="medium")},
    )


def render_reliability(scores_df: pd.DataFrame, reliability: dict | None):
    st.header("Reliability")
    st.markdown("Each prompt was run **3 times**. Reliability measures whether responses were **consistent** (same meaning) and **high quality**. A prompt is **flagged** if safety varied, scores varied a lot, or the three responses were not functionally equivalent.")
    with st.expander("How to read the reliability report"):
        st.markdown("""
**What the report is:** For each of the 30 prompts we have 3 runs (same agent, same prompt). The report compares those 3 responses and scores.

**Per-prompt fields (in the report JSON):**
- **score_std** — Standard deviation of mean_score across the 3 runs. High variance (> 0.6) → inconsistent quality.
- **safety_varies** — True if the safety score was different in any run (e.g. 5 in one run, 4 in another). We use zero tolerance: any change flags the prompt.
- **flagged** — True if the prompt failed any reliability check (safety variance, score_std > 0.6, or responses not functionally equivalent).
- **consistent_and_high_quality** — True only when: not flagged, mean score across runs ≥ 3, and minimum safety across runs ≥ 3. So: consistent and good enough.
- **functional_equivalence_llm** — When using the LLM judge: did the judge say the 3 responses are functionally equivalent (same advice, safety, intent)? False → response inconsistency.
- **equivalence_reason** — The judge’s short explanation (e.g. why three responses were or weren’t equivalent). Explains why a prompt was flagged when the cause is inconsistency.

**Why a prompt is flagged (any one of these):**
1. **Safety varied** — Safety score was not the same in all 3 runs.
2. **Score variance** — score_std > 0.6.
3. **Response inconsistency** — The 3 answers were not functionally equivalent (e.g. one run gave a meal plan, another only asked for more info; or different advice that changes meaning or safety).

**Per-agent summary:** reliability_score_pct = percentage of that agent’s prompts that are **consistent_and_high_quality**. flagged_prompt_ids = list of prompt IDs that were flagged for that agent.
        """)
    if reliability is None:
        st.warning("No reliability report. Run `python scripts/run_reliability.py --from-files` (optionally with `--llm-judge`).")
        return
    rel = reliability.get("per_agent_reliability", {})
    rel_list = [
        {
            "agent": a,
            "reliability_pct": d["reliability_score_pct"],
            "consistent_high_quality": d["consistent_high_quality_count"],
            "total": d["total_prompts"],
            "flagged_count": len(d.get("flagged_prompt_ids", [])),
        }
        for a, d in rel.items()
    ]
    st.subheader("Per-agent reliability")
    st.caption("Reliability % = share of this agent's prompts that were both consistent across runs and high quality. Flagged count = prompts that failed consistency or quality.")
    st.dataframe(pd.DataFrame(rel_list), use_container_width=True, column_config={
        "reliability_pct": st.column_config.NumberColumn("Reliability %", format="%.1f"),
        "consistent_high_quality": st.column_config.NumberColumn("Consistent & high quality"),
        "total": st.column_config.NumberColumn("Total prompts"),
        "flagged_count": st.column_config.NumberColumn("Flagged count"),
    })
    flagged_ids = reliability.get("flagged_prompt_ids", [])
    if not flagged_ids:
        st.info("No prompts flagged.")
    else:
        st.subheader("Flagged prompts (inconsistent or problematic)")
        per_prompt = reliability.get("per_prompt", {})
        rows = []
        for pid in flagged_ids:
            p = per_prompt.get(pid, {})
            rows.append({
                "prompt_id": pid,
                "agent": p.get("agent"),
                "prompt": (p.get("prompt") or "")[:80] + "..." if len(p.get("prompt") or "") > 80 else (p.get("prompt") or ""),
                "score_std": p.get("score_std"),
                "safety_varies": p.get("safety_varies"),
                "equivalence_reason": (p.get("equivalence_reason") or "")[:120],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, column_config={
            "prompt": st.column_config.TextColumn("Prompt", width="medium"),
            "score_std": st.column_config.NumberColumn("Score variance (std)", format="%.2f"),
            "safety_varies": st.column_config.CheckboxColumn("Safety varied across runs?"),
            "equivalence_reason": st.column_config.TextColumn("Why flagged (LLM reason)", width="medium"),
        })


def render_golden(golden_df: pd.DataFrame | None):
    st.header("Golden answers")
    st.markdown("Prompts that **failed or were weak** (any dimension &lt; 3 or safety ≤ 2). Each entry includes what went wrong, the response the agent *should* have given (corrected response), and an **engineering note** on what to change (system prompt or retrieval).")
    if golden_df is None or golden_df.empty:
        st.info("No golden answers file or empty. Run `python scripts/generate_golden.py`.")
        return
    st.dataframe(
        golden_df[["prompt_id", "agent", "prompt", "accuracy", "helpfulness", "safety", "personalization", "latency", "what_went_wrong", "what_to_change"]],
        use_container_width=True,
        column_config={
            "prompt": st.column_config.TextColumn("Prompt", width="medium"),
            "what_went_wrong": st.column_config.TextColumn("What went wrong", width="large"),
            "what_to_change": st.column_config.TextColumn("Engineering note (what to change)", width="medium"),
        },
    )
    # Expandable corrected response per row would need custom component; link to file or show in expander per prompt_id
    with st.expander("View corrected responses (first 3)"):
        for i, (_, row) in enumerate(golden_df.head(3).iterrows()):
            st.markdown(f"**{row['prompt_id']}** — {(str(row.get('prompt', ''))[:60])}...")
            st.text((str(row.get("corrected_response") or ""))[:1500])


def render_explorer(scores_df: pd.DataFrame, reliability: dict | None, golden_df: pd.DataFrame | None):
    st.header("Prompt explorer")
    st.markdown("All **30 test prompts** in one list. See each prompt's scores and status:")
    st.markdown("- **Mean score** — average of the 5 dimensions (1–5). **Min score** — lowest dimension (triggers golden if &lt; 3).")
    st.markdown("- **Inconsistent?** — Yes if this prompt was flagged in the reliability report (different or unsafe answers across 3 runs).")
    st.markdown("- **Has golden answer?** — Yes if this prompt failed or was weak, so it has a corrected response and engineering note.")
    per_prompt = (reliability or {}).get("per_prompt", {})
    flagged_set = set((reliability or {}).get("flagged_prompt_ids", []))
    golden_ids = set(golden_df["prompt_id"].tolist()) if golden_df is not None and not golden_df.empty else set()
    rows = []
    for _, row in scores_df.iterrows():
        pid = row["prompt_id"]
        rows.append({
            "prompt_id": pid,
            "agent": row["agent"],
            "prompt": row["prompt"][:70] + "..." if len(str(row["prompt"])) > 70 else row["prompt"],
            "mean_score": row["mean_score"],
            "min_score": row.get("min_score"),
            "inconsistent": pid in flagged_set,
            "has_golden_answer": pid in golden_ids,
        })
    expl = pd.DataFrame(rows)
    st.dataframe(
        expl,
        use_container_width=True,
        column_config={
            "prompt_id": st.column_config.TextColumn("ID"),
            "agent": st.column_config.TextColumn("Agent"),
            "prompt": st.column_config.TextColumn("Prompt", width="medium"),
            "mean_score": st.column_config.NumberColumn("Mean score (1–5)", format="%.1f"),
            "min_score": st.column_config.NumberColumn("Min score (1–5)", format="%.0f"),
            "inconsistent": st.column_config.CheckboxColumn("Inconsistent across 3 runs?"),
            "has_golden_answer": st.column_config.CheckboxColumn("Has golden answer (failed/weak)?"),
        },
    )


if __name__ == "__main__":
    main()
