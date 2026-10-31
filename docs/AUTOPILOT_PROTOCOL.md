# Autopilot Protocol

This protocol defines how the coding agent proceeds autonomously while keeping
human oversight, safety, and clarity.

## Permissions
- Proceed with recommended steps and run required commands.
- Create branches, commit changes, and update docs as needed.

## Pause Conditions (must ask first)
- Destructive actions, including:
  - deleting data, wiping caches, or removing datasets
  - force-push or history rewrite (rebase, amend, reset --hard)
  - dropping tables or removing storage folders
  - changing default scoring logic without a baseline snapshot
- Any decision that changes goals or scope.
- Uncertainty about intent or risk of unintended impact.

## Commit Expectations
- Commit in small, logical chunks.
- Include a one-line summary and how to reproduce (commands or "No tests run").

## Timeouts and Long Runs
- Avoid hard timeouts that cut tasks short; allow long-running runs to finish.
- If a run might be long, mention it in the next check-in.

## Check-ins
- Provide brief status + next step every 60-120 minutes or at natural breakpoints.
- Invite a pause, Stillpoint, or questions whenever helpful.
