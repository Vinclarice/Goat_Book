# Capture API + personal access tokens

**Shipped in the Albatross/Bittern era.** It established `POST /api/v1/capture`
and the personal access token that authenticates it — both of which survive, and
neither of which still does what this plan described.

The endpoint writes a `Node` rather than a `Capture` (Heron 4a, August 15), and
the token gained scopes and an expiry (August 11). Its create-only rule holds:
reviewing what has been captured stays off this endpoint, because a phone client
exists to get a thought out of your head in three seconds.

This is a stub. See [`roadmap-history.md`](roadmap-history.md) under *Albatross*
and *Heron*.

Reduced to a stub on August 16, 2026. See [`README.md`](README.md).
