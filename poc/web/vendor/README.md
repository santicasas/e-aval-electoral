# Vendored third-party code

`autoscript.js` — AutoScript 1.10.1 (Cliente @firma / AutoFirma JavaScript).
Origin: https://github.com/ctt-gob-es/clienteafirma, path
`afirma-ui-miniapplet-deploy/src/main/webapp/js/autoscript.js`, fetched 2026-10-12, unmodified.
Licence: the upstream project is dual-licensed (GPLv2 / EUPL v1.1). Compatibility with the platform licence
(ADR 0007) must be reviewed before the production release. Vendored so that aval pages load no third-party
script at runtime.

`autoscript.debug.js` — the same file with ONE added line in `openUrl` that logs the `afirma://` URL it opens. Debug
aid for the mobile PoC, used only by `debug.html`; never part of a production page.
The debug copy also sets `MAX_LONG_GENERAL_URL = 0` (always upload the operation data to the intermediate server
instead of putting it in the `afirma://` URL when it is short): experiment for the iOS app, which rejected the
direct form. Not part of the production page until the experiment is evaluated.
