# Personal access token scopes and expiry

**Shipped and deployed August 11, 2026.** Every token carries an explicit scope
set and an expiry; there is no scope-blind default, so an endpoint that forgets
to think about scope fails to construct rather than quietly accepting anything.

This is a stub. The narrative is in [`roadmap-history.md`](roadmap-history.md)
under *After Dunlin*.

Twenty-four comments cite this plan, most of them at the seams `§7` describes —
`token_or_session_required`, and the scope-creep note that keeps a token from
reaching `item_detail`'s DELETE.

Reduced to a stub on August 16, 2026. See [`README.md`](README.md).
