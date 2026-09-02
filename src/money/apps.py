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

**The models moved too, and no table did.** Two state-only migrations changed
which app owns them and emitted no SQL; `db_table` pins each to the `lists_`
name it was created with. That sequencing was deliberate — code first, state
second — because moving code needs no migration at all and it was worth knowing
the code was right before writing one.
"""
from django.apps import AppConfig


class MoneyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "money"
    verbose_name = "Money"
