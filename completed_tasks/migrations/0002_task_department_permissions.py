from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("completed_tasks", "0001_initial"),
    ]

    operations = [
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
                ],
            },
        )
    ]
