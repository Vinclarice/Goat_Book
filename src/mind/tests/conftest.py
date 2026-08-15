from datetime import datetime, timezone as dt_timezone

import pytest
from django.contrib.auth import get_user_model

from mind.models import Node


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_user(
        username="vince", email="v@example.com", password="x"
    )


@pytest.fixture
def other_owner(db):
    return get_user_model().objects.create_user(
        username="someone-else", email="other@example.com", password="x"
    )


@pytest.fixture
def make_node(owner):
    """Nodes with explicit capture times.

    The clock is passed in rather than read inside the domain, so a test never
    depends on when it happens to run.
    """

    def _make(content: str, captured: str = "2026-01-01", source: str = Node.Source.WEB):
        return Node.objects.create(
            owner=owner,
            original_content=content,
            captured_at=datetime.fromisoformat(captured).replace(tzinfo=dt_timezone.utc),
            source=source,
        )

    return _make
