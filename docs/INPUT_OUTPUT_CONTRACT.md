# Input and Output Contract

## Input

OpenAI export JSON containing conversation records with stable conversation IDs and a `mapping` graph.

## Source authority

- Conversation identity: `id`, falling back to `conversation_id`.
- Graph ancestry and ordering: `mapping.<node>.parent`.
- Message identity: `message.id`, falling back to the graph node ID.
- Source timestamps: export epoch fields when present.

## Output

One normalized JSON file per conversation plus four derived registers:

1. observed branch register;
2. provisional restart-candidate register;
3. exact asset-reference register;
4. empty-content classification register.

Receipts include source hashes, schema hash, totals, exceptions, and a checksum ledger.

## Hard boundary

Observed branches are source-derived facts. Restart candidates are provisional interpretive enrichment and require operator review.
