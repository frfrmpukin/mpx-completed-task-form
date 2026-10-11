import csv

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from allianceauth.eveonline.models import EveCharacter

from .forms import (
    TaskBulkCompletionForm,
    TaskCompletionForm,
    TaskForm,
    TaskReviewForm,
)
from .models import Task, TaskCompletion


def _in_groups(user, groups):
    return user.is_authenticated and groups.filter(
        pk__in=user.groups.values_list("pk", flat=True)
    ).exists()


def _is_assigned(task, user):
    return task.assigned_users.filter(pk=user.pk).exists() or _in_groups(
        user, task.assigned_groups
    )


def _department_groups_with_permission(user, codename):
    return user.groups.filter(
        permissions__content_type__app_label="completed_tasks",
        permissions__codename=codename,
    ).distinct()


def _can_manage_task(user, task):
    return user.has_perm("completed_tasks.add_task") or (
        task.department_group_id is not None
        and _department_groups_with_permission(
            user, "add_department_tasks"
        ).filter(pk=task.department_group_id).exists()
    )


def _can_bulk_submit(user, task):
    return (
        task.allow_bulk_submissions
        and task.frequency == Task.Frequency.ONGOING
        and (
            user.has_perm("completed_tasks.submit_bulk_task_completions")
            or (
                task.department_group_id is not None
                and _department_groups_with_permission(
                    user, "submit_department_task_completions"
                ).filter(pk=task.department_group_id).exists()
            )
        )
    )


def _can_close_task(user, task):
    return (
        task.created_by_id == user.pk
        or _can_manage_task(user, task)
        or _can_bulk_submit(user, task)
    )


def _eligible_users(task):
    user_model = get_user_model()
    users = user_model._default_manager.filter(
        Q(groups__in=task.assigned_groups.all())
        | Q(pk__in=task.assigned_users.values("pk"))
    ).distinct()
    if any(field.name == "is_active" for field in user_model._meta.fields):
        users = users.filter(is_active=True)
    return users


def _eligible_characters(task):
    return EveCharacter.objects.filter(
        character_ownership__user__in=_eligible_users(task)
    ).select_related("character_ownership__user").order_by("character_name")


def _characters_for_user(user):
    return EveCharacter.objects.filter(
        character_ownership__user=user
    ).select_related("character_ownership__user").order_by("character_name")


def _csv_cell(value):
    text = "" if value is None else str(value)
    if text.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return f"'{text}"
    return text


def _can_approve(task, user):
    return (
        user.has_perm("completed_tasks.approve_task_completions")
        or (
            task.department_group_id is not None
            and _department_groups_with_permission(
                user, "approve_department_completions"
            ).filter(pk=task.department_group_id).exists()
        )
        or task.approver_users.filter(pk=user.pk).exists()
        or _in_groups(user, task.approver_groups)
    )


def _completion_limit_reached(task, user, character=None):
    if task.max_completions is None:
        return False
    completions = task.completions.exclude(status=TaskCompletion.Status.DENIED)
    if task.limit_scope == Task.LimitScope.PER_USER:
        if character is not None:
            completions = completions.filter(
                Q(character=character) | Q(character__isnull=True, user=user)
            )
        else:
            characters = _characters_for_user(user)
            if not characters.exists():
                return False
            return all(
                _completion_limit_reached(task, user, pilot_character)
                for pilot_character in characters
            )
    return completions.count() >= task.max_completions


def _bulk_limit_reached(task, characters):
    if task.max_completions is None:
        return False
    if task.limit_scope == Task.LimitScope.SHARED:
        return _completion_limit_reached(task, None)
    return all(
        _completion_limit_reached(
            task,
            character.character_ownership.user,
            character,
        )
        for character in characters
    )


def _task_has_open_one_time_completion(task):
    return (
        task.frequency == Task.Frequency.ONE_TIME
        and task.completions.filter(
            status__in=(
                TaskCompletion.Status.PENDING,
                TaskCompletion.Status.REVISION_REQUESTED,
            )
        ).exists()
    )


def _require_task_access(request, task):
    if not request.user.has_perm("completed_tasks.access_task_reports"):
        raise PermissionDenied
    if not (
        _is_assigned(task, request.user)
        or task.created_by_id == request.user.pk
        or _can_approve(task, request.user)
        or request.user.has_perm("completed_tasks.view_all_completions")
        or _can_bulk_submit(request.user, task)
    ):
        raise PermissionDenied


@login_required
@permission_required("completed_tasks.access_task_reports", raise_exception=True)
def dashboard(request):
    user = request.user
    can_view_all = user.has_perm("completed_tasks.view_all_completions")
    can_manage = user.has_perm("completed_tasks.add_task")
    can_bulk_submit_any = user.has_perm(
        "completed_tasks.submit_bulk_task_completions"
    )
    manageable_departments = _department_groups_with_permission(
        user, "add_department_tasks"
    )
    bulk_departments = _department_groups_with_permission(
        user, "submit_department_task_completions"
    )
    can_approve_any = user.has_perm("completed_tasks.approve_task_completions")
    can_view_departments = _department_groups_with_permission(
        user, "view_department_completions"
    )
    if can_view_all or can_approve_any:
        tasks = (
            Task.objects.filter(is_active=True)
            .select_related("department_group")
            .prefetch_related(
                "assigned_groups",
                "assigned_users",
                "approver_groups",
                "approver_users",
            )
        )
    else:
        task_scope = models_q_for_user(user) | Q(created_by=user)
        if can_bulk_submit_any:
            task_scope |= Q(allow_bulk_submissions=True)
        if manageable_departments.exists():
            task_scope |= Q(department_group__in=manageable_departments)
        if bulk_departments.exists():
            task_scope |= Q(
                department_group__in=bulk_departments,
                allow_bulk_submissions=True,
            )
        if can_view_departments.exists():
            task_scope |= Q(department_group__in=can_view_departments)
        tasks = (
            Task.objects.filter(is_active=True)
            .filter(task_scope)
            .distinct()
            .select_related("department_group")
            .prefetch_related(
                "assigned_groups",
                "assigned_users",
                "approver_groups",
                "approver_users",
            )
        )
    closed_task_scope = Q(created_by=user)
    if can_manage:
        closed_tasks = Task.objects.filter(is_active=False)
    else:
        if manageable_departments.exists():
            closed_task_scope |= Q(department_group__in=manageable_departments)
        closed_tasks = Task.objects.filter(is_active=False).filter(
            closed_task_scope
        )
    closed_tasks = closed_tasks.select_related(
        "department_group", "created_by", "updated_by"
    )
    own_completions = TaskCompletion.objects.filter(user=user).select_related(
        "task", "task__department_group", "reviewer", "character", "submitted_by"
    )[:50]
    pending_reviews = TaskCompletion.objects.filter(
        status=TaskCompletion.Status.PENDING
    ).select_related("task", "user", "character", "submitted_by")
    if not can_approve_any:
        approval_scope = Q(task__approver_users=user) | Q(
            task__approver_groups__in=user.groups.all()
        )
        department_approvers = _department_groups_with_permission(
            user, "approve_department_completions"
        )
        if department_approvers.exists():
            approval_scope |= Q(task__department_group__in=department_approvers)
        pending_reviews = pending_reviews.filter(approval_scope).distinct()
    task_cards = []
    for task in tasks:
        has_open_one_time_completion = _task_has_open_one_time_completion(task)
        if has_open_one_time_completion and not (
            task.created_by_id == user.pk or _can_manage_task(user, task)
        ):
            continue
        assigned = _is_assigned(task, user)
        has_registered_character = _characters_for_user(user).exists()
        limit_reached = _completion_limit_reached(task, user)
        can_submit = (
            assigned
            and has_registered_character
            and not limit_reached
            and not has_open_one_time_completion
        )
        bulk_authorized = _can_bulk_submit(user, task)
        eligible_characters = _eligible_characters(task)
        has_eligible_characters = eligible_characters.exists()
        can_bulk_submit = (
            bulk_authorized
            and has_eligible_characters
            and not _bulk_limit_reached(task, eligible_characters)
        )
        message = ""
        if has_open_one_time_completion:
            can_submit = False
            message = "A completion for this one-time task is awaiting review."
        elif assigned and limit_reached:
            can_submit = False
            message = "The completion limit has been reached."
        elif assigned and not has_registered_character:
            can_submit = False
            message = "Register a character in Alliance Auth before reporting completion."
        elif bulk_authorized and not has_eligible_characters:
            message = "No registered characters belonging to task members are available."
        elif bulk_authorized and not can_bulk_submit:
            message = "The task's completion limit has been reached."
        elif not assigned and not can_bulk_submit:
            message = "You can review or manage this task but are not assigned to complete it."
        task_cards.append(
            {
                "task": task,
                "can_submit": can_submit,
                "can_bulk_submit": can_bulk_submit,
                "can_close": _can_close_task(user, task),
                "can_edit": (
                    task.created_by_id == user.pk or _can_manage_task(user, task)
                ),
                "availability_message": message,
            }
        )
    team_scope = (
        Q(task__created_by=user)
        | Q(task__approver_users=user)
        | Q(task__approver_groups__in=user.groups.all())
    )
    if can_view_all:
        team_completions = TaskCompletion.objects.select_related(
            "task", "task__department_group", "user", "reviewer",
            "character", "submitted_by"
        )[:50]
    else:
        visible_departments = _department_groups_with_permission(
            user, "view_department_completions"
        )
        if visible_departments.exists():
            team_scope |= Q(task__department_group__in=visible_departments)
        team_completions = TaskCompletion.objects.filter(
            team_scope
        ).select_related(
            "task", "task__department_group", "user", "reviewer",
            "character", "submitted_by"
        ).distinct()[:50]

    can_view_department_reports = can_view_all or can_view_departments.exists()
    can_create_tasks = can_manage or manageable_departments.exists()
    can_view_reports = can_view_department_reports
    return render(
        request,
        "completed_tasks/dashboard.html",
        {
            "task_cards": task_cards,
            "closed_tasks": closed_tasks,
            "own_completions": own_completions,
            "pending_reviews": pending_reviews,
            "team_completions": team_completions,
            "can_create_tasks": can_create_tasks,
            "can_view_all": can_view_all,
            "can_view_reports": can_view_reports,
            "user": user,
        },
    )


def models_q_for_user(user):
    return (
        Q(assigned_users=user)
        | Q(assigned_groups__in=user.groups.all())
        | Q(approver_users=user)
        | Q(approver_groups__in=user.groups.all())
    )


@login_required
@permission_required("completed_tasks.access_task_reports", raise_exception=True)
def create_task(request):
    can_manage_all = request.user.has_perm("completed_tasks.add_task")
    if can_manage_all:
        department_queryset = Group.objects.order_by("name")
    else:
        department_queryset = _department_groups_with_permission(
            request.user, "add_department_tasks"
        ).order_by("name")
        if not department_queryset.exists():
            raise PermissionDenied
    form = TaskForm(
        request.POST or None,
        department_queryset=department_queryset,
    )
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.created_by = request.user
        task.save()
        form.save_m2m()
        messages.success(request, "Task created.")
        return redirect("completed_tasks:dashboard")
    return render(
        request,
        "completed_tasks/create_task.html",
        {"form": form, "is_editing": False},
    )


@login_required
@permission_required("completed_tasks.access_task_reports", raise_exception=True)
def edit_task(request, task_id):
    task = get_object_or_404(Task.objects.select_related("department_group"), pk=task_id)
    if task.created_by_id != request.user.pk and not _can_manage_task(
        request.user, task
    ):
        raise PermissionDenied

    if request.method == "POST":
        with transaction.atomic():
            task = get_object_or_404(
                Task.objects.select_for_update().select_related(
                    "department_group"
                ),
                pk=task_id,
            )
            can_manage_workflow = _can_manage_task(request.user, task)
            if task.created_by_id != request.user.pk and not can_manage_workflow:
                raise PermissionDenied
            has_completions = task.completions.exists()
            workflow_locked = has_completions or not can_manage_workflow
            if can_manage_workflow:
                if request.user.has_perm("completed_tasks.add_task"):
                    department_queryset = Group.objects.order_by("name")
                else:
                    department_queryset = _department_groups_with_permission(
                        request.user, "add_department_tasks"
                    ).order_by("name")
            else:
                department_queryset = Group.objects.filter(
                    pk=task.department_group_id
                )
            form = TaskForm(
                request.POST,
                instance=task,
                department_queryset=department_queryset,
                workflow_locked=workflow_locked,
            )
            if form.is_valid():
                task = form.save(commit=False)
                task.updated_by = request.user
                task.save()
                form.save_m2m()
                messages.success(
                    request,
                    "Task updated. Existing completion reports remain unchanged.",
                )
                return redirect("completed_tasks:dashboard")
    else:
        can_manage_workflow = _can_manage_task(request.user, task)
        has_completions = task.completions.exists()
        workflow_locked = has_completions or not can_manage_workflow
        if can_manage_workflow:
            if request.user.has_perm("completed_tasks.add_task"):
                department_queryset = Group.objects.order_by("name")
            else:
                department_queryset = _department_groups_with_permission(
                    request.user, "add_department_tasks"
                ).order_by("name")
        else:
            department_queryset = Group.objects.filter(
                pk=task.department_group_id
            )
        form = TaskForm(
            instance=task,
            department_queryset=department_queryset,
            workflow_locked=workflow_locked,
        )

    if has_completions:
        workflow_lock_reason = (
            "This task already has completion reports. Title and instructions "
            "remain editable, but assignment, approval, frequency, limit, and "
            "bulk-submission settings are locked to preserve the task's workflow."
        )
    elif not can_manage_workflow:
        workflow_lock_reason = (
            "You created this task but no longer have department task-management "
            "permission. You can edit its title and instructions only."
        )
    else:
        workflow_lock_reason = ""
    return render(
        request,
        "completed_tasks/create_task.html",
        {
            "form": form,
            "is_editing": True,
            "task": task,
            "workflow_locked": workflow_locked,
            "workflow_lock_reason": workflow_lock_reason,
        },
    )


@login_required
@permission_required("completed_tasks.access_task_reports", raise_exception=True)
def submit_completion(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    _require_task_access(request, task)
    if not task.is_active or not _is_assigned(task, request.user):
        raise PermissionDenied

    character_queryset = _characters_for_user(request.user)
    form = TaskCompletionForm(
        request.POST or None,
        character_queryset=character_queryset,
    )
    if not character_queryset.exists():
        form.add_error(
            None,
            "No Alliance Auth-registered characters are linked to your account.",
        )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked_task = Task.objects.select_for_update().get(pk=task.pk)
            if not locked_task.is_active:
                form.add_error(None, "This task is no longer active.")
            elif _completion_limit_reached(
                locked_task,
                request.user,
                form.cleaned_data["character"],
            ):
                form.add_error(None, "The completion limit for this task was reached.")
            elif _task_has_open_one_time_completion(locked_task):
                form.add_error(
                    None,
                    "A completion for this one-time task is already awaiting review.",
                )
            else:
                completion = form.save(commit=False)
                completion.task = locked_task
                completion.user = request.user
                completion.submitted_by = request.user
                completion.status = (
                    TaskCompletion.Status.PENDING
                    if locked_task.requires_approval
                    else TaskCompletion.Status.APPROVED
                )
                completion.save()
                if (
                    locked_task.frequency == Task.Frequency.ONE_TIME
                    and not locked_task.requires_approval
                ):
                    locked_task.is_active = False
                    locked_task.save(update_fields=("is_active",))
                if locked_task.requires_approval:
                    messages.success(
                        request,
                        "Completion submitted and is awaiting approval.",
                    )
                else:
                    messages.success(request, "Task completion reported.")
                return redirect("completed_tasks:dashboard")
    return render(
        request,
        "completed_tasks/submit_completion.html",
        {"form": form, "task": task},
    )


@login_required
@permission_required("completed_tasks.access_task_reports", raise_exception=True)
def bulk_submit_completions(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    if not _can_bulk_submit(request.user, task):
        raise PermissionDenied
    if not task.is_active:
        raise PermissionDenied

    character_queryset = _eligible_characters(task)
    form = TaskBulkCompletionForm(
        request.POST or None,
        character_queryset=character_queryset,
    )
    if not character_queryset.exists():
        form.add_error(
            None,
            "No registered characters belong to members assigned to this task.",
        )
    if request.method == "POST" and form.is_valid():
        selected_characters = list(form.cleaned_data["characters"])
        with transaction.atomic():
            locked_task = Task.objects.select_for_update().get(pk=task.pk)
            if not locked_task.is_active or not _can_bulk_submit(
                request.user, locked_task
            ):
                form.add_error(None, "Bulk reporting is no longer available.")
            elif locked_task.frequency != Task.Frequency.ONGOING:
                form.add_error(
                    None,
                    "Bulk completion reports require an ongoing task.",
                )
            elif set(
                _eligible_characters(locked_task)
                .filter(pk__in=[character.pk for character in selected_characters])
                .values_list("pk", flat=True)
            ) != {character.pk for character in selected_characters}:
                form.add_error(
                    None,
                    "One or more selected characters are no longer eligible for this task.",
                )
            elif locked_task.max_completions is not None and (
                locked_task.limit_scope == Task.LimitScope.SHARED
                and _completion_limit_reached(locked_task, request.user)
            ):
                form.add_error(None, "The shared completion limit was reached.")
            elif locked_task.max_completions is not None and (
                locked_task.limit_scope == Task.LimitScope.SHARED
                and locked_task.completions.exclude(
                    status=TaskCompletion.Status.DENIED
                ).count()
                + len(selected_characters)
                > locked_task.max_completions
            ):
                form.add_error(
                    None,
                    "There are not enough remaining shared completion slots "
                    "for all selected characters.",
                )
            elif locked_task.max_completions is not None and any(
                _completion_limit_reached(
                    locked_task,
                    character.character_ownership.user,
                    character,
                )
                for character in selected_characters
            ):
                form.add_error(
                    None,
                    "At least one selected character has reached its completion limit.",
                )
            else:
                status = (
                    TaskCompletion.Status.PENDING
                    if locked_task.requires_approval
                    else TaskCompletion.Status.APPROVED
                )
                for character in selected_characters:
                    TaskCompletion.objects.create(
                        task=locked_task,
                        user=character.character_ownership.user,
                        character=character,
                        submitted_by=request.user,
                        completed_at=form.cleaned_data["completed_at"],
                        notes=form.cleaned_data["notes"],
                        status=status,
                    )
                messages.success(
                    request,
                    f"Submitted {len(selected_characters)} individual "
                    "character completion report(s).",
                )
                return redirect("completed_tasks:dashboard")
    return render(
        request,
        "completed_tasks/bulk_submit_completions.html",
        {"form": form, "task": task},
    )


@login_required
@permission_required("completed_tasks.access_task_reports", raise_exception=True)
def close_task(request, task_id):
    if request.method != "POST":
        raise Http404
    with transaction.atomic():
        task = get_object_or_404(
            Task.objects.select_for_update(),
            pk=task_id,
        )
        if not _can_close_task(request.user, task):
            raise PermissionDenied
        if task.is_active:
            task.is_active = False
            task.save(update_fields=("is_active",))
            messages.success(
                request,
                "Task closed. Existing reports remain available.",
            )
    return redirect("completed_tasks:dashboard")


@login_required
@permission_required("completed_tasks.access_task_reports", raise_exception=True)
def revise_completion(request, completion_id):
    completion = get_object_or_404(
        TaskCompletion.objects.select_related("task", "character"), pk=completion_id
    )
    if completion.user_id != request.user.pk:
        raise PermissionDenied
    if completion.status != TaskCompletion.Status.REVISION_REQUESTED:
        raise Http404("This completion is not awaiting revision.")
    form = TaskCompletionForm(
        request.POST or None,
        instance=completion,
        character_queryset=_characters_for_user(request.user),
    )
    if completion.character_id:
        form.fields.pop("character")
    if request.method == "POST" and form.is_valid():
        completion = form.save(commit=False)
        completion.status = TaskCompletion.Status.PENDING
        completion.review_notes = ""
        completion.reviewer = None
        completion.reviewed_at = None
        completion.save()
        messages.success(request, "Your revised completion was resubmitted.")
        return redirect("completed_tasks:dashboard")
    return render(
        request,
        "completed_tasks/revise_completion.html",
        {"completion": completion, "form": form},
    )


@login_required
@permission_required("completed_tasks.access_task_reports", raise_exception=True)
def review_completion(request, completion_id):
    completion = get_object_or_404(
        TaskCompletion.objects.select_related(
            "task", "user", "submitted_by", "character"
        ),
        pk=completion_id,
    )
    if (
        request.user.pk in (completion.user_id, completion.submitted_by_id)
        or not _can_approve(completion.task, request.user)
    ):
        raise PermissionDenied
    if not completion.task.requires_approval:
        raise Http404("This task does not require approval.")
    if completion.status != TaskCompletion.Status.PENDING:
        raise Http404("This completion is not awaiting review.")

    form = TaskReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        action = form.cleaned_data["action"]
        with transaction.atomic():
            completion = TaskCompletion.objects.select_for_update().select_related(
                "task"
            ).get(pk=completion.pk)
            if completion.status != TaskCompletion.Status.PENDING:
                raise Http404("This completion has already been reviewed.")
            completion.review_notes = form.cleaned_data["review_notes"]
            completion.reviewer = request.user
            completion.reviewed_at = timezone.now()
            if action == "approve":
                completion.status = TaskCompletion.Status.APPROVED
                if completion.task.frequency == Task.Frequency.ONE_TIME:
                    completion.task.is_active = False
                    completion.task.save(update_fields=("is_active",))
                messages.success(request, "Completion approved.")
            elif action == "revise":
                completion.status = TaskCompletion.Status.REVISION_REQUESTED
                messages.success(request, "Revision requested.")
            else:
                completion.status = TaskCompletion.Status.DENIED
                messages.success(request, "Completion denied permanently.")
            completion.save(
                update_fields=(
                    "status",
                    "review_notes",
                    "reviewer",
                    "reviewed_at",
                    "updated_at",
                )
            )
        return redirect("completed_tasks:dashboard")
    return render(
        request,
        "completed_tasks/review_completion.html",
        {"completion": completion, "form": form},
    )


@login_required
@permission_required("completed_tasks.access_task_reports", raise_exception=True)
def all_completions(request):
    user = request.user
    can_view_all = user.has_perm("completed_tasks.view_all_completions")
    visible_departments = _department_groups_with_permission(
        user, "view_department_completions"
    )
    if not can_view_all and not visible_departments.exists():
        raise PermissionDenied

    departments = (
        Group.objects.order_by("name")
        if can_view_all
        else visible_departments.order_by("name")
    )
    completions = TaskCompletion.objects.select_related(
        "task", "task__department_group", "user", "reviewer",
        "character", "submitted_by"
    )
    if not can_view_all:
        completions = completions.filter(task__department_group__in=visible_departments)

    selected_department = request.GET.get("department", "")
    if selected_department:
        try:
            department_id = int(selected_department)
        except ValueError as error:
            raise Http404("Department not found.") from error
        if not departments.filter(pk=department_id).exists():
            raise Http404("Department not found.")
        completions = completions.filter(task__department_group_id=department_id)
    selected_status = request.GET.get("status", "")
    if selected_status:
        if selected_status not in TaskCompletion.Status.values:
            raise Http404("Invalid completion status.")
        completions = completions.filter(status=selected_status)
    search = request.GET.get("q", "").strip()
    if search:
        completions = completions.filter(
            Q(task__title__icontains=search)
            | Q(user__username__icontains=search)
            | Q(character__character_name__icontains=search)
            | Q(notes__icontains=search)
        )
    can_export_all = user.has_perm("completed_tasks.export_all_completions")
    export_departments = _department_groups_with_permission(
        user, "export_department_completions"
    )
    export_url = reverse("completed_tasks:export_completions")
    if request.GET:
        export_url = f"{export_url}?{request.GET.urlencode()}"
    can_export = can_export_all or (
        bool(selected_department)
        and export_departments.filter(pk=selected_department).exists()
    )
    return render(
        request,
        "completed_tasks/all_completions.html",
        {
            "completions": completions.order_by("-completed_at"),
            "departments": departments,
            "selected_department": selected_department,
            "selected_status": selected_status,
            "status_choices": TaskCompletion.Status.choices,
            "search": search,
            "can_export": can_export,
            "export_url": export_url,
        },
    )


@login_required
@permission_required("completed_tasks.access_task_reports", raise_exception=True)
def export_completions(request):
    user = request.user
    can_export_all = user.has_perm("completed_tasks.export_all_completions")
    export_departments = _department_groups_with_permission(
        user, "export_department_completions"
    )
    if not can_export_all and not export_departments.exists():
        raise PermissionDenied

    completions = TaskCompletion.objects.select_related(
        "task", "task__department_group", "user", "reviewer",
        "character", "submitted_by"
    )
    if not can_export_all:
        completions = completions.filter(
            task__department_group__in=export_departments
        )

    selected_department = request.GET.get("department", "")
    if selected_department:
        try:
            department_id = int(selected_department)
        except ValueError as error:
            raise Http404("Department not found.") from error
        allowed_departments = (
            Group.objects.all() if can_export_all else export_departments
        )
        if not allowed_departments.filter(pk=department_id).exists():
            raise Http404("Department not found.")
        completions = completions.filter(task__department_group_id=department_id)
    selected_status = request.GET.get("status", "")
    if selected_status:
        if selected_status not in TaskCompletion.Status.values:
            raise Http404("Invalid completion status.")
        completions = completions.filter(status=selected_status)
    search = request.GET.get("q", "").strip()
    if search:
        completions = completions.filter(
            Q(task__title__icontains=search)
            | Q(user__username__icontains=search)
            | Q(character__character_name__icontains=search)
            | Q(notes__icontains=search)
        )

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="task-completions.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(
        (
            "Department",
            "Task",
            "Pilot",
            "Submitted by",
            "Completed at",
            "Status",
            "Notes",
            "Reviewer",
            "Reviewed at",
            "Review notes",
        )
    )
    for completion in completions.order_by("-completed_at").iterator():
        writer.writerow(
            (
                _csv_cell(completion.task.department_group.name)
                if completion.task.department_group
                else "",
                _csv_cell(completion.task.title),
                _csv_cell(
                    completion.character.character_name
                    if completion.character
                    else completion.user.get_username()
                ),
                _csv_cell(completion.submitted_by.get_username())
                if completion.submitted_by
                else "",
                completion.completed_at.isoformat(),
                completion.get_status_display(),
                _csv_cell(completion.notes),
                _csv_cell(completion.reviewer.get_username())
                if completion.reviewer
                else "",
                completion.reviewed_at.isoformat() if completion.reviewed_at else "",
                _csv_cell(completion.review_notes),
            )
        )
    return response
