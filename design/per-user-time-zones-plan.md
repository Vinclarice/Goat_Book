# Per-user time zones — delivery plan

**Deployed August 1, 2026, and verified in production the same morning at 07:00
WITA** — the first real exercise of a user's own day boundary.

Its one gap outlived it by two weeks: token-authenticated requests were outside
the middleware, and five date-bearing endpoints each failed to activate the
owner's zone themselves. That is `commercial-blueprint.md` defect 2, fixed
August 14 in `accounts.auth._resolve_scoped_token` — the seam both token paths
converge on, rather than at each endpoint.

This is a stub. See [`roadmap-history.md`](roadmap-history.md) under *Bittern*.

Reduced to a stub on August 16, 2026. See [`README.md`](README.md).
