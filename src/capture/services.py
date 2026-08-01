"""The rules a capture has to satisfy, in one place.

There is exactly one rule -- text that isn't blank -- and it lived
implicitly in CaptureForm's CharField (strip + required) until the API
needed the same rule. Two enforcement points that can drift is one too
many for a rule this small, so both call through here now.

Mirrors lists.services.normalize_task_text, deliberately: same shape,
same reason.
"""
from capture.models import Capture


EMPTY_CAPTURE_ERROR = "Write something down first"


class CaptureConflict(Exception):
    pass


def normalize_capture_text(text):
    normalized = (text or "").strip()
    if not normalized:
        raise CaptureConflict(EMPTY_CAPTURE_ERROR)
    return normalized


def create_capture(owner, text):
    return Capture.objects.create(owner=owner, text=normalize_capture_text(text))
