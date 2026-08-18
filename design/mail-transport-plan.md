# Mail over HTTPS, because SMTP cannot leave this droplet

Vince · brief · written August 18, 2026 · **designed, not started**

## 1. State, and it is not intermittent

Three Sentry reports in three days read as a flaky relay. They are not. Measured
from the production droplet, read-only, on August 18:

```
BLOCKED  resend smtp   (54.205.195.44:587) after 8s
BLOCKED  resend smtp   (54.157.71.137:587) after 8s
BLOCKED  resend smtps  (54.205.195.44:465) after 8s
BLOCKED  resend smtp/25(54.205.195.44:25)  after 8s
OPEN     cloudflare    (1.1.1.1:443)       in 0s
OPEN     github        (140.82.121.4:443)  in 1s
```

All three SMTP ports are dropped; ordinary outbound is fine. That is
DigitalOcean's default on every Droplet — ports 25, 465 and 587, lifted only by
support ticket. It is a silent drop rather than a refusal, which is why the
application saw connect timeouts and not errors.

**Every detail of the incidents follows from it.** `smtp.resend.com` resolves to
exactly two IPv4 addresses, and `socket.create_connection` walks them until the
kernel exhausts its SYN retries at ~127s each — 2 × ~135s ≈ the 271 seconds
between the first breadcrumb and the `TimeoutError`, with `raise exceptions[0]`
firing because both failed. Resend itself is healthy: both addresses answer from
an ordinary network in 0.15s with `220 Resend SMTP Relay ESMTP`.

Only three reports arrived because the digest skips users with nothing due and
the contact form is rarely used, not because it usually works.

## 2. What is actually broken

Worse than a missing digest, and two of these got *safer* with the August 18
deploy in a way that makes them unusable rather than dangerous:

| Path | Today |
|---|---|
| Daily digest | fails; caught, logged, reported (D6/D11) |
| Contact form | fails; visitor keeps their text and is given the support address (D-contact) |
| Signup admin notice | fails; signup completes, logged |
| **Password reset** | **unguarded 500 — nobody locked out can recover an account** |
| **Account deletion** | warning fails → `request_deletion` rolls back (D10). Cannot be scheduled at all |
| **Account erasure** | receipt fails inside `purge_account`'s transaction → erasure rolls back. A standing obligation that cannot complete |

The last three are the reason this is not "the digest is broken".

## 3. The decision: send over Resend's HTTP API

Verified reachable from the droplet — `POST https://api.resend.com/emails`
without credentials returns **401**, so the request arrives and is rejected only
for auth. Port 443, which is open.

**Refused: asking DigitalOcean to unblock.** It is a support ticket with no
guarantee, it leaves the application one policy decision away from this outage
again, and DigitalOcean's own guidance is to use a provider's API rather than
outbound SMTP.

**Refused: a queue or an outbox table.** It is the right answer at a scale this
does not have, and it converts every send into two moving parts. The transport
is what is broken; fix the transport.

**Refused: a new dependency.** `requirements.txt` has ten entries and no HTTP
client. One `POST` with a JSON body and a bearer header is `urllib.request`,
which is already there.

## 4. The backend

`src/clarice/mail.py`, beside `monitoring.py` and `deployment.py`, for the reason
`monitoring.py`'s own docstring gives: kept out of `settings.py` so the decision
is a function with a test rather than a branch in a config file.

A `BaseEmailBackend` subclass implementing `send_messages(messages) -> int`.
Every existing caller — four `EmailMessage(...).send()`, two `mail_admins()`,
one `send_mail()`, and Django's own `PasswordResetView` — keeps working
unchanged, because they all go through the configured backend.

**The mapping is small because the surface is small.** Nothing in the tree sends
HTML, attachments, cc or bcc; one message sets `reply_to`.

| `EmailMessage` | Resend |
|---|---|
| `from_email` | `from` |
| `to` | `to` |
| `subject` | `subject` |
| `body` | `text` |
| `reply_to` | `reply_to`, omitted when empty |

**It refuses what it cannot faithfully send.** An attachment or an HTML
alternative raises rather than sending a degraded message, so the day somebody
adds one they find out immediately instead of shipping mail with the attachment
missing. Same instinct as `commitments._UNHOLDABLE`: the next person to widen
this should have to delete a line first.

**Four things it must get right, each with a test:**

- **`fail_silently`.** Part of the backend contract and Django's own code relies
  on it. Honoured, not ignored.
- **A bounded request.** `settings.EMAIL_TIMEOUT` passed to `urlopen`, for the
  reason it was introduced two days ago: an unbounded send on a request thread,
  on one worker with four of them.
- **A non-2xx is a failure.** Resend answers `403` for a bad key and `429` when
  rate limited; a backend that returns success on either is the "SMTP returned
  200 and the message was discarded" failure that `bittern-plan.md` B4 exists
  because of.
- **An injectable transport**, following `monitoring.py`'s `sentry_initialiser`:
  no test opens a socket, and one test resolves the real thing.

**`Idempotency-Key`, derived from a hash of the message.** Resend accepts one and
dedupes for 24 hours. This is worth taking because the failure it guards was
observed: on a failed send the digest deliberately does *not* stamp
`last_digest_date`, so it retries the next hour — and a request that timed out
*after* Resend accepted it would otherwise deliver twice. The trade, stated: two
byte-identical messages to the same address inside 24 hours collapse into one.
For a digest whose body carries the date, and a contact form, that is a case
worth losing.

## 5. Slices

1. **The backend and its tests.** `clarice/mail.py`, no wiring. Includes the
   refusals, `fail_silently`, the timeout, the non-2xx rule, and the real-SDK-style
   test that the transport resolves.
2. **Wire it.** `DJANGO_EMAIL_BACKEND` gains `resend` alongside `smtp` and
   `console`; the key arrives as `DJANGO_RESEND_API_KEY` rather than being reused
   through `DJANGO_EMAIL_HOST_PASSWORD`, which names it for what it is. The
   playbook already reads `~/.resend-api-key` and needs one variable renamed.
3. **Guard the password reset.** Independent of transport and a hole either way:
   Django's `PasswordResetView` 500s on a send failure, on a public page, for the
   person least able to work around it. A subclass that catches and re-renders,
   the same shape the contact form now uses.
4. **Deploy and verify in production** — §6.

Slices 1 and 2 are one commit's worth of work each. Slice 3 is separable and
could go first if the reset hole is judged more urgent than the transport.

## 6. Verification

The suite cannot prove this; the block is real and only production is behind it.

- `send_due_digest --username <vince> --send-hour 0 --until-hour 24` after
  deploy, and the mail arrives or it does not.
- The contact form from a browser, which exercises the request-thread path
  rather than the cron one.
- A read-only re-run of §1's probe, expecting SMTP still blocked and 443 open —
  so the fix is demonstrably independent of the block rather than coincident
  with it being lifted.

## 7. Rollback

`DJANGO_EMAIL_BACKEND` back to `smtp` and redeploy. The SMTP backend is not
deleted, it is deselected — which also means the day DigitalOcean unblocks the
ports, nothing has to be rewritten to use them.

## 8. Out of scope, deliberately

- **Retries and a queue.** §3.
- **Batch sending.** Resend has `/emails/batch`; the digest sends one per user
  and at three users the loop is not the problem.
- **HTML mail.** Nothing sends it today and the backend refuses it loudly, which
  is the trigger for revisiting this rather than a gap in it.
- **Inbound mail.** There is none, and `contact` is deliberately not a ticketing
  system.
