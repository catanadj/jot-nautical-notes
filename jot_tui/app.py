from __future__ import annotations

from typing import Any

from jot_core.services import JotService


def run_tui(service: JotService) -> int:
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical
        from textual.widgets import DataTable, Footer, Header, Input, Static
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "textual is required for `jot tui` (install with: pip install textual)"
        ) from exc

    class JotTUI(App[None]):
        CSS = """
        Screen { layout: vertical; }
        #top { height: 1fr; }
        #left { width: 2fr; border: round $panel; }
        #right { width: 3fr; border: round $panel; }
        #search-input { margin: 0 1; }
        #task-detail { padding: 1; }
        #recent-table, #projects-table, #search-notes-table, #search-events-table { height: 1fr; }
        """

        BINDINGS = [
            ("q", "quit", "Quit"),
            ("r", "refresh", "Refresh"),
            ("slash", "focus_search", "Search"),
        ]

        def __init__(self, svc: JotService) -> None:
            super().__init__()
            self.svc = svc
            self.recent_rows: list[dict[str, Any]] = []

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            yield Input(placeholder="Search notes/events and press Enter", id="search-input")
            with Horizontal(id="top"):
                with Vertical(id="left"):
                    recent = DataTable(id="recent-table", cursor_type="row")
                    recent.add_columns("ts", "kind", "id", "summary")
                    yield Static("Recent", classes="title")
                    yield recent
                    projects = DataTable(id="projects-table", cursor_type="row")
                    projects.add_columns("project", "updated")
                    yield Static("Projects", classes="title")
                    yield projects
                with Vertical(id="right"):
                    yield Static("Task Detail", classes="title")
                    yield Static("Select a recent task row to load details.", id="task-detail")
                    notes = DataTable(id="search-notes-table", cursor_type="row")
                    notes.add_columns("kind", "path", "match")
                    yield Static("Search Notes", classes="title")
                    yield notes
                    events = DataTable(id="search-events-table", cursor_type="row")
                    events.add_columns("task", "annotation", "ts")
                    yield Static("Search Events", classes="title")
                    yield events
            yield Footer()

        def on_mount(self) -> None:
            self._refresh_recent()
            self._refresh_projects()

        def action_refresh(self) -> None:
            self._refresh_recent()
            self._refresh_projects()

        def action_focus_search(self) -> None:
            self.query_one("#search-input", Input).focus()

        def on_input_submitted(self, event: Input.Submitted) -> None:
            if event.input.id != "search-input":
                return
            query = event.value.strip()
            if not query:
                return
            self._run_search(query)

        def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
            if event.data_table.id != "recent-table":
                return
            row_index = event.cursor_row
            if row_index < 0 or row_index >= len(self.recent_rows):
                return
            item = self.recent_rows[row_index]
            short_uuid = str(item.get("task_short_uuid") or "").strip()
            if not short_uuid:
                return
            self._load_task(short_uuid)

        def _refresh_recent(self) -> None:
            table = self.query_one("#recent-table", DataTable)
            table.clear()
            self.recent_rows = self.svc.recent(limit=80)
            for item in self.recent_rows:
                ident = (
                    str(item.get("task_short_uuid") or "").strip()
                    or str(item.get("chain_id") or "").strip()
                    or str(item.get("project") or "").strip()
                )
                summary = (
                    str(item.get("description") or "").strip()
                    or str(item.get("annotation") or "").strip()
                    or str(item.get("path") or "").strip()
                )
                table.add_row(
                    str(item.get("ts") or ""),
                    str(item.get("kind") or ""),
                    ident,
                    summary,
                )

        def _refresh_projects(self) -> None:
            table = self.query_one("#projects-table", DataTable)
            table.clear()
            for item in self.svc.projects():
                table.add_row(str(item.get("project") or ""), str(item.get("updated") or ""))

        def _run_search(self, query: str) -> None:
            notes_table = self.query_one("#search-notes-table", DataTable)
            events_table = self.query_one("#search-events-table", DataTable)
            notes_table.clear()
            events_table.clear()
            data = self.svc.search(query)
            for item in data.get("notes", []):
                notes_table.add_row(
                    str(item.get("kind") or ""),
                    str(item.get("path") or ""),
                    str(item.get("match") or ""),
                )
            for item in data.get("events", []):
                events_table.add_row(
                    str(item.get("task_short_uuid") or ""),
                    str(item.get("annotation") or ""),
                    str(item.get("ts") or ""),
                )

        def _load_task(self, task_ref: str) -> None:
            detail = self.query_one("#task-detail", Static)
            try:
                data = self.svc.task_summary(task_ref)
            except Exception as exc:
                detail.update(f"Task load failed for {task_ref}\n\n{exc}")
                return
            lines: list[str] = []
            task = data.get("task", {})
            lines.append(f"Task {task.get('short_uuid')}")
            lines.append(f"Description: {task.get('description')}")
            lines.append(f"Project: {task.get('project') or ''}")
            tags = task.get("tags") or []
            if tags:
                lines.append(f"Tags: {', '.join(tags)}")
            notes = data.get("notes", {})
            lines.append("")
            lines.append("Notes:")
            lines.append(f"  task: {notes.get('task')}")
            if notes.get("chain"):
                lines.append(f"  chain: {notes.get('chain')}")
            if notes.get("project"):
                lines.append(f"  project: {notes.get('project')}")
            lines.append("")
            lines.append("Recent events:")
            events = data.get("events") or []
            if not events:
                lines.append("  (none)")
            else:
                for item in events[:8]:
                    lines.append(f"  {item.get('entry') or ''} {item.get('description') or ''}".strip())
            detail.update("\n".join(lines))

    app = JotTUI(service)
    app.run()
    return 0
