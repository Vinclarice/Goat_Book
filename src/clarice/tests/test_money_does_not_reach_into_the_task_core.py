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

#: The money modules, by path. Two today; `money/*.py` after step 3.
MONEY_MODULES = ("lists/bills.py", "lists/money.py")

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
