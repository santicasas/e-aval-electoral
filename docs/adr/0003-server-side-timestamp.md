# 0003 — Server-side timestamp, no TSA

Status: Accepted. **Acceptance by the Junta Electoral is not verified.**

## Context
Instrucción 7/2011 requires a "sello o marca de tiempo" of the signature to be communicated to the Junta.

## Decision
No TSA. The server records the reception and validation time of each aval, and the document for the Junta
states this explicitly.

## Consequences
The server time is not signed by a third party. Risks: the Junta may require a qualified timestamp.
Possible cheap mitigation if needed: a hash-chained, periodically signed ledger of received avales. Ask the
pilot candidacy to confirm with its Junta.
