from __future__ import annotations

import argparse
import sys

from .app import build_app_context
from .config import ensure_app_dirs
from .doctor import run_doctor
from .editor import open_in_editor
from .events import collect_event_text, format_event_text, validate_event_type
from .frontmatter import read_document
from .models import CommandResult
from .nautical import nautical_summary
from .notes import (
    ensure_chain_note,
    ensure_project_note,
    ensure_task_note,
    find_chain_note,
    find_project_note,
    find_task_note,
    project_note_path,
)
from .output import emit_result, warn
from .search import search_all
from .storage import (
    append_chain_note_storage,
    append_project_note_storage,
    append_task_note_storage,
    finalize_chain_note_edit,
    finalize_project_note_edit,
    finalize_task_note_edit,
    record_event_add,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jot",
        description=(
            "Note-first companion for Taskwarrior and Taskwarrior-Nautical. "
            "Taskwarrior annotations remain the visible event stream; durable "
            "task, chain, and project context lives in note files under ~/.task/jot/."
        ),
        epilog=(
            "Examples:\n"
            "  jot note 42\n"
            "  jot chain 42\n"
            "  jot project Finances.Expense\n"
            "  jot add --type status 42 waiting on vendor\n"
            "  jot task-cat 42\n"
            "  jot project-show Finances.Expense"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of text",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "doctor",
        help="check configuration, storage paths, and Taskwarrior availability",
        description="Validate jot configuration, storage paths, and Taskwarrior access.",
    )

    task_commands = {
        "note": "open or create the task note in your editor",
        "chain": "open or create the Nautical chain note in your editor",
        "show": "show note paths and Nautical summary for a task",
        "list": "show task summary plus the current annotation event stream",
        "export": "export task summary and events",
        "task-cat": "print the full task note without opening an editor",
        "chain-cat": "print the full chain note without opening an editor",
    }
    for name, help_text in task_commands.items():
        sub = subparsers.add_parser(name, help=help_text, description=help_text[:1].upper() + help_text[1:] + ".")
        sub.add_argument(
            "task_ref",
            help="task ID, full UUID, or unique short UUID",
        )

    project = subparsers.add_parser(
        "project",
        help="open or create a project note in your editor",
        description="Open or create a durable note for an exact Taskwarrior project name.",
    )
    project.add_argument(
        "project_name",
        help="exact Taskwarrior project name, for example Finances.Expense",
    )

    project_show = subparsers.add_parser(
        "project-show",
        help="show project-note path and summary without editing",
        description="Show whether a project note exists, where it lives, and a short preview.",
    )
    project_show.add_argument(
        "project_name",
        help="exact Taskwarrior project name, for example Finances.Expense",
    )

    project_cat = subparsers.add_parser(
        "project-cat",
        help="print the full project note without opening an editor",
        description="Print the full project note content for an exact Taskwarrior project name.",
    )
    project_cat.add_argument(
        "project_name",
        help="exact Taskwarrior project name, for example Finances.Expense",
    )

    append_commands = {
        "note-append": "append plain text to a task note",
        "chain-append": "append plain text to a chain note",
    }
    for name, help_text in append_commands.items():
        sub = subparsers.add_parser(name, help=help_text, description=help_text[:1].upper() + help_text[1:] + ".")
        sub.add_argument(
            "task_ref",
            help="task ID, full UUID, or unique short UUID",
        )
        sub.add_argument(
            "text",
            nargs="*",
            help="text to append; if omitted, read stdin",
        )

    project_append = subparsers.add_parser(
        "project-append",
        help="append plain text to a project note",
        description="Append plain text to a project note without opening an editor.",
    )
    project_append.add_argument(
        "project_name",
        help="exact Taskwarrior project name, for example Finances.Expense",
    )
    project_append.add_argument(
        "text",
        nargs="*",
        help="text to append; if omitted, read stdin",
    )

    add = subparsers.add_parser(
        "add",
        help="add a short event to the task annotation stream",
        description=(
            "Add a short event to the Taskwarrior annotation stream. "
            "Text can come from arguments, stdin, or an editor fallback."
        ),
    )
    add.add_argument(
        "--type",
        default="note",
        dest="event_type",
        help="event type label, for example note, status, decision, blocker",
    )
    add.add_argument(
        "task_ref",
        help="task ID, full UUID, or unique short UUID",
    )
    add.add_argument(
        "text",
        nargs="*",
        help="event text; if omitted, read stdin or open the editor",
    )

    search = subparsers.add_parser(
        "search",
        help="search note files and logged events",
        description="Search task notes, chain notes, project notes, and the logged event stream.",
    )
    search.add_argument("query", help="case-insensitive search text")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    ctx = build_app_context()
    ensure_app_dirs(ctx.config)

    try:
        if args.command == "doctor":
            result = run_doctor(ctx.config, ctx.taskwarrior)
        elif args.command == "note":
            result = _run_note(ctx, args.task_ref)
        elif args.command == "chain":
            result = _run_chain(ctx, args.task_ref)
        elif args.command == "task-cat":
            result = _run_task_cat(ctx, args.task_ref)
        elif args.command == "chain-cat":
            result = _run_chain_cat(ctx, args.task_ref)
        elif args.command == "project":
            result = _run_project(ctx, args.project_name)
        elif args.command == "project-show":
            result = _run_project_show(ctx, args.project_name)
        elif args.command == "project-cat":
            result = _run_project_cat(ctx, args.project_name)
        elif args.command == "add":
            result = _run_add(ctx, args.task_ref, args.text, args.event_type)
        elif args.command == "note-append":
            result = _run_note_append(ctx, args.task_ref, _text_from_args(args.text))
        elif args.command == "chain-append":
            result = _run_chain_append(ctx, args.task_ref, _text_from_args(args.text))
        elif args.command == "project-append":
            result = _run_project_append(ctx, args.project_name, _text_from_args(args.text))
        elif args.command == "list":
            result = _run_list(ctx, args.task_ref)
        elif args.command == "show":
            result = _run_show(ctx, args.task_ref)
        elif args.command == "export":
            result = _run_export(ctx, args.task_ref)
        elif args.command == "search":
            result = _run_search(ctx, args.query)
        else:  # pragma: no cover
            parser.error(f"unknown command {args.command}")
            return 2
    except RuntimeError as exc:
        warn(str(exc))
        return 1

    emit_result(result, json_mode=args.json)
    return 0


def _run_note(ctx, task_ref: str) -> CommandResult:
    task = ctx.taskwarrior.resolve_task(task_ref)
    note = ensure_task_note(ctx.config, task)
    open_in_editor(note.note_path, ctx.config.editor_command)
    finalize_task_note_edit(ctx.config, task, note)
    return CommandResult(
        command="note",
        payload={
            "path": str(note.note_path),
            "opened": note.existed,
            "task_short_uuid": task.task_short_uuid,
        },
    )


def _run_chain(ctx, task_ref: str) -> CommandResult:
    task = ctx.taskwarrior.resolve_task(task_ref)
    note = ensure_chain_note(ctx.config, task)
    open_in_editor(note.note_path, ctx.config.editor_command)
    finalize_chain_note_edit(ctx.config, task, note)
    return CommandResult(
        command="chain",
        payload={
            "path": str(note.note_path),
            "opened": note.existed,
            "task_short_uuid": task.task_short_uuid,
        },
    )


def _run_project(ctx, project_name: str) -> CommandResult:
    note = ensure_project_note(ctx.config, project_name)
    open_in_editor(note.note_path, ctx.config.editor_command)
    finalize_project_note_edit(ctx.config, project_name, note)
    return CommandResult(
        command="project",
        payload={
            "path": str(note.note_path),
            "opened": note.existed,
            "project": project_name,
        },
    )


def _run_project_show(ctx, project_name: str) -> CommandResult:
    note_path = find_project_note(ctx.config, project_name)
    if note_path is None:
        return CommandResult(
            command="project-show",
            payload={
                "project": project_name,
                "path": str(project_note_path(ctx.config, project_name)),
                "exists": False,
            },
        )

    metadata, body = read_document(note_path)
    return CommandResult(
        command="project-show",
        payload={
            "project": project_name,
            "path": str(note_path),
            "exists": True,
            "created": metadata.get("created"),
            "updated": metadata.get("updated"),
            "project_path": metadata.get("project_path") or [],
            "body_preview": _body_preview(body),
        },
    )


def _run_project_cat(ctx, project_name: str) -> CommandResult:
    note_path = find_project_note(ctx.config, project_name)
    if note_path is None:
        raise RuntimeError(f"project note does not exist for {project_name}")
    return _cat_result("project-cat", note_path, project=project_name)


def _run_task_cat(ctx, task_ref: str) -> CommandResult:
    task = ctx.taskwarrior.resolve_task(task_ref)
    note_path = find_task_note(ctx.config, task)
    if note_path is None:
        raise RuntimeError(f"task note does not exist for {task.task_short_uuid}")
    return _cat_result(
        "task-cat",
        note_path,
        task_short_uuid=task.task_short_uuid,
    )


def _run_chain_cat(ctx, task_ref: str) -> CommandResult:
    task = ctx.taskwarrior.resolve_task(task_ref)
    note_path = find_chain_note(ctx.config, task)
    if note_path is None:
        raise RuntimeError(f"chain note does not exist for {task.task_short_uuid}")
    return _cat_result(
        "chain-cat",
        note_path,
        task_short_uuid=task.task_short_uuid,
    )


def _run_show(ctx, task_ref: str) -> CommandResult:
    task = ctx.taskwarrior.resolve_task(task_ref)
    payload = _task_summary_payload(ctx, task)
    return CommandResult(command="show", payload=payload)


def _run_export(ctx, task_ref: str) -> CommandResult:
    task = ctx.taskwarrior.resolve_task(task_ref)
    payload = _task_summary_payload(ctx, task)
    payload["events"] = ctx.taskwarrior.annotations_for_task(task)
    return CommandResult(command="export", payload=payload)


def _task_summary_payload(ctx, task) -> dict:
    task_note = find_task_note(ctx.config, task)
    payload: dict[str, object] = {
        "task_short_uuid": task.task_short_uuid,
        "description": task.description,
        "task_note": str(task_note) if task_note is not None else None,
        "nautical": nautical_summary(task.task),
    }
    if task.project:
        project_note = find_project_note(ctx.config, task.project)
        payload["project"] = task.project
        if project_note is not None:
            payload["project_note"] = str(project_note)
    chain_note = find_chain_note(ctx.config, task)
    if chain_note is not None:
        payload["chain_note"] = str(chain_note)
    return payload


def _run_add(ctx, task_ref: str, text_parts: list[str], event_type: str) -> CommandResult:
    task = ctx.taskwarrior.resolve_task(task_ref)
    normalized_type = validate_event_type(event_type)
    text = collect_event_text(
        parts=text_parts,
        stdin_text=(sys.stdin.read().strip() if not sys.stdin.isatty() else None),
        editor_command=ctx.config.editor_command,
        task_short_uuid=task.task_short_uuid,
        description=task.description,
    )
    annotation = format_event_text(normalized_type, text)
    ctx.taskwarrior.add_annotation(task.task_uuid, annotation)
    record_event_add(ctx.config, task, event_type=normalized_type, annotation=annotation)
    return CommandResult(
        command="add",
        payload={
            "task_short_uuid": task.task_short_uuid,
            "annotation": annotation,
            "event_type": normalized_type,
        },
    )


def _run_list(ctx, task_ref: str) -> CommandResult:
    task = ctx.taskwarrior.resolve_task(task_ref)
    payload = _task_summary_payload(ctx, task)
    payload["events"] = ctx.taskwarrior.annotations_for_task(task)
    return CommandResult(command="list", payload=payload)


def _run_note_append(ctx, task_ref: str, text: str) -> CommandResult:
    task = ctx.taskwarrior.resolve_task(task_ref)
    result = append_task_note_storage(ctx.config, task, text)
    return CommandResult(
        command="note-append",
        payload={
            "path": str(result.note_path),
            "opened": result.existed,
            "task_short_uuid": task.task_short_uuid,
        },
    )


def _run_chain_append(ctx, task_ref: str, text: str) -> CommandResult:
    task = ctx.taskwarrior.resolve_task(task_ref)
    result = append_chain_note_storage(ctx.config, task, text)
    return CommandResult(
        command="chain-append",
        payload={
            "path": str(result.note_path),
            "opened": result.existed,
            "task_short_uuid": task.task_short_uuid,
        },
    )


def _run_project_append(ctx, project_name: str, text: str) -> CommandResult:
    result = append_project_note_storage(ctx.config, project_name, text)
    return CommandResult(
        command="project-append",
        payload={
            "path": str(result.note_path),
            "opened": result.existed,
            "project": project_name,
        },
    )


def _run_search(ctx, query: str) -> CommandResult:
    payload = {
        "query": query,
        **search_all(ctx.config, query),
    }
    return CommandResult(command="search", payload=payload)


def _text_from_args(parts: list[str]) -> str:
    if parts:
        return " ".join(parts).strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    raise RuntimeError("no text supplied; provide text or pipe stdin")


def _body_preview(body: str, width: int = 120) -> str:
    text = " ".join(str(body or "").split())
    if len(text) <= width:
        return text
    return text[: width - 3].rstrip() + "..."


def _cat_result(command: str, note_path, **extra: str) -> CommandResult:
    metadata, body = read_document(note_path)
    payload = {
        **extra,
        "path": str(note_path),
        "metadata": dict(metadata),
        "body": body,
        "content": note_path.read_text(encoding="utf-8"),
    }
    return CommandResult(command=command, payload=payload)
