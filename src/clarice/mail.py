"""Sending mail over Resend's HTTP API, because SMTP cannot leave this droplet.

DigitalOcean drops outbound 25, 465 and 587 on every Droplet. Measured from
production on August 18, 2026: all three blocked, ordinary outbound fine, and an
unauthenticated `POST https://api.resend.com/emails` answering 401 from that same
host — the request arrives and is refused only for credentials. The full
diagnosis, and what it was costing, is in `design/mail-transport-plan.md`.

**A backend rather than a new function to call**, so nothing else moves. Four
`EmailMessage(...).send()`, two `mail_admins()`, one `send_mail()` and Django's
own `PasswordResetView` all route through whatever `EMAIL_BACKEND` names.

Kept out of `settings.py` for the reason `monitoring.py` gives one file over:
the decision is a function with a test, not a branch in a config nobody runs the
suite against.

**No new dependency.** `requirements.txt` has ten entries and no HTTP client,
and this is one POST with a JSON body and a bearer header, which
`urllib.request` has done since forever.
"""
import hashlib
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


ENDPOINT = "https://api.resend.com/emails"

# Identifies this application to Resend, and gets past the edge in front of it.
# Anything that is not urllib's default would do; saying who is calling is the
# more useful of the two reasons.
USER_AGENT = "Clarice/1.0 (+https://vinclarice.com)"


class ResendError(Exception):
    """A message did not go, whatever the reason.

    One class for refusals, non-2xx answers and transport failures alike,
    because every caller's question is the same one: did this leave. What kind
    of failure it was belongs in the message, where a Sentry event will carry
    it.
    """


def resend_transport():
    """The real POST, resolved separately so no test opens a socket.

    Same arrangement as `monitoring.sentry_initialiser`: the backend takes this
    as an injectable, one test asserts the default *is* this, and one asserts on
    the request it would build without making it.

    Returns `(status, body)` rather than raising, because `urlopen` raises
    `HTTPError` on 4xx and the body is where Resend explains itself — a 403
    saying `invalid_api_key` and a 400 naming the bad field are different
    incidents, and losing that leaves an event that says only "it failed".
    Deciding what a status *means* is the backend's job, and is tested there.
    """

    def post(payload, *, api_key, timeout, idempotency_key):
        request = Request(
            ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                # Resend dedupes on this for 24 hours. See the backend's
                # `_idempotency_key` for why it is worth taking.
                "Idempotency-Key": idempotency_key,
                # Named, because urllib's default is refused at the edge.
                # Cloudflare fronts api.resend.com and blocks `Python-urllib`
                # by signature -- HTTP 403 with a body of "error code: 1010",
                # which is Cloudflare's, not Resend's, and never reaches them.
                # Verified from production on 2026-08-18: that agent 403s while
                # every other value, including no User-Agent at all, gets a
                # normal 422 for the same malformed payload.
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.status, response.read().decode("utf-8", "replace")
        except HTTPError as refused:
            return refused.code, refused.read().decode("utf-8", "replace")

    return post


_TRANSPORT = resend_transport()


class ResendBackend(BaseEmailBackend):
    """Django's email backend contract, answered by an HTTPS request.

    `fail_silently` is honoured rather than ignored: it is part of the contract
    and Django's own code passes it.
    """

    def __init__(self, fail_silently=False, transport=None, **kwargs):
        super().__init__(fail_silently=fail_silently)
        # Module-level default rather than a fresh closure per instance, so
        # `backend.transport is resend_transport()` is a fact a test can assert.
        self.transport = transport or _TRANSPORT

    def send_messages(self, email_messages):
        """Send each, and return how many actually left."""
        sent = 0
        for message in email_messages or []:
            # Django's SMTP backend skips these too. An API call with an empty
            # `to` is a 400 for a message nobody was owed.
            if not message.to:
                continue
            try:
                self._send(message)
            except ResendError:
                if not self.fail_silently:
                    raise
                continue
            sent += 1
        return sent

    def _send(self, message):
        api_key = getattr(settings, "RESEND_API_KEY", "")
        if not api_key:
            # Named rather than posted anonymously. An unauthenticated send is
            # a 401 for every message until somebody reads the events, and the
            # setting is the thing to look at.
            raise ResendError("RESEND_API_KEY is not set; refusing to send.")

        payload = self._payload(message)
        try:
            status, body = self.transport(
                payload,
                api_key=api_key,
                timeout=settings.EMAIL_TIMEOUT,
                idempotency_key=self._idempotency_key(payload),
            )
        except ResendError:
            raise
        except Exception as failure:
            # A timeout, a DNS failure, a reset -- which is exactly what the
            # SMTP backend was producing for three days before anybody knew the
            # port was blocked.
            raise ResendError(f"Could not reach Resend: {failure!r}") from failure

        if not 200 <= status < 300:
            # B4's evening, guarded. A provider returned success for a message
            # it had discarded and every mechanism this project owned reported
            # a clean send; treating Resend's 403 or 429 as delivery would be
            # that failure again with a new transport.
            raise ResendError(f"Resend refused the message: HTTP {status} {body}")

    def _payload(self, message):
        """The documented fields, and a refusal for anything else.

        Nothing in the tree attaches a file or sends HTML. These raise so that
        the day somebody does, they find out at once rather than shipping mail
        with the attachment missing -- the same instinct as
        `commitments._UNHOLDABLE`, where widening the rule means deleting a
        line first.
        """
        if message.attachments:
            raise ResendError(
                "This backend cannot send an attachment. Add support for "
                "Resend's `attachments` field rather than dropping it."
            )
        if getattr(message, "alternatives", None):
            raise ResendError(
                "This backend cannot send an HTML alternative. Map it to "
                "Resend's `html` field rather than sending only the text."
            )
        if message.content_subtype != "plain":
            raise ResendError(
                f"This backend sends text/plain, not text/{message.content_subtype}."
            )

        payload = {
            "from": message.from_email,
            "to": list(message.to),
            "subject": message.subject,
            # `text`, never `html`: Resend generates one from the other, and a
            # plain body sent as HTML would render somebody's newlines away.
            "text": message.body,
        }
        # Absent rather than empty. Nothing sends cc or bcc today; they are
        # mapped rather than refused because Resend has both natively, and a
        # bcc that vanished silently is the quiet kind of wrong.
        for field in ("cc", "bcc", "reply_to"):
            value = getattr(message, field, None)
            if value:
                payload[field] = list(value)
        return payload

    @staticmethod
    def _idempotency_key(payload):
        """A stable fingerprint of the message, so a retry cannot double-send.

        The digest deliberately does not stamp `last_digest_date` when a send
        fails, so it tries again the next hour -- and a request that timed out
        *after* Resend accepted it would otherwise deliver a second copy.

        Over the whole payload, not the body: the digest sends near-identical
        mail to several people, and keying on the body alone would deliver to
        the first and dedupe the rest.

        The trade, stated: two byte-identical messages to the same address
        inside 24 hours collapse into one. For a digest whose body carries the
        date, and a contact form, that is the cheaper mistake.
        """
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
