"""Synthetic test PKI (PoC): root -> intermediate named like the idCAT issuer -> end-entity of several kinds.

Only used to exercise rejection paths that the owner's single real idCAT certificate cannot (expired,
revoked, seal, legal person). No real certificate or personal data.
"""
from __future__ import annotations

import datetime as dt

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

NOW = dt.datetime.now(dt.timezone.utc)
POLICY = "1.3.6.1.4.1.15096.1.3.2.86.2"


def _tlv(tag: int, content: bytes) -> bytes:
    assert len(content) < 128
    return bytes([tag, len(content)]) + content


def qc_statements(qc_type_last: int) -> bytes:
    # QcCompliance (0.4.0.1862.1.1) and QcType (0.4.0.1862.1.6) with 0.4.0.1862.1.6.<qc_type_last>
    compliance = _tlv(0x30, bytes.fromhex("060604008e460101"))
    type_oid = bytes.fromhex("060704008e460106") + bytes([qc_type_last])
    qc_type = _tlv(0x30, bytes.fromhex("060604008e460106") + _tlv(0x30, type_oid))
    return _tlv(0x30, compliance + qc_type)


def _dp(url="http://pki.invalid/ca.crl"):
    return x509.CRLDistributionPoints([x509.DistributionPoint([x509.UniformResourceIdentifier(url)], None, None, None)])


def _key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _name(cn, **extra):
    attrs = [x509.NameAttribute(NameOID.COMMON_NAME, cn), x509.NameAttribute(NameOID.COUNTRY_NAME, "ES")]
    return x509.Name(attrs + extra.get("attrs", []))


def make_pki(inter_cn="EC-Ciutadania"):
    root_key, inter_key = _key(), _key()
    root_name = _name("Synthetic Root")
    root = (x509.CertificateBuilder().subject_name(root_name).issuer_name(root_name)
            .public_key(root_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(NOW - dt.timedelta(days=3650)).not_valid_after(NOW + dt.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
            .sign(root_key, hashes.SHA256()))
    inter_name = _name(inter_cn)  # same CN as the real issuer so the PoC profile applies
    inter = (x509.CertificateBuilder().subject_name(inter_name).issuer_name(root_name)
             .public_key(inter_key.public_key()).serial_number(x509.random_serial_number())
             .not_valid_before(NOW - dt.timedelta(days=3000)).not_valid_after(NOW + dt.timedelta(days=3000))
             .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
             .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), True)
             .add_extension(_dp("http://pki.invalid/root.crl"), False)
             .sign(root_key, hashes.SHA256()))
    return root, inter, inter_key, root_key


def make_ee(inter, inter_key, kind="valid", nif="00000000T", policy=POLICY):
    key = _key()
    attrs = [x509.NameAttribute(NameOID.SERIAL_NUMBER, f"IDCES-{nif}"),
             x509.NameAttribute(NameOID.GIVEN_NAME, "TEST"), x509.NameAttribute(NameOID.SURNAME, "PERSON")]
    qc_last, cc = 1, True
    not_after = NOW + dt.timedelta(days=365)
    not_before = NOW - dt.timedelta(days=10)
    if kind == "expired":
        not_before, not_after = NOW - dt.timedelta(days=400), NOW - dt.timedelta(days=35)
    elif kind == "seal":
        qc_last = 2
        attrs = [x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Example Org"),
                 x509.NameAttribute(x509.ObjectIdentifier("2.5.4.97"), "VATES-A00000000")]
    elif kind == "legal_person":
        attrs += [x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Example Org"),
                  x509.NameAttribute(x509.ObjectIdentifier("2.5.4.97"), "VATES-A00000000")]
    elif kind == "other_policy":
        policy = "1.2.3.4.5"
    elif kind == "no_content_commitment":
        cc = False
    b = (x509.CertificateBuilder()
         .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "TEST PERSON - DNI " + nif)] + attrs
                                 + [x509.NameAttribute(NameOID.COUNTRY_NAME, "ES")]))
         .issuer_name(inter.subject).public_key(key.public_key())
         .serial_number(x509.random_serial_number())
         .not_valid_before(not_before).not_valid_after(not_after)
         .add_extension(x509.BasicConstraints(ca=False, path_length=None), True))
    if kind != "no_revocation_pointer":
        b = b.add_extension(_dp(), False)
    cert = (b
            .add_extension(x509.KeyUsage(True, cc, False, False, False, False, False, False, False), True)
            .add_extension(x509.CertificatePolicies([x509.PolicyInformation(x509.ObjectIdentifier(policy), None)]),
                           False)
            .add_extension(x509.UnrecognizedExtension(x509.ObjectIdentifier("1.3.6.1.5.5.7.1.3"),
                                                      qc_statements(qc_last)), False)
            .sign(inter_key, hashes.SHA256()))
    return cert


def make_crl(issuer, issuer_key, revoked_serials=()):
    inter, inter_key = issuer, issuer_key
    b = (x509.CertificateRevocationListBuilder().issuer_name(inter.subject)
         .last_update(NOW - dt.timedelta(hours=1)).next_update(NOW + dt.timedelta(days=1)))
    for s in revoked_serials:
        b = b.add_revoked_certificate(x509.RevokedCertificateBuilder().serial_number(s)
                                      .revocation_date(NOW - dt.timedelta(minutes=30)).build())
    return b.sign(inter_key, hashes.SHA256())


def der(cert) -> bytes:
    return cert.public_bytes(serialization.Encoding.DER)
