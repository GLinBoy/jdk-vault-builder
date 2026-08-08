"""Content extraction from raw HTML via trafilatura."""

import logging
from dataclasses import dataclass

import trafilatura

logger = logging.getLogger(__name__)


@dataclass
class ExtractedContent:
    text: str
    page_title: str | None


def extract_content(html: str) -> ExtractedContent:
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        output_format="markdown",
    )

    if not text:
        logger.warning("Could not extract readable content from HTML")
        return ExtractedContent(text="", page_title=None)

    return ExtractedContent(text=text, page_title=_extract_page_title(html))


def _extract_page_title(html: str) -> str | None:
    metadata = trafilatura.extract_metadata(html)
    if metadata is not None and metadata.title:
        return metadata.title
    return None
