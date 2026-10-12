"""PoC verification pipeline. Each check reports pass/fail plus detail, so results go straight into the PoC report.

Checks: XML safety, node integrity, schema, XMLDSig+XAdES signature (SignXML), XAdES properties, certificate
chain + revocation (pyhanko-certvalidator), certificate classification and NIF extraction.

Personal data is never put in the report: the NIF is only compared, never echoed.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import re
from pathlib import Path

from asn1crypto import core as acore
from asn1crypto import x509 as ax509
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID
from lxml import etree
from pyhanko_certvalidator import CertificateValidator, ValidationContext
from pyhanko_certvalidator.fetchers.aiohttp_fetchers import AIOHttpFetcherBackend
from signxml import xades

from . import avalxml

TRUST = Path(__file__).resolve().parent.parent / "trust"
DS = "{http://www.w3.org/2000/09/xmldsig#}"
XADES = "{http://uri.etsi.org/01903/v1.3.2#}"
MAX_BYTES = 256 * 1024

# --- Issuer profiles (the curated list, PoC version). Only idCAT is verified with a real certificate. ---
PROFILES = {
    "EC-Ciutadania": {
        # CN of the issuing CA -> accepted natural-person policy OIDs and where the NIF lives.
        "policies": {"1.3.6.1.4.1.15096.1.3.2.86.2"},  # "idCAT Certificat" (seen in the owner's certificate)
        "nif_regex": re.compile(r"^IDCES-([0-9A-Z]{9})$"),  # subject serialNumber
    },
}
QC_STATEMENTS_OID = "1.3.6.1.5.5.7.1.3"
QC_TYPE_OID = "0.4.0.1862.1.6"
QC_TYPES = {"0.4.0.1862.1.6.1": "esign", "0.4.0.1862.1.6.2": "eseal", "0.4.0.1862.1.6.3": "web"}
ORGANIZATION_IDENTIFIER_OID = "2.5.4.97"


def _load_trust() -> tuple[list[ax509.Certificate], list[ax509.Certificate]]:
    roots = [ax509.Certificate.load(p.read_bytes()) for p in sorted((TRUST).glob("roots/*.crt"))]
    inters = [ax509.Certificate.load(p.read_bytes()) for p in sorted((TRUST).glob("intermediates/*.crt"))]
    return roots, inters


class _Verifier(xades.XAdESVerifier):
    """SignXML re-serializes nodes with an ASCII encoding, which breaks on non-ASCII element names such as
    <circunscripción>. Serialize as unicode instead."""

    def _tostring(self, xml_node, **kwargs):
        return etree.tostring(xml_node, encoding="unicode", **kwargs)


def strip_redundant_ns(src, parent=None):
    """Rebuild the tree without redundant namespace declarations.

    AutoFirma emits <ds:XPath xmlns:ds="..."> inside a Signature that already declares xmlns:ds. libxml2's
    C14N 1.0 keeps that redundant declaration (the spec says to drop it), so the SignedInfo canonical form no
    longer matches what the signer computed and SignXML reports InvalidSignature.
    """
    import copy

    own = {}
    if parent is not None:
        parent_map = parent.nsmap
        own = {p: u for p, u in (src.nsmap or {}).items() if parent_map.get(p) != u}
        new = etree.SubElement(parent, src.tag, dict(src.attrib), nsmap=own or None)
    else:
        new = etree.Element(src.tag, dict(src.attrib), nsmap=src.nsmap)
    new.text = src.text
    for ch in src:
        if isinstance(ch.tag, str):
            c = strip_redundant_ns(ch, new)
        else:
            c = copy.deepcopy(ch)
            new.append(c)
        c.tail = ch.tail
    return new


def _qc_info(cert: x509.Certificate) -> dict:
    try:
        ext = cert.extensions.get_extension_for_oid(x509.ObjectIdentifier(QC_STATEMENTS_OID))
    except x509.ExtensionNotFound:
        return {"present": False, "types": []}
    seq = acore.load(ext.value.value)
    types, compliance = [], False
    for i in range(len(seq)):  # a generic asn1crypto Sequence must be indexed, not iterated
        st = seq[i]
        oid = st[0].native
        compliance = compliance or oid == "0.4.0.1862.1.1"
        if oid == QC_TYPE_OID and len(st) > 1:
            types += [QC_TYPES.get(st[1][k].native, st[1][k].native) for k in range(len(st[1]))]
    return {"present": True, "types": types, "compliance": compliance}


def _has(exts: x509.Extensions, cls) -> bool:
    try:
        exts.get_extension_for_class(cls)
        return True
    except x509.ExtensionNotFound:
        return False


def classify_certificate(cert: x509.Certificate) -> dict:
    """Decide whether the certificate is an admissible natural-person signature certificate."""
    issuer_cn = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    profile = PROFILES.get(issuer_cn)
    out = {"issuer_cn": issuer_cn, "known_profile": profile is not None, "problems": []}
    if profile is None:
        out["problems"].append("issuer has no profile in the curated list")
        return out
    policies = {p.policy_identifier.dotted_string for p in cert.extensions.get_extension_for_class(
        x509.CertificatePolicies).value}
    out["policy_match"] = bool(policies & profile["policies"])
    if not out["policy_match"]:
        out["problems"].append("no accepted natural-person policy OID")
    qc = _qc_info(cert)
    out["qc_types"] = qc["types"]
    out["qc_compliance"] = qc.get("compliance", False)
    if qc["types"] and "esign" not in qc["types"]:
        out["problems"].append(f"QcType is {qc['types']}, not esign")
    if cert.subject.get_attributes_for_oid(x509.ObjectIdentifier(ORGANIZATION_IDENTIFIER_OID)):
        out["problems"].append("organizationIdentifier present (legal person / representative)")
    if cert.subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME):
        out["problems"].append("organization attribute present (legal person / representative)")
    exts = cert.extensions
    aia = exts.get_extension_for_class(x509.AuthorityInformationAccess).value if _has(
        exts, x509.AuthorityInformationAccess) else []
    has_ocsp = any(a.access_method == x509.oid.AuthorityInformationAccessOID.OCSP for a in aia)
    if not has_ocsp and not _has(exts, x509.CRLDistributionPoints):
        out["problems"].append("certificate declares no OCSP or CRL endpoint")
    ku = cert.extensions.get_extension_for_class(x509.KeyUsage).value
    out["content_commitment"] = ku.content_commitment
    if not ku.content_commitment:
        out["problems"].append("keyUsage lacks nonRepudiation/contentCommitment")
    sn = cert.subject.get_attributes_for_oid(NameOID.SERIAL_NUMBER)
    m = profile["nif_regex"].match(sn[0].value) if sn else None
    out["nif_found"] = bool(m)
    out["nif"] = m.group(1) if m else None  # internal use only, removed before reporting
    if not m:
        out["problems"].append("NIF not found in subject serialNumber")
    return out


def _xades_properties(sig: etree._Element, cert_der: bytes, now: dt.datetime) -> dict:
    res: dict = {"problems": []}
    sp = sig.find(f".//{XADES}SignedProperties")
    if sp is None:
        return {"ok": False, "problems": ["no xades:SignedProperties"]}
    st = sp.findtext(f".//{XADES}SigningTime")
    if not st:
        res["problems"].append("no SigningTime")
    else:
        t = dt.datetime.fromisoformat(st)
        res["signing_time_skew_s"] = round((now - t).total_seconds())
        if abs((now - t).total_seconds()) > 600:
            res["problems"].append("SigningTime differs from server time by more than 10 minutes")
    cd = sp.find(f".//{XADES}SigningCertificate/{XADES}Cert/{XADES}CertDigest")
    if cd is None:
        res["problems"].append("no SigningCertificate digest")
    else:
        alg = cd.find(f"{DS}DigestMethod").get("Algorithm").rsplit("#", 1)[1]
        digest = base64.b64decode(cd.findtext(f"{DS}DigestValue"))
        h = {"sha1": hashlib.sha1, "sha256": hashlib.sha256, "sha384": hashlib.sha384,
             "sha512": hashlib.sha512}[alg]
        res["cert_digest_alg"] = alg
        res["cert_digest_matches"] = h(cert_der).digest() == digest
        if not res["cert_digest_matches"]:
            res["problems"].append("SigningCertificate digest does not match the KeyInfo certificate")
    target = sig.find(f".//{XADES}QualifyingProperties").get("Target")
    res["target_ok"] = target == "#" + sig.get("Id", "")
    if not res["target_ok"]:
        res["problems"].append("QualifyingProperties Target does not point to this Signature")
    res["ok"] = not res["problems"]
    return res


def check_signature(signed: bytes, original_node_c14n: bytes) -> tuple[dict, bytes | None]:
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    root = etree.fromstring(signed, parser)
    sigs = root.findall(f"{DS}Signature")
    allsigs = list(root.iter(f"{DS}Signature"))
    out: dict = {"problems": []}
    if len(sigs) != 1 or len(allsigs) != 1:
        return {"ok": False, "problems": [f"expected exactly one Signature child of the root, got {len(allsigs)}"]}, None
    sig = sigs[0]
    node = root.find("avalcandidatura")
    node_id = node.get("Id")
    refs = sig.findall(f"{DS}SignedInfo/{DS}Reference")
    if not refs or refs[0].get("URI") != f"#{node_id}":
        out["problems"].append("first reference does not point to the avalcandidatura node")
    certs = sig.findall(f".//{DS}X509Certificate")
    if len(certs) != 1:
        return {"ok": False, "problems": ["expected exactly one X509Certificate in KeyInfo"]}, None
    cert_der = base64.b64decode(certs[0].text)
    cert = x509.load_der_x509_certificate(cert_der)
    pem = cert.public_bytes(serialization.Encoding.PEM)
    try:
        results = _Verifier().verify(strip_redundant_ns(root), x509_cert=pem, validate_schema=False)
    except Exception as exc:  # noqa: BLE001 - PoC report
        out["problems"].append(f"{type(exc).__name__}: {str(exc)[:200]}")
        out["ok"] = False
        return out, cert_der
    signed_names = [etree.QName(r.signed_xml).localname for r in results]
    out["signed_elements"] = signed_names
    node_result = next((r for r in results if etree.QName(r.signed_xml).localname == "avalcandidatura"), None)
    if node_result is None:
        out["problems"].append("signature does not cover avalcandidatura")
    else:
        # Compare the node that the signature really covers against the node we will store and export.
        covered = etree.tostring(node_result.signed_xml, method="c14n")
        stored = etree.tostring(node, method="c14n")
        out["covered_node_is_stored_node"] = covered == stored
        if covered != stored:
            out["problems"].append("signed node differs from the node found in the document (wrapping?)")
    out["ok"] = not out["problems"]
    return out, cert_der


async def check_certificate(cert_der: bytes, roots=None, inters=None, crls=None, live: bool = True) -> dict:
    """Chain, validity and revocation. With live=True OCSP/CRL are fetched; otherwise only supplied CRLs are used."""
    if roots is None:
        roots, inters = _load_trust()
    ee = ax509.Certificate.load(cert_der)
    backend = AIOHttpFetcherBackend() if live else None
    try:
        kwargs = {"fetchers": backend.get_fetchers(), "allow_fetching": True} if live else {"allow_fetching": False}
        vc = ValidationContext(trust_roots=roots, other_certs=inters or [], crls=crls or [],
                               revocation_mode="require", **kwargs)
        path = await CertificateValidator(ee, validation_context=vc).async_validate_usage({"non_repudiation"})
        return {"ok": True, "path_length": len(path),
                "revocation_mode": "require (OCSP/CRL fetched live)" if live else "require (supplied CRLs)"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"{type(exc).__name__}: {str(exc)[:300]}"}
    finally:
        if backend is not None:
            await backend.close()


async def run_checks(original: bytes, signed: bytes) -> dict:
    report: dict = {"checks": {}}
    c = report["checks"]
    if len(signed) > MAX_BYTES:
        c["size"] = {"ok": False, "detail": "signed XML too large"}
        report["accepted"] = False
        return report
    ok, detail = avalxml.integrity_ok(original, signed)
    c["integrity"] = {"ok": ok, "detail": detail}
    try:
        ok, errors = avalxml.schema_validate(signed)
        c["schema"] = {"ok": ok, "detail": errors}
    except Exception as exc:  # noqa: BLE001
        c["schema"] = {"ok": False, "detail": [f"error: {exc}"]}
    sig_res, cert_der = check_signature(signed, b"")
    c["signature"] = {"ok": sig_res["ok"], **sig_res}
    if cert_der is not None:
        root = etree.fromstring(signed)
        sig = root.find(f"{DS}Signature")
        now = dt.datetime.now(dt.timezone.utc)
        x = _xades_properties(sig, cert_der, now)
        c["xades_properties"] = x
        c["certificate_chain"] = await check_certificate(cert_der)
        cert = x509.load_der_x509_certificate(cert_der)
        cls = classify_certificate(cert)
        nif = cls.pop("nif")
        xml_id = root.findtext("avalcandidatura/avalista/id")
        cls["nif_matches_xml_id"] = bool(nif) and nif == (xml_id or "").upper()
        if not cls["nif_matches_xml_id"]:
            cls["problems"].append("certificate NIF does not match <id>")
        cls["ok"] = not cls["problems"]
        c["certificate_profile"] = cls
    report["accepted"] = all(v.get("ok") for v in c.values())
    return report
