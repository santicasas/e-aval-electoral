# 0010 — Recommended defaults for the open format questions

Status: Accepted as configurable defaults (owner, 2026-10-12). Items marked UNVERIFIED must be confirmed with
the Junta Electoral / Oficina del Censo; none of them is hard-coded, all are options in `eaval.config.Options`.

| Question | Default | Where | Status |
|---|---|---|---|
| Name and surnames case/accents | Upper case, accents removed except Ñ and Ç (`name_case="upper_ascii"`); `as_typed` available. The signer always sees the normalised text before signing | `normalize.py` | UNVERIFIED: whether the Oficina del Censo compares names |
| Name or surname over the XSD limit | Truncate and show a notice before signing (`overflow="truncate"`); `reject` available. Never silent. The candidacy name and the id are never truncated | `normalize.py`, `prepare.py` | Decided |
| `/` in constituency names inside the ZIP name | Replaced by `-` (`Araba-Álava`), configurable per character; the same substitution covers `\ : * ? " < > \|` in candidacy names. XML values are never altered | `zipexport.py`, `config.py` | UNVERIFIED: the BOE is silent; to be asked to the Junta |
| Dots inside a name part | Kept, but flagged (`dot_in_name_part`): the format `EEEEEE.CCCCCC.PPPPPP` uses the dot as separator | `zipexport.py` | UNVERIFIED |
| Province with islands and both chambers | Two avals: `CONGRESO` with the province and `SENADO` with the island, signed one after the other with a single data confirmation; two ZIPs. The signer chooses the island they are registered in | `constituencies.required_avals` | Design confirmed by default; the double-signature UI flow is not implemented yet |
| Minimum age | 18 on election day (needs the election date) | `normalize.py` | Proposal accepted by default |
| NIF types K, L, M | Rejected | `normalize.py` | Proposal accepted by default |
| NIE | Only for `PARLAMENTO EUROPEO` | `prepare.py` | From the owner's brief |

Other facts: the ZIP file name is kept in NFC; the archive entries are ASCII (`NIF.xml`), so no UTF-8 flag is
needed inside the archive. DNI numbers shorter than 8 digits are left-padded with zeros; NIE are not padded.
