"""Which operations a phone can call, held to a list somebody has to edit.

`clarice/api.py` described `lists`, `daily` and `routines` as session-only.
None of them is: fourteen operations across four routers accept a bearer token,
and the Android client calls `/api/v1/agenda`, `/api/v1/day` and
`/api/v1/routines/{id}/log` with one today. The comments were true when written
and nothing noticed them stop being true, because a comment is not checked by
anything.

So the surface gets a test rather than a better comment. This is the same shape
as `test_unauthenticated_endpoints_are_throttled`, which reads `auth_param` to
find operations a stranger can reach: here it reads the resolved auth callbacks
to find the ones a *token holder* can reach.

**Editing the set is the point, not the cost.** Widening what a token reaches is
a security decision — a bearer token sits in an Android keystore and outlives a
session by ninety days — and it should take a deliberate line in a list, next to
a comment in `api.py` that has to be updated with it.
"""
from django.test import SimpleTestCase
from ninja.constants import NOT_SET

from clarice.api import api


def _operations():
    for prefix, router in api._routers:
        for path, view in router.path_operations.items():
            for operation in view.operations:
                for method in operation.methods:
                    yield method, f"/api/v1{prefix}{path}", operation


def token_authenticated():
    """Operations a bearer token can call.

    Read from the resolved callbacks rather than from a decorator's source, so
    this sees what Ninja will actually enforce at request time.
    """
    return {
        (method, path)
        for method, path, operation in _operations()
        if any(
            type(callback).__name__ == "TokenAuth"
            for callback in operation.auth_callbacks
        )
    }


def unauthenticated():
    return {
        (method, path)
        for method, path, operation in _operations()
        if operation.auth_param is None
    }


# Every operation a personal access token can reach, and nothing else.
#
# The phone is the only token client. Slice 1 read the Day, slice 2 added the
# Agenda and acting on it, and routine logging came with them -- which is why
# `api.py`'s note about routine logging "having no product trigger yet" had to
# go: it has one, and this is it.
TOKEN_AUTHENTICATED = {
    # The Agenda, read-only. Writes to a task still go through the session.
    ("GET", "/api/v1/agenda"),
    # Capture, the original reason a token exists at all.
    ("POST", "/api/v1/capture"),
    # The Day, read *and* write -- pinning a focus and writing the day's own
    # words are both things the phone does.
    ("GET", "/api/v1/day"),
    ("GET", "/api/v1/day/{day}"),
    ("PATCH", "/api/v1/day/{day}"),
    ("POST", "/api/v1/day/{day}/focus"),
    # Accepting the day's draft is pinning, in one act instead of five. Same
    # scope, same effect on the same rows -- session-only here would be an
    # asymmetry beside the line above that somebody would later have to undo,
    # and Vince's August 20 call ("on a phone means the Android app too")
    # says that Day screen keeps growing. Added deliberately, which is what
    # this list exists to make somebody do.
    ("POST", "/api/v1/day/{day}/focus/draft"),
    ("DELETE", "/api/v1/day/{day}/focus/{task_id}"),
    # Which account a freshly pasted token belongs to. The one endpoint the
    # Connect screen can call before anything else works.
    ("GET", "/api/v1/me"),
    # Routines: every write, and deliberately not the read. `GET /routines`
    # is session-only, which is worth noticing rather than assuming symmetric.
    ("POST", "/api/v1/routines"),
    ("POST", "/api/v1/routines/{routine_id}/enough"),
    ("POST", "/api/v1/routines/{routine_id}/log"),
    ("POST", "/api/v1/routines/{routine_id}/pause"),
    ("POST", "/api/v1/routines/{routine_id}/resume"),
    ("POST", "/api/v1/routines/{routine_id}/skip"),
}

# `auth=None`. Kept here beside the token set because the two questions get
# asked together, and because this one is already load-bearing elsewhere:
# `test_unauthenticated_endpoints_are_throttled` requires every entry to have
# an nginx rate limit.
UNAUTHENTICATED = {
    ("POST", "/api/v1/login"),
}


class TokenSurfaceTest(SimpleTestCase):
    def test_exactly_these_operations_accept_a_token(self):
        """Both directions in one assertion. An operation that gained token
        auth without being listed is a widening nobody reviewed; one that lost
        it is a phone feature that has silently stopped working."""
        self.assertEqual(token_authenticated(), TOKEN_AUTHENTICATED)

    def test_exactly_these_operations_need_no_account_at_all(self):
        self.assertEqual(unauthenticated(), UNAUTHENTICATED)


class TheSweepActuallySeesTheApiTest(SimpleTestCase):
    """Positive controls.

    Both assertions above compare a computed set to a literal one, so an
    introspection that quietly returned `set()` would make them pass the moment
    somebody emptied the literals to match -- and would read as coverage
    forever. These fail first.
    """

    def test_the_api_has_operations_at_all(self):
        self.assertGreater(len(list(_operations())), 30)

    def test_the_token_set_is_not_empty(self):
        self.assertGreater(len(token_authenticated()), 0)

    def test_most_of_the_api_is_still_session_only(self):
        """The shape worth holding, not just the list. If a refactor ever made
        token auth the default, every assertion above could be 'fixed' by
        pasting in a longer literal; this says the balance itself changed."""
        total = len({(method, path) for method, path, _ in _operations()})

        self.assertLess(len(token_authenticated()), total / 2)

    def test_session_only_operations_carry_no_token_callback(self):
        """A spot check against the introspection itself: the review's own
        endpoints are session-only, and if `token_authenticated()` started
        matching everything this is what would say so."""
        for operation in (("GET", "/api/v1/review"), ("PATCH", "/api/v1/review/{day}")):
            with self.subTest(operation=operation):
                self.assertNotIn(operation, token_authenticated())
