# Chaos Playground v2

This directory preserves the interactive artifact built by Opus 5 during the
Firelink reconstruction.

## Preserved source

- File: `chaos-playground-v2.html`
- Size: 64,584 bytes / 1,614 lines
- SHA-256: `227C350BFC930ACC17FFD3309D5AFB5F9EA1EA0876DEE82497746B33B0EF44B5`
- Claude artifact URL:
  `https://claude.ai/code/artifact/c3fcff45-8e5d-432d-9216-2306614a931b`
- Original scratchpad path:
  `C:\Users\Rick\AppData\Local\Temp\claude\C--Games-FRAM-V22-Starter-fram-v22-starter\862c7f7e-bebe-42ff-9252-5d238e089580\scratchpad\chaos-playground-v2.html`
- Preserved on: 2026-07-27

The HTML was copied byte-for-byte. It intentionally has no `html`, `head`, or
`body` wrapper because it was authored as a Claude artifact fragment. Browsers
still accept it as a top-level local HTML document.

## Capability surface

- draggable, zoomable logistic-map helix;
- live Lyapunov exponent, orbit-period, superstable-onset, and Feigenbaum-ratio
  readouts;
- scrubbable bifurcation diagram;
- coupled Mandelbrot and Julia views;
- deterministic scene save/export/import;
- recoverable shelving in place of destructive deletion.

The artifact is self-contained and makes no network requests.

`golden-default-v1.json` connects the browser's default logistic readouts to
the canonical Python simulator and diagnostics. It also records the visible
Edge render and the save → shelve → restore memory cycle. The cascade onsets
remain browser-specific finite numerical measurements; the fixture checks
their internal spacing ratios rather than relabeling them as superstable roots.

## Run

Open `chaos-playground-v2.html` in a browser. The canvases depend on
`requestAnimationFrame`, so a headless or backgrounded document can execute the
math while still painting no pixels.

## Evidence boundary

The source and visible browser run establish an interactive reconstruction.
They do not establish that the original March 2026 implementation used these
exact formulas or parameters. The supplied historical screenshots are recovery
evidence for the visual vocabulary and intended logistic-map lineage, not a
source-code identity proof.
