from django.urls import path

from . import views

app_name = "completed_tasks"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("tasks/create/", views.create_task, name="create_task"),
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
]
