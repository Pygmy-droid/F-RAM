# Codex App-Server Integration Notes (Draft)

Purpose: capture key points from the Codex app-server announcement and outline a
safe, high-level integration plan for F-RAM without exposing internal mechanics.

Key points (from announcement)
- App-server is the interface Codex uses for rich clients (e.g., VS Code).
- It supports authentication, conversation history, approvals, and streamed agent events.
- The app-server implementation is open source (openai/codex/codex-rs/app-server).

Why this matters for F-RAM
- App-server provides a clean integration surface for memory-aware agents.
- It offers a natural place to attach F-RAM memory, traces, and approvals.
- It should reduce glue code for client integrations.

Integration map (high-level)
- Authentication -> bind to F-RAM user/session scope for memory isolation.
- Conversation history -> normalize into FRAM query context and memory capsules.
- Approvals -> wire to policy gates (memory writes, retrieval, fractal influence).
- Streamed agent events -> stream redacted trace summaries + status updates.

Proposed integration flow (no internals)
1) Client -> Codex app-server -> F-RAM gateway (adapter).
2) Adapter maps app-server request into a F-RAM query payload.
3) F-RAM orchestrator runs retrieval, memory, and confidence gates.
4) Adapter streams back redacted agent events and a response.
5) Adapter logs publish-safe trace metadata for auditability.

Data minimization and safety
- Keep only user/session identifiers and redacted trace summaries in logs.
- Avoid internal weights, heuristics, or raw memory artifacts in streamed events.
- Maintain a separate publish-safe trace format for external sharing.

Open questions (for when we inspect the open-source app-server)
- What is the exact event schema for streaming?
- How approvals are represented and how timeouts are handled?
- How conversation history is stored and retrieved (server vs client)?
- What is the recommended auth handshake and token lifecycle?
- How to register or route tool/agent events to custom backends?

Next steps
- Review the app-server repo for exact schemas and hooks.
- Draft a concrete adapter spec based on the open-source protocol.
- Validate that the publish snapshot remains safe if app-server events are logged.
