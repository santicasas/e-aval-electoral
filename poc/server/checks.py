"""PoC verification pipeline. Each check reports pass/fail plus detail, so results can go into the PoC report.

Stage 1 (this file, first cut): integrity and schema. Signature, XAdES properties and certificate checks are
added once a real AutoFirma output is available.
"""
from __future__ import annotations

from . import avalxml


def run_checks(original: bytes, signed: bytes) -> dict:
    report: dict = {"checks": {}}
    ok, detail = avalxml.integrity_ok(original, signed)
    report["checks"]["integrity"] = {"ok": ok, "detail": detail}
    try:
        ok, errors = avalxml.schema_validate(signed)
        report["checks"]["schema"] = {"ok": ok, "detail": errors}
    except Exception as exc:  # noqa: BLE001
        report["checks"]["schema"] = {"ok": False, "detail": [f"error: {exc}"]}
    report["accepted"] = all(c["ok"] for c in report["checks"].values())
    return report
