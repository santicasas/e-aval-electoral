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
    # Experiment: allow inline styles (AutoScript injects a <style> and style attributes).
    "style-inline": (
        "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "connect-src 'self' wss://127.0.0.1:*; frame-src afirma:; form-action 'none'; "
        "base-uri 'none'; object-src 'none'; frame-ancestors 'none'"
    ),
}
CSP = CSP_MODES[os.environ.get("POC_CSP_MODE", "strict")]

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
# Variant B: the server puts an Id on the node and nodeToSign refers to that Id.
def sign_params(variant: str, node_id: str | None) -> str:
    node = node_id if variant == "B" else "avalcandidatura"
    return "\n".join(
        [
            "format=XAdES Enveloped",
            f"nodeToSign={node}",
            "insertEnvelopedSignatureOnNodeByXPath=/oce",
            "includeOnlySignningCertificate=true",
        ]
    )


@app.get("/api/circunscripciones")
def circunscripciones():
    import re

    text = avalxml.XSD_PATH.read_text(encoding="utf-8")
    block = re.search(r'name="circunscripcionINE".*?</xs:simpleType>', text, re.S).group(0)
    return re.findall(r'enumeration value="([^"]+)"', block)


@app.post("/api/aval")
def create_aval(body: AvalIn, variant: str = "A"):
    if variant not in ("A", "B"):
        raise HTTPException(400, "variant must be A or B")
    aval_id = str(uuid.uuid4())
    node_id = f"avalcandidatura-{aval_id}" if variant == "B" else None
    data = body.model_dump()
    data["circunscripción"] = data.pop("circunscripcion")
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
