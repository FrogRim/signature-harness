#!/usr/bin/env python3
"""
Signature Harness runtime substrate.

This is intentionally not a full product CLI. It provides mechanical checks that
should not be delegated to an LLM: state transitions, slice/evidence hashing,
directive writing, ledger appending, and resume-check contract validation.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


EXECUTION_STATES = {"RUNNING", "GAP_FILL", "RECOVERY"}
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
    ("GAP_FILL", "missing_proof_acquired"): "RUNNING",
    ("GAP_FILL", "proof_still_missing_3x"): "PAUSED",
    ("GAP_FILL", "oracle_blocked"): "BLOCKED",
    ("GAP_FILL", "security_violation"): "ABORTED",
    ("BLOCKED", "rehydration_pass"): "RECOVERY",
    ("BLOCKED", "rehydration_fail"): "BLOCKED",
    ("RECOVERY", "recovery_validated"): "RUNNING",
    ("RECOVERY", "drift_detected"): "PAUSED",
    ("RECOVERY", "security_violation"): "ABORTED",
    ("PAUSED", "evolution_accepted"): "RUNNING",
    ("PAUSED", "unstuck_accepted"): "RUNNING",
    ("PAUSED", "seed_update_accepted"): "RUNNING",
}

EVENT_ACTION = {
    "oracle_complete": "close",
    "oracle_incomplete": "gap-fill",
    "oracle_blocked": "blocked",
    "redteam_no_progress": "pause",
    "heartbeat_timeout": "abort",
    "critical_risk": "abort",
    "security_violation": "abort",
    "missing_proof_acquired": "continue",
    "proof_still_missing_3x": "pause",
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

SHELL_META_PATTERNS = (";", "&&", "|", "`", "$(", ">", "<", "\n", "\r")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
DYNAMIC_WORKFLOW_PATTERNS = {
    "classify-and-act",
    "fan-out-and-synthesize",
    "adversarial-verification",
    "generate-and-filter",
    "tournament",
    "loop-until-done",
}


class ShRuntimeError(Exception):
    def __init__(self, message: str, code: int = 2, payload: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.code = code
        self.payload = payload or {}


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def emit(payload: Dict[str, Any], code: int = 0) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code


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


def cmd_validate_transition(args: argparse.Namespace) -> int:
    payload = transition_result(args.from_state, args.event, args.to_state)
    if not payload["ok"]:
        payload["error"] = "transition_not_allowed"
        return emit(payload, 2)
    return emit(payload)


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


def cmd_init_state(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    for path in default_sh_dirs(root):
        path.mkdir(parents=True, exist_ok=True)
    ledger = root / ".sh" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.touch(exist_ok=True)
    return emit({"ok": True, "root": str(root), "created": [str(p) for p in default_sh_dirs(root)], "ledger": str(ledger)})


def is_under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def rel_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def json_sha256(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def contains_excluded_part(path: Path, names: Iterable[str]) -> bool:
    return any(part in set(names) for part in path.parts)


def collect_files(root: Path, targets: List[str], *, domain: str, exclude_names: Iterable[str]) -> List[Path]:
    files: List[Path] = []
    exclude_set = set(exclude_names)
    for raw in targets:
        target = (root / raw).resolve()
        if not is_under(target, root):
            raise ShRuntimeError(f"{domain} target escapes root: {raw!r}")
        rel = rel_posix(target, root) if target.exists() else raw.replace("\\", "/")
        if domain == "drift":
            if rel in {"", "."}:
                raise ShRuntimeError("drift target cannot be repository root; declare active-slice targets explicitly")
            if rel == ".sh" or rel.startswith(".sh/"):
                raise ShRuntimeError(f"drift target cannot include .sh harness state: {raw!r}")
        if domain == "evidence" and (rel.startswith(".sh/") and not rel.startswith(".sh/evidence/")):
            raise ShRuntimeError(f"evidence target may use .sh/evidence only, not other .sh state: {raw!r}")
        if not target.exists():
            raise ShRuntimeError(f"{domain} target does not exist: {raw!r}")
        if target.is_file():
            if domain == "drift" and contains_excluded_part(target.relative_to(root), exclude_set):
                continue
            files.append(target)
            continue
        if not target.is_dir():
            raise ShRuntimeError(f"{domain} target is not file or directory: {raw!r}")
        for current, dirs, filenames in os.walk(target):
            cur_path = Path(current)
            dirs[:] = [d for d in dirs if d not in exclude_set]
            for filename in filenames:
                p = cur_path / filename
                if domain == "drift" and contains_excluded_part(p.relative_to(root), exclude_set):
                    continue
                files.append(p)
    unique = sorted({p.resolve() for p in files}, key=lambda p: rel_posix(p, root))
    return unique


def hash_file_set(root: Path, files: List[Path]) -> Tuple[str, List[Dict[str, Any]]]:
    entries = []
    for path in files:
        stat = path.stat()
        entries.append(
            {
                "path": rel_posix(path, root),
                "sha256": file_sha256(path),
                "size": stat.st_size,
            }
        )
    return json_sha256(entries), entries


def git_diff_hash(root: Path, rel_paths: List[str]) -> Optional[str]:
    try:
        inside = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if inside.returncode != 0:
            return None
        cmd = ["git", "-C", str(root), "diff", "--no-ext-diff", "--binary", "--"] + rel_paths
        diff = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if diff.returncode != 0:
            return None
        return "sha256:" + hashlib.sha256(diff.stdout).hexdigest()
    except (OSError, subprocess.SubprocessError):
        return None


def cmd_hash_manifest(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest).resolve()
    manifest = load_json(manifest_path)
    root_raw = args.root or manifest.get("root") or "."
    root = (manifest_path.parent / root_raw).resolve() if not Path(root_raw).is_absolute() else Path(root_raw).resolve()
    drift_targets = manifest.get("drift_targets") or []
    evidence_assets = manifest.get("evidence_assets") or []
    if not isinstance(drift_targets, list) or not isinstance(evidence_assets, list):
        raise ShRuntimeError("drift_targets and evidence_assets must be lists")
    exclude_names = set(DEFAULT_DRIFT_EXCLUDE_NAMES)
    exclude_names.update(manifest.get("drift_exclude_names") or [])

    drift_files = collect_files(root, drift_targets, domain="drift", exclude_names=exclude_names)
    evidence_files = collect_files(root, evidence_assets, domain="evidence", exclude_names=set())
    drift_hash, drift_entries = hash_file_set(root, drift_files)
    evidence_hash, evidence_entries = hash_file_set(root, evidence_files)
    diff_hash = git_diff_hash(root, [entry["path"] for entry in drift_entries])
    payload = {
        "ok": True,
        "root": str(root),
        "generated_at": utc_now(),
        "drift_hash": drift_hash,
        "git_diff_hash": diff_hash,
        "drift_files": drift_entries,
        "evidence_hash": evidence_hash,
        "evidence_assets": evidence_entries,
        "excluded_from_drift": sorted(exclude_names),
    }
    return emit(payload)


def has_shell_meta(value: str) -> Optional[str]:
    for pattern in SHELL_META_PATTERNS:
        if pattern in value:
            return pattern
    return None


def validate_resume_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    findings: List[Dict[str, str]] = []

    def finding(code: str, detail: str) -> None:
        findings.append({"code": code, "detail": detail})

    check_id = contract.get("id")
    if not isinstance(check_id, str) or not SAFE_ID_RE.match(check_id):
        finding("invalid_id", "id must be a safe string")

    argv = contract.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
        finding("invalid_argv", "argv must be a non-empty list of strings")
    else:
        for item in argv:
            meta = has_shell_meta(item)
            if meta is not None:
                finding("shell_metacharacter", f"argv item contains {meta!r}")

    if contract.get("shell") is not False:
        finding("shell_not_false", "shell must be false")

    env_from_user = contract.get("env_from_user", [])
    if not isinstance(env_from_user, list) or not all(isinstance(x, str) and SAFE_ID_RE.match(x) for x in env_from_user):
        finding("invalid_env_from_user", "env_from_user must be a list of safe environment variable names")

    timeout = contract.get("timeout_sec")
    if not isinstance(timeout, int) or timeout <= 0 or timeout > 3600:
        finding("invalid_timeout", "timeout_sec must be an integer in 1..3600")

    allowed_egress = contract.get("allowed_egress", [])
    if not isinstance(allowed_egress, list) or not all(isinstance(x, str) for x in allowed_egress):
        finding("invalid_allowed_egress", "allowed_egress must be a list of strings")

    writable_paths = contract.get("writable_paths", [])
    if not isinstance(writable_paths, list) or not writable_paths or not all(isinstance(x, str) for x in writable_paths):
        finding("invalid_writable_paths", "writable_paths must be a non-empty list of strings")

    if contract.get("sandbox_required") is not True:
        finding("sandbox_required_missing", "sandbox_required must be true")

    if contract.get("records_secret") is not False:
        finding("records_secret_not_false", "records_secret must be false")

    rejected = bool(findings)
    return {
        "ok": not rejected,
        "status": "ok" if not rejected else "rejected_security",
        "recommended_state": "BLOCKED" if not rejected else "ABORTED",
        "security_findings": findings,
        "resume_check_id": check_id,
    }


def cmd_validate_resume(args: argparse.Namespace) -> int:
    contract = load_json(Path(args.contract).resolve())
    if not isinstance(contract, dict):
        raise ShRuntimeError("resume check contract must be a JSON object")
    result = validate_resume_contract(contract)
    return emit(result, 0 if result["ok"] else 3)


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def has_evidence(value: Any) -> bool:
    if is_non_empty_string(value):
        return True
    if isinstance(value, list):
        return any(is_non_empty_string(item) for item in value)
    return False


def validate_workflow_evidence_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    schema_findings: List[Dict[str, str]] = []
    completion_blockers: List[Dict[str, str]] = []

    def schema_finding(code: str, detail: str) -> None:
        schema_findings.append({"code": code, "detail": detail})

    def blocker(code: str, detail: str) -> None:
        completion_blockers.append({"code": code, "detail": detail})

    workflow_id = contract.get("workflow_id")
    if workflow_id is not None and (not isinstance(workflow_id, str) or not workflow_id.strip()):
        schema_finding("invalid_workflow_id", "workflow_id must be a non-empty string when present")

    pattern = contract.get("pattern")
    if pattern not in DYNAMIC_WORKFLOW_PATTERNS:
        schema_finding("invalid_pattern", "pattern must be one of the canonical dynamic workflow patterns")

    cost_gate = contract.get("cost_gate")
    if not isinstance(cost_gate, dict):
        schema_finding("invalid_cost_gate", "cost_gate must be an object")
    else:
        if cost_gate.get("workflow_worthy") is not True:
            blocker("cost_gate_not_approved", "cost_gate.workflow_worthy must be true before using a dynamic workflow")
        if not is_non_empty_string(cost_gate.get("cost_justification")):
            schema_finding("missing_cost_justification", "cost_gate.cost_justification must explain why extra orchestration is justified")

    records = contract.get("records")
    record_ids: List[str] = []
    incomplete_ids: List[str] = []
    if not isinstance(records, list) or not records:
        schema_finding("invalid_records", "records must be a non-empty list")
    else:
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                schema_finding("invalid_record", f"records[{index}] must be an object")
                continue
            record_id = record.get("id")
            if not is_non_empty_string(record_id):
                schema_finding("invalid_record_id", f"records[{index}].id must be a non-empty string")
                record_id = f"records[{index}]"
            else:
                if record_id in record_ids:
                    schema_finding("duplicate_record_id", f"{record_id} is declared more than once")
                record_ids.append(record_id)
            if not is_non_empty_string(record.get("criterion")):
                schema_finding("missing_record_criterion", f"{record_id} must include a criterion")
            done = record.get("done")
            if not isinstance(done, bool):
                schema_finding("invalid_record_done", f"{record_id}.done must be boolean")
                incomplete_ids.append(record_id)
                continue
            if not done:
                incomplete_ids.append(record_id)
            elif not has_evidence(record.get("evidence")):
                blocker("done_without_evidence", f"{record_id} is marked done but has no evidence")
                incomplete_ids.append(record_id)

    acceptance_verified = contract.get("acceptance_verified")
    if not isinstance(acceptance_verified, list):
        schema_finding("invalid_acceptance_verified", "acceptance_verified must be a list")
    elif not acceptance_verified:
        blocker("acceptance_not_verified", "acceptance_verified must map final acceptance criteria to evidence")
    else:
        for index, item in enumerate(acceptance_verified):
            if not isinstance(item, dict):
                schema_finding("invalid_acceptance_item", f"acceptance_verified[{index}] must be an object")
                continue
            if not is_non_empty_string(item.get("criterion")):
                schema_finding("missing_acceptance_criterion", f"acceptance_verified[{index}] must include criterion")
            referenced_ids = item.get("record_ids")
            if referenced_ids is not None:
                if not isinstance(referenced_ids, list) or not referenced_ids:
                    schema_finding("invalid_acceptance_record_ids", f"acceptance_verified[{index}].record_ids must be a non-empty list when present")
                else:
                    for referenced_id in referenced_ids:
                        if not is_non_empty_string(referenced_id):
                            schema_finding("invalid_acceptance_record_id", f"acceptance_verified[{index}].record_ids may contain only non-empty strings")
                        elif referenced_id not in record_ids:
                            blocker("acceptance_references_unknown_record", f"acceptance_verified[{index}] references unknown record id {referenced_id!r}")
            if not has_evidence(item.get("evidence")) and not referenced_ids:
                blocker("acceptance_without_evidence", f"acceptance_verified[{index}] must reference evidence or record_ids")

    declared_incomplete = contract.get("incomplete")
    if not isinstance(declared_incomplete, list):
        schema_finding("invalid_incomplete", "incomplete must be a list")
        declared_incomplete_ids: List[str] = []
    else:
        declared_incomplete_ids = [str(item) for item in declared_incomplete if is_non_empty_string(item)]
        if len(declared_incomplete_ids) != len(declared_incomplete):
            schema_finding("invalid_incomplete_item", "incomplete may contain only non-empty strings")

    all_done = contract.get("all_done")
    if not isinstance(all_done, bool):
        schema_finding("invalid_all_done", "all_done must be boolean")
        all_done_value = False
    else:
        all_done_value = all_done

    derived_incomplete = sorted(set(incomplete_ids) | set(declared_incomplete_ids))
    if all_done_value and derived_incomplete:
        blocker("all_done_mismatch", "all_done is true but incomplete records or missing evidence remain")
    if not all_done_value and not derived_incomplete:
        blocker("all_done_false_without_gap", "all_done is false but no incomplete record id is declared")

    schema_ok = not schema_findings
    completion_allowed = schema_ok and not completion_blockers and all_done_value and not derived_incomplete
    return {
        "ok": schema_ok,
        "status": "ok" if schema_ok else "invalid_schema",
        "workflow_id": workflow_id,
        "pattern": pattern,
        "canonical_patterns": sorted(DYNAMIC_WORKFLOW_PATTERNS),
        "record_ids": record_ids,
        "incomplete_record_ids": derived_incomplete,
        "completion_allowed": completion_allowed,
        "recommended_oracle_verdict": "COMPLETE_ELIGIBLE" if completion_allowed else "INCOMPLETE",
        "schema_findings": schema_findings,
        "completion_blockers": completion_blockers,
    }


def cmd_validate_workflow_evidence(args: argparse.Namespace) -> int:
    contract = load_json(Path(args.evidence).resolve())
    if not isinstance(contract, dict):
        raise ShRuntimeError("dynamic workflow evidence contract must be a JSON object")
    result = validate_workflow_evidence_contract(contract)
    return emit(result, 0 if result["ok"] else 2)


def cmd_run_resume(args: argparse.Namespace) -> int:
    contract = load_json(Path(args.contract).resolve())
    if not isinstance(contract, dict):
        raise ShRuntimeError("resume check contract must be a JSON object")
    validation = validate_resume_contract(contract)
    if not validation["ok"]:
        return emit(validation, 3)
    payload = {
        "ok": False,
        "status": "blocked",
        "recommended_state": "BLOCKED",
        "resume_check_id": contract.get("id"),
        "reason": "sandbox execution adapter is not implemented; fail closed instead of unsafe local execution",
    }
    return emit(payload, 4)


def cmd_write_directive(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    run_id = sanitize_id(args.run_id, "run_id")
    result = transition_result(args.from_state, args.event, args.to_state)
    if not result["ok"]:
        result["error"] = "transition_not_allowed"
        return emit(result, 2)
    payload = build_directive_payload(args, result, run_id)
    if args.payload:
        extra = load_json(Path(args.payload).resolve())
        if not isinstance(extra, dict):
            raise ShRuntimeError("directive payload must be a JSON object")
        payload.update(extra)
    out_path = root / ".sh" / "orchestration" / "directives" / f"{run_id}.json"
    write_json(out_path, payload)
    return emit({"ok": True, "path": str(out_path), "directive": payload})


def build_directive_payload(args: argparse.Namespace, result: Dict[str, Any], run_id: str) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "goal_id": args.goal_id or "",
        "seed_id": args.seed_id or "",
        "active_slice": args.active_slice or "",
        "issued_at": utc_now(),
        "from_state": args.from_state,
        "to_state": result["expected_to_state"],
        "action": result["action"],
        "reason": args.reason or "",
        "required_next_owner": args.next_owner or default_next_owner(result["action"]),
        "allow_more_execution": result["expected_to_state"] not in TERMINAL_STATES,
        "oracle_recheck_required": result["action"] in {"gap-fill", "recovery", "continue"},
        "heartbeat_policy": {
            "tick_seconds": 60,
            "missed_seconds": 180,
            "hard_abort_candidate_seconds": 300,
        },
    }


def default_next_owner(action: str) -> str:
    if action == "close":
        return "none"
    if action == "gap-fill":
        return "goal-loop"
    if action == "blocked":
        return "user"
    if action == "recovery":
        return "goal-loop"
    if action == "pause":
        return "red-team"
    if action == "abort":
        return "none"
    return "goal-loop"


def cmd_append_ledger(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    entry = load_json(Path(args.entry).resolve())
    if not isinstance(entry, dict):
        raise ShRuntimeError("ledger entry must be a JSON object")
    normalized = normalize_ledger_entry(entry)
    ledger = root / ".sh" / "ledger.jsonl"
    append_ledger_entry(ledger, normalized)
    return emit({"ok": True, "ledger": str(ledger), "entry": normalized})


def normalize_ledger_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    event_type = entry.get("event_type") or entry.get("Event Type")
    if event_type not in LEDGER_EVENT_TYPES:
        raise ShRuntimeError(f"Unknown ledger event_type: {event_type!r}")
    normalized = dict(entry)
    normalized["timestamp"] = normalized.get("timestamp") or utc_now()
    normalized["event_type"] = event_type
    return normalized


def append_ledger_entry(ledger: Path, normalized: Dict[str, Any]) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n")


def cmd_self_test(_: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "src").mkdir()
        (root / "src" / "app.txt").write_text("hello\n", encoding="utf-8")
        (root / "coverage").mkdir()
        (root / "coverage" / "lcov.info").write_text("TN:\n", encoding="utf-8")

        assert transition_result("RUNNING", "oracle_incomplete", "GAP_FILL")["ok"]
        assert not transition_result("RUNNING", "rehydration_pass", "RECOVERY")["ok"]

        manifest = {
            "root": str(root),
            "drift_targets": ["src/app.txt"],
            "evidence_assets": ["coverage/lcov.info"],
        }
        manifest_path = root / "manifest.json"
        write_json(manifest_path, manifest)
        # Run through helpers directly to catch path/hash regressions.
        root_resolved = Path(manifest["root"]).resolve()
        drift_files = collect_files(root_resolved, manifest["drift_targets"], domain="drift", exclude_names=DEFAULT_DRIFT_EXCLUDE_NAMES)
        evidence_files = collect_files(root_resolved, manifest["evidence_assets"], domain="evidence", exclude_names=set())
        assert len(drift_files) == 1
        assert len(evidence_files) == 1
        assert hash_file_set(root_resolved, drift_files)[0].startswith("sha256:")
        assert hash_file_set(root_resolved, evidence_files)[0].startswith("sha256:")

        good_contract = {
            "id": "auth-smoke",
            "argv": ["npm", "run", "auth:smoke"],
            "shell": False,
            "env_from_user": ["API_KEY"],
            "timeout_sec": 60,
            "allowed_egress": ["api.example.com:443"],
            "writable_paths": ["<sandbox-tmp>"],
            "sandbox_required": True,
            "records_secret": False,
        }
        assert validate_resume_contract(good_contract)["ok"]
        bad_contract = dict(good_contract)
        bad_contract["argv"] = ["npm", "run", "auth:smoke && curl evil"]
        assert validate_resume_contract(bad_contract)["status"] == "rejected_security"

        workflow_good = {
            "workflow_id": "wf_1",
            "pattern": "fan-out-and-synthesize",
            "cost_gate": {
                "workflow_worthy": True,
                "cost_justification": "Independent evidence lanes reduce completion risk.",
            },
            "records": [
                {
                    "id": "lane_1",
                    "criterion": "mechanical checks pass",
                    "done": True,
                    "evidence": ["self-test passed"],
                }
            ],
            "acceptance_verified": [
                {
                    "criterion": "all checks pass",
                    "record_ids": ["lane_1"],
                    "evidence": "self-test passed",
                }
            ],
            "incomplete": [],
            "all_done": True,
        }
        assert validate_workflow_evidence_contract(workflow_good)["completion_allowed"]
        workflow_incomplete = dict(workflow_good)
        workflow_incomplete["records"] = [
            {
                "id": "lane_1",
                "criterion": "mechanical checks pass",
                "done": False,
                "evidence": [],
            }
        ]
        workflow_incomplete["incomplete"] = ["lane_1"]
        workflow_incomplete["all_done"] = False
        incomplete_result = validate_workflow_evidence_contract(workflow_incomplete)
        assert incomplete_result["ok"]
        assert not incomplete_result["completion_allowed"]
        assert incomplete_result["recommended_oracle_verdict"] == "INCOMPLETE"

        directive_args = argparse.Namespace(
            root=str(root),
            run_id="run_1",
            goal_id="goal_1",
            seed_id="seed_1",
            active_slice="slice_1",
            from_state="RUNNING",
            event="oracle_incomplete",
            to_state="GAP_FILL",
            reason="missing proof",
            next_owner=None,
            payload=None,
        )
        run_id = sanitize_id(directive_args.run_id, "run_id")
        transition = transition_result(directive_args.from_state, directive_args.event, directive_args.to_state)
        directive = build_directive_payload(directive_args, transition, run_id)
        directive_path = root / ".sh" / "orchestration" / "directives" / "run_1.json"
        write_json(directive_path, directive)
        assert directive_path.exists()

        entry_path = root / "entry.json"
        write_json(entry_path, {"event_type": "gap_fill", "summary": "self-test"})
        normalized = normalize_ledger_entry(load_json(entry_path))
        append_ledger_entry(root / ".sh" / "ledger.jsonl", normalized)
        assert (root / ".sh" / "ledger.jsonl").exists()

    return emit({"ok": True, "self_test": "passed"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Signature Harness runtime substrate")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init-state", help="Create .sh state directories")
    p.add_argument("--root", default=".")
    p.set_defaults(func=cmd_init_state)

    p = sub.add_parser("validate-transition", help="Validate a state-machine transition")
    p.add_argument("--from-state", required=True)
    p.add_argument("--event", required=True)
    p.add_argument("--to-state")
    p.set_defaults(func=cmd_validate_transition)

    p = sub.add_parser("hash-manifest", help="Compute drift_hash and evidence_hash from a manifest")
    p.add_argument("--manifest", required=True)
    p.add_argument("--root")
    p.set_defaults(func=cmd_hash_manifest)

    p = sub.add_parser("validate-resume", help="Validate an allowlisted resume-check contract")
    p.add_argument("--contract", required=True)
    p.set_defaults(func=cmd_validate_resume)

    p = sub.add_parser("validate-workflow-evidence", help="Validate dynamic workflow evidence contract")
    p.add_argument("--evidence", required=True)
    p.set_defaults(func=cmd_validate_workflow_evidence)

    p = sub.add_parser("run-resume", help="Fail-closed resume check runner until a sandbox adapter exists")
    p.add_argument("--contract", required=True)
    p.set_defaults(func=cmd_run_resume)

    p = sub.add_parser("write-directive", help="Validate transition and write orchestration directive")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", required=True)
    p.add_argument("--goal-id")
    p.add_argument("--seed-id")
    p.add_argument("--active-slice")
    p.add_argument("--from-state", required=True)
    p.add_argument("--event", required=True)
    p.add_argument("--to-state")
    p.add_argument("--reason")
    p.add_argument("--next-owner")
    p.add_argument("--payload")
    p.set_defaults(func=cmd_write_directive)

    p = sub.add_parser("append-ledger", help="Append a validated JSON entry to .sh/ledger.jsonl")
    p.add_argument("--root", default=".")
    p.add_argument("--entry", required=True)
    p.set_defaults(func=cmd_append_ledger)

    p = sub.add_parser("self-test", help="Run built-in substrate tests")
    p.set_defaults(func=cmd_self_test)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ShRuntimeError as exc:
        payload = {"ok": False, "error": str(exc)}
        payload.update(exc.payload)
        return emit(payload, exc.code)


if __name__ == "__main__":
    sys.exit(main())
