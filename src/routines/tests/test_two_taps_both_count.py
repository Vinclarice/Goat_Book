"""Two logs at once, and the increment that used to go missing.

`log_progress` read `occurrence.progress`, added to it in Python and saved --
no `select_for_update`, no `F()`. Every mutation in `lists/services.py` opens
with `select_for_update`; this module had it nowhere, and this is the one write
in it where a lost update is not recoverable. The log *is* the count, so an
increment that vanishes leaves nothing to reconstruct it from: if the loss is
what makes the period miss its target, `habits_met` is wrong for that week and
no other record disagrees.

A phone on a poor connection retrying, or a double-tapped "+1", is the ordinary
way this happens rather than an exotic one.

`TransactionTestCase` rather than `TestCase`, and threads rather than a
simulated interleave, because the thing under test is what two database
connections do to one row -- a test inside one transaction cannot see it, and
would pass against the broken version.
"""

import threading
import time

from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from accounts.models import User
from routines import services
from routines.models import RoutineOccurrence


class TwoSimultaneousLogsBothCountTest(TransactionTestCase):
    def test_neither_increment_is_lost(self):
        owner = User.objects.create_user("vince", "vince@example.com", "pw")
        routine = services.create_routine(
            owner, title="Practice Spanish", target_quantity=10
        )
        day = timezone.localdate()

        # Logged once up front so the row exists and is committed. Without it
        # both threads race `get_or_create`'s INSERT instead, which Postgres
        # serialises on the unique index -- a different mechanism that would
        # mask the one under test.
        services.log_progress(owner, routine, day, amount=1)

        first_has_read = threading.Event()
        errors = []
        original_settle = services._settle_outcome

        def settle(occurrence):
            """Hold the first writer between its read and its write.

            Long enough that an unlocked second reader gets the stale value.
            With the lock in place the second thread never reaches its read
            until this one commits, so the pause costs the test its duration
            and nothing else.
            """
            original_settle(occurrence)
            if threading.current_thread().name == "first":
                first_has_read.set()
                time.sleep(0.5)

        def log(name):
            try:
                if name == "second":
                    # Start only once the first has read, so the interleave is
                    # forced rather than hoped for.
                    assert first_has_read.wait(timeout=10)
                services.log_progress(owner, routine, day, amount=1)
            except Exception as error:  # surfaced below; a thread that raises
                errors.append(error)    # would otherwise fail as a wrong count
            finally:
                connection.close()

        services._settle_outcome = settle
        try:
            threads = [
                threading.Thread(target=log, args=(name,), name=name)
                for name in ("first", "second")
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=30)
        finally:
            services._settle_outcome = original_settle

        self.assertEqual(errors, [])
        occurrence = RoutineOccurrence.objects.get(routine=routine)
        self.assertEqual(occurrence.progress, 3)
