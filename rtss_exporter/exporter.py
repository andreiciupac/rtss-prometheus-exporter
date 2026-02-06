"""Main poll loop that drives RTSS metric collection."""

import time
import logging

from .collector import RTSSCollector
from .config import DEFAULT_POLL_INTERVAL

logger = logging.getLogger(__name__)


def run_loop(poll_interval: float = DEFAULT_POLL_INTERVAL) -> None:
    """Run the collection loop indefinitely.

    Each cycle opens the RTSS shared memory, reads all active app entries,
    updates the Prometheus Gauges, and closes the handle.  When RTSS is not
    running the loop stays alive and clears all metrics until RTSS returns.
    """
    collector = RTSSCollector()
    logger.info("Starting collection loop (interval=%.1fs)", poll_interval)

    while True:
        collector.collect()
        time.sleep(poll_interval)
