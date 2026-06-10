# Non-Canonical Sentinel Source Explanation

Raw output: [4c_prohibited_language_raw_postfix.txt](4c_prohibited_language_raw_postfix.txt) is unrelated; the sentinel evidence is captured in the live query output below.

Live query output showed exactly two non-canonical entries:
- `agent.immutability_guard.v1` with `CALIBRATION_IMMUTABILITY_VIOLATION` at `2026-05-24T10:19:56.426504+00:00`
- `agent.immutability_guard.v1` with `CALIBRATION_IMMUTABILITY_VIOLATION` at `2026-05-27T13:32:29.057575+00:00`

Why they are non-canonical:
- The canonical format enforced by the directive is `agent.<lowercase>.v<digits>`.
- The agent id `agent.immutability_guard.v1` contains an underscore, so it does not match the canonical pattern.

Source attribution:
- The event type indicates these were emitted by the calibration/immutability guard path, not by the standard canonical agent id writer.
- Because the query result did not include a different source field, the immediate source we can evidence from the live record is the immutability guard service path embedded in the `agent_id` itself.

Operational note:
- This looks like a production event, not a test artifact, because it exists in the live production collection and was returned by the live Mongo query.
- If the production source is still emitting this identity, the writer should be corrected to use a canonical agent id.
