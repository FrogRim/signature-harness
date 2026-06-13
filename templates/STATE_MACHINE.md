# SH State Machine

`INCOMPLETE` is an Oracle verdict, not a runtime state. Ordinary missing proof creates `GAP_FILL`; external-runner hang artifacts create `REMEDIATING` first.

## States

| Class | States |
| --- | --- |
| Execution | `RUNNING`, `GAP_FILL`, `RECOVERY`, `REMEDIATING` |
| Suspended | `PAUSED`, `BLOCKED` |
| Terminal | `COMPLETE`, `ABORTED` |

Any transition not listed below is a system-level exception.
`proof_still_missing` is the explicit `GAP_FILL` self-loop before the 3-strikes pause threshold.

## Transitions

| Current State | Trigger Event | Next State | Owner / Action |
| --- | --- | --- | --- |
| `RUNNING` | Oracle: all evidence validated | `COMPLETE` | Orchestration writes `close` directive and permanently freezes the loop. |
| `RUNNING` | Oracle: evidence missing or mismatched | `GAP_FILL` | Orchestration keeps the Seed, narrows the active slice to missing-proof acquisition, and dispatches gap-fill. |
| `RUNNING`, `GAP_FILL`, `RECOVERY` | External runner hang artifact proves timeout plus no-progress | `REMEDIATING` | Orchestration writes remediation directive for the external runner; SH does not execute cleanup. |
| `RUNNING` | Oracle: auth, user interaction, permission, or external state required | `BLOCKED` | Orchestration dumps blocked receipt and parks the process. |
| `RUNNING` | Red-team: 3-strikes no-progress | `PAUSED` | Red-team/evolution/unstuck chooses a new route before further execution. |
| `RUNNING` | Heartbeat: missed plus timeout, or critical risk | `ABORTED` | Orchestration hard-stops the run and preserves evidence. |
| `GAP_FILL` | Missing proof acquired | `RUNNING` | Goal loop continues only with oracle recheck required. |
| `GAP_FILL` | Proof still missing but below 3 strikes | `GAP_FILL` | Continue the narrow missing-proof slice; no broad retry. |
| `GAP_FILL` | Proof still missing 3 times | `PAUSED` | Orchestration pauses and reroutes. |
| `GAP_FILL` | Heartbeat timeout, critical risk, or security violation | `ABORTED` | Orchestration hard-stops the run and preserves evidence. |
| `BLOCKED` | Rehydration gate: resume check passed and hashes clean | `RECOVERY` | Goal loop resumes in recovery mode with a narrow recovery slice. |
| `BLOCKED` | Rehydration gate: resume check failed | `BLOCKED` | Orchestration keeps the run parked and requests the missing action. |
| `RECOVERY` | Oracle: recovery evidence validated | `RUNNING` | Orchestration restores original active-slice authority after oracle recheck. |
| `RECOVERY` | Oracle: auth, user interaction, permission, or external state required | `BLOCKED` | Orchestration parks the recovery slice and writes a new blocked receipt. |
| `RECOVERY` | Drift detected | `PAUSED` | Orchestration routes to evolution, unstuck, or clarification. |
| `RECOVERY` | Heartbeat timeout, critical risk, or security violation | `ABORTED` | Orchestration hard-stops the recovery run and preserves evidence. |
| `REMEDIATING` | Cleanup/reset evidence valid | `GAP_FILL` | Reconcile time debt and missing proof before normal execution resumes. |
| `REMEDIATING` | Cleanup/reset evidence invalid but deadline open | `REMEDIATING` | Keep external runner on remediation evidence. |
| `REMEDIATING` | Cleanup/reset deadline expired | `ABORTED` | Environment control is lost; abort run. |
| `REMEDIATING` | Heartbeat timeout, critical risk, or security violation | `ABORTED` | Orchestration hard-stops the remediation run and preserves evidence. |
| `PAUSED` | Evolution, unstuck, or Seed update accepted | `RUNNING` | Orchestration dispatches the revised route. |
| `PAUSED` | Abort requested, critical risk, or security violation | `ABORTED` | Orchestration permanently discards the loop and preserves evidence. |

`COMPLETE` and `ABORTED` are terminal and must not be resumed.
