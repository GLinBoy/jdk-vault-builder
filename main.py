"""JDK Vault Builder CLI entrypoint.

Wires together the csv_loader, fetcher, content_extractor, note_builder, and
combiner modules into end-to-end subcommands. All path arguments default to
the constants in config.py.
"""

import argparse
import sys
from pathlib import Path

import config
from src import combiner, content_extractor, csv_loader, fetcher, home_builder, note_builder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jdk-vault-builder",
        description=(
            "Builds and maintains an Obsidian vault documenting Java JDK changes "
            "from a CSV of release links."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    fetch = subparsers.add_parser(
        "fetch", help="Fetch and cache raw HTML for every URL in the CSV."
    )
    _add_common_path_args(fetch, include_vault=False)
    _add_version_arg(fetch)
    fetch.set_defaults(func=_cmd_fetch)

    build_notes = subparsers.add_parser(
        "build-notes", help="Build vault notes from cached HTML for every URL in the CSV."
    )
    _add_common_path_args(build_notes, include_vault=True)
    _add_version_arg(build_notes)
    build_notes.set_defaults(func=_cmd_build_notes)

    combine = subparsers.add_parser(
        "combine",
        help="Merge all notes for one (or every) JDK version into a single file.",
    )
    combine.add_argument(
        "--vault",
        type=Path,
        default=config.VAULT_DIR,
        help="Vault directory (default: %(default)s).",
    )
    _add_version_arg(combine)
    combine.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing combined files without prompting.",
    )
    combine.set_defaults(func=_cmd_combine)

    home = subparsers.add_parser(
        "home", help="Generate the root-level vault Home.md overview page."
    )
    home.add_argument(
        "--vault",
        type=Path,
        default=config.VAULT_DIR,
        help="Vault directory (default: %(default)s).",
    )
    home.set_defaults(func=_cmd_home)

    all_ = subparsers.add_parser(
        "all", help="Run fetch, then build-notes, then combine, then home in sequence."
    )
    _add_common_path_args(all_, include_vault=True)
    _add_version_arg(all_)
    all_.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing combined files without prompting.",
    )
    all_.set_defaults(func=_cmd_all)

    return parser


def _add_common_path_args(parser: argparse.ArgumentParser, *, include_vault: bool) -> None:
    parser.add_argument(
        "--csv",
        type=Path,
        default=config.CSV_PATH,
        help="Path to the JDK links CSV (default: %(default)s).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=config.CACHE_DIR,
        help="Directory for cached raw HTML (default: %(default)s).",
    )
    if include_vault:
        parser.add_argument(
            "--vault",
            type=Path,
            default=config.VAULT_DIR,
            help="Obsidian vault output directory (default: %(default)s).",
        )


def _add_version_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--version",
        type=int,
        help="Restrict the run to a single jdk_version (e.g. 21).",
    )


def _filter_by_version(
    links: list[csv_loader.JdkLink], version: int | None
) -> list[csv_loader.JdkLink]:
    if version is None:
        return links
    return [link for link in links if link.jdk_version == version]


def _cmd_fetch(args: argparse.Namespace) -> None:
    fetcher.configure_logging(args.cache_dir)
    links = _filter_by_version(csv_loader.load_csv(args.csv), args.version)

    counts = {"cached": 0, "fetched": 0, "not_found": 0, "blocked": 0}
    failures: list[tuple[csv_loader.JdkLink, str]] = []
    for index, link in enumerate(links, start=1):
        print(f"Fetching {index}/{len(links)}: {link.url}")
        result = fetcher.fetch_url(link.url, args.cache_dir)
        counts[result.status] += 1
        if result.status in ("not_found", "blocked"):
            failures.append((link, result.status))

    summary = ", ".join(f"{name}={count}" for name, count in counts.items())
    print(f"Fetch complete: {summary}")
    for link, status in failures:
        print(f"  {status}: {link.url} (no note will be built for this row)")


def _cmd_build_notes(args: argparse.Namespace) -> None:
    links = csv_loader.load_csv(args.csv)
    selected = _filter_by_version(links, args.version)

    built = 0
    skipped = 0
    for link in selected:
        cache_path = fetcher.url_to_cache_path(link.url, args.cache_dir)
        if not cache_path.exists():
            print(f"Warning: no cached HTML for {link.url}; skipping note")
            skipped += 1
            continue
        html = cache_path.read_text(encoding="utf-8")
        extracted = content_extractor.extract_content(html)
        path = note_builder.build_note(link, extracted, links, args.vault)
        print(f"Built note: {path}")
        built += 1
    scope = "all versions" if args.version is None else f"JDK {args.version}"
    print(f"Notes ({scope}): built={built}, skipped={skipped}")


def _cmd_combine(args: argparse.Namespace) -> None:
    if args.version is not None:
        _combine_one(args.vault, args.version, args.force)
        return
    for version in _find_version_folders(args.vault):
        _combine_one(args.vault, version, args.force)


def _cmd_home(args: argparse.Namespace) -> None:
    path = home_builder.build_home(args.vault)
    print(f"Built home page: {path}")


def _combine_one(vault_dir: Path, version: int, force: bool) -> None:
    output = combiner.combine_version(vault_dir, version, force=force)
    if output is not None:
        print(f"Combined JDK {version}: {output}")
    else:
        print(f"No notes to combine for JDK {version}")


def _find_version_folders(vault_dir: Path) -> list[int]:
    if not vault_dir.is_dir():
        return []
    versions: list[int] = []
    for folder in vault_dir.iterdir():
        name = folder.name
        if folder.is_dir() and name.startswith("JDK ") and name[4:].isdigit():
            versions.append(int(name[4:]))
    return sorted(versions)


def _cmd_all(args: argparse.Namespace) -> None:
    _cmd_fetch(args)
    _cmd_build_notes(args)
    _cmd_combine(args)
    _cmd_home(args)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
