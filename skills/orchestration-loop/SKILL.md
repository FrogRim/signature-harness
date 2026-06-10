---
name: orchestration-loop
description: Read-only Signature Harness control plane. Watches goal-loop state, heartbeat, budgets, red-team/oracle receipts, and no-progress signals, then writes routing receipts or directives without implementing fixes or editing source files.
---

# Orchestration Loop

Treat orchestration as the control plane, not the action plane.

The orchestration loop watches goal loops, decides the next route, and records why. It does not implement code, edit project files, mark completion, mutate Seeds, or update active memory.

Runtime states:

- execution: `RUNNING`, `GAP_FILL`, `RECOVERY`
- suspended: `PAUSED`, `BLOCKED`
- terminal: `COMPLETE`, `ABORTED`

`INCOMPLETE` is an Oracle verdict, not a runtime state. Any unlisted state transition is a system-level exception.

## Inputs

- goal id and active Seed id/hash
- active slice
- run trace and heartbeat state
- budget counters
- red-team receipts
- oracle receipts
- evidence hashes and failure signatures
- dynamic workflow cost-gate and evidence contracts
- Oracle `evidence_gap_report`
- Oracle `blocked_receipt`
- user-fit profile

## Authority

Allowed:

- read project and `.sh/` state
- write `.sh/orchestration/` routing receipts
- write `.sh/orchestration/directives/<run_id>.json`
- write `.sh/orchestration/gap-fill/<run_id>.json`
- write `.sh/orchestration/blocked/<run_id>.json`
- write `.sh/orchestration/security/<run_id>.json`
- append minimal steering events to `.sh/ledger.jsonl`

Forbidden:

- edit source files or artifacts outside orchestration state
- perform implementation work
- mark a goal complete
- silently mutate an accepted Seed
- update active rules, user fit, or Seed defaults without `promotion-gate`
- approve ordinary retry after no-progress
- execute resume checks from free-form command strings
- place user input directly into command arguments

## Watchdog Defaults

Heartbeat:

- heartbeat tick: 60 seconds
- missed heartbeat: 180 seconds
- hard-abort candidate: 300 seconds
- `waiting_user` and `blocked` are not heartbeat failures
- long commands must declare `deadline_at`
- hard abort requires missing heartbeat plus process/session unresponsive or critical risk

No-progress:

- same failure signature 3 times
- same completion claim with unchanged evidence hash 3 times
- plan-only churn without execution evidence 3 times
- repeated oracle/red-team finding 3 times

## Routing

State transitions:

| Current | Trigger | Next | Action |
| --- | --- | --- | --- |
| `RUNNING` | Oracle `COMPLETE` | `COMPLETE` | write `close` directive and freeze loop |
| `RUNNING` | Oracle `INCOMPLETE` | `GAP_FILL` | keep Seed, narrow active slice to missing proof, dispatch gap-fill |
| `RUNNING` | Oracle `BLOCKED` | `BLOCKED` | dump blocked receipt and park process |
| `RUNNING` | no-progress 3-strikes | `PAUSED` | pause and route through red-team/evolution/unstuck |
| `RUNNING` | missed heartbeat plus timeout or critical risk | `ABORTED` | hard-stop run and preserve evidence |
| `GAP_FILL` | missing proof acquired | `RUNNING` | require oracle recheck before further expansion |
| `GAP_FILL` | proof still missing 3 times | `PAUSED` | pause and reroute |
| `BLOCKED` | rehydration gate passes | `RECOVERY` | dispatch narrow recovery slice |
| `BLOCKED` | rehydration gate fails | `BLOCKED` | remain blocked and request the missing action |
| `RECOVERY` | recovery evidence validated | `RUNNING` | restore original active-slice authority after oracle recheck |
| `RECOVERY` | drift detected | `PAUSED` | route to evolution, unstuck, or clarification |
| `PAUSED` | evolution, unstuck, or Seed update accepted | `RUNNING` | dispatch revised route |

Terminal states `COMPLETE` and `ABORTED` must not be resumed.

Default no-progress route:

```text
pause
-> red-team review
-> narrow-active-slice | evolution-loop | unstuck | abort
```

Retry is forbidden by default. Approve `retry-once` only when:

- red-team explicitly approves the exception
- the failure cause is clear and local
- new evidence or a new constraint changes the next attempt
- the next attempt is meaningfully different
- the run has not already consumed its single retry exception

## Dynamic Workflow Routing

Dynamic workflows are not the default. Before dispatching extra agents, fan-out,
or adversarial panels, run a cost gate:

- Is the active slice too broad, parallel, risky, or adversarial for a static goal loop?
- Can each lane return comparable evidence?
- Is there a clear synthesis or tournament rule?
- Would the extra token/time cost reduce a known failure mode such as agentic laziness, self-preferential bias, or goal drift?

Canonical patterns:

- `classify-and-act` - route the slice by type, then run the matching bounded loop.
- `fan-out-and-synthesize` - split independent lanes and merge evidence.
- `adversarial-verification` - assign a separate critic or red-team lane before completion.
- `generate-and-filter` - produce candidates, then filter with fixed criteria.
- `tournament` - run competing approaches and select by evidence score.
- `loop-until-done` - repeat a bounded check/fix loop until Oracle evidence passes or a stop trigger fires.

If the cost gate fails, route to the ordinary goal loop. If it passes, require a
dynamic workflow evidence contract and validate it mechanically:

```powershell
py scripts/sh_runtime.py validate-workflow-evidence --evidence <path>
```

When `completion_allowed` is false, dispatch `GAP_FILL` for the listed
`incomplete_record_ids`. Do not let the goal loop repeat the whole workflow.

## Gap Fill

When Oracle returns `INCOMPLETE`, read the `evidence_gap_report` and write a gap-fill dispatch under:

```text
.sh/orchestration/gap-fill/<run_id>.json
```

The dispatch must:

- keep the same Seed
- narrow the active slice to missing-proof acquisition
- list allowed and forbidden actions
- require an Oracle recheck before returning to normal `RUNNING`
- forbid unrelated implementation, cleanup, and completion claims

## Blocked Rehydration

When Oracle returns `BLOCKED`, write a blocked receipt under:

```text
.sh/orchestration/blocked/<run_id>.json
```

After the user or external system resolves the blocker, run the rehydration gate mechanically:

1. Load the blocked receipt, Seed, active slice, run trace, red-team/oracle receipts, evidence map, and last safe checkpoint.
2. Resolve `resume_check_id` to an allowlisted command contract.
3. Reject free-form command strings.
4. Validate that `argv` contains no shell metacharacters and `shell` is `false`.
5. Inject user secrets only through isolated subprocess environment variables.
6. Execute in a least-privilege sandbox with denied-by-default network and declared egress/write allowlists.
7. If the check fails, stay `BLOCKED`.
8. If the check passes, compare `drift_hash` and `evidence_hash` domains.
9. If hashes are clean, dispatch `RECOVERY`; if drift exists, route to `PAUSED`.

Security violations abort the current run and write a security incident receipt. They do not terminate the whole harness runtime.

## Hash Domains

- `drift_hash`: active-slice target source files/directories declared by the slice, using Git diff and content hashes.
- `evidence_hash`: Oracle evidence-map assets only, by content hash.

Exclude unrelated repository space, `.sh/` harness state, and global temp directories from `drift_hash`.

## Directive Contract

When a runtime exists, write directives to:

```text
.sh/orchestration/directives/<run_id>.json
```

Directive values:

- `continue`
- `close`
- `pause`
- `gap-fill`
- `narrow-active-slice`
- `blocked`
- `recovery`
- `red-team`
- `evolution-loop`
- `unstuck`
- `abort`
- `retry-once`

Goal loops must read the directive before each non-trivial tick and obey `pause`, `abort`, and reroute directives.

## Output

```md
# Orchestration Receipt - <run-id>

Verdict: continue | close | pause | gap-fill | narrow-active-slice | blocked | recovery | red-team | evolution-loop | unstuck | abort | retry-once

## State Read
- goal_id:
- seed_id:
- active_slice:
- run_id:

## Watchdog
- heartbeat_status:
- no_progress_trigger:
- budget_status:
- risk_status:
- state_transition:
- hash_status:
- resume_check_status:

## Reason
<why this route was selected>

## Directive
<directive path or none>

## Next Owner
orchestration-loop | goal-loop | red-team | oracle-verification | active-slice | evolution-loop | unstuck | user
```
