# Schema notes

The three JSON Schemas in [`../schemas/`](../schemas/) are the normative definition of the data. The Python code is one implementation of them. This page explains the reasoning, field by field. Schemas use JSON Schema draft 2020-12.

## `diff.schema.json`: one amendment

| Field | Required | Notes |
|---|---|---|
| `diff_id` | yes | Unique across the ledger. Duplicates are refused at append and flagged at verify. |
| `instrument_id` | yes | The rulebook the amendment belongs to. |
| `op` | yes | `insert`, `replace` or `repeal`. There is no `edit`. A correction is another amendment. |
| `clause_id` | yes | Dotted identifier such as `1.1`. Ordered naturally (1.2 before 1.10). It is an opaque label; a production design should separate permanent identity from display number. |
| `authority` | yes | Who issued it. |
| `source_ref` | yes | The circular, order or notification reference as printed. |
| `effective_from` | no | The date the amendment *claims* to apply from, with an explicit offset. It is a claim, not a fact. Under the `tora` regime it can never operate earlier than publication. |
| `note` | no | Free text. |
| `clause` | insert, replace | The clause body. Forbidden on repeal. |

**There is deliberately no `published_at` field.** The ledger assigns publication time when it appends, so that nobody submitting an amendment can say when it was published. A diff that tries to carry one is rejected by the schema (`additionalProperties: false`), and a test checks it.

### `clause`

| Field | Required | Notes |
|---|---|---|
| `text` | yes | The words of the rule. What the text says is what applies. |
| `subject` | no | What the clause governs, for the discretion probe (for example `annual_return_due`). |
| `value` | no | What the clause requires on that subject (for example `45d`). |
| `scope` | no | Map from fact attribute to a non-empty list of accepted values. A missing attribute means "any value". An empty scope applies to every fact pattern. Specificity is the number of attributes constrained. |

## `ledger_entry.schema.json`: the hash chain

| Field | Notes |
|---|---|
| `seq` | Zero-based, gap-free. |
| `prev_hash` | Hash of the previous entry; 64 zeros for the first. |
| `published_at` | UTC, second precision (`YYYY-MM-DDTHH:MM:SSZ`). Never earlier than the previous entry. |
| `diff` | The amendment. |
| `hash` | SHA-256 (hex) of the canonical JSON of `{seq, prev_hash, published_at, diff}`: keys sorted, separators `,` and `:`, UTF-8, no ASCII escaping. |

Because `published_at` is inside the hash, changing a publication time breaks the chain exactly as changing the text does.

## `corpus.schema.json`: what is not law

| Field | Notes |
|---|---|
| `disclaimer` | Required text stating the data is synthetic. |
| `instruments` | Titles and issuing authority for display. |
| `shadows` | Circulars that were applied but never published, each with `surfaced_at` (when first applied to someone). They model legacy practice, are excluded from the chain, and have no effect under the `tora` regime. |
| `facts` | Fact patterns (label plus attribute values) for the discretion probe. |

Keeping shadows in a separate file that is outside the hash chain is intentional: a rule that is not in the ledger should not look like one that is.

## Compatibility

Schema changes that would alter the hash input (new required fields inside `diff`, a different canonicalisation) invalidate existing ledgers. Version any such change explicitly and never rewrite an existing ledger to fit it.
