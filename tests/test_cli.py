from __future__ import annotations

import json
from pathlib import Path

from tkp_conversation_normalizer.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_cli_end_to_end(tmp_path: Path):
    output = tmp_path / "run"
    code = main([
        str(ROOT / "fixtures" / "sanitized_conversations.json"),
        str(output),
        "--schema",
        str(ROOT / "schema" / "normalized_conversation.schema.json"),
    ])
    assert code == 0
    receipt = json.loads((output / "receipts" / "Normalization_Run_Receipt.json").read_text())
    assert receipt["status"] == "PASS"
    assert receipt["totals"]["normalized_conversation_count"] == 2
    assert receipt["totals"]["exception_count"] == 0
    assert (output / "receipts" / "CHECKSUMS.sha256").is_file()
