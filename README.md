# MPX Completed Task Form

An Alliance Auth app for publishing reportable tasks, recording member
completions, routing required approvals, and keeping a completion history.
It follows the Bootstrap 5 layout and Alliance Auth navigation pattern used by
the MPX Missed Meeting form.

## Features

- Tasks belong to an Alliance Auth/Django department group and can be assigned
  to groups, individuals, or both.
- Task creators choose one-time or ongoing tasks and whether each completion
  requires approval.
- Approval can be routed to selected groups and/or individual users.
- Reviewers can approve a completion, request a revision, or deny it
  permanently. Revisions are resubmitted to the review queue.
- One-time tasks close after an approved completion, or immediately after
  submission when approval is not required.
- Optional lifetime completion caps can apply per pilot or across a task.
- Department-authorized users can create tasks and view/export reports only for
  department groups where they have the matching permission. Global permissions
  can be assigned to administrators for cross-department access.
- Task creators can close ongoing tasks while preserving completion history.
- Members can view their own completion history. Users with the appropriate
  permission can view all reports.
- Completion notes provide a short summary; detailed structure data can remain
  in the existing structures module.

This app reports task completions; it is not a task manager or PAP system.

## Task and completion fields

The task forms mark **Required** fields in red, **Optional** fields in green,
and **Conditional** fields in amber. Conditional fields are required only when
their related option is enabled.

| Field | Required? | Purpose and impact |
|---|---|---|
| **Task name** | Yes | Short title shown in task lists, history, and reports. |
| **Instructions** | Yes | Tells members what work to do and what to include in their completion notes. Detailed game or scanning data can remain in its existing module. |
| **Department** | Yes | Selects the owning Alliance Auth group. Department permissions scope task creation, approvals, reporting, and exports. Choices are limited to departments the creator is allowed to manage; global task creators can choose any group. |
| **Who can report: groups** | At least one group or individual is required | Every member of a selected group is eligible to submit the task. |
| **Who can report: individuals** | At least one group or individual is required | Selected individuals are also eligible, whether or not they belong to an assigned group. |
| **Each completion requires approval** | No; unchecked by default | When checked, a submission waits for an assigned approver. When unchecked, it is recorded as approved immediately. |
| **Approver groups / individuals** | Only when approval is enabled | Members of a selected group and selected individuals can review submissions for this task. At least one approver group or person is required if approval is enabled. |
| **Task type** | Yes; one-time by default | A one-time task closes after its completion is approved, or after submission if approval is off. An ongoing task remains available for repeat reports until closed or its cap is reached. |
| **Completion limit** | No | Optional lifetime cap for ongoing tasks. Pending, revision-requested, and approved submissions count; permanently denied submissions do not. It does not reset daily or weekly. |
| **Limit applies to** | No | Only affects the task when a limit is set. Per pilot gives each eligible member their own lifetime cap. Shared applies one total cap across all eligible members. |
| **Completion date and time** | Yes; defaults to current local time | Records when the member says the work was completed, rather than when the report was submitted. |
| **Completion notes** | No; up to 2,000 characters | Briefly describes what was done—for example, systems visited. Shown in the member's history and permission-scoped reports. |
| **Review decision** | Yes for reviewers | Approve accepts the report; request revision returns it to the pilot for resubmission; deny permanently ends that submission. |
| **Review feedback** | Required for revision or denial; optional for approval | Explains the decision to the pilot and remains with the completion history. |

Task submissions record reporting and review status; this app does not award
PAP points or integrate with a PAP system.

## Installation

Install the package in the Alliance Auth virtual environment:

```shell
pip install git+https://github.com/frfrmpukin/mpx-completed-task-form.git
```

Add `completed_tasks` to `INSTALLED_APPS` in Alliance Auth settings. Then apply
migrations, collect static files, and restart Alliance Auth:

```shell
python /home/allianceserver/myauth/manage.py migrate
python /home/allianceserver/myauth/manage.py collectstatic --noinput
supervisorctl restart myauth:
```

Alliance Auth hooks add the **Task Reporter** navigation link for users granted
the access permission. Task creation, completion approval, report visibility,
and CSV export are controlled by Django permissions and task-specific
group/user assignments. Department-level permissions are assigned to the
department's Alliance Auth group; the user must belong to that group. The
models are intentionally not registered in Django Admin; task work is managed
through the app, while access to Django Admin remains governed by Alliance
Auth's existing staff permissions.

## Permissions

Assign these permissions to users or groups in Alliance Auth's permission
settings:

| Permission | What it allows |
|---|---|
| **Can access task reports** (`access_task_reports`) | Allows access to the app and displays its navigation link. |
| **Can add task** (`add_task`) | Global permission: create tasks in any department and close any task. Reserve for administrators. |
| **Can add department tasks** (`add_department_tasks`) | When granted on an Alliance Auth group, members of that group can create tasks for that department and close its tasks. |
| **Can view all task completions** (`view_all_completions`) | Global permission: view completion reports from all departments. |
| **Can view department completions** (`view_department_completions`) | When granted on a department group, members can view that department's reports. |
| **Can export all task completions** (`export_all_completions`) | Global permission: export reports across all departments as CSV. |
| **Can export department completions** (`export_department_completions`) | When granted on a department group, members can export that department's reports as CSV. The department must also grant report-view permission to appear in the reports interface. |
| **Can approve any task completion** (`approve_task_completions`) | Global permission: approve completions across all departments. |
| **Can approve department completions** (`approve_department_completions`) | When granted on a department group, members can approve that department's completions. |

Task-specific approver groups and individuals can review only completions for
the tasks that assign them as approvers. For department-level access, assign
the relevant permission to the department's Django group in Alliance Auth's
permission settings. Global access permissions should be reserved for
administrators.

## Development

The package requires Python 3.10 or later and Alliance Auth 4.0 or later. The
app can be tested from an Alliance Auth installation using its configured
Django test runner.
