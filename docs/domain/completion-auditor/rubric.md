# Completion Auditor Rubric

This rubric is for judging whether an AI coding-agent run may be accepted as complete.

| Dimension | Complete | Incomplete / Blocked |
|---|---|---|
| Artifact presence | Final verdict references concrete files that exist. | Verdict relies on descriptive claims only. |
| Artifact integrity | Evidence files match manifest hashes or are freshly hashed. | Evidence path is missing, stale, or mismatched. |
| Mechanical checks | Tests, schema validation, replay, or policy checks are recorded. | Agent says checks passed without logs or results. |
| State discipline | Runtime state follows the transition map. | Unlisted transition, retry churn, or terminal-state resume attempt. |
| Traceability | `trace.jsonl`, `tool_calls.jsonl`, cost/latency, and replay artifacts reconstruct the run. | Failure cannot be reproduced from artifacts. |
| Security boundary | Action fits the active permission profile or has approval artifact. | Dangerous shell, unrestricted network, or write escape is unapproved. |
| Recovery behavior | Missing proof becomes `GAP_FILL`; blocked work resumes with same run id after a gate. | Same broad task is repeated without narrowing or evidence. |
| Hang remediation | External-runner hang artifacts move SH to `REMEDIATING`; cleanup/reset evidence returns through `GAP_FILL`. | SH executes cleanup itself, skips remediation evidence, or resumes directly to `RUNNING`. |

Minimum complete verdict:

1. `validate-workflow-evidence` returns exit `0`.
2. Required evidence paths exist and use allowed artifact types.
3. If an evidence manifest is supplied, current hashes match it.
4. Runtime replay reconstructs the state flow.
5. Any dangerous action has an approval artifact or remains blocked.
6. If a SUT/tick hang occurred, remediation evidence was validated before returning through `GAP_FILL`.
