# 0005 — OVH Madrid hosting

Status: Accepted. **Offer unverified.**

## Decision
VPS at OVH in the Madrid Local Zone (data in Spain), Docker Compose deployed from GitHub Actions. Personal OVH
account, separate from any company. Encrypted backups to OVH Object Storage in a French region.

## Open point
Local Zones may belong to Public Cloud instances rather than the classic VPS range. Verify the offer,
provisioning time and domain/DNS (European DNS provider, no Cloudflare, no TLS-terminating intermediary)
before depending on it. Until then PoC resource tests run in Docker with CPU/memory limits.
