"""Write poc/private/defaults.json (git-ignored) to pre-fill the PoC form from your own signed test file.

Name and NIF come from your certificate's subject; the birth date is NOT in the certificate, so a placeholder
is used (edit the file if you want another). Usage: python poc/tools/make_defaults.py [signed.xml]
"""
from __future__ import annotations

import base64
import glob
import json
import sys
from pathlib import Path

from cryptography import x509
from cryptography.x509.oid import NameOID
from lxml import etree

POC = Path(__file__).resolve().parent.parent
DS = "{http://www.w3.org/2000/09/xmldsig#}"


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob(str(POC / "private" / "signed" / "*.xml")))[-1]
    root = etree.parse(path).getroot()
    cert = x509.load_der_x509_certificate(base64.b64decode(root.find(f".//{DS}X509Certificate").text))
    attr = lambda oid: cert.subject.get_attributes_for_oid(oid)[0].value  # noqa: E731
    surname = attr(NameOID.SURNAME).split()
    nif = attr(NameOID.SERIAL_NUMBER).split("-", 1)[1]
    data = {
        "nomb": attr(NameOID.GIVEN_NAME)[:20],
        "ape1": surname[0][:25],
        "ape2": " ".join(surname[1:])[:25],
        "fnac": "19800101",
        "tipoid": "2" if nif[0] in "XYZ" else "1",
        "id": nif,
        "elecciones": "CONGRESO Y SENADO",
        "circunscripcion": "Barcelona",
        "nombre": "Example Candidacy",
    }
    out = POC / "private" / "defaults.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
