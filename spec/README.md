# Official specification of the aval XML

One directory per election call, so schema and enumerations can change between processes:

```
spec/
  generales-2026/            # general elections of 29 Nov 2026 (Real Decreto 806/2026)
    aval-jec-2011.xsd        # official XSD, verbatim
    example-unsigned.xml     # unsigned example that validates against the XSD (fake data)
```

## Origin
Instrucción 7/2011 of the Junta Electoral Central, Annex II, section 2.2, BOE no. 224 of 17 Sep 2011, pages
98888 to 98890 (BOE-A-2011-14814): <https://www.boe.es/boe/dias/2011/09/17/pdfs/BOE-A-2011-14814.pdf>.

`aval-jec-2011.xsd` was transcribed by the project owner from the text of the official PDF (the BOE web page
publishes it only as images) and validated with lxml. Its normative content is unmodified; only the origin
comment was added. On 2026-10-12 it was cross-checked against an independent reading of the BOE images: the 69
enumeration values (in order), the five `maxLength` values and the element names are identical.

## Particularities of the document
- Root `oce` with no namespace; `avalcandidatura` contains `avalista` (`nomb`, `ape1`, `ape2`, `fnac`, `tipoid`,
  `id`) and `candidatura` (`elecciones`, `circunscripcion`, `nombre`), in that order.
- **The element is `circunscripcion` (no accent).** The BOE example XML writes `<circunscripción>`; the schema
  rules. (The earlier PoC used the accented name; that was reverted.)
- `elecciones`: `CONGRESO`, `SENADO`, `CONGRESO Y SENADO`, `PARLAMENTO EUROPEO`.
- `circunscripcion`: 63 values: 50 provinces, Ceuta, Melilla, 10 islands and `Circunscripción Nacional`. The
  schema only checks list membership, not coherence with `elecciones` (see the coherence matrix in the code).
- Limits: `nomb` 20, `ape1`/`ape2` 25, `id` 9, `nombre` 100. `fnac` is `AAAAMMDD` but the schema only enforces
  `maxLength 8`. `tipoid` is `1` (NIF) or `2` (NIE).
- Several values contain `/` (`Araba/Álava`, `Alicante/Alacant`, `Castellón/Castelló`, `Valencia/València`),
  which cannot appear in a file name; the BOE does not say how to write them in ZIP names (open point).
- **The signed document does not validate against this XSD.** The BOE's own signed example adds the attributes
  `Id`, `Encoding` and `MimeType` to `avalcandidatura` and puts `ds:Signature` inside `oce`; the schema allows
  neither. Hence the two-phase validation: strict XSD before signing, a derived schema after signing.
- The 2011 example uses SHA-1 and RSA-SHA1; this project requires SHA-256 or stronger.
