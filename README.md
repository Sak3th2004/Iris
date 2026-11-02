# Iris

**Say one change. Walk away. The agent saves only what you actually authorized.**

Give an AI agent access to your calendar, your orders, your payments, and sooner or later it does the thing nobody tests for: it clicks the right-looking button on the *wrong* record. No typo. No bad prompt. Just a confident save you never approved.

Iris sits at that exact moment. You say what you want in one sentence. It locks that into a permission you can read. Then an agent does the work on its own machine, and a save reaches the database only if the write is *exactly* the change you approved: right record, right fields, nothing else touched, same version you were looking at.

Built solo for the Meta Global AI Developer Hackathon (Push the Frontier, software). Everything here is new work from the event.

## See it in 30 seconds

Open the app and go to the **Evaluation** tab.
- Hit **Wrong record**, **Protected field**, or **Prompt injection**. An unguarded agent saves the wrong write. A reviewer that only sees the button saves it too. Iris blocks it, every time.
- Then run it for real: say *"set the Acme payment to $5,000, keep the payee,"* watch the agent fill it in on a separate desktop, and watch Iris read the screen and the stored record before a single click lands.

## The numbers (held-out, reproducible)

Three systems, one frozen set of 19 tasks (wrong record, protected field, stale version, vague instruction, forbidden action, prompt injection, and legitimate changes), scored the same way:

| System | Unauthorized saves | Finished legitimate | False blocks |
| --- | --- | --- | --- |
| Agent alone | 14 / 19 | 5 / 5 | 0 / 5 |
| Button-only reviewer | 12 / 19 | 5 / 5 | 0 / 5 |
| **Iris** | **0 / 19** | 5 / 5 | 0 / 5 |

Regenerate anytime with `python scripts/run_evaluation.py`. The live view is the Evaluation tab, and it needs no API key.

## How it works

Three Meta models, each with one job, and one small deterministic gate that owns the write.

- **Muse Voice Transcribe** takes your spoken sentence.
- **Muse Spark** turns it into a readable permission and plans the browser steps.
- **Muse Spark Open** (open weights, on Baseten) is an independent reader. At the moment of save it reads the form pixels on screen and names the record and values, blind to your sentence and to the planner's answer.
- The **gate** (`backend/iris/gate.py`, a single `decide` function) compares the proposed write to the permission inside the database transaction: identity, every protected field, forbidden operations, exact values, and record version. Only an exact match saves. Click, Enter, and raw HTTP all go through it.

The agent proposes, the open-weights reader disputes, the gate decides. That is the whole idea.

Three desks (booking, store orders, payments) run on the *same* gate with no desk-specific logic. That is the point: the gate does not know what a booking or a payment is. It only knows resource, record, the fields that may change, the fields that must not, forbidden operations, and the version the permission was based on.

## Run it

The live isolated agent (the real thing):

```
docker compose up -d --build
# then open http://127.0.0.1:8768
```

The browser runs inside Docker's Linux VM on an internal network, and its real viewport streams back to the owner page. The agent never touches your host desktop.

API and UI only, no VM (Python 3.11+):

```
python -m pip install -e ".[test,agent]"
cp .env.example .env        # add your own keys locally, never commit them
python -m uvicorn iris.api:app --app-dir backend --host 127.0.0.1 --port 8765
```

Structured permissions work with no key. Voice and natural-language interpretation call the real Meta API and tell you clearly when they are unavailable. There is no canned fallback.

## Tests

```
python -m pytest -q         # 103 tests: the gate, the ledger, recovery, the reader, the held-out harness
```

## Honest notes

Invented people, invented money, invented prices. No real payments, no real inbox, no cloned cookies. The payments desk is a mock console that *prevents* a wrong transfer; it does not move real money. The agent only ever sees the restricted worker gateway, never your machine. Faults I planted for testing are labeled as fault injection and kept separate from the agent's own mistakes.

No world-first claim. Related work exists, including Google's User Alignment Critic and the Visual Confused Deputy research. Iris's contribution is a permission you can read, enforced on the write, measured head to head against a button-only reviewer.

## A short map of the code

- `backend/iris/gate.py` — the `decide` function. The whole safety argument lives here.
- `backend/iris/store.py` — the transactional ledger; `decide` is called once, inside the write.
- `backend/iris/evaluation.py` — the held-out three-system harness.
- `worker/desktop_worker.py` — the isolated Playwright agent inside the VM.
- `frontend/src/Evaluation.tsx` — the live comparison and attack view.
- `docs/EVALUATION.md` — the frozen results and the protocol.
