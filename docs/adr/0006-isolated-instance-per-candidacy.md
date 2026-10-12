# 0006 — One isolated instance per candidacy

Status: Accepted.

## Decision
Each candidacy gets its own instance (database and encryption key) on the same VPS. No data shared across
candidacies.

## Consequences
Duplicate-aval detection across candidacies is NOT implemented (decision pending). Default behaviour is total
isolation plus a clear warning to the signer that endorsing more than one candidacy annuls all their avales.
