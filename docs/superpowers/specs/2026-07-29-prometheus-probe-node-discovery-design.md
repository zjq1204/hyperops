# Prometheus Probe Node Discovery

## Goal

Make blackbox-exporter instances already scraped by Prometheus visible in the
HyperOps probe configuration center, then let an operator explicitly bring
them under HyperOps management without editing external Prometheus files.

## Product Flow

1. HyperOps reads Prometheus active targets and identifies exporter scrape
   endpoints, excluding blackbox probe requests.
2. Endpoints already represented by a HyperOps probe node are removed from the
   discovery result.
3. The settings page shows the discovery section only when unmanaged endpoints
   exist.
4. The operator chooses **Add to HyperOps**, confirms the node name, and decides
   whether to bind enabled targets that currently have no probe node.
5. Existing target bindings are never overwritten.
6. After onboarding, the discovery disappears and the node appears in the
   managed node list.

## Prometheus Migration Boundary

- HyperOps may inspect the live Prometheus configuration for legacy HTTP SD
  references such as port `18081`.
- When legacy configuration is detected, HyperOps displays a migration warning
  and the generated port `18080` configuration.
- HyperOps does not write Prometheus configuration files or restart Prometheus.
  The operator remains responsible for applying and reloading the external
  configuration.

## Safety Rules

- Discovery is read-only.
- Onboarding is explicit and transactional.
- Only enabled, unassigned probe targets are eligible for one-time binding.
- Existing bindings and disabled targets remain unchanged.
- Duplicate endpoint onboarding returns a conflict instead of creating another
  source of truth.

## Verification

- Backend API tests cover discovery, deduplication, onboarding, optional
  binding, and binding preservation.
- Frontend contract tests require conditional discovery UI, explicit binding,
  and legacy migration messaging.
- Live validation must confirm discovery against the configured Prometheus
  instance without submitting the onboarding action.
