from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("completed_tasks", "0004_task_edit_audit"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="pap_value",
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text="PAP value assigned to each accepted completion.",
                validators=[MinValueValidator(1)],
            ),
        ),
    ]
