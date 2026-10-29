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

## Owner leaves and returns

A subsequent live UI run used the clarified planner prompt and the redesigned workspace. The test entered an instruction through the UI, reviewed the generated permission, clicked Start agent, and closed the owner page. The worker continued independently. Reopening the page recovered the completed permission and database receipt. New invented guest Nila a40ee1 moved Monday → Friday, price $163 remained unchanged, and version advanced from 1 to 2. Spark took 3 actions; additional accounted model cost was $0.014032. Trace: `docs/evidence/ui-away-return.json`. Mobile overflow, dialog keyboard dismissal, and JavaScript errors were also checked. This is a development integration check, not a held-out result.


## Muse Spark Open integration ? 29 October 2026

Actual calls through the Docker browser, not mocked model responses. The permission parser and three browser actions used Muse Spark 1.3 Standard; the blind reader used Baseten `meta-models/muse-spark-open-1026`. Reader evidence includes the independent input/output and model identity, without reasoning text or keys.

| Resource | Actual saved change | Preserved price | Version | Agent actions | Job duration | Open reader delay |
| --- | --- | --- | --- | --- | --- | --- |
| Booking, Mira a76c2d | Monday ? Thursday | $137 | 1 ? 2 | 3 | 17.22 s | 3.008 s |
| Order, Mira 09c273 | Quantity 1 ? 4 | $137 | 1 ? 2 | 3 | 15.16 s | 3.238 s |

[Booking trace](evidence/baseten-booking.json), [order trace](evidence/baseten-order.json). Duration starts after permission compilation. Both tasks completed with the exact database result. Baseten's local cumulative estimate after both reads was $0.006058 against a $10 development allowance; Meta's Docker-database cumulative estimate was $0.153019, including earlier activity. These are application estimates, not provider billing statements.

34 backend tests passed, including separate budgets, concurrent budget reservations, reader timeouts/truncation/invalid output, missing keys, and reader agreement on a wrong record still rejected by the gate. Browser acceptance and actual container network/key isolation checks passed. These development checks do not establish held-out superiority, visual-reader accuracy, or a completed hackathon submission.
