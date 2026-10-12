# 0002 — Single-phase signature

Status: Accepted.

## Decision
The backend generates the aval XML; the browser passes it to AutoFirma via the local WebSocket; the signed XML
returns to the backend, which checks integrity, signature, certificate, revocation, NIF and schema before
accepting it.

## Parameters
Verified in the PoC (2026-10-12, AutoFirma latest, Chrome/Windows): `format=XAdES Enveloped`,
`nodeToSign=<value of the node's Id attribute>` (the element name fails with `java.lang.Exception`),
`insertEnvelopedSignatureOnNodeByXPath=/oce`, `includeOnlySignningCertificate=true`,
`avoidEnvelopedTransformWhenSigningNode=true`, `avoidXpathExtraTransformsOnEnveloped=true`,
`referencesDigestMethod=http://www.w3.org/2001/04/xmlenc#sha256`; algorithm `SHA256withRSA`. The server
generates the node `Id` (`avalcandidatura-<uuid>`). Result: a single C14N transform and SHA-256 digests, as in
the BOE example.

## Consequences
The signature layer is abstract so that three-phase signing (official server in a container or a Python
reimplementation) and Cl@ve Firma can be added later. Safari support is unverified (see PoC): it may force
the intermediate storage/retrieve servers.
