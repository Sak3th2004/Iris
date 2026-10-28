# Real isolated-agent development runs

October 28, 2026. These are integration checks, **not held-out benchmark results**. No action sequence was supplied by the script: it created a fresh invented record, asked Muse Spark to interpret the sentence, queued the permission, and polled the result. Muse Spark selected the browser actions. A separate Spark call read the form before the generic gate allowed the update.

Environment: Docker Desktop Linux VM; dedicated non-root browser container; headed Chromium on Xvfb; Playwright 1.64.1; Standard Muse Spark 1.3. Raw traces are in `docs/evidence/`. Model-generated redundant actions are retained.

| Task | Result | Version | Protected price | Browser steps | Agent wall time |
| --- | --- | --- | --- | --- | --- |
| New guest Mira 00966f: Monday → Thursday | Saved and read back | 1 → 2 | $137 unchanged | 6 | 53.48 s |
| New buyer Mira c4abf7: quantity 1 → 4 | Saved and read back | 1 → 2 | $137 unchanged | 6 | 42.44 s |

Combined provider-usage accounting for these two tasks was $0.088694. The planner unnecessarily reopened/edited records before saving; that is a development finding, not a planted fault. After these runs, the planner prompt was clarified to distinguish persisted list values from unsaved form values. The table above describes the pre-clarification runs and must not be presented as measurements of the updated prompt.

Actual network probes from the running browser container verified: gateway reachable; public internet, both host owner ports, and the owner container IP unreachable. Docker inspection confirmed no mounted storage, no Docker socket, no Meta API key, and membership only in the internal browser network. The software test suite also covers token-gated frame ingestion, stale-frame refusal, and stopping during the independent reader without a save.

This evidence establishes the live agent loop and both resources. It does not establish Cal interception, voice capture, prompt-injection robustness, held-out superiority, arbitrary-site support, or a completed video.
