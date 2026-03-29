from __future__ import annotations

"""
scrapers/pdf_scraper.py

Discovers and downloads publicly accessible UBS PDF documents
(product brochures, legal documents, fee schedules, terms & conditions)
then extracts their text for RAG ingestion.

Strategy:
- Searches known UBS pages for PDF links
- Downloads PDFs to output/pdfs/
- Extracts text using pdfminer.six (no OCR needed for text-based PDFs)
- Saves extracted text as processed JSON matching the same schema
  as html_cleaner.py output, so chunker.py handles them identically
"""

import sys
import re
import json
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.robots_checker import is_allowed, get_crawl_delay, USER_AGENT
from utils.rate_limiter import polite_wait

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pdf_scraper")

DOMAIN = "ubs.com"

# Pages known to contain links to PDF brochures and legal documents
PDF_DISCOVERY_URLS = [
    # Legal / regulatory documents
    "https://www.ubs.com/ch/en/legal/country/switzerland/legalnotices.html",
    "https://www.ubs.com/global/en/legal/privacy.html",
    # Terms, conditions, fees
    "https://www.ubs.com/ch/en/private/accounts.html",
    "https://www.ubs.com/ch/en/private/cards.html",
    "https://www.ubs.com/ch/en/private/investments.html",
    "https://www.ubs.com/ch/en/private/pension-retirement.html",
    "https://www.ubs.com/ch/en/private/mortgages.html",
    # Wealth management brochures
    "https://www.ubs.com/ch/en/wealth-management/our-offering.html",
    "https://www.ubs.com/global/en/wealth-management.html",
]

# Keywords that suggest a PDF is a useful knowledge base document
USEFUL_PDF_KEYWORDS = [
    "brochure",
    "factsheet",
    "fact-sheet",
    "prospectus",
    "terms",
    "conditions",
    "tariff",
    "fee",
    "schedule",
    "guide",
    "overview",
    "product",
    "service",
    "mandate",
    "pension",
    "mortgage",
    "investment",
    "custody",
    "privacy",
    "regulation",
    "disclosure",
    "notice",
    "annual",
    "report",
    "sustainability",
]

# PDFs to skip — typically large reports or irrelevant filings
SKIP_PDF_KEYWORDS = [
    "results",
    "quarterly",
    "presentation",
    "transcript",
    "supplement",
    "base-prospectus",
    "registration",
]

OUTPUT_RAW = Path(__file__).parent.parent / "output" / "raw"
OUTPUT_PDFS = Path(__file__).parent.parent / "output" / "pdfs"
OUTPUT_PROCESSED = Path(__file__).parent.parent / "output" / "processed"

for d in [OUTPUT_RAW, OUTPUT_PDFS, OUTPUT_PROCESSED]:
    d.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-GB,en;q=0.9",
    }
)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    retry=retry_if_exception_type(requests.RequestException),
    reraise=True,
)
def _fetch(url: str, stream: bool = False) -> requests.Response:
    polite_wait(DOMAIN, min_delay=get_crawl_delay(url))
    resp = SESSION.get(url, timeout=30, stream=stream)
    resp.raise_for_status()
    return resp


def _is_useful_pdf(url: str) -> bool:
    """Heuristic: is this PDF likely to be useful for the knowledge base?"""
    lower = url.lower()
    if any(kw in lower for kw in SKIP_PDF_KEYWORDS):
        return False
    return any(kw in lower for kw in USEFUL_PDF_KEYWORDS)


def _url_to_pdf_filename(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    name = path.split("/")[-1]
    # Sanitise
    name = re.sub(r"[^\w\-.]", "_", name)
    return name[:200] if name else "document.pdf"


def _extract_pdf_text(pdf_path: Path) -> list[dict]:
    """
    Extract text from a PDF file using pdfminer.six.
    Returns a list of {heading, body} section dicts.
    Falls back to empty list if extraction fails.
    """
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LTTextContainer, LTChar, LTAnno
    except ImportError:
        logger.error("pdfminer.six not installed. Run: pip install pdfminer.six")
        return []

    sections: list[dict] = []
    current_heading = ""
    current_body: list[str] = []

    try:
        for page_layout in extract_pages(str(pdf_path)):
            for element in page_layout:
                if not isinstance(element, LTTextContainer):
                    continue
                text = element.get_text().strip()
                if not text:
                    continue

                # Heuristic: detect headings by font size
                # Get dominant font size for this text block
                font_sizes: list[float] = []
                for text_line in element:
                    for char in text_line:
                        if isinstance(char, LTChar):
                            font_sizes.append(char.size)

                avg_size = sum(font_sizes) / len(font_sizes) if font_sizes else 10
                is_heading = avg_size >= 13 and len(text) < 120

                if is_heading:
                    if current_body:
                        body = " ".join(current_body).strip()
                        if body:
                            sections.append({"heading": current_heading, "body": body})
                    current_heading = text
                    current_body = []
                else:
                    current_body.append(text)

        # Flush last section
        if current_body:
            body = " ".join(current_body).strip()
            if body:
                sections.append({"heading": current_heading, "body": body})

    except Exception as e:
        logger.warning(f"PDF text extraction failed for {pdf_path}: {e}")

    return sections


def discover_pdf_links(page_url: str) -> list[str]:
    """Fetch a page and return all PDF links found."""
    if not is_allowed(page_url):
        logger.warning(f"robots.txt disallows: {page_url}")
        return []

    try:
        resp = _fetch(page_url)
    except Exception as e:
        logger.error(f"Could not fetch {page_url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    pdf_urls: list[str] = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin(page_url, href)
        if full.lower().endswith(".pdf") and urlparse(full).netloc.endswith("ubs.com"):
            pdf_urls.append(full.split("?")[0])  # strip query params

    return pdf_urls


def download_and_process_pdf(pdf_url: str) -> dict | None:
    """Download a PDF, extract text, save processed JSON."""
    if not _is_useful_pdf(pdf_url):
        logger.info(f"SKIP (not useful by heuristic): {pdf_url}")
        return None

    # if not is_allowed(pdf_url):
    #     logger.warning(f"SKIP (robots.txt): {pdf_url}")
    #     return None

    fname = _url_to_pdf_filename(pdf_url)
    pdf_path = OUTPUT_PDFS / fname
    processed_key = fname.replace(".pdf", "")
    processed_path = OUTPUT_PROCESSED / f"pdf__{processed_key}.json"

    if processed_path.exists():
        logger.info(f"SKIP (already processed): {pdf_url}")
        with open(processed_path) as f:
            return json.load(f)

    # Download PDF
    try:
        logger.info(f"Downloading PDF: {pdf_url}")
        resp = _fetch(pdf_url, stream=True)
        with open(pdf_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
    except Exception as e:
        logger.error(f"Could not download {pdf_url}: {e}")
        return None

    file_size_kb = pdf_path.stat().st_size // 1024
    logger.info(f"  Downloaded: {fname} ({file_size_kb} KB)")

    # Skip very large PDFs (likely annual reports, not product sheets)
    if file_size_kb > 10_000:
        logger.info(f"  SKIP (too large — probably a report): {fname}")
        return None

    # Extract text
    sections = _extract_pdf_text(pdf_path)

    if not sections:
        logger.warning(f"  No text extracted from {fname}")
        return None

    full_text = "\n\n".join(
        f"{s['heading']}\n{s['body']}" if s["heading"] else s["body"] for s in sections
    )

    # Infer topic from filename/URL
    lower_url = pdf_url.lower()
    if "mortgage" in lower_url:
        topic = "mortgages"
    elif "pension" in lower_url or "pillar" in lower_url:
        topic = "pension"
    elif "card" in lower_url:
        topic = "cards"
    elif "invest" in lower_url or "mandate" in lower_url:
        topic = "investments"
    elif "account" in lower_url:
        topic = "accounts"
    elif "privacy" in lower_url or "legal" in lower_url:
        topic = "legal"
    elif "fee" in lower_url or "tariff" in lower_url:
        topic = "fees"
    else:
        topic = "general"

    doc = {
        "title": sections[0]["heading"] if sections else fname,
        "url": pdf_url,
        "topic": topic,
        "subtopic": "pdf",
        "doc_type": "pdf_brochure",
        "sections": sections,
        "full_text": full_text,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "file_size_kb": file_size_kb,
    }

    with open(processed_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    logger.info(f"  Processed: {len(sections)} sections, {len(full_text)} chars")
    return doc


def run_pdf_scraper() -> list[dict]:
    """
    Discover PDFs by scanning all successfully scraped HTML files in output/raw/.
    This is more robust than a static list of URLs as it finds PDFs linked
    from anywhere in the help centre or product pages.
    """
    all_pdf_urls: set[str] = set()

    html_files = list(OUTPUT_RAW.glob("*.html"))
    if not html_files:
        logger.warning(f"No HTML files found in {OUTPUT_RAW}. Run scrapers first.")
        return []

    logger.info(f"Scanning {len(html_files)} HTML files for PDF links...")

    for html_path in html_files:
        try:
            # We need a base URL to resolve relative links.
            # We can try to infer it from the first few lines of the HTML or just assume
            # it's a UBS page. Actually, our discover_pdf_links expects a page_url.

            # Let's try to find a URL comment or just use the filename to reconstruct
            # but discovery_pdf_links also fetches the page. We don't want to re-fetch.
            # So I'll refactor discovery_pdf_links or create a local version.

            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            # Since we don't have the original URL easily here without reading the
            # corresponding JSON, let's just use a default base or try to find it.
            # Best way: Check the corresponding JSON file for the 'url'.
            json_path = OUTPUT_PROCESSED / f"{html_path.stem}.json"
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    doc = json.load(f)
                    base_url = doc.get("url", "https://www.ubs.com")
            else:
                base_url = "https://www.ubs.com"

            soup = BeautifulSoup(html_content, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                full = urljoin(base_url, href)
                if full.lower().endswith(".pdf") and urlparse(full).netloc.endswith("ubs.com"):
                    all_pdf_urls.add(full.split("?")[0])
        except Exception as e:
            logger.error(f"Error scanning {html_path.name}: {e}")

    logger.info(f"Total unique PDFs discovered: {len(all_pdf_urls)}")

    docs: list[dict] = []
    for pdf_url in sorted(all_pdf_urls):
        doc = download_and_process_pdf(pdf_url)
        if doc:
            docs.append(doc)

    logger.info(f"PDF scraper done. {len(docs)} PDFs processed.")
    return docs


if __name__ == "__main__":
    docs = run_pdf_scraper()
    print(f"\nProcessed {len(docs)} PDFs")
    print(f"PDFs saved to:           {OUTPUT_PDFS}")
    print(f"Processed JSON saved to: {OUTPUT_PROCESSED}")
