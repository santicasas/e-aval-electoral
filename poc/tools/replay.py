"""Replay a saved signed aval through the verification pipeline and print a PII-free report.

Usage: python poc/tools/replay.py poc/private/signed/<id>.signed.xml [tamper]
The original document is reconstructed by removing the Signature (AutoFirma leaves the node untouched).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lxml import etree  # noqa: E402

from server.checks import DS, run_checks  # noqa: E402


def original_from_signed(signed: bytes) -> bytes:
    root = etree.fromstring(signed)
    for sig in root.findall(f"{{{DS[1:-1]}}}Signature"):
        root.remove(sig)
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True)


if __name__ == "__main__":
    signed = Path(sys.argv[1]).read_bytes()
    print(json.dumps(asyncio.run(run_checks(original_from_signed(signed), signed)), indent=1, ensure_ascii=False))
