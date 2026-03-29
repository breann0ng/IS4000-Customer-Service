from __future__ import annotations

"""
scrapers/help_scraper.py

Crawls the UBS public help centre at https://www.ubs.com/ch/en/help/
and all discovered sub-pages. Saves raw HTML and cleaned JSON to output/.

Behaviour:
- Starts from the known category index pages
- Discovers child page links (only within /ch/en/help/)
- Respects robots.txt (via utils.robots_checker)
- Polite rate limiting (via utils.rate_limiter)
- Retries transient failures up to 3 times
- Saves raw HTML to output/raw/
- Saves cleaned JSON to output/processed/
"""

import os
import sys
import json
import logging
import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Allow running directly from scrapers/ or from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.robots_checker import is_allowed, get_crawl_delay, USER_AGENT
from utils.rate_limiter import polite_wait
from processors.html_cleaner import clean_html

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("help_scraper")

BASE_URL = "https://www.ubs.com"
DOMAIN = "ubs.com"

# All known help category index pages — these are the top-level entry points
# discovered from the UBS help centre navigation
HELP_SEED_URLS = [
    "https://www.ubs.com/ch/en/help.html",
    "https://www.ubs.com/ch/en/help/digital-banking.html",
    "https://www.ubs.com/ch/en/help/cards-keyclub.html",
    "https://www.ubs.com/ch/en/help/accounts-payments.html",
    "https://www.ubs.com/ch/en/help/my-data.html",
    "https://www.ubs.com/ch/en/help/pension.html",
    "https://www.ubs.com/ch/en/help/mortgages.html",
    "https://www.ubs.com/ch/en/help/key4.html",
    "https://www.ubs.com/ch/en/help/key4-business.html",
    # Individual topic pages
    "https://www.ubs.com/ch/en/help/account.html",
    "https://www.ubs.com/ch/en/help/payments.html",
    "https://www.ubs.com/ch/en/help/creditcard.html",
    "https://www.ubs.com/ch/en/help/debitcard.html",
    "https://www.ubs.com/ch/en/help/e-banking.html",
    "https://www.ubs.com/ch/en/help/mobile-banking.html",
    "https://www.ubs.com/ch/en/help/twint.html",
]

OUTPUT_RAW = Path(__file__).parent.parent / "output" / "raw"
OUTPUT_PROCESSED = Path(__file__).parent.parent / "output" / "processed"
OUTPUT_RAW.mkdir(parents=True, exist_ok=True)
OUTPUT_PROCESSED.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
)


def _url_to_filename(url: str) -> str:
    """Convert URL to a safe filename."""
    path = urlparse(url).path.strip("/").replace("/", "__")
    if not path:
        path = "index"
    return path[:200]  # filesystem limit


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    retry=retry_if_exception_type(requests.RequestException),
    reraise=True,
)
def _fetch(url: str) -> requests.Response:
    polite_wait(DOMAIN, min_delay=get_crawl_delay(url))
    resp = SESSION.get(url, timeout=20)
    resp.raise_for_status()
    return resp


def _discover_child_links(html: str, base_url: str) -> list[str]:
    """
    Find all links on the page that are within /ch/en/help/ and are
    leaf article pages (i.e. contain a third path segment after /help/).
    """
    soup = BeautifulSoup(html, "lxml")
    links: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        # Only same domain, only /ch/en/help/ subtree, no fragments/queries
        if (
            parsed.netloc.endswith("ubs.com")
            and parsed.path.startswith("/ch/en/help/")
            and not parsed.fragment
            and not parsed.query
            and parsed.path.endswith(".html")
        ):
            links.add(full.split("#")[0])
    return sorted(links)


def scrape_page(url: str) -> dict | None:
    """Fetch, clean, and save a single page. Returns cleaned doc dict or None."""
    fname = _url_to_filename(url)
    raw_path = OUTPUT_RAW / f"{fname}.html"
    processed_path = OUTPUT_PROCESSED / f"{fname}.json"

    # Skip if already processed (resume-safe)
    if processed_path.exists():
        logger.info(f"SKIP (already done): {url}")
        with open(processed_path) as f:
            return json.load(f)

    if not is_allowed(url):
        logger.warning(f"SKIP (robots.txt disallows): {url}")
        return None

    try:
        resp = _fetch(url)
    except Exception as e:
        logger.error(f"FAILED to fetch {url}: {e}")
        return None

    html = resp.text

    # Save raw HTML
    raw_path.write_text(html, encoding="utf-8")

    # Clean and extract
    doc = clean_html(html, url)
    doc["doc_type"] = "help_faq"

    # Skip pages with no useful content
    if not doc["full_text"] or len(doc["full_text"]) < 100:
        logger.warning(f"SKIP (empty content): {url}")
        return None

    # Save processed JSON
    with open(processed_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    logger.info(f"OK: {url} → {len(doc['sections'])} sections, {len(doc['full_text'])} chars")
    return doc


def run_help_scraper(max_pages: int = 500) -> list[dict]:
    """
    Full crawl of the UBS help centre.
    Returns list of all successfully cleaned doc dicts.
    """
    visited: set[str] = set()
    queue: list[str] = list(HELP_SEED_URLS)
    docs: list[dict] = []

    logger.info(f"Starting help scraper with {len(queue)} seed URLs")

    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        logger.info(f"[{len(visited)}/{max_pages}] Scraping: {url}")
        doc = scrape_page(url)

        if doc:
            docs.append(doc)
            # Discover more links from this page
            raw_path = OUTPUT_RAW / f"{_url_to_filename(url)}.html"
            if raw_path.exists():
                child_links = _discover_child_links(raw_path.read_text(encoding="utf-8"), url)
                new_links = [l for l in child_links if l not in visited]
                logger.info(f"  Discovered {len(new_links)} new links from {url}")
                queue.extend(new_links)

    logger.info(f"Help scraper done. {len(docs)} pages scraped.")
    return docs


if __name__ == "__main__":
    docs = run_help_scraper()
    print(f"\nScraped {len(docs)} help pages.")
    print(f"Raw HTML saved to:     {OUTPUT_RAW}")
    print(f"Processed JSON saved to: {OUTPUT_PROCESSED}")
