# SH Runtime Substrate

This folder contains small mechanical helpers for Signature Harness. These are
not a standalone product CLI; they only handle checks that should be
deterministic instead of prompt-driven.

Use `py` on Windows when `python` resolves to the Windows Store stub:

```powershell
py scripts/sh_runtime.py self-test
```

## Commands

```powershell
py scripts/sh_runtime.py init-state --root .
py scripts/sh_runtime.py validate-transition --from-state RUNNING --event oracle_incomplete --to-state GAP_FILL
py scripts/sh_runtime.py hash-manifest --manifest .sh/hash-manifest.json
py scripts/sh_runtime.py validate-resume --contract .sh/resume-checks/auth-smoke.json
py scripts/sh_runtime.py write-directive --run-id run_1 --from-state RUNNING --event oracle_incomplete --to-state GAP_FILL
py scripts/sh_runtime.py append-ledger --entry .sh/events/event.json
```

`run-resume` intentionally fails closed until a real sandbox adapter exists.
Unsafe local execution would violate the resume-check security contract.

## Fallback Local Install

Prefer plugin-native installation from the repository root:

```powershell
claude plugin marketplace add FrogRim/signature-harness
claude plugin install signature-harness
codex plugin marketplace add FrogRim/signature-harness
```

Claude Code exposes `plugin install` directly. Current Codex CLI builds may only
register the marketplace source; if the host does not expose plugin enable/install
yet, use this fallback installer for Codex skill files.

Use the fallback installer when developing the harness locally or when a host
plugin marketplace is unavailable.

Install the portable skills and Claude slash commands into the user-local Codex
and Claude folders, plus a self-contained bundle under `~/.signature-harness`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_local.ps1
```

The installer is marker-based:

- directories/files previously installed by Signature Harness are updated
- existing unmarked user files are skipped as conflicts
- `-Force` is required to overwrite an unmarked target
