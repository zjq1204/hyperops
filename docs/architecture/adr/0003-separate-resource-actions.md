# ADR-0003: Keep Resource Actions Explicit and Separate

- Status: Accepted
- Date: 2026-09-01
- Scope: Object storage administration and employee workspaces

## Context

The previous interface used state-dependent actions and combined unrelated
resource operations under broad labels such as disabling object storage. This
made it unclear whether a click affected a key, a bucket, or all cloud resources.

## Decision

Use fixed, resource-specific actions: keys support disable, enable, rotate, and
revoke; buckets support release, recover, configure, and delete. There is no
global disable-all-resources action. Status is information, while action labels
remain stable. Cloud mutations are asynchronous and preserve the previous
configuration when they fail.

## Consequences

The user can predict the scope of every action. The interface needs explicit
confirmation dialogs and detail states, but it avoids accidental broad changes
and makes audit entries meaningful.
