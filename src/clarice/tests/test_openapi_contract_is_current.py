"""`frontend/openapi.json` is a generated file, and nothing checked it.

The SPA is typed against this file, not against the server: the chain is
`dump_openapi_schema` -> `generate:api` -> `tsc --noEmit`. Every link after the
first is enforced -- the build type-checks the client against the contract --
but **the first link was enforced by nothing at all.** A Ninja schema change
that never got dumped left the contract describing an API that no longer
existed, and the build stayed green, because it checks the client against the
contract rather than the contract against the server.

**Not hypothetical, and it did not drift once.** On September 7, 2026 the
committed contract was stale for *three separate pieces of work*: the pool
endpoint gaining token auth and the leftovers endpoint gaining it (both
September 6, `android-overhaul-plan.md` increments 3 and 4), and `LoginIn`
gaining `totp`. Two of the three had been committed and pushed a day earlier.
Nothing anywhere went red.

**Why it stayed invisible is worth keeping.** The SPA holds a generated type for
`/api/v1/login` and calls it from nowhere -- it logs in by session. So the one
endpoint whose *shape* had changed was the one endpoint no component referenced,
and the type checker had nothing to disagree with. A contract can be wrong in
exactly the places nothing consumes, which is the argument for checking it
directly rather than trusting a downstream build to notice.

**A regression guard, and it passed the first time it ran** -- `principles.md`
allows that as the honest exception, provided it is said out loud rather than
presented as test-first. What makes it more than decoration is
`TheGuardCanActuallyFailTest` below: the assertion was demonstrated failing
against a deliberately mutated contract before it was trusted, because a
comparison that silently compares nothing to nothing is exactly the shape this
file exists to catch elsewhere.
"""
import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from clarice.api import api


CONTRACT = settings.BASE_DIR.parent / "frontend" / "openapi.json"

REGENERATE = (
    "Run:\n"
    "    python src/manage.py dump_openapi_schema\n"
    "    pnpm --dir frontend generate:api\n"
    "and commit both files together -- the schema and the client generated\n"
    "from it do not earn separate commits, because a commit with one and not\n"
    "the other does not build."
)


def live_schema():
    """The schema as the server would dump it, normalised through JSON.

    The round trip matters: `get_openapi_schema()` returns a dict subclass
    holding tuples and other non-JSON types in places, and comparing that to
    parsed JSON reports differences that `json.dumps` would have erased. This
    compares what would actually be *written* against what is actually
    committed.
    """
    return json.loads(json.dumps(api.get_openapi_schema()))


def committed_schema():
    """Parsed, never compared as text.

    Deliberately not a string comparison. `dump_openapi_schema` writes with
    `path.write_text(...)`, which on Windows translates `\\n` to `\\r\\n` --
    so a byte-for-byte assertion would fail on every Windows checkout while
    passing on CI, which is the worst possible direction for a guard to break.
    The contract is the *structure*; the formatting is not this test's business.
    """
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


class TheContractMatchesTheServerTest(SimpleTestCase):
    def test_the_committed_contract_is_what_the_server_would_dump(self):
        self.assertEqual(committed_schema(), live_schema(), f"\n\n{REGENERATE}\n")

    def test_the_paths_agree(self):
        """The same fact at a coarser grain, for the failure message.

        The assertion above is correct and, on a large schema, prints a diff
        nobody can read. This one names the endpoints that appeared or vanished
        in one line, which is the most common way the contract goes stale --
        somebody added an operation and never dumped.
        """
        self.assertEqual(
            set(committed_schema()["paths"]),
            set(live_schema()["paths"]),
            f"\n\nThe contract and the server disagree about which endpoints "
            f"exist.\n\n{REGENERATE}\n",
        )


class TheGuardCanActuallyFailTest(SimpleTestCase):
    """Positive controls, in the shape `test_api_auth_surface.py` uses.

    Both assertions above compare two things that are *supposed* to be equal,
    which is the one kind of test that keeps passing after it stops reading
    anything -- an empty file against an empty schema is a green run. These
    fail first, and they are the reason the guard above is trustworthy on a run
    where it happens to be green.
    """

    def test_the_contract_file_exists_and_is_not_empty(self):
        self.assertTrue(CONTRACT.exists(), f"{CONTRACT} is missing")
        self.assertGreater(len(committed_schema()["paths"]), 30)

    def test_the_live_schema_is_not_empty(self):
        self.assertGreater(len(live_schema()["paths"]), 30)

    def test_a_changed_contract_is_detected(self):
        """The demonstration, run every time rather than done once by hand.

        Mutates a copy of the committed contract the way a real drift does --
        an endpoint the server has and the contract does not -- and asserts the
        comparison notices. Without this, both tests above could be satisfied by
        a `live_schema()` that had quietly started returning the file it is
        supposed to be checking.
        """
        drifted = committed_schema()
        removed = sorted(drifted["paths"])[0]
        del drifted["paths"][removed]

        self.assertNotEqual(drifted, live_schema())
        self.assertNotEqual(set(drifted["paths"]), set(live_schema()["paths"]))
