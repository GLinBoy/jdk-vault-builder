# JDK Vault Builder

A Python CLI tool that builds and maintains an **Obsidian vault** documenting
Java JDK changes. It reads a manually-maintained CSV of JDK release links,
fetches and archives the referenced web pages, extracts clean readable text,
generates one markdown note per link, and combines each JDK version's notes
into a single markdown file for use as a **NotebookLM** source.

The tool is designed to be re-run whenever a new JDK version is released.
Updates are cheap, safe, and never touch previously completed work — a URL is
"done" if its cached HTML exists, and a note is "done" if its `.md` file
exists (no state database).

## Module layout

| Path                    | Purpose                                                          |
|-------------------------|------------------------------------------------------------------|
| `config.py`             | Paths, throttle settings, user agent, bot-challenge markers     |
| `main.py`               | CLI entrypoint (argparse)                                       |
| `data/jdk_links.csv`    | Source CSV of JDK release links (hand-maintained)               |
| `cache/raw_pages/`      | Archived HTML backups, keyed by SHA-256 of the URL              |
| `vault/`                | Generated Obsidian vault (one folder per JDK version)           |
| `src/csv_loader.py`     | CSV parsing, validation, `JdkLink` dataclass, version grouping  |
| `src/fetcher.py`        | Throttled HTTP fetch, disk cache, headless-browser fallback     |
| `src/content_extractor.py` | HTML → clean readable text via `trafilatura`                 |
| `src/vault_organizer.py`    | Folder/filename creation and path resolution                 |
| `src/note_builder.py`       | Renders individual notes from templates + frontmatter      |
| `src/combiner.py`           | Merges notes for one JDK version into a single file     |
| `templates/`               | Jinja2 templates (`note.md.j2`, `combined.md.j2`)          |
| `tests/`                   | Pytest suite (one test file per `src/` module + integration) |

## How to run

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py --help
```

Real subcommands (`fetch`, `build-notes`, `combine`, `all`) are scaffolded as
part of the phased build-out documented in `PLAN.md` (internal-only file).

## Development

Quality gate before any phase is considered done:

```bash
ruff check src/ main.py config.py
black --check src/ main.py config.py
mypy src/ main.py config.py
pytest
```