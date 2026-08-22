"""No date is derived from an instant without naming a clock — **D16's guard**.

D16 asked *whose clock is a morning?* and the answer is in
[`clarice/clocks.py`](../clocks.py). This is the mechanism that keeps it
answered, and it exists because of how the original defect behaved:
`what_surrounded` asked for **tomorrow's** `DailyEntry` for every evening note
west of UTC, found nothing, and returned an empty section. **No exception, no
wrong number on a page — just a feature that quietly did less than it claimed**,
through a whole release and a verdict of *works*.

**A note telling the next person to remember something is not a mechanism.**
That sentence is already in `accounts/middleware.py`, written after six
token-authenticated endpoints each forgot to activate the owner's zone despite
a docstring asking them to. This is the same class of mistake one core over, so
it gets the same treatment the executable-file-modes and line-endings guards
get: something that fails.

**Scope: the two cores' shared code and the knowledge core.** The task core is
deliberately not scanned — it settled this in August 2026 and answers with
`timezone.localdate()` throughout, which is correct *there* because the viewer
is the subject. See `clocks.py` for where that stops being true.
"""

import ast
import pathlib

from django.test import SimpleTestCase


ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

#: Where a date may be built from a datetime, and only these.
#:
#: `astimezone` and `localtime` both name a zone before they truncate. Anything
#: else is taking the UTC date and hoping.
SANCTIONED = {"astimezone", "localtime"}

#: Sites that build a date some other way and have argued for it in place.
#: Keyed by `path:attribute`, valued by the reason -- so removing the reasoning
#: from the code without removing it from here is itself a failure.
DECLARED = {
    "clarice/health.py": (
        "the definition of a conservative skew allowance, argued in place: an "
        "alerting path where a false alarm is the expensive failure"
    ),
}


def _scanned():
    for directory in ("clarice", "mind"):
        for path in sorted((ROOT / directory).rglob("*.py")):
            relative = path.relative_to(ROOT).as_posix()
            if "/tests/" in relative or "/migrations/" in relative:
                continue
            if pathlib.Path(relative).name.startswith("test_"):
                continue
            yield relative, path


def _unclocked_dates(source):
    """Every `.date()` whose receiver did not name a zone first."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        if not (isinstance(callee, ast.Attribute) and callee.attr == "date"):
            continue
        if node.args or node.keywords:
            # `datetime.date(2026, 8, 20)` constructs one, it does not
            # truncate an instant, and it cannot be wrong about a zone.
            continue
        receiver = callee.value
        if (
            isinstance(receiver, ast.Call)
            and isinstance(receiver.func, ast.Attribute)
            and receiver.func.attr in SANCTIONED
        ):
            continue
        found.append(node.lineno)
    return found


class ADayNamesItsClockTest(SimpleTestCase):
    def test_no_date_is_taken_from_an_instant_without_a_zone(self):
        offenders = {}
        for relative, path in _scanned():
            lines = _unclocked_dates(path.read_text(encoding="utf-8"))
            if lines and relative not in DECLARED:
                offenders[relative] = lines

        self.assertEqual(
            offenders,
            {},
            "\n\nThese take the UTC date off an instant. Whose clock is that?\n"
            "Use `clarice.clocks.day_for(owner, instant)`, or add the file to\n"
            "DECLARED in this test with the argument for why UTC is right:\n"
            f"{offenders}",
        )

    def test_a_declared_exemption_is_still_doing_something(self):
        """An allowlist that outlives its entries stops being an allowlist and
        becomes a place to put things. Same reasoning as the restore drill's
        `NOT_DRILLED`."""
        scanned = dict(_scanned())
        for relative in DECLARED:
            self.assertIn(relative, scanned, f"{relative} is no longer scanned")
            self.assertTrue(
                _unclocked_dates(scanned[relative].read_text(encoding="utf-8")),
                f"{relative} no longer needs its exemption -- remove it",
            )
