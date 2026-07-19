# TKP Conversation Normalizer

A graph-aware, source-traceable normalizer for OpenAI conversation export JSON.

This is a supporting technical project for [Project Foreman](https://github.com/Torch-Key-Forge/tkp-project-foreman), the public product for recovering valuable work trapped inside long AI conversations.

## What it does

The normalizer:

- preserves conversation and message identities;
- reconstructs parent-first graph order from `mapping.parent`;
- preserves observed source branches;
- normalizes roles, timestamps, and content blocks;
- accepts only conservative export-style asset identifiers;
- classifies empty or non-text content instead of silently dropping it;
- emits provisional restart candidates separately from source-derived branch facts;
- generates registers, receipts, exceptions, and SHA-256 checksums;
- leaves source files untouched.

## What it does not do

It does **not**:

- acquire or capture conversations from a live account;
- infer operator authority, acceptance, execution, or completion;
- generate Project Foreman artifacts;
- claim that restart candidates are authoritative;
- distribute a private conversation corpus.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest -q

tkp-normalize .\fixtures\sanitized_conversations.json .\demo-output `
  --schema .\schema\normalized_conversation.schema.json
```

The output contains:

```text
demo-output/
├── normalized/
├── registers/
└── receipts/
```

## Input contract

Accepted inputs are:

- one OpenAI export conversation object;
- a JSON list of conversation objects;
- an object containing a `conversations` list;
- a directory containing `conversations-*.json` shards.

The canonical graph authority is `mapping.parent`. The source `children` field is not trusted as the sole ordering authority.

## Public evidence boundary

The included fixture is synthetic and sanitized. It demonstrates linear turns, branching, exact asset identity handling, a continuation question that must not become a restart candidate, and an explicit resumption after a long gap.

The historic private validation run processed 328 conversations and 29,345 turns with zero recorded normalization exceptions. That run is supporting evidence, not bundled source data. See `evidence/HISTORIC_VALIDATION_SUMMARY.md`.

## Status

`0.1.0-release-candidate`

- Runnable: yes
- Fixture-only public tests: yes
- Clean Windows wheel verification: passed
- Live capture: no
- Private corpus included: no
- Decision/authority intelligence: out of scope

## License

Released under the MIT License. See `LICENSE`.
