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
- resume_check_contract:
  - argv:
  - shell: false
  - env_from_user:
  - timeout_sec:
  - allowed_egress:
  - writable_paths:
- last_safe_checkpoint_hash:
- open_evidence_gaps:
- allowed_next_actions:
- forbidden_next_actions:

## Hash Domains
- drift_hash:
- drift_hash_scope:
- evidence_hash:
- evidence_hash_assets:

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
