from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
import re

from .frontmatter import read_document, update_metadata, write_document
from .models import AppConfig, AppendResult, NotePaths, ResolvedTask
from .nautical import chain_id_for_task
from .ops import iso_now
from .templates import apply_template


SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, fallback: str = "task", max_len: int = 40) -> str:
    slug = SLUG_RE.sub("-", text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        slug = fallback
    return slug[:max_len].rstrip("-") or fallback


def task_note_path(config: AppConfig, task: ResolvedTask) -> Path:
    existing = sorted(config.tasks_dir.glob(f"{task.task_short_uuid}--*.md"))
    if existing:
        return existing[0]
    slug = slugify(task.description or "task", fallback="task")
    return config.tasks_dir / f"{task.task_short_uuid}--{slug}.md"


def chain_note_path(config: AppConfig, chain_id: str, description: str) -> Path:
    existing = sorted(config.chains_dir.glob(f"{chain_id}--*.md"))
    if existing:
        return existing[0]
    slug = slugify(description or "chain", fallback="chain")
    return config.chains_dir / f"{chain_id}--{slug}.md"


def project_note_path(config: AppConfig, project_name: str) -> Path:
    normalized = str(project_name or "").strip()
    if not normalized:
        raise RuntimeError("project name is empty")
    parts = [slugify(part, fallback="project") for part in normalized.split(".") if part.strip()]
    if not parts:
        raise RuntimeError("project name is empty")
    return config.projects_dir.joinpath(*parts, "index.md")


def ensure_task_note(config: AppConfig, task: ResolvedTask) -> NotePaths:
    note_path = task_note_path(config, task)
    existed = note_path.exists()
    if not existed:
        metadata, body = _build_task_note_document(config, task)
        write_document(note_path, metadata, body)
    return NotePaths(note_path=note_path, existed=existed)


def find_task_note(config: AppConfig, task: ResolvedTask) -> Path | None:
    existing = sorted(config.tasks_dir.glob(f"{task.task_short_uuid}--*.md"))
    return existing[0] if existing else None


def ensure_chain_note(config: AppConfig, task: ResolvedTask) -> NotePaths:
    chain_id = chain_id_for_task(task.task)
    if not chain_id:
        raise RuntimeError("task is not part of a Nautical chain")
    note_path = chain_note_path(config, chain_id, task.description or chain_id)
    existed = note_path.exists()
    if not existed:
        metadata, body = _build_chain_note_document(config, task)
        write_document(note_path, metadata, body)
    return NotePaths(note_path=note_path, existed=existed)


def ensure_project_note(config: AppConfig, project_name: str) -> NotePaths:
    normalized = str(project_name or "").strip()
    if not normalized:
        raise RuntimeError("project name is empty")
    note_path = project_note_path(config, normalized)
    existed = note_path.exists()
    if not existed:
        metadata, body = _build_project_note_document(config, normalized)
        write_document(note_path, metadata, body)
    return NotePaths(note_path=note_path, existed=existed)


def touch_updated(path: Path) -> None:
    update_metadata(path, {"updated": iso_now()})


def append_to_task_note(config: AppConfig, task: ResolvedTask, text: str) -> AppendResult:
    note = ensure_task_note(config, task)
    _append_text(note.note_path, text)
    touch_updated(note.note_path)
    return AppendResult(note_path=note.note_path, existed=note.existed, appended_text=text)


def append_to_chain_note(config: AppConfig, task: ResolvedTask, text: str) -> AppendResult:
    note = ensure_chain_note(config, task)
    _append_text(note.note_path, text)
    touch_updated(note.note_path)
    return AppendResult(note_path=note.note_path, existed=note.existed, appended_text=text)


def append_to_project_note(config: AppConfig, project_name: str, text: str) -> AppendResult:
    note = ensure_project_note(config, project_name)
    _append_text(note.note_path, text)
    touch_updated(note.note_path)
    return AppendResult(note_path=note.note_path, existed=note.existed, appended_text=text)


def find_chain_note(config: AppConfig, task: ResolvedTask) -> Path | None:
    chain_id = chain_id_for_task(task.task)
    if not chain_id:
        return None
    existing = sorted(config.chains_dir.glob(f"{chain_id}--*.md"))
    return existing[0] if existing else None


def find_project_note(config: AppConfig, project_name: str) -> Path | None:
    normalized = str(project_name or "").strip()
    if not normalized:
        return None
    note_path = project_note_path(config, normalized)
    return note_path if note_path.exists() else None


def _build_task_note_document(config: AppConfig, task: ResolvedTask) -> tuple[OrderedDict[str, object], str]:
    created = iso_now()
    chain_id = chain_id_for_task(task.task)
    link_value = str(task.task.get("link") or "").strip()
    metadata: OrderedDict[str, object] = OrderedDict(
        [
            ("kind", "task-note"),
            ("task_short_uuid", task.task_short_uuid),
            ("description", task.description or ""),
            ("project", task.project or ""),
            ("tags", list(task.tags)),
        ]
    )
    if chain_id:
        metadata["chain_id"] = chain_id
    if link_value:
        metadata["link"] = link_value
    metadata["created"] = created
    metadata["updated"] = created
    default_body = "\n".join(
        [
            f"# {task.description or task.task_short_uuid}",
            "",
            "## Context",
            "",
            "## Notes",
            "",
            "## References",
            "",
            "## Next steps",
        ]
    )
    context = {
        "task_short_uuid": task.task_short_uuid,
        "task_uuid": task.task_uuid,
        "description": task.description or "",
        "project": task.project or "",
        "chain_id": chain_id or "",
        "link": link_value,
        "created": created,
        "updated": created,
        "project_path": task.project or "",
    }
    return apply_template(
        config.templates_dir,
        kind="task-note",
        context=context,
        default_metadata=metadata,
        default_body=default_body,
    )


def _build_chain_note_document(config: AppConfig, task: ResolvedTask) -> tuple[OrderedDict[str, object], str]:
    created = iso_now()
    chain_id = chain_id_for_task(task.task)
    metadata: OrderedDict[str, object] = OrderedDict(
        [
            ("kind", "chain-note"),
            ("chain_id", chain_id),
            ("description", task.description or ""),
            ("anchor", str(task.task.get("anchor") or "").strip() or None),
            ("cp", str(task.task.get("cp") or "").strip() or None),
            ("anchor_mode", str(task.task.get("anchor_mode") or "").strip() or None),
            ("created", created),
            ("updated", created),
        ]
    )
    default_body = "\n".join(
        [
            f"# {task.description or chain_id}",
            "",
            "## Purpose",
            "",
            "## Operating notes",
            "",
            "## Exceptions",
            "",
            "## References",
        ]
    )
    context = {
        "task_short_uuid": task.task_short_uuid,
        "task_uuid": task.task_uuid,
        "description": task.description or "",
        "project": task.project or "",
        "chain_id": chain_id or "",
        "link": str(task.task.get("link") or "").strip(),
        "created": created,
        "updated": created,
        "project_path": task.project or "",
    }
    return apply_template(
        config.templates_dir,
        kind="chain-note",
        context=context,
        default_metadata=metadata,
        default_body=default_body,
    )


def _build_project_note_document(config: AppConfig, project_name: str) -> tuple[OrderedDict[str, object], str]:
    created = iso_now()
    project_path = [part.strip() for part in project_name.split(".") if part.strip()]
    metadata: OrderedDict[str, object] = OrderedDict(
        [
            ("kind", "project-note"),
            ("project", project_name),
            ("project_path", project_path),
            ("created", created),
            ("updated", created),
        ]
    )
    default_body = "\n".join(
        [
            f"# {project_name}",
            "",
            "## Purpose",
            "",
            "## Context",
            "",
            "## Standards",
            "",
            "## References",
            "",
            "## Active concerns",
        ]
    )
    context = {
        "task_short_uuid": "",
        "task_uuid": "",
        "description": project_name,
        "project": project_name,
        "chain_id": "",
        "link": "",
        "created": created,
        "updated": created,
        "project_path": ".".join(project_path),
    }
    return apply_template(
        config.templates_dir,
        kind="project-note",
        context=context,
        default_metadata=metadata,
        default_body=default_body,
    )


def _append_text(path: Path, text: str) -> None:
    metadata, body = read_document(path)
    chunk = text.rstrip()
    if not chunk:
        raise RuntimeError("cannot append empty text")
    normalized = body.rstrip("\n")
    if normalized:
        normalized += "\n\n"
    normalized += chunk
    write_document(path, metadata, normalized)

