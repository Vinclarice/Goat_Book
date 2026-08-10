# project-workspace-plan.md's contract migration. Retires Project.area and
# Item.project now that nothing in the codebase reads either -- see that
# plan's migration section for what's lost: every existing Project.area
# link, and every existing Item.project cherry-pick. Named and counted here
# rather than dropped silently, same practice 0028_delete_ownerless_lists
# already used ahead of its own destructive step.
from django.db import migrations


def log_before_removal(apps, schema_editor):
    Project = apps.get_model("lists", "Project")
    Item = apps.get_model("lists", "Item")
    print(f"projects_with_area={Project.objects.exclude(area=None).count()}")
    print(f"items_with_project={Item.objects.exclude(project=None).count()}")


class Migration(migrations.Migration):

    dependencies = [
        ('lists', '0033_alter_project_area'),
    ]

    operations = [
        migrations.RunPython(log_before_removal, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='item',
            name='project',
        ),
        migrations.RemoveField(
            model_name='project',
            name='area',
        ),
    ]
