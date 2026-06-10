# Dynamic Workflow - <goal>

## Cost Gate
- workflow_worthy: yes | no
- reason:
- fallback_static_loop:
- token_or_time_budget:

Use a dynamic workflow only when the work has real coordination value: independent lanes, adversarial verification, tournament selection, repeated completion checks, or domain-specific routing. Otherwise keep the ordinary goal loop.

## Selected Pattern
One of:

- `classify-and-act`
- `fan-out-and-synthesize`
- `adversarial-verification`
- `generate-and-filter`
- `tournament`
- `loop-until-done`

Pattern:
Rationale:

## Workflow Shape
- goal_id:
- seed_id:
- active_slice:
- lanes:
  - id:
    owner:
    hypothesis_or_task:
    allowed_actions:
    forbidden_actions:
    evidence_required:

## Synthesis Rule
- how results will be merged:
- tie_breaker:
- red_team_checkpoint:
- oracle_checkpoint:

## Evidence Contract
Record evidence in `DYNAMIC_WORKFLOW_EVIDENCE.json` shape and validate with:

```powershell
py scripts/sh_runtime.py validate-workflow-evidence --evidence <path>
py scripts/sh_runtime.py validate-workflow-evidence --evidence <path> --root <repo> --require-artifacts
py scripts/sh_runtime.py validate-workflow-evidence --evidence <path> --root <repo> --require-artifacts --evidence-manifest <hash-manifest-output>
```

Completion requires:

- `cost_gate.workflow_worthy` is true
- every `record` with `done: true` has concrete evidence
- `acceptance_verified` maps final criteria to evidence
- artifact-backed mode can resolve evidence values to existing files under the repo root
- manifest-backed artifact mode can find those files in `hash-manifest` `evidence_assets` with matching `sha256` and `size`
- `incomplete` is empty
- `all_done` is true

If validation is schema-valid but `completion_allowed` is false, Oracle must return `INCOMPLETE` and orchestration must dispatch a `GAP_FILL` slice, not a retry.
