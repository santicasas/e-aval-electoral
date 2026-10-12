"""From the signer's form data to a validated ``Aval`` plus the notices to show before signing."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import constituencies
from .avalxml import Aval
from .config import Options
from .errors import AvalError, Notice
from .normalize import (check_min_age, clean_text, normalize_id, normalize_name, parse_birth_date)
from .schema import Spec, load_spec


@dataclass(frozen=True)
class FormData:
    nomb: str
    ape1: str
    ape2: str
    fnac: str | date
    id: str
    elecciones: str
    circunscripcion: str
    tipoid: str | None = None  # derived from id when omitted


def prepare(form: FormData, candidacy_name: str, *, today: date, election_date: date | None = None,
            options: Options | None = None, spec: Spec | None = None) -> tuple[Aval, list[Notice]]:
    """Normalise and validate. Raises AvalError on anything that cannot be fixed; returns Notices for what was
    changed (the UI shows them and the signer confirms before AutoFirma is called)."""
    options = options or Options()
    spec = spec or load_spec()
    notices: list[Notice] = []
    nomb, n = normalize_name("nomb", form.nomb, spec.max_length("nombavalista"), options, required=True)
    notices += n
    ape1, n = normalize_name("ape1", form.ape1, spec.max_length("apellidoavalista"), options, required=True)
    notices += n
    ape2, n = normalize_name("ape2", form.ape2, spec.max_length("apellidoavalista"), options, required=False)
    notices += n
    nif, tipoid = normalize_id(form.id, form.tipoid, options)
    if nif != form.id:
        notices.append(Notice("id_normalised", "id", form.id, nif))
    if form.elecciones in (constituencies.CONGRESO, constituencies.SENADO, constituencies.AMBOS) and tipoid != "1":
        raise AvalError("nie_not_allowed_for_general_elections", "tipoid")
    birth = parse_birth_date(form.fnac, today=today)
    check_min_age(birth, election_date, options)
    name = clean_text(candidacy_name)
    if len(name) > spec.max_length("nombcandidatura"):
        raise AvalError("candidacy_name_too_long", "nombre", f"{len(name)} > 100")  # never truncated
    if not name:
        raise AvalError("required", "nombre")
    aval = Aval(nomb=nomb, ape1=ape1, ape2=ape2, fnac=birth.strftime("%Y%m%d"), tipoid=tipoid, id=nif,
                elecciones=form.elecciones, circunscripcion=form.circunscripcion, nombre=name)
    constituencies.check(aval.elecciones, aval.circunscripcion, spec)
    return aval, notices
