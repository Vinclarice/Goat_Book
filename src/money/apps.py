"""The Money module, as a Django app.

**A module is where somebody goes; an app is where its code lives.**
`modules.md` draws that line and Money had earned only the first of them until
September 2, 2026 — it was a destination in the product and a section of
`lists`. The threshold was crossed when `Bill` stopped being an `Item`.

**What it owns**: five models with their own life cycles, its own reads and
writes, its own API namespace, a scheduled job, a vocabulary, and six frontend
surfaces. What it has with the task core is an integration contract — the Day
and the Agenda receive bills through `money.reads` — rather than inheritance
from it.

**`label` is `money` and the models still live in `lists`** until step 4 moves
their state. That is deliberate sequencing: moving code needs no migration, and
moving model state needs one that must not also be a data migration. `0057` and
`0059` were both real ones and there is no appetite for a third in the same
week.
"""
from django.apps import AppConfig


class MoneyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "money"
    verbose_name = "Money"
