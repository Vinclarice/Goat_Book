"""Errors that mean the same thing in more than one domain.

**One class, because the boundary treats them alike.** `api_v1` turns a refused
write into a 409 and a sentence, and it does that identically whether a task or
a bill refused it. What it should not have to do is catch something called
`TaskConflict` around a call about money.

**Extracted September 2, 2026**, step 2 of moving Money into its own app.
`lists.services.TaskConflict` and `lists.bills.BillConflict` both subclass
`Conflict`, so a handler may catch the base and get either, or catch one and
get only that. Existing handlers that name `TaskConflict` keep working and keep
meaning what they said.
"""


class Conflict(Exception):
    """A write refused because the domain says no, not because it broke.

    Distinct from a validation error: the request was well formed and the
    answer is still no — *there is already an open bill from Amazon*, *restore
    this task before editing it*. The boundary owes the caller a sentence it
    can show, so the message is written for a person rather than for a log.
    """
