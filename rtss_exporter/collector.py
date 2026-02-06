"""Prometheus metric definitions and RTSS data collection logic."""

import logging
from typing import Any

from prometheus_client import Gauge

from .shared_memory import RTSSSharedMemoryReader
from .structs import (
    HEADER_STRUCT,
    APP_ENTRY_CORE_STRUCT,
    unpack_header,
    validate_header,
    unpack_app_entry_core,
    extract_exe_name,
    compute_fps,
    frame_time_us_to_ms,
)

logger = logging.getLogger(__name__)

# -- Prometheus metrics -------------------------------------------------------

rtss_fps = Gauge(
    'rtss_fps',
    'Current frames per second reported by RTSS',
    ['process'],
)

rtss_frame_time_ms = Gauge(
    'rtss_frame_time_milliseconds',
    'Current frame time in milliseconds reported by RTSS',
    ['process'],
)


# -- Collector ----------------------------------------------------------------

class RTSSCollector:
    """Reads RTSS shared memory and updates Prometheus Gauge metrics.

    Tracks which process labels are active so that stale labels can be
    removed when a game closes (preventing flat-lining graphs).
    """

    def __init__(self):
        self._known_processes: set[str] = set()
        self._reader = RTSSSharedMemoryReader()

    def collect(self) -> None:
        """Perform one collection cycle: read shared memory -> update metrics."""
        entries = self._read_entries()
        self._update_metrics(entries)

    # -- internals ------------------------------------------------------------

    def _read_entries(self) -> list[dict[str, Any]]:
        """Open RTSS shared memory and parse all active app entries."""
        if not self._reader.open():
            return []

        try:
            return self._parse_entries()
        except Exception:
            logger.exception("Error parsing RTSS shared memory")
            return []
        finally:
            self._reader.close()

    def _parse_entries(self) -> list[dict[str, Any]]:
        header_bytes = self._reader.read_bytes(0, HEADER_STRUCT.size)
        header = unpack_header(header_bytes)

        if not validate_header(header):
            logger.debug("Invalid RTSS header (sig=0x%08X, ver=0x%08X)",
                         header.dwSignature, header.dwVersion)
            return []

        entries: list[dict[str, Any]] = []

        for i in range(header.dwAppArrSize):
            offset = header.dwAppArrOffset + (i * header.dwAppEntrySize)

            # Only read the core fields we need (284 bytes), regardless of
            # dwAppEntrySize which can be 5000+ bytes in newer RTSS versions.
            read_size = min(APP_ENTRY_CORE_STRUCT.size, header.dwAppEntrySize)
            raw = self._reader.read_bytes(offset, read_size)

            if len(raw) < APP_ENTRY_CORE_STRUCT.size:
                continue

            entry = unpack_app_entry_core(raw)

            # Skip empty / unused slots
            if entry.dwProcessID == 0:
                continue

            exe_name = extract_exe_name(entry.szName)
            fps = compute_fps(entry.dwTime0, entry.dwTime1, entry.dwFrames)
            frame_time = frame_time_us_to_ms(entry.dwFrameTime)

            entries.append({
                'process': exe_name,
                'pid': entry.dwProcessID,
                'fps': fps,
                'frame_time_ms': frame_time,
            })

        return entries

    def _update_metrics(self, entries: list[dict[str, Any]]) -> None:
        """Push entry data into Prometheus Gauges and remove stale labels."""
        current_processes: set[str] = set()

        for entry in entries:
            name = entry['process']
            current_processes.add(name)
            rtss_fps.labels(process=name).set(entry['fps'])
            rtss_frame_time_ms.labels(process=name).set(entry['frame_time_ms'])

        # Remove metrics for processes that are no longer active
        stale = self._known_processes - current_processes
        for name in stale:
            rtss_fps.remove(name)
            rtss_frame_time_ms.remove(name)
            logger.info("Removed stale metrics for process: %s", name)

        if current_processes != self._known_processes:
            new = current_processes - self._known_processes
            for name in new:
                logger.info("Tracking new process: %s", name)

        self._known_processes = current_processes
