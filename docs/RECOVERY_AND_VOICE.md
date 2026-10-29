# Recovery and recording-start permissions

## Worker ownership and recovery

Each worker process generates a fresh session UUID. The restricted gateway requires it in `X-Iris-Worker-ID` for job requests. A queued job has 60 seconds to be claimed. Its running lease lasts 20 seconds; an independent worker task renews it every three seconds, including while the planner or reader is waiting on a provider. Losing a heartbeat stops the worker from executing further actions. Heartbeats cannot revive expired or terminal jobs, and another worker session cannot renew the lease.

The gateway sweeps expired jobs every two seconds without an owner page open. Write transactions also check expiry directly. Expiry revokes permission and pauses the task; it does not queue it for automatic replay. Stop also revokes permission. A newly restarted worker can claim only a fresh owner-authorized job.

The record update, permission consumption, write audit, durable job receipt, and completion status share one SQLite transaction. If receipt persistence fails, all those changes roll back. This closes the former gap where a record could be saved while its job still appeared running. Legacy interrupted jobs are reconciled against successful audit receipts; committed work is marked complete without replaying it.

`GET /api/runs/{id}` retrieves the job's own receipt, reader checks, and events. The owner write endpoint cannot use a permission already assigned to a worker to bypass its lease. Authentication remains local-development scope, not multi-user cloud authentication. Worker session IDs are ownership identifiers within the authenticated gateway, not remote attestation.

Paid development trial: `python scripts/recovery_check.py` stops **only** Iris's browser container, waits for expiry, attempts a labeled stale-permission write, restarts the browser, then completes a newly authorized task. See [actual evidence](evidence/recovery.json). The injected interruption is not an agent mistake. The Docker host remaining alive is assumed; this does not establish recovery from filesystem corruption or loss of the persistent volume.

## Voice snapshot lifecycle

1. The browser obtains microphone access and initializes its AudioWorklet.
2. `POST /api/voice/start` stores the current records and versions on the server.
3. Only then does the worklet begin collecting samples. Audio is encoded as mono 16-bit 24 kHz WAV, resampling from the actual AudioContext rate when necessary.
4. `POST /api/voice` carries `X-Iris-Capture-ID`. A capture can start one transcription attempt; a failed attempt requires a new recording. Meta Voice Transcribe returns the sentence.
5. Permission interpretation receives that sentence and the stored recording-start records. The browser cannot supply substitute record versions.
6. Permission locking checks the current target version against the stored version and consumes the capture in the same transaction as creating permission. A changed record is refused. Snapshots expire after ten minutes.

Editing a transcript retains its original snapshot. The UI provides an explicit “Use as a new typed instruction” action for starting over with a typed sentence. An ambiguous sentence asks for clarification without consuming the snapshot. Starting another recording captures fresh versions.

`python scripts/voice_browser_check.py` generates labeled synthetic speech using Windows' local speech engine and sends it through Chromium's microphone test device. It then uses the actual AudioWorklet, paid Meta transcription, Spark parser/planner, Baseten reader, and isolated browser write. The fixture script uses a process-only PowerShell execution-policy override; it does not change the machine's policy. No synthetic speech is presented as a human recording. See [actual evidence](evidence/voice-synthetic.json).

The observed transcript repeated “booking” and “unchanged”; the stored trace preserves that actual output. The intended booking and constraints were still parsed correctly, and the saved record was read back. A human microphone trial, noisy-accent testing, and the final coffee recording remain outstanding.
