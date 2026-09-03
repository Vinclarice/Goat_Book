"""The money modules may not borrow the task core's internals.

**Step 2 of the extraction sequence**, and the reason it comes before the app
move rather than after: `money/` cannot become its own app while its services
import a private function from `lists.services` to work out what *monthly*
means. The dependency is real either way — both domains recur — but it should
point at a neutral module rather than into a sibling's private surface.

**What this refuses, and why each is more than tidiness:**

- **Private names.** `bills.py` imported `_advance_due_date`, and the leading
  underscore is `lists.services` saying *this is mine and it may change*. Money
  had no claim on it and no notice if it moved.
- **`Item`.** Importing a task model to spell `Item.Recurrence.MONTHLY` makes a
  bill's cadence look like a property of tasks. It is a property of calendars.
- **`TaskConflict` by that name.** A bill refusing a write is not a task
  conflict. It was caught by name at the boundary, so it worked -- and read as
  though bills were still tasks, which is the thing nine increments removed.

**Named modules rather than a directory scan**, because the list has to survive
the move: when these become `money/services.py` and `money/reads.py` the names
here change and nothing else does. A scan of `lists/` would silently cover
nothing the day they leave.
"""
import ast
import pathlib

from django.test import SimpleTestCase

SRC = pathlib.Path(__file__).resolve().parents[2]

#: The money modules, by path. They were `lists/bills.py` and `lists/money.py`
#: until step 3 moved them on September 2, 2026 -- and
#: `test_the_modules_this_guards_still_exist` is what said so, by failing, which
#: is the whole reason it is there. A guard over files that have moved passes
#: over nothing.
MONEY_MODULES = (
    "money/models.py",
    "money/services.py",
    "money/reads.py",
    "money/api_v1.py",
    "money/admin.py",
    "money/management/commands/catch_up_bills.py",
)

#: Where shared calendar vocabulary lives now. Both cores may depend on this;
#: neither owns it.
NEUTRAL = ("clarice.recurrence", "clarice.errors")


def _imports(path):
    """Every `from X import a, b` in one module, as (module, name) pairs."""
    tree = ast.parse((SRC / path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                yield node.module, alias.name


class MoneyDoesNotReachIntoTheTaskCoreTest(SimpleTestCase):
    def test_it_imports_no_private_name_from_the_task_core(self):
        for path in MONEY_MODULES:
            for module, name in _imports(path):
                if not module.startswith("lists"):
                    continue
                with self.subTest(module=path, imported=f"{module}.{name}"):
                    self.assertFalse(
                        name.startswith("_"),
                        f"{path} imports the private {module}.{name}. A leading "
                        "underscore is that module saying it may change without "
                        "notice; move what is genuinely shared to "
                        "clarice.recurrence instead.",
                    )

    def test_it_does_not_import_a_task_model_for_its_vocabulary(self):
        for path in MONEY_MODULES:
            imported = {name for module, name in _imports(path)
                        if module.startswith("lists")}
            with self.subTest(module=path):
                self.assertNotIn(
                    "Item",
                    imported,
                    f"{path} imports Item. A bill's cadence is a property of "
                    "calendars, not of tasks -- clarice.recurrence.Recurrence "
                    "says the same thing without the claim.",
                )

    def test_the_shared_vocabulary_comes_from_the_neutral_module(self):
        """A positive control as much as a rule: if these stopped being imported
        from `clarice.recurrence` because somebody inlined a copy, the two rules
        above would still pass over a module that had quietly forked the
        calendar."""
        wanted = {"Recurrence", "CadenceMode", "advance_due_date"}
        found = set()
        for path in MONEY_MODULES:
            for module, name in _imports(path):
                if module in NEUTRAL:
                    found.add(name)

        self.assertTrue(
            wanted & found,
            "no money module takes its cadence vocabulary from "
            f"{NEUTRAL[0]}; one of {sorted(wanted)} was expected",
        )

    def test_a_bill_refusing_a_write_is_not_a_task_conflict(self):
        for path in MONEY_MODULES:
            imported = {name for module, name in _imports(path)}
            with self.subTest(module=path):
                self.assertNotIn(
                    "TaskConflict",
                    imported,
                    f"{path} raises TaskConflict. A bill is not a task; it has "
                    "been nine increments since it was. Raise the neutral "
                    "Conflict, or money's own subclass of it.",
                )

    def test_the_modules_this_guards_still_exist(self):
        """The control the seam rule asks for. These paths move at step 3, and a
        guard over files that are no longer there passes over nothing."""
        for path in MONEY_MODULES:
            with self.subTest(module=path):
                self.assertTrue((SRC / path).exists(), f"{path} has moved")

    def test_no_money_module_imports_the_task_core_at_all(self):
        """**The strongest form, and it became true on September 2, 2026.**

        The four rules above each refuse one *kind* of borrowing. This refuses
        the category: after step 5 moved the account and category writes across,
        not one module in `money/` imports anything from `lists`. What money
        shares with the task core is `clarice.recurrence` and `clarice.errors`,
        which belong to neither.

        **Its tests are exempt and deliberately so.** `money/tests/` still
        imports `Item` and `lists.services` because some of what money promises
        is an *asymmetry* -- `test_a_task_still_skips` asserts that the task
        core did **not** get the missed-period replay, and it cannot assert that
        without a task. A test reaching across is evidence about the boundary;
        a module reaching across is a hole in it.
        """
        for path in MONEY_MODULES:
            offenders = sorted({module for module, _ in _imports(path)
                                if module.split(".")[0] == "lists"})
            with self.subTest(module=path):
                self.assertEqual(
                    offenders,
                    [],
                    f"{path} imports {offenders}. Money is its own app and owns "
                    "its own models; what it genuinely shares with the task core "
                    "lives in clarice/.",
                )


class NoTaskModuleSerialisesABillTest(SimpleTestCase):
    """The mirror rule, and the reason the four above were not enough.

    **Every rule in the class above is one-directional**: it asserts that
    `money/` does not import `lists`. It says nothing about money's *code*
    living in `lists`, and for a week four pieces of it did — the agenda's bill
    row and its query, and the digest's two bill lines — all passing the
    boundary guard cleanly, because a module in `lists` importing nothing from
    `money` is exactly what those rules want to see.

    **How code ends up in the wrong app**, which is worth naming because it was
    nobody's decision: the first caller that needed a bill serialized happened
    to be the agenda payload, so the serializer was written there. Not moved
    there, not argued for — just written where it was first wanted.

    So this walks the other way: a module in the task core that knows a bill's
    field names is money's code in the wrong place, whoever put it there.
    """

    #: Modules that legitimately name a bill because they *consume* the
    #: contract: a schema reference, a call into `money.reads`, a docstring.
    #: What none of them may do is take a `Bill` apart.
    TASK_MODULES = (
        "lists/agenda.py",
        "lists/api_v1.py",
        "lists/services.py",
        "lists/serializers.py",
        "lists/management/commands/send_due_digest.py",
        "daily/api_v1.py",
        "daily/reads.py",
    )

    #: Fields only a `Bill` has. A task module reading one is pulling a money
    #: record apart rather than passing it on.
    BILL_FIELDS = ("payee", "paid_at", "paid_amount", "due_date")

    def test_no_task_module_reads_a_bill_apart(self):
        import re

        for path in self.TASK_MODULES:
            source = (SRC / path).read_text(encoding="utf-8")
            # Comments and docstrings talk about bills constantly and
            # correctly, so only code is read.
            code = "\n".join(
                line.split("#")[0] for line in source.splitlines()
            )
            for attribute in ("bill.payee", "bill.paid_at", "bill.paid_amount",
                              "row.payee", "row.paid_at"):
                # The line number rather than `assertNotIn`, whose failure
                # prints the whole haystack -- and the haystack here is a
                # thousand-line module, which in CI is a wall nobody reads.
                found = [
                    n for n, line in enumerate(code.splitlines(), 1)
                    if attribute in line
                ]
                with self.subTest(module=path, reads=attribute):
                    self.assertEqual(
                        found,
                        [],
                        f"{path} reads {attribute} at line(s) {found}. "
                        "Serialising a bill is money's -- "
                        "`money.reads.bill_row` and `money.reads.digest_line` "
                        "are what these consume.",
                    )

    def test_the_task_modules_this_names_still_exist(self):
        """The control the seam rule asks for, in its usual form: a list of
        paths is a list that rots, and one that rots passes over everything."""
        for path in self.TASK_MODULES:
            with self.subTest(module=path):
                self.assertTrue((SRC / path).exists(), f"{path} has moved")
