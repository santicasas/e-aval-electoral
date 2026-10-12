"""PoC probe: records what the mobile app sends to the three-phase signature service, to document the protocol.

The iOS app signs XAdES in three phases (pre-sign, local signature, post-sign) against a server it finds at
``<origin>/afirma-server-triphase-signer/SignatureService``. This endpoint only LOGS the request (to the
git-ignored poc/private/) and answers with an error. It is not an implementation of the service.
"""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

TRIPHASE_PATH = "/afirma-server-triphase-signer/SignatureService"
LOG = Path(__file__).resolve().parent.parent / "private" / "triphase-requests.log"


def make_probe_router() -> APIRouter:
    router = APIRouter()

    @router.api_route(TRIPHASE_PATH, methods=["GET", "POST"])
    async def probe(request: Request):
        body = (await request.body()).decode("utf-8", "replace")
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"=== {time.strftime('%H:%M:%S')} {request.method} {request.url.path}?{request.url.query}\n")
            for k, v in request.headers.items():
                if k.lower() in ("content-type", "content-length", "user-agent"):
                    fh.write(f"{k}: {v}\n")
            fh.write(f"\n{body}\n\n")
        return PlainTextResponse("ERR-00:=probe: request recorded, service not implemented", status_code=500)

    return router
