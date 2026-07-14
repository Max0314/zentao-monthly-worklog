from __future__ import annotations

import re
from calendar import monthrange
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .records import load_json, save_json


FIX_RE = re.compile(r"(?i)\bfix(?:ed|es)?\b|bug|hotfix|修复|异常|错误|问题")


def draft_date(month: str) -> str:
    start = datetime.strptime(month, "%Y-%m").date()
    end = date(start.year, start.month, monthrange(start.year, start.month)[1])
    return min(date.today(), end).isoformat()


def _repo_mapping(settings, repo_name: str) -> dict[str, Any] | None:
    if repo_name in settings.repositories:
        return settings.repositories[repo_name]
    lower = repo_name.lower()
    for pattern, mapping in settings.repositories.items():
        if pattern.endswith("*") and lower.startswith(pattern[:-1].lower()):
            return mapping
    return None


def _unique_files(commits: list[dict[str, Any]], limit=12) -> list[str]:
    result = []
    for commit in commits:
        for item in commit.get("files", []):
            path = item.get("path")
            if path and path not in result:
                result.append(path)
            if len(result) >= limit:
                return result
    return result


def build_draft(evidence: dict[str, Any], settings) -> dict[str, Any]:
    month = evidence["month"]
    draft: dict[str, Any] = {
        "month": month,
        "date": draft_date(month),
        "project_id": settings.project_id,
        "stories": [],
        "tasks": [],
        "bugs": [],
        "bug_candidates": [],
        "unclassified": [],
    }
    groups: dict[tuple[int, str], dict[str, Any]] = {}
    for repo in evidence.get("git_repositories", []):
        mapping = _repo_mapping(settings, repo["name"])
        if not mapping:
            draft["unclassified"].append(
                {"repository": repo["name"], "reason": "No repository mapping in config.local.json"}
            )
            continue
        execution = settings.execution(mapping["execution"])
        product_id = int(mapping.get("product_id") or execution.get("product_id") or 0)
        display_name = mapping.get("display_name") or execution.get("name") or repo["name"]
        group = groups.setdefault(
            (int(execution["id"]), display_name),
            {
                "execution": execution,
                "product_id": product_id,
                "display_name": display_name,
                "repositories": [],
                "commits": {},
            },
        )
        group["repositories"].append(repo["name"])
        for commit in repo.get("commits", []):
            group["commits"].setdefault(commit["hash"], commit)

    for group in groups.values():
        execution = group["execution"]
        product_id = group["product_id"]
        display_name = group["display_name"]
        repo_key = "-".join(sorted(group["repositories"]))
        commits = list(group["commits"].values())
        fixes = [item for item in commits if FIX_RE.search(item.get("subject", ""))]
        work = commits

        if work:
            subjects = [item["subject"] for item in work[:10]]
            files = _unique_files(work)
            draft["tasks"].append(
                {
                    "key": f"{month}-{repo_key}-task",
                    "execution": int(execution["id"]),
                    "title": f"完善 {display_name} 本月功能与工程能力",
                    "detail": "【任务详细描述】结合本月 AI 对话与 Git 变更，完成："
                    + "；".join(subjects),
                    "comments": [
                        f"【任务完成步骤】梳理 {display_name} 本月需求与提交记录，明确实现范围和验收口径。",
                        "【任务完成步骤】完成核心代码修改，涉及文件：" + "、".join(files[:8]) + "。",
                        "【任务完成步骤】执行相关测试、静态检查或构建验证，并复查提交差异。",
                    ],
                    "estimate": max(1, min(8, len(work))),
                    "sources": [item["hash"] for item in work],
                }
            )

        for commit in fixes:
            files = [item.get("path") for item in commit.get("files", []) if item.get("path")]
            subject = commit["subject"]
            draft["bug_candidates"].append(
                {
                    "execution": int(execution["id"]),
                    "product": product_id,
                    "title": subject,
                    "files": files[:6],
                    "reason": "Commit message suggests a fix; inspect conversation evidence before promoting to a resolved Bug.",
                    "sources": [commit["hash"]],
                }
            )
    return draft


def create_draft_file(evidence_path: str | Path, settings, output: str | Path | None = None) -> Path:
    evidence = load_json(evidence_path)
    target = Path(output) if output else Path("output") / evidence["month"] / "draft.json"
    return save_json(target, build_draft(evidence, settings))
