# ADR-0001: Use a Platform-Level Object Storage Model

- Status: Accepted
- Date: 2026-09-01
- Scope: HyperOps object storage phase one

## Context

The original design modeled object storage around enterprises and tenants. The
actual product has one Feishu application and one Alibaba Cloud resource pool,
and the user-facing concept is simply a HyperOps user's own object storage.
The product is not yet online and has no real object-storage data to migrate.

## Decision

Replace the object-storage tenant model with singleton platform configuration
and direct ownership by the existing HyperOps user model. Use one platform
Feishu configuration, one platform object-storage configuration, one RAM user per
HyperOps user, and batch/item application records. Remove enterprise selection,
tenant query parameters, and tenant-dependent authorization from the phase-one
runtime.

## Consequences

The data model and UI match the actual product mental model, and authorization
is easier to audit. The migration is a clean forward migration rather than a
compatibility bridge. Adding multiple providers, pools, or organizations later
will require an explicit architecture decision instead of being accidentally
inherited from the old model.
