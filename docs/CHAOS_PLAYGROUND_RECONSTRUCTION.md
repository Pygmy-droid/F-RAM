# Chaos Playground reconstruction contract

Date: 2026-07-27  
Status: visual contract and deterministic Python math core recovered; original
browser source and exact rotational formula remain missing.

## Surviving evidence

The protected source tree contains two screenshots of the original system:

- `Images/Screenshot/IMG_0090.PNG` — 1206x2622, SHA-256 prefix `c1454e`.
  It preserves the orange/blue density-weighted rotational creature and the
  original description of recursive-motion interference born from the logistic
  map.
- `Images/Screenshot/IMG_0091.PNG` — 1206x2622, SHA-256 prefix `5f78e7`.
  It shows the Chaos Playground interface rendering a "Cathedral Organism" and
  a DNA-like double helix, with side controls and lower logistic/fractal and
  complex-plane panes.

Each image has a byte-identical duplicate in the `2026-07-16/` mirror. The
original application source was not found in Git history, the NVMe source
trees, or archive filenames.

The screenshots establish visual and interaction intent. They do not recover
the exact rotational mapping, density rule, or numerical implementation.

## Existing reusable math

- `fram_eval.fractal_falsification`: deterministic logistic, Henon, Lorenz, and
  Aizawa trajectories, normalization, embedding, soft-DTW evaluation, and
  quaternion/lambda ablations.
- `fram_serving.fractal_memory.fractal_gen`: deterministic 6D IFS traces,
  direction-derived quaternions, and independently seeded per-node lambda.
- `fram_core.rotational_lift`: general-dimensional Givens rotations, exact
  residual-preserving lift/reconstruction, degradation experiments, and PCA
  invariant compression.
- `fram_serving.embedding.quaternion_adapter`: a lossy R^d to R^4 projection and
  the proof-track Hopf map.

These are separate constructions. They must not be substituted silently.

## Implemented bounded module split

```text
fram_eval/chaos/
  systems.py       map/flow registry and simulation protocol
  diagnostics.py   Lyapunov, period, superstable roots, Feigenbaum delta
  geometry.py      declared dual rotational encoding
  complex.py       Mandelbrot and Julia escape-time kernels
  scene.py         versioned deterministic scene memory
```

The modules landed at canonical commit `574f25d`. They reuse the established
falsification simulators instead of duplicating system equations.

### Systems

```python
SystemSpec(key, kind, dimension, defaults, simulate)
simulate(system, initial_state, steps, *, params, burn_in=0) -> ndarray
```

### Diagnostics

```python
logistic_lyapunov(x0, r, steps, *, burn_in=1000) -> float
detect_orbit_period(samples, *, max_period=1024, atol=1e-8, repeats=4) -> int | None
logistic_superstable_parameters(max_power, *, tolerance=1e-12) -> list[float]
feigenbaum_delta_estimates(parameters) -> list[float]
```

Feigenbaum estimates use superstable roots of
`f_r^(2^n)(0.5) - 0.5 = 0`. The screenshot value `4.662960` is a meaningful
finite-stage estimate, not the limiting `4.669201609...`.

### Rotational encoding

```python
rotational_accumulation(
    orbit,
    *,
    angular_gain,
    radius_rule,
    pitch,
) -> RotationalPair
```

The clockwise and counter-clockwise branches use identical radius and height
with opposite phase. Because the original formula is lost, the first rebuild
must call the contract `RotationalEncodingV1` and persist its exact rule rather
than claiming exact recovery.

### Complex dynamics

```python
mandelbrot_escape(bounds, width, height, max_iter) -> ndarray
julia_escape(c, bounds, width, height, max_iter) -> ndarray
```

Selecting a Mandelbrot point supplies `c` to the Julia renderer. This is a UI
coupling, not a mathematical equivalence with the logistic map.

### Scene memory

`SceneV1` stores:

- schema and math version;
- system key, parameters, initial state, steps, burn-in, dt, and seed;
- diagnostic tolerances;
- rotational-encoding parameters;
- complex-plane `c`, bounds, and iteration count;
- camera, color, and density settings; and
- title and notes.

Save/load and JSON export/import must round-trip exactly. Numerical arrays are
recomputed from the versioned scene contract; exported scenes remain small and
deterministic.

## Acceptance gates

- [x] Golden first-step fixtures for all four systems.
- [x] Existing logistic/Henon/Lorenz/Aizawa outputs remain bit-identical.
- [x] Logistic Lyapunov is negative in a stable regime and near `ln(2)` at
  `r=4` after burn-in.
- [x] Period detection reports period 2 at `r=3.2`, period 4 at `r=3.5`, and no
  stable period at chaotic `r=3.9`.
- [x] Superstable parameters reproduce known early values; finite delta
  estimates approach the Feigenbaum constant within the declared float64 cap.
- [x] Clockwise/counter-clockwise curves have equal radius and height,
  mirrored phase, and opposite signed winding.
- [x] Mandelbrot `c=0` stays bounded; a known exterior point escapes.
- [x] Julia output changes deterministically with `c`.
- [x] Scene JSON round-trips exactly and rejects unknown schema versions.
- [ ] A shared golden JSON fixture is consumed by both Python and a committed
  browser artifact so the two runtimes cannot drift.

Focused canonical seam verification after Hopf/Aizawa integration:
`128 passed in 15.06s`.

## Naming hazards

"Logistic" currently refers to four different mechanisms in F-RAM:

1. the chaotic logistic map;
2. logistic confidence regression;
3. the Phase D sigmoid alpha blend; and
4. independently hash-seeded per-node lambda.

Per-node lambda is not a temporal logistic orbit and cannot produce
period-doubling or a Feigenbaum estimate. New code and UI labels must qualify
which mechanism they mean.
