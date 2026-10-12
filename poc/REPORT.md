# PoC report — Phase 0 (DRAFT, day 1 results)

Date: 2026-10-12. Status: **items 1 (Chrome/Windows, Firefox/Windows, Chrome and Safari/macOS), 2, 3 (idCAT only), 4, 7 done; Firefox/macOS,
other issuers and mobile pending.** No recommendation is final until the pending items are in. The decision between
continuing with Python or switching approach is the owner's.

Environment: Windows 11, Chrome 154, AutoFirma latest (AutoScript 1.10.1), Python 3.14.2, SignXML 5.1.0,
pyhanko-certvalidator 0.32.1, lxml 6.1.3, cryptography 50.0.2. Real certificate: owner's idCAT software
certificate (issuer EC-Ciutadania, from the Windows store). No DNIe or FNMT available.

## Summary

| # | Item | Result |
|---|------|--------|
| 1 | Static page + AutoFirma, XAdES enveloped over `avalcandidatura`, strict CSP | **Works on Chrome/Windows, Firefox/Windows, Chrome/macOS and Safari/macOS** with 1 CSP finding. Firefox on macOS pending |
| 2 | XAdES verification in Python | **Works with 2 workarounds** (library incompatibilities, below) |
| 3 | Certificate validation | **Works** for idCAT: chain to EC-ACC, live OCSP (`require` mode), policy, QcType, NIF. Rejections tested with synthetic certs. NIF for DNIe/FNMT **unverified** |
| 4 | Integrity of the node | **Works** (byte-identical canonical form of the node; signed-node == stored-node) |
| 5 | Real certificates | idCAT (accepted) and FNMT representative (rejected as expected). DNIe and FNMT natural person: none |
| 6 | Mobile | Not attempted (optional) |
| 7 | Resources | Negligible CPU; no Docker on this machine, no VPS test |

## 1. Signature from the static page

**Recommended parameters (variant C, verified 2026-10-12 09:14 on Chrome/Windows, idCAT, `accepted: true`):**
`format=XAdES Enveloped`, `nodeToSign=<Id of the node>`, `insertEnvelopedSignatureOnNodeByXPath=/oce`,
`includeOnlySignningCertificate=true`, `avoidEnvelopedTransformWhenSigningNode=true`,
`avoidXpathExtraTransformsOnEnveloped=true`, `referencesDigestMethod=http://www.w3.org/2001/04/xmlenc#sha256`,
algorithm `SHA256withRSA`, format `XAdES`. This reproduces the shape of the BOE example: `Id` on the node,
`URI="#<Id>"`, a **single C14N transform** (no enveloped, no XPath), **SHA-256 digests** on all three
references and on the `SigningCertificate`, `ds:Signature` as sibling of `avalcandidatura`. With C, the XPath
transform and its redundant `xmlns:ds` are gone, so **plain SignXML verifies the signature**; the only remaining
workaround is `validate_schema=False` (39-digit serial number). The namespace rebuild (`strip_redundant_ns`) and
the unicode `_tostring` are no longer needed with the official, unaccented XSD, and are kept only as a
defensive fallback. (`nodeToSign=avalcandidatura` without an `Id` still fails.)

**End-to-end live run (Chrome 154/Windows, 2026-10-12 09:02):** page -> server-generated XML -> AutoFirma
(certificate from the Windows store) -> server: all checks passed (`accepted: true`), SigningTime skew 0 s,
live OCSP in `require` mode. Variant A failed again with the same error, confirming the `Id` requirement.

Parameters that work (variant B): `format=XAdES Enveloped`, `nodeToSign=<Id of the node>`,
`insertEnvelopedSignatureOnNodeByXPath=/oce`, `includeOnlySignningCertificate=true`, algorithm `SHA256withRSA`,
format `XAdES`.

- **`nodeToSign` must be the value of the node's `Id` attribute.** With `nodeToSign=avalcandidatura` and no `Id`
  on the node, AutoFirma fails with `java.lang.Exception: undefined`. The server therefore generates
  `Id="avalcandidatura-<uuid>"` on the node (the BOE example also has an `Id` on the node).
- What AutoFirma produced: `ds:Signature` as sibling of `avalcandidatura` under `oce`; C14N 1.0 inclusive;
  `rsa-sha256`; **digests SHA-512**; three references (node, `SignedProperties`, `KeyInfo`); the node reference
  has transforms enveloped + C14N + XPath `not(ancestor-or-self::ds:Signature)`; XAdES 1.3.2 namespace;
  `SigningTime` with offset; `SigningCertificate` (SHA-512 digest + `IssuerSerial`); `DataObjectFormat` with
  `urn:oid:1.2.840.10003.5.109.10`; only the signer certificate in `KeyInfo` (no chain). The node keeps only the
  `Id` attribute (no `MimeType`/`Encoding` in this AutoFirma version, unlike the 2011 BOE example).
- **CSP finding:** under the strict CSP (`style-src 'self'`) the flow works, but AutoScript injects a `<style>`
  for its dialogs and the browser blocks it (`style-src-elem` violation). Dialogs (AutoFirma not installed,
  errors) would render unstyled. Options: allow `style-src 'unsafe-inline'` (low risk, but a relaxation),
  or patch the vendored script, or replace its dialogs with our own UI. **Owner decision.**
  Not yet tested: `frame-src afirma:` (Firefox/Safari open AutoFirma through an iframe; Chrome navigates),
  and the iframe's `style` attribute (`style-src-attr`).
- **Firefox 140.0.4 / Windows (2026-10-12 09:08):** works. AutoFirma opened (iframe path), the signature came back
  and the server verified it (signature, XAdES, chain, live OCSP all OK; signed with the FNMT representative
  certificate, so the final verdict was a rejection by profile, as intended). **No `frame-src` violation:
  `frame-src afirma:` is sufficient.** Two CSP violations, both from AutoScript, neither blocking the flow:
  `style-src-elem` (injected `<style>` for the dialogs) and `style-src-attr` (the hidden iframe's `style`
  attribute). Chrome shows only the first.
- **Chrome 154 / macOS (Darwin 25.6) / AutoFirma 1.9 (2026-10-12 09:37):** works with variant C and the idCAT
  certificate from the login Keychain. AutoScript 1.10.1 (vendored) talked to AutoFirma 1.9 without problems, so
  the two versions are compatible. Server verdict `accepted: true` (integrity, schema, signature, XAdES, chain with
  live OCSP, profile, NIF); signing time skew 0 s; about 13 s from calling AutoFirma to the signed XML (user
  confirmation included). A first run with the example NIF in the form was correctly rejected only for
  `certificate NIF does not match <id>`. Python 3.11.3, same pinned requirements, 167 tests pass.
  Observation: on this machine plain `XAdESVerifier().verify()` also verifies the variant C signature **without**
  `validate_schema=False` (the Windows run needed it for the 39-digit serial). Same SignXML/lxml/libxml2 versions
  as reported for Windows; the cause of the difference was not investigated, so keep the workaround.
- **Safari 26.6.2 / macOS / AutoFirma 1.9 (2026-10-12 09:40):** works with variant C and the idCAT certificate,
  `accepted: true`, skew 1 s, about 15 s from calling AutoFirma to the signed XML (user confirmation included). The
  page log shows **no CSP violation** under the `style-inline` CSP (ADR 0009), so `frame-src afirma:` is enough here
  too. Not verified: whether Safari used the WebSocket or the intermediate-server path (the page log does not say; the
  flow worked either way, and the signed XML came back in the same page).
- **CSP options for styles** (**decided 2026-10-12: option (a), ADR 0009**): (a) `style-src 'self' 'unsafe-inline'` on the signature
  page only: the risk is low while `script-src 'self'` holds and there is no inline script; (b) patch the vendored
  script (nonce on the injected style, class instead of the style attribute) at the cost of maintaining a fork;
  (c) our own error UI and disabling the dialogs. Suggestion for 16–17 Oct: (a), revisit with (b) after the
  election.
- AutoScript uses `wss://127.0.0.1` on desktop browsers that support WebSocket and falls back to the
  intermediate servers only for iOS/Android, forced mode, or Safari 10. So **modern Safari is expected to use
  the WebSocket path**; to be confirmed on macOS.
- `autoscript.js` is vendored (`poc/web/vendor/`). Upstream is dual-licensed GPLv2/EUPL v1.1: licence
  compatibility with ADR 0007 must be reviewed.

## 2. XAdES verification with SignXML — works, with workarounds

Plain `XAdESVerifier().verify()` **fails** on the real AutoFirma output. Causes found and worked around in
`poc/server/checks.py`:

1. **Schema validation of `X509SerialNumber`.** The idCAT serial has 39 digits and libxml2's `xs:integer`
   rejects it (`DocumentInvalid`). Workaround: `validate_schema=False`; we substitute our own structural checks
   (single Signature, single certificate, references, XAdES properties).
2. **C14N 1.0 mismatch in `SignedInfo`.** AutoFirma emits a redundant `xmlns:ds` on `<ds:XPath>`. libxml2 keeps it
   when canonicalizing, the C14N 1.0 spec drops it, so the digest differs and verification raises
   `InvalidSignature`. Workaround: rebuild the tree without redundant namespace declarations before
   verification (`strip_redundant_ns`). Longer-term options: python-xmlsec (libxmlsec1), or a vetted
   C14N implementation.
3. **Non-ASCII element names.** SignXML re-serializes with an ASCII encoding, which cannot represent
   `<circunscripción>` (owner's decision to use the accented name). Workaround: subclass overriding
   `_tostring` to use unicode. Risk to flag: more tooling may choke on a non-ASCII element name.

With these, SignXML verifies the three references, and we check that the node covered by the signature is the
node we store (defends against signature wrapping). Checked: XAdES `SigningTime` (skew), `SigningCertificate`
digest, `QualifyingProperties/@Target`, single signature, single `avalcandidatura`.

## 3. Certificate validation

- Chain: end-entity -> EC-Ciutadania (intermediate) -> EC-ACC (root). Intermediate downloaded from the AIA URL;
  root from `epscd.aoc.cat`; the root's SHA-1 thumbprint matches the one in the Windows trusted-root store, and
  the intermediate verifies against it. **The root was fetched over plain HTTP: its fingerprint must be checked
  against an official AOC source before the curated list is accepted** (the Windows-store match is only a
  consistency check). The root has a negative serial number: `cryptography` warns it will reject such
  certificates in the future (asn1crypto, used by certvalidator, still parses it).
- Revocation: live OCSP, ~370 ms median. **Important:** with `revocation_mode="hard-fail"` a certificate that
  declares no OCSP/CRL endpoint is accepted without any revocation check. We use `require`, which also demands
  revocation data for the intermediate (works with idCAT: both have OCSP), and we additionally reject end-entity
  certificates with no OCSP/CRL endpoint.
- Classification of the idCAT certificate: policy `1.3.6.1.4.1.15096.1.3.2.86.2` (idCAT Certificat), QCStatements
  (QcCompliance, QcType `esign`, retention 15 years, PDS), keyUsage digitalSignature + contentCommitment, no
  organization/organizationIdentifier.
- **NIF location, idCAT:** subject `serialNumber` = `IDCES-<NIF>`. For DNIe, FNMT and the rest this is
  **unverified**: no certificate available. Do not assume the same layout.
- **FNMT representative certificate (real, owner's):** the full pipeline ran on it. Signature, XAdES and chain are
  valid (AC Representación -> AC RAIZ FNMT-RCM, live OCSP at `ocsprep.cert.fnmt.es`; the root's SHA-1 matches the
  Windows store; the root expires 2030-01-01). What it shows about the FNMT layout:
  - subject `serialNumber` = `IDCES-<NIF of the representative>`, i.e. **the same NIF layout as idCAT, and
    QcType `esign` too: a representative certificate looks like a natural person at first sight.**
  - It is told apart by `organizationName`, `organizationIdentifier` (2.5.4.97 = `VATES-<CIF>`), the registry
    description attribute (2.5.4.13), the FNMT SAN attributes (1.3.6.1.4.1.5734.1.x) and the policy OID
    `1.3.6.1.4.1.5734.3.11.1` ("representante de p. jurídica"). keyUsage also includes keyEncipherment.
  - Outcome: rejected, because AC Representación has no profile in the curated list. A test also proves that
    even if that issuer were admitted, the organization attributes and the unaccepted policy reject it.
  - The natural-person FNMT policy OID and issuer (AC FNMT Usuarios) are **not verified**: no certificate.
  - An early bug surfaced here: an unknown issuer made the pipeline raise (HTTP 500). Now any unexpected error
    becomes a rejection.
- **FNMT natural-person certificate (real, owner's, issued 2023, EXPIRED 2026-07-20; read from the macOS Keychain,
  not signed with):** issuer `AC FNMT Usuarios` (intermediate under AC RAIZ FNMT-RCM, SHA-1
  `80:8B:72:E4:3B:57:4C:F5:87:7C:B8:41:A8:DF:88:39:6D:38:AB:94`, taken from the Keychain, **not verified against an
  official FNMT source**). Layout: subject `serialNumber` = `IDCES-<NIF>` (same as idCAT and the FNMT
  representative certificate), `GN`/`SN` split, **no** organization or organizationIdentifier; SAN dirName with FNMT
  attributes 1.3.6.1.4.1.5734.1.1-4 (name, surnames, NIF); policy **`1.3.6.1.4.1.5734.3.10.1`** ("certificado
  cualificado de firma electrónica", persona física) plus `0.4.0.194112.1.0` (QCP-n); QcType `esign`, QcCompliance;
  keyUsage digitalSignature + nonRepudiation + keyEncipherment; OCSP `ocspusu.cert.fnmt.es`. With a temporary
  profile (policy above, same NIF regex) `classify_certificate` accepts the profile and extracts the NIF, and
  `check_certificate` against FNMT root + intermediate rejects it with `ExpiredError` (a real expired case). The profile
  and the intermediate are now in `PROFILES` / `trust/intermediates/ac-fnmt-usuarios.crt` (tests added), but the
  **intermediate's fingerprint is still unchecked against an official FNMT source**, and one certificate is evidence
  for the layout, not for the whole issuer; DNIe stays unverified. Not tested: an actual signature with it (AutoFirma may hide expired certificates).
- Rejections verified with synthetic certificates (`poc/tests`): expired, revoked (CRL), seal (QcType `eseal` and
  organizationIdentifier), legal person / representative (organization attributes), unaccepted policy, missing
  nonRepudiation, no revocation endpoint, unknown issuer. Real revoked/expired certificates were not tested.

## 4. Integrity

The server keeps the generated XML. On receipt, the canonical form of `avalcandidatura` (ignoring the signature)
must be identical to the stored one, and the node covered by the signature must be the one stored. Tampering with
`id`, candidacy name or constituency, adding a second node, removing the signature and XML entities are all
rejected in tests.

## 7. Resources

Per aval, the crypto checks (integrity, schema, signature, XAdES, profile) cost about 2.4 ms CPU; the OCSP call
adds ~370 ms of network wait (async). A worker process holding the libraries uses about 65 MB RSS. Even with
FastAPI and PostgreSQL this fits the smallest VPS by a wide margin. Not measured: Docker limits (Docker is not
installed on this machine) and a real VPS. Mitigate OCSP load with per-certificate caching of responses.

## Findings on the official format (see `spec-draft/README.md`)

BOE inconsistency `circunscripcion`/`circunscripción` (owner chose the accented name), 4th election value
`PARLAMENTO EUROPEO`, tight field limits (name 20, surnames 25), `Id` attribute on the signed node and the
`ds:Signature` sibling are outside the draft XSD (the server validates the unsigned structure), and the 2011
example uses SHA-1 (acceptance of SHA-256/512 by the Oficina del Censo unverified).

## Pending

- Firefox on macOS (Chrome and Safari done): signature flow. It may read certificates from its own NSS store rather than the Keychain.
- Verify the production CSP decision about `style-src` (above).
- DNIe and FNMT natural person: NIF extraction and policy OIDs (needs certificates). The owner's Mac Keychain holds
  an FNMT natural-person certificate that has **expired**: usable for the layout/OID and as a real expired case.
- Mobile storage/retrieve servers (optional, not attempted).
- Docker/VPS resource test.
- Check the curated roots' and intermediates' fingerprints (incl. AC FNMT Usuarios, taken from the Mac Keychain) against official sources; verify the idCAT root fetched over HTTP.

## Preliminary recommendation (not a decision)

Items 1–4 work in Python for the idCAT path on Chrome/Windows, but not out of the box: two SignXML/libxml2
incompatibilities needed workarounds. If macOS/Safari tests pass and the C14N workaround is accepted (or replaced
by libxmlsec1), continuing with Python is viable. The fallback (DSS / official @firma server as containers) stays
available if the workarounds prove fragile with other issuers.
