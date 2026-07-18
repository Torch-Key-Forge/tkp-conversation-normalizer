from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from tkp_conversation_normalizer.normalizer import (
    exact_asset_ids_from_text,
    normalize_export,
)

ROOT = Path(__file__).resolve().parents[1]


def load_fixture():
    return json.loads((ROOT / "fixtures" / "sanitized_conversations.json").read_text(encoding="utf-8"))


def test_fixture_schema_validates():
    schema = json.loads((ROOT / "schema" / "normalized_conversation.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    records = normalize_export(load_fixture(), source_name="sanitized_conversations.json")
    assert len(records) == 2
    for record in records:
        assert list(validator.iter_errors(record)) == []


def test_parent_precedes_child():
    record = normalize_export(load_fixture(), source_name="fixture.json")[1]
    positions = {turn["node_id"]: turn["ordinal"] for turn in record["turns"]}
    for turn in record["turns"]:
        parent = turn["parent_turn_id"]
        if parent in positions:
            assert positions[parent] < turn["ordinal"]


def test_branch_graph_is_preserved():
    record = normalize_export(load_fixture(), source_name="fixture.json")[1]
    assert record["metrics"]["reconstructed_fork_count"] == 1
    assert record["metrics"]["observed_branch_count"] == 2
    assert len({turn["observed_branch_id"] for turn in record["turns"] if turn["observed_branch_id"]}) == 2


def test_asset_identity_filter_is_fail_closed():
    text = "file_search file_path file-level file_0123456789abcdef01234567 file-AbCdEfGhIjKlMnOpQrStUv"
    assert exact_asset_ids_from_text(text) == {
        "file_0123456789abcdef01234567",
        "file-AbCdEfGhIjKlMnOpQrStUv",
    }


def test_continuation_question_is_not_restart_candidate():
    record = normalize_export(load_fixture(), source_name="fixture.json")[0]
    assert record["restart_candidates"] == []


def test_explicit_resumption_after_long_gap_is_provisional_candidate():
    record = normalize_export(load_fixture(), source_name="fixture.json")[1]
    assert len(record["restart_candidates"]) == 1
    candidate = record["restart_candidates"][0]
    assert candidate["operator_status"] == "proposed"
    assert "explicit_topic_shift_opening" in candidate["restart_reason"]
    assert "long_time_gap" in candidate["restart_reason"]
