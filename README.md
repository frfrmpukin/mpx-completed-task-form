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

Alliance Auth hooks add the **Task Reports** navigation link for users granted
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
