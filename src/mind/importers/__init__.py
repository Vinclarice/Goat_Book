"""Backfill import.

The corpus problem is inherent to a second mind: connections cannot exist before
material accumulates, and no sequencing trick removes that. Import is how the
wait gets shortened — historical material arrives already old, which is the one
thing a freshly captured note cannot be.

Adapters read a format. The runner decides what to write. Timestamp
interpretation happens once, in `base.resolve_captured_at`, rather than being
re-derived and re-broken per format.
"""

from .base import (
    ImportSource,
    SourceRecord,
    TimeQuality,
    import_key,
    resolve_captured_at,
)
from .docx_files import DocxDirectorySource
from .jsonl import JsonlSource, parse_timestamp
from .markdown_files import MarkdownDirectorySource
from .runner import DEFAULT_BATCH_SIZE, ImportReport, existing_keys, run_import

__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DocxDirectorySource",
    "ImportReport",
    "ImportSource",
    "JsonlSource",
    "MarkdownDirectorySource",
    "SourceRecord",
    "TimeQuality",
    "existing_keys",
    "import_key",
    "parse_timestamp",
    "resolve_captured_at",
    "run_import",
]
