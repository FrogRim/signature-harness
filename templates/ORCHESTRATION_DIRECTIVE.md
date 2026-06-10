# Orchestration Directive - <run-id>

```json
{
  "run_id": "",
  "goal_id": "",
  "seed_id": "",
  "active_slice": "",
  "issued_at": "",
  "from_state": "RUNNING | GAP_FILL | RECOVERY | PAUSED | BLOCKED",
  "to_state": "RUNNING | GAP_FILL | RECOVERY | PAUSED | BLOCKED | COMPLETE | ABORTED",
  "action": "continue | close | pause | gap-fill | narrow-active-slice | blocked | recovery | red-team | evolution-loop | unstuck | abort | retry-once",
  "reason": "",
  "required_next_owner": "goal-loop | red-team | oracle-verification | active-slice | evolution-loop | unstuck | user | none",
  "allow_more_execution": true,
  "oracle_recheck_required": false,
  "gap_fill": {
    "enabled": false,
    "missing_proof": [],
    "allowed_actions": [],
    "forbidden_actions": []
  },
  "recovery": {
    "enabled": false,
    "resume_from_checkpoint_hash": "",
    "resume_check_id": "",
    "first_task": "",
    "allowed_actions": [],
    "forbidden_actions": []
  },
  "retry_exception": {
    "approved": false,
    "basis": "",
    "max_attempts": 1
  },
  "heartbeat_policy": {
    "tick_seconds": 60,
    "missed_seconds": 180,
    "hard_abort_candidate_seconds": 300
  },
  "extra": {}
}
```

Runtime-generated directive keys are reserved. Caller-provided payload may add
only `extra` data and must not override state, action, heartbeat, owner, or
execution permission fields.
