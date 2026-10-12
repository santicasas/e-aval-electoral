"""PoC backend (FastAPI). Throwaway code for Phase 0.

Serves the static page with the production-style security headers and exposes the single-phase flow:
POST /api/aval            -> server generates the XML and keeps a copy
POST /api/aval/{id}/signed -> receives the signed XML, runs the checks and returns a report
"""
from __future__ import annotations

import base64
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import avalxml
from .checks import run_checks

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
PRIVATE = ROOT / "private"
(PRIVATE / "signed").mkdir(parents=True, exist_ok=True)

CSP_MODES = {
    "strict": (
        "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self' wss://127.0.0.1:*; frame-src afirma:; form-action 'none'; "
        "base-uri 'none'; object-src 'none'; frame-ancestors 'none'"
    ),
    # Chosen for the signature page: allow inline styles only (AutoScript injects a <style> and style attributes).
    "style-inline": (
        "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "connect-src 'self' wss://127.0.0.1:*; frame-src afirma:; form-action 'none'; "
        "base-uri 'none'; object-src 'none'; frame-ancestors 'none'"
    ),
}
# Owner decision 2026-10-12 (ADR 0009): the signature page allows inline styles because AutoScript injects a
# <style> and style attributes; script-src stays strictly 'self'. "strict" is kept for comparison tests.
CSP = CSP_MODES[os.environ.get("POC_CSP_MODE", "style-inline")]

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
STORE: dict[str, dict] = {}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = CSP
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if "server" in response.headers:
        del response.headers["server"]
    return response


class AvalIn(BaseModel):
    nomb: str
    ape1: str
    ape2: str
    fnac: str
    tipoid: str
    id: str
    elecciones: str
    circunscripcion: str
    nombre: str


# AutoFirma extra parameters under test. Variant A: signer picks the node by name (no Id from the server).
# Variant B: the server puts an Id on the node and nodeToSign refers to that Id (the only one that works).
# Variant C: B plus the extra parameters that should reproduce the BOE example's signature shape.
def sign_params(variant: str, node_id: str | None) -> str:
    node = node_id if variant in ("B", "C") else "avalcandidatura"
    params = [
        "format=XAdES Enveloped",
        f"nodeToSign={node}",
        "insertEnvelopedSignatureOnNodeByXPath=/oce",
        "includeOnlySignningCertificate=true",
    ]
    if variant == "C":
        # Pattern of the BOE example / other platforms: single C14N transform, SHA-256 digests.
        params += [
            "avoidEnvelopedTransformWhenSigningNode=true",
            "avoidXpathExtraTransformsOnEnveloped=true",
            "referencesDigestMethod=http://www.w3.org/2001/04/xmlenc#sha256",
        ]
    return "\n".join(params)


EXAMPLE_DEFAULTS = {
    "nomb": "Test", "ape1": "Example", "ape2": "Person", "fnac": "19800101", "tipoid": "1",
    "id": "00000000T", "elecciones": "CONGRESO Y SENADO", "circunscripcion": "Barcelona",
    "nombre": "Example Candidacy",
}


@app.get("/api/defaults")
def defaults():
    """Form pre-fill: poc/private/defaults.json (git-ignored, see tools/make_defaults.py) or fake examples."""
    import json

    path = PRIVATE / "defaults.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else EXAMPLE_DEFAULTS


@app.get("/api/circunscripciones")
def circunscripciones():
    import re

    text = avalxml.XSD_PATH.read_text(encoding="utf-8")
    block = re.search(r'name="circunscripcionINE".*?</xs:simpleType>', text, re.S).group(0)
    return re.findall(r'enumeration value="([^"]+)"', block)


@app.post("/api/aval")
def create_aval(body: AvalIn, variant: str = "A"):
    if variant not in ("A", "B", "C"):
        raise HTTPException(400, "variant must be A, B or C")
    aval_id = str(uuid.uuid4())
    node_id = f"avalcandidatura-{aval_id}" if variant in ("B", "C") else None
    data = body.model_dump()
    xml = avalxml.build_unsigned(data, node_id)
    ok, errors = avalxml.schema_validate(xml)
    if not ok:
        raise HTTPException(422, {"schema_errors": errors})
    STORE[aval_id] = {"xml": xml, "variant": variant}
    return {
        "id": aval_id,
        "xml_b64": base64.b64encode(xml).decode(),
        "params": sign_params(variant, node_id),
    }


class SignedIn(BaseModel):
    xml_b64: str


@app.post("/api/aval/{aval_id}/signed")
async def receive_signed(aval_id: str, body: SignedIn):
    entry = STORE.get(aval_id)
    if entry is None:
        raise HTTPException(404, "unknown aval")
    signed = base64.b64decode(body.xml_b64)
    (PRIVATE / "signed" / f"{aval_id}.signed.xml").write_bytes(signed)
    return await run_checks(entry["xml"], signed)


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
