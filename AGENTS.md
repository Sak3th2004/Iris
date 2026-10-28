# Iris master prompt

You are the coding agent for Iris. Build the product described here. Do not invent a different product. Do not copy Second Self.

## Product

Iris lets a person speak one change, leave, and let an agent work. A save happens only when the write is exactly the authorized change.

The gate is generic. It does not know bookings, orders, plans, or discounts. A permission is:

- Resource type
- Record id
- Fields that may be set, and the required value
- Fields that must stay unchanged
- Operations that are forbidden
- The record version the permission was based on

Two desks prove that. Both are real product screens with invented data. Neither is a spreadsheet.

- Booking desk. Guests, day, and price. Aimed at self-hosted Cal.com: https://cal.com/docs/self-hosting
- Store-order desk. Buyers, item, quantity, and price.

The coffee story uses the booking desk. A second beat uses the store desk: change one order, block the wrong buyer. Judges must be able to see that Iris is not a booking app and not a table app.

If Cal.com writes cannot be intercepted on the first build day, serve both desks from Iris and say so in the README. Do not automate Amazon, Booking.com, Gmail, or any site the project does not own.

## Example

Spoken: "Move Alice's booking to Thursday. Keep the price. Leave Bob's booking unchanged."

Permission:

- Resource: booking
- Record: Alice's booking id
- Set day to Thursday
- Preserve price
- Forbid cancel, email, and every other booking
- Version: the version when the sentence was spoken

Then:

- Reschedule on Bob is rejected. Bob is unchanged.
- A write that zeros Alice's price is rejected.
- Alice, Thursday, same price is saved and read back.
- A version mismatch invalidates the permission and asks again.

These scenes are tests and a film. They are not the only paths in the code. A vague sentence pauses. It does not guess.

## Flow

1. Muse Voice Transcribe captures the sentence. That sentence is the only instruction.
2. Muse Spark turns it into the permission. If a record or a field is missing, Spark asks one question.
3. The card shows the locked permission.
4. The person can leave. The agent keeps working on the other desktop.
5. Muse Spark drives the browser inside a virtual machine. It may not click the main Windows desktop.
6. A blind reader names the open record and the fields the form would save. It does not see Spark's answer. Use Muse Spark Open on Baseten when that credit exists. Until then, use a second Spark call with a separate prompt.
7. The agent proposes a write. Mouse, Enter, and HTTP all become the same proposed write.
8. `decide` returns allow, reject, or pause. Only allow mutates the database.
9. The card shows the attempt and the row afterward.

SAM 3.1 is optional. Add it only if a measured test identifies the open record better than the app's own form data. Do not add it for appearance.

## Code that already exists

`C:\Users\saketh\Projects\iris`

- `backend/iris/models.py`
- `backend/iris/gate.py`
- `backend/iris/store.py`
- `backend/tests/test_gate.py`

Keep the gate idea. The current models still say customer and subscription. Generalize them to resource type, record id, and field rules. Rewrite `store.py` so it calls `decide` once. The ledger must not be able to save a rejected write.

Required tests:

- Wrong record is rejected and unchanged
- A preserved field cannot be overwritten
- The exact write is saved once and the version increments
- A stale version is rejected
- Delete and message are rejected when the permission forbids them
- A missing permission pauses and writes nothing
- The same decision is returned for a click, an Enter key, and an HTTP write

## Screens

Not a chatbot. Not a Mac menu-bar mascot. Second Self's notch, Gmail ingestion, cookie cloning, and personality profile are out of scope. The only lesson from https://github.com/23jmo/second-self is a visible second desktop and a tool boundary around clicks.

- Permission card: sentence, resource, record, set fields, preserved fields, forbidden actions, version, verdict
- Agent desk: the virtual machine, first the booking screen, then the store screen
- Ask state: one question
- Audit: each attempt marked as the agent's own miss or as labeled fault injection

## Stack

- Python, FastAPI, SQLite, pytest for the gate, ledger, and API
- A small web UI for the card
- Playwright for the browser agent inside the virtual machine
- Meta Model API, Standard mode, base `https://api.meta.ai/v1`
- Models: `muse-spark-1.3`, voice transcribe, `sam-3.1` only if the measurement earns it
- Open weights: Baseten model `meta-models/muse-spark-open-1026` for the blind reader when the credit arrives
- About $149.99 of Meta credits. Set a spend limit. No Contributor mode.

## Hackathon

Meta Global AI Developer Hackathon. Indie track. Theme: Push the Frontier, software.

Deadline: 4 November 2026, 9:00 PM ET. Submit earlier, on 4 November India time, not in the last hour.

Submission needs a public GitHub repository, a three-minute video, a description of what was built during the event, and why Meta's models are required. The video must show Iris as the new work. Cal.com or the Iris desks are the environment.

Do not claim a world first. Google's User Alignment Critic and the Visual Confused Deputy research already check agent actions. The claim is a readable permission enforced on the write, measured against a button-only reviewer.

Bonuses to build for:

- Agentic: the agent proposes, the blind reader disagrees, the gate changes what is saved
- Open weights: only if Spark Open performs the blind read
- Community vote: the coffee recording, playable without an API key
- Viral: post "It clicked the right button on the wrong booking. Iris stopped the save."

Do not build for the Muse Image creative prize.

Rules that must hold:

- New work, public repo, no secrets in git
- Invented people and prices only
- No real payment, no real inbox, no cloned cookies
- The agent never receives the host Windows desktop
- Faults planted by the developer are labeled fault injection
- Held-out tasks are scored for three systems: agent alone, button-only reviewer, Iris
- Report unauthorized saves, finished legitimate tasks, false blocks, and delay

## Done

A spoken change becomes a permission. A wrong record cannot be saved. A protected field cannot change. An exact write is read back from the database. A stale version is refused. A vague sentence pauses. Click, Enter, and HTTP share one gate. Booking and store order both use that gate. The held-out table exists. The README explains what is live. The coffee recording matches a real run.

## Order

1. Generalize the gate and make the tests pass.
2. API, both resources, invented rows, permission card.
3. Spark permission parser and browser agent. Every write waits on the gate.
4. Blind reader, then the booking coffee run, then one store-order beat.
5. Held-out measurement, voice, README, video, submission.

Do not start the virtual machine, SAM, or a second model until a wrong record is already impossible to save.
