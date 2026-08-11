"""Which DJANGO_ENVIRONMENT values get production-grade settings.

Pulled out of settings.py for the same reason monitoring.py was: the
decision is a function with a test, not an inline branch in a config file
nobody runs the test suite against directly. Written for the staging
environment (design/staging-environment-plan.md): settings.py's own
DEBUG = DEPLOYMENT_ENVIRONMENT != "production" would have forced staging
into DEBUG mode -- a real security problem on a publicly reachable host,
since DEBUG serves tracebacks, defaults to a guessable SECRET_KEY, and
skips HSTS/secure-cookie settings -- or, if staging were given the literal
value "production" instead to dodge that, would have reported its own
errors into the same Sentry project production uses
(clarice/monitoring.py already refuses everything but exactly
"production" for that reason, and stays untouched here).
"""
from django.test import SimpleTestCase

from clarice.deployment import is_debug


class IsDebugTest(SimpleTestCase):
    def test_production_is_not_debug(self):
        self.assertFalse(is_debug("production"))

    def test_staging_is_not_debug(self):
        self.assertFalse(is_debug("staging"))

    def test_development_is_debug(self):
        self.assertTrue(is_debug("development"))

    def test_an_unrecognised_value_fails_safe_into_debug(self):
        # A typo'd or missing DJANGO_ENVIRONMENT must not silently grant
        # production-grade settings (which require DJANGO_SECRET_KEY,
        # DJANGO_ALLOWED_HOST and DJANGO_DATABASE_URL to even boot) to an
        # environment nobody deliberately promoted.
        self.assertTrue(is_debug("some-typo"))
