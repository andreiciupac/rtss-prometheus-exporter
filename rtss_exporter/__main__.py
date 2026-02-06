"""CLI entry point for the RTSS Prometheus Exporter.

Usage:
    python -m rtss_exporter [--port 9101] [--interval 2.0] [--log-level INFO]
"""

import argparse
import logging
import signal
import sys

from prometheus_client import start_http_server

from .config import DEFAULT_PORT, DEFAULT_POLL_INTERVAL
from .exporter import run_loop


def main() -> None:
    parser = argparse.ArgumentParser(
        description='RTSS Prometheus Exporter — exports FPS and FrameTime metrics'
    )
    parser.add_argument(
        '--port', type=int, default=DEFAULT_PORT,
        help=f'HTTP port for the /metrics endpoint (default: {DEFAULT_PORT})',
    )
    parser.add_argument(
        '--interval', type=float, default=DEFAULT_POLL_INTERVAL,
        help=f'Poll interval in seconds (default: {DEFAULT_POLL_INTERVAL})',
    )
    parser.add_argument(
        '--log-level', default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging verbosity (default: INFO)',
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )

    # Graceful shutdown on Ctrl+C or service stop signal
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    start_http_server(args.port, addr='0.0.0.0')
    logging.getLogger(__name__).info(
        "Serving metrics on http://0.0.0.0:%d/metrics", args.port
    )

    run_loop(poll_interval=args.interval)


if __name__ == '__main__':
    main()
