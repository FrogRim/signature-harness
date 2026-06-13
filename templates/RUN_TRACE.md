# Run Trace - <run-id>

## Metadata
- goal_id:
- seed_id:
- active_slice:
- started_at:
- ended_at:
- mode: fresh | gap-fill | recovery | replay | exploratory
- status: RUNNING | GAP_FILL | RECOVERY | REMEDIATING | PAUSED | BLOCKED | COMPLETE | ABORTED
- iteration:

## Heartbeat
- updated_at:
- next_heartbeat_due_at:
- deadline_at:
- last_action:
- last_evidence_hash:
- heartbeat_status: ok | soft-stale | missed | hard-abort-candidate

## Events
- timestamp:
  type: decision | action | evidence | verification | red-team | oracle | candidate | promotion | gap
  summary:
  evidence:

## Scores
- progress_score:
- drift_score:
- stuck_signals:
- repeated_failure_signature_count:
- unchanged_evidence_claim_count:
- plan_only_churn_count:
- repeated_oracle_red_team_finding_count:
- uncertainty_rate:
- evidence_gap:

## Routing
- directive: continue | close | pause | gap-fill | narrow-active-slice | blocked | recovery | remediate | evolution-loop | unstuck | abort | retry-once
- retry_exception_approved: yes | no
- retry_exception_basis:

## Hash Domains
- drift_hash:
- drift_hash_scope:
- evidence_hash:
- evidence_hash_assets:

## Outcome
complete | gap-fill | remediation | recovery | paused | blocked | aborted | candidate-created | promoted | pruned
