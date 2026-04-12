from __future__ import annotations

from pathlib import Path
from typing import Any

from .frontmatter import read_document
from .models import AppConfig
from .ops import read_ops
from .search import ALLOWED_KINDS


def list_project_notes(config: AppConfig) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(config.projects_dir.glob("**/index.md")):
        metadata, _body = read_document(path)
        project = str(metadata.get("project") or "").strip()
        if not project:
            continue
        items.append(
            {
                "project": project,
                "path": str(path),
                "updated": str(metadata.get("updated") or "").strip() or None,
            }
        )
    items.sort(key=lambda item: str(item.get("project") or "").lower())
    return items


def recent_activity(
    config: AppConfig,
    *,
    limit: int = 20,
    kinds: set[str] | None = None,
) -> list[dict[str, Any]]:
    if limit <= 0:
        raise RuntimeError("limit must be greater than zero")
    selected = set(kinds or ALLOWED_KINDS)

    items: list[dict[str, Any]] = []
    if "task-note" in selected:
        items.extend(_recent_task_notes(config))
    if "chain-note" in selected:
        items.extend(_recent_chain_notes(config))
    if "project-note" in selected:
        items.extend(_recent_project_notes(config))
    if "event" in selected:
        items.extend(_recent_events(config))
    items.sort(key=lambda item: str(item.get("ts") or ""), reverse=True)
    return items[:limit]


def _recent_task_notes(config: AppConfig) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(config.tasks_dir.glob("*.md")):
        metadata, _body = read_document(path)
        ts = str(metadata.get("updated") or "").strip()
        short_uuid = str(metadata.get("task_short_uuid") or "").strip()
        if not ts or not short_uuid:
            continue
        items.append(
            {
                "ts": ts,
                "kind": "task-note",
                "task_short_uuid": short_uuid,
                "path": str(path),
                "description": str(metadata.get("description") or "").strip(),
            }
        )
    return items


def _recent_chain_notes(config: AppConfig) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(config.chains_dir.glob("*.md")):
        metadata, _body = read_document(path)
        ts = str(metadata.get("updated") or "").strip()
        chain_id = str(metadata.get("chain_id") or "").strip()
        if not ts or not chain_id:
            continue
        items.append(
            {
                "ts": ts,
                "kind": "chain-note",
                "chain_id": chain_id,
                "path": str(path),
                "description": str(metadata.get("description") or "").strip(),
            }
        )
    return items


def _recent_project_notes(config: AppConfig) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(config.projects_dir.glob("**/index.md")):
        metadata, _body = read_document(path)
        ts = str(metadata.get("updated") or "").strip()
        project = str(metadata.get("project") or "").strip()
        if not ts or not project:
            continue
        items.append(
            {
                "ts": ts,
                "kind": "project-note",
                "project": project,
                "path": str(path),
            }
        )
    return items


def _recent_events(config: AppConfig) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in read_ops(config):
        if str(item.get("op") or "") != "event_add":
            continue
        ts = str(item.get("ts") or "").strip()
        if not ts:
            continue
        items.append(
            {
                "ts": ts,
                "kind": "event",
                "task_short_uuid": str(item.get("task_short_uuid") or "").strip() or None,
                "annotation": str(item.get("annotation") or "").strip(),
            }
        )
    return items
