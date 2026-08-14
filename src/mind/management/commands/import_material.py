"""The import entry point.

An entry point has to read the clock somewhere, and this is that place: it is
read once here and the resulting instant is passed down, so nothing inside the
domain reads it for itself. Note that `now` is used only for the import's own
bookkeeping event — every node's `captured_at` comes from the source record,
which is the entire point of importing rather than re-capturing.
"""

from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from mind.importers import (
    DocxDirectorySource,
    JsonlSource,
    MarkdownDirectorySource,
    run_import,
)


class Command(BaseCommand):
    help = "Import historical material from a directory or export file."

    def add_arguments(self, parser):
        parser.add_argument("path", type=Path)
        parser.add_argument(
            "--owner",
            required=True,
            help="Username the material belongs to. Its time zone interprets "
            "any naive timestamp in the source.",
        )
        parser.add_argument(
            "--format",
            choices=("markdown", "docx", "jsonl"),
            default="markdown",
        )
        parser.add_argument(
            "--recursive",
            action="store_true",
            help="docx only: descend into subdirectories. Off by default, since "
            "those directories also hold thousands of photos and videos.",
        )
        parser.add_argument(
            "--exclude",
            action="append",
            default=[],
            help="docx only, repeatable: skip files whose name contains this "
            "(case-insensitive). Useful for coursework and paperwork mixed in "
            "with personal writing.",
        )
        parser.add_argument(
            "--source-name",
            help="Namespaces import keys. Defaults to the format name. Change it "
            "to import two corpora of the same format without collision — and "
            "never change it afterwards, or the next run re-imports everything.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Read, resolve timestamps, and report without writing.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Stop after N *new* records. Counting created rather than "
            "consumed records is what lets a repeated run make progress.",
        )
        parser.add_argument("--batch-size", type=int, default=200)
        parser.add_argument(
            "--no-mtime",
            action="store_true",
            help="Skip files with no date in front matter or filename rather "
            "than falling back to file metadata.",
        )

    def handle(self, *args, **options):
        path: Path = options["path"]
        if not path.exists():
            raise CommandError(f"{path} does not exist")

        try:
            owner = get_user_model().objects.get(username=options["owner"])
        except get_user_model().DoesNotExist:
            raise CommandError(f"no user named {options['owner']!r}")

        fmt = options["format"]
        name = options["source_name"] or fmt

        if fmt == "markdown":
            if not path.is_dir():
                raise CommandError("--format markdown expects a directory")
            source = MarkdownDirectorySource(
                root=path, name=name, use_mtime_fallback=not options["no_mtime"]
            )
        elif fmt == "docx":
            if not path.is_dir():
                raise CommandError("--format docx expects a directory")
            source = DocxDirectorySource(
                root=path,
                name=name,
                recursive=options["recursive"],
                exclude=options["exclude"],
            )
        else:
            if path.is_dir():
                raise CommandError("--format jsonl expects a file")
            source = JsonlSource(path=path, name=name)

        report = run_import(
            owner,
            source,
            now=timezone.now(),
            batch_size=options["batch_size"],
            limit=options["limit"],
            dry_run=options["dry_run"],
        )

        # ASCII only in console output: the Windows console codepage mangles an
        # em dash into a replacement character.
        prefix = "would import: " if options["dry_run"] else "imported: "
        self.stdout.write(self.style.SUCCESS(prefix + report.summary()))

        if report.guessed_timestamps:
            # Said plainly rather than logged quietly: a corpus resting on file
            # metadata cannot support a temporal detector, and that is worth
            # knowing before the detectors run over it, not after.
            self.stdout.write(
                self.style.WARNING(
                    f"{report.guessed_timestamps} of {report.created} timestamps were "
                    "not stated by the source. Dormancy and recurrence over this "
                    "material will be approximate."
                )
            )
            for quality, count in sorted(report.quality.items()):
                self.stdout.write(f"  {quality}: {count}")

        for external_id, reason in report.failures[:20]:
            self.stdout.write(self.style.ERROR(f"  failed {external_id}: {reason}"))
        if len(report.failures) > 20:
            self.stdout.write(f"  ... and {len(report.failures) - 20} more")

        # An adapter may pass over files for reasons the runner never sees —
        # a password-protected document above all. Reported rather than dropped
        # silently, so the count of what was NOT imported is visible too.
        adapter_skips = getattr(source, "skipped", [])

        if report.reached_runner == 0:
            # A run that reaches nothing looks identical to a run over an empty
            # directory, and the commonest cause is a field-name mismatch: point
            # this at an export whose date field is `date` rather than
            # `created_at` and every record is dropped by the adapter. Silence
            # here would be a successful-looking no-op over a whole corpus.
            self.stderr.write(
                self.style.ERROR(
                    f"Nothing reached the importer from {path}. "
                    f"{len(adapter_skips)} item(s) were passed over by the "
                    f"{fmt} adapter — check the reasons below, and for jsonl "
                    "confirm the content and timestamp field names match the export."
                )
            )

        if adapter_skips:
            self.stdout.write(f"{len(adapter_skips)} item(s) passed over:")
            by_reason: dict[str, int] = {}
            for _, reason in adapter_skips:
                key = reason.split(":")[0]
                by_reason[key] = by_reason.get(key, 0) + 1
            for reason, count in sorted(by_reason.items(), key=lambda kv: -kv[1]):
                self.stdout.write(f"  {reason}: {count}")
