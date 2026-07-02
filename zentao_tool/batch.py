from .client import ZentaoClient, extract_created_id
from .web_comments import ZentaoWebComments


def create_completed_task_with_comments(client, comments, execution_id, title, detail, estimate=3, date=None):
    created = client.create_task(execution_id, title, detail, estimate=estimate, date=date)
    task_id = extract_created_id(created, "task")
    web = ZentaoWebComments(account=client.account, password=client.password)
    for comment in comments:
        web.add_comment("task", task_id, comment)
    client.finish_task(task_id, consumed=estimate, date=date)
    return task_id


def create_resolved_bug_with_comments(client, comments, product_id, execution_id, project_id, title, detail, date=None):
    created = client.create_bug(product_id, execution_id, project_id, title, detail)
    bug_id = extract_created_id(created, "bug")
    web = ZentaoWebComments(account=client.account, password=client.password)
    for comment in comments:
        web.add_comment("bug", bug_id, comment)
    client.resolve_bug(bug_id, date=date)
    return bug_id


def verify_records(client, tasks_by_execution, bugs_by_execution):
    rows = []

    for execution_id, tasks in tasks_by_execution.items():
        listed = client.list_execution_tasks(execution_id)
        by_id = {int(item["id"]): item for item in listed}
        for task_id, title in tasks.items():
            item = by_id.get(int(task_id))
            rows.append(
                {
                    "type": "task",
                    "execution": int(execution_id),
                    "id": int(task_id),
                    "expected_title": title,
                    "found": item is not None,
                    "status": item.get("status") if item else None,
                    "title": item.get("name") if item else None,
                }
            )

    for execution_id, bugs in bugs_by_execution.items():
        listed = client.list_execution_bugs(execution_id)
        by_id = {int(item["id"]): item for item in listed}
        for bug_id, title in bugs.items():
            item = by_id.get(int(bug_id))
            rows.append(
                {
                    "type": "bug",
                    "execution": int(execution_id),
                    "id": int(bug_id),
                    "expected_title": title,
                    "found": item is not None,
                    "status": item.get("status") if item else None,
                    "resolution": item.get("resolution") if item else None,
                    "title": item.get("title") if item else None,
                }
            )

    return rows

