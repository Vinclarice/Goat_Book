# Bittern M1 -- the retry-safety key a mobile client sends, not something a
# browser capture ever needs. See design/bittern-plan.md's M1 section and
# capture.services.create_capture_idempotent.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('capture', '0002_idea'),
    ]

    operations = [
        migrations.AddField(
            model_name='capture',
            name='idempotency_key',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='capture',
            constraint=models.UniqueConstraint(
                fields=('owner', 'idempotency_key'),
                name='capture_owner_idempotency_key_uniq',
            ),
        ),
    ]
