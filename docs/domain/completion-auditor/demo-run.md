# Completion Auditor Demo Run

This repo-local demo proves the vertical without requiring Codex or Claude host integration.

## Runtime smoke

```powershell
py scripts/sh_runtime.py start-run --root . --goal-id smoke_goal --seed-id smoke_seed --active-slice smoke_slice --objective "Smoke runtime" --run-id smoke-runtime
py scripts/sh_runtime.py record-step --root . --run-id smoke-runtime --step-id step_1 --operation-name inspect --tool-name rg --state-before RUNNING --state-after RUNNING --artifact README.md
py scripts/sh_runtime.py record-interruption --root . --run-id smoke-runtime --kind pause --reason "smoke pause"
py scripts/sh_runtime.py resume-run --root . --run-id smoke-runtime --reason "smoke resume"
py scripts/sh_runtime.py replay-run --root . --run-id smoke-runtime
```

Expected runtime artifacts:

- `.sh/runs/smoke-runtime/run_manifest.json`
- `.sh/runs/smoke-runtime/state.json`
- `.sh/runs/smoke-runtime/trace.jsonl`
- `.sh/runs/smoke-runtime/tool_calls.jsonl`
- `.sh/runs/smoke-runtime/cost_latency.json`
- `.sh/runs/smoke-runtime/artifacts.json`
- `.sh/runs/smoke-runtime/replay.json`
- `.sh/runs/smoke-runtime/handoff.md`

## Completion evidence gate

```powershell
py scripts/sh_runtime.py validate-workflow-evidence --evidence templates/DYNAMIC_WORKFLOW_EVIDENCE.json --root .
py scripts/sh_runtime.py validate-workflow-evidence --evidence evals/fixtures/evidence/evidence_less_completion.json --root .
```

The first command should be completion-eligible because it references tracked evidence artifacts. The second command should fail with exit `5` because descriptive strings are not artifact-backed evidence.

## Benchmark suite

```powershell
py scripts/sh_runtime.py run-evals --root . --suite evals/benchmark_tasks.jsonl --trials 3 --eval-run-id completion-auditor-demo
```

Expected eval artifacts:

- `.sh/evals/completion-auditor-demo/eval_result.json`
- `.sh/evals/completion-auditor-demo/transcript_review.md`

## Security policy smoke

```powershell
py scripts/sh_runtime.py validate-policy --root . --policy security/policy.json --action-file security/fixtures/read_only_ok.json
py scripts/sh_runtime.py validate-policy --root . --policy security/policy.json --action-file security/fixtures/dangerous_shell_needs_approval.json
py scripts/sh_runtime.py validate-policy --root . --policy security/policy.json --action-file security/fixtures/dangerous_shell_approved.json --write-approval-log
```

The denied dangerous shell fixture should return a blocked policy decision. The approved fixture should write `.sh/approvals/dangerous_shell_approved.json`.
