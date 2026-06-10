---
name: oracle-verification
description: Staged Signature Harness completion gate. Use before claiming any non-trivial goal is complete, especially after implementation, review, cleanup, research, evolution, or red-team findings. Maps success criteria to evidence, measures drift, and returns COMPLETE, INCOMPLETE, or BLOCKED.
---

# Oracle Verification

The oracle decides whether completion is proven. It runs cheap mechanical checks first, semantic alignment second, and consensus only when uncertainty or risk justifies the cost.

`INCOMPLETE` is a verdict, not a runtime state. When completion is not proven, the oracle must return a precise missing-proof report so orchestration can create a `GAP_FILL` execution slice instead of allowing ordinary retry.

## Inputs

- normalized goal
- active Seed or explicit reason no Seed was needed
- success criteria
- non-goals
- plan or routed loop summary
- result summary
- verification evidence
- red-team findings
- ledger/checkpoint summary
- run trace summary
- improvement candidates or promotion decisions
- active-slice target manifest and evidence asset manifest
- dynamic workflow evidence contract when fan-out, tournament, adversarial verification, generate/filter, classify/act, or loop-until-done was used

## Method

1. Re-read the goal and stop condition.
2. Confirm the active Seed matches the goal, or record why no Seed was needed.
3. Stage 1: run or inspect mechanical verification.
4. Stage 2: map each success criterion to evidence and measure drift.
5. Stage 3: trigger consensus review only when uncertainty, risk, red-team disagreement, or user request justifies it.
6. Confirm red-team `BLOCK` findings are resolved.
7. Confirm non-goals and scope boundaries were respected.
8. Confirm any active memory update passed `promotion-gate`.
9. If a dynamic workflow was used, validate its evidence contract with `scripts/sh_runtime.py validate-workflow-evidence`.
10. Return one verdict with its required control-plane payload:
   - `COMPLETE` - evidence proves the goal.
   - `INCOMPLETE` - evidence is missing or mismatched; include `evidence_gap_report`.
   - `BLOCKED` - progress needs user input, authority, credentials, or an external state change; include `blocked_receipt`.

## Drift Scores

Score each dimension from `0.0` (no drift) to `1.0` (severe drift):

- `goal_drift` - result no longer satisfies the original objective.
- `constraint_drift` - constraints, non-goals, or decision boundaries were violated.
- `ontology_drift` - the Seed's objects, terms, or assumed domain model changed without being evolved.
- `evidence_gap` - completion claim lacks proof.

If any drift score is materially high, return `INCOMPLETE` and recommend `GAP_FILL`, `evolution-loop`, `unstuck`, or clarification. Use `GAP_FILL` only when the Seed remains valid and the missing work is evidence acquisition.

## Dynamic Workflow Evidence

Dynamic workflows must prove that the extra orchestration actually closed the
active slice. Accept only the canonical patterns:

- `classify-and-act`
- `fan-out-and-synthesize`
- `adversarial-verification`
- `generate-and-filter`
- `tournament`
- `loop-until-done`

Use the deterministic substrate:

```powershell
py scripts/sh_runtime.py validate-workflow-evidence --evidence <path>
```

Use the stricter artifact-backed form for completion claims:

```powershell
py scripts/sh_runtime.py validate-workflow-evidence --evidence <path> --root <repo> --require-artifacts
py scripts/sh_runtime.py validate-workflow-evidence --evidence <path> --root <repo> --require-artifacts --evidence-manifest <hash-manifest-output>
```

If the schema is invalid, return `INCOMPLETE` with a missing-proof report for the
bad contract. If the schema is valid but `completion_allowed` is false, return
`INCOMPLETE` and point orchestration at the listed `incomplete_record_ids`.
Do not accept "all agents reported done" unless `acceptance_verified`,
`incomplete`, and `all_done` agree. In manifest-backed artifact mode, evidence
paths must also appear in `hash-manifest` `evidence_entries`.

## Hash Domains

When checking recovery or evidence stability, keep hash domains separate:

- `drift_hash` - active-slice target files/directories declared by the slice, using Git diff and content hashes.
- `evidence_hash` - Oracle evidence-map assets only, by content hash.

Exclude unrelated repository space, `.sh/` harness state, and global temp directories from `drift_hash`.

## Output

```md
# Oracle Verification - <goal>

Verdict: COMPLETE | INCOMPLETE | BLOCKED
Seed: <seed id/hash or none with reason>

## Stage 1 - Mechanical
- <check> -> passed | failed | not run

## Stage 2 - Semantic
- <success criterion> -> <evidence>

## Drift
- goal_drift: 0.0-1.0
- constraint_drift: 0.0-1.0
- ontology_drift: 0.0-1.0
- evidence_gap: 0.0-1.0

## Evidence Map
- <success criterion> -> <evidence>

## Dynamic Workflow Evidence
- contract_path:
- validation_status:
- pattern:
- cost_gate_status:
- completion_allowed:
- incomplete_record_ids:

## Evidence Gap Report
- gap_id:
  criterion:
  missing_proof:
  required_evidence:
  allowed_gap_fill_actions:
  forbidden_actions:
  keep_seed: yes | no
  recommended_next_state: GAP_FILL | PAUSED

## Blocked Receipt
- blocker_kind: credential_missing | user_decision | permission_required | external_service | destructive_authority | waiting_ci | none
- required_user_action:
- resume_check_id:
- resume_check_contract_sha256:
- resume_check_contract:
  - argv:
  - shell: false
  - env_from_user:
  - timeout_sec:
  - allowed_egress:
  - declared_evidence_outputs:
  - writable_paths:
- last_safe_checkpoint_hash:
- open_evidence_gaps:
- allowed_next_actions:
- forbidden_next_actions:

## Stage 3 - Consensus
- triggered: yes | no
- reason:
- result:

## Learning / Promotion
- candidate_created: yes | no
- promotion_required: yes | no
- promotion_verdict:

## Red-Team Resolution
- <finding> -> resolved | unresolved | not applicable

## Scope Check
- <non-goal/scope boundary> -> respected | violated

## Required Next Action
<empty only when COMPLETE>
```

Do not accept confidence, effort, or "looks good" as evidence.
Do not output a free-form shell command as a resume check. Use only an allowlisted `resume_check_id`, a receipt-bound contract hash, and fixed `argv` contract with `shell: false`.
