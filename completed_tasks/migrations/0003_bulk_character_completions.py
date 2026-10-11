import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("completed_tasks", "0002_task_department_permissions"),
        ("authentication", "0015_user_profiles"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="allow_bulk_submissions",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="taskcompletion",
            name="character",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="completed_task_reports",
                to="eveonline.evecharacter",
            ),
        ),
        migrations.AddField(
            model_name="taskcompletion",
            name="submitted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="submitted_task_completions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterModelOptions(
            name="task",
            options={
                "ordering": ("-created_at", "-pk"),
                "permissions": [
                    ("access_task_reports", "Can access task reports"),
                    ("view_all_completions", "Can view all task completions"),
                    ("approve_task_completions", "Can approve any task completion"),
                    ("export_all_completions", "Can export all task completions"),
                    (
                        "add_department_tasks",
                        "Can create tasks for an authorized department",
                    ),
                    (
                        "view_department_completions",
                        "Can view completions for an authorized department",
                    ),
                    (
                        "approve_department_completions",
                        "Can approve completions for an authorized department",
                    ),
                    (
                        "export_department_completions",
                        "Can export completions for an authorized department",
                    ),
                    (
                        "submit_bulk_task_completions",
                        "Can submit task completions for any eligible pilot",
                    ),
                    (
                        "submit_department_task_completions",
                        "Can submit task completions for eligible pilots in an authorized department",
                    ),
                ],
            },
        ),
    ]
