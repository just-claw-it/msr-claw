# LLM-generated collection, analysis, figures, and plans

## Research plan (problem agent)

After RQs and sources, the problem agent asks the LLM for a **`research_plan`** object: summary, `collection_strategy`, `analysis_strategy`, `figure_plan` (title + rationale per intended figure), `validity_focus`, `paper_emphasis`. It is saved as `research_plan.json` in the run workspace and passed to downstream agents (collection script prompts, analysis, figures, sampling interpretation, refinement, validity, writer).

## Scripts (`MSRCLAW_LLM_SCRIPTS=1`, not mock)

1. **Collection** (per source): JSON `{ "filename", "script" }` tailored to the problem, RQs, plan, and source hints. Fallback: plugin template.

2. **Analysis**: reads collected paths; writes `data/processed/summary.json`. Fallback: `msrclaw.codegen.analysis_script.build_analysis_script` (includes `research_plan` in embedded context).

3. **Figures**: optional second script `make_figures.py` writes under `figures/` (PNG/PDF/SVG). May use matplotlib/pandas if available. **Result** rows with `result_type="figure"` record paths. Skipped if the LLM response is invalid or disabled.

4. **Sampling**: after pandas profiling, an optional LLM paragraph is appended to sample notes (interpretation tied to RQs and plan).

5. **Validity & writer**: prompts include the full problem, `research_plan` excerpt, and (for writer) figure paths so sections match the study.

6. **Mock / CI** (`MSRCLAW_MOCK_LLM=1`): stub plan; no LLM script synthesis; template analysis; no figure LLM.

7. **Opt-out**: `MSRCLAW_LLM_SCRIPTS=0` forces template-only scripts for collection/analysis/figures.

## Expectations

Use a **capable** model (e.g. GPT-4o-class). Invalid JSON or scripts fall back where possible so runs can still complete.
