"""Production error reporting.

Kept out of settings.py so the decision to switch monitoring on is a
function with a test rather than a branch in a config file. See
design/bittern-plan.md, B4.
"""


def sentry_initialiser():
    """The real SDK's init, imported only when it is actually going to be
    used.

    Deferred rather than imported at module scope so that development and
    the test suite never load the SDK at all -- there is no instrumentation
    to accidentally activate and nothing to mock away.
    """
    import sentry_sdk

    return sentry_sdk.init


def initialise(*, dsn, environment, release, initialiser=None):
    """Switch on error reporting, and report whether it was switched on.

    Both conditions are required, and the second is not redundant. A DSN
    can reach a development environment easily -- copied into a local
    .env, inherited from a shell, pasted while debugging -- and if it did,
    a developer's own broken experiments would report into the production
    project and bury real incidents under noise from a laptop. Guards fail
    closed: an uncertain environment gets no reporting rather than
    reporting into the wrong place.
    """
    if not dsn or environment != "production":
        return False

    if initialiser is None:
        initialiser = sentry_initialiser()

    initialiser(
        dsn=dsn,
        environment=environment,
        # Without a release an event says something broke but not in which
        # deploy, which is most of what makes it actionable.
        release=release,
        # Usernames and cookies. It does **not** cover request bodies, which
        # the comment here used to claim it did -- see max_request_body_size
        # below, and read `should_send_default_pii()` in the SDK's
        # `_wsgi_common.extract_into_event`, where it gates the cookie line
        # and nothing else.
        send_default_pii=False,
        # And this is the one the line above does not cover, which the
        # comment here used to claim it did. `include_local_variables` is
        # independent of `send_default_pii` and defaults to **True**, so
        # every stack frame in a 500 shipped its locals -- on a capture or
        # daily-entry path that is `text`, `intentions`, `notes`: somebody's
        # unfiltered thinking, sent to a third party by code documented as
        # not doing that. commercial-blueprint.md defect 10.
        #
        # Passed explicitly rather than trusted to stay False, because the
        # default belongs to a dependency: silence here is a decision made
        # by whoever last released the SDK.
        #
        # It costs real debugging power, and that is the trade being made
        # knowingly. A traceback without locals says where a 500 happened
        # but not what value caused it. The material this application holds
        # is worth more than the shorter investigation.
        include_local_variables=False,
        # The third one, and the same trap a second time: an option the line
        # above was documented as covering and does not. `request_info["data"]`
        # is set unconditionally in `extract_into_event`; the only thing
        # standing between a request body and a third party is this, and it
        # defaults to "medium" -- ten kilobytes, which is every captured
        # thought, every day's intentions and every task note this
        # application holds. A 500 on POST /api/v1/capture, POST /mind/ or
        # POST /api/v1/day sent the text itself.
        #
        # "never" rather than "small": there is no size at which somebody's
        # writing becomes safe to forward, and the debugging value of a body
        # we already refuse to keep locals for is not worth the trade.
        max_request_body_size="never",
    )
    return True
