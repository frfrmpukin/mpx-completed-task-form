from django.urls import path

from . import views

app_name = "completed_tasks"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("superadmin/records/", views.superadmin_records, name="superadmin_records"),
    path(
        "superadmin/tasks/<int:task_id>/edit/",
        views.superadmin_edit_task,
        name="superadmin_edit_task",
    ),
    path(
        "superadmin/tasks/<int:task_id>/delete/",
        views.superadmin_delete_task,
        name="superadmin_delete_task",
    ),
    path(
        "superadmin/completions/<int:completion_id>/edit/",
        views.superadmin_edit_completion,
        name="superadmin_edit_completion",
    ),
    path(
        "superadmin/completions/<int:completion_id>/delete/",
        views.superadmin_delete_completion,
        name="superadmin_delete_completion",
    ),
    path("tasks/create/", views.create_task, name="create_task"),
    path("tasks/<int:task_id>/edit/", views.edit_task, name="edit_task"),
    path("tasks/<int:task_id>/close/", views.close_task, name="close_task"),
    path("tasks/<int:task_id>/submit/", views.submit_completion, name="submit"),
    path(
        "tasks/<int:task_id>/submit-for-pilots/",
        views.bulk_submit_completions,
        name="bulk_submit",
    ),
    path(
        "completions/<int:completion_id>/revise/",
        views.revise_completion,
        name="revise",
    ),
    path(
        "completions/<int:completion_id>/review/",
        views.review_completion,
        name="review",
    ),
    path("reports/", views.all_completions, name="all_completions"),
    path("reports/export.csv", views.export_completions, name="export_completions"),
    path("reports/monthly-pap/", views.monthly_pap_report, name="monthly_pap_report"),
    path(
        "reports/monthly-pap/export.csv",
        views.export_monthly_pap_report,
        name="export_monthly_pap_report",
    ),
]
