"""Everything hanging off a task is named where the next occurrence is built.

**Written August 27, 2026, after the same defect twice in one day.** A bill is a
one-to-one sidecar on `Item`; `_spawn_next_occurrence` never mentioned it; so
paying a repeating bill produced a plain task for the following month and rent
silently stopped being a bill. `set_bill` was correct. `_spawn_next_occurrence`
was correct. `bills_for` was correct. **The defect lived in the space between
three correct things**, which is the failure this project keeps producing and
has no instrument for.

**The existing guards catch the other shape.**
`test_dark_services_declare_their_deferral.py` asks *does anything call this?*
That question cannot see a sidecar nobody joined to a copy path: `Bill` had
callers, plenty of them, and was still dropped on every spawn.

**So this asks the opposite question: does the copy path know about you?** Every
reverse relation on `Item` must be **named in the source of
`_spawn_next_occurrence`** -- either because it is carried, or in a comment
saying why it is not. A name, not a behaviour, and deliberately so: the failure
was nobody deciding, and what fixes that is being made to write the decision
down. The same reasoning as the `# DARK:` declarations the knowledge core uses.

**What it found when it was written**: `Facet` and `ActivityEvent`, neither
carried and neither declared. Both turned out to be *correctly* not carried --
which is the point. The answer was right and nowhere, and a right answer nobody
wrote down is one the next person has to work out again, or miss.

**This test reads source as text and opens no database**, so it costs nothing.
"""
import inspect

from django.test import SimpleTestCase

from lists import services
from lists.models import Item


def spawn_source():
    """The text of the function that builds the next occurrence."""
    return inspect.getsource(services._spawn_next_occurrence)


def hangs_off_a_task():
    """Every model with a relation pointing at `Item`, by name."""
    return sorted(
        rel.related_model.__name__ for rel in Item._meta.related_objects
    )


class ASpawnAccountsForEverythingOnATaskTest(SimpleTestCase):
    def test_every_relation_on_a_task_is_named_where_the_next_one_is_built(self):
        source = spawn_source()

        unaccounted = [name for name in hangs_off_a_task() if name not in source]

        self.assertEqual(
            unaccounted,
            [],
            "Something hangs off a task and `_spawn_next_occurrence` has never "
            "heard of it. When a repeating task comes round, that thing is "
            "silently left behind -- which is exactly how a paid bill stopped "
            "being a bill. Carry it, or say in a comment there why it is not "
            "carried. Either is fine; saying nothing is not.",
        )

    def test_the_sweep_actually_finds_the_relations(self):
        """A positive control, for the reason its siblings carry one: a sweep
        that quietly returned nothing would make the assertion above pass over
        an empty list forever, which is the un-switched-on seam this repository
        has now found five times."""
        found = hangs_off_a_task()

        self.assertIn("Bill", found)
        self.assertIn("ChecklistStep", found)
        self.assertGreaterEqual(len(found), 3)
