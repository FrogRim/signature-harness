# Architecture Candidate - <candidate-id>

Status: candidate
Application Mode: candidate_only

## Scope
- agents | skills | commands | runtime | plugin | docs | templates | schemas | installer

## Evidence
- file: <repo-relative path>
- line:
- observation:

## Proposed Change
- action: add | merge | delete | update | split | prune | keep
- target: <repo-relative source-of-record path>
- reason:

## Compatibility
- Codex:
- Claude:
- Agent Teams dependency: none | optional

## Verification
- commands:
  - py -3 scripts/sh_runtime.py validate-schemas --root .
  - py -3 scripts/sh_runtime.py validate-release --root .
- oracle_criteria:
  - all cited evidence paths exist
  - no direct host-local `.claude/` or `.codex/` target is required
  - Codex and Claude compatibility impact is explicit

## Residual Risks
- <risk or none>

## Machine-Readable Candidate

Persist the JSON sidecar and validate it with:

```powershell
py -3 scripts/sh_runtime.py validate-architecture-candidate --candidate .sh/candidates/<candidate-id>.json --root .
```

```json
{
  "schema": "sh.architecture_candidate.v1",
  "id": "<candidate-id>",
  "status": "candidate",
  "application_mode": "candidate_only",
  "scope": ["skills"],
  "summary": "<one sentence>",
  "evidence": [
    {
      "path": "skills/example/SKILL.md",
      "line": 1,
      "observation": "<observed issue>"
    }
  ],
  "proposed_changes": [
    {
      "action": "update",
      "target": "skills/example/SKILL.md",
      "reason": "<why this source-of-record path should change>"
    }
  ],
  "compatibility": {
    "codex": "<impact>",
    "claude": "<impact>",
    "agent_teams_dependency": "none"
  },
  "verification": {
    "commands": [
      "py -3 scripts/sh_runtime.py validate-schemas --root .",
      "py -3 scripts/sh_runtime.py validate-release --root ."
    ],
    "oracle_criteria": [
      "candidate remains source-of-record only",
      "evidence paths exist"
    ]
  },
  "residual_risks": []
}
```
