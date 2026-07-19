from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .normalizer import normalize_export, sha256_file


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _input_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        shards = sorted(path.glob("conversations-*.json"))
        if shards:
            return shards
        files = sorted(path.glob("*.json"))
        if files:
            return files
    raise FileNotFoundError(f"No JSON input found at {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tkp-normalize",
        description="Normalize OpenAI conversation export JSON into graph-aware, source-traceable records.",
    )
    parser.add_argument("input", type=Path, help="conversations.json, one conversation JSON file, or a shard directory")
    parser.add_argument("output", type=Path, help="new output directory; must not already exist")
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parent / "schema" / "normalized_conversation.schema.json",
    )
    args = parser.parse_args(argv)

    if args.output.exists():
        parser.error(f"output already exists: {args.output}")
    if not args.schema.is_file():
        parser.error(f"schema not found: {args.schema}")

    files = _input_files(args.input)
    args.output.mkdir(parents=True)
    normalized_dir = args.output / "normalized"
    registers_dir = args.output / "registers"
    receipts_dir = args.output / "receipts"
    for directory in (normalized_dir, registers_dir, receipts_dir):
        directory.mkdir()

    schema = _load_json(args.schema)
    validator = Draft202012Validator(schema)
    generated_at = datetime.now(timezone.utc).isoformat()
    normalized_records: list[dict[str, Any]] = []
    exceptions: list[dict[str, str]] = []
    source_manifest: list[dict[str, Any]] = []

    for source_path in files:
        source_hash = sha256_file(source_path)
        source_manifest.append({"path": str(source_path), "sha256": source_hash})
        try:
            records = normalize_export(
                _load_json(source_path),
                source_name=source_path.name,
                source_sha256=source_hash,
            )
        except Exception as exc:
            exceptions.append({"source": str(source_path), "error": f"{type(exc).__name__}: {exc}"})
            continue
        for record in records:
            errors = sorted(validator.iter_errors(record), key=lambda error: list(error.path))
            if errors:
                exceptions.append({
                    "source": str(source_path),
                    "conversation_id": str(record.get("conversation_id")),
                    "error": "; ".join(error.message for error in errors),
                })
                continue
            out_path = normalized_dir / f"{record['conversation_id']}__normalized.json"
            out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            normalized_records.append(record)

    branch_register = []
    restart_register = []
    asset_register = []
    empty_register = []
    for record in normalized_records:
        conversation_id = record["conversation_id"]
        for turn in record["turns"]:
            if turn["observed_branch_id"]:
                branch_register.append({
                    "conversation_id": conversation_id,
                    "turn_id": turn["turn_id"],
                    "ordinal": turn["ordinal"],
                    "observed_branch_id": turn["observed_branch_id"],
                })
            for asset_id in turn["asset_ids"]:
                asset_register.append({
                    "conversation_id": conversation_id,
                    "turn_id": turn["turn_id"],
                    "asset_id": asset_id,
                })
            if turn["empty_content_classification"]:
                empty_register.append({
                    "conversation_id": conversation_id,
                    "turn_id": turn["turn_id"],
                    "classification": turn["empty_content_classification"],
                })
        for candidate in record["restart_candidates"]:
            restart_register.append({"conversation_id": conversation_id, **candidate})

    register_payloads = {
        "Observed_Branch_Register.json": branch_register,
        "Conversation_Restart_Candidate_Register.json": restart_register,
        "Asset_Reference_Register.json": asset_register,
        "Empty_Content_Classification_Register.json": empty_register,
    }
    for filename, payload in register_payloads.items():
        (registers_dir / filename).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    totals = {
        "source_file_count": len(files),
        "normalized_conversation_count": len(normalized_records),
        "turn_count": sum(record["metrics"]["turn_count"] for record in normalized_records),
        "reconstructed_fork_count": sum(record["metrics"]["reconstructed_fork_count"] for record in normalized_records),
        "observed_branch_count": sum(record["metrics"]["observed_branch_count"] for record in normalized_records),
        "restart_candidate_count": len(restart_register),
        "asset_reference_rows": len(asset_register),
        "empty_content_rows": len(empty_register),
        "exception_count": len(exceptions),
    }
    status = "PASS" if not exceptions and normalized_records else "FAIL"
    receipt = {
        "receipt_type": "TKP_CONVERSATION_NORMALIZATION_RUN",
        "version": "0.1.0",
        "generated_at": generated_at,
        "status": status,
        "source_files_modified": False,
        "source_manifest": source_manifest,
        "schema_sha256": sha256_file(args.schema),
        "totals": totals,
        "authorization_boundary": "Normalization only. No decision authority, execution, or completion is inferred.",
    }
    (receipts_dir / "Normalization_Run_Receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    (receipts_dir / "Normalization_Exception_Register.json").write_text(json.dumps(exceptions, indent=2) + "\n", encoding="utf-8")

    checksum_lines = []
    for path in sorted(args.output.rglob("*")):
        if path.is_file() and path.name != "CHECKSUMS.sha256":
            checksum_lines.append(f"{sha256_file(path)}  {path.relative_to(args.output).as_posix()}")
    (receipts_dir / "CHECKSUMS.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    print(json.dumps(receipt, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
