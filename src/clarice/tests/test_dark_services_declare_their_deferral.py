"""Every service nothing calls says so, and says what would switch it on.

`principles.md`, *Deliver vertical slices*: **a slice is not closed while
nothing calls it**, and an undeclared deferral gets a named trigger or a
deletion. This is that rule with teeth, for the app where it kept happening.

**The finding that shaped it.** Twelve services in `src/mind/` had no
production caller, and eleven were the **undo half of a live pair** -- `capture`
has seven callers and `revise`, `delete_node`, `purge_node` and `archive_node`
had none; `link` has two and `unlink` none; `resolve_question` has two and
`reopen_question` none; `confirm_concept` has three and `merge_concept` none.

**`revise` was the first one to come back.** Track E increment 21 gave it the
door its declaration named, and this file found out the way it was built to:
`test_nothing_here_has_quietly_come_alive` failed, and the fix was deleting a
comment that had become untrue.

**`unlink` was the second, on August 26, 2026**, when the note page's
connections section got a "Not this" button on each card -- the exact trigger
its declaration named, two days after it was written. Three `EdgeRelation`
values went live in the same commit and the companion enum guard caught those.
**Both directions have now fired in anger**, which is the argument for a guard
over an inventory: an inventory would still be listing all four.

So the inventory was never twelve pieces of dead code. **It is one missing
surface, listed eleven times**, and deleting them would have deleted half of
eleven features immediately before building the node page that needs them.

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

import ast
import functools
import pathlib
import re

from django.test import SimpleTestCase


SRC = pathlib.Path(__file__).resolve().parents[2]
SERVICES = SRC / "mind" / "services.py"

#: Reads and helpers outside `mind/services.py` that nothing calls either.
#:
#: ~~**Why these modules and not every module.** The rule is about code somebody
#: wrote to be called; a view is reached from a URLconf without parentheses, a
#: model method through the ORM, a management command by name -- each needs a
#: different notion of *caller*, and one scanner over all of them would be four
#: heuristics wearing a trenchcoat. These four are plain function modules where
#: a call looks like a call.~~
#:
#: **The modules are discovered now** -- August 24, 2026. The paragraph above was
#: this file's own failure repeated one level up: it had just learned that a
#: hardcoded list of *functions* cannot notice a new one, and then trusted a
#: hardcoded list of *modules*. `mind/embeddings.py` was not in it.
#:
#: And the trenchcoat argument turned out to be **half wrong, which is why the
#: scan was fixed before the list was widened**: once callers are parsed rather
#: than matched, a view referenced in a URLconf *is* visible -- `urls.py` names
#: it, and naming is what the parser looks for. Views and models are in scope now
#: and produce no false positives across 69 modules and 350 functions. What
#: stays out is `NOT_PLAIN_MODULES`, where the caller genuinely is not a Python
#: reference to the name.
#:
#: So this is a registry of declarations, not a list of places to look.
ELSEWHERE = {
    "lists/agenda.py": ("snooze_presets", "tag_summaries"),
    # `close_account` joined on August 27, 2026, the day accounts were built:
    # they can be created and not removed, so a card somebody stops using stays
    # in the monthly balance pass forever asking for a figure. Its declaration
    # carries the trigger. Found by this test, on work added hours after it was
    # cited approvingly -- which is the argument for a guard over a habit.
    "lists/services.py": ("close_account",),
    # `month_from_bills` joined on August 31, 2026: increment 3 of
    # bill-as-a-model-plan.md is a read against the new `Bill` model, proven
    # against the old one by `lists/tests/test_bill_reads_agree.py` and called
    # by nothing until increment 4 moves the writes. Caught by this test within
    # minutes of being written, which is the third time it has paid for itself.
    "lists/money.py": (
        "landing_from_bills",
        "month_from_bills",
        "open_bills_for",
    ),
    # The whole write half of the bill split, dark together and switching on
    # together -- increment 4 of bill-as-a-model-plan.md. `spawn_next` is
    # absent because `settle` and `remove` call it, which is what this guard
    # means by a caller.
    "lists/bills.py": ("record", "remove", "revise_series", "settle", "update"),
    "routines/reads.py": ("occurrence_for",),
    "accounts/export.py": ("owned_models", "export_key"),
}

#: Where a function's caller is not a Python reference to its name, so absence
#: of one proves nothing. Each entry is a different mechanism, not a taste:
NOT_PLAIN_MODULES = {
    #: Reached from a `.html` by the name its decorator registered, and this
    #: scan deliberately does not read templates -- see `callers_in_module`.
    "templatetags",
    #: Run by the migration framework, by file name, in order.
    "migrations",
    #: Invoked as `manage.py <name>`; the work is a `handle` method.
    "management",
    "tests",
}

#: The same thing at file granularity.
NOT_PLAIN_FILES = {
    #: Framework entry points, called by Django or the server, never by us.
    "__init__.py",
    "settings.py",
    "wsgi.py",
    "asgi.py",
    "apps.py",
    "manage.py",
    "conftest.py",
    #: Registered by decorator -- `@admin.register`, `@router.get` -- so the
    #: function is never named a second time. `api_v1.py` and `api.py` are
    #: matched by prefix below for the same reason.
    "admin.py",
    #: A test helper that lives outside `tests/` so both runners can import it.
    #: Its callers are all tests, which this scan excludes by design.
    "testing.py",
}

#: Live functions the scan has to keep finding, one per shape it used to miss.
#:
#: **This is the guard's guard, and it is the direction that actually hurts.**
#: A missed dark service is a deferral nobody declared; a *live* function
#: reported dark invites a `# DARK:` comment onto working code, which the
#: module docstring above calls worse than no declaration at all. Widening
#: `ELSEWHERE` by hand -- which `clarice-v4-plan.md` asks for -- is exactly
#: when that happens, so the instrument is held first.
#:
#: All six were found by pointing the scan at every plain-function module in
#: `src/` on August 24, 2026 and reading the 41 results instead of believing
#: them. Every one is a **different** blind spot, which is why they are fixed
#: by parsing rather than by six more regexes:
LIVE = {
    # A parenthesised, multi-line `from ... import (...)`. The old import
    # pattern ended at `[^\n(]+` -- it stopped dead at the bracket and at the
    # newline, so no call site written this way was ever visible. Three of
    # these, and `/privacy/`'s "everything" promise is downstream of the
    # module they live in.
    ("emails", "send_activation_email"): "parenthesised import",
    ("emails", "notify_admins_of_pending_signup"): "parenthesised import",
    ("emails", "send_support_message"): "parenthesised import",
    # Referenced as a value, never called: `before_send=without_the_query_string`
    # in `monitoring.py`. A function handed to somebody else to call is as live
    # as one invoked, and the scan only looked for `(`.
    ("monitoring", "without_the_query_string"): "callback reference",
    # Called from `mind/services.py` and nowhere else. `production_sources()`
    # drops that file so the mind scan cannot count its own internals, and the
    # exclusion leaked into every other module's scan with it.
    ("commitments", "find_commitment"): "caller is the excluded home file",
    # Re-exported through `importers/__init__.py`, which imports it and does
    # not call it; the management command then imports it from the package.
    # A one-hop chain the scan could not follow.
    ("runner", "run_import"): "re-export chain",
}

#: The ones still dark, each with the live half whose absence of an undo it
#: represents, or None where it is not an undo half at all.
#:
#: **The count used to be in this sentence and is not any more.** It read *"the
#: ten still dark"* while the dict held thirteen -- three were added on August 24
#: and the prose was not, in the file whose entire subject is a declaration
#: outliving what it declares. `len(DARK)` is exact and free; a number written
#: out is a second copy of a fact, which is the mistake `design/README.md` spends
#: a table preventing.
#:
#: **Kept as a list rather than derived**, for the reason `NOT_DRILLED` and
#: `PERSON_EVENTS` are: a set computed from the code cannot fail when something
#: is forgotten, only when it is removed. This one fails both ways -- a new dark
#: service is caught by `test_every_dark_service_is_declared`, and one that
#: gains a caller is caught by `test_nothing_here_has_quietly_come_alive`.
DARK = {
    "delete_node": "capture",
    "purge_node": "capture",
    "archive_node": "capture",
    # `unlink` came off this list on August 26, 2026, when the note page's
    # connections section gained a "Not this" button -- the trigger its own
    # declaration named. Ten left.
    "reopen_question": "resolve_question",
    "merge_concept": "confirm_concept",
    "confirm_mention": "propose_mention",
    # `mark_reviewed` came off this list on August 22, 2026, when **D15** was
    # answered and `mind.views.this_time_before` began calling it. The guard
    # caught it in the same run that wired it, which is what it is for -- and
    # the pleasant direction, since the alternative is finding out months later
    # that a declaration had gone stale.
    "resolve_retrieval_miss": None,
    "expire_stale_hypotheses": None,
    "commitments_without_tasks": None,
    # The three `test_the_list_is_the_whole_list` found on August 24, 2026,
    # none of them an undo half and none a leftover: two writers-and-readers
    # whose surfaces were never built, and one pass nothing schedules. All
    # three post-date the file, which is exactly what the hardcoded list could
    # not notice on its own.
    "what_a_task_was_read_in": None,
    "make_it_the_goal": None,
    "run_producers_over_unprocessed": None,
}


def production_sources(exclude=SERVICES):
    """Every non-test Python and template file, minus one definitions' home.

    `exclude` defaults to `mind/services.py` because the two `DARK` tests count
    outside callers only -- `internal_callers_of` answers separately for calls
    within that file. **It is a parameter rather than a constant since August
    24, 2026**: the exclusion had leaked into every other module's scan, so a
    function whose only caller is `mind/services.py` -- `find_commitment` --
    read as dark from a file that was in fact calling it. Pass `exclude=None`
    for any scan that is not about `mind/services.py`.
    """
    for path in SRC.rglob("*.py"):
        if "tests" in path.parts or path.name.startswith("test_"):
            continue
        if exclude is not None and path == exclude:
            continue
        yield path
    yield from SRC.rglob("*.html")


def plain_modules():
    """Every module whose functions are reached by naming them in Python.

    Discovered rather than listed, which is the whole correction of August 24,
    2026 -- see `ELSEWHERE`. Everything in `src/` qualifies unless it is in
    `NOT_PLAIN_MODULES` or `NOT_PLAIN_FILES`, so a new module is in scope the
    day it is written and nobody has to remember this file exists.
    """
    for path in SRC.rglob("*.py"):
        if NOT_PLAIN_MODULES & set(path.parts):
            continue
        if path.name in NOT_PLAIN_FILES or path.name.startswith("test_"):
            continue
        # Ninja routers, registered by decorator like `admin.py` above.
        if path.name.startswith("api"):
            continue
        yield path


@functools.lru_cache(maxsize=None)
def references(text):
    """Every `(module, name)` this file reaches for, however it was written.

    **Cached on the source text**, because the scan asks this question once per
    service per file -- 49 services against several hundred files is twenty
    thousand parses, and it took the suite from 7 seconds to 19 before the
    cache went on. A file's text is its own cache key: two files with identical
    contents genuinely have identical references.

    **Parsed rather than matched.** Four separate blind spots came out of one
    afternoon's sweep and each would have needed its own regex: a parenthesised
    import, a function handed over as a callback, a caller sitting in the file
    the scan excluded, and a re-export chain. `ast` answers all four at once and
    keeps the property the module docstring claims -- this reads source as text
    and never opens a database.

    Two shapes count as reaching for a name, and the second is the one regexes
    missed: **calling it**, and **naming it at all**. `before_send=f` is as much
    a caller as `f()`, because somebody else is going to call it.

    A bare `import` on its own does not count. That distinction is what keeps a
    genuinely dark service from looking live because a package re-exported it --
    the re-export is followed by `reexports()` instead, which is honest about
    being a second hop rather than a use.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:  # pragma: no cover -- a template, or a file mid-edit
        return set()

    # local name -> (module, original name), from `from x import y as z`
    imported = {}
    # local name -> module, from `import x.y as z` and `from . import y`
    modules = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            origin = (node.module or "").split(".")[-1]
            for alias in node.names:
                local = alias.asname or alias.name
                if origin:
                    imported[local] = (origin, alias.name)
                else:  # `from . import queries` -- the name *is* the module
                    modules[local] = alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                modules[local] = alias.name.split(".")[-1]

    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            found.add((module_behind(node.value.id, imported, modules), node.attr))
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute):
            # The last two links of a longer chain. `Item.Status.ACTIVE` is
            # three deep, and reading only the first two says `Status` is a
            # thing `Item` has and stops -- which reported every value of six
            # enums unwritten, `Item.Status.ACTIVE` included. Cheap, and it can
            # only ever add a caller, never remove one.
            found.add((node.value.attr, node.attr))
        elif isinstance(node, ast.Name) and node.id in imported:
            found.add(imported[node.id])
    return found


def module_behind(local, imported, modules):
    """Which module a local name stands for, when it stands for one.

    `from lists import agenda as lists_agenda` puts the alias in `imported`
    rather than `modules`, because syntactically it is a name being imported
    from a package -- and it is also the module every `lists_agenda.x(...)`
    call goes through. Consulting only `modules` reported the whole of
    `lists/agenda.py` dark, `coming_up_for` included, which `daily/reads.py`
    calls on the day page.
    """
    if local in modules:
        return modules[local]
    if local in imported:
        return imported[local][1]
    return local


def reexports(sources):
    """`(package, name) -> (module, name)` for every `__init__.py` pass-through.

    `mind/importers/__init__.py` imports `run_import` from `.runner` and never
    calls it; `management/commands/import_material.py` then imports it from the
    package. Neither file on its own looks like a caller, and together they are
    one. Followed exactly one hop, because that is how deep this codebase goes
    and a general resolver would be a package importer wearing a test.
    """
    aliases = {}
    for path, text in sources.items():
        if path.name != "__init__.py":
            continue
        package = path.parent.name
        try:
            tree = ast.parse(text)
        except SyntaxError:  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                origin = node.module.split(".")[-1]
                for alias in node.names:
                    exported = alias.asname or alias.name
                    aliases[(package, exported)] = (origin, alias.name)
    return aliases


def callers_of(name, sources):
    """Anything reaching `services.name`, by any of the four shapes.

    ~~Calls written as `<something>services.name(`.~~ **Delegated to the parsed
    scan on August 24, 2026.** The regex was right about the two blind spots it
    was built for -- `staged.unlink(missing_ok=True)` is `pathlib`'s method and
    has nothing to do with `services.unlink`, and a view referenced in a URLconf
    is never called with parentheses -- and it still could not see a
    parenthesised import or a callback.

    **The two were compared before switching rather than assumed equivalent**:
    they agree on all 49 public services in `mind/services.py`, so this changes
    no verdict today. What it buys is the case that has not happened yet -- a
    node page calling `from mind.services import delete_node` rather than
    `services.delete_node`, which the regex would have called dark forever,
    against a file whose whole subject is declarations going stale.
    """
    return callers_in_module("services", name, sources)


def public_services(source):
    """Every module-level `def` in `services.py` that is not private.

    Module-level only -- `^def` rather than `\\s*def` -- because a nested
    helper is reached through the function that encloses it, and a method on a
    dataclass is not a service.
    """
    return [
        name
        for name in re.findall(r"^def (\w+)\(", source, re.MULTILINE)
        if not name.startswith("_")
    ]


def aliases_for(modname, text):
    """Every name a module is reachable by in one file.

    `from lists import projects as project_reader` is the case that makes this
    necessary: a bare module-name regex reported three live functions in
    `lists/projects.py` as dark, because every call site says
    `project_reader.project_for(...)`. A guard that cannot see an alias would
    invite declarations onto working code, which is the failure this file calls
    worse than no declaration at all.
    """
    names = {modname}
    for match in re.finditer(r"from\s+[\w.]+\s+import\s+([^\n(]+)", text):
        for part in match.group(1).split(","):
            bits = part.strip().split()
            if len(bits) == 3 and bits[1] == "as" and bits[0] == modname:
                names.add(bits[2])
    for match in re.finditer(rf"import\s+[\w.]*\b{modname}\s+as\s+(\w+)", text):
        names.add(match.group(1))
    return names


def callers_in_module(modname, name, sources):
    """Every file that reaches `modname.name`, through any of the four shapes.

    **Rewritten August 24, 2026**, after pointing the scan at every plain-function
    module in `src/` reported 41 dark functions and reading them found six that
    were live -- one per shape the regexes could not see. See `LIVE`, which holds
    the six so this cannot regress.

    Templates are still matched as text: a `.html` file has no syntax tree, and
    what it does with a name is call it from a tag.
    """
    wanted = {(modname, name)}
    for alias, target in reexports(sources).items():
        if target == (modname, name):
            wanted.add(alias)

    # Templates are deliberately not searched, and the first attempt at this
    # searched them. `privacy.html` documents the export by writing
    # *"owned_models(), which is why 'everything' is true"* -- prose, in a
    # sentence about the function, which a `name\s*\(` match reads as a call
    # and promotes to a live caller. A Django template reaches Python through
    # tags and filters, never by name, so there is nothing here to miss and a
    # false *live* is the one error this file cannot afford: it retires a
    # declaration on a function that has still never run.
    return [
        path
        for path, text in sources.items()
        if path.suffix == ".py" and references(text) & wanted
    ]


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
    called = [
        line
        for line in re.findall(rf".*\b{re.escape(name)}\s*\(.*", source)
        if not line.lstrip().startswith("def ")
    ]
    return called or internal_references(name, source)


def internal_references(name, source):
    """The same file naming the function without calling it.

    **Added August 24, 2026.** `monitoring.without_the_query_string` is handed
    to Sentry as `before_send=without_the_query_string` -- no parentheses, in
    the module that defines it, so both halves of the scan missed it and a live
    redaction hook read as dark. A function passed to somebody else to call is
    live; that is what a callback is.

    Parsed rather than matched so a mention inside a docstring or a comment --
    of which this file's own subject matter produces many -- cannot count.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:  # pragma: no cover
        return []
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == name
    ]


class DarkServicesTest(SimpleTestCase):
    def setUp(self):
        self.source = SERVICES.read_text(encoding="utf-8")
        # A mapping now rather than a list: the parsed scan reads each file
        # once here instead of once per service, which is what keeps a scan
        # over 49 services and several hundred files to a few seconds.
        self.sources = {
            path: path.read_text(encoding="utf-8", errors="ignore")
            for path in production_sources()
        }

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

    def test_the_scan_does_not_report_live_code_as_dark(self):
        """The guard's guard -- see `LIVE`.

        Every other test here trusts `callers_in_module` to know what a caller
        is. This one checks the instrument against six functions that demonstrably
        have callers, so that widening the scan cannot quietly start recommending
        `# DARK:` comments for working code.
        """
        sources = {
            path: path.read_text(encoding="utf-8", errors="ignore")
            # `exclude=None`, because this is not a scan about
            # `mind/services.py` -- and one of the six is live precisely
            # because that file calls it.
            for path in production_sources(exclude=None)
        }
        for (module, name), shape in LIVE.items():
            with self.subTest(module=module, function=name, shape=shape):
                # The same two halves `test_the_wider_registry_is_declared_and_whole`
                # puts together, rather than one of them: a function called only
                # by the file that defines it is live, and asserting on the
                # outside half alone would demand a caller that need not exist.
                home = next(p for p in sources if p.stem == module)
                self.assertTrue(
                    callers_in_module(module, name, sources)
                    or internal_callers_of(name, sources[home]),
                    f"{module}.{name} is live and the scan cannot see it "
                    f"({shape}) -- fix the scan, do not declare it dark",
                )

    def test_the_list_is_the_whole_list(self):
        """`DARK` is discovered rather than trusted, which is the half this
        file claimed and did not have.

        Its docstring said the list *"fails both ways -- a new dark service is
        caught by `test_every_dark_service_is_declared`"*. It was not: that
        test iterates `DARK`, so it can only notice a name somebody has already
        written down. A service that goes dark **after** this file was written
        was invisible to every test in it, which is the failure mode the file
        exists to prevent, one level up.

        Three had, and none was a leftover -- they are the same *undo half of
        a live pair* shape the module docstring describes, plus one scheduled
        pass nothing schedules.
        """
        undeclared = sorted(
            name
            for name in public_services(self.source)
            if not callers_of(name, self.sources)
            and not internal_callers_of(name, self.source)
            and name not in DARK
        )

        self.assertEqual(
            undeclared,
            [],
            f"{undeclared} have no caller and are not declared -- add each to "
            f"DARK with a trigger, or delete it",
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

    def test_the_wider_registry_is_declared_and_whole(self):
        """The same rule past `mind/services.py`, over every module there is.

        August 24's first discovery test covered one file, so five functions in
        three other modules were dark and unguarded -- including two the plan
        corpus had listed for two days without anything failing. Widening it to
        a hardcoded set of three modules repeated the same mistake one level up,
        and `mind/embeddings.py` was the one it missed.

        **So the modules are discovered too**, and the assertion is that the
        tree's dark set and the declared set are the same set. Both directions,
        for every module at once: a function that goes dark in a module nobody
        listed is caught, and one that gains a caller is caught.
        """
        everything = {
            path: path.read_text(encoding="utf-8", errors="ignore")
            for path in production_sources(exclude=None)
        }

        for path in sorted(plain_modules()):
            if path == SERVICES:
                continue  # `DARK` owns this one, with its live-half pairing.
            rel = path.relative_to(SRC).as_posix()
            source = everything[path]
            declared = ELSEWHERE.get(rel, ())
            sources = {p: t for p, t in everything.items() if p != path}

            with self.subTest(module=rel):
                dark = [
                    name
                    for name in public_services(source)
                    if not callers_in_module(path.stem, name, sources)
                    and not internal_callers_of(name, source)
                ]
                self.assertEqual(
                    sorted(dark),
                    sorted(declared),
                    f"{rel}: the dark set has moved -- declare a new one in "
                    f"ELSEWHERE with a trigger, or delete it, or remove the "
                    f"declaration of one that came alive",
                )

        for rel, declared in ELSEWHERE.items():
            source = (SRC / rel).read_text(encoding="utf-8")
            for name in declared:
                with self.subTest(module=rel, function=name):
                    declaration = re.search(
                        rf"((?:^# .*\n)+)def {re.escape(name)}\(", source, re.MULTILINE
                    )
                    self.assertTrue(
                        declaration
                        and "# DARK: no production caller." in declaration.group(1)
                        and (
                            "Trigger:" in declaration.group(1)
                            or "Decision registered:" in declaration.group(1)
                            or "Decide before wiring" in declaration.group(1)
                        ),
                        f"{rel}:{name} is dark without saying so and naming a trigger",
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
