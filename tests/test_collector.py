"""Unit tests for the Prometheus metric collector logic."""

import unittest
from unittest.mock import patch, MagicMock

from prometheus_client import REGISTRY

from rtss_exporter.collector import RTSSCollector, rtss_fps, rtss_frame_time_ms


class TestRTSSCollector(unittest.TestCase):
    def setUp(self):
        """Reset metric state before each test."""
        # Clear any existing label children
        rtss_fps._metrics.clear()
        rtss_frame_time_ms._metrics.clear()
        self.collector = RTSSCollector()

    def test_update_adds_metrics(self):
        entries = [
            {'process': 'game.exe', 'pid': 1234, 'fps': 60.0, 'frame_time_ms': 16.667},
        ]
        self.collector._update_metrics(entries)

        # Verify the gauge was set
        sample = rtss_fps.labels(process='game.exe')._value.get()
        self.assertAlmostEqual(sample, 60.0)

        sample_ft = rtss_frame_time_ms.labels(process='game.exe')._value.get()
        self.assertAlmostEqual(sample_ft, 16.667)

    def test_update_multiple_processes(self):
        entries = [
            {'process': 'game1.exe', 'pid': 100, 'fps': 60.0, 'frame_time_ms': 16.667},
            {'process': 'game2.exe', 'pid': 200, 'fps': 144.0, 'frame_time_ms': 6.944},
        ]
        self.collector._update_metrics(entries)

        self.assertAlmostEqual(
            rtss_fps.labels(process='game1.exe')._value.get(), 60.0)
        self.assertAlmostEqual(
            rtss_fps.labels(process='game2.exe')._value.get(), 144.0)

    def test_stale_removal(self):
        # First cycle: game is running
        entries = [
            {'process': 'game.exe', 'pid': 1234, 'fps': 60.0, 'frame_time_ms': 16.667},
        ]
        self.collector._update_metrics(entries)

        # Verify it exists
        self.assertIn(('game.exe',), rtss_fps._metrics)

        # Second cycle: game closed
        self.collector._update_metrics([])

        # Verify it was removed
        self.assertNotIn(('game.exe',), rtss_fps._metrics)
        self.assertNotIn(('game.exe',), rtss_frame_time_ms._metrics)

    def test_stale_partial_removal(self):
        # Two games running
        entries = [
            {'process': 'game1.exe', 'pid': 100, 'fps': 60.0, 'frame_time_ms': 16.667},
            {'process': 'game2.exe', 'pid': 200, 'fps': 144.0, 'frame_time_ms': 6.944},
        ]
        self.collector._update_metrics(entries)

        # game1 closes, game2 stays
        entries = [
            {'process': 'game2.exe', 'pid': 200, 'fps': 120.0, 'frame_time_ms': 8.333},
        ]
        self.collector._update_metrics(entries)

        self.assertNotIn(('game1.exe',), rtss_fps._metrics)
        self.assertIn(('game2.exe',), rtss_fps._metrics)
        self.assertAlmostEqual(
            rtss_fps.labels(process='game2.exe')._value.get(), 120.0)

    def test_empty_entries_first_cycle(self):
        """No crash when first cycle has no entries."""
        self.collector._update_metrics([])
        self.assertEqual(len(rtss_fps._metrics), 0)


if __name__ == '__main__':
    unittest.main()
