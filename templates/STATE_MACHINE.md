# SH State Machine

`INCOMPLETE` is an Oracle verdict, not a runtime state. It creates `GAP_FILL`.

## States

| Class | States |
| --- | --- |
| Execution | `RUNNING`, `GAP_FILL`, `RECOVERY` |
| Suspended | `PAUSED`, `BLOCKED` |
| Terminal | `COMPLETE`, `ABORTED` |

Any transition not listed below is a system-level exception.

## Transitions

| Current State | Trigger Event | Next State | Owner / Action |
| --- | --- | --- | --- |
| `RUNNING` | Oracle: all evidence validated | `COMPLETE` | Orchestration writes `close` directive and permanently freezes the loop. |
| `RUNNING` | Oracle: evidence missing or mismatched | `GAP_FILL` | Orchestration keeps the Seed, narrows the active slice to missing-proof acquisition, and dispatches gap-fill. |
| `RUNNING` | Oracle: auth, user interaction, permission, or external state required | `BLOCKED` | Orchestration dumps blocked receipt and parks the process. |
| `RUNNING` | Red-team: 3-strikes no-progress | `PAUSED` | Red-team/evolution/unstuck chooses a new route before further execution. |
| `RUNNING` | Heartbeat: missed plus timeout, or critical risk | `ABORTED` | Orchestration hard-stops the run and preserves evidence. |
| `GAP_FILL` | Missing proof acquired | `RUNNING` | Goal loop continues only with oracle recheck required. |
| `GAP_FILL` | Proof still missing 3 times | `PAUSED` | Orchestration pauses and reroutes. |
| `BLOCKED` | Rehydration gate: resume check passed and hashes clean | `RECOVERY` | Goal loop resumes in recovery mode with a narrow recovery slice. |
| `BLOCKED` | Rehydration gate: resume check failed | `BLOCKED` | Orchestration keeps the run parked and requests the missing action. |
| `RECOVERY` | Oracle: recovery evidence validated | `RUNNING` | Orchestration restores original active-slice authority after oracle recheck. |
| `RECOVERY` | Drift detected | `PAUSED` | Orchestration routes to evolution, unstuck, or clarification. |
| `PAUSED` | Evolution, unstuck, or Seed update accepted | `RUNNING` | Orchestration dispatches the revised route. |

`COMPLETE` and `ABORTED` are terminal and must not be resumed.
