from __future__ import annotations
import requests
from protego import Protego
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)
USER_AGENT = "UBSKnowledgeBaseBot/1.0 (internal RAG pipeline; contact: your@email.com)"
_robots_cache = {}

def _get_robots(base_url):
    parsed = urlparse(base_url)
    domain = f"{parsed.scheme}://{parsed.netloc}"
    if domain in _robots_cache:
        return _robots_cache[domain]
    robots_url = f"{domain}/robots.txt"
    try:
        resp = requests.get(robots_url, timeout=10, headers={"User-Agent": USER_AGENT})
        if resp.status_code == 200:
            robots = Protego.parse(resp.text)
            _robots_cache[domain] = robots
            return robots
    except Exception as e:
        logger.warning(f"Could not fetch robots.txt: {e}")
    return None

def is_allowed(url):
    robots = _get_robots(url)
    if robots is None:
        return True
    return robots.can_fetch(url, USER_AGENT)

def get_crawl_delay(url):
    robots = _get_robots(url)
    if robots is None:
        return 2.0
    delay = robots.crawl_delay(USER_AGENT)
    return float(delay) if delay else 2.0
