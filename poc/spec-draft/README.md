# Draft transcription of the official aval XSD — UNVERIFIED

Source: Instrucción 7/2011 JEC, BOE-A-2011-14814, Annex II. The BOE publishes the XML format, the XSD and a
signed example only as images (`14814_002.png` format, `14814_003..005.png` XSD, `14814_006/007.png` signed
example), at `https://www.boe.es/datos/imagenes/disp/2011/224/`.

`oce.UNVERIFIED.xsd` was transcribed by Claude on 2026-10-12 from those 720px-wide images. **It has not been
verified by the project owner.** It must not move to `spec/` until the owner checks it against the images
(especially accents and the enumeration list) and records that here.

## Findings from the images
1. **BOE inconsistency (needs owner decision):** the XSD declares the element `circunscripcion`
   (no accent), but both example XMLs show `<circunscripción />` (with accent). The draft follows the XSD; the
   official validator's behaviour is unknown.
2. **`PARLAMENTO EUROPEO`** is a fourth value of `tipoelecciones` (the project brief listed three). The list
   also ends with `Circunscripción Nacional` (European Parliament constituency).
3. The list has 63 values: 50 provinces, Ceuta, Melilla, 10 islands (Mallorca, Menorca, Ibiza-Formentera,
   Gran Canaria, Fuerteventura, Lanzarote, Tenerife, La Palma, El Hierro, La Gomera) and the national one.
4. **Field limits:** `nomb` max 20, `ape1`/`ape2` max 25, `id` max 9, `nombre` max 100; `fnac` is `AAAAMMDD`
   with only `maxLength 8` (no pattern); `tipoid` is `1` (NIF) or `2` (NIE). Real names longer than the limits
   would fail the schema: how to handle that is an open question.
5. **Signed example:** the signed `avalcandidatura` node carries attributes `Encoding=""`,
   `Id="avalcandidatura-<uuid>"` and `MimeType="text/xml"` that the XSD does not declare, and `ds:Signature`
   is a sibling of `avalcandidatura` under `oce`, also not in the XSD. So the XSD can only validate the
   unsigned structure: the server must strip the signature and these three attributes before schema
   validation, and the integrity check (PoC item 4) must tolerate them. To be confirmed against real AutoFirma
   output in the PoC.
6. The 2011 example uses RSA-SHA1/SHA1 digests and XAdES 1.3.2. Our SHA-256+ requirement is not contradicted
   by the visible text, but acceptance by the Oficina del Censo is unverified.
