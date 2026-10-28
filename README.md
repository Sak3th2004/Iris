# Iris

**Step away. Stay in control.**

Iris turns an instruction into a readable permission and enforces it at the database write. A correct-looking click is not sufficient: the resource, record, version, and resulting values must match. Booking and store-order desks use the same generic gate.

Built for the Meta Global AI Developer Hackathon. This repository is new work; Second Self is an architectural reference for a visible separate desktop, not a code or design dependency.

## Run locally

Python 3.11 or newer:

```powershell
python -m pip install -e ".[test,agent]"
Copy-Item .env.example .env  # only if you do not already have .env
# Edit .env locally. Never commit or share its keys.
python -m uvicorn iris.api:app --app-dir backend --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765. Exact structured permissions work without an API key. Natural-language interpretation and voice use the actual Meta API and report errors when unavailable. No canned model fallback exists.

Use **New record** to create invented guests and buyers. The initial Alice/Bob/Priya records are starter data, not special cases in the gate. The API accepts arbitrary record IDs and names; the gate has no booking-specific or person-specific logic. Owner record creation is setup, separate from gated updates, and is never exposed to the worker.

## What is working

| Capability | Status |
| --- | --- |
| Generic field rules, identity checks, preserved fields, stale-version refusal | Implemented and tested |
| Atomic SQLite save, single-use permission, readback and audit | Implemented; concurrent submission tested |
| Booking and store-order screens; new invented records | Implemented and browser-tested |
| Same write endpoint for click, Enter and HTTP | Implemented and tested |
| Muse Spark 1.3 Standard permission interpretation | One live API interpretation verified locally |
| Muse Voice Transcribe recording and WAV adapter | Implemented; live microphone/provider path not yet verified |
| VM-only Playwright worker and separate Spark blind reader | Implemented; unit-tested, no VM end-to-end run yet |
| Baseten Spark Open reader | Not integrated; awaiting credits |
| Actual VM preview in owner UI | Not yet implemented; current desk is labeled local |
| Cal.com / Cal.diy write interception | Not integrated; current desks are served by Iris |
| Held-out three-system results, coffee video, submission | Pending actual VM runs; no fabricated results |

This is a working local foundation, **not a completed hackathon submission**.

## Permission and persistence

`backend/iris/gate.py` is a pure `decide` function. It knows resource type, record ID, field rules, prohibited operations, and version. `Store.submit` begins an immediate SQLite transaction, loads the server-side permission and current record, calls `decide` exactly once, and updates the record only on `allow`. It consumes successful permissions, invalidates stale permissions, records before/after snapshots, and commits the change and audit together. JSON types are compared strictly.

An exact write can include unchanged form fields. An unauthorized extra change, wrong record, forbidden operation, or wrong version cannot save. A missing or consumed permission pauses. A version is captured before Spark interprets a sentence and checked again when locking the permission.

The current product editors support booking-day and order-quantity instructions. Other fields are preserved. This is an explicit application scope; the underlying gate supports arbitrary field rules. Full dates/time zones and broader edit schemas remain work before a production scheduling integration. Spoken instructions currently lock against the snapshot at interpretation, not at recording start; capture-time snapshot binding remains to be implemented.

## Meta usage and budget

Only `muse-spark-1.3` Standard and `muse-voice-transcribe-1.0` are configured. No Contributor mode, SAM, image generation, or automatic provider retries. A persistent SQLite budget reserves estimated worst-case input/output cost before each model call. Successful token usage settles the reservation; uncertain failures retain it conservatively. The default app budget is $149.99, bounded by `IRIS_SPEND_LIMIT_USD`. This is a local app guard, not a provider account limit; it cannot account for spending from other apps or a deleted database. Set the account limit in Meta's dashboard too.

Pricing assumptions (checked October 28, 2026): Spark input $1.25/M tokens and output $4.25/M; voice $0.18/hour. Cached-token savings are deliberately not assumed. [Meta pricing](https://dev.meta.ai/docs/pricing-rate-limits), [API reference](https://dev.meta.ai/docs/api-reference), [voice format](https://dev.meta.ai/docs/speech-to-text).

Spark's roles are interpretation, browser action selection, and an independently prompted form read. The reader sees neither the instruction nor the planner answer. Reader disagreement stops the job; reader agreement never overrides the deterministic gate. Model interpretation can still misunderstand intent: the readable card makes that interpretation inspectable, and the gate enforces the locked permission, not a proof of natural-language understanding.

## Isolation and security scope

The owner app is single-user, loopback-only development software. It has host/origin validation but does not yet have production authentication, session isolation, CSRF tokens, or rate limiting. Do not publish this server or expose it to the agent network. See [VM setup and limitations](docs/VM.md) for the separate, token-protected worker gateway. The worker has no shell tool, host desktop API, real inbox, cookies, or payment connection. The current VM check is a guard, not remote attestation.

The worker must run inside a Linux VM, with access only to the restricted gateway. Neither its token nor the Meta key may enter git. Recording and local databases are ignored. Invented people and prices only. Rejected browser-agent writes are labeled agent misses; intentional manual fault controls are explicitly labeled fault injection.

## Verification

```powershell
python -m pytest -q
python -m playwright install chromium
python scripts/browser_check.py
```

The browser check uses an isolated temporary database and real browser interactions: wrong record, protected-price fault, Enter save, a newly created buyer and order, mobile overflow, and browser errors. It is a software acceptance test, not an autonomous agent evaluation. `scripts/check_meta.py` makes one bounded **paid** live parser call; it never prints the key.

See [evaluation protocol](docs/EVALUATION.md), [Cal integration assessment](docs/CAL_INTEGRATION.md), and [submission draft](docs/SUBMISSION.md). Do not claim measured superiority or a completed recording until those artifacts exist.
