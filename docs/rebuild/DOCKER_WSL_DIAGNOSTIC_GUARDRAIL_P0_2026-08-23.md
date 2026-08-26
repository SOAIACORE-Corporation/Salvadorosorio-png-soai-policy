# SOAIACORE · Docker/WSL Diagnostic Guardrail · Rebuild P0 · 2026-08-23

## Status

- Scope: implementation/runtime diagnostic guardrail.
- Architecture authority: `SOAIACORE Architecture v0.6 FINAL / FROZEN FOR P0`.
- Architecture delta: NONE.
- Azure apply: FORBIDDEN.
- Cloud resources: 0.

## Trigger

Use this guardrail whenever Docker Desktop reports `wslUpdateRequired=true`, `WSL version check failed`, `wsl.exe --version exit != 0` or equivalent while a direct interactive/elevated invocation of `%SystemRoot%\System32\wsl.exe --version` succeeds.

## Current evidence baseline

Observed on the P0 Windows host:

- BIOS virtualization: visually verified enabled.
- Direct/elevated WSL: `2.9.3.0`, exit `0`.
- Docker backend WSL version check: exit `1`.
- Docker internal flag: `wslUpdateRequired=true`.

Therefore the Docker flag alone is **not sufficient evidence that host WSL is outdated**. The discrepancy must be treated as an execution-context/data-quality conflict until resolved.

## Evidence precedence

1. Direct execution of `%SystemRoot%\System32\wsl.exe` in the host context.
2. Direct execution of the `docker-desktop` WSL distribution probe.
3. Docker Engine server readiness (`docker info`).
4. Docker backend/process/log evidence.
5. Docker UI/internal `wslUpdateRequired` flag.

A lower-ranked contradictory signal cannot by itself trigger destructive or state-changing remediation.

## Mandatory precheck

Run the read-only diagnostic entrypoint:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\deploy\local\SOAIACORE-DockerWsl-Diagnostic-OneShot.ps1" -RepoPath "$PWD"
```

The diagnostic must capture:

- exact `wsl.exe` resolution and `%SystemRoot%\System32\wsl.exe` result;
- WSL version/status/distribution list;
- `docker-desktop` distribution probe;
- Docker CLI/Desktop/Engine/Compose state;
- `com.docker.backend.exe` path, PID, parent, command line and owner where obtainable;
- Docker service state;
- non-destructive Docker diagnostic result when available;
- relevant Docker log evidence for `wslUpdateRequired`, `wsl.exe`, `--version`, `exit status 1`, backend/engine failures.

## Prohibited actions until classification

Do **not** perform any of the following solely because `wslUpdateRequired=true`:

- repeat `wsl --update`;
- reinstall WSL;
- `wsl --unregister` any distribution;
- delete/reset `docker-desktop`, Docker data, VHDX, images, containers or volumes;
- Docker Factory Reset / Clean up data;
- change the backend to Hyper-V as a workaround;
- modify BIOS/UEFI;
- delete Docker AppData;
- modify global PATH as a workaround;
- reboot Windows;
- create Azure/cloud resources.

## Classification

The diagnostic must produce one of these states:

- `DOCKER_ENGINE_READY`: `docker info` has a valid server. Resume the canonical SOAIACORE rebuild one-shot immediately.
- `HOST_WSL_FAILURE`: direct `%SystemRoot%\System32\wsl.exe` probe fails.
- `DOCKER_DESKTOP_WSL_DISTRO_FAILURE`: direct host WSL succeeds but the `docker-desktop` distribution probe fails or the distribution is unavailable.
- `DOCKER_BACKEND_WSL_CONTEXT_MISMATCH`: direct host WSL succeeds and Docker-specific evidence shows the backend failing/misreading the WSL version context.
- `DOCKER_ENGINE_NOT_READY_DIAGNOSTIC_CAPTURED`: evidence is insufficient for a narrower root cause; stop with diagnostics, not destructive remediation.

## Repair policy after classification

- Prefer the smallest implementation-level fix.
- If host WSL is healthy, do not touch WSL just to satisfy a contradictory Docker flag.
- If Docker Desktop is demonstrably outdated and an in-place update is warranted, prefer an in-place Docker Desktop update preserving data/configuration over WSL reinstall/reset.
- If the installed Docker version is current, investigate backend identity/path/context and logs before changing machine state.
- Any repair must be followed by `docker version`, `docker info`, and `docker compose version`.
- Only valid Docker Client + Server readiness authorizes continuation to PostgreSQL+pgvector.

## Return to canonical one-shot

When `DOCKER_ENGINE_READY=true`, resume the same canonical entrypoint/checkpoint:

```powershell
.\deploy\local\SOAIACORE-RebuildP0-OneShot.ps1
```

Continue through PostgreSQL+pgvector → migrations → tests → teardown → receipts.

Allowed terminal states remain:

```text
SOAIACORE_LOCAL_POSTGRES_GATE=PASS
```

or

```text
SOAIACORE_LOCAL_POSTGRES_GATE=BLOCKED :: <EXACT_ROOT_CAUSE>
```

This guardrail does not create a second architecture or deployment path; it is a diagnostic gate protecting the existing one-shot from false-positive remediation.
