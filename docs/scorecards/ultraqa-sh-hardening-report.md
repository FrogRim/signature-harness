# UltraQA Report

## Goal and success criteria

- Goal: harden Signature Harness repo-local runtime/evals/observability/security until the 95/100 score is defensible.
- Stop condition: baseline verification and adversarial e2e repros pass without hiding fixture-only false greens.
- Safety bounds applied: no destructive commands, no production/network side effects, temp harnesses under `%TEMP%`, tracked artifacts only when intentional.

## Scenario matrix

| ID | User/attacker model | Scenario | Command/harness | Expected signal | Actual result | Status | Evidence | Cleanup |
|----|---------------------|----------|-----------------|-----------------|---------------|--------|----------|---------|
| ADV-E2E-001 | Malicious/over-optimistic agent | Force `RUNNING -> COMPLETE` through `record-step` without Oracle event | temp `.sh` run under `%TEMP%` | nonzero exit; state remains `RUNNING` | exit `2`; state remained `RUNNING` | passed | command output in active thread | temp-only |
| ADV-E2E-002 | Contract author with malformed field types | `inputSchema` and `timeout_sec` changed to strings | temp copied `schemas/` | `validate-schemas` exits nonzero | exit `2`; schema type findings emitted | passed | command output in active thread | temp-only |
| ADV-E2E-003 | Eval author hiding missing proof | Eval references missing `expected_artifacts` while fixture says pass | temp custom eval suite | `run-evals` exits `8` | exit `8`; pass rate `0.0` | passed | command output in active thread | temp-only |
| ADV-E2E-004 | Action author abusing policy gap | `scoped_network` writes `README.md` outside `.sh/` write allowlist | temp action JSON | `validate-policy` exits `7` | exit `7`; BLOCKED | passed | command output in active thread | temp-only |
| NORMAL-001 | Normal user | Start, record, pause, resume, replay run | `.sh/runs/ultraqa-smoke-cycle1` | replay state `RUNNING` with 4 steps | passed | passed | `.sh/runs/ultraqa-smoke-cycle1/replay.json` | intentional runtime artifact |
| NORMAL-002 | Eval maintainer | Run benchmark suite | `run-evals --suite evals/benchmark_tasks.jsonl --trials 3` | 60/60 trials pass | passed | passed | `.sh/evals/ultraqa-benchmark-final/eval_result.json` | intentional runtime artifact |
| NORMAL-003 | Security reviewer | allowlisted scoped network and blocked unallowlisted domain | `validate-policy` fixtures | ok for allowlist, exit `7` for block | passed | passed | command output in active thread | tracked fixtures |
| NORMAL-004 | Oracle reviewer | artifact-backed workflow passes and evidence-less workflow fails | `validate-workflow-evidence` fixtures | exit `0` and exit `5` respectively | passed | passed | command output in active thread | tracked fixtures |

## Commands run

- `[0] py -m py_compile scripts/sh_runtime.py`
- `[0] py scripts/sh_runtime.py self-test`
- `[0] py scripts/sh_runtime.py validate-schemas --root .`
- `[0] py scripts/sh_runtime.py run-evals --root . --suite evals/benchmark_tasks.jsonl --trials 3 --eval-run-id ultraqa-benchmark-final --reset-existing`
- `[0] py scripts/sh_runtime.py run-evals --root . --suite evals/regression_tasks.jsonl --trials 3 --eval-run-id ultraqa-regression-final --reset-existing`
- `[0] py scripts/sh_runtime.py run-evals --root . --suite evals/benchmark_tasks.jsonl --trials 3 --eval-run-id ultraqa-recheck-20260613-031156-benchmark --reset-existing`
- `[0] py scripts/sh_runtime.py run-evals --root . --suite evals/regression_tasks.jsonl --trials 3 --eval-run-id ultraqa-recheck-20260613-031156-regression --reset-existing`
- `[0] py scripts/sh_runtime.py run-evals --root . --suite evals/benchmark_tasks.jsonl --trials 3 --eval-run-id ultraqa-recheck-20260613-031613-benchmark --reset-existing`
- `[0] py scripts/sh_runtime.py run-evals --root . --suite evals/regression_tasks.jsonl --trials 3 --eval-run-id ultraqa-recheck-20260613-031613-regression --reset-existing`
- `[0] py scripts/sh_runtime.py run-evals --root . --suite evals/benchmark_tasks.jsonl --trials 3 --eval-run-id ultraqa-recheck-20260613-031816-benchmark --reset-existing`
- `[0] py scripts/sh_runtime.py run-evals --root . --suite evals/regression_tasks.jsonl --trials 3 --eval-run-id ultraqa-recheck-20260613-031816-regression --reset-existing`
- `[0] node -e "... omx state clear {mode:'ultraqa', all_sessions:true} ..."` removed stale session-scoped `ultraqa-state.json`
- `[0] node -e "... omx state clear {mode:'skill-active', all_sessions:true} ..."` removed stale session-scoped `skill-active-state.json`
- `[nonzero expected] py scripts/sh_runtime.py validate-policy --root . --policy security/policy.json --action-file security/fixtures/scoped_network_blocked.json`
- `[nonzero expected] py scripts/sh_runtime.py validate-workflow-evidence --evidence evals/fixtures/evidence/evidence_less_completion.json --root . --require-artifacts`
- `[0] py scripts/sh_runtime.py verify-ledger --root .`
- `[0] claude plugin validate .`
- `[0] git diff --check`
- `[0] node -e "... omx state clear ..."` (shell quoting bypass for OMX state cleanup)
- `[2] adversarial transition-bypass repro`
- `[2] adversarial malformed-schema repro`
- `[8] adversarial missing-expected-artifact eval repro`
- `[7] adversarial scoped write allowlist repro`

## Failures found

- `record-step` allowed state-changing traces without transition events.
- `validate-schemas` checked shapes but not field types.
- `run-evals` accepted fixture self-pass even when expected artifacts were missing.
- `validate-policy` ignored per-profile filesystem write allowlists.

## Fixes applied

- `scripts/sh_runtime.py`: state-changing `record-step` now requires a canonical event.
- `scripts/sh_runtime.py`: added minimal schema validator and applied it to tool contracts, taxonomy, security policy, and eval tasks.
- `scripts/sh_runtime.py`: eval tasks now require existing expected artifacts and can run workflow/resume/policy validators.
- `scripts/sh_runtime.py`: policy validator now enforces per-profile write allowlists.
- `schemas/*.schema.json`: tightened field types and nested structures.
- `evals/benchmark_tasks.jsonl`: linked key tasks to substrate validators.

## Cleanup and rollback

- Temporary adversarial harness files were created under `%TEMP%`.
- No destructive cleanup was required.
- Runtime smoke artifacts under `.sh/` are intentional ignored evidence artifacts.

## Residual risks

- Host-level Codex/Claude integration is still not executed.
- `run-resume` still fails closed because no OS/Docker/WASM sandbox adapter exists.
- Eval graders are deterministic substrate/fixture graders, not LLM transcript judges.

## Evidence

- Runtime: `.sh/runs/ultraqa-smoke-cycle1/`
- Benchmark eval: `.sh/evals/ultraqa-recheck-20260613-031816-benchmark/eval_result.json`
- Regression eval: `.sh/evals/ultraqa-recheck-20260613-031816-regression/eval_result.json`
- Scorecard: `docs/scorecards/sh-runtime-evals-scorecard.md`
