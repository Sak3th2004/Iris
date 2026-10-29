# Isolated browser worker

The selected and verified deployment is now the [dedicated Docker browser inside Docker Desktop's Linux VM](DOCKER_DESKTOP.md). It streams real browser frames to the owner UI. The instructions below describe an alternative full Linux guest and SSH-forwarding setup, which has **not** been exercised.

The owner service runs on Windows at 127.0.0.1:8765. A separate restricted gateway on 127.0.0.1:8766 exposes records, job claiming, model steps, and gated writes. It has **no permission issuance or record creation routes**. Do not expose the owner port to the VM. The model cannot run shell commands or choose external URLs; its tools are open record, fill field, save, and pause.

1. Provision a Linux VM with a graphical session, Python 3.11+, OpenSSH and Chromium dependencies. No shared host folders, browser profile, clipboard, cookies, or host desktop access.
2. Generate a random worker token (at least 32 characters). Put it in the owner's ignored `.env` as `IRIS_WORKER_TOKEN`. Give the worker the same token as an environment variable. Do not give it the Meta key.
3. Start the owner API, then the restricted gateway on the host:

   ```powershell
   python -m uvicorn iris.worker_api:create_worker_app --factory --app-dir backend --host 127.0.0.1 --port 8766
   ```

4. From the host, forward **only** the gateway to the VM with `ssh -R 8766:127.0.0.1:8766 user@VM_IP`. Configure the VM network/firewall to deny access to the owner's port and other host services. Restrict VM egress to the gateway. Verify those rules before running the worker. The browser route allowlist is defense in depth, not a replacement for network isolation.
5. Copy only `worker/run.py` into the VM. Install `httpx` and `playwright` there, and run `python -m playwright install --with-deps chromium`.
6. Lock a permission in the owner UI, then choose **Send to agent**. Inside the VM graphical session run `python run.py`.

The worker checks Linux virtualization using `systemd-detect-virt --vm`, creates a fresh Chromium context, and records its actual browser video in `recordings/`. This runtime check is a guard against accidental host execution, not a security attestation. A job gets at most 12 planner calls. Every attempted agent save invokes a separate blind-reader call that receives only the captured form, not the sentence or planner answer. Disagreement pauses the job; agreement still requires the deterministic gate to allow the write. The gateway now defaults to the Baseten Open reader; see [configuration](BASETEN.md).

The Docker worker is persistent and has completed both resource types with live streaming and network-isolation probes. The alternative `worker/run.py` above processes one job and exits. Remaining submission work includes real adversarial runs, broader interruption/recovery checks, Cal integration, voice validation, held-out measurement, and recording. A paused or expired job requires a new owner permission.
