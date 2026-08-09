# JDK Vault Builder

A Python CLI tool that builds and maintains an **Obsidian vault** documenting
Java JDK changes. It reads a manually-maintained CSV of JDK release links,
fetches and archives the referenced web pages, extracts clean readable text,
generates one markdown note per link, organizes notes into a per-version vault
folder structure, and combines each version's notes into a single markdown file
for use as a **NotebookLM** source.

Re-run it whenever a new JDK version is released. Updates are cheap, safe, and
never touch previously completed work — there is no state database. A URL is
"done" if its cached HTML exists, and a note is "done" if its `.md` file
exists.

## Features

- **Throttled fetching** — 1 request/second globally, with a disk cache keyed
  by SHA-256 of the URL, so re-runs never refetch.
- **Headless-browser fallback** — Cloudflare/CAPTCHA-style bot challenges are
  retried once via Playwright, lazily imported only when actually needed.
- **Raw content extraction** — HTML is reduced to clean readable text with
  `trafilatura` (a raw dump, not a summary), mirroring what the Obsidian Web
  Clipper browser extension produces.
- **Per-version vault** — one folder per JDK version (with a `jep/` subfolder
  for JEP notes), where notes are Obsidian-free markdown connected via tags
  (`jdk_7`, link type) rather than wikilinks.
- **Idempotent and safe** — notes are never overwritten once written; the
  per-version combined file is rebuilt from scratch and only overwritten with
  confirmation (or `--force`).
- **NotebookLM-ready export** — every version's notes are merged into a single
  `_combined/JDK {version} - Full.md` file.

## Installation

Requires Python 3.10+.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The Playwright headless browser is only needed if a site serves a bot-challenge
and no cached copy exists. To enable that fallback, install the Chromium binary:

```bash
playwright install chromium
```

## Usage

```
usage: jdk-vault-builder [-h] COMMAND ...

Commands:
  fetch        Fetch and cache raw HTML for every URL in the CSV.
  build-notes  Build vault notes from cached HTML for every URL in the CSV.
  combine      Merge all notes for one (or every) JDK version into a single file.
  all          Run fetch, then build-notes, then combine in sequence.
```

All path arguments default to the constants in `config.py`:

| Option        | Description                                                    |
|---------------|----------------------------------------------------------------|
| `--csv PATH`  | Path to the JDK links CSV (default: `data/jdk_links.csv`)      |
| `--cache-dir` | Directory for cached raw HTML (default: `cache/`)              |
| `--vault`     | Obsidian vault output directory (default: `JDK Changes Vault/`) |
| `--version N` | Restrict the run to a single `jdk_version` (e.g. `21`)         |
| `--force`     | Overwrite existing combined files without prompting (`combine`, `all`) |

### Examples

Run the full pipeline:

```bash
python main.py all
```

Run the full pipeline for a single JDK version:

```bash
python main.py all --version 21
```

Fetch only (no note building or combining):

```bash
python main.py fetch
```

Rebuild only the combined NotebookLM files, overwriting without prompting:

```bash
python main.py combine --force
```

### How re-runs behave

Running the same command again does no re-fetching and no re-note-building —
cached HTML and existing notes are reused as-is. Only the combined files are
rebuilt, and the `combine` step prompts for confirmation (`[y/N]`, default no)
unless `--force` is passed. To refresh a specific page, delete its cached HTML
file in `cache/raw_pages/` (or the note in `JDK Changes Vault/`) and re-run.

## Project layout

```
config.py                  Paths, throttle settings, user agent, bot-challenge markers
main.py                    CLI entrypoint (argparse: fetch / build-notes / combine / home / all)
data/jdk_links.csv         Source CSV of JDK release links (hand-maintained)
cache/raw_pages/           Archived HTML backups, keyed by SHA-256 of the URL
cache/fetch.log            Fetch run logs
JDK Changes Vault/         Generated Obsidian vault (one folder per JDK version)
src/
  csv_loader.py            CSV parsing, validation, JdkLink dataclass, version grouping
  fetcher.py               Throttled HTTP fetch, disk cache, headless-browser fallback
  content_extractor.py     HTML -> clean raw text via trafilatura
  vault_organizer.py       Folder/filename creation and path resolution
  note_builder.py          Renders individual notes from templates + frontmatter
  combiner.py              Merges notes for one JDK version into a single file
  home_builder.py          Generates the root-level vault Home.md overview page
templates/
  note.md.j2               Single-note template (frontmatter + content)
  combined.md.j2           Per-version combined-file template
  home.md.j2               Vault root overview template
tests/                     Pytest suite (one test file per src/ module + integration)
```

## Note format

Every note carries YAML frontmatter:

```yaml
---
jdk_version: 9
link_type: jep
jep_number: 110
title: HTTP 2 Client
source_url: https://openjdk.org/jeps/110
fetched: 2026-08-08
parent: "[[JDK 9 Project Page]]"
tags: [jdk_9, jep]
---
```

Notes are Obsidian-free, independent markdown: no wikilinks, no trailing tags
section, no other Obsidian-specific syntax in the body. Cross-note connection
happens through the YAML frontmatter — the `tags:` property carries both the
version tag (`jdk_7`) and the link type (`project_page` / `release_notes` /
`jep`), and the `parent:` property links each note to its JDK version's project
page. JEP notes live in a `jep/` subfolder under their version's folder.

Each version's combined `_combined/JDK {version} - Full.md` file ends with a
`Tags: #jdk_{version}` line.

## Development

### Quality gate

All four must pass before work is considered done:

```bash
ruff check src/ main.py config.py
black --check src/ main.py config.py
mypy src/ main.py config.py
pytest
```

### Testing

The test suite covers every `src/` module plus an end-to-end integration test.
Tests never make real network calls — `requests.get` and the Playwright
fallback are mocked. Test artifacts are written to temporary directories, never
to the real `cache/` or `JDK Changes Vault/`.

```bash
pytest -v
```

## Constraints (v1 scope)

- The CSV is **hand-maintained** — no automatic row discovery or scraping.
- Content extraction is a **raw dump**; there is no LLM summarization or
  structured per-section parsing of JEP pages.
- Pages are treated as **immutable** once released — no automatic staleness
  detection or refetching.
