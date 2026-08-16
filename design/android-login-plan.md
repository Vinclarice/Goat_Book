# Logging in from the app, instead of pasting a token

**Shipped and deployed August 6, 2026.** `POST /api/v1/login` trades a password
for a token once, routed through `authenticate()` so axes' lockout covers it
exactly as it covers the web form.

Its one non-obvious rule still holds and is cited in both codebases: axes answers
a lockout with its own JSON body when the request carries
`X-Requested-With: XMLHttpRequest`, which is why `OkHttpClariceApi` sends it.

This is a stub. See [`roadmap-history.md`](roadmap-history.md) under
*After Dunlin*.

Reduced to a stub on August 16, 2026. See [`README.md`](README.md).
