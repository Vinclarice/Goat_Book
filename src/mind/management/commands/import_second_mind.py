"""Load a corpus exported from the standalone Second Mind project.

Step 3 of that project's `two-cores.md`. The knowledge core's code moved here
first; this moves the material, which is the half that cannot be re-derived.

**A one-time move, not a sync.** It refuses to run against an owner who already
has notes, because merging two divergent copies of one corpus is a different and
much harder problem than loading one into an empty table, and a command that
silently attempted it would be the wrong tool wearing the right name.

**Owner is re-pointed, not preserved.** The two projects have unrelated user
tables -- the same person is a different row in each -- so every foreign key to a
user is rewritten to the named local account. That is the only rewrite; every
other primary key and relationship is preserved exactly, so `public_id` still
identifies the same thought and a device holding one is not stranded.

**Tokens are deliberately left behind.** An `ApiToken` authenticates a device
against a particular server, and the whole point of this step is that the server
changes. Carrying the hashes across would leave credentials that look valid and
address somewhere that no longer serves them; reconnecting the phone once is the
honest cost.

The load itself is `loaddata`, not hand-written inserts. Django already knows how
to defer constraints, resolve self-references and preserve keys, and the
append-only trigger on the activity log permits inserts -- it refuses updates and
deletes, which is exactly the guarantee that makes the log worth moving intact.
"""

import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from mind.models import Node

# Every model in the export whose `owner` is a user in the *source* project.
_OWNER_FIELDS = ("owner",)

# Left behind rather than translated. See the module docstring.
_SKIPPED_MODELS = ("mind.apitoken",)


class Command(BaseCommand):
    help = "Load a Second Mind corpus export, re-pointing it at a local account."

    def add_arguments(self, parser):
        parser.add_argument("dump", help="A `dumpdata mind` JSON export.")
        parser.add_argument("--owner", required=True, help="Local username to own it.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Load even though this owner already has notes. Almost never right.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be loaded without writing anything.",
        )

    def handle(self, *args, **options):
        try:
            owner = get_user_model().objects.get(username=options["owner"])
        except get_user_model().DoesNotExist:
            raise CommandError(f"no user named {options['owner']!r}")

        path = Path(options["dump"])
        if not path.exists():
            raise CommandError(f"no such file: {path}")

        existing = Node.objects.filter(owner=owner).count()
        if existing and not options["force"]:
            raise CommandError(
                f"{owner} already has {existing} note(s). This is a one-time move "
                "into an empty corpus, not a sync -- reconciling two divergent "
                "copies is a different problem. Pass --force only if you are "
                "certain that is what you want."
            )

        records = json.loads(path.read_text(encoding="utf-8"))
        kept, skipped = [], 0
        for record in records:
            if record["model"] in _SKIPPED_MODELS:
                skipped += 1
                continue
            for field in _OWNER_FIELDS:
                if field in record["fields"]:
                    record["fields"][field] = owner.pk
            kept.append(record)

        counts: dict[str, int] = {}
        for record in kept:
            counts[record["model"]] = counts.get(record["model"], 0) + 1

        for model, count in sorted(counts.items()):
            self.stdout.write(f"  {count:>5}  {model}")
        if skipped:
            self.stdout.write(f"  {skipped:>5}  skipped (credentials do not move)")

        if options["dry_run"]:
            self.stdout.write("Dry run: nothing written.")
            return

        # Written out rather than passed in memory because loaddata takes a path.
        # delete=False on Windows, where a file cannot be reopened while the
        # handle that made it is still open.
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as handle:
            json.dump(kept, handle)
            staged = Path(handle.name)
        try:
            call_command("loaddata", str(staged), verbosity=0)
        finally:
            staged.unlink(missing_ok=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"{Node.objects.filter(owner=owner).count()} note(s) now owned by {owner}"
            )
        )
