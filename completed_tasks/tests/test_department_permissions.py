from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import RequestFactory, TestCase
from django.urls import reverse

from completed_tasks.forms import (
    TaskBulkCompletionForm,
    TaskCompletionForm,
    TaskForm,
)
from completed_tasks.models import Task, TaskCompletion
from completed_tasks.views import (
    _can_approve,
    _can_bulk_submit,
    _can_close_task,
    _can_manage_task,
    _department_groups_with_permission,
    export_completions,
)


class DepartmentPermissionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(
            username="department-member",
            password="test-password",
        )
        cls.department = Group.objects.create(name="Department A")
        cls.other_department = Group.objects.create(name="Department B")
        permissions = Permission.objects.filter(
            content_type__app_label="completed_tasks",
            codename__in=(
                "access_task_reports",
                "add_department_tasks",
                "approve_department_completions",
                "export_department_completions",
                "submit_department_task_completions",
            ),
        )
        cls.department.permissions.add(*permissions)
        cls.user.groups.add(cls.department)
        cls.task = Task.objects.create(
            title="Department task",
            instructions="Report the completion.",
            department_group=cls.department,
        )
        cls.other_task = Task.objects.create(
            title="Other department task",
            instructions="Report the completion.",
            department_group=cls.other_department,
        )

    def test_department_permissions_are_scoped_to_membership_group(self):
        self.assertQuerySetEqual(
            _department_groups_with_permission(self.user, "add_department_tasks"),
            [self.department],
        )
        self.assertTrue(_can_manage_task(self.user, self.task))
        self.assertFalse(_can_manage_task(self.user, self.other_task))
        self.assertTrue(_can_approve(self.task, self.user))
        self.assertFalse(_can_approve(self.other_task, self.user))

    def test_bulk_submission_permission_is_scoped_to_enabled_department_task(self):
        self.task.allow_bulk_submissions = True
        self.task.frequency = Task.Frequency.ONGOING
        self.task.save(update_fields=("allow_bulk_submissions", "frequency"))
        self.other_task.allow_bulk_submissions = True
        self.other_task.frequency = Task.Frequency.ONGOING
        self.other_task.save(update_fields=("allow_bulk_submissions", "frequency"))

        self.assertTrue(_can_bulk_submit(self.user, self.task))
        self.assertFalse(_can_bulk_submit(self.user, self.other_task))
        self.assertTrue(_can_close_task(self.user, self.task))
        self.assertFalse(_can_close_task(self.user, self.other_task))

    def test_task_form_only_offers_authorized_department(self):
        allowed_departments = _department_groups_with_permission(
            self.user, "add_department_tasks"
        )
        form = TaskForm(department_queryset=allowed_departments)

        self.assertQuerySetEqual(
            form.fields["department_group"].queryset,
            [self.department],
        )

    def test_bulk_submissions_require_an_ongoing_task(self):
        form = TaskForm(
            data={
                "title": "One-time bulk task",
                "instructions": "Report the completed work.",
                "department_group": str(self.department.pk),
                "assigned_groups": [str(self.department.pk)],
                "allow_bulk_submissions": "on",
                "frequency": Task.Frequency.ONE_TIME,
                "limit_scope": Task.LimitScope.PER_USER,
            },
            department_queryset=Group.objects.all(),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("allow_bulk_submissions", form.errors)

    def test_task_workflow_settings_are_locked_after_reports(self):
        form = TaskForm(
            instance=self.task,
            department_queryset=Group.objects.all(),
            workflow_locked=True,
        )

        self.assertFalse(form.fields["title"].disabled)
        self.assertFalse(form.fields["instructions"].disabled)
        for field_name in TaskForm.WORKFLOW_FIELDS:
            with self.subTest(field=field_name):
                self.assertTrue(form.fields[field_name].disabled)

    def test_task_creator_can_edit_task(self):
        self.task.created_by = self.user
        self.task.save(update_fields=("created_by",))
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("completed_tasks:edit_task", args=(self.task.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_editing"])
        self.assertFalse(response.context["workflow_locked"])

    def test_editing_after_a_completion_keeps_workflow_settings_unchanged(self):
        self.task.created_by = self.user
        self.task.frequency = Task.Frequency.ONGOING
        self.task.assigned_groups.add(self.department)
        self.task.save(update_fields=("created_by", "frequency"))
        TaskCompletion.objects.create(task=self.task, user=self.user)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("completed_tasks:edit_task", args=(self.task.pk,)),
            {
                "title": "Updated title",
                "instructions": "Updated instructions",
                "department_group": str(self.other_department.pk),
                "assigned_groups": [str(self.other_department.pk)],
                "frequency": Task.Frequency.ONE_TIME,
                "limit_scope": Task.LimitScope.SHARED,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Updated title")
        self.assertEqual(self.task.instructions, "Updated instructions")
        self.assertEqual(self.task.department_group, self.department)
        self.assertEqual(self.task.frequency, Task.Frequency.ONGOING)
        self.assertQuerySetEqual(
            self.task.assigned_groups.all(),
            [self.department],
        )
        self.assertEqual(self.task.updated_by, self.user)

    def test_forms_mark_required_optional_and_conditional_fields(self):
        form = TaskForm(department_queryset=Group.objects.all())
        completion_form = TaskCompletionForm()
        bulk_form = TaskBulkCompletionForm()

        self.assertEqual(
            form.fields["title"].widget.attrs["data-requirement-label"],
            "Required",
        )
        self.assertEqual(
            form.fields["assigned_groups"].widget.attrs["data-requirement-label"],
            "Optional",
        )
        self.assertEqual(
            form.fields["approver_groups"].widget.attrs["data-requirement-label"],
            "Conditional",
        )
        self.assertEqual(
            completion_form.fields["notes"].widget.attrs["data-requirement-label"],
            "Optional",
        )
        self.assertEqual(
            completion_form.fields["character"].widget.attrs[
                "data-requirement-label"
            ],
            "Required",
        )
        self.assertEqual(
            bulk_form.fields["characters"].widget.attrs[
                "data-requirement-label"
            ],
            "Required",
        )

    def test_csv_export_contains_only_authorized_department_reports(self):
        completion = TaskCompletion.objects.create(
            task=self.task,
            user=self.user,
            notes="Department A notes",
        )
        other_user = get_user_model().objects.create_user(
            username="other-pilot",
            password="test-password",
        )
        other_completion = TaskCompletion.objects.create(
            task=self.other_task,
            user=other_user,
            notes="Department B secret notes",
        )
        request = RequestFactory().get("/task-reports/reports/export.csv")
        request.user = self.user

        response = export_completions(request)
        body = response.content.decode("utf-8-sig")

        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("Department A notes", body)
        self.assertNotIn("Department B secret notes", body)
        self.assertIn(completion.user.get_username(), body)
        self.assertNotIn(other_completion.user.get_username(), body)
