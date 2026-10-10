from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Task, TaskCompletion


class TaskForm(forms.ModelForm):
    REQUIREMENT_LABELS = {
        "title": ("Required", "required"),
        "instructions": ("Required", "required"),
        "department_group": ("Required", "required"),
        "assigned_groups": ("Optional", "optional"),
        "assigned_users": ("Optional", "optional"),
        "requires_approval": ("Optional", "optional"),
        "approver_groups": ("Conditional", "conditional"),
        "approver_users": ("Conditional", "conditional"),
        "frequency": ("Required", "required"),
        "max_completions": ("Optional", "optional"),
        "limit_scope": ("Optional", "optional"),
    }

    class Meta:
        model = Task
        fields = (
            "title",
            "instructions",
            "department_group",
            "assigned_groups",
            "assigned_users",
            "requires_approval",
            "approver_groups",
            "approver_users",
            "frequency",
            "max_completions",
            "limit_scope",
        )
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "instructions": forms.Textarea(
                attrs={"rows": 4, "class": "form-control"}
            ),
            "department_group": forms.Select(attrs={"class": "form-select"}),
            "assigned_groups": forms.SelectMultiple(attrs={"class": "form-select"}),
            "assigned_users": forms.SelectMultiple(attrs={"class": "form-select"}),
            "approver_groups": forms.SelectMultiple(attrs={"class": "form-select"}),
            "approver_users": forms.SelectMultiple(attrs={"class": "form-select"}),
            "requires_approval": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "frequency": forms.Select(attrs={"class": "form-select"}),
            "max_completions": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
            "limit_scope": forms.Select(attrs={"class": "form-select"}),
        }
        help_texts = {
            "title": "Required. Short name shown in the task list, completion history, and reports.",
            "instructions": (
                "Required. Explain what members need to do and what to include "
                "in their completion notes. Detailed data can remain in the "
                "existing game or scanning module."
            ),
            "department_group": (
                "Required. Sets the department that owns this task and controls "
                "department-scoped task management, approvals, reports, and exports."
            ),
            "assigned_groups": (
                "Optional if you select individuals below; otherwise select at "
                "least one group. Members of any selected group can report this task."
            ),
            "assigned_users": (
                "Optional if you select a group above; otherwise select at least "
                "one individual. Selected people can report this task in addition "
                "to members of the selected groups."
            ),
            "requires_approval": (
                "Optional. If checked, each submission waits for an assigned "
                "approver. If unchecked, it is recorded as approved immediately."
            ),
            "approver_groups": (
                "Required when approval is enabled. Members of any selected "
                "group can review this task's pending submissions."
            ),
            "approver_users": (
                "Required when approval is enabled. Selected people can review "
                "this task's pending submissions in addition to approver groups."
            ),
            "frequency": (
                "Required. One-time tasks close after an accepted completion "
                "(or after submission if approval is off). Ongoing tasks stay "
                "available for multiple completion reports."
            ),
            "max_completions": (
                "Optional; ongoing tasks only. Sets a lifetime total, not a "
                "daily or weekly limit. Pending, revision-requested, and "
                "approved submissions count; permanently denied submissions do "
                "not. Leave blank for no cap."
            ),
            "limit_scope": (
                "Only affects the task when a completion limit is set. Per pilot "
                "gives each person their own cap; shared applies one total across "
                "all eligible pilots."
            ),
        }

    def __init__(self, *args, department_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        user_model = get_user_model()
        self.fields["department_group"].queryset = (
            department_queryset
            if department_queryset is not None
            else Group.objects.order_by("name")
        )
        self.fields["department_group"].required = True
        self.fields["assigned_groups"].queryset = Group.objects.order_by("name")
        self.fields["approver_groups"].queryset = Group.objects.order_by("name")
        user_queryset = user_model._default_manager.all()
        if any(field.name == "is_active" for field in user_model._meta.fields):
            user_queryset = user_queryset.filter(is_active=True)
        self.fields["assigned_users"].queryset = user_queryset.order_by(
            user_model.USERNAME_FIELD
        )
        self.fields["approver_users"].queryset = (
            user_queryset.order_by(user_model.USERNAME_FIELD)
        )
        self._set_requirement_labels()

    def _set_requirement_labels(self):
        for name, (label, style) in self.REQUIREMENT_LABELS.items():
            self.fields[name].widget.attrs["data-requirement-label"] = label
            self.fields[name].widget.attrs["data-requirement-style"] = style

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("assigned_groups") and not cleaned_data.get(
            "assigned_users"
        ):
            raise ValidationError(
                "Assign this task to at least one group or individual."
            )
        if cleaned_data.get("requires_approval") and not (
            cleaned_data.get("approver_groups")
            or cleaned_data.get("approver_users")
        ):
            raise ValidationError(
                "Choose at least one approver group or individual."
            )
        if cleaned_data.get("max_completions") and cleaned_data.get(
            "frequency"
        ) != Task.Frequency.ONGOING:
            self.add_error(
                "max_completions",
                "Completion limits can only be set for ongoing tasks.",
            )
        if cleaned_data.get("max_completions") is None:
            cleaned_data["limit_scope"] = Task.LimitScope.PER_USER
        return cleaned_data


class TaskCompletionForm(forms.ModelForm):
    REQUIREMENT_LABELS = {
        "completed_at": ("Required", "required"),
        "notes": ("Optional", "optional"),
    }

    class Meta:
        model = TaskCompletion
        fields = ("completed_at", "notes")
        widgets = {
            "completed_at": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"},
                format="%Y-%m-%dT%H:%M",
            ),
            "notes": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        }
        help_texts = {
            "completed_at": (
                "Required. Defaults to the current local date and time; adjust "
                "it if you are reporting work completed earlier."
            ),
            "notes": (
                "Optional, up to 2,000 characters. Summarize what you completed "
                "and include useful details such as the systems visited. This "
                "appears in your history and authorized reports."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, (label, style) in self.REQUIREMENT_LABELS.items():
            self.fields[name].widget.attrs["data-requirement-label"] = label
            self.fields[name].widget.attrs["data-requirement-style"] = style
        self.fields["completed_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        if not self.is_bound and not self.instance.pk:
            self.fields["completed_at"].initial = timezone.localtime().strftime(
                "%Y-%m-%dT%H:%M"
            )


class TaskReviewForm(forms.Form):
    ACTIONS = (
        ("approve", "Approve"),
        ("revise", "Request revision"),
        ("deny", "Deny permanently"),
    )
    action = forms.ChoiceField(
        choices=ACTIONS,
        widget=forms.RadioSelect,
        initial="approve",
        help_text=(
            "Approve accepts the completion in the task report. Request "
            "revision returns it to the pilot for an update and resubmission. "
            "Deny permanently closes this submission without resubmission."
        ),
    )
    review_notes = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        help_text=(
            "Required for a revision request or permanent denial; optional for "
            "approval. The pilot can see this feedback."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        requirement_labels = {
            "action": ("Required", "required"),
            "review_notes": ("Conditional", "conditional"),
        }
        for name, (label, style) in requirement_labels.items():
            self.fields[name].widget.attrs["data-requirement-label"] = label
            self.fields[name].widget.attrs["data-requirement-style"] = style

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get("action")
        if action in ("revise", "deny") and not cleaned_data.get("review_notes"):
            self.add_error(
                "review_notes",
                "Add a reason when requesting a revision or denying a completion.",
            )
        return cleaned_data
