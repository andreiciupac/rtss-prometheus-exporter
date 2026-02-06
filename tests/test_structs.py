"""Unit tests for RTSS struct parsing with known byte sequences."""

import struct
import unittest

from rtss_exporter.config import RTSS_SIGNATURE, RTSS_VERSION_2_0
from rtss_exporter.structs import (
    HEADER_STRUCT,
    APP_ENTRY_CORE_STRUCT,
    RTSSHeader,
    AppEntryCore,
    unpack_header,
    validate_header,
    unpack_app_entry_core,
    extract_exe_name,
    compute_fps,
    frame_time_us_to_ms,
)


def _build_header(
    signature=RTSS_SIGNATURE,
    version=0x00020007,
    app_entry_size=5028,
    app_arr_offset=36,
    app_arr_size=256,
    osd_entry_size=0,
    osd_arr_offset=0,
    osd_arr_size=0,
    osd_frame=0,
) -> bytes:
    """Build a fake RTSS header for testing."""
    return HEADER_STRUCT.pack(
        signature, version, app_entry_size, app_arr_offset,
        app_arr_size, osd_entry_size, osd_arr_offset, osd_arr_size,
        osd_frame,
    )


def _build_app_entry(
    pid=1234,
    name=b'C:\\Games\\game.exe',
    flags=0x01000000,
    time0=1000,
    time1=2000,
    frames=60,
    frame_time=16667,
) -> bytes:
    """Build a fake RTSS app entry (core fields) for testing."""
    # Pad name to 260 bytes
    name_padded = name + b'\x00' * (260 - len(name))
    return APP_ENTRY_CORE_STRUCT.pack(
        pid, name_padded, flags, time0, time1, frames, frame_time,
    )


class TestHeaderParsing(unittest.TestCase):
    def test_valid_header(self):
        raw = _build_header()
        header = unpack_header(raw)
        self.assertEqual(header.dwSignature, RTSS_SIGNATURE)
        self.assertEqual(header.dwVersion, 0x00020007)
        self.assertEqual(header.dwAppEntrySize, 5028)
        self.assertEqual(header.dwAppArrOffset, 36)
        self.assertEqual(header.dwAppArrSize, 256)

    def test_validate_header_valid(self):
        raw = _build_header()
        header = unpack_header(raw)
        self.assertTrue(validate_header(header))

    def test_validate_header_bad_signature(self):
        raw = _build_header(signature=0xDEAD)
        header = unpack_header(raw)
        self.assertFalse(validate_header(header))

    def test_validate_header_old_version(self):
        raw = _build_header(version=0x00010000)
        header = unpack_header(raw)
        self.assertFalse(validate_header(header))

    def test_validate_header_v2_0_minimum(self):
        raw = _build_header(version=RTSS_VERSION_2_0)
        header = unpack_header(raw)
        self.assertTrue(validate_header(header))


class TestAppEntryParsing(unittest.TestCase):
    def test_basic_entry(self):
        raw = _build_app_entry()
        entry = unpack_app_entry_core(raw)
        self.assertEqual(entry.dwProcessID, 1234)
        self.assertEqual(entry.dwFlags, 0x01000000)
        self.assertEqual(entry.dwTime0, 1000)
        self.assertEqual(entry.dwTime1, 2000)
        self.assertEqual(entry.dwFrames, 60)
        self.assertEqual(entry.dwFrameTime, 16667)

    def test_empty_slot(self):
        raw = _build_app_entry(pid=0)
        entry = unpack_app_entry_core(raw)
        self.assertEqual(entry.dwProcessID, 0)

    def test_unpack_at_offset(self):
        padding = b'\x00' * 100
        raw = padding + _build_app_entry(pid=5678)
        entry = unpack_app_entry_core(raw, offset=100)
        self.assertEqual(entry.dwProcessID, 5678)


class TestExeNameExtraction(unittest.TestCase):
    def test_full_path(self):
        name = b'C:\\Games\\game.exe' + b'\x00' * 243
        self.assertEqual(extract_exe_name(name), 'game.exe')

    def test_just_filename(self):
        name = b'game.exe' + b'\x00' * 252
        self.assertEqual(extract_exe_name(name), 'game.exe')

    def test_deep_path(self):
        name = b'C:\\Program Files\\Steam\\steamapps\\common\\Cyberpunk 2077\\bin\\x64\\Cyberpunk2077.exe'
        name += b'\x00' * (260 - len(name))
        self.assertEqual(extract_exe_name(name), 'cyberpunk2077.exe')

    def test_uppercase_normalized(self):
        name = b'C:\\GAME.EXE' + b'\x00' * 249
        self.assertEqual(extract_exe_name(name), 'game.exe')

    def test_all_nulls(self):
        name = b'\x00' * 260
        self.assertEqual(extract_exe_name(name), '')


class TestFPSCalculation(unittest.TestCase):
    def test_basic_fps(self):
        # 60 frames in 1000ms = 60 FPS
        fps = compute_fps(1000, 2000, 60)
        self.assertAlmostEqual(fps, 60.0, places=1)

    def test_zero_frames(self):
        self.assertEqual(compute_fps(1000, 2000, 0), 0.0)

    def test_zero_time_delta(self):
        self.assertEqual(compute_fps(1000, 1000, 60), 0.0)

    def test_high_fps(self):
        # 144 frames in 1000ms = 144 FPS
        fps = compute_fps(0, 1000, 144)
        self.assertAlmostEqual(fps, 144.0, places=1)

    def test_gettickcount_wraparound(self):
        # dwTime0 near max, dwTime1 wrapped around
        # delta should be (0xFFFFFFFF - 0xFFFFFFF0) + 100 + 1 = 116 ms
        fps = compute_fps(0xFFFFFFF0, 100, 10)
        expected_dt_ms = (0xFFFFFFFF - 0xFFFFFFF0) + 100 + 1  # 116
        expected_fps = 10 / (expected_dt_ms / 1000.0)
        self.assertAlmostEqual(fps, expected_fps, places=1)


class TestFrameTimeConversion(unittest.TestCase):
    def test_16667_us(self):
        # 16667 us = 16.667 ms (60 FPS)
        self.assertAlmostEqual(frame_time_us_to_ms(16667), 16.667, places=3)

    def test_zero(self):
        self.assertEqual(frame_time_us_to_ms(0), 0.0)

    def test_6944_us(self):
        # 6944 us ≈ 6.944 ms (144 FPS)
        self.assertAlmostEqual(frame_time_us_to_ms(6944), 6.944, places=3)


if __name__ == '__main__':
    unittest.main()
