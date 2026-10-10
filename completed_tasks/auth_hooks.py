from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class TaskReportsMenuItemHook(MenuItemHook):
    def render(self, request):
        if not request.user.has_perm("completed_tasks.access_task_reports"):
            return ""
        return super().render(request)


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "completed_tasks", r"^task-reports/")


@hooks.register("menu_item_hook")
def register_menu():
    return TaskReportsMenuItemHook(
        "Task Reports",
        "fas fa-list-check fa-fw",
        "completed_tasks:dashboard",
        order=1110,
    )
