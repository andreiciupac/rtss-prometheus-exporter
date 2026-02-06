"""RTSS shared memory struct definitions and binary parsing logic."""

import struct
from typing import NamedTuple

from .config import RTSS_SIGNATURE, RTSS_VERSION_2_0

# ---------------------------------------------------------------------------
# Header: first 36 bytes of the shared memory
# ---------------------------------------------------------------------------

HEADER_STRUCT = struct.Struct('<9I')  # 9 x uint32, little-endian = 36 bytes


class RTSSHeader(NamedTuple):
    dwSignature: int       # 0x53535452 ('RTSS') when valid
    dwVersion: int         # (major << 16) | minor
    dwAppEntrySize: int    # size in bytes of each APP_ENTRY
    dwAppArrOffset: int    # byte offset from start to first APP_ENTRY
    dwAppArrSize: int      # number of APP_ENTRY slots allocated
    dwOSDEntrySize: int
    dwOSDArrOffset: int
    dwOSDArrSize: int
    dwOSDFrame: int


def unpack_header(data: bytes) -> RTSSHeader:
    """Unpack the RTSS shared memory header from raw bytes."""
    return RTSSHeader(*HEADER_STRUCT.unpack_from(data, 0))


def validate_header(header: RTSSHeader) -> bool:
    """Return True if the header has a valid signature and supported version."""
    if header.dwSignature != RTSS_SIGNATURE:
        return False
    if header.dwVersion < RTSS_VERSION_2_0:
        return False
    return True


# ---------------------------------------------------------------------------
# App Entry: core fields (first 284 bytes of each entry)
# ---------------------------------------------------------------------------
# Layout:
#   0     DWORD      dwProcessID
#   4     char[260]  szName (null-terminated, MAX_PATH)
#   264   DWORD      dwFlags
#   268   DWORD      dwTime0   (period start, ms)
#   272   DWORD      dwTime1   (period end, ms)
#   276   DWORD      dwFrames  (frames in period)
#   280   DWORD      dwFrameTime (instantaneous frame time, microseconds)
# ---------------------------------------------------------------------------

APP_ENTRY_CORE_STRUCT = struct.Struct('<I 260s 5I')  # 284 bytes


class AppEntryCore(NamedTuple):
    dwProcessID: int
    szName: bytes
    dwFlags: int
    dwTime0: int
    dwTime1: int
    dwFrames: int
    dwFrameTime: int  # microseconds


def unpack_app_entry_core(data: bytes, offset: int = 0) -> AppEntryCore:
    """Unpack the core fields of an RTSS app entry."""
    return AppEntryCore(*APP_ENTRY_CORE_STRUCT.unpack_from(data, offset))


def extract_exe_name(szName: bytes) -> str:
    """Extract the lowercased executable filename from a null-terminated path.

    Example: b'C:\\Games\\game.exe\\x00...' -> 'game.exe'
    """
    path = szName.split(b'\x00', 1)[0].decode('ascii', errors='replace')
    return path.rsplit('\\', 1)[-1].lower()


def compute_fps(dwTime0: int, dwTime1: int, dwFrames: int) -> float:
    """Compute FPS from the RTSS timing fields.

    Handles the GetTickCount 32-bit wraparound (~49.7 days).
    """
    if dwFrames == 0:
        return 0.0

    # Handle 32-bit unsigned wraparound
    if dwTime1 >= dwTime0:
        dt_ms = dwTime1 - dwTime0
    else:
        dt_ms = (0xFFFFFFFF - dwTime0) + dwTime1 + 1

    if dt_ms == 0:
        return 0.0

    return dwFrames / (dt_ms / 1000.0)


def frame_time_us_to_ms(dwFrameTime: int) -> float:
    """Convert RTSS frame time from microseconds to milliseconds."""
    return dwFrameTime / 1000.0
