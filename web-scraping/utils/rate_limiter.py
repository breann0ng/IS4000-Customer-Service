from __future__ import annotations
import time
import random
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)
_last_request_time = defaultdict(float)

def polite_wait(domain, min_delay=2.0, jitter=1.0):
    now = time.time()
    elapsed = now - _last_request_time[domain]
    wait = max(0.0, min_delay - elapsed) + random.uniform(0, jitter)
    if wait > 0:
        time.sleep(wait)
    _last_request_time[domain] = time.time()
