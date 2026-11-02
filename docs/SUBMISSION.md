# Iris — a seatbelt for write-capable agents

**One line:** You speak one change and leave. An agent does the work on its own desktop.
A save happens only when the write is *exactly* the change you authorized.

Problem statement: **Push the Frontier — software.** Theme: verifiable agents.

## The problem (why this matters)
Agents are getting write access — to calendars, orders, records, money. The failure that
matters is not a wrong sentence, it is a wrong *write*: the agent clicks the right-looking
button on the **wrong record**, or quietly changes a field you never authorized (zeroes a
price, cancels the wrong booking). A reviewer that only sees the button label cannot catch
this, because the identity and the saved values are invisible at the button.

Iris is the layer that sits at the write and refuses anything that is not the exact authorized
change. It is model-agnostic and app-agnostic: the gate knows nothing about bookings or orders,
only *resource, record, fields-that-may-change, fields-that-must-not, forbidden operations, and
the record version the permission was based on.*

## How it works
1. **Muse Voice Transcribe** captures the spoken instruction — the only instruction.
2. **Muse Spark** compiles it into a *readable, locked permission* (asks one question if vague).
3. The agent (**Muse Spark**) drives a browser inside an isolated Linux VM — never the host desktop.
4. At the moment of save, two independent checks run on the proposed write:
   - **Muse Spark Open (open weights, on Baseten)** is a *blind reader*: it reads the on-screen
     form pixels and names the record and values, with no sight of the sentence, the permission,
     or the planner's answer.
   - A **deterministic gate** compares the proposed write to the permission (identity, every
     protected field, forbidden ops, exact values, record version) inside the write transaction.
5. Only an exact match mutates the database. Click, Enter key, and raw HTTP all share one gate.

## Evidence (not a claim — a measured result)
A frozen held-out evaluation scores three systems on identical tasks (see `docs/EVALUATION.md`,
regenerate with `scripts/run_evaluation.py`; the live view is the **Evaluation** tab in the app):

| System | Unauthorized saves | Finished legitimate | False blocks |
| --- | --- | --- | --- |
| Agent alone | **12 / 16** | 4 / 4 | 0 / 4 |
| Button-only reviewer | **10 / 16** | 4 / 4 | 0 / 4 |
| **Iris** | **0 / 16** | 4 / 4 | 0 / 4 |

Across wrong-record, protected-field, stale-version, vague, forbidden-op and prompt-injection
tasks, Iris stops every unauthorized save while finishing every legitimate one and blocking
none of them. A button-only reviewer only catches the visible forbidden verb.

## Why Meta's models are required
- **Muse Spark** — turns a spoken sentence into a structured permission, and plans the browser steps.
- **Muse Spark Open (open weights, Baseten)** — the independent pixel reader. It is load-bearing:
  the agent proposes, the open-weights reader disagrees, and the gate changes what is saved.
  *(Eligible for Best Build on Meta Open Weight Models.)*
- **Muse Voice Transcribe** — hands-free capture so you can speak the change and walk away.

The agent proposes, the independent reader disputes, the gate decides — meaningful multi-step
autonomy with a verifiable outcome. *(Eligible for Best Agentic Use-Case.)*

## Built during the Hackathon (new work)
Generic permission gate + transactional SQLite ledger; two owned resource desks (booking +
store-order) that share one gate; the Spark permission compiler and browser agent; the
open-weights blind reader; the pixel visual guard; the isolated Docker VM browser worker with
lease recovery and network egress restriction; live desktop stream; voice capture; and the
**held-out three-system evaluation harness + the live comparison/attack UI**. Commit history is
under the author's name and shows every step was built during the event.

## What is live vs. environment
Iris owns both desks with invented people and prices (aimed at self-hosted Cal.com:
cal.com/docs/self-hosting). Per the project plan, the Iris desks are the sanctioned environment;
no real payment, inbox, or cloned cookies are used, and the agent never receives the host desktop.

## Honesty / prior art
No world-first claim. Related action-review work exists (Google's User Alignment Critic, the
Visual Confused Deputy research). Iris's specific contribution is a *readable permission enforced
on the write*, measured head-to-head against a button-only reviewer.

## Links
- Public repo: <this repository>
- 3-minute demo video: <link>
- Live app: `docker compose up -d --build` → http://127.0.0.1:8768 (Evaluation tab needs no API key)
