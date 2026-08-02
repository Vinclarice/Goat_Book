"""Crane 1 slice 3's acceptance: two ways in, one kind of row.

A thought typed on the Daily Page must be "indistinguishable in the triage
flow from one typed on the Inbox's own form". The Daily Page adds no
server code to achieve that -- it posts to the capture endpoint that
already exists, which without an Idempotency-Key calls the same
`create_capture` the Inbox form calls.

That makes the guarantee structural rather than coincidental, which is
exactly why it is worth a test: the claim is easy to break later by adding
something to one path and not the other, and nothing else in the suite
compares the two.
"""
from django.test import Client, TestCase

from accounts.models import User
from capture.models import Capture


PASSWORD = "correct horse battery staple 47!"

# Everything triage reads off a row. Deliberately spelled out rather than
# compared with a blanket __dict__, so a new field is a decision someone
# makes about both paths rather than something a loose assertion absorbs.
TRIAGE_FIELDS = (
    "text",
    "owner_id",
    "resolved_at",
    "resolution",
    "promoted_task_id",
    "promoted_idea_id",
    "idempotency_key",
)


class CapturePathsAgreeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.user)

    def snapshot(self, capture):
        return {field: getattr(capture, field) for field in TRIAGE_FIELDS}

    def test_the_daily_pages_route_and_the_inbox_form_write_the_same_row(self):
        self.client.post("/capture/new/", {"text": "A thought from the Inbox"})
        from_form = Capture.objects.get(text="A thought from the Inbox")

        self.client.post(
            "/api/v1/capture",
            data='{"text": "A thought from the Daily Page"}',
            content_type="application/json",
        )
        from_api = Capture.objects.get(text="A thought from the Daily Page")

        form_row = self.snapshot(from_form)
        api_row = self.snapshot(from_api)
        # The text differs by construction; everything else must not.
        form_row.pop("text")
        api_row.pop("text")
        self.assertEqual(form_row, api_row)

    def test_a_capture_from_the_api_carries_no_retry_identity(self):
        """The mobile client's key is mobile-only.

        A browser capture that arrived with one would sort differently under
        the owner-scoped unique constraint, and would be the one visible
        difference between the two paths.
        """
        self.client.post(
            "/api/v1/capture",
            data='{"text": "From the Daily Page"}',
            content_type="application/json",
        )

        self.assertIsNone(Capture.objects.get().idempotency_key)

    def test_both_paths_refuse_an_empty_capture(self):
        self.client.post("/capture/new/", {"text": "   "})
        response = self.client.post(
            "/api/v1/capture",
            data='{"text": "   "}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Capture.objects.count(), 0)

    def test_both_paths_normalise_text_the_same_way(self):
        """Behavioural rather than structural, so this one has teeth.

        The form's CharField strips and the API calls
        normalize_capture_text; if either stopped, the same typing would
        produce two different rows and triage would show a ragged Inbox.
        """
        padded = "  a thought with room around it  "

        self.client.post("/capture/new/", {"text": padded})
        self.client.post(
            "/api/v1/capture",
            data=f'{{"text": "{padded}"}}',
            content_type="application/json",
        )

        texts = list(Capture.objects.values_list("text", flat=True))
        self.assertEqual(len(texts), 2)
        self.assertEqual(texts[0], texts[1])
        self.assertEqual(texts[0], "a thought with room around it")

    def test_a_capture_made_through_the_api_lands_in_the_inbox(self):
        """The whole point: it shows up where triage happens."""
        self.client.post(
            "/api/v1/capture",
            data='{"text": "Ship slice 3"}',
            content_type="application/json",
        )

        inbox = self.client.get("/capture/")

        self.assertContains(inbox, "Ship slice 3")
