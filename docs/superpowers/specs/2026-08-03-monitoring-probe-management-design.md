# Monitoring Probe Management Design

## Goal

Separate host collection, probe configuration, and deployment execution so operators can understand where to configure each monitoring capability.

## Information Architecture

- **Collection Hosts** manages SSH connectivity and Categraf installation/runtime state only.
- **Probe Management** is one sidebar destination with routed tabs for targets, probe nodes, and Prometheus access configuration.
- **Deploy Jobs** remains the shared execution history for Categraf and blackbox-exporter installations.

## Probe Nodes

The node list represents shared blackbox-exporter capacity. A node without a host association is an independent probe; a node with a host association is a host probe. Enabled state is configuration intent, while online state comes from Prometheus active targets. Registered nodes must remain visible when Prometheus cannot confirm their runtime state.

Installing blackbox-exporter starts from the node page. The operator selects a host, reviews deployment parameters, and creates a deployment job. Successful installation may create or update the corresponding probe node through the existing backend workflow.

## Error Handling

Prometheus failures do not hide configured nodes. Their runtime state becomes unknown and the page explains that Prometheus could not verify them. Unmanaged endpoints discovered by Prometheus remain available for onboarding.

## Responsive Behavior

Desktop uses a compact operational table. Narrow screens use row cards with the same fields and actions. The three routed tabs remain horizontally scrollable without wrapping labels.
