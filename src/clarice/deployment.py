"""Decisions about how *this* checkout runs, kept as functions with tests.

Kept out of settings.py so this decision is a function with a test rather
than a branch in a config file, the same reasoning monitoring.py already
gives for its own split. See clarice/tests/test_deployment.py.
"""

import hashlib

# Both get production-grade settings: a required SECRET_KEY, secure
# cookies, HSTS, and no debug tracebacks. They differ only in
# clarice/monitoring.py, which reports exclusively for the literal string
# "production" -- staging stays off Sentry so its own noise never buries a
# real incident.
_PRODUCTION_GRADE_ENVIRONMENTS = ("production", "staging")


def is_debug(deployment_environment):
    """False only for a recognised, deliberately-promoted environment.

    Fails safe: an unset or mistyped DJANGO_ENVIRONMENT stays in DEBUG
    mode rather than silently granting production-grade settings to
    somewhere nobody meant to promote.
    """
    return deployment_environment not in _PRODUCTION_GRADE_ENVIRONMENTS


# Postgres truncates identifiers at 63 bytes without complaining, so two long
# names can arrive at the same one -- the exact collision this exists to stop.
# Eight hex characters of a path digest is 1 in 4 billion between two checkouts
# on one machine, and leaves the name short enough to read in a log.
_CHECKOUT_TOKEN_LENGTH = 8


def test_database_name(*, database_name, base_dir, override=None):
    """What to call the test database, so two checkouts cannot share one.

    Django names it `test_<database>`, which is a constant -- so the main
    checkout and every worktree ask one Postgres for the same database, and the
    second run to start either finds it present and asks a question nothing can
    answer, or has it dropped mid-suite by the first one's teardown. Both were
    observed on August 19, 2026, and the second reads like a broken migration
    rather than like contention.

    **Derived by default rather than opt-in.** `DJANGO_TEST_DB_SUFFIX` came
    first and still works, as `override`; it fixed the collision for anyone who
    remembered to set it, which is the wrong set of people, since the runs that
    collide are the uncoordinated ones.

    Two properties make the derived default safe, and both are tested:

    - **Stable** for a given checkout, so a laptop keeps one test database per
      checkout rather than accumulating an orphan per run. This was the
      objection to deriving it at all, and it only applies to a default that
      changes every time.
    - **Different** between checkouts, which is what a worktree is.

    CI is unaffected in substance: it runs one checkout against its own
    Postgres, so it creates exactly one database as before, under a name that
    happens to carry a digest.
    """
    if override:
        return f"test_{database_name}_{override}"

    digest = hashlib.sha256(str(base_dir).encode("utf-8")).hexdigest()
    return f"test_{database_name}_{digest[:_CHECKOUT_TOKEN_LENGTH]}"
