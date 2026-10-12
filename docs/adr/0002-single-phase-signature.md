# 0002 — Single-phase signature

Status: Accepted.

## Decision
The backend generates the aval XML; the browser passes it to AutoFirma via the local WebSocket; the signed XML
returns to the backend, which checks integrity, signature, certificate, revocation, NIF and schema before
accepting it.

## Parameters
`format=XAdES Enveloped`, `nodeToSign=avalcandidatura`, `insertEnvelopedSignatureOnNodeByXPath`, SHA-256 or
stronger, `includeOnlySignningCertificate=true`.

## Consequences
The signature layer is abstract so that three-phase signing (official server in a container or a Python
reimplementation) and Cl@ve Firma can be added later. Safari support is unverified (see PoC): it may force
the intermediate storage/retrieve servers.
