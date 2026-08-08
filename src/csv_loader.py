"""CSV parsing and validation for JDK release links."""

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class JdkLink:
    jdk_version: int
    link_type: str
    jep_number: int | None
    title: str
    url: str


def load_csv(path: Path) -> list[JdkLink]:
    """Load and validate JDK release links from a CSV file.

    The CSV must have a header row with ``jdk_version``, ``link_type``,
    ``jep_number``, ``title``, and ``url`` columns. ``jep_number`` is allowed
    to be empty (becomes ``None``); all other fields must be non-empty.

    Rows must be fully unique; exact duplicate rows are logged as warnings but
    do not fail the load.

    Raises:
        ValueError: if a row is malformed (missing/empty required field or a
            non-integer ``jdk_version``/``jep_number``), with the offending
            row number included in the message.
    """
    links: list[JdkLink] = []
    seen: set[tuple[object, ...]] = set()

    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row_number, row in enumerate(reader, start=2):  # row 1 is the header
            jdk_version = _required_str(row, "jdk_version", row_number)
            link_type = _required_str(row, "link_type", row_number)
            title = _required_str(row, "title", row_number)
            url = _required_str(row, "url", row_number)
            jep_raw = (row.get("jep_number") or "").strip()

            try:
                jdk_version_int = int(jdk_version)
            except ValueError:
                raise ValueError(
                    f"Row {row_number}: jdk_version must be an integer, got {jdk_version!r}"
                )

            jep_number = None
            if jep_raw:
                try:
                    jep_number = int(jep_raw)
                except ValueError:
                    raise ValueError(
                        f"Row {row_number}: jep_number must be an integer, got {jep_raw!r}"
                    )

            link = JdkLink(
                jdk_version=jdk_version_int,
                link_type=link_type,
                jep_number=jep_number,
                title=title,
                url=url,
            )
            signature = (
                link.jdk_version,
                link.link_type,
                link.jep_number,
                link.title,
                link.url,
            )
            if signature in seen:
                logger.warning("Duplicate row ignored at CSV line %d: %r", row_number, link)
            else:
                seen.add(signature)
                links.append(link)

    return links


def group_by_version(links: list[JdkLink]) -> dict[int, list[JdkLink]]:
    """Group links by their JDK version."""

    grouped: dict[int, list[JdkLink]] = {}
    for link in links:
        grouped.setdefault(link.jdk_version, []).append(link)
    return grouped


def _required_str(row: dict[str, str], field: str, row_number: int) -> str:
    """Return the stripped value for ``field`` or raise for an empty value."""

    value = (row.get(field) or "").strip()
    if not value:
        raise ValueError(f"Row {row_number}: required field {field!r} is empty")
    return value
