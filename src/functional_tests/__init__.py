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
"""
import os

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")
