"""Every knowledge-core enum value nothing writes says so, and says what would.

The companion to `test_dark_services_declare_their_deferral.py`, for the other
shape the same rule takes. `principles.md`, *Deliver vertical slices*: **a slice
is not closed while nothing calls it.** A `TextChoices` member nothing ever
writes is that, in miniature -- a branch of the domain that has never once been
taken, reading as available.

**It has already cost a published number.** `clarice-v4-plan.md`: all three
writers of `HypothesisResolution.EXPIRED` are themselves dark, so `/numbers/`
reported an `expired` count and an `unseen_rate` that were **structurally zero
on live data** -- a page reporting a figure that could not be anything else.
Declared at the code on August 24, 2026 (`dbc8186`), and the cell carries its
reason now. This file is so the next one is caught before it is published.

**Why this is scoped to the knowledge core, when the service scan is not.**
A function has one kind of caller and Python can be parsed for it. A *value* has
four write paths and three of them are invisible to a Python scan:

1. **Python names it** -- `source=NodeSource.WEB`. Visible.
2. **A form offers the whole enum** -- `{"kinds": ConceptType.choices}` reaching
   a `<select>`, so a person can post any member. `ConceptType` is exempted this
   way, and `test_a_form_written_enum_is_not_reported_dark` holds it.
3. **A field default** -- `default=Priority.NONE` writes on every row created.
4. **A client posts the string** -- `frontend/src/app/theme.ts` declares
   `"system" | "light" | "dark"` and the API accepts it, so `Theme`'s three
   members are written by code in another language.

Rules 3 and 4 are why `lists`, `accounts`, `routines` and `review` are out of
scope rather than merely unlisted: a guard that exempts four ways of writing is
weak enough that its silence means little, and **a weak guard is worse than
none, because it is read as evidence.** The knowledge core writes its own values
in Python, so here the scan can be strict.

**And the predicate is *never mentioned*, not *never written*, which is a
weaker claim deliberately.** A read and a write are the same shape to a parser:
`Q(resolution=HypothesisResolution.EXPIRED)` counts rows and
`_resolve(hypothesis, HypothesisResolution.EXPIRED)` sets one, and nothing in
the syntax tells them apart. So this file proves the strong, checkable thing --
**no production code names this value at all** -- and leaves the subtler case to
a person.

`EventType.THREAD_ARTICULATED` is that subtler case, and it is the reason this
paragraph exists rather than being an aside. It is **read and never written**:
`confirm_hypothesis` creates the thread node -- `source=NodeSource.THREAD`,
which *is* written -- and logs no event for it, while `clarice/recall.py` lists
the type among the person's own acts and `mind/views.py` carries its label. The
act happens in production, a reader waits for it, and the row has never been
written. A first draft of this file registered it here and the registry test
refused it, correctly: it is mentioned. **The finding is recorded at
`confirm_hypothesis`**, where somebody meets it, and what the append-only log
should record is a product decision rather than a tidy-up.

**This test never opens a database.** It reads source as text.
"""

import ast
import pathlib

from django.test import SimpleTestCase

from clarice.tests.test_dark_services_declare_their_deferral import (
    production_sources,
    references,
)


SRC = pathlib.Path(__file__).resolve().parents[2]
MODELS = SRC / "mind" / "models.py"

#: The ten values nothing writes, each with what would switch it on.
#:
#: **Declared rather than deleted, and not for the usual reason.** Elsewhere the
#: argument is that the design note is the load-bearing part; here there is a
#: second one that is harder. Every one of these is inside a database
#: `CheckConstraint` -- `condition=Q(source__in=NodeSource.values)` and its
#: siblings -- so removing a member is a migration against live tables, not a
#: deletion. That is a real cost for tidiness, and none of these is in anybody's
#: way.
DARK_VALUES = {
    # `/mind/share/` pre-fills the capture form and deliberately does not save;
    # the person then submits it, which writes `WEB`. So a shared capture
    # genuinely *is* a web capture, and this value describes a share target that
    # writes without asking -- which `views.share` argues against by name.
    ("NodeSource", "SHARE"): "a share target that writes without the form",
    # `/api/v1/capture` writes `MOBILE` or `WEB` from `from_a_phone`, so even
    # the API does not write this. It is for a caller that is neither -- a
    # script, or somebody else's client against a token.
    ("NodeSource", "API"): "a token client that is neither the phone nor the SPA",
    # Two of the twelve memory roles that nothing proposes. The kind's own
    # docstring predicted exactly this: *"shipping all fourteen with nothing
    # proposing any of them would be the dark seam this project keeps
    # rediscovering, times fourteen."* Ten of the twelve have a writer; these
    # are the two that do not.
    ("FacetKind", "MEDIA"): "an extractor or a person's facet surface proposing it",
    ("FacetKind", "CONCEPT"): "an extractor or a person's facet surface proposing it",
    # `EdgeRelation.CONTRADICTS`, `SUPERSEDES` and `DEVELOPED_FROM` came off
    # this list on August 26, 2026 -- **two days after going on it.** Each was
    # declared with the trigger *"the node page's manual link surface"*, that
    # surface was built, and this test failed in the direction it exists for,
    # naming all three in the same run that `DARK` gave up `unlink`.
    #
    # **The registry is two days old and has already been right twice**, which
    # is the argument for a guard over an inventory: an inventory of dark
    # symbols would still say these were dark.
    # `confirm_hypothesis` and `dismiss_hypothesis` write the first two and
    # `expire_stale_hypotheses` the third. Nothing renames a hypothesis, so
    # nothing resolves one this way.
    ("HypothesisResolution", "RENAMED"): "a path that renames a hypothesis rather than confirming it",
    # `SEARCH` and `RECOLLECTION` are the two miss buttons that exist. There is
    # no miss button on the capture surface, which is what this value is for --
    # *I came here to write something down and could not find what it was
    # about.*
    ("MissContext", "CAPTURE"): "a miss button on the capture surface",
    # `EventType.THREAD_ARTICULATED` is **not** here, and the module docstring
    # says why at length: it is read by `clarice/recall.py` and written by
    # nothing, which this scan cannot distinguish from being used. Registering
    # it made `test_the_registry_is_the_whole_list` fail, which was the test
    # being right.
}


def enums_in(path):
    """Every `TextChoices` class in one module, with its members."""
    found = {}
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(
            (isinstance(base, ast.Attribute) and base.attr == "TextChoices")
            or (isinstance(base, ast.Name) and base.id == "TextChoices")
            for base in node.bases
        ):
            continue
        found[node.name] = [
            target.id
            for statement in node.body
            if isinstance(statement, ast.Assign)
            for target in statement.targets
            if isinstance(target, ast.Name) and target.id.isupper()
        ]
    return found


def written_values(sources):
    """`(enum, MEMBER)` pairs production code names, and enums a form offers.

    Shares `references()` with the service scan, which is what makes both able
    to see `Item.Status.ACTIVE` -- three links deep, and reading only the first
    two reported six enums entirely unwritten.
    """
    named, offered = set(), set()
    for path, text in sources.items():
        if path == MODELS or path.suffix != ".py":
            continue
        for enum, attr in references(text):
            named.add((enum, attr))
            if attr in {"choices", "values"}:
                offered.add(enum)
    return named, offered


class DarkEnumValuesTest(SimpleTestCase):
    def setUp(self):
        self.enums = enums_in(MODELS)
        self.sources = {
            path: path.read_text(encoding="utf-8", errors="ignore")
            for path in production_sources(exclude=None)
        }
        self.named, self.offered = written_values(self.sources)
        self.models_source = MODELS.read_text(encoding="utf-8")

    def dark(self):
        return {
            (enum, member)
            for enum, members in self.enums.items()
            if enum not in self.offered
            for member in members
            if (enum, member) not in self.named
        }

    def test_the_registry_is_the_whole_list(self):
        """Discovered, not trusted -- the lesson the service scan learned twice.

        A hardcoded list of values cannot notice a new one, exactly as a
        hardcoded list of functions could not and then a hardcoded list of
        modules could not.
        """
        undeclared = sorted(self.dark() - set(DARK_VALUES))
        self.assertEqual(
            undeclared,
            [],
            f"{undeclared} are never written and not declared -- add each to "
            f"DARK_VALUES with a trigger, or write something that uses it",
        )

    def test_nothing_here_has_quietly_come_alive(self):
        """The happier direction. When the node page finally offers a manual
        link, `CONTRADICTS` gains a writer and this says to delete a comment
        that has stopped being true."""
        for enum, member in sorted(DARK_VALUES):
            with self.subTest(enum=enum, member=member):
                # `assertFalse` rather than `assertNotIn`, which prints the
                # whole container it searched: the named set is every
                # attribute reference in `src/`, and the first time this
                # fired it produced 179KB of failure output for a
                # one-line finding. A guard nobody can read the failure of
                # is a guard people learn to skim.
                self.assertFalse(
                    (enum, member) in self.named,
                    f"{enum}.{member} is written now -- remove its declaration",
                )

    def test_every_dark_value_says_so_where_it_is_defined(self):
        """A reader meeting the value should not have to grep to learn it has
        never been written, and the declaration has to name what would change
        that -- *a named trigger or a deletion*, the easy half being the
        admission."""
        for (enum, member), trigger in sorted(DARK_VALUES.items()):
            with self.subTest(enum=enum, member=member):
                declaration = self.declaration_for(enum, member)
                self.assertIn(
                    "DARK: never written.",
                    declaration,
                    f"{enum}.{member} is never written and does not say so",
                )
                self.assertIn(
                    "Trigger:",
                    declaration,
                    f"{enum}.{member} admits it is dark without naming a trigger",
                )

    def test_a_form_written_enum_is_not_reported_dark(self):
        """`ConceptType` is the canary for write path 2 -- see the module
        docstring.

        Its five non-default members are named nowhere in Python, and all seven
        are live: `mind/views.py` puts `ConceptType.choices` in the template
        context and `concept.html` renders a `<select>`, so a person writes
        them. A scan without this exemption reports five false darks, and a
        false dark is what invites a `# DARK:` comment onto working code.
        """
        self.assertIn("ConceptType", self.offered)
        self.assertEqual(
            [(enum, member) for enum, member in self.dark() if enum == "ConceptType"],
            [],
        )

    def declaration_for(self, enum, member):
        """The comment block immediately above the member's line."""
        lines = self.models_source.splitlines()
        start = None
        depth = 0
        for index, line in enumerate(lines):
            if line.startswith(f"class {enum}("):
                depth = index
            if depth and line.strip().startswith(f"{member} = "):
                start = index
                break
        if start is None:
            return ""
        block = []
        for line in reversed(lines[:start]):
            if line.strip().startswith("#"):
                block.append(line)
            elif line.strip() == "":
                continue
            else:
                break
        return "\n".join(reversed(block))
