"""Backfill sentence vectors.

Separate from capture on purpose: encoding must never sit on the path a thought takes
into the system. A missing model file or a slow machine can cost a proposal, never a
note.

Resumable — nodes already embedded for this model version are skipped, and re-running
after an interruption picks up where it stopped.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from mind import embeddings
from mind.models import Node, SentenceEmbedding


class Command(BaseCommand):
    help = "Compute sentence embeddings for a person's notes."

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True)
        parser.add_argument("--model", default=embeddings.DEFAULT_MODEL)
        parser.add_argument(
            "--index-version",
            default=embeddings.INDEX_VERSION,
            help="Stamped on every vector. Change it with the model, or a mixed "
            "index silently compares vectors from two different models.",
        )
        parser.add_argument("--limit", type=int, help="Stop after N nodes.")
        parser.add_argument(
            "--rebuild",
            action="store_true",
            help="Re-encode nodes that already have vectors for this version.",
        )

    def handle(self, *args, **options):
        try:
            owner = get_user_model().objects.get(username=options["owner"])
        except get_user_model().DoesNotExist:
            raise CommandError(f"no user named {options['owner']!r}")

        if not embeddings.encoder_available(options["model"]):
            raise CommandError(
                "The embedding model is unavailable. It is an optional dependency:\n"
                "  pip install -r requirements-embeddings.txt\n"
                "Everything else in the application works without it."
            )

        version = options["index_version"]
        nodes = Node.objects.filter(
            owner=owner, deleted_at__isnull=True, archived_at__isnull=True
        ).order_by("captured_at")

        if not options["rebuild"]:
            already = SentenceEmbedding.objects.filter(
                index_version=version
            ).values_list("node_id", flat=True)
            nodes = nodes.exclude(pk__in=already)

        if options["limit"]:
            nodes = nodes[: options["limit"]]

        total = nodes.count()
        if not total:
            self.stdout.write("Nothing to embed.")
            return

        self.stdout.write(f"Embedding {total} node(s) with {options['model']} …")
        vectors = 0
        skipped = 0
        for index, node in enumerate(nodes.iterator(), start=1):
            written = embeddings.embed_node(
                node, model_name=options["model"], index_version=version
            )
            vectors += written
            if not written:
                skipped += 1
            if index % 50 == 0 or index == total:
                self.stdout.write(f"  {index}/{total} nodes, {vectors} sentences")

        self.stdout.write(
            self.style.SUCCESS(
                f"{vectors} sentence vector(s) across {total - skipped} node(s)"
            )
        )
        if skipped:
            # Said plainly: a note with no sentence long enough to embed cannot be
            # reached by this detector at all, and a silent count would hide that.
            self.stdout.write(
                self.style.WARNING(
                    f"{skipped} node(s) had no sentence long enough to embed and are "
                    "invisible to the semantic-echo detector."
                )
            )
