"""Every unauthenticated endpoint is throttled before it reaches Django.

`nginx-clarice.conf.j2` states the architecture in its own header — *"First
line of defense against brute-forcing login/signup: throttle by client IP
before the request even reaches Django. django-axes is the second line"* — and
`settings.py` repeats it: *"nginx's rate limiting is what handles the by-IP
case."* Both were false for `/api/v1/login`, which trades a password for a
90-day all-scopes token and matched only the catch-all `location /`.

`architecture-trajectory.md` §6 records closing exactly this hole for `/` on
August 3. The API login shipped three days later without a matching rule,
because nothing connected the two facts. This test is that connection: it reads
the real template and the real API, so a new `auth=None` operation cannot ship
without a throttle again.

The pattern — a `SimpleTestCase` asserting on a file outside `src/` — is
`lists/tests/test_frontend_style_contract.py`'s, for the same reason: the
guarantee spans two languages and neither compiler can see the other.
"""
import re
from pathlib import Path

from django.test import SimpleTestCase

from clarice.api import api


NGINX_TEMPLATE = (
    Path(__file__).resolve().parents[3] / "infra" / "templates" / "nginx-clarice.conf.j2"
)

# `location = /path {` — nginx's exact match, which beats every prefix and
# regex block regardless of order. The existing `= /` and `= /contact/` rules
# use it for the same reason: it is the only matcher that cannot be
# accidentally shadowed by a later edit.
EXACT_LOCATION = re.compile(
    r"location\s*=\s*(?P<path>\S+)\s*\{(?P<body>[^}]*)\}", re.MULTILINE
)


def throttled_exact_paths():
    """Paths with an exact-match block that actually spends a rate limit."""
    config = NGINX_TEMPLATE.read_text(encoding="utf-8")
    return {
        match.group("path")
        for match in EXACT_LOCATION.finditer(config)
        if "limit_req" in match.group("body")
    }


def unauthenticated_api_paths():
    """Operations that set `auth=None` explicitly, rather than inheriting the
    API's `django_auth`.

    `auth_param` is the discriminator: Ninja records `NOT_SET` for an
    operation that inherits and `None` for one that opts out, and only the
    second kind can be called by a stranger.
    """
    paths = set()
    for prefix, router in api._routers:
        for path, view in router.path_operations.items():
            for operation in view.operations:
                if operation.auth_param is None:
                    paths.add(f"/api/v1{prefix}{path}")
    return paths


class UnauthenticatedEndpointsAreThrottledTest(SimpleTestCase):
    def test_every_unauthenticated_api_operation_has_a_rate_limit(self):
        """The guard for the whole class. Adding an `auth=None` operation
        without a matching nginx rule fails here rather than in production."""
        unthrottled = unauthenticated_api_paths() - throttled_exact_paths()

        self.assertEqual(
            unthrottled,
            set(),
            f"unauthenticated and unthrottled: {sorted(unthrottled)}",
        )

    def test_the_sweep_actually_finds_the_login_endpoint(self):
        """Guards the test above from passing vacuously. If the introspection
        breaks — a Ninja upgrade renaming `auth_param`, a router restructure —
        the set goes empty and every unthrottled endpoint passes silently."""
        self.assertIn("/api/v1/login", unauthenticated_api_paths())

    def test_the_sweep_actually_reads_the_config(self):
        """The same guard from the other side: an unreadable or restructured
        template would make `throttled_exact_paths` empty, which fails loudly
        above rather than quietly here — but a regex that silently matched
        nothing would not."""
        self.assertIn("/", throttled_exact_paths())

    def test_the_password_reset_is_throttled_too(self):
        """Not an API route, so the sweep above cannot see it: it is a Django
        view, it is reachable without an account, and it sends mail
        synchronously. Same shape as the login hole, lower severity, and named
        here so it is covered rather than remembered."""
        self.assertIn("/accounts/password/reset/", throttled_exact_paths())
