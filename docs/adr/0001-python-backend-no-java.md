# 0001 — Python backend, no Java

Status: Proposed — pending Phase 0 PoC results.

## Context
Validating AutoFirma's XAdES output and the certificate chain is usually done with Java (DSS, @firma). We
want a small Python stack that fits the smallest VPS and a short timeline.

## Decision
Use Python (FastAPI or equivalent) with SignXML (`signxml.xades`) or equivalent for XAdES verification and
pyhanko-certvalidator for chain, validity and revocation. Confirm in the PoC (items 1–5).

## Fallback (owner decides, not us)
If XAdES verification or certificate validation fail without a quick fix: run the European Commission DSS or
the official @firma three-phase server as closed containers, with no Java code of our own.

## Consequences
Known risk: differences between AutoFirma's output (XAdES namespace version, transforms, algorithms) and what
the library accepts. The client-side AutoFirma is Java regardless; this ADR concerns only our backend.
