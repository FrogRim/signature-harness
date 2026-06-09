# Signature Harness (SH)

> Personal goal-loop runtime for Codex and Claude Code. The harness is optimized for running a user's goals with explicit scope, adversarial pressure, durable evidence, and a user-fit operating style.

Signature Harness is no longer a fixed `research -> spec -> plan -> implement -> review` pipeline. That pipeline is only one possible loop. The core unit is now a **Goal**, the executable contract is a **Seed**, and durable learning moves through **candidate -> promotion** gates.

```text
goal intake
  -> fit-aware clarification
  -> goal hierarchy / active slice selection
  -> ambiguity scoring
  -> seed crystallization
  -> rule memory read
  -> orchestration routing
  -> red-team pressure on seed/plan
  -> plan or execute in bounded steps
  -> trace-backed evidence capture
  -> oracle verification
  -> reflect / evolve when quality or drift requires it
  -> improvement candidate / promotion gate
  -> ledger checkpoint
  -> finish / continue / reroute
```

## Design Target

SH exists to answer one question:

> How well can this harness keep a goal moving to verified completion in a way that fits this user?

That means the harness values:

- durable goal state over hopeful status updates
- critical feedback over agreeable optimism
- evidence-backed completion over "looks done"
- trace-backed learning over vague reflection
- candidate-only self-improvement over silent memory mutation
- compact public commands over a sprawling skill zoo
- user-fit defaults over generic assistant behavior

## Public Workflow Surface

Keep the public surface small.

| Surface | Purpose |
| --- | --- |
| `/sh <goal>` | Short Claude Code entrypoint for a goal loop. |
| `/signature-harness:sh <goal>` | Claude Code entrypoint for a goal loop. |
| `sh-goal` / `goal-loop` skill | Portable Codex/Claude skill for goal intake, routing, execution, and verification. |
| `orchestration-loop` skill | Read-only control plane that watches goal-loop state and routes pause, evolve, unstuck, abort, or exception retry directives. |
| `seed-crystallizer` skill | Convert a normalized goal into a stable executable Seed. |
| `red-team` skill | Adversarial critique for plans, assumptions, completion claims, and sycophancy. |
| `oracle-verification` skill | Staged evidence gate before any goal is marked complete. |
| `evolution-loop` skill | Reflect on failed or incomplete results and create the next Seed generation. |
| `unstuck` skill | Use lateral thinking personas when the loop stagnates or assumptions look wrong. |

Internal learning gates:

| Surface | Purpose |
| --- | --- |
| `active-slice` skill | Select the currently executable slice of a larger goal. |
| `rule-memory-read` skill | Read only the rules relevant to the active slice and current loop state. |
| `improvement-candidate` skill | Convert trace-backed failures or wins into candidate updates. |
| `promotion-gate` skill | Promote candidates only after evidence, QA, and regression checks. |
| `parallel-hypothesis` skill | Treat subagents as independent hypothesis runs with comparable evidence. |
| `gap-closure` skill | Attach every known gap to a boundary, closure path, evidence source, and gate. |

Recommended default path:

```text
goal-loop -> active-slice -> seed-crystallizer -> rule-memory-read -> orchestration-loop -> execute/checkpoint -> oracle-verification
```

For vague or high-risk goals:

```text
deep-interview -> seed-crystallizer -> red-team-seed -> approved execution -> oracle-verification
```

For incomplete, drifting, or stagnant work:

```text
oracle-verification -> gap-fill for missing proof, or evolution-loop/unstuck for drift/stagnation -> execute/checkpoint
```

For learning from execution:

```text
run trace -> improvement-candidate -> promotion-gate -> active rules / fit / seed defaults
```

## Runtime State

The harness should persist runtime state under `.sh/` when implemented as a CLI/runtime, or use the host agent's native state when running as a pure skill bundle.

```text
.sh/
  goals.json          # active and historical goals
  seeds/              # seed specs, one immutable file per accepted generation
  rules/              # active rule memory, scoped by loop and user fit
  runs/               # run traces and event timelines
  orchestration/      # read-only control-plane receipts and directives
  ledger.jsonl        # append-only checkpoints, steering, reviews
  fit.md              # user-fit operating profile
  evidence/           # command output summaries, review receipts, artifacts
  candidates/         # trace-backed candidate updates; not active by default
  promotions/         # promotion decisions and active-memory updates
  hypotheses/         # parallel hypothesis run summaries and scores
  gaps/               # gap closure records
  red-team/           # plan/result critique reports
  oracle/             # staged verification receipts
  evolution/          # generation lineage, reflections, drift summaries
  unstuck/            # lateral persona reports for stalled work
```

State is leader-owned. Worker agents may report evidence, but they do not mutate the goal ledger or mark completion.

## Plugin Install

Preferred install path is host-native plugin installation.

Claude Code:

```powershell
claude plugin marketplace add FrogRim/signature-harness
claude plugin install signature-harness
```

After restarting Claude Code, use:

```text
/sh <goal>
/signature-harness:sh <goal>
```

Codex:

```powershell
codex plugin marketplace add FrogRim/signature-harness
```

If the active Codex build exposes plugin enable/install through the app or a newer CLI, enable `signature-harness@signature-harness` after adding the marketplace. Current CLI builds may only register the marketplace source; in that case use the fallback installer for Codex skill files until the host plugin manager enables the plugin.

After Codex loads the plugin or fallback skill install, use:

```text
$sh-goal
$goal-loop
$orchestration-loop
$red-team
$oracle-verification
```

Fallback/development install:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_local.ps1
```

The fallback installer copies portable skills to the user-local Codex/Claude skill folders, installs the Claude slash commands as `/sh` and `/signature-harness:sh`, and copies a self-contained source/runtime bundle into `~/.signature-harness`. It skips existing unmarked user files unless `-Force` is passed.

## Runtime Substrate

SH does not require a standalone CLI product. It does require small deterministic helpers for checks that should not be left to an LLM.

Use:

```powershell
py scripts/sh_runtime.py self-test
py scripts/sh_runtime.py init-state --root .
py scripts/sh_runtime.py validate-transition --from-state RUNNING --event oracle_incomplete --to-state GAP_FILL
py scripts/sh_runtime.py hash-manifest --manifest .sh/hash-manifest.json
py scripts/sh_runtime.py validate-resume --contract .sh/resume-checks/auth-smoke.json
```

The substrate handles:

- state transition validation
- `.sh` state directory creation
- `drift_hash` / `evidence_hash` calculation from active-slice manifests
- orchestration directive writing
- ledger append validation
- resume-check contract validation

`run-resume` fails closed until a real sandbox adapter exists. Unsafe local execution is not a fallback.

## Orchestration Control Plane

SH separates the control plane from the action plane.

```text
Signature Harness = operating system
orchestration-loop = read-only control plane / dispatch center
goal-loop = executable unit of work
executor/tools = action plane that may modify files
red-team/oracle = safety and verification signals
```

The orchestration loop may read goal state, run traces, Seed status, active slices, oracle receipts, red-team receipts, budget counters, and heartbeat data. It may write only:

- `.sh/orchestration/` routing receipts
- `.sh/orchestration/directives/<run_id>.json` pause/reroute/abort directives
- `.sh/orchestration/blocked/<run_id>.json` blocked receipts and rehydration packets
- `.sh/orchestration/gap-fill/<run_id>.json` evidence-gap dispatch directives
- `.sh/orchestration/security/<run_id>.json` security incident receipts
- minimal steering events to `.sh/ledger.jsonl`

It must not edit project source files, implement fixes, mark a goal complete, mutate an accepted Seed, or update active rule memory/user fit without a promotion gate.

Heartbeat defaults:

```text
heartbeat tick: 60 seconds
missed heartbeat: 180 seconds
hard-abort candidate: 300 seconds
hard abort allowed only when heartbeat is missing plus process/session unresponsive or critical risk is present
waiting_user and blocked states are not heartbeat failures
long commands must declare deadline_at before they start
```

No-progress defaults:

```text
same failure signature 3 times
or same completion claim with unchanged evidence hash 3 times
or plan-only churn without execution evidence 3 times
or repeated red-team/oracle finding 3 times
```

Default response to no-progress:

```text
pause goal loop
-> red-team review
-> active-slice shrink, evolution-loop, unstuck, or abort
```

Retry is not a default recovery path. A retry is allowed at most once and only when red-team explicitly approves it based on a clear local failure cause, new evidence or a new constraint, and a meaningfully different approach.

## Termination And Recovery

Oracle verdicts are not all runtime states. `INCOMPLETE` is a verdict only; it must create a narrowed `GAP_FILL` execution state instead of an ordinary retry.

Runtime states:

| Class | States |
| --- | --- |
| Execution | `RUNNING`, `GAP_FILL`, `RECOVERY` |
| Suspended | `PAUSED`, `BLOCKED` |
| Terminal | `COMPLETE`, `ABORTED` |

Any transition not listed here is a system-level exception.

| Current State | Trigger Event | Next State | Owner / Action |
| --- | --- | --- | --- |
| `RUNNING` | Oracle `COMPLETE` | `COMPLETE` | Orchestration writes `close` directive and permanently freezes the loop. |
| `RUNNING` | Oracle `INCOMPLETE` | `GAP_FILL` | Orchestration keeps the Seed, shrinks the active slice to missing-proof acquisition, and dispatches a gap-fill directive. |
| `RUNNING` | Oracle `BLOCKED` | `BLOCKED` | Orchestration dumps blocked receipt and parks the process. |
| `RUNNING` | Red-team 3-strikes no-progress | `PAUSED` | Red-team/evolution/unstuck chooses a new route before any further execution. |
| `RUNNING` | Missed heartbeat plus timeout, or critical risk | `ABORTED` | Orchestration hard-stops the run and preserves evidence. |
| `GAP_FILL` | Missing proof acquired | `RUNNING` | Goal loop may continue only with oracle recheck required. |
| `GAP_FILL` | Proof still missing 3 times | `PAUSED` | Orchestration pauses and routes to red-team/evolution/unstuck. |
| `BLOCKED` | Rehydration gate passes | `RECOVERY` | Goal loop resumes in recovery mode with a narrow recovery slice. |
| `BLOCKED` | Rehydration gate fails | `BLOCKED` | Orchestration keeps the run parked and asks for the missing user/external action. |
| `RECOVERY` | Recovery evidence validated | `RUNNING` | Orchestration restores the original active-slice authority after oracle recheck. |
| `RECOVERY` | Drift detected | `PAUSED` | Orchestration routes to evolution, unstuck, or clarification. |
| `PAUSED` | Evolution, unstuck, or Seed update accepted | `RUNNING` | Orchestration dispatches the revised route. |

`COMPLETE` and `ABORTED` are terminal. A terminal loop is never resumed. Its trace, receipts, and evidence remain durable.

### Gap Fill

When Oracle returns `INCOMPLETE`, it must include an `evidence_gap_report`, not a vague rejection. Orchestration uses that report to write a gap-fill dispatch directive:

```yaml
mode: GAP_FILL
seed_id: <same seed>
active_slice: <missing proof only>
missing_proof:
  - criterion:
    required_evidence:
    allowed_actions:
    forbidden_actions:
oracle_recheck_required: true
```

Gap fill is not retry. The Seed remains fixed, and the Goal loop may only acquire the missing proof or report a blocker.

### Blocked Rehydration

When Oracle returns `BLOCKED`, it must include a blocked receipt:

```yaml
blocker_kind: credential_missing | user_decision | permission_required | external_service | destructive_authority | waiting_ci
required_user_action: ""
resume_check_id: ""
last_safe_checkpoint_hash: ""
open_evidence_gaps: []
allowed_next_actions: []
forbidden_next_actions: []
```

After user/external intervention, Orchestration does not ask an LLM whether resume is safe. It mechanically runs the allowlisted `resume_check_id`. If it fails, the run remains `BLOCKED`. If it passes, Orchestration compares the checkpoint hash domains and dispatches `RECOVERY`.

### Hash Domains

Use two separate hash domains:

- `drift_hash` covers only the active-slice target file set: target source files/directories declared by the slice plus their Git diff/content hashes.
- `evidence_hash` covers only Oracle evidence-map assets, such as `coverage/lcov.info` or `test-results.xml`, by content hash.

Always exclude the whole repository space outside the active-slice target set, `.sh/` harness state, and global temp directories from `drift_hash`. `.sh/evidence` may preserve copied evidence, but it belongs to `evidence_hash`, not workspace drift.

### Resume Check Security

`resume_check` is not a shell command string. It is an allowlisted contract:

```yaml
resume_check:
  id: auth-smoke
  argv: ["npm", "run", "auth:smoke"]
  shell: false
  env_from_user: ["API_KEY"]
  timeout_sec: 60
  allowed_egress: ["api.example.com:443"]
  writable_paths: ["<sandbox-tmp>", "<declared-evidence-output>"]
```

Security rules:

- No user input may be formatted into `argv`; secrets enter only through isolated subprocess environment variables.
- Shell metacharacters such as `;`, `&&`, `|`, backticks, `$(`, `>`, `<`, newline, or carriage return in the command contract cause the current run to enter `ABORTED` with a security incident receipt.
- `shell` must be `false`.
- The check must run in a least-privilege sandbox. If sandboxing cannot be provided, keep the run `BLOCKED`; do not fall back to unsafe execution.
- Network is denied by default and enabled only through explicit per-check egress allowlists.
- Write access is limited to sandbox temp and declared evidence outputs.

## Goal Schema

Every goal should be normalized before routing:

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

## Seed Contract

A Seed is the stable execution contract derived from a Goal. The harness should not execute broad or ambiguous work directly from a conversational prompt.

```yaml
seed_id: ""
goal_id: ""
generation: 1
objective: ""
constraints: []
acceptance_criteria: []
non_goals: []
ontology:
  entities: []
  relationships: []
evaluation_plan:
  mechanical: []
  semantic: []
  consensus_trigger: ""
exit_conditions: []
seed_hash: ""
status: draft | accepted | superseded
```

Seed rules:

- no broad execution before ambiguity is low enough to route safely
- restate the goal before accepting a seed
- every plan, checkpoint, and oracle receipt references a seed id or seed hash
- evolve by creating a new seed generation, not by silently mutating the old one
- active rules, fit profile, and seed defaults update only through promoted candidates

## Active Slice

Large goals must be staged. SH should keep the global objective visible while executing only the current slice.

```yaml
global_goal: ""
active_slice:
  id: ""
  objective: ""
  completion_signal: ""
  boundaries: []
roadmap:
  - id: ""
    status: planned | active | complete | blocked
```

Rules:

- do not shrink the global goal to make the current slice look complete
- do not claim roadmap items as active runtime capability
- each active slice needs its own completion signal and evidence plan

## Rule Memory

The model should not reread every preference, rule, and prior lesson for every task. SH should select only the rules relevant to the active slice, loop type, and current evidence.

Rule layers:

- `control` - safe command/tool boundaries
- `mode` - behavior for build, debug, review, research, cleanup, performance
- `user-fit` - calibrated preferences and interaction defaults
- `domain` - project-specific facts and constraints
- `failure` - known anti-patterns and repeated mistakes
- `promotion` - rules that were QA-gated into active memory

## Trace And Promotion

Learning from a run is not the same as mutating the harness.

```text
execution trace
  -> evaluator finding
  -> improvement candidate
  -> promotion gate
  -> active rule / fit / seed default update
```

Candidate rules:

- failures create candidates, not active rules
- wins create reusable hints, not universal rules
- every candidate references trace evidence
- promotion requires oracle evidence and a regression/scope check
- rejected candidates remain evidence; they are not deleted

## Parallel Hypotheses

Parallel workers should be treated as hypothesis runs, not as generic extra effort.

Each run records:

- hypothesis
- active slice
- seed id/hash
- evidence
- progress score
- stuck signals and retry-exception evidence
- fallback rate or uncertainty rate
- recommendation: promote | keep-candidate | prune | rerun

The leader owns promotion. Worker success cannot silently rewrite active memory.

## Gap Closure

A gap is acceptable only when it has a closure path.

Each gap records:

- current boundary
- why the gap matters
- closure path
- evidence source
- promotion or verification gate
- owner/next action

## Loop Types

| Loop | Use When |
| --- | --- |
| `clarify` | Intent, scope, constraints, or success criteria are vague. |
| `research` | External evidence, official docs, papers, or current facts determine correctness. |
| `build` | A code/artifact deliverable can be implemented and tested. |
| `debug` | The goal is failure reproduction, root cause, or regression isolation. |
| `performance` | The goal has benchmark, latency, throughput, or memory criteria. |
| `cleanup` | The goal is behavior-preserving simplification or AI-slop removal. |
| `review` | The goal is critique, risk assessment, or verification only. |

## Red Team Gate

SH treats over-agreeable AI behavior as a real failure mode. The `red-team` agent challenges:

- sycophancy: agreeing with the user instead of testing the claim
- optimism bias: assuming easy success without evidence
- hidden assumptions
- missing non-goals
- weak tests or unverifiable completion criteria
- scope drift
- unsafe or irreversible execution paths
- seed drift or unreviewed seed mutation

Verdicts:

- `PASS` - no blocking issue
- `WARN` - proceed with explicit residual risk
- `BLOCK` - do not execute or complete until resolved

## Oracle Gate

The oracle is staged to avoid expensive or speculative review when cheap checks already fail:

1. Mechanical verification: lint, typecheck, build, tests, static checks, artifact existence.
2. Semantic verification: acceptance criteria mapping, goal alignment, non-goal respect, drift score.
3. Consensus verification: optional critic/multi-agent review only when uncertainty, risk, or user request justifies it.

The oracle records:

- `goal_drift`
- `constraint_drift`
- `ontology_drift`
- `evidence_gap`
- final verdict: `COMPLETE`, `INCOMPLETE`, or `BLOCKED`

Verdict handling:

- `COMPLETE` closes the loop.
- `INCOMPLETE` is not a state; it must include an evidence gap report and dispatch `GAP_FILL`.
- `BLOCKED` parks the loop and requires secure rehydration before `RECOVERY`.

## Evolution And Unstuck

When oracle verification fails without a hard external blocker, the harness should decide whether to:

- enter `GAP_FILL` when the Seed is valid and only proof is missing
- evolve into a new seed generation
- run `unstuck` lateral review before changing approach
- reroute to clarification when the original goal was wrong or underspecified

Stagnation signals:

- repeated failed verification with the same root cause
- oscillating approach changes
- no drift reduction after multiple checkpoints
- red-team repeatedly finding the same assumption gap
- no-progress trigger after 3 repeated failures, unsupported claims, or plan-only churn

Do not use retry as the default response to stagnation. Route through red-team and then narrow, evolve, unstuck, or abort unless the retry exception rule is satisfied.

## Relationship To Existing Harnesses

Ideas adopted from Gajae-Code:

- small public workflow surface
- goal ledger as the durable runtime object
- read-only planner/architect/critic lanes
- tmux/team execution only when parallelism materially helps
- fail-closed mindset for remote control surfaces

Ideas adopted from LazyCodex / OmO:

- one-line install UX
- three-command mental model
- verified completion loops
- hierarchical project memory
- evidence gates before completion

Ideas adopted from Ouroboros:

- Seed as an immutable execution contract
- ambiguity scoring before execution
- restate gate before locking a seed
- mechanical -> semantic -> consensus oracle stages
- drift measurement across goal, constraints, and ontology
- evolution loop for repeated improvement
- unstuck/lateral personas for stagnation

SH intentionally does not copy Ouroboros's full Agent OS/kernel shape. The useful subset is the loop contract, not the whole runtime.

Ideas adopted from Pocketmon-Harness:

- global goal plus active executable slice
- rule memory read instead of giant prompts
- deterministic/mechanical authority before LLM fallback
- trace-backed improvement candidates
- QA-gated promotion before active memory changes
- parallel workers as hypothesis experiments
- gap closure records instead of fake completion

SH intentionally does not copy the Pokemon/mGBA runtime. The useful subset is the learning and promotion discipline.

## Files

- `scripts/sh_runtime.py` - deterministic runtime substrate for state, hash, directive, ledger, and resume-check validation
- `skills/` - portable skill core
- `agents/` - Claude Code role prompts / conceptual role surfaces
- `commands/sh.md` - Claude Code slash command entrypoint
- `templates/` - durable goal, red-team, oracle, and ledger artifact templates
- seed/evolution templates - stable contracts for repeated loop engineering
- candidate/promotion/gap templates - safe learning contracts for personal fit
- `AGENTS.md` - Codex adapter / repo-local operating contract

## Next Build Steps

1. Add a sandbox adapter for `run-resume` so allowlisted resume checks can execute without violating the security contract.
2. Add tests/gates that reject stale fixed-pipeline language and enforce the public surface contract.
3. Start the user-fit calibration pass: tune ambiguity thresholds, default loop depth, red-team strictness, and report shape to this user's actual working style.
4. Add candidate-only fit updates so the harness learns from actual sessions without silently rewriting the user's preferences.
