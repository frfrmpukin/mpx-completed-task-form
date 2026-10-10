from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Task, TaskCompletion


class TaskForm(forms.ModelForm):
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
            "assigned_groups": "Members of any selected group can report this task.",
            "assigned_users": "Individuals selected here can also report this task.",
            "approver_groups": "Required when approval is enabled.",
            "approver_users": "Required when approval is enabled.",
            "max_completions": (
                "Optional lifetime cap. Leave blank for no completion limit."
            ),
            "limit_scope": (
                "Choose whether the cap applies to each pilot or the task overall."
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
            "notes": "Optional. Add a brief summary of what you completed.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
        choices=ACTIONS, widget=forms.RadioSelect, initial="approve"
    )
    review_notes = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get("action")
        if action in ("revise", "deny") and not cleaned_data.get("review_notes"):
            self.add_error(
                "review_notes",
                "Add a reason when requesting a revision or denying a completion.",
            )
        return cleaned_data
