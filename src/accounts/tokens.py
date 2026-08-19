"""The activation link's token.

Stateless, and deliberately so: `architecture-trajectory.md` §4 asks that a
concept earn its own model by having a different life cycle, and a token whose
whole existence is "this URL is valid until it is used" has no life cycle at
all. Django's generator signs the user's current state with a timestamp, so
the link's validity is derived rather than stored -- nothing to create, nothing
to expire by cron, and nothing left in a table for an account that never came
back.
"""

from django.contrib.auth.tokens import PasswordResetTokenGenerator


class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    """A single-use link, and `is_active` is what makes it single-use.

    The base class hashes the password and `last_login`, which is what stops a
    password-reset link working twice. Neither changes when an account is
    verified, so without adding something that does, an activation link would
    stay valid for its whole timeout -- sitting in an inbox, in a forwarded
    message, in a screenshot pasted into a chat -- and every copy would be a
    way into the account.

    `email_confirmed_at` is set exactly once, by the transition this token
    authorises, which makes it the right thing to sign: using the link
    invalidates it.

    **Not `is_active`.** That is approval, and approval happens later and by
    somebody else -- signing it would leave a confirmation link valid through
    the whole review window, which is the stretch during which it is most
    likely to be sitting unread in an inbox.

    The timeout is `PASSWORD_RESET_TIMEOUT`, shared with the reset flow. Three
    days is on the short side for "check your email" and the setting is one
    value for both; if that becomes a real complaint the fix is a separate
    setting, not a longer default for password resets.
    """

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.password}{user.last_login}{timestamp}{user.email_confirmed_at}"


activation_token = AccountActivationTokenGenerator()
