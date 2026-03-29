from __future__ import annotations

"""
scrapers/services_scraper.py

Crawls public UBS private banking product and services pages.
Target: /ch/en/wealth-management/, /ch/en/private/, /global/en/wealth-management/

These pages describe UBS's products, service tiers, and investment offerings —
the "what do you offer?" knowledge that the chatbot needs.
"""

import sys
import json
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.robots_checker import is_allowed, get_crawl_delay, USER_AGENT
from utils.rate_limiter import polite_wait
from processors.html_cleaner import clean_html

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("services_scraper")

DOMAIN = "ubs.com"

# Seed URLs for product and service information
# These cover: wealth management, private banking, investment products,
# digital banking services, cards, mortgages, and pension
SERVICES_SEED_URLS = [
    # Private / wealth management overview
    "https://www.ubs.com/ch/en/private.html",
    "https://www.ubs.com/ch/en/private/accounts.html",
    "https://www.ubs.com/ch/en/private/cards.html",
    "https://www.ubs.com/ch/en/private/investments.html",
    "https://www.ubs.com/ch/en/private/pension-retirement.html",
    "https://www.ubs.com/ch/en/private/mortgages.html",
    # Wealth management
    "https://www.ubs.com/ch/en/wealth-management.html",
    "https://www.ubs.com/ch/en/wealth-management/our-offering.html",
    "https://www.ubs.com/ch/en/wealth-management/investment-management.html",
    # Global wealth management (English, publicly accessible)
    "https://www.ubs.com/global/en/wealth-management.html",
    "https://www.ubs.com/global/en/wealth-management/our-services.html",
    # Digital banking
    "https://www.ubs.com/ch/en/private/digital-banking.html",
    "https://www.ubs.com/ch/en/private/digital-banking/e-banking.html",
    "https://www.ubs.com/ch/en/private/digital-banking/mobile-banking.html",
]

# Only follow links within these path prefixes
ALLOWED_PATH_PREFIXES = [
    "/ch/en/private",
    "/ch/en/wealth-management",
    "/global/en/wealth-management",
    "/ch/en/help",
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
    path = urlparse(url).path.strip("/").replace("/", "__")
    return path[:200] if path else "index"


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


def _discover_product_links(html: str, base_url: str) -> list[str]:
    """Find links within allowed product/service path prefixes."""
    soup = BeautifulSoup(html, "lxml")
    links: set[str] = set()
    for a in soup.find_all("a", href=True):
        full = urljoin(base_url, a["href"])
        parsed = urlparse(full)
        if (
            parsed.netloc.endswith("ubs.com")
            and any(parsed.path.startswith(prefix) for prefix in ALLOWED_PATH_PREFIXES)
            and not parsed.fragment
            and not parsed.query
            and parsed.path.endswith(".html")
        ):
            links.add(full.split("#")[0])
    return sorted(links)


def scrape_page(url: str, doc_type: str = "product_info") -> dict | None:
    """Fetch, clean and save a single product page."""
    fname = _url_to_filename(url)
    raw_path = OUTPUT_RAW / f"{fname}.html"
    processed_path = OUTPUT_PROCESSED / f"{fname}.json"

    if processed_path.exists():
        logger.info(f"SKIP (already done): {url}")
        with open(processed_path) as f:
            d = json.load(f)

    if not is_allowed(url):
        logger.warning(f"SKIP (robots.txt disallows): {url}")
        return None

    try:
        resp = _fetch(url)
    except Exception as e:
        logger.error(f"FAILED: {url}: {e}")
        return None

    html = resp.text
    raw_path.write_text(html, encoding="utf-8")

    doc = clean_html(html, url)
    doc["doc_type"] = doc_type

    if not doc["full_text"] or len(doc["full_text"]) < 100:
        logger.warning(f"SKIP (empty): {url}")
        return None

    with open(processed_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    logger.info(f"OK: {url} → {len(doc['sections'])} sections")
    return doc


def run_services_scraper(max_pages: int = 200) -> list[dict]:
    """Full crawl of UBS product/service pages."""
    visited: set[str] = set()
    queue: list[str] = list(SERVICES_SEED_URLS)
    docs: list[dict] = []

    logger.info(f"Starting services scraper with {len(queue)} seed URLs")

    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        logger.info(f"[{len(visited)}/{max_pages}] Scraping: {url}")
        doc = scrape_page(url, doc_type="product_info")

        if doc:
            docs.append(doc)
            raw_path = OUTPUT_RAW / f"{_url_to_filename(url)}.html"
            if raw_path.exists():
                new_links = [
                    l
                    for l in _discover_product_links(raw_path.read_text(encoding="utf-8"), url)
                    if l not in visited
                ]
                logger.info(f"  Discovered {len(new_links)} new links")
                queue.extend(new_links)

    logger.info(f"Services scraper done. {len(docs)} pages scraped.")
    return docs


if __name__ == "__main__":
    docs = run_services_scraper()
    print(f"\nScraped {len(docs)} service/product pages.")
