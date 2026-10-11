from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils import timezone

from allianceauth.eveonline.models import EveCharacter

from .models import Task, TaskCompletion


COMPLETION_EXPORT_COLUMNS = (
    ("department", "Department"),
    ("task", "Task"),
    ("pap_value", "PAP(s)"),
    ("pilot", "Pilot"),
    ("submitted_by", "Submitted by"),
    ("completed_at", "Completed at"),
    ("status", "Status"),
    ("notes", "Notes"),
    ("reviewer", "Reviewer"),
    ("reviewed_at", "Reviewed at"),
    ("review_notes", "Review notes"),
)


class CharacterChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.character_name} — {obj.character_ownership.user}"


class CharacterMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.character_name} — {obj.character_ownership.user}"


class CompletionReportFilterForm(forms.Form):
    date_from = forms.DateField(
        required=False,
        label="Completed from",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    date_to = forms.DateField(
        required=False,
        label="Completed through",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    columns = forms.MultipleChoiceField(
        choices=COMPLETION_EXPORT_COLUMNS,
        initial=[value for value, _ in COMPLETION_EXPORT_COLUMNS],
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        error_messages={"required": "Select at least one CSV column to export."},
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error(
                "date_to", "The end date must be on or after the start date."
            )
        return cleaned_data


class TaskForm(forms.ModelForm):
    WORKFLOW_FIELDS = (
        "pap_value",
        "department_group",
        "assigned_groups",
        "assigned_users",
        "requires_approval",
        "allow_bulk_submissions",
        "approver_groups",
        "approver_users",
        "frequency",
        "max_completions",
        "limit_scope",
    )
    REQUIREMENT_LABELS = {
        "title": ("Required", "required"),
        "instructions": ("Required", "required"),
        "pap_value": ("Required", "required"),
        "department_group": ("Required", "required"),
        "assigned_groups": ("Optional", "optional"),
        "assigned_users": ("Optional", "optional"),
        "requires_approval": ("Optional", "optional"),
        "allow_bulk_submissions": ("Optional", "optional"),
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
            "pap_value",
            "department_group",
            "assigned_groups",
            "assigned_users",
            "requires_approval",
            "allow_bulk_submissions",
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
            "pap_value": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "step": 1}
            ),
            "department_group": forms.Select(attrs={"class": "form-select"}),
            "assigned_groups": forms.SelectMultiple(attrs={"class": "form-select"}),
            "assigned_users": forms.SelectMultiple(attrs={"class": "form-select"}),
            "approver_groups": forms.SelectMultiple(attrs={"class": "form-select"}),
            "approver_users": forms.SelectMultiple(attrs={"class": "form-select"}),
            "requires_approval": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "allow_bulk_submissions": forms.CheckboxInput(
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
            "pap_value": (
                "Required; defaults to 1 PAP per accepted completion. Set the "
                "value with the task's expected duration in mind: work under "
                "2 hours is typically 1 PAP, with 1 additional PAP for each "
                "additional 2-hour block. Pilots do not enter time, and this "
                "value is not calculated automatically."
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
            "allow_bulk_submissions": (
                "Optional. Allows users with the separate department or global "
                "bulk-submission permission to report completions for multiple "
                "registered characters assigned to this task. This requires an "
                "ongoing task; each selected character receives an individual "
                "completion record."
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
                "gives each registered character its own cap; shared applies one "
                "total across all eligible characters."
            ),
        }

    def __init__(
        self,
        *args,
        department_queryset=None,
        workflow_locked=False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.workflow_locked = workflow_locked
        user_model = get_user_model()
        self.fields["department_group"].queryset = (
            department_queryset
            if department_queryset is not None
            else Group.objects.order_by("name")
        )
        self.fields["department_group"].required = True
        if workflow_locked and self.instance.department_group_id is None:
            self.fields["department_group"].required = False
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
        if workflow_locked:
            for field_name in self.WORKFLOW_FIELDS:
                self.fields[field_name].disabled = True
        self._set_requirement_labels()
        self.sections = (
            {
                "title": "1. Task details",
                "description": (
                    "Name the work and explain what a member should do. Choose "
                    "the department that owns this task; this affects department "
                    "permissions and reporting."
                ),
                "fields": (
                    self["title"],
                    self["instructions"],
                    self["pap_value"],
                    self["department_group"],
                ),
            },
            {
                "title": "2. Who can complete this task?",
                "description": (
                    "Selected groups and individuals are combined: anyone in a "
                    "selected group or any selected individual can submit a "
                    "completion. At least one group or individual is required. "
                    "You can also enable permission-controlled bulk reporting "
                    "for this task."
                ),
                "fields": (
                    self["assigned_groups"],
                    self["assigned_users"],
                    self["allow_bulk_submissions"],
                ),
            },
            {
                "title": "3. Completion approval",
                "description": (
                    "Choose whether a submission is accepted immediately or "
                    "waits for review. If approval is enabled, at least one "
                    "approver group or individual is required."
                ),
                "fields": (
                    self["requires_approval"],
                    self["approver_groups"],
                    self["approver_users"],
                ),
            },
            {
                "title": "4. Repeat submissions and limits",
                "description": (
                    "Choose whether this is a one-time task or remains available "
                    "for repeated reports. An optional completion cap is a "
                    "lifetime total; it does not reset on a schedule."
                ),
                "fields": (
                    self["frequency"],
                    self["max_completions"],
                    self["limit_scope"],
                ),
            },
        )

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
        if cleaned_data.get("allow_bulk_submissions") and cleaned_data.get(
            "frequency"
        ) != Task.Frequency.ONGOING:
            self.add_error(
                "allow_bulk_submissions",
                "Bulk submissions can only be enabled for ongoing tasks.",
            )
        if cleaned_data.get("max_completions") is None:
            cleaned_data["limit_scope"] = Task.LimitScope.PER_USER
        return cleaned_data


class TaskCompletionForm(forms.ModelForm):
    REQUIREMENT_LABELS = {
        "character": ("Required", "required"),
        "completed_at": ("Required", "required"),
        "notes": ("Optional", "optional"),
    }

    class Meta:
        model = TaskCompletion
        fields = ("character", "completed_at", "notes")
        widgets = {
            "character": forms.Select(attrs={"class": "form-select"}),
            "completed_at": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"},
                format="%Y-%m-%dT%H:%M",
            ),
            "notes": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        }
        help_texts = {
            "character": (
                "Required. Select the registered character receiving this "
                "completion credit."
            ),
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

    def __init__(self, *args, character_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["character"] = CharacterChoiceField(
            queryset=(
                character_queryset
                if character_queryset is not None
                else EveCharacter.objects.none()
            ),
            required=True,
            widget=forms.Select(attrs={"class": "form-select"}),
            help_text=self.Meta.help_texts["character"],
        )
        for name, (label, style) in self.REQUIREMENT_LABELS.items():
            self.fields[name].widget.attrs["data-requirement-label"] = label
            self.fields[name].widget.attrs["data-requirement-style"] = style
        self.fields["completed_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        if not self.is_bound and not self.instance.pk:
            self.fields["completed_at"].initial = timezone.localtime().strftime(
                "%Y-%m-%dT%H:%M"
            )


class TaskBulkCompletionForm(forms.Form):
    characters = CharacterMultipleChoiceField(
        queryset=EveCharacter.objects.none(),
        required=True,
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": 10}),
        help_text=(
            "Choose every registered character that participated. The list is "
            "limited to characters owned by members assigned to this task. "
            "Use Ctrl-click (Windows/Linux) or Command-click (Mac) to select "
            "multiple characters."
        ),
    )
    completed_at = forms.DateTimeField(
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"},
            format="%Y-%m-%dT%H:%M",
        ),
        help_text=(
            "Required. Defaults to the current local date and time; adjust it "
            "if the work was completed earlier."
        ),
    )
    notes = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        help_text=(
            "Optional, up to 2,000 characters. These notes are copied to each "
            "selected character's individual completion record."
        ),
    )

    REQUIREMENT_LABELS = {
        "characters": ("Required", "required"),
        "completed_at": ("Required", "required"),
        "notes": ("Optional", "optional"),
    }

    def __init__(self, *args, character_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if character_queryset is not None:
            self.fields["characters"].queryset = character_queryset
        if not self.is_bound:
            self.fields["completed_at"].initial = timezone.localtime().strftime(
                "%Y-%m-%dT%H:%M"
            )
        for name, (label, style) in self.REQUIREMENT_LABELS.items():
            self.fields[name].widget.attrs["data-requirement-label"] = label
            self.fields[name].widget.attrs["data-requirement-style"] = style


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
