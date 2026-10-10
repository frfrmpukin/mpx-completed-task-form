from django.conf import settings
from django.contrib.auth.models import Group
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Task(models.Model):
    class Frequency(models.TextChoices):
        ONE_TIME = "one_time", "One time"
        ONGOING = "ongoing", "Ongoing"

    class LimitScope(models.TextChoices):
        PER_USER = "per_user", "Per pilot"
        SHARED = "shared", "Shared across the task"

    title = models.CharField(max_length=200)
    instructions = models.TextField()
    department_group = models.ForeignKey(
        Group,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="department_task_reports",
    )
    assigned_groups = models.ManyToManyField(
        Group, blank=True, related_name="assigned_task_reports"
    )
    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="assigned_task_reports"
    )
    approver_groups = models.ManyToManyField(
        Group, blank=True, related_name="approvable_task_reports"
    )
    approver_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="approvable_task_reports"
    )
    requires_approval = models.BooleanField(default=False)
    allow_bulk_submissions = models.BooleanField(default=False)
    frequency = models.CharField(
        max_length=12, choices=Frequency.choices, default=Frequency.ONE_TIME
    )
    max_completions = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=(MinValueValidator(1),),
        help_text="Optional lifetime completion cap for this task.",
    )
    limit_scope = models.CharField(
        max_length=12,
        choices=LimitScope.choices,
        default=LimitScope.PER_USER,
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_task_reports",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at", "-pk")
        permissions = [
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
        ]

    def __str__(self):
        return self.title


class TaskCompletion(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending approval"
        APPROVED = "approved", "Approved"
        REVISION_REQUESTED = "revision_requested", "Revision requested"
        DENIED = "denied", "Denied"

    task = models.ForeignKey(
        Task, on_delete=models.PROTECT, related_name="completions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="task_completions",
    )
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_task_reports",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submitted_task_completions",
    )
    completed_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, max_length=2000)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_task_completions",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, max_length=2000)
    submitted_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-completed_at", "-pk")
        indexes = [
            models.Index(fields=("task", "status"), name="task_status_idx"),
            models.Index(fields=("user", "status"), name="user_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(
                    status__in=[
                        "pending",
                        "approved",
                        "revision_requested",
                        "denied",
                    ]
                ),
                name="valid_task_completion_status",
            )
        ]

    def __str__(self):
        return (
            f"{self.task}: {self.character or self.user} "
            f"({self.get_status_display()})"
        )
