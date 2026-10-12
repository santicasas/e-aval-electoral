# 0009 — Inline styles allowed on the signature page

Status: Accepted (owner decision, 2026-10-12). Revisit after the 29 Nov 2026 election.

## Context
The PoC showed that AutoScript (the AutoFirma JavaScript) injects a `<style>` element for its dialogs and sets a
`style` attribute on its hidden iframe (Firefox). Under `style-src 'self'` the browser reports `style-src-elem`
and `style-src-attr` violations. The signature flow still works; only the AutoScript dialogs (AutoFirma not
installed, errors) would render unstyled.

## Decision
The signature page uses `style-src 'self' 'unsafe-inline'`. Every other directive stays strict, in particular
`script-src 'self'` with no inline script, `default-src 'none'`, `frame-ancestors 'none'`,
`frame-src afirma:` (verified sufficient on Firefox/Windows) and `connect-src` limited to the backend and
`wss://127.0.0.1:*`. Other pages keep `style-src 'self'`.

## Consequences
A small relaxation: injected CSS could be used for CSS-based data exfiltration or UI redressing if an HTML
injection existed. Mitigated by no inline script, no user HTML rendered, and all dynamic text set with
`textContent`. Later alternatives: patch the vendored script (nonce on the injected style, class instead of the
style attribute) or build our own error UI and disable the dialogs.
