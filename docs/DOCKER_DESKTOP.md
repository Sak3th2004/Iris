# Dedicated browser inside Docker Desktop's Linux VM

This deployment uses three services. It is a container inside Docker Desktop's Linux VM, not a separate full guest operating system per agent.

- `owner`: permission UI/API, published only on **127.0.0.1:8768**.
- `gateway`: token-authenticated worker endpoints, no published ports, no permission-creation endpoints. It has outbound access for Meta calls.
- `browser`: headed Chromium on Xvfb, non-root user, no mounted folders, no published ports, no Meta key, no Docker socket. Its only network is the internal browser network shared with the gateway. Model-selected actions are limited to opening owned records, filling fields, saving and pausing.

Owner and gateway share a Docker-managed database volume. This deployment uses a separate database from the original host development server. The browser cannot mount or access that volume. Do not attach the browser to the control network or publish the gateway.

## Start

Set `MODEL_API_KEY` and a random `IRIS_WORKER_TOKEN` (at least 32 characters) in the ignored `.env`. The worker receives only its own token; provider secrets stay in the services that call Meta. The Docker build context is an allowlist; `.env` and the reference repo are not included.

```powershell
docker compose up -d --build
```

Open http://127.0.0.1:8768. Once a real frame arrives, the viewer reports connected. Lock a sentence and send it to the agent. The worker keeps running and streaming after the task finishes. No model calls are made while idle.

The owner viewer polls fresh JPEG frames captured from the actual browser viewport. It is read-only, not host desktop capture. A pointer overlay follows actual browser mouse events. Frames older than five seconds are refused and the viewer shows disconnected. Execution events describe completed actions, not private model reasoning. Stop revokes the permission transactionally; already-committed writes remain committed.

## Verify and stop

`python scripts/docker_smoke.py --resource booking` and `--resource order` create new invented records and issue real paid model tasks. Actions are chosen by Spark, not the test script. Raw traces go into ignored `artifacts/`; they are integration evidence, not held-out evaluation.

```powershell
docker compose logs --tail 40 browser
docker compose stop
```

Stopping retains the database volume. Do not use `down -v` unless deliberately deleting the Iris data. Other Docker projects are unaffected by this Compose project.

The screenshot pipeline is infrastructure, not a proof of VM attestation. Container isolation and browser sandboxing are distinct: Playwright's default Chromium sandbox setting is not a hardened arbitrary-web browsing configuration. This worker is restricted to Iris-owned content. Broader browsing requires a separate security review and hardened browser configuration.
