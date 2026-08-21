"""Every service nothing calls says so, and says what would switch it on.

`principles.md`, *Deliver vertical slices*: **a slice is not closed while
nothing calls it**, and an undeclared deferral gets a named trigger or a
deletion. This is that rule with teeth, for the app where it kept happening.

**The finding that shaped it.** Twelve services in `src/mind/` have no
production caller, and eleven are the **undo half of a live pair** -- `capture`
has seven callers and `revise`, `delete_node`, `purge_node` and `archive_node`
have none; `link` has two and `unlink` none; `resolve_question` has two and
`reopen_question` none; `confirm_concept` has three and `merge_concept` none.
So the inventory is not twelve pieces of dead code. **It is one missing surface,
listed eleven times**, and deleting them would delete half of eleven features
immediately before building the node page that needs them.

Which is why these are declared rather than removed. The declaration is the
thing the principle actually requires, and it goes where a reader meets the
function rather than in a plan they would have to know to look for.

**Two are not undo halves and are the real outliers**:
`expire_stale_hypotheses` is scheduled work nothing schedules, and wiring it to
cron would make a machine's `HYPOTHESIS_RESOLVED` indistinguishable from a
person's; `commitments_without_tasks` is an invariant monitor nobody monitors.
Both are named in the module.

**This test never opens a database.** It reads source as text, so it runs
anywhere and costs nothing.
"""

import pathlib
import re

from django.test import SimpleTestCase


SRC = pathlib.Path(__file__).resolve().parents[2]
SERVICES = SRC / "mind" / "services.py"

#: The twelve, each with the live half whose absence of an undo it represents,
#: or None where it is not an undo half at all.
#:
#: **Kept as a list rather than derived**, for the reason `NOT_DRILLED` and
#: `PERSON_EVENTS` are: a set computed from the code cannot fail when something
#: is forgotten, only when it is removed. This one fails both ways -- a new dark
#: service is caught by `test_every_dark_service_is_declared`, and one that
#: gains a caller is caught by `test_nothing_here_has_quietly_come_alive`.
DARK = {
    "revise": "capture",
    "delete_node": "capture",
    "purge_node": "capture",
    "archive_node": "capture",
    "unlink": "link",
    "reopen_question": "resolve_question",
    "merge_concept": "confirm_concept",
    "confirm_mention": "propose_mention",
    "mark_reviewed": "open_review",
    "resolve_retrieval_miss": None,
    "expire_stale_hypotheses": None,
    "commitments_without_tasks": None,
}


def production_sources():
    """Every non-test Python and template file, minus the definitions' own home."""
    for path in SRC.rglob("*.py"):
        if "tests" in path.parts or path.name.startswith("test_"):
            continue
        if path == SERVICES:
            continue
        yield path
    yield from SRC.rglob("*.html")


def callers_of(name, sources):
    """Calls written as `<something>services.name(`.

    Matched that way rather than on a bare `name(`, which is how two blind spots
    got past a hand check: `staged.unlink(missing_ok=True)` is `pathlib`'s
    method and has nothing to do with `services.unlink`, and a view referenced
    in a URLconf is never called with parentheses at all.
    """
    pattern = re.compile(rf"\w*services\.{re.escape(name)}\s*\(")
    return [p for p in sources if pattern.search(p.read_text(encoding="utf-8"))]


def internal_callers_of(name, source):
    """Calls from elsewhere inside `services.py`.

    `link` has no outside caller and is not dark: `confirm_hypothesis` calls
    it, and that is live from `mind/views.py`. Counting only outside callers
    said otherwise. A bare `\\bname\\s*\\(` is safe here because the word
    boundary keeps `unlink(` from matching `link` -- the pathlib collision that
    hid `services.unlink` from a hand check does not arise inside this file.

    **Not full reachability**, and it does not need to be: nothing in `DARK` is
    called internally either, so an internal caller here is a live one.
    """
    return [
        line
        for line in re.findall(rf".*\b{re.escape(name)}\s*\(.*", source)
        if not line.lstrip().startswith("def ")
    ]


class DarkServicesTest(SimpleTestCase):
    def setUp(self):
        self.source = SERVICES.read_text(encoding="utf-8")
        self.sources = list(production_sources())

    def declaration_for(self, name):
        match = re.search(
            rf"((?:^# .*\n)+)def {re.escape(name)}\(", self.source, re.MULTILINE
        )
        return match.group(1) if match else ""

    def test_every_dark_service_is_declared(self):
        """The rule itself. A reader meeting one of these should not have to
        discover by grep that it has never run."""
        for name in DARK:
            with self.subTest(service=name):
                self.assertIn(
                    "# DARK: no production caller.",
                    self.declaration_for(name),
                    f"{name} has no caller and does not say so",
                )

    def test_every_declaration_names_what_would_switch_it_on(self):
        """*A named trigger or a deletion* -- so a declaration that only admits
        the code is dark has done the easy half."""
        for name in DARK:
            with self.subTest(service=name):
                declaration = self.declaration_for(name)
                self.assertTrue(
                    "Trigger:" in declaration
                    or "Decision registered:" in declaration
                    or "Decide before wiring" in declaration,
                    f"{name} is declared dark without naming a trigger or a decision",
                )

    def test_nothing_here_has_quietly_come_alive(self):
        """The other direction, and the happier failure.

        When the node page finally calls `delete_node`, this fails and tells
        somebody to delete a comment that has become untrue. A declaration that
        outlives its deferral is worse than none: it teaches a reader that
        working code is dark.
        """
        for name in DARK:
            with self.subTest(service=name):
                self.assertEqual(
                    callers_of(name, self.sources),
                    [],
                    f"{name} now has a caller -- remove its DARK declaration",
                )

    def test_the_live_halves_are_still_live(self):
        """The pairing is the whole argument for declaring rather than
        deleting, so it is asserted rather than described.

        If `capture` ever loses its callers too, these stop being undo halves
        of a working feature and become an abandoned subsystem -- which is a
        different decision, and one nobody should reach by assumption.
        """
        for name, live_half in DARK.items():
            if live_half is None:
                continue
            with self.subTest(service=name, live_half=live_half):
                reached = callers_of(live_half, self.sources) or internal_callers_of(
                    live_half, self.source
                )
                self.assertNotEqual(
                    reached,
                    [],
                    f"{live_half} has lost its callers, so {name} is no longer "
                    f"the dark half of a live pair",
                )
