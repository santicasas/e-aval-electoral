# 0004 — Curated root CA list

Status: Accepted.

## Decision
A versioned, auditable list of accepted root CAs in the repository (Policía/DNIe, FNMT, ACCV, Izenpe, AOC,
Camerfirma, Firmaprofesional, ANF…) replaces processing the EU trusted lists.

## Consequences
The list must be derived from the CAs recognised by the INE electronic office. That list is not yet verified;
the owner reviews the proposal. Certificate classification (natural person vs seal vs legal person vs
representative) should rely on certificate policy OIDs and QCStatements, not on the subject alone.
