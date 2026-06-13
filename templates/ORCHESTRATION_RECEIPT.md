# Orchestration Receipt - <run-id>

## Metadata
- goal_id:
- seed_id:
- active_slice:
- run_id:
- timestamp:

## Verdict
continue | close | pause | gap-fill | narrow-active-slice | blocked | recovery | red-team | evolution-loop | unstuck | abort | retry-once

## State Transition
- from_state: RUNNING | GAP_FILL | RECOVERY | REMEDIATING | PAUSED | BLOCKED
- trigger_event:
- to_state: RUNNING | GAP_FILL | RECOVERY | REMEDIATING | PAUSED | BLOCKED | COMPLETE | ABORTED
- listed_transition: yes | no

## Watchdog
- heartbeat_status: ok | soft-stale | missed | hard-abort-candidate
- heartbeat_basis:
- no_progress_trigger: none | repeated-failure | unchanged-evidence-claim | plan-only-churn | repeated-review-finding
- no_progress_count:
- budget_status: ok | warning | exceeded
- risk_status: ok | warning | critical

## Gap Fill
- evidence_gap_report:
- narrowed_active_slice:
- oracle_recheck_required: yes | no

## Rehydration
- blocked_receipt:
- resume_check_id:
- resume_check_status: not_applicable | passed | failed | rejected_security
- drift_hash_status: clean | drifted | not_checked
- evidence_hash_status: clean | drifted | not_checked

## Retry Policy
- retry_exception_requested: yes | no
- retry_exception_approved: yes | no
- retry_exception_basis:

## Reason
<why orchestration selected this route>

## Directive
- directive_path:
- directive_action:
- next_owner:

## Evidence
- <trace, receipt, command, file, or hash>
