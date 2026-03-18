# UBS Knowledge Base Scraper

Scrapes public UBS help/FAQ and product pages for use as RAG knowledge base documents.

## Project Structure

```
ubs_scraper/
├── scrapers/
│   ├── help_scraper.py        # Crawls all /ch/en/help/* pages
│   └── services_scraper.py    # Crawls all /ch/en/services/* product pages
├── processors/
│   ├── html_cleaner.py        # Strips nav/footer, extracts clean text
│   └── chunker.py             # Splits into 300-500 token RAG chunks
├── utils/
│   ├── robots_checker.py      # Checks robots.txt before each domain crawl
│   └── rate_limiter.py        # Polite delay between requests
├── ingest_to_chroma.py        # Loads chunks → ChromaDB with metadata
├── run_all.py                 # Orchestrates full pipeline
├── requirements.txt
└── output/
    ├── raw/                   # Raw HTML per page
    ├── processed/             # Cleaned text JSON per page
    └── chunks/                # Final chunked JSONL ready for ChromaDB
```

## Quick Start

```bash
pip install -r requirements.txt
python run_all.py
```

## Output Format

Each chunk in `output/chunks/` is a JSONL file with records:
```json
{
  "id": "ubs-help-creditcard-lock-replacement-chunk-0",
  "text": "...",
  "metadata": {
    "source_url": "https://www.ubs.com/ch/en/help/creditcard/lock-replacement.html",
    "topic": "creditcard",
    "subtopic": "lock-replacement",
    "doc_type": "help_faq",
    "scraped_at": "2025-01-01T00:00:00Z",
    "chunk_index": 0,
    "total_chunks": 2
  }
}
```

## Legal & Ethics Notes

- Only scrapes publicly accessible pages (no login required)
- Respects robots.txt (checked before each crawl session)
- Polite rate limiting: 2-3 seconds between requests
- Content used for internal RAG only, not redistributed
- Source URL preserved in all chunk metadata for attribution
- UBS copyright notice: https://www.ubs.com/global/en/legal/disclaimer.html
