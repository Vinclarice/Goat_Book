# Recurring subtasks: `always_recurs`

Addendum to `subtasks-plan.md` — closes a gap a review of the shipped subtask
work found: a subtask completed *before* its recurring parent silently never
reappeared in the next occurrence, because `complete_item` reused the same
"still-active children" list both to decide what to cascade-complete and
what to clone forward. Those are two different questions and shouldn't
share one query.

## Settled decisions

| Question | Decision |
| --- | --- |
| Does a subtask carry forward to the next occurrence regardless of when it was completed? | Per-subtask choice, not a global rule. |
| Field | `Item.always_recurs`, boolean. Meaningful only when `parent_id` is set. |
| Default for new subtasks | `True` — a subtask is assumed part of the recurring routine unless marked otherwise. |
| Setting it on a root task (no parent) | Rejected, same pattern as `SUBTASK_RECURRENCE_ERROR` — meaningless there. |
| Where it's set | At subtask creation (checkbox, defaults checked) and editable later via the same PATCH path as `notes`/`parent`. |
| Independently archived children | Excluded from carry-forward even if `always_recurs=True` — archiving reads as "removed," not "done," so it shouldn't come back on its own. Worth revisiting if that reads wrong once there's real use. |

## Model

```python
# lists/models.py, on Item
always_recurs = models.BooleanField(default=True)
```

Migration `0021_item_always_recurs` — additive with a default, same shape
as `0019_item_notes`: no data migration, no table rewrite on Postgres 11+.

## Service layer

`_lock_open_children(item)` stays exactly as it is — it answers "what must
be resolved because an archived/completed parent can't have live children,"
which has nothing to do with recurrence.

New, separate function for the other question:

```python
def _children_to_carry_forward(item):
    """Every child flagged always_recurs=True that hasn't been independently
    archived -- this is what clones into the next occurrence, regardless of
    whether it's still active, already completed, or about to be cascaded
    by this same action. Deliberately not the same query as
    _lock_open_children: that one is about cascade bookkeeping, this one is
    about what the next occurrence looks like, and conflating them is the
    bug this addendum exists to fix.
    """
    return list(
        Item.objects.filter(parent=item, always_recurs=True)
        .exclude(status=Item.Status.ARCHIVED)
        .order_by("pk")
    )
```

**Ordering matters in `complete_item`.** Compute `_children_to_carry_forward(item)`
*before* the cascade loop mutates any child's status — otherwise an active,
always-recurring child that's about to be cascade-completed would already
show `status=ARCHIVED` by the time this query ran (when `is_recurring`) and
get wrongly excluded by the `.exclude(status=ARCHIVED)` above.

```python
children = _lock_open_children(item)              # unchanged: cascade set
carry_forward = _children_to_carry_forward(item)  # NEW: read before any mutation below
...
if is_recurring:
    item._spawned = _spawn_next_occurrence(item, cascaded=carry_forward)
```

`_spawn_next_occurrence`'s clone needs one more field carried over:
`always_recurs=child.always_recurs`, so the flag persists cycle to cycle
instead of resetting to the model default.

New `set_always_recurs(item, value)`, same guard shape as the other
subtask-only setters:

```python
def set_always_recurs(item, value):
    if item.parent_id is None:
        raise TaskConflict(ALWAYS_RECURS_ON_ROOT_ERROR)
    item.always_recurs = value
    item.save()
    return item
```

## API

`create_item` gains an optional `always_recurs` (bool, default `True`),
accepted only when `parent` is also present. `item_detail` PATCH adds
`always_recurs` to the one-field-per-request set, same as `notes` and
`parent`.

## Tests to add

- Default is `True` on a newly created subtask; explicit `False` is respected.
- A subtask completed independently *before* its recurring parent, with
  `always_recurs=True`, still appears on the spawned occurrence.
- The same scenario with `always_recurs=False` does not carry forward —
  this is the existing (pre-addendum) behavior, now explicit rather than
  incidental.
- A subtask independently archived before the parent completes does not
  carry forward even with `always_recurs=True`.
- Setting `always_recurs` on a root task is rejected.
- The clone on the next occurrence keeps the same `always_recurs` value as
  its source.

## Non-goals

- No change to the rule that subtasks can't carry their own `recurrence` —
  this is a different flag answering a different question.
- No UI beyond a single checkbox at creation and one edit control later; no
  bulk toggle across all of a parent's subtasks.
