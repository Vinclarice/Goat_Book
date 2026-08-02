"""Browser smoke tests.

Playwright's synchronous API drives the browser from a greenlet, which
Django's ORM guard cannot distinguish from a real async context -- so every
query, including the ones the test runner itself makes while flushing the
database between tests, raises SynchronousOnlyOperation. Django documents
this environment variable as the way out.

Set here rather than in the runner or in CI so that it applies exactly when
this package is imported, which is only when these tests are the chosen
label. The guard stays fully in force for `accounts lists capture clarice`,
where nothing should ever be touching the ORM from an async context.

The same trick, and the same reasoning, gives this label its own on-disk
test database. `manage.py test` puts SQLite in memory, and an in-memory
database cannot be reached from a second connection -- so
`LiveServerTestCase` hands its own connection to the server thread instead,
while `ThreadedWSGIServer` serves each request on a thread of its own.
Django marks that connection shareable, which silences the warning without
serialising anything, and concurrent statements interleave on one cursor.
The symptom was a 500 from a session lookup and a Playwright timeout that
looked nothing like the cause; see test_harness.py for the full trace.

Naming the test database makes it a file, which makes it reachable, which
means every thread opens its own connection and the sharing never happens.
Only this label pays the disk cost -- `accounts lists capture clarice`
stays in memory and stays fast, which is the run people do all day.

This has to happen at import time: the runner imports test modules while
building the suite, and that is before it creates any database.
"""
import os
import tempfile
from pathlib import Path

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

from django.conf import settings  # noqa: E402  (after the env var above)


def _name_the_test_database():
    """Give SQLite a file to put the test database in.

    Postgres is left alone: separate connections are already the default
    there, so the sharing this avoids never arises. That keeps the CI
    django job and any local Postgres run on exactly the path they have.
    """
    default = settings.DATABASES["default"]
    if "sqlite" not in default["ENGINE"]:
        return
    test_settings = default.setdefault("TEST", {})
    if test_settings.get("NAME"):
        return
    # The pid keeps two runs on one machine from colliding, and keeps a
    # crashed run from leaving a file that makes the next one stop and ask
    # whether to delete it -- which in CI would hang rather than fail.
    test_settings["NAME"] = str(
        Path(tempfile.gettempdir()) / f"clarice-functional-{os.getpid()}.sqlite3"
    )


_name_the_test_database()
