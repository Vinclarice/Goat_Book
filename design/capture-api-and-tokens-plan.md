# Capture API + personal access tokens

Foundation work for a phone-based capture client (Android, to start). Scope
for this pass is exactly two things: a way for a non-browser client to
authenticate as a specific user, and one endpoint for it to call. Not in
scope: the Android app itself, which stays a separate, later decision —
see `design/roadmap.md`'s Track B notes on trying the zero-code
home-screen-shortcut version first.

## Why this is the actual prerequisite

Capture MVP shipped deliberately Django-only: templates, session login, no
API, no SPA route. That was correct for generating usage evidence fast. It
also means there is currently no way for anything other than a logged-in
browser to create a capture. A native client can't carry a session cookie,
so this has to exist before any app — however trivial — can talk to
Clarice.

## Settled decisions

| Question | Decision |
| --- | --- |
| Token storage | Store a hash of the token, never the raw value, matching how passwords are already handled. The raw token is shown exactly once, at creation. |
| Token scope | Whole-account, not endpoint-scoped. At one or two users and one client type, a permissions model is speculative complexity. Revisit if that changes. |
| Revocation | Deleting the row invalidates it. No separate `revoked` boolean — a deleted token and a revoked token are the same state, so don't model two. |
| Where tokens are managed | A small self-service page under account settings (list of labeled tokens with created/last-used dates, a create button showing the raw value once, a delete button per token) rather than admin-only. Cheap to build now, and it's the same self-service instinct the public-readiness bar already calls for elsewhere. |
| Auth mechanism | Runs alongside session auth, not instead of it. The SPA keeps using cookies; only new API surfaces (starting with capture) also accept a bearer token. |
| Rate limiting | Still deferred, same as the rest of the quality bar. Fine at this scale; revisit before anything public. |

## Model

```python
# accounts/models.py
import hashlib
import secrets

class PersonalAccessToken(models.Model):
    owner = models.ForeignKey(
        "accounts.User", related_name="tokens", on_delete=models.CASCADE
    )
    label = models.CharField(max_length=100, blank=True)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    @staticmethod
    def generate(owner, label=""):
        raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        instance = PersonalAccessToken.objects.create(
            owner=owner, label=label, token_hash=token_hash
        )
        return instance, raw  # raw is only ever available here, at creation
```

`secrets.token_urlsafe` over `uuid4` — it's built for exactly this
(cryptographically strong, URL-safe). SHA-256 over bcrypt/argon2 for the
hash: this is a high-entropy random token, not a human-chosen password, so
there's nothing for a slow hash to protect against that a fast one doesn't
already prevent by sheer key space.

## Auth wiring

Django Ninja's `HttpBearer` is the right shape — it already knows how to
pull `Authorization: Bearer <token>` and hand the value to an
`authenticate()` method:

```python
# capture/auth.py
from ninja.security import HttpBearer

class TokenAuth(HttpBearer):
    def authenticate(self, request, token):
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        try:
            pat = PersonalAccessToken.objects.select_related("owner").get(
                token_hash=token_hash
            )
        except PersonalAccessToken.DoesNotExist:
            return None
        pat.last_used_at = timezone.now()
        pat.save(update_fields=["last_used_at"])
        request.user = pat.owner
        return pat.owner
```

The capture router accepts both this and Django's existing session auth, so
the same endpoint works from a logged-in browser tab and a token-bearing
client without two code paths.

## Endpoint

```
POST /api/v1/capture
{"text": "..."}
-> 201 {"id": ..., "created_at": ...}
```

Create-only. No list, no resolve, no edit via the API in this pass — the
Inbox page stays the only way to review and triage what's been captured.
Reuses the same "don't allow empty/whitespace-only text" rule `CaptureForm`
already enforces; worth factoring that one validation into somewhere both
the form and the endpoint call, rather than duplicating the rule in two
places that can drift.

## Isolation

Nothing here takes an id in the path or body representing someone else's
data — every capture is created for whichever user the token (or session)
resolves to, and there's no way to address another user's capture through
this endpoint at all. That's a materially smaller attack surface than
`parent` was, so this doesn't need its own adversarial suite the way
subtasks did. Two tests are enough: a valid token creates a capture owned
by that token's user, and a missing/invalid/deleted token gets 401, not a
500 or a silent fallback to session auth.

## Sequencing

1. `PersonalAccessToken` model + migration.
2. `TokenAuth` + the capture endpoint, tested standalone (curl/Postman)
   before any client exists.
3. The token self-service page (create/list/revoke).
4. Only after 1–3 are live: try the zero-code home-screen-shortcut
   experiment from `design/roadmap.md` first. If that alone solves the
   actual friction, the case for building a native app at all gets weaker,
   not stronger — worth knowing before writing any Kotlin.

## Non-goals

- No endpoint-scoped permissions.
- No refresh tokens / expiry — a token lives until deleted.
- No rate limiting on the new endpoint (tracked, deferred, same as the rest
  of the quality bar).
- No Android app in this pass. This is the two pieces of ground it needs to
  stand on, nothing more.
