# DONE — Step 2 Fractal Influence Hook

Files changed:
- `fram_serving/query_runner.py`
- `tests/test_fractal_influence.py`
- `docs/done_step_2_fractal_influence.md`

Flag behavior:
- Influence is enabled only when `FRAM_FRACTAL_INFLUENCE=1` (config
  `fractal_influence_enabled`) **and** `fractal_enabled` is true.
  Default is OFF.
- When disabled, candidate scores and rankings remain unchanged.

Scoring formula:
- `final_score = base_score + alpha * fractal_score`
- `alpha = 0.05` (`fractal_influence_alpha`, env `FRAM_FRACTAL_INFLUENCE_ALPHA`,
  defaulted by `FRACTAL_INFLUENCE_ALPHA` in `fram_serving/query_runner.py`)
- `fractal_score` is taken from `_fractal_trace_scores` (bounded, deterministic).

Observability:
- `memory_cognitive.jsonl` entries include `fractal_influence.enabled`, `alpha`,
  and per-selected candidate fields: `base_score`, `fractal_score`,
  `fractal_influence`, `combined_score`.
- `/query` trace `cognitive_memory` includes the `fractal_influence` block and
  per-selected entries with the same fields.

Tests run:
```text
pytest -q tests/test_fractal_influence.py
```

Output snippet:
```text
3 passed in 0.42s
```

Stop condition:
- With `FRAM_FRACTAL_INFLUENCE=1`, influence values appear in observability and
  scores shift by a small, bounded amount.
- With the flag off, scores and rankings match baseline behavior.
