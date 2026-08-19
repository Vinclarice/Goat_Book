# Mail over HTTPS, because SMTP cannot leave this droplet

**Shipped and verified in production August 18, 2026** (`jackdaw`). DigitalOcean
blocks outbound 25, 465 and 587 on every Droplet, so no mail had left the host
for at least three days. The transport moved to Resend's HTTPS API; the drill
that proves it is that SMTP is *still* blocked and mail still goes.

This is a stub. See [`roadmap-history.md`](roadmap-history.md) under
*The mail transport*.

Reduced to a stub on August 18, 2026. See [`README.md`](README.md).
