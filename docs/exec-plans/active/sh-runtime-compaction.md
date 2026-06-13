# SH Runtime Compaction Plan

## Purpose / Big Picture

Compact Signature Harness runtime around the global principle of minimal rails and maximum model agency. The runtime should enforce only true invariants: state transitions, evidence integrity, trace/replay, resumability, permissions, and minimal Seed identity/hash gates. It should not become a rigid process cage or a feature sink.

## Progress

- [x] Confirmed current runtime size: `scripts/sh_runtime.py` is 2,435 lines and carries 18 subcommands.
- [x] Confirmed existing command surface should remain stable for this slice.
- [x] Identified first low-risk compaction boundary: common constants, JSON IO, schema subset validation, state transition helpers, and path/hash helpers.
- [x] Extract common runtime core without changing CLI behavior.
- [x] Run compile/self-test/schema/eval smoke checks.
- [x] Record outcomes and remaining compaction candidates.

## Surprises & Discoveries

- The runtime file has clear internal boundaries already, but earlier hardening accumulated them in one script.
- The safest first move is module extraction, not command deletion.
- Existing docs and skills call `py scripts/sh_runtime.py`; preserving this entrypoint avoids host integration churn.
- `self-test` caught a single missing import (`ensure_state`) after extraction; this is exactly the kind of narrow failure this slice should surface.

## Decision Log

- Keep `scripts/sh_runtime.py` as the public CLI entrypoint.
- Move generic substrate code into `scripts/sh_runtime_core.py`.
- Do not add new commands in this slice.
- Do not add stricter schemas in this slice.
- Treat compaction as behavior-preserving unless a test reveals an existing bug.

## Outcomes & Retrospective

Completed the first runtime compaction slice without changing the public CLI surface.

What changed:

- Added `scripts/sh_runtime_core.py` for shared constants, state transitions, JSON IO, schema subset validation, ID/path/hash helpers, shell-meta checks, and evidence-string helpers.
- Kept `scripts/sh_runtime.py` as the stable command-handler entrypoint.
- Reduced `scripts/sh_runtime.py` from 2,435 lines to 2,059 lines.
- Preserved all 18 runtime subcommands.
- Updated `README.md` and `scripts/README.md` with the new internal boundary.

Validation evidence:

- `py -m py_compile scripts\sh_runtime.py scripts\sh_runtime_core.py` passed.
- `py scripts\sh_runtime.py self-test` passed.
- `py scripts\sh_runtime.py validate-schemas --root .` passed.
- `py scripts\sh_runtime.py run-evals --root . --suite evals\benchmark_tasks.jsonl --trials 3 --eval-run-id compaction-benchmark --reset-existing` passed: 20 tasks, 60 trials, pass rate 1.0.
- `py scripts\sh_runtime.py run-evals --root . --suite evals\regression_tasks.jsonl --trials 3 --eval-run-id compaction-regression --reset-existing` passed: 4 tasks, 12 trials, pass rate 1.0.
- `py scripts\sh_runtime.py verify-ledger --root .` passed.
- `git diff --check` passed.

Remaining compaction candidates:

- Extract evidence/workflow validation into a focused module only if future edits touch that area.
- Extract run lifecycle and trace/replay only after another feature or bug fix requires it.
- Keep eval runner optional; do not expand command surface.
- Defer Minimal SDD Contract until runtime core boundaries have settled.

## Context and Orientation

Relevant files:

- `scripts/sh_runtime.py`
- `scripts/README.md`
- `schemas/tool_contracts.json`
- `docs/exec-plans/active/sh-runtime-evals-observability.md`

## Plan of Work

1. Extract generic runtime core.
2. Keep command handlers in the CLI script.
3. Verify all existing deterministic checks still pass.
4. If safe, update docs to note the new module boundary.

## Concrete Steps

- Add `scripts/sh_runtime_core.py`.
- Import constants/helpers from the new module.
- Remove duplicated definitions from `scripts/sh_runtime.py`.
- Update the short runtime file map without changing the public command surface.
- Run `py -m py_compile scripts/sh_runtime.py scripts/sh_runtime_core.py`.
- Run `py scripts/sh_runtime.py self-test`.
- Run `py scripts/sh_runtime.py validate-schemas --root .`.
- Run benchmark/regression eval smoke if compile/self-test pass.

## Validation and Acceptance

Acceptance:

- CLI usage stays `py scripts/sh_runtime.py <subcommand>`.
- No command is added or removed.
- `self-test` passes.
- `validate-schemas` passes.
- Benchmark and regression evals pass with deterministic fixtures.
- `git diff --check` passes.

## Idempotence and Recovery

This slice is source-only and reversible. Runtime artifacts under `.sh/` are ignored. If the extraction breaks imports, restore the imported helper in `scripts/sh_runtime.py` or move only the failing helper back.

## Artifacts and Notes

Planned artifact:

- `scripts/sh_runtime_core.py`

## Interfaces and Dependencies

- Python standard library only.
- No host plugin integration changes.
- No new user-facing commands.
