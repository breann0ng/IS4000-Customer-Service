from __future__ import annotations
"""
processors/html_cleaner.py

Takes raw HTML from a UBS page and returns clean structured text.
Strips navigation, footer, cookie banners, breadcrumbs, and all
boilerplate — leaving only the article heading and body content.

Returns a dict:
{
    "title":    str,          # H1 of the page
    "topic":    str,          # inferred from URL path
    "subtopic": str,          # inferred from URL path
    "sections": [             # list of content sections
        {"heading": str, "body": str},
        ...
    ],
    "full_text": str,         # flat join of all sections, for embedding
}
"""

import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup, Tag


# CSS selectors / tag names we always strip before parsing
_NOISE_SELECTORS = [
    "nav", "header", "footer",
    "[class*='navigation']", "[class*='nav-']",
    "[class*='breadcrumb']", "[class*='cookie']",
    "[class*='banner']", "[class*='modal']",
    "[class*='skip']", "[class*='meta']",
    "[class*='footer']", "[class*='header']",
    "[id*='nav']", "[id*='header']", "[id*='footer']",
    "script", "style", "noscript", "iframe",
    # UBS-specific boilerplate selectors
    ".cmp-navigation", ".cmp-footer", ".cmp-header",
    ".ubs-header", ".ubs-footer",
]

# Patterns to strip from text
_NOISE_TEXT_PATTERNS = [
    r"Skip Links?",
    r"Back to top",
    r"You are here:",
    r"© UBS \d{4}.*",
    r"Short URL:.*",
    r"Change your domicile.*",
    r"Footer Navigation",
    r"Main Navigation",
    r"Meta Navigation",
    r"\d+ results? found",
]
_NOISE_RE = re.compile("|".join(_NOISE_TEXT_PATTERNS), re.IGNORECASE)


def _infer_topic_from_url(url: str) -> tuple[str, str]:
    """Return (topic, subtopic) inferred from URL path segments."""
    path = urlparse(url).path.rstrip("/")
    parts = [p for p in path.split("/") if p]
    # e.g. ['ch', 'en', 'help', 'creditcard', 'lock-replacement']
    try:
        help_idx = parts.index("help")
        topic = parts[help_idx + 1] if len(parts) > help_idx + 1 else "general"
        subtopic = parts[help_idx + 2] if len(parts) > help_idx + 2 else ""
    except ValueError:
        # Not a /help/ page — try /services/
        try:
            svc_idx = parts.index("services")
            topic = parts[svc_idx + 1] if len(parts) > svc_idx + 1 else "services"
            subtopic = parts[svc_idx + 2] if len(parts) > svc_idx + 2 else ""
        except ValueError:
            topic = parts[-2] if len(parts) >= 2 else "general"
            subtopic = parts[-1] if parts else ""
    return topic, subtopic


def _clean_text(text: str) -> str:
    """Normalise whitespace and strip noise patterns."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l and not _NOISE_RE.search(l)]
    return "\n".join(lines).strip()


def clean_html(html: str, url: str) -> dict:
    """Parse HTML and return structured clean text dict."""
    soup = BeautifulSoup(html, "lxml")

    # Remove all noise elements
    for selector in _NOISE_SELECTORS:
        for el in soup.select(selector):
            el.decompose()

    # Remove all <a> tags that are purely navigation links (no text body)
    for a in soup.find_all("a"):
        if a.get_text(strip=True) == "":
            a.decompose()

    # Get title
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""

    # Get main content area — try common UBS content wrappers first
    main = (
        soup.find("main")
        or soup.find(id="main")
        or soup.find(class_=re.compile(r"content|article|body", re.I))
        or soup.find("article")
        or soup.body
    )

    sections: list[dict] = []
    current_heading = title
    current_body_parts: list[str] = []

    if main:
        for el in main.descendants:
            if not isinstance(el, Tag):
                continue
            if el.name in ("h2", "h3", "h4"):
                # Save previous section
                body = _clean_text(" ".join(current_body_parts))
                if body:
                    sections.append({"heading": current_heading, "body": body})
                current_heading = el.get_text(strip=True)
                current_body_parts = []
            elif el.name in ("p", "li", "dt", "dd"):
                txt = el.get_text(separator=" ", strip=True)
                if txt:
                    current_body_parts.append(txt)

    # Flush last section
    body = _clean_text(" ".join(current_body_parts))
    if body:
        sections.append({"heading": current_heading, "body": body})

    # If we got nothing structured, fall back to full page text
    if not sections:
        fallback = _clean_text(soup.get_text(separator="\n"))
        if fallback:
            sections = [{"heading": title, "body": fallback}]

    full_text = "\n\n".join(
        f"{s['heading']}\n{s['body']}" if s["heading"] else s["body"]
        for s in sections
    )

    topic, subtopic = _infer_topic_from_url(url)

    return {
        "title": title,
        "url": url,
        "topic": topic,
        "subtopic": subtopic,
        "sections": sections,
        "full_text": _clean_text(full_text),
    }
