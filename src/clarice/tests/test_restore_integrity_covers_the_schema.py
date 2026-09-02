"""Every constraint is either drilled or deliberately not drilled.

`infra/check-restore-integrity.sh` answers the question a row-count diff
cannot: does a restored database still *enforce* what the live one enforces?
A restore that came back without a single trigger or constraint passes the
count comparison exactly, because the `django_migrations` rows are data and say
the migration ran, while the trigger it created is not a row.

**The script is a curated list, and a curated list over a growing schema drifts
in silence.** `MIGRATION.md`'s own August 19 note describes exactly that: five
task-core constraints were unchecked, so a restore that lost every one of them
printed *"All checked guarantees are intact."* Two days and two deploys later,
forty-nine of fifty-five declared constraints were unnamed in it again.

So this is the same shape as `recall.PERSON_EVENTS`' partition and
`test_emitters_are_idempotent`'s coverage assertion: **a list that only fails
on removal never fails on omission.** A new constraint has to be put on one
side or the other, and being forgotten is not one of the sides.

**The criterion for drilling one:** a constraint is checked when some code's
correctness argument names it -- when a docstring or comment says *this is safe
because the database refuses that*. Those are the ones whose loss turns working
code into silently wrong code rather than into a visible error.

**What is deliberately not drilled** is below, and it is not a backlog. Shape
checks on a value -- `*_span_ordered`, `*_confidence_range`, `*_valid` over an
enum -- fail loudly on the first bad write if they are missing, and a drill
that checked all fifty-five would cost an hour of a billed cluster to
re-verify things a failing insert reports anyway. Several belong to models
with no live writer at all (`Revision`, `Attachment`), which is its own
finding and lives in `code-review-2026-08-21.md` rather than here.

**This test never connects to a database.** It reads the script as text and the
models as declarations, so it runs anywhere and costs nothing -- which is the
point, because the drill it guards costs money and an hour.
"""

import pathlib
import re

from django.apps import apps
from django.test import SimpleTestCase


SCRIPT = pathlib.Path(__file__).resolve().parents[3] / "infra" / "check-restore-integrity.sh"


#: Constraints the drill deliberately does not check, and why they are safe to
#: leave out: each fails loudly on the first bad write rather than letting a
#: correctness argument quietly become false.
#:
#: **Adding a name here is a decision, not housekeeping.** If the constraint is
#: one that some service's docstring leans on -- "safe because the database
#: refuses that" -- it belongs in the script instead.
NOT_DRILLED = {
    # Shape of a value: an ordered or paired span, a confidence inside its
    # range, a size that is not negative. A missing one produces a bad row that
    # the next read shows as nonsense, not a silent wrong answer.
    "attachment_size_non_negative",
    # Guards the `default=b""` that exists only so `content` could be added to
    # an empty table. Its loss lets a zero-byte attachment be written -- a file
    # somebody downloads and finds empty, which is visible rather than silently
    # wrong.
    "attachment_has_content",
    # A decision with nothing chosen is a question, and the service refuses one
    # first. Losing the constraint lets a blank row through a path nothing
    # takes -- visible as an empty entry, not a wrong answer.
    "decision_chose_something",
    "edge_confidence_range",
    "facet_span_ordered",
    "facet_span_paired",
    "hypothesis_confidence_range",
    "hypothesis_member_span_ordered",
    "hypothesis_member_span_paired",
    "mention_span_ordered",
    "mention_span_paired",
    "revision_seq_positive",
    "sentence_span_ordered",
    # Enum validity, all of them backed by a TextChoices the application writes
    # from. `event_type_valid` and `event_origin_valid` are the exception and
    # are drilled, because `clarice/life_log.py` raises in front of them by
    # name and so treats them as the backstop.
    "concept_type_valid",
    "edge_origin_valid",
    "edge_relation_valid",
    "facet_kind_valid",
    "facet_origin_valid",
    "hypothesis_relation_valid",
    "hypothesis_resolution_valid",
    "mention_origin_valid",
    "miss_context_valid",
    "node_source_valid",
    # Internal consistency of one row's own fields.
    "concept_no_self_merge",
    "edge_no_self_link",
    "facet_cites_exactly_one_source",
    "hypothesis_resolution_paired",
    "hypothesis_surface_count_agrees",
    "hypothesis_window_requires_surfacing",
    "node_import_key_requires_import_source",
    # Uniqueness on knowledge-core structure. Real guarantees, but a duplicate
    # here is visible in the surface that reads it rather than silently
    # changing an answer -- and `mention_unique` is drilled as the representative
    # of the class, including its NULLS NOT DISTINCT behaviour, which is the
    # part a restore can plausibly lose.
    "concept_label_unique",
    "edge_directed_unique",
    "edge_symmetric_unique",
    "facet_entry_fingerprint_unique",
    "facet_one_live_per_kind",
    "hypothesis_fingerprint_unique",
    "hypothesis_member_unique",
    "node_import_key_unique",
    "revision_seq_unique",
    "sentence_unique_per_model",
    # Task-core and routine uniqueness whose loss shows up as a duplicate row
    # somebody can see, not as a wrong number. `unique_active_item` is the one
    # in this family that is drilled, and exercised rather than looked up,
    # because it is what stops a retried share writing the note twice.
    "one_open_pause_per_routine",
    "unique_owner_tag_name",
    "unique_planning_session_per_owner_week",
    "unique_routine_occurrence_period",
}


def declared_constraints():
    return {
        constraint.name
        for model in apps.get_models()
        for constraint in model._meta.constraints
    }




def _constraints_the_script_checks(script):
    """Every name the drill queries `pg_constraint` for.

    Parsed rather than matched: the script is a shell file full of English, and
    a substring search over it would call `exit` a constraint. The names live in
    `for constraint in <names>` loops, which may continue across backslashes and
    end at the `do` on the next line.
    """
    joined = re.sub(r"\\\n\s*", " ", script)
    names = set()
    for line in joined.split("\n"):
        match = re.match(r"\s*for constraint in (.+)$", line)
        if match:
            names.update(match.group(1).split())
    return names


class RestoreDrillCoversTheSchemaTest(SimpleTestCase):
    def setUp(self):
        self.script = SCRIPT.read_text(encoding="utf-8")

    def test_every_constraint_is_drilled_or_deliberately_not(self):
        """The assertion the August 19 drill needed and did not have.

        A constraint added tomorrow lands in neither the script nor
        `NOT_DRILLED`, and this fails until somebody says which it is.
        """
        unclassified = {
            name
            for name in declared_constraints()
            if name not in self.script and name not in NOT_DRILLED
        }

        self.assertEqual(
            unclassified,
            set(),
            "these constraints are neither drilled by "
            "infra/check-restore-integrity.sh nor listed as deliberately "
            "undrilled -- decide which, and say so in one place or the other",
        )

    def test_nothing_is_listed_as_undrilled_that_no_longer_exists(self):
        """The other direction, so the list cannot rot into a record of
        constraints that were deleted years ago."""
        gone = NOT_DRILLED - declared_constraints()

        self.assertEqual(gone, set(), "listed as undrilled but no longer declared")

    def test_the_script_checks_nothing_that_no_longer_exists(self):
        """**The direction this file was missing**, found on September 1, 2026
        by deleting a model.

        `test_every_constraint_is_drilled_or_deliberately_not` walks *declared →
        script*, so a constraint added without a decision fails. Nothing walked
        *script → declared*, so a constraint **deleted** left its name in the
        script and nothing said a word. `money_line_amount_not_negative` did
        exactly that when increment 8 of `bill-as-a-model-plan.md` dropped
        `MoneyLine`.

        **What that costs is the drill itself.** The script would query a
        constraint that cannot exist, report `no`, and fail -- at step 5, in
        WSL, with a paid scratch cluster running, which is precisely the
        mid-drill failure `CLAUDE.md` records for the executable-bit bug. A
        drill that cannot be trusted to pass for the right reason is worse than
        no drill, because it trains somebody to ignore it.

        `NOT_DRILLED` already had this direction --
        `test_nothing_is_listed_as_undrilled_that_no_longer_exists` -- and the
        script did not. The asymmetry was the whole gap.
        """
        checked = _constraints_the_script_checks(self.script)
        self.assertTrue(checked, "the script names no constraints at all")

        declared = declared_constraints()
        stale = {name for name in checked if name not in declared}

        self.assertEqual(
            stale,
            set(),
            "infra/check-restore-integrity.sh checks constraints that are no "
            "longer declared anywhere. The drill will report `no` for each and "
            "fail -- remove them from the script, or put the constraint back.",
        )

    def test_nothing_is_both_drilled_and_listed_as_undrilled(self):
        """A name in both places reads as a considered decision and is a
        contradiction -- and the script would win, silently."""
        both = {name for name in NOT_DRILLED if name in self.script}

        self.assertEqual(both, set(), "both drilled and listed as undrilled")

    def test_the_drilled_guarantees_the_log_rests_on_are_named(self):
        """The four the day's work made load-bearing, asserted by name rather
        than left to the partition -- deleting the block that checks them
        should fail something that says why they mattered.

        `unique_daily_focus_per_entry_task` is the grain C2 and C3 were keyed
        to: one focus per task *per day* is what makes a second backfill run
        safe against a table that refuses DELETE.
        """
        for name in (
            "event_type_valid",
            "event_origin_valid",
            "unique_daily_entry_per_owner_date",
            "unique_daily_focus_per_entry_task",
        ):
            with self.subTest(constraint=name):
                self.assertIn(name, self.script)

    def test_the_duplicate_task_probe_skips_generated_columns(self):
        """`lists.0040` added a generated `search_document` on August 20, the
        day after the drill passed, and Postgres refuses to insert a
        non-DEFAULT value into one -- so the strongest check in the script
        errored from that day, and the next drill would have reported a failure
        that reads exactly like a lost `unique_active_item`.

        Asserted as text because this test never opens a database: the probe
        must build its column list from the catalogue, excluding generated
        columns, so the next generated column needs no edit either.
        """
        self.assertIn("is_generated = 'NEVER'", self.script)
