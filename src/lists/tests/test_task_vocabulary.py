"""What the API calls a task — coherence-audit-2026-08-30.md F5.

The sibling of [`test_area_vocabulary.py`](test_area_vocabulary.py), which
guards the `List` → "Area" half of the same finding. This guards the `Item` →
"task" half, and it reads the **published OpenAPI schema** rather than the
router source, because the schema is what the generated client is built from
and therefore what a client can actually see.

**The model stays `Item` and the app stays `lists`.**
`architecture-trajectory.md` §7 refuses renaming either for a cosmetic reason,
and nothing here asks it to. The boundary is the whole scope: what a client
reads, not what the ORM calls its columns. `lists/api_v1.py`'s own docstring
carries the same split for Area.

**Two things are deliberately exempt, and the exemption has a trigger rather
than being a permanent carve-out** — see `EXEMPT` below.
"""
from django.test import SimpleTestCase

from clarice.api import api


#: Payload keys that still say `Item` and are frozen by the shipped Android
#: build, which reads them with `getString`/`getJSONArray` and would throw
#: without them.
#:
#: **Not a refusal — a deferral whose trigger is named.** They move the day
#: `android-release-signing-plan.md`'s keystore lets a signed release carry a
#: client that reads the new names, which is the same trigger that retires
#: `lists/api.py`. Renaming the two payloads Android *doesn't* read while these
#: two stay would split the vocabulary rather than close it, which is the
#: failure F5 describes rather than a step toward fixing it.
EXEMPT = {
    # AgendaApi.parseAgenda
    ("AgendaOut", "items"),
    # DailyApi, the Day payload's own list of what is due
    ("DayOut", "action_items"),
    # AreaDetailOut and ArchiveOut also say `items`, and are held with the two
    # above on purpose: three payloads agreeing is worth more than two of them
    # being right.
    ("AreaDetailOut", "items"),
    ("ArchiveOut", "items"),
}


def _schema():
    return api.get_openapi_schema()


class TaskVocabularyTest(SimpleTestCase):
    def test_no_path_parameter_calls_a_task_an_item(self):
        """The one this test was written for.

        `/api/v1/tasks/{item_id}` and `/api/v1/tasks/{task_id}/checklist-steps`
        sat two routes apart in one file, naming the same object two ways --
        which is exactly what `api_urls.py` called *"two vocabularies in one
        path"* about the endpoints these replaced.

        Nothing on the wire changes when this is fixed: a path parameter's name
        appears in the schema and the generated client, never in the URL. That
        is what makes it free to correct, and what made it easy to leave wrong.
        """
        offenders = [
            path
            for path in _schema()["paths"]
            if "{item_id}" in path or "{list_id}" in path
        ]

        self.assertEqual(offenders, [])

    def test_no_response_field_calls_a_task_an_item(self):
        offenders = {
            (name, field)
            for name, schema in _schema()["components"]["schemas"].items()
            for field in schema.get("properties", {})
            if field in ("item", "items", "item_id", "action_items")
        }

        self.assertEqual(offenders - EXEMPT, set())

    def test_the_exemptions_still_exist(self):
        """An exemption for a field nobody serves any more is a comment
        pretending to be a rule, and it is how this guard would quietly stop
        guarding anything."""
        served = {
            (name, field)
            for name, schema in _schema()["components"]["schemas"].items()
            for field in schema.get("properties", {})
        }

        self.assertEqual(EXEMPT - served, set())


class ABillDoesNotCallItsKeyATaskTest(SimpleTestCase):
    """Increment 9 of `design/bill-as-a-model-plan.md`.

    **The key said `task_id` and pointed at a `Bill` for two days**, on purpose:
    a mechanical rename across the server, the contract, four routes and the SPA
    is the wrong thing to carry into the commit that changes what a bill *is*.
    It was the last thing in the money module still speaking the task core's
    vocabulary, and this is what stops it coming back.

    **Not a blanket ban.** `ChecklistStepOut.task_id` and every `/tasks/{id}`
    route name a genuine `Item` and are correct; a pin is a `DailyFocus` with a
    foreign key to one. What is refused is a bill-shaped schema carrying the
    word.
    """

    BILL_SCHEMAS = ("MonthBillOut", "AgendaBillOut", "LandingLineOut", "NextPaymentOut")

    def _properties(self, name):
        return _schema()["components"]["schemas"][name]["properties"]

    def test_no_bill_schema_has_a_task_id(self):
        for name in self.BILL_SCHEMAS:
            with self.subTest(schema=name):
                self.assertNotIn(
                    "task_id",
                    self._properties(name),
                    f"{name} points at a Bill; `task_id` is the task core's "
                    "word and this module stopped speaking it.",
                )

    def test_the_bill_routes_take_a_bill_id(self):
        """The path parameter too, not only the payload. A route reading
        `entry/{task_id}` is the same claim in the place a person looks first."""
        paths = [
            route for route in _schema()["paths"] if "/money/bills/entry/" in route
        ]

        self.assertTrue(paths, "the bill entry routes have moved")
        for route in paths:
            with self.subTest(route=route):
                self.assertNotIn("task_id", route)

    def test_the_sweep_finds_the_schemas_it_claims_to(self):
        """A positive control, for the reason every guard here carries one: a
        lookup that quietly found nothing would pass over an empty set."""
        for name in self.BILL_SCHEMAS:
            self.assertIn("payee", self._properties(name))
