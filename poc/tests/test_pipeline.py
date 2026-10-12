"""PoC tests: real AutoFirma output (optional, local only) and synthetic rejection cases."""
from __future__ import annotations

import asyncio
import base64
import copy
import glob
import sys
from pathlib import Path

import pytest
from asn1crypto import crl as acrl
from asn1crypto import x509 as ax509
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from lxml import etree

POC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(POC))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import synth  # noqa: E402
from server import avalxml, checks  # noqa: E402
from server.checks import DS  # noqa: E402

SIGNED = sorted(glob.glob(str(POC / "private" / "signed" / "*.signed.xml")))
real = pytest.mark.skipif(not SIGNED, reason="needs a real AutoFirma-signed aval in poc/private/signed/")


def run(coro):
    return asyncio.run(coro)


def original_of(signed: bytes) -> bytes:
    root = etree.fromstring(signed)
    for s in root.findall(f"{DS}Signature"):
        root.remove(s)
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True)


def load_signed():
    return Path(SIGNED[0]).read_bytes()


# ---- real signature -------------------------------------------------------------------------------------------

@real
def test_real_signature_signxml_workarounds_needed():
    """Documents the two library incompatibilities: plain SignXML must fail, the workarounds must pass."""
    signed = load_signed()
    res, _ = checks.check_signature(signed, b"")
    assert res["ok"], res
    assert res["signed_elements"] == ["avalcandidatura", "SignedProperties", "KeyInfo"]
    from signxml import xades
    root = etree.fromstring(signed)
    cert = x509.load_der_x509_certificate(base64.b64decode(root.find(f".//{DS}X509Certificate").text))
    with pytest.raises(Exception):
        xades.XAdESVerifier().verify(signed, x509_cert=cert.public_bytes(serialization.Encoding.PEM))


@real
def test_real_full_pipeline_accepts():
    signed = load_signed()
    rep = run(checks.run_checks(original_of(signed), signed))
    # signing_time_skew only matters for fresh signatures; ignore it when replaying an old file
    c = rep["checks"]
    assert c["integrity"]["ok"] and c["schema"]["ok"] and c["signature"]["ok"]
    assert c["certificate_chain"]["ok"], c["certificate_chain"]
    assert c["certificate_profile"]["ok"], c["certificate_profile"]


@real
@pytest.mark.parametrize("path,new", [("avalista/id", "11111111H"), ("candidatura/nombre", "Other Candidacy"),
                                       ("candidatura/circunscripción", "Madrid")])
def test_real_tampered_node_rejected(path, new):
    signed = load_signed()
    root = etree.fromstring(signed)
    root.find(f"avalcandidatura/{path}").text = new
    tampered = etree.tostring(root, encoding="UTF-8", xml_declaration=True)
    sig_res, _ = checks.check_signature(tampered, b"")
    assert not sig_res["ok"]
    assert not avalxml.integrity_ok(original_of(signed), tampered)[0]


@real
def test_real_signature_wrapping_rejected():
    """Add a second, forged avalcandidatura: the single-node rule and the covered-node check must reject it."""
    root = etree.fromstring(load_signed())
    forged = copy.deepcopy(root.find("avalcandidatura"))
    forged.find("avalista/id").text = "11111111H"
    root.insert(0, forged)
    out = etree.tostring(root, encoding="UTF-8", xml_declaration=True)
    with pytest.raises(ValueError):
        avalxml.normalized_node_c14n(out)
    rep = run(checks.run_checks(original_of(load_signed()), out))
    assert not rep["accepted"]
    assert not rep["checks"]["integrity"]["ok"]


@real
def test_real_no_signature_rejected():
    root = etree.fromstring(load_signed())
    for s in root.findall(f"{DS}Signature"):
        root.remove(s)
    out = etree.tostring(root, encoding="UTF-8", xml_declaration=True)
    assert not checks.check_signature(out, b"")[0]["ok"]


@real
def test_real_xxe_and_entities_not_resolved():
    evil = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a SYSTEM "file:///etc/passwd">]><oce>&a;</oce>'
    with pytest.raises(Exception):
        avalxml.schema_validate(evil)


# ---- synthetic rejection cases ------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pki():
    return synth.make_pki()


def validate(pki, kind, revoke=False):
    root, inter, inter_key, root_key = pki
    ee = synth.make_ee(inter, inter_key, kind)
    crl = synth.make_crl(inter, inter_key, [ee.serial_number] if revoke else [])
    root_crl = synth.make_crl(root, root_key, [])
    chain = run(checks.check_certificate(
        synth.der(ee), roots=[ax509.Certificate.load(synth.der(root))],
        inters=[ax509.Certificate.load(synth.der(inter))],
        crls=[acrl.CertificateList.load(c.public_bytes(serialization.Encoding.DER)) for c in (crl, root_crl)],
        live=False))
    return ee, chain


def test_synthetic_valid_accepted(pki):
    ee, chain = validate(pki, "valid")
    assert chain["ok"], chain
    cls = checks.classify_certificate(ee)
    assert not cls["problems"], cls
    assert cls["nif"] == "00000000T"


def test_synthetic_expired_rejected(pki):
    _, chain = validate(pki, "expired")
    assert not chain["ok"]


def test_synthetic_revoked_rejected(pki):
    _, chain = validate(pki, "valid", revoke=True)
    assert not chain["ok"] and "revoked" in chain["detail"].lower()


@pytest.mark.parametrize("kind,fragment", [
    ("seal", "QcType"),
    ("legal_person", "legal person"),
    ("other_policy", "policy"),
    ("no_content_commitment", "nonRepudiation"),
    ("no_revocation_pointer", "no OCSP or CRL"),
])
def test_synthetic_profile_rejections(pki, kind, fragment):
    ee, _ = validate(pki, kind)
    cls = checks.classify_certificate(ee)
    assert any(fragment in p for p in cls["problems"]), cls


def test_unknown_issuer_rejected(pki):
    root, inter, inter_key, _ = pki
    ee = synth.make_ee(inter, inter_key, "valid")
    saved = dict(checks.PROFILES)
    checks.PROFILES.clear()
    try:
        assert "no profile" in " ".join(checks.classify_certificate(ee)["problems"])
    finally:
        checks.PROFILES.update(saved)


# ---- real representative certificate (FNMT) -----------------------------------------------------------------

def _signed_by(issuer_cn):
    for f in SIGNED:
        root = etree.parse(f).getroot()
        cert = x509.load_der_x509_certificate(base64.b64decode(root.find(f".//{DS}X509Certificate").text))
        if issuer_cn in cert.issuer.rfc4514_string():
            return Path(f).read_bytes(), cert
    return None, None


def test_real_fnmt_representative_rejected_even_if_issuer_were_admitted():
    """The representative certificate has serialNumber IDCES-<NIF> and QcType esign, like a natural person:
    only the organization attributes and the policy tell them apart."""
    signed, cert = _signed_by("AC Representaci")
    if cert is None:
        pytest.skip("needs a signature made with an FNMT representative certificate")
    import re
    checks.PROFILES["AC Representación"] = {"policies": {"1.3.6.1.4.1.5734.3.10.1"},  # hypothetical natural-person OID
                                            "nif_regex": re.compile(r"^IDCES-([0-9A-Z]{9})$")}
    try:
        cls = checks.classify_certificate(cert)
    finally:
        del checks.PROFILES["AC Representación"]
    assert cls["nif_found"] and cls["qc_types"] == ["esign"]  # looks like a natural person at first sight
    assert any("legal person" in p for p in cls["problems"])
    assert any("policy" in p for p in cls["problems"])
