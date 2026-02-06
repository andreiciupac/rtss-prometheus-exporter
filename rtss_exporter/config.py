"""Configuration constants for the RTSS Prometheus Exporter."""

DEFAULT_PORT = 9101
DEFAULT_POLL_INTERVAL = 2.0  # seconds
SHARED_MEMORY_NAME = "RTSSSharedMemoryV2"
RTSS_SIGNATURE = 0x52545353  # 'RTSS' as DWORD (big-endian representation)
RTSS_VERSION_2_0 = 0x00020000
