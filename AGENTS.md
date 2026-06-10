# Signature Harness - Codex Adapter

This repository is a personal goal-loop harness. Treat the **Goal** as the primary unit of work.

## Operating Contract

Default path:

```text
goal intake -> active slice -> ambiguity scoring -> seed crystallization -> rule memory read -> orchestration routing -> red-team pressure -> execution/checkpoint -> staged oracle verification -> candidate/promotion or complete
```

Do not treat the old `research -> spec -> plan -> implement -> review` pipeline as mandatory. Use it only when the routed loop actually needs that shape.

## Public Workflow Surface

Public entrypoints are `/sh <goal>` for Claude Code and `$sh-goal` for portable Codex/Claude use. The remaining skills are internal modules routed by the goal loop.

Use the portable skills in this repo:

- `goal-loop` - normalize the request into a goal, choose the loop, run/checkpoint progress, and preserve evidence.
- `orchestration-loop` - read goal-loop state as a control plane and write only routing receipts/directives.
- `seed-crystallizer` - convert a goal into an accepted Seed before broad execution.
- `red-team` - adversarially critique plans, assumptions, completion claims, and sycophantic/over-optimistic behavior.
- `oracle-verification` - staged evidence gate before claiming completion.
- `evolution-loop` - reflect on failed or drifting work and create the next Seed generation.
- `unstuck` - run lateral thinking personas when the loop stagnates.
- `active-slice` - choose the current executable slice of a larger goal.
- `rule-memory-read` - select only the active rules relevant to the goal state.
- `improvement-candidate` - turn trace-backed learning into a candidate, not an active rule.
- `promotion-gate` - decide whether a candidate may update active rule memory, fit, or seed defaults.
- `parallel-hypothesis` - run independent subagents as scored hypothesis experiments.
- `gap-closure` - record gaps with closure path, evidence source, and gate.
- `user-fit` - preserve the user's preferred autonomy, rigor, questioning, and reporting style.

Existing utility skills remain available when they fit the routed loop:

- `deep-interview` for unclear intent
- `brainstorming` for option exploration
- `scope-guard` for scope boundaries
- `test-driven-development` for implementation loops
- `verification` for source/evidence checks

## Rules

- Normalize goals before execution when the request is broad, long-running, or ambiguous.
- Preserve the global goal while selecting only the current active slice for execution.
- Do not execute broad or ambiguous work until a Seed is accepted.
- Score ambiguity before seed acceptance. If ambiguity is materially high, clarify first.
- Restate the goal before locking a Seed.
- Reference the active Seed in plans, checkpoints, red-team reports, and oracle receipts.
- Run `rule-memory-read` before planning broad work; do not stuff every rule or preference into the active prompt.
- Prefer deterministic/mechanical authority before LLM fallback: inspect, test, parse, typecheck, and score before speculating.
- Use `scripts/sh_runtime.py` for deterministic substrate checks when applicable: state transitions, hash manifests, directive writing, ledger appends, and resume-check contract validation.
- Use dynamic workflows only after a cost gate proves coordination value. Canonical patterns are `classify-and-act`, `fan-out-and-synthesize`, `adversarial-verification`, `generate-and-filter`, `tournament`, and `loop-until-done`.
- Validate dynamic workflow completion evidence with `scripts/sh_runtime.py validate-workflow-evidence`; exit `0` means completion-eligible, exit `2` means invalid schema, and exit `5` means schema-valid but incomplete. If `completion_allowed` is false, route to `GAP_FILL` for missing records instead of repeating the whole workflow.
- Ask only when the missing decision would materially change execution or risk.
- Prefer critical, evidence-backed disagreement over agreeable optimism.
- Treat `orchestration-loop` as a read-only control plane. It may write `.sh/orchestration/` receipts/directives and minimal ledger steering events, but it must not edit source files or implement fixes.
- Goal loops must emit heartbeat/checkpoint state. Default heartbeat policy is 60s tick, 180s missed, 300s hard-abort candidate; hard abort requires missing heartbeat plus process/session unresponsiveness or critical risk.
- Treat 3 repeated failure signatures, unchanged-evidence completion claims, plan-only churn, or repeated oracle/red-team findings as no-progress. Pause and route through red-team.
- Retry is forbidden by default. Allow one retry only when red-team explicitly approves a local, evidence-backed retry exception with a meaningfully different approach.
- Treat Oracle `INCOMPLETE` as a verdict, not a runtime state. It must create a `GAP_FILL` execution slice scoped only to missing proof.
- Treat `RUNNING`, `GAP_FILL`, and `RECOVERY` as execution states; `PAUSED` and `BLOCKED` as suspended states; `COMPLETE` and `ABORTED` as terminal states. Unlisted state transitions are system-level exceptions.
- For blocked resume, run only allowlisted `resume_check` contracts with fixed `argv`, `shell: false`, env-only secret injection, explicit timeout, sandbox isolation, and egress/write allowlists.
- Never execute user- or LLM-generated resume command strings. Shell metacharacters in a resume check contract abort the current run and create a security incident receipt.
- Compute `drift_hash` only from active-slice target files/directories and their Git diff/content hashes. Compute `evidence_hash` only from Oracle evidence-map assets. Exclude `.sh/`, unrelated repo space, and global temp directories from `drift_hash`.
- Run `red-team` before executing high-risk plans and before accepting completion.
- Do not mark a goal complete until staged `oracle-verification` passes.
- When oracle fails because of drift or incomplete quality, route to `evolution-loop` or `unstuck` instead of repeating the same plan.
- Convert run learning into `improvement-candidate`; do not silently mutate active rules, fit profile, or seed defaults.
- Promote candidates only through `promotion-gate`.
- Treat parallel workers as hypothesis runs with evidence and scores, not as unsupervised memory writers.
- Every known gap must have a closure path or be reported as residual risk.
- Persist or report evidence for every completion claim.
- Keep worker/subagent roles bounded. The leader owns goal state and completion.

## Recommended Artifact Paths

When a runtime exists, use `.sh/`:

- `.sh/goals.json`
- `.sh/seeds/`
- `.sh/rules/`
- `.sh/runs/`
- `.sh/orchestration/`
- `.sh/candidates/`
- `.sh/promotions/`
- `.sh/hypotheses/`
- `.sh/workflows/`
- `.sh/gaps/`
- `.sh/ledger.jsonl`
- `.sh/evidence/`
- `.sh/red-team/`
- `.sh/oracle/`
- `.sh/evolution/`
- `.sh/unstuck/`
- `.sh/fit.md`

When running as portable skills only, produce equivalent markdown artifacts from `templates/`.
