import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="Task",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                ("instructions", models.TextField()),
                (
                    "requires_approval",
                    models.BooleanField(default=False),
                ),
                (
                    "frequency",
                    models.CharField(
                        choices=[
                            ("one_time", "One time"),
                            ("ongoing", "Ongoing"),
                        ],
                        default="one_time",
                        max_length=12,
                    ),
                ),
                (
                    "max_completions",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Optional lifetime completion cap for this task.",
                        null=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "limit_scope",
                    models.CharField(
                        choices=[
                            ("per_user", "Per pilot"),
                            ("shared", "Shared across the task"),
                        ],
                        default="per_user",
                        max_length=12,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "assigned_groups",
                    models.ManyToManyField(
                        blank=True,
                        related_name="assigned_task_reports",
                        to="auth.group",
                    ),
                ),
                (
                    "assigned_users",
                    models.ManyToManyField(
                        blank=True,
                        related_name="assigned_task_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "approver_groups",
                    models.ManyToManyField(
                        blank=True,
                        related_name="approvable_task_reports",
                        to="auth.group",
                    ),
                ),
                (
                    "approver_users",
                    models.ManyToManyField(
                        blank=True,
                        related_name="approvable_task_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "department_group",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="department_task_reports",
                        to="auth.group",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_task_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "-pk"),
                "permissions": [
                    ("access_task_reports", "Can access task reports"),
                    ("view_all_completions", "Can view all task completions"),
                    (
                        "approve_task_completions",
                        "Can approve any task completion",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="TaskCompletion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("completed_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("notes", models.TextField(blank=True, max_length=2000)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending approval"),
                            ("approved", "Approved"),
                            ("revision_requested", "Revision requested"),
                            ("denied", "Denied"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "reviewed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "review_notes",
                    models.TextField(blank=True, max_length=2000),
                ),
                ("submitted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "reviewer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_task_completions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="completions",
                        to="completed_tasks.task",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="task_completions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-completed_at", "-pk"),
                "indexes": [
                    models.Index(
                        fields=["task", "status"], name="task_status_idx"
                    ),
                    models.Index(
                        fields=["user", "status"], name="user_status_idx"
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        check=models.Q(
                            status__in=[
                                "pending",
                                "approved",
                                "revision_requested",
                                "denied",
                            ]
                        ),
                        name="valid_task_completion_status",
                    )
                ],
            },
        ),
    ]
