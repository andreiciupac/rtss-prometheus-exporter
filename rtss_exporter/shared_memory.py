"""Win32 API wrapper for reading RTSS shared memory via ctypes."""

import ctypes
from ctypes import wintypes
import logging

from .config import SHARED_MEMORY_NAME

logger = logging.getLogger(__name__)

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# Constants
FILE_MAP_READ = 0x0004

# OpenFileMappingW — opens an EXISTING named shared memory object.
# Returns NULL if the object does not exist (i.e., RTSS is not running).
_OpenFileMappingW = kernel32.OpenFileMappingW
_OpenFileMappingW.restype = wintypes.HANDLE
_OpenFileMappingW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]

# MapViewOfFile — maps the shared memory into our process address space.
_MapViewOfFile = kernel32.MapViewOfFile
_MapViewOfFile.restype = ctypes.c_void_p
_MapViewOfFile.argtypes = [
    wintypes.HANDLE,  # hFileMappingObject
    wintypes.DWORD,   # dwDesiredAccess
    wintypes.DWORD,   # dwFileOffsetHigh
    wintypes.DWORD,   # dwFileOffsetLow
    ctypes.c_size_t,  # dwNumberOfBytesToMap (0 = entire mapping)
]

_UnmapViewOfFile = kernel32.UnmapViewOfFile
_UnmapViewOfFile.restype = wintypes.BOOL
_UnmapViewOfFile.argtypes = [ctypes.c_void_p]

_CloseHandle = kernel32.CloseHandle
_CloseHandle.restype = wintypes.BOOL
_CloseHandle.argtypes = [wintypes.HANDLE]


class RTSSSharedMemoryReader:
    """Reads raw bytes from the RTSS shared memory mapping.

    Usage:
        reader = RTSSSharedMemoryReader()
        if reader.open():
            data = reader.read_bytes(0, 36)
            reader.close()
    """

    def __init__(self):
        self._handle = None
        self._view = None

    def open(self) -> bool:
        """Open the RTSS shared memory for reading.

        Returns True on success, False if RTSS is not running or the shared
        memory is not available in this session.
        """
        self._handle = _OpenFileMappingW(FILE_MAP_READ, False, SHARED_MEMORY_NAME)
        if not self._handle:
            error = ctypes.get_last_error()
            logger.debug("OpenFileMappingW failed (error %d) — RTSS not running?", error)
            return False

        self._view = _MapViewOfFile(self._handle, FILE_MAP_READ, 0, 0, 0)
        if not self._view:
            error = ctypes.get_last_error()
            logger.warning("MapViewOfFile failed (error %d)", error)
            _CloseHandle(self._handle)
            self._handle = None
            return False

        return True

    def read_bytes(self, offset: int, size: int) -> bytes:
        """Read ``size`` bytes from the shared memory at ``offset``."""
        if not self._view:
            raise RuntimeError("Shared memory is not open")
        return ctypes.string_at(self._view + offset, size)

    def close(self):
        """Unmap and close the shared memory handle."""
        if self._view:
            _UnmapViewOfFile(self._view)
            self._view = None
        if self._handle:
            _CloseHandle(self._handle)
            self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
