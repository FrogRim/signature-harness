# SH Runtime / Evals / Observability Scorecard

Date: 2026-06-13 KST

Scope: repo-local Signature Harness substrate for the AI coding-agent completion auditor vertical. This score does not claim host-level Codex/Claude end-to-end execution or OS-level sandboxing.

## Updated Score

| Area | Score | Evidence | Remaining gap |
|---|---:|---|---|
| Goal and task definition | 8 / 8 | `docs/domain/completion-auditor/glossary.md`, `docs/domain/completion-auditor/rubric.md` | None for repo-local vertical. |
| Agent loop design | 10 / 10 | `scripts/sh_runtime.py` run lifecycle commands, `.sh/runs/ultraqa-smoke-cycle1/replay.json`; UltraQA transition-bypass repro now fails closed | Host loop integration is still outside repo-local proof. |
| Tool contract and execution environment | 9 / 10 | `schemas/tool_contracts.json`, `schemas/tool_contracts.schema.json`, `py scripts/sh_runtime.py validate-schemas --root .` | No real sandbox adapter for `run-resume`; it fails closed. |
| Context / memory / handoff | 9 / 10 | `.sh/runs/smoke-runtime-20260613-a/handoff.md`, `.sh/runs/smoke-runtime-20260613-a/replay.json` | Long-run semantic summarizer is artifact-based, not model-assisted. |
| Verification / eval | 14 / 15 | `evals/benchmark_tasks.jsonl` 20 tasks, `.sh/evals/ultraqa-recheck-20260613-031816-benchmark/eval_result.json` 60/60 passed; missing expected artifacts now fail closed | Graders are deterministic fixtures plus substrate validators, not model-judged transcripts. |
| Observability / trace | 10 / 10 | `.sh/runs/smoke-runtime-20260613-a/trace.jsonl`, `tool_calls.jsonl`, `cost_latency.json`, `artifacts.json` | None for repo-local traces. |
| Permission / safety / security | 9 / 10 | `security/policy.json`, `validate-policy` fixtures, `.sh/approvals/dangerous_shell_approved.json`; scoped write allowlists now enforced | Policy enforcement exists at substrate boundary; OS/container sandbox is not implemented. |
| Failure taxonomy / recovery | 8 / 8 | `schemas/failure_taxonomy.json`, `resume-run`, `record-interruption`, `verify-ledger` | None for repo-local taxonomy coverage. |
| Domain specificity | 9 / 10 | `docs/domain/completion-auditor/failure-corpus.md`, `evals/fixtures/evidence/` | Needs real user-run corpus over time. |
| Maintainability / documentation | 5 / 5 | `scripts/README.md`, `.github/workflows/sh-runtime.yml`, living plan | None. |
| Cost / latency management | 4 / 4 | `cost_latency.json`, eval aggregate cost/duration/retry/tool error metrics | None for deterministic fixtures. |

Total: **95 / 100 repo-local**.

## Score Justification

The jump is justified only for the repo-local substrate. The harness now starts a run, records trace-backed steps, pauses, resumes under the same run id, replays the run, validates tool contracts and failure taxonomy with strict field types, runs a 20-task deterministic benchmark with 3 trials per task, blocks evidence-less completion by default, fails eval tasks with missing expected artifacts, and evaluates permission/network/write approval fixtures.

UltraQA hardening closed the four regressions that previously made 95 indefensible: direct `record-step` transition bypass, shape-only schema validation, eval self-pass without expected artifacts, and scoped profile write allowlist bypass.

## Evidence Map

- Runtime runner: `scripts/sh_runtime.py`
- Run artifacts: `.sh/runs/ultraqa-smoke-cycle1/`
- Trace: `.sh/runs/ultraqa-smoke-cycle1/trace.jsonl`
- Tool calls: `.sh/runs/ultraqa-smoke-cycle1/tool_calls.jsonl`
- Replay: `.sh/runs/ultraqa-smoke-cycle1/replay.json`
- Eval result: `.sh/evals/ultraqa-recheck-20260613-031816-benchmark/eval_result.json`
- Regression result: `.sh/evals/ultraqa-recheck-20260613-031816-regression/eval_result.json`
- Approval log: `.sh/approvals/dangerous_shell_approved.json`
- Tool contracts: `schemas/tool_contracts.json`
- Failure taxonomy: `schemas/failure_taxonomy.json`
- Security policy: `security/policy.json`
- Benchmark tasks: `evals/benchmark_tasks.jsonl`
- Regression tasks: `evals/regression_tasks.jsonl`
- Completion-auditor docs: `docs/domain/completion-auditor/`

## Not Claimed

- Full Claude Code or Codex host end-to-end orchestration was not executed.
- `run-resume` still fails closed; no OS account, Docker, WASM, or network sandbox adapter is implemented.
- Benchmark graders are deterministic fixture graders, not LLM-as-judge or external human review.
