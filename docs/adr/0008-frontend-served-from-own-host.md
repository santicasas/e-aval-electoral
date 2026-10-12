# 0008 — Frontend served from the application host, not GitHub Pages

Status: Accepted (supersedes the initial GitHub Pages idea).

## Context
GitHub Pages cannot set custom HTTP response headers. A `<meta>` CSP ignores `frame-ancestors`, and
`X-Frame-Options`, `Cache-Control` and others cannot be set at all. GitHub/its CDN also terminates TLS and
sees visitor IPs, conflicting with "no TLS-terminating intermediary" and "zero third parties" on aval pages.

## Decision
The frontend stays static, configurable per candidacy and without runtime external dependencies, but is
served by a reverse proxy (Caddy or nginx) on the same host, with the full security header set.
GitHub Pages may host a public informational site only.

## Consequences
One origin per candidacy, `connect-src 'self'` plus AutoFirma's local socket. The PoC tests the page with
real headers locally; a Pages deployment would only be tested with meta CSP for comparison.
