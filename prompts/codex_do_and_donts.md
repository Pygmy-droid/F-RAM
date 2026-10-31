# Coding Agent — Do & Don't

**Do**
- Read local files first (`docs/FRAMv2.2-SPEC.md`, cheatsheet, architecture).
- Propose **diffs** for specific paths, with minimal context lines.
- Keep PR-sized changes with tests and doc updates.
- Reference the spec section that justifies a change.

**Don't**
- Don't dump entire files when only a few lines change.
- Don't rely on stale chat messages — always re-read the local docs.
- Don't add heavy dependencies without noting why and where they're used.
