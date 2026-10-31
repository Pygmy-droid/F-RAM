# Cosmic Cathedral

The Cosmic Cathedral is a local, interactive continuity map for F-RAM. It
projects a bounded set of repository sources into a rotatable 3D gravity-well
view so a person or agent can navigate relationships without loading every
document into context.

It is a **navigation layer**, not a new authority layer:

- current code and tests remain the strongest implementation evidence;
- the Atlas authority ladder remains binding;
- file status means Git/worktree state, not scientific truth or project
  completeness;
- grass, erosion, river recall, and last-combed lift are labelled
  reconstruction encodings; and
- the Hairy Ball theorem is shown only as a theorem about continuous tangent
  vector fields on even-dimensional spheres.

## Run

Build the deterministic repository projection:

```powershell
python tools/build_cosmic_cathedral.py
```

Keep it refreshed while working:

```powershell
python tools/build_cosmic_cathedral.py --watch --interval 5
```

Witness inclusion is separate and explicit:

```powershell
python tools/build_cosmic_cathedral.py --watch --interval 5 --include-witness
```

Serve the repository root and open:

```text
http://127.0.0.1:8765/experiments/cosmic_cathedral/cosmic-cathedral-v1.html
```

The page polls `cosmic-cathedral-map.json` every five seconds. The builder
records branch, HEAD, file hashes, modification times, and tracked/modified/
untracked/missing state for each source-backed node. It keeps repository
`worktree_state`, epistemic `claim_state`, `scope`, and `substrate` separate.

When `FRAM_CONTINUITY_WITNESS_ENABLED=1`, finalized queries append a sanitized
v2 sidecar under `storage/observability/continuity/`. The builder includes it
only with `--include-witness`, applies a freshness bound, and projects aggregate
counts/statuses rather than trace, selection, citation, write, or digest IDs.
The live graph shows query, active gates, candidate-origin forks, selection,
citations, and final write outcomes; it does not contain raw query/answer text
and cannot feed retrieval.

If no witness exists, the map displays an explicit awaiting/unknown node. It
does not invent a successful run.

## Interaction

- Drag empty space to orbit the 3D map.
- Use the wheel to zoom.
- Drag a node to move it; browser-local positions persist.
- Select or explicitly comb a node to append a local traversal event.
- Recall searches labels, paths, summaries, kinds, and authority.
- Familiar/recent traversal lowers only the visual route resistance.
- The last-combed node is lifted along z as an explicit navigation encoding.
- Export trail downloads the append-only local event log as JSON.
- Hairy Ball field displays the theorem boundary separately from the
  grass-memory reconstruction.
- Live witness nodes use equal default mass; shape communicates kind, arrows
  communicate relation direction, and claim/scope remain explicit metadata.
- The United Ecological Strata constellation gives human participation, model
  roles, planetary ecology, and hypothetical future intelligence equal default
  visual mass while `docs/UNITED_STRATA_CONTRACT.md` keeps their agency,
  authority, consent, capability, substrate, and evidence distinct.

Traversal events live in browser local storage under
`fram.cosmic-cathedral.traversal.v1`; they never modify F-RAM runtime memory.
