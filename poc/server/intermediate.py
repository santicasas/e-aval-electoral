"""Intermediate storage/retrieve services for mobile signing (Cliente @firma on iOS/Android). PoC.

Protocol reimplemented from the official servlets (ctt-gob-es/clienteafirma, afirma-signature-storage and
afirma-signature-retriever, class StorageService / RetrieveService):
- Storage: ``POST`` (or GET) with ``op=put&v=1_0&id=<id>&dat=<data>``. Answers ``OK`` or ``ERR-nn:=message``
  (always HTTP 200). ``op=check`` answers ``OK``.
- Retrieve: ``op=get&v=1_0&id=<id>[&it=<n>]`` by GET or by POST form body (the page uses POST). Returns the stored
  text and deletes it (one-time read). Missing, expired or already read ids all answer ``ERR-06`` so a client
  cannot tell them apart; the page treats ``ERR-06`` as "not yet, keep polling".

The server only ever holds data that the page encrypted for the native app (and the app's encrypted answer); it
cannot read it. Nothing is logged about ids or content. Expiry is short and the size limit bounds memory.
"""
from __future__ import annotations

import re
import time
from typing import Callable
from urllib.parse import unquote_plus

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

STORAGE_PATH = "/afirma-signature-storage/StorageService"
RETRIEVE_PATH = "/afirma-signature-retriever/RetrieveService"

ERRORS = {
    "ERR-00": "No se ha indicado código de operación",
    "ERR-01": "Código de operación no soportado",
    "ERR-02": "No se han proporcionado los datos de la operación",
    "ERR-05": "No se ha proporcionado un identificador para los datos",
    "ERR-06": "El identificador para los datos es inválido",
    "ERR-07": "Los datos solicitados o enviados son inválidos",
    "ERR-20": "No se ha indicado la versión de la sintaxis de la operación",
}
# The official servlets only reject '.', '/' and '\'. We are stricter: URL-safe characters only.
_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def err(code: str) -> str:
    return f"{code}:={ERRORS[code]}"


class Store:
    """In-memory one-time store with expiry and bounds. Single process (PoC)."""

    def __init__(self, ttl: float = 120.0, max_bytes: int = 512 * 1024, max_items: int = 1000,
                 clock: Callable[[], float] = time.monotonic):
        self.ttl, self.max_bytes, self.max_items, self.clock = ttl, max_bytes, max_items, clock
        self._items: dict[str, tuple[float, str]] = {}

    def _purge(self) -> None:
        now = self.clock()
        for key in [k for k, (t, _) in self._items.items() if now - t > self.ttl]:
            del self._items[key]

    def put(self, id_: str, data: str) -> str:
        self._purge()
        if len(data.encode("utf-8")) > self.max_bytes:
            data = err("ERR-07")  # like the official servlet: the error travels through the stored file
        if id_ not in self._items and len(self._items) >= self.max_items:
            return err("ERR-07")
        self._items[id_] = (self.clock(), data)
        return "OK"

    def get(self, id_: str) -> str:
        self._purge()
        item = self._items.pop(id_, None)  # one-time read
        return item[1] if item else err("ERR-06")

    def __len__(self) -> int:
        return len(self._items)


def _parse_form(body: bytes) -> dict[str, str]:
    params: dict[str, str] = {}
    for part in body.decode("utf-8", "replace").split("&"):
        key, eq, value = part.partition("=")
        if eq:
            params[key] = value
    return params


async def _params(request: Request) -> dict[str, str]:
    """Parameters from the query string and, for POST, the form-encoded body (as the Java servlets do)."""
    params = {k: v for k, v in request.query_params.items()}
    if request.method == "POST":
        params.update(_parse_form(await request.body()))
    return params


def make_router(store: Store) -> APIRouter:
    router = APIRouter()

    def text(body: str) -> PlainTextResponse:
        return PlainTextResponse(body + "\n" if body != "OK" else body, media_type="text/plain; charset=utf-8")

    @router.api_route(STORAGE_PATH, methods=["GET", "POST"])
    async def storage(request: Request):
        p = await _params(request)
        op = p.get("op")
        if op is None:
            return text(err("ERR-00"))
        if op == "check" and request.method == "GET":
            return text("OK")
        if "v" not in p:
            return text(err("ERR-20"))
        if op.lower() != "put":
            return text(err("ERR-01"))
        id_ = p.get("id")
        if id_ is None:
            return text(err("ERR-05"))
        if not _ID.match(id_):
            return text(err("ERR-06"))
        data = p.get("dat")
        if not data:
            return text(store.put(id_, err("ERR-02")))
        return text(store.put(id_, unquote_plus(data)))

    @router.api_route(RETRIEVE_PATH, methods=["GET", "POST"])
    async def retrieve(request: Request):
        p = await _params(request)
        op = p.get("op")
        if op is None:
            return text(err("ERR-00"))
        if op == "check":
            return text("OK")
        if "v" not in p:
            return text(err("ERR-20"))
        if op.lower() != "get":
            return text(err("ERR-01"))
        id_ = p.get("id")
        if id_ is None:
            return text(err("ERR-05"))
        if not _ID.match(id_):
            return text(err("ERR-06"))
        return text(store.get(id_))

    return router
