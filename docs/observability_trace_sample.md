# Observability Trace Sample (Residual Step Metadata)

- Query: `What does the roadmap say about curvature anchors?`
- Run mode: forced `conformal_policy` to return `"anchors"` to surface the new residual metadata.
- Data source: default demo corpus ingested via `scripts/ingest_project_docs.py`.
- Full trace saved alongside this doc as `trace_sample.json` (same directory).

The snippet below captures the anchor entries and the attached `residual_step` fields now emitted by `fram_core/pipeline._curvature_anchor_candidates`.

```json
[
  {
    "id": 8,
    "is_seed": true,
    "delta": 7.600000000000002,
    "composite_cost": 1.234,
    "ratio": 6.158833063209078,
    "residual_step": {
      "eig_index": 0,
      "eig_value": 5.6693980504485723e-05,
      "step_scale": 0.7,
      "step_sign": -1,
      "target_length": 0.005270678366889598,
      "clamped_length": 0.7802810041553899,
      "projection_cos": 0.13476007227563286
    }
  },
  {
    "id": 19,
    "is_seed": false,
    "delta": 16.959999999999976,
    "composite_cost": 1.7,
    "ratio": 9.97647058823528
  },
  {
    "id": 21,
    "is_seed": false,
    "delta": 15.791999999999948,
    "composite_cost": 1.95,
    "ratio": 8.098461538461512
  },
  {
    "id": 2,
    "is_seed": false,
    "delta": 14.463999999999956,
    "composite_cost": 2.3,
    "ratio": 6.288695652173894
  }
]
```

Include this document in the docs ingest run so observability tooling can cite an example residual-step payload.
