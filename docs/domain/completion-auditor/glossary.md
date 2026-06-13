# Completion Auditor Glossary

Primary vertical: AI coding-agent completion auditor.

- **Completion claim**: A statement that a coding-agent run is done.
- **Artifact-backed evidence**: A file that exists in the repository or run artifact tree and can be hashed, referenced, and replayed.
- **Evidence-less completion**: A completion claim with only descriptive text and no artifact path.
- **Hallucinated evidence**: A referenced file path, test result, log, or report that does not exist.
- **Stale evidence**: An artifact whose current content differs from the hash recorded in the evidence manifest.
- **Oracle verdict**: Mechanical or staged judgment of completion. `INCOMPLETE` is a verdict, not a runtime state.
- **GAP_FILL**: Narrow execution state for collecting missing proof only.
- **Replay**: Reconstruction of a run from `.sh/runs/<run_id>/replay.json`, `trace.jsonl`, and related artifacts.
- **Permission profile**: Repo-local policy level: `read_only`, `workspace_write`, `scoped_network`, or `danger_full_access`.
- **Approval lifecycle**: Recorded request, reviewer, result, timestamp, and reason for a policy-gated action.
- **Failure taxonomy**: Machine-readable enum in `schemas/failure_taxonomy.json` shared by trace, evals, and policy decisions.
