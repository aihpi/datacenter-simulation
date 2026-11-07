# Verifiable success criteria

`eval/run_eval.py` runs the **full pipeline** (profiling → correlation + FDR →
LLM classify → partial-correlation verification) on every pair in
`data/ground_truth.json`, then scores predictions against the
known-by-construction ground truth.

It reports: overall verdict accuracy, a 5×5 confusion matrix, a per-case
PASS/FAIL table, the `confounder_in_data` match rate, and the "chance" accuracy
on the independent random pairs. It **exits non-zero** when thresholds are not met.

## Thresholds depend on the active `LLM_BACKEND`

### `mock` (the default — proves the PLUMBING, not LLM quality)
- **Verdict accuracy == 100%.** The mock is scripted from the answer key, so any
  miss is a pipeline/wiring bug, not a modeling error.
- **`confounder_in_data` matches truth for every case.**
- **Chance accuracy ≥ 90%** on the independent random pairs (confabulation guard).

> **Honesty note.** Gate 2's 100% is *only* meaningful for the mock and validates
> the pipeline end to end. It does **not** measure explanation quality. The
> ground-truth-correct answers live **only** inside `MockLLMClient`; nothing is
> hardcoded anywhere else in the pipeline.

### `vertex` (run later — measures REAL explanation quality)
- **Verdict accuracy ≥ 80%.**
- **Chance accuracy ≥ 90%** on the random pairs (the model must resist
  confabulating relationships among pure noise).
- `confounder_in_data` match rate is reported but not gated at 100%.

Switch with `export LLM_BACKEND=vertex` after pasting a working Vertex call into
`engine/llm/vertex.py` (see .env.example).

## What "verification" proves
For every `confounder_in_data == true` case, controlling for the named confounder
Z via partial correlation must drop the X–Y association below the configured
threshold (`engine/config.py: PARTIAL_COLLAPSE_ABS`). This is a property of the
DATA and is asserted numerically in `tests/test_verification.py` (Gate 4),
independent of any LLM.
