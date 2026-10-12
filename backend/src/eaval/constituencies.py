"""Coherence between ``elecciones`` and ``circunscripcion``, which the XSD does not check (it only checks that
the value belongs to the list).

Rules (owner, 2026-10-12):
- CONGRESO: 50 provinces + Ceuta + Melilla; in the Balearic and Canary Islands the *province*.
- SENADO: in the Balearic and Canary Islands the *island or island group*; elsewhere the province.
- CONGRESO Y SENADO: only where both constituencies coincide, i.e. NOT in the insular provinces.
- PARLAMENTO EUROPEO <-> "Circunscripción Nacional", only with each other.
"""
from __future__ import annotations

from dataclasses import dataclass

from .errors import AvalError
from .schema import Spec, load_spec

CONGRESO, SENADO, AMBOS, EUROPEO = "CONGRESO", "SENADO", "CONGRESO Y SENADO", "PARLAMENTO EUROPEO"
NACIONAL = "Circunscripción Nacional"

# Insular province (Congreso constituency) -> islands / island groups (Senado constituencies).
INSULAR: dict[str, tuple[str, ...]] = {
    "Balears, Illes": ("Mallorca", "Menorca", "Ibiza-Formentera"),
    "Palmas, Las": ("Gran Canaria", "Fuerteventura", "Lanzarote"),
    "Santa Cruz de Tenerife": ("Tenerife", "La Palma", "El Hierro", "La Gomera"),
}
ISLANDS: dict[str, str] = {island: prov for prov, islands in INSULAR.items() for island in islands}


def _provinces(spec: Spec) -> list[str]:
    """The 52 Congreso constituencies: everything that is neither an island nor the national constituency."""
    return [c for c in spec.circunscripciones if c not in ISLANDS and c != NACIONAL]


def allowed(elecciones: str, spec: Spec | None = None) -> list[str]:
    """Constituencies valid for an election type."""
    spec = spec or load_spec()
    provinces = _provinces(spec)
    if elecciones == CONGRESO:
        return provinces
    if elecciones == SENADO:
        return [p for p in provinces if p not in INSULAR] + [i for i in spec.circunscripciones if i in ISLANDS]
    if elecciones == AMBOS:
        return [p for p in provinces if p not in INSULAR]
    if elecciones == EUROPEO:
        return [NACIONAL]
    raise AvalError("unknown_election", "elecciones", elecciones)


def check(elecciones: str, circunscripcion: str, spec: Spec | None = None) -> None:
    """Raise AvalError unless the pair is coherent."""
    spec = spec or load_spec()
    if elecciones not in spec.elecciones:
        raise AvalError("unknown_election", "elecciones", elecciones)
    if circunscripcion not in spec.circunscripciones:
        raise AvalError("unknown_constituency", "circunscripcion", circunscripcion)
    if circunscripcion in allowed(elecciones, spec):
        return
    if circunscripcion == NACIONAL or elecciones == EUROPEO:
        raise AvalError("national_only_for_europeo", "circunscripcion", f"{elecciones} / {circunscripcion}")
    if elecciones == AMBOS and (circunscripcion in INSULAR or circunscripcion in ISLANDS):
        raise AvalError("both_chambers_insular", "elecciones",
                        "Congreso and Senado have different constituencies here: two avals are needed")
    raise AvalError("incoherent_constituency", "circunscripcion", f"{elecciones} / {circunscripcion}")


@dataclass(frozen=True)
class AvalSlot:
    """One aval the signer has to sign."""

    elecciones: str
    circunscripcion: str


def required_avals(chambers: str, province: str, island: str | None = None,
                   spec: Spec | None = None) -> list[AvalSlot]:
    """Avals a signer must sign for a candidacy that stands in ``chambers`` (CONGRESO, SENADO, CONGRESO Y
    SENADO or PARLAMENTO EUROPEO) when the signer is registered in ``province`` (and ``island`` if insular).

    In an insular province a candidacy standing in both chambers needs TWO avals: a CONGRESO one with the
    province and a SENADO one with the island.
    """
    spec = spec or load_spec()
    if chambers == EUROPEO:
        slots = [AvalSlot(EUROPEO, NACIONAL)]
    else:
        insular = province in INSULAR
        if insular and island is None and chambers in (SENADO, AMBOS):
            raise AvalError("island_required", "island", province)
        if island is not None:
            if not insular or island not in INSULAR[province]:
                raise AvalError("island_not_in_province", "island", f"{island} / {province}")
        if chambers == CONGRESO:
            slots = [AvalSlot(CONGRESO, province)]
        elif chambers == SENADO:
            slots = [AvalSlot(SENADO, island if insular else province)]
        elif chambers == AMBOS:
            slots = ([AvalSlot(CONGRESO, province), AvalSlot(SENADO, island)] if insular
                     else [AvalSlot(AMBOS, province)])
        else:
            raise AvalError("unknown_election", "elecciones", chambers)
    for s in slots:
        check(s.elecciones, s.circunscripcion, spec)
    return slots
