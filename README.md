# TKP Conversation Normalizer

**Turn supported AI conversation exports into stable, source-traceable records that downstream recovery tools can trust.**

TKP Conversation Normalizer is the first public technical component in the Project Foreman recovery chain. It reconstructs conversation structure conservatively, preserves source identity and branches, and emits deterministic records, registers, receipts, and checksums without modifying the source export.

## Where it fits

```text
AI conversation export
        ↓
TKP Conversation Normalizer
        ↓
TKP Decision and Authority Intelligence
        ↓
TKP Conversation-to-Artifact
        ↓
Project Foreman workspace / recovery package
```

Related public components:

- [Project Foreman](https://github.com/Torch-Key-Forge/tkp-project-foreman) — the product-level recovery surface;
- [TKP Decision and Authority Intelligence](https://github.com/Torch-Key-Forge/tkp-decision-authority-intelligence) — separates operator authority from proposals and review candidates;
- [TKP Conversation-to-Artifact](https://github.com/Torch-Key-Forge/tkp-conversation-to-artifact) — composes reviewed evidence into portable project artifacts.

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

## Fit and limitations

Use this component when the job is **deterministic normalization and graph reconstruction of supported conversation-export JSON**.

It does **not**:

- acquire or capture conversations from a live account;
- infer operator authority, acceptance, execution, or completion;
- generate complete Project Foreman artifacts;
- claim that restart candidates are authoritative;
- distribute a private conversation corpus;
- establish general provider or marketplace portability.

## Fastest first value

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

## Proof and evidence boundary

The included fixture is synthetic and sanitized. It demonstrates linear turns, branching, exact asset identity handling, a continuation question that must not become a restart candidate, and an explicit resumption after a long gap.

The historic private validation run processed 328 conversations and 29,345 turns with zero recorded normalization exceptions. That run is supporting evidence, not bundled source data. See `evidence/HISTORIC_VALIDATION_SUMMARY.md`.

## Current release state

Current public release: **v0.1.0**, published July 19, 2026.

- Runnable: yes
- Fixture-only public tests: yes
- Clean Windows wheel verification: passed
- GitHub-hosted Windows verification on the release head: passed
- Live capture: no
- Private corpus included: no
- Decision/authority intelligence: out of scope

The release verification covered source tests, wheel construction, fresh-environment installation, CLI fixture execution, schema validation, PASS receipt generation, zero recorded exceptions, and a targeted privacy scan. See [PUBLICATION_READINESS.md](PUBLICATION_READINESS.md) and [WINDOWS_VERIFICATION_GATE.md](WINDOWS_VERIFICATION_GATE.md).

## Trust, support, and security

For ordinary usage questions and non-sensitive defects, see [SUPPORT.md](SUPPORT.md).

For credential, privacy, and security-sensitive handling guidance, see [SECURITY.md](SECURITY.md). The repository does not currently claim a dedicated private vulnerability-reporting channel.

## Product and portability boundary

This repository is an upstream **product component** for Project Foreman. Its current public contract is normalization of supported conversation-export JSON into stable, source-traceable records.

No general multi-provider acquisition layer, decision/authority engine, or cross-marketplace/target adapter framework is claimed here. Portability beyond the documented input forms and packaged Python CLI has not been independently established by this repository.

## License

Released under the MIT License. See `LICENSE`.
