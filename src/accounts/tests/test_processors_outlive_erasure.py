"""Every processor that outlives an erasure is named where the erasing happens.

`security-and-resilience-plan.md` 2.2, and its acceptance in that plan's words:
the steps a purge does not perform, **named at
`accounts.services.purge_account`**, with the argument for why they are manual,
"so the gap is visible at the function rather than only in a roadmap".

**The gap was never that the promise was unmade.** `/privacy/` has said the
honest thing since August 19, 2026 — deleting an account does not reach an error
report already sent to Sentry or a delivery record already at Resend, and those
are cleared by hand on request. **What was missing is that the function doing
the erasing did not know.** Somebody reading `purge_account` to find out what
erasure covers would have finished believing it covered everything.

**So this test ties three places together and fails if they part company.** A
processor is declared once, at the settings line that configures it, with a
`# PROCESSOR:` marker — the same shape as the `# DARK:` declarations the
knowledge core already uses, and for the same reason: the declaration goes where
a reader meets the thing, not in a document they would have to know to look for.
Every declared processor must then be named **in `purge_account`'s docstring**
and **on the published policy**.

**The failure it is built for is a third processor**, not a rewrite. Adding one
is a two-line settings change that silently widens what survives an erasure, and
nothing else in this repository would notice. This does.

**It does not grade prose and does not read the plan.** It asserts three
mentions of a name. Whether the argument beside the name is any good stays
Vince's to keep true by reading it, which is `test_legal_pages.py`'s stated
position and this file takes the same one.
"""
import re

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from accounts.services import purge_account

REPO = settings.BASE_DIR.parent
SETTINGS_FILE = REPO / "src" / "clarice" / "settings.py"

# `# PROCESSOR: <name>` at the line that configures a third party this
# application sends personal data to and cannot erase from.
PROCESSOR = re.compile(r"#\s*PROCESSOR:\s*([A-Za-z][A-Za-z0-9_-]*)")


def declared_processors():
    """The processors settings.py declares, lowercased, deduplicated."""
    text = SETTINGS_FILE.read_text(encoding="utf-8")
    return sorted({name.lower() for name in PROCESSOR.findall(text)})


class ProcessorsOutliveErasureTest(TestCase):
    def test_the_declaration_sweep_finds_something(self):
        """A positive control, for the reason its siblings carry one.

        A regex that matched nothing would make every assertion below pass over
        an empty list, and the file would read as coverage while proving that
        zero things satisfy a condition. This repository has now found five
        seams that were never switched on; a test asserting something about the
        empty set is the same mistake wearing a lab coat.
        """
        self.assertNotEqual(
            declared_processors(),
            [],
            "No `# PROCESSOR:` declarations in settings.py. Either the markers "
            "were removed, or this application no longer sends personal data "
            "anywhere it cannot erase from -- and the second would be worth "
            "celebrating rather than quietly passing a test.",
        )

    def test_purge_account_names_every_processor_it_cannot_reach(self):
        doc = (purge_account.__doc__ or "").lower()

        missing = [name for name in declared_processors() if name not in doc]

        self.assertEqual(
            missing,
            [],
            "A processor receives personal data that `purge_account` cannot "
            "erase, and the function's own documentation does not say so. "
            "Somebody reading it to find out what erasure covers would finish "
            "believing it covered everything. Name it in the docstring, with "
            "what it holds and why clearing it is manual.",
        )

    def test_the_published_policy_names_every_processor_too(self):
        """The same names, on the page that makes the promise to a person.

        Held here rather than in `test_legal_pages.py` because the interesting
        failure is the two drifting apart: a processor added to the code and to
        the docstring, and never to the policy, is a published promise quietly
        becoming false.
        """
        page = self.client.get(reverse("privacy")).content.decode().lower()

        missing = [name for name in declared_processors() if name not in page]

        self.assertEqual(
            missing,
            [],
            "A processor survives account deletion and /privacy/ does not "
            "mention it. The page's own comment says this file is part of any "
            "change to what the application sends -- this is that change.",
        )
