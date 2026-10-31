# DONE — Step 1 Core Semantics Contract

Files created/changed:
- `docs/fractal_core.md`
- `docs/done_step_1_core_semantics.md`

Tests that enforce guarantees (existing):
- `tests/test_fractal_memory.py:test_generation_determinism`
- `tests/test_fractal_memory.py:test_quaternion_normalized`
- `tests/test_fractal_memory.py:test_lambda_bounds`
- `tests/test_fractal_memory.py:test_trace_schema_v2_persisted`
- `tests/test_fractal_trace_smoke.py:test_fractal_trace_smoke`
- `tests/test_fractal_memory.py:test_v1_trace_load_compatibility`

Tests run in this step:
```text
pytest -q -s tests\test_fractal_trace_smoke.py
pytest -q -s tests\test_fractal_memory.py
```

Output snippet:
```text
1 passed, 1 warning in 9.89s
11 passed in 0.13s
```

Stop condition confirmation:
- The live trace JSON under the repo storage root contains `coord6`, `q`, and
  `lambda`. See `docs/proof/fractal_core_proof.md` for the exact path and snippet.
