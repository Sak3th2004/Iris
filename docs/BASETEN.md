# Muse Spark Open independent reader

The hackathon key is restricted to **`meta-models/muse-spark-open-1026`** at `https://inference.baseten.co/v1`. Iris fixes both values in its Baseten adapter. It does not use the generic slug shown in some examples.

Edit the ignored local `.env` without replacing existing settings:

```dotenv
BASETEN_API_KEY=your_private_key_here
IRIS_READER_PROVIDER=baseten
IRIS_BASETEN_SPEND_LIMIT_USD=10
```

The $10 setting is the initial development allowance, not the total grant. The application refuses a configured Baseten allowance above the $100 credit ceiling. Meta has a separate ledger and limit. These are local estimates, not provider account limits; external usage and deleting the database are outside their accounting. Check the provider dashboard too.

After changing `.env`, recreate services (a plain restart does not reload container environment):

```powershell
docker compose up -d --build
```

Open http://127.0.0.1:8768. `/api/state` reports the reader name, whether a key is present, and committed estimated spend without returning the key. Key presence alone does not prove the provider works. The browser container receives neither model key.

The parser and browser planner remain Muse Spark 1.3 Standard on Meta. Only the blind reader uses Baseten. It sees form identity, version, and values without the user's sentence or permission. Its disagreement, timeout, invalid output, or exhausted budget pauses the job, revokes permission, and saves nothing. There is no automatic fallback. `IRIS_READER_PROVIDER=meta` explicitly selects the earlier separate-prompt reader if needed; such runs do not count as Open-model evidence.

Run these bounded **paid** development checks after configuration:

```powershell
python scripts/docker_smoke.py --resource booking --require-open-reader
python scripts/docker_smoke.py --resource order --require-open-reader
```

Each creates one invented record, compiles one sentence, and lets the live browser agent choose actions. The trace in ignored `artifacts/` includes database readback, gate audit, reader checks, model identity, and both budget snapshots. They are development runs, not held-out evaluations.

Pricing reservation assumptions checked 29 October 2026: $1.25 per million input tokens and $4.25 per million output tokens, without assuming cache discounts. Output is capped at 4096 tokens, including reasoning. Only final JSON content is parsed; reasoning text is not stored as the reader answer. See [Baseten model pricing](https://www.baseten.co/library/muse-spark-open/), [reasoning behavior](https://docs.baseten.co/inference/model-apis/reasoning), and [JSON mode](https://docs.baseten.co/inference/json-mode). Hackathon-specific pricing overrides, if any, need to be reconciled against the provider dashboard.
