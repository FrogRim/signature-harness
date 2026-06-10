# Signature Harness 구현/설계 검수 문서

작성일: 2026-06-10

대상 저장소: `FrogRim/signature-harness`

현재 기준 커밋:

- `7c913bf` - Preserve Signature Harness as a portable private repo
- `a961fe6` - Expose Signature Harness through host plugin marketplaces
- `ced1dc6` - Require evidence-backed dynamic workflows

## 1. 요약

Signature Harness는 Codex나 Claude Code 위에서 동작하는 개인용 goal-loop harness다. 핵심 목표는 하나의 고정된 프롬프트 파이프라인을 만드는 것이 아니라, 사용자의 목적을 끝까지 검증 가능한 방식으로 운행하는 loop engineering 체계를 만드는 것이다.

이 저장소는 현재 독립 실행형 대형 CLI가 아니라, host-native plugin/skill bundle과 작은 deterministic runtime substrate의 조합으로 구현되어 있다.

구현 방향은 다음과 같다.

- Goal을 최상위 작업 단위로 둔다.
- Seed를 실행 계약으로 둔다.
- Active Slice로 현재 실행 범위를 제한한다.
- Orchestration Loop는 관제센터 역할만 수행하고 직접 구현하지 않는다.
- Goal Loop는 실제 작업 전차 역할을 한다.
- Red Team은 과잉 낙관, sycophancy, 누락된 증거, drift를 공격한다.
- Oracle은 완료 판정을 담당하며 `COMPLETE`, `INCOMPLETE`, `BLOCKED`를 구분한다.
- `INCOMPLETE`는 상태가 아니라 verdict이며, `GAP_FILL` 실행 상태로 전환된다.
- Blocked rehydration은 LLM 판단이 아니라 allowlisted mechanical check로만 재개된다.
- Dynamic Workflow는 기본값이 아니라 cost gate를 통과한 경우에만 사용된다.

## 2. 설계 목표

### 2.1 최종 목표

사용자가 정의한 `goal`을 얼마나 잘 끝까지 운행할 수 있는지에 최적화된 harness를 만드는 것이 목표다.

여기서 "잘 운행한다"는 것은 단순히 많은 작업을 수행한다는 뜻이 아니다.

- 목적이 drift 되지 않는다.
- 완료 조건이 불명확할 때 멈추거나 좁힌다.
- 증거 없이 완료를 주장하지 않는다.
- 실패나 정체를 반복하지 않는다.
- 사용자의 성향에 맞게 질문, 자율성, 검증 강도를 조정한다.
- 성공/실패 학습을 바로 active rule로 승격하지 않고 candidate/promotion gate를 거친다.

### 2.2 해결하려는 실패 모드

LLM agent에서 반복적으로 발생하는 문제를 구조적으로 줄이는 것이 설계의 출발점이다.

- Agentic laziness: 큰 작업 중 일부만 보고 완료했다고 선언한다.
- Self-preferential bias: 자기가 만든 결과를 자기가 관대하게 평가한다.
- Goal drift: 긴 컨텍스트나 compaction 과정에서 원래 제약이 희미해진다.
- Over-engineering: 완료 후에도 불안해서 불필요한 구조를 덧붙인다.
- Premature completion: 핵심 예외와 evidence gap이 있는데도 완료를 주장한다.
- Retry loop: 같은 실패를 다른 말로 반복한다.
- Unsafe resume: blocked 상태에서 임의 command string을 실행해 보안 위험을 만든다.

## 3. 전체 아키텍처

현재 공개 workflow surface는 작게 유지했다.

```text
goal intake
  -> active slice
  -> ambiguity scoring
  -> seed crystallization
  -> rule memory read
  -> orchestration routing
  -> red-team pressure
  -> execution/checkpoint
  -> staged oracle verification
  -> candidate/promotion or complete
```

기존 `research -> spec -> plan -> implement -> review`는 mandatory pipeline이 아니다. 특정 goal이 그 형태를 필요로 할 때만 선택되는 loop 중 하나다.

## 4. 핵심 구성요소

### 4.1 Goal

Goal은 harness의 최상위 작업 단위다.

구현 위치:

- `README.md`
- `AGENTS.md`
- `templates/GOAL.md`
- `skills/goal-loop/SKILL.md`

Goal schema는 objective, why, success criteria, constraints, non-goals, autonomy level, verification, stop condition 등을 포함한다.

왜 이렇게 했는가:

- 대화형 prompt는 쉽게 흐려진다.
- 긴 작업에서는 "현재 하고 있는 일"과 "원래 달성해야 할 일"이 분리된다.
- Goal을 구조화해야 active slice, seed, oracle, red-team이 같은 기준을 공유할 수 있다.

### 4.2 Active Slice

Active Slice는 큰 goal 중 현재 실행 가능한 최소 단위다.

구현 위치:

- `skills/active-slice/SKILL.md`
- `templates/GOAL_HIERARCHY.md`
- `README.md`
- `AGENTS.md`

핵심 규칙:

- global goal은 유지한다.
- 현재 slice만 실행한다.
- slice마다 completion signal과 evidence plan을 둔다.
- slice를 줄여서 전체 goal이 끝난 것처럼 주장하지 않는다.

왜 이렇게 했는가:

- 큰 goal을 한 번에 실행하면 drift와 premature completion 위험이 커진다.
- 반대로 전체 목적을 잊고 slice만 완료하면 부분 최적화가 된다.
- 그래서 global goal과 active slice를 동시에 유지한다.

### 4.3 Seed

Seed는 Goal에서 파생된 immutable execution contract다.

구현 위치:

- `skills/seed-crystallizer/SKILL.md`
- `templates/SEED.md`
- `README.md`
- `AGENTS.md`

핵심 규칙:

- broad execution 전에 Seed를 accepted 상태로 고정한다.
- Seed에는 objective, constraints, acceptance criteria, non-goals, ontology, evaluation plan, exit conditions가 들어간다.
- 수정이 필요하면 기존 Seed를 조용히 바꾸지 않고 generation을 올린다.

왜 이렇게 했는가:

- prompt는 실행 중에 계속 변형될 수 있다.
- Seed는 "이 goal loop가 실제로 무엇을 하기로 했는가"를 고정하는 기준점이다.
- Oracle, Red Team, Orchestration이 동일한 기준으로 판단할 수 있다.

### 4.4 Rule Memory Read

모든 규칙을 항상 prompt에 넣지 않고, 현재 loop와 active slice에 필요한 규칙만 읽는 방식이다.

구현 위치:

- `skills/rule-memory-read/SKILL.md`
- `templates/RULE_MEMORY.md`
- `README.md`
- `AGENTS.md`

왜 이렇게 했는가:

- 많은 규칙을 항상 넣으면 컨텍스트가 무거워지고 서로 충돌한다.
- 사용자 fit, mode, domain, failure rule을 매번 전부 주입하면 오히려 decision noise가 늘어난다.
- 필요한 규칙만 선택해야 loop engineering의 제어력이 올라간다.

## 5. Orchestration Loop

Orchestration Loop는 사용자가 비유한 "관제센터"다.

구현 위치:

- `skills/orchestration-loop/SKILL.md`
- `templates/ORCHESTRATION_RECEIPT.md`
- `templates/ORCHESTRATION_DIRECTIVE.md`
- `scripts/sh_runtime.py`
- `README.md`
- `AGENTS.md`

### 5.1 역할

Orchestration Loop는 Goal Loop를 직접 구현하지 않는다.

Allowed:

- goal state 읽기
- heartbeat, budget, red-team/oracle receipt 읽기
- no-progress signal 감지
- `.sh/orchestration/` 아래 routing receipt/directive 쓰기
- `.sh/ledger.jsonl`에 최소 steering event 기록

Forbidden:

- source file 수정
- implementation work 수행
- goal complete 판정
- accepted Seed를 조용히 변경
- active rule/user fit/seed default를 promotion gate 없이 변경
- free-form resume command 실행

왜 이렇게 했는가:

- 관제센터가 직접 선로를 깔고 전차를 운전하면 책임 경계가 무너진다.
- Orchestration은 control plane이어야 하고, 실제 작업은 Goal Loop/action plane이 해야 한다.
- 이렇게 나눠야 abort, pause, gap-fill, recovery 같은 제어가 명확해진다.

### 5.2 Watchdog

구현된 기본값:

```text
heartbeat tick: 60 seconds
missed heartbeat: 180 seconds
hard-abort candidate: 300 seconds
```

hard abort는 단순 heartbeat 누락만으로 실행하지 않는다. heartbeat missing에 더해 process/session unresponsive 또는 critical risk가 있어야 한다.

no-progress 기본 트리거:

- 같은 failure signature 3회
- evidence hash가 변하지 않았는데 같은 completion claim 3회
- 실행 증거 없이 plan-only churn 3회
- 같은 red-team/oracle finding 반복 3회

왜 이렇게 했는가:

- 너무 빠른 abort는 긴 명령이나 사용자 대기 상태를 잘못 죽인다.
- 너무 느슨한 retry는 무한 루프를 만든다.
- 따라서 heartbeat와 no-progress를 분리하고, retry를 기본 회복 전략에서 제외했다.

## 6. 상태 머신

구현 위치:

- `scripts/sh_runtime.py`
- `templates/STATE_MACHINE.md`
- `README.md`
- `AGENTS.md`
- `skills/orchestration-loop/SKILL.md`

상태 분류:

```text
Execution: RUNNING, GAP_FILL, RECOVERY
Suspended: PAUSED, BLOCKED
Terminal: COMPLETE, ABORTED
```

중요한 결정:

- `INCOMPLETE`는 runtime state가 아니라 Oracle verdict다.
- Oracle `INCOMPLETE`는 `GAP_FILL` 상태로 전환된다.
- terminal state인 `COMPLETE`, `ABORTED`는 재개하지 않는다.
- 명시되지 않은 transition은 system-level exception이다.

왜 이렇게 했는가:

- `INCOMPLETE`를 state로 두면 Goal Loop가 "다시 해볼게" 식의 넓은 retry를 반복하기 쉽다.
- `GAP_FILL`은 누락된 proof만 좁게 수행하게 만든다.
- terminal loop를 재사용하지 않으면 완료/폐기된 trace의 의미가 보존된다.

## 7. Oracle Verification

Oracle은 종착역의 신호등 역할이다.

구현 위치:

- `skills/oracle-verification/SKILL.md`
- `templates/ORACLE.md`
- `templates/EVIDENCE_GAP_REPORT.md`
- `templates/BLOCKED_RECEIPT.md`
- `README.md`
- `AGENTS.md`

### 7.1 Staged Verification

Oracle은 3단계로 동작한다.

1. Mechanical verification
   - lint, typecheck, build, tests, static checks, artifact existence
2. Semantic verification
   - success criteria mapping, goal alignment, non-goal respect, drift score
3. Consensus verification
   - uncertainty, risk, red-team disagreement, user request가 있을 때만 추가 critic/multi-agent review

왜 이렇게 했는가:

- 모든 일을 곧바로 consensus review로 보내면 token cost가 커진다.
- mechanical check가 실패한 상태에서 semantic review를 하는 것은 비효율적이다.
- cheap check부터 비싼 check로 올라가는 staged gate가 합리적이다.

### 7.2 Verdict

Oracle verdict:

- `COMPLETE`: evidence가 충분함
- `INCOMPLETE`: evidence가 누락되거나 mismatch됨
- `BLOCKED`: 사용자/권한/외부 상태가 필요함

`INCOMPLETE`일 때 반드시 `evidence_gap_report`를 반환한다.

왜 이렇게 했는가:

- 단순 "incomplete"는 Goal Loop가 넓은 재시도를 반복하게 한다.
- 누락된 evidence가 정확히 무엇인지 알아야 Orchestration이 Active Slice를 gap-fill로 줄일 수 있다.

## 8. Gap Fill

구현 위치:

- `skills/orchestration-loop/SKILL.md`
- `skills/oracle-verification/SKILL.md`
- `templates/EVIDENCE_GAP_REPORT.md`
- `README.md`
- `AGENTS.md`
- `scripts/sh_runtime.py`

Gap Fill 규칙:

- 동일 Seed를 유지한다.
- active slice를 missing proof acquisition으로 제한한다.
- unrelated implementation, cleanup, completion claim을 금지한다.
- Oracle recheck를 필수로 둔다.

왜 이렇게 했는가:

- `retry`는 같은 계획을 반복하게 만드는 위험이 있다.
- `gap-fill`은 "누락 증거 확보"만 수행하도록 경로를 좁힌다.
- completion 품질을 높이면서 over-engineering을 줄인다.

## 9. BLOCKED Rehydration

구현 위치:

- `templates/BLOCKED_RECEIPT.md`
- `templates/RESUME_CHECK_CONTRACT.md`
- `scripts/sh_runtime.py`
- `skills/orchestration-loop/SKILL.md`
- `skills/oracle-verification/SKILL.md`
- `README.md`
- `AGENTS.md`

Blocked 상태는 사용자 action, credential, permission, external service, destructive authority, waiting CI 등으로 인해 진행이 멈춘 상태다.

Resume 절차:

1. blocked receipt를 읽는다.
2. `resume_check_id`를 allowlisted contract로 해석한다.
3. LLM에게 안전 여부를 묻지 않는다.
4. fixed `argv`, `shell: false`, env-only secret injection, timeout, sandbox 요구를 검증한다.
5. security violation이면 `ABORTED`로 간주할 수 있는 security incident를 만든다.
6. check가 실패하면 `BLOCKED` 유지.
7. check가 통과하면 hash domain을 비교하고 `RECOVERY`로 전환한다.

왜 이렇게 했는가:

- blocked 후 재개는 가장 위험한 구간이다.
- 사용자 입력/API key를 command string에 포매팅하면 RCE/shell injection 위험이 있다.
- resume은 LLM 판단이 아니라 deterministic contract validation이 담당해야 한다.

## 10. Resume Check Security Contract

구현 위치:

- `scripts/sh_runtime.py`
- `templates/RESUME_CHECK_CONTRACT.md`
- `README.md`
- `AGENTS.md`

강제 규칙:

- command string 실행 금지
- fixed argv만 허용
- `shell: false` 필수
- user secret은 environment variable로만 주입
- shell metacharacter 검출 시 reject/security violation
- sandbox required
- network/write access는 allowlist 기반

현재 `run-resume`은 의도적으로 fail-closed다. 실제 sandbox adapter는 아직 구현하지 않았다.

왜 이렇게 했는가:

- sandbox 없이 resume command를 실행하는 것은 harness의 가장 약한 보안 고리가 된다.
- 안전한 adapter가 없으면 실행하지 않는 것이 맞다.
- 따라서 `validate-resume`은 구현하고, `run-resume`은 fail-closed로 둔다.

## 11. Hash Domains

구현 위치:

- `scripts/sh_runtime.py`
- `templates/HASH_MANIFEST.json`
- `README.md`
- `AGENTS.md`
- `skills/orchestration-loop/SKILL.md`
- `skills/oracle-verification/SKILL.md`

두 hash domain:

- `drift_hash`: active-slice target file/directories와 Git diff/content hash
- `evidence_hash`: Oracle evidence-map assets의 content hash

제외:

- 전체 repo space
- `.sh/` harness state
- global temp directory
- unrelated source files

왜 이렇게 했는가:

- 전체 repo hash를 보면 unrelated change 때문에 recovery가 막힌다.
- `.sh/` 상태 폴더까지 drift에 넣으면 harness 기록 자체가 drift를 만든다.
- active slice와 evidence asset만 분리해야 재개 판단이 정확해진다.

## 12. Red Team

구현 위치:

- `skills/red-team/SKILL.md`
- `templates/RED_TEAM.md`
- `README.md`
- `AGENTS.md`

Red Team은 다음을 공격한다.

- sycophancy
- optimism bias
- hidden assumptions
- missing non-goals
- weak tests
- unverifiable completion
- scope drift
- unsafe execution path
- seed drift

Verdict:

- `PASS`
- `WARN`
- `BLOCK`

왜 이렇게 했는가:

- 사용자가 지적한 "AI가 너무 호의적이고 낙관적"인 문제를 구조적으로 완화한다.
- self-review만으로는 self-preferential bias가 남는다.
- Red Team은 계획 전, high-risk execution 전, completion 전 압력을 준다.

## 13. Evolution Loop / Unstuck

구현 위치:

- `skills/evolution-loop/SKILL.md`
- `skills/unstuck/SKILL.md`
- `templates/EVOLUTION.md`
- `templates/UNSTUCK.md`
- `README.md`
- `AGENTS.md`

사용 시점:

- 같은 실패 반복
- oracle failure가 단순 evidence gap이 아님
- seed가 잘못됨
- approach가 oscillation함
- stagnation signal 발생

왜 이렇게 했는가:

- 실패 후 단순 retry를 금지했기 때문에 대체 회복 경로가 필요하다.
- `GAP_FILL`은 Seed가 유효할 때만 사용한다.
- Seed/전략 자체가 틀렸다면 Evolution 또는 Unstuck으로 lateral search를 해야 한다.

## 14. Improvement Candidate / Promotion Gate

구현 위치:

- `skills/improvement-candidate/SKILL.md`
- `skills/promotion-gate/SKILL.md`
- `templates/IMPROVEMENT_CANDIDATE.md`
- `templates/PROMOTION_GATE.md`
- `README.md`
- `AGENTS.md`

핵심 원칙:

- run learning은 바로 active rule이 되지 않는다.
- candidate로 기록한다.
- promotion gate가 evidence, regression, scope를 검토한다.
- rejected candidate도 evidence로 남긴다.

왜 이렇게 했는가:

- agent가 한 번의 경험을 과잉 일반화하면 harness fit이 망가진다.
- 사용자의 선호/규칙은 trace-backed promotion을 거쳐야 한다.
- 이것이 개인화와 안전성을 동시에 유지하는 방법이다.

## 15. Parallel Hypothesis

구현 위치:

- `skills/parallel-hypothesis/SKILL.md`
- `templates/HYPOTHESIS_RUN.md`
- `README.md`
- `AGENTS.md`

Parallel worker는 "많이 돌리기"가 아니라 hypothesis experiment다.

각 run 기록:

- hypothesis
- active slice
- seed id/hash
- evidence
- progress score
- stuck signals
- uncertainty/fallback rate
- recommendation

왜 이렇게 했는가:

- 병렬 agent는 비용이 크다.
- 독립 가설과 비교 가능한 evidence가 없으면 병렬화가 검증 품질을 올리지 못한다.
- leader가 promotion을 소유해야 worker 결과가 active memory를 마음대로 바꾸지 않는다.

## 16. Dynamic Workflow Contracts

구현 위치:

- `templates/DYNAMIC_WORKFLOW.md`
- `templates/DYNAMIC_WORKFLOW_EVIDENCE.json`
- `scripts/sh_runtime.py`
- `skills/orchestration-loop/SKILL.md`
- `skills/oracle-verification/SKILL.md`
- `skills/parallel-hypothesis/SKILL.md`
- `templates/LOOP_PLAN.md`
- `templates/ORACLE.md`
- `templates/HYPOTHESIS_RUN.md`
- `README.md`
- `AGENTS.md`
- plugin manifests

### 16.1 왜 추가했는가

Hugh Kim의 dynamic workflow 관점에서 핵심은 "static harness"와 "dynamic workflow"를 구분하는 것이다.

정적 harness는 항상 같은 단계로 검색/검증/요약을 반복한다. 반면 dynamic workflow는 task shape에 맞춰 그때그때 작업장을 구성한다.

다만 모든 작업에 dynamic workflow를 쓰면 token cost가 커지고 과한 구조가 된다. 그래서 SH에서는 dynamic workflow를 기본값이 아니라 opt-in/high-compute path로 둔다.

### 16.2 Canonical Patterns

현재 고정한 6개 pattern:

- `classify-and-act`
- `fan-out-and-synthesize`
- `adversarial-verification`
- `generate-and-filter`
- `tournament`
- `loop-until-done`

왜 이렇게 했는가:

- "loop"라는 단어가 너무 모호하다.
- pattern vocabulary가 있어야 orchestration, evidence, oracle이 같은 구조를 이해한다.
- 패턴 수를 작게 유지해야 사용자가 mental model을 유지할 수 있다.

### 16.3 Cost Gate

Dynamic workflow는 다음 조건을 만족해야 한다.

- active slice가 broad/parallel/risky/adversarial/repeatedly incomplete하다.
- 각 lane이 comparable evidence를 반환할 수 있다.
- synthesis/filter/tournament rule이 명확하다.
- extra token/time cost가 known failure mode를 줄인다.

왜 이렇게 했는가:

- Dynamic workflow는 강력하지만 비싸다.
- 일반 coding task에 리뷰어 5명짜리 패널을 붙이면 과하다.
- cost gate가 있어야 "작업장 설계"와 "과잉 오케스트레이션"을 구분할 수 있다.

### 16.4 Evidence Contract

`templates/DYNAMIC_WORKFLOW_EVIDENCE.json` 구조:

- `workflow_id`
- `goal_id`
- `seed_id`
- `active_slice`
- `pattern`
- `cost_gate`
- `records`
- `acceptance_verified`
- `incomplete`
- `all_done`

`scripts/sh_runtime.py validate-workflow-evidence`가 이를 검증한다.

반환 의미:

- schema invalid: runtime validation 실패
- schema valid + `completion_allowed: false`: Oracle은 `INCOMPLETE`로 판단하고 `GAP_FILL`로 좁힌다.
- schema valid + `completion_allowed: true`: Oracle complete 후보가 될 수 있다. 단, Oracle의 다른 stage도 통과해야 한다.

왜 이렇게 했는가:

- "여러 agent가 다 했다고 했다"는 완료 증거가 아니다.
- 완료 가능성을 evidence contract로 기계 검증해야 한다.
- incomplete record를 명시해야 다음 slice를 정확히 줄일 수 있다.

## 17. Runtime Substrate

구현 위치:

- `scripts/sh_runtime.py`
- `scripts/README.md`

현재 command:

- `init-state`
- `validate-transition`
- `hash-manifest`
- `validate-resume`
- `validate-workflow-evidence`
- `run-resume`
- `write-directive`
- `append-ledger`
- `self-test`

왜 Python substrate로 구현했는가:

- 이 부분은 LLM에게 맡기면 안 되는 deterministic check다.
- state transition, hash, resume security, evidence schema validation은 기계적으로 검증해야 한다.
- 하지만 아직 standalone runtime CLI 제품까지 만들 필요는 없으므로 작은 substrate로 제한했다.

## 18. Plugin / Host Integration

구현 위치:

- `plugin.json`
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.codex-plugin/plugin.json`
- `.codex-plugin/marketplace.json`
- `commands/sh.md`
- `skills/sh-goal/SKILL.md`
- `scripts/install_local.ps1`

설계:

- Claude Code는 plugin marketplace/install surface를 우선 사용한다.
- Codex는 현재 CLI plugin manager 제약 때문에 marketplace add + fallback skill install을 문서화한다.
- fallback installer는 dev/local 용도이며 marker-based overwrite 정책을 사용한다.

왜 이렇게 했는가:

- 사용자가 노트북에서도 쓰고 싶어 했기 때문에 GitHub repo 기반 설치가 필요했다.
- 별도 runtime CLI보다 host-native plugin/skill surface가 현재 목적에 더 가볍다.
- Codex/Claude Code의 명령어 체계가 다르므로 공통 core는 `skills/`, host adapter는 plugin manifest/command로 둔다.

## 19. 현재 구현된 것과 구현하지 않은 것

### 구현됨

- Goal-loop 중심 public surface
- Seed/ambiguity/oracle/evolution/unstuck 문서 및 skill surface
- Orchestration control plane 규칙
- Execution/Suspended/Terminal state machine
- Gap-fill contract
- Blocked rehydration contract
- Resume-check security validation
- Hash domain separation
- Red-team gate
- Candidate/promotion learning discipline
- Parallel hypothesis contract
- Dynamic workflow canonical patterns/cost gate/evidence schema
- Deterministic runtime substrate commands
- Claude/Codex plugin metadata
- local fallback installer

### 의도적으로 아직 구현하지 않음

- 독립 standalone runtime CLI 제품
- JS workflow runner
- 실제 sandbox adapter 기반 `run-resume`
- global config mutation hook
- automatic multi-agent process manager
- remote MCP orchestration server
- 공개 marketplace 배포 자동화

왜 아직 구현하지 않았는가:

- 현재 목표는 개인용 harness의 contract와 host integration을 안정화하는 것이다.
- runtime을 크게 만들면 검증해야 할 surface가 급격히 커진다.
- 보안상 sandbox adapter 없는 resume execution은 허용할 수 없다.
- 먼저 skill/plugin 계약이 사용자의 실제 workflow에 fit하는지 확인해야 한다.

## 20. 외부 reference에서 가져온 아이디어

### Gajae-Code

채택:

- 작은 public workflow surface
- durable ledger 중심 사고
- planner/critic/architect 역할 분리
- 필요할 때만 team/tmux parallelism
- remote control surface에 대한 fail-closed 태도

적용 방식:

- SH는 public command를 작게 유지하고, 내부 skill/contract로 확장한다.
- Orchestration은 직접 구현하지 않는 control plane으로 제한했다.

### LazyCodex / OmO

채택:

- 간단한 설치 UX
- 검증된 completion loop
- project memory/goal hierarchy 사고

적용 방식:

- plugin-native install과 fallback local install을 동시에 지원한다.
- 완료는 Oracle evidence gate를 통과해야 한다.

### Ouroboros

채택:

- Seed
- ambiguity scoring
- restate/lock gate
- mechanical -> semantic -> consensus oracle
- drift scoring
- evolution loop
- unstuck/lateral persona

적용 방식:

- full Agent OS/kernel은 복제하지 않았다.
- SH에 필요한 loop contract primitive만 가져왔다.

### Pocketmon-Harness

채택:

- global goal + active executable slice
- rule memory read
- deterministic/mechanical authority before LLM fallback
- trace-backed improvement candidate
- QA-gated promotion
- parallel worker as hypothesis experiment
- gap closure records

적용 방식:

- mGBA/Pokemon runtime은 가져오지 않았다.
- 개인 goal harness에 맞는 learning/promotion discipline만 반영했다.

### Dynamic Workflows Article

채택:

- static harness와 dynamic workflow 구분
- classify-and-act
- fan-out-and-synthesize
- adversarial verification
- generate-and-filter
- tournament
- loop-until-done
- agentic laziness/self-preferential bias/goal drift framing

적용 방식:

- 6개 canonical pattern으로 vocabulary를 고정했다.
- cost gate로 dynamic workflow 사용 조건을 제한했다.
- evidence contract와 runtime validator를 추가했다.

## 21. 검증 내역

마지막 dynamic workflow 반영 기준 검증:

```powershell
py scripts/sh_runtime.py self-test
py -m py_compile scripts/sh_runtime.py
py scripts/sh_runtime.py validate-workflow-evidence --evidence templates/DYNAMIC_WORKFLOW_EVIDENCE.json
claude plugin validate .
```

추가 검증:

- JSON manifests parse with `ConvertFrom-Json`
- stale version string search
- `git diff --check`
- incomplete workflow evidence smoke test
- scoped anti-slop review
- self code review: APPROVE / architectural status CLEAR
- ultragoal 13/13 complete

## 22. 주요 파일 맵

```text
README.md
  전체 설계 설명, runtime state, orchestration, dynamic workflow, reference adoption

AGENTS.md
  Codex adapter operating contract

scripts/sh_runtime.py
  deterministic substrate: state transition, hash manifest, resume validation, workflow evidence validation

scripts/install_local.ps1
  fallback/dev local installer

plugin.json
.claude-plugin/*
.codex-plugin/*
  host-native plugin metadata

commands/sh.md
  Claude slash command entrypoint

skills/*
  portable workflow surface

templates/*
  durable artifact contracts
```

## 23. 검수자가 봐야 할 핵심 쟁점

검수 시 다음 질문을 중심으로 보면 된다.

1. Orchestration Loop가 정말 control plane으로 제한되어 있는가?
2. `INCOMPLETE`를 state가 아니라 verdict로 둔 결정이 일관되게 반영되어 있는가?
3. `GAP_FILL`이 retry와 명확히 분리되어 있는가?
4. Resume check security contract가 충분히 fail-closed인가?
5. Hash domain이 active slice/evidence asset으로 충분히 좁혀져 있는가?
6. Dynamic workflow가 cost gate 없이 남용될 수 있는 구멍이 있는가?
7. Evidence contract가 "agent가 done이라고 말했다"를 완료 증거로 오인하지 않게 막는가?
8. Plugin-native install과 fallback installer의 책임 경계가 명확한가?
9. 현재 구현 수준에서 standalone runtime CLI를 미룬 결정이 타당한가?
10. 사용자 fit을 반영하는 candidate/promotion 구조가 과잉 자동 학습을 막는가?

## 24. 남은 작업

다음 단계 후보:

1. 실제 sandbox adapter 기반 `run-resume` 구현
2. host별 plugin install smoke test를 별도 machine에서 수행
3. user-fit calibration 문답/trace 기반 candidate 생성
4. dynamic workflow 실제 세션 샘플 3개 수집
5. Oracle evidence map과 coverage/test artifact 연동 강화
6. `.sh/` runtime state writer를 더 넓게 자동화
7. 검수 결과에 따라 contract wording과 validator schema 보강

## 25. 검수 후 보강 내역

핵심 contract 경로 검수에서 지적된 약한 보장 지점을 substrate와 문서에 반영했다.

반영된 수정:

- `write-directive`의 `--payload`가 `to_state`, `action`, `allow_more_execution`, `oracle_recheck_required` 같은 reserved key를 덮어쓰지 못하게 했다. 추가 payload는 `extra` 아래에만 들어간다.
- resume contract는 blocked receipt의 `resume_check_contract_sha256`과 `resume_check_id`에 바인딩할 수 있게 했다. 이제 잘 형성된 임의 JSON contract만으로는 충분하지 않다.
- Windows 환경의 command injection 구멍을 줄이기 위해 `&`, `%`, `^`, `!`를 shell metacharacter 검사에 추가하고 `.bat`, `.cmd`, `.ps1`, `npm`, `npx`, `pnpm`, `yarn` 같은 Windows script shim을 reject한다.
- `allowed_egress`는 `host:port` 형식으로 제한하고, `writable_paths`는 `<sandbox-tmp>` 또는 `declared_evidence_outputs`에 포함된 상대 경로만 허용한다.
- `GAP_FILL`/`RECOVERY`에도 heartbeat timeout, critical risk, security violation의 abort transition을 추가했다.
- `GAP_FILL`에는 3-strikes 이전의 `proof_still_missing` self-loop를 명시했다.
- `RECOVERY -> BLOCKED`, `PAUSED -> ABORTED` 경로를 추가해 문서의 orchestration route와 상태 머신을 맞췄다.
- dynamic workflow evidence validator에 `--require-artifacts --root <path>`와 `--evidence-manifest <path>` 옵션을 추가했다. 이 모드에서는 evidence 값이 실제 존재하는 파일이어야 하며, 선택적으로 `hash-manifest`의 `evidence_entries`에 등록된 자산인지까지 확인한다. `goal_id`, `seed_id`, `active_slice`도 필요하다.
- `hash-manifest`는 drift target 삭제를 에러로만 처리하지 않고 `status: missing` 항목으로 drift hash에 포함한다.
- Git diff hash는 우선 `git diff HEAD -- <paths>`를 사용해 staged 변경까지 포함하려고 시도하고, 실패 시 기존 diff 방식으로 fallback한다.
- ledger append는 `prev_hash`와 `entry_hash`를 기록하는 hash-chain으로 바꿨다.

남은 보강 후보:

- 실제 sandbox adapter 구현 전, executable allowlist를 더 좁혀야 한다.
- workflow evidence artifact mode를 Oracle 기본 경로로 강제할지, high-risk/dynamic workflow에서만 강제할지 결정해야 한다.
- promotion gate와 ledger hash-chain 검증 명령을 별도 command로 분리할 수 있다.
- 모든 legacy/utility skill의 active/legacy 지위를 표로 정리하면 검수 범위가 더 명확해진다.

## 26. 결론

현재 Signature Harness는 "큰 런타임 제품"이 아니라 "host-native agent 위에서 goal을 안전하게 운행하기 위한 계약/검증 중심 harness"로 구현되어 있다.

핵심 설계 선택은 책임 분리다.

- Goal Loop는 실행한다.
- Orchestration Loop는 관제한다.
- Red Team은 공격적으로 의심한다.
- Oracle은 증거 기반으로 완료를 승인한다.
- Runtime substrate는 LLM이 하면 안 되는 deterministic check를 담당한다.

이 방식은 token cost를 무조건 줄이는 설계가 아니다. 사용자가 원한 "goal을 잘 돌리는 loop engineering"에 맞춰, 필요한 곳에서는 token을 더 쓰되 그 비용이 검증 가능성과 drift 방지로 이어지도록 설계했다.
