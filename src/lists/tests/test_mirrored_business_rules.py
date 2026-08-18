"""Constants hand-ported across Python, TypeScript and Kotlin, checked.

`design/mirrored-rules-brief.md` §2 demonstrates the hole this closes. Raise
`WEEK_HORIZON_DAYS` to 14 in Python and TypeScript, leave Kotlin at 7, and all
three suites stay green: 594 Django, 34 vitest, 311 Kotlin. The digest and the
web then call a task due in ten days *this week* while the phone calls it
*later*, and nothing anywhere says so.

The reason the existing tests cannot catch it is that each computes its expected
edge from **its own** constant, so none can disagree with itself. Only a test
that reads more than one language can see it, which is why this one does — the
same reach `test_frontend_style_contract.py` already uses for CSS, extended to
`android/`.

**What this does not do**, so nobody reads more into a green run than it earns:
it compares *constants*, not behaviour. Three implementations can agree on 7 and
still disagree about whether the seventh day is inclusive. The brief's §6 says
what the thorough version would be, and §4 says why deleting two of the three
copies would be worth more than testing them.
"""
import re

from django.conf import settings
from django.test import SimpleTestCase


REPO = settings.BASE_DIR.parent
SRC = settings.BASE_DIR
FRONTEND = REPO / "frontend" / "src"
ANDROID = REPO / "android" / "app" / "src" / "main" / "java" / "com" / "vinclarice" / "capture"

# Every constant that exists in more than one language, and where each copy
# lives. A rule with one home does not belong here; a rule that grows a third
# copy does.
MIRRORED = {
    "WEEK_HORIZON_DAYS": {
        "python": SRC / "lists" / "agenda.py",
        "typescript": FRONTEND / "agenda.ts",
        "kotlin": ANDROID / "AgendaFormatting.kt",
    },
    "AGE_WORTH_MENTIONING": {
        "typescript": FRONTEND / "agenda.ts",
        "kotlin": ANDROID / "DailyFormatting.kt",
    },
}


def declared_value(name, path):
    """The integer a named constant is assigned in this file.

    One expression for three languages, because all three spell an assignment
    close enough:

        WEEK_HORIZON_DAYS = 7            Python
        export const WEEK_HORIZON_DAYS = 7;      TypeScript
        const val WEEK_HORIZON_DAYS = 7L         Kotlin

    Raises rather than returning None when the constant is absent or appears
    more than once. A sweep that quietly finds nothing is the failure mode this
    kind of test is most prone to -- `test_export.py`'s coverage guard passed
    while a model was missing, because it looked for a key and found one by
    accident. Loud is the only safe direction here.
    """
    if not path.exists():
        raise AssertionError(f"{path} does not exist; the mirror map is stale.")

    matches = re.findall(
        rf"^\s*(?:export\s+)?(?:const\s+)?(?:val\s+)?{re.escape(name)}\s*(?::\s*\w+\s*)?=\s*(\d+)",
        path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one assignment of {name} in {path.name}, "
            f"found {len(matches)}"
        )
    return int(matches[0])


class MirroredConstantsAgreeTest(SimpleTestCase):
    def test_every_mirrored_constant_holds_the_same_value_everywhere(self):
        for name, homes in MIRRORED.items():
            values = {
                language: declared_value(name, path)
                for language, path in homes.items()
            }
            with self.subTest(constant=name):
                self.assertEqual(
                    len(set(values.values())),
                    1,
                    f"{name} disagrees across languages: {values}",
                )


class TheSweepActuallyReachesAllThreeTest(SimpleTestCase):
    """Positive controls.

    Every assertion above is of the form "these agree". A map that had gone
    stale -- a moved file, a renamed constant, an empty dict -- would make that
    vacuously true and this test file worse than useless, because it would read
    as coverage. These fail instead.
    """

    def test_the_map_is_not_empty_and_every_entry_spans_languages(self):
        self.assertGreater(len(MIRRORED), 0)
        for name, homes in MIRRORED.items():
            with self.subTest(constant=name):
                self.assertGreater(
                    len(homes), 1, f"{name} has one home and is not a mirror"
                )

    def test_every_file_named_exists_and_declares_its_constant(self):
        for name, homes in MIRRORED.items():
            for language, path in homes.items():
                with self.subTest(constant=name, language=language):
                    self.assertIsInstance(declared_value(name, path), int)

    def test_all_three_languages_are_covered_between_them(self):
        """If a refactor left only Python and TypeScript here, the phone would
        stop being checked and the suite would not mention it."""
        covered = {language for homes in MIRRORED.values() for language in homes}

        self.assertEqual(covered, {"python", "typescript", "kotlin"})

    def test_the_reader_refuses_a_constant_that_is_not_there(self):
        """The guard on the guard: a regex that silently matched nothing would
        make every comparison above pass."""
        with self.assertRaises(AssertionError):
            declared_value("NO_SUCH_CONSTANT", SRC / "lists" / "agenda.py")

    def test_the_reader_refuses_a_file_that_is_not_there(self):
        with self.assertRaises(AssertionError):
            declared_value("WEEK_HORIZON_DAYS", SRC / "lists" / "no_such_file.py")
