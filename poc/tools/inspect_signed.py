"""Print the structure of an AutoFirma-signed aval with personal data masked (safe to paste in a report).

Usage: python poc/tools/inspect_signed.py poc/private/signed/<id>.signed.xml
"""
from __future__ import annotations

import base64
import re
import sys

from cryptography import x509
from lxml import etree

NS = {
    "ds": "http://www.w3.org/2000/09/xmldsig#",
    "xades": None,
}


def mask(text: str) -> str:
    text = re.sub(r"(CN=|givenName=|surname=|2\.5\.4\.42=|2\.5\.4\.4=)[^,]*", r"\1<NAME>", text)
    text = re.sub(r"\b[0-9XYZxyz][0-9]{7}[A-Za-z]\b", "<NIF>", text)
    text = re.sub(r"\b[0-9]{8}[A-Za-z]\b", "<NIF>", text)
    return text


def main(path: str) -> None:
    root = etree.parse(path).getroot()
    print("root:", root.tag, dict(root.attrib))
    for child in root:
        print(" child:", etree.QName(child).localname, "ns=", etree.QName(child).namespace, dict(child.attrib))
    ds = "{http://www.w3.org/2000/09/xmldsig#}"
    sig = root.find(f"{ds}Signature")
    si = sig.find(f"{ds}SignedInfo")
    print("c14n:", si.find(f"{ds}CanonicalizationMethod").get("Algorithm"))
    print("sigmethod:", si.find(f"{ds}SignatureMethod").get("Algorithm"))
    for ref in si.findall(f"{ds}Reference"):
        tr = [t.get("Algorithm") for t in ref.iter(f"{ds}Transform")]
        print(" ref:", ref.get("URI"), ref.get("Type"), ref.find(f"{ds}DigestMethod").get("Algorithm"), tr)
    for el in sig.iter():
        if isinstance(el.tag, str) and "xades" in el.tag.lower() or (
            isinstance(el.tag, str) and "uri.etsi.org" in el.tag
        ):
            ln = etree.QName(el)
            print(" xades:", ln.namespace, ln.localname, (el.text or "").strip()[:60])
    cert_b64 = sig.find(f".//{ds}X509Certificate").text
    certs = [c.text for c in sig.iter(f"{ds}X509Certificate")]
    print("X509Certificate elements:", len(certs))
    cert = x509.load_der_x509_certificate(base64.b64decode(certs[0]))
    print("subject:", mask(cert.subject.rfc4514_string()))
    for attr in cert.subject:
        is_name = attr.oid._name in ("commonName", "givenName", "surname")
        print("   ", attr.oid.dotted_string, attr.oid._name, "=", "<NAME>" if is_name else mask(str(attr.value)))
    print("issuer:", cert.issuer.rfc4514_string())
    print("validity:", cert.not_valid_before_utc, "->", cert.not_valid_after_utc)
    for ext in cert.extensions:
        v = ext.value
        print(" ext:", ext.oid.dotted_string, ext.oid._name, mask(str(v))[:300])


if __name__ == "__main__":
    main(sys.argv[1])
