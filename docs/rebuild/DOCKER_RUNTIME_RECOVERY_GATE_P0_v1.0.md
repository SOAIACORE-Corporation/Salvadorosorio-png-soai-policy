# SOAIACORE · Docker Runtime Recovery Gate · P0 v1.0

Status: ACTIVE diagnostic addendum for `WS-SOAIACORE-REBUILD-P0-001`.
Architecture authority remains `SOAIACORE Architecture v0.6 FINAL / FROZEN FOR P0`.
This addendum does not authorize Azure apply or cloud resource creation.

## Trigger

Use this gate when the canonical local entrypoint returns:

`SOAIACORE_LOCAL_POSTGRES_GATE=BLOCKED :: DOCKER_ENGINE_NOT_READY_AFTER_SELF_HEAL`

Firmware virtualization has already been visually verified enabled on the target ThinkPad. It must not be reclassified as disabled from a single WMI/CIM signal without corroborating evidence.

## Operating rule

No more blind reboot/reinstall loops. Diagnose first, classify the failing layer, then apply only the narrow repair justified by evidence. Preserve the same idempotent one-shot/checkpoint model.

## PRECHECK / diagnostic evidence

Capture before mutation:

- Windows edition/build and pending reboot state.
- Optional-feature states: `Microsoft-Windows-Subsystem-Linux`, `VirtualMachinePlatform`, and Hyper-V when exposed.
- `bcdedit /enum {current}` and `hypervisorlaunchtype`.
- `Win32_ComputerSystem.HypervisorPresent` plus available CPU virtualization signals; do not trust a single firmware flag alone.
- service state for `vmcompute`, `hns`, `WslService` and/or `LxssManager` when present, and `com.docker.service` when present.
- `wsl --version`, `wsl --status`, `wsl -l -v`.
- if `docker-desktop` exists: `wsl -d docker-desktop sh -lc "uname -a; echo DOCKER_DESKTOP_WSL_OK"`.
- Docker Desktop version, `docker desktop status`, `docker context ls`, `docker version`, `docker info`, `docker compose version` when supported.
- Docker Desktop diagnostics using `docker desktop diagnose` when available; otherwise gather with the installed `com.docker.diagnose.exe` tool. Do not require upload to continue local diagnosis.
- relevant Docker Desktop logs, especially `%LOCALAPPDATA%\Docker\log\vm\init.log` and recent backend logs.
- disk free space and RAM availability sufficient for WSL/Docker startup.

Persist a redacted diagnostic summary under `%ProgramData%\SOAIACORE\RebuildP0\diagnostics\` and include its path/hash in the gate receipt. Do not persist credentials, tokens or unrelated personal data.

## Failure classification

### A · WSL_BASE_NOT_OPERATIONAL

`wsl --status` / `wsl -l -v` cannot operate or a trivial WSL2 execution fails.

Repair only WSL/VirtualMachinePlatform/hypervisor prerequisites. Reboot only when Windows reports a real pending restart or a changed boot/feature state requires one.

### B · DOCKER_DESKTOP_WSL_DISTRO_NOT_OPERATIONAL

Base WSL works, but `docker-desktop` is missing or cannot execute.

First update/repair Docker Desktop non-destructively and restart WSL/Desktop. Do **not** unregister Docker WSL distributions, reset to factory defaults, delete VHDX/data, or run destructive cleanup without a separate explicit authorization gate.

### C · DOCKER_BACKEND_STARTUP_FAILURE

`docker-desktop` WSL executes, but Desktop/backend/engine does not become ready.

Use Docker diagnostics and logs to identify the exact backend error. Apply only the specific non-destructive repair. Prefer an in-place Docker Desktop update/repair if the installed version is behind a currently available stable version and diagnostics do not identify a narrower cause.

### D · DOCKER_ENGINE_READY

`docker info` and `docker compose version` both pass. Immediately resume the existing PostgreSQL+pgvector gate; do not stop for another human decision.

## Safety constraints

- No `docker system prune`, factory reset, distro unregister, VHDX deletion or Docker data wipe as part of automatic recovery.
- No blind repeated reboot.
- No Azure apply; `AZURE_APPLY_EXECUTED=false` and `CLOUD_RESOURCES_CREATED=0` remain invariants.
- No architecture change.
- Do not run the separate Windows cleanup/optimization task concurrently with active WSL/Docker recovery.

## One-shot hardening requirement

Codex must incorporate the diagnostic/classification logic into the same canonical entrypoint `deploy/local/SOAIACORE-RebuildP0-OneShot.ps1` (next implementation revision) rather than requiring an operator to chain a second script. A rerun must reuse the existing checkpoint and skip already-validated prerequisites.

## Exit

Success:

`DOCKER_RUNTIME_GATE=PASS`
`SOAIACORE_LOCAL_POSTGRES_GATE=PASS`

Blocked:

Return one precise classified blocker plus diagnostic receipt. Do not fall back to generic `DOCKER_ENGINE_NOT_READY_AFTER_SELF_HEAL` once the diagnostic evidence can name the failing layer.
