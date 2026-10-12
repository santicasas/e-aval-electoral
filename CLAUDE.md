# e-aval-electoral — permanent project context

Open-source platform that lets any candidacy (party, federation, coalition, electors' group) collect
**electoral endorsements (avales) with electronic signature**, per constituency, for free. Deployable by a
candidacy on its own or offered as a service. Immediate target: **Spanish general elections, 29 Nov 2026**
(Real Decreto 806/2026 of 5 Oct, published in BOE 6 Oct 2026 — verified).

The owner is an expert in electronic signature / eIDAS / trust services. Do not explain basics; **say clearly
when a decision depends on an unverified requirement**. Chat language: Catalan. Technical docs, code comments,
commit messages: English. README: English, Catalan, Spanish.

## Calendar (main constraint)
- 6 Oct: elections called; avales are only valid if signed after this date.
- 21–26 Oct: candidacies filed, with avales.
- 30 Oct: deadline for Juntas to report irregularities; then 48 h to fix.
- **Production target: 16–17 Oct.** Anything not essential for that date goes to a later phase.
- **Public-repo rule:** this repository is public. It must never contain information about any specific
  candidacy (names, config, contacts, notes, test data, commit messages, issues). Per-candidacy
  configuration lives outside the repo (private deployment config / secrets). Use neutral placeholders
  such as "Example Candidacy" in docs, fixtures and tests.

## Phase 0 — PoC (current phase)
Two days max, throwaway code in `poc/`. **Do not write platform code until the owner reads the PoC report
(`poc/REPORT.md`) and decides.** The Python-vs-DSS/@firma-trifasic decision is the owner's, not ours: present
results and options only.

PoC scope: (1) static page -> AutoFirma (AutoScript, local WebSocket), XAdES enveloped over `avalcandidatura`,
under the production CSP; (2) verify AutoFirma's XAdES in Python (SignXML or equivalent); (3) certificate
validation with pyhanko-certvalidator (curated root, validity, OCSP/CRL, NIF extraction, reject seals /
legal-person / representative certs); (4) integrity: server-generated node == signed node; (5) real
certificates; (6) mobile storage/retrieve servers (optional); (7) resource usage on a small VPS.

PoC test material: the owner's **software idCAT certificate only**. DNIe and FNMT are NOT available, so NIF
extraction for those issuers stays unverified and must be reported as such. Rejection cases (revoked, expired,
seal, legal person) need synthetic certificates generated in-test.

## Regulatory frame
Instrucción 7/2011 JEC (BOE-A-2011-14814): Congreso, Senado, Parlamento Europeo.
- Parties without representation: 0.1% of census per constituency; electors' groups 1%; EP: 15,000 electors.
- Mandatory data: name, surnames, DNI/NIE, birth date, signature. Signer must be registered in the constituency.
- Each aval is one XML file, XMLDSig + XAdES (ETSI TS 101 903) **enveloped**, signing node `avalcandidatura`.
- File name `NIF.xml`; NIF must match the certificate and the `<ID>` field.
- Delivery: one ZIP per election, constituency and candidacy: `EEEEEE.CCCCCC.PPPPPP.zip`
  (e.g. `CONGRESO Y SENADO.Almería.Candidatura1.zip`). `elecciones` values: `CONGRESO`, `SENADO`,
  `CONGRESO Y SENADO`. Island provinces: Congreso and Senado have different constituencies -> two ZIPs
  (Senado per island / island group).
- Candidacy name: max 100 chars, identical in XML and ZIP.
- Signature must carry a seal/timestamp communicated to the Junta. We do NOT use a TSA: the server records
  receipt+validation time per aval and documents it (ADR 0003). **Not verified that the Junta accepts this.**
- Certificates: those recognised by the INE electronic office.
- A signer may endorse one candidacy per process; otherwise the Census Office annuls all. JEC recommends
  collecting 10–20% extra.

### UNVERIFIED requirements — stop and ask the owner, never invent
1. **Official XSD.** Published in the BOE only as images (`14814_002.png` … `14814_007.png`). Create
   `spec/` only from a transcription verified by the owner, with an origin note. Until then: clearly marked
   placeholder and schema-validation tests that **fail explicitly**. Schema and enumerations must be
   versionable per election call.
2. **Exact constituency values** (INE nomenclature: `Coruña, A`, `Balears, Illes`, `Araba/Álava`,
   `Valencia/València`…). XML and ZIP values come from the XSD; visible labels may be translated, the
   submitted value may not.
3. **Legal basis.** The Instruction cites Ley 59/2003 (repealed); current frame is eIDAS + Ley 6/2020.
   Document it; it does not change the required format.
4. List of CAs recognised by the INE (input for the curated root list).
5. Whether the Local Zone Madrid at OVH offers classic VPS (ADR 0005).

## Architecture decisions (see `docs/adr/`)
- Backend Python (FastAPI or equivalent) + PostgreSQL, Docker Compose, deployed from GitHub Actions to an OVH
  host in Madrid. Personal OVH account, separate from any company.
- **Frontend: static, served from the same host as the backend (ADR 0008)**, not GitHub Pages, because Pages
  cannot set HTTP security headers and adds a third-party TLS terminator. Configurable per candidacy via a
  config file; multi-language; zero runtime external dependencies.
- Single-phase signature: backend generates the aval XML, browser hands it to AutoFirma (local WebSocket),
  signed XML returns, backend checks integrity, signature, certificate, revocation, NIF and schema before
  accepting. Abstract signature layer so three-phase signing and Cl@ve Firma can be added later.
- Curated, versioned, auditable list of root CAs in the repo (Policia/DNIe, FNMT, ACCV, Izenpe, AOC,
  Camerfirma, Firmaprofesional, ANF…) instead of processing EU trusted lists.
- No Cloudflare or any TLS-terminating intermediary. DNS at a European provider.
- Encrypted backups in OVH Object Storage in a French region.
- One isolated instance per candidacy (own database and encryption key) on the same host.

### Signature parameters (from analysis of real platforms)
`format=XAdES Enveloped`, `nodeToSign=avalcandidatura`, `insertEnvelopedSignatureOnNodeByXPath`, digest
SHA-256 or stronger, `includeOnlySignningCertificate=true`. Never sign the whole document instead of the node.

### Browser hardening
Strict CSP with own resources only (the signature page additionally allows inline styles, ADR 0009), `frame-ancestors 'none'`, `connect-src` limited to the backend and
AutoFirma's local socket, `frame-src afirma:`, `X-Frame-Options: DENY`, `nosniff`,
`Referrer-Policy: no-referrer`, HSTS, `Cache-Control: no-store` on data responses, no server version
exposure. No analytics, external translators, Google Fonts or CDNs on aval pages. No non-essential cookies.

## Functional scope (29N)
Per-candidacy config: exact official name, elections and constituencies (full, including islands for
Senado), target per constituency, collection window (not before the call), visual identity, languages,
privacy/contact texts, optional in-person alternative, optional public counter (must state it shows avales
received and validated by the platform, not validated by the census).
Signer flow: data -> declarations (census registration, not having endorsed another candidacy with nullity
warning, explicit consent) -> AutoFirma -> server validation -> receipt with no unnecessary data.
Candidacy side: counts per constituency, incidents, ZIP export in Instruction format, document for the Junta
describing signature, verification and timestamp. Languages: ca, es, eu, gl, en (translation files, no text
in code).

## Data protection and security
An aval reveals political opinion (GDPR art. 9): explicit consent + LOREG. Each candidacy is controller; the
operator is processor. Templates in `docs/`: processor contract, information layer, DPIA. Encryption at rest
with a per-candidacy key, access log, strong auth (at least TOTP) for admins. Retention until the end of the
process and possible appeals, then final export and verifiable automatic deletion.
**Pending decision, do NOT implement:** detecting duplicate avales across candidacies. Default: total
isolation plus a clear warning to the signer.

## Working on Windows and Mac
Owner uses both indistinguishably; nothing may depend on local-only state.
- `.gitattributes` forces LF. No absolute paths. Scripts run inside containers or are cross-platform
  (Python, not bash/PowerShell, for project tooling).
- Config via environment variables and versioned files. **No secret or real certificate in the repo**
  (`.gitignore` blocks key/cert extensions; CI runs secret scanning). Real test certs live outside the repo.
- Python venv in `.venv/`; pin dependencies; same commands on both OSes.

## Working rules
- Small descriptive commits; no phase is closed without tests.
- When a legal/format requirement is unverified: stop and ask.
- Tests required eventually: XSD validation, node integrity, signature parameters, rejection of unsupported
  certs, revocation, NIF extraction per issuer, ZIP names (incl. islands), candidacy isolation, security
  headers. CI on GitHub Actions: tests, dependency analysis, deploy.
- WCAG 2.2 AA, mobile-friendly UI (even though mobile signing is out of scope for now).
- Licence: proposed EUPL-1.2 (ADR 0007), **not committed as `LICENSE` until the owner confirms.**
- Plan after PoC, if we continue: (a) skeleton, CI, (b) XML generation/validation, (c) end-to-end signature
  and validation, (d) ZIP export + Junta document, (e) per-candidacy config + i18n, (f) security, data
  protection, OVH deployment. Always prioritise what is needed for 16–17 Oct.
