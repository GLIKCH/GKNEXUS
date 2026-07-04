# MemoryManagement

This package stores and manages conversation memory files.

Data storage:
- Human-editable Markdown files with YAML frontmatter in [docs/conversations](docs/conversations).
- An `index.json` at [docs/index.json](docs/index.json) maps conversation IDs to files and metadata.

Usage:
- Add a conversation via the CLI (expects JSON input).

Example JSON for `add`:

{
  "id": "example-1",
  "metadata": {"title": "Example 1", "created": "2026-07-02"},
  "messages": [{"role":"user","content":"Hello"},{"role":"assistant","content":"Hi"}]
}

Commands:
- `python -m MemoryManagement.cli add path/to/data.json`
- `python -m MemoryManagement.cli edit path/to/data.json`
- `python -m MemoryManagement.cli delete <id>`
- `python -m MemoryManagement.cli list`
- `python -m MemoryManagement.cli show example-1`
- `python -m MemoryManagement.cli search "query"`
- `python -m MemoryManagement.cli prune`

Web UI:
- Run `python -m MemoryManagement.webapp`
- Open `http://localhost:5001/`
- Search conversations, view expiry status, edit metadata, and delete entries

Capture API:
- POST JSON to `/api/capture` to automatically save bot conversations.
- Payload fields: `id`, `metadata`, `messages`

Testing:
- Run unit tests with `python -m unittest discover -s MemoryManagement/tests`

Next steps:
- Add better frontend message editing.
- Add authentication and bot framework adapters.
- Add conversation version history and backups.
