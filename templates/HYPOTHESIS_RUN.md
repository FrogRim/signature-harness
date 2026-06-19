# Hypothesis Run - <run-id>

## Hypothesis
<what this lane tests>

## Active Slice
<slice id/objective>

## Dynamic Workflow Pattern
fan-out-and-synthesize | tournament | generate-and-filter | adversarial-verification | loop-until-done | classify-and-act | none

## Dispatch Gate
- fan_out_allowed: yes | no
- independence_evidence:
- shared_write_targets:
- evaluator:
- cost_gate_status:
- serial_fallback:

## Seed
<seed id/hash>

## Evidence
- <artifact, command, source, trace, or result>

## Scores
- progress_score:
- stuck_signals:
- fallback_or_uncertainty_rate:
- evidence_gap:

## Recommendation
promote | keep-candidate | prune | rerun

## Candidate Outputs
- <candidate ids or none>
