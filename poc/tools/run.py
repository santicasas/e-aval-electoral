"""Run the PoC over HTTPS on https://localhost:8443 (self-signed dev certificate, generated on first run).

Usage (same on Windows and macOS):  python poc/tools/run.py [port] [--host IP] [--cert C --key K]
The certificate and key go to poc/private/dev-tls/, which is git-ignored.
"""
from __future__ import annotations

import datetime
import ipaddress
import subprocess
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

POC = Path(__file__).resolve().parent.parent
TLS = POC / "private" / "dev-tls"


def ensure_cert() -> tuple[Path, Path]:
    TLS.mkdir(parents=True, exist_ok=True)
    cert_path, key_path = TLS / "cert.pem", TLS / "key.pem"
    if cert_path.exists() and key_path.exists():
        return cert_path, key_path
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=30))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("port", nargs="?", default="8443")
    ap.add_argument("--host", default="127.0.0.1",
                    help="address to bind; use your Tailscale IP to reach the PoC from a phone, never 0.0.0.0")
    ap.add_argument("--cert", help="TLS certificate (PEM); default: the local self-signed one")
    ap.add_argument("--key", help="TLS private key (PEM)")
    args = ap.parse_args()
    cert, key = (Path(args.cert), Path(args.key)) if args.cert and args.key else ensure_cert()
    subprocess.run(
        [
            sys.executable, "-m", "uvicorn", "--app-dir", str(POC), "server.app:app",
            "--host", args.host, "--port", args.port,
            "--ssl-certfile", str(cert), "--ssl-keyfile", str(key),
            "--no-server-header",
        ],
        check=True,
    )
