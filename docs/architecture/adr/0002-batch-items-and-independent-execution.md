# ADR-0002: Model Batch Applications as Independent Items

- Status: Accepted
- Date: 2026-09-01
- Scope: Object storage bucket applications

## Context

Users may request multiple buckets in one submission. A single cloud operation
can fail independently for each bucket, and rolling back successful buckets
would be destructive and confusing.

## Decision

Persist one application batch containing one item per requested bucket. Reserve
quota for the complete batch before execution. Execute items independently and
show aggregate counts at batch level. Each item may succeed, fail, retry, or be
cancelled without changing completed siblings.

RAM-user and first-key provisioning are shared prerequisites. Credential delivery
is available once at least one item is authorized. If every item fails, delivery
is withheld until retry or cancellation.

## Consequences

The UI can explain partial completion without exposing noisy attempt numbers.
The worker and audit model are slightly larger, but retries and failure recovery
are explicit and safe.
