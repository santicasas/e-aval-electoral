# PoC report — Phase 0 (final)

Date: 2026-10-12. Scope: can the whole aval flow be done with a Python backend, without Java of our own?
**This report presents results and options. The decision to continue or to change approach is the owner's.**

Evidence lives in the repository: PoC code in `poc/`, the production-oriented core library in `backend/`, the official
XSD in `spec/`, decisions in `docs/adr/`. At the time of writing `python -m pytest backend poc/tests` gives
**192 passed, 1 skipped** (the skipped one needs a signature made with the FNMT representative certificate, which
is kept out of the repository).

Real material used: the owner's software idCAT certificate (issuer EC-Ciutadania), an FNMT representative
certificate, and one **expired** FNMT natural-person certificate (read from the macOS Keychain, not signed with).
No DNIe. No revoked real certificate.

## 1. Verdict at a glance

| # | Item | Result | Confidence |
|---|------|--------|------------|
| 1 | Signature from a static page, XAdES enveloped over `avalcandidatura`, strict CSP | **Works** on Chrome and Firefox (Windows) and Chrome and Safari (macOS). Firefox/macOS not tested | High for what was tested |
| 2 | XAdES verification in Python | **Works** with SignXML; with the final parameters only one workaround remains (section 4) | High |
| 3 | Certificate validation (chain, validity, revocation, NIF, rejections) | **Works for idCAT**, live OCSP; rejections proven with real (representative, expired) and synthetic certificates | High for idCAT; **low for every other issuer** |
| 4 | Integrity of the node | **Works** | High |
| 5 | Real certificates (DNIe, FNMT, idCAT) | idCAT accepted; FNMT representative rejected as intended; FNMT natural person: layout read, no signature; **DNIe: nothing** | Partial |
| 6 | Mobile | **Does not work without a three-phase signature server.** Out of scope for the 29N | High |
| 7 | Resources | ~2.4 ms CPU per aval plus ~370 ms OCSP wait; ~65 MB RSS | Medium (no Docker, no VPS) |

Browser matrix (all 2026-10-12, owner's idCAT certificate unless noted):

| Platform | AutoFirma | Result | CSP violations (with `style-src 'self'`) |
|---|---|---|---|
| Windows 11, Chrome 154 | latest (version not recorded) | accepted, variants B and C | `style-src-elem` |
| Windows 11, Firefox 140.0.4 | latest (version not recorded) | works (signed with the FNMT representative certificate, rejected by profile, as intended) | `style-src-elem`, `style-src-attr` |
| macOS, Chrome 154 | 1.9 | accepted, variant C | not recorded |
| macOS, Safari 26.6.2 | 1.9 | accepted, variant C | none (with the ADR 0009 CSP) |
| macOS, Firefox | 1.9 | **not tested** (may use its own NSS store, not the Keychain) | |
| iPhone, Safari 26.6.1 / Autofirma App | n/a | **fails**: needs a three-phase server (section 7) | |

## 2. Recommendation (not a decision)

**Continue with Python.** The decision criterion of the brief (items 1 to 5 work) is met for what could be tested:
the page signs, the Python backend verifies the real AutoFirma output, validates the chain with live OCSP, extracts
the NIF, rejects the wrong certificate types and detects altered nodes. No finding so far needed Java.

Conditions, each of which could change the recommendation:
1. **Other issuers.** Everything certified was seen with ONE issuer. The NIF location, the policy OIDs and the
   AutoFirma output must be checked with a DNIe and an FNMT natural-person certificate before real use. If either
   breaks the SignXML/certvalidator path in a way that is not a quick fix, the fallback in the brief applies.
2. **Acceptance by the Oficina del Censo.** Unverified: SHA-256 digests (the BOE example is SHA-1), an `Id`
   attribute on `avalcandidatura` (the BOE's own signed example has it, the XSD forbids it), and a server-side
   reception time instead of a TSA timestamp (ADR 0003). Ask the Junta, ideally with a sample file.
3. **Trust list provenance.** Roots and intermediates were fetched over plain HTTP and compared with the Windows
   certificate store, never with an official page. They must be checked against official sources before the
   curated list is accepted (section 6).

Options, so the choice is yours:

| Option | What it is | For | Against |
|---|---|---|---|
| **A. Continue with Python (recommended)** | The stack proven here, extended | No Java of our own; small footprint; one language; the core library already exists and is tested | Two library incompatibilities to maintain (section 4); only one issuer verified |
| B. Python plus a second opinion | A, plus the official DSS or @firma validator in a closed container used as a cross-check on the Junta document | Independent verification of the same avals | Java in the deployment; more resources; more to operate for little gain before 29N |
| C. Change approach | Validation with DSS or the official three-phase server as closed containers | Mature validation code | Not justified by any result; costs time we do not have; mobile still needs custom work |

## 3. What this means for 16 or 17 October

Today is 12 October; the PoC decision is due by 14 October. These are my estimates, not measurements.

Already built and tested: official XSD and derived signed-document schema (`spec/`), the library that generates,
normalises, validates and zips avals (`backend/`, 148 tests), the verification pipeline (`poc/server/checks.py`,
to be moved into `backend/`), 10 ADRs.

Not built: the backend API and database, administrator authentication (TOTP), per-candidacy configuration and
multi-language, the production frontend, the document for the Junta, encryption at rest, backups, CI, and the OVH
deployment. **The OVH instance, a domain and DNS do not exist yet, and the Madrid Local Zone offer is unverified
(ADR 0005).** Reaching production with everything by 16 or 17 October is unlikely; a realistic cut is:

| Day | Work |
|---|---|
| 14 Oct | Backend skeleton, database, API around the core library, productise the verification pipeline, CI with tests and secret scanning |
| 15 Oct | Administrator login with TOTP, per-candidacy configuration, ZIP export endpoint, Junta document, production page in Catalan and Spanish |
| 16 Oct | Security headers, encryption at rest, backups, deployment on the VPS, DNS and TLS, smoke test with real certificates |
| 17 Oct | Buffer, hardening, privacy documents |

Postponed: Basque, Galician and English; public counter; orchestration of several instances (one instance, one
candidacy); mobile; data-protection templates can be written in parallel without blocking.

Needs from the owner: the OVH account and instance (or a decision to start elsewhere), a domain, the candidacy's
exact official name, the licence decision (ADR 0007), the trust-list verification, and the Junta questions below.

## 4. Library findings and workarounds

Final AutoFirma parameters (ADR 0002), verified: `format=XAdES Enveloped`, `nodeToSign=<value of the node's Id>`,
`insertEnvelopedSignatureOnNodeByXPath=/oce`, `includeOnlySignningCertificate=true`,
`avoidEnvelopedTransformWhenSigningNode=true`, `avoidXpathExtraTransformsOnEnveloped=true`,
`referencesDigestMethod=http://www.w3.org/2001/04/xmlenc#sha256`, algorithm `SHA256withRSA`, format `XAdES`.
`nodeToSign=avalcandidatura` without an `Id` fails with `java.lang.Exception: undefined`, so the server generates
`Id="avalcandidatura-<uuid>"` after validating the document strictly. Result: `ds:Signature` as a sibling of the
node under `oce`, a single C14N transform, SHA-256 digests everywhere, XAdES 1.3.2, only the signer certificate in
`KeyInfo`: the shape of the BOE example.

- **Plain SignXML fails on the default AutoFirma output** (enveloped + C14N + XPath transforms, SHA-512): libxml2's
  C14N 1.0 keeps a redundant `xmlns:ds` that AutoFirma emits on `<ds:XPath>`, so `SignedInfo` no longer matches.
  The variant-C parameters remove the XPath transform and with it the problem. The namespace rebuild stays in the
  code as a fallback.
- **Remaining workaround:** `validate_schema=False` in SignXML, because libxml2's `xs:integer` can reject a 39-digit
  `X509SerialNumber` (idCAT), depending on the platform build (Windows rejected it, macOS did not). It must not
  depend on the platform, so it is always off. Our own structural checks replace it: one `Signature`, one
  certificate, the three references, the node covered by the signature equals the stored node (against signature
  wrapping), `SigningTime` skew, `SigningCertificate` digest, `QualifyingProperties/@Target`.
- SignXML serialises with an ASCII encoding, which breaks non-ASCII element names. Moot with the official
  unaccented `circunscripcion`.
- **`revocation_mode="hard-fail"` accepts a certificate that declares no OCSP/CRL endpoint without any revocation
  check.** The code uses `require` and also rejects end-entity certificates with no endpoint.
- `cryptography` warns that the AOC root EC-ACC has a negative serial number and will reject such certificates in
  a future release; asn1crypto (used by pyhanko-certvalidator) still parses it. Pin versions.
- Longer-term alternative if the C14N path proves fragile with other issuers: python-xmlsec (libxmlsec1).

## 5. Certificates

- **idCAT** (verified with a real signature): chain EC-Ciutadania to EC-ACC; policy `1.3.6.1.4.1.15096.1.3.2.86.2`;
  QcCompliance and QcType `esign`; keyUsage digitalSignature and contentCommitment; NIF in subject `serialNumber`
  as `IDCES-<NIF>`; OCSP `ocsp.aoc.cat`.
- **FNMT representative** (real signature, rejected as intended): chain AC Representación to AC RAIZ FNMT-RCM with
  live OCSP. It has the same `IDCES-<NIF>` and QcType `esign` as a natural person, so **the subject and QcType
  alone cannot tell it apart.** What does: `organizationName`, `organizationIdentifier` (2.5.4.97, `VATES-…`), the
  registry-description attribute (2.5.4.13), FNMT SAN attributes `1.3.6.1.4.1.5734.1.x` and policy
  `1.3.6.1.4.1.5734.3.11.1`. The curated list therefore must be per issuer and per policy.
- **FNMT natural person** (one expired certificate, layout only): `AC FNMT Usuarios`; `IDCES-<NIF>`; no organisation;
  policy `1.3.6.1.4.1.5734.3.10.1`; against the FNMT root and intermediate the pipeline rejects it with
  `ExpiredError`, a real expired case. The profile is in the PoC code. **One certificate is evidence of a layout,
  not of an issuer.**
- **DNIe:** nothing tested. Do not assume the same layout.
- Rejections proven with synthetic certificates in tests: expired, revoked (CRL), seal (QcType `eseal`), legal
  person, unaccepted policy, missing nonRepudiation, no revocation endpoint, unknown issuer. No real revoked
  certificate was available.

## 6. Unverified, untested, and open questions

Not verified (do not rely on these):
1. Fingerprints of EC-ACC, EC-Ciutadania, AC RAIZ FNMT-RCM, AC Representación and AC FNMT Usuarios against official
   sources (they match the Windows certificate store; the idCAT root was fetched over HTTP).
2. The list of CAs recognised by the INE electronic office (input for the curated list).
3. Whether the Oficina del Censo accepts SHA-256 digests, the `Id` attribute on the signed node, and the server-side
   reception time as the "marca de tiempo".
4. Whether it compares names (the default normalisation upper-cases and strips accents except Ñ and Ç, ADR 0010).
5. How to write `/` (and dots) in ZIP names; the default is `-`, pending the Junta (ADR 0010).
6. The OVH Madrid Local Zone offer for the VPS (ADR 0005).
7. The AutoFirma version used on Windows was not recorded.

Not tested: Firefox on macOS; DNIe; a signature with an FNMT natural-person certificate; the mobile three-phase flow;
Docker or a real VPS under limits; a real revoked certificate; load beyond a few signatures.

## 7. Mobile (iPhone)

Setup: iPhone (iOS 18.7, Safari 26.6.1) with the App Store «Autofirma App» holding the owner's idCAT certificate as
PKCS#12, the PoC reached over Tailscale with a Let's Encrypt certificate from `tailscale cert` (the host name is in
the public CT logs). A Python reimplementation of the official storage and retrieve servlets (22 tests) works.

1. The app **rejects the direct request** (operation data in the `afirma://` URL when under 2000 characters). The
   upload form requires lowering `MAX_LONG_GENERAL_URL` in a vendored `autoscript.js` (1000 works, 0 does not: the
   check runs twice). The upload form is also better for privacy: the direct form leaves the signer's name and NIF
   in a URL, unencrypted.
2. After downloading the operation, the app calls `POST <origin>/afirma-server-triphase-signer/SignatureService`
   (form, URL-safe base64): `op=pre`, `cop=sign`, `format=XAdES`, `algo=SHA256withRSA`, `cert`, `params`, `doc`.
   Without it the app fails with «Error HTTP al realizar la operación de prefirma». **On iOS XAdES is signed in
   three phases**, so a mobile signature needs a three-phase service (the official one, Java, as a closed container,
   or a Python reimplementation, about one to two days plus tests) and a patched AutoScript. The server then sees
   the document and the certificate.
3. Returning to Safari by hand lets the page resume polling, so the feared page suspension did not block the flow.

**Out of scope for 29N.** A later phase; ADR 0002 keeps the signature layer abstract for it.

## 8. Resources

Per aval the crypto checks cost about 2.4 ms CPU; live OCSP adds about 370 ms of asynchronous network wait; a worker
holding the libraries uses about 65 MB RSS. With FastAPI and PostgreSQL this fits the smallest VPS by a wide margin.
Cache OCSP responses per certificate to limit calls to the CA.

## 9. Findings on the official format and decisions taken during the PoC

- The official XSD (`spec/generales-2026/`) uses `circunscripcion` without accent, four values for `elecciones`
  (the fourth is `PARLAMENTO EUROPEO`), 63 constituencies, name 20 and surname 25 characters, `id` 9, candidacy name
  100. It does not validate the signed document (extra attributes, `ds:Signature` in `oce`): validation is in two
  phases, with a derived schema generated from the official one.
- The browser's CSP allows inline styles on the signature page only (ADR 0009), because AutoScript injects a
  `<style>` and a `style` attribute; `frame-src afirma:` was enough on Firefox and Safari.
- `autoscript.js` is vendored. Upstream is dual-licensed (GPLv2 / EUPL v1.1): its compatibility with the platform
  licence must be reviewed before release.
- Defaults for the open questions (ADR 0010): upper case without accents, truncate with a notice, `-` for `/`,
  two avals in insular provinces for both chambers, minimum age 18 on election day, NIF types K, L and M rejected.

## 10. Questions for the Junta Electoral

1. Are SHA-256 digests and an `Id` attribute on `avalcandidatura` accepted by the Oficina del Censo?
2. Is the platform's reception time acceptable as the "marca de tiempo", or is a qualified timestamp required?
3. How are `/` and `.` to be written in ZIP names (`Araba/Álava`, candidacy names with dots)?
4. Are names compared with the census, and how (case, accents)?
5. For an insular province with both chambers, are two avals, one per chamber, the expected form?
