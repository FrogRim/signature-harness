---
name: goal-loop
description: Internal Signature Harness module. Invoked by $sh-goal or /sh; not the preferred public command.
---

# Goal Loop

Treat the **Goal** as the primary object. The job is verified completion, not a polished status update.

## Goal Schema

Normalize broad or open-ended requests into:

```yaml
objective: ""
why: ""
goal_hierarchy:
  global_goal: ""
  active_slice: ""
  roadmap: []
success_criteria: []
constraints: []
non_goals: []
autonomy_level: high | medium | low
decision_boundaries: []
verification: []
loop_type: clarify | research | build | debug | performance | cleanup | review
ambiguity_score: 0.0-1.0
seed_readiness: ready | needs_clarification | blocked
stop_condition: ""
```

## Ambiguity Gate

Before broad execution, score ambiguity from `0.0` to `1.0`:

- objective clarity
- constraint clarity
- measurable success criteria
- context/codebase clarity
- non-goals and decision boundaries
- verification path clarity

Interpretation:

- `0.00-0.20` - ready for Seed acceptance.
- `0.21-0.40` - may proceed only for small reversible work; otherwise clarify.
- `>0.40` - route to clarification before implementation.

The score is a routing tool, not a decorative metric. If the score blocks execution, ask the smallest question or inspect the smallest source needed to lower it.

## Routing

Choose the smallest loop that can succeed:

- `clarify` - intent, scope, constraints, non-goals, or success criteria are unclear.
- `research` - external facts, official docs, or papers determine correctness.
- `build` - code or artifacts must be implemented and tested.
- `debug` - reproduction, root cause, or regression isolation is central.
- `performance` - benchmark, latency, throughput, memory, or cost improvement is the goal.
- `cleanup` - behavior must be preserved while simplifying or removing AI-looking code.
- `review` - critique, risk assessment, or verification is the deliverable.

## Loop

1. Normalize the goal.
2. Apply `user-fit`.
3. Invoke `active-slice` for broad or staged goals.
4. Score ambiguity.
5. Clarify only if missing information materially changes execution.
6. Invoke `seed-crystallizer` for broad, long-running, risky, or multi-step work.
7. Invoke `rule-memory-read` for broad, repeated, or user-fit-sensitive work.
8. Route to the loop. For broad, long-running, resumable, high-risk, or multi-agent work, route through `orchestration-loop` as a read-only control plane.
9. Draft the smallest viable plan against the active Seed and selected rules.
10. Run `red-team` before mutation for broad, risky, security-sensitive, production, irreversible, or assumption-heavy work.
11. Execute in bounded steps. Before each non-trivial tick, read any runtime directive at `.sh/orchestration/directives/<run_id>.json`.
    - In `GAP_FILL`, do only the missing-proof work listed by orchestration.
    - In `RECOVERY`, do only the recovery slice until Oracle recheck restores normal authority.
12. Capture trace-backed evidence and heartbeat/checkpoint state.
13. Run `red-team` on completion claims when the work is non-trivial.
14. Run staged `oracle-verification`.
15. If the run produced reusable learning, invoke `improvement-candidate`.
16. Invoke `promotion-gate` before updating active rules, fit, or Seed defaults.
17. If oracle fails from drift or weak quality, invoke `evolution-loop` or `unstuck`.
18. Complete, continue, reroute, or report the blocker.

## Watchdog Contract

Goal loops are executable work units. They must be observable by the orchestration control plane.

Heartbeat defaults:

- heartbeat tick: 60 seconds
- missed heartbeat: 180 seconds
- hard-abort candidate: 300 seconds
- hard abort only when heartbeat is missing plus process/session unresponsive or critical risk is present
- `waiting_user` and `blocked` are not heartbeat failures
- long commands must declare `deadline_at` before they start

No-progress trigger:

- same failure signature 3 times
- same completion claim with unchanged evidence hash 3 times
- plan-only churn without execution evidence 3 times
- repeated oracle/red-team finding 3 times

No-progress response:

```text
pause
-> red-team review
-> active-slice shrink | evolution-loop | unstuck | abort
```

Retry is forbidden by default. Allow one retry only when red-team explicitly approves a clear local failure cause, new evidence or a new constraint, and a meaningfully different approach.

## Termination Contract

Goal loops do not decide terminal success. Oracle verdicts and orchestration state transitions control termination:

- `COMPLETE` closes the loop and forbids more execution.
- `INCOMPLETE` is not a state; orchestration converts it to `GAP_FILL`.
- `BLOCKED` parks the loop until rehydration passes.
- `ABORTED` is terminal and must not be resumed.

If a directive says `close`, `pause`, `blocked`, `gap-fill`, `recovery`, or `abort`, obey that directive before any further implementation.

## State

When a runtime exists, persist under `.sh/`:

- `.sh/goals.json`
- `.sh/seeds/`
- `.sh/rules/`
- `.sh/runs/`
- `.sh/orchestration/`
- `.sh/candidates/`
- `.sh/promotions/`
- `.sh/hypotheses/`
- `.sh/gaps/`
- `.sh/ledger.jsonl`
- `.sh/evidence/`
- `.sh/red-team/`
- `.sh/oracle/`
- `.sh/evolution/`
- `.sh/unstuck/`

If there is no runtime, produce equivalent markdown artifacts from `templates/`.

## Completion Rule

Never mark a goal complete until:

- success criteria are mapped to evidence
- the active Seed is referenced or the work is small enough to justify no Seed
- the active slice completion signal is proven
- red-team `BLOCK` findings are resolved
- verification has actually run or the gap is explicit
- `oracle-verification` returns `COMPLETE`
- any active memory update passed `promotion-gate`
