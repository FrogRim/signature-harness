# SH Runtime, Evals, Observability, And Security Plan

## Purpose / Big Picture

Raise Signature Harness from a prompt-plus-substrate MVP to a repo-local, runnable completion-auditor harness for AI coding agents. The work must add executable runtime state, trace, replay, schema contracts, artifact-backed evidence, eval fixtures, benchmark reporting, and least-privilege policy checks without claiming host integration that has not run.

Primary vertical: **AI coding-agent completion auditor**.

## Progress

- [x] Reconfirmed repo surface: `scripts/sh_runtime.py`, plugin manifests, `skills/`, `templates/`, `agents/`, `commands/`, and ignored `.sh/` runtime path.
- [x] Created this living execution plan before runtime edits.
- [x] Add runner lifecycle artifacts under `.sh/runs/<run_id>/`.
- [x] Add trace, tool-call, cost/latency, artifact index, and replay substrate.
- [x] Add machine-readable schemas and centralized tool contracts.
- [x] Add failure taxonomy and recovery mapping.
- [x] Strengthen artifact-backed evidence validation.
- [x] Add repo-local eval/benchmark suite with at least 20 tasks and 3-trial default.
- [x] Add permission profile and approval logging checks.
- [x] Add vertical-specific glossary, rubric, failure corpus, demo, and scorecard.
- [x] Run verification and write final evidence map.
- [x] UltraQA hardening: state transition bypass must fail.
- [x] UltraQA hardening: malformed tool/eval/security contracts must fail schema validation.
- [x] UltraQA hardening: eval tasks with missing expected artifacts must fail.
- [x] UltraQA hardening: permission profile filesystem/network allowlists must be enforced.
- [x] UltraQA recheck after repeated stop hook: fresh `ultraqa-recheck-20260613-031613-*` eval artifacts produced, `omx state` confirmed inactive/cleared.
- [x] UltraQA stale stop-hook cleanup: session-scoped `ultraqa-state.json` and `skill-active-state.json` removed with `omx state clear --all_sessions` via direct Node argv; fresh `ultraqa-recheck-20260613-031816-*` eval artifacts produced.

## Surprises & Discoveries

- `.sh/` is ignored and currently absent in the working tree; runtime commands can create it without adding tracked session state.
- Existing substrate already has transition validation, hash manifests, resume contract validation, workflow evidence validation, directive writing, ledger hash-chain, and self-test.
- Current artifact-backed workflow sample intentionally fails when `--require-artifacts` is used because the sample `.sh/evidence/...` artifacts do not exist.
- PowerShell heredoc syntax is not portable for quick Python validation; use `py -c` or repo validators instead.
- `run-evals` originally wrapped failed eval suites with `ok: true`; it now returns `ok: false` and exit `8` when any trial fails.
- The realistic security boundary for this pass is policy validation plus fail-closed execution, not OS/container sandbox execution.
- UltraQA repro found `record-step` can force `RUNNING -> COMPLETE` without an event or Oracle verdict.
- UltraQA repro found `validate-schemas` accepts malformed contract field types because it checks required keys rather than applying schema rules.
- UltraQA repro found `run-evals` can pass a task whose `expected_artifacts` path does not exist.
- UltraQA repro found `scoped_network` can write outside its declared `.sh/` write allowlist.
- Repeated stop-hook prompts can report stale UltraQA activity even when `omx state list-active` is empty; direct `node ... omx.js` invocation preserves JSON argv better than the npm PowerShell wrapper.
- The stale source was not root `.omx/state/ultraqa-state.json`; it was session-scoped `.omx/state/sessions/019eaaf5-bdd5-79b0-b381-9ba8da5e0227/ultraqa-state.json` plus `skill-active-state.json`.

## Decision Log

- Keep public command surface small; add substrate subcommands rather than new user-facing slash/skill commands.
- Use repo-tracked `schemas/`, `evals/`, `security/`, and `docs/domain/completion-auditor/` for durable contracts and fixtures.
- Keep run outputs in ignored `.sh/` so smoke tests can prove runtime behavior without polluting git history.
- Do not implement unrestricted command execution. Permission checks and approval artifacts come first; actual dangerous actions remain non-executable in this substrate.
- Keep benchmark grading deterministic and repo-local for now; do not claim LLM transcript judging until there is a real grader integration.
- Score the result as repo-local harness quality, not host-integrated product quality.
- UltraQA hardening must make adversarial failure cases executable, not just documented. Scorecard cannot return to 95+ until the four repros above fail closed.

## UltraQA Scenario Matrix

| ID | User/attacker model | Scenario | Command/harness | Expected signal | Actual result | Status | Evidence | Cleanup |
|----|---------------------|----------|-----------------|-----------------|---------------|--------|----------|---------|
| ADV-E2E-001 | Malicious/over-optimistic agent | Force `RUNNING -> COMPLETE` through `record-step` without Oracle event | temp `.sh` run under `%TEMP%` | nonzero exit; state remains `RUNNING` | fixed: exit `2`, state stayed `RUNNING` | passed | temp harness output | temp-only |
| ADV-E2E-002 | Contract author with malformed schema fields | Set `tool_contracts.json.inputSchema` and `timeout_sec` to strings | temp copied `schemas/` | `validate-schemas` exits nonzero | fixed: exit `2`, type mismatch findings | passed | temp harness output | temp-only |
| ADV-E2E-003 | Eval author hiding missing proof | Eval task references missing `expected_artifacts` while fixture says pass | temp custom eval suite | `run-evals` exits `8` or infra failure | fixed: exit `8`, pass rate `0.0` | passed | temp harness output | temp-only |
| ADV-E2E-004 | Action author abusing broad policy gap | `scoped_network` writes `README.md` outside `.sh/` write allowlist | temp action JSON | `validate-policy` exits `7`, BLOCKED | fixed: exit `7`, `write is outside profile allowlist` | passed | temp harness output | temp-only |

## Outcomes & Retrospective

Implemented repo-local runtime, trace/replay, schema contracts, failure taxonomy, deterministic eval suite, artifact-backed evidence validation, security policy fixtures, approval logging, vertical completion-auditor docs, and CI contract checks. Validation passed for self-test, py_compile, schema validation, benchmark suite, regression suite, plugin manifest validation, policy fixtures, replay smoke, ledger verification, and `git diff --check`.

Residual gaps are explicit: host-level Codex/Claude end-to-end execution was not run, `run-resume` still fails closed without a sandbox adapter, and eval graders are deterministic fixtures rather than model-judged transcripts.

## Context and Orientation

Current runtime entrypoint: `py scripts/sh_runtime.py <subcommand>`.

Existing subcommands:

- `init-state`
- `validate-transition`
- `hash-manifest`
- `validate-resume`
- `validate-workflow-evidence`
- `run-resume`
- `write-directive`
- `append-ledger`
- `verify-ledger`
- `self-test`

Existing docs/skills define the loop, but many guarantees are still prompt contracts. The implementation work should move guarantees into validators, generated artifacts, replayable traces, and eval results.

## Plan of Work

1. Extend `scripts/sh_runtime.py` with run lifecycle commands:
   - `start-run`
   - `resume-run`
   - `record-step`
   - `record-interruption`
   - `replay-run`
   - `validate-schemas`
   - `validate-policy`
   - `run-evals`
2. Add JSON Schemas and contract files under `schemas/`.
3. Add eval task corpus and resource spec under `evals/`.
4. Add security policy profiles under `security/`.
5. Add vertical-specific assets under `docs/domain/completion-auditor/`.
6. Update `scripts/README.md` and short README references only after runtime exists.
7. Run smoke tests and record evidence.

## Concrete Steps

- Create schema files for run manifest, trace event, eval task, tool contracts, failure taxonomy, and security policy.
- Implement runtime helpers for JSONL append, run directories, trace span ids, cost/latency aggregation, artifact index, and handoff generation.
- Implement eval runner that reads 20+ static benchmark tasks, simulates grader outcomes from fixture definitions, produces `.sh/evals/<run_id>/eval_result.json`, and includes cost/duration/retry/tool-error aggregates.
- Implement evidence validation strict mode so high-risk/dynamic workflows require artifact-backed evidence.
- Implement policy validation for permission profiles, network allowlist, dangerous shell tokens, out-of-workspace writes, and approval artifacts.
- Expand self-test to cover runner start/resume/replay, schema validation, eval run, policy checks, and evidence-less completion failure.

## Validation and Acceptance

Acceptance checks:

- `py scripts/sh_runtime.py self-test`
- `py -m py_compile scripts/sh_runtime.py`
- `py scripts/sh_runtime.py validate-schemas --root .`
- `py scripts/sh_runtime.py start-run --root . --goal-id smoke_goal --seed-id smoke_seed --active-slice smoke_slice --objective "Smoke runtime" --run-id smoke-runtime --reset-existing`
- `py scripts/sh_runtime.py record-step --root . --run-id smoke-runtime --step-id step_1 --operation-name inspect --tool-name rg --state-before RUNNING --state-after RUNNING --artifact README.md`
- `py scripts/sh_runtime.py record-interruption --root . --run-id smoke-runtime --kind pause --reason "smoke pause"`
- `py scripts/sh_runtime.py resume-run --root . --run-id smoke-runtime --reason "smoke resume"`
- `py scripts/sh_runtime.py replay-run --root . --run-id smoke-runtime`
- `py scripts/sh_runtime.py run-evals --root . --suite evals/benchmark_tasks.jsonl --trials 3`
- `py scripts/sh_runtime.py validate-policy --root . --policy security/policy.json --action-file security/fixtures/read_only_ok.json`
- `py scripts/sh_runtime.py validate-policy --root . --policy security/policy.json --action-file security/fixtures/dangerous_shell_needs_approval.json`
- `py scripts/sh_runtime.py validate-workflow-evidence --evidence evals/fixtures/evidence_less_completion.json --root . --require-artifacts`
- `claude plugin validate .`
- `git diff --check`

## Idempotence and Recovery

- `start-run --reset-existing` may remove only `.sh/runs/<safe-run-id>` after validating the path is under `.sh/runs`.
- Normal `start-run` refuses to overwrite an existing run.
- `resume-run` refuses terminal states and appends recovery state without changing run id.
- Replay reads artifacts and does not mutate state unless an explicit output path is supplied.
- Eval outputs use a generated eval run id unless supplied; existing output paths are not overwritten unless a reset flag is used.

## Artifacts and Notes

Planned tracked artifacts:

- `schemas/*.json`
- `evals/benchmark_tasks.jsonl`
- `evals/regression_tasks.jsonl`
- `evals/resource_spec.yaml`
- `evals/fixtures/*`
- `security/policy.json`
- `security/fixtures/*.json`
- `docs/domain/completion-auditor/*`
- `docs/scorecards/sh-runtime-evals-scorecard.md`
- `.github/workflows/sh-runtime.yml`

Runtime artifacts:

- `.sh/runs/<run_id>/run_manifest.json`
- `.sh/runs/<run_id>/state.json`
- `.sh/runs/<run_id>/step_ledger.jsonl`
- `.sh/runs/<run_id>/trace.jsonl`
- `.sh/runs/<run_id>/tool_calls.jsonl`
- `.sh/runs/<run_id>/cost_latency.json`
- `.sh/runs/<run_id>/artifacts.json`
- `.sh/runs/<run_id>/interruptions.json`
- `.sh/runs/<run_id>/handoff.md`
- `.sh/runs/<run_id>/replay.json`
- `.sh/evals/<eval_run_id>/eval_result.json`
- `.sh/evals/<eval_run_id>/transcript_review.md`
- `.sh/approvals/<approval_id>.json`

## Interfaces and Dependencies

- Python standard library only; no new package dependency unless unavoidable.
- JSON Schema files are machine-readable contracts. Runtime validation will implement the subset needed for these schemas without pulling a validator dependency.
- Host integration remains mocked/fixture-based unless actually run.
- Permission policy is repo-local and does not claim OS-level sandboxing until enforcement exists.
