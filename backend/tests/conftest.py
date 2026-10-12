from __future__ import annotations

from datetime import date

import pytest
from lxml import etree

from eaval.avalxml import Aval
from eaval.prepare import FormData
from eaval.schema import DS, load_spec

TODAY = date(2026, 10, 12)
ELECTION = date(2026, 11, 29)
NAME = "Candidatura de prova"


@pytest.fixture(scope="session")
def spec():
    return load_spec()


@pytest.fixture
def make_aval():
    def make(**kw) -> Aval:
        base = dict(nomb="NOM DE PROVA", ape1="COGNOM", ape2="SEGON COGNOM", fnac="19800101", tipoid="1",
                    id="00000000T", elecciones="CONGRESO", circunscripcion="Barcelona", nombre=NAME)
        base.update(kw)
        return Aval(**base)
    return make


@pytest.fixture
def make_form():
    def make(**kw) -> FormData:
        base = dict(nomb="Nom de prova", ape1="Cognom", ape2="Segon cognom", fnac="1980-01-01",
                    id="00000000T", elecciones="CONGRESO", circunscripcion="Barcelona")
        base.update(kw)
        return FormData(**base)
    return make


def fake_sign(unsigned_with_id: bytes, extra_attrs: bool = True) -> bytes:
    """Mimic what AutoFirma does to the document: ds:Signature inside oce after the node (+ attributes)."""
    root = etree.fromstring(unsigned_with_id)
    node = root.find("avalcandidatura")
    if extra_attrs:
        node.set("Encoding", "")
        node.set("MimeType", "text/xml")
    sig = etree.SubElement(root, f"{{{DS}}}Signature", nsmap={"ds": DS})
    etree.SubElement(sig, f"{{{DS}}}SignatureValue").text = "AAAA"
    return b'<?xml version="1.0" encoding="UTF-8"?>' + etree.tostring(root, encoding="UTF-8")
