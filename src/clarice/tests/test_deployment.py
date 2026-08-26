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

from clarice.deployment import is_debug, test_database_name


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


class TestDatabaseNameTest(SimpleTestCase):
    """The test database's name, which two checkouts must not share.

    `DJANGO_TEST_DB_SUFFIX` shipped on August 19 as an opt-in: set it and your
    run gets its own database. It fixed the collision for anyone who remembered
    it, which is the wrong set of people -- the runs that collide are the ones
    nobody coordinated, and a session that knew to set the variable was not
    going to be the problem. **The default is what has to be safe.**

    So the default carries the checkout, and the two properties below are what
    make that safe rather than merely different. It must be *stable* for one
    checkout, or a laptop accumulates an orphan database per run; and it must
    *differ* between checkouts, which is what a worktree is.
    """

    def test_two_checkouts_do_not_share_a_test_database(self):
        main = test_database_name(database_name="clarice", base_dir="/repo")
        tree = test_database_name(
            database_name="clarice", base_dir="/repo/.claude/worktrees/increment-1"
        )

        self.assertNotEqual(main, tree)

    def test_one_checkout_always_gets_the_same_name(self):
        """Otherwise every run leaves a database behind, which is the objection
        that kept this opt-in in the first place."""
        first = test_database_name(database_name="clarice", base_dir="/repo")
        second = test_database_name(database_name="clarice", base_dir="/repo")

        self.assertEqual(first, second)

    def test_an_explicit_suffix_wins(self):
        """The opt-in stays: two runs in one checkout still need a way to be
        told apart, and that is the case the derived name cannot see."""
        name = test_database_name(
            database_name="clarice", base_dir="/repo", override="b"
        )

        self.assertEqual(name, "test_clarice_b")

    def test_the_name_is_a_legal_postgres_identifier(self):
        """Postgres truncates identifiers at 63 bytes, silently. Two long
        names truncated to the same 63 bytes would collide exactly the way
        this exists to prevent."""
        name = test_database_name(
            database_name="clarice", base_dir="/" + "d" * 300
        )

        self.assertLessEqual(len(name), 63)
        self.assertRegex(name, r"^[a-z][a-z0-9_]*$")


class HstsIsLongEnoughToProtectAnyoneTest(SimpleTestCase):
    """`security-and-resilience-plan.md` 1.6.

    `settings.py` started at one hour under a comment saying to raise it "only
    once HTTPS is confirmed working end-to-end, per Django's own warning."
    HTTPS has been confirmed for weeks -- certbot renews automatically and the
    playbook exercises it -- and at one hour the header is close to decorative:
    somebody returning the next day has no protection against a downgrade at
    all, which is the attack it exists for.

    **The plan names the habit rather than the instance, and the habit is the
    reason this is a test.** *"A conservative default with a condition attached
    needs somebody holding the condition, or it becomes permanent by
    inattention."* Two of these were found the same week -- this and the CSP's
    report-only mode. An assertion is what holds a condition when nobody is.

    **Preload is deliberately absent.** It is a different decision and a
    genuinely hard one to reverse -- browsers ship the list, so withdrawal takes
    months -- and it belongs to that plan's D4 rather than riding along here.

    Read from the source rather than from `settings`, because the values live in
    the `not DEBUG` branch and the suite runs on the other side of it. The
    pattern is `test_unauthenticated_endpoints_are_throttled.py`'s: a guarantee
    that no import in this process can see.
    """

    def production_branch(self):
        """The `not DEBUG` branch with its comments stripped.

        Stripping matters for `test_preload_is_not_set`, which asserts a name
        is *absent*: the comment explaining why preload is absent names it, so
        the first version of that test failed against the very sentence that
        makes the decision legible. An assertion about code should not be able
        to be broken by prose about the code.
        """
        from pathlib import Path

        settings_source = (
            Path(__file__).resolve().parents[1] / "settings.py"
        ).read_text(encoding="utf-8")
        branch = settings_source[: settings_source.index("\nelse:")]
        return "\n".join(
            line for line in branch.splitlines() if not line.strip().startswith("#")
        )

    def test_hsts_lasts_a_year(self):
        self.assertIn("SECURE_HSTS_SECONDS = 31536000", self.production_branch())

    def test_it_covers_subdomains(self):
        self.assertIn(
            "SECURE_HSTS_INCLUDE_SUBDOMAINS = True", self.production_branch()
        )

    def test_preload_is_not_set(self):
        """Asserted absent rather than merely not asserted present, so turning
        it on has to be a decision somebody takes here and argues for."""
        self.assertNotIn("SECURE_HSTS_PRELOAD", self.production_branch())
