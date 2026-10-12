# PoC report — Phase 0 (DRAFT, day 1 results)

Date: 2026-10-12. Status: **items 1 (Chrome/Windows), 2, 3 (idCAT only), 4, 7 done; Firefox/Safari/macOS, other
issuers and mobile pending.** No recommendation is final until the pending items are in. The decision between
continuing with Python or switching approach is the owner's.

Environment: Windows 11, Chrome 154, AutoFirma latest (AutoScript 1.10.1), Python 3.14.2, SignXML 5.1.0,
pyhanko-certvalidator 0.32.1, lxml 6.1.3, cryptography 50.0.2. Real certificate: owner's idCAT software
certificate (issuer EC-Ciutadania, from the Windows store). No DNIe or FNMT available.

## Summary

| # | Item | Result |
|---|------|--------|
| 1 | Static page + AutoFirma, XAdES enveloped over `avalcandidatura`, strict CSP | **Works on Chrome/Windows** with 1 CSP finding. Firefox, Safari, macOS pending |
| 2 | XAdES verification in Python | **Works with 2 workarounds** (library incompatibilities, below) |
| 3 | Certificate validation | **Works** for idCAT: chain to EC-ACC, live OCSP (`require` mode), policy, QcType, NIF. Rejections tested with synthetic certs. NIF for DNIe/FNMT **unverified** |
| 4 | Integrity of the node | **Works** (byte-identical canonical form of the node; signed-node == stored-node) |
| 5 | Real certificates | idCAT only |
| 6 | Mobile | Not attempted (optional) |
| 7 | Resources | Negligible CPU; no Docker on this machine, no VPS test |

## 1. Signature from the static page

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

- Firefox and Chrome on macOS, Safari: signature flow, `frame-src afirma:`, WebSocket certificate trust (day 2).
- Verify the production CSP decision about `style-src` (above).
- DNIe, FNMT: NIF extraction and policy OIDs (needs certificates; the owner has none for the PoC).
- Mobile storage/retrieve servers (optional, not attempted).
- Docker/VPS resource test.
- Check the curated roots' fingerprints against official sources; verify the idCAT root fetched over HTTP.

## Preliminary recommendation (not a decision)

Items 1–4 work in Python for the idCAT path on Chrome/Windows, but not out of the box: two SignXML/libxml2
incompatibilities needed workarounds. If macOS/Safari tests pass and the C14N workaround is accepted (or replaced
by libxmlsec1), continuing with Python is viable. The fallback (DSS / official @firma server as containers) stays
available if the workarounds prove fragile with other issuers.
