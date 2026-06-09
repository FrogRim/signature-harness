# Security Incident - <run-id>

## Metadata
- goal_id:
- seed_id:
- active_slice:
- run_id:
- timestamp:

## Trigger
- source: resume_check | directive | command_contract | other
- violation: shell_metacharacter | shell_true | free_form_command | unsafe_env_injection | sandbox_unavailable | unauthorized_egress | unauthorized_write
- detected_value_hash:

## Action
- state_before:
- state_after: ABORTED
- directive_path:
- process_action: cooperative_abort | hard_stop | not_started

## Evidence Preservation
- run_trace:
- orchestration_receipt:
- blocked_receipt:
- logs:

## Notes
Do not store secrets or raw user credentials in this receipt.
