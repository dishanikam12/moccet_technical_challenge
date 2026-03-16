# Approximate cost: Agent responses + LLM-as-judge

Rough cost per **single eval run** (33 prompts). You can use **mock** responses (no API) or **real agent** (LLM) responses; if you use the agent, add the cost below. Judge cost is per run when `--llm-judge` is used. Prices are indicative; check provider pages for current rates.

---

## Agent responses (real API: `--llm` without `--mock`)

One LLM call per prompt: system prompt from `config/agents.yaml` + user prompt → response (max 1,500 tokens).

| What | Tokens per call | × 33 calls |
|------|-----------------|------------|
| **Input** (system + user prompt) | ~100–150 | ~3.3k–5k |
| **Output** (agent response) | ~200–500 (avg) | ~7k–17k |

**Cost per run (33 prompts), agent only:**

| Model | Input | Output (avg) | **Total** |
|-------|--------|--------------|-----------|
| **gpt-4o-mini** (OpenAI) | ~\$0.001 | ~\$0.007 | **~\$0.01 (≈1 cent)** |
| **Claude 3.5 Haiku** (Anthropic) | ~\$0.003 | ~\$0.05 | **~\$0.05 (≈5 cents)** |

---

## Judge only (LLM-as-judge, `--llm-judge`)

**Token use per run (approx):**

| What | Tokens per call | × 33 calls |
|------|-----------------|------------|
| **Input** (rubric + prompt + expected_behavior + response) | ~1,200–1,800 | ~40k–60k |
| **Output** (JSON score only) | ~50 | ~1.7k |

---

## Cost per single run (33 prompts)

### OpenAI – **gpt-4o-mini** (default judge)

- **Input:** ~\$0.15 / 1M tokens → ~\$0.006–0.009  
- **Output:** ~\$0.60 / 1M tokens → ~\$0.001  
- **Total per run:** **~\$0.01 (about 1 cent)**

### Anthropic – **Claude 3.5 Haiku**

- **Input:** ~\$0.80 / 1M tokens → ~\$0.03–0.05  
- **Output:** ~\$4.00 / 1M tokens → ~\$0.007  
- **Total per run:** **~\$0.04–0.06 (about 4–6 cents)**

---

## Reliability benchmark (3 runs)

- **OpenAI:** ~3 × \$0.01 ≈ **~\$0.03**  
- **Anthropic:** ~3 × \$0.05 ≈ **~\$0.15**

---

## Summary

| Scenario | gpt-4o-mini (OpenAI) | Claude 3.5 Haiku (Anthropic) |
|----------|----------------------|------------------------------|
| **Judge only** (33 prompts, mock responses) | ~1 cent | ~4–6 cents |
| **Agent only** (33 prompts, real API responses) | ~1 cent | ~5 cents |
| **Agent + judge** (33 prompts, full eval) | **~2 cents** | **~10 cents** |
| **Reliability** (3 runs, judge only) | ~3 cents | ~15 cents |
| **Reliability** (3 runs, agent + judge) | **~6 cents** | **~30 cents** |

So even with real agent responses + judge, a full 33-prompt eval is about **2 cents (OpenAI)** or **10 cents (Anthropic)**; a 3-run reliability benchmark stays under **\$0.35**. Pricing as of 2024–2025; confirm on [OpenAI pricing](https://platform.openai.com/docs/models) and [Anthropic pricing](https://docs.anthropic.com/en/docs/about-claude/pricing).
