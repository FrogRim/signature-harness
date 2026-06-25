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
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from sh_runtime_core import (
    AGENT_NAME,
    AGENT_VERSION,
    ALLOWED_EVIDENCE_SUFFIXES,
    DEFAULT_DRIFT_EXCLUDE_NAMES,
    DYNAMIC_WORKFLOW_PATTERNS,
    EXPECTED_SCHEMA_FILES,
    EXPECTED_TOOL_CONTRACTS,
    FAILURE_CODES,
    LEDGER_EVENT_TYPES,
    PERMISSION_PROFILES,
    RESERVED_DIRECTIVE_KEYS,
    RESERVED_LEDGER_KEYS,
    RUN_ARTIFACT_FILES,
    SAFE_ID_RE,
    SCHEMA_VERSION,
    TERMINAL_STATES,
    WINDOWS_SCRIPT_SHIM_NAMES,
    WINDOWS_SCRIPT_SUFFIXES,
    ShRuntimeError,
    append_jsonl,
    contains_excluded_part,
    contract_sha256,
    default_sh_dirs,
    evidence_strings,
    ensure_state,
    file_sha256,
    has_evidence,
    has_shell_meta,
    is_non_empty_string,
    is_safe_relative_path,
    is_under,
    json_sha256,
    load_json,
    load_json_array,
    load_json_object,
    new_span_id,
    new_trace_id,
    now_epoch_ms,
    read_jsonl,
    rel_posix,
    safe_optional_float,
    safe_optional_int,
    sanitize_id,
    stable_hash_text,
    transition_result,
    utc_now,
    validate_against_schema,
    valid_egress,
    write_json,
)


def emit(payload: Dict[str, Any], code: int = 0) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REMEDIATION_CLEANUP_STATUSES = {"cleanup_complete", "reset_complete"}
REMEDIATION_RESOURCE_CLEAR_STATUSES = {"clear", "none_remaining"}


def cmd_validate_transition(args: argparse.Namespace) -> int:
    payload = transition_result(args.from_state, args.event, args.to_state)
    if not payload["ok"]:
        payload["error"] = "transition_not_allowed"
        return emit(payload, 2)
    return emit(payload)


def run_path(root: Path, run_id: str) -> Path:
    safe_run_id = sanitize_id(run_id, "run_id")
    path = root.resolve() / ".sh" / "runs" / safe_run_id
    runs_root = root.resolve() / ".sh" / "runs"
    if not is_under(path, runs_root):
        raise ShRuntimeError(f"run path escapes .sh/runs: {run_id!r}")
    return path


def run_file(root: Path, run_id: str, key: str) -> Path:
    filename = RUN_ARTIFACT_FILES[key]
    return run_path(root, run_id) / filename


def require_run(root: Path, run_id: str) -> Path:
    path = run_path(root, run_id)
    if not path.exists():
        raise ShRuntimeError(f"run does not exist: {run_id!r}")
    return path


def load_run_manifest(root: Path, run_id: str) -> Dict[str, Any]:
    return load_json_object(run_file(root, run_id, "manifest"), "run manifest")


def load_run_state(root: Path, run_id: str) -> Dict[str, Any]:
    return load_json_object(run_file(root, run_id, "state"), "run state")


def write_run_state(root: Path, run_id: str, state: Dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    write_json(run_file(root, run_id, "state"), state)


def relative_artifact_entry(root: Path, artifact: str) -> Dict[str, Any]:
    path = (root / artifact).resolve()
    if not is_under(path, root):
        raise ShRuntimeError(f"artifact escapes root: {artifact!r}")
    if not path.exists() or not path.is_file():
        raise ShRuntimeError(f"artifact does not exist: {artifact!r}")
    suffix = path.suffix.lower()
    if suffix and suffix not in ALLOWED_EVIDENCE_SUFFIXES:
        raise ShRuntimeError(f"unsupported artifact type: {artifact!r}", payload={"allowed_suffixes": sorted(ALLOWED_EVIDENCE_SUFFIXES)})
    stat = path.stat()
    return {
        "path": rel_posix(path, root),
        "sha256": file_sha256(path),
        "size": stat.st_size,
        "mtime_utc": _dt.datetime.fromtimestamp(stat.st_mtime, _dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "suffix": suffix or "<none>",
    }


def load_artifact_index(root: Path, run_id: str) -> Dict[str, Any]:
    path = run_file(root, run_id, "artifacts")
    if not path.exists():
        return {"run_id": run_id, "artifacts": []}
    return load_json_object(path, "artifact index")


def update_artifact_index(root: Path, run_id: str, artifact_paths: List[str]) -> List[Dict[str, Any]]:
    index = load_artifact_index(root, run_id)
    existing = {entry.get("path"): entry for entry in index.get("artifacts", []) if isinstance(entry, dict)}
    entries: List[Dict[str, Any]] = []
    for artifact in artifact_paths:
        entry = relative_artifact_entry(root, artifact)
        existing[entry["path"]] = entry
        entries.append(entry)
    index["run_id"] = run_id
    index["updated_at"] = utc_now()
    index["artifacts"] = sorted(existing.values(), key=lambda entry: entry["path"])
    write_json(run_file(root, run_id, "artifacts"), index)
    return entries


def default_cost_latency(run_id: str) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "updated_at": utc_now(),
        "step_count": 0,
        "tool_call_count": 0,
        "duration_ms_total": 0,
        "token_usage_input": 0,
        "token_usage_output": 0,
        "estimated_cost": 0.0,
        "tool_error_count": 0,
        "retry_count": 0,
    }


def update_cost_latency(root: Path, run_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    path = run_file(root, run_id, "cost_latency")
    current = load_json_object(path, "cost latency") if path.exists() else default_cost_latency(run_id)
    current["updated_at"] = utc_now()
    current["step_count"] = int(current.get("step_count", 0)) + 1
    if event.get("tool_name"):
        current["tool_call_count"] = int(current.get("tool_call_count", 0)) + 1
    current["duration_ms_total"] = int(current.get("duration_ms_total", 0)) + int(event.get("duration_ms") or 0)
    current["token_usage_input"] = int(current.get("token_usage_input", 0)) + int(event.get("token_usage_input") or 0)
    current["token_usage_output"] = int(current.get("token_usage_output", 0)) + int(event.get("token_usage_output") or 0)
    current["estimated_cost"] = round(float(current.get("estimated_cost", 0.0)) + float(event.get("estimated_cost") or 0.0), 8)
    if event.get("error_type"):
        current["tool_error_count"] = int(current.get("tool_error_count", 0)) + 1
    write_json(path, current)
    return current


def write_handoff(root: Path, run_id: str) -> None:
    manifest = load_run_manifest(root, run_id)
    state = load_run_state(root, run_id)
    cost = load_json_object(run_file(root, run_id, "cost_latency"), "cost latency")
    artifacts = load_artifact_index(root, run_id)
    interruptions = load_json_array(run_file(root, run_id, "interruptions"), "interruptions")
    lines = [
        f"# SH Handoff - {run_id}",
        "",
        f"- goal_id: {manifest.get('goal_id')}",
        f"- seed_id: {manifest.get('seed_id')}",
        f"- active_slice: {manifest.get('active_slice')}",
        f"- current_state: {state.get('current_state')}",
        f"- iteration: {state.get('iteration')}",
        f"- updated_at: {state.get('updated_at')}",
        f"- interruptions: {len(interruptions)}",
        f"- artifacts: {len(artifacts.get('artifacts', []))}",
        f"- duration_ms_total: {cost.get('duration_ms_total')}",
        f"- token_usage_input: {cost.get('token_usage_input')}",
        f"- token_usage_output: {cost.get('token_usage_output')}",
        "",
        "## Resume",
        "",
        f"Run `py scripts/sh_runtime.py resume-run --root . --run-id {run_id} --reason \"resume from handoff\"` after checking unresolved blockers.",
        "",
        "## Artifact Index",
    ]
    for entry in artifacts.get("artifacts", []):
        if isinstance(entry, dict):
            lines.append(f"- {entry.get('path')} {entry.get('sha256')}")
    run_file(root, run_id, "handoff").write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_replay(root: Path, run_id: str) -> Dict[str, Any]:
    manifest = load_run_manifest(root, run_id)
    state = load_run_state(root, run_id)
    trace = read_jsonl(run_file(root, run_id, "trace"))
    step_ledger = read_jsonl(run_file(root, run_id, "step_ledger"))
    replay = {
        "run_id": run_id,
        "trace_id": manifest.get("trace_id"),
        "generated_at": utc_now(),
        "manifest": RUN_ARTIFACT_FILES["manifest"],
        "state": state,
        "steps": [
            {
                "step_id": row.get("step_id"),
                "operation_name": row.get("operation_name"),
                "tool_name": row.get("tool_name"),
                "state_before": row.get("state_before"),
                "state_after": row.get("state_after"),
                "error_type": row.get("error_type"),
                "artifact_hashes": row.get("artifact_hashes", []),
            }
            for row in trace
        ],
        "ledger_events": step_ledger,
    }
    write_json(run_file(root, run_id, "replay"), replay)
    return replay


def cmd_init_state(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    for path in default_sh_dirs(root):
        path.mkdir(parents=True, exist_ok=True)
    ledger = root / ".sh" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.touch(exist_ok=True)
    return emit({"ok": True, "root": str(root), "created": [str(p) for p in default_sh_dirs(root)], "ledger": str(ledger)})


def collect_files(
    root: Path,
    targets: List[str],
    *,
    domain: str,
    exclude_names: Iterable[str],
    missing_entries: Optional[List[Dict[str, Any]]] = None,
) -> List[Path]:
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
            if domain == "drift" and missing_entries is not None:
                missing_entries.append({"path": rel, "status": "missing", "sha256": None, "size": 0})
                continue
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


def hash_file_set(root: Path, files: List[Path], extra_entries: Optional[List[Dict[str, Any]]] = None) -> Tuple[str, List[Dict[str, Any]]]:
    entries = []
    for path in files:
        stat = path.stat()
        entries.append(
            {
                "path": rel_posix(path, root),
                "status": "present",
                "sha256": file_sha256(path),
                "size": stat.st_size,
            }
        )
    if extra_entries:
        entries.extend(extra_entries)
    entries = sorted(entries, key=lambda entry: entry["path"])
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
        cmd = ["git", "-C", str(root), "diff", "--no-ext-diff", "--binary", "HEAD", "--"] + rel_paths
        diff = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if diff.returncode != 0:
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
    return emit(build_hash_manifest(root, manifest))


def build_hash_manifest(root: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
    drift_targets = manifest.get("drift_targets") or []
    evidence_assets = manifest.get("evidence_assets") or []
    if not isinstance(drift_targets, list) or not isinstance(evidence_assets, list):
        raise ShRuntimeError("drift_targets and evidence_assets must be lists")
    exclude_names = set(DEFAULT_DRIFT_EXCLUDE_NAMES)
    exclude_names.update(manifest.get("drift_exclude_names") or [])

    missing_drift_entries: List[Dict[str, Any]] = []
    drift_files = collect_files(root, drift_targets, domain="drift", exclude_names=exclude_names, missing_entries=missing_drift_entries)
    evidence_files = collect_files(root, evidence_assets, domain="evidence", exclude_names=set())
    drift_hash, drift_entries = hash_file_set(root, drift_files, missing_drift_entries)
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
    return payload


def validate_resume_binding(contract: Dict[str, Any], receipt: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    if receipt is None:
        return findings
    receipt_id = receipt.get("resume_check_id")
    contract_id = contract.get("id")
    if receipt_id != contract_id:
        findings.append({"code": "resume_check_id_mismatch", "detail": "receipt resume_check_id does not match contract id"})
    expected_hash = receipt.get("resume_check_contract_sha256") or receipt.get("contract_sha256")
    if not isinstance(expected_hash, str) or not expected_hash.startswith("sha256:"):
        findings.append({"code": "missing_contract_hash", "detail": "receipt must include resume_check_contract_sha256"})
    elif expected_hash != contract_sha256(contract):
        findings.append({"code": "contract_hash_mismatch", "detail": "resume contract hash does not match blocked receipt"})
    return findings


def validate_resume_contract(contract: Dict[str, Any], receipt: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        executable = argv[0].lower()
        executable_name = Path(executable).name
        if executable.endswith(WINDOWS_SCRIPT_SUFFIXES) or executable_name in WINDOWS_SCRIPT_SHIM_NAMES:
            finding("windows_script_executable", "argv[0] must not be a .bat, .cmd, .ps1, or known Windows script shim")
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
    else:
        for egress in allowed_egress:
            if not valid_egress(egress):
                finding("invalid_allowed_egress_item", "allowed_egress entries must be host:port strings with port 1..65535")

    declared_outputs = contract.get("declared_evidence_outputs", [])
    if not isinstance(declared_outputs, list) or not all(isinstance(x, str) and is_safe_relative_path(x) for x in declared_outputs):
        finding("invalid_declared_evidence_outputs", "declared_evidence_outputs must be relative evidence paths when present")
        declared_output_set = set()
    else:
        declared_output_set = set(declared_outputs)

    writable_paths = contract.get("writable_paths", [])
    if not isinstance(writable_paths, list) or not writable_paths or not all(isinstance(x, str) for x in writable_paths):
        finding("invalid_writable_paths", "writable_paths must be a non-empty list of strings")
    else:
        for writable in writable_paths:
            if writable == "<sandbox-tmp>" or writable.startswith("<sandbox-tmp>/"):
                continue
            if writable in declared_output_set:
                continue
            finding("invalid_writable_path_scope", "writable_paths may include only <sandbox-tmp> or declared_evidence_outputs")

    if contract.get("sandbox_required") is not True:
        finding("sandbox_required_missing", "sandbox_required must be true")

    if contract.get("records_secret") is not False:
        finding("records_secret_not_false", "records_secret must be false")

    findings.extend(validate_resume_binding(contract, receipt))

    rejected = bool(findings)
    return {
        "ok": not rejected,
        "status": "ok" if not rejected else "rejected_security",
        "recommended_state": "BLOCKED" if not rejected else "ABORTED",
        "security_findings": findings,
        "resume_check_id": check_id,
        "contract_sha256": contract_sha256(contract),
    }


def cmd_validate_resume(args: argparse.Namespace) -> int:
    contract = load_json(Path(args.contract).resolve())
    if not isinstance(contract, dict):
        raise ShRuntimeError("resume check contract must be a JSON object")
    receipt = None
    if args.receipt:
        receipt = load_json(Path(args.receipt).resolve())
        if not isinstance(receipt, dict):
            raise ShRuntimeError("blocked receipt must be a JSON object")
    result = validate_resume_contract(contract, receipt)
    return emit(result, 0 if result["ok"] else 3)


def evidence_artifact_path(root: Path, value: str) -> Optional[Path]:
    raw = value.removeprefix("file:").strip()
    if not raw:
        return None
    path = (root / raw).resolve()
    if not is_under(path, root) or not path.is_file():
        return None
    return path


def manifest_evidence_entries(manifest: Optional[Dict[str, Any]]) -> Optional[Dict[str, Dict[str, Any]]]:
    if manifest is None:
        return None
    entries = manifest.get("evidence_assets")
    if not isinstance(entries, list):
        entries = manifest.get("evidence_entries")
    if not isinstance(entries, list):
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        if isinstance(entry, dict) and is_non_empty_string(entry.get("path")):
            result[entry["path"].replace("\\", "/")] = entry
    return result


def validate_workflow_artifacts(
    root: Path,
    evidence_values: List[str],
    evidence_manifest: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]], Optional[str]]:
    findings: List[Dict[str, str]] = []
    current_entries: List[Dict[str, Any]] = []
    manifest_entries = manifest_evidence_entries(evidence_manifest)
    seen: Set[str] = set()
    for value in evidence_values:
        artifact = evidence_artifact_path(root, value)
        if artifact is None:
            findings.append({"code": "evidence_artifact_missing", "detail": f"evidence item is not an existing artifact under root: {value!r}"})
            continue
        rel = rel_posix(artifact, root)
        if rel in seen:
            continue
        seen.add(rel)
        suffix = artifact.suffix.lower()
        if suffix and suffix not in ALLOWED_EVIDENCE_SUFFIXES:
            findings.append({"code": "evidence_type_not_allowed", "detail": f"{rel!r} has unsupported evidence type {suffix!r}"})
            continue
        stat = artifact.stat()
        current_entry = {
            "path": rel,
            "status": "present",
            "sha256": file_sha256(artifact),
            "size": stat.st_size,
        }
        current_entries.append(current_entry)
        if manifest_entries is None:
            continue
        manifest_entry = manifest_entries.get(rel)
        if manifest_entry is None:
            findings.append({"code": "evidence_not_in_manifest", "detail": f"evidence artifact is not registered in hash manifest: {rel!r}"})
            continue
        manifest_status = manifest_entry.get("status")
        if manifest_status not in (None, "present"):
            findings.append({"code": "evidence_manifest_status_invalid", "detail": f"{rel!r} has non-present manifest status: {manifest_status!r}"})
            continue
        if manifest_entry.get("sha256") != current_entry["sha256"]:
            findings.append({"code": "evidence_hash_mismatch", "detail": f"{rel!r} content differs from manifest"})
        if manifest_entry.get("size") != current_entry["size"]:
            findings.append({"code": "evidence_size_mismatch", "detail": f"{rel!r} size differs from manifest"})
        generated_at = evidence_manifest.get("generated_at") if isinstance(evidence_manifest, dict) else None
        if isinstance(generated_at, str):
            try:
                manifest_ts = _dt.datetime.fromisoformat(generated_at.replace("Z", "+00:00")).timestamp()
                if stat.st_mtime - manifest_ts > 1.0:
                    findings.append({"code": "evidence_newer_than_manifest", "detail": f"{rel!r} was modified after the evidence manifest was generated"})
            except ValueError:
                findings.append({"code": "invalid_manifest_timestamp", "detail": "evidence manifest generated_at is not ISO-8601"})
    current_entries = sorted(current_entries, key=lambda entry: entry["path"])
    return findings, current_entries, json_sha256(current_entries) if current_entries else None


def validate_workflow_evidence_contract(
    contract: Dict[str, Any],
    *,
    root: Optional[Path] = None,
    require_artifacts: bool = False,
    evidence_manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    schema_findings: List[Dict[str, str]] = []
    completion_blockers: List[Dict[str, str]] = []
    artifact_evidence: List[str] = []
    artifact_evidence_assets: List[Dict[str, Any]] = []
    artifact_evidence_hash: Optional[str] = None

    def schema_finding(code: str, detail: str) -> None:
        schema_findings.append({"code": code, "detail": detail})

    def blocker(code: str, detail: str) -> None:
        completion_blockers.append({"code": code, "detail": detail})

    workflow_id = contract.get("workflow_id")
    if workflow_id is not None and (not isinstance(workflow_id, str) or not workflow_id.strip()):
        schema_finding("invalid_workflow_id", "workflow_id must be a non-empty string when present")
    if require_artifacts:
        for required_field in ("goal_id", "seed_id", "active_slice"):
            if not is_non_empty_string(contract.get(required_field)):
                schema_finding(f"missing_{required_field}", f"{required_field} is required when artifact-backed validation is enabled")

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
            else:
                artifact_evidence.extend(evidence_strings(record.get("evidence")))

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
            artifact_evidence.extend(evidence_strings(item.get("evidence")))

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
    if require_artifacts:
        if root is None:
            schema_finding("missing_root", "root is required when artifact-backed validation is enabled")
        else:
            artifact_findings, artifact_evidence_assets, artifact_evidence_hash = validate_workflow_artifacts(root, artifact_evidence, evidence_manifest)
            completion_blockers.extend(artifact_findings)

    schema_ok = not schema_findings
    completion_allowed = schema_ok and not completion_blockers and all_done_value and not derived_incomplete
    return {
        "ok": schema_ok,
        "status": "ok" if schema_ok else "invalid_schema",
        "workflow_id": workflow_id,
        "pattern": pattern,
        "canonical_patterns": sorted(DYNAMIC_WORKFLOW_PATTERNS),
        "record_ids": record_ids,
        "artifact_evidence_count": len(artifact_evidence),
        "artifact_evidence_assets": artifact_evidence_assets,
        "artifact_evidence_hash": artifact_evidence_hash,
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
    root = Path(args.root).resolve() if args.root else Path(".").resolve()
    evidence_manifest = None
    if args.evidence_manifest:
        evidence_manifest = load_json(Path(args.evidence_manifest).resolve())
        if not isinstance(evidence_manifest, dict):
            raise ShRuntimeError("evidence manifest must be a JSON object")
    result = validate_workflow_evidence_contract(
        contract,
        root=root,
        require_artifacts=args.require_artifacts or not args.allow_descriptive_evidence,
        evidence_manifest=evidence_manifest,
    )
    if not result["ok"]:
        return emit(result, 2)
    if not result["completion_allowed"]:
        return emit(result, 5)
    return emit(result)


def parse_utc_timestamp(value: Any, label: str, findings: List[Dict[str, str]]) -> Optional[_dt.datetime]:
    if not isinstance(value, str) or not value.strip():
        findings.append({"code": f"missing_{label}", "detail": f"{label} must be an ISO-8601 UTC timestamp"})
        return None
    try:
        parsed = _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        findings.append({"code": f"invalid_{label}", "detail": f"{label} must be an ISO-8601 timestamp"})
        return None
    if parsed.tzinfo is None:
        findings.append({"code": f"invalid_{label}", "detail": f"{label} must include a timezone"})
        return None
    return parsed.astimezone(_dt.timezone.utc)


def require_safe_artifact_id(artifact: Dict[str, Any], key: str, findings: List[Dict[str, str]]) -> Optional[str]:
    value = artifact.get(key)
    if not isinstance(value, str) or not SAFE_ID_RE.match(value):
        findings.append({"code": f"invalid_{key}", "detail": f"{key} must be a safe non-empty identifier"})
        return None
    return value


def require_sha256(artifact: Dict[str, Any], key: str, findings: List[Dict[str, str]]) -> Optional[str]:
    value = artifact.get(key)
    if not isinstance(value, str) or not SHA256_RE.match(value):
        findings.append({"code": f"invalid_{key}", "detail": f"{key} must match sha256:<64 lowercase hex chars>"})
        return None
    return value


def validate_sut_tick_hang_artifact(artifact: Dict[str, Any], *, max_retries: int) -> Dict[str, Any]:
    findings: List[Dict[str, str]] = []
    process_id = require_safe_artifact_id(artifact, "process_id", findings)
    tick_id = require_safe_artifact_id(artifact, "tick_id", findings)
    started_at = parse_utc_timestamp(artifact.get("started_at"), "started_at", findings)
    observed_at = parse_utc_timestamp(artifact.get("observed_at"), "observed_at", findings)
    duration_ms = artifact.get("duration_ms")
    if not isinstance(duration_ms, int) or isinstance(duration_ms, bool) or duration_ms <= 0:
        findings.append({"code": "invalid_duration_ms", "detail": "duration_ms must be a positive integer"})
        duration_ms = None
    previous_hash = require_sha256(artifact, "previous_artifact_hash", findings)
    current_hash = require_sha256(artifact, "current_artifact_hash", findings)
    retry_count = artifact.get("retry_count")
    if not isinstance(retry_count, int) or isinstance(retry_count, bool) or retry_count < 0:
        findings.append({"code": "invalid_retry_count", "detail": "retry_count must be a non-negative integer"})
        retry_count = None

    elapsed_ms: Optional[int] = None
    timed_out = False
    if started_at is not None and observed_at is not None and duration_ms is not None:
        elapsed_ms = int((observed_at - started_at).total_seconds() * 1000)
        if elapsed_ms < 0:
            findings.append({"code": "invalid_time_order", "detail": "observed_at must be at or after started_at"})
        else:
            timed_out = elapsed_ms >= duration_ms

    no_progress = previous_hash is not None and current_hash is not None and previous_hash == current_hash
    retry_limit_exceeded = retry_count is not None and retry_count > max_retries
    schema_ok = not findings
    hang_detected = schema_ok and timed_out and no_progress
    status = "invalid_schema"
    recommended_verdict = "CONTINUE"
    recommended_state = "RUNNING"
    recommended_event = None
    failure_code = None
    blockers: List[Dict[str, str]] = []
    if schema_ok:
        if hang_detected:
            status = "retry_limit_exceeded" if retry_limit_exceeded else "hang_detected"
            recommended_verdict = "INCOMPLETE"
            recommended_state = "REMEDIATING"
            recommended_event = "sut_hang_incomplete"
            failure_code = "SUT_HANG_TIMEOUT"
            if retry_limit_exceeded:
                blockers.append({"code": "retry_limit_exceeded", "detail": f"retry_count {retry_count} exceeds max_retries {max_retries}"})
        elif not timed_out:
            status = "not_timed_out"
        else:
            status = "progressing"
    return {
        "ok": schema_ok,
        "kind": "sut_tick_hang",
        "status": status,
        "process_id": process_id,
        "tick_id": tick_id,
        "elapsed_ms": elapsed_ms,
        "duration_ms": duration_ms,
        "timed_out": timed_out,
        "no_progress": no_progress,
        "retry_count": retry_count,
        "max_retries": max_retries,
        "recommended_oracle_verdict": recommended_verdict,
        "recommended_state": recommended_state,
        "recommended_event": recommended_event,
        "failure_code": failure_code,
        "schema_findings": findings,
        "completion_blockers": blockers,
    }


def validate_remediation_evidence_artifact(artifact: Dict[str, Any]) -> Dict[str, Any]:
    findings: List[Dict[str, str]] = []
    blockers: List[Dict[str, str]] = []
    process_id = require_safe_artifact_id(artifact, "process_id", findings)
    tick_id = require_safe_artifact_id(artifact, "tick_id", findings)
    remediation_started_at = parse_utc_timestamp(artifact.get("remediation_started_at"), "remediation_started_at", findings)
    remediation_deadline_at = parse_utc_timestamp(artifact.get("remediation_deadline_at"), "remediation_deadline_at", findings)
    observed_at = parse_utc_timestamp(artifact.get("observed_at"), "observed_at", findings)
    evidence_hash = require_sha256(artifact, "evidence_hash", findings)
    cleanup_status = artifact.get("cleanup_status")
    if cleanup_status not in REMEDIATION_CLEANUP_STATUSES:
        blockers.append({"code": "cleanup_status_incomplete", "detail": "cleanup_status must be cleanup_complete or reset_complete"})
    residual_resource_check = artifact.get("residual_resource_check")
    if residual_resource_check not in REMEDIATION_RESOURCE_CLEAR_STATUSES:
        blockers.append({"code": "residual_resources_not_clear", "detail": "residual_resource_check must be clear or none_remaining"})

    expired = False
    if remediation_started_at is not None and remediation_deadline_at is not None and remediation_deadline_at < remediation_started_at:
        findings.append({"code": "invalid_deadline_order", "detail": "remediation_deadline_at must be at or after remediation_started_at"})
    if observed_at is not None and remediation_deadline_at is not None:
        expired = observed_at >= remediation_deadline_at

    schema_ok = not findings
    if not schema_ok:
        status = "invalid_schema"
        recommended_state = "REMEDIATING"
        recommended_event = None
        failure_code = "CONTRACT_VIOLATION"
        recommended_verdict = "INCOMPLETE"
    elif expired:
        status = "cleanup_timeout"
        recommended_state = "ABORTED"
        recommended_event = "cleanup_timeout"
        failure_code = "REMEDIATION_TIMEOUT"
        recommended_verdict = "INCOMPLETE"
    elif blockers:
        status = "cleanup_evidence_invalid"
        recommended_state = "REMEDIATING"
        recommended_event = "cleanup_evidence_invalid"
        failure_code = "INVALID_EVIDENCE"
        recommended_verdict = "INCOMPLETE"
    else:
        status = "cleanup_evidence_valid"
        recommended_state = "GAP_FILL"
        recommended_event = "cleanup_evidence_valid"
        failure_code = None
        recommended_verdict = "INCOMPLETE"

    return {
        "ok": schema_ok,
        "kind": "remediation_evidence",
        "status": status,
        "process_id": process_id,
        "tick_id": tick_id,
        "cleanup_status": cleanup_status,
        "residual_resource_check": residual_resource_check,
        "evidence_hash": evidence_hash,
        "expired": expired,
        "recommended_oracle_verdict": recommended_verdict,
        "recommended_state": recommended_state,
        "recommended_event": recommended_event,
        "failure_code": failure_code,
        "schema_findings": findings,
        "completion_blockers": blockers,
    }


def validate_completion_artifact(artifact: Dict[str, Any], *, max_retries: int = 0) -> Dict[str, Any]:
    kind = artifact.get("kind")
    if kind == "sut_tick_hang":
        return validate_sut_tick_hang_artifact(artifact, max_retries=max_retries)
    if kind == "remediation_evidence":
        return validate_remediation_evidence_artifact(artifact)
    return {
        "ok": False,
        "kind": kind,
        "status": "invalid_schema",
        "recommended_oracle_verdict": "INCOMPLETE",
        "recommended_state": "REMEDIATING",
        "recommended_event": None,
        "failure_code": "CONTRACT_VIOLATION",
        "schema_findings": [{"code": "invalid_kind", "detail": "kind must be sut_tick_hang or remediation_evidence"}],
        "completion_blockers": [],
    }


def cmd_validate_completion_artifact(args: argparse.Namespace) -> int:
    artifact = load_json(Path(args.artifact).resolve())
    if not isinstance(artifact, dict):
        raise ShRuntimeError("completion artifact must be a JSON object")
    result = validate_completion_artifact(artifact, max_retries=args.max_retries)
    if not result["ok"]:
        return emit(result, 2)
    if result.get("recommended_state") == "ABORTED":
        return emit(result, 6)
    if result.get("status") == "cleanup_evidence_valid":
        return emit(result)
    if result.get("recommended_oracle_verdict") == "INCOMPLETE" and result.get("recommended_state") in {"REMEDIATING", "GAP_FILL"}:
        return emit(result, 5)
    return emit(result)


def cmd_run_resume(args: argparse.Namespace) -> int:
    contract = load_json(Path(args.contract).resolve())
    if not isinstance(contract, dict):
        raise ShRuntimeError("resume check contract must be a JSON object")
    receipt = None
    if args.receipt:
        receipt = load_json(Path(args.receipt).resolve())
        if not isinstance(receipt, dict):
            raise ShRuntimeError("blocked receipt must be a JSON object")
    validation = validate_resume_contract(contract, receipt)
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
        reserved = sorted(set(extra) & RESERVED_DIRECTIVE_KEYS)
        if reserved:
            raise ShRuntimeError("directive payload attempts to override reserved keys", payload={"reserved_keys": reserved})
        payload["extra"] = extra
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
        "oracle_recheck_required": result["action"] in {"gap-fill", "recovery", "continue", "remediate"},
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
    if action == "remediate":
        return "external-runner"
    return "goal-loop"


def create_run(
    root: Path,
    *,
    run_id: str,
    goal_id: str,
    seed_id: str,
    active_slice: str,
    objective: str,
    vertical: str = "completion-auditor",
    permission_profile: str = "read_only",
    reset_existing: bool = False,
) -> Dict[str, Any]:
    sanitize_id(run_id, "run_id")
    if permission_profile not in PERMISSION_PROFILES:
        raise ShRuntimeError(f"Unknown permission profile: {permission_profile!r}")
    path = run_path(root, run_id)
    if path.exists():
        if not reset_existing:
            raise ShRuntimeError(f"run already exists: {run_id!r}")
        runs_root = root.resolve() / ".sh" / "runs"
        if not is_under(path, runs_root):
            raise ShRuntimeError(f"refusing to reset run outside .sh/runs: {path}")
        shutil.rmtree(path)
    for d in default_sh_dirs(root):
        d.mkdir(parents=True, exist_ok=True)
    path.mkdir(parents=True, exist_ok=True)
    trace_id = new_trace_id()
    created_at = utc_now()
    manifest = {
        "run_id": run_id,
        "trace_id": trace_id,
        "goal_id": goal_id,
        "seed_id": seed_id,
        "active_slice": active_slice,
        "objective": objective,
        "vertical": vertical,
        "permission_profile": permission_profile,
        "status": "RUNNING",
        "created_at": created_at,
        "updated_at": created_at,
        "agent_name": AGENT_NAME,
        "agent_version": AGENT_VERSION,
        "resource_spec": {
            "cpu": platform.processor() or platform.machine(),
            "memory": "unknown",
            "time_budget_sec": None,
            "concurrency": 1,
            "network": "offline-by-default",
            "seed": run_id,
            "retries": 0,
        },
    }
    state = {
        "run_id": run_id,
        "trace_id": trace_id,
        "current_state": "RUNNING",
        "iteration": 0,
        "resumed_count": 0,
        "last_step_id": None,
        "last_span_id": None,
        "created_at": created_at,
        "updated_at": created_at,
    }
    write_json(run_file(root, run_id, "manifest"), manifest)
    write_json(run_file(root, run_id, "state"), state)
    write_json(run_file(root, run_id, "interruptions"), [])
    write_json(run_file(root, run_id, "artifacts"), {"run_id": run_id, "updated_at": created_at, "artifacts": []})
    write_json(run_file(root, run_id, "cost_latency"), default_cost_latency(run_id))
    for key in ("step_ledger", "trace", "tool_calls"):
        run_file(root, run_id, key).write_text("", encoding="utf-8")
    start_event = build_trace_event(
        manifest,
        state,
        step_id="run_start",
        operation_name="run.start",
        tool_name="sh_runtime.start-run",
        state_before="RUNNING",
        state_after="RUNNING",
        artifact_entries=[],
        input_text=objective,
        output_text="run initialized",
        duration_ms=0,
    )
    append_trace_event(root, run_id, start_event)
    append_jsonl(run_file(root, run_id, "step_ledger"), {"ts": created_at, "event": "run_started", "state": "RUNNING", "step_id": "run_start"})
    append_ledger_entry(root / ".sh" / "ledger.jsonl", normalize_ledger_entry({"event_type": "goal_created", "run_id": run_id, "goal_id": goal_id, "seed_id": seed_id, "summary": objective}))
    update_replay(root, run_id)
    write_handoff(root, run_id)
    return {"ok": True, "run_id": run_id, "run_dir": str(path), "manifest": manifest}


def build_trace_event(
    manifest: Dict[str, Any],
    state: Dict[str, Any],
    *,
    step_id: str,
    operation_name: str,
    tool_name: Optional[str],
    state_before: str,
    state_after: str,
    artifact_entries: List[Dict[str, Any]],
    input_text: Optional[str] = None,
    output_text: Optional[str] = None,
    duration_ms: int = 0,
    token_usage_input: int = 0,
    token_usage_output: int = 0,
    estimated_cost: float = 0.0,
    error_type: Optional[str] = None,
    approval_needed: bool = False,
    approval_result: Optional[str] = None,
) -> Dict[str, Any]:
    start_ts = utc_now()
    end_ts = start_ts
    span_id = new_span_id()
    artifact_hashes = [entry.get("sha256") for entry in artifact_entries if isinstance(entry.get("sha256"), str)]
    return {
        "event_schema": "sh.trace_event.v1",
        "trace_id": manifest["trace_id"],
        "span_id": span_id,
        "parent_span_id": state.get("last_span_id"),
        "run_id": manifest["run_id"],
        "step_id": step_id,
        "agent_name": manifest.get("agent_name", AGENT_NAME),
        "agent_version": manifest.get("agent_version", AGENT_VERSION),
        "conversation_id": manifest.get("conversation_id"),
        "session_id": manifest.get("session_id"),
        "operation_name": operation_name,
        "tool_name": tool_name,
        "input_hash": stable_hash_text(input_text),
        "args_hash": stable_hash_text(json.dumps({"operation_name": operation_name, "tool_name": tool_name}, sort_keys=True)),
        "output_hash": stable_hash_text(output_text),
        "artifact_hashes": artifact_hashes,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "duration_ms": int(duration_ms),
        "token_usage_input": int(token_usage_input),
        "token_usage_output": int(token_usage_output),
        "estimated_cost": float(estimated_cost),
        "error_type": error_type,
        "state_before": state_before,
        "state_after": state_after,
        "approval_needed": bool(approval_needed),
        "approval_result": approval_result,
        "semconv": {
            "gen_ai.operation.name": operation_name,
            "gen_ai.system": AGENT_NAME,
            "gen_ai.tool.name": tool_name,
        },
    }


def append_trace_event(root: Path, run_id: str, event: Dict[str, Any]) -> None:
    append_jsonl(run_file(root, run_id, "trace"), event)
    if event.get("tool_name"):
        append_jsonl(
            run_file(root, run_id, "tool_calls"),
            {
                "trace_id": event.get("trace_id"),
                "span_id": event.get("span_id"),
                "run_id": run_id,
                "step_id": event.get("step_id"),
                "tool_name": event.get("tool_name"),
                "input_hash": event.get("input_hash"),
                "output_hash": event.get("output_hash"),
                "duration_ms": event.get("duration_ms"),
                "error_type": event.get("error_type"),
                "start_ts": event.get("start_ts"),
                "end_ts": event.get("end_ts"),
            },
        )
    update_cost_latency(root, run_id, event)


def record_step(
    root: Path,
    *,
    run_id: str,
    step_id: str,
    operation_name: str,
    tool_name: Optional[str],
    state_before: str,
    state_after: str,
    artifacts: List[str],
    input_text: Optional[str],
    output_text: Optional[str],
    duration_ms: int,
    token_usage_input: int,
    token_usage_output: int,
    estimated_cost: float,
    error_type: Optional[str],
    approval_needed: bool,
    approval_result: Optional[str],
    event_name: Optional[str] = None,
) -> Dict[str, Any]:
    require_run(root, run_id)
    ensure_state(state_before, "state_before")
    ensure_state(state_after, "state_after")
    state = load_run_state(root, run_id)
    manifest = load_run_manifest(root, run_id)
    if state.get("current_state") != state_before:
        raise ShRuntimeError("state_before does not match current run state", payload={"current_state": state.get("current_state"), "state_before": state_before})
    if state_before != state_after:
        if not event_name:
            raise ShRuntimeError(
                "state-changing record-step requires an explicit state-machine event",
                payload={"state_before": state_before, "state_after": state_after},
            )
        transition = transition_result(state_before, event_name, state_after)
        if not transition["ok"]:
            raise ShRuntimeError(
                "record-step state transition is not allowed",
                payload={"state_before": state_before, "state_after": state_after, "event": event_name, "transition": transition},
            )
    artifact_entries = update_artifact_index(root, run_id, artifacts)
    event = build_trace_event(
        manifest,
        state,
        step_id=step_id,
        operation_name=operation_name,
        tool_name=tool_name,
        state_before=state_before,
        state_after=state_after,
        artifact_entries=artifact_entries,
        input_text=input_text,
        output_text=output_text,
        duration_ms=duration_ms,
        token_usage_input=token_usage_input,
        token_usage_output=token_usage_output,
        estimated_cost=estimated_cost,
        error_type=error_type,
        approval_needed=approval_needed,
        approval_result=approval_result,
    )
    append_trace_event(root, run_id, event)
    append_jsonl(
        run_file(root, run_id, "step_ledger"),
        {
            "ts": utc_now(),
            "event": "step_recorded",
            "step_id": step_id,
            "operation_name": operation_name,
            "tool_name": tool_name,
            "state_before": state_before,
            "state_after": state_after,
            "event_name": event_name,
            "error_type": error_type,
            "artifact_count": len(artifact_entries),
        },
    )
    state["current_state"] = state_after
    state["iteration"] = int(state.get("iteration", 0)) + 1
    state["last_step_id"] = step_id
    state["last_span_id"] = event["span_id"]
    write_run_state(root, run_id, state)
    manifest["status"] = state_after
    manifest["updated_at"] = utc_now()
    write_json(run_file(root, run_id, "manifest"), manifest)
    update_replay(root, run_id)
    write_handoff(root, run_id)
    return {"ok": True, "run_id": run_id, "step_id": step_id, "trace_event": event}


def cmd_start_run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    run_id = args.run_id or ("run_" + uuid.uuid4().hex[:12])
    result = create_run(
        root,
        run_id=run_id,
        goal_id=args.goal_id,
        seed_id=args.seed_id,
        active_slice=args.active_slice,
        objective=args.objective,
        vertical=args.vertical,
        permission_profile=args.permission_profile,
        reset_existing=args.reset_existing,
    )
    return emit(result)


def cmd_record_step(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    result = record_step(
        root,
        run_id=args.run_id,
        step_id=args.step_id,
        operation_name=args.operation_name,
        tool_name=args.tool_name,
        state_before=args.state_before,
        state_after=args.state_after,
        artifacts=args.artifact or [],
        input_text=args.input,
        output_text=args.output,
        duration_ms=safe_optional_int(args.duration_ms),
        token_usage_input=safe_optional_int(args.token_usage_input),
        token_usage_output=safe_optional_int(args.token_usage_output),
        estimated_cost=safe_optional_float(args.estimated_cost),
        error_type=args.error_type,
        approval_needed=args.approval_needed,
        approval_result=args.approval_result,
        event_name=args.event,
    )
    return emit(result)


def interruption_event_for_kind(kind: str) -> str:
    if kind == "blocked":
        return "oracle_blocked"
    if kind == "abort":
        return "critical_risk"
    return "redteam_no_progress"


def cmd_record_interruption(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    require_run(root, args.run_id)
    state = load_run_state(root, args.run_id)
    current_state = state.get("current_state")
    event_name = args.event or interruption_event_for_kind(args.kind)
    transition = transition_result(current_state, event_name)
    if not transition["ok"]:
        transition["error"] = "transition_not_allowed"
        return emit(transition, 2)
    interruptions = load_json_array(run_file(root, args.run_id, "interruptions"), "interruptions")
    interruption = {
        "id": "int_" + uuid.uuid4().hex[:12],
        "kind": args.kind,
        "reason": args.reason,
        "event": event_name,
        "state_before": current_state,
        "state_after": transition["expected_to_state"],
        "timestamp": utc_now(),
        "approval_needed": args.approval_needed,
    }
    interruptions.append(interruption)
    write_json(run_file(root, args.run_id, "interruptions"), interruptions)
    record_step(
        root,
        run_id=args.run_id,
        step_id=interruption["id"],
        operation_name="run.interruption",
        tool_name="sh_runtime.record-interruption",
        state_before=current_state,
        state_after=transition["expected_to_state"],
        artifacts=[],
        input_text=args.reason,
        output_text=args.kind,
        duration_ms=0,
        token_usage_input=0,
        token_usage_output=0,
        estimated_cost=0.0,
        error_type=None,
        approval_needed=args.approval_needed,
        approval_result=None,
        event_name=event_name,
    )
    return emit({"ok": True, "run_id": args.run_id, "interruption": interruption})


def default_resume_event(current_state: str) -> str:
    if current_state == "BLOCKED":
        return "rehydration_pass"
    if current_state == "PAUSED":
        return "unstuck_accepted"
    if current_state == "RECOVERY":
        return "recovery_validated"
    return "seed_update_accepted"


def cmd_resume_run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    require_run(root, args.run_id)
    state = load_run_state(root, args.run_id)
    current_state = state.get("current_state")
    if current_state in TERMINAL_STATES:
        raise ShRuntimeError("terminal run cannot be resumed", payload={"current_state": current_state})
    event_name = args.event or default_resume_event(current_state)
    if current_state == "RUNNING":
        next_state = "RUNNING"
        transition = {"ok": True, "expected_to_state": "RUNNING", "event": "already_running"}
    else:
        transition = transition_result(current_state, event_name)
        if not transition["ok"]:
            transition["error"] = "transition_not_allowed"
            return emit(transition, 2)
        next_state = transition["expected_to_state"]
    state["resumed_count"] = int(state.get("resumed_count", 0)) + 1
    write_run_state(root, args.run_id, state)
    result = record_step(
        root,
        run_id=args.run_id,
        step_id="resume_" + uuid.uuid4().hex[:8],
        operation_name="run.resume",
        tool_name="sh_runtime.resume-run",
        state_before=current_state,
        state_after=next_state,
        artifacts=[],
        input_text=args.reason,
        output_text=event_name,
        duration_ms=0,
        token_usage_input=0,
        token_usage_output=0,
        estimated_cost=0.0,
        error_type=None,
        approval_needed=False,
        approval_result=None,
        event_name=event_name if current_state != "RUNNING" else None,
    )
    append_ledger_entry(root / ".sh" / "ledger.jsonl", normalize_ledger_entry({"event_type": "recovery", "run_id": args.run_id, "summary": args.reason or "resume", "from_state": current_state, "to_state": next_state}))
    return emit({"ok": True, "run_id": args.run_id, "transition": transition, "trace_event": result["trace_event"]})


def cmd_replay_run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    require_run(root, args.run_id)
    replay = update_replay(root, args.run_id) if args.refresh else load_json_object(run_file(root, args.run_id, "replay"), "replay")
    trace = read_jsonl(run_file(root, args.run_id, "trace"))
    tool_calls = read_jsonl(run_file(root, args.run_id, "tool_calls"))
    cost = load_json_object(run_file(root, args.run_id, "cost_latency"), "cost latency")
    summary = {
        "ok": True,
        "run_id": args.run_id,
        "trace_id": replay.get("trace_id"),
        "state": replay.get("state", {}).get("current_state"),
        "step_count": len(trace),
        "tool_call_count": len(tool_calls),
        "duration_ms_total": cost.get("duration_ms_total", 0),
        "estimated_cost": cost.get("estimated_cost", 0.0),
        "error_count": len([row for row in trace if row.get("error_type")]),
        "steps": replay.get("steps", []),
    }
    return emit(summary)


def validate_json_schema_files(root: Path) -> Dict[str, Any]:
    schema_dir = root / "schemas"
    findings: List[Dict[str, str]] = []
    if not schema_dir.exists():
        findings.append({"code": "missing_schema_dir", "detail": "schemas/ does not exist"})
        return {"ok": False, "findings": findings}
    for filename in sorted(EXPECTED_SCHEMA_FILES):
        path = schema_dir / filename
        if not path.exists():
            findings.append({"code": "missing_schema_file", "detail": filename})
            continue
        payload = load_json(path)
        if not isinstance(payload, dict):
            findings.append({"code": "schema_not_object", "detail": filename})
            continue
        if filename.endswith(".schema.json") and payload.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            findings.append({"code": "invalid_schema_dialect", "detail": filename})
    tool_contracts_path = schema_dir / "tool_contracts.json"
    if tool_contracts_path.exists():
        tool_contracts_schema = load_json_object(schema_dir / "tool_contracts.schema.json", "tool contracts schema")
        contracts = load_json_object(tool_contracts_path, "tool contracts")
        findings.extend(validate_against_schema(contracts, tool_contracts_schema, "$.tool_contracts"))
        tools = contracts.get("tools")
        if not isinstance(tools, list):
            findings.append({"code": "invalid_tool_contracts", "detail": "tools must be a list"})
        else:
            names = {tool.get("name") for tool in tools if isinstance(tool, dict)}
            missing = sorted(EXPECTED_TOOL_CONTRACTS - names)
            if missing:
                findings.append({"code": "missing_tool_contracts", "detail": ",".join(missing)})
            for tool in tools:
                if not isinstance(tool, dict):
                    findings.append({"code": "invalid_tool_contract", "detail": "tool entry must be object"})
                    continue
                for key in ("name", "description", "inputSchema", "outputSchema", "exit_codes", "retryability", "timeout_sec", "side_effect_class", "approval_required", "emitted_artifacts", "failure_modes"):
                    if key not in tool:
                        findings.append({"code": "tool_contract_missing_key", "detail": f"{tool.get('name', '<unknown>')} missing {key}"})
    taxonomy_path = schema_dir / "failure_taxonomy.json"
    if taxonomy_path.exists():
        taxonomy_schema = load_json_object(schema_dir / "failure_taxonomy.schema.json", "failure taxonomy schema")
        taxonomy = load_json_object(taxonomy_path, "failure taxonomy")
        findings.extend(validate_against_schema(taxonomy, taxonomy_schema, "$.failure_taxonomy"))
        failure_types = taxonomy.get("failure_types")
        if not isinstance(failure_types, list):
            findings.append({"code": "invalid_failure_taxonomy", "detail": "failure_types must be a list"})
        else:
            codes = set()
            for item in failure_types:
                if not isinstance(item, dict):
                    findings.append({"code": "invalid_failure_type", "detail": "failure type must be object"})
                    continue
                for key in ("code", "severity", "retriable", "recovery_action", "owner", "evidence_required", "user_visible_message"):
                    if key not in item:
                        findings.append({"code": "failure_type_missing_key", "detail": f"{item.get('code', '<unknown>')} missing {key}"})
                codes.add(item.get("code"))
            missing_codes = sorted(FAILURE_CODES - codes)
            if missing_codes:
                findings.append({"code": "missing_failure_codes", "detail": ",".join(missing_codes)})
    policy_path = root / "security" / "policy.json"
    policy_schema_path = schema_dir / "security_policy.schema.json"
    if policy_path.exists() and policy_schema_path.exists():
        policy_schema = load_json_object(policy_schema_path, "security policy schema")
        policy = load_json_object(policy_path, "security policy")
        findings.extend(validate_against_schema(policy, policy_schema, "$.security_policy"))
    return {"ok": not findings, "findings": findings}


def validate_eval_task(task: Dict[str, Any], index: int, root: Optional[Path] = None, schema: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    if schema is not None:
        findings.extend(validate_against_schema(task, schema, f"$.eval_task[{index}]"))
    for key in ("id", "title", "vertical", "input", "expected_artifacts", "grader_config", "resource_spec", "trial_count", "seed_policy"):
        if key not in task:
            findings.append({"code": "eval_task_missing_key", "detail": f"task[{index}] missing {key}"})
    if "trial_count" in task and (not isinstance(task.get("trial_count"), int) or int(task.get("trial_count")) < 1):
        findings.append({"code": "invalid_trial_count", "detail": f"task[{index}].trial_count must be >=1"})
    if task.get("vertical") != "AI coding-agent completion auditor":
        findings.append({"code": "invalid_vertical", "detail": f"task[{index}] is outside the selected vertical"})
    expected_artifacts = task.get("expected_artifacts")
    if not isinstance(expected_artifacts, list) or not expected_artifacts:
        findings.append({"code": "invalid_expected_artifacts", "detail": f"task[{index}].expected_artifacts must be a non-empty list"})
    elif root is not None:
        for artifact in expected_artifacts:
            if not is_non_empty_string(artifact):
                findings.append({"code": "invalid_expected_artifact", "detail": f"task[{index}] expected_artifacts may contain only non-empty strings"})
                continue
            path = (root / artifact).resolve()
            if not is_under(path, root) or not path.is_file():
                findings.append({"code": "expected_artifact_missing", "detail": f"task[{index}] expected artifact is missing: {artifact!r}"})
    return findings


def validate_eval_files(root: Path) -> Dict[str, Any]:
    findings: List[Dict[str, str]] = []
    task_count = 0
    eval_schema = load_json_object(root / "schemas" / "eval_task.schema.json", "eval task schema")
    for rel in ("evals/benchmark_tasks.jsonl", "evals/regression_tasks.jsonl"):
        path = root / rel
        if not path.exists():
            findings.append({"code": "missing_eval_suite", "detail": rel})
            continue
        rows = read_jsonl(path)
        if rel.endswith("benchmark_tasks.jsonl"):
            task_count = len(rows)
            if len(rows) < 20:
                findings.append({"code": "benchmark_task_count_low", "detail": f"expected at least 20 tasks, got {len(rows)}"})
        for index, task in enumerate(rows):
            findings.extend(validate_eval_task(task, index, root=root, schema=eval_schema))
    return {"ok": not findings, "benchmark_task_count": task_count, "findings": findings}


MANIFEST_IDENTITY_FILES = (
    "plugin.json",
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".codex-plugin/marketplace.json",
)


def validate_manifest_consistency(root: Path) -> Dict[str, Any]:
    """Guard the cross-manifest invariants.

    Only ``name`` and ``version`` must stay in lockstep across every plugin and
    marketplace manifest (including nested ``plugins[]`` entries). Presentation
    fields such as description, category, and the interface block are
    intentionally allowed to differ per host, so they are not checked here. A
    missing manifest is skipped rather than flagged, so the file set can be
    pruned later without tripping the guard, but the canonical Claude Code
    manifest must exist.
    """
    findings: List[Dict[str, str]] = []
    names: Dict[str, Any] = {}
    versions: Dict[str, Any] = {}
    checked: List[str] = []

    def record(label: str, obj: Any) -> None:
        if not isinstance(obj, dict):
            return
        if "name" in obj:
            names[label] = obj.get("name")
        if "version" in obj:
            versions[label] = obj.get("version")

    for rel in MANIFEST_IDENTITY_FILES:
        path = root / rel
        if not path.exists():
            continue
        checked.append(rel)
        try:
            payload = load_json(path)
        except ShRuntimeError:
            findings.append({"code": "manifest_unreadable", "detail": rel})
            continue
        if not isinstance(payload, dict):
            findings.append({"code": "manifest_not_object", "detail": rel})
            continue
        record(rel, payload)
        plugins = payload.get("plugins")
        if isinstance(plugins, list):
            for index, plugin in enumerate(plugins):
                record(f"{rel}#plugins[{index}]", plugin)

    if not (root / ".claude-plugin" / "plugin.json").exists():
        findings.append({"code": "missing_canonical_manifest", "detail": ".claude-plugin/plugin.json"})

    distinct_names = {value for value in names.values()}
    distinct_versions = {value for value in versions.values()}
    if len(distinct_names) > 1:
        findings.append({
            "code": "manifest_name_mismatch",
            "detail": "; ".join(f"{label}={names[label]!r}" for label in sorted(names)),
        })
    if len(distinct_versions) > 1:
        findings.append({
            "code": "manifest_version_mismatch",
            "detail": "; ".join(f"{label}={versions[label]!r}" for label in sorted(versions)),
        })

    return {
        "ok": not findings,
        "findings": findings,
        "files_checked": checked,
        "name": next(iter(distinct_names)) if len(distinct_names) == 1 else None,
        "version": next(iter(distinct_versions)) if len(distinct_versions) == 1 else None,
    }


def build_version_surface(root: Path, manifest_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    manifest_result = manifest_result or validate_manifest_consistency(root)
    plugin_version = manifest_result.get("version")
    canonical_manifest = root / ".claude-plugin" / "plugin.json"
    if not is_non_empty_string(plugin_version) and canonical_manifest.exists():
        try:
            payload = load_json_object(canonical_manifest, "canonical plugin manifest")
            plugin_version = payload.get("version")
        except ShRuntimeError:
            plugin_version = None
    return {
        "plugin_version": plugin_version,
        "plugin_version_source": ".claude-plugin/plugin.json via manifest identity guard",
        "runtime_agent_name": AGENT_NAME,
        "runtime_version": AGENT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "schema_files_checked": sorted(EXPECTED_SCHEMA_FILES),
        "manifest_files_checked": list(manifest_result.get("files_checked", [])),
    }


def cmd_validate_schemas(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    schema_result = validate_json_schema_files(root)
    eval_result = validate_eval_files(root)
    manifest_result = validate_manifest_consistency(root)
    policy_path = root / "security" / "policy.json"
    policy_ok = policy_path.exists() and isinstance(load_json(policy_path), dict)
    result = {
        "ok": schema_result["ok"] and eval_result["ok"] and manifest_result["ok"] and policy_ok,
        "schemas": schema_result,
        "evals": eval_result,
        "manifests": manifest_result,
        "security_policy_present": policy_ok,
        "versions": build_version_surface(root, manifest_result),
    }
    return emit(result, 0 if result["ok"] else 2)


RELEASE_FORBIDDEN_PHRASES = (
    "production-grade",
    "100%",
    "auto-commit",
    "auto commit",
    "every-step-E2E",
    "every meaningful step",
)

RELEASE_SCAN_PATTERNS = (
    "README.md",
    "AGENTS.md",
    "skills/**/*.md",
    "templates/**/*.md",
)

RELEASE_REQUIRED_ANCHORS = (
    ("README.md", "## Thin Contract Patch"),
    ("AGENTS.md", "acceptance_criteria"),
    ("AGENTS.md", "verification_tier"),
    ("skills/seed-crystallizer/SKILL.md", "acceptance_criteria:"),
    ("skills/seed-crystallizer/SKILL.md", "verification_tier: low | medium | high | release"),
    ("skills/oracle-verification/SKILL.md", "## Measured Completion Gate"),
    ("skills/parallel-hypothesis/SKILL.md", "Parallel fan-out is default-deny"),
    ("templates/SEED.md", "## Verification Tier"),
    ("templates/ORACLE.md", "## Measured Completion Gate"),
    ("templates/DYNAMIC_WORKFLOW.md", "Parallel fan-out is default-deny"),
)


def release_scan_files(root: Path) -> List[Path]:
    files: Dict[str, Path] = {}
    for pattern in RELEASE_SCAN_PATTERNS:
        for path in root.glob(pattern):
            if path.is_file():
                files[rel_posix(path.resolve(), root)] = path.resolve()
    return [files[key] for key in sorted(files)]


def validate_release_static_contracts(root: Path) -> Dict[str, Any]:
    findings: List[Dict[str, str]] = []
    anchors_checked: List[Dict[str, str]] = []
    for rel, needle in RELEASE_REQUIRED_ANCHORS:
        path = root / rel
        anchors_checked.append({"path": rel, "contains": needle})
        if not path.exists() or not path.is_file():
            findings.append({"code": "release_anchor_file_missing", "detail": rel})
            continue
        text = path.read_text(encoding="utf-8-sig")
        if needle not in text:
            findings.append({"code": "release_anchor_missing", "detail": f"{rel} missing {needle!r}"})

    scanned_files = release_scan_files(root)
    for path in scanned_files:
        rel = rel_posix(path, root)
        text = path.read_text(encoding="utf-8-sig")
        text_lower = text.lower()
        for phrase in RELEASE_FORBIDDEN_PHRASES:
            haystack = text if phrase == "100%" else text_lower
            needle = phrase if phrase == "100%" else phrase.lower()
            if needle in haystack:
                findings.append({"code": "release_forbidden_phrase", "detail": f"{rel} contains {phrase!r}"})

    return {
        "ok": not findings,
        "findings": findings,
        "anchors_checked": anchors_checked,
        "forbidden_phrases": list(RELEASE_FORBIDDEN_PHRASES),
        "files_scanned": [rel_posix(path, root) for path in scanned_files],
    }


def cmd_validate_release(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    schema_result = validate_json_schema_files(root)
    eval_result = validate_eval_files(root)
    manifest_result = validate_manifest_consistency(root)
    policy_path = root / "security" / "policy.json"
    policy_ok = policy_path.exists() and isinstance(load_json(policy_path), dict)
    static_result = validate_release_static_contracts(root)
    version_surface = build_version_surface(root, manifest_result)
    version_ok = all(
        is_non_empty_string(version_surface.get(key))
        for key in ("plugin_version", "runtime_version", "schema_version")
    )
    result = {
        "ok": schema_result["ok"] and eval_result["ok"] and manifest_result["ok"] and policy_ok and static_result["ok"] and version_ok,
        "release_gate_schema": "sh.release_gate.v1",
        "generated_at": utc_now(),
        "schemas": schema_result,
        "evals": eval_result,
        "manifests": manifest_result,
        "security_policy_present": policy_ok,
        "static_contracts": static_result,
        "versions": version_surface,
        "version_surface_ok": version_ok,
        "recommended_verification": [
            "py -3 -m py_compile scripts/sh_runtime.py scripts/sh_runtime_core.py",
            "py -3 scripts/sh_runtime.py self-test",
            "py -3 scripts/sh_runtime.py validate-schemas --root .",
            "py -3 scripts/sh_runtime.py run-evals --root . --suite evals/benchmark_tasks.jsonl --trials 3 --eval-run-id release-benchmark --reset-existing",
            "py -3 scripts/sh_runtime.py run-evals --root . --suite evals/regression_tasks.jsonl --trials 3 --eval-run-id release-regression --reset-existing",
        ],
    }
    substrate_ok = schema_result["ok"] and eval_result["ok"] and manifest_result["ok"]
    if result["ok"]:
        return emit(result, 0)
    return emit(result, 2 if not substrate_ok else 9)


def validate_policy_action(root: Path, policy: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
    findings: List[Dict[str, str]] = []
    profile_name = action.get("permission_profile")
    profiles = policy.get("profiles", {})
    profile = profiles.get(profile_name) if isinstance(profiles, dict) else None
    if profile_name not in PERMISSION_PROFILES or not isinstance(profile, dict):
        findings.append({"code": "PERMISSION_DENIED", "detail": f"unknown permission profile {profile_name!r}"})
        profile = {}
    approval = action.get("approval", {}) if isinstance(action.get("approval"), dict) else {}
    approval_required = False
    fs = action.get("filesystem", {}) if isinstance(action.get("filesystem"), dict) else {}
    writes = fs.get("writes", [])
    if writes and profile_name == "read_only":
        approval_required = True
        findings.append({"code": "PERMISSION_DENIED", "detail": "read_only profile cannot write"})
    profile_fs = profile.get("filesystem", {}) if isinstance(profile.get("filesystem"), dict) else {}
    allowed_write_roots = profile_fs.get("write", [])
    for raw in writes if isinstance(writes, list) else []:
        p = (root / str(raw)).resolve()
        if not is_under(p, root):
            approval_required = True
            findings.append({"code": "UNSAFE_ACTION", "detail": f"write escapes workspace: {raw}"})
            continue
        if profile_name != "danger_full_access":
            allowed = False
            for allowed_raw in allowed_write_roots if isinstance(allowed_write_roots, list) else []:
                allowed_path = (root / str(allowed_raw)).resolve()
                if is_under(p, allowed_path):
                    allowed = True
                    break
            if not allowed:
                approval_required = True
                findings.append({"code": "PERMISSION_DENIED", "detail": f"write is outside profile allowlist: {raw}"})
    if fs.get("destructive") is True:
        approval_required = True
        findings.append({"code": "UNSAFE_ACTION", "detail": "destructive action requires approval"})
    network = action.get("network", {}) if isinstance(action.get("network"), dict) else {}
    domains = network.get("domains", [])
    allowed_domains = set(profile.get("network_allowlist", []))
    if domains:
        if profile_name not in {"scoped_network", "danger_full_access"}:
            approval_required = True
            findings.append({"code": "PERMISSION_DENIED", "detail": f"{profile_name} profile cannot use network"})
        for domain in domains if isinstance(domains, list) else []:
            if profile_name == "scoped_network" and domain not in allowed_domains:
                approval_required = True
                findings.append({"code": "PERMISSION_DENIED", "detail": f"network domain not allowlisted: {domain}"})
    command = action.get("command", {}) if isinstance(action.get("command"), dict) else {}
    argv = command.get("argv", [])
    if command.get("shell") is True:
        approval_required = True
        findings.append({"code": "UNSAFE_ACTION", "detail": "shell=true requires approval"})
    for item in argv if isinstance(argv, list) else []:
        meta = has_shell_meta(str(item))
        if meta:
            approval_required = True
            findings.append({"code": "UNSAFE_ACTION", "detail": f"shell metacharacter {meta!r} requires approval"})
    approval_result = approval.get("result")
    approval_satisfied = approval_required and approval_result == "approved"
    ok = not findings or approval_satisfied
    return {
        "ok": ok,
        "approval_required": approval_required,
        "approval_result": approval_result,
        "failure_findings": findings if not approval_satisfied else [],
        "raw_findings": findings,
        "recommended_state": "RUNNING" if ok else "BLOCKED",
    }


def cmd_validate_policy(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    policy = load_json_object(Path(args.policy).resolve(), "security policy")
    action = load_json_object(Path(args.action_file).resolve(), "policy action")
    result = validate_policy_action(root, policy, action)
    if args.write_approval_log:
        approval_dir = root / ".sh" / "approvals"
        approval_dir.mkdir(parents=True, exist_ok=True)
        approval_id = action.get("approval", {}).get("id") if isinstance(action.get("approval"), dict) else None
        approval_id = approval_id if is_non_empty_string(approval_id) and SAFE_ID_RE.match(approval_id) else "approval_" + uuid.uuid4().hex[:12]
        write_json(
            approval_dir / f"{approval_id}.json",
            {
                "request": action,
                "reviewer": action.get("approval", {}).get("reviewer") if isinstance(action.get("approval"), dict) else None,
                "result": result,
                "timestamp": utc_now(),
                "reason": action.get("approval", {}).get("reason") if isinstance(action.get("approval"), dict) else None,
            },
        )
        result["approval_log"] = str(approval_dir / f"{approval_id}.json")
    return emit(result, 0 if result["ok"] else 7)


def eval_validator_result(root: Path, task: Dict[str, Any]) -> Dict[str, Any]:
    fixture = task.get("fixture", {}) if isinstance(task.get("fixture"), dict) else {}
    validator = fixture.get("validator") if isinstance(fixture.get("validator"), dict) else None
    if validator is None:
        return {"ok": True, "type": "none"}
    validator_type = validator.get("type")
    if validator_type == "workflow_evidence":
        evidence_path = (root / str(validator.get("path", ""))).resolve()
        contract = load_json_object(evidence_path, "workflow evidence fixture")
        manifest = None
        if is_non_empty_string(validator.get("evidence_manifest")):
            manifest = load_json_object((root / str(validator["evidence_manifest"])).resolve(), "evidence manifest fixture")
        result = validate_workflow_evidence_contract(
            contract,
            root=root,
            require_artifacts=validator.get("require_artifacts", True) is not False,
            evidence_manifest=manifest,
        )
        expected = validator.get("expected_completion_allowed")
        return {
            "ok": expected is None or bool(result["completion_allowed"]) == bool(expected),
            "type": validator_type,
            "result": result,
        }
    if validator_type == "policy":
        policy = load_json_object(root / "security" / "policy.json", "security policy")
        action = load_json_object((root / str(validator.get("path", ""))).resolve(), "policy action fixture")
        result = validate_policy_action(root, policy, action)
        expected = validator.get("expected_ok")
        return {"ok": expected is None or bool(result["ok"]) == bool(expected), "type": validator_type, "result": result}
    if validator_type == "resume_contract":
        contract = load_json_object((root / str(validator.get("path", ""))).resolve(), "resume contract fixture")
        result = validate_resume_contract(contract)
        expected = validator.get("expected_ok")
        expected_status = validator.get("expected_status")
        ok = expected is None or bool(result["ok"]) == bool(expected)
        if expected_status is not None:
            ok = ok and result.get("status") == expected_status
        return {"ok": ok, "type": validator_type, "result": result}
    if validator_type == "completion_artifact":
        artifact = load_json_object((root / str(validator.get("path", ""))).resolve(), "completion artifact fixture")
        result = validate_completion_artifact(artifact, max_retries=int(validator.get("max_retries", 0)))
        ok = True
        for expected_key, result_key in (
            ("expected_ok", "ok"),
            ("expected_status", "status"),
            ("expected_recommended_state", "recommended_state"),
            ("expected_recommended_event", "recommended_event"),
            ("expected_oracle_verdict", "recommended_oracle_verdict"),
            ("expected_failure_code", "failure_code"),
        ):
            if expected_key in validator:
                ok = ok and result.get(result_key) == validator[expected_key]
        return {"ok": ok, "type": validator_type, "result": result}
    return {"ok": False, "type": validator_type, "error": "unknown eval validator type"}


def grade_eval_task(root: Path, task: Dict[str, Any], trial_index: int) -> Dict[str, Any]:
    fixture = task.get("fixture", {}) if isinstance(task.get("fixture"), dict) else {}
    grader = task.get("grader_config", {}) if isinstance(task.get("grader_config"), dict) else {}
    outcome = grader.get("outcome_grader", {}) if isinstance(grader.get("outcome_grader"), dict) else {}
    behavior = grader.get("transcript_behavior_grader", {}) if isinstance(grader.get("transcript_behavior_grader"), dict) else {}
    observed_outcome = fixture.get("observed_outcome")
    required_detection = behavior.get("must_detect")
    signals = set(fixture.get("signals", [])) if isinstance(fixture.get("signals"), list) else set()
    outcome_pass = observed_outcome == outcome.get("expected_outcome")
    behavior_pass = required_detection is None or required_detection in signals
    validator = eval_validator_result(root, task)
    return {
        "task_id": task.get("id"),
        "trial_index": trial_index,
        "passed": bool(outcome_pass and behavior_pass and validator["ok"]),
        "outcome_pass": bool(outcome_pass),
        "behavior_pass": bool(behavior_pass),
        "validator_pass": bool(validator["ok"]),
        "validator_type": validator.get("type"),
        "signals": sorted(str(signal) for signal in signals),
        "failure_code": fixture.get("failure_code"),
        "duration_ms": int(fixture.get("duration_ms", 100)),
        "estimated_cost": float(fixture.get("estimated_cost", 0.0)),
        "retries": int(fixture.get("retries", 0)),
        "tool_errors": int(fixture.get("tool_errors", 0)),
    }


def count_values(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        value = row.get(key)
        label = "NONE" if value is None else str(value)
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def score_metric(
    rows: List[Dict[str, Any]],
    *,
    signals: Optional[Set[str]] = None,
    failure_codes: Optional[Set[str]] = None,
    validator_types: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    selected: List[Dict[str, Any]] = []
    for row in rows:
        row_signals = set(row.get("signals", [])) if isinstance(row.get("signals"), list) else set()
        matched = False
        if signals and row_signals.intersection(signals):
            matched = True
        if failure_codes and row.get("failure_code") in failure_codes:
            matched = True
        if validator_types and row.get("validator_type") in validator_types:
            matched = True
        if matched:
            selected.append(row)
    passed = len([row for row in selected if row.get("passed")])
    return {
        "total_trials": len(selected),
        "passed": passed,
        "rate": round(passed / len(selected), 4) if selected else None,
    }


def build_eval_scorecard(eval_result: Dict[str, Any]) -> Dict[str, Any]:
    rows = [row for row in eval_result.get("trial_results", []) if isinstance(row, dict)]
    return {
        "schema": "sh.scorecard.v1",
        "eval_run_id": eval_result.get("eval_run_id"),
        "suite": eval_result.get("suite"),
        "generated_at": utc_now(),
        "task_count": eval_result.get("task_count"),
        "trial_count": eval_result.get("trial_count"),
        "passed": eval_result.get("passed"),
        "failed": eval_result.get("failed"),
        "pass_rate": eval_result.get("pass_rate"),
        "completion_auditor_metrics": {
            "false_completion_detection_rate": score_metric(
                rows,
                signals={"false_completion", "failed_test"},
                failure_codes={"FAILED_TEST"},
            ),
            "evidence_gap_detection_rate": score_metric(
                rows,
                signals={"evidence_less_completion", "hallucinated_evidence", "artifact_mismatch", "missing_proof", "stale_manifest", "require_artifacts_default", "invalid_evidence"},
                failure_codes={"INVALID_EVIDENCE", "ARTIFACT_MISMATCH"},
            ),
            "unsafe_resume_block_rate": score_metric(
                rows,
                signals={"unsafe_resume", "security_violation"},
                failure_codes={"UNSAFE_RESUME"},
            ),
            "no_progress_detection_rate": score_metric(
                rows,
                signals={"no_progress_loop", "repeated_tool_failure"},
                failure_codes={"NO_PROGRESS", "REPEATED_TOOL_FAILURE"},
            ),
            "permission_block_rate": score_metric(
                rows,
                signals={"permission_denied", "read_only_write", "network_allowlist", "destructive_action"},
                failure_codes={"PERMISSION_DENIED", "BLOCKED_APPROVAL", "UNSAFE_ACTION"},
            ),
            "gap_fill_routing_rate": score_metric(
                rows,
                signals={"gap_fill", "missing_proof", "oracle_incomplete"},
            ),
            "hang_detection_rate": score_metric(
                rows,
                signals={"sut_hang_timeout", "progressing_tick"},
                failure_codes={"SUT_HANG_TIMEOUT"},
            ),
            "remediation_gate_rate": score_metric(
                rows,
                signals={"cleanup_evidence_valid", "cleanup_timeout", "environment_control_lost"},
                failure_codes={"REMEDIATION_TIMEOUT"},
            ),
            "artifact_backed_validator_pass_rate": score_metric(
                rows,
                validator_types={"workflow_evidence", "completion_artifact"},
            ),
        },
        "resource_metrics": {
            "duration_ms_total": eval_result.get("duration_ms_total"),
            "estimated_cost_total": eval_result.get("estimated_cost_total"),
            "retries_total": eval_result.get("retries_total"),
            "tool_error_rate": eval_result.get("tool_error_rate"),
        },
        "breakdowns": {
            "failure_code": count_values(rows, "failure_code"),
            "validator_type": count_values(rows, "validator_type"),
        },
    }


def cmd_run_evals(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    suite_path = Path(args.suite).resolve()
    rows = read_jsonl(suite_path)
    if len(rows) < 20 and suite_path.name == "benchmark_tasks.jsonl":
        raise ShRuntimeError("benchmark suite must include at least 20 tasks")
    eval_run_id = args.eval_run_id or ("eval_" + uuid.uuid4().hex[:12])
    sanitize_id(eval_run_id, "eval_run_id")
    out_dir = root / ".sh" / "evals" / eval_run_id
    if out_dir.exists():
        if not args.reset_existing:
            raise ShRuntimeError(f"eval run already exists: {eval_run_id!r}")
        if not is_under(out_dir, root / ".sh" / "evals"):
            raise ShRuntimeError("eval output escapes .sh/evals")
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    trial_results: List[Dict[str, Any]] = []
    eval_schema = load_json_object(root / "schemas" / "eval_task.schema.json", "eval task schema") if (root / "schemas" / "eval_task.schema.json").exists() else None
    for task_index, task in enumerate(rows):
        findings = validate_eval_task(task, task_index, root=root, schema=eval_schema)
        if findings:
            trial_results.append({"task_id": task.get("id"), "passed": False, "infra_findings": findings, "failure_code": "BENCHMARK_INFRA_FAILURE"})
            continue
        trial_count = max(int(args.trials), int(task.get("trial_count", 1)))
        for trial_index in range(1, trial_count + 1):
            trial_results.append(grade_eval_task(root, task, trial_index))
    total = len(trial_results)
    passed = len([row for row in trial_results if row.get("passed")])
    duration_total = sum(int(row.get("duration_ms", 0)) for row in trial_results)
    cost_total = round(sum(float(row.get("estimated_cost", 0.0)) for row in trial_results), 8)
    retries_total = sum(int(row.get("retries", 0)) for row in trial_results)
    tool_errors_total = sum(int(row.get("tool_errors", 0)) for row in trial_results)
    result = {
        "ok": passed == total and total > 0,
        "eval_run_id": eval_run_id,
        "suite": rel_posix(suite_path, root) if is_under(suite_path, root) else str(suite_path),
        "generated_at": utc_now(),
        "resource_spec": load_json_object(root / "evals" / "resource_spec.json", "resource spec") if (root / "evals" / "resource_spec.json").exists() else {},
        "task_count": len(rows),
        "trial_count": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "duration_ms_total": duration_total,
        "estimated_cost_total": cost_total,
        "retries_total": retries_total,
        "tool_error_rate": round(tool_errors_total / total, 4) if total else 0.0,
        "trial_results": trial_results,
    }
    write_json(out_dir / "eval_result.json", result)
    scorecard = build_eval_scorecard(result)
    scorecard_schema_path = root / "schemas" / "scorecard.schema.json"
    if scorecard_schema_path.exists():
        scorecard_schema = load_json_object(scorecard_schema_path, "scorecard schema")
        scorecard_findings = validate_against_schema(scorecard, scorecard_schema, "$.scorecard")
        if scorecard_findings:
            raise ShRuntimeError("generated scorecard failed schema validation", payload={"findings": scorecard_findings})
    write_json(out_dir / "scorecard.json", scorecard)
    review_lines = [
        f"# Transcript Review - {eval_run_id}",
        "",
        f"- suite: {result['suite']}",
        f"- pass_rate: {result['pass_rate']}",
        f"- failed: {result['failed']}",
        f"- scorecard: {out_dir / 'scorecard.json'}",
        "",
        "## Failed Trials",
    ]
    for row in trial_results:
        if not row.get("passed"):
            review_lines.append(f"- {row.get('task_id')} trial={row.get('trial_index')} failure={row.get('failure_code') or row.get('infra_findings')}")
    (out_dir / "transcript_review.md").write_text("\n".join(review_lines) + "\n", encoding="utf-8")
    return emit(
        {
            "ok": result["ok"],
            "eval_result": str(out_dir / "eval_result.json"),
            "scorecard": str(out_dir / "scorecard.json"),
            "summary": {k: result[k] for k in ("task_count", "trial_count", "pass_rate", "duration_ms_total", "estimated_cost_total", "retries_total", "tool_error_rate")},
        },
        0 if result["ok"] else 8,
    )


def cmd_append_ledger(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    entry = load_json(Path(args.entry).resolve())
    if not isinstance(entry, dict):
        raise ShRuntimeError("ledger entry must be a JSON object")
    normalized = normalize_ledger_entry(entry)
    ledger = root / ".sh" / "ledger.jsonl"
    chained = append_ledger_entry(ledger, normalized)
    return emit({"ok": True, "ledger": str(ledger), "entry": chained})


def normalize_ledger_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    reserved = sorted(set(entry) & RESERVED_LEDGER_KEYS)
    if reserved:
        raise ShRuntimeError("ledger entry attempts to set chain-reserved keys", payload={"reserved_keys": reserved})
    event_type = entry.get("event_type") or entry.get("Event Type")
    if event_type not in LEDGER_EVENT_TYPES:
        raise ShRuntimeError(f"Unknown ledger event_type: {event_type!r}")
    normalized = dict(entry)
    normalized["timestamp"] = normalized.get("timestamp") or utc_now()
    normalized["event_type"] = event_type
    return normalized


def last_ledger_entry_hash(ledger: Path) -> str:
    if not ledger.exists():
        return "sha256:0"
    last = ""
    with ledger.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last = line.strip()
    if not last:
        return "sha256:0"
    try:
        payload = json.loads(last)
        entry_hash = payload.get("entry_hash")
        if isinstance(entry_hash, str) and entry_hash.startswith("sha256:"):
            return entry_hash
    except json.JSONDecodeError:
        pass
    return "sha256:" + hashlib.sha256(last.encode("utf-8")).hexdigest()


def append_ledger_entry(ledger: Path, normalized: Dict[str, Any]) -> Dict[str, Any]:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    chained = dict(normalized)
    chained["prev_hash"] = last_ledger_entry_hash(ledger)
    unsigned = dict(chained)
    unsigned.pop("entry_hash", None)
    chained["entry_hash"] = json_sha256(unsigned)
    with ledger.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(chained, sort_keys=True, separators=(",", ":")) + "\n")
    return chained


def verify_ledger(ledger: Path) -> Dict[str, Any]:
    if not ledger.exists():
        return {"ok": True, "ledger": str(ledger), "line_count": 0, "last_hash": "sha256:0"}
    expected_prev_hash = "sha256:0"
    line_count = 0
    with ledger.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            line_count += 1
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError as exc:
                return {"ok": False, "ledger": str(ledger), "line": lineno, "error": f"invalid_json: {exc}"}
            if not isinstance(entry, dict):
                return {"ok": False, "ledger": str(ledger), "line": lineno, "error": "entry_not_object"}
            if entry.get("prev_hash") != expected_prev_hash:
                return {
                    "ok": False,
                    "ledger": str(ledger),
                    "line": lineno,
                    "error": "prev_hash_mismatch",
                    "expected_prev_hash": expected_prev_hash,
                    "actual_prev_hash": entry.get("prev_hash"),
                }
            entry_hash = entry.get("entry_hash")
            unsigned = dict(entry)
            unsigned.pop("entry_hash", None)
            actual_hash = json_sha256(unsigned)
            if entry_hash != actual_hash:
                return {
                    "ok": False,
                    "ledger": str(ledger),
                    "line": lineno,
                    "error": "entry_hash_mismatch",
                    "expected_entry_hash": actual_hash,
                    "actual_entry_hash": entry_hash,
                }
            expected_prev_hash = entry_hash
    return {"ok": True, "ledger": str(ledger), "line_count": line_count, "last_hash": expected_prev_hash}


def cmd_verify_ledger(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    result = verify_ledger(root / ".sh" / "ledger.jsonl")
    return emit(result, 0 if result["ok"] else 6)


def cmd_self_test(_: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "src").mkdir()
        (root / "src" / "app.txt").write_text("hello\n", encoding="utf-8")
        (root / "coverage").mkdir()
        (root / "coverage" / "lcov.info").write_text("TN:\n", encoding="utf-8")

        assert transition_result("RUNNING", "oracle_incomplete", "GAP_FILL")["ok"]
        assert not transition_result("RUNNING", "rehydration_pass", "RECOVERY")["ok"]
        assert transition_result("RUNNING", "sut_hang_incomplete", "REMEDIATING")["ok"]
        assert transition_result("GAP_FILL", "sut_hang_incomplete", "REMEDIATING")["ok"]
        assert transition_result("RECOVERY", "sut_hang_incomplete", "REMEDIATING")["ok"]
        assert transition_result("REMEDIATING", "cleanup_evidence_valid", "GAP_FILL")["ok"]
        assert transition_result("REMEDIATING", "cleanup_evidence_invalid", "REMEDIATING")["ok"]
        assert transition_result("REMEDIATING", "cleanup_timeout", "ABORTED")["ok"]

        hash_a = "sha256:" + ("a" * 64)
        hash_b = "sha256:" + ("b" * 64)
        hang_artifact = {
            "kind": "sut_tick_hang",
            "process_id": "proc_123",
            "tick_id": "tick_45",
            "started_at": "2026-06-13T18:10:00Z",
            "observed_at": "2026-06-13T18:11:00Z",
            "duration_ms": 60000,
            "previous_artifact_hash": hash_a,
            "current_artifact_hash": hash_a,
            "retry_count": 0,
        }
        hang_result = validate_completion_artifact(hang_artifact)
        assert hang_result["ok"]
        assert hang_result["status"] == "hang_detected"
        assert hang_result["recommended_oracle_verdict"] == "INCOMPLETE"
        assert hang_result["recommended_state"] == "REMEDIATING"
        assert hang_result["recommended_event"] == "sut_hang_incomplete"
        progress_artifact = dict(hang_artifact)
        progress_artifact["current_artifact_hash"] = hash_b
        progress_result = validate_completion_artifact(progress_artifact)
        assert progress_result["ok"]
        assert progress_result["status"] == "progressing"
        assert progress_result["recommended_state"] == "RUNNING"
        cleanup_artifact = {
            "kind": "remediation_evidence",
            "process_id": "proc_123",
            "tick_id": "tick_45",
            "remediation_started_at": "2026-06-13T18:11:00Z",
            "remediation_deadline_at": "2026-06-13T18:12:00Z",
            "observed_at": "2026-06-13T18:11:30Z",
            "cleanup_status": "reset_complete",
            "residual_resource_check": "clear",
            "evidence_hash": hash_b,
        }
        cleanup_result = validate_completion_artifact(cleanup_artifact)
        assert cleanup_result["ok"]
        assert cleanup_result["status"] == "cleanup_evidence_valid"
        assert cleanup_result["recommended_state"] == "GAP_FILL"
        expired_cleanup = dict(cleanup_artifact)
        expired_cleanup["observed_at"] = "2026-06-13T18:12:00Z"
        expired_result = validate_completion_artifact(expired_cleanup)
        assert expired_result["ok"]
        assert expired_result["status"] == "cleanup_timeout"
        assert expired_result["recommended_state"] == "ABORTED"

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
            "argv": ["python", "--version"],
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
        bad_contract["argv"] = ["python", "--version", "&&", "curl"]
        assert validate_resume_contract(bad_contract)["status"] == "rejected_security"
        script_contract = dict(good_contract)
        script_contract["argv"] = ["npm", "--version"]
        assert validate_resume_contract(script_contract)["status"] == "rejected_security"
        receipt = {
            "resume_check_id": "auth-smoke",
            "resume_check_contract_sha256": contract_sha256(good_contract),
        }
        assert validate_resume_contract(good_contract, receipt)["ok"]
        tampered_contract = dict(good_contract)
        tampered_contract["timeout_sec"] = 61
        assert validate_resume_contract(tampered_contract, receipt)["status"] == "rejected_security"

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
        evidence_artifact = root / "coverage" / "workflow.txt"
        evidence_artifact.write_text("passed\n", encoding="utf-8")
        workflow_artifact = dict(workflow_good)
        workflow_artifact["goal_id"] = "goal_1"
        workflow_artifact["seed_id"] = "seed_1"
        workflow_artifact["active_slice"] = "slice_1"
        workflow_artifact["records"] = [
            {
                "id": "lane_1",
                "criterion": "mechanical checks pass",
                "done": True,
                "evidence": ["coverage/workflow.txt"],
            }
        ]
        workflow_artifact["acceptance_verified"] = [
            {
                "criterion": "all checks pass",
                "record_ids": ["lane_1"],
                "evidence": "coverage/workflow.txt",
            }
        ]
        assert validate_workflow_evidence_contract(workflow_artifact, root=root, require_artifacts=True)["completion_allowed"]
        workflow_manifest = build_hash_manifest(
            root,
            {
                "drift_targets": ["src/missing.txt"],
                "evidence_assets": ["coverage/workflow.txt"],
            },
        )
        assert workflow_manifest["evidence_assets"][0]["path"] == "coverage/workflow.txt"
        artifact_manifest_result = validate_workflow_evidence_contract(
            workflow_artifact,
            root=root,
            require_artifacts=True,
            evidence_manifest=workflow_manifest,
        )
        assert artifact_manifest_result["completion_allowed"]
        assert artifact_manifest_result["artifact_evidence_hash"].startswith("sha256:")
        evidence_artifact.write_text("changed\n", encoding="utf-8")
        stale_manifest_result = validate_workflow_evidence_contract(
            workflow_artifact,
            root=root,
            require_artifacts=True,
            evidence_manifest=workflow_manifest,
        )
        assert not stale_manifest_result["completion_allowed"]
        assert any(item["code"] == "evidence_hash_mismatch" for item in stale_manifest_result["completion_blockers"])
        evidence_artifact.write_text("passed\n", encoding="utf-8")
        legacy_workflow_manifest = {
            "evidence_entries": workflow_manifest["evidence_assets"],
        }
        assert validate_workflow_evidence_contract(
            workflow_artifact,
            root=root,
            require_artifacts=True,
            evidence_manifest=legacy_workflow_manifest,
        )["completion_allowed"]
        empty_manifest_result = validate_workflow_evidence_contract(
            workflow_artifact,
            root=root,
            require_artifacts=True,
            evidence_manifest={"evidence_entries": []},
        )
        assert not empty_manifest_result["completion_allowed"]
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
        directive_cases = [
            ("RUNNING", "sut_hang_incomplete", "REMEDIATING", "remediate", "external-runner", True, True),
            ("REMEDIATING", "cleanup_evidence_valid", "GAP_FILL", "gap-fill", "goal-loop", True, True),
            ("REMEDIATING", "cleanup_evidence_invalid", "REMEDIATING", "remediate", "external-runner", True, True),
            ("REMEDIATING", "cleanup_timeout", "ABORTED", "abort", "none", False, False),
        ]
        for from_state, event, to_state, action, owner, recheck, allow_more in directive_cases:
            args = argparse.Namespace(
                root=str(root),
                run_id=f"directive_{event}",
                goal_id="goal_1",
                seed_id="seed_1",
                active_slice="slice_1",
                from_state=from_state,
                event=event,
                to_state=to_state,
                reason="self-test",
                next_owner=None,
                payload=None,
            )
            result = transition_result(from_state, event, to_state)
            payload = build_directive_payload(args, result, args.run_id)
            assert payload["to_state"] == to_state
            assert payload["action"] == action
            assert payload["required_next_owner"] == owner
            assert payload["oracle_recheck_required"] is recheck
            assert payload["allow_more_execution"] is allow_more

        entry_path = root / "entry.json"
        write_json(entry_path, {"event_type": "gap_fill", "summary": "self-test"})
        normalized = normalize_ledger_entry(load_json(entry_path))
        ledger = root / ".sh" / "ledger.jsonl"
        append_ledger_entry(ledger, normalized)
        write_json(entry_path, {"event_type": "oracle", "summary": "self-test"})
        append_ledger_entry(ledger, normalize_ledger_entry(load_json(entry_path)))
        assert verify_ledger(ledger)["ok"]
        run_result = create_run(
            root,
            run_id="run_smoke",
            goal_id="goal_1",
            seed_id="seed_1",
            active_slice="slice_1",
            objective="Verify durable runtime smoke path.",
            reset_existing=False,
        )
        assert run_result["ok"]
        step_result = record_step(
            root,
            run_id="run_smoke",
            step_id="step_1",
            operation_name="inspect",
            tool_name="rg",
            state_before="RUNNING",
            state_after="RUNNING",
            artifacts=["src/app.txt"],
            input_text="inspect repo",
            output_text="found app",
            duration_ms=7,
            token_usage_input=11,
            token_usage_output=13,
            estimated_cost=0.001,
            error_type=None,
            approval_needed=False,
            approval_result=None,
        )
        assert step_result["ok"]
        pause_transition = transition_result("RUNNING", "redteam_no_progress")
        assert pause_transition["ok"]
        interruptions = load_json_array(run_file(root, "run_smoke", "interruptions"), "interruptions")
        interruptions.append({"id": "int_smoke", "kind": "pause", "reason": "smoke pause", "timestamp": utc_now()})
        write_json(run_file(root, "run_smoke", "interruptions"), interruptions)
        record_step(
            root,
            run_id="run_smoke",
            step_id="int_smoke",
            operation_name="run.interruption",
            tool_name="sh_runtime.record-interruption",
            state_before="RUNNING",
            state_after="PAUSED",
            artifacts=[],
            input_text="smoke pause",
            output_text="pause",
            duration_ms=0,
            token_usage_input=0,
            token_usage_output=0,
            estimated_cost=0.0,
            error_type=None,
            approval_needed=False,
            approval_result=None,
            event_name="redteam_no_progress",
        )
        resume_transition = transition_result("PAUSED", "unstuck_accepted")
        assert resume_transition["ok"]
        record_step(
            root,
            run_id="run_smoke",
            step_id="resume_smoke",
            operation_name="run.resume",
            tool_name="sh_runtime.resume-run",
            state_before="PAUSED",
            state_after="RUNNING",
            artifacts=[],
            input_text="smoke resume",
            output_text="unstuck_accepted",
            duration_ms=0,
            token_usage_input=0,
            token_usage_output=0,
            estimated_cost=0.0,
            error_type=None,
            approval_needed=False,
            approval_result=None,
            event_name="unstuck_accepted",
        )
        record_step(
            root,
            run_id="run_smoke",
            step_id="remediate_smoke",
            operation_name="completion-auditor.hang",
            tool_name="sh_runtime.validate-completion-artifact",
            state_before="RUNNING",
            state_after="REMEDIATING",
            artifacts=["src/app.txt"],
            input_text="hang artifact",
            output_text="sut_hang_incomplete",
            duration_ms=1,
            token_usage_input=0,
            token_usage_output=0,
            estimated_cost=0.0,
            error_type="SUT_HANG_TIMEOUT",
            approval_needed=False,
            approval_result=None,
            event_name="sut_hang_incomplete",
        )
        record_step(
            root,
            run_id="run_smoke",
            step_id="cleanup_smoke",
            operation_name="completion-auditor.cleanup",
            tool_name="sh_runtime.validate-completion-artifact",
            state_before="REMEDIATING",
            state_after="GAP_FILL",
            artifacts=["src/app.txt"],
            input_text="cleanup evidence",
            output_text="cleanup_evidence_valid",
            duration_ms=1,
            token_usage_input=0,
            token_usage_output=0,
            estimated_cost=0.0,
            error_type=None,
            approval_needed=False,
            approval_result=None,
            event_name="cleanup_evidence_valid",
        )
        record_step(
            root,
            run_id="run_smoke",
            step_id="gap_fill_after_cleanup",
            operation_name="completion-auditor.gap-fill",
            tool_name="sh_runtime.record-step",
            state_before="GAP_FILL",
            state_after="RUNNING",
            artifacts=["src/app.txt"],
            input_text="time debt reconciled",
            output_text="missing_proof_acquired",
            duration_ms=1,
            token_usage_input=0,
            token_usage_output=0,
            estimated_cost=0.0,
            error_type=None,
            approval_needed=False,
            approval_result=None,
            event_name="missing_proof_acquired",
        )
        replay = update_replay(root, "run_smoke")
        assert replay["state"]["current_state"] == "RUNNING"
        assert (root / ".sh" / "runs" / "run_smoke" / "trace.jsonl").exists()
        assert (root / ".sh" / "runs" / "run_smoke" / "tool_calls.jsonl").exists()

        policy = {
            "profiles": {
                "read_only": {"network_allowlist": []},
                "workspace_write": {"network_allowlist": []},
                "scoped_network": {"network_allowlist": ["api.example.com"]},
                "danger_full_access": {"network_allowlist": ["*"]},
            }
        }
        assert validate_policy_action(root, policy, {"permission_profile": "read_only", "filesystem": {"writes": []}, "network": {"domains": []}, "command": {"argv": ["python", "--version"], "shell": False}})["ok"]
        unsafe_policy = validate_policy_action(root, policy, {"permission_profile": "read_only", "filesystem": {"writes": ["README.md"]}, "network": {"domains": []}, "command": {"argv": ["python", "--version"], "shell": False}, "approval": {"result": "denied"}})
        assert not unsafe_policy["ok"]

        evals_dir = root / "evals"
        evals_dir.mkdir()
        write_json(evals_dir / "resource_spec.json", {"cpu": "test", "memory": "test", "time_budget_sec": 60, "concurrency": 1, "network": "offline", "seed": "self-test", "retries": 0})
        task = {
            "id": "bench_001",
            "title": "Detect evidence-less completion",
            "vertical": "AI coding-agent completion auditor",
            "input": "Agent claims done without artifacts.",
            "expected_artifacts": ["evals/resource_spec.json"],
            "grader_config": {
                "outcome_grader": {"type": "outcome", "expected_outcome": "invalid_evidence_detected"},
                "transcript_behavior_grader": {"type": "transcript", "must_detect": "evidence_less_completion"},
            },
            "resource_spec": {"time_budget_sec": 60, "concurrency": 1, "network": "offline"},
            "trial_count": 3,
            "seed_policy": {"mode": "fixed", "seed": "bench_001"},
            "fixture": {
                "observed_outcome": "invalid_evidence_detected",
                "signals": ["evidence_less_completion"],
                "failure_code": "INVALID_EVIDENCE",
                "duration_ms": 10,
                "estimated_cost": 0.0,
                "retries": 0,
                "tool_errors": 0,
            },
        }
        with (evals_dir / "benchmark_tasks.jsonl").open("w", encoding="utf-8") as f:
            for i in range(20):
                row = dict(task)
                row["id"] = f"bench_{i + 1:03d}"
                row["seed_policy"] = {"mode": "fixed", "seed": row["id"]}
                f.write(json.dumps(row, sort_keys=True) + "\n")
        loaded_tasks = read_jsonl(evals_dir / "benchmark_tasks.jsonl")
        assert len(loaded_tasks) == 20
        assert not validate_eval_task(loaded_tasks[0], 0, root=root)
        trial_results = [grade_eval_task(root, row, trial) for row in loaded_tasks for trial in range(1, 4)]
        assert len(trial_results) == 60
        assert all(row["passed"] for row in trial_results)
        scorecard = build_eval_scorecard(
            {
                "eval_run_id": "self_test",
                "suite": "evals/benchmark_tasks.jsonl",
                "task_count": 20,
                "trial_count": len(trial_results),
                "passed": len(trial_results),
                "failed": 0,
                "pass_rate": 1.0,
                "duration_ms_total": 600,
                "estimated_cost_total": 0.0,
                "retries_total": 0,
                "tool_error_rate": 0.0,
                "trial_results": trial_results,
            }
        )
        assert scorecard["schema"] == "sh.scorecard.v1"
        assert scorecard["completion_auditor_metrics"]["evidence_gap_detection_rate"]["rate"] == 1.0
        try:
            record_step(
                root,
                run_id="run_smoke",
                step_id="bypass_complete",
                operation_name="bypass",
                tool_name=None,
                state_before="RUNNING",
                state_after="COMPLETE",
                artifacts=[],
                input_text=None,
                output_text=None,
                duration_ms=0,
                token_usage_input=0,
                token_usage_output=0,
                estimated_cost=0.0,
                error_type=None,
                approval_needed=False,
                approval_result=None,
            )
            raise AssertionError("state-changing record-step without event was accepted")
        except ShRuntimeError:
            pass
        try:
            normalize_ledger_entry({"event_type": "gap_fill", "prev_hash": "sha256:attacker-controlled"})
            raise AssertionError("reserved prev_hash was accepted")
        except ShRuntimeError:
            pass
        lines = ledger.read_text(encoding="utf-8").splitlines()
        lines[0] = lines[0].replace("gap_fill", "aborted")
        ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
        assert not verify_ledger(ledger)["ok"]

        # Manifest identity guard: matching name/version passes; a skewed
        # version or a missing canonical manifest is reported.
        guard_root = root / "manifest_guard"
        (guard_root / ".claude-plugin").mkdir(parents=True)
        (guard_root / ".codex-plugin").mkdir(parents=True)
        write_json(guard_root / "plugin.json", {"name": "demo", "version": "1.0.0"})
        write_json(guard_root / ".claude-plugin" / "plugin.json", {"name": "demo", "version": "1.0.0"})
        write_json(guard_root / ".codex-plugin" / "plugin.json", {"name": "demo", "version": "1.0.0"})
        write_json(guard_root / ".claude-plugin" / "marketplace.json", {"name": "demo", "version": "1.0.0", "plugins": [{"name": "demo", "version": "1.0.0"}]})
        assert validate_manifest_consistency(guard_root)["ok"]
        write_json(guard_root / ".codex-plugin" / "plugin.json", {"name": "demo", "version": "1.0.1"})
        skew = validate_manifest_consistency(guard_root)
        assert not skew["ok"]
        assert any(item["code"] == "manifest_version_mismatch" for item in skew["findings"])
        missing_root = root / "manifest_missing"
        missing_root.mkdir()
        write_json(missing_root / "plugin.json", {"name": "demo", "version": "1.0.0"})
        assert any(item["code"] == "missing_canonical_manifest" for item in validate_manifest_consistency(missing_root)["findings"])

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
    p.add_argument("--receipt", help="Blocked receipt binding the resume_check_id to a contract sha256")
    p.set_defaults(func=cmd_validate_resume)

    p = sub.add_parser("validate-workflow-evidence", help="Validate dynamic workflow evidence contract")
    p.add_argument("--evidence", required=True)
    p.add_argument("--root")
    p.add_argument("--require-artifacts", action="store_true")
    p.add_argument("--allow-descriptive-evidence", action="store_true", help="Legacy/low-risk mode: allow descriptive evidence strings instead of artifact-backed evidence")
    p.add_argument("--evidence-manifest", help="hash-manifest output whose evidence_assets must include evidence artifacts")
    p.set_defaults(func=cmd_validate_workflow_evidence)

    p = sub.add_parser("validate-completion-artifact", help="Validate Completion Auditor artifact evidence")
    p.add_argument("--artifact", required=True)
    p.add_argument("--max-retries", type=int, default=0)
    p.set_defaults(func=cmd_validate_completion_artifact)

    p = sub.add_parser("run-resume", help="Fail-closed resume check runner until a sandbox adapter exists")
    p.add_argument("--contract", required=True)
    p.add_argument("--receipt", help="Blocked receipt binding the resume_check_id to a contract sha256")
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

    p = sub.add_parser("verify-ledger", help="Verify .sh/ledger.jsonl hash-chain integrity")
    p.add_argument("--root", default=".")
    p.set_defaults(func=cmd_verify_ledger)

    p = sub.add_parser("start-run", help="Start a durable SH run and create run artifacts")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id")
    p.add_argument("--goal-id", required=True)
    p.add_argument("--seed-id", required=True)
    p.add_argument("--active-slice", required=True)
    p.add_argument("--objective", required=True)
    p.add_argument("--vertical", default="completion-auditor")
    p.add_argument("--permission-profile", default="read_only", choices=sorted(PERMISSION_PROFILES))
    p.add_argument("--reset-existing", action="store_true")
    p.set_defaults(func=cmd_start_run)

    p = sub.add_parser("record-step", help="Record a trace-backed step in an existing run")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", required=True)
    p.add_argument("--step-id", required=True)
    p.add_argument("--operation-name", required=True)
    p.add_argument("--tool-name")
    p.add_argument("--state-before", required=True)
    p.add_argument("--state-after", required=True)
    p.add_argument("--event", help="Required when state-before and state-after differ; must match the canonical transition map")
    p.add_argument("--artifact", action="append")
    p.add_argument("--input")
    p.add_argument("--output")
    p.add_argument("--duration-ms", type=int)
    p.add_argument("--token-usage-input", type=int)
    p.add_argument("--token-usage-output", type=int)
    p.add_argument("--estimated-cost", type=float)
    p.add_argument("--error-type")
    p.add_argument("--approval-needed", action="store_true")
    p.add_argument("--approval-result")
    p.set_defaults(func=cmd_record_step)

    p = sub.add_parser("record-interruption", help="Record pause/blocked/approval interruption and state transition")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", required=True)
    p.add_argument("--kind", required=True, choices=["pause", "blocked", "approval", "review", "abort"])
    p.add_argument("--reason", required=True)
    p.add_argument("--event")
    p.add_argument("--approval-needed", action="store_true")
    p.set_defaults(func=cmd_record_interruption)

    p = sub.add_parser("resume-run", help="Resume a paused or blocked run with the same run_id")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", required=True)
    p.add_argument("--reason")
    p.add_argument("--event")
    p.set_defaults(func=cmd_resume_run)

    p = sub.add_parser("replay-run", help="Reconstruct a run summary from trace and replay artifacts")
    p.add_argument("--root", default=".")
    p.add_argument("--run-id", required=True)
    p.add_argument("--refresh", action="store_true")
    p.set_defaults(func=cmd_replay_run)

    p = sub.add_parser("validate-schemas", help="Validate repo schemas, contracts, taxonomy, eval tasks, policy, and manifest identity")
    p.add_argument("--root", default=".")
    p.set_defaults(func=cmd_validate_schemas)

    p = sub.add_parser("validate-release", help="Validate release gate contracts, thin-contract anchors, and version surface")
    p.add_argument("--root", default=".")
    p.set_defaults(func=cmd_validate_release)

    p = sub.add_parser("validate-policy", help="Validate a proposed action against SH permission/network policy")
    p.add_argument("--root", default=".")
    p.add_argument("--policy", required=True)
    p.add_argument("--action-file", required=True)
    p.add_argument("--write-approval-log", action="store_true")
    p.set_defaults(func=cmd_validate_policy)

    p = sub.add_parser("run-evals", help="Run repo-local deterministic benchmark/eval fixtures")
    p.add_argument("--root", default=".")
    p.add_argument("--suite", required=True)
    p.add_argument("--trials", type=int, default=3)
    p.add_argument("--eval-run-id")
    p.add_argument("--reset-existing", action="store_true")
    p.set_defaults(func=cmd_run_evals)

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
