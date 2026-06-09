# Evaluation - <goal>

## Seed
<seed id/hash>

## Stage 1 - Mechanical
- <check> -> passed | failed | not run

## Stage 2 - Semantic
- <acceptance criterion> -> satisfied | failed | unclear

## Stage 3 - Consensus
- triggered: yes | no
- reason:
- result:

## Verdict
COMPLETE | INCOMPLETE | BLOCKED

`INCOMPLETE` is a verdict, not a state. It must produce `Evidence Gap Report` and route to `GAP_FILL` when the Seed remains valid.

## Evidence Gap Report
- gap_id:
- missing_proof:
- required_evidence:
- recommended_next_state: GAP_FILL | PAUSED

## Blocked Receipt
- blocker_kind:
- required_user_action:
- resume_check_id:

## Required Next Action
<none only when COMPLETE>
