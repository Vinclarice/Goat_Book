"""Which DJANGO_ENVIRONMENT values run with DEBUG off.

Kept out of settings.py so this decision is a function with a test rather
than a branch in a config file, the same reasoning monitoring.py already
gives for its own split. See clarice/tests/test_deployment.py.
"""

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
