# AGENTS.md

This file gives AI coding assistants (and humans) the standing context needed to work on this repository correctly, without re-deriving decisions already made. Read this before making changes. For phase-by-phase task breakdown, see `PLAN.md` (internal only, not committed).

## Project Purpose

A Python CLI tool that builds and maintains an Obsidian vault documenting Java JDK changes. It reads a manually-maintained CSV of JDK release links, fetches and archives the referenced web pages, extracts clean readable text, generates one markdown note per link, organizes notes into a per-version vault folder structure, and combines each version's notes into a single markdown file for use as a NotebookLM source.

This tool is re-run every time a new JDK version is released — updates must be cheap, safe, and never touch previously completed work.

## Tech Stack

- Python 3 (developed on 3.14.6; code should remain compatible with 3.10+)
- Dependency management: `venv` + `pip` + `requirements.txt` — no Poetry, no uv, no pipenv
- Key libraries: `requests` (HTTP), `trafilatura` (content extraction), `playwright` (headless-browser fallback only), `jinja2` (templating), `pyyaml` (frontmatter), `pytest` (testing), `ruff` + `black` + `mypy` (quality gate)
- No database — filesystem state only (see "State Model" below)

## Repository Layout

```
config.py               # all paths, constants, throttle settings, bot-challenge markers
main.py                 # CLI entrypoint (argparse: fetch / build-notes / combine / home / all)
data/jdk_links.csv       # manually maintained source CSV (~350 rows and growing)
cache/                  # untouched HTML backups, keyed by sha256(url).html
cache/fetch.log          # fetch run logs
JDK Changes Vault/       # the generated Obsidian vault (one folder per JDK version + Home.md)
src/
  csv_loader.py          # CSV parsing, validation, JdkLink dataclass, version grouping
  fetcher.py              # throttled HTTP fetch, disk cache, headless-browser fallback
  content_extractor.py    # HTML -> clean raw-dump text via trafilatura
  vault_organizer.py      # folder/filename creation and path resolution
  note_builder.py         # renders individual notes from templates + frontmatter
  combiner.py             # merges all notes for one jdk_version into one file
  home_builder.py         # generates the root-level vault Home.md overview page
templates/
  note.md.j2              # single-note template
  combined.md.j2          # per-version combined-file template
  home.md.j2              # vault root overview template
tests/                    # pytest suite, one test file per src/ module + integration test
```

Each `src/` module is independent and stateless between calls — no module reaches into another module's internals. `main.py` is the only place that wires modules together.

## State Model (important — do not reinvent)

There is **no database, no JSON ledger, no run-tracking file**. "Has this URL/note already been processed?" is answered purely by filesystem existence:

- A URL is considered fetched if `cache/{sha256(url)}.html` exists. If present, `fetcher.py` returns a cache hit and makes **no network call**.
- A note is considered built if its `.md` file already exists in the vault. `note_builder.py` **never overwrites** an existing note.
- The combined `_combined/JDK {version} - Full.md` file is the one exception: it is **always rebuilt from scratch** on each `combine` run (never tracked/diffed), and prompts for overwrite confirmation (default: no) unless `--force` is passed.

Do not add a state database, hash-comparison cache invalidation, or "last run" tracking — this was a deliberate scope decision. If content ever needs to be refreshed, the fix is to delete the specific cached HTML file or note file and re-run, not to build automatic staleness detection.

## Fetching Rules

- Global throttle: **1 request per second** across the entire run, not per-domain.
- `200` response → check body against `config.BOT_CHALLENGE_MARKERS`; if clean, cache and return success.
- `404` → log a warning, skip, move to the next URL. No retry.
- Bot-challenge detected (Cloudflare/CAPTCHA-style page) → retry once via a **lazily-imported** Playwright headless browser. Only import Playwright inside that code path — never at module top-level — so normal runs never pay headless-browser startup cost.
- Never fetch a URL whose cache file already exists.

## Content Extraction Rules

- Extraction is a **raw dump**, not a summary — mirrors what the Obsidian Web Clipper browser extension produces. Do not add LLM summarization, keyword extraction, or section-splitting logic (e.g., don't try to parse JEP pages into separate "Goals"/"Motivation" fields — that's an explicit v2 idea, not in scope now).
- Both artifacts are kept: raw HTML in `cache/` (permanent backup, re-parseable) and extracted markdown text embedded in the note (used directly by Obsidian and NotebookLM/RAG).
- No iframe embedding of live web pages — sites frequently block iframe embedding and it doesn't survive offline use. Always archive the content, don't reference the live page as the primary artifact.

## Note & Vault Conventions

- One markdown note per CSV row (per URL). `project_page` and `release_notes` rows are "parent" notes for their `jdk_version`.
- Every note has YAML frontmatter: `jdk_version`, `link_type`, `jep_number`, `title`, `source_url`, `fetched`, a `parent:` property holding an Obsidian `[[wikilink]]` to that version's `project_page` note (the project page links to itself), and a `tags:` list holding the version tag (`jdk_7`) and the link type (`project_page`, `release_notes`, or `jep`).
- Notes are **Obsidian-free, independent markdown** — no `[[wikilink]]` or other Obsidian-specific syntax in the body, and no trailing tags section. Cross-note connection happens through the YAML frontmatter: the `tags:` property carries both `jdk_{version}` and the link type, and the `parent:` property links each note to its JDK version's project page. This is the deliberate replacement for the earlier wikilink-backlink scheme.
- Vault folder structure: `JDK Changes Vault/JDK {version}/` per version, with a `_combined/` subfolder holding that version's merged NotebookLM file. JEP notes live in a `jep/` subfolder (`JDK Changes Vault/JDK {version}/jep/`); `project_page` and `release_notes` notes sit directly in the version folder. Combined files end with a `Tags: #jdk_{version}` line.
- A root-level `JDK Changes Vault/Home.md` is regenerated on every `home`/`all` run (always overwritten, like the combiner output) — a hub page that explains the vault's purpose and summarizes its data: the versions present, note counts per version, counts by link type, and pointers to each version's combined file.
- Because notes are never overwritten, an existing note only picks up a new format if it is **deleted and rebuilt** (from `cache/`, no network needed). The full vault was regenerated this way when the tag-based format was introduced.
- Filenames are sanitized via `vault_organizer.sanitize_filename()` — never write raw titles containing filesystem-unsafe characters directly to disk.

## Git Workflow

- **No remote exists yet.** Never run `git push` until explicitly told a GitHub repo has been created and its URL confirmed.
- Branch model: `main` + `feature/*` only. No git-flow, no `develop` branch.
- Before starting work: check `git branch --show-current`. If on `main`, create a new `feature/<name>` branch automatically. If on an unrecognized branch, ask before proceeding.
- **Never commit without explicit user permission.** Show the full diff/file list first and wait for the word "commit".
- Use Conventional Commits: `feat:`, `fix:`, `refactor:`, `chore:`, `test:`.
- `PLAN.md` is internal-only — never commit or push it; it must stay in `.gitignore`.

## Quality Gate (required before any phase is considered done)

```bash
ruff check src/ main.py config.py
black --check src/ main.py config.py
mypy src/ main.py config.py
pytest
```

All four must pass cleanly. Do not mark work complete, update `PLAN.md` status, or ask for a commit until they do.

## Testing Conventions

- One test file per `src/` module (`tests/test_<module>.py`), plus `tests/test_integration.py` for the full end-to-end pipeline.
- Never make real network calls in tests — mock `requests.get` and the Playwright fallback.
- The canonical test fixture is the 6-row sample CSV (JDK 6 and JDK 9 rows) used throughout `PLAN.md` — reuse it rather than inventing new sample data, so tests stay consistent across phases.
- Use `tmp_path`/temp directories for any test that touches the filesystem (cache, vault) — never write test artifacts into the real `cache/` or `JDK Changes Vault/` directories.

## Things Explicitly Out of Scope (v1)

- Discovering/scraping new CSV rows automatically — the CSV is hand-maintained.
- Structured per-section parsing of JEP content (Goals/Motivation/etc.) — raw dump only.
- Automatic staleness detection / re-fetching changed pages — pages are treated as immutable once released.
- GitHub Actions automation — deferred to `PLAN.md` Phase 10, after local completion and repo creation.
- Support for other content types (migration guides, deprecation notices, Java EE, frameworks like Spring Boot) — the CSV schema and note templates may need to extend for these later, but the current templates should not be over-generalized preemptively for content that doesn't exist yet in the CSV.

## When Extending This Project Later

If this pipeline is reused for a future related project (e.g., a separate Java EE or Spring Boot changelog vault), keep `fetcher.py`, `content_extractor.py`, and `combiner.py` free of any JDK-specific assumptions — they should already be generic enough to lift into a new project without modification. `csv_loader.py`, `note_builder.py`, and `vault_organizer.py` are the modules expected to change per-project (schema and template specifics).
