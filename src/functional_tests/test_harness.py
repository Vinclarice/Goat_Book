"""The live server must not share the test's database connection.

Not a smoke test -- a guard on the harness the smoke tests run in, and the
reason it exists is a CI failure that looked like a UI bug:

    playwright._impl._errors.TimeoutError: Page.fill: Timeout 10000ms
    exceeded. waiting for locator("#agenda-add-text")

The page never rendered because /api/v1/agenda had 500'd, and the traceback
underneath was not application code at all -- it was Django loading a
*session* row, a three-column table:

    django/db/models/sql/compiler.py, in apply_converters
        value = row[pos]
    IndexError: list index out of range

Reading past the end of a row is what interleaved statements on one cursor
look like. `manage.py test` puts SQLite in memory by default, and
`LiveServerTestCase._make_connections_override` hands that in-memory
connection straight to the server thread, because an in-memory database is
invisible to any other connection. `ThreadedWSGIServer` then serves each
request on its own thread. Django marks the connection thread-shareable,
which suppresses the guard that would have complained -- it does not
serialise the queries.

So the suite was one connection driven by several threads, and it failed
roughly one run in three. The fix is in this package's __init__: give the
test database a filename, so it is no longer in-memory, so Django does not
share it and every thread opens its own.

This test asserts the condition rather than the symptom, because the
symptom is a race and a race cannot be asserted on directly.
"""
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections


class LiveServerConnectionTest(StaticLiveServerTestCase):
    """Deliberately not a BrowserTest: no page is needed to prove this, and
    a second Chromium launch would cost more than the check is worth."""

    def test_the_server_thread_gets_its_own_database_connection(self):
        self.assertEqual(
            self.server_thread.connections_override,
            {},
            "The live server is sharing the test's connection. Concurrent "
            "requests will interleave on one cursor -- see this module's "
            "docstring.",
        )

    def test_the_test_database_is_not_in_memory(self):
        # The condition behind the override above, asserted separately so a
        # failure says which half broke. Postgres has no in-memory mode and
        # no is_in_memory_db() at all -- __init__.py's own
        # _name_the_test_database() already leaves it alone for exactly
        # that reason, so this assertion only means something on SQLite,
        # which local dev no longer runs by default
        # (design/architecture-trajectory.md §6).
        if "sqlite" not in connections["default"].settings_dict["ENGINE"]:
            self.skipTest("Only SQLite can be in-memory; not the engine under test here.")
        self.assertFalse(connections["default"].is_in_memory_db())
