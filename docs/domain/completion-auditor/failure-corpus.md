# Completion Auditor Failure Corpus

The deterministic benchmark suite in `evals/benchmark_tasks.jsonl` covers the following failure families.

| Failure family | Benchmark ids | Taxonomy code |
|---|---|---|
| Evidence-less completion | `bench_001`, `bench_019` | `INVALID_EVIDENCE` |
| Hallucinated or stale evidence | `bench_002`, `bench_008` | `ARTIFACT_MISMATCH` |
| False completion after failed tests | `bench_003` | `FAILED_TEST` |
| Unsafe resume contract | `bench_004` | `UNSAFE_RESUME` |
| No-progress loop | `bench_005` | `NO_PROGRESS` |
| Repeated tool failure | `bench_006` | `REPEATED_TOOL_FAILURE` |
| Missing proof / gap-fill | `bench_007` | `INVALID_EVIDENCE` |
| Permission denial | `bench_009`, `bench_010` | `PERMISSION_DENIED` |
| Approval required | `bench_011` | `BLOCKED_APPROVAL` |
| Replay and trace reconstruction | `bench_012` | none |
| Contract violation | `bench_013`, `bench_018` | `CONTRACT_VIOLATION`, `TOOL_SCHEMA_ERROR` |
| Budget and missing context | `bench_014`, `bench_015` | `OVER_BUDGET`, `MISSING_CONTEXT` |
| Wrong tool and human blocker | `bench_016`, `bench_017` | `WRONG_TOOL`, `NEEDS_HUMAN_DECISION` |
| Positive artifact-backed completion | `bench_020` | none |
| External-runner SUT hang | `bench_021` | `SUT_HANG_TIMEOUT` |
| Progressing external-runner tick | `bench_022` | none |
| Remediation timeout fail-safe | `bench_023` | `REMEDIATION_TIMEOUT` |
| Valid remediation evidence | `reg_005` | none |

Fixture files live under `evals/fixtures/evidence/` and `security/fixtures/`. These fixtures are intentionally small; their role is to make the audit failure mode explicit and replayable, not to simulate a full host agent.
