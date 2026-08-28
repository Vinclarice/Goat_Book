"""Every release codename has a narrative in `roadmap-history.md`.

`CLAUDE.md`'s deploy section calls the bird "a permanent annotated release tag
describing what shipped and how it was verified", and `roadmap.md`'s *Release
practice* says what earns one: a subject you can say in a sentence, and a move
in something a document tracks. Both make the bird **a claim that a body of work
finished** -- and a claim with nothing behind it is what this guard exists to
catch.

**Four releases had no narrative when this was written**, found by an audit on
August 26, 2026 rather than by anything automatic. `osprey` -- twenty-one
commits, four of the nineteen journeys moved out of *impossible* -- appeared
**nowhere in `design/` at all**; its only account anywhere was its own tag
message. `petrel` was the second. `godwit` and `ibis` were the other two, and
`godwit` is the Second Mind merger, the largest single piece of work this
project has done.

**A guard rather than an inventory**, for the reason its sibling
`test_dark_services_declare_their_deferral.py` gives at length: an inventory
records the four that were missing, and a guard notices the fifth. The whole
failure here was that nothing noticed -- the tags were written carefully, and
the twelve inches from tag message to record was the step with no trigger on it.

**Annotation is the selector, and it is a rule this tree already states rather
than a trick.** `CLAUDE.md` requires release tags to be annotated so that
`git describe` can see them. So an annotated tag that is neither `LIVE` nor a
`DEPLOYED-` marker is a release codename, and a *lightweight* tag of any name is
somebody's working marker -- `revisit_this_point_with_isolated_tests` is exactly
that, and is correctly invisible to this test without needing to be named in an
exception list that would then need maintaining.

**Deploys without a codename are deliberately not checked.** Most deploys have
no bird, which `roadmap.md` says is correct: a deploy
that is a follow-up, a correction or infrastructure is fully accounted for by
its `DEPLOYED-` tag. Requiring a narrative for each would make the record a log,
which is the thing the codename rule exists to prevent.

**This test reads one file as text and runs one `git` command. It opens no
database**, so it runs anywhere and costs nothing.
"""
import subprocess

from django.conf import settings
from django.test import SimpleTestCase

REPO = settings.BASE_DIR.parent
RECORD = REPO / "design" / "roadmap-history.md"

# The moving pointer and the per-deployment markers are not release codenames.
# Everything else annotated under refs/tags is.
NOT_A_CODENAME = ("LIVE",)
DEPLOYMENT_MARKER = "DEPLOYED-"


def release_codenames():
    """Annotated tags that name a release, newest first is not needed here.

    `for-each-ref` rather than `tag -l` plus `cat-file`: it answers the type and
    the name together in one call, and the type is the whole question -- an
    annotated tag object means somebody wrote a release message, a lightweight
    one means somebody marked a commit.
    """
    result = subprocess.run(
        ["git", "for-each-ref", "--format=%(objecttype) %(refname:short)", "refs/tags"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    names = []
    for line in result.stdout.splitlines():
        objecttype, _, name = line.partition(" ")
        if objecttype != "tag":
            continue
        if name in NOT_A_CODENAME or name.startswith(DEPLOYMENT_MARKER):
            continue
        names.append(name)
    return names


class EveryReleaseIsInTheRecordTest(SimpleTestCase):
    def test_every_release_codename_appears_in_the_record(self):
        record = RECORD.read_text(encoding="utf-8").lower()

        missing = [name for name in release_codenames() if name.lower() not in record]

        self.assertEqual(
            missing,
            [],
            "A release has a codename and no narrative in "
            "design/roadmap-history.md. The tag's own message is the material: "
            "`git tag -l -n60 <name>`. If the deploy should not have had a "
            "codename at all, roadmap.md's *Release practice* says what earns "
            "one -- and the answer is to delete the tag, not to skip the entry.",
        )

    def test_the_tag_sweep_finds_the_releases(self):
        """A positive control, and it is load-bearing rather than decorative.

        `actions/checkout@v4` clones at `fetch-depth: 1` and **fetches no tags**,
        so without `fetch-tags: true` on the job this sweep returns an empty list
        and the assertion above passes while proving nothing. That is the
        un-switched-on seam this repository has now found five times, and it
        would be especially galling in the guard written to stop drift.
        """
        codenames = release_codenames()

        self.assertNotEqual(
            codenames,
            [],
            "No annotated release tags are visible. On CI this means the "
            "checkout fetched no tags -- set `fetch-tags: true` on the job "
            "rather than deleting this assertion, which is the only thing "
            "standing between the test above and passing vacuously.",
        )
        self.assertIn("albatross", codenames)
        self.assertIn("nightjar", codenames)
