"""Writes the /api/v1/ OpenAPI schema to a file for the frontend's TS
codegen step (see frontend/package.json's generate:api script).

Reads from clarice.api directly rather than hitting a running server, so
codegen doesn't depend on the dev server being up:

    python manage.py dump_openapi_schema
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from clarice.api import api


class Command(BaseCommand):
    help = "Write the /api/v1/ OpenAPI schema to frontend/openapi.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "output",
            nargs="?",
            default=str(settings.BASE_DIR.parent / "frontend" / "openapi.json"),
        )

    def handle(self, *args, **options):
        path = Path(options["output"])
        path.write_text(json.dumps(api.get_openapi_schema(), indent=2))
        self.stdout.write(self.style.SUCCESS(f"Wrote OpenAPI schema to {path}"))
