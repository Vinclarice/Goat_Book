"""Carry `MoneyLine`'s not-negative guarantee onto `Bill` — increment 8 of
`design/bill-as-a-model-plan.md`.

**Not a new rule; a rescued one.** The sidecar `0059` deletes carried
`money_line_amount_not_negative` -- *a bill is something owed, a negative one is
a refund* -- and refused it in the database *"as well as at the boundary,
because the boundary is not the only writer"*. `Bill` was built without it, so
between September 1 and 2, 2026 the only thing refusing a negative bill was
Python. Deleting the old model without this would have dropped a guarantee
quietly, which is what `principles.md` means by buying retry- and
integrity-safety with a constraint rather than with care.

**Wider than the original**: `paid_amount` is included, which
`money_line_amount_not_negative` never covered. It records what actually moved,
and money moving backwards is the same refund the other column already refuses.

**Safe to apply.** Development and production both hold zero negative rows --
`bills.record` and `bills.update` have refused them at the boundary since the
model existed, and every row in production was written by the conversion in
`0055` from a column that carried the original constraint.
"""
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lists', '0059_delete_moneyline'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='bill',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('amount__isnull', True), ('amount__gte', 0), _connector='OR'), models.Q(('paid_amount__isnull', True), ('paid_amount__gte', 0), _connector='OR')), name='bill_amount_not_negative'),
        ),
    ]
