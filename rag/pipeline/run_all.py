from __future__ import annotations
"""
run_all.py

Orchestrates the full UBS knowledge base pipeline:

    Step 1: Check robots.txt (logged, not blocking)
    Step 2: Scrape help centre pages  → output/raw/ + output/processed/
    Step 3: Scrape product/service pages → output/raw/ + output/processed/
    Step 4: Chunk all processed docs  → output/chunks/
    Step 5: Ingest into ChromaDB      → collection: ubs_knowledge_base

Usage:
    python run_all.py                    # full pipeline
    python run_all.py --skip-scrape      # chunking + ingest only (re-run)
    python run_all.py --scrape-only      # scrape + chunk, no ingest
    python run_all.py --help-only        # only help pages
    python run_all.py --services-only    # only product pages
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_all")


def main():
    parser = argparse.ArgumentParser(description="UBS Knowledge Base Pipeline")
    parser.add_argument("--skip-scrape", action="store_true",
                        help="Skip scraping, use existing output/processed/ files")
    parser.add_argument("--scrape-only", action="store_true",
                        help="Scrape and chunk but do not ingest into ChromaDB")
    parser.add_argument("--help-only", action="store_true",
                        help="Only scrape help centre pages")
    parser.add_argument("--services-only", action="store_true",
                        help="Only scrape product/services pages")
    parser.add_argument("--skip-pdfs", action="store_true",
                        help="Skip PDF discovery and extraction")
    parser.add_argument("--max-help-pages", type=int, default=500)
    parser.add_argument("--max-service-pages", type=int, default=200)
    parser.add_argument("--test-query", action="store_true",
                        help="Run smoke test queries after ingest")
    args = parser.parse_args()

    total_docs = 0

    # ── Step 1: Robots check ─────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Step 1: Checking robots.txt")
    logger.info("=" * 60)
    from utils.robots_checker import get_crawl_delay, _get_robots
    robots = _get_robots("https://www.ubs.com")
    if robots:
        delay = get_crawl_delay("https://www.ubs.com")
        logger.info(f"Crawl delay from robots.txt: {delay}s")
    else:
        logger.info("No robots.txt found — will use default 2s delay")

    # ── Step 2 & 3: Scraping ─────────────────────────────────────────────────
    if not args.skip_scrape:
        if not args.services_only:
            logger.info("=" * 60)
            logger.info("Step 2: Scraping UBS Help Centre")
            logger.info("=" * 60)
            from scrapers.help_scraper import run_help_scraper
            help_docs = run_help_scraper(max_pages=args.max_help_pages)
            total_docs += len(help_docs)
            logger.info(f"Help scraper: {len(help_docs)} pages processed")

        if not args.help_only:
            logger.info("=" * 60)
            logger.info("Step 3: Scraping UBS Product / Services Pages")
            logger.info("=" * 60)
            from scrapers.services_scraper import run_services_scraper
            service_docs = run_services_scraper(max_pages=args.max_service_pages)
            total_docs += len(service_docs)
            logger.info(f"Services scraper: {len(service_docs)} pages processed")

        if not args.skip_pdfs and not args.help_only and not args.services_only:
            logger.info("=" * 60)
            logger.info("Step 3b: Scraping UBS PDFs (brochures, legal docs)")
            logger.info("=" * 60)
            from scrapers.pdf_scraper import run_pdf_scraper
            pdf_docs = run_pdf_scraper()
            total_docs += len(pdf_docs)
            logger.info(f"PDF scraper: {len(pdf_docs)} PDFs processed")
    else:
        logger.info("Skipping scrape — using existing processed files")
        processed_dir = Path(__file__).parent / "output" / "processed"
        total_docs = len(list(processed_dir.glob("*.json")))
        logger.info(f"Found {total_docs} existing processed files")

    # ── Step 4: Chunking ─────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Step 4: Chunking all processed documents")
    logger.info("=" * 60)
    from chunk_all import run_chunker
    counts = run_chunker()
    total_chunks = sum(counts.values())
    logger.info(f"Chunking complete: {total_chunks} total chunks")

    # ── Step 5: ChromaDB ingest ───────────────────────────────────────────────
    if not args.scrape_only:
        logger.info("=" * 60)
        logger.info("Step 5: Ingesting into ChromaDB")
        logger.info("=" * 60)
        from ingest_to_chroma import ingest, query_test
        final_count = ingest()

        if args.test_query:
            query_test()
    else:
        logger.info("Skipping ChromaDB ingest (--scrape-only flag set)")

    # ── Summary ───────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Pipeline complete!")
    logger.info(f"  Pages scraped/processed : {total_docs}")
    logger.info(f"  Chunks created          : {total_chunks}")
    for dt, count in counts.items():
        logger.info(f"    {dt:20s}: {count}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
