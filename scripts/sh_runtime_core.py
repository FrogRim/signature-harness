"""Shared core primitives for the Signature Harness runtime.

This module holds invariants and small deterministic helpers. Command handlers
stay in ``sh_runtime.py`` so the public CLI surface remains stable.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


EXECUTION_STATES = {"RUNNING", "GAP_FILL", "RECOVERY", "REMEDIATING"}
SUSPENDED_STATES = {"PAUSED", "BLOCKED"}
TERMINAL_STATES = {"COMPLETE", "ABORTED"}
ALL_STATES = EXECUTION_STATES | SUSPENDED_STATES | TERMINAL_STATES

TRANSITIONS: Dict[Tuple[str, str], str] = {
    ("RUNNING", "oracle_complete"): "COMPLETE",
    ("RUNNING", "oracle_incomplete"): "GAP_FILL",
    ("RUNNING", "oracle_blocked"): "BLOCKED",
    ("RUNNING", "redteam_no_progress"): "PAUSED",
    ("RUNNING", "heartbeat_timeout"): "ABORTED",
    ("RUNNING", "critical_risk"): "ABORTED",
    ("RUNNING", "security_violation"): "ABORTED",
    ("RUNNING", "sut_hang_incomplete"): "REMEDIATING",
    ("GAP_FILL", "missing_proof_acquired"): "RUNNING",
    ("GAP_FILL", "proof_still_missing"): "GAP_FILL",
    ("GAP_FILL", "proof_still_missing_3x"): "PAUSED",
    ("GAP_FILL", "oracle_blocked"): "BLOCKED",
    ("GAP_FILL", "heartbeat_timeout"): "ABORTED",
    ("GAP_FILL", "critical_risk"): "ABORTED",
    ("GAP_FILL", "security_violation"): "ABORTED",
    ("GAP_FILL", "sut_hang_incomplete"): "REMEDIATING",
    ("BLOCKED", "rehydration_pass"): "RECOVERY",
    ("BLOCKED", "rehydration_fail"): "BLOCKED",
    ("RECOVERY", "recovery_validated"): "RUNNING",
    ("RECOVERY", "oracle_blocked"): "BLOCKED",
    ("RECOVERY", "drift_detected"): "PAUSED",
    ("RECOVERY", "heartbeat_timeout"): "ABORTED",
    ("RECOVERY", "critical_risk"): "ABORTED",
    ("RECOVERY", "security_violation"): "ABORTED",
    ("RECOVERY", "sut_hang_incomplete"): "REMEDIATING",
    ("REMEDIATING", "cleanup_evidence_valid"): "GAP_FILL",
    ("REMEDIATING", "cleanup_evidence_invalid"): "REMEDIATING",
    ("REMEDIATING", "cleanup_timeout"): "ABORTED",
    ("REMEDIATING", "heartbeat_timeout"): "ABORTED",
    ("REMEDIATING", "critical_risk"): "ABORTED",
    ("REMEDIATING", "security_violation"): "ABORTED",
    ("PAUSED", "evolution_accepted"): "RUNNING",
    ("PAUSED", "unstuck_accepted"): "RUNNING",
    ("PAUSED", "seed_update_accepted"): "RUNNING",
    ("PAUSED", "abort_requested"): "ABORTED",
    ("PAUSED", "critical_risk"): "ABORTED",
    ("PAUSED", "security_violation"): "ABORTED",
}

EVENT_ACTION = {
    "oracle_complete": "close",
    "oracle_incomplete": "gap-fill",
    "oracle_blocked": "blocked",
    "redteam_no_progress": "pause",
    "heartbeat_timeout": "abort",
    "critical_risk": "abort",
    "security_violation": "abort",
    "sut_hang_incomplete": "remediate",
    "missing_proof_acquired": "continue",
    "proof_still_missing": "gap-fill",
    "proof_still_missing_3x": "pause",
    "cleanup_evidence_valid": "gap-fill",
    "cleanup_evidence_invalid": "remediate",
    "cleanup_timeout": "abort",
    "abort_requested": "abort",
    "rehydration_pass": "recovery",
    "rehydration_fail": "blocked",
    "recovery_validated": "continue",
    "drift_detected": "pause",
    "evolution_accepted": "continue",
    "unstuck_accepted": "continue",
    "seed_update_accepted": "continue",
}

LEDGER_EVENT_TYPES = {
    "goal_created",
    "active_slice_selected",
    "seed_created",
    "seed_accepted",
    "rule_memory_read",
    "orchestration",
    "directive",
    "heartbeat",
    "checkpoint",
    "red_team",
    "oracle",
    "candidate",
    "promotion",
    "hypothesis",
    "workflow",
    "gap",
    "gap_fill",
    "recovery",
    "evolution",
    "unstuck",
    "steering",
    "paused",
    "blocked",
    "aborted",
    "complete",
    "remediation",
}

DEFAULT_DRIFT_EXCLUDE_NAMES = {
    ".git",
    ".sh",
    ".omx",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

SHELL_META_PATTERNS = ("&&", ";", "|", "&", "`", "$(", "%", "^", "!", ">", "<", "\n", "\r")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
EGRESS_RE = re.compile(r"^[A-Za-z0-9.-]+:[0-9]{1,5}$")
WINDOWS_SCRIPT_SUFFIXES = (".bat", ".cmd", ".ps1")
WINDOWS_SCRIPT_SHIM_NAMES = {"npm", "npx", "pnpm", "yarn"}
RESERVED_DIRECTIVE_KEYS = {
    "run_id",
    "goal_id",
    "seed_id",
    "active_slice",
    "issued_at",
    "from_state",
    "to_state",
    "action",
    "required_next_owner",
    "allow_more_execution",
    "oracle_recheck_required",
    "heartbeat_policy",
}
RESERVED_LEDGER_KEYS = {"prev_hash", "entry_hash"}
DYNAMIC_WORKFLOW_PATTERNS = {
    "classify-and-act",
    "fan-out-and-synthesize",
    "adversarial-verification",
    "generate-and-filter",
    "tournament",
    "loop-until-done",
}
AGENT_NAME = "signature-harness"
AGENT_VERSION = "0.9.0-runtime-evals"
SCHEMA_VERSION = "0.9.0-schema-contracts"
RUN_ARTIFACT_FILES = {
    "manifest": "run_manifest.json",
    "state": "state.json",
    "step_ledger": "step_ledger.jsonl",
    "interruptions": "interruptions.json",
    "handoff": "handoff.md",
    "replay": "replay.json",
    "trace": "trace.jsonl",
    "tool_calls": "tool_calls.jsonl",
    "cost_latency": "cost_latency.json",
    "artifacts": "artifacts.json",
}
ALLOWED_EVIDENCE_SUFFIXES = {
    ".md",
    ".markdown",
    ".json",
    ".jsonl",
    ".log",
    ".txt",
    ".diff",
    ".patch",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}
PERMISSION_PROFILES = {"read_only", "workspace_write", "scoped_network", "danger_full_access"}
FAILURE_CODES = {
    "MISSING_CONTEXT",
    "WRONG_TOOL",
    "TOOL_SCHEMA_ERROR",
    "FAILED_TEST",
    "LOOP_DETECTED",
    "PERMISSION_DENIED",
    "UNSAFE_ACTION",
    "OVER_BUDGET",
    "NEEDS_HUMAN_DECISION",
    "NO_PROGRESS",
    "REPEATED_TOOL_FAILURE",
    "INVALID_EVIDENCE",
    "BLOCKED_APPROVAL",
    "UNSAFE_RESUME",
    "CONTRACT_VIOLATION",
    "ARTIFACT_MISMATCH",
    "BENCHMARK_INFRA_FAILURE",
    "SUT_HANG_TIMEOUT",
    "REMEDIATION_TIMEOUT",
}
EXPECTED_SCHEMA_FILES = {
    "tool_contracts.schema.json",
    "tool_contracts.json",
    "failure_taxonomy.schema.json",
    "failure_taxonomy.json",
    "run_manifest.schema.json",
    "trace_event.schema.json",
    "eval_task.schema.json",
    "security_policy.schema.json",
    "completion_artifact.schema.json",
    "scorecard.schema.json",
}
EXPECTED_TOOL_CONTRACTS = {
    "init-state",
    "validate-transition",
    "hash-manifest",
    "validate-resume",
    "validate-workflow-evidence",
    "run-resume",
    "write-directive",
    "append-ledger",
    "verify-ledger",
    "start-run",
    "resume-run",
    "record-step",
    "record-interruption",
    "replay-run",
    "validate-schemas",
    "validate-policy",
    "validate-completion-artifact",
    "validate-release",
    "run-evals",
    "self-test",
}


class ShRuntimeError(Exception):
    def __init__(self, message: str, code: int = 2, payload: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.code = code
        self.payload = payload or {}


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ShRuntimeError(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(str(tmp), str(path))


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ShRuntimeError(f"Invalid JSONL in {path} line {lineno}: {exc}") from exc
            if not isinstance(payload, dict):
                raise ShRuntimeError(f"JSONL row in {path} line {lineno} must be an object")
            rows.append(payload)
    return rows


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def load_json_object(path: Path, label: str) -> Dict[str, Any]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ShRuntimeError(f"{label} must be a JSON object")
    return payload


def load_json_array(path: Path, label: str) -> List[Any]:
    payload = load_json(path)
    if not isinstance(payload, list):
        raise ShRuntimeError(f"{label} must be a JSON array")
    return payload


def schema_type_matches(value: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(schema_type_matches(value, item) for item in expected)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def validate_against_schema(value: Any, schema: Dict[str, Any], path: str = "$") -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    expected_type = schema.get("type")
    if expected_type is not None and not schema_type_matches(value, expected_type):
        findings.append({"code": "schema_type_mismatch", "detail": f"{path} expected {expected_type!r}"})
        return findings
    if "const" in schema and value != schema["const"]:
        findings.append({"code": "schema_const_mismatch", "detail": f"{path} expected const {schema['const']!r}"})
    if "minimum" in schema and isinstance(value, (int, float)) and value < schema["minimum"]:
        findings.append({"code": "schema_minimum_violation", "detail": f"{path} must be >= {schema['minimum']!r}"})
    if "minItems" in schema and isinstance(value, list) and len(value) < int(schema["minItems"]):
        findings.append({"code": "schema_min_items_violation", "detail": f"{path} must contain at least {schema['minItems']} item(s)"})
    if isinstance(value, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in value:
                    findings.append({"code": "schema_missing_required", "detail": f"{path}.{key} is required"})
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, dict):
                    findings.extend(validate_against_schema(value[key], child_schema, f"{path}.{key}"))
            additional = schema.get("additionalProperties", True)
            extra_keys = sorted(set(value) - set(properties))
            if additional is False:
                for key in extra_keys:
                    findings.append({"code": "schema_additional_property", "detail": f"{path}.{key} is not allowed"})
            elif isinstance(additional, dict):
                for key in extra_keys:
                    findings.extend(validate_against_schema(value[key], additional, f"{path}.{key}"))
    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                findings.extend(validate_against_schema(item, item_schema, f"{path}[{index}]"))
    return findings


def now_epoch_ms() -> int:
    return int(time.time() * 1000)


def new_span_id() -> str:
    return uuid.uuid4().hex[:16]


def new_trace_id() -> str:
    return uuid.uuid4().hex


def stable_hash_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def safe_optional_int(value: Optional[int]) -> int:
    if value is None:
        return 0
    return int(value)


def safe_optional_float(value: Optional[float]) -> float:
    if value is None:
        return 0.0
    return float(value)


def sanitize_id(value: str, label: str) -> str:
    if not value or not SAFE_ID_RE.match(value):
        raise ShRuntimeError(f"Unsafe {label}: {value!r}")
    return value


def ensure_state(value: str, label: str) -> str:
    if value not in ALL_STATES:
        raise ShRuntimeError(f"Unknown {label}: {value!r}")
    return value


def transition_result(from_state: str, event: str, requested_to: Optional[str] = None) -> Dict[str, Any]:
    ensure_state(from_state, "from_state")
    expected = TRANSITIONS.get((from_state, event))
    ok = expected is not None and (requested_to is None or requested_to == expected)
    return {
        "ok": ok,
        "from_state": from_state,
        "event": event,
        "expected_to_state": expected,
        "requested_to_state": requested_to,
        "to_state": expected if ok else requested_to,
        "action": EVENT_ACTION.get(event),
        "terminal": expected in TERMINAL_STATES if expected else False,
        "listed_transition": expected is not None,
    }


def default_sh_dirs(root: Path) -> List[Path]:
    names = [
        "seeds",
        "rules",
        "runs",
        "orchestration",
        "orchestration/directives",
        "orchestration/blocked",
        "orchestration/gap-fill",
        "orchestration/security",
        "evidence",
        "candidates",
        "promotions",
        "hypotheses",
        "workflows",
        "gaps",
        "red-team",
        "oracle",
        "evolution",
        "unstuck",
    ]
    return [root / ".sh" / name for name in names]


def is_under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def rel_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def json_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def contains_excluded_part(path: Path, names: Iterable[str]) -> bool:
    excluded = set(names)
    return any(part in excluded for part in path.parts)


def has_shell_meta(value: str) -> Optional[str]:
    for pattern in SHELL_META_PATTERNS:
        if pattern in value:
            return pattern
    return None


def valid_egress(value: str) -> bool:
    if not isinstance(value, str) or not EGRESS_RE.match(value):
        return False
    try:
        port = int(value.rsplit(":", 1)[1])
    except ValueError:
        return False
    return 1 <= port <= 65535


def contract_sha256(contract: Dict[str, Any]) -> str:
    return json_sha256(contract)


def is_safe_relative_path(value: str) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = Path(value)
    if path.is_absolute():
        return False
    if any(part in {"..", ""} for part in path.parts):
        return False
    if has_shell_meta(value):
        return False
    return True


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def has_evidence(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(has_evidence(item) for item in value)
    if isinstance(value, dict):
        return any(has_evidence(item) for item in value.values())
    return False


def evidence_strings(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        result: List[str] = []
        for item in value:
            result.extend(evidence_strings(item))
        return result
    if isinstance(value, dict):
        result = []
        for item in value.values():
            result.extend(evidence_strings(item))
        return result
    return []
