# ADR 006 Builder for validated maintenance requests

Status: accepted for the final implementation; feature PR pending partner review.

## Context

Request construction now combines four issue inputs with a server-owned identity/contact snapshot, an optional registered unit and optional image. Repeating long constructors would mix field order and encourage passing a browser-selected tenant identity.

## Decision

Add MaintenanceRequestBuilder with named optional assembly steps and build(). Tenant Service supplies the verified account; owner submissions omit it. Build delegates to the immutable MaintenanceRequest constructor, which retains all Domain validation. The Builder has no storage, session or presentation dependency. Assess all five creational patterns in pattern-map.md and decline patterns without an actual construction problem.

## Consequences

Call sites show what each optional part means. Existing four-field submission callers remain compatible. Built products are independent and frozen; rejected construction never reaches persistence. The extra class is justified by the expanded request shape and is covered by product/validation/service tests. This is Builder, not Factory Method or an enforced global Singleton.
