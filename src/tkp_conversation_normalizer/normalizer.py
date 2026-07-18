from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ASSET_ID_PATTERNS = (
    re.compile(r"\bfile-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bfile_[0-9a-fA-F]{24,}\b"),
)

RESTART_OPENING_PATTERNS = (
    re.compile(r"^\s*(?:okay|ok|alright|right|so)?[\s,;:—-]*(?:let['’]?s|lets)\s+go\s+back\b", re.I),
    re.compile(r"^\s*(?:okay|ok|alright|right|so)?[\s,;:—-]*(?:let['’]?s|lets)\s+return\s+to\b", re.I),
    re.compile(r"^\s*(?:okay|ok|alright|right|so)?[\s,;:—-]*(?:let['’]?s|lets)\s+revisit\b", re.I),
    re.compile(r"^\s*(?:okay|ok|alright|right|so)?[\s,;:—-]*back\s+to\b", re.I),
    re.compile(r"^\s*(?:another|separate|different|new)\s+question\b", re.I),
    re.compile(r"^\s*(?:switching|changing)\s+(?:topics?|subjects?)\b", re.I),
)

CONTINUATION_ONLY_PATTERNS = (
    re.compile(r"^\s*(?:what|which)\s+(?:are|is)\s+the\s+next\s+steps?\b", re.I),
    re.compile(r"^\s*(?:okay|ok|alright|so)?[\s,;:—-]*what['’]?s\s+next\b", re.I),
    re.compile(r"^\s*(?:okay|ok|alright|so)?[\s,;:—-]*now\s+what\b", re.I),
)

MACHINE_JSON_KEYS = {
    "asset_pointer",
    "sandbox",
    "file_id",
    "file_name",
    "mime_type",
    "attachment_id",
    "content_type",
    "image_url",
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def iso_from_epoch(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def exact_asset_ids_from_text(text: str) -> set[str]:
    refs: set[str] = set()
    for pattern in ASSET_ID_PATTERNS:
        refs.update(pattern.findall(text))
    return refs


def find_asset_refs(value: Any) -> set[str]:
    refs: set[str] = set()

    def walk(item: Any, key_hint: str | None = None) -> None:
        if isinstance(item, str):
            refs.update(exact_asset_ids_from_text(item))
            if key_hint in {"file_id", "attachment_id", "asset_id"}:
                if re.fullmatch(r"(?:file-|file_)[A-Za-z0-9_-]{20,}", item):
                    refs.add(item)
        elif isinstance(item, dict):
            for key, sub in item.items():
                walk(sub, str(key))
        elif isinstance(item, list):
            for sub in item:
                walk(sub, key_hint)

    walk(value)
    return refs


def classify_empty_content(message: dict[str, Any]) -> str:
    content = message.get("content")
    if not isinstance(content, dict):
        return "content_not_object"
    content_type = str(content.get("content_type") or "unknown")
    parts = content.get("parts")
    if parts is None:
        return f"parts_missing::{content_type}"
    if not isinstance(parts, list):
        return f"parts_not_array::{content_type}"
    if not parts:
        return f"parts_empty::{content_type}"
    if find_asset_refs(message):
        return f"asset_only_or_nontext::{content_type}"
    for part in parts:
        if isinstance(part, str) and part.strip():
            return f"unclassified::{content_type}"
        if isinstance(part, dict) and isinstance(part.get("text"), str) and part["text"].strip():
            return f"unclassified::{content_type}"
    return f"parts_present_no_text::{content_type}"


def extract_content_blocks(message: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], str | None]:
    content = message.get("content")
    warnings: list[str] = []
    blocks: list[dict[str, Any]] = []
    empty_classification: str | None = None

    if not isinstance(content, dict):
        empty_classification = classify_empty_content(message)
        blocks.append({
            "block_type": "unknown",
            "text": "",
            "language": None,
            "source_fragment_sha256": sha256_text(""),
        })
        warnings.append("Message content was not an object; empty unknown block preserved.")
        return blocks, warnings, empty_classification

    content_type = str(content.get("content_type") or "").lower()
    default_block_type = {
        "text": "markdown",
        "multimodal_text": "markdown",
        "code": "code",
        "execution_output": "tool_result",
        "computer_initialize_state": "tool_result",
    }.get(content_type, "unknown")

    parts = content.get("parts")
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, str):
                blocks.append({
                    "block_type": default_block_type,
                    "text": part,
                    "language": None,
                    "source_fragment_sha256": sha256_text(part),
                })
            elif isinstance(part, dict):
                text = part.get("text")
                assets = find_asset_refs(part)
                if isinstance(text, str):
                    blocks.append({
                        "block_type": "image_reference" if assets else default_block_type,
                        "text": text,
                        "language": None,
                        "source_fragment_sha256": sha256_text(text),
                    })
                elif assets:
                    for asset_id in sorted(assets):
                        rendered = f"asset_reference:{asset_id}"
                        blocks.append({
                            "block_type": "image_reference",
                            "text": rendered,
                            "language": None,
                            "source_fragment_sha256": sha256_text(rendered),
                        })
                elif part:
                    rendered = json.dumps(part, ensure_ascii=False, sort_keys=True)
                    blocks.append({
                        "block_type": "unknown",
                        "text": rendered,
                        "language": None,
                        "source_fragment_sha256": sha256_text(rendered),
                    })

    represented = set()
    for block in blocks:
        represented.update(find_asset_refs(block["text"]))
    for asset_id in sorted(find_asset_refs(message) - represented):
        rendered = f"asset_reference:{asset_id}"
        blocks.append({
            "block_type": "image_reference",
            "text": rendered,
            "language": None,
            "source_fragment_sha256": sha256_text(rendered),
        })

    if not blocks or not any(block["text"].strip() for block in blocks):
        empty_classification = classify_empty_content(message)
        if not blocks:
            blocks.append({
                "block_type": "unknown",
                "text": "",
                "language": None,
                "source_fragment_sha256": sha256_text(""),
            })
        warnings.append(f"Empty or non-text content preserved; classification={empty_classification}.")

    return blocks, warnings, empty_classification


def build_graph(conversation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping = conversation.get("mapping")
    if not isinstance(mapping, dict):
        return {}
    graph: dict[str, dict[str, Any]] = {}
    for node_id, node in mapping.items():
        if not isinstance(node, dict):
            continue
        graph[str(node_id)] = {
            "node_id": str(node_id),
            "parent": str(node.get("parent")) if node.get("parent") is not None else None,
            "children": [],
            "message": node.get("message") if isinstance(node.get("message"), dict) else None,
        }
    for node_id, node in graph.items():
        parent = node["parent"]
        if parent in graph:
            graph[parent]["children"].append(node_id)
    for node in graph.values():
        node["children"] = sorted(set(node["children"]))
    return graph


def graph_parent_first_order(graph: dict[str, dict[str, Any]]) -> list[str]:
    if not graph:
        return []
    roots = sorted(node_id for node_id, node in graph.items() if node["parent"] not in graph)
    roots = roots or sorted(graph)[:1]
    ordered: list[str] = []
    seen: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in seen or node_id not in graph:
            return
        seen.add(node_id)
        if graph[node_id]["message"] is not None:
            ordered.append(node_id)
        for child in graph[node_id]["children"]:
            visit(child)

    for root in roots:
        visit(root)
    for node_id in sorted(graph):
        visit(node_id)
    return ordered


def assign_observed_branch_ids(graph: dict[str, dict[str, Any]]) -> dict[str, str | None]:
    roots = sorted(node_id for node_id, node in graph.items() if node["parent"] not in graph)
    roots = roots or sorted(graph)[:1]
    branch_ids: dict[str, str | None] = {}
    queue: deque[tuple[str, str | None]] = deque((root, None) for root in roots)
    seen: set[str] = set()
    while queue:
        node_id, inherited = queue.popleft()
        if node_id in seen or node_id not in graph:
            continue
        seen.add(node_id)
        branch_ids[node_id] = inherited
        children = graph[node_id]["children"]
        if len(children) <= 1:
            queue.extend((child, inherited) for child in children)
        else:
            for index, child in enumerate(children, start=1):
                seed = f"{node_id}:{child}:{index}"
                suffix = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
                queue.append((child, f"branch_{suffix}"))
    for node_id in graph:
        branch_ids.setdefault(node_id, None)
    return branch_ids


def _looks_like_machine_payload(text: str) -> bool:
    stripped = text.strip()
    if not stripped or stripped.startswith("asset_reference:"):
        return True
    if stripped[:1] in "[{" and stripped[-1:] in "]}":
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return False
        if isinstance(payload, dict):
            keys = {str(key).lower() for key in payload}
            return bool(keys & MACHINE_JSON_KEYS) or (len(stripped) > 250 and len(keys) >= 3)
        return isinstance(payload, list) and len(stripped) > 250
    return False


def restart_candidate(
    ordinal: int,
    role: str,
    text: str,
    previous_created_at: str | None,
    created_at: str | None,
    block_types: set[str],
    empty_classification: str | None,
) -> dict[str, Any] | None:
    if role != "user" or ordinal <= 1 or empty_classification is not None:
        return None
    if block_types <= {"image_reference", "tool_result", "unknown"}:
        return None
    stripped = text.strip()
    if len(stripped) < 40 or _looks_like_machine_payload(stripped):
        return None
    if any(pattern.search(stripped) for pattern in CONTINUATION_ONLY_PATTERNS):
        return None

    reasons: list[str] = []
    if any(pattern.search(stripped) for pattern in RESTART_OPENING_PATTERNS):
        reasons.append("explicit_topic_shift_opening")
    if previous_created_at and created_at:
        try:
            previous = datetime.fromisoformat(previous_created_at)
            current = datetime.fromisoformat(created_at)
            if (current - previous).total_seconds() >= 6 * 60 * 60:
                reasons.append("long_time_gap")
        except ValueError:
            pass
    if len(stripped) >= 500 and reasons:
        reasons.append("substantial_human_prompt")
    if not reasons:
        return None
    confidence = min(0.95, 0.58 + 0.12 * len(reasons))
    return {
        "restart_candidate_id": f"restart_{ordinal:04d}",
        "restart_reason": reasons,
        "restart_confidence": round(confidence, 2),
        "operator_status": "proposed",
        "materialized_conversation_id": None,
    }


def normalize_conversation(
    conversation: dict[str, Any],
    *,
    source_name: str = "conversations.json",
    source_sha256: str | None = None,
) -> dict[str, Any]:
    conversation_id = conversation.get("id") or conversation.get("conversation_id")
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise ValueError("Conversation is missing a non-empty id or conversation_id.")

    graph = build_graph(conversation)
    order = graph_parent_first_order(graph)
    branch_ids = assign_observed_branch_ids(graph)
    turns: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    previous_created_at: str | None = None
    empty_counts: Counter[str] = Counter()

    for ordinal, node_id in enumerate(order, start=1):
        node = graph[node_id]
        message = node["message"] or {}
        author = message.get("author")
        role = str(author.get("role") or "unknown") if isinstance(author, dict) else "unknown"
        created_at = iso_from_epoch(message.get("create_time"))
        blocks, warnings, empty_classification = extract_content_blocks(message)
        if empty_classification:
            empty_counts[empty_classification] += 1
        text = "\n".join(block["text"] for block in blocks if block["text"])
        assets = sorted(find_asset_refs(message))
        turn = {
            "turn_id": str(message.get("id") or node_id),
            "node_id": node_id,
            "parent_turn_id": node["parent"] if node["parent"] in graph else None,
            "ordinal": ordinal,
            "decimal_label": f"{ordinal}.0",
            "role": role,
            "created_at": created_at,
            "observed_branch_id": branch_ids.get(node_id),
            "content_blocks": blocks,
            "asset_ids": assets,
            "empty_content_classification": empty_classification,
            "warnings": warnings,
            "source_message_sha256": sha256_text(json.dumps(message, ensure_ascii=False, sort_keys=True)),
        }
        turns.append(turn)
        candidate = restart_candidate(
            ordinal,
            role,
            text,
            previous_created_at,
            created_at,
            {block["block_type"] for block in blocks},
            empty_classification,
        )
        if candidate:
            candidate.update({"turn_id": turn["turn_id"], "ordinal": ordinal})
            candidates.append(candidate)
        if created_at:
            previous_created_at = created_at

    branch_nodes = [node_id for node_id, node in graph.items() if len(node["children"]) > 1]
    observed_branch_ids = sorted({value for value in branch_ids.values() if value is not None})
    project_id = conversation.get("project_id") or conversation.get("workspace_id")

    return {
        "schema_version": "0.1.0",
        "conversation_id": conversation_id.strip(),
        "title": str(conversation.get("title") or "Untitled conversation"),
        "project_id": str(project_id) if project_id is not None else None,
        "created_at": iso_from_epoch(conversation.get("create_time")),
        "updated_at": iso_from_epoch(conversation.get("update_time")),
        "source": {
            "source_type": "openai_export_json",
            "source_name": source_name,
            "source_sha256": source_sha256,
            "source_record_modified": False,
            "completeness": "export_record",
            "confidence": 1.0,
        },
        "turns": turns,
        "observed_branches": {
            "branching_node_ids": sorted(branch_nodes),
            "observed_branch_ids": observed_branch_ids,
            "authority": "mapping.parent",
        },
        "restart_candidates": candidates,
        "metrics": {
            "turn_count": len(turns),
            "reconstructed_fork_count": len(branch_nodes),
            "observed_branch_count": len(observed_branch_ids),
            "restart_candidate_count": len(candidates),
            "asset_reference_count": len(find_asset_refs(conversation)),
            "empty_content_count": sum(empty_counts.values()),
            "empty_content_classifications": dict(empty_counts),
        },
        "limitations": [
            "Observed branches are source-derived graph facts.",
            "Restart candidates are provisional and require operator review.",
            "Normalization does not infer decision authority or execution status.",
        ],
    }


def _iter_conversations(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                yield item
        return
    if isinstance(payload, dict):
        if isinstance(payload.get("conversations"), list):
            yield from _iter_conversations(payload["conversations"])
            return
        yield payload
        return
    raise ValueError("Input JSON must be a conversation object, a list, or an object with a conversations list.")


def normalize_export(payload: Any, *, source_name: str, source_sha256: str | None = None) -> list[dict[str, Any]]:
    return [
        normalize_conversation(item, source_name=source_name, source_sha256=source_sha256)
        for item in _iter_conversations(payload)
    ]
