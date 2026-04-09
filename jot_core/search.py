from __future__ import annotations

from pathlib import Path
from typing import Any

from .frontmatter import read_document
from .models import AppConfig
from .ops import read_ops


def search_all(config: AppConfig, query: str) -> dict[str, list[dict[str, Any]]]:
    needle = str(query or "").strip().lower()
    if not needle:
        raise RuntimeError("search query is empty")

    return {
        "notes": _search_notes(config, needle),
        "events": _search_events(config, needle),
    }


def _search_notes(config: AppConfig, needle: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for base, pattern, kind in (
        (config.tasks_dir, "*.md", "task-note"),
        (config.chains_dir, "*.md", "chain-note"),
        (config.projects_dir, "**/index.md", "project-note"),
    ):
        for path in sorted(base.glob(pattern)):
            metadata, body = read_document(path)
            haystacks = [
                str(metadata.get("description") or ""),
                str(metadata.get("project") or ""),
                str(body or ""),
                path.name,
            ]
            combined = "\n".join(haystacks).lower()
            if needle not in combined:
                continue
            item = {
                "kind": kind,
                "path": str(path),
                "description": str(metadata.get("description") or ""),
                "match": _excerpt(str(body or ""), needle),
            }
            project_name = str(metadata.get("project") or "")
            if project_name:
                item["project"] = project_name
            hits.append(item)
    return hits


def _search_events(config: AppConfig, needle: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for item in read_ops(config):
        if str(item.get("op") or "") != "event_add":
            continue
        annotation = str(item.get("annotation") or "")
        if needle not in annotation.lower():
            continue
        hits.append(
            {
                "kind": "event",
                "task_short_uuid": str(item.get("task_short_uuid") or ""),
                "ts": str(item.get("ts") or ""),
                "annotation": annotation,
            }
        )
    return hits


def _excerpt(body: str, needle: str, width: int = 80) -> str:
    text = " ".join(str(body or "").split())
    if not text:
        return ""
    idx = text.lower().find(needle)
    if idx < 0:
        return text[:width]
    start = max(0, idx - width // 3)
    end = min(len(text), start + width)
    excerpt = text[start:end]
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(text):
        excerpt += "..."
    return excerpt
