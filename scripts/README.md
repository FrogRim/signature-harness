# SH Runtime Substrate

This folder contains small mechanical helpers for Signature Harness. These are
not a standalone product CLI; they only handle checks that should be
deterministic instead of prompt-driven.

Implementation boundary:

- `sh_runtime.py` is the stable CLI entrypoint and command-handler surface.
- `sh_runtime_core.py` holds shared invariants and deterministic helpers such
  as state transitions, JSON IO, schema subset validation, path checks, and
  hashing.

Use `py` on Windows when `python` resolves to the Windows Store stub:

```powershell
py scripts/sh_runtime.py self-test
```

## Commands

```powershell
py scripts/sh_runtime.py init-state --root .
py scripts/sh_runtime.py validate-transition --from-state RUNNING --event oracle_incomplete --to-state GAP_FILL
py scripts/sh_runtime.py hash-manifest --manifest .sh/hash-manifest.json
py scripts/sh_runtime.py validate-resume --contract .sh/resume-checks/auth-smoke.json --receipt .sh/orchestration/blocked/run_1.json
py scripts/sh_runtime.py validate-workflow-evidence --evidence .sh/workflows/wf_001.json
py scripts/sh_runtime.py validate-workflow-evidence --evidence .sh/workflows/wf_001.json --root . --require-artifacts
py scripts/sh_runtime.py validate-workflow-evidence --evidence .sh/workflows/wf_001.json --root . --require-artifacts --evidence-manifest .sh/evidence/hash-manifest.json
py scripts/sh_runtime.py validate-completion-artifact --artifact evals/fixtures/evidence/sut_hang_timeout.json
py scripts/sh_runtime.py write-directive --run-id run_1 --from-state RUNNING --event oracle_incomplete --to-state GAP_FILL
py scripts/sh_runtime.py append-ledger --entry .sh/events/event.json
py scripts/sh_runtime.py verify-ledger --root .
py scripts/sh_runtime.py start-run --root . --goal-id smoke_goal --seed-id smoke_seed --active-slice smoke_slice --objective "Smoke runtime"
py scripts/sh_runtime.py record-step --root . --run-id <run_id> --step-id step_1 --operation-name inspect --state-before RUNNING --state-after RUNNING --artifact README.md
py scripts/sh_runtime.py record-interruption --root . --run-id <run_id> --kind pause --reason "smoke pause"
py scripts/sh_runtime.py resume-run --root . --run-id <run_id> --reason "smoke resume"
py scripts/sh_runtime.py replay-run --root . --run-id <run_id>
py scripts/sh_runtime.py validate-schemas --root .
py scripts/sh_runtime.py validate-release --root .
py scripts/sh_runtime.py validate-policy --root . --policy security/policy.json --action-file security/fixtures/read_only_ok.json
py scripts/sh_runtime.py run-evals --root . --suite evals/benchmark_tasks.jsonl --trials 3
```

`validate-schemas` checks JSON schema files, tool contracts, failure taxonomy,
eval task fixtures, the security policy presence, and plugin/marketplace
manifest identity. It also reports the separated `plugin_version`,
`runtime_version`, and `schema_version` surface. Manifest descriptions and
host-specific interface fields may differ, but every present manifest must keep
the same `name` and `version`.

`validate-release` is the thin release gate. It reuses the schema/eval/manifest
checks, confirms the security policy exists, verifies Thin Contract Patch
anchors in README/AGENTS/skills/templates, rejects forbidden prompt-template
phrases such as `production-grade`, `100%`, and `auto-commit`, and reports the
same explicit version surface. It exits `9` when a release contract fails.

`run-resume` intentionally fails closed until a real sandbox adapter exists.
Unsafe local execution would violate the resume-check security contract.

`validate-resume` can bind a resume contract to the blocked receipt that named
it. The receipt must include `resume_check_id` and
`resume_check_contract_sha256`; otherwise a newly generated but well-formed JSON
contract is rejected.

`validate-workflow-evidence` checks the dynamic workflow evidence contract. It
accepts only the canonical patterns, validates the cost gate, confirms that done
records have evidence, and reports whether Oracle may treat the workflow as
completion-eligible. Exit code `0` means `COMPLETE_ELIGIBLE`, `2` means invalid
schema, and `5` means schema-valid but `INCOMPLETE`. A valid schema with
`completion_allowed: false` should become an Oracle `INCOMPLETE` verdict and an
orchestration `GAP_FILL` slice.
By default the CLI requires artifact-backed evidence. Add
`--allow-descriptive-evidence` only for legacy or low-risk checks that
explicitly permit descriptive strings. Add
`--evidence-manifest <path>` to require those files to appear in a prior
`hash-manifest` output's `evidence_assets` with matching `sha256` and `size`.

`validate-completion-artifact` checks Completion Auditor artifacts emitted by an
external runner. It does not execute, kill, or clean up the SUT. `sut_tick_hang`
artifacts use `observed_at - started_at >= duration_ms` plus unchanged
previous/current hashes to recommend `INCOMPLETE` and `REMEDIATING`.
`remediation_evidence` artifacts gate cleanup/reset proof: valid evidence returns
`GAP_FILL`, invalid-but-open evidence stays `REMEDIATING`, and expired evidence
recommends `ABORTED`. Exit code `0` means the artifact is valid with no
fail-closed gate, `2` means invalid schema, `5` means incomplete/remediation
handling is required, and `6` means remediation timeout.

The durable runner commands create ignored runtime artifacts under
`.sh/runs/<run_id>/`: `run_manifest.json`, `state.json`,
`step_ledger.jsonl`, `interruptions.json`, `handoff.md`, `replay.json`,
`trace.jsonl`, `tool_calls.jsonl`, `cost_latency.json`, and `artifacts.json`.
`replay-run` reconstructs the core run flow from those artifacts.
If `record-step` changes state, pass `--event <state-machine-event>`; the event must match the canonical transition map. Same-state trace rows do not require an event.

`run-evals` executes repo-local deterministic benchmark fixtures. It writes
`.sh/evals/<eval_run_id>/eval_result.json`,
`.sh/evals/<eval_run_id>/scorecard.json`, and
`.sh/evals/<eval_run_id>/transcript_review.md`, and returns exit code `8` when
any trial fails. `scorecard.json` aggregates Completion Auditor product metrics
such as false-completion detection, evidence-gap detection, unsafe-resume
blocking, no-progress detection, remediation gating, and runtime overhead.
Eval tasks must reference existing `expected_artifacts`; selected fixtures can also invoke the workflow evidence validator, resume contract validator, or policy validator as part of grading.
Eval tasks may also invoke the Completion Auditor artifact validator with
`fixture.validator.type: completion_artifact`.

`append-ledger` writes `prev_hash` and `entry_hash`; callers may not provide
chain-reserved keys. `verify-ledger` checks the full hash chain and exits `6`
on the first integrity failure.

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
- run `-DryRun` before forceful local development installs
- `-Force` backs up an unmarked target to `*.sh-backup-<timestamp>` before installing
- all writes are limited to `.codex`, `.claude`, and `.signature-harness` under the selected `-HomeDir`
